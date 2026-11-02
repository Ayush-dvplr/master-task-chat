# LEVERS (one row per check)

Lever ids come from the cost runs: a check carries a lever when the lever-wrong package (WORK/cost/final_rows.json) loses it. No secondary stated-rule lever (core build).

| check | weight | levers | other role |
|---|---|---|---|
| hidden_book_1_core | 5 | LV-BS-1, LV-BS-2, LV-BS-3 | whole document exact |
| hidden_book_1_metrics | 5 | LV-BS-1, LV-BS-2, LV-BS-3 | whole document exact |
| hidden_book_1_deps | 5 | LV-BS-1, LV-BS-2, LV-BS-3 | whole document exact |
| hidden_book_1_summary | 5 | LV-BS-1, LV-BS-2, LV-BS-3 | whole document exact |
| hidden_book_2_core | 5 | LV-BS-1, LV-BS-2, LV-BS-3 | whole document exact |
| hidden_book_2_metrics | 5 | LV-BS-1, LV-BS-2, LV-BS-3 | whole document exact |
| hidden_book_2_deps | 5 | LV-BS-1, LV-BS-2, LV-BS-3 | whole document exact |
| hidden_book_2_summary | 5 | LV-BS-1, LV-BS-2, LV-BS-3 | whole document exact |
| hidden_book_3_core | 5 | LV-BS-1, LV-BS-2, LV-BS-3 | whole document exact |
| hidden_book_3_metrics | 5 | LV-BS-1, LV-BS-2, LV-BS-3 | whole document exact |
| hidden_book_3_deps | 5 | LV-BS-1, LV-BS-2, LV-BS-3 | whole document exact |
| hidden_book_3_summary | 5 | LV-BS-1, LV-BS-2, LV-BS-3 | whole document exact |
| hidden_book_4_core | 5 | LV-BS-1, LV-BS-2, LV-BS-3 | whole document exact |
| hidden_book_4_metrics | 5 | LV-BS-1, LV-BS-2, LV-BS-3 | whole document exact |
| hidden_book_4_deps | 5 | LV-BS-1, LV-BS-2, LV-BS-3 | whole document exact |
| hidden_book_4_summary | 5 | LV-BS-1, LV-BS-2, LV-BS-3 | whole document exact |
| rows_reshuffled | 5 | LV-BS-1, LV-BS-2, LV-BS-3 | whole document exact |
| policy_changed | 5 | LV-BS-1, LV-BS-2, LV-BS-3 | whole document exact |
| run_twice | 3 | - | determinism (HASHORDER mutant) |
| shipped_core | 3 | LV-BS-1, LV-BS-2, LV-BS-3 | whole document exact |
| shipped_metrics | 3 | LV-BS-1, LV-BS-2, LV-BS-3 | whole document exact |
| shipped_deps | 3 | LV-BS-1, LV-BS-2, LV-BS-3 | whole document exact |
| shipped_summary | 3 | LV-BS-1, LV-BS-2, LV-BS-3 | whole document exact |
| worker_capacity | 3 | - | invariant (DOWNKEEP mutant; also lost under LV-BS-1 via state) |
| state_invariants | 3 | LV-BS-1 |  |
| refuse_missing_input | 3 | - | rejection |
| refuse_invalid_policy | 3 | - | rejection |
| refuse_unknown_entity | 3 | - | rejection |
| refuse_event_conflict | 3 | - | rejection |
| refuse_cycle | 3 | - | rejection |
| artifacts_present | 1 | - | existence |
| call_and_module_agree | 3 | - | package |
| selftest_matches_rerun | 3 | - | package |
| build_report | 3 | - | package |
| shipped_tests_kept | 3 | - | package |
| negative_package_reads_grader_paths | -5 | - | negative: reads grader paths |
| negative_hardcoded_sample_answers | -3 | - | negative: stored answers |

Checks: 37 (WARN A3: above 35, recorded; no lever checks merged). Positive total: 139. Negatives: negative_package_reads_grader_paths -5, negative_hardcoded_sample_answers -3.

| lever | checks | weight | share of positive |
|---|---|---|---|
| LV-BS-1 | 23 | 105 | 75.5% |
| LV-BS-2 | 22 | 102 | 73.4% |
| LV-BS-3 | 22 | 102 | 73.4% |

The three levers share the whole-document checks through the COUPLING quantity (one replayed timeline per set feeds all four documents), so the shares overlap; each lever alone loses at least 73% of test points (COST_TABLE).
