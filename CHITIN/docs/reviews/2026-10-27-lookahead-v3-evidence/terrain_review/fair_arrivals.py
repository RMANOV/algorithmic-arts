"""Read-only check of the terrain proposal's travel-time model against real _move, all methods, MINE targets.

Compares predicted ticks to reach mining range (<1.35, the forecast's ore start rule) under:
  S = straight base speed (today), T = terrain integrated along the path (best case),
  P = proposal's single scalar speed=distance/travel_full applied uniformly (what step 1c would feed _forecast_lifetime).
Also compares predicted vs actual progress after 10 moves (short-lane movement energy = .055 x progress).
The world is not modified; hooks only observe.
"""

import importlib.util
import math
import sys
import statistics as st
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
SOURCE = Path(r"C:\Users\rmanov\algorithmic-arts\CHITIN\battle_evolution.py")
spec = importlib.util.spec_from_file_location("chitin_fair", SOURCE)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


def travel(world, a, target, speed, limit):
    """Ticks to advance `limit` units along a->target with ice/river active at arrival (age+t>=35)."""
    dx, dy = target[0] - a.x, target[1] - a.y
    distance = math.hypot(dx, dy)
    if limit <= 0 or distance < 1e-9:
        return 0.0, False
    hz = [h for h in world.hazards if h["kind"] in ("ice", "river")]
    n = max(1, min(40, math.ceil(distance)))
    step = distance / n
    ang = math.atan2(dy, dx)
    t = 0.0
    done = 0.0
    crossed = False
    for i in range(n):
        if done >= limit:
            break
        seg = min(step, limit - done)
        frac = (done + seg * 0.5) / distance
        x, y = a.x + dx * frac, a.y + dy * frac
        mult = 1.0
        drift = 0.0
        for h in hz:
            if h["age"] + t < 35:
                continue
            if math.hypot(x - h["x"], y - h["y"]) < h["radius"]:
                crossed = True
                if h["kind"] == "ice":
                    mult *= 0.34
                else:
                    mult *= 0.7 if abs(y - h["y"]) < 1 else 0.42
                    drift += 0.065 * math.cos(h["heading"] - ang)
        t += seg / max(0.01, speed * mult + drift)
        done += seg
    return t, crossed


def progress_after(world, a, target, speed, ticks):
    """Integrated distance covered in `ticks` along the path under the terrain model (T)."""
    dx, dy = target[0] - a.x, target[1] - a.y
    distance = math.hypot(dx, dy)
    lo, hi = 0.0, distance
    if travel(world, a, target, speed, hi)[0] <= ticks:
        return distance
    for _ in range(40):
        mid = (lo + hi) / 2
        if travel(world, a, target, speed, mid)[0] <= ticks:
            lo = mid
        else:
            hi = mid
    return lo


pending = {}
rows = []
prog = []
cnt = Counter()
orig_choose = m.BattleWorld._choose
orig_step = m.BattleWorld.step


def ch(self, a, s):
    orig_choose(self, a, s)
    if a.action != "MINE" or not a.target:
        return
    tgt = tuple(a.target)
    if pending.get(a.uid, {}).get("target") == tgt:
        return
    d0 = math.hypot(tgt[0] - a.x, tgt[1] - a.y)
    if d0 < 1.35:
        cnt["already_in_range"] += 1
        pending.pop(a.uid, None)
        return
    speed = (
        (0.29 if a.trophic == "hunter" else 0.23)
        * a.speed
        * (0.65 if a.energy < 20 else 1.0)
    )
    L = d0 - 1.35
    t_full, cr_full = travel(self, a, tgt, speed, d0)
    t_lim, cr_lim = travel(self, a, tgt, speed, L)
    S = L / speed
    T = t_lim
    P = L * t_full / d0
    v_p = d0 / t_full if t_full > 0 else speed
    pending[a.uid] = dict(
        target=tgt,
        start=self.tick,
        ep=self.episode,
        d0=d0,
        S=S,
        T=T,
        P=P,
        cross=cr_lim,
        cross_full=cr_full,
        method=self.factions[a.faction].method,
        p10=(
            min(d0, 10 * speed),
            min(d0, 10 * v_p),
            progress_after(self, a, tgt, speed, 10),
        ),
    )


def stp(self):
    orig_step(self)
    for uid, r in list(pending.items()):
        a = self._alive.get(uid)
        if (
            a is None
            or r["ep"] != self.episode
            or a.action != "MINE"
            or tuple(a.target or ()) != r["target"]
        ):
            pending.pop(uid)
            cnt["censored"] += 1
            continue
        moves = self.tick - r["start"] + 1
        d = math.hypot(a.x - r["target"][0], a.y - r["target"][1])
        if moves == 10 and "act10" not in r:
            r["act10"] = r["d0"] - d
        if d < 1.35:
            rows.append(
                (
                    r["S"],
                    r["T"],
                    r["P"],
                    moves,
                    r["cross"],
                    r["cross_full"],
                    r["method"],
                )
            )
            if "act10" in r:
                prog.append((r["p10"], r["act10"], r["cross_full"]))
            pending.pop(uid)


m.BattleWorld._choose = ch
m.BattleWorld.step = stp
seeds = [int(x) for x in sys.argv[1].split(",")]
steps = int(sys.argv[2])
for seed in seeds:
    w = m.BattleWorld(seed=seed, max_agents=60, episode_ticks=1500, learning=True)
    for _ in range(steps):
        w.step()
    pending.clear()
print("counts", dict(cnt), "arrivals", len(rows))


def report(label, sub):
    if not sub:
        print(label, "n=0")
        return
    act = [r[3] for r in sub]
    mae = lambda k: st.mean(abs(r[k] - r[3]) for r in sub)
    bias = lambda k: st.mean(r[k] - r[3] for r in sub)
    print(
        f"{label:34} n={len(sub):5d} actual mean {st.mean(act):6.1f} | MAE S {mae(0):6.2f} T {mae(1):6.2f} P {mae(2):6.2f}"
        f" | bias S {bias(0):+6.2f} T {bias(1):+6.2f} P {bias(2):+6.2f}"
    )


report("all arrivals", rows)
report("crossing before mining range", [r for r in rows if r[4]])
report("crossing only beyond range (full)", [r for r in rows if r[5] and not r[4]])
report("no crossing", [r for r in rows if not r[5]])
report("Lookahead crossing", [r for r in rows if r[4] and r[6] == "Lookahead"])
pc = [p for p in prog if p[2]]
if pc:
    for i, name in enumerate(("S", "P", "T")):
        print(
            f"10-move progress, crossing paths n={len(pc)}: MAE {name} {st.mean(abs(p[0][i] - p[1]) for p in pc):.3f} units"
            f" (energy x.055 = {0.055 * st.mean(abs(p[0][i] - p[1]) for p in pc):.4f})"
        )
