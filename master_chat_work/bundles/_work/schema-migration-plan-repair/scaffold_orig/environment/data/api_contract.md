# Repair API contract

The repaired repository must import as `task` from `src/` and expose:

- `VERSION`, equal to the `version` in `/app/data/package_manifest.json`; the
  repaired `pyproject.toml` carries the same `version`
- `load_events(text: str) -> list[dict]` for JSON object/list payloads and CSV ledgers
- `tally_events(rows) -> dict[str, int]` with signed accumulation by account
- `build_report(text: str) -> dict` returning sorted `accounts`, `grand_total`, and `version`
  (the same `VERSION`)

The delivered `patched-repo.zip` follows `/app/data/build_config.json`: members
sorted by name, no directory entries, every member's timestamp equal to
`archive.timestamp`, compressed with `archive.compression` (`stored` or
`deflated`), and with unix permission bits equal to `archive.mode`.

No network clients, runtime monkeypatch hooks, or third-party dependencies are allowed.

## Report artifacts

Each report under `/app/out` is one JSON object; key order and whitespace are free.

- `repair-report.json`: `package` (the import name), `fixes` (a non-empty list of
  strings, one per repair you made, in your own words) and `checks` (a list of
  `{"name": str, "passed": bool}` objects for the checks you ran; at least one passed).
  The report is the one place to explain fixes in prose.
- `module_core.json`, `module_parser.json`, `module_report.json`: `module` (`core`,
  `parser` or `report`), `status` (`fixed` or `unchanged`), `fixes` (a list of
  strings in your own words, non-empty when `status` is `fixed`) and `lint_errors`
  (the number of `/app/data/lint_report.json` issues for that module whose
  `severity` is `error`). `module_core.json`
  adds `validations`, a non-empty list of the checks you ran against `tally_events`;
  `module_parser.json` adds `contract_terms`, the sorted names of the three entry points
  this contract lists; `module_report.json` adds `deterministic`, `true` when two
  `build_report` calls on the same input return equal results.
- `test_fixes.json`: `visible_tests_preserved` (bool), `previously_failing` (the
  sorted case names whose test is reported `FAIL` or `ERROR` in
  `/app/data/failing_tests.log`; a test named `test_<name>` belongs to case
  `<name>`), `regression_cases` (one
  `{"name", "expected", "actual", "passed"}` object per line of
  `regression_cases.jsonl`, in file order, where `actual` is what the repaired package
  returns for that case) and `all_regressions_passed` (bool).
- `summary.json`: `package`, `status` (`complete`), `inputs_used` (the sorted names of
  every file in `/app/data`), `artifacts` (the seven deliverable paths in the order the
  task lists them), `artifact_count` and `stdlib_only` (bool).
