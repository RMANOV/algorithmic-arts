"""Quick cuts (read-only): LA-Opp per epoch index, level per epoch from timeline, clustered extinction contrast,
births/losses/end-pop identity, epochs 2-4 sample sizes."""

import glob
import json
import math
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
files = sorted(glob.glob(str(Path(sys.argv[1]) / "cmp_seed*.json")))
epochs = defaultdict(dict)
levels = defaultdict(list)
for fpath in files:
    d = json.loads(Path(fpath).read_text(encoding="utf-8"))
    for run in d["runs"]:
        w = run["world"]
        for t in w["timeline"]:
            (
                levels[t["episode"]].append((t["tick"], t["level"]))
                if "level" in t and "episode" in t
                else None
            )
        snaps = list(w["episodes"]) + [run["summary"]]
        for ep, snap in enumerate(snaps[:-1], 1):
            pops = snap["populations"]
            for fa in snap["factions"]:
                epochs[(run["seed"], run["learning"], ep)][fa["method"]] = dict(
                    score=fa["score"],
                    losses=fa["losses"],
                    births=fa["births"],
                    pop=pops[fa["id"]],
                )


def summarize(label, vals_by_key):
    keys = list(vals_by_key)
    v = [vals_by_key[k] for k in keys]
    n = len(v)
    mean = st.mean(v)
    sd = st.stdev(v)
    g = defaultdict(list)
    for k in keys:
        g[(k[0], k[1])].append(vals_by_key[k])
    G = len(g)
    se_w = (
        math.sqrt(sum((sum(x) - len(x) * mean) ** 2 for x in g.values()))
        / n
        * math.sqrt(G / (G - 1))
    )
    print(
        f"{label}: n={n} mean={mean:+.3f} sd={sd:.2f} naive ±{1.96 * sd / math.sqrt(n):.3f} world-clustered ±{1.96 * se_w:.3f}"
    )


for e in (1, 2, 3, 4):
    summarize(
        f"LA-Opp score, epoch {e}",
        {
            k: m["Lookahead"]["score"] - m["Opponent"]["score"]
            for k, m in epochs.items()
            if k[2] == e
        },
    )
summarize(
    "LA-Opp extinct indicator (LA ext - Opp ext)",
    {
        k: float(m["Lookahead"]["pop"] == 0) - float(m["Opponent"]["pop"] == 0)
        for k, m in epochs.items()
    },
)
summarize(
    "LA-Opp extinct indicator, epochs 2-4",
    {
        k: float(m["Lookahead"]["pop"] == 0) - float(m["Opponent"]["pop"] == 0)
        for k, m in epochs.items()
        if k[2] >= 2
    },
)
summarize(
    "LA-Opp births",
    {k: m["Lookahead"]["births"] - m["Opponent"]["births"] for k, m in epochs.items()},
)
summarize(
    "LA-Opp losses",
    {k: m["Lookahead"]["losses"] - m["Opponent"]["losses"] for k, m in epochs.items()},
)
summarize(
    "LA-Opp (losses-births)",
    {
        k: (m["Lookahead"]["losses"] - m["Lookahead"]["births"])
        - (m["Opponent"]["losses"] - m["Opponent"]["births"])
        for k, m in epochs.items()
    },
)
ident = sum(
    m[x]["pop"] == 4 + m[x]["births"] - m[x]["losses"]
    for m in epochs.values()
    for x in m
)
print(
    f"identity end_pop == 4 + births - losses holds for {ident}/{sum(len(m) for m in epochs.values())} faction-epochs"
)
print("\nlevel at timeline entries by epoch (first entry = epoch start):")
for e in sorted(levels):
    lv = [l for _, l in levels[e]]
    starts = [l for (t, l) in levels[e]][:1]
    print(
        f"  epoch {e}: entries {len(lv)}, level min {min(lv)} max {max(lv)}, mean {st.mean(lv):.2f}"
    )
