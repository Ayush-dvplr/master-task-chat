"""After repair: (1) every wide optimum comes from _WIDE_TRUTH (_exact never called on wide roots);
(2) new tests' expected() equals the pre-edit tests' expected() (bounded truth) on shipped, H1, H2 and wide0..3."""
import importlib.util
import json
import sys
import time
from pathlib import Path

WORK = Path(__file__).resolve().parent.parent
BUNDLE = WORK.parent.parent / "district-heat-flex-procurement"
sys.path.insert(0, str(WORK / "stub"))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


new = load("tq_new", BUNDLE / "tests/test_output.py")
old = load("tq_old", WORK / "p12q2/src_before/tests_test_output.py")
calls = [0]
real = new._exact


def counting(*a):
    calls[0] += 1
    return real(*a)


new._exact = counting
roots = {"shipped": new.visible_root(), "H1": new.hidden_root("H1"), "H2": new.hidden_root("H2")}
for k in range(4):
    roots[f"wide{k}"] = new.wide_root(k)[0]
bad = 0
for name, root in roots.items():
    calls[0] = 0
    t0 = time.perf_counter()
    got = new.expected(root)
    t1 = time.perf_counter()
    want = old.expected(root)
    t2 = time.perf_counter()
    same = json.dumps(got, sort_keys=True) == json.dumps(want, sort_keys=True)
    bad += not same or (name.startswith("wide") and calls[0] != 0)
    print(f"{name}: same={same} exact_calls={calls[0]} new {t1 - t0:.1f}s old {t2 - t1:.1f}s", flush=True)
print("CHECK", "OK" if bad == 0 else f"BAD {bad}")
