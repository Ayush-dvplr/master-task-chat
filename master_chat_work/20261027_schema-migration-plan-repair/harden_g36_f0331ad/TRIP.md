# Trajectory read-out: /Users/mac/Desktop/Terminal Bench/master_chat_work/20261027_schema-migration-plan-repair/gate_run_a5/run

- final 68.62; agent steps 86; cost_usd 7.342618749999999
- judge: 7/13 (53.85%)
- test_output: 201/241 (83.40%)
- lost test points by kind (Law 1: TIMEOUT/CRASH give a recovery signal, WRONG is silent): {'TIMEOUT': 40.0} (corrected by hand: tool reads `[check] {json}` lines without kind; every lost check's first_difference is TimeoutExpired on the setpriv child)
- final message (step 88): I repaired `migrakit` so every stage follows the contract, and wrote all deliverables to `/app/out`. **Defects found and fixed (19 code fixes across 9 files + one missing file)** core (`core/`, `pipeline.py`) - `FieldView.from_payload` dropped explicit nulls, so a null field looked absent (N1). - `n

## Scored items

| class | layer | item | weight | target | kind | evidence |
|---|---|---|---|---|---|---|
| LOST_GRADED | test_output | world_29_core_large_graph | 5.0 | output | TIMEOUT | test-stdout first_difference TimeoutExpired (60 s core budget) |
| LOST_GRADED | test_output | world_30_core_large_graph | 5.0 | output | TIMEOUT | test-stdout first_difference TimeoutExpired (60 s core budget) |
| LOST_GRADED | test_output | world_31_core_large_graph | 5.0 | output | TIMEOUT | test-stdout first_difference TimeoutExpired (60 s core budget) |
| LOST_GRADED | test_output | world_32_core_large_graph | 5.0 | output | TIMEOUT | test-stdout first_difference TimeoutExpired (60 s core budget) |
| LOST_GRADED | test_output | world_33_core_large_graph | 5.0 | output | TIMEOUT | test-stdout first_difference TimeoutExpired (60 s core budget) |
| LOST_GRADED | test_output | world_34_core_large_graph | 5.0 | output | TIMEOUT | test-stdout first_difference TimeoutExpired (60 s core budget) |
| LOST_GRADED | test_output | world_35_core_large_graph | 5.0 | output | TIMEOUT | test-stdout first_difference TimeoutExpired (60 s core budget) |
| LOST_GRADED | test_output | world_36_core_large_graph | 5.0 | output | TIMEOUT | test-stdout first_difference TimeoutExpired (60 s core budget) |
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
| 3-12 | read contract, migration_semantics, ini, corrections, aliases, taxonomy, every repo file | instruction.md:3 | (none) | EASY |
| 13 | ran visible tests on shipped repo (2 fail) | instruction.md:11 | test_fixes_matches_visible_test_runs | EASY |
| 20 | copied repo to /app/orig-repo for before/after | repository_contract.md:136-150 (K19) | module_*_claims, test_fixes | EASY |
| 21-41 | first write: all 19 fixes in 9 files + `__main__.py` in 5 min; planner = Dijkstra over (schema, field state) ordered by (cost, edge-id list), no lower bound | repository_contract.md:34-35 (K6), :88-93 (K14); migration_semantics.md:31-44 (M6-M8) | world_29..36_core_large_graph | LOST_GRADED (TIMEOUT at hidden scale; shipped inputs fast) |
| 21-41 | every other stated rule right on first write | repository_contract.md K1-K19, N/C/P/T rules | 57 other positive checks | EASY |
| 55 | brute-force DFS (depth 7) vs plan_migration on 120 shipped records, 0 mismatches | migration_semantics.md:41-44 (M8) | (none; shipped graph small) | EASY |
| 56-57 | stress timing on own graphs: 80-schema chain, 200 schemas / 3,000 edges / 10 fields, worst 0.05 s | repository_contract.md:88-93 (K14: 1,200 schemas, 6,000 edges) | world_29..36 | SKIPPED (never built a graph near the stated limits; costs 1-9 only) |
| 64-69 | /tmp/checks.py 20 synthetic contract checks (2 failures fixed in the check file) | K13-K16, M, N, P, T rules | judge R1, R2, R9 | EASY |
| 64 | E_PARSE lines only with no batch or batch B9 absent from manifest | repository_contract.md:79-86, :95-99 (K13, K15) | judge R3 | SKIPPED |
| 64 | " NULL " payload checked only for status | null_semantics.ini N6-N8 | judge R4 | SKIPPED |
| 64 | every manifest row names a batch some feed line uses | repository_contract.md:84-85 ('00000000' when no record has that batch) | new probe (manifest row with no records) | SKIPPED |
| 64 | CLI run from a relative cwd into a fresh nested --out | repository_contract.md:54-58 (K10) | world_*_cli; new probe (rerun into older --out) | SKIPPED (rerun never done) |
| (none) | never added a file to a contract folder, never altered a copy of /app/ci, never priced an edge above 9 | repository_contract.md:22 (K2), migration_semantics.md:10-11 (M2) | new probes | SKIPPED |
| 79, 86 | make_report.py: 9 checks re-run after last repo edit (step 85 docstring), 9/9 pass | judge R8 / J3a | R8 | EASY (claims backed; no FALSE_CLAIM) |
| 88 | final message: figures equal /app/out/summary.json; size claim '200-schema/3000-edge' matches step 57 | judge J3b/J3c candidates | (none fire) | EASY |

Phase A: run staged tests/ and environment/ identical to BUNDLE (diff -rq empty); task.toml differs only by allowed_hosts staging (host.docker.internal).
