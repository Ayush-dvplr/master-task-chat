# RULE_COVERAGE (G11), P12 v3 r3

Each CTRL rule QC v3 F1 named has a hidden test that owns it. Mutant = the fixed solution/solve.py with that one rule put back to the old reading (WORK/rule_cov/make_mutants.py). Scored with WORK/local_score.py on the AFTER tests (46 checks, P = 172); oracle scores 172/172 (rule_cov/score_oracle.txt).

| rule | file:line | mutant | tests failed |
| --- | --- | --- | --- |
| CTRL-C broken or short payload = twenty four zero digits (calibration.md:85-87) | solution/solve.py:273; tests/test_output.py:1025-1028 (reference) | mut_zero: broken payload read as `none` | test_trap_zeroed_payload_inverse (exit 1, calibration); 169/172 |
| CTRL-G carry resets to 0 and 0 after a none (calibration.md:109-111) | solution/solve.py:324 | mut_carry: carry kept across a none | test_trap_carry_reset_inverse (exit 1); 169/172 |
| CTRL-H none counts as a stored 0 (calibration.md:118-119) | solution/solve.py:353 | mut_stepped: none breaks the stepped series | test_trap_stepped_gap_inverse (exit 1); 169/172 |
| CTRL-H index taken against the list length (calibration.md:122) | solution/solve.py:365 | mut_index: index >= len(table) dropped | test_trap_index_lap_inverse (exit 1); 169/172 |

Rules uncovered: 0. The pre-fix oracle (WORK/trap/before_v3r3/solution/solve.py) fails all four new tests (exit 1). Generator bounds (G12): `_check_damage` (tests/test_output.py:520) asserts the reference decode of every damaged set equals the planted marks (damaged entry -> `none`) and no damaged entry sits in an echoed capture; `_check_unbound` (:481) asserts no charter in a trap or damaged set can reach its allowance under any reading.

## P12 v3 r5 (QC v5 F1 CL-4): cancellation order

| rule | file:line | mutant | tests failed |
| --- | --- | --- | --- |
| reversal cancels the earliest uncancelled entry of its kind (engine-rules.md:87-88) | solution/solve.py (`queue.pop(0)`); tests/test_output.py `_grades_order`, `_plant_divergence`, `_settle_one_order` | var_lifo (single_lever.py): `queue.pop()` | instance_scenario_visible, instance_perf_report, instance_recommendations, instance_data_quality, instance_report_serialization, general_reversal_density, general_reversal_tiebreak; 157/172 (trap/scores_after_v3r5/var_lifo.txt) |

Rules uncovered: 0. Bound: `assert_postconditions` requires the two orders to part on the shipped set and forbids it on every corpus `_grades_order` excludes.
