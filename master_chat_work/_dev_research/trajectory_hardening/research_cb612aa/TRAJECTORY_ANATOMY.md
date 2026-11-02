# Trajectory folder anatomy (cb612aa)

Session rename: `name_session.py cb612aa` printed `codex: no match / opencode: no match / NOT RENAMED: no session starts with this board id`. I did not retry it.

H = `Terminal_2.0_Harbor_Harness`. I read three runs, and all three use the same layout:
- pushed: `H/jobs/match-replay-desync-audit/trajectory/claude-opus-5/Run 1` (tests 69.19 / rubric 17.65 / final 43.42)
- parked at tests 100: `H/jobs/cohort-retention-reconciliation/trajectory/claude-opus-5/Run 1` (25 tests, 0 failed, 8 judge criteria, final 100, 17 agent steps)
- sentinel attempt 7: `H/jobs/sentinel-policy-recompute/trajectory/claude-opus-5/Run 1` (80.69 / 19.51 / 50.1; scores.jsonl:94)

## Files and what each tells you about a trip

| Path inside `Run N/` | Content | Trip-point use |
|---|---|---|
| `agent/trajectory.json` (and the copy in `artifacts/logs/agent/trajectory.json`) | schema_version "9"; `steps[]` with `step_id, timestamp, source (system/user/agent), message, tool_calls[{function_name, arguments{command}}], observation{results[{content}]}`; `final_metrics{total_prompt_tokens, total_completion_tokens, total_cost_usd}` (match-replay $4.21, 41 agent steps) | Order of actions: first edit, which self-checks ran, what their outputs said, and the final claim (`finish` tool call `arguments.message`) |
| `agent/instruction.txt` | instruction.md exactly as the agent received it | Confirms what was promised (AL-1) |
| `agent/openhands_sdk.txt` | raw SDK log (351 KB for match-replay) | Thinking and retries. Not needed for trips |
| `artifacts/manifest.json` + `artifacts/app/...` | every declared artifact `{source, destination, status ok/empty}`. These are the only bytes the verifier sees (separate mode) | Lets you re-run any test against the agent's actual outputs, e.g. match-replay keeps `/app/out/optimize.py` |
| `verifier/test-stdout.txt` | one line per check, `[check] test_<name>: AssertionError: <msg>` | The exact failing assertion. This is the WRONG_AND_GRADED evidence line |
| `verifier/reward-details.json` | rewardkit tree: `components[{name: judge or test_output, weight, detail{criteria[{id, value, weight, reasoning}]}}]` | **Ground truth** for pass/fail and for whether a negative fired (value > 0 on a negative weight means it fired) |
| `verifier/reward_raw.json` / `reward.json` / `reward.txt` | 0.4342 / 43.42 | Final score before and after rescaling |
| `verifier/ctrf.json` | synthesized from reward-details (finalize step 2) | Duplicate of reward-details |
| `judge_response.txt` | judge prose | Reasoning behind each criterion |
| `report.json` | `pytest{tests[{name, weight, passed}]}`, `rubric[{number, criterion, evaluation_target trajectory/final_answer/state_change, score, is_positive, passed}]`, `final_reward`, `judge_model` | Convenient, but **`passed` on negatives is inconsistent**: cohort-uplift, pcggc and 7ef8d80a use passed=True to mean avoided, while match-replay R6 has passed=False with value 1.0, meaning it fired. Read reward-details instead |
| `result.json` | `task_checksum` (dirhash of the whole task dir, installed `harbor/models/task/task.py:216-231`), `config.source_trial: null`, `verifier_environment_mode: separate` | Fingerprint of the bundle that graded this run. If `source_trial` is not null, the run is a regrade |
| `lock.json` | `task.digest` (`models/job/lock.py:600-630`) | Same fingerprint, shown at job level |
| `config.json` | `task.path` = `.kiro-staged-tasks/<slug>`; judge `gpt-5.6-sol`; agent openhands-sdk claude-opus-5, temp 1.0, MAX_ITERATIONS 350 | Which staged copy was graded |
| model dir `pass_summary.json` | tests / rubric / combined, where combined is the mean of tests and rubric | The registry number |
| job `logs/finalize.log` | rescale -> normalize_ctrf -> judge_trajectory ("using in-verifier rewardkit judge verdicts") -> pass_summary -> usage POST | The judge runs **inside the verifier**, so a regrade re-runs the judge as well |

## The three runs side by side
- **match-replay (pushed)**: 31 checks passed, 15 failed. Failures are hidden trap corpora (`trap_drifted/woven/flipped/padded/shadowed/spun_inverse`), `trap_stepped_gap_inverse` (killed with -9 after running past 120 s), and `mutation_window_split_moves_only_amounts` (exit 1, "no candidate chain reproduces the controls"). On the judge side, R1, R3 and R7-R9 failed (R7-R9: never built its own adversarial inputs) and the R6 negative fired (wrote under /app/work and /tmp). The final message (step 43) says "all 11 reproduce their control digest exactly". That is true of the shipped controls but overstates coverage. The trip is visible in the trajectory: it only ever self-tested on the shipped captures.
- **cohort-retention (tests 100)**: 17 agent steps, no failed test, 5 of 25 positives are format/existence checks (RIGHT_EASY). The trajectory has nothing to mine because the model never tripped. A tests-100 run cannot be hardened from its own trajectory, because nothing was recorded at the place where a lever would apply. Hardening it means adding a lever, which is Way B (see WAY_A.md (c)).
- **sentinel attempt 7**: lost 28/145 test points, all in the hidden `ledger_repair` family: `hidden_ledger_repair_{reconciles,cheapest,tie,unit,spare}_hard` at w5 each, plus `hidden_rare_repair_pairs_hard` at w3 (from `loss.py`). It also lost judge R6, R7 and R8 (w5 each: no independent recompute of 2250 / the threshold / the prod profile), R1 (never ran the shipped tool before its first edit), and R3, R4, R5 and R9. Step 45 says "All checks pass" while 6 positive tests failed (STATED_WRONG_FACT). No judge negative charged that claim.

## What the folder can and cannot tell you
- Can: which graded checks failed and why, through the assertion text plus the agent's artifacts. Which judged acts the agent skipped, from the step order. Which claims were false, by comparing the final message with failed tests.
- Cannot: whether the agent did something wrong that **no test looks at** (WRONG_NOT_GRADED). That needs an independent reference computed on the agent's artifacts, because the trajectory alone does not reveal it (TRIP_METHOD.md §3).
