You are auditing whether the agent under test can reach the grader: the tests, the hidden data, the rubric or judge criteria, the reference solution, or anything that gives away the answers. Board id: `e59fc8d`. This prompt is saved at `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/_adhoc/20261024T1004_grader_leak_audit.md`.

Why (Ayush, 24 Oct): Opus scores 100/100/100 on task after task, while our local reflex and agent programs score about 0.11 to 0.13. If any grader material is reachable, every score we have is contaminated and all lever work rests on bad data. This is NOT the lever-leak library (`LEAK_LIBRARY.md` is about the agent working out a trap from the spec). This audit is about the agent getting grader material.

## Rules that survive compaction
- First thing: `python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/name_session.py" e59fc8d`. If it fails, note it and carry on. Run it again at the very end.
- Tools are always available; never claim otherwise without a real call and its quoted error.
- After every compaction: run `date`, re-read this prompt, then `OUT/TODO.md`, and continue from the first unticked item. Copy this section word for word into any compaction summary.
- Keep `OUT/TODO.md` and `OUT/LOG.md` current after every step. Read files in pieces of at most 50 KB.
- Never edit the harness clone, the QC kit, any bundle, `QC/`, `QC assigned/` or `master_chat_tasks/`. Read-only git and `gh api` GET only. Never run `harbor run` or any job that calls a model or uploads anything.
- Docker is allowed only to build a bundle image from a COPY in scratch (`/tmp/leak_audit-<YYYYMMDDTHHMM>/`) and look around inside it as the agent's user. Use `nohup ... &` for builds and poll with waits under 4 minutes. Remove your own containers and images at the end.
- Do the work yourself. No subagents.
- Every claim cites a file:line, a command with its output, or a trajectory step. Something you did not confirm is labelled UNVERIFIED.

## Inputs
- Harness (how a run is staged): `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/` (HEAD 71a653b2). Find the code that builds the task image, starts the agent, decides when `tests/`, `solution/`, `judge.toml`, `reward.toml` and hidden data enter the container, mounts volumes, sets env vars, and controls network access.
- Real Opus trajectories: `Terminal_2.0_Harbor_Harness/jobs/<slug>/` and `jobs/_archive/<slug>-<ts>/` (logs/job-config.json, trajectory/claude-opus-5/*). The master's notes on each run are under `master_chat_tasks/prompts/issued/_adhoc/2026102*_harness_traj_*.md`.
- Bundles: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/<slug>/` (environment/Dockerfile, environment/data, tests/test_output.py with its `_SHIPPED_DATA` embedding, any test_visible.py, tests/judge.toml, tests/reward.toml, solution/).
- Earlier permission scan: `master_chat_work/20261022_pl-note/passat1_scan/SCAN.md` (board 4b75115).
- OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261024_process/leak_audit/`

## Phase 1: staging (from code, no Docker)
Write how a run is staged, in order, with file:line for each step: image build context, what is COPYed, what goes into /app, when tests and solution are copied in (before, during or after the agent), mounts, the user the agent runs as, env vars, network policy, and where verifier logs and reward files are written. List every place a grader file could exist while the agent is running.

## Phase 2: channels
For each channel below: reachable (yes / no / UNVERIFIED), evidence, which tasks it affects, and the fix. Check at least:
1. `/tests`, `/solution`, `/logs/verifier`, reward or judge files present in the container during the agent phase.
2. Image layers or build context carrying grader files (a COPY of a whole folder, or an earlier layer with the file deleted later).
3. Shipped or visible test files (test_visible.py, repo tests) that embed hidden cases, expected values, seeds, `_SHIPPED_DATA`, or reference outputs.
4. Hidden-data generators or their seeds reachable or reproducible from shipped files.
5. The answer recoverable from shipped data (sorted ids, leftover columns, names that encode the answer, files in environment/data named after expected outputs).
6. Reference solution traces: .pyc, __pycache__, backup files, git history inside /app (any `.git` in shipped repos), timestamps or file sizes that reveal answers.
7. Environment variables, harness config or job metadata visible to the agent (job-config.json contents, any task id or path naming the test).
8. Network: can the agent reach the internet during a run, and are any of our repos (ShreeyankDoliya/Terminal_2.0_Harbor_Harness, ShreeyankDoliya/Anubis_Tasks_Samples, ayushsah-dev/beta-task-generator, ShreeyankDoliya/Finalized_Tasks_RFP) public or holding our bundles (`gh api` GET only)? Is the task or a near-identical one public (search by distinctive names from instruction.md)?
9. The judge: does the judge prompt or rubric reach the agent, or does the agent's final message format let it steer the judge (for example, the judge grading only the agent's own claims)?
10. Anything else you find.

## Phase 3: container probe
Build 2 images from copies (dispatch-plan-reoptimization and one 100/100/100 task such as cohort-retention-reconciliation). Run each as the agent's user and the way the harness starts it. Run `find / -xdev \( -name '*test*' -o -name '*judge*' -o -name '*reward*' -o -name '*solution*' -o -name 'TRUTH*' \) 2>/dev/null`, check `env`, `ls -la /app /tests /solution /logs`, `docker history --no-trunc`, and whether each file from Phase 2 is readable. Quote the output.

## Phase 4: trajectories
For every real Opus trajectory we have (all slugs and archived runs), search every tool call and output for reads of /tests, /solution, /logs, reward, judge, TRUTH, hidden, any grader filename, any `pip download`, `curl`, `wget`, `git clone`, or web access, and any visible-test file it opened. For each run: `contaminated` (it read grader material), `exposed` (it could have, but did not), or `clean`, with the quoted steps. Note any run where the agent got a hidden-case value it could not have computed from shipped files.

## Deliverables
- `OUT/LEAK_REPORT.md`: the staging timeline, the channel matrix (channel | reachable | used in a trajectory | tasks | evidence | fix), the trajectory table, and a verdict: are our 100/100/100 scores explained by leakage (yes / partly / no), with the evidence.
- `OUT/result.json`: `{board:"e59fc8d", harness_head, channels:[{id, reachable, used, tasks}], trajectories:[{slug, run, verdict}], verdict, status:"done"}`.
- "Lessons for the master" at the end of LEAK_REPORT.md.
End your final reply with: `Next session: board e59fc8d done. Paste back: done : e59fc8d`.
