# Data-quality counting rules

Every key in `data_quality.json` is a non-negative integer count of a named anomaly, derived at run time from the shipped sources. This document fixes the counting rule for each key. Every count is taken AFTER admission (rows dropped by the admission instant per `source_manifest.md` are not re-counted here; they appear only as `late_recorded` and `out_of_horizon_rows`).

## late_recorded

Count of all source rows whose `recorded_instant` is strictly after the admission instant `2033-01-15T00:00:00Z`, taken across every file in the corpus.

## duplicate_identical

Count of pairs of admitted rows whose `(claim_ref, _source, lob, accident_year, paid_to_date, incurred, recorded_instant)` tuple is identical. One pair contributes one to the count. Counted after admission.

## duplicate_conflicting

Count of pairs of admitted rows sharing the same `(claim_ref, _source)` whose remaining fields disagree on at least one of `paid_to_date`, `incurred` or `recorded_instant`. One pair contributes one to the count.

## cross_source_collapsed

Count of claims whose admitted rows span two or more distinct `_source` files and were collapsed into one governing claim row by the cross-source collapse stage.

## fold_disambiguated

Count of claims where the cross-source collapse stage read conflicting values for the same field across two or more sources and selected the governing value by the precedence declared in `source_declarations.properties`.

## gap_shifted

Count of admitted claim rows whose `recorded_instant` fell inside the DST transition window (either a missing local hour or a repeated local hour) and whose cycle placement was therefore moved to the adjacent cycle. Counted at the row level, not the claim level.

## log_continuations

Count of lines in the three rotated endorsement audit logs (`endorsement_audit.log`, `endorsement_audit.log.1`, `endorsement_audit.log.2`) that are continuation lines of a preceding log entry (the leading non-whitespace character is not an opening timestamp). The shipped rule is: a line is a continuation iff it does not begin with a four-digit year.

## unknown_reinsurer_rows

Count of admitted rows whose `reinsurer_id` could not be resolved to a canonical identifier through `reinsurer_alias_map.csv` and `reinsurer_master.csv`.

## out_of_horizon_rows

Count of admitted claim rows whose `accident_year` is outside the horizon `AY2023` through `AY2032`, inclusive.

## block_unit_rows

Count of fixed-width intake rows (across `fixed_width_intake_h1.txt` and `fixed_width_intake_h2.txt`) whose `paid_to_date` is a positive integer multiple of one thousand dollars. These are the rows where the writing system declared the reserve in blocks of thousand dollars rather than in cents.

## paren_negatives

Count of lines across every CSV and TSV source whose value column contains a parenthesised negative in the form `(NNNN)` (opening paren, one or more digits possibly with commas, closing paren).

## restatement_gaps

Count of claim transaction rows whose `paid_to_date` at column position 4 disagrees with the restatement at column position 7 of the same row. Counted at the row level, across every `claim_tx_H*.csv`.
