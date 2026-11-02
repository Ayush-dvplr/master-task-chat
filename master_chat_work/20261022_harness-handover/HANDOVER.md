# Harness chat handover (22 Oct 2026, 13:20 IST)

This was written by the harness-run chat, the "master harness run" session. Everything here was checked on disk or with live commands at 13:16–13:20 IST unless it is marked FROM MEMORY or UNSURE. The same facts, in machine-readable form, are in `handover.json` in this folder.

## 1. Role

**What this chat does:**
- Runs harness trajectories (Harbor) on the Kiro route.
- Queues tasks through its own queue runner and records every attempt and score.
- Diagnoses failed runs.
- Fixes nothing in the bundles it runs.

On 21 Oct I also checked by hand, outside the harness, why vendor-archive and emberforge failed their tests. I re-ran the agent's delivered code against the bundle's own `test_output.py` in a plain `python:3.12-slim` container.

**What it never does:**
- Edit the operator's bundles (they are copied unchanged into `Tasks_INPUT/`).
- Edit tracked harness files.
- `git push`, `commit`, `merge` or open a PR in the harness repo (ground rule 13).
- Pull unless the operator asks.
- Run the PL QC, the v0 QC or `exe_copy`. The 21 Oct "v0 QC + P3" request was dropped by the operator: "take the task names and path only of 4 tasks ... ignore rest".
- Resend Odoo records.
- Set `ANUBIS_SUBSCRIPTION_ID`.

## 2. Paths

### Harness clone

- **Path:** `/Users/mac/Desktop/Terminal Bench/Harbor_Harness/Terminal_2.0_Harbor_Harness`
- **Branch:** `kiro-bridge`. HEAD is `b1ffb283ec0956586111918ad4b71d870f489013` (19 Oct 18:12, "Stop tracking generated .kiro/agents session configs").
- **Local refs:** the local `origin/kiro-bridge` is also `b1ffb283` (last fetch 2026-10-20 19:10), and the local `origin/main` is `9b8229f6`.
- **Remote now:** `git ls-remote --heads origin` (13:17) lists only `refs/heads/main` = `a74bda85…`. There is no `kiro-bridge` head on the remote, and `a74bda85` isn't present locally.
- **Match with remote:** HEAD does not match the remote. UNSURE whether `kiro-bridge` was deleted, renamed or merged upstream. I did not fetch.
- **Remote URL:** `git@github.com:ShreeyankDoliya/Terminal_2.0_Harbor_Harness.git`
- **Working tree:** no tracked-file edits. Untracked: the runner, ledger, `.master-queue/`, `Tasks_INPUT/`, `jobs/`, `Output_*` and two `.kiro-run-*` folders.
- **Not used by me:** a second clone exists at `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness`, at HEAD `bde868c4` per another session's `MIGRATION_REPORT.md`. I only read from it.

### Bundle sources

| Source | What it holds |
|---|---|
| `master_chat_work/bundles/<slug>` | The 4 bundles of 21 Oct |
| Paths the operator pasted earlier | The 13 tasks of 19–20 Oct (FROM MEMORY; they are recorded per run as `source` in `state.json`) |
| `Tasks_INPUT/<slug>/` | Unchanged copies of each bundle, which runs use. A fixed bundle is matched by folder name and replaces the copy; the old copy moves to `.master-queue/task-archive/<slug>-<ts>/` (currently `emberforge-vault-settlement-20261021T173133`). |

### Job output

| Path | What it holds |
|---|---|
| `.kiro-run-<slug>-<ts>/` | Each run's private jobs root (`--jobs-dir`). Kept for failed runs; I deleted it after network or start failures. |
| `jobs/<slug>/` | A finished run's job, renamed there by the harness |
| `jobs/_archive/<slug>-<ts>/` | An older result moved aside when a rerun of the same slug finishes |
| `Output_Deliverables/<slug>/`, `Output_RFP/<slug>/` | Rebuilt by the harness finalize step on every run |

A new run does not overwrite an old one: the runner archives the old result first. One exception: an errored trial still rebuilds `Output_RFP/<slug>/`. This happened for emberforge attempt 2, schema-migration attempt 2 and district-heat both attempts.

### QC report output

None by this chat. `master_chat_work/20261021_{vendor-archive-roundtrip-recovery,schema-migration-plan-repair}/baseline_v0/QC_RESULT.md` and `TRAJECTORY_RESULT.md` exist but are 0 bytes. They were written by another session.

### My files

All are untracked in the clone above unless they are outside it.

| File | What it is |
|---|---|
| `scripts/master_queue.py` | Queue runner and CLI ("mq"): `add / status / scores / start / stop / resume / cancel / set-max / render / refinalize` |
| `scripts/tests/test_master_queue.py` | Its tests |
| `MASTER_RUN_LEDGER.md` | The readable record: usage, latest scores, queue, history, failure log, git rules, open issues, decisions |
| `.master-queue/state.json`, `state.lock`, `task-archive/` | The runner's data |
| `~/.config/opencode/rules/ground-rules.md` | Rule 13 (no push/commit) was added by me, with a backup at `ground-rules.md.bak-20261020-nopush` |
| `~/.anubis/subscription.env` | Copied from the repo template on day one (mode 600) |
| `/tmp/opencode-logs/<slug>-<ts>/run.log` | Debug logs, one per run (cleared on reboot) |
| `/tmp/opencode-logs/master-queue/runner.log` | The runner's log |
| `/tmp/opencode-logs/mq-watcher-20261021T1831/watch.log` | The watcher's log (finished) |
| `/tmp/opencode-logs/rerun-dh-schema-20261021T2328/pids.txt` | PIDs of the last two runs |

## 3. How a run is started

1. **Add:** `.venv/bin/python scripts/master_queue.py add <bundle path> [...]`. This copies the bundle to `Tasks_INPUT/`, queues it and starts the detached runner if it isn't running. `add <slug>` with no path requeues the existing copy.
2. **Launch:** for each queued task the runner runs `bash scripts/run-with-kiro-subscription.sh -p Tasks_INPUT/<slug> -y --jobs-dir <repo>/.kiro-run-<slug>-<ts>` with the wrapper defaults.
3. **Wrapper defaults:**
   - agent `openhands-sdk`, model `claude-opus-5` through a local Kiro bridge;
   - judge `gpt-5.6-sol` through the bridge, `REWARDKIT_JUDGE`;
   - harbor flags `--ae LLM_NUM_RETRIES=10`, `--artifact /logs/agent/trajectory.json`, `--agent-setup-timeout-multiplier 3`, `--allow-agent-host host.docker.internal`;
   - 1 run per task;
   - local Docker, no `exe_copy`.
4. **Finalize:** `_kiro_run_and_finalize.sh` runs harbor, then the finalize steps: pass summary, judge, Odoo usage post, deliverables and RFP packaging.
5. **Timeouts:** these come from each bundle's `task.toml`.

| Bundle | Verifier | Agent | Image build |
|---|---|---|---|
| district-heat, schema-migration, vendor-archive | 2700 s | 7200 s | 900 s |
| emberforge | 3300 s | 7200 s | 900 s |

6. **Runner settings:**
   - checks every 60 s;
   - max concurrent 3;
   - FIFO with a CPU and memory budget from `docker info`, minus 4096 MB headroom;
   - hang check: 15 min with no ESTABLISHED connection plus an idle log, on 3 checks in a row, gets one auto-relaunch;
   - pauses the queue on the Kiro "monthly usage limit" or on a startup failure under 300 s.
7. **Env variable names:**
   - `~/.anubis/subscription.env`: `ANUBIS_USAGE_API_URL`, `ANUBIS_USAGE_AUTH_HEADER`, `ANUBIS_USAGE_AUTH_VALUE`, `ANUBIS_PROJECT_ID`, `ANUBIS_PROJECT_TYPE`, `ANUBIS_TEAM_TYPE`, `ANUBIS_BUDGET_TYPE`, `ANUBIS_RFP_SUB_TYPE`, `ANUBIS_SETUP_TIMEOUT_MULTIPLIER`, `ANUBIS_CC_HEADROOM`, `HARBOR_HEADROOM_ENABLED`;
   - generated per run by the wrapper: `ANUBIS_KIRO_BRIDGE_SECRET` (passed as `LLM_API_KEY` / `OPENAI_API_KEY`), `ANUBIS_KIRO_BRIDGE_PORT`, `ANUBIS_KIRO_BRIDGE_HOST`;
   - `ANUBIS_SUBSCRIPTION_ID` is deliberately left unset;
   - a kiro-cli login must be active (it is not run by me).
8. **Tools:** Harbor 0.24.0, kiro-cli 2.33.1 (was 2.32.0 on 19 Oct), Docker Desktop.
9. **Typical duration:** 10–60 min per run; median of the scored runs is about 33 min. Runs that hit the agent limit take 127–137 min.

## 4. How QC is run

None. This chat has not run the PL QC, the v0 QC, `validate_bundle.py` or `exe_copy`, so no QC version or commit applies.

## 5. Inputs

The operator (Ayush) gives me work in chat messages, with bundle paths and sometimes text copied from the master chat. On 21 Oct the message listed the 4 `master_chat_work/bundles/*` paths. Nothing comes from prompt files or builder sessions directly.

## 6. Live status now (13:16 IST)

- **Processes:** none. No runner, harbor, bridge or `_kiro_run` processes.
- **Docker:** no containers.
- **Queue:** empty, not paused, max concurrent 3.
- **In-progress jobs:** none.

## 7. Run history

There are 25 harness attempts and 2 local verifier reproductions. All harness rows used agent `openhands-sdk`, model `claude-opus-5` (Kiro bridge) and judge `gpt-5.6-sol`. Times are IST and scores are combined / tests % / rubric %.

| Started | Task | Att | Min | Result | Job folder | Exists |
|---|---|---|---|---|---|---|
| 10-19 19:03 | season-ladder-settlement | 1 | 1 | STOPPED by operator | `jobs/2026-10-19__19-03-36/` (deleted) | no |
| 10-19 19:07 | season-ladder-settlement | 2 | 35 | FAILED: hung on a model request | deleted | no |
| 10-19 19:43 | season-ladder-settlement | 3 | 22 | 82.09 / 64.19 / 100 | `jobs/season-ladder-settlement/` | yes |
| 10-19 23:21 | 7ef8d80a-fea7-5d9e-b426-bcabfc6802ec | 1 | 48 | 99.10 / 98.21 / 100 (re-finalized) | `jobs/7ef8d80a-…/` | yes |
| 10-19 23:22 | caldermoor-commitment-closure | 1 | 46 | 87.22 / 74.44 / 100 (re-finalized) | `jobs/caldermoor-commitment-closure/` | yes |
| 10-19 23:23 | cohort-retention-reconciliation | 1 | 10 | 58.67 / 42.35 / 75 | `jobs/cohort-retention-reconciliation/` | yes |
| 10-19 23:33 | cohort-uplift-reconciliation | 1 | 24 | 100 / 100 / 100 | `jobs/cohort-uplift-reconciliation/` | yes |
| 10-19 23:58 | dispatch-plan-reoptimization | 1 | 33 | 64.19 / 29.67 / 98.72 (re-finalized) | `jobs/dispatch-plan-reoptimization/` | yes |
| 10-20 00:09 | emberforge-vault-settlement | 1 | 56 | 84.00 / 68.00 / 100 (re-finalized) | `jobs/_archive/emberforge-vault-settlement-20261021T193942/` | yes |
| 10-20 00:10 | numeric-reduction-benchmark-forge | 1 | 12 | 87.41 / 98.81 / 76 | `jobs/numeric-reduction-benchmark-forge/` | yes |
| 10-20 00:22 | pcggc-multi-state-rec-settlement | 1 | 14 | 100 / 100 / 100 (re-finalized) | `jobs/pcggc-multi-state-rec-settlement/` | yes |
| 10-20 00:31 | sensor-network-lsq-correlated-adjustment | 1 | 25 | 71.16 / 100 / 42.31 (re-finalized) | `jobs/sensor-network-lsq-correlated-adjustment/` | yes |
| 10-20 00:36 | sentinel-policy-recompute | 1 | 19 | 77.78 / 100 / 55.56 | `jobs/sentinel-policy-recompute/` | yes |
| 10-20 01:05 | specdec-verification-engine | 1 | 12 | 100 / 100 / 100 | `jobs/specdec-verification-engine/` | yes |
| 10-20 01:17 | match-replay-desync-audit | 1 | 85 | FAILED: Kiro monthly usage limit (`ApiOverloadedError`) | `jobs/_archive/match-replay-desync-audit-20261020T111343/` (see note 1) | yes |
| 10-20 10:32 | match-replay-desync-audit | 2 | 41 | 80.43 / 63.19 / 97.67 | `jobs/match-replay-desync-audit/` | yes |
| 10-21 17:31 | district-heat-flex-procurement | 1 | 137 | FAILED: `AgentTimeoutError` 7200 s, then judge "Trajectory not found", no reward | `.kiro-run-district-heat-flex-procurement-20261021T173139/` | yes |
| 10-21 17:32 | emberforge-vault-settlement | 2 | 19 | FAILED: `EnvironmentStartTimeoutError` 900 s (load average about 200) | deleted | no |
| 10-21 17:36 | vendor-archive-roundtrip-recovery | 1 | 59 | 52.41 / 4.83 / 100 (tests score not genuine, see section 10) | `jobs/vendor-archive-roundtrip-recovery/` | yes |
| 10-21 17:52 | schema-migration-plan-repair | 1 | 18 | FAILED: `EnvironmentStartTimeoutError` 900 s | deleted | no |
| 10-21 18:10 | emberforge-vault-settlement | 3 | 1 | FAILED: bridge not healthy within 30 s | deleted | no |
| 10-21 18:44 | schema-migration-plan-repair | 2 | 47 | FAILED: judge "Connection error", then `RewardFileNotFoundError` | deleted | no |
| 10-21 18:45 | emberforge-vault-settlement | 4 | 54 | 43.07 / 1.94 / 84.21 (tests score not genuine) | `jobs/emberforge-vault-settlement/` | yes |
| 10-21 23:28 | district-heat-flex-procurement | 2 | 127 | FAILED: `AgentTimeoutError` 7200 s, then no trajectory, no reward | `.kiro-run-district-heat-flex-procurement-20261021T232853/` | yes |
| 10-21 23:36 | schema-migration-plan-repair | 3 | 41 | 84.44 / 99.3 / 69.57, 1 test failed (`module_core_claims_match_archive`) | `jobs/schema-migration-plan-repair/` | yes |

**Local verifier reproductions (not harness runs):**

| When | Task | What I did | Result |
|---|---|---|---|
| 10-21 20:50 | vendor-archive-roundtrip-recovery | Ran the agent's `decode.py` against the bundle's `test_output.py`, as root in `python:3.12-slim` | Grader temp input is mode 600, then the decoder runs as `nobody`, then "Permission denied" and all behavioural checks fail. With `chmod 644`, 5 of 6 basic checks pass. Scratch deleted. |
| 10-21 23:00 | emberforge-vault-settlement | Same check | 41 of 50 checks pass locally, against 3 of 50 in the harness. Exact cause UNSURE. Scratch deleted. |

**Notes:**
1. `state.json` still points match-replay attempt 1 at `jobs/match-replay-desync-audit/`. The ledger and the directory listing show it moved to `jobs/_archive/match-replay-desync-audit-20261020T111343/` (the pointer is stale).
2. Re-finalized: these runs were scored again after the harness finalize step picked the wrong job folder (see section 10).

## 8. Pending work

None queued or half-done. Items waiting on a decision:
1. **district-heat-flex-procurement:** no score after 2 attempts, both hit the 7200 s agent limit. The agent was still load-testing `derive_report.py`, with each test run limited to 300 s. It needs a bundle change or a longer agent limit before a rerun. Waiting on Ayush or the bundle builder.
2. **vendor-archive-roundtrip-recovery:** the tests score is invalid. The `test_output.py` temp-file permission fix is needed, then a rerun. Waiting on Ayush or the bundle builder.
3. **emberforge-vault-settlement:** the tests score is invalid. The cause needs finding (the grader's permissions for user 4001 in the harness), then a fix and a rerun. Waiting on Ayush or the bundle builder.
4. **Docker memory:** I said I'd remind Ayush to change it from 24 GB to 16 GB after the runs. Docker now reports about 11.7 GiB (12 GB), so it was changed, but to a lower value than suggested. See section 10.

## 9. Rules I follow

- **Ground rules:** `~/.config/opencode/rules/ground-rules.md`, including:
  - rule 13: "never run `git push`, `git commit`, `git merge` into a pushed branch, or open a PR, under any circumstance";
  - rule 17: long calls go through nohup or background, with logs in `/tmp/opencode-logs/<task>/`;
  - no `kiro-cli login`/`logout`, and never print tokens.
- **Harness and bundles:** "Do not change the harness"; I only add wrappers and new files. Never change the operator's tasks: copy them unchanged into `Tasks_INPUT/` and only read the originals.
- **Committing:** "2. do not commit", which also rules out a local backup branch or commit.
- **Matching fixed tasks:** "match same tasks with tasks name not path"; a fixed task can come from any folder.
- **Hung or network-failed runs:** "stop and delete this run completely ... and run again".
- **Odoo records:** leave the 4 early, incomplete records (dispatch, pcggc, emberforge, sensor-network) and never resend them.
- **Subscription ID:** leave `ANUBIS_SUBSCRIPTION_ID` unset; "don't raise this again".
- **Logs:** leave the logs in `/tmp/opencode-logs` as they are.
- **Bridge investigation:** the bridge 300 s timeout hang: "leave it for now".
- **Changes:** process rule: list planned changes, Ayush approves each item, then edit only the approved items. "No edit just answer" means no edits at all.
- **Monitoring:** for the 21–22 Oct runs, "do not use watcher just save the pid", and report status only when asked.
- **Style:** short, plain answers, tables when useful, times in IST, "answer in short".

## 10. Known problems

1. **Finalize picks the wrong job folder.** `_kiro_run_and_finalize.sh` finalizes the "newest new folder" under `jobs/`, so runs side by side finalize each other's folders. Evidence: 6 runs on 19–20 Oct were re-finalized, and 2 incomplete Odoo records were posted. Workaround: a private `--jobs-dir .kiro-run-<slug>-<ts>/` per run.
2. **Host overload.** Other sessions (opencode processes, a long-running `driver.py`, a `migrakit` job) pushed the load average to 150–280 on 8 CPUs on 21 Oct, and swap filled up. This caused the `EnvironmentStartTimeoutError` (900 s) failures, the bridge failing to start in 30 s, 10 bridge `TimeoutError`s and the judge "Connection error". Workaround: run when the load is low; nothing of theirs was touched.
3. **An errored trial loses the whole reward.** When the agent times out (no trajectory) or the judge call fails, rewardkit writes no reward file, so harbor reports `RewardFileNotFoundError` or "Trajectory not found" and the tests score is lost too. Seen in district-heat attempts 1–2 and schema-migration attempt 2.
4. **Errored trials rebuild `Output_RFP/<slug>/`.** Evidence: emberforge attempt 2 and district-heat at 19:48 and 01:36.
5. **Vendor-archive test bug (confirmed).** `tests/test_output.py` writes the input with `tempfile.NamedTemporaryFile` (mode 600, root) and runs `decode.py` as `nobody` through `setpriv`. The decoder returns `{"error":"unreadable_input","detail":"[Errno 13] Permission denied"}`. Evidence is in section 7.
6. **Emberforge test bug (cause UNSURE).** Only 3 of 50 checks pass in the harness, against 41 of 50 locally with the same delivered `settle_vault.py`. The grader drops to uid 4001; the harness-side permissions on `/app/out` or the corpus are the likely difference, but not confirmed.
7. **Docker memory limits concurrency.** Docker memory is now about 11,946 MB. The runner's budget is that minus 4096 MB headroom, about 7,850 MB, which fits only one 4096 MB task at a time even with max concurrent 3 (worked out from the code, not tested).
8. **Remote branch missing.** The remote has no `kiro-bridge` branch (section 2), so the safe-pull steps in the ledger, which use `origin/kiro-bridge`, no longer apply as written.
9. **Logs are in `/tmp`.** Run logs are cleared on reboot. Results are in `jobs/`.
10. **Kiro monthly usage limit.** The limit was hit on 20 Oct at 02:39 and had reset by 10:32. The runner now pauses the queue on it.
11. **Bridge 300 s timeout.** It didn't release the 19 Oct hang. Not investigated (operator decision).

## 11. Open questions for Ayush or the PL

1. Was `kiro-bridge` removed from the remote on purpose, and which branch should this clone track now (`main` is at `a74bda85`)?
2. For district-heat: should the agent limit be raised above 7200 s, or should the bundle's load testing be reduced? Who fixes it?
3. Who fixes the vendor and emberforge test permission bugs, and should both be rerun afterwards?
4. Docker memory is 12 GB, not the suggested 16 GB. Is that intended? At 12 GB the runner fits only 1 run at a time.
5. `Tasks_INPUT/cf9b2067-1ba0-5bab-a1ea-83e976851e6c/` (created 2026-10-19 18:55) has no run in `state.json`. UNSURE where it came from and whether it should be run.
6. Should the empty `baseline_v0/QC_RESULT.md` and `TRAJECTORY_RESULT.md` files in `master_chat_work` be filled in from the trajectory results above?
