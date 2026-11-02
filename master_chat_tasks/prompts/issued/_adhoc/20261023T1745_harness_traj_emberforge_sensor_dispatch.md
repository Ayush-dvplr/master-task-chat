# Harness chat: queue trajectories for emberforge + sensor + dispatch, 23 Oct 17:45 IST

=== PASTE BELOW ===

Queue three trajectory runs. All three bundles now have 0 QC fails (kit 71a653b2): emberforge-vault-settlement (P12 r5, board 51efd20), sensor-network-lsq-correlated-adjustment (P12 r3, board 078d40a), dispatch-plan-reoptimization (QC v4 0/3/4, board 3a23fca). Tasks_INPUT holds older copies of all three. `add` replaces a stale copy and archives the old one, which is what we want.

1. From the harness clone run:
   `.venv/bin/python scripts/master_queue.py add "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/emberforge-vault-settlement" "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/sensor-network-lsq-correlated-adjustment" "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/dispatch-plan-reoptimization"`
   The runner is stopped. If `add` does not start it, run `.venv/bin/python scripts/master_queue.py start`. Max concurrent stays at 2, so the third task waits for a free slot.
2. Before the runs start, prove each Tasks_INPUT copy is the current bundle: `diff -rq "<master bundle>" "Tasks_INPUT/<slug>"` must print nothing for all three. Quote the `add` line for each task ("replaced", "copied" or "identical"). If any `add` prints "skip ... already queued or running", stop and tell me.
3. Rules: no `--delete`, no image prune, and never touch other sessions' containers. On a startup network error, report it and do not retry.
4. Do not edit any of the three bundles or their Tasks_INPUT copies.
5. When all three finish, reply with the queue table (task, attempt, state). For each run, give the job folder and the scores line (combined, tests %, rubric %, failed checks).
