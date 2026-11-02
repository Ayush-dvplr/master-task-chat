The directory `/app/repo` holds `migrakit`, a standard-library Python repository with a `src/` layout that upgrades historical partner records to the canonical schema of their domain through a graph of migration edges. Parts of its code do not behave the way its contract says.

The contract is `/app/ci/repository_contract.md`. It names the other files in `/app/ci` that also carry rules, and those files are the records the package reads: the migration graph, the field policy, the null semantics, the partner register, the report taxonomy and partner order, and the shipped feed, correction log and replay manifest. Repair the repository so that every stage behaves as the contract states, on any contract folder and feed inside the stated limits, and not only on the shipped ones. Every public function the contract names must behave as stated when it is called on its own.

Write these files:

- `/app/out/patched-repo.zip`: the repaired repository, laid out as rule K1 states.
- `/app/out/summary.json`: the run summary the repaired package produces for the shipped inputs in `/app/ci`.
- `/app/out/module_core.json`, `/app/out/module_parser.json`, `/app/out/module_report.json`, `/app/out/test_fixes.json` and `/app/out/repair-report.json`, in the shapes rule K19 gives.

Keep the visible tests in `tests/test_visible.py` and their assertions. Use only the Python standard library; add no third-party package to the repository or the environment.

In your final reply, give these figures from running the repaired package on the shipped inputs: how many records end migrated, how many end rejected, how many are attempted, how many end with code `E_UNREACHABLE`, how many entries `invalid_corrections` lists, and the sum of `completed_steps` over every record.

You have 7200 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
