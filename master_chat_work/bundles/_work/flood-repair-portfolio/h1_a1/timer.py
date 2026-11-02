"""python3 -B timer.py CAP LABEL BOOKDIR OUTDIR REFDIR PROGRAM: one timed run, one result line.

Prints: LABEL book seconds rc peak_kb verdict, where verdict is EXACT, WRONG, TIMEOUT or CRASH
(compared document by document with REFDIR when REFDIR is not '-').
"""
import json
import os
import resource
import subprocess
import sys
import time


def main(argv):
    cap, label, book, out, ref, prog = float(argv[1]), argv[2], argv[3], argv[4], argv[5], argv[6]
    t0 = time.monotonic()
    try:
        proc = subprocess.run([sys.executable, "-I", "-S", prog, book, out], capture_output=True, timeout=cap)
        rc = proc.returncode
        verdict = None
    except subprocess.TimeoutExpired:
        rc = -9
        verdict = "TIMEOUT"
    secs = time.monotonic() - t0
    peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    if verdict is None:
        if rc != 0:
            verdict = "CRASH"
        elif ref == "-":
            verdict = "DONE"
        else:
            verdict = "EXACT"
            for name in sorted(os.listdir(ref)):
                if not name.endswith(".json"):
                    continue
                path = os.path.join(out, name)
                try:
                    with open(path) as fh:
                        got = json.load(fh)
                except (OSError, ValueError):
                    verdict = "CRASH"
                    break
                with open(os.path.join(ref, name)) as fh:
                    if json.load(fh) != got:
                        verdict = "WRONG"
    print(label, os.path.basename(book), "%.2f" % secs, rc, peak, verdict, flush=True)


if __name__ == "__main__":
    main(sys.argv)
