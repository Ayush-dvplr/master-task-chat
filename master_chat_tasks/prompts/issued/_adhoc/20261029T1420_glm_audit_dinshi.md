# b118b8c: audit GLM-5.3 trajectory runs on Dinshi Jain's anubis-stage-2 tasks (read-only)

Session title: b118b8c

## Goal
For every task in `/Users/mac/Desktop/Terminal Bench/anubis-stage-2` whose `task.toml` `authors` list contains "Dinshi" (case-insensitive), decide whether the recorded **GLM-5.3** run (`trajectories/glm-5.3/`) is a **valid** run whose score reflects the agent's real work, or whether the score (high or low) comes from an **error or failure**: infrastructure, harness, verifier, judge, timeout, OOM, packaging, or a stale or mismatched bundle.

## Hard rules
- READ-ONLY. Do not edit, move or delete anything under `anubis-stage-2`. No `git pull`, `fetch`, `checkout`, `commit` or `stash` there. It is a teammates' repo.
- No Docker and no harness runs. This audit uses only the files on disk. If a question can only be settled by running something, write "COULD NOT CHECK: needs <what>" and move on.
- Every claim cites `file:line` or a JSON key path, plus the value quoted. No guessing.
- Long scans: use `sleep 120; echo poll <n>` with a rising n. Never make 3 identical tool calls in a row.
- Write everything only under OUT = `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261029_glm_audit_dinshi/` (create it).

## Task list (16; master found them with grep. Step 0 re-derives the list and reports any difference)
Co-author shown. Scores are tests / rubric / combined from each model's `pass_summary.json`.

| task id | co-author | GLM-5.3 | Opus-5 |
|---|---|---|---|
| 072aced5-ac2b-5029-8831-e570547ce89a | Kunwar Singh | 0.0/0.0/0.0 | 27.52/64.44/45.98 |
| 0b27b9dc-7985-54f1-a120-46e6810315a3 | Abdus Samad Ali | 68.24/22.81/45.52 | 96.47/26.32/61.39 |
| 11564348-6b1b-57f4-8851-490d0cbc1c5e | Abdus Samad Ali | 88.46/64.41/76.44 | 91.35/45.76/68.55 |
| 56fe3bdd-00c6-5b13-a5c8-90a94ccc475e | Aditya Patel | 0.0/36.11/18.05 | 64.9/58.33/61.62 |
| 5b2b0901-1afd-5581-9afa-4b59ee504918 | Abdus Samad Ali | 35.56/14.29/24.93 | 36.56/6.98/21.77 |
| 65ba10c2-1913-5076-94a6-d8763828cf25 | Kunwar Singh | 30.88/87.91/59.39 | 16.42/81.4/48.91 |
| 69de664a-afeb-5ad4-9453-b5fb0b108cd6 | Kunwar Singh | 100.0/37.17/68.59 | 76.65/28.32/52.48 |
| 6d12f970-25e4-5a6c-94bc-595bdbe515ae | Abdus Samad Ali | 3.09/81.25/42.17 | 3.09/64.71/33.9 |
| 8764bfdd-69b5-57a0-bc6a-db095fe071db | Aditya Patel | 5.34/83.33/44.34 | 51.46/83.33/67.39 |
| b28ebc90-3080-5d41-9f01-e02549d3efaf | Aniket Datta | 43.94/30.91/37.42 | 63.64/36.36/50.0 |
| cf9b2067-1ba0-5bab-a1ea-83e976851e6c | Aditya Patel | 100.0/50.0/75.0 | 84.52/46.67/65.59 |
| d9e08524-272b-5b4a-aca0-dfb2955591bf | Kunwar Singh | 5.76/94.74/50.25 | 2.88/94.74/48.81 |
| daaca581-de32-5fc7-bd44-dd51c8f26be3 | Aditya Patel | 4.11/83.33/43.72 | 17.12/83.33/50.23 |
| dad47963-3ef5-569b-9c83-dcf0fa4ffb57 | Aditya Patel | 6.45/52.63/29.54 | 78.49/52.63/65.56 |
| f357cd96-1afe-50bc-b553-a1be78c907e3 | Abdus Samad Ali | 70.71/70.59/70.65 | 70.71/58.82/64.77 |
| fb91cc7f-793e-5852-a976-bd859255194d | Kunwar Singh | 45.16/100.0/72.58 | 25.0/64.91/44.95 |

Already seen by master (verify, do not trust):
- 072aced5: GLM scored 0/0/0, `run_1/artifacts/` has no `app/` and `verifier/` has no `reward.txt`. Likely a failed run.
- dad47963: GLM `verifier/reward.txt` = 12.83 but `pass_summary.json` combined = 29.54. These disagree.
- Several tasks have GLM tests < 7% but rubric >= 80 (6d12f970, 8764bfdd, d9e08524, daaca581, dad47963). Check whether the tests really ran or crashed, timed out or never collected.
- `result.json` `exception_info` is null on all 16. Do not treat that alone as "valid".

## Files per run (`<task>/trajectories/glm-5.3/`)
`pass_summary.json`, `run_1/{config.json, result.json, report.json, trajectory_usage.json, artifacts/{manifest.json, app/, logs/}, agent/trajectory.json, verifier/{reward.txt, reward.json, reward_raw.json, score.json, reward-details.json, ctrf.json, test-stdout.txt}}`. Use the same layout under `claude-opus-5/` for comparison. Task files: `task.toml`, `instruction.md`, `tests/{test.sh, test_output.py, reward.toml, judge.toml, Dockerfile}`, `environment/`, `solution/`.

## Steps
0. Re-derive the list: grep `task.toml` authors for "dinshi" case-insensitive. Report any task added or missing against the table. Write `OUT/tasks.csv`.
1. Pick one clean task first and learn the scoring: how `reward.toml` weights tests vs rubric, how `pass_summary` combined is computed, and how `reward.txt`/`reward.json`/`score.json` relate. Write the formula in `OUT/SCORING.md` with citations. Use it for every task.
2. Run these checks on each task's GLM run (each check gets PASS, FAIL or COULD NOT CHECK, with evidence):
   - C1 **Run completed:** `result.json` timestamps, `agent_result`, `agent_execution`, `verifier`, `step_results`, `exception_info`. Did the agent stop on its own, hit the time limit, or get killed? Did the verifier run to the end?
   - C2 **Agent really worked:** read `agent/trajectory.json`. Count steps and tool calls, and find the last message. Look for API errors, rate limits, 4xx/5xx responses, empty replies, context overflow, repeated loops, sandbox or network errors, or a missing tool or package. Check `trajectory_usage.json` tokens and cost.
   - C3 **Output exists:** check that `artifacts/app` and `manifest.json` contain the files the instruction requires, and that they are non-empty.
   - C4 **Tests ran honestly:** check `test-stdout.txt` and `ctrf.json` for collection errors, import errors, an unbuilt Dockerfile, timeouts, OOM or exit 137, killed children, a missing pytest plugin, or 0 tests collected. Count passed, failed and errored, and say whether failures are WRONG output vs CRASH/TIMEOUT/INFRA. For every test score under 10%, name the actual cause.
   - C5 **Judge ran honestly:** check `reward-details.json` and `score.json` for a rubric API error, empty judge replies, a default score, or criteria skipped as errors. Check whether a rubric score is high only because the judge credited items while the output is missing.
   - C6 **Numbers agree:** `reward.txt` = `reward.json` = `score.json` = `pass_summary` = formula from step 1, within rounding. Explain every mismatch, starting with dad47963.
   - C7 **Same bytes:** compare `result.json` `task_checksum` and `config.json` task path, model and timeouts against the current task files where possible. Was the run made on an older version of the bundle? Note any task files with git history newer than `started_at` (`git log -1 --format=%ci -- <task>`, read-only).
   - C8 **Fair against Opus:** compare the same checks on the Opus run. Is any GLM vs Opus gap explained by an infrastructure difference such as different timeouts, model config or verifier mode, rather than model ability?
3. Verdict per task, one of:
   - **VALID**: the score reflects GLM's real work.
   - **VALID-WITH-NOTES**: real work, with a minor issue that does not move the score more than 5 points.
   - **INVALID-INFRA**: harness, agent API, container, OOM or timeout problems not caused by the agent.
   - **INVALID-VERIFIER**: tests or judge broke, or numbers disagree.
   - **STALE**: the run used different task bytes.
   - **UNCLEAR**: give the reason.

   For anything not VALID, state the estimated effect on the score and what would fix it, for example a rerun or a regrade.

## Deliverables (in OUT)
- `AUDIT.md`:
  - a top table: task id | co-author | GLM tests/rubric/combined | verdict | one-line reason | evidence file:line;
  - then a section per task with C1-C8;
  - then patterns across tasks, for example the same failure in many runs;
  - then a list of COULD NOT CHECK items.
- `tasks.csv`, `SCORING.md`, `checks.csv` (task, check, result, evidence).
- `result_b118b8c.json`: `{"status":"DONE","tasks":16,"verdicts":{...},"invalid":[...],"mismatches":[...],"could_not_check":[...]}`.
- Final chat line: `DONE b118b8c` plus the counts per verdict.
