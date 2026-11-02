Our cold-chain planning team quotes the cost of a backbone network for each project in a quote book: the links to build and the sites to switch on so that the depot reaches every cold room. The quoting package in `/app/repo` gives wrong quotes and wrong reports, and parts of it do not run. Please repair it in place so that it follows `/app/ci/api_contract.md`. The book in `/app/ci` is the current one; the CI log, lint report, regression cases and build settings there come from the last pipeline run.

Please deliver these files:

- `/app/out/patched-repo.zip`, the repaired repository packed as the contract and `/app/ci/build_config.json` describe.
- `/app/out/module_core.json`, `/app/out/module_parser.json`, `/app/out/module_report.json` and `/app/out/summary.json`, as the repaired command writes them for the book in `/app/ci`.
- `/app/out/test_fixes.json`, with the previously failing tests and the quote of every regression case.
- `/app/out/repair-report.json`, with the defects you fixed and the checks you ran.
- `/app/repo/src/task/core.py`, repaired in place and written so that our team can maintain it.

The contract gives the content of each file. The archive is what gets imported and run, so the repaired code must be inside it. Each output document is graded whole on fresh books, and only an exact match counts.

In your final reply, list the projects of the current book that the command rejects, with their codes.

You have 7200 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
