# Draft write inbox protocol

## Location and worker file

Proposed master DB: `master_chat_tasks/pipeline.sqlite`; worker inbox: `master_chat_tasks/inbox/<board-sha>.json`. The worker's only shared-state write is its own inbox JSON. It may still write its assigned OUT artifacts. The master owns the DB and generated views. This follows Ayush's U15 wording in `20261030_upgrade2/REQUEST.md`, sections A/E, and the current board SHA convention in `tools/board.py:1-8,42-52`.

The inbox extends the existing `result_<sha>.json` object. Keep every existing result key at top level. Add:

```json
{
  "sha": "abcdef0",
  "slug": "example-task",
  "step": "P11",
  "status": "DONE",
  "report": "QC/reports/example-task/v1.md",
  "inbox_version": 1,
  "written_at": "2026-10-30T21:00:00+05:30",
  "board_base": {"status": "issued", "updated": "2026-10-30 20:50"},
  "result_path": "QC/reports/example-task/result_abcdef0.json",
  "result_sha256": "64 lowercase hex characters",
  "artifacts": [{"path": "QC/reports/example-task/v1.md", "sha256": "64 lowercase hex characters"}],
  "proposed_changes": [{"type": "qc_round", "source": "QC/reports/example-task/result_abcdef0.json"}]
}
```

`sha` is the exact seven-character board ID; `slug` and `step` must match the issued board row. The result's original fields remain valid, including P11 `fail/minor/warn/rewards/ql_rows/kit` (`prompts/templates/P11_full_qc_v3.md:105`), P2 build metrics (`P2_build_v5.md:148`), and P12 fix metrics (`P12_recheck_fix_v4.md:73`). Research/adhoc results that lack `slug` or `step` today add the values from the board; the old result stays untouched and its hash proves provenance. `result_path` is optional only if the board points to a directory instead of a JSON file; then the inbox itself is the canonical result. `artifacts` may be empty. `proposed_changes` are suggestions, never commands accepted blindly.

Worker validates JSON locally, writes a unique temp file in `inbox/` with mode 0600, flushes and `fsync`s it, then uses `os.replace(temp, inbox/<sha>.json)` and `fsync`s the directory. A worker may revise its own inbox file until Ayush says `done: <sha>`. The final path must contain one complete JSON object and no secrets. Workers must not open `pipeline.sqlite`, `pending.db`, or any other master record for writing. Concurrent workers for one SHA are a protocol violation; the master detects a changed hash at merge and stops.

## Master merge after `done: <sha>`

1. Look up an **exact** SHA in `sessions`; refuse unknown, ambiguous, or already superseded IDs. `board.py show` currently accepts prefixes (`tools/board.py:60-62`), so the new merge must be stricter.
2. Read `inbox/<sha>.json` once, enforce a size limit (proposed 1 MiB), parse strict JSON (no duplicate keys or non-finite numbers), require `inbox_version=1`, valid SHA, and matching `sha/slug/step`. Refuse symlinks or paths escaping the allowed OUT/QC roots. Verify `result_sha256` and artifact hashes; inspect the report and any task tree before accepting claims. Current intake checks result parse and TODO lines (`tools/intake.py:75-111`) and job tree/score evidence (`tools/intake.py:114-168`); retain those checks.
3. Compare `board_base` to the issued state. A normal transition from `issued` to `running` is allowed; a different completion, changed result path, task tree SHA, or incompatible stage is a conflict. Record a conflict with both versions and leave the inbox file untouched. Never silently pick the newer timestamp.
4. Start one `BEGIN IMMEDIATE` transaction. Require the SHA still exists and has the expected state. Insert `session_results`, validated typed rows, `source_records`, and `inbox_merges`; update session and pending state together. Generated `BOARD.md` and `STATUS.md` are refreshed *after* commit from one DB snapshot. On any validation or SQL error, roll back the whole transaction; leave inbox for retry.
5. Repeating `done: <sha>` with the same inbox file SHA returns `already merged` without a new stage, score, or pending-history row. A different file SHA for an already merged SHA creates `inbox_conflicts` and stops. Corrections use a new board SHA or a master-authored explicit amendment referencing the original SHA. Preserve the inbox file as an audit artifact; never delete or rewrite it after merge.

The worker cannot create a decision, waiver, score validity, or exception merely through `proposed_changes`. The master applies rule checks and records Ayush's authorizing words for exceptions. `intake.py` currently requires `--ayush-ok` on regrade and validates frozen tree SHAs (`tools/intake.py:145-164`).

## Auto mode

Auto mode may observe inbox readiness and report `ready for done: <sha>` in its run state/events. It may set a session `running` through the master-owned path. It does **not** merge the inbox until Ayush's exact `done: <sha>` arrives, per U15. Auto's own operational `state.json` and `events.jsonl` remain local to the auto run; their snapshots/events can be imported by the master. `auto/auto.py:225-248` already locks its state file, but `auto/auto.py:219-223` appends events without that lock.

## Failure and recovery

Malformed/unknown/mismatched inbox: leave the file, report the exact validation error, write a conflict row only if the SHA is known, and await a corrected worker file or a new session. Database busy: wait up to five seconds, then retry later; never let a worker fall back to direct DB writes. Crash before commit: transaction rolls back. Crash after commit but before generated Markdown: rerender views; `inbox_merges` prevents duplicate ingestion. A result file that has changed after `result_sha256` was computed is refused. The original `result_<sha>.json` and inbox both remain on disk.
