You are scoring, without a paid run, the program that paid attempt 3 of ONE Harbor 0.24 bundle, `flood-repair-portfolio`, left behind when the agent hit the 7200 s agent limit, and reading what the agent spent its time on. No bundle edits. Board id: `ea9239d`. This prompt is saved at `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/_adhoc/20261101T1718_flood-repair-portfolio.md`. Issued by the master on route 1 (Ayush 1 Nov 17:16: "Flood A" = score the saved a3 program locally in Docker on the hidden books before deciding attempt 4).

## Rules that survive compaction
- First thing: rename this session to `ea9239d`:
  python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/name_session.py" ea9239d
  If the list does not show it, note that in the report and carry on; never retry on another ID.
- Strictly do not run subagents (no task/agent/background tools); do all work in this main chat.
- Last step before the final reply: run the rename again: `python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/name_session.py" ea9239d`.
- Tools are always available. Never claim otherwise without a real call (bash `date`) and its quoted error.
- After every compaction: run `date`, re-read this prompt, then `OUT/TODO.md`, and continue from the first unticked item. Never re-run a finished Docker block; check its log for ALL_DONE first. Copy this section word for word into any compaction summary.
- Keep `OUT/TODO.md` and `OUT/LOG.md` current after every step. Read files in pieces of at most 50 KB (tests/test_output.py and openhands_sdk.txt: grep and line ranges, never print whole).
- Every program run in Docker only (`--memory 4g --cpus 2`, wall cap `perl -e 'alarm N; exec @ARGV'`). Before each container `python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/dockfree.py" --need-mb 4096 --cpus 2` must print START=yes. Poll with the early-exit loop of _COMMON_RULES_v5 rule 3. Kill your own child processes before you finish. Scratch and logs: `/Users/mac/Desktop/Terminal Bench/_runs/20261101/flood-repair-portfolio/a3score-<TS>/`.
- Read first: `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/_adhoc/20261101_route1_notes.md` (R3 trajectory items) and `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/templates/_COMMON_RULES_v5.md`.
- Never commit, push, pull or open a PR. Edit only OUT and the scratch folder. Never edit BUNDLE, Tasks_INPUT, the harness clone, the QC kit, `QC/`, `jobs/`, `.kiro-run-*` or the Anubis repos (all read only).

## Inputs (read only)
- Frozen bundle: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/flood-repair-portfolio/` (expect tree 931f8f817d76 = Tasks_INPUT; record it with `find . -type f -print0 | LC_ALL=C sort -z | xargs -0 shasum -a 256 | shasum -a 256 | cut -c1-12`).
- a3 run: `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/.kiro-run-flood-repair-portfolio-20261101T145306/flood-repair-portfolio/trajectory/claude-opus-5/Run 1/` - `artifacts/app/out/` (derive_report.py mtime 16:02, reports mtime 15:19), `agent/openhands_sdk.txt` (the only agent log; there is no trajectory.json), `exception.txt` (AgentTimeoutError 7200 s), `verifier/test-stdout.txt` (judge crash: Trajectory not found). Run log `/tmp/opencode-logs/flood-repair-portfolio-20261101T145306/run.log`.
- Kill-table tooling from harden r2: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/flood-repair-portfolio/h2_a1/` and `h1_a1/` (drive2.sh, digest_checks*.py, a1_program, firstwrite/allbutone programs), harden r2 report `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261101_flood-repair-portfolio/harden_r2/HARDEN_REPORT.md` (kill table, a1 TIMEOUT 0/78 lever, pred judge 13.33).
- Paid a1 for comparison: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261031_flood-repair-portfolio/gate_run_a1/`.
- OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261101_flood-repair-portfolio/a3_score`

## Master notes
1. The agent had a program and nine reports by 15:19, edited derive_report.py at 16:02, then (from the log tail) prototyped a frontier DP in /tmp on synthetic 160-proposal books with `timeout 900` runs until the 7200 s limit. The rubric judge needs `/logs/agent/trajectory.json`, which OpenHands writes only at the end, so the timeout left no reward file.
2. Score the delivered 16:02 program exactly as the verifier would: a copy of the frozen bundle made with the live kit's `exe_copy.py`, the a3 `/app/out` (program and reports) placed as the agent left it, tests-only (`tests/test_output.py` through rewardkit, judge disabled or skipped), `--cpus 2 --memory 4g`. Also run it through the h2_a1 kill-table driver per hidden book (seconds, peak MB, EXACT/WRONG/TIMEOUT/CRASH, lever points kept). If the two disagree, say which is right and why.
3. Predicted a3 final had it finished: tests from step 2 plus judge low/mid/high (judge.toml read against what openhands_sdk.txt shows the agent did; mid by the same method as harden r2).

## Steps
1. OUT/TODO.md, record tree sha, copy the a3 `artifacts/app/out/` into OUT/a3_out/ with sha256 of each file.
2. Timeline from openhands_sdk.txt (python, grep "Agent Action", "Summary:", "$ " commands, token totals): step count; first time each of the nine reports existed; when correctness checking stopped; when performance work started and what sizes it built; the last command; route-1 R3 items (files never opened, shipped-fitted literals, where checking stopped). OUT/TIMELINE.md, max 80 lines, with line numbers into openhands_sdk.txt.
3. Docker scoring per master note 2. Quote the reward lines and per-check results; list every check lost with its weight and kind (TIMEOUT/WRONG/CRASH).
4. OUT/A3_SCORE.md: tests score, lever points kept/lost, judge low/mid/high, predicted final; whether the lever held; whether a4 unchanged is likely to time out again (what in the docs or tests pulls the agent into performance work; quote file:line); options for a4 with a one-line cost each (unchanged rerun; one instruction sentence on the agent time budget - say what QC row it would touch; anything else you find). No edits.

## Deliverables
- OUT/TIMELINE.md, OUT/A3_SCORE.md, OUT/LOG.md, OUT/result_ea9239d.json: {"sha":"ea9239d","slug":"flood-repair-portfolio","step":"a3-score","status":"DONE|PAUSED","tree_sha":"<12>","a3_tests":x,"lever_points_kept":x,"lever_points_total":x,"lost_checks":{"<check>":"TIMEOUT|WRONG|CRASH"},"pred_judge_low":x,"pred_judge_mid":x,"pred_judge_high":x,"pred_final":x,"first_reports_time":"HH:MM","perf_work_minutes":x,"a4_timeout_risk":"low|medium|high","report":"<path>"}. It must parse.

Final reply (8 lines max): a3 tests score; lever held yes/no; predicted final; where the 2 hours went; a4 options with your pick; report path.
