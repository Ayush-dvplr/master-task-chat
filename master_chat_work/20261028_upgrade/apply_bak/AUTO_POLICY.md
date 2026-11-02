# AUTO_POLICY: how the master chat answers for Ayush while he is away

Replaces NIGHT_POLICY.md (archived in `auto/runs/20261025_0048_night/`). Approved by Ayush 26 Oct 2026. Applies only while auto mode is on (`auto/LATEST` run has a live watcher and no `AUTO_STOP`). Everything in `master_chat_tasks/README.md` still applies: same read order, tools (`issue.py`, `board.py`, `pending.py`, `intake.py`, `precheck.sh`, `loss.py`, `status.py`), caps and rules. The run's `PLAN.md` (Ayush's list for this run) wins over this file where they differ.

Restart after power cut, reboot or closed laptop (Ayush 26 Oct, option A): nothing starts by itself. Ayush types `resume auto` in the master chat; the master runs `python3 auto/auto.py resume` and reports what was lost and what was resumed.

Scheduled start (Ayush 27 Oct): "start auto at HH:MM until HH:MM" -> `python3 auto/auto.py start --at HH:MM --until HH:MM --plan <file> --label <l>`. Everything is checked when it is set (master chat reachable, limits, plan file, no run active); a waiter (+ caffeinate) runs the normal start at that time, adopting the board rows running then. Master chat unreachable at the start time: retry every minute for 15 minutes, then give up (SCHEDULED.log). Mac asleep past the start time but before the end: start on wake, with a late note in REPORT.md. `auto.py status` shows the schedule; `auto.py cancel` removes it; a plain `start` refuses while one exists. After a power cut the schedule is lost: `status`/`resume` show it as STALE and the master asks Ayush.

## Hands
| Day action | Auto command (run from the master chat) |
|---|---|
| Hand Ayush a prompt to paste in a new session | `tools/issue.py ...` as by day, then `auto/auto.py spawn <sha> <prompt.md>` (`--build` for a new task build) |
| Ayush pastes "go" / an answer into a worker | `auto/auto.py send <sha> "go"` or `send <sha> @answer.md` (works for adopted sessions too, once they are idle) |
| Ayush says `done: <sha>` | The watcher sends `done : <sha>` with the reply tail. Read the OUT files as by day, update board/pending/registry |
| Give Ayush a bundle path for the harness | `auto/auto.py harness <Tasks_INPUT bundle path>` |
| Harness result | The watcher sends `harness DONE/FAILED: <task> ...`. Read scores as by day |
| A session Ayush started before auto mode | Adopted at start (board rows with status running). When its `done` arrives, check its result, then continue it with `send`, and note "continued in auto mode" in REPORT.md |

## Decisions in place of Ayush (rules as of 26 Oct)
| Situation | Auto answer |
|---|---|
| Worker reports DESIGN READY / DIAGNOSIS READY | Review against LEVER_RULES_v3 and the kit, send the go message (written to `prompts/issued/<slug>/<ts>_go.md`). If it breaks a hard rule, send the correction instead |
| Worker reports DESIGN BLIND READY / BUILD READY | Issue a P13 v2 blind read (`prompts/templates/P13_blind_solve_v2.md`), spawn it; when done, score it as by day and send the blind-program path / result back to the builder |
| Blind read exact on a redesign that was already redesigned once | Stop that task, write it under Needs Ayush. No third redesign |
| Issuing any QC prompt (P11 v3) in auto mode | Keep its AUTO MODE Step 10 block: "run 2 oracle runs and 1 nop run (oracle-1, oracle-2, nop-1 on the tests-only copy); pass = both oracle 1.000 and nop 0.000". Ayush decision 9, 27 Oct. The rest of Step 10 (oracle 3-5, stub, owner-only) is owed before push and run by the master or a manual QC |
| QC PASS or minors only (v4 order, Ayush decision 1) | Accept minors as PL notes, freeze (record tree sha), then 1 harness run on the frozen bytes. No hardening after a QC pass |
| QC FAIL | One fix session (QC_FIX_PLAYBOOK_v3 guard rules G1-G7), then QC recheck |
| Run: tests < 85 AND rubric < 85 AND final < 50 (gate v3.6, Ayush 27 Oct 22:20) | Gate met on the frozen QC-passed bytes = stage `pl_ready`, stop (push needs 1 such run, Ayush 27 Oct 17:17). NEVER push |
| Run misses the gate | Never re-run the same bytes (decision 6). Write the trajectory read-out (KNOWLEDGE.md section T, `tools/trajectory_readout.py`), then the fix prompt in QC-safe form; then QC recheck, then 1 new run. tests 100 -> new test lever (back to design). Never park; parking only on Ayush's word |
| A round limit blocks the recommended step | Give the override yourself: `--override "AUTO override per Ayush 26 Oct: <reason>"`. List every override in REPORT.md |
| Anything outside this table | Skip that task, keep others running, write it under Needs Ayush |
| Worker BLOCKED (permission/question) or ERROR (not limit/network) | Do not retry blindly. One corrective message if the cause is clear, else skip and report |

## Interruptions (handled by auto.py; the master only reports)
| Event | What the master does |
|---|---|
| `PAUSED <sha>: limit/network` | Nothing; the watcher sends "continue" at the reset time (max 4 tries). Note the lost time in REPORT.md |
| `GAVE UP <sha>` | Mark it under "Interrupted or unfinished" |
| `INTERRUPTED <sha>` | Check its OUT folder. If the step is finished on disk (result json), treat as done. Else send one "continue" if the session is idle, otherwise report it |
| `GAP` / `AUTO RESUMED` | Re-check every running item (board rows, OUT folders, harness status) before issuing anything; write what was lost and what was resumed |
| `NETWORK BACK` | Continue; no extra action |

Rule for every interruption: no mess. Never delete partial work, never re-issue a step that already has a result on disk, never start the same board id twice. If unsure, mark it "unfinished" in REPORT.md and leave it.

## Limits
- Busy workers and harness runs follow the run's limits (`auto.py status`; hard caps 4 workers, 2 harness). At most 2 new builds per run unless PLAN.md says otherwise.
- Docker cap (27 Oct, after the 14:35 hang): the master spawns at most 2 Docker-heavy workers at once (QC, harden, build, kill test, blind scoring); check `auto.py status` and `docker ps` before each spawn. auto.py does not enforce this.
- Workers run anthropic/claude-opus-5-5, variant high. They cannot push, commit, use `gh`, queue the harness, or run auto.py. They may run `harbor run --agent oracle` and `--agent nop` (QC Step 10); every other `harbor run` stays denied. The permission applies to workers spawned after auto.py is restarted.

## Hard rules
1. Never push, publish, submit, or commit. `pl_ready` is the end.
2. Never edit templates, kit files, GOALS.md, LEVER_RULES, or this policy. Proposed changes go in REPORT.md.
3. Never delete or overwrite a QC report, bundle, or harness job.
4. Every decision goes to `decisions.jsonl` with `"by": "master (auto)"` and the policy row used.
5. After `AUTO STOP`: start nothing new. On `FINAL`, finish REPORT.md and stop.
6. Always give file links in REPORT.md for every prompt issued and every result read.

## REPORT.md (`auto/runs/<run>/REPORT.md`, linked from `auto/LATEST`)
Keep it current through the run: In short; Needs Ayush; Results per task; Decisions and overrides; Interrupted or unfinished (with times); Still running at stop; Proposed changes. Times in IST (`TZ=Asia/Kolkata date`).
