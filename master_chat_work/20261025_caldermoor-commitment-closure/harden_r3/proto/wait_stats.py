"""Feasibility of candidate N2 (wait along the blocking chain) on hidden seeds. Runs in the verifier image.

For each seed: build corpus (optionally survivor fixture), run the oracle, then from its outputs compute
wait(b) = 1 + max(wait of blocked blockers, 0) over blocking edges leaving b, compare with chain_depth,
and count principal-months whose reserve would move and whose allocation would move.
usage: python3 -B /proto/wait_stats.py seed [seed ...]
"""
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, "/tests")
import test_output as T  # noqa: E402


def stats(out):
    led = {}
    for line in open(os.path.join(out, "commitment_ledger.jsonl")):
        r = json.loads(line)
        led[r["commitment_key"]] = r
    blocked = {r["commitment_key"]: r for r in csv.DictReader(open(os.path.join(out, "blocked_commitments.csv")))}
    hold = {k for k, r in led.items() if r["resolved_state"] in ("OPEN", "DEFERRED")}
    nxt = {}
    for e in csv.DictReader(open(os.path.join(out, "live_edges.csv"))):
        if e["blocker_key"] in hold:
            nxt.setdefault(e["dependent_key"], set()).add(e["blocker_key"])
    memo = {}

    def wait(k):
        if k not in blocked:
            return 0
        if k not in memo:
            memo[k] = 1 + max(wait(x) for x in nxt.get(k, ()))
        return memo[k]

    diff = [k for k in blocked if wait(k) != int(blocked[k]["chain_depth"])]
    load = {(r["obligor_actor"], r["year_month"]): r for r in csv.DictReader(open(os.path.join(out, "month_load_index.csv")))}
    pm_res, pm_alloc = set(), set()
    for k in diff:
        pm = (led[k]["obligor_actor"], led[k]["commitment_day"][:7])
        pm_res.add(pm)
        r = load.get(pm)
        if r and int(r["demand_minutes"]) > max(0, int(r["budget_minutes"]) - int(r["reserve_minutes"])) - 1:
            pm_alloc.add(pm)
    longer = sum(1 for k in diff if wait(k) > int(blocked[k]["chain_depth"]))
    return {"blocked": len(blocked), "wait_ne_depth": len(diff), "wait_gt_depth": longer,
            "pm_reserve_moves": len(pm_res), "pm_alloc_moves": len(pm_alloc), "pm_total": len(load)}


def main():
    for s in sys.argv[1:]:
        seed = int(s)
        tmp = tempfile.mkdtemp()
        try:
            files, _w = T.build_all(seed)
            data = os.path.join(tmp, "data")
            os.makedirs(data)
            for n, t in files.items():
                open(os.path.join(data, n), "w", encoding="utf-8", newline="").write(t)
            out = os.path.join(tmp, "out")
            os.makedirs(out)
            shutil.copy("/solution/solve.py", os.path.join(tmp, "reconcile.py"))
            subprocess.run([sys.executable, "-B", os.path.join(tmp, "reconcile.py"), data, out], check=True,
                           capture_output=True)
            print(seed, json.dumps(stats(out)))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
