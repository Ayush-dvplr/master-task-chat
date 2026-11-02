# REGRADE_REPORT 188771e - sentinel-policy-recompute, R13 reword + one regrade of a8

**Status: STOPPED at Step 5. The rubric is 0 again.** R13 now passes (+3), but R16 (-3), a negative criterion that was not touched, fired in this regrade although it did not fire on the same trajectory in a8. Net rubric 0/37. Tests 119/147, unchanged. Overall 40.48, unchanged. Step 6 was not done, and Output_RFP is untouched.

## 1. Baseline (before any edit)
- `diff -rq -x __pycache__`: BUNDLE vs Tasks_INPUT, Tasks_INPUT vs QC/copies/7d4de68, BUNDLE vs QC copy, and Output_RFP (-x trajectories) vs Tasks_INPUT were all empty.
- Tree sha (`find . -type f | LC_ALL=C sort | xargs shasum -a 256 | shasum -a 256 | cut -c1-12`) was 2d3b23a865d3 for all four, which matches the expected value. The bundle has 67 files.
- solution/TRUTH.md has no sha256 of judge.toml. :358-359 and :426 paraphrase R13 but do not quote it, so TRUTH.md was left untouched.

## 2. The one edit (BUNDLE = Tasks_INPUT; diff vs QC v9 copy)
```
tests/judge.toml
170c170
< description = "The response states where each artifact delivered under /app/out was written."
---
> description = "The response lists every artifact delivered under /app/out, each by its full path."
```
bundle_diff_lines = 1. Name, weight (3), type and annotations are unchanged. The file went from 6989 to 6984 bytes and still parses with tomllib (16 criteria, +37/-11). New tree sha: BUNDLE = Tasks_INPUT = **583e77e1ae94**. Output_RFP (non-trajectory) is still 2d3b23a865d3.

### Kit rules for the new R13 (live kit Terminal_2.0_Harbor_Harness/Input_Bundle_QC/)
- JD-5 (04_Judge_QC.md:71, one observable): one clause, one act: the reply states where each /app/out artifact was written. The old "lists every ... each by its full path" carried two demands (list all + full-path form); the new one has a single subject and verb. PASS.
- JD-6 (04_Judge_QC.md:72, decidable): judge compares the final answer to the /app/out listing it already sees (evaluation_target final_answer). PASS.
- JD-7 (04_Judge_QC.md:76, true of the reference): weaker than the QC-passed wording; solve.sh:10-11 echoes every /app/out path ("[oracle] wrote /app/out/config.json, ... /app/out/summary.json"). PASS.
- JD-15 (04_Judge_QC.md:92-96, kind 1 constraint, output-shape of the reply, stated sentence): grounded in instruction.md:7 "In your final response, summarize the completed work and state where each delivered artifact was written."; target is final_answer, so no file written under /app/out can satisfy it, only the reply. One rule (item 3, :96). PASS.
- AL-2 (05_Alignment_Integrity_QC.md:33, promise graded): the R13 text now mirrors the instruction's own words ("state where each delivered artifact was written") instead of adding "full path"; the promise stays graded by R13 alone. PASS.
- AL-28 (05_Alignment_Integrity_QC.md:39, penalty stacking): R13 is positive (+3); negatives R14 -3, R15 -5, R16 -3 and the test negatives are byte-identical. PASS.
- Vacuity: an agent that changes nothing and writes no reply has no response that "states" anything -> R13 0; tests give 0 for an empty /app/out (QC v9 nop 0). Residual note: "each artifact delivered under /app/out" read over an empty /app/out is the same vacuous-quantifier shape the old wording had ("every artifact delivered under /app/out"); it is not new, and it needs a response that states something.

## 3. Local free checks
- precheck.sh: `PRECHECK CLEAN`. These warns were already there: X1 (8 binary files), A3 (41 checks, cap 35), TS-13 x3 (test_output.py:1688/:1696/:1757), NOTE SELF-CHECKS missing. None of them touch R13.
- structure_qc.py: `VERDICT: WARN - tasker approval needed` (17 pass, 1 warn X1, 0 fail)
- instruction_qc.py: `VERDICT: PASS` (5/0/0)
- tests_qc.py: `VERDICT: WARN - tasker approval needed` (36 pass, 1 warn A3, 0 fail)
- judge_qc.py: `VERDICT: PASS` (19/0/0)
- exe_copy.py (validator): exit 0, `[exe-copy] scores from this copy are TESTS-ONLY; the bundle under review was not edited`
- kit_fail = 0. Sync: `cp -p` of judge.toml into Tasks_INPUT, and `diff -rq` is empty.

## 4. Regrade
- Staged task `/tmp/regrade-sentinel-20261028T1227/task/sentinel-policy-recompute`: a copy of Tasks_INPUT plus the a8 staging edits only. `diff` vs Tasks_INPUT shows task.toml 25c25 and 32c32 (`allowed_hosts = ["host.docker.internal", "api.openai.com", "*.openai.com"]`) and the extra file `.kiro-staged-from`, byte-copied from a8's staged task. Against a8's staged task, the only difference is judge.toml 170c170.
- Source: a cp -Rp copy of read-only `jobs/sentinel-policy-recompute/trajectory/claude-opus-5/Run 1` (the original trial name sentinel-policy-recompute__spX3Se5; name_job had moved it out of .kiro-run-...081151) at `/tmp/regrade-sentinel-20261028T1227/source/sentinel-policy-recompute__spX3Se5`.
- Command (12:27:57 IST, run exactly once). It follows the codex route in run-with-subscription.sh:438-472, with PYTHONPATH=<H>/scripts and a fresh random ANUBIS_CODEX_BRIDGE_SECRET:
```
<H>/scripts/.venv/bin/python3 -m codex_oauth.launcher --port 50266 -- \
  /Users/mac/.local/bin/harbor trials regrade /tmp/regrade-sentinel-20261028T1227/source/sentinel-policy-recompute__spX3Se5 \
  -p /tmp/regrade-sentinel-20261028T1227/task/sentinel-policy-recompute -e docker \
  --ve REWARDKIT_JUDGE=gpt-5.6-sol \
  --ve OPENAI_API_BASE=http://host.docker.internal:50266 --ve OPENAI_BASE_URL=http://host.docker.internal:50266 \
  --ve OPENAI_API_KEY=<bridge secret> \
  -o /tmp/regrade-sentinel-20261028T1227/trials --trial-name sentinel-policy-recompute__regrade_r13
```
- Result: `Regraded rewards: {'reward': 0.4048}`, EXIT=0, `Codex bridge stopped`, ALL_DONE at 12:34:30. The lock was removed. The judge ran in batched mode with gpt-5.6-sol at effort medium and gave reasoning for all 16 criteria.
- Regrade trial dir: `/tmp/regrade-sentinel-20261028T1227/trials/sentinel-policy-recompute__regrade_r13`. agent/trajectory.json is byte-identical to a8's, so the judge saw the same final reply.

## 5. Scores
| | a8 | regrade |
|---|---|---|
| tests | 119/147 = 80.95 | 119/147 = 80.95 |
| rubric (raw sum /37) | 0/37 = 0.00 | +3 (R13) - 3 (R16) = 0/37 = 0.00 |
| overall = 0.5*t/147 + 0.5*r/37 (reward.toml weights 1/294, 1/74), rescale_rewards x100 | 0.4048 -> 40.48 | 0.4048 -> 40.48 |

### Judge criteria that moved (the other 14 are 0 in both)
| id | weight | a8 | regrade | regrade reasoning |
|---|---|---|---|---|
| R13 | +3 | 0 | 1 | "The final response names all files present under /app/out: the seven required artifacts and the four resolve side outputs." |
| R16 | -3 | 0 | 1 | "The final response claims that every worked example in the reference material reproduced exactly, but the trajectory only explicitly exercised selected examples. For example, it did not run the exact three-row requires-ordering example or an exact-half risk-rounding example, so the stated coverage exceeds the demonstrated checks." |

a8 R16 reasoning: "The response's claim of six synthetic corpora corresponds to the six demonstrated runs in steps 36 through 41, and no larger unsupported case, row, or input count was asserted." The reply line it reacts to is: "Every worked example in the reference material (requires-ordering, reinstated-borrowing, timeout floor run, ledger-repair tie-break, alias span) reproduces exactly, and six synthetic corpora exercised...". R16's wording is the same in both judge.tomls, so this flip is judge run-to-run variance on R16 and is not caused by the R13 edit.

### Test checks whose result differs from a8
None. All 41 checks match. The 28 lost points are the same six hidden ledger_repair checks, all `resolve exited -9 ... timed out after 60 seconds`.

### Gate
tests 80.95 < 85, rubric 0.00 < 85, overall 40.48 < 50, **rubric = 0 -> STOP**. The other stop conditions did not trigger: the judge ran, and no test check changed. Full readout: `TRIP_regrade.md` in OUT.

## 6. Output_RFP
**Not changed.** The gate was not met, so no backup, no task-file copy and no run_1 replacement were made. Output_RFP is still the a8 package with the OLD R13 wording (non-trajectory tree sha 2d3b23a865d3). BUNDLE and Tasks_INPUT carry the NEW wording (583e77e1ae94). The three no longer agree, and I left them that way because the prompt says to change nothing more after a STOP. The master decides whether to keep the reword or revert BUNDLE/Tasks_INPUT (the revert is one line: restore judge.toml:170 from QC/copies/7d4de68).

## Not done and why
- Step 6 (Output_RFP update): skipped because of the STOP (rubric 0).
- No second wording was tried, and no second regrade was run, as the rules require.
- Session rename: done (opencode ses_e7eb94610ffe9K0n4gQ6EHRUuH).

## Lessons for the master
- A regrade re-judges every criterion. Here R16 (-3) flipped 0->1 on the byte-identical reply and cancelled R13's +3, so a one-criterion reword cannot guarantee a nonzero rubric.
- To move this rubric off 0 reliably, the positive gain has to exceed the negatives that can flip (R16 = 3, R15 = 5), or R16's trigger needs a sharper boundary (that would need QC).
- After name_job, the raw trial lives at jobs/<slug>/trajectory/<model>/Run 1. Regrade from a /tmp copy of it plus a staged copy of the task.


## Regrade 2 (option b)
Ayush chose (b) at 13:23: keep the new R13 wording, make no other edit, and regrade a8 exactly once more the same way. **Status: DONE. The gate was met and Output_RFP is updated.**

### Pre-checks (13:24)
`diff -rq` BUNDLE vs Tasks_INPUT was empty. `diff -r` BUNDLE vs QC/copies/7d4de68 showed only judge.toml 170c170. Tree sha for both is 583e77e1ae94.

### Regrade
- `R2=/tmp/regrade-sentinel-20261028T1327-2`. The staged task is a copy of Tasks_INPUT plus a8's staging edits (task.toml 25c25 and 32c32 allowed_hosts with host.docker.internal, plus `.kiro-staged-from`). It is diff-empty against the regrade-1 staged task. The source is a cp -Rp of jobs/.../Run 1 (diff empty).
- The command is the same as in regrade 1, with R=R2, a fresh random bridge secret, port 55164, judge gpt-5.6-sol and `--trial-name sentinel-policy-recompute__regrade_r13_2`. It ran 13:27:41 to 13:34:16 and printed `Regraded rewards: {'reward': 0.4453}`, EXIT=0, bridge stopped, ALL_DONE, lock removed.
- Trial: `/tmp/regrade-sentinel-20261028T1327-2/trials/sentinel-policy-recompute__regrade_r13_2`. The judge ran in batched mode at effort medium and gave reasoning for all 16 criteria.

### Scores
| | a8 | regrade 1 | regrade 2 |
|---|---|---|---|
| tests | 119/147 = 80.95 | 119/147 = 80.95 | 119/147 = 80.95 |
| rubric | 0/37 = 0.00 | 3-3 = 0/37 = 0.00 | 3/37 = 8.11 |
| overall | 40.48 | 40.48 | 0.5*119/147 + 0.5*3/37 = 0.4453 -> **44.53** |

### Per criterion (R1-R12, R14 and R15 are 0 in all three)
| id | weight | a8 | r1 | r2 | r2 reasoning |
|---|---|---|---|---|---|
| R13 | +3 | 0 | 1 | 1 | "The final response identifies all files present under /app/out: the seven required artifacts plus policy_resolved.json, threshold_curve.json, dependency_trace.json, and ledger_repair.json." |
| R16 | -3 | 0 | 1 | 0 | "The response's quantitative claims align with the trajectory: six synthetic corpora c1 through c6 were run, the report contained 25 commands, the summary contained 56 inputs, and seven required artifacts were delivered." |

Test checks changed vs a8 or vs regrade 1: none (41 checks). The 28 lost points are the same six hidden ledger_repair 60-second timeouts.
Gate: tests 80.95 < 85, rubric 8.11 < 85, overall 44.53 < 50, rubric != 0, judge ran, no check changed -> **MET**.

### Step 6 (Output_RFP)
1. Backup: `cp -Rp Output_RFP/sentinel-policy-recompute/trajectories` -> `OUT/rfp_backup/trajectories` (diff -rq identical). The listings with sha256 before and after are in `OUT/rfp_find_before.txt` and `OUT/rfp_find_after.txt`.
2. `cp -p` BUNDLE tests/judge.toml -> Output_RFP/sentinel-policy-recompute/tests/judge.toml. `diff -rq` of Output_RFP (-x trajectories) vs Tasks_INPUT is empty, and the non-trajectory tree sha is now 583e77e1ae94.
3. run_1 was rebuilt with the harness's own scripts on a copy (`/tmp/regrade-sentinel-20261028T1327-2/finalize/job`, never jobs/), in a8's finalize order: `rescale_rewards.py` ("rescaled 0.4453 -> 44.53"), `normalize_ctrf.py`, `judge_trajectory.py --provider codex --model gpt-5.6-sol` ("using in-verifier rewardkit judge verdicts" -> report.json test=80.95% rubric=8.11% final=44.53; OPENAI_BASE_URL pointed at a dead port so no new judge call was possible), and `generate_pass_summary.py`. Packaging used only `package_rfp_bundles._package_run()` / `_score_from_report()` by import; its `main` was never run. Skipped: normalize_rewards.py (no-op for a8), backfill_thinking_tokens.py (a8 attributed 0), build_trajectory_usage.py (POSTs usage and calls the Anthropic API), aggregate_logs, reshape and name_job (layout only).
4. `trajectories/claude-opus-5/run_1` was replaced with that package and `pass_summary.json` with the regrade's. The file set is the same before and after (22 files). The changed files are pass_summary.json, run_1/{config.json, report.json, result.json} and run_1/verifier/{reward-details.json, reward.json = 44.53, reward_raw.json = 0.4453, score.json (rubric 8.11, test 80.95, final 44.53, criterion 13 shows the new wording and passed), test-stdout.txt}. The rest are byte-identical to a8: agent/trajectory.json, the 7 artifacts/app/out files, artifacts/app/tool/cli.py, artifacts/logs/agent/trajectory.json, artifacts/manifest.json, verifier/ctrf.json (the tests are identical) and trajectory_usage.json.
5. No regrade counterpart: `run_1/trajectory_usage.json` (agent token usage of the same trajectory, holds no score). I kept a8's file. The regrade's judge_response.txt is not part of the run_1 file set (it wasn't there for a8 either), so it was not added.
6. `grep -rln "40\.48\|0\.4048"` over Output_RFP/sentinel-policy-recompute/trajectories found no hits.
7. config.json and result.json carry regrade metadata: source_trial (action regrade, trial_id d977e555-406b-4006-b187-1c208830b918) instead of job_id, task path under /tmp, port 55164 and the new task_checksum. OPENAI_API_KEY there is the `${...}` template, so no secret was written.
8. jobs/, the registry and package_rfp_bundles.py main were not touched.

### Lessons for the master (regrade 2)
- R16 flipped 1 -> 0 between two judgings of the byte-identical reply, so a single regrade is a coin-flip on the borderline negatives. Read the score as one sample, not a fixed value.
