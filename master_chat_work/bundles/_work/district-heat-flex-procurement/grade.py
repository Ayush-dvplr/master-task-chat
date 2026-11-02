"""Grade a workspace with the real test_output.py through the local rewardkit stand-in.

Usage: python3 grade.py TEST_OUTPUT_PY WORKSPACE [--json]
Prints each check result and the test-channel fraction (earned / positive total).
"""
import importlib.util
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "stub"))
import rewardkit  # noqa: E402

spec = importlib.util.spec_from_file_location("test_output", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
ws = Path(sys.argv[2])
results = {}
for name, (fn, _) in rewardkit.CHECKS.items():
    t0 = time.time()
    value = fn(ws)
    results[name] = (value, rewardkit.WEIGHTS[name], round(time.time() - t0, 2))
pos = sum(w for _, w, _ in results.values() if w > 0)
earned = sum(w for v, w, _ in results.values() if v is True)
for name, (v, w, dt) in results.items():
    print(f"{'PASS' if v is True else 'fail'} {w:>3} {dt:>6}s {name}" if not isinstance(v, bool) or True else "")
print(f"earned {earned} of {pos} -> fraction {earned / pos!r}")
if "--json" in sys.argv:
    print(json.dumps({"earned": earned, "positive": pos, "fraction": earned / pos,
                      "failed": sorted(n for n, (v, w, _) in results.items() if (w > 0) != (v is True))}))
