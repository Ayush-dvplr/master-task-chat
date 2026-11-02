"""Old vs new solve.py on every corpus the tests use (+ wide g20): byte compare and seconds. Docker: /k=WORK, /b=BUNDLE, /o=old solution dir."""
import subprocess, sys, time, filecmp, shutil
from pathlib import Path
sys.dont_write_bytecode = True
import gen
T = gen.T
CASES = ["waiver", "tie", "rate", "multiplier", "rounding", "mut_adder", "mut_adder_moved", "residual",
         "tick_feasibility", "components", "full", "rejected", "unknown_region", "allowance_order",
         "allowance_consumption", "mut_allowance", "mut_allowance_moved", "mut_grant", "mut_grant_moved"]
roots = [("shipped", Path("/b/environment/data")), ("H1", T.hidden_root("H1")), ("H2", T.hidden_root("H2"))]
roots += [(c, T.case_root(c)) for c in CASES]
roots += [(w, Path("/k/proto/ex") / w) for w in sys.argv[1:]]
bad = 0
for name, root in roots:
    outs = []
    for tag, prog in (("old", "/o/solve.py"), ("new", "/b/solution/solve.py")):
        out = Path(f"/tmp/cmp_{tag}_{name}")
        shutil.rmtree(out, ignore_errors=True)
        t0 = time.time()
        rc = subprocess.run(["python3", "-B", prog, str(root), str(out)], capture_output=True, timeout=900).returncode
        outs.append((out, rc, time.time() - t0))
    (a, rca, ta), (b, rcb, tb) = outs
    files = sorted(p.name for p in a.iterdir()) if a.exists() else []
    same = rca == rcb == 0 and files == sorted(p.name for p in b.iterdir()) and all(
        filecmp.cmp(a / f, b / f, shallow=False) for f in files)
    bad += not same
    print(f"{name} old={ta:.2f}s rc={rca} new={tb:.2f}s rc={rcb} identical={same}", flush=True)
print("MISMATCH", bad)
print("ALL_DONE")
