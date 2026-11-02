"""Reproduce design assumptions. This is not a Roblox gameplay test."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def load_economy():
    return json.loads((ROOT / "config/economy.json").read_text(encoding="utf-8"))


def band_for(economy, depth):
    for band in economy["reward_bands"]:
        if band["min_depth"] <= depth and (band["max_depth"] is None or depth <= band["max_depth"]):
            return band
    raise ValueError(f"No reward band for depth {depth}")


def rebirth_cost(economy, rank):
    rule = economy["rebirth"]
    return min(rule["base_cost"] + rule["increment"] * (rank - 1), rule["cost_cap"])


def simulate(economy, elapsed_seconds):
    intro = economy["simulation"]["intro_seconds"]
    time = intro
    completed = 0
    coins = sum(economy["tutorial"]["rewards"])
    permits = 0
    while True:
        band = band_for(economy, completed + 1)
        if time + band["simulation_seconds"] > elapsed_seconds:
            break
        time += band["simulation_seconds"]
        completed += 1
        coins += band["base_total"]
        permits += band["permits"]
    balance = coins
    owned = 0
    for tool in economy["tools"]:
        if tool["unlock"]["min_completed_rooms"] > completed or tool["coins"] > balance:
            break
        balance -= tool["coins"]
        owned += 1
    return {
        "elapsed_seconds": elapsed_seconds,
        "completed_rooms": completed,
        "coins_earned": coins,
        "permits_earned": permits,
        "tools_owned": owned,
        "coins_spent": coins - balance,
        "coin_balance": balance,
    }


def build_report(economy):
    simulations = []
    for expected in economy["simulation"]["checkpoints"]:
        actual = simulate(economy, expected["elapsed_seconds"])
        assert actual == expected, {"expected": expected, "actual": actual}
        simulations.append(actual)
    base = sum(tool["coins"] for tool in economy["tools"])
    all_ranks = base + sum(rank["upgrade_coins"] for tool in economy["tools"] for rank in tool["ranks"])
    assert base == 39250 and all_ranks == 98450
    permit_balance = 326
    new_rank = 0
    while permit_balance >= rebirth_cost(economy, new_rank + 1):
        new_rank += 1
        permit_balance -= rebirth_cost(economy, new_rank)
    assert (new_rank, permit_balance) == (4, 76)
    # Verify cumulative rounding for all ranks and every reward band.
    rounding_cases = 0
    for rank in range(0, 16):
        multiplier_bps = 10000 + min(rank * 400, 4000)
        for band in economy["reward_bands"]:
            base_claimed = paid = 0
            for reward in band["milestones"] + [band["exit_reward"]]:
                base_claimed += reward
                cumulative = base_claimed * multiplier_bps // 10000
                delta = cumulative - paid
                assert delta >= 0
                paid += delta
            assert paid == band["base_total"] * multiplier_bps // 10000
            rounding_cases += 1
    return {
        "status": "PASS",
        "scope": "Specification arithmetic only; not Roblox runtime or retention",
        "simulations": simulations,
        "catalog_base_coins": base,
        "catalog_all_ranks_coins": all_ranks,
        "batch_rebirth_example": {"initial_permits": 326, "ranks": new_rank, "remaining_permits": permit_balance},
        "rounding_cases_checked": rounding_cases,
        "game_tests_executed": False,
    }


if __name__ == "__main__":
    print(json.dumps(build_report(load_economy()), ensure_ascii=False, indent=2))

