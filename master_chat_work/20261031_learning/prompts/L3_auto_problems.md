# L3: Auto-mode and worker problems: why workers "go to sleep", Docker polling, other stalls
OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261031_learning/L3_auto_problems/`

Ayush: "check all auto mode sessions and verify the problems we faced; often a worker goes to sleep, so we have to fix this; Docker keeps polling."
1. Sources: every `master_chat_tasks/auto/runs/*/{REPORT.md,events.jsonl,state.json}`, `board.json`, decisions.jsonl, and worker sessions in the opencode DB (read-only; worker sessions are titled with a board sha; tables session, message, part). S6 `INCIDENTS.csv` has 20 incidents: extend, don't repeat.
2. "Went to sleep": find every worker session that went idle (last message an assistant turn ending, no further tool call) while its own background job (nohup harbor/docker/script) was still running or before its deliverable existed; also sessions stuck in retry, doom-loop guard stops, compaction stops, token-cap stops. For each: time, sha, how long it sat, what woke it (watcher, Ayush, master send). Table `SLEEP_CASES.csv`. Group by root cause and quote the transcript lines that show it.
3. Polling: count sleep/poll tool calls per session and the time spent in them; which waited for a Docker slot vs its own job; which repeated identical calls. What a single blocking wait (e.g. waiting on `docker events` or a log line with a long tool timeout) would have saved.
4. Watcher gaps: what auto.py's watcher detects today (`auto.py` watch_once, check_limit, note_master_hold, STALL_MIN, DOOM_CONTINUE) vs the cases in 2; which cases it missed and the exact rule that would catch each.
5. Fixes: ranked list (time saved x safety): prompt rule text, auto.py watcher rule, worker template change. For each: where (file:line), test to prove it, what it could break.
Extra: SLEEP_CASES.csv, POLL_STATS.csv.
