"""Score many programs against tests/test_output.py, building every data folder once.

Usage (inside the test image, as root, shipped data at /app/data):
    python3 -B score_many.py /tests/test_output.py PROG_DIR name1 name2 ...
name "oracle" means /solution/solve.py. Prints `CHK prog check w HOLD|FAIL msg`, then
`SCORE prog tests=x/129 lever=...` and ALL_DONE.
"""
import importlib.util
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

test_path, prog_dir, names = sys.argv[1], Path(sys.argv[2]), sys.argv[3:]
src = open(test_path).read()
spec = importlib.util.spec_from_file_location("test_output", test_path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
pairs = re.findall(r"def (\w+)\(workspace: Path\) -> bool:\n    return _holds\((.+)\)\n", src)
weights = dict((n, int(w)) for n, w in re.findall(r"criteria\.(\w+)\(weight=(-?\d+)\)", src))
pos = sum(w for w in weights.values() if w > 0)
OUT = Path("/app/out")


def install(name):
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    if name == "oracle":
        shutil.copyfile("/solution/solve.py", OUT / "derive_report.py")
    else:
        shutil.copyfile(prog_dir / (name + ".py"), OUT / "derive_report.py")
        if name == "e8e9c82_adapted":
            shutil.copyfile(prog_dir / "e8e9c82_program.py", OUT / "e8e9c82_program.py")
    subprocess.run([sys.executable, str(OUT / "derive_report.py"), "/app/data", str(OUT)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)


for name in names:
    t0 = time.time()
    install(name)
    for key, case in list(mod._CASES.items()):
        if key == "shipped" or "want" not in case:
            continue
        case.pop("error", None)
        try:
            case["stray"] = []
            case["got"] = mod._run_program(case["data"], Path(tempfile.mkdtemp(prefix="hangar-run-")), case["stray"])
        except Exception as exc:
            case["error"] = "%s: %s" % (type(exc).__name__, exc)
    score, lost = 0, []
    for check, call in pairs:
        fn = eval(call, vars(mod))
        try:
            fn()
            ok, msg = True, ""
        except Exception as exc:
            ok, msg = False, ("%s: %s" % (type(exc).__name__, exc))[:200]
        w = weights[check]
        if ok and w > 0:
            score += w
        if ok and w < 0:
            score += w
        print("CHK %s %s %d %s %s" % (name, check, w, "HOLD" if ok else "FAIL", msg), flush=True)
    print("SCORE %s tests=%d/%d %.1f%% sec=%.0f" % (name, max(0, score), pos, 100.0 * max(0, score) / pos,
                                                  time.time() - t0), flush=True)
print("ALL_DONE")
