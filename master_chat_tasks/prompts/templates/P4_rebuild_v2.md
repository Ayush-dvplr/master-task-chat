# P4 Rebuild a weak task, template v2 (23 Oct 2026)

v2 changes (SETUP_PLAN_v1 Part 1, IMPROVEMENT_PLAN_v1 A2/E3): fixes follow `knowledge/LEVER_RULES_v1.md` (never pasted); reflex pre-mortem before any edit; STACKING_CHECK + reflex gate (<= 0.20); no fix may undo a lever or add a giveaway; board-id rename, compaction rules, result json; "Lessons for the master".

Use this when P3 v2 returns REBUILD. Continue the builder's session with it if that session is still alive, otherwise start a new one. Master checks the filled prompt against `knowledge/PROMPT_CHECKLIST.md`.

=== PASTE BELOW ===

You are strengthening one Harbor 0.24 bundle that the hardness audit marked REBUILD. Edit the bundle in place. Never regenerate it and never use `--force`. Board id: `[[SHA]]`. This prompt is saved at `[[PROMPT_PATH]]`.

## Rules that survive compaction
- First thing: rename this session to `[[SHA]]`:
  python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/name_session.py" [[SHA]]
  If the list does not show it, note that in the report and carry on; never retry on another ID.
- Tools are always available. Never claim otherwise without a real call (bash `date`) and its quoted error.
- After every compaction: run `date`, re-read this prompt, then `WORK/TODO.md`, and continue from the first unticked item. Never re-run a finished Docker block; check its log for ALL_DONE first. Copy this section word for word into any compaction summary.
- Keep `WORK/TODO.md` and `WORK/LOG.md` current after every step. Read files in pieces of at most 50 KB.
- Read first, in full: `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/templates/_COMMON_RULES_v2.md`, `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/LEVER_RULES_v3.md`, `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/LEAK_LIBRARY.md`, `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/QC_FIX_PLAYBOOK.md` (QC_DEFENCE fallbacks use its DO fixes); then `WORK/DESIGN.md`, `WORK/LEVERS.md`, `WORK/QC_DEFENCE.md` and the hardness report below.
- Never commit, push, pull or open a PR. Read-only git only. Edit only BUNDLE, WORK and OUT.

## Inputs
- BUNDLE: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/[[SLUG]]/`
- WORK: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/[[SLUG]]/`
- HARDNESS REPORT: `[[HARDNESS_REPORT_PATH]]` (round [[ROUND]])
- Reflex program (trajectory or P13 blind-solve; NONE if neither): `[[REFLEX_PROGRAM_OR_NONE]]`
- Master's instructions on which fixes to apply, and any new levers: [[MASTER_FIXES]]
- OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/[[DATE]]_[[SLUG]]/rebuild_r[[ROUND]]/`

## Rules
- Fix the causes the report names, and only those, plus the master's additions.
- Order of preference: add separating hidden cases and whole-document checks (G1); move a DERIVABLE lever's rule into the file that governs its data and remove any visible separating example (W2, W5, W6); add a new lever from LEVER_RULES section 1. Change weights only as a last step.
- No change may undo a lever or add a giveaway (W1: no trap explanation, no rule count, no worked separating example). Never hide a rule. Never remove a check without replacing it with one that fails the same wrong solver.
- After any data edit, apply common rule 6. Update `LEVERS.md`, `DESIGN.md` (add a "Round N changes" section), `QC_DEFENCE.md` and TRUTH.md.

## Steps
1. Reflex pre-mortem: append to `WORK/PREMORTEM.md` (create it if missing) how claude-opus-5 would solve the CURRENT bundle in its first 10 minutes (files read in order, the program it writes once, its self-tests, its reading of each rule), and the point where each kept or new lever makes that program wrong. A lever its first write would get right is redesigned now.
2. Write the change plan in `WORK/PLAN.md` under "Rebuild round [[ROUND]]": one line per fix, the solver it must defeat, and its effect on every lever (none / harder / easier).
3. Apply the changes.
4. Re-run the 4 QC scripts, the validator (`--archetype [[ARCHETYPE]]`), playground static, and the oracle through the real tests: oracle x3 1.0 (oracle x3 per Ayush; the kit asks x5), nop 0.0. Fix any FAIL you caused.
5. STACKING_CHECK and reflex gate (LEVER_RULES sections 5 and 6): run `python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/stacking_check.py" "<BUNDLE>"`, write `OUT/STACKING_CHECK.md`, and score the reflex program (or, if NONE, your S2 and S4) on the real tests: <= 0.20. Above 0.20: strengthen in the same lever family, max 2 tries, then report "PILOT WEAK: <score>".
6. Write `OUT/REBUILD_REPORT.md`: changes, files touched, the per-lever effect of every fix, new check count and weights per lever, weight shares, stacking verdict, reflex scores, gate results, anything not run, and last `## Lessons for the master` (max 5 lines).
7. Write `OUT/result_[[SHA]].json`: {"sha":"[[SHA]]","slug":"[[SLUG]]","step":"P4 r[[ROUND]]","status":"DONE|BLOCKED|PILOT_WEAK|ROUND_LIMIT","fixes":N,"tests":N,"criteria":N,"reflex":x,"stacking":"PASS|FAIL","oracle":[],"nop":x,"qc_fail":0,"tree_sha":"<first 12>","report":"<path>"}. The `sha` value is the board id. It must parse.

Stop after 3 rebuild rounds in total for this bundle. Report "ROUND LIMIT" and wait for Ayush.

Final reply (8 lines max): DONE, BLOCKED or PILOT WEAK; fixes applied; new check count; reflex score; stacking result; oracle; report path. The next step is a fresh P3 v2 session.
