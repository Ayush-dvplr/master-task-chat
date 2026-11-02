# Source manifest

File role mapping and row layout per source.

## Canonical reinsurer identifier format

Rows carrying a reused reinsurer id across the Q3 cutover (see `reinsurer_master.csv`, which lists multiple rows for the same `reinsurer_id` with the shared `epoch_boundary`) take the canonical form `<reinsurer_id>#1` for records whose `recorded_instant` is strictly before the `epoch_boundary` and `<reinsurer_id>#2` for records whose `recorded_instant` is at or after the `epoch_boundary`. Identifiers with an empty `epoch_boundary` take `#1` throughout.

## Repeated column names in flat files

Where a flat file carries two columns with the same header name, the leftmost occurrence of that header governs. The subsequent occurrence of a repeated header is a restatement column written by a downstream system and is kept only to let an audit cross-check reconstruct what the restater saw; it is not the governing value. A reader that discards the position of each column (for example a `csv.DictReader` or any dict-style reader that overwrites earlier values with later ones for the same key) will silently keep the restatement column and lose the governing one.

This rule applies to every CSV, TSV and fixed-width source. The one declared source where this matters in the shipped corpus is `claim_tx_H01_H04.csv` through `claim_tx_H25_H26.csv`, where the header name `paid_to_date` appears three times (at column positions 4, 5 and 7). The first occurrence (position 4) is the governing cumulative-paid amount. The second occurrence (position 5) carries the incurred figure despite the header string. The third occurrence (position 7) is a later audit restatement that may disagree with position 4. A dict reader keyed by column name keeps only the last occurrence (position 7) and loses the governing column.

The leftmost-header rule can be satisfied either by positional access (reading column index 4 directly) or by first-match header lookup (scanning the header row from left to right and taking the first `paid_to_date` match). Both readings yield the same column; what fails is any reader that silently overwrites earlier matches with later ones for the same header name.

## Row layout per claim transaction log (`claim_tx_H01_H04.csv` ... `claim_tx_H25_H26.csv`)

The seven claim transaction logs share the same column ordering. By position, each data row carries:

- column 0: `claim_ref` (string of the form `CLM-NNNNN`)
- column 1: `reinsurer_id` (raw reinsurer identifier, resolved via `reinsurer_alias_map.csv`)
- column 2: `lob` (one of `wc`, `cal`, `gl`, `cp`, `spec`)
- column 3: `accident_year` (string of the form `AYYYYY`, e.g. `AY2028`)
- column 4: `paid_to_date` (integer dollars; GOVERNING cumulative paid)
- column 5: `incurred` (integer dollars; the header on this column reads `paid_to_date` but the semantics are the incurred amount declared by the writing system)
- column 6: `recorded_instant` (ISO 8601 UTC string ending in Z)
- column 7: `paid_to_date_restated` (integer dollars; the AUDIT RESTATEMENT the writing system published later. A dict reader that keyed by header name would keep this column as `paid_to_date` and lose column 4.)

Column 4 governs. Column 7 is kept for diagnostic reconciliation and feeds the `restatement_gaps` tally in `data_quality.json`.

## Admission by valuation date

Every source file carries a `recorded_instant` on each data row (either a dedicated column or embedded in the row). The valuation date governs admission: a row whose `recorded_instant` is strictly after `2033-01-15T00:00:00Z` is evidence of nothing, including treaty endorsements, retro notices and reserve-state events. The number of such rows dropped during admission is the `late_recorded` tally in `data_quality.json`.

## File roles

- `claim_tx_H*.csv`, seven claim transaction logs (one per booking cycle quarter), carrying every claim movement by cycle. Read by column position per the layout above.
- `cession_q1.tsv` through `cession_q4.tsv`, the cession bordereau, one TSV per quarter, carrying treaty cession amounts.
- `fixed_width_intake_h1.txt` and `fixed_width_intake_h2.txt`, legacy fixed-width intake, two files, parsed by column offsets.
- `claim_master.csv`, one row per `claim_id` with booked LOB, accident year, event id, and segment.
- `claim_adjustment_log.log`, line-based observation log carrying the ALAE allocation observations that settle the ALAE convention.
- `treasury_curve_observations.log`, line-based observation log carrying the discount-curve observations that settle the discount curve reading.
- `curve_marks.csv`, the shipped treasury curve by tenor.
- `cycle_marks.csv`, the semi-monthly cycle boundary clock for H01 through H26.
- `layer_capacity_declarations.csv`, one row per (LOB, cycle), carrying the capacity in dollars.
- `attachment_factors.csv`, the per-layer attachment multipliers (retention, working_excess, cat_excess). The authority is this file, not any value hardcoded in the module.
- `authority_roles.csv`, the underwriter authority roster, one row per (underwriter_id, lob).
- `ceiling_register.csv`, one row per (LOB, cycle), carrying the ceiling in dollars.
- `commitment_agreements.csv`, one row per (reinsurer_id, lob), carrying the minimum dollars honoured.
- `commitment_exceptions.csv`, one row per (reinsurer_id, lob, cycle) where the minimum is waived.
- `priority_register.csv`, one row per LOB with the commitment priority order.
- `reinsurer_master.csv`, one row per reinsurer_id, possibly repeated across the Q3 epoch boundary.
- `reinsurer_alias_map.csv`, one row per alias, mapping to a canonical reinsurer_id.
- `endorsement_circulars_p*.jsonl`, three JSONL files carrying endorsement circulars.
- `endorsement_audit.log`, `endorsement_audit.log.1`, `endorsement_audit.log.2`, three rotated audit logs; a treaty endorsement counts only when its claim_ref appears in one of them.
- `reserve_events_p*.jsonl`, five JSONL files carrying reserve-state events, applied by ascending `version`.
- `retraction_notices.csv`, one row per retracted claim.
- `derivation_policy.ini`, `unit_declarations.ini`, `source_declarations.properties`, `reason_codes.json`, the four declaration files that form the contract alongside the `.md` documents.
- `treaty_handbook.md`, withdrawn; records an older desk practice and governs nothing you deliver.
- `errata_2032-04.md`, the active authority on treaty attachment, replacing the individual-risk reading in `treaty_handbook.md` with clash-cover.
- `output_contract.md`, fixes every output key, every ordering and every spelling.
- `alae_rules.md`, `amendment_rules.md`, `attachment_rules.md`, `discounting_rules.md`, `priority_rules.md`, `allocation_rules.md`, `chain_ladder_rules.md`, `counterfactual_parameters.md`, `data_quality_counting.md`, the rule documents the contract binds to.
- `corpus_index.md`, the top-level index that lists every file in the corpus by category.
