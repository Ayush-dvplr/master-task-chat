# Report contract

Every report under `/app/out` is one JSON object; key order and whitespace are free.
Values describe the repaired package you deliver in `/app/out/package.zip`.

The package version is `required_version` from `/app/data/dependency_manifest.json`:
`__version__`, the `pyproject.toml` `version` and every report's `version` carry it.
`package.zip` holds every `archive_members` path of `/app/data/expected_targets.json`,
and each member uses the compression named by `zip_compression` in
`/app/data/compiler_flags.json` (`stored` or `deflated`) and the timestamp
`deterministic_zip_timestamps` (`YYYY-MM-DDTHH:MM:SS`).

- `selftest.json`: `ok` (bool), `package` (import name), `version` (the package's
  `__version__`), `archive` (`/app/out/package.zip`), `tests_run` (how many checks you
  ran, an integer), `reports` (the five other `.json` report paths, in the order the
  task lists them), `fixtures_total` (the number of entries in
  `/app/data/scoring_fixtures.jsonl`), `fixtures_passed` (how many of them the repaired
  `score_entry` scores exactly as their `want` object says) and `ci_commands` (the
  `commands` list of `/app/data/ci_config.yaml`, in order; each command is a YAML
  single-quoted scalar in which `''` stands for one `'`).
- `build_report.json`: `ok`, `package`, `version`, `layout` (`src`), `python` (`3.12`),
  `fixed_modules` (the sorted file names under `src/task/` that you changed
  or created) and `fix_categories` (a non-empty list of short labels for the kinds of
  faults you repaired, in your own words) and `log_errors` (the sorted distinct
  exception names that begin a line of `/app/data/build.log` in the form
  `<Name>Error: message`).
- `module_core.json`: `ok`, `module` (`task.core`), `public_functions` (the
  sorted names of the public functions the repaired core module defines),
  `uses_stdlib_tomllib` (bool), `default_label` (the label `score_entry` attaches),
  `average_rounding_digits` (the digits `summarize` rounds the average to) and
  `negative_measurements_raise` (the exception name `score_entry` raises on a negative
  measurement).
- `module_metrics.json`: `ok`, `module` (`task.metrics`), `bucket_order`
  (the module's bucket order), `thresholds` (`ok_min`, `watch_min`, `repair_min` and
  `critical_max`, the inclusive score bounds `bucket_for_score` uses) and
  `syntax_repaired` (bool).
- `dependency_resolution.json`: `ok`, `package`, `requires_python` (the repaired
  `pyproject.toml` value), `dependencies` (its runtime dependency list),
  `removed_dependencies` (sorted runtime dependencies the shipped project used that the
  repair drops) and `stdlib_modules_used` (the sorted standard-library modules the
  repaired core module imports, `__future__` excluded).
- `summary.json`: `ok`, `package`, `version`, `artifact_count`, `artifacts` (the seven
  deliverable paths in the order the task lists them), `primary_archive`
  (`/app/out/package.zip`), `json_reports` (how many of the deliverables are `.json`
  files) and `modules_mapped` (the sorted `/app/data/module_map.json` keys that name a
  module of the package itself, i.e. start with `task.`).
