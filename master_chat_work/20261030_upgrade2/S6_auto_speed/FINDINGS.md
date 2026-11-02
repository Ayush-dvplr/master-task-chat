VERDICT: Keep the applied auto reliability fixes; prioritize the paid-cap parser, shared Docker admission, and narrowly scoped decision defaults before raising concurrency.

# S6: auto mode, speed, and master decisions audit

Paths below are relative to `/Users/mac/Desktop/Terminal Bench/` unless they start `/tmp/`. This was a read-only audit of source data. `INCIDENTS.csv` has 20 run incidents; `scripts/measure_lanes.py` reproduces the saved-log runtime extraction.

## 1. Earlier plans versus current code

### Finding

- **Applied from upgrade v2:** limit/retry detection and hold, reset parsing, AUTH split, 2-strike health, stall alert, doom continuation, stop-now, final-result wait, wind-down harness, last-spawn cutoff, paid-run budget, oracle/nop paid-slot exclusion, and issue/decision cleanup. The implementation log records E1-E6 review at `master_chat_work/20261028_upgrade/APPLY_LOG.md:42-66`. Live anchors: `master_chat_tasks/auto/auto.py:65-104, 1113-1135, 1155-1177, 1228-1281, 1376-1398, 1493-1615, 1876-1923`; `Terminal_2.0_Harbor_Harness/scripts/master_queue.py:75-79, 240-247, 613-623, 641-665, 955-963`; `master_chat_tasks/auto/AUTO_POLICY.md:45-66`. This supersedes most R5 recommendations (`master_chat_work/20261028_upgrade/R5_auto_issues/FINDINGS.md:116-124`). The upgraded Kiro smoke test passed two workers and follow-ups (`auto/runs/20261029T0224_smoke_kiro/REPORT.md:20`), but no later production auto run in the examined `auto/runs/*` folders proves all fixes under a live limit. **UNVERIFIED production efficacy.**
- **Speed plan still open:** `SPEED_PLAN_v1.md:1, 78-86` explicitly says plan only and held. No `dockslot.py` was found in `master_chat_tasks/tools/` (command `rg --files master_chat_tasks/tools | rg 'dockslot'` returned no match); `master_queue.py:249-259, 613-627` has only its own Docker budget and FIFO; `auto.py:1259-1263` checks Docker reachability and PyPI, not a shared lease. The live prompt still uses `/tmp/oracle-qc`, `/tmp/harbor-jobs-qc`, and `/tmp/opencode-logs` (`prompts/templates/P11_full_qc_v3.md:76,79-83`) and the common rule still uses `/tmp` plus sleep polling (`prompts/templates/_COMMON_RULES_v5.md:17,35`). Gate reuse is absent from P11 v3 (`prompts/templates/P11_full_qc_v3.md:82-105`). `SPEED_PLAN_v1.md:28-66` describes these as S1-S4, with Ayush's answers at :78-86.
- **Now wrong or stale in the held plan:** It says policy has a 4-worker hard cap and MQ counts worker oracle/nop against paid concurrency (`SPEED_PLAN_v1.md:67-75`); current policy has 5 workers/2 harness (`AUTO_POLICY.md:45-50`), and MQ excludes gate agents from paid concurrency while still charging Docker resources (`master_queue.py:240-247, 616-623`). It says auto limits need setting to 4/2 (`SPEED_PLAN_v1.md:60-62`); current hard caps are already 5/2 (`auto.py:65-67`), and per-run limits are accepted through `auto.py:543-548`. It proposes notifications and preapproved defaults as new S5 work (`SPEED_PLAN_v1.md:53-59`); LIMIT notifications are already in `auto.py:1531-1583`, but plan-scoped defaults for other Needs-Ayush decisions are still absent from `AUTO_POLICY.md:15-42`.
- **A new bug since the held plan:** `auto.py:498-500` extracts the first digit sequence from arbitrary `Paid runs:` text. The 30 Oct plan quoted `00:40` and auto read cap zero; the master changed the plan to `99` (`auto/runs/20261030T0100_night/REPORT.md:82,114`). This bypasses the policy default six, so a strict parser is higher priority than raising worker counts.

### Recommendation

Keep upgrade E1-E6 as the baseline, then fix `auto.py:498-500` with a full-value parser (`6`, `no cap` only if explicitly allowed), rejecting a quoted time or prose. Test a plan line containing `00:40`, explicit `6`, absent field, and malformed values. Expected gain: prevent refused or unexpectedly unbounded paid runs; risk: old free-form plans that relied on the first number will fail validation. Migrate active plans before enabling. **No new Ayush OK needed for strict numeric parsing; `no cap` policy needs OK.**

## 2. Auto run incidents

### Finding

`INCIDENTS.csv` inventories all nine runs with `REPORT.md`/`events.jsonl` under `auto/runs/` (27-30 Oct), plus the archived 25 Oct night run's `MORNING.md` because it predates the REPORT format. Event counts were computed with the command `python3 -c '...json.loads(each line of each events.jsonl)...'`: nine event files, 308 event lines (6+46+37+60+41+17+10+38+53). The main historical losses were provider retry invisible to the watcher, a 05:00-07:50 all-worker stall, false server-down after one slow check, FINAL before unread worker/harness results, wind-down paid runs bypassing auto.py, and manual stop sequences (`INCIDENTS.csv` evidence column; `R5_auto_issues/FINDINGS.md:53-65`). Most have code fixes; the 2239 stall's root cause remains **UNVERIFIED** (`auto/runs/20261027T2239_overnight/REPORT.md:30,80`). Current open incidents are malformed paid caps and child Docker scripts continuing after a worker stop (`auto/runs/20261030T0100_night/REPORT.md:37-38,82,100-114`). The old 25 Oct AUTH classification is fixed in current MQ/auto (`master_queue.py:75-79`; `auto.py:104,1516-1526`).

### Recommendation

Add an ownership manifest for background gate processes to each worker OUT and have auto record it on stop/resume; do not terminate jobs from a guessed task prefix. Test with a fake detached child and simulated stop that records PID/PGID, command, log, and current state. Expected gain: avoid lost/rescored work after manual interruption; risk: stale PID reuse, so validate process start time and job path before any later action. **Ayush OK needed before any automatic termination behavior.**

## 3. Waiting for master/Ayush decisions

### Finding

The 35% figure is `85.7 h / 245.1 h` over 164 sha-titled worker sessions starting 26-30 Oct; it measures gaps above three minutes before a user message not covered by a tool, not all board time (`master_chat_work/20261030_speed_measure/MEASURE.md:72-100`). `board.json` has `issued`, current `status`, and `updated`, but no running transition timestamp (`master_chat_tasks/board.json#/rows/305` for b223662). The board alone cannot split work from waiting; its spans are affected by late updates (`MEASURE.md:42-69`). **UNVERIFIED issued→running duration for historical rows.**

Largest measured human/master waits, from `opencode_wait_vs_work.csv` sorted by `human_or_master_wait_min` for first messages 26-30 Oct: b223662 cold-chain 1,876.9 min; fuel-card 60e9db0 411.4; pilotage 44635de 410.6; tariff ed621c7 323.5; schema 9111ecc 218.7. The first five total 3,241.1 min, 63.0% of the 5,142 min human wait headline. The 60e9db0/44635de gaps are overnight continuation/adoption, not proved to be a decision wait; classify them **UNVERIFIED** until message-level review (`auto/runs/20261027T0200_night/REPORT.md:49`).

Decision types with verified long waits:

| Type | Measured wait and evidence | Rule boundary |
|---|---|---|
| Crash/timeout cap exception | cold-chain b223662 1,876.9 min, tariff ed621c7 323.5 min; both paused at the 30% rule (`auto/runs/20261029T0355_night/REPORT.md:29-31`, `decisions.jsonl:439-440`); cold-chain answer 30 Oct 11:55 (`decisions.jsonl:544-545`), tariff answer 29 Oct 09:15 (`decisions.jsonl:455`). | Cannot be auto-approved generically: changes a task-quality rule. Preapprove only a named task, numeric ceiling, and evidence condition in Ayush-approved PLAN. |
| Schema cap exception | 9111ecc 218.7 min aggregate, with 60% and then 70%/71.57% decisions (`decisions.jsonl:457-459,464,478-479`). | Same task-specific bound; automatic go only while measured share ≤ written ceiling. |
| Routine design go and QC pass/fail | Policy already allows go/fix/run decisions (`AUTO_POLICY.md:18-29`); 30 Oct warrant go at 02:21 event then build (`auto/runs/20261030T0100_night/events.jsonl:14-15`). | Keep existing table; no extra approval step. |
| Park after NO CORE / novel exception | Slipway and metered waited for Ayush on 30 Oct, `auto/runs/20261030T0100_night/REPORT.md:42-57`. | Never silently park or waive a rule; plan can name a default next experiment, with explicit stop conditions. |

**Proposed exact PLAN rule text:** “For `<slug>` only, when the measured crash+timeout loss share is above the global 30% cap but at most `<N>%`, and all other gate checks pass on the same tree, auto may send the named go and log the measured fraction, source files, and plan line. Above `<N>%`, or if the failure kind is uncertain, stop under Needs Ayush. This rule never applies to another task or changes LEVER_RULES.” For routine go: “If DESIGN READY meets every current stated bar, send go within the next poll; if a bar fails, write the failed measurement and stop.” The latter restates current `AUTO_POLICY.md:18-19` and could remove avoidable master latency without changing authority.

### Recommendation

Add a `Pre-approved defaults:` block to `auto/PLAN_TEMPLATE.md` and parser/report support in `auto.py`, limited to the exact task, measurement, expiry, and tree. Test out-of-range, missing evidence, changed tree, and cross-task attempts. Expected gain: potentially hours in the two recorded cap waits, but the 31.3 h cold-chain wait is an outlier, not a reliable per-run saving. Risk: silently relaxing scoring quality; require Ayush's explicit OK for each cap value and the new mechanism. A notification for any other Needs-Ayush stop would shorten attention delay; LIMIT notification already exists (`auto.py:1531-1583`).

## 4. Docker lane experiment on 30 Oct

### Finding

The reproducible command `python3 master_chat_work/20261030_upgrade2/S6_auto_speed/scripts/measure_lanes.py` reads saved Harbor `Total runtime:` lines; no Docker job was run. Data are warm-image QC/fix gates on 30 Oct, with different bundle revisions and different external load, so the differences below **cannot establish contention causality**.

| Gate | Jobs and measured runtime | Gate wall / limitation |
|---|---|---|
| Nikhil 02c7202 three lanes | lane1 44+36 s, lane2 41+41 s, lane3 42+41 s (`/tmp/opencode-logs/b7c42a8f-6d19-4e35-9f82-5a3c1d7e8042-step10-20261030T163722-c7df/lane{1,2,3}.log:17,52`); all rewards valid (`QC/reports/b7c42a8f-6d19-4e35-9f82-5a3c1d7e8042/v1.md:566-585`). | First lane began 16:40:30, ALL_DONE 16:44:18 = 3m48s including launch stagger (`lane1.log:1`, `runs.log:1`). **UNVERIFIED solo baseline for same bytes**, so no slowdown estimate. |
| Warrant earlier gate with mostly serial chain | 3 oracle runtimes 1,349/1,361/1,424 s; stub 240 s; owner 1,428 s (`/tmp/opencode-logs/warrant-asof-entitlement-compiler-step10-20261030T140824-f6b3/runs.log:17,43,71,102,129`). | 14:18:51→15:40:53 = 82m02s (`runs.log:1,140`). Oracle-3 overlapped later jobs (`runs.log:86,112-113`), so this is **not a pure serial baseline**. |
| Warrant fix d872b22 three lanes | oracle 1,683/1,688/1,683 s, nop 269 s, owner 1,486 s (`master_chat_work/20261029_warrant-asof-entitlement-compiler/p12_fix_v2_d872b22/RECHECK_FIX.md:110-119`). | Oracle average 1,685 s, +22.3% versus the earlier gate's 1,378 s; changed bytes and job mix prevent attribution to contention. |
| Warrant QC v3 three lanes | oracle 1,853/1,834/1,841 s; nop 289 s; stub 265 s; owner 1,373 s (`/tmp/opencode-logs/warrant-asof-entitlement-compiler-step10-20261030T174955-6298/lane{1,2,3}.log:16,42`; `QC/reports/warrant-asof-entitlement-compiler/v3.md:346-349`). | Oracle mean 1,842.7 s, +33.7% versus earlier 1,378 s. v3 report says all jobs full, none reused; the per-run slowdown is an observation, **INFERRED cause unknown**. |
| Cold-chain QC c75ddad | Six sequential runtimes 791/774/803/819/838/1,020 s (`/tmp/opencode-logs/cold-chain-backbone-quote-step10-20261030T152505-b234/runs.log:17,45,73,101,129,157`); 15:25:27→16:50:04 = 84m37s (`runs.log:1,167`). | The report explicitly says “strictly sequential” (`QC/reports/cold-chain-backbone-quote/v5.md:91-94`). The premise that this particular QC used parallel lanes is wrong. v4 used earlier bytes and was much faster (`v4.md:318-328`), so it is not a same-bytes contention baseline. |

The warrant v3 3-lane gate saved roughly 16 minutes versus the earlier 82-minute gate **only if** the v3 report's 17:52 launch and 18:58 log close describe the same gate (`v3.md:141,346-349`; `/tmp/opencode-logs/.../runs.log` ends only `ALL_DONE`, without a timestamp). Treat that wall saving as **INFERRED approximate**. The per-oracle slowdown is 22-34% across two later parallel gates, larger than the held plan's 0-18% 1-3-container observation (`SPEED_PLAN_v1.md:16-20`; `MEASURE.md:181-188`), but task bytes and host load changed. A controlled same-tree one-lane versus three-lane comparison is needed before a 4-lane default.

### Recommendation

Adopt up to three lanes first, with a same-tree benchmark recording process start/end, trial phase times, host load, Docker stats, and reward equality; allow four only if the measured median oracle slowdown is ≤25% and no OOM/timeout. This follows Ayush's earlier answer (`SPEED_PLAN_v1.md:80-86`), so no new OK for the benchmark; enabling the production default belongs to the later approved build. Risk: Docker memory contention and image races. Warm once and charge declared task resources to a shared slot budget (`SPEED_PLAN_v1.md:22-39`).

## 5. Ranked proposed changes (expected time saved × safety)

| Rank | Change / file | Proof before enablement | Expected gain | Risk to current behavior / Ayush OK |
|---|---|---|---|---|
| 1 | Strict `Paid runs:` value, `auto/auto.py:498-500`, `auto/PLAN_TEMPLATE.md` | unit cases `6`, blank, `00:40`, malformed prose, cap exhaustion; smoke `status` | avoids refused starts and accidental cap bypass | Old free text rejected; no OK for numeric parsing; **OK for `no cap` semantics** |
| 2 | Shared Docker lease and budget, new `tools/dockslot.py`, MQ `master_queue.py:613-627`, auto status and worker rules | two-acquirer and dead-lease tests; simulated 8 GiB+4 GiB contention; dry run | targets 55.5 h poll time/164 sessions (`MEASURE.md:72-100`), upper bound only | wrong accounting could overcommit or starve; **OK already recorded for plan, build still held** |
| 3 | Three QC/fix lanes with warm image, P11 template and P12 fix prompt | same-tree 1/3/4-lane timed gate, identical rewards, no OOM | potential ~16 min on warrant; not a measured general saving | concurrent load raises long-job runtime; **OK up to 4 conditional on benchmark** |
| 4 | Same-tree Step 10 reuse on P11 recheck only, P11 v3 recheck block and result schema | tree hash equality + saved complete oracle/owner/nop/stub results; spot oracle x1+nop; changed byte forces full | 18/24 rechecks ran full Step 10 (`MEASURE.md:193-202`), 10-68 min each possible | stale or incomplete gate accepted; **OK given 30 Oct 14:15** (`SPEED_PLAN_v1.md:79-85`) |
| 5 | Stable gate/log path under `~/tb_runs/<date>/`, P11 template, common rule, MQ log path | reboot-survival check using a new test directory; paths in result manifest | avoids lost blind/gate work (77/80 referenced `/tmp` paths absent after reboot, `MEASURE.md:208-216`) | old prompts point to `/tmp`; **OK given 30 Oct 14:15** |
| 6 | Exact plan-scoped preapproved decisions, PLAN_TEMPLATE, AUTO_POLICY, auto report | cross-task/expired/changed-tree rejection tests | could remove a large cap wait, but 31.3 h is an outlier | rule drift affects task quality; **requires Ayush OK for each exception** |
| 7 | Need-Ayush notification and background-job manifest, auto.py | fake notification and stop/resume with detached job | reduces attention delay, avoids rescoring | notification noise; PID identity; notification already OK in held plan, **OK for automated job termination** |
| 8 | Own-container cleanup by run IDs/labels, MQ `remove_containers` at :272-310 | two same-task fake sessions; cancel one leaves other untouched | prevents interference, time saved unmeasured | changing kill path could leave stale containers; **OK before deployment of automatic cleanup** |

Do not implement a blanket 4-worker/2-harness setting from the old speed plan: current caps and budget already exist (`auto.py:65-92`; `AUTO_POLICY.md:45-59`). Docker admission and the paid subscription budget are separate constraints. Keep MQ FIFO until backfill can prove a waiting small job never delays a reserved paid run (`master_queue.py:613-627`); changing queue order risks surprise spend.
