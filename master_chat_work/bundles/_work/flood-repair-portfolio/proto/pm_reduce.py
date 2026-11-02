import json, sys, time, mw
from pm_docker import instance, PLAN
from variants_lib import reduce_bnb
LIM = float(sys.argv[1])
for seed, n, rows in PLAN:
    n_, W, adj, pairs = instance(seed, n, rows)
    t = time.time(); ok, v, S, c = reduce_bnb(n_, W, adj, LIM)
    print(json.dumps({"seed": seed, "reduce_bnb": ("cert %.1fs" % (time.time() - t)) if ok else "TO", "nodes": c}), flush=True)
print("ALL_DONE", flush=True)
