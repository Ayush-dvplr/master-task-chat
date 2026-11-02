# P10 upstream diff: PL generator + Input Bundle QC, 9b8229f6..bfe40804

Measured 22 Oct 2026 09:40 to 10:05 IST (04:10 to 04:35 UTC). Clone HEAD confirmed `bfe40804ff6d7e29ba94e6c7f1b116ea2154e034`. Read only: `git status` identical before and after, bundle sha256 identical before and after (119 files).

## 1. Verdict

UPSTREAM CHANGED. GEN: 163 files (9 added, 9 removed, both from renames, plus 41 modified). QC: 12 files (9 modified).

The main finding is that the GEN+QC tree at `bfe40804` is byte-identical to the tree at `f0579497`. The merge `bfe40804` ("content is kiro-bridge") takes its GEN+QC content from parent `14b4ccf9`. So the net change is commits 4f7f760b (QC) and f0579497 (generator) only. 8c37863a and bde868c4 (chmod 755, IN-15/JD-15 wording fix, whole-context `COPY .` detection) are fully reverted (`git diff f0579497 bfe40804 -- GEN QC` is empty).

## 2. Commits

9b8229f6..bde868c4 (main side, 5 commits, all confirmed):

| commit | IST | author | touches GEN/QC | net effect at HEAD |
|---|---|---|---|---|
| 4f7f760b | 21 Oct 14:54 | Shreeyank Doliya | QC (9 files) + 9 GEN template renames | kept |
| f0579497 | 21 Oct 14:54 | Shreeyank Doliya | GEN (42 files) | kept |
| 95401d0e | 21 Oct 14:54 | Shreeyank Doliya | no (Tasks_INPUT/cf9b2067 only) | n/a |
| 8c37863a | 21 Oct 15:21 | Sugam Agrawal | GEN 9 + QC 6 | reverted by merge |
| bde868c4 | 21 Oct 15:24 | Sugam Agrawal | GEN 8 + QC 1 | reverted by merge |

bde868c4..bfe40804 is 68 commits (measured with `git rev-list --count`); 9b8229f6..bfe40804 is 73. Commits that touch GEN/QC (`--full-history`) are 14 non-merge plus the merge, 15 in total over 9b8229f6..HEAD. Of those, 11 are inside the 68 (10 non-merge plus the merge), not 15 as the master note says. The 10 non-merge commits are on the kiro-bridge side: 27835845, f9457271, 044c5f3f, 3016254a, dd285b15, fa5e6de0, ca37d72f, 3e2d5479, 0475012b (24 Aug to 16 Sep, older history not reachable from 9b8229f6) and 14b4ccf9 (21 Oct 23:15, "Add Input Bundle Generator New and Input_Bundle_QC", which sets the f0579497 content). A plain path-limited `git log 9b8229f6..HEAD -- GEN QC` hides the main-side commits through history simplification; use `--full-history`.

### What bde868c4..bfe40804 changed (listed separately)

Inside GEN/QC (15 files, `git diff bde868c4 bfe40804`), all of them reverts to the f0579497 state:
- 8 `templates/*/tests/test.sh`: `chmod 755` back to `chmod 700 /logs/verifier`.
- `CHEAT_VECTORS.md` #9 and its mitigation paragraph: back to mode 700 (the 755 rationale is removed).
- QC `tests_qc.py` H5: 700 is ok and anything else warns (it was 755 ok, 700 warn). The whole-context `COPY .` expansion in `input_mounts` is removed.
- QC `structure_qc.py` S4: the whole-context `COPY .` handling is removed, so `COPY . /app` no longer counts as copying every input dir.
- QC `03_Tests_QC.md` TS-28 and `Final_checklist.md` test.sh template: back to `chmod 700`.
- QC `01_Instruction_QC.md` IN-15: back to "carries `kind = "constraint"` (which always comes with `category = "instruction following"`)". Both are retired keys that J6 now fails.
- QC `04_Judge_QC.md` JD-15: back to "an unstated standard labelled `constraint` ... a stated rule labelled `conduct`". Those are not `type` values any more.

Outside GEN/QC (850 files in total, context only): `Output_Bundle_QC/` is deleted (7 files). `AGENTS.md`, `CLAUDE.md`, `HARDNESS.md`, `VERDICT.md` and 6 `.opencode/commands/*.md` are deleted. `Tasks_INPUT/` is down to one task (cf9b2067). `Output/`, `seed/`, `audit/` are deleted. New: `input/`, `outputs/`, `scripts/` (25 added, 22 modified), `HYBRID_RUN_GUIDE.md`, `SETUP.md`, `TRACKING.md`, `sign_provenance.py`, `run_glm_batch*.sh`.

## 3. File changes (every changed file accounted for)

QC, modified (9): `01_Instruction_QC.md`, `02_Data_Solution_QC.md`, `03_Tests_QC.md`, `04_Judge_QC.md`, `05_Alignment_Integrity_QC.md`, `Final_checklist.md`, `judge_qc.py`, `structure_qc.py`, `tests_qc.py`. Unchanged: `Starter.md`, `exe_copy.py`, `instruction_qc.py`.

GEN, renamed (9 removed, 9 added):
- `templates/repo-patch/environment/data/repo/**` (6 files) moved to `environment/repo/**`.
- `templates/repo-patch/environment/data/api_contract.md` moved to `environment/ci/api_contract.md`, with its paths changed to `/app/ci`.
- `templates/service-interaction/environment/data/service/{client,simulator}.py` moved to `environment/service/`.

GEN, modified (41):
- Code: `README.md`, `generate_bundle.py`, `playground.py`, `task_memory.py`, `validate_bundle.py`.
- Tests: `tests/test_generator_contract.py`, `tests/test_memory_playground.py`, `tests/test_truth_md.py`.
- All 8 archetypes: `archetype.toml`, `solution/TRUTH.md`, `tests/judge.toml` (24 files).
- repo-patch also: `datagen.py`, `environment/Dockerfile`, `instruction.md`, `solution/solve.py`, `tests/test_output.py`.
- service-interaction also: `environment/Dockerfile`, `environment/data/api_contract.md`, `instruction.md`, `solution/solve.py`.

Unchanged in all 8 archetypes: `task.toml`, `tests/Dockerfile`, `tests/test.sh` (700 at both ends). No `add_argument` change in `generate_bundle.py` or `validate_bundle.py`.

## 4. Check and rule changes

The full list (47 entries: id, kind, old, new, impact, templates) is in `changes.json`. The rows below are the ones that change authoring.

### QC (net: 4f7f760b)

| ID | kind | old, then new | severity, owner |
|---|---|---|---|
| DS-1 / FC-S3 / S3 / S4 | reworded, threshold | `environment/data/` only, at least 1 file. Now: any number of named input dirs; each non-empty and each a COPY/ADD source; a loose file under environment/ fails; `COPY .` is not recognised | FAIL, script structure_qc S3/S4 |
| DS-2 | reworded | deleting data/ makes the task unsolvable. Now: deleting any single input dir must make it unsolvable | FAIL, manual |
| DS-4, DS-9, DS-16, AL-11 | reworded | data/ becomes "every input directory" or "/app/<dir>" | FAIL / allowance, manual |
| IN-S7 | reworded | promised paths under `/app/data/`. Now: under any input COPY destination | FAIL, script instruction_qc C4/C5 (script unchanged; C4 already resolves COPY) |
| TS-1 / TS-S7 / D1 | reworded, threshold | no unconditional `/app/data` read. Now: no unconditional read of any input COPY destination (`input_mounts`) | FAIL, script tests_qc D1 |
| 04 schema, JD-S8 / J6 | removed | 8 keys plus kind-specific extras. Now: exactly `mode, type, evaluation_target, importance`; `category, kind, serves, residue, evidence, contract_sentence, contract_file` FAIL | FAIL, script judge_qc J6 |
| JD-S9 / J7 | threshold | effect `type`, residue sentence, kind iff category. Now: `type` is the category set ("safety and boundaries" with "and"), plus target and importance sets | FAIL, script judge_qc J7 |
| JD-15 | reworded | "declares its own answer in annotations.kind". Now: "its annotations type is a claim to check" (keeps the stale words `constraint`/`conduct`) | FAIL, manual; thresholds unchanged |
| JD-16 (item 2, checklist) | reworded | `kind = "constraint"` + `category = "instruction following"`. Now: `type = "instruction following"` | FAIL, manual |
| IN-15 | no net change | still says `kind = "constraint"` (a retired key); the bde868c4 fix was reverted | FAIL, manual. Upstream defect |
| H5 / TS-28 | no net change | 700 at both ends; bde868c4's 755 was reverted | WARN, script tests_qc H5 |

Unchanged although the master notes list them as changes: JD-13 / J13 (pairing by |weight| was already present at 9b8229f6), DS-27 (already present at 9b8229f6; what is new is the validator enforcing it). No check ID was added, removed or renumbered.

### Generator (net: f0579497)

| item | change |
|---|---|
| archetype.toml | new `[[inputs]]` (dir, mount) and `datagen_input`; default `data` to `/app/data` |
| repo-patch | `data/repo.zip` + context becomes `environment/repo/` (`COPY --chown=1000:1000 repo /app/repo`) + `environment/ci/` (`COPY ci /app/ci`); `source_archives` dropped; `datagen_input = "ci"`; paths in instruction, contract, TRUTH and solve.py move to `/app/repo` and `/app/ci` |
| service-interaction | same kind of change: `data/service.zip` becomes `environment/service/` (`COPY service /app/service`) + `environment/data/`; no extraction step. The other 6 archetypes keep `data/` (build-repair and cli-config still zip `project/` and `tool/` inside data/) |
| judge.toml (8) | 4-key annotations; generator dies on any other key list |
| TRUTH.md (8) | provenance drops `authored_by, status, archetype, generator_seed, trailer_token`; prose drops "generator seed" and "archetype" |
| validator §15.5 | `authored_by`/`status` were required and are now forbidden, together with archetype/generator_seed/trailer_token; also FAILs on narration words (`generate_bundle`, `harbor-generator`, `archetype(s)`, `scaffold`, `generator seed`, `datagen`, "this bundle/task was built/generated/..."). Resolves Q13 |
| validator §1.4, §5.5 | layout and COPY lines must equal the detected archetype's `[[inputs]]` (flags stripped; last line one of them). Titles still say "data/ only" |
| validator §1.7 | the "data must be flat" requirement is removed; every input dir is non-empty |
| validator §1.12 detection | archetype = the unique template whose artifacts equal task.toml artifacts, else format-recovery (TRUTH `archetype:` is no longer read); `--archetype` help text is stale |
| validator §1.13, §5.6, §6.3 | count, size and scan every input dir, recursively |
| validator `--semantic` | runs on an `exe_copy.py` tests-only copy and reads `reward.json["reward"]` (did not run it) |
| playground | `--ablation sample|full|off` (default sample: 1 unit per dir + up to 8), `--jobs` (default 2); a tree dir is one unit; memory reuse of a full pass; `A3-judge-contract` removed; ablation_max found through artifact detection |
| generator internals | `{{SHIPPED:<dir>}}` token; `{{SHIPPED_DATA}}` is now the `datagen_input` dir; trailer token is now `<tag>:<sha256[:16]>` (was `harbor:<arch>:<tag>:<seed>`), so the same seed gives different output than before; TRUTH data list uses image paths; memory keys are `<dir>/<path>` |
| unchanged | CLI flags of generate_bundle/validate_bundle, `task.toml` template, `tests/Dockerfile`, `[judge]` header, reward.toml maths, validator rule IDs and severities (52 rules, all FAIL), playground A5 numbers (2,000 per record file, 20,000 total) |

## 5. Master's notes checked against the diff

| note | result |
|---|---|
| 5 commits 9b8229f6..bde868c4 | confirmed |
| 68 commits after bde868c4, "only 15 touch GEN/QC" | 68 confirmed; 11 of them touch GEN/QC (15 is the count for all of 9b8229f6..HEAD) |
| four-key annotations, old keys retired | confirmed (J6, J7, generator guard) |
| JD-13 importance vs |weight| | not changed in this range (already at 9b8229f6) |
| TRUTH must not carry the 5 keys (validator + DS-27) | confirmed for the validator (§15.5); DS-27 itself is unchanged |
| test.sh `chmod 755` | wrong at HEAD: 700 (the 755 change was reverted by the merge) |
| `--semantic` reads reward.json; sampled ablation | confirmed |
| named input dirs, `[[inputs]]` | confirmed |
| repo-patch becomes repo/ + ci/, §1.4/§5.5 fail the old layout | confirmed. service-interaction also changed (service/ + data/) |

## 6. Impact

| change | what a builder or fixer must now do differently | templates affected |
|---|---|---|
| 4-key judge annotations | write exactly `mode, type, evaluation_target, importance`; put the category in `type`; constraints are `type = "instruction following"`; no contract_sentence, so record the source sentence in LEVERS/TRUTH for reviewers | P2, P4, P7, P9, knowledge/qc_authoring_checklist (line 95) |
| §15.5 + DS-27 | delete `authored_by`, `status` (and the other 3) from TRUTH provenance; never write archetype, scaffold or datagen in TRUTH.md | P2, P4, P7, _COMMON_RULES, knowledge/KNOWLEDGE.md (lines 30, 35), qc_authoring_checklist (line 69: the conflict is gone) |
| named input dirs (QC) vs archetype layout (validator) | QC accepts any dir names, but the validator only accepts the detected archetype's dirs. A custom-artifact bundle is checked as format-recovery, so keep it to `data/` only. A bundle with an archetype's exact artifacts must use that archetype's layout | P2, P4, P7, knowledge/archetypes.md, qc_authoring_checklist (lines 8, 11, 34) |
| repo-patch / service-interaction layout | ship `repo/` + `ci/` (or `service/` + `data/`) with the exact COPY lines; no repo.zip/service.zip inside data/ | P2, P4, P7, knowledge/archetypes.md (lines 10, 11) |
| §1.7 flat rule gone | subdirectories inside an input dir are allowed | P1 (line 33 "flat files"), P2 (line 56 "Keep the data flat"), qc_authoring_checklist (line 11) |
| DS-2 per directory | every input dir must be load-bearing on its own | P2, P5, P9 |
| TS-1 / D1 widened | no unconditional reads of `/app/repo`, `/app/ci` and so on in tests; embed them with `{{SHIPPED:<dir>}}` | P2, P5 (line 31), P7 |
| S4 / D1 drop `COPY .` | always one explicit COPY per input dir | P2, P7, qc_authoring_checklist (line 34) |
| `{{SHIPPED:<dir>}}` | after a data edit, re-embed every embedded input dir, not only data/ | _COMMON_RULES (rule 6), P4, P7, P9 |
| H5 back to 700 | generated test.sh has 700; the 4 live bundles have 755 and WARN H5. Ask PL which mode to ship (755 was chosen for the Harbor Linux host read; 700 is what HEAD QC wants) | P2, P7, _COMMON_RULES, qc_authoring_checklist (line 75 already says 700) |
| IN-15 / JD-15 stale key words | reviewers read `kind = "constraint"` and the `constraint`/`conduct` labels as `type = "instruction following"` and the classification; report the wording to PL | P5, P8, qc_authoring_checklist |
| playground sampled ablation | default is sampled; run `--ablation full` once before sign-off and state the mode; A3-judge-contract no longer exists | P3, P4, P6, P9 |
| validator `--semantic` | may now work without an API key (UNVERIFIED) | P6, knowledge/KNOWLEDGE.md (line 24 "--semantic is broken") |
| trailer token format | same seed no longer reproduces older bundles byte for byte | P4 |

## 7. Q21 #3 to #5 re-check (on bfe40804; GEN is identical to bde868c4 for these files)

| item | verdict | evidence |
|---|---|---|
| (3) blank words in instruction.md | still present | `generate_bundle.py:1856-1857` set `container_noun` and `producer_system` to "" outside format-recovery; `{{CONTAINER_NOUN}}`/`{{PRODUCER_SYSTEM}}` are used on line 1 of `templates/build-repair/instruction.md`, `domain-calculation/instruction.md`, `performance/instruction.md`, and `{{PRODUCER_SYSTEM}}` on line 1 of `data-pipeline/instruction.md` |
| (4) QC Step 10 oracle x5 vs QL interim <=3 | still present | `Final_checklist.md:273` "five oracle runs, one nop run, one stub run"; `:350` "The oracle runs five times" |
| (5) CATEGORIES.md 2 archetypes; `--category` help | still present | `CATEGORIES.md:34-35` "The current archetypes are `format-recovery` and `build-repair`" (8 exist); `generate_bundle.py:2516-2517` help says "Defaults to 'software-engineering'" but `:1784-1785` picks a random category when `--category` is absent |

## 8. Existing bundles (HEAD QC scripts + validator; logs in `/tmp/opencode-logs/p10-bde868c4-20261021T1735/`)

| bundle | structure / instruction / tests / judge QC | validator | FAIL detail | caused by this upstream change? |
|---|---|---|---|---|
| district-heat-flex-procurement | PASS / PASS / WARN (A3 41, H5) / PASS | PASS | none | H5 WARN yes (755) |
| emberforge-vault-settlement | PASS / PASS / WARN (A3 50, H5) / PASS | FAIL (3) | §1.12 artifacts match no archetype; §15.5 missing `fix_patch_sha256`; §15.7 same key | no: the same 3 FAILs occur on the 9b8229f6 validator; `--archetype domain-calculation` gives the same result |
| schema-migration-plan-repair | WARN (X1) / PASS / WARN (A3 50, H5) / PASS | FAIL (2) | §1.4 wants `environment/repo` + `environment/ci`, found `data`; §5.5 wants `COPY repo /app/repo`, `COPY ci /app/ci` | yes: artifacts now auto-detect repo-patch, whose layout changed |
| vendor-archive-roundtrip-recovery | WARN (X1) / PASS / WARN (A3 48, A5 x4, H5) / PASS | PASS | none | H5 WARN yes |

Baseline run with the 9b8229f6 tree (rebuilt by `git show` in scratch): all 4 bundles FAIL judge_qc J6/J7 there (they already use 4-key annotations) and validator §15.5 (`authored_by`/`status` missing). So the new rules fix those and break only schema-migration-plan-repair. Fixing schema-migration-plan-repair means moving `data/repo.zip` + context into `repo/` + `ci/` (or changing its artifact list so it is not detected as repo-patch); that is a builder job, not done here.

## 9. Not run or unverified

- Docker steps were not run: `validate_bundle.py --semantic`, the playground docker layer, harbor runs.
- Generator unit tests (`tests/*.py`) were not run.
- Whether 700 breaks Harbor's host-side reward read on Linux (the stated reason for 755) is UNVERIFIED.
- Old map `qc_checks.json` cites `QC assigned/` paths. Old wording here was taken from `git show 9b8229f6:Input_Bundle_QC/...`, not from that frozen copy.
