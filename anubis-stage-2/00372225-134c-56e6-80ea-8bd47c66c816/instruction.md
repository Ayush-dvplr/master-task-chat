The files in `/app/data` hold one run of a clinical-assay quality-control recalibration: a stream of per-reading instrument signals for a small analyte panel, the reference tables, the governance inputs, and a complete written specification of how the reconciled recalibration report is worked out. The specification is split across the pipeline contract and the per-stage note files kept next to it in `/app/data`. The method coefficients and governance constants that the calculation depends on are kept in the recalibration spreadsheet and the governance document there, not in any plain-text file. Your job is to read the specification, work out which inputs feed which figure, and reconcile the run into the exact report it describes. Read the pipeline contract and the per-stage notes before you start writing the program. Every figure can be derived from the shipped files, and the work is to derive each one rather than copy it out of any single file.

Write one reusable program at `/app/out/derive_report.py` that reads a run in this layout from a data directory and writes the same reports into an output directory. It should run as `python3 /app/out/derive_report.py DATA_DIR OUT_DIR` and take both directories only from those two arguments, never from a fixed path. Then run it on the shipped run so that these files are written:

- `/app/out/summary.json`, the committed allocation summary
- `/app/out/policy_audit.json`, the reconciliation audit
- `/app/out/data_quality.json`, the objective and digest summary
- `/app/out/panel_analyte_glucose.json`, `/app/out/panel_analyte_calcium.json`, `/app/out/panel_analyte_lactate.json` and `/app/out/panel_analyte_creatinine.json`, the four per-analyte rollups
- `/app/out/matrix_rollup.json` and `/app/out/tier_rollup.json`, the matrix and tier rollups
- `/app/out/analyte_totals.json` and `/app/out/tier_analyte_membership.json`, the analyte totals and the tier membership map
- `/app/out/ordered_reading_index.json` and `/app/out/excluded_readings.json`, the ordered reading index and the excluded reading list
- `/app/out/analyte_committed.csv`, `/app/out/batch_committed.tsv` and `/app/out/matrix_weighted.psv`, the per-analyte totals, the per-batch totals and the per-tier weighted contributions
- `/app/out/carryover_ledger.xml`, `/app/out/objective_summary.yaml`, `/app/out/reconciliation_report.md` and `/app/out/run_status.txt`, the carryover ledger, the objective summary, the reconciliation narrative and the run status line
- `/app/out/provenance_manifest.json`, the provenance manifest

When you finish, state in your closing reply the objective value and the core sha256 digest your run produced, and the directory where you wrote the files.

Rules for the calculation:

- Take the recalibration coefficients only from the live sheet that the run profile selects, and take the five governance constants only from the governance document.
- Treat the files marked superseded as retired and derive nothing from them.
- Exclude the flagged quality-control readings before any ordering or aggregation happens.
- Apply the recalibration stages in the order the contract fixes. The committed per-analyte per-batch result is the base that every other figure is taken from, so one wrong reading of the ordering, the coefficients, the governance constants, the recovery floor, the batch cap, the convergence or the carryover pass shows up as many wrong figures at once.
- Apply the fixed-point rounding at each stage the specification names, not once at the end.
- Take the effective calibration lot as the smaller of the two declared lots.
- Apply the recovery floor before reweighting, and add the matrix shift after the floor clamp.
- Keep every recalibration figure as an exact integer or fixed-point value, because nothing is compared with a tolerance.
- Write every JSON file as compact JSON with sorted keys and a single trailing newline.
- Use only the Python standard library.

Your program will also be run on other runs in this same layout that you have not seen, built from the same rules, so it has to implement the specification in general and not depend on the shipped numbers. Only the paths listed above are collected.

You have 7200 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
