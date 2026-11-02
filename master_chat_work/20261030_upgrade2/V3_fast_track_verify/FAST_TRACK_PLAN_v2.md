# Fast-track plan v2: faster new tasks — verified before build

Status: PLAN ONLY. Nothing in the pipeline has been changed by V3. This plan covers D6, D2–D3, A5+F2, F3, D4, and their prerequisites D1/D5. It lifts the speed-plan HOLD for these items only after Ayush says proceed. The rest of Upgrade 2 remains in `UPGRADE2_PLAN_DRAFT_v1.md`. Do not switch on a change until its stated gate passes. Preserve current QC quality, paid-run order, LIMIT handling, tree refusals and worker permissions.

## 1. Today, as verified

- Auto `PLAN_TEMPLATE.md:3-8` has five fields and no pre-approved decision block; `auto.py:96,484-500` parses those fields. AUTO_POLICY applies only while auto runs (`AUTO_POLICY.md:3`). An out-of-table decision stops (`:31`). The existing `notify()` is a popup without sound and is called for LIMIT and master hold, not every Needs-Ayush stop (`auto.py:1530-1537,1578,1790`). No notify CLI exists (`:1996-2043`). Manual paid-run authority begins with Ayush's answer in section 4 below.
- `Paid runs:` currently accepts the first digit sequence, so `00:40` becomes 0 (`auto.py:498-500`). The default is 6 (`:92`).
- No shared dockslot exists. MQ already sees external `harbor run` process groups, including oracle/nop, and charges default resources, but cannot account for arbitrary worker `docker run` jobs (`master_queue.py:229-259,616-627`). Current paid queue is FIFO and locked with `flock` (`:147-164,625-628`).
- P11 template Step 10 is a serial nohup chain (`P11_full_qc_v3.md:89-91`); some 30 Oct issued prompts/logs used three lanes (`S6_auto_speed/FINDINGS.md:61-79`). Four lanes are unbenchmarked.
- `issue.py:77-109,142-149` enforces stage/round/time-box and placeholders, with no semantic content lint.
- P12 already has G1–G7 guards, touched-rule table, vacuity, side-effect and trap checks (`P12_recheck_fix_v4.md:55-73`); it lacks the structured receipt described below.
- P2 v5 already has design and blind stops and a generic kill table (`P2_build_v5.md:56-75`). P9 v4 has no design blind when adding a core lever (`P9_harden_from_results_v4.md:42-63`).
- 18/24 QC rechecks in the 26–30 Oct study ran full Step 10 (`MEASURE.md:191-194`). P12 saves scalar gate results in OUT but raw jobs can remain in `/tmp`, and P12 does not require stub (`P12_recheck_fix_v4.md:67,73`; warrant `RECHECK_FIX.md:108-122`).
- Host logs, QC copies/jobs, blind copies and some tool work use `/tmp` (`_COMMON_RULES_v5.md:17`; P11 `:49,79-85`; P13 `:7`; `master_queue.py:54`; `repackage_one.py:86`). The 30 Oct study found 77/80 referenced `/tmp` paths absent after reboot (`MEASURE.md:208-216`).

The recomputed QC report-mention table is AL-27 13, DS-22 13, AL-2 12, TS-19 12, CL-2 12, AL-1 11, AL-18 11, CL-4 11, JD-18 11, CL-10 11, JD-7 10, DS-27 10, AL-4 10 tasks. Method and limits are in `V3_fast_track_verify/scripts/count_qc_failures.py` and `VERIFY_REPORT.md` section 1.

## 2. Evidence-based expectations

The 30 Oct saved logs show warrant's earlier mostly serial gate wall 82m02s and a later three-lane gate around 66 min; the two used different bytes/load, and later oracle runs were slower. Cold-chain's six sequential jobs took 84m37s. Nikhil's light three-lane gate had 80–83 seconds of jobs per lane and no solo baseline (`S6_auto_speed/scripts/measure_lanes.py`; `S6_auto_speed/FINDINGS.md:61-79`). Therefore **15–45 min per gate is a hypothesis**, not a measured typical gain. A same-tree empty-Docker 1/3/4-lane benchmark is required.

The study found 18/24 rechecks ran a full gate; one proved identical-tree outage repeat cost ~10 minutes, while a potential warrant repeat would have cost 62–68 minutes but was not run (`MEASURE.md:191-194`). Thus **25–60 min per recheck is an opportunity range, not a measured saving**, and it applies only to eligible saved complete gates. The **12 h → 6–7 h** new-task prediction is unverified; waits in one outage timeline and aggregate overlapping session-hours do not establish a per-task median (`MEASURE.md:72-108`). Measure a pilot cohort with task wall time, active worker time, gate time, human wait, poll time, token fields, corrections and QC/gate outcomes before quoting a result.

## 3. Build sequence, gates and rollback

### Step 0 — Snapshot and baseline

Record hashes of live policy, auto.py, MQ, issue.py, active templates, common rules, live QC kit and tool tests; copy rollback versions into the upgrade work folder. Save the current run and queue state read-only. Update `prompts/templates/CHANGELOG.md` and rule fingerprints when each approved template changes. The V3 sandbox baseline is incomplete: `auto/tests` 73 run/24 socket errors, `tools/tests` 30 run/3 stale-fixture failures, harness unittest 0 collected because tests are pytest-style (`VERIFY_REPORT.md` section 4). Before enabling, fix fixture drift and run auto/tools unittest plus harness pytest in the real host environment; require green suites. Do not rewrite live state as part of a test.

### Step 1 — D1 strict paid-run field

In `auto/auto.py`, parse the complete `Paid runs:` value as one nonnegative whole number or exact `no cap`; absent field means 6. Reject whitespace/prose/time like `00:40`, duplicate `Paid runs:` lines, negative and malformed values at plan start/status/harness use. Update `auto/PLAN_TEMPLATE.md` so examples are exact values, not `6 (explanation)`. Audit/migrate any active free-form plans before switching. A `no cap` plan is still bounded by the other paid-run and subscription gates. Tests: `6`, empty, `0`, `00:40`, `7 today`, `no cap`, duplicate, exhaustion and status formatting. Rollback: restore parser/template snapshot between runs; do not alter a live plan silently.

### Step 2 — D6 exact pre-approval, alerts and manual paid run

Add a `Pre-approved:` block to the plan template, parsed as typed records with stable line ID/hash: task slug; one action (`timeout_share`, `no_core_park`, `qc_minor_warning_ql`); optional numerical ceiling; expected frozen tree SHA where a tree exists; evidence source; expiry time. An exact task line can raise the timeout share above the current 30% default for that task only. A missing percentage means **30%**. A line can authorize “NO CORE → park and move on”; a QC minor/warning line can authorize note for QL while preserving the QC verdict. It never authorizes “slightly above gate → harden once.” `AUTO_POLICY.md` must state these narrow plan overrides and still make unlisted cases Needs Ayush. Freeze/expiry/measurement checks occur immediately before the decision; fail closed for missing, duplicate, expired, changed-tree, cross-task, ambiguous failure kind, missing data or over-ceiling cases.

The master reads the exact plan line, checks the typed evidence, calls `tools/decide.py --by 'master (auto)' --slug ... --what 'pre-approved: <line ID/hash>; measured ...' --words '<exact plan line>'`, and writes the same ID and evidence into REPORT. The current `decide.py` fields are `by/slug/what/words` (`tools/decide.py:35-65`). Add `auto.py notify '<text>'` with macOS popup **and sound** (mockable), and require the master to call it at every Needs-Ayush stop, including outside auto. The watcher may notify automatically when it can identify a stop; deduplicate by decision ID. No notification sends a message to another person.

For manual mode, implement one master-only paid-run preflight/entry command (or guarded wrapper around MQ add) that proves: current QC report verdict PASS; the exact bundle matches its recorded freeze tree sha via `intake.tree_sha`; no outstanding kit Step 10 obligation; daily cap including queued and started runs; no LIMIT; ≤2 busy workers at launch and ≤3 while running; harness max; MQ FIFO and pause. It tells Ayush and logs the queue decision before launching. Refuse if any proof is missing. Do not reuse a paid result. Tests: 4 refusal scopes, duplicate plan lines, default 30%, “above gate harden” refusal, manual QC/freeze/cap/LIMIT refusals, popup+sound and logging. Rollback: remove new plan records and guarded command, restore policy snapshot; leave decisions already logged.

### Step 3 — A5 prompt lint with replay

Extend `tools/issue.py` with a deterministic lint result before it writes board/pending/prompt. Hard-refuse unresolved `[[...]]`/`<SHA>` after substitution, malformed Board ID, invalid active input paths, gate values that contradict current gate/task exceptions, and a conflicting oracle count in a QC/fix prompt. Distinguish existing input paths from future OUT/jobs and container `/app` paths. For semantic reachability, require a short numeric attestation in the draft: current tests/rubric, target, permitted edits, maximum plausible change and arithmetic. Flag contradictions for master review; a text linter cannot prove a target reachable. Allow `--force-lint '<reason>'` only for a warning, log it in decisions and the issued prompt; no production `--no-lint` bypass. Replay cold-chain 12:00 go, schema “oracle once” note and Nikhil data scope; ensure the latest ten issued prompts are not falsely refused. Store replay inputs/expected diagnostics as fixtures. Risk: overzealous lint blocks valid work; keep warnings separate from hard syntax errors. Rollback: switch off new lint with logged operator reason while keeping existing cap checks.

### Step 4 — F2 fix receipt and F3 design gap

Update P12 v4 → v5 without removing G1–G7: structured before/after tree sha; changed check/criterion IDs and old→new weights; oracle, owner, nop, stub and saved agent-program scores before/after when run; verifier budget; changed-file list and doc/solution/judge/test consistency scan. Re-scan the four known regression families after each edit: stale text/solution (AL-18/DS-22/DS-27), overlap (JD-14/AL-28), promises (AL-1/AL-2), branch trigger (AL-27). Report “not run” explicitly and why. Reprocess the 11 FIX_MAP rows as a review, not an assertion of causality (`S4_task_study/FINDINGS.md:36-41`).

Update P2 v5 and P9 v4 kill tables to name (1) decomposition into independent exact subproblems and (2) strongest plain exact solver, alongside existing generic/first-write solvers. P9 gets a DESIGN BLIND READY stop only when it adds a new core/lever; a normal QC-safe hardening fix follows its current route. Keep WRONG/TIMEOUT/CRASH split and the current Law-1 filter. Compare diffs to live QC kit; pilot on two builds and measure extra elapsed time, blind miss and later QC findings. Rollback: restore versioned template snapshots; never weaken a current QC rule.

### Step 5 — Pre-QC fresh-eyes Codex pilot

Ayush answered yes. A cheap read-only Codex review reads the finished bundle and current QC kit, checks the 13 most mentioned ❌ IDs as a *screen*, writes only to its OUT, and sends hits to the builder before full QC. It does not decide QC, edit task bytes or replace P11. First test Codex path confinement with a disposable copied bundle: host hashes before/after, OUT writable, bundle read-only, no unintended writes. S7 says the exact `codex exec -s read-only -o OUT` behavior is unverified (`S7_cli_workers/FINDINGS.md:10-18`). Compare findings with the next two real full QCs; measure extra tokens/time and false positives. If confinement fails or no useful hits, skip the precheck without weakening full QC.

### Step 6 — D5 durable host work roots

Inventory all active `/tmp` host paths and migrate QC gate copies/jobs/logs, P13 blind copies, P16/P17 scratch, common rules, P9/P12 directions, MQ host log root and `repackage_one.py` work to `~/tb_runs/<date>/<slug>/<step>/<unique-id>/`. Preserve historical prompt versions unchanged. Do **not** change container `HOME=/tmp` (`master_queue.py:62`). Add a narrow `~/tb_runs/**` allowance in `auto.py:135-141` while preserving all Harbor/auto/queue denies. Verify Docker Desktop can bind-mount this root before switch; `settings-store.json` did not expose file-sharing directories in V3, so this is still UNVERIFIED. Test create/read/copy/hash/cleanup behavior and reboot survival of one test folder. Never prune Docker images or pass Harbor `--delete`; keep logs and jobs per retention policy. Rollback to previous paths only between runs; preserve all newly created artifacts and pointers.

### Step 7 — D2 dockslot, then D3 lanes

Implement `tools/dockslot.py acquire/release/status` with its own `fcntl.flock` state, unique lease ID, owner PID/PGID and start time, job/run identity, heartbeat, expiry and recorded resource charge. Avoid lock-order deadlock with MQ's state lock. A dead wrapper does not prove its container died; reconcile container identity before releasing, and fail closed on uncertainty. Use `docker events` as a wake-up hint with a timed status fallback; `docker events --help` alone did not prove daemon delivery, and V3 `docker info` lacked socket permission. Persist peak memory measured from the task's own sampled Docker stats (task/phase/tree/window) and charge **peak ×1.5 when valid; else task.toml memory**, per Ayush. Show provenance in status. Respect Docker VM CPU/RAM budget with 3 GiB headroom. MQ retains existing external Harbor process accounting, FIFO, flock, auto-resume and paid concurrency, avoiding double charge when a run has a lease. Paid runs and harden measurement have admission priority **without changing paid FIFO**; do not implement opportunistic queue backfill in this fast track. Worker direct Docker jobs acquire the same lease; keep WORKER_PERMISSION allowlist and never allow paid Harbor agents.

Tests: two takers, dead wrapper with live container, PID reuse, stale heartbeat, daemon restart, event unavailable fallback, 8+4 GiB squeeze, double-counting, FIFO/usage-limit resume, same-task separate owners, and dry run beside a real paid run. Switch on dockslot in one small task first. Only then edit P11/P12 to three lanes and warm image once. Benchmark on empty Docker, same frozen task/tree and same tools at 1/3/4 lanes, recording wall, per-oracle runtime, reward equality, crashes/OOM and host load. Four lanes only if median oracle slowdown ≤25% against solo, no crash/OOM/timeout and identical rewards; otherwise three. If three lanes regresses quality or wall, use serial. Rollback: restore rule/queue snapshots between runs; preserve lease evidence.

### Step 8 — D4 recheck-only gate reuse

After D5 saves raw jobs, have P12 write a durable, immutable gate manifest: exact tree sha using `intake.tree_sha`, kit/tool versions, exe_copy output and allowed diffs, per-trial paths and hashes, exit/exception status, rewards and reward-details, ALL_DONE, three oracle 1.000, nop 0.000, owner 1.000, stub judgment and any new kit-required run. If P12 skipped Docker, a run failed, stub is missing, any file moved or any byte changed, reuse refuses and P11 runs its ordinary gate. The QC recheck independently recomputes the tree and checks manifest completeness, then runs oracle x1 + nop as Ayush chose, compares rewards, and records `step10: reused <tree sha>` with source/spot paths and the explicit kit-exception status. **MODE full always does complete Step 10 and never reuses.** A paid run is never reused. Before a paid run, resolve the kit x5 readiness question in `QUESTIONS.md`; until resolved, the manual preflight requires a kit-complete x5 round (P11 template `:89-90`; kit `Final_checklist.md:354-367,390`). Tests: changed byte, absent stub, absent result, exception, wrong reward, changed kit/copy recipe, and spot mismatch all force full gate. Rollback: remove reuse branch, keep manifest for audit.

### Step 9 — Release gate and measurement

Run updated auto/tools unittest and harness pytest in a host environment that permits loopback and test fakes; all green. Review policy/template/kit diffs, CHANGELOG and rule hashes. Do one small auto smoke without a paid run, then one supervised real task with manual/auto preflight and dockslot, no overlapping uncontrolled Docker jobs. Verify LIMIT, MAX_BUSY_AT_LAUNCH 2, MAX_BUSY_WITH_RUN 3, MQ FIFO/flock/resume, tree refusals, worker permissions, no prune/Harbor `--delete`, and QC kit sign-off. Switch on between active runs only. Track a matched pilot set; do not claim the 12→6–7 h target until measured without worse QC or gate outcomes. If any regression, turn off the affected feature only, restore its snapshot between runs and keep all result logs.

## 4. Ayush's answers (unchanged from v1; binding)

1. Auto may decide alone, only on an exact plan line: **time-out share** up to the % written for that task; **no core -> park** and move on; **QC minor/warning -> note for QL** (already policy). NOT allowed: "slightly above gate -> harden once" (still Needs Ayush).
2. Default time-out share when a plan names no %: **30% (current rule)**. Higher only by a task line in the plan.
3. Outside auto mode, after QC PASS and freeze, the master **may start the paid run itself within the day's cap** (tell Ayush, log it). Takes effect when this plan is switched on.
4. Alert: **Mac popup + sound** on every Needs-Ayush stop.
5. Pre-QC fresh-eyes check (step 6): **yes, with codex read-only**.
6. Paid-run field: **exact `no cap` allowed**; anything else a whole number, default 6.
7. 30 Oct speed answers **still hold** (peak memory +50% else task.toml; reuse only in rechecks; 4 lanes only if <=25% slowdown; work out of /tmp).
8. **Verify the plan first** (fresh session), then build on Ayush's word.

## Changes from v1

1. Corrected MQ visibility: it already detects external Harbor oracle/nop; dockslot must cover arbitrary Docker and avoid double charging (`master_queue.py:229-247,616-627`).
2. Corrected notifications: master-hold already triggers popup, but sound and general Needs-Ayush command are absent (`auto.py:1530-1537,1785-1790`).
3. Added manual paid-run QC/freeze/cap/LIMIT preflight because section 4 grants new outside-auto authority (`AUTO_POLICY.md:3,26,51-53`).
4. Made `Paid runs:` exact and required active-plan migration; current template prose and first-number parsing conflict (`PLAN_TEMPLATE.md:4`; `auto.py:498-500`).
5. Narrowed A5 from impossible static “target reachable” proof to arithmetic attestation plus mechanical lint; added path categories and recent-prompt false-positive replay (`issue.py:142-149`; cold-chain go `:5-9`).
6. Kept P12's current guards and added only missing receipt fields; S4 family counts are inferred mentions (`P12_recheck_fix_v4.md:59-73`; S4 `FINDINGS.md:36-41`).
7. Limited F3 extra blind to a new P9 core/lever, while preserving P2's existing generic solver kill table (`P2_build_v5.md:66-75`).
8. Made D5 include P13/P16/P17, repackage, worker permission, Docker mount proof and container `/tmp` exception (`VERIFY_REPORT.md` section 5).
9. Made D2 fail closed on uncertain dead leases, preserve FIFO/flock/resume and use events only as a hint; live Docker event delivery was unavailable for verification (`VERIFY_REPORT.md` section 5).
10. Required a durable complete manifest and stub for D4; current P12 records only scalar rewards and may skip Docker (`P12_recheck_fix_v4.md:67,73`).
11. Exposed the QC kit x5 versus x3+spot conflict and kept full kit readiness before paid launch until Ayush answers the narrow question (`Final_checklist.md:354-367,390`; P11 `:89-90`).
12. Replaced unverified 15–45 min, 25–60 min and 12→6–7 h promises with measured pilot gates (`VERIFY_REPORT.md` section 2).
13. Added fixture repair, harness pytest, snapshots, rule hashes, CHANGELOG and rollback to the release gate (`VERIFY_REPORT.md` sections 4 and 6).
