# WaveLab — NOT_RUN in this environment

Suite id: `waves` (`python tools/game_checks.py studio --suite waves` reports BLOCKED here: no Roblox Studio).

Procedure and pass criteria:

T08: waves keep arriving while the player stays; coral warning appears >= warning_seconds before impact; dynamic bodies <= 40 (Developer Console: count models with unanchored Collider); occupied support never removed; ExitClearance sweep recycles intruders; seed of any failure is noted.

Record PASS / FAIL / NOT_RUN per item with date, place version and device names in the report named by the backlog task.
