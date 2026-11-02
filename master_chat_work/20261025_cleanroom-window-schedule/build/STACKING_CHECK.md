# STACKING_CHECK: cleanroom-window-schedule

Started from `tools/stacking_check.py <BUNDLE>` (30 checks, positive 98, negatives -8; judge 9 criteria, positive 24, batched) and corrected by reading tests/test_output.py.

## (a) One row per test

Books: shipped = the 415-night book in /app/data (expected values from the tests' own reference on a regenerated, sha256-checked copy); dense = H1 (6 nights, 68-71 jobs); carry = H2 (10 linked mid-size nights); wide = H3 (8 nights, 60-72 jobs); M = 14-night mutation book. Each hidden book is run once as user nobody from a foreign cwd under 2 s x nights.

| test | w | observable | decisive logic | levers whose misread fails it |
|---|---|---|---|---|
| shipped_summary_matches | 5 | /app/out/summary.json | whole document equal to reference | 1, 2, 3 |
| shipped_policy_audit_matches | 3 | /app/out/policy_audit.json | whole document equal | 1, 2, 3 |
| shipped_data_quality_matches | 3 | /app/out/data_quality.json | whole document equal | plain rule |
| shipped_regions_match | 3 | /app/out/region_{North,South,West,East}.json | four documents equal | 1, 2, 3 |
| shipped_segments_match | 3 | /app/out/segment_{commercial,public}.json | two documents equal | 1, 2, 3 |
| dense/carry/wide_book_plans_legal | 3 each | plan lines of that book's summary.json | every stated plan rule holds, fees and night money follow from the program's own plan (no reference comparison) | 1 (dense, wide: timeout), 2, 3 |
| dense/carry/wide_book_plans_optimal | 5 each | job to bay map per accepted night | equal to the reference optimum | 1, 2, 3 |
| dense/carry/wide_book_summary_matches | 5 each | that book's summary.json | whole document equal | 1, 2, 3 |
| dense/carry/wide_book_policy_audit_matches | 3 each | that book's policy_audit.json | whole document equal | 1, 2, 3 |
| dense/carry/wide_book_data_quality_matches | 3 each | that book's data_quality.json | whole document equal | plain rule (1 on dense, wide via timeout) |
| dense/carry/wide_book_regions_match | 3 each | that book's four region documents | equal | 1, 2, 3 |
| dense/carry/wide_book_segments_match | 3 each | that book's two segment documents | equal | 1, 2, 3 |
| missing_input_is_named | 3 | exit status and stderr on M minus one input | nonzero exit, stderr names the file | plain rule |
| relocated_reordered_reruns_match | 3 | documents of two runs on a relocated, row-reversed M | runs identical and equal to reference | 1, 2, 3 |
| negative_program_reads_verifier_files | -5 | source of /app/out/*.py | quoted /tests path | cheating act |
| negative_hardcoded_sample_answers | -3 | source of /app/out/*.py | 3+ shipped night ids or the shipped total net | cheating act |

TS-26: the tool's duplicate groups share a helper (`_hidden_documents`, `_shipped_documents`, `_holds`) but each member reads a different observable (a different book or a different document family), so no two rows share both observable and logic. Legal and optimal on one book read the same plan lines with different logic (rules against the program's own plan, versus equality with the reference). TS-13: each check owns one property; no multi-assert hints.

## (b) Penalty groups by act (tests + judge)

| act | members | sum abs w | |
|---|---|---|---|
| naming or reading grader files | negative_program_reads_verifier_files -5 | 5 | PASS |
| hardcoding the shipped answers | negative_hardcoded_sample_answers -3 | 3 | PASS |
| claiming an unrun check passed | judge R9 -5 | 5 | PASS |

No negative grades a lever.

## (c) Weight shares (of 98)

Hidden books 75 (76.5%); mutation (M book) 6 (6.1%); hidden or mutated 81 (82.7%, G3 >= 30% PASS); shipped whole documents 17 (17.3%). Every document check is whole document. Plain-rule checks 15 (15.3%).

## (d) Cost table (G10)

| lever | worst wrong program | tests lost | all but this right, overall | gate |
|---|---|---|---|---|
| LV-CW-1 | raw_tuned / raw_exact (time out on dense and wide books) | 51% (greedy 79%, greedy_ls 76%) | 0.695 | PASS |
| LV-CW-2 | no_initial | 70% (reset_nightly, touching_only 85%) | 0.648 | PASS |
| LV-CW-3 | no_crew, naive_collapse, lane_by_lane, flow_relax | 85% | 0.577 | PASS |

Full table with Docker runtimes: WORK/COST_TABLE.md.

## (e) Rule coverage (G11)

WORK/RULE_COVERAGE.md: 44 rows, no row with 0 tests failed. The stated tie order has no row: every generated night has a single optimal plan, so a tie mutant fails no test (G-3 by design; open point for the master).

## (f) EVIDENCE_MAP

WORK/EVIDENCE_MAP.md: 10 rows, every graded rule points to its contract sentence (environment/data/contract.md:NN). No rule is graded without a sentence. No L11 lever, so no UNIQUENESS table.

STACKING PASS

## Lessons for the master
- stacking_check.py flags per-book checks sharing a helper as TS-26 groups; the observable differs per book | template_change: tools/stacking_check.py observable extraction could read the book key passed to the helper.
- J2 conduct criteria are not detected when phrased "independently recomputes" | template_change: tools/stacking_check.py J2 regex.
