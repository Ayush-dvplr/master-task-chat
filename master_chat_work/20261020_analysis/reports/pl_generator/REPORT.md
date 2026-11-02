# PL Input Bundle Generator New (Harbor 0.24): analysis

Source: `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input Bundle Generator New/` at git HEAD `1096b2447dd4` (2026-10-19 11:30 IST). Read-only. All execution ran on a copy in `/tmp/plgen-analysis-20261020T2228/` (generator + `Input_Bundle_QC` copied side by side so `../Input_Bundle_QC` resolves). Paths below are relative to SOURCE unless prefixed. `gb` = `generate_bundle.py`, `vb` = `validate_bundle.py`, `pg` = `playground.py`, `tm` = `task_memory.py`.

Untracked in SOURCE (not PL's, Ayush's own): `ayush sah tasks/` (one finished task `district-heat-flex-procurement`, a `_work` folder, a `_qc` copy of Input_Bundle_QC) and `memory/ideas.jsonl` (1 row, that task). They are included in `fingerprint.json` but are not part of the generator.

## A. CLI

### generate_bundle.py (`gb:2413-2588`, defaults applied in `_resolve_args` `gb:1741-1860`)

| Flag | Default | Effect |
|---|---|---|
| `--out` | required | Existing dir; bundle written to `<out>/<name>/` (`gb:2269-2282`). |
| `--category` | seeded random category | One of 16 keys (`gb:2431`). `gb:1751` picks a **seeded random** category when `--category` is omitted (`args.random or args.category is None`), so the help text "Defaults to 'software-engineering'" (`gb:2435`) is wrong. |
| `--seed INT` | `secrets.randbits(63)`, printed | Root seed (`gb:1744-1746`). |
| `--random` | off | Random category from the seed (`gb:1751`). |
| `--name` | `<title-slug or archetype>-NN` (lowest free ordinal in `--out`) | `gb:1787-1793`, regex `^[a-z0-9][a-z0-9-]{2,63}$` (`gb:68`). |
| `--title` | title-cased name | `gb:1794`. Also used as name stem. |
| `--format-tag` / `--format-ext` | category pools (format-recovery); forced `TASK` / `.dat` for every other archetype | `gb:1778-1786`. `{{PACKAGE_NAME}}` = tag lower-case, so every non-format-recovery package is named `task` (`gb:1338`). |
| `--description` | manifest `default_description` | `gb:1799-1800`; also the memory "premise". |
| `--keywords` / `--tags` | manifest `default_keywords`; tags = keywords | `gb:1801-1837`. |
| `--difficulty` | n/a | **Does not exist** in the parser (ARCHITECTURE_MAP lists it). `task.toml` has no difficulty key. |
| `--docker-image` | `terminal-bench/<name>:latest` | No-op, prints a warning (`gb:1828-1835`). |
| `--estimated-duration-sec` | 7200.0 | `[metadata]`. |
| `--expert-time-min` / `--junior-time-min` | 480.0 / 1440.0 | `[metadata]`. |
| `--verifier-timeout-sec` | 2700.0 | `[verifier].timeout_sec`. |
| `--agent-timeout-sec` | 7200.0 | `[agent].timeout_sec`; integer form quoted in instruction trailer. |
| `--build-timeout-sec` | 900.0 | `[environment]`. |
| `--cpus` / `--memory-mb` / `--storage-mb` | 2 / 4096 / 10240 | `[environment]` (`gb:2535-2555`, `gb:1853-1858`). |
| `--author "Full Name <x@ethara.ai>"` | **required**, repeatable | Exit 2 without it (`gb:1766-1772`; measured: `NOAUTHOR exit=2`). Name must be ≥2 capitalised words, email must end `@ethara.ai` (`gb:974-1018`). QC T14 additionally rejects placeholder names: `Test Author` passed the generator but failed `vb §3.3` (measured, RUN_LOG). |
| `--archetype` | `auto` | `auto` = seeded pick from category affinity list, `random` = any of 8, or explicit name (`gb:1521-1540`). |
| `--force` | off | `rmtree` existing target (`gb:2274-2280`). |
| `--allow-duplicate` | off | Skip memory duplicate refusal (`gb:2582-2587`). |
| `--allow-internet` | n/a | **Removed**; ARCHITECTURE_MAP/FORMAT_SPEC/AUDIT_NOTES still describe it. |

Seeds and determinism:
- Content RNG `random.Random(seed)` (`gb:1747`), draw order fixed (`gb:1774-1824`).
- Child seeds: `blake2b(f"{root}:{tag}", 8 bytes) & (2^63-1)` (`gb:890-898`) for `sample`, `challenge`, `eval`, `container-grammar` (`gb:1054`), `data` (datagen seed, `gb:2369`), `archetype:<category>` (archetype pick, `gb:1539`).
- `datagen.generate(data_dir, _derive_seed(seed,"data"), subs)` (`gb:2353-2369`).
- Measured: two runs with the same seed/category/archetype/name into different dirs are byte-identical (`diff -r` exit 0 for data-pipeline s303 and format-recovery s505).
- Auto selection is `picker.choice(sorted(pool))` (`gb:1540`). Measured: `--category games --seed 20260811` gives **format-recovery** (ARCHETYPE_SELECTION.md:105 says performance); `--category file-operations --seed 4058222581` gives **format-recovery** (README.md:81 says data-pipeline).
- Seed-derived values that leak into graded content: `{{CLI_MAX_RECORDS_BASE}} = 50 + eval_seed%451`, `{{CLI_RETRY_LIMIT_BASE}}`, `{{CLI_TIMEOUT_MS_BASE}}`, `{{SERVICE_ALPHA_BONUS}} = eval_seed%7`, `{{SERVICE_BETA_BONUS}} = eval_seed%11`, `{{CLI_TRAILER}} = harbor:<archetype>:<tag>:<seed hex>` (`gb:1352-1357`). Commit 74d74a8d moved these into shipped `defaults.json` / `seed_config.json` so they are agent-visible (see B).

Pipeline (`scaffold_bundle`, `gb:2242-2350`): resolve args → memory duplicate check → copy+substitute template tree (skips `archetype.toml`, `datagen.py`, `cheat/`, source-archive dirs) → `datagen.py` → zip `source_archives` (ZIP_STORED, fixed 1980 timestamps, `gb:1638-1694`) → `post_generate` (none of the 8 manifests declare one now) → chmod +x → `_embed_shipped_data` (zlib+base64 of every data file into `{{SHIPPED_DATA}}` in `tests/test_output.py`, `gb:1983-2006`) → `_write_reward_toml` → TRUTH.md second pass → memory row.

Scaffold-time refusals (exit 2 via `_die`): judge `[judge]` header not exactly the 5 pinned keys in order (`gb:1903-1937`); judge < 8 criteria (`gb:1939`); any weight outside {5,3,1,-1,-3,-5}, no positive, no negative, or Σ|neg| > Σpos in either channel (`gb:1912-1921`); a `{` or `}` in any `@criterion(description=...)` (`gb:1963-1973`); unresolved `{{TRUTH_*}}` (`gb:2228-2233`).

### validate_bundle.py (`vb:1639-1698`)
`bundle_dir`; `--verbose` (no-op); `--strict` (no-op, strict is default); `--lenient` (WARN not blocking, "NOT shippable"); `--archetype` (override detection, else TRUTH.md `archetype:` line, else `format-recovery`, `vb:62-70`); `--semantic` (Docker floor + visible-only solve, `vb:1479-1636`); `--semantic-report PATH` (must be outside bundle). Exit 0 pass, 1 any FAIL or (strict) WARN, 2 usage.

### playground.py (`pg:425-466`)
`bundle`; `--skip-docker`; `--model` (uploads agent-visible files + grader to api.openai.com, needs `OPENAI_API_KEY`, advisory WARN only); `--min-lines 2000`; `--min-total-lines 20000`; `--ablation-max` (default manifest `ablation_max`, else 0.5); `--json OUT`. Exit 0 no FAIL, 1 FAIL, 2 usage. Never edits the bundle; does update the memory row.

### task_memory.py (`tm:223-271`)
`list`; `show <name>`; `set-status <name> generated|qc-passed|delivered|rejected [--note]`; `record-step10 <name> --oracle a,b,c,d,e --nop X --stub Y [--harbor 0.24.0]` (passed = five oracle values all 1.0 and nop 0.0). Env: `IBG_MEMORY=off`, `IBG_MEMORY_PATH`.

Side effect to know: running `gb`, `pg` or `vb` in SOURCE writes `memory/ideas.jsonl` (default ledger, `tm:45`) and `__pycache__/` (import of `task_memory`, `gb:59`; `vb:742` imports gb). Run from a copy or set `PYTHONDONTWRITEBYTECODE=1 IBG_MEMORY_PATH=...`.

## B. Archetypes

`CATEGORIES.md` says 2 archetypes; the code has 8 (`gb:1434-1443`, all 8 generated and validated). Per-file measurements are in `archetypes.json`. `T/<a>` = `templates/<a>`.

| Archetype | Agent builds | Artifacts | Data files (measured) | Tests pos/neg (P/N) | Judge (P/N) | ablation_max | Hidden grading input |
|---|---|---|---|---|---|---|---|
| build-repair | repair zipped 6-file package, ship `package.zip` + 6 JSON reports | 7 | 9; 1.92 MB; 21,120 l | 15/4 (51/−16) | 13 (41/−10) | 0.9 | 18 seeded manifests + 2 edge cases (`T/build-repair/tests/test_output.py:203-225`) |
| cli-config | repair zipped CLI, run it to produce flat config + transcript | 7 | 9; 2.14 MB; 21,239 l | 14/4 (48/−16) | 10 (30/−10) | 0.5 (default) | none hidden: expected config derived from shipped defaults + journal |
| data-pipeline | reusable `transform.py` normalising 4 feeds via 7 lookup tables | 14 | 12; 2.16 MB; 45,452 l | 13/4 (51/−16) | 11 (33/−10) | 0.5 | reseeded input dir (hidden row order, currencies) |
| domain-calculation | reusable `derive_report.py` for an exact reconciled report | 10 | 11; 1.26 MB; 25,134 l | 16/4 (54/−16) | 11 (38/−5) | 0.5 | reseeded extract (`hidden_seeded_outputs_match_reference`) |
| format-recovery | `/app/decode.py` + byte-exact `/app/encode.py` from a seeded spec | 6 | 7 (6 md + capture log); 2.22 MB; 20,256 l | 24/5 (72/−23) | 12 (34/−10) | 0.95 | EVAL_SEED corpus (delta, dict, mixed, i16/i32 boundary, bad magic/version/CRC) |
| performance | `optimize.py` single-pass aggregator, ≤0.70× baseline median, 9 reports | 10 | 14; 0.67 MB; 20,918 l | 13/4 (49/−16) | 11 (38/−5) | 0.85 | seeded workload + timing run |
| repo-patch | repair zipped 5-layer repo, ship `patched-repo.zip` + 6 reports | 7 | 7; 2.42 MB; 33,072 l | 16/4 (54/−16) | 11 (33/−10) | 0.9 | hidden JSON and CSV ledgers run in child processes |
| service-interaction | start zipped HTTP simulator, drive it via CLI and API, emit state + transcript | 7 | 8; 3.32 MB; 23,621 l | 14/4 (48/−18) | 10 (32/−10) | 0.7 | live run against the shipped simulator; plan re-derived from shipped log |

All 8: same `task.toml`, `test.sh`, `tests/Dockerfile`, near-identical `environment/Dockerfile`; stdlib Python 3.12 only; every check binary; every test channel registers `negative_hardcoded_sample_answers` (−5). Counts and totals above are measured from the generated `test_output.py`/`judge.toml`; the subagent-read template totals differed in two places (build-repair 56 vs measured 51) and I used the measured ones.

**build-repair.** Datagen (`T/build-repair/datagen.py:33-137`): `dependency_manifest.json`, `compiler_flags.json` (zip compression + timestamp chosen by seed), `expected_targets.json`, `module_map.json`, `ci_config.yaml`, `scoring_fixtures.jsonl` (5,500 rows each with the labelled answer `want:{score,bucket}` from `_score`, `datagen.py:24-30,94-101`), `build.log` (~15k lines of pip/compile/test noise with the real errors). Static template project (`environment/data/project/`, zipped): 7 planted defects (wrong `package-dir`, missing `__init__.py`, core↔reports import cycle, tab/space + unclosed bracket in metrics.py, `import tomli`, inverted clamp, two off-by-one boundaries; TRUTH.md Defect section). Solution rewrites the four modules wholesale and builds the zip with manifest-chosen compression/timestamp. Tests import the archive offline as an unprivileged child, score hidden manifests, compare 6 JSON reports to embedded references.

**cli-config.** Datagen writes `validation_rules.json` and `change_journal.jsonl` (21,000 rows, ~6 % bad keys, ~15 % out-of-bounds values, invalid modes; `T/cli-config/datagen.py:38-62`); templates ship `config_schema.json`, `defaults.json` (with seed-derived `base_config` incl. the trailer), `env_overrides.json`, two sample configs, `config_contract.md`, `tool/` (cli.py zipped). Planted CLI bugs: wrong argparse attribute, nested output, `.upper()` keys + string values, `commands="unknown"`, optional subparsers, unsorted JSON (TRUTH.md:27-71). Tests rerun the repaired CLI's `validate`, compare config/profiles to values derived from defaults + valid journal ops, and check the transcript.

**data-pipeline.** Datagen (`T/data-pipeline/datagen.py:74-232`): regions 2,300, customers 2,400, catalog 2,100, inventory ~5,200, channels 2,050, fx ~13,400 (6 currencies × 2,240 days), calendar 2,222, sales 8,200, refunds 2,600, adjustments.jsonl 2,300, legacy.txt pipe-delimited 2,500; each field corrupted with p = 0.004 and casing/whitespace "messiness". `schema.md` documents the canonical record and aggregates. Tests: exact visible outputs, rerun `transform.py` on a fresh dir, hidden row order/currency case.

**domain-calculation.** Datagen (`T/domain-calculation/datagen.py:56-143`): discount_rules 320 codes, customers 2,500, regions 2,400 sites, tax_rules (default + region + 900 site overrides), rate_table 2,160 rows of textual multipliers, fx_rates, calendar 2,200 with 1.2 % holes, transactions 12,000 (8 % credits, posting lag 0-8 days), thresholds, policy. `schema.md` gives the exact derivation (Decimal ROUND_HALF_UP, precedence site > region > default, clamp). Tests: exact summary/policy_audit/data_quality/region/segment files, hidden reseeded outputs, rounding/FX/discount/clamp case, script runs as unprivileged user.

**format-recovery.** Category-themed: 6 spec documents (`<TAG>-container-format.md`, decoder-appendix, encoder-notes, error-codes, glossary, varint-crc-primer) with seed grammar rendered in (`gb:1048-1320`), plus `<TAG>-capture-log.jsonl`: 20,000 unlabelled `{capture_id, hex}` captures, ~9 % damaged, generated by the verifier's own `_build_capture_log` (`T/format-recovery/datagen.py:1-8`, `tests/test_output.py:643-669`). Grammar per seed: 2 mode bits + wide + long-key bits out of 8, mode-id permutation, header field order (5!), zigzag vs signed LEB128 delta, dictionary source/direction, CRC coverage (`gb:1048-1076`). `solve.sh` Phase 1/2 loop over `sample_*.<ext>` / `field_*.<ext>` files that no longer ship (nullglob), so those phases are no-ops. Docker-measured: oracle 1.0, nop 0.0, stub 0.0.

**performance.** Datagen (`T/performance/datagen.py:35-128`): accounts 2,200; 5 workload CSVs × 3,700 rows (25 % hot accounts); rules, thresholds (max_relative_median 0.70), baseline_metrics, cost_model, hardware_profile, query_plan, index_config. Traps: order-dependent checksum fold, fixed contract values in `perf_report.json` (e.g. observed_relative_median 0.35 is a contract, not a measurement), opposite tie-break directions, literal recommendation strings (TRUTH.md focal list). Tests include a warm-up + repeated-median speed gate.

**repo-patch.** Datagen (`T/repo-patch/datagen.py`): package_manifest, build_config (zip compression/timestamp/mode), lint_report (~700 pylint issues, 4 focal), regression_cases.jsonl (2,403 labelled `payload`→`expected`), failing_tests.log (~25k lines). Static template repo with 5 broken layers (pyproject 4 ways, missing `__init__`, cycle hidden by deferred imports, parser handles one shape, report sums keys). Tests run hidden JSON and CSV ledgers in child processes.

**service-interaction.** Datagen (`T/service-interaction/datagen.py:39-86`): approvals.csv 2,400 rows of which exactly 46 are `approved`; request_log.jsonl 21,000 shuffled rows of which only the requests carrying those 46 approvals (with 1-3 idempotent duplicates each) replay; `expected_schema.json` gains 1-2 random required fields. Templates: `api_contract.md`, `auth_policy.json`, `scenarios.json`, `seed_config.json` (ports, bonuses, trailer), `service/{simulator.py,client.py}` zipped. TRUTH.md focal list: real server must run, plan = filter over history, order-sensitive arithmetic, report carries sha256 of delivered state; drift: final_state is not `/state`; traps: artifact network scan, trailer exactly once.

## C. Categories

16 keys in `_CATEGORIES` (`gb:135-619`): software-engineering, system-admin, data-science, security, scientific-computing, file-operations, debugging, data-processing, model-training, mathematics, machine-learning, games, video-processing, data-querying, optimization, personal-assistant. Each has `display`, `canonical`, `subcategory`, `family` (always `"format-recovery"`, unused), `notes`, `magic_pool` (5 x 5-byte ASCII), `tag_prefix_pool`, `ext_pool`, `noun_pool`, `verb_pool`, `producer_pool`, `keyword_pool`.

What a category changes:

| Archetype | Category effect |
|---|---|
| format-recovery | magic bytes, format tag (file prefix of every data file, e.g. `VAULT-*.md`), extension, version 1..5, container noun, producer name in instruction, `[metadata].category` (`gb:1778-1819`). Keywords/description come from the manifest; the keyword/verb/noun pools are drawn only to keep RNG positions (`gb:1810-1815`). |
| other 7 | Only `[metadata].category` display string and the auto-archetype pool. `format_tag="TASK"`, magic empty, version 0, nouns empty (`gb:1784-1786`, `gb:1820-1824`). Content, file names, narrative and tests are identical across categories for a given seed. |

Affinity map `_DOMAIN_ARCHETYPE_AFFINITY` (`gb:1446-1518`) matches ARCHETYPE_SELECTION.md:54-71 row for row. Every archetype appears in 6 to 9 lists. QC `structure_qc.py` T7 accepts any non-empty category string (`Input_Bundle_QC/structure_qc.py:545-615`), and `vb` never checks the vocabulary (`_allowed_categories` at `vb:742` is never called), so a hand-edited category passes both.

`CATEGORIES.md:34-36` says only format-recovery and build-repair exist. The code discovers 8 (`gb:1434-1443`, `--help` lists all 8, all 8 generated). CATEGORIES.md is stale.

## D. Bundle anatomy (0.24, as emitted)

```
<name>/
├── instruction.md
├── task.toml
├── environment/
│   ├── Dockerfile
│   └── data/            flat, files only (vb §1.7); zips allowed as files
├── solution/
│   ├── solve.sh
│   ├── solve.py
│   └── TRUTH.md         ≥4000 chars, 8 sections, provenance yaml
└── tests/
    ├── Dockerfile
    ├── test.sh
    ├── test_output.py   rewardkit @criterion checks + criteria.<n>(weight=W); embeds zlib/base64 copy of environment/data
    ├── judge.toml
    └── reward.toml      generated
```
No README.md, no test_weights.json, no rubric.json (`vb:258-274`; QC Final_checklist).

`task.toml` (identical template for all 8, `templates/*/task.toml:1-47`): root `schema_version="1.4"`, `artifacts` (= manifest list, `vb §1.12` requires exact equality); `[task]` name `terminal-bench/<name>`, `version="1.0.0"`, description, keywords, `authors=[{name,email}]`; `[metadata]` category (display string), `platforms=["linux/amd64","linux/arm64"]`, tags, `estimated_duration_sec`, `expert_time_estimate_min`, `junior_time_estimate_min`, `null_floor=0.0`, `discrimination_weight=1.0`; `[verifier]` timeout_sec, `environment_mode="separate"`, `network_mode="allowlist"`, `allowed_hosts=["api.openai.com","*.openai.com"]`; `[verifier.env] OPENAI_API_KEY="${OPENAI_API_KEY:-}"`; `[verifier.environment]` repeats the allowlist; `[agent]` timeout_sec, `network_mode="allowlist"`, `allowed_hosts=["api.anthropic.com","api.z.ai"]`, `user="1000:1000"`; `[environment]` build_timeout_sec, `network_mode="no-network"`, cpus, memory_mb, storage_mb, `gpus=0`, `mcp_servers=[]`. No `difficulty`, no `allow_internet` (QC T12 forbids it, `structure_qc.py:465-496`).

`environment/Dockerfile` (all 8 equivalent; cosmetic whitespace diffs only): `FROM public.ecr.aws/docker/library/python:3.12-slim@sha256:646fb0bc…7d7b`; `groupadd -g 1000 agent && useradd -u 1000 … -d /home/agent`; `ENV HOME=/home/agent`; one apt layer with `xxd file curl bash nodejs npm procps ca-certificates tmux` + `rm -rf /var/lib/apt/lists/*`; `WORKDIR /app`; venv `/opt/openhands-sdk-venv` with `openhands-sdk==1.55.1 openhands-tools==1.55.1 litellm==1.105.0 fastapi` (fastapi unpinned) + import check; `RUN mkdir -p /app && chown 1000:1000 /app` (exact line required, `vb:548`); last line `COPY data /app/data` (`vb:560-572`).

`tests/Dockerfile` (identical for all 8): `FROM python:3.12-slim` (not digest-pinned, Docker Hub), apt `util-linux` (setpriv), `pip install harbor-rewardkit==0.2.1`, `ENV LITELLM_LOCAL_MODEL_COST_MAP=True`, `COPY . /tests/`, `mkdir -p /app`, `WORKDIR /app`.

`tests/test.sh` (identical for all 8): `set -euo pipefail`; delete old reward files; `/logs/verifier` root-owned 0700; `chmod -R go-rwx /tests`; `exec rewardkit /tests --workspace /app --output /logs/verifier/reward.json`. It writes no reward itself.

`tests/judge.toml`: `[judge]` exactly `judge="openai/gpt-5.6-sol"`, `mode="individual"`, `timeout=300`, `atif-trajectory="/logs/agent/trajectory.json"`, `weight=1.0` (`gb:1903-1909`); `[scoring] aggregation="weighted-sum"`; ≥8 `[[criterion]]` with `id` (R1..), `name`, `description`, `type="binary"`, `weight` ∈ {±1,±3,±5}, and `[criterion.annotations]` keys `mode, type, evidence, residue, kind, category, evaluation_target, importance, serves`, optionally `contract_file`, `contract_sentence` (measured across the 8 bundles). Measured counts: 10 to 13 criteria, positive totals 30 to 41, negative totals -5 to -10.

`tests/reward.toml` (written by `gb:2009-2025`):
```toml
[[reward]]
name = "reward"
aggregation = "weighted-sum"
weights = { test_output = 0.5/P_test, judge = 0.5/P_judge }   # repr floats
[scoring.test_output]
aggregation = "weighted-sum"
```

Reward arithmetic: `reward = 0.5·Σ_i(v_i·w_i)/P_test + 0.5·Σ_j(v_j·w_j)/P_judge`, v ∈ {0,1} (binary checks/criteria), P = sum of positive weights per channel. Negatives subtract when the cheat check fires. No clamp; since Σ|neg| ≤ Σpos is enforced per channel the floor is −1.0 (Final_checklist.md:403-429). Oracle can reach at most 0.5 + judge share; Step 10 grades the test channel alone on an `exe_copy.py` copy that rewrites weights to `test_output = 1/P_test` and drops the judge (Final_checklist.md:717; `Input_Bundle_QC/exe_copy.py:19`). How rewardkit combines `[[reward]]` with `[scoring.*]` internally is not in this repo: UNVERIFIED beyond the file shape and the QC description.

`solution/`: `solve.sh` (bash, `set -euo pipefail`, installs/executes `solve.py` and writes the artifacts), `solve.py` (stdlib reference), `TRUTH.md` (author-only, sections Defect / Load-bearing work / Verification / Root cause / Solution shape / Ordered plan / Pitfalls / Provenance; second-pass tokens from the generated files, `gb:2211-2236`). Harbor 0.24 oracle runs `solve.sh` as uid 1000 (playground mirrors this, `pg:257-259`).

`instruction.md` shape (measured in all 8): 1,407 to 3,663 chars, 3 to 7 blocks (paragraphs plus code), every artifact path in backticks, a fenced json shape example only in format-recovery and performance, then the fixed trailer `You have <agent_timeout_int> seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.` Must stay < 6000 chars (`vb:439-444`).

## E. Hardness mechanisms (full list with ids in `hardness.json`)

| Id | Mechanism | Automatic? | Main weakness |
|---|---|---|---|
| P-001 | Verifier-side seeded hidden inputs (EVAL_SEED in `tests/test_output.py`, never in agent image) | yes | Hidden sets are small (build-repair 18+2 manifests) and drawn from the same documented rules, so a correct general solution and an overfit one differ only on edges; cli-config and service-interaction have no hidden data at all. |
| P-002 | Seed-varying format grammar, fully documented (format-recovery) | yes | Pure careful-reading task; spec is complete by design (GENERATOR_TRAP_RECIPE §3), grammar space is small (bit picks, 3! mode ids, 5! header orders, 2×2×2×2 flags). |
| P-003 | Layered, mutually masking planted bugs in a zipped source tree (build-repair 7, repo-patch 5 layers, cli-config 7) | yes, but static | Bugs are hard-coded in `environment/data/project|repo|tool` templates; only names/versions vary by seed, so every bundle of an archetype has the same bugs. Source is 59-135 lines. |
| P-004 | Labelled fixture corpora (build-repair `scoring_fixtures.jsonl` with `want`; repo-patch `regression_cases.jsonl` with `expected`) | yes | Lets the agent fit and check the hidden scoring rule from 5,500 / 2,403 examples; turns "derive the rule" into "match the labels". |
| P-005 | Dirty data: p=0.004 per-field corruption, messy casing (data-pipeline), 1.2 % calendar holes, credits, posting lag (domain-calculation), 6 % bad keys + 15 % out-of-bounds (cli-config), 9 % damaged captures (format-recovery) | yes | Rules for each are documented in `schema.md`/contract; rates are fixed per archetype. |
| P-006 | Noise filtering: 46 approved of 2,400 approvals, ~21k request rows of which a small subset replays (service-interaction) | yes | A single join/filter collapses the volume; size is not difficulty. |
| P-007 | Contract-over-instinct "drift" values (performance fixed `perf_report` values and literal recommendation strings; service final_state ≠ `/state`) | template | Documented in shipped `schema.md`/contract, so they test reading, not reasoning. |
| P-008 | Byte-exact / canonical outputs (sorted keys, zip timestamps/compression/mode from sidecars, encoder round-trip, signed i16/i32 boundaries) | yes | Mechanical once read. |
| P-009 | Polarity-inverted negative tests (−3/−5) per archetype | template | Substring heuristics: e.g. cli-config fires if repaired CLI source contains the visible number `MAX_RECORDS_BASE` (e.g. `146`) or `TIMEOUT_MS_BASE` (`tests/test_output.py:341-345` in the generated bundle), risking false positives; source scans are easy to evade. |
| P-010 | Judge channel = 50 % of reward, ABSENCE criteria at −5 | template | Criteria are generic process checks ("reads spec first", "summarises paths"); a competent agent earns most of them regardless of correctness, inflating scores; the judged half has no oracle. |
| P-011 | Speed gate: warm-up + repeated median ≤ 0.70 of baseline (performance) | template | Timing noise; the reference baseline is a deliberately slow implementation. |
| P-012 | Input volume gate (A5) + per-file ablation (D4) | playground only | Padding passes A5; `ablation_max` 0.7-0.95 lets one file be dropped for ≤30 % loss; neither runs in `vb`. |
| P-013 | TRUTH.md focal/drift/trap labelling | author | `vb §15.4` counts substrings only; nothing checks that a trap is actually tested. |
| P-014 | "What not how" instruction, inputs not enumerated, breadth of relevant files | template + QC | `[dependencies]` graph is only written to memory, never enforced; A4 only checks a file is named somewhere. |
| P-015 | Partial-solver ceiling < 0.35 (GENERATOR_TRAP_RECIPE §6, §8) | **no** | Not implemented anywhere in `gb`/`vb`/`pg` (no ceiling code); purely advisory. |
| P-016 | Isolation: separate verifier image, `/tests` 0700, uid 1000 agent, `setpriv`, no-network agent env | yes | Verifier image is not digest-pinned (`FROM python:3.12-slim`). |

## F. Validator rules (`vb:1280-1393`, 52 rules; full list in `validator_rules.json`)

Counts: 46 FAIL-type, 4 WARN-type (§11.2-§11.5: blocking by default because strict is the default, `vb:1690-1695`; non-blocking only with `--lenient`), 2 INFO-only (§1.9, §10). Four rules delegate to the QC scripts (§3.3 structure_qc, §3.4 instruction_qc, §7.5 judge_qc, §7.6 tests_qc; QC FAIL → FAIL, QC WARN → INFO, `vb:1236-1264`). Nine rules are gated to format-recovery only (§1.5, §6.1, §6.2, §7.2, §11.1-§11.5; others get INFO, `vb:1267-1278`). Per-archetype measured split: format-recovery 49 PASS + 3 INFO; the others 39 to 41 PASS + 11 to 13 INFO; 0 FAIL, 0 WARN for all 8.

| Group | Rules |
|---|---|
| §1 tree | 1.1 name regex · 1.2 root files · 1.3 dirs · 1.4 env = Dockerfile+data · 1.5 solution exact (FR) · 1.6 tests exact 5 files · 1.6a cheat/ shape · 1.7 data flat, non-empty · 1.8 no `__pycache__` · 1.9 exec (INFO) · 1.10 no CRLF · 1.11 no residual markers incl. inside zips · 1.12 archetype/manifest/artifacts match · 1.13 min_inputs/min_outputs |
| §2 instruction | 2.1 exists · 2.2 < 6000 chars · 2.3 backticked abs path · 2.4 "second(s)" · 2.5 online-lookup phrase |
| §3 task.toml | 3.1 parses · 3.2 schema_version+artifacts · 3.3 structure_qc · 3.4 instruction_qc · 3.5 placeholder (always PASS) |
| §5 env Dockerfile | 5.1 exists · 5.2 digest-pinned ECR FROM · 5.3 one apt layer w/ baseline pkgs · 5.4 WORKDIR + exact chown line, no claude-code · 5.5 last line `COPY data /app/data` only · 5.6 files ≤100 MB |
| §6 solution | 6.1 solve.sh strict + copies solve.py (FR) · 6.2 solve.py exists (FR) · 6.3 static solvability audit (all) |
| §7 tests | 7.1 parses · 7.2 seeds/_write_corpus/main (FR) · 7.4 weights legal + bijection + `negative_hardcoded_sample_answers` (all) · 7.5 judge_qc · 7.6 tests_qc |
| §10, §11 | 10 INFO · 11.1-11.5 FR negative tests |
| §15 TRUTH.md | 15.1 ≥4000 chars · 15.2 H1 · 15.3 8 sections ordered · 15.4 ≥2 focal, ≥1 drift, ≥1 trap · 15.5 provenance keys · 15.6 identity · 15.7 sha256 · 15.8 positive total + negatives named |

Dead code: `c_9_corpus` (`vb:678-702`, the sample_/field_ corpus rule) and `_allowed_categories` (`vb:742-753`) are defined but not in `RULES`.

`--semantic` (`vb:1479-1636`, not part of the 52): builds both images, runs `test.sh` on an empty tests container (nop must be < 1.0), runs `solve.sh` in the env image with `--network none` and seed/API-key env vars blanked, copies artifacts into a fresh tests container, requires reward exactly 1.0. It does not run `solve.sh` as uid 1000, it runs `test.sh` with the full judge config (no `exe_copy` rewrite), and needs network for the judge, so with the 0.24 two-channel reward it cannot reach 1.0 unless the judge pays 100 %: did not run (UNVERIFIED in practice).

Caps (reported, not design constraints): judge ≥ 8 criteria (`gb:1939`); weights {±1,±3,±5}; Σ|neg| ≤ Σpos per channel (`gb:1920`). No upper cap on test or criterion counts in `gb`/`vb`; any upper caps live in the QC scripts (analysed separately).

## G. Author surface

Must add or replace (the scaffold is a working but generic task):
- Rewrite `instruction.md` prose for the real scenario. In build-repair, data-pipeline, domain-calculation and performance the generated sentence has empty slots (`{{CONTAINER_NOUN}}`/`{{PRODUCER_SYSTEM}}` resolve to `""` outside format-recovery, `gb:1820-1824`), measured: "meant to summarize  manifests from a .", "a  reconciliation extract from ,", "a deterministic  workload from a ,". `vb` and the QC scripts pass it. Also "package named task" (`{{PACKAGE_NAME}}` = `task`).
- Replace `defaults.json`/`seed_config.json` `producer`/`container` empty strings (cli-config, service-interaction) if the narrative needs them.
- Rewrite `solution/TRUTH.md` prose if the defects change; keep the 8 headings, ≥2 `(focal)`, ≥1 `(drift)`, ≥1 `(trap)`, the provenance yaml, and the positive weight total (`vb §15`).
- Any new hardness (new datagen, new hidden cases, new tests, new judge criteria) is the author's; the generator gives one fixed task per archetype.
- `--author` must be a real `First Last <first.last@ethara.ai>`; placeholders fail QC T14.

Must stay exactly as generated (or validation breaks):
- `task.toml` keys/values incl. `schema_version "1.4"`, network roles, `user "1000:1000"`, `null_floor`, `discrimination_weight`, and `artifacts` **equal to the archetype manifest list** (`vb §1.12`). Adding or renaming an artifact requires editing `templates/<a>/archetype.toml` itself or the bundle fails, because the manifest is read from the generator folder, not the bundle.
- `solution/TRUTH.md` line `archetype: <name>` (drives archetype detection, `vb:62-70`), `fix_patch_sha256`/`solve_py_sha256` (recompute after every solve.sh/solve.py edit, `vb §15.7`).
- `environment/Dockerfile`: digest-pinned ECR FROM, single apt layer with the 8 baseline packages, `WORKDIR /app`, the exact `RUN mkdir -p /app && chown 1000:1000 /app` line, final `COPY data /app/data`, no other COPY (`vb §5`). The uid 1000 account and openhands-sdk venv are QC S9/S10 requirements (commit 1096b244).
- `tests/` exactly 5 files; `judge.toml` header 5 keys in order; weights in {±1,±3,±5}; Σ|neg| ≤ Σpos per channel; ≥8 criteria; `negative_hardcoded_sample_answers` registered negative; no braces in `@criterion` descriptions; `reward.toml` = `0.5/P` per channel (regenerate if weights change: the generator writes it only at scaffold time).
- `environment/data` flat, ≥ `min_inputs` files (6 or 10), ≤100 MB per file; no `TODO/FIXME/XXX/PLACEHOLDER/<TAG>/{{X}}/__X__` anywhere incl. zip members (`vb §1.11`), so never leave those words in data or prose.
- format-recovery only: magic, version, tag-prefixed file names, extension and grammar are baked consistently into spec, `solve.py`, `test_output.py` and the capture log; changing one by hand desynchronises the rest. Regenerate with flags instead.
- If you edit `environment/data`, re-embed it into `tests/test_output.py` (`{{SHIPPED_DATA}}` is replaced once at scaffold, `gb:1983-2006`); tests that recompute from shipped data will otherwise grade against stale copies.

## H. Data volume and formats (measured)

Generated in SCRATCH, explicit archetype, `--author "Priya Raman <priya.raman@ethara.ai>"`, isolated ledger. `vb` default (strict) on each.

| Bundle (category, seed) | bundle files / bytes | data files | data bytes | data lines* | largest data file | formats in data/ | vb |
|---|---|---|---|---|---|---|---|
| build-repair (software-engineering, 101) | 20 / 2,179,250 | 9 | 1,916,182 | 21,120 | build.log 1,237,910 B (15,371 l) | json, jsonl, log, md, yaml, zip(py,md,toml) | PASS 39/0/0 |
| cli-config (system-admin, 202) | 20 / 2,575,808 | 9 | 2,138,122 | 21,239 | change_journal.jsonl 2,130,331 B (21,000 l) | json, jsonl, md, zip(py,md,json) | PASS 41/0/0 |
| data-pipeline (data-processing, 303) | 23 / 3,092,675 | 12 | 2,156,756 | 45,452 | sales.csv 554,644 B (8,201 l) | csv, jsonl, md, txt | PASS 40/0/0 |
| domain-calculation (mathematics, 404) | 22 / 1,905,556 | 11 | 1,261,260 | 25,134 | transactions.csv 943,210 B (12,001 l) | csv, json, md | PASS 40/0/0 |
| format-recovery (security, 505) | 18 / 2,331,712 | 7 | 2,216,995 | 20,256 | VAULT-capture-log.jsonl 2,203,344 B (20,000 l) | jsonl, md | PASS 49/0/0 |
| performance (optimization, 606) | 25 / 1,024,990 | 14 | 667,031 | 20,918 | workload_peak.csv 126,021 B (3,701 l) | csv, json, md | PASS 40/0/0 |
| repo-patch (debugging, 707) | 18 / 2,708,549 | 7 | 2,416,301 | 33,072 | failing_tests.log 1,512,686 B (25,599 l) | json, jsonl, log, md, zip(py,md,toml) | PASS 41/0/0 |
| service-interaction (machine-learning, 808) | 19 / 4,030,664 | 8 | 3,319,353 | 23,621 | request_log.jsonl 3,216,443 B (21,000 l) | csv, json, jsonl, md, zip(py) | PASS 41/0/0 |

*newline count of data files plus text members of zips. Per-file rows are in `archetypes.json`. Generation takes ≤1 s per bundle.

Findings:
- "Data too small" is fixed in volume: every bundle has 20k to 45k lines and 0.67 to 3.3 MB of input, enforced by playground A5 (≥20,000 total lines, ≥2,000 per csv/tsv/jsonl/txt/log file, `pg:180-204`). All 8 pass A5. But volume is concentrated: in 6 of 8 bundles one or two files hold most of the lines, and the commit for build-repair raised fixture rows 4,500 → 5,500 just to stay above 20k (`git show 1096b244 -- templates/build-repair/datagen.py`). The zipped source code the agent repairs is tiny: 59 to 135 lines (repo.zip, project.zip, tool.zip, service.zip).
- Size alone is not load-bearing: format-recovery's 20,000-line capture log is unlabelled `{"capture_id","hex"}` rows used only for the four report artifacts; deleting it costs 0.167 of the test channel (playground D4 measured 0.8333). Manifests openly set ablation ceilings of 0.7 to 0.95 for five archetypes (`templates/*/archetype.toml`), i.e. any single data file can be removed for at most 5 to 30 % loss.
- "Too few formats" is still true. Formats seen across all 8: csv, json, jsonl, md, txt, log, yaml, zip (zip members py, md, toml, json). Never emitted: tsv, xml, ini/cfg, parquet, sqlite, xlsx, binary blobs, gz/tar, html, pdf, images. format-recovery ships no binary file at all; its "binary" corpus is hex strings inside JSONL. Playground's record-file list knows csv/tsv/jsonl/txt/log only (`pg:53`); `vb` has no format whitelist, so other formats are allowed by `vb` but escape the A5 per-file size check (they still count toward the 20k total only if they decode as UTF-8 text).
- Everything is stdlib Python 3.12; no archetype uses another language, a database, or a compiled toolchain.

Docker run (one bundle): `playground.py out/format-recovery-s505` (tests-only `exe_copy` copy, `--network none`, uid 1000): oracle 1.0, nop 0.0, stub 0.0, ablation of the capture log 0.8333 (≤ 0.95 PASS), playground PASS 0 FAIL 0 WARN. `harbor run` itself: did not run. Oracle/nop for the other 7: did not run.

Static playground (`--skip-docker`) on all 8: PASS, 0 FAIL; 4 WARN of type A2 (test reads a key absent from agent-visible files): build-repair `callables`, data-pipeline `APP_ROOT`, performance `median_ns`, repo-patch `APP_ROOT`. QC WARN surfaced as INFO by vb: instruction_qc C6 ("instruction mentions a grader/verifier") on build-repair and format-recovery; tests_qc O1 (21 % oracle/verifier line overlap) on build-repair.

Generator unit tests (`python3 -m unittest discover -s tests`, `IBG_MEMORY=off`, on the copy): 59 tests, OK, 47.7 s.

## I. Memory and playground

`task_memory.py` keeps one JSON row per generated bundle in `memory/ideas.jsonl` (`tm:138-167`): name, title, archetype, category, seed, premise (= description), `premise_is_default`, `ideas` (all `@criterion(description=…)` strings and judge descriptions, `tm:124-135`), `input_files` {bytes, lines, sha256}, `dependency_graph` (manifest `[dependencies]` after substitution), `data_hash`, `created_at`, `status`, `status_note`, `playground`, `step10`. The generator refuses (exit 1) when another row has the same archetype+seed, the same data hash, or (both non-default) a premise with token Jaccard ≥ 0.9 in the same archetype (`tm:170-200`; measured `DUP exit=1`). Rows with the same name are replaced, so `--force` regeneration is allowed. Because the premise check is skipped when the description is the manifest default, two default-description bundles of the same archetype with different seeds are never flagged. Nothing from the ledger enters a bundle.

SOURCE's ledger has 1 row: `district-heat-flex-procurement` (domain-calculation, seed 731904, 11 files, 25,137 lines, playground passed 0/0, step10 null, status generated). That is Ayush's task, not a PL sample.

`playground.py` layers: static A1 (every `/app/…` path in instruction appears in test_output.py), A2 (WARN: dict keys the tests read that no agent-visible file contains), A3 (judge `contract_sentence` annotations verbatim in instruction), A4 (every non-.md data file named in some other agent-visible text), A5 (size), plus the 4 QC scripts; docker D1 oracle = 1.0, D2 nop = 0.0, D3 stub ≤ 0.25 (else WARN), D4 per-file ablation ≤ `ablation_max`; model M* advisory. Intended use: run after authoring and before QC/Step 10; record results with `task_memory.py record-step10` and `set-status`.

## J. Change tracking (last 15 commits touching the folder, newest first)

| Commit | Date (IST) | Author | Change |
|---|---|---|---|
| 1096b244 | 2026-10-19 11:30 | Shreeyank Doliya | QC S9/S10/G2: uid 1000 `agent` account + HOME, openhands-sdk venv baked into all 8 env Dockerfiles, tmux; `reasoning_effort` dropped from judge header and extra keys refused; build-repair fixtures 4,500 → 5,500 rows "to keep build-repair inputs above 20k lines". |
| ceec0fab | 2026-10-18 01:56 | Shreeyank Doliya | Harbor 0.24 migration: rewardkit tests, judge.toml (+~200 lines per archetype), reward.toml, `datagen.py` per archetype (static data files deleted, replaced by seeded large interdependent inputs), playground.py, task_memory.py, validator −462 lines. |
| 0a606d57 | 2026-10-17 17:30 | Shreeyank Doliya | "V3": removed per-bundle README.md, rubric.json, test_weights.json; new test.sh/Dockerfile/task.toml. |
| eb830ea4 | 2026-09-15 | Sugam Agrawal | TRUTH.md moved to solution/. |
| 526f860f | 2026-09-01 | Shreeyank Doliya | authors as `{name,email}` tables. |
| fcbb4574 | 2026-09-01 | Shreeyank Doliya | cheat overlay retired; `--author`; rubric contract. |
| a3ae6647 | 2026-08-20 | Shreeyank Doliya | TRUTH.md golden trajectory in every bundle. |
| 78321f17 | 2026-08-19 | Shreeyank Doliya | exact field derivations in domain-calculation/performance schema.md. |
| 74d74a8d | 2026-08-18 | Shreeyank Doliya | solvability guarantee: §6.3 audit, `--semantic`; seed-derived graded values moved into shipped files; instructions de-recipe'd. |
| bca99f7d | 2026-08-14 | Shreeyank Doliya | min_inputs/min_outputs tiers (6/6, 10/10). |
| 568a7569 | 2026-08-13 | Shreeyank Doliya | QC contradictions C1-C8; format-recovery to complete spec, no shipped corpus. |
| 8eb37af8, 902ba396, 0a433465, cdcfbe54 | 2026-08-12 | Shreeyank Doliya | cheat docs, service-interaction isolation. |

Direction: the generator chases the QC checklist (each recent commit names QC ids), grows input volume by padding the biggest file to clear the 20k-line gate, and keeps the reference-matching style of tests. Docs were not updated after ceec0fab beyond a "Superseded for Harbor 0.24" banner.

## K. Gaps and risks for authoring hard tasks

- Leaks the scaffold makes easy: labelled fixtures (`want`, `expected`) that let the agent fit the graded rule (P-004); complete specs by policy (P-002); seed-derived "hidden" constants now shipped in `defaults.json`/`seed_config.json`; `schema.md` files that spell out exact derivations (commit 78321f17); TRUTH.md is outside the image but `solve.py` logic is duplicated into `test_output.py` (tests_qc O1 21 % overlap on build-repair).
- Cannot express: non-Python toolchains, compiled builds, databases/servers other than the zipped stdlib simulator, multi-service setups, GPUs (`gpus = 0` fixed), network-dependent tasks (`no-network`), binary inputs (format-recovery ships hex in JSONL), subdirectories in `environment/data` (zip is the only nesting), per-bundle artifact lists different from the manifest (§1.12), non-binary/partial-credit checks (all checks binary).
- Formats: only csv, json, jsonl, md, txt, log, yaml, zip are emitted; playground size rules only know csv/tsv/jsonl/txt/log. Adding xml, ini, tsv, parquet, sqlite, xlsx, gz/tar or raw binary is up to the author and is not covered by A5 per-file checks (binary files count 0 lines).
- Size: 20k-line floor is met by padding one or two files (logs, journals); repaired source trees are tiny; cross-file dependency is declared but not enforced.
- Monotony: the 7 non-format-recovery archetypes produce the same task text, the same bugs, and the same tests for every category and seed; only data values change. Batch-generated bundles of one archetype are near-duplicates even though memory only refuses same seed / same data / similar custom premise.
- Reward inflation: the judge half pays for process; a wrong but well-behaved run can score ~0.4-0.5 (UNVERIFIED, no agent run).
- Tooling caveats: running `gb`/`vb`/`pg` in SOURCE writes `memory/ideas.jsonl` and `__pycache__`; `vb --semantic` cannot reach 1.0 under the two-channel reward without a judge; documented auto-selection examples are wrong.

## Doc vs code disagreements

| Doc claim | Code / measurement |
|---|---|
| CATEGORIES.md:34-36 "current archetypes are format-recovery and build-repair" | 8 archetypes discovered and generated. |
| CATEGORIES.md:31 "validate_bundle.py §3 accepts only the 16 display values" | No vb rule checks category; `_allowed_categories` (`vb:742`) is never called; QC T7 accepts any non-empty string. |
| gb `--category` help (`gb:2435`) and ARCHITECTURE_MAP "default software-engineering" | `gb:1751` picks a random category when omitted. |
| ARCHETYPE_SELECTION.md:105 games/20260811 → performance; README.md:81 file-operations/4058222581 → data-pipeline | Both measured → format-recovery. |
| FORMAT_SPEC §1 tree (README.md, test_weights.json, rubric.json), §3 schema 1.1, §7 pytest Dockerfile, §8 reward formula, §4 README | 0.24: no README, rewardkit, judge.toml, reward.toml, schema 1.4 (banner says superseded, body not updated). |
| FORMAT_SPEC §3, AUDIT_NOTES, ARCHITECTURE_MAP: `allow_internet` always `true`, `--allow-internet` flag accepted | No `allow_internet` key (QC T12 forbids it); `[environment].network_mode = "no-network"`; flag removed from parser. |
| ARCHITECTURE_MAP: `--difficulty` flag, `[metadata].difficulty`, 1928-line gb, format-recovery data `{{FORMAT_TAG}}-v1.0-DRAFT.md` | No difficulty anywhere; gb is 2618 lines; spec files are `<TAG>-container-format.md` + 5 others. |
| FORMAT_SPEC §14 "25 tests (20 positive = 60, 5 negative = −23)" | format-recovery measured 29 checks: 24 positive = 72, 5 negative = −23. |
| FORMAT_SPEC §5.1 and AUDIT_NOTES V3: both Dockerfiles digest-pinned | `tests/Dockerfile` is `FROM python:3.12-slim` (unpinned); vb only checks the env Dockerfile. |
| FORMAT_SPEC §1 "global floor 6/6; data-science tier 10/10" | Matches manifests (6/6 for 5 archetypes, 10/10 for data-pipeline, domain-calculation, performance). |
| FORMAT_SPEC §9/§12 `--semantic` proves visible-only reward 1.000 | Implementation scores via full two-channel test.sh (judge included) as root; not achievable as written (did not run). |
| GENERATOR_TRAP_RECIPE §6/§8 "generator loops until partial-solver ceiling < 0.35" | No such code. |
| CHEAT_VECTORS §1 "24 shipped sample captures"; §6 sample_*.json; solve.sh Phase 1/2 | No sample/field captures ship; `c_9_corpus` is dead; solve.sh loops are no-ops. |
| README: "every record file at least 2,000 lines" | Enforced only by playground, not by vb. |
| README "--author … 'Ram Lakhan <ram.lakhan@ethara.ai>'" | gb accepts any capitalised name; QC T14 rejects placeholders (measured with "Test Author"). |

## Not checked

- `harbor run` (oracle ×5, nop, stub) on any bundle: did not run. Docker playground ran for format-recovery only; the other 7 did not get oracle/nop.
- `validate_bundle.py --semantic`: did not run.
- `playground.py --model`: did not run (would upload to api.openai.com).
- Judge channel behaviour and actual rewardkit aggregation: UNVERIFIED.
- Template `test_output.py` files were read at function level by two subagents and spot-checked by me (build-repair hidden entries, `_score`, cli-config negative, format-recovery capture generator, service-interaction datagen); not every assertion line was re-read by me.
- `reference/frontier-bench/` (upstream rubric/docs copies) not read; no code path references it (grep of the four .py files finds only comments mentioning "frontier-bench").
- QC scripts' own rules: out of scope (analysed separately); only the parts vb/pg call were checked.
