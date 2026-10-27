"""Value/risk lens, counterfactual only: how much decision authority would candidate B take from Lookahead?

Wraps BattleWorld._lookahead read-only (no RNG, no state writes), computes the B bias on a COPY of the
final scores and compares argmax over the post-planning eligible set (same set as _choose line 478).
Sanity: the instrumented world's end snapshot must equal the stored cmp_seed*.json summary.
"""

import importlib.util
import json
import statistics as st
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
SRC = Path(r"C:\Users\rmanov\algorithmic-arts\CHITIN\battle_evolution.py")
CMP = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("be_vr", SRC)
be = importlib.util.module_from_spec(spec)
sys.modules["be_vr"] = be
spec.loader.exec_module(be)
A = be.ACTIONS
ATT = ("ATTACK", "FLANK", "RAID")
rec = Counter()
margins = []
corr = []
flips_to = Counter()
pred_c = Counter()
contra = Counter()
orig = be.BattleWorld._lookahead


def top(v, elig):
    best = max(v[i] for i in elig)
    tied = [i for i in elig if abs(v[i] - best) <= 1e-10]
    return tied


def wrapped(self, a, s, utility):
    u = list(utility)
    scores, reason = orig(self, a, s, utility)
    elig = self.eligible_indices(a, s)
    if not elig:
        return scores, reason
    rec["la_decisions"] += 1
    f = self.factions[a.faction]
    observed = sum(f.opponent) - 8
    conc = max(f.opponent) / sum(f.opponent)
    b = list(scores)
    tu, ts = top(u, elig), top(scores, elig)
    if len(tu) == 1 and len(ts) == 1 and tu != ts:
        rec["planner_changes_utility_choice"] += 1
    corr.extend(abs(scores[i] - u[i]) for i in elig)
    if len(elig) > 1:
        srt = sorted((scores[i] for i in elig), reverse=True)
        margins.append(srt[0] - srt[1])
    if observed >= 16 and conc > 0.25 and s["enemy"]:
        rec["gate_open"] += 1
        pred = max(range(8), key=lambda i: f.opponent[i])
        pred_c[A[pred]] += 1
        if pred in (0, 1):
            b[2] += 0.65
            b[6] += 0.8
        elif pred == 2:
            b[4] += 0.9
            b[5] += 0.5
        elif pred == 3:
            b[6] += 0.7
        elif pred in (4, 7):
            b[5] += 0.9
        cur = s["enemy"].action
        if pred == 2 and cur not in ATT:
            contra["pred ATTACK, nearest enemy now not attacking"] += 1
        if pred == 2:
            contra["pred ATTACK total"] += 1
        if pred == 3 and cur != "RETREAT":
            contra["pred RETREAT, nearest enemy now not retreating"] += 1
        if pred == 3:
            contra["pred RETREAT total"] += 1
        tb = top(b, elig)
        if len(ts) == 1 and len(tb) == 1 and tb != ts:
            rec["B_changes_lookahead_choice"] += 1
            flips_to[f"{A[ts[0]]}->{A[tb[0]]}"] += 1
        if any(b[i] != scores[i] for i in elig):
            rec["B_bias_hits_eligible_action"] += 1
    return scores, reason


be.BattleWorld._lookahead = wrapped
for seed in (101, 202):
    w = be.BattleWorld(seed=seed, max_agents=60, episode_ticks=1500, learning=True)
    for _ in range(6000):
        w.step()
    stored = json.loads((CMP / f"cmp_seed{seed}.json").read_text(encoding="utf-8"))[
        "runs"
    ][0]
    assert stored["seed"] == seed and stored["learning"] is True
    same = json.dumps(w.snapshot(), sort_keys=True) == json.dumps(
        stored["summary"], sort_keys=True
    )
    print(f"seed {seed}: instrumented snapshot == stored summary: {same}")

n = rec["la_decisions"]
g = rec["gate_open"]
print(f"Lookahead planning calls {n}; gate open {g} ({100 * g / n:.1f}%)")
print(
    f"planner itself changes the utility argmax: {rec['planner_changes_utility_choice']} ({100 * rec['planner_changes_utility_choice'] / n:.1f}% of LA decisions)"
)
print(
    f"B bias touches an eligible action: {rec['B_bias_hits_eligible_action']} ({100 * rec['B_bias_hits_eligible_action'] / n:.1f}%)"
)
print(
    f"B would change Lookahead's final choice: {rec['B_changes_lookahead_choice']} ({100 * rec['B_changes_lookahead_choice'] / n:.1f}% of LA decisions, {100 * rec['B_changes_lookahead_choice'] / max(g, 1):.1f}% of gated)"
)
print(
    f"|planner correction| per eligible action: median {st.median(corr):.3f}, mean {st.mean(corr):.3f}, p90 {sorted(corr)[int(0.9 * len(corr))]:.3f}"
)
print(
    f"final top1-top2 margin: median {st.median(margins):.3f}; share < .5: {100 * sum(m < 0.5 for m in margins) / len(margins):.0f}%; share < .9: {100 * sum(m < 0.9 for m in margins) / len(margins):.0f}%"
)
print("pred under gate:", dict(pred_c.most_common()))
print(
    "contradiction with current enemy action (which the planner already uses):",
    dict(contra),
)
print("B flips (from->to), top 8:", flips_to.most_common(8))
