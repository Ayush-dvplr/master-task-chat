| check | weight | lever | result | failure kind | first assertion line |
|---|---|---|---|---|---|
| artifact_set_exists_and_parses | 1 |  | pass |  |  |
| canonical_serialization_and_integer_units | 1 |  | pass |  |  |
| report_keys_match_schema | 1 |  | pass |  |  |
| report_arrays_in_schema_order | 1 |  | pass |  |  |
| selection_match | 3 |  | pass |  |  |
| selection_match_hard | 5 |  | pass |  |  |
| intervals_match | 3 |  | pass |  |  |
| intervals_match_hard | 5 |  | pass |  |  |
| tie_decisions_match | 3 |  | pass |  |  |
| tie_decisions_match_hard | 5 |  | pass |  |  |
| segment_rows_match | 3 |  | pass |  |  |
| segment_rows_match_hard | 5 |  | pass |  |  |
| ledger_quality_match | 3 |  | pass |  |  |
| ledger_quality_match_hard | 5 |  | pass |  |  |
| region_totals_North_match | 3 |  | pass |  |  |
| region_totals_North_match_hard | 5 |  | pass |  |  |
| region_totals_South_match | 3 |  | pass |  |  |
| region_totals_South_match_hard | 5 |  | pass |  |  |
| region_totals_West_match | 3 |  | pass |  |  |
| region_totals_West_match_hard | 5 |  | pass |  |  |
| region_totals_East_match | 3 |  | pass |  |  |
| region_totals_East_match_hard | 5 |  | pass |  |  |
| segment_totals_match | 3 |  | pass |  |  |
| segment_totals_match_hard | 5 |  | pass |  |  |
| summary_match | 3 |  | pass |  |  |
| summary_match_hard | 5 |  | pass |  |  |
| labels_match | 3 |  | pass |  |  |
| labels_match_hard | 5 |  | pass |  |  |
| quality_counts_match | 3 |  | pass |  |  |
| quality_counts_match_hard | 5 |  | pass |  |  |
| credit_rows_match | 3 |  | pass |  |  |
| credit_rows_match_hard | 5 |  | pass |  |  |
| segment_credit_rows_match | 3 |  | pass |  |  |
| segment_credit_rows_match_hard | 5 |  | pass |  |  |
| funded_pool_match | 3 |  | pass |  |  |
| funded_pool_match_hard | 5 |  | pass |  |  |
| grants_match | 3 |  | pass |  |  |
| grants_match_hard | 5 |  | pass |  |  |
| grant_allocation_match | 3 |  | pass |  |  |
| grant_allocation_match_hard | 5 |  | pass |  |  |
| residual_match | 3 |  | pass |  |  |
| residual_match_hard | 5 |  | pass |  |  |
| cap_binding_match | 3 |  | pass |  |  |
| cap_binding_match_hard | 5 |  | pass |  |  |
| wide_0_portfolios_feasible | 3 | yes | FAIL | TIMEOUT | program run failed: timed out after 120 s |
| wide_0_selection_match | 5 | yes | FAIL | TIMEOUT | program run failed: timed out after 120 s |
| wide_0_tie_decisions_match | 5 | yes | FAIL | TIMEOUT | program run failed: timed out after 120 s |
| wide_0_intervals_match | 3 | yes | FAIL | TIMEOUT | program run failed: timed out after 120 s |
| wide_1_portfolios_feasible | 3 | yes | FAIL | TIMEOUT | program run failed: timed out after 120 s |
| wide_1_selection_match | 5 | yes | FAIL | TIMEOUT | program run failed: timed out after 120 s |
| wide_1_tie_decisions_match | 5 | yes | FAIL | TIMEOUT | program run failed: timed out after 120 s |
| wide_1_intervals_match | 3 | yes | FAIL | TIMEOUT | program run failed: timed out after 120 s |
| segment_rate_adder_mutation | 3 |  | pass |  |  |
| allowance_ticks_mutation | 3 |  | pass |  |  |
| minimum_grant_mutation | 3 |  | pass |  |  |
| negative_hardcoded_sample_answers | -5 |  | not fired |  |  |
| negative_reads_tests_or_reward_files | -5 |  | not fired |  |  |
| negative_external_dependency_or_network | -3 |  | not fired |  |  |

earned=173 neg_fired=0 pos_total=205 tests_pct=84.39 lever_lost=8/8 lever_pts_lost=32/32 non_lever_lost=0 kinds=['TIMEOUT']
