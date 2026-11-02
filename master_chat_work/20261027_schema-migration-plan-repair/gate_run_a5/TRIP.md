# Trajectory read-out: /Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/jobs/schema-migration-plan-repair/trajectory/claude-opus-5/Run 1

- final 68.62; agent steps 86; cost_usd 7.342618749999999
- judge: 7/13 (53.85%)
- test_output: 201/241 (83.40%)
- lost test points by kind (Law 1: TIMEOUT/CRASH give a recovery signal, WRONG is silent): {'WRONG': 40.0}
- final message (step 88): I repaired `migrakit` so every stage follows the contract, and wrote all deliverables to `/app/out`. **Defects found and fixed (19 code fixes across 9 files + one missing file)** core (`core/`, `pipeline.py`) - `FieldView.from_payload` dropped explicit nulls, so a null field looked absent (N1). - `n

## Scored items

| class | layer | item | weight | target | kind | evidence |
|---|---|---|---|---|---|---|
| LOST_GRADED | test_output | world_29_core_large_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_30_core_large_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_31_core_large_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_32_core_large_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_33_core_large_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_34_core_large_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_35_core_large_graph | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | world_36_core_large_graph | 5.0 | output | WRONG |  |
| SKIPPED | judge | R3 r3_probes_parse_rejected_batch_line | 3.0 | trajectory | - | The synthetic E_PARSE cases either have no usable batch or name B9, which is absent from the manifest. No constructed E_PARSE line names a batch that is listed in the manifest and then checks that batch's receipt. |
| SKIPPED | judge | R4 r4_probes_spaced_null_token | 3.0 | trajectory | - | The agent constructed a payload containing " NULL " and checked its status as part of a status list, but did not inspect that record's resulting payload or plan as required by this criterion. |
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

## Master note (auto 21:35)
- Correction: the 8 lost lever checks world_29..36_core_large_graph are TIMEOUT (verifier first_difference "TimeoutExpired" on the setpriv child), not WRONG. trajectory_readout.py read the JSON `[check] {...}` line format without classifying kind (tool gap).
- Law-1 v3.5: limit stated (repository_contract.md:91 'within 10 seconds'), shipped inputs fast (harden e3e74e6 kill table), loss confined to lever checks (201/241 = exactly the 40 lever points). Counts.
- negative_unsafe_archive_members passed=false means the negative did not fire (no points deducted).
