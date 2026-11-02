The files in `/app/data` are a book of flood repair funding rounds: the repair proposals of each round with their sites, crews and households, the segment of each proposal, the site register with risk classes and premiums, the site regions, the crew register, the permits named by each proposal, the exclusions between proposals or sites, the benefit rates, and the audit queries. The file `/app/data/contract.md` is the whole specification of that data, of how each round is checked, valued and planned, and of every output document.

Write a reusable program at `/app/out/derive_report.py` that implements the contract, runnable as `python3 /app/out/derive_report.py DATA_DIR OUT_DIR`. The program is one self-contained file that uses python3 and its standard library only. Run it on the shipped book with `/app/out` as the output folder, so that these documents exist:

- `/app/out/summary.json`
- `/app/out/policy_audit.json`
- `/app/out/data_quality.json`
- `/app/out/region_North.json`, `/app/out/region_South.json`, `/app/out/region_West.json` and `/app/out/region_East.json`
- `/app/out/segment_commercial.json` and `/app/out/segment_public.json`

The program will also be run on other books written in the same format. Each output document is graded whole on fresh books, and only an exact match counts.

In your final reply, list every round of the shipped book that the program rejects, each by its round id.

You have 7200 seconds to complete this task. Leave enough of that time to finish and write your final reply. Do not cheat by using online solutions or hints specific to this task.
