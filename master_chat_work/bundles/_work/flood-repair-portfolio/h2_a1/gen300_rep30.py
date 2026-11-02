"""TS-19 / G12 for the rep30 hidden tier: 300 seeds of each rep30 hidden spec build without error;
bounds asserted inside bookgen._check_bounds (contract.md:11-12 caps); shape: 100 rounds, 60 large;
every fault kind planted across the corpus; pinned H1-H3 from hidden_meta.json equal proto_gen2 books."""
import hashlib, json, os, sys
from multiprocessing import Pool
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import bookgen  # noqa: E402

META = json.load(open(os.path.join(HERE, "..", "hidden_meta.json")))
NAMES = ("H1", "H2", "H3")


def digest(files):
    return hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()


def one(seed):
    name = NAMES[seed % 3]
    spec = dict(META[name]["spec"])
    spec["large"] = [tuple(x) for x in spec["large"]]
    try:
        files, meta = bookgen.make_book(9000 + seed, spec)
        nr = len({ln.split(",")[0] for ln in files["proposals.csv"].splitlines()[1:] if ln.strip()})
        return seed, None, len(meta["large"]), nr, sorted({k for ks in meta["faults"].values() for k in ks})
    except Exception as e:  # report every failure
        return seed, repr(e), 0, 0, []


if __name__ == "__main__":
    with Pool(2) as p:
        res = p.map(one, range(1, 301))
    errs = [r for r in res if r[1]]
    print("seeds 300 errors", len(errs), errs[:3])
    print("large per book", sorted({r[2] for r in res}), "rounds per book", sorted({r[3] for r in res}))
    kinds = set(k for r in res for k in r[4])
    print("fault kinds planted", len(kinds), "of", len(bookgen.FAULT_KINDS), "missing", sorted(set(bookgen.FAULT_KINDS) - kinds))
    import proto_gen2  # noqa: E402,F401
    for name, base in zip(NAMES, ("H1", "H2", "H3")):
        e = META[name]
        spec = dict(e["spec"]); spec["large"] = [tuple(x) for x in spec["large"]]
        pinned, _ = bookgen.make_book(e["seed"], spec)
        large = proto_gen2.BASE[base] * 30; k = len(large)
        pspec = {"audit_large": 60, "audit_small": 12, "blank_row": 50, "crews": 700 + 60 * k, "faults": 12,
                 "large": large, "order": "shuffle", "permits": 600 + 80 * k, "sites": 500 + 60 * k,
                 "small": 40, "ties": 8}
        proto, _ = bookgen.make_book(e["seed"], pspec)
        print(name, "seed", e["seed"], "pinned", digest(pinned)[:16], "equals kill-table book", digest(pinned) == digest(proto))
    print("ALL_DONE")
