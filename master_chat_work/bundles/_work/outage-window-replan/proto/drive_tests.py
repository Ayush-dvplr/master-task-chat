"""Run every criterion of /tests/test_output.py with a stub rewardkit; print per-check result and score."""
import importlib.util
import sys
import time
import types
from pathlib import Path

REG = {}
WEIGHTS = {}


def criterion(description=""):
    def deco(fn):
        REG[fn.__name__] = fn
        return fn
    return deco


class _Criteria:
    def __getattr__(self, name):
        def register(weight):
            WEIGHTS[name] = weight
        return register


mod = types.ModuleType("rewardkit")
mod.criterion = criterion
mod.criteria = _Criteria()
sys.modules["rewardkit"] = mod

spec = importlib.util.spec_from_file_location("test_output", sys.argv[1] if len(sys.argv) > 1 else "/tests/test_output.py")
tm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tm)

t0 = time.time()
got = 0
pos = sum(w for w in WEIGHTS.values() if w > 0)
for name, w in WEIGHTS.items():
    s = time.time()
    ok = bool(REG[name](Path("/app")))
    if ok and w > 0:
        got += w
    print("CHECK %-28s w=%2d %s %.1fs" % (name, w, "PASS" if ok else "FAIL", time.time() - s), flush=True)
print("SCORE %d/%d = %.4f total %.1fs" % (got, pos, got / pos, time.time() - t0))
