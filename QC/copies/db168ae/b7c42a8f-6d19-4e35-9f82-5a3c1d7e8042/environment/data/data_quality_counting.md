# Data-quality counting rules

Every key in `data_quality.json` is a non-negative integer count of a named anomaly, derived at run time from the shipped sources. This document fixes the counting rule for each key. A source row recorded strictly after the admission instant (`valuation_instant` in `derivation_policy.ini`) is dropped before every other stage; it is counted by `late_recorded` and `out_of_horizon_rows` and by no claim-level key. The claim-level keys (`duplicate_identical`, `duplicate_conflicting`, `cross_source_collapsed`, `fold_disambiguated`, `gap_shifted`, `unknown_reinsurer_rows`) look at admitted rows only. The file-level keys (`log_continuations`, `block_unit_rows`, `paren_negatives`, `restatement_gaps`) count what the source files hold as shipped, before admission.

## late_recorded

Count of source rows across the claim transaction logs, the cession bordereau and the fixed-width intake whose `recorded_instant` is strictly after the admission instant. Counted at the row level.

## duplicate_identical

Count of claims that have two or more admitted rows, taken across the three sources together, where every one of those rows carries the same `paid_to_date`. Each such claim counts once.

## duplicate_conflicting

Count of claims that have two or more admitted rows, taken across the three sources together, where those rows carry two or more different `paid_to_date` values. Each such claim counts once.

## cross_source_collapsed

Count of claims that have two or more admitted rows, whether from one source or several, and were therefore collapsed into one governing claim row by the cross-source collapse stage. Each such claim counts once.

## fold_disambiguated

Count of claims where the cross-source collapse stage read two or more different `paid_to_date` values and selected the governing row by the precedence declared under `[precedence]` in `derivation_policy.ini`.

## gap_shifted

Count of ledger rows whose governing `recorded_instant` falls inside no cycle window of `cycle_marks.csv` (after one cycle's `end_instant` and before the next cycle's `start_instant`). Such a row is placed in the first cycle whose `start_instant` follows its instant. Counted at the row level.

## log_continuations

Count of rotated continuation files of the endorsement audit log present in the corpus: each of `endorsement_audit.log.1` and `endorsement_audit.log.2` that is present counts one. The base file `endorsement_audit.log` is not a continuation.

## unknown_reinsurer_rows

Count of ledger rows whose `reinsurer_canonical` is null because the governing `reinsurer_id` resolves to no canonical identifier through `reinsurer_alias_map.csv` and `reinsurer_master.csv`.

## out_of_horizon_rows

Count of source rows dropped by the admission instant, counted exactly as `late_recorded` counts them.

## block_unit_rows

Count of fixed-width intake rows (across `fixed_width_intake_h1.txt` and `fixed_width_intake_h2.txt`) whose `paid_to_date` is a positive whole multiple of one thousand dollars.

## paren_negatives

Count of lines across every CSV and TSV file that contain a parenthesised amount: an opening paren, a digit, further digits or commas, and a closing paren. A line counts once however many such amounts it holds. A parenthesised amount is a negative number of dollars, as `unit_declarations.ini` declares.

## restatement_gaps

Count of claim transaction rows whose `paid_to_date` at column position 4 disagrees with the restatement at column position 7 of the same row. Counted at the row level, across every `claim_tx_H*.csv`.
