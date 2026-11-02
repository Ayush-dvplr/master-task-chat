"""300-seed shape assert for the capped-crew branch: python3 -B shape300.py N0 N1 SHIPPED_DIR.

Per seed: make_book2 with two capped rounds; the capped reference (proto/solve.py) must select the
generator's capped optimum inside each gadget, the shipped reference (no cap) must select the uncapped
optimum there, all other rounds must agree, and bounds must hold. Also compares proto vs shipped
reference on the shipped data set.
"""
import importlib.util
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import capgen  # noqa: E402

BUNDLE = os.environ.get("BUNDLE", "/b")


def _mod(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


NEW = _mod("newref", os.path.join(HERE, "solve.py"))
OLD = _mod("oldref", os.path.join(BUNDLE, "solution", "solve.py"))

SPEC = {"audit_large": 60, "audit_small": 12, "blank_row": 50, "crews": 700, "faults": 10,
        "large": [], "order": "shuffle", "permits": 600, "sites": 500, "small": 30, "ties": 6,
        "capped": 2}


def picks(mod, d):
    book = mod.load(d)
    return {r.rid: (r.fault, tuple(r.selected) if r.fault is None else None) for r in mod.build(book)}


def main(argv):
    n0, n1, shipped = int(argv[1]), int(argv[2]), argv[3]
    stats = {}
    for seed in range(n0, n1):
        files, meta = capgen.make_book2(seed, SPEC)
        with tempfile.TemporaryDirectory() as d:
            for k, v in files.items():
                with open(os.path.join(d, k), "w") as fh:
                    fh.write(v)
            new, old = picks(NEW, d), picks(OLD, d)
        assert len(meta["capped"]) == 2
        for rid, c in meta["capped"].items():
            assert new[rid][0] is None and old[rid][0] is None, (seed, rid, "capped round faulted")
            mem = set(c["members"])
            gset = set(c["opt"]) | set(c["unc"]) | mem
            gn = sorted(p for p in new[rid][1] if p in gset or p in set(c["opt"]))
            assert set(c["opt"]) <= set(new[rid][1]), (seed, rid, "capped opt not selected")
            assert len(set(new[rid][1]) & mem) <= capgen.CAP
            assert set(c["unc"]) <= set(old[rid][1]), (seed, rid, "uncapped opt not selected by old ref")
            assert len(set(old[rid][1]) & mem) >= capgen.CAP + 2
            assert 6 <= c["k"] <= 8 and len(c["segs"]) >= 2
            stats.setdefault("k%d" % c["k"], 0)
            stats["k%d" % c["k"]] += 1
            stats.setdefault("attempts_max", 0)
            stats["attempts_max"] = max(stats["attempts_max"], c["attempts"])
            del gn
        others = [r for r in new if r not in meta["capped"]]
        assert all(new[r] == old[r] for r in others), (seed, "non-capped round changed")
        assert any(new[r] != old[r] for r in meta["capped"])
    print("SEEDS_OK", n0, n1, stats, flush=True)
    a, b = picks(NEW, shipped), picks(OLD, shipped)
    diff = [r for r in a if a[r] != b[r]]
    print("SHIPPED_DIFF_ROUNDS", diff, flush=True)


if __name__ == "__main__":
    main(sys.argv)
