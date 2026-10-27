"""Read-only: action mix (argmax of pooled enemy decisions), paired LA-Opp sd by epoch index, power, ticks/s."""

import glob
import json
import math
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
files = sorted(glob.glob(str(Path(sys.argv[1]) / "cmp_seed*.json")))
actions_all = Counter()
actions_by_method = defaultdict(Counter)
by_epoch = defaultdict(dict)
tps = []
la_opp_adjacent = 0
births = defaultdict(list)
losses = defaultdict(list)
kills = defaultdict(list)
for f in files:
    d = json.loads(Path(f).read_text(encoding="utf-8"))
    for run in d["runs"]:
        tps.append(run["ticks_per_second"])
        snaps = list(run["world"]["episodes"]) + [run["summary"]]
        for ep_index, snap in enumerate(snaps, 1):
            closed = ep_index < len(snaps)
            for fa in snap["factions"]:
                actions_all.update(fa["actions"])
                actions_by_method[fa["method"]].update(fa["actions"])
                if closed:
                    by_epoch[(run["seed"], run["learning"], ep_index)][fa["method"]] = (
                        fa["score"]
                    )
                    births[fa["method"]].append(fa["births"])
                    losses[fa["method"]].append(fa["losses"])
                    kills[fa["method"]].append(fa["kills"])
tot = sum(actions_all.values())
print(
    "pooled action mix (all methods, all epochs):",
    {k: f"{100 * v / tot:.1f}%" for k, v in actions_all.most_common()},
)
for m, c in actions_by_method.items():
    t = sum(c.values())
    print(f"  {m:10}", {k: f"{100 * v / t:.0f}%" for k, v in c.most_common(4)})
print(
    "ticks/s per world: min %.0f median %.0f max %.0f"
    % (min(tps), st.median(tps), max(tps))
)


def paired(epochs, label):
    diffs = [
        m["Lookahead"] - m["Opponent"] for k, m in by_epoch.items() if k[2] in epochs
    ]
    n = len(diffs)
    sd = st.stdev(diffs)
    se = sd / math.sqrt(n)
    wins = sum(x > 0 for x in diffs)
    print(
        f"{label}: n={n} LA-Opp mean={st.mean(diffs):+.2f} sd={sd:.1f} ci95=±{1.96 * se:.2f} wins={100 * wins / n:.0f}%"
    )
    return sd


sd_all = paired({1, 2, 3, 4}, "all closed epochs")
sd_1 = paired({1}, "epoch 1 only (fixed order, LA id5 / Opp id4 neighbours)")
sd_24 = paired({2, 3, 4}, "epochs 2-4 (shuffled)")
for delta in (1.0, 1.5, 2.0):
    n80 = 7.85 * (sd_24 / delta) ** 2
    print(
        f"power 80% two-sided alpha .05 to detect delta={delta}: n≈{n80:.0f} closed epochs (2-4) ≈ {n80 / 3:.0f} worlds ≈ {n80 / 3 / 2:.0f} seeds with --compare-learning"
    )
for m in ("Lookahead", "Opponent"):
    print(
        m,
        "births %.2f losses %.2f kills %.2f"
        % (st.mean(births[m]), st.mean(losses[m]), st.mean(kills[m])),
    )
