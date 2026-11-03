DOCKSLOT: DESIGN (W1-031, draft, 3 Nov 2026)

Answers problem P3 ("sessions poll and wait although the jobs could run together") with suggestion S1 (a background Docker room manager that uses no AI tokens, works from measured values, and shows its state). Script: dockslot.py in this folder (standard library only, macOS and Linux). Nothing here is applied; it is a draft for the upgrade plan.

1. WHAT IS WRONG TODAY (from FINDINGS P3 and ANSWERS Q16 to Q18)

1. Each worker runs tools/dockfree.py and loops by itself while it prints START=no. There is no queue, so nobody knows who is next, a waiting worker spends tokens on every retry, and one chain died because set e treated START=no as fatal (sensor network log, 2 Nov).
2. dockfree counts memory limits, not memory used, and a container without a limit counts as 4096 MiB. Three 4 GiB jobs fill the 12.9 GiB it allows, even when they really use 1 GiB each.
3. dockfree looks only inside Docker. The 27 Oct hang came from outside Docker: three orphan Python solvers on the host (about 185 GB with swap) plus other apps and a VMware VM.
4. Limits are spread over auto.py constants (MAX_BUSY_WORKERS 5, MAX_HARNESS 2, MAX_BUSY_AT_LAUNCH 2, MAX_BUSY_WITH_RUN 3), AUTO_POLICY.md and old README and state.json lines.

2. THE IDEA IN ONE PARAGRAPH

dockslot keeps a small queue on disk. A worker asks for room with one blocking call (`dockslot.py run --kind kill -- docker run ...`). The call returns only when the job may start, runs the job, and frees the room when the job ends, also on error. While it waits, the worker's tool call simply blocks: there is no loop in the prompt and no token cost. Room is computed from the Docker VM size and from what containers really use, minus a headroom, and new grants stop while the Mac itself is short of memory or orphan solver processes are found. Paid runs go first, then the oldest waiter. A lease whose owner died is freed after a grace time and reported; a container is never stopped.

3. FILES (state directory, default ~/.local/state/dockslot, settings key docker.state_dir)

1. lock: one file; every change happens under `fcntl.flock` on it, so many workers can call at once.
2. leases/ID.json: one granted job (kind, mb, cpus, owner pid, granted time, note). Written with a temporary file and os.replace, so a reader never sees half a file.
3. waiters/ID.json and waiters/ID.fifo: one waiting job and its wake up pipe.
4. measure.json: the last measurement (refreshed when older than measure_max_age_s, or every refresh_s by the daemon).
5. status.json: the small state file the master and Ayush read (see section 9).
6. events.log: one JSON line per GRANT, RELEASE, FREED, OWNER_GONE, LONG, WAITER_GONE, HOLD, UNHOLD, DAEMON.
7. hold.json: present while new grants are held by hand.
8. daemon.json: pid of the background loop.

4. HOW A WORKER GETS ROOM (blocking acquire, not a poll loop)

1. The worker calls `run --kind K [--mb N --cpus N] -- command` (preferred) or `acquire` plus `release`.
2. acquire writes waiters/ID.json and creates a named pipe waiters/ID.fifo, then blocks in `select` on that pipe.
3. Whoever changes the state (a release, the daemon, another acquire) runs the scheduler under the lock. The scheduler walks the queue in order, writes a lease for each waiter that fits, and writes one byte into that waiter's pipe. The waiter wakes at once, sees its lease and returns LEASE=ID.
4. The waiter also wakes every refresh_s seconds on its own (a select timeout inside the script, not in the AI) to pick up changes in measured use and dead leases when no daemon runs.
5. `run` holds the lease under its own pid, exports DOCKSLOT_LEASE to the job, and releases in a finally block. Ctrl C on the run process does not free the room while the job still runs; the room is freed when the job ends.
6. `acquire --wait-max S` returns exit 3 after S seconds for callers whose tool calls have a time limit. With `--ticket NAME` the waiter keeps its place in the queue and a later call with the same ticket picks up the lease once granted. The ticket waiter is dropped only when no call has touched it for dead_grace_s.
7. For a job started by hand, `acquire` prints a docker hint `--label dockslot.lease=ID`. With that label dockslot can tie the container to its lease (section 6 and 7).

5. HOW ROOM IS COMPUTED (from real use)

1. Docker side: `docker info` gives VM memory and CPUs (today 15970 MiB and 8). `docker stats --no-stream` gives each container's real memory and CPU. `docker ps` gives the dockslot.lease label.
2. Capacity: cap_mb = VM memory minus headroom_mb (3072 today, as in dockfree).
3. Use: for each lease, the larger of its reservation and the real memory of its labelled containers; plus foreign use, which is the real memory of unlabelled containers beyond what the unlabelled leases reserved (a harbor run started under `dockslot run` has no label; its use is covered by its lease first). So a job above its size, or a container started outside dockslot, lowers the room at once.
4. free_mb = cap_mb minus use. A waiter fits when its mb is at most free_mb and its cpus keep the reserved CPU total at most cpu_cap (12 against 8 VM CPUs, as in dockfree; CPU overcommit only slows jobs).
5. Host side (the 27 Oct cause): on macOS `sysctl kern.memorystatus_level` (percent of memory free) and `sysctl vm.swapusage`; on Linux /proc/meminfo. New grants are held while free percent is below host.min_free_pct (15) or swap used is above host.max_swap_mb (8192).
6. Orphan detection: `ps -axo pid,ppid,rss,etime,comm`. A process whose name looks like a solver interpreter (python, node, java, perl, ruby, pypy), whose parent is pid 1 (its session is gone) and whose memory is at least orphan_rss_mb (2048) is listed as ORPHAN?. When orphans together hold orphan_hold_mb (8192) or more, new grants are held. Other processes above big_rss_mb (4096), such as VMware or a browser, are listed as BIG for Ayush to see. dockslot never kills any of them.
7. When Docker is not reachable, VM size and CPUs come from settings (fallback_vm_mb, fallback_vm_cpus) and use is the sum of reservations. status shows source=settings (docker unreachable).
8. What stays static on purpose: a running lease keeps at least its reserved size even if it uses less right now, because memory peaks come late in solver runs. The sizes themselves come from measurement (MEASURE.md, Q19), so they are real values, measured once and then checked live.

6. JOB KINDS AND DEFAULT SIZES (settings docker.kinds; placeholders until MEASURE.md)

1. kill: 4096 MB, 2 CPUs (matches `docker run --memory 4g --cpus 2`), priority 1, long_h 1.
2. oracle and nop: 4096 MB, 2 CPUs, priority 1, long_h 2. A task with a bigger task.toml memory_mb passes `--mb` and `--cpus` from task.toml.
3. paid: 8192 MB, 4 CPUs, priority 0, long_h 6, at most limits.harness (2) at once.
4. A new kind is one more entry in settings; no code change.

7. FAIRNESS

1. Order: priority first (paid 0, all others 1), then the time the waiter joined.
2. Head of line: if the first waiter does not fit, nobody behind it starts, so a big job (a paid run of 8 GB) is not starved by a stream of small kill tests. The one exception: a waiter blocked only by its own kind's max_running (a third paid run) does not block other kinds.
3. TEST.md shows a paid run that joined after an older kill test waiter and still started first.

8. DEAD AND LONG LEASES

1. A lease is alive while its owner pid lives (os.kill pid 0).
2. Owner gone but a container with its label still runs: the lease is kept and OWNER_GONE is reported once. Nothing is stopped.
3. Owner gone and no labelled container: dead_seen is stamped; after dead_grace_s (120) the lease file is deleted and FREED is written to events.log. If an unlabelled container of that job is in fact still running, its real memory still counts as foreign use, so freeing the lease cannot overfill the VM.
4. A waiter whose process is gone and that nobody touched for dead_grace_s is removed (WAITER_GONE).
5. A lease older than its kind's long_h is reported once as LONG (ENTRY 47: a long running job is only reported, never stopped).
6. dockslot never runs docker rm, docker kill, docker stop, docker system prune or harbor delete, and sends a signal only to its own daemon after checking that pid's command line contains dockslot.

9. STATE THE MASTER AND AYUSH CAN READ

1. `dockslot.py status` prints one summary line plus one line per lease, waiter, orphan and big process, for example:
   DOCKSLOT source=docker vm=15970MB cap=12898MB used=9758MB (reserved 8192, measured 9758, foreign 440) free=3140MB cpus=4/12 hold=no leases=2 waiters=1 idle=no daemon=running
2. `dockslot.py status --json` and the file status.json hold the same as JSON: source, vm_mb, cap_mb, used_mb, free_mb, reserved_mb, measured_mb, foreign_mb, cpus_used, cpu_cap, hold (list of reasons), leases, waiters (with position and wait minutes), containers, host (free_pct, swap_used_mb, orphans, big), idle, daemon, settings path, last events.
3. idle is true when there are no leases, no waiters and no containers. That is the only moment an image prune may run (R23); dockslot itself never prunes, it only says idle=yes.
4. The board or the master card can show one line from status.json (free_mb, leases, waiters, hold, orphans).

10. START AND STOP

1. Without a daemon dockslot already works: every acquire, release and status call measures (cached for measure_max_age_s) and schedules.
2. `dockslot.py daemon` adds a loop every refresh_s seconds: fresh measurement, dead lease cleanup, grants, status.json. On the Mac it runs with `nohup python3 tools/dockslot.py daemon >/dev/null 2>&1 &` from auto.py start, or later as a launchd agent. `daemon --once` does one pass.
3. `dockslot.py stop` stops the daemon only. Leases, waiters and containers stay as they are.
4. `dockslot.py hold "reason"` stops new grants (for example on a usage LIMIT or before Ayush uses the Mac for something heavy); running jobs go on. `dockslot.py unhold` resumes and grants at once.
5. All of this is plain Python: no AI tokens, no network, no Docker writes.

11. HANDOVER FROM AUTO.PY AND DOCKFREE.PY (R20)

1. Settings key docker.manager: "dockfree" (today) or "dockslot". While it says dockfree nothing changes; dockfree.py stays as the fallback (R20).
2. Rule 16 of _COMMON_RULES becomes, when manager is dockslot: "run every solver, kill test and blind program through `python3 tools/dockslot.py run --kind kill -- docker run --rm --memory 4g --cpus 2 ...`; oracle and nop runs through `dockslot.py run --kind oracle -- harbor run ...`. Do not loop; the call waits for you. If it exits 3, call it again with the same --ticket." The dockfree line stays as a fallback for when dockslot.py is missing.
3. auto.py: (a) `start` launches the daemon and `stop --now` leaves it running (jobs still need their queue) unless Ayush asks; (b) the spawn check "dockfree --need-mb 4096 once" becomes a read of status.json (hold empty and free_mb at least one kill size); (c) MAX_BUSY_WORKERS, MAX_BUILDS, MAX_HARNESS, MAX_BUSY_AT_LAUNCH, MAX_BUSY_WITH_RUN, PAID_RUNS_PER_DAY are read from settings limits.* with the current values as defaults (R21, R22); (d) on LIMIT the watcher may call `dockslot.py hold "usage limit"` beside its auto_hold.json.
4. Harness master_queue.py (not seen, F3.6) launches each paid run as `dockslot.py run --kind paid -- ...` or calls acquire with its own long lived pid as --owner-pid. Then MQ counts only kind paid leases, and the workers' oracle runs stop eating its 2 run limit (Q16 item 2).
5. Session limits stay separate: limits.workers and busy_with_run limit AI sessions (tokens and attention); dockslot limits Docker memory. A worker blocked in dockslot still counts as a busy session.

12. WHAT STAYS IN SETTINGS.JSON (see SETTINGS_ADD.json)

limits: workers, builds, harness, paid_per_day, busy_at_launch, busy_with_run. docker: manager, state_dir, headroom_mb, cpu_cap, fallback_vm_mb, fallback_vm_cpus, refresh_s, measure_max_age_s, dead_grace_s, kinds (mb, cpus, priority, long_h per kind), host (min_free_pct, max_swap_mb, orphan_rss_mb, orphan_hold_mb, orphan_names, big_rss_mb). The settings path comes from `--settings`, else DOCKSLOT_SETTINGS, else settings.json one folder above the script (master_chat_tasks/settings.json when it lives in tools/).

13. LIMITS OF THIS DRAFT

1. docker stats takes about 2 seconds with several containers; it runs under the lock at most once per measure_max_age_s.
2. kern.memorystatus_level is the macOS free memory percent used by Activity Monitor's pressure graph; the threshold 15 is a guess until MEASURE.md.
3. A lease held through acquire by a short lived shell (the default owner is the parent pid) is freed after dead_grace_s unless its container carries the label. That is why `run` is the normal path for workers.
4. Tested here only in dry mode (no Docker in this container) and with a stub docker for the stats parsing; the first real run belongs on the Mac with manager still on dockfree.
