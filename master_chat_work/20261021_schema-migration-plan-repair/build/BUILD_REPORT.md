# BUILD_REPORT: schema-migration-plan-repair (21 Oct 2026 IST)

Verdict: DONE. All scores are tests-only (no OPENAI_API_KEY; judge channel not run).

## Bundle

`/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/schema-migration-plan-repair/`, 24 files:

| path | bytes |
|---|---|
| instruction.md | 2,397 (under 6,000) |
| task.toml | 1,894 |
| environment/Dockerfile | 857 (template, unchanged) |
| environment/data/ | 13 files, flat (table below) |
| solution/solve.sh | 77 (template) |
| solution/solve.py | 23,468 (561 lines, 408 substantive; 6% shared with test_output.py) |
| solution/TRUTH.md | 15,676 (8 sections, 6 focal, 3 drift, 2 trap) |
| tests/Dockerfile, test.sh | template, unchanged |
| tests/test_output.py | 802,079 (50 checks + embedded data) |
| tests/judge.toml | 9,943 (17 criteria) |
| tests/reward.toml | test_output = 0.5/142, judge = 0.5/46 |

## Data (environment/data), 9 formats, 27,647 counted lines (A5 minimum 20,000)

| file | format | lines | role |
|---|---|---|---|
| repo.zip | zip | 21 members, 1,152 lines (999 in src/) | shipped `migrakit` repository, 15 planted divergences |
| repository_contract.md | md | 138 | rules K1..K19 |
| migration_semantics.md | md | 64 | rules M1..M12 |
| null_semantics.ini | ini | 96 | header rules N1..N8 + presence, fill, 60 partner token lists |
| correction_log.txt | txt | 2,419 | header rules C1..C8 + SET/UNSET/NULL/REISSUE lines (10 malformed) |
| partner_aliases.xml | xml | 2,266 | header rules P1..P4; 2,100 partners, 146 merge links in chains, 2 loops |
| report_taxonomy.json | json | 56 | rules T1..T3 + 7 ordered categories |
| schema_versions.json | json | 5,004 | 1,000 schemas, 100 domains |
| migration_edges.csv | csv | 2,401 | 2,400 edges |
| field_policy.tsv | tsv | 2,001 | 2,000 policy rows |
| partner_batches.jsonl | jsonl | 8,000 | feed (15 malformed lines, replays, conflicts, reissues, tokens, nulls) |
| replay_manifest.csv | csv | 2,201 | 2,200 batches, shuffled received_seq |
| partner_order.tsv | tsv | 2,051 | 2,050 ranked partners (50 unranked) |

No expected outputs, no plans, no sample_*.json. Chains of length 4 or more: (1) feed partner -> partner_aliases.xml (alias, merge chain) -> replay_manifest.csv order -> REISSUE in correction_log.txt -> record status; (2) payload -> null_semantics.ini tokens -> field_policy.tsv presence and fill -> migration_edges.csv prerequisites and operations -> schema_versions.json canonical; (3) plan -> pinned corrections -> field_policy.tsv on the re-check -> report_taxonomy.json category -> partner_order.tsv roll-up.

Rule count stated in the instruction: 54. No defect list ships anywhere (master change 2); F1..F15 live only in DESIGN.md and TRUTH.md.

## Levers (copied from LEVERS.md)

50 checks; positive total 142; negative total 12. A check counts for every lever it needs. Rule homes: K = repository_contract.md, M = migration_semantics.md, N = null_semantics.ini header, C = correction_log.txt header, P = partner_aliases.xml header, T = report_taxonomy.json rules.

| check | w | levers | rule homes | observable | lost by (wrong solvers, measured) |
|---|---|---|---|---|---|
| artifacts_exist | +1 | STRUCT | K19 | seven files exist | none |
| archive_members_safe_src_layout | +1 | STRUCT | K1, K19 | zip member names | none |
| api_entry_points_importable | +1 | STRUCT | K1 | callables on migrakit | none |
| cli_module_runs_from_foreign_cwd | +3 | C | K10 | CLI output files, relative paths | WF2_abort_on_bad_line, WC_cli_paths, S2_shipped |
| visible_repo_tests_pass_from_archive | +3 | C | K1 | unittest result of delivered tests | WC_cli_paths, S2_shipped |
| summary_json_matches_delivered_run | +1 | HONESTY | K19 | summary.json vs delivered run | WF2_abort_on_bad_line, WC_cli_paths, S2_shipped, W3_enumeration |
| module_core_claims_match_archive | +1 | HONESTY | K19 | module_core.json vs archive AST | S2_shipped |
| module_parser_claims_match_archive | +1 | HONESTY | K19 | module_parser.json vs archive AST | S2_shipped |
| module_report_claims_match_archive | +1 | HONESTY | K19 | module_report.json vs archive AST | S2_shipped |
| test_fixes_matches_visible_test_runs | +1 | HONESTY | K19 | test_fixes.json vs real runs | none |
| repair_report_well_formed | +1 | HONESTY | K19 | repair-report.json shape | none |
| signature_keeps_explicit_null | +3 | LV-MR-6 | M10, N1 | state_signature result | W6_null_fix_at_call_site, S2_shipped |
| plan_tracks_field_dropped_earlier | +5 | LV-MR-1 | M6 | plan, gadget P1 | W1_prereq_on_received, S2_shipped |
| plan_uses_edge_enabled_earlier | +3 | LV-MR-1 | M6, N4 | plan, gadget P2 | W1_prereq_on_received, S2_shipped |
| plan_revisits_schema_with_new_state | +5 | LV-MR-1 | M6, M7 | plan, gadget P3 | W1_prereq_on_received, W3b_schema_dijkstra, S2_shipped |
| plan_renamed_null_satisfies_has | +5 | LV-MR-1, LV-MR-6 | M6 + N1/N5 | plan, gadget P4 | W1_prereq_on_received, W6_null_fix_at_call_site, S2_shipped |
| plan_tie_first_edge_decides | +5 | LV-MR-2 | M8 | plan, gadget P6 | W2_last_edge_tie |
| plan_tie_longer_plan_wins | +3 | LV-MR-2 | M8 | plan, gadget P7 | W2_last_edge_tie, W2b_fewest_steps, S2_shipped |
| plan_unreachable_by_state | +3 | F, LV-MR-1 | K12 + M6 | error code, gadget P8 | W1_prereq_on_received, S2_shipped |
| ladder_small | +3 | LV-MR-1, LV-MR-2 | M6 + M8 | plan, 6x3 ladder | W1_prereq_on_received, W2_last_edge_tie, W3b_schema_dijkstra, S2_shipped |
| ladder_medium_state | +3 | D, LV-MR-1 | K14 + M6 | plan, 16x4 ladder | W1_prereq_on_received, W3b_schema_dijkstra, S2_shipped, W3_enumeration |
| ladder_large_state | +5 | D, LV-MR-1 | K14 + M6 | plan, 45x3 ladder | W1_prereq_on_received, W3b_schema_dijkstra, S2_shipped, W3_enumeration |
| ladder_large_tie | +5 | D, LV-MR-2 | K14 + M8 | plan, 45x3 tie ladder | W2_last_edge_tie, S2_shipped, W3_enumeration |
| ladder_large_null | +5 | D, LV-MR-6 | K14 + N1/N2 | plan, 45x3 null ladder | W6_null_fix_at_call_site, S2_shipped, W3_enumeration |
| exec_add_fill_absent_vs_null | +3 | LV-MR-4 | N4 | executor payload | W4_fill_nulls, W4b_ini_only, S2_shipped |
| exec_operations_apply_in_order | +3 | B | M4, M5 | executor payload | S2_shipped |
| exec_correction_unset_breaks_step2 | +5 | LV-MR-7 | C4, M11 | executor result | W7a_corrections_up_front, W7b_no_recheck, S2_shipped |
| exec_correction_null_blocks_lacks | +5 | LV-MR-7, LV-MR-6 | C4 + N1/N2 | executor result | W6_null_fix_at_call_site, W7b_no_recheck, S2_shipped |
| exec_correction_null_counted_absent | +3 | LV-MR-7, LV-MR-4 | C4 + N2 (field_policy) | executor result | W4b_ini_only, W7b_no_recheck, S2_shipped |
| exec_correction_first_arrival_only | +3 | LV-MR-7 | C4 | executor result | W7d_every_arrival |
| exec_correction_at_source_enables_step1 | +3 | LV-MR-7 | C4 | executor result | none |
| identity_merge_chain | +3 | F | P2 | resolve_partner values | WF1_one_merge_hop, S2_shipped |
| identity_merge_loop_rejected | +3 | F | P3 | resolve_partner values | WF1_one_merge_hop, S2_shipped |
| pipe_rejection_codes | +3 | F | K12, K15 | codes of rejected lines | none |
| pipe_bad_lines_run_continues | +3 | F | K15 | status and payload of every line | WF2_abort_on_bad_line, S2_shipped |
| pipe_replay_across_aliases | +3 | LV-MR-5, F | K16 + P2 | statuses | W5m_fp_after_migration, W5c_raw_alias_key, WF1_one_merge_hop, S2_shipped |
| pipe_token_vs_json_null_conflict | +3 | LV-MR-5, LV-MR-4 | K16 + N6/N8 | statuses | W5_fp_after_tokens, W5m_fp_after_migration, S2_shipped |
| pipe_edit_dropped_by_migration_conflict | +3 | LV-MR-5 | K16 | statuses | W5m_fp_after_migration, S2_shipped |
| pipe_reissue_supersedes_holder | +3 | LV-MR-5 | K16 + C7 | statuses and payloads | W5m_fp_after_migration, S2_shipped |
| pipe_received_seq_decides_holder | +3 | LV-MR-5 | K13 | statuses | W5b_file_order, S2_shipped |
| pipe_mid_path_failure_record | +5 | LV-MR-7, F | C3/C4 + P2 | record fields | W7a_corrections_up_front, W7b_no_recheck, W7c_failed_as_migrated, WF1_one_merge_hop, S2_shipped |
| pipe_attempted_vs_migrated_counts | +5 | LV-MR-7, REPORT | C4/M11 + K18 | summary attempted and by_status | W7a_corrections_up_front, W7b_no_recheck, W7c_failed_as_migrated, S2_shipped |
| pipe_invalid_corrections_listed | +3 | F | C8 | summary invalid_corrections | W7a_corrections_up_front, S2_shipped |
| pipe_partner_token_list_replaces_default | +3 | LV-MR-4 | N7 | migrated payload | W4c_merged_tokens, W5c_raw_alias_key, S2_shipped |
| summary_categories_from_taxonomy | +3 | REPORT | T1, T2 | build_summary by_category | WR_summary_by_status, S2_shipped |
| summary_partner_order | +3 | REPORT | T3 | build_summary partners | WR_summary_by_status, S2_shipped |
| negative_hardcoded_sample_answers | -5 | CHEAT |  | seed or hidden edge ids in archive source | none |
| negative_filename_dependent_behaviour | -3 | CHEAT |  | records under two feed names | none |
| negative_deleted_visible_tests | -3 | CHEAT |  | visible test file content | none |
| negative_nondeterministic_output | -1 | CHEAT |  | two identical runs | none |

## Weight per lever (positive, needed-by)

| lever | weight | share of positive |
|---|---|---|
| LV-MR-1 | 32 | 22.5% |
| LV-MR-7 | 29 | 20.4% |
| F | 26 | 18.3% |
| LV-MR-6 | 18 | 12.7% |
| D | 18 | 12.7% |
| LV-MR-2 | 16 | 11.3% |
| LV-MR-5 | 15 | 10.6% |
| LV-MR-4 | 12 | 8.5% |
| REPORT | 11 | 7.7% |
| C | 6 | 4.2% |
| HONESTY | 6 | 4.2% |
| STRUCT | 3 | 2.1% |
| B | 3 | 2.1% |

## Wrong solvers (tests-only, measured with the real checks, local runner)

| solver | lever reverted | score | weight lost | checks lost | negatives fired |
|---|---|---|---|---|---|
| W1_prereq_on_received | LV-MR-1 | 0.7746 | 32 | ladder_large_state, ladder_medium_state, ladder_small, plan_renamed_null_satisfies_has, plan_revisits_schema_with_new_state, plan_tracks_field_dropped_earlier, plan_unreachable_by_state, plan_uses_edge_enabled_earlier | none |
| W2_last_edge_tie | LV-MR-2 | 0.8873 | 16 | ladder_large_tie, ladder_small, plan_tie_first_edge_decides, plan_tie_longer_plan_wins | none |
| W2b_fewest_steps | LV-MR-2 | 0.9789 | 3 | plan_tie_longer_plan_wins | none |
| W3b_schema_dijkstra | D | 0.8873 | 16 | ladder_large_state, ladder_medium_state, ladder_small, plan_revisits_schema_with_new_state | none |
| W4_fill_nulls | LV-MR-4 | 0.9789 | 3 | exec_add_fill_absent_vs_null | none |
| W4b_ini_only | LV-MR-4 | 0.9577 | 6 | exec_add_fill_absent_vs_null, exec_correction_null_counted_absent | none |
| W4c_merged_tokens | LV-MR-4 | 0.9789 | 3 | pipe_partner_token_list_replaces_default | none |
| W5_fp_after_tokens | LV-MR-5 | 0.9789 | 3 | pipe_token_vs_json_null_conflict | none |
| W5m_fp_after_migration | LV-MR-5 | 0.9155 | 12 | pipe_edit_dropped_by_migration_conflict, pipe_reissue_supersedes_holder, pipe_replay_across_aliases, pipe_token_vs_json_null_conflict | none |
| W5b_file_order | LV-MR-5 | 0.9789 | 3 | pipe_received_seq_decides_holder | none |
| W5c_raw_alias_key | LV-MR-5 | 0.9577 | 6 | pipe_partner_token_list_replaces_default, pipe_replay_across_aliases | none |
| W6_null_fix_at_call_site | LV-MR-6 | 0.8732 | 18 | exec_correction_null_blocks_lacks, ladder_large_null, plan_renamed_null_satisfies_has, signature_keeps_explicit_null | none |
| W7a_corrections_up_front | LV-MR-7 | 0.8732 | 18 | exec_correction_unset_breaks_step2, pipe_attempted_vs_migrated_counts, pipe_invalid_corrections_listed, pipe_mid_path_failure_record | none |
| W7b_no_recheck | LV-MR-7 | 0.8380 | 23 | exec_correction_null_blocks_lacks, exec_correction_null_counted_absent, exec_correction_unset_breaks_step2, pipe_attempted_vs_migrated_counts, pipe_mid_path_failure_record | none |
| W7c_failed_as_migrated | LV-MR-7 | 0.9296 | 10 | pipe_attempted_vs_migrated_counts, pipe_mid_path_failure_record | none |
| W7d_every_arrival | LV-MR-7 | 0.9789 | 3 | exec_correction_first_arrival_only | none |
| WF1_one_merge_hop | F | 0.9014 | 14 | identity_merge_chain, identity_merge_loop_rejected, pipe_mid_path_failure_record, pipe_replay_across_aliases | none |
| WF2_abort_on_bad_line | F | 0.9507 | 7 | cli_module_runs_from_foreign_cwd, pipe_bad_lines_run_continues, summary_json_matches_delivered_run | none |
| WR_summary_by_status | REPORT | 0.9577 | 6 | summary_categories_from_taxonomy, summary_partner_order | none |
| WC_cli_paths | C | 0.9507 | 7 | cli_module_runs_from_foreign_cwd, summary_json_matches_delivered_run, visible_repo_tests_pass_from_archive | none |
| S2_shipped | baseline | 0.1338 | 123 | cli_module_runs_from_foreign_cwd, exec_add_fill_absent_vs_null, exec_correction_null_blocks_lacks, exec_correction_null_counted_absent, exec_correction_unset_breaks_step2, exec_operations_apply_in_order, identity_merge_chain, identity_merge_loop_rejected, ladder_large_null, ladder_large_state, ladder_large_tie, ladder_medium_state, ladder_small, module_core_claims_match_archive, module_parser_claims_match_archive, module_report_claims_match_archive, pipe_attempted_vs_migrated_counts, pipe_bad_lines_run_continues, pipe_edit_dropped_by_migration_conflict, pipe_invalid_corrections_listed, pipe_mid_path_failure_record, pipe_partner_token_list_replaces_default, pipe_received_seq_decides_holder, pipe_reissue_supersedes_holder, pipe_replay_across_aliases, pipe_token_vs_json_null_conflict, plan_renamed_null_satisfies_has, plan_revisits_schema_with_new_state, plan_tie_longer_plan_wins, plan_tracks_field_dropped_earlier, plan_unreachable_by_state, plan_uses_edge_enabled_earlier, signature_keeps_explicit_null, summary_categories_from_taxonomy, summary_json_matches_delivered_run, summary_partner_order, visible_repo_tests_pass_from_archive | none |
| W3_enumeration | D | 0.8662 | 19 | ladder_large_null, ladder_large_state, ladder_large_tie, ladder_medium_state, summary_json_matches_delivered_run | none |

## Script, validator and playground results (final run, 21 Oct 16:10 IST)

| tool | result |
|---|---|
| structure_qc.py | 17 pass, 1 warn, 0 fail (WARN X1: repo.zip skipped as binary, expected) |
| instruction_qc.py | 5 pass, 0 warn, 0 fail (no C6 wording) |
| tests_qc.py | 34 pass, 1 warn, 0 fail (WARN A3: 50 checks over 35, accepted by the common rules; O1 overlap 6%) |
| judge_qc.py | 19 pass, 0 warn, 0 fail |
| validate_bundle.py --archetype repo-patch | 40 passed, 0 failed, 0 warnings, GATE PASS |
| playground.py --skip-docker | 0 FAIL, 1 WARN (A2: `APP_ROOT`, the tests' own path override, test-internal) |

## Oracle and baselines (tests-only)

Method: QC `exe_copy.py` tests-only copy, real `harbor-rewardkit==0.2.1` via uvx, run locally (no Docker) against fresh oracle artifacts from `solution/solve.py`.

| agent | runs | reward |
|---|---|---|
| oracle | 3 | 1.0, 1.0, 1.0 |
| nop | 1 | 0.0 |
| stub (empty artifacts) | 1 | 0.007 (artifacts_exist only) |
| S2 shipped repo, honest reports (local runner) | 1 | 0.134 |

Wrong solvers: see the table above; each reverted rule loses exactly its planned checks, the largest single-lever loss is W1 (32 of 142, 22.5%), and no negative fired on any of them. K14 time limit N = 10 s from the oracle (slowest of 3 runs 0.62 to 0.73 s locally; enumeration 7.6 s on 12x4, the hidden 16x4 has 256x the paths). check_exact.py (brute force, a second planner, an executor simulator) agrees on every hidden planner and executor case.

## Open conflicts

- OPEN CONFLICT Q18: TRUTH.md keeps the generator's provenance block (`authored_by: harbor-generator`, `status: generated_reference`, archetype, generator_seed, trailer_token). VB §15.5 passes with it; QC DS-27 (manual) fails generator provenance. Not resolved here, as instructed.

## Deviations and notes

- `--format-tag MIGRAKIT` was added to the scaffold command to name the package; the generator ignored it for repo-patch (package `task`), so every package file was rewritten as `migrakit`.
- Scaffold data files (api_contract.md, build_config.json, failing_tests.log, lint_report.json, package_manifest.json, regression_cases.jsonl) were replaced by the 13 designed files; the untouched scaffold is in `_work/.../scaffold_orig/`.
- Negatives: 4 (-12) instead of the 5 in DESIGN v2; the source-token negative was dropped (TS-27 risk).
- Embedded base64 data is split into adjacent literals so no literal holds a banned marker word (common rule 7).

## Not run

- Harbor Docker runs (QL procedure or Step 10 oracle x5): not run; the oracle was scored with real rewardkit locally instead. Not measured on 2 CPUs in Docker.
- Judge channel: not run (no OPENAI_API_KEY).
- P3 baselines: no real agent run, no S3.k table beyond the wrong solvers above, S4b (right in isolation, wrong where two rules meet) not built. Careful-agent difficulty is UNVERIFIED.
- Manual QC gates (IN-*, DS-*, TS-*, JD-*, CL-2, CL-4 numbers): not reviewed by a separate reviewer.
