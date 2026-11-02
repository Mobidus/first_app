# PurchaseLab — NOT_RUN in this environment

Suite id: `purchases` (`python tools/game_checks.py studio --suite purchases` reports BLOCKED here: no Roblox Studio).

Procedure and pass criteria:

T20 (BLOCKED until real product ids exist in an authorised test experience): cancel, deferred receipt, double receipt, DataStore unavailable during ProcessReceipt, purchase kept after rebirth. Never fake a purchase success: product_id null keeps every Robux button disabled.

Record PASS / FAIL / NOT_RUN per item with date, place version and device names in the report named by the backlog task.
