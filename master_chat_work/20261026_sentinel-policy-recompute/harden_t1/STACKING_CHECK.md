# STACKING_CHECK: sentinel-policy-recompute (test-hardening t1, b7e15f9)

Tool: `master_chat_tasks/tools/stacking_check.py` (raw `stacking_raw.txt`); hints corrected by reading `tests/test_output.py` and by local scoring (`WORK/local_score.py`; oracle 80/80). Tests channel only; judge is d0f1870 unchanged (15 criteria, P 40).

## (a) Per-test rows (new and changed)

| id | w | observable | decisive logic | misreads that fail it | probe-4 program |
|---|---|---|---|---|---|
| hidden_running_timeout_floor_hard | 5 | policy + curve + graded trace (incl ledger_controls) on q1-a, q1-b | running floor 1000 in ascending seq (3 and 2 raises) | Q1 sum, Q1 clamp after sum | FAIL (-996 vs 1146) |
| hidden_reissued_override_hard | 5 | same on q2-a, q2-b | only highest-seq row of a reissued id; earlier rows draw nothing | Q2 rows independent | FAIL |
| hidden_principal_alias_span_hard | 5 | same on q3-a, q3-b | alias rows count for K042 only inside the half-open span | Q3 aliases ignored, span ignored | FAIL |
| hidden_requires_order_hard | 5 | same on q4-a, q4-b | requires met only by an earlier applied row | Q4 ignored, order-free | FAIL |
| hidden_superseded_carry_hard | 5 | same on q5-a, q5-b | superseded carry adds one delta when window/version match; not listed | Q5 ignored, carry outside window | FAIL |
| hidden_rare_rule_pairs_hard | 3 | same on combo-a, combo-b | seven two-rule pairs on one record | any primary Q reading | FAIL |
| older 17 checks | 52 | unchanged | old corpora rebuilt byte-equal; no quiet rule fires there | unchanged | 52/52 PASS |

TS-26: the tool groups the four older `_hard` tests and leaves the new five undistinguished (each a call to `assert_full_documents` on its own `OWNED` corpora). Not duplicates: each reads its own generated corpora and `t1_levers.py` shows each primary reading fails only its own check plus the rare-pair check. TS-13: `assert_full_documents` asserts on three documents of one rerun; the trace check's 5 asserts grade one document.

## (b) Penalty groups by act (tests + judge)

| act | members | sum abs w | verdict |
|---|---|---|---|
| hardcoding the shipped answers | negative_hardcoded_sample_answers -5 | 5 | PASS |
| forging the command transcript | negative_transcript_disagrees_with_config -3 | 3 | PASS |
| host or credential material in artifacts | negative_url_or_secret_in_artifacts -3 | 3 | PASS |
| claiming a check passed with no run | judge r13 -3 | 3 | PASS |
| stating a figure that differs from the delivered file | judge r14 -5 | 5 | PASS |
| overstating a check's size | judge r15 -3 | 3 | PASS |

The tool's UNMATCHED row (14) lumps four distinct acts; split by hand, every group <= 5. Negatives unchanged. No negative grades a quiet-rule reading.

## (c) Shares and caps

P = 80 (weights 5/3/1; the five owned checks weigh 5, tests_qc W2). Hidden or mutated reruns 76/80 = 95.0% (>= 30%); new quiet-rule checks 28 (35.0%); older `_hard` 20 (25.0%); coupling whole-document 15 (18.75%); mutation 9 (11.25%); isolated 3 + rebuild 3 (7.5%); shipped-only 1 (1.25%). Tests 23, criteria 15. Weight-1: rerun and shipped check only (not core).

## (d) Cost table (G10, measured, WORK/COST_TABLE.md)

| reading (one rule wrong) | tests | share lost |
|---|---|---|
| Q1 sum / Q1 clamp after sum | 72/80 = 90.0 | 10.0% |
| Q2 reissued rows independent | 72/80 = 90.0 | 10.0% |
| Q3 aliases ignored | 72/80 = 90.0 | 10.0% |
| Q3 span ignored | 75/80 = 93.75 | 6.25% |
| Q4 requires ignored / order-free | 72/80 = 90.0 | 10.0% |
| Q5 carry ignored | 72/80 = 90.0 | 10.0% |
| Q5 carry outside window | 75/80 = 93.75 | 6.25% |
| all-but-one (best single miss) | 72/80 = 90.0 | 10.0% |
| first write (every quiet rule skipped) | 52/80 = 65.0 | 35.0% |
| probe-4 agent program (as delivered) | 52/80 = 65.0 | 35.0% |

## (e) Rule coverage (G11)

WORK/RULE_COVERAGE.md: 27 old mutants at P 80 plus the nine Q readings; every rule fails at least one test; 0 uncovered.

STACKING PASS
