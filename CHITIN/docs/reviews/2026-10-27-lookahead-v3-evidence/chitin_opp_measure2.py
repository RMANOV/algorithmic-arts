"""Follow-up checks (read-only): colour effect SE, spillover in epochs 3-4, LA vs Opp extinction McNemar,
sensitivity of alternative endpoints (losses, extinction, rank) for a +1 score-equivalent change."""

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
for fpath in files:
    d = json.loads(Path(fpath).read_text(encoding="utf-8"))
    for run in d["runs"]:
        snaps = list(run["world"]["episodes"]) + [run["summary"]]
        for ep, snap in enumerate(snaps[:-1], 1):
            pops = snap["populations"]
            for fa in snap["factions"]:
                epochs[(run["seed"], run["learning"], ep)][fa["method"]] = dict(
                    fid=fa["id"],
                    score=fa["score"],
                    losses=fa["losses"],
                    pop=pops[fa["id"]],
                    births=fa["births"],
                )
dm = {}
for k, m in epochs.items():
    mu = st.mean(v["score"] for v in m.values())
    for meth, v in m.items():
        dm[(k, meth)] = v["score"] - mu
# colour effects with SE, epochs 2-4
col = defaultdict(list)
for (k, meth), v in dm.items():
    if k[2] >= 2:
        col[epochs[k][meth]["fid"]].append(v)
print("colour effect (demeaned score), epochs 2-4, mean ± 95%:")
for fid, vs in sorted(col.items()):
    print(
        f"  fid {fid}: {st.mean(vs):+.2f} ± {1.96 * st.stdev(vs) / math.sqrt(len(vs)):.2f} (n={len(vs)})"
    )
# spillover restricted to epochs 3-4 (LA's previous colour is randomised, not always AZURE)
sp, oth = [], []
for k, m in epochs.items():
    if k[2] < 3:
        continue
    prev_fid = epochs[(k[0], k[1], k[2] - 1)]["Lookahead"]["fid"]
    for meth, v in m.items():
        if meth != "Lookahead":
            (sp if v["fid"] == prev_fid else oth).append(dm[(k, meth)])
print(
    f"spillover epochs 3-4: holder of LA previous colour {st.mean(sp):+.2f} ± {1.96 * st.stdev(sp) / math.sqrt(len(sp)):.2f} "
    f"(n={len(sp)}) vs others {st.mean(oth):+.2f} ± {1.96 * st.stdev(oth) / math.sqrt(len(oth)):.2f} (n={len(oth)})"
)
# extinction McNemar LA vs Opp
la_only = sum(
    m["Lookahead"]["pop"] == 0 and m["Opponent"]["pop"] > 0 for m in epochs.values()
)
op_only = sum(
    m["Lookahead"]["pop"] > 0 and m["Opponent"]["pop"] == 0 for m in epochs.values()
)
both = sum(
    m["Lookahead"]["pop"] == 0 and m["Opponent"]["pop"] == 0 for m in epochs.values()
)
print(
    f"extinction: LA-only {la_only}, Opp-only {op_only}, both {both}, McNemar z={(op_only - la_only) / math.sqrt(op_only + la_only):+.2f}"
)
# extinct LA epochs: score of LA when extinct vs when surviving
ext = [m["Lookahead"]["score"] for m in epochs.values() if m["Lookahead"]["pop"] == 0]
sur = [m["Lookahead"]["score"] for m in epochs.values() if m["Lookahead"]["pop"] > 0]
print(
    f"LA score when extinct {st.mean(ext):.2f} (n={len(ext)}) vs surviving {st.mean(sur):.2f} (n={len(sur)})"
)
# distribution of LA-Opp: share of variance from top/bottom 5%
d = sorted(m["Lookahead"]["score"] - m["Opponent"]["score"] for m in epochs.values())
n = len(d)
mu = st.mean(d)
tail = d[: n // 20] + d[-n // 20 :]
print(
    f"LA-Opp: min {d[0]:.1f} p5 {d[n // 20]:.1f} median {st.median(d):.1f} p95 {d[-n // 20]:.1f} max {d[-1]:.1f}; "
    f"top+bottom 5% carry {100 * sum((x - mu) ** 2 for x in tail) / sum((x - mu) ** 2 for x in d):.0f}% of the variance"
)
# rank of LA among six
ranks = []
for m in epochs.values():
    sc = sorted((v["score"] for v in m.values()), reverse=True)
    ranks.append(1 + sum(s > m["Lookahead"]["score"] + 1e-9 for s in sc))
print(f"LA mean rank {st.mean(ranks):.2f} sd {st.stdev(ranks):.2f} (n={len(ranks)})")
