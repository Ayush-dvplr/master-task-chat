"""Rewrite solution/TRUTH.md for wave 1 (d11904c). Content part runs once (guarded); sha part always.
usage: python3 -B truth4.py [TRIAL DATE]   (measured points read from t4_results/cost_docker.json)"""
import hashlib, json, re, sys
from pathlib import Path
B = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/tariff-engine-audit-repair")
W = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/tariff-engine-audit-repair")
p = B / "solution/TRUTH.md"
s = p.read_text()


def sub(old, new):
    global s
    assert s.count(old) == 1, old[:70]
    s = s.replace(old, new)


if "ledger corpus" not in s:
    cost = json.loads((W / "t4_results/cost_docker.json").read_text())

    def pts(name):
        return cost[name]["earned"]

    sub("""    `due`, within 10 seconds. The oracle keeps, for each voucher in id order, the set of
    sums the later vouchers reach (an integer used as a bit set over cents), takes the top
    reachable sum, and walks the vouchers in id order, taking each one whose remainder is
    still reachable; this is exact and gives the first id list. Hidden corpora copy three""",
        """    `due`, within 10 seconds. The oracle sorts the amounts and looks for the fewest
    small vouchers whose total stays below the common unit (greatest common divisor) of
    the rest. The rest is searched in that unit: for each voucher in id order it keeps the
    set of unit counts the later vouchers reach (an integer used as a bit set), takes the
    top count not above the balance and walks the vouchers in id order, taking each one
    whose remainder is still reachable. The small vouchers are tried in every combination
    for what is left; the first id list of each part together is the first id list of the
    whole, and no smaller unit part can win because the small ones add up to less than one
    unit. This is exact on every input. Hidden corpora copy three""")
    sub("""    slip there moves the balance and the redeemed set.

## Load-bearing work""", """    slip there moves the balance and the redeemed set. Seven further ledger corpora copy
    three accounts with their reads scaled so the balance is 400 to 800 million (in
    cents 4e10 to 8e10), and give each 46 to 55 vouchers that are multiples of one unit
    of 500.00 to 999.99 plus 9 to 11 small vouchers adding up to less than that unit, with
    equal-sum ties planted in both groups; a table over cents or over one sum, a split in
    two halves, a list of kept sums or a bounded search gives no output within 10 seconds.
    The shipped account A1643 shows the same two groups at a small balance (311.48).

## Load-bearing work""")
    sub("The test channel registers 89 positive checks worth 397 points and 2 negative checks,",
        "The test channel registers 110 positive checks worth 488 points and 2 negative checks,")
    sub("""  the statement planting; `_assert_statements` checks that every invoice outside the
  copied accounts is unchanged and that each corpus holds at least two ties.
""", """  the statement planting; `_assert_statements` checks that every invoice outside the
  copied accounts is unchanged and that each corpus holds at least two ties.
- Ledger statements: on each hidden ledger corpus (own random stream, seed x 59 + 31)
  the accounts, balances and a feasible redeemed set (3), every `due` (5) and every
  `redeemed` list (5), run and stopped the same way. `_assert_ledger` checks that every
  invoice outside the copied accounts is unchanged, that each big balance lies between
  3e10 and 1e11 cents, that both voucher groups are used, that the overpaid account has
  balance 0.00, and that each corpus holds a tie in each group.
""")
    sub("Measured on real runs (test points of 397): the oracle scores 397;",
        f"Measured on real runs (test points of 488): the oracle scores {pts('oracle')}; "
        f"the round-3 blind program (a bit set over cents) {pts('blind_r3')}; a bit set over "
        f"cents {pts('solver:bitset')}; a table of sums {pts('solver:table')}; two halves "
        f"{pts('solver:mitm')}; a list of kept sums {pts('solver:pareto')}; a bounded search "
        f"{pts('solver:branch_bound')}; largest voucher first {pts('solver:greedy')}; every "
        f"subset tried {pts('solver:naive')}; revisions ignored {pts('U1_off')}. Before the "
        "wave-1 ledger statements (test points of 397): the oracle scores 397;")
    sub("""- Redeeming the largest vouchers first, a search that cannot finish in 10 seconds on a
  large balance, a different set of equal sum, or ids in numeric order.
""", """- Redeeming the largest vouchers first, a search that cannot finish in 10 seconds on a
  large balance, a different set of equal sum, or ids in numeric order.
- A table over cents or a split in two halves on a ledger balance of hundreds of millions.
""")
    sub("  The test channel carries 89 positive checks worth 397 weight and 2 negative",
        "  The test channel carries 110 positive checks worth 488 weight and 2 negative")
if len(sys.argv) > 1:
    trial, date = sys.argv[1], sys.argv[2]
    s = re.sub(r"golden_score_trial_id: \S+", "golden_score_trial_id: " + trial, s)
    s = re.sub(r"three runs on \S+ \(test-hardening round\n  \w+\)", f"three runs on {date} (test-hardening round\n  d11904c)", s)
sh = hashlib.sha256((B / "solution/solve.sh").read_bytes()).hexdigest()
py = hashlib.sha256((B / "solution/solve.py").read_bytes()).hexdigest()
s = re.sub(r"fix_patch_sha256: [0-9a-f]{64}", "fix_patch_sha256: " + sh, s)
s = re.sub(r"solve_py_sha256: [0-9a-f]{64}", "solve_py_sha256: " + py, s)
p.write_text(s)
print("ok", py[:12])
