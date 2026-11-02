Our fleet fuel card business settles card sales every month through five processors: kestrel, lumen, marlow, norvik and oberon. Each processor sends its own settlement export in its own format. This month's data is in `/app/data`: the rule documents in `/app/data/docs`, the master data in `/app/data/ref` and the five exports in `/app/data/exports`. Treat `/app/data` as read-only.

Please write one reusable program at `/app/out/transform.py` that reads a month's data directory and writes that month's consolidated settlement ledger and reports. It is run like this, with absolute paths, from any working directory:

```bash
python3 /app/out/transform.py --data <data directory> --out <output directory>
```

The rules the program follows are in the documents under `/app/data/docs`; `/app/data/docs/RULES.md` lists them and says which one governs when two disagree. Use the Python standard library only.

Write the program first, then produce this month's outputs by running it with `--data /app/data --out /app/out`, so that these fourteen files exist:

- `/app/out/transform.py`
- `/app/out/normalized.jsonl`
- `/app/out/summary.json`
- `/app/out/data_quality.json`
- `/app/out/product_summary.json`
- `/app/out/region_central.json`
- `/app/out/region_east.json`
- `/app/out/region_north.json`
- `/app/out/region_south.json`
- `/app/out/region_west.json`
- `/app/out/segment_consumer.json`
- `/app/out/segment_corporate.json`
- `/app/out/segment_enterprise.json`
- `/app/out/segment_smb.json`

The program is also run again, with the command above, on fresh months' data directories laid out the same way. Each output document is graded whole, on this month's data and on those fresh months, and only an exact match counts.

Write only under `/app/out`. In your final reply, list each file you wrote under `/app/out`, and list every processor that has rejected lines this month with each rejection reason and its count.

You have 7200 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
