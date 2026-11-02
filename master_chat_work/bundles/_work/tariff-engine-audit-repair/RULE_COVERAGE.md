# RULE_COVERAGE (harden round 2, Phase 2, 7f1d771)

Re-measured 15:07-15:12 IST 25 Oct on the round-2 test file (157 positive points): each mutant is a patched copy of solution/solve.py run on the shipped inputs, then every check run (WORK/rule_mutants.py, 4 local shards; raw results harden_r2_p2_7f1d771/mutants2/shard0-3.json). Last column is the number of positive checks the mutant fails; no mutant fires a negative. Input-shape statements of api_contract.md lines 58-79 (bounds on periods, decimals, allowances, tiers) are enforced by bounds asserts inside the corpus generator of tests/test_output.py, not by mutants. Contract line numbers refer to the 194-line api_contract.md as of round 2 (file:line column re-mapped this round; earlier rows carried build-era numbers).

| rule | file:line | mutant | tests failed |
|---|---|---|---|
| arbiter; visible tests corrected | environment/ci/api_contract.md:3-5,143-145 | M01_keep_visible_asserts | 2 |
| stdlib only, no network client | environment/ci/api_contract.md:9-11 | M02_socket_import | 1 |
| VERSION equals manifest version | environment/ci/api_contract.md:12-13 | M03_version_unchanged | 1 |
| pyproject dependencies empty | environment/ci/api_contract.md:13-15 | M04_dependencies_kept | 1 |
| build_invoices(data_dir) returns the document | environment/ci/api_contract.md:16-17 | M05_api_rejects_text_path | 5 |
| render returns JSON text; CLI writes it | environment/ci/api_contract.md:18-20 | M06_render_prefix | 25 |
| missing input exit 2 and message | environment/ci/api_contract.md:21-24 | M07_missing_exit_1 | 1 |
| text values trimmed | environment/ci/api_contract.md:28-29 | M08_no_trim | 25 |
| date ranges include both days | environment/ci/api_contract.md:30-31,90 | M09_period_end_excluded | 25 |
| amounts are JSON strings with two decimals | environment/ci/api_contract.md:32-33 | M10_subtotal_number | 8 |
| only accepted reads are billed | environment/ci/api_contract.md:37,52 | M11_bill_rejected_reads | 24 |
| empty active_to stays active | environment/ci/api_contract.md:41-42 | M12_open_window_closed | 26 |
| active days count both ends | environment/ci/api_contract.md:43 | M13_active_days_short | 9 |
| credit when subtotal is at least commitment | environment/ci/api_contract.md:134-136 | M14_strictly_above | 8 |
| line amount half to even | environment/ci/api_contract.md:49-50,128-129 | M15_half_up | 21 |
| month is a calendar month, not the billing period | environment/ci/api_contract.md:51,115-117 | M16_month_is_period | 12 |
| period quantity is the sum of accepted reads | environment/ci/api_contract.md:52 | M17_quantity_max | 23 |
| plan named by billing_periods row | environment/ci/api_contract.md:53,74 | M18_first_plan | 27 |
| tiers numbered from 1 | environment/ci/api_contract.md:54,111 | M19_tiers_from_zero | 9 |
| quantity is a JSON integer; strings malformed | environment/ci/api_contract.md:63,85-86 | M20_quoted_integer_coerced | 24 |
| true, false and negative integers malformed | environment/ci/api_contract.md:63,85-86 | M21_bool_negative_accepted | 25 |
| number with decimal point or exponent malformed | environment/ci/api_contract.md:63,85-86 | M22_integral_float_accepted | 25 |
| first applicable exception, malformed first | environment/ci/api_contract.md:83,85-88 | M23_unknown_before_malformed | 1 |
| inactive_meter before outside_period | environment/ci/api_contract.md:89-90 | M24_outside_before_inactive | 1 |
| outside_period reads rejected | environment/ci/api_contract.md:90 | M25_outside_billed | 25 |
| duplicate only of an earlier accepted read | environment/ci/api_contract.md:91-92 | M26_duplicate_of_rejected | 24 |
| exceptions sorted by read_id | environment/ci/api_contract.md:94-96 | M27_exceptions_by_account | 2 |
| one invoice per row, sorted by account | environment/ci/api_contract.md:100-101 | M28_invoices_reversed | 26 |
| every meter of the account is billed | environment/ci/api_contract.md:103-104 | M29_skip_unused_meters | 21 |
| tier up to and including up_to | environment/ci/api_contract.md:107-110 | M30_tier_cap_exclusive | 11 |
| tier with no units has no line | environment/ci/api_contract.md:110-111 | M31_zero_unit_tier_line | 9 |
| exact energy value is units x rate | environment/ci/api_contract.md:112-113 | M32_rate_rounded_first | 24 |
| standing_charge x active days / days in the month | environment/ci/api_contract.md:115-117 | M33_no_proration | 25 |
| no standing line without an active day | environment/ci/api_contract.md:119 | M34_zero_day_standing | 8 |
| energy lines by tier, then standing | environment/ci/api_contract.md:121-122 | M35_standing_first | 4 |
| amounts from decimal values as written | environment/ci/api_contract.md:124-125 | M36_float_values | 21 |
| subtotal is the sum of the line amounts | environment/ci/api_contract.md:129-130 | M37_subtotal_energy_only | 17 |
| credit base: accepted, rated, prorated lines | environment/ci/api_contract.md:132-134 | M38_credit_base_energy_only | 9 |
| total rounded, credit = subtotal minus total | environment/ci/api_contract.md:134-136 | M39_credit_rounded | 7 |
| document keys invoices and exceptions | environment/ci/api_contract.md:138-139 | M40_document_key | 27 |
| archive follows build_config | environment/ci/api_contract.md:149-155 | M41_zip_deflated | 1 |
| repair-report has a passed check | environment/ci/api_contract.md:160-163 | M42_no_check_passed | 1 |
| lint_errors counts severity error | environment/ci/api_contract.md:167-169 | M43_lint_all_severities | 1 |
| parser contract_terms | environment/ci/api_contract.md:171-173 | M44_contract_terms_short | 1 |
| report deterministic is a bool | environment/ci/api_contract.md:173-174 | M45_deterministic_text | 1 |
| corrected_tests lists changed tests | environment/ci/api_contract.md:175-176 | M46_corrected_tests_short | 1 |
| previously_failing includes FAIL and ERROR | environment/ci/api_contract.md:177-179 | M47_failing_fail_only | 1 |
| regression expected is customer_claim | environment/ci/api_contract.md:181-185 | M48_expected_disputed | 1 |
| all_regressions_passed | environment/ci/api_contract.md:179-180 | M49_any_regression | 1 |
| summary artifacts and count | environment/ci/api_contract.md:191-194 | M50_artifact_count | 1 |
| summary inputs_used every /app/ci file | environment/ci/api_contract.md:191-192 | M51_inputs_partial | 1 |
| allowance and energy share | environment/ci/api_contract.md:44,46-50,69-72 | M52_allowance_ignored | 14 |
| unshared allowance shared again | environment/ci/api_contract.md:124-128 | M53_share_one_pass | 12 |
| tiers by account position | environment/ci/api_contract.md:38-40,107-110 | M54_tiers_per_meter | 9 |
| energy share only on energy lines | environment/ci/api_contract.md:46-50,128 | M55_allowance_on_standing | 17 |
| never more than a line's exact value | environment/ci/api_contract.md:46-48,126-127 | M56_share_exceeds_line | 14 |
| each calendar month has its own days | environment/ci/api_contract.md:51,115-117 | M57_month_of_start | 9 |
| L11 plan value that is no key: first entry | environment/ci/rate_card.json:7-10 (codes), environment/ci/billing_periods.csv | M58_code_defaults_first | 8 |
| L11 plan value that is no key: last entry | environment/ci/rate_card.json:7-10 (codes), environment/ci/billing_periods.csv | M59_code_defaults_last | 8 |
| L11 codes compared after trimming (padded code) | environment/ci/rate_card.json:50-53, environment/ci/api_contract.md:28-29 | M60_codes_untrimmed | 8 |
| invoice `plan` is the row's `plan` value | environment/ci/api_contract.md:101-103 | M62_output_plan_key | 2 |
Uncovered rules: 0 of 61 (61 of 61 mutants killed, none fires a negative; M61 codes-casefold dropped as an equivalent mutant: no graded corpus holds a lower-case code, see WORK/UNIQUENESS.md R16).

New-lever rows: M52_allowance_ignored, M53_share_one_pass, M55_allowance_on_standing, M56_share_exceeds_line (N1); M16_month_is_period, M57_month_of_start (N2); M54_tiers_per_meter (N3); M58_code_defaults_first, M59_code_defaults_last, M60_codes_untrimmed, M62_output_plan_key, M18_first_plan (L11; each fails shipped_standing_lines_exact, shipped_energy_lines_exact, shipped_subtotals_exact, shipped_credits_and_totals_exact and the six recoded/renamed checks, M62 the two subtotals/heads checks).

## Lessons for the master
A rule mutant run in parallel with a variant run once dropped the oracle to 0.8976 (three shipped checks) and scored 1.0 alone | no change: re-measure any surprising oracle score alone before acting


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

## Round 2 rows (15b380e); mutant = measure_variants variant on solve.py
| rule | file:line | mutant | tests failed |
|---|---|---|---|
| U1 revision choice | environment/ci/api_contract.md:63-70 | U1_off | 5 |
| U1 verdict no fit / several | environment/ci/api_contract.md:65-67 | U1_first_fit | 3 |
| U1 revision used | environment/ci/api_contract.md:63-70 | U1_first_revision | 5 |
| D1 arrears | environment/ci/api_contract.md:191-195 | D1_off | 5 |
| payments.csv no row = no paid amount | environment/ci/api_contract.md:119-123 | D1_missing_is_zero | 15 |
| D2 billed quantity | environment/ci/api_contract.md:53-59 | D2_off | 5 |
| D2 previous by `day` | environment/ci/api_contract.md:53-59 | D2_file_order | 5 |
| D2 previous of the account and meter, any invoice | environment/ci/api_contract.md:53-59 | D2_per_row | 1 |
Rows M01-M70 were measured in round 1 (69/69 killed, mutants_fix.json); this round's solve.py refactor left 14 of their patch targets stale, so they were not re-run; the old checks and their reference are byte-unchanged for non-lever accounts (snapshot compare).

## Round 3 rows (fc1fb76); mutant = measure_variants variant on solve.py
| rule | file:line | mutant | tests failed |
|---|---|---|---|
| statements command and document | environment/ci/api_contract.md:25-28, :211-215 | S_off | 22 |
| redeemed = largest sum not above balance | environment/ci/api_contract.md:219-221 | S_greedy | 15 |
| 10 s limit | environment/ci/api_contract.md:25-28 | S_setdp / S_naive | 21 |
| tie: first id list | environment/ci/api_contract.md:221-223 | S_tie_any | 8 |
| ids in plain string order | environment/ci/api_contract.md:219-220 | S_numeric_ids | 8 |
| balance less paid amounts | environment/ci/api_contract.md:217-218 | S_no_paid | 21 |
| balance 0.00 below zero | environment/ci/api_contract.md:217-218 | S_no_clamp | 14 |
Rows with 0 tests failed: none.
