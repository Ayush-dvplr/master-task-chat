The flat files in `/app/data` are one collection round of the Regional Household Activity Survey, exported as the collection system emitted them. A written standard and a field-level index ship with the data. The standard is the contract: it defines every rule, every record layout and the exact shape of every report, and it decides which files, and which rows inside them, are in scope.

Take the round through to a disclosure-controlled publication set, and deliver the derivation as a program somebody else can run on the next round. Build it at `/app/out/derive_survey.py`. It runs as `python3 /app/out/derive_survey.py DATA_DIR OUT_DIR`, reads an extract in this layout from the first directory and writes the complete report set into the second in one run. Use only the Python standard library. The program takes its input directory from its first argument, never from a path written into its source, and one run may take at most 120 seconds. Run it on the shipped extract so the reports land in `/app/out`. The program itself will be run again on the shipped extract and on other extracts in the same layout, with different households, benchmarks, settings and sampling structure, and the reports it writes on each are checked against the standard.

The report set is twenty-two files: `/app/out/frame_audit.json`, `/app/out/control_totals.json`, `/app/out/control_margins.tsv`, `/app/out/response_status.json`, `/app/out/design_weights.csv`, `/app/out/adjustment_cells.json`, `/app/out/adjusted_weights.csv`, `/app/out/raking_trace.json`, `/app/out/final_weights.csv`, `/app/out/weight_diagnostics.json`, `/app/out/replicate_design.json`, `/app/out/replicate_summary.csv`, `/app/out/estimates_activity_by_region.csv`, `/app/out/estimates_tenure_by_wquintile.csv`, `/app/out/estimates_hours_by_sector.csv`, `/app/out/estimates_band_transition.csv`, `/app/out/variance_components.json`, `/app/out/cv_screening.json`, `/app/out/primary_suppression.json`, `/app/out/secondary_suppression.json`, `/app/out/disclosure_audit.tsv` and `/app/out/closure_report.json`.

Every report must match the standard exactly, with its field names, field order, row order and serialization, and every figure in it is a whole number. Running the program twice over one extract, or over a copy of it under another directory name, gives the same bytes, and the output does not depend on the order of rows inside an input file.

Two settings of the round, the order the raking margins are applied in and the point at which raking rounds, were never written into the rule files. The published pilot figures shipped with the data settle them, as the standard explains.

Leave the shipped extract under `/app/data` exactly as you found it. Nothing else belongs in `/app/out`: the twenty-two reports and the program are the whole delivery, and a scratch file, a backup copy or a working note left there counts against it. Do not look up solutions online; everything the work needs ships with the data.

When the work is done, finish with a short written summary that answers these questions about the shipped round. None of the answers is written into any report.

1. If the round's raking used the other rounding point, keeping its margin order and iteration limit, what deviation in micro-units would its last iteration leave?
2. Of the other eleven combinations of margin order and rounding point, the best one reproduces how many of the published pilot figures?
3. If the minimum publishable count were two higher, how many cells across the four tables would change between published and suppressed?
4. If the maximum publishable coefficient of variation were 500 basis points lower, how many cells would change between published and suppressed?
5. What would the finished weight total be, in micro-units, if the margins were applied in the order the rule file lists them, with the round's rounding point?
6. If the trim trigger were 100 basis points higher, to how many strata would trimming apply?
7. If the iteration limit were doubled, what is the largest number of iterations any replicate's raking would use?
8. If the secondary cascade were limited to a single pass, how many cells would be suppressed across the four tables?

You have 7200 seconds to complete this task.
