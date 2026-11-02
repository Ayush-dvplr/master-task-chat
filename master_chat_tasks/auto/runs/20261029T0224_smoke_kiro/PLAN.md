# PLAN: smoke test of the upgraded auto mode on Kiro (Ayush 29 Oct 02:23)

Until: 02:55 IST
Paid runs: 0 (no harness runs)
Workers/harness/Docker: 2 / 1 (no harness runs) / 0
Budget: no paid run
Wind-down: none
Last spawn: 02:50
Ayush's words (verbatim):
> Start auto mode with AUTO_MODEL=kiro/claude-opus-5.5 and 2 tiny workers (t1 and t2). Each replies, then gets one follow-up.

## Do, in this order
1. Spawn t1smoke with auto/smoketest/t1.md and t2smoke with auto/smoketest/t2.md (`AUTO_MODEL=kiro/claude-opus-5.5 auto.py spawn`).
2. When each reports done, read its reply and send one follow-up (`AUTO_MODEL=kiro/claude-opus-5.5 auto.py send`): t1smoke "Reply with exactly: T1 STEP2 OK"; t2smoke "Reply with exactly: T2 STEP2 OK".
3. When both step-2 replies are in, summarise for Ayush. Stop only when Ayush says so.

## Do not
- No board.json/registry/pending changes, no harness runs, no Docker, no real task work, no pushing, no deletes.

## Timed steps (the watcher delivers each at its time)
