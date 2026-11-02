import importlib.util, sys
sys.path.insert(0, "/h")
def load(path="/tests/test_output.py"):
    spec = importlib.util.spec_from_file_location("t", path)
    m = importlib.util.module_from_spec(spec); sys.modules["t"] = m
    spec.loader.exec_module(m)
    return m
