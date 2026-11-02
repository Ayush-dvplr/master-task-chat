# L1: QC failures, the fixes we applied, and what the fixes broke
OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261031_learning/L1_qc_fixes/`

Ayush: "check all the QC reports, what failed, how it went after the fixes, what new errors the fixes caused."
1. Build `QC_FINDINGS.csv`: one row per finding in every `TB/QC/reports/*/v*.md` (task, report version, check id, severity ❌/minor/warn, one-line problem, file:line it names). Say how you parsed (script in OUT/scripts).
2. Link rounds: for each finding in round N, what happened in round N+1 of the same task: FIXED, CAME BACK (same id, same place), MOVED (same id, new place), KEPT/REBUTTED (KEPT.md, PL_NOTE), or NOT RECHECKED. Use the fix outputs (`master_chat_work/*/p12_fix_*/RECHECK_FIX.md`) to say what each fix actually changed.
3. Fix side effects: every NEW finding in round N+1 that touches a file or criterion the round-N fix edited = "caused by the fix" (say how you matched). Build `FIX_EFFECTS.csv` (task, fix sha, edit, new finding id, why linked). Extend S4 FIX_MAP (11 rows), don't repeat it.
4. Per check id (top 20 by number of tasks): `FIX_RECIPES.md` = what the problem usually is, the fix that worked (with task examples), the fix that failed or broke something, and a 1-line "do this at build time so it never appears".
5. Rounds: how many QC rounds each task needed, and which check ids alone forced an extra round.
Extra files: QC_FINDINGS.csv, FIX_EFFECTS.csv, FIX_RECIPES.md.
