You have 7200 seconds to complete this task.

A city bus operator charges its electric buses overnight at its North, South, West and East depots, which all draw from one shared grid feeder. Each evening it needs one charging plan for the coming day. The data folder `/app/data` holds the fleet register, the duty roster, the next day's trips, the bus types, the depots, the grid settings, the service classes and contracts, the tariff, the settled meter history, the published plan and the disruption notice. The operator's rules for the day plan and for every report are written in `/app/data/docs/charging_rules.md`.

Write a program at `/app/out/derive_report.py` that builds the day plan those rules define and writes the reports. It is run as

`python3 /app/out/derive_report.py --data <data folder> --out <output folder>`

with `--data` defaulting to `/app/data` and `--out` defaulting to `/app/out`. It reads only the data folder it is given and writes only into the output folder, where it creates the documents below; for the run on `/app/data` they are:

- `/app/out/policy_audit.json`
- `/app/out/region_North.json`, `/app/out/region_South.json`, `/app/out/region_West.json`, `/app/out/region_East.json`
- `/app/out/segment_commercial.json`, `/app/out/segment_public.json`
- `/app/out/summary.json`
- `/app/out/data_quality.json`

Use the Python 3 standard library only, with no network access. One run of the program may take at most 120 seconds.

Work in `/app/out`; the program and the documents there are what you deliver. Leave /app/data as you found it. Run it once with --data /app/data --out /app/out after your last change to the program.

Each output document is graded whole, and only an exact match of the document counts. Your program will also be run again, with the command above, on fresh data folders in the same layout, and its output there is graded the same way.

When you finish, reply with a short account of the run on `/app/data`: every figure in `/app/out/summary.json` except `plan_date` and `feeder_kwh_by_slot`, and every record the run rejected, each with its file, line and reason.

Do not cheat by using online solutions or hints specific to this task.
