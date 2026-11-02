import runpy
import subprocess
import sys
import time

_real = subprocess.run


def timed(argv, *a, **k):
    t0 = time.time()
    proc = _real(argv, *a, **k)
    words = [str(x) for x in argv]
    sub = next((w for w in words if w in ("resolve-config", "compile", "audit", "summarize")), words[-1])
    prof = words[words.index("--profile") + 1] if "--profile" in words else ""
    print(f"TIMING {sub} {prof} rc={proc.returncode} {time.time() - t0:.1f}s", file=sys.stderr, flush=True)
    return proc


subprocess.run = timed
t0 = time.time()
try:
    runpy.run_path("/solution/solve.py", run_name="__main__")
finally:
    print(f"TIMING total {time.time() - t0:.1f}s", file=sys.stderr, flush=True)
