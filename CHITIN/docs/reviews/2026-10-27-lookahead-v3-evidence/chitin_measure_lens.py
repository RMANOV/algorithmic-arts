"""Measurement-lens audit of the CHITIN method comparison (read-only).

Questions: (1) is score a population-time artefact? (2) noise / power / cluster
structure of the paired contrasts, (3) positional and learning-pair confounds.
"""

import glob
import json
import math
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
files = sorted(glob.glob(str(Path(sys.argv[1]) / "cmp_seed*.json")))
rows = []
cfg = None
for fpath in files:
    d = json.loads(Path(fpath).read_text(encoding="utf-8"))
    for ri, run in enumerate(d["runs"]):
        if cfg is None:
            cfg = run["world"]["config"]
        snaps = list(run["world"]["episodes"]) + [run["summary"]]
        for ep, snap in enumerate(snaps, 1):
            if ep == len(snaps):
                continue  # open epoch
            pops = snap.get("populations") or [None] * 6
            for fa in snap["factions"]:
                rows.append(
                    dict(
                        seed=run["seed"],
                        learning=run["learning"],
                        epoch=ep,
                        world=(run["seed"], run["learning"]),
                        fid=fa["id"],
                        method=fa["method"],
                        score=fa["score"],
                        births=fa["births"],
                        kills=fa["kills"],
                        losses=fa["losses"],
                        dec=fa["decisions"],
                        pop=pops[fa["id"]],
                        ep_tick=snap.get("episode_tick"),
                        tick=snap.get("tick"),
                    )
                )
print("config", cfg)
print(
    "rows",
    len(rows),
    "worlds",
    len({r["world"] for r in rows}),
    "seeds",
    len({r["seed"] for r in rows}),
)
epochs = defaultdict(list)
for r in rows:
    epochs[(r["seed"], r["learning"], r["epoch"])].append(r)
print("closed epochs", len(epochs))
lens = [rs[0]["ep_tick"] for rs in epochs.values()]
print(
    "episode_tick at close: min",
    min(lens),
    "max",
    max(lens),
    "n<1500:",
    sum(x < 1500 for x in lens),
)


def ols(x, y):
    mx, my = st.mean(x), st.mean(y)
    sxx = sum((a - mx) ** 2 for a in x)
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    syy = sum((b - my) ** 2 for b in y)
    slope = sxy / sxx
    r = sxy / math.sqrt(sxx * syy)
    return slope, my - slope * mx, r


# (1) within-epoch demeaned relation score ~ decisions (agent-time proxy)
dx, dy, db, dl, dp = [], [], [], [], []
for rs in epochs.values():
    md = st.mean(r["dec"] for r in rs)
    ms = st.mean(r["score"] for r in rs)
    mb = st.mean(r["births"] for r in rs)
    ml = st.mean(r["losses"] for r in rs)
    mp = st.mean(r["pop"] for r in rs)
    for r in rs:
        dx.append(r["dec"] - md)
        dy.append(r["score"] - ms)
        db.append(r["births"] - mb)
        dl.append(r["losses"] - ml)
        dp.append(r["pop"] - mp)
s, _, rr = ols(dx, dy)
print(
    f"\n(1) within-epoch score ~ decisions: slope {s:+.4f}/decision, r={rr:+.3f}, R2={rr * rr:.3f}"
)
s, _, rr = ols(db, dy)
print(f"    within-epoch score ~ births: slope {s:+.3f}/birth, r={rr:+.3f}")
s, _, rr = ols(dl, dy)
print(f"    within-epoch score ~ losses: slope {s:+.3f}/loss, r={rr:+.3f}")
s, _, rr = ols(dp, dy)
print(f"    within-epoch score ~ pop_end: slope {s:+.3f}/agent, r={rr:+.3f}")
s, _, rr = ols(db, dx)
print(
    f"    within-epoch decisions ~ births: slope {s:+.1f} decisions/birth, r={rr:+.3f}"
)

# per-method means
by = defaultdict(list)
for r in rows:
    by[r["method"]].append(r)
print(
    f"\n{'method':11} {'score':>7} {'dec':>6} {'score/dec':>9} {'births':>6} {'losses':>6} {'pop':>5} {'extinct%':>8}"
)
for m, rs in sorted(by.items(), key=lambda kv: -st.mean(r["score"] for r in kv[1])):
    print(
        f"{m:11} {st.mean(r['score'] for r in rs):7.2f} {st.mean(r['dec'] for r in rs):6.0f} "
        f"{st.mean(r['score'] / max(1, r['dec']) for r in rs):9.4f} {st.mean(r['births'] for r in rs):6.2f} "
        f"{st.mean(r['losses'] for r in rs):6.2f} {st.mean(r['pop'] for r in rs):5.2f} "
        f"{100 * sum(r['pop'] == 0 for r in rs) / len(rs):7.1f}%"
    )

# extinct factions: score vs survivors in same epoch
ext, surv = [], []
for rs in epochs.values():
    for r in rs:
        (ext if r["pop"] == 0 else surv).append(r["score"])
print(
    f"\nextinct factions n={len(ext)} mean score {st.mean(ext) if ext else float('nan'):.2f} | survivors n={len(surv)} mean {st.mean(surv):.2f}"
)
# rank of extinct within epoch
ranks_ext = []
for rs in epochs.values():
    sc = sorted((r["score"] for r in rs), reverse=True)
    for r in rs:
        if r["pop"] == 0:
            ranks_ext.append(1 + sum(v > r["score"] + 1e-9 for v in sc))
if ranks_ext:
    print(
        "extinct faction mean rank (1=best):",
        round(st.mean(ranks_ext), 2),
        "top1 share",
        round(sum(x == 1 for x in ranks_ext) / len(ranks_ext), 3),
    )


def contrast(fn, label, keep=None):
    diffs = []
    worlds = defaultdict(list)
    seeds = defaultdict(list)
    for key, rs in epochs.items():
        if keep and not keep(key, rs):
            continue
        m = {r["method"]: r for r in rs}
        v = fn(m)
        diffs.append(v)
        worlds[(key[0], key[1])].append(v)
        seeds[key[0]].append(v)
    n = len(diffs)
    mean = st.mean(diffs)
    sd = st.stdev(diffs)
    se_naive = sd / math.sqrt(n)

    # cluster-robust SE of the mean (CR0) by world and by seed
    def crse(groups):
        g = len(groups)
        tot = sum((sum(v) - len(v) * mean) ** 2 for v in groups.values())
        return math.sqrt(tot) / n * math.sqrt(g / (g - 1))

    se_w = crse(worlds)
    se_s = crse(seeds)
    n80_1 = ((1.96 + 0.8416) * sd / 1.0) ** 2
    n80_15 = ((1.96 + 0.8416) * sd / 1.5) ** 2
    mde400 = (1.96 + 0.8416) * sd / math.sqrt(400) * (se_s / se_naive)
    print(
        f"{label}: n={n} mean={mean:+.2f} sd={sd:.2f} | 95%CI naive ±{1.96 * se_naive:.2f} "
        f"cluster(world) ±{1.96 * se_w:.2f} cluster(seed) ±{1.96 * se_s:.2f} | "
        f"deff(seed)={(se_s / se_naive) ** 2:.2f} | n for 80% power: d=1 → {n80_1:.0f}, d=1.5 → {n80_15:.0f} (naive) | "
        f"MDE80 at n=400 (seed-clustered) ≈ {mde400:.2f}"
    )
    return diffs


serious = ("Utility", "UCB", "Q-learning", "Opponent")
print("\n(2) paired contrasts, score")
contrast(lambda m: m["Lookahead"]["score"] - m["Opponent"]["score"], "LA-Opp")
contrast(
    lambda m: m["Lookahead"]["score"] - st.mean(m[o]["score"] for o in serious),
    "LA-4serious",
)
contrast(
    lambda m: m["Lookahead"]["score"] - m["Opponent"]["score"],
    "LA-Opp epochs 2-4",
    keep=lambda k, rs: k[2] >= 2,
)
contrast(
    lambda m: m["Lookahead"]["score"] - m["Opponent"]["score"],
    "LA-Opp epoch 1",
    keep=lambda k, rs: k[2] == 1,
)
print("\n    contrasts on agent-time-free metrics")
contrast(
    lambda m: (
        m["Lookahead"]["score"] / max(1, m["Lookahead"]["dec"]) * 1000
        - m["Opponent"]["score"] / max(1, m["Opponent"]["dec"]) * 1000
    ),
    "LA-Opp score per 1000 decisions",
)
contrast(
    lambda m: m["Lookahead"]["dec"] - m["Opponent"]["dec"],
    "LA-Opp decisions (agent-time)",
)
contrast(lambda m: m["Lookahead"]["pop"] - m["Opponent"]["pop"], "LA-Opp pop_end")
contrast(lambda m: m["Lookahead"]["births"] - m["Opponent"]["births"], "LA-Opp births")
contrast(lambda m: m["Lookahead"]["losses"] - m["Opponent"]["losses"], "LA-Opp losses")

# (3) learning ON/OFF pairs on same seed: correlation of epoch-level LA-Opp
pair = defaultdict(dict)
for key, rs in epochs.items():
    m = {r["method"]: r for r in rs}
    pair[(key[0], key[2])][key[1]] = m["Lookahead"]["score"] - m["Opponent"]["score"]
on = [v[True] for v in pair.values() if True in v and False in v]
off = [v[False] for v in pair.values() if True in v and False in v]
print(
    f"\n(3) LA-Opp, learning ON vs OFF same seed+epoch: r={ols(on, off)[2]:+.3f} (n={len(on)})"
)
# same for epoch 1 only: are the ON/OFF worlds still identical early?
on1 = [v[True] for k, v in pair.items() if k[1] == 1 and True in v and False in v]
off1 = [v[False] for k, v in pair.items() if k[1] == 1 and True in v and False in v]
print(f"    epoch 1 only: r={ols(on1, off1)[2]:+.3f} (n={len(on1)})")
# within-world serial correlation of LA-Opp across epochs
w = defaultdict(dict)
for key, rs in epochs.items():
    m = {r["method"]: r for r in rs}
    w[(key[0], key[1])][key[2]] = m["Lookahead"]["score"] - m["Opponent"]["score"]
a1 = [v[e] for v in w.values() for e in (1, 2, 3) if e in v and e + 1 in v]
a2 = [v[e + 1] for v in w.values() for e in (1, 2, 3) if e in v and e + 1 in v]
print(
    f"    lag-1 within-world correlation of LA-Opp across epochs: r={ols(a1, a2)[2]:+.3f}"
)

# (4) positional confound: LA score minus epoch mean, by faction id and by epoch
pos = defaultdict(list)
epo = defaultdict(list)
fac_all = defaultdict(list)
for key, rs in epochs.items():
    ms = st.mean(r["score"] for r in rs)
    for r in rs:
        fac_all[r["fid"]].append(r["score"] - ms)
        if r["method"] == "Lookahead":
            pos[r["fid"]].append(r["score"] - ms)
            epo[key[2]].append(r["score"] - ms)
print(
    "\n(4) LA score - epoch mean, by faction id:",
    {k: (len(v), round(st.mean(v), 2)) for k, v in sorted(pos.items())},
)
print(
    "    LA score - epoch mean, by epoch:",
    {k: (len(v), round(st.mean(v), 2)) for k, v in sorted(epo.items())},
)
print(
    "    ALL methods: faction-id effect (score - epoch mean):",
    {k: round(st.mean(v), 2) for k, v in sorted(fac_all.items())},
)
fa2 = defaultdict(list)
for key, rs in epochs.items():
    if key[2] < 2:
        continue
    ms = st.mean(r["score"] for r in rs)
    for r in rs:
        fa2[r["fid"]].append(r["score"] - ms)
print(
    "    ALL methods, epochs 2-4 (inherited genes): faction-id effect:",
    {k: round(st.mean(v), 2) for k, v in sorted(fa2.items())},
)
