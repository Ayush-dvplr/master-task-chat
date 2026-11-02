"""Scratch: old hidden digest unchanged; shipped group shape; build a long corpus."""
import hashlib, json, os, random, sys, time
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import gen_core as G, ref_core as R
def dg(files):
    h = hashlib.sha256()
    for k in sorted(files):
        h.update(k.encode()); h.update(files[k])
    return h.hexdigest()[:16]
before = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "DIGESTS_BEFORE.json")))
r = random.Random(58213); month = "%04d-%02d" % (r.choice((2027, 2028, 2029)), r.randint(1, 12))
if "old" in sys.argv:
    t = time.time(); f = G.gen_month(58213, month, 1600, 1200, True, R.ref_compute)
    print("hidden", dg(f), before["hidden"]["files"], dg(f) == before["hidden"]["files"], round(time.time() - t, 1))
if "ship" in sys.argv:
    t = time.time(); f = G.gen_month(461927, "2026-09", 3200, 2400, False, R.ref_compute)
    rows = f["accounts.csv"].decode().splitlines()[1:]
    par = [x for x in rows if x.split(",")[3]]
    print("shipped", round(time.time() - t, 1), "accounts", len(rows), "with parent", len(par), par[:4])
