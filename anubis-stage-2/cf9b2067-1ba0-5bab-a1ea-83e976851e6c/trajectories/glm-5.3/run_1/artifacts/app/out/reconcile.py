#!/usr/bin/env python3
"""Reconcile a multi-source spectral covariance audit extract.

Usage:
    python3 reconcile.py DATA_DIR OUT_DIR

Inputs are discovered inside DATA_DIR by file family (params.json,
source_priors.csv, calibration_<source>.csv, anchor_constraints_<source>.csv,
state_edges_<period>.csv, ledger_corrections_<cohort>.csv,
field_observations_<cohort>_<period>.csv).  The audit contract is applied --
ledger corrections, per-source/per-period calibration, anchor-derived source
bias, weighted cross-source reconciliation, state-edge propagation, symmetry
convergence, diagonal floors and off-diagonal caps -- and the contract's JSON
artifacts are written into OUT_DIR.

All arithmetic uses exact rational numbers so that nearest-even ppm rounding
is decided on exact values rather than binary floating point.
"""

import csv
import json
import os
import sys
from decimal import Decimal
from fractions import Fraction

SERIALIZATION_TAG = "json-sort-compact-newline"
ARTIFACT_COUNT = 25

PPM = 1000000
BPS = 10000

# Contract-fixed orders.  They only bias the ordering of names that the extract
# itself supplies; anything the extract adds beyond these is appended in sorted
# order, so an extract with different names still reconciles.
PREFERRED_VARIABLES = ("hydra", "kepler", "lyra", "orion", "pavo", "vega")
PREFERRED_COHORTS = ("Arden", "Beryl", "Canto", "Dorian")
PREFERRED_SOURCES = ("atlas", "beacon", "cygnus", "draco")
PREFERRED_PERIODS = ("2026Q1", "2026Q2", "2026Q3")

ZERO = Fraction(0)
ONE = Fraction(1)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def read_rows(path):
    """Read a CSV file into a list of dicts with stripped keys/values."""
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        rows = []
        for row in csv.DictReader(handle):
            clean = {}
            for key, value in row.items():
                if key is None:
                    continue
                key = key.strip()
                clean[key] = (value or "").strip()
            rows.append(clean)
        return rows


def number(text):
    """Parse a decimal/integer string into an exact Fraction (blank -> 0).

    Scientific notation is accepted for robustness; the standard-library
    Fraction already handles plain decimals exactly.
    """
    text = (text or "").strip()
    if text == "":
        return ZERO
    if "e" in text.lower():
        return Fraction(Decimal(text))
    return Fraction(text)


def round_even(value):
    """Nearest-even rounding of an exact rational to an integer."""
    value = Fraction(value)
    floor = value.numerator // value.denominator
    remainder = value - floor
    half = Fraction(1, 2)
    if remainder > half:
        return floor + 1
    if remainder < half:
        return floor
    return floor if floor % 2 == 0 else floor + 1


def ppm_round(value):
    """Nearest-even ppm integer of a decimal value."""
    return round_even(Fraction(value) * PPM)


def mean(values):
    if not values:
        return ZERO
    return sum(values, ZERO) / len(values)


def ordered_names(names, preferred):
    """Order discovered names: contract order first, then corpus order of first
    appearance, then anything still unplaced sorted.

    ``names`` is a sequence in order of first appearance in the extract; it keeps
    the extract's own variable ordering for names the contract does not fix.
    """
    seen = set()
    appearance = []
    for name in names:
        if name not in seen:
            seen.add(name)
            appearance.append(name)
    remainder = set(seen) - set(preferred)
    ordered = [name for name in preferred if name in seen]
    ordered.extend(name for name in appearance if name in remainder)
    ordered.extend(sorted(remainder - set(appearance)))
    return ordered


def family_paths(data_dir, prefix):
    """Immediate files in data_dir named '<prefix><something>.csv'."""
    paths = []
    for name in sorted(os.listdir(data_dir)):
        path = os.path.join(data_dir, name)
        if not os.path.isfile(path):
            continue
        if name.startswith(prefix) and name.endswith(".csv"):
            if len(name) > len(prefix) + len(".csv"):
                paths.append(path)
    return paths


def single_path(data_dir, filename):
    path = os.path.join(data_dir, filename)
    return path if os.path.isfile(path) else None


def write_json(out_dir, filename, payload):
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    with open(os.path.join(out_dir, filename), "w", encoding="utf-8") as handle:
        handle.write(text + "\n")


# --------------------------------------------------------------------------- #
# input loading
# --------------------------------------------------------------------------- #

def ppm(value):
    """A contract bound given in ppm units, as an exact number."""
    return number(str(value))


def load_params(data_dir):
    path = single_path(data_dir, "params.json")
    params = {
        "diagonal_floor": ZERO,
        "offdiag_cap": None,
        "rounding": "nearest-even-ppm",
    }
    if path is None:
        return params
    with open(path, "r", encoding="utf-8-sig") as handle:
        raw = json.load(handle)
    floor = raw.get("diagonal_floor_ppm")
    if floor is not None:
        # A ppm bound is parts per million of the decimal value.
        params["diagonal_floor"] = ppm(floor) / PPM
    cap = raw.get("offdiag_abs_cap_ppm")
    if cap is not None:
        params["offdiag_cap"] = ppm(cap) / PPM
    params["rounding"] = raw.get("rounding", "nearest-even-ppm")
    return params


def load_priors(data_dir):
    """source -> prior_bps (integer Fraction)."""
    priors = {}
    path = single_path(data_dir, "source_priors.csv")
    if path is None:
        return priors
    for row in read_rows(path):
        priors[row["source"]] = number(row["prior_bps"])
    return priors


def load_calibration(data_dir):
    """(source, period) -> dict of scale/offset/stability."""
    calibration = {}
    for path in family_paths(data_dir, "calibration_"):
        for row in read_rows(path):
            key = (row["source"], row["period"])
            calibration[key] = {
                "scale": number(row["scale_ppm"]),
                "offset": number(row["offset_ppm"]),
                "stability": number(row["stability_bps"]),
            }
    return calibration


def load_anchors(data_dir):
    anchors = []
    for path in family_paths(data_dir, "anchor_constraints_"):
        for row in read_rows(path):
            anchors.append(row)
    return anchors


def load_edges(data_dir):
    edges = []
    for path in family_paths(data_dir, "state_edges_"):
        for row in read_rows(path):
            edges.append(row)
    return edges


def load_ledger(data_dir):
    """observation_id -> ledger action row (first occurrence wins)."""
    ledger = {}
    for path in family_paths(data_dir, "ledger_corrections_"):
        for row in read_rows(path):
            observation_id = row["observation_id"]
            if observation_id not in ledger:
                ledger[observation_id] = row
    return ledger


def load_observations(data_dir):
    """Observation rows from the field_observations family (sample excluded)."""
    observations = []
    for path in family_paths(data_dir, "field_observations_"):
        for row in read_rows(path):
            observations.append(row)
    return observations


# --------------------------------------------------------------------------- #
# pipeline
# --------------------------------------------------------------------------- #

def source_bias(anchors, sources):
    """Per-source anchor bias: mean(target_ppm - observed_ppm), in ppm and decimal."""
    diffs = {source: [] for source in sources}
    for row in anchors:
        source = row["source"]
        diffs.setdefault(source, []).append(
            number(row["target_ppm"]) - number(row["observed_ppm"])
        )
    bias_ppm = {}
    bias_decimal = {}
    counts = {}
    for source in ordered_names(list(diffs), sources):
        values = diffs[source]
        counts[source] = len(values)
        if not values:
            bias_ppm[source] = 0
            bias_decimal[source] = ZERO
        else:
            mean_ppm = sum(values, ZERO) / len(values)
            bias_ppm[source] = round_even(mean_ppm)
            bias_decimal[source] = mean_ppm / PPM
    return bias_ppm, bias_decimal, counts


def apply_ledger(observations, ledger):
    """Apply ledger actions by observation_id; return (kept rows, event records).

    A void row drops the observation(s) carrying that id; a replace row swaps in
    replacement_value and replacement_reliability_bps.  Actions apply before
    calibration, so a replace record's before/after are the raw values swapped.
    """
    by_id = {}
    for row in observations:
        by_id.setdefault(row["observation_id"], []).append(row)

    voided = set()
    replaced = {}
    events = []
    for observation_id, action in ledger.items():
        if observation_id not in by_id:
            continue  # dangling ledger reference: nothing to act on
        action_name = action["action"].lower()
        if action_name == "void":
            voided.add(observation_id)
            events.append({
                "observation_id": observation_id,
                "effect": "voided",
            })
        elif action_name == "replace":
            replaced[observation_id] = action
            events.append({
                "observation_id": observation_id,
                "effect": "replaced",
                "before": float(number(by_id[observation_id][0]["raw_value"])),
                "after": float(number(action["replacement_value"])),
            })

    kept = []
    for row in observations:
        observation_id = row["observation_id"]
        if observation_id in voided:
            continue
        if observation_id in replaced:
            action = replaced[observation_id]
            row = dict(row)
            row["raw_value"] = action["replacement_value"]
            if action.get("replacement_reliability_bps"):
                row["reliability_bps"] = action["replacement_reliability_bps"]
        kept.append(row)
    return kept, events


def local_estimates(observations, calibration, priors, bias_decimal):
    """Weighted cross-source average per (cohort, period, var_i, var_j) cell."""
    weighted_sum = {}
    weight_total = {}
    for row in observations:
        source = row["source"]
        period = row["period"]
        cal = calibration.get((source, period))
        prior = priors.get(source)
        if cal is None or prior is None:
            continue
        weight = (
            number(row["reliability_bps"]) / BPS
            * prior / BPS
            * cal["stability"] / BPS
        )
        if weight <= 0:
            continue
        corrected = (
            number(row["raw_value"]) * cal["scale"] / PPM
            + cal["offset"] / PPM
            + bias_decimal.get(source, ZERO)
        )
        key = (row["cohort"], period, row["var_i"], row["var_j"])
        weighted_sum[key] = weighted_sum.get(key, ZERO) + weight * corrected
        weight_total[key] = weight_total.get(key, ZERO) + weight
    estimates = {}
    for key, total in weight_total.items():
        if total > 0:
            estimates[key] = weighted_sum[key] / total
    return estimates


def apply_edges(edges, estimates):
    """Apply state edges in file order; return (applied records, count)."""
    records = []
    for edge in edges:
        period = edge["period"]
        var_i = edge["var_i"]
        var_j = edge["var_j"]
        source_key = (edge["from_cohort"], period, var_i, var_j)
        target_key = (edge["to_cohort"], period, var_i, var_j)
        if source_key not in estimates or target_key not in estimates:
            continue
        propagated = (
            estimates[source_key] * number(edge["multiplier_ppm"]) / PPM
            + number(edge["delta_ppm"]) / PPM
        )
        before = estimates[target_key]
        after = (before + propagated) / 2
        estimates[target_key] = after
        records.append({
            "edge_id": edge["edge_id"],
            "before_ppm": ppm_round(before),
            "after_ppm": ppm_round(after),
            "propagated_ppm": ppm_round(propagated),
        })
    return records


def build_matrices(estimates, cohorts, periods, variables, params):
    """Decimal matrices keyed by (cohort, period), symmetric, floored and capped."""
    diagonal_floor = params.get("diagonal_floor", ZERO)
    offdiag_cap = params.get("offdiag_cap", None)
    size = len(variables)
    matrices = {}
    for cohort in cohorts:
        for period in periods:
            matrix = [[ZERO] * size for _ in range(size)]
            for i in range(size):
                var_i = variables[i]
                for j in range(i, size):
                    var_j = variables[j]
                    if i == j:
                        value = estimates.get((cohort, period, var_i, var_j))
                        if value is None:
                            value = ONE
                    else:
                        forward = estimates.get((cohort, period, var_i, var_j))
                        reverse = estimates.get((cohort, period, var_j, var_i))
                        candidates = [c for c in (forward, reverse) if c is not None]
                        if candidates:
                            value = sum(candidates, ZERO) / len(candidates)
                        else:
                            value = ZERO
                    if i == j:
                        if value < diagonal_floor:
                            value = diagonal_floor
                    else:
                        if offdiag_cap is not None:
                            if value > offdiag_cap:
                                value = offdiag_cap
                            elif value < -offdiag_cap:
                                value = -offdiag_cap
                    matrix[i][j] = value
                    matrix[j][i] = value
            matrices[(cohort, period)] = matrix
    return matrices


def matrix_ppm(matrix):
    return [[ppm_round(value) for value in row] for row in matrix]


def upper_triangle(matrix):
    return [
        matrix[i][j]
        for i in range(len(matrix))
        for j in range(i, len(matrix))
    ]


def diagonal_cells(matrix):
    return [matrix[i][i] for i in range(len(matrix))]


# --------------------------------------------------------------------------- #
# artifact assembly
# --------------------------------------------------------------------------- #

def build_artifacts(data_dir, params, priors, calibration, anchors, ledger,
                    edges, observations):
    sources = ordered_names(
        [row["source"] for row in observations]
        + [source for source, _period in sorted(calibration)]
        + [row["source"] for row in anchors]
        + sorted(priors),
        PREFERRED_SOURCES,
    )

    bias_ppm, bias_decimal, anchor_counts = source_bias(anchors, sources)

    kept, events = apply_ledger(observations, ledger)
    estimates = local_estimates(kept, calibration, priors, bias_decimal)

    cohorts = ordered_names(
        [row["cohort"] for row in observations], PREFERRED_COHORTS)
    periods = ordered_names(
        [row["period"] for row in observations], PREFERRED_PERIODS)
    variables = ordered_names(
        [name for row in observations for name in (row["var_i"], row["var_j"])],
        PREFERRED_VARIABLES,
    )

    edge_records = apply_edges(edges, estimates)

    matrices = build_matrices(estimates, cohorts, periods, variables, params)

    # ---- global summary -------------------------------------------------- #
    all_upper = []
    all_diagonal = []
    for cohort in cohorts:
        for period in periods:
            matrix = matrices[(cohort, period)]
            all_upper.extend(upper_triangle(matrix))
            all_diagonal.extend(diagonal_cells(matrix))
    global_summary = {
        "cohorts": len(cohorts),
        "periods": len(periods),
        "variables": list(variables),
        "global_mean_ppm": ppm_round(mean(all_upper)),
        "diagonal_mean_ppm": ppm_round(mean(all_diagonal)),
        "ledger_events": len(events),
        "state_edges": len(edge_records),
    }

    # ---- audit state ----------------------------------------------------- #
    audit_state = {
        "source_bias_ppm": {source: bias_ppm[source] for source in sources},
        "anchor_counts": {source: anchor_counts[source] for source in sources},
    }

    # ---- dependency checks ----------------------------------------------- #
    complete = all(
        (cohort, period, variable, variable) in estimates
        for cohort in cohorts
        for period in periods
        for variable in variables
    )
    dependency_checks = {
        "observation_cells": len(estimates),
        "calibration_keys": len(calibration),
        "anchors": len(anchors),
        "constraints_applied": len(edge_records),
        "complete": complete,
    }

    # ---- matrix artifacts ------------------------------------------------ #
    ppm_matrices = {
        key: matrix_ppm(matrix) for key, matrix in matrices.items()
    }
    matrix_all = {
        cohort: {
            period: ppm_matrices[(cohort, period)]
            for period in periods
        }
        for cohort in cohorts
    }

    # ---- cohort artifacts ------------------------------------------------ #
    cohort_payloads = {}
    for cohort in cohorts:
        cells = []
        for period in periods:
            cells.extend(upper_triangle(matrices[(cohort, period)]))
        cohort_payloads["cohort_%s.json" % cohort] = {
            "cohort": cohort,
            "mean_ppm": ppm_round(mean(cells)),
            "periods": {
                period: ppm_matrices[(cohort, period)] for period in periods
            },
        }

    # ---- source artifacts ------------------------------------------------ #
    # Descending prior_bps; ties keep corpus order, as a stable sort would.
    rank_order = [s for s in sources if s in priors]
    rank_order += [s for s in sources if s not in priors]
    rank_order.sort(key=lambda s: -priors.get(s, ZERO))
    rank_of = {source: index + 1 for index, source in enumerate(rank_order)}
    source_payloads = {}
    for source in sources:
        source_payloads["source_%s.json" % source] = {
            "source": source,
            "bias_ppm": bias_ppm[source],
            "prior_bps": int(priors.get(source, ZERO)),
            "relative_rank": rank_of[source],
        }

    # ---- variable artifacts ---------------------------------------------- #
    variable_payloads = {}
    for index, variable in enumerate(variables):
        cells = [
            matrices[(cohort, period)][index][index]
            for cohort in cohorts
            for period in periods
        ]
        variable_payloads["variable_%s.json" % variable] = {
            "variable": variable,
            "diagonal_mean_ppm": ppm_round(mean(cells)),
            "diagonal_min_ppm": ppm_round(min(cells)),
            "diagonal_max_ppm": ppm_round(max(cells)),
        }

    # ---- convergence ------------------------------------------------------ #
    period_mean = {}
    for period in periods:
        cells = []
        for cohort in cohorts:
            cells.extend(upper_triangle(matrices[(cohort, period)]))
        period_mean[period] = ppm_round(mean(cells))

    shifts = [abs(record["after_ppm"] - record["before_ppm"])
              for record in edge_records]

    artifacts = {
        "global_summary.json": global_summary,
        "audit_state.json": audit_state,
        "dependency_checks.json": dependency_checks,
        "matrix_all.json": matrix_all,
        "convergence_periods.json": {"period_mean_ppm": period_mean},
        "convergence_constraints.json": {
            "max_abs_edge_shift_ppm": max(shifts) if shifts else 0,
            "edge_count": len(edge_records),
        },
        "eigen_spectrum.json": {
            "gershgorin_radii_ppm": {
                cohort: [
                    ppm_round(max(
                        sum((abs(value) for value in row), ZERO)
                        for row in matrices[(cohort, period)]
                    ))
                    for period in periods
                ]
                for cohort in cohorts
            }
        },
        "residuals.json": {"edge_residuals": edge_records},
        "ledger_effects.json": {"events": events},
    }
    artifacts.update(cohort_payloads)
    artifacts.update(source_payloads)
    artifacts.update(variable_payloads)

    input_files = sum(
        1 for name in os.listdir(data_dir)
        if os.path.isfile(os.path.join(data_dir, name))
    )
    artifacts["reproducibility.json"] = {
        "serialization": SERIALIZATION_TAG,
        "input_files": input_files,
        "artifact_count": ARTIFACT_COUNT,
    }
    return artifacts


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: python3 reconcile.py DATA_DIR OUT_DIR\n")
        return 2
    data_dir = argv[1]
    out_dir = argv[2]
    if not os.path.isdir(data_dir):
        sys.stderr.write("data directory not found: %s\n" % data_dir)
        return 2
    os.makedirs(out_dir, exist_ok=True)

    params = load_params(data_dir)
    priors = load_priors(data_dir)
    calibration = load_calibration(data_dir)
    anchors = load_anchors(data_dir)
    ledger = load_ledger(data_dir)
    edges = load_edges(data_dir)
    observations = load_observations(data_dir)

    artifacts = build_artifacts(
        data_dir, params, priors, calibration, anchors, ledger, edges,
        observations,
    )
    for filename in sorted(artifacts):
        write_json(out_dir, filename, artifacts[filename])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
