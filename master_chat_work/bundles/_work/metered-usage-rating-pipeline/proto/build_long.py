"""Scratch: build one long corpus with the work generator; print shape and cost figures."""
import json, os, random, sys, time
sys.dont_write_bytecode = True
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(here))
import gen_core as G, ref_core as R
seed, rows, nacc, res = (int(x) for x in sys.argv[1:5])
rng = random.Random(seed)
month = "%04d-%02d" % (rng.choice((2027, 2028, 2029)), rng.randint(1, 12))
t0 = time.time(); files = G.gen_month(seed, month, rows, nacc, True, R.ref_compute, resellers=res); t1 = time.time()
docs = R.ref_compute(files); t2 = time.time()
parent = {}
for ln in files["accounts.csv"].decode().splitlines()[1:]:
    a, _, _, p = ln.split(",")
    parent[R.ref_canon(a)] = R.ref_canon(p) if p else ""
depth = G._gen_depths(list(parent), parent)
lines = docs["normalized.jsonl"]
cost = sum(depth[R.ref_canon(l["account_id"])] for l in lines)
d = os.path.join(here, "long_%d" % seed)
os.makedirs(d + "/in", exist_ok=True)
for k, v in files.items():
    open(os.path.join(d, "in", k), "wb").write(v)
print(json.dumps({"seed": seed, "month": month, "rows": rows, "n": nacc, "resellers": res, "gen_s": round(t1 - t0, 1),
                  "ref_s": round(t2 - t1, 2), "lines": len(lines), "max_depth": max(depth.values()),
                  "acct_depth_sum": sum(depth.values()), "line_depth_sum": cost}), flush=True)
