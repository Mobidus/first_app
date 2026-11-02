"""Validate the specification bundle. Does not certify any Roblox asset or game."""
from pathlib import Path
import json
import math

ROOT = Path(__file__).resolve().parents[1]


def read(relative):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def unique(items, key="id"):
    values = [item[key] for item in items]
    assert len(values) == len(set(values)), f"Duplicate {key}"


def validate(initial_delivery=False):
    econ, rooms, runtime = [read(f"config/{name}.json") for name in ["economy", "rooms", "runtime"]]
    backlog = read("tasks/backlog.json")
    assets = read("assets/manifest.json")
    assert runtime["room_time_limit_seconds"] is None
    assert runtime["max_rooms_per_run"] is None
    assert runtime["fill_percentage_causes_ko"] is False
    assert runtime["waves_continue_over_time"] is True
    assert runtime["streaming"]["max_dynamic_objects"] == 40
    assert runtime["streaming"]["max_resident_room_modules"] == 3
    assert len(econ["tools"]) == 12
    assert len(econ["cosmetics"]) == 24
    unique(econ["tools"]); unique(econ["cosmetics"])
    assert sum(econ["tutorial"]["rewards"]) == 65
    assert econ["tools"][0]["id"] == "radar_pop"
    assert econ["tools"][0]["coins"] == 50
    previous_max = 0
    for band in econ["reward_bands"]:
        assert band["min_depth"] == previous_max + 1
        assert sum(band["milestones"]) + band["exit_reward"] == band["base_total"]
        assert band["permits"] >= 1
        previous_max = band["max_depth"] or previous_max
    assert econ["reward_bands"][-1]["max_depth"] is None
    for tool in econ["tools"]:
        assert tool["slot"] in ["active", "passive"]
        assert len(tool["ranks"]) == 3
        assert tool["ranks"][1]["upgrade_coins"] == max(100, math.ceil((tool["coins"] * 0.5) / 50) * 50)
        assert tool["ranks"][2]["upgrade_coins"] == max(200, tool["coins"])
    if initial_delivery:
        assert all(x["product_id"] is None for x in econ["coin_packs"])
        assert all(x["gamepass_id"] is None for x in econ["premium_cosmetics"])
    assert len(rooms["families"]) == 6
    unique(rooms["families"])
    props = [p for family in rooms["families"] for p in family["props"]]
    assert len(props) == 48
    unique(props)
    prop_ids = {p["id"] for p in props}
    families = {f["id"]: f for f in rooms["families"]}
    exit_ids = {e["id"] for e in rooms["exit_types"]}
    assert len(exit_ids) == 6
    assert len([p for p in props if p.get("deformation_profile") == "plush_soft"]) >= 3
    for family in rooms["families"]:
        assert {"S", "M", "L", "V"} <= set(family["formats"])  # XL/XV added on user request (decision 0017)
        for dimensions in family["formats"].values():
            assert len(dimensions) == 3 and all(n > 0 for n in dimensions)
        assert set(family["exits"]).issubset(exit_ids)
        assert set(family.get("souvenir_cosmetic_ids", [])).issubset({c["id"] for c in econ["cosmetics"]})
        for prop in family["props"]:
            assert len(prop["size_studs"]) == 3 and all(n > 0 for n in prop["size_studs"])
    for room in rooms["first_rooms"]:
        assert room["family"] in families
        assert room["format"] in families[room["family"]]["formats"]
        assert room["exit"] in families[room["family"]]["exits"]
        for guest in room.get("guest_props", []):
            assert guest["prop_id"] in prop_ids
    assert [r["depth"] for r in rooms["first_rooms"]] == list(range(1, 11))
    for band in rooms["difficulty_bands"]:
        assert band["warning_seconds"] >= 1.3
        assert band["wave_interval_seconds"] >= 7.5
        assert band["maximum_required_gap_ratio"] <= 0.85
    assert rooms["difficulty_bands"][-1]["depth_max"] is None
    tasks = backlog["tasks"]
    unique(tasks)
    seen = set()
    for task in tasks:
        assert set(task["depends_on"]).issubset(seen), task["id"]
        assert task["outputs"] and task["acceptance"]
        assert task["status"] in ["todo", "doing", "blocked", "done"]
        seen.add(task["id"])
    unique(assets["assets"])
    asset_ids = {a["id"] for a in assets["assets"]}
    assert prop_ids.issubset(asset_ids)
    assert {t["id"] for t in econ["tools"]}.issubset(asset_ids)
    for sku in econ["premium_cosmetics"]:
        assert set(sku["grants"]).issubset(asset_ids), sku["sku_id"]
    if initial_delivery:
        assert all(a["status"] == "planned" and a["roblox_asset_id"] is None for a in assets["assets"]), "Initial delivery must not claim fabricated assets"
    else:
        for asset in assets["assets"]:
            assert asset["status"] in ["planned", "designed", "modeled", "imported", "validated"]
            if asset["status"] in ["imported", "validated"]:
                assert (ROOT / asset["export_path"]).exists(), asset["id"]
                if asset["requires_external_import"]:
                    assert asset["roblox_asset_id"] is not None, asset["id"]
    assert all((ROOT / f"prompts/{name}").exists() for name in ["00_MISSION_IA.md", "01_CLAUDE_DESIGN_DIRECTION.md", "02_CLAUDE_DESIGN_PELUCHES.md", "03_CLAUDE_DESIGN_SALLES.md", "04_CLAUDE_DESIGN_OUTILS_UI.md", "05_FABRICATION_3D.md", "06_EXPORT_ET_RECETTE.md"])
    return {
        "status": "PASS",
        "scope": "Specification bundle, not implemented gameplay",
        "tools": len(econ["tools"]), "cosmetics": len(econ["cosmetics"]),
        "room_families": len(families), "room_props": len(props),
        "exit_types": len(exit_ids), "planned_assets": len(assets["assets"]),
        "tasks": len(tasks), "roblox_tests_executed": False,
    }


if __name__ == "__main__":
    print(json.dumps(validate(), ensure_ascii=False, indent=2))

