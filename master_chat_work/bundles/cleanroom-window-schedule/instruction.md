The files in `/app/data` are a book of nights from a pharmaceutical cleanroom: the jobs offered each night in fixed time windows, the bays and the families they are qualified for, the changeover fees and sterilisation crew minutes, the clients with their regions and segments, the mandatory jobs, and the night calendar. The file `/app/data/contract.md` is the whole specification of that data, of how each night is planned, and of every output document.

Write a reusable program at `/app/out/derive_report.py` that implements the contract, runnable as `python3 /app/out/derive_report.py DATA_DIR OUT_DIR`. Run it on the shipped book with `/app/out` as the output folder, so that these documents exist:

- `/app/out/summary.json`
- `/app/out/policy_audit.json`
- `/app/out/data_quality.json`
- `/app/out/region_North.json`, `/app/out/region_South.json`, `/app/out/region_West.json` and `/app/out/region_East.json`
- `/app/out/segment_commercial.json` and `/app/out/segment_public.json`

The program will also be run on other books written in the same format. Each output document is graded whole on fresh books, and only an exact match counts.

In your final reply, list every night of the shipped book that the program rejects, each by its night id.

You have 7200 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
