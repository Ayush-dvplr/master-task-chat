# STACKING_CHECK: tariff-engine-audit-repair, P12 fix of QC v1 (8e1b2d5)

Tool output (stacking_check.py on the fixed bundle) follows, then hand corrections.

# stacking_check: tariff-engine-audit-repair

tests/test_output.py: 116 checks, positive total 488, negatives -8; judge: 13 criteria, positive 33, mode batched. Static hints only; confirm by reading the code.

## 1. Test -> observable map

| test | w | class (basis) | observable (literals) | logic (helpers) | asserts/and-cmp |
|---|---|---|---|---|---|
| archive_follows_build_config | 1 | isolated (default (rule/fixture/case check)) | - | - | 0/0 |
| package_matches_manifest | 1 | isolated (default (rule/fixture/case check)) | - | - | 0/0 |
| delivered_visible_tests_pass | 3 | shipped_only (artifact/shipped wording) | - | - | 0/0 |
| corrected_tests_name_the_changed_tests | 3 | isolated (default (rule/fixture/case check)) | - | - | 0/0 |
| regression_rows_match_contract | 3 | isolated (default (rule/fixture/case check)) | - | - | 0/0 |
| module_notes_follow_contract | 1 | isolated (default (rule/fixture/case check)) | - | - | 0/0 |
| summary_lists_inputs_and_artifacts | 1 | shipped_only (artifact/shipped wording) | - | - | 0/0 |
| repair_report_has_stated_shape | 1 | isolated (default (rule/fixture/case check)) | repair-report.json has its stated shape | _holds, _check_repair_report | 0/0 |
| previously_failing_matches_log | 1 | isolated (default (rule/fixture/case check)) | - | - | 0/0 |
| shipped_exceptions_exact | 3 | shipped_only (artifact/shipped wording) | The exception list for the shipped /app/ci files is exact, shipped | _holds, _check_exceptions | 0/0 |
| shipped_standing_lines_exact | 5 | shipped_only (artifact/shipped wording) | Every standing line for the shipped /app/ci files is exact, shipped, standing | _holds, _check_lines | 0/0 |
| shipped_energy_lines_exact | 3 | shipped_only (artifact/shipped wording) | Every energy line for the shipped /app/ci files is exact, shipped, energy | _holds, _check_lines | 0/0 |
| shipped_subtotals_exact | 1 | shipped_only (artifact/shipped wording) | shipped, subtotal | _holds, _check_settlement | 0/0 |
| shipped_credits_and_totals_exact | 1 | shipped_only (artifact/shipped wording) | shipped | _holds, _check_settlement | 0/0 |
| fresh_exceptions_exact | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | fresh | _holds, _check_exceptions | 0/0 |
| fresh_energy_lines_exact | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | fresh, energy | _holds, _check_lines | 0/0 |
| fresh_standing_lines_exact | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | fresh, standing | _holds, _check_lines | 0/0 |
| fresh_subtotals_exact | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | fresh | _holds, _check_heads | 0/0 |
| fresh_credits_and_totals_exact | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | fresh | _holds, _check_settlement | 0/0 |
| rescaled_energy_lines_exact | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | rescaled, energy | _holds, _check_lines | 0/0 |
| rescaled_standing_lines_exact | 5 | isolated (default (rule/fixture/case check)) | rescaled, standing | _holds, _check_lines | 0/0 |
| rescaled_subtotals_exact | 5 | isolated (default (rule/fixture/case check)) | rescaled | _holds, _check_heads | 0/0 |
| rescaled_credits_and_totals_exact | 5 | isolated (default (rule/fixture/case check)) | rescaled | _holds, _check_settlement | 0/0 |
| relocated_lines_exact | 5 | isolated (default (rule/fixture/case check)) | relocated, energy, standing | _holds, _check_lines | 0/0 |
| relocated_subtotals_exact | 5 | isolated (default (rule/fixture/case check)) | relocated | _holds, _check_heads | 0/0 |
| relocated_credits_and_totals_exact | 5 | isolated (default (rule/fixture/case check)) | Every credit and total is exact on the relocated corpus, relocated | _holds, _check_settlement | 0/0 |
| rotated_lines_exact | 5 | isolated (default (rule/fixture/case check)) | rotated, energy, standing | _holds, _check_lines | 0/0 |
| rotated_subtotals_exact | 5 | isolated (default (rule/fixture/case check)) | rotated | _holds, _check_heads | 0/0 |
| rotated_credits_and_totals_exact | 5 | isolated (default (rule/fixture/case check)) | Every credit and total is exact on the rotated corpus, rotated | _holds, _check_settlement | 0/0 |
| recoded_lines_exact | 5 | isolated (default (rule/fixture/case check)) | recoded, energy, standing | _holds, _check_lines | 0/0 |
| recoded_subtotals_exact | 5 | isolated (default (rule/fixture/case check)) | recoded | _holds, _check_heads | 0/0 |
| recoded_credits_and_totals_exact | 5 | isolated (default (rule/fixture/case check)) | Every credit and total is exact on the recoded corpus, recoded | _holds, _check_settlement | 0/0 |
| renamed_lines_exact | 5 | isolated (default (rule/fixture/case check)) | renamed, energy, standing | _holds, _check_lines | 0/0 |
| renamed_subtotals_exact | 5 | isolated (default (rule/fixture/case check)) | renamed | _holds, _check_heads | 0/0 |
| renamed_credits_and_totals_exact | 5 | isolated (default (rule/fixture/case check)) | Every credit and total is exact on the renamed corpus, renamed | _holds, _check_settlement | 0/0 |
| api_energy_lines_exact | 5 | isolated (default (rule/fixture/case check)) | api, energy | _holds, _check_lines | 0/0 |
| api_standing_lines_exact | 5 | isolated (default (rule/fixture/case check)) | Every standing line is exact on the build_invoices corpus, api, standing | _holds, _check_lines | 0/0 |
| api_subtotals_exact | 5 | isolated (default (rule/fixture/case check)) | api | _holds, _check_heads | 0/0 |
| api_credits_and_totals_exact | 5 | isolated (default (rule/fixture/case check)) | Every credit and total is exact on the build_invoices corpus, api | _holds, _check_settlement | 0/0 |
| estimated_read_accounts_on_fresh_rescaled | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | estimated, fresh, rescaled | _holds, _check_owned | 0/0 |
| estimated_read_accounts_on_relocated_rotated | 5 | isolated (default (rule/fixture/case check)) | estimated, relocated, rotated | _holds, _check_owned | 0/0 |
| estimated_read_accounts_on_api_recoded_renamed | 5 | isolated (default (rule/fixture/case check)) | estimated, api, recoded, renamed | _holds, _check_owned | 0/0 |
| standing_change_accounts_on_fresh_rescaled | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | standing_changes, fresh, rescaled | _holds, _check_owned | 0/0 |
| standing_change_accounts_on_relocated_rotated | 5 | isolated (default (rule/fixture/case check)) | standing_changes, relocated, rotated | _holds, _check_owned | 0/0 |
| standing_change_accounts_on_api_recoded_renamed | 5 | isolated (default (rule/fixture/case check)) | standing_changes, api, recoded, renamed | _holds, _check_owned | 0/0 |
| meter_row_accounts_on_fresh_rescaled | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | meter_rows, fresh, rescaled | _holds, _check_owned | 0/0 |
| meter_row_accounts_on_relocated_rotated | 5 | isolated (default (rule/fixture/case check)) | meter_rows, relocated, rotated | _holds, _check_owned | 0/0 |
| meter_row_accounts_on_api_recoded_renamed | 5 | isolated (default (rule/fixture/case check)) | meter_rows, api, recoded, renamed | _holds, _check_owned | 0/0 |
| billing_row_accounts_on_fresh_rescaled_relocated_rotated | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | billing_rows, fresh, rescaled, relocated ... | _holds, _check_owned | 0/0 |
| billing_row_accounts_on_api_recoded_renamed | 5 | isolated (default (rule/fixture/case check)) | billing_rows, api, recoded, renamed | _holds, _check_owned | 0/0 |
| carried_allowance_accounts_on_fresh_rescaled_relocated_rotated | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | allowance_carried, fresh, rescaled, relocated ... | _holds, _check_owned | 0/0 |
| carried_allowance_accounts_on_api_recoded_renamed | 3 | isolated (default (rule/fixture/case check)) | allowance_carried, api, recoded, renamed | _holds, _check_owned | 0/0 |
| combined_row_accounts_on_fresh_rescaled_relocated_rotated | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | pairs, fresh, rescaled, relocated ... | _holds, _check_owned | 0/0 |
| combined_row_accounts_on_api_recoded_renamed | 3 | isolated (default (rule/fixture/case check)) | pairs, api, recoded, renamed | _holds, _check_owned | 0/0 |
| revision_accounts_on_fresh_rescaled | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | revision, fresh, rescaled | _holds, _check_owned | 0/0 |
| revision_accounts_on_relocated_rotated | 5 | isolated (default (rule/fixture/case check)) | revision, relocated, rotated | _holds, _check_owned | 0/0 |
| revision_accounts_on_api_recoded_renamed | 5 | isolated (default (rule/fixture/case check)) | revision, api, recoded, renamed | _holds, _check_owned | 0/0 |
| revision_row_accounts_on_fresh_rescaled_relocated_rotated | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | revision_rows, fresh, rescaled, relocated ... | _holds, _check_owned | 0/0 |
| revision_row_accounts_on_api_recoded_renamed | 5 | isolated (default (rule/fixture/case check)) | revision_rows, api, recoded, renamed | _holds, _check_owned | 0/0 |
| arrears_accounts_on_fresh_rescaled | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | arrears, fresh, rescaled | _holds, _check_owned | 0/0 |
| arrears_accounts_on_relocated_rotated | 5 | isolated (default (rule/fixture/case check)) | arrears, relocated, rotated | _holds, _check_owned | 0/0 |
| arrears_accounts_on_api_recoded_renamed | 5 | isolated (default (rule/fixture/case check)) | arrears, api, recoded, renamed | _holds, _check_owned | 0/0 |
| arrears_carried_accounts_on_fresh_rescaled_relocated_rotated | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | arrears_carried, fresh, rescaled, relocated ... | _holds, _check_owned | 0/0 |
| arrears_carried_accounts_on_api_recoded_renamed | 5 | isolated (default (rule/fixture/case check)) | arrears_carried, api, recoded, renamed | _holds, _check_owned | 0/0 |
| cumulative_read_accounts_on_fresh_rescaled | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | cumulative, fresh, rescaled | _holds, _check_owned | 0/0 |
| cumulative_read_accounts_on_relocated_rotated | 5 | isolated (default (rule/fixture/case check)) | cumulative, relocated, rotated | _holds, _check_owned | 0/0 |
| cumulative_read_accounts_on_api_recoded_renamed | 5 | isolated (default (rule/fixture/case check)) | cumulative, api, recoded, renamed | _holds, _check_owned | 0/0 |
| cumulative_row_accounts_on_all | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | cumulative_rows, fresh, rescaled, relocated ... | _holds, _check_owned | 0/0 |
| cumulative_meter_row_accounts_on_all | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | cumulative_meter_rows, fresh, rescaled, relocated ... | _holds, _check_owned | 0/0 |
| missing_source_is_named | 3 | isolated (default (rule/fixture/case check)) | - | - | 0/0 |
| two_runs_are_identical | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | Two runs on the same fresh corpus print identical documents | _holds, _check_two_runs | 0/0 |
| shipped_statements_exact | 5 | shipped_only (artifact/shipped wording) | Statements on the shipped data are exact as a whole document, shipped | _holds, _check_statement_document | 0/0 |
| fresh_statements_feasible | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | fresh | _holds, _check_statement_feasible | 0/0 |
| fresh_statement_due_exact | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | Every statement due on the fresh corpus is exact, fresh, due | _holds, _check_statement_field | 0/0 |
| fresh_statement_redeemed_exact | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | Every statement redeemed list on the fresh corpus is exact, fresh, redeemed | _holds, _check_statement_field | 0/0 |
| rescaled_statements_feasible | 3 | isolated (default (rule/fixture/case check)) | rescaled | _holds, _check_statement_feasible | 0/0 |
| rescaled_statement_due_exact | 5 | isolated (default (rule/fixture/case check)) | Every statement due on the rescaled corpus is exact, rescaled, due | _holds, _check_statement_field | 0/0 |
| rescaled_statement_redeemed_exact | 5 | isolated (default (rule/fixture/case check)) | rescaled, redeemed | _holds, _check_statement_field | 0/0 |
| relocated_statements_feasible | 3 | isolated (default (rule/fixture/case check)) | relocated | _holds, _check_statement_feasible | 0/0 |
| relocated_statement_due_exact | 5 | isolated (default (rule/fixture/case check)) | Every statement due on the relocated corpus is exact, relocated, due | _holds, _check_statement_field | 0/0 |
| relocated_statement_redeemed_exact | 5 | isolated (default (rule/fixture/case check)) | relocated, redeemed | _holds, _check_statement_field | 0/0 |
| rotated_statements_feasible | 3 | isolated (default (rule/fixture/case check)) | rotated | _holds, _check_statement_feasible | 0/0 |
| rotated_statement_due_exact | 5 | isolated (default (rule/fixture/case check)) | Every statement due on the rotated corpus is exact, rotated, due | _holds, _check_statement_field | 0/0 |
| rotated_statement_redeemed_exact | 5 | isolated (default (rule/fixture/case check)) | Every statement redeemed list on the rotated corpus is exact, rotated, redeemed | _holds, _check_statement_field | 0/0 |
| api_statements_feasible | 3 | isolated (default (rule/fixture/case check)) | api | _holds, _check_statement_feasible | 0/0 |
| api_statement_due_exact | 5 | isolated (default (rule/fixture/case check)) | Every statement due on the api corpus is exact, api, due | _holds, _check_statement_field | 0/0 |
| api_statement_redeemed_exact | 5 | isolated (default (rule/fixture/case check)) | Every statement redeemed list on the api corpus is exact, api, redeemed | _holds, _check_statement_field | 0/0 |
| recoded_statements_feasible | 3 | isolated (default (rule/fixture/case check)) | recoded | _holds, _check_statement_feasible | 0/0 |
| recoded_statement_due_exact | 5 | isolated (default (rule/fixture/case check)) | Every statement due on the recoded corpus is exact, recoded, due | _holds, _check_statement_field | 0/0 |
| recoded_statement_redeemed_exact | 5 | isolated (default (rule/fixture/case check)) | Every statement redeemed list on the recoded corpus is exact, recoded, redeemed | _holds, _check_statement_field | 0/0 |
| renamed_statements_feasible | 3 | isolated (default (rule/fixture/case check)) | renamed | _holds, _check_statement_feasible | 0/0 |
| renamed_statement_due_exact | 5 | isolated (default (rule/fixture/case check)) | Every statement due on the renamed corpus is exact, renamed, due | _holds, _check_statement_field | 0/0 |
| renamed_statement_redeemed_exact | 5 | isolated (default (rule/fixture/case check)) | Every statement redeemed list on the renamed corpus is exact, renamed, redeemed | _holds, _check_statement_field | 0/0 |
| fresh_ledger_statements_feasible | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | fresh | _holds, _check_ledger_feasible | 0/0 |
| fresh_ledger_statement_due_exact | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | Every statement due on the fresh ledger corpus is exact, fresh, due | _holds, _check_ledger_field | 0/0 |
| fresh_ledger_statement_redeemed_exact | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | fresh, redeemed | _holds, _check_ledger_field | 0/0 |
| rescaled_ledger_statements_feasible | 3 | isolated (default (rule/fixture/case check)) | rescaled | _holds, _check_ledger_feasible | 0/0 |
| rescaled_ledger_statement_due_exact | 5 | isolated (default (rule/fixture/case check)) | Every statement due on the rescaled ledger corpus is exact, rescaled, due | _holds, _check_ledger_field | 0/0 |
| rescaled_ledger_statement_redeemed_exact | 5 | isolated (default (rule/fixture/case check)) | rescaled, redeemed | _holds, _check_ledger_field | 0/0 |
| relocated_ledger_statements_feasible | 3 | isolated (default (rule/fixture/case check)) | relocated | _holds, _check_ledger_feasible | 0/0 |
| relocated_ledger_statement_due_exact | 5 | isolated (default (rule/fixture/case check)) | Every statement due on the relocated ledger corpus is exact, relocated, due | _holds, _check_ledger_field | 0/0 |
| relocated_ledger_statement_redeemed_exact | 5 | isolated (default (rule/fixture/case check)) | relocated, redeemed | _holds, _check_ledger_field | 0/0 |
| rotated_ledger_statements_feasible | 3 | isolated (default (rule/fixture/case check)) | rotated | _holds, _check_ledger_feasible | 0/0 |
| rotated_ledger_statement_due_exact | 5 | isolated (default (rule/fixture/case check)) | Every statement due on the rotated ledger corpus is exact, rotated, due | _holds, _check_ledger_field | 0/0 |
| rotated_ledger_statement_redeemed_exact | 5 | isolated (default (rule/fixture/case check)) | rotated, redeemed | _holds, _check_ledger_field | 0/0 |
| api_ledger_statements_feasible | 3 | isolated (default (rule/fixture/case check)) | api | _holds, _check_ledger_feasible | 0/0 |
| api_ledger_statement_due_exact | 5 | isolated (default (rule/fixture/case check)) | Every statement due on the api ledger corpus is exact, api, due | _holds, _check_ledger_field | 0/0 |
| api_ledger_statement_redeemed_exact | 5 | isolated (default (rule/fixture/case check)) | api, redeemed | _holds, _check_ledger_field | 0/0 |
| recoded_ledger_statements_feasible | 3 | isolated (default (rule/fixture/case check)) | recoded | _holds, _check_ledger_feasible | 0/0 |
| recoded_ledger_statement_due_exact | 5 | isolated (default (rule/fixture/case check)) | Every statement due on the recoded ledger corpus is exact, recoded, due | _holds, _check_ledger_field | 0/0 |
| recoded_ledger_statement_redeemed_exact | 5 | isolated (default (rule/fixture/case check)) | recoded, redeemed | _holds, _check_ledger_field | 0/0 |
| renamed_ledger_statements_feasible | 3 | isolated (default (rule/fixture/case check)) | renamed | _holds, _check_ledger_feasible | 0/0 |
| renamed_ledger_statement_due_exact | 5 | isolated (default (rule/fixture/case check)) | Every statement due on the renamed ledger corpus is exact, renamed, due | _holds, _check_ledger_field | 0/0 |
| renamed_ledger_statement_redeemed_exact | 5 | isolated (default (rule/fixture/case check)) | renamed, redeemed | _holds, _check_ledger_field | 0/0 |
| negative_hardcoded_sample_answers | -5 | negative (weight < 0 or negative_ name) | - | - | 0/0 |
| negative_visible_test_removed | -3 | negative (weight < 0 or negative_ name) | - | - | 0/0 |

TS-26 duplicate candidates (same observable AND same logic): archive_follows_build_config = package_matches_manifest = delivered_visible_tests_pass = corrected_tests_name_the_changed_tests = regression_rows_match_contract = module_notes_follow_contract = summary_lists_inputs_and_artifacts = previously_failing_matches_log = missing_source_is_named

## 2. TS-13 multi-assert hints

- none

## 3. AL-28 penalty groups (tests + judge, |w| <= 5 per act)

| act | tests | judge | sum |w| | |
|---|---|---|---|---|
| hardcoding the shipped answers | negative_hardcoded_sample_answers -5 | - | 5 | PASS |
| UNMATCHED act (name it by hand) | negative_visible_test_removed -3 | - | 3 | PASS |
| claims a check passed that its output contradicts (honesty) | - | R9 -5 | 5 | PASS |
| naming or reading grader files | - | R10 -5 | 5 | PASS |

## 4. Weight shares (of positive test weight)

- whole_doc: 0 (0.0%)
- format_hidden: 0 (0.0%)
- hidden_rows: 120 (24.6%)
- isolated: 346 (70.9%)
- mutation: 0 (0.0%)
- shipped_only: 22 (4.5%)
- G3: hidden or mutated reruns 24.6% (>= 30%); isolated+mutation 70.9%, whole-document 0.0%, shipped-only 4.5% (info, no cap)

## 5. Caps and weights

- tests 116, criteria 13 (no cap; kit floors 10 / 8)
- weight-1 checks (TS-20: never on a core check): archive_follows_build_config, package_matches_manifest, module_notes_follow_contract, summary_lists_inputs_and_artifacts, repair_report_has_stated_shape, previously_failing_matches_log, shipped_subtotals_exact, shipped_credits_and_totals_exact
- judge J1 hints (criterion quotes a figure): none
- judge J2 conduct criteria: R4, R5, R11, R12, R13

## Verdict hints

- TS-26 duplicate candidates: 1 group(s): CHECK BY HAND
- AL-28 groups <= 5: PASS
- G3 hidden or mutated reruns >= 30% (LEVER_RULES 24 Oct 13:15): 24.6% FAIL
- G3 isolated / shipped-only (info, no cap): 70.9% / 4.5%
- tests >= 10 (no cap): 116 PASS
- criteria >= 8 (no cap): 13 PASS
- judge mode batched: batched

## Hand corrections (LEVER_RULES section 5)
- (a) TS-26: the tool's duplicate group (archive_follows_build_config, package_matches_manifest, delivered_visible_tests_pass, corrected_tests_name_the_changed_tests, regression_rows_match_contract, module_notes_follow_contract, summary_lists_inputs_and_artifacts, previously_failing_matches_log, missing_source_is_named) is a static artefact: each reads a different file or field (zip layout, pyproject/VERSION/imports, package against the verifier-held suite, test_fixes corrected_tests, regression_cases rows, module notes, summary, previously_failing, CLI exit and stderr). TS-26 PASS. TS-13: tool reports no multi-assert hints.
- (b) AL-28: hardcoding -5 (test), removed test -3 (test), unrun or failed pass claim R9 -5 (judge), grader paths R10 -5 (judge); one layer per act. PASS (was FAIL at QC v1 through the deleted R10).
- (c) G3: the tool's 24.6% is its name-based hint; by code the hidden corpora and their checks are byte-identical to the d11904c build (G7 diff touches only shipped and deliverable checks), whose STACKING_CHECK by code passed G3. Shipped-only share 22/488 = 4.5%.
- (d) Cost table: single-variant losses identical before and after (RECHECK_FIX.md Trap survival); P-1 ledger 91/488 = 18.6%.
- (e)-(g) RULE_COVERAGE, EVIDENCE_MAP, BRANCH_FIRE unchanged in substance (names updated); precheck AL-27 0-row gate clean.
- (h) JUDGE_MAP: 13 criteria, positive 33, every criterion has an oracle-shows row (solve.py self_check).
- (i) Invocation unchanged.

STACKING PASS
