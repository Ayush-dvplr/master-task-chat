#!/usr/bin/env python3
"""Multi-source spectral covariance repair / reconciliation.

Usage:
    python3 reconcile.py DATA_DIR OUT_DIR

Implements the "Spectral covariance audit contract":
  * discovers inputs by file family inside DATA_DIR (never by fixed paths),
  * applies ledger corrections, per-source/per-period calibration,
    anchor-derived source bias, weighted cross-source reconciliation,
    state-edge propagation, symmetry convergence, diagonal floors and
    off-diagonal caps,
  * writes 24 deterministic JSON artifacts (sorted keys, compact
    separators, one trailing newline).

All arithmetic is done in Decimal at full precision; every ppm field is
rounded to the nearest-even integer part per million exactly once, at
output time.
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
from decimal import Decimal, ROUND_HALF_EVEN, getcontext

getcontext().prec = 60

ONE_M = Decimal(1000000)
BPS = Decimal(10000)
UNIT = Decimal(1)

SERIALIZATION = "json-sort-compact-newline"
ARTIFACT_COUNT = 25

# ---------------------------------------------------------------- helpers


def ppm(value: Decimal) -> int:
    """Nearest-even integer parts-per-million of a decimal value."""
    return int((Decimal(value) * ONE_M).quantize(UNIT, rounding=ROUND_HALF_EVEN))


def ppm_of_ratio(numerator: Decimal, denominator: Decimal) -> int:
    """Nearest-even ppm of an exact ratio of already-ppm-scaled decimals."""
    return int((Decimal(numerator) / Decimal(denominator)).quantize(
        UNIT, rounding=ROUND_HALF_EVEN))


def mean_ppm(values) -> int:
    """Nearest-even ppm mean of full-precision decimal cell values."""
    vals = list(values)
    if not vals:
        return 0
    total = Decimal(0)
    for v in vals:
        total += v
    return ppm(total / Decimal(len(vals)))


def dec(text: str) -> Decimal:
    return Decimal(str(text).strip())


def read_csv(path: str):
    with open(path, "r", newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_json(out_dir: str, name: str, payload) -> str:
    path = os.path.join(out_dir, name)
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
        handle.write("\n")
    return path


# ------------------------------------------------------------- discovery

FAMILIES = {
    "params": re.compile(r"^params\.json$"),
    "priors": re.compile(r"^source_priors\.csv$"),
    "calibration": re.compile(r"^calibration_(?P<source>.+)\.csv$"),
    "anchors": re.compile(r"^anchor_constraints_(?P<source>.+)\.csv$"),
    "edges": re.compile(r"^state_edges_(?P<period>.+)\.csv$"),
    "ledger": re.compile(r"^ledger_corrections_(?P<cohort>.+)\.csv$"),
    "observations": re.compile(
        r"^field_observations_(?P<cohort>.+)_(?P<period>[^_]+)\.csv$"),
}


def discover(data_dir: str):
    """Group the immediate files of DATA_DIR into the contract's families."""
    entries = sorted(
        name for name in os.listdir(data_dir)
        if os.path.isfile(os.path.join(data_dir, name))
    )
    found = {key: [] for key in FAMILIES}
    for name in entries:
        for key, pattern in FAMILIES.items():
            match = pattern.match(name)
            if match:
                found[key].append((name, match.groupdict()))
                break
    return entries, found


# ------------------------------------------------------------------ main


def reconcile(data_dir: str, out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    input_entries, fam = discover(data_dir)

    def path(name: str) -> str:
        return os.path.join(data_dir, name)

    # -- params ---------------------------------------------------------
    diagonal_floor = Decimal(0)
    offdiag_cap = None
    for name, _ in fam["params"]:
        with open(path(name), "r", encoding="utf-8") as handle:
            params = json.load(handle)
        diagonal_floor = dec(params.get("diagonal_floor_ppm", 0)) / ONE_M
        if params.get("offdiag_abs_cap_ppm") is not None:
            offdiag_cap = dec(params["offdiag_abs_cap_ppm"]) / ONE_M

    # -- source priors --------------------------------------------------
    priors_bps = {}
    for name, _ in fam["priors"]:
        for row in read_csv(path(name)):
            priors_bps[row["source"].strip()] = int(row["prior_bps"])

    # -- calibration ----------------------------------------------------
    calibration = {}
    for name, _ in fam["calibration"]:
        for row in read_csv(path(name)):
            key = (row["source"].strip(), row["period"].strip())
            calibration[key] = {
                "scale": dec(row["scale_ppm"]) / ONE_M,
                "offset": dec(row["offset_ppm"]) / ONE_M,
                "stability": dec(row["stability_bps"]) / BPS,
            }

    # -- anchors -> source bias ----------------------------------------
    anchor_diff_sum = {}
    anchor_counts = {}
    for name, _ in fam["anchors"]:
        for row in read_csv(path(name)):
            src = row["source"].strip()
            diff = Decimal(int(row["target_ppm"])) - Decimal(int(row["observed_ppm"]))
            anchor_diff_sum[src] = anchor_diff_sum.get(src, Decimal(0)) + diff
            anchor_counts[src] = anchor_counts.get(src, 0) + 1
    anchors_total = sum(anchor_counts.values())

    source_bias = {}
    source_bias_ppm = {}
    for src, count in anchor_counts.items():
        mean_diff_ppm = anchor_diff_sum[src] / Decimal(count)
        source_bias[src] = mean_diff_ppm / ONE_M
        # Rounding decided on the exact mean of the integer ppm differences.
        source_bias_ppm[src] = int(
            mean_diff_ppm.quantize(UNIT, rounding=ROUND_HALF_EVEN))

    # -- observations ---------------------------------------------------
    observations = {}          # observation_id -> record
    cohort_obs_ids = {}        # cohort -> ordered list of observation ids
    cohorts = set()
    periods = set()
    variables = set()
    sources = set(priors_bps) | set(anchor_counts)

    for name, groups in fam["observations"]:
        for row in read_csv(path(name)):
            obs_id = row["observation_id"].strip()
            cohort = row.get("cohort", groups.get("cohort", "")).strip()
            period = row.get("period", groups.get("period", "")).strip()
            record = {
                "cohort": cohort,
                "period": period,
                "source": row["source"].strip(),
                "var_i": row["var_i"].strip(),
                "var_j": row["var_j"].strip(),
                "raw": dec(row["raw_value"]),
                "reliability": Decimal(int(row["reliability_bps"])),
            }
            observations[obs_id] = record
            cohort_obs_ids.setdefault(cohort, []).append(obs_id)
            cohorts.add(cohort)
            periods.add(period)
            variables.add(record["var_i"])
            variables.add(record["var_j"])
            sources.add(record["source"])

    cohort_order = sorted(cohorts)
    period_order = sorted(periods)
    variable_order = sorted(variables)
    source_order = sorted(sources)

    # -- ledger corrections --------------------------------------------
    ledger_events = []
    voided = set()
    for name, groups in sorted(fam["ledger"], key=lambda item: item[0]):
        for row in read_csv(path(name)):
            obs_id = row["observation_id"].strip()
            action = row["action"].strip().lower()
            if obs_id not in observations or obs_id in voided:
                continue
            if action == "void":
                voided.add(obs_id)
                ledger_events.append({
                    "observation_id": obs_id,
                    "effect": "voided",
                })
            elif action == "replace":
                record = observations[obs_id]
                before = record["raw"]
                after = dec(row["replacement_value"])
                record["raw"] = after
                rel = row.get("replacement_reliability_bps", "")
                if rel is not None and str(rel).strip() != "":
                    record["reliability"] = Decimal(int(str(rel).strip()))
                ledger_events.append({
                    "observation_id": obs_id,
                    "effect": "replaced",
                    "before": float(before),
                    "after": float(after),
                })

    # -- calibration + weighted cross-source reconciliation ------------
    acc = {}   # (cohort, period, var_i, var_j) -> [sum(w*v), sum(w)]
    for obs_id in sorted(observations):
        if obs_id in voided:
            continue
        rec = observations[obs_id]
        src = rec["source"]
        cal = calibration.get((src, rec["period"]))
        if cal is None:
            continue
        corrected = (rec["raw"] * cal["scale"]
                     + cal["offset"]
                     + source_bias.get(src, Decimal(0)))
        weight = ((rec["reliability"] / BPS)
                  * (Decimal(priors_bps.get(src, 0)) / BPS)
                  * cal["stability"])
        key = (rec["cohort"], rec["period"], rec["var_i"], rec["var_j"])
        slot = acc.setdefault(key, [Decimal(0), Decimal(0)])
        slot[0] += weight * corrected
        slot[1] += weight

    estimates = {}
    for key, (wsum, w) in acc.items():
        if w != 0:
            estimates[key] = wsum / w
    observation_cells = len(estimates)

    complete = all(
        (cohort, period, var, var) in estimates
        for cohort in cohort_order
        for period in period_order
        for var in variable_order
    )

    # -- state-edge propagation ----------------------------------------
    edge_residuals = []
    for name, groups in sorted(fam["edges"], key=lambda item: item[0]):
        for row in read_csv(path(name)):
            period = row["period"].strip()
            var_i = row["var_i"].strip()
            var_j = row["var_j"].strip()
            src_key = (row["from_cohort"].strip(), period, var_i, var_j)
            dst_key = (row["to_cohort"].strip(), period, var_i, var_j)
            if src_key not in estimates or dst_key not in estimates:
                continue
            multiplier = dec(row["multiplier_ppm"]) / ONE_M
            delta = dec(row["delta_ppm"]) / ONE_M
            propagated = estimates[src_key] * multiplier + delta
            before = estimates[dst_key]
            after = (before + propagated) / Decimal(2)
            estimates[dst_key] = after
            edge_residuals.append({
                "edge_id": row["edge_id"].strip(),
                "before_ppm": ppm(before),
                "after_ppm": ppm(after),
                "propagated_ppm": ppm(propagated),
            })
    edge_count = len(edge_residuals)

    # -- matrices -------------------------------------------------------
    n = len(variable_order)
    matrices = {}  # cohort -> period -> list[list[Decimal]]
    for cohort in cohort_order:
        matrices[cohort] = {}
        for period in period_order:
            grid = [[Decimal(0) for _ in range(n)] for _ in range(n)]
            for a in range(n):
                for b in range(a, n):
                    vi = variable_order[a]
                    vj = variable_order[b]
                    found = []
                    forward = estimates.get((cohort, period, vi, vj))
                    if forward is not None:
                        found.append(forward)
                    if vi != vj:
                        reverse = estimates.get((cohort, period, vj, vi))
                        if reverse is not None:
                            found.append(reverse)
                    if found:
                        total = Decimal(0)
                        for v in found:
                            total += v
                        value = total / Decimal(len(found))
                    else:
                        value = Decimal(1) if a == b else Decimal(0)
                    if a == b:
                        if value < diagonal_floor:
                            value = diagonal_floor
                    elif offdiag_cap is not None:
                        if value > offdiag_cap:
                            value = offdiag_cap
                        elif value < -offdiag_cap:
                            value = -offdiag_cap
                    grid[a][b] = value
                    grid[b][a] = value
            matrices[cohort][period] = grid

    def upper_cells(cohort, period):
        grid = matrices[cohort][period]
        return [grid[a][b] for a in range(n) for b in range(a, n)]

    matrix_ppm = {
        cohort: {
            period: [[ppm(v) for v in row] for row in matrices[cohort][period]]
            for period in period_order
        }
        for cohort in cohort_order
    }

    # -- summaries ------------------------------------------------------
    all_upper = []
    all_diag = []
    for cohort in cohort_order:
        for period in period_order:
            all_upper.extend(upper_cells(cohort, period))
            grid = matrices[cohort][period]
            all_diag.extend(grid[a][a] for a in range(n))

    artifacts = []

    artifacts.append(write_json(out_dir, "global_summary.json", {
        "cohorts": len(cohort_order),
        "periods": len(period_order),
        "variables": list(variable_order),
        "global_mean_ppm": mean_ppm(all_upper),
        "diagonal_mean_ppm": mean_ppm(all_diag),
        "ledger_events": len(ledger_events),
        "state_edges": edge_count,
    }))

    artifacts.append(write_json(out_dir, "audit_state.json", {
        "source_bias_ppm": {s: source_bias_ppm.get(s, 0) for s in source_order},
        "anchor_counts": {s: anchor_counts.get(s, 0) for s in source_order},
    }))

    artifacts.append(write_json(out_dir, "dependency_checks.json", {
        "observation_cells": observation_cells,
        "calibration_keys": len(calibration),
        "anchors": anchors_total,
        "constraints_applied": edge_count,
        "complete": bool(complete),
    }))

    artifacts.append(write_json(out_dir, "matrix_all.json", matrix_ppm))

    for cohort in cohort_order:
        cells = []
        for period in period_order:
            cells.extend(upper_cells(cohort, period))
        artifacts.append(write_json(out_dir, "cohort_%s.json" % cohort, {
            "cohort": cohort,
            "mean_ppm": mean_ppm(cells),
            "periods": {p: matrix_ppm[cohort][p] for p in period_order},
        }))

    rank_order = sorted(source_order, key=lambda s: (-priors_bps.get(s, 0), s))
    ranks = {s: i + 1 for i, s in enumerate(rank_order)}
    for src in source_order:
        artifacts.append(write_json(out_dir, "source_%s.json" % src, {
            "source": src,
            "bias_ppm": source_bias_ppm.get(src, 0),
            "prior_bps": priors_bps.get(src, 0),
            "relative_rank": ranks[src],
        }))

    for index, var in enumerate(variable_order):
        diag = [matrices[c][p][index][index]
                for c in cohort_order for p in period_order]
        artifacts.append(write_json(out_dir, "variable_%s.json" % var, {
            "variable": var,
            "diagonal_mean_ppm": mean_ppm(diag),
            "diagonal_min_ppm": ppm(min(diag)) if diag else 0,
            "diagonal_max_ppm": ppm(max(diag)) if diag else 0,
        }))

    period_mean = {}
    for period in period_order:
        cells = []
        for cohort in cohort_order:
            cells.extend(upper_cells(cohort, period))
        period_mean[period] = mean_ppm(cells)
    artifacts.append(write_json(out_dir, "convergence_periods.json", {
        "period_mean_ppm": period_mean,
    }))

    max_shift = 0
    for rec in edge_residuals:
        shift = abs(rec["after_ppm"] - rec["before_ppm"])
        if shift > max_shift:
            max_shift = shift
    artifacts.append(write_json(out_dir, "convergence_constraints.json", {
        "max_abs_edge_shift_ppm": max_shift,
        "edge_count": edge_count,
    }))

    radii = {}
    for cohort in cohort_order:
        per_period = []
        for period in period_order:
            grid = matrices[cohort][period]
            best = None
            for row in grid:
                total = Decimal(0)
                for v in row:
                    total += abs(v)
                if best is None or total > best:
                    best = total
            per_period.append(ppm(best if best is not None else Decimal(0)))
        radii[cohort] = per_period
    artifacts.append(write_json(out_dir, "eigen_spectrum.json", {
        "gershgorin_radii_ppm": radii,
    }))

    artifacts.append(write_json(out_dir, "residuals.json", {
        "edge_residuals": edge_residuals,
    }))
    artifacts.append(write_json(out_dir, "ledger_effects.json", {
        "events": ledger_events,
    }))
    artifacts.append(write_json(out_dir, "reproducibility.json", {
        "serialization": SERIALIZATION,
        "input_files": len(input_entries),
        "artifact_count": ARTIFACT_COUNT,
    }))

    sys.stdout.write(
        "wrote %d artifacts to %s\n" % (len(artifacts), out_dir))


def main(argv) -> int:
    if len(argv) != 3:
        sys.stderr.write("usage: reconcile.py DATA_DIR OUT_DIR\n")
        return 2
    reconcile(argv[1], argv[2])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
