# P12 Recheck + fix QC findings, one bundle per session, template v2 (23 Oct 2026)

v2 changes (SETUP_PLAN_v1 Part 1.2/1.3, IMPROVEMENT_PLAN_v1 A2/C3/E3): no fix may undo a lever or add a giveaway; each fix is labelled with its effect on EVERY lever; the reflex program is re-run after the fixes, and a score above 0.20 is compensated in the same lever family before finishing; QC rulings on lever-touching rules are listed for `knowledge/QC_RULINGS.md`; "Lessons for the master". Everything else is v1 unchanged (rename, compaction rules, oracle x3, clash rules, result json).

Master duty before issuing (Ayush 10:53 23 Oct, major gap): read the QC report's fail/minor/warn list and write [[FIX_DIRECTIONS]]: one line per finding with FIX (the exact difficulty-keeping fix: file, what to change, to what), KEEP (one-line reason) or REBUT (why it is a false positive). Prefer fixing the oracle/data/judge wording over loosening a lever; never copy the report's "Fix:" line without checking it keeps the difficulty. A P12 prompt with an empty or generic directions block is not issued. Each line cites a row of `knowledge/QC_FIX_PLAYBOOK.md` and uses its section 2 format (Ayush 11:00 23 Oct: clear QC without softening the levers).

Runs after a P11 QC, in a NEW session (never the QC session). Master fills [[...]], checks it against `knowledge/PROMPT_CHECKLIST.md`, and issues it to `prompts/issued/<slug>/P12_r<round>.md`. Next: P11 re-run (max 3 P11/P12 rounds), then the trajectory through the harness queue.

=== PASTE BELOW ===

You are rechecking and then fixing the QC findings of ONE Harbor 0.24 bundle: `[[SLUG]]`. Board id: `[[SHA]]`. This prompt is saved at `[[PROMPT_PATH]]`.

## Rules that survive compaction
- First thing: rename this session to `[[SHA]]`:
  python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/name_session.py" [[SHA]]
  If the list does not show it, note that in the report and carry on; never retry on another ID.
- Tools are always available. Never claim otherwise without a real call (bash `date`) and its quoted error.
- After every compaction: run `date`, re-read this prompt, then `WORK/TODO.md`, and continue from the first unticked item. Never re-run a finished Docker block; check its log for ALL_DONE first. Copy this section word for word into any compaction summary.
- Keep `WORK/TODO.md` and `WORK/LOG.md` current after every step. Read files in pieces of at most 50 KB.
- Read first, in full: `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/templates/_COMMON_RULES_v2.md`, then `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/_adhoc/20261022_round_notes.md` sections C, E, F, G, then `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/LEVER_RULES_v1.md`, `QC_RULINGS.md` and `QC_FIX_PLAYBOOK.md` (same folder). The playbook is the rule for how each finding is fixed: its DO column, never its NEVER column.
- Never commit, push, pull or open a PR. Read-only git only. Never edit the harness clone, the QC kit, `QC assigned/`, `my tasks/`, or any QC copy under `QC/copies/`. Edit only BUNDLE and WORK.

## Inputs
- BUNDLE (edit here): `[[BUNDLE]]`
- WORK: `[[WORK]]`
- QC report: `[[QC_REPORT]]` (and its `result_*.json` if present)
- Reflex program (agent program from the last valid trajectory, or the P13 blind-solve program; NONE if neither): `[[REFLEX_PROGRAM_OR_NONE]]`
- QC kit (live rules): `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC/`. Record `git -C "/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness" rev-parse HEAD` once. The live kit is the authority, even if newer than the report's kit; say so in a row whose rule changed.
- OUT: `[[OUT]]`

## Master's fix directions (one line per QC finding)
[[FIX_DIRECTIONS]]
Follow these unless your Phase 1 recheck proves one wrong (false positive, or the fix would make the task easier); then do the difficulty-keeping alternative and explain it in RECHECK_FIX.md under "Deviations from master directions".

## Phase 0: defence and cross-reference files (only if missing)
1. `WORK/QC_DEFENCE.md`: one entry per lever and per deliberate design choice: what it is, why it is there (which wrong reading it punishes), which QC check it could trip, why that is not a defect (quote the rule), and the safe fix if QC insists (one that keeps the difficulty). Build it from DESIGN.md, LEVERS.md, TRUTH.md and the bundle. Mark anything you inferred as INFERRED.
2. `WORK/XREF.md`: a ```json block `{"entries":[{"key":"","value":"","files":[...],"retired":[...]}]}` with every value that appears in more than one file: task name, slug, file and folder names, field and key names the instruction or tests use, stated figures, check IDs, judge figures. Then run `python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/xref_check.py" "<BUNDLE>" "<WORK>/XREF.md"`; it must print 0 findings before you change anything.
3. Reflex and trap baseline (QC_FIX_PLAYBOOK section 3 step 1): if a reflex program is given, score it on the CURRENT tests (tests channel, real `tests/test_output.py`) before any fix and record the number. Also record, per lever, the points lost by its single wrong-reading variant on the current tests.

## Phase 1: recheck every finding (no Docker)
For every ❌, 🟡 and ⚠️ in the report (and every FAIL row of its QL coverage table):
1. Quote the finding. Find the rule in the live kit by ID AND wording; quote it with file:line (say if the ID or wording changed).
2. Read every bundle file the rule concerns; quote evidence with file:line. If the rule is script-owned, run that script on BUNDLE and quote the line.
3. Read the matching QC_DEFENCE entry and any QC_RULINGS row for the same rule.
4. Label: REAL, FALSE_POSITIVE (quote both sides) or UNSURE (write the exact PL question).
5. Decide (Ayush rule 21:27):
   - REAL ❌: fix.
   - FALSE_POSITIVE ❌: do not fix; write a one-paragraph rebuttal with quotes.
   - 🟡 / ⚠️: fix if REAL and it matters. KEEP it unfixed if it is a false positive or not a major concern; write a one-line reason.
   - Suggestion test for every 🟡 / ⚠️ (Ayush 10:05 23 Oct, interim): "Would this fix make the task easier for the agent?" YES (e.g. state the rule beside its use, add a format hint, explain why a decoy is wrong) → KEEP, reason: "fixing it would reveal lever <L>; the instruction already settles it at <file:line>". NO and cheap (e.g. split a check that grades 2+ properties, fix a weight inversion, replace an absence-shaped or style-preference criterion) → FIX. Exception: if the finding shows a rule stated NOWHERE in the bundle (a hidden rule), fix it by stating the rule neutrally, never pointing at the trap. Every KEEP goes into `OUT/PL_NOTE.md`.
   - Caps are never waived: more than 70 tests or 70 judge criteria is always fixed.
6. For each fix, choose the option that keeps the difficulty: the master's direction, else the QC_DEFENCE "safe fix", else the playbook row's DO fix. Never apply a playbook NEVER fix, even if the report's "Fix:" line says so; record the row id used. Label its effect on EVERY lever in LEVERS.md: none, harder, easier, unknown. A fix may never undo a lever or add a giveaway: no trap explanation, no rule count, no worked example that separates the readings, no rule moved next to its use, no figure stated (LEVER_RULES W1, W2, W6, J1). For easier/unknown, add a compensating check or lever in the same family. Stop and report "PAUSED: <id>" only if no compensation exists.
Write each row to `OUT/RECHECK_FIX.md` as you finish it.

## Phase 2: apply, then verify once
1. Make the smallest change per fix. Keep tests, weights, `reward.toml`, LEVERS.md, TRUTH.md and QC_DEFENCE.md in step. After any data edit apply common rule 6.
2. Any rename or changed value: update every file listed for it in XREF.md, move the old value to `retired`, and re-run xref_check.py: 0 findings. Never rename the slug or the bundle folder.
3. Re-run the 4 QC scripts and the manual checks behind every fixed ID: 0 FAIL.
4. STACKING_CHECK after the fixes: run `python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/stacking_check.py" "<BUNDLE>"` and update `OUT/STACKING_CHECK.md` (LEVER_RULES section 5) if tests or judge changed.
5. Reflex re-run (LEVER_RULES section 6): score the reflex program (or, if NONE, the S2 and S4 solvers in `WORK/wrong/`) on the fixed tests. If it is above 0.20, compensate in the same lever family and re-score before finishing; after 2 tries above 0.20, report "PAUSED: reflex <score>". Then the trap-survival check (QC_FIX_PLAYBOOK section 3): re-run every single-lever variant; each lever must keep at least 90% of its before loss, reflex no more than 0.05 above before, no separating hidden case removed. Else compensate from playbook section 4, max 2 tries, then "PAUSED: trap <L> <before> -> <after>".
6. Warm the verifier image first (round notes G, "Warm the verifier image"): `docker build` the copy's tests/ (and environment/ if slow) in the background and wait for it, so Harbor's 900 s start limit never covers a cold download. Then: If tests/, solution/, environment/ or data changed: one Docker block, tests only, from copies built by the live kit's `exe_copy.py` (plain and `--owner-only`): oracle x3 = 1.000, owner-only x1 = 1.000, nop x1 = 0.000. Clash rules (round notes G): bundle lock, TS with seconds + random hex, no `--delete`, max 2 Docker-heavy jobs (check `docker ps`), one nohup chain with ALL_DONE, waits under 4 minutes. If nothing in those folders changed, skip Docker and say so.

## Deliverables
- `OUT/RECHECK_FIX.md`: table (ID, label, rule quote, evidence quote, decision fix/keep/rebut, playbook row, effect per lever, compensation, files changed), then gate results, the reflex score before and after, a `## Trap survival` table (playbook section 3 step 5), and a section `QC_RULINGS rows` with one line per finding on IN-15, IN-16, TS-13, TS-19, TS-20, TS-26, AL-28, JD-7 or JD-15 (rule, our design, QC verdict, our label, reason) for the master to copy. Last: `## Lessons for the master` (max 5 lines).
- `OUT/PL_NOTE.md`: false positives (rebuttals), kept minors (reasons), UNSURE questions. Short, plain words, ready for Ayush to send.
- `OUT/result_[[SHA]].json`: {"sha":"[[SHA]]","slug":"[[SLUG]]","step":"P12","status":"DONE|PAUSED","real":N,"false_positive":N,"unsure":N,"fixed":N,"kept_minor":N,"paused_ids":[],"lever_effects":{"<lever>":"none|harder|easier|compensated"},"reflex_before":x,"reflex_after":x,"trap_survival":"PASS|FAIL","lever_loss":{"<lever>":[before,after]},"stacking":"PASS|FAIL","oracle":[],"owner":x,"nop":x,"xref_findings":0,"qc_fail":0,"tree_sha":"<sha256 over sorted paths+contents, first 12>","report":"<path>"}. It must parse.

Final reply (8 lines max): counts REAL / FP / UNSURE, fixed, kept minors, paused IDs, reflex before/after, oracle x3 / owner / nop, QC scripts result, report path. Next step: master issues the P11 re-run.
