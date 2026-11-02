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

before = sorted((p.name, p.read_bytes()) for p in out.iterdir())
for test_name in sys.argv[5:]:
    try:
        getattr(module, test_name)()
        print(test_name, "FIRED (returned)")
    except BaseException as error:
        print(test_name, "no fire:", type(error).__name__, str(error)[:200])
after = sorted((p.name, p.read_bytes()) for p in out.iterdir())
print("out root restored byte for byte:", before == after)
shutil.rmtree(scratch, ignore_errors=True)
for bundle in module._STAGE_CACHE.values():
    shutil.rmtree(bundle["room"], ignore_errors=True)
