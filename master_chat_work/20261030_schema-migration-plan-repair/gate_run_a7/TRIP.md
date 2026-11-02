# Trajectory read-out: master_chat_work/20261030_schema-migration-plan-repair/gate_run_a7/trajectory/claude-opus-5/Run 1

- final 32.12; agent steps 90; cost_usd 9.293263999999999
- judge: 13/43 (30.23%)
- test_output: 201/591 (34.01%)
- lost test points by kind (Law 1: TIMEOUT/KILLED/CRASH give a recovery signal, WRONG is silent): {'WRONG': 390.0}
- final message (step 92): The repository is repaired and all deliverables are written. ## What was broken and fixed **core** (`core/`, `pipeline.py`) - `FieldView.from_payload` collapsed an explicit null into "absent", destroying the three-state model of N1; it now reports `absent`/`null`/`value`. - `null_counts_as` fell bac

## Scored items

| class | layer | item | weight | target | kind | evidence |
|---|---|---|---|---|---|---|
| LOST_GRADED | test_output | world_100_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_101_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_102_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_103_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_104_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_105_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_106_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_29_core_large_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_30_core_large_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_31_core_large_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_32_core_large_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_33_core_large_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_34_core_large_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_35_core_large_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_36_core_large_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_37_core_large_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_38_core_large_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_39_core_large_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_40_core_large_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_41_core_large_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_42_core_large_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_43_core_large_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_44_core_large_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_45_core_large_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_46_core_large_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_47_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_48_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_49_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_50_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_51_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_52_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_53_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_54_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_55_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_56_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_57_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_58_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_59_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_60_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_61_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_62_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_63_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_64_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_65_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_66_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_67_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_68_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_69_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_70_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_71_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_72_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_73_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_74_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_75_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_76_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_77_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_78_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_79_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_80_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_81_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_82_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_83_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_84_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_85_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_86_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_87_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_88_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_89_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_90_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_91_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_92_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_93_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_94_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_95_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_96_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_97_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_98_core_gated_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_99_core_gated_graph | 5.0 | output | WRONG |  |
| SKIPPED | judge | R10 r11_reruns_cli_over_older_output | 3.0 | trajectory | - | The CLI was run into new output directories, but not over an existing older, longer `records.jsonl` output. |
| SKIPPED | judge | R11 r12_reruns_on_altered_copy | 3.0 | trajectory | - | No copy of `/app/ci` had the cost of a shipped record's used edge changed and that record's resulting plan displayed. |
| SKIPPED | judge | R19 r22_probes_empty_feed | 3.0 | trajectory | - | No pipeline run used a completely empty feed and inspected its summary. |
| SKIPPED | judge | R20 r24_probes_altered_field_policy | 3.0 | trajectory | - | Synthetic field-policy contracts were tested, but the agent did not alter one row in a copy of `/app/ci` and compare a corresponding shipped-domain record with the original run. |
| SKIPPED | judge | R21 r25_probes_altered_explicit_null | 3.0 | trajectory | - | Synthetic contracts tested both explicit-null defaults, but there was no altered copy of `/app/ci` and no comparison of a shipped explicit-null record against the original run. |
| SKIPPED | judge | R3 r3_probes_parse_rejected_batch_line | 3.0 | trajectory | - | The custom parse failures were either unnamed non-JSON input or a record naming B9, which was absent from the manifest. No E_PARSE record naming a manifest-listed batch was used to check that batch's receipt. |
| SKIPPED | judge | R4 r4_probes_spaced_null_token | 3.0 | trajectory | - | The agent tested exact token lists and unrelated whitespace-tolerant casts, but did not run a feed containing a value differing from a null token only by surrounding spaces and inspect its payload or plan. |
| SKIPPED | judge | R6 r7_compares_large_graph_plan | 3.0 | trajectory | - | The brute-force comparison used the shipped `/app/ci` graph rather than a thousand-schema folder built by the agent. The built large graph was timed but not shown beside a separate-search plan for the same record. |
| SKIPPED | judge | R7 r8_plans_with_dear_edge | 3.0 | trajectory | - | No constructed contract with an edge costing more than one million was exercised. |
| SKIPPED | judge | R8 r9_runs_with_unnamed_file | 3.0 | trajectory | - | The agent did not add a K2-ignored file to a copied contract folder and compare its records with the original run. |
| EASY | test_output | api_entry_points_importable | 1.0 | output | - | passed; weight 1 or sample/interface-level name |
| EASY | test_output | archive_src_layout | 1.0 | output | - | passed; weight 1 or sample/interface-level name |
| EASY | test_output | artifacts_exist | 1.0 | output | - | passed; weight 1 or sample/interface-level name |
| EASY | test_output | identity_merge_chain_followed | 1.0 | output | - | passed; weight 1 or sample/interface-level name |
| EASY | test_output | identity_merge_loop_rejected | 1.0 | output | - | passed; weight 1 or sample/interface-level name |
| EASY | test_output | identity_partner_id_beats_alias | 1.0 | output | - | passed; weight 1 or sample/interface-level name |
| EASY | test_output | module_core_claims_match_archive | 1.0 | output | - | passed; weight 1 or sample/interface-level name |
| EASY | test_output | module_parser_claims_match_archive | 1.0 | output | - | passed; weight 1 or sample/interface-level name |
| EASY | test_output | module_report_claims_match_archive | 1.0 | output | - | passed; weight 1 or sample/interface-level name |
| EASY | test_output | plan_revisits_schema_with_new_state | 3.0 | output | - | passed; weight 1 or sample/interface-level name |
| EASY | test_output | receipt_skips_lines_rejected_at_parse | 3.0 | output | - | passed; weight 1 or sample/interface-level name |
| EASY | test_output | repair_report_well_formed | 1.0 | output | - | passed; weight 1 or sample/interface-level name |
| EASY | test_output | signature_rejects_unknown_schema | 1.0 | output | - | passed; weight 1 or sample/interface-level name |
| EASY | test_output | summary_json_matches_delivered_run | 1.0 | output | - | passed; weight 1 or sample/interface-level name |
| EASY | test_output | summary_partner_order_by_rank | 1.0 | output | - | passed; weight 1 or sample/interface-level name |
| EASY | test_output | test_fixes_matches_visible_test_runs | 1.0 | output | - | passed; weight 1 or sample/interface-level name |
| EASY | test_output | visible_repo_tests_pass_from_archive | 1.0 | output | - | passed; weight 1 or sample/interface-level name |
| EASY | test_output | world_05_null_policy_replay_cli | 5.0 | output | - | passed; weight 1 or sample/interface-level name |
| EASY | test_output | world_09_policy_tokens_replay_corrections_cli | 5.0 | output | - | passed; weight 1 or sample/interface-level name |
| EASY | test_output | world_11_null_tie_corrections_cli | 5.0 | output | - | passed; weight 1 or sample/interface-level name |
| EASY | test_output | world_13_state_policy_feed_cli | 5.0 | output | - | passed; weight 1 or sample/interface-level name |
| EASY | test_output | world_18_scale_tie_replay_cli | 5.0 | output | - | passed; weight 1 or sample/interface-level name |
| EASY | test_output | world_24_reject_damage_tie_cli | 5.0 | output | - | passed; weight 1 or sample/interface-level name |
| EASY | test_output | world_27_pad_scope_state_tokens_cli | 5.0 | output | - | passed; weight 1 or sample/interface-level name |

## TRIP table (master fills by hand; WRONG_UNGRADED only here)

| step | what the agent did | what the docs require (file:line) | check/criterion | class |
|---|---|---|---|---|
