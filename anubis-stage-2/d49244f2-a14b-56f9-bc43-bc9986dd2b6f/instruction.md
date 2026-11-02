`/app/data` is a return batch for the 2026 levy year of the Commonwealth of Arvenna. The law is `/app/data/levy_code.md`, the Consolidated Enterprise Levy Code: one consolidated statute of roughly 200,000 tokens. Amendments, corrections, substitutions made elsewhere in the text, binding rulings and material with no legal effect are printed where they were made and are not written into the provisions they affect. A figure printed in one section is therefore not necessarily the figure in force, and a provision can depend on a definition or rule stated far away from it. The Code's own provisions decide which text has effect, how provisions combine, and in what order things are applied. `/app/data/report_format.md` fixes the shape of the assessment statements; the Code fixes every value in them. The other files are the registers the statements are computed from.

Build `/app/out/derive_report.py`, a reusable Python 3.12 program, run as

```bash
python3 /app/out/derive_report.py <DATA_DIR> <OUT_DIR>
```

that reads a return batch laid out like `/app/data` and writes the nine statements into `<OUT_DIR>`. Run it on `/app/data` with `/app/out` as the output directory and leave the results there. The program will also be run on other return batches under the same Code, with different filers and records, different row order, a different batch identifier, a different assessment date and a different directory name, so it must apply the Code in general.

## Deliverables

- `/app/out/derive_report.py`: the reusable program.
- `/app/out/summary.json`: batch totals, region totals and status counts.
- `/app/out/policy_audit.json`: every value of the Code the assessment applies, with its controlling section.
- `/app/out/data_quality.json`: register counts and every matter the Code requires to be recorded.
- `/app/out/region_North.json`, `/app/out/region_South.json`, `/app/out/region_West.json`, `/app/out/region_East.json`: the filer assessments of each region.
- `/app/out/segment_commercial.json`, `/app/out/segment_public.json`: the filer-class rollups.

## Requirements

R01. All ten deliverables exist at those exact paths, and the nine statements follow `report_format.md` exactly: key names, nesting, list order, integer cents, and serialization.

R02. Every rate, amount, limit, period, band, designation, date and sequence is the one in force under the Code read as a whole, for the day, quarter or year concerned.

R03. Every `authority` in `policy_audit.json` is the section that controls the value as `report_format.md` defines it.

R04. Every rounding happens exactly where, and in the mode, the Code directs. No floating-point arithmetic touches money.

R05. The program reads only its `<DATA_DIR>` argument and writes only into its `<OUT_DIR>` argument, creating `<OUT_DIR>` if it does not exist. Running it twice on the same batch gives byte-identical files, and one run on a batch the size of `/app/data` finishes within 120 seconds.

R06. The program uses the Python standard library only. It uses no network, subprocess, multiprocessing, ctypes, clock or randomness, it does not import importlib, site or builtins or modify sys.modules, and it embeds no filer identifier, total or other figure taken from the shipped registers.

R07. Before you finish the program, write out in your session a table of every provision you apply that modifies a value printed elsewhere: its section number, the value it modifies and its effect.

R08. Before relying on any document in Part 14 or any provision of Part 7, state whether the Code gives it legal effect, and why.

R09. Work at least one filer through by hand, showing its activity levy lines, establishment levy, surcharge, credits in order, Net Levy and instalments, and compare the result with your program's output.

R10. Build at least one return batch of your own, distinct from `/app/data`, and run the finished program on it.

R11. In your final response, name the output directory, list the checks you ran, and list the section numbers of the modifying provisions your program applies.

All comparisons are exact. Do not modify anything under `/app/data`. The environment is offline; do not install packages.

You have 14400 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
