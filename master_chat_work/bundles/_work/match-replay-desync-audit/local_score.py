"""Local tests-channel scorer for match-replay-desync-audit.

Usage: python3 local_score.py <tests_dir> <data_dir> <program.py> <result_file>

Runs the program once on the shipped data into a scratch out dir (as the agent
would leave /app/out), then imports <tests_dir>/test_output.py with a stand-in
rewardkit, points its out root at the scratch dir and runs every test with the
weights the module itself registers. Writes `PASS name` / `FAIL name :: msg`
lines plus a SCORE line: positive points earned, negatives fired, P, share.
"""

import importlib.util
import shutil
import subprocess
import sys
import tempfile
import types
from pathlib import Path

tests_dir, data_dir, program, result_file = (Path(a) for a in sys.argv[1:5])

WEIGHTS = {}


class _Criteria:
    def __getattr__(self, name):
        def register(weight):
            WEIGHTS[name] = weight
        return register


def criterion(description=""):
    def wrap(func):
        return func
    return wrap


fake = types.ModuleType("rewardkit")
fake.criteria = _Criteria()
fake.criterion = criterion
sys.modules["rewardkit"] = fake

scratch = Path(tempfile.mkdtemp(prefix="mrda-score-"))
out = scratch / "out"
out.mkdir()
shutil.copy(program, out / "optimize.py")
run = subprocess.run([sys.executable, str(out / "optimize.py"), str(data_dir), str(out)],
                     capture_output=True, text=True)
spec = importlib.util.spec_from_file_location("test_output_local", tests_dir / "test_output.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module._out_root = lambda: out

lines = ["# shipped run exit %d %s" % (run.returncode, run.stderr[-300:].replace("\n", " "))]
earned = 0
fired = 0
positive = sum(w for w in WEIGHTS.values() if w > 0)
for name, weight in WEIGHTS.items():
    test = getattr(module, "test_" + name, None) or getattr(module, "test_negative_weight_" + name[len("negative_"):])
    try:
        test()
        ok = True
        msg = ""
    except BaseException as error:  # the grader treats any raise as a fail
        ok = False
        msg = ("%s: %s" % (type(error).__name__, error)).replace("\n", " ")[:300]
    if ok:
        lines.append("PASS test_%s" % name)
        if weight > 0:
            earned += weight
        else:
            fired += weight
    else:
        lines.append("FAIL test_%s :: %s" % (name, msg))
total = max(0, earned + fired)
lines.append("SCORE earned=%d negatives=%d P=%d share=%.4f checks=%d"
             % (earned, fired, positive, total / positive, len(WEIGHTS)))
result_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(lines[-1])
shutil.rmtree(scratch, ignore_errors=True)
for bundle in module._STAGE_CACHE.values():
    shutil.rmtree(bundle["room"], ignore_errors=True)
