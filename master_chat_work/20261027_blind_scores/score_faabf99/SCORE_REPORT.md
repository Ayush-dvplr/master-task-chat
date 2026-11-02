# Blind score report: district-heat-flex-procurement (board faabf99)

Bundle after harden 7d95b18 (read only): `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/district-heat-flex-procurement`.
Session rename: `name_session.py faabf99` printed `codex: no match` / `opencode: ['ses_e81fde228ffe3B8CUcseZk3ipu']`; faabf99 was not shown in the output. Not retried, as instructed.

## Result
| blind | tests% | lever pts lost | lever checks lost | loss kind | non-lever lost | loses >=10% of positive points |
|---|---|---|---|---|---|---|
| ef9234c | 84.39 (173/205) | 32/32 | 8/8 | TIMEOUT (all 8) | 0 | yes (15.6%) |
| d62d21c | 84.39 (173/205) | 32/32 | 8/8 | TIMEOUT (all 8) | 0 | yes (15.6%) |
| 7dd7290 | 84.39 (173/205) | 32/32 | 8/8 | TIMEOUT (all 8) | 0 | yes (15.6%) |

Oracle sanity (same copy recipe, unchanged solve.sh): reward 1.0, 205/205, 0 exceptions.

Under Law-1 v3.5 all three losses count: every lost point is a lever check, the loss kind is TIMEOUT, and no non-lever check was lost (all 4 format, 40 pair, 3 mutation checks pass; no negative fired).

## What the tests read
`instruction.md`: the agent leaves `/app/out/derive_report.py` (run as `python3 /app/out/derive_report.py DATA_DIR OUT_DIR`) and the 9 reports `/app/out/{summary,policy_audit,data_quality,region_North,region_South,region_West,region_East,segment_commercial,segment_public}.json`. `tests/test.sh` runs `rewardkit /tests --workspace /app`. `test_output.py` reads only `/app/out/*`; `run_agent` copies `/app/out/derive_report.py` into a scratch box and runs it on hidden extracts with `_AGENT_TIMEOUT = 120` s. Positive total 205; negatives -5, -5, -3.

## Method
- Copies were built with the live kit `Input_Bundle_QC/exe_copy.py <bundle> /tmp/score_faabf99/<name>/` (judge off: judge.toml removed, reward.toml = test_output only at 1/205 per point). Copies: `oracle`, `ef9234c`, `d62d21c`, `7dd7290`.
- In each blind copy the only change is `solution/solve.sh`, plus `solution/blind_app` and `solution/blind_out`, which are `cp -R` of the blind `app/` and `out/` folders. All three copies use the same solve.sh (cmp equal), see `logs/blind_solve.sh`. It copies the files and prints the sha256 of every installed file. No program is run.
- Runs: `yes | harbor run --agent oracle --env docker` (OPENAI_API_KEY=unused), one nohup chain (`logs/chain.sh`). At most 2 heavy containers at a time, with lock `/tmp/opencode-logs/locks/district-heat-flex-procurement.lock`. Chain log: `START oracle 21:36:59 (waited 1660 s)`, `END oracle rc=0 21:37:48`, `END ef9234c rc=0 21:42:17`, `END d62d21c rc=0 21:46:42`, `END 7dd7290 rc=0 21:51:08`, `ALL_DONE 21:51:08`.
- The per-check results come from the verifier's `reward-details.json` plus the `[check]` reason lines in `test-stdout.txt`, both copied to `logs/`. The table parser is `logs/table.py`. tests% = (positive points earned - fired negatives) / 205.
- Timing measurement (Docker only, `--network none --cpus 4`, tests image `warm-district-heat-flex-procurement-tests:latest`; scripts `logs/run.sh`, `logs/time_wide.py`). It imports the copy's `test_output`, builds the same two wide extracts (`wide_root(0)`, `wide_root(1)`, seeds from EVAL_SEED), and runs the bundle reference `solve.py` and each blind program with a 400 s cap. Output is in `logs/timing_diag.log`.

## Install map (same for all three blinds)
| blind path | /app path |
|---|---|
| `app/derive_report.py` | `/app/derive_report.py` (same bytes as out/derive_report.py) |
| `out/derive_report.py` | `/app/out/derive_report.py` (the graded program) |
| `out/{summary,policy_audit,data_quality,region_North,region_South,region_West,region_East,segment_commercial,segment_public}.json` | `/app/out/<same name>` |

The blind folders' `instruction.md` and `environment/data` are byte-identical to the bundle's. No delivered file contains `/tmp/blind`, `/Users/` or `environment/data` paths.

## Pair: ef9234c (`/tmp/blind/district-heat-flex-procurement-20261027T202450-09c3`)
**Diff proof** (full output in `logs/diff_proof.txt`):
```
$ diff -r /tmp/blind/district-heat-flex-procurement-20261027T202450-09c3/app  copy/solution/blind_app   -> (empty) app-identical
$ diff -r /tmp/blind/district-heat-flex-procurement-20261027T202450-09c3/out  copy/solution/blind_out   -> (empty) out-identical
$ diff -rq oracle-copy ef9234c-copy
Only in solution: blind_app
Only in solution: blind_out
Files solution/solve.sh differ
```
Inside the container, the installed sha256 list (`logs/ef9234c.solve-output.txt`) matches the host `shasum -a 256` of the blind files. The program is `1f999dbb8d5069c3f4a558bacc30baf991e5b34a4926a3e04cc9168f0395f00e` at both `/app/derive_report.py` and `/app/out/derive_report.py`.

**Oracle sanity:** 1.0 (205/205).
**Blind tests%:** 84.39 (173/205). Harbor reward 0.8439, run rc=0, no exceptions.
**Lever checks lost:** 8/8 (32/32 pts). Kind: all TIMEOUT. The verifier gives the same reason for every lever check: `program run failed: timed out after 120 s`.
**Measured seconds** (timing run, 400 s cap): wide_0 400.1 s timed_out=True, wide_1 400.1 s timed_out=True. In the same container the reference solve.py took 4.22 s and 5.83 s. The blind program finishes neither wide extract within 400 s, more than 3x the 120 s limit. This is a real timeout, not a slow-host effect.
**Non-lever checks lost:** 0. **Loses >= 10% of positive points:** yes (32/205 = 15.6%).

| check | weight | lever | result | failure kind | first assertion line |
|---|---|---|---|---|---|
| artifact_set_exists_and_parses | 1 |  | pass |  |  |
| canonical_serialization_and_integer_units | 1 |  | pass |  |  |
| report_keys_match_schema | 1 |  | pass |  |  |
| report_arrays_in_schema_order | 1 |  | pass |  |  |
| selection_match | 3 |  | pass |  |  |
| selection_match_hard | 5 |  | pass |  |  |
| intervals_match | 3 |  | pass |  |  |
| intervals_match_hard | 5 |  | pass |  |  |
| tie_decisions_match | 3 |  | pass |  |  |
| tie_decisions_match_hard | 5 |  | pass |  |  |
| segment_rows_match | 3 |  | pass |  |  |
| segment_rows_match_hard | 5 |  | pass |  |  |
| ledger_quality_match | 3 |  | pass |  |  |
| ledger_quality_match_hard | 5 |  | pass |  |  |
| region_totals_North_match | 3 |  | pass |  |  |
| region_totals_North_match_hard | 5 |  | pass |  |  |
| region_totals_South_match | 3 |  | pass |  |  |
| region_totals_South_match_hard | 5 |  | pass |  |  |
| region_totals_West_match | 3 |  | pass |  |  |
| region_totals_West_match_hard | 5 |  | pass |  |  |
| region_totals_East_match | 3 |  | pass |  |  |
| region_totals_East_match_hard | 5 |  | pass |  |  |
| segment_totals_match | 3 |  | pass |  |  |
| segment_totals_match_hard | 5 |  | pass |  |  |
| summary_match | 3 |  | pass |  |  |
| summary_match_hard | 5 |  | pass |  |  |
| labels_match | 3 |  | pass |  |  |
| labels_match_hard | 5 |  | pass |  |  |
| quality_counts_match | 3 |  | pass |  |  |
| quality_counts_match_hard | 5 |  | pass |  |  |
| credit_rows_match | 3 |  | pass |  |  |
| credit_rows_match_hard | 5 |  | pass |  |  |
| segment_credit_rows_match | 3 |  | pass |  |  |
| segment_credit_rows_match_hard | 5 |  | pass |  |  |
| funded_pool_match | 3 |  | pass |  |  |
| funded_pool_match_hard | 5 |  | pass |  |  |
| grants_match | 3 |  | pass |  |  |
| grants_match_hard | 5 |  | pass |  |  |
| grant_allocation_match | 3 |  | pass |  |  |
| grant_allocation_match_hard | 5 |  | pass |  |  |
| residual_match | 3 |  | pass |  |  |
| residual_match_hard | 5 |  | pass |  |  |
| cap_binding_match | 3 |  | pass |  |  |
| cap_binding_match_hard | 5 |  | pass |  |  |
| wide_0_portfolios_feasible | 3 | yes | FAIL | TIMEOUT | program run failed: timed out after 120 s |
| wide_0_selection_match | 5 | yes | FAIL | TIMEOUT | program run failed: timed out after 120 s |
| wide_0_tie_decisions_match | 5 | yes | FAIL | TIMEOUT | program run failed: timed out after 120 s |
| wide_0_intervals_match | 3 | yes | FAIL | TIMEOUT | program run failed: timed out after 120 s |
| wide_1_portfolios_feasible | 3 | yes | FAIL | TIMEOUT | program run failed: timed out after 120 s |
| wide_1_selection_match | 5 | yes | FAIL | TIMEOUT | program run failed: timed out after 120 s |
| wide_1_tie_decisions_match | 5 | yes | FAIL | TIMEOUT | program run failed: timed out after 120 s |
| wide_1_intervals_match | 3 | yes | FAIL | TIMEOUT | program run failed: timed out after 120 s |
| segment_rate_adder_mutation | 3 |  | pass |  |  |
| allowance_ticks_mutation | 3 |  | pass |  |  |
| minimum_grant_mutation | 3 |  | pass |  |  |
| negative_hardcoded_sample_answers | -5 |  | not fired |  |  |
| negative_reads_tests_or_reward_files | -5 |  | not fired |  |  |
| negative_external_dependency_or_network | -3 |  | not fired |  |  |

earned=173 neg_fired=0 pos_total=205 tests_pct=84.39 lever_lost=8/8 lever_pts_lost=32/32 non_lever_lost=0 kinds=['TIMEOUT']

## Pair: d62d21c (`/tmp/blind/district-heat-flex-procurement-20261027T204418-9654`)
**Diff proof** (full output in `logs/diff_proof.txt`):
```
$ diff -r /tmp/blind/district-heat-flex-procurement-20261027T204418-9654/app  copy/solution/blind_app   -> (empty) app-identical
$ diff -r /tmp/blind/district-heat-flex-procurement-20261027T204418-9654/out  copy/solution/blind_out   -> (empty) out-identical
$ diff -rq oracle-copy d62d21c-copy
Only in solution: blind_app
Only in solution: blind_out
Files solution/solve.sh differ
```
Inside the container, the installed sha256 list (`logs/d62d21c.solve-output.txt`) matches the host `shasum -a 256` of the blind files. The program is `9fc0f640883441d10fa62b83fb262ccb204a819f6cffb413adc81d596d1de563` at both `/app/derive_report.py` and `/app/out/derive_report.py`.

**Oracle sanity:** 1.0 (205/205).
**Blind tests%:** 84.39 (173/205). Harbor reward 0.8439, run rc=0, no exceptions.
**Lever checks lost:** 8/8 (32/32 pts). Kind: all TIMEOUT. The verifier gives the same reason for every lever check: `program run failed: timed out after 120 s`.
**Measured seconds** (timing run, 400 s cap): wide_0 400.1 s timed_out=True, wide_1 400.1 s timed_out=True. In the same container the reference solve.py took 4.22 s and 5.83 s. The blind program finishes neither wide extract within 400 s, more than 3x the 120 s limit. This is a real timeout, not a slow-host effect.
**Non-lever checks lost:** 0. **Loses >= 10% of positive points:** yes (32/205 = 15.6%).

| check | weight | lever | result | failure kind | first assertion line |
|---|---|---|---|---|---|
| artifact_set_exists_and_parses | 1 |  | pass |  |  |
| canonical_serialization_and_integer_units | 1 |  | pass |  |  |
| report_keys_match_schema | 1 |  | pass |  |  |
| report_arrays_in_schema_order | 1 |  | pass |  |  |
| selection_match | 3 |  | pass |  |  |
| selection_match_hard | 5 |  | pass |  |  |
| intervals_match | 3 |  | pass |  |  |
| intervals_match_hard | 5 |  | pass |  |  |
| tie_decisions_match | 3 |  | pass |  |  |
| tie_decisions_match_hard | 5 |  | pass |  |  |
| segment_rows_match | 3 |  | pass |  |  |
| segment_rows_match_hard | 5 |  | pass |  |  |
| ledger_quality_match | 3 |  | pass |  |  |
| ledger_quality_match_hard | 5 |  | pass |  |  |
| region_totals_North_match | 3 |  | pass |  |  |
| region_totals_North_match_hard | 5 |  | pass |  |  |
| region_totals_South_match | 3 |  | pass |  |  |
| region_totals_South_match_hard | 5 |  | pass |  |  |
| region_totals_West_match | 3 |  | pass |  |  |
| region_totals_West_match_hard | 5 |  | pass |  |  |
| region_totals_East_match | 3 |  | pass |  |  |
| region_totals_East_match_hard | 5 |  | pass |  |  |
| segment_totals_match | 3 |  | pass |  |  |
| segment_totals_match_hard | 5 |  | pass |  |  |
| summary_match | 3 |  | pass |  |  |
| summary_match_hard | 5 |  | pass |  |  |
| labels_match | 3 |  | pass |  |  |
| labels_match_hard | 5 |  | pass |  |  |
| quality_counts_match | 3 |  | pass |  |  |
| quality_counts_match_hard | 5 |  | pass |  |  |
| credit_rows_match | 3 |  | pass |  |  |
| credit_rows_match_hard | 5 |  | pass |  |  |
| segment_credit_rows_match | 3 |  | pass |  |  |
| segment_credit_rows_match_hard | 5 |  | pass |  |  |
| funded_pool_match | 3 |  | pass |  |  |
| funded_pool_match_hard | 5 |  | pass |  |  |
| grants_match | 3 |  | pass |  |  |
| grants_match_hard | 5 |  | pass |  |  |
| grant_allocation_match | 3 |  | pass |  |  |
| grant_allocation_match_hard | 5 |  | pass |  |  |
| residual_match | 3 |  | pass |  |  |
| residual_match_hard | 5 |  | pass |  |  |
| cap_binding_match | 3 |  | pass |  |  |
| cap_binding_match_hard | 5 |  | pass |  |  |
| wide_0_portfolios_feasible | 3 | yes | FAIL | TIMEOUT | program run failed: timed out after 120 s |
| wide_0_selection_match | 5 | yes | FAIL | TIMEOUT | program run failed: timed out after 120 s |
| wide_0_tie_decisions_match | 5 | yes | FAIL | TIMEOUT | program run failed: timed out after 120 s |
| wide_0_intervals_match | 3 | yes | FAIL | TIMEOUT | program run failed: timed out after 120 s |
| wide_1_portfolios_feasible | 3 | yes | FAIL | TIMEOUT | program run failed: timed out after 120 s |
| wide_1_selection_match | 5 | yes | FAIL | TIMEOUT | program run failed: timed out after 120 s |
| wide_1_tie_decisions_match | 5 | yes | FAIL | TIMEOUT | program run failed: timed out after 120 s |
| wide_1_intervals_match | 3 | yes | FAIL | TIMEOUT | program run failed: timed out after 120 s |
| segment_rate_adder_mutation | 3 |  | pass |  |  |
| allowance_ticks_mutation | 3 |  | pass |  |  |
| minimum_grant_mutation | 3 |  | pass |  |  |
| negative_hardcoded_sample_answers | -5 |  | not fired |  |  |
| negative_reads_tests_or_reward_files | -5 |  | not fired |  |  |
| negative_external_dependency_or_network | -3 |  | not fired |  |  |

earned=173 neg_fired=0 pos_total=205 tests_pct=84.39 lever_lost=8/8 lever_pts_lost=32/32 non_lever_lost=0 kinds=['TIMEOUT']

## Pair: 7dd7290 (`/tmp/blind/district-heat-flex-procurement-20261027T205625-dc49`)
**Diff proof** (full output in `logs/diff_proof.txt`):
```
$ diff -r /tmp/blind/district-heat-flex-procurement-20261027T205625-dc49/app  copy/solution/blind_app   -> (empty) app-identical
$ diff -r /tmp/blind/district-heat-flex-procurement-20261027T205625-dc49/out  copy/solution/blind_out   -> (empty) out-identical
$ diff -rq oracle-copy 7dd7290-copy
Only in solution: blind_app
Only in solution: blind_out
Files solution/solve.sh differ
```
Inside the container, the installed sha256 list (`logs/7dd7290.solve-output.txt`) matches the host `shasum -a 256` of the blind files. The program is `94d070f164e31d388ee1d85916b094bae88f47ca76f27ef99578794058ab0d72` at both `/app/derive_report.py` and `/app/out/derive_report.py`.

**Oracle sanity:** 1.0 (205/205).
**Blind tests%:** 84.39 (173/205). Harbor reward 0.8439, run rc=0, no exceptions.
**Lever checks lost:** 8/8 (32/32 pts). Kind: all TIMEOUT. The verifier gives the same reason for every lever check: `program run failed: timed out after 120 s`.
**Measured seconds** (timing run, 400 s cap): wide_0 400.1 s timed_out=True, wide_1 400.1 s timed_out=True. In the same container the reference solve.py took 4.22 s and 5.83 s. The blind program finishes neither wide extract within 400 s, more than 3x the 120 s limit. This is a real timeout, not a slow-host effect.
**Non-lever checks lost:** 0. **Loses >= 10% of positive points:** yes (32/205 = 15.6%).

| check | weight | lever | result | failure kind | first assertion line |
|---|---|---|---|---|---|
| artifact_set_exists_and_parses | 1 |  | pass |  |  |
| canonical_serialization_and_integer_units | 1 |  | pass |  |  |
| report_keys_match_schema | 1 |  | pass |  |  |
| report_arrays_in_schema_order | 1 |  | pass |  |  |
| selection_match | 3 |  | pass |  |  |
| selection_match_hard | 5 |  | pass |  |  |
| intervals_match | 3 |  | pass |  |  |
| intervals_match_hard | 5 |  | pass |  |  |
| tie_decisions_match | 3 |  | pass |  |  |
| tie_decisions_match_hard | 5 |  | pass |  |  |
| segment_rows_match | 3 |  | pass |  |  |
| segment_rows_match_hard | 5 |  | pass |  |  |
| ledger_quality_match | 3 |  | pass |  |  |
| ledger_quality_match_hard | 5 |  | pass |  |  |
| region_totals_North_match | 3 |  | pass |  |  |
| region_totals_North_match_hard | 5 |  | pass |  |  |
| region_totals_South_match | 3 |  | pass |  |  |
| region_totals_South_match_hard | 5 |  | pass |  |  |
| region_totals_West_match | 3 |  | pass |  |  |
| region_totals_West_match_hard | 5 |  | pass |  |  |
| region_totals_East_match | 3 |  | pass |  |  |
| region_totals_East_match_hard | 5 |  | pass |  |  |
| segment_totals_match | 3 |  | pass |  |  |
| segment_totals_match_hard | 5 |  | pass |  |  |
| summary_match | 3 |  | pass |  |  |
| summary_match_hard | 5 |  | pass |  |  |
| labels_match | 3 |  | pass |  |  |
| labels_match_hard | 5 |  | pass |  |  |
| quality_counts_match | 3 |  | pass |  |  |
| quality_counts_match_hard | 5 |  | pass |  |  |
| credit_rows_match | 3 |  | pass |  |  |
| credit_rows_match_hard | 5 |  | pass |  |  |
| segment_credit_rows_match | 3 |  | pass |  |  |
| segment_credit_rows_match_hard | 5 |  | pass |  |  |
| funded_pool_match | 3 |  | pass |  |  |
| funded_pool_match_hard | 5 |  | pass |  |  |
| grants_match | 3 |  | pass |  |  |
| grants_match_hard | 5 |  | pass |  |  |
| grant_allocation_match | 3 |  | pass |  |  |
| grant_allocation_match_hard | 5 |  | pass |  |  |
| residual_match | 3 |  | pass |  |  |
| residual_match_hard | 5 |  | pass |  |  |
| cap_binding_match | 3 |  | pass |  |  |
| cap_binding_match_hard | 5 |  | pass |  |  |
| wide_0_portfolios_feasible | 3 | yes | FAIL | TIMEOUT | program run failed: timed out after 120 s |
| wide_0_selection_match | 5 | yes | FAIL | TIMEOUT | program run failed: timed out after 120 s |
| wide_0_tie_decisions_match | 5 | yes | FAIL | TIMEOUT | program run failed: timed out after 120 s |
| wide_0_intervals_match | 3 | yes | FAIL | TIMEOUT | program run failed: timed out after 120 s |
| wide_1_portfolios_feasible | 3 | yes | FAIL | TIMEOUT | program run failed: timed out after 120 s |
| wide_1_selection_match | 5 | yes | FAIL | TIMEOUT | program run failed: timed out after 120 s |
| wide_1_tie_decisions_match | 5 | yes | FAIL | TIMEOUT | program run failed: timed out after 120 s |
| wide_1_intervals_match | 3 | yes | FAIL | TIMEOUT | program run failed: timed out after 120 s |
| segment_rate_adder_mutation | 3 |  | pass |  |  |
| allowance_ticks_mutation | 3 |  | pass |  |  |
| minimum_grant_mutation | 3 |  | pass |  |  |
| negative_hardcoded_sample_answers | -5 |  | not fired |  |  |
| negative_reads_tests_or_reward_files | -5 |  | not fired |  |  |
| negative_external_dependency_or_network | -3 |  | not fired |  |  |

earned=173 neg_fired=0 pos_total=205 tests_pct=84.39 lever_lost=8/8 lever_pts_lost=32/32 non_lever_lost=0 kinds=['TIMEOUT']

## Oracle copy, per-check table
| check | weight | lever | result | failure kind | first assertion line |
|---|---|---|---|---|---|
| artifact_set_exists_and_parses | 1 |  | pass |  |  |
| canonical_serialization_and_integer_units | 1 |  | pass |  |  |
| report_keys_match_schema | 1 |  | pass |  |  |
| report_arrays_in_schema_order | 1 |  | pass |  |  |
| selection_match | 3 |  | pass |  |  |
| selection_match_hard | 5 |  | pass |  |  |
| intervals_match | 3 |  | pass |  |  |
| intervals_match_hard | 5 |  | pass |  |  |
| tie_decisions_match | 3 |  | pass |  |  |
| tie_decisions_match_hard | 5 |  | pass |  |  |
| segment_rows_match | 3 |  | pass |  |  |
| segment_rows_match_hard | 5 |  | pass |  |  |
| ledger_quality_match | 3 |  | pass |  |  |
| ledger_quality_match_hard | 5 |  | pass |  |  |
| region_totals_North_match | 3 |  | pass |  |  |
| region_totals_North_match_hard | 5 |  | pass |  |  |
| region_totals_South_match | 3 |  | pass |  |  |
| region_totals_South_match_hard | 5 |  | pass |  |  |
| region_totals_West_match | 3 |  | pass |  |  |
| region_totals_West_match_hard | 5 |  | pass |  |  |
| region_totals_East_match | 3 |  | pass |  |  |
| region_totals_East_match_hard | 5 |  | pass |  |  |
| segment_totals_match | 3 |  | pass |  |  |
| segment_totals_match_hard | 5 |  | pass |  |  |
| summary_match | 3 |  | pass |  |  |
| summary_match_hard | 5 |  | pass |  |  |
| labels_match | 3 |  | pass |  |  |
| labels_match_hard | 5 |  | pass |  |  |
| quality_counts_match | 3 |  | pass |  |  |
| quality_counts_match_hard | 5 |  | pass |  |  |
| credit_rows_match | 3 |  | pass |  |  |
| credit_rows_match_hard | 5 |  | pass |  |  |
| segment_credit_rows_match | 3 |  | pass |  |  |
| segment_credit_rows_match_hard | 5 |  | pass |  |  |
| funded_pool_match | 3 |  | pass |  |  |
| funded_pool_match_hard | 5 |  | pass |  |  |
| grants_match | 3 |  | pass |  |  |
| grants_match_hard | 5 |  | pass |  |  |
| grant_allocation_match | 3 |  | pass |  |  |
| grant_allocation_match_hard | 5 |  | pass |  |  |
| residual_match | 3 |  | pass |  |  |
| residual_match_hard | 5 |  | pass |  |  |
| cap_binding_match | 3 |  | pass |  |  |
| cap_binding_match_hard | 5 |  | pass |  |  |
| wide_0_portfolios_feasible | 3 | yes | pass |  |  |
| wide_0_selection_match | 5 | yes | pass |  |  |
| wide_0_tie_decisions_match | 5 | yes | pass |  |  |
| wide_0_intervals_match | 3 | yes | pass |  |  |
| wide_1_portfolios_feasible | 3 | yes | pass |  |  |
| wide_1_selection_match | 5 | yes | pass |  |  |
| wide_1_tie_decisions_match | 5 | yes | pass |  |  |
| wide_1_intervals_match | 3 | yes | pass |  |  |
| segment_rate_adder_mutation | 3 |  | pass |  |  |
| allowance_ticks_mutation | 3 |  | pass |  |  |
| minimum_grant_mutation | 3 |  | pass |  |  |
| negative_hardcoded_sample_answers | -5 |  | not fired |  |  |
| negative_reads_tests_or_reward_files | -5 |  | not fired |  |  |
| negative_external_dependency_or_network | -3 |  | not fired |  |  |

earned=205 neg_fired=0 pos_total=205 tests_pct=100.00 lever_lost=0/8 lever_pts_lost=0/32 non_lever_lost=0 kinds=[]

## Hygiene
- No bundle, blind folder, Tasks_INPUT, harness clone or QC kit was edited. All blind code ran only inside Docker.
- Logs are kept in `logs/`. The `/tmp/score_faabf99/` copies are removed after this report.
