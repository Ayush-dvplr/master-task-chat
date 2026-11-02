"""Build-time search for the hidden books embedded in tests/test_output.py (WORK only).

For each hidden book spec, tries generator seeds until: every accepted night has exactly one
maximum-net plan (redraw attempts recorded), every wrong program in cw.VARIANTS plus the
nightly-reset program produces a different plan on at least one night of the book, the naive
collapse plan of some night has a later-starting job's crew window beginning before an
earlier-starting job's window (master point 5), and every bound of the contract holds.
Writes hidden_meta.json with seeds, attempts and the sha256 of each rendered book."""
import hashlib
import json
import os
import sys
import time

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bookgen  # noqa: E402
import cw  # noqa: E402
import datagen  # noqa: E402


def spec(jobs, ov, mand, crew, fee, values, dur, defects=()):
    s = {"jobs": jobs, "overlap": ov, "mand": mand, "crew": crew, "fee": fee, "values": values, "dur": dur}
    if defects:
        s["defects"] = list(defects)
    return s


def book_specs(name, r):
    if name == "H1":
        out = [spec(r.randint(66, 72), 7, r.randint(2, 4), (30, 60), (20, 120), (200, 900), (30, 180))
               for _ in range(5)]
        out.insert(2, spec(9, 4, 1, (30, 60), (20, 120), (200, 900), (30, 180), ["dup", "fee_missing"]))
        return out
    if name == "H2":
        out = [spec(r.randint(20, 48), 6, r.randint(1, 3), (20, 45), (40, 200), (300, 1200), (20, 150))
               for _ in range(8)]
        out.insert(3, spec(10, 4, 1, (20, 45), (40, 200), (300, 1200), (20, 150), ["win_late", "unk_client"]))
        out.insert(7, spec(8, 4, 1, (20, 45), (40, 200), (300, 1200), (20, 150), ["fee_missing"]))
        return out
    if name == "M":
        out = [spec(r.randint(6, 24), r.randint(4, 6), r.randint(0, 2), (15, 50), (20, 200), (200, 900), (30, 180))
               for _ in range(13)]
        out.insert(6, spec(8, 4, 1, (15, 50), (20, 200), (200, 900), (30, 180), ["win_reversed", "unk_client"]))
        return out
    out = [spec(r.randint(60, 72), 7, r.randint(2, 4), (25, 60), (30, 160), (150, 1000), (30, 180))
           for _ in range(6)]
    out.insert(1, spec(9, 4, 1, (25, 60), (30, 160), (150, 1000), (30, 180), ["win_missing", "unk_family"]))
    out.insert(5, spec(7, 4, 1, (25, 60), (30, 160), (150, 1000), (30, 180), ["unk_client"]))
    return out


BOOKS = {"H1": (91001, 400, 300, 61), "H2": (92001, 500, 350, 200), "H3": (93001, 450, 320, 400),
         "M": (94001, 300, 250, 30)}


def check(name, seed):
    base, n_clients, n_sites, start = BOOKS[name]
    r = bookgen._Rng(seed + 3)
    sp = book_specs(name, r)
    th = (r.randint(80, 140), r.randint(1500, 4000))
    t0 = time.time()
    files, attempts, nights, plans, ctx = datagen.build(sp, seed, n_clients, n_sites, th, start)
    t_build = time.time() - t0
    book = {"bays": ctx["bays"], "quals": {b: set(q) for b, q in ctx["quals"].items()},
            "order": [datagen.to_cw(n) for n in nights]}
    ref = [(n["night_id"], p) for n, p in zip(nights, plans)]
    report = {}
    for v, fn in cw.VARIANTS.items():
        runs = cw.run_book(book, fn)
        diff = sum(1 for (a, p), (b, q) in zip(ref, runs) if p != q)
        report[v] = diff
    runs = cw.run_book(book, cw.ref_solver, carry=False)
    report["reset_nightly"] = sum(1 for (a, p), (b, q) in zip(ref, runs) if p != q)
    bays = [(b["bay_id"], b["minute_rate"]) for b in ctx["bays"]]
    fam = {b["bay_id"]: b["initial_family"] for b in ctx["bays"]}
    crossing = 0
    for n, p in zip(nights, plans):
        if p is None:
            continue
        c = datagen.to_cw(n)
        q = cw.solve_night(c, bays, book["quals"], fam, naive=True, count=False)[1]
        if q and cw.crossing_windows(c, bays, fam, q):
            crossing += 1
        J = {j["job_id"]: j for j in n["jobs"]}
        for b, _ in bays:
            seq = sorted((J[i] for i, x in p.items() if x == b), key=lambda j: (j["start"], j["job_id"]))
            if seq:
                fam[b] = seq[-1]["family"]
    if name == "M":
        ok = report["reset_nightly"] >= 1 and report["no_initial"] >= 1
    else:
        ok = all(v >= 1 for v in report.values()) and crossing >= 1
    text = json.dumps(files, sort_keys=True)
    return ok, {"seed": seed, "attempts": attempts, "specs": sp, "thresholds": th, "variants": report,
                "crossing_nights": crossing, "build_s": round(t_build, 2),
                "sha256": hashlib.sha256(text.encode()).hexdigest(),
                "jobs": [len(n["jobs"]) for n in nights]}


def main():
    meta = {}
    for name, (base, *_rest) in BOOKS.items():
        for seed in range(base, base + 40):
            ok, info = check(name, seed)
            print(name, seed, ok, info["variants"], "crossing", info["crossing_nights"], "attempts",
                  info["attempts"], "build_s", info["build_s"], flush=True)
            if ok:
                meta[name] = info
                break
        assert name in meta, name
    with open(os.path.join(HERE, "hidden_meta.json"), "w") as fh:
        json.dump(meta, fh, indent=1)
    print("ALL_DONE")


if __name__ == "__main__":
    main()
