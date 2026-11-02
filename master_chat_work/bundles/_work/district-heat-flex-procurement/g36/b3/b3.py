"""g36 B3 scratch: old corpora byte-identical old vs new tests; existing check bodies identical; reference == solve.py on wide_2/3."""
import ast, hashlib, importlib.util, subprocess, sys, types, json
from pathlib import Path
sys.dont_write_bytecode = True
fake = types.ModuleType("rewardkit")
class _Any:
    def __getattr__(self, n):
        return lambda *a, **k: None
fake.criteria = _Any(); fake.criterion = lambda *a, **k: (lambda f: f)
sys.modules["rewardkit"] = fake
def load(name, path):
    sp = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m); return m
OLD, NEW = Path(sys.argv[1]), Path(sys.argv[2]); SOLVE = sys.argv[3]
def digest(folder):
    h = hashlib.sha256()
    for p in sorted(Path(folder).rglob("*")):
        if p.is_file():
            h.update(p.name.encode()); h.update(p.read_bytes())
    return h.hexdigest()[:16]
# function bodies
def funcs(path):
    src = path.read_text(); tree = ast.parse(src)
    return {n.name: ast.get_source_segment(src, n) for n in tree.body if isinstance(n, ast.FunctionDef)}
fo, fn = funcs(OLD), funcs(NEW)
changed = [k for k in fo if fo[k] != fn.get(k)]
print("old functions", len(fo), "new", len(fn), "changed or missing", changed, "added", sorted(set(fn) - set(fo)))
o = load("told", OLD); n = load("tnew", NEW)
for k in (0, 1):
    a, _ = o.wide_root(k); b, _ = n.wide_root(k)
    print(f"wide_{k}", digest(a), digest(b), "SAME" if digest(a) == digest(b) else "DIFF")
for kind in ("H1", "H2"):
    a = o.hidden_root(kind); b = n.hidden_root(kind)
    print(kind, digest(a), digest(b), "SAME" if digest(a) == digest(b) else "DIFF")
for k in (2, 3):
    root, spec = n.wide_root(k)
    want = n.expected(root)
    out = Path(f"/tmp/b3solve{k}"); subprocess.run([sys.executable, "-B", SOLVE, str(root), str(out)], check=True)
    got = {p.name: json.loads(p.read_text()) for p in out.glob("*.json")}
    diff = [f for f in want if n.canon(want[f]) != n.canon(got.get(f))]
    print(f"wide_{k} seed {n.WIDE_SEEDS[k]} files {len(want)} ref==solve {'YES' if not diff else diff} ers {len(spec['limits'])}")
print("B3_DONE")
