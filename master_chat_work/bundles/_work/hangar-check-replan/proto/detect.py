"""Branch detector: for a set of seeds, report which hard branches fire (each wrong solver differs from ref)."""
import json
import sys
import time

import gen
import ref
import wrong


def flags(inst):
    r0 = ref.solve(inst)
    free = dict(inst, K=10 ** 6)
    ru = ref.solve(free)
    out = {"T": r0["T"], "used": r0["used"], "K": inst["K"], "free_used": ru["used"],
           "binds": int(ru["used"] > inst["K"] and ru["T"] != r0["T"])}
    for name, fn in wrong.SOLVERS.items():
        out[name] = int(not wrong.same(fn(inst), r0))
    return out


if __name__ == "__main__":
    mode, n, frac = sys.argv[1], int(sys.argv[2]), float(sys.argv[3])
    for seed in [int(s) for s in sys.argv[4:]]:
        inst = gen.make(mode, seed, n)
        inst["K"] = 10 ** 6
        free = ref.solve(inst)["used"]
        inst["K"] = int(free * frac)
        t = time.time()
        f = flags(inst)
        f["sec"] = round(time.time() - t, 1)
        print(seed, json.dumps(f))
