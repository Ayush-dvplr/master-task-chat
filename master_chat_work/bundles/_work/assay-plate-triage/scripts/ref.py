"""Import the verifier's reference engine without rewardkit (WORK helper)."""
import sys, types, importlib.util
B = "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/assay-plate-triage"
rk = types.ModuleType("rewardkit")
class _C:
    def __getattr__(self, n): return lambda *a, **k: (lambda f: f) if not a or not callable(a[0]) else a[0]
rk.criteria = _C(); rk.criterion = lambda *a, **k: (lambda f: f) if not a or not callable(a[0]) else a[0]
sys.modules["rewardkit"] = rk
def load(path=B + "/tests/test_output.py", name="ref"):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); sys.dont_write_bytecode = True
    spec.loader.exec_module(m); return m
