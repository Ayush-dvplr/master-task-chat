"""Build each grader season (copy of tests/test_output.py), settle with grader settle(), oracle solve.py and agent program; diff."""
import sys, types, json, subprocess, shutil, os
from pathlib import Path
HERE = Path(__file__).resolve().parent
rk = types.ModuleType("rewardkit")
def _deco(*a, **k):
    if a and callable(a[0]) and not k: return a[0]
    return lambda f: f
rk.criteria = types.SimpleNamespace(); rk.criterion = _deco
class _C:
    def __getattr__(self, n): return _deco
rk.criteria = _C()
sys.modules["rewardkit"] = rk
sys.path.insert(0, str(HERE))
import grader as G

def read(d):
    return {p.name: json.loads(p.read_text()) for p in sorted(Path(d).glob("*.json"))}

def first_diff(a, b, path=""):
    if type(a) != type(b): return path, a, b
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b: return path + "/" + k, a.get(k, "<missing>"), b.get(k, "<missing>")
            r = first_diff(a[k], b[k], path + "/" + k)
            if r: return r
        return None
    if isinstance(a, list):
        if len(a) != len(b): 
            for i,(x,y) in enumerate(zip(a,b)):
                r = first_diff(x, y, "%s[%d]" % (path, i))
                if r: return r
            return path + ".len", len(a), len(b)
        for i, (x, y) in enumerate(zip(a, b)):
            r = first_diff(x, y, "%s[%d]" % (path, i))
            if r: return r
        return None
    return None if a == b else (path, a, b)

names = sys.argv[1:] or list(G.SEASONS)
root = HERE / "seasons"
for name in names:
    seed, params, mutate = G.SEASONS[name]
    d = root / name
    if d.exists(): shutil.rmtree(d)
    data = d / "data"
    G._build_corpus_dir(data, params=params, mutate=mutate, main_seed=seed)
    want = G.settle(G.load(data, ""), params)
    PROGS = [(HERE / p, p.split(".")[0]) for p in os.environ.get("PROGS","oracle_solve.py,agent_settle.py").split(",")]
    for prog, tag in PROGS:
        out = d / ("out_" + tag)
        r = subprocess.run([sys.executable, str(prog), str(data), str(out)], capture_output=True, text=True, timeout=300)
        if r.returncode: print(name, tag, "rc", r.returncode, r.stderr[-400:]); continue
        got = read(out)
        diffs = []
        for doc in sorted(set(want) | set(got)):
            fd = first_diff(want.get(doc), got.get(doc), doc)
            if fd: diffs.append(fd)
        print(name, tag, "docs differing:", len(diffs))
        for fd in diffs: print("   ", str(fd)[:300])
