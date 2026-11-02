# BRANCH_FIRE (W5), test-hardening round 78d433c

Counts are accounts whose invoices or exception rows change when the rule alone is read the habitual way
(`_Ledger(texts, off={rule})` against the full reference, /tmp/bf/bf.py on the bundle's tests/test_output.py,
26 Oct 2026). Shipped = the ten files of environment/ci as embedded in the test file. Shipped files carry no
`estimated` key (0 occurrences), no `standing_changes` key (0), no account with a second billing row (0 of 2000)
and no account/meter pair with a second accounts.csv row (0 of 3393).

| rule | branch | fires on shipped (count) | fires on hidden (accounts per corpus; seeds) |
|---|---|---|---|
| Q1 estimated reads | `estimated` true read set aside for an accepted actual read of the same meter and day (`replaced_estimate`); duplicate key includes `estimated` | 0 | 5 in each of fresh (H1), rescaled (H1+1), relocated (H3), rotated (H3+1), api (H5), recoded (H7), renamed (H7+1) |
| Q2 standing changes | standing charge of a day from the `standing_changes` entry with the latest `from` on or before it | 0 | 5 in each of the 7 |
| Q3 several billing rows | one invoice per row, sorted by account then start; reads belong to the row holding their day; outside_period = in no row | 0 | 8 in each of the 7 |
| Q4 allowance carried | allowance no energy line can take moves to the account's next invoice by start | 0 | 3 in each of the 7 |
| Q5 several accounts rows | meter active on the days of any of its rows for the account | 0 | 4 in each of the 7 |

Planting: `_quiet(texts, seed)` in tests/test_output.py, RNG `random.Random(seed * 31 + 7 + 1000003 * attempt)`,
seeds per corpus in `_QUIET_SEEDS`; 17 planted accounts per corpus: Q1 x3, Q2 x3, Q3 x2, Q3+Q4 x2, Q5 x2 and
the rare pairs Q1+Q3, Q2+Q3, Q3+Q5, Q1+Q5, Q2+Q3+Q4 once each (T4). `_assert_quiet` asserts per corpus that
each rule changes exactly the accounts labelled with it, at least two single-rule accounts per rule, every pair
account changes under both its rules, and the unplanted part of the document equals the base document.
Crash sweep: 300 seeds over the 7 base corpora, see LOG.md.

## Round 2 (15b380e): accounts whose document changes when the rule is switched off (`t2_scripts/bf2.py`)
| rule | branch | fires on shipped (count) | fires on hidden (accounts per corpus; all 7 corpora) |
|---|---|---|---|
| U1 | revisions ignored | 0 | 5 |
| U1 | first fitting revision | 0 | 3 |
| U1 | no fit -> first revision | 0 | 2 |
| D1 | arrears ignored | 0 | 4 |
| D1 | no payment row read as 0 | 0 | 10-16 |
| D2 | count billed as is | 0 | 6 |
| D2 | chain per billing row | 0 | 2 |
| D2 | chain in file order | 0 | 5-6 |
| D2 | rejected reads in chain | 0 | 2 |
Shipped keys: `cumulative` 0 reads, `revisions` 0 plans, `payments.csv` absent. Planting `_levers` on own RNG `Random(seed*37+11+1000003*attempt)`; `_assert_levers` proves non-lever accounts equal the round-1 document and each lever moves exactly its owners; 300-seed sweep 300 ok, 0 fail.

## Round 3 (fc1fb76): statement branches per corpus (`t3_scripts/bf3.py`)
| branch | shipped | fresh | rescaled | relocated | rotated | api | recoded | renamed |
|---|---|---|---|---|---|---|---|---|
| statements | 60 | 11 | 11 | 11 | 11 | 11 | 11 | 11 |
| big (balance > 1,000,000 cents; enumeration and cent DP exceed 10 s) | 0 | 3 | 3 | 3 | 3 | 3 | 3 | 3 |
| greedy (largest first) differs from the optimum | 15 | 11 | 11 | 10 | 11 | 11 | 10 | 9 |
| tie (>= 2 optimal sets, countable accounts only) | 1 | 2 | 4 | 2 | 4 | 2 | 2 | 2 |
| string order != numeric order of ids | 34 | 11 | 11 | 11 | 11 | 11 | 11 | 11 |
| no voucher fits -> [] | 9 | 0 | 0 | 0 | 0 | 0 | 0 | 2 |
| balance below zero -> 0.00 (verdict sentence) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| paid amount present (D1/U1 sources) | 0 | 0 | 3 | 0 | 0 | 0 | 0 | 3 |
The optimum itself fires on shipped data on purpose (main lever is computational, not quiet): shipped instances
are small, hidden ones are large of the same form. Lever-family sources per corpus: see LEVERS.md round 3.

## Wave 1 (d11904c) ledger statement corpora (t4_scripts/branch_fire.py)
Per corpus: 7 statements; 3 big accounts (balance 4.0e10-8.0e10 cents, 55-66 vouchers, unit group + small group,
asserted per corpus: >= 1 tie inside a unit group, >= 1 tie inside a small group, both groups used); 1 overpaid
account at 0.00 (renamed: 3 at 0.00, two of its tie accounts are paid up); ties among the 3 small accounts:
fresh 2, rescaled 0, relocated 1, rotated 2, api 0, recoded 0, renamed 0; largest-first differs from the answer on
6 of 7 statements (renamed 4 of 7). Shipped: 61 statements (A1643 added: unit group tie, balance 311.48).

## Harden round _ql1 (ed621c7): scale statement sets statement / batch / cycle
| rule | branch | fires on shipped (count) | fires on hidden (seeds) |
|---|---|---|---|
| :221-225 largest sum, balance above 1e10 cents | exact search where a cent table does not fit | 0 (largest shipped balance below 1e7 cents) | every corpus of every set: 3 accounts at 4e10-8e10 cents (7 x 4 sets) |
| :221-225 on 36 unrelated vouchers, gcd 1 | no shared unit, no small group | 0 | one account per corpus in statement, batch, cycle (21) |
| :223-225 tie, first id list | equal-amount pair, one used | shipped 1 tie (A1643) | each odd account (asserted) + ledger accounts' unit/small ties |
| :219-220 balance below zero -> 0.00 | overpaid account | shipped 0 | one per corpus per set (28) |
