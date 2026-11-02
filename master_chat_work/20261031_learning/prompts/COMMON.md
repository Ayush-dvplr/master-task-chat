# Common rules for every learning session (L1-L7), night of 31 Oct 2026

You are one learning session for Ayush's Terminal-Bench task pipeline on this Mac. Tonight is LEARNING ONLY: no task is built or changed. The master chat reads your files in the morning.

## Strict ground rules (breaking one = your output is thrown away)
1. Do ALL work yourself in this main chat. Do NOT spawn sub-agents, helper agents or parallel agents of any kind.
2. Never run `claude`, `opencode`, `codex`, `harbor`, `kiro-cli` or any other AI agent CLI, and never call an AI API.
3. Read-only everywhere except your OUT folder (in your session prompt). Never edit, move, rename or delete anything outside OUT. No git write commands (log/status/diff/show are fine).
4. No Docker runs, builds, pulls, prunes or deletes. (L4 alone may run read-only Docker listing commands named in its prompt.)
5. No network unless your session prompt says web search is on. Never print or copy secrets (auth.json, API keys, tokens, `~/.config/oc-bridge/secret`, `.env`).
6. The opencode DB `~/.local/share/opencode/opencode.db` is live: open it read-only only (`sqlite3 "file:<path>?mode=ro"` or python `uri=True`).
7. Don't touch running work; don't kill processes.

## Evidence
- Every claim carries evidence: `path:line`, a JSON path, or a command + output excerpt, or a count with the command that made it. Mark guesses `INFERRED` and unchecked items `UNVERIFIED`.
- Put every script you write in OUT/scripts/ so it can be re-run. Prefer `rg`, `jq`, `sqlite3`, small python over reading huge files whole.

## Earlier research you must build on (read the parts you need; don't redo them)
- `TB/master_chat_work/20261030_upgrade2/` S1-S9 (FINDINGS.md each): S4_task_study (TASKS.csv, LEVER_WEIGHTS.csv, FIX_MAP.csv over anubis-stage-2), S5_build_method, S6_auto_speed (INCIDENTS.csv), S7_cli_workers.
- `TB/master_chat_work/20261030_speed_measure/MEASURE.md`; `TB/master_chat_work/20261028_upgrade/` R3 (hardness claims/levers), R4 (teammate cards, ANGLES).
- `TB/master_chat_tasks/knowledge/` (LEVER_RULES_v3.md, QC_FIX_PLAYBOOK_v3.md, QC_RULINGS.md, FP_DOSSIER.md, TEAMMATE_MODELS_v1.md, ANGLES.md).

## Map (TB = `/Users/mac/Desktop/Terminal Bench`)
- QC kit (authority on QC rules): `TB/Terminal_2.0_Harbor_Harness/Input_Bundle_QC/` (Starter.md, Final_checklist.md, 01_Instruction_QC.md .. 05_Alignment_Integrity_QC.md, scripts).
- QC reports: `TB/QC/reports/<slug>/vN.md`, `result_<sha>.json`, `KEPT.md`; QC copies `TB/QC/copies/<sha>/`.
- Fix outputs: `TB/master_chat_work/<date>_<slug>/p12_fix_*/` (RECHECK_FIX.md, KEPT.md, PL_NOTE.md, result_*.json); hardens `harden_*/`; paid runs `gate_run_aN/` (TRIP.md).
- Control: `TB/master_chat_tasks/` (board.json, registry/tasks.json, decisions.jsonl, feedback.jsonl, prompts/templates/, prompts/issued/<slug>/, auto/ (auto.py, AUTO_POLICY.md, runs/<stamp>/REPORT.md + events.jsonl)).
- Harness: `TB/Terminal_2.0_Harbor_Harness/` (Tasks_INPUT, Output_RFP, scripts/master_queue.py, .master-queue/).
- Teammate repos: `TB/anubis-stage-2/` (102 tasks, `<uuid>/{task.toml, instruction.md, environment, solution, tests, trajectories/<model>/...}`), `TB/anubis-stage-1/`.
- Gate today: tests < 85, rubric < 85, final < 40 (some tasks had recorded exceptions in decisions.jsonl).

## Deliverables in OUT
- `FINDINGS.md`: line 1 `VERDICT: <one sentence>`, then one section per question in your prompt: finding, evidence, what to change (where), expected gain, what it could break, how to check it.
- `QUESTIONS.md`: only what Ayush must decide; plain words; options with the recommended one first.
- `result.json`: `{"session":"Lx","status":"DONE|PARTIAL","findings":N,"recommendations":N,"questions":N,"unverified":N,"files":[...]}` (must parse).
- Extra files your prompt asks for.
Last terminal message: at most 5 lines (verdict, counts, paths). Plain, short English.
