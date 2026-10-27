"""Read-only: within-epoch correlation LA vs Opponent / 4 serious; per-tick normalisation; early-closed epochs."""

import glob, json, math, statistics as st, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
la, op, s4, lat, opt, closed_early = [], [], [], [], [], []
for f in sorted(glob.glob(str(Path(sys.argv[1]) / "cmp_seed*.json"))):
    d = json.loads(Path(f).read_text(encoding="utf-8"))
    for run in d["runs"]:
        snaps = list(run["world"]["episodes"]) + [run["summary"]]
        for snap in snaps[:-1]:
            m = {fa["method"]: fa for fa in snap["factions"]}
            la.append(m["Lookahead"]["score"])
            op.append(m["Opponent"]["score"])
            s4.append(
                st.mean(
                    m[o]["score"] for o in ("Utility", "UCB", "Q-learning", "Opponent")
                )
            )
            T = snap["episode_tick"]
            lat.append(m["Lookahead"]["score"] / T * 1500)
            opt.append(m["Opponent"]["score"] / T * 1500)
            closed_early.append(T < 1500)


def corr(x, y):
    mx, my = st.mean(x), st.mean(y)
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / math.sqrt(
        sum((a - mx) ** 2 for a in x) * sum((b - my) ** 2 for b in y)
    )


print(
    f"sd LA {st.stdev(la):.2f}  sd Opp {st.stdev(op):.2f}  corr(LA,Opp) {corr(la, op):+.3f}  sd(LA-Opp) {st.stdev([a - b for a, b in zip(la, op)]):.2f}"
)
print(
    f"sd mean4 {st.stdev(s4):.2f}  corr(LA,mean4) {corr(la, s4):+.3f}  sd(LA-mean4) {st.stdev([a - b for a, b in zip(la, s4)]):.2f}"
)
d = [a - b for a, b in zip(lat, opt)]
print(
    f"per-1500-tick normalised LA-Opp: mean {st.mean(d):+.2f} sd {st.stdev(d):.2f} | early-closed epochs {sum(closed_early)}/{len(closed_early)}"
)
