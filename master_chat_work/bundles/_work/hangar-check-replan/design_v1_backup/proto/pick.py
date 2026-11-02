"""Rejection seed picker: accept a hidden seed only if every hard branch fires (pool binds, split_marginal, asap_only, defer_noslot, rev_tie differ)."""
import json
import sys
import time

import detect
import gen
import ref

NEED = ["binds", "split_marginal", "exact_asap_only", "exact_defer_noslot", "exact_rev_tie"]

if __name__ == "__main__":
    n, frac, lo, hi = int(sys.argv[1]), float(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
    acc = 0
    for seed in range(lo, hi):
        inst = gen.make("hidden", seed, n)
        inst["K"] = 10 ** 6
        inst["K"] = int(ref.solve(inst)["used"] * frac)
        t = time.time()
        f = detect.flags(inst)
        ok = all(f[k] for k in NEED)
        acc += ok
        print(seed, "ACCEPT" if ok else "reject", [k for k in NEED if not f[k]], "K", inst["K"], "sec", round(time.time() - t, 1), flush=True)
    print("accepted", acc, "of", hi - lo)
    print("ALL_DONE")
