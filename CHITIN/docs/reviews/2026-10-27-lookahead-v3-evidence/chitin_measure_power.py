"""Power of the pre-registered branching decision rule, by cluster bootstrap of today's A data.

Model: B = A + delta added to Lookahead's epoch score (pure improvement, no spillover).
Rule (proposal): HELPS iff mean(LA-Opp)>=1.5 and its 95% CI lower bound>0 (SE clustered by world)
and mean(LA-4serious)>=1.5 and top1>=0.24 and mean LA losses<=4.0.
HARMS iff mean(LA-4serious)<1.5 or losses>4.0 or top1<0.20. NEUTRAL iff CI of LA-Opp includes 0.
Also: paired extinction (LA vs Opp), LA-Utility contrast, sd of LA absolute score.
"""

import glob
import json
import math
import random
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
files = sorted(glob.glob(str(Path(sys.argv[1]) / "cmp_seed*.json")))
worlds = defaultdict(list)  # world -> list of epoch dicts method->row
for fpath in files:
    d = json.loads(Path(fpath).read_text(encoding="utf-8"))
    for run in d["runs"]:
        snaps = list(run["world"]["episodes"]) + [run["summary"]]
        for ep, snap in enumerate(snaps[:-1], 1):
            pops = snap["populations"]
            m = {
                fa["method"]: dict(
                    score=fa["score"],
                    losses=fa["losses"],
                    births=fa["births"],
                    pop=pops[fa["id"]],
                    dec=fa["decisions"],
                )
                for fa in snap["factions"]
            }
            worlds[(run["seed"], run["learning"])].append(m)
keys = sorted(worlds)
serious = ("Utility", "UCB", "Q-learning", "Opponent")

# descriptive extras
eps = [m for k in keys for m in worlds[k]]
la_u = [m["Lookahead"]["score"] - m["Utility"]["score"] for m in eps]
print(
    f"LA-Utility paired: n={len(la_u)} mean={st.mean(la_u):+.2f} ±{1.96 * st.stdev(la_u) / math.sqrt(len(la_u)):.2f}"
)
print(
    f"LA absolute score sd={st.stdev(m['Lookahead']['score'] for m in eps):.2f} | LA score - epoch mean sd="
    f"{st.stdev(m['Lookahead']['score'] - st.mean(v['score'] for v in m.values()) for m in eps):.2f}"
)
both = sum(m["Lookahead"]["pop"] == 0 and m["Opponent"]["pop"] == 0 for m in eps)
la_only = sum(m["Lookahead"]["pop"] == 0 and m["Opponent"]["pop"] > 0 for m in eps)
op_only = sum(m["Lookahead"]["pop"] > 0 and m["Opponent"]["pop"] == 0 for m in eps)
z = (op_only - la_only) / math.sqrt(op_only + la_only)
print(
    f"extinction LA vs Opp: both {both}, LA-only {la_only}, Opp-only {op_only}, McNemar z={z:+.2f}"
)
for meth in ("Utility", "UCB", "Q-learning", "Reflex"):
    lo = sum(m["Lookahead"]["pop"] == 0 and m[meth]["pop"] > 0 for m in eps)
    oo = sum(m["Lookahead"]["pop"] > 0 and m[meth]["pop"] == 0 for m in eps)
    print(
        f"   extinction LA vs {meth}: LA-only {lo}, {meth}-only {oo}, z={(oo - lo) / math.sqrt(max(1, oo + lo)):+.2f}"
    )
# within-epoch: does score rank extinct factions above survivors?
inv = tot = 0
for m in eps:
    rows = list(m.values())
    for a in rows:
        for b in rows:
            if a["pop"] == 0 and b["pop"] > 0:
                tot += 1
                inv += a["score"] > b["score"]
print(
    f"pairs (extinct, survivor) in same epoch where extinct has HIGHER score: {inv}/{tot} = {100 * inv / tot:.1f}%"
)


def evaluate(sample, delta):
    n = len([1 for w in sample for _ in worlds[w]])
    d1, d2, top, loss, cl = [], [], 0, [], []
    for w in sample:
        tot1 = 0.0
        for m in worlds[w]:
            la = m["Lookahead"]["score"] + delta
            x1 = la - m["Opponent"]["score"]
            x2 = la - st.mean(m[o]["score"] for o in serious)
            d1.append(x1)
            d2.append(x2)
            tot1 += x1
            others = max(v["score"] for k, v in m.items() if k != "Lookahead")
            top += la >= others - 1e-9
            loss.append(m["Lookahead"]["losses"])
        cl.append((tot1, len(worlds[w])))
    mean1 = sum(d1) / n
    g = len(cl)
    se = (
        math.sqrt(sum((t - k * mean1) ** 2 for t, k in cl)) / n * math.sqrt(g / (g - 1))
    )
    lower, upper = mean1 - 1.96 * se, mean1 + 1.96 * se
    mean2 = sum(d2) / n
    top1 = top / n
    ml = sum(loss) / n
    helps = mean1 >= 1.5 and lower > 0 and mean2 >= 1.5 and top1 >= 0.24 and ml <= 4.0
    harms = mean2 < 1.5 or ml > 4.0 or top1 < 0.20
    neutral = lower <= 0 <= upper
    return helps, harms, neutral, lower > 0, mean1, mean2, top1


rng = random.Random(20261027)
B = 2000
print("\nrule outcome rates, n=100 worlds (=400 epochs) per replicate, B=", B)
print(
    f"{'delta':>5} {'HELPS':>7} {'HARMS':>7} {'NEUTRAL':>8} {'LAOpp sig>0':>11} {'HARMS & sig>0':>13} {'unclassified':>12}"
)
for delta in (0.0, 0.5, 1.0, 1.5, 2.0, 3.0):
    c = defaultdict(int)
    for _ in range(B):
        sample = [rng.choice(keys) for _ in range(100)]
        h, hm, ne, sig, *_ = evaluate(sample, delta)
        c["h"] += h
        c["hm"] += hm
        c["ne"] += ne
        c["sig"] += sig
        c["hm_sig"] += hm and sig
        c["none"] += (not h) and (not hm) and (not ne)
    print(
        f"{delta:5.1f} {100 * c['h'] / B:6.1f}% {100 * c['hm'] / B:6.1f}% {100 * c['ne'] / B:7.1f}% {100 * c['sig'] / B:10.1f}% "
        f"{100 * c['hm_sig'] / B:12.1f}% {100 * c['none'] / B:11.1f}%"
    )

# Proper B-vs-A test: difference of mean(LA-Opp) between two independent arms of 100 worlds each
print(
    "\nB-vs-A two-arm test on LA-Opp (100 worlds per arm), power at alpha=.05 two-sided:"
)
for delta in (0.5, 1.0, 1.5, 2.0, 3.0):
    hits = 0
    for _ in range(B // 2):
        sa = [rng.choice(keys) for _ in range(100)]
        sb = [rng.choice(keys) for _ in range(100)]

        def stat(sample, dl):
            vals = [
                (
                    sum(
                        m["Lookahead"]["score"] + dl - m["Opponent"]["score"]
                        for m in worlds[w]
                    ),
                    len(worlds[w]),
                )
                for w in sample
            ]
            n = sum(k for _, k in vals)
            mean = sum(t for t, _ in vals) / n
            g = len(vals)
            se = (
                math.sqrt(sum((t - k * mean) ** 2 for t, k in vals))
                / n
                * math.sqrt(g / (g - 1))
            )
            return mean, se

        ma, sea = stat(sa, 0.0)
        mb, seb = stat(sb, delta)
        hits += (mb - ma) / math.sqrt(sea**2 + seb**2) > 1.96
    print(f"  delta={delta:.1f}: power {100 * hits / (B // 2):.1f}%")
