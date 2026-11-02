# Analyse: PL's Input Bundle Generator New (Harbor 0.24)

You are a read-only analyst. Map one generator completely: what it produces, how it makes tasks hard, and every rule its validator enforces. Another agent will write task-building prompts from your report without reopening the source. You build no deliverable task and fix nothing.

## Paths (absolute)
- SOURCE (read only, PL-owned, pushed `main`): `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input Bundle Generator New/`
- REPORT OUT: `/Users/mac/Desktop/Terminal Bench/_tmp_master_tasks_20261020T2214/reports/pl_generator/`
- SCRATCH (only place you may execute code or write bundles): `/tmp/plgen-analysis-<YYYYMMDDTHHMM>/`
- LOGS: `/tmp/opencode-logs/plgen-analysis-<YYYYMMDDTHHMM>/`

## Background
Harbor moved from 0.23.0 to 0.24. This generator, owned by Ayush's PL, scaffolds 0.24 input bundles and is updated without notice. Ayush authors tasks on top of its scaffold and they must pass the Input Bundle QC (`../Input_Bundle_QC/`, analysed separately). Known weak spots of the generators so far: generated data files too small, and too few file formats accepted. Verify whether that is still true here.

Size: ~226 files, 12 MB. Key files: `generate_bundle.py` (2618 lines), `validate_bundle.py` (1702), `playground.py` (470), `task_memory.py` (275), docs `README.md`, `FORMAT_SPEC.md` (775), `ARCHITECTURE_MAP.md` (754), `GENERATOR_TRAP_RECIPE.md` (311), `CHEAT_VECTORS.md`, `AUDIT_NOTES.md`, `ARCHETYPE_SELECTION.md`, `CATEGORIES.md`; `templates/` has 8 archetypes (build-repair, cli-config, data-pipeline, domain-calculation, format-recovery, performance, repo-patch, service-interaction), each with `archetype.toml`, `datagen.py`, `instruction.md`, `task.toml`, `environment/`, `solution/`, `tests/`; `reference/frontier-bench/`; `tests/`. Note that `CATEGORIES.md` mentions only 2 archetypes while `templates/` has 8. Resolve which is true from the code.
Ignored by Ayush on purpose: the test and rubric count caps (more tests scored better). Report the caps, but do not treat them as design constraints.

## Hard rules
1. Never modify, create or delete anything inside `Terminal_2.0_Harbor_Harness/`. No git commands except read-only ones (`git log`, `git show`, `git diff`, `git status`). Never commit, push, pull or checkout.
2. All generation and execution happens in SCRATCH. Pass `--output`/output-dir flags pointing into SCRATCH; if a command would write next to SOURCE, `cp -R` SOURCE into SCRATCH and run the copy instead.
3. Read, do not grep-and-conclude. Read every doc in full and every Python file at function level, including the full rule list in `validate_bundle.py`. If a read says truncated, read the rest.
4. Every claim cites `path:line` or a command and its output. Anything not confirmed is UNVERIFIED. Flag every doc-versus-code disagreement.
5. Any command that may take more than about 4 minutes runs as `nohup ... > LOGS/<name>.log 2>&1 &`, polled with waits under 4 minutes. Do not end your turn while your own job runs. Docker builds count as long.
6. Subagents only for parallel reading of separate parts (for example, one per group of archetypes). Verify their claims yourself.
7. Write each section to disk as soon as it is done.

## What to find out (all of it)
A. CLI: every flag of `generate_bundle.py`, `validate_bundle.py`, `playground.py`, `task_memory.py`, with defaults and effect. Seeds and determinism.
B. Archetypes: for each of the 8, what kind of task it makes, what the agent is asked to do, the files it emits (names, formats, counts, byte sizes), what `datagen.py` generates and how much, what the solution does, what the tests check, and how reward is computed. Put a comparison table at the top.
C. Categories: the 16 categories, what they change per archetype (magic, narrative, tags, keywords), and how they combine with archetypes.
D. Bundle anatomy for 0.24: exact tree, `task.toml` keys and allowed values, `instruction.md` shape, `environment/Dockerfile` requirements (runtime pins, uid 1000 agent account, openhands-sdk), `tests/` (test.sh, test_*.py, `reward.toml`, `judge.toml`), `solution/` (solve.sh, solve.py, TRUTH.md), and the reward arithmetic from tests plus judge into the final score.
E. Hardness: every mechanism the generator and docs use (GENERATOR_TRAP_RECIPE, CHEAT_VECTORS, AUDIT_NOTES, hidden rules, tiers or labelled/unlabelled corpora, stubs, wrong implementations, partial credit). For each: how it works, where it is, whether it is generated automatically or left to the author, and its known weaknesses (for example, rules a corpus lets the agent derive).
F. Validator: every rule in `validate_bundle.py` as a list: id or name, what it checks, FAIL or WARN, strict-only or not, `path:line`.
G. Author surface: what the author must add or replace on top of the scaffold, what must stay exactly as generated (names, magic, version, extension, Dockerfile pins), and what breaks validation if changed.
H. Data volume and formats: measure them. In SCRATCH, generate at least one bundle per archetype (fixed seeds, varied categories), then record per bundle the file count, total bytes, largest file, formats/extensions present and line counts of data files. Run `validate_bundle.py` (strict, if available) on each and record the result. If Docker is available and time allows, run the oracle and nop through `tests/test.sh` for one bundle in the background; otherwise say "did not run".
I. Memory and playground: what `task_memory.py`, `playground.py` and `memory/` record and how they are meant to be used.
J. Change tracking: `git log` for this folder (last 15 commits, with what changed). Note anything that suggests direction (for example, "keep build-repair inputs above 20k lines").
K. Gaps and risks for authoring hard tasks: what the scaffold makes easy to leak, what it cannot express, and where file-format or data-size limits remain.

## Deliverables (in REPORT OUT)
1. `REPORT.md`: sections A to K, plus `## Doc vs code disagreements` and `## Not checked`.
2. `archetypes.json`: `[{"archetype":"","purpose":"","agent_task":"","emitted_files":[{"path":"","format":"","bytes":0,"lines":0}],"datagen":"","tests_summary":"","reward":"","hardness_hooks":[],"author_must_edit":[],"must_not_change":[],"validate_result":""}]`
3. `validator_rules.json`: `[{"id":"","checks":"","severity":"FAIL|WARN","strict_only":false,"source":"path:line"}]`
4. `bundle_schema.json`: the 0.24 tree, `task.toml` keys and allowed values, and the reward and judge file shapes.
5. `hardness.json`: `[{"id":"P-001","name":"","how":"","where":"path:line","automatic":true,"weakness":""}]`
6. `fingerprint.json`: `{"source":"<abs path>","git_head":"","generated_ist":"","files":{"<relpath>":"<sha256>"}}` for every file in SOURCE.
7. `RUN_LOG.md`: every command you ran, with seeds and exit codes.

## Done when
All seven files exist and the JSON parses (`python3 -m json.tool`), every archetype has a measured row, the validator list matches the code one to one, SOURCE is unchanged (re-hash against `fingerprint.json` and run `git status` on the clone), and SCRATCH is deleted. Finish with a reply of at most 10 lines: paths, archetype count, validator rule counts (FAIL/WARN), measured data-size range and the formats seen.
