# Run inside the capped container only (python3 -B), verifier tests dir mounted read-only.
#   python3 -B vtool.py digest <tests_dir> <out.json>      old-check books: input and expected digests
#   python3 -B vtool.py books <tests_dir> <out_dir>         write hidden books H1-H3 (+ meta) as the verifier builds them
#   python3 -B vtool.py shape300 <tests_dir> <out.json>     300 seeds of a reduced spec through make_book, all assertions
"""Loads the verifier (tests/test_output.py) with a stub rewardkit and drives its generator and oracle."""
from __future__ import annotations

import hashlib
import json
import sys
import time
import types
from multiprocessing import Pool
from pathlib import Path


def load(tests: Path):
    stub = types.ModuleType("rewardkit")

    class _Any:
        def __getattr__(self, name):
            return lambda *a, **k: None

    def criterion(**kw):
        return lambda f: f
    stub.criteria = _Any()
    stub.criterion = criterion
    sys.modules["rewardkit"] = stub
    ns = {"__name__": "verifier_under_test"}
    src = tests / "test_output.py"
    exec(compile(src.read_text(), str(src), "exec"), ns)
    return ns


def sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()


def digest(ns, out: Path) -> None:
    res = {}
    for name in ("SHIPPED", "M", "MS", "MR"):
        t = time.time()
        res[name] = {"files": sha(ns["book_files"](name)), "expected": sha(ns["expected"](name)),
                     "seconds": round(time.time() - t, 2)}
        print(name, res[name], flush=True)
    for name in ("H1", "H2", "H3"):
        entry = ns["_BOOKS"][name]
        files, meta = ns["make_book"](entry["seed"], entry["spec"])
        res[name] = {"files": sha(files), "pinned": entry["sha256"], "crowd": meta.get("crowd")}
        print(name, res[name]["files"], res[name]["pinned"], flush=True)
    out.write_text(json.dumps(res, indent=1, sort_keys=True))


def books(ns, out: Path) -> None:
    for name in ("H1", "H2", "H3"):
        files = ns["book_files"](name)
        entry = ns["_BOOKS"][name]
        _, meta = ns["make_book"](entry["seed"], entry["spec"])
        d = out / name
        d.mkdir(parents=True, exist_ok=True)
        for k, v in files.items():
            (d / k).write_text(v)
        (out / (name + ".meta.json")).write_text(json.dumps(meta, indent=1, sort_keys=True, default=list))
        print("BOOK", name, sha(files), "crowd", sorted(meta.get("crowd", {})), flush=True)


NS = None


def one_seed(seed: int):
    ns = NS
    spec = {"audit_large": 60, "audit_small": 12, "blank_row": 50, "capped": 3, "crews": 1500,
            "faults": 12, "order": "shuffle", "permits": 1200, "sites": 900, "small": 40, "ties": 8,
            "large": ([(156, 13), (160, 14)], [(148, 12), (160, 13)], [(152, 14), (144, 12)])[seed % 3] * 2,
            "crowd": [0, 2]}
    try:
        files, meta = ns["make_book"](9000 + seed, spec)
        props = files["proposals.csv"].splitlines()[1:]
        per = {}
        for line in props:
            if line:
                per[line.split(",")[0]] = per.get(line.split(",")[0], 0) + 1
        crowd = meta["crowd"]
        assert len(crowd) == 2, crowd
        for rid, c in crowd.items():
            assert per[rid] == 160, (rid, per[rid])
            rows = [l.split(",") for l in props if l and l.split(",")[0] == rid]
            assert sum(r[3] == c["crew"] for r in rows) == 10
        assert max(per.values()) <= 160
        return seed, None
    except Exception as exc:  # report every failing seed
        return seed, repr(exc)


def shape300(tests: Path, out: Path) -> None:
    global NS
    NS = load(tests)
    with Pool(2) as pool:
        res = pool.map(one_seed, range(1, 301))
    errs = [(s, e) for s, e in res if e]
    out.write_text(json.dumps({"seeds": 300, "errors": errs}, indent=1))
    print("SEEDS 300 errors", len(errs), errs[:5], flush=True)


if __name__ == "__main__":
    mode, tests, out = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    if mode == "shape300":
        shape300(tests, out)
    else:
        ns = load(tests)
        {"digest": digest, "books": books}[mode](ns, out)
    print("ALL_DONE", flush=True)
