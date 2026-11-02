# RULE_COVERAGE flood-repair-portfolio

Each mutant is the oracle solution/solve.py with one rule dropped or misread (WORK/rule_mut/<id>.py; lever rows WORK/mutants/<name>.py), run through every check of tests/test_output.py with WORK/run_tests.py. Last cell = number of checks the mutant fails (score in brackets). Every row is at least 1.

| rule | file:line | mutant | tests failed |
|---|---|---|---|
| one self-contained file, python3 and its standard library only | environment/data/contract.md:5 | rule_mut/third_party_import | 32 (0.000) |
| missing declared file: no documents, ERROR MISSING_FILE, exit 1 | environment/data/contract.md:19 | rule_mut/missing_file_silent | 1 (0.972) |
| row numbers of the whole file | environment/data/contract.md:21 | mutants/row_within_round | 5 (0.861) |
| row numbers count data rows of the whole file from 1 | environment/data/contract.md:21 | rule_mut/row_numbers_from_zero | 5 (0.861) |
| a data row is any later non-empty line (an empty line is not a row) | environment/data/contract.md:21 | rule_mut/blank_line_counts_as_row | 3 (0.917) |
| a data row is any later non-empty line (reading goes on after an empty line) | environment/data/contract.md:21 | rule_mut/blank_line_ends_file | 22 (0.278) |
| risk_override replaces the site class | environment/data/contract.md:23 | mutants/no_override | 28 (0.093) |
| shared crew joins nothing | environment/data/contract.md:27 | mutants/shared_crews_too | 29 (0.065) |
| a site name stands for every proposal of the round at that site | environment/data/contract.md:29 | mutants/site_names_ignored | 31 (0.028) |
| round files checked in manifest order | environment/data/contract.md:35 | mutants/fixed_file_order | 1 (0.972) |
| checks in listed order | environment/data/contract.md:37 | mutants/invalid_before_duplicate | 3 (0.917) |
| DUPLICATE_PROPOSAL at the second occurrence | environment/data/contract.md:37 | mutants/first_occurrence_duplicate | 4 (0.889) |
| DUPLICATE_PROPOSAL | environment/data/contract.md:37 | rule_mut/dup_unchecked | 18 (0.444) |
| INVALID_INPUT households whole number 1..60 | environment/data/contract.md:37 | rule_mut/households_range_unchecked | 5 (0.843) |
| INVALID_INPUT unknown site | environment/data/contract.md:37 | rule_mut/unknown_site_unchecked | 31 (0.028) |
| INVALID_INPUT unknown crew | environment/data/contract.md:37 | rule_mut/unknown_crew_unchecked | 24 (0.259) |
| INVALID_INPUT risk_override not empty and not A-D | environment/data/contract.md:37 | rule_mut/override_unchecked | 16 (0.519) |
| segment_codes UNKNOWN_PROPOSAL | environment/data/contract.md:38 | rule_mut/segment_unknown_unchecked | 13 (0.620) |
| segment_codes INVALID_INPUT segment not a key | environment/data/contract.md:38 | rule_mut/segment_invalid_unchecked | 28 (0.130) |
| permits UNKNOWN_PROPOSAL | environment/data/contract.md:39 | rule_mut/permit_unknown_unchecked | 16 (0.519) |
| permits INVALID_INPUT status | environment/data/contract.md:39 | rule_mut/permit_status_unchecked | 23 (0.287) |
| exclusions UNKNOWN_PROPOSAL | environment/data/contract.md:40 | rule_mut/exclusion_unknown_unchecked | 31 (0.028) |
| exclusions INVALID_INPUT first equals second | environment/data/contract.md:40 | rule_mut/exclusion_same_unchecked | 13 (0.602) |
| NONPOSITIVE_BENEFIT only after file checks | environment/data/contract.md:42 | mutants/value_before_files | 5 (0.861) |
| NONPOSITIVE_BENEFIT | environment/data/contract.md:42 | rule_mut/nonpositive_unchecked | 2 (0.944) |
| NONPOSITIVE_BENEFIT reports the first such row | environment/data/contract.md:42 | rule_mut/nonpositive_last_row | 2 (0.944) |
| site premium added | environment/data/contract.md:48 | mutants/no_premium | 29 (0.065) |
| households x (rate + uplift) | environment/data/contract.md:48 | mutants/uplift_flat | 27 (0.120) |
| risk uplift added to the rate | environment/data/contract.md:50 | mutants/no_uplift | 27 (0.120) |
| exclusive crew joins its proposals | environment/data/contract.md:56 | mutants/no_crew | 29 (0.065) |
| held/applied permit joins its proposals | environment/data/contract.md:57 | mutants/no_permit | 29 (0.065) |
| withdrawn permit row counts for nothing | environment/data/contract.md:57 | mutants/withdrawn_counts | 31 (0.028) |
| exclusion entry joins the pair | environment/data/contract.md:58 | mutants/no_exclusion | 29 (0.065) |
| exclusion joins the pair in either order | environment/data/contract.md:58 | rule_mut/exclusion_one_order | 29 (0.065) |
| greatest total benefit | environment/data/contract.md:62 | mutants/greedy_benefit | 22 (0.259) |
| greatest total benefit | environment/data/contract.md:62 | mutants/greedy_ratio | 22 (0.259) |
| greatest total benefit | environment/data/contract.md:62 | mutants/greedy_swaps | 23 (0.231) |
| greatest total benefit | environment/data/contract.md:62 | mutants/timed_bnb | 23 (0.231) |
| greatest total benefit | environment/data/contract.md:62 | mutants/timed_ils | 23 (0.231) |
| tie-break: smaller sorted id list | environment/data/contract.md:62 | mutants/no_tiebreak | 22 (0.259) |
| tie-break: smaller sorted id list | environment/data/contract.md:62 | mutants/tiebreak_largest | 22 (0.259) |
| every figure of a round comes from the one chosen portfolio | environment/data/contract.md:64 | rule_mut/rollups_from_other_portfolio | 9 (0.750) |
| rounds listed in ascending round id | environment/data/contract.md:68 | rule_mut/rounds_in_file_order | 25 (0.176) |
| rejected round proposals row count kept, selected empty, total 0 | environment/data/contract.md:70 | rule_mut/rejected_round_keeps_count | 7 (0.731) |
| policy_audit line is the 1-based line number in the file | environment/data/contract.md:72 | rule_mut/audit_line_skips_blank | 5 (0.861) |
| PAIR sources in order crew, permit, exclusion | environment/data/contract.md:73 | rule_mut/audit_sources_unordered | 5 (0.861) |
| withdrawn_permit_rows counts planned rounds only | environment/data/contract.md:74 | rule_mut/withdrawn_rows_all_rounds | 5 (0.861) |
| conflict_pairs counts distinct pairs | environment/data/contract.md:74 | rule_mut/conflict_pairs_by_source_sum | 5 (0.861) |
| region rounds: one object for every planned round | environment/data/contract.md:76 | rule_mut/region_skips_empty_rounds | 9 (0.750) |

Rules uncovered: 0.
