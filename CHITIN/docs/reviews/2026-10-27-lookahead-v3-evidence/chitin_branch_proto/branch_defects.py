"""Count opponent-identity defects of the proposed switch in natural runs (review probe)."""

import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "chitin_B3", HERE / "b3" / "CHITIN" / "battle_evolution.py"
)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)
ATTACKS = ("ATTACK", "FLANK", "RAID")
ctx = {}
calls = []
orig_fl, orig_ps = m._forecast_lifetime, m.predictive_scores


def fl(
    a,
    enemy,
    action,
    food_path,
    distance,
    speed,
    contact,
    reaction,
    own_rate,
    enemy_rate,
    ore_available=0.0,
    switch=None,
):
    result = orig_fl(
        a,
        enemy,
        action,
        food_path,
        distance,
        speed,
        contact,
        reaction,
        own_rate,
        enemy_rate,
        ore_available,
        switch,
    )
    if switch is not None:
        s = ctx["sensed"]
        nearest = s.get("enemy")
        raid = s.get("raid_target") or nearest
        cont = switch[1]
        cont_enemy = raid if cont == "RAID" else nearest
        phantom = (
            enemy is not None and contact > 180 and cont in ATTACKS and switch[4] <= 168
        )
        mixed = enemy is not None and cont_enemy is not None and cont_enemy is not enemy
        p = result["points"][180]
        calls.append(
            {
                "prefix": action,
                "cont": cont,
                "phantom": phantom,
                "mixed": mixed,
                "received": p["received"],
                "dealt": p["dealt"],
                "uid": a.uid,
                "tick": ctx["tick"],
            }
        )
    return result


def ps(world, a, sensed, utility):
    ctx.update(sensed=sensed, tick=world.tick)
    start = len(calls)
    scores, reason, forecast = orig_ps(world, a, sensed, utility)
    for row in calls[start:]:
        row["won"] = forecast["continuations"].get(row["prefix"]) == row["cont"]
    chosen = max(world.eligible_indices(a, sensed), key=lambda i: scores[i])
    for row in calls[start:]:
        row["prefix_is_argmax"] = m.ACTIONS[chosen] == row["prefix"]
    return scores, reason, forecast


m._forecast_lifetime, m.predictive_scores = fl, ps
summary = {}
for seed in (101, 202, 303):
    calls.clear()
    w = m.BattleWorld(seed=seed, max_agents=60)
    for _ in range(3000):
        w.step()
    c = Counter()
    for r in calls:
        c["branches"] += 1
        c["won"] += r["won"]
        for flag in ("phantom", "mixed"):
            if r[flag]:
                c[flag] += 1
                c[flag + "_won"] += r["won"]
                c[flag + "_won_and_prefix_top"] += r["won"] and r["prefix_is_argmax"]
                c[flag + "_received_zero"] += r["received"] == 0
    summary[seed] = dict(c)
    summary[f"{seed}_examples"] = [r for r in calls if r["phantom"]][:2] + [
        r for r in calls if r["mixed"]
    ][:2]
print(json.dumps(summary, indent=1, default=str))
