"""Score one delivered program on the final tests/test_output.py with a stub rewardkit.

Prints one line per check (PASS, WRONG, TIMEOUT, CRASH), the program's seconds per
input set it was run on, the lever split and a `## SCORE` line over positive weight.
"""
import contextlib
import importlib.util
import io
import sys
import time
import types
from pathlib import Path

REG, WEIGHTS = {}, {}


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


stub = types.ModuleType("rewardkit")
stub.criterion = criterion
stub.criteria = _Criteria()
sys.modules["rewardkit"] = stub

spec = importlib.util.spec_from_file_location("test_output", sys.argv[1])
tm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tm)

RUNS = {}
_current = ["?"]
_memo_orig = tm._memo
_run_orig = tm._run_program


def _memo(key, build):
    previous = _current[0]
    _current[0] = key
    try:
        return _memo_orig(key, build)
    finally:
        _current[0] = previous


def _run_program(data, workdir=None):
    start = time.time()
    result = _run_orig(data, workdir)
    RUNS[_current[0]] = (time.time() - start, result["returncode"], result["note"])
    return result


tm._memo = _memo
tm._run_program = _run_program


def lever(name):
    return name.startswith(("h2_", "h3_")) and not name.endswith("_data_quality")


pos = sum(w for w in WEIGHTS.values() if w > 0)
got = neg = 0
lost = {"WRONG": 0, "TIMEOUT": 0, "CRASH": 0}
hidden_lost = dict(lost)
t0 = time.time()
for name, w in WEIGHTS.items():
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        ok = bool(REG[name](Path("/app")))
    text = buf.getvalue().strip().replace("\n", " ")
    if w < 0:
        status = "FIRED" if ok else "silent"
        neg += w if ok else 0
    elif ok:
        status = "PASS"
        got += w
    elif "did not finish" in text:
        status = "TIMEOUT"
    elif "exit status" in text:
        status = "CRASH"
    else:
        status = "WRONG"
    if w > 0 and not ok:
        if lever(name):
            lost[status] += w
        if name.startswith(("h2_", "h3_")):
            hidden_lost[status] += w
    print("CHECK %-34s w=%2d %-7s %s" % (name, w, status, text[:160]), flush=True)

for key, (secs, rc, note) in sorted(RUNS.items()):
    print("RUN %-10s %6.1fs rc=%s %s" % (key, secs, rc, note))
total_lost = sum(lost.values())
print("LEVER points (hidden region/policy_audit/segment/summary, 68): lost %d = WRONG %d, TIMEOUT %d, CRASH %d"
      % (total_lost, lost["WRONG"], lost["TIMEOUT"], lost["CRASH"]))
print("HIDDEN points (74): lost %d = WRONG %d, TIMEOUT %d, CRASH %d"
      % (sum(hidden_lost.values()), hidden_lost["WRONG"], hidden_lost["TIMEOUT"], hidden_lost["CRASH"]))
print("NEGATIVES fired: %d" % neg)
print("## SCORE %d/%d = %.4f (negatives %d) total %.1fs" % (got, pos, got / pos, neg, time.time() - t0))
