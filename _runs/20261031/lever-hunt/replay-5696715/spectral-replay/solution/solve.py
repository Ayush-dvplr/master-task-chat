#!/usr/bin/env python3
"""Reconcile a spectral covariance audit extract into the contract's artifacts.

Usage: reconcile.py DATA_DIR OUT_DIR

The pipeline follows /app/data/schema.md: anchor-derived source bias, ledger
void and replace actions applied before calibration, per-source and per-period
calibration, reliability weighting, per-cell weighted averaging, state-edge
propagation, then bound enforcement and the summary views. Decimal cell values
are carried at full precision and rounded to nearest-even ppm once, at output.
"""
from __future__ import annotations

import csv
import json
import sys
from fractions import Fraction
from pathlib import Path

VARIABLES = ['hydra', 'kepler', 'lyra', 'orion', 'pavo', 'vega']
COHORTS = ['Arden', 'Beryl', 'Canto', 'Dorian']
SOURCES = ['atlas', 'beacon', 'cygnus', 'draco']
PERIODS = ['2026Q1', '2026Q2', '2026Q3']

PPM = 1_000_000.0
BPS = 10_000.0
ARTIFACT_COUNT = 25
SERIALIZATION_TAG = 'json-sort-compact-newline'


class ReconcileError(Exception):
    """An input file is missing, unreadable, or inconsistent with the contract."""


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    """Read one CSV into a list of dicts, naming the file if it cannot be read."""
    try:
        with open(path, newline='') as handle:
            return list(csv.DictReader(handle))
    except OSError as exc:
        raise ReconcileError(f'cannot read {path.name}: {exc}') from exc


def read_json(path: Path) -> dict:
    """Read one JSON object, naming the file if it cannot be read or parsed."""
    try:
        with open(path) as handle:
            return json.load(handle)
    except OSError as exc:
        raise ReconcileError(f'cannot read {path.name}: {exc}') from exc
    except ValueError as exc:
        raise ReconcileError(f'{path.name} is not valid JSON: {exc}') from exc


def write_artifact(path: Path, payload) -> None:
    """Write one artifact as canonical JSON: sorted keys, compact, one newline."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, separators=(',', ':')) + '\n')


def to_ppm(value: float) -> int:
    """Scale a decimal to parts per million, rounded half to even."""
    return int(round(value * PPM))


def clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def numeric(row: dict[str, str], column: str, source_name: str) -> float:
    """Read one numeric cell, naming the file and column when it is unusable."""
    try:
        return float(row[column])
    except KeyError as exc:
        raise ReconcileError(f'{source_name} has no column {column}') from exc
    except (TypeError, ValueError) as exc:
        raise ReconcileError(
            f'{source_name} column {column} holds a non-numeric value {row[column]!r}'
        ) from exc


def collect_inputs(data_dir: Path) -> dict:
    """Discover every input family inside DATA_DIR by file name pattern.

    sample_observations.csv is illustrative only and is excluded by the
    field_observations_ prefix; the descriptive files are not read at all.
    """
    if not data_dir.is_dir():
        raise ReconcileError(f'DATA_DIR {data_dir} is not a directory')

    priors_rows = read_csv_rows(data_dir / 'source_priors.csv')
    priors = {row['source']: row for row in priors_rows}

    calibration: dict[tuple[str, str], dict[str, str]] = {}
    for path in sorted(data_dir.glob('calibration_*.csv')):
        for row in read_csv_rows(path):
            calibration[(row['source'], row['period'])] = row

    anchors: list[dict[str, str]] = []
    for path in sorted(data_dir.glob('anchor_constraints_*.csv')):
        anchors.extend(read_csv_rows(path))

    edges: list[dict[str, str]] = []
    for path in sorted(data_dir.glob('state_edges_*.csv')):
        edges.extend(read_csv_rows(path))

    observations: list[dict[str, str]] = []
    for path in sorted(data_dir.glob('field_observations_*.csv')):
        observations.extend(read_csv_rows(path))

    ledger: list[dict[str, str]] = []
    for path in sorted(data_dir.glob('ledger_corrections_*.csv')):
        ledger.extend(read_csv_rows(path))

    return {
        'params': read_json(data_dir / 'params.json'),
        'priors': priors,
        'calibration': calibration,
        'anchors': anchors,
        'edges': edges,
        'observations': observations,
        'ledger': ledger,
        'input_file_count': sum(1 for path in data_dir.iterdir() if path.is_file()),
    }


def source_bias_from_anchors(
    anchors: list[dict[str, str]],
) -> tuple[dict[str, float], dict[str, int], dict[str, int]]:
    """Average target minus observed per source.

    Returns the decimal offset used inside the pipeline, the anchor row count,
    and the reported ppm value. The reported value is rounded from the exact
    rational mean, so a mean landing on exactly half a ppm goes to the even
    integer instead of whichever side float error happens to push it.
    """
    bias_totals = {source: 0.0 for source in SOURCES}
    exact_totals = {source: Fraction(0) for source in SOURCES}
    anchor_counts = {source: 0 for source in SOURCES}
    for row in anchors:
        source = row['source']
        if source not in bias_totals:
            raise ReconcileError(f'anchor row names unknown source {source!r}')
        target = numeric(row, 'target_ppm', 'anchor_constraints')
        observed = numeric(row, 'observed_ppm', 'anchor_constraints')
        bias_totals[source] += target / PPM - observed / PPM
        exact_totals[source] += Fraction(row['target_ppm']) - Fraction(row['observed_ppm'])
        anchor_counts[source] += 1
    bias = {
        source: (bias_totals[source] / anchor_counts[source] if anchor_counts[source] else 0.0)
        for source in SOURCES
    }
    bias_ppm = {
        source: (round(exact_totals[source] / anchor_counts[source]) if anchor_counts[source] else 0)
        for source in SOURCES
    }
    return bias, anchor_counts, bias_ppm


def apply_ledger(
    observations: list[dict[str, str]], ledger: list[dict[str, str]]
) -> tuple[list[dict[str, str]], list[dict]]:
    """Void or replace observations by observation_id, before any calibration."""
    corrections = {row['observation_id']: row for row in ledger}
    surviving: list[dict[str, str]] = []
    events: list[dict] = []
    for observation in observations:
        correction = corrections.get(observation['observation_id'])
        if correction is None:
            surviving.append(observation)
            continue
        action = correction['action']
        if action == 'void':
            events.append({'observation_id': observation['observation_id'], 'effect': 'voided'})
            continue
        if action == 'replace':
            before = observation['raw_value']
            replaced = dict(observation)
            replaced['raw_value'] = correction['replacement_value']
            replaced['reliability_bps'] = correction['replacement_reliability_bps']
            events.append({
                'observation_id': replaced['observation_id'],
                'effect': 'replaced',
                'before': before,
                'after': replaced['raw_value'],
            })
            surviving.append(replaced)
            continue
        raise ReconcileError(f'ledger row carries unknown action {action!r}')
    return surviving, events


def local_estimates(
    observations: list[dict[str, str]],
    priors: dict[str, dict[str, str]],
    calibration: dict[tuple[str, str], dict[str, str]],
    bias: dict[str, float],
) -> dict[tuple[str, str, str, str], float]:
    """Calibrate, weight and average every observation into its cell."""
    weighted: dict[tuple[str, str, str, str], list[tuple[float, float]]] = {}
    for observation in observations:
        source = observation['source']
        period = observation['period']
        calibration_row = calibration.get((source, period))
        if calibration_row is None:
            raise ReconcileError(f'no calibration row for source {source!r} period {period!r}')
        prior_row = priors.get(source)
        if prior_row is None:
            raise ReconcileError(f'no prior row for source {source!r}')

        raw_value = numeric(observation, 'raw_value', 'field_observations')
        scale = numeric(calibration_row, 'scale_ppm', 'calibration')
        offset = numeric(calibration_row, 'offset_ppm', 'calibration')
        stability = numeric(calibration_row, 'stability_bps', 'calibration')
        reliability = numeric(observation, 'reliability_bps', 'field_observations')
        prior = numeric(prior_row, 'prior_bps', 'source_priors')

        corrected = raw_value * scale / PPM + offset / PPM + bias[source]
        weight = reliability / BPS * prior / BPS * stability / BPS
        cell = (observation['cohort'], period, observation['var_i'], observation['var_j'])
        weighted.setdefault(cell, []).append((corrected, weight))

    estimates = {}
    for cell, entries in weighted.items():
        total_weight = sum(weight for _, weight in entries)
        if total_weight == 0.0:
            raise ReconcileError(f'cell {cell} carries zero total weight')
        estimates[cell] = sum(value * weight for value, weight in entries) / total_weight
    return estimates


def propagate_state_edges(
    estimates: dict[tuple[str, str, str, str], float], edges: list[dict[str, str]]
) -> list[dict]:
    """Blend each destination cell with its propagated source, recording residuals."""
    residuals: list[dict] = []
    for edge in edges:
        period = edge['period']
        var_i, var_j = edge['var_i'], edge['var_j']
        origin = (edge['from_cohort'], period, var_i, var_j)
        destination = (edge['to_cohort'], period, var_i, var_j)
        if origin not in estimates or destination not in estimates:
            continue
        multiplier = numeric(edge, 'multiplier_ppm', 'state_edges')
        delta = numeric(edge, 'delta_ppm', 'state_edges')
        propagated = estimates[origin] * multiplier / PPM + delta / PPM
        before = estimates[destination]
        estimates[destination] = (before + propagated) / 2.0
        residuals.append({
            'edge_id': edge['edge_id'],
            'before_ppm': to_ppm(before),
            'after_ppm': to_ppm(estimates[destination]),
            'propagated_ppm': to_ppm(propagated),
        })
    return residuals


def build_matrices(
    estimates: dict[tuple[str, str, str, str], float], params: dict
) -> dict[str, dict[str, list[list[float]]]]:
    """Build every cohort-period matrix, enforcing the floor, cap and symmetry."""
    diagonal_floor = float(params['diagonal_floor_ppm']) / PPM
    offdiag_cap = float(params['offdiag_abs_cap_ppm']) / PPM

    matrices: dict[str, dict[str, list[list[float]]]] = {}
    for cohort in COHORTS:
        matrices[cohort] = {}
        for period in PERIODS:
            cells = [[0.0] * len(VARIABLES) for _ in VARIABLES]
            for i, var_i in enumerate(VARIABLES):
                for j, var_j in enumerate(VARIABLES):
                    if i > j:
                        continue
                    available = [
                        estimates[key]
                        for key in ((cohort, period, var_i, var_j), (cohort, period, var_j, var_i))
                        if key in estimates
                    ]
                    if available:
                        value = sum(available) / len(available)
                    else:
                        value = 1.0 if i == j else 0.0
                    if i == j:
                        value = max(value, diagonal_floor)
                    else:
                        value = clip(value, -offdiag_cap, offdiag_cap)
                    cells[i][j] = cells[j][i] = value
            matrices[cohort][period] = cells
    return matrices


def upper_triangle(cells: list[list[float]]):
    for i in range(len(VARIABLES)):
        for j in range(i, len(VARIABLES)):
            yield cells[i][j]


def diagonal(cells: list[list[float]]):
    for i in range(len(VARIABLES)):
        yield cells[i][i]


def mean_ppm(values) -> int:
    """Average full-precision decimals, then round to ppm exactly once."""
    values = list(values)
    if not values:
        raise ReconcileError('cannot average an empty set of cells')
    return to_ppm(sum(values) / len(values))


def write_reports(out_dir: Path, matrices, estimates, inputs, bias_ppm, anchor_counts,
                  ledger_events, residuals) -> None:
    """Derive and write all 24 JSON artifacts from the full-precision cells."""
    rounded_matrices = {
        cohort: {
            period: [[to_ppm(value) for value in row] for row in matrices[cohort][period]]
            for period in PERIODS
        }
        for cohort in COHORTS
    }
    write_artifact(out_dir / 'matrix_all.json', rounded_matrices)

    all_upper = [
        value for cohort in COHORTS for period in PERIODS
        for value in upper_triangle(matrices[cohort][period])
    ]
    all_diagonal = [
        value for cohort in COHORTS for period in PERIODS
        for value in diagonal(matrices[cohort][period])
    ]
    write_artifact(out_dir / 'global_summary.json', {
        'cohorts': len(COHORTS),
        'periods': len(PERIODS),
        'variables': VARIABLES,
        'global_mean_ppm': mean_ppm(all_upper),
        'diagonal_mean_ppm': mean_ppm(all_diagonal),
        'ledger_events': len(ledger_events),
        'state_edges': len(residuals),
    })

    write_artifact(out_dir / 'audit_state.json', {
        'source_bias_ppm': dict(bias_ppm),
        'anchor_counts': anchor_counts,
    })

    write_artifact(out_dir / 'dependency_checks.json', {
        'observation_cells': len(estimates),
        'calibration_keys': len(inputs['calibration']),
        'anchors': len(inputs['anchors']),
        'constraints_applied': len(residuals),
        'complete': all(
            (cohort, period, variable, variable) in estimates
            for cohort in COHORTS for period in PERIODS for variable in VARIABLES
        ),
    })

    write_artifact(out_dir / 'residuals.json', {'edge_residuals': residuals})
    write_artifact(out_dir / 'ledger_effects.json', {'events': ledger_events})

    write_artifact(out_dir / 'convergence_periods.json', {'period_mean_ppm': {
        period: mean_ppm(
            value for cohort in COHORTS for value in upper_triangle(matrices[cohort][period])
        )
        for period in PERIODS
    }})

    edge_shifts = [abs(record['after_ppm'] - record['before_ppm']) for record in residuals]
    write_artifact(out_dir / 'convergence_constraints.json', {
        'max_abs_edge_shift_ppm': max(edge_shifts) if edge_shifts else 0,
        'edge_count': len(residuals),
    })

    write_artifact(out_dir / 'eigen_spectrum.json', {'gershgorin_radii_ppm': {
        cohort: [
            to_ppm(max(sum(abs(value) for value in row) for row in matrices[cohort][period]))
            for period in PERIODS
        ]
        for cohort in COHORTS
    }})

    write_artifact(out_dir / 'reproducibility.json', {
        'serialization': SERIALIZATION_TAG,
        'input_files': inputs['input_file_count'],
        'artifact_count': ARTIFACT_COUNT,
    })

    for cohort in COHORTS:
        write_artifact(out_dir / f'cohort_{cohort}.json', {
            'cohort': cohort,
            'mean_ppm': mean_ppm(
                value for period in PERIODS for value in upper_triangle(matrices[cohort][period])
            ),
            'periods': rounded_matrices[cohort],
        })

    rank_order = sorted(SOURCES, key=lambda name: int(inputs['priors'][name]['prior_bps']), reverse=True)
    for source in SOURCES:
        write_artifact(out_dir / f'source_{source}.json', {
            'source': source,
            'bias_ppm': bias_ppm[source],
            'prior_bps': int(inputs['priors'][source]['prior_bps']),
            'relative_rank': rank_order.index(source) + 1,
        })

    for index, variable in enumerate(VARIABLES):
        diagonal_cells = [
            matrices[cohort][period][index][index] for cohort in COHORTS for period in PERIODS
        ]
        write_artifact(out_dir / f'variable_{variable}.json', {
            'variable': variable,
            'diagonal_mean_ppm': mean_ppm(diagonal_cells),
            'diagonal_min_ppm': to_ppm(min(diagonal_cells)),
            'diagonal_max_ppm': to_ppm(max(diagonal_cells)),
        })


def reconcile(data_dir: Path, out_dir: Path) -> None:
    inputs = collect_inputs(data_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    bias, anchor_counts, bias_ppm = source_bias_from_anchors(inputs['anchors'])
    surviving, ledger_events = apply_ledger(inputs['observations'], inputs['ledger'])
    estimates = local_estimates(surviving, inputs['priors'], inputs['calibration'], bias)
    residuals = propagate_state_edges(estimates, inputs['edges'])
    matrices = build_matrices(estimates, inputs['params'])

    write_reports(out_dir, matrices, estimates, inputs, bias_ppm, anchor_counts,
                  ledger_events, residuals)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(f'usage: {Path(argv[0]).name} DATA_DIR OUT_DIR', file=sys.stderr)
        return 2
    try:
        reconcile(Path(argv[1]), Path(argv[2]))
    except ReconcileError as exc:
        print(f'reconciliation failed: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
