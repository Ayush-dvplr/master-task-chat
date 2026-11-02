"""Per-round MWIS timing on prototype lattice graphs (run in Docker only).

usage: python3 -B bench.py SOLVER N ROWS PDIAG SEED
SOLVER: a1 | dae | ref | elim
Prints: solver n rows pdiag seed edges seconds value
"""
import importlib.util
import random
import sys
import time
import types
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def lattice(rng, n, rows, pdiag):
    edges = set()
    cols = (n + rows - 1) // rows
    for c in range(cols):
        for r in range(rows):
            v = c * rows + r
            if v >= n:
                continue
            if r + 1 < rows and v + 1 < n:
                edges.add((v, v + 1))
            if v + rows < n:
                edges.add((v, v + rows))
            if r + 1 < rows and v + rows + 1 < n and rng.random() < pdiag:
                edges.add((v, v + rows + 1))
    return edges


def main():
    solver, n, rows, pdiag, seed = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), float(sys.argv[4]), int(sys.argv[5])
    rng = random.Random(seed)
    edges = lattice(rng, n, rows, pdiag)
    perm = list(range(n))
    rng.shuffle(perm)
    edges = {tuple(sorted((perm[a], perm[b]))) for a, b in edges}
    t = rng.randint(1000, 1300)
    ben = [int(t * rng.uniform(0.92, 1.08)) for _ in range(n)]
    enc = [ben[i] * (1 << n) + (1 << (n - 1 - i)) for i in range(n)]
    adj = [0] * n
    for a, b in edges:
        adj[a] |= 1 << b
        adj[b] |= 1 << a
    t0 = time.perf_counter()
    if solver == "a1":
        mod = load("a1", HERE / "a1_program" / "derive_report.py")
        mask = mod.Planner(adj, ben).best_set()
        chosen = [i for i in range(n) if mask >> i & 1]
    elif solver == "dae":
        mod = load("dae", HERE / "dae9563_program.py")
        res = mod.MWIS(n, adj, enc).solve((1 << n) - 1)
        chosen = [i for i in range(n) if res[1] >> i & 1]
    elif solver == "ref":
        mod = load("ref", HERE.parent.parent.parent / "flood-repair-portfolio" / "solution" / "solve.py")
        ids = ["P%03d" % i for i in range(n)]
        rnd = types.SimpleNamespace(ids=ids, detail={ids[i]: {"benefit": ben[i]} for i in range(n)})
        pairs = [(ids[a], ids[b]) for a, b in edges]
        chosen = [int(p[1:]) for p in mod.choose(rnd, pairs)]
    elif solver == "elim":
        mod = load("elim", HERE / "elim_ref.py")
        info = {"P%03d" % i: {"benefit": ben[i]} for i in range(n)}
        joined = {frozenset(("P%03d" % a, "P%03d" % b)) for a, b in edges}
        chosen = [int(p[1:]) for p in mod._portfolio(info, joined)]
    elif solver.startswith("ve_"):
        mod = load("strong", HERE / "strong.py")
        got, _, t_ord = mod.solve_ve(solver, n, adj, enc)
        chosen = [i for i in range(n) if got >> i & 1]
        print("order_seconds %.3f" % t_ord, flush=True)
    elif solver.startswith("sweep_"):
        mod = load("strong", HERE / "strong.py")
        got, _ = mod.solve(solver, n, adj, enc)
        chosen = [i for i in range(n) if got >> i & 1]
    else:
        raise SystemExit("unknown solver")
    dt = time.perf_counter() - t0
    print(solver, n, rows, pdiag, seed, len(edges), "%.3f" % dt, sum(ben[i] for i in chosen), flush=True)


if __name__ == "__main__":
    main()
