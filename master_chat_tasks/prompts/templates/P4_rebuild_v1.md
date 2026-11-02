# P4 Rebuild a weak task, template v1 (21 Oct 2026)

Use this when P3 returns REBUILD. Continue the builder's session with it if that session is still alive, otherwise start a new one.

=== PASTE BELOW ===

You are strengthening one Harbor 0.24 bundle that the hardness audit marked REBUILD. Edit the bundle in place. Never regenerate it and never use `--force`.

First read in full: `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/templates/_COMMON_RULES.md`. Then read `WORK/DESIGN.md`, `WORK/LEVERS.md` and the hardness report below.

## Inputs
- BUNDLE: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/[[SLUG]]/`
- WORK: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/[[SLUG]]/`
- HARDNESS REPORT: `[[HARDNESS_REPORT_PATH]]` (round [[ROUND]])
- Master's instructions on which fixes to apply, and any new levers: [[MASTER_FIXES]]
- OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/[[DATE]]_[[SLUG]]/rebuild_r[[ROUND]]/`

## Rules
- Fix the causes the report names, and only those, plus the master's additions.
- Order of preference: add separating hidden cases and checks; move a DERIVABLE lever's visible data so the samples no longer separate the readings; add a new lever. Change weights only as a last step. The partial-solver lever is the number of checks, not the size of weights.
- Never make the task easier to pass QC. Never hide a rule. Never remove a check without replacing it with one that fails the same wrong solver.
- After any data edit, re-embed the data, recompute `reward.toml` and update the TRUTH.md sha256 values (common rule 6). Update `LEVERS.md`, `DESIGN.md` (add a "Round N changes" section) and TRUTH.md.

## Steps
1. Write the change plan in `WORK/PLAN.md` under "Rebuild round [[ROUND]]": one line per fix, and the solver it must defeat.
2. Apply the changes.
3. Re-run the 4 QC scripts, the validator (`--archetype [[ARCHETYPE]]`), playground static, and the oracle through the real tests (it must be 1.0). Fix any FAIL you caused.
4. Write `OUT/REBUILD_REPORT.md`: changes, files touched, new check count and weights per lever, gate results.

Stop after 3 rebuild rounds in total for this bundle. Report "ROUND LIMIT" and wait for Ayush.

Final reply: DONE or BLOCKED, the fixes applied, the new check count, the oracle score, and the report path. The next step is a fresh P3 session.
