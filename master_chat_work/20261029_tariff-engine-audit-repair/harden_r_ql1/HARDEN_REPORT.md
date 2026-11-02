# HARDEN_REPORT ed621c7 tariff-engine-audit-repair, round _ql1

Status: BUILD DONE (29 Oct 2026, 12:30 IST). Phase A GENUINE, primary cause 4 (levers weak by design). Full diagnosis: DIAGNOSIS.md. The 04:52 PAUSED report is kept as HARDEN_REPORT_paused_0452.md. Ayush cleared it at 09:12 ("C. Raise the limit for tariff only.: okay"), which sets the CRASH+TIMEOUT cap at 60% of positive test weight for this bundle only.

## What changed (start bytes = QL bundle + `_visible_test_removed` add-on)
- F1: the 7 r3 statement corpora moved to hidden scale. Each document has 2 two-group (ledger shape) accounts and 1 account with 36 unrelated large vouchers (gcd 1, 3 equal-amount pairs, a tie at the best sum); balances 4e10-8e10 cents.
- F2: two more 7-corpus sets, `batch` and `cycle` (42 checks: feasible w3, due w5, redeemed w5), each corpus in its own 10 s call.
- Reference `_redeem_any` in tests and solve.py: bit set for small targets, two-group split, otherwise halves search with first-id tie order. 3000 brute cases, 0 mismatches. Ledger documents are byte-identical to before.
- Judge: R14 (large own input, run time vs 10 s), R15 (outside recompute of redeemed), R16 (tie witness), w3 each. The oracle self-check prints R14-R16.
- No new rule text. instruction.md, docs and environment are unchanged. The statement rule stays in the shipped docs: largest sum at or below the balance, first id list in plain string order, 10 s per call.
- reward.toml: test 0.5/670, judge 0.5/42.

## Before / after
| | before (QL bytes) | after |
|---|---|---|
| test checks (positive / negative) | 114 / 2 | 156 / 2 |
| positive test points | 488 | 670 |
| judge criteria / positive | 13 / 33 | 16 / 42 |
| lever share (hidden-scale statements) | 91/488 = 18.6% | 364/670 = 54.3% |
| held-out w5 | 53% | 535/670 = 79.9% |
| shipped-only | - | 33/670 = 4.9% |
| hidden reseeded (whole document per corpus) | - | 637/670 = 95.1% |
| QL-run agent package tests | 81.35 | 45.67 (measured) |

## Kill table (Docker 4g / 2 cpu; WORK/KILL_TEST.md)
| program | tests | WRONG | TIMEOUT | CRASH |
|---|---|---|---|---|
| oracle / combined | 100.00 | 0 | 0 | 0 |
| QL-run agent package | 45.67 | 0 | 0 | 364 |
| bitset | 45.67 | 0 | 0 | 364 |
| gcd_split | 59.25 | 0 | 0 | 273 |
| mitm_only | 45.67 | 0 | 351 | 13 |
| tie_naive | 78.36 | 145 | 0 | 0 |
| greedy | 57.46 | 285 | 0 | 0 |
| mitm_dedupe / branch_bound | 45.67 | 0 | 364 | 0 |
| first_write | 28.06 | 482 | 0 | 0 |
| blind_r3 | 45.67 | 0 | 0 | 364 |

All CRASH/TIMEOUT loss is on lever checks and stays at or below 364/670 = 54.3%, under the 60% cap. Every generic solver loses at least 15% of lever points; tie_naive loses 39.8% by WRONG output.

## Cost table
Reference worst is 0.28 s per corpus call (bar 2.5 s). Oracle verifier 46 s. Worst measured verifier 325 s (mitm_only), analytic about 340 s, against a 2430 s bar. Shipped statements stay below 1e7 cents.

## Gates (DESIGN READY a-e in WORK/DESIGN.md)
- (a) predicted final = (45.67 + 21.4)/2 = 33.5 <= 35. With the judge upper estimate 28.6 it is 37.1.
- (b) lever share is 54.3% (>= 40%), held-out w5 is 79.9% (>= 50%).
- (c) blind programs score at most 45.67.
- (d) worst verifier time is 325 s, against a 2430 s bar.
- (e) the kill table holds (see above).
- Docker (/tmp/opencode-logs/tariff-ql1-gates-20261029T121241-4488, ALL_DONE 12:26:05): oracle 1.0 / 1.0 / 1.0 (plain__LyU6mrM, plain__eGPj9x5, plain__754mTLf), owner-only 1.0, nop 0.0, stub 0.0, forgery 0.0463. No exceptions.
- STACKING_CHECK PASS (OUT/STACKING_CHECK.md). The tool's G3 hidden share of 21.8% is a name misread; the call graph gives 95.1%.
- QC: structure 17/0/0, instruction 5/0/0, tests 35 pass 1 warn (A3, 158 checks) 0 fail, judge 19/0/0, validator 40/0/0. Kit HEAD 5574d77e; `git diff 5574d77e HEAD` is empty, so there are no changed checks to list. xref 0 findings.
- PRECHECK last line: `PRECHECK CLEAN`.
- TRUTH sha lines written by WORK/ql1/truth_sha.py (solve.py 487e942c..., solve.sh 25c71b6c...).
- Tasks_INPUT synced (5 files, diff -rq empty). Tree sha 7d8861ab1d7a (master's find|shasum command; same on both copies).

## Deviations and not run
- The 09:15 go said "no change to judge" and also ordered the 3 probes. Only R14-R16 were added; no other judge text changed.
- Oracle x3 as Ayush asked (the kit asks x5).
- Not run: the 3 fresh blind reads (master's P13) and the harness run. The judge estimate (9/42 mid) is a prediction, not a measurement.
- The session rename list did not show ed621c7.

## Lessons for the master
- An exact first-write program loses only by CRASH/TIMEOUT at hidden scale. A WRONG-only bar cannot be met without new rule text, so set the cap per bundle up front.
- In tariff, hidden scale bites only on the statement solver. The invoice families are linear and gave no fair scale lever.
- The tie order is the only WRONG-output lever against a correct fast solver (tie_naive, 145 points).
- Foreign containers held the kill chain for about 1h45; the memory rule (docker ps = 0) dominated wall time.
