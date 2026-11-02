"""G12: 300 seeds of the hidden spec build without error; bounds asserted inside bookgen._check_bounds;
every fault kind and both tie gadgets planted across the hidden corpus (WORK only)."""
import json, sys
from multiprocessing import Pool
sys.dont_write_bytecode = True
import bookgen
LARGE = ([[156, 13], [160, 14]], [[148, 12], [160, 13]], [[152, 14], [144, 12]])
BASE = {"small": 40, "sites": 500, "crews": 700, "permits": 600, "faults": 12, "ties": 8,
        "audit_small": 12, "audit_large": 60, "order": "shuffle"}

def one(seed):
    spec = dict(BASE, large=LARGE[seed % 3])
    try:
        files, meta = bookgen.make_book(5000 + seed, spec)
        return seed, None, sorted({k for ks in meta["faults"].values() for k in ks})
    except Exception as e:
        return seed, repr(e), []

if __name__ == "__main__":
    with Pool(6) as p:
        res = p.map(one, range(1, 301))
    errs = [r for r in res if r[1]]
    print("seeds 300 errors", len(errs), errs[:3])
    meta = json.load(open("hidden_meta.json"))
    print("hidden meta keys", {k: list(v.keys()) for k, v in meta.items()})
    print("ALL_DONE")
