"""Which continuation leaks nearest-enemy motion into the RAID score (review probe)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(sys.argv[1]) / "tests"))
import test_chitin_raid as t

m = t.chitin
case = t.RaidIdentityTests()
for velocity in ((0.0, 0.0), (0.2, 0.0), (-0.2, 0.0), (0.0, 0.2)):
    world, actor, nearest, richest, sensed = case.scenario(velocity)
    util = world._utility(actor, sensed)
    scores, _, fc = m.predictive_scores(world, actor, sensed, util)
    elig = [m.ACTIONS[i] for i in world.eligible_indices(actor, sensed)]
    print(
        velocity,
        "RAID score",
        repr(scores[6]),
        "continuations",
        fc.get("continuations"),
        "eligible",
        elig,
        "util",
        [round(u, 3) for u in util],
    )
