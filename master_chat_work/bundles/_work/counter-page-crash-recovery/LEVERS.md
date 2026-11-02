# LEVERS counter-page-crash-recovery (board 54e38ee)

Levers: LV-WR-1 exact recovered page image from analysis, redo and undo together (wrong: commit-filter replay B1, CLRs left out of redo B2, redo when lsn >= pageLSN B3, redo decided per record B15, pageLSN raised between changes of one record B16, analysis scan from checkpoint_end B8);
LV-WR-2 compensation chains followed through undo_next so each update is undone once, incl. CLRs of earlier interrupted restarts (wrong: prev walk through CLRs B5, CLR-to-CLR undo_next treated as the undo point B12);
LV-WR-3 stated audit sequence (wrong: per-transaction undo order B4, redo from master_lsn B6, textbook END placement and table-order winner ENDs B7, ENDs without an LSN B9).
No secondary lever. Variant losses measured by cost_table.py on the real test books (cost_table.json).

| check | weight | levers | measured loss by variant |
|---|---|---|---|
| artifacts_present | 1 | none | none |
| archive_layout | 3 | none | none |
| package_metadata | 3 | none | none |
| build_report_values | 1 | none | none |
| selftest_truthful | 3 | none | none |
| shipped_core | 3 | LV-WR-1, LV-WR-2, LV-WR-3 | B1, B15, B2, B3, B4, B5, B6, B7, B8, B9, TB |
| shipped_metrics | 3 | LV-WR-1, LV-WR-2, LV-WR-3 | B1, B10, B15, B2, B3, B5, B6, B8, B9 |
| shipped_appended | 3 | LV-WR-1, LV-WR-2, LV-WR-3 | B1, B13, B4, B5, B7, B8, B9, TB |
| shipped_summary | 3 | LV-WR-1, LV-WR-2, LV-WR-3 | B1, B15, B2, B3, B4, B5, B6, B7, B8, B9, TB |
| dense_core | 5 | LV-WR-1, LV-WR-2, LV-WR-3 | B1, B12, B15, B16, B2, B3, B4, B5, B6, B7, B8, B9, TB |
| dense_metrics | 5 | LV-WR-1, LV-WR-2, LV-WR-3 | B1, B10, B12, B15, B16, B2, B3, B5, B6, B8, B9, TB |
| dense_appended | 5 | LV-WR-1, LV-WR-2, LV-WR-3 | B1, B12, B13, B4, B5, B7, B8, B9, TB |
| dense_summary | 5 | LV-WR-1, LV-WR-2, LV-WR-3 | B1, B12, B15, B16, B2, B3, B4, B5, B6, B7, B8, B9, TB |
| restart_core | 5 | LV-WR-1, LV-WR-2, LV-WR-3 | B1, B12, B15, B16, B2, B3, B4, B5, B6, B7, B8, B9, TB |
| restart_metrics | 5 | LV-WR-1, LV-WR-2, LV-WR-3 | B1, B10, B12, B15, B16, B2, B3, B5, B6, B8, B9, TB |
| restart_appended | 5 | LV-WR-1, LV-WR-2, LV-WR-3 | B1, B12, B13, B4, B5, B7, B8, B9, TB |
| restart_summary | 5 | LV-WR-1, LV-WR-2, LV-WR-3 | B1, B12, B15, B16, B2, B3, B4, B5, B6, B7, B8, B9, TB |
| max_core | 5 | LV-WR-1, LV-WR-2, LV-WR-3 | B1, B12, B15, B16, B2, B3, B4, B5, B6, B7, B8, B9, TB |
| max_summary | 3 | LV-WR-1, LV-WR-2, LV-WR-3 | B1, B12, B15, B16, B2, B3, B4, B5, B6, B7, B8, B9, TB |
| max_within_limit | 3 | none | none |
| rejection_core | 5 | LV-WR-1, LV-WR-2, LV-WR-3 | B1, B12, B15, B16, B2, B3, B4, B5, B6, B7, B8, B9, TB |
| relocated_core | 5 | LV-WR-1, LV-WR-2, LV-WR-3 | B1, B12, B15, B16, B2, B3, B4, B5, B6, B7, B8, B9, TB |
| scaled_summary | 5 | LV-WR-1, LV-WR-2, LV-WR-3 | B1, B12, B15, B16, B2, B3, B4, B5, B6, B7, B8, B9, TB |
| missing_input_rejected | 3 | none | none |
| rerun_identical | 3 | none | none |
| negative_hardcoded_sample_answers | -5 | none | none |
| negative_shipped_tests_dropped | -3 | none | none |

Positive weight 95. Weight total per lever (checks some variant of that lever fails): LV-WR-1 75; LV-WR-2 75; LV-WR-3 75.
Non-lever slips measured: B10 latest checkpoint instead of master (13, metrics only), B13 undo_next resolved to an update (13, appended only).
