"""CHITIN Lookahead V3, Stage 1 lane (plan section 4, commands 1-2): BelowNormal, blocks in sequence.

Lane i runs blocks[i::3] of seeds 3001-3195 (15 seeds x learning ON/OFF per block); lane 1 first runs the
determinism twin of seed 3001 (command 2). Each block refuses to start if the source SHA256 changed.
Writes <raw>/<name>.json, <name>.log and lane<i>.log (wall and CPU seconds per block).
"""

import ctypes
import datetime as dt
import hashlib
import subprocess
import sys
import time
from pathlib import Path

PY = r"C:\Users\rmanov\AppData\Local\Programs\Python\Python314\python.exe"
SRC = Path(r"C:\Users\rmanov\algorithmic-arts\CHITIN\battle_evolution.py")
RAW = Path(
    r"C:\Users\rmanov\Downloads\CHITIN-2.0.1-20261026\CHITIN\reports\cmp_20261027"
)
SHA = "a8f7f74ab9ca00d24369c985281b5340d2df461d14cd364a5c33e57fda2849fe"
BLOCKS = (3001, 3016, 3031, 3046, 3061, 3076, 3091, 3106, 3121, 3136, 3151, 3166, 3181)
BELOW_NORMAL = 0x4000


class FILETIME(ctypes.Structure):
    _fields_ = [("lo", ctypes.c_uint32), ("hi", ctypes.c_uint32)]


kernel = ctypes.WinDLL("kernel32", use_last_error=True)
kernel.GetCurrentProcess.restype = ctypes.c_void_p
kernel.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
kernel.GetProcessTimes.argtypes = [ctypes.c_void_p] + [ctypes.POINTER(FILETIME)] * 4
kernel.SetPriorityClass(kernel.GetCurrentProcess(), BELOW_NORMAL)


def cpu_seconds(handle):
    t = [FILETIME() for _ in range(4)]
    kernel.GetProcessTimes(handle, *[ctypes.byref(x) for x in t])
    return sum((x.hi << 32 | x.lo) for x in t[2:]) / 1e7


def done(name):
    log = RAW / f"{name}.log"
    return (
        (RAW / f"{name}.json").exists()
        and log.exists()
        and b"\nSaved " in b"\n" + log.read_bytes()
    )


lane = int(sys.argv[1])
jobs = [("det_3001", 3001, 1)] if lane == 1 else []
jobs += [(f"cmp_v3_{s}", s, 15) for s in BLOCKS[lane::3]]
lane_t0 = time.perf_counter()
with (RAW / f"lane{lane}.log").open("a", encoding="utf-8") as lane_log:
    for name, seed, trials in jobs:
        if done(name):
            continue
        if time.perf_counter() - lane_t0 > 18 * 60:
            # A background task may be cut at ~30 min: never start a block that could straddle it.
            lane_log.write(
                f"{name} PAUSED after 18 min of lane time; resume this lane\n"
            )
            raise SystemExit(3)
        if hashlib.sha256(SRC.read_bytes()).hexdigest() != SHA:
            lane_log.write(f"{name} REFUSED: source SHA changed, BASE arm invalid\n")
            raise SystemExit(2)
        start = dt.datetime.now().isoformat(timespec="seconds")
        t0 = time.perf_counter()
        with (RAW / f"{name}.log").open("wb") as log:
            p = subprocess.Popen(
                [
                    PY,
                    "-I",
                    "-B",
                    str(SRC),
                    "--headless",
                    "--seed",
                    str(seed),
                    "--steps",
                    "6000",
                    "--trials",
                    str(trials),
                    "--compare-learning",
                    "--max-agents",
                    "60",
                    "--episode-ticks",
                    "1500",
                    "--output",
                    str(RAW / f"{name}.json"),
                ],
                stdout=log,
                stderr=subprocess.STDOUT,
                creationflags=BELOW_NORMAL,
            )
            rc = p.wait()
            cpu = cpu_seconds(int(p._handle))
        lane_log.write(
            f"{name} start {start} end {dt.datetime.now().isoformat(timespec='seconds')} rc {rc} "
            f"wall {time.perf_counter() - t0:.1f}s cpu {cpu:.1f}s\n"
        )
        lane_log.flush()
