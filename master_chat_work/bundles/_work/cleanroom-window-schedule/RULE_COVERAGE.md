# RULE_COVERAGE

Each mutant is the oracle `solution/solve.py` with one rule dropped (WORK/rule_mut/<id>.py, lever rows WORK/mutants/<name>.py), run through every check of `tests/test_output.py` by WORK/run_tests.py. Last cell = number of checks the mutant fails.

| rule | file:line | mutant | tests failed |
|---|---|---|---|
| missing input file: nonzero exit, stderr names it | contract.md:11-12 | missing_input_exit | 1 |
| nights run in audit.toml date order | contract.md:42 | night_order_by_id | 24 |
| E_DUP_JOB | contract.md:47 | dup_job_unchecked | 6 |
| E_BAD_WINDOW: absent window | contract.md:48 | absent_window_unchecked | 6 |
| E_BAD_WINDOW: 0 <= start < end <= 1440 | contract.md:48-49 | window_bounds_unchecked | 6 |
| E_UNKNOWN_RESOURCE: family | contract.md:50 | unknown_family_unchecked | 5 |
| E_UNKNOWN_RESOURCE: client | contract.md:50-51 | unknown_client_unchecked | 12 |
| E_BAD_FEE | contract.md:52-53 | fee_table_unchecked | 12 |
| first applicable code in stated order | contract.md:44-45 | code_priority_swapped | 4 |
| rejection message text | contract.md:55 | message_format | 5 |
| rejected night leaves every bay's family as it was | contract.md:55-56 | rejected_resets_families | 22 |
| job runs on a qualified bay | contract.md:61-62 | qualification_ignored | 12 |
| half-open windows, touching jobs share no minute | contract.md:62-64 | touching_forbidden | 15 |
| every mandatory job runs | contract.md:64 | mandatory_optional | 23 |
| changeover pays fee of ordered pair | contract.md:75-76 | fee_not_charged | 24 |
| bay's earlier job ends by crew window start | contract.md:78-79 | bay_busy_in_window | 23 |
| no crew window before minute 0 | contract.md:79 | window_before_zero | 23 |
| bay charge = minute_rate x (end - start) | contract.md:85 | bay_charge_inclusive | 20 |
| job net = value - bay charge - fee | contract.md:85-86 | job_net_without_fee | 9 |
| plan items ordered by start then job id | contract.md:110-111 | plan_lines_by_job_id | 5 |
| crew windows ordered by start | contract.md:120-121 | crew_windows_by_job_id | 5 |
| families_after at night end | contract.md:121-122 | families_after_dropped | 5 |
| crew_load_high flag | contract.md:123-124 | crew_flag_dropped | 5 |
| low_margin flag | contract.md:124 | margin_flag_dropped | 2 |
| flags alphabetically sorted | contract.md:122-123 | flags_unsorted | 2 |
| region of the client's site | contract.md:102 | region_not_by_site | 5 |
| segment of the client | contract.md:102 | segment_not_by_client | 5 |
| rollups list every accepted night | contract.md:137-138 | rollup_skips_empty_nights | 4 |
| rollup totals | contract.md:139-140 | rollup_totals_partial | 9 |
| summary totals | contract.md:113-114 | summary_totals_partial | 5 |
| rejected night: empty plan, zero figures | contract.md:112-113 | rejected_night_omitted | 11 |
| program reads DATA_DIR, writes OUT_DIR | instruction.md:3 | data_dir_ignored | 28 |
| output paths region_North.json and the rest (case) | instruction.md:5-11 | output_paths_lowercase | 23 |
| LV-CW-1 maximum net plan | contract.md:89-91 | greedy (mutants/greedy.py) | 21 |
| LV-CW-1 maximum net plan | contract.md:89-91 | greedy_ls | 20 |
| coupling: every figure from the maximum-net-value plan | contract.md:97 | greedy_ls | 20 |
| LV-CW-2 initial_family until first job | contract.md:68 | no_initial | 19 |
| LV-CW-2 previous family = latest-starting earlier job (across gaps) | contract.md:70-71 | touching_only | 23 |
| LV-CW-2 family held at night start (carry across nights) | contract.md:71-73 | reset_nightly | 23 |
| LV-CW-3 single crew, windows never share a minute | contract.md:79-80 | no_crew | 23 |
| LV-CW-3 crew window [start - crew_minutes, start) ends at job start | contract.md:77-79 | naive_collapse | 23 |
| LV-CW-3 qualification and crew per bay (shared state) | contract.md:61-62,79-80 | flow_relax | 23 |
| LV-CW-3 plans per night across all bays | contract.md:61-64,89-91 | lane_by_lane | 23 |

Notes

- output_paths_lowercase passes every check on macOS (case-insensitive APFS); it was run in Linux Docker (python:3.12-slim, uid 1000) where it scores 17/98 and fails 23 checks (shipped regions, every hidden summary, regions and relocated rerun). That Linux figure is the one recorded.
- Tie order (contract.md:91-95) has no row: every shipped and hidden night has exactly one maximum-net plan (counted at build time, WORK/datagen.py and WORK/hidden_build.py assert count == 1), so a tie mutant changes no output. The rule is kept as stated by IDEA G-3. Open point for the master: G-3 and G11 conflict on this rule.
- Stated limit (contract.md:19-20, 2 s per night) is covered by raw_exact and raw_tuned in COST_TABLE.md.

Failed checks per mutant

- missing_input_exit: missing_input_is_named
- night_order_by_id: shipped_summary_matches, shipped_policy_audit_matches, shipped_data_quality_matches, shipped_regions_match, shipped_segments_match, dense_book_plans_legal, dense_book_plans_optimal, dense_book_summary_matches, dense_book_policy_audit_matches, dense_book_regions_match, dense_book_segments_match, carry_book_plans_legal, carry_book_plans_optimal, carry_book_summary_matches, carry_book_policy_audit_matches, carry_book_regions_match, carry_book_segments_match, wide_book_plans_legal, wide_book_plans_optimal, wide_book_summary_matches, wide_book_policy_audit_matches, wide_book_regions_match, wide_book_segments_match, relocated_reordered_reruns_match
- dup_job_unchecked: shipped_summary_matches, shipped_policy_audit_matches, shipped_data_quality_matches, shipped_regions_match, shipped_segments_match, dense_book_data_quality_matches
- absent_window_unchecked: shipped_summary_matches, shipped_policy_audit_matches, shipped_data_quality_matches, shipped_regions_match, shipped_segments_match, wide_book_data_quality_matches
- window_bounds_unchecked: shipped_summary_matches, shipped_policy_audit_matches, shipped_data_quality_matches, shipped_regions_match, shipped_segments_match, carry_book_data_quality_matches
- unknown_family_unchecked: shipped_summary_matches, shipped_policy_audit_matches, shipped_data_quality_matches, shipped_regions_match, shipped_segments_match
- unknown_client_unchecked: shipped_summary_matches, shipped_policy_audit_matches, shipped_data_quality_matches, shipped_regions_match, shipped_segments_match, wide_book_plans_legal, wide_book_plans_optimal, wide_book_summary_matches, wide_book_policy_audit_matches, wide_book_data_quality_matches, wide_book_regions_match, wide_book_segments_match
- fee_table_unchecked: shipped_summary_matches, shipped_policy_audit_matches, shipped_data_quality_matches, shipped_regions_match, shipped_segments_match, carry_book_plans_legal, carry_book_plans_optimal, carry_book_summary_matches, carry_book_policy_audit_matches, carry_book_data_quality_matches, carry_book_regions_match, carry_book_segments_match
- code_priority_swapped: shipped_data_quality_matches, carry_book_data_quality_matches, wide_book_data_quality_matches, relocated_reordered_reruns_match
- message_format: shipped_data_quality_matches, dense_book_data_quality_matches, carry_book_data_quality_matches, wide_book_data_quality_matches, relocated_reordered_reruns_match
- rejected_resets_families: shipped_summary_matches, shipped_policy_audit_matches, shipped_regions_match, shipped_segments_match, dense_book_plans_legal, dense_book_plans_optimal, dense_book_summary_matches, dense_book_policy_audit_matches, dense_book_regions_match, dense_book_segments_match, carry_book_plans_legal, carry_book_summary_matches, carry_book_policy_audit_matches, carry_book_regions_match, carry_book_segments_match, wide_book_plans_legal, wide_book_plans_optimal, wide_book_summary_matches, wide_book_policy_audit_matches, wide_book_regions_match, wide_book_segments_match, relocated_reordered_reruns_match
- qualification_ignored: shipped_summary_matches, shipped_policy_audit_matches, shipped_data_quality_matches, shipped_regions_match, shipped_segments_match, carry_book_plans_legal, carry_book_plans_optimal, carry_book_summary_matches, carry_book_policy_audit_matches, carry_book_regions_match, carry_book_segments_match, relocated_reordered_reruns_match
- touching_forbidden: shipped_summary_matches, shipped_policy_audit_matches, shipped_regions_match, shipped_segments_match, dense_book_plans_optimal, dense_book_summary_matches, dense_book_policy_audit_matches, dense_book_regions_match, dense_book_segments_match, carry_book_plans_optimal, carry_book_summary_matches, carry_book_policy_audit_matches, carry_book_regions_match, carry_book_segments_match, relocated_reordered_reruns_match
- mandatory_optional: shipped_summary_matches, shipped_policy_audit_matches, shipped_regions_match, shipped_segments_match, dense_book_plans_legal, dense_book_plans_optimal, dense_book_summary_matches, dense_book_policy_audit_matches, dense_book_regions_match, dense_book_segments_match, carry_book_plans_legal, carry_book_plans_optimal, carry_book_summary_matches, carry_book_policy_audit_matches, carry_book_regions_match, carry_book_segments_match, wide_book_plans_legal, wide_book_plans_optimal, wide_book_summary_matches, wide_book_policy_audit_matches, wide_book_regions_match, wide_book_segments_match, relocated_reordered_reruns_match
- fee_not_charged: shipped_summary_matches, shipped_policy_audit_matches, shipped_data_quality_matches, shipped_regions_match, shipped_segments_match, dense_book_plans_legal, dense_book_plans_optimal, dense_book_summary_matches, dense_book_policy_audit_matches, dense_book_regions_match, dense_book_segments_match, carry_book_plans_legal, carry_book_plans_optimal, carry_book_summary_matches, carry_book_policy_audit_matches, carry_book_regions_match, carry_book_segments_match, wide_book_plans_legal, wide_book_plans_optimal, wide_book_summary_matches, wide_book_policy_audit_matches, wide_book_regions_match, wide_book_segments_match, relocated_reordered_reruns_match
- bay_busy_in_window: shipped_summary_matches, shipped_policy_audit_matches, shipped_regions_match, shipped_segments_match, dense_book_plans_legal, dense_book_plans_optimal, dense_book_summary_matches, dense_book_policy_audit_matches, dense_book_regions_match, dense_book_segments_match, carry_book_plans_legal, carry_book_plans_optimal, carry_book_summary_matches, carry_book_policy_audit_matches, carry_book_regions_match, carry_book_segments_match, wide_book_plans_legal, wide_book_plans_optimal, wide_book_summary_matches, wide_book_policy_audit_matches, wide_book_regions_match, wide_book_segments_match, relocated_reordered_reruns_match
- window_before_zero: shipped_summary_matches, shipped_policy_audit_matches, shipped_regions_match, shipped_segments_match, dense_book_plans_legal, dense_book_plans_optimal, dense_book_summary_matches, dense_book_policy_audit_matches, dense_book_regions_match, dense_book_segments_match, carry_book_plans_legal, carry_book_plans_optimal, carry_book_summary_matches, carry_book_policy_audit_matches, carry_book_regions_match, carry_book_segments_match, wide_book_plans_legal, wide_book_plans_optimal, wide_book_summary_matches, wide_book_policy_audit_matches, wide_book_regions_match, wide_book_segments_match, relocated_reordered_reruns_match
- bay_charge_inclusive: shipped_summary_matches, shipped_policy_audit_matches, shipped_regions_match, shipped_segments_match, dense_book_plans_legal, dense_book_summary_matches, dense_book_regions_match, dense_book_segments_match, carry_book_plans_legal, carry_book_plans_optimal, carry_book_summary_matches, carry_book_policy_audit_matches, carry_book_regions_match, carry_book_segments_match, wide_book_plans_legal, wide_book_plans_optimal, wide_book_summary_matches, wide_book_regions_match, wide_book_segments_match, relocated_reordered_reruns_match
- job_net_without_fee: shipped_regions_match, shipped_segments_match, dense_book_regions_match, dense_book_segments_match, carry_book_regions_match, carry_book_segments_match, wide_book_regions_match, wide_book_segments_match, relocated_reordered_reruns_match
- plan_lines_by_job_id: shipped_summary_matches, dense_book_summary_matches, carry_book_summary_matches, wide_book_summary_matches, relocated_reordered_reruns_match
- crew_windows_by_job_id: shipped_policy_audit_matches, dense_book_policy_audit_matches, carry_book_policy_audit_matches, wide_book_policy_audit_matches, relocated_reordered_reruns_match
- families_after_dropped: shipped_policy_audit_matches, dense_book_policy_audit_matches, carry_book_policy_audit_matches, wide_book_policy_audit_matches, relocated_reordered_reruns_match
- crew_flag_dropped: shipped_policy_audit_matches, dense_book_policy_audit_matches, carry_book_policy_audit_matches, wide_book_policy_audit_matches, relocated_reordered_reruns_match
- margin_flag_dropped: shipped_policy_audit_matches, relocated_reordered_reruns_match
- flags_unsorted: shipped_policy_audit_matches, relocated_reordered_reruns_match
- region_not_by_site: shipped_regions_match, dense_book_regions_match, carry_book_regions_match, wide_book_regions_match, relocated_reordered_reruns_match
- segment_not_by_client: shipped_segments_match, dense_book_segments_match, carry_book_segments_match, wide_book_segments_match, relocated_reordered_reruns_match
- rollup_skips_empty_nights: shipped_regions_match, shipped_segments_match, carry_book_regions_match, relocated_reordered_reruns_match
- rollup_totals_partial: shipped_regions_match, shipped_segments_match, dense_book_regions_match, dense_book_segments_match, carry_book_regions_match, carry_book_segments_match, wide_book_regions_match, wide_book_segments_match, relocated_reordered_reruns_match
- summary_totals_partial: shipped_summary_matches, dense_book_summary_matches, carry_book_summary_matches, wide_book_summary_matches, relocated_reordered_reruns_match
- rejected_night_omitted: shipped_summary_matches, dense_book_plans_legal, dense_book_plans_optimal, dense_book_summary_matches, carry_book_plans_legal, carry_book_plans_optimal, carry_book_summary_matches, wide_book_plans_legal, wide_book_plans_optimal, wide_book_summary_matches, relocated_reordered_reruns_match
- data_dir_ignored: shipped_summary_matches, shipped_policy_audit_matches, shipped_data_quality_matches, shipped_regions_match, shipped_segments_match, dense_book_plans_legal, dense_book_plans_optimal, dense_book_summary_matches, dense_book_policy_audit_matches, dense_book_data_quality_matches, dense_book_regions_match, dense_book_segments_match, carry_book_plans_legal, carry_book_plans_optimal, carry_book_summary_matches, carry_book_policy_audit_matches, carry_book_data_quality_matches, carry_book_regions_match, carry_book_segments_match, wide_book_plans_legal, wide_book_plans_optimal, wide_book_summary_matches, wide_book_policy_audit_matches, wide_book_data_quality_matches, wide_book_regions_match, wide_book_segments_match, missing_input_is_named, relocated_reordered_reruns_match
- greedy (mutants/greedy.py): shipped_summary_matches, shipped_policy_audit_matches, shipped_regions_match, shipped_segments_match, dense_book_plans_legal, dense_book_plans_optimal, dense_book_summary_matches, dense_book_policy_audit_matches, dense_book_regions_match, dense_book_segments_match, carry_book_plans_optimal, carry_book_summary_matches, carry_book_policy_audit_matches, carry_book_regions_match, carry_book_segments_match, wide_book_plans_optimal, wide_book_summary_matches, wide_book_policy_audit_matches, wide_book_regions_match, wide_book_segments_match, relocated_reordered_reruns_match
- greedy_ls: shipped_summary_matches, shipped_policy_audit_matches, shipped_regions_match, shipped_segments_match, dense_book_plans_optimal, dense_book_summary_matches, dense_book_policy_audit_matches, dense_book_regions_match, dense_book_segments_match, carry_book_plans_optimal, carry_book_summary_matches, carry_book_policy_audit_matches, carry_book_regions_match, carry_book_segments_match, wide_book_plans_optimal, wide_book_summary_matches, wide_book_policy_audit_matches, wide_book_regions_match, wide_book_segments_match, relocated_reordered_reruns_match
- no_initial: dense_book_plans_legal, dense_book_plans_optimal, dense_book_summary_matches, dense_book_policy_audit_matches, dense_book_regions_match, dense_book_segments_match, carry_book_plans_legal, carry_book_plans_optimal, carry_book_summary_matches, carry_book_policy_audit_matches, carry_book_regions_match, carry_book_segments_match, wide_book_plans_legal, wide_book_plans_optimal, wide_book_summary_matches, wide_book_policy_audit_matches, wide_book_regions_match, wide_book_segments_match, relocated_reordered_reruns_match
- touching_only: shipped_summary_matches, shipped_policy_audit_matches, shipped_regions_match, shipped_segments_match, dense_book_plans_legal, dense_book_plans_optimal, dense_book_summary_matches, dense_book_policy_audit_matches, dense_book_regions_match, dense_book_segments_match, carry_book_plans_legal, carry_book_plans_optimal, carry_book_summary_matches, carry_book_policy_audit_matches, carry_book_regions_match, carry_book_segments_match, wide_book_plans_legal, wide_book_plans_optimal, wide_book_summary_matches, wide_book_policy_audit_matches, wide_book_regions_match, wide_book_segments_match, relocated_reordered_reruns_match
- reset_nightly: shipped_summary_matches, shipped_policy_audit_matches, shipped_regions_match, shipped_segments_match, dense_book_plans_legal, dense_book_plans_optimal, dense_book_summary_matches, dense_book_policy_audit_matches, dense_book_regions_match, dense_book_segments_match, carry_book_plans_legal, carry_book_plans_optimal, carry_book_summary_matches, carry_book_policy_audit_matches, carry_book_regions_match, carry_book_segments_match, wide_book_plans_legal, wide_book_plans_optimal, wide_book_summary_matches, wide_book_policy_audit_matches, wide_book_regions_match, wide_book_segments_match, relocated_reordered_reruns_match
- no_crew: shipped_summary_matches, shipped_policy_audit_matches, shipped_regions_match, shipped_segments_match, dense_book_plans_legal, dense_book_plans_optimal, dense_book_summary_matches, dense_book_policy_audit_matches, dense_book_regions_match, dense_book_segments_match, carry_book_plans_legal, carry_book_plans_optimal, carry_book_summary_matches, carry_book_policy_audit_matches, carry_book_regions_match, carry_book_segments_match, wide_book_plans_legal, wide_book_plans_optimal, wide_book_summary_matches, wide_book_policy_audit_matches, wide_book_regions_match, wide_book_segments_match, relocated_reordered_reruns_match
- naive_collapse: shipped_summary_matches, shipped_policy_audit_matches, shipped_regions_match, shipped_segments_match, dense_book_plans_legal, dense_book_plans_optimal, dense_book_summary_matches, dense_book_policy_audit_matches, dense_book_regions_match, dense_book_segments_match, carry_book_plans_legal, carry_book_plans_optimal, carry_book_summary_matches, carry_book_policy_audit_matches, carry_book_regions_match, carry_book_segments_match, wide_book_plans_legal, wide_book_plans_optimal, wide_book_summary_matches, wide_book_policy_audit_matches, wide_book_regions_match, wide_book_segments_match, relocated_reordered_reruns_match
- flow_relax: shipped_summary_matches, shipped_policy_audit_matches, shipped_regions_match, shipped_segments_match, dense_book_plans_legal, dense_book_plans_optimal, dense_book_summary_matches, dense_book_policy_audit_matches, dense_book_regions_match, dense_book_segments_match, carry_book_plans_legal, carry_book_plans_optimal, carry_book_summary_matches, carry_book_policy_audit_matches, carry_book_regions_match, carry_book_segments_match, wide_book_plans_legal, wide_book_plans_optimal, wide_book_summary_matches, wide_book_policy_audit_matches, wide_book_regions_match, wide_book_segments_match, relocated_reordered_reruns_match
- lane_by_lane: shipped_summary_matches, shipped_policy_audit_matches, shipped_regions_match, shipped_segments_match, dense_book_plans_legal, dense_book_plans_optimal, dense_book_summary_matches, dense_book_policy_audit_matches, dense_book_regions_match, dense_book_segments_match, carry_book_plans_legal, carry_book_plans_optimal, carry_book_summary_matches, carry_book_policy_audit_matches, carry_book_regions_match, carry_book_segments_match, wide_book_plans_legal, wide_book_plans_optimal, wide_book_summary_matches, wide_book_policy_audit_matches, wide_book_regions_match, wide_book_segments_match, relocated_reordered_reruns_match

## Lessons for the master

- Case of output names only shows on a case-sensitive file system | template_change: no change: run rule mutants inside the Linux image, not on the Mac.
- A unique-optimum design leaves the stated tie rule untestable | no change: master decides G-3 versus G11.
