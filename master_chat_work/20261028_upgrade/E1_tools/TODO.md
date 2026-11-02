# TODO 7fdff25 (E-code-1)
- [x] name_session start, read plan + specs, back up issue/intake/status to bak/
- [x] auto tests before (46 OK)
- [x] A3 status.py FIELDS + stage_since + MT_ROOT
- [x] A1 issue.py ql kind, time box, --by, _2 suffix, MT_ROOT
- [x] A2 intake.py FINAL_GATE, events, regrade, tree_sha, refusals, dry row
- [x] A4 repackage_one.py
- [x] tests MT/tools/tests/test_upgrade_tools.py green (23 ok)
- [x] verify commands + negatives -> REPORT.md
- [x] auto tests after (46 OK)
- [x] result_7fdff25.json, name_session end

# TODO 7fdff25 E1 (Batch 2: limit detection + budget)
- [x] name_session start, read prompt + plan v2 E1 :229-235 :294, exp1.py
- [x] backups: bak/auto.py bak/test_auto.py bak/master_queue.py + H/.master-queue/backup-20261029T0124-e1/
- [x] auto tests before (46 OK)
- [x] P1 busy_ids/retry_ids split
- [x] P2 LIMIT state + notifier + LIMIT CLEARED
- [x] P3 spawn/harness refused while LIMIT
- [x] P4 RESET_IN_RE seconds, +5 min pad, resume keyed by task (auto + MQ)
- [x] P5 AUTH (401 / exit 8) not LIMIT (auto + MQ)
- [x] P6 budget: harness refused if >2 busy; <=3 busy while paid run RUNNING
- [x] P7 accounts exhausted during paid run: log only
- [x] new tests green; tools tests 23 OK; exp1 reset check + negative; status; MQ ast + --help
- [x] REPORT_E1.md, result_7fdff25_E1.json, name_session end
