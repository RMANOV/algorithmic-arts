"""Invariant checks for the branching prototype (review only, scratch copies)."""

import importlib.util
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ORIG = Path(r"C:\Users\rmanov\algorithmic-arts\CHITIN\battle_evolution.py")


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


A = load(ORIG, "chitin_A")
B0 = load(HERE / "b0" / "CHITIN" / "battle_evolution.py", "chitin_B0")
B3 = load(HERE / "b3" / "CHITIN" / "battle_evolution.py", "chitin_B3")


def strip(export):
    export["snapshot"]["stats"].pop("forecast_branches", None)
    for ep in export["episodes"]:
        ep["stats"].pop("forecast_branches", None)
    return export


def run(mod, seed, ticks, max_agents=60):
    w = mod.BattleWorld(seed=seed, max_agents=max_agents)
    for _ in range(ticks):
        w.step()
    return w


out = {}
# 1) Fidelity: BRANCH_BEAM=0 must equal today's model (except one new stats key).
for seed in (42, 101):
    a = run(A, seed, 1500).export()
    b = strip(run(B0, seed, 1500).export())
    out[f"fidelity_beam0_equals_A_seed{seed}"] = json.dumps(
        a, sort_keys=True
    ) == json.dumps(b, sort_keys=True)
# 2) Determinism with branching: same seed -> same export (selftest config).
w1 = B3.BattleWorld(seed=31, max_agents=60, episode_ticks=240)
w2 = B3.BattleWorld(seed=31, max_agents=60, episode_ticks=240)
for _ in range(520):
    w1.step()
    w2.step()
out["b3_deterministic_replay_520"] = w1.export() == w2.export()
# 3) Metal ledger and branch counters on longer runs.
for seed in (101, 202):
    w = run(B3, seed, 3000)
    look = sum(
        ep["factions"][i]["decisions"]
        for ep in list(w.episodes) + [w.snapshot()]
        for i in range(6)
        if ep["factions"][i]["method"] == "Lookahead"
    )
    out[f"b3_seed{seed}"] = {
        "ledger_error": w.last_ledger_error,
        "population": len(w.agents),
        "forecast_branches": w.stats["forecast_branches"],
        "lookahead_decisions": look,
        "branches_per_decision": round(w.stats["forecast_branches"] / max(1, look), 3),
        "forecast_rollouts": w.stats["forecast_rollouts"],
    }
# 4) Cost: wall time and planner time per call, same seeds, 3000 ticks.
for label, mod in (("A", A), ("B3", B3)):
    calls = {"n": 0, "t": 0.0, "traj": 0}
    orig_ps, orig_fl = mod.predictive_scores, mod._forecast_lifetime

    def fl(*args, **kw):
        calls["traj"] += 1
        return orig_fl(*args, **kw)

    def ps(*args, **kw):
        t0 = time.perf_counter()
        r = orig_ps(*args, **kw)
        calls["t"] += time.perf_counter() - t0
        calls["n"] += 1
        return r

    mod.predictive_scores, mod._forecast_lifetime = ps, fl
    rows = []
    for seed in (101, 202):
        calls.update(n=0, t=0.0, traj=0)
        w = mod.BattleWorld(seed=seed, max_agents=60)
        t0 = time.perf_counter()
        for _ in range(3000):
            w.step()
        wall = time.perf_counter() - t0
        rows.append(
            {
                "seed": seed,
                "ticks_per_s": round(3000 / wall, 1),
                "planner_share": round(calls["t"] / wall, 3),
                "ms_per_call": round(calls["t"] / max(1, calls["n"]) * 1000, 3),
                "calls_per_tick": round(calls["n"] / 3000, 3),
                "traj_per_call": round(calls["traj"] / max(1, calls["n"]), 2),
            }
        )
    mod.predictive_scores, mod._forecast_lifetime = orig_ps, orig_fl
    out[f"cost_{label}"] = rows
print(json.dumps(out, indent=1))
