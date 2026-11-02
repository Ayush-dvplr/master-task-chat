# Research kit audit: Harbor 0.23 to 0.24 kit vs installed tools and current QC

Generated 2026-10-20 23:01-23:20 IST (17:31-17:50 UTC). Read-only audit of
`/Users/mac/Desktop/Terminal Bench/research/` (274 files). Machine evidence lives in
`/tmp/opencode-logs/research-kit-analysis-20261020T2301/`; every command and exit code is in
`RUN_LOG.md`. `claims.json` holds 88 claims: 75 STILL_TRUE, 2 STALE, 11 UNVERIFIED.

Bottom line: almost every claim the kit makes about Harbor is still true on 0.24.0. The task
format did not change. The thing that did change is the bundle shape the QC and the generator
require: the rewardkit `test_output.py` plus `judge.toml` plus `reward.toml` test channel,
a separate verifier, a pinned `task.toml` template, an exact five-folder file set, and
single-step only. Both kit examples load and score correctly in Harbor 0.24.0
(oracle 1.0, nop 0.0), and both fail `structure_qc.py` (50 and 51 FAIL lines).
So for this team "the old format is gone" is a QC fact, not a Harbor fact.

Status words: STILL_TRUE / STALE / UNVERIFIED are measured against installed Harbor 0.24.0,
as the brief asks. Where the current QC disagrees, that is shown separately (QC column in B,
and sections C and D).

## A. What each kit file claims

| File | What it claims |
|---|---|
| `00-index.md` | Summary: task format identical in 0.23.0 and 0.24.0 (schema sha256 `6c08a596...ef08d`, 34 scaffold files). 0.24 changes runtime behaviour and CLI flags only. Both examples score oracle 1.0 / nop 0.0. Recommends `final` + `min_reward = 1.0` for multi-step. Lists four traps. Defines evidence IDs L1-L15 (local) and W1-W27 (web), the places sources disagree, an UNVERIFIED list and open questions. |
| `01-report-0.23-to-0.24.md` | No task format change, so no file edits are needed to load under 0.24. Lists 9 runtime changes (separate-verifier image precedence, RewardKit per-file grouping, multi-step leak fix, MCP/skills preflight and others), the CLI flag changes, the dependency changes and 7 action items. |
| `02-format-spec-0.24.md` | Full reference: single-step, multi-step and other layouts; every `task.toml` field with type and default; the runtime paths inside the container; reward file parsing; oracle and nop; canary stripping; README; datasets. |
| `03-decisions.md` | D1-D15: single-step by default, a separate verifier for TB, pytest + CTRF, binary `reward.txt`, `network_mode` (never `allow_internet`), digest pins, canary always, explicit resources, README always, `final` multi-step strategy, schema 1.4, TB instruction suffix, root agent user. |
| `04-checklist.md` | 45 testable pre-submit items (A1-I3) with shell or Python one-liners, plus a `keycheck.py` that flags unknown `task.toml` keys. |
| `examples/single-step/` | `research-kit/log-status-summary`: pytest verifier, binary `reward.txt`, agent `no-network`, verifier `public`, canary on instruction line 1. `VALIDATION.md`: oracle 1.0, nop 0.0. |
| `examples/multi-step/` | `research-kit/config-then-report`: 2 steps, `min_reward = 1.0` on step 1, `final` strategy. `VALIDATION.md`: oracle 1.0, nop 0.0, half-solved 0.0 under `final` and 0.5 under `mean`. |
| `_scaffold-0.23/`, `_scaffold-0.24/` | `harbor task init` output for the `single`, `multi` (`--steps 2`), `canary` and `minimal` variants (34 files each, identical). |
| `_evidence/0.23/`, `_evidence/0.24/` | 74 and 76 `--help` captures, task schema JSON, version files, parser edge cases (L9), lint absent (L10), run summaries (L8, L14), checklist test (L15) and its scripts (`checklist-test.zsh`, `plant.py`, `keycheck.py`). |

## B. Re-verification against installed Harbor 0.24.0

The full per-claim list is in `claims.json`. Tools on this Mac: `harbor --version` prints
`0.24.0` (exit 0). `harbor-rewardkit` 0.2.1 is **not installed** as a tool or a package:
`pip3 show` and `uv tool list` do not list it. It exists only in the uv cache
(`~/.cache/uv/archive-v0/uZX90PsFgbA2_FvK/harbor_rewardkit-0.2.1.dist-info`) and is used inside
the verifier image (`pip install harbor-rewardkit==0.2.1`).

### B.1 `00-index.md` and `01-report` claims

| Claim (source) | Harbor 0.24.0 | Evidence | QC view |
|---|---|---|---|
| Schema byte-identical, scaffolds identical, default 1.4 (`00-index.md:8-10`, `01-report:9-14, 31-36`) | STILL_TRUE | Re-run in SCRATCH: sha256 `6c08a596...ef08d` equals both saved schemas; the 4 init variants (34 files) match `_scaffold-0.24` and `_scaffold-0.23` under `diff -r` (`rerun.log`) | QC needs a different file set anyway (C) |
| CLI changes (`00-index.md:11-14`, `01-report:70-81`) | STILL_TRUE | All 76 `COLUMNS=200 --help` captures are identical to `_evidence/0.24/allhelp`; `run --help` has `--share`, `--diff`, `--effort`, `--stream`, `--use-static-ip` | n/a |
| Runtime changes: verifier image precedence, leak fix, MCP/skills preflight (`01-report:50, 53, 54`) | STILL_TRUE (source) | `verifier_mode.py:95-116`, `trial.py:829-836` (`_reset_shared_step_verifier_dirs`), `trial.py:1619-1627` | QC relies on the precedence (`Final_checklist.md:36`) |
| RewardKit per-file grouping, pin 0.2.* (`01-report:51`) | STILL_TRUE | A current-format bundle scored through `[scoring.test_output]` (see the separate-verifier row) | QC narrows the pin to exactly `==0.2.1` (tests_qc K5) |
| RewardKit rejects non-finite scores; CSV column change (`01-report:52`) | UNVERIFIED | rewardkit internals not tested. Harbor itself rejects non-finite values (`verifier.py:83`, `:118`) | - |
| Examples score oracle 1.0, nop 0.0 (`00-index.md:15-16`, L8) | STILL_TRUE | Re-run: single 1.0 / 0.0; multi 1.0 (both steps) / 0.0 (step 2 skipped); 0 exceptions | Both examples fail QC (`qc_on_bundles.log`) |
| `final` vs `mean` arithmetic (`00-index.md:17-19`, L14) | STILL_TRUE | `trial.py:793-825`; multi oracle and nop re-run; half-solved runs not repeated | Multi-step not allowed by QC |
| Separate verifier and RewardKit not exercised (`00-index.md:116`, `01-report:111-112`) | **STALE** (now exercised) | `exe_copy.py` tests-only copy of `district-heat-flex-procurement`: verifier built from `tests/Dockerfile`, rewardkit 0.2.1; oracle 1.0, nop 0.0, `reward.json` and `reward-details.json` written (`dh-oracle.log`, `dh-nop.log`). The judged channel was not run | Matches QC Step 10 |
| L1-L7, L9-L13, L15 | STILL_TRUE | `rerun.log`, `traps.log`, `checklist-test.log` (heading and rc sequence identical to the first 122 lines of `_evidence/0.24/checklist-test.txt`); source spot-checked; `harbor-0.24.0.dist-info/RECORD` is dated 14 Oct 2026, before the kit was written | - |
| Disagreements table (`00-index.md:101-111`) | STILL_TRUE, except W1 docs version (UNVERIFIED, web not fetched) | `headers` count in the schema = 0; scaffold timeouts 600.0; canary cases in `traps.log` | Reward row: QC uses rewardkit `reward.json`, not binary `reward.txt` |
| Agent `no-network` enforcement (`00-index.md:117-118`) | UNVERIFIED | Harbor accepted agent `no-network` on this host (Docker 29.8.2 linux/arm64) and the runs completed; egress was not probed | QC `Final_checklist.md:378-385` says Docker Desktop refuses `no-network`; that is not what this host does |
| Release dates, 146 commits, librarian diffs, docs 1.3 (`01-report:22-24, 37-42`) | UNVERIFIED | No GitHub or web fetch: `harbor-framework/harbor` is not on the allowed repo list | - |
| Temp folders and `/tmp/harbor-v024` left behind (`00-index.md:133-147`) | STILL_TRUE | `ls -d` shows all 7 still present | Cleanup command in "Commands for Ayush" |

### B.2 Decisions D1-D15

Every decision still describes Harbor 0.24.0 correctly (all STILL_TRUE). The QC column is
the one that matters for authoring.

| D | Decision | Harbor 0.24.0 | QC (current) |
|---|---|---|---|
| D1 | Single-step by default | STILL_TRUE | **Single-step only.** S2 needs a root `instruction.md` and `solution/solve.sh`, S3 rejects `steps/`, T2 root keys must be exactly `[schema_version, artifacts]` (`structure_qc.py:129-143`) |
| D2 | Separate verifier for TB; shared is fine for own tasks | STILL_TRUE | Conflicts: separate is mandatory (T2 `structure_qc.py:455-459`) |
| D3 | `test.sh` runs pinned pytest + CTRF | STILL_TRUE | Conflicts: rewardkit `test_output.py` (tests_qc A1-A5, W1-W7, B1); `ctrf.json` is forbidden (S5) |
| D4 | Bake deps for TB; runtime install for own tasks | STILL_TRUE | Always bake into `tests/Dockerfile` (K2, K4, K5, K7). The verifier allowlist only reaches OpenAI, so a runtime install fails |
| D5 | Binary `reward.txt`, write 0 first | STILL_TRUE | Conflicts: B4 fails `echo 0 > /logs/verifier/reward.txt`; the reward is rewardkit's weighted sum, -1..1 (`Final_checklist.md:229-231`) |
| D6 | `network_mode`, never `allow_internet` | STILL_TRUE | Agrees on the key; values pinned: env `no-network`, verifier allowlist to OpenAI, agent allowlist to anthropic/z.ai (T12) |
| D7 | Digest pins, pinned pip, unpinned apt | STILL_TRUE | QC does not check base digests; the generator requires a digest-pinned `public.ecr.aws` FROM (`validate_bundle.py:503-510`). QC pins rewardkit and the openhands packages but keeps `fastapi` unpinned (S9) |
| D8 | Canary in every file, one line, first line of the instruction | STILL_TRUE | Conflicts: IN-4 "no GUIDs" in `instruction.md` (`01_Instruction_QC.md:34`) |
| D9 | Explicit resources and timeouts | STILL_TRUE | Agrees (T2 key presence, T11, T13) |
| D10 | Always README, keep `.gitignore`; optional extras | STILL_TRUE | Conflicts: README.md, .gitignore, trajectory.json, workdir/ all fail S3; TRUTH.md, judge.toml and reward.toml are required (S2) |
| D11 | `[metadata]` per target benchmark | STILL_TRUE | Conflicts: 8 pinned keys, no `difficulty` (T2, T13) |
| D12 | `final` + `min_reward = 1.0` | STILL_TRUE (source + runs) | Not applicable: multi-step is not allowed |
| D13 | `schema_version = "1.4"` | STILL_TRUE | Agrees (T3) |
| D14 | Absolute paths, exact schema; TB suffix for TB only | STILL_TRUE | IN-1/C1 requires "You have N seconds" with N = `[agent] timeout_sec`. The "do not cheat" sentence is unchecked by QC (IN-10) but required by the generator (§2.5). Headings are allowed |
| D15 | Agent user left as root | STILL_TRUE | Conflicts: `[agent] user = "1000:1000"` (T13), uid 1000 account (S10), writable artifact directories (S8) |

## C. Harbor schema vs QC bundle shape (what is actually gone)

Full table with 47 rows in `harbor_vs_qc.json` (27 stricter, 13 qc_only, 5 different, 2 same).
Evidence for "Harbor accepts it but QC does not": the QC-template `task.toml` (filled) passes the
kit's `keycheck.py` ("OK: all keys known to the schema") and `TaskConfig` loads it with
`environment_mode=separate`, `agent.user=1000:1000` (`traps.log`). The current-format bundle
`district-heat-flex-procurement` passes all four QC scripts (exit 0) **and**
`Task.is_valid_dir` = True. So the QC shape is a strict subset of what Harbor 0.24.0 accepts.
Nothing the QC requires is outside Harbor's schema.

What is gone for QC-bound tasks (all from the kit's 0.23/0.24 way of working):

| Area | Kit / Harbor 0.24.0 | QC requires | Check |
|---|---|---|---|
| File set | task.toml, instruction.md, environment/, tests/, solution/, plus README.md, .gitignore, extra helpers | exactly root {instruction.md, task.toml, environment, solution, tests}; environment {Dockerfile, data}; solution {solve.sh, solve.py?, TRUTH.md}; tests {Dockerfile, test.sh, test_output.py, judge.toml, reward.toml} | S2, S3, S4 |
| Multi-step | `[[steps]]` + `steps/<name>/` | not allowed | S2, S3, T2 |
| Verifier | shared by default | separate verifier, image built from `tests/Dockerfile`, `COPY . /tests/`, `harbor-rewardkit==0.2.1`, `LITELLM_LOCAL_MODEL_COST_MAP=True` | T2, K1-K7 |
| Deterministic tests | pytest `test_outputs.py`, CTRF | `test_output.py` with `@criterion` functions and `criteria.<name>(weight=W)`, 10-35 checks, W in {±1,±3,±5}, at least one negative | A1-A5, W1-W7 |
| Judged channel | none | `judge.toml`, pinned `[judge]` (`openai/gpt-5.6-sol`, individual, 300, `atif-trajectory`, 1.0), at least 8 annotated criteria | judge_qc G1-G6, J1-J13 |
| Reward | `test.sh` writes binary `reward.txt` | `test.sh` writes nothing and ends with `exec rewardkit ...`; `reward.toml` combines both channels 50/50 (each `0.5 / positive total`); range -1..1 | B1-B5, R1-R5 |
| task.toml | any key, any order; unknown keys silently ignored | exact template, table and key order fixed, extra keys fail; name `terminal-bench/<dir>`; authors `@ethara.ai`; 8 pinned metadata keys; `docker_image` forbidden | T1-T15 |
| Network | `public` default, per-phase overrides optional | env `no-network`; verifier and verifier.environment allowlist `api.openai.com`, `*.openai.com`; agent allowlist `api.anthropic.com`, `api.z.ai` | T12 |
| Agent image | anything | uid 1000 account + `ENV HOME`; openhands-sdk 1.55.1 venv pre-baked; artifact directories writable by uid 1000; COPY only from `data/` | S7-S10 |
| Instruction | canary allowed and stripped | no GUID (IN-4); "You have N seconds" = agent timeout (C1); no em/en dash anywhere (X1); no word "reward" (C3) | IN-4, C1, C3, X1 |

Where the generator differs from the QC (both are "current" authorities):
- The generator **tolerates `cheat/`** (`validate_bundle.py:277-306`); the QC **fails** it (S3). Do not ship `cheat/`.
- The generator **requires** `solve.py` and a flat `environment/data/`, a digest-pinned `public.ecr.aws` FROM, an apt layer with `xxd file curl bash nodejs npm procps ca-certificates`, `RUN mkdir -p /app && chown 1000:1000 /app`, an online-lookup sentence and an instruction under 6000 characters. The QC needs none of these. A bundle that passes the generator passes the QC scripts too (it calls them, §3.3-3.4, 7.5-7.6); the reverse does not hold.
- `FORMAT_SPEC.md:3-7` says it is superseded by `Final_checklist.md`. Its v1 body (README.md, `test_weights.json`, `rubric.json`, CTRF, `reward.txt`) is the "old format" that is gone. That was the team's own bundle format, not a Harbor format.
- The generator's QC path is `Terminal_2.0_Harbor_Harness/Input_Bundle_QC` (`validate_bundle.py:1225`). On 2026-10-20 `diff -rq` against `QC assigned/Input_Bundle_QC` shows **no difference**, and the harness HEAD is `9b8229f6`. The brief's "2 commits stale" note no longer holds.

## D. Checklist `04-checklist.md` vs QC

Verdicts: **covered** (a QC check already does it, ID given), **needed** (no QC check; still
worth running), **conflicts** (running it as written would push a bundle to fail QC), **n/a**
(multi-step, which QC does not allow).

| Item | Verdict | Why |
|---|---|---|
| A1 Harbor is 0.24.0 | covered | Step 10 preflight `harbor --version` >= 0.24.0 (`Final_checklist.md:327-335`) |
| A2 `Task.is_valid_dir` + `Task(p)` | needed | QC never calls Harbor's loader (T1 is `tomllib`). Harbor validators (author name, artifact paths) can make a dir silently stop counting as a task (`Final_checklist.md:309` FC-S18 says so). Cheap |
| A3 Required files | covered (stricter) | S2 + S3 exact set; the multi-step branch conflicts |
| A4 Step names match folders | n/a | multi-step not allowed |
| A5 No tests/solution in agent image | covered | S7, DS-8, DS-23 |
| A6 macOS junk, CRLF | covered, mostly | S5 (.DS_Store, __pycache__, .pytest_cache), S6 (CRLF). `._*` AppleDouble files inside `data/` are not caught (S3 only lists the top of each folder): keep that part |
| B1 Parses with `TaskConfig` | needed | QC parses with `tomllib` only; Harbor-model validation still adds value |
| B2 No unknown keys (`keycheck.py`) | covered (stricter) | T2 exact key lists and order; the QC template passes `keycheck.py` |
| B3 schema 1.4, no top-level `version` | covered | T3 + T2 root keys |
| B4 `org/name` | covered (stricter) | T13 `terminal-bench/<dir>` |
| B5 No deprecated fields | covered | T2 exact keys exclude `memory`/`storage`; T12 bans `allow_internet` |
| B6 Resources and timeouts explicit | covered | T2, T11, T13; the multi-step part is n/a |
| B7 No MCP `headers` | covered | T13 `mcp_servers = []` |
| B8 `--dry-run` | needed (optional) | not a QC item; a cheap config check before Step 10 |
| C1 Image builds, no exception | covered | Step 10: an errored trial is not a score (`Final_checklist.md:403`) |
| C2 `network_mode`, not `allow_internet` | covered | T12 |
| C3 [TB] Digest pins | conflicts for `tests/Dockerfile` | The QC template's `FROM python:3.12-slim` is unpinned and accepted; the generator pins only `environment/Dockerfile` (§5.2). Apply to the environment image only |
| C4 pip pinned, apt unpinned | partly covered, partly conflicts | K5, S9 pin rewardkit and openhands; S9 requires `fastapi` **unpinned**, so "every Python package has ==" fails the QC template. Keep it for other verifier deps (TS-4 only requires them installed) |
| C5 [TB] Separate verifier, deps baked, artifacts | covered (required) | T2, T4, K2, K4, TS-2 |
| C6 [TB] Network public | conflicts | T12 pins env `no-network` and allowlists |
| D1 Canary first line of instruction | conflicts | IN-4 "no GUIDs" |
| D2 Canary in every other file | not needed | no QC rule either way; drop it at least from `instruction.md` |
| D3 Absolute paths in instruction | covered, mostly | C5 (artifacts by full path), C4, generator §2.3; IN-5 forbids findings about unmentioned inputs |
| D4 Every `/app` path the tests use is in the instruction | covered | C5, IN-6, DS-25, CL-5 |
| D5 [TB] Suffix, no headings | partly covered | "You have N seconds" = C1/IN-1. The "Do not cheat" sentence: no QC check (IN-10), but generator §2.5 requires one. Headings are allowed by QC (`01_Instruction_QC.md:19`) |
| E1 `echo 0 > reward.txt` default | conflicts | B4 fails any reward write in `test.sh` |
| E2 Binary reward | conflicts | the reward is a weighted sum in -1..1 (`Final_checklist.md:229-231`) |
| E3 Expected values from hidden reference | covered | TS-5, TS-7, CL-3, CL-10 |
| E4 Protected inputs: sha256 vs a `/tests` reference copy | conflicts as written | S3 forbids reference files in `tests/`, and `/app/data` does not exist in the verifier (TS-1). Use the template pattern: a sha256 constant in `test_output.py`, the file declared as an artifact, and a `negative_<cheat>` check (`Final_checklist.md:178-207`) |
| E5 One CTRF per verifier run | conflicts | `ctrf.json` forbidden (S5); rewardkit writes `reward-details.json` |
| E6 Stable: `-k 3` Mean 1.000 | covered (stricter) | Step 10: five oracle runs, each exactly 1.000 |
| E7 No test-only requirements | covered | TS-19, AL-1, Step 11 coverage |
| F1 Oracle derives the answer | covered | DS-14, CL-8, DS-24 |
| F2 `set -euo pipefail` in solve.sh | needed | no QC check; the generator templates already do it |
| G1 Oracle 1.0 | covered (stricter) | Step 10 on the `exe_copy.py` copy, 5 runs |
| G2 nop 0.0 | covered | Step 10 nop exactly 0.000; the stub run is extra |
| G3 Nothing uploaded | needed | no QC rule; Step 10 commands carry no `--upload`/`--share` |
| H1-H5 Multi-step strategy, gates, standalone steps | n/a | multi-step not allowed |
| I1 README says what it tests | conflicts | README.md fails S3 |
| I2 Description filled | covered (stricter) | T5 (one paragraph, at most 100 words) |
| I3 [TB] README sections and metadata keys | conflicts | README forbidden; metadata keys pinned differently (T2) |

Counts (45 items): covered 23 (including "mostly", "stricter" and D5 "partly"), needed 5 (A2, B1, B8, F2, G3), not needed 1 (D2), conflicts 9 (C3, C6, D1, E1, E2, E4, E5, I1, I3), split 1 (C4: partly covered, partly conflicts), n/a 6 (A4, H1-H5).

## E. The kit's traps in 0.24.0

| Trap | Still holds? | Evidence | Hardness use / QC risk |
|---|---|---|---|
| Unknown `task.toml` keys silently ignored | Yes | `[enviroment]`, `cpu = 2`, root `stepz` load with no warning (`traps.log`) | No hardness use. QC T2 makes it harmless (exact keys), but an author tweaking `task.toml` by hand can still believe a typo key took effect while running Step 10. rewardkit is the opposite: `judge.toml` and `reward.toml` models are `extra="forbid"` (`rewardkit/models.py:31, 45, 293, 314, 335`), so a typo there aborts the verifier with no reward |
| Only one-line canaries stripped | Yes | `task.py:10`; a two-line comment reaches the agent (`traps.log`) | QC fails any GUID in the instruction (IN-4), so leave the canary out. A multi-line HTML comment in `instruction.md` reaches the agent verbatim: never hide notes there |
| Step verifier timeout not inherited | Yes | step 600.0 vs task 300.0 (`traps.log`; `trial.py:838-843`) | Irrelevant under QC (single-step only) |
| Separate verifier sees only `artifacts` | Yes | `verifier_mode.py:95-116`, `trial.py:949`; the dh-oracle run graded from artifacts only | Central to QC: any output a test reads must be in `artifacts` (T4), and `/app/data` reads crash (TS-1). For hardness: the agent cannot tamper with anything outside the artifacts, so files the agent was told to leave alone can only be graded if they are declared artifacts (TS-12) or through the judge |
| `final` vs `mean` multi-step strategy | Yes | `trial.py:793-825` | n/a under QC |
| (QC-specific) rewardkit `str.format` on criterion descriptions | Yes, in 0.2.1 | `rewardkit/session.py:133` `description.format(**bound)` | A `{` or `}` in a `@criterion` description raises KeyError and writes no reward (tests_qc A4) |

None of these traps gives legitimate hardness. Hardness has to come from the task itself.

## F. Multi-step under the current QC and generator

Not allowed. Evidence:
- `structure_qc.py:129-132` requires a root `instruction.md` and `solution/solve.sh` (S2).
- `structure_qc.py:134-139`: the root may hold only `instruction.md, task.toml, environment, solution, tests`, so `steps/` fails S3.
- `structure_qc.py:143, 425-427`: root keys must be exactly `["schema_version", "artifacts"]`, so `multi_step_reward_strategy` and `[[steps]]` fail T2. Observed: `T2 root keys must be exactly ['schema_version', 'artifacts'] in order, found ['schema_version', 'multi_step_reward_strategy', 'steps']` on the kit's multi-step example (`qc_on_bundles.log`).
- `instruction_qc.py`, `tests_qc.py` and `judge_qc.py` exit 2 (usage error) on the multi-step example because the root files are missing.
- No QC markdown and no generator file mentions multi-step: no hits for `multi.?step|[[steps]]|steps/|multi_step|min_reward` in `QC assigned/Input_Bundle_QC/*` or in `validate_bundle.py`, `generate_bundle.py` and the generator `*.md`. The QC never says "no multi-step" in words; it is excluded by the exact templates.

Harbor itself runs multi-step fine (multi oracle 1.0, nop 0.0 in this audit). Staged work has to
be expressed inside one instruction, with milestones graded as separate weighted checks.

## G. Kit material useful for making tasks harder

1. Partial-credit design, not all-or-nothing: the kit's D12 analysis shows how `mean` rewards half-solved work. Under QC the same idea comes from weighting independent facts separately (CL-4); the kit's per-step milestone thinking maps onto multiple `criteria.<name>(weight=...)` checks.
2. Hidden-reference grading (D3, E3): compute expected values from data embedded in `tests/` (now inside `test_output.py` or the verifier image), never from agent-writable files. This keeps hard tasks honest.
3. Protected-input tamper detection (E4), rewritten as a `negative_<cheat>` sha256 check on a declared artifact.
4. Separate verifier sees only artifacts: graders can recompute from fresh data the agent never saw (the `data-pipeline` template runs the agent's program on newly generated input, `templates/data-pipeline/instruction.md:3`). This defeats hard-coding and filename keying (AL-10, AL-24).
5. Example-instruction patterns that QC also likes: exact output schema, explicit tie-break ("sorts first alphabetically"), explicit rounding (`examples/single-step/instruction.md:16-19`). These close IN-16 ambiguity while keeping the computation hard.
6. Dirty-input handling as a trap: "Some lines are not valid log entries ... Ignore every line that does not match" (`examples/single-step/instruction.md:8-9`). This is an honest trap that satisfies CL-6 because it is signposted.
7. The `harbor check` rubric (L11) and the TB `task-implementation.toml` (W19, also in `Input Bundle Generator New/reference/frontier-bench/rubrics/`) as an outside difficulty review, if paying for a model run is acceptable.
8. Not useful for hardness: canary, `no-network` for the agent (TB: "disabling network access is not a valid way to make a task difficult", D6), unknown-key or timeout traps.

## H. Gaps: what an author still needs that neither the kit nor the QC documents

1. **How to write and debug `test_output.py` locally without Docker.** No guide shows running rewardkit 0.2.1 directly (for example `uvx --from harbor-rewardkit==0.2.1 rewardkit tests --workspace <dir>`) against a fake `/app`. rewardkit is not installed on this Mac. Not tested here.
2. **How the judged channel behaves in a real run.** The QC validates `judge.toml` but never executes it (`Final_checklist.md:345`); the kit predates it. Nobody documents the judge cost per trial, the variance across repeated judge runs, or what `reward-details.json` looks like for judge criteria.
3. **The real-agent run command for both channels**: only a one-line hint (`--ve OPENAI_API_KEY=...`, `Final_checklist.md:387`). There is no worked command with the `openhands-sdk` agent, model, and where the trajectory lands for `atif-trajectory`.
4. **Network enforcement on this Mac.** QC says Docker Desktop refuses `no-network`/`allowlist` (`Final_checklist.md:378-385`), but on this host Harbor accepted agent `no-network` (L8 re-run). Whether the full QC network trio (env `no-network` + allowlists) runs unmodified here, and whether egress is actually blocked, is UNVERIFIED. If it does run, Step 10 could use the real network policy.
5. **Hardness calibration.** Neither source says what pass rate or score band counts as "hard enough", or how to measure it before shipping (the kit has no model runs; the QC is shape and fairness only). `AL-8` judges time estimates by reading.
6. **Generator vs QC disagreements** (`cheat/`, `solve.py`, flat data, digest FROM, online sentence) are not written down anywhere as one list. Section C above is the first.
7. **Where the rewardkit 0.2.1 pin comes from.** The QC says Harbor 0.24.0's own `rewardkit/pyproject.toml` names 0.2.1 (`Final_checklist.md:36`). The installed Harbor wheel contains no rewardkit reference, and the local fork's `packages/rewardkit/pyproject.toml` says `0.1.7`. UNVERIFIED.
8. **Canary policy.** The kit says always; the QC bans GUIDs in the instruction and is silent elsewhere. No decision exists on whether other files should carry the canary.

## Commands for Ayush

Only cleanup, which this audit is not allowed to do (destructive, outside SCRATCH). These are the
kit's own leftovers from 17 Oct. Check that nothing you still need lives in them first.

```bash
rm -rf /tmp/harbor-v024
rm -rf /tmp/opencode-logs/jobs /tmp/opencode-logs/half-final /tmp/opencode-logs/half-mean \
       /tmp/opencode-logs/legacytask /tmp/opencode-logs/scaffold-check "/tmp/opencode-logs/bad task"
```

No git command is needed: the QC copies are already identical.

## Not checked

- Web sources W1-W27 (changelog, PRs, release dates, TB CONTRIBUTING/CI rules, docs): no outbound fetch; all W-only claims stay UNVERIFIED.
- Harbor 0.23.0 side of any diff (no `uvx harbor==0.23.0` run); the kit's saved 0.23 captures were compared only against re-run 0.24 output.
- The kit's half-solved multi-step runs (L14 half-final, half-mean) and its planted-fault checklist copies (L15 bad task): not re-run; the source code supports both.
- The judged channel (`judge.toml`) was never executed: no API key use, by rule.
- QC model gates 01-05 and Step 11 were not run on any bundle; only the four scripts and `exe_copy.py` were.
- Agent-side egress enforcement for `no-network`/`allowlist`; `[steps.verifier]` user/network fallback; `dataset.toml` fields; rewardkit non-finite handling.
- `validate_bundle.py` was read, not run.
