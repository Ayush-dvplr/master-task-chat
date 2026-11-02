You have 5400 seconds to complete this task.

Our electric bus fleet charges overnight at four depots (North, South, West and East). Operations published a charging plan for the plan day, and then a disruption notice arrived with cabinet outages, a feeder derating and extra trips. The charging plan now has to be redone for the whole fleet. Please write the program that does this.

Write a Python 3 program at `/app/out/derive_report.py`. It is run as:

    python3 /app/out/derive_report.py --data <data folder> --out <output folder>

When `--data` is not given it reads `/app/environment/data/`, and when `--out` is not given it writes to `/app/out/`. The program uses only the Python standard library, reads only the data folder and `/app/environment/docs/`, and writes only inside the output folder. One run on one data folder must finish within 120 seconds.

The planning rules, the meaning of every input file and the content of every report are in `/app/environment/docs/charging_rules.md`.

The program writes nine reports into the output folder: `policy_audit.json`, `data_quality.json`, `summary.json`, `region_North.json`, `region_South.json`, `region_West.json`, `region_East.json`, `segment_commercial.json` and `segment_public.json`.

After writing the program, run it once on `/app/environment/data/` so that the reports for this plan day are present under `/app/out/`. Do not change anything under `/app/environment/`.

Each output document is graded whole, and only an exact match of the document counts. Your program will also be run again, with the command above, on fresh data folders in the same layout, and its output there is graded the same way.

You may not look anything up online.
