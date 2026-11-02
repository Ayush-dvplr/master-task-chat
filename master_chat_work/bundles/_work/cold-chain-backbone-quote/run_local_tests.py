"""Run tests/test_output.py locally with a stub rewardkit. Usage: run_local_tests.py <app_root> [test file]"""
import importlib.util
import json
import os
import sys
import time
import types
from pathlib import Path

WEIGHTS = {}
FUNCS = {}


class _Criteria:
    def __getattr__(self, name):
        def register(weight):
            WEIGHTS[name] = weight
        return register


def criterion(description):
    def wrap(fn):
        FUNCS[fn.__name__] = fn
        return fn
    return wrap


stub = types.ModuleType("rewardkit")
stub.criteria = _Criteria()
stub.criterion = criterion
sys.modules["rewardkit"] = stub

app = Path(sys.argv[1]).resolve()
os.environ["APP_ROOT"] = str(app)
test_file = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(
    "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/cold-chain-backbone-quote/tests/test_output.py")
spec = importlib.util.spec_from_file_location("test_output", test_file)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

earned = 0
positive = sum(w for w in WEIGHTS.values() if w > 0)
results = {}
for name, weight in WEIGHTS.items():
    start = time.time()
    ok = bool(FUNCS[name](app))
    results[name] = ok
    if ok:
        earned += weight
    print(f"{name:36s} w={weight:3d} {'PASS' if ok else 'fail'} {time.time() - start:6.1f}s", flush=True)
print(f"SCORE {earned}/{positive} = {earned / positive:.4f}")
print("RESULTS " + json.dumps(results, sort_keys=True))
