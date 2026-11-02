# REPORT E2 (board 593d59d): watcher reliability

Status: DONE. Files changed: `MT/auto/auto.py` (1707 -> 1864 lines), `MT/auto/tests/test_auto.py` (855 -> 998; 4 new tests, `FakeOpencode` gains `messages` and `bodies`, no old test changed). MQ not touched (none of the 4 points needs it). Nothing written outside OUT except those two files. No real start/resume/spawn/send/harness/stop/watch, no Docker, no osascript in tests.

Backups: `OUT/bak/auto.py` (sha 16 `210cb23856025a22`, = E1 final), `OUT/bak/test_auto.py` (`a8cebd694e27baaa`).
Final sha256 (first 16): auto.py `4faf0709535b4833`, test_auto.py `13b14a19c5c68170`.

E1 kept as is: `notify()`, `retry_ids()`, `report_line`, `LIMIT_RE`/`AUTH_RE`, every `include_retry=True` (deliver still uses it at :1665).

## Test counts
- before: `Ran 57 tests in 6.063s  OK` (scratch/auto_before.txt)
- after: `Ran 61 tests in 7.840s  OK`, exit 0 (scratch/auto_after.txt)
- negative: the new test file against `OUT/bak/auto.py` (copy in /tmp/E2-neg): `Ran 61 tests  FAILED (failures=4)`. The 4 failures are exactly the new tests; the 57 old ones pass (scratch/auto_neg_bak.txt):
```
FAIL: test_doom_classified_one_auto_send_then_blocked
FAIL: test_health_two_strikes_then_answering_again
FAIL: test_master_retry_two_polls_reports_once_events_stay_then_delivered
FAIL: test_stall_one_event_per_stall_with_fixed_message_time
```
- tools: `Ran 23 tests in 4.443s  OK`, exit 0 (scratch/tools_tests.txt)

New tests are in `TestWatcherE2` (test_auto.py:864-998). They use E1's `FakeOpencode`/`LimitCase` with `notify` patched, and the clock is mocked through `auto.now`.

## Point 1: undelivered events (R5-04)
- before: `deliver` (old :1522-1524): a master in retry or busy -> `master_idle_polls = 0; return`, and nothing is written anywhere.
- after: deliver :1664-1668 calls the new `note_master_hold(st, murl, msid)` (:1624) while the master is busy or in retry. A free poll clears `master_hold`. The hold is only counted while events are queued. Kind = `retry` if `retry_ids(murl)` holds the master, else `busy`. After `MASTER_HOLD_POLLS = 2` (:72) polls of the same kind it writes, once per hold: `report_line("master chat in provider retry since HH:MM: <msg>; N watcher events not delivered (still queued)")` (or `master chat busy since HH:MM; ...`). The new `report_undelivered()` (:269) adds a `## Watcher events not delivered` section with the first line of each queued event. Then one `notify()` and `log("master_hold")`. Events are not touched, and delivery is the old path once the master is idle for IDLE_POLLS. A change of kind (busy -> retry) counts as a new hold. `insert_report_line` (:245) gains an optional `header` argument (default unchanged).
- verify: `test_master_retry_two_polls_reports_once_events_stay_then_delivered`: no line after 1 poll. After 4 polls: 1 REPORT line, 1 notify, both events in the new section, events still queued, no prompt. Master idle -> 2 polls -> exactly one prompt_async that carries both events, events emptied. A later busy hold -> its own single line and a 2nd notify. On bak: FAIL.

## Point 2: stall watchdog (R5-05)
- before: the only busy alert was `LONG_BUSY_H` (old :1229-1231).
- after: `STALL_MIN = 20` (:71) next to LONG_BUSY_H. `poll_workers` (:1258) collects owned workers that are busy or in provider retry (`active`, with a status text) and calls `check_stall` (:1296 -> :1349). `last_activity` (:1337) = the newest of the last message `info.time.*` (`/session/<id>/message?limit=1`), the OUT folder mtime (`tree_mtime` :1321: folder + up to 2000 files under it) and our last send. OUT comes from the prompt file's `OUT ... \`path\`` line (`worker_out` :1310, `OUT_RE` :103, cached in `w["out"]`). With no such line, only the message time (and the send) is used. Each worker gets `w["last_activity"]`. When the newest activity of all active workers is >= 20 min old: one `STALL: N workers no progress since HH:MM (status: <retry: msg> | busy) [shas]` event and `log("stall")`. `stall_reported` resets only when some activity is < 20 min old or no worker is active.
- verify: `test_stall_one_event_per_stall_with_fixed_message_time`: the message time is fixed at t0. +15 min -> none. OUT file touched at +20, poll at +25 -> none (OUT counts). +41 -> exactly one `STALL: 2 workers no progress since <t0+20> (status: busy)`. +42 and +60 -> none. A new message at +61 -> reset. +82 with w1 in retry -> one new STALL with `(status: retry: ...)`. On bak: FAIL.

## Point 3: doom class (R5-06, ANS Q19 a)
- before: `classify` (old :469-479) returned `other` for the guard message -> `ERROR` event, so it needed a master turn.
- after: `"doom_loop": "deny"` unchanged (:136). `DOOM_RE` (:100) = `prevents you from using this specific tool call|doom.?loop`, checked in `classify` (:490) before LIMIT/NETWORK. `handle_result` (:1218) routes `doom` to the new `handle_doom` (:1233). First doom on a worker: `prompt(worker_url, sid, DOOM_CONTINUE)` (:101, the exact text from the brief), `mark_sent`, `w["doom_sent"] = w["corrective_sent"] = ts`, and a `DOOM <sha>: ... sent the one corrective message automatically ... a second doom is BLOCKED` event so the master does not send a second corrective (AUTO_POLICY :32). Second doom: a `BLOCKED <sha>: doom_loop guard again after the automatic corrective continue ...; no second send` event. If the send fails (URLError/OSError): an `ERROR` event instead of a lost doom.
- verify: `test_doom_classified_one_auto_send_then_blocked`: classify -> `doom` for both wordings, the permission is still `deny`. An idle worker with the error, over 5 polls -> exactly one POST `/session/ses_w1/prompt_async` with DOOM_CONTINUE and 1 DOOM event. A second doom (new msg id) -> 1 BLOCKED and still 1 POST. exp1.py `classify doom:` -> `doom` (new) / `other` (bak), below. On bak: FAIL.

## Point 4: health check (R5-07 = R2 N6)
- before: `healthy()` timeout 5 (old :281). watch_once (old :1572-1579): one miss = `ERROR ... not answering`, `worker_down_reported` never cleared except in cmd_resume.
- after: `HEALTH_TIMEOUT_S = 15` (:73) used in `healthy` (:302). watch_once (:1715-1737): on success, if `worker_down_reported`, an event + REPORT line `worker server answering again (not answering since HH:MM); polling workers again`, then `worker_fail=0`, `worker_fail_since=None`, `worker_down_reported=False`. On a miss: `worker_fail += 1` and `worker_fail_since` is set. At `WORKER_DOWN_POLLS = 2` (:74), once: event + REPORT line `ERROR: auto worker server not answering (2 health checks in a row since HH:MM, 15 s timeout); workers are not polled`. Polls (poll_workers, process_retries) are skipped on every miss, as before. cmd_resume's restart path is kept and also resets `worker_fail`/`worker_fail_since` (:989-990).
- verify: `test_health_two_strikes_then_answering_again`: `healthy` passes timeout 15. With pattern F,T,T,F,F,T the new events per poll are `[0,0,0,0,1,1]`: `not answering` at the 2nd miss of the second outage, then `answering again`. poll_workers runs 3 times (T polls only), and the flag is cleared at the end. On bak: FAIL.
- exp1 replay (`/tmp/R5-auto-1/auto_copy.py`, scratch/exp1.txt):
```
--- exp1 on NEW
reason -> 2026-10-28 18:54:49+05:30
litellm -> 2026-10-28 19:13:07+05:30
LIMIT_RE matches reason: True
next_occurrence 01:07 after 01:07:01 -> 2026-10-28 01:07:00+05:30
classify doom: doom
classify rate: limit
replayed watch_once:1390-1397 with health F,T,T,F -> ['poll0: ERROR down'] (second outage at poll3 NOT reported)
--- exp1 on BAK
...
classify doom: other
...
replayed watch_once:1390-1397 with health F,T,T,F -> ['poll0: ERROR down'] (second outage at poll3 NOT reported)
```
  exp1's health part runs on, but it re-implements the old watch_once lines inline and only patches `a.healthy`, so it prints the same line for any auto.py. It cannot test the fix. So I added `scratch/health_replay.py` (copy run from /tmp/E2-replay), which drives the real `watch_once` of a given file with health F,T,T,F,F,T (net down, polls stubbed). Output (scratch/health_replay.txt):
```
--- health replay NEW
poll0 health=F new events: []
poll1 health=T new events: []
poll2 health=T new events: []
poll3 health=F new events: []
poll4 health=F new events: ['ERROR: auto worker server not answering (2 health checks in a row sinc']
poll5 health=T new events: ['worker server answering again (not answering since 01:53); polling wor']
worker_down_reported at end: False
--- health replay BAK
poll0 health=F new events: ['ERROR: auto worker server is not answering; workers are stopped']
poll1 health=T new events: []
...
poll4 health=F new events: []
poll5 health=T new events: []
worker_down_reported at end: True
```

## `auto.py status`
exit 0 (scratch/status.txt). It shows the 1553_evening run, 4 idle workers, `budget: ... no LIMIT`, `undelivered events: 1`. Negative: `OUT/bak/auto.py status` -> `auto mode never started` (its AUTO_DIR is beside its own file), so it reads no run.

## Choices
- Point 1 "busy" holds also report, as the brief asks. A master that works more than 2 polls while events are queued gets one REPORT line + one notification per hold. On a busy night that can be many lines and notices. If it is too noisy, raise `MASTER_HOLD_POLLS` or limit `note_master_hold` to `retry` (one-line change).
- Point 2 counts workers in provider retry as active (the brief's `status: <retry msg>` needs them). Passive (adopted, not owned) workers are left out, because their DB state turns `interrupted` after 10 min anyway. Our own last send counts as activity.
- Point 3 sends the corrective even after AUTO STOP (it continues the current step and is not new work). It applies wherever `handle_result` runs (poll, resume), through the worker server, like `cmd_send`.
- Point 4: the 15 s timeout applies to every `healthy()` call (master too), as the plan says. The REPORT also gets the down/again lines, so the night report shows outages.

## Needs master (before the G2 smoketest)
- None blocking. G2 (plan :294) is a real auto run: for the master.
- If an old run is ever `resume`d with its worker server still up and `worker_down_reported: true` in its state.json (the 1553_evening state has it, R5-07), the first poll prints one `worker server answering again` event. That is harmless and expected.
- Optional: R5-06 also proposed a worker-prompt line about polls ("`sleep 120; echo poll <n>` with a rising n"). That is in `MT/prompts/templates/*`, which E2 must not touch, so the line was not added. It is for the master.

## Rollback
```
cp OUT/bak/auto.py MT/auto/auto.py
cp OUT/bak/test_auto.py MT/auto/tests/test_auto.py
```
