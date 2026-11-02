The files under `/app/data` are a deterministic {{CONTAINER_NOUN}} workload from a {{PRODUCER_SYSTEM}}, and your job is to write a fast aggregator that reproduces the reference results exactly while running well under the verifier's own baseline. The written contract is at `/app/data/schema.md`; it describes the workload columns, the scoring rule, the rules file, and the exact shape of every artifact you must emit. The rest of the directory carries the workloads, baselines, thresholds, and profiles the reports draw on, so read the contract and the data together and decide what each figure needs.

Deliver the optimizer at `/app/out/optimize.py`. It must expose a function `aggregate(events_path, rules_path)` returning the result object the contract defines, and it must also run as a script:

```bash
python3 /app/out/optimize.py EVENTS_CSV RULES_JSON
```

printing that same object as canonical JSON. The grader compares your median runtime against a stdlib baseline it builds itself and rewards a genuine relative speedup, so correctness and speed both matter, and there is no fixed time target to hit. A result object looks like this in shape:

```json
{"label":"{{FORMAT_TAG}}-seed","event_count":2,"account_totals":{"A01":10},"region_totals":{"north":10},"kind_totals":{"alpha":10},"flag_counts":{"ok":2},"top_accounts":[["A01",10]],"checksum":12345}
```

Write one scenario artifact per workload at `/app/out/scenario_visible.json`, `/app/out/scenario_peak.json`, `/app/out/scenario_steady.json`, `/app/out/scenario_burst.json`, and `/app/out/scenario_latency.json`, and the roll-up reports at `/app/out/perf_report.json`, `/app/out/bottleneck_analysis.json`, `/app/out/recommendations.json`, and `/app/out/data_quality.json`, each with the keys the contract lists and written as deterministic JSON with sorted keys. Use only the Python standard library, keep every artifact reproducible across runs, and do not read anything under the verifier's own directories.

You have {{AGENT_TIMEOUT_SEC_INT}} seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
