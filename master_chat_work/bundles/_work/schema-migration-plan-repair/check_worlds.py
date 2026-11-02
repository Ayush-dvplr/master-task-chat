"""Round 1: cross-check the tests' reference pipeline against repo_fixed.

    python3 check_worlds.py [extra_salts]

Builds every hidden world (and extra worlds from other salts with the same
lever sets), runs repo_fixed's run_pipeline in-process and compares records and
summary with the reference. Prints one line per world.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path

WORK = Path(__file__).resolve().parent
sys.path.insert(0, str(WORK / "rewardkit_stub"))
sys.path.insert(0, str(WORK / "repo_fixed" / "src"))
spec_ = importlib.util.spec_from_file_location("tests_src", WORK / "test_output.src.py")
T = importlib.util.module_from_spec(spec_)
spec_.loader.exec_module(T)
import migrakit  # noqa: E402


def run(world) -> tuple[bool, str, float]:
    spec, lines, seqs, corrections, receipts = world
    expected = T._ref_pipeline(spec, T._feed_text(lines), seqs, T._corrections_text(corrections), receipts)
    job = T._feed_job(spec, lines, seqs, corrections, receipts)
    start = time.time()
    records, summary = migrakit.run_pipeline(job["contracts"], job["feed"], job["corrections"], job["manifest"])
    took = time.time() - start
    if not T._same(records, expected["records"]):
        for a, b in zip(records, expected["records"]):
            if not T._same(a, b):
                return False, json.dumps({"fixed": a, "ref": b}, sort_keys=True)[:900], took
    if not T._same(summary, expected["summary"]):
        return False, json.dumps({"fixed": summary, "ref": expected["summary"]}, sort_keys=True)[:900], took
    statuses = expected["summary"]["by_status"]
    return True, json.dumps(statuses, sort_keys=True), took


def main() -> None:
    extra = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    bad = 0
    for index, name in enumerate(T.WORLDS):
        levers = T._levers(name)
        ok, note, took = run(T._world(name))
        bad += not ok
        print(("OK  " if ok else "BAD ") + f"{name} {took:.2f}s {note}")
        for salt in range(extra):
            w = T._World(5000 + index * 100 + salt, levers)
            for lever in levers:
                if lever in T._GADGETS:
                    T._GADGETS[lever](w)
            T._filler(w, 16)
            for lever in levers:
                if lever in T._LATE_GADGETS:
                    T._LATE_GADGETS[lever](w)
            if "REPORT" in levers:
                T._g_report(w)
            ok, note, took = run(w.finish())
            bad += not ok
            if not ok:
                print(f"BAD {name} salt {salt}: {note}")
    print("failures", bad)


if __name__ == "__main__":
    main()
