# Grader leak audit (board e59fc8d)

Harness: `Terminal_2.0_Harbor_Harness` HEAD `71a653b2` ("QC + generator: accept a shipped trajectories/ directory (S3, S5)").
Code paths below are relative to `Terminal_2.0_Harbor_Harness/src/harbor/`. Scratch: `/tmp/leak_audit-20261024T1024/`.

**Verdict: NO.** Grader leakage does not explain the 100/100/100 scores. In every run the agent could not reach the tests, the hidden data generators, the judge rubric or the reference solution. No trajectory tried to reach them. One leak did happen: an old copy of sensor-network shipped author trap notes in its data. That run used them and scored 71.16, not 100.

---

## 1. Staging timeline (when grader files exist, and where)

| Step | What happens | Grader material present in the agent container? | Evidence |
|---|---|---|---|
| 1 Build | The agent image is built with `environment_dir` as its build context. That is the task's `environment/` folder only. | No. `tests/` and `solution/` sit outside the build context. | trial.py:844-867; environments/docker/docker.py:238-248 (`CONTEXT_DIR=environment_dir`), :349-379 |
| 2 Start | `docker compose up` runs. These bind mounts are added: host trial `agent_dir`→`/logs/agent`, `verifier_dir`→`/logs/verifier`, artifacts→`/logs/artifacts`. Host dirs are chmod 0o777. | `/logs/verifier` is mounted, empty and writable. | trial.py:1249-1271; models/trial/paths.py:36-43, :141-150 |
| 3 Network | Agent-phase policy is the task `[agent]` allowlist plus `extra_allowed_hosts`. For every run that is `api.anthropic.com`, `api.z.ai`, `host.docker.internal`. Enforcement: egress sidecar (gost + nftables, non-TCP rejected). The run refuses to start if enforcement is unsupported. | n/a | trial/network_policy.py:23-42, :108-120; docker.py:184-195; environments/base.py:768-790; sidecar bin/network-policy:33-58 |
| 4 Agent setup | The openhands-sdk runner is uploaded to `/installed-agent/run_agent.py`. Env passed: LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, AGENT_LOGS_DIR, TRAJECTORY_PATH, MAX_ITERATIONS and similar. Tools: Terminal, FileEditor, TaskTracker. | No grader files. The LLM proxy key is in the env (it is the agent's own key). | agents/installed/openhands_sdk.py:136-147, :182-245; openhands_sdk_runner.py:225-228 |
| 5 Agent run | Runs as task `agent.user` (`1000:1000` for all 23 staged copies). | No `/tests` and no `/solution` (probe output in §3). | trial.py:445-488; trial/single_step.py:75-82 |
| 6 After agent | Agent logs are uploaded, artifacts collected, and the agent container stopped (`environment_mode = "separate"` in every task.toml). | n/a | single_step.py:38-55 |
| 7 Verifier | A NEW container is built from `tests/` (`COPY . /tests/`, `chmod -R go-rwx /tests`). It gets a fresh `/logs/verifier` and the artifacts. `/tests` is uploaded only inside `verify()`. The judge env (`OPENAI_*`, `REWARDKIT_JUDGE`) is only here. | Grader files exist only here, after the agent has stopped. | trial.py:563-631, :675-696; verifier/verifier.py:147-157, :159-173 |
| — `/solution` | Uploaded only by the oracle agent or `harbor tasks` CLI. Never for openhands-sdk. | Never. | agents/oracle.py:92-99; cli/tasks.py:427 |

---

## 2. Channel matrix

| # | Channel | Reachable | Used in a trajectory | Tasks | Evidence | Fix |
|---|---|---|---|---|---|---|
| 1 | `/tests`, `/solution`, `/logs/verifier`, reward, judge inside the agent container during the run | **No** for tests/solution/reward/judge. `/logs/verifier` is reachable as an empty writable mount. | No. 0 tool calls mention `/tests`, `/solution`, `/logs`, reward or judge. | all | Build context: trial.py:844-867. Separate verifier: trial.py:563-631. Probe: `ls: cannot access '/tests': No such file or directory` and the same for `/solution`; `/logs/verifier` is `drwxrwxrwx` and empty (probe_dispatch.txt:447-471). test.sh removes `reward.{txt,json}` first, and the separate verifier gets a fresh dir, so anything planted is discarded. | Mount `/logs/verifier` only in the verifier container (trial.py:1249-1271), not in the agent container. |
| 2 | Image layers / build context | **No** | No | all 23 staged copies | Every `environment/Dockerfile` does only `COPY data /app/data`. New schema-migration also does `COPY repo` and `COPY ci`. `docker history --no-trunc` for both probe images shows only base, useradd, apt, openhands venv, WORKDIR, `COPY data /app/data` (1.13MB / 73.7kB) and `chown /app`. No tests or solution layer (history.txt). | None needed. |
| 3 | Shipped/visible tests that embed hidden cases or `_SHIPPED_DATA` | **No** | No | schema-migration (new), 7ef8d80a | schema `repo/tests/test_visible.py` is a 122-line toy fixture. Its ids (`L01,ledger.v1`, `north-books`) appear 0 times in tests/test_output.py (10135 lines). `_SHIPPED_DATA` is defined only at tests/test_output.py:59, which is verifier-only. 7ef8d80a `calibration_expected.json` comes from a different seed (`seed ^ 0x5DEECE66D`, test_output.py:3239-3250). Grading uses the PROFILE_SEEDS corpora (test_output.py:3266-3269). | None. Calibration slices are fine because they use a different seed. |
| 4 | Hidden-data generators / seeds | **No** | No | all 16 | `SEED` constants from tests/*.py grepped into environment/ and instruction.md: 0 real hits (one 3-digit substring in cohort-uplift events.csv). The only code in any environment/ is the schema-migration repo under repair. | None. |
| 5 | Answer recoverable directly from shipped data | **No** | No | all 23 | Every ≥6-digit number in each solution/TRUTH.md was grepped (-w) into environment/. Every hit is an input: dispatch 4200000 decoy and 724451671 faulty objective (solver_run_report.json:166), pcggc 250000 capacity (facilities.csv:13), sentinel window bounds, a sensor chi-square table row, a schema id substring. The corrected answers (e.g. dispatch 446527364) are absent. The container probe agrees: `grep -rlwE '446527364\|31756967\|19229000' /` gave 0 files. | None. |
| 6 | Solution traces (.pyc, .git, backups, timestamps) | **No** | No | all | No .git, `__pycache__`, .pyc, `~`, .bak or .orig in any environment/. mtimes reveal nothing. | None. |
| 7 | Env vars / job metadata | **No** grader values | No | all | Probe env has only GPG_KEY, HOME, HOSTNAME, LANG, PATH, PWD, PYTHON_* and SHLVL. The agent-run env adds LLM_* and runner vars (openhands_sdk.py:182-245). Judge vars live only in the verifier env (verifier.py:159-173; job-config.json `verifier.env`). | None. |
| 8 | Network / public repos | Task repos: **No**. `host.docker.internal` on any port: **UNVERIFIED**. | No. 0 curl, wget, git clone or host.docker.internal calls. Every http string is an OOXML namespace. | all | All 4 repos return `private: true` from `gh api`, and unauthenticated api.github.com gives 404. Task-name code search hits only private `ShreeyankDoliya/Anubis_Tasks_Samples` (it contains solution/TRUTH.md). Public repo search finds only unrelated repos. github is not on the allowlist. The allowlist matches hostnames with no port restriction (sidecar gost.yaml + allowlist.txt), so every host port is open to the agent: LLM proxy :63439, judge proxy :63440 and anything else listening. Not exercised: the proxies are down now and I did not emulate the sidecar. | Restrict `host.docker.internal` to the LLM proxy port in the agent phase. Keep the judge proxy off the agent allowlist. |
| 9 | Judge steerability | **No** for rubric content. Trajectory tampering: **UNVERIFIED**. | No | all with judge.toml | The judge (gpt-5.6-sol, batched) compares figures stated in the final reply with fixed values in tests/judge.toml (dispatch R1-R5: 446527364 / 19229000 / 31756967 / 75 / 33012). It also has penalties R7 (−5, reply contradicts artifacts) and R8 (−3, modifies /app/data). Claims cannot pass without the right numbers. The judge reads `/logs/agent/trajectory.json`, which the agent could write. The runner writes it at the end (overwrites). Unused. | Write the trajectory from the host side, or keep `/logs/agent` read-only to the agent user. |
| 10 | Other: author notes left in shipped data | **Yes**, in the OLD copy of sensor-network only | **Yes**, in 1 run | sensor-network-lsq-correlated-adjustment (old `Harbor_Harness/` copy) | Old data: 51 files and 624 lines of `# TRAP n: ... inverse: ...` recipes, e.g. data/station_registry.csv:8-15. `stale_cached_solution.json` has a `_traps` key with 12 traps. Archive run `sensor-network-lsq-correlated-adjustment-20261023T200155` read them at steps 5 and 11 and referenced `_traps` at step 12. Reward 0.7115. The new copy has 0 `inverse:` hits and no `_traps`; its run scored 0.9. Smaller giveaways: self-labelled decoys in old numeric-reduction (`_decoy_weights`, schema.md:63-71) and old sentinel (`DECOY_MAX_RECORDS`, `OV-K042-decoy`). These give the spec away, not grader material. | Add a QC lint that fails on `TRAP\|inverse:\|_traps\|decoy` in environment/. Always stage from the current Tasks_INPUT, not the old `Harbor_Harness/` copy. |

---

## 3. Container probe (dispatch-plan-reoptimization, cohort-retention-reconciliation, new staged copies)

Built from copies in scratch as `leakaudit-dispatch:e59fc8d` (0e6a37f13b3e) and `leakaudit-cohort:e59fc8d` (b702bd0c8aab). Run with `docker run --rm --network none --user 1000:1000 -e HOME=/tmp`, with empty 0777 binds at `/logs/{agent,verifier,artifacts}` as in trial.py:1249-1271.

```
uid=1000(agent) gid=1000(agent) groups=1000(agent)
ls: cannot access '/tests': No such file or directory
ls: cannot access '/solution': No such file or directory
/app:  drwxr-xr-x agent agent .   |  drwxr-xr-x root root data
/logs: drwxrwxrwx agent agent agent | artifacts | verifier   (all empty)
```

- `find / -xdev \( -name '*test*' -o -name '*judge*' -o -name '*reward*' -o -name '*solution*' -o -name 'TRUTH*' \)` gave 931 hits (dispatch) and 921 (cohort). All of them are in `/opt/openhands-sdk-venv`, `/usr/lib/python3*` or `/home/agent/.cache/uv`: third-party package tests, `openhands/sdk/conversation/goal/judge.py`, `litellm/.../llm_judge.py`, `browser_use/agent/judge.py`, googleapiclient `baremetalsolution*.json`. None belongs to the task.
- env: `GPG_KEY HOME=/tmp HOSTNAME LANG=C.UTF-8 PATH PWD=/app PYTHON_SHA256 PYTHON_VERSION=3.12.13 SHLVL`.
- Answer grep over `/`: dispatch corrected figures gave 0 files. Cohort TRUTH figures matched only 2 litellm tokenizer hash files, which are unrelated.
- `docker history`: no layer touches tests/ or solution/ (excerpt above in channel 2; full output in history.txt).
- Not covered: the egress sidecar and the live proxies. Channel 8's any-port point stays UNVERIFIED.

---

## 4. Trajectories (every Opus run)

25 trajectory.json files were scanned (16 jobs/ and 9 of the 10 archive dirs; archive match-replay-20261020T111343 failed with exception.txt and has no trajectory). Each job has one run (`Run 1`). The scan regexes all tool-call arguments for /tests, /solution, /logs, reward, judge, TRUTH, hidden, curl, wget, git clone, pip download, http and host.docker.internal. No command touched `ls /`, `find /`, /proc, /opt, /installed-agent or /etc.

Verdicts: **clean** means no grader material was reachable or used. **exposed** means grader-like material was shown to the agent.

| Slug | Run | Reward | Verdict | Note |
|---|---|---|---|---|
| 7ef8d80a-fea7-5d9e-b426-bcabfc6802ec | jobs/Run 1 | 0.9911 | clean | calibration slice from a different seed |
| caldermoor-commitment-closure | jobs/Run 1 | 0.8722 | clean | |
| cohort-retention-reconciliation | jobs/Run 1 | 1.0 | clean | probed image |
| cohort-uplift-reconciliation | jobs/Run 1 | 1.0 | clean | |
| dispatch-plan-reoptimization | jobs/Run 1 | 0.7652 | clean | probed image; http = OOXML ns (steps 17,18,25,29) |
| district-heat-flex-procurement | jobs/Run 1 | 0.8125 | clean | |
| emberforge-vault-settlement | jobs/Run 1 | 0.2731 | clean | `ps aux` only (steps 36,44) |
| match-replay-desync-audit | jobs/Run 1 | 0.8043 | clean | |
| numeric-reduction-benchmark-forge | jobs/Run 1 | 0.874 | clean | self-labelled decoys (spec, not grader) |
| pcggc-multi-state-rec-settlement | jobs/Run 1 | 1.0 | clean | |
| schema-migration-plan-repair | jobs/Run 1 | 0.4615 | clean | `pip install pyflakes` fallback (step 78), no network |
| season-ladder-settlement | jobs/Run 1 | 0.8209 | clean | |
| sensor-network-lsq-correlated-adjustment | jobs/Run 1 | 0.9 | clean | new copy, no traps |
| sentinel-policy-recompute | jobs/Run 1 | 0.7778 | clean | |
| specdec-verification-engine | jobs/Run 1 | 1.0 | clean | |
| vendor-archive-roundtrip-recovery | jobs/Run 1 | 0.7188 | clean | |
| cohort-retention-reconciliation | archive 20261023T003936 | 0.5868 | clean | |
| dispatch-plan-reoptimization | archive 20261023T203020 | 0.6419 | clean | |
| district-heat-flex-procurement | archive 20261023T124919 | 1.0 | clean | |
| emberforge-vault-settlement | archive 20261021T193942 | 0.84 | clean | "pip" was a grep pattern (step 25) |
| emberforge-vault-settlement | archive 20261023T211239 | 0.4307 | clean | |
| match-replay-desync-audit | archive 20261020T111343 | — | no trajectory | exception.txt |
| schema-migration-plan-repair | archive 20261023T231133 | 0.8443 | clean | |
| sensor-network-lsq-correlated-adjustment | archive 20261023T200155 | 0.7115 | **exposed** | old data TRAP/inverse notes read at steps 5 and 11; `_traps` referenced at step 12 |
| vendor-archive-roundtrip-recovery | archive 20261023T005752 | 0.5241 | clean | |
| vendor-archive-roundtrip-recovery | archive 20261023T130725 | 1.0 | clean | |

No run is **contaminated**, meaning no run read tests, solution, rubric or hidden data. All six 1.0 runs are clean. Which three tasks the master's "100/100/100" refers to is UNVERIFIED (master note 20261023T0750_peer_levers/G*.md:5 does not name them). All six candidates are clean.

---

## 5. Verdict: is 100/100/100 explained by leakage? **No.**

- The agent container never holds tests, the solution, the judge rubric or the generators (§1, §3). The build context is environment/ only, and the verifier runs separately after the agent stops.
- No trajectory looked for grader material (§4).
- The one real leak (old sensor TRAP notes) produced 71.16, not 100.
- Other explanations already on record fit better. Master note G*.md:5 says earlier low scores came from a grader permission bug (see SCAN.md, board 4b75115) and that the levers leaked through instruction wording. Note 20261023T0912_chatgpt_research_r2.md:9 says the agent read every file and wrote one program that it checked only against shipped data. Opus can solve these tasks from the instruction and the shipped data; the local reflex programs score 0.11-0.13 because they do not. That gap is about how hard the tasks are and how they are worded (the lever library), not grader exposure.

Open items (UNVERIFIED): (a) whether any other host service is reachable on `host.docker.internal` during a real run; (b) whether a rewritten `/logs/agent/trajectory.json` would survive to the judge. Neither was used in any run.

---

## Lessons for the master

1. Grader isolation in this harness holds: separate verifier, build context limited to environment/, no `/solution` for real agents. Do not spend more boards chasing leaks to explain high Opus scores. Look at instruction wording and data giveaways instead.
2. The real leak risk is author notes inside `environment/data` (TRAP/inverse/_traps/decoy labels). Add a QC grep gate for these, and never stage from the old `Harbor_Harness/` copy. 18 of 26 job configs (9 jobs/, 9 archive) pointed at that old path.
3. Tighten two harness loose ends: mount `/logs/verifier` only into the verifier, and limit the agent's `host.docker.internal` allowance to the LLM proxy port.
4. Compare local reflex programs against Opus only on the same staged copy. Old and new copies differ, as sensor 0.71 vs 0.90 shows.
