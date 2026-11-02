"""G12 sweep: the embedded generator and reference over 300 seeds.

Usage: sweep300.py <tests file> <first seed> <count> [processes]
Each seed builds a fresh book, a rescaled book, a rejection book, a tie book and
a wide book, asserts the generator shape and that every planted branch is
present, and times the reference per project.
"""
import multiprocessing
import os
import sys
import tempfile
import time
from pathlib import Path

import book_digests

t = None


def _load():
    global t
    if t is None:
        t = book_digests.load(sys.argv[1])
    return t


def bounds(book, need_cold, narrow):
    data = t._read_book(book)
    for pid, proj in data["accepted"].items():
        assert proj["n"] + 1 <= 52, pid
        assert len(proj["links"]) <= 95, pid
        assert len(proj["cold"]) <= 17, pid
        if need_cold:
            assert 8 <= len(proj["cold"]) <= 10, pid
        assert all(c > 0 for c in proj["charge"]), pid
        assert all(lk[3] > 0 for lk in proj["links"]), pid
        if narrow:
            assert all(lo == 0 or hi - lo <= t.WIDTH for _, lo, hi, _ in proj["links"]), pid
    return data


def one(seed):
    _load()
    worst = 0.0
    base = Path(tempfile.mkdtemp(prefix="sweep"))
    fresh = t._make_fresh(seed, base / "fresh")
    text = (fresh / "activation.ini").read_text()
    assert "[overrides]" in text and text.split("[overrides]")[1].strip(), seed
    assert '"L' in (fresh / "access_rules.toml").read_text().split("[closed]")[1], seed
    data = bounds(fresh, True, True)
    assert len(data["accepted"]) == 10 and not data["rejected"], seed
    for proj in data["accepted"].values():
        start = time.time()
        found = t._optimum(proj)
        worst = max(worst, time.time() - start)
        assert found is not None and found[1] == 1, seed
    bounds(t._make_rescaled(seed, base / "rescaled"), True, True)
    rej = bounds(t._make_rejections(seed, base / "rej"), False, False)
    codes = set(rej["rejected"].values())
    assert codes == {"E_DUP_SITE", "E_UNKNOWN_ENDPOINT", "E_NO_NETWORK"}, (seed, codes)
    assert len(rej["accepted"]) in (4, 5), (seed, sorted(rej["accepted"]))
    ties = bounds(t._make_ties(seed, base / "ties"), False, True)
    for proj in ties["accepted"].values():
        assert t._enumerate(proj)[1] == 2 and t._optimum(proj)[1] == 2, seed
    if os.environ.get("SWEEP_SKIP_WIDE"):  # wide generator unchanged in 25c745d (AST + digests)
        return seed, worst, {"n": (0, 0), "cold": (0, 0), "links": (0, 0)}
    # wide book: the generator itself asserts the five planted branches per project
    wide = t._read_book(t._make_wide(seed, base / "wide"))
    assert len(wide["accepted"]) == 10 and not wide["rejected"], seed
    counts = []
    shape = {"n": [], "cold": [], "links": []}
    for proj in wide["accepted"].values():
        start = time.time()
        found = t._optimum(proj)
        worst = max(worst, time.time() - start)
        assert found is not None, seed
        counts.append(found[1])
        shape["n"].append(proj["n"])
        shape["cold"].append(len(proj["cold"]))
        shape["links"].append(len(proj["links"]))
        assert len(proj["cold"]) >= 28 and all(lk[3] > 0 for lk in proj["links"]), seed
        assert max(hi - lo for _, lo, hi, _ in proj["links"] if lo > 0) >= proj["n"] // 2, seed
    assert sorted(counts) == [1] * 9 + [2], (seed, counts)
    return seed, worst, {k: (min(v), max(v)) for k, v in shape.items()}


def main():
    first, count = int(sys.argv[2]), int(sys.argv[3])
    procs = int(sys.argv[4]) if len(sys.argv) > 4 else 1
    worst = 0.0
    lo = {"n": 10**9, "cold": 10**9, "links": 10**9}
    hi = {"n": 0, "cold": 0, "links": 0}
    with multiprocessing.Pool(procs, initializer=_load) as pool:
        for seed, w, shape in pool.imap_unordered(one, range(first, first + count)):
            worst = max(worst, w)
            for k, (a, b) in shape.items():
                lo[k] = min(lo[k], a)
                hi[k] = max(hi[k], b)
            print("seed", seed, "ok worst", round(w, 3), shape, flush=True)
    print("SWEEP PASS seeds", count, "worst reference seconds per project", round(worst, 3),
          "wide n", lo["n"], hi["n"], "cold", lo["cold"], hi["cold"], "links", lo["links"], hi["links"])
    print("ALL_DONE")


if __name__ == "__main__":
    main()
