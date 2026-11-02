# Common rules for every Upgrade-2 research session (S1-S9)

You are one research session of "Upgrade 2" for Ayush's Terminal-Bench task pipeline on this Mac. The master chat (an opencode session) runs you with `codex exec` and reads your files when you finish. Ayush's request and answers so far: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261030_upgrade2/REQUEST.md` (read it first, in full).

## Hard limits
1. Read-only everywhere except your OUT folder (given in your session prompt). Never edit, move, rename or delete anything outside OUT. No git commit, push, pull, checkout or reset anywhere (read-only git like `git log`, `git status`, `git diff` is fine).
2. No Docker runs, no harness runs, no paid agent runs, no network requests, no package installs, unless your session prompt explicitly allows one. Never print or copy secrets (auth.json, API keys, tokens, passwords, `~/.config/oc-bridge/secret`).
3. The opencode database `~/.local/share/opencode/opencode.db` is live: open it read-only only (`sqlite3 "file:<path>?mode=ro" ...` or python `sqlite3.connect('file:...?mode=ro', uri=True)`); never write it.
4. Do not touch running work: other sessions and Docker jobs may be active. Do not kill processes.

## Evidence
5. Every claim carries evidence: `path:line`, a JSON path, a command plus its output excerpt, or a count you computed (with the command). Mark anything you could not verify as `UNVERIFIED` and anything you inferred as `INFERRED`. Never present a guess as a finding.
6. When you measure, say exactly what was measured, over which files/dates, and how.

## Efficiency (Ayush: the upgrade must cost less tokens and time without lowering task quality)
7. Read big files in pieces; prefer `rg`, `wc`, `jq`, `sqlite3`, small python scripts over reading whole files. Put any script you write in OUT/scripts/ so the master can re-run it.
8. Stop searching once your questions are answered with evidence; do not pad.

## Deliverables (in OUT)
- `FINDINGS.md`: first line `VERDICT: <one sentence>`. Then sections per question in your prompt: finding, evidence, recommendation (what to change, where, expected gain, risk of breaking something that works today, how to verify it).
- `QUESTIONS.md`: questions only Ayush can answer, each with options and your recommended option plus the reason. No question you could answer from the files.
- `result.json`: `{"session":"<Sx>","status":"DONE|PARTIAL","findings":N,"recommendations":N,"questions":N,"unverified":N,"files":[...]}` (must parse).
- Any extra files your prompt asks for.
Your last terminal message: 5 lines max: verdict, counts, paths. Write in plain, short English.

## Context you can rely on (read only what your session needs)
- Root: `/Users/mac/Desktop/Terminal Bench/` (TB below).
- Master control folder: `TB/master_chat_tasks/` (GOALS.md, README.md, board.json + BOARD.md (session board), registry/tasks.json (task stages), pending.db (pending items via tools/pending.py), decisions.jsonl, feedback.jsonl, lessons.jsonl, open_questions.json, state.json, knowledge/ (INDEX.md, KNOWLEDGE.md, LEVER_RULES_v3.md, QC_RULINGS.md, QC_FIX_PLAYBOOK_v3.md, FP_DOSSIER.md, archetypes.md, ANGLES.md, TEAMMATE_MODELS_v1.md), prompts/templates/ (P1-P17 versions, _COMMON_RULES_v5.md, CHANGELOG.md), prompts/issued/<slug>/ (every prompt sent), tools/ (status.py, board.py, pending.py, intake.py, issue.py, trajectory_readout.py, repackage_one.py, decide.py, registry_check.py, precheck.sh, stacking_check.py, xref_check.py, name_session.py), auto/ (auto.py, AUTO_POLICY.md, PLAN_TEMPLATE.md, plans/, runs/<stamp>/REPORT.md, tests/)).
- Master work folder: `TB/master_chat_work/` (bundles/<slug> working copies, bundles/_work/<slug> worker notes, <date>_<slug>/ per-step outputs incl. gate_run_aN/TRIP.md, _ql/ QL exchanges, 20261028_upgrade/ (previous upgrade: P1_plan/UPGRADE_PLAN_v1.md, V1_verify/UPGRADE_PLAN_v2.md, APPLY_LOG.md, R1-R5 findings), 20261030_speed_measure/ (MEASURE.md, SPEED_PLAN_v1.md, on hold)).
- QC: `TB/QC/reports/<slug>/vN.md` + result_<sha>.json, `TB/QC/copies/<sha>/`. QC kit (authority on QC rules): `TB/Terminal_2.0_Harbor_Harness/Input_Bundle_QC/` (Starter.md, Final_checklist.md, gate files, exe_copy.py).
- Harness: `TB/Terminal_2.0_Harbor_Harness/` (Tasks_INPUT/<slug>, Output_RFP/<slug>, jobs/, scripts/master_queue.py).
- Older/other: `TB/master_chat/` (older master notes), `TB/harness_master_tasks/` (older harness master), `TB/beta-task-generator/` (generator), `TB/anubis-stage-1`, `TB/anubis-stage-2` (teammate task repos), `TB/Anubis_Tasks_Samples/`.
- Pipeline in one paragraph: the master issues sessions by board sha (P2 build, P9 harden, P11 QC, P12 fix, P13 blind, P16/P17 QL loop); Ayush opens them or auto mode spawns them; a QC-passed bundle is frozen by tree sha and gets a paid harness run (claude-opus agent); gate today: tests < 85, rubric < 85, final < 40 (per-task exceptions recorded in decisions.jsonl); results are copied to gate_run_aN, read with trajectory_readout.py and recorded with intake.py; Ayush pushes.
