# S6: Auto mode, speed and master decisions audit
OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261030_upgrade2/S6_auto_speed/`

Goal (Ayush U5, U6): improve auto mode and speed, merging the held speed plan, and audit the master's own process decisions.

Answer with evidence:
1. Read `TB/master_chat_work/20261030_speed_measure/SPEED_PLAN_v1.md` and `MEASURE.md` and the previous upgrade (`TB/master_chat_work/20261028_upgrade/V1_verify/UPGRADE_PLAN_v2.md`, `APPLY_LOG.md`, `R5_auto_issues/`). Which items were applied, which are still open, which are now wrong (code changed since)? Check against current `auto/auto.py`, `AUTO_POLICY.md`, `Terminal_2.0_Harbor_Harness/scripts/master_queue.py` (file:line).
2. Auto runs: read every `TB/master_chat_tasks/auto/runs/*/REPORT.md` and events.jsonl: list incidents (limits hit, stuck sessions, doom loops, wrong caps, idle time, manual interventions) with cause and the change that would prevent it. Output `INCIDENTS.csv`.
3. Waiting time: measured 35% of worker time waiting on Ayush/master. From board.json (issued -> running -> done times) and decisions.jsonl, which decision types caused the longest waits, and which of them could be pre-approved by rule (with the rule text).
4. Speed experiments: parallel Docker lanes were used on 30 Oct (QC 02c7202, warrant fix d872b22 gate, cold-chain QC c75ddad). From their runs.log/lane logs (paths in their QC reports or RECHECK_FIX.md) measure per-run time vs earlier serial runs of the same task; did contention slow runs, by how much?
5. Proposed changes ranked by (time saved x safety), each with: file to change, test that proves it, risk to what works now. Mark which need Ayush's OK.
