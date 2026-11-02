"""Time the delivered archive on the hidden books in Docker (same command, env, uid drop as _run_cli), cap CAP s.

Usage inside the container: python -B measure_wide.py <label> <cap_seconds> <book>...
/app/out holds the blind's delivered files; /tests holds the copy's tests.
"""
import json, os, resource, subprocess, sys, time
sys.path.insert(0, "/tests")
import test_output as T

label, cap, books = sys.argv[1], int(sys.argv[2]), sys.argv[3:]
repo = T._extract_archive()
for name in books:
    book = T._book(name)
    n = T._book_projects(book)
    out = T._scratch("m-") / "out"; out.mkdir(); out.chmod(0o777)
    cwd = T._scratch("cwd-")
    cmd = [sys.executable, "-B", "-m", T.PACKAGE, "--book", str(book), "--out", str(out)]
    before = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    t0 = time.monotonic()
    try:
        r = subprocess.run(T._untrusted_command(cmd), text=True, capture_output=True,
                           env=T._env(cwd, repo / "src"), cwd=cwd, timeout=cap)
        rc, err = r.returncode, r.stderr[-300:]
    except subprocess.TimeoutExpired:
        rc, err = "capped", "still running at cap"
    dt = time.monotonic() - t0
    rss = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    match = None
    if rc == 0:
        want = T._expected(name)
        match = {d: T._first_difference(want[d], json.loads((out / d).read_text())[d] if False else json.loads((out / d).read_text())) is None for d in T.DOCUMENTS}
    print(json.dumps({"label": label, "book": name, "projects": n, "limit_s": T.SECONDS_PER_PROJECT * n + T.START_UP_SECONDS,
                      "rc": rc, "seconds": round(dt, 2), "peak_rss_mb_children": round(rss / 1024, 1),
                      "rss_prev_mb": round(before / 1024, 1), "stderr_tail": err, "docs_match": match}), flush=True)
