"""Step 0b probe (read-only): can an action-conditioned transition table (P(next|current), 8x8 per faction pool)
beat persistence out of sample? Fit on seed 101, test on seed 202 (and the reverse). Also the empirical 60-tick
combat-capable share of the nearest enemy split by its current class (the base rate behind reaction=5)."""

import importlib.util
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

SOURCE = Path(r"C:\Users\rmanov\algorithmic-arts\CHITIN\battle_evolution.py")
spec = importlib.util.spec_from_file_location("chitin_probe_b", SOURCE)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)
A = m.ACTIONS
CHASE = {"ATTACK", "FLANK", "RAID"}
SHIELD = {"GUARD", "ESCORT"}
COMBAT = CHASE | SHIELD


def collect(seed, ticks=6000):
    w = m.BattleWorld(seed=seed, max_agents=60, episode_ticks=1500, learning=True)
    last_seen = {}
    pairs = []
    pending = []
    action_log = defaultdict(dict)
    orig = m.BattleWorld._choose

    def choose(self, a, s):
        for e in s["enemies"]:
            key = (a.faction, e.uid)
            prev = last_seen.get(key)
            if e.decision_id and (prev is None or prev[0] != e.decision_id):
                if prev is not None:
                    pairs.append((prev[1], e.action, self.tick - prev[2]))
                last_seen[key] = (e.decision_id, e.action, self.tick)
        enemy = s.get("enemy")
        if enemy is not None:
            pending.append((self.tick, enemy.uid, enemy.action))
        return orig(self, a, s)

    m.BattleWorld._choose = choose
    try:
        for _ in range(ticks):
            w.step()
            for a in w.agents:
                action_log[a.uid][w.tick] = a.action
    finally:
        m.BattleWorld._choose = orig
    windows = []
    for t, uid, action in pending:
        log = action_log.get(uid, {})
        win = [log[k] for k in range(t + 1, t + 61) if k in log]
        if len(win) >= 30:
            windows.append((action, sum(x in COMBAT for x in win) / len(win)))
    return pairs, windows


def fit(pairs):
    table = defaultdict(Counter)
    for prev, nxt, _ in pairs:
        table[prev][nxt] += 1
    return {prev: c.most_common(1)[0][0] for prev, c in table.items()}, table


def fit_share(windows):
    by = defaultdict(list)
    for action, share in windows:
        by[action].append(share)
    return {k: st.mean(v) for k, v in by.items()}


data = {seed: collect(seed) for seed in (101, 202)}
for seed in (101, 202):
    print(
        f"seed {seed}: observed transitions {len(data[seed][0])}, 60-tick windows {len(data[seed][1])}, "
        f"median gap between observations {st.median(g for _, _, g in data[seed][0])} ticks"
    )

for train, test in ((101, 202), (202, 101)):
    model, table = fit(data[train][0])
    pairs = data[test][0]
    n = len(pairs)
    persist = sum(p == q for p, q, _ in pairs)
    cond = sum(model.get(p, p) == q for p, q, _ in pairs)
    persist_c = sum((p in COMBAT) == (q in COMBAT) for p, q, _ in pairs)
    cond_c = sum((model.get(p, p) in COMBAT) == (q in COMBAT) for p, q, _ in pairs)
    print(
        f"\nfit {train} -> test {test} (n={n}): next action: persistence {100 * persist / n:.1f}% | conditional argmax {100 * cond / n:.1f}%"
        f" | combat-class: persistence {100 * persist_c / n:.1f}% | conditional {100 * cond_c / n:.1f}%"
    )
    print(
        "  conditional argmax by current action (train): "
        + ", ".join(f"{p}->{model[p]}" for p in A if p in model)
    )
    by_prev = defaultdict(lambda: [0, 0, 0])
    for p, q, _ in pairs:
        row = by_prev[p]
        row[0] += 1
        row[1] += p == q
        row[2] += model.get(p, p) == q
    print(
        "  per current action (test): "
        + ", ".join(
            f"{p}: n={r[0]} persist {100 * r[1] / r[0]:.0f}% cond {100 * r[2] / r[0]:.0f}%"
            for p, r in sorted(by_prev.items(), key=lambda kv: -kv[1][0])
        )
    )
    share_model = fit_share(data[train][1])
    wins = data[test][1]
    mae_persist = st.mean(abs(s - float(a in COMBAT)) for a, s in wins)
    mae_cond = st.mean(abs(s - share_model.get(a, float(a in COMBAT))) for a, s in wins)
    print(
        f"  60-tick combat share (test, n={len(wins)}): MAE persistence {mae_persist:.3f} | conditional mean-by-current-action {mae_cond:.3f}"
    )
    print(
        "  empirical 60-tick combat share by current action (train): "
        + ", ".join(f"{a}={v:.2f}" for a, v in sorted(share_model.items()))
    )
