| branch or mutator | doc line | folders | MATCH/DIFF | first DIFF field | who is right |
|---|---|---|---|---|---|
| branch h1 | all docs | 300 | MATCH 300 | - | - |
| branch h2 | all docs | 300 | MATCH 300 | - | - |
| branch h3 | all docs | 300 | MATCH 300 | - | - |
| branch h4 | all docs | 300 | MATCH 300 | - | - |
| branch h5 | all docs | 300 | MATCH 300 | - | - |
| branch h6 | all docs | 300 | MATCH 300 | - | - |
| branch shipped | all docs | 300 | MATCH 300 | - | - |
| C_blankline | data_conventions.md:45-46 | 96 | MATCH 96 | - | - |
| C_colorder | data_conventions.md:9-16 | 96 | MATCH 96 | - | - |
| C_crlf | data_conventions.md:9-16 | 96 | MATCH 96 | - | - |
| C_extra_col | data_conventions.md:9-16 | 96 | MATCH 96 | - | - |
| C_jsonl_style | data_conventions.md:9-16 | 96 | MATCH 96 | - | - |
| C_quoted | data_conventions.md:9-16 | 96 | MATCH 96 | - | - |
| C_toml_style | data_conventions.md:9-16 | 96 | MATCH 96 | - | - |
| C_types_extra | data_conventions.md:9-16 | 96 | MATCH 96 | - | - |
| D_abs_target | data_conventions.md:20-23 | 100 | MATCH 100 | - | - |
| D_alt_allow | data_conventions.md:20-23; overtime_policy.md:14 | 96 | MATCH 0; DIFF 96 (W96 C0 T0) | summary.json.settlement.allowance_granted: 1348 vs 48 | reference (a1 misreads ECMA-376 markup) |
| D_alt_avail | data_conventions.md:20-23,51-53 | 96 | MATCH 46; DIFF 50 (W50 C0 T0) | summary.json.plan_terms.first: 826 vs 820 | reference (a1 misreads ECMA-376 markup) |
| D_alt_closure_days | data_conventions.md:20-23,54-55 | 96 | MATCH 1; DIFF 94 (W94 C0 T0); SKIP 1 | policy_audit.json.checks[22].deferral_reason: 'no_slot' vs 'plan_trade | reference (a1 misreads ECMA-376 markup) |
| D_altcontent | data_conventions.md:20-23 | 96 | MATCH 0; DIFF 96 (W0 C96 T0) | cannot use input file /tmp/fzu0mz7agj/d19/disruption_notice.docx: no t | reference; a1 stops (not a lever, Law 1) |
| D_altcontent_data | data_conventions.md:20-23 | 96 | MATCH 0; DIFF 96 (W1 C95 T0) | summary.json.plan_terms.first: 472 vs 726 | reference (a1 misreads ECMA-376 markup) |
| D_bookmarks | data_conventions.md:20-23 | 96 | MATCH 96 | - | - |
| D_cellsdt_allow | data_conventions.md:20-23 | 103 | MATCH 0; DIFF 103 (W0 C103 T0) | KeyError: 'allowance_shifts' | reference; a1 stops (not a lever, Law 1) |
| D_cxml_row_allow | data_conventions.md:20-23; overtime_policy.md:14 | 103 | MATCH 0; DIFF 103 (W103 C0 T0) | summary.json.settlement.allowance_granted: 34 vs 48 | reference (a1 misreads ECMA-376 markup) |
| D_cxml_row_avail | data_conventions.md:20-23,51-53 | 103 | MATCH 58; DIFF 45 (W45 C0 T0) | summary.json.plan_terms.first: 824 vs 820 | reference (a1 misreads ECMA-376 markup) |
| D_cxml_row_closure | data_conventions.md:20-23,54-55 | 103 | MATCH 0; DIFF 102 (W102 C0 T0); SKIP 1 | summary.json.plan_terms.first: 660 vs 820 | reference (a1 misreads ECMA-376 markup) |
| D_decoy_table | data_conventions.md:20-23 | 97 | MATCH 97 | - | - |
| D_dot_target | data_conventions.md:20-21 | 99 | MATCH 0; DIFF 99 (W0 C99 T0) | cannot use input file /tmp/fzu0mz7agj/d15/disruption_notice.docx: "The | reference; a1 stops (not a lever, Law 1) |
| D_extra_rels | data_conventions.md:20-23 | 98 | MATCH 98 | - | - |
| D_header_spaces | data_conventions.md:20-23 | 96 | MATCH 96 | - | - |
| D_prefix | data_conventions.md:20-23 | 96 | MATCH 96 | - | - |
| D_rename_part | data_conventions.md:20-23 | 101 | MATCH 101 | - | - |
| D_rowprops | data_conventions.md:20-23 | 96 | MATCH 96 | - | - |
| D_sdt_allrows_allow | data_conventions.md:20-23; overtime_policy.md:14 | 102 | MATCH 0; DIFF 102 (W102 C0 T0) | summary.json.settlement.allowance_granted: 0 vs 48 | reference (a1 misreads ECMA-376 markup) |
| D_sdt_row_allow | data_conventions.md:20-23; overtime_policy.md:14 | 97 | MATCH 0; DIFF 97 (W97 C0 T0) | summary.json.settlement.allowance_granted: 35 vs 48 | reference (a1 misreads ECMA-376 markup) |
| D_sdt_row_avail | data_conventions.md:20-23,51-53 | 99 | MATCH 64; DIFF 35 (W35 C0 T0) | summary.json.plan_terms.first: 826 vs 820 | reference (a1 misreads ECMA-376 markup) |
| D_sdt_row_class | data_conventions.md:15,20-23 | 101 | MATCH 4; DIFF 97 (W0 C97 T0) | cannot use input file /tmp/fzu0mz7agj/d4/planning_limits.docx: no clas | reference; a1 stops (not a lever, Law 1) |
| D_sdt_row_closure | data_conventions.md:20-23,54-55 | 98 | MATCH 0; DIFF 96 (W96 C0 T0); SKIP 2 | summary.json.plan_terms.first: 560 vs 820 | reference (a1 misreads ECMA-376 markup) |
| D_sdt_row_item | data_conventions.md:15,20-23 | 100 | MATCH 0; DIFF 100 (W0 C100 T0) | cannot use input file /tmp/fzu0mz7agj/d3/planning_limits.docx: missing | reference; a1 stops (not a lever, Law 1) |
| D_sdt_run | data_conventions.md:20-23 | 103 | MATCH 103 | - | - |
| D_sdt_tbl | data_conventions.md:20-23 | 103 | MATCH 103 | - | - |
| D_split_runs | data_conventions.md:20-23 | 102 | MATCH 102 | - | - |
| D_tracked | data_conventions.md:20-23 | 96 | MATCH 96 | - | - |
| S_avail_after_end | data_conventions.md:51-53 | 12 | MATCH 12 | - | - |
| S_avail_before_start | data_conventions.md:51-53 | 12 | MATCH 12 | - | - |
| S_avail_late_in | data_conventions.md:51-53 | 12 | MATCH 12 | - | - |
| S_avail_own_out | data_conventions.md:51-53 | 12 | MATCH 12 | - | - |
| S_calendar_random | data_conventions.md:54-56 | 12 | MATCH 12 | - | - |
| S_closure_from_before | data_conventions.md:54-56 | 12 | MATCH 12 | - | - |
| S_closure_outside | data_conventions.md:54-56 | 12 | MATCH 12 | - | - |
| S_closure_past_end | data_conventions.md:54-56 | 12 | MATCH 12 | - | - |
| S_due_far | planning_policy.md:24-25 | 12 | MATCH 12 | - | - |
| S_dur1 | overtime_policy.md:3-7 | 12 | MATCH 12 | - | - |
| S_empty_requests | output_schema.md | 12 | MATCH 12 | - | - |
| S_grants0 | overtime_policy.md:14-24 | 12 | MATCH 12 | - | - |
| S_grants_big | overtime_policy.md:14-24 | 12 | MATCH 12 | - | - |
| S_grants_rand | overtime_policy.md:14-24 | 12 | MATCH 12 | - | - |
| S_ids_varlen | planning_policy.md:36-41 | 12 | MATCH 3; SKIP 9 | - | - |
| S_pool0 | overtime_policy.md:9-10 | 12 | MATCH 12 | - | - |
| S_pool_big | overtime_policy.md:9-10 | 12 | MATCH 12 | - | - |
| S_pool_small | overtime_policy.md:9-10 | 12 | MATCH 12 | - | - |
| S_pub_outside | planning_policy.md:30-31 | 12 | MATCH 12 | - | - |
| S_rates_types | planning_policy.md:22-29 | 12 | MATCH 12 | - | - |
| S_shift_cost | planning_policy.md:28-29 | 12 | MATCH 12 | - | - |
| S_status_case | data_conventions.md:31-32 | 12 | MATCH 12 | - | - |

Total folders: 5904
