import sys, time, subprocess, tempfile, pathlib
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[2])
import test_output as t
solve = sys.argv[3]
for kind, fn, ks in (("long", t._long_files, (1, 2, 3)), ("ladder", t._ladder_files, (1, 2, 3, 4))):
    for k in ks:
        g0 = time.time(); files = fn(k); g1 = time.time()
        w = pathlib.Path(tempfile.mkdtemp(prefix="qct-")); src = w / "in"; src.mkdir()
        for n, b in files.items(): (src / n).write_bytes(b)
        r0 = time.time()
        p = subprocess.run([sys.executable, "-I", solve, "--input", str(src), "--output", str(w / "out")], capture_output=True, text=True)
        r1 = time.time()
        print("%s-%d gen %.1fs run %.2fs rc %s" % (kind, k, g1 - g0, r1 - r0, p.returncode), flush=True)
print("TIMING_DONE", flush=True)
