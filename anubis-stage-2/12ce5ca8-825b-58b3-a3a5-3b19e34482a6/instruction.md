The files under `/app/data` are a telemetry corpus whose precomputed rollup is
numerically wrong. Recompute the rollup and deliver a fast standard-library
aggregator plus the reports it produces.

`/app/data/schema.md` is the authoritative specification for this corpus: where
any other file disagrees with it, the contract wins. It defines which inputs are
authoritative, how every figure is computed and rounded, and the shape of every
artifact. All arithmetic is exact, integer or exact-decimal, with no tolerances.

Deliver the optimizer at `/app/out/optimize.py`. It must expose
`aggregate(events_path, rules_path)` returning the result object the contract
defines and `resolve_rules(data_dir, scenario)` returning the resolved rules
object the contract defines, and it must also run as a script, `python3 /app/out/optimize.py
EVENTS_FILE RULES_JSON`, printing that same object to standard output as canonical
JSON with sorted keys and nothing else on standard output.

Write one scenario artifact per scenario at `/app/out/scenario_visible.json`,
`/app/out/scenario_peak.json`, `/app/out/scenario_steady.json`,
`/app/out/scenario_burst.json` and `/app/out/scenario_latency.json`, and write
the roll-up reports at `/app/out/perf_report.json`,
`/app/out/bottleneck_analysis.json`, `/app/out/recommendations.json` and
`/app/out/data_quality.json`. Every artifact must carry exactly the keys the
contract lists, must be serialised as JSON with its object keys sorted, and must
come out byte-identical when you run the same work again on the same data.

Your aggregator has to be measurably faster than the rescan baseline the contract
describes, compared as a ratio of repeated medians on one machine rather than as
an absolute time in seconds. The resolved threshold configuration carries the
relative ceiling your aggregator has to stay under, and
`/app/out/perf_report.json` has to report the ratio you actually measured on this
machine rather than a figure you assumed.

Use only the Python standard library. Do not install or import third-party
packages, and do not use the network at any point. Keep the aggregator reading
only from `/app`, the `events_path` and `rules_path` it is handed, and any
temporary scratch files it writes and reads back itself, and keep clock readings,
randomness and process-timing tricks out of the aggregator itself. Do not
hardcode a result that belongs to one particular input; apart from the fixed
strings the contract itself spells out, every figure a run reports has to come
out of the data that run resolved.

When you are done, close with a short written summary that names the files you
resolved as the authoritative inputs, says where you wrote the artifacts, and
states the corpus row, admitted, replayed and quarantined counts plus each
scenario's `event_count`, `checksum`, total `account_totals`, and total
`account_cost_cents` (the sums over accounts), exactly as your artifacts carry
them.

A result object looks like this in shape:

```json
{"label":"ROLLUP","window":[1000,9000],"event_count":2,"account_totals":{"A01":10},"region_totals":{"north":10},"kind_totals":{"alpha":10},"flag_counts":{"ok":2},"account_usage_wh":{"A01":30},"account_energy_kwh":{"A01":0},"account_cost_cents":{"A01":4},"top_accounts":[["A01",10]],"checksum":12345}
```

You have 7200 seconds to complete this task.
Do not cheat by using online solutions or hints specific to this task.
