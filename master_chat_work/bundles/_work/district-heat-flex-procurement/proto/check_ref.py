"""Test reference (bounded search) vs bundle solve.py on every corpus incl. wide 0/1: family projections + seconds.
Docker: /k=WORK, /b=BUNDLE ro, -w /k/proto."""
import shutil, subprocess, sys, time
from pathlib import Path
sys.dont_write_bytecode = True
import gen
T = gen.T
CASES = ["waiver", "tie", "rate", "multiplier", "rounding", "mut_adder", "mut_adder_moved", "residual",
         "tick_feasibility", "components", "full", "rejected", "unknown_region", "allowance_order",
         "allowance_consumption", "mut_allowance", "mut_allowance_moved", "mut_grant", "mut_grant_moved"]
roots = [("shipped", Path("/b/environment/data")), ("H1", T.hidden_root("H1")), ("H2", T.hidden_root("H2"))]
roots += [(c, T.case_root(c)) for c in CASES]
t0 = time.time()
roots += [(f"wide{k}", T.wide_root(k)[0]) for k in (0, 1)]
print(f"wide generation {time.time() - t0:.2f}s", flush=True)
bad = 0
for name, root in roots:
    out = Path(f"/tmp/ref_{name}")
    shutil.rmtree(out, ignore_errors=True)
    t0 = time.time()
    rc = subprocess.run(["python3", "-B", "/b/solution/solve.py", str(root), str(out)], capture_output=True,
                        timeout=900).returncode
    ts = time.time() - t0
    got = {n: T.produced(out, n) for n in T.ARTIFACT_JSON}
    t0 = time.time()
    want = T.expected(root)
    te = time.time() - t0
    diff = [f for f in T.FAMILIES if T.canon(T._project(f, got)) != T.canon(T._project(f, want))]
    bad += bool(diff) or rc != 0
    print(f"{name} solve={ts:.2f}s rc={rc} reference={te:.2f}s families_differ={diff}", flush=True)
print("MISMATCH", bad)
print("ALL_DONE")
