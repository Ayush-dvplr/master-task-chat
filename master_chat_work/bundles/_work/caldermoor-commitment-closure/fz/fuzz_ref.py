"""F4: tests' reference + hidden generator over N seeds; oracle must equal reference.

Run inside the verifier image: python3 /fz/fuzz_ref.py N OUTJSONL
"""
import json
import os
import random
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from multiprocessing import Pool

sys.path.insert(0, "/tests")
import test_output as T  # noqa: E402

GRADED = [a for a in T.ARTIFACTS if a != "reconcile.py"]
def _alarm(*_):
    raise TimeoutError("no result within 400 s")


signal.signal(signal.SIGALRM, _alarm)
FIXES = ["none", "prec", "env", "ident", "surv", "all"]


def one(job):
    i, seed = job
    fix = FIXES[i % len(FIXES)]
    rec = {"i": i, "seed": seed, "fix": fix}
    tmp = tempfile.mkdtemp(prefix="fzref")
    t0 = time.time()
    signal.alarm(400)
    try:
        files = T.build_all(seed)[0]
        if fix in ("prec", "all"):
            T._add_precedence_row(files)
        if fix in ("env", "all"):
            T._add_small_envelopes(files)
        if fix in ("ident", "all"):
            T._add_identity_fixtures(files)
        if fix in ("surv", "all"):
            try:
                T._add_survivor_envelopes(files)
            except AssertionError as exc:
                rec["surv_none"] = str(exc)
        data = os.path.join(tmp, "data")
        os.makedirs(data)
        for name in sorted(files):
            with open(os.path.join(data, name), "w", encoding="utf-8", newline="") as fh:
                fh.write(files[name])
        ref = os.path.join(tmp, "ref")
        os.makedirs(ref)
        T.write_all(T.compute(data), ref)
        rec["ref_secs"] = round(time.time() - t0, 2)
        orc = os.path.join(tmp, "orc")
        os.makedirs(orc)
        shutil.copy("/progs/oracle/solve.py", os.path.join(orc, "reconcile.py"))
        t1 = time.time()
        p = subprocess.run([sys.executable, "-B", os.path.join(orc, "reconcile.py"), data, orc],
                           capture_output=True, timeout=T.RUN_TIMEOUT_SEC, cwd=tmp)
        rec["orc_secs"] = round(time.time() - t1, 2)
        rec["orc_code"] = p.returncode
        diff = []
        for a in GRADED:
            pa, pb = os.path.join(ref, a), os.path.join(orc, a)
            if not os.path.exists(pb) or not os.path.exists(pa):
                diff.append(a + ":missing")
                continue
            with open(pa, "rb") as fa, open(pb, "rb") as fb:
                if fa.read() != fb.read():
                    diff.append(a)
        rec["diff"] = diff
    except Exception as exc:  # recorded as a finding, never swallowed
        rec["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        signal.alarm(0)
        shutil.rmtree(tmp, ignore_errors=True)
    return rec


def main():
    n, out = int(sys.argv[1]), sys.argv[2]
    r = random.Random(52150)
    jobs = [(i, r.randint(10**7, 10**8 - 1)) for i in range(n)]
    with Pool(4) as pool, open(out, "w") as fh:
        for rec in pool.imap_unordered(one, jobs):
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
    print("ALL_DONE")


if __name__ == "__main__":
    main()
