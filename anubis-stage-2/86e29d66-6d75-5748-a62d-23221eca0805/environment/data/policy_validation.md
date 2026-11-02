# Validation and refusal policy

Every micro record in the ordered stream ends up in exactly one of four classes:
accepted, rejected, skipped or rolled back. The four counts plus nothing else add up to
the total record count, and that identity is reported.

## Rejection reasons, in resolution order

A record is tested against the list below in this exact order and is charged to the
first reason that matches. No record is charged twice and no record is charged to a
later reason when an earlier one applies.

1. `duplicate_sequence`. Two records share a sequence number. The ordering policy says
   which one survives; the other is charged here.
2. `unknown_field`. The record key set differs from the documented micro record key
   set, in either direction. A missing key and an extra key are both this reason.
3. `unknown_shard`. The pair of shard identifier and pass index has no row in the shard
   manifest. A shard that exists at a different pass index is still this reason.
4. `retired_shard`. The manifest row that governs the shard carries status `retired`.
5. `empty_shard`. The effective size of the shard is zero or below.
6. `unknown_owner`. The record owner has no row in the worker roster.
7. `owner_excluded`. The record owner appears in the `excluded_owners` list of the
   profile being audited.
8. `owner_mismatch`. The record owner differs from the owner that the ownership
   timeline resolves for that shard at that sequence.
9. `examples_out_of_range`. The example count is zero or below, or it is larger than the
   effective size of the shard.
10. `bad_loss_scale`. The loss scale is not a power of two, or it is below 64, or it is
    above 65536.

## Effective size

The effective size of a shard is its manifest example count, minus one for every
hold out row naming that shard, minus one for every duplicate group row naming that
shard whose `keep` column is 0. Rows whose `keep` column is 1 do not reduce the size.
Hold out rows and duplicate rows both count even when the same example identifier
appears in both tables.

Worked example. A shard with example count 512, six hold out rows and two duplicate
rows with `keep` 0 has an effective size of 504. A record on that shard with an example
count of 505 is charged to `examples_out_of_range`; a record with 504 is accepted.

## Skips

A record that survives every rejection reason and carries `overflow` equal to 1 is
skipped rather than accepted. It is counted under `overflow_skipped`, its examples are
counted as skipped examples, and it takes no part in the accumulation walk, the step
ledger or the coverage total. A record with `overflow` equal to 0 continues to the
accumulation walk. The overflow flag is tested after the ten reasons, so an overflow
record that also has a bad loss scale is a rejection, not a skip.

## Roll back

Roll back is applied after classification, once per restart, in ascending order of
restart sequence. Look up the resume checkpoint of the restart and take its
`written_at_sequence`. Every record that is currently accepted and whose sequence is
strictly greater than that written sequence and strictly less than the restart sequence
is reclassified as rolled back. A record exactly at the written sequence survives, and
a record exactly at the restart sequence survives. Rolled back records leave the
accepted stream entirely: they contribute no examples, close no window and move no
running state.

## Checkpoint cursor drift

Each row of the checkpoint index claims a `micro_cursor`, the number of accepted records
that existed when that checkpoint was written. Rebuild that number for the profile being
audited by counting accepted records with a sequence less than or equal to the
checkpoint `written_at_sequence`, after roll back has been applied. Every checkpoint
whose claim differs from the rebuilt number raises one `cursor_drift` event. Drift is
counted and reported; it changes no classification.

## Other counted events

* `manifest_conflict`, raised by the ordering policy when manifest rows disagree.
* `supersession_cycle`, raised when a checkpoint supersession chain returns to a
  checkpoint it has already visited. The chain stops at the repeat.
* `zero_denominator`, raised by the arithmetic policy.

## Bottleneck stages

The bottleneck report groups removed records and examples into five stages.

* `validation` is the sum of `duplicate_sequence`, `unknown_field`,
  `unknown_shard`, `retired_shard`, `empty_shard`, `examples_out_of_range` and
  `bad_loss_scale` rejections.
* `ownership` is the sum of `unknown_owner`, `owner_excluded` and
  `owner_mismatch` rejections.
* `rollback` contains the records and examples removed by checkpoint rollback.
* `partial_discard` contains the records and examples discarded from incomplete
  windows at restart boundaries.
* `trailing` contains the records and examples left in an incomplete final window.

Order these stages and choose the dominant stage as specified by the run contract.

## Ordered recommendation rules

Evaluate the following rules in this order for each profile.

1. `align-restart-to-window` when `discarded_partial_records` is greater than zero.
2. `shorten-checkpoint-interval` when `rolled_back_records` is greater than zero.
3. `freeze-shard-moves` when the `owner_mismatch` rejection count is greater than
   zero.
4. `restore-probe-cadence` when `missing_probe` is greater than zero.
5. `retire-stray-probes` when `orphan_probe` is greater than zero.
6. `lower-loss-scale` when `overflow_skipped * 100` is greater than
   `accepted_records * 5`.
7. `pad-final-window` when `trailing_partial_records` is greater than zero.
8. `repair-schedule-spans` when `zero_denominator` is greater than zero.
9. `reconcile-shard-plan` when `coverage_gap` is not zero.

A profile for which no rule fires receives the single code `hold-current-plan`.
The merged `codes` list contains each non-fallback code once, in the table order
above, when that rule fires for at least one profile. When no rule fires for any
profile, the merged list is `["hold-current-plan"]`.

## Identities

Two identities are reported and must hold.

* Partition: total records equals accepted plus rejected plus skipped plus rolled back,
  where rejected is the sum of the ten reason counts.
* Coverage: planned examples is the sum, over every distinct pair of shard and pass
  index in the manifest, of the effective size of that shard, counting a negative
  effective size as zero. The coverage gap is planned examples minus accepted examples
  and carries its sign.
