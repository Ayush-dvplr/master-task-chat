You are studying 5 finished, QC-passed Harbor 0.24 tasks written by other taskers (group `sugam_b`). They are in our delivery folder because they make claude-opus-5 genuinely lose TEST points, which ours did not do. Your job is to LEARN, not to judge or fix: how their tests are built, how those tests satisfy QC, which lever shapes made Opus fail, and how they keep the traps from leaking. Board id: `bd5de18`. This prompt is saved at `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/_adhoc/20261025T1046_study-sugam_b_bd5de18.md`.

Why this matters: on 25 Oct night, 7 of our tasks scored tests 98.45-100 against fresh Opus after harden rounds. Our rules were either stated so precisely that the agent copied them into code, or the shipped data and visible tests let it check itself. These tasks reach tests 3-95 and passed QC. We want the patterns.

## Rules that survive compaction
- First thing: rename this session to `bd5de18`:
  python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/name_session.py" bd5de18
  If the list does not show it, note that in the report and carry on; never retry on another ID.
- Tools are always available. Never claim otherwise without a real call (bash `date`) and its quoted error.
- READ ONLY. No Docker, no harbor, no pip, no running the tasks' tests or solutions. Never edit, move, mask or create anything inside `/Users/mac/Desktop/Terminal Bench/Anubis_Tasks_Samples/` (a shared git repo). Write only in OUT. Read-only git only (log/show/rev-parse); never commit, push, pull or open a PR. You may run `python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/stacking_check.py" "<task folder>"` (static, prints only); nothing else that executes task code.
- After every compaction: run `date`, re-read this prompt, then `OUT/TODO.md`, and continue from the first unticked item. Copy this section word for word into any compaction summary.
- Keep `OUT/TODO.md` (one line per task per section) and `OUT/LOG.md` (IST times) current after every step.
- Read files in pieces of at most 50 KB. Trajectories are large: list steps with python/jq (index, tool, command first 200 chars, output first 300 chars), then read only the steps you need. Never print a whole trajectory.
- Every claim has evidence: a quote with file:line, a trajectory step index, or command output. Inferred = marked INFERRED. Never guess a score.
- Peer tasks: extract PATTERNS, never content. Nothing you write may be pasted into our bundles as text, data or code. Short quotes as evidence are fine.
- Record `git -C "/Users/mac/Desktop/Terminal Bench/Anubis_Tasks_Samples" rev-parse HEAD` once.

## Read first (our map; compare everything against these)
- `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/LEVER_RULES_v1.md` (levers H1-H7 and L-ids, writing W1-W7, grading G1-G12, judge J1-J9, stacking, reflex gate)
- `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/QC_RULINGS.md` and `QC_FIX_PLAYBOOK_v2.md` (same folder)
- `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/LEAK_LIBRARY.md`
- Live QC kit rule files for rule ids: `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC/` (`01_Instruction_QC.md`, `03_Tests_QC.md`, `04_Judge_QC.md`, `05_Alignment_Integrity_QC.md`).

## Inputs
| # | task | folder | recorded run (overall / tests / rubric) | run folder | QC report |
|---|---|---|---|---|---|
| 1 | ae640566-6067-508e-b982-0158d72da2d4 | `/Users/mac/Desktop/Terminal Bench/Anubis_Tasks_Samples/Perfect_for_Delivery/Sugam_Agrawal/ae640566-6067-508e-b982-0158d72da2d4/` | 59.59 / 34.97 / 84.21 | `/Users/mac/Desktop/Terminal Bench/Anubis_Tasks_Samples/Perfect_for_Delivery/Sugam_Agrawal/ae640566-6067-508e-b982-0158d72da2d4/trajectories/claude-opus-5/run_1/` | none in folder |
| 2 | af6f42c3-6bee-568f-a5d8-1459eb6dee7d | `/Users/mac/Desktop/Terminal Bench/Anubis_Tasks_Samples/Perfect_for_Delivery/Sugam_Agrawal/af6f42c3-6bee-568f-a5d8-1459eb6dee7d/` | 69.5 / 45.83 / 93.18 | `/Users/mac/Desktop/Terminal Bench/Anubis_Tasks_Samples/Perfect_for_Delivery/Sugam_Agrawal/af6f42c3-6bee-568f-a5d8-1459eb6dee7d/trajectories/claude-opus-5/run_1/` | none in folder |
| 3 | b47fd5f7-5a83-5aec-bdb1-d83d68ea1870 | `/Users/mac/Desktop/Terminal Bench/Anubis_Tasks_Samples/Perfect_for_Delivery/Sugam_Agrawal/b47fd5f7-5a83-5aec-bdb1-d83d68ea1870/` | 59.91 / 94.83 / 25.0 | `/Users/mac/Desktop/Terminal Bench/Anubis_Tasks_Samples/Perfect_for_Delivery/Sugam_Agrawal/b47fd5f7-5a83-5aec-bdb1-d83d68ea1870/trajectories/claude-opus-5/run_1/` | none in folder |
| 4 | ceab1cf6-7fe5-5824-8acf-a7485e2eb1cd | `/Users/mac/Desktop/Terminal Bench/Anubis_Tasks_Samples/Perfect_for_Delivery/Sugam_Agrawal/ceab1cf6-7fe5-5824-8acf-a7485e2eb1cd/` | 65.47 / 50.0 / 80.95 | `/Users/mac/Desktop/Terminal Bench/Anubis_Tasks_Samples/Perfect_for_Delivery/Sugam_Agrawal/ceab1cf6-7fe5-5824-8acf-a7485e2eb1cd/trajectories/claude-opus-5/run_1/` | none in folder |
| 5 | d22ff871-0564-5b0a-b08a-6f80f912e74b | `/Users/mac/Desktop/Terminal Bench/Anubis_Tasks_Samples/Perfect_for_Delivery/Sugam_Agrawal/d22ff871-0564-5b0a-b08a-6f80f912e74b/` | 32.36 / 25.93 / 38.78 | `/Users/mac/Desktop/Terminal Bench/Anubis_Tasks_Samples/Perfect_for_Delivery/Sugam_Agrawal/d22ff871-0564-5b0a-b08a-6f80f912e74b/trajectories/claude-opus-5/run_1/` | none in folder |

Each run folder holds `result.json`, `report.json`, `verifier/` (reward details, test stdout) and `agent/` (trajectory). Masked tasks have UUID names; use the UUID as the task id.
OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/_dev_research/delivery_study/sugam_b_bd5de18`

## Step 1, per task: is the test loss genuine? (all tasks first)
In `OUT/A_<task>.md`, verdict GENUINE / ARTEFACT / PARTLY with evidence: exception_info, timeouts, verifier errors, tracebacks, `Permission denied`, missing files, wrong output path. For each failed check: a wrong VALUE (genuine) or a gate/crash/path problem. A single gate check that zeroes many tests (schema, file name, one early exception) is PARTLY: name the gate and say whether the instruction states it clearly. Very low test scores (under 30) need the exact reason.

## Step 2, per GENUINE/PARTLY task: one card `OUT/C_<task>.md` with exactly these sections
1. **Scores and verdict**: overall/tests/rubric, Step 1 verdict, genuine test points lost.
2. **Inventory**: domain, archetype, files the agent sees (names, sizes, rows), instruction length in words, test count and weights, judge criteria count and mode, reward split.
3. **Test architecture**: how expected values are produced (fixed file, reference at test time, reseeded or mutated generator); hidden vs shipped inputs; isolated vs whole-document checks; partial credit; negatives and anti-cheat; mutation tests; weight shares from stacking_check.py (correct its hints by reading the code). Name the test-file functions that matter (file:line).
4. **Lever table** for every FAILED check: id, weight, rule graded, ALL locations of the rule (file:line, quote), sentence form (plain sentence / split across files / data header / implied by a definition / default + exception / scope by omission / other), agent's reading (step quote), correct reading, why the agent's own self-test missed it, is the rule fully stated somewhere visible (if NOT: mark HIDDEN RULE), nearest of our H1-H7 / L-ids or NEW.
5. **How the tests handle QC**: for each rule in our map that touches tests (at least TS-13, TS-16, TS-19, TS-20, TS-26, IN-15, IN-16, AL-28, CL-4, JD-7), how this task's tests satisfy it, with file:line. Where the task does something `QC_RULINGS.md` or `QC_FIX_PLAYBOOK_v2.md` treats as risky and it still passed QC, quote both sides. Use the QC report if one exists (warns accepted, pre-fix fails and how they were fixed).
6. **Leak avoidance**: how the trap stays hidden while the rule stays stated: wording (3-5 short quotes, mapped to W1-W7), whether shipped data separates the readings, visible tests or examples, file and column naming, where the rule sits relative to its use. Compare each with the matching `LEAK_LIBRARY.md` row (what we did that leaked vs what they did).
7. **Agent behaviour**: files read and order, minute of the first full program, whether the graded logic changed after it, self-tests run (data used, which levers they covered), where it went wrong, final claim vs reality.
8. **Passed checks**: grouped, and what made them easy.
9. **Take-aways**: patterns to adopt (SAFE / RISKY with reason), patterns to avoid, each in 1-2 lines with no task content.

## Step 3: group summary `OUT/GROUP_SUMMARY.md`
1. Table: task, verdict, overall/tests/rubric, genuine test points lost, main lever shape.
2. Test-design patterns ranked by genuine test points they caused to be lost (SAFE/RISKY only): mechanism, how it is graded, how it passes QC, tasks showing it.
3. Leak-avoidance patterns, with the LEAK_LIBRARY row each one would have fixed.
4. Where these tasks differ from our LEVER_RULES (things they do that our rules forbid or do not mention, and vice versa), with evidence.
5. Anti-patterns and artefacts found.
6. Open questions for the master.
7. `## Lessons for the master` (max 5 lines).

`OUT/result_bd5de18.json`: {"sha":"bd5de18","group":"sugam_b","status":"DONE|PARTIAL","repo_head":"<sha>","tasks":[{"task":"","verdict":"GENUINE|ARTEFACT|PARTLY","tests":x,"rubric":x,"genuine_tests_points_lost":x,"lever_shapes":[]}],"patterns":N,"report":"/Users/mac/Desktop/Terminal Bench/master_chat_work/_dev_research/delivery_study/sugam_b_bd5de18/GROUP_SUMMARY.md"}. It must parse.

Final reply (10 lines max): per task verdict and main reason for lost test points; top 3 test-design patterns; top 2 leak-avoidance patterns; any artefact; report path. Next step: the synthesis session reads all four group summaries.
