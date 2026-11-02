# ProfileLab — NOT_RUN in this environment

Suite id: `persistence` (`python tools/game_checks.py studio --suite persistence` reports BLOCKED here: no Roblox Studio).

Procedure and pass criteria:

T11/T15: use a SEPARATE test experience with API access. Check session lock across two Studio servers (Team Test), failed UpdateAsync (unplug network) shows 'Sauvegarde impossible' and never 'Sauvegardé', purchase debit+ownership in one write, KO keeps coins/permits/tools, rebirth in sas only with preview token.

Record PASS / FAIL / NOT_RUN per item with date, place version and device names in the report named by the backlog task.
