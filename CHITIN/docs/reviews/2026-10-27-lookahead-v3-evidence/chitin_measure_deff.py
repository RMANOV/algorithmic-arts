"""Read-only: design effect by world for candidate outcomes; n per arm for delta=1 at 80% power (two-arm)."""

import glob, json, math, statistics as st, sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
out = defaultdict(lambda: defaultdict(list))
for f in sorted(glob.glob(str(Path(sys.argv[1]) / "cmp_seed*.json"))):
    d = json.loads(Path(f).read_text(encoding="utf-8"))
    for run in d["runs"]:
        w = (run["seed"], run["learning"])
        snaps = list(run["world"]["episodes"]) + [run["summary"]]
        for ep, snap in enumerate(snaps[:-1], 1):
            m = {fa["method"]: fa for fa in snap["factions"]}
            pops = snap["populations"]
            mean_all = st.mean(fa["score"] for fa in snap["factions"])
            out["LA score"][w].append(m["Lookahead"]["score"])
            out["LA - epoch mean(others)"][w].append(
                m["Lookahead"]["score"]
                - st.mean(
                    fa["score"]
                    for fa in snap["factions"]
                    if fa["method"] != "Lookahead"
                )
            )
            out["LA - Opp"][w].append(m["Lookahead"]["score"] - m["Opponent"]["score"])
            out["LA extinct (0/1)"][w].append(
                1.0 if pops[m["Lookahead"]["id"]] == 0 else 0.0
            )
for name, groups in out.items():
    vals = [v for g in groups.values() for v in g]
    n = len(vals)
    mean = st.mean(vals)
    sd = st.stdev(vals)
    g = len(groups)
    se_cl = (
        math.sqrt(sum((sum(v) - len(v) * mean) ** 2 for v in groups.values()))
        / n
        * math.sqrt(g / (g - 1))
    )
    deff = (se_cl / (sd / math.sqrt(n))) ** 2
    n_arm = (
        2 * ((1.96 + 0.8416) * sd) ** 2 * deff
    )  # delta = 1 point (or 1.0 for proportion -> scaled below)
    print(
        f"{name:26} mean {mean:+7.3f} sd {sd:6.3f} deff(world) {deff:4.2f} | two-arm n/arm for delta=1: {n_arm:7.0f} epochs "
        f"(~{n_arm / 4:5.0f} worlds) | MDE80 at 400/arm: {(1.96 + 0.8416) * sd * math.sqrt(2 * deff / 400):.2f}"
    )
