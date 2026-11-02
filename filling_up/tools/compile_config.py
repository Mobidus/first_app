"""Compile canonical JSON configuration into Luau modules (src/shared/GeneratedConfig).

The JSON files in config/ are the single source of truth. This compiler:
  * validates invariants that the game code relies on (blocking errors),
  * emits read-only Luau tables (JSON null -> key omitted -> nil in Luau),
  * stamps a content hash used as `configVersion` locked by each expedition.
No constant is duplicated by hand in game code.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"
OUT = ROOT / "src" / "shared" / "GeneratedConfig"
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
LUAU_KEYWORDS = {"and", "break", "do", "else", "elseif", "end", "false", "for", "function", "if", "in", "local",
                 "nil", "not", "or", "repeat", "return", "then", "true", "until", "while", "continue", "type", "export"}


class ConfigError(Exception):
    pass


def luau_string(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)  # JSON string escapes are valid Luau escapes


def to_luau(value, indent: int = 0, path: str = "$") -> str:
    pad = "\t" * indent
    if value is None:
        raise ConfigError(f"null inside an array at {path} cannot be represented")
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ConfigError(f"non-finite number at {path}")
        return repr(value)
    if isinstance(value, str):
        return luau_string(value)
    if isinstance(value, list):
        if not value:
            return "{}"
        items = [to_luau(v, indent + 1, f"{path}[{i}]") for i, v in enumerate(value)]
        if all(not isinstance(v, (dict, list)) for v in value) and sum(len(x) for x in items) < 100:
            return "{ " + ", ".join(items) + " }"
        return "{\n" + "".join(f"{pad}\t{x},\n" for x in items) + pad + "}"
    if isinstance(value, dict):
        lines = []
        for k, v in value.items():
            if v is None:
                continue  # JSON null == "absent / not configured" -> nil
            key = k if IDENT.match(k) and k not in LUAU_KEYWORDS else f"[{luau_string(k)}]"
            lines.append(f"{pad}\t{key} = {to_luau(v, indent + 1, f'{path}.{k}')},\n")
        if not lines:
            return "{}"
        return "{\n" + "".join(lines) + pad + "}"
    raise ConfigError(f"unsupported type {type(value)} at {path}")


def load(name: str):
    return json.loads((CONFIG / f"{name}.json").read_text(encoding="utf-8"))


def validate(econ, rooms, runtime) -> list[str]:
    errors: list[str] = []

    def check(cond, msg):
        if not cond:
            errors.append(msg)

    # canonical invariants (AGENTS.md)
    check(runtime.get("room_time_limit_seconds") is None, "runtime.room_time_limit_seconds must be null")
    check(runtime.get("max_rooms_per_run") is None, "runtime.max_rooms_per_run must be null")
    check(runtime.get("fill_percentage_causes_ko") is False, "fill_percentage_causes_ko must be false")
    check(set(runtime["ko_causes"]) <= {"confirmed_burial", "marked_kill_volume"}, "unknown KO cause")
    check(runtime["streaming"]["max_resident_room_modules"] == 3, "resident modules must be 3")
    check(runtime["streaming"]["max_dynamic_objects"] == 40, "dynamic objects budget must be 40")
    d = runtime["deformation"]
    check(d["impact_scale_y_min"] >= 0.72 - 1e-9 and d["fall_stretch_y_max"] <= 1.12 + 1e-9, "deformation caps")
    check(d["impact_compression_seconds"] + d["rebound_seconds"] <= d["max_total_settle_seconds"], "pose phases exceed cap")
    check(d["settle_seconds"] <= d["max_total_settle_seconds"], "settle exceeds cap")
    check(d["deformation_affects_reward_or_burial"] is False, "deformation must not affect rewards/burial")
    # economy
    check(sum(econ["tutorial"]["rewards"]) == econ["tutorial"]["total_coins"] == 65, "tutorial must total 65")
    tools = {t["id"]: t for t in econ["tools"]}
    check(len(tools) == len(econ["tools"]) == 12, "12 unique tools")
    check(tools.get("radar_pop", {}).get("coins") == 50, "radar_pop costs 50")
    up = econ["upgrade_costs"]
    for t in econ["tools"]:
        r2 = max(up["rank_2_minimum"], math.ceil(t["coins"] * up["rank_2_base_price_factor"] / up["rank_2_round_up_multiple"]) * up["rank_2_round_up_multiple"])
        r3 = max(up["rank_3_minimum"], int(t["coins"] * up["rank_3_base_price_factor"]))
        check(t["ranks"][1]["upgrade_coins"] == r2, f"{t['id']} rank2 cost mismatch")
        check(t["ranks"][2]["upgrade_coins"] == r3, f"{t['id']} rank3 cost mismatch")
        check(t["slot"] in ("active", "passive"), f"{t['id']} slot")
    prev = 0
    for b in econ["reward_bands"]:
        check(b["min_depth"] == prev + 1, f"reward band gap at {b['min_depth']}")
        check(sum(b["milestones"]) + b["exit_reward"] == b["base_total"], f"band {b['min_depth']} total")
        prev = b["max_depth"] or prev
    check(econ["reward_bands"][-1]["max_depth"] is None, "last reward band must be open-ended")
    cos_ids = [c["id"] for c in econ["cosmetics"]]
    check(len(cos_ids) == len(set(cos_ids)) == 24, "24 unique cosmetics")
    for c in econ["cosmetics"]:
        req = c["unlock"].get("requires_tool_id")
        check(req is None or req in tools, f"cosmetic {c['id']} requires unknown tool {req}")
    check(econ["monetization"]["robux_shop_enabled"] is False, "robux shop must stay disabled in this delivery")
    check(all(p["product_id"] is None for p in econ["coin_packs"]), "coin pack product ids must be null (no real ids)")
    check(all(p["gamepass_id"] is None for p in econ["premium_cosmetics"]), "gamepass ids must be null")
    # rooms
    fams = {f["id"]: f for f in rooms["families"]}
    exits = {e["id"] for e in rooms["exit_types"]}
    for f in rooms["families"]:
        check(set(f["formats"]) == {"S", "M", "L", "V"}, f"{f['id']} formats")
        check(set(f["exits"]) <= exits, f"{f['id']} exits")
        check(len(f["props"]) == 8, f"{f['id']} must have 8 props")
        for p in f["props"]:
            col = p["collider"]
            check(col["shape"] == "box", f"{p['id']} collider must be box")
            for i in range(3):
                check(col["size_studs"][i] <= p["size_studs"][i] + 1e-9, f"{p['id']} collider exceeds visual envelope")
            check(min(col["walkable_top"]) > 0, f"{p['id']} walkable top")
    for r in rooms["first_rooms"]:
        check(r["family"] in fams, f"first room {r['depth']} family")
        check(r.get("final_room") in (None, False), "no final room")
    for prof in rooms["release_profiles"].values():
        check(set(prof["families"]) <= set(fams), "release families")
        check(set(prof["exits"]) <= exits, "release exits")
    prev = 0
    for b in rooms["difficulty_bands"]:
        check(b["depth_min"] == prev + 1, f"difficulty band gap {b['id']}")
        check(0 < b["maximum_required_gap_ratio"] <= 0.85 + 1e-9, f"{b['id']} gap ratio bounded")
        check(b["wave_interval_seconds"] >= 7.5 - 1e-9, f"{b['id']} wave interval bounded")
        prev = b["depth_max"] or prev
    check(rooms["difficulty_bands"][-1]["depth_max"] is None, "last difficulty band open-ended")
    check(rooms["mode"]["room_limit"] is None and rooms["mode"]["bin_is_final_boss"] is False, "no room limit / final boss")
    check(rooms["validation_rules"]["exit_approach_clearance_studs"] == [8, 8, 10], "exit clearance 8x8x10")
    return errors


def main(argv: list[str]) -> int:
    check_only = "--check" in argv
    econ, rooms, runtime = load("economy"), load("rooms"), load("runtime")
    errors = validate(econ, rooms, runtime)
    raw = b"".join((CONFIG / f"{n}.json").read_bytes() for n in ("economy", "rooms", "runtime"))
    digest = hashlib.sha256(raw).hexdigest()[:16]
    result = {"status": "FAIL" if errors else "PASS", "errors": errors, "config_version": digest}
    if errors:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 1
    modules = {"Economy": econ, "Rooms": rooms, "Runtime": runtime}
    rendered = {}
    header = "--!strict\n-- AUTO-GENERATED by tools/compile_config.py from config/{src}.json. DO NOT EDIT.\n"
    for name, data in modules.items():
        rendered[f"{name}.luau"] = header.format(src=name.lower()) + "return table.freeze(" + to_luau(data) + ")\n"
    rendered["init.luau"] = (
        "--!strict\n-- AUTO-GENERATED by tools/compile_config.py. DO NOT EDIT.\n"
        "return table.freeze({\n"
        f"\tconfigVersion = \"{digest}\",\n"
        "\tEconomy = require(script.Economy),\n\tRooms = require(script.Rooms),\n\tRuntime = require(script.Runtime),\n})\n"
    )
    if check_only:
        stale = [n for n, txt in rendered.items() if not (OUT / n).exists() or (OUT / n).read_text(encoding="utf-8") != txt]
        result["stale_generated_files"] = stale
        if stale:
            result["status"] = "FAIL"
            result["errors"].append("generated config out of date; run tools/compile_config.py")
        print(json.dumps(result, indent=2))
        return 0 if not stale else 1
    OUT.mkdir(parents=True, exist_ok=True)
    for n, txt in rendered.items():
        (OUT / n).write_text(txt, encoding="utf-8")
    result["written"] = sorted(rendered)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
