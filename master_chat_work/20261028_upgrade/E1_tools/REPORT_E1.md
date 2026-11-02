# REPORT E1 (board 7fdff25): limit detection and budget

Status: DONE. Files changed: `MT/auto/auto.py` (1529 -> 1707 lines), `MT/auto/tests/test_auto.py` (555 -> 855, 11 new tests, none of the old ones changed in substance), `H/scripts/master_queue.py` (1029 -> 1069). Nothing else written outside OUT. No real start/resume/spawn/send/harness/stop/watch, no Docker, no MQ runner.

Final sha256 (first 16): auto.py `210cb23856025a22`, test_auto.py `a8cebd694e27baaa`, master_queue.py `8b727c46689edcf5`.

## Test counts
- auto tests before: `Ran 46 tests ... OK` (scratch/e1_auto_before.txt)
- auto tests after: `Ran 57 tests in 5.859s OK`, exit 0 (scratch/e1_auto_after.txt)
- tools tests: `Ran 23 tests in 4.410s OK`, exit 0 (scratch/e1_tools_tests.txt)
- Negative: the same new test file against `OUT/bak/auto.py` (copy in /tmp/E1b-neg; only change: `create=True` on the `notify` patch, since the old file has no `notify`): `Ran 57 tests  FAILED (failures=6, errors=5)` = exactly the 11 new tests fail, the 46 old ones pass (scratch/e1_auto_neg_bak.txt).

New tests (test_auto.py :559-855): `FakeOpencode` = real HTTP server in a thread (`/global/health`, `/session/status`, `/session`, prompt_async); `auto.SECRET`, `auto.HARNESS` (fake harness whose `.venv/bin/python` only records its args) patched; `auto.notify` patched in `RunCase.setUp` (no osascript in any test).
- `test_retry_is_not_busy`
- `test_retry_gives_limit_within_two_polls_then_cleared_after_two_clean_polls` (also: 1 notification, 1 REPORT line, MQ `pause` called once, a dirty poll resets the clean count, MQ `resume` on clear)
- `test_mq_usage_limit_pause_is_limit_and_mq_not_paused_again` (reset 4698 s parsed from the MQ reason)
- `test_401_is_auth_not_limit` (worker retry 401 and MQ AUTH pause; no LIMIT, no auto-resume)
- `test_exhausted_line_during_paid_run_is_logged_not_killed`
- `test_hold_file_written_for_limit_and_busy`
- `test_spawn_and_harness_refused_during_limit` (incl. `auto.main()` exit 2 with the message)
- `test_harness_refused_with_three_busy_workers` (+ 2 busy + 1 retry passes the budget)
- `test_fourth_spawn_held_while_paid_run_running` (+ same spawn succeeds when the run is DONE)
- `test_reset_in_seconds`
- `test_resume_keyed_by_task_with_five_minute_pad`

## Point 1: retry is not busy
- before `auto.py:299-301` `busy_ids` = every type != idle.
- after `auto.py:307-322`: `session_status(url)`; `busy_ids(url, status=None, include_retry=False)` drops `idle` and `retry`; new `retry_ids(url, status=None)` returns `{sid: status}` for `type == "retry"`.
- Callers that must not prompt a session keep the old meaning via `include_retry=True`: cmd_resume :968, cmd_send :1057, process_retries :1369, deliver (master) :1522. So the master/deliver behaviour is unchanged (E2 scope).
- poll_workers :1206-1217: one status call; an owned worker in retry gets `idle_polls = 0` and goes to `note_retry` (never read as a finished step). `auto.py status` shows `RETRY` (:1159).
- Verify: `test_retry_is_not_busy` OK; fails on bak (FAIL).

## Point 2: LIMIT state
- `note_retry` :1254: worker retry message matching LIMIT_RE -> `st["limit_workers"][sha]` (message + `next`).
- `check_limit` :1293, called from watch_once after poll_harness (:1583). Hit = owned worker in limit retry, or MQ paused with a usage-limit reason (`is_limit_pause` :1287: LIMIT_RE, not AUTH, not startup, not our own pause). First hit: `limit_since`, `limit_reset` (earliest of reset text in the messages and retry `next` ms) in state.json; event `LIMIT: <who> hit a usage/rate limit (<msg>); reset HH:MM. Holding spawns and the harness queue.`; one REPORT line; `log("limit_seen")`; `notify()`; MQ `pause "auto.py LIMIT since HH:MM: no new paid run starts until it clears"` only when MQ is not already paused. The pause reason has no LIMIT_RE words, so it never re-triggers LIMIT or auto-resume.
- `LIMIT CLEARED` after `LIMIT_CLEAR_POLLS = 2` clean polls in a row (a dirty poll resets the count); clears `limit_since/limit_reset/limit_clean/mq_paused_by_limit`; runs MQ `resume` only when the pause reason is our own `auto.py LIMIT` one.
- `notify(text)` :1269: `osascript -e 'display notification "..." with title "auto"'`, `\` and `"` escaped, 10 s timeout, failure logged. Tests replace it.
- Verify: tests 2 and 3 above OK; on bak they ERROR (`no attribute poll_workers->note_retry/check_limit`).

## Point 3: refusals while LIMIT
- `refuse_if_limit(st, what)` :1337 raises `LIMIT since HH:MM; parsed reset HH:MM: no spawn|harness until LIMIT CLEARED`; called in cmd_spawn :1016 and cmd_harness :1080 (before any docker/pypi check). `main()` turns it into exit 2.
- Verify: `test_spawn_and_harness_refused_during_limit` OK; on bak FAIL (spawn went through to the fake server).

## Point 4: reset parsing, +5 min, resume keyed by task
- before `auto.py:87` `RESET_IN_RE = r"try again in\s+(\d+)\s*(minute|min|hour|hr)s?"`.
- after `auto.py:93` `r"(?:try again|reset) in\s+(\d+)\s*(seconds?|secs?|s|minutes?|mins?|hours?|hrs?|h|m)\b"`; new `reset_in_text()` :488 (seconds/minutes/hours, clock time, else None); `parse_reset` :509 is unchanged in contract (raw reset, else base + default). Worker retries keep the raw reset (the existing test wants now+90 min).
- Harness resume = parsed reset + `RESUME_PAD_MIN = 5` (:81, :1433). `harness_auto_resume` :1416 key = MQ `pause_task`, else `during <task>` from the reason, else the reason (the old test still passes). 3 tries per task, whatever the reason text.
- MQ: usage-limit pause (:644-656) sets `pause_task` and appends `; soonest reset in Ns` from the run log (`RESET_SECS_RE` :77). `pause`/`resume` clear `pause_task`.
- Plan reset check (scratch/e1_exp1.txt):
```
$ mkdir -p /tmp/R5-auto-1 && cp MT/auto/auto.py /tmp/R5-auto-1/auto_copy.py && python3 U/R5_auto_issues/exp1.py
reason -> 2026-10-28 18:54:49+05:30
litellm -> 2026-10-28 19:13:07+05:30
...
$ NEGATIVE: same with OUT/bak/auto.py
reason -> 2026-10-28 18:54:49+05:30
litellm -> 2026-10-28 18:54:49+05:30
```
  `soonest reset in 4698s` at 17:54:49 -> 19:13:07 (>= 19:13:07, pass); bak gives the 60 min default 18:54:49 (fail). The `reason` line is the old MQ text with no reset in it; new MQ reasons carry `; soonest reset in Ns`. The resume then happens at 19:18:07 (+5 min).
- MQ check on a copy (/tmp/E1b-mq, `tick()` with a dead fake run, `read_result` mocked):
```
NEW limit-task: paused=True pause_task='limit-task' queue=['limit-task']
  reason: subscription usage limit reached during limit-task (requeued at the front). Resume once the limit resets.; soonest reset in 4698s
OLD limit-task: paused=True pause_task=None ... Resume once the limit resets.
```
- Verify: `test_reset_in_seconds`, `test_resume_keyed_by_task_with_five_minute_pad` OK; both FAIL on bak.

## Point 5: AUTH is not LIMIT
- MQ before :75 `USAGE_LIMIT_RE` matched `EXHAUSTED http \d+`, so a 401 preflight looked like a limit. After: `AUTH_RE` :76 (`(EXHAUSTED|BADKEY) http 40[13]` or `wrapper_exit=8`) checked first (:632): requeue at front, paused, `pause_task`, `pause_reason = "AUTH: login rejected during <task> (requeued at the front). Run scripts/anubis-auth setup, then master_queue.py resume."` (no LIMIT_RE words).
- auto: `AUTH_RE` :94; worker retry 401 -> `AUTH <sha>: ...` event once per message, no LIMIT (:1254); MQ AUTH pause -> `AUTH: harness paused on a login fault ...` event (:1408), `is_limit_pause` is False, so no LIMIT and no auto-resume.
- MQ copy check:
```
NEW auth-task:   reason: AUTH: login rejected during auth-task ...      (log: EXHAUSTED http 401, wrapper_exit=4)
NEW badkey-task: reason: AUTH: login rejected during badkey-task ...    (log: BADKEY http 401, wrapper_exit=8)
OLD auth-task:   reason: subscription usage limit reached during auth-task ...   <- the bug
OLD badkey-task: paused=False
```
- Verify: `test_401_is_auth_not_limit` OK; ERROR on bak.

## Point 6: budget in code (ANS Q16 a)
- Constants :82-83 `MAX_BUSY_AT_LAUNCH = 2`, `MAX_BUSY_WITH_RUN = 3`; MAX_BUSY_WORKERS stays 5.
- cmd_harness :1083-1087: refuses with `N workers busy; a paid run starts only with <= 2 busy (ANS Q16 a)` when > 2 busy (retry sessions are not busy).
- cmd_spawn :1024-1030: while any MQ run is RUNNING (`paid_running` :1343) and >= 3 busy: `held: 3 workers busy while paid run <task> is RUNNING (limit 3 during a paid run); ...`; otherwise the old limit (5).
- Launch happens in MQ (`maybe_launch`), so: the watcher writes `H/.master-queue/auto_hold.json` each poll (`write_hold` :1347, only if that dir exists) = `{hold, reason, busy, written, expires = now + 3 polls}`; hold when LIMIT or > 2 busy. MQ `auto_hold()` :594 and `maybe_launch` :606 start nothing while an unexpired hold is true; a dead watcher's hold expires by itself. MQ `status` prints `AUTO HOLD (...)` (:902). New MQ subcommand `pause [REASON]` (:999, :1030).
- MQ copy check: `maybe_launch with hold: []`, `with expired: ['docker is not reachable; not launching']`, `with no hold: [...]` (the docker message proves it got past the hold); OLD: `with hold: ['docker is not reachable; ...']` (hold ignored).
- Verify: `test_harness_refused_with_three_busy_workers`, `test_fourth_spawn_held_while_paid_run_running`, `test_hold_file_written_for_limit_and_busy` OK; FAIL/ERROR on bak.

## Point 7: accounts exhausted during a paid run: log only (ANS Q18 a)
- poll_harness :1390-1404: for RUNNING runs, `EXHAUSTED_LINE_RE` (:95) on the run log; once per task#attempt: event + REPORT line `harness LOG: <task> attempt N still RUNNING: <line> (not killed)` and `log("harness_exhausted_line")`. No kill, no LIMIT, no MQ call.
- Verify: `test_exhausted_line_during_paid_run_is_logged_not_killed` OK; ERROR on bak.

## Other verify commands
`python3 MT/auto/auto.py status` (scratch/e1_status.txt), exit 0; ends with:
```
harness: running -  queued 0  paused True
limits now: 5 workers, 2 harness
budget: paid run starts with <= 2 busy; <= 3 busy while one RUNS  no LIMIT
undelivered events: 1
```
Negative: `OUT/bak/auto.py status` prints `auto mode never started` (its AUTO_DIR is next to its own file) and has no budget line.

MQ (scratch/e1_mq_check.txt): `ast.parse` exit 0; `master_queue.py --help` exit 0, choices now include `pause`. Negative: ast.parse on a copy with the `:` removed from `def maybe_launch` -> `SyntaxError: expected ':'`. Old MQ `pause` -> `invalid choice: 'pause'`, exit 2. New MQ `pause`/`status` on a temp `--root` -> `queue paused: auto.py LIMIT since 01:40 ...`, then `AUTO HOLD (no launch from the queue): LIMIT since 01:40`.

## Choices
- Retry sessions are left out of `busy_ids` only. Places that send prompts use `include_retry=True`, so a retrying session (master included) still gets no prompt (deliver is E2's).
- A MQ usage-limit pause counts as LIMIT until the harness is resumed (by harness_auto_resume at reset + 5 min, or by hand). So spawns are refused while MQ sits in a limit pause.
- Our own MQ pause reason starts `auto.py LIMIT` and has no LIMIT_RE words. That keeps it from being read as a fresh limit or being auto-resumed, and it is the only pause that LIMIT CLEARED resumes.
- The MQ launch gate is a hold file with an expiry. MQ does not depend on auto.py, and a dead watcher cannot block the queue for more than 3 polls.
- The +5 min pad applies only to harness resume. Worker retries stay at the raw reset (an existing test pins now+90 min).
- AUTH is matched only on 401/403 or exit 8. A 429 is still a limit.

## Needs master
- The live MQ is paused now with `subscription usage limit reached during cold-chain-backbone-quote ...` (no pause_task, no reset text). On the next watcher start, the new code raises LIMIT at once (spawns and `auto.py harness` refused) and auto-resumes MQ at the 60 + 5 min default. If the limit is already over, run `master_queue.py resume` before starting auto.
- G2 smoketest (plan :294) is a real run. It is for the master, not done here.

## Rollback
```
cp OUT/bak/auto.py MT/auto/auto.py
cp OUT/bak/test_auto.py MT/auto/tests/test_auto.py
cp OUT/bak/master_queue.py H/scripts/master_queue.py   # or H/.master-queue/backup-20261029T0124-e1/master_queue.py
rm -f H/.master-queue/auto_hold.json                    # only exists after a new-code watcher ran
```
