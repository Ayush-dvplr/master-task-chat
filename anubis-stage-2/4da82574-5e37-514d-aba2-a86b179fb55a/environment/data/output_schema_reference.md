# Output schema reference

Twenty four documents are published. Every one is written through
`serialisation_and_digest_contract.md`.

## package.zip

The repaired package. `pyproject.toml` sits at the archive root, the
source tree sits under `src/bcrep`, and the shipped `tests`
directory is carried through unchanged.

## unit_normalisation.json

Keys: `epoch_id`, `workbook_epoch_key`, `live_sheet`,
`frozen_register_revision`, `round_ceiling`, `implausible_ceiling_cu`,
`settlement_floor_cu`, `precedence_levels` as a list of strings in
level order, `units` as a mapping of symbol to scale, `classes` as a
mapping of class to a mapping holding `carry_quantum`,
`conversion_den`, `conversion_num`, `reversal_den` and
`reversal_num`, `ceilings` as a mapping whose key is the revision, a
colon and the class, `event_count` and `normalised_total_cu`. The
normalised total sums the normalised quantity of every canonical
event whose quantity resolved above zero.

## alias_resolution.jsonl

One record per kind and alias pair that carries an in force
crosswalk row, taken from the row that governs the pair, ordered by
kind then alias, each holding `alias`, `canonical`, `kind` and
`in_force_from_revision`.

## canonical_order.csv

Header `position,event_id,sequence,stamp,kind,rank,tiebreak`, one row
per canonical event in canonical order.

## checkpoint_selection.json

Keys: `requested_start`, `requested_end`, `usable` as a sorted list
of identifiers, `selected`, `selected_position`, `watermark_position`
and `rejected` as a list of objects holding `checkpoint_id` and
`reason`, ordered by identifier then reason. An unselected run
publishes an empty `selected` and a zero `selected_position`.

## replay_window.json

Keys: `start_position`, `end_position`, `replayed_count`,
`first_replayed_position`, `last_replayed_position`,
`skipped_before_watermark` and `boundary`, whose value is the string
`start inclusive, end exclusive`. An empty window publishes zero for
the first and last position.

## dependency_closure.json

Keys: `edges_in_force`, `satisfied_by_checkpoint`,
`satisfied_by_window`, `unsatisfied` as a list of objects holding
`event_id` and `reason` ordered by identifier then reason, and
`cycle_members` as a sorted list of identifiers.

## quarantine_ledger.csv

Header `event_id,position,stage,reason_code,detail`, ordered by
position then identifier. `detail` carries the event kind.

## transition_log.jsonl

One record per applied transition in application order, holding
`order`, `event_id`, `position`, `kind`, `station`, `programme`,
`quantity_cu` and `balance_after`. Compensations are not transitions
and do not appear here.

## compensation_register.csv

Header `compensation_id,target_event_id,target_position,disposition,
reversed_cu,applied_order`, ordered by compensation identifier.

## derived_counters.csv

Header `counter,value`, one row per counter in ascending counter
name order: `compensations`, `deferred_admitted`, `granted_cu`,
`grants`, `retired_cu`, `retires`, `reversed_cu`, `spilled_cu`,
`transferred_cu`, `transfers`.

## eligibility_passes.json

Keys: `pass_ceiling`, `deferred_at_first_pass` as a sorted list of
identifiers, `rounds` as a list of objects holding `round`,
`admitted` in admission order and `admitted_count`, `round_count`,
`stable` as a boolean and `deferred_remaining` in queue order.

## final_state.json

Keys: `position`, `balances`, `allotments`, `counters`, `pending`,
`applied` and `reversed`, exactly as stage r13 describes them.

## derived_index.jsonl

One record per surviving station and programme pair holding
`region`, `hub`, `station`, `programme`, `allotment_cu` and `share`.

## checkpoint_reconciliation.json

Keys: `selected`, `declared_digest`, `recomputed_digest`, `matches`,
`archive_rows` as the number of rows the archive's `prior_counters`
table holds across every checkpoint, `counter_deltas` as a mapping of
counter name to the
archive value less the checkpoint value for the counters the archive
carries for the selected checkpoint, `historic_ceiling_total_cu` as
the sum of the ceiling history rows at the revision the selected
register row carries, and `rejected_count`.

## equivalence_report.json

Keys: `comparison_start`, `comparison_end`, `checkpoint_used`,
`from_scratch_digest`, `from_checkpoint_digest`, `identical` and the
two replayed counts `scratch_replayed_count` and
`checkpoint_replayed_count`.

## state_at_event.json

The published state shape at the probe position.

## bounded_replay.json

Keys: `start_position`, `end_position`, `replayed_count` and `state`,
whose value is the published state shape.

## repair_report.json

Keys: `package`, `modules` as the module list the package
expectations name, `stage_ids`, `stage_count`, `entry_point`,
`standard_library_only` and `reason_codes` in screening order.

## selftest.json

Keys: `checks` as a list of objects holding `name` and `value` in
this order: `canonical_order_total`, `checkpoint_digest_matches`,
`window_end_exclusive`, `watermark_replayed_once`,
`scratch_matches_checkpoint`, `targets_reversed_once`,
`pending_after_rounds`, `rounds_run`; then `passed` and `failed`.
Each flag check publishes one when it holds and zero when it does
not; `canonical_order_total`, `pending_after_rounds` and `rounds_run`
publish their count. `passed` is the number of flag checks that
publish one and `failed` the number that publish zero; the three
counts are counted in neither.

## defect_register.md

A title line reading `# Defect register`, a blank line, a three
column table of stage, reason code and meaning under the header row
`| stage | reason code | meaning |` and the separator row
`| --- | --- | --- |`, over the reason codes in force sorted ascending by
code, a blank line, then a line reading `Stages in force: ` followed
by the fourteen stage identifiers separated by a comma and a space.

## verification_notes.md

A title line reading `# Verification notes`, a blank line, then one
line each in this order, a single space between words: `epoch`
and the identifier, `live sheet` and the sheet name, `watermark
position` and the number, `window` then the opening position then
`to` then the closing position then `end exclusive`, `rounds run` and
the number, `stable` and `yes` or `no`, `pending after rounds` and
the number, `compensations applied` and the number, `compensations
void` and the number, `reversed cu` and the number, `spilled cu` and
the number, `settlement floor` and the number, `settlement floor
breaches` and the number, `scratch equals checkpoint` and `yes` or
`no`. Nothing follows that last line but the one trailing newline.

## run_manifest.txt

Two lines: `core` and the digest, then `publication` and the digest.

## summary.json

Keys: `epoch_id`, `live_sheet`, `frozen_register_revision`,
`control_totals`, `stable`, `equivalence_identical` and
`balance_share`. The control totals hold `admitted_in_rounds`,
`allotment_total_cu`, `balance_total_cu`, `canonical_events`,
`checkpoint_position`, `compensations_applied`, `compensations_void`,
`deferred_at_first_pass`, `index_rows`, `pending_remaining`,
`quarantined_events`, `replayed_positions`, `reversed_cu`,
`round_count`, `settlement_floor_breaches`, `spilled_cu`,
`window_end` and `window_start`. The balance share is the total
balance over the total allotment as a ratio at twelve places, and it
publishes an exact zero when the total allotment is zero.

A settlement floor breach is a published station balance standing
strictly below the settlement floor the memo names.
