# PLAN for this auto run: learning-run check-ins only (Ayush 31 Oct ~01:35)

Until: 09:00 IST
Paid runs: 0 (no paid runs tonight)
Workers/harness/Docker: 1 / 1 / 0 Docker-heavy (no worker is spawned tonight)
Budget: no paid run
Wind-down: none
Last spawn: 01:40
Ayush's words (verbatim):
> Let it continue., Timed check-ins: add these also if anything goes wrong or stopped due to any reson and restart that sessions again or from whre they left okay
> (answers) every 2 h 03:00, 05:00, 07:00; 2 tries; stuck = 30 min no log growth; usage limit -> wait for reset and resume; L5 picks 15 tasks by rule; let them finish in the morning; proceed.

## Do, in this order
1. Nothing at start. The supervisor script `master_chat_work/20261031_learning/supervise_learning.sh` (no AI) runs and restarts the Codex learning sessions L1-L7 by itself.
2. At each timed step: check the learning run (see the step text), fix only what the supervisor cannot (e.g. supervisor dead -> restart it; a FAILED session whose cause is fixable -> one resume), and append a short entry to `master_chat_work/20261031_learning/CHECKINS.md`.

## Do not
- Spawn any worker session, start any harness/paid run, or start any task work (tonight is learning only).
- Run claude/opencode workers for the learning; Codex sessions only, main chat only, no sub-agents.
- Edit rule files, templates, tasks or bundles. Docker prune or any Docker run.
- Touch Nikhil's QC 0d957b9 (its result waits for the morning).

## Timed steps (the watcher delivers each at its time)
- at 03:00: CHECK-IN 1 learning run: read master_chat_work/20261031_learning/supervisor.log (tail), every L*/status.txt and result.json; confirm supervisor pid alive; rule check on codex*.log (no claude/opencode/harbor/codex/docker runs, no writes outside OUT, no spawn_agent); restart the supervisor if dead; append CHECKINS.md.
- at 05:00: CHECK-IN 2 learning run: same checks as check-in 1; append CHECKINS.md.
- at 07:00: CHECK-IN 3 learning run: same checks; spot-check 3 claims in finished FINDINGS.md files against their sources; append CHECKINS.md.
