"""da61544 Phase 1 H7 fuzz: copy of WORK/fz/fz_cm.py logic (not edited in place) plus the survivor fixture.

Runs inside the verifier image with /tests (BUNDLE tests), /progs/<label>/reconcile.py and /fz (this dir).
Per corpus: reference via T.write_all(T.compute(data)); each program run as nobody; per artifact sha1
recorded so lever attribution (mutant vs agent) is done offline by fz_h7_sum.py.
usage: python3 -B /fz/fz_h7.py N OUT.jsonl WORKERS
"""
import hashlib
import json
import os
import random
import shutil
import sys
import tempfile

sys.path.insert(0, "/fz")
import fz_cm_copy as F  # noqa: E402

T = F.T
LABELS = ["oracle", "A", "B", "C", "H7", "agent_p3", "agent_p2"]
FIXSETS = [["surv"], ["surv", "env"], ["surv", "prec", "env", "ident"], [], ["surv", "env2"], ["prec", "env", "ident"]]


def fixtures(files, fix, seed):
    rest = [f for f in fix if f != "surv"]
    F.fixtures(files, rest, seed)
    if "surv" in fix:
        T._add_survivor_envelopes(files)


def digest(out):
    return {n: (hashlib.sha1(open(os.path.join(out, n), "rb").read()).hexdigest()[:16]
                if os.path.isfile(os.path.join(out, n)) else None) for n in F.GRADED}


def one(case):
    rec = dict(case)
    tmp = tempfile.mkdtemp(prefix="cmh7")
    try:
        files, _w = T.build_all(case["seed"])
        try:
            fixtures(files, case["fix"], case["seed"])
        except AssertionError as exc:
            rec["fix_note"] = str(exc)[:120]
        rng = random.Random(case["seed"] * 17 + 3)
        for m in case["muts"]:
            {"waivers": F.m_waivers, "revision": F.m_revision}[m](files, rng)
        data = os.path.join(tmp, "in", "data")
        F.write(files, data)
        ref = os.path.join(tmp, "ref")
        os.makedirs(ref)
        T.write_all(T.compute(data), ref)
        rec["ref"] = digest(ref)
        for lab in LABELS:
            out = os.path.join(tmp, "o_" + lab, "out")
            os.makedirs(os.path.dirname(out))
            pdir = os.path.join(tmp, "p_" + lab)
            os.makedirs(pdir)
            prog = shutil.copy("/progs/%s/reconcile.py" % lab, os.path.join(pdir, "reconcile.py"))
            code, err, secs = F.run(prog, data, out, tmp)
            rec[lab] = {"code": code, "secs": round(secs, 2), "err": err if code != 0 else "",
                        "h": digest(out) if code == 0 else {}}
    except Exception as exc:  # recorded as a finding
        rec["error"] = "%s: %s" % (type(exc).__name__, str(exc)[:200])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return rec


def main():
    n, path, workers = int(sys.argv[1]), sys.argv[2], int(sys.argv[3])
    r = random.Random(61544)
    cases = [{"id": "H7-%03d" % i, "seed": r.randint(10**7, 10**8 - 1), "fix": FIXSETS[i % len(FIXSETS)],
              "muts": ["waivers"] if i % 3 == 2 else []} for i in range(n)]
    from multiprocessing import Pool
    with Pool(workers) as pool, open(path, "w") as fh:
        for rec in pool.imap_unordered(one, cases):
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
    print("ALL_DONE")


if __name__ == "__main__":
    main()
