"""Rewrite solution/TRUTH.md for the fc1fb76 round. Content part runs once (guarded); sha part always."""
import hashlib, re, sys
from pathlib import Path
B = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/tariff-engine-audit-repair")
p = B / "solution/TRUTH.md"
s = p.read_text()
def sub(old, new):
    global s
    assert s.count(old) == 1, old[:70]
    s = s.replace(old, new)
if "(lever S1)" not in s:
    sub("""    accounts rows with an inactive count in the gap.

## Load-bearing work""", """    accounts rows with an inactive count in the gap.
24. (lever S1) the package has no statement document. The contract adds
    `python -m tariff --statements <data_dir>`: one statement per account in the optional
    `vouchers.csv`, with `balance` (invoice totals less paid amounts, 0.00 below zero),
    `redeemed` (the ids, in plain string order, of the vouchers whose amounts add up to the
    largest sum not above the balance, the first id list on ties, `[]` when none fits) and
    `due`, within 10 seconds. The oracle keeps, for each voucher in id order, the set of
    sums the later vouchers reach (an integer used as a bit set over cents), takes the top
    reachable sum, and walks the vouchers in id order, taking each one whose remainder is
    still reachable; this is exact and gives the first id list. Hidden corpora copy three
    accounts with their reads scaled so the balance is 50,000.00 to 90,000.00, give each
    45 to 70 vouchers whose amounts share a factor the balance lacks (the balance itself
    is never reached), and add small accounts with equal-sum ties, an overpaid account at
    balance 0.00, and accounts that carry one quiet rule (cumulative reads, arrears,
    estimated reads, standing changes, meter rows, carried allowance, revisions), so a
    slip there moves the balance and the redeemed set.

## Load-bearing work""")
    sub("The test channel registers 67 positive checks worth 301 points and 2 negative checks,",
        "The test channel registers 89 positive checks worth 397 points and 2 negative checks,")
    sub("""  meter exchange (5). `_assert_levers` checks that each lever read the habitual way
  changes exactly its accounts and that the rest of the corpus is unchanged.
""", """  meter exchange (5). `_assert_levers` checks that each lever read the habitual way
  changes exactly its accounts and that the rest of the corpus is unchanged.
- Statements: the shipped statement document whole (5); on each hidden statement corpus
  (own random stream, seed x 53 + 29) the accounts, balances and a feasible redeemed set
  (3), every `due` (5) and every `redeemed` list (5). The statement command is run with
  `--statements` and stopped after 10 seconds. The invoice corpora are not changed by
  the statement planting; `_assert_statements` checks that every invoice outside the
  copied accounts is unchanged and that each corpus holds at least two ties.
""")
    sub("Measured on real runs (test points of 301): the oracle scores 301;",
        "Measured on real runs (test points of 397): the oracle scores 397; no statement "
        "command 301; largest voucher first 322; every subset tried, or a table of sums, "
        "306 (no output in 10 seconds on any hidden corpus); a different set reaching the "
        "best sum, or ids in numeric order, 357. Before the round-3 statements (test points "
        "of 301): the oracle scores 301;")
    sub("""- Billing a cumulative count as written, or chaining counts in file order or per row.
""", """- Billing a cumulative count as written, or chaining counts in file order or per row.
- Redeeming the largest vouchers first, a search that cannot finish in 10 seconds on a
  large balance, a different set of equal sum, or ids in numeric order.
""")
    sub("  The test channel carries 67 positive checks worth 301 weight and 2 negative",
        "  The test channel carries 89 positive checks worth 397 weight and 2 negative")
if len(sys.argv) > 1:
    trial, date = sys.argv[1], sys.argv[2]
    s = re.sub(r"golden_score_trial_id: \S+", "golden_score_trial_id: " + trial, s)
    s = re.sub(r"three runs on \S+ \(test-hardening round\n  \w+\)", f"three runs on {date} (test-hardening round\n  fc1fb76)", s)
sh = hashlib.sha256((B / "solution/solve.sh").read_bytes()).hexdigest()
py = hashlib.sha256((B / "solution/solve.py").read_bytes()).hexdigest()
s = re.sub(r"fix_patch_sha256: [0-9a-f]{64}", "fix_patch_sha256: " + sh, s)
s = re.sub(r"solve_py_sha256: [0-9a-f]{64}", "solve_py_sha256: " + py, s)
p.write_text(s)
print("ok", py[:12])
