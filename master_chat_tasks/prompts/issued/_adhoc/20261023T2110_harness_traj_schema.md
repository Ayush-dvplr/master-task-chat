# Harness chat: queue trajectory for schema-migration-plan-repair, 23 Oct 21:10 IST (board 27b2e45)

=== PASTE BELOW ===

Queue one trajectory run: schema-migration-plan-repair. The bundle now has 0 QC fails (QC v7, board 8f891ea, kit 71a653b2: 0 fail / 1 minor kept / 3 warns approved by Ayush). Tasks_INPUT holds an older copy (last scored attempt 3, 84.44/99.3/69.57). `add` replaces a stale copy and archives the old one, which is what we want.

1. From the harness clone run:
   `.venv/bin/python scripts/master_queue.py add "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/schema-migration-plan-repair"`
   If the runner is stopped and `add` does not start it, run `.venv/bin/python scripts/master_queue.py start`. Max concurrent stays at 2; if emberforge-vault-settlement or another run holds the slots, schema waits.
2. Before the run starts, prove the Tasks_INPUT copy is the current bundle: `diff -rq "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/schema-migration-plan-repair" "Tasks_INPUT/schema-migration-plan-repair"` must print nothing. Quote the `add` line ("replaced", "copied" or "identical"). If `add` prints "skip ... already queued or running", stop and tell me.
3. Rules: no `--delete`, no image prune, and never touch other sessions' containers. On a startup network error, report it and do not retry.
4. Do not edit the bundle or its Tasks_INPUT copy.
5. When it finishes, reply with the queue table (task, attempt, state), the job folder, and the scores line (combined, tests %, rubric %, failed checks, judge criteria failed and negatives fired).
