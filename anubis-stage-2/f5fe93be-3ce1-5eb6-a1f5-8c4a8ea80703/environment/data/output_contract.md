# Output contract

All artifacts are JSON. Dates are ISO `YYYY-MM-DD` broadcast dates, money is integer cents, frames are integer channel frames, and `null` is JSON null. Key order and whitespace carry no meaning; list order is fixed as stated.

## The program

`/app/out/optimize.py` defines `reconcile(data_dir, workload)`, which returns the scenario object of that workload for the data directory given, and runs as

```
python3 /app/out/optimize.py DATA_DIR WORKLOAD
```

printing that same object as one JSON document on standard output and nothing else. `workload` is any section name of `DATA_DIR/channels.ini`. The program reads only files inside `DATA_DIR`, takes every rule parameter from them, writes nothing anywhere, and when a file it needs is missing it exits with a non zero status and prints nothing on standard output.

## Scenario object

```
{
  "workload": "<name>", "channel": "<channel code>",
  "spots": [{"spot_id", "order_line", "broadcast_date", "chain", "disposition"}],
  "deliveries": [{"order_line", "broadcast_date", "committed", "held", "delivered", "billable", "shortfall", "bonus"}],
  "makegoods": [{"order_line", "from_date", "unit", "status", "break_id", "broadcast_date"}],
  "billing": [{"order_line", "advertiser", "gross_cents", "commission_cents", "credit_cents", "net_cents"}],
  "rejects": [{"chain", "seq", "reason"}],
  "totals": {"scheduled_spots", "aired", "committed", "held", "delivered", "billable", "shortfall", "bonus",
             "placed_units", "credited_units", "gross_cents", "commission_cents", "credit_cents", "net_cents"}
}
```

`spots` has one entry per schedule row, ordered by `spot_id`; `order_line` is the governing order line, `chain` is `"A"`, `"B"` or null and `disposition` is one of the seven codes of `reconciliation_rules.md`. `deliveries` is ordered by `order_line` then `broadcast_date`. `makegoods` has one entry per make-good unit, ordered by `order_line`, `from_date` (the shortfall date) and `unit`; `status` is `placed` or `credited`, and `break_id` and `broadcast_date` name the break and its broadcast date, both null for a credited unit. `billing` is ordered by `order_line`. `rejects` has one entry per rejected line, ordered by `chain` then `seq`, with `seq` exactly as logged and `reason` one of the three reason codes. In `totals`, `scheduled_spots` counts the schedule rows, `aired` the `AIRED` spots, `placed_units` and `credited_units` the make-good units by status, and every other key is the sum of that column over `deliveries` or `billing`.

The five scenario artifacts `/app/out/scenario_visible.json`, `/app/out/scenario_peak.json`, `/app/out/scenario_steady.json`, `/app/out/scenario_burst.json` and `/app/out/scenario_latency.json` each hold exactly the object the program prints for `/app/data` and that workload.

## Roll-ups over the five workloads

Workload order is `visible, peak, steady, burst, latency` wherever a list is ordered by workload.

`/app/out/perf_report.json` is `{"workloads", "advertisers", "totals"}`. `workloads` has one row per workload in workload order with `workload` and the sums over that workload's deliveries of `committed, held, delivered, billable, shortfall, bonus` and over its billing of `gross_cents, commission_cents, credit_cents, net_cents`. `advertisers` has one row per advertiser with any deliveries row, ordered by `advertiser`, with `advertiser`, the same ten sums over that advertiser's order lines, and `delivery_bps`. `totals` holds the ten sums over all workloads and `delivery_bps`. `delivery_bps` is `floor(10000 * billable / (billable + shortfall))`, or 0 when the denominator is 0.

`/app/out/bottleneck_analysis.json` is `{"dayparts", "worst"}`. `dayparts` has one row per workload and daypart of its set, in workload order and then daypart set order, with `workload, daypart, breaks` (break count), `capacity_frames` (sum), `occupied_frames` (sum of occupying spot frames), `overbooked_breaks` (breaks whose occupied frames exceed capacity), `makegood_frames` (sum of the needs of units placed there), `spare_frames_after` (sum over breaks of the spare frames left after all placements), `zero_spare_breaks` (breaks left with exactly zero spare frames) and `unplaced_units` (credited units whose order line is in that daypart). `worst` is `{"workload", "daypart"}` of the row with the most unplaced units, ties going to the lower `spare_frames_after` and then to the earlier row.

`/app/out/recommendations.json` is `{"order_lines", "totals"}`. `order_lines` has one row per workload and order line with at least one make-good unit, in workload order and then by `order_line`, with `workload, order_line, advertiser, shortfall_units, placed_units, credited_units, credit_cents, first_break_id, last_break_id`; the last two name the earliest and latest break, by broadcast date, broadcast clock opening count and `break_id`, that received one of its units, or null. `totals` holds the sums of `shortfall_units, placed_units, credited_units, credit_cents`.

`/app/out/data_quality.json` is `{"workloads", "identities"}`. `workloads` has one row per workload in workload order with:

- `workload`;
- `asrun_lines`: `{"A", "B"}`, the non blank lines of each as-run log;
- `duplicate_lines`: lines, over both logs, that repeat an earlier line of the same log byte for byte;
- `rejects`: `{"BAD_TIMECODE", "DROPPED_LABEL", "MISSING_FIELD"}`, rejected lines by reason;
- `reairs`: plays that are not governing plays;
- `retracted_lines`: distinct `type=SPOT` lines removed by admitted retractions;
- `corrections`: `{"admitted", "late", "reattributed_spots"}`, the last counting spots whose governing order line differs from the scheduled one;
- `amendments`: `{"admitted", "late"}` for the workload's order lines;
- `alias_spots`: spots whose scheduled house id or reference play house id passed through at least one alias row while resolving;
- `relock_probes` and `stale_probes`: `chain=B` probes with that lock;
- `dispositions`: the seven disposition codes with their spot counts;
- `partition_residual`: `scheduled_spots` minus the sum of `dispositions`.

`identities` holds three residuals computed from the written artifacts: `billing_net_vs_perf_report` (sum of the five scenario `net_cents` totals minus the `perf_report` total), `credits_vs_recommendations` (sum of the five scenario `credit_cents` totals minus the `recommendations` total) and `unplaced_vs_bottleneck` (sum of the five scenario `credited_units` minus the sum of `unplaced_units` in `bottleneck_analysis`).

## Closing figures

The closing message reports nine counterfactual figures for `/app/data`. Each figure takes every rule as written except the one change it names, is counted per workload, and is reported as three facts: the total over the five workloads, the workload with the largest count (ties to the earlier workload), and that workload's count.

1. `dropframe_as_nondrop`: spots whose disposition changes when every drop frame count of the five workloads (labels, bounds and `DAY` alike) is taken as `((HH * 60 + MM) * 60 + SS) * 30 + FF`, the rejection checks and the prior close settlements unchanged.
2. `start_only_window`: `OUT_OF_WINDOW` spots that would be `AIRED` if window membership asked only whether the reference play's broadcast clock count lies from the daypart start up to but not including its end.
3. `chain_a_always_on_air`: spots whose disposition changes when chain A is taken as on air at every instant and nothing else ever on air.
4. `chain_b_uncorrected`: spots whose disposition changes when every chain B offset is taken as zero.
5. `relock_printed_offset`: spots whose disposition changes when a `RELOCK` probe sets the offset to its printed `offset_frames`.
6. `late_corrections_admitted`: spots whose governing order line changes when corrections recorded at or after the cutoff are admitted too, amendments unchanged.
7. `weekly_clamp_extra_billable`: billable spots gained when billable is taken once per order line over the whole workload as the minimum of its total `delivered` and its total effective commitment.
8. `aliases_undated`: spots whose disposition changes when every alias row applies whatever its `effective_from`.
9. `unconverted_frames`: spots whose disposition changes when a copy's registry `frames` are used as its expected frames on every channel, make-good needs included.
