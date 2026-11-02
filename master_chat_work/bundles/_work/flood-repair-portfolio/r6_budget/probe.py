# How to run (inside the capped container only):
#   python3 -B /w/r6_budget/probe.py BOOK PROGRAM [ROUND_IDS...]
"""Per-round timing of a P copy (imported) on one r6 book; prints the slowest rounds."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import time

book_name, program = sys.argv[1], sys.argv[2]
spec = importlib.util.spec_from_file_location('pcopy', program)
assert spec is not None and spec.loader is not None
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)
sys.setrecursionlimit(10000)
meta = json.loads(Path(f'/w/r6_budget/books/{book_name}.meta.json').read_text())
crowd = set(meta.get('crowd', {}))
only = set(sys.argv[3:])
P.set_book_budget(P.BOOK_BUDGET)
t0 = time.monotonic()
book = P.Book(f'/w/r6_budget/books/{book_name}')
print('LOAD', round(time.monotonic() - t0, 3), flush=True)
original = P.plan_round
times = []


def timed(bk, valued, pairs, by_crew):
    rid = valued[0]['round'] if 'round' in valued[0] else None
    start = time.monotonic()
    out = original(bk, valued, pairs, by_crew)
    times.append((round(time.monotonic() - start, 3), len(valued), out[1]))
    return out


P.plan_round = timed
if only:
    book.rounds = [r for r in book.rounds if r in only]
rounds = P.derive(book)
planned = [r for r in book.rounds if rounds[r]['status'] == 'planned']
for rid, (sec, n, total) in zip(planned, times):
    if sec > 0.5 or rid in crowd:
        print('ROUND', rid, 'crowd' if rid in crowd else '-', 'n', n, 'sec', sec, 'total', total, flush=True)
print('TOTAL', round(time.monotonic() - t0, 3), flush=True)
print('ALL_DONE', flush=True)
