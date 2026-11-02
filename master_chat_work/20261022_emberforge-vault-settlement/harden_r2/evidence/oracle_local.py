import sys, pathlib, tempfile, subprocess, time
sys.path.insert(0, sys.argv[1] + "/tests")
import test_output as T
prog = sys.argv[1] + "/solution/solve.py"
bad = 0
for s in ["visible"] + list(T.SEASONS):
    root = pathlib.Path(tempfile.mkdtemp()); d = root / "data"; o = root / "out"
    if s == "visible":
        T._build_corpus_dir(d); params = T.TRUE
    else:
        seed, params, mut = T.SEASONS[s]; T._build_corpus_dir(d, params=params, mutate=mut, main_seed=seed)
    want = T.settle(T.load(d, ""), params)
    t = time.time(); r = subprocess.run([sys.executable, prog, str(d), str(o)], capture_output=True, text=True); el = time.time() - t
    got = T._read_dir(o) if r.returncode == 0 else {}
    ok = got == want and all((o / n).read_text() == T._canon(want[n]) for n in want)
    bad += not ok
    print(s, "OK" if ok else "MISMATCH rc=%d %s" % (r.returncode, r.stderr[-300:]), "%.2fs" % el)
print("mismatches", bad)
