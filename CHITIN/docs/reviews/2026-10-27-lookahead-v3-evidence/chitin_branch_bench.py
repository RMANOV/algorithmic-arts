"""Read-only micro-benchmark: cost of predictive_scores per call and share of step time (baseline build)."""

import importlib.util
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
SOURCE = Path(r"C:\Users\rmanov\algorithmic-arts\CHITIN\battle_evolution.py")
spec = importlib.util.spec_from_file_location("chitin_bench", SOURCE)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)

calls = 0
total = 0.0
eligible_sum = 0
lifetime_calls = 0
lifetime_ticks = 0
orig_scores = m.predictive_scores
orig_lifetime = m._forecast_lifetime


def timed_scores(world, a, sensed, utility):
    global calls, total, eligible_sum
    t0 = time.perf_counter()
    out = orig_scores(world, a, sensed, utility)
    total += time.perf_counter() - t0
    calls += 1
    eligible_sum += len(out[2]["candidates"])
    return out


def counted_lifetime(*args, **kwargs):
    global lifetime_calls, lifetime_ticks
    out = orig_lifetime(*args, **kwargs)
    lifetime_calls += 1
    # ticks actually simulated: last long horizon reached or death
    lifetime_ticks += 181
    return out


m.predictive_scores = timed_scores
m._forecast_lifetime = counted_lifetime

for seed in (101, 202):
    calls = 0
    total = 0.0
    eligible_sum = 0
    lifetime_calls = 0
    w = m.BattleWorld(seed=seed, max_agents=60, episode_ticks=1500)
    steps = 3000
    t0 = time.perf_counter()
    for _ in range(steps):
        w.step()
    wall = time.perf_counter() - t0
    la_decisions = sum(f.decisions for f in w.factions if f.method == "Lookahead")
    print(
        f"seed {seed}: {steps} ticks in {wall:.2f}s = {steps / wall:.0f} ticks/s | predictive_scores calls {calls} "
        f"({calls / steps:.2f}/tick), total {total * 1000:.0f} ms = {100 * total / wall:.1f}% of wall, "
        f"{1000 * total / max(1, calls):.3f} ms/call, mean candidates {eligible_sum / max(1, calls):.2f}, "
        f"lifetime calls {lifetime_calls}, population {len(w.agents)}, ledger_error {w.last_ledger_error}"
    )
