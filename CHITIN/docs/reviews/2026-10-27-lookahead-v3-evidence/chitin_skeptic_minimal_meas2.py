"""Read-only: endpoint alternatives for the 'minimal' proposal (epochs>=2), from today's cmp_seed*.json."""

import glob
import json
import math
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
eps = []
for fpath in sorted(glob.glob(str(Path(sys.argv[1]) / "cmp_seed*.json"))):
    d = json.loads(Path(fpath).read_text(encoding="utf-8"))
    for run in d["runs"]:
        snaps = list(run["world"]["episodes"]) + [run["summary"]]
        for ep, snap in enumerate(snaps[:-1], 1):
            pops = snap["populations"]
            m = {
                fa["method"]: dict(
                    score=fa["score"],
                    births=fa["births"],
                    kills=fa["kills"],
                    losses=fa["losses"],
                    dec=fa["decisions"],
                    pop=pops[fa["id"]],
                )
                for fa in snap["factions"]
            }
            eps.append(
                dict(
                    w=(run["seed"], run["learning"]), ep=ep, T=snap["episode_tick"], m=m
                )
            )
late = [e for e in eps if e["ep"] >= 2]


def corr(x, y):
    mx, my = st.mean(x), st.mean(y)
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / math.sqrt(
        sum((a - mx) ** 2 for a in x) * sum((b - my) ** 2 for b in y)
    )


def summ(v, label):
    n = len(v)
    mu = st.mean(v)
    sd = st.stdev(v)
    print(f"{label}: n={n} mean {mu:+.3f} sd {sd:.3f} ±{1.96 * sd / math.sqrt(n):.3f}")
    return mu, sd


def deff(vals, keys):
    n = len(vals)
    mu = st.mean(vals)
    sd = st.stdev(vals)
    g = defaultdict(list)
    for k, v in zip(keys, vals):
        g[k].append(v)
    G = len(g)
    se = (
        math.sqrt(sum((sum(v) - len(v) * mu) ** 2 for v in g.values()))
        / n
        * math.sqrt(G / (G - 1))
    )
    return (se / (sd / math.sqrt(n))) ** 2


la = [e["m"]["Lookahead"]["score"] for e in late]
op = [e["m"]["Opponent"]["score"] for e in late]
print(
    f"corr(LA, Opp) within epoch: {corr(la, op):+.3f}; sd LA {st.stdev(la):.2f}, sd Opp {st.stdev(op):.2f}, sd(LA-Opp) {st.stdev([a - b for a, b in zip(la, op)]):.2f}"
)
keys = [e["w"] for e in late]
print(
    f"deff(world) LA absolute {deff(la, keys):.2f}; Opp absolute {deff(op, keys):.2f}"
)

d = sorted(a - b for a, b in zip(la, op))
n = len(d)
q = lambda p: d[min(n - 1, int(p * n))]
mu = st.mean(d)
sd = st.stdev(d)
kurt = sum((x - mu) ** 4 for x in d) / n / sd**4
print(
    f"LA-Opp quantiles: p05 {q(0.05):+.1f} p25 {q(0.25):+.1f} median {q(0.5):+.2f} p75 {q(0.75):+.1f} p95 {q(0.95):+.1f} | kurtosis {kurt:.2f}"
)
k = int(0.1 * n)
tr = d[k : n - k]
print(f"10% trimmed mean {st.mean(tr):+.2f}")
# Wilcoxon signed-rank (normal approx)
nz = [x for x in d if abs(x) > 1e-12]
ranks = sorted(range(len(nz)), key=lambda i: abs(nz[i]))
r = [0] * len(nz)
for rank, i in enumerate(ranks, 1):
    r[i] = rank
W = sum(rr for rr, x in zip(r, nz) if x > 0)
N = len(nz)
z = (W - N * (N + 1) / 4) / math.sqrt(N * (N + 1) * (2 * N + 1) / 24)
print(f"Wilcoxon signed-rank z {z:+.2f}")
full = [e for e in late if e["T"] >= 1500]
summ(
    [e["m"]["Lookahead"]["score"] - e["m"]["Opponent"]["score"] for e in full],
    "LA-Opp full-length epochs only",
)

print(
    "\n-- arm A is already in the data: Opponent with gate closed == Utility (only branch: line 463)"
)
summ(
    [e["m"]["Opponent"]["score"] - e["m"]["Utility"]["score"] for e in late],
    "Opp - Utility (counter-table value), epochs>=2",
)
summ(
    [e["m"]["Opponent"]["score"] - e["m"]["Utility"]["score"] for e in eps],
    "Opp - Utility, all closed epochs",
)
summ(
    [e["m"]["Lookahead"]["score"] - e["m"]["Utility"]["score"] for e in late],
    "LA - Utility (forecast value), epochs>=2",
)

print(
    "\n-- survival / descendants endpoints, epochs>=2 (guide: advantage = survival, descendants, command influence)"
)
for meth in ("Lookahead", "Opponent", "Utility"):
    v = [e["m"][meth] for e in late]
    print(
        f"  {meth:10} extinct {100 * sum(x['pop'] == 0 for x in v) / len(v):5.1f}%  pop_end {st.mean(x['pop'] for x in v):4.2f}  births {st.mean(x['births'] for x in v):4.2f}  losses {st.mean(x['losses'] for x in v):4.2f}"
    )
lo = sum(
    e["m"]["Lookahead"]["pop"] == 0 and e["m"]["Opponent"]["pop"] > 0 for e in late
)
oo = sum(
    e["m"]["Lookahead"]["pop"] > 0 and e["m"]["Opponent"]["pop"] == 0 for e in late
)
print(
    f"  McNemar extinction LA-only {lo} vs Opp-only {oo}: z = {(oo - lo) / math.sqrt(oo + lo):+.2f}"
)
summ(
    [e["m"]["Lookahead"]["pop"] - e["m"]["Opponent"]["pop"] for e in late],
    "  pop_end LA-Opp",
)
summ(
    [e["m"]["Lookahead"]["births"] - e["m"]["Opponent"]["births"] for e in late],
    "  births LA-Opp",
)
summ(
    [e["m"]["Lookahead"]["losses"] - e["m"]["Opponent"]["losses"] for e in late],
    "  losses LA-Opp",
)

print("\n-- does score reward descendants? within-method correlations, epochs>=2")
for meth in ("Lookahead", "Opponent", "Utility", "Reflex"):
    v = [e["m"][meth] for e in late]
    print(
        f"  {meth:10} corr(score,births) {corr([x['score'] for x in v], [x['births'] for x in v]):+.3f}  "
        f"corr(score,pop_end) {corr([x['score'] for x in v], [x['pop'] for x in v]):+.3f}  "
        f"corr(score,losses) {corr([x['score'] for x in v], [x['losses'] for x in v]):+.3f}"
    )
# per-birth marginal score: within-epoch regression of score on births and losses (all methods, demeaned by epoch)
X1, X2, Y = [], [], []
for e in late:
    mb = st.mean(r["births"] for r in e["m"].values())
    ml = st.mean(r["losses"] for r in e["m"].values())
    ms = st.mean(r["score"] for r in e["m"].values())
    for r in e["m"].values():
        X1.append(r["births"] - mb)
        X2.append(r["losses"] - ml)
        Y.append(r["score"] - ms)
s11 = sum(a * a for a in X1)
s22 = sum(b * b for b in X2)
s12 = sum(a * b for a, b in zip(X1, X2))
s1y = sum(a * y for a, y in zip(X1, Y))
s2y = sum(b * y for b, y in zip(X2, Y))
det = s11 * s22 - s12 * s12
b1 = (s1y * s22 - s2y * s12) / det
b2 = (s2y * s11 - s1y * s12) / det
print(f"  within-epoch OLS: score ~ {b1:+.2f}*births {b2:+.2f}*losses (all methods)")
