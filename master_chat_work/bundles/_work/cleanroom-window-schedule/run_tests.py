"""Local runner for BUNDLE/tests/test_output.py with a stub rewardkit (WORK only).

usage: python3 -B run_tests.py <program.py> [--json result.json]
Copies the program to a scratch /app/out stand-in, runs it on the shipped data there,
then evaluates every criterion and prints pass/fail, weight and the tests score."""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import types
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
BUNDLE = HERE.parent.parent / "cleanroom-window-schedule"
REGISTRY, WEIGHTS = {}, {}


def stub():
    mod = types.ModuleType("rewardkit")

    def criterion(description=""):
        def wrap(fn):
            REGISTRY[fn.__name__] = (fn, description)
            return fn
        return wrap

    class Criteria:
        def __getattr__(self, name):
            def set_weight(weight):
                WEIGHTS[name] = weight
            return set_weight

    mod.criterion = criterion
    mod.criteria = Criteria()
    sys.modules["rewardkit"] = mod


def main():
    program = Path(sys.argv[1]).resolve()
    dump = sys.argv[sys.argv.index("--json") + 1] if "--json" in sys.argv else None
    stub()
    spec = importlib.util.spec_from_file_location("test_output", BUNDLE / "tests" / "test_output.py")
    t = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(t)
    work = Path(tempfile.mkdtemp(prefix="cwout"))
    out = work / "out"
    out.mkdir()
    shutil.copy(program, out / "derive_report.py")
    t.OUT = out
    t.SCRIPT = out / "derive_report.py"
    t0 = time.time()
    proc = subprocess.run([sys.executable, "-B", str(t.SCRIPT), str(BUNDLE / "environment" / "data"), str(out)],
                          capture_output=True, text=True, timeout=2 * 415)
    shipped_s = time.time() - t0
    rows, pos, got = [], 0, 0
    for name, w in WEIGHTS.items():
        fn = REGISTRY[name][0]
        t1 = time.time()
        ok = fn(work)
        rows.append((name, w, ok, round(time.time() - t1, 2)))
        if w > 0:
            pos += w
        if ok:
            got += w
    for r in rows:
        print("%-42s %3d %-5s %6.2fs" % r)
    score = max(0, got) / pos
    print("shipped run exit %d %.2fs; tests score %.4f (%d/%d)" % (proc.returncode, shipped_s, score, got, pos))
    if proc.returncode:
        print(proc.stderr[-2000:])
    if dump:
        json.dump({"rows": rows, "score": score, "shipped_s": shipped_s}, open(dump, "w"), indent=1)
    shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
