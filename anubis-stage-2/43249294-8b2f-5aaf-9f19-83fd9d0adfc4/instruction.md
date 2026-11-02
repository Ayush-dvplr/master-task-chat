`/app/data` is a billing batch for the 2026 tariff year of the City of Vellmouth's water and wastewater utility. The law is `/app/data/tariff_code.md`, the Vellmouth Consolidated Municipal Utility Tariff Code: one consolidated text of roughly 200,000 tokens. The Code says which of its text has legal effect and in what order its provisions apply. `/app/data/report_format.md` fixes the shape of the statements; the Code fixes every value in them. The other files are the registers the statements are computed from.

Build `/app/out/derive_report.py`, a reusable Python 3.12 program, run as

```bash
python3 /app/out/derive_report.py <DATA_DIR> <OUT_DIR>
```

It reads a batch laid out like `/app/data` and writes the nine statements into `<OUT_DIR>`. Run it on `/app/data` with `/app/out` as the output directory and leave the results there. It will also be run on other batches under the same Code, with different accounts and records, different row order, a different batch identifier, a different assessment date and a different directory name, so it must apply the Code in general.

## Deliverables

- `/app/out/derive_report.py`: the reusable program.
- `/app/out/summary.json`: batch totals, region totals and status counts.
- `/app/out/policy_audit.json`: every value of the Code the assessment applies, with its controlling section.
- `/app/out/data_quality.json`: register counts and every matter the Code requires to be recorded.
- `/app/out/region_North.json`, `/app/out/region_South.json`, `/app/out/region_West.json`, `/app/out/region_East.json`: the account assessments of each region.
- `/app/out/segment_commercial.json`, `/app/out/segment_public.json`: the class rollups.

## Requirements

R01. All ten deliverables exist at those paths and the nine statements follow `report_format.md` exactly: keys, nesting, list order, integer units and serialization.

R02. Every rate, allowance, factor, limit, priority, period, designation, date and method is the one in force under the Code read as a whole, for the day, quarter or year concerned.

R03. Every `authority` in `policy_audit.json` is the section that controls the value as `report_format.md` defines it.

R04. Every rounding happens exactly where, and in the mode, the Code directs. No floating-point arithmetic touches money or volumes.

R05. The program reads only its `<DATA_DIR>` argument and writes only into its `<OUT_DIR>` argument. Two runs on the same batch give byte-identical files.

R06. The program uses the Python standard library only. It uses no network, subprocess, multiprocessing, ctypes, clock or randomness, does not change the interpreter, its import system or `builtins`, and embeds no account identifier, total or other figure taken from the shipped registers.

R07. Before your last edit of the program, write out in your session a table of every provision that modifies a value printed elsewhere in the Code, wherever in the Code it is printed: section number, value modified, new value or effect, and the period or date of making where the Code makes it matter.

R08. Before relying on any proposal, memorandum, example, note or ruling, state whether the Code gives it legal effect and why, and what prevails when a ruling conflicts with other text.

R09. Work at least one account through by hand, showing its meter intervals and blocks, wastewater, service and stormwater charges, surcharge, catchment levy, rebates in order with their limits, minimum charge, instalments and interest, and compare every figure with your program's output.

R10. Build at least one batch of your own, distinct from `/app/data`, and run the finished program on it.

R11. In your final response, name the output directory, list the checks you actually ran with their results, and list the section numbers of the modifying provisions your program applies. Do not claim a check or a hand derivation your session does not show.

All comparisons are exact. Do not modify anything under `/app/data`. Do not read anything under `/tests` or `/logs`, and do not look for this task or its answers anywhere outside `/app/data`. The environment is offline; do not install packages.

You have 14400 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
