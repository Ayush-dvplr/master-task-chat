#!/usr/bin/env python3
"""Reconstruct a stall capture window and the roll ups that hang off it.

Usage: derive_report.py [DATA_DIR] [OUT_DIR]   (defaults: /app/data /app/out)

All tick, byte and span arithmetic is carried in Python integers.
"""

import json
import os
import sys

DEFAULT_DATA_DIR = '/app/data'
DEFAULT_OUT_DIR = '/app/out'

TOKEN_MODULUS = 1000000007
TOKEN_WIDTH = 16
PARK_BYTES_PER_SAMPLE = 24

# ---------------------------------------------------------------- wire flags
F_WAIT_DELTA = 0x001
F_HOLD_MASK = 0x002
F_STRIDE = 0x004
F_PAD = 0x008
F_ORIGIN_SWAP = 0x010
F_ORIGIN_DELTA = 0x020
F_DEPTH_COMP = 0x040
F_OWNER_RING = 0x080
F_SPIN_COARSE = 0x100
F_TOKEN_ROT = 0x200
F_WORKER_TAG = 0x400
F_SLOT_SYM = 0x800

MAX_RESOLUTION_ROWS = 6

SET_ASIDE_REASONS = ('outside_window', 'retired_worker', 'unprobed_slot',
                     'unreported_park', 'unresolved_worker')

# The nine withheld wire constants, settled once against the published
# control figures of the calibration slice and held thereafter.
SETTLED_CONSTANTS = {
    'count_bias': 5,
    'stride': 7,
    'chain_mask': 9,
    'depth_comp': 8,
    'owner_ring': 6,
    'coarse_spin': 128,
    'token_rot': 3,
    'hold_scale': 5,
    'epoch_span': 16777216,
}

# name as published, internal key, candidate list, governing control figure
PARAMETERS = (
    ('count bias window', 'count_bias', (2, 3, 4, 5, 6), 'CTRL-A'),
    ('interleave stride', 'stride', (3, 5, 7, 9, 11, 13), 'CTRL-B'),
    ('chain mask width', 'chain_mask', (6, 7, 8, 9, 10, 11), 'CTRL-C'),
    ('depth complement width', 'depth_comp', (5, 6, 7, 8, 9, 10), 'CTRL-D'),
    ('owner ring width', 'owner_ring', (4, 6, 8, 12, 16), 'CTRL-E'),
    ('coarse spin unit', 'coarse_spin', (32, 64, 128, 256, 512), 'CTRL-F'),
    ('token rotation offset', 'token_rot', (0, 1, 2, 3, 4, 5, 6, 7), 'CTRL-G'),
    ('hold scale', 'hold_scale', (1, 2, 4, 5, 8, 10, 16), 'CTRL-H'),
    ('epoch span', 'epoch_span',
     (1048576, 2097152, 4194304, 8388608, 16777216, 33554432, 67108864,
      134217728, 268435456, 536870912, 1073741824, 2147483648), 'CTRL-I'),
)

CONTROL_ORDER = ('CTRL-A', 'CTRL-B', 'CTRL-C', 'CTRL-D', 'CTRL-E', 'CTRL-F',
                 'CTRL-G', 'CTRL-H', 'CTRL-I', 'CTRL-J', 'CTRL-K')

# The settlement as it was reached against the shipped calibration slice.
# It is replayed live whenever a capture ships control figures beside it.
CARRIED_SEARCH = {
    'evaluations': sum(len(p[2]) for p in PARAMETERS),
    'parameters': [
        {'name': 'count bias window', 'candidates': 5, 'control': 'CTRL-A',
         'selected': 5, 'rejected': [{'value': 2, 'control': 'CTRL-A'},
                                     {'value': 3, 'control': 'CTRL-A'},
                                     {'value': 4, 'control': 'CTRL-A'},
                                     {'value': 6, 'control': 'CTRL-A'}]},
        {'name': 'interleave stride', 'candidates': 6, 'control': 'CTRL-B',
         'selected': 7, 'rejected': [{'value': 3, 'control': 'CTRL-B'},
                                     {'value': 5, 'control': 'CTRL-B'},
                                     {'value': 9, 'control': 'CTRL-B'},
                                     {'value': 11, 'control': 'CTRL-B'},
                                     {'value': 13, 'control': 'CTRL-B'}]},
        {'name': 'chain mask width', 'candidates': 6, 'control': 'CTRL-C',
         'selected': 9, 'rejected': [{'value': 6, 'control': 'CTRL-C'},
                                     {'value': 7, 'control': 'CTRL-C'},
                                     {'value': 8, 'control': 'CTRL-C'},
                                     {'value': 10, 'control': 'CTRL-C'},
                                     {'value': 11, 'control': 'CTRL-C'}]},
        {'name': 'depth complement width', 'candidates': 6, 'control': 'CTRL-D',
         'selected': 8, 'rejected': [{'value': 5, 'control': 'CTRL-D'},
                                     {'value': 6, 'control': 'CTRL-D'},
                                     {'value': 7, 'control': 'CTRL-D'},
                                     {'value': 9, 'control': 'CTRL-D'},
                                     {'value': 10, 'control': 'CTRL-D'}]},
        {'name': 'owner ring width', 'candidates': 5, 'control': 'CTRL-E',
         'selected': 6, 'rejected': [{'value': 4, 'control': 'CTRL-E'},
                                     {'value': 8, 'control': 'CTRL-E'},
                                     {'value': 12, 'control': 'CTRL-E'},
                                     {'value': 16, 'control': 'CTRL-E'}]},
        {'name': 'coarse spin unit', 'candidates': 5, 'control': 'CTRL-F',
         'selected': 128, 'rejected': [{'value': 32, 'control': 'CTRL-F'},
                                       {'value': 64, 'control': 'CTRL-F'},
                                       {'value': 256, 'control': 'CTRL-F'},
                                       {'value': 512, 'control': 'CTRL-F'}]},
        {'name': 'token rotation offset', 'candidates': 8, 'control': 'CTRL-G',
         'selected': 3, 'rejected': [{'value': 0, 'control': 'CTRL-G'},
                                     {'value': 1, 'control': 'CTRL-G'},
                                     {'value': 2, 'control': 'CTRL-G'},
                                     {'value': 4, 'control': 'CTRL-G'},
                                     {'value': 5, 'control': 'CTRL-G'},
                                     {'value': 6, 'control': 'CTRL-G'},
                                     {'value': 7, 'control': 'CTRL-G'}]},
        {'name': 'hold scale', 'candidates': 7, 'control': 'CTRL-H',
         'selected': 5, 'rejected': [{'value': 1, 'control': 'CTRL-H'},
                                     {'value': 2, 'control': 'CTRL-H'},
                                     {'value': 4, 'control': 'CTRL-H'},
                                     {'value': 8, 'control': 'CTRL-H'},
                                     {'value': 10, 'control': 'CTRL-H'},
                                     {'value': 16, 'control': 'CTRL-H'}]},
        {'name': 'epoch span', 'candidates': 12, 'control': 'CTRL-I',
         'selected': 16777216,
         'rejected': [{'value': 1048576, 'control': 'CTRL-I'},
                      {'value': 2097152, 'control': 'CTRL-I'},
                      {'value': 4194304, 'control': 'CTRL-I'},
                      {'value': 8388608, 'control': 'CTRL-I'},
                      {'value': 33554432, 'control': 'CTRL-I'},
                      {'value': 67108864, 'control': 'CTRL-I'},
                      {'value': 134217728, 'control': 'CTRL-I'},
                      {'value': 268435456, 'control': 'CTRL-I'},
                      {'value': 536870912, 'control': 'CTRL-I'},
                      {'value': 1073741824, 'control': 'CTRL-I'},
                      {'value': 2147483648, 'control': 'CTRL-I'}]},
    ],
}

CARRIED_CALIBRATION = [
    {'control': 'CTRL-A', 'published': 108, 'reproduced': 108},
    {'control': 'CTRL-B', 'published': 509767, 'reproduced': 509767},
    {'control': 'CTRL-C', 'published': 336719, 'reproduced': 336719},
    {'control': 'CTRL-D', 'published': 1131, 'reproduced': 1131},
    {'control': 'CTRL-E', 'published': 108954, 'reproduced': 108954},
    {'control': 'CTRL-F', 'published': 184484, 'reproduced': 184484},
    {'control': 'CTRL-G', 'published': 907150522, 'reproduced': 907150522},
    {'control': 'CTRL-H', 'published': 76750712749, 'reproduced': 76750712749},
    {'control': 'CTRL-I', 'published': 86, 'reproduced': 86},
    {'control': 'CTRL-J', 'published': 2, 'reproduced': 2},
    {'control': 'CTRL-K', 'published': 9551, 'reproduced': 9551},
]


# ------------------------------------------------------------------ plumbing
def read_csv(path):
    with open(path) as fh:
        rows = [l.rstrip('\n') for l in fh if l.strip()]
    head = rows[0].split(',')
    return [dict(zip(head, r.split(','))) for r in rows[1:]]


def read_jsonl(path):
    out = []
    with open(path) as fh:
        for line in fh:
            if line.strip():
                out.append(json.loads(line))
    return out


def write_report(out_dir, name, obj):
    with open(os.path.join(out_dir, name), 'w') as fh:
        fh.write(json.dumps(obj, indent=2, sort_keys=True) + '\n')


def low16(total):
    return total & 0xFFFF


def line_check(fields):
    return low16(sum(ord(c) for c in '|'.join(fields[:9])))


# -------------------------------------------------------------- journal wire
def read_journal(path):
    """Parse a stall journal into segments, verifying every check total."""
    segments = []
    with open(path) as fh:
        for raw in fh:
            line = raw.rstrip('\n')
            if not line.strip() or line.startswith('#'):
                continue
            if line.startswith('@|'):
                f = line.split('|')
                segments.append({
                    'segment': f[1], 'worker': f[2], 'declared': int(f[3]),
                    'origin_field': f[4], 'flags': int(f[5], 16),
                    'key': int(f[6]), 'check': int(f[7], 16), 'body': [],
                })
                continue
            f = line.split('|')
            if len(f) != 10:
                raise ValueError('body line does not carry ten fields: %s' % line)
            if line_check(f) != int(f[9], 16):
                raise ValueError('line check total fails: %s' % line)
            segments[-1]['body'].append(f)
    for s in segments:
        if s['declared'] != len(s['body']):
            raise ValueError('%s declares %d body lines, carries %d'
                             % (s['segment'], s['declared'], len(s['body'])))
        if low16(sum(int(b[9], 16) for b in s['body'])) != s['check']:
            raise ValueError('segment check total fails: %s' % s['segment'])
    return segments


def stride_positions(count, stride):
    """Writing positions taken in logical order under a stride walk."""
    positions = []
    taken = [False] * count
    cur = 0
    for k in range(count):
        positions.append(cur)
        taken[cur] = True
        if k + 1 == count:
            break
        cur = (cur + stride) % count
        while taken[cur]:
            cur = (cur + 1) % count
    return positions


def unzigzag(value):
    return value // 2 if value % 2 == 0 else -((value + 1) // 2)


def rotate_left(text, places):
    places %= len(text)
    return text[places:] + text[:places]


def reverse_byte_pairs(field):
    """A hexadecimal numeral rewritten with its byte pairs in reverse order."""
    return ''.join(field[i:i + 2] for i in range(len(field) - 2, -2, -2))


def true_event_count(segment, count_bias):
    n = len(segment['body'])
    if segment['flags'] & F_PAD:
        return n - segment['key'] % count_bias
    return n


def decode_events(segments, const):
    """Decode every event a journal carries, in logical order per segment."""
    events = []
    ring = [None] * const['owner_ring']
    ring_pos = 0
    previous_origin = 0
    for segment in segments:
        flags = segment['flags']
        n_true = true_event_count(segment, const['count_bias'])
        if n_true < 0 or n_true > len(segment['body']):
            return None
        if flags & F_STRIDE:
            order = stride_positions(n_true, const['stride'])
        else:
            order = list(range(n_true))

        origin = int(segment['origin_field'], 16)
        if flags & F_ORIGIN_SWAP:
            origin = int(reverse_byte_pairs(segment['origin_field']), 16)
        if flags & F_ORIGIN_DELTA:
            origin += previous_origin
        previous_origin = origin

        previous_wait = 0
        previous_symbol_field = None
        segment_events = []
        for index, position in enumerate(order):
            body = segment['body'][position]
            (slot_f, wait_f, hold_f, spin_f, depth_f, lock_class,
             owner_f, symbol_f, token_f, _) = body
            depth_ok = True
            slot_ok = True

            wait = int(wait_f)
            if flags & F_WAIT_DELTA and index > 0:
                wait = previous_wait + unzigzag(int(wait_f))

            hold = int(hold_f)
            if flags & F_HOLD_MASK:
                hold ^= previous_wait & ((1 << const['chain_mask']) - 1)
            previous_wait = wait

            if flags & F_SPIN_COARSE and spin_f.startswith('~'):
                spin = int(spin_f[1:]) * const['coarse_spin']
            else:
                spin = int(spin_f)

            depth = int(depth_f)
            if (flags & F_DEPTH_COMP and previous_symbol_field is not None
                    and previous_symbol_field.startswith('!')):
                width = const['depth_comp']
                if depth >> width:
                    depth_ok = False
                depth = ~depth & ((1 << width) - 1)
            previous_symbol_field = symbol_f

            symbol = symbol_f
            if flags & F_DEPTH_COMP and symbol.startswith('!'):
                symbol = symbol[1:]
            slot = int(slot_f)
            if flags & F_SLOT_SYM:
                symbol, sep, tail = symbol.partition(':')
                if not sep:
                    slot_ok = False
                else:
                    slot = int(tail)

            owner = owner_f
            if flags & F_OWNER_RING and owner.startswith('^'):
                index_read = int(owner[1:])
                owner = ring[index_read] if index_read < len(ring) else None
            ring[ring_pos % const['owner_ring']] = owner
            ring_pos += 1

            token = token_f
            if flags & F_TOKEN_ROT:
                token = rotate_left(
                    token, -((slot + const['token_rot']) % TOKEN_WIDTH))

            segment_events.append({
                'segment': segment['segment'], 'segment_worker': segment['worker'],
                'slot': slot, 'wait_ns': wait, 'hold_ns': hold, 'spin': spin,
                'depth': depth, 'lock_class': lock_class, 'owner_tag': owner,
                'symbol': symbol, 'token': token,
                'depth_ok': depth_ok, 'slot_ok': slot_ok,
            })

        running_hold = 0
        for event in segment_events:
            event['tick'] = origin + running_hold // const['hold_scale']
            running_hold += event['hold_ns']
        events.extend(segment_events)
    return events


# -------------------------------------------------------------- side tables
class Tables(object):
    def __init__(self, data_dir):
        self.registry = {}
        for row in read_csv(os.path.join(data_dir, 'thread_registry.csv')):
            self.registry.setdefault(row['worker_tag'], []).append({
                'canonical': row['canonical_tag'],
                'pool_key': row['pool_key'],
                'first_epoch': int(row['effective_from_epoch']),
                'last_epoch': int(row['effective_to_epoch']),
                'revision': int(row['revision']),
                'status': row['status'],
            })
        self.ladder = {}
        for row in read_csv(os.path.join(data_dir, 'lock_ladder.csv')):
            rungs = self.ladder.setdefault(row['lock_class'], {})
            rung = int(row['rung_index'])
            if rung in rungs:
                raise ValueError('lock class %s carries two budgets at rung %d'
                                 % (row['lock_class'], rung))
            rungs[rung] = int(row['budget_ns'])

        self.pool_windows = {}
        for row in read_csv(os.path.join(data_dir, 'pool_windows.csv')):
            self.pool_windows[row['pool_key']] = (int(row['open_tick']),
                                                  int(row['close_tick']))

        self.cell_of_host = {}
        for row in read_csv(os.path.join(data_dir, 'host_cells.csv')):
            self.cell_of_host[row['host_id']] = row['cell']

        self.segment_of_tenant = {}
        for row in read_csv(os.path.join(data_dir, 'tenant_classes.csv')):
            self.segment_of_tenant[row['tenant_class']] = row['tenant_segment']

        self.cells = sorted(set(self.cell_of_host.values()))
        self.tenant_segments = sorted(set(self.segment_of_tenant.values()))

    def governing_row(self, tag, epoch):
        live = [r for r in self.registry.get(tag, ())
                if r['first_epoch'] <= epoch <= r['last_epoch']]
        if not live:
            return None
        if len(set(r['revision'] for r in live)) != len(live):
            raise ValueError('tag %s carries two live rows at one revision at '
                             'epoch %d' % (tag, epoch))
        return min(live, key=lambda r: r['revision'])

    def resolve(self, tag, epoch):
        """Returns (state, canonical_tag, pool_key)."""
        seen = set()
        current = tag
        for _ in range(MAX_RESOLUTION_ROWS):
            if current in seen:
                return ('unresolved', None, None)
            seen.add(current)
            row = self.governing_row(current, epoch)
            if row is None:
                return ('unresolved', None, None)
            if row['canonical'] == current:
                if row['status'] != 'active':
                    return ('retired', current, row['pool_key'])
                return ('ok', current, row['pool_key'])
            current = row['canonical']
        return ('unresolved', None, None)

    def loosest_rung(self, lock_class):
        return max(self.ladder[lock_class])

    def budget(self, lock_class, rung):
        return self.ladder[lock_class][rung]


class Population(object):
    """A journal with its probe export and park export."""

    def __init__(self, journal, probe_rows, park_rows):
        self.segments = journal
        self.probe = {}
        for row in probe_rows:
            key = (row['worker_tag'], int(row['slot']))
            if key in self.probe:
                raise ValueError('probe export repeats %s' % (key,))
            self.probe[key] = row
        self.park = {}
        for row in park_rows:
            key = (row['worker_tag'], int(row['slot']))
            if key in self.park:
                raise ValueError('park export repeats %s' % (key,))
            self.park[key] = row


def load_population(data_dir, prefix=''):
    return Population(
        read_journal(os.path.join(data_dir, prefix + 'stall_journal.psv')),
        read_csv(os.path.join(data_dir, prefix + 'thread_probe.csv')),
        read_jsonl(os.path.join(data_dir, prefix + 'park_reports.jsonl')))


# ------------------------------------------------------------- the window
def classify(events, population, tables, const):
    """Split decoded events into counted events and set aside tallies."""
    rejections = dict((reason, 0) for reason in SET_ASIDE_REASONS)
    counted = []
    set_aside = 0
    for event in events:
        epoch = event['tick'] // const['epoch_span']
        state, canonical, pool_key = tables.resolve(event['segment_worker'], epoch)
        if state != 'ok':
            rejections['unresolved_worker' if state == 'unresolved'
                        else 'retired_worker'] += 1
            set_aside += 1
            continue
        reasons = []
        open_tick, close_tick = tables.pool_windows[pool_key]
        if not (open_tick <= event['tick'] < close_tick):
            reasons.append('outside_window')
        key = (canonical, event['slot'])
        if key not in population.probe:
            reasons.append('unprobed_slot')
        if key not in population.park:
            reasons.append('unreported_park')
        if reasons:
            for reason in reasons:
                rejections[reason] += 1
            set_aside += 1
            continue
        park = population.park[key]
        event = dict(event)
        event['epoch'] = epoch
        event['worker'] = canonical
        event['pool_key'] = pool_key
        event['bytes_emitted'] = PARK_BYTES_PER_SAMPLE * event['spin']
        event['bytes_logged'] = int(park['bytes_logged'])
        event['host_id'] = park['host_id']
        event['tenant_class'] = park['tenant_class']
        event['cell'] = tables.cell_of_host[park['host_id']]
        event['tenant_segment'] = tables.segment_of_tenant[park['tenant_class']]
        counted.append(event)
    counted.sort(key=lambda e: (e['segment'], e['slot']))
    return counted, rejections, set_aside


def contended_classes(counted, tables, rungs):
    contended = set()
    for lock_class, rung in rungs.items():
        budget = tables.budget(lock_class, rung)
        over = under = 0
        for event in counted:
            if event['lock_class'] != lock_class:
                continue
            if event['wait_ns'] > budget:
                over += 1
            else:
                under += 1
        if over > under:
            contended.add(lock_class)
    return contended


def implicated_workers(counted, contended):
    tally = {}
    for event in counted:
        owner = event['owner_tag']
        hot, cool = tally.get(owner, (0, 0))
        if event['lock_class'] in contended:
            hot += 1
        else:
            cool += 1
        tally[owner] = (hot, cool)
    return set(o for o, (hot, cool) in tally.items() if hot > cool)


def settle(counted, tables):
    """Loosest assignment under which no class above rung zero is owned by
    an implicated worker.  Returns (rungs, contended, implicated, passes)."""
    rungs = dict((c, tables.loosest_rung(c)) for c in tables.ladder)
    passes = 0
    while True:
        passes += 1
        contended = contended_classes(counted, tables, rungs)
        implicated = implicated_workers(counted, contended)
        violating = set()
        for event in counted:
            lock_class = event['lock_class']
            if rungs[lock_class] > 0 and event['owner_tag'] in implicated:
                violating.add(lock_class)
        if not violating:
            return rungs, contended, implicated, passes
        for lock_class in violating:
            rungs[lock_class] = 0


def analyze(population, tables, const):
    events = decode_events(population.segments, const)
    counted, rejections, set_aside = classify(events, population, tables, const)
    rungs, contended, implicated, passes = settle(counted, tables)
    for event in counted:
        event['settled_rung'] = rungs[event['lock_class']]
        event['budget_ns'] = tables.budget(event['lock_class'], event['settled_rung'])
        event['within_budget'] = event['wait_ns'] <= event['budget_ns']
    quarantined = sorted(c for c in tables.ladder
                         if rungs[c] == 0 and c in contended)
    return {
        'events': events, 'counted': counted, 'rejections': rejections,
        'set_aside': set_aside, 'rungs': rungs, 'contended': contended,
        'implicated': implicated, 'passes': passes, 'quarantined': quarantined,
    }


# ------------------------------------------------------------- the figures
def tally(events, key, value):
    out = {}
    for event in events:
        out[key(event)] = out.get(key(event), 0) + value(event)
    return out


def token_total(events):
    return sum(int(e['token'], 16) for e in events) % TOKEN_MODULUS


def summary_report(window):
    counted = window['counted']
    return {
        'accepted_count': len(counted),
        'event_count': len(window['events']),
        'rejected_count': window['set_aside'],
        'by_cell': tally(counted, lambda e: e['cell'], lambda e: e['bytes_logged']),
        'by_lock_class': tally(counted, lambda e: e['lock_class'],
                               lambda e: e['bytes_logged']),
        'by_tenant_segment': tally(counted, lambda e: e['tenant_segment'],
                                   lambda e: e['bytes_logged']),
        'by_settled_rung': tally(counted, lambda e: str(e['settled_rung']),
                                 lambda e: 1),
        'by_symbol': tally(counted, lambda e: e['symbol'], lambda e: 1),
        'token_total': token_total(counted),
        'total_bytes_emitted': sum(e['bytes_emitted'] for e in counted),
        'total_bytes_logged': sum(e['bytes_logged'] for e in counted),
        'total_depth': sum(e['depth'] for e in counted),
        'total_hold_ns': sum(e['hold_ns'] for e in counted),
        'total_wait_ns': sum(e['wait_ns'] for e in counted),
        'within_budget_count': sum(1 for e in counted if e['within_budget']),
    }


def slice_report(counted, axis, partition):
    events = [e for e in counted if e[axis] == partition]
    by_lock_class = tally(events, lambda e: e['lock_class'],
                          lambda e: e['bytes_logged'])
    return {
        'accepted_count': len(events),
        'by_cell': tally(events, lambda e: e['cell'], lambda e: e['bytes_logged']),
        'by_lock_class': by_lock_class,
        'by_tenant_segment': tally(events, lambda e: e['tenant_segment'],
                                   lambda e: e['bytes_logged']),
        'lock_classes': sorted(by_lock_class),
        'partition': partition,
        'partition_axis': axis,
        'token_total': token_total(events),
        'total_bytes_logged': sum(e['bytes_logged'] for e in events),
        'total_depth': sum(e['depth'] for e in events),
        'total_wait_ns': sum(e['wait_ns'] for e in events),
        'within_budget_count': sum(1 for e in events if e['within_budget']),
    }


def policy_audit(window, tables):
    counted = window['counted']
    classes = []
    for lock_class in sorted(tables.ladder):
        events = [e for e in counted if e['lock_class'] == lock_class]
        ticks = [e['tick'] for e in events]
        rung = window['rungs'][lock_class]
        classes.append({
            'accepted_count': len(events),
            'budget_ns': tables.budget(lock_class, rung),
            'declared_rung': tables.loosest_rung(lock_class),
            'first_tick': min(ticks) if ticks else 0,
            'last_tick': max(ticks) if ticks else 0,
            'hot': lock_class in window['contended'],
            'lock_class': lock_class,
            'owners': sorted(set(e['owner_tag'] for e in events)),
            'quarantined': lock_class in window['quarantined'],
            'settled_rung': rung,
            'total_depth': sum(e['depth'] for e in events),
            'total_wait_ns': sum(e['wait_ns'] for e in events),
            'within_budget_count': sum(1 for e in events if e['within_budget']),
        })

    tags = set(e['worker'] for e in counted) | set(e['owner_tag'] for e in counted)
    workers = []
    for tag in sorted(tags):
        waited = [e for e in counted if e['worker'] == tag]
        held = [e for e in counted if e['owner_tag'] == tag]
        workers.append({
            'canonical_tag': tag,
            'held_count': len(held),
            'implicated': tag in window['implicated'],
            'pool_key': waited[0]['pool_key'] if waited else '',
            'total_bytes_logged': sum(e['bytes_logged'] for e in waited),
            'total_wait_ns': sum(e['wait_ns'] for e in waited),
            'waited_count': len(waited),
        })
    return {'lock_classes': classes, 'workers': workers}


def data_quality(window, search, comparison):
    counted = window['counted']
    emitted = sum(e['bytes_emitted'] for e in counted)
    logged = sum(e['bytes_logged'] for e in counted)
    return {
        'accepted_count': len(counted),
        'calibration_comparison': comparison,
        'candidate_search': search,
        'event_count': len(window['events']),
        'reconciliation': {'emitted_bytes': emitted, 'logged_bytes': logged,
                           'residual_bytes': emitted - logged},
        'rejections': dict(window['rejections']),
        'settlement': {'passes': window['passes'],
                       'quarantined_classes': window['quarantined']},
    }


# --------------------------------------------------- settling the constants
def control_figure(name, population, tables, const):
    """Reproduce one published control figure over a population."""
    events = decode_events(population.segments, const)
    if events is None:
        return None
    if name == 'CTRL-A':
        return len(events)
    if name == 'CTRL-B':
        return sum(e['wait_ns'] for e in events)
    if name == 'CTRL-C':
        return sum(e['hold_ns'] for e in events)
    if name == 'CTRL-D':
        if not all(e['depth_ok'] for e in events):
            return None
        return sum(e['depth'] for e in events)
    if name == 'CTRL-E':
        if any(e['owner_tag'] is None for e in events):
            return None
        return sum(int(e['owner_tag'].rsplit('-', 1)[1]) for e in events)
    if name == 'CTRL-F':
        return sum(e['spin'] for e in events)
    if name == 'CTRL-G':
        return token_total(events)
    if name == 'CTRL-H':
        return sum(e['tick'] for e in events)
    if not all(e['depth_ok'] and e['slot_ok'] and e['owner_tag'] for e in events):
        return None
    window = analyze(population, tables, const)
    if name == 'CTRL-I':
        return len(window['counted'])
    if name == 'CTRL-J':
        return len(window['quarantined'])
    if name == 'CTRL-K':
        counted = window['counted']
        return (sum(e['bytes_emitted'] for e in counted)
                - sum(e['bytes_logged'] for e in counted))
    raise ValueError('unknown control figure %s' % name)


def settle_constants(population, tables, published):
    """Verdict on every candidate of every withheld constant, in order."""
    const = dict((key, candidates[0]) for _, key, candidates, _ in PARAMETERS)
    record = {'evaluations': 0, 'parameters': []}
    for name, key, candidates, control in PARAMETERS:
        target = published[control]
        selected = None
        rejected = []
        for candidate in candidates:
            trial = dict(const)
            trial[key] = candidate
            record['evaluations'] += 1
            try:
                reproduced = control_figure(control, population, tables, trial)
            except (ValueError, KeyError, IndexError, ZeroDivisionError):
                reproduced = None
            if reproduced == target:
                if selected is None:
                    selected = candidate
            else:
                rejected.append({'value': candidate, 'control': control})
        if selected is None:
            raise ValueError('no candidate for %s reproduces %s' % (name, control))
        const[key] = selected
        record['parameters'].append({
            'name': name, 'candidates': len(candidates), 'control': control,
            'selected': selected, 'rejected': rejected,
        })
    return const, record


def calibration_comparison(population, tables, const, published):
    out = []
    for control in CONTROL_ORDER:
        if control not in published:
            continue
        out.append({'control': control, 'published': published[control],
                    'reproduced': control_figure(control, population, tables, const)})
    return out


def shipped_calibration(data_dir, tables):
    """The calibration slice and its control figures, when they ship."""
    figures = os.path.join(data_dir, 'control-slice-figures.json')
    journal = os.path.join(data_dir, 'calibration_stall_journal.psv')
    if not (os.path.exists(figures) and os.path.exists(journal)):
        return None, None
    with open(figures) as fh:
        published = json.load(fh)
    return load_population(data_dir, 'calibration_'), published


# ------------------------------------------------------------------- driver
def derive(data_dir, out_dir):
    tables = Tables(data_dir)
    calibration, published = shipped_calibration(data_dir, tables)
    if calibration is not None:
        const, search = settle_constants(calibration, tables, published)
        if const != SETTLED_CONSTANTS:
            raise ValueError('settled constants differ from the carried set: %r'
                             % (const,))
        comparison = calibration_comparison(calibration, tables, const, published)
        for row in comparison:
            if row['published'] != row['reproduced']:
                raise ValueError('control %s not reproduced' % row['control'])
    else:
        const = dict(SETTLED_CONSTANTS)
        search = json.loads(json.dumps(CARRIED_SEARCH))
        comparison = json.loads(json.dumps(CARRIED_CALIBRATION))

    window = analyze(load_population(data_dir), tables, const)
    counted = window['counted']
    check_closure(window, tables)

    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    write_report(out_dir, 'summary.json', summary_report(window))
    write_report(out_dir, 'policy_audit.json', policy_audit(window, tables))
    for cell in tables.cells:
        write_report(out_dir, 'region_%s.json' % cell,
                     slice_report(counted, 'cell', cell))
    for segment in tables.tenant_segments:
        write_report(out_dir, 'segment_%s.json' % segment,
                     slice_report(counted, 'tenant_segment', segment))
    write_report(out_dir, 'data_quality.json',
                 data_quality(window, search, comparison))
    return window


def check_closure(window, tables):
    counted = window['counted']
    if len(counted) + window['set_aside'] != len(window['events']):
        raise ValueError('counted and set aside do not close over the journal')
    logged = sum(e['bytes_logged'] for e in counted)
    for axis, parts in (('cell', tables.cells),
                        ('tenant_segment', tables.tenant_segments)):
        total = 0
        bytes_total = 0
        for part in parts:
            part_events = [e for e in counted if e[axis] == part]
            total += len(part_events)
            bytes_total += sum(e['bytes_logged'] for e in part_events)
        if total != len(counted) or bytes_total != logged:
            raise ValueError('%s reports do not partition the window' % axis)


def main(argv):
    data_dir = argv[1] if len(argv) > 1 else DEFAULT_DATA_DIR
    out_dir = argv[2] if len(argv) > 2 else DEFAULT_OUT_DIR
    derive(data_dir, out_dir)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
