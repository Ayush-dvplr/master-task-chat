#!/usr/bin/env python3
"""The inference gate.

    gate.py <input-dir> <output-dir>

Reads one shift (runtimes.csv, variants.csv, callers.csv, endpoints.csv and
probes.jsonl) out of the input directory, resolves every probe through the
scoring chain and writes verdicts.jsonl, endpoints.json, precision.csv and
shift.json into the output directory.  Standard library only; two runs over
one input directory produce byte identical files.
"""

import csv
import json
import os
import sys

# --------------------------------------------------------------------------
# controller constants
# --------------------------------------------------------------------------
GAIN = 800                 # stage 4 throughput gain
SPAN_FACTOR = 4            # stage 1 factor applied when spans governs
SPANS_IDLE = 0             # the spans value that hands the width to rows
REPLAY_OFFSET = 2          # stage 2 offset carried by the replays column

# stage 5..8 responses: ('a', c) adds c, ('m', n, d) multiplies by n/d
PRECISION_ADJ = {
    'fp32': ('a', 0),
    'bf16': ('a', 11),
    'fp16': ('m', 7, 8),
    'int8': ('m', 3, 2),
}
ACCEL_ADJ = {
    'none': ('a', 0),
    'npu': ('a', 8),
    'rocm': ('a', -13),
    'cuda': ('m', 6, 5),
    'wasm': ('m', 1, 3),
    'xla': ('m', 4, 5),
    'fpga': ('a', 0),
}
PHASE_ADJ = {
    'prefill': ('a', 0),
    'batch': ('a', 14),
    'decode': ('m', 9, 10),
}
KERNEL_ADJ = {
    'graph': ('a', 0),
    'eager': ('a', -9),
    'traced': ('a', 6),
    'fused': ('m', 5, 4),
}

COARSE_ACCEL = 'fpga'      # records its meter on a coarser scale
COARSE_SCALE = 10
RESERVED_METER = -1        # never a difference: repeats the previous meter

BAND_SATURATE = 300        # stage 12 band floors
BAND_HIGH = 150
BAND_BASE = 55

MODE_SEGMENT = 'reset'     # opens a segment and reinstalls the budget
MODE_CLEAR = 'drain'       # clears the backlog
MODE_CREDIT = 'refund'     # arms the one shot credit
MODE_SERVE = 'serve'       # adds backlog
SETUP_MODES = ('reset', 'refund')
VOID_MODES = ('abort',)

PLAN_TOLERANCE = {'gold': 60, 'silver': 38, 'bronze': 17, 'trial': 0}

RECORD_SIZE = 4            # probes kept in the trailing record
CREDIT_DIVISOR = 3         # stage 11 division

BACKLOG_DIVISOR = 30       # backlog a serve adds, per unit of batch width
BACKLOG_TIER = '3'         # the tier that doubles that amount
BACKLOG_STREAK = 9         # serve directly after a serve
BACKLOG_CEILING = 200

BUDGET_DIVISOR = 1000      # a segment installs running score total // this

INHERIT_PRECISION = True   # a variant with a base is charged the base's

COUNTED_VERDICTS = ('ok', 'flagged')
QUARANTINE_STRIKES = 3
THROTTLE_BACKLOG = 40
TOP_TAG_TIE_LAST = False       # keep the earliest probe at the top score
TOP_ENDPOINT_TIE_LAST = False  # keep the first endpoint name at the top total

BANDS = ('saturate', 'high', 'base', 'idle')
VERDICTS = ('setup', 'void', 'rejected', 'flagged', 'ok')


# --------------------------------------------------------------------------
# input
# --------------------------------------------------------------------------
def _read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline='', encoding='utf-8') as fh:
        return [row for row in csv.DictReader(fh)]


def load_shift(indir):
    runtimes = {r['runtime']: r for r in _read_csv(os.path.join(indir, 'runtimes.csv'))}
    variants = {r['variant']: r for r in _read_csv(os.path.join(indir, 'variants.csv'))}
    callers = {r['caller']: r for r in _read_csv(os.path.join(indir, 'callers.csv'))}
    endpoints = {r['endpoint']: r for r in _read_csv(os.path.join(indir, 'endpoints.csv'))}
    probes = []
    path = os.path.join(indir, 'probes.jsonl')
    if os.path.exists(path):
        with open(path, encoding='utf-8') as fh:
            for line in fh:
                line = line.strip()
                if line:
                    probes.append(json.loads(line))
    probes.sort(key=lambda p: p['seq'])
    return runtimes, variants, callers, endpoints, probes


def charged_precision(variants, variant):
    row = variants.get(variant)
    if row is None:
        return None
    if INHERIT_PRECISION:
        base = (row.get('base') or '').strip()
        if base and base in variants:
            return variants[base]['precision']
    return row['precision']


# --------------------------------------------------------------------------
# resolution
# --------------------------------------------------------------------------
class EndpointState(object):
    __slots__ = ('budget', 'backlog', 'strikes', 'prev_serve', 'credit',
                 'record', 'meters', 'last_meter')

    def __init__(self, floor):
        self.budget = floor
        self.backlog = 0
        self.strikes = 0
        self.prev_serve = False
        self.credit = False
        self.record = []        # [(tag, score)], oldest first
        self.meters = {}        # phase -> running token counter
        self.last_meter = {}    # phase -> meter of the previous probe


def _apply(x, adj):
    if adj[0] == 'a':
        x = x + adj[1]
    else:
        x = x * adj[1] // adj[2]
    return x if x > 0 else 0


def resolve(runtimes, variants, callers, endpoints, probes):
    states = {}
    for name, row in endpoints.items():
        runtime = runtimes.get(row['runtime'])
        states[name] = EndpointState(int(runtime['floor']) if runtime else 0)

    running_total = 0
    records = []

    for probe in probes:
        name = probe['endpoint']
        endpoint = endpoints.get(name, {})
        state = states.get(name)
        if state is None:
            state = states[name] = EndpointState(0)
        runtime = runtimes.get(endpoint.get('runtime'))
        kernel = runtime['kernel'] if runtime else None
        precision = charged_precision(variants, endpoint.get('variant'))
        accel = endpoint.get('accel')
        phase = probe['phase']
        mode = probe['mode']

        # meter recovery: first differences of a per endpoint, per phase counter
        raw = probe['meter']
        if raw == RESERVED_METER:
            meter = state.last_meter.get(phase, 0)
        else:
            meter = state.meters.get(phase, 0) + raw
            state.meters[phase] = meter
        state.last_meter[phase] = meter
        if accel == COARSE_ACCEL:
            meter = meter * COARSE_SCALE

        # 1 batch width
        spans = probe['spans']
        width = spans * SPAN_FACTOR if spans != SPANS_IDLE else probe['rows']
        if width < 0:
            width = 0
        # 2 replay expansion
        width = width * (probe['replays'] + REPLAY_OFFSET)
        if width < 0:
            width = 0
        # 3 warmup draw
        x = meter - state.budget
        if x < 0:
            x = 0
        # 4 throughput normalisation
        x = x * GAIN // width if width > 0 else 0
        if x < 0:
            x = 0
        # 5..8 precision, accelerator, phase and kernel responses
        x = _apply(x, PRECISION_ADJ.get(precision, ('a', 0)))
        x = _apply(x, ACCEL_ADJ.get(accel, ('a', 0)))
        x = _apply(x, PHASE_ADJ.get(phase, ('a', 0)))
        x = _apply(x, KERNEL_ADJ.get(kernel, ('a', 0)))
        # 9 backlog relief
        backlog_before = state.backlog
        x = x - backlog_before
        if x < 0:
            x = 0
        # 10 replay lookup
        tag = probe['tag']
        for rec_tag, rec_score in reversed(state.record):
            if rec_tag == tag:
                x = rec_score
                break
        # 11 credit
        if state.credit:
            x = x // CREDIT_DIVISOR
            state.credit = False
        if x < 0:
            x = 0
        score = x
        # 12 banding
        if score >= BAND_SATURATE:
            band = 'saturate'
        elif score >= BAND_HIGH:
            band = 'high'
        elif score >= BAND_BASE:
            band = 'base'
        else:
            band = 'idle'
        # 13 verdict
        if mode in SETUP_MODES:
            verdict = 'setup'
        elif mode in VOID_MODES:
            verdict = 'void'
        elif band == 'idle':
            verdict = 'rejected'
        else:
            plan = callers.get(probe['caller'], {}).get('plan')
            if backlog_before > PLAN_TOLERANCE.get(plan, 0):
                verdict = 'flagged'
            else:
                verdict = 'ok'

        records.append({
            'backlog_before': backlog_before,
            'band': band,
            'caller': probe['caller'],
            'endpoint': name,
            'mode': mode,
            'phase': phase,
            'score': score,
            'seq': probe['seq'],
            'tag': tag,
            'verdict': verdict,
        })
        running_total += score

        # 14 carry update
        if mode == MODE_SEGMENT:
            state.meters = {}
            state.last_meter = {}
            state.budget = running_total // BUDGET_DIVISOR
        if mode == MODE_CLEAR:
            state.backlog = 0
        if mode == MODE_CREDIT:
            state.credit = True
        if mode == MODE_SERVE:
            amount = width // BACKLOG_DIVISOR
            if endpoint.get('tier') == BACKLOG_TIER:
                amount *= 2
            if state.prev_serve:
                amount += BACKLOG_STREAK
            backlog = state.backlog + amount
            state.backlog = BACKLOG_CEILING if backlog > BACKLOG_CEILING else backlog
        state.prev_serve = (mode == MODE_SERVE)
        if verdict == 'rejected':
            state.strikes += 1
        state.record.append((tag, score))
        if len(state.record) > RECORD_SIZE:
            del state.record[0]

    return records, states


# --------------------------------------------------------------------------
# rollups
# --------------------------------------------------------------------------
def rollup(endpoints, records, states):
    per = {}
    for name in endpoints:
        state = states.get(name)
        per[name] = {
            'endpoint': name,
            'probes': 0,
            'counted': 0,
            'score_total': 0,
            'flagged': 0,
            'top_score': 0,
            'top_tag': None,
            'bands': dict((band, 0) for band in BANDS),
            'strikes': state.strikes if state else 0,
            'backlog_end': state.backlog if state else 0,
            'budget_end': state.budget if state else 0,
        }
    for rec in records:
        row = per.get(rec['endpoint'])
        if row is None:
            continue
        row['probes'] += 1
        row['bands'][rec['band']] += 1
        if rec['verdict'] == 'flagged':
            row['flagged'] += 1
        if rec['verdict'] in COUNTED_VERDICTS:
            row['counted'] += 1
            row['score_total'] += rec['score']
            score = rec['score']
            if row['top_tag'] is None or score > row['top_score'] or (
                    TOP_TAG_TIE_LAST and score == row['top_score']):
                row['top_score'] = score
                row['top_tag'] = rec['tag']
    for row in per.values():
        if row['strikes'] >= QUARANTINE_STRIKES:
            row['disposition'] = 'quarantine'
        elif row['backlog_end'] >= THROTTLE_BACKLOG:
            row['disposition'] = 'throttle'
        else:
            row['disposition'] = 'clear'
    return per


def write_reports(outdir, variants, endpoints, records, per):
    if outdir and not os.path.isdir(outdir):
        os.makedirs(outdir)

    with open(os.path.join(outdir, 'verdicts.jsonl'), 'w', encoding='utf-8') as fh:
        for rec in records:
            fh.write(json.dumps(rec, sort_keys=True, separators=(',', ':')) + '\n')

    rows = []
    for name in sorted(per):
        row = per[name]
        rows.append({
            'backlog_end': row['backlog_end'],
            'bands': row['bands'],
            'budget_end': row['budget_end'],
            'counted': row['counted'],
            'disposition': row['disposition'],
            'endpoint': row['endpoint'],
            'flagged': row['flagged'],
            'probes': row['probes'],
            'score_total': row['score_total'],
            'strikes': row['strikes'],
            'top_score': row['top_score'],
            'top_tag': row['top_tag'],
        })
    with open(os.path.join(outdir, 'endpoints.json'), 'w', encoding='utf-8') as fh:
        fh.write(json.dumps({'endpoints': rows}, sort_keys=True, indent=2) + '\n')

    precision = {}
    for name in sorted(per):
        key = charged_precision(variants, endpoints[name].get('variant'))
        agg = precision.setdefault(key, {'endpoints': 0, 'probes': 0,
                                         'score_total': 0, 'flagged': 0})
        agg['endpoints'] += 1
        agg['probes'] += per[name]['probes']
        agg['score_total'] += per[name]['score_total']
        agg['flagged'] += per[name]['flagged']
    with open(os.path.join(outdir, 'precision.csv'), 'w', encoding='utf-8') as fh:
        fh.write('precision,endpoints,probes,score_total,flagged\n')
        for key in sorted(precision):
            agg = precision[key]
            fh.write('%s,%d,%d,%d,%d\n' % (key, agg['endpoints'], agg['probes'],
                                           agg['score_total'], agg['flagged']))

    by_band = dict((band, 0) for band in BANDS)
    by_verdict = dict((verdict, 0) for verdict in VERDICTS)
    for rec in records:
        by_band[rec['band']] += 1
        by_verdict[rec['verdict']] += 1
    top_endpoint = None
    top_total = None
    for name in sorted(per):
        total = per[name]['score_total']
        if top_total is None or total > top_total or (
                TOP_ENDPOINT_TIE_LAST and total == top_total):
            top_total = total
            top_endpoint = name
    document = {
        'by_band': by_band,
        'by_verdict': by_verdict,
        'endpoints': len(per),
        'probes': len(records),
        'quarantined': sorted(n for n in per if per[n]['disposition'] == 'quarantine'),
        'score_total': sum(per[n]['score_total'] for n in per),
        'top_endpoint': top_endpoint,
    }
    with open(os.path.join(outdir, 'shift.json'), 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(document, sort_keys=True, indent=2) + '\n')


def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: gate.py <input-dir> <output-dir>\n')
        return 2
    indir, outdir = argv[1], argv[2]
    runtimes, variants, callers, endpoints, probes = load_shift(indir)
    records, states = resolve(runtimes, variants, callers, endpoints, probes)
    per = rollup(endpoints, records, states)
    write_reports(outdir, variants, endpoints, records, per)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
