# S3: One proper database with a write inbox
OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261030_upgrade2/S3_database/`

Goal (Ayush U15): a proper SQLite database for the pipeline; running terminals never write it directly; they write a JSON file next to it; the master merges the JSON into the DB only when Ayush says "done: <sha>", so no other terminal writes the master's DB.

Answer with evidence:
1. Today's records: list every JSON/JSONL/SQLite the pipeline writes (registry/tasks.json, board.json, pending.db, decisions.jsonl, feedback.jsonl, lessons.jsonl, scores.jsonl, open_questions.json, state.json, auto runs state.json/events.jsonl, master_queue state, result_<sha>.json files), their schemas (fields seen, with counts), writers (which tool, file:line), and every place two writers can race (no lock). Output `RECORDS.csv`.
2. Schema: propose tables (tasks, stages history, sessions/board, runs/scores, qc rounds+findings, decisions, feedback, pending, levers, exceptions) with keys and indexes; show how each current record maps in (`MAPPING.md`). Keep human-readable views (generated BOARD.md / STATUS) for Ayush.
3. Inbox protocol: file name and JSON schema a worker writes (one file per session sha, atomic write via temp + rename), how the master validates and merges (idempotent, refuses unknown sha, keeps the inbox file as audit), what happens on conflict, and how auto mode uses it. Check what result_<sha>.json files look like today and make the inbox a superset.
4. Safety: SQLite settings (WAL, busy_timeout, single writer = master), backups (when, where, how many), migration from today's files with a dry run and a row-count check, rollback.
5. Cost: estimate the tokens/time saved for the master (fewer file reads, one query instead of 5 files) and the work to migrate the tools that read/write today's files (list each tool and function).
Write a DRAFT `schema.sql` and `INBOX_SPEC.md` in OUT (not installed).
