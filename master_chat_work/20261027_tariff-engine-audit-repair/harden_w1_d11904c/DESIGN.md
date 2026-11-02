# DESIGN d11904c: wave 1, lever P-1 (rebuild the r3 statements optimum)

Bundle `master_chat_work/bundles/tariff-engine-audit-repair/`, QC kit HEAD 5574d77e. Phase 1 only; no BUNDLE edit yet.

## Phase A

Probe staged task (26 Oct 17:56) differs from BUNDLE in tests/reward.toml, tests/test_output.py, environment/ci/api_contract.md and BUNDLE-only environment/ci/vouchers.csv: the probe predates rounds 2 and 3 (no statements); tests/judge.toml identical.

## Diagnosis

| run | minutes | first full write | tests | where the hard part came right |
|---|---|---|---|---|
| probe run_1 (opus-5, 44 steps) | 13.3 | step 33, 8.5 min | 157/157 (100%), old bundle | first write; judge 6/33 |
| blind r3 (36f4266) | 7 | first write | 397/397 | `_redeem` big-int shift bitset over cents (report.py:229) |

The r3 core fell because every hidden balance fits a cents bitset (4M-12M cents, 45-70 vouchers): width is small, so one table over the one sum is exact and fast. The r3 reference is itself that bitset.

## Lever: scale-split vouchers at ledger scale (design D3)

Objective and constraints, as the docs already state them (api_contract.md:219-224, unchanged): `redeemed` is the id list of the account's vouchers whose amounts add to the largest sum not above `balance`, each voucher whole or not at all; ties go to the id list that comes first comparing ids one by one; `due` is `balance` less that sum; `balance` is invoice totals less paid, `0.00` below zero. Run limit, also stated: `--statements` exits within 10 seconds (api_contract.md:25-28). No size, count, width or amount bound is stated, and none will be: `quantity` is "a JSON integer, 0 or more" (:83) and voucher `amount` is any 2dp decimal above 0.00 (:129-132).

No new contract sentence is planned. The lever is data only: new hidden statement corpora at ledger scale.

### Hidden instances

7 new hidden statement corpora, one per existing `_STATEMENT_LEVER` family (fresh D2, rescaled D1, relocated Q1, rotated Q2, api Q5, recoded Q4, renamed U1), own RNG, separate from the r3 corpora. Each corpus:

- 3 big accounts: cloned accounts whose read quantities are scaled so `balance` lands at 3e10-1e11 cents (300M-1B dollars); 55-66 vouchers each:
  - 46-55 "large" vouchers of amount u*g cents, g drawn in [50 000, 100 000), u in [1 000, 60 000), 3 planted repeats of u (id ties inside the large group);
  - 9-11 "small" vouchers with amounts in [g//(3ns), g//(ns+1)), their total below g, gcd(g, smalls) = 1, two equal small amounts (planted id tie);
  - g picked after the balance is known so that balance mod g lies in [small total / 3, g) (both groups matter) and balance // g is 30-70% of the large unit total.
- 3 small accounts with planted equal-sum id ties, 1 overpaid account (balance 0.00, `redeemed` []).
- Shipped data stays as is (198 vouchers, 60 statements of 1-6 vouchers): a plain program is exact and fast on it.

Sizes vs the 10 s limit: a cents table needs 3e10-1e11 bits (3.6-12.5 GB per account, 4 GB box); the voucher count (55-66) puts 2^(n/2) halves at 1e8-1e10; the count vectors of the large group are not small (u values distinct apart from 3 repeats).

### Reference (exact for every input, relies on structure the data shows)

Sort amounts ascending, take suffix gcds. For each k from 0 (up to 20) where the k smallest amounts add to less than the gcd `unit` of the rest (always true for k = n), cost = balance // unit + 2^k; pick the cheapest k. Large part: big-int bitset over units capped at balance // unit, suffix bitsets in id order, top reachable L*, first id list by id-order rebuild. Small part: all 2^k subsets with sum <= balance - L*·unit, max sum, first id list. Answer: sorted union.

Why exact: a large total below L* loses at least `unit`, more than all small vouchers together, so every optimum uses L*; with positive amounts no optimum set is a proper subset of another, so the id order between two optimal sets is set by the smallest id in their difference, which is unchanged by adding a disjoint part; hence first(large) ∪ first(small) is first overall. Checked against naive combinations on 3000 random small structured instances: 0 differences. On data with no such split (k = n) it is plain exhaustive search over a small set, and on the shipped data (unit gcd of all, k = 0) it is the old bitset, so it stays general.

Measured: 0.08-0.12 s per corpus in Docker (python:3.12-slim, 2 cpus, 4 GB), limit 10 s, so under 1/4 of the limit (2.5 s) by 20x.

### Wrong document a plausible program writes

- Cents bitset (the r3 blind program and any copy): no output inside 10 s or killed for memory, so the whole corpus run is no output: 0 of 13.
- Table, Pareto list, halves, branch-and-bound (fractional bound equals min(balance, taken + remaining) here, and the balance itself is never reachable, so no early stop): no output inside 10 s: 0 of 13.
- Fallback to largest-first greedy when the table is too wide: a feasible but non-optimal set, so `due` and `redeemed` wrong: 3 of 13.

## Kill test (measured, WORK/KILL_TEST.md)

Docker python:3.12-slim, --cpus 2 --memory 4g, 10 s per run, 7 prototype corpora (WORK/proto/corpus_1..7.json; big balances 2.87e10-9.87e10 cents, 55-66 vouchers). Points per corpus as planned: feasible 3, due 5, redeemed 5.

| solver | max seconds | exact corpora | points kept of 91 | lost |
|---|---|---|---|---|
| reference | 0.12 | 7/7 | 91 | 0% |
| blind r3 `_redeem` (suffix bitsets) | 10 (4 timeout, 3 OOM) | 0/7 | 0 | 100% |
| big-int shift bitset over cents, gcd reduced, with rebuild | 10 (3 timeout, 4 OOM) | 0/7 | 0 | 100% |
| big-int bitset, optimum sum only | 10 timeout | 0/7 | 0 | 100% |
| dict subset-sum table | 10 timeout | 0/7 | 0 | 100% |
| Pareto list (dominance and bound pruned) | 10 timeout | 0/7 | 0 | 100% |
| meet in the middle, sorted halves | 10 timeout | 0/7 | 0 | 100% |
| meet in the middle, halves deduped by sum (id split) | 10 timeout | 0/7 | 0 | 100% |
| meet in the middle, halves deduped (amount sorted split) | 10 timeout | 0/7 | 0 | 100% |
| branch and bound, fractional bound, largest first | 10 timeout | 0/7 | 0 | 100% |
| largest-first greedy | 0.08 | 0/7 | 21 | 76.9% |
| naive combinations | 10 timeout | 0/7 | 0 | 100% |

Every generic solver loses at least 76.9% of the lever's points (rule: at least 15%). Design 1 (face-value groups) was dropped on paper before measuring: halves deduped after sorting by amount equal its reference.

## Points and shares (plan)

- r3 tests: 91 checks, 89 positive = 397 points, 2 negatives (-5, -3); the 22 r3 statement checks and the r3 `_redeem` stay byte-unchanged.
- New: 7 corpora x (`<c>_ledger_statements_feasible` 3 + `<c>_ledger_statement_due_exact` 5 + `<c>_ledger_statement_redeemed_exact` 5) = 21 checks, 91 points. Total positive 488; the lever alone costs 91/488 = 18.6% (target 10-30%). Weights only from {1, 3, 5} (precheck W2).
- Feasibility checked apart from optimality (feasible check: account order, balance exact, ids owned and distinct, spent <= balance, due consistent); due and redeemed whole-document exact per corpus (G1, G1a owned rows). G5 sentence already at instruction.md:13.
- Each new corpus carries one quiet family in its balance, so a program wrong on one quiet rule also loses that corpus (P-2 interaction kept, S2 tie and S3 balance link kept). All-but-one (U1 wrong alone) estimate about 0.906, to be measured; G3 shares recomputed by call graph in the build.

## Build risks to settle in Phase 2

- Balances come from the ledger: scaled clone reads must give 3e10-1e11 cents with no contract rule capping a read or a total (check every rule on quantity, rate and rounding); generator asserts the bounds over 300 seeds (G12) and plants every branch (tie in large group, tie in small group, overpaid, both groups used).
- Runtime of the whole hidden statement step: 7 extra runs at most 10 s each, inside the 2700 s verifier limit; reference timed per corpus in Docker and the task time limit kept at least 3x the oracle.
- No hole: no new stated bound, no method words, no note about scale.
