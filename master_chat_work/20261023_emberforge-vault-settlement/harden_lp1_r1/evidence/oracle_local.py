"""solve.py vs tests settle() on visible + every SEASONS entry. usage: oracle_local.py <bundle> [season...]"""
import sys, pathlib, tempfile, subprocess, time
from tk import load_T
B = pathlib.Path(sys.argv[1]); T = load_T(B)
names = sys.argv[2:] or ["visible"] + list(T.SEASONS)
bad = 0
for n in names:
    root = pathlib.Path(tempfile.mkdtemp()); d = root / "data"; o = root / "out"; o.mkdir()
    if n == "visible":
        T._build_corpus_dir(d); params = T.TRUE
    else:
        seed, params, mut = T.SEASONS[n]
        T._build_corpus_dir(d, params=params, mutate=mut, main_seed=seed)
    t = time.time()
    r = subprocess.run([sys.executable, str(B / "solution/solve.py"), str(d), str(o)], capture_output=True, text=True)
    dt = time.time() - t
    want = T.settle(T.load(d, ""), params)
    got = T._read_dir(o) if r.returncode == 0 else None
    ok = got == want
    bad += not ok
    print("%-22s %s %.1fs %s" % (n, "OK " if ok else "BAD", dt, r.stderr[-200:]))
print("BAD", bad)
