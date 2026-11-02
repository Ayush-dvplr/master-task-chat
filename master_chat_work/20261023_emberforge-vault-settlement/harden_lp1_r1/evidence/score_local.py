"""Tests-channel score of a program against a bundle's tests/test_output.py, run locally.

usage: python3 score_local.py <bundle> <program.py> [label]

The grader module is imported with a stub rewardkit that records each
criterion's registered weight. The program is staged as /app/out/settle_vault.py
equivalent in a temp app folder and run on the shipped (visible) corpus first,
as the agent would have left it. Checks that touch the real /app/data path are
reported as NOT_RUN and scored in the program's favour (positive passes,
negative does not fire).
"""
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
import types

bundle, program = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
label = sys.argv[3] if len(sys.argv) > 3 else program.name

registry = []


class _Criteria:
    def __getattr__(self, name):
        def register(weight=1, **_kw):
            registry.append((name, weight))
        return register


def _criterion(description="", **_kw):
    def wrap(fn):
        fn.description = description
        return fn
    return wrap


stub = types.ModuleType("rewardkit")
stub.criteria = _Criteria()
stub.criterion = _criterion
sys.modules["rewardkit"] = stub
sys.path.insert(0, str(bundle / "tests"))
import test_output as T  # noqa: E402

app = pathlib.Path(tempfile.mkdtemp(prefix="score_app_"))
out = app / "out"
out.mkdir()
shutil.copyfile(program, out / "settle_vault.py")
T.OUT = out
T.PROGRAM = out / "settle_vault.py"
vis = T._visible_corpus()
r = subprocess.run([sys.executable, str(T.PROGRAM), str(vis), str(out)], capture_output=True, text=True)
first_run = "rc=%d %s" % (r.returncode, (r.stderr or "")[-300:].strip())

TOUCHES_APP_DATA = {"structure_program_takes_directories", "negative_reads_training_corpus_at_runtime"}
rows = []
pos_total = sum(w for _n, w in registry if w > 0)
earned = 0.0
for name, weight in registry:
    t0 = time.time()
    if name in TOUCHES_APP_DATA:
        ok, status = (weight > 0), "NOT_RUN"
    else:
        val = float(getattr(T, name)(None))
        ok = val > 0
        status = ("PASS" if val == 1 else "PART %.2f" % val) if ok else "FAIL"
        if weight < 0:
            status = "FIRES" if ok else "quiet"
    if name in TOUCHES_APP_DATA:
        val = 1.0 if ok else 0.0
    earned += weight * val
    rows.append({"name": name, "weight": weight, "status": status, "secs": round(time.time() - t0, 1)})

score = max(0.0, earned) / pos_total
print(json.dumps({"label": label, "first_run": first_run, "earned": earned, "positive_total": pos_total,
                  "score": round(score, 4), "rows": rows}, indent=1))
