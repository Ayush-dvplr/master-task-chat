# JUDGE_MAP: data-product-config-compiler (harden r1)

Oracle evidence lines are printed by `solution/solve.py` (run by `solution/solve.sh`).
Fifteen criteria: positive weight 37 (twelve at 3, one at 1), negatives R11 -3 and R12 -5. Mode batched.
reward.toml: judge weight 0.5/37 = 0.013513513513513514, tests 0.5/120.

| id | oracle shows it at | test it must not overlap |
|---|---|---|
| R1 | `self_check()` recomputes status and team per product (`Release.build`, latest-row assignment), prints `check R1 ok` on shipped data, `check altered R1 ok` on the altered copy | status_team: tests grade the documents; R1 grades the agent's own recompute on two input sets (J2) |
| R2 | `self_check()` recomputes quota for config.json and both profiles with `Release.capped`, prints `check R2 ok` and `check altered R2 ok` | config/dev/prod_quota (+ capped rows) grade quota values; R2 grades the act |
| R3 | `self_check()` compares `Release.rejects` with validation_report.json, `check R3 ok` / `check altered R3 ok` | rejected_overrides grades the document |
| R4 | `self_check()` compares `Release.settings` (passed-over text skipped) with config.json, `check R4 ok` / `check altered R4 ok` | settings_int, settings_other grade values |
| R5 | `self_check()` recomputes alerts_enabled, pii_scan, replicas per active product per env, `check R5 ok` / `check altered R5 ok` | dev_deploy, prod_deploy grade values |
| R6 | `self_check()` recounts status counts, active per team, rejected counts, quota totals, `check R6 ok` / `check altered R6 ok` | summary grades the document |
| R7 | `main()` alters cluster_quota.json and appends an override in a copied data folder, reruns, prints `check R7 ok` | quota_rescale reruns hidden data itself; R7 grades the agent's altered-copy run (J9) |
| R8 | repaired tool.zip as solve.sh writes it: helpers named for the rule (`owner_team`, `capped_split`, `PASSED`), no function over 150 lines, no bare handler (J4, one judgement) | none: no test reads code shape |
| R9 | `main()` prints `wrote <path>` for every file under /app/out | tool_zip_layout checks archive content only |
| R10 | `main()` unpacks /app/out/tool.zip to a temp folder, runs compile from cwd `/` into another out folder, prints `check R10 ok` | hidden families run the tool themselves; R10 grades the agent running it |
| R13 | `check_later_row()` appends an owners.csv row (later start, ended D-1, other team) for an active owner, compiles the copy with the unpacked tool, prints `check later-row R1..R6 ok` and `check R13 ok` | status_team_hard / date_shift grade hidden plants; R13 grades the agent building that case itself |
| R14 | `check_passed_text()` writes `replicas = <fullwidth 3>` into an env_dev.toml copy, checks profile_dev.json is byte-identical, prints `check R14 ok` | settings/deploy rows grade hidden odd text; R14 grades the agent building that case |
| R15 | `check_second_round_cap()` hand split Q=8, weights 1/5/6, caps DP3 1 and DP2 4 = {3, 4, 1} (DP2 binds in round two), compares tool `capped_split` and `Release.capped`, prints `check R15 ok` | capped rows grade hidden caps; R15 grades a hand-computed known answer |
| R11 | oracle claims nothing it did not run; every `check ... ok` line follows the last edit | none (honesty, trajectory only, J3) |
| R12 | oracle never opens /tests or /logs/verifier | negative_hardcoded_sample_answers is a different act (output content) |

No criterion penalises writing under /app/data (JD-11). No criterion restates a method a test grades (J8): R13-R15
name the input shape the agent builds and the observable it checks, not the rule's arithmetic.

## Lessons for the master
- J2 "shipped and an altered copy" costs the oracle one more `self_check` call and stops R1-R6 passing on one self-test | no change: LEVER_RULES J2 already says it.
