"""Write the sha256 of solution/solve.sh and solution/solve.py into TRUTH.md provenance (run last)."""
import hashlib
import os
import re

B = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                 "hangar-check-replan", "solution")
t = open(os.path.join(B, "TRUTH.md")).read()
for key, name in (("fix_patch_sha256", "solve.sh"), ("solve_py_sha256", "solve.py")):
    h = hashlib.sha256(open(os.path.join(B, name), "rb").read()).hexdigest()
    t = re.sub(r"^%s: .*$" % key, "%s: %s  # sha256 of solution/%s" % (key, h, name), t, flags=re.M)
    print(key, h)
open(os.path.join(B, "TRUTH.md"), "w").write(t)
