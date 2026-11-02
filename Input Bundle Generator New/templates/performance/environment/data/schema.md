# Performance workload schema

All files are flat under `/app/data`.

CSV workload columns: `id`, `account`, `kind`, `amount`, `units`, `latency_ms`, `flag`.
Rows carry no region: a row's region is the `region` of its `account` in the
accounts file that `rules.json` names in `accounts_file` (a path relative to the
directory holding `rules.json`; here `accounts.csv`, columns `account,region,tier`).

The optimizer artifact `/app/out/optimize.py` must expose `aggregate(events_path, rules_path)`.
Summary artifacts must be deterministic JSON written with sorted keys.

The score of one row is `amount * units * kind_weight + region_offset -
flag_penalty - latency_ms // 10`, where `kind_weight`, `region_offset`, and
`flag_penalty` come from the `kind_weights`, `region_offsets`, and
`flag_penalties` maps in `rules.json`, looked up by the row's `kind`, its
account's region, and its `flag` (a flag absent from `flag_penalties` has penalty
0). The `aggregate(events_path, rules_path)` return object carries `label` (from
the rules), `event_count`, the maps `account_totals`, `region_totals`, and
`kind_totals` (each summing scores per key, sorted by key), `flag_counts` (rows
per flag, sorted by key), a `top_accounts` list of `[account, score]` pairs sorted
by score descending then account ascending and truncated to the rules `top_n`,
and a rolling `checksum` folded over every row in file order.

The `checksum` starts at zero and, for each row in file order, updates to
`(checksum * 1315423911 + score * position + int(id[1:])) & 0xFFFFFFFF`, where
`score` is the row score defined above, `position` is the 1-based row index
within the file, and `int(id[1:])` is the integer value of the `id` column with
its leading letter dropped. The final value after the last row is the reported
`checksum`.

Each scenario artifact carries `scenario`, `source` (the workload filename),
`result` (the aggregate object above), `metrics`, `thresholds`, `cost` and `plan`.
`metrics` holds `average_score` (total score over event count, rounded to three
places), `top_account`, `top_account_score`, `total_score`, and
`latency_warnings` (rows whose `latency_ms` exceeds `max_latency_warning_ms` from
`thresholds.json`). `thresholds` holds `max_relative_median` and
`max_latency_warning_ms` from `thresholds.json`. `cost` holds
`baseline_median_ms` (this scenario's entry in `median_ms_by_scenario` of
`baseline_metrics.json`), `profile` (the `profile` from `hardware_profile.json`),
and `estimated_credits`: `cpu_unit_cost * event_count + latency_ms_cost *
(sum of latency_ms) + memory_mb_cost * memory_mb`, with the three costs from
`cost_model.json` and `memory_mb` from `hardware_profile.json`, computed in
`Decimal` from the numbers exactly as written in the JSON, quantized half up to six
decimal places and emitted as a string. `plan` holds `group_keys` (the
`recommended_group_keys` from `index_config.json`) and `stages` (the `name` of each
`optimized_stages` entry of `query_plan.json`, in order). The scenarios are
`visible`, `peak`, `steady`, `burst`, and `latency`, drawn from `events.csv`,
`workload_peak.csv`, `workload_steady.csv`, `workload_burst.csv` and
`workload_latency.csv`.

`perf_report.json` carries `ok` (the boolean `true`), `module` (the string
`/app/out/optimize.py`), `benchmark_method` (the fixed string `warmups repeated
median relative to verifier baseline`), `observed_relative_median` (the fixed
contract value `0.35`), `relative_target` (the `max_relative_median` from
`thresholds.json`), `scenario_count` (the integer `5`), `artifact_count` (the
integer `10`), the `scenarios` name list, `baseline_name` (from
`baseline_metrics.json`), and `hardware_profile` (the `profile` from
`hardware_profile.json`). `bottleneck_analysis.json` carries `primary_bottleneck`,
`baseline_complexities`, `optimized_complexities`,
`baseline_median_ms_by_scenario`, and `highest_baseline_scenario`.
`recommendations.json` carries `group_keys` (the `recommended_group_keys` from
`index_config.json`), `top_accounts_order` (the `top_accounts_order` from
`index_config.json`), `materialized_outputs` (the `materialized_outputs` from
`index_config.json`), `estimated_rewrite_fixed_cost` (the `rewrite_fixed_cost`
from `cost_model.json`), and a `recommendations` list holding exactly these three
strings in this order: `Replace repeated per-key scans with one pass over each
CSV.`, `Accumulate account, region, kind, and flag dictionaries together.`, and
`Sort top accounts by score descending and account ascending.`.
`data_quality.json` carries `flat_input_file_count`, an `input_files`
list of `{name, size_bytes}`, and a `scenario_checks` list of
`{scenario, event_count, missing_result_fields, unique_accounts, checksum}`.
