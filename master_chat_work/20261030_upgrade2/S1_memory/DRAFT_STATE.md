# DRAFT — generated master state snapshot

Generated for Upgrade-2 S1 research, 2026-10-30. NOT INSTALLED. Future owner: proposed `tools/generate_state.py`; read only source files, write one atomic snapshot after intake/status/board/pending/decision updates and at chat start. Target <= 2,000 words / <= 12 KiB. This draft is deliberately shorter; authoritative records remain linked below.

## Identity and authority
- Master advises Ayush on Terminal-Bench task building, hardening, QC, trajectory decisions, and next session prompts. Ayush runs manual paid harness and pushes; auto mode may run harness under an approved plan. Sources: `master_chat_tasks/README.md:1-7`, `feedback.jsonl:24`, `REQUEST.md:E`.
- Current gate: tests <85, rubric <85, final <40 except recorded per-task exceptions. Freeze exact QC-passed bytes, then count a valid harness run on those bytes. Source: `state.json:test_phase_gate`, `README.md:Pipeline`, `decisions.jsonl` latest task exceptions. **Resolve stale conflicting lines before applying them.**
- No test or judge-criterion count cap. Source: `feedback.jsonl:10`, `decisions.jsonl:112`. `state.json:targets.caps` is stale.

## Source map
- Task stage, scores, next step: `registry/tasks.json` via `tools/status.py`.
- Session sha, prompt, status: `board.json` via `tools/board.py`; `BOARD.md` is rendered view.
- Open questions/reminders/steps: `pending.db` via `tools/pending.py list`.
- Decisions and exceptions: `decisions.jsonl` (latest applicable entry wins only if no unresolved conflict); corrections: `feedback.jsonl`; process lessons: `lessons.jsonl`.
- Rules and checks: `knowledge/INDEX.md`, `knowledge/LEVER_RULES_v3.md`, `knowledge/QC_FIX_PLAYBOOK_v3.md`, current `Input_Bundle_QC/` kit, active `prompts/templates/`.
- Work and evidence: `master_chat_work/bundles/<slug>`, `master_chat_work/<date>_<slug>/`, `QC/reports/<slug>/`, harness `Tasks_INPUT/`, `Output_RFP/`, `jobs/`.

## Snapshot counts (read only, 30 Oct)
- Registry: 34 tasks; stages: pushed 12, parked 11, dropped 9, killed 1, fix 1. Source: `scripts/analyze_memory.py` on `registry/tasks.json`.
- Board: 352 rows, currently one running: `72ebb9d` (Nikhil fix). Source: `scripts/analyze_memory.py` on `board.json`.
- Pending: 457 total; open 32, running 3, waiting 15, done 367, dropped 40. Source: read-only SQLite status count in S1 research.
- Recent decision rows: 28 Oct 41, 29 Oct 89, 30 Oct 90; full file 589. Source: `scripts/analyze_memory.py`.
- Most recent registry `updated_ist`: `2026-10-30T21:03+05:30`; most recent recorded decision 22:43. These timestamps are different because decision events include the research kickoff.

## Live work and handoff
- Nikhil `b7c42a8f-6d19-4e35-9f82-5a3c1d7e8042`: registry stage `fix`, board `72ebb9d` running, QC v2 FAIL 13/7/1; next P11 recheck v3, freeze, harness, hand back. Sources: `registry/tasks.json` task pipeline, `board.json` sha `72ebb9d`, `decisions.jsonl:587`.
- No task currently `pl_ready` in registry (stage count above). Check again before every status reply.
- Do not infer that pending status mirrors board: 21 of 50 linked board rows updated 28-30 Oct disagree with pending item status. Reconcile before claiming a step finished. Source: `scripts/analyze_memory.py` and `FINDINGS.md` question 1.

## Standing interaction rules (pointer, not full copy)
- One exact clickable prompt link per action; include board sha/step, destination, result path. Do not mark running until Ayush confirms. Harness handoff: bundle path only. Sources: `feedback.jsonl:8-14`.
- A changed bundle voids previous gate runs; check tree SHA before shipping. Source: `feedback.jsonl:18-19`, `state.json:targets.gate_runs`.
- Flag out-of-scope findings and ask before changing; flag author/trajectory-byte mismatches; mention `pl_ready` in status replies. Sources: `feedback.jsonl:22,25-26`.
- Read all current feedback before acting; keep this snapshot small and point to the full records.

## Open reconciliation
- Pending S358 says running while board 7d4de68 says done; S372/S373 say open while board rows say done. Nikhil running board 72ebb9d has no pending ID. Source: `FINDINGS.md` question 1.
- `state.json:targets.caps` and older pipeline gate text conflict with later `feedback.jsonl:10` and top-level `state.json:test_phase_gate`. Treat old text as stale; generator should emit a conflict warning until state config is cleaned by a separately approved change.

## Resume recipe
1. Read this snapshot and `DRAFT_BOOTSTRAP_PROMPT.md` (once installed under approved names); check their generation timestamp.
2. Run `tools/status.py`, `tools/pending.py list`, and `tools/board.py show <sha>` for the task in question. Read the last decisions and all feedback.
3. Verify current task files, QC copy, frozen tree SHA, and run source bytes before giving a go/ship answer.
4. If sources conflict, quote both and flag for reconciliation. Then update records through the established tools after each verified event.
