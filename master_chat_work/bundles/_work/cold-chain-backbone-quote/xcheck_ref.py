"""Cross-check the new reference block (ref_block.py) against the old one and _enumerate.

python3 -B xcheck_ref.py <template.py> <ref_block.py> <ci dir> books   -> every generator call, shipped book, cases
python3 -B xcheck_ref.py <template.py> <ref_block.py> <ci dir> small N -> N random small projects vs _enumerate
"""
from __future__ import annotations

import hashlib
import heapq
import json
import os
import random
import sys
import time
from pathlib import Path

from book_digests import digest, load

tt = load(sys.argv[1])
ns: dict = {"heapq": heapq}
exec(compile(Path(sys.argv[2]).read_text(), sys.argv[2], "exec"), ns)
CI = Path(sys.argv[3])
MODE = sys.argv[4]
old_opt = tt._optimum
stats = {"calls": 0, "mismatch": [], "old_s": 0.0, "new_s": 0.0, "new_max": 0.0, "shape": {}}


def both(proj):
    t0 = time.perf_counter()
    a = old_opt(proj)
    t1 = time.perf_counter()
    b = ns["_optimum"](proj)
    t2 = time.perf_counter()
    stats["calls"] += 1
    stats["old_s"] += t1 - t0
    stats["new_s"] += t2 - t1
    stats["new_max"] = max(stats["new_max"], t2 - t1)
    if a != b:
        stats["mismatch"].append({"old": repr(a)[:300], "new": repr(b)[:300], "n": proj["n"], "m": len(proj["links"])})
    return a


def docs_digest(docs: dict) -> dict:
    return {d: hashlib.sha256(json.dumps(v, sort_keys=True).encode()).hexdigest()[:16] for d, v in sorted(docs.items())}


if MODE == "books":
    tt._optimum = both
    orig_shape = tt._wide_shape
    METHOD = {"piece by subsets", "piece by sweep"}

    def shape(P):
        br = orig_shape(P)
        others = [b for b in br if b not in METHOD]
        key = "%d branches, %d non-method" % (len(br), len(others))
        stats["shape"][key] = stats["shape"].get(key, 0) + 1
        return br

    tt._wide_shape = shape
    table = {}
    names = ["fresh_1", "fresh_2", "fresh_3", "rescaled", "relocated", "missing", "rejections", "ties",
             "wide_1", "wide_2", "wide_3"]
    if os.environ.get("NAMES"):
        names = os.environ["NAMES"].split(",")
    for name in names:
        t = time.time()
        book = tt._book(name)
        exp = {} if name == "missing" else tt._expected(name)
        table[name] = {"book": digest(book)[:16], "docs": docs_digest(exp), "sec": round(time.time() - t, 1)}
        print(name, table[name], "calls", stats["calls"], "mism", len(stats["mismatch"]), flush=True)
    t = time.time()
    table["shipped"] = {"book": digest(CI)[:16], "docs": docs_digest(tt._expected_documents(CI)),
                        "sec": round(time.time() - t, 1)}
    cases = {}
    for line in (CI / "regression_cases.jsonl").read_text().splitlines():
        case = json.loads(line)
        cases[case["case"]] = tt._case_outcome(case)
    table["cases"] = cases
    print(json.dumps({"table": table, "stats": stats}, indent=1, sort_keys=True))
elif MODE == "small":
    count = int(sys.argv[5])
    rng = random.Random(20261028)
    lbl, queue = ns["_link_by_link"], ns["_one_queue"]
    bad = []
    kinds = {"none": 0, "unique": 0, "tie": 0}
    for case in range(count):
        n = rng.randint(1, 7)
        m = rng.randint(1, 12)
        links = []
        for k in range(m):
            a = rng.randint(0, n)
            b = a if rng.random() < 0.05 else rng.randint(0, n)
            if rng.random() < 0.6 and a != b:
                b = min(n, max(0, a + rng.choice([-2, -1, 1, 2])))
            links.append(("L%03d" % rng.randint(0, 999) + "%02d" % k, min(a, b), max(a, b), rng.randint(1, 5)))
        links.sort()
        proj = {"n": n, "charge": [rng.randint(1, 4) for _ in range(n + 1)],
                "cold": set(rng.sample(range(1, n + 1), rng.randint(1, n))), "links": links}
        want = tt._enumerate(proj)
        want = None if want is None else (want[0], 1 if want[1] == 1 else 2, want[2])
        kinds["none" if want is None else ("unique" if want[1] == 1 else "tie")] += 1
        got = {}
        got["auto"] = ns["_optimum"](proj)
        ns["_one_queue"] = lbl
        got["lbl"] = ns["_optimum"](proj)
        ns["_one_queue"], ns["_link_by_link"] = queue, queue
        got["queue"] = ns["_optimum"](proj)
        ns["_link_by_link"] = lbl
        got["old"] = old_opt(proj)
        for k, v in got.items():
            if v != want:
                bad.append({"case": case, "how": k, "want": repr(want), "got": repr(v), "proj": repr(proj)})
    print(json.dumps({"count": count, "kinds": kinds, "bad": len(bad), "first_bad": bad[:5]}, indent=1))
