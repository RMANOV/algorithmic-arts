"""Lower this process to BelowNormal, then run a module or script (review harness)."""

import ctypes
import runpy
import sys

BELOW_NORMAL_PRIORITY_CLASS = 0x4000
kernel = ctypes.WinDLL("kernel32", use_last_error=True)
kernel.GetCurrentProcess.restype = ctypes.c_void_p
kernel.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
kernel.SetPriorityClass(kernel.GetCurrentProcess(), BELOW_NORMAL_PRIORITY_CLASS)
mode, target, *rest = sys.argv[1:]
sys.argv = [target, *rest]
if mode == "-m":
    runpy.run_module(target, run_name="__main__", alter_sys=True)
else:
    runpy.run_path(target, run_name="__main__")
