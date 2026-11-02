# RUN_LOG: research kit audit, 2026-10-20 (IST)

SCRATCH `/tmp/research-kit-analysis-20261020T2301/` (deleted at the end), LOGS
`/tmp/opencode-logs/research-kit-analysis-20261020T2301/` (kept). SOURCE paths are relative to
`/Users/mac/Desktop/Terminal Bench/research/`. Nothing was written outside SCRATCH, LOGS and REPORT OUT.

| # | Time IST (approx.) | Command (abridged) | Exit | Result / log |
|---|---|---|---|---|
| 1 | 23:01 | `mkdir -p` SCRATCH, LOGS, REPORT OUT; `find research -type f \| wc -l`; `du -sh` | 0 | 274 files, 1.9M |
| 2 | 23:02 | `find . -type f -print0 \| sort -z \| xargs -0 shasum -a 256 > SCRATCH/hash_before.txt` (in SOURCE) | 0 | 274 lines |
| 3 | 23:03 | `harbor --version`; `uv tool list`; `pip3 show harbor-rewardkit`; harbor python `importlib.metadata.version('harbor-rewardkit')` | 0 / 0 / 1 / 1 | 0.24.0; tools: harbor only; rewardkit not installed; found in uv cache `archive-v0/uZX90PsFgbA2_FvK` (0.2.1) |
| 4 | 23:04 | `zsh SCRATCH/rerun.zsh` (nohup): version, `harbor task schema`, 4 x `harbor task init` (single, `--steps 2`, `--include-canary-strings`, `--no-pytest --no-solution --no-package`), 76 x `COLUMNS=200 harbor <cmd> --help`, `harbor run --help`, `harbor lint --help`, `harbor check --help`, with `shasum`, `cmp`, `diff -r`, `diff -rq` | 0 (inner: schema 0, inits 0/0/0/0, lint 2, check 0) | `rerun.log`: schema sha identical; scaffolds identical to `_scaffold-0.24` and `_scaffold-0.23`; allhelp identical; run help identical; lint absent |
| 5 | 23:06 | `sed -n` / `grep -n` on installed `harbor/` source (task.py, trial.py, verifier_mode.py, verifier.py, oracle.py, multi_step.py, config.py, paths.py, job.py, artifact_handler.py, docker.py) | 0 | line cites in REPORT and claims.json |
| 6 | 23:07 | `grep` rewardkit cache `models.py`, `session.py`, `METADATA` | 0 | `extra="forbid"`; `description.format`; Version 0.2.1 |
| 7 | 23:08 | `diff -rq "QC assigned/Input_Bundle_QC" Terminal_2.0_Harbor_Harness/Input_Bundle_QC`; `git -C Terminal_2.0_Harbor_Harness log --oneline -1` / `-3 -- Input_Bundle_QC`; `git status --short Input_Bundle_QC` | 0 | no difference; HEAD 9b8229f6; clean |
| 8 | 23:09 | `cp -R` examples/single-step, examples/multi-step, generator `district-heat-flex-procurement` into SCRATCH/bundles; fill generator `data-pipeline/task.toml` placeholders into SCRATCH | 0 | - |
| 9 | 23:09 | harbor python `SCRATCH/traps.py` (parser edge cases, step timeout, strategy default, canary strip, QC template under `TaskConfig`, `Task.is_valid_dir` x3) | 0 | `traps.log` |
| 10 | 23:10 | harbor python `_evidence/0.24/keycheck.py` on filled QC template | 0 | OK: all keys known to the schema |
| 11 | 23:10 | `python3 QC/{structure,instruction,tests,judge}_qc.py` on 3 bundle copies | single: 1/1/1/2; multi: 1/2/2/2; district: 0/0/0/0 | `qc_on_bundles.log` (50 and 51 structure FAILs on the kit examples) |
| 12 | 23:11 | nohup `harbor run -p SCRATCH/bundles/{single,multi}-step -a {oracle,nop} -e docker -o SCRATCH/jobs --job-name rk-*-2310 -y` (4 runs, chained) | 0/0/0/0 | `single-oracle.log` etc.; rewards 1.0/0.0/1.0/0.0, 0 exceptions |
| 13 | 23:13 | `ls -l` re-scaffolded scripts; `grep` regrade help; `cat` scaffold test.sh | 0 | `-rw-r--r--`; pins pytest 8.4.1, ctrf 0.3.5, uv 0.9.7 |
| 14 | 23:14 | `ls -d` kit leftovers (`/tmp/harbor-v024`, `/tmp/opencode-logs/{jobs,half-final,half-mean,legacytask,scaffold-check,bad task}`) | 0 | all 7 present |
| 15 | 23:15 | `zsh SCRATCH/checklist-test.zsh` (kit script, keycheck and JOBS paths moved to SCRATCH) on both example copies | 0 | `checklist-test.log`; same heading/rc sequence as the kit's first 122 lines; B8 dry run OK x2 |
| 16 | 23:15 | `python3 QC/exe_copy.py SCRATCH/bundles/district-heat-flex-procurement SCRATCH/step10run` | 0 | `exe_copy.log` |
| 17 | 23:16 | nohup `harbor run --path SCRATCH/step10run --agent {oracle,nop} --env docker -o SCRATCH/jobs --job-name rk-dh-*-2320 -y` | 0/0 | `dh-oracle.log`, `dh-nop.log`: 1.0 / 0.0, rewardkit wrote reward.json + reward-details.json |
| 18 | 23:16 | `grep` harbor METADATA, schema `headers`, MCP/skills preflight; `TaskConfig` shared + `[verifier.environment]` | 0 / ValidationError (expected) | Requires-Python >=3.12; semver etc.; headers 0; preflight trial.py:1619-1627 |
| 19 | 23:17 | `python3 SCRATCH/make_claims.py`; `python3 SCRATCH/make_hvq.py`; `python3 -m json.tool` both | 0 / 0 / 0 / 0 | 88 claims (75/2/11); 47 rows |
| 20 | 23:19 | re-hash SOURCE (`shasum -a 256`, same pipeline as #2), `cmp hash_before.txt hash_after.txt`, write `fingerprint.json`, `python3 -m json.tool` on claims/harbor_vs_qc/fingerprint, `docker ps -a` (no leftover task containers), `rm -rf` SCRATCH | 0 | SOURCE_UNCHANGED (274 files); 3 x JSON OK; SCRATCH removed |

No `harbor run` used a real agent or model; no `--upload`, `--share`, `publish`, `auth`; no git
write command; no outbound fetch of project content.
