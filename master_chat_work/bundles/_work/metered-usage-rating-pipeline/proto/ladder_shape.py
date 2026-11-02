"""Scratch: 300-seed shape check of gen_month(..., ladder=50000) on a mid-size reseller month."""
import json, random, sys, time
from multiprocessing import Pool
sys.dont_write_bytecode = True
sys.path.insert(0, "/w")
import gen_core as G, ref_core as R

def one(seed):
    rng = random.Random(seed)
    month = "%04d-%02d" % (rng.choice((2027, 2028, 2029)), rng.randint(1, 12))
    files = G.gen_month(seed, month, 2000, 5000, True, R.ref_compute, resellers=800, ladder=50000)
    card = json.loads(files["rate_card.json"])
    for code, spec in card["products"].items():
        t = spec["tiers"]
        assert len(t) == 50000 and t[0]["from"] == 0, code
        assert all(a["from"] < b["from"] for a, b in zip(t, t[1:])), code
        assert [x["tier"] for x in t] == list(range(1, 50001)), code
    docs = R.ref_compute(files)
    used = len({(l["product"], l["tier"]) for l in docs["normalized.jsonl"]})
    top = max(l["tier"] for l in docs["normalized.jsonl"])
    return used, top

if __name__ == "__main__":
    t0 = time.time()
    with Pool(2) as pool:
        res = pool.map(one, [s * 11 + 5 for s in range(1, 301)])
    print(json.dumps({"seeds": len(res), "min_distinct_tiers_used": min(r[0] for r in res),
                      "min_top_tier": min(r[1] for r in res), "seconds": round(time.time() - t0, 1)}))
    print("LADDER_SHAPE_OK")
