"""Lever plant stats for a generated month (scratch)."""
import random, sys, time
sys.dont_write_bytecode = True
sys.path.insert(0, sys.argv[1])
from ref_core import ref_compute
from gen_core import gen_month

def month(seed):
    rng = random.Random(seed)
    return "%04d-%02d" % (rng.choice((2027, 2028, 2029)), rng.randint(1, 12))

args = {"shipped": (461927, "2026-09", 3200, 2400, False), "hidden": (58213, month(58213), 1600, 1200, True)}
for label in sys.argv[2:]:
    t = time.time()
    files = gen_month(*args[label], ref_compute)
    docs = ref_compute(files)
    print(label, "gen+ref %.1fs" % (time.time() - t))
    print(files["commitments.xml"].decode())
    for r in ("central", "east", "north", "south", "west"):
        d = docs["region_%s.json" % r]
        lines = [l for l in docs["normalized.jsonl"] if l["region"] == r and l["plan"] is not None]
        over = sum(1 for l in lines if float(l["credit"]) > float(l["charge"]))
        tu = sum(1 for l in lines if l["true_up"] != "0.00")
        print(r, {k: d[k] for k in ("credit_pool", "credit_base", "credit_applied", "credit_unallocated", "minimum", "true_up")}, "credit>charge", over, "true_up lines", tu)
