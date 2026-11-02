# SCORE_REPORT: schema-migration-plan-repair, blind 4f7606c (board caa031b)

**Result: blind tests = 201/241 = 83.4% (reward 0.834). Lever lost: 40/40 points (all 8 checks). Oracle sanity on the same copy recipe: 1.0 (241/241).**
The blind loses 40/241 = 16.6% of positive test points, so it **does lose >= 10%**. All of the lost points come from the harden-round lever checks.

- Bundle: `master_chat_work/bundles/schema-migration-plan-repair` (after harden e3e74e6), read only. Blind folder: `/tmp/blind/schema-migration-plan-repair-20261027T145907-d721`, read only.
- Session rename: `name_session.py caa031b` printed `codex: no match / opencode: ['ses_e832f264bffeDO5vVKgb16l7Bm']`. The output does not show caa031b. Per the prompt I did not retry.
- Harbor 0.24.0, `--agent oracle --env docker`, `OPENAI_API_KEY=unused`, `yes |`, tests only (judge.toml deleted by exe_copy.py). There was one run per pair. Lock `/tmp/opencode-logs/locks/schema-migration-plan-repair.lock` (removed). The chain log ends `ALL_DONE` (`logs/chain.log`).

## What the tests read
`tests/test.sh` runs `rewardkit /tests --workspace /app`. `test_output.py` declares the artifacts `/app/out/{patched-repo.zip, repair-report.json, module_core.json, module_parser.json, module_report.json, test_fixes.json, summary.json}`. It rebuilds `/app/ci` and the starting `/app/repo` from embedded copies, and it grades the package from the zip.

## Copy recipe
`exe_copy.py <bundle> /tmp/score_caa031b/schema-migration-plan-repair` and the same into `...-oracle`. Its stdout is the standard one: judge.toml deleted, reward.toml weights = { test_output = 0.004149377593360996 } (1/241), network public, OpenHands venv dropped.
In the blind copy only, `solution/solve.sh` was replaced (saved as `logs/blind_solve.sh`). The blind `app/` and `out/` were staged under `solution/blind/` with `cp -Rp`. The oracle copy keeps its original solve.sh, which calls solve.py.

## Install map (blind path -> /app path)
| blind | /app |
|---|---|
| `app/repo/` (whole tree, 23 files) | `/app/repo/` (shipped repo removed first) |
| `app/build_outputs.py` | `/app/build_outputs.py` |
| `out/patched-repo.zip`, `out/summary.json`, `out/module_core.json`, `out/module_parser.json`, `out/module_report.json`, `out/test_fixes.json`, `out/repair-report.json` | `/app/out/<same name>` |
I found no absolute `/tmp/blind/...` path in any delivered file. `grep -rn /tmp/blind app out` came back empty. `build_outputs.py` uses paths relative to `__file__`, and the tests do not run it.

## Diff proof
- `diff -r <blind>/app <copy>/solution/blind/app` and `diff -r <blind>/out <copy>/solution/blind/out`: both empty (`DIFF_R_EMPTY`).
- In the container, solve.sh printed sha256 for every installed file under /app (`logs/container_sha256.txt`, taken from `agent/oracle.txt`). I compared that list with the host sha256 of the blind files (`logs/blind_host_sha256.txt`): `diff` was empty, `SHA_IDENTICAL 30 files`. The blind's code and outputs were installed byte for byte.

## Scores
| run | job | reward | test points |
|---|---|---|---|
| blind 4f7606c | `jobs/caa031b-blind-1` | 0.834 | 201 / 241, no negatives fired |
| bundle oracle (sanity) | `jobs/caa031b-oracle-1` | **1.0** | 241 / 241 |

tests% = (positive points earned 201 - fired negatives 0) / positive total 241 = **83.40%**. This is the reward.toml weighted sum.

## Per-check table (blind)
| check | weight | result | failure kind | first assertion line |
|---|---|---|---|---|
| artifacts_exist | 1 | pass |  |  |
| negative_unsafe_archive_members | -1 | not fired |  |  |
| archive_src_layout | 1 | pass |  |  |
| api_entry_points_importable | 1 | pass |  |  |
| visible_repo_tests_pass_from_archive | 1 | pass |  |  |
| summary_json_matches_delivered_run | 1 | pass |  |  |
| module_core_claims_match_archive | 1 | pass |  |  |
| module_parser_claims_match_archive | 1 | pass |  |  |
| module_report_claims_match_archive | 1 | pass |  |  |
| test_fixes_matches_visible_test_runs | 1 | pass |  |  |
| repair_report_well_formed | 1 | pass |  |  |
| signature_keeps_explicit_null | 3 | pass |  |  |
| signature_rejects_unknown_schema | 1 | pass |  |  |
| plan_revisits_schema_with_new_state | 3 | pass |  |  |
| plan_tie_first_edge_decides | 3 | pass |  |  |
| ladder_large_state | 3 | pass |  |  |
| exec_add_fill_absent_vs_null | 3 | pass |  |  |
| exec_correction_first_arrival_only | 3 | pass |  |  |
| identity_merge_chain_followed | 1 | pass |  |  |
| identity_merge_loop_rejected | 1 | pass |  |  |
| identity_partner_id_beats_alias | 1 | pass |  |  |
| pipe_rejection_codes | 3 | pass |  |  |
| pipe_bad_lines_run_continues | 3 | pass |  |  |
| receipt_skips_lines_rejected_at_parse | 3 | pass |  |  |
| receipt_counts_partner_rejected_lines | 3 | pass |  |  |
| tokens_match_exactly | 3 | pass |  |  |
| summary_categories_code_first | 3 | pass |  |  |
| summary_partner_order_by_rank | 1 | pass |  |  |
| world_01_state_null_corrections_summary | 5 | pass |  |  |
| world_02_tie_tokens_replay_feed | 5 | pass |  |  |
| world_03_state_policy_tokens_corrections | 5 | pass |  |  |
| world_04_scale_state_replay_summary | 5 | pass |  |  |
| world_05_null_policy_replay_cli | 5 | pass |  |  |
| world_06_tie_corrections_feed_summary | 5 | pass |  |  |
| world_07_state_tie_null_tokens_summary | 5 | pass |  |  |
| world_08_scale_policy_corrections_feed | 5 | pass |  |  |
| world_09_policy_tokens_replay_corrections_cli | 5 | pass |  |  |
| world_10_state_feed_replay_summary | 5 | pass |  |  |
| world_11_null_tie_corrections_cli | 5 | pass |  |  |
| world_12_scale_tokens_null_summary | 5 | pass |  |  |
| world_13_state_policy_feed_cli | 5 | pass |  |  |
| world_14_tie_policy_replay_summary | 5 | pass |  |  |
| world_15_scale_corrections_tokens_feed | 5 | pass |  |  |
| world_16_null_state_replay_corrections | 5 | pass |  |  |
| world_17_tie_policy_null_feed_summary | 5 | pass |  |  |
| world_18_scale_tie_replay_cli | 5 | pass |  |  |
| world_19_state_tokens_corrections_replay_feed_summary | 5 | pass |  |  |
| world_20_reject_pad_state_corrections | 5 | pass |  |  |
| world_21_scope_damage_null_replay | 5 | pass |  |  |
| world_22_reject_scope_feed_summary | 5 | pass |  |  |
| world_23_pad_damage_tokens_policy | 5 | pass |  |  |
| world_24_reject_damage_tie_cli | 5 | pass |  |  |
| world_25_scope_pad_corrections_summary | 5 | pass |  |  |
| world_26_reject_scope_pad_damage | 5 | pass |  |  |
| world_27_pad_scope_state_tokens_cli | 5 | pass |  |  |
| world_28_damage_reject_scale_replay | 5 | pass |  |  |
| world_29_core_large_graph | 5 | FAIL | timeout | TimeoutExpired: Command '['setpriv', '--reuid=nobody', ... '/usr/local/bin/python3.12', '-c', ...]' (child under RLIMIT_AS, core-world budget) |
| world_30_core_large_graph | 5 | FAIL | timeout | TimeoutExpired: Command '['setpriv', '--reuid=nobody', ... '/usr/local/bin/python3.12', '-c', ...]' (child under RLIMIT_AS, core-world budget) |
| world_31_core_large_graph | 5 | FAIL | timeout | TimeoutExpired: Command '['setpriv', '--reuid=nobody', ... '/usr/local/bin/python3.12', '-c', ...]' (child under RLIMIT_AS, core-world budget) |
| world_32_core_large_graph | 5 | FAIL | timeout | TimeoutExpired: Command '['setpriv', '--reuid=nobody', ... '/usr/local/bin/python3.12', '-c', ...]' (child under RLIMIT_AS, core-world budget) |
| world_33_core_large_graph | 5 | FAIL | timeout | TimeoutExpired: Command '['setpriv', '--reuid=nobody', ... '/usr/local/bin/python3.12', '-c', ...]' (child under RLIMIT_AS, core-world budget) |
| world_34_core_large_graph | 5 | FAIL | timeout | TimeoutExpired: Command '['setpriv', '--reuid=nobody', ... '/usr/local/bin/python3.12', '-c', ...]' (child under RLIMIT_AS, core-world budget) |
| world_35_core_large_graph | 5 | FAIL | timeout | TimeoutExpired: Command '['setpriv', '--reuid=nobody', ... '/usr/local/bin/python3.12', '-c', ...]' (child under RLIMIT_AS, core-world budget) |
| world_36_core_large_graph | 5 | FAIL | timeout | TimeoutExpired: Command '['setpriv', '--reuid=nobody', ... '/usr/local/bin/python3.12', '-c', ...]' (child under RLIMIT_AS, core-world budget) |
| mutation_receipt_moves_only_mismatches | 5 | pass |  |  |
| mutation_tokens_move_only_that_partner | 5 | pass |  |  |
| negative_hardcoded_sample_answers | -5 | not fired |  |  |
| negative_filename_dependent_behaviour | -3 | not fired |  |  |
| negative_deleted_visible_tests | -3 | not fired |  |  |
| negative_nondeterministic_output | -1 | not fired |  |  |
| negative_entry_points_mutate_arguments | -1 | not fired |  |  |

All 8 failures are the same kind: **timeout**. They are not a wrong document, a crash or a missing file. The verifier's child process, run as nobody with the 4 GiB RLIMIT_AS cap, was killed by `subprocess.TimeoutExpired` on the large-graph core world. The harden report gives the core-world child budget as `TIME_LIMIT_SEC * len(lines) + 20` = 60 s. The other 63 checks passed, and none of the 6 negatives fired.

## Lever checks (harden round e3e74e6, P-3 exact optimum on larger hidden graphs)
| lever check | weight | blind |
|---|---|---|
| world_29_core_large_graph | 5 | FAIL (timeout) |
| world_30_core_large_graph | 5 | FAIL (timeout) |
| world_31_core_large_graph | 5 | FAIL (timeout) |
| world_32_core_large_graph | 5 | FAIL (timeout) |
| world_33_core_large_graph | 5 | FAIL (timeout) |
| world_34_core_large_graph | 5 | FAIL (timeout) |
| world_35_core_large_graph | 5 | FAIL (timeout) |
| world_36_core_large_graph | 5 | FAIL (timeout) |
Lever lost: **8/8 checks, 40/40 points** (16.6% of 241). This blind's planner notes describe a Dijkstra search over (schema, tracked field states) ordered by (cost, edge-id list), which is the plain-Dijkstra shape the harden kill table shows being killed at 70 s. The result, 201/241 = 83.4%, matches the harden report's "first write" and "all-but-one" rows.

## Loses >= 10% of positive test points?
**Yes.** It loses 40/241 = 16.6%, and all of it comes from the lever.

## Hygiene
No bundle, blind folder, Tasks_INPUT, harness or QC kit file was edited. Every program ran in Docker. The `/tmp/score_caa031b/` copies were removed after this report was written. Logs and job folders are kept in OUT (`logs/`, `jobs/`).
