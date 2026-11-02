# MovementLab (T06) — NOT_RUN in this environment

Build `rojo build studio-tests.project.json -o build/StudioTests.rbxlx`, open it in Roblox Studio,
set `Workspace` attribute `FU_TEST_SUITE = "movement"`, press Play (server). Copy the line
`STUDIO_RESULT_JSON:` from the output into `reports/movement_calibration.json` under `measured`.

Then:
1. Feed the measured `{rise, reach}` table to `JumpModel.setMeasuredTable` (shared) and rerun
   `python tools/game_checks.py unit --suite generation-initial` and `generation-full`.
2. Manual mobile checks on real devices (list the device models): jump button reach, camera drag,
   HUD readable at 16:9 and compact, tool button never covering the jump button (≥ 48 px targets).
3. Check that coyote time (0.12 s) and jump buffer (0.12 s) never trigger a jump without input.

Pass criteria: required hops of generated rooms ≤ measured reach × band ratio; no automatic jump.
