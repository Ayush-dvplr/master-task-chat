"""G12 survey: run the embedded generator over many seeds and report bounds/planting failures.

Usage: python3 -B g12_seeds.py /tests/test_output.py FIRST LAST WORKERS
"""
import importlib.util
import sys
import tempfile
import time
from multiprocessing import Pool

CONFIGS = [(True, "cap", False), (True, "short", False), (False, "bind", True), (False, "bind", False)]


def load(path):
    spec = importlib.util.spec_from_file_location("t", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def one(arg):
    path, seed = arg
    t = load(path)
    empty, stype, x1 = CONFIGS[seed % len(CONFIGS)]
    t0 = time.time()
    with tempfile.TemporaryDirectory() as td:
        try:
            inst, want = t._planted_corpus("s%d" % seed, seed, empty, stype, x1, t.Path(td) / "d")
            res = "OK draw=%d" % inst["meta"]["draw"]
        except Exception as exc:  # recorded per seed
            res = "FAIL %s: %s" % (type(exc).__name__, str(exc)[:120])
    return "SEED %d %s %s x1=%d %.1fs %s" % (seed, "empty" if empty else "full", stype, x1, time.time() - t0, res)


if __name__ == "__main__":
    path, a, b, w = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
    with Pool(w) as pool:
        for line in pool.imap_unordered(one, [(path, s) for s in range(a, b + 1)]):
            print(line, flush=True)
    print("ALL_DONE", flush=True)
