# Harness chat: queue emberforge trajectory, 23 Oct 00:59 IST

=== PASTE BELOW ===

Add one more task to the running batch. Do not stop or restart the runner, and do not touch the vendor-archive run or district-heat's queue slot.

1. From the harness clone, run `.venv/bin/python scripts/master_queue.py add "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/emberforge-vault-settlement"` so it queues after district-heat-flex-procurement (QC v5 PASS 0/0/1, kit 71a653b2).
2. Same rules as the batch: no `--delete`, no prune, and on a startup network error report it and do not retry.
3. Reply with the queue table: task, attempt, state, position. For each finished run, give me the job folder and the scores line.
