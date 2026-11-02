# R5 Research: find and explain every issue in our auto runs

Board id: `366516b`
This prompt is saved at `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/_upgrade/20261028T1930_R5_auto_run_issues.md`. After any compaction, re-read it, then `OUT/TODO.md`.
OUT = `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261028_upgrade/R5_auto_issues/`

This is a research session, one of 5 parallel upgrade sessions (R1-R5). You read every auto-mode run we have had, find each issue that was detected (or should have been), trace it to its root cause in code or policy, and propose a fix with a test. You **edit no code**. A later plan session merges R1-R5; nothing is applied until Ayush says "proceed".

## Ayush's words (28 Oct 19:00-19:35 IST)
- "also session to handle and find the issues in auto run that are detected"
- Answer: cover **all auto runs so far**.

## Rules that survive compaction (copy this section word for word into any compaction summary)
- First thing and last thing: `python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/name_session.py" 366516b`.
- Tools work in every turn; get IST time with `TZ=Asia/Kolkata date`.
- READ ONLY everywhere except OUT and `/tmp/R5-auto-*/`. No code edits, no git writes. Do NOT run `auto.py start/resume/spawn/send/harness/stop`, `master_queue.py` write commands, or anything that starts the opencode worker server, a watcher, Docker or a harness run. `auto.py status` and `--help` are fine. You may copy a script to `/tmp/R5-auto-*/` and run a unit-level experiment there against fake paths (auto.py supports `AUTO_DIR`, `AUTO_REGISTRY`, `AUTO_BOARD`, `AUTO_DB` etc. for tests), never against the real folders.
- Read the opencode DB only read-only, if at all.
- Keep `OUT/TODO.md` and `OUT/LOG.md` current. Read at most 50 KB per read (events.jsonl: parse with python).
- Every issue cites evidence (run folder + events.jsonl line or REPORT.md line, decisions.jsonl line, log file:line) and a code location (file:line). INFERRED / UNVERIFIED labels.

## Inputs
- Run folders (all 7): `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/auto/runs/` = `20261025_0048_night`, `20261027T0107_smoketest`, `20261027T0200_night`, `20261027T2031_evening`, `20261027T2239_overnight`, `20261028T1220_day`, `20261028T1553_evening`; each has PLAN.md, REPORT.md, events.jsonl, state.json, logs/. Older night mode, if any traces remain: grep `master_chat_tasks/` for "night mode".
- Code and policy: `master_chat_tasks/auto/auto.py`, `auto/AUTO_POLICY.md`, `auto/PLAN_TEMPLATE.md`, `auto/plans/`, `master_chat_tasks/tools/issue.py` (the session time-box refusal that needed overrides), `tools/name_session.py`, `tools/board.py`, `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/scripts/master_queue.py` (harness queue; usage-limit requeue + pause around :616-631), the RFP packaging step it calls.
- Records: `master_chat_tasks/decisions.jsonl` (entries with `"who": "master (auto)"` and the overrides), `feedback.jsonl`, `lessons.jsonl`, `board.json`, `log.jsonl`.
- Logs: `/tmp/opencode-logs/` (worker step logs), the harness jobs folder for the 28 Oct 17:51 errored run of cold-chain-backbone-quote.

## Known issues to confirm and root-cause (then find the ones not listed)
1. 28 Oct 17:44-17:51: the harness and the workers share one Claude subscription; the paid run errored ("all 1 accounts exhausted; soonest reset in 4698s") and both workers sat in opencode retry ("would exceed your account's rate limit"). Nothing warned before it hit; the master learned late. What signals existed (opencode `GET /session/status` retry state, litellm errors, master_queue failure text), and what should the watcher do (early warning, hold spawns, pause the queue, alert)?
2. 28 Oct 16:55: a worker hit opencode's doom_loop guard (3 identical poll calls) while waiting on a long Docker chain.
3. 28 Oct 17:36: "worker server not answering" alert from one missed health check while the server process was at ~100% CPU; `auto.py` watch_once around :1390-1396 never clears `worker_down_reported` except via resume (:935).
4. `tools/issue.py` refused every prompt on the session time box (16+ sessions) during auto runs, so the master overrode each one (decisions.jsonl lines 393-399 and 28 Oct entries).
5. After `master_queue.py cancel`, the queue stays flagged PAUSED until resume or the next add.
6. `auto.py spawn SHA PROMPT` called from zsh with `set -- $x` did not word-split (master-side usage trap).
7. Stale board rows (e.g. sentinel `7d4de68 P11 v3 recheck (running)`), registry type drift (traj fields stored as floats vs strings, fixed for caldermoor on 28 Oct).
8. Wind-down: cap `WIND_DOWN_MAX_H=2` (auto.py:73, wind_down :1367); harness auto-resume `harness_auto_resume` (:1237) resumes at parse_reset or +60 min, max 3 tries.
Then sweep every run for anything else: retries, crashes, timeouts, packaging failures, events never delivered, sessions left busy at stop, REPORT sections left empty, decisions the master had to make by hand that policy should have covered.

## Output
`OUT/FINDINGS.md`:
1. Run-by-run timeline (one short table per run: start, stop, sessions, harness runs, issues seen).
2. Issue table: id, symptom, runs affected (count), evidence, root cause (file:line), impact (time lost, paid runs lost, wrong state), severity (HIGH / MED / LOW), fix proposal (a diff sketch or exact policy wording, not applied), test that proves the fix (how to run it in `/tmp` with fake paths), detection rule the watcher should have.
3. Usage-limit section: what our runs tell us about budget per day (paid runs, worker hours), and a proposed budget rule for auto plans.
4. Policy gaps in AUTO_POLICY.md / PLAN_TEMPLATE.md (cite lines) and proposed wording.
5. Fix order (what first, what together, what risky).
6. Questions for Ayush (numbered, each with your recommended answer).
7. `## Lessons for the master` (max 5 lines).
Also `OUT/issues.csv` and `OUT/result_366516b.json` (must parse): `{"sha":"366516b","status":"DONE|BLOCKED","findings":"<path>","runs":7,"issues":N,"high":N,"med":N,"low":N}`.

## Stops
- Done: reply in at most 15 lines, ending with `done: /Users/mac/Desktop/Terminal Bench/master_chat_work/20261028_upgrade/R5_auto_issues/FINDINGS.md`.
