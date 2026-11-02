#!/usr/bin/env python3
"""Reconcile a clinical-assay recalibration run into its committed reports.

Usage: python3 derive_report.py DATA_DIR OUT_DIR

The run directory is read for the layout fixed by the pipeline contract and the
per-stage notes; every figure is derived from the shipped inputs.  All arithmetic
is exact integer or signed Q16.16 fixed point, staged as the specification fixes.
"""

import csv
import hashlib
import json
import math
import os
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
import zlib

ONE = 1 << 16

GOVERNANCE_CONSTANTS = (
    'RECOVERY_FLOOR_BP',
    'FLOOR_RESULT',
    'DAMPING_SEED',
    'BATCH_CAP',
    'CARRYOVER_CEILING',
)
CORE_FILES = ['summary.json', 'policy_audit.json', 'panel_analyte_glucose.json']
REUSABLE_PROGRAM = '/app/out/derive_report.py'
MAX_ROUNDS = 64


# ---------------------------------------------------------------- fixed point

def rha(num, den):
    """Divide num by den, rounding half away from zero (den > 0)."""
    if num >= 0:
        return (2 * num + den) // (2 * den)
    return -((2 * -num + den) // (2 * den))


def fp_int(n):
    return n * ONE


def fp_bp(bp):
    return rha(bp * ONE, 10000)


def fp_milli(m):
    return rha(m * ONE, 1000)


def fp_mul(a, b):
    p = a * b
    return p >> 16 if p >= 0 else -((-p) >> 16)


def fp_sqrt(v):
    return math.isqrt(v * ONE) if v > 0 else 0


def fp_round_whole(v):
    return rha(v, ONE) * ONE


def fp_trunc(v):
    return v // ONE if v >= 0 else -((-v) // ONE)


def apply_exponent(v, exponent_milli):
    if exponent_milli == 1500:
        return fp_mul(v, fp_sqrt(v))
    if exponent_milli == 2000:
        return fp_mul(v, v)
    return v


# ------------------------------------------------------------------ input io

def join(*parts):
    return os.path.join(*parts)


def read_csv_rows(path):
    with open(path, newline='') as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def as_int(value):
    if value is None:
        raise ValueError('missing integer value')
    if isinstance(value, bool):
        raise ValueError('boolean where an integer was expected')
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value != int(value):
            raise ValueError('non-integral value %r' % value)
        return int(value)
    text = str(value).strip()
    if re.fullmatch(r'[+-]?\d+', text):
        return int(text)
    number = float(text)
    if number != int(number):
        raise ValueError('non-integral value %r' % text)
    return int(number)


def is_set(value):
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    text = str(value).strip()
    if re.fullmatch(r'[+-]?\d+', text):
        return int(text) != 0
    return text.lower() in ('true', 'yes', 'y', 't', 'on', 'set')


def numeric_map(obj):
    out = {}
    for key, value in obj.items():
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            out[key] = value
        elif isinstance(value, float):
            out[key] = int(value)
        elif isinstance(value, str) and re.fullmatch(r'[+-]?\d+(\.0+)?', value.strip()):
            out[key] = as_int(value)
    return out


# ------------------------------------------------------------------- sources

def read_governance(path):
    """Pull the five governance constants out of the envelope document."""
    with open(path, 'rb') as fh:
        data = fh.read()
    chunks = []
    for match in re.finditer(rb'stream\r?\n', data):
        start = match.end()
        end = data.find(b'endstream', start)
        if end < 0:
            continue
        raw = data[start:end]
        try:
            raw = zlib.decompress(raw)
        except zlib.error:
            pass
        chunks.append(raw)
    blob = b'\n'.join(chunks).decode('latin-1')
    strings = []
    for piece in re.findall(r'\((?:\\.|[^()\\])*\)', blob):
        body = piece[1:-1]
        body = re.sub(r'\\([()\\])', r'\1', body)
        body = re.sub(r'\\([0-7]{1,3})', lambda m: chr(int(m.group(1), 8)), body)
        strings.append(body)
    text = '\n'.join(strings)
    if not text:
        text = blob
    constants = {}
    for name in GOVERNANCE_CONSTANTS:
        match = re.search(r'\b%s\b\s*[:=]?\s*([+-]?\d+)' % name, text)
        if not match:
            raise ValueError('governance constant %s not found' % name)
        constants[name] = int(match.group(1))
    return constants


SS_NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
REL_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'


def _sheet_rows(zf, part):
    root = ET.fromstring(zf.read(part))
    shared = []
    if 'xl/sharedStrings.xml' in zf.namelist():
        sst = ET.fromstring(zf.read('xl/sharedStrings.xml'))
        for si in sst.findall('{%s}si' % SS_NS):
            shared.append(''.join(t.text or '' for t in si.iter('{%s}t' % SS_NS)))
    rows = []
    for row in root.iter('{%s}row' % SS_NS):
        cells = {}
        for cell in row.iter('{%s}c' % SS_NS):
            ref = cell.get('r') or ''
            letters = re.match(r'([A-Z]+)', ref)
            index = 0
            if letters:
                for ch in letters.group(1):
                    index = index * 26 + (ord(ch) - 64)
            index -= 1
            kind = cell.get('t')
            value = None
            v = cell.find('{%s}v' % SS_NS)
            is_node = cell.find('{%s}is' % SS_NS)
            if is_node is not None:
                value = ''.join(t.text or '' for t in is_node.iter('{%s}t' % SS_NS))
            elif v is not None:
                value = v.text or ''
                if kind == 's':
                    value = shared[int(value)]
            if index >= 0:
                cells[index] = value
        width = max(cells) + 1 if cells else 0
        rows.append([cells.get(i) for i in range(width)])
    return rows


def read_grid(path, tag):
    """Select the grid sheet whose calibration tag matches the run profile."""
    with zipfile.ZipFile(path) as zf:
        workbook = ET.fromstring(zf.read('xl/workbook.xml'))
        rels = ET.fromstring(zf.read('xl/_rels/workbook.xml.rels'))
        targets = {}
        for rel in rels:
            targets[rel.get('Id')] = rel.get('Target')
        sheets = []
        for sheet in workbook.iter('{%s}sheet' % SS_NS):
            rid = sheet.get('{%s}id' % REL_NS)
            target = targets.get(rid)
            if target is None:
                continue
            if target.startswith('/'):
                target = target.lstrip('/')
            elif not target.startswith('xl/'):
                target = 'xl/' + target
            sheets.append((sheet.get('name'), target))
        selected = None
        for name, target in sheets:
            rows = _sheet_rows(zf, target)
            sheet_tag = None
            for row in rows:
                for idx, value in enumerate(row):
                    if value == 'calibration_tag':
                        if idx + 1 < len(row):
                            sheet_tag = row[idx + 1]
                        break
                if sheet_tag is not None:
                    break
            if sheet_tag == tag:
                selected = rows
                break
        if selected is None:
            raise ValueError('no grid sheet carries calibration tag %r' % tag)
        return _parse_grid_sheet(selected)


def _parse_grid_sheet(rows):
    header = None
    for row in rows:
        if row and row[0] == 'row_kind':
            header = [name for name in row]
            break
    if header is None:
        raise ValueError('grid sheet has no row_kind header')
    col = {}
    for idx, name in enumerate(header):
        if name and name not in col:
            col[name] = idx
    methods = {}
    recal = {}
    started = False
    for row in rows:
        if not row:
            continue
        if row[0] == 'row_kind':
            started = True
            continue
        if not started:
            continue

        def pick(name):
            idx = col.get(name)
            if idx is None or idx >= len(row) or row[idx] in (None, ''):
                return None
            return row[idx]
        kind = row[0]
        if kind == 'method':
            key = pick('key')
            if key is None:
                continue
            methods[key] = {
                'exponent_milli': as_int(pick('exponent_milli')),
                'gain_bp': as_int(pick('gain_bp')),
            }
        elif kind == 'recal':
            key = pick('key')
            if key is None:
                continue
            recal[key] = {
                'a_milli': as_int(pick('a_milli')),
                'b_milli': as_int(pick('b_milli')),
            }
    return {'methods': methods, 'recal': recal}


# ------------------------------------------------------------------ pipeline

def pick_batch(calendar, slot, effective_lot):
    chosen = None
    for name, from_slot, to_slot, min_lot in calendar:
        if min_lot <= effective_lot and from_slot <= slot < to_slot:
            chosen = name
    return chosen


def whole_result(reading, scales, methods, recal, recovery_floor_bp):
    scale = fp_bp(scales[reading['spec_unit']])
    scaled_raw = fp_mul(fp_int(as_int(reading['raw_signal'])), scale)
    scaled_basis = fp_mul(fp_int(as_int(reading['basis_signal'])), scale)
    method = methods[reading['method']]
    powered = apply_exponent(scaled_basis, method['exponent_milli'])
    transformed = fp_round_whole(fp_mul(powered, fp_bp(method['gain_bp'])))
    coeff = recal[reading['analyte']]
    recalibrated = fp_round_whole(
        fp_mul(fp_milli(coeff['a_milli']), scaled_raw + transformed) + fp_milli(coeff['b_milli'])
    )
    recovery_bp = as_int(reading['recovery_bp'])
    if recovery_bp < recovery_floor_bp:
        recovery_bp = recovery_floor_bp
    reweighted = fp_round_whole(fp_mul(recalibrated, fp_bp(recovery_bp)))
    return fp_trunc(reweighted)


def fair_share(names, masses, total, target):
    fair = {}
    if total == 0:
        for name in names:
            fair[name] = 0
        return fair
    base = {}
    rem = {}
    for name in names:
        value = masses[name] * target
        base[name] = value // total
        rem[name] = value - base[name] * total
    left = target - sum(base.values())
    order = sorted(names, key=lambda n: (-rem[n], n))
    if left > 0:
        for i in range(left):
            base[order[i % len(order)]] += 1
    elif left < 0:
        for i in range(-left):
            base[order[i % len(order)]] -= 1
    return base


def converge(names, masses, cap, damping_seed):
    """Damped proportional rebalance of one batch; returns (rounds, masses)."""
    current = dict(masses)
    damping = damping_seed
    prev_residual = None
    non_improving = 0
    seen = {}
    states = []
    for rnd in range(MAX_ROUNDS):
        state = tuple(current[name] for name in names)
        if state in seen:
            cycle = states[seen[state]:]
            smallest = min(cycle)
            return -1, {name: value for name, value in zip(names, smallest)}
        seen[state] = rnd
        states.append(state)
        total = sum(current[name] for name in names)
        target = total if total <= cap else cap
        fair = fair_share(names, current, total, target)
        residual = sum(abs(current[name] - fair[name]) for name in names)
        if prev_residual is not None and residual >= prev_residual:
            non_improving += 1
            if non_improving >= 2:
                damping //= 2
                non_improving = 0
        prev_residual = residual
        flows = {name: rha((fair[name] - current[name]) * damping, 10000) for name in names}
        excess = sum(flows.values())
        if excess != 0:
            furthest = min(names, key=lambda n: (-abs(current[n] - fair[n]), n))
            flows[furthest] -= excess
        if residual == 0:
            return rnd, current
        if all(value == 0 for value in flows.values()):
            return rnd, current
        for name in names:
            current[name] += flows[name]
    return MAX_ROUNDS, current


# -------------------------------------------------------------------- output

def dump_json(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':')) + '\n'


def xml_escape(value):
    return (
        str(value)
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
    )


def write_text(path, text):
    with open(path, 'w', newline='\n') as fh:
        fh.write(text)


class Emitter(object):
    """Collects every artifact the program writes, for the provenance manifest."""

    def __init__(self, out_dir):
        self.out_dir = out_dir
        self.written = []

    def json(self, name, obj):
        self.text(name, dump_json(obj))
        return obj

    def text(self, name, payload):
        write_text(join(self.out_dir, name), payload)
        self.written.append(name)


def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: derive_report.py DATA_DIR OUT_DIR\n')
        return 2
    data_dir, out_dir = argv[1], argv[2]
    os.makedirs(out_dir, exist_ok=True)
    out = Emitter(out_dir)

    with open(join(data_dir, 'run_profile.json')) as fh:
        profile = json.load(fh)
    tag = profile['calibration_tag']
    effective_lot = min(as_int(profile['lot_a']), as_int(profile['lot_b']))

    gov = read_governance(join(data_dir, 'governance_envelope.pdf'))
    floor_result = gov['FLOOR_RESULT']
    damping_seed = gov['DAMPING_SEED']
    batch_cap = gov['BATCH_CAP']
    ceiling = gov['CARRYOVER_CEILING']

    grid = read_grid(join(data_dir, 'recalibration_grid.xlsx'), tag)
    methods = grid['methods']
    recal = grid['recal']

    scales = {
        row['spec_unit']: as_int(row['scale_bp'])
        for row in read_csv_rows(join(data_dir, 'unit_scale_book.csv'))
    }
    with open(join(data_dir, 'tier_weight_book.json')) as fh:
        tier_weights = numeric_map(json.load(fh))
    crosswalk = [
        (row['analyte'], row['matrix'])
        for row in read_csv_rows(join(data_dir, 'analyte_crosswalk.csv'))
    ]
    topology = {}
    for row in read_csv_rows(join(data_dir, 'panel_topology.csv')):
        topology[row['analyte']] = {
            'matrix_class': row['matrix_class'],
            'tier': row['tier'],
            'shift': as_int(row['matrix_shift_units']),
        }
    calendar = [
        (
            row['batch'],
            as_int(row['from_slot']),
            as_int(row['to_slot']),
            as_int(row['min_lot']),
        )
        for row in read_csv_rows(join(data_dir, 'batch_calendar.csv'))
    ]

    # Ordering: exclude qc-fail readings, then settle_slot, draw_slot, id desc.
    readings = read_csv_rows(join(data_dir, 'assay_capture_run.csv'))
    excluded = sorted(r['reading_id'] for r in readings if is_set(r['is_qc_fail']))
    live = [r for r in readings if not is_set(r['is_qc_fail'])]
    live.sort(key=lambda r: r['reading_id'], reverse=True)
    live.sort(key=lambda r: as_int(r['draw_slot']))
    live.sort(key=lambda r: as_int(r['settle_slot']))
    ordered_ids = [r['reading_id'] for r in live]

    # Admission with channel carry, seating and committed totals.
    committed = {}
    seated = {}
    admitted_mass = {}
    carry = {}
    first_admitted = {}
    for reading in live:
        batch = pick_batch(calendar, as_int(reading['settle_slot']), effective_lot)
        if batch is None:
            continue
        analyte = reading['analyte']
        channel = reading['channel']
        seated.setdefault(batch, set()).add(analyte)
        committed.setdefault((batch, analyte), 0)
        if channel not in first_admitted:
            first_admitted[channel] = (batch, analyte)
        whole = whole_result(reading, scales, methods, recal, gov['RECOVERY_FLOOR_BP'])
        if whole < 0:
            admitted = whole
        else:
            candidate = whole + carry.get(channel, 0)
            headroom = batch_cap - admitted_mass.get(batch, 0)
            if headroom < 0:
                headroom = 0
            admitted = candidate if candidate <= headroom else headroom
            carry[channel] = candidate - admitted
        admitted_mass[batch] = admitted_mass.get(batch, 0) + admitted
        figure = admitted if admitted > floor_result else floor_result
        figure += topology[analyte]['shift']
        if figure < 0:
            figure = 0
        committed[(batch, analyte)] += figure

    for channel in sorted(carry):
        left = carry[channel]
        if left and channel in first_admitted:
            batch, analyte = first_admitted[channel]
            committed[(batch, analyte)] += left

    # Convergence per batch, then carryover reprojection.
    batches = sorted(seated)
    batch_masses = {}
    convergence_rounds = {}
    for batch in batches:
        names = sorted(seated[batch])
        masses = {name: committed[(batch, name)] for name in names}
        rounds, settled = converge(names, masses, batch_cap, damping_seed)
        convergence_rounds[batch] = rounds
        batch_masses[batch] = settled
        for name in names:
            committed[(batch, name)] = settled[name]

    carryover = []
    for batch in batches:
        settled = batch_masses[batch]
        total = sum(settled.values())
        if total <= ceiling:
            continue
        excess = total - ceiling
        for analyte in sorted(settled, key=lambda n: (-settled[n], n)):
            if excess <= 0:
                break
            available = settled[analyte]
            if available <= 0:
                continue
            take = available if available < excess else excess
            settled[analyte] -= take
            committed[(batch, analyte)] -= take
            excess -= take
            carryover.append({'analyte': analyte, 'clawed_units': take, 'batch': batch})
    carryover.sort(key=lambda e: (e['batch'], e['analyte']))
    carryover_total = sum(entry['clawed_units'] for entry in carryover)

    # Projections of the committed per-analyte per-batch result.
    batch_totals = {batch: sum(batch_masses[batch].values()) for batch in batches}
    analyte_allocations = {
        batch: {name: committed[(batch, name)] for name in sorted(seated[batch])}
        for batch in batches
    }
    panel_analytes = sorted({name for name, _ in crosswalk})
    allocation_analytes = sorted(
        {name for batch in batches for name in analyte_allocations[batch]}
    )
    analyte_totals = {
        name: sum(analyte_allocations[batch][name] for batch in batches
                   if name in analyte_allocations[batch])
        for name in allocation_analytes
    }
    grand_total = sum(analyte_totals.values())

    analyte_tier = {name: topology[name]['tier'] for name in panel_analytes}
    analyte_matrix = {name: topology[name]['matrix_class'] for name in panel_analytes}
    for name, matrix in crosswalk:
        analyte_matrix[name] = matrix

    tier_totals = {}
    for name in allocation_analytes:
        tier = analyte_tier[name]
        tier_totals[tier] = tier_totals.get(tier, 0) + analyte_totals[name]
    matrix_totals = {}
    for name in allocation_analytes:
        matrix = analyte_matrix[name]
        matrix_totals[matrix] = matrix_totals.get(matrix, 0) + analyte_totals[name]

    objective = sum(
        tier_totals.get(tier, 0) * weight for tier, weight in tier_weights.items()
    )

    unsettled = sorted(b for b in batches if convergence_rounds[b] == -1)

    summary = {
        'batch_totals': batch_totals,
        'analyte_allocations': analyte_allocations,
        'convergence_rounds': convergence_rounds,
        'unsettled_batches': unsettled,
    }
    policy_audit = {
        'tier_totals': tier_totals,
        'carryover_ledger': carryover,
        'excluded_reading_ids': excluded,
        'excluded_count': len(excluded),
        'effective_lot': effective_lot,
        'ordered_reading_ids': ordered_ids,
    }

    core_payload = dump_json(summary)
    policy_payload = dump_json(policy_audit)
    panel_payloads = {}
    for analyte in panel_analytes:
        per_batch = {
            batch: analyte_allocations[batch][analyte]
            for batch in batches
            if analyte in analyte_allocations[batch]
        }
        panel = {
            'analyte': analyte,
            'matrix': analyte_matrix[analyte],
            'tier': analyte_tier[analyte],
            'committed_total': analyte_totals.get(analyte, 0),
            'per_batch': per_batch,
        }
        panel_payloads[analyte] = dump_json(panel)

    digest = hashlib.sha256(
        (core_payload + policy_payload + panel_payloads['glucose']).encode('utf-8')
    ).hexdigest()

    data_quality = {
        'objective_value': objective,
        'tier_totals': tier_totals,
        'committed_grand_total': grand_total,
        'carryover_total_units': carryover_total,
        'core_files': CORE_FILES,
        'core_sha256': digest,
    }

    out.text('summary.json', core_payload)
    out.text('policy_audit.json', policy_payload)
    out.json('data_quality.json', data_quality)
    for analyte in panel_analytes:
        out.text('panel_analyte_%s.json' % analyte, panel_payloads[analyte])
    out.json('matrix_rollup.json', {
            'axis': 'matrix',
            'class_totals': matrix_totals,
            'analyte_membership': {n: analyte_matrix[n] for n in allocation_analytes},
        })
    out.json('tier_rollup.json', {
        'axis': 'tier',
        'class_totals': tier_totals,
        'weighted_objective': objective,
        'analyte_membership': {n: analyte_tier[n] for n in allocation_analytes},
    })
    out.json('analyte_totals.json', analyte_totals)
    out.json('tier_analyte_membership.json', {
        n: analyte_tier[n] for n in allocation_analytes
    })
    out.json('ordered_reading_index.json', ordered_ids)
    out.json('excluded_readings.json', excluded)

    lines = ['analyte,matrix,tier,committed_total']
    for analyte, matrix in sorted(crosswalk):
        lines.append('%s,%s,%s,%d' % (
            analyte, matrix, analyte_tier[analyte], analyte_totals.get(analyte, 0)))
    out.text('analyte_committed.csv', '\n'.join(lines) + '\n')

    lines = ['batch\tcommitted_total\tconvergence_rounds']
    for batch in batches:
        lines.append('%s\t%d\t%d' % (
            batch, batch_totals[batch], convergence_rounds[batch]))
    out.text('batch_committed.tsv', '\n'.join(lines) + '\n')

    lines = ['tier|committed_total|tier_weight|weighted_contribution']
    for tier in sorted(tier_weights):
        total = tier_totals.get(tier, 0)
        weight = tier_weights[tier]
        lines.append('%s|%d|%d|%d' % (tier, total, weight, total * weight))
    out.text('matrix_weighted.psv', '\n'.join(lines) + '\n')

    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<carryover_ledger>']
    for entry in carryover:
        lines.append('  <entry batch="%s" analyte="%s" clawed_units="%d"/>' % (
            xml_escape(entry['batch']),
            xml_escape(entry['analyte']),
            entry['clawed_units'],
        ))
    lines.append('  <total clawed_units="%d"/>' % carryover_total)
    lines.append('</carryover_ledger>')
    out.text('carryover_ledger.xml', '\n'.join(lines) + '\n')

    lines = [
        'objective_value: %d' % objective,
        'committed_grand_total: %d' % grand_total,
        'excluded_count: %d' % len(excluded),
        'carryover_total_units: %d' % carryover_total,
        'effective_lot: %d' % effective_lot,
        'core_sha256: %s' % digest,
        'tier_totals:',
    ]
    for tier in sorted(tier_totals):
        lines.append('  %s: %d' % (tier, tier_totals[tier]))
    out.text('objective_summary.yaml', '\n'.join(lines) + '\n')

    lines = [
        '# Assay QC Reconciliation Report',
        '',
        'objective_value %d' % objective,
        'committed_grand_total %d' % grand_total,
        'effective_lot %d' % effective_lot,
        'excluded_count %d' % len(excluded),
        '',
        '## Batch totals',
        '',
    ]
    for batch in batches:
        lines.append('- %s %d' % (batch, batch_totals[batch]))
    out.text('reconciliation_report.md', '\n'.join(lines) + '\n')

    status = 'SETTLED' if not unsettled else 'UNSETTLED'
    unsettled_word = 'none' if not unsettled else ','.join(unsettled)
    out.text('run_status.txt', '\n'.join([
        'status %s' % status,
        'objective_value %d' % objective,
        'core_sha256 %s' % digest,
        'unsettled_batches %s' % unsettled_word,
    ]) + '\n')

    out.json('provenance_manifest.json', {
        'artifact_names': sorted(set(out.written)),
        'core_files': CORE_FILES,
        'core_sha256': digest,
        'reusable_program': REUSABLE_PROGRAM,
    })
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
