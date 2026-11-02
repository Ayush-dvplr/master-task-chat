# MEASURE: where time goes on this Mac (26-30 Oct 2026)

Measured 30 Oct 2026 13:47-13:56 IST. Read-only on all project files and on opencode.db (`sqlite3`/python `mode=ro`, `query_only=1`). Nothing was started, stopped or deleted except my own helper files.
All times are IST. Harbor `result.json` timestamps ending in `Z` were converted from UTC (+5:30).
Raw data: CSVs in this folder (names given per section). Scripts used: `scripts/` (sess.py, gaps.py, decomp.py, trials.py).

## 0. Headline findings (all derived below)

1. Wall time is dominated by waiting, not by compute. Over 164 worker sessions (26-30 Oct, 245 session-hours) the split is: waiting for Ayush/master 35%, `sleep N; echo poll` loops (waiting for Docker chains) 23%, other tool time 6%, model thinking/typing and everything else 36%. (sec 3)
2. Docker is NOT saturated. In 382 `docker ps` samples taken inside workers' poll loops, containers up: 0 in 43%, 1 in 16%, 2 in 20%, 3 in 15%, 4 in 5%, 5 in 0.8%. Mean active worker sessions (5-min grid, 29 Oct 00:00-30 Oct 13:45) is 1.7; 4+ sessions active only 6.4% of slots. (sec 4)
3. The queue is serial by convention, not by hardware: workers wait for a "free slot" (foreign container) before starting their own chain. ed621c7 waited at least 1 h 42 min (09:19 to first own container 11:01) with only 1-2 foreign containers up. (sec 4.2)
4. Contention that can be measured is small at 1-3 containers: the warrant gate's oracle verifier took 727.1-740.2 s in both gates (6740572 and 4989b35), agent 651-732 s, nop/stub 229-247 s. Largest measured slowdown: warrant P7w scoring calls ~370 s alone vs ~435 s under 2 jobs (+17.6%, from LOG.md). (sec 6)
5. The 7-job QC/fix gate for ONE task is 62.0 min (6740572) to 67.6 min (4989b35) wall with 2 lanes; summed container time is 117 min, i.e. mean concurrency 1.9. Longest single job is 24 min, so more lanes could cut the gate toward ~25-30 min, but that was NOT benchmarked (sec 7, 9).
6. The reboot on 30 Oct 11:14 wiped /tmp: 77 of 80 `/tmp/...` paths named in LOG.md/BOARD.md are gone, including `/tmp/blind` blind packages (3 warrant blinds could not be re-scored), and the historical gate/harbor job dirs. (sec 8)
7. The parallel-container benchmark was SKIPPED: `docker ps` was non-empty at start (13:47: `cold-chain-backbone-quote__bujdnue__verifier__trial-main-1`, 13:54: `...__cckux6w__...`). (sec 5)

## 1. Machine facts (source: `machine_raw.txt`, produced by the commands named)

| Item | Value | Command / file |
|---|---|---|
| CPU | Apple M1 Max, 10 logical cores | `sysctl -n hw.ncpu machdep.cpu.brand_string` |
| RAM | 34,359,738,368 B = 32 GiB | `sysctl -n hw.memsize` |
| OS | macOS 27.0.1 (26A434) | `sw_vers` |
| macOS swap | total 0 MB, used 0 | `sysctl vm.swapusage` |
| Page stats (16 KiB pages) | free 76,880 (1.2 GiB); inactive 780,220 (11.9 GiB); active 819,517 (12.5 GiB); wired 139,771 (2.1 GiB); compressor holds 427,067 pages (6.5 GiB); pageouts 225; swapouts 0 | `vm_stat` |
| memory_pressure | "System-wide memory free percentage: 82%" | `memory_pressure` |
| Boot time | 30 Oct 11:14 (uptime 2:33 at 13:47); earlier reboots 23 Oct 09:42, 23 Oct 00:26 | `uptime`, `last reboot` |
| Load average | 13:47: 5.51 / 4.64 / 4.57; 13:54: 2.08 / 3.18 / 3.93 (10 cores) | `uptime` |
| Docker | Docker Desktop, server 29.8.2, overlayfs (containerd snapshotter) | `docker info` |
| Docker VM | 8 CPUs, 15.6 GiB RAM (settings: Cpus 8, MemoryMiB 16384, SwapMiB 2048, Virtualization.framework + Rosetta) | `docker info`; `~/Library/Group Containers/group.com.docker/settings-store.json` |
| Docker disk | images 463 (8.06 GB, 2.70 GB reclaimable); build cache 556 entries 18.66 GB (10.63 GB reclaimable); containers 2 (1 active) | `docker system df` |
| One live verifier container | 100.15% CPU (= 1 vCPU), 327.8 MiB, 13 pids (13:47); 100.12%, 324.2 MiB (13:54) | `docker stats --no-stream` |

Caveat: vm_stat counters are since the 11:14 boot only, so they say nothing about 26-29 Oct.
Inference (not measured): a verifier is single-threaded (1 vCPU, ~330 MiB), so on 8 vCPU / 15.6 GiB roughly 8 such containers fit before CPU saturates. Tasks that allocate up to 4 GiB (cold-chain wide books OOM at 4 GiB per its LOG.md 12:43) change the memory side.

## 2. Per-step durations from board.json (source: `board_step_durations.csv`, `board_step_summary.csv`)

Method: rows with `issued` 2026-10-26..30 (157 rows), `updated - issued`, status `done`. Class by regex on `step` (hand-checked: see CSV column `class`). Flag `LAG/ABN` = note says verified-on-disk / aborted / stopped / moved / waits-for-Ayush / go sent, or status is not done. `updated` includes master lag (sec 2.2).

### 2.1 Durations in minutes (done rows only)

| Step kind | n all | median | min | max | n clean | median clean | min clean | max clean | p25-p75 clean |
|---|---|---|---|---|---|---|---|---|---|
| P2 build | 4 | 873 | 302 | 1301 | 2 | 374 | 302 | 446 | 302-446 |
| P9 harden / redesign / other-fix | 25 | 209 | 13 | 646 | 22 | 180 | 13 | 646 | 56-265 |
| P11 QC full | 8 | 80 | 28 | 1219 | 7 | 52 | 28 | 246 | 38-121 |
| P11 QC recheck | 30 | 48 | 7 | 1874 | 27 | 43 | 7 | 237 | 31-102 |
| P12 fix | 20 | 99 | 14 | 1219 | 18 | 90 | 14 | 309 | 42-129 |
| P13 blind (read/solve) | 44 | 32 | 5 | 684 | 44 | 32 | 5 | 684 | 13-51 |
| score blinds in Docker | 7 | 66 | 32 | 299 | 7 | 66 | 32 | 299 | 54-290 |
| triage / scan / research | 12 | 47 | 15 | 199 | 12 | 47 | 15 | 199 | 36-57 |

Checks against the numbers given in the brief:
- tariff harden ed621c7: board says 589 min (04:14 issued to 14:03 updated) because it includes the wait for Ayush's go. The opencode session shows go at 09:07/09:15 and last message 12:29, so about 3 h 14-3 h 22 on the go-to-finish span: **matches "3h16"**. The ~1 h 55 Docker wait is partly verified: sec 4.2 shows 1 h 42 min (09:19 to 11:01).
- QC rechecks "21 min-2.5 h": board clean rows run 7 min to 3 h 57 (median 43 min, p75 102 min). Range roughly OK; median is lower than the brief's range.
- full QC "1h53-3h57": board gives 3 rows over 100 min: 121 (df9f49f), 109 (bdd41f8, warrant), 246 (4e298da, cold-chain); the other full-QC rows are 28-52 min. So only the long tail matches; the median is 52 min.
- fixes "50 min-3h09": board clean P12 rows have p25-p75 42-129 min, max 309 min; the brief's range is the upper-middle of it.
- paid runs "19-52 min": see sec 6.4, done runs 16.1-101.7 min, median 26.5; 21 of 23 under 60 min.
- warrant oracle "732 s agent + 731 s verifier": **verified**, 4989b35 gate4 oracle-1: agent 732.2 s, verifier 730.9 s (`harbor_trial_phases_ours_dedup.csv`).

### 2.2 Board time vs real session time (source: `board_vs_session_lag.csv`)

For sha-titled sessions, medians in minutes: issue-to-first-message / session first-to-last message / last-message-to-board-updated.

| Step kind | n | board total | issue->first msg | session | last msg->updated |
|---|---|---|---|---|---|
| P11 QC full | 8 | 80 | 4 | 26 | 4 |
| P11 QC recheck | 30 | 48 | 1 | 30 | 3 |
| P12 fix | 20 | 99 | 2 | 86 | 3 |
| P13 blind | 44 | 32 | 8 | 6 | 4 |
| P9 harden etc. | 25 | 209 | 3 | 82 | 4 |
| P2 build | 4 | 873 | 4 | 444 | 404 |
| score blinds | 7 | 66 | 2 | 63 | 3 |

Medians show master/paste lag is small (1-8 min). Summed lag is large only because of outliers: P11 recheck sum board 84.9 h vs session 31.1 h; P9 harden board 95.4 h vs session 76.1 h. P13 blind: median board 32 min vs session 6 min, i.e. most of the board time is the waiting before the blind is picked up (8 min) and the scoring that follows, not the blind itself.

## 3. Wait vs work from the opencode DB (sources: `opencode_sessions.csv`, `opencode_wait_vs_work.csv`, `wait_vs_work_by_step_class.csv`, `opencode_long_bash_calls.csv`, `scripts/`)

DB schema read first: `session(id,title,parent_id,time_created...)`, `message(session_id,time_created,data)`, `part(message_id,session_id,time_created,data)`; tool parts carry `state.time.start/end` and `state.input.command`. 323 top-level sessions are titled with a 7-hex sha; 164 start 26 Oct or later.

Definitions (the only assumptions): span = first to last message; **human/master wait** = a gap above 3 min before a *user* message that is not covered by tool execution; **poll** = union of bash calls with `sleep N` plus `poll|docker ps|tail|result.json|echo|date`, which are the "wait for Docker chain" loops; **other tool** = remaining tool time; **residual** = span minus the three = model generation, reading and everything else.

| Scope | Sessions | Span h | Human wait h | Poll h | Other tool h | Residual h |
|---|---|---|---|---|---|---|
| 26-30 Oct | 164 | 245.1 | 85.7 (35%) | 55.5 (23%) | 14.8 (6%) | 89.1 (36%) |
| 27-28 Oct | 83 | 107.2 | 22.6 (21%) | 22.0 (21%) | 9.0 (8%) | 53.7 (50%) |
| 29-30 Oct | 51 | 111.2 | 48.1 (43%) | 33.3 (30%) | 5.0 (4%) | 24.8 (22%) |
| 29-30 Oct without b223662 | 50 | 77.7 | 16.9 (22%) | 31.8 (41%) | n/a | 24.2 (31%) |

b223662 (cold-chain harden) alone is 33.5 h span, 31.3 h of it waiting for Ayush's cap-60 go (04:46 29 Oct to 11:57 30 Oct, gap 1870.5 min).

By step kind (sha sessions from 26 Oct; hours):

| Step kind | n | Span | Human wait | Poll | Residual |
|---|---|---|---|---|---|
| P9 harden etc. | 28 | 113.2 | 54.1 (48%) | 19.8 (18%) | 31.7 (28%) |
| P12 fix | 22 | 35.3 | 3.8 (11%) | 15.2 (43%) | 13.1 (37%) |
| P11 QC recheck | 30 | 31.1 | 3.9 (13%) | 9.6 (31%) | 16.5 (53%) |
| P2 build | 4 | 27.9 | 15.1 (54%) | 4.0 (14%) | 7.6 (27%) |
| P11 QC full | 8 | 9.7 | 0 | 2.6 (27%) | 6.9 (72%) |
| score blinds | 7 | 7.4 | 2.5 (33%) | 3.5 (47%) | 0.8 (11%) |
| P13 blind | 44 | 5.8 | 0 | 0 | 5.2 (90%) |

Per-worker examples (span / human wait / poll / residual, minutes): ed621c7 494 / 324 / 107 / 58; 4989b35 304 / 67 / 164 / 60; 6740572 399 / 25 / 155 / 191; 7d363c8 299 / 59 / 86 / 116; 9111ecc 584 / 219 / 243 / 85.
Examples of poll-heavy sessions: 145bdba 193 min span, 170 min in poll loops; d21576c 174 / 137; 92ee28b 232 / 152; a395eb2 127 / 94.
Long gaps (>10 min, `scripts/gaps.py`): almost all precede a user message ("Master go for ...", "continue where u left", "do not use subagents"). Examples: ed621c7 257 min waiting for go, 28.7 and 35.9 min "continue"; 9111ecc 137.5 min waiting for go; 7d363c8 47 min. The run of 10-20 minute gaps inside 9111ecc (about 14 gaps, 29 Oct 14:26-18:51) are long tool calls (the assistant message is created after the tool returns), which is why section 3 uses tool timestamps, not message gaps.
Polling cadence: 431 `sleep ...; docker ps` commands in sha sessions (382 of them 26-30 Oct); they sleep 120-240 s each (`sleep 120; echo poll`, `sleep 210; echo poll 25`, `sleep 237`).

## 4. Docker concurrency actually seen

### 4.1 Containers up at poll time (source: `docker_ps_poll_samples.csv`; 382 samples 26-30 Oct)

| Containers up | 0 | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|---|
| samples | 165 | 61 | 75 | 58 | 20 | 3 |
| share | 43% | 16% | 20% | 15% | 5% | 0.8% |

Mean per day: 27 Oct 1.30, 28 Oct 1.54, 29 Oct 1.23, 30 Oct 1.09 containers (max 5). Bias: samples exist only when a worker was polling, so idle periods are under-counted.
Active worker sessions (>=1 message in the previous 10 min, `active_session_concurrency.csv`): 0 for 18.8% of 5-min slots, 1 for 23.8%, 2 for 33.1%, 3 for 17.9%, 4 for 5.1%, 5 for 1.3%; mean 1.7.
Paid queue: `max_concurrent` = 2 (`.master-queue/state.json`); only 5 of 27 paid runs overlapped another (sec 6.4).

### 4.2 ed621c7 waiting for a Docker slot (sources: DB session ed621c7 text parts; `docker_ps_poll_samples.csv` rows for ed621c7)

- 09:07 master go ("29 Oct 09:15"). 09:19: "Another session's container is up; I'll prepare the kill chain and start it when the slot is free." 09:41: "Still waiting on the foreign containers". 11:11: "k2 waiting for the foreign container".
- Polls between 09:19:13 and 11:01:37: 29 samples, foreign container(s) up in 25 of them; the foreign ones were `k5_9111ecc`, `quirky_hopper`, `plain__eawb8v9__verifier`, `plain__xlk6ulr__verifier`, `plain__2gwhrki__verifier` (other tasks' verifiers), never more than 2 containers. First ed621c7 container (`kill-ed621c7-k1-ae99`) is seen at 11:01:37.
- Waiting before its first own container: 09:19 to 11:01 = **1 h 42 min**; the brief's "~1 h 55" is not reproduced exactly (the chain log in /tmp/opencode-logs was wiped by the reboot, sec 8). A second wait: k2 waited for `owner__vnpon4s__verifier` until ~11:24.
- Session ed621c7 ran 04:15-12:29 but 04:49-09:07 (257 min) was waiting for the go; from go to end ~3 h 22 min, polling inside it 107 min (46 poll commands).
- Same pattern elsewhere: cold-chain LOG 28 Oct "waiting for docker slots (2 others' verifiers up)" 13:08:18; "waiting slot for nop" 13:29:20 to 13:35:07 = 5 m 47 s (`bundles/_work/cold-chain-backbone-quote/LOG.md`); warrant gate2 "waits s3" (LOG l.71).

## 5. Parallel-container benchmark: NOT RUN

Condition was "only if `docker ps` shows no containers when you start". `docker ps` at 13:47 showed `cold-chain-backbone-quote__bujdnue__verifier__trial-main-1` (Up 8 minutes) and at 13:54 `...__cckux6w__verifier__trial-main-1` (the cold-chain cap-60 gate, `/tmp/ccq_gate_20261030T132433-ff4c`, still running oracle_2 then owner/nop/stub). The warrant gate4 finished 13:42:21 (log `p12/runs/gate4.log`). No bench container was created; no `bench_speed_*` files exist; `bench_io` was not created. Table (e) below is therefore empty:

| Concurrency | CPU+mem loop per-container wall | total wall | I/O 500 MB wall |
|---|---|---|---|
| 1, 2, 3, 4, 5 | not measured | not measured | not measured |

Closest real evidence instead: sec 6 and the single snapshot "one verifier = 1 vCPU, ~330 MiB" in sec 1.

## 6. Gate / run phase timings and contention evidence

### 6.1 Source coverage
The brief's sources were mostly gone: `/tmp/wae*_gate*/jobs` (only the current `wae4989b35_gate_20261030T123443-4655` survives), `/tmp/ccq_gate_*` (only `ccq_gate_20261030T132433-ff4c`), `/tmp/harbor-jobs-qc/*` (gone), `/tmp/opencode-logs/*` (only `locks/cold-chain-backbone-quote.lock`). Reason: reboot 30 Oct 11:14 (sec 8). I therefore also parsed every `result.json` under the project tree (find over `Terminal Bench`, 965 files; 291 trial-level files from 26 Oct; 53 unique after de-duplicating copies): `Terminal_2.0_Harbor_Harness/jobs|Output_RFP|.kiro-run-*`, `master_chat_work/**/gate_run_a*`, `master_chat_work/*_blind_scores`, `master_chat_work/*/jobs`, and the two live /tmp gates. All rows: `harbor_trial_phases.csv` (includes Anubis sample runs), project-only de-duplicated: `harbor_trial_phases_ours_dedup.csv` (columns env_setup_s, agent_setup_s, agent_exec_s, verifier_s, reward, exception).

### 6.2 Phase split (de-duplicated project trials, seconds; median (min-max))

| Trial kind | n | total | env setup | agent exec | verifier | share of summed time env/agent/verifier |
|---|---|---|---|---|---|---|
| paid agent (openhands-sdk, claude-opus-5) | 28 | 1544 (393-6077) | 10 (5-171) | 1091 (570-5853) | 211 (50-2016) | 1.3% / 77.7% / 20.0% |
| oracle-type gate job | 22 | 1118 (49-1737) | 3 (2-11) | 5 (0-732) | 729 (25-1719) | 0.5% / 19.3% / 79.3% |
| nop | 3 | 240 (71-952) | 4 (2-11) | 0 | 229 (42-943) | 1.4% / 0 / 96.1% |

env setup is tiny because images are pre-warmed ("warm environment" step, 3 s when cached: `wae4989b35.../logs/warm_environment.log`, gate4.log `START warm 12:34:53 / DONE 12:34:56`). Image-build time is not in these numbers (sec 9).
Key reading: for gates, the verifier is where the time goes (oracle verifier 727-740 s for warrant, 1100-1260 s for schema/metered blind scores, up to 1719 s); for paid runs it is the agent (~18 min median).
Notable slow paid runs: multicorner 6077 s total (agent 5853 s); schema a7 4169 s total with a 2016 s verifier (30 Oct 03:08); metered a4 2290 s with a 1554 s verifier.

### 6.3 The two warrant gates compared (same task, same 2-lane script; sources: `warrant-asof-entitlement-compiler/gate/chain.log` for 6740572; `p12/runs/gate4.log` + live /tmp result.json for 4989b35)

| Job | 6740572 gate wall s | 6740572 verifier s | 4989b35 gate4 wall s | 4989b35 verifier s | agent exec (4989b35) |
|---|---|---|---|---|---|
| oracle-1 | 1381 | 732.1 | 1476 | 730.9 | 732.2 |
| oracle-2 | 1390 | 740.2 | 1465 | 727.1 | 726.6 |
| oracle-3 | 1426 | 727.7 | 1421 | 732.7 | 656.2 |
| owner-1 | 1417 | 728.7 | 1396 | 732.6 | 651.6 |
| nop-1 | 261 | 247.1 | 243 | 228.7 | 0 |
| stub-1 | 259 | 244.7 | 256 | 240.1 | 0.3 |
| forgery-1 | 909 | 234.5 | 892 | 232.3 | 641.0 |
| gate total | 04:57:21-05:59:21 = 62.0 min | | 12:34:43-13:42:21 = 67.6 min | | |

- Verifier time is identical within 1.7% between gates (oracle 727-740 s). Wall time differs +0 to +7% (oracle-1 +6.9%, oracle-3 -0.4%).
- Docker polls during the first gate: 19 samples, mean 1.63 containers, max 3; during gate4: 2 samples, mean 1.5, max 3 (`docker_ps_poll_samples.csv`). Other workers were active in both windows (7d363c8 build; b223662 cap-60 scoring), so neither gate was "alone".
- Mean concurrency inside a gate: summed wall 7043 s / 3721 s = 1.9. Lane A: oracle-1 -> oracle-3 -> forgery; lane B: oracle-2 -> owner -> nop -> stub. A zero-wait schedule could not go below the longest job (1426 s = 23.8 min) plus the setup, so 62-68 min is about 2.6-2.8x the single-job floor.

### 6.4 Paid runs (source: `.master-queue/state.json` runs -> `master_queue_runs.csv`, `paid_runs_overlap.csv`)
27 runs started 26-30 Oct (total 869.7 min): 23 DONE, 3 FAILED, 1 STOPPED. DONE: median 26.5 min, min 16.1, max 101.7; 21 of 23 under 60 min (median of those 26.2). Failures/stops consumed 129.1 min (slipway p1 31.2 min wrapper_exit=1; cold-chain a3 12.1 min subscription limit; district a14 39.2 min cancelled by operator; slipway p2 46.6 min wrapper_exit=1).
Overlap with another queue run: only 5 runs (district a12 23%, schema a6 18%, district a15 34%, slipway p2 100%, warrant a1 72%). Agent exec for the same task with vs without overlap: district-heat a11 1090.6 s (0%), a12 1021.8 s (23%), a13 1031.0 s (0%), a15 1003.4 s (34%); no slowdown visible. Possible slowdown: slipway pass2 2515.8 s at 100% overlap (failed, RewardFileNotFound) vs pass3 1386.8 s at 0%; warrant a1 2945.7 s at 72% overlap; both are confounded by task and by API latency (cold-chain a3 died with ApiOverloadedError). Treat as unproven.

### 6.5 Contention evidence, collected
1. **P7w calls**: `warrant-asof-entitlement-compiler/LOG.md` l.75 "calls ~370 s" (alone) vs l.76 "P7w calls ~435 s under 2 jobs, near the 450 s per-call cap" (12:12 vs 12:28 30 Oct). +17.6%. Note this is the worker's own statement; containers up at that time are not recorded in the log.
2. **Warrant gates** (6.3): verifier flat at 727-740 s with 1-3 containers up. So the 727-740 s is the real single-job cost, not a contention artefact, and 2-3 concurrent containers on 8 vCPU do not slow it.
3. **cold-chain gates** (`cold-chain-backbone-quote/LOG.md`): 28 Oct 13:08: oracle_1b 6 m 01 s with "1 other task container up", oracle_2 6 m 42 s, oracle_3 8 m 14 s, nop waited a slot 5 m 47 s then 6 m 39 s, owner 6 m 49 s. 28 Oct 15:57-16:27 ("1 other task container up"): oracle-1 7 m 34 s (includes warm image build), oracle-2 3 m 57 s, oracle-3 6 m 16 s, owner 7 m 16 s, nop 4 m 48 s. Same oracle job ranged 3 m 57 s to 8 m 14 s (2.1x), but the other containers' identity is not logged for each job and the tests differ slightly between the two gates, so this is suggestive only.
4. **metered gate (ac12c0b, 28 Oct)**: oracle verifier 1194.0, 1259.1, 1227.5 s; stub 1204.4; nop 942.6; owner-only 1719.4 s (+36-44% vs oracle). Poll samples exist for the first five (1-4 containers) but none at 18:13 for the owner run, so the cause (extra containers vs different job) cannot be attributed.
5. **Current cold-chain cap-60 gate**: oracle_1 started 13:38:36 (while warrant stub ran 13:38:05-13:42:21): 767 s total, verifier 753.9 s; compare warrant stub 256 s vs 259 s earlier: unchanged with 2 containers up.
6. Load average 5.5 on 10 cores at 13:47 with just one verifier container (100% of 1 vCPU) running: the rest of the load is host processes (opencode, python scoring scripts, Docker VM). Not decomposed (sec 9).

Net: measurable contention at <=3 containers is 0-18%; the larger loss is queueing (sec 4.2) and serial lanes, not slow containers.

## 7. Duplicate work

Sources: `qc_result_oracle_counts.csv` (QC/reports/*/result_*.json), `registry/tasks.json` pipeline.tree_sha, worker LOG.md files.

- **QC Step 10 reruns the full gate every time**: 37 QC result files since 26 Oct; each carries `rewards.oracle` arrays plus owner, nop, stub. 25 are `step10: full` (75 oracle runs in total), 6 `reduced-auto`, 6 unlabeled (older sentinel/caldermoor/assay, 3-5 oracle runs each). Total oracle runs recorded 114. Of the 37, 24 are `mode: recheck`; 18 of those still ran `step10: full` (6 were `reduced-auto`), so 3 of 4 rechecks pay the full gate again.
- **Same tree gated twice back to back**: outage-window-replan: fix 20552cf gate chain ALL_DONE 08:45:09 (oracle 1.0 x3, owner 1.0, nop 0.0) on tree 005e42b1b4aa, then QC a36c154 Step 10 08:51-09:01 on "frozen 005e42b1b4aa" (board note; `QC/reports/outage-window-replan/_progress_v2.md`): oracle x3 + owner + nop + stub repeated on an identical tree, ~10 min of Docker for this fast task. metered 145bdba is also "frozen bbc865f36130" (registry tree_sha bbc865f36130) after fix d21576c's own gates. Warrant 4989b35: gate4 ended 13:42 on tree bd90fad58ff0 (LOG l.80); a following P11 recheck with Step 10 full would repeat a 62-68 min gate (not yet run, so not measured).
- **Oracle-equivalent scoring repeated per test edit** (warrant p12, `p12/runs/*.txt`): eng1 (the repaired solve) scored in full at 1155.2 s (`score_eng1.txt`) and again 1144.2 s (`s3_eng1.txt`); partial rescoring 479.1 s (s4) and 567.5 s (s5); then the gate runs oracle x3 at ~1400 s each. The same 3 blinds (`787e598`, `b6c896c`, `92419ce`) plus a1 were rescored in s3, s4 and s5 (3 times each; b92419ce 4 times incl. s2) after each tests change; after t6 the results collapsed to 3/155 then 0/155 (the s4/s5 rescore was cheap: 13-58 s each, so the cost is small except the oracle).
- **Identical blinds scored**: 9111ecc LOG/DB 29 Oct 16:47: "the 4 blinds scored so far are identical (199/591). Skip blinds 9179 and b686" (master message). Cold-chain/schema/district: `score 3 ... blinds` steps ran 32-299 min each (7 steps, median 66 min).
- **Kill programs re-scored after master kill**: warrant `p12/runs/killed_1027/` holds s3_P3b, s3_P6o, s6_P7w_first, gate3.log; rerun as s3r (LOG l.73-76), P7w rc 137 then rerun with budget lifted (s6).

## 8. Lost work and restarts

- **Reboot 30 Oct 11:14 wiped /tmp** (`last reboot`; `/private/tmp` entries all created 11:14 or later; `powerlog` dir 11:14). Of 80 distinct top-level `/tmp/...` paths named in worker LOG.md, BOARD.md and board.json, 77 no longer exist (list: `tmp_paths_referenced_missing.txt`; only /tmp/blind, current ccq gate, opencode-logs survive). Consequences logged: warrant LOG 11:37 "blind delivered dirs under /tmp/blind are gone (tmp cleared), blinds cannot be re-scored on t7 conv_6; s5 blind rows void" and 12:12 repeated; all historical gate result.json and chain logs in /tmp are gone (sec 6.1).
- **Master killed worker runs**: 4989b35 stopped 10:23, scripts killed 10:27 (board note + LOG l.73): partial s3_P3b/P6o and s5/gate3 moved to killed_1027, restarted 11:32; gate2 had already been killed by the worker at 10:19 (LOG l.72) and gate4 started 12:34; `s3r P7w rc=137` at 12:11:40 (s5.log).
- **Sessions stopped by user mid-step**: 6740572 stopped 00:45-01:01 30 Oct ("Your session was stopped by Ayush mid-step", 16.4 min gap); 6ebf33a "stopped by Ayush 30 Oct ~00:58 for auto adoption"; a4f790c aborted mid-build 28 Oct 18:55 (superseded, DESIGN.md kept); ac12c0b aborted 28 Oct 18:55 and v1 report finished by 47cde19 (board notes). Board status counts overall: 14 superseded, 11 dropped, 2 running.
- **Invalid gate**: cold-chain 28 Oct 13:01:45 "gate oracle_1 INVALID: harbor CancelledError after wrapper pkill ... Re-run when docker slots free" (LOG).
- **Paid runs lost**: 4 runs, 129.1 min (sec 6.4). Plus first-chain aborts at harbor prompts in earlier days (sentinel 23 Oct, emberforge 22 Oct, vendor-archive 21 Oct, district 22 Oct), outside the 26-30 Oct window.
- **Pauses waiting for decisions** (not lost work but idle time): b223662 31.3 h; ed621c7 4.3 h; 9111ecc 3.6 h; 09963d3 / 7d95b18 / d11904c 0.6-3.5 h each (sec 3).

## 9. NOT MEASURED, and why

1. Parallel Docker benchmark (1-5 concurrent containers, I/O variant): skipped, containers from the running cold-chain gate were up at start and at re-check (sec 5). Rule: do not run while any non-bench container is up.
2. How many containers the Mac sustains before verifiers slow down: no controlled solo-vs-N experiment exists. Observed up to 5 containers in polls but no job timing paired to that count except sec 6.3 (<=3).
3. Host CPU/memory over time (26-29 Oct): no sampling log exists (`sar`-like data absent; `powerlog` empty; vm_stat since 11:14 only). Only snapshots: load 5.51 and 2.08, one `docker stats`.
4. Docker image build time: gate jobs use warm images (3 s warm step); `docker build` durations for first builds are not recorded anywhere I could read, and build cache is 18.66 GB.
5. Exact slot-wait for ed621c7 (brief: ~1 h 55): chain logs lost with /tmp; measured 1 h 42 min from polls; other tasks' slot waits only where a worker wrote them in text (cold-chain 5 m 47 s).
6. Harbor phase timings for gates run before 11:14 on 30 Oct that lived only in /tmp (e.g. `/tmp/wae*_gate*/jobs`, `/tmp/ccq_gate_*` older, `/tmp/harbor-jobs-qc`): gone. The 291 saved trial files (26 Oct+) cover archived blind scores, paid runs and a few oracle gates only; the 6740572 gate has wall= lines but no result.json.
7. LLM/API latency and token cost per step: not extracted (the DB has `tokens_*` and `cost` columns per session but I did not break down model time from tool time at message level; "residual" mixes thinking, generation and I/O).
8. Subagent sessions (titled `... (@explore subagent)`) and non-sha-titled sessions (e.g. 086e1b4... blank titles, 28-29 Oct): excluded; sessions renamed after 29 Oct might be missed.
9. Master chat time (the controlling session) and Ayush's own think time: only visible as the "human wait" gaps in worker sessions.
10. Contention cause attribution for the 1719 s metered owner run and the cold-chain 3 m 57 s vs 8 m 14 s spread: containers up at those moments are not logged for every job.
11. Same-tree duplicate QC Step 10 for tasks other than outage-window-replan: tree shas for fix vs QC are recorded only for outage (005e42b1b4aa), metered (bbc865f36130) and warrant (bd90fad58ff0); registry holds tree_sha for 8 of 33 tasks.
12. Not run: nothing (no harbor, no docker run, no prune). Files created: this folder only (+ `scripts/` copies); helper scripts initially written in /tmp were moved here and removed.

## 10. File index (this folder)

| File | Content |
|---|---|
| `machine_raw.txt` | raw output of sysctl/vm_stat/memory_pressure/uptime/docker info/df/stats/settings |
| `board_step_durations.csv`, `board_step_summary.csv` | per-row and summarized board durations |
| `board_vs_session_lag.csv` | issue/first message/last message/updated per sha |
| `opencode_sessions.csv`, `opencode_wait_vs_work.csv`, `wait_vs_work_by_step_class.csv`, `opencode_long_bash_calls.csv` | session spans, gap and tool-time decomposition, bash calls >=120 s |
| `docker_ps_poll_samples.csv`, `active_session_concurrency.csv` | containers up at poll time; active sessions |
| `harbor_trial_phases.csv`, `harbor_trial_phases_ours_dedup.csv`, `trial_phase_vs_docker_ps_load.csv`, `gate_wall_lines.csv` | harbor phase timings, wall= lines |
| `master_queue_runs.csv`, `paid_runs_overlap.csv` | paid runs from state.json |
| `qc_result_oracle_counts.csv`, `tmp_paths_referenced_missing.txt` | duplicate-gate counts; lost /tmp paths |
