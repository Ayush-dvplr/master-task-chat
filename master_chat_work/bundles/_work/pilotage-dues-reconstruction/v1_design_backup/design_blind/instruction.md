A pilotage authority has a batch of disputed pilotage invoices and no copy of the tariffs its pilot
stations charged. Paid invoices, the pilot movements log, the vessel register, exemption certificates,
holiday lists, tariff notices and station fees are in `/app/data`, together with the tariff circular and policy documents that govern them.
`/app/data/rule_register.md` names the governing file for every rule.

Write a Python program at `/app/out/derive_report.py`, using only the standard library, that reviews the
disputed batch and writes the documents described in `/app/data/output_contract.md`: `summary.json`,
`policy_audit.json`, `data_quality.json`, `region_North.json`, `region_South.json`, `region_West.json`,
`region_East.json`, `segment_commercial.json` and `segment_public.json`.

The program is run as:

    python3 /app/out/derive_report.py --data <data directory> --out <output directory>

Run it once with `--data /app/data --out /app/out`. It will also be run on other data directories with
the same files and layouts, and only an exact match of every document counts.

In your final reply, list every station and tariff period with its `period_start`, `tariff` and `reason`
as your program wrote them, and every disputed invoice whose verdict is `underbilled`, each by its invoice
id.

You have 3600 seconds to complete this task. Do not look up this data or its answers online.
