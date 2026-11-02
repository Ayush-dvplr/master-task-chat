# Speed upgrade plan v1 (30 Oct 2026, master). PLAN ONLY: nothing applied.

Ayush asked for: ~4 worker sessions + 2 harness runs + 4-5 Docker containers at once, no session stuck waiting, every step measured, no conflict with what is built, no assumptions.
Evidence: [MEASURE.md](MEASURE.md) (+ CSVs here), the explore map of auto.py / master_queue.py / rules, and the librarian web research (Slurm backfill, Docker cgroup limits, SQLite WAL queues, macOS tmp cleaner).

## 1. Where the time goes (measured, 164 worker sessions, 26-30 Oct, 245 h)

| Cause | Share | Evidence |
|---|---|---|
| Waiting for Ayush / master decision | 35% | MEASURE sec 3; b223662 31.3 h, ed621c7 4.3 h, 9111ecc 3.6 h |
| Workers sleep-polling for a Docker slot or a chain | 23% | 382 `sleep N; docker ps` loops; ed621c7 1 h 42 min waiting with only 1-2 foreign containers |
| Model work, reading, tools | 42% | residual + other tool |

Docker itself is idle most of the time: 0 containers in 43% of samples, mean 1.1-1.5, max 5. One verifier = 1 vCPU, ~330 MiB. Docker VM = 8 vCPU, 15.6 GiB. Measured slowdown at 1-3 containers: 0-18%.
So the limit is the **rules** ("wait until no other session's container is up", "max 2 Docker-heavy", one serial gate chain), not the hardware.

Other losses: 18 of 24 QC rechecks re-ran the full oracle gate, some on a tree that had just been gated (outage 005e42b1b4aa twice); the 30 Oct reboot wiped /tmp (77 of 80 work paths, 3 warrant blinds lost); 4 failed paid runs (129 min).

## 2. Changes, in order of measured gain

### S1. Shared Docker slot tool (replaces "wait for a free slot" by eye). Gain: most of the 23% poll time.
- New `tools/dockslot.py acquire --cpus N --mem MB --tag SHA:job` / `release` / `status`. One state file with `fcntl.flock` (the lock pattern master_queue.py already uses at :148-152). Leases with heartbeat + pid check, so a dead job frees its slot.
- Budget = Docker VM: 8 vCPU, 15.6 GiB minus 3 GiB headroom (the same MEM_HEADROOM_MB 3072 master_queue uses). A job is charged its task.toml `cpus` / `memory_mb` (21 tasks 4096 MB, 5 tasks 8192 MB; 22 tasks 2 cpus, 4 tasks 4).
- master_queue paid runs take their slot through the same tool. Today `harbor_pgids` sees only `bin/harbor run` (:229-238), so worker `docker run` jobs are invisible to it. After S1 both see one budget.
- Order rule = backfill: a waiting paid run or a harden's measuring step goes first; a smaller job may start ahead only if it fits without delaying it (Slurm backfill idea).
- `acquire` waits inside one call (it watches `docker events --filter event=die`, re-checking every 30 s as a fallback), so a worker makes one tool call instead of 40 poll loops.
- What fits at once with the 12.6 GiB usable: 3 jobs of 4096 MB, or 1 of 8192 + 1 of 4096. That is below "4-5 containers" if we charge the declared memory. See question Q1.

### S2. Gate jobs in parallel lanes. Gain: 62-68 min gate down to ~25-35 min (prediction, not measured).
- Today QC Step 10 and the fix gates run 7 harbor jobs in 1-2 lanes (warrant: mean concurrency 1.9; longest job 24 min).
- New: warm the image once first (the QC prompt's "two at once build the same image and stall" note, :81, is the reason it was serial), then each job takes its own dockslot. Up to 4 lanes.
- Gate first: a benchmark on an empty Docker (1-5 containers, CPU and I/O). MEASURE could not run it (containers were up). If the benchmark shows >25% slowdown at 4, lanes stay at 3.

### S3. Reuse a gate on identical bytes, in QC RECHECK only. Gain: one full gate (10-68 min) on most rechecks.
- Scope (Ayush 30 Oct 14:15): ONLY the P11 `MODE recheck` that follows a P12 fix. A `MODE full` QC (a task's first QC, or any full QC) ALWAYS runs the full Step 10 gate, no reuse.
- The fix session already runs oracle x3 / owner / nop / stub. If the recheck finds the same tree sha (the method intake.py uses) and the saved gate results (result.json files kept outside /tmp, see S4), Step 10 reruns only oracle x1 + nop as a spot check, and writes "reused gate <tree sha>" in the report.
- A changed byte = full gate, as now. A paid run is never reused.
- Enforced in the recheck prompt text only (the full-QC prompt is not edited), and the QC result json gets `step10: reused <tree sha>` so it can be audited.

### S4. Nothing important lives in /tmp. Gain: no lost blinds or gate logs after a reboot.
- macOS clears /tmp on reboot and removes files not accessed for 3 days. Move /tmp/oracle-qc, /tmp/harbor-jobs-qc, /tmp/opencode-logs, /tmp/blind and gate dirs to `~/tb_runs/<date>/...` (same disk, not synced). Docker mounts stay the same kind of path.
- Rule text changes only (QC prompt :69-73, _COMMON_RULES rule 3, master_queue log path :581-584).

### S5. Fewer stops for decisions. Gain: part of the 35%.
- Most waits were known exception questions (crash/timeout cap, park or harden). A plan line "Pre-approved defaults" lets auto take the stated default and log it; anything not on the list still stops.
- Every Needs-Ayush stop also gets a macOS notification (`osascript display notification`, no install) so a 31 h wait becomes a short one.
- Workers that wait for a "go" are left idle and their Docker slot is released (S1), so they do not hold capacity.

### S6. Limits set to the target and checked in one place.
- Auto: 4 workers, 2 harness. A Docker job needs a dockslot; the old "max 2 / max 3 Docker-heavy" advice lines become "use dockslot".
- master_queue `remove_containers` matches by task-name prefix (:272-286) and can hit another session's container of the same task; S1 tags make it remove only its own.

## 3. What this must not break (checked against the code)

| Built thing | How the plan keeps it |
|---|---|
| auto.py LIMIT state, MAX_BUSY_AT_LAUNCH 2 / MAX_BUSY_WITH_RUN 3 (subscription budget) | Unchanged. Docker slots are a separate budget. |
| master_queue flock state, FIFO paid runs, auto-resume after usage limit | Kept; only the resource check calls dockslot. |
| Tree sha method (intake.py) and tree refusals | S3 reuses it; no change to intake. |
| WORKER_PERMISSION (workers may only run harbor `--agent oracle|nop`) | Unchanged. |
| Tests pinning numbers: test_auto.py MAX_BUSY_WORKERS==5 (:1215), policy text (:1213), test_master_queue docker_budget (:70, :137) | Updated with the change, all three suites must stay green. |
| Never prune, never `--delete` | Unchanged. |
| Oracle count rules (AUTO_POLICY 2+nop, QC Override 4 x3, kit x5) | Not changed by this plan; already a known conflict (pending). |

## 4. Steps (each: who / check / undo)

| # | Step | Who | Check | Undo |
|---|---|---|---|---|
| 0 | Benchmark 1-5 containers (CPU loop + 500 MB I/O) and one real verifier at 1/2/3/4, on an empty Docker | worker, read-only on project | table in MEASURE_BENCH.md | none needed |
| 1 | dockslot.py + tests (lease expiry, crash, two acquirers, budget) | worker | unit tests green; fake jobs | delete file |
| 2 | master_queue uses dockslot; tagged container removal | worker | test_master_queue green + 1 dry run | backup file |
| 3 | auto.py: limits 4/2, dockslot status in `auto.py status`, notifications, pre-approved defaults read from PLAN | worker | test_auto green; smoke run | backup file |
| 4 | Rule/prompt text: dockslot, ~/tb_runs paths, parallel lanes, gate reuse (snapshot first, as for v3.7) | master | grep: no old "/tmp/oracle-qc", "Max 2 Docker-heavy" in live files | snapshots |
| 5 | Verify session (fresh eyes): plan vs code vs tests | worker | VERIFY_REPORT PASS | - |
| 6 | One real day at 4 workers / 2 harness, measured again with the MEASURE scripts | auto | poll share and container use vs today | old limits |

Order: 0 can run any time Docker is empty. 1-3 do not touch any task bytes and can run while tasks run, but are switched on only between runs.

## 5. Ayush answers (30 Oct ~14:15)
- Q1 memory charge: measured peak +50% when known, task.toml value when not.
- Q2 gate reuse: yes, spot check oracle x1 + nop, ONLY in QC recheck after a fix; full QC always full gate (S3 scope line).
- Q3 parallel lanes: up to 4, capped at 3 if the benchmark shows >25% slowdown.
- Q4 decisions: both (pre-approved defaults listed in each plan, logged; macOS notification on every Needs-Ayush stop).
- Q5 /tmp: move to ~/tb_runs/<date>/.
- Q6: PLAN ONLY for now. Saved to the later upgrade list; nothing applied. Next when Ayush says: verify session, then build steps 0-6.
| 30 Oct | HOLD (Ayush): record only. More improvements to come, researched together, then one build on Ayush's word. |
