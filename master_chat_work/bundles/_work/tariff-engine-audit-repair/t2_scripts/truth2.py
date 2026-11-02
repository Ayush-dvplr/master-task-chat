"""Rewrite solution/TRUTH.md for the 15b380e round. Content part runs once (guarded); sha part always."""
import hashlib, re, sys
from pathlib import Path
B = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/tariff-engine-audit-repair")
p = B / "solution/TRUTH.md"
s = p.read_text()
def sub(old, new):
    global s
    assert s.count(old) == 1, old[:70]
    s = s.replace(old, new)
if "(lever U1)" not in s:
    sub("""    windows with a gap read that is `inactive_meter`.
""", """    windows with a gap read that is `inactive_meter`.
21. (lever U1) `report` rates every invoice with the plan's own `tiers`. A plan can carry
    `revisions`, and the optional `payments.csv` gives paid amounts per invoice. The
    contract's Tier definition rates a plan's invoices with the `tiers` of the one revision
    under which every invoice on the plan that has a paid amount totals exactly that
    amount, and with the plan's own `tiers` when no revision or more than one does. The
    totals that must match come out of the whole account chain (carried allowance,
    account position over meters, re-shared allowance, arrears), so a revision fits only
    when every other rule is read right. The shipped card has no `revisions` and no
    `payments.csv` ships; every hidden corpus plants a plan with one fitting revision
    listed after a revision that fits only some paid amounts, a plan with two fitting
    revisions and a plan with none, plus two-row accounts on the first plan.
22. (lever D1) the credit ignores payments. The Credit paragraph gives an invoice no
    credit when the account's previous invoice by `start` has a paid amount below that
    invoice's total; an invoice with no `payments.csv` row has no paid amount. Hidden
    corpora plant four-invoice chains (underpaid, then paid at the credited figure of an
    invoice that lost its credit, then paid in two rows, then unpaid) and three-invoice
    chains with carried allowance and a standing change, rows written out of order.
23. (lever D2) a read with `cumulative` `true` holds the meter's running count. Its billed
    quantity is its count less the count of the same account and meter's accepted
    cumulative read with the latest earlier `day`; 0 without one, the whole count when the
    earlier count is larger. Hidden corpora plant counts written out of day order, a
    rejected count before the period, an estimated count replaced by an actual one, a
    drop to a lower count, chains across two billing rows and a meter exchange across two
    accounts rows with an inactive count in the gap.
""")
    sub("The test channel registers 52 positive checks worth 226 points and 2 negative checks,",
        "The test channel registers 67 positive checks worth 301 points and 2 negative checks,")
    sub("""  exactly the accounts it owns and that the unowned part of every corpus is unchanged.
""", """  exactly the accounts it owns and that the unowned part of every corpus is unchanged.
- Owned lever accounts: every hidden corpus also holds accounts owned by U1, D1 and D2
  (own random stream `_levers`, seed x 37 + 11), with `payments.csv` added: plan
  revisions (5 + 5 + 5) and revisions on two-row accounts (5 + 5), arrears chains
  (5 + 5 + 5) and arrears chains with carried allowance and a standing change (5 + 5),
  cumulative reads (5 + 5 + 5), cumulative reads across billing rows (5) and across a
  meter exchange (5). `_assert_levers` checks that each lever read the habitual way
  changes exactly its accounts and that the rest of the corpus is unchanged.
""")
    sub("Measured on real runs (test points of 226): the oracle scores 226.",
        "Measured on real runs (test points of 301): the oracle scores 301; revisions ignored, "
        "the first revision taken, payments ignored by the credit, or counts billed as written "
        "each 276; the first fitting revision 286; a missing payment row read as 0.00 232; all "
        "eight rules of rows 16 to 23 read the habitual way 157. Before the round-2 levers "
        "(test points of 226):")
    sub("""- Dropping allowance no line can take instead of carrying it to the next invoice.
""", """- Dropping allowance no line can take instead of carrying it to the next invoice.
- Ignoring `revisions` and `payments.csv`, or taking the first revision that fits.
- Crediting an invoice whose account's previous invoice was paid below its total, or
  treating an invoice with no payment row as paid 0.00.
- Billing a cumulative count as written, or chaining counts in file order or per row.
""")
    sub("  The test channel carries 52 positive checks worth 226 weight and 2 negative",
        "  The test channel carries 67 positive checks worth 301 weight and 2 negative")
if len(sys.argv) > 1:
    trial, date = sys.argv[1], sys.argv[2]
    s = re.sub(r"golden_score_trial_id: \S+", "golden_score_trial_id: " + trial, s)
    s = re.sub(r"three runs on \S+ \(test-hardening round\n  \w+\)", f"three runs on {date} (test-hardening round\n  15b380e)", s)
sh = hashlib.sha256((B / "solution/solve.sh").read_bytes()).hexdigest()
py = hashlib.sha256((B / "solution/solve.py").read_bytes()).hexdigest()
s = re.sub(r"fix_patch_sha256: [0-9a-f]{64}", "fix_patch_sha256: " + sh, s)
s = re.sub(r"solve_py_sha256: [0-9a-f]{64}", "solve_py_sha256: " + py, s)
p.write_text(s)
print("ok", py[:12])
