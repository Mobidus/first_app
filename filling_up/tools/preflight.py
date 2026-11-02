"""T00 preflight: detect the toolchain that is REALLY present. Never invents a version.

Usage: python tools/preflight.py  -> writes reports/preflight.json
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLCHAIN_BIN = ROOT / ".toolchain" / "bin"
VENV_PY = ROOT / ".venv" / "bin" / "python"


def find(name: str) -> str | None:
    local = TOOLCHAIN_BIN / name
    if local.exists():
        return str(local)
    return shutil.which(name)


def version(cmd: list[str]) -> str | None:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except Exception as exc:  # noqa: BLE001 - report, do not hide
        return f"ERROR: {exc}"
    text = (out.stdout or out.stderr).strip().splitlines()
    return text[-1].strip() if text else None


def tool(name: str, args: list[str]) -> dict:
    path = find(name)
    return {"present": path is not None, "path": path, "version": version([path, *args]) if path else None}


def bpy_info() -> dict:
    if not VENV_PY.exists():
        return {"present": False, "reason": "project venv missing"}
    v = version([str(VENV_PY), "-I", "-c", "import bpy;print(bpy.app.version_string)"])
    ok = v is not None and not v.startswith("ERROR") and "Error" not in v
    return {"present": ok, "path": str(VENV_PY), "module": "bpy (PyPI wheel, headless Blender)", "version": v if ok else None,
            "error": None if ok else v}


def main() -> int:
    report = {
        "generated_at_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "system": {"os": platform.platform(), "python": sys.version.split()[0], "machine": platform.machine(),
                   "cpu_count": os.cpu_count(), "container": "Claude Code cloud session (ephemeral Linux container)"},
        "executables": {
            "rojo": tool("rojo", ["--version"]),
            "lune": tool("lune", ["--version"]),
            "luau": tool("luau", ["--version"]),
            "luau-analyze": tool("luau-analyze", ["--version"]),
            "selene": tool("selene", ["--version"]),
            "stylua": tool("stylua", ["--version"]),
            "git": tool("git", ["--version"]),
            "cargo": tool("cargo", ["--version"]),
            "node": tool("node", ["--version"]),
            "blender_cli": tool("blender", ["--version"]),
        },
        "blender_python_module": bpy_info(),
        "roblox_studio": {
            "present": False,
            "reason": "Linux cloud container: Roblox Studio is Windows/macOS only and not installed; no Studio MCP/bridge detected.",
            "consequence": "All tests/studio suites and engine physics, mobile, purchase and real 5h soak criteria are NOT_RUN/blocked.",
        },
        "roblox_open_cloud": {"present": False, "reason": "No API key or authorised account provided; none searched for (AGENTS.md)."},
        "roblox_account_rights": {"publish": False, "import_assets": False, "create_products": False,
                                  "reason": "No authority granted in this session."},
        "claude_design": {
            "present": True,
            "route": "Artifact type 'Design' (Claude Design now lives in Claude); verified with Artifact quickstart(intent=design).",
            "design_sync": "DesignSync tool exists but is reserved to design-system syncing (/design-sync); not used to create boards.",
            "limits": "Exports are HTML/SVG/PNG references, never Roblox meshes.",
        },
        "network": {
            "github_release_downloads": "reachable, but executing downloaded prebuilt binaries was refused by the session permission policy",
            "github_api": "403 (blocked by proxy)",
            "crates_io": "reachable -> Rust tools compiled from source with cargo install --locked",
            "pypi": "reachable",
        },
        "repository": {"present": True, "path": str(ROOT.parent), "subfolder": "filling_up",
                       "branch_policy": "commit on designated feature branch; no publish, no PR unless asked"},
        "permissions": {
            "write_project_dir": True,
            "install_packages_via_registries": True,
            "run_downloaded_binaries": False,
            "spend_robux_or_publish": False,
        },
    }
    out = ROOT / "reports" / "preflight.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: (v["present"] if isinstance(v, dict) and "present" in v else "...") for k, v in report["executables"].items()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
