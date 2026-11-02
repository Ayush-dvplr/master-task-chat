# REPORT E3-E6 (board 478e1df): stop and final report, decisions file, policy + plan template, LOW cleanups

Status: DONE. All four items are in, built on E1/E2 (`notify`, `retry_ids`, `report_line`, LIMIT/AUTH, hold file, `note_master_hold` retry-only per Ayush 29 Oct 01:58: all unchanged).
Files changed: `MT/auto/auto.py` (1867 -> 2071 lines), `MT/auto/tests/test_auto.py` (1005 -> 1279; 12 new tests, 2 test-harness changes listed below), `MT/auto/AUTO_POLICY.md`, `MT/auto/PLAN_TEMPLATE.md` (14 -> 19 lines), `H/scripts/master_queue.py` (1069 -> 1085), `H/scripts/package_rfp_bundles.py` (`main` only). New: `MT/tools/decide.py`, `MT/tools/registry_check.py`, `MT/tools/tests/test_e3_e6_tools.py` (7 tests). `board.py` and `issue.py` are unchanged (sha = bak).
Not run: no real start/resume/spawn/send/harness/stop/watch, no MQ add/run/cancel/resume/pause on the live root, no Docker, no osascript. Live files I only read: registry/tasks.json (sha16 `b5a6722066e33160` before and after registry_check), board.json, MQ state. The `decisions.jsonl` rows written at 02:09 and 02:16 during this session are the master's (`"who": "master"`), not mine.

Backups: `OUT/bak/` (auto.py `993d072a96a351af`, test_auto.py `ced6f91e4b183d41`, AUTO_POLICY.md, PLAN_TEMPLATE.md, board.py, issue.py, test_upgrade_tools.py, master_queue.py `8b727c46689edcf5`, package_rfp_bundles.py `32d42d0ce7cfd0eb`). MQ also in `H/.master-queue/backup-20261029T0203-e3/master_queue.py`.
Final sha256 (first 16): auto.py `e160ba9ab8224dd8`, test_auto.py `ceb86f3839fbfc89`, AUTO_POLICY.md `a92a78375dc73406`, PLAN_TEMPLATE.md `92eb6cea8e200892`, decide.py `3c51ef2f2487b14f`, registry_check.py `c03e4b5e533c74bb`, test_e3_e6_tools.py `4150d8ba30d01e55`, master_queue.py `8117911da2e7c2fb`, package_rfp_bundles.py `9c1018f8bf74b183`.

## Test counts
```
auto before:  Ran 61 tests in 7.784s  OK            (scratch/auto_before_full.txt)
auto after:   Ran 73 tests in 13.072s OK, exit 0    (scratch/auto_after.txt)
tools before: Ran 23 tests in 4.585s  OK            (scratch/tools_before.txt)
tools after:  Ran 30 tests in 4.956s  OK, exit 0    (scratch/tools_after.txt)
```
Harness's own package tests (no change expected): `H/.venv/bin/python -m pytest scripts/tests/test_package_rfp_bundles.py` -> `.......` 7 passed.

Negative: the new test_auto.py against the OUT/bak auto.py + bak AUTO_POLICY/PLAN_TEMPLATE (copy in /tmp/E3-neg, now deleted), scratch/auto_neg_bak.txt:
```
ERROR: test_board_rows_set_through_board_py
ERROR: test_stop_now_stops_watcher_caffeinate_pauses_queue_and_lists_still_running
ERROR: test_harness_wind_down_after_stop_needs_plan_line
ERROR: test_plan_template_fields_parse
FAIL: test_plan_step_at_start_minute_runs_today
FAIL: test_timed_lines_parse_with_next_occurrence
FAIL: test_final_waits_for_unread_result_and_running_harness
FAIL: test_overdue_final_lists_busy_and_leaves_worker_server_up
FAIL: test_paid_run_cap_six_per_day_or_plan_number
FAIL: test_policy_text_matches_code
FAIL: test_spawn_refused_in_last_20_min_unless_wind_down
Ran 73 tests  FAILED (failures=7, errors=4)
```
Two new tests pass on bak by design: `test_plain_stop_only_writes_the_stop_file` (plain stop must stay as it was) and `test_worker_permission_allows_harbor_oracle_and_nop` (a regression lock on rules that already exist). For the latter, the negative is a mutation: in a copy of the new auto.py, moving `"*harbor run*": "deny"` after the allow rules gives `Ran 1 test ... FAILED (failures=1)` (scratch/r526_mutation.txt). `test_timed_lines_parse_with_next_occurrence` is the one old test whose expected value changed (R5-17, below).

Negative for the tools tests: the new file runs with `E3_MQ`/`E3_PRB` pointing at the bak MQ/package and without decide.py/registry_check.py (scratch/tools_neg_bak.txt):
```
FAIL: test_decide_appends_one_valid_row
FAIL: test_mq_cancel_clears_pause_when_queue_empty
FAIL: test_mq_gate_runs_do_not_hold_a_slot
FAIL: test_package_errored_run_exits_3_without_traceback
FAIL: test_registry_check_clean_exit_0_and_unreadable_exit_2
FAIL: test_registry_check_reports_drift_exit_1_read_only
Ran 7 tests  FAILED (failures=6)
```
`test_decide_refuses_bad_by_and_empty_what` passes there only because a missing script also exits 2. Its real negative is the CLI check below (`--by Ayush` -> exit 2, nothing written).

## R5 row -> test
| Row | Test (file) |
|---|---|
| R5-09 | `test_final_waits_for_unread_result_and_running_harness` (test_auto) |
| R5-10 | `test_harness_wind_down_after_stop_needs_plan_line`, `test_paid_run_cap_six_per_day_or_plan_number`, `test_plan_template_fields_parse` |
| R5-11 | `test_stop_now_stops_watcher_caffeinate_pauses_queue_and_lists_still_running`, `test_plain_stop_only_writes_the_stop_file` |
| R5-12 | `test_mq_gate_runs_do_not_hold_a_slot` (test_e3_e6_tools) |
| R5-14 | `test_mq_cancel_clears_pause_when_queue_empty` (test_e3_e6_tools) |
| R5-15 | `test_board_rows_set_through_board_py` |
| R5-16 | `test_registry_check_reports_drift_exit_1_read_only`, `test_registry_check_clean_exit_0_and_unreadable_exit_2` (test_e3_e6_tools) |
| R5-17 | `test_plan_step_at_start_minute_runs_today` (+ the changed line in `test_timed_lines_parse_with_next_occurrence`) |
| R5-19 | `test_policy_text_matches_code` + the grep below |
| R5-20 | `test_overdue_final_lists_busy_and_leaves_worker_server_up` |
| R5-21 | `test_package_errored_run_exits_3_without_traceback` (test_e3_e6_tools) |
| R5-22 | `test_spawn_refused_in_last_20_min_unless_wind_down` |
| R5-23 | `test_decide_appends_one_valid_row`, `test_decide_refuses_bad_by_and_empty_what` (test_e3_e6_tools) |
| R5-25 | `test_final_waits_...` ("none" line), `test_overdue_final_...` and `test_stop_now_...` (items listed) |
| R5-26 | `test_worker_permission_allows_harbor_oracle_and_nop` |
| R5-18 | lesson only, no code (plan :252: KN lessons, which is the master's job) |
| R5-24 | done in A1 |

## E3 Stop and final report (R5-09, R5-11, R5-25; ANS Q20 a)
- R5-09 before: `wind_down` bak :1696-1705 `idle = not busy_workers(st)`. A worker whose result was not read yet (idle_polls < 2) counted as idle, and harness runs were ignored.
  After: `still_running()` :1839 lists busy and provider-retry workers, owned workers that were busy and are idle for < IDLE_POLLS polls ("finished, result not read yet"), adopted sessions busy in the DB, RUNNING harness runs and the queued runs of an unpaused queue. `wind_down` :1876 sends FINAL only when that list is empty, or at the 2 h cap. Both run after poll_workers/poll_harness in the same poll, so the last `done :`/`harness DONE` event comes before FINAL in the same delivery. The event text is now `ALL AUTO WORKERS IDLE AND HARNESS DONE` (same prefix as before).
- R5-25: `write_still_running()` :1865 fills `## Still running at stop` at FINAL and on `stop --now`: one line per item with the time, or `- none: no worker busy and no paid run active (FINAL HH:MM)`.
- R5-20 (the wind-down cap does not abort busy sessions mid-step): before, bak `shutdown_children` :1769 always killed the worker server, which aborted every busy session. After (:1955): if a worker is busy and the server is ours (`proc_is`), the server is left up, with a REPORT line `worker server pid N left running: <shas> still busy finish their current step (nothing aborted). Stop it after they finish: kill N` and log `worker_server_left`. Caffeinate is stopped as before. With no busy worker, the old path runs. At the cap, the TIMEOUT event lists what still runs.
- R5-11 `stop --now`: bak `cmd_stop` :1025 only wrote AUTO_STOP. Plain `stop` is unchanged (:1103). `--now` -> `stop_now()` :1113, all under the state lock: writes AUTO_STOP, `stopping`; SIGTERMs the watcher (`terminate(pid, "auto.py")`); pauses MQ with `auto.py stop --now at HH:MM: queue held until master_queue.py resume` (no LIMIT words; skipped if MQ is already paused, which keeps a LIMIT reason); fills "Still running at stop"; lists the undelivered events in REPORT.md; `shutdown_children` (caffeinate; worker server only if nobody is busy); sets `ended`, `final_sent`, `stopped_now`; logs `stopped_now`. Busy workers and RUNNING paid runs are not killed.
- Verify: tests above. `auto.py stop --help` (scratch/stop_help.txt):
```
usage: auto.py stop [-h] [--now]
  --now       stop now in one step: stop the watcher and caffeinate, pause the
              harness queue, list busy workers and RUNNING paid runs under
              'Still running at stop' in REPORT.md (they are not killed; the
              worker server stays up while a worker is busy)
exit=0
$ NEGATIVE: OUT/bak/auto.py stop --help
usage: auto.py stop [-h]
exit=0
```

## E4 Decisions file (R5-23)
- New `MT/tools/decide.py`: `--by` (required; `ayush | master | master (auto) | worker <7-hex>`, exact), `--what` (required, not blank), `--slug`, `--words` (verbatim), `--file` / `$DECIDE_FILE` / default `MT/decisions.jsonl`. Row keys in order `ist, by, slug?, what, words?`, `ist` = IST `YYYY-MM-DD HH:MM`. Appends one line (adds a newline first if the file does not end in one) and prints it. Bad `--by` / blank `--what` -> exit 2, nothing written. Old rows are never read or rewritten.
- Readers: no code reads decisions.jsonl (grep: only issue.py, which appends, and test_upgrade_tools.py, which reads issue.py's own rows). So there was nothing to make accept both shapes. issue.py already writes `by` (A1) and is unchanged.
- AP:54 -> AP:65 keeps `"by": "master (auto)"` and now names the decide.py command.
- Verify (scratch/decide_help.txt): `decide.py --help` exit 0 (usage above in scratch). Negative: `decide.py --by Ayush --what x --file /tmp/E3-neg/d.jsonl` -> `decide.py: --by 'Ayush': want ayush, master, 'master (auto)' or 'worker <7-hex sha>'`, `exit=2 file exists: no`.

## E5 Policy and plan template (R5-10, R5-19, R5-20, R5-22)
AUTO_POLICY.md (text only):
- AP:46 `hard caps 4 workers, 2 harness` -> `hard caps 5 workers (Ayush 27 Oct 22:20; auto.py:65), 2 harness`.
- AP:47 Docker cap -> reworded to advice, not enforced in code: `Docker advice ...: This is advice: auto.py does not count Docker-heavy workers (MAX_HARNESS caps paid runs, MAX_BUILDS caps new builds per run, nothing else).`
- AP:48 adds "The harness queue does not count these oracle/nop runs as paid-run slots" (E6). New AP:49 `Last spawn:` rule.
- New `## Budget` (AP:51-59): 6 paid runs/day unless PLAN.md `Paid runs:` says otherwise; no LIMIT and <= 2 busy at launch; <= 3 busy while a paid run runs; the master counts as a worker; fresh window -> paid run first; on LIMIT: hold, pause, resume at reset + 5 min, REPORT line + notification; metered may run beside one other Docker-heavy job (Docker 16 GiB, B-N2 done 29 Oct); wind-down and FINAL rule; `stop --now`.
- AP:15 harness row and AP:66 rule 5 name `harness --wind-down`. AP:70 REPORT section note: auto.py fills "Still running at stop".
PLAN_TEMPLATE.md :4-8 gains `Paid runs:`, `Workers/harness/Docker:`, `Budget:`, `Wind-down:`, `Last spawn:`.
Code (auto.py):
- `plan_fields()` :484 parses those 5 fields (first line wins). Used: `Paid runs:` (first integer = daily cap, `paid_run_cap` :498), `Wind-down:` (whole-word names, `wind_down_names` :503), `Last spawn:` (`HH:MM` or `N min`, default Until - 20 min, `last_spawn_at` :509). `Budget:` and `Workers/harness/Docker:` are text for the master. The limits stay the `start --workers/--harness` flags, so these two are not parsed into limits.
- `harness --wind-down` (R5-10): before, bak cmd_harness :1102 refused every run while stopping. After (:1223): stopping + no flag -> `auto mode is stopping; nothing new starts (... may use harness --wind-down)`; flag + PLAN.md `Wind-down:` not naming the bundle -> refused; named -> goes through every check that was already there (LIMIT, busy budget, harness limit, paused, pre-checks). `harness_add` logs `wind_down`.
- Paid-run cap in code (Budget): `paid_runs_today()` :523 = MQ runs started today (IST) + queued items. `harness` refuses at the cap (6, or the PLAN.md number) with `paid-run cap: N paid runs today or queued (...)`. This applies to every `harness`, not only wind-down. `auto.py status` prints `paid runs today N/6  last spawn HH:MM`.
- Last-spawn cutoff (R5-22): cmd_spawn :1146-1165. From Until - 20 min (or the plan's time), a spawn is refused with `last spawn was HH:MM (AUTO STOP HH:MM); ... (spawn --wind-down)`. With `--wind-down` it is allowed only when the Wind-down: line names the sha or the prompt's slug folder (`prompts/issued/<slug>/`). After AUTO STOP every spawn is still refused.
- R5-20: see E3 (worker server kept for busy sessions). The harness resume key by task was done in E1.
- Verify (scratch/grep.txt):
```
$ grep -n "Budget\|Wind-down\|Last spawn" MT/auto/AUTO_POLICY.md MT/auto/PLAN_TEMPLATE.md
master_chat_tasks/auto/AUTO_POLICY.md:15:| Give Ayush a bundle path for the harness | ... `harness --wind-down <bundle>` for a task named on PLAN.md's `Wind-down:` line (caps still apply) |
master_chat_tasks/auto/AUTO_POLICY.md:49:- Last spawn: no new spawn in the last 20 min before Until ...
master_chat_tasks/auto/AUTO_POLICY.md:51:## Budget
master_chat_tasks/auto/AUTO_POLICY.md:58:- Wind-down: after `AUTO STOP`, a paid run only via `harness --wind-down` ...
master_chat_tasks/auto/AUTO_POLICY.md:66:5. After `AUTO STOP`: start nothing new (only `harness --wind-down` per the Budget section). ...
master_chat_tasks/auto/PLAN_TEMPLATE.md:6:Budget: paid run only with no LIMIT and <= 2 busy workers; <= 3 busy while it runs; fresh window -> paid run first
master_chat_tasks/auto/PLAN_TEMPLATE.md:7:Wind-down: none (tasks, shas or slugs allowed after AUTO STOP via `harness --wind-down` / ...)
master_chat_tasks/auto/PLAN_TEMPLATE.md:8:Last spawn: 20 min before Until (or HH:MM)
exit=0
$ NEGATIVE: same grep on OUT/bak
exit=1
```

## E6 LOW cleanups
- R5-12 (MQ): bak :223-239 counted every `bin/harbor run`. After: `GATE_AGENT_RE` :80 (`--agent oracle|nop`, `--agent=`, `-a`), `is_gate_run` :224, `harbor_pgids(..., include_gate)` :229, `external_harbor_pgids(st, include_gate)` :240. `maybe_launch` :616 counts slots with `include_gate=False`. The Docker budget (:623) still counts gate runs, because they use Docker. `tick`'s refinalize guard (:690) and `kill_run` still see every harbor process, since a gate run can write into `jobs/`.
- R5-14 (MQ): `cmd_cancel` :942-964: when the cancel leaves the queue empty and nothing RUNNING, `paused/pause_reason/pause_task` are cleared and it prints `queue empty and nothing running: pause cleared (was: ...)`. With items still queued the pause stays.
- R5-15: new `board_set()` auto.py :688 runs `python3 <board dir>/tools/board.py set SHA status=...` (subprocess, like issue.py); rows that are not on the board are skipped; a failure goes to the log as `board_set_failed` and never raises. spawn and send -> `running`, `done :` result -> `done`, non-retry ERROR -> `error` (the R5-15 fix wording; "error" is a new status value on the board). Limit/network pauses and doom leave the row as it is. `stop --now` does not set `aborted`, because nothing is aborted. Tests patch `auto.BOARD` to a temp path in `RunCase` (`no_board`), so no test can reach the live board.
- R5-16: new `MT/tools/registry_check.py` (read-only; `--file` / `$REGISTRY_FILE`). It flags a path (list items as `[]`) that holds more than one kind (number/string/bool/list/object; null ignored) across tasks. Exit 1 on drift, 0 clean, 2 unreadable. Live run (scratch/registry_check.txt):
```
$ python3 MT/tools/registry_check.py
/Users/mac/Desktop/Terminal Bench/master_chat_tasks/registry/tasks.json: 30 tasks, 2 field(s) with type drift
  build.oracle: number x1, string x1
    number: vendor-archive-roundtrip-recovery = 1.0
    string: schema-migration-plan-repair = "1.0 x3"
  pipeline.traj_final: number x1, string x1
    number: sentinel-policy-recompute = 65.59
    string: caldermoor-commitment-closure = "51.45"
exit=1
tasks.json sha16 before b5a6722066e33160 after b5a6722066e33160
```
  This matches R5-16's evidence. The registry is not fixed here (I may not write MT/registry).
- R5-17: bak parse_plan :461-473 took `next_occurrence(hhmm, start)` (strictly after) -> a line at the start minute moved to tomorrow. After :467: base = the start minute - 1 min (seconds dropped) -> the start minute is today, earlier minutes are tomorrow. The old test `TestPlan.test_timed_lines_parse_with_next_occurrence` (test_auto.py:207) asserted the bug (`"at 22:00: same minute"` with start 22:00 -> 27 Oct). Its expected value is now 26 Oct with an `R5-17` comment. This is the only old assertion changed. The fix makes that line run today, as the brief asks, so the old expectation could not stay.
- R5-21: package_rfp_bundles.py `main` :292-305: a `FileNotFoundError` from `package()` (missing delivery evidence = errored run) prints `  <task>: not packaged: <msg>` plus a summary line and exits 3, with no traceback. `package()` already checks before writing, so nothing is half-written. The wrapper (`run-with-subscription.sh:905-907`, `_kiro_run_and_finalize.sh:217-218`) already turns a non-zero exit into a warning. Changing `wrapper_exit` itself is in those scripts, which I may not edit.
- R5-26: `test_worker_permission_allows_harbor_oracle_and_nop` replays opencode's "last matching rule wins" with `fnmatch` over `WORKER_PERMISSION["bash"]`: oracle/nop (also after `cd ... &&`, `oracle-2`) -> allow; claude-code agent, plain `harbor run`, auto.py, master_queue.py, git push -> deny; the allow keys come after `*harbor run*`.

## Other verify commands
`python3 MT/auto/auto.py status` exit 0 (scratch/status.txt); it ends:
```
harness: running -  queued 0  paused True
limits now: 5 workers, 2 harness
budget: paid run starts with <= 2 busy; <= 3 busy while one RUNS  no LIMIT
paid runs today 0/6  last spawn 17:40
undelivered events: 1
exit=0
```
`python3 H/scripts/master_queue.py status` exit 0 (scratch/mq_status.txt): `runner: stopped   max concurrent: 2`, `PAUSED: subscription usage limit reached during cold-chain-backbone-quote ...`, 5 run rows (live state unchanged; status is read-only).
`py_compile` of all 5 changed or new .py files: ok. lsp_diagnostics could not run: basedpyright is not installed (declined earlier).

## Choices
- `stop --now` does what the brief lists (watcher, caffeinate, queue pause) plus the REPORT section. It does not abort busy workers or kill RUNNING paid runs, so they appear under "Still running at stop". The worker server is stopped only when no worker is busy (shared with the R5-20 rule). It sets `final_sent`, so a later `resume` says "finished normally; use start".
- FINAL waits for the queued runs of an unpaused queue (they will start). A paused queue's items do not hold FINAL. A worker with only a scheduled limit retry (idle, error read) does not hold it either. A worker sent to in the last poll but not yet seen busy is not counted (after AUTO STOP the master sends nothing new).
- The daily paid-run cap is enforced in `auto.py harness` for every run (6, or the PLAN.md number), counted from the MQ state (runs started today + queued), so runs added outside auto.py count too.
- The Docker cap is advice; nothing was added to enforce it.
- The board gets `error` on a non-retry ERROR, as R5-15's fix says.

## Needs master
- The registry drift above (schema `build.oracle`, caldermoor `pipeline.traj_final`) is for the master to fix by hand (`status.py`/registry writer). Then `registry_check.py` should exit 0.
- New PLAN.md files should carry the 5 new fields (template updated). A plan without `Wind-down:` means no wind-down runs after AUTO STOP.
- If a wind-down cap ever leaves a worker server up, the REPORT line names the pid to kill after the workers finish.
- R5-18 lesson (zsh) for the KN lessons file: not done (MT/knowledge is out of scope here).
- The worker server keeps the old WORKER_PERMISSION until auto.py restarts (no change there).

## Rollback
```
cp OUT/bak/auto.py MT/auto/auto.py
cp OUT/bak/test_auto.py MT/auto/tests/test_auto.py
cp OUT/bak/AUTO_POLICY.md MT/auto/AUTO_POLICY.md
cp OUT/bak/PLAN_TEMPLATE.md MT/auto/PLAN_TEMPLATE.md
cp OUT/bak/master_queue.py H/scripts/master_queue.py      # or H/.master-queue/backup-20261029T0203-e3/master_queue.py
cp OUT/bak/package_rfp_bundles.py H/scripts/package_rfp_bundles.py
rm MT/tools/decide.py MT/tools/registry_check.py MT/tools/tests/test_e3_e6_tools.py
```
