# SCORE_REPORT: schema-migration-plan-repair blind scoring (board a02a352)

Bundle `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/schema-migration-plan-repair` (after gate v3.6 harden f0331ad, tree 44942c1a65ac), scored tests-only in Docker with harbor 0.24.0, `--agent oracle --env docker`, `OPENAI_API_KEY=unused`, judge removed by `exe_copy.py` (reward.toml test_output weight = 1/291). Harbor applied task.toml cpus=2, memory_mb=4096 itself; no extra flags. Bundles, blind folders, harness and QC kit were not edited.

Session rename: `name_session.py a02a352` printed `codex: no match` / `opencode: ['ses_e807aea85ffeq6tGdGrpLrfHS3']`; the output does not show the string a02a352 (noted, not retried).

## Result

| blind | folder | tests points | tests % | reward.json | lever lost (of 90) | non-lever lost | loss kinds (points) | negatives fired | tests <= 80 | losses only lever or WRONG | loses >= 10% of positive |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 541e695 | `/tmp/blind/schema-migration-plan-repair-20261028T034828-d2fb` | 200/291 | 68.73 | 0.6873 | 90 | 1 {'WRONG': 1.0} | {'WRONG': 1, 'TIMEOUT': 90} | none | YES | YES | YES (31.27% lost) |
| c720dd9 | `/tmp/blind/schema-migration-plan-repair-20261028T034929-9179` | 201/291 | 69.07 | 0.6907 | 90 | 0  | {'TIMEOUT': 90} | none | YES | YES | YES (30.93% lost) |
| 428ead4 | `/tmp/blind/schema-migration-plan-repair-20261028T035031-b686` | 197/291 | 67.70 | 0.677 | 90 | 4 {'WRONG': 4.0} | {'WRONG': 4, 'TIMEOUT': 90} | none | YES | YES | YES (32.3% lost) |

Oracle sanity (same copy recipe, bundle's own solve.sh unchanged): reward 1.0, tests 291/291 = 100.00%, 0 exceptions (job `a02a352-oracle`, 48 s).

tests% = (positive points earned - fired negative points) / 291, as reward.toml's weighted sum does; it equals harbor's reward.json value for each run.

## Install map (blind path -> container path)

| blind | blind path | /app path |
|---|---|---|
| all three | `app/repo/` (whole tree) | `/app/repo/` (the shipped /app/repo is removed first, so files the blind deleted stay deleted) |
| c720dd9, 428ead4 | `app/make_outputs.py` | `/app/make_outputs.py` |
| 541e695 | (no file besides app/repo; its helper sits in work/, which is the report, not installed) | - |
| all three | `out/{patched-repo.zip,summary.json,module_core.json,module_parser.json,module_report.json,test_fixes.json,repair-report.json}` | `/app/out/<same name>` |

The verifier runs in a separate container and receives only the seven declared `/app/out` artifacts (task.toml `artifacts`); the graded program is the repository inside the blind's own `patched-repo.zip`. No delivered file (app/, out/, or members of patched-repo.zip) contains `/tmp/blind`, `/Users/` or `environment/data` paths (grep: 0 hits).

Copy recipe: `exe_copy.py <bundle> /tmp/score_a02a352/schema-migration-plan-repair-<id>`, then in the copy only `solution/` replaced by `solution/blind/{app,out}` (`cp -Rp` of the blind folders) plus this solve.sh:

```bash
#!/bin/bash
# Blind-score install: place the blind's files byte for byte where the instruction says the agent leaves them.
set -euo pipefail
R="${SOLUTION_ROOT:-/solution}/blind"
rm -rf /app/repo
cp -R "$R/app/." /app/
mkdir -p /app/out
cp -R "$R/out/." /app/out/
echo "INSTALL-DIFF app (excluding ci,out):"; diff -r -x ci -x out "$R/app" /app && echo "app identical"
echo "INSTALL-DIFF out:"; diff -r "$R/out" /app/out && echo "out identical"
```

## Diff proof

Host, blind folder vs the payload in the copy:
```
541e695: diff -r /tmp/blind/schema-migration-plan-repair-20261028T034828-d2fb/app <copy>/solution/blind/app -> identical (rc 0)
541e695: diff -r /tmp/blind/schema-migration-plan-repair-20261028T034828-d2fb/out <copy>/solution/blind/out -> identical (rc 0)
c720dd9: diff -r /tmp/blind/schema-migration-plan-repair-20261028T034929-9179/app <copy>/solution/blind/app -> identical (rc 0)
c720dd9: diff -r /tmp/blind/schema-migration-plan-repair-20261028T034929-9179/out <copy>/solution/blind/out -> identical (rc 0)
428ead4: diff -r /tmp/blind/schema-migration-plan-repair-20261028T035031-b686/app <copy>/solution/blind/app -> identical (rc 0)
428ead4: diff -r /tmp/blind/schema-migration-plan-repair-20261028T035031-b686/out <copy>/solution/blind/out -> identical (rc 0)
```
In the container, after install (from each trial's `agent/oracle.txt`):
```
[541e695] INSTALL-DIFF app (excluding ci,out): | app identical | INSTALL-DIFF out: | out identical
[c720dd9] INSTALL-DIFF app (excluding ci,out): | app identical | INSTALL-DIFF out: | out identical
[428ead4] INSTALL-DIFF app (excluding ci,out): | app identical | INSTALL-DIFF out: | out identical
```
`diff -r` printed no differing line in any of the six comparisons (rc 0 -> 'identical').

## Lever checks

From `harden_w1_e3e74e6/HARDEN_REPORT.md` (world_29..36) and `harden_g36_f0331ad/HARDEN_REPORT.md` (world_37..46): `world_29_core_large_graph` .. `world_46_core_large_graph`, 18 checks x 5 = 90 points (30.9% of 291): exact optimal plans on large hidden graphs within the K14 limit.

- 541e695: lever lost 90/90 (all 18 TIMEOUT); non-lever lost 1 {'WRONG': 1.0}.
- c720dd9: lever lost 90/90 (all 18 TIMEOUT); non-lever lost 0 .
- 428ead4: lever lost 90/90 (all 18 TIMEOUT); non-lever lost 4 {'WRONG': 4.0}.

## Per-check table

Cell = pass, or FAIL KIND followed by the check's first `[check]` difference line from `verifier/test-stdout.txt` (TIMEOUT lines truncated). Negative checks: pass = not fired.

| check | weight | lever | 541e695 | c720dd9 | 428ead4 |
|---|---|---|---|---|---|
| artifacts_exist | 1 |  | pass | pass | pass |
| negative_unsafe_archive_members | -1 |  | pass | pass | pass |
| archive_src_layout | 1 |  | pass | pass | pass |
| api_entry_points_importable | 1 |  | pass | pass | pass |
| visible_repo_tests_pass_from_archive | 1 |  | pass | pass | pass |
| summary_json_matches_delivered_run | 1 |  | pass | pass | pass |
| module_core_claims_match_archive | 1 |  | pass | pass | FAIL WRONG: `condition not met` |
| module_parser_claims_match_archive | 1 |  | pass | pass | FAIL WRONG: `condition not met` |
| module_report_claims_match_archive | 1 |  | pass | pass | FAIL WRONG: `condition not met` |
| test_fixes_matches_visible_test_runs | 1 |  | FAIL WRONG: `$.visible_tests[0].after: got "fail", expected "pass"` | pass | FAIL WRONG: `$.visible_tests[0].before: got "pass", expected "fail"` |
| repair_report_well_formed | 1 |  | pass | pass | pass |
| signature_keeps_explicit_null | 3 |  | pass | pass | pass |
| signature_rejects_unknown_schema | 1 |  | pass | pass | pass |
| plan_revisits_schema_with_new_state | 3 |  | pass | pass | pass |
| plan_tie_first_edge_decides | 3 |  | pass | pass | pass |
| ladder_large_state | 3 |  | pass | pass | pass |
| exec_add_fill_absent_vs_null | 3 |  | pass | pass | pass |
| exec_correction_first_arrival_only | 3 |  | pass | pass | pass |
| identity_merge_chain_followed | 1 |  | pass | pass | pass |
| identity_merge_loop_rejected | 1 |  | pass | pass | pass |
| identity_partner_id_beats_alias | 1 |  | pass | pass | pass |
| pipe_rejection_codes | 3 |  | pass | pass | pass |
| pipe_bad_lines_run_continues | 3 |  | pass | pass | pass |
| receipt_skips_lines_rejected_at_parse | 3 |  | pass | pass | pass |
| receipt_counts_partner_rejected_lines | 3 |  | pass | pass | pass |
| tokens_match_exactly | 3 |  | pass | pass | pass |
| summary_categories_code_first | 3 |  | pass | pass | pass |
| summary_partner_order_by_rank | 1 |  | pass | pass | pass |
| world_01_state_null_corrections_summary | 5 |  | pass | pass | pass |
| world_02_tie_tokens_replay_feed | 5 |  | pass | pass | pass |
| world_03_state_policy_tokens_corrections | 5 |  | pass | pass | pass |
| world_04_scale_state_replay_summary | 5 |  | pass | pass | pass |
| world_05_null_policy_replay_cli | 5 |  | pass | pass | pass |
| world_06_tie_corrections_feed_summary | 5 |  | pass | pass | pass |
| world_07_state_tie_null_tokens_summary | 5 |  | pass | pass | pass |
| world_08_scale_policy_corrections_feed | 5 |  | pass | pass | pass |
| world_09_policy_tokens_replay_corrections_cli | 5 |  | pass | pass | pass |
| world_10_state_feed_replay_summary | 5 |  | pass | pass | pass |
| world_11_null_tie_corrections_cli | 5 |  | pass | pass | pass |
| world_12_scale_tokens_null_summary | 5 |  | pass | pass | pass |
| world_13_state_policy_feed_cli | 5 |  | pass | pass | pass |
| world_14_tie_policy_replay_summary | 5 |  | pass | pass | pass |
| world_15_scale_corrections_tokens_feed | 5 |  | pass | pass | pass |
| world_16_null_state_replay_corrections | 5 |  | pass | pass | pass |
| world_17_tie_policy_null_feed_summary | 5 |  | pass | pass | pass |
| world_18_scale_tie_replay_cli | 5 |  | pass | pass | pass |
| world_19_state_tokens_corrections_replay_feed_summary | 5 |  | pass | pass | pass |
| world_20_reject_pad_state_corrections | 5 |  | pass | pass | pass |
| world_21_scope_damage_null_replay | 5 |  | pass | pass | pass |
| world_22_reject_scope_feed_summary | 5 |  | pass | pass | pass |
| world_23_pad_damage_tokens_policy | 5 |  | pass | pass | pass |
| world_24_reject_damage_tie_cli | 5 |  | pass | pass | pass |
| world_25_scope_pad_corrections_summary | 5 |  | pass | pass | pass |
| world_26_reject_scope_pad_damage | 5 |  | pass | pass | pass |
| world_27_pad_scope_state_tokens_cli | 5 |  | pass | pass | pass |
| world_28_damage_reject_scale_replay | 5 |  | pass | pass | pass |
| world_29_core_large_graph | 5 | LEVER | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` |
| world_30_core_large_graph | 5 | LEVER | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` |
| world_31_core_large_graph | 5 | LEVER | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` |
| world_32_core_large_graph | 5 | LEVER | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` |
| world_33_core_large_graph | 5 | LEVER | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` |
| world_34_core_large_graph | 5 | LEVER | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` |
| world_35_core_large_graph | 5 | LEVER | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` |
| world_36_core_large_graph | 5 | LEVER | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` |
| world_37_core_large_graph | 5 | LEVER | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` |
| world_38_core_large_graph | 5 | LEVER | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` |
| world_39_core_large_graph | 5 | LEVER | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` |
| world_40_core_large_graph | 5 | LEVER | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` |
| world_41_core_large_graph | 5 | LEVER | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` |
| world_42_core_large_graph | 5 | LEVER | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` |
| world_43_core_large_graph | 5 | LEVER | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` |
| world_44_core_large_graph | 5 | LEVER | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` |
| world_45_core_large_graph | 5 | LEVER | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` |
| world_46_core_large_graph | 5 | LEVER | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` | FAIL TIMEOUT: `TimeoutExpired: Command ['setpriv', '--reuid=nobody', ... python3.12 -c ...]` |
| mutation_receipt_moves_only_mismatches | 5 |  | pass | pass | pass |
| mutation_tokens_move_only_that_partner | 5 |  | pass | pass | pass |
| negative_hardcoded_sample_answers | -5 |  | pass | pass | pass |
| negative_filename_dependent_behaviour | -3 |  | pass | pass | pass |
| negative_deleted_visible_tests | -3 |  | pass | pass | pass |
| negative_nondeterministic_output | -1 |  | pass | pass | pass |
| negative_entry_points_mutate_arguments | -1 |  | pass | pass | pass |

## Lost points split

| blind | lever lost (kind) | non-lever lost (check: kind) |
|---|---|---|
| 541e695 | 90 TIMEOUT (world_29..46) | test_fixes_matches_visible_test_runs (1): WRONG |
| c720dd9 | 90 TIMEOUT (world_29..46) | none |
| 428ead4 | 90 TIMEOUT (world_29..46) | module_core_claims_match_archive (1): WRONG; module_parser_claims_match_archive (1): WRONG; module_report_claims_match_archive (1): WRONG; test_fixes_matches_visible_test_runs (1): WRONG |

No CRASH, no MISSING file, no negative check fired in any run. The only TIMEOUTs are the lever worlds; every non-lever loss is a WRONG document (test_fixes.json's before/after state for visible test 0 disagrees with what the verifier observed; for 428ead4 also the three module_*.json claims do not match the archive diff vs the shipped repo).

## Runs and logs (kept in OUT)

- `chain.log` (one nohup chain, oracle+541e695 then c720dd9+428ead4, 2 Docker jobs at a time, ends ALL_DONE), `run_<id>.log` per harbor run, `jobs/jobs/a02a352-<id>/` (trial dirs with `verifier/reward.json`, `reward-details.json`, `test-stdout.txt`, `agent/oracle.txt`).
- Wall time: oracle 04:11:28-04:12:21, 541e695 04:11:28-04:30:10, c720dd9 and 428ead4 04:30:10-04:48:52 (IST, 28 Oct 2026). All harbor runs: 1 trial, 0 exceptions.
- `/tmp/score_a02a352/` copies removed after the report; the lock `/tmp/opencode-logs/locks/schema-migration-plan-repair.lock` was released by the chain.
