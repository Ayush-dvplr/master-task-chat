# LEVERS: schema-migration-plan-repair

63 checks; positive total 201; negative total 14 (Harden P9 v2 r1; the older tables below keep their own totals). A check counts for every lever it needs. Rule homes: K = repository_contract.md, M = migration_semantics.md, N = null_semantics.ini header, C = correction_log.txt header, P = partner_aliases.xml header, T = report_taxonomy.json rules.

The detailed check and variant tables below preserve the original build measurements. The Harden P9 v2 r1 section at the end gives the current registration names, weights and shares.

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

## Round 1 (22 Oct 2026): supersedes the tables above

Levers: STATE (prereqs after previous step, schemas repeat: F1/F2), TIE (edge-id list from the first edge: F3), SCALE (polynomial search, 30 and 45 layer ladders: F4), NULL (explicit null kept: F5), POLICY (empty null_counts_as column falls back to ini [presence], the decoy default `OPTIONAL_NULL` + README; fill column first: F6), TOKENS (own line used exactly, empty line means no tokens (N7, rule by omission), tokens before planning, keyed by canonical id: F7/F7b), CORR (first arrival incl. source and canonical, log order, re-check, failed stays failed: F8/F9), REPLAY (canonical identity, holder once partner stage passes, received_seq order, fingerprint as received: F10/F11), FEED (every merge link, loops, id beats alias, non-JSON lines continue: F12/F13), REPORT (taxonomy code first, partner rank: F14), CLI (relative paths, `__main__`: F15).

Checks (46; positive 137; negative 13; P12 r1 split the old three-part signature check, TS-13; P12 r2 moved the argument guard to a negative, TS-25; P12 r3 split the summary check, TS-13). w1: artifacts_exist, archive_members_safe_src_layout, api_entry_points_importable (STRUCT), visible_repo_tests_pass_from_archive (CLI), summary_json_matches_delivered_run, module_core/parser/report_claims_match_archive, test_fixes_matches_visible_test_runs, repair_report_well_formed (HONESTY, shipped-input outputs only: 6 = 4.4%), signature_rejects_unknown_schema (guard, K11), and the negative negative_entry_points_mutate_arguments (-1, K5/K6/K7; its case runs the fill and correction paths, so a fix that writes into the caller's payload fires it). isolated (31 = 22.6%; weight 3 unless noted): signature_keeps_explicit_null (NULL, K5, M10), plan_revisits_schema_with_new_state (STATE), plan_tie_first_edge_decides (TIE), ladder_large_state (SCALE), exec_add_fill_absent_vs_null (POLICY fill, N4 only since P12 r3), exec_correction_first_arrival_only (CORR), identity_merge_links_followed (FEED, P1-P3), pipe_rejection_codes (FEED, K12), pipe_bad_lines_run_continues (FEED, K15), summary_categories_code_first (REPORT, T1/T2, weight 3) and summary_partner_order_by_rank (REPORT, T3, weight 1). w5 composed (95 = 69.9%): 19 hidden worlds, whole records (and summary in REPORT worlds) against the tests' reference pipeline:

| world | levers |
|---|---|
| 01 | STATE NULL CORR REPORT |
| 02 | TIE TOKENS REPLAY FEED |
| 03 | STATE POLICY TOKENS CORR |
| 04 | SCALE STATE REPLAY REPORT |
| 05 | NULL POLICY REPLAY CLI |
| 06 | TIE CORR FEED REPORT |
| 07 | STATE TIE NULL TOKENS REPORT |
| 08 | SCALE POLICY CORR FEED |
| 09 | POLICY TOKENS REPLAY CORR CLI |
| 10 | STATE FEED REPLAY REPORT |
| 11 | NULL TIE CORR CLI |
| 12 | SCALE TOKENS NULL REPORT |
| 13 | STATE POLICY FEED CLI |
| 14 | TIE POLICY REPLAY REPORT |
| 15 | SCALE CORR TOKENS FEED |
| 16 | NULL STATE REPLAY CORR |
| 17 | TIE POLICY NULL FEED REPORT |
| 18 | SCALE TIE REPLAY CLI |
| 19 | STATE TOKENS CORR REPLAY FEED REPORT |

Positive weight per lever by design (a check counts for each lever it carries): STATE 43, TIE 38, SCALE 28, NULL 38, POLICY 38, TOKENS 35, CORR 48, REPLAY 45, FEED 49, REPORT 48, CLI 26, STRUCT 3, HONESTY 6.

Measured (measure_variants.py, stub rewardkit, tests channel; variant = repo_fixed plus one wrong reading; run-lost excludes the five report-consistency checks, which compare against the oracle's own reports):

| variant | score | run-lost | worlds lost | isolated lost |
|---|---|---|---|---|
| shipped | 0.0296 | 126 | 19 | 31 |
| F1-F4 planner | 0.2593 | 99 | 18 (all but 09) | 9 |
| F5 null dropped | 0.4963 | 66 | 12 (NULL + POLICY worlds) | 6 |
| F6 decoy presence | 0.7259 | 35 | 7 (POLICY) | 0 |
| F6 fill ini only | 0.7111 | 38 | 7 (POLICY) | 3 |
| F7 merged tokens | 0.7333 | 35 | 7 (TOKENS) | 0 |
| F7b empty line falls back | 0.7333 | 35 | 7 (TOKENS) | 0 |
| tokens after planning | 0.7333 | 35 | 7 (TOKENS) | 0 |
| F8 executor | 0.6370 | 48 | 9 (CORR) | 3 |
| F9 failed as migrated | 0.6593 | 45 | 9 (CORR) | 0 |
| corrections in id order | 0.6667 | 45 | 9 (CORR) | 0 |
| F10 raw identity, late holder | 0.6593 | 45 | 9 (REPLAY) | 0 |
| F11 file order | 0.6593 | 45 | 9 (REPLAY) | 0 |
| F12 one merge hop | 0.6519 | 46 | 8 (FEED) | 6 |
| alias before id | 0.6815 | 43 | 8 (FEED) | 3 |
| F13 abort on bad line | 0.6741 | 43 | 8 (FEED) | 3 |
| F14 summary | 0.6296 | 48 | 9 (REPORT) | 3 |
| F15 cli | 0.7926 | 26 | 5 (CLI) | 1 |

P12 r1 (positive 137 after the TS-13 split): every variant above passes both new w1 guards, so each score becomes (old x 135 + 2) / 137. Measured: shipped 0.0438, F1-F4 planner 0.2701, F5 null dropped 0.5036, F6 decoy presence 0.7299, F15 cli 0.7956, tokens after planning 0.7372; oracle 1.0000, forgery 0.0365. Lost checks per variant are unchanged.

P12 r2 (positive 136, negative 13; argument guard now negative, R7 negative, K19 completeness and boolean casts graded). Measured with measure_variants.py on the stub runner: shipped 0.0368 (35 lost), F1-F4 planner 0.2647 (22), F5 from_payload 0.5000 (16), F6 decoy null 0.7279 (9), F6 fill 0.7132 (9), F7 parser merge 0.7353 (8), F7b tokens_for 0.7353 (8), F8 executor 0.6397 (11), F9 classify 0.6618 (10), F10 admit 0.6618 (10), F11 order 0.6618 (10), F12 identity 0.6544 (11), F13 feed 0.6765 (10), F14 summary 0.6324 (12), F15 cli 0.7941 (8); no negative fired on any variant; oracle 1.0000 (136/136).

P12 r3 (positive 137 after the summary split; AL-27 triggers added inside the NULL, REPLAY and FEED gadgets). Measured with measure_variants.py on the stub runner: shipped 0.0365 (36 lost), F1-F4 planner 0.2701 (22), F5 from_payload 0.5036 (16), F6 fill 0.7153 (9), F8 executor 0.6423 (11), F9 classify 0.6642 (10), F10 admit 0.4818 (15), F11 order 0.6642 (10), F12 identity 0.6569 (11), F13 feed 0.6788 (10), F14 summary 0.6277 (13), F15 cli 0.7956 (8). One-rule-broken variants: M5 integral float kept 0.7007 (9), M4 cast touches null 0.7372 (8), M5 cast converts booleans 0.7372 (8), K4 ASCII-escaped fingerprint 0.6642 (10), K13 schema before partner 0.7007 (9), K15 partner before batch 0.7007 (9), K16 holder needs known schema 0.7080 (8); before the fix the same seven scored 0.9926, 0.9926, 0.9706, 0.9926, 0.9926, 0.9926 and 1.0000. No negative fired on any variant; oracle 1.0000 (137/137).

Visible-data agreement (verify_visible.py): every single wrong reading above except F5 and the decoy gives records identical to repo_fixed on the shipped inputs; F5 and the decoy each change the same 16 boundary records; F14 changes only by_category and partners.

## P12 r4 current registration and split

49 checks: 43 positive worth 137 and 6 negative worth 14. Eleven weight-1 structural/guard checks worth 11, thirteen isolated checks worth 31 (22.6%), and nineteen hidden-world checks worth 95 (69.3%). Six shipped-input-only points are 4.4% of positive weight. `negative_unsafe_archive_members` penalizes unsafe archive paths at weight -1; `archive_src_layout` rewards K1 layout at weight 1. The safety half is negative to satisfy TS-25. `identity_merge_chain_followed`, `identity_merge_loop_rejected`, and `identity_partner_id_beats_alias` each read one P2/P3/P1 property at weight 1. These replace `archive_members_safe_src_layout` and `identity_merge_links_followed`. All previously registered hidden worlds and their separating cases remain. Lever effect of this split and K19/TRUTH corrections: none for STATE, TIE, SCALE, NULL, POLICY, TOKENS, CORR, REPLAY, FEED, REPORT, CLI, STRUCT, and HONESTY. The archived wrong-reading artifacts are stale; see P12 r4 RECHECK_FIX.md for the trap measurement limitation.

## Harden P9 v2 r1 (23 Oct 2026): levers L1 + L2 + L5 + L6

63 checks: 57 positive worth 201, 6 negative worth 14 (unchanged). Ten w1 structural checks worth 10 (six shipped-input-only, 3.0%), seventeen isolated checks worth 41 (20.4%), thirty w5 whole-document checks on hidden reseeded inputs worth 150 (74.6%: 28 worlds and 2 mutation tests). Every world now compares the whole records list and the whole run summary. Old levers stay as cascade members inside the worlds; every one of them leaked in the blind solve (OUT DIAGNOSIS.md), so none carries the hardness alone.

New hidden gadgets (tests `_LATE_GADGETS`, run after the filler): REJECT (a batch with good lines, a ghost-partner line and a merge-loop line, honest receipt), SCOPE (a batch with good lines and two parse-rejected lines that name it, honest receipt that leaves them out), PAD (padded default and own tokens in plain fields, a padded token in a prereq field whose null counts as absent, so the plan changes), DAMAGE (two damaged receipts, one count off by one and one XOR bit flipped, plus an empty batch `0,00000000`). Worlds 01-19 each gained the tags of their pair (REJECT,PAD), (SCOPE,DAMAGE), (REJECT,SCOPE), (PAD,DAMAGE), (REJECT,DAMAGE), (SCOPE,PAD); worlds 20-28 are new mixes.

### RECEIPT (L1 green control)
- Rule: repository_contract.md:79-86 (K13 batch receipt), K18 line 128 (`receipt_mismatches` in the run summary).
- Reflex reading: the receipt is a transport control; once `receipt_mismatches` is `[]` on the shipped run, the run is taken as right.
- Hidden cases: DAMAGE worlds (02, 04, 05, 08, 10, 11, 14, 16, 17, 21, 23, 24, 26, 28) and the mutation test expect named mismatches; every other world expects `[]` while its graded records still depend on tokens, planning and corrections.
- Wrong reading fails: `W_receipt_always_empty` (see table).
- Interactions: L2 and L6 live inside the same control; L1 is what makes a make-it-match repair look finished.

### RECEIPT make-it-match (L2)
- Rule: control at repository_contract.md:81-84; reading rule repository_contract.md:120-121 ("`fingerprint` (null before the partner stage passes)").
- Shipped defect F17: the check XORs the records' `fingerprint` field and skips nulls, so on the shipped run 25 batches holding E_UNKNOWN_PARTNER lines show mismatches.
- Reflex reading: give partner-rejected records a fingerprint (shipped receipt turns green; K17 broken).
- Hidden cases: REJECT worlds (01, 03, 05, 07, 09, 11, 13, 15, 17, 19, 20, 22, 24, 26, 28), `receipt_counts_partner_rejected_lines` (also requires the rejected records' fingerprint null; QC v6 TS-13 drop of that half was tried in P12 r5 and reverted: the reflex replay rose to 42/201 = 0.209 > 0.20). Judge: R2 w3 checks the rejected record's fingerprint field, R9 w1 checks that batch's receipt result (split in P12 r5, QC v6 JD-5).
- Wrong readings fail: `W_receipt_make_it_match`, `W_receipt_skips_rejected`.

### RECEIPT scope (L6 scope carried by a definition)
- Rule: repository_contract.md:81 ("`lines` is the number of records whose `batch` is that batch") with repository_contract.md:97-98 (K15: every E_PARSE record has `batch` null).
- Shipped defect F17 (same loop): counts the raw `batch` field of every feed line in the manifest.
- Reflex reading: count feed lines by their raw `batch`; shipped data never has a parse-rejected line that names a manifest batch (W5), so the reflex stays green there.
- Hidden cases: SCOPE worlds (02, 03, 06, 08, 09, 12, 14, 15, 18, 21, 22, 25, 26, 27), `receipt_skips_lines_rejected_at_parse` (expects `["B4"]`, not `["B1"]`).
- Wrong reading fails: `W_receipt_counts_parse_rejects`.

### TOKENS exact (L5 strict beside normalising)
- Rule: null_semantics.ini:20-21 (N6 "a string exactly equal to one of the partner's null tokens"); normalising neighbours null_semantics.ini:24 (N8 trims the token text) and migration_semantics.md:25,27 (M5 casts ignore surrounding spaces).
- Shipped defect F16: `_replace_tokens` compares `value.strip()`, docstring "values are compared trimmed, as the tokens are".
- Reflex reading: keep the trim (it reads as consistent with N8 and M5).
- Separating rows ship (W5 allows it for L5): 32 shipped records hold padded tokens in plain fields; the shipped summary figures do not move, only those records' payloads.
- Hidden cases: PAD worlds (01, 04, 06, 07, 10, 12, 13, 16, 18, 19, 20, 23, 25, 26, 27), `tokens_match_exactly`, `pipe_bad_lines_run_continues` (line k3 `"N/A "` stays a string), `mutation_tokens_move_only_that_partner`.
- Wrong reading fails: `F16 tokens trimmed`.

### Reflex gate
OUT/agent_program/replay.py (blind repair re-applied to the new shipped repo plus the reflex reading of each new lever): tests channel 39/201 = 0.1940. It keeps all ten structural checks, the old isolated checks except `pipe_bad_lines_run_continues`, and fails the three new isolated checks, both mutation tests and all 28 worlds.

### Variant re-measure on the 63-check tests (17:20-17:30)

| variant | tests score | checks lost |
|---|---|---|
| shipped | 0.0299 | 51 |
| F1-F4 planner | 0.3781 | 27 |
| F5 from_payload | 0.5871 | 19 |
| F6 decoy null | 0.7662 | 11 |
| F6 fill | 0.7562 | 11 |
| F7 parser merge | 0.7313 | 12 |
| F7b tokens_for or | 0.7463 | 11 |
| F8 executor | 0.7065 | 13 |
| F9 classify | 0.7214 | 12 |
| F10 admit | 0.5224 | 20 |
| F11 order | 0.6965 | 13 |
| F12 identity | 0.4577 | 25 |
| F13 feed | 0.7313 | 12 |
| F14 summary | 0.2239 | 34 |
| F16 tokens trimmed | 0.5672 | 19 |
| F17 receipt shipped | 0.3134 | 30 |
| F15 cli | 0.8109 | 10 |
| W_alias_before_id | 0.7463 | 11 |
| W_corrections_sorted_by_id | 0.7264 | 11 |
| W_tokens_after_planning | 0.7264 | 13 |
| W_cast_int_drops_integral_float | 0.7463 | 11 |
| W_cast_touches_null | 0.7960 | 9 |
| W_cast_converts_booleans | 0.7960 | 9 |
| W_fingerprint_ascii_escaped | 0.6965 | 13 |
| W_schema_before_partner | 0.7463 | 11 |
| W_partner_before_batch | 0.7463 | 11 |
| W_holder_needs_known_schema | 0.7512 | 10 |
| W_receipt_make_it_match | 0.4876 | 21 |
| W_receipt_counts_parse_rejects | 0.5124 | 20 |
| W_receipt_skips_rejected | 0.4826 | 22 |
| W_receipt_always_empty | 0.5672 | 19 |

Reflex program (blind repair + make-it-match + raw-count scope + trimmed tokens): 39/201 = 0.194.

## Wave 1 hardening (27 Oct 2026, board e3e74e6): P-3 large hidden migration graphs

Registration now 71 checks: 65 positive worth 241, 6 negative worth 14. The 28 earlier worlds, ladders and isolated cases are byte-identical (digest c70a4595... before and after).

| check | weight | lever | what it needs | measured |
| --- | --- | --- | --- | --- |
| world_29_core_large_graph .. world_36_core_large_graph (8) | 5 each, 40 = 16.6% | P-3 (CORE tag) | cheapest plan (M8) on a domain of 1,145 to 1,195 schemas and 4,575 to 4,778 edges, 10 fields, 8 prerequisite fields, inside the K14 10 s; whole records + run summary compare | reference 0.04 s max; every generic solver of KILL_TEST.md keeps 0/40 |

Doc text: none added. K14 already states the sizes and the 10 s; migration_semantics.md:11 states cost is a positive integer (no upper bound), so the 40,000,000 escape edge is inside the stated value form.
Variant re-measure: the pre-wave oracle with its plain planner (the all-but-one program) loses exactly the 8 core worlds (see COST_TABLE.md).

## Gate v3.6 harden (28 Oct 2026, board f0331ad): P-3 raised to 18 large-graph worlds
- Lever: world_29..world_46_core_large_graph, tag CORE, weight 5 each = 90 of 291 positive test points (30.9%; bar 25-40%). world_37..46 are new: `_g_core(w, number, 7000, 5)` (own stream `_rng(7000 + number)`, five cheap edges per region schema, a draw above 6,000 edges is skipped). world_29..36 keep stream 5000 and four edges; their inputs and expectations, and all 28 older worlds, ladders and isolated cases, are byte-identical (proto/digest36_before.txt == digest36_after.txt, TOTAL 629bd769...).
- Doc text: none added. K14 (repository_contract.md:88-93) states the sizes and the 10 s per call; M2 (migration_semantics.md:10-11) the positive integer cost; M8 (:41-44) the objective.
- Loss for plausible programs (proto/kill3_*.log): plain/speed-tuned/incumbent/prereq-keyed Dijkstra, exhaustive, the a5 agent, blind 4f7606c, blind cee149a and Opus a4 planners TIMEOUT (>62 s) on every new world; dominance, bidirectional, greedy and schema-only return a WRONG plan. Reference 0.011 s max. Shipped inputs fast for all.
- Judge: probe band rebuilt (WORK/JUDGE_MAP.md, make_judge_g36.py): 20 criteria, positive 38 (13 probes, one J4), negatives -20.
- J4 oracle repair: repo_fixed parser/contracts.py `_read` wraps reader errors in ValueError naming the file; make_shipped.py gets the reverse PATCHES so repo_shipped and environment/repo stay byte-identical (rebuild check SHIPPED_SAME, ENV_SAME); solve.py renders 30 repairs.

## P12 fix QC v9 (28 Oct 2026, board c9ea299)
- Judge only: R14 rewritten to a conduct J4 (every private helper under src/migrakit called; shipped `_partner_order` uncalled), R20 narrowed to a check that passed after the last edit (disjoint from R18). Tests, data, docs, instruction byte-unchanged; P-3 lever 90/291 unchanged. a5 predicted judge 8/38 = 21.1%.

## Gate v3.6 harden a6 (28 Oct 2026, board a4f790c): 34 gated large-graph worlds
- Why: run a6 (tests 291/291) planner = A* with the schema-graph lower bound, the same method as the old reference; old worlds' region exits cost 9.0-9.9M, so that bound prunes them (WORK/a6_repo, KILL_TEST.md a4f790c).
- Lever: world_47..world_80_core_gated_graph, tags ("CORE", "GATE"), weight 5 each = 170 of 461 positive (36.9%; band 25-40). Generator `_g_gate` (tests/test_output.py:9542; own stream `_rng(9000 + number)`, degree 5): the `_g_core` corridor plus a cheap region whose 40 cheap exits need `has:<gate>`, a field only a 5-6M edge adds; one hard record per world (child timeout 30 s).
- Reference: `_reference_plan` (:8347) with a stronger consistent remainder, max(schema-graph cost, per-prerequisite-field projected cost `_field_remainders` :8309); output-neutral on every old world, ladder and case (digest46 TOTAL 5f8f9d62... before == after; proto gate.py same 987 calls 0 diff). Max 0.372 s over 300 seeds, 0.20-0.34 s on the 34 worlds (limit 10 s).
- Doc text: none added (K14 repository_contract.md:88-93 states sizes, 10 s per call and 'graphs whose number of distinct paths is far too large to list'; M6-M8 migration_semantics.md:31-44).
- Loss: a6 repo, old oracle, a5, blinds cee149a/4f7606c/d721/d2fb/9179/b686, Opus a4 TIMEOUT (a6 also killed at 4 GiB after 78 s); dominance, signature-keyed, greedy, schema-only WRONG; plain/fast/incumbent/bidirectional Dijkstra, exhaustive, A* schema bound TIMEOUT. Shipped inputs fast for all.
- Oracle: repo_fixed core/planner.py gains `_field_cost_to_target` + `_only`; make_shipped.py one reverse PATCH (import line); solve.py renders 31 repairs (round trip verified); oracle exact on every CORE world 29..80, worst 0.234 s per record.

## Gate v3.7 redesign a6 (board 9111ecc)

This section supersedes the unfinished a4f790c half-build above. The approved build adds 60 gated worlds (300 positive points), not 34. There are 141 registered checks, 135 positive worth 591 and six negative worth 14. New-tier share is 300/591 = 50.76%; all hidden whole-document checks together are 540/591 = 91.37%. No old check was removed or weakened.

The existing _g_core family supplies the corridor and state-changing region. _g_gate changes the region's exits to require a fourth field that only a dear entry edge establishes. Each world uses its own stream and one package call. The planted plan remains reachable and non-empty; the schema-only remainder is optimistic about exits unavailable to the current field state. The reference uses the maximum of schema and per-prerequisite-field projected remainders; it does not assume a particular solver implementation.

Rules: K14 repository_contract.md:88 (bounds and ten seconds per plan), M2 migration_semantics.md:10 (positive integer costs), M3/M4 :13/:17 (field operations), M6 :31 (current-state prerequisites), M7 :35 (revisits), M8 :41 (least cost then edge-id list), and N2-N4 null_semantics.ini:7. No doc or shipped input changed. Generator _g_gate is tests/test_output.py:9542; reference _reference_plan is :8347; per-world child cap is TIME_LIMIT_SEC+5 = 15 s in :9804.

G7: g37_guard.json records 81 old check bodies and weights unchanged; immutable input files unchanged. Docker g37_audit.log records 987 old reference calls unchanged (b0f465e55d9b6d1a), old world documents unchanged, and 300 new shape seeds. Maximum reference call was 0.267 s; maximum construction 0.319 s. Direct oracle final tests passed 591/591; real Harbor gates remain separate.

Master go at 10:05 permits CRASH+TIMEOUT loss up to 60% of positive test weight for this bundle only. The new tier alone costs 50.76% when fully lost; cumulative old-plus-new timeout weight must also be measured, not silently ignored. Final measurements live in COST_TABLE.md and proto/g37_cost_*.json. Existing kill5/kill6 blocks are ALL_DONE and were not rerun.

| Check | Weight | Seed stream | Check body | Owned output |
|---|---|---|---|---|
| world_47_core_gated_graph | 5 | 9000+47 | tests/test_output.py:10401 | one record and its run summary |
| world_48_core_gated_graph | 5 | 9000+48 | tests/test_output.py:10406 | one record and its run summary |
| world_49_core_gated_graph | 5 | 9000+49 | tests/test_output.py:10411 | one record and its run summary |
| world_50_core_gated_graph | 5 | 9000+50 | tests/test_output.py:10416 | one record and its run summary |
| world_51_core_gated_graph | 5 | 9000+51 | tests/test_output.py:10421 | one record and its run summary |
| world_52_core_gated_graph | 5 | 9000+52 | tests/test_output.py:10426 | one record and its run summary |
| world_53_core_gated_graph | 5 | 9000+53 | tests/test_output.py:10431 | one record and its run summary |
| world_54_core_gated_graph | 5 | 9000+54 | tests/test_output.py:10436 | one record and its run summary |
| world_55_core_gated_graph | 5 | 9000+55 | tests/test_output.py:10441 | one record and its run summary |
| world_56_core_gated_graph | 5 | 9000+56 | tests/test_output.py:10446 | one record and its run summary |
| world_57_core_gated_graph | 5 | 9000+57 | tests/test_output.py:10451 | one record and its run summary |
| world_58_core_gated_graph | 5 | 9000+58 | tests/test_output.py:10456 | one record and its run summary |
| world_59_core_gated_graph | 5 | 9000+59 | tests/test_output.py:10461 | one record and its run summary |
| world_60_core_gated_graph | 5 | 9000+60 | tests/test_output.py:10466 | one record and its run summary |
| world_61_core_gated_graph | 5 | 9000+61 | tests/test_output.py:10471 | one record and its run summary |
| world_62_core_gated_graph | 5 | 9000+62 | tests/test_output.py:10476 | one record and its run summary |
| world_63_core_gated_graph | 5 | 9000+63 | tests/test_output.py:10481 | one record and its run summary |
| world_64_core_gated_graph | 5 | 9000+64 | tests/test_output.py:10486 | one record and its run summary |
| world_65_core_gated_graph | 5 | 9000+65 | tests/test_output.py:10491 | one record and its run summary |
| world_66_core_gated_graph | 5 | 9000+66 | tests/test_output.py:10496 | one record and its run summary |
| world_67_core_gated_graph | 5 | 9000+67 | tests/test_output.py:10501 | one record and its run summary |
| world_68_core_gated_graph | 5 | 9000+68 | tests/test_output.py:10506 | one record and its run summary |
| world_69_core_gated_graph | 5 | 9000+69 | tests/test_output.py:10511 | one record and its run summary |
| world_70_core_gated_graph | 5 | 9000+70 | tests/test_output.py:10516 | one record and its run summary |
| world_71_core_gated_graph | 5 | 9000+71 | tests/test_output.py:10521 | one record and its run summary |
| world_72_core_gated_graph | 5 | 9000+72 | tests/test_output.py:10526 | one record and its run summary |
| world_73_core_gated_graph | 5 | 9000+73 | tests/test_output.py:10531 | one record and its run summary |
| world_74_core_gated_graph | 5 | 9000+74 | tests/test_output.py:10536 | one record and its run summary |
| world_75_core_gated_graph | 5 | 9000+75 | tests/test_output.py:10541 | one record and its run summary |
| world_76_core_gated_graph | 5 | 9000+76 | tests/test_output.py:10546 | one record and its run summary |
| world_77_core_gated_graph | 5 | 9000+77 | tests/test_output.py:10551 | one record and its run summary |
| world_78_core_gated_graph | 5 | 9000+78 | tests/test_output.py:10556 | one record and its run summary |
| world_79_core_gated_graph | 5 | 9000+79 | tests/test_output.py:10561 | one record and its run summary |
| world_80_core_gated_graph | 5 | 9000+80 | tests/test_output.py:10566 | one record and its run summary |
| world_81_core_gated_graph | 5 | 9000+81 | tests/test_output.py:10571 | one record and its run summary |
| world_82_core_gated_graph | 5 | 9000+82 | tests/test_output.py:10576 | one record and its run summary |
| world_83_core_gated_graph | 5 | 9000+83 | tests/test_output.py:10581 | one record and its run summary |
| world_84_core_gated_graph | 5 | 9000+84 | tests/test_output.py:10586 | one record and its run summary |
| world_85_core_gated_graph | 5 | 9000+85 | tests/test_output.py:10591 | one record and its run summary |
| world_86_core_gated_graph | 5 | 9000+86 | tests/test_output.py:10596 | one record and its run summary |
| world_87_core_gated_graph | 5 | 9000+87 | tests/test_output.py:10601 | one record and its run summary |
| world_88_core_gated_graph | 5 | 9000+88 | tests/test_output.py:10606 | one record and its run summary |
| world_89_core_gated_graph | 5 | 9000+89 | tests/test_output.py:10611 | one record and its run summary |
| world_90_core_gated_graph | 5 | 9000+90 | tests/test_output.py:10616 | one record and its run summary |
| world_91_core_gated_graph | 5 | 9000+91 | tests/test_output.py:10621 | one record and its run summary |
| world_92_core_gated_graph | 5 | 9000+92 | tests/test_output.py:10626 | one record and its run summary |
| world_93_core_gated_graph | 5 | 9000+93 | tests/test_output.py:10631 | one record and its run summary |
| world_94_core_gated_graph | 5 | 9000+94 | tests/test_output.py:10636 | one record and its run summary |
| world_95_core_gated_graph | 5 | 9000+95 | tests/test_output.py:10641 | one record and its run summary |
| world_96_core_gated_graph | 5 | 9000+96 | tests/test_output.py:10646 | one record and its run summary |
| world_97_core_gated_graph | 5 | 9000+97 | tests/test_output.py:10651 | one record and its run summary |
| world_98_core_gated_graph | 5 | 9000+98 | tests/test_output.py:10656 | one record and its run summary |
| world_99_core_gated_graph | 5 | 9000+99 | tests/test_output.py:10661 | one record and its run summary |
| world_100_core_gated_graph | 5 | 9000+100 | tests/test_output.py:10666 | one record and its run summary |
| world_101_core_gated_graph | 5 | 9000+101 | tests/test_output.py:10671 | one record and its run summary |
| world_102_core_gated_graph | 5 | 9000+102 | tests/test_output.py:10676 | one record and its run summary |
| world_103_core_gated_graph | 5 | 9000+103 | tests/test_output.py:10681 | one record and its run summary |
| world_104_core_gated_graph | 5 | 9000+104 | tests/test_output.py:10686 | one record and its run summary |
| world_105_core_gated_graph | 5 | 9000+105 | tests/test_output.py:10691 | one record and its run summary |
| world_106_core_gated_graph | 5 | 9000+106 | tests/test_output.py:10696 | one record and its run summary |
