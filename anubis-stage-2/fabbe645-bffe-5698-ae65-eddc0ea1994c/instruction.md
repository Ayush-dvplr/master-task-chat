Hello, this is the archive desk at Konkan Coast Broadcast Archive. Our four tape vaults hold more copies of the digitised masters than the retention charter asks for, and the next tape order depends on a proper plan of which copies to keep and how the kept copies pack onto cartridges. We need that plan as a program the desk can run again every cycle, so please write the planner, run it once on this cycle's export and tell us what it found.

This cycle's estate export is in `/app/data`. Please start reading at `/app/data/archive_desk_brief.md`; it tells you which paper governs which question. The exact layout of every output file, with the status values and reason codes, is in `/app/data/plan_output_contract.md`.

Write the planner as `/app/out/optimize.py` in Python 3.12. The desk will call it like this:

```bash
python3 /app/out/optimize.py --data DATA_DIR --out OUT_DIR
python3 /app/out/optimize.py --data DATA_DIR --out OUT_DIR --prior EARLIER_OUT_DIR
```

What we need from the planner:

1. It works on any export laid out like this one. Later cycles come with other planning dates, other amendments, other cartridges and a different mix of objects, so nothing that belongs to this cycle can be fixed inside the program.
2. It reads only from the folder given with `--data` (and `--prior` when given) and writes only into the folder given with `--out`.
3. Given the same input it writes byte identical files every time, whatever the input folder is called and wherever it sits.
4. With `--prior` pointing at the output of an earlier run, each scenario carries forward the earlier tape volumes in the way the volume layout paper describes.
5. When the export does not reconcile with its census, it holds the plan back and writes only the status report with its reasons, as the contract describes.
6. A run on an export of this size finishes in under 60 seconds.

Every byte count, digest, class, list, label, order and fill figure is compared exactly against what the papers and the export determine. There is no tolerance, so a value that is off by one counts as wrong.

When the planner is ready, run it once with `--data /app/data --out /app/out`, so that these files are in place along with the program itself:

- `/app/out/scenario_visible.json`
- `/app/out/scenario_peak.json`
- `/app/out/scenario_steady.json`
- `/app/out/scenario_burst.json`
- `/app/out/scenario_latency.json`
- `/app/out/perf_report.json`
- `/app/out/bottleneck_analysis.json`
- `/app/out/recommendations.json`
- `/app/out/data_quality.json`

Treat everything under /app/data as read only. Work offline with the Python standard library only and install no packages. Do not cheat by using online solutions or hints specific to this task.

In your reply, give us the plan status, and for each scenario the number of objects, kept replicas, released replicas and volumes. Wherever two papers disagreed, tell us which one you followed and why. Also list the checks you actually ran on the output.

You have 14400 seconds to complete this task.
