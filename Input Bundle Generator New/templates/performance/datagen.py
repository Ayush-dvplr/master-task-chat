"""Seeded input data for the performance archetype.

Every scenario artifact needs every input file, so deleting any one of them
makes the shipped artifacts impossible to reproduce:

  events.csv, workload_<name>.csv   rows: id, account, kind, amount, units, latency_ms, flag
  accounts.csv                      account -> region (rows carry no region)
  rules.json                        weights, offsets, penalties, top_n, label, accounts_file
  thresholds.json                   latency warning limit and relative target
  baseline_metrics.json             per-scenario baseline median
  cost_model.json, hardware_profile.json   the per-scenario credit estimate
  query_plan.json, index_config.json       the per-scenario plan block
"""

from __future__ import annotations

import csv
import io
import json
import random
from pathlib import Path

REGIONS = ["north", "south", "east", "west", "central"]
KINDS = ["alpha", "beta", "gamma", "delta", "epsilon", "zeta"]
FLAGS = ["ok", "review", "hold", "late", "audit"]
WORKLOADS = {"events.csv": (40, 3, 0, 90), "workload_peak.csv": (90, 12, 20, 120), "workload_steady.csv": (35, 5, 20, 60),
             "workload_burst.csv": (120, 3, 10, 40), "workload_latency.csv": (45, 5, 150, 320)}
ALPHABET = "BCDFGHJKLMNPQRSTVWXZ"


def _json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def generate(data_dir: Path, seed: int, subs: dict[str, str]) -> None:
    rng = random.Random(seed)
    for stale in data_dir.iterdir():
        if stale.is_file() and stale.name != "schema.md":
            stale.unlink()

    accounts: list[str] = []
    seen: set[str] = set()
    while len(accounts) < 2200:
        code = "A" + "".join(rng.choice(ALPHABET) for _ in range(4))
        if code not in seen:
            seen.add(code)
            accounts.append(code)
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["account", "region", "tier"])
    for code in accounts:
        writer.writerow([code, rng.choice(REGIONS), rng.choice(["gold", "silver", "bronze"])])
    (data_dir / "accounts.csv").write_text(buf.getvalue(), encoding="utf-8")

    hot = rng.sample(accounts, 40)
    next_id = rng.randint(1000, 9000)
    for name, (amount_mid, units_mid, latency_low, latency_high) in WORKLOADS.items():
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerow(["id", "account", "kind", "amount", "units", "latency_ms", "flag"])
        for _ in range(3700):
            next_id += rng.randint(1, 3)
            account = rng.choice(hot) if rng.random() < 0.25 else rng.choice(accounts)
            writer.writerow([f"e{next_id:07d}", account, rng.choice(KINDS),
                             max(1, int(rng.gauss(amount_mid, amount_mid / 3))), rng.randint(1, units_mid * 2),
                             rng.randint(latency_low, latency_high), rng.choices(FLAGS, weights=[70, 12, 8, 6, 4])[0]])
        (data_dir / name).write_text(buf.getvalue(), encoding="utf-8")

    _json(data_dir / "rules.json", {
        "kind_weights": {k: rng.randint(2, 9) for k in KINDS},
        "region_offsets": {r: rng.randint(5, 30) for r in REGIONS},
        "flag_penalties": {"ok": 0, "review": rng.randint(15, 30), "hold": rng.randint(35, 50), "late": rng.randint(10, 20)},
        "top_n": rng.randint(5, 9),
        "label": f"{subs['{{FORMAT_TAG}}']}-{subs['{{SEED_HEX}}']}",
        "accounts_file": "accounts.csv",
    })
    _json(data_dir / "thresholds.json", {
        "max_relative_median": 0.70,
        "max_missing_values": 0,
        "min_scenarios": 5,
        "min_artifacts": 10,
        "max_latency_warning_ms": rng.choice([180, 200, 220, 240]),
        "required_fields": ["label", "event_count", "account_totals", "region_totals", "kind_totals", "flag_counts", "top_accounts", "checksum"],
    })
    _json(data_dir / "baseline_metrics.json", {
        "baseline_name": rng.choice(["quadratic_group_scans", "per_key_rescans", "nested_group_loops"]),
        "median_ms_by_scenario": {s: round(rng.uniform(180, 420), 2) for s in ["visible", "peak", "steady", "burst", "latency"]},
        "operation_model": {"passes_per_group": "accounts + regions + kinds + flags", "row_scans_per_scenario": 2200 + 5 + 6 + 5},
        "reference_relative_target": 0.70,
    })
    _json(data_dir / "cost_model.json", {
        "cpu_unit_cost": round(rng.uniform(0.0001, 0.0003), 5),
        "memory_mb_cost": round(rng.uniform(0.00001, 0.00004), 6),
        "latency_ms_cost": round(rng.uniform(0.0002, 0.0006), 5),
        "rewrite_fixed_cost": round(rng.uniform(1.0, 3.0), 2),
        "currency": "credits",
    })
    _json(data_dir / "hardware_profile.json", {
        "profile": rng.choice(["standard-ci-small", "shared-ci-medium", "burst-ci-small"]),
        "python": "3.x-stdlib",
        "cpu": "shared-2-vcpu",
        "memory_mb": rng.choice([1024, 2048, 4096]),
        "storage": "ephemeral-ssd",
        "notes": "Use relative repeated medians; do not depend on absolute host speed.",
    })
    _json(data_dir / "query_plan.json", {
        "baseline_stages": [
            {"name": "load_csv", "complexity": "O(n)"},
            {"name": "join_accounts", "complexity": "O(n)"},
            {"name": "scan_accounts", "complexity": "O(n*a)"},
            {"name": "scan_regions", "complexity": "O(n*r)"},
            {"name": "scan_kinds", "complexity": "O(n*k)"},
            {"name": "scan_flags", "complexity": "O(n*f)"},
            {"name": "sort_top_accounts", "complexity": "O(a log a)"},
        ],
        "optimized_stages": [
            {"name": "load_account_regions", "complexity": "O(a)"},
            {"name": "single_pass_accumulate", "complexity": "O(n)"},
            {"name": "sort_top_accounts", "complexity": "O(a log a)"},
        ],
        "primary_bottleneck": "repeated full-row scans for each grouping key",
    })
    _json(data_dir / "index_config.json", {
        "recommended_group_keys": ["account", "region", "kind", "flag"],
        "top_accounts_order": ["score_desc", "account_asc"],
        "checksum_order": "csv_file_order",
        "materialized_outputs": ["scenario_visible", "scenario_peak", "scenario_steady", "scenario_burst", "scenario_latency"],
    })
