"""Read-only diagnostic: how often the forecast correction changes the choice vs plain utility, and how often a doomed long tail vetoes the utility argmax."""

import importlib.util
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
SOURCE = Path(r"C:\Users\rmanov\algorithmic-arts\CHITIN\battle_evolution.py")
spec = importlib.util.spec_from_file_location("chitin_flips", SOURCE)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)

orig = m.predictive_scores
c = Counter()


def probe(world, a, sensed, utility):
    scores, reason, forecast = orig(world, a, sensed, utility)
    eligible = world.eligible_indices(a, sensed)
    c["calls"] += 1
    c["eligible"] += len(eligible)
    if len(eligible) < 2:
        return scores, reason, forecast
    ua = max(eligible, key=lambda i: (utility[i], -i))
    sa = max(eligible, key=lambda i: (scores[i], -i))
    c["two_plus"] += 1
    if ua != sa:
        c["flip"] += 1
        c["flip_to_" + m.ACTIONS[sa]] += 1
        c["flip_from_" + m.ACTIONS[ua]] += 1
    cand = forecast["candidates"]
    # doomed tail: utility argmax candidate healthy at 30 but <15 health or ~0 energy at 180
    pts = {p["ticks"]: p for p in cand[m.ACTIONS[ua]]}
    if pts[30]["health"] >= 30 and (pts[180]["health"] < 15 or pts[180]["energy"] < 1):
        c["utility_argmax_doomed_tail"] += 1
        if ua != sa:
            c["doomed_and_flipped"] += 1
    # rank of utility argmax under scores (beam coverage check): is it in the top-3 by scores?
    order = sorted(eligible, key=lambda i: (-scores[i], i))
    if ua in order[:3]:
        c["utility_argmax_in_top3_scores"] += 1
    if 1 in eligible:
        c["build_eligible"] += 1
        if sa == 1:
            c["build_chosen_when_eligible"] += 1
        if ua == 1:
            c["build_utility_argmax_when_eligible"] += 1
    return scores, reason, forecast


m.predictive_scores = probe
for seed in (101, 202, 303):
    w = m.BattleWorld(seed=seed, max_agents=60, episode_ticks=1500)
    for _ in range(4000):
        w.step()
print({k: v for k, v in sorted(c.items())})
print(
    f"flip rate among decisions with >=2 eligible: {100 * c['flip'] / max(1, c['two_plus']):.1f}%  | mean eligible {c['eligible'] / c['calls']:.2f}"
)
print(
    f"utility argmax within top-3 by scores: {100 * c['utility_argmax_in_top3_scores'] / max(1, c['two_plus']):.1f}%"
)
print(
    f"BUILD eligible {c['build_eligible']}, chosen {c['build_chosen_when_eligible']}, utility-argmax {c['build_utility_argmax_when_eligible']}"
)
