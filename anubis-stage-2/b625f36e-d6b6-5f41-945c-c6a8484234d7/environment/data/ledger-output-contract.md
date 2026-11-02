# Ledger output contract

Twenty four deliverables are written under `/app/out`. Every one of them is
written in UTF-8 with Unix line endings and a trailing newline, and no
deliverable carries a timestamp, a hostname or a path taken from the run.

## Serialization

A file whose name ends `.jsonl` carries one JSON object per line, serialized
with sorted keys and with no space after the separators.

A file whose name ends `.json` carries one JSON document, serialized with sorted
keys and an indent of two spaces.

A file whose name ends `.csv` carries a header line naming its columns in the
order this document gives, then one line per record, comma separated, with no
quoting and no escaping. No value written to a `.csv` deliverable contains a
comma.

Integers are written in decimal with no separators and no sign on a positive
value. A negative integer carries a leading minus. Kilowatt hour presentations
are written as a decimal string with exactly the number of decimal places the
resolved rounding configuration gives.

## The deliverables

```
materialize.py               the reusable program
canonical_ledger.jsonl       one object per event
revision_index.jsonl         one object per admitted revision
partition_20310308.csv       through partition_20310315.csv, one per day
partition_manifest.json      one entry per settlement day
rejects.csv                  one line per rejected row
quarantine.jsonl             one object per conflicting row
dedup_ledger.csv             one line per duplicate row
deferred.jsonl               one object per deferred event
unresolvable.json            events and missing batches
entity_resolution.json       one entry per event whose source site was merged
clamp_register.csv           one line per event a clamp reduced
stack_register.csv           one line per admitted restatement delta
restatement_adjustments.csv  one line per changed zone cell
reconciliation.json          the three identities
validation_report.txt        eight lines
run_manifest.json            the run's resolved decisions
```

## Field orders and orderings

`canonical_ledger.jsonl` carries the keys `canonical_site`, `event_key`,
`outcome`, `quantity_kwh`, `quantity_wh`, `revision_class`, `revision_no`,
`settlement_day`, `source_site`, `tariff_band`, `tariff_class` and `zone`. Lines are ordered by
`settlement_day`, then `canonical_site`, then `event_key`, each ascending as a
string. Every event appears exactly once, whatever its outcome.

`revision_index.jsonl` carries the keys `batch_id`, `event_key`, `family`,
`is_canonical`, `quantity_wh`, `revision_class`, `revision_no` and `role`.
`family` is the batch family the revision arrived in, written as one of
`adjustment`, `desk`, `import`, `legacy`, `partner` or `relay`.
`quantity_wh` is the integer watt-hour value of that revision as delivered,
after its pulse multiplier and the single conversion and before any clamp, and
is null when the revision carries no quantity. Lines are
ordered by `event_key`, then `revision_no`, then `revision_class`, then
`family`, each ascending as a string except `revision_no` which ascends as an
integer. Only admitted revisions appear.

Each `partition_YYYYMMDD.csv` carries the columns `sequence_no`, `event_key`,
`canonical_site`, `zone`, `tariff_band`, `outcome`, `quantity_wh`. Rows hold the
events of that settlement day in the order those events occupy in
`canonical_ledger.jsonl`, and `sequence_no` counts those rows from one within
each partition file.

`partition_manifest.json` carries one key `partitions`, an array of eight
objects in ascending `settlement_day`, each with the keys `settlement_day`,
`row_count`, `settled_event_count`, `settled_wh` and `settled_kwh`. `row_count`
is the number of rows the partition file carries.

`rejects.csv` carries the columns `batch_id`, `filename`, `line_no`,
`event_key`, `reason_code`, ordered by `batch_id` then `line_no`. `line_no`
counts lines of the batch body from one, and a header line is not a body line.

`quarantine.jsonl` carries the keys `batch_id`, `event_key`, `line_no`,
`revision_class` and `revision_no`, ordered by `batch_id` then `line_no`.

`dedup_ledger.csv` carries the columns `batch_id`, `line_no`, `event_key`,
`revision_no`, `revision_class`, ordered by `batch_id` then `line_no`.

`deferred.jsonl` carries the keys `canonical_site`, `event_key`,
`revision_no` and `settlement_day`, ordered by `event_key`.

`unresolvable.json` carries the keys `events` and `missing_batches`. Each entry
of `events` carries `canonical_site`, `event_key`, `reason_code` and
`settlement_day`, ordered by `event_key`. Each entry of `missing_batches`
carries `batch_id`, `filename` and `reason_code`, ordered by `batch_id`.

`entity_resolution.json` carries the key `resolutions`, an array whose entries
carry `canonical_site`, `event_key`, `merge_applied` and `source_site`, ordered
by `event_key`. An event appears here when its source site has a row in
`site_merges.csv`, whether or not the merge applied.

`clamp_register.csv` carries the columns `event_key`, `canonical_site`,
`max_interval_wh`, `base_wh`, `base_clamped_wh`, `stack_delta_wh`, `final_wh`
and `clamp_stage`, ordered by `event_key`. An event appears here when a clamp
changed a value, and only then. A clamp changes a value when it lowers a figure
that sits above the ceiling and equally when it raises a figure that sits below
zero, and both count here. `base_wh` is the base revision's watt-hour value
before any clamp, `base_clamped_wh` is that value after the first clamp,
`stack_delta_wh` is the sum of the restatement deltas that were then added, and
`final_wh` is the value after the second clamp. `clamp_stage` is `BASE` when
only the first clamp changed a value, `SUM` when only the second did, and
`BOTH` when each of them did.

`stack_register.csv` carries the columns `event_key`, `revision_no`,
`family`, `delta_wh` and `stack_state`, ordered by `event_key`, then
`revision_no` ascending as an integer, then `family`. One line appears for
every admitted `RESTATEMENT` revision of every event that carries at least
one, whatever the outcome of that event. `delta_wh` is the signed watt-hour
delta the revision delivered, before any clamp, and is zero when the revision
carries no quantity. `stack_state` is drawn from the stack states
`reason-codes.md` closes.

`restatement_adjustments.csv` carries the columns `settlement_day`, `zone`,
`adjustment_kind`, `baseline_settled_wh`, `restated_settled_wh`, `delta_wh`,
`baseline_event_count`, `restated_event_count`, `delta_events`, ordered by
`settlement_day` then `zone`. `adjustment_kind` is `INCREASE` when the watt-hour
difference is above zero, `DECREASE` when it is below zero, and `COUNT_ONLY`
when the watt-hour difference is zero and the event count difference is not.
The rows are drawn from the union of the zone cells the publication states and
the zone cells this run computes, so a cell the publication states and this
run computes nothing for carries a row whose restated figures are zero.

`reconciliation.json` carries the keys `identity_class_partition`,
`identity_partition_rollup` and `identity_restatement`.
`identity_class_partition` carries `admitted`, `conflict`, `duplicate`,
`rejected`, `residual` and `total_rows`, where `total_rows` is the number of
body lines read from in scope batches and `residual` is the sum of the four
dispositions less `total_rows`. `identity_partition_rollup` carries
`ledger_settled_wh`, `partition_settled_wh` and `residual`, where `residual` is
the partition figure less the ledger figure. `identity_restatement` carries
`adjustment_delta_wh`, `baseline_settled_wh`, `restated_settled_wh` and
`residual`, where the first three are summed over every zone cell and `residual`
is the baseline plus the adjustment less the restated figure.

`validation_report.txt` carries exactly eight lines in this order and this
shape, where the last three state the size of the population the run's own
check covered:

```
CLASS_PARTITION residual=<integer>
PARTITION_ROLLUP residual=<integer>
RESTATEMENT residual=<integer>
ROUNDING quantity_dp=<integer> total_dp=<integer>
EXCLUSION policy=<include or omit>
CLAMPED events=<integer>
UNRESOLVED events=<integer>
DISPLACED revisions=<integer>
```

`CLAMPED events` is the number of lines `clamp_register.csv` carries,
`UNRESOLVED events` is the number of entries the `events` array of
`unresolvable.json` carries, and `DISPLACED revisions` is the number of lines
`stack_register.csv` carries whose `stack_state` is `DISPLACED`.

`run_manifest.json` carries the keys `batches_ingested`, `batches_withdrawn`,
`config_resolved`, `config_winner` and `row_exceptions`. `batches_ingested` is
the sorted array of `batch_id` values that were read. `batches_withdrawn` is
the sorted array of `batch_id` values whose status kept them out of scope. A
`filename` that carries more than one manifest row is named by each of its
`batch_id` values, so the same file can be named in both arrays.
`config_resolved` maps every configuration key to its resolved value as a
string. `config_winner` maps every configuration key to the file name of the
layer whose value governed. `row_exceptions` is an array ordered by `batch_id`
whose entries carry `batch_id`, `declared_rows`, `filename` and
`observed_rows`.

## The program

`materialize.py` accepts `--data` naming a corpus directory and `--out` naming a
destination directory, and writing every deliverable other than itself into the
destination. It reads nothing outside the directory `--data` names, and it uses
only the Python standard library.
