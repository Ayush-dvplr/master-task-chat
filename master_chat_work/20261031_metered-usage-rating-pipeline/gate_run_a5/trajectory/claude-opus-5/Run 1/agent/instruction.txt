Our cloud team bills metered usage every month. Five regional collectors (central, east, north, south and west) each write their own file in their own format, and the month's extract sits in `/app/data` together with the account list, the plan changes log, the rate card, the commitments file, the product map and the collector controls. Treat `/app/data` as read-only.

Please write one reusable program at `/app/out/transform.py` that reads a month's extract and writes the month's rated usage and reports. It must work on any month's extract laid out like this one, not only on the month that is here. It is run like this:

```bash
python3 /app/out/transform.py --input <input directory> --output <output directory>
```

Every rule the program has to follow is written in `/app/data/rating_contract.md`: what each input file means, which records are quarantined and why, how plans and segments change during the month, how a line is rated, how each region's commitment credit is shared, and the exact keys and value formats of every output document. If any other file in `/app/data` seems to say something different from the contract, the contract wins.

For this month, run the program with `--input /app/data --output /app/out`, so that these fourteen files exist:

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

Each output document is graded whole, and only an exact match counts: this month's documents are graded as they stand in `/app/out` when you finish, and your program is run again on fresh extracts of other months laid out like this one, from a different input folder and a different working directory. Apart from the record counts in `/app/data/collector_controls.json`, nothing in `/app/data` gives an expected count or total.

In your final reply, list each file you wrote under `/app/out`, and say which checks you ran on the last version of the program and what they showed.

You have 7200 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
