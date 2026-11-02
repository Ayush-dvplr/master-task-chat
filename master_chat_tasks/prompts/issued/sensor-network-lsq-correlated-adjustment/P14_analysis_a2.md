# P14 Task analysis: sensor-network-lsq-correlated-adjustment, trajectory attempt 2 (from template P14_task_analysis_v1, 23 Oct 2026)

=== PASTE BELOW ===

You are studying 1 finished Harbor 0.24 task of our own, sensor-network-lsq-correlated-adjustment, after its second real trajectory run. The goal is to learn exactly HOW claude-opus-5 kept (or lost) points, so we can design levers that hold. This is a trajectory autopsy (B1) of one task only. Board id: `e30c85c`. This prompt is saved at `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/sensor-network-lsq-correlated-adjustment/P14_analysis_a2.md`.

Why this matters: our levers leaked because each rule was one plain sentence (sometimes with the trap explained), so the agent coded it right on the first write and checked itself on its own data. This task has had one harden round (H1-CENTRING, H2-ANGLE-REDUCE, H3-REVISION, H4-CHAIN). Local wrong-solution mutants scored 8/62, but the real agent still scored tests 100. A low score is NOT evidence of a good lever until you prove it is genuine.

Read first:
- `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/templates/_COMMON_RULES_v2.md`
- `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/LEVER_RULES_v1.md` (sections 0-4)
- `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/LEAK_LIBRARY.md`
- `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/QC_RULINGS.md`
- the `master_process` lines in `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/lessons.jsonl`

## Rules that survive compaction
- First thing: rename this session to `e30c85c`:
  python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/name_session.py" e30c85c
  If the list does not show it, note that in the report and carry on; never retry on another ID. Run it again as the last step.
- Tools are always available. Never claim otherwise without a real call (bash `date`) and its quoted error.
- READ ONLY. No Docker, no harbor, no pip, no edits anywhere except OUT. Never edit the Anubis repo, the harness clone, our bundles, the WORK folder or the master records. Read-only git only (log/show/rev-parse). Never commit, push, pull or open a PR.
- After every compaction: run `date`, re-read this prompt, then `OUT/TODO.md`, and continue from the first unticked item. Copy this section word for word into any compaction summary.
- Keep `OUT/TODO.md` (one line per phase) and `OUT/LOG.md` (IST times) current after every step.
- Read files in pieces of at most 50 KB. `agent/trajectory.json` is large: use `python3`/`jq` to list steps (index, tool, command first 200 chars, output first 300 chars), then read only the steps you need. Never print a whole trajectory.
- Every claim has evidence: a quote with file:line, a trajectory step index, or command output. Anything inferred is marked INFERRED. Never guess a score.
- No repo HEAD to record (not a git checkout); write `"repo_head":"n/a"` and record `find "<task folder>" -type f -not -path '*/.git/*' | sort | xargs shasum | shasum` once as the bundle fingerprint instead.

## Inputs
| # | slug | task folder | recorded run (overall / tests / rubric) | run folder |
|---|---|---|---|---|
| 1 | sensor-network-lsq-correlated-adjustment | `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/sensor-network-lsq-correlated-adjustment` | attempt 2 (23 Oct 19:44-20:01): 90.0 / 100 / 80 (22/24) | `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261023_sensor-network-lsq-correlated-adjustment/traj_a2/job/trajectory/claude-opus-5/Run 1` (job root one level up: `.../traj_a2/job`) |

History: attempt 1 (20 Oct, bundle v0, before the harden) scored 71.16 / 100 / 42.31; its job folder no longer exists, so use only the number.

Our own design notes (allowed here, this is our task): WORK = `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/sensor-network-lsq-correlated-adjustment` (DESIGN.md, LEVERS.md, PLAN.md, QC_DEFENCE.md, baselines.json, trap/, wrong/). Read LEVERS.md and DESIGN.md to know what each lever was meant to catch.

Live QC kit for Phase B section 8: `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC/` (`01_Instruction_QC.md`, `03_Tests_QC.md`, `04_Judge_QC.md`, `05_Alignment_Integrity_QC.md`).
OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261023_sensor-network-lsq-correlated-adjustment/p14_a2`

## Phase A: is the score genuine?
Write `OUT/A_sensor-network-lsq-correlated-adjustment.md` with a verdict GENUINE / ARTEFACT / PARTLY and the evidence:
1. `result.json` exception_info, agent timeout or step limit, verifier errors; `test-stdout.txt` for tracebacks, `Permission denied`/`Errno 13`, `No such file`, timeouts, import or collection errors, skipped tests.
2. Did the verifier actually run the agent's program/outputs on the hidden inputs? A tests score of 100 must be proven real: list every check and show it ran against the agent's output (not skipped, not trivially true).
3. Near-100 scores need the exact reason.
4. Judge: did it read the response? R5 (named-function code structure, w3) failed: was that about the agent's work or an unmeetable criterion (JD-7: the oracle must meet it)? The two "failed" negatives (negative_hardcoded_sample_answers, negative_external_dependency) mean the penalty did NOT fire; confirm that from judge_response.txt.
5. Permission setup: does tests/test.sh or test_output.py chmod/chown /logs/verifier, grant read on the agent's files, or run as another user?
If ARTEFACT, write one paragraph and skip Phase B except instruction/test design worth noting.

## Phase B: how it is built and why no test points were lost
Write `OUT/B_sensor-network-lsq-correlated-adjustment.md` with these sections:
1. **Inventory**: domain, archetype, files the agent sees (names, sizes, rows), instruction length (words), tests and weights, isolated vs whole-output checks, hidden/reseeded inputs (how generated), judge criteria count and mode, reward split.
2. **Rule map**: every graded rule: ALL locations (file:line, quote); sentence form (one plain sentence / split across files / data header / example / implied by a definition / scope by omission / default + exception); trap explained in the text (Y/N); shipped data separates the readings (Y/N).
3. **Lever table** for EVERY lever in WORK/LEVERS.md (V0-1..V0-12 and H1-H4) plus every failed check or criterion: id, weight, rule graded, the step where the agent first coded it (quote), was it right on the first write (Y/N), did a self-test on shipped data touch it (Y/N, step), why it leaked or held, fully stated somewhere visible (if NOT: HIDDEN RULE, not allowed for us), family (A-F or NEW), nearest LEVER_RULES id (L1-L7 or none).
4. **Contrast**: why 8/62 local mutants lost points but the real agent did not. For each wrong/ mutant, name the mistake it encodes and whether the agent was ever close to making it (step evidence or "never"). Compare with `LEAK_LIBRARY.md`.
5. **Agent behaviour** (trajectory autopsy): files read and order; did it read every spec fully; plan; minute of first full program write and whether graded logic ever changed after it; self-tests (data used, levers covered); where it hesitated or nearly went wrong; step count; time per phase; final claim vs reality.
6. **Test design**: how expected values are produced (fixed file, oracle at test time, reseeded generator); partial credit; negatives and anti-cheat; whole-document checks; weight shares (isolated / whole-document / shipped-only; use `python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/stacking_check.py" "<task folder>"` and correct its hints).
7. **Judge design**: R1-R4 are "states figure X" criteria (w3 each) that passed. Did they reward reasoning or only copying a printed number? Why did R5 fail? Any criterion breaking JD-7/JD-8/JD-15/JD-18 (quote the rule).
8. **QC safety**: for each lever that cost points or could, would it pass our live QC? At least IN-15, IN-16, TS-13, TS-16, TS-19, TS-20, TS-26, AL-28. SAFE / RISKY (why) / NOT ALLOWED. Compare with `knowledge/QC_RULINGS.md`.
9. **Writing style**: 3-5 short quotes from our instruction or docs that gave the trap away or made the rule reflexive, and the W1-W7 rule each breaks.

## Phase C: summary and lever candidates
Write `OUT/GROUP_SUMMARY.md`:
1. Table: task, verdict A, overall/tests/rubric, genuine points lost on tests, genuine points lost on judge.
2. **Why the harden failed**: for H1-H4, one line each with the step evidence.
3. **Natural traps**: the places in this domain (correlated least squares, centring, angle reduction, revisions, chains) where the agent's trajectory shows real hesitation, a wrong first attempt, or an unchecked assumption. Only these are lever candidates. For each: mechanism in 2 lines, how the rule could be fully stated but not reflexive, why a self-test on shipped data would miss it, family, nearest L-id, SAFE/RISKY. If you find none, say "NO NATURAL TRAP" plainly (like district-heat) and stop Phase C there.
4. **Anti-patterns**: what looked hard but cost nothing.
5. **Score artefacts** found in Phase A.
6. **Judge fix proposals**: replacing "states figure" criteria with criteria the agent can fail genuinely, each within JD rules.
7. **Proposed LEVER_RULES changes** (new lever, changed rule) with evidence, for the master to decide. Never edit LEVER_RULES yourself.
8. Open questions for the master chat.
9. `## Lessons for the master` (max 5 lines).

`OUT/result_e30c85c.json`: {"sha":"e30c85c","group":"sensor-a2","status":"DONE|NO NATURAL TRAP","repo_head":"n/a","bundle_fingerprint":"<sha>","tasks":[{"slug":"sensor-network-lsq-correlated-adjustment","verdict":"GENUINE|ARTEFACT|PARTLY","tests":x,"rubric":x,"genuine_tests_points_lost":x,"levers":["pattern names"]}],"natural_traps":N,"patterns":N,"report":"<OUT>/GROUP_SUMMARY.md"}. The `sha` value is the board id. It must parse.

Final reply (10 lines max): verdict and why tests scored 100; why each of H1-H4 leaked; the top 3 natural-trap candidates (or NO NATURAL TRAP); any artefact found; report path.
