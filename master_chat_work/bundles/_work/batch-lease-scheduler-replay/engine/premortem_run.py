"""Run refsim vs heap(flags) on hidden books; report per set which documents differ."""
import json
import sys
import time

import gen
import heap
import refsim

DOCS = ("core", "metrics", "deps", "summary")
FLAGSETS = {
    "clean": set(),
    "FW1": {"FW1"}, "FW2": {"FW2"}, "FW2R": {"FW2R"}, "FW3": {"FW3"}, "FW3b": {"FW3b"},
    "FW4": {"FW4"}, "FW5": {"FW5"}, "LAZY": {"LAZY"}, "PREFAIL": {"PREFAIL"}, "STALE": {"STALE"},
    "ANYTERM": {"ANYTERM"}, "SUBORDER": {"SUBORDER"}, "REDUP": {"REDUP"}, "PEREVENT": {"PEREVENT"},
    "PRECSWAP": {"PRECSWAP"}, "FIRSTWRITE": {"FW3b", "FW4", "FW5"},
}


def per_set_diff(a, b):
    """a, b: 4-tuples of docs. returns {sid: [doc names that differ]}"""
    out = {}
    for name, x, y in zip(DOCS, a, b):
        for sid in x["sets"]:
            if x["sets"][sid] != y["sets"][sid]:
                out.setdefault(sid, []).append(name)
    return out


def main(seeds, profile="hidden", nsets=3):
    books = {sd: gen.make_book(sd, profile, nsets) for sd in seeds}
    stats = {}
    for sd, b in books.items():
        st = {sid: (len(s["jobs"]), len(s["workers"]), len(s["events"]), len(s["checkpoints"]))
              for sid, s in b["sets"].items()}
        stats[sd] = st
    if nsets <= 5:
        print("book stats (jobs, workers, events, cps):", json.dumps({str(k): {str(a): v for a, v in st.items()}
                                                                        for k, st in stats.items()}))
    refs = {}
    for sd, b in books.items():
        t0 = time.time()
        refs[sd] = refsim.documents(b)
        print("refsim seed", sd, "%.2fs" % (time.time() - t0))
    report = {}
    for name, fl in FLAGSETS.items():
        row = {}
        for sd, b in books.items():
            t0 = time.time()
            got = heap.documents(b, fl)
            dt = time.time() - t0
            d = per_set_diff(refs[sd], got)
            row[sd] = {"sets_wrong": len(d), "docs": {str(k): v for k, v in d.items()}, "sec": round(dt, 2)}
        report[name] = row
        lost = sum(len(v) for r in row.values() for v in r["docs"].values())
        corp = {sd: len({dn for v in r["docs"].values() for dn in v}) for sd, r in row.items()}
        print("%-9s set-docs wrong %2d/%d sets-wrong %s corpus-docs-wrong(of 4) %s" % (
            name, lost, 4 * 3 * len(seeds), [r["sets_wrong"] for r in row.values()], list(corp.values())))
    return report


if __name__ == "__main__":
    prof = sys.argv[1]
    nsets = int(sys.argv[2])
    seeds = [int(x) for x in sys.argv[3:]] or [11, 22, 33, 44]
    rep = main(seeds, prof, nsets)
    json.dump(rep, open("premortem_report.json", "w"), indent=1)
