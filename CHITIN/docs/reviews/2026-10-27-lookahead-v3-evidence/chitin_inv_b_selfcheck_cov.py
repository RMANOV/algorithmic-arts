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
w = B.BattleWorld(seed=31, max_agents=60, episode_ticks=240)
for _ in range(520):
    w.step()
print(
    "self_check replay world (seed31/520/ep240): lookahead_opponent_bias =",
    w.stats["lookahead_opponent_bias"],
    "| opponent_predictions =",
    w.stats["opponent_predictions"],
)
