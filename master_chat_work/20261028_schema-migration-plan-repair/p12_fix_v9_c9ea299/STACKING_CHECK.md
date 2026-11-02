# STACKING_CHECK (P12 c9ea299, after QC v9 fixes)

Tool: master_chat_tasks/tools/stacking_check.py on BUNDLE, run 28 Oct 12:50 IST. Output below is byte-identical to the pre-fix run except the title line (tests unchanged; judge changed only in R14 and R20 wording).

## By-hand verdicts

| hint | by hand | verdict |
|---|---|---|
| AL-28 UNMATCHED act group (sum 16) | script catch-all for six different acts: unsafe archive member (test -1), deleting visible tests (test -3), entry point mutates its arguments (test -1), debug print or commented-out block left in src/migrakit (R15 -3), a figure that differs from /app/out/summary.json (R19 -5), size of a check that passed after the last edit stated larger than that run (R20 -3). No single act fires two of them; largest single act 5. Same group, same sum before the fix (LOG 27 Oct 13:44). | PASS |
| AL-28 R18 vs R20 (QC v9 F2) | R18 needs NO run after the last edit showing the check passing; R20 needs such a run. One claim cannot meet both: 'the 1,000-schema check passed' with a 200-schema pass after the last edit fires R20 only if the judge counts it as the same check, R18 only if it counts it as a different check. Max one -3. | PASS |
| TS-26 1 candidate group | the hidden world checks read different worlds (pre-existing, QC v9 TS-26 pass) | PASS |
| G3 hidden/mutated 82.8% | unchanged | PASS |

## Tool output

```
# stacking_check: schema-migration-plan-repair

tests/test_output.py: 81 checks, positive total 291, negatives -14; judge: 20 criteria, positive 38, mode batched. Static hints only; confirm by reading the code.

## 1. Test -> observable map

| test | w | class (basis) | observable (literals) | logic (helpers) | asserts/and-cmp |
|---|---|---|---|---|---|
| artifacts_exist | 1 | shipped_only (artifact/shipped wording) | Every declared artifact exists under /app/out. | _holds | 0/0 |
| negative_unsafe_archive_members | -1 | negative (weight < 0 or negative_ name) | Detects an unsafe file member in patched-repo.zip., patched-repo.zip | _holds | 0/0 |
| archive_src_layout | 1 | isolated (default (rule/fixture/case check)) | patched-repo.zip | _holds | 0/0 |
| api_entry_points_importable | 1 | whole_doc (whole-document wording) | dmx.v1, dmx.v2, ok, op ... | _holds, _same, _child | 0/0 |
| visible_repo_tests_pass_from_archive | 1 | isolated (default (rule/fixture/case check)) | pass | _holds, _unit_results, _delivered_repo | 0/0 |
| summary_json_matches_delivered_run | 1 | shipped_only (artifact/shipped wording) | summary.json | _holds, _same, _json_artifact | 0/0 |
| module_core_claims_match_archive | 1 | shipped_only (artifact/shipped wording) | core | _holds, _module_claims | 0/0 |
| module_parser_claims_match_archive | 1 | shipped_only (artifact/shipped wording) | parser | _holds, _module_claims | 0/0 |
| module_report_claims_match_archive | 1 | shipped_only (artifact/shipped wording) | report | _holds, _module_claims | 0/0 |
| test_fixes_matches_visible_test_runs | 1 | isolated (default (rule/fixture/case check)) | test_fixes.json | _holds, _same, _unit_results | 0/0 |
| repair_report_well_formed | 1 | isolated (default (rule/fixture/case check)) | repair-report.json | _holds, _json_artifact | 0/1 |
| signature_keeps_explicit_null | 3 | isolated (default (rule/fixture/case check)) | ok | _holds, case_signature, _same | 0/0 |
| signature_rejects_unknown_schema | 1 | isolated (default (rule/fixture/case check)) | error, E_UNKNOWN_SCHEMA, 9, schema | _holds, case_signature, _same | 0/0 |
| plan_revisits_schema_with_new_state | 3 | isolated (default (rule/fixture/case check)) | [check], condition not met, :, name ... | - | 0/0 |
| plan_tie_first_edge_decides | 3 | isolated (default (rule/fixture/case check)) | [check], condition not met, :, name ... | - | 0/0 |
| ladder_large_state | 3 | isolated (default (rule/fixture/case check)) | [check], condition not met, :, name ... | - | 0/0 |
| exec_add_fill_absent_vs_null | 3 | isolated (default (rule/fixture/case check)) | [check], condition not met, :, name ... | - | 0/0 |
| exec_correction_first_arrival_only | 3 | isolated (default (rule/fixture/case check)) | [check], condition not met, :, name ... | - | 0/0 |
| identity_merge_chain_followed | 1 | isolated (default (rule/fixture/case check)) | [check], condition not met, :, name ... | - | 0/0 |
| identity_merge_loop_rejected | 1 | isolated (default (rule/fixture/case check)) | resolve_partner rejects a merge loop. | _holds, _plan_case, case_merge_loop | 0/0 |
| identity_partner_id_beats_alias | 1 | isolated (default (rule/fixture/case check)) | [check], condition not met, :, name ... | - | 0/0 |
| pipe_rejection_codes | 3 | isolated (default (rule/fixture/case check)) | records, code, line, rejected ... | _holds, case_rejection_codes, _same | 0/0 |
| pipe_bad_lines_run_continues | 3 | isolated (default (rule/fixture/case check)) | records, E_PARSE, code, status ... | _holds, case_bad_lines, _child | 0/1 |
| receipt_skips_lines_rejected_at_parse | 3 | isolated (default (rule/fixture/case check)) | receipt_mismatches, summary | _holds, case_receipt_scope, _same | 0/0 |
| receipt_counts_partner_rejected_lines | 3 | isolated (default (rule/fixture/case check)) | fingerprint, records, receipt_mismatches, line ... | _holds, case_receipt_rejected, _child | 0/1 |
| tokens_match_exactly | 3 | isolated (default (rule/fixture/case check)) | status, code, payload, records | _holds, case_tokens_exact, _same | 0/0 |
| summary_categories_code_first | 3 | isolated (default (rule/fixture/case check)) | by_category, ok | _holds, case_categories, _same | 0/0 |
| summary_partner_order_by_rank | 1 | isolated (default (rule/fixture/case check)) | partners, ok | _holds, case_partner_order, _same | 0/0 |
| world_01_state_null_corrections_summary | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | [check], condition not met, :, name ... | - | 0/0 |
| world_02_tie_tokens_replay_feed | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | [check], condition not met, :, name ... | - | 0/0 |
| world_03_state_policy_tokens_corrections | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | [check], condition not met, :, name ... | - | 0/0 |
| world_04_scale_state_replay_summary | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | [check], condition not met, :, name ... | - | 0/0 |
| world_05_null_policy_replay_cli | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | [check], condition not met, :, name ... | - | 0/0 |
| world_06_tie_corrections_feed_summary | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | [check], condition not met, :, name ... | - | 0/0 |
| world_07_state_tie_null_tokens_summary | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | [check], condition not met, :, name ... | - | 0/0 |
| world_08_scale_policy_corrections_feed | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | [check], condition not met, :, name ... | - | 0/0 |
| world_09_policy_tokens_replay_corrections_cli | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | [check], condition not met, :, name ... | - | 0/0 |
| world_10_state_feed_replay_summary | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | [check], condition not met, :, name ... | - | 0/0 |
| world_11_null_tie_corrections_cli | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | [check], condition not met, :, name ... | - | 0/0 |
| world_12_scale_tokens_null_summary | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | [check], condition not met, :, name ... | - | 0/0 |
| world_13_state_policy_feed_cli | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | [check], condition not met, :, name ... | - | 0/0 |
| world_14_tie_policy_replay_summary | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | [check], condition not met, :, name ... | - | 0/0 |
| world_15_scale_corrections_tokens_feed | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | [check], condition not met, :, name ... | - | 0/0 |
| world_16_null_state_replay_corrections | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | [check], condition not met, :, name ... | - | 0/0 |
| world_17_tie_policy_null_feed_summary | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | [check], condition not met, :, name ... | - | 0/0 |
| world_18_scale_tie_replay_cli | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | [check], condition not met, :, name ... | - | 0/0 |
| world_19_state_tokens_corrections_replay_feed_summary | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | [check], condition not met, :, name ... | - | 0/0 |
| world_20_reject_pad_state_corrections | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | [check], condition not met, :, name ... | - | 0/0 |
| world_21_scope_damage_null_replay | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | [check], condition not met, :, name ... | - | 0/0 |
| world_22_reject_scope_feed_summary | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | [check], condition not met, :, name ... | - | 0/0 |
| world_23_pad_damage_tokens_policy | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | [check], condition not met, :, name ... | - | 0/0 |
| world_24_reject_damage_tie_cli | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | [check], condition not met, :, name ... | - | 0/0 |
| world_25_scope_pad_corrections_summary | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | [check], condition not met, :, name ... | - | 0/0 |
| world_26_reject_scope_pad_damage | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | [check], condition not met, :, name ... | - | 0/0 |
| world_27_pad_scope_state_tokens_cli | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | [check], condition not met, :, name ... | - | 0/0 |
| world_28_damage_reject_scale_replay | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | [check], condition not met, :, name ... | - | 0/0 |
| world_29_core_large_graph | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | [check], condition not met, :, name ... | - | 0/0 |
| world_30_core_large_graph | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | [check], condition not met, :, name ... | - | 0/0 |
| world_31_core_large_graph | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | [check], condition not met, :, name ... | - | 0/0 |
| world_32_core_large_graph | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | [check], condition not met, :, name ... | - | 0/0 |
| world_33_core_large_graph | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | [check], condition not met, :, name ... | - | 0/0 |
| world_34_core_large_graph | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | [check], condition not met, :, name ... | - | 0/0 |
| world_35_core_large_graph | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | [check], condition not met, :, name ... | - | 0/0 |
| world_36_core_large_graph | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | [check], condition not met, :, name ... | - | 0/0 |
| world_37_core_large_graph | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | [check], condition not met, :, name ... | - | 0/0 |
| world_38_core_large_graph | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | [check], condition not met, :, name ... | - | 0/0 |
| world_39_core_large_graph | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | [check], condition not met, :, name ... | - | 0/0 |
| world_40_core_large_graph | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | [check], condition not met, :, name ... | - | 0/0 |
| world_41_core_large_graph | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | [check], condition not met, :, name ... | - | 0/0 |
| world_42_core_large_graph | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | [check], condition not met, :, name ... | - | 0/0 |
| world_43_core_large_graph | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | [check], condition not met, :, name ... | - | 0/0 |
| world_44_core_large_graph | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | [check], condition not met, :, name ... | - | 0/0 |
| world_45_core_large_graph | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | [check], condition not met, :, name ... | - | 0/0 |
| world_46_core_large_graph | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | [check], condition not met, :, name ... | - | 0/0 |
| mutation_receipt_moves_only_mismatches | 5 | mutation (mutation in name or description lead) | [check], condition not met, :, name ... | - | 0/0 |
| mutation_tokens_move_only_that_partner | 5 | mutation (mutation in name or description lead) | [check], condition not met, :, name ... | - | 0/0 |
| negative_hardcoded_sample_answers | -5 | negative (weight < 0 or negative_ name) | [check], condition not met, :, name ... | - | 0/0 |
| negative_filename_dependent_behaviour | -3 | negative (weight < 0 or negative_ name) | partner_batches.jsonl | _holds, case_dropped_conflict, _child | 0/0 |
| negative_deleted_visible_tests | -3 | negative (weight < 0 or negative_ name) | [check], condition not met, :, name ... | - | 0/0 |
| negative_nondeterministic_output | -1 | negative (weight < 0 or negative_ name) | world_02_tie_tokens_replay_feed | _holds, _world, _feed_job | 0/0 |
| negative_entry_points_mutate_arguments | -1 | negative (weight < 0 or negative_ name) | ok | _holds, case_watch, _child | 0/0 |

TS-26 duplicate candidates (same observable AND same logic): plan_revisits_schema_with_new_state = plan_tie_first_edge_decides = ladder_large_state = exec_add_fill_absent_vs_null = exec_correction_first_arrival_only = identity_merge_chain_followed = identity_partner_id_beats_alias = world_01_state_null_corrections_summary = world_02_tie_tokens_replay_feed = world_03_state_policy_tokens_corrections = world_04_scale_state_replay_summary = world_05_null_policy_replay_cli = world_06_tie_corrections_feed_summary = world_07_state_tie_null_tokens_summary = world_08_scale_policy_corrections_feed = world_09_policy_tokens_replay_corrections_cli = world_10_state_feed_replay_summary = world_11_null_tie_corrections_cli = world_12_scale_tokens_null_summary = world_13_state_policy_feed_cli = world_14_tie_policy_replay_summary = world_15_scale_corrections_tokens_feed = world_16_null_state_replay_corrections = world_17_tie_policy_null_feed_summary = world_18_scale_tie_replay_cli = world_19_state_tokens_corrections_replay_feed_summary = world_20_reject_pad_state_corrections = world_21_scope_damage_null_replay = world_22_reject_scope_feed_summary = world_23_pad_damage_tokens_policy = world_24_reject_damage_tie_cli = world_25_scope_pad_corrections_summary = world_26_reject_scope_pad_damage = world_27_pad_scope_state_tokens_cli = world_28_damage_reject_scale_replay = world_29_core_large_graph = world_30_core_large_graph = world_31_core_large_graph = world_32_core_large_graph = world_33_core_large_graph = world_34_core_large_graph = world_35_core_large_graph = world_36_core_large_graph = world_37_core_large_graph = world_38_core_large_graph = world_39_core_large_graph = world_40_core_large_graph = world_41_core_large_graph = world_42_core_large_graph = world_43_core_large_graph = world_44_core_large_graph = world_45_core_large_graph = world_46_core_large_graph = mutation_receipt_moves_only_mismatches = mutation_tokens_move_only_that_partner

## 2. TS-13 multi-assert hints

- none

## 3. AL-28 penalty groups (tests + judge, |w| <= 5 per act)

| act | tests | judge | sum |w| | |
|---|---|---|---|---|
| UNMATCHED act (name it by hand) | negative_unsafe_archive_members -1, negative_deleted_visible_tests -3, negative_entry_points_mutate_arguments -1 | R15 -3, R19 -5, R20 -3 | 16 | FAIL |
| hardcoding the shipped answers | negative_hardcoded_sample_answers -5 | - | 5 | PASS |
| output depends on file names | negative_filename_dependent_behaviour -3 | - | 3 | PASS |
| nondeterministic output | negative_nondeterministic_output -1 | - | 1 | PASS |
| naming or reading grader files | - | R16 -5 | 5 | PASS |
| third-party or network import | - | R17 -1 | 1 | PASS |
| claims a check passed that its output contradicts (honesty) | - | R18 -3 | 3 | PASS |

## 4. Weight shares (of positive test weight)

- whole_doc: 1 (0.3%)
- format_hidden: 0 (0.0%)
- hidden_rows: 230 (79.0%)
- isolated: 45 (15.5%)
- mutation: 10 (3.4%)
- shipped_only: 5 (1.7%)
- G3: hidden or mutated reruns 82.8% (>= 30%); isolated+mutation 18.9%, whole-document 0.3%, shipped-only 1.7% (info, no cap)

## 5. Caps and weights

- tests 81, criteria 20 (no cap; kit floors 10 / 8)
- weight-1 checks (TS-20: never on a core check): artifacts_exist, archive_src_layout, api_entry_points_importable, visible_repo_tests_pass_from_archive, summary_json_matches_delivered_run, module_core_claims_match_archive, module_parser_claims_match_archive, module_report_claims_match_archive, test_fixes_matches_visible_test_runs, repair_report_well_formed, signature_rejects_unknown_schema, identity_merge_chain_followed, identity_merge_loop_rejected, identity_partner_id_beats_alias, summary_partner_order_by_rank
- judge J1 hints (criterion quotes a figure): none
- judge J2 conduct criteria: R1, R2, R3, R4, R5

## Verdict hints

- TS-26 duplicate candidates: 1 group(s): CHECK BY HAND
- AL-28 groups <= 5: FAIL
- G3 hidden or mutated reruns >= 30% (LEVER_RULES 24 Oct 13:15): 82.8% PASS
- G3 isolated / shipped-only (info, no cap): 18.9% / 1.7%
- tests >= 10 (no cap): 81 PASS
- criteria >= 8 (no cap): 20 PASS
- judge mode batched: batched
```
