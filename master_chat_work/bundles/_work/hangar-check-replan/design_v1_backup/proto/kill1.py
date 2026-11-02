"""Run one solver on one generated instance; print verdict line."""
import json
import sys
import time

import gen
import ref
import wrong

if __name__ == "__main__":
    mode, n, frac, seed, name = sys.argv[1], int(sys.argv[2]), float(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
    inst = gen.make(mode, seed, n)
    inst["K"] = 10 ** 6
    free = ref.solve(inst)["used"]
    inst["K"] = int(free * frac) if frac < 1 else free
    t0 = time.time()
    r0 = ref.solve(inst)
    tref = time.time() - t0
    t = time.time()
    r = dict(wrong.SOLVERS, **wrong.SLOW)[name](inst)
    sec = time.time() - t
    diff = [k for k in sorted(r0["plan"]) if tuple(r["plan"][k]) != tuple(r0["plan"][k])]
    print("ROW", name, mode, seed, round(sec, 1), "EXACT" if not diff else "WRONG", "ref_sec", round(tref, 1),
          "T", r["T"], "refT", r0["T"], "first_diff", diff[:1], flush=True)
