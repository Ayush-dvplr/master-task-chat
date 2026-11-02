"""Load a bundle's tests/test_output.py with a stub rewardkit (run inside Docker only)."""
import importlib.util
import sys
import types

REG = {}
W = {}


def load(tests_dir):
    rk = types.ModuleType("rewardkit")

    def criterion(description=""):
        def deco(f):
            REG[f.__name__] = f
            return f
        return deco

    class _C:
        def __getattr__(self, name):
            def setw(weight):
                W[name] = weight
            return setw

    rk.criterion = criterion
    rk.criteria = _C()
    sys.modules["rewardkit"] = rk
    spec = importlib.util.spec_from_file_location("test_output", tests_dir + "/test_output.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
