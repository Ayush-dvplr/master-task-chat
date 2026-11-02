# Backtest rules

Halvard Equipment Finance leases equipment to commercial firms and public
bodies in four regions: North, South, West and East. The champion lease
scorecard is backtested out of time: every lease is scored at a series of
snapshot dates exactly as it could have been scored on that date, and the
score is then judged against what the lease actually did afterwards.

## Snapshots

`backtest_run.toml` gives the first snapshot date, the number of snapshots and
the step in months. Snapshot `i` (from 0) falls `i * snapshot_step_months`
months after the first, on the same day of the month, clamped to the last day
of a shorter month. The as of date of a snapshot is the calendar day before
it. Characteristics describe the lease at the end of its as of date.

## Knowledge instant

The knowledge instant of a lease at a snapshot is the `cut_local_time` of the
snapshot date on the clock of the lease's booking region (`calendar_rules.md`,
`identity_rules.md`), expressed in UTC. Every time stamped record has a
recorded time: `recorded_at`, `created_at`, `status_at`, `received_at`,
`batch_at`, `posted_at`, `loaded_at` or the leading time of an
`ach_returns.log` line. A characteristic of a snapshot may use a record only
when the record is known at the lease's knowledge instant. Whether a record
whose recorded time equals the knowledge instant is known follows production
practice: `snapshot_runs.log` holds, for the production runs of an earlier
year, every record recorded close to a cut and whether that run admitted or
deferred it. The same boundary applies to the watermark.

## Watermark

`watermark_utc` closes the extract. A record recorded after the watermark is a
late record: it is ignored everywhere, as if it were absent, and counted in
`late_records` under the name of its file. Labels (`label_rules.md`) use every
record known at the watermark. Rejects, duplicates and the payment counts of
`data_quality.json` are also stated as known at the watermark.

## Candidates and observations

A lease is a candidate at a snapshot when its state on the as of date, built
from the lease events known at its knowledge instant (`lifecycle_rules.md`), is
`active`. Each candidate becomes either one scored observation or one
unresolved observation. It is unresolved with reason `no_branch` when no
branch history row of the lease is known at the instant with `effective_from`
on or before the as of date, and otherwise with reason `unknown_obligor` when
its obligor reference names no obligor known at the instant
(`identity_rules.md`). `no_branch` is checked first. These are the only two
reasons. An unresolved observation is never scored, labelled or counted in a
regional or segment report.

Every other candidate is scored. Its region is the region of its branch on the
as of date and its segment is its observation segment (`identity_rules.md`).
