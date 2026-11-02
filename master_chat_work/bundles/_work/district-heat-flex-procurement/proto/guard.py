"""Re-draw heavy event-regions until every one stays under a reference node budget (scratch).
Usage: guard.py NAME SEED BUDGET key=value ..."""
import json, subprocess, sys, signal
from pathlib import Path
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gen, solvers

class Over(Exception):
    pass

def capped(p, budget):
    solvers.NODES[0] = 0
    orig = solvers.NODES
    def handler(*a):
        raise Over
    signal.signal(signal.SIGALRM, handler)
    signal.alarm(20)
    try:
        r = solvers.ref2(p)
    finally:
        signal.alarm(0)
    return solvers.NODES[0]

name, seed, budget = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
P = dict(gen.DEFAULT)
for kv in sys.argv[4:]:
    k, v = kv.split("="); P[k] = int(v)
bump = {}
for rnd in range(12):
    folder = HERE / "ex" / name
    if folder.exists():
        import shutil; shutil.rmtree(folder)
    gen.T.write_extract(folder, gen.wide_spec(seed, P, bump))
    subprocess.run([sys.executable, "-B", str(HERE / "export.py"), str(folder), str(HERE / f"p_{name}.json")], check=True, capture_output=True)
    probs = json.loads((HERE / f"p_{name}.json").read_text())
    heavy, total, mx = [], 0, 0
    for p in probs:
        try:
            n = capped(p, budget)
        except Over:
            n = 10**9
        total += min(n, 10**7); mx = max(mx, n)
        if n > budget:
            heavy.append(tuple(p["er"]))
    print(f"round {rnd} heavy {len(heavy)} total {total} max {mx}", flush=True)
    if not heavy:
        break
    for er in heavy:
        bump[er] = bump.get(er, 0) + 1
