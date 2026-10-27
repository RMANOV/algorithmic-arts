"""Shadow diagnostic (read-only on the product): how often would terrain-aware travel time flip a Lookahead decision?

Runs the unmodified world; at every Lookahead decision also computes a shadow score vector where each candidate's
speed is scaled by the straight-path terrain factor (ice .34, river .42/.7 ford, mountain ring ~.5 proxy; hazards
active at the sample's arrival tick: age+t >= 35 (56 flash is irrelevant here), age+t <= ttl). World trajectory is
untouched (shadow result discarded), so flip rates are measured on the real state distribution.
Also: hazard damage and slowed ticks per method, predicted vs actual MINE arrival ticks.
"""

import importlib.util
import inspect
import math
import sys
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
SOURCE = Path(r"C:\Users\rmanov\algorithmic-arts\CHITIN\battle_evolution.py")
spec = importlib.util.spec_from_file_location("chitin_diag", SOURCE)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)

TERRAIN = ("ice", "river", "mountain")


def terrain_factor(world, a, target, action):
    """(travel_ticks, straight_ticks, crossed:set) along the straight segment, sampled every <=1 unit."""
    if not target:
        return 0.0, 0.0, set()
    dx, dy = target[0] - a.x, target[1] - a.y
    distance = math.hypot(dx, dy)
    speed = (
        (0.29 if a.trophic == "hunter" else 0.23)
        * a.speed
        * (1.35 if action in ("RETREAT", "RAID") else 1)
    )
    if action == "GUARD":
        speed *= 0.5
    if a.energy < 20:
        speed *= 0.65
    if distance < 1e-9 or speed <= 0:
        return 0.0, 0.0, set()
    hz = [h for h in world.hazards if h["kind"] in TERRAIN]
    if not hz:
        return distance / speed, distance / speed, set()
    n = max(1, min(40, math.ceil(distance)))
    step = distance / n
    path_angle = math.atan2(dy, dx)
    t = 0.0
    crossed = set()
    for i in range(n):
        frac = (i + 0.5) / n
        x, y = a.x + dx * frac, a.y + dy * frac
        mult = 1.0
        drift = 0.0
        for h in hz:
            if h["kind"] == "mountain":
                continue  # ship rule: mountain ring-walk not modelled
            if h["age"] + t < 35:
                continue  # announced but not yet active at arrival; ttl not read
            hd = math.hypot(x - h["x"], y - h["y"])
            if h["kind"] == "ice" and hd < h["radius"]:
                mult *= 0.34
                crossed.add("ice")
            elif h["kind"] == "river" and hd < h["radius"]:
                mult *= 0.7 if abs(y - h["y"]) < 1 else 0.42
                crossed.add("river")
                drift += 0.065 * math.cos(
                    h["heading"] - path_angle
                )  # along-path component of the current (_move 601-603)
        t += step / max(0.01, speed * mult + drift)
    return t, distance / speed, crossed


# --- shadow predictive_scores: inject terrain factor into candidate speed ---
src = inspect.getsource(m.predictive_scores)
needle = "        if a.energy<20: speed*=.65\n"
assert src.count(needle) == 1, "anchor line changed"
src_b = src.replace("def predictive_scores(", "def predictive_scores_B(").replace(
    needle,
    needle
    + "        _tt,_st,_cr=terrain_factor(world,a,target,action)\n        if _tt>0 and _st>0: speed*=_st/_tt\n        DIAG['cand'].append((action,_st/_tt if _tt>0 else 1.,bool(_cr)))\n",
)
ns = dict(m.__dict__)
ns["terrain_factor"] = terrain_factor
DIAG = {"cand": []}
ns["DIAG"] = DIAG
TIMES = Counter()
exec(src_b, ns)
predictive_scores_B = ns["predictive_scores_B"]

orig_ps = m.predictive_scores
A2 = []
stats = Counter()
flips = Counter()
flip_pairs = Counter()
chosen_factor = []
min_factor = []


def shadow_ps(world, a, sensed, utility):
    _t0 = time.perf_counter()
    scores_a, reason, forecast = orig_ps(world, a, sensed, utility)
    TIMES["A"] += time.perf_counter() - _t0
    DIAG["cand"].clear()
    _t0 = time.perf_counter()
    scores_b, _, _ = predictive_scores_B(world, a, sensed, utility)
    TIMES["B"] += time.perf_counter() - _t0
    eligible = world.eligible_indices(a, sensed)
    best_a = max(eligible, key=lambda i: (scores_a[i], -i))
    best_b = max(eligible, key=lambda i: (scores_b[i], -i))
    stats["decisions"] += 1
    cand = DIAG["cand"]
    if any(c[2] for c in cand):
        stats["decisions_any_candidate_crossing"] += 1
    fa = next((c[1] for c in cand if c[0] == m.ACTIONS[best_a]), 1.0)
    chosen_factor.append(fa)
    min_factor.append(min((c[1] for c in cand), default=1.0))
    if fa < 0.999:
        stats["decisions_chosen_path_crossing"] += 1
    if best_a != best_b and scores_b[best_b] - scores_b[best_a] > 1e-9:
        flips["flip"] += 1
        flip_pairs[(m.ACTIONS[best_a], m.ACTIONS[best_b])] += 1
    # A2 potential: MINE candidate whose default path crosses terrain -> best of 8 nearest alternatives
    if 0 in eligible:
        default = world._target(a, sensed, "MINE")
        default = m.predictive_target(world, a, sensed, "MINE", default)
        tt, stt, cr = terrain_factor(world, a, default, "MINE")
        stats["mine_candidates"] += 1
        if math.hypot(default[0] - a.x, default[1] - a.y) < 1.35:
            stats["mine_already_there"] += 1
        elif cr:
            stats["mine_default_crossing"] += 1
            alts = sorted(
                (n for n in world.nodes if n.amount > 0.05),
                key=lambda n: (
                    math.hypot(n.x - a.x, n.y - a.y) / (1 + min(n.amount, 20) * 0.025),
                    n.x,
                    n.y,
                ),
            )[:8]
            best = min(
                (terrain_factor(world, a, (n.x, n.y), "MINE")[0] for n in alts),
                default=tt,
            )
            A2.append((tt, best, tt - best, m.ACTIONS[best_a]))
    return scores_a, reason, forecast


m.predictive_scores = shadow_ps

# --- hazard damage & slowed ticks per method; MINE arrival predicted vs actual ---
dmg = defaultdict(float)
slowed = Counter()
arrivals = []
pending = {}
orig_hc = m.BattleWorld._hazard_contact
orig_move = m.BattleWorld._move
orig_choose = m.BattleWorld._choose
orig_step = m.BattleWorld.step


def hc(self, a):
    before = a.health
    orig_hc(self, a)
    d = before - a.health
    if d > 0:
        dmg[self.factions[a.faction].method] += d


def mv(self, a):
    if a.target and a.action != "BUILD":
        meth = self.factions[a.faction].method
        for h in self.hazards:
            if h["warning"] or h["kind"] not in TERRAIN:
                continue
            hd = math.hypot(a.x - h["x"], a.y - h["y"])
            if (h["kind"] == "mountain" and hd < h["radius"] + 1.3) or (
                h["kind"] != "mountain" and hd < h["radius"]
            ):
                slowed[(meth, h["kind"])] += 1
        slowed[(meth, "moving_ticks")] += 1
    orig_move(self, a)


def ch(self, a, s):
    orig_choose(self, a, s)
    f = self.factions[a.faction]
    if f.method == "Lookahead" and a.action == "MINE" and a.target:
        if pending.get(a.uid, {}).get("target") != tuple(a.target):
            tt, stt, cr = terrain_factor(self, a, a.target, "MINE")
            pending[a.uid] = {
                "target": tuple(a.target),
                "start": self.tick,
                "pred_straight": stt,
                "pred_terrain": tt,
                "crossing": bool(cr),
                "episode": self.episode,
            }


def stp(self):
    orig_step(self)
    for uid, rec in list(pending.items()):
        a = self._alive.get(uid)
        if (
            a is None
            or rec["episode"] != self.episode
            or a.action != "MINE"
            or tuple(a.target or ()) != rec["target"]
        ):
            pending.pop(uid)
            stats["arrival_censored"] += 1
            continue
        if math.hypot(a.x - rec["target"][0], a.y - rec["target"][1]) < 1.35:
            arrivals.append(
                (
                    rec["pred_straight"],
                    rec["pred_terrain"],
                    self.tick - rec["start"],
                    rec["crossing"],
                )
            )
            pending.pop(uid)


m.BattleWorld._hazard_contact = hc
m.BattleWorld._move = mv
m.BattleWorld._choose = ch
m.BattleWorld.step = stp

seeds = [int(x) for x in sys.argv[1].split(",")]
steps = int(sys.argv[2])
import time

for seed in seeds:
    w = m.BattleWorld(seed=seed, max_agents=60, episode_ticks=1500, learning=True)
    t0 = time.perf_counter()
    for _ in range(steps):
        w.step()
    print(
        f"seed {seed}: {steps} ticks in {time.perf_counter() - t0:.1f}s, epoch {w.episode}, pop {len(w.agents)}"
    )

print("\n== Lookahead decisions ==", dict(stats))
print(
    "flips (shadow argmax != real argmax):",
    flips["flip"],
    f"= {100 * flips['flip'] / max(1, stats['decisions']):.2f}% of decisions",
)
print("flip pairs (real -> shadow):", flip_pairs.most_common(12))
print(
    "chosen-path factor: mean",
    round(st.mean(chosen_factor), 4),
    "share<.999",
    round(sum(f < 0.999 for f in chosen_factor) / len(chosen_factor), 4),
    "share<.8",
    round(sum(f < 0.8 for f in chosen_factor) / len(chosen_factor), 4),
    "share<.6",
    round(sum(f < 0.6 for f in chosen_factor) / len(chosen_factor), 4),
)
print(
    "min candidate factor <.8 share",
    round(sum(f < 0.8 for f in min_factor) / len(min_factor), 4),
)
print(
    "\n== hazard damage per method (health) ==",
    {k: round(v, 1) for k, v in sorted(dmg.items())},
)
meths = sorted({k[0] for k in slowed})
for meth in meths:
    mt = slowed[(meth, "moving_ticks")]
    print(
        f"{meth:11} moving_ticks {mt:7d} ice {100 * slowed[(meth, 'ice')] / mt:5.2f}% river {100 * slowed[(meth, 'river')] / mt:5.2f}% mountain {100 * slowed[(meth, 'mountain')] / mt:5.2f}%"
    )
print(
    f"== timing: predictive_scores A {1000 * TIMES['A'] / max(1, stats['decisions']):.3f} ms/decision, shadow B {1000 * TIMES['B'] / max(1, stats['decisions']):.3f} ms/decision =="
)
print(
    "== A2 potential (MINE candidate, default path crossing terrain) ==",
    {k: v for k, v in stats.items() if k.startswith("mine")},
)
if A2:
    sav = [r[2] for r in A2]
    print(
        "n",
        len(A2),
        "saving ticks: mean",
        round(st.mean(sav), 1),
        "median",
        round(st.median(sav), 1),
        "share>=10",
        round(sum(x >= 10 for x in sav) / len(sav), 3),
        "share>=30",
        round(sum(x >= 30 for x in sav) / len(sav), 3),
    )
    print(
        "default travel ticks mean",
        round(st.mean(r[0] for r in A2), 1),
        "best alt mean",
        round(st.mean(r[1] for r in A2), 1),
        "chosen action when MINE crossed:",
        Counter(r[3] for r in A2).most_common(),
    )
if arrivals:
    err_s = [abs(p - act) for p, _, act, _ in arrivals]
    err_t = [abs(q - act) for _, q, act, _ in arrivals]
    cross = [r for r in arrivals if r[3]]
    print(
        f"\n== MINE arrivals (Lookahead) n={len(arrivals)}, crossing n={len(cross)}, censored {stats['arrival_censored']} =="
    )
    print(
        "all: MAE straight",
        round(st.mean(err_s), 2),
        "MAE terrain",
        round(st.mean(err_t), 2),
        "median actual",
        st.median(a for *_, a, _ in arrivals),
    )
    if cross:
        print(
            "crossing: MAE straight",
            round(st.mean(abs(p - act) for p, _, act, _ in cross), 2),
            "MAE terrain",
            round(st.mean(abs(q - act) for _, q, act, _ in cross), 2),
            "mean actual",
            round(st.mean(a for *_, a, _ in cross), 1),
            "mean pred straight",
            round(st.mean(p for p, *_ in cross), 1),
            "mean pred terrain",
            round(st.mean(q for _, q, *_ in cross), 1),
        )
        print(
            "crossing sample:",
            [
                tuple(round(v, 1) if isinstance(v, float) else v for v in r)
                for r in cross[:12]
            ],
        )
