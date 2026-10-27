"""Read-only measurement-lens check of the 'minimal' proposal's pre-registered rule, from today's cmp_seed*.json."""

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
eps = []  # one dict per closed epoch
for fpath in files:
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
                    fid=fa["id"],
                )
                for fa in snap["factions"]
            }
            eps.append(
                dict(
                    seed=run["seed"],
                    learning=run["learning"],
                    ep=ep,
                    T=snap["episode_tick"],
                    m=m,
                )
            )
print("closed epochs", len(eps))


def ci(v):
    n = len(v)
    return st.mean(v), st.stdev(v), 1.96 * st.stdev(v) / math.sqrt(n), n


def corr(x, y):
    mx, my = st.mean(x), st.mean(y)
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / math.sqrt(
        sum((a - mx) ** 2 for a in x) * sum((b - my) ** 2 for b in y)
    )


late = [e for e in eps if e["ep"] >= 2]
d = [e["m"]["Lookahead"]["score"] - e["m"]["Opponent"]["score"] for e in late]
mean, sd, h, n = ci(d)
print(f"\n[1] LA-Opp epochs>=2: n={n} mean {mean:+.2f} sd {sd:.2f} ±{h:.2f}")
for k in (2, 3, 4):
    v = [
        e["m"]["Lookahead"]["score"] - e["m"]["Opponent"]["score"]
        for e in eps
        if e["ep"] == k
    ]
    a, s, hh, nn = ci(v)
    print(f"    epoch {k}: n={nn} mean {a:+.2f} sd {s:.2f} ±{hh:.2f}")

# [2] cluster design effect of d (epochs>=2) by world and by seed
for label, keyf in (
    ("world", lambda e: (e["seed"], e["learning"])),
    ("seed", lambda e: e["seed"]),
):
    g = defaultdict(list)
    for e, x in zip(late, d):
        g[keyf(e)].append(x)
    G = len(g)
    se_cl = (
        math.sqrt(sum((sum(v) - len(v) * mean) ** 2 for v in g.values()))
        / n
        * math.sqrt(G / (G - 1))
    )
    deff = (se_cl / (sd / math.sqrt(n))) ** 2
    cm = [st.mean(v) for v in g.values()]
    print(
        f"[2] cluster={label}: G={G} cluster-robust ±{1.96 * se_cl:.2f} deff {deff:.2f} | mean of cluster means {st.mean(cm):+.2f} ±{1.96 * st.stdev(cm) / math.sqrt(G):.2f}"
    )

# [3] absolute score sd (unpaired between-arm comparisons) and the proposal's non-inferiority margins
N = 660
for meth, margin in (("Lookahead", 0.5), ("Opponent", 1.0)):
    v = [e["m"][meth]["score"] for e in late]
    s = st.stdev(v)
    se = s * math.sqrt(2 / N)
    p_fail = 0.5 * math.erfc((margin / se) / math.sqrt(2))
    print(
        f"[3] {meth} absolute score epochs>=2 sd {s:.2f} -> SE(B-BASE) at {N}/arm {se:.2f}; "
        f'P(gate "B >= BASE-{margin}" fails | zero true effect) = {100 * p_fail:.0f}%'
    )
seD = sd * math.sqrt(2 / N)
for delta in (1.0, 1.5):
    z = delta / seD
    pw = 0.5 * math.erfc((1.96 - z) / math.sqrt(2))
    print(
        f"[3b] two-arm test of patch effect on d: SE {seD:.2f}; power for Delta={delta}: {100 * pw:.0f}%; "
        f"n/arm for 80%: {2 * ((1.96 + 0.8416) * sd / delta) ** 2:.0f} epochs (x deff)"
    )

# [4] operating characteristics of the exact ship / refute / park rule by resampling worlds
worlds = defaultdict(list)
for e in late:
    worlds[(e["seed"], e["learning"])].append(e)
wkeys = sorted(worlds)
rng = random.Random(7)


def draw(nseeds):
    # resample worlds (pairs ON/OFF not kept; independence assumed for epochs>=2), 2 worlds per seed
    out = []
    for i in range(nseeds * 2):
        for x in worlds[rng.choice(wkeys)]:
            y = dict(x)
            y["sid"] = i // 2
            out.append(y)
    return out


def stats_d(sample, shift_la=0.0, shift_opp=0.0, base_shift=0.0):
    v = [
        x["m"]["Lookahead"]["score"]
        - x["m"]["Opponent"]["score"]
        + base_shift
        + shift_la
        - shift_opp
        for x in sample
    ]
    return v


def seed_ci_low(sample, dB):
    g = defaultdict(list)
    for x, v in zip(sample, dB):
        g[x["sid"]].append(v)
    cm = [st.mean(v) for v in g.values()]
    return st.mean(cm) - 1.96 * st.stdev(cm) / math.sqrt(len(cm))


def rule(dB, laB, laBASE, oppB, oppBASE, dBASE, seed_low=1.0):
    mB, sB = st.mean(dB), st.stdev(dB) / math.sqrt(len(dB))
    mBASE, sBASE = st.mean(dBASE), st.stdev(dBASE) / math.sqrt(len(dBASE))
    if mBASE >= 1.0 and mBASE - 1.96 * sBASE > 0:
        return "stop_sanity"
    ship = (
        mB >= 1.5
        and mB - 1.96 * sB > 0
        and seed_low > 0
        and st.mean(laB) >= st.mean(laBASE) - 0.5
        and st.mean(oppB) >= st.mean(oppBASE) - 1.0
    )
    refuted = mB < 0.5 or mB - 1.96 * sB <= 0
    parked = 0.5 <= mB < 1.5
    if ship:
        return "ship"
    if refuted and parked:
        return "refuted&parked(overlap)"
    if refuted:
        return "refuted"
    if parked:
        return "parked"
    return "ship-blocked-by-noninferiority"


base_mean = mean
print(
    f"\n[4] exact rule, 110 seeds x2 learning x epochs 2-4 per arm, resampled worlds; baseline d0 = data mean {base_mean:+.2f} shifted to d0"
)
for d0 in (0.0, base_mean, 1.0):
    for delta in (0.0, 0.5, 1.0, 1.5):
        tally = defaultdict(int)
        R = 400
        for _ in range(R):
            sBASE = draw(110)
            sB = draw(110)
            dBASE = stats_d(sBASE, base_shift=d0 - base_mean)
            dB = stats_d(sB, shift_la=delta, base_shift=d0 - base_mean)
            laBASE = [x["m"]["Lookahead"]["score"] for x in sBASE]
            laB = [x["m"]["Lookahead"]["score"] + delta for x in sB]
            oppBASE = [x["m"]["Opponent"]["score"] for x in sBASE]
            oppB = [x["m"]["Opponent"]["score"] for x in sB]
            tally[rule(dB, laB, laBASE, oppB, oppBASE, dBASE, seed_ci_low(sB, dB))] += 1
        print(
            f"    d0={d0:+.2f} Delta={delta:.1f}: "
            + ", ".join(f"{k} {100 * v / R:.0f}%" for k, v in sorted(tally.items()))
        )

# [4b] loophole: patch that only hurts Opponent by 0.9 (allowed by margin) and does nothing for LA
tally = defaultdict(int)
R = 400
for _ in range(R):
    sBASE = draw(110)
    sB = draw(110)
    dBASE = stats_d(sBASE)
    dB = stats_d(sB, shift_opp=-0.9)
    laBASE = [x["m"]["Lookahead"]["score"] for x in sBASE]
    laB = [x["m"]["Lookahead"]["score"] for x in sB]
    oppBASE = [x["m"]["Opponent"]["score"] for x in sBASE]
    oppB = [x["m"]["Opponent"]["score"] - 0.9 for x in sB]
    tally[rule(dB, laB, laBASE, oppB, oppBASE, dBASE, seed_ci_low(sB, dB))] += 1
print(
    "[4b] zero LA effect, Opp -0.9 (inside margin): "
    + ", ".join(f"{k} {100 * v / R:.0f}%" for k, v in sorted(tally.items()))
)

# [5] is score a fitness metric? relation to agent-ticks (decisions), births, survival
rows = [(e, meth, r) for e in late for meth, r in e["m"].items()]
sc = [r["score"] for _, _, r in rows]
for name, key in (
    ("decisions", "dec"),
    ("births", "births"),
    ("losses", "losses"),
    ("kills", "kills"),
    ("pop_end", "pop"),
):
    print(
        f"[5] corr(score, {name}) over faction-epochs (epochs>=2): {corr(sc, [r[key] for _, _, r in rows]):+.3f}"
    )
# within-epoch: demeaned
dm_s, dm_dec = [], []
for e in late:
    ms = st.mean(r["score"] for r in e["m"].values())
    md = st.mean(r["dec"] for r in e["m"].values())
    for r in e["m"].values():
        dm_s.append(r["score"] - ms)
        dm_dec.append(r["dec"] - md)
b = sum(x * y for x, y in zip(dm_dec, dm_s)) / sum(x * x for x in dm_dec)
print(
    f"[5b] within-epoch slope score~decisions: {b:+.4f} per decision ({b * 100:+.2f} per 100 decisions); corr {corr(dm_s, dm_dec):+.3f}"
)
for meth in ("Lookahead", "Opponent", "Utility", "UCB", "Q-learning", "Reflex"):
    v = [e["m"][meth] for e in late]
    print(
        f"    {meth:10} score {st.mean(x['score'] for x in v):+7.2f} decisions {st.mean(x['dec'] for x in v):6.0f} "
        f"births {st.mean(x['births'] for x in v):4.2f} losses {st.mean(x['losses'] for x in v):4.2f} "
        f"extinct {100 * sum(x['pop'] == 0 for x in v) / len(v):4.1f}% pop_end {st.mean(x['pop'] for x in v):4.2f}"
    )
# LA-Opp adjusted for decision difference (regression-adjusted)
dd = [e["m"]["Lookahead"]["dec"] - e["m"]["Opponent"]["dec"] for e in late]
adj = [x - b * y for x, y in zip(d, dd)]
a, s, hh, nn = ci(adj)
print(
    f"[5c] LA-Opp after removing within-epoch decisions slope: {a:+.2f} ±{hh:.2f} (raw {mean:+.2f}); mean dec diff {st.mean(dd):+.1f}"
)
early = sum(e["T"] < 1500 for e in eps)
print(f"[6] early-closed epochs: {early}/{len(eps)}")
