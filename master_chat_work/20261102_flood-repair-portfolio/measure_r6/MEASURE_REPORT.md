# MEASURE REPORT — flood-repair-portfolio r6 budget lever (board 2939ad0)

Verdict: DESIGN READY, path A+B. Tree sha 7d68065946fd at start and end. BUNDLE, Tasks_INPUT, r0_lever untouched.
Session rename ran at start: `codex: no match`, `opencode: ['ses_e63a05cb5ffeTxsiYtxSaU7SDb']`.

## What ran (all Docker, python:3.12-slim, --memory 4g --cpus 2, perl alarm cap, dockfree START=yes before each)
Scratch/logs: `/Users/mac/Desktop/Terminal Bench/_runs/20261102/flood-repair-portfolio/r6-20261102T1838/`
1. baseline.log: reference, P, P_inf on r5 books H1-H3 (all equal reference; P 11.54/8.55/7.38 s).
2. gen_books.log: `gen_r6.py books 6` -> WORK/r6_budget/books/H1-H3 (103 rounds, 6 crowd rounds k=10 each).
3. probe_h1_one.log: P_inf one crowd round (H1 R23779) 33.858 s.
4. measure_H1/H2/H3.log: reference + oracle ledger equality, P, P_x4, P_inf, blinds, kill programs, busy reference.
5. measure_SHIPPED.log: reference, oracle, P and busy reference on BUNDLE/environment/data.
6. shape300.log: 300 seeds of a reduced spec with 2 crowd rounds each: errors 0.
7. witness.log: smallest witness book plus P branch trace.
P_x4 / P_inf: WORK/r6_budget/programs/p_x4.py, p_inf.py; diffs p_x4.diff / p_inf.diff change only P:24-25.

## Kill table (hidden points out of 75; verdict and seconds per book H1 / H2 / H3)
| program | verdicts | seconds | points |
|---|---|---|---|
| P (paid a4) | WRONG / WRONG / WRONG | 13.6812 / 14.2081 / 13.6135 | 18 |
| P_x4 | WRONG / WRONG / WRONG | 52.4109 / 53.1405 / 52.6094 | 18 |
| P_inf | EXACT / EXACT / EXACT | 149.2739 / 122.6133 / 104.2548 | 75 |
| blind4_b1 | EXACT / EXACT / EXACT | 6.7954 / 7.6965 / 5.8171 | 75 |
| blind4_b2 | WRONG / WRONG / WRONG | 11.2467 / 15.5389 / 9.3946 | 18 |
| first_write | TIMEOUT x3 | 20.0156 / 20.0262 / 20.0296 | 0 |
| all_but_one | TIMEOUT x3 | 20.0197 / 20.0795 / 20.0121 | 0 |
| lever_aware (recorded only) | EXACT x3 | 1.8074 / 3.7670 / 2.0379 | 75 |
WRONG rows keep feasible + data_quality (6/25) and lose optimal, summary, policy_audit, regions, segments.
Wrong rounds: P 48/56/34, P_x4 22/52/33, b2 6/4/5. First differing round: R11123 / R18482 / R17164 (crowd rounds).

## Timing table (seconds)
| book | P | P_x4 | P_inf | reference | reference busy | oracle (verifier) |
|---|---|---|---|---|---|---|
| H1 | 13.6812 | 52.4109 | 149.2739 | 2.6915 | 1.5219 | 236.94 |
| H2 | 14.2081 | 53.1405 | 122.6133 | 2.3949 | 2.2565 | 242.07 |
| H3 | 13.6135 | 52.6094 | 104.2548 | 3.2346 | 2.4820 | 223.13 |
| shipped | 0.6519 (EXACT) | - | - | 0.5309 | 0.3743 | 0.82 |

## Points
P loses 57/108 positive points (19 x 3 hidden books); shipped and other tests kept. Predicted tests 47.22%,
judge 37.5/37.5/53.125 unchanged, final low/mid 42.36, high 50.17.

## Witness
`WORK/r6_budget/witness/` (book/, book.meta.json, witness.json, outputs/): 3 rounds, crowd round R39321
(150 lattice + 10 members of shared crew C3955, 160 proposals, 460 records). Reference 0.6852 s, oracle ledger
equals reference; P 4.25 s total_benefit 63929 vs oracle 73387; 8 documents differ (all but data_quality).
Trace: capped_dp raised Timeout after 4.006 s (P:383 dp per combo, check_deadline P:468), then
greedy(160) at P:355-356. Oracle: test_output.py:1260-1277 (_capped) over :1179-1257 (_portfolio).

## Not run
- reruns_identical-style double run of P on H1 (timing-dependent output; could add 3 lost points).
- Full verifier (pytest) wall time with the r6 books; only the oracle ledger per book was timed.
- No QC lanes, no bundle edit, no Tasks_INPUT sync, no judge call.

## Lessons for the master
- r5 failed at k=11 because C(11,7)=330 > COMBO_CAP 256 sends P to fast B&B; k=10 (210 combos) is the lever.
- blind4_b1 stays EXACT: the lever kills P's branch, not careful programs; verifier oracle cost rises to ~240 s/book.
