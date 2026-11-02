"""Scratch: kill table on the final generator output (bundle tests/test_output.py long corpora)."""
import importlib.util, json, os, shutil, subprocess, sys, tempfile, time
from pathlib import Path
sys.dont_write_bytecode = True
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here)  # rewardkit stub
spec = importlib.util.spec_from_file_location("T", "/b/tests/test_output.py")
T = importlib.util.module_from_spec(spec); spec.loader.exec_module(T)
LIMIT = T.RUN_LIMIT_SEC
k = int(sys.argv[1]); cap = float(sys.argv[2]); solvers = sys.argv[3:]
t0 = time.time(); files = T._long_files(k); gen_s = time.time() - t0
t0 = time.time(); want = T.ref_compute(files); ref_s = time.time() - t0
src = tempfile.mkdtemp(); Path(src, "in").mkdir()
for name, data in files.items():
    Path(src, "in", name).write_bytes(data)
print(json.dumps({"long": k, "gen_s": round(gen_s, 1), "ref_compute_s": round(ref_s, 2),
                  "lines": len(want["normalized.jsonl"]), "accounts": files["accounts.csv"].count(b"\n") - 1}), flush=True)
POINTS = {"normalized.jsonl": 5, "summary.json": 5, "product_summary.json": 3}
for name in solvers:
    work = tempfile.mkdtemp(); out = Path(work) / "out"
    t0 = time.time()
    try:
        proc = subprocess.run([sys.executable, "-I", "-B", os.path.join(here, "solvers", name + ".py"),
                               "--input", os.path.join(src, "in"), "--output", str(out)],
                              cwd=work, capture_output=True, text=True, timeout=cap)
        rc, err = proc.returncode, proc.stderr[-160:]
    except subprocess.TimeoutExpired:
        rc, err = None, "timed out at cap"
    secs = time.time() - t0
    ok_run = rc == 0 and secs <= LIMIT
    docs = {}
    for doc in sorted(want):
        if rc != 0:
            docs[doc] = "no run"; continue
        try:
            got = T._load(out, doc)
        except Exception as exc:
            docs[doc] = "unreadable %s" % type(exc).__name__; continue
        found = T._first_diff(want[doc], got)
        docs[doc] = "exact" if found is None else found[:80]
    present = rc == 0 and all((out / d).exists() for d in T.DOCUMENTS)
    kept = (3 if ok_run and present else 0) + sum(p for d, p in POINTS.items() if ok_run and docs.get(d) == "exact")
    print(json.dumps({"solver": name, "long": k, "seconds": round(secs, 2), "rc": rc, "err": err.strip()[-100:],
                      "exact_docs": sum(v == "exact" for v in docs.values()), "of": len(docs),
                      "points_kept": kept, "of_points": 16,
                      "wrong": {d: v for d, v in docs.items() if v != "exact" and v != "no run"}}), flush=True)
    shutil.rmtree(work, ignore_errors=True)
shutil.rmtree(src, ignore_errors=True)
