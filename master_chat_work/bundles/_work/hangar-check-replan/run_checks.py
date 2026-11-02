"""Run every check of /tests/test_output.py directly (no judge); print one line per check and the test score."""
import importlib.util
import re
import sys
import os
import time

path = sys.argv[1] if len(sys.argv) > 1 else "/tests/test_output.py"
src = open(path).read()
spec = importlib.util.spec_from_file_location("test_output", path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
pairs = re.findall(r"def (\w+)\(workspace: Path\) -> bool:\n    return _holds\((.+)\)\n", src)
weights = dict((n, int(w)) for n, w in re.findall(r"criteria\.(\w+)\(weight=(-?\d+)\)", src))
pos = sum(w for w in weights.values() if w > 0)
score = 0
only = re.compile(os.environ.get("ONLY", ""))
for name, call in pairs:
    if not only.search(name):
        continue
    t = time.time()
    fn = eval(call, vars(mod))
    try:
        fn()
        ok, msg = True, ""
    except Exception as exc:
        ok, msg = False, ("%s: %s" % (type(exc).__name__, exc))[:300]
    w = weights[name]
    if ok:
        score += w
    print("CHK %-45s w=%3d %s %.1fs %s" % (name, w, "HOLD" if ok else "FAIL", time.time() - t, msg), flush=True)
print("TESTS %d/%d = %.4f" % (score, pos, max(0, score) / pos))
print("ALL_DONE")
