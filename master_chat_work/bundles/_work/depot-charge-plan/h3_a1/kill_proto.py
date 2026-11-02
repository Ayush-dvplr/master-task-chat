"""Kill table for the uplift prototype folders.

Usage: kill.py <seed,seed,...> <prog,prog,...> <jobs>
Mounts: /w = WORK (h3_a1/proto/gen_core_up.py), /p = programs dir (oracle.py is the reference),
/docs = shipped environment/data/docs (copied into every folder, as the tests do).
For every seed renders an uplift folder, runs the reference and every program (120 s cap per run), compares the 8 plan
documents whole and prints one JSON line per (seed, program): EXACT/WRONG/CRASH/TIMEOUT counts and seconds.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from multiprocessing import Pool

sys.path.insert(0, "/w/h3_a1/proto")
import gen_core_up  # noqa: E402

PLAN_DOCS = ["policy_audit.json", "region_North.json", "region_South.json", "region_West.json", "region_East.json",
             "segment_commercial.json", "segment_public.json", "summary.json"]


def run(prog, data, out):
    t = time.time()
    try:
        p = subprocess.run(["python3", "-B", prog, "--data", data, "--out", out], capture_output=True, text=True,
                           timeout=120, cwd=out)
        rc = p.returncode
    except subprocess.TimeoutExpired:
        rc = "TIMEOUT"
    return rc, round(time.time() - t, 2)


def one(args):
    seed, progs = args
    tmp = tempfile.mkdtemp(dir="/tmp")
    recs = []
    try:
        data = os.path.join(tmp, "data")
        gen_core_up.render(seed, "uplift", data)
        shutil.copytree("/docs", os.path.join(data, "docs"))
        ref = os.path.join(tmp, "ref")
        os.makedirs(ref)
        rr, rs = run("/p/oracle.py", data, ref)
        assert rr == 0, (seed, rr)
        for name in progs:
            out = os.path.join(tmp, name)
            os.makedirs(out)
            rc, sec = run("/p/%s.py" % name, data, out)
            rec = {"seed": seed, "prog": name, "sec": sec, "ref_s": rs, "EXACT": 0, "WRONG": 0, "CRASH": 0,
                   "TIMEOUT": 0}
            for d in PLAN_DOCS:
                if rc == "TIMEOUT":
                    rec["TIMEOUT"] += 1
                    continue
                try:
                    same = json.load(open(os.path.join(out, d))) == json.load(open(os.path.join(ref, d)))
                except (OSError, ValueError):
                    rec["CRASH"] += 1
                    continue
                rec["EXACT" if same else "WRONG"] += 1
            recs.append(rec)
        return recs
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    seeds = [int(x) for x in sys.argv[1].split(",")]
    progs = sys.argv[2].split(",")
    with Pool(int(sys.argv[3])) as pool:
        for recs in pool.imap_unordered(one, [(s, progs) for s in seeds]):
            for r in recs:
                print(json.dumps(r), flush=True)
    print("ALL_DONE", flush=True)
