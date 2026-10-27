"""Skeptic check: the registered Stage-1 rule (z=2.394, wider of naive/seed-clustered SE) applied to dev epochs 2-4,
plus sd of LA absolute guards for G4 power. Read-only over cmp_seed*.json; mirrors chitin_v3_baseline.py rows."""

import glob
import json
import math
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

Z = 2.394
files = sorted(glob.glob(str(Path(sys.argv[1]) / "cmp_seed*.json")))
ep = defaultdict(dict)
for f in files:
    d = json.loads(Path(f).read_text(encoding="utf-8"))
    for run in d["runs"]:
        snaps = list(run["world"]["episodes"]) + [run["summary"]]
        for i, snap in enumerate(snaps, 1):
            if i >= len(snaps):
                continue
            pops = snap["populations"]
            for fa in snap["factions"]:
                ep[(run["seed"], run["learning"], i)][fa["method"]] = {
                    "score": fa["score"],
                    "losses": fa["losses"],
                    "pop": pops[fa["id"]],
                }


def ses(pairs):
    vals = [v for _, v in pairs]
    n = len(vals)
    m = st.mean(vals)
    sd = st.stdev(vals)
    naive = sd / math.sqrt(n)
    g = defaultdict(float)
    for s, v in pairs:
        g[s] += v - m
    cl = math.sqrt(sum(x * x for x in g.values())) / n
    return n, m, sd, naive, cl


keys = [k for k in ep if k[2] in (2, 3, 4)]
rule = {}
for name, fn in (
    (
        "P1 score LA-Utility",
        lambda k: ep[k]["Lookahead"]["score"] - ep[k]["Utility"]["score"],
    ),
    (
        "P2 pop LA-Utility",
        lambda k: ep[k]["Lookahead"]["pop"] - ep[k]["Utility"]["pop"],
    ),
    (
        "P3 extinct LA-Utility",
        lambda k: (
            float(ep[k]["Lookahead"]["pop"] == 0) - float(ep[k]["Utility"]["pop"] == 0)
        ),
    ),
):
    n, m, sd, naive, cl = ses([(k[0], fn(k)) for k in keys])
    wide = max(naive, cl)
    lo, hi = m - Z * wide, m + Z * wide
    rule[name] = (lo, hi)
    print(
        f"{name:24} n={n} mean={m:+.4f} naiveSE={naive:.4f} seedSE={cl:.4f} wider={'naive' if naive >= cl else 'seed'} "
        f"half={Z * wide:.4f} CI=[{lo:+.4f}; {hi:+.4f}]"
    )
trigger = (
    rule["P1 score LA-Utility"][1] < 0
    or rule["P2 pop LA-Utility"][1] < 0
    or rule["P3 extinct LA-Utility"][0] > 0
)
print("decision:", "TRIGGER" if trigger else "CLOSE")

for name, fn in (
    ("LA score abs", lambda k: ep[k]["Lookahead"]["score"]),
    ("LA losses abs", lambda k: ep[k]["Lookahead"]["losses"]),
    ("LA extinct abs", lambda k: float(ep[k]["Lookahead"]["pop"] == 0)),
    ("LA pop abs", lambda k: ep[k]["Lookahead"]["pop"]),
):
    n, m, sd, naive, cl = ses([(k[0], fn(k)) for k in keys])
    print(f"{name:16} mean={m:+.4f} sd={sd:.4f} deff={(cl / naive) ** 2:.2f}")
