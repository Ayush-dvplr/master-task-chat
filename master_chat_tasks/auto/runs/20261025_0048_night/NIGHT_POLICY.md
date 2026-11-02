# NIGHT_POLICY: how the master chat answers for Ayush at night

Approved by Ayush 24 Oct 23:04 to 23:47 (decisions.jsonl). Applies only while night mode is on (`night/state.json` running, no `night/NIGHT_STOP`). Everything in `master_chat_tasks/README.md` still applies: same read order, same tools (`issue.py`, `intake.py`, `precheck.sh`, `loss.py`, `status.py`, `pending.py`, `board.py`), same caps, same U-rules. The only change: where the day process waits for Ayush, use the table below.

## Hands
| Day action | Night command (run from the master chat) |
|---|---|
| Hand Ayush a prompt to paste in a new session | `tools/issue.py ...` as by day, then `night/night.py spawn <sha> <prompt.md>` (add `--build` for a new task build) |
| Ayush sends "go" / an answer to a worker | `night/night.py send <sha> "go"` or `send <sha> @answer.md` |
| Ayush says `done: <sha>` | The watcher sends `[NIGHT WATCHER] done : <sha>` with the reply tail. Intake it as by day (`intake.py <sha>`) |
| Ask the harness chat to queue a run | `night/night.py harness <bundle path>` (pre-checks, diff, `master_queue.py add`, diff again, status) |
| Harness result | The watcher sends `harness DONE/FAILED: <task> ...`. Run `tools/intake.py --job <task>` as by day |

## Decisions in place of Ayush
| Situation | Night answer |
|---|---|
| QC PASS, or only minor findings | Accept the minors as PL notes, stop QC (U12), issue 1 gate run |
| QC FAIL | One fix within the round limits, then QC again |
| Probe tests >= 95 | Harden, up to 3 rounds, then park (kill rule) |
| Probe tests < 95 | Judge criteria from what the probe got wrong, then QC. Caldermoor: probe 3 tests 95-99 and overall < 70 goes straight to QC; tests 100 goes to harden r3 (Ayush 23:21) |
| Gate met (tests < 100, rubric < 100, overall < 70, 2 runs) | Stage `pl_ready`, stop. NEVER push, never submit |
| Worker reports DESIGN READY / DIAGNOSIS READY | Review it against the kit and the rules; send `go` unless it breaks a hard rule. If it does, send the correction instead |
| A round limit blocks the step you recommend | Give the override yourself (Ayush 23:45: "if override is your recomendation then give it"): `issue.py ... --override "NIGHT override per Ayush 23:45: <reason>"`. List every override in MORNING.md |
| Anything outside this table | Skip that task, keep the others running, write it under "Needs Ayush" in MORNING.md (Ayush 23:04: "skip it and keep the others running") |
| A worker is BLOCKED (permission or question) or ERROR | Do not retry blindly. Note it, send one corrective message if the cause is clear, else skip the task |

## Limits
- Busy workers and harness runs at a time follow the night's limits (`night.py status` shows them; hard caps 4 workers, 2 harness). A ramp raises them at its time and the watcher sends `LIMITS RAISED`; fill the free slots then. At most 2 new builds a night (`--build`); otherwise work on parked tasks first (Ayush 23:04).
- 25 Oct night (Ayush 00:3x): start 2 workers + 1 harness; from start + 1 h, 4 workers + 2 harness (`start ... --workers 2 --harness 1 --ramp HH:MM 4 2`). Change live with `night.py limits --workers N --harness N`.
- Ayush's own sessions d62ffe6, e2dc50b, e317de1, 9aaa7c6 run outside night mode (the watcher cannot see them): check their OUT folders for result_*.json about every hour and intake them per this policy.
- Harness paused for the Claude usage limit: run `.venv/bin/python scripts/master_queue.py resume` once after the reset time it states. Paused for a startup failure: leave it paused, note it in MORNING.md.
- Workers run anthropic/claude-opus-5-5, variant high. They cannot push, commit, use `gh`, queue the harness, or run night.py.

## Hard rules
1. Never push, publish, submit, or commit. `pl_ready` is the end of the night.
2. Never edit templates, kit files, GOALS.md, or this policy. Write proposed template changes in MORNING.md; they are applied only after Ayush says ok.
3. Never delete or overwrite a QC report, bundle, or harness job.
4. Every decision goes to `decisions.jsonl` with `"by": "master (night)"` and the policy row used, as verbatim.
5. After `NIGHT STOP`: start nothing (no spawn, no harness add, no send of a new step). On `FINAL`, finish MORNING.md and stop.

## MORNING.md (`night/MORNING.md`)
Keep it current through the night, not only at the end: needs Ayush; results per task; decisions and overrides; parked or skipped; proposed template changes; still running at stop. Times in IST (`TZ=Asia/Kolkata date`).
