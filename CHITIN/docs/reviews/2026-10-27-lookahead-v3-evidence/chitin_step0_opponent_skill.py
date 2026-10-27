"""Step 0 probe (read-only): does the faction's observed opponent histogram predict the nearest enemy's behaviour?

At every decision of every agent we record, for the deciding faction: gate state (Opponent rule 466),
argmax, aggressive/chase/shield mass. Skill is measured two ways:
  (1) next observed decision of the same enemy by the same faction: persistence (current action) vs argmax;
  (2) 60-tick realized share of combat-capable ticks (ATTACK/FLANK/RAID/GUARD/ESCORT, the set that may call _fight
      in step() 928) of the nearest enemy vs persistence indicator vs histogram mass p_aggr (gated), MAE.
Nothing in the model is modified; the world is driven only through public step()."""

import importlib.util
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

SOURCE = Path(r"C:\Users\rmanov\algorithmic-arts\CHITIN\battle_evolution.py")
spec = importlib.util.spec_from_file_location("chitin_probe", SOURCE)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)
A = m.ACTIONS
CHASE = {"ATTACK", "FLANK", "RAID"}
SHIELD = {"GUARD", "ESCORT"}
COMBAT = CHASE | SHIELD

seeds = [int(x) for x in sys.argv[1:]] or [101]
ticks = 6000
agg = Counter()
horizon_rows = []  # (method, gated, realized_share, persist_ind, p_aggr, p_chase)
per_method_gate = defaultdict(Counter)
argmax_hist = defaultdict(Counter)

for seed in seeds:
    w = m.BattleWorld(seed=seed, max_agents=60, episode_ticks=1500, learning=True)
    last_seen = {}  # (faction, enemy uid) -> (decision_id, action, argmax, gated)
    action_log = defaultdict(dict)  # uid -> {tick: action}
    pending = []  # (tick, method, gated, enemy uid, persist_ind, p_aggr, p_chase)
    orig = m.BattleWorld._choose

    def choose(self, a, s):
        f = self.factions[a.faction]
        total = sum(f.opponent)
        observed = total - 8
        conc = max(f.opponent) / total
        gated = observed >= 16 and conc > 0.25
        amax = A[max(range(8), key=lambda i: f.opponent[i])]
        p_chase = sum(f.opponent[i] for i in (2, 5, 6)) / total
        p_shield = (f.opponent[4] + f.opponent[7]) / total
        per_method_gate[f.method]["n"] += 1
        per_method_gate[f.method]["gated"] += gated
        if gated:
            argmax_hist[f.method][amax] += 1
        for e in s["enemies"]:
            key = (a.faction, e.uid)
            prev = last_seen.get(key)
            if e.decision_id and (prev is None or prev[0] != e.decision_id):
                if prev is not None:
                    tag = "LA" if f.method == "Lookahead" else "all"
                    for t in (tag, "all") if tag == "LA" else ("all",):
                        agg[t + "_n"] += 1
                        agg[t + "_persist"] += e.action == prev[1]
                        agg[t + "_argmax"] += e.action == prev[2]
                        agg[t + "_mine"] += e.action == "MINE"
                        agg[t + "_combat_persist"] += (e.action in COMBAT) == (
                            prev[1] in COMBAT
                        )
                        agg[t + "_combat_argmax"] += (e.action in COMBAT) == (
                            prev[2] in COMBAT
                        )
                        if prev[3]:
                            agg[t + "_g_n"] += 1
                            agg[t + "_g_persist"] += e.action == prev[1]
                            agg[t + "_g_argmax"] += e.action == prev[2]
                            agg[t + "_g_combat_persist"] += (e.action in COMBAT) == (
                                prev[1] in COMBAT
                            )
                            agg[t + "_g_combat_argmax"] += (e.action in COMBAT) == (
                                prev[2] in COMBAT
                            )
                last_seen[key] = (e.decision_id, e.action, amax, gated)
        enemy = s.get("enemy")
        if enemy is not None:
            pending.append(
                (
                    self.tick,
                    f.method,
                    gated,
                    enemy.uid,
                    float(enemy.action in COMBAT),
                    p_chase + p_shield,
                    p_chase,
                    float(enemy.action in CHASE),
                )
            )
        return orig(self, a, s)

    m.BattleWorld._choose = choose
    try:
        for _ in range(ticks):
            w.step()
            for a in w.agents:
                action_log[a.uid][w.tick] = a.action
    finally:
        m.BattleWorld._choose = orig
    for t, method, gated, uid, persist_ind, p_aggr, p_chase, chase_ind in pending:
        log = action_log.get(uid, {})
        window = [log[k] for k in range(t + 1, t + 61) if k in log]
        if len(window) < 30:
            continue  # enemy died early; skip (survivorship noted)
        realized = sum(x in COMBAT for x in window) / len(window)
        realized_chase = sum(x in CHASE for x in window) / len(window)
        horizon_rows.append(
            (
                method,
                gated,
                realized,
                persist_ind,
                p_aggr,
                p_chase,
                chase_ind,
                realized_chase,
            )
        )
    print(
        f"seed {seed}: ticks {w.tick}, epoch {w.episode}, decisions {w.stats['decisions']}, "
        f"opponent_predictions {w.stats['opponent_predictions']}"
    )

print("\n== gate pass by deciding method ==")
for meth, c in sorted(per_method_gate.items()):
    print(
        f"{meth:11} n={c['n']:6} gated={100 * c['gated'] / c['n']:5.1f}%  argmax under gate: "
        + ", ".join(
            f"{k}:{100 * v / max(1, c['gated']):.0f}%"
            for k, v in argmax_hist[meth].most_common(4)
        )
    )

print("\n== next observed decision of the same enemy (same observing faction) ==")
for t in ("LA", "all"):
    n = agg[t + "_n"]
    g = agg[t + "_g_n"]
    if not n:
        continue
    print(
        f"[{t}] n={n}: persistence {100 * agg[t + '_persist'] / n:.1f}% | argmax {100 * agg[t + '_argmax'] / n:.1f}% "
        f"| always-MINE {100 * agg[t + '_mine'] / n:.1f}% | combat-class: persist {100 * agg[t + '_combat_persist'] / n:.1f}% "
        f"argmax {100 * agg[t + '_combat_argmax'] / n:.1f}%"
    )
    if g:
        print(
            f"[{t}] gated only n={g}: persistence {100 * agg[t + '_g_persist'] / g:.1f}% | argmax {100 * agg[t + '_g_argmax'] / g:.1f}% "
            f"| combat-class: persist {100 * agg[t + '_g_combat_persist'] / g:.1f}% argmax {100 * agg[t + '_g_combat_argmax'] / g:.1f}%"
        )

print(
    "\n== 60-tick realized combat-capable share of the nearest enemy (MAE of predictors) =="
)
for label, rows in (
    ("Lookahead decisions", [r for r in horizon_rows if r[0] == "Lookahead"]),
    ("all decisions", horizon_rows),
):
    for gate_label, sub in (
        ("gated", [r for r in rows if r[1]]),
        ("ungated", [r for r in rows if not r[1]]),
    ):
        if len(sub) < 20:
            continue
        realized = [r[2] for r in sub]
        mae_persist = st.mean(abs(r[2] - r[3]) for r in sub)
        mae_hist = st.mean(abs(r[2] - r[4]) for r in sub)
        mae_const = st.mean(abs(r[2] - st.mean(realized)) for r in sub)
        mae_blend = st.mean(abs(r[2] - (0.5 * r[3] + 0.5 * r[4])) for r in sub)
        mae_chase_persist = st.mean(abs(r[7] - r[6]) for r in sub)
        mae_chase_hist = st.mean(abs(r[7] - r[5]) for r in sub)
        print(
            f"{label:20} {gate_label:8} n={len(sub):6} realized mean={st.mean(realized):.3f} | MAE persist={mae_persist:.3f} "
            f"hist p_aggr={mae_hist:.3f} blend={mae_blend:.3f} const={mae_const:.3f} | chase: persist={mae_chase_persist:.3f} hist={mae_chase_hist:.3f} "
            f"| mean p_aggr={st.mean(r[4] for r in sub):.3f} mean persist={st.mean(r[3] for r in sub):.3f}"
        )
