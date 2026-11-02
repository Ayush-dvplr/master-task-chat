# Output contract

The program writes nine JSON files. Every file is one JSON object written with
sorted keys and a trailing newline. Dates are `YYYY-MM-DD`, instants are UTC
`YYYY-MM-DDTHH:MM:SSZ`, money is integer cents, and every count, score and
`_ppm` figure is an integer or, where `metrics_rules.md` says so, `null`.
Lists are ordered as stated. An empty group still gets its file and its
entries, with zero counts.

## Shared objects

A totals object counts the scored observations of a group:
`observations`, `excluded`, `bad`, `good`, `indeterminate`, `immature` and
`approved` (excluded observations included in every count).

A metrics object has `population`, `bad`, `good`, `auc_ppm`, `ks_ppm`,
`bad_rate_ppm`, `approved` and `approved_bad` (`metrics_rules.md`).

An observation object has `lease_id`, `snapshot` (the snapshot date),
`obligor_id` (the obligor of the lease at the snapshot), `segment` (the
observation segment, `commercial` or `public`), `scorecard` (the version),
`bins` (characteristic name to bin label, for exactly the characteristics the
version lists), `score`, `approved` (boolean), `exclusion` (a reason or
`null`) and `label`.

## Files

`region_North.json`, `region_South.json`, `region_West.json` and
`region_East.json`: `region`, `totals`, `metrics` and `observations`, the
scored observations of the region ordered by `snapshot` then `lease_id`.

`segment_commercial.json` and `segment_public.json`: `segment`, `totals`,
`metrics`, `by_snapshot` (one entry per snapshot in date order with
`snapshot`, `totals` and `metrics` of the segment's observations of that
snapshot) and `by_scorecard` (version to number of the segment's
observations; versions with none are left out).

`summary.json`: `run_id`; `snapshots` (the snapshot dates in order); `totals`
and `metrics` of every scored observation; `by_region` (region to totals);
`by_segment` (segment to totals); `by_snapshot` (one entry per snapshot in
date order with `snapshot`, `totals` and `auc_ppm`); `score_bands` (one entry
per band of `score_bands.yaml` in file order with `band`, `observations`,
`bad` and `good`, a score falling in a band when it is at or above `lo` and
below `hi`).

`policy_audit.json`:

- `cut_instants`: snapshot date to an object of region to the UTC instant of
  `cut_local_time` on that date on the region's clock.
- `scorecard_usage`: entries `snapshot`, `version`, `observations`, one per
  snapshot and version scoring at least one observation, ordered by snapshot
  then version.
- `exclusions`: entries `lease_id`, `snapshot`, `reason` for every excluded
  observation, ordered by `snapshot` then `lease_id`.
- `quarantined`: entries `lease_id`, `snapshot`, `characteristics` (the sorted
  names of the characteristics in a `quarantined` bin) for every observation
  with at least one, in the same order.
- `holidays`: entries `request_id`, `lease_id`, `months`,
  `first_deferred_instalment` for every governing payment holiday in force at
  the watermark, ordered by `request_id`.
- `merges`: entries `obligor_id`, `resolved_to` for every obligor that a
  `MERGE` event known at the watermark names as the folded obligor, with its
  surviving obligor when every such event applies, ordered by `obligor_id`.

`data_quality.json`:

- `rejects`: entries `source` (file name), `record_id` and `reason`, ordered
  by `source`, then `record_id`, then `reason`, one entry per distinct triple.
  The record id is the `event_id`, the `status_id` (or, for `holiday_limit`,
  the `request_id`), the `item_id`, the `auth_code` or the return id.
- `duplicates`: file name to the number of byte identical repeat lines, for
  files with at least one.
- `late_records`: file name to the number of late records, for files with at
  least one.
- `unresolved`: entries `lease_id`, `snapshot`, `reason`, ordered by
  `snapshot` then `lease_id`.
- `partition`: `candidates`, `scored` and `unresolved` counts.
- `payments`: `lockbox`, `card`, `ach` and `reversed` (`cash_rules.md`).
- `identity_check`: `regions_minus_summary` (the sum of the four regional
  `totals.observations` minus `summary.totals.observations`),
  `segments_minus_summary` (the same for the two segments) and
  `snapshots_minus_summary` (the sum of the `summary.by_snapshot` totals
  observations minus the same), computed from the files written in the same
  run.

## Closing message

The closing message reports ten what-if figures. Each comes from running the
whole backtest again with exactly one reading changed and every other rule
unchanged; none of them is written to any report. Every figure is an exact
integer. An observation "changes" when it is scored in both runs and the named
field differs; "overall" figures are those of `summary.json` `metrics` unless
another object is named.

1. Every knowledge instant taken as `cut_local_time` in UTC on the snapshot
   date, in every region: observations whose score changes, overall
   `auc_ppm`, and `summary.totals.observations`.
2. The watermark used in place of the knowledge instant for candidacy,
   branches, obligors and every characteristic, while incidents still match
   the knowledge instant: observations whose score changes, overall
   `auc_ppm`, and overall `approved`.
3. Every `MERGE` event ignored: observations whose `obligor_id` changes,
   observations whose `active_leases` bin changes, and overall `auc_ppm`.
4. Withdrawn scorecard versions treated as released: observations scored by a
   withdrawn version, `summary.totals.approved`, and overall `auc_ppm`.
5. Both payment tolerances set to 0: overall `bad`, observations whose label
   changes, and overall `auc_ppm`.
6. Every return code reversing its payment: overall `bad`, observations whose
   label changes, and overall `auc_ppm`.
7. Every incident ignored: observations whose score changes, overall
   `auc_ppm`, and overall `ks_ppm`.
8. The governing convention of commercial agreements applied to public
   agreements too: instalments of all leases, on their schedules with the
   holidays in force at the watermark, whose due date changes; observations
   whose label changes; and overall `bad`.
9. No exclusion applied: overall `population`, `auc_ppm` and `ks_ppm`.
10. The two vendor precedence lists swapped between the segments:
    observations whose `bureau` bin changes, `summary.totals.approved`, and
    overall `auc_ppm`.
