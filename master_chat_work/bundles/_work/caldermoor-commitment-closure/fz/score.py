"""Score one delivered program against the real tests/test_output.py (inside the verifier image).

usage: python3 score.py <program.py> <tests_dir> [label]
Mounts expected: /app/data (shipped extract, read-only). Writes /app/out.
"""
import json
import os
import re
import shutil
import subprocess
import sys

prog, tests = sys.argv[1], sys.argv[2]
label = sys.argv[3] if len(sys.argv) > 3 else os.path.basename(os.path.dirname(prog))
shutil.rmtree("/app/out", ignore_errors=True)
os.makedirs("/app/out")
shutil.copy(prog, "/app/out/reconcile.py")
run = subprocess.run([sys.executable, "/app/out/reconcile.py", "/app/data", "/app/out"],
                     capture_output=True, text=True)
sys.path.insert(0, tests)
import test_output as T  # noqa: E402

src = open(os.path.join(tests, "test_output.py")).read()
weights = [(n, int(w)) for n, w in re.findall(r"^criteria\.(\w+)\(weight=(-?\d+)\)", src, re.M)]
target = dict(re.findall(r"def (\w+)\(workspace: Path\) -> bool:\n(?:    #[^\n]*\n)*    return _passes\((\w+)\)", src))
P = sum(w for _n, w in weights if w > 0)
earned, failed, fired, msgs = 0, [], [], {}
for name, w in weights:
    fn = getattr(T, target[name])
    try:
        fn()
        ok = True
    except BaseException as exc:  # noqa: BLE001
        ok = False
        msgs[name] = str(exc)[:300]
    if w > 0:
        if ok:
            earned += w
        else:
            failed.append((name, w))
    elif ok:
        fired.append((name, w))
neg = sum(w for _n, w in fired)
print(json.dumps({
    "label": label, "exit": run.returncode, "P": P, "earned": earned,
    "share": round(earned / P, 4), "reward": round(max(0, earned + neg) / P, 4),
    "failed": failed, "neg_fired": fired,
    "msgs": {k: v for k, v in msgs.items() if k in dict(failed)},
}))
