"""Read-only: which part of each run do the exported long-lane outcomes (deque 120) come from?"""

import glob, json, statistics as st, sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
status = Counter()
made = []
ep_of = Counter()
per_world_eval180 = []
ticks = []
for f in sorted(glob.glob(str(Path(sys.argv[1]) / "cmp_seed*.json"))):
    d = json.loads(Path(f).read_text(encoding="utf-8"))
    for run in d["runs"]:
        pred = run["summary"]["prediction"]
        T = run["summary"]["tick"]
        ticks.append(T)
        n180 = 0
        for o in pred["outcomes"]:
            status[(o["status"], o.get("reason"))] += 1
            if o["status"] == "evaluated":
                made.append(T - o["made_at"])
                ep_of[o["context"][3]] += 1
                if o["horizon"] == 180 and o["action"] in ("ATTACK", "FLANK"):
                    n180 += 1
        per_world_eval180.append(n180)
print("final tick", min(ticks), max(ticks))
print("status", dict(status))
made.sort()
print(
    "evaluated outcomes: run_end - made_at  median",
    made[len(made) // 2],
    " p90",
    made[int(0.9 * len(made))],
    " max",
    made[-1],
)
print("epoch index of evaluated exported outcomes", dict(ep_of))
print(
    "ATTACK/FLANK 180-tick evaluated per world: total",
    sum(per_world_eval180),
    " median",
    st.median(per_world_eval180),
)
