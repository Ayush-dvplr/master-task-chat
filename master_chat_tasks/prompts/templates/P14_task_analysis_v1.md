# P14 Task analysis (own or peer tasks), template v1 (23 Oct 2026)

New (IMPROVEMENT_PLAN_v1 A2 "Analysis", B1, B2). The standard structure from the G1-G5 peer mining (Phase A genuineness, Phase B per-task build and loss analysis, Phase C group summary). Use it for groups of up to 4 tasks: peer tasks listed as new/changed by `tools/peer_manifest.py check`, or our own tasks after a trajectory (then it is the trajectory autopsy, B1). Master fills `[[...]]`, checks it against `knowledge/PROMPT_CHECKLIST.md`, and issues it to `prompts/issued/_adhoc/<YYYYMMDDTHHMM>_analysis/<group>.md`.

=== PASTE BELOW ===

You are studying [[N_TASKS]] finished Harbor 0.24 tasks. The goal is to learn exactly HOW claude-opus-5 lost (or kept) points, so we can design levers that hold. Board id: `[[SHA]]`. This prompt is saved at `[[PROMPT_PATH]]`.

Why this matters: our levers leaked because each rule was one plain sentence (sometimes with the trap explained), so the agent coded it right on the first write and checked itself on its own data. Read first: `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/LEVER_RULES_v1.md` (sections 0-4) and `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/LEAK_LIBRARY.md`. A low score is NOT evidence of a good lever until you prove it is genuine.

## Rules that survive compaction
- First thing: rename this session to `[[SHA]]`:
  python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/name_session.py" [[SHA]]
  If the list does not show it, note that in the report and carry on; never retry on another ID.
- Tools are always available. Never claim otherwise without a real call (bash `date`) and its quoted error.
- READ ONLY. No Docker, no harbor, no pip, no edits anywhere except OUT. Never edit the Anubis repo, the harness clone, our bundles or the master records. Read-only git only (log/show/rev-parse). Never commit, push, pull or open a PR.
- After every compaction: run `date`, re-read this prompt, then `OUT/TODO.md`, and continue from the first unticked item. Copy this section word for word into any compaction summary.
- Keep `OUT/TODO.md` (one line per task per phase) and `OUT/LOG.md` (IST times) current after every step.
- Read files in pieces of at most 50 KB. `agent/trajectory.json` files are large: use `python3`/`jq` to list steps (index, tool, command first 200 chars, output first 300 chars), then read only the steps you need. Never print a whole trajectory.
- Every claim has evidence: a quote with file:line, a trajectory step index, or command output. Anything inferred is marked INFERRED. Never guess a score.
- Peer tasks: extract PATTERNS, never content. Do not copy task text, data or code into anything that will go into our bundles. Short quotes in the report are fine as evidence.
- Record `git -C "<repo root of the tasks>" rev-parse HEAD` once.

## Inputs
| # | slug | task folder | recorded run (overall / tests / rubric) | run folder |
|---|---|---|---|---|
[[TASK_ROWS]]

Live QC kit for Phase B section 8: `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC/` (`01_Instruction_QC.md`, `03_Tests_QC.md`, `04_Judge_QC.md`, `05_Alignment_Integrity_QC.md`).
OUT: `[[OUT]]`

## Phase A, per task: is the score genuine? (all tasks first)
Write `OUT/A_<slug>.md` with a verdict GENUINE / ARTEFACT / PARTLY and the evidence:
1. `result.json` exception_info, agent timeout or step limit, verifier errors; `test-stdout.txt` for tracebacks, `Permission denied`/`Errno 13`, `No such file`, timeouts, import or collection errors, skipped tests.
2. Did the verifier actually run the agent's program/outputs? For each failed check: a wrong VALUE (genuine) or a missing file, crash, unreadable path, wrong output location, or harness problem (artefact)?
3. Near-0 or near-100 scores need the exact reason. A single gate check that zeroes everything (schema, file name) is PARTLY: record the gate and whether the instruction states it clearly.
4. Judge: did it read the response? Which criteria failed, and was each about the agent's work or an unmeetable criterion (JD-7: the oracle must meet it)?
5. Permission setup: does tests/test.sh or test_output.py chmod/chown /logs/verifier, grant read on the agent's files, or run as another user?
If ARTEFACT, write one paragraph and skip Phase B except instruction/test design worth noting.

## Phase B, per GENUINE/PARTLY task: how it is built and why points were lost
Write `OUT/B_<slug>.md` with these sections:
1. **Inventory**: domain, archetype, files the agent sees (names, sizes, rows), instruction length (words), tests and weights, isolated vs whole-output checks, hidden/reseeded inputs (how generated), judge criteria count and mode, reward split.
2. **Rule map**: every graded rule: ALL locations (file:line, quote); sentence form (one plain sentence / split across files / data header / example / implied by a definition / scope by omission / default + exception); trap explained in the text (Y/N); shipped data separates the readings (Y/N).
3. **Lever table** for every FAILED check and criterion: id, weight, rule graded, agent's reading (step quote), correct reading, mechanism, would a self-test on shipped data catch it (Y/N, why), fully stated somewhere visible (if NOT: HIDDEN RULE, not allowed for us), family (A-F or NEW), nearest LEVER_RULES id (L1-L7 or none).
4. **Contrast**: the PASSED checks, grouped, and what made them easy; compare with `LEAK_LIBRARY.md`.
5. **Agent behaviour** (trajectory autopsy): files read and order; did it read every spec fully; plan; minute of first full program write and whether graded logic ever changed after it; self-tests (data used, levers covered); where it went wrong; step count; time per phase; final claim vs reality.
6. **Test design**: how expected values are produced (fixed file, oracle at test time, reseeded generator); partial credit; negatives and anti-cheat; whole-document checks; weight shares (isolated / whole-document / shipped-only; use `python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/stacking_check.py" "<task folder>"` and correct its hints).
7. **Judge design**: failed criteria and why; reusable patterns; any breaking JD-7/JD-8/JD-15/JD-18 (quote the rule).
8. **QC safety**: for each working lever, would it pass our live QC? At least IN-15, IN-16, TS-13, TS-16, TS-19, TS-20, TS-26, AL-28. SAFE / RISKY (why) / NOT ALLOWED. Compare with `knowledge/QC_RULINGS.md`.
9. **Writing style**: 3-5 short quotes showing how a rule is stated without giving the trap away, and the technique each shows (map to W1-W7).

## Phase C: group summary
Write `OUT/GROUP_SUMMARY.md`:
1. Table: task, verdict A, overall/tests/rubric, genuine points lost on tests, genuine points lost on judge.
2. **Lever patterns**, ranked by genuine points cost, SAFE or RISKY only: name, mechanism in 2 lines, how the rule is written, why the self-test misses it, tasks showing it (evidence file), family, nearest L-id, and one line on applying it to a data-reconciliation task.
3. **Writing patterns** that keep a rule fully stated but not reflexively solvable.
4. **Anti-patterns**: looked hard but cost nothing; levers that only work because the rule is hidden.
5. **Score artefacts** found in Phase A.
6. **Proposed LEVER_RULES changes** (new lever, changed rule) with evidence, for the master to decide. Never edit LEVER_RULES yourself.
7. Open questions for the master chat.
8. `## Lessons for the master` (max 5 lines).

`OUT/result_[[SHA]].json`: {"sha":"[[SHA]]","group":"[[GROUP]]","status":"DONE","repo_head":"<sha>","tasks":[{"slug":"","verdict":"GENUINE|ARTEFACT|PARTLY","tests":x,"rubric":x,"genuine_tests_points_lost":x,"levers":["pattern names"]}],"patterns":N,"report":"<OUT>/GROUP_SUMMARY.md"}. The `sha` value is the board id. It must parse. (Its `tasks` entries feed `registry/peer_tasks.json` via `peer_manifest.py add`.)

Final reply (10 lines max): per task verdict and the main reason it lost points; the top 3 SAFE patterns; any artefact found; report path.
