# auto.py test report (2026-10-26)

## Unit tests: `python3 -B -W error::ResourceWarning -m unittest discover -s tests` -> 36 tests, OK (0.4 s)

Temp dirs + temp sqlite db with the opencode schema; no network, no opencode.

| Test group | Observed |
|---|---|
| db_state: recent user msg -> busy; old user msg -> interrupted; assistant error -> error; not completed fresh/stale -> busy/interrupted; finish tool-calls fresh/stale -> busy/interrupted; finish stop/length/null+completed -> done (text parts only, joined); last message by time_created wins; missing session/db -> unknown; connection is read-only (insert raises) | pass |
| adopt lookup: newest root session by title, ignores child sessions; adopt_one sets adopted=True owned=False, board prompt copied, reported_msg None, build False; unknown title / unknown session id -> not adopted | pass |
| classify on the 6 real error strings: extra-usage -> limit, Cannot connect -> network, MessageAbortedError -> aborted, Internal error / OAuth revoked / Claude Code version -> other; plus 429 and timed out | pass |
| parse_reset: "resets at 3:30pm" (today), "resets 9:05am" (tomorrow), 24h, 12am; "try again in N minutes/hours"; default +30 min; "resets 5 times" ignored | pass |
| parse_plan: `- At 03:00:`, `* at 7:30 -`, en dash, bare `at`, invalid 25:99 skipped, mid-line "at" ignored, next-occurrence rule | pass |
| REPORT: template section order; watcher lines inserted under "Interrupted or unfinished" before next `## `, in order, after hand-written lines; missing header -> appended at end | pass |
| resume refusal: no state, watcher alive, ended+FINAL -> "last run finished normally; use start", dead watcher and ended-without-FINAL allowed | pass |
| retries: PAUSED once per pause, GAVE UP once after 4 retries, aborted/other -> ERROR without retry, done clears pause, adopted done tagged, retry time from "try again in 90 minutes" | pass |
| passive (adopted) polling: INTERRUPTED once, done once; busy_workers counts passive busy sessions | pass |
| gap detection (event + REPORT line, once); network down >5 min note once, NETWORK BACK event | pass |
| harness auto-resume with fake `.venv/bin/python`: waits for reset, max 3 resumes, one GAVE UP event, startup-failure pause never resumed | pass |
| watcher message prefix/footer, worker permission (`*auto.py*`, `*night.py*`, `*master_queue.py*` deny), require_not_worker, master limit error holds delivery then sends `continue`, clears when answered | pass |

## Live tests (real opencode, isolated temp AUTO_* dirs, temp secret, throwaway servers; AUTO_POLL_S=10)

| # | Test | Observed |
|---|---|---|
| 1 | `start --until now+15 --plan (one "at" line +2 min) --workers 2` with fake board row `fakerow1` (running) and throwaway master session `auto-master-test` | worker server up (pid 73703), watcher 73704 and `caffeinate -i -s -w 73704` (pid 73705) alive; adoption reported `not found: ['fakerow1']`; throwaway master received `[AUTO WATCHER] 22:08 IST (auto mode until 22:22; Ayush is away)` + "AUTO MODE START" + full PLAN + adopted list + footer (read via its API, model/variant copied from its last user message); at 22:09 it received `PLAN AT 22:09: PLAN LINE CHECK reply only OK.`; both answered OK |
| 2 | adopt across processes: session `t-adopt` made and finished on throwaway server A, A killed, `adopt t-adopt`, then `send t-adopt "Reply only OK2."` | `done : t-adopt (adopted session ses_e86eba...)` delivered exactly once (from DB, `adopted=True owned=False`); send accepted (db_state done), session became owned; DB shows new user message "Reply only OK2." and new assistant reply "OK2." (finish=stop) on the same session id. Continuing a session created by another process works. |
| 3 | spawn `res1` (counting task), SIGKILL watcher + worker server + caffeinate (only ones started by the test), `resume` | new worker server (new url/pid), `res1` was busy-at-kill -> `continue` sent, t-adopt left (finished), REPORT "Interrupted or unfinished" got the gap line `gap 22:10-22:11` and per-action lines, `AUTO RESUMED after gap 22:10-22:11: ...` delivered to the master; `res1` then reported `done : res1` with the full count + DONE; watcher + caffeinate restarted |
| 4 | `stop` | AUTO STOP, "ALL AUTO WORKERS IDLE", FINAL delivered in one message; watcher exited ~20 s later, state `ended` set, worker server and caffeinate gone (`ps` clean) |
| 5 | `resume` after the normal end | prints "last run finished normally; use start", exit 0 |

Cleanup: throwaway master/A servers killed, the 3 test sessions deleted through the opencode API (DELETE /session, not via sqlite), temp dirs removed, no `__pycache__`, no stray processes. opencode.db was only ever opened read-only by auto.py.

## Not exercised live
Real limit/network pauses on a worker (covered by unit tests only), harness auto-resume against a real queue, ramp, gap detection by real sleep (resume writes the gap line; the watcher gap path is unit-tested), net-down handling (unit-tested with `net_up` mocked).
