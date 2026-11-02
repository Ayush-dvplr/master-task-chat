# LEVERS

One row per check of tests/test_output.py. A lever id is listed when at least one wrong program for that lever (WORK/mutants/, see COST_TABLE.md) fails the check.

| check | weight | levers |
|---|---|---|
| shipped_summary_matches | 5 | LV-CW-1, LV-CW-2, LV-CW-3 |
| shipped_policy_audit_matches | 3 | LV-CW-1, LV-CW-2, LV-CW-3 |
| shipped_data_quality_matches | 3 | none (plain rule) |
| shipped_regions_match | 3 | LV-CW-1, LV-CW-2, LV-CW-3 |
| shipped_segments_match | 3 | LV-CW-1, LV-CW-2, LV-CW-3 |
| dense_book_plans_legal | 3 | LV-CW-1, LV-CW-2, LV-CW-3 |
| dense_book_plans_optimal | 5 | LV-CW-1, LV-CW-2, LV-CW-3 |
| dense_book_summary_matches | 5 | LV-CW-1, LV-CW-2, LV-CW-3 |
| dense_book_policy_audit_matches | 3 | LV-CW-1, LV-CW-2, LV-CW-3 |
| dense_book_data_quality_matches | 3 | LV-CW-1 (runtime: raw optimisers time out) |
| dense_book_regions_match | 3 | LV-CW-1, LV-CW-2, LV-CW-3 |
| dense_book_segments_match | 3 | LV-CW-1, LV-CW-2, LV-CW-3 |
| carry_book_plans_legal | 3 | LV-CW-2, LV-CW-3 |
| carry_book_plans_optimal | 5 | LV-CW-1, LV-CW-2, LV-CW-3 |
| carry_book_summary_matches | 5 | LV-CW-1, LV-CW-2, LV-CW-3 |
| carry_book_policy_audit_matches | 3 | LV-CW-1, LV-CW-2, LV-CW-3 |
| carry_book_data_quality_matches | 3 | none (plain rule) |
| carry_book_regions_match | 3 | LV-CW-1, LV-CW-2, LV-CW-3 |
| carry_book_segments_match | 3 | LV-CW-1, LV-CW-2, LV-CW-3 |
| wide_book_plans_legal | 3 | LV-CW-1, LV-CW-2, LV-CW-3 |
| wide_book_plans_optimal | 5 | LV-CW-1, LV-CW-2, LV-CW-3 |
| wide_book_summary_matches | 5 | LV-CW-1, LV-CW-2, LV-CW-3 |
| wide_book_policy_audit_matches | 3 | LV-CW-1, LV-CW-2, LV-CW-3 |
| wide_book_data_quality_matches | 3 | LV-CW-1 (runtime: raw optimisers time out) |
| wide_book_regions_match | 3 | LV-CW-1, LV-CW-2, LV-CW-3 |
| wide_book_segments_match | 3 | LV-CW-1, LV-CW-2, LV-CW-3 |
| missing_input_is_named | 3 | none (plain rule) |
| relocated_reordered_reruns_match | 3 | LV-CW-1, LV-CW-2, LV-CW-3 |
| negative_program_reads_verifier_files | -5 | none (cheating act) |
| negative_hardcoded_sample_answers | -3 | none (cheating act) |

| lever | positive weight of checks it can fail | share of 98 |
|---|---|---|
| LV-CW-1 | 86 | 88% |
| LV-CW-2 | 83 | 85% |
| LV-CW-3 | 83 | 85% |

Checks no lever program fails on fast runs (the four data_quality checks and missing_input_is_named) grade plain stated rules: 15 of 98; the dense and wide data_quality checks are also lost by the raw exact optimisers through the time limit. There is no secondary lever. The two negative checks grade cheating acts, not a lever.

## Lessons for the master

- Lever weight per check follows directly from the cost runs | no change: LEVERS.md is generated from tmp/cost/*.json.
