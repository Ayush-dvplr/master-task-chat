The harbour authority of four pilot stations has a batch of disputed pilotage invoices and no copy of the tariffs its stations billed by. The files in `/app/data` are what it holds; `rule_register.md` lists them and names the file that governs each topic.

Write a Python 3 program `/app/out/derive_report.py`, standard library only, that is run as

    python3 /app/out/derive_report.py --data <data directory> --out <output directory>

It reads the data files from the data directory and writes these nine documents, as `output_contract.md` describes, into the output directory:

- `summary.json`
- `policy_audit.json`
- `data_quality.json`
- `region_North.json`, `region_South.json`, `region_West.json`, `region_East.json`
- `segment_commercial.json`, `segment_public.json`

Run it once with `--data /app/data --out /app/out`. The program will be run again, with the same command, on fresh data directories that hold the same files in the same layouts. Each output document is compared whole on every data directory, and only an exact match counts.

Work in `/app/out` and leave `/app/data` unchanged.

In your final reply, list every period of every station with its `period_start` and its tariff (or that it is unresolved), and every invoice id whose verdict in `/app/out/policy_audit.json` is `underbilled`.

You have 3600 seconds to complete this task. Do not look up this data or its answers online.
