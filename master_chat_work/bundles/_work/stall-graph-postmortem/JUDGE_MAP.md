# JUDGE_MAP (harden round 1)

| id | oracle shows it at | test it must not overlap |
|---|---|---|
| R1 | the self-check stage in solution/solve.sh prints `check R1 ok` (per-cell logged bytes from its own join, compared with summary.json by_cell) | shipped_window_summary_matches_the_reference grades the figure; R1 grades only the act of recomputing it |
| R2 | the self-check stage in solution/solve.sh prints `check R2 ok` (own blame settlement, compared with policy_audit.json settled_rung per class) | shipped_policy_audit_matches_the_reference |
| R3 | the self-check stage in solution/solve.sh prints `check R3 ok` (own per-cell counted events and waits, compared with region_*.json) | shipped_cell_reports_match_the_reference |
| R4 | the self-check stage in solution/solve.sh prints `check R4 ok` (own per-segment depth totals, compared with segment_*.json) | shipped_tenant_segment_reports_match_the_reference |
| R5 | the self-check stage in solution/solve.sh prints `check R5 ok` (own set-aside tally per reason, compared with data_quality.json rejections) | shipped_reconciliation_record_matches_the_reference |
| R6 | the self-check stage in solution/solve.sh prints `check R6 ok` (control figures CTRL-A to CTRL-H measured again from the calibration journal, compared with published and reproduced) | none: candidate_search and calibration_comparison are ungraded by tests |
| R7 | the self-check stage in solution/solve.sh prints `check R7 ok` (copy of /app/data with every park bytes_logged raised by 1000, program rerun, total_bytes_logged and residual move by 1000 x counted) | none: tests never alter shipped contents for a judge reason |
| R8 | the self-check stage in solution/solve.sh prints `quarantined lock classes: LCK-A, LCK-B, LCK-C, LCK-E, LCK-F, LCK-H`; the oracle's final answer repeats the list | data_quality settlement.quarantined_classes is graded by _match_post_mortem on hidden windows; R8 grades the response text only |
| R9 | solution/solve.py is the delivered program (named stages, typed records, ValueError on malformed input) | none |
| R10 | negative: solve.sh runs the program and every check after its last copy of the program | none |
| R11 | negative: solve.sh never writes under /app/data (R7 alters a temp copy) | none |
