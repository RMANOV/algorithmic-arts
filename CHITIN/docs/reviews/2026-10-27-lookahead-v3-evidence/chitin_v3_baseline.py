"""V3 plan baseline: within-epoch contrasts with naive and seed-clustered 95% CI. Read-only over cmp_seed*.json."""

import glob
import json
import math
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
files = sorted(glob.glob(str(Path(sys.argv[1]) / "cmp_seed*.json")))
ep = defaultdict(dict)  # (seed, learning, epoch) -> method -> row
early = 0
for f in files:
    d = json.loads(Path(f).read_text(encoding="utf-8"))
    for run in d["runs"]:
        snaps = list(run["world"]["episodes"]) + [run["summary"]]
        for i, snap in enumerate(snaps, 1):
            if i >= len(snaps):
                continue  # open epoch
            pops = snap.get("populations") or [None] * 6
            for fa in snap["factions"]:
                ep[(run["seed"], run["learning"], i)][fa["method"]] = {
                    "score": fa["score"],
                    "births": fa["births"],
                    "losses": fa["losses"],
                    "pop": pops[fa["id"]],
                }


def stat(pairs, label):
    """pairs: list of (seed, value). Naive and seed-clustered CI of the mean."""
    vals = [v for _, v in pairs]
    n = len(vals)
    m = st.mean(vals)
    sd = st.stdev(vals)
    naive = 1.96 * sd / math.sqrt(n)
    g = defaultdict(float)
    for s, v in pairs:
        g[s] += v - m
    cl = 1.96 * math.sqrt(sum(x * x for x in g.values())) / n
    deff = (cl / naive) ** 2
    print(
        f"{label:34} n={n:4} mean={m:+7.2f} sd={sd:6.2f} naive±{naive:5.2f} seed±{cl:5.2f} deff={deff:4.2f}"
    )
    return sd, deff


def run(epochs, tag):
    keys = [
        k for k in ep if k[2] in epochs and "Lookahead" in ep[k] and "Opponent" in ep[k]
    ]
    print(f"--- {tag}: {len(keys)} epochs, {len({k[0] for k in keys})} seeds")
    four = ("Utility", "UCB", "Q-learning", "Opponent")
    stat([(k[0], ep[k]["Lookahead"]["score"]) for k in keys], "LA score (absolute)")
    stat(
        [
            (k[0], ep[k]["Lookahead"]["score"] - ep[k]["Opponent"]["score"])
            for k in keys
        ],
        "LA-Opp score",
    )
    stat(
        [(k[0], ep[k]["Lookahead"]["score"] - ep[k]["Utility"]["score"]) for k in keys],
        "LA-Utility score",
    )
    stat(
        [(k[0], ep[k]["Opponent"]["score"] - ep[k]["Utility"]["score"]) for k in keys],
        "Opp-Utility score",
    )
    stat(
        [
            (
                k[0],
                ep[k]["Lookahead"]["score"] - st.mean(ep[k][o]["score"] for o in four),
            )
            for k in keys
        ],
        "LA-4 serious score",
    )
    stat(
        [
            (k[0], ep[k]["Lookahead"]["births"] - ep[k]["Opponent"]["births"])
            for k in keys
        ],
        "LA-Opp births",
    )
    stat(
        [
            (k[0], ep[k]["Lookahead"]["losses"] - ep[k]["Opponent"]["losses"])
            for k in keys
        ],
        "LA-Opp losses",
    )
    stat(
        [(k[0], ep[k]["Lookahead"]["pop"] - ep[k]["Opponent"]["pop"]) for k in keys],
        "LA-Opp end population",
    )
    la0 = [ep[k]["Lookahead"]["pop"] == 0 for k in keys]
    op0 = [ep[k]["Opponent"]["pop"] == 0 for k in keys]
    b = sum(1 for x, y in zip(la0, op0) if x and not y)
    c = sum(1 for x, y in zip(la0, op0) if y and not x)
    z = (c - b) / math.sqrt(b + c) if b + c else float("nan")
    stat(
        [(k[0], float(x) - float(y)) for k, x, y in zip(keys, la0, op0)],
        "LA-Opp extinct share",
    )
    print(
        f"extinct LA {100 * sum(la0) / len(keys):.1f}% Opp {100 * sum(op0) / len(keys):.1f}% | only LA {b}, only Opp {c}, McNemar z={z:+.2f}"
    )
    top = sum(
        1
        for k in keys
        if ep[k]["Lookahead"]["score"] >= max(r["score"] for r in ep[k].values()) - 1e-9
    )
    print(f"LA first place {top}/{len(keys)} = {100 * top / len(keys):.1f}%")


run({1, 2, 3, 4}, "all closed epochs")
run({2, 3, 4}, "epochs 2-4 (methods shuffled, 184)")
for e in (1, 2, 3, 4):
    keys = [k for k in ep if k[2] == e]
    d = [ep[k]["Lookahead"]["score"] - ep[k]["Opponent"]["score"] for k in keys]
    print(
        f"epoch {e}: LA-Opp {st.mean(d):+.2f} ±{1.96 * st.stdev(d) / math.sqrt(len(d)):.2f} sd {st.stdev(d):.2f} n={len(d)}"
    )
