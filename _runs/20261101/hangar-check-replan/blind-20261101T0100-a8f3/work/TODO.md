# TODO (board d0dc88d / hangar-check-replan / blind-20261101T0100-a8f3)

- [x] 0. Rename session to d0dc88d
- [x] 1. Read instruction.md and every doc/data file it points to
- [x] 2. Write solution program once, completely (app/derive_report.py + out/derive_report.py)
- [x] 3. Self-check on shipped data only (one run, /usr/bin/time -p, logged in work/CHECKS.md) — PASS
- [x] 4. Freeze; write work/FINAL_REPLY.md
- [x] 5. Write work/BLIND_REPORT.md and work/result.json
- [x] 6. Verify no stray python processes (ps -axo pid,rss,command | grep python) — none of mine

ALL DONE. Frozen; no further iteration.

## Rules that survive compaction
- First thing: rename this session to `d0dc88d`:
  python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/name_session.py" d0dc88d
  If the list does not show it, note that in the report and carry on; never retry on another ID.
- Tools are always available. Never claim otherwise without a real call (bash `date`) and its quoted error.
- After every compaction: run `date`, re-read this prompt, then `/Users/mac/Desktop/Terminal Bench/_runs/20261101/hangar-check-replan/blind-20261101T0100-a8f3/work/TODO.md`, and continue from the first unticked item. Copy this section word for word into any compaction summary.
- Read ONLY files inside `/Users/mac/Desktop/Terminal Bench/_runs/20261101/hangar-check-replan/blind-20261101T0100-a8f3`. Never open, list or search anything else: no `master_chat_work/`, `master_chat_tasks/`, bundles, `QC_*`, `_runs/` or `/tmp` outside BLIND_DIR, the harness clone, the Anubis repo, or any `tests/` or `solution/` folder anywhere. No web lookups. No subagents.
- No Docker, no harbor, no pip, no git. Python 3 standard library only.
- Every run of your program goes under a 600 s wall-clock cap: `perl -e 'alarm 600; exec @ARGV' python3 ...` (macOS has no `timeout`, and `ulimit -v` fails here). Before you finish, `ps -axo pid,rss,command | grep python` must show no python process of yours still running; kill any you left.
