"""Compute WIDE_BUMPS for the final _wide_spec in test_output.src.py (scratch).
Usage: guard2.py K BUDGET   (K = 0 or 1, index into WIDE_SEEDS)"""
import json, shutil, signal, subprocess, sys
from pathlib import Path
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gen, solvers
T = gen.T


class Over(Exception):
    pass


def nodes(p):
    solvers.NODES[0] = 0

    def handler(*a):
        raise Over
    signal.signal(signal.SIGALRM, handler)
    signal.alarm(20)
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
    folder = HERE / "ex" / f"wide{k}"
    if folder.exists():
        shutil.rmtree(folder)
    T.write_extract(folder, T._wide_spec(seed))
    pj = HERE / f"p_wide{k}.json"
    subprocess.run([sys.executable, "-B", str(HERE / "export.py"), str(folder), str(pj)], check=True,
                   capture_output=True)
    probs = json.loads(pj.read_text())
    heavy, total, mx = [], 0, 0
    for p in probs:
        n = nodes(p)
        total += min(n, 10**7)
        mx = max(mx, n)
        if n > budget:
            heavy.append(tuple(p["er"]))
    print(f"seed {seed} round {rnd} ers {len(probs)} heavy {len(heavy)} total {total} max {mx}", flush=True)
    if not heavy:
        break
    for er in heavy:
        bump[er] = bump.get(er, 0) + 1
print("BUMP", seed, json.dumps(sorted([list(er) + [v] for er, v in bump.items()])), flush=True)
