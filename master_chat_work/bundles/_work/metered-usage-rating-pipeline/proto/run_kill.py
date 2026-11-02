"""Scratch: run kill-test solvers on a prototype corpus, compare every document whole."""
import json, os, shutil, subprocess, sys, tempfile, time
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here)
sys.dont_write_bytecode = True
import t_proto as T
sys.path.insert(0, os.path.dirname(here))
import ref_core as R
from pathlib import Path

corpus = sys.argv[1]
cap = float(sys.argv[2])
solvers = sys.argv[3:]
files = {k: open(os.path.join(here, corpus, "in", k), "rb").read() for k in os.listdir(os.path.join(here, corpus, "in"))}
t0 = time.time()
want = R.ref_compute(files)
ref_s = time.time() - t0
print(json.dumps({"corpus": corpus, "ref_compute_s": round(ref_s, 2)}), flush=True)
for name in solvers:
    work = tempfile.mkdtemp()
    out = Path(work) / "out"
    t0 = time.time()
    try:
        proc = subprocess.run([sys.executable, "-I", "-B", os.path.join(here, "solvers", name + ".py"),
                               "--input", os.path.join(here, corpus, "in"), "--output", str(out)],
                              cwd=work, capture_output=True, text=True, timeout=cap)
        rc, err = proc.returncode, proc.stderr[-200:]
    except subprocess.TimeoutExpired:
        rc, err = None, "timed out"
    secs = time.time() - t0
    docs = {}
    for doc in sorted(want):
        if rc != 0:
            docs[doc] = "no run"
            continue
        try:
            got = T._load(out, doc)
        except Exception as exc:
            docs[doc] = "unreadable %s" % type(exc).__name__
            continue
        found = T._first_diff(want[doc], got)
        docs[doc] = "exact" if found is None else found[:90]
    exact = sum(1 for v in docs.values() if v == "exact")
    print(json.dumps({"solver": name, "seconds": round(secs, 2), "rc": rc, "err": err.strip()[-120:],
                      "exact_docs": exact, "of": len(docs),
                      "wrong": {k: v for k, v in docs.items() if v != "exact"}}), flush=True)
    shutil.rmtree(work, ignore_errors=True)
