import ctypes, importlib.util, sys

ctypes.windll.kernel32.SetPriorityClass(
    ctypes.windll.kernel32.GetCurrentProcess(), 0x4000
)
from pathlib import Path

p = Path(__file__).resolve().parent / "chitin_inv_b" / "CHITIN" / "battle_evolution.py"
spec = importlib.util.spec_from_file_location("chitin_b", p)
B = importlib.util.module_from_spec(spec)
sys.modules["chitin_b"] = B
spec.loader.exec_module(B)
w = B.BattleWorld(seed=202, max_agents=60, episode_ticks=1500)
mo = ms = 0
mpop = 0
la_pop = 0
for _ in range(6000):
    w.step()
    mo = max(mo, max(len(f.observed_decisions) for f in w.factions))
    ms = max(ms, max(sum(f.opponent) for f in w.factions))
    mpop = max(mpop, len(w.agents))
    la = next(f.id for f in w.factions if f.method == "Lookahead")
    la_pop = max(la_pop, sum(a.faction == la for a in w.agents))
print(
    f"over 6000 ticks: max len(observed_decisions)={mo} (prune at >{2 * w.max_agents}), max sum(opponent)={ms:.1f} (leak at >240), max population={mpop}, max Lookahead pop={la_pop}, ledger_error={w.last_ledger_error:.3g}, lookahead_opponent_bias={w.stats['lookahead_opponent_bias']}"
)
