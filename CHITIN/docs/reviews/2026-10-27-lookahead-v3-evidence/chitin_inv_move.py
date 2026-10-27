import importlib.util, inspect, json, sys, textwrap, time
from pathlib import Path

SOURCE = Path(r"C:\Users\rmanov\algorithmic-arts\CHITIN\battle_evolution.py")
spec = importlib.util.spec_from_file_location("chitin_inv2", SOURCE)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)

OLD = """        for h in self.hazards:
            if h['warning']: continue
            hd=math.hypot(a.x-h['x'],a.y-h['y'])
            if hd<h['radius'] and h['kind']=='ice':
                speed*=.34; self.stats['ice_slow_ticks']+=1
            if hd<h['radius'] and h['kind']=='river':
                speed*=.7 if abs(a.y-h['y'])<1 else .42
                self.stats['river_crossing_ticks']+=1
"""
NEW = """        speed,kinds=_terrain_speed([h for h in self.hazards if not h['warning']],a.x,a.y,speed)
        for kind in kinds:
            self.stats['ice_slow_ticks' if kind=='ice' else 'river_crossing_ticks']+=1
"""
HELPER = """
def _terrain_speed(hazards,x,y,speed):
    kinds=[]
    for h in hazards:
        hd=math.hypot(x-h['x'],y-h['y'])
        if hd<h['radius'] and h['kind']=='ice':
            speed*=.34; kinds.append('ice')
        if hd<h['radius'] and h['kind']=='river':
            speed*=.7 if abs(y-h['y'])<1 else .42
            kinds.append('river')
    return speed,kinds
"""
src = textwrap.dedent(inspect.getsource(m.BattleWorld._move))
old = textwrap.dedent(OLD.replace("        ", "    ", 1)) if False else None
src_full = inspect.getsource(m.BattleWorld._move)
assert src_full.count(OLD.replace("        ", "    ", 0)) == 1, "anchor"
patched = textwrap.dedent(src_full.replace(OLD, NEW))
ns = m.__dict__
exec(HELPER, ns)
exec(patched, ns)
orig_move = m.BattleWorld._move
new_move = ns["_move"]


def run(move, seed, steps):
    m.BattleWorld._move = move
    w = m.BattleWorld(seed=seed)
    t0 = time.perf_counter()
    for _ in range(steps):
        w.step()
    dt = time.perf_counter() - t0
    m.BattleWorld._move = orig_move
    return w, dt


for seed, steps in ((42, 520), (101, 1500)):
    a, _ = run(orig_move, seed, steps)
    b, _ = run(new_move, seed, steps)
    ja = json.dumps(a.export(), allow_nan=False)
    jb = json.dumps(b.export(), allow_nan=False)
    print(
        f"seed {seed}/{steps}: export bytes identical={ja == jb} ice={a.stats['ice_slow_ticks']} river={a.stats['river_crossing_ticks']}"
    )

ta, tb = [], []
for r in range(3):
    ta.append(run(orig_move, 202, 3000)[1])
    tb.append(run(new_move, 202, 3000)[1])
print(
    "3000 ticks seed 202: orig",
    [round(x, 2) for x in ta],
    "helper",
    [round(x, 2) for x in tb],
    f"median delta {100 * (sorted(tb)[1] / sorted(ta)[1] - 1):+.1f}%",
)
