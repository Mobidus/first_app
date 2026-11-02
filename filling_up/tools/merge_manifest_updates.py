"""Merge proposed asset status updates (reports/T02, reports/T03) into assets/manifest.json.

Rules (docs/02, prompts/06):
  * statuses only move forward: planned < designed < modeled < imported < validated;
  * a file-based status requires that every cited path exists (checked here, not assumed);
  * roblox_asset_id stays null unless an authorised real import returned an id (never here);
  * design references are kept as `design_reference_paths`, model sources as `source_path`.
Writes reports/T02/manifest_merge_log.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORDER = ["planned", "designed", "modeled", "imported", "validated"]


def load(p: str):
    return json.loads((ROOT / p).read_text(encoding="utf-8"))


def main() -> int:
    manifest = load("assets/manifest.json")
    by_id = {a["id"]: a for a in manifest["assets"]}
    log = {"applied": [], "rejected": []}
    sources = [("T02", "reports/T02/manifest_updates.json"), ("T03", "reports/T03/manifest_updates.json")]
    for task, path in sources:
        if not (ROOT / path).exists():
            continue
        for u in load(path)["updates"]:
            a = by_id.get(u["id"])
            if a is None:
                log["rejected"].append({"task": task, "id": u["id"], "reason": "unknown asset id"})
                continue
            new = u["status"]
            if new == "planned":
                log["applied"].append({"task": task, "id": u["id"], "from": a["status"], "to": a["status"], "note": "kept planned"})
                continue
            # designed (reference) needs its reference evidence; modeled needs its editable source.
            # Engine exports (.rbxm) cannot exist before a Studio import and are not required here.
            cited = list(u.get("validation_evidence", []))
            if task == "T03" and new == "modeled":
                cited.append(u.get("source_path"))
                cited += [p for p in [u.get("export_path"), *u.get("additional_exports", [])] if p and not str(p).endswith(".rbxm")]
            cited = [str(p).split("#")[0] for p in cited if p]
            missing = [p for p in cited if not (ROOT / p).exists()]
            if missing:
                log["rejected"].append({"task": task, "id": u["id"], "reason": "missing files", "missing": missing})
                continue
            if u.get("roblox_asset_id") is not None:
                log["rejected"].append({"task": task, "id": u["id"], "reason": "roblox_asset_id must stay null without a real import"})
                continue
            if new in ("imported", "validated"):
                log["rejected"].append({"task": task, "id": u["id"], "reason": f"status {new} impossible without Studio import"})
                continue
            old = a["status"]
            if ORDER.index(new) > ORDER.index(old):
                a["status"] = new
            if task == "T02":
                refs = a.setdefault("design_reference_paths", [])
                for p in [u.get("source_path"), u.get("export_path")]:
                    if p and p not in refs:
                        refs.append(p)
                if a.get("category") in ("tool_icon", "ui_icon", "icon") and u.get("export_path"):
                    a["export_path"] = u["export_path"]
                    a["source_path"] = u.get("source_path", a["source_path"])
            else:
                if u.get("source_path"):
                    a["source_path"] = u["source_path"]
                if u.get("export_path") and (ROOT / u["export_path"]).exists():
                    a["export_path"] = u["export_path"]
                elif u.get("export_path"):
                    a["export_pending"] = "engine export requires an authorised Studio import"
                if u.get("additional_exports"):
                    a["additional_exports"] = u["additional_exports"]
            ev = a.setdefault("validation_evidence", [])
            for e in u.get("validation_evidence", []):
                if e not in ev:
                    ev.append(e)
            log["applied"].append({"task": task, "id": u["id"], "from": old, "to": a["status"]})
    manifest["notice"] = ("Statuses merged from reports/T02 and reports/T03 (tools/merge_manifest_updates.py). "
                          "No Roblox import performed: every roblox_asset_id is null.")
    counts: dict[str, int] = {}
    for a in manifest["assets"]:
        counts[a["status"]] = counts.get(a["status"], 0) + 1
        assert a["roblox_asset_id"] is None
    manifest["status_counts"] = counts
    (ROOT / "assets/manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    log["status_counts"] = counts
    (ROOT / "reports/T02/manifest_merge_log.json").write_text(json.dumps(log, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"applied": len(log["applied"]), "rejected": log["rejected"], "counts": counts}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
