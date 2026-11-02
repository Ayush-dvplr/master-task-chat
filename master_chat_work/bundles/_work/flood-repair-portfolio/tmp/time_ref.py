import subprocess, sys, time, tempfile
books = sys.argv[1:]
for b in books:
    ts = []
    for _ in range(3):
        with tempfile.TemporaryDirectory() as td:
            t = time.time()
            r = subprocess.run([sys.executable, "-I", "-S", "/b/solution/solve.py", b, td + "/o"], capture_output=True)
            ts.append(round(time.time() - t, 3))
            assert r.returncode == 0, r.stderr
    print(b, ts, flush=True)
print("ALL_DONE")
