"""g36 scratch: compute WIDE_BUMPS for new wide seeds from g36/tsrc_g36.py. Usage: g36_guard.py K BUDGET"""
import importlib.util, json, shutil, signal, subprocess, sys, types
from pathlib import Path
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
fake = types.ModuleType("rewardkit")
class _Any:
    def __getattr__(self, name):
        return lambda *a, **k: None
fake.criteria = _Any(); fake.criterion = lambda *a, **k: (lambda f: f)
sys.modules["rewardkit"] = fake
sp = importlib.util.spec_from_file_location("tsrc", HERE / "g36" / "tsrc_g36.py")
T = importlib.util.module_from_spec(sp); sp.loader.exec_module(T)
import solvers

class Over(Exception):
    pass

def nodes(p):
    solvers.NODES[0] = 0
    def handler(*a):
        raise Over
    signal.signal(signal.SIGALRM, handler); signal.alarm(20)
    try:
        solvers.ref2(p)
    except Over:
        return 10**9
    finally:
        signal.alarm(0)
    return solvers.NODES[0]

k, budget = int(sys.argv[1]), int(sys.argv[2])
seed = T.WIDE_SEEDS[k]
bump = {}
for rnd in range(12):
    T.WIDE_BUMPS[seed] = dict(bump)
    folder = HERE / "g36" / "ex" / f"wide{k}"
    if folder.exists():
        shutil.rmtree(folder)
    spec = T._wide_spec(seed)
    assert T.within_contract(spec)
    T._assert_bounds(spec)
    T.write_extract(folder, spec)
    pj = HERE / "g36" / f"p_wide{k}.json"
    subprocess.run([sys.executable, "-B", str(HERE / "export.py"), str(folder), str(pj)], check=True, capture_output=True)
    probs = json.loads(pj.read_text())
    heavy, total, mx = [], 0, 0
    for p in probs:
        n = nodes(p)
        total += min(n, 10**7); mx = max(mx, n)
        if n > budget:
            heavy.append(tuple(p["er"]))
    print(f"seed {seed} round {rnd} ers {len(probs)} heavy {len(heavy)} total {total} max {mx}", flush=True)
    if not heavy:
        break
    for er in heavy:
        bump[er] = bump.get(er, 0) + 1
print("BUMP", seed, json.dumps(sorted([list(er) + [v] for er, v in bump.items()])), flush=True)
