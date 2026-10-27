import sys, time

sys.argv = ["x"]
exec(open("chitin_inv_move.py", encoding="utf-8").read().split("for seed, steps in")[0])
# interleaved, 5 reps x 2000 ticks, seed 303
ta, tb = [], []
for r in range(5):
    ta.append(run(orig_move, 303, 2000)[1])
    tb.append(run(new_move, 303, 2000)[1])
med = lambda v: sorted(v)[len(v) // 2]
print(
    "2000 ticks seed 303: orig",
    [round(x, 2) for x in ta],
    "helper",
    [round(x, 2) for x in tb],
    f"median delta {100 * (med(tb) / med(ta) - 1):+.1f}%  min delta {100 * (min(tb) / min(ta) - 1):+.1f}%",
)
# per-call microbenchmark of _move on a live world state (3 terrain hazards present)
w = m.BattleWorld(seed=42)
for _ in range(60):
    w.step()
movers = [a for a in w.agents if a.target and a.action != "BUILD"]


def bench(move):
    snap = [(a, a.x, a.y, a.energy, a.pending_reward, a.heading) for a in movers]
    t0 = time.perf_counter()
    for _ in range(2000):
        for a in movers:
            move(w, a)
        for a, x, y, e, p, hd in snap:
            a.x, a.y, a.energy, a.pending_reward, a.heading = x, y, e, p, hd
    return (time.perf_counter() - t0) / (2000 * len(movers)) * 1e6


b1 = [bench(orig_move) for _ in range(3)]
b2 = [bench(new_move) for _ in range(3)]
print(
    f"_move per call: orig {min(b1):.2f} us, helper {min(b2):.2f} us, delta {min(b2) - min(b1):+.2f} us; agents {len(w.agents)}, hazards {[h['kind'] for h in w.hazards]}"
)
