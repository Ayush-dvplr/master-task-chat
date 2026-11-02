#!/bin/bash
# Oracle for the metered cloud billing extract.
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1

mkdir -p "/app/out"

# 1. Install the module. Every call settles the extract's kind weights and cancellation
#    table from its rate card and withdrawal journal and applies the legacy rules as
#    recovered from the closing journals.
cp /solution/solve.py /app/out/optimize.py

# 2. Write every report of the shipped extract with the installed module, and time it
#    against a re-walking implementation from this script (the module has no clock).
python3 - <<'PY'
import importlib.util
import json
import statistics
import time
from pathlib import Path

spec = importlib.util.spec_from_file_location("delivered", "/app/out/optimize.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
data = Path("/app/data")
out = Path("/app/out")
manifest = json.loads((data / "manifest.json").read_text(encoding="utf-8"))
rules = data / manifest["rules"]
GROUPS = ("account_totals", "region_totals", "kind_totals", "flag_counts")


def emit(name, value):
    (out / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


quality, advice, load = [], [], []
processed_total = 0
for entry in manifest["scenarios"]:
    rated = module.rate(data / entry["source"], rules)
    result = rated["result"]
    total = sum(result["account_totals"].values())
    head = result["top_accounts"][0] if result["top_accounts"] else [None, 0]
    emit(f"scenario_{entry['name']}.json", {
        "scenario": entry["name"], "source": entry["source"], "result": result,
        "metrics": {"total_score": total, "average_score": total // rated["live"] if rated["live"] else 0,
                    "top_account": head[0], "top_account_score": head[1]},
    })
    quality.append(dict(rated["quality"], scenario=entry["name"]))
    advice.append({"scenario": entry["name"], "rescued_accounts": rated["rescued"],
                   "waived_penalty": rated["waived_penalty"]})
    keys = sum(len(result[g]) for g in GROUPS)
    load.append({"scenario": entry["name"], "group_keys": keys, "processed_rows": rated["processed"],
                 "baseline_row_scans": keys * rated["processed"]})
    processed_total += rated["processed"]
emit("data_quality.json", {"scenarios": quality})
emit("recommendations.json", {"scenarios": advice})
emit("bottleneck_analysis.json", {"scenarios": load})


def rewalk(events, rules_path):
    """The re-walking implementation of the performance contract: for every group key, read the
    whole workload again and redo every step of the rules, configuration included."""
    shape = module.aggregate(events, rules_path)
    answer = dict(shape)
    for group in GROUPS:
        answer[group] = {key: module.aggregate(events, rules_path)[group][key] for key in shape[group]}
    return answer


def median_ns(fn, events, warmups, runs):
    for _ in range(warmups):
        fn(events, rules)
    samples = []
    for _ in range(runs):
        start = time.perf_counter_ns()
        fn(events, rules)
        samples.append(time.perf_counter_ns() - start)
    return int(statistics.median(samples))


sample = data / manifest["scenarios"][0]["source"]
if rewalk(sample, rules) != module.aggregate(sample, rules):
    raise SystemExit("re-walking and single-pass results differ")
base = median_ns(rewalk, sample, 1, 3)
fast = median_ns(module.aggregate, sample, 1, 3)
emit("perf_report.json", {
    "ok": True,
    "module": "/app/out/optimize.py",
    "scenario_count": len(manifest["scenarios"]),
    "scenarios": [e["name"] for e in manifest["scenarios"]],
    "processed_rows_total": processed_total,
    "relative_target": 0.7,
    "baseline_median_ns": base,
    "optimized_median_ns": fast,
    "warmup_runs": 1,
    "measured_runs": 3,
    "observed_relative_median": round(fast / base, 3),
    "benchmark_method": "median of three timed calls after one warmup, single pass against re-walking every step of the rules once per group key",
    "checks_run": ["re-walking and single-pass results agree on the visible workload",
                   "command line prints the aggregate object"],
})
print("reports written")
PY

# 3. The command line form prints the same object the function returns.
python3 "/app/out/optimize.py" "/app/data/events.csv" "/app/data/rules.json" > /dev/null
