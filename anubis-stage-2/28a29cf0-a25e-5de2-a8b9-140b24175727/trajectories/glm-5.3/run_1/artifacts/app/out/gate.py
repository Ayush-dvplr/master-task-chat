#!/usr/bin/env python3
"""Inference gate: score a shift of metered serving probes.

Usage: gate.py INPUT_DIR OUTPUT_DIR

Reads runtimes.csv, variants.csv, callers.csv, endpoints.csv and probes.jsonl
from INPUT_DIR and writes verdicts.jsonl, endpoints.json, precision.csv and
shift.json into OUTPUT_DIR.
"""

import csv
import json
import os
import sys

# --- controller constants -------------------------------------------------
GAIN = 800                    # stage 4: figure * GAIN // width
REPLAY_OFFSET = 2             # stage 2: width = base * (replays + offset)
SPANS_FACTOR = 4              # stage 1: spans * factor governs when non-zero
RESERVED_METER = -1           # meter column sentinel: repeat previous meter
COARSE_ACCEL = 'fpga'         # accelerator recording on a coarser scale
COARSE_SCALE = 5

BAND_SATURATE = 300
BAND_HIGH = 150
BAND_BASE = 55

PLAN_TOLERANCE = {'gold': 60, 'silver': 38, 'bronze': 17, 'trial': 0}
SETUP_MODES = ('reset', 'refund')
VOID_MODES = ('abort',)
SEGMENT_MODE = 'reset'        # mode that opens a segment (restarts counters)
BACKLOG_CLEAR_MODE = 'drain'  # mode that clears the backlog
CREDIT_ARM_MODE = 'refund'    # mode that arms the one shot credit
CREDIT_DIVISOR = 3

BACKLOG_PER_WIDTH = 15        # serve adds width // 15
BACKLOG_TIER_DOUBLE = '3'     # tier value that doubles the amount
BACKLOG_CONSECUTIVE = 9       # extra amount for a serve directly after a serve
BACKLOG_CEILING = 120

TRAILING_RECORD = 4           # probes kept in the trailing record
QUARANTINE_STRIKES = 3        # strikes at or above this quarantine
THROTTLE_BACKLOG = 40         # backlog above this throttles

PRECISION_RESPONSE = {
    'fp32': None,
    'fp16': ('mul', 875, 1000),
    'bf16': ('add', 11),
    'int8': ('mul', 1500, 1000),
}
ACCEL_RESPONSE = {
    'none': None,
    'cuda': ('mul', 1200, 1000),
    'rocm': ('add', -13),
    'xla': ('mul', 800, 1000),
    'npu': ('add', 8),
    'wasm': ('div', 3),
    'fpga': ('floor', 7),
}
PHASE_RESPONSE = {
    'prefill': None,
    'decode': ('mul', 900, 1000),
    'batch': ('add', 14),
}
KERNEL_RESPONSE = {
    'graph': None,
    'eager': ('add', -9),
    'fused': ('mul', 1250, 1000),
    'traced': ('add', 6),
}
BANDS = ('saturate', 'high', 'base', 'idle')
VERDICTS = ('setup', 'void', 'rejected', 'flagged', 'ok')

BUDGET_MOD = 10000            # budget reinstall: floor + (score run % mod) // div
BUDGET_DIV = 400


def apply_response(figure, response):
    if response is None:
        return figure
    kind = response[0]
    if kind == 'add':
        figure += response[1]
    elif kind == 'mul':
        figure = figure * response[1] // response[2]
    elif kind == 'div':
        figure = figure // response[1]
    elif kind == 'floor':
        step = response[1]
        figure = figure // step * step
    return figure if figure > 0 else 0


def read_table(path):
    with open(path, newline='') as fh:
        rows = list(csv.reader(fh))
    header = rows[0]
    return [dict(zip(header, row)) for row in rows[1:]]


def load_shift(indir):
    runtimes = {r['runtime']: r for r in read_table(os.path.join(indir, 'runtimes.csv'))}
    variants = {r['variant']: r for r in read_table(os.path.join(indir, 'variants.csv'))}
    callers = {r['caller']: r for r in read_table(os.path.join(indir, 'callers.csv'))}
    endpoints = read_table(os.path.join(indir, 'endpoints.csv'))
    probes = []
    with open(os.path.join(indir, 'probes.jsonl')) as fh:
        for line in fh:
            line = line.strip()
            if line:
                probes.append(json.loads(line))
    probes.sort(key=lambda p: p['seq'])
    return runtimes, variants, callers, endpoints, probes


def charged_precision(variant, variants):
    row = variants[variant]
    base = row['base']
    return variants[base]['precision'] if base else row['precision']


def band_of(score):
    if score >= BAND_SATURATE:
        return 'saturate'
    if score >= BAND_HIGH:
        return 'high'
    if score >= BAND_BASE:
        return 'base'
    return 'idle'


def run_gate(indir):
    runtimes, variants, callers, endpoints, probes = load_shift(indir)

    floor_of = {rt: int(runtimes[rt]['floor']) for rt in runtimes}
    kernel_of = {rt: runtimes[rt]['kernel'] for rt in runtimes}

    state = {}
    for row in endpoints:
        ep = row['endpoint']
        state[ep] = {
            'budget': floor_of[row['runtime']],
            'backlog': 0,
            'strikes': 0,
            'prev_serve': False,
            'credit': False,
            'record': [],
            'counters': {},
            'last_meter': {},
            'precision': charged_precision(row['variant'], variants),
            'accel': row['accel'],
            'kernel': kernel_of[row['runtime']],
            'tier': row['tier'],
            'probes': 0,
            'counted': 0,
            'score_total': 0,
            'flagged': 0,
            'bands': {b: 0 for b in BANDS},
            'top_score': 0,
            'top_tag': None,
            'backlog_end': 0,
            'budget_end': floor_of[row['runtime']],
            'floor': floor_of[row['runtime']],
        }

    verdict_records = []
    score_run = 0

    for probe in probes:
        ep = probe['endpoint']
        st = state[ep]
        phase = probe['phase']
        mode = probe['mode']
        key = phase
        raw = int(probe['meter'])
        rows = int(probe['rows'])
        spans = int(probe['spans'])
        replays = int(probe['replays'])

        # --- segment boundary: every counter the endpoint holds restarts ----
        if mode == SEGMENT_MODE:
            st['counters'] = {}

        # --- meter recovery ------------------------------------------------
        # A reserved meter repeats the meter of the previous probe resolved on
        # the same endpoint and phase; it never enters the accumulation.
        counters = st['counters']
        if raw == RESERVED_METER:
            meter = st['last_meter'].get(key, 0)
        else:
            if key in counters:
                counters[key] += raw
            else:
                counters[key] = raw
            meter = counters[key]
        st['last_meter'][key] = meter
        if st['accel'] == COARSE_ACCEL:
            meter *= COARSE_SCALE

        # --- stages 1..4 ---------------------------------------------------
        base = spans * SPANS_FACTOR if spans > 0 else rows
        width = base * (replays + REPLAY_OFFSET)
        figure = meter - st['budget']
        if figure < 0:
            figure = 0
        figure = figure * GAIN // width
        if figure < 0:
            figure = 0

        # --- stages 5..8 ---------------------------------------------------
        figure = apply_response(figure, PRECISION_RESPONSE[st['precision']])
        figure = apply_response(figure, ACCEL_RESPONSE[st['accel']])
        figure = apply_response(figure, PHASE_RESPONSE[phase])
        figure = apply_response(figure, KERNEL_RESPONSE[st['kernel']])

        # --- stage 9: backlog relief ----------------------------------------
        backlog_before = st['backlog']
        figure -= backlog_before
        if figure < 0:
            figure = 0

        # --- stage 10: replay lookup ----------------------------------------
        for tag, score in reversed(st['record']):
            if tag == probe['tag']:
                figure = score
                break

        # --- stage 11: credit ------------------------------------------------
        if st['credit']:
            figure = figure // CREDIT_DIVISOR
            st['credit'] = False
        score = figure

        # --- stage 12: banding -----------------------------------------------
        band = band_of(score)

        # --- stage 13: verdict ------------------------------------------------
        if mode in SETUP_MODES:
            verdict = 'setup'
        elif mode in VOID_MODES:
            verdict = 'void'
        elif band == 'idle':
            verdict = 'rejected'
        elif backlog_before > PLAN_TOLERANCE[callers[probe['caller']]['plan']]:
            verdict = 'flagged'
        else:
            verdict = 'ok'

        verdict_records.append({
            'backlog_before': backlog_before,
            'band': band,
            'caller': probe['caller'],
            'endpoint': ep,
            'mode': mode,
            'phase': phase,
            'score': score,
            'seq': int(probe['seq']),
            'tag': probe['tag'],
            'verdict': verdict,
        })
        score_run += score

        # --- rollup accumulation ---------------------------------------------
        st['probes'] += 1
        st['bands'][band] += 1
        if verdict in ('ok', 'flagged'):
            st['counted'] += 1
            st['score_total'] += score
            if score >= st['top_score']:
                st['top_score'] = score
                st['top_tag'] = probe['tag']
        if verdict == 'flagged':
            st['flagged'] += 1

        # --- stage 14: carry update -------------------------------------------
        if mode == BACKLOG_CLEAR_MODE:
            st['backlog'] = 0
        elif mode == CREDIT_ARM_MODE:
            st['credit'] = True
        if mode == 'serve':
            amount = base // BACKLOG_PER_WIDTH
            if st['tier'] == BACKLOG_TIER_DOUBLE:
                amount *= 2
            if st['prev_serve']:
                amount += BACKLOG_CONSECUTIVE
            st['backlog'] += amount
            if st['backlog'] > BACKLOG_CEILING:
                st['backlog'] = BACKLOG_CEILING
        if verdict == 'rejected':
            st['strikes'] += 1
        st['record'].append((probe['tag'], score))
        if len(st['record']) > TRAILING_RECORD:
            del st['record'][0]
        st['prev_serve'] = (mode == 'serve')

        if mode == SEGMENT_MODE:
            st['budget'] = st['floor'] + (score_run % BUDGET_MOD) // BUDGET_DIV

    # finish endpoint state
    for ep, st in state.items():
        st['backlog_end'] = st['backlog']
        st['budget_end'] = st['budget']

    return state, verdict_records, endpoints


def build_reports(state, verdict_records, endpoints):
    rows = []
    quarantined = []
    for ep in sorted(state):
        st = state[ep]
        if st['strikes'] >= QUARANTINE_STRIKES:
            disposition = 'quarantine'
            quarantined.append(ep)
        elif st['backlog_end'] > THROTTLE_BACKLOG:
            disposition = 'throttle'
        else:
            disposition = 'clear'
        rows.append({
            'backlog_end': st['backlog_end'],
            'bands': {b: st['bands'][b] for b in BANDS},
            'budget_end': st['budget_end'],
            'counted': st['counted'],
            'disposition': disposition,
            'endpoint': ep,
            'flagged': st['flagged'],
            'probes': st['probes'],
            'score_total': st['score_total'],
            'strikes': st['strikes'],
            'top_score': st['top_score'],
            'top_tag': st['top_tag'],
        })
    endpoints_doc = {'endpoints': rows}

    by_band = {b: 0 for b in BANDS}
    by_verdict = {v: 0 for v in VERDICTS}
    for rec in verdict_records:
        by_band[rec['band']] += 1
        by_verdict[rec['verdict']] += 1

    top_endpoint = None
    best = None
    for row in rows:
        if best is None or row['score_total'] >= best:
            best = row['score_total']
            top_endpoint = row['endpoint']

    shift_doc = {
        'by_band': by_band,
        'by_verdict': by_verdict,
        'endpoints': len(rows),
        'probes': len(verdict_records),
        'quarantined': quarantined,
        'score_total': sum(r['score_total'] for r in rows),
        'top_endpoint': top_endpoint,
    }

    # precision rollup
    agg = {}
    for ep in sorted(state):
        st = state[ep]
        cur = agg.setdefault(st['precision'], {'endpoints': 0, 'probes': 0, 'score_total': 0, 'flagged': 0})
        cur['endpoints'] += 1
        cur['probes'] += st['probes']
        cur['score_total'] += st['score_total']
        cur['flagged'] += st['flagged']
    precision_lines = ['precision,endpoints,probes,score_total,flagged']
    for name in sorted(agg):
        a = agg[name]
        precision_lines.append('%s,%d,%d,%d,%d' % (name, a['endpoints'], a['probes'], a['score_total'], a['flagged']))
    precision_text = '\n'.join(precision_lines) + '\n'

    return endpoints_doc, shift_doc, precision_text


def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: gate.py INPUT_DIR OUTPUT_DIR\n')
        return 2
    indir, outdir = argv[1], argv[2]
    state, verdict_records, endpoints = run_gate(indir)
    endpoints_doc, shift_doc, precision_text = build_reports(state, verdict_records, endpoints)

    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, 'verdicts.jsonl'), 'w') as fh:
        for rec in verdict_records:
            fh.write(json.dumps(rec, sort_keys=True, separators=(',', ':')) + '\n')
    with open(os.path.join(outdir, 'endpoints.json'), 'w') as fh:
        fh.write(json.dumps(endpoints_doc, sort_keys=True, indent=2) + '\n')
    with open(os.path.join(outdir, 'precision.csv'), 'w') as fh:
        fh.write(precision_text)
    with open(os.path.join(outdir, 'shift.json'), 'w') as fh:
        fh.write(json.dumps(shift_doc, sort_keys=True, indent=2) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
