"""Aggregate per-method outcomes over all epochs of the headless comparison runs (methods rotate across factions per epoch)."""

import glob
import json
import math
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
files = sorted(glob.glob(str(Path(sys.argv[1]) / "cmp_seed*.json")))
rows = []  # one row per (file, run, epoch, faction)
for f in files:
    d = json.loads(Path(f).read_text(encoding="utf-8"))
    for run in d["runs"]:
        snaps = list(run["world"]["episodes"]) + [run["summary"]]
        for ep_index, snap in enumerate(snaps, 1):
            pops = snap.get("populations") or [None] * 6
            scores = [fa["score"] for fa in snap["factions"]]
            best = max(scores)
            for fa in snap["factions"]:
                rows.append(
                    {
                        "seed": run["seed"],
                        "learning": run["learning"],
                        "epoch": ep_index,
                        "closed": ep_index < len(snaps),
                        "method": fa["method"],
                        "score": fa["score"],
                        "births": fa["births"],
                        "kills": fa["kills"],
                        "losses": fa["losses"],
                        "decisions": fa["decisions"],
                        "pop": pops[fa["id"]],
                        "top": abs(fa["score"] - best) <= 1e-9,
                        "rank": 1 + sum(s > fa["score"] + 1e-9 for s in scores),
                    }
                )
print(
    "files",
    len(files),
    "| rows",
    len(rows),
    "| epochs",
    len({(r["seed"], r["learning"], r["epoch"]) for r in rows}),
)


def table(subset, label):
    by = defaultdict(list)
    for r in subset:
        by[r["method"]].append(r)
    print(
        f"\n== {label}: {len({(r['seed'], r['learning'], r['epoch']) for r in subset})} epochs =="
    )
    print(
        f"{'method':11} {'n':>4} {'score mean':>10} {'median':>8} {'top1 %':>7} {'rank':>5} {'births':>7} {'kills':>6} {'losses':>7} {'pop end':>8} {'decis':>7}"
    )
    for m, rs in sorted(by.items(), key=lambda kv: -st.mean(r["score"] for r in kv[1])):
        n = len(rs)
        print(
            f"{m:11} {n:4} {st.mean(r['score'] for r in rs):10.2f} {st.median(r['score'] for r in rs):8.2f} "
            f"{100 * sum(r['top'] for r in rs) / n:6.1f}% {st.mean(r['rank'] for r in rs):5.2f} "
            f"{st.mean(r['births'] for r in rs):7.2f} {st.mean(r['kills'] for r in rs):6.2f} {st.mean(r['losses'] for r in rs):7.2f} "
            f"{st.mean(r['pop'] for r in rs if r['pop'] is not None):8.2f} {st.mean(r['decisions'] for r in rs):7.0f}"
        )


closed = [r for r in rows if r["closed"]]
table(closed, "closed epochs, all runs")
table([r for r in closed if r["learning"]], "closed epochs, learning ON")
table(
    [r for r in closed if not r["learning"]],
    "closed epochs, learning OFF (Q/UCB ablated)",
)

# Paired per-epoch: Lookahead score minus mean of the other five methods in the same epoch.
diffs = []
by_epoch = defaultdict(list)
for r in closed:
    by_epoch[(r["seed"], r["learning"], r["epoch"])].append(r)
for key, rs in by_epoch.items():
    la = [r for r in rs if r["method"] == "Lookahead"]
    ot = [r for r in rs if r["method"] != "Lookahead"]
    if la and ot:
        diffs.append(la[0]["score"] - st.mean(r["score"] for r in ot))
n = len(diffs)
mean = st.mean(diffs)
se = st.stdev(diffs) / math.sqrt(n) if n > 1 else float("nan")
wins = sum(dd > 0 for dd in diffs)
print(
    f"\nPaired per epoch (n={n}): Lookahead - others mean = {mean:+.2f} ± {1.96 * se:.2f} (95% CI) | epochs where Lookahead > others: {wins}/{n} = {100 * wins / n:.0f}%"
)
# Sign test against 50%: normal approximation
z = (wins - n / 2) / math.sqrt(n / 4)
print(f"sign test z = {z:+.2f} (|z|>1.96 ≈ p<0.05)")
top = sum(r["top"] for r in closed if r["method"] == "Lookahead")
tot = sum(1 for r in closed if r["method"] == "Lookahead")
print(
    f"Lookahead ranks first in {top}/{tot} epochs = {100 * top / tot:.0f}% (chance 16.7%)"
)
