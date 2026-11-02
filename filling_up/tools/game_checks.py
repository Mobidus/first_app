"""Reproducible checks for FILLING UP (T04 contract, docs/06 §9).

    python tools/game_checks.py config
    python tools/game_checks.py build
    python tools/game_checks.py unit --suite <name|all>
    python tools/game_checks.py studio --suite <name>
    python tools/game_checks.py soak --simulated-seconds 18000
    python tools/game_checks.py soak --real-hours 5

Each command writes reports/checks/<command>[_<suite>].json with: status (PASS | FAIL | BLOCKED),
date, tool versions, executed checks, failures and checks NOT_RUN. A missing component yields
BLOCKED, never an empty success. Exit code: 0 PASS, 1 FAIL, 2 BLOCKED.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / ".toolchain" / "bin"
REPORTS = ROOT / "reports" / "checks"

STUDIO_SUITES = {
    "movement": "tests/studio/MovementLab",
    "reception": "tests/studio/ReceptionRoom",
    "waves": "tests/studio/WaveLab",
    "plush": "tests/studio/PlushLab",
    "burial": "tests/studio/BurialFixtures",
    "transitions": "tests/studio/TransitionLab",
    "persistence": "tests/studio/ProfileLab",
    "onboarding": "tests/studio/FirstSessionLab",
    "coin-shop": "tests/studio/FirstSessionLab",
    "tools": "tests/studio/ToolLab",
    "rebirth": "tests/studio/ProfileLab",
    "rooms-initial": "tests/studio/ReceptionRoom",
    "rooms-full": "tests/studio/ReceptionRoom",
    "reconnect": "tests/studio/ResumeLab",
    "ui": "tests/studio/EndToEndLab",
    "purchases": "tests/studio/PurchaseLab",
    "end-to-end": "tests/studio/EndToEndLab",
}


def tool(name: str) -> str | None:
    p = BIN / name
    if p.exists():
        return str(p)
    return shutil.which(name)


def version(cmd: list[str]) -> str | None:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return (out.stdout or out.stderr).strip().splitlines()[0]
    except Exception:  # noqa: BLE001
        return None


def versions() -> dict:
    v = {"python": sys.version.split()[0]}
    for name in ("rojo", "lune", "stylua", "selene"):
        t = tool(name)
        v[name] = version([t, "--version"]) if t else None
    return v


def run(cmd: list[str], timeout: int = 1800) -> tuple[int, str]:
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def result_json(output: str) -> dict | None:
    for line in reversed(output.splitlines()):
        if line.startswith("RESULT_JSON:"):
            return json.loads(line[len("RESULT_JSON:"):])
    return None


def as_list(v) -> list:
    """Lune's serde encodes an empty Luau table as {}: normalise to a list."""
    if isinstance(v, list):
        return v
    return [] if not v else list(v.values()) if isinstance(v, dict) else [v]


def write(name: str, report: dict) -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    for key in ("failures", "not_run", "executed"):
        if key in report:
            report[key] = as_list(report[key])
    report.setdefault("date_utc", dt.datetime.now(dt.timezone.utc).isoformat())
    report.setdefault("versions", versions())
    path = REPORTS / f"{name}.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    status = report["status"]
    print(f"{status}  {name}  -> {path.relative_to(ROOT)}")
    for f in report.get("failures", [])[:20]:
        print("   FAIL:", f)
    for n in report.get("not_run", [])[:20]:
        print("   NOT_RUN:", n)
    return {"PASS": 0, "FAIL": 1}.get(status, 2)


def blocked(name: str, reason: str, not_run: list[str]) -> int:
    return write(name, {"status": "BLOCKED", "reason": reason, "executed": [], "failures": [], "not_run": not_run})


def cmd_config(_args) -> int:
    executed, failures = [], []
    for label, cmd in (
        ("compile_config --check (JSON -> GeneratedConfig up to date + invariants)", [sys.executable, "-I", "tools/compile_config.py", "--check"]),
        ("scripts/validate_pack.py (specification bundle)", [sys.executable, "-I", "scripts/validate_pack.py"]),
        ("scripts/simulate_economy.py (specification arithmetic)", [sys.executable, "-I", "scripts/simulate_economy.py"]),
    ):
        code, out = run(cmd)
        executed.append({"check": label, "exit_code": code, "output_tail": out.strip().splitlines()[-5:]})
        if code != 0:
            failures.append(label)
    lune = tool("lune")
    if lune:
        code, out = run([lune, "run", "tests/run.luau", "config"])
        r = result_json(out) or {}
        executed.append({"check": "unit suite 'config' (generated modules vs JSON)", "exit_code": code, "passed": r.get("passed"), "failed": r.get("failed")})
        if code != 0:
            failures.append("unit config suite")
    return write("config", {"status": "FAIL" if failures else "PASS", "executed": executed, "failures": failures,
                            "not_run": [] if lune else ["unit config suite (lune missing)"],
                            "scope": "Configuration and specification consistency; not gameplay."})


def cmd_build(_args) -> int:
    rojo, lune, stylua, selene = tool("rojo"), tool("lune"), tool("stylua"), tool("selene")
    if not rojo:
        return blocked("build", "rojo not installed (run tools/bootstrap_toolchain.sh)", ["rojo build", "place verification"])
    executed, failures, not_run = [], [], []
    code, out = run([sys.executable, "-I", "tools/compile_config.py"])
    executed.append({"check": "compile_config", "exit_code": code})
    if code != 0:
        failures.append("compile_config")
    (ROOT / "build").mkdir(exist_ok=True)
    code, out = run([rojo, "build", "default.project.json", "-o", "build/FillingUp.rbxlx"])
    executed.append({"check": "rojo build -> build/FillingUp.rbxlx", "exit_code": code, "output_tail": out.strip().splitlines()[-3:]})
    if code != 0:
        failures.append("rojo build")
    if lune and code == 0:
        code, out = run([lune, "run", "tools/verify_build.luau", "build/FillingUp.rbxlx"])
        r = result_json(out) or {}
        executed.append({"check": "verify_build (place tree + every script compiles with Luau)", "exit_code": code,
                         "scripts": r.get("scripts"), "modules": r.get("modules"), "compiled": r.get("compiled"),
                         "errors": r.get("errors")})
        if code != 0:
            failures.append("verify_build")
    else:
        not_run.append("verify_build (lune missing or build failed)")
    if stylua:
        code, out = run([stylua, "--check", "src", "tests", "tools", "assets/source/generators"])
        executed.append({"check": "stylua --check", "exit_code": code})
        if code != 0:
            failures.append("stylua formatting")
    else:
        not_run.append("stylua")
    if selene:
        code, out = run([selene, "src"])
        executed.append({"check": "selene src (std roblox_min: Roblox API dump unavailable offline)", "exit_code": code,
                         "output_tail": out.strip().splitlines()[-4:]})
        if code != 0:
            failures.append("selene")
    else:
        not_run.append("selene")
    not_run.append("luau-analyze --strict type checking (binary not available in this environment)")
    not_run.append("Opening the place in Roblox Studio (Studio not available)")
    return write("build", {"status": "FAIL" if failures else "PASS", "executed": executed, "failures": failures, "not_run": not_run,
                           "artifact": "build/FillingUp.rbxlx",
                           "scope": "A valid local place file is produced; this is not a gameplay test (Rojo != Studio)."})


def cmd_unit(args) -> int:
    lune = tool("lune")
    name = f"unit_{args.suite}"
    if not lune:
        return blocked(name, "lune not installed", [f"unit suite {args.suite}"])
    code, out = run([lune, "run", "tests/run.luau", args.suite], timeout=3600)
    r = result_json(out)
    if r is None:
        return write(name, {"status": "FAIL", "executed": [], "failures": ["runner produced no result"], "not_run": [],
                            "output_tail": out.strip().splitlines()[-30:]})
    if r.get("status") == "BLOCKED":
        return blocked(name, r.get("error", "unknown"), [args.suite])
    cases = r.get("cases") or []
    failures = [c["name"] + " :: " + c.get("error", "").splitlines()[0] for c in cases if c.get("status") == "FAIL"]
    return write(name, {"status": "PASS" if code == 0 and not failures else "FAIL", "suite": args.suite, "passed": r["passed"],
                        "failed": r["failed"], "seconds": r["seconds"], "executed": [c["name"] for c in cases],
                        "failures": failures, "not_run": [],
                        "scope": "Pure Luau logic under Lune (no Roblox engine services)."})


def cmd_studio(args) -> int:
    scene = STUDIO_SUITES.get(args.suite)
    name = f"studio_{args.suite}"
    if scene is None:
        return write(name, {"status": "FAIL", "failures": [f"unknown studio suite {args.suite}"], "executed": [], "not_run": []})
    exists = (ROOT / scene).exists()
    return blocked(name, "Roblox Studio / a Studio test bridge is not available in this environment (Linux container). "
                         "Run the scene in Studio: see " + scene + "/README.md",
                   [f"{scene} ({'scene present' if exists else 'scene MISSING'})"])


def cmd_soak(args) -> int:
    if args.real_hours is not None:
        return blocked("soak_real", "A real 5 h Roblox client+server session requires Roblox Studio or a live test place with a test pilot; "
                                    "not available here. Simulation is NOT a substitute.",
                       [f"real Roblox session of {args.real_hours} h with periodic memory/instances/connections/frame-time samples"])
    lune = tool("lune")
    if not lune:
        return blocked("soak_simulated", "lune not installed", ["logic soak"])
    seconds = args.simulated_seconds or 18000
    code, out = run([lune, "run", "tools/soak_sim.luau", str(seconds)], timeout=7200)
    r = result_json(out)
    if r is None:
        return write("soak_simulated", {"status": "FAIL", "failures": ["soak produced no result"], "executed": [], "not_run": [],
                                        "output_tail": out.strip().splitlines()[-30:]})
    (ROOT / "reports" / "soak_simulated.json").write_text(json.dumps(r, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return write("soak_simulated", {"status": r["status"], "executed": r.get("executed", []), "failures": r.get("failures", []),
                                    "not_run": ["engine physics, network, camera and frame time (simulation only)"],
                                    "summary": r.get("summary")})


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("config")
    sub.add_parser("build")
    u = sub.add_parser("unit")
    u.add_argument("--suite", required=True)
    s = sub.add_parser("studio")
    s.add_argument("--suite", required=True)
    k = sub.add_parser("soak")
    g = k.add_mutually_exclusive_group(required=True)
    g.add_argument("--simulated-seconds", type=int)
    g.add_argument("--real-hours", type=float)
    args = ap.parse_args()
    return {"config": cmd_config, "build": cmd_build, "unit": cmd_unit, "studio": cmd_studio, "soak": cmd_soak}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
