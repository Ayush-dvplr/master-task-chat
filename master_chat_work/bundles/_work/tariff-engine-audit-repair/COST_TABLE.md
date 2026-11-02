# COST_TABLE (G10), harden round 2 Phase 2 (7f1d771), measured

Method: each wrong reading is patched alone into a copy of `solution/solve.py` (WORK/measure_variants.py),
the patched oracle runs on a fresh copy of `environment/ci` and `environment/repo`, then the current
`tests/test_output.py` runs on its `/app/out` (WORK/run_checks.py, rewardkit stub). Test points are out of
157 positive points. Overall = 0.5 x tests + 0.5 x rubric, given twice: rubric 90 (G10 default) and the
rubric measured on probe 2 (3.33, judge_response of job tariff-engine-audit-repair). Raw results:
OUT/g10b/g10.json, OUT/g10b/g10_onefact.json, OUT/g10c/g10.json. Measured 2026-10-25 15:00-15:16 IST,
each run alone.

| lever | wrong reading injected | tests score | points lost | lever alone loss | all but one right, overall (rubric 90) | overall (rubric 3.33 measured) | gate |
|---|---|---|---|---|---|---|---|
| L11 plan codes (new) | unknown plan value falls to the first plan (`L11_first_plan`) | 0.7452 | 40 | 25.5% | 82.3 | 38.9 | share PASS (25-45%); overall FAIL at 90, PASS measured |
| L11 | unknown plan value falls to the last plan (`L11_last_plan`) | 0.7452 | 40 | 25.5% | 82.3 | 38.9 | as above |
| L11 | key lookup only (`L11_key_only`) | ERROR | n/a | loud KeyError on shipped data | n/a | n/a | crash, visible to the author |
| L11 | codes compared untrimmed (`L11_codes_raw`) | ERROR | n/a | loud: plan `T2319` names no entry | n/a | n/a | crash, visible to the author |
| N1 allowance re-share | allowance ignored (`N1_no_share`) | 0.5669 | 68 | 43.3% | 73.3 | 30.0 | share PASS |
| N1 | allowance shared once (`N1_one_pass`) | 0.6178 | 60 | 38.2% | 75.9 | 32.6 | share PASS |
| N1 | allowance shared twice (`N1_two_passes`) | 0.6178 | 60 | 38.2% | 75.9 | 32.6 | share PASS |
| N2 calendar month | standing / days of the start month (`N2_start_month`) | 0.7134 | 45 | 28.7% | 80.7 | 37.3 | share PASS |
| N2 | standing / billing-period length (`N2_period_length`) | 0.6306 | 58 | 36.9% | 76.5 | 33.2 | share PASS |
| N3 account tier position | tiers restart per meter (`N3_per_meter`) | 0.7134 | 45 | 28.7% | 80.7 | 37.3 | share PASS |
| gate LV-TR-4 | quoted integers coerced (`V_qty_coerce`) | 0.2611 | 116 | 73.9% | 58.1 | 14.7 | gate |
| cheat | shipped answers hard-coded (`C_hardcode_shipped`) | 0.7134 before the -5 negative | 45 | 28.7% | 80.7 | 37.3 | negative fires |
| one fact | one energy line +0.01, recoded account (`one_fact:P0389`) | 0.8089 | 30 | 19.1% | 85.4 | 42.1 | n/a |
| one fact | one energy line +0.01, shipped code-named account (`one_fact:A0001`) | 0.9682 | 5 | 3.2% | 93.4 | 50.1 | n/a |
| one fact | one energy line +0.01, fresh account (`one_fact:V0167`) | 0.8089 | 30 | 19.1% | 85.4 | 42.1 | n/a |
| one fact | one energy line +0.01, relocated account (`one_fact:L0214`) | 0.8089 | 30 | 19.1% | 85.4 | 42.1 | n/a |
| one fact | one energy line +0.01, api account (`one_fact:N0054`) | 0.9045 | 15 | 9.6% | 90.2 | 46.9 | n/a |

Not re-measured this round (round-1 values on 127 points stand as history): `V_month_30`, `V_half_up`,
`V_float_round`, `V_credit_rounded`, `V_keep_asserts`, `one_fact_standing`, `one_fact_qty`.

Planting (which hidden corpus family carries which lever): fresh + rescaled (H1 seed) N1 + N2;
relocated + rotated (H3 seed) N1 + N3; api (H5 seed) N2 + N3; recoded + renamed (H7 seed) L11 only;
shipped `environment/ci` carries L11 (503 of 2000 billing rows name their plan by a code) and none of N1-N3.
Lever alone: L11 40 points (25.5%), N1 60-68 (38.2-43.3%), N2 45-58 (28.7-36.9%), N3 45 (28.7%).
Union of the four counted levers: 133 of 157 points (every figure check of every hidden family, the two
shipped invoice checks, and `regression_rows`, which N1 and N2 readings also fail).

G10 "all but one right overall < 70": with the rubric assumed 90 it fails for every lever alone (73-82),
because each lever alone is 25-43% of the tests half. With the rubric measured on probe 2 (3.33) every row
is far under 70. Both are reported; the master's 3 blind reads and the next probe decide.

CL-4 one-fact-wrong: one cent on one line of one recoded account costs 30 points (19.1%), on one shipped
code-named account 5 points (3.2%), on an api account 15 (9.6%). That is the cost of one wrong fact.

## Lessons for the master
L11 owned families (recoded + renamed, 30 points) plus 2 shipped checks land at 25.5%, the floor of the 25-45% band; a third owned check family would be needed to move it up | no change: master note 2 band met

# Test-hardening round (78d433c), measured 26 Oct 2026 21:30-21:45 IST

Same method (WORK/measure_variants.py patches `solution/solve.py`, WORK/run_checks.py runs the current
`tests/test_output.py`); test points out of 226 positive points (157 earlier + 69 for the six owned-row
criteria). Raw: harden_t1/cost_q.json (Q rows), harden_t1/cost_old.json (earlier levers re-measured).

| lever | wrong reading injected | tests score | points lost | alone loss | checks failed |
|---|---|---|---|---|---|
| oracle | none | 1.0000 | 0 | 0 | none |
| Q1 estimated reads | `estimated` ignored (`Q1_off`) | 0.9071 | 21 | 9.3% | estimated_read, combined_row |
| Q2 standing changes | `standing_changes` ignored (`Q2_off`) | 0.9071 | 21 | 9.3% | standing_change, combined_row |
| Q3 several billing rows | last billing row per account (`Q3_off`) | 0.8938 | 24 | 10.6% | billing_row, carried_allowance, combined_row |
| Q4 allowance carried (Q3 right) | leftover dropped (`Q4_off`) | 0.9381 | 14 | 6.2% | carried_allowance, combined_row |
| Q5 several accounts rows | last accounts row per meter (`Q5_off`) | 0.9071 | 21 | 9.3% | meter_row, combined_row |
| first write (all five habitual) | `Q_all_off` | 0.6947 | 69 | 30.5% | the six owned-row criteria |
| all but one right (best case) | only Q4 wrong | 0.9381 | 14 | 6.2% | as Q4 |
| N1 | `N1_no_share` / `N1_one_pass` / `N1_two_passes` | 0.6372 / 0.7345 / 0.7345 | 82 / 60 / 60 | | |
| N2 | `N2_start_month` / `N2_period_length` / `V_month_30` | 0.8009 / 0.6504 / 0.1593 | 45 / 79 / 190 | | |
| N3 | `N3_per_meter` | 0.8009 | 45 | 19.9% | |
| L11 | `L11_first_plan` / `L11_last_plan` | 0.8230 / 0.8230 | 40 / 40 | 17.7% | |
| L11 | `L11_key_only` / `L11_codes_raw` | crash on shipped data (unchanged from round 2) | | | |
| gates | `V_qty_coerce` / `V_half_up` / `V_float_round` / `V_credit_rounded` / `V_keep_asserts` | 0.4867 / 0.5354 / 0.5354 / 0.8451 / 0.9735 | | | |
| cheat | `C_hardcode_shipped` | 0.8009 before the -5 negative (negative fires) | | | |

Targets (master GO note 5): each Q alone 5-12% PASS (6.2-10.6%); first write <= 75 PASS (69.5); all-but-one
<= 95 PASS (93.8). Q4 is measured with Q3 right; with Q3 wrong the Q4 accounts are already lost to Q3.

## Round 2 (15b380e, 27 Oct 2026): measured, tests share of 301 positive points (measure_variants.py; cost2a/2b/3 in /tmp/tariff-15b380e)
| program | tests | positive checks failed |
|---|---|---|
| oracle | 1.0000 | 0 |
| blind round-1 program (WORK/blind_r1) | 0.7508 | 15 (exactly the new lever checks; no crash) |
| U1_off | 0.9169 | 5 |
| U1_first_fit | 0.9502 | 3 |
| U1_first_revision | 0.9169 | 5 |
| D1_off | 0.9169 | 5 |
| D1_missing_is_zero | 0.7708 | 15 |
| D2_off | 0.9169 | 5 |
| D2_per_row | 0.9834 | 1 |
| D2_file_order | 0.9169 | 5 |
| Q1_off | 0.8804 | 8 |
| Q2_off | 0.8970 | 7 |
| Q3_off | 0.7375 | 17 |
| Q4_off | 0.8372 | 11 |
| Q5_off | 0.9136 | 6 |
| first_write | 0.5216 | 30 |
| L2_all_off | 0.7508 | 15 |

Readings: `*_off` = rule ignored; U1_first_fit = first fitting revision; U1_first_revision = revisions[0] always; D1_missing_is_zero = no payment row read as paid 0.00; D2_per_row = chain restarts per billing row; D2_file_order = previous read by file order; first_write = Q1-Q5, U1, D1, D2 all ignored; L2_all_off = U1, D1, D2 ignored (equals blind_r1).
Gates: each new lever alone 8.3% (5-12 PASS); best single-rule-wrong program 0.9169 (<= 92 PASS; partial habit D2_per_row 0.9834 shown); blind_r1 75.1 (70-90 PASS); first write 52.2.
Cascade: Q3 alone now 26.3% (U1 rows, D1, D2 rows, Q3+Q4 and pairs need several billing rows); Q4 16.3% (D1+Q2+Q3+Q4 combo and U1 rows carry); Q1 12.0% (D2 replaced estimated count); Q2 10.3%; Q5 8.6%.
`all_but_X` rows in cost2b mean only X right (all other seven wrong): 0.52-0.57, kept in cost2b.json.

## Round 3 (fc1fb76, 27 Oct 2026): measured, tests share of 397 positive points (measure_variants.py; t3_results/cost_final.json)
| program | tests | positive checks failed |
|---|---|---|
| oracle | 1.0000 | 0 |
| blind round-2 program (WORK/blind_r2, 301/301 last round) | 0.7582 | 22 (exactly the statement checks; no crash) |
| blind round-1 program (WORK/blind_r1) | 0.5693 | 37 (15 round-2 lever checks + 22 statement checks) |
| S_greedy (largest voucher first) | 0.8111 | 15 |
| S_setdp (dict of sums -> first id tuple, exact) | 0.7708 | 21 (no output in 10 s on all 7 hidden corpora) |
| S_naive (every subset, exact) | 0.7708 | 21 (timeouts) |
| S_tie_any (another optimal set) | 0.8992 | 8 |
| S_numeric_ids (ids in numeric order) | 0.8992 | 8 |
| S_no_paid (balance ignores payments) | 0.7708 | 21 |
| S_no_clamp (negative balance kept) | 0.8589 | 14 |
| S_off (empty statement list) | 0.7582 | 22 |
| Q1_off / Q2_off / Q3_off / Q4_off / Q5_off | 0.8438 / 0.8564 / 0.7154 / 0.7909 / 0.9018 | 14 / 13 / 25 / 19 / 9 |
| U1_off / D1_off / D2_off | 0.9169 / 0.9043 / 0.9043 | 7 / 8 / 8 |
| first write (eight quiet/lever rules wrong, exact statements) | 0.4207 | 50 |
| first write + exact slow DP / + greedy | 0.4081 / 0.3955 | 51 / 52 |
| all but one right (best single-rule-wrong) | 0.9169 (U1_off) | 7 |
No variant fired a negative.
Docker timing (python:3.12-slim, 2 cpus, 4 GB; t3_scripts/dock_time.py, 30 s cap): reference 0.22-0.27 s per hidden
corpus, 0.62 s shipped (max 0.27 s = 1/37 of the 10 s limit); greedy 0.13 s, 1-3 of 12 statements right; set DP,
bytearray DP over cents and plain enumeration exact on shipped (0.6 s) and > 30 s on every hidden corpus.
Gates: blind r2 loses 24.2% (10-30 PASS); greedy loses 18.9%, naive / slow exact 22.9% (>= 15 PASS); all-but-one
91.7 (<= 92 PASS); no crash in the invoice checks for any statement variant.
Cascade: each quiet rule now also moves the balances of its corpus's statement accounts (`_STATEMENT_LEVER`), e.g.
Q3 26.3 -> 28.5%, Q1 12.0 -> 15.6%.

## Wave 1 (d11904c, 27 Oct 2026): measured in Docker on the built bundle, tests share of 488 positive points

python:3.12-slim, 2 cpus, 4 GB, uid 1000; whole program scored by the real checks (t4_scripts/cost_t4.py,
cost_docker.sh; t4_results/cost_docker.json). Lever = the 21 ledger checks, 91 points.

| program | tests | positive checks failed | lever points kept of 91 |
|---|---|---|---|
| oracle (split reference) | 1.0000 | 0 | 91 |
| oracle build, kill-test reference solver | 1.0000 | 0 | 91 |
| blind round-3 program (397/397 last round) | 0.8135 | 21 | 0 |
| blind round-3 program with the reference optimum (float check) | 1.0000 | 0 | 91 |
| blind r3 `_redeem` (cents bitset, suffix masks) | 0.8135 | 21 | 0 |
| gcd-reduced cents bitset with id-order rebuild | 0.8135 | 21 | 0 |
| cents bitset, optimum sum only, greedy ids | 0.6598 | 36 | 0 |
| dict table of sums -> first ids | 0.6270 | 42 | 0 |
| Pareto list, dominance pruned | 0.6270 | 42 | 0 |
| halves, sorted, raw | 0.6270 | 42 | 0 |
| halves deduped by sum, id split | 0.6270 | 42 | 0 |
| halves deduped by sum, amount split | 0.6270 | 42 | 0 |
| branch and bound, fractional bound | 0.6270 | 42 | 0 |
| largest voucher first | 0.7029 | 29 | 21 |
| naive combinations | 0.6270 | 42 | 0 |
| Q1 wrong alone | 0.8197 | 20 | 65 |
| Q2 wrong alone | 0.8299 | 19 | 65 |
| Q3 wrong alone | 0.6885 | 34 | 52 |
| Q4 wrong alone | 0.7500 | 28 | 52 |
| Q5 wrong alone | 0.8934 | 12 | 78 |
| U1 wrong alone | 0.9057 | 10 | 78 |
| D1 wrong alone | 0.8955 | 11 | 78 |
| D2 wrong alone | 0.8955 | 11 | 78 |
| first write (Q1-Q5, U1, D1, D2 wrong; exact statements) | 0.3422 | 71 | 0 |
| first write plus cents bitset | 0.3422 | 71 | 0 |
| first write plus greedy | 0.3217 | 73 | 0 |

All-but-one (best single wrong): U1_off 0.9057 (<= 0.92). Lever alone: blind r3 loses 18.6% (10-30%). Negatives fired: none.

## Harden round _ql1 (ed621c7)
| item | value |
|---|---|
| reference per corpus call | worst 0.28 s (bar 2.5 s), generator 0.17-1.72 s |
| oracle full verifier (Docker) | 46.1 s |
| worst measured verifier (mitm_only, all lever calls time out) | 325.0 s |
| analytic worst | 28 lever calls x 10 s + ~60 s rest = ~340 s, limit 2700, bar 2430 |
| judge estimate | mid 9/42 = 21.4%, upper 12/42 = 28.6% |
| predicted final at agent package | (45.67 + 21.4) / 2 = 33.5; upper (45.67 + 28.6)/2 = 37.1 |
