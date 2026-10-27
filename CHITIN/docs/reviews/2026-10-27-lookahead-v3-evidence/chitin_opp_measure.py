"""Measurement-lens audit for the 'opponent model in forecast' proposal (read-only).

Questions: is score a population-time artefact; noise/power/cluster structure of LA-Opponent;
epoch-1 fixed assignment; colour carry-over (best_genes); learning ON/OFF pairing; win-rate threshold
consistency; DiD power for the stage-2 design.
"""

import ctypes
import glob
import json
import math
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

try:
    ctypes.windll.kernel32.SetPriorityClass(
        ctypes.windll.kernel32.GetCurrentProcess(), 0x4000
    )
except Exception:
    pass
sys.stdout.reconfigure(encoding="utf-8")
files = sorted(glob.glob(str(Path(sys.argv[1]) / "cmp_seed*.json")))
rows = []
for fpath in files:
    d = json.loads(Path(fpath).read_text(encoding="utf-8"))
    for run in d["runs"]:
        w = run["world"]
        snaps = list(w["episodes"]) + [run["summary"]]
        hist = w["history"]
        # agent-ticks per (episode, faction) from 10-tick population samples
        at = defaultdict(float)
        for h in hist:
            for fid, p in enumerate(h["populations"]):
                at[(h["episode"], fid)] += 10 * p
        for ep, snap in enumerate(snaps, 1):
            if ep == len(snaps):
                continue
            pops = snap["populations"]
            for fa in snap["factions"]:
                rows.append(
                    dict(
                        seed=run["seed"],
                        learning=run["learning"],
                        epoch=ep,
                        fid=fa["id"],
                        world=(run["seed"], run["learning"]),
                        method=fa["method"],
                        score=fa["score"],
                        births=fa["births"],
                        kills=fa["kills"],
                        losses=fa["losses"],
                        dec=fa["decisions"],
                        pop=pops[fa["id"]],
                        at=at[(ep, fa["id"])],
                        hist_len=len(hist),
                    )
                )
print("rows", len(rows), "hist_len set", sorted({r["hist_len"] for r in rows}))
epochs = defaultdict(dict)
for r in rows:
    epochs[(r["seed"], r["learning"], r["epoch"])][r["method"]] = r
print("closed epochs", len(epochs))


def ols(x, y):
    mx, my = st.mean(x), st.mean(y)
    sxx = sum((a - mx) ** 2 for a in x)
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    syy = sum((b - my) ** 2 for b in y)
    return sxy / sxx, sxy / math.sqrt(sxx * syy)


# (1) score vs agent-ticks
x = [r["at"] for r in rows]
y = [r["score"] for r in rows]
s, rr = ols(x, y)
print(
    f"\n(1) score ~ agent-ticks (all faction-epochs): slope {1000 * s:+.2f} per 1000 agent-ticks, r={rr:+.3f}, R2={rr * rr:.3f}"
)
dx, dy = [], []
for m in epochs.values():
    ma = st.mean(v["at"] for v in m.values())
    ms = st.mean(v["score"] for v in m.values())
    for v in m.values():
        dx.append(v["at"] - ma)
        dy.append(v["score"] - ms)
s, rr = ols(dx, dy)
print(
    f"    within-epoch demeaned: slope {1000 * s:+.2f} per 1000 agent-ticks, r={rr:+.3f}, R2={rr * rr:.3f}"
)
by = defaultdict(list)
for r in rows:
    by[r["method"]].append(r)
print(
    f"{'method':11} {'score':>7} {'agentT':>7} {'sc/1kAT':>8} {'sc/dec':>8} {'births':>6} {'kills':>6} {'losses':>6} {'pop':>5} {'ext%':>5}"
)
for meth, rs in sorted(by.items(), key=lambda kv: -st.mean(r["score"] for r in kv[1])):
    print(
        f"{meth:11} {st.mean(r['score'] for r in rs):7.2f} {st.mean(r['at'] for r in rs):7.0f} "
        f"{1000 * sum(r['score'] for r in rs) / sum(r['at'] for r in rs):8.3f} "
        f"{sum(r['score'] for r in rs) / sum(r['dec'] for r in rs):8.4f} {st.mean(r['births'] for r in rs):6.2f} "
        f"{st.mean(r['kills'] for r in rs):6.2f} {st.mean(r['losses'] for r in rs):6.2f} {st.mean(r['pop'] for r in rs):5.2f} "
        f"{100 * sum(r['pop'] == 0 for r in rs) / len(rs):5.1f}"
    )
inv = tot = 0
for m in epochs.values():
    vs = list(m.values())
    for a in vs:
        for b in vs:
            if a["pop"] == 0 and b["pop"] > 0:
                tot += 1
                inv += a["score"] > b["score"]
print(
    f"extinct-vs-survivor pairs where the extinct faction has the HIGHER score: {inv}/{tot} = {100 * inv / max(1, tot):.1f}%"
)


# (2) LA - Opponent contrasts: sd, clustering, power
def stats(diffs_by_key):
    keys = list(diffs_by_key)
    v = [diffs_by_key[k] for k in keys]
    n = len(v)
    mean = st.mean(v)
    sd = st.stdev(v)

    def crse(groupfn):
        g = defaultdict(list)
        for k in keys:
            g[groupfn(k)].append(diffs_by_key[k])
        G = len(g)
        tot = sum((sum(vals) - len(vals) * mean) ** 2 for vals in g.values())
        return math.sqrt(tot) / n * math.sqrt(G / (G - 1))

    se = sd / math.sqrt(n)
    return (
        n,
        mean,
        sd,
        se,
        crse(lambda k: (k[0], k[1])),
        crse(lambda k: k[0]),
        crse(lambda k: k[0] // 100),
    )


def report(label, fn, keep=lambda k: True):
    dd = {k: fn(m) for k, m in epochs.items() if keep(k)}
    n, mean, sd, se, sew, ses, sef = stats(dd)
    wins = sum(v > 0 for v in dd.values()) / n
    print(
        f"{label}: n={n} mean={mean:+.2f} sd={sd:.2f} wins={100 * wins:.0f}% | 95% half-width naive ±{1.96 * se:.2f}, "
        f"world-clustered ±{1.96 * sew:.2f}, seed-clustered ±{1.96 * ses:.2f}, file-clustered(6) ±{1.96 * sef:.2f}; "
        f"deff(seed)={(ses / se) ** 2:.2f}"
    )
    return dd, sd, ses / se


print("\n(2) paired contrasts")
la_opp, sd_lo, inf_lo = report(
    "LA-Opp all", lambda m: m["Lookahead"]["score"] - m["Opponent"]["score"]
)
report(
    "LA-Opp epochs 2-4",
    lambda m: m["Lookahead"]["score"] - m["Opponent"]["score"],
    lambda k: k[2] >= 2,
)
report(
    "LA-Opp epoch 1 (fixed AZURE vs CORAL)",
    lambda m: m["Lookahead"]["score"] - m["Opponent"]["score"],
    lambda k: k[2] == 1,
)
report(
    "LA-Opp per 1k agent-ticks",
    lambda m: (
        1000
        * (
            m["Lookahead"]["score"] / max(1, m["Lookahead"]["at"])
            - m["Opponent"]["score"] / max(1, m["Opponent"]["at"])
        )
    ),
)
report("LA-Opp agent-ticks", lambda m: m["Lookahead"]["at"] - m["Opponent"]["at"])
report("LA-Opp losses", lambda m: m["Lookahead"]["losses"] - m["Opponent"]["losses"])
report("LA-Opp end pop", lambda m: m["Lookahead"]["pop"] - m["Opponent"]["pop"])
report("LA-Opp kills", lambda m: m["Lookahead"]["kills"] - m["Opponent"]["kills"])

# power: within-build (one-sample) and DiD (two independent builds) for delta
z_a, z_b = 1.959964, 0.841621
for label, sd, infl in (("LA-Opp", sd_lo, inf_lo),):
    for delta in (1.0, 1.5, 2.0):
        n1 = ((z_a + z_b) * sd / delta) ** 2 * infl**2
        n2 = 2 * n1
        print(
            f"  {label} delta={delta}: epochs for 80% power one-sample {n1:.0f}; DiD per build {n2:.0f} (seed-cluster inflation {infl**2:.2f})"
        )
    se720 = sd * infl / math.sqrt(720)
    for delta in (0.0, 1.0, 1.5, 2.0, 3.0):
        # stage-2 rule on treatment build only: mean>=1.5 and lower CI>0 (normal approx); wins>=55% via shift model
        p_mean = 1 - 0.5 * (1 + math.erf((1.5 - delta) / (se720 * math.sqrt(2))))
        wins = sum(v + delta > 0 for v in la_opp.values()) / len(la_opp)
        se_did = math.sqrt(2) * se720
        p_did = 1 - 0.5 * (
            1 + math.erf((z_a * se_did - delta) / (se_did * math.sqrt(2)))
        )
        print(
            f"  delta={delta:.1f}: P(mean>=1.5 | n=720)={p_mean:.2f}; empirical win share after shift={100 * wins:.1f}% "
            f"(rule needs >=55%); DiD power at n=720/build={p_did:.2f}"
        )

# (3) ON/OFF pairing: correlation of LA-Opp between learning ON and OFF of the same seed and epoch
pairs = [
    (la_opp[(s_, True, e)], la_opp[(s_, False, e)])
    for (s_, l, e) in la_opp
    if l and (s_, False, e) in la_opp
]
for e in (1, 2, 3, 4):
    pe = [
        (a, b)
        for (s_, l, ee) in la_opp
        if l and ee == e and (s_, False, ee) in la_opp
        for a, b in [(la_opp[(s_, True, ee)], la_opp[(s_, False, ee)])]
    ]
    print(
        f"(3) ON/OFF corr of LA-Opp, epoch {e}: r={ols([a for a, _ in pe], [b for _, b in pe])[1]:+.3f} (n={len(pe)})"
    )
# raw score identity in epoch 1 ON vs OFF for LA and Opp
same = sum(
    abs(epochs[(s_, True, 1)][mm]["score"] - epochs[(s_, False, 1)][mm]["score"]) < 1e-9
    for s_ in {k[0] for k in epochs}
    for mm in ("Lookahead", "Opponent")
)
print(
    f"    epoch-1 LA/Opp scores bit-identical between ON and OFF worlds: {same}/{2 * len({k[0] for k in epochs})}"
)

# (4) colour effects and carry-over
col = defaultdict(list)
for r in rows:
    col[r["fid"]].append(
        r["score"]
        - st.mean(
            v["score"] for v in epochs[(r["seed"], r["learning"], r["epoch"])].values()
        )
    )
print(
    "\n(4) mean demeaned score by colour (fid):",
    {k: round(st.mean(v), 2) for k, v in sorted(col.items())},
    " n per colour",
    {k: len(v) for k, v in sorted(col.items())},
)
col_e = defaultdict(list)
for r in rows:
    if r["epoch"] >= 2:
        col_e[r["fid"]].append(
            r["score"]
            - st.mean(
                v["score"]
                for v in epochs[(r["seed"], r["learning"], r["epoch"])].values()
            )
        )
print(
    "    epochs 2-4 only:", {k: round(st.mean(v), 2) for k, v in sorted(col_e.items())}
)
# carry-over: demeaned score of colour c in epoch e vs epoch e-1 (methods differ after the shuffle)
byc = {}
for r in rows:
    byc[(r["seed"], r["learning"], r["epoch"], r["fid"])] = r["score"] - st.mean(
        v["score"] for v in epochs[(r["seed"], r["learning"], r["epoch"])].values()
    )
xs, ys = [], []
for (s_, l, e, c), v in byc.items():
    if e >= 2 and (s_, l, e - 1, c) in byc:
        xs.append(byc[(s_, l, e - 1, c)])
        ys.append(v)
print(
    f"    colour carry-over: corr(demeaned score e-1, e) on same colour r={ols(xs, ys)[1]:+.3f} (n={len(xs)})"
)
# spillover: colour held by LA in e-1 -> its new holder's demeaned score in e
sp, other = [], []
for (s_, l, e), m in epochs.items():
    if e < 2:
        continue
    prev = epochs.get((s_, l, e - 1))
    la_fid_prev = prev["Lookahead"]["fid"]
    for meth, v in m.items():
        if meth == "Lookahead":
            continue
        (sp if v["fid"] == la_fid_prev else other).append(byc[(s_, l, e, v["fid"])])
print(
    f"    non-LA method on the colour LA held in e-1: mean demeaned {st.mean(sp):+.2f} (n={len(sp)}) vs other colours {st.mean(other):+.2f} (n={len(other)})"
)
# how often LA keeps the same colour / Opp colour in epoch 1
print(
    "    epoch-1 colours: LA",
    {epochs[k]["Lookahead"]["fid"] for k in epochs if k[2] == 1},
    "Opp",
    {epochs[k]["Opponent"]["fid"] for k in epochs if k[2] == 1},
)
