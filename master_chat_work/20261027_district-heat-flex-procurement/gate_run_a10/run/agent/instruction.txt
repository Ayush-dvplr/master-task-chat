A district-heating company runs a winter demand-response programme. Its exports for one season are in `/app/data`, and the full rulebook for reading them is `/app/data/schema.md`. Treat schema.md, together with the data files it names, as the authority on every rule, unit and output field, and work out from them how the files fit together.

Write one reusable program at `/app/out/derive_report.py`, run as `python3 /app/out/derive_report.py DATA_DIR OUT_DIR`, that reads an extract in this schema from `DATA_DIR` and writes the reports into `OUT_DIR`. It will also be run on other extracts in the same schema, so it must follow the rules in general and must not depend on the shipped records. Use only the Python 3.12 standard library.

Run it on the shipped data so these files exist: `/app/out/summary.json`, `/app/out/policy_audit.json`, `/app/out/data_quality.json`, `/app/out/region_North.json`, `/app/out/region_South.json`, `/app/out/region_West.json`, `/app/out/region_East.json`, `/app/out/segment_commercial.json` and `/app/out/segment_public.json`.

Each output document is graded whole on fresh inputs: every value in it must be the one the rulebook defines. For every event and region the program picks the portfolio the rulebook calls best. Energy is in whole ticks, money in whole cents and ratios in whole basis points, all as JSON integers. Write every JSON file with sorted keys and a trailing newline, and order every array as schema.md says.

When you finish, reply with a short report of what the program does and how you checked it.

You have 7200 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
