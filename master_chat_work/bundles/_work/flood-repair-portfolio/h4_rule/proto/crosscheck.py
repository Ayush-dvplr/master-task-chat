"""Embedded-reference prototype + cross-check: python3 -B crosscheck.py N0 N1 BOOKDIR...

Builds the verifier's _Ledger from BUNDLE tests/test_output.py (source slice _records .. expected),
with the one planned edit: `chosen = _portfolio(info, joined)` -> `chosen = _capped(info, joined, self.mode)`
plus the _capped helper below (enumerates allowed four-subsets of each over-full shared crew).
Compares its documents with proto/solve.py documents on seeds N0..N1 (make_book2, two capped rounds)
and on every BOOKDIR given (Hc/Mc books, shipped data).
"""
import itertools
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import capgen  # noqa: E402
import shape300  # noqa: E402

BUNDLE = os.environ.get("BUNDLE", "/b")

CAPPED_SRC = '''

def _capped(info, joined, mode):
    crews = {}
    for p, d in info.items():
        if mode[d["crew"]] == "shared":
            crews.setdefault(d["crew"], []).append(p)
    over = [sorted(ps) for ps in crews.values() if len(ps) > 4]
    if not over:
        return _portfolio(info, joined)
    best = None
    for keep in itertools.product(*(itertools.combinations(ps, 4) for ps in over)):
        out = {p for ps in over for p in ps} - {p for ks in keep for p in ks}
        part = {p: d for p, d in info.items() if p not in out}
        pick = _portfolio(part, {k: v for k, v in joined.items() if not k & out})
        key = (-sum(info[p]["benefit"] for p in pick), sorted(pick))
        if best is None or key < best:
            best = key
    return best[1]
'''


def ledger_ns():
    text = open(os.path.join(BUNDLE, "tests", "test_output.py"), encoding="utf-8").read()
    body = text[text.index("def _records"):text.index("def expected(")]
    old = "chosen = _portfolio(info, joined)"
    assert body.count(old) == 1
    body = body.replace(old, "chosen = _capped(info, joined, self.mode)") + CAPPED_SRC
    head = ("from __future__ import annotations\nimport configparser, csv, io, itertools, json, re\n"
            "from typing import Any\nfrom pathlib import Path\n"
            + text[text.index("OUT = Path("):text.index("_SETPRIV")]
            + text[text.index("SEGMENTS = ("):text.index("FAULT_KINDS = (")])
    ns = {"__name__": "ledger_proto"}
    exec(compile(head + body, "ledger_proto", "exec"), ns)
    return ns


NS = ledger_ns()


def read_dir(d):
    return {k: open(os.path.join(d, k), encoding="utf-8").read() for k in os.listdir(d)
            if os.path.isfile(os.path.join(d, k))}


def compare(label, d):
    files = read_dir(d)
    t0 = time.time()
    want = NS["_Ledger"](files).documents()
    t1 = time.time()
    book = shape300.NEW.load(d)
    got = shape300.NEW.documents(book, shape300.NEW.build(book))
    got = json.loads(json.dumps(got))
    bad = sorted(k for k in want if want[k] != got.get(k))
    assert not bad and set(got) == set(want), (label, bad)
    return t1 - t0


def main(argv):
    n0, n1 = int(argv[1]), int(argv[2])
    worst = 0.0
    for seed in range(n0, n1):
        files, meta = capgen.make_book2(seed, shape300.SPEC)
        with tempfile.TemporaryDirectory() as d:
            for k, v in files.items():
                with open(os.path.join(d, k), "w") as fh:
                    fh.write(v)
            worst = max(worst, compare(seed, d))
    print("SEEDS_SAME", n0, n1, "ledger_worst_s %.2f" % worst, flush=True)
    for d in argv[3:]:
        print("BOOK_SAME", os.path.basename(d.rstrip("/")), "ledger_s %.2f" % compare(d, d), flush=True)


if __name__ == "__main__":
    main(sys.argv)
