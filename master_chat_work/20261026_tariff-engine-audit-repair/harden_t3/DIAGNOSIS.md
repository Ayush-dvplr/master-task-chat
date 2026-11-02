# DIAGNOSIS fc1fb76: tariff-engine-audit-repair, test-hardening round 3

## Phase A
`diff -rq` of BUNDLE `environment/` and `instruction.md` against the round-2 blind copy
(`/tmp/blind/tariff-engine-audit-repair-20261027T031055-c34a/environment`): identical (rc 0).
The blind program was copied to `WORK/blind_r2/app`. It scored 301/301 in Docker (round-2 report).

## What the blind reads got right, and why it was easy
The blind reads have no trajectory. The second column gives the program location instead
(`WORK/blind_r2/app/repo/src/tariff/...`).

| Rule | Where the r2 program has it | What made it easy |
|---|---|---|
| Q1 cumulative / malformed read forms | parser.py:44, 117-135 | one paragraph in meter_reads; its docstring copies the contract sentence |
| Q2 standing_changes per day | core.py:73-91 | the rule sits next to its use (Standing line); toy worked example |
| Q3 several rows per account, carry | report.py:102-115 | the Amounts paragraph names the carry; toy is the only branch |
| Q4 allowance carry | report.py:115 | the same sentence as its use |
| Q5 meter active windows | parser.py:49-81, report.py:46-48 | the accounts.csv paragraph states it; the shipped data has 2-3 meters |
| U1 revision unique fit | report.py:145-170 | the Tier definition states the objective and the verdict for "none or more than one"; the search space is tiny (revisions x 1) |
| D1 no credit after underpay | report.py:119-120 | one sentence in Credit plus the X1 April/May toy |
| D2 cumulative reads | parser.py:117-135 | Billed quantity definition plus the Y9 toy |
| plan codes (padded) | report.py:28-35, 54 | `codes` named in the rate_card paragraph; a data profile shows it |

Common cause: every rule is a plain transform, local to one record, and costs O(n) to run.
Once the reader has the sentence, the code follows from it. No rule needs an algorithm that is
easy to state but hard to run fast, so no correct reading fails on larger hidden data.

## Arithmetic
- Now: 69 checks, 67 positive = 301 points. The 15 round-2 lever checks (75 points) are the only
  checks with behaviour that appears in hidden data only. Every round-1 Q rule now has shipped
  or toy-equivalent firing, so a careful reader always gets it.
- To bring a careful solver to 70-90 we need 30-130 lost points of about 400. Each stated
  transform rule has been coded right on the first read, so these points have to come from a
  figure that a plausible reading gets exactly right on small data and wrong, or too slowly,
  on hidden data.

## Planned levers
L1 (computational core, main): an optional `vouchers.csv` (`account,voucher,amount`) and a new
CLI form `python -m tariff --statements <data_dir>`. The command writes one statement per
voucher account: `balance` (invoice totals less paid, floored at 0.00), `redeemed` (the
account's vouchers whose sum is the largest not above the balance; on ties, the id list that
comes first comparing ids one by one as plain strings) and `due`. The contract gives the
objective, the tie order, the no-fit verdict and a 10-second limit per run. It names no method
and states no size.
- Careful-reader readings it targets: (a) largest-first greedy; (b) an exact search over all
  subsets, which is instant on the shipped 1-6 vouchers; (c) a sum-indexed dictionary or array
  DP over cents. All three are exact or near-exact on the shipped data.
- Wrong document each yields on hidden data: (a) feasible but not optimal; (b) and (c) give no
  output in time. Each hidden corpus has 3 large accounts (balances 50,000-90,000.00, so 5M-9M
  cents, 45-70 vouchers, the balance itself unreachable) beside 9 small ones.
- Why the r1 and r2 blind programs miss it: neither has a statements command, so all 22
  statement checks fail with no crash in the invoice checks.
L2 (long replay, secondary): `balance` uses the round-1/2 state, i.e. Q3 multi-row invoices,
D1 credit loss, D2 cumulative quantities and payments.csv. The hidden voucher accounts include
owned Q3/D1/D2 accounts, so an error in that state moves the target and with it the optimum.
Feasibility (ids belong to the account, distinct, sum <= balance, due = balance - sum) is
graded apart from the two optimality checks (redeemed exact, due exact). Each hidden corpus is
graded whole-document for the statement family.

Planned points: 7 corpora x (feasible 3 + due 5 + redeemed 5) + shipped statements exact 5 = 96,
for a total of 397. Expected losses: no statements 24%, greedy about 18%, naive or slow exact
about 23%, tie order wrong about 9%. AUTO mode (master notes): proceeding without waiting for "go".
