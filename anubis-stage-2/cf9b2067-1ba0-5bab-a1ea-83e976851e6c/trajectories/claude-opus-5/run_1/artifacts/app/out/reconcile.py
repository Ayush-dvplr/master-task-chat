#!/usr/bin/env python3
"""Spectral covariance audit reconciliation.

Usage: python3 reconcile.py DATA_DIR OUT_DIR

Implements the audit contract: ledger corrections, per-source/per-period
calibration, anchor-derived source bias, weighted cross-source reconciliation,
state-edge propagation, symmetry convergence, diagonal floors, off-diagonal
caps and the collected output artifacts.
"""

import csv
import json
import os
import re
import sys
from decimal import Decimal, ROUND_HALF_EVEN, getcontext

getcontext().prec = 60

MILLION = Decimal(1000000)
TEN_K = Decimal(10000)
SERIALIZATION = "json-sort-compact-newline"
ARTIFACT_COUNT = 25


def round_ppm(value):
    """Nearest-even integer parts per million of a decimal value."""
    return int((Decimal(value) * MILLION).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


def round_even_int(value):
    """Nearest-even integer of an exact decimal quantity already in ppm."""
    return int(Decimal(value).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


def write_json(path, payload):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, sort_keys=True, separators=(",", ":"))
        fh.write("\n")


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return [row for row in csv.DictReader(fh)]


def discover(data_dir):
    """Group the immediate files of DATA_DIR into the contract's families."""
    names = sorted(
        n for n in os.listdir(data_dir) if os.path.isfile(os.path.join(data_dir, n))
    )
    fam = {
        "params": [],
        "priors": [],
        "calibration": {},
        "anchors": {},
        "edges": {},
        "ledger": {},
        "observations": {},
    }
    for name in names:
        stem, ext = os.path.splitext(name)
        path = os.path.join(data_dir, name)
        if ext == ".json" and stem == "params":
            fam["params"].append(path)
            continue
        if ext != ".csv":
            continue
        if stem == "source_priors":
            fam["priors"].append(path)
        elif stem.startswith("calibration_"):
            fam["calibration"][stem[len("calibration_"):]] = path
        elif stem.startswith("anchor_constraints_"):
            fam["anchors"][stem[len("anchor_constraints_"):]] = path
        elif stem.startswith("state_edges_"):
            fam["edges"][stem[len("state_edges_"):]] = path
        elif stem.startswith("ledger_corrections_"):
            fam["ledger"][stem[len("ledger_corrections_"):]] = path
        else:
            match = re.fullmatch(r"field_observations_(.+)_([^_]+)", stem)
            if match:
                fam["observations"][(match.group(1), match.group(2))] = path
    fam["input_files"] = len(names)
    return fam


def load_params(paths):
    params = {}
    for path in paths:
        with open(path, encoding="utf-8") as fh:
            params.update(json.load(fh))
    return params


def compute_bias(anchor_files):
    """Anchor-derived per-source bias: mean of target_ppm - observed_ppm."""
    bias_ppm = {}
    bias_dec = {}
    counts = {}
    anchor_rows = 0
    for source in sorted(anchor_files):
        rows = read_csv(anchor_files[source])
        diffs = [int(r["target_ppm"]) - int(r["observed_ppm"]) for r in rows]
        counts[source] = len(rows)
        anchor_rows += len(rows)
        mean = Decimal(sum(diffs)) / Decimal(len(diffs)) if diffs else Decimal(0)
        bias_ppm[source] = round_even_int(mean)
        bias_dec[source] = mean / MILLION
    return bias_ppm, bias_dec, counts, anchor_rows


def load_ledger(ledger_files):
    ledger = {}
    order = []
    for cohort in sorted(ledger_files):
        for row in read_csv(ledger_files[cohort]):
            obs_id = row["observation_id"]
            ledger[obs_id] = row
            order.append(obs_id)
    return ledger, order


def main(argv):
    if len(argv) != 3:
        print("usage: reconcile.py DATA_DIR OUT_DIR", file=sys.stderr)
        return 2
    data_dir, out_dir = argv[1], argv[2]
    os.makedirs(out_dir, exist_ok=True)

    fam = discover(data_dir)
    params = load_params(fam["params"])
    diag_floor = Decimal(params["diagonal_floor_ppm"]) / MILLION
    offdiag_cap = Decimal(params["offdiag_abs_cap_ppm"]) / MILLION

    priors = {}
    for path in fam["priors"]:
        for row in read_csv(path):
            priors[row["source"]] = int(row["prior_bps"])

    calibration = {}
    for source in sorted(fam["calibration"]):
        for row in read_csv(fam["calibration"][source]):
            calibration[(row["source"], row["period"])] = row

    bias_ppm, bias_dec, anchor_counts, anchor_rows = compute_bias(fam["anchors"])
    ledger, ledger_order = load_ledger(fam["ledger"])

    cohorts = sorted({c for c, _ in fam["observations"]})
    periods = sorted({p for _, p in fam["observations"]})

    observations = []
    variables = set()
    for key in sorted(fam["observations"]):
        for row in read_csv(fam["observations"][key]):
            observations.append(row)
            variables.add(row["var_i"])
            variables.add(row["var_j"])
    variables = sorted(variables)
    sources = sorted(set(priors) | set(fam["calibration"]))

    # Ledger handling: void removes a row, replace substitutes value/reliability.
    by_id = {row["observation_id"]: row for row in observations}
    voided = set()
    replaced = {}
    events = []
    for obs_id in ledger_order:
        row = ledger[obs_id]
        target = by_id.get(obs_id)
        if target is None:
            continue
        action = (row.get("action") or "").strip()
        if action == "void":
            voided.add(obs_id)
            events.append({"observation_id": obs_id, "effect": "voided"})
        elif action == "replace":
            before = Decimal(target["raw_value"])
            after = Decimal(row["replacement_value"])
            replaced[obs_id] = (after, int(row["replacement_reliability_bps"]))
            events.append(
                {
                    "observation_id": obs_id,
                    "effect": "replaced",
                    "before": float(before),
                    "after": float(after),
                }
            )

    # Calibrated, bias-corrected, reliability-weighted local estimates.
    acc = {}
    for row in observations:
        obs_id = row["observation_id"]
        if obs_id in voided:
            continue
        source = row["source"]
        period = row["period"]
        if obs_id in replaced:
            raw, reliability = replaced[obs_id]
        else:
            raw = Decimal(row["raw_value"])
            reliability = int(row["reliability_bps"])
        cal = calibration[(source, period)]
        corrected = (
            raw * Decimal(cal["scale_ppm"]) / MILLION
            + Decimal(cal["offset_ppm"]) / MILLION
            + bias_dec[source]
        )
        weight = (
            Decimal(reliability) / TEN_K
            * Decimal(priors[source]) / TEN_K
            * Decimal(cal["stability_bps"]) / TEN_K
        )
        key = (row["cohort"], period, row["var_i"], row["var_j"])
        num, den = acc.get(key, (Decimal(0), Decimal(0)))
        acc[key] = (num + weight * corrected, den + weight)

    estimates = {k: (n / d) for k, (n, d) in acc.items() if d != 0}
    observation_cells = len(estimates)

    # State-edge propagation.
    edge_records = []
    for period in sorted(fam["edges"]):
        for row in read_csv(fam["edges"][period]):
            src = (row["from_cohort"], row["period"], row["var_i"], row["var_j"])
            dst = (row["to_cohort"], row["period"], row["var_i"], row["var_j"])
            if src not in estimates or dst not in estimates:
                continue
            propagated = (
                estimates[src] * Decimal(row["multiplier_ppm"]) / MILLION
                + Decimal(row["delta_ppm"]) / MILLION
            )
            before = estimates[dst]
            after = (before + propagated) / Decimal(2)
            estimates[dst] = after
            edge_records.append(
                {
                    "edge_id": row["edge_id"],
                    "before_ppm": round_ppm(before),
                    "after_ppm": round_ppm(after),
                    "propagated_ppm": round_ppm(propagated),
                }
            )

    # Matrix assembly with symmetry convergence, floors and caps.
    nvar = len(variables)
    matrices = {}
    for cohort in cohorts:
        for period in periods:
            cells = [[None] * nvar for _ in range(nvar)]
            for i in range(nvar):
                for j in range(i, nvar):
                    vi, vj = variables[i], variables[j]
                    found = []
                    for a, b in ((vi, vj), (vj, vi)):
                        key = (cohort, period, a, b)
                        if key in estimates:
                            found.append(estimates[key])
                            if a == b:
                                break
                    if found:
                        value = sum(found) / Decimal(len(found))
                    else:
                        value = Decimal(1) if i == j else Decimal(0)
                    if i == j:
                        if value < diag_floor:
                            value = diag_floor
                    else:
                        if value > offdiag_cap:
                            value = offdiag_cap
                        elif value < -offdiag_cap:
                            value = -offdiag_cap
                    cells[i][j] = value
                    cells[j][i] = value
            matrices[(cohort, period)] = cells

    def upper(cohort, period):
        cells = matrices[(cohort, period)]
        return [cells[i][j] for i in range(nvar) for j in range(i, nvar)]

    def mean_ppm(values):
        if not values:
            return 0
        return round_ppm(sum(values) / Decimal(len(values)))

    all_upper = [v for c in cohorts for p in periods for v in upper(c, p)]
    all_diag = [
        matrices[(c, p)][i][i] for c in cohorts for p in periods for i in range(nvar)
    ]

    int_matrices = {
        key: [[round_ppm(v) for v in row] for row in cells]
        for key, cells in matrices.items()
    }

    complete = all(
        (c, p, v, v) in estimates
        for c in cohorts
        for p in periods
        for v in variables
    )

    write_json(
        os.path.join(out_dir, "global_summary.json"),
        {
            "cohorts": len(cohorts),
            "periods": len(periods),
            "variables": variables,
            "global_mean_ppm": mean_ppm(all_upper),
            "diagonal_mean_ppm": mean_ppm(all_diag),
            "ledger_events": len(events),
            "state_edges": len(edge_records),
        },
    )

    write_json(
        os.path.join(out_dir, "audit_state.json"),
        {
            "source_bias_ppm": {s: bias_ppm[s] for s in sources},
            "anchor_counts": {s: anchor_counts.get(s, 0) for s in sources},
        },
    )

    write_json(
        os.path.join(out_dir, "dependency_checks.json"),
        {
            "observation_cells": observation_cells,
            "calibration_keys": len(calibration),
            "anchors": anchor_rows,
            "constraints_applied": len(edge_records),
            "complete": complete,
        },
    )

    write_json(
        os.path.join(out_dir, "matrix_all.json"),
        {c: {p: int_matrices[(c, p)] for p in periods} for c in cohorts},
    )

    for cohort in cohorts:
        values = [v for p in periods for v in upper(cohort, p)]
        write_json(
            os.path.join(out_dir, "cohort_%s.json" % cohort),
            {
                "cohort": cohort,
                "mean_ppm": mean_ppm(values),
                "periods": {p: int_matrices[(cohort, p)] for p in periods},
            },
        )

    ranked = sorted(sources, key=lambda s: (-priors[s], s))
    for source in sources:
        write_json(
            os.path.join(out_dir, "source_%s.json" % source),
            {
                "source": source,
                "bias_ppm": bias_ppm[source],
                "prior_bps": priors[source],
                "relative_rank": ranked.index(source) + 1,
            },
        )

    for index, variable in enumerate(variables):
        diag = [matrices[(c, p)][index][index] for c in cohorts for p in periods]
        write_json(
            os.path.join(out_dir, "variable_%s.json" % variable),
            {
                "variable": variable,
                "diagonal_mean_ppm": mean_ppm(diag),
                "diagonal_min_ppm": round_ppm(min(diag)),
                "diagonal_max_ppm": round_ppm(max(diag)),
            },
        )

    write_json(
        os.path.join(out_dir, "convergence_periods.json"),
        {
            "period_mean_ppm": {
                p: mean_ppm([v for c in cohorts for v in upper(c, p)]) for p in periods
            }
        },
    )

    write_json(
        os.path.join(out_dir, "convergence_constraints.json"),
        {
            "max_abs_edge_shift_ppm": max(
                (abs(r["after_ppm"] - r["before_ppm"]) for r in edge_records),
                default=0,
            ),
            "edge_count": len(edge_records),
        },
    )

    write_json(
        os.path.join(out_dir, "eigen_spectrum.json"),
        {
            "gershgorin_radii_ppm": {
                c: [
                    round_ppm(max(sum(abs(v) for v in row) for row in matrices[(c, p)]))
                    for p in periods
                ]
                for c in cohorts
            }
        },
    )

    write_json(os.path.join(out_dir, "residuals.json"), {"edge_residuals": edge_records})
    write_json(os.path.join(out_dir, "ledger_effects.json"), {"events": events})
    write_json(
        os.path.join(out_dir, "reproducibility.json"),
        {
            "serialization": SERIALIZATION,
            "input_files": fam["input_files"],
            "artifact_count": ARTIFACT_COUNT,
        },
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
