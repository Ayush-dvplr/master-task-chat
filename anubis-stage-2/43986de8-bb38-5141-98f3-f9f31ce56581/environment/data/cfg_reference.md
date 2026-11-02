# Configuration reference

## office.ini

Section `[period]` holds `first_day` and `last_day` (YYYY-MM-DD). Section `[corrections]` holds `cutoff_seq`. Section `[sweep]` holds `parameter_sheet`, the name of the worksheet of sweep_tab.xlsx that governs the sweep of this extract. Section `[overrides]`, when present, holds lines `<district>_<parameter> = <whole number>`, where the parameter is a column name of the parameter sheet.

## sweep_tab.xlsx

A SpreadsheetML workbook as ECMA-376 defines it, whose worksheets each hold a header row `district`, `damping_percent`, `patience`, `round_budget` and one row per district. Only the worksheet that `parameter_sheet` names governs. `damping_percent` is the household's starting damping rate, `patience` its patience and `round_budget` its round budget, each a whole number; patience and round budget are at least 1. Text cells are stored as inline strings.

## Other files

prior_sweep.json holds the moved dollars and exit of each household from an earlier run of the sweep for this period, made before the ledger closed. It is kept for comparison only: the prior_delta.yaml report compares against it. tot_q2.csv holds the totals that the office sent each household for 2026-Q2.
