"""Paired Lookahead checks: vs 4 serious methods, vs Opponent, by epoch index; Opponent gate rate. Read-only."""

import glob
import json
import math
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
files = sorted(glob.glob(str(Path(sys.argv[1]) / "cmp_seed*.json")))
by_epoch = defaultdict(dict)
opp_dec = 0
opp_pred = 0
la_dec_closed = 0
for f in files:
    d = json.loads(Path(f).read_text(encoding="utf-8"))
    for run in d["runs"]:
        snaps = list(run["world"]["episodes"]) + [run["summary"]]
        opp_pred += run["summary"]["stats"].get("opponent_predictions", 0)
        for ep_index, snap in enumerate(snaps, 1):
            for fa in snap["factions"]:
                if fa["method"] == "Opponent":
                    opp_dec += fa["decisions"]
                if ep_index < len(snaps):
                    by_epoch[(run["seed"], run["learning"], ep_index)][fa["method"]] = (
                        fa["score"]
                    )


def paired(others, label, epochs=None):
    diffs = []
    for key, m in by_epoch.items():
        if epochs and key[2] not in epochs:
            continue
        diffs.append(m["Lookahead"] - st.mean(m[o] for o in others))
    n = len(diffs)
    mean = st.mean(diffs)
    se = st.stdev(diffs) / math.sqrt(n)
    wins = sum(x > 0 for x in diffs)
    print(
        f"{label}: n={n} mean={mean:+.2f} ±{1.96 * se:.2f} wins={100 * wins / n:.0f}%"
    )


paired(("Utility", "UCB", "Q-learning", "Opponent"), "LA vs 4 serious")
paired(("Opponent",), "LA vs Opponent")
paired(("UCB",), "LA vs UCB")
paired(
    ("Utility", "UCB", "Q-learning", "Opponent"),
    "LA vs 4 serious, epochs 4+",
    epochs={4, 5, 6, 7},
)
paired(
    ("Utility", "UCB", "Q-learning", "Opponent", "Reflex"),
    "LA vs all 5 (aggregate_methods.py definition)",
)
print(
    f"Opponent decisions (all snaps) {opp_dec}, opponent_predictions {opp_pred}, gate pass {100 * opp_pred / opp_dec:.1f}%"
)
print("epoch index distribution:", sorted({k[2] for k in by_epoch}))
