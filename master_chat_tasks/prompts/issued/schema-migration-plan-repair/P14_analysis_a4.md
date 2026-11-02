# P14 Task analysis: schema-migration-plan-repair, trajectory attempt 4 (from template P14_task_analysis_v1, 24 Oct 2026)

=== PASTE BELOW ===

You are studying 1 finished Harbor 0.24 task of our own, schema-migration-plan-repair, after its fourth real trajectory run. The goal: find out whether this task has a NATURAL TRAP. A natural trap is a fully stated rule that claude-opus-5 can plausibly misread on unseen data and that our tests could grade, or whether tests at 100 are the honest ceiling. Also confirm one judge defect and propose its fix. This is a trajectory autopsy (B1) of one task only. Board id: `41af690`. This prompt is saved at `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/schema-migration-plan-repair/P14_analysis_a4.md`.

Why this matters: attempt 4 scored 46.16 overall, 100 tests (57/57 positives), -7.69 rubric. The gate needs tests < 100 as well, so it is not met. The harden P9 v2 r1 levers were L1 (RECEIPT green control), L2 (RECEIPT make-it-match), L5 (TOKENS strict beside normalising) and L6 (RECEIPT scope carried by a definition). The agent beat all four. A blind solve (cee149a) also scored tests 100. Before we spend another harden round, we must know whether any lever-grade misreading exists in this task at all.

Read first:
- `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/templates/_COMMON_RULES_v2.md`
- `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/LEVER_RULES_v1.md` (sections 0-4)
- `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/LEAK_LIBRARY.md`
- `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/QC_RULINGS.md`
- the `master_process` lines in `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/lessons.jsonl`

## Rules that survive compaction
- First thing: rename this session to `41af690`:
  python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/name_session.py" 41af690
  If the list does not show it, note that in the report and carry on; never retry on another ID. Run it again as the last step.
- Tools are always available. Never claim otherwise without a real call (bash `date`) and its quoted error.
- READ ONLY. No Docker, no harbor, no pip. Edit nothing except files under OUT. Never edit the Anubis repo, the harness clone, our bundles, the WORK folder or the master records. Read-only git only (log/show/rev-parse). Never commit, push, pull or open a PR.
- You MAY run the agent's delivered repository and our oracle locally with `python3` on copies placed under OUT (never inside the bundle or the job folder), to compare outputs. Standard library only.
- After every compaction: run `date`, re-read this prompt, then `OUT/TODO.md`, and continue from the first unticked item. Copy this section word for word into any compaction summary.
- Keep `OUT/TODO.md` (one line per phase) and `OUT/LOG.md` (IST times) current after every step.
- Read files in pieces of at most 50 KB. `agent/trajectory.json` is large: use `python3`/`jq` to list steps (index, tool, command first 200 chars, output first 300 chars), then read only the steps you need. Never print a whole trajectory.
- Every claim has evidence: a quote with file:line, a trajectory step index, or command output. Anything inferred is marked INFERRED. Never guess a score.
- No repo HEAD to record (not a git checkout); write `"repo_head":"n/a"` and record `find "<task folder>" -type f -not -path '*/.git/*' | sort | xargs shasum | shasum` once as the bundle fingerprint instead.

## Inputs
| # | slug | task folder | recorded run (overall / tests / rubric) | run folder |
|---|---|---|---|---|
| 1 | schema-migration-plan-repair | `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/schema-migration-plan-repair` | attempt 4 (23 Oct 21:15-23:11): 46.16 / 100 / -7.69 | `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261023_schema-migration-plan-repair/traj_a4/job/trajectory/claude-opus-5/Run 1` (job root one level up: `.../traj_a4/job`) |

History: attempt 3 (22 Oct, v0): tests 99.3, rubric 69.57; blind solve cee149a: tests 100. Use only these numbers for earlier attempts.

Recorded judge result in attempt 4: met R1, R2, R9; missed R3 (E_PARSE probes) and R4 (spaced null token). R6 (-5, "opens a path under /tests, /solution or /logs/verifier") FIRED because the agent opened `/app/repo/tests/test_visible.py`, which instruction.md:11 itself names. Our view is that this is a judge defect. R8 (-3) fired because the agent claimed under 10 s while its own stress run took 78 s; the graded SCALE worlds (world_04/08/12/15/18/28) all passed and `TIME_LIMIT_SEC=10` is at tests/test_output.py:30. Our view is that R8 is genuine. Our paper estimate: with R6 fixed, rubric 30.8 and overall 65.4.

Our own design notes (allowed here, this is our task): WORK = `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/schema-migration-plan-repair` (DESIGN.md, DESIGN_SUMMARY.md, LEVERS.md, PLAN.md, QC_DEFENCE.md, TRUTH.src.md, trap/, wrong/, measure_variants.py, check_worlds.py). Read LEVERS.md from "## Harden P9 v2 r1" onward, and DESIGN.md, to see what each lever was meant to catch.

Live QC kit for Phase B section 8: `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC/` (`01_Instruction_QC.md`, `03_Tests_QC.md`, `04_Judge_QC.md`, `05_Alignment_Integrity_QC.md`).
OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261023_schema-migration-plan-repair/p14_a4`

## Phase A: is the score genuine?
Write `OUT/A_schema-migration-plan-repair.md` with a verdict GENUINE / ARTEFACT / PARTLY and the evidence:
1. `result.json` exception_info, agent timeout or step limit, verifier errors; `verifier/` stdout and reward details for tracebacks, skipped tests, collection errors.
2. Tests at 100: confirm every positive check really ran the agent's delivered repository on the hidden worlds (not a skipped or trivially satisfied check). List any check whose pass you cannot explain from the delivered code.
3. Judge: confirm from `judge_response.txt` which criteria were met or fired. For R6, quote the criterion text, the trajectory step where the agent opened `/app/repo/tests/test_visible.py`, and instruction.md:11. Say whether R6 also fires on any act that was really forbidden. For R8, quote the claim (step) and the stress timing (step). For R3 and R4: is each one meetable (JD-7: the oracle trajectory or solution meets it)? Is it graded on behaviour, not a figure? Is the miss genuine?
4. Write a proposed R6 wording that keeps the anti-peeking intent (root `/tests`, `/solution`, `/logs/verifier`) and cannot fire on `/app/repo/tests/`. Check it against JD rules in `04_Judge_QC.md` (quote the rule ids). Re-score attempt 4 on paper with the new wording and give rubric and overall (overall = 0.5 tests + 0.5 rubric; confirm the split from the bundle).

## Phase B: how it is built and where the agent nearly lost points
Write `OUT/B_schema-migration-plan-repair.md` with these sections:
1. **Inventory**: domain, archetype, files the agent sees (names, sizes, rows), instruction length (words), tests and weights, hidden worlds (how generated), judge criteria count and mode, reward split.
2. **Rule map**: every graded rule in ALL its locations (file:line, quote). Give each rule's sentence form (one plain sentence / split across files / data header / example / implied by a definition / scope by omission / default + exception). Mark whether the trap is explained in the text (Y/N) and whether the shipped data separates the readings (Y/N).
3. **Lever table** for L1, L2, L5, L6 and every other rule the hidden worlds exercise. Columns: id, weight, rule graded, the step where the agent first coded it (quote), right on the first write (Y/N), did a self-test touch it (Y/N, step), why it held, family (A-F or NEW), nearest LEVER_RULES id.
4. **Near misses**: every place in the trajectory where the agent first wrote a wrong reading and later corrected it, or hesitated between readings. For each, give the step, both readings, and what made it correct itself (a visible test, shipped data, a rule sentence). These are the natural-trap candidates.
5. **Agent behaviour** (trajectory autopsy): files read and order; did it read every rule file fully; plan; minute of first full repair and whether graded logic changed after it; self-tests (data used, rules covered); step count; time per phase; final claim vs reality.
6. **Test design**: how expected values are produced; partial credit; whole-document cascades; weight shares (use `python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/stacking_check.py" "<task folder>"` and correct its hints).
7. **Judge design**: any criterion breaking JD-7/JD-8/JD-15/JD-18 (quote the rule), beyond R6.
8. **QC safety**: for each natural-trap candidate from section 4, would a lever built on it pass our live QC? Check at least IN-15, IN-16, TS-13, TS-16, TS-19, TS-20, TS-26, AL-27, AL-28. Mark SAFE / RISKY (why) / NOT ALLOWED. Compare with `knowledge/QC_RULINGS.md`.

## Phase C: summary
Write `OUT/GROUP_SUMMARY.md`:
1. Table: task, verdict A, overall/tests/rubric, judge points lost genuinely, judge points lost to defects (R6), paper score with R6 fixed.
2. **Natural traps**: each candidate from B4 that is fully stated, reachable on unseen data, not reflexive and QC SAFE. Give the step evidence and the rule quote, how a hidden world would separate the readings, and the expected loss for a program with the wrong reading. If none qualifies, write the single line `NO NATURAL TRAP` and say why the agent cannot be caught on tests (as for district and sensor).
3. **Judge fix**: the R6 wording from A4, plus any other judge change that grades behaviour the agent really got wrong (R3, R4, R8), with weights only 1, 3 or 5 (negatives -1, -3, -5).
4. **Recommendation** for the master: HARDEN (name the trap and the smallest test change), JUDGE ONLY (fix R6 and park), or PARK.
5. Open questions for the master chat.
6. `## Lessons for the master` (max 5 lines).

`OUT/result_41af690.json`: {"sha":"41af690","group":"schema-a4","status":"DONE|NO NATURAL TRAP","repo_head":"n/a","bundle_fingerprint":"<sha>","verdict":"GENUINE|ARTEFACT|PARTLY","natural_traps":[{"rule":"","evidence":"","qc":"SAFE|RISKY"}],"patterns":["<one line each>"],"r6_fix":"<new criterion text>","paper_rubric_r6_fixed":x,"paper_overall_r6_fixed":x,"recommendation":"HARDEN|JUDGE ONLY|PARK","report":"<OUT>/GROUP_SUMMARY.md"}. The `sha` value is the board id. It must parse.

Final reply (10 lines max): verdict; natural traps found (or NO NATURAL TRAP) with the rule quote; the R6 fix and paper score; recommendation; report path.
