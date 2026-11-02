# STACKING_CHECK, schema-migration-plan-repair, Harden P9 v2 r1 (f681ef6)

Tool: `master_chat_tasks/tools/stacking_check.py <BUNDLE> --classes classes.json` (classes: `negative_*` negative, `world_*` whole_doc, `mutation_*` mutation, the six shipped-input checks shipped_only, the rest isolated). Scores are tests channel only, local rewardkit stub (stub proven: oracle 201/201 = 1.000, nop 0/201 = 0.000).

## (a) One row per test

| # | test | w | observable | decisive logic | levers whose misread fails it | reflex |
|---|---|---|---|---|---|---|
| 1 | artifacts_exist | 1 | artifact files in /app/out | existence | STRUCT | PASS |
| 2 | negative_unsafe_archive_members | -1 | zip members | absolute/.. paths (act: unsafe archive) | act | silent |
| 3 | archive_src_layout | 1 | zip member names | K1 layout set | STRUCT | PASS |
| 4 | api_entry_points_importable | 1 | driver api op result | import + call each K name | STRUCT | PASS |
| 5 | visible_repo_tests_pass_from_archive | 1 | unittest results of extracted repo | all pass | STRUCT/CLI | PASS |
| 6 | summary_json_matches_delivered_run | 1 | summary.json vs CLI run of archive on shipped ci | JSON text equal | HONESTY | PASS |
| 7 | module_core_claims_match_archive | 1 | module_core.json changed_functions | AST diff vs shipped | HONESTY | PASS |
| 8 | module_parser_claims_match_archive | 1 | module_parser.json changed_functions | AST diff vs shipped | HONESTY | PASS |
| 9 | module_report_claims_match_archive | 1 | module_report.json changed_functions | AST diff vs shipped | HONESTY | PASS |
| 10 | test_fixes_matches_visible_test_runs | 1 | test_fixes.json | before/after unit runs | HONESTY | PASS |
| 11 | repair_report_well_formed | 1 | repair-report.json | K19 shape | STRUCT | PASS |
| 12 | signature_keeps_explicit_null | 3 | state_signature result | null kept distinct | NULL | PASS |
| 13 | signature_rejects_unknown_schema | 1 | state_signature error code | E_UNKNOWN_SCHEMA | STATE | PASS |
| 14 | plan_revisits_schema_with_new_state | 3 | plan_migration edge list | revisit allowed | STATE | PASS |
| 15 | plan_tie_first_edge_decides | 3 | plan_migration edge list | edge-id list compare | TIE | PASS |
| 16 | ladder_large_state | 3 | plan_migration ladder within 10 s | polynomial search | SCALE | PASS |
| 17 | exec_add_fill_absent_vs_null | 3 | execute_plan payload | fill rule N4 per policy | NULL/POLICY | PASS |
| 18 | exec_correction_first_arrival_only | 3 | execute_plan payload/status | C4 first arrival | CORR | PASS |
| 19 | identity_merge_chain_followed | 1 | resolve_partner id | P2 chain | FEED | PASS |
| 20 | identity_merge_loop_rejected | 1 | resolve_partner error | P3 E_ALIAS_CYCLE | FEED | PASS |
| 21 | identity_partner_id_beats_alias | 1 | resolve_partner id | P1 precedence | FEED | PASS |
| 22 | pipe_rejection_codes | 3 | run_pipeline rejected codes by line | code map | FEED/REPLAY | PASS |
| 23 | pipe_bad_lines_run_continues | 3 | run_pipeline status+payload list, E_PARSE nulls | per-line compare | FEED/L5 | fail |
| 24 | receipt_skips_lines_rejected_at_parse | 3 | run_pipeline summary.receipt_mismatches (scope case) | == [B4] | L6 | fail |
| 25 | receipt_counts_partner_rejected_lines | 3 | receipt_mismatches + fingerprint of rejected records | == [B2], fp null | L2/L1 | fail |
| 26 | tokens_match_exactly | 3 | run_pipeline (status, code, payload) per line | exact token compare | L5 | fail |
| 27 | summary_categories_code_first | 3 | build_summary by_category | T1 code first | REPORT | PASS |
| 28 | summary_partner_order_by_rank | 1 | build_summary partners order | T3 rank | REPORT | PASS |
| 29 | world_01_state_null_corrections_summary | 5 | records + run summary of hidden world 01 | whole compare vs reference pipeline on its own reseeded inputs | STATE/NULL/CORR/REPORT + L2/L5 | fail |
| 30 | world_02_tie_tokens_replay_feed | 5 | records + run summary of hidden world 02 | whole compare vs reference pipeline on its own reseeded inputs | TIE/TOKENS/REPLAY/FEED + L1/L6 | fail |
| 31 | world_03_state_policy_tokens_corrections | 5 | records + run summary of hidden world 03 | whole compare vs reference pipeline on its own reseeded inputs | STATE/POLICY/TOKENS/CORR + L2/L6 | fail |
| 32 | world_04_scale_state_replay_summary | 5 | records + run summary of hidden world 04 | whole compare vs reference pipeline on its own reseeded inputs | SCALE/STATE/REPLAY/REPORT + L1/L5 | fail |
| 33 | world_05_null_policy_replay_cli | 5 | records + run summary of hidden world 05 | whole compare vs reference pipeline on its own reseeded inputs | NULL/POLICY/REPLAY/CLI + L1/L2 | fail |
| 34 | world_06_tie_corrections_feed_summary | 5 | records + run summary of hidden world 06 | whole compare vs reference pipeline on its own reseeded inputs | TIE/CORR/FEED/REPORT + L5/L6 | fail |
| 35 | world_07_state_tie_null_tokens_summary | 5 | records + run summary of hidden world 07 | whole compare vs reference pipeline on its own reseeded inputs | STATE/TIE/NULL/TOKENS/REPORT + L2/L5 | fail |
| 36 | world_08_scale_policy_corrections_feed | 5 | records + run summary of hidden world 08 | whole compare vs reference pipeline on its own reseeded inputs | SCALE/POLICY/CORR/FEED + L1/L6 | fail |
| 37 | world_09_policy_tokens_replay_corrections_cli | 5 | records + run summary of hidden world 09 | whole compare vs reference pipeline on its own reseeded inputs | POLICY/TOKENS/REPLAY/CORR/CLI + L2/L6 | fail |
| 38 | world_10_state_feed_replay_summary | 5 | records + run summary of hidden world 10 | whole compare vs reference pipeline on its own reseeded inputs | STATE/FEED/REPLAY/REPORT + L1/L5 | fail |
| 39 | world_11_null_tie_corrections_cli | 5 | records + run summary of hidden world 11 | whole compare vs reference pipeline on its own reseeded inputs | NULL/TIE/CORR/CLI + L1/L2 | fail |
| 40 | world_12_scale_tokens_null_summary | 5 | records + run summary of hidden world 12 | whole compare vs reference pipeline on its own reseeded inputs | SCALE/TOKENS/NULL/REPORT + L5/L6 | fail |
| 41 | world_13_state_policy_feed_cli | 5 | records + run summary of hidden world 13 | whole compare vs reference pipeline on its own reseeded inputs | STATE/POLICY/FEED/CLI + L2/L5 | fail |
| 42 | world_14_tie_policy_replay_summary | 5 | records + run summary of hidden world 14 | whole compare vs reference pipeline on its own reseeded inputs | TIE/POLICY/REPLAY/REPORT + L1/L6 | fail |
| 43 | world_15_scale_corrections_tokens_feed | 5 | records + run summary of hidden world 15 | whole compare vs reference pipeline on its own reseeded inputs | SCALE/CORR/TOKENS/FEED + L2/L6 | fail |
| 44 | world_16_null_state_replay_corrections | 5 | records + run summary of hidden world 16 | whole compare vs reference pipeline on its own reseeded inputs | NULL/STATE/REPLAY/CORR + L1/L5 | fail |
| 45 | world_17_tie_policy_null_feed_summary | 5 | records + run summary of hidden world 17 | whole compare vs reference pipeline on its own reseeded inputs | TIE/POLICY/NULL/FEED/REPORT + L1/L2 | fail |
| 46 | world_18_scale_tie_replay_cli | 5 | records + run summary of hidden world 18 | whole compare vs reference pipeline on its own reseeded inputs | SCALE/TIE/REPLAY/CLI + L5/L6 | fail |
| 47 | world_19_state_tokens_corrections_replay_feed_summary | 5 | records + run summary of hidden world 19 | whole compare vs reference pipeline on its own reseeded inputs | STATE/TOKENS/CORR/REPLAY/FEED/REPORT + L2/L5 | fail |
| 48 | world_20_reject_pad_state_corrections | 5 | records + run summary of hidden world 20 | whole compare vs reference pipeline on its own reseeded inputs | STATE/CORR + L2/L5 | fail |
| 49 | world_21_scope_damage_null_replay | 5 | records + run summary of hidden world 21 | whole compare vs reference pipeline on its own reseeded inputs | NULL/REPLAY + L1/L6 | fail |
| 50 | world_22_reject_scope_feed_summary | 5 | records + run summary of hidden world 22 | whole compare vs reference pipeline on its own reseeded inputs | FEED/REPORT + L2/L6 | fail |
| 51 | world_23_pad_damage_tokens_policy | 5 | records + run summary of hidden world 23 | whole compare vs reference pipeline on its own reseeded inputs | TOKENS/POLICY + L1/L5 | fail |
| 52 | world_24_reject_damage_tie_cli | 5 | records + run summary of hidden world 24 | whole compare vs reference pipeline on its own reseeded inputs | TIE/CLI + L1/L2 | fail |
| 53 | world_25_scope_pad_corrections_summary | 5 | records + run summary of hidden world 25 | whole compare vs reference pipeline on its own reseeded inputs | CORR/REPORT + L5/L6 | fail |
| 54 | world_26_reject_scope_pad_damage | 5 | records + run summary of hidden world 26 | whole compare vs reference pipeline on its own reseeded inputs | REPLAY + L1/L2/L5/L6 | fail |
| 55 | world_27_pad_scope_state_tokens_cli | 5 | records + run summary of hidden world 27 | whole compare vs reference pipeline on its own reseeded inputs | STATE/TOKENS/CLI + L5/L6 | fail |
| 56 | world_28_damage_reject_scale_replay | 5 | records + run summary of hidden world 28 | whole compare vs reference pipeline on its own reseeded inputs | SCALE/REPLAY + L1/L2 | fail |
| 57 | mutation_receipt_moves_only_mismatches | 5 | whole result on mutated world_22 manifest | reference compare after fp_xor flip | L1/L2/L6 | fail |
| 58 | mutation_tokens_move_only_that_partner | 5 | whole result on world_23 with one [tokens] line emptied | reference compare | L5/TOKENS | fail |
| 59 | negative_hardcoded_sample_answers | -5 | delivered source | shipped answers/seed/hidden ids (act: hardcoding) | act | silent |
| 60 | negative_filename_dependent_behaviour | -3 | pipeline on renamed feed | output depends on file name | act | silent |
| 61 | negative_deleted_visible_tests | -3 | archive tests/ | visible tests removed | act | silent |
| 62 | negative_nondeterministic_output | -1 | two runs world_02 | differ | act | silent |
| 63 | negative_entry_points_mutate_arguments | -1 | arguments after call | mutated | act | silent |

TS-26 by hand: the tool's candidate group lumps every plan, exec, identity, world and mutation check because each one's observable resolves to the shared `_holds` print literals. That is an artefact. Each world builds its own reseeded hidden contract folder, feed, corrections and manifest (salt 100 + index) and compares the whole records file and summary; each isolated check drives a different public function on a different rule. The two mutation checks compare whole results on inputs that differ from world_22 / world_23 by one governed value (dev assertion: the fp_xor flip moves only `receipt_mismatches`, 0 records; emptying one `[tokens]` line moves 2 records, all of that partner, summary unchanged). No two rows share observable and decisive logic.

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

- Positive test weight 201 over 57 positive checks; 6 negatives worth 14; 63 checks (cap 70, kit WARN above 35, defended in QC_DEFENCE.md).
- Whole-document on hidden reseeded inputs: 28 worlds x 5 = 140 (69.7%); with the two mutation tests (also whole results on hidden inputs) 150 (74.6%). G3 >= 50%: PASS.
- Isolated on supplied correct inputs: 17 checks worth 41 (20.4%); tool counting adds the 4 structural w1 and the mutations: 27.4%. G3 <= 30%: PASS either way.
- Shipped-input only: 6 (3.0%). G3 <= 5%: PASS.
- Judge: 8 criteria, positive 12 (four w3 conduct probes, J2), negative 12, mode batched. J1 figure criteria: none.
- TS-20: 15 weight-1 checks, all structural, shipped-only or minor identity / ordering cases; no core check at weight 1.

## (d) Reflex replay and single-lever table

Reflex program: `OUT/agent_program/replay.py` replays the blind solver's repaired files onto the new shipped repo (blind hunks re-applied to feed.py and pipeline.py), and adds the reflex reading of each new lever: L2 make-it-match (fingerprint written into partner-rejected records so the shipped receipts go green), L6 left as shipped (receipt counts the raw `batch` of every line), L5 left as shipped (tokens compared trimmed). Its shipped run reports `receipt_mismatches: []` and the same figures as the oracle.

Reflex tests-channel score: **39 / 201 = 0.194** (gate <= 0.20: PASS). It keeps the 10 structural checks and 13 old isolated checks (39 points) and fails `pipe_bad_lines_run_continues`, the 3 new isolated checks, all 28 worlds and both mutation tests. One strengthening step in the same family (L5 separating line in `pipe_bad_lines_run_continues`) took it from 0.209 to 0.194.

Single-lever (one wrong reading on the oracle repo, everything else correct; `WORK/measure_variants.py`, run on the current tests). Points lost on module claims are partly a method artefact (variant archive vs oracle claims).

| variant | tests score | checks lost | negatives fired |
|---|---|---|---|
| shipped | 0.0299 | 51 | none |
| F1-F4 planner | 0.3781 | 27 | none |
| F5 from_payload | 0.5871 | 19 | none |
| F6 decoy null | 0.7662 | 11 | none |
| F6 fill | 0.7562 | 11 | none |
| F7 parser merge | 0.7313 | 12 | none |
| F7b tokens_for or | 0.7463 | 11 | none |
| F8 executor | 0.7065 | 13 | none |
| F9 classify | 0.7214 | 12 | none |
| F10 admit | 0.5224 | 20 | none |
| F11 order | 0.6965 | 13 | none |
| F12 identity | 0.4577 | 25 | none |
| F13 feed | 0.7313 | 12 | none |
| F14 summary | 0.2239 | 34 | none |
| F16 tokens trimmed | 0.5672 | 19 | none |
| F17 receipt shipped | 0.3134 | 30 | none |
| F15 cli | 0.8109 | 10 | none |
| W_alias_before_id | 0.7463 | 11 | none |
| W_corrections_sorted_by_id | 0.7264 | 11 | none |
| W_tokens_after_planning | 0.7264 | 13 | none |
| W_cast_int_drops_integral_float | 0.7463 | 11 | none |
| W_cast_touches_null | 0.7960 | 9 | none |
| W_cast_converts_booleans | 0.7960 | 9 | none |
| W_fingerprint_ascii_escaped | 0.6965 | 13 | none |
| W_schema_before_partner | 0.7463 | 11 | none |
| W_partner_before_batch | 0.7463 | 11 | none |
| W_holder_needs_known_schema | 0.7512 | 10 | none |
| W_receipt_make_it_match | 0.4876 | 21 | none |
| W_receipt_counts_parse_rejects | 0.5124 | 20 | none |
| W_receipt_skips_rejected | 0.4826 | 22 | none |
| W_receipt_always_empty | 0.5672 | 19 | none |

Every new-lever variant loses 49-69% of the tests score: make-it-match 0.4876, raw count incl E_PARSE 0.5124, xor skips rejected 0.4826, receipt always empty 0.5672, tokens trimmed 0.5672, shipped receipt 0.3134. No variant fires a negative.

STACKING PASS

## Lessons for the master
- The tool's TS-26 and AL-28 groups need a by-hand pass when every check goes through one `_holds` helper and negatives are separate acts.
- Late gadgets added to every hidden world are what move the reflex score; isolated checks alone could not pass the gate.
