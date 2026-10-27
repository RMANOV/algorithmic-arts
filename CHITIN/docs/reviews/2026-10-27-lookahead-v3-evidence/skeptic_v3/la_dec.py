"""Skeptic check: LA decisions per epoch, ledger_error carriers, early-closed epochs. Read-only over cmp_seed*.json."""

import glob
import json
import sys
from pathlib import Path

files = sorted(glob.glob(str(Path(sys.argv[1]) / "cmp_seed*.json")))
tot = closed = e24 = n_closed = n24 = early = 0
led_final, led_ep, ticks_closed = [], [], []
first_keys = None
for f in files:
    d = json.loads(Path(f).read_text(encoding="utf-8"))
    for run in d["runs"]:
        snaps = list(run["world"]["episodes"]) + [run["summary"]]
        if first_keys is None:
            first_keys = sorted(run["world"]["episodes"][0].keys())
        led_final.append(abs(run["summary"].get("ledger_error", 0.0)))
        for i, s in enumerate(snaps, 1):
            la = [fa for fa in s["factions"] if fa["method"] == "Lookahead"][0]
            tot += la["decisions"]
            if "ledger_error" in s:
                led_ep.append(abs(s["ledger_error"]))
            if i < len(snaps):
                closed += la["decisions"]
                n_closed += 1
                et = s.get("episode_tick")
                ticks_closed.append(et)
                if et is not None and et < 1500:
                    early += 1
                if i >= 2:
                    e24 += la["decisions"]
                    n24 += 1
print(
    "LA decisions total",
    tot,
    "| closed",
    closed,
    "| per closed epoch",
    round(closed / n_closed, 1),
    "| ep2-4 per epoch",
    round(e24 / n24, 1),
    "| n24",
    n24,
)
print(
    "max |ledger_error| final summaries",
    max(led_final),
    "| all snaps",
    max(led_ep),
    "count",
    len(led_ep),
)
print(
    "closed epochs",
    n_closed,
    "| early (<1500)",
    early,
    "| min episode_tick",
    min(t for t in ticks_closed if t is not None),
)
print("episode snapshot keys", first_keys)
