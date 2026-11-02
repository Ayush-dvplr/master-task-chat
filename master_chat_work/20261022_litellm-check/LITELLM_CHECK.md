# litellm 1.107.0 check (read only)

Brief issued 22 Oct 2026 14:30 IST by the master chat. Checks ran 23 Oct 2026 IST. Nothing was installed, deleted or edited. No Python was started and litellm was never imported. No network calls were made. Logs are in `/tmp/opencode-logs/litellm-check-20261022T1430/`.

## Result

- **1 SUSPECT environment**: the uv cached environment `~/.cache/uv/archive-v0/mGj267huY6AIjqVl`, which holds litellm 1.107.0. The payload was installed there **and has run**. There is also 1 SUSPECT cache hit: the unpacked 1.107.0 wheel `~/.cache/uv/archive-v0/zluUC3T4H2vAmp6A`.
- **616 of 648 bundles** have no `litellm==1.105.0` pin in `tests/Dockerfile`, so they FAIL K8. Only 32 PASS.
- **Do not start Python in that environment; tell Ayush to rotate keys.** Do not run `uv run` / `uvx` with the rewardkit + litellm requirement set until the uv cache entry has been dealt with, because uv reuses this cached environment.

## Step 1 and 2: Host Python environments

Locations searched with `find -maxdepth 8 -type d -name 'litellm-*.dist-info'`: `/Users/mac/Desktop/Terminal Bench`, `~/.local` (which includes `~/.local/share/uv`), `~/.cache/uv`, `~/Library/Caches/pip` and `~/.cache/opencode`. I also searched `~/Library/Python` and `~/.config`.

| # | site-packages path | litellm | dist-info mtime (birth) | `.pth` / `sitecustomize` / `usercustomize` in site-packages | Verdict |
|---|---|---|---|---|---|
| 1 | `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/.venv/lib/python3.13/site-packages` | 1.86.2 | 2026-10-22 13:36:19 (born 2026-10-19 18:57:10) | none | CLEAN (see note A) |
| 2 | `/Users/mac/Desktop/Terminal Bench/Harbor_Harness/Terminal_2.0_Harbor_Harness/.venv/lib/python3.13/site-packages` | 1.86.2 | 2026-10-19 18:57:10 | none | CLEAN |
| 3 | `~/.local/share/uv/tools/harbor/lib/python3.13/site-packages` (uv tool `harbor`) | 1.105.1 | 2026-10-14 18:21:03 | none | CLEAN |
| 4 | `~/.cache/uv/archive-v0/vOAIlGYi0_2pFM9V/lib/python3.14/site-packages` | 1.106.1 | 2026-10-21 14:03:56 (born 14:03:45) | none | CLEAN |
| 5 | `~/.cache/uv/archive-v0/mGj267huY6AIjqVl/lib/python3.12/site-packages` | **1.107.0** | **2026-10-21 17:34:22** (born 17:34:03) | `cook.pth` (12 bytes): `import cook`. `cook.py` (22,252 bytes). `sitecustomize.py` (25,509 bytes), first 3 lines: `import asyncio` / `import os` / `import re` | **SUSPECT, payload ran** (see note B) |
| 6 | `~/.cache/uv/archive-v0/Q6EchsiBVR_Cmsnb/lib/python3.12/site-packages` | 1.106.2 | 2026-10-21 18:18:24 (born 18:18:17) | none | CLEAN |
| 7 | `~/.cache/uv/archive-v0/MsqOr6SUYLIqSTYt/lib/python3.14/site-packages` | 1.105.1 | 2026-10-17 02:37:31 (born 2026-10-14 18:19:26) | none | CLEAN |

**Note A.** On 22 Oct 13:36:19, `INSTALLER`, `RECORD`, `REQUESTED` and `licenses/` in the env 1 dist-info were rewritten. `METADATA` and `WHEEL` still date from 19 Oct, and the version is still 1.86.2. This is a reinstall of the same version, not 1.107.0.

**Note B, the SUSPECT environment** `~/.cache/uv/archive-v0/mGj267huY6AIjqVl`:
- The litellm 1.107.0 `RECORD` lists `cook.pth`, `cook.py` and `sitecustomize.py`, so these files came from the litellm wheel.
- **It ran.** `__pycache__/cook.cpython-312.pyc` and `__pycache__/sitecustomize.cpython-312.pyc` were written on 2026-10-21 at 17:36. Sixty-three `.pyc` files were written in that window, the newest at 17:36:19. They include `requests` and `urllib3`, which means Python started in this environment and the hook imported HTTP libraries.
- From `pyvenv.cfg`: uv 0.13.1, CPython 3.12.15 from `~/.local/share/uv/python/cpython-3.12-macos-aarch64-none`.
- Contents: `harbor_rewardkit-0.2.1`, `openai`, `boto3`, `huggingface_hub`, and others. `bin/` has `rewardkit`, `litellm` and `litellm-proxy`.
- The symlink `~/.cache/uv/environments-v2/a8a188ba51d26bd7/1e5d53cf1c5205c8` points to it. This is a cached `uv run --with` / `uvx` environment, most likely a local rewardkit run on 21 Oct around 17:34 that pulled litellm in without a pin.
- I grepped the files as text only. `sitecustomize.py` has `requests` ×4, `exec(` ×2, `base64` ×1, `http` ×2 and `socket` ×3. `cook.py` has `exec(` ×1 and `base64` ×1. Neither file contains the literal strings `169.254.169.254`, `metadata.google.internal`, `os.environ`, `.ssh`, `.aws`, `LaunchAgents` or `crontab`. The payload is probably encoded, so their absence proves nothing.

### Locations that do not exist
`/opt/homebrew/lib/python3*`, `/Library/Frameworks/Python.framework`, `~/.pyenv` and `~/.openhands` do not exist. `~/.cache/opencode` exists but has no litellm.

### Other payload files
No other `cook.pth`, `cook.py`, `sitecustomize.py` or `usercustomize.py` was found anywhere under `~/.local`, `~/.cache`, `~/Library/Python`, `~/.config` or the Terminal Bench folder.

## Cache hits

| Cache | Entry | Content | Date | Verdict |
|---|---|---|---|---|
| uv | `~/.cache/uv/archive-v0/zluUC3T4H2vAmp6A` | unpacked **litellm 1.107.0** wheel. `litellm-1.107.0.data/purelib/` holds `cook.pth` (12 B), `cook.py` (22,252 B) and `sitecustomize.py` (25,509 B) | 2026-10-21 17:34:21 | **SUSPECT** |
| uv | `~/.cache/uv/archive-v0/mGj267huY6AIjqVl` | environment 5 above (installed 1.107.0) | 2026-10-21 17:34:22 | **SUSPECT** |
| uv | `~/.cache/uv/environments-v2/a8a188ba51d26bd7/1e5d53cf1c5205c8` | symlink to `mGj267huY6AIjqVl` | 2026-10-21 | SUSPECT (pointer) |
| uv | `archive-v0/vPCnloXHeIvHOTnQ` | litellm 1.106.1 wheel | 2026-10-21 14:03 | CLEAN |
| uv | `archive-v0/zMw42TRPY07wbkOA` | litellm 1.106.2 wheel | 2026-10-21 18:18 | CLEAN |
| uv | `archive-v0/jc3UyQUR0l21TS5p` | litellm 1.105.1 wheel | 2026-10-14 | CLEAN |
| uv | `archive-v0/0pi0tmeUvFe-TIyN` | litellm 1.86.2 wheel | 2026-10-19 | CLEAN |
| pip | `~/Library/Caches/pip` | no `litellm-1.107.0*` file name and no litellm dist-info | n/a | none found (see limits) |

## Step 3: Bundles

- I scanned **1,296 Dockerfiles in 648 bundles** across the four roots. Every bundle has both a `tests/Dockerfile` and an `environment/Dockerfile`.
- K8 PASS means `tests/Dockerfile` pins `litellm==1.105.0`.
- No file in any of the four roots mentions litellm 1.107.

**tests/Dockerfile**

| Pin | Bundles |
|---|---|
| `==1.105.0` | 32 |
| none | 600 |
| none, with litellm named only in a comment | 16 |

**environment/Dockerfile**

| Pin | Bundles |
|---|---|
| `==1.105.0` | 332 |
| none | 312 |
| `==1.104.0` | 4 |

The four `==1.104.0` bundles are all under `Anubis_Tasks_Samples/stale_Pass@1/Dinshi_Jain/Abdus Samad Ali/`.

A typical FAIL line is `RUN pip install --no-cache-dir harbor-rewardkit==0.2.1`. `harbor-rewardkit==0.2.1` pulls in litellm without a pin. Built on 21 Oct, that verifier would have resolved to 1.107.0, and the SUSPECT environment above is exactly rewardkit 0.2.1 plus litellm 1.107.0. The PASS line is `RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0`.

### K8 by root (tests/Dockerfile)

| Root | PASS | FAIL |
|---|---|---|
| `master_chat_work/bundles/` (includes `_work` backups and scaffolds) | 8 | 2 |
| `Terminal_2.0_Harbor_Harness/Tasks_INPUT/` | 3 | 14 |
| `Anubis_Tasks_Samples/Pass@1_New` | 16 | 4 |
| `Anubis_Tasks_Samples/stale_Pass@1` | 5 | 61 |
| `Anubis_Tasks_Samples/Backup_Tasks` | 0 | 34 |
| `Anubis_Tasks_Samples/Low_Effort` | 0 | 207 |
| `Anubis_Tasks_Samples/More_Efforts` | 0 | 31 |
| `Anubis_Tasks_Samples/QC_Fixed_17_10` | 0 | 12 |
| `Anubis_Tasks_Samples/QC_Fixed_18_10` | 0 | 196 |
| `Anubis_Tasks_Samples/QC_Fixed_19_10` | 0 | 26 |
| `QC assigned/` (converted tasks 14, my tasks 14, sales-csv-summary 1) | 0 | 29 |
| **Total** | **32** | **616** |

### Full bundle table

Paths are relative to `/Users/mac/Desktop/Terminal Bench/`. The pip line comes from `tests/Dockerfile`, with its line number.

| Bundle | tests/Dockerfile pin | tests/Dockerfile pip line | environment/Dockerfile pin | K8 |
|---|---|---|---|---|
| `Anubis_Tasks_Samples/Backup_Tasks_(High_Pass_Rate_Rejected)/No_Trajectory/6c382654-a456-5716-9a74-86755fc2c106` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Backup_Tasks_(High_Pass_Rate_Rejected)/No_Trajectory/d6b271a6-36cd-52d8-a0c5-05ba68012bfc` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Backup_Tasks_(High_Pass_Rate_Rejected)/No_Trajectory/finetune-run-plan-reconciler` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Backup_Tasks_(High_Pass_Rate_Rejected)/No_Trajectory/household-ledger-reconciliation-engine` | none | `4:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Backup_Tasks_(High_Pass_Rate_Rejected)/No_Trajectory/hrd-dual-bucket-conformance` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Backup_Tasks_(High_Pass_Rate_Rejected)/No_Trajectory/ml-serving-rollout-reconcile-2` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Backup_Tasks_(High_Pass_Rate_Rejected)/No_Trajectory/numeric-reconciliation-audit` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Backup_Tasks_(High_Pass_Rate_Rejected)/No_Trajectory/stage-metrology-trim-optimization` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Backup_Tasks_(High_Pass_Rate_Rejected)/With_Trajectory/1beb9411-fbcc-53bc-9606-4cd74bebad8c` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Backup_Tasks_(High_Pass_Rate_Rejected)/With_Trajectory/9b5126c9-4460-5eaf-95d5-da58d27c0880` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Backup_Tasks_(High_Pass_Rate_Rejected)/With_Trajectory/aquifer-solute-transport-reconciliation` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Backup_Tasks_(High_Pass_Rate_Rejected)/With_Trajectory/capacity-lease-settlement-hk-95` | none | `4:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Backup_Tasks_(High_Pass_Rate_Rejected)/With_Trajectory/checkpoint-shard-ledger-recovery` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Backup_Tasks_(High_Pass_Rate_Rejected)/With_Trajectory/confined-aquifer-transport` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Backup_Tasks_(High_Pass_Rate_Rejected)/With_Trajectory/constraint-band-surface-reconcile-hk-84` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Backup_Tasks_(High_Pass_Rate_Rejected)/With_Trajectory/dedup-backup-catalog-repair` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Backup_Tasks_(High_Pass_Rate_Rejected)/With_Trajectory/dispatch-commitment-capacity-hk-89` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Backup_Tasks_(High_Pass_Rate_Rejected)/With_Trajectory/e8a00b57-445c-5cc1-9a70-07e91c3ebb0c` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Backup_Tasks_(High_Pass_Rate_Rejected)/With_Trajectory/eval-shard-propensity-attribution` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Backup_Tasks_(High_Pass_Rate_Rejected)/With_Trajectory/exact-rational-settlement-hk-88` | none | `4:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Backup_Tasks_(High_Pass_Rate_Rejected)/With_Trajectory/fieldkit-assembly-recompute` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Backup_Tasks_(High_Pass_Rate_Rejected)/With_Trajectory/hermetic-link-admission-plan` | none | `7:RUN pip install --no-cache-dir pytest==8.3.4 pytest-json-ctrf==0.3.5` | none | FAIL |
| `Anubis_Tasks_Samples/Backup_Tasks_(High_Pass_Rate_Rejected)/With_Trajectory/inference-scorer-reckoning` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Backup_Tasks_(High_Pass_Rate_Rejected)/With_Trajectory/logstore-compaction-ledger-repair` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Backup_Tasks_(High_Pass_Rate_Rejected)/With_Trajectory/markov-chain-stationary-audit` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Backup_Tasks_(High_Pass_Rate_Rejected)/With_Trajectory/merge-governance-restatement` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Backup_Tasks_(High_Pass_Rate_Rejected)/With_Trajectory/numeric-pipeline-correction` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Backup_Tasks_(High_Pass_Rate_Rejected)/With_Trajectory/polytope-lattice-count-repair` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Backup_Tasks_(High_Pass_Rate_Rejected)/With_Trajectory/quarrylane-trunk-gate-replay` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Backup_Tasks_(High_Pass_Rate_Rejected)/With_Trajectory/query-ledger-settlement` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Backup_Tasks_(High_Pass_Rate_Rejected)/With_Trajectory/recurrence-anchor-zone-reconcile-hk-46` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Backup_Tasks_(High_Pass_Rate_Rejected)/With_Trajectory/seat-entitlement-trueup` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Backup_Tasks_(High_Pass_Rate_Rejected)/With_Trajectory/service-orchestration-planner` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Backup_Tasks_(High_Pass_Rate_Rejected)/With_Trajectory/training-mixture-admission-audit` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/18b5d99f-d4de-5e08-bb90-aeae31d33b3e` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/5a75ec1c-4d25-50b2-a448-2657814e4f90` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/5a9af8bf-ad23-50a3-ab15-2bef1b62f30f` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/7ef8d80a-fea7-5d9e-b426-bcabfc6802ec/data` | none | `2:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/81435bd4-3eec-5fcb-b0da-dbc1500c2d7c` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/92427898-6c8d-5a67-907d-e259a78b3721` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/a693e3d3-cba1-50a7-8870-462cf0f70b24` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/ability-loadout-surface-reconcile-hk-81` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/abr-segment-shaping-ctl` | none | `7:RUN pip install --no-cache-dir pytest==8.3.4 pytest-json-ctrf==0.3.5` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/admission-hardening-config-forge` | none | `7:RUN pip install --no-cache-dir pytest==8.3.4 pytest-json-ctrf==0.3.5` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/af346080-1654-5b88-934f-e27fa27371ce` | none | `7:RUN pip install --no-cache-dir pytest==8.3.4 pytest-json-ctrf==0.3.5` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/af406434-881e-5eed-8cdb-0c1f61694ef9` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/airport-turnaround-packet-compiler` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/amp-mixed-precision-loss-scaling-correction` | none | `8:RUN pip install --no-cache-dir "pytest==8.3.3" \` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/archive-index-restore-audit` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/archive-member-surface-reconcile-hk-75` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/archive-retention-settlement-hk-94` | none | `5:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/bastion-access-audit` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/batch-schedule-cost-reconciliation` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/beamtime-custody-replay-repair` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/blend-merit-allocation` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/brackwell-custody-materialization` | none | `10:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/brawl-ladder-settlement` | none | `10:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/brine-loop-lithium-yield-reconciliation` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/calorimeter-network-inference` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/catalog-probe-replay` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/catalog-temporal-rollup` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/cdc-ingest-window-settlement` | none | `10:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/checkpoint-compaction-recompute` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/checkpoint-lineage-compute-reconciliation` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/checkpoint-promotion-fixpoint` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/chrono-ledger-compiler` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/clinical-assay-batch-reconciliation` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/clinical-assay-qc-recalibration-forge` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/cohort-uplift-reconciliation` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/commerce-normalization-02` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/commitment-ledger-reconstruction` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/committed-tree-manifest-reconcile-hk-36` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/continued-fraction-ledger-reconciliation` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/crash-fault-attribution-repair` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/credential-scope-settlement-hk-90` | none | `4:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/dedup-vault-catalog-repair` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/depot-charge-ledger` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/detector-flux-reconciliation-forge` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/dual-price-basis-reconcile-hk-68` | none | `3:# No pip installs on purpose: test.sh carries its own loader and reward loop, and test_output.py imports only the standard library.` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/e78f9a39-85ab-512b-b434-3d1911dc7619` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/ee632e0e-3bbc-553e-a0f4-fdd2e9061931` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/ensemble-timescale-recompute` | none | `4:RUN pip install --no-cache-dir pytest==8.3.3 pytest-json-ctrf==0.3.5` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/epi-exposure-survival-reconcile-forge` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/errand-desk-allowance` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/eventforge-scale` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/experiment-decision-ledger-reconciliation` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/fault-signature-surface-reconcile-hk-76` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/fcc-multi-jurisdiction-sales-settlement` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/fdc5a20d-2dfe-5f64-a3fa-2c023318a760` | none | `2:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/feature-materialization-delta` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/feature-pipeline-config-ctl` | none | `7:RUN pip install --no-cache-dir pytest==8.3.4 pytest-json-ctrf==0.3.5` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/feature-pipeline-config-forge` | none | `7:RUN pip install --no-cache-dir pytest==8.3.4 pytest-json-ctrf==0.3.5` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/fenmarch-intervention-settlement` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/fleet-reservation-drain-plan` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/fleet-resource-governance` | none | `7:RUN pip install --no-cache-dir pytest==8.3.4 pytest-json-ctrf==0.3.5` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/fleet-rollout-audit` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/frame-packet-ledger-reconciliation` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/gateway-reentrancy-deadlock-auditor` | none | `4:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/geodetic-network-lsq-variance-reconcile-forge` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/gm-arena-ladder-payout-reconciliation-forge` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/gm-roguelite-run-economy-reconciliation-forge` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/gop-vbv-conformance-audit` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/grid-dispatch-optimization` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/groundlink-contact-settlement` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/h3-fleet-migration-scheduler-nk-20260907` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/halberd-query-plan-accounting` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/hardened-policy-config-repair` | none | `7:RUN pip install --no-cache-dir pytest==8.3.4 pytest-json-ctrf==0.3.5` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/host-budget-derivation-repair` | none | `7:RUN pip install --no-cache-dir pytest==8.3.4 pytest-json-ctrf==0.3.5` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/hoststore-mount-reconcile` | none | `4:RUN pip install --no-cache-dir pytest==8.3.3 pytest-json-ctrf==0.3.5` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/household-contingency-planner` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/inference-gate-replay` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/ironvault-bastion-policy-reconcile` | none | `7:RUN pip install --no-cache-dir pytest==8.3.4 pytest-json-ctrf==0.3.5` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/journal-replay-fault-repair` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/kestrel-run-scrutineer` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/lane-dispatch-optimisation` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/late-arrival-window-basis-reconcile-hk-65` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/latency-optimal-workload-scheduler-calibration` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/layered-aquifer-model-repair` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/ledger-settlement-netting` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/lsm-compaction-ledger-repair` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/manifest-tree-reconciliation` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/marrowgate-interval-restatement` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/marrowgate-maintenance-orchestration` | none | `6:RUN pip install --no-cache-dir pytest==8.3.4 pytest-json-ctrf==0.3.5` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/match-replay-desync-audit` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/meridan-streaming-moment-rollup` | none | `7:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/meridian-amr-field-consolidation` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/meridian-grid-tariff-reconciliation` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/meridian-neutron-activation-reconciliation` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/meter-drift-reconstruction-repair` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/metering-settlement-audit` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/ml-domain-marl-quantized-federated-v1` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/ml-drift-cohort-recalibration-forge` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/ml-inference-metric-reconciliation` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/model-training-checkpoint-calibration` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/modular-congruence-settlement` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/monorepo-dependency-reconciliation` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/museum-touring-installation-dossier` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/nebula-federated-aggregation-audit` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/ninefold-crown-settlement-recompute` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/numeric-reduction-benchmark-forge` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/observatory-semester-block-allocation` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/omnichannel-ledger-reconciliation/data` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/optimization-mincost-optctl-a1` | none | `7:RUN pip install --no-cache-dir pytest==8.3.4 pytest-json-ctrf==0.3.5` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/optimization-tick-aggregation-perf` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/pa-envelope-budget-ledger-repair` | none | `7:RUN pip install --no-cache-dir pytest==8.3.4 pytest-json-ctrf==0.3.5` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/pa-nutrient-ledger-reconciliation` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/pa-reminder-cadence-governor-forge` | none | `6:RUN pip install --no-cache-dir pytest==8.3.4 pytest-json-ctrf==0.3.5` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/partition-snapshot-query-replay` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/pcggc-multi-state-rec-settlement` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/plugin-capability-registration-reconcile-hk-63` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/plugin-loader-tls-arbiter` | none | `4:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/project-schedule-feasibility` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/quillfen-sla-settlement-repair` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/raceshuttle-volume-compiler` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/reactor-thermal-hydraulic-balance` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/reefer-power-dispatch-recompute` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/reelworks-transcode-config-forge` | none | `7:RUN pip install --no-cache-dir pytest==8.3.4 pytest-json-ctrf==0.3.5` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/refinery-blend-optimization-01` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/regional-anomaly-drift-reconciler` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/registry-lock-footprint-resolution` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/release-graph-reconciliation` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/release-line-support-ledger` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/release-provenance-reconciliation` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/relocation-moveout-reconcile` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/reminder-scope-surface-reconcile-hk-85` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/reminder-store-reconciliation` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/render-track-surface-reconcile-hk-82` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/residue-lattice-reconciliation` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/restoration-cadence-settlement` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/runtime-config-derivation-repair` | none | `7:RUN pip install --no-cache-dir pytest==8.3.4 pytest-json-ctrf==0.3.5` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/sc-radio-array-gain-recalibration-forge` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/se-buildfarm-cost-reconciliation` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/season-ladder-settlement` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/secondlife-battery-allocation` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/security-cli-crypto-policy-baseline` | none | `6:RUN pip install --no-cache-dir pytest==8.3.4 pytest-json-ctrf==0.3.5` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/security-metric-reconciliation` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/security-risk-ledger-reconciliation` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/security-vault-retention-arbiter` | none | `5:RUN pip install --no-cache-dir pytest==8.3.4 pytest-json-ctrf==0.3.5` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/segment-timebase-authority-reconcile-hk-43` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/sensor-network-lsq-correlated-adjustment` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/sentinel-policy-recompute` | none | `7:RUN pip install --no-cache-dir pytest==8.3.4 pytest-json-ctrf==0.3.5` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/sentinel-privilege-attestation` | none | `7:RUN pip install --no-cache-dir pytest==8.3.4 pytest-json-ctrf==0.3.5` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/serving-route-surface-reconcile-hk-80` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/session-watermark-settlement` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/shadowgate-authz-bypass` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/spectral-collocation-reconciliation` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/speculative-decode-arbiter` | none | `7:RUN pip install --no-cache-dir pytest==8.3.4 pytest-json-ctrf==0.3.5` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/strata-cartridge-recovery` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/strata-extent-relocation-planner` | none | `7:RUN pip install --no-cache-dir pytest==8.3.4 pytest-json-ctrf==0.3.5` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/stratified-boost-inference` | none | `2:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/supply-allocation-reconciliation` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/survey-raking-disclosure-audit` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/sysadmin-quota-reconcile-01` | none | `7:RUN pip install --no-cache-dir pytest==8.3.4 pytest-json-ctrf==0.3.5` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/telemetry-rollup-recompute` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/telemetry-throughput-optimizer` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/temporal-dependency-risk-ledger` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/temporal-graph-leakage-sampler` | none | `3:RUN pip install --no-cache-dir numpy==2.1.3 scipy==1.14.1 scikit-learn==1.5.2 pandas==2.2.3` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/tensor-packet-admission-recovery` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/thornevale-uplift-appraisal` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/tracehop-span-repair/data` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/trainmix-allocation-certificate` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/vantage-session-assembly` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/warrant-token-gateway-audit` | none | `7:RUN pip install --no-cache-dir pytest==8.3.4 pytest-json-ctrf==0.3.5` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/watershed-load-settlement-audit` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/wistmoor-agenda-settlement` | none | `15:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/wrenmoor-desk-replay` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/zero-trust-quorum-gate-configuration` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/With_Trajectory/07d51b69-db0c-57ed-9208-bcb7a5a3fd47` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/With_Trajectory/4e759599-27ea-59a0-9b7b-228efcc834a8` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/With_Trajectory/6090aa67-183f-5d64-955f-8fb51ecb043e` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/With_Trajectory/6cad24be-642d-597d-ab35-6eb5a919951b` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/With_Trajectory/7b219817-c863-5d7a-b0b9-b0274aa1175c` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/With_Trajectory/ae2bee53-13cc-54fc-930d-cfab8d5ca83a` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/With_Trajectory/assistant-sync-preemption-hub` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/With_Trajectory/cf9b2067-1ba0-5bab-a1ea-83e976851e6c` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/With_Trajectory/coldchain-settlement-reconciliation` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/With_Trajectory/cryogenic-energy-balance-repair` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/With_Trajectory/dabebf7d-379d-5679-982d-0a288eca5de7` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/With_Trajectory/daybreak-routine-dispatch-recompute` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/With_Trajectory/dc48a092-3f5d-5981-a8bd-e82d5530fe9d` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/With_Trajectory/dispatch-plan-reoptimization` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/With_Trajectory/emberforge-vault-settlement` | none | `7:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/With_Trajectory/f327a79b-42db-55ad-bf28-727cec533440/data` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/With_Trajectory/helios-array-calibration-reconciliation` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/With_Trajectory/iterative-solver-reconciliation` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/With_Trajectory/keyframe-interval-basis-reconcile-hk-67` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/With_Trajectory/ml-serving-rollout-reconcile` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/With_Trajectory/modulus-sieve-replay` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/With_Trajectory/moe-capacity-recompile-planner` | none | `2:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/With_Trajectory/pa-household-ledger-reconciliation-forge` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/With_Trajectory/patch-window-replay/data` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/With_Trajectory/plugin-linker-resolver` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/With_Trajectory/sc-seismic-array-recalibration-forge` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/With_Trajectory/segment-ledger-conform` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/With_Trajectory/slipway-overhaul-replan-repair` | none | `2:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/With_Trajectory/specdec-verification-engine` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/With_Trajectory/stall-graph-postmortem` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/With_Trajectory/survival-competing-risks` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2 numpy==2.1.3 scipy==1.14.1 scikit-learn==1.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/With_Trajectory/transcode-ladder-reconciliation` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/With_Trajectory/transparency-log-equivocation-audit` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/With_Trajectory/vault-evidence-archive-planner` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/More_Efforts/No_Trajectory/backup-consolidation-repair` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/More_Efforts/No_Trajectory/cohort-retention-reconciliation` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/More_Efforts/No_Trajectory/fused-attention-tile-schedule` | none | `5:    && pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/More_Efforts/No_Trajectory/least-grant-admission-solver` | none | `7:RUN pip install --no-cache-dir pytest==8.3.4 pytest-json-ctrf==0.3.5` | none | FAIL |
| `Anubis_Tasks_Samples/More_Efforts/No_Trajectory/residue-lattice-settlement` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/More_Efforts/With_Trajectory/archive-entry-path-authority-reconcile-hk-64` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/More_Efforts/With_Trajectory/assay-plate-triage` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/More_Efforts/With_Trajectory/assistant-budget-rollup-repair` | none | `7:RUN pip install --no-cache-dir pytest==8.3.4 pytest-json-ctrf==0.3.5` | none | FAIL |
| `Anubis_Tasks_Samples/More_Efforts/With_Trajectory/bitemporal-audit-ledger` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/More_Efforts/With_Trajectory/cadence-conform-audit` | none | `7:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.3` | none | FAIL |
| `Anubis_Tasks_Samples/More_Efforts/With_Trajectory/caldav-schedule-reconciliation/data` | none | `2:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/More_Efforts/With_Trajectory/caldermoor-commitment-closure` | none | `11:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/More_Efforts/With_Trajectory/evrp-tw-dynamic-charge-dispatch-nk-20260907` | none | `4:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/More_Efforts/With_Trajectory/fleet-snapshot-capacity-reconciliation` | none | `4:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/More_Efforts/With_Trajectory/gop-slice-recovery` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/More_Efforts/With_Trajectory/grain-intake-settlement` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/More_Efforts/With_Trajectory/grid-converged-parameter-report/data` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/More_Efforts/With_Trajectory/helion-array-performance-reconciliation` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/More_Efforts/With_Trajectory/meterflux-settlement-reconciler` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/More_Efforts/With_Trajectory/ml-streaming-tokenized-dataset` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/More_Efforts/With_Trajectory/nightfall-sentinel-crypto-reconcile` | none | `7:RUN pip install --no-cache-dir pytest==8.3.4 pytest-json-ctrf==0.3.5` | none | FAIL |
| `Anubis_Tasks_Samples/More_Efforts/With_Trajectory/optimizer-state-basis-resume-reconcile-hk-66` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/More_Efforts/With_Trajectory/playout-conform-avail-recompute` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/More_Efforts/With_Trajectory/residue-class-surface-reconcile-hk-79` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/More_Efforts/With_Trajectory/roastery-batch-replay/data` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/More_Efforts/With_Trajectory/security-hardened-crypto-ledger-lockdown` | none | `7:RUN pip install --no-cache-dir pytest==8.3.4 pytest-json-ctrf==0.3.5` | none | FAIL |
| `Anubis_Tasks_Samples/More_Efforts/With_Trajectory/sidereal-cohort-retention-analytics` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/More_Efforts/With_Trajectory/stream-partition-surface-reconcile-hk-77` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/More_Efforts/With_Trajectory/tilted-collector-flux-audit` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/More_Efforts/With_Trajectory/trust-anchor-surface-reconcile-hk-73` | none | `NO_PIP_LINE` | none | FAIL |
| `Anubis_Tasks_Samples/More_Efforts/With_Trajectory/yard-rehandle-ledger-recompute` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `Anubis_Tasks_Samples/Pass@1_New/Dinshi_Jain/Abdus Samad Ali/gm-arena-ladder-payout-reconciliation-forge` | ==1.105.0 | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0` | ==1.105.0 | PASS |
| `Anubis_Tasks_Samples/Pass@1_New/Dinshi_Jain/Abdus Samad Ali/h3-fleet-migration-scheduler-nk-20260907` | ==1.105.0 | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0` | ==1.105.0 | PASS |
| `Anubis_Tasks_Samples/Pass@1_New/Dinshi_Jain/Abdus Samad Ali/lane-dispatch-optimisation` | ==1.105.0 | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0` | ==1.105.0 | PASS |
| `Anubis_Tasks_Samples/Pass@1_New/Dinshi_Jain/Abdus Samad Ali/project-schedule-feasibility` | ==1.105.0 | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0` | ==1.105.0 | PASS |
| `Anubis_Tasks_Samples/Pass@1_New/Dinshi_Jain/Abdus Samad Ali/reminder-scope-surface-reconcile-hk-85` | ==1.105.0 | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0` | ==1.105.0 | PASS |
| `Anubis_Tasks_Samples/Pass@1_New/Dinshi_Jain/Abdus Samad Ali/reminder-store-reconciliation` | ==1.105.0 | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0` | ==1.105.0 | PASS |
| `Anubis_Tasks_Samples/Pass@1_New/Dinshi_Jain/Abdus Samad Ali/session-watermark-settlement` | ==1.105.0 | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0` | ==1.105.0 | PASS |
| `Anubis_Tasks_Samples/Pass@1_New/Dinshi_Jain/Abdus Samad Ali/wire-format-recovery` | ==1.105.0 | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0` | ==1.105.0 | PASS |
| `Anubis_Tasks_Samples/Pass@1_New/Poonam_Chourey/Aditya Jain/survey-raking-disclosure-audit` | ==1.105.0 | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0` | ==1.105.0 | PASS |
| `Anubis_Tasks_Samples/Pass@1_New/Poonam_Chourey/Aryan Mehta/clinical-assay-qc-recalibration-forge` | ==1.105.0 | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0` | ==1.105.0 | PASS |
| `Anubis_Tasks_Samples/Pass@1_New/Poonam_Chourey/Bhavik Jain/pretraining-token-ledger-closeout` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 openpyxl==3.1.5 python-docx==1.1.2 lxml==5.3.0 pypdf==5.1.0 pdfplumber==0.11.4 pyarrow==17.0.0 PyYAML==6.0.2 icalendar==6.0.1 reportlab==4.2.5` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/Pass@1_New/Poonam_Chourey/Bhavik Jain/sentinel-fraud-training-release` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 openpyxl==3.1.5 python-docx==1.1.2 lxml==5.3.0 pypdf==5.1.0 pdfplumber==0.11.4 pyarrow==17.0.0 PyYAML==6.0.2 icalendar==6.0.1 tomli==2.0.1 reportlab==4.2.5` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/Pass@1_New/Poonam_Chourey/Bhavik Jain/slo-credit-closeout` | ==1.105.0 | `4:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0 openpyxl==3.1.5 python-docx==1.1.2 lxml==5.3.0 pypdf==5.1.0 pdfplumber==0.11.4 pyarrow==17.0.0 PyYAML==6.0.3 icalendar==6.0.1 tomli==2.0.1 reportlab==4.2.5` | ==1.105.0 | PASS |
| `Anubis_Tasks_Samples/Pass@1_New/Poonam_Chourey/Harsh Gupta/6090aa67-183f-5d64-955f-8fb51ecb043e` | ==1.105.0 | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0` | ==1.105.0 | PASS |
| `Anubis_Tasks_Samples/Pass@1_New/Poonam_Chourey/Harsh Gupta/collateral-gated-settlement-ladder` | ==1.105.0 | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0` | ==1.105.0 | PASS |
| `Anubis_Tasks_Samples/Pass@1_New/Poonam_Chourey/Shivendra Shukla/iterative-solver-reconciliation` | ==1.105.0 | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0` | ==1.105.0 | PASS |
| `Anubis_Tasks_Samples/Pass@1_New/Sugam_Agrawal/Nikhil Bansal/cli-config-01` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/Pass@1_New/Sugam_Agrawal/Nikhil Bansal/policy-convergence-dataproc-21` | ==1.105.0 | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0` | ==1.105.0 | PASS |
| `Anubis_Tasks_Samples/Pass@1_New/Sugam_Agrawal/Nikhil Bansal/sec-firewall-policy-converge` | ==1.105.0 | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0` | ==1.105.0 | PASS |
| `Anubis_Tasks_Samples/Pass@1_New/Sugam_Agrawal/Nikhil Bansal/sec-sealed-posture-compile-forge` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_17_10_2026/Aryan Mehta/bastion-access-audit` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_17_10_2026/Aryan Mehta/clinical-assay-batch-reconciliation` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_17_10_2026/Aryan Mehta/clinical-assay-qc-recalibration-forge` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_17_10_2026/Aryan Mehta/commerce-normalization-02` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_17_10_2026/Aryan Mehta/depot-charge-ledger` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_17_10_2026/Aryan Mehta/halberd-query-plan-accounting` | none | `7:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_17_10_2026/Ayush_Sah/7ef8d80a-fea7-5d9e-b426-bcabfc6802ec` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_17_10_2026/Ayush_Sah/caldermoor-commitment-closure` | none | `12:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_17_10_2026/Ayush_Sah/cohort-retention-reconciliation` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_17_10_2026/Ayush_Sah/cohort-uplift-reconciliation` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_17_10_2026/Ayush_Sah/dispatch-plan-reoptimization` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_17_10_2026/Ayush_Sah/emberforge-vault-settlement` | none | `7:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aakarsh_Kumar/assay-plate-triage` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aakarsh_Kumar/brawl-ladder-settlement` | none (litellm named in a comment only) | `10:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aakarsh_Kumar/calorimeter-network-inference` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aakarsh_Kumar/dc48a092-3f5d-5981-a8bd-e82d5530fe9d` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aakarsh_Kumar/fleet-rollout-audit` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aakarsh_Kumar/fleet-snapshot-capacity-reconciliation` | none | `4:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aakarsh_Kumar/optimization-tick-aggregation-perf` | none (litellm named in a comment only) | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aakarsh_Kumar/refinery-blend-optimization-01` | none (litellm named in a comment only) | `11:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aakarsh_Kumar/render-track-surface-reconcile-hk-82` | none (litellm named in a comment only) | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aakarsh_Kumar/slipway-overhaul-replan-repair` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aakarsh_Kumar/stall-graph-postmortem` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aakarsh_Kumar/tensor-packet-admission-recovery` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aakarsh_Kumar/thornevale-uplift-appraisal` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Abdus Samad Ali/gm-arena-ladder-payout-reconciliation-forge` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | none | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Abdus Samad Ali/h3-fleet-migration-scheduler-nk-20260907` | none | `7:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | none | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Abdus Samad Ali/inference-gate-replay` | none (litellm named in a comment only) | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | none | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Abdus Samad Ali/lane-dispatch-optimisation` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | none | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Abdus Samad Ali/least-grant-admission-solver` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | none | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Abdus Samad Ali/project-schedule-feasibility` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | none | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Abdus Samad Ali/quillfen-sla-settlement-repair` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | none | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Abdus Samad Ali/reactor-thermal-hydraulic-balance` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | none | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Abdus Samad Ali/reminder-scope-surface-reconcile-hk-85` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | none | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Abdus Samad Ali/reminder-store-reconciliation` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | none | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Abdus Samad Ali/roastery-batch-replay/data` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | none | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Abdus Samad Ali/session-watermark-settlement` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | none | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Abdus Samad Ali/telemetry-rollup-recompute` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | none | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aditya Jain/18b5d99f-d4de-5e08-bb90-aeae31d33b3e` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | none | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aditya Jain/4e759599-27ea-59a0-9b7b-228efcc834a8` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | none | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aditya Jain/ability-loadout-surface-reconcile-hk-81` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | none | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aditya Jain/amp-mixed-precision-loss-scaling-correction` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 torch==2.6.0 numpy==1.26.4 pyyaml==6.0.1` | none | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aditya Jain/checkpoint-promotion-fixpoint` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | none | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aditya Jain/ee632e0e-3bbc-553e-a0f4-fdd2e9061931` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | none | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aditya Joshi/6cad24be-642d-597d-ab35-6eb5a919951b` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aditya Joshi/epi-exposure-survival-reconcile-forge` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aditya Joshi/fcc-multi-jurisdiction-sales-settlement` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aditya Joshi/fenmarch-intervention-settlement` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aditya Joshi/fused-attention-tile-schedule` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aditya Joshi/gateway-reentrancy-deadlock-auditor` | none | `4:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aditya Joshi/meridian-grid-tariff-reconciliation` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aditya Joshi/ml-domain-marl-quantized-federated-v1` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aditya Joshi/moe-capacity-recompile-planner` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aditya Joshi/residue-lattice-reconciliation` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aditya Joshi/shadowgate-authz-bypass` | none (litellm named in a comment only) | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | none | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aditya Joshi/temporal-dependency-risk-ledger` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | none | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aditya Joshi/tilted-collector-flux-audit` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aditya_Patel/07d51b69-db0c-57ed-9208-bcb7a5a3fd47` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aditya_Patel/archive-retention-settlement-hk-94` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aditya_Patel/brine-loop-lithium-yield-reconciliation` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aditya_Patel/cadence-conform-audit` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aditya_Patel/cf9b2067-1ba0-5bab-a1ea-83e976851e6c` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aditya_Patel/chrono-ledger-compiler` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aditya_Patel/commitment-ledger-reconstruction` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aditya_Patel/ninefold-crown-settlement-recompute` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aditya_Patel/security-vault-retention-arbiter` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aditya_Patel/tracehop-span-repair` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aniket Datta/admission-hardening-config-forge` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aniket Datta/archive-member-surface-reconcile-hk-75` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aniket Datta/backup-consolidation-repair` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aniket Datta/checkpoint-compaction-recompute` | none | `9:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aniket Datta/daybreak-routine-dispatch-recompute` | none | `7:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aniket Datta/f327a79b-42db-55ad-bf28-727cec533440` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aniket Datta/geodetic-network-lsq-variance-reconcile-forge` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aniket Datta/meridian-neutron-activation-reconciliation` | none (litellm named in a comment only) | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aniket Datta/nightfall-sentinel-crypto-reconcile` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aniket Datta/partition-snapshot-query-replay` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aniket Datta/security-cli-crypto-policy-baseline` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aniket Datta/spectral-collocation-reconciliation` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aniket Datta/transparency-log-equivocation-audit` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Anjali_kumari/airport-turnaround-packet-compiler` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | none | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Anjali_kumari/clinic-billing-reconciliation-report` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | none | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Anjali_kumari/committed-tree-manifest-reconcile-hk-36` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Anjali_kumari/fdc5a20d-2dfe-5f64-a3fa-2c023318a760` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Anjali_kumari/journal-replay-fault-repair` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | none | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Anjali_kumari/meridan-streaming-moment-rollup` | none | `4:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Anjali_kumari/model-training-checkpoint-calibration` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Anjali_kumari/modular-congruence-settlement` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Anjali_kumari/monorepo-dependency-reconciliation` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Anjali_kumari/runtime-config-derivation-repair` | none | `7:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Anjali_kumari/sysadmin-quota-reconcile-01` | none | `4:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Anjali_kumari/transcode-ladder-reconciliation` | none | `7:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aryan Mehta/caldav-schedule-reconciliation` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aryan Mehta/lsm-compaction-ledger-repair` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aryan Mehta/ml-inference-metric-reconciliation` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aryan Mehta/raceshuttle-volume-compiler` | none | `9:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aryan Mehta/release-line-support-ledger` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aryan Mehta/relocation-moveout-reconcile` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Aryan Mehta/sidereal-cohort-retention-analytics` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Ayush_Sah/numeric-reduction-benchmark-forge` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Ayush_Sah/pcggc-multi-state-rec-settlement` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Ayush_Sah/season-ladder-settlement` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Ayush_Sah/sensor-network-lsq-correlated-adjustment` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Ayush_Sah/sentinel-policy-recompute` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 ; 6:RUN pip install --no-cache-dir pyarrow==18.1.0` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Ayush_Sah/specdec-verification-engine` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Harsh_Gupta/6090aa67-183f-5d64-955f-8fb51ecb043e` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Harsh_Gupta/81435bd4-3eec-5fcb-b0da-dbc1500c2d7c` | none | `10:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Harsh_Gupta/batch-schedule-cost-reconciliation` | none | `4:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Harsh_Gupta/catalog-temporal-rollup` | none | `8:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Harsh_Gupta/gm-roguelite-run-economy-reconciliation-forge` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Harsh_Gupta/groundlink-contact-settlement` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Harsh_Gupta/kestrel-run-scrutineer` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Harsh_Gupta/manifest-tree-reconciliation` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Harsh_Gupta/meterflux-settlement-reconciler` | none | `8:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Harsh_Gupta/plugin-capability-registration-reconcile-hk-63` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Harsh_Gupta/security-hardened-crypto-ledger-lockdown` | none | `9:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Harsh_Gupta/serving-route-surface-reconcile-hk-80` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Harsh_Gupta/watershed-load-settlement-audit` | none (litellm named in a comment only) | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Harshank_kanungo/5a9af8bf-ad23-50a3-ab15-2bef1b62f30f` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Harshank_kanungo/archive-entry-path-authority-reconcile-hk-64` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Harshank_kanungo/blend-merit-allocation` | none | `4:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Harshank_kanungo/continued-fraction-ledger-reconciliation` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Harshank_kanungo/feature-materialization-delta` | none (litellm named in a comment only) | `7:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Harshank_kanungo/fleet-resource-governance` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Harshank_kanungo/grain-intake-settlement` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Harshank_kanungo/helios-array-calibration-reconciliation` | none | `7:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Harshank_kanungo/marrowgate-interval-restatement` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Harshank_kanungo/metering-settlement-audit` | none (litellm named in a comment only) | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Harshank_kanungo/se-buildfarm-cost-reconciliation` | none | `4:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Harshank_kanungo/survival-competing-risks` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 \` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Harshank_kanungo/vantage-session-assembly` | none (litellm named in a comment only) | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Kunwar_Singh/abr-segment-shaping-ctl` | none | `9:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Kunwar_Singh/cdc-ingest-window-settlement` | none | `10:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Kunwar_Singh/detector-flux-reconciliation-forge` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Kunwar_Singh/dual-price-basis-reconcile-hk-68` | none | `7:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Kunwar_Singh/feature-pipeline-config-ctl` | none | `9:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Kunwar_Singh/fleet-reservation-drain-plan` | none | `7:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Kunwar_Singh/grid-dispatch-optimization` | none | `4:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Kunwar_Singh/household-contingency-planner` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Kunwar_Singh/keyframe-interval-basis-reconcile-hk-67` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Kunwar_Singh/ml-streaming-tokenized-dataset` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Kunwar_Singh/registry-lock-footprint-resolution` | none | `7:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Kunwar_Singh/restoration-cadence-settlement` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Kunwar_Singh/yard-rehandle-ledger-recompute` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Nikhil_Bansal/dabebf7d-379d-5679-982d-0a288eca5de7` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Nikhil_Bansal/ensemble-timescale-recompute` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Nikhil_Bansal/evrp-tw-dynamic-charge-dispatch-nk-20260907` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Nikhil_Bansal/feature-pipeline-config-forge` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Nikhil_Bansal/ironvault-bastion-policy-reconcile` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Nikhil_Bansal/latency-optimal-workload-scheduler-calibration` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Nikhil_Bansal/meter-drift-reconstruction-repair` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Nikhil_Bansal/museum-touring-installation-dossier` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Nikhil_Bansal/nebula-federated-aggregation-audit` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Nikhil_Bansal/sc-radio-array-gain-recalibration-forge` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Nikhil_Bansal/segment-ledger-conform` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Nikhil_Bansal/strata-cartridge-recovery` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Nikhil_Bansal/warrant-token-gateway-audit` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Sanvi Gupta/assistant-budget-rollup-repair` | none | `8:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Sanvi Gupta/beamtime-custody-replay-repair` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Sanvi Gupta/brackwell-custody-materialization` | none | `11:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Sanvi Gupta/catalog-probe-replay` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Sanvi Gupta/fault-signature-surface-reconcile-hk-76` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Sanvi Gupta/playout-conform-avail-recompute` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Sanvi Gupta/plugin-linker-resolver` | none | `7:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Sanvi Gupta/secondlife-battery-allocation` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Sanvi Gupta/security-risk-ledger-reconciliation` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Sanvi Gupta/segment-timebase-authority-reconcile-hk-43` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Sanvi Gupta/strata-extent-relocation-planner` | none | `9:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Sanvi Gupta/temporal-graph-leakage-sampler` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 numpy==2.1.3 scipy==1.14.1 scikit-learn==1.5.2 pandas==2.2.3` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Sanvi Gupta/trainmix-allocation-certificate` | none | `4:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Shivendra_Shukla/7b219817-c863-5d7a-b0b9-b0274aa1175c` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Shivendra_Shukla/ae2bee53-13cc-54fc-930d-cfab8d5ca83a` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Shivendra_Shukla/coldchain-settlement-reconciliation` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Shivendra_Shukla/experiment-decision-ledger-reconciliation` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Shivendra_Shukla/iterative-solver-reconciliation` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Shivendra_Shukla/patch-window-replay` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Shivendra_Shukla/reelworks-transcode-config-forge` | none | `8:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Shivendra_Shukla/release-provenance-reconciliation` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Shivendra_Shukla/supply-allocation-reconciliation` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Shivendra_Shukla/trust-anchor-surface-reconcile-hk-73` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Shivendra_Shukla/vault-evidence-archive-planner` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Shivendra_Shukla/wistmoor-agenda-settlement` | none | `14:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Shivendra_Shukla/zero-trust-quorum-gate-configuration` | none (litellm named in a comment only) | `15:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Shubhi_Goyal/af406434-881e-5eed-8cdb-0c1f61694ef9` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Shubhi_Goyal/eventforge-scale` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Shubhi_Goyal/gop-slice-recovery` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Shubhi_Goyal/gop-vbv-conformance-audit` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Shubhi_Goyal/marrowgate-maintenance-orchestration` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Shubhi_Goyal/ml-drift-cohort-recalibration-forge` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Shubhi_Goyal/observatory-semester-block-allocation` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Shubhi_Goyal/omnichannel-ledger-reconciliation` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Shubhi_Goyal/optimization-mincost-optctl-a1` | none | `7:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Shubhi_Goyal/pa-envelope-budget-ledger-repair` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 PyYAML==6.0.2` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Shubhi_Goyal/pa-household-ledger-reconciliation-forge` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Shubhi_Goyal/plugin-loader-tls-arbiter` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Tarun Nautiyal/5a75ec1c-4d25-50b2-a448-2657814e4f90` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Tarun Nautiyal/af346080-1654-5b88-934f-e27fa27371ce` | none | `7:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Tarun Nautiyal/crash-fault-attribution-repair` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Tarun Nautiyal/cryogenic-energy-balance-repair` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Tarun Nautiyal/dedup-vault-catalog-repair` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Tarun Nautiyal/frame-packet-ledger-reconciliation` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Tarun Nautiyal/hardened-policy-config-repair` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Tarun Nautiyal/helion-array-performance-reconciliation` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Tarun Nautiyal/optimizer-state-basis-resume-reconcile-hk-66` | none | `7:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Tarun Nautiyal/pa-nutrient-ledger-reconciliation` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Tarun Nautiyal/pa-reminder-cadence-governor-forge` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Tarun Nautiyal/regional-anomaly-drift-reconciler` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_18_10_2026/Tarun Nautiyal/release-graph-reconciliation` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_19_10_2026/Abdus Samad Ali/nonce-vault-codec-recovery` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_19_10_2026/Abdus Samad Ali/packet-vault-codec-recovery` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_19_10_2026/Abdus Samad Ali/wire-format-recovery` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_19_10_2026/Anjali_kumari/crew-duty-ledger-repair` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_19_10_2026/Anjali_kumari/matchgate-session-ledger-replay` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_19_10_2026/Anjali_kumari/stream-watermark-attribution-replay` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_19_10_2026/Ayush_Sah/match-replay-desync-audit` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_19_10_2026/Nikhil Bansal/opt-cli-config-19oct` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_19_10_2026/Nikhil Bansal/opt-throughput-schedule-forge-19oct` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_19_10_2026/Nikhil Bansal/sealb-policy-compiler` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_19_10_2026/Shubhi_Goyal/gas-day-meter-settlement` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_19_10_2026/Shubhi_Goyal/oncall-rotation-resolver-repair` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_19_10_2026/Shubhi_Goyal/pa-larkspur-carpool-term-desk` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_19_10_2026/Swati_Sharma/92427898-6c8d-5a67-907d-e259a78b3721` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_19_10_2026/Swati_Sharma/a693e3d3-cba1-50a7-8870-462cf0f70b24` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_19_10_2026/Swati_Sharma/credential-scope-settlement-hk-90` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_19_10_2026/Swati_Sharma/host-budget-derivation-repair` | none | `7:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_19_10_2026/Swati_Sharma/ledger-settlement-netting` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_19_10_2026/Swati_Sharma/meridian-amr-field-consolidation` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_19_10_2026/Swati_Sharma/modulus-sieve-replay` | none | `7:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_19_10_2026/Swati_Sharma/reefer-power-dispatch-recompute` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_19_10_2026/Swati_Sharma/residue-class-surface-reconcile-hk-79` | none | `7:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_19_10_2026/Swati_Sharma/security-metric-reconciliation` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_19_10_2026/Swati_Sharma/stratified-boost-inference` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_19_10_2026/Swati_Sharma/stream-partition-surface-reconcile-hk-77` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/QC_Fixed_19_10_2026/Swati_Sharma/telemetry-throughput-optimizer` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Dinshi_Jain/Abdus Samad Ali/gm-arena-ladder-payout-reconciliation-forge` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.104.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Dinshi_Jain/Abdus Samad Ali/h3-fleet-migration-scheduler-nk-20260907` | none | `7:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.104.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Dinshi_Jain/Abdus Samad Ali/inference-gate-replay` | none (litellm named in a comment only) | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Dinshi_Jain/Abdus Samad Ali/lane-dispatch-optimisation` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Dinshi_Jain/Abdus Samad Ali/least-grant-admission-solver` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Dinshi_Jain/Abdus Samad Ali/nonce-vault-codec-recovery` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Dinshi_Jain/Abdus Samad Ali/packet-vault-codec-recovery` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.104.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Dinshi_Jain/Abdus Samad Ali/project-schedule-feasibility` | ==1.105.0 | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0` | ==1.105.0 | PASS |
| `Anubis_Tasks_Samples/stale_Pass@1/Dinshi_Jain/Abdus Samad Ali/quillfen-sla-settlement-repair` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | none | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Dinshi_Jain/Abdus Samad Ali/reactor-thermal-hydraulic-balance` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.104.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Dinshi_Jain/Abdus Samad Ali/reminder-scope-surface-reconcile-hk-85` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Dinshi_Jain/Abdus Samad Ali/reminder-store-reconciliation` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Dinshi_Jain/Abdus Samad Ali/session-watermark-settlement` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Dinshi_Jain/Abdus Samad Ali/telemetry-rollup-recompute` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Dinshi_Jain/Abdus Samad Ali/wire-format-recovery` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Dinshi_Jain/Aditya_Patel/cf9b2067-1ba0-5bab-a1ea-83e976851e6c` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Dinshi_Jain/Aditya_Patel/ninefold-crown-settlement-recompute` | ==1.105.0 | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0` | ==1.105.0 | PASS |
| `Anubis_Tasks_Samples/stale_Pass@1/Dinshi_Jain/Kunwar_Singh/8325e01e-19fe-56c8-8ec9-633754851d75` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Dinshi_Jain/Kunwar_Singh/9506acb0-5468-5907-bf1e-0036593e942e` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Dinshi_Jain/Kunwar_Singh/95c2eff0-f9fc-5201-b50d-26ddba238e97` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Dinshi_Jain/Kunwar_Singh/registry-lock-footprint-resolution` | ==1.105.0 | `7:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0` | ==1.105.0 | PASS |
| `Anubis_Tasks_Samples/stale_Pass@1/Dinshi_Jain/Swati_Sharma/modulus-sieve-replay` | none | `7:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Dinshi_Jain/Swati_Sharma/reefer-power-dispatch-recompute` | ==1.105.0 | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0` | ==1.105.0 | PASS |
| `Anubis_Tasks_Samples/stale_Pass@1/Dinshi_Jain/Swati_Sharma/telemetry-throughput-optimizer` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Poonam_Chourey/Aditya Jain/18b5d99f-d4de-5e08-bb90-aeae31d33b3e` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Poonam_Chourey/Aditya Jain/residue-lattice-settlement` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Poonam_Chourey/Aditya Jain/sentinel-privilege-attestation` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Poonam_Chourey/Aditya Jain/speculative-decode-arbiter` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Poonam_Chourey/Harsh_Gupta/6090aa67-183f-5d64-955f-8fb51ecb043e` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Poonam_Chourey/Harsh_Gupta/groundlink-contact-settlement` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Poonam_Chourey/Harsh_Gupta/plugin-capability-registration-reconcile-hk-63` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Poonam_Chourey/Harsh_Gupta/watershed-load-settlement-audit` | none (litellm named in a comment only) | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Poonam_Chourey/Shivendra Shukla/7b219817-c863-5d7a-b0b9-b0274aa1175c` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Poonam_Chourey/Shivendra Shukla/iterative-solver-reconciliation` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Poonam_Chourey/Shivendra Shukla/vault-evidence-archive-planner` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Poonam_Chourey/Shivendra Shukla/wistmoor-agenda-settlement` | none | `14:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Sugam_Agrawal/Aakarsh_Kumar/assay-plate-triage` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Sugam_Agrawal/Aakarsh_Kumar/calorimeter-network-inference` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Sugam_Agrawal/Aakarsh_Kumar/fleet-snapshot-capacity-reconciliation` | none | `4:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Sugam_Agrawal/Aakarsh_Kumar/tensor-packet-admission-recovery` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Sugam_Agrawal/Aakarsh_Kumar/thornevale-uplift-appraisal` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Sugam_Agrawal/Aakarsh_Kumar/xdp-zero-copy-cutover` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Sugam_Agrawal/Anjali_kumari/committed-tree-manifest-reconcile-hk-36` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Sugam_Agrawal/Anjali_kumari/fdc5a20d-2dfe-5f64-a3fa-2c023318a760` | ==1.105.0 | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0` | ==1.105.0 | PASS |
| `Anubis_Tasks_Samples/stale_Pass@1/Sugam_Agrawal/Anjali_kumari/modular-congruence-settlement` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Sugam_Agrawal/Anjali_kumari/stream-watermark-attribution-replay` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Sugam_Agrawal/Anjali_kumari/transcode-ladder-reconciliation` | none | `7:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Sugam_Agrawal/Ayush sah/cohort-retention-reconciliation` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Sugam_Agrawal/Ayush sah/dispatch-plan-reoptimization` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Sugam_Agrawal/Ayush sah/sensor-network-lsq-correlated-adjustment` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Sugam_Agrawal/Harshank_Kanungo/feature-materialization-delta` | none (litellm named in a comment only) | `7:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Sugam_Agrawal/Harshank_Kanungo/grain-intake-settlement` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Sugam_Agrawal/Harshank_Kanungo/helios-array-calibration-reconciliation` | none | `7:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Sugam_Agrawal/Harshank_Kanungo/marrowgate-interval-restatement` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Sugam_Agrawal/Harshank_Kanungo/metering-settlement-audit` | none (litellm named in a comment only) | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Sugam_Agrawal/Nikhil_Bansal/ensemble-timescale-recompute` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Sugam_Agrawal/Nikhil_Bansal/ironvault-bastion-policy-reconcile` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Sugam_Agrawal/Nikhil_Bansal/museum-touring-installation-dossier` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Sugam_Agrawal/Nikhil_Bansal/nebula-federated-aggregation-audit` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Sugam_Agrawal/Nikhil_Bansal/sc-radio-array-gain-recalibration-forge` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Sugam_Agrawal/Nikhil_Bansal/segment-ledger-conform` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Sugam_Agrawal/Shubhi_Goyal/ml-drift-cohort-recalibration-forge` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Sugam_Agrawal/Shubhi_Goyal/omnichannel-ledger-reconciliation` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Sugam_Agrawal/Shubhi_Goyal/pa-envelope-budget-ledger-repair` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 PyYAML==6.0.2` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Sugam_Agrawal/Shubhi_Goyal/pa-household-ledger-reconciliation-forge` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Anubis_Tasks_Samples/stale_Pass@1/Sugam_Agrawal/Shubhi_Goyal/plugin-loader-tls-arbiter` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `QC assigned/converted tasks/07d51b69-db0c-57ed-9208-bcb7a5a3fd47` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `QC assigned/converted tasks/7ef8d80a-fea7-5d9e-b426-bcabfc6802ec` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `QC assigned/converted tasks/caldermoor-commitment-closure` | none | `12:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `QC assigned/converted tasks/cohort-retention-reconciliation` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `QC assigned/converted tasks/cohort-uplift-reconciliation` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `QC assigned/converted tasks/dispatch-plan-reoptimization` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `QC assigned/converted tasks/emberforge-vault-settlement` | none | `7:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `QC assigned/converted tasks/match-replay-desync-audit` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `QC assigned/converted tasks/numeric-reduction-benchmark-forge` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `QC assigned/converted tasks/pcggc-multi-state-rec-settlement` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `QC assigned/converted tasks/season-ladder-settlement` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `QC assigned/converted tasks/sensor-network-lsq-correlated-adjustment` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `QC assigned/converted tasks/sentinel-policy-recompute` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 ; 6:RUN pip install --no-cache-dir pyarrow==18.1.0` | ==1.105.0 | FAIL |
| `QC assigned/converted tasks/specdec-verification-engine` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `QC assigned/my tasks/07d51b69-db0c-57ed-9208-bcb7a5a3fd47` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `QC assigned/my tasks/7ef8d80a-fea7-5d9e-b426-bcabfc6802ec` | none | `2:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `QC assigned/my tasks/caldermoor-commitment-closure` | none | `11:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `QC assigned/my tasks/cohort-retention-reconciliation` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `QC assigned/my tasks/cohort-uplift-reconciliation` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `QC assigned/my tasks/dispatch-plan-reoptimization` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `QC assigned/my tasks/emberforge-vault-settlement` | none | `7:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `QC assigned/my tasks/match-replay-desync-audit` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `QC assigned/my tasks/numeric-reduction-benchmark-forge` | none | `NO_PIP_LINE` | none | FAIL |
| `QC assigned/my tasks/pcggc-multi-state-rec-settlement` | none | `NO_PIP_LINE` | none | FAIL |
| `QC assigned/my tasks/season-ladder-settlement` | none | `NO_PIP_LINE` | none | FAIL |
| `QC assigned/my tasks/sensor-network-lsq-correlated-adjustment` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `QC assigned/my tasks/sentinel-policy-recompute` | none | `7:RUN pip install --no-cache-dir pytest==8.3.4 pytest-json-ctrf==0.3.5` | none | FAIL |
| `QC assigned/my tasks/specdec-verification-engine` | none | `3:RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2` | none | FAIL |
| `QC assigned/sales-csv-summary` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | none | FAIL |
| `Terminal_2.0_Harbor_Harness/Tasks_INPUT/7ef8d80a-fea7-5d9e-b426-bcabfc6802ec` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Terminal_2.0_Harbor_Harness/Tasks_INPUT/caldermoor-commitment-closure` | none | `12:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Terminal_2.0_Harbor_Harness/Tasks_INPUT/cf9b2067-1ba0-5bab-a1ea-83e976851e6c` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Terminal_2.0_Harbor_Harness/Tasks_INPUT/cohort-retention-reconciliation` | ==1.105.0 | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0` | ==1.105.0 | PASS |
| `Terminal_2.0_Harbor_Harness/Tasks_INPUT/cohort-uplift-reconciliation` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Terminal_2.0_Harbor_Harness/Tasks_INPUT/dispatch-plan-reoptimization` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Terminal_2.0_Harbor_Harness/Tasks_INPUT/district-heat-flex-procurement` | ==1.105.0 | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0` | ==1.105.0 | PASS |
| `Terminal_2.0_Harbor_Harness/Tasks_INPUT/emberforge-vault-settlement` | none | `7:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Terminal_2.0_Harbor_Harness/Tasks_INPUT/match-replay-desync-audit` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Terminal_2.0_Harbor_Harness/Tasks_INPUT/numeric-reduction-benchmark-forge` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Terminal_2.0_Harbor_Harness/Tasks_INPUT/pcggc-multi-state-rec-settlement` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Terminal_2.0_Harbor_Harness/Tasks_INPUT/schema-migration-plan-repair` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Terminal_2.0_Harbor_Harness/Tasks_INPUT/season-ladder-settlement` | none | `6:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Terminal_2.0_Harbor_Harness/Tasks_INPUT/sensor-network-lsq-correlated-adjustment` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Terminal_2.0_Harbor_Harness/Tasks_INPUT/sentinel-policy-recompute` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 ; 6:RUN pip install --no-cache-dir pyarrow==18.1.0` | ==1.105.0 | FAIL |
| `Terminal_2.0_Harbor_Harness/Tasks_INPUT/specdec-verification-engine` | none | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `Terminal_2.0_Harbor_Harness/Tasks_INPUT/vendor-archive-roundtrip-recovery` | ==1.105.0 | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0` | ==1.105.0 | PASS |
| `master_chat_work/bundles/_work/dispatch-plan-reoptimization/backup_p12_pre_233248` | ==1.105.0 | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0` | ==1.105.0 | PASS |
| `master_chat_work/bundles/_work/schema-migration-plan-repair/scaffold_orig` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `master_chat_work/bundles/_work/vendor-archive-roundtrip-recovery/scaffold_orig` | none | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1` | ==1.105.0 | FAIL |
| `master_chat_work/bundles/cohort-retention-reconciliation` | ==1.105.0 | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0` | ==1.105.0 | PASS |
| `master_chat_work/bundles/dispatch-plan-reoptimization` | ==1.105.0 | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0` | ==1.105.0 | PASS |
| `master_chat_work/bundles/district-heat-flex-procurement` | ==1.105.0 | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0` | ==1.105.0 | PASS |
| `master_chat_work/bundles/emberforge-vault-settlement` | ==1.105.0 | `7:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0` | ==1.105.0 | PASS |
| `master_chat_work/bundles/schema-migration-plan-repair` | ==1.105.0 | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0` | ==1.105.0 | PASS |
| `master_chat_work/bundles/sensor-network-lsq-correlated-adjustment` | ==1.105.0 | `3:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0` | ==1.105.0 | PASS |
| `master_chat_work/bundles/vendor-archive-roundtrip-recovery` | ==1.105.0 | `5:RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0` | ==1.105.0 | PASS |

## Step 4: Suspicious traces

These ran because a SUSPECT was found. Only names and dates were collected, never contents.

| Location | Finding |
|---|---|
| `~/.ssh` | Nothing modified on or after 21 Oct. The newest entries are `agent` (17 Oct 02:39), `known_hosts` (14 Oct 00:44), `config` (14 Oct) and key files (13 to 14 Oct). |
| `~/.aws` | Does not exist. |
| `~/Library/LaunchAgents` | One file modified after 21 Oct: `com.amazon.codewhisperer.launcher.plist`, at 2026-10-23 09:44:33. It is most likely the Amazon Q / CodeWhisperer updater, but it falls in the window, so check it by hand. The other files are `com.ayush.cursor-api-proxy.plist` and `com.ayush.cursor-chat-proxy.plist` (14 Oct) and three Google plists (8 Oct). |
| `crontab -l` | `no crontab for mac` |

## Not checked, and why

- **What the payload actually did.** `cook.py` and `sitecustomize.py` look encoded (`exec` plus `base64`). Decoding them would mean running or reconstructing code, which the read-only rules forbid. So I cannot say which keys or files it read, or where it sent them. Assume every secret reachable from that process on 21 Oct around 17:34 to 17:36 is exposed: environment variables, `.env` files in the working folder, and the harbor and OpenAI/Anthropic/HF/AWS credentials.
- **Contents of the pip HTTP cache.** `~/Library/Caches/pip/http*` entries are stored under hashed names. A search by file name cannot rule out a cached 1.107.0 download. No pip-installed site-packages anywhere has a litellm dist-info.
- **Network and process evidence.** The rules forbid network calls, and nothing reports which hosts were contacted, so I could not confirm a call to the cloud metadata endpoint (169.254.169.254). On a Mac with no cloud metadata service, that call would fail anyway. I did not inspect running processes, unified logs or firewall logs, because they were outside the brief.
- **Docker images and containers.** These were not rechecked. The master chat already checked Docker storage on 22 Oct at 13:08 and found no 1.107.0. A `docker run` or build would also break the rules.
- **Locations that do not exist**: `/opt/homebrew/lib/python3*`, `/Library/Frameworks/Python.framework`, `~/.pyenv`, `~/.openhands`.
- **Search depth.** Searches used `-maxdepth 8`, as the brief asked. A litellm install nested deeper than 8 levels below a search root would be missed. I also ran a payload-file search (`cook.pth`, `sitecustomize.py`, `usercustomize.py`) over `~/.local`, `~/.cache`, `~/Library/Python`, `~/.config` and the Terminal Bench folder, and it found only environment 5 and the cached wheel.
- **Environments outside the listed roots**, such as Conda, system `/usr/bin/python3` site-packages and other users' homes, were not searched. Only `~/Library/Python` and `~/.config` were added beyond the brief.
