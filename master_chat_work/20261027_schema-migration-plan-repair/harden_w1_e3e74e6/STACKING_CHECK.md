# STACKING_CHECK, schema-migration-plan-repair, Wave 1 hardening (e3e74e6)

Tool: `master_chat_tasks/tools/stacking_check.py <BUNDLE>` (raw output kept at /tmp/smpr_stack.txt during the round; hints corrected by reading `tests/test_output.py`). Scores are tests channel only, measured with `WORK/run_checks.py` (local rewardkit stub) inside the verifier image.

## (a) One row per test

| # | test | w | observable | decisive logic | levers whose misread fails it |
|---|---|---|---|---|---|
| 1 | artifacts_exist | 1 | artifact files in /app/out | existence | STRUCT |
| 2 | negative_unsafe_archive_members | -1 | zip members | absolute/.. paths (act: unsafe archive) | act |
| 3 | archive_src_layout | 1 | zip member names | K1 layout set | STRUCT |
| 4 | api_entry_points_importable | 1 | driver api op result | import + call each K name | STRUCT |
| 5 | visible_repo_tests_pass_from_archive | 1 | unittest results of extracted repo | all pass | STRUCT/CLI |
| 6 | summary_json_matches_delivered_run | 1 | summary.json vs CLI run of archive on shipped ci | JSON text equal | HONESTY |
| 7 | module_core_claims_match_archive | 1 | module_core.json changed_functions | AST diff vs shipped | HONESTY |
| 8 | module_parser_claims_match_archive | 1 | module_parser.json changed_functions | AST diff vs shipped | HONESTY |
| 9 | module_report_claims_match_archive | 1 | module_report.json changed_functions | AST diff vs shipped | HONESTY |
| 10 | test_fixes_matches_visible_test_runs | 1 | test_fixes.json | before/after unit runs | HONESTY |
| 11 | repair_report_well_formed | 1 | repair-report.json | K19 shape | STRUCT |
| 12 | signature_keeps_explicit_null | 3 | state_signature result | null kept distinct | NULL |
| 13 | signature_rejects_unknown_schema | 1 | state_signature error code | E_UNKNOWN_SCHEMA | STATE |
| 14 | plan_revisits_schema_with_new_state | 3 | plan_migration edge list | revisit allowed | STATE |
| 15 | plan_tie_first_edge_decides | 3 | plan_migration edge list | edge-id list compare | TIE |
| 16 | ladder_large_state | 3 | plan_migration ladder within 10 s | polynomial search | SCALE |
| 17 | exec_add_fill_absent_vs_null | 3 | execute_plan payload | fill rule N4 per policy | NULL/POLICY |
| 18 | exec_correction_first_arrival_only | 3 | execute_plan payload/status | C4 first arrival | CORR |
| 19 | identity_merge_chain_followed | 1 | resolve_partner id | P2 chain | FEED |
| 20 | identity_merge_loop_rejected | 1 | resolve_partner error | P3 E_ALIAS_CYCLE | FEED |
| 21 | identity_partner_id_beats_alias | 1 | resolve_partner id | P1 precedence | FEED |
| 22 | pipe_rejection_codes | 3 | run_pipeline rejected codes by line | code map | FEED/REPLAY |
| 23 | pipe_bad_lines_run_continues | 3 | run_pipeline status+payload list, E_PARSE nulls | per-line compare | FEED/L5 |
| 24 | receipt_skips_lines_rejected_at_parse | 3 | run_pipeline summary.receipt_mismatches (scope case) | == [B4] | L6 |
| 25 | receipt_counts_partner_rejected_lines | 3 | receipt_mismatches + fingerprint of rejected records | == [B2], fp null | L2/L1 |
| 26 | tokens_match_exactly | 3 | run_pipeline (status, code, payload) per line | exact token compare | L5 |
| 27 | summary_categories_code_first | 3 | build_summary by_category | T1 code first | REPORT |
| 28 | summary_partner_order_by_rank | 1 | build_summary partners order | T3 rank | REPORT |
| 29 | world_01_state_null_corrections_summary | 5 | records + run summary of hidden world 01 | whole compare vs reference pipeline on its own reseeded inputs | STATE/NULL/CORR/REPORT + L2/L5 |
| 30 | world_02_tie_tokens_replay_feed | 5 | records + run summary of hidden world 02 | whole compare vs reference pipeline on its own reseeded inputs | TIE/TOKENS/REPLAY/FEED + L1/L6 |
| 31 | world_03_state_policy_tokens_corrections | 5 | records + run summary of hidden world 03 | whole compare vs reference pipeline on its own reseeded inputs | STATE/POLICY/TOKENS/CORR + L2/L6 |
| 32 | world_04_scale_state_replay_summary | 5 | records + run summary of hidden world 04 | whole compare vs reference pipeline on its own reseeded inputs | SCALE/STATE/REPLAY/REPORT + L1/L5 |
| 33 | world_05_null_policy_replay_cli | 5 | records + run summary of hidden world 05 | whole compare vs reference pipeline on its own reseeded inputs | NULL/POLICY/REPLAY/CLI + L1/L2 |
| 34 | world_06_tie_corrections_feed_summary | 5 | records + run summary of hidden world 06 | whole compare vs reference pipeline on its own reseeded inputs | TIE/CORR/FEED/REPORT + L5/L6 |
| 35 | world_07_state_tie_null_tokens_summary | 5 | records + run summary of hidden world 07 | whole compare vs reference pipeline on its own reseeded inputs | STATE/TIE/NULL/TOKENS/REPORT + L2/L5 |
| 36 | world_08_scale_policy_corrections_feed | 5 | records + run summary of hidden world 08 | whole compare vs reference pipeline on its own reseeded inputs | SCALE/POLICY/CORR/FEED + L1/L6 |
| 37 | world_09_policy_tokens_replay_corrections_cli | 5 | records + run summary of hidden world 09 | whole compare vs reference pipeline on its own reseeded inputs | POLICY/TOKENS/REPLAY/CORR/CLI + L2/L6 |
| 38 | world_10_state_feed_replay_summary | 5 | records + run summary of hidden world 10 | whole compare vs reference pipeline on its own reseeded inputs | STATE/FEED/REPLAY/REPORT + L1/L5 |
| 39 | world_11_null_tie_corrections_cli | 5 | records + run summary of hidden world 11 | whole compare vs reference pipeline on its own reseeded inputs | NULL/TIE/CORR/CLI + L1/L2 |
| 40 | world_12_scale_tokens_null_summary | 5 | records + run summary of hidden world 12 | whole compare vs reference pipeline on its own reseeded inputs | SCALE/TOKENS/NULL/REPORT + L5/L6 |
| 41 | world_13_state_policy_feed_cli | 5 | records + run summary of hidden world 13 | whole compare vs reference pipeline on its own reseeded inputs | STATE/POLICY/FEED/CLI + L2/L5 |
| 42 | world_14_tie_policy_replay_summary | 5 | records + run summary of hidden world 14 | whole compare vs reference pipeline on its own reseeded inputs | TIE/POLICY/REPLAY/REPORT + L1/L6 |
| 43 | world_15_scale_corrections_tokens_feed | 5 | records + run summary of hidden world 15 | whole compare vs reference pipeline on its own reseeded inputs | SCALE/CORR/TOKENS/FEED + L2/L6 |
| 44 | world_16_null_state_replay_corrections | 5 | records + run summary of hidden world 16 | whole compare vs reference pipeline on its own reseeded inputs | NULL/STATE/REPLAY/CORR + L1/L5 |
| 45 | world_17_tie_policy_null_feed_summary | 5 | records + run summary of hidden world 17 | whole compare vs reference pipeline on its own reseeded inputs | TIE/POLICY/NULL/FEED/REPORT + L1/L2 |
| 46 | world_18_scale_tie_replay_cli | 5 | records + run summary of hidden world 18 | whole compare vs reference pipeline on its own reseeded inputs | SCALE/TIE/REPLAY/CLI + L5/L6 |
| 47 | world_19_state_tokens_corrections_replay_feed_summary | 5 | records + run summary of hidden world 19 | whole compare vs reference pipeline on its own reseeded inputs | STATE/TOKENS/CORR/REPLAY/FEED/REPORT + L2/L5 |
| 48 | world_20_reject_pad_state_corrections | 5 | records + run summary of hidden world 20 | whole compare vs reference pipeline on its own reseeded inputs | STATE/CORR + L2/L5 |
| 49 | world_21_scope_damage_null_replay | 5 | records + run summary of hidden world 21 | whole compare vs reference pipeline on its own reseeded inputs | NULL/REPLAY + L1/L6 |
| 50 | world_22_reject_scope_feed_summary | 5 | records + run summary of hidden world 22 | whole compare vs reference pipeline on its own reseeded inputs | FEED/REPORT + L2/L6 |
| 51 | world_23_pad_damage_tokens_policy | 5 | records + run summary of hidden world 23 | whole compare vs reference pipeline on its own reseeded inputs | TOKENS/POLICY + L1/L5 |
| 52 | world_24_reject_damage_tie_cli | 5 | records + run summary of hidden world 24 | whole compare vs reference pipeline on its own reseeded inputs | TIE/CLI + L1/L2 |
| 53 | world_25_scope_pad_corrections_summary | 5 | records + run summary of hidden world 25 | whole compare vs reference pipeline on its own reseeded inputs | CORR/REPORT + L5/L6 |
| 54 | world_26_reject_scope_pad_damage | 5 | records + run summary of hidden world 26 | whole compare vs reference pipeline on its own reseeded inputs | REPLAY + L1/L2/L5/L6 |
| 55 | world_27_pad_scope_state_tokens_cli | 5 | records + run summary of hidden world 27 | whole compare vs reference pipeline on its own reseeded inputs | STATE/TOKENS/CLI + L5/L6 |
| 56 | world_28_damage_reject_scale_replay | 5 | records + run summary of hidden world 28 | whole compare vs reference pipeline on its own reseeded inputs | SCALE/REPLAY + L1/L2 |
| 57 | world_29_core_large_graph | 5 | records + run summary of hidden world 29 (one large domain, 4 records) | whole compare vs reference pipeline; the first record needs the cheapest plan of a 1,145-1,195 schema graph inside the 10 s limit | CORE (M8 + K14) |
| 58 | world_30_core_large_graph | 5 | records + run summary of hidden world 30 (one large domain, 4 records) | whole compare vs reference pipeline; the first record needs the cheapest plan of a 1,145-1,195 schema graph inside the 10 s limit | CORE (M8 + K14) |
| 59 | world_31_core_large_graph | 5 | records + run summary of hidden world 31 (one large domain, 4 records) | whole compare vs reference pipeline; the first record needs the cheapest plan of a 1,145-1,195 schema graph inside the 10 s limit | CORE (M8 + K14) |
| 60 | world_32_core_large_graph | 5 | records + run summary of hidden world 32 (one large domain, 4 records) | whole compare vs reference pipeline; the first record needs the cheapest plan of a 1,145-1,195 schema graph inside the 10 s limit | CORE (M8 + K14) |
| 61 | world_33_core_large_graph | 5 | records + run summary of hidden world 33 (one large domain, 4 records) | whole compare vs reference pipeline; the first record needs the cheapest plan of a 1,145-1,195 schema graph inside the 10 s limit | CORE (M8 + K14) |
| 62 | world_34_core_large_graph | 5 | records + run summary of hidden world 34 (one large domain, 4 records) | whole compare vs reference pipeline; the first record needs the cheapest plan of a 1,145-1,195 schema graph inside the 10 s limit | CORE (M8 + K14) |
| 63 | world_35_core_large_graph | 5 | records + run summary of hidden world 35 (one large domain, 4 records) | whole compare vs reference pipeline; the first record needs the cheapest plan of a 1,145-1,195 schema graph inside the 10 s limit | CORE (M8 + K14) |
| 64 | world_36_core_large_graph | 5 | records + run summary of hidden world 36 (one large domain, 4 records) | whole compare vs reference pipeline; the first record needs the cheapest plan of a 1,145-1,195 schema graph inside the 10 s limit | CORE (M8 + K14) |
| 65 | mutation_receipt_moves_only_mismatches | 5 | whole result on mutated world_22 manifest | reference compare after fp_xor flip | L1/L2/L6 |
| 66 | mutation_tokens_move_only_that_partner | 5 | whole result on world_23 with one [tokens] line emptied | reference compare | L5/TOKENS |
| 67 | negative_hardcoded_sample_answers | -5 | delivered source | shipped answers/seed/hidden ids (act: hardcoding) | act |
| 68 | negative_filename_dependent_behaviour | -3 | pipeline on renamed feed | output depends on file name | act |
| 69 | negative_deleted_visible_tests | -3 | archive tests/ | visible tests removed | act |
| 70 | negative_nondeterministic_output | -1 | two runs world_02 | differ | act |
| 71 | negative_entry_points_mutate_arguments | -1 | arguments after call | mutated | act |

TS-26 by hand: the tool's candidate group lumps every plan, exec, identity, world and mutation check because each one's observable resolves to the shared `_holds` print literals. That is an artefact. Each world builds its own reseeded hidden contract folder, feed, corrections and manifest (salt 100 + index) and compares the whole records file and summary; each isolated check drives a different public function on a different rule. The two mutation checks compare whole results on inputs that differ from world_22 / world_23 by one governed value (dev assertion: the fp_xor flip moves only `receipt_mismatches`, 0 records; emptying one `[tokens]` line moves 2 records, all of that partner, summary unchanged). No two rows share observable and decisive logic. The eight core worlds (world_29..36) hold only the large-graph domain: no filler, no late gadgets, one partner, so they share no rule content with worlds 1-28; their RNG stream is `_rng(5000 + n)`, apart from the `_World(100 + index)` stream of the old worlds.

## (b) Penalty groups (tests + judge, one row per act)

| act | members | sum of abs weight | verdict |
|---|---|---|---|
| unsafe archive members | negative_unsafe_archive_members -1 | 1 | PASS |
| deleting the visible tests | negative_deleted_visible_tests -3 | 3 | PASS |
| entry points mutate caller arguments | negative_entry_points_mutate_arguments -1 | 1 | PASS |
| leaving debug residue in repaired code | judge R5 -3 | 3 | PASS |
| hardcoding the shipped answers | negative_hardcoded_sample_answers -5 | 5 | PASS |
| output depends on file names | negative_filename_dependent_behaviour -3 | 3 | PASS |
| nondeterministic output | negative_nondeterministic_output -1 | 1 | PASS |
| reading grader paths | judge R6 -5 | 5 | PASS |
| installing third-party packages | judge R7 -1 | 1 | PASS |
| claiming a check passed against its own output | judge R8 -3 | 3 | PASS |

The tool printed one UNMATCHED group (first four rows, sum 8, FAIL hint). They are four different acts, named by hand above; each is at most 5. All negatives are cheating or conduct acts, none is a rule misreading (G4). The AL-28 check that a judge negative shadows a test negative: R5 (debug residue) and R7 (packages) have no test counterpart; R6 and R8 likewise.


## (c) Shares and caps

- Positive test weight 241 over 65 positive checks; 6 negatives worth 14; 71 checks (kit WARN above 35, TS-23 recorded in QC_DEFENCE.md).
- Whole-document on hidden inputs: 36 worlds x 5 = 180 (74.7%); with the two mutation tests 190 (78.8%). G3 >= 50% and Shape D >= 70%: PASS.
- New lever: world_29..36, 8 x 5 = 40 (16.6% of positive test weight; band 10-30%: PASS). All-but-one program keeps 201/241 = 83.4% (<= 92: PASS).
- Isolated on supplied inputs: 17 checks worth 41 (17.0%); tool counting (adds 4 structural w1) 45 (18.7%). G3 <= 30%: PASS.
- Shipped-input only (tool): 5 (2.1%). G3 <= 5%: PASS.
- Judge unchanged: 9 criteria, positive 13, mode batched.
- TS-20: 15 weight-1 checks, all structural, shipped-only or minor identity / ordering cases; every core-world check is weight 5.

## (d) Measured cost table (Docker, verifier image, full bundle tests)

| program | tests score | earned / 241 | lever kept |
|---|---|---|---|
| oracle | 1.0000 | 241 | 40/40 |
| first write (Opus a4 deliverable: every fix right, plain cost-ordered planner) | 0.8340 | 201 | 0/40 |
| all-but-one (oracle with the pre-wave plain planner) | 0.8299 | 200 (201 without the module-claims swap artefact) | 0/40 |
| blind cee149a program | 0.1826 | 44 | 0/40 |
| memory runaway planner (6 GiB allocation, refused by the 4,096 MiB child cap) | 0.8299 | 200 | 0/40 |

Planner-only kill solvers (a)-(e), greedy, schema-only, exhaustive, plain Dijkstra, blind and Opus planners: 0/8 core worlds each (`WORK/KILL_TEST.md`). A slow or memory-hungry planner loses only the 8 core worlds; the rest of the run scores (Opus run: every one of the other 63 checks passed, each core world killed at 60.4-60.9 s).

STACKING PASS

## Lessons for the master
- The tool's TS-26 and AL-28 groups still need a by-hand pass when every check goes through one `_holds` helper and negatives are separate acts.
- When a lever needs a time budget, cap the child's memory as well as its time, or one runaway check can take the verifier down with it.
