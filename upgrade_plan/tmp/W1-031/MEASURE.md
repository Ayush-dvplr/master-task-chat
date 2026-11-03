DOCKSLOT: ONE TIME MEASUREMENT ON THE MAC (answers Q19, W1-031, 3 Nov 2026)

Goal: replace the placeholder sizes in settings docker.kinds (4096 MB per kill test, oracle and nop, 8192 MB per paid run) and the host thresholds with measured values. Time: about 20 to 30 minutes of Ayush's normal jobs, plus the paid run whenever one runs anyway. Everything below only reads (docker info, docker stats, sysctl, ps). It starts, stops and deletes nothing; the jobs measured are the jobs Ayush would run today anyway. No extra paid run is needed.

Copy dockslot.py to master_chat_tasks/tools/ first (or run it from upgrade_plan/tmp/W1-031/). In the commands below, DS means: python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/dockslot.py"

STEP 1. STARTING POINT (1 minute)

  sysctl kern.memorystatus_level vm.swapusage
  docker info --format 'mem={{.MemTotal}} cpus={{.NCPU}}'
  docker ps --format '{{.Names}} {{.Status}}'
  DS status

Write down: free percent (memorystatus_level), swap used, number of running containers, and any ORPHAN? or BIG lines (VMware, browser). Best start is with no container running.

STEP 2. START THE SAMPLER (keeps running in its own Terminal tab)

  DS peaks --minutes 30 --every 3 --csv ~/dockslot_peaks_1.csv

It reads docker stats every 3 seconds and at the end prints, per container name, the peak memory in MB and the peak CPU percent (100 means one full CPU), plus _ALL_CONTAINERS (peak of the sum) and _HOST_SWAP_USED_MB (peak swap on the Mac). In a second tab, also keep the Mac's own view:

  while true; do date +%T; sysctl -n kern.memorystatus_level; sysctl -n vm.swapusage; sleep 30; done | tee ~/dockslot_host_1.txt

STEP 3. ONE JOB OF EACH KIND, ONE AFTER ANOTHER (about 15 minutes)

1. One kill test, alone, as a worker would run it (`docker run --rm --memory 4g --cpus 2 ...` with its wall cap). Use a task whose strong solver runs the longest, since that is the peak that matters. Note the container name in the peaks table.
2. One oracle run: `harbor run --agent oracle` on a bundle with memory_mb 4096 in task.toml, and if there is one, also on the biggest bundle (memory_mb 6144).
3. One nop run on the same bundle.

STEP 4. JOBS TOGETHER (about 10 minutes)

1. Start two kill tests and one oracle run at the same time.
2. If swap did not grow and memorystatus_level stayed above about 25 percent, add a third kill test.
3. Stop adding when swap grows by more than about 500 MB, or the level falls under about 20 percent. Do not stop any running job to finish early; just let them end.
Write down the largest set that ran with flat swap.

STEP 5. THE PAID RUN (whenever one runs anyway)

When the next paid run starts from the queue, start a second sampler for its full length:

  DS peaks --minutes 120 --every 10 --csv ~/dockslot_peaks_paid.csv

Note which container names belong to the paid run (the harness names them after the task).

STEP 6. TURN THE PEAKS INTO SETTINGS

For each kind, take the peak memory of its container (for a harbor run, the sum of its containers at their peak):
1. mb = peak memory times 1.25, rounded up to a multiple of 256, never above the job's own Docker limit (4096 for a kill test with --memory 4g; the task.toml memory_mb for oracle, nop and paid).
2. cpus = peak CPU percent divided by 100, rounded up, never above the job's --cpus.
3. Fit count = (VM memory in MB minus headroom_mb) divided by mb. With today's VM (15970 MB) and headroom 3072, the cap is 12898 MB: at 1536 MB per kill test that is 8 kill tests, at 4096 it is 3.
4. Check the fit count against STEP 4: if fewer jobs ran with flat swap than the fit count says, raise headroom_mb by the missing amount (so the formula matches what the Mac really did).
5. host.min_free_pct = the lowest memorystatus_level seen in STEP 4 while swap stayed flat, minus 10, but at least 10.
6. host.max_swap_mb = swap used at STEP 1 plus 2048.
7. Leave cpu_cap at 12 unless STEP 4 showed jobs timing out from CPU (kill tests that hit their wall cap only when run together).

STEP 7. WHAT TO SEND BACK (paste into the chat)

  kind     peak_mem_mb   peak_cpu_%   -> mb    cpus
  kill     ...           ...          -> ...   ...
  oracle   ...           ...          -> ...   ...
  nop      ...           ...          -> ...   ...
  paid     ...           ...          -> ...   ...
  together: largest set with flat swap = ... ; lowest memorystatus_level = ... %
  start: swap used ... MB, free ... %, other apps: ...

Plus the two csv files. These numbers go into settings docker.kinds.*.mb and cpus, docker.headroom_mb, docker.host.min_free_pct and docker.host.max_swap_mb (SETTINGS_ADD.json). After that dockslot works from these sizes and from live docker stats, so a job that grows past its size, or a container started outside dockslot, still lowers the room at once.

Notes.
1. If the VM size in Docker Desktop changes later, nothing needs to change here: dockslot reads the VM size from docker info every time.
2. Run this with docker.manager still "dockfree"; the measurement does not depend on dockslot being in charge.
3. If Docker Desktop's memory graph and docker stats disagree a lot, trust docker stats for per job sizes and the host log for swap.
