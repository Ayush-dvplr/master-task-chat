# Run audit contract

This archive holds the bookkeeping of one sharded training run: the micro step log,
the shard plan, the restart record, the checkpoint index, the schedule definition and
the evaluation probe log. The bookkeeping is wrong in places. The audit program
rebuilds the optimizer step ledger from the primary evidence and publishes nine
reports.

## Program interface

The program is a single Python file that runs on the standard library only and is
invoked as:

```
python3 optimize.py --data <archive directory> --out <output directory>
```

It reads only files directly inside the archive directory, writes only files directly
inside the output directory, and produces byte identical output for the same archive
every time. It must work on any archive that follows the layouts in this note, not
only on the one shipped here. Archive file names carry no authority: role comes from
content, as described in `policy_ordering.md`.

## Profiles

The profile document lists the named profiles to audit. Each profile produces one
scenario report named `scenario_<profile name>.json`. The profile named `visible`
is the reference pass over the archive. Every profile audits the same archive under
its own overlay of overrides.

## The nine reports

All nine use the serialization in `policy_serialization.md` and carry the field
`body_fingerprint` described there. All numbers are integers.

### scenario_<name>.json

Keys: `document` with value `scenario`, `profile` with the profile name, and

```
accepted_examples            sum of examples over accepted micro records
accepted_records             count of accepted micro records
averaged_metric_milli        the weight averaging result
best_checkpoint              the settled best checkpoint identifier
cursor_drift                 count of checkpoints whose cursor disagrees
discarded_partial_examples   examples lost to discarded accumulation windows
discarded_partial_records    micro records lost to discarded accumulation windows
logged_steps                 count of optimizer steps on the log cadence
matched_probes               count of probes on the probe cadence
missing_probe                cadence steps with no probe
optimizer_steps              count of closed accumulation windows
orphan_probe                 probes off the probe cadence
overflow_skipped             micro records skipped for overflow
rate_digest                  digest of the rate table
rate_first                   rate in milli units at the first optimizer step
rate_last                    rate in milli units at the last optimizer step
rate_max                     largest rate in the table
rate_min                     smallest rate in the table
rate_sum                     sum of every rate in the table
reject_counts                object holding one count per rejection reason
rejected_records             sum of every rejection reason count
rolled_back_examples         examples withdrawn by restart rollback
rolled_back_records          micro records withdrawn by restart rollback
stop_step                    optimizer step where early stopping lands
supersession_cycle           count of supersession chains that revisit a checkpoint
total_records                gross count of logged micro records
trailing_partial_examples    examples left in the open window at end of run
trailing_partial_records     micro records left in the open window at end of run
zero_denominator             count of divisions with a zero denominator
```

`reject_counts` holds every reason named in `policy_validation.md`, including the
reasons whose count is zero.

The rate table is the ordered list of two element lists, one per optimizer step,
holding the step index and the rate in milli units. `rate_digest` is the first
sixteen lowercase hexadecimal characters of the SHA-256 digest of the canonical
serialization of that list.

### perf_report.json

Keys `document` with value `perf_report` and

```
profiles           object keyed by profile name, each holding accepted_examples,
                   accepted_records, averaged_metric_milli, best_checkpoint,
                   optimizer_steps, rate_last and stop_step
deltas_vs_visible  object keyed by every profile name other than visible, each
                   holding accepted_examples_delta and optimizer_steps_delta,
                   both signed differences of that profile minus visible
totals             object holding accepted_examples, accepted_records,
                   optimizer_steps, rejected_records, rolled_back_records and
                   skipped_records summed over every profile
identity_checks    object holding coverage_gap_total, the sum of every profile
                   coverage gap, partition_holds, which is 1 when the partition
                   identity holds for every profile and 0 otherwise, and
                   profiles_checked, the count of audited profiles
```

### bottleneck_analysis.json

Keys `document` with value `bottleneck_analysis` and `profiles`, an object keyed by
profile name. Each profile holds `stages`, `dominant_stage` and `dominant_reason`.
`stages` is a list of objects with keys `stage`, `records_removed` and
`examples_removed`, one entry per stage named in `policy_validation.md`, ordered by
descending `records_removed` and then by ascending stage name. `dominant_stage` is
the stage name of the first entry. `dominant_reason` is the rejection reason with
the largest count, resolved by ascending reason name, or the value `none` when every
rejection count is zero.

### recommendations.json

Keys `document` with value `recommendations`, `per_profile`, an object keyed by
profile name holding that profile's ordered code list, and `codes`, the ordered list
of codes that fired for at least one profile. The rule table and its order live in
`policy_validation.md`.

### data_quality.json

Keys `document` with value `data_quality` and `profiles`, an object keyed by profile
name. Each profile holds `reject_counts`, `overflow_skipped`, `cursor_drift`,
`manifest_conflict`, `supersession_cycle`, `zero_denominator`, a `partition` object
holding `accepted_records`, `holds`, `rejected_records`, `rolled_back_records`,
`skipped_records` and `total_records`, and a `coverage` object holding
`accepted_examples`, `coverage_gap` and `planned_examples`.

## Record layouts

A micro step line carries exactly these keys: `record` with value `micro`,
`sequence`, `owner`, `shard`, `pass_index`, `examples`, `loss_scale`, `overflow`.

A marker line carries exactly these keys: `record` with value `marker`, `sequence`,
`kind`, `phase`. The only kind in use is `phase_open`. Markers are not micro records
and never enter the record partition.

The shard manifest table carries `shard_id`, `owner`, `example_count`, `pass_index`,
`order_key` and `status`. One row describes one shard pass. A shard whose status is
`retired` contributes no accepted work.

The shard move table carries `shard_id`, `from_owner`, `to_owner` and
`effective_sequence`.

The worker roster carries `owner`, `role` and `slots`.

The checkpoint index carries `checkpoint`, `micro_cursor`, `superseded_by` and
`written_at_sequence`. An empty `superseded_by` means the checkpoint still stands.

The holdout table carries `example_id`, `shard_id` and `reason`. The duplicate group
table carries `group_id`, `shard_id`, `example_id` and `keep`.
