"""Read-only SHADOW probe of the proposed two-stage Lookahead branch (scratchpad only, zero product change).

PRE-DECLARED before the first run (27.10, value/risk review):
  (a) decision change on the SAME state: branched argmax vs fixed argmax (A mode: the world acts on today's
      fixed scores, so the trajectory equals main @ 7162820) -> rate, from/to, share of today's RETREAT vetoes undone.
  (b) defect at line 1502: continuations into ATTACK/FLANK/RAID evaluated with the first action's enemy dropped
      (contact_i > 180) although that continuation alone has an enemy with contact_j <= 180 -> combat silently lost.
  (c) policy consistency: when the branched best for the ACTUALLY chosen action is a switch i->j, does the agent's
      next real decision pick j?  Control: when the best is the fixed history, does it keep i?
  (d) ATTACK/FLANK/RAID-first switch rescues with contact_i > 12 and zero combat after the switch.
  Refutation bars: (c) hit < 50%, or (b) > 5% of attack continuations -> mechanism refuted, not only the axiom.
  Falsifier of the erosion claim: branched flips >= 7.5% of 2+-eligible decisions AND RETREAT share of flips >= 40%.
Faithfulness: A-mode patched export == unpatched export (same seed); fixed flips reproduce chitin_branch_flips.py.
"""

import ctypes
import hashlib
import importlib.util
import json
import math
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
try:
    ctypes.windll.kernel32.SetPriorityClass(
        ctypes.windll.kernel32.GetCurrentProcess(), 0x00004000
    )
except Exception:
    pass

SOURCE = Path(r"C:\Users\rmanov\algorithmic-arts\CHITIN\battle_evolution.py")
spec = importlib.util.spec_from_file_location("chitin_shadow", SOURCE)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)
ACTIONS = m.ACTIONS
clamp = m.clamp
BRANCH_TICK, BRANCH_BEAM, BRANCH_CONT = 12, 3, 2
ATTACKS = ("ATTACK", "FLANK", "RAID")
C = Counter()
MODE = "A"
SHADOW = {}
PENDING = {}


def lifetime(
    a,
    enemy,
    action,
    food_path,
    distance,
    speed,
    contact,
    reaction,
    own_rate,
    enemy_rate,
    ore_available=0.0,
    switch=None,
):
    horizons = (30, 90, 180)
    short = (1, 8, 9, 10, 11, 12)
    enemy = enemy if enemy is not None and contact <= horizons[-1] else None
    health = [max(0.0, a.health), max(0.0, enemy.health) if enemy else 0.0]
    energy = [max(0.0, a.energy), max(0.0, enemy.energy) if enemy else 0.0]
    hunters = (a.trophic == "hunter", bool(enemy and enemy.trophic == "hunter"))
    actions = (action, enemy.action if enemy else "RETREAT")
    basal_costs = tuple(0.16 if hunter else 0.10 for hunter in hunters)
    intake_rates = tuple(
        0.22 if item in ("MINE", "GUARD") else 0.17 for item in actions
    )
    can_repair = tuple(item in ("MINE", "GUARD") for item in actions)
    rates = (own_rate, enemy_rate)
    totals = dict(
        ore=0.0,
        spent=0.0,
        dealt=0.0,
        received=0.0,
        stolen=0.0,
        enemy_stolen=0.0,
        kill=0.0,
        hunger_damage=0.0,
        construction=0.0,
    )
    remaining = max(0.0, distance)
    base_speed = speed / (0.65 if a.energy < 20 else 1.0)
    ore_limit = max(0.0, min(ore_available, 15.0 - a.metal))
    access = (
        clamp(food_path[30], 0.0, 1.0),
        clamp((90 * food_path[90] - 30 * food_path[30]) / 60, 0.0, 1.0),
        clamp((180 * food_path[180] - 90 * food_path[90]) / 90, 0.0, 1.0),
    )
    points, validation = {}, {}
    info = {
        "enemy_dropped": enemy is None,
        "switched": False,
        "combat_after_switch": False,
    }

    def spend(who, requested):
        paid = min(energy[who], max(0.0, requested))
        energy[who] -= paid
        if who == 0:
            totals["spent"] += paid
        return paid

    def state():
        return {
            **totals,
            "energy": energy[0] if health[0] > 0 else 0.0,
            "health": max(0.0, health[0]),
        }

    def metabolism(who, tick):
        if health[who] <= 0:
            return
        if not hunters[who]:
            food = access[0 if tick <= 30 else 1 if tick <= 90 else 2]
            intake = intake_rates[who] * food
            energy[who] += min(max(0.0, 100.0 - energy[who]), intake)
        paid = min(energy[who], basal_costs[who])
        energy[who] -= paid
        if who == 0:
            totals["spent"] += paid
        if energy[who] < 0.05:
            health[who] -= 0.22
            if who == 0:
                totals["hunger_damage"] += 0.22
        if 0 < health[who] < 70 and can_repair[who] and energy[who] > 15:
            repair = min(0.045, 70.0 - health[who])
            health[who] += repair
            spend(who, repair * 0.3)

    def strike(who):
        other = 1 - who
        if (
            health[who] <= 0
            or health[other] <= 0
            or rates[who] <= 0
            or energy[who] < 0.7
        ):
            return
        spend(who, 0.7 * 0.22)
        hit = min(health[other], rates[who])
        health[other] -= hit
        totals["dealt" if who == 0 else "received"] += hit
        if hunters[who]:
            taken = min(energy[other], hit * 0.9, max(0.0, (100.0 - energy[who]) / 0.8))
            energy[other] -= taken
            energy[who] += taken * 0.8
            totals["stolen" if who == 0 else "enemy_stolen"] += taken
        if who == 0 and health[other] <= 0:
            totals["kill"] = 1.0

    for tick in range(181):
        if tick:
            metabolism(0, tick)
            if health[1] > 0:
                metabolism(1, tick)
        if tick in short:
            validation[tick] = state()
        if health[0] > 0:
            if switch is not None and tick == switch[0]:
                # Proposal section 2, literally: rebind locals; keep an open combat window, else restart contact.
                _, action, distance2, speed2, contact2, reaction, own2, enemy2, ore2 = (
                    switch
                )
                remaining = max(0.0, distance2)
                base_speed = speed2 / (0.65 if a.energy < 20 else 1.0)
                rates = (own2, enemy2)
                ore_limit = max(0.0, min(ore2, 15.0 - a.metal))
                actions = (action, actions[1])
                intake_rates = tuple(
                    0.22 if item in ("MINE", "GUARD") else 0.17 for item in actions
                )
                can_repair = tuple(item in ("MINE", "GUARD") for item in actions)
                if not (contact <= tick < contact + 60):
                    contact = switch[0] + contact2
                info["switched"] = True
            if action == "BUILD" and tick == 0:
                paid = spend(0, 12.0)
                totals["construction"] = paid
                energy[0] *= 0.55
            elif action != "BUILD" and remaining >= 0.2:
                moved = min(remaining, base_speed * (0.65 if energy[0] < 20 else 1.0))
                remaining -= moved
                spend(0, moved * 0.055)
            if action == "MINE" and remaining < 1.35:
                totals["ore"] += min(0.55, max(0.0, ore_limit - totals["ore"]))
            if enemy and contact <= tick < contact + 60:
                for who in (0, 1) if tick % 2 == 0 else (1, 0):
                    if who == 0 or tick - contact >= reaction:
                        strike(who)
                if info["switched"]:
                    info["combat_after_switch"] = True
        if tick in horizons:
            points[tick] = state()
        if health[0] <= 0:
            for horizon in horizons:
                points.setdefault(horizon, state())
            for horizon in short:
                validation.setdefault(horizon, state())
            break
    return {"points": points, "validation": validation, "info": info}


def evaluate(action, trajectory, authority, food_path, a, hunter, basal):
    points = []
    value = 0.0
    for horizon, weight in zip(m.FORECAST_HORIZONS, (0.50, 0.32, 0.18)):
        point = trajectory["points"][horizon]
        projected_energy, projected_health = point["energy"], point["health"]
        point_value = (
            point["ore"] * 0.09
            + point["dealt"] * 0.065
            + point["stolen"] * 0.025
            + point["kill"] * 0.5
            - point["received"] * 0.10
            - point["spent"] * 0.03
            - point["hunger_damage"] * 0.10
        )
        if action == "BUILD":
            intake = (0.17 * food_path[horizon]) if not hunter else 0.0
            child_energy = (a.energy - 12) * 0.45 + (intake - basal) * 45
            viable = (
                child_energy > 0.7
                and projected_health >= 30
                and (hunter or food_path[90] > 0.35)
            )
            point_value += 1.1 if viable else -2.5
        if projected_health < 15:
            point_value -= (15 - projected_health) * 0.12
        confidence = authority / (1.0 + horizon / 100.0)
        value += weight * point_value * (0.55 + 0.45 * confidence)
        points.append(
            {
                "ticks": horizon,
                "energy": round(projected_energy, 3),
                "health": round(projected_health, 3),
                "confidence": round(confidence, 3),
            }
        )
    return value, points


def shadow_scores(world, a, sensed, utility):
    ecology = getattr(world, "ecology", {})
    hunter = getattr(a, "trophic", "forager") == "hunter"
    basal = 0.16 if hunter else 0.10
    stock = max(0.0, float(ecology.get("food", 240.0)))
    capacity = max(1.0, float(ecology.get("food_capacity", 240.0)))
    prey_count = max(0.0, float(ecology.get("prey", 18.0)))
    drought = world.mode in ("Scarcity", "Siege")
    growth_rate, inoculum = (0.022, 0.04) if drought else (0.080, 0.08)
    food_path = {}
    access_total = 0.0
    reserve_ticks = 9999.0
    for t in range(10, 181, 10):
        access = stock / (stock + 18.0)
        renewal = growth_rate * stock * (1 - stock / capacity) + inoculum
        stock = clamp(
            stock + 10 * (renewal - prey_count * 0.195 * access), 0.0, capacity
        )
        access_total += (access + stock / (stock + 18.0)) * 0.5 * 10
        if stock / (stock + 18.0) * 0.195 < 0.10 and reserve_ticks == 9999.0:
            reserve_ticks = float(t)
        if t in m.FORECAST_HORIZONS:
            food_path[t] = access_total / t
    nearest = sensed.get("enemy")
    support = max(0.0, sensed.get("support", 0.0))
    pressure = max(0.0, sensed.get("pressure", 0.0))
    eligible = world.eligible_indices(a, sensed)
    scores = list(utility)
    candidates = {}
    validation_candidates = {}
    ledger = getattr(world, "forecaster", None)
    observations = ledger.validation_count if ledger else 0
    error = ledger.validation_error_sum / observations if observations else None
    trust = 0.25 if observations < 6 else clamp(1.0 / (1.0 + error / 12.0), 0.12, 0.75)
    attack_actions = ("ATTACK", "FLANK", "RAID")
    params, fixed_val = {}, {}
    for index in eligible:
        action = ACTIONS[index]
        enemy = sensed.get("raid_target", nearest) if action == "RAID" else nearest
        if enemy is None:
            enemy = nearest
        target = m.predictive_target(
            world, a, sensed, action, world._target(a, sensed, action)
        )
        distance = math.hypot(target[0] - a.x, target[1] - a.y) if target else 0.0
        speed = (
            (0.29 if hunter else 0.23)
            * a.speed
            * (1.35 if action in ("RETREAT", "RAID") else 1)
        )
        if action == "GUARD":
            speed *= 0.5
        if a.energy < 20:
            speed *= 0.65
        enemy_distance = math.hypot(a.x - enemy.x, a.y - enemy.y) if enemy else 1000.0
        chasing = action in attack_actions
        defensive = action in ("GUARD", "ESCORT")
        chased = bool(enemy and enemy.action in attack_actions)
        enemy_speed = (
            (
                (0.29 if getattr(enemy, "trophic", "forager") == "hunter" else 0.23)
                * enemy.speed
            )
            if enemy
            else 0.0
        )
        contact = (
            max(0.0, enemy_distance - 1.7)
            / max(0.08, speed + (enemy_speed * 0.5 if chased else 0.0))
            if chasing
            else 1e9
        )
        if enemy_distance < 2:
            contact = 0.0
        elif chased:
            closing = enemy_speed - (speed * 0.8 if action == "RETREAT" else 0.0)
            if closing > 0.04:
                contact = min(contact, max(0.0, enemy_distance - 1.7) / closing)
        local_evidence = bool(
            enemy
            and enemy_distance < 6
            and (
                enemy.health < 18
                or pressure > support + 1.5
                or (hunter and 0.7 < a.energy < 20)
            )
        )
        authority = max(trust, 0.7 if local_evidence else 0.0)
        own_rate = enemy_rate = 0.0
        reaction = 0.0
        if enemy:
            own_rate = (
                0.22
                * (4.8 if hunter else 3.6)
                * a.damage
                / (enemy.armor * (1.55 if enemy.action in ("GUARD", "ESCORT") else 1.0))
                if chasing or defensive
                else 0.0
            )
            reaction = (
                0.0 if enemy.action in attack_actions + ("GUARD", "ESCORT") else 5.0
            )
            enemy_rate = (
                0.22
                * (4.8 if enemy.trophic == "hunter" else 3.6)
                * enemy.damage
                / a.armor
            )
            enemy_rate *= (1 + min(2.0, pressure) * 0.18) / (1 + support * 0.35)
            if defensive:
                enemy_rate /= 1.55
            if action == "FLANK":
                enemy_rate *= 0.85
            if action == "RETREAT":
                enemy_rate *= 0.20
        ore_available = 0.0
        if action == "MINE" and target and world.nodes:
            node = min(
                world.nodes, key=lambda n: math.hypot(n.x - target[0], n.y - target[1])
            )
            if math.hypot(node.x - target[0], node.y - target[1]) <= 1.35:
                ore_available = node.amount
        trajectory = lifetime(
            a,
            enemy,
            action,
            food_path,
            distance,
            speed,
            contact,
            reaction,
            own_rate,
            enemy_rate,
            ore_available,
        )
        validation_candidates[action] = [
            {
                "ticks": horizon,
                "energy": round(point["energy"], 3),
                "health": round(point["health"], 3),
            }
            for horizon, point in sorted(trajectory["validation"].items())
        ]
        value, points = evaluate(
            action, trajectory, authority, food_path, a, hunter, basal
        )
        scores[index] = utility[index] + clamp(value * 0.45 * authority, -2.8, 2.8)
        candidates[action] = points
        params[index] = (
            enemy,
            distance,
            speed,
            contact,
            reaction,
            own_rate,
            enemy_rate,
            ore_available,
            authority,
        )
        fixed_val[index] = value
    world.stats["forecast_rollouts"] += len(eligible) * len(m.FORECAST_HORIZONS)

    # ---- shadow pass (proposal section 3(g)-(d)); never writes to world ----
    beam = sorted(eligible, key=lambda i: (-scores[i], i))[:BRANCH_BEAM]
    branched = list(scores)
    best_src = {}
    for i in beam:
        cont = sorted(
            (j for j in eligible if j not in (1, i)), key=lambda j: (-utility[j], j)
        )[:BRANCH_CONT]
        e_i, d_i, s_i, c_i, r_i, o_i, er_i, ore_i, auth_i = params[i]
        best_value, src = fixed_val[i], None
        for j in cont:
            pj = params[j]
            sw = (1 if ACTIONS[i] == "BUILD" else BRANCH_TICK, ACTIONS[j], *pj[1:8])
            tr = lifetime(
                a,
                e_i,
                ACTIONS[i],
                food_path,
                d_i,
                s_i,
                c_i,
                r_i,
                o_i,
                er_i,
                ore_i,
                switch=sw,
            )
            v, _ = evaluate(ACTIONS[i], tr, auth_i, food_path, a, hunter, basal)
            C["branches"] += 1
            if ACTIONS[j] in ATTACKS:
                C["b_cont_into_attack"] += 1
                if tr["info"]["enemy_dropped"] and pj[0] is not None and pj[3] <= 180:
                    C["b_cont_into_attack_combat_lost"] += 1
                if ACTIONS[j] == "RAID" and pj[0] is not e_i:
                    C["b_raid_cont_other_enemy"] += 1
            if v > best_value:
                best_value, src = v, (j, tr["info"], c_i)
        branched[i] = utility[i] + clamp(best_value * 0.45 * auth_i, -2.8, 2.8)
        best_src[i] = src
        cls = "atk" if ACTIONS[i] in ATTACKS else "other"
        C[f"uplift_n_{cls}"] += 1
        C[f"uplift_sum_{cls}"] += branched[i] - scores[i]
        C[f"switch_best_{cls}"] += src is not None
    if len(eligible) >= 2:
        C["two_plus"] += 1
        ua = max(eligible, key=lambda i: (utility[i], -i))
        fa = max(eligible, key=lambda i: (scores[i], -i))
        ba = max(eligible, key=lambda i: (branched[i], -i))
        if ua != fa:
            C["flip_fixed"] += 1
            C["flip_fixed_to_" + ACTIONS[fa]] += 1
            if ACTIONS[fa] == "RETREAT":
                C["veto_retreat_fixed"] += 1
                C["veto_retreat_undone"] += ba == ua
        if ua != ba:
            C["flip_branch"] += 1
            C["flip_branch_to_" + ACTIONS[ba]] += 1
        if fa != ba:
            C["changed"] += 1
            C[f"chg {ACTIONS[fa]}->{ACTIONS[ba]}"] += 1
        if ua != fa and ba == ua:
            C["flip_undone"] += 1
        if ua == fa and ba != ua:
            C["flip_new"] += 1
    SHADOW[a.uid] = best_src
    forecast = {
        "horizons": list(m.FORECAST_HORIZONS),
        "candidates": candidates,
        "validation_candidates": validation_candidates,
        "food_runway_ticks": round(min(9999.0, reserve_ticks), 1),
        "calibration": {
            "observations": observations,
            "mean_error": None if error is None else round(error, 3),
            "trust": round(trust, 3),
            "basis": "fixed_action_until_next_decision",
        },
        "assumption": "conditional current action and population; replanning can invalidate it",
    }
    out = scores if MODE == "A" else branched
    return (
        out,
        "30/90/180-tick forecast · short-transition evidence / finite combat / viable heirs",
        forecast,
    )


orig_choose = m.BattleWorld._choose


def choose(self, a, s):
    f = self.factions[a.faction]
    SHADOW.pop(a.uid, None)
    orig_choose(self, a, s)
    if f.method != "Lookahead":
        return
    C[f"{MODE}_la_decisions"] += 1
    C[f"{MODE}_la_action_{a.action}"] += 1
    prev = PENDING.pop(a.uid, None)
    if prev is not None and prev[3] == self.episode:
        kind, expect, frm, _ = prev
        C[f"c_{kind}_n"] += 1
        C[f"c_{kind}_hit"] += a.action == expect
        C[f"c_{kind}_kept"] += a.action == frm
    best_src = SHADOW.pop(a.uid, None)
    if best_src is None:
        return
    chosen = ACTIONS.index(a.action)
    if chosen not in best_src:
        C["chosen_outside_beam"] += 1
        return
    src = best_src[chosen]
    if src is None:
        PENDING[a.uid] = ("fixed", a.action, a.action, self.episode)
    else:
        j, tinfo, c_i = src
        PENDING[a.uid] = ("switch", ACTIONS[j], a.action, self.episode)
        if a.action in ATTACKS:
            C["d_attack_rescue"] += 1
            if c_i > BRANCH_TICK and not tinfo["combat_after_switch"]:
                C["d_attack_rescue_zero_exposure"] += 1


def digest(world):
    return hashlib.sha256(
        json.dumps(world.export(), sort_keys=True, default=str).encode()
    ).hexdigest()[:16]


def run(seed, ticks):
    w = m.BattleWorld(seed=seed, max_agents=60, episode_ticks=1500)
    for _ in range(ticks):
        w.step()
    return w


if __name__ == "__main__":
    base = digest(run(101, 1500))
    orig_ps = m.predictive_scores
    m.predictive_scores = shadow_scores
    m.BattleWorld._choose = choose
    patched = digest(run(101, 1500))
    print(
        f"faithfulness seed 101 x1500: unpatched {base} | patched-A {patched} | equal={base == patched}"
    )
    C.clear()
    PENDING.clear()
    SHADOW.clear()
    report = {}
    for MODE in ("A", "B"):
        globals()["MODE"] = MODE
        C.clear()
        PENDING.clear()
        SHADOW.clear()
        for seed in (101, 202, 303):
            run(seed, 4000)
        report[MODE] = dict(C)
    for mode, c in report.items():
        c = Counter(c)
        n2 = max(1, c["two_plus"])
        print(
            f"\n===== MODE {mode} (world acts on {'fixed' if mode == 'A' else 'branched'} scores) ====="
        )
        print(
            f"2+-eligible decisions {c['two_plus']} | fixed flips {c['flip_fixed']} ({100 * c['flip_fixed'] / n2:.1f}%) "
            f"| branched flips {c['flip_branch']} ({100 * c['flip_branch'] / n2:.1f}%) | fixed!=branched {c['changed']} "
            f"({100 * c['changed'] / n2:.1f}%) | undone {c['flip_undone']} | new {c['flip_new']}"
        )
        print(
            f"RETREAT vetoes (fixed) {c['veto_retreat_fixed']}, undone by branch {c['veto_retreat_undone']} "
            f"({100 * c['veto_retreat_undone'] / max(1, c['veto_retreat_fixed']):.0f}%)"
        )
        print(
            "fixed flips to:",
            {k[14:]: v for k, v in sorted(c.items()) if k.startswith("flip_fixed_to_")},
        )
        print(
            "branched flips to:",
            {
                k[15:]: v
                for k, v in sorted(c.items())
                if k.startswith("flip_branch_to_")
            },
        )
        print(
            "changes fixed->branched:",
            dict(
                sorted(
                    ((k[4:], v) for k, v in c.items() if k.startswith("chg ")),
                    key=lambda kv: -kv[1],
                )[:10]
            ),
        )
        print(
            f"(b) continuations into ATTACK/FLANK/RAID {c['b_cont_into_attack']} of {c['branches']} branches; "
            f"combat silently lost (enemy dropped at 1502) {c['b_cont_into_attack_combat_lost']} "
            f"({100 * c['b_cont_into_attack_combat_lost'] / max(1, c['b_cont_into_attack']):.1f}%); RAID cont. vs other enemy {c['b_raid_cont_other_enemy']}"
        )
        for cls in ("atk", "other"):
            n = max(1, c[f"uplift_n_{cls}"])
            print(
                f"uplift {cls}: beam members {c[f'uplift_n_{cls}']}, best is a switch {100 * c[f'switch_best_{cls}'] / n:.1f}%, "
                f"mean score uplift {c[f'uplift_sum_{cls}'] / n:+.3f}"
            )
        print(
            f"(c) next decision after a SWITCH-best choice: n={c['c_switch_n']} picks assumed j {100 * c['c_switch_hit'] / max(1, c['c_switch_n']):.1f}% "
            f"| keeps i {100 * c['c_switch_kept'] / max(1, c['c_switch_n']):.1f}%"
        )
        print(
            f"    control after a FIXED-best choice: n={c['c_fixed_n']} keeps i {100 * c['c_fixed_hit'] / max(1, c['c_fixed_n']):.1f}%"
        )
        print(
            f"(d) ATTACK/FLANK/RAID chosen with switch-best {c['d_attack_rescue']}; contact_i>12 and zero combat after switch "
            f"{c['d_attack_rescue_zero_exposure']} ({100 * c['d_attack_rescue_zero_exposure'] / max(1, c['d_attack_rescue']):.0f}%)"
        )
        la = max(1, c[f"{mode}_la_decisions"])
        print(
            "Lookahead action mix:",
            {
                k.split("_")[-1]: f"{100 * v / la:.1f}%"
                for k, v in sorted(c.items())
                if k.startswith(f"{mode}_la_action_")
            },
        )
