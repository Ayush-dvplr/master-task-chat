"""P12 qc1: render the graded fresh corpora (h2, h3) of a tests/test_output.py into <outdir>/<key>."""
import importlib.util
import shutil
import sys
import types
from pathlib import Path

rk = types.ModuleType("rewardkit")


class _C:
    def __getattr__(self, n):
        return lambda *a, **k: (lambda f: f)


rk.criteria = _C()
rk.criterion = lambda *a, **k: (lambda f: f)
sys.modules["rewardkit"] = rk
spec = importlib.util.spec_from_file_location("t", sys.argv[1])
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)
out = Path(sys.argv[2])
for key, seed in t._FRESH_SEEDS.items():
    d = t._write_tree({n: s.encode() for n, s in t.build_inputs(seed).items()})
    shutil.rmtree(out / key, ignore_errors=True)
    shutil.copytree(d, out / key)
    print(key, seed, sorted(p.name for p in (out / key).iterdir()))
