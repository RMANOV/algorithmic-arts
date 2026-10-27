"""Value/risk lens: is arm A (Opponent with closed gate == Utility) already answered by existing data? Read-only."""

import glob
import json
import math
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
files = sorted(glob.glob(str(Path(sys.argv[1]) / "cmp_seed*.json")))
rows = []  # (seed, learning, epoch, {method: score})
for f in files:
    d = json.loads(Path(f).read_text(encoding="utf-8"))
    for run in d["runs"]:
        snaps = list(run["world"]["episodes"]) + [run["summary"]]
        for ep, snap in enumerate(snaps[:-1], 1):
            rows.append(
                (
                    run["seed"],
                    run["learning"],
                    ep,
                    {fa["method"]: fa["score"] for fa in snap["factions"]},
                )
            )


def paired(a, b, sel, label):
    v = [m[a] - m[b] for (s, l, e, m) in rows if sel(e)]
    n = len(v)
    mu = st.mean(v)
    h = 1.96 * st.stdev(v) / math.sqrt(n)
    # seed-cluster robust: mean of per-seed means
    g = defaultdict(list)
    for s, l, e, m in rows:
        if sel(e):
            g[s].append(m[a] - m[b])
    cm = [st.mean(x) for x in g.values()]
    hs = 1.96 * st.stdev(cm) / math.sqrt(len(cm))
    wins = sum(x > 0 for x in v) / n
    print(
        f"{label:<34} n={n:3d} mean {mu:+.2f} ±{h:.2f} | by seed (G={len(cm)}) ±{hs:.2f} | wins {100 * wins:.0f}%"
    )


for sel, tag in ((lambda e: e >= 2, "epochs>=2"), (lambda e: True, "all closed")):
    print(f"== {tag}")
    paired("Opponent", "Utility", sel, "Opponent - Utility (=arm A effect)")
    paired("Lookahead", "Utility", sel, "Lookahead - Utility (whole planner)")
    paired("Lookahead", "Opponent", sel, "Lookahead - Opponent")
    paired("Q-learning", "Utility", sel, "Q-learning - Utility")
