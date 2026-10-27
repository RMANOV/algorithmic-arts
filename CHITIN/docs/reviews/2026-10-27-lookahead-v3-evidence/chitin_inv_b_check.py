"""Invariant lens check for candidate B (Opponent frequency bias stacked on Lookahead).

Read-only toward the repo: patched copies live under scratchpad/chitin_inv_b/.
"""

import copy
import ctypes
import importlib.util
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

if sys.platform == "win32":  # BelowNormal for this process and children
    ctypes.windll.kernel32.SetPriorityClass(
        ctypes.windll.kernel32.GetCurrentProcess(), 0x4000
    )
sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(r"C:\Users\rmanov\algorithmic-arts")
SRC = REPO / "CHITIN" / "battle_evolution.py"
OUT = Path(__file__).resolve().parent / "chitin_inv_b"
text = SRC.read_text(encoding="utf-8")
lines = text.splitlines(keepends=True)
old_block = "".join(lines[462:475])  # file lines 463..475
assert old_block.lstrip().startswith("elif method=='Opponent':"), old_block[:60]
assert (
    "elif method=='Lookahead': scores,reason=self._lookahead(a,s,scores)" in lines[474]
)
assert text.count(old_block) == 1

METHOD = """    def _opponent_bias(self,f,s,scores,stat):
        observed=sum(f.opponent)-8
        concentration=max(f.opponent)/sum(f.opponent)
        if not (observed>=16 and concentration>.25 and s['enemy']): return None
        predicted=max(range(8),key=lambda i:f.opponent[i])
        if predicted in (0,1): scores[2]+=.65; scores[6]+=.8
        elif predicted==2: scores[4]+=.9; scores[5]+=.5
        elif predicted==3: scores[6]+=.7
        elif predicted in (4,7): scores[5]+=.9
        self.stats[stat]+=1
        return predicted

"""
OPP = (
    "            elif method=='Opponent':\n"
    "                predicted=self._opponent_bias(f,s,scores,'opponent_predictions')\n"
    "                if predicted is not None: reason=f'opponent frequency model → {ACTIONS[predicted]}'\n"
    "                else: reason='uncertain opponent → diversified utility'\n"
)
LA_OLD = (
    "            elif method=='Lookahead': scores,reason=self._lookahead(a,s,scores)\n"
)
LA_NEW = (
    "            elif method=='Lookahead':\n"
    "                scores,reason=self._lookahead(a,s,scores)\n"
    "                predicted=self._opponent_bias(f,s,scores,'lookahead_opponent_bias')\n"
    "                if predicted is not None: reason+=' · observed-frequency counter → '+ACTIONS[predicted]\n"
)
CHOOSE = "    def _choose(self,a,s):\n"
assert text.count(CHOOSE) == 1


def build(lookahead):
    t = text.replace(old_block, OPP + (LA_NEW if lookahead else LA_OLD))
    return t.replace(CHOOSE, METHOD + CHOOSE)


SRC_B, SRC_B0 = build(True), build(False)
print("patch B touched lines (diff size):", len(SRC_B.splitlines()) - len(lines))


def load(name, source_text, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source_text, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


if OUT.exists():
    shutil.rmtree(OUT)
B = load("chitin_b", SRC_B, OUT / "CHITIN" / "battle_evolution.py")
B0 = load("chitin_b0", SRC_B0, OUT / "b0" / "battle_evolution.py")
spec = importlib.util.spec_from_file_location("chitin_base", SRC)
BASE = importlib.util.module_from_spec(spec)
sys.modules["chitin_base"] = BASE
spec.loader.exec_module(BASE)

# 6) 38 regression tests against the patched copy (tests resolve SOURCE relative to __file__)
(OUT / "tests").mkdir(parents=True, exist_ok=True)
for t in (REPO / "tests").glob("test_chitin*.py"):
    shutil.copy(t, OUT / "tests" / t.name)
r = subprocess.run(
    [
        sys.executable,
        "-B",
        "-m",
        "unittest",
        "discover",
        "-s",
        "tests",
        "-p",
        "test_chitin*.py",
    ],
    cwd=OUT,
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
)
print("unittest on patched B:", r.stderr.strip().splitlines()[-3:])
sc = B.self_check()
print("self_check patched B:", sum(sc.values()), "/", len(sc))


def run(
    mod, seed, steps, max_agents=60, episode_ticks=1500, learning=True, probe=False
):
    w = mod.BattleWorld(
        seed=seed, max_agents=max_agents, episode_ticks=episode_ticks, learning=learning
    )
    stats = {"calls": 0, "fired": 0, "flipped": 0}
    if probe:
        orig = mod.BattleWorld._opponent_bias

        def wrapped(self, f, s, scores, stat):
            if stat != "lookahead_opponent_bias":
                return orig(self, f, s, scores, stat)
            a = sys._getframe(1).f_locals["a"]
            elig = self.eligible_indices(a, s)
            before = max(elig, key=lambda i: scores[i]) if elig else None
            res = orig(self, f, s, scores, stat)
            stats["calls"] += 1
            if res is not None:
                stats["fired"] += 1
                after = max(elig, key=lambda i: scores[i]) if elig else None
                stats["flipped"] += before != after
            return res

        mod.BattleWorld._opponent_bias = wrapped
    t0 = time.perf_counter()
    try:
        for _ in range(steps):
            w.step()
    finally:
        if probe:
            mod.BattleWorld._opponent_bias = orig
    return w, time.perf_counter() - t0, stats


def js(w):
    return json.dumps(w.export(), sort_keys=True, allow_nan=False, ensure_ascii=False)


# 2) determinism, same seed, patched B
for seed, steps, ep in ((31, 520, 240), (101, 1500, 1500)):
    a, _, _ = run(B, seed, steps, episode_ticks=ep)
    b, _, _ = run(B, seed, steps, episode_ticks=ep)
    print(
        f"B determinism seed {seed}/{steps}: export bytes equal={js(a) == js(b)} ledger_error={a.last_ledger_error:.3g}"
    )

# 3) non-vacuity + B0 byte identity (Opponent refactor alone must not change anything)
base, tb, _ = run(BASE, 101, 1500)
b0, _, _ = run(B0, 101, 1500)
pb, tpb, st = run(B, 101, 1500, probe=True)
print("B0 (refactor only) export == BASE:", js(b0) == js(base))
print(
    "B export != BASE:",
    js(pb) != js(base),
    "| lookahead_opponent_bias:",
    pb.stats["lookahead_opponent_bias"],
    "| probe calls/fired/flipped-argmax:",
    st,
)
print(
    "opponent_predictions BASE vs B0:",
    base.stats["opponent_predictions"],
    b0.stats["opponent_predictions"],
)

# 4) metal + 7) bounded containers after a long run
lw, _, st6 = run(B, 202, 6000, probe=True)
print(
    f"B 6000 ticks seed 202: ledger_error={lw.last_ledger_error:.3g} episodes={lw.episode} probe={st6}"
)
print(
    "  max len(observed_decisions)=",
    max(len(f.observed_decisions) for f in lw.factions),
    "(cap trigger",
    2 * lw.max_agents,
    ")",
    "| max sum(opponent)=",
    round(max(sum(f.opponent) for f in lw.factions), 1),
    "| stats keys=",
    len(lw.stats),
    "| forecasts",
    len(lw.forecasts),
    "| ledger outcomes",
    len(lw.forecaster.outcomes),
    len(lw.forecaster.validation_outcomes),
)

# 5) RNG neutrality of a decision with the gate forced open vs closed, same state
w = B.BattleWorld(seed=17001, max_agents=60, auto=False)
for _ in range(40):
    w.step()
la = [a for a in w.agents if w.factions[a.faction].method == "Lookahead"]
cand = (
    next(a for a in la if w._sense(a)["enemy"] is not None)
    if any(w._sense(a)["enemy"] for a in la)
    else None
)
if cand is None:
    a0 = la[0]
    e0 = next(x for x in w.agents if x.faction != a0.faction)
    e0.x, e0.y = a0.x + 3, a0.y
    w._rebuild_grid()
    cand = a0
res = {}
for label, hist in (
    ("closed", [1.0] * 8),
    ("open", [1.0, 1.0, 30.0, 1.0, 1.0, 1.0, 1.0, 1.0]),
):
    wc = copy.deepcopy(w)
    ac = next(x for x in wc.agents if x.uid == cand.uid)
    wc.factions[ac.faction].opponent = list(hist)
    s = wc._sense(ac)
    r0, t0 = wc.rng.getstate(), wc.tie_rng.getstate()
    wc._choose(ac, s)
    res[label] = (
        wc.rng.getstate(),
        wc.tie_rng.getstate(),
        ac.action,
        wc.stats["lookahead_opponent_bias"],
        ac.trace["reason"],
    )
print(
    "RNG after _choose closed==open:",
    res["closed"][0] == res["open"][0],
    "| tie_rng equal:",
    res["closed"][1] == res["open"][1],
    "| actions:",
    res["closed"][2],
    "->",
    res["open"][2],
    "| bias fired open:",
    res["open"][3],
)
print(
    "  open reason len",
    len(res["open"][4]),
    "| GUI card shows reason[:82] ->",
    repr(res["open"][4][:82][-30:]),
    "| suffix visible:",
    "observed-frequency" in res["open"][4][:82],
)

# 7) timing, interleaved
tb_, tB_ = [], []
for _ in range(3):
    tb_.append(run(BASE, 303, 2000)[1])
    tB_.append(run(B, 303, 2000)[1])
med = lambda v: sorted(v)[len(v) // 2]
print(
    "2000 ticks seed 303 BASE",
    [round(x, 2) for x in tb_],
    "B",
    [round(x, 2) for x in tB_],
    f"median delta {100 * (med(tB_) / med(tb_) - 1):+.1f}%",
)
import timeit

wb = B.BattleWorld(seed=5, auto=False)
f = wb.factions[5]
f.opponent = [1.0, 1.0, 30.0, 1.0, 1.0, 1.0, 1.0, 1.0]
s = {"enemy": wb.agents[0]}
sc8 = [0.0] * 8
n = 200000
dt = timeit.timeit(lambda: wb._opponent_bias(f, s, sc8, "x"), number=n)
print(f"_opponent_bias per call: {dt / n * 1e6:.2f} us")
