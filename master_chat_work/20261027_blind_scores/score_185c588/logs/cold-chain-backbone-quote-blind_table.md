| check | weight | result | lever | failure kind | first assertion line |
|---|---|---|---|---|---|
| archive_follows_build_config | 1 | pass |  |  |  |
| shipped_core_document | 5 | pass |  |  |  |
| shipped_parser_document | 3 | pass |  |  |  |
| shipped_report_document | 5 | pass |  |  |  |
| shipped_summary_document | 3 | pass |  |  |  |
| test_fixes_document | 3 | pass |  |  |  |
| repair_report_fields | 1 | pass |  |  |  |
| fresh_1_core | 5 | FAIL |  | timeout (50 s CLI limit) | `AssertionError: exit -9: timed out after 50 s` |
| fresh_2_core | 5 | FAIL |  | timeout (50 s CLI limit) | `AssertionError: exit -9: timed out after 50 s` |
| fresh_3_core | 5 | FAIL |  | timeout (50 s CLI limit) | `AssertionError: exit -9: timed out after 50 s` |
| fresh_1_report | 5 | FAIL |  | timeout (50 s CLI limit) | `AssertionError: exit -9: timed out after 50 s` |
| fresh_2_report | 5 | FAIL |  | timeout (50 s CLI limit) | `AssertionError: exit -9: timed out after 50 s` |
| fresh_3_report | 5 | FAIL |  | timeout (50 s CLI limit) | `AssertionError: exit -9: timed out after 50 s` |
| fresh_1_summary | 3 | FAIL |  | timeout (50 s CLI limit) | `AssertionError: exit -9: timed out after 50 s` |
| fresh_2_summary | 3 | FAIL |  | timeout (50 s CLI limit) | `AssertionError: exit -9: timed out after 50 s` |
| fresh_3_summary | 3 | FAIL |  | timeout (50 s CLI limit) | `AssertionError: exit -9: timed out after 50 s` |
| fresh_networks_feasible | 3 | FAIL |  | timeout (50 s CLI limit) | `AssertionError: exit -9: timed out after 50 s` |
| fresh_rollups_follow_network | 3 | FAIL |  | timeout (50 s CLI limit) | `AssertionError: exit -9: timed out after 50 s` |
| rescaled_book_documents | 5 | FAIL |  | timeout (50 s CLI limit) | `AssertionError: exit -9: timed out after 50 s` |
| relocated_book_documents | 3 | FAIL |  | timeout (50 s CLI limit) | `AssertionError: exit -9: timed out after 50 s` |
| missing_file_reported | 3 | pass |  |  |  |
| rejection_book_parser | 3 | pass |  |  |  |
| tie_book_core | 3 | pass |  |  |  |
| rerun_identical | 1 | FAIL |  | timeout (50 s CLI limit) | `AssertionError: exit -9: timed out after 50 s` |
| wide_1_core | 5 | FAIL | yes | timeout (50 s CLI limit) | `AssertionError: exit -9: timed out after 50 s` |
| wide_2_core | 5 | FAIL | yes | timeout (50 s CLI limit) | `AssertionError: exit -9: timed out after 50 s` |
| wide_3_core | 5 | FAIL | yes | timeout (50 s CLI limit) | `AssertionError: exit -9: timed out after 50 s` |
| wide_books_report | 3 | FAIL | yes | timeout (50 s CLI limit) | `AssertionError: exit -9: timed out after 50 s` |
| wide_books_summary | 3 | FAIL | yes | timeout (50 s CLI limit) | `AssertionError: exit -9: timed out after 50 s` |
| wide_networks_feasible | 3 | FAIL | yes | timeout (50 s CLI limit) | `AssertionError: exit -9: timed out after 50 s` |
| negative_hardcoded_sample_answers | -5 | not fired |  |  |  |
| negative_visible_tests_removed | -3 | not fired |  |  |  |
