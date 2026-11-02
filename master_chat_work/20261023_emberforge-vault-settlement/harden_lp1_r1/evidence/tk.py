"""Import a bundle's tests/test_output.py with a stub rewardkit. usage: from tk import load_T; T = load_T(bundle)"""
import sys, types, importlib, pathlib
def load_T(bundle, modname="test_output"):
    reg = []
    class C:
        def __getattr__(self, name):
            def r(weight=1, **k): reg.append((name, weight))
            return r
    def crit(description="", **k):
        def w(f): f.description = description; return f
        return w
    stub = types.ModuleType("rewardkit"); stub.criteria = C(); stub.criterion = crit
    sys.modules["rewardkit"] = stub
    p = str(pathlib.Path(bundle) / "tests")
    if p not in sys.path: sys.path.insert(0, p)
    sys.modules.pop(modname, None)
    T = importlib.import_module(modname)
    T._REGISTRY = reg
    return T
