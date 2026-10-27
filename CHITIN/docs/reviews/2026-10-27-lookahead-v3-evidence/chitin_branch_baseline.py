"""Read-only baseline facts from existing cmp_seed*.json: BUILD share per method, long-lane error per horizon, planning energy."""

import glob
import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
files = sorted(glob.glob(str(Path(sys.argv[1]) / "cmp_seed*.json")))
actions = defaultdict(lambda: defaultdict(int))  # method -> action -> decisions
decisions = defaultdict(int)
long_err = defaultdict(list)  # horizon -> errors (last 120 outcomes per world only)
long_err_by_action = defaultdict(list)
mean_long = []
mean_short = []
interv = defaultdict(int)
evaluated_long = 0
registered_long = 0
for f in files:
    d = json.loads(Path(f).read_text(encoding="utf-8"))
    for run in d["runs"]:
        snaps = list(run["world"]["episodes"]) + [run["summary"]]
        for ep_index, snap in enumerate(snaps, 1):
            if ep_index >= len(snaps):
                continue
            for fa in snap["factions"]:
                for act, n in fa["actions"].items():
                    actions[fa["method"]][act] += n
                decisions[fa["method"]] += fa["decisions"]
        pred = run["summary"]["prediction"]
        mean_long.append(pred["mean_absolute_state_error"])
        mean_short.append(pred["validation_mean_state_error"])
        stats = run["summary"]["stats"]
        evaluated_long += stats.get("forecasts_evaluated", 0)
        registered_long += stats.get("forecasts_registered", 0)
        for o in pred["outcomes"]:
            if o["status"] != "evaluated":
                continue
            err = (
                o["health_error"]
                if o["energy_error"] is None
                else (o["health_error"] + o["energy_error"]) / 2
            )
            long_err[o["horizon"]].append(err)
            long_err_by_action[(o["horizon"], o["action"])].append(err)
            for i in o["interventions"]:
                interv[(o["horizon"], i)] += 1
            if not o["interventions"]:
                interv[(o["horizon"], "none")] += 1

print("== decision shares by method (closed epochs) ==")
for method, acts in sorted(actions.items()):
    tot = decisions[method]
    share = " ".join(
        f"{a}:{100 * n / tot:4.1f}%"
        for a, n in sorted(acts.items(), key=lambda kv: -kv[1])
    )
    print(f"{method:11} n={tot:6} {share}")
print(
    "\n== long lane (30/90/180) per-world mean error: mean",
    round(st.mean(mean_long), 3),
    "short lane:",
    round(st.mean(mean_short), 3),
)
print("registered long", registered_long, "evaluated long points", evaluated_long)
print("\n== long-lane error by horizon (last 120 outcomes per world, 60 worlds) ==")
for h in sorted(long_err):
    e = long_err[h]
    print(
        f"horizon {h:3}: n={len(e):5} mean={st.mean(e):6.2f} median={st.median(e):6.2f}"
    )
print("\n== interventions flagged on long outcomes (horizon, flag) ==")
for k in sorted(interv):
    print(k, interv[k])
print("\n== long error by (horizon, first action) ==")
for k in sorted(long_err_by_action):
    e = long_err_by_action[k]
    if len(e) >= 30:
        print(f"{k}: n={len(e):4} mean={st.mean(e):6.2f}")
