Our billing team keeps a small standard-library Python package, `tariff`, in `/app/repo` (a `src/` layout). It reads a month of meter reads and turns them into customer invoices. A billing audit found that its invoices drift from the written tariff contract at `/app/ci/api_contract.md`. The package's unit tests are in `/app/repo/tests/test_visible.py`. The other files in `/app/ci` are the sample data the package runs on, the dispute replays and their last failing log, the lint report, the package manifest and the build settings.

Repair the package in `/app/repo` so it follows the contract, and correct any unit test that asserts something the contract contradicts. When the code, its docstrings, its README or its visible tests disagree with `/app/ci/api_contract.md`, the contract wins. Use only the Python standard library.

Deliver these files:

- `/app/out/patched-repo.zip`, the repaired repository;
- `/app/out/repair-report.json`;
- `/app/out/module_core.json`, `/app/out/module_parser.json` and `/app/out/module_report.json`, one note per module;
- `/app/out/test_fixes.json`;
- `/app/out/summary.json`.

The contract gives the content of each file. The archive is what gets imported and run, so the repaired code must be inside it. Each invoice, each exception list and each statement list is graded whole on fresh inputs, and only an exact match counts.

In your final reply, list every function you changed in the package, by module and name.

You have 7200 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
