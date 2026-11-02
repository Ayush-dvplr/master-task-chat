# Reverse-engineer 10 low-scoring Pass@1 tasks (overall 5-29%), issued 22 Oct 2026 01:05 IST (v2 01:15: compaction-safe)

This prompt is saved on disk at:
`/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/_adhoc/20261022T0105_lowscore_10task_study.md`
It is the full brief. After any compaction or restart, re-read this file in full before doing anything else.

You are studying 10 finished Harbor 0.24 tasks that passed QC and scored below 30% overall on a real claude-opus-5 run. Goal: learn exactly WHY a frontier agent failed them, how their instructions are written, and which mechanisms (levers) did the work, so we can reuse the patterns in our own tasks. Our own 4 tasks scored 84-94% overall on the same model; the operator's hypothesis is that ours tell the agent too precisely what to do. Test that hypothesis with evidence; do not just accept it.

## Surviving compaction (this is heavy work; follow exactly)
The conversation may be compacted several times. Nothing that exists only in the conversation is safe. The files below are the only truth.

- **Progress file:** `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261022_lowscore-study/PROGRESS.md`. Create it first. It holds:
  - a table: task NN | slug | status (`todo` / `in_progress` / `done`) | owner (`me` or subagent task id `bg_...` and session id `ses_...`) | checklist steps done (1-9) | report path | step 2 label;
  - phase: `A` / `A_done_waiting_approval` / `B` / `B_done`;
  - approved Phase B tasks (exact operator text and time);
  - a short "next action" line, rewritten every time you finish a unit of work.
- **Notes per task:** `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261022_lowscore-study/notes/<NN>.md`. Append findings as you go (trajectory digest by step number, check-to-rule map, failed-check causes), so a half-done task can be resumed without re-reading the trajectory. Notes are raw working material; the report is the clean output.
- **Write order:** after each checklist step of a task, append to its notes file and tick the step in PROGRESS.md. When a task is complete, write `tasks/<NN>_<slug>.md` and set it `done` before starting the next task.
- **Resume protocol (run this at the start, and after every compaction):**
  1. Re-read this prompt file in full.
  2. Read PROGRESS.md. If it does not exist, start fresh.
  3. For every task marked `done`, check its report file exists and is non-empty; if not, set it back to `in_progress`.
  4. For a task `in_progress` by `me`: read its notes file and continue from the first unticked checklist step. Do not redo ticked steps.
  5. For a task owned by a subagent: call `background_output` on its `bg_...` id. If finished, verify its report (step "Verifying subagent work" below). If it is gone or failed, continue it with `task(task_id="ses_...")`; if that fails too, take the task over yourself from its notes.
  6. If the phase is `A_done_waiting_approval`: do nothing except answer the operator. Never start Phase B without an "approved: <numbers>" message recorded in PROGRESS.md.
- Never trust a summary of earlier work over the files. If they disagree, the files win.

## Hard rules
- READ ONLY on the inputs. Never edit the copies or the originals. Never pull, commit or push.
- Phase A (all 10 tasks) uses NO RUNS: no harness, no Docker, no model calls, no rewardkit, no executing the agent's or the oracle's code. Everything comes from the saved files. Phase B (Docker replay) runs ONLY for tasks the operator approves by number in this session, after Phase A is finished.
- What the master already checked about the saved files (verify, do not trust): `verifier/ctrf.json` has pass/fail per check but NO failure messages; `verifier/test-stdout.txt` holds only the reward line; file modes were lost when the runs were committed to git (every artifact is 100644), so the delivered files' real modes are unknown; the trajectories are complete (tool calls and their outputs); 9 of 10 test files drop privileges (setpriv) before running agent code; in all 10 the agent wrote its files with the editor's `create` command and never ran chmod.
- Scratch only in `/tmp/lowscore-study-20261022T0105/`. Delete it at the very end (after Phase B, or after Phase A if no Phase B).
- Trajectory files are large: read them in pieces (offset/limit, or a small python extractor that prints step number, tool, command and the first lines of output). Never skip a part because output was truncated; read the rest.
- Never let one tool call run longer than about 4 minutes. Long work goes to background subagents or `nohup` with a log in `/tmp/opencode-logs/lowscore-study-20261022T0105/`.
- Mark every guess UNVERIFIED. Quote file:line for every claim about a file.

## Subagents (recommended)
Split the 10 tasks across at most 3 background subagents (`run_in_background=true`), for example tasks 01-04, 05-07, 08-10. Record each `bg_...` and `ses_...` id in PROGRESS.md the moment you launch it.
Each subagent prompt must include: the path of this prompt file with "read it in full first; you own only tasks NN-NN; ignore the Subagents, Synthesis and Phase B sections", the notes and report paths for its tasks, and "write notes after every checklist step and the report as soon as each task is done". Subagents never write PROGRESS.md; you do.
While they work, do not read their tasks yourself. Prepare the synthesis skeleton and the comparison notes on our 4 instructions (notes/ours.md). Never end your turn while a subagent is still running: wait in steps of under 4 minutes and check again.

### Verifying subagent work
For each returned report: it follows checklist steps 1-9 in order, every claim about a file has file:line, step 2 has a label with evidence, step 4 covers every failed positive check and every fired negative listed in that task's ctrf.json (count them). Fix gaps by continuing that subagent's session, or do it yourself.

## Inputs
- Copies (work from these): `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261022_lowscore-study/tasks_copy_20261022T0105/<NN>_<slug>/`. `INDEX.tsv` there lists number, overall %, slug and original path. Integrity list: `../tasks_copy.sha256`.
- Each task has `instruction.md`, `task.toml`, `environment/` (Dockerfile + data), `solution/` (solve.sh, solve.py, TRUTH.md), `tests/` (test_output.py, judge.toml, reward.toml, test.sh), and `trajectories/claude-opus-5/run_1/` with: `agent/trajectory.json`, `artifacts/app/...` (what the agent delivered), `verifier/ctrf.json` (per-check pass/fail), `verifier/score.json` (judge criteria with verdicts), `verifier/reward.json`, `verifier/test-stdout.txt`, `result.json`, and `pass_summary.json` one level up.
- Comparison (read only): our tasks' instructions `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/{emberforge-vault-settlement,vendor-archive-roundtrip-recovery,schema-migration-plan-repair,district-heat-flex-procurement}/instruction.md` and their `environment/data/` doc files.
- Live QC rules (for "how does it still pass QC"): `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC/`.

## Per task (all 10): checklist
1. **Shape.** Files and folders, data formats and sizes, number of doc files, instruction word count, number of tests and judge criteria, positive and negative weight totals, timeouts, output artifacts.
2. **Is the low score genuine? (static screen, no runs)** We lost a day to a broken grade in our own tasks: the verifier ran the agent's program as another user who could not read it, so a correct agent scored near 0. Rule this out from the files:
   - a. Classify every check as EXEC (runs the agent's program or code) or READ (only reads delivered files). Quote the line that decides it.
   - b. If at least one EXEC check passed, the verifier could run the agent's program, so the permission trap did not hit the program. Say so and quote the passed check.
   - c. If no EXEC check passed: read how the tests run agent code (setpriv/uid drop, chmod of the program, its folders, temp inputs and output dirs; quote file:line), and compare with the trajectory: did the agent's own runs of its program on the visible data succeed, and do its delivered outputs in `artifacts/` match what the READ checks expect? A program that works in the trajectory but fails every EXEC check, while the tests never make it readable to the dropped uid, is SUSPECT.
   - d. Also look for other grade breakers: hardcoded paths the agent could not know, timeouts far below the trajectory's measured run time, missing dependencies.
   - Label: GENUINE / SUSPECT / UNSURE, with the evidence. Only a SUSPECT or UNSURE task whose answer changes the study's conclusions may go into a Phase B request.
3. **Instruction anatomy.** How it is written: what it states as the goal, what it leaves for the agent to discover, where the rules live (instruction vs data docs), how specific or vague each step is, whether it gives a procedure or only an end state, what it asks the agent to report, tone, length. Quote the key sentences. Compare its style directly with our instructions.
4. **Every failed positive check and every fired negative.** For each: name, weight, what it checks, the rule behind it and where that rule is written (file:line), what the agent actually did (trajectory step number + artifact evidence), and the cause, one of: never read the doc / read it but misapplied / two rules combined wrongly / hidden-input generalisation failed / shortcut or hardcoding / ran out of time or steps / output format / other. Also list checks the agent passed that a lazy agent would also pass.
5. **Levers.** Name each mechanism that cost points, its weight share, and map it to our families: A hidden composition of documented rules, B dependent chain, C audit/repair, D size ladder, E stacked constraints, F rejection paths, or NEW (describe it). Say which were triggered in this run.
6. **Judge.** Each criterion, whether met (from `score.json`), and why it failed when it did. How the criteria avoid paying for text copied from the docs and avoid overlapping the tests.
7. **How it passes QC and still beats the agent.** Which traps are fully documented (so not "hidden rules") yet missed; what makes them easy to miss (placement, wording, cross-file dependence, defaults that look right). Any anti-cheat design.
8. **Trajectory story.** Number of steps, duration, what the agent read and in what order, which docs it never opened, where it went wrong first, whether it tested itself and how, and whether its final message claims things the tests show are false.
9. **Reusable patterns / things to avoid.** 3-6 bullets each.

For hidden-input checks, the exact wrong output cannot be seen without running the program. Infer the cause by reading the agent's code against the rule and the check, mark it UNVERIFIED, and move on. Do not request a run just for that.

## Synthesis (after all 10 reports are done and verified)
Write `SYNTHESIS.md` and `levers_found.json` (see Deliverables). Build them from the 10 report files on disk, not from memory. Set PROGRESS.md phase to `A_done_waiting_approval`.

## Stop after Phase A
When all 10 reports and the synthesis are written, stop and reply. If any task is SUSPECT or UNSURE in step 2 and it matters, list it as a `RUN REQUEST`: task, the evidence, and which conclusion depends on it. Do nothing more until the operator answers "approved: <task numbers>". Record that answer in PROGRESS.md before starting Phase B.

## Phase B (only for approved tasks)
Faithful replay of the saved run in Docker, tests only, using the live QC kit's Step 10 method (`/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC/Final_checklist.md`, Step 10, and `exe_copy.py`, which drops the OpenHands SDK so the build takes seconds):
1. Copy the task to `/tmp/lowscore-study-20261022T0105/replay/<NN>/`, build the tests-only copy with `exe_copy.py`, and replace `solution/solve.sh` with a script that writes the agent's delivered files from `trajectories/.../artifacts/app/` into `/app` at the same paths.
2. The real file modes are unknown (git), so run two variants, once each: V600 (every delivered `.py` program 0600, which is what the editor's `create` can produce) and V644 (all 0644).
3. Compare with the recorded `ctrf.json`. If V600 or V644 reproduces the recorded per-check results, the replay is faithful; report which. If V644 scores much higher than the record, the grade was broken: report the checks that change.
4. Limits: at most 2 Docker runs at the same time, logs in `/tmp/opencode-logs/lowscore-study-20261022T0105/`, run each run in the background with nohup, never wait on one command longer than 4 minutes. Expect about 2 to 5 minutes per run. Never run the real agent or the judge.
5. After each run, write its result to that task's notes file and PROGRESS.md at once. When a task's two variants are done, add a "Phase B" section to its report. At the end update SYNTHESIS.md, set phase `B_done`, then delete the replay folders.

## Deliverables
OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261022_lowscore-study/`
- `PROGRESS.md` and `notes/<NN>.md` (working state; keep them).
- `tasks/<NN>_<slug>.md`: one report per task, the checklist above in order.
- `SYNTHESIS.md`:
  1. Table: task | overall | tests | rubric | genuine? | main failure causes | lever families.
  2. Instruction-writing patterns that correlate with low scores, with quoted examples, plus a direct side-by-side with our 4 instructions (where ours over-specify, if they do, quoted).
  3. Lever families ranked by points lost across the 10 tasks, with the strongest single example of each.
  4. Failure causes ranked by points lost.
  5. Judge patterns that held up (low rubric scores) vs ones the agent met.
  6. Rules for our builder prompts: 8-15 concrete, testable rules ("do X", "never Y"), each citing the tasks it comes from.
  7. Open questions and all RUN REQUESTs in one list.
- `levers_found.json`: `[{"task":"","name":"","family":"A|B|C|D|E|F|NEW","mechanism":"","where_documented":"","weight_share":0.0,"triggered":true,"cause_of_failure":"","evidence":""}]`

## Done when
All 10 task reports exist and follow the checklist, SYNTHESIS.md and levers_found.json exist and the JSON parses, the copies' sha256 list still matches (`shasum -a 256 -c ../tasks_copy.sha256` run from inside `tasks_copy_20261022T0105/`), PROGRESS.md shows every task `done`, and no subagent is still running. Final reply (after Phase A): the summary table, the top 5 builder rules, the step 2 label of every task with its one-line evidence, every RUN REQUEST, and the OUT path.
