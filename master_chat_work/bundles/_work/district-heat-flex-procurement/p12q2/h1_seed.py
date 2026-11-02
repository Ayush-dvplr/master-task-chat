"""Compare the H1/H2 hidden extracts built by the old tests and the new tests (file bytes)."""
import hashlib, importlib.util, sys
from pathlib import Path
W = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(W / "stub"))
def load(p, name):
    spec = importlib.util.spec_from_file_location(name, p); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
old = load(W / "p12q2/src_before/tests_test_output.py", "old")
new = load(W.parent.parent / "district-heat-flex-procurement/tests/test_output.py", "new")
for kind in ("H1", "H2"):
    a, b = old.hidden_root(kind), new.hidden_root(kind)
    da = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(a.iterdir())}
    db = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(b.iterdir())}
    print(kind, "same" if da == db else "DIFF", [k for k in da if da.get(k) != db.get(k)])
