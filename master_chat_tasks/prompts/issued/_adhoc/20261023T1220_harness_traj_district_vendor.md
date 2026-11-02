# Harness chat: queue trajectories for district-heat + vendor-archive, 23 Oct 12:20 IST

=== PASTE BELOW ===

Queue two trajectory runs. Both bundles passed QC with 0 fails (district v5 0/2/2 board 2fd95f2, vendor v6 0/2/3 board 9bc33e6; kit 71a653b2).

1. From the harness clone run:
   `.venv/bin/python scripts/master_queue.py add "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/district-heat-flex-procurement" "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/vendor-archive-roundtrip-recovery"`
   The runner is stopped; if `add` does not start it, run `.venv/bin/python scripts/master_queue.py start`. Max concurrent stays 2.
2. Rules: no `--delete`, no image prune, never touch other sessions' containers. On a startup network error, report it and do not retry.
3. Do not edit either bundle.
4. When both finish, reply with the queue table (task, attempt, state) and, for each run, the job folder and the scores line (combined, tests %, rubric %, failed checks).
