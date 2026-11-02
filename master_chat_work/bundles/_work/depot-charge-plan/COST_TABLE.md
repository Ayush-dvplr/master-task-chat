# COST_TABLE (G10), depot-charge-plan

Method: WORK/tools/mutants.py patches one wrong reading into a copy of `solution/solve.py`; each mutant is
installed as `/app/out/derive_report.py`, run once on `/app/data` as uid 1000, then the real
`tests/test_output.py` runs through rewardkit in image dcp-verifier:1 (Docker, --memory 4g --cpus 2).
Logs: `_runs/20261101/depot-charge-plan/tests-20261101T0320/logs/mut2_0.log`, `mut2_1.log`, `mut3.log`, `mut4_*.log`.
Positive test weight 191. Judge mid estimate 44% (JUDGE_MAP.md, probes at 25%).
"one-fact-wrong score" (CL-4) = tests score with only that reading wrong.

## Shape D levers (gate: every lever alone >= 25%)

| lever | wrong reading injected alone | tests kept / 191 | lost % | all-but-this-one-right tests % | predicted final = (tests + 44)/2 | gate |
|---|---|---|---|---|---|---|
| M meter convention (rule 12) | identity meter (tariff as written) `L_meter_identity` | 25 | 86.9 | 13.1 | 28.6 | PASS |
| F shared feeder (rule 11) | feeder limit ignored `L_feeder_ignored` | 25 | 86.9 | 13.1 | 28.6 | PASS |
| F cabinets (rule 10) | cabinet limit ignored `L_cabinets_ignored` | 25 | 86.9 | 13.1 | 28.6 | PASS |
| T tie-break (rule 15) | first optimum found `L_tiebreak_first_found` | 25 | 86.9 | 13.1 | 28.6 | PASS |
| T tie-break (rule 15) | order bus then slot `L_tiebreak_reversed_order` | 25 | 86.9 | 13.1 | 28.6 | PASS |
| first write | identity meter + no tie pass `X_first_write` | 25 | 86.9 | 13.1 | 28.6 | PASS |

Every lever mutant keeps exactly: shipped 15 + present 1 + hidden data_quality 6 + missing input 3 = 25.
All "all but one" finals are below 70 (28.6).

## Plain rules (one-fact-wrong score)

| rule | mutant | tests kept / 191 | lost % |
|---|---|---|---|
| 2 span end excluded | R_span_inclusive_end | 53 | 72.3 |
| 4 retired rejected | R_retired_accepted | 90 | 52.9 |
| 4 duplicate rejected | R_duplicate_accepted | 4 | 97.9 |
| 4 bad window variants | R_bad_window_order_only | 19 | 90.1 |
| 7 extra trips counted | R_extra_trips_ignored | 13 | 93.2 |
| 7 extra trips only day after | R_extra_trips_any_date | 45 | 76.4 |
| 7 trips of day after | R_trips_plan_date | 13 | 93.2 |
| 7 reserve added | R_reserve_ignored | 13 | 93.2 |
| 7 need floor 0 | R_need_no_floor | 13 | 93.2 |
| 8 unlisted contract commercial | R_unlisted_contract_public | 128 | 33.0 |
| 8 class weights | R_class_weight_ignored | 135 | 29.3 |
| 10 outages | R_outage_ignored | 151 | 20.9 |
| 11 derates | R_derate_ignored | 25 | 86.9 |
| 12 settled energy in equal parts | R_settled_start_price | 3 | 98.4 |
| 13 published outside window rejected | R_published_outside_kept | 140 | 26.7 |
| 14 moved term | R_moved_term_ignored | 13 | 93.2 |
| 14 moved is shortfall only | R_moved_absolute | 168 | 12.0 |
| 17 unmet_reason window | R_unmet_reason_no_window | 165 | 13.6 |
| 17 changed per slot | R_changed_by_total | 145 | 24.1 |
| 18 slot feeder_kwh is fleet load | R_slot_feeder_is_group | 65 | 66.0 |
| 21 data_quality order | R_quality_file_order | 182 | 4.7 |
| 22 missing input names file | R_missing_file_unnamed | 188 | 1.6 |

These are design numbers, not hardness evidence.

## Fix v2 (board 0d6348c, 1 Nov)
Positive test weight is now 197 (48 checks: 45 positive, 3 negatives -3, -5, -1) and positive judge
weight 38 (judge mid 46.7%, JUDGE_MAP.md). The shipped derating now binds (CL-3), so the F lever also
costs the shipped plan checks. The tables above are the pre-fix measurement on 191 and are kept as they
were; the post-fix kill table (three blind programs, first write, all but one, careful shift search) is in
`master_chat_work/20261101_depot-charge-plan/p12_fix_v2_0d6348c/FIX_REPORT.md`.

## Harden r3 (board c5b188a), measured 1 Nov 20:10-20:30 on the final tests

Full tests-only verifier (dcp-verifier:1, --memory 4g --cpus 2, reward 1/557 per point), program copied as /app/out/derive_report.py.
Lever U = 72 checks fresh_u1..u9 (360 points). Logs: _runs/20261101/depot-charge-plan/harden3-20261101T1746/newkill/lane{A,B}.log.

| program | reward | points /557 | U points kept /360 | U checks EXACT/WRONG/CRASH | test.sh s |
|---|---|---|---|---|---|
| a1 (paid attempt-1 program) | 0.3537 | 197 | 0 | 0/72/0 | 52 |
| dblind_fd98e12 | 0.0072 | 4 | 0 | 0/72/0 | 60 |
| dblind_d9d6ab5 | 0.0180 | 10 | 0 | 0/72/0 | 74 |
| blind1 | 0.0180 | 10 | 0 | 0/72/0 | 155 |
| blind2 | 0.0108 | 6 | 0 | 0/0/72 | 56 |
| blind3 | 0.0108 | 6 | 0 | 0/0/72 | 56 |
| firstwrite | 0.0233 | 13 | 0 | 0/72/0 | 61 |
| allbutone (no tie pass) | 0.0287 | 16 | 0 | 0/72/0 | 80 |
| oracle_min (all-but-one for U) | 0.3537 | 197 | 0 | 0/72/0 | 76 |
| careful shift search | 0.8618 | 480 | 315 | 63/9/0 | 77 |
| careful shift search + rule 13 | 1.0 | 557 | 360 | 72/0/0 | 71 |
| iso_u5 (oracle raising on u5 only) | 0.9282 | 517 | 320 | 64/0/8 | 73 |
| oracle | 1.0 | 557 | 360 | 72/0/0 | 89 |

Reference seconds: u folders max 3.29 s (300-seed fuzz), hidden max ~1.9 s, large max 17.9 s under 3-container contention (limit 120 s, bar 30 s).
Harbor gate verifier seconds: oracle 115.8 / 109.4 / 123.3, owner 124.6, nop 42.0, stub 98.5, forgery 87.1 (timeout 2700, bar 2430).
