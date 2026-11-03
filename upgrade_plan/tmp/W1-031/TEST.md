DOCKSLOT: DRY TEST (W1-031, 3 Nov 2026, run in the planning container, Linux, Python 3.13, no Docker daemon)

Setup. Fake capacity vm_mb=11264 with headroom 3072 gives cap 8192 MB, so exactly two 4096 MB jobs fit. Test settings (test_settings.json in this folder) set refresh_s 1 and dead_grace_s 2 so the test is quick, and give the paid kind 4096 MB so a paid run fits in one freed slot. The script that ran is test_dockslot.sh in this folder; its core lines:

  export DOCKSLOT_SETTINGS=test_settings.json DOCKSLOT_DIR=<empty temp dir> DOCKSLOT_FAKE="vm_mb=11264,cpus=8"
  job() { echo "$(date +%T) $1 START lease=$DOCKSLOT_LEASE"; sleep "$2"; echo "$(date +%T) $1 END"; }
  T1, T2: run --kind kill -- job A 4 &   run --kind kill -- job B 6 &   (1 s later) run --kind kill -- job C 1 &   status
  T3:     acquire --kind kill --owner-pid 999999   status   (3 s later) daemon --once   status
  T4:     run kill K1 3 &   run kill K2 6 &   (1 s) run kill K3 1 &   (1 s) run --kind paid PAID 1 &   status

Command: DOCKSLOT_DIR=<scratch>/t1 bash test_dockslot.sh
Output (stderr and stdout together, unedited):

  == T1 and T2: two small jobs start together, a third waits and starts when one releases
  dockslot GRANT: kill-1103-113014-1265 kill 4096 MB 2 cpus after 0 s wait
  11:30:14 A START lease=kill-1103-113014-1265
  dockslot GRANT: kill-1103-113014-1266 kill 4096 MB 2 cpus after 0 s wait
  11:30:14 B START lease=kill-1103-113014-1266
  WAITING kill-1103-113015-1274 position 1 of 1, need 4096 MB (free 0 MB)
  DOCKSLOT source=fake vm=11264MB cap=8192MB used=8192MB (reserved 8192, measured 0, foreign 0) free=0MB cpus=4/12 hold=no leases=2 waiters=1 idle=no daemon=stopped
    LEASE kill-1103-113014-1265 kill 4096MB 2cpu pid=1265 age=0.0min
    LEASE kill-1103-113014-1266 kill 4096MB 2cpu pid=1266 age=0.0min
    WAIT  #1 kill-1103-113015-1274 kill 4096MB waiting 0.0min
  11:30:18 A END
  dockslot RELEASE: kill-1103-113014-1265 kill after 0.1 min
  dockslot GRANT: kill-1103-113015-1274 kill 4096 MB 2 cpus after 3 s wait
  11:30:18 C START lease=kill-1103-113015-1274
  11:30:19 C END
  dockslot RELEASE: kill-1103-113015-1274 kill after 0.0 min
  11:30:20 B END
  dockslot RELEASE: kill-1103-113014-1266 kill after 0.1 min
  
  == T3: a dead lease (fake owner pid 999999) is freed and reported
  dockslot GRANT: kill-1103-113020-1283 kill 4096 MB 2 cpus after 0 s wait
  LEASE=kill-1103-113020-1283
  docker run hint: --label dockslot.lease=kill-1103-113020-1283
  DOCKSLOT source=fake vm=11264MB cap=8192MB used=4096MB (reserved 4096, measured 0, foreign 0) free=4096MB cpus=2/12 hold=no leases=1 waiters=0 idle=no daemon=stopped
    LEASE kill-1103-113020-1283 kill 4096MB 2cpu pid=999999 OWNER-GONE age=0.0min
  dockslot FREED: dead lease kill-1103-113020-1283 (kill, 4096 MB) freed: owner pid 999999 gone, no container with its label; nothing was stopped
  DOCKSLOT source=fake vm=11264MB cap=8192MB used=0MB (reserved 0, measured 0, foreign 0) free=8192MB cpus=0/12 hold=no leases=0 waiters=0 idle=yes daemon=stopped
  
  == T4: a paid run jumps the queue
  dockslot GRANT: kill-1103-113023-1291 kill 4096 MB 2 cpus after 0 s wait
  11:30:23 K1 START lease=kill-1103-113023-1291
  dockslot GRANT: kill-1103-113023-1292 kill 4096 MB 2 cpus after 0 s wait
  11:30:23 K2 START lease=kill-1103-113023-1292
  WAITING kill-1103-113024-1300 position 1 of 1, need 4096 MB (free 0 MB)
  WAITING paid-1103-113025-1302 position 1 of 2, need 4096 MB (free 0 MB)
  DOCKSLOT source=fake vm=11264MB cap=8192MB used=8192MB (reserved 8192, measured 0, foreign 0) free=0MB cpus=4/12 hold=no leases=2 waiters=2 idle=no daemon=stopped
    LEASE kill-1103-113023-1291 kill 4096MB 2cpu pid=1291 age=0.0min
    LEASE kill-1103-113023-1292 kill 4096MB 2cpu pid=1292 age=0.0min
    WAIT  #1 paid-1103-113025-1302 paid 4096MB waiting 0.0min
    WAIT  #2 kill-1103-113024-1300 kill 4096MB waiting 0.0min
  11:30:26 K1 END
  dockslot RELEASE: kill-1103-113023-1291 kill after 0.1 min
  dockslot GRANT: paid-1103-113025-1302 paid 4096 MB 2 cpus after 1 s wait
  11:30:26 PAID START lease=paid-1103-113025-1302
  11:30:27 PAID END
  dockslot RELEASE: paid-1103-113025-1302 paid after 0.0 min
  dockslot GRANT: kill-1103-113024-1300 kill 4096 MB 2 cpus after 3 s wait
  11:30:27 K3-older-waiter START lease=kill-1103-113024-1300
  11:30:28 K3-older-waiter END
  dockslot RELEASE: kill-1103-113024-1300 kill after 0.0 min
  11:30:29 K2 END
  dockslot RELEASE: kill-1103-113023-1292 kill after 0.1 min
  
  == events.log
  {"t": "2026-11-03 11:30:14", "event": "GRANT", "text": "kill-1103-113014-1265 kill 4096 MB 2 cpus after 0 s wait", "lease": "kill-1103-113014-1265"}
  {"t": "2026-11-03 11:30:14", "event": "GRANT", "text": "kill-1103-113014-1266 kill 4096 MB 2 cpus after 0 s wait", "lease": "kill-1103-113014-1266"}
  {"t": "2026-11-03 11:30:18", "event": "RELEASE", "text": "kill-1103-113014-1265 kill after 0.1 min", "lease": "kill-1103-113014-1265"}
  {"t": "2026-11-03 11:30:18", "event": "GRANT", "text": "kill-1103-113015-1274 kill 4096 MB 2 cpus after 3 s wait", "lease": "kill-1103-113015-1274"}
  {"t": "2026-11-03 11:30:19", "event": "RELEASE", "text": "kill-1103-113015-1274 kill after 0.0 min", "lease": "kill-1103-113015-1274"}
  {"t": "2026-11-03 11:30:20", "event": "RELEASE", "text": "kill-1103-113014-1266 kill after 0.1 min", "lease": "kill-1103-113014-1266"}
  {"t": "2026-11-03 11:30:20", "event": "GRANT", "text": "kill-1103-113020-1283 kill 4096 MB 2 cpus after 0 s wait", "lease": "kill-1103-113020-1283"}
  {"t": "2026-11-03 11:30:23", "event": "FREED", "text": "dead lease kill-1103-113020-1283 (kill, 4096 MB) freed: owner pid 999999 gone, no container with its lab
  {"t": "2026-11-03 11:30:23", "event": "GRANT", "text": "kill-1103-113023-1291 kill 4096 MB 2 cpus after 0 s wait", "lease": "kill-1103-113023-1291"}
  {"t": "2026-11-03 11:30:23", "event": "GRANT", "text": "kill-1103-113023-1292 kill 4096 MB 2 cpus after 0 s wait", "lease": "kill-1103-113023-1292"}
  {"t": "2026-11-03 11:30:26", "event": "RELEASE", "text": "kill-1103-113023-1291 kill after 0.1 min", "lease": "kill-1103-113023-1291"}
  {"t": "2026-11-03 11:30:26", "event": "GRANT", "text": "paid-1103-113025-1302 paid 4096 MB 2 cpus after 1 s wait", "lease": "paid-1103-113025-1302"}
  {"t": "2026-11-03 11:30:27", "event": "RELEASE", "text": "paid-1103-113025-1302 paid after 0.0 min", "lease": "paid-1103-113025-1302"}
  {"t": "2026-11-03 11:30:27", "event": "GRANT", "text": "kill-1103-113024-1300 kill 4096 MB 2 cpus after 3 s wait", "lease": "kill-1103-113024-1300"}
  {"t": "2026-11-03 11:30:28", "event": "RELEASE", "text": "kill-1103-113024-1300 kill after 0.0 min", "lease": "kill-1103-113024-1300"}
  {"t": "2026-11-03 11:30:29", "event": "RELEASE", "text": "kill-1103-113023-1292 kill after 0.1 min", "lease": "kill-1103-113023-1292"}

Reading.
1. T1 and T2 pass: A and B started in the same second (11:30:14). C waited at position 1 with free 0 MB, did not loop in any AI, and started at 11:30:18, the same second A released (woken through its pipe, "after 3 s wait").
2. T3 passes: the lease with owner pid 999999 shows OWNER-GONE, and after the 2 s grace `daemon --once` freed it with the FREED event "owner pid 999999 gone, no container with its label; nothing was stopped". free went back to 8192 and idle=yes.
3. T4 passes: K3 joined the queue at 11:30:24, the paid run at 11:30:25. status lists the paid run as #1 and K3 as #2. When K1 released at 11:30:26 the paid run started first; K3 started only after more room was freed (11:30:27).

Extra checks (same container, real mode, so Docker is unreachable and the settings fallback is used; daemon pid replaced by N):

  $ python3 dockslot.py status
  DOCKSLOT source=settings (docker unreachable) vm=15970MB cap=12898MB used=0MB (reserved 0, measured 0, foreign 0) free=12898MB cpus=0/12 hold=no leases=0 waiters=0 idle=yes daemon=stopped
    HOST free=97% swap_used=0MB
  $ python3 dockslot.py daemon &  (then status after 2 s)
  DOCKSLOT source=settings (docker unreachable) vm=15970MB cap=12898MB used=0MB (reserved 0, measured 0, foreign 0) free=12898MB cpus=0/12 hold=no leases=0 waiters=0 idle=yes daemon=running
  $ python3 dockslot.py hold "test hold"
  dockslot HOLD: new grants held: test hold; running jobs go on
  $ python3 dockslot.py acquire --kind kill --wait-max 2; echo rc=$?
  WAITING kill-1103-113038-1426 position 1 of 1, need 4096 MB (manual: test hold)
  TIMEOUT no lease yet
  rc=3
  $ python3 dockslot.py unhold
  dockslot UNHOLD: grants resumed
  $ python3 dockslot.py stop
  daemon pid N asked to stop; leases and containers untouched

Reading.
4. With Docker unreachable, status says source=settings (docker unreachable) and uses fallback_vm_mb 15970 minus 3072 headroom = 12898 MB, exactly the room dockfree allows today (F3.7). Host free percent and swap come from /proc/meminfo here; on the Mac from sysctl.
5. daemon starts and shows daemon=running; stop signals only that pid after checking its command line, and leaves leases and containers alone.
6. hold blocks new grants with the reason shown to the waiter; acquire --wait-max gives exit 3 instead of hanging a tool call forever.

Stats parsing check (stub docker on PATH that prints fixed `docker info`, `docker ps` and `docker stats` lines; three containers: k1 labelled kill-x using 5.1 GiB of a 4 GiB size, an unlabelled harbor oracle using 1.5 GiB, an unlabelled foreign container using 3000 MiB; leases kill-x and oracle-y at 4096 MB each):

  docker 15970 [k1 5222 MB lease kill-x, harbor-oracle 1536 MB, foreign 3000 MB]
  {'cap_mb': 12898, 'reserved_mb': 8192, 'measured_mb': 9758, 'foreign_mb': 440, 'used_mb': 9758, 'free_mb': 3140, 'cpus_used': 4, 'cpu_cap': 12, 'hold': []}

7. The overuse of kill-x counts at its real 5222 MB, the unlabelled 4536 MB are first covered by oracle-y's 4096 MB reservation, and the remaining 440 MB count as foreign. dockfree would have said free = 12898 minus limits (4096 + 6144 + 4096 for the no limit container) = negative, START=no; dockslot sees 3140 MB free.

Not tested here: a real Docker daemon, macOS sysctl values and orphan detection on the Mac (ps output format is the same on both systems), and many hours of uptime. Those belong in the first run on the Mac with docker.manager still "dockfree".

T5 FAST LANE (added by the master, 3 Nov, ENTRY 68). Fake VM 11264 MB minus 3072 headroom = 8192 MB. A kill job (4096) runs; a paid job of 8192 MB waits for room; oracle and nop (2048 each, fast) pass it while they fit; the paid job starts when the kill job ends. Fast jobs pass a blocked job only up to fast_max_running (4) at once and only until it has waited fast_starve_s (300 s).
14:41:03 KILL START lease=kill-1103-144103-563
14:41:05 NOP START lease=nop-1103-144105-571
14:41:05 ORACLE START lease=oracle-1103-144105-570
14:41:06 NOP END
14:41:06 ORACLE END
14:41:09 KILL END
14:41:09 PAID2 START lease=paid-1103-144104-568
14:41:10 PAID2 END
