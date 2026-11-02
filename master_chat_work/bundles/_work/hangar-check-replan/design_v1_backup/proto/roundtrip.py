"""For each corpus dir under root: run solve_proto on data/, compare plan_terms with ref.solve(abstract)."""
import json
import os
import subprocess
import sys
import time

from ref import solve

root = sys.argv[1]
for name in sorted(os.listdir(root)):
    d = os.path.join(root, name)
    if not os.path.isdir(os.path.join(d, "data")):
        continue
    t = time.time()
    p = subprocess.run([sys.executable, "-B", os.path.join(os.path.dirname(__file__), "solve_proto.py"),
                        "--data", os.path.join(d, "data"), "--out", os.path.join(d, "out")],
                       capture_output=True, text=True)
    sec = time.time() - t
    if p.returncode:
        print("RT", name, "CRASH", p.stderr[-300:])
        continue
    got = json.load(open(os.path.join(d, "out", "plan_summary.json")))["plan_terms"]
    want = solve(json.load(open(os.path.join(d, "abstract.json"))))["T"]
    gt = [got["first"], got["second"], got["third"]]
    print("RT", name, "MATCH" if gt == want else "DIFF", gt, want, "%.1f" % sec)
print("ALL_DONE")
