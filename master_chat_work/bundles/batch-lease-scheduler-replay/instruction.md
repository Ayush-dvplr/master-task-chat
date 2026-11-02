A zipped Python package, `leasebook`, is at `/app/data/project.zip`. It replays books of batch scheduler logs: jobs with priorities, pools, dependencies, retry limits and worker leases, driven by submit, heartbeat, fail, cancel, boost and worker events. `/app/data/replay_contract.md` is its contract: the book format and bounds, the replay, the output documents, the refusals, and the package and build layout. The other files in `/app/data` form one book.

Repair the package so that it meets the contract, and write these files:

- `/app/out/package.zip`: the repaired package, laid out as the contract's section 9 describes.
- `/app/out/selftest.json` and `/app/out/build_report.json`: the self-test and build record of that archive, as section 9 describes.
- `/app/out/module_core.json`, `/app/out/module_metrics.json`, `/app/out/dependency_resolution.json` and `/app/out/summary.json`: the documents the repaired package writes for the book in `/app/data`.

The package inside `/app/out/package.zip` is also run on fresh books within the contract's bounds, from another working directory and as another user, with Python 3.12. Each output document is graded whole on fresh books, and only an exact match counts.

Use only the Python standard library; anything you install here is absent later. You have 7200 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
