# TRUTH.md - batch-lease-scheduler-replay

## Defect

The source archive at `/app/data/project.zip` holds a stdlib-only Python project that
does not build, does not install, and does not import. Every layer is broken at once:
the packaging metadata points at directories that do not exist, one module will not even
tokenise, a third-party dependency is imported where a standard-library module belongs,
two modules import each other in a cycle, the package initializer is missing outright,
and the scoring arithmetic is inverted so that a project which *did* import would still
return the wrong answer for every manifest. The agent must extract the archive to
`/app/project`, discover all of these independently, repair them at the source level, and
re-deliver the result as an installable archive at `/app/out/package.zip` plus
7 graded report artifacts. The package name, the shipped data, and
the hidden evaluation manifests are all specific to this task instance, so
nothing below can be recalled from training.

The sidecars are large and each one feeds a graded value: `dependency_manifest.json`
fixes the seeded package version (`__version__`, `pyproject.toml`, every report),
`compiler_flags.json` fixes the archive's compression and member timestamp,
`expected_targets.json` lists the archive members, `scoring_fixtures.jsonl` holds 5,500
entries the repaired `score_entry` must reproduce (`fixtures_total`/`fixtures_passed`),
`ci_config.yaml` lists the CI commands `selftest.json` echoes, `module_map.json` names the
mapped package modules for `summary.json`, and the roughly 18,000-line `build.log` carries
the exception types `build_report.json` must list in `log_errors`. Deleting any one of
them makes part of the deliverable impossible to produce exactly.

1. (focal) `pyproject.toml` is wrong in four independent ways and every one of them
   blocks installation. `package-dir` points at a `python/` directory that does not exist
   (the sources are under `src/`); `packages` names `task_core`, a package
   that was never written; `requires-python` demands `>=3.13` while the shipped runtime
   and the grader are Python 3.12, so a compliant installer refuses the wheel outright;
   and `version` reads `0.0.3` while `dependency_manifest.json` and the shipped smoke test
   both require the seeded `required_version`. Fixing three of the four still fails
   `pyproject_metadata_is_python312_stdlib_only` and
   `archive_installs_offline_and_imports`.
2. (focal) There is no `__init__.py` in the package directory at all. The sources ship
   `core.py`, `metrics.py`, and `reports.py` and nothing that binds them, so `import
   task` finds a namespace package with no `__version__` and none of the six
   names the README publishes. The initializer has to be written from scratch, re-exporting
   `load_manifest`, `score_entry`, `score_batch`, `summarize`, and `render_report` and
   declaring `__version__` as the manifest's `required_version`. This is what
   `archive_installs_offline_and_imports` and `shipped_tests_are_preserved`
   measure together.
3. (focal) The scoring arithmetic in `core.py` is inverted. The line reads
   `score = min(100, max(0, 100 + penalty))` where the penalty must be *subtracted*:
   `max(0, min(100, 100 - penalty))`. As written, every entry clamps to 100 and every
   bucket comes back `ok`, which looks plausible on a happy-path manifest and is wrong on
   all of them. The shipped smoke test pins the correct behaviour - an entry with
   `expected=100, observed=130, seconds=40, critical=true` must land in the `critical`
   bucket, not `ok`. `public_api_scores_hidden_seeded_manifests` and
   `edge_cases_and_report_are_correct` both key off this.
4. (focal) `metrics.py` does not tokenise. The `return "ok"` branch is indented with a
   literal tab inside an otherwise space-indented block, which raises `TabError` before
   any import can proceed, and the last line `BUCKET_ORDER = ["ok", "watch", "repair",
   "critical"` is missing its closing bracket, which raises `SyntaxError` on its own. Two
   separate lexical faults in a nine-line file; repairing one and re-running still fails.
5. (drift) `core.py` and `reports.py` import each other. `core.py` pulls `DEFAULT_LABEL`
   from `.reports`, and `reports.py` pulls `summarize` from `.core`. The experienced
   instinct is to break the cycle with a deferred import inside the function body, which
   makes the traceback go away and leaves the design defect in place. The correct repair
   is to move `DEFAULT_LABEL` down into `core.py` where its only consumer lives, so
   `reports.py` depends on `core.py` and nothing depends back. A lazy-import patch will
   import cleanly and still read as an unrepaired root cause to the Channel B judge under
   rubric R2 and R4.
6. (trap) `core.py` does `import tomli`. That package is not installed, is not the
   standard library, and cannot be installed - anything pip-installed during the working
   session is absent at grading time. The answer is `tomllib`, which has been in the
   standard library since 3.11 and has a compatible `load()`. An agent that "fixes" this
   by adding `tomli` to the `dependencies` array of `pyproject.toml` passes locally if it
   happened to be cached and fails `load_manifest_uses_stdlib_tomllib` and
   `dependency_resolution_json_matches_reference` at grading time.
7. (trap) Two boundary conditions in `score_entry` are off by one step and neither is
   visible in the shipped smoke test. `misses` is computed with `math.floor` where the
   reference uses `math.ceil`, and the slow-entry penalty triggers on `seconds >= 30`
   where the reference uses `seconds > 30`. Both agree on every entry in
   `tests/test_smoke.py`; the hidden seeded manifests plant an entry at exactly 30 seconds
   and an entry whose deviation is a fraction of one tolerance step precisely to separate
   a repair that reasoned about the boundaries from one that pattern-matched the visible
   test. `edge_cases_and_report_are_correct` is the check that fires.

The reference is authored in Python (Python 3.12, standard library only, a
340-line repair driver) with a Bash oracle dispatcher (`solve.sh`)
that extracts the archive, rewrites the metadata and the four modules, rebuilds
`package.zip` with `zipfile`, and emits the report artifacts. A deterministic channel
observes the delivered archive and artifacts (Channel A, `tests/test_output.py`, weighted by its
`criteria.<name>(weight=W)` registrations); a judged rubric channel grades the repair trajectory
(Channel B, `tests/judge.toml`). Counts and weights are not mirrored into the prose above
 -  read them from those files, or from the lists below, which mirror them.

Out of bounds: installing anything with pip, since the grading container has no network
and no site-packages beyond the standard library
(`source_avoids_network_and_runtime_patch_imports`); deleting, emptying, or
`skip`-decorating the shipped tests under `tests/` to make the suite green
(`negative_deleted_or_neutered_shipped_tests`); writing the report artifacts
by hand with claims that no build supports
(`negative_fake_artifact_without_real_fix`); embedding the smoke test's own
expected values as literals so the API returns them without computing them
(`negative_hardcoded_sample_answers`); monkeypatching import machinery,
`sys.modules`, or `builtins` at runtime to paper over an unrepaired module
(`negative_nondeterministic_or_monkeypatched_solution`); and looking the
project up online - it is specific to this instance and exists nowhere else.

## Load-bearing work

7 artifacts are collected, and every one of them is graded:

- `/app/out/package.zip`
- `/app/out/selftest.json`
- `/app/out/build_report.json`
- `/app/out/module_core.json`
- `/app/out/module_metrics.json`
- `/app/out/dependency_resolution.json`
- `/app/out/summary.json`

- `/app/out/package.zip` (new) - the repaired project as an installable archive. Must
  contain `pyproject.toml`, a `src/task/` source tree with a real
  `__init__.py`, and the `tests/` directory preserved intact. It has to install offline
  into a clean Python 3.12 and expose the six public names on import.
- `/app/out/selftest.json` (new) - the package name, the version, and whether the
  repaired package imports and self-tests cleanly. The truthfulness of this file is
  itself graded by `selftest_json_is_truthful`; a `true` written next to a suite that
  did not run is worse than a `false`.
- `/app/out/build_report.json` (new) - the corrected layout, the version, and the
  categories of fixes applied. The categories must correspond to repairs that actually
  landed in the archive.
- `/app/out/module_core.json` (new) - the specific repairs made to `core.py` together
  with the public API the module now exposes.
- `/app/out/module_metrics.json` (new) - the specific repairs made to `metrics.py`
  together with the bucket boundaries it computes. The boundaries are `ok` at 90 and
  above, `watch` at 70, `repair` at 40, `critical` below that, in that declared order.
- `/app/out/dependency_resolution.json` (new) - the statement, and the evidence for it,
  that the package resolves against the standard library alone on Python 3.12.
- `/app/out/summary.json` (new) - the overall roll-up, which must agree with the artifact
  set actually written.

Every rule those artifacts must satisfy lives in `tests/test_output.py` and is mirrored by
the reference `solution/solve.py`. This section names the deliverables so a reader knows
the shape of the work, not the text to type.

Out of bounds by design: shipping a `package.zip` whose contents differ from the tree the
agent actually repaired and tested; dropping the shipped tests from the archive to avoid
having to make them pass; declaring fixes in the JSON reports that the source does not
contain; and any artifact whose bytes change between two consecutive runs.

## Verification

Grader entrypoint: `tests/test.sh`. It hardens the verifier (clears stale reward files,
locks `/logs/verifier` to root, restricts `/tests`) and then runs
`exec rewardkit /tests --workspace /app --output /logs/verifier/reward.json`. rewardkit
scores Channel A from the `@criterion` checks in `tests/test_output.py`, each weighted by
its `criteria.<name>(weight=W)` registration, and Channel B from the criteria in
`tests/judge.toml`, which the judge reads against `/logs/agent/trajectory.json`.
`tests/reward.toml` divides each channel's weighted sum by that channel's positive total
and gives each half of `reward`, so the combined reward runs from -1.000 to +1.000.
The oracle and nop calibration runs score Channel A alone, on the tests-only copy that
`Input_Bundle_QC/exe_copy.py` builds; Channel B has no oracle score.

Channel A declares 15 positive and 4 negative tests, positive weight total
51 and negative weight total -16, so the
theoretical reward range is -16/51 = -0.314 to +1.000.

Positive tests (15):

- `artifacts_exist` (weight 1)
- `archive_has_expected_project_layout` (weight 3)
- `pyproject_metadata_is_python312_stdlib_only` (weight 5)
- `archive_installs_offline_and_imports` (weight 5)
- `public_api_calls_complete_within_five_seconds` (weight 3)
- `public_api_scores_hidden_seeded_manifests` (weight 5)
- `load_manifest_uses_stdlib_tomllib` (weight 3)
- `edge_cases_and_report_are_correct` (weight 5)
- `selftest_json_is_truthful` (weight 3)
- `build_report_json_matches_reference` (weight 3)
- `module_reports_match_reference` (weight 3)
- `dependency_resolution_json_matches_reference` (weight 3)
- `summary_json_matches_declared_artifacts` (weight 3)
- `shipped_tests_are_preserved` (weight 3)
- `source_avoids_network_and_runtime_patch_imports` (weight 3)

Negative tests (4) are polarity-inverted: their assertions hold
only when the cheat is present, so an honest run leaves them "failing" and contributes
zero weight. They subtract only from a solver that actually cheats.

- `negative_hardcoded_sample_answers` (weight -5)
- `negative_fake_artifact_without_real_fix` (weight -5)
- `negative_deleted_or_neutered_shipped_tests` (weight -3)
- `negative_nondeterministic_or_monkeypatched_solution` (weight -3)

Channel B is 13 criteria (11 positive / 2 negative), positive total 41:

- **R1** (+3, trajectory): The agent inspects project metadata, package sources, and shipped tests before changing the broken project.
- **R2** (+5, trajectory): The agent identifies independent root causes across packaging metadata, imports, version declarations, and scoring behaviour.
- **R3** (+3, trajectory): The agent bases dependency and toolchain decisions on the shipped Python 3.12 environment and local project files.
- **R4** (+5, trajectory): The agent traces import failures through the package graph and repairs their underlying source-level causes.
- **R5** (+3, trajectory): The agent uses observed failures as diagnostic evidence to isolate independent root causes before editing source files.
- **R6** (+5, trajectory): The agent assembles the requested archive by invoking deterministic Python standard-library packaging commands during the working session.
- **R7** (+5, trajectory): The agent runs local package imports and the shipped test suite after completing the repair and before packaging artifacts.
- **R8** (+3, trajectory): The agent records diagnostic evidence from final local checks before creating either output artifact.
- **R9** (-5, trajectory): The agent retrieves a task-specific repaired package, prior submission, or reference solution from an external source.
- **R10** (-5, trajectory): The agent reports successful builds, imports, or tests that lack supporting execution evidence in the trajectory.
- **R11** (+3, user_facing_message): The response summarizes the completed work and names where the produced artifacts were written.
- **R12** (+3, trajectory): The agent writes every produced artifact once, at the exact path and filename the instruction names.
- **R13** (+3, trajectory): The agent keeps the repaired build on the shipped Python 3.12 toolchain and adds only dependencies the instruction lists.

The evaluation manifests are reseeded on every run from `EVAL_SEED = 5338588010480986425`,
distinct from the visible `SAMPLE_SEED = 9046772049770565972` and the labelled
`CHALLENGE_SEED = 8534472571618152890`. The verifier imports the delivered
`package.zip` as an unprivileged user in a temporary directory, so the repair has to
survive being moved off the machine it was built on, and every import or API call it makes
must return within five seconds. The oracle expectation is that running `solution/solve.sh`
inside the container drives every positive Channel A test to pass and holds every negative
test in its failing state.

## Root cause

**Why the faults are layered.** The project is broken at five different levels - build
metadata, module lexing, dependency selection, module topology, and domain arithmetic  - 
and the layers mask each other. A `SyntaxError` in `metrics.py` hides the circular import
between `core.py` and `reports.py`; the circular import hides the missing `tomli`; the
missing `tomli` hides the inverted score. An agent that fixes the first traceback it sees
and re-runs will get a *different* traceback, five times in a row, and only reaches the
arithmetic defect - which produces no traceback at all - if it keeps going. This is the
whole design of the task, and it is why rubric R2 and R5 credit *isolating
independent root causes* rather than the number of edits made.

**Packaging metadata is executable, not documentation.** `package-dir`, `packages`, and
`requires-python` are consumed by the build backend and by the installer. A `src/` layout
with `package-dir = {"" = "python"}` produces a wheel containing nothing at all - the
build *succeeds*, and the resulting archive is empty. `requires-python = ">=3.13"` on a
3.12 interpreter is refused at install time, not at build time. These are two distinct
failure surfaces and they report at different moments, which is why
`pyproject_metadata_is_python312_stdlib_only` and
`archive_installs_offline_and_imports` are separately weighted.

**The circular import is a design defect, not a syntax one.** `DEFAULT_LABEL` is a
constant with exactly one consumer: `score_entry` in `core.py`. It was placed in
`reports.py`, which forces `core.py` to import upward into a module that already imports
down into it. Python will resolve some cycles by accident depending on which module is
imported first, which makes the bug intermittent and makes a deferred import look like a
fix. Moving the constant to its consumer removes the cycle instead of hiding it, and
leaves a dependency graph with a single direction: `reports` → `core` → `metrics`.

**The scoring contract.** `score_entry` computes `tolerance = max(1.0, |expected| * 0.05)`,
`misses = ceil(|observed - expected| / tolerance)`, then `penalty = misses * 7`, plus 10
when `seconds > 30`, plus 15 when the entry is flagged critical *and* has at least one
miss. The final score is `max(0, min(100, 100 - penalty))` and the bucket is drawn from
that score at the 90 / 70 / 40 boundaries. `summarize` averages the scores and rounds to
two places. Every one of those constants is pinned by the shipped smoke test or by the
hidden manifests; none of them may be adjusted to make a test pass.

**Determinism requirements.** `package.zip` is compared for stability, and the six JSON
reports are re-read after a second run. Archive member order, archive timestamps, dict
iteration order in the reports, and absolute temporary paths are the four things that
routinely differ between runs. Write the archive from a sorted file list and serialise the
reports with sorted keys.

**Red lines.** No pip installs and no third-party imports; no deletion, emptying, or
skipping of the shipped tests; no report claim without a run behind it; no monkeypatching
of import machinery or `sys.modules` to fake a working package; no hardcoded smoke-test
answers; no non-determinism between runs; no online lookup.

## Solution shape

1. Extract `/app/data/project.zip` into `/app/project` and read the whole tree before
   editing anything: `README.md` for the published API contract, `pyproject.toml` for the
   build metadata, the three modules, and `tests/test_smoke.py` for the behaviour that is
   pinned. Read the sidecars in `/app/data` - `build.log`, `dependency_manifest.json`,
   `expected_targets.json`, `module_map.json`, `compiler_flags.json`, `ci_config.yaml`,
   `scoring_fixtures.jsonl` - 
   as repair context; deciding which of them is authoritative for which decision is part
   of the task.
2. Rewrite `pyproject.toml` in one pass: keep the setuptools backend, set
   `name` to task, `version` to the manifest's `required_version`, `requires-python` to `>=3.12`,
   `dependencies` to the empty list, `package-dir` to `{"" = "src"}`, and replace the
   hand-written `packages` list with `[tool.setuptools.packages.find] where = ["src"]` so
   the layout is discovered rather than asserted.
3. Write `src/task/__init__.py` from scratch: import the five public callables
   from `.core` and `.reports`, set `__version__` to the same version, and declare `__all__` covering
   the version plus all five names.
4. Repair `metrics.py`: re-indent the tab-indented branch with spaces to match the rest of
   the file, close the `BUCKET_ORDER` list, and keep the bucket order and the 90 / 70 / 40
   boundaries exactly as the README describes.
5. Repair `core.py`: swap `import tomli` for `import tomllib`, move `DEFAULT_LABEL` in from
   `reports.py` and drop the upward import, switch `math.floor` to `math.ceil`, switch
   `seconds >= 30` to `seconds > 30`, and correct the clamp to
   `max(0, min(100, 100 - penalty))`.
6. Repair `reports.py`: it now imports only `summarize` from `.core`, and the label
   constant is gone from it.
7. Run the shipped smoke test against the repaired tree, then build `/app/out/package.zip`
   with `zipfile` from a sorted list of `pyproject.toml`, `README.md`, the `src/` tree, and
   the `tests/` tree, so the archive bytes are stable across runs.
8. Install the archive into a throwaway directory as an unprivileged user, import
   task from it, exercise the public API, and only then write the six JSON
   reports from what those runs actually observed, with sorted keys and a trailing newline.

## Ordered plan

1. Extract and read first, edit nothing. Inventory the README's published API, the smoke
   test's pinned assertions, and the six diagnostic sidecars. Rubric R1 credits exactly
   this: inspecting metadata, sources, and shipped tests *before* changing the project.
2. Build the fault list before the fix list. Run `python3 -m compileall src/` to surface
   the lexical faults, then `python3 -c "import task"` repeatedly, recording
   each distinct traceback. Expect at least five different failures in sequence. Rubric R2
   and R5 grade the identification of *independent* root causes and the use of observed
   failures as diagnostic evidence.
3. Fix the lexical layer first because nothing else can be observed until it is gone: the
   tab in `metrics.py` and the unclosed list. Re-run `compileall` and confirm it is clean.
4. Fix the topology and dependency layer: move `DEFAULT_LABEL` into `core.py`, remove the
   upward import, and replace `tomli` with `tomllib`. Do not paper over the cycle with a
   function-local import - rubric R4 asks for the underlying source-level cause, and
   R3 asks that the decision be grounded in the shipped Python 3.12 environment.
5. Fix the metadata layer: rewrite `pyproject.toml` completely rather than patching the
   four wrong keys individually. Verify by building a wheel into a temporary directory and
   listing its contents; an empty wheel means `package-dir` is still wrong.
6. Fix the arithmetic layer last, driven by the smoke test. Derive the expected score for
   the `critical` entry by hand - tolerance 5.0, six misses, penalty 42 plus 10 for the
   slow entry plus 15 for the critical flag, score 33 - and confirm the code reproduces
   it. Then reason about the two boundary cases the smoke test does not cover, at exactly
   30 seconds and at a sub-tolerance deviation. Rubric R7 credits running the shipped suite
   after the repair and before packaging.
7. Package with `zipfile` from a sorted file list, then install the archive into a clean
   temporary prefix as an unprivileged user and import it there. This is the step that
   catches a repair that only works in the build tree. Rubric R6 credits assembling the
   archive by invoking deterministic standard-library packaging during the session.
8. Write the six JSON reports from the evidence of those runs, with sorted keys, then run
   the whole pipeline a second time and diff `package.zip` and the reports byte for byte.
   Close with a summary naming where each artifact was written - rubric R8 credits
   recording diagnostic evidence before creating the artifacts, and R11 credits the
   closing summary.

## Pitfalls

- **Stopping after the first green import.** Five of the seven defects produce a
  traceback and the sixth does not. An agent that iterates until `import
  task` succeeds ships an inverted score function and fails
  `public_api_scores_hidden_seeded_manifests` and
  `edge_cases_and_report_are_correct` with a clean-looking package.
- **Breaking the import cycle with a deferred import.** Moving `from .core import
  summarize` inside `render_report` makes the traceback disappear and leaves the cycle in
  the dependency graph. Rubric R2 and R4 grade the root cause, not the symptom.
- **Adding `tomli` to the dependency list instead of switching to `tomllib`.** The
  grading container has no network and no site-packages. A dependency declaration is not
  a repair; `load_manifest_uses_stdlib_tomllib` reads the source.
- **Patching `pyproject.toml` key by key.** There are four wrong keys and they fail at
  two different moments - `package-dir` and `packages` produce an empty wheel at build
  time, `requires-python` is refused at install time. Fixing the loud ones and leaving
  `requires-python` at `>=3.13` still fails `archive_installs_offline_and_imports`.
- **Assuming the missing `__init__.py` is optional.** Python will treat the directory as
  a namespace package and `import task` will appear to succeed, right up
  until `task.__version__` raises `AttributeError` inside the shipped smoke
  test.
- **Fixing only one of the two faults in `metrics.py`.** The tab and the unclosed list are
  independent; the tokeniser reports whichever it reaches first, so repairing one and
  re-running yields a second `SyntaxError` that looks like the fix did not take.
- **Copying the visible smoke test's boundaries.** `math.floor` versus `math.ceil` and
  `seconds >= 30` versus `> 30` agree on every entry in `tests/test_smoke.py`. The hidden
  manifests are seeded to separate them, which is what
  `edge_cases_and_report_are_correct` exists to catch.
- **Deleting or skipping the shipped tests.** They are part of the deliverable archive and
  `shipped_tests_are_preserved` reads them out of `package.zip`;
  `negative_deleted_or_neutered_shipped_tests` fires on top of that.
- **Writing the reports before running anything.** `selftest_json_is_truthful`,
  `build_report_json_matches_reference`, and
  `negative_fake_artifact_without_real_fix` all compare declared claims
  against the delivered source. A report that says the suite passed when it was never run
  is a scored lie, not an optimistic guess.
- **Hardcoding the smoke test's expected values.** Returning `33` for the critical entry
  without computing it fires
  `negative_hardcoded_sample_answers`, and the hidden manifests make the
  shortcut worthless anyway - they are reseeded from a value the agent never sees.
- **Monkeypatching import machinery.** Injecting a fake module into `sys.modules`, or
  rebinding `builtins.__import__` so the unrepaired package appears to work, fires
  `negative_nondeterministic_or_monkeypatched_solution` and does nothing at
  all when the verifier imports the archive in a fresh process.
- **A non-deterministic archive.** `zipfile` records a modification time per member and
  `Path.rglob` does not guarantee an order. Two builds of an identical tree can differ
  byte for byte unless the file list is sorted, which shows up on the second run rather
  than the first.
- **Building and testing only in `/app/project`.** The verifier installs the delivered
  archive elsewhere, as an unprivileged user. A repair that depends on the build tree's
  `sys.path`, on a stale `.egg-info`, or on files that were never added to the archive
  fails `test_package_imports_offline_as_unprivileged_user` territory checks inside
  `archive_installs_offline_and_imports`.

## Provenance

```yaml
uuid: null  # task.toml carries no canary_guid or uuid field
instance_id: batch-lease-scheduler-replay
task_name: terminal-bench/batch-lease-scheduler-replay
fix_patch_sha256: b2a76e764f0dcdd046cae116a78df8b6efca3abaae52632c2184c0d551ddc19f  # sha256 of solution/solve.sh
solve_py_sha256: 6fe2bceb21e737ada26e17d4e6bd6ac2325aeba35248856fefc39e02a3683435  # informational; solve.py is 340 lines
language: python
golden_score_measured: null  # not measured for this instance
golden_score_channel_a_pct: null
golden_score_channel_b_pct: null
golden_score_runs: 0
golden_score_trial_id: null  # no calibration trial has been run yet
golden_score_verified_by: >
  Not yet measured. The expected figures are exactly 1.000 on each of five
  oracle runs and exactly 0.000 on a no-op run, on the test channel in
  tests/test_output.py only; the judged channel has no oracle score.
caveat: >
  The test channel carries 15 positive checks worth 51 weight and 4 negative
  checks worth -16 weight, so on its own it ranges -16/51 = -0.314 to
  +1.000. The judged channel carries 13 criteria worth 41 positive points.
  tests/reward.toml divides each channel's weighted sum by its positive
  total and gives each half of the reward, so the combined reward runs from
  -1.000 to +1.000 with no clamp.
```
