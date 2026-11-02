You have 7200 seconds to complete this task. Leave enough of that time to finish and write your final reply.

Our heavy maintenance planning team published the hangar check plan for the season, and then
Maintenance Control sent a disruption notice with base closures and revised aircraft availability.
The plan now has to be redone for the whole fleet at every base, and the overtime it needs
has to be settled against the fleet overtime allowance. Please write the program that does this.

Write a Python 3 program at `/app/out/derive_report.py`. It is run as:

    python3 /app/out/derive_report.py DATA_DIR OUT_DIR

`DATA_DIR` is a data folder in the format of `/app/data/` and `OUT_DIR` is the folder the program
writes into. The program uses only the Python standard library, reads only the data folder and the
documents, and writes only inside `OUT_DIR`. One run on one data folder must finish within 60 seconds.

The rules are in `/app/data/docs/`. Start with `/app/data/docs/README.md`, which says which file
governs each topic. The input files are described in `/app/data/docs/data_conventions.md` and the
output files in `/app/data/docs/output_schema.md`. Every number the plan needs comes from the data
folder; nothing is to be typed in by hand.

Write the program first, and then run it once as
`python3 /app/out/derive_report.py /app/data /app/out`, so that the output files in `/app/out/`
come from that run. That run writes these files:

- `/app/out/policy_audit.json` (the plan for every open check request)
- `/app/out/region_North.json`, `/app/out/region_South.json`, `/app/out/region_West.json`,
  `/app/out/region_East.json` (one report per base)
- `/app/out/segment_commercial.json`, `/app/out/segment_public.json` (one report per segment)
- `/app/out/summary.json` (the season summary)
- `/app/out/data_quality.json` (the rejected request rows)

Each output document is compared field by field with the expected document, and only an exact match
of a field counts. Your program will also be run again on other data folders in the same format,
and its output there is compared the same way.

In your final reply, name every request that the plan for `/app/data/` defers, by its request id.

Do not cheat by using online solutions or hints specific to this task.
