# stacking_check: cold-chain-backbone-quote

tests/test_output.py: 54 checks, positive total 200, negatives -8; judge: 13 criteria, positive 32, mode batched. Static hints only; confirm by reading the code.

## 1. Test -> observable map

| test | w | class (basis) | observable (literals) | logic (helpers) | asserts/and-cmp |
|---|---|---|---|---|---|
| archive_follows_build_config | 1 | isolated (default (rule/fixture/case check)) | %s: %s, __name__, check | - | 0/0 |
| archived_package_metadata | 1 | isolated (default (rule/fixture/case check)) | %s: %s, __name__, check | - | 0/0 |
| shipped_core_document | 5 | shipped_only (artifact/shipped wording) | module_core.json | _holds, _check_shipped | 0/0 |
| shipped_parser_document | 3 | shipped_only (artifact/shipped wording) | module_parser.json | _holds, _check_shipped | 0/0 |
| shipped_report_document | 5 | shipped_only (artifact/shipped wording) | module_report.json | _holds, _check_shipped | 0/0 |
| shipped_summary_document | 3 | shipped_only (artifact/shipped wording) | summary.json, summary.json for the shipped book matches the contract whole | _holds, _check_shipped | 0/0 |
| test_fixes_document | 3 | whole_doc (whole-document wording) | %s: %s, __name__, check | - | 0/0 |
| repair_report_fields | 1 | isolated (default (rule/fixture/case check)) | %s: %s, __name__, check | - | 0/0 |
| fresh_1_core | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | module_core.json | _holds, _check_fresh | 0/0 |
| fresh_2_core | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | module_core.json | _holds, _check_fresh | 0/0 |
| fresh_3_core | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | module_core.json | _holds, _check_fresh | 0/0 |
| fresh_1_report | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | module_report.json | _holds, _check_fresh | 0/0 |
| fresh_2_report | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | module_report.json | _holds, _check_fresh | 0/0 |
| fresh_3_report | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | module_report.json | _holds, _check_fresh | 0/0 |
| fresh_1_summary | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | summary.json | _holds, _check_fresh | 0/0 |
| fresh_2_summary | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | summary.json | _holds, _check_fresh | 0/0 |
| fresh_3_summary | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | summary.json | _holds, _check_fresh | 0/0 |
| fresh_networks_feasible | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | %s: %s, __name__, check | - | 0/0 |
| fresh_rollups_follow_network | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | %s: %s, __name__, check | - | 0/0 |
| rescaled_book_documents | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | rescaled | _holds, _check_fresh | 0/0 |
| relocated_book_documents | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | %s: %s, __name__, check | - | 0/0 |
| missing_file_reported | 3 | whole_doc (whole-document wording) | %s: %s, __name__, check | - | 0/0 |
| rejection_book_parser | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | module_parser.json | _holds, _check_fresh | 0/0 |
| tie_book_core | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | module_core.json | _holds, _check_fresh | 0/0 |
| rerun_identical | 1 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | %s: %s, __name__, check | - | 0/0 |
| wide_1_core | 5 | whole_doc (whole-document wording) | module_core.json | _holds, _check_fresh | 0/0 |
| wide_2_core | 5 | whole_doc (whole-document wording) | module_core.json | _holds, _check_fresh | 0/0 |
| wide_3_core | 5 | whole_doc (whole-document wording) | module_core.json | _holds, _check_fresh | 0/0 |
| wide_books_report | 3 | whole_doc (whole-document wording) | module_report.json | _holds, _check_wide | 0/0 |
| wide_books_summary | 3 | whole_doc (whole-document wording) | summary.json | _holds, _check_wide | 0/0 |
| wide_networks_feasible | 3 | isolated (default (rule/fixture/case check)) | %s: %s, __name__, check | - | 0/0 |
| wide_4_core | 5 | whole_doc (whole-document wording) | module_core.json | _holds, _check_fresh | 0/0 |
| wide_4_report | 5 | whole_doc (whole-document wording) | module_report.json | _holds, _check_fresh | 0/0 |
| wide_4_summary | 3 | whole_doc (whole-document wording) | summary.json | _holds, _check_fresh | 0/0 |
| wide_5_core | 5 | whole_doc (whole-document wording) | module_core.json | _holds, _check_fresh | 0/0 |
| wide_5_report | 5 | whole_doc (whole-document wording) | module_report.json | _holds, _check_fresh | 0/0 |
| wide_5_summary | 3 | whole_doc (whole-document wording) | summary.json | _holds, _check_fresh | 0/0 |
| wide_6_core | 5 | whole_doc (whole-document wording) | module_core.json | _holds, _check_fresh | 0/0 |
| wide_6_report | 5 | whole_doc (whole-document wording) | module_report.json | _holds, _check_fresh | 0/0 |
| wide_6_summary | 3 | whole_doc (whole-document wording) | summary.json | _holds, _check_fresh | 0/0 |
| wide_7_core | 5 | whole_doc (whole-document wording) | module_core.json | _holds, _check_fresh | 0/0 |
| wide_7_report | 5 | whole_doc (whole-document wording) | module_report.json | _holds, _check_fresh | 0/0 |
| wide_7_summary | 3 | whole_doc (whole-document wording) | summary.json | _holds, _check_fresh | 0/0 |
| wide_8_core | 5 | whole_doc (whole-document wording) | module_core.json | _holds, _check_fresh | 0/0 |
| wide_8_report | 5 | whole_doc (whole-document wording) | module_report.json | _holds, _check_fresh | 0/0 |
| wide_8_summary | 3 | whole_doc (whole-document wording) | summary.json | _holds, _check_fresh | 0/0 |
| wide_9_core | 5 | whole_doc (whole-document wording) | module_core.json | _holds, _check_fresh | 0/0 |
| wide_9_report | 5 | whole_doc (whole-document wording) | module_report.json | _holds, _check_fresh | 0/0 |
| wide_9_summary | 3 | whole_doc (whole-document wording) | summary.json | _holds, _check_fresh | 0/0 |
| wide_10_core | 5 | whole_doc (whole-document wording) | module_core.json | _holds, _check_fresh | 0/0 |
| wide_10_report | 5 | whole_doc (whole-document wording) | module_report.json | _holds, _check_fresh | 0/0 |
| wide_10_summary | 3 | whole_doc (whole-document wording) | summary.json | _holds, _check_fresh | 0/0 |
| negative_hardcoded_sample_answers | -5 | negative (weight < 0 or negative_ name) | The fresh-book run returns the shipped book's documents | _fires, _replays_shipped_output | 0/0 |
| negative_visible_tests_removed | -3 | negative (weight < 0 or negative_ name) | The archive drops or skips a shipped visible test | _fires, _visible_tests_removed | 0/0 |

TS-26 duplicate candidates (same observable AND same logic): archive_follows_build_config = archived_package_metadata = test_fixes_document = repair_report_fields = fresh_networks_feasible = fresh_rollups_follow_network = relocated_book_documents = missing_file_reported = rerun_identical = wide_networks_feasible; fresh_1_core = fresh_2_core = fresh_3_core = tie_book_core = wide_1_core = wide_2_core = wide_3_core = wide_4_core = wide_5_core = wide_6_core = wide_7_core = wide_8_core = wide_9_core = wide_10_core; fresh_1_report = fresh_2_report = fresh_3_report = wide_4_report = wide_5_report = wide_6_report = wide_7_report = wide_8_report = wide_9_report = wide_10_report; fresh_1_summary = fresh_2_summary = fresh_3_summary = wide_4_summary = wide_5_summary = wide_6_summary = wide_7_summary = wide_8_summary = wide_9_summary = wide_10_summary

## 2. TS-13 multi-assert hints

- none

## 3. AL-28 penalty groups (tests + judge, |w| <= 5 per act)

| act | tests | judge | sum |w| | |
|---|---|---|---|---|
| hardcoding the shipped answers | negative_hardcoded_sample_answers -5 | - | 5 | PASS |
| UNMATCHED act (name it by hand) | negative_visible_tests_removed -3 | R12 -5, R13 -3 | 11 | FAIL |
| claims a check passed that its output contradicts (honesty) | - | R11 -3 | 3 | PASS |

## 4. Weight shares (of positive test weight)

- whole_doc: 118 (59.0%)
- format_hidden: 0 (0.0%)
- hidden_rows: 60 (30.0%)
- isolated: 6 (3.0%)
- mutation: 0 (0.0%)
- shipped_only: 16 (8.0%)
- G3: hidden or mutated reruns 89.0% (>= 30%); isolated+mutation 3.0%, whole-document 59.0%, shipped-only 8.0% (info, no cap)

## 5. Caps and weights

- tests 54, criteria 13 (no cap; kit floors 10 / 8)
- weight-1 checks (TS-20: never on a core check): archive_follows_build_config, archived_package_metadata, repair_report_fields, rerun_identical
- judge J1 hints (criterion quotes a figure): none
- judge J2 conduct criteria: none

## Verdict hints

- TS-26 duplicate candidates: 4 group(s): CHECK BY HAND
- AL-28 groups <= 5: FAIL
- G3 hidden or mutated reruns >= 30% (LEVER_RULES 24 Oct 13:15): 89.0% PASS
- G3 isolated / shipped-only (info, no cap): 3.0% / 8.0%
- tests >= 10 (no cap): 54 PASS
- criteria >= 8 (no cap): 13 PASS
- judge mode batched: batched
