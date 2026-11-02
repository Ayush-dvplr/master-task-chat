# RUN_LOG

All times IST, 2026-10-20. SCRATCH = `/tmp/plgen-analysis-20261020T2228`, LOGS = `/tmp/opencode-logs/plgen-analysis-20261020T2228`, SRC = `"$SCRATCH/src/Input Bundle Generator New"` (copy of SOURCE, with `Input_Bundle_QC` copied beside it). All generator/validator runs used the copy with `PYTHONDONTWRITEBYTECODE=1` and `IBG_MEMORY_PATH=$SCRATCH/memory/ideas.jsonl` unless noted.

| # | Command | Exit / result |
|---|---|---|
| 1 | `git rev-parse HEAD; git status --short .` in SOURCE (read-only) | 0; HEAD 1096b2447dd4; untracked `ayush sah tasks/`, `memory/` |
| 2 | `git log -15 --stat -- "Input Bundle Generator New"`, `git log -15 --skip=6`, `git show 1096b244 -- …` | 0 |
| 3 | `python3 $SCRATCH/fp.py SOURCE REPORT/fingerprint.json` | 0; 226 files hashed |
| 4 | `cp -R SOURCE "$SCRATCH/src/"; cp -R Input_Bundle_QC "$SCRATCH/src/"` | 0 |
| 5 | `nohup $SCRATCH/gen_all.sh` (first pass, `--author "Test Author <test.author@ethara.ai>"`): 8× `generate_bundle.py --out $SCRATCH/out --archetype A --category C --seed S --name A-sS` | gen exit 0 ×8; validate exit 1 ×8 (only FAIL: QC T14 placeholder author name) |
| 5a | same script: determinism regen of data-pipeline s303 and format-recovery s505 into `out_det` (separate ledger), `diff -r` | gen 0, diff 0 (byte-identical) ×2 |
| 5b | `generate_bundle.py --category games --seed 20260811` (auto, `IBG_MEMORY=off`) | 0; archetype format-recovery (auto) |
| 5c | `generate_bundle.py --category file-operations --seed 4058222581` (auto) | 0; archetype format-recovery (auto) |
| 5d | `generate_bundle.py --archetype data-pipeline --category data-processing --seed 303 --name dup-check` | 1; memory refuses same archetype+seed |
| 5e | `generate_bundle.py --archetype data-pipeline --seed 9` (no `--author`) | 2; "--author is required" |
| 6 | Regenerate the 8 with `--author "Priya Raman <priya.raman@ethara.ai>"` then `validate_bundle.py <bundle>` (strict default) | see table below |
| 7 | `python3 $SCRATCH/measure.py $SCRATCH/out $SCRATCH/measure.json` | 0 |
| 8 | `playground.py <bundle> --skip-docker --json …` ×8 | 0 ×8; PASS, 0 FAIL; WARN A2 on build-repair, data-pipeline, performance, repo-patch |
| 9 | `nohup playground.py $SCRATCH/out/format-recovery-s505 --json …` (Docker) | 0; D1 oracle 1.0, D2 nop 0.0, D3 stub 0.0, D4 ablate capture log 0.8333; PASS |
| 10 | `nohup python3 -m unittest discover -s tests -v` in SRC with `IBG_MEMORY=off` | 0; 59 tests OK in 47.7 s |
| 11 | Static inspection scripts (criteria/judge totals, instruction shape, data heads) on generated bundles | 0 |
| 12 | `python3 -m json.tool` on the 5 JSON deliverables; re-hash SOURCE vs fingerprint; `git status --short` on SOURCE | see end of file |

Step 6 detail (generation and validation, all with the real-shaped author):

| Archetype | --category | --seed | gen exit | validate exit | SUMMARY |
|---|---|---|---|---|---|
| build-repair | software-engineering | 101 | 0 | 0 | 39 passed, 0 failed, 0 warnings (13 INFO) |
| cli-config | system-admin | 202 | 0 | 0 | 41 passed, 0 failed, 0 warnings (11 INFO) |
| data-pipeline | data-processing | 303 | 0 | 0 | 40 passed, 0 failed, 0 warnings (12 INFO) |
| domain-calculation | mathematics | 404 | 0 | 0 | 40 passed, 0 failed, 0 warnings (12 INFO) |
| format-recovery | security | 505 | 0 | 0 | 49 passed, 0 failed, 0 warnings (3 INFO) |
| performance | optimization | 606 | 0 | 0 | 40 passed, 0 failed, 0 warnings (12 INFO) |
| repo-patch | debugging | 707 | 0 | 0 | 41 passed, 0 failed, 0 warnings (11 INFO) |
| service-interaction | machine-learning | 808 | 0 | 0 | 41 passed, 0 failed, 0 warnings (11 INFO) |

Not run: `harbor run`, `validate_bundle.py --semantic`, `playground.py --model`, Docker playground for 7 of 8 archetypes.

Subagents: two read-only `explore` agents read `templates/` (group 1: build-repair, cli-config, data-pipeline, domain-calculation; group 2: format-recovery, performance, repo-patch, service-interaction). Their counts were replaced with measured values where they differed.

Final checks (step 12):
- `python3 -m json.tool` on archetypes.json, validator_rules.json, bundle_schema.json, hardness.json, fingerprint.json: all exit 0.
- Re-hash of SOURCE (226 files) against fingerprint.json: UNCHANGED.
- `git status --short -- "Input Bundle Generator New"`: only the two pre-existing untracked entries (`ayush sah tasks/`, `memory/`); HEAD still 1096b2447dd4.
- No leftover `ibg-*` Docker images.
- `rm -rf /tmp/plgen-analysis-20261020T2228` (SCRATCH deleted). Logs kept in `/tmp/opencode-logs/plgen-analysis-20261020T2228/`.
