# TRUTH.md - cold-chain-backbone-quote

## Defect

`/app/repo` holds a small stdlib-only event-ledger repository that is broken at
five independent layers at once: its packaging metadata points at a directory that does
not exist, its package initializer is missing from the archive entirely, its accumulator
overwrites instead of accumulating, its parser understands exactly one of the four input
shapes it is contracted to accept, and its report module closes an import cycle while
summing the wrong thing. None of the five can be diagnosed from the traceback of any
other, because the first one prevents the package from importing at all. The task is to
repair the repository - not to reimplement it beside the broken copy - and to deliver it
back as `/app/out/patched-repo.zip` with the `src/` layout intact, plus six sidecar
reports that have to be truthful about what was actually checked. The hidden ledgers the
grader runs against the delivered archive are specific to this task instance, so
nothing below can be recalled from training.

The context files are large and each one is read by a complete repair: about 2,400
regression cases, a 25,000-line pre-repair CI log, a lint report of several hundred
issues, and seeded `package_manifest.json` and `build_config.json` values (the package
version, the archive timestamp, compression and member mode). Deleting any of them makes
part of the deliverable impossible to produce exactly.

0. (focal) The sidecars are inputs, not decoration. `VERSION`, `build_report()["version"]`
   and the `pyproject.toml` version must equal the manifest's seeded `version`; the
   archive must use `build_config.json`'s `timestamp`, `compression` and `mode`; each
   module note's `lint_errors` counts that module's `error`-severity issues in
   `lint_report.json`; and `test_fixes.json`'s `previously_failing` lists every case
   whose test the log reports as `FAIL` or `ERROR`.

1. (focal) `pyproject.toml` is wrong in four independent ways and each one is separately
   graded. `version = "0.0.0"` contradicts the seeded `version` in
   `/app/ci/package_manifest.json` that `/app/ci/api_contract.md` requires; `requires-python = ">=3.13"` excludes the
   3.12 runtime the container actually ships; `dependencies = ["requests"]` declares a
   third-party package in a repository the contract calls stdlib-only; and
   `package-dir = {"" = "lib"}` points setuptools at a `lib/` tree that does not exist
   anywhere in the archive, while the sources live under `src/`.
   `metadata_is_python312_and_stdlib_only` reads the delivered `pyproject.toml` and
   asserts the name, the absence of `3.13`, and an empty dependency list.
2. (focal) `src/task/__init__.py` is **absent from the archive**. This is the
   defect behind `ModuleNotFoundError: No module named 'task'` in
   `/app/ci/failing_tests.log`, and it is easy to misread as a `PYTHONPATH` problem
   because setting `PYTHONPATH=src` does not fix it. The initializer has to be created and
   it has to re-export the full public API named in the manifest - `VERSION`,
   `build_report`, `load_events`, `tally_events` - because
   `package_imports_offline_as_unprivileged_user` imports the package in a child
   process and reads `task.VERSION` and `task.build_report` off the
   top-level module, and `archive_has_expected_source_layout` asserts the file exists.
3. (focal) `core.tally_events` does `totals[account] = row.get("count", 0)`. Two bugs are
   fused into one line. The assignment overwrites, so three rows for `alpha` yield the last
   one instead of their sum; and it reads only `count`, while every visible row and every
   hidden row carries `delta`, so the common path silently yields zeros. The contract wants
   *signed* accumulation - negative deltas subtract - keyed by account, with `delta` and
   `count` treated as aliases for the same field.
   `hidden_json_ledgers_are_accumulated_correctly` runs unseen ledgers with repeated
   accounts and negative deltas through the delivered archive.
4. (focal) `parser.parse_events` is `return json.loads(text)["rows"]` and nothing else. It
   raises `TypeError` on a bare JSON list, `KeyError` on any object without a `rows` key,
   and `json.JSONDecodeError` on the CSV ledgers the README and the API contract both say
   the hidden verifier uses. It also performs no normalization at all, so the `count`/`delta`
   alias, whitespace in account names, string deltas from CSV, and the optional `note`
   column are all left for the accumulator to trip over.
   `hidden_csv_ledgers_are_supported` writes a real CSV with `account`, `delta`, and
   `note` columns and pushes it through `build_report`.
5. (focal) `report.render_report` closes the import cycle and miscomputes the total.
   `core.py` does `from .report import render_report` at module scope while `report.py` does
   `from .core import VERSION` at module scope - the `ImportError: circular import` in the
   failure log. And `sum(totals)` sums the *keys* of the dict, which are account-name
   strings, so it raises `TypeError` the moment the cycle is broken. Neither does it sort:
   `/app/ci/lint_report.json` flags report ordering as nondeterministic under changing
   insertion order, and `report_output_is_sorted_and_deterministic` asserts
   `["alpha", "zeta"]` from rows supplied in the opposite order.
6. (drift) The obvious way to break the `core` ↔ `report` cycle is a deferred import  - 
   move `from .core import VERSION` inside the function body, or reach for
   `importlib.import_module`. Both work at runtime and both are wrong here.
   `source_avoids_network_and_runtime_patch_imports` scans every `.py` file under
   `src/` for the bare substrings `requests`, `urllib`, `socket`, `subprocess`, `importlib`,
   `sitecustomize`, and `sys.meta_path`, and a function-local import leaves the cycle in
   place for anyone who imports `report` first. The correct repair is directional: make
   `report.py` depend on nothing from `core.py`, so the edge disappears rather than being
   deferred. The same substring scan means no packaging helper, no `importlib.metadata`
   version lookup, and no `subprocess` call may survive into the shipped `src/` tree - even
   though the driving script that *builds* the archive is free to use all of them.
7. (trap) `visible_tests_are_preserved` asserts `"pass" not in text.lower()` over the
   whole of `tests/test_visible.py`. That is a substring check, not a token check, so a
   stubbed `pass` body fails it - and so does the word `passed`, the word `bypass`, and a
   comment mentioning a passing test. The shipped visible tests already satisfy this; the
   trap only fires on an agent that "tidies" them, stubs one out, or annotates them.
8. (trap) `/app/ci/build_config.json` pins the archive format exactly: `stored`
   compression, member timestamp, compression and mode from `build_config.json`, sorted members.
   `zipfile` defaults to the current wall-clock time and `Path.rglob` gives no ordering
   guarantee, so an archive built the naive way differs between two runs of an identical
   tree. `archive_is_safe_and_deterministic` asserts `names == sorted(names)`, checks
   every member's `date_time`, and rejects any `..` component.

The reference is authored in Python (Python 3.12, standard library only, a
182-line repair-and-package driver) with a Bash oracle dispatcher
(`solve.sh`) that copies `/app/repo` into a scratch tree, rewrites the metadata and
the four modules, proves the repair by importing the package in a child process and
replaying the sidecar regression cases, and only then builds the deterministic archive. A
deterministic channel observes the delivered archive and the six reports (Channel A,
`tests/test_output.py`, weighted by its
`criteria.<name>(weight=W)` registrations); a judged rubric
channel grades the diagnose-and-repair trajectory (Channel B, `tests/judge.toml`). Counts
and weights are not mirrored into the prose above - read them from those files, or from the
lists below, which are generated from them.

Out of bounds: embedding the hidden expected totals or the evaluation seed as constants in
any shipped `.py` file (`negative_hardcoded_sample_answers`); writing a repair
report that claims successful checks while the package source is missing from the archive
(`negative_fake_report_without_real_patch`); deleting the visible tests or
gutting their assertions (`negative_deleted_visible_tests`); shipping a network
client or an import-machinery hook inside `src/`
(`negative_network_or_monkeypatch_cheat`); installing third-party packages; and
looking the repository up online - it is generated for this instance and exists nowhere
else.

## Load-bearing work

7 artifacts are collected, and every one of them is graded:

- `/app/out/patched-repo.zip`
- `/app/out/repair-report.json`
- `/app/out/module_core.json`
- `/app/out/module_parser.json`
- `/app/out/module_report.json`
- `/app/out/test_fixes.json`
- `/app/out/summary.json`

- `/app/out/patched-repo.zip` (new) - the repaired repository, keeping the `src/` layout,
  with `src/task/__init__.py`, `src/task/core.py`, and
  `tests/test_visible.py` all present. Built from a sorted file list with fixed
  the `build_config.json` member timestamps, mode bits and compression, and sorted
  compression, so two builds of the same tree are byte-identical.
- `/app/out/repair-report.json` (new) - names the package, carries a `checks` list with at
  least one genuinely passing entry, and a `fixes` list whose text mentions the metadata,
  the parser, and the tally repairs by name. The claims are cross-read against the archive.
- `/app/out/module_core.json`, `module_parser.json`, `module_report.json` (new) - one
  per-module record each, naming what was wrong and what was verified: the cycle removal
  and signed accumulation for core, the JSON-object / JSON-list / CSV / alias normalization
  for parser, the sorted keys and value-summed total for report.
- `/app/out/test_fixes.json` (new) - regression evidence. `visible_tests_preserved` is
  `true`, `all_regressions_passed` is `true`, and `regression_cases` replays every case from
  `/app/ci/regression_cases.jsonl` **in file order**, each entry carrying the case's
  `expected`, the `actual` the repaired package produced, and `passed`. The grader zips this
  list against the sidecar with `strict=True`, so a reordered or truncated list fails
  outright.
- `/app/out/summary.json` (new) - the roll-up naming the package, the seven input files
  consumed, the ordered artifact list, the artifact count, and the stdlib-only flag.

Every rule those artifacts must satisfy lives in `tests/test_output.py` and is mirrored by
the reference `solution/solve.py`. This section names the deliverables so a reader knows the
shape of the work, not the text to type.

Out of bounds by design: a rewritten-from-scratch package that discards the shipped layout;
an archive whose members carry live timestamps or arbitrary order; regression results
asserted rather than executed; a `src/` tree containing any of the banned substrings; and
any artifact whose bytes change between two runs.

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

Channel A declares 16 positive and 4 negative tests, positive weight total
54 and negative weight total -16, so the
theoretical reward range is -16/54 = -0.296 to +1.000.

Positive tests (16):

- `artifacts_exist` (weight 1)
- `archive_is_safe_and_deterministic` (weight 3)
- `archive_has_expected_source_layout` (weight 3)
- `metadata_is_python312_and_stdlib_only` (weight 5)
- `package_imports_offline_as_unprivileged_user` (weight 5)
- `hidden_json_ledgers_are_accumulated_correctly` (weight 5)
- `hidden_csv_ledgers_are_supported` (weight 5)
- `report_output_is_sorted_and_deterministic` (weight 3)
- `visible_tests_are_preserved` (weight 3)
- `repair_report_is_truthful` (weight 3)
- `core_module_artifact_matches_reference` (weight 3)
- `parser_module_artifact_matches_reference` (weight 3)
- `report_module_artifact_matches_reference` (weight 3)
- `test_fixes_artifact_covers_sidecar_regressions` (weight 3)
- `summary_artifact_matches_manifest` (weight 3)
- `source_avoids_network_and_runtime_patch_imports` (weight 3)

Negative tests (4) are polarity-inverted: their assertions hold only
when the cheat is present, so an honest run leaves them "failing" and contributes zero
weight. They subtract only from a solver that actually cheats.

- `negative_hardcoded_sample_answers` (weight -5)
- `negative_fake_report_without_real_patch` (weight -5)
- `negative_deleted_visible_tests` (weight -3)
- `negative_network_or_monkeypatch_cheat` (weight -3)

Channel B is 11 criteria (9 positive / 2 negative), positive total 33:

- **R1** (+3, trajectory): The agent inspects the zipped repository structure, metadata, source modules, and visible tests before editing.
- **R2** (+5, trajectory): The agent identifies root causes in package discovery, exports, parsing, circular imports, and accumulation semantics rather than only patching symptoms.
- **R3** (+3, trajectory): The agent keeps the repaired project stdlib-only and compatible with the shipped Python 3.12 runtime.
- **R4** (+3, trajectory): The agent uses local test failures and targeted import checks as diagnostic evidence while preserving meaningful visible coverage.
- **R5** (+5, trajectory): The agent assembles the requested patched archive by invoking deterministic Python standard-library packaging commands during the working session.
- **R6** (+3, trajectory): The agent records a repair report whose check and fix claims are supported by actions visible in the trajectory.
- **R7** (+5, trajectory): The agent validates behavior on more than the visible happy path, including repeated accounts, negative deltas, and CSV or equivalent alternate input handling.
- **R8** (-5, trajectory): The agent retrieves a task-specific patched repository, prior submission, hidden answer, or reference solution from outside the local bundle.
- **R9** (-5, trajectory): The agent deletes tests, fabricates reports, or monkeypatches import/runtime machinery while leaving repository defects in place.
- **R10** (+3, user_facing_message): The response summarizes the completed work and names where the produced artifacts were written.
- **R11** (+3, trajectory): The agent writes the patched repository archive once, at the exact path and filename the instruction names.

The hidden ledgers are reseeded from `EVAL_SEED = 4608925405049192081`, distinct from the visible
`SAMPLE_SEED = 54438424367678111` and the labelled `CHALLENGE_SEED = 929222594054820803`; the
CSV case is generated from `EVAL_SEED ^ CHALLENGE_SEED`, so passing the JSON case tells you
nothing about the CSV case. Every hidden test extracts the delivered `patched-repo.zip`
into a temporary directory and imports the package there in a **child process** - the
repair has to survive being moved off the machine it was built on, with no state left over
from the build. The oracle expectation is that running `solution/solve.sh` inside the
container drives every positive Channel A test to pass and holds every negative test in its
failing state.

## Root cause

**Five layers, one traceback.** The failure log shows four distinct errors, but they are
serialised: nothing runs until `__init__.py` exists, the cycle does not surface until the
import succeeds, `sum(totals)` does not raise until the cycle is broken, and the
accumulation bug produces wrong answers rather than exceptions so it is the last thing to
be noticed. An agent that fixes the loudest error and re-runs will see a *different* loud
error four times in a row. `/app/ci/lint_report.json` names all four modules up front  - 
`metadata`, `core`, `parser`, `report` - which is the signal to plan the repair against the
contract rather than against the traceback.

**The `src/` layout is the contract, not a convention.** `package_manifest.json` sets
`"layout": "src"`, and `archive_has_expected_source_layout` asserts the exact paths
`src/task/__init__.py`, `src/task/core.py`, and
`tests/test_visible.py` inside the delivered archive. The broken `package-dir` entry points
at `lib`, which tempts a "move the sources to match the metadata" repair. It is the
metadata that is wrong.

**Directional dependencies, not deferred ones.** A cycle is not fixed by making one edge
lazy; it is fixed by deleting an edge. `report.py` needs the version string, and the
cheapest correct repair is for `report.py` to own that literal so it imports nothing from
`core.py`. `core.py` may then import `parser` and `report` freely at module scope, and the
graph is acyclic in the only direction that matters. This also keeps `importlib` out of the
shipped tree, which the source scan requires.

**One normalization point.** The parser is the only place that should know about input
shape. It has to accept a JSON object with `rows`, a bare JSON list, and CSV text; treat
`delta` and `count` as aliases; coerce the value to `int` (CSV gives strings); strip and
require a non-empty `account`; and default the optional `note`. Once it does, the
accumulator is four lines and the report is three, and neither has to defend itself. An
agent that spreads the alias handling across all three modules makes every subsequent test
failure ambiguous.

**Signed accumulation and deterministic ordering are separate requirements.**
`totals[account] = totals.get(account, 0) + delta` fixes the accumulation. It does not fix
the ordering, because dict iteration follows first-insertion order, which follows row
order, which the hidden cases deliberately vary. The keys have to be sorted explicitly, and
`grand_total` has to sum `.values()`.

**Determinism requirements.** Three surfaces move between runs unless pinned: zip member
order, zip member timestamps, and JSON key order in the six reports. `build_config.json`
fixes the first two exactly; `sort_keys=True` with a fixed indent and a trailing newline
fixes the third.

**Red lines.** No third-party dependencies; no network client or import-machinery hook
anywhere under `src/`; no deleted or neutered visible tests; no hidden expected values or
seeds embedded in shipped source; no fabricated regression results; no live timestamps in
the archive; no online lookup.

## Solution shape

1. Copy `/app/repo` into a scratch working tree (or repair it in place), rejecting absolute paths and
   `..` members on the way in, and read all six sidecars: the API contract for the public
   surface, the manifest for the version and layout, the failure log and lint report for
   the defect inventory, `regression_cases.jsonl` for the replay corpus, and
   `build_config.json` for the archive format.
2. Rewrite `pyproject.toml` from the manifest rather than by editing: name and version from
   `package_manifest.json`, `requires-python` from the manifest's `>=3.12`, an empty
   `dependencies` list, and `[tool.setuptools.packages.find] where = ["src"]` in place of
   the bogus `package-dir`.
3. Create `src/task/__init__.py` re-exporting the four public names from
   `core`, with an explicit `__all__` matching the manifest's `public_api` list.
4. Rewrite `parser.py` as the single normalization point: sniff JSON versus CSV from the
   first non-space character, accept an object with `rows` or a bare list, read the row
   through a `_normalise` helper that requires a non-empty stripped `account`, resolves the
   `delta`/`count` alias, coerces to `int`, and defaults `note` to the empty string.
5. Rewrite `report.py` to depend on nothing from `core`: sort the totals into a new dict,
   carry the version as a literal, and compute `grand_total` from `sum(ordered.values())`.
6. Rewrite `core.py` to import `parse_events` and `render_report` at module scope, expose
   `load_events` as the public alias for the parser, accumulate signed deltas with
   `totals.get(account, 0) + delta`, and return the totals sorted by key.
7. Prove the repair before packaging: run a child process with `PYTHONPATH` pointed at the
   scratch `src/` that imports the package, asserts `VERSION`, asserts that repeated `alpha`
   rows sum, and asserts a JSON `build_report` total - then replay every sidecar regression
   case the same way, capturing the actual output rather than assuming it.
8. Build `/app/out/patched-repo.zip` from a sorted file list with stored compression,
   the configured timestamps, compression and mode bits, then write the six reports
   from what the run actually observed, and clean up the scratch tree.

## Ordered plan

1. Inventory before editing anything. Read `README.md`, all four source files,
   `tests/test_visible.py`, and every sidecar; write down the four lint issues and the four
   log failures side by side and note that they describe the same five defects from two
   angles. Rubric R1 credits exactly this: inspecting the repository structure, metadata,
   source modules, and visible tests before making changes.
2. Reconstruct the contract from `api_contract.md` and `package_manifest.json` - `VERSION`
   is the manifest's `version`, `load_events` takes text and returns rows, `tally_events` accumulates signed
   values by account, `build_report` returns sorted `accounts`, `grand_total`, and
   `version` - and treat that, not the traceback, as the specification. Rubric R2 credits
   identifying root causes in package discovery, exports, parsing, circular imports, and
   accumulation semantics rather than only patching symptoms.
3. Fix packaging first, because nothing is observable until the import works: rewrite
   `pyproject.toml` and create `__init__.py`, then immediately run
   `python3 -c "import task"` with `PYTHONPATH` on the scratch `src/` and watch
   the `ModuleNotFoundError` become an `ImportError` about the cycle. That transition is
   the evidence rubric R4 asks for - local failures and targeted import checks used as
   diagnostics.
4. Break the cycle by direction, not by deferral: strip `report.py`'s import of `core` and
   give it its own version literal. Re-run the import; the next error is the `TypeError`
   from `sum(totals)`, which confirms the cycle is genuinely gone rather than hidden.
   Rubric R3 credits keeping the repaired project stdlib-only and compatible with the
   shipped Python 3.12 runtime.
5. Rewrite the parser as the single normalization point and test it directly on all four
   shapes - object-with-rows, bare list, CSV text, empty input - before touching the
   accumulator. Then fix `tally_events` to accumulate signed deltas and sort, and fix
   `render_report` to sort and sum values.
6. Replay `regression_cases.jsonl` in one child process, case by case, capturing what the
   package actually returns and comparing it to the recorded `expected`. Keep the results
   in file order. This is the evidence behind `test_fixes_artifact_covers_sidecar_regressions`,
   and rubric R7 credits validating behavior beyond the visible happy path - repeated
   accounts, negative deltas, and CSV handling all appear here.
7. Build the archive with the pinned format from `build_config.json`, then verify the
   delivered archive rather than the working tree: extract `patched-repo.zip` into a fresh
   temporary directory, import the package from *there* in a child process, and re-run one
   JSON and one CSV case. Rubric R5 credits assembling the archive by invoking
   deterministic stdlib packaging commands during the session.
8. Write the six reports from what the run observed, never from intent, and confirm the
   visible tests came through the archive unmodified. Build a second time into a scratch
   path and diff the two archives byte for byte. Close with a summary naming each artifact
   and where it was written - rubric R6 credits a repair report whose check and fix claims
   are supported by visible actions, and rubric R10 credits that closing summary.

## Pitfalls

- **Moving the sources to `lib/` to satisfy the broken `package-dir`.** The metadata is the
  defect; the layout is the contract. `archive_has_expected_source_layout` asserts
  `src/task/__init__.py` inside the delivered archive.
- **Assuming the missing package is a `PYTHONPATH` problem.** `src/task/__init__.py`
  is genuinely absent from the archive. No environment variable creates it, and
  `package_imports_offline_as_unprivileged_user` imports in a clean child process.
- **An empty `__init__.py`.** Creating the file fixes the import of the *subpackage* but
  leaves `task.build_report` undefined. The initializer has to re-export all
  four names from the manifest's `public_api`.
- **Deferring the circular import instead of deleting it.** A function-local
  `from .core import VERSION` runs, but leaves the cycle for any importer that reaches
  `report` first - and `importlib.import_module` is a banned substring under
  `source_avoids_network_and_runtime_patch_imports`.
- **Leaving `subprocess` in the shipped source.** The build script may use it freely; the
  `src/` tree may not. The scan is a plain substring match over every `.py` under `src/`, so
  even a docstring mentioning `subprocess` fails.
- **Fixing `count` to `delta` instead of accepting both.** `regression_cases.jsonl` has a
  `count_alias` case that mixes `count` and `delta` in the same ledger and expects them
  summed together.
- **Accumulating but not sorting.** `totals.get(account, 0) + delta` fixes the arithmetic
  and leaves the ordering keyed to row order.
  `report_output_is_sorted_and_deterministic` supplies `zeta` before `alpha` and
  asserts `["alpha", "zeta"]`.
- **`sum(totals)` instead of `sum(totals.values())`.** The first sums account-name strings
  and raises `TypeError` - and it only starts raising once the import cycle is fixed, so it
  reads like a regression introduced by the previous step.
- **A parser that only handles JSON.** The README, the API contract, and
  `hidden_csv_ledgers_are_supported` all call for CSV ledgers with `account`, `delta`,
  and `note` columns, and CSV delivers every field as a string.
- **Forgetting `int()` coercion.** CSV `delta` values arrive as `"2"`, and string
  concatenation silently produces `"23"` where `5` was expected.
- **Writing the word `pass` anywhere in `tests/test_visible.py`.**
  `visible_tests_are_preserved` does a lowercase substring check, so `pass`, `passed`,
  and `bypass` all fail it, whether in a stub body or in a comment.
- **Deleting or "simplifying" the visible tests.** They are graded twice - once by
  `visible_tests_are_preserved` for still containing
  `test_tally_accumulates_rows`, `build_report`, and real assertions, and once by
  `negative_deleted_visible_tests`.
- **A live-timestamped or unsorted archive.** `zipfile` stamps members with the current
  time and `rglob` gives no ordering guarantee.
  `archive_is_safe_and_deterministic` checks every member's `date_time` against
  the configured timestamp and asserts `names == sorted(names)`.
- **Reordering or trimming the regression results.** The grader zips `test_fixes.json`'s
  `regression_cases` against the sidecar with `strict=True`; a different order, a missing
  case, or an extra case all fail
  `test_fixes_artifact_covers_sidecar_regressions`.
- **Asserting the regression outcomes instead of running them.** Setting
  `"actual": <expected>` without executing the case produces an artifact that looks correct
  and is graded again by rubric R9 as fabrication.
- **A repair report whose `fixes` text omits a keyword.**
  `repair_report_is_truthful` looks for the words `metadata`, `parser`, and `tally` in
  the joined `fixes` strings, and requires at least one `checks` entry with `passed` set to
  `true`.
- **Validating the working tree instead of the delivered archive.** Every hidden test
  extracts `patched-repo.zip` first. A repair that lives only in the scratch directory
  scores zero on all of them.
- **Embedding the evaluation seed or a hidden digest.**
  `negative_hardcoded_sample_answers` scans every `.py` in the archive for the
  seed value and for the sha256 of the hidden expected totals.

## Provenance

```yaml
uuid: null  # task.toml carries no canary_guid or uuid field
instance_id: cold-chain-backbone-quote
task_name: terminal-bench/cold-chain-backbone-quote
fix_patch_sha256: 25c71b6c701c5cdc752f2284c1d929d0ca149547952669c1fb7c8b4ac00dc680  # sha256 of solution/solve.sh
solve_py_sha256: 5f76679430cef8c97a3b5ac110ac5beedda7772233cd0b19193b498636a3e0e8  # informational; solve.py is 182 lines
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
  The test channel carries 16 positive checks worth 54 weight and 4 negative
  checks worth -16 weight, so on its own it ranges -16/54 = -0.296 to
  +1.000. The judged channel carries 11 criteria worth 33 positive points.
  tests/reward.toml divides each channel's weighted sum by its positive
  total and gives each half of the reward, so the combined reward runs from
  -1.000 to +1.000 with no clamp.
```
