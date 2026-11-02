"""Run every kill-test solver on every proto corpus with the 10 s CLI limit.

usage: python3 -B run_kill.py [solver ...]  -> proto/kill_results.json + table on stdout
Points per corpus as the new checks would carry them: feasible 3, due 5, redeemed 5.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import solvers  # noqa: E402

LIMIT = 10
ORDER = ["reference", "blind_r3", "bitset", "table", "pareto", "mitm", "mitm_dedupe",
         "mitm_dedupe_sorted", "branch_bound", "greedy", "naive"]


def score(data, got):
    owned = {a["account"]: dict(map(tuple, a["vouchers"])) for a in data["accounts"]}
    feasible = got is not None and set(got) == set(owned)
    due = redeemed = feasible
    if feasible:
        for account in data["accounts"]:
            name = account["account"]
            ids = got[name]
            amounts = owned[name]
            if len(set(ids)) != len(ids) or any(i not in amounts for i in ids):
                feasible = due = redeemed = False
                break
            spent = sum(amounts[i] for i in ids)
            if spent > account["balance"]:
                feasible = due = redeemed = False
                break
            want = solvers.reference(account["balance"], [tuple(v) for v in account["vouchers"]])
            if spent != sum(amounts[i] for i in want):
                due = redeemed = False
            if ids != want:
                redeemed = False
    return 3 * feasible + 5 * due + 5 * redeemed


def main():
    names = sys.argv[1:] or ORDER
    corpora = sorted(HERE.glob("corpus_*.json"), key=lambda p: int(p.stem.split("_")[1]))
    results = {}
    for name in names:
        for path in corpora:
            data = json.loads(path.read_text())
            start = time.monotonic()
            try:
                run = subprocess.run([sys.executable, "-B", str(HERE / "solvers.py"), name, str(path)],
                                     capture_output=True, text=True, timeout=LIMIT)
                seconds = time.monotonic() - start
                got = {}
                for line in run.stdout.splitlines():
                    got.update(json.loads(line))
                status = "ok" if run.returncode == 0 else "rc%d" % run.returncode
                if run.returncode != 0:
                    got = None
            except subprocess.TimeoutExpired:
                seconds, got, status = LIMIT, None, "timeout"
            points = score(data, got)
            results.setdefault(name, {})[path.stem] = {"seconds": round(seconds, 2), "status": status,
                                                         "points": points}
            print(name, path.stem, round(seconds, 2), status, points, flush=True)
    (HERE / ("kill_results_%s.json" % "_".join(names) if sys.argv[1:] else "kill_results.json")).write_text(
        json.dumps(results, indent=1))
    print("ALL_DONE")


if __name__ == "__main__":
    main()
