import importlib.util, math, sys, random
from pathlib import Path

SOURCE = Path(r"C:\Users\rmanov\algorithmic-arts\CHITIN\battle_evolution.py")
spec = importlib.util.spec_from_file_location("chitin_inv", SOURCE)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)

# 1) ulp perturbation: speed' = distance / sum(step/speed) vs speed, for non-crossing paths
rng = random.Random(7)
diff = 0
total = 0
for _ in range(100000):
    s = rng.uniform(0.03, 0.45)
    d = rng.uniform(0.2, 118.0)
    n = max(1, min(40, math.ceil(d)))
    step = d / n
    t = 0.0
    for i in range(n):
        t += step / s
    total += 1
    diff += d / t != s
print(
    f"ulp check: speed changed bitwise in {diff}/{total} non-crossing candidates ({100 * diff / total:.1f}%)"
)

# 2) seed 42 / 520 steps (proposal's byte-identity check): are ice/river stats exercised?
w = m.BattleWorld(seed=42)
for _ in range(520):
    w.step()
print(
    "seed42/520: ice_slow_ticks",
    w.stats["ice_slow_ticks"],
    "river_crossing_ticks",
    w.stats["river_crossing_ticks"],
    "mountain_detours",
    w.stats["mountain_detours"],
    "episode",
    w.episode,
    "hazards now",
    [(h["kind"], h["age"], h["ttl"]) for h in w.hazards],
)
keys = list(w.stats)
print(
    "stats key order index: river",
    keys.index("river_crossing_ticks") if "river_crossing_ticks" in keys else None,
    "ice",
    keys.index("ice_slow_ticks") if "ice_slow_ticks" in keys else None,
)
