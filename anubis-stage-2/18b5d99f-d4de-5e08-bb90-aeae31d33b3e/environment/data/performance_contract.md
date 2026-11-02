# Performance contract

The rating aggregate used to be produced by a re-walking implementation: for every
group key it read the whole workload again and redid every step of the rules (identity,
amendments, kind weights, ordering, values, withdrawals and standing) before it summed
that one key. Its results are correct; only its running time is the problem. The
module at /app/out/optimize.py returns exactly the same result object while doing the
work once.

## Figures

- The group keys of a workload are the keys of its account totals, region totals, kind
  totals and flag counts together; `group_keys` is their number.
- `processed_rows` is the number of processed rows of the workload (ledger_rules.md).
- The re-walking implementation reads every processed row once per group key, so the
  baseline row scans of a workload, `baseline_row_scans`, are `group_keys` times
  `processed_rows`.

## Relative target

The speed target is relative to the re-walking implementation on the same host and the
same input, never an absolute time. With warmup calls first and then repeated timed
calls of each implementation, the median cost of `aggregate` must be at most 0.7 of the
median cost of the re-walking implementation on the same extract.

## Running time

Every call of `aggregate` must finish within 60 seconds on any extract in this layout of
up to 15,000 workload rows, 12 kinds and 2,000 lines in each closing journal.

## Measuring

The module carries no clock and no randomness. Measure from a separate script that
picks or builds an extract, makes at least one warmup call and at least three timed
calls of each implementation, and takes the median of each.

## perf_report.json

`perf_report.json` carries exactly these fields:

- `ok`: true.
- `module`: the text `/app/out/optimize.py`.
- `scenario_count`: the number of scenarios in the manifest.
- `scenarios`: their names in manifest order.
- `processed_rows_total`: the processed rows summed over every scenario.
- `relative_target`: 0.7.
- `baseline_median_ns` and `optimized_median_ns`: the two medians of your own timing
  run, as integer nanoseconds.
- `warmup_runs` (at least 1) and `measured_runs` (at least 3): the integer counts that
  run used for each implementation.
- `observed_relative_median`: `optimized_median_ns / baseline_median_ns` rounded to
  three decimals, a number above zero and at most `relative_target`.
- `benchmark_method`: a short sentence naming the median comparison performed.
- `checks_run`: a non-empty list of short non-empty texts, one per check you ran.
