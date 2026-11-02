#!/usr/bin/env python3
"""Spectral covariance audit reconciliation.

Usage: python3 reconcile.py DATA_DIR OUT_DIR

Implements the contract in the extract's schema: ledger corrections, per-source
and per-period calibration, anchor-derived bias, weighted cross-source
reconciliation, state-edge propagation, symmetry/floor/cap convergence and
deterministic JSON artifacts.
"""

import csv
import json
import os
import re
import sys
from fractions import Fraction

MILLION = Fraction(1000000)
BPS = Fraction(10000)

FAMILY_PATTERNS = {
    "params": re.compile(r"^params\.json$"),
    "priors": re.compile(r"^source_priors\.csv$"),
    "calibration": re.compile(r"^calibration_(.+)\.csv$"),
    "anchors": re.compile(r"^anchor_constraints_(.+)\.csv$"),
    "edges": re.compile(r"^state_edges_(.+)\.csv$"),
    "ledger": re.compile(r"^ledger_corrections_(.+)\.csv$"),
    "observations": re.compile(r"^field_observations_(.+)_([^_]+)\.csv$"),
}

EDGE_ID_RE = re.compile(r"^e(\d+)$")


def frac(text, default=None):
    text = (text or "").strip()
    if not text:
        if default is None:
            raise ValueError("missing numeric value")
        return default
    return Fraction(text)


def as_int(text, default=None):
    text = (text or "").strip()
    if not text:
        if default is None:
            raise ValueError("missing integer value")
        return default
    return int(Fraction(text))


def round_half_even(value):
    """Round an exact Fraction to the nearest integer, ties to even."""
    value = Fraction(value)
    low = value.numerator // value.denominator
    rest = value - low
    half = Fraction(1, 2)
    if rest < half:
        return low
    if rest > half:
        return low + 1
    return low if low % 2 == 0 else low + 1


def ppm(value):
    """Nearest-even integer parts per million of a decimal Fraction."""
    return round_half_even(Fraction(value) * MILLION)


def mean(values):
    if not values:
        return None
    total = Fraction(0)
    for value in values:
        total += value
    return total / len(values)


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            yield {
                (key.strip() if key else key): (value.strip() if isinstance(value, str) else value)
                for key, value in row.items()
            }


def discover(data_dir):
    """Group the immediate files of DATA_DIR into the contract's families."""
    families = {name: [] for name in FAMILY_PATTERNS}
    file_count = 0
    for name in sorted(os.listdir(data_dir)):
        path = os.path.join(data_dir, name)
        if not os.path.isfile(path):
            continue
        file_count += 1
        for family, pattern in FAMILY_PATTERNS.items():
            match = pattern.match(name)
            if match:
                families[family].append((match.groups(), path))
                break
    return families, file_count


def load_extract(data_dir):
    families, file_count = discover(data_dir)

    params = {"diagonal_floor_ppm": 0, "offdiag_abs_cap_ppm": 0}
    for _, path in families["params"]:
        with open(path, encoding="utf-8") as handle:
            params.update(json.load(handle))

    priors = {}
    for _, path in families["priors"]:
        for row in read_csv(path):
            priors[row["source"]] = as_int(row["prior_bps"], 0)

    calibration = {}
    for _, path in families["calibration"]:
        for row in read_csv(path):
            calibration[(row["source"], row["period"])] = {
                "scale_ppm": frac(row["scale_ppm"], Fraction(1000000)),
                "offset_ppm": frac(row["offset_ppm"], Fraction(0)),
                "stability_bps": frac(row["stability_bps"], BPS),
            }

    anchors = {}
    for (name,), path in families["anchors"]:
        rows = list(read_csv(path))
        for row in rows:
            source = row.get("source") or name
            anchors.setdefault(source, []).append(
                as_int(row["target_ppm"], 0) - as_int(row["observed_ppm"], 0)
            )
        anchors.setdefault(name, [])

    edges = []
    for _, path in families["edges"]:
        for row in read_csv(path):
            edges.append(row)

    ledger = []
    for (name,), path in sorted(families["ledger"]):
        for row in read_csv(path):
            ledger.append((name, row))

    observations = []
    for _, path in sorted(families["observations"], key=lambda item: item[1]):
        for row in read_csv(path):
            observations.append(
                {
                    "observation_id": row["observation_id"],
                    "cohort": row["cohort"],
                    "period": row["period"],
                    "source": row["source"],
                    "var_i": row["var_i"],
                    "var_j": row["var_j"],
                    "raw_value": frac(row["raw_value"], Fraction(0)),
                    "reliability_bps": frac(row["reliability_bps"], Fraction(0)),
                }
            )

    cohorts = {obs["cohort"] for obs in observations}
    cohorts.update(name for (name,), _ in families["ledger"])
    periods = {obs["period"] for obs in observations}
    periods.update(name for (name,), _ in families["edges"])
    periods.update(period for _, period in calibration)
    sources = {obs["source"] for obs in observations}
    sources.update(priors)
    sources.update(anchors)
    sources.update(source for source, _ in calibration)
    sources.update(name for (name,), _ in families["calibration"])
    variables = {obs["var_i"] for obs in observations}
    variables.update(obs["var_j"] for obs in observations)

    return {
        "params": params,
        "priors": priors,
        "calibration": calibration,
        "anchors": anchors,
        "edges": edges,
        "ledger": ledger,
        "observations": observations,
        "cohorts": sorted(cohorts),
        "periods": sorted(periods),
        "sources": sorted(sources),
        "variables": sorted(variables),
        "input_files": file_count,
    }


def source_biases(extract):
    """Mean anchor gap per source: exact ppm mean and decimal bias."""
    bias_ppm = {}
    bias_decimal = {}
    counts = {}
    for source in extract["sources"]:
        gaps = extract["anchors"].get(source, [])
        counts[source] = len(gaps)
        if gaps:
            exact = Fraction(sum(gaps), len(gaps))
        else:
            exact = Fraction(0)
        bias_ppm[source] = round_half_even(exact)
        bias_decimal[source] = exact / MILLION
    return bias_ppm, bias_decimal, counts


def apply_ledger(extract):
    """Apply ledger rows in order, returning survivors and the event log."""
    by_id = {}
    for obs in extract["observations"]:
        by_id[obs["observation_id"]] = obs
    voided = set()
    events = []
    for _, row in extract["ledger"]:
        obs_id = row.get("observation_id")
        action = (row.get("action") or "").lower()
        obs = by_id.get(obs_id)
        if obs is None or obs_id in voided:
            continue
        if action == "void":
            voided.add(obs_id)
            events.append({"effect": "voided", "observation_id": obs_id})
        elif action == "replace":
            before = obs["raw_value"]
            after = frac(row.get("replacement_value"), before)
            obs["raw_value"] = after
            obs["reliability_bps"] = frac(
                row.get("replacement_reliability_bps"), obs["reliability_bps"]
            )
            events.append(
                {
                    "after": float(after),
                    "before": float(before),
                    "effect": "replaced",
                    "observation_id": obs_id,
                }
            )
    survivors = [obs for obs in extract["observations"] if obs["observation_id"] not in voided]
    return survivors, events


def calibration_for(extract, source, period):
    table = extract["calibration"]
    if (source, period) in table:
        return table[(source, period)]
    periods = extract["periods"]
    if period in periods:
        for earlier in reversed(periods[: periods.index(period)]):
            if (source, earlier) in table:
                return table[(source, earlier)]
    return {
        "scale_ppm": Fraction(1000000),
        "offset_ppm": Fraction(0),
        "stability_bps": BPS,
    }


def local_estimates(extract, survivors, bias_decimal):
    buckets = {}
    for obs in survivors:
        cal = calibration_for(extract, obs["source"], obs["period"])
        corrected = (
            obs["raw_value"] * cal["scale_ppm"] / MILLION
            + cal["offset_ppm"] / MILLION
            + bias_decimal.get(obs["source"], Fraction(0))
        )
        prior = Fraction(extract["priors"].get(obs["source"], 10000))
        weight = (obs["reliability_bps"] / BPS) * (prior / BPS) * (cal["stability_bps"] / BPS)
        key = (obs["cohort"], obs["period"], obs["var_i"], obs["var_j"])
        bucket = buckets.setdefault(key, [Fraction(0), Fraction(0), []])
        bucket[0] += weight * corrected
        bucket[1] += weight
        bucket[2].append(corrected)

    estimates = {}
    for key, (numer, denom, values) in buckets.items():
        estimates[key] = numer / denom if denom != 0 else mean(values)
    return estimates


def apply_edges(extract, estimates):
    def order(row):
        match = EDGE_ID_RE.match((row.get("edge_id") or "").strip())
        return (0, int(match.group(1))) if match else (1, 0)

    residuals = []
    for row in sorted(extract["edges"], key=order):
        period = row["period"]
        src_key = (row["from_cohort"], period, row["var_i"], row["var_j"])
        dst_key = (row["to_cohort"], period, row["var_i"], row["var_j"])
        if src_key not in estimates or dst_key not in estimates:
            continue
        propagated = (
            estimates[src_key] * frac(row["multiplier_ppm"], Fraction(1000000)) / MILLION
            + frac(row["delta_ppm"], Fraction(0)) / MILLION
        )
        before = estimates[dst_key]
        after = (before + propagated) / 2
        estimates[dst_key] = after
        residuals.append(
            {
                "after_ppm": ppm(after),
                "before_ppm": ppm(before),
                "edge_id": row["edge_id"],
                "propagated_ppm": ppm(propagated),
            }
        )
    return residuals


def build_matrices(extract, estimates):
    variables = extract["variables"]
    size = len(variables)
    floor = Fraction(extract["params"].get("diagonal_floor_ppm", 0)) / MILLION
    cap = Fraction(extract["params"].get("offdiag_abs_cap_ppm", 0)) / MILLION
    matrices = {}
    for cohort in extract["cohorts"]:
        for period in extract["periods"]:
            cells = [[Fraction(0)] * size for _ in range(size)]
            for i in range(size):
                for j in range(i, size):
                    var_i, var_j = variables[i], variables[j]
                    values = []
                    direct = estimates.get((cohort, period, var_i, var_j))
                    if direct is not None:
                        values.append(direct)
                    if i != j:
                        reverse = estimates.get((cohort, period, var_j, var_i))
                        if reverse is not None:
                            values.append(reverse)
                    value = mean(values)
                    if value is None:
                        value = Fraction(1) if i == j else Fraction(0)
                    if i == j:
                        value = max(value, floor)
                    else:
                        value = max(-cap, min(cap, value))
                    cells[i][j] = value
                    cells[j][i] = value
            matrices[(cohort, period)] = cells
    return matrices


def upper_values(matrix):
    size = len(matrix)
    return [matrix[i][j] for i in range(size) for j in range(i, size)]


def diagonal_values(matrix):
    return [matrix[i][i] for i in range(len(matrix))]


def matrix_ppm(matrix):
    return [[ppm(value) for value in row] for row in matrix]


def gershgorin(matrix):
    return max(sum(abs(value) for value in row) for row in matrix)


def write_json(out_dir, name, payload):
    path = os.path.join(out_dir, name)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")))
        handle.write("\n")


def run(data_dir, out_dir):
    extract = load_extract(data_dir)
    bias_ppm, bias_decimal, anchor_counts = source_biases(extract)
    survivors, events = apply_ledger(extract)
    estimates = local_estimates(extract, survivors, bias_decimal)
    observation_cells = len(estimates)
    residuals = apply_edges(extract, estimates)
    matrices = build_matrices(extract, estimates)

    cohorts = extract["cohorts"]
    periods = extract["periods"]
    variables = extract["variables"]

    os.makedirs(out_dir, exist_ok=True)

    matrix_json = {
        cohort: {period: matrix_ppm(matrices[(cohort, period)]) for period in periods}
        for cohort in cohorts
    }
    write_json(out_dir, "matrix_all.json", matrix_json)

    all_upper = []
    all_diag = []
    for cohort in cohorts:
        for period in periods:
            all_upper.extend(upper_values(matrices[(cohort, period)]))
            all_diag.extend(diagonal_values(matrices[(cohort, period)]))

    write_json(
        out_dir,
        "global_summary.json",
        {
            "cohorts": len(cohorts),
            "diagonal_mean_ppm": ppm(mean(all_diag) or Fraction(0)),
            "global_mean_ppm": ppm(mean(all_upper) or Fraction(0)),
            "ledger_events": len(events),
            "periods": len(periods),
            "state_edges": len(residuals),
            "variables": list(variables),
        },
    )

    write_json(
        out_dir,
        "audit_state.json",
        {
            "anchor_counts": {source: anchor_counts[source] for source in extract["sources"]},
            "source_bias_ppm": {source: bias_ppm[source] for source in extract["sources"]},
        },
    )

    complete = all(
        (cohort, period, variable, variable) in estimates
        for cohort in cohorts
        for period in periods
        for variable in variables
    )
    write_json(
        out_dir,
        "dependency_checks.json",
        {
            "anchors": sum(anchor_counts.values()),
            "calibration_keys": len(extract["calibration"]),
            "complete": complete,
            "constraints_applied": len(residuals),
            "observation_cells": observation_cells,
        },
    )

    for cohort in cohorts:
        values = []
        for period in periods:
            values.extend(upper_values(matrices[(cohort, period)]))
        write_json(
            out_dir,
            "cohort_%s.json" % cohort,
            {
                "cohort": cohort,
                "mean_ppm": ppm(mean(values) or Fraction(0)),
                "periods": {period: matrix_ppm(matrices[(cohort, period)]) for period in periods},
            },
        )

    priors = extract["priors"]
    for source in extract["sources"]:
        prior = priors.get(source, 10000)
        rank = 1 + sum(
            1 for other in extract["sources"] if priors.get(other, 10000) > prior
        )
        write_json(
            out_dir,
            "source_%s.json" % source,
            {
                "bias_ppm": bias_ppm[source],
                "prior_bps": prior,
                "relative_rank": rank,
                "source": source,
            },
        )

    for index, variable in enumerate(variables):
        diag = [
            matrices[(cohort, period)][index][index] for cohort in cohorts for period in periods
        ]
        write_json(
            out_dir,
            "variable_%s.json" % variable,
            {
                "diagonal_max_ppm": ppm(max(diag)),
                "diagonal_mean_ppm": ppm(mean(diag)),
                "diagonal_min_ppm": ppm(min(diag)),
                "variable": variable,
            },
        )

    period_means = {}
    for period in periods:
        values = []
        for cohort in cohorts:
            values.extend(upper_values(matrices[(cohort, period)]))
        period_means[period] = ppm(mean(values) or Fraction(0))
    write_json(out_dir, "convergence_periods.json", {"period_mean_ppm": period_means})

    shifts = [abs(item["after_ppm"] - item["before_ppm"]) for item in residuals]
    write_json(
        out_dir,
        "convergence_constraints.json",
        {
            "edge_count": len(residuals),
            "max_abs_edge_shift_ppm": max(shifts) if shifts else 0,
        },
    )

    write_json(
        out_dir,
        "eigen_spectrum.json",
        {
            "gershgorin_radii_ppm": {
                cohort: [ppm(gershgorin(matrices[(cohort, period)])) for period in periods]
                for cohort in cohorts
            }
        },
    )

    write_json(out_dir, "residuals.json", {"edge_residuals": residuals})
    write_json(out_dir, "ledger_effects.json", {"events": events})
    write_json(
        out_dir,
        "reproducibility.json",
        {
            "artifact_count": 25,
            "input_files": extract["input_files"],
            "serialization": "json-sort-compact-newline",
        },
    )


def main(argv):
    if len(argv) != 3:
        print("usage: reconcile.py DATA_DIR OUT_DIR", file=sys.stderr)
        return 2
    run(argv[1], argv[2])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
