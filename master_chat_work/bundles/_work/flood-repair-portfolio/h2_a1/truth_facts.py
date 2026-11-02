"""Facts for TRUTH.md (DS-22) on the books the tests regenerate.

Run in the verifier image: python3 -B truth_facts.py /tests/test_output.py /w
Per book: large rounds (more than 40 proposals), sizes, conflicts per proposal, conflict
records, sweep frontier width, share of pairs per source, and maximiser counts.
"""
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

spec = importlib.util.spec_from_file_location("t", sys.argv[1])
T = importlib.util.module_from_spec(spec)
spec.loader.exec_module(T)
sys.path.insert(0, sys.argv[2])
import solve_draft as S  # noqa: E402
from count_opt import count_best  # noqa: E402


def width(order, adj):
    pos = {v: i for i, v in enumerate(order)}
    last = {v: max([pos[u] for u in adj[v]] + [pos[v]]) for v in order}
    live, best, ends = 0, 0, [0] * (len(order) + 1)
    for i, v in enumerate(order):
        live += 1
        ends[last[v]] += 1
        live -= ends[i]
        best = max(best, live)
    return best


for name in ("SHIPPED", "H1", "H2", "H3", "M"):
    with tempfile.TemporaryDirectory() as td:
        data = T._write_book(Path(td) / "b", T.book_files(name))
        book = S.load(str(data))
        rounds = S.build(book)
    large, small_ties, small_many, src = [], 0, 0, {"crew": 0, "permit": 0, "exclusion": 0, "site": 0, "all": 0}
    for r in rounds:
        if r.fault is not None:
            continue
        _, c = count_best(r)
        n = len(r.ids)
        if n <= 40:
            small_ties += c == 2
            small_many += c > 2
            continue
        adj = {p: set() for p in r.ids}
        for a, b in r.pairs:
            adj[a].add(b)
            adj[b].add(a)
        w = max(width(S.sweep_order(sorted(part), adj), adj) for part in [r.ids])
        site_pairs = set()
        for first, second in r.exclusions:
            if first.startswith("S") or second.startswith("S"):
                ga = [p for p in r.ids if r.detail[p]["site"] == first] if first not in r.detail else [first]
                gb = [p for p in r.ids if r.detail[p]["site"] == second] if second not in r.detail else [second]
                site_pairs |= {(min(a, b), max(a, b)) for a in ga for b in gb if a != b}
        for pair, sources in r.pairs.items():
            src["all"] += 1
            for s in sources:
                src[s] += 1
            src["site"] += pair in site_pairs
        large.append({"n": n, "deg": round(2 * len(r.pairs) / n, 2), "records": len(r.permits) + len(r.exclusions),
                      "width": w, "count": c})
    out = {
        "book": name, "rounds": len(rounds), "large": len(large),
        "n": [min(x["n"] for x in large), max(x["n"] for x in large)],
        "deg": [min(x["deg"] for x in large), max(x["deg"] for x in large),
                round(sum(x["deg"] for x in large) / len(large), 2)],
        "records": [min(x["records"] for x in large), max(x["records"] for x in large)],
        "width": [min(x["width"] for x in large), max(x["width"] for x in large)],
        "large_count_not_1": sum(x["count"] != 1 for x in large),
        "large_counts": sorted({x["count"] for x in large}),
        "small_count2": small_ties, "small_count_gt2": small_many,
        "share": {k: round(v / src["all"], 3) for k, v in src.items() if k != "all"},
    }
    print(json.dumps(out), flush=True)
print("ALL_DONE", flush=True)
