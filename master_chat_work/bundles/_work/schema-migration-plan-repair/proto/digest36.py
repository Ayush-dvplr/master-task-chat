"""Scratch: digest of every hidden input and expectation the tests build (worlds 01-28, ladders, cases).

    python3 -B digest.py [SRC]   # prints one line per item and a total digest
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

WORK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORK / "rewardkit_stub"))
src = Path(sys.argv[1]) if len(sys.argv) > 1 else WORK / "test_output.src.py"
spec = importlib.util.spec_from_file_location("tests_src", src)
T = importlib.util.module_from_spec(spec)
spec.loader.exec_module(T)


def h(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=lambda o: sorted(o) if isinstance(o, (set, frozenset)) else o.__dict__).encode()).hexdigest()[:16]


total = hashlib.sha256()
names = [n for n in T.WORLDS if int(n.split("_")[1]) <= 36]
for name in names:
    line = f"{name} input={h(T._world(name))} expected={h(T._world_expected(name))}"
    print(line)
    total.update(line.encode())
for name in T.LADDERS:
    s, job, exp = T.case_ladder(name)
    line = f"{name} input={h(s)} expected={h(exp)}"
    print(line)
    total.update(line.encode())
for build in (T.case_revisit, T.case_tie_first_edge):
    s, job, exp = build()
    line = f"{build.__name__} expected={h(exp)}"
    print(line)
    total.update(line.encode())
print("TOTAL", total.hexdigest())
