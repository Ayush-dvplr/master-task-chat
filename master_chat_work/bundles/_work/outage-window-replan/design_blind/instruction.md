A transmission operator published its maintenance outage season and has since received control-room notices: crews lost on some days, new requests, withdrawals. Write a program that replans the season and publishes the replan.

The data is in `/app/data`. Its register, `/app/data/docs/RULES.md`, names the document that governs each topic.

Write the program at `/app/out/derive_report.py`. It is run as

```
python3 /app/out/derive_report.py --data <data dir> --out <out dir>
```

where `<data dir>` has the same layout as `/app/data`. It writes nine documents into `<out dir>`: `policy_audit.json`, `summary.json`, `data_quality.json`, `region_North.json`, `region_South.json`, `region_West.json`, `region_East.json`, `segment_commercial.json` and `segment_public.json`. When a file it needs is missing or cannot be read, it exits with a non-zero status and a message naming that file.

Run it once on `/app/data` with `--out /app/out`, so that the nine documents sit in `/app/out` next to the program.

The program is run again on fresh inputs in the same layout. Each output document is graded whole against the contract on each input set, and only an exact match counts. Each run must finish within 300 seconds. Use the Python 3 standard library only, with no network access.

Leave `/app/data` as you found it, and write only under `/app/out`.

In your final reply, give the objective pair `[risk_days, moved]` for `/app/data` and list every rejected record of that run by its `asset_id` with its rejection reason.

You have 7200 seconds to complete this task.
