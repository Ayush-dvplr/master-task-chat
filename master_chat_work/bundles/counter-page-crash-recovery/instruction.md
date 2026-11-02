The archive `/app/data/project.zip` holds `pagerecover`, a standard-library Python package that recovers the counter pages of crashed storage images from a write-ahead journal and the pages found on disk. Extract the project to `/app/project` and repair it so that it installs and its recovery follows the recovery contract, then deliver the outputs listed here. The book in `/app/data` (the journal, the disk page frames, the page map, the checkpoint master records, the transaction catalog and the audit queries) is the input of the recovery.

`/app/data/recovery_contract.md` is the governing document. It states the input formats, the validation codes, the recovery protocol, the shape of every output document, the stated limits and the build deliverables. Where the project's source, README, comments or tests disagree with it, the contract decides. The configuration files `expected_targets.json`, `compiler_flags.json`, `dependency_manifest.json` and `ci_config.yaml` in `/app/data` supply the values the contract refers to.

Write these files:

- `/app/out/package.zip`: the repaired project archive.
- `/app/out/module_core.json`, `/app/out/module_metrics.json`, `/app/out/dependency_resolution.json` and `/app/out/summary.json`: the four recovery documents of the book in `/app/data`, written by the package from the archive with `python -m pagerecover recover --data /app/data --out /app/out`.
- `/app/out/selftest.json` and `/app/out/build_report.json`: the build facts the contract lists.

Only an exact match counts. Each recovery document counts as a whole, across every crash image it covers: one wrong value, one missing or extra record, or one list in a different order makes that document wrong. The archived package is also run, from other working directories, on other books in the same formats within the stated limits, so the documents must come from the package reading its inputs.

Use only the Python standard library on Python 3.12; anything you install with pip here will be absent later.

You have 7200 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
