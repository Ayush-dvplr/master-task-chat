# Fast-track plan v1: faster new tasks (31 Oct 2026, ~00:50 IST)

Status: PLAN ONLY. Nothing changed yet. Covers the five items Ayush picked: D6, D2-D3, A5+F2, F3, D4 (from [UPGRADE2_PLAN_DRAFT_v1.md](UPGRADE2_PLAN_DRAFT_v1.md)), plus D1 and D5 because two of them depend on those. It lifts the HOLD on [SPEED_PLAN_v1.md](../20261030_speed_measure/SPEED_PLAN_v1.md) for these items only. Every other upgrade 2 item stays in the draft plan.

## 1. What is true today (checked in code and files)

| Item | Today | Evidence |
|---|---|---|
| D6 pre-approved limits | **Missing.** The plan template has only Paid runs / Workers / Budget / Wind-down / Last spawn. Anything outside the policy table stops as Needs Ayush. Outside auto mode the master never starts a paid run (your rule). `auto.py` has a `notify()` popup, but only the usage-limit code calls it. There is no command for "Needs Ayush". | `auto/PLAN_TEMPLATE.md` (19 lines); `AUTO_POLICY.md:31`; `auto.py:1530`; auto.py subcommands |
| D1 paid-run parser | **Bug.** It reads the first number in the line, so a quoted `00:40` gave a cap of 0. D6 adds more plan lines, so this must be fixed first. | `auto.py:498-500` |
| D2 shared Docker slots | **Missing.** The harness queue has its own budget and can't see workers' Docker jobs. Workers wait by eye (`sleep 200; docker ps`). | `master_queue.py:229-259, 612-628`; `_COMMON_RULES_v5.md:35, 50` |
| D3 parallel lanes | **Partly.** 3 lanes have been used in issued QC prompts since 30 Oct 16:50, but the template `P11_full_qc_v3.md:35` still says one serial chain. 4 lanes are untested. | issued QC prompt line 80; template |
| A5 prompt checks | **Partly.** `issue.py` refuses on time box, round limits and missing `<SHA>` only. It has no content check, so the cold-chain 12:00 go (a target the allowed edits could not reach) went out. | `tools/issue.py:77-144` |
| F2 fix receipts | **Missing.** The fix template has no before/after receipt or re-scan list. Fixes that broke something else: judge overlap 30 of 58 reports, test edits 26/58, stale text 20/58. | `P12_recheck_fix_v4.md`; S4 FIX_MAP |
| F3 design blind first | **Already mostly built** (P2 build v5): design and kill test → DESIGN READY → prototype → DESIGN BLIND READY → one blind → NO CORE stop. Outage died this way 1 h 52 min after start (02:45 → 04:37). The 7 slow parked builds came before or outside this step. Gap: the kill table has no "split the problem into independent parts" solver (the outage miss), and the harden template has no design blind. | `P2_build_v5.md:59-75`; decisions 30 Oct |
| D4 gate reuse | **Missing.** 18 of 24 rechecks re-ran the full Docker gate, sometimes on bytes the fix had just tested. Fix-session gate results sit in `/tmp`, so reuse first needs D5. | MEASURE.md:193-202 |
| D5 durable work folders | **Missing.** The 30 Oct reboot wiped 77 of 80 `/tmp` paths, including the 3 warrant blinds. | MEASURE.md; S6 |

**What QC fails on most** (all 95 QC reports, 17 tasks; the number is how many tasks had a ❌ for that check):
- AL-27 "the test never actually triggers the rule": 13
- DS-22 "solution and `TRUTH.md` don't match": 13
- AL-2 "promised but not graded": 12
- TS-19: 12
- CL-2 forgery price: 12
- AL-1 "graded but not promised": 11
- AL-18 stale numbers or paths: 11
- CL-4 "one wrong fact costs everything": 11
- JD-18 code-quality criterion: 11
- CL-10: 11
- JD-7 "judge disagrees with solution": 10
- DS-27 `TRUTH.md` narrates how the task was made: 10
- AL-4: 10

## 2. Correction to my earlier number

I said test runs would go "from about 2 h to about 45 min". The measured data does not support that for heavy tasks:
- Warrant's gate went from 82 to about 66 min with 3 lanes. Each oracle run got 22-34% slower when sharing Docker.
- Cold-chain ran its 6 jobs one at a time in 85 min. 3 lanes would make that about 35-45 min (estimate).
- Light tasks already take minutes.

So lanes save roughly 15-45 min per gate. The bigger wins are D4, which skips the repeat gate entirely (25-60 min per recheck on heavy tasks), and D6 (hours of waiting).

## 3. What gets built (order, check, undo)

| Step | What | Who | Check before switching on | Undo |
|---|---|---|---|---|
| 1 | **D1** strict `Paid runs:` value: a whole number or the one allowed phrase. A time or text in the field is refused. | worker (code + tests) | unit cases `6`, empty, `00:40`, text, allowed phrase | backup file |
| 2 | **D6** `Pre-approved:` block in `PLAN_TEMPLATE.md` + `AUTO_POLICY.md`. Each line names: task, what may be decided, the limit, the frozen tree, and the end time. The master applies only exact matches and logs `pre-approved: <line>` in decisions.jsonl and REPORT. Anything else still stops. New `auto.py notify "<text>"` command; the master calls it on every Needs-Ayush stop, in and outside auto mode. | master (text) + worker (notify) | 4 refusal cases (other task, expired, changed tree, over the limit) | remove block |
| 3 | **A5** content checks in `issue.py` before a prompt is written: (a) every target is reachable with the allowed edits (the cold-chain case); (b) one oracle count; (c) every path named exists; (d) no `[[ ]]` or `<SHA>` left; (e) gate numbers match the current gate and the task's exceptions. On a hit it refuses, or warns with `--force-lint "<reason>"` logged. | worker | replay the past bad prompts (each caught); the last 10 good prompts pass | `--no-lint` |
| 4 | **F2** fix receipt in `P12_recheck_fix_v4` (becomes v5): before/after tree sha; each changed check with old→new weight; oracle and agent-program score before/after; a re-scan after every edit for the 4 "fix broke it" families (stale text AL-18/DS-22/DS-27, judge overlap JD-14/AL-28, promises AL-1/AL-2, rule triggered AL-27). | master (template) | next real fix uses it | v4 stays |
| 5 | **F3** gap fill: P2 v5 and P9 v4 kill tables must include (a) a "split into independent parts, solve each exactly" solver and (b) the strongest plain exact solver. P9 gets the same design-blind stop when it adds a new lever. | master (template) | diff review | snapshots |
| 6 | **Pre-QC fresh-eyes check** (only if Q6 = yes): one cheap read-only session reads the finished bundle against the kit wording of the 13 most common failures above and lists hits. The builder fixes them before the full QC. | master issues; codex read-only or opencode | first 2 builds: compare its hits with the real QC findings | skip step |
| 7 | **D5** all gate, blind and log folders move from `/tmp` to `~/tb_runs/<date>/` (rule and prompt text plus the harness queue log path). | worker + master | a test folder survives a reboot | old paths |
| 8 | **D2** `tools/dockslot.py` (acquire / release / status; shared lock file; dead jobs free their slot). It waits on Docker "container ended" events, so a worker makes one call instead of dozens of sleep polls. Charge per job = your 30 Oct answer (measured peak +50%, else task.toml memory). Paid runs and the harden measuring step go first. The harness queue and `auto.py status` use it; the worker rule text "max 2 Docker-heavy, wait by eye" becomes "use dockslot". | worker (code + tests) | two-takers test, dead-job test, 8 GiB + 4 GiB squeeze test, dry run next to a real paid run | rules fall back to today's text |
| 9 | **D3** 3 lanes written into the QC and fix templates. Then a benchmark when Docker is empty: the same task at 1/3/4 lanes. 4 lanes only if each oracle slows ≤25% with no crash and identical rewards (your 30 Oct rule). | worker (benchmark) + master (templates) | benchmark table | 3 lanes |
| 10 | **D4** in the P11 recheck only (never full QC): if the tree sha equals the fix session's tested tree and its saved results are complete (oracle ×3, nop, stub, owner in `~/tb_runs`), Step 10 runs only oracle ×1 + nop as a spot check and writes `step10: reused <tree sha>`. Any changed byte means a full gate. | master (template) + worker (result field) | a changed byte forces the full gate (fixture) | remove block |
| 11 | Verify session (fresh eyes): plan vs code vs tests, all 3 test suites green, one small smoke auto run, then switch on. | worker | VERIFY PASS | old files |

**Effort:**
- Steps 2 (text part), 4 and 5 are text edits I can make in about 1 hour.
- Steps 1, 2 (notify), 3, 7, 8 and 10 are code for one worker session, about 3-5 h, which can run during a normal auto run without touching any task.
- Step 9 needs about 1 h with Docker empty.
- Step 11 takes about 1 h.

**Doesn't change:**
- the gate rules
- QC kit rules
- the oracle count rule
- the usage-limit logic
- harness paid-run order
- tree sha checks
- what workers may run in Docker

**Expected result** (my estimate from the outage timeline, not measured): a new task goes from about 12 h to about 6-7 h. The gain comes from:
- removing the 2 waits (≈5 h) where a pre-approval covers them;
- skipping one repeat gate (25-60 min);
- gates 15-45 min shorter;
- some fix rounds avoided.

## 4. Ayush's answers (31 Oct ~00:55 IST)

1. Auto may decide alone, only on an exact plan line: **time-out share** up to the % written for that task; **no core -> park** and move on; **QC minor/warning -> note for QL** (already policy). NOT allowed: "slightly above gate -> harden once" (still Needs Ayush).
2. Default time-out share when a plan names no %: **30% (current rule)**. Higher only by a task line in the plan.
3. Outside auto mode, after QC PASS and freeze, the master **may start the paid run itself within the day's cap** (tell Ayush, log it). Takes effect when this plan is switched on.
4. Alert: **Mac popup + sound** on every Needs-Ayush stop.
5. Pre-QC fresh-eyes check (step 6): **yes, with codex read-only**.
6. Paid-run field: **exact `no cap` allowed**; anything else a whole number, default 6.
7. 30 Oct speed answers **still hold** (peak memory +50% else task.toml; reuse only in rechecks; 4 lanes only if <=25% slowdown; work out of /tmp).
8. **Verify the plan first** (fresh session), then build on Ayush's word.
