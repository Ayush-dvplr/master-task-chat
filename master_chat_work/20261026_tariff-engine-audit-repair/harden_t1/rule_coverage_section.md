
## 78d433c test-hardening round (26 Oct 2026)

Re-measured on the 226-point test file (WORK/rule_mutants.py, 2 shards, raw `harden_t1/mutants_fix.json` (merged shards, M11/M25 re-run after a fix to their patches)). Contract lines refer to the 225-line api_contract.md. Last column: positive checks failed; none fires a negative.

| rule | file:line | mutant | tests failed | score |
|---|---|---|---|---|
| arbiter; visible tests corrected | environment/ci/api_contract.md:3-5,174-176 | M01_keep_visible_asserts | 2 | 0.9735 |
| stdlib only, no network client | environment/ci/api_contract.md:9-11 | M02_socket_import | 1 | 0.9867 |
| VERSION equals manifest version | environment/ci/api_contract.md:12-13 | M03_version_unchanged | 1 | 0.9867 |
| pyproject dependencies empty | environment/ci/api_contract.md:13-15 | M04_dependencies_kept | 1 | 0.9867 |
| build_invoices(data_dir) returns the document | environment/ci/api_contract.md:16-17 | M05_api_rejects_text_path | 11 | 0.5929 |
| render returns JSON text; CLI writes it | environment/ci/api_contract.md:18-20 | M06_render_prefix | 31 | 0.1681 |
| missing input exit 2 and message | environment/ci/api_contract.md:21-24 | M07_missing_exit_1 | 1 | 0.9867 |
| text values trimmed | environment/ci/api_contract.md:28-29 | M08_no_trim | 25 | 0.4735 |
| date ranges include both days | environment/ci/api_contract.md:30-31,80,110 | M09_period_end_excluded | 30 | 0.2345 |
| amounts are JSON strings with two decimals | environment/ci/api_contract.md:32-33 | M10_subtotal_number | 14 | 0.5177 |
| only accepted reads are billed | environment/ci/api_contract.md:37,53 | M11_bill_rejected_reads | 27 | 0.3274 |
| empty active_to stays active | environment/ci/api_contract.md:41-43 | M12_open_window_closed | 32 | 0.1549 |
| active days count both ends | environment/ci/api_contract.md:44,145 | M13_active_days_short | 15 | 0.5044 |
| credit when subtotal is at least commitment | environment/ci/api_contract.md:165 | M14_strictly_above | 8 | 0.8230 |
| line amount half to even | environment/ci/api_contract.md:50-51,159-160 | M15_half_up | 21 | 0.5354 |
| month is a calendar month, not the billing period | environment/ci/api_contract.md:52,142-143 | M16_month_is_period | 14 | 0.6504 |
| period quantity is the sum of accepted reads | environment/ci/api_contract.md:53 | M17_quantity_max | 29 | 0.1947 |
| plan named by billing_periods row | environment/ci/api_contract.md:54 | M18_first_plan | 33 | 0.1062 |
| tiers numbered from 1 | environment/ci/api_contract.md:55 | M19_tiers_from_zero | 15 | 0.5044 |
| quantity is a JSON integer; strings malformed | environment/ci/api_contract.md:64,105-106 | M20_quoted_integer_coerced | 24 | 0.4867 |
| true, false and negative integers malformed | environment/ci/api_contract.md:64,105-106 | M21_bool_negative_accepted | 26 | 0.4071 |
| number with decimal point or exponent malformed | environment/ci/api_contract.md:64,105-106 | M22_integral_float_accepted | 25 | 0.4735 |
| first applicable exception, malformed first | environment/ci/api_contract.md:103-106 | M23_unknown_before_malformed | 1 | 0.9867 |
| inactive_meter before outside_period | environment/ci/api_contract.md:103,109-110 | M24_outside_before_inactive | 1 | 0.9867 |
| outside_period reads rejected | environment/ci/api_contract.md:110 | M25_outside_billed | 3 | 0.9292 |
| duplicate only of an earlier accepted read | environment/ci/api_contract.md:111-112 | M26_duplicate_of_rejected | 24 | 0.4867 |
| exceptions sorted by read_id | environment/ci/api_contract.md:121-123 | M27_exceptions_by_account | 6 | 0.7699 |
| one invoice per row, sorted by account | environment/ci/api_contract.md:127-128 | M28_invoices_reversed | 32 | 0.1195 |
| every meter of the account is billed | environment/ci/api_contract.md:131-132 | M29_skip_unused_meters | 34 | 0.0929 |
| tier up to and including up_to | environment/ci/api_contract.md:134-137 | M30_tier_cap_exclusive | 11 | 0.7655 |
| tier with no units has no line | environment/ci/api_contract.md:137 | M31_zero_unit_tier_line | 11 | 0.7301 |
| exact energy value is units x rate | environment/ci/api_contract.md:140 | M32_rate_rounded_first | 24 | 0.4867 |
| standing_charge x active days / days in the month | environment/ci/api_contract.md:142-143 | M33_no_proration | 28 | 0.3053 |
| no standing line without an active day | environment/ci/api_contract.md:145-146 | M34_zero_day_standing | 8 | 0.8230 |
| energy lines by tier, then standing | environment/ci/api_contract.md:148-149 | M35_standing_first | 10 | 0.6062 |
| amounts from decimal values as written | environment/ci/api_contract.md:151-152 | M36_float_values | 21 | 0.5354 |
| subtotal is the sum of the line amounts | environment/ci/api_contract.md:160-161 | M37_subtotal_energy_only | 23 | 0.3363 |
| credit base: accepted, rated, prorated lines | environment/ci/api_contract.md:163-164 | M38_credit_base_energy_only | 12 | 0.7035 |
| total rounded, credit = subtotal minus total | environment/ci/api_contract.md:165-167 | M39_credit_rounded | 7 | 0.8451 |
| document keys invoices and exceptions | environment/ci/api_contract.md:169-170 | M40_document_key | 33 | 0.1239 |
| archive follows build_config | environment/ci/api_contract.md:180-186 | M41_zip_deflated | 1 | 0.9867 |
| repair-report has a passed check | environment/ci/api_contract.md:191-194 | M42_no_check_passed | 1 | 0.9956 |
| lint_errors counts severity error | environment/ci/api_contract.md:198-200 | M43_lint_all_severities | 1 | 0.9956 |
| parser contract_terms | environment/ci/api_contract.md:202-204 | M44_contract_terms_short | 1 | 0.9956 |
| report deterministic is a bool | environment/ci/api_contract.md:204-205 | M45_deterministic_text | 1 | 0.9956 |
| corrected_tests lists changed tests | environment/ci/api_contract.md:206-207 | M46_corrected_tests_short | 1 | 0.9867 |
| previously_failing includes FAIL and ERROR | environment/ci/api_contract.md:208-210 | M47_failing_fail_only | 1 | 0.9956 |
| regression expected is customer_claim | environment/ci/api_contract.md:212-216 | M48_expected_disputed | 1 | 0.9867 |
| all_regressions_passed | environment/ci/api_contract.md:210-211 | M49_any_regression | 1 | 0.9867 |
| summary artifacts and count | environment/ci/api_contract.md:222-225 | M50_artifact_count | 1 | 0.9956 |
| summary inputs_used every /app/ci file | environment/ci/api_contract.md:222-224 | M51_inputs_partial | 1 | 0.9956 |
| allowance and energy share | environment/ci/api_contract.md:45,47-51 | M52_allowance_ignored | 16 | 0.6372 |
| unshared allowance shared again | environment/ci/api_contract.md:151-154 | M53_share_one_pass | 12 | 0.7345 |
| tiers by account position | environment/ci/api_contract.md:38-40,134-136 | M54_tiers_per_meter | 9 | 0.8009 |
| energy share only on energy lines | environment/ci/api_contract.md:47-51,159-160 | M55_allowance_on_standing | 19 | 0.5708 |
| never more than a line's exact value | environment/ci/api_contract.md:47-49,152-153 | M56_share_exceeds_line | 16 | 0.6372 |
| each calendar month has its own days | environment/ci/api_contract.md:52,142-143 | M57_month_of_start | 9 | 0.8009 |
| L11 plan value that is no key: first entry | environment/ci/rate_card.json:7-10 | M58_code_defaults_first | 8 | 0.8230 |
| L11 plan value that is no key: last entry | environment/ci/rate_card.json:7-10 | M59_code_defaults_last | 8 | 0.8230 |
| L11 codes compared untrimmed (padded code) | environment/ci/rate_card.json:50-53;environment/ci/api_contract.md:28-29 | M60_codes_untrimmed | 8 | 0.8230 |
| invoice plan is the row's plan value | environment/ci/api_contract.md:130 | M62_output_plan_key | 2 | 0.9558 |
| estimated field, duplicate per estimated, replaced_estimate | environment/ci/api_contract.md:65,111-119 | M63_estimated_ignored | 2 | 0.9071 |
| estimate replaced wherever the actual read stands | environment/ci/api_contract.md:113-115 | M64_estimate_file_order | 2 | 0.9071 |
| standing charge of a day from standing_changes | environment/ci/api_contract.md:92-99,142-143 | M65_changes_ignored | 2 | 0.9071 |
| entry with the latest from on or before the day | environment/ci/api_contract.md:94-96 | M66_changes_list_order | 2 | 0.9071 |
| one or more billing rows, each its own invoice | environment/ci/api_contract.md:75-85,110,127-128 | M67_last_billing_row | 3 | 0.8938 |
| invoices sorted by account then start | environment/ci/api_contract.md:127-128 | M68_rows_file_order | 3 | 0.8938 |
| unused allowance added to the next invoice | environment/ci/api_contract.md:154-159 | M69_allowance_not_carried | 2 | 0.9381 |
| one or more accounts rows per meter | environment/ci/api_contract.md:41-43,67-73 | M70_last_accounts_row | 2 | 0.9071 |

Rows: 69; rows with 0 tests failed: none.
