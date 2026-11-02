# RUN_LOG (qc-analysis-20261020T2228)

SCRATCH: `/tmp/qc-analysis-20261020T2228/` (deleted at the end). LOGS: `/tmp/opencode-logs/qc-analysis-20261020T2228/`. All times are IST, 2026-10-20.

| # | Command (cwd) | Exit | Result |
|---|---|---|---|
| 1 | `date; git rev-parse HEAD; git status --short -- Input_Bundle_QC; ls -la Input_Bundle_QC; wc -l Input_Bundle_QC/*` (clone) | 0 | HEAD 1096b244, status clean, 12 files / 6473 lines |
| 2 | `mkdir -p SCRATCH LOGS reports/qc` | 0 | |
| 3 | `git log --oneline -15 -- Input_Bundle_QC; git log -1 --format=%H%n%ci; git branch --show-current` | 0 | branch main |
| 4 | `wc -l validate_bundle.py generate_bundle.py; git log --oneline -5 -- .; python3 --version; generate_bundle.py --help` (GEN) | 0 | Python 3.14.8 |
| 5 | `grep -n memory/write_text generate_bundle.py; generate_bundle.py --help` (GEN, read-only) | 0 | found ledger write in GEN/memory, so IBG_MEMORY=off |
| 6 | `cp -R Input_Bundle_QC SCRATCH/qc; cp -R "Input Bundle Generator New" SCRATCH/gen` | 0 | |
| 7 | `IBG_MEMORY=off PYTHONDONTWRITEBYTECODE=1 nohup python3 generate_bundle.py --out SCRATCH/out --seed 20261020 --name qc-probe-bundle --author "Ram Lakhan <ram.lakhan@ethara.ai>"` (SCRATCH/gen) | 0 | data-pipeline, category system-admin (log generate.log) |
| 8 | `mv SCRATCH/qc SCRATCH/Input_Bundle_QC` (so VB's sibling QC_DIR resolves inside SCRATCH) | 0 | |
| 9 | `generate_bundle.py --out SCRATCH/out --seed 20261020 --name qc-probe-default` (no --author) | 2 | "ERROR: --author is required: QC FC-S18 fails an empty [task].authors" |
| 10 | `generate_bundle.py ... --name qc-probe-fmt --archetype format-recovery --author "Ram Lakhan <ram.lakhan@ethara.ai>"` | 0 | tag NETST, ext .psnp |
| 11 | `structure_qc.py out/qc-probe-bundle` | 0 | 17 pass, 0 warn, 0 fail |
| 12 | `instruction_qc.py out/qc-probe-bundle` | 0 | 5 pass, 1 warn (C6), 0 fail |
| 13 | `tests_qc.py out/qc-probe-bundle` | 0 | 35 pass, 0 warn, 0 fail |
| 14 | `judge_qc.py out/qc-probe-bundle` | 0 | 19 pass, 0 warn, 0 fail |
| 15 | `gen/validate_bundle.py out/qc-probe-bundle` | 0 | 40 passed, 0 failed, 0 warnings, GATE PASS |
| 16 | `exe_copy.py out/qc-probe-bundle SCRATCH/step10-qc-probe-bundle` | 0 | weight 1/51; 4 network roles public; openhands RUN dropped |
| 17 | `exe_copy.py out/qc-probe-bundle SCRATCH/stub-qc-probe-bundle --stub` | 0 | stub with 14 empty artifacts |
| 18 | `structure_qc.py out/qc-probe-fmt` | 0 | 17/0/0 |
| 19 | `instruction_qc.py out/qc-probe-fmt` | 0 | 5/1 (C6)/0 |
| 20 | `tests_qc.py out/qc-probe-fmt` | 0 | 35/0/0 |
| 21 | `judge_qc.py out/qc-probe-fmt` | 0 | 19/0/0 |
| 22 | `gen/validate_bundle.py out/qc-probe-fmt` | 0 | 49 passed, GATE PASS |
| 23 | `exe_copy.py out/qc-probe-fmt SCRATCH/step10-qc-probe-fmt` | 0 | weight 1/72 |
| 24 | `exe_copy.py out/qc-probe-fmt SCRATCH/stub-qc-probe-fmt --stub` | 0 | |
| 25 | `grep` over probe instruction.md / TRUTH.md / judge.toml / test_output.py (SCRATCH) | 0 | manual-gate evidence for REPORT section I |
| 26 | `git log -15 --numstat -- Input_Bundle_QC; git log --format=%ci -- Input_Bundle_QC \| wc -l` (clone) | 0 | 39 commits since 2026-08-10 |
| 27 | `git show 92295542 / 263361e0 / 3e8feaca -- <gate files> \| grep ID` (first attempt) | 1 | zsh: unquoted `===` read as a command; reran quoted |
| 28 | same, quoted; `git status --short -- Input_Bundle_QC "Input Bundle Generator New"` | 0 | QC clean; GEN shows pre-existing untracked `ayush sah tasks/`, `memory/` (present in the first `ls`, before any run) |
| 29 | `git show 92295542:<02,03> \| grep DS-2x/TS-2x` | 0 | confirmed ID renumbering |
| 30 | `python3 SCRATCH/build_checks.py reports/qc/qc_checks.json` | 0 | 307 entries, 0 unresolved, 0 duplicates |
| 31 | ID coverage script (all ID tokens in the 12 files vs qc_checks.json ids+aliases) | 0 | 298 found, 0 missing; 0 md-referenced script IDs missing |
| 32 | `python3 -c "import rewardkit"` | 1 (in python) | ModuleNotFoundError, so exe_copy used fallback schema |
| 33 | `python3 SCRATCH/build_caps.py reports/qc/caps.json` | 0 | 53 limits |
| 34 | `python3 -m json.tool caps.json; python3 -m json.tool qc_checks.json` | 0 / 0 | |
| 35 | fingerprint script (sha256 of 12 QC files + validate_bundle.py, git HEAD) | 0 | |
| 36 | `python3 -m json.tool` on qc_checks.json, caps.json, fingerprint.json | 0 / 0 / 0 | all parse |
| 37 | `git status --short -- Input_Bundle_QC` (clone) | 0 | empty = clean |
| 38 | `rm -rf /tmp/qc-analysis-20261020T2228` and the interim notes file | 0 | SCRATCH gone; LOGS folder kept (outside repo) |

Not run: harbor (oracle/nop/stub), docker builds, `validate_bundle.py --semantic`, any judged-channel execution.

## Delta to 9b8229f6 (qc-delta-20261020T2304)

LOGS: `/tmp/opencode-logs/qc-delta-20261020T2304/` (per-file `diff -u`, idmap.json, blocks.json, paras.json, para_hunks.txt, report_citation_remap.json). SCRATCH `/tmp/qc-delta-old-20261020T2304/` and `/tmp/qc-delta-scratch-20261020T2304/`, deleted at the end. Times IST, 2026-10-20.

| # | Command | Exit | Result |
|---|---|---|---|
| D1 | sha256 of all 12 files, clone vs `QC assigned/` | 0 | identical; the clone was fast-forwarded to 9b8229f6 at 22:54 (reflog), so OLD was rebuilt from `git show 1096b244:Input_Bundle_QC/<f>`, whose hashes match the old fingerprint |
| D2 | `git diff --stat 1096b244 9b8229f6`; `git show 9b8229f6` | 0 | 7 .md files, +463 -2851; 5 scripts untouched |
| D3 | `diff -u` OLD vs CURRENT per file | 1 | 38 hunks (4/3/4/7/3/14/3) |
| D4 | ID-block and paragraph comparison after whitespace normalisation | 0 | 332/358 ID items identical, 11 changed, 15 moved out of 05; 35 paragraph hunks, all mapped in REPORT.md delta ledger |
| D5 | `cp -p` five report files to `_pre_delta/` | 0 | |
| D6 | line-map remap + delta edits of qc_checks.json and caps.json | 0 | 648 + 99 citations; 88 entries with delta_9b8229f6; H2 removed_in |
| D7 | REPORT.md remap (131 citations) + edits; authoring_checklist.md 3 lines | 0 | two commit times hit by the citation regex (01:56, 01:07) restored by hand |
| D8 | fingerprint of CURRENT; `git show 9b8229f6:<f> \| cmp` for all 12 files | 0 | all 12 byte-identical to 9b8229f6 |
| D9 | `json.load` of the three JSON files; every md citation within the CURRENT file length | 0 | all parse; 0 out-of-range |
