"""Build a scratch prototype of the 'two-stage lookahead' proposal (review only).

Reads the original CHITIN 2.0.1 source, applies the proposal's mechanism as
written (switch kwarg in _forecast_lifetime; pass-2 beam/continuations in
predictive_scores), and writes the copy under this folder. The repository is
never modified. BEAM env var lets the reviewer reproduce BRANCH_BEAM=0.
"""

import os
import shutil
from pathlib import Path

ORIG = Path(r"C:\Users\rmanov\algorithmic-arts\CHITIN\battle_evolution.py")
TESTS = Path(r"C:\Users\rmanov\algorithmic-arts\tests")
HERE = Path(__file__).resolve().parent / os.environ.get("VARIANT", "b3")
OUT = HERE / "CHITIN" / "battle_evolution.py"

src = ORIG.read_text(encoding="utf-8")


def sub(old, new, count=1):
    global src
    assert src.count(old) == count, (old[:80], src.count(old))
    src = src.replace(old, new)


beam = os.environ.get("BEAM", "3")
sub(
    "FORECAST_HORIZONS = (30, 90, 180)\n",
    "FORECAST_HORIZONS = (30, 90, 180)\n"
    f"BRANCH_TICK = 12\nBRANCH_BEAM = {beam}\nBRANCH_CONTINUATIONS = 2\n",
)

# (2) switch kwarg in _forecast_lifetime
sub(
    "                       reaction, own_rate, enemy_rate, ore_available=0.):\n",
    "                       reaction, own_rate, enemy_rate, ore_available=0., switch=None):\n",
)
sub(
    """        if health[0] > 0:
            if action == 'BUILD' and tick == 0:""",
    """        if health[0] > 0:
            if switch and tick == switch[0]:
                # Proposal 2: re-bind locals; closures read the new cells.
                action = switch[1]
                remaining = max(0., switch[2])
                base_speed = switch[3] / (.65 if a.energy < 20 else 1.)
                if not (enemy and contact <= tick < contact+60):
                    contact = tick + switch[4]
                reaction = switch[5]
                rates = (switch[6], switch[7])
                ore_limit = max(0., min(switch[8], 15.-a.metal))
                intake_rates = (.22 if action in ('MINE', 'GUARD') else .17, intake_rates[1])
                can_repair = (action in ('MINE', 'GUARD'), can_repair[1])
            if action == 'BUILD' and tick == 0:""",
)

# (3) predictive_scores: params/evaluate/pass 2
old_tail = src[
    src.index(
        "        trajectory=_forecast_lifetime(a,enemy,action,food_path,distance,speed,"
    ) : src.index("    return scores,'30/90/180-tick forecast")
]
new_tail = """        trajectory=_forecast_lifetime(a,enemy,action,food_path,distance,speed,
                                      contact,reaction,own_rate,enemy_rate,ore_available)
        params[index]=(enemy,distance,speed,contact,reaction,own_rate,enemy_rate,ore_available)
        authorities[index]=authority
        validation_candidates[action]=[
            {'ticks':horizon,'energy':round(point['energy'],3),'health':round(point['health'],3)}
            for horizon,point in sorted(trajectory['validation'].items())]
        value,points=evaluate(action,trajectory,authority)
        fixed[index]=(value,points)
        scores[index]=utility[index]+clamp(value*.45*authority,-2.8,2.8)
        candidates[action]=points
    continuations={ACTIONS[i]:None for i in eligible}
    branches_run=0
    beam=sorted(eligible,key=lambda i:(-scores[i],i))[:BRANCH_BEAM]
    for i in beam:
        action_i=ACTIONS[i]
        e_i,d_i,s_i,c_i,r_i,o_i,er_i,ore_i=params[i]
        cont=sorted((j for j in eligible if j not in (1,i)),key=lambda j:(-utility[j],j))[:BRANCH_CONTINUATIONS]
        best=fixed[i]; best_j=None
        for j in cont:
            trajectory=_forecast_lifetime(a,e_i,action_i,food_path,d_i,s_i,c_i,r_i,o_i,er_i,ore_i,
                switch=(1 if action_i=='BUILD' else BRANCH_TICK,ACTIONS[j],*params[j][1:]))
            branches_run+=1
            candidate=evaluate(action_i,trajectory,authorities[i])
            if candidate[0]>best[0]: best=candidate; best_j=j
        scores[i]=utility[i]+clamp(best[0]*.45*authorities[i],-2.8,2.8)
        candidates[action_i]=best[1]
        continuations[action_i]=ACTIONS[best_j] if best_j is not None else None
    world.stats['forecast_branches']+=branches_run
    world.stats['forecast_rollouts']+=len(eligible)*len(FORECAST_HORIZONS)
"""
src = src.replace(old_tail, new_tail)
sub(
    "    attack_actions = ('ATTACK','FLANK','RAID')\n    for index in eligible:\n",
    """    attack_actions = ('ATTACK','FLANK','RAID')
    def evaluate(action, trajectory, authority):
        points=[]; value=0.
        for horizon,weight in zip(FORECAST_HORIZONS,(.50,.32,.18)):
            point=trajectory['points'][horizon]
            projected_energy,projected_health=point['energy'],point['health']
            point_value=(point['ore']*.09+point['dealt']*.065+point['stolen']*.025+
                         point['kill']*.5-point['received']*.10-point['spent']*.03-
                         point['hunger_damage']*.10)
            if action=='BUILD':
                intake=(.17*food_path[horizon]) if not hunter else 0.
                child_energy=(a.energy-12)*.45+(intake-basal)*45
                viable=child_energy>.7 and projected_health>=30 and (hunter or food_path[90]>.35)
                point_value+=1.1 if viable else -2.5
            if projected_health<15:point_value-=(15-projected_health)*.12
            confidence=authority/(1.+horizon/100.)
            value+=weight*point_value*(.55+.45*confidence)
            points.append({'ticks':horizon,'energy':round(projected_energy,3),
                           'health':round(projected_health,3),'confidence':round(confidence,3)})
        return value,points
    params={}; fixed={}; authorities={}
    for index in eligible:
""",
)
sub(
    "        'validation_candidates':validation_candidates,\n",
    "        'validation_candidates':validation_candidates,'continuations':continuations,\n",
)

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(src, encoding="utf-8", newline=chr(10))
(HERE / "tests").mkdir(exist_ok=True)
for t in TESTS.glob("test_chitin_*.py"):
    shutil.copy2(t, HERE / "tests" / t.name)
print("wrote", OUT, "BRANCH_BEAM", beam)
