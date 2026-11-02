#!/usr/bin/env python3
"""Settle Ninefold Marches replay captures and emit the scenario reports.

usage: optimize.py <capture-dir> <report-dir>

The eleven withheld quantities are recovered at run time from the calibration
notes found in the capture directory; none of their values live in this source.
Every amount, share, stock and target is carried as an exact Fraction.
"""

import bisect
import csv
import hashlib
import json
import os
import re
import sys
from fractions import Fraction

SEALED, CHAINED, STEPPED, DRIFTED = 1, 2, 4, 8
WOVEN, ECHOED, FLIPPED, PADDED = 16, 32, 64, 128
SHADOWED, SPUN, ALIASED, WARDED = 256, 512, 1024, 2048

ECHO_KIND = 224
REVERSAL_KIND = 3
ORDINARY_KINDS = (0, 1, 2)
PAYLOAD_LEN = 12
TICK_WRAP = 65536
M32 = 0xFFFFFFFF

FALLBACK_KEY = 'MRD-2031'
FALLBACK_UNIT_WORDS = (
    'aurochs basilisk cockatrice dryad ettin fenrir golem hydra ifrit jotun '
    'kelpie lamia manticore nixie ogre pegasus quasit roc sylph troll '
    'undine vodyanoi wyvern xorn').split()
FALLBACK_LABELS = ('aegis banner cinder dagger ember falcon gale harrow ingot '
                   'javelin kestrel lantern').split()
FALLBACK_CHARTERS = 'azure crimson gilded sable verdant'.split()
FALLBACK_CADENCE = ['peak', 'steady', 'burst', 'latency']

REPORT_NAMES = ['scenario_visible.json', 'scenario_peak.json',
                'scenario_steady.json', 'scenario_burst.json',
                'scenario_latency.json', 'perf_report.json',
                'recommendations.json', 'data_quality.json',
                'bottleneck_analysis.json']

# quantities whose value changes how a capture decodes
DECODE_KEYS = ('weave_seed_offset', 'sentinel_code_value', 'drift_modulus',
               'seal_label_index', 'spin_modulus', 'shadow_pad_base',
               'alias_donor_shift', 'echo_window_span')


# --------------------------------------------------------------- shipped notes

def read_text(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def words_in_sentence(text, phrase, fallback):
    """Backticked tokens of the sentence that carries `phrase`."""
    at = text.find(phrase)
    if at < 0:
        return list(fallback)
    tail = text[at:]
    stop = tail.find('.')
    found = re.findall(r'`([^`]+)`', tail if stop < 0 else tail[:stop])
    return found or list(fallback)


def parse_notes(capture_dir):
    path = os.path.join(capture_dir, 'charter-scale.md')
    if not os.path.exists(path):
        return {'key': FALLBACK_KEY, 'unit_words': list(FALLBACK_UNIT_WORDS),
                'labels': list(FALLBACK_LABELS), 'charters': list(FALLBACK_CHARTERS),
                'cadence': list(FALLBACK_CADENCE)}
    text = read_text(path)
    found = re.search(r'engine\s+key\s+`([^`]+)`', text)
    return {
        'key': found.group(1) if found else FALLBACK_KEY,
        'unit_words': words_in_sentence(text, 'unit words', FALLBACK_UNIT_WORDS),
        'labels': words_in_sentence(text, 'label words', FALLBACK_LABELS),
        'charters': words_in_sentence(text, 'charters are', FALLBACK_CHARTERS),
        'cadence': words_in_sentence(text, 'cadence classes', FALLBACK_CADENCE),
    }


def parse_calibration(capture_dir):
    """Return the published quantity rows and the published control figures."""
    text = read_text(os.path.join(capture_dir, 'calibration.md'))
    quantities = []
    published = {}
    for line in text.splitlines():
        row = line.strip()
        if not row.startswith('|'):
            continue
        cells = [c.strip() for c in row.strip('|').split('|')]
        if len(cells) >= 3:
            name = re.match(r'^`([a-z_]+)`$', cells[0])
            span = re.match(r'^(\d+)\s+through\s+(\d+)$', cells[1])
            if name and span:
                low, high = int(span.group(1)), int(span.group(2))
                quantities.append({'name': name.group(1),
                                   'candidates': list(range(low, high + 1)),
                                   'control': cells[2]})
                continue
        if len(cells) == 2 and cells[0].upper().startswith('CTRL'):
            figure = re.match(r'^`([0-9a-f]+)`$', cells[1])
            if figure:
                published[cells[0]] = figure.group(1)
    return quantities, published


def parse_roster(capture_dir):
    register = {}
    order = []
    with open(os.path.join(capture_dir, 'roster-register.csv'), newline='',
              encoding='utf-8') as fh:
        for row in csv.DictReader(fh):
            word = row['word'].strip()
            closed = row['closed'].strip()
            register[word] = {'charter': row['charter'].strip(),
                              'opened': int(row['opened'].strip()),
                              'closed': int(closed) if closed else 0,
                              'successor': row['successor'].strip()}
            order.append(word)
    return register, order


def parse_windows(capture_dir):
    windows = []
    with open(os.path.join(capture_dir, 'tick-schedule.csv'), newline='',
              encoding='utf-8') as fh:
        for row in csv.DictReader(fh):
            windows.append({'first': int(row['first_tick'].strip()),
                            'last': int(row['last_tick'].strip()),
                            'live': row['live'].strip().lower() in ('1', 'true', 'yes')})
    return windows


def parse_bench(capture_dir):
    bench = []
    path = os.path.join(capture_dir, 'bench-candidates.csv')
    if not os.path.exists(path):
        return bench
    with open(path, newline='', encoding='utf-8') as fh:
        for row in csv.DictReader(fh):
            bench.append((row['word'].strip(), int(row['upkeep'].strip())))
    return bench


def parse_captures(capture_dir):
    captures = []
    for name in sorted(os.listdir(capture_dir)):
        if not name.endswith('.rpl'):
            continue
        lines = read_text(os.path.join(capture_dir, name)).split('\n')
        head = lines[0].split()
        fields = dict(kv.split('=', 1) for kv in head[1:] if '=' in kv)
        blocks = []
        for line in lines[1:]:
            if not line.strip():
                continue
            parts = line.split()
            if parts[0] == 'B':
                blocks.append({'bo': int(parts[1]), 'width': int(parts[2]),
                               'check': parts[3], 'payloads': []})
            elif parts[0] == 'R' and blocks:
                blocks[-1]['payloads'].append(parts[1])
        captures.append({'name': fields.get('capture', name),
                         'num': int(fields['number']),
                         'flags': int(fields['flags'], 16),
                         'frames': int(fields['frames']),
                         'words': fields['words'].split(','),
                         'seal': fields.get('seal', ''),
                         'blocks': blocks})
    captures.sort(key=lambda cap: cap['num'])
    return captures


# -------------------------------------------------------------------- digests

def mask(key, label, *numbers):
    buf = bytearray(key.encode())
    buf += label.encode()
    for number in numbers:
        buf += b':' + str(number).encode()
    return hashlib.sha256(bytes(buf)).digest()[:PAYLOAD_LEN]


def control_figure(key, fragments):
    buf = bytearray(key.encode())
    for fragment in fragments:
        buf += b'|' + fragment.encode('utf-8')
    return hashlib.sha256(bytes(buf)).hexdigest()[:12]


def xor_bytes(left, right):
    return bytes(a ^ b for a, b in zip(left, right))


# ----------------------------------------------------------------- transforms

def weave_order(offset, num, block_ordinal, width):
    state = (offset + 97 * num + 7 * block_ordinal) & M32
    state = (state * 2654435761 + 1013904223) & M32
    if state == 0:
        state = 2654435769
    order = list(range(width))
    for position in range(width - 1, 0, -1):
        state ^= (state << 13) & M32
        state &= M32
        state ^= state >> 17
        state ^= (state << 5) & M32
        state &= M32
        draw = state % (position + 1)
        order[position], order[draw] = order[draw], order[position]
    return order


def unweave(capture, quantities):
    """Payload hex per block with the woven lines standing back in place."""
    blocks = []
    for block in capture['blocks']:
        payloads = list(block['payloads'])
        if capture['flags'] & WOVEN:
            order = weave_order(quantities['weave_seed_offset'], capture['num'],
                                block['bo'], block['width'])
            restated = list(payloads)
            for position in range(min(len(payloads), len(order))):
                restated[order[position]] = payloads[position]
            payloads = restated
        blocks.append(payloads)
    return blocks


def unward_payload(hexed, sentinel):
    raw = bytes.fromhex(hexed)
    out = bytearray()
    index = 0
    while index < len(raw):
        if raw[index] == sentinel:
            if index + 1 < len(raw) and raw[index + 1] == sentinel:
                out.append(sentinel)
                index += 2
            else:
                return None
        else:
            out.append(raw[index])
            index += 1
    return bytes(out) if len(out) == PAYLOAD_LEN else None


def unward(capture, quantities, woven):
    """Per block list of twelve-byte payloads, None where one did not come out."""
    blocks = []
    for payloads in woven:
        row = []
        for hexed in payloads:
            if capture['flags'] & WARDED:
                row.append(unward_payload(hexed, quantities['sentinel_code_value']))
            else:
                raw = bytes.fromhex(hexed)
                row.append(raw if len(raw) == PAYLOAD_LEN else None)
        blocks.append(row)
    return blocks


def block_key(key, num, block_ordinal, modulus):
    return mask(key, 'drift', num, (block_ordinal + 1 + 5 * num) % modulus)


def undrift(key, capture, quantities, unwarded):
    """Per block list of (payload, came_out) with the block mask lifted."""
    blocks = []
    for index, row in enumerate(unwarded):
        ordinal = capture['blocks'][index]['bo']
        if capture['flags'] & DRIFTED:
            keyed = block_key(key, capture['num'], ordinal, quantities['drift_modulus'])
            blocks.append([(xor_bytes(p if p is not None else bytes(PAYLOAD_LEN), keyed),
                            p is not None) for p in row])
        else:
            blocks.append([((p if p is not None else bytes(PAYLOAD_LEN)), p is not None)
                           for p in row])
    return blocks


def unwarded_text(capture, woven, unwarded):
    parts = []
    for index, row in enumerate(unwarded):
        for position, payload in enumerate(row):
            if capture['flags'] & WARDED:
                parts.append(payload.hex() if payload is not None else '0' * 24)
            else:
                parts.append(woven[index][position].lower())
    return ','.join(parts)


def rotate_right(payload, amount):
    amount %= len(payload)
    if amount == 0:
        return payload
    return payload[len(payload) - amount:] + payload[:len(payload) - amount]


def flipped_block(capture):
    if not (capture['flags'] & FLIPPED) or not capture['blocks']:
        return None
    return capture['num'] % len(capture['blocks'])


def unpack(key, payload, little):
    """Read a payload with the shipped layout; the check word stays big endian."""
    if len(payload) != PAYLOAD_LEN:
        return None
    head = payload[:10]
    if payload[10:12] != mask(key, 'entry', *head)[:2]:
        return None
    order = 'little' if little else 'big'
    return {'tick': int.from_bytes(head[0:2], order),
            'index': int.from_bytes(head[2:4], order),
            'kind': head[4],
            'amount': int.from_bytes(head[5:9], order),
            'mark': head[9]}


def stored_entries(key, capture, quantities, undrifted):
    """Filler set aside, then each entry unchained, unsealed, unspun, unpacked."""
    sequence = []
    for index, row in enumerate(undrifted):
        items = list(row)
        if index == 0 and (capture['flags'] & SHADOWED):
            filler = quantities['shadow_pad_base'] - 3
            if filler >= len(items):
                items = []
            elif filler > 0:
                items = items[:len(items) - filler]
        for payload, came_out in items:
            sequence.append((index, payload, came_out))

    flipped = flipped_block(capture)
    label = quantities['labels'][quantities['seal_label_index']]
    entries = []
    prior_tick, prior_amount = 0, 0
    for ordinal, (block_index, payload, came_out) in enumerate(sequence):
        work = payload
        if capture['flags'] & CHAINED:
            work = xor_bytes(work, mask(key, 'chain', capture['num'],
                                        prior_tick, prior_amount))
        if capture['flags'] & SEALED:
            work = xor_bytes(work, mask(key, label, capture['num'], ordinal))
        if capture['flags'] & SPUN:
            work = rotate_right(work, ((ordinal + 1) * quantities['spin_modulus'])
                                % PAYLOAD_LEN)
        fields = unpack(key, work, block_index == flipped) if came_out else None
        entries.append({'block': block_index, 'ordinal': ordinal, 'fields': fields})
        if fields is None:
            prior_tick, prior_amount = 0, 0
        else:
            prior_tick, prior_amount = fields['tick'], fields['amount']
    return entries


def entry_text(fields):
    if fields is None:
        return 'none'
    return '%d/%d/%d/%d/%d' % (fields['tick'], fields['index'], fields['kind'],
                               fields['amount'], fields['mark'])


def restored_ticks(capture, entries):
    stored = [(e['fields']['tick'] if e['fields'] else 0) for e in entries]
    if not (capture['flags'] & STEPPED):
        return stored
    ticks = []
    for index, value in enumerate(stored):
        if index == 0:
            ticks.append(value % TICK_WRAP)
        elif index == 1:
            ticks.append((value + ticks[0]) % TICK_WRAP)
        else:
            ticks.append((value + 2 * ticks[index - 1] - ticks[index - 2]) % TICK_WRAP)
    return ticks


def word_table(capture, captures, quantities):
    if capture['flags'] & ALIASED:
        shift = quantities['alias_donor_shift']
        donor = captures[(capture['num'] + shift) % len(captures)]
        words = donor['words']
        turn = shift % len(words)
        return words[turn:] + words[:turn]
    return quantities['unit_words']


def word_records(key, capture, captures, quantities, entries):
    ticks = restored_ticks(capture, entries)
    table = word_table(capture, captures, quantities)
    records = []
    for index, entry in enumerate(entries):
        fields = entry['fields']
        if fields is None:
            records.append({'none': True, 'ordinal': index})
            continue
        records.append({'none': False, 'ordinal': index, 'tick': ticks[index],
                        'word': table[fields['index'] % len(table)],
                        'kind': fields['kind'], 'amount': fields['amount'],
                        'mark': fields['mark']})
    return records


def word_entry_text(record):
    if record['none']:
        return 'none'
    return '%d/%s/%d/%d/%d' % (record['tick'], record['word'], record['kind'],
                               record['amount'], record['mark'])


def resolve_echoes(capture, records, quantities):
    if not (capture['flags'] & ECHOED):
        return records
    span = quantities['echo_window_span']
    for index, record in enumerate(records):
        if record['none'] or record['kind'] != ECHO_KIND:
            continue
        distance = (index % (span - 1)) + 1 if span > 1 else 1
        source_at = index - distance
        if source_at < 0:
            continue
        source = records[source_at]
        if source['none']:
            continue
        record['word'] = source['word']
        record['kind'] = source['kind']
        record['amount'] = source['amount']
        record['mark'] = source['mark']
    return records


def decode_capture(key, capture, captures, quantities):
    woven = unweave(capture, quantities)
    unwarded = unward(capture, quantities, woven)
    undrifted = undrift(key, capture, quantities, unwarded)
    entries = stored_entries(key, capture, quantities, undrifted)
    records = word_records(key, capture, captures, quantities, entries)
    return resolve_echoes(capture, records, quantities)


def decode_all(context, quantities):
    key = context['key']
    captures = context['captures']
    decoded = []
    for capture in captures:
        for record in decode_capture(key, capture, captures, quantities):
            if record['none']:
                continue
            decoded.append({'capture': capture['num'], 'ordinal': record['ordinal'],
                            'tick': record['tick'], 'word': record['word'],
                            'kind': record['kind'], 'mark': record['mark'],
                            'amount': Fraction(record['amount'])})
    decoded.sort(key=lambda e: (e['tick'], e['capture'], e['ordinal']))
    return decoded


# ----------------------------------------------------------------- settlement

def canonical(word, tick, register):
    """Chase a recorded word to the identity in force at this tick."""
    seen = set()
    while True:
        if word not in register:
            return None
        if word in seen:
            return (word, register[word]['charter'])
        seen.add(word)
        row = register[word]
        if row['successor'] == word:
            return (word, row['charter'])
        if row['closed'] == 0 or tick <= row['closed']:
            return (word, row['charter'])
        if not row['successor']:
            return None
        word = row['successor']


def settling_passes(register, order):
    canon = {word: register[word]['charter'] for word in order}
    passes = 0
    while True:
        passes += 1
        stale = False
        for word in order:
            row = register[word]
            successor = row['successor']
            if (successor and successor != word and successor in register
                    and row['closed'] != 0):
                target = canon[successor]
            else:
                target = row['charter']
            if canon[word] != target:
                canon[word] = target
                stale = True
        if not stale:
            return passes


def charter_baselines(register, order, charters):
    baselines = {charter: 0 for charter in charters}
    counts = {charter: 0 for charter in charters}
    for word in order:
        charter = register[word]['charter']
        baselines[charter] = baselines.get(charter, 0) + register[word]['opened']
        counts[charter] = counts.get(charter, 0) + 1
    return baselines, counts


def settlement(context, quantities):
    cache_key = tuple(quantities.get(name) for name in DECODE_KEYS)
    cached = context['settled_cache'].get(cache_key)
    if cached is not None:
        return cached

    register = context['register']
    live = [w for w in context['windows'] if w['live'] and w['first'] <= w['last']]
    decoded = decode_all(context, quantities)

    decoded_amount = sum((e['amount'] for e in decoded), Fraction(0))
    reversals = sum(1 for e in decoded if e['kind'] == REVERSAL_KIND)

    dropped_retired = 0
    dropped_offwindow = 0
    dropped_amount = Fraction(0)
    surviving = []
    for entry in decoded:
        if entry['kind'] == ECHO_KIND:
            continue
        identity = canonical(entry['word'], entry['tick'], register)
        if identity is None:
            dropped_retired += 1
            dropped_amount += entry['amount']
            continue
        if not any(w['first'] <= entry['tick'] <= w['last'] for w in live):
            dropped_offwindow += 1
            dropped_amount += entry['amount']
            continue
        row = dict(entry)
        row['unit'], row['charter'] = identity
        surviving.append(row)

    # A reversal cancels the earliest still uncancelled entry of its kind that
    # the canonical unit recorded before it. One that cancels nothing is
    # promoted to an ordinary entry of that kind and becomes cancellable itself.
    pools = {}
    for index, entry in enumerate(surviving):
        if entry['kind'] in ORDINARY_KINDS:
            pools.setdefault((entry['unit'], entry['kind']), []).append(index)
    cancelled = set()
    promoted = set()
    for index, entry in enumerate(surviving):
        if entry['kind'] != REVERSAL_KIND:
            continue
        pool = pools.setdefault((entry['unit'], entry['mark']), [])
        target = None
        for candidate in pool:
            if candidate < index and candidate not in cancelled:
                target = candidate
                break
        if target is None:
            promoted.add(index)
            bisect.insort(pool, index)
        else:
            cancelled.add(target)

    settled = []
    for index, entry in enumerate(surviving):
        if index in cancelled:
            continue
        if entry['kind'] == REVERSAL_KIND and index not in promoted:
            continue
        row = dict(entry)
        row['effective'] = (entry['mark'] if entry['kind'] == REVERSAL_KIND
                            else entry['kind'])
        settled.append(row)

    # Allowances stand at full cap from the first tick of every live window and
    # are drawn down in the walk order the reversal rules use.
    baselines = context['baselines']
    counts = context['counts']
    caps = {c: Fraction(baselines.get(c, 0) * counts.get(c, 0))
            for c in context['charters']}
    allowance = dict(caps)
    renewals = sorted({w['first'] for w in live})
    next_renewal = 0
    for entry in settled:
        while next_renewal < len(renewals) and renewals[next_renewal] <= entry['tick']:
            allowance = dict(caps)
            next_renewal += 1
        left = allowance.get(entry['charter'], Fraction(0))
        drawn = entry['amount'] if entry['amount'] <= left else left
        allowance[entry['charter']] = left - drawn
        entry['drawn'] = drawn
        entry['surplus'] = entry['amount'] - drawn

    result = {'decoded': decoded, 'decoded_amount': decoded_amount,
              'reversals': reversals, 'surviving': surviving, 'settled': settled,
              'cancelled': cancelled, 'promoted': promoted,
              'dropped_retired': dropped_retired,
              'dropped_offwindow': dropped_offwindow,
              'dropped_amount': dropped_amount}
    context['settled_cache'][cache_key] = result
    return result


def unit_rollup(context, quantities, run):
    register = context['register']
    units = {}
    for entry in run['surviving']:
        units.setdefault(entry['unit'], {
            'unit': entry['unit'],
            'charter': register[entry['unit']]['charter'],
            'tick_total': 0,
            'amount_total': Fraction(0),
            'kind_totals': [Fraction(0), Fraction(0), Fraction(0)]})
    for entry in run['settled']:
        unit = units[entry['unit']]
        unit['tick_total'] += entry['tick']
        unit['amount_total'] += entry['drawn']
        if entry['effective'] in ORDINARY_KINDS:
            unit['kind_totals'][entry['effective']] += entry['drawn']
    modulus = quantities.get('cadence_modulus')
    classes = quantities['cadence']
    for unit in units.values():
        if modulus:
            unit['cadence'] = classes[(unit['tick_total'] // modulus) % len(classes)]
    return [units[word] for word in sorted(units)]


def charter_stocks(context, run):
    """Solve the coupled charter relations exactly by elimination."""
    charters = context['charters']
    baselines = context['baselines']
    opening = context['opening_charter']
    scale = sum(baselines.get(c, 0) for c in charters)

    flows = {}
    for entry in run['settled']:
        if entry['effective'] != 1:
            continue
        origin = opening.get(entry['word'])
        target = entry['charter']
        if origin is None or origin == target:
            continue
        flows[(origin, target)] = flows.get((origin, target), Fraction(0)) + entry['drawn']
    shares = ({pair: amount / scale for pair, amount in flows.items()}
              if scale else {})

    size = len(charters)
    index = {charter: i for i, charter in enumerate(charters)}
    matrix = [[Fraction(0)] * (size + 1) for _ in range(size)]
    for charter in charters:
        row = index[charter]
        matrix[row][row] = Fraction(1)
        for other in charters:
            if other == charter:
                continue
            share = shares.get((other, charter))
            if share:
                matrix[row][index[other]] -= share
        matrix[row][size] = Fraction(baselines.get(charter, 0))

    for column in range(size):
        pivot = None
        for candidate in range(column, size):
            if matrix[candidate][column] != 0:
                pivot = candidate
                break
        if pivot is None:
            continue
        matrix[column], matrix[pivot] = matrix[pivot], matrix[column]
        divisor = matrix[column][column]
        matrix[column] = [value / divisor for value in matrix[column]]
        for row in range(size):
            if row != column and matrix[row][column] != 0:
                factor = matrix[row][column]
                matrix[row] = [a - factor * b for a, b in zip(matrix[row], matrix[column])]
    return {charter: matrix[index[charter]][size] for charter in charters}


# ---------------------------------------------------------------- calibration

def produce(name, quantities, context):
    """Reproduce the control figure the published row for `name` describes."""
    key = context['key']
    captures = context['captures']

    if name == 'frame_bias_limit':
        limit = quantities['frame_bias_limit']
        fragments = []
        for capture in captures:
            bias = (3 * capture['num'] + 1) % limit if (capture['flags'] & PADDED) else 0
            fragments.append('%d:%d' % (capture['num'], bias))
        return control_figure(key, fragments)

    if name == 'weave_seed_offset':
        fragments = []
        for capture in captures:
            woven = unweave(capture, quantities)
            payloads = ','.join(p.lower() for block in woven for p in block)
            fragments.append('%d:%s' % (capture['num'], payloads))
        return control_figure(key, fragments)

    if name == 'sentinel_code_value':
        fragments = []
        for capture in captures:
            woven = unweave(capture, quantities)
            unwarded = unward(capture, quantities, woven)
            fragments.append('%d:%s' % (capture['num'],
                                        unwarded_text(capture, woven, unwarded)))
        return control_figure(key, fragments)

    if name == 'drift_modulus':
        fragments = []
        for capture in captures:
            undrifted = undrift(key, capture, quantities,
                                unward(capture, quantities, unweave(capture, quantities)))
            payloads = ','.join(p.hex() for block in undrifted for p, _ in block)
            fragments.append('%d:%s' % (capture['num'], payloads))
        return control_figure(key, fragments)

    if name in ('seal_label_index', 'spin_modulus'):
        label = quantities['labels'][quantities['seal_label_index']]
        fragments = []
        for capture in captures:
            undrifted = undrift(key, capture, quantities,
                                unward(capture, quantities, unweave(capture, quantities)))
            if not undrifted or not undrifted[0]:
                fragments.append('%d:%s' % (capture['num'], 'none'))
                continue
            payload, came_out = undrifted[0][0]
            if capture['flags'] & CHAINED:
                payload = xor_bytes(payload, mask(key, 'chain', capture['num'], 0, 0))
            if capture['flags'] & SEALED:
                payload = xor_bytes(payload, mask(key, label, capture['num'], 0))
            if name == 'seal_label_index':
                fragments.append('%d:%s' % (capture['num'], payload.hex()))
                continue
            if capture['flags'] & SPUN:
                payload = rotate_right(payload, quantities['spin_modulus'] % PAYLOAD_LEN)
            fields = unpack(key, payload, flipped_block(capture) == 0) if came_out else None
            fragments.append('%d:%s' % (capture['num'], entry_text(fields)))
        return control_figure(key, fragments)

    if name == 'shadow_pad_base':
        fragments = []
        for capture in captures:
            undrifted = undrift(key, capture, quantities,
                                unward(capture, quantities, unweave(capture, quantities)))
            entries = stored_entries(key, capture, quantities, undrifted)
            texts = ','.join(entry_text(e['fields']) for e in entries)
            fragments.append('%d:%s' % (capture['num'], texts))
        return control_figure(key, fragments)

    if name == 'alias_donor_shift':
        fragments = []
        for capture in captures:
            undrifted = undrift(key, capture, quantities,
                                unward(capture, quantities, unweave(capture, quantities)))
            entries = stored_entries(key, capture, quantities, undrifted)
            records = word_records(key, capture, captures, quantities, entries)
            texts = ','.join(word_entry_text(r) for r in records)
            fragments.append('%d:%s' % (capture['num'], texts))
        return control_figure(key, fragments)

    if name == 'echo_window_span':
        fragments = []
        for capture in captures:
            records = decode_capture(key, capture, captures, quantities)
            texts = ','.join(word_entry_text(r) for r in records)
            fragments.append('%d:%s' % (capture['num'], texts))
        return control_figure(key, fragments)

    if name == 'cadence_modulus':
        units = unit_rollup(context, quantities, settlement(context, quantities))
        return control_figure(key, ['%s:%s' % (u['unit'], u['cadence']) for u in units])

    if name == 'upkeep_target_scale':
        target = Fraction(quantities['upkeep_target_scale']
                          * sum(context['baselines'].get(c, 0)
                                for c in context['charters']))
        return control_figure(key, ['%d/%d' % (target.numerator, target.denominator)])

    raise ValueError('no producer for quantity %r' % name)


def calibrate(context, rows, published):
    """Pin every withheld quantity against its own control, in published order.

    A candidate is recorded as rejected the moment no surviving assignment
    carries it any more, against the control figure that separated it.
    """
    base = {'labels': context['labels'], 'unit_words': context['unit_words'],
            'cadence': context['cadence']}
    branches = [dict(base)]
    rejected = {row['name']: [] for row in rows}
    for position, row in enumerate(rows):
        name, control = row['name'], row['control']
        figure = published.get(control)
        survivors = []
        for branch in branches:
            for candidate in row['candidates']:
                trial = dict(branch)
                trial[name] = candidate
                if produce(name, trial, context) == figure:
                    survivors.append(trial)
        if not survivors:
            raise SystemExit('calibration failed at %s (%s)' % (control, name))
        for earlier in rows[:position + 1]:
            held = earlier['name']
            alive = {branch[held] for branch in survivors}
            before = (set(earlier['candidates']) if earlier is row
                      else {branch[held] for branch in branches})
            already = {item['candidate'] for item in rejected[held]}
            for candidate in sorted(earlier['candidates']):
                if candidate in before and candidate not in alive \
                        and candidate not in already:
                    rejected[held].append({'candidate': candidate, 'falsifier': control})
        branches = survivors
    for row in rows:
        rejected[row['name']].sort(key=lambda item: item['candidate'])
    return branches[0], rejected


# --------------------------------------------------------------------- upkeep

def find_bench(candidates, target):
    """The one subset of the candidate list whose upkeep meets the target."""
    if target < 0:
        return None
    if target == 0:
        return []
    limit = int(target)
    if limit != target:
        return None
    reachable = {0: ()}
    for word, upkeep in candidates:
        if upkeep > limit:
            continue
        grown = dict(reachable)
        for total, chosen in reachable.items():
            moved = total + upkeep
            if moved <= limit and moved not in grown:
                grown[moved] = chosen + (word,)
        reachable = grown
    found = reachable.get(limit)
    return sorted(found) if found is not None else None


# -------------------------------------------------------------------- reports

def rational(value):
    value = Fraction(value)
    return '%d/%d' % (value.numerator, value.denominator)


def write_report(report_dir, name, payload):
    with open(os.path.join(report_dir, name), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(json.dumps(payload, indent=2))
        fh.write('\n')


def build_reports(context, quantities, rows, published, rejected, report_dir):
    run = settlement(context, quantities)
    units = unit_rollup(context, quantities, run)

    write_report(report_dir, 'scenario_visible.json', {
        'capture_count': len(context['captures']),
        'entry_total': len(run['decoded']),
        'settled_total': len(run['settled']),
        'units': [{'unit': u['unit'], 'charter': u['charter'],
                   'tick_total': u['tick_total'],
                   'amount_total': rational(u['amount_total']),
                   'cadence': u['cadence'],
                   'kind_totals': [rational(k) for k in u['kind_totals']]}
                  for u in units]})

    for cadence in context['cadence']:
        held = [u for u in units if u['cadence'] == cadence]
        write_report(report_dir, 'scenario_%s.json' % cadence, {
            'cadence': cadence,
            'unit_count': len(held),
            'amount_total': rational(sum((u['amount_total'] for u in held), Fraction(0))),
            'units': [{'unit': u['unit'], 'charter': u['charter'],
                       'tick_total': u['tick_total'],
                       'amount_total': rational(u['amount_total'])} for u in held]})

    stocks = charter_stocks(context, run)
    settled_amount = sum((e['drawn'] for e in run['settled']), Fraction(0))
    write_report(report_dir, 'perf_report.json', {
        'charter_stocks': [{'charter': charter, 'stock': rational(stocks[charter])}
                           for charter in sorted(stocks)],
        'settled_total': rational(settled_amount),
        'decoded_total': rational(run['decoded_amount']),
        'reversal_count': run['reversals'],
        'promoted_reversal_count': len(run['promoted'])})

    target = Fraction(quantities['upkeep_target_scale']
                      * sum(context['baselines'].get(c, 0) for c in context['charters']))
    bench = find_bench(context['bench'], target) or []
    upkeep = Fraction(sum(dict(context['bench'])[word] for word in bench))
    write_report(report_dir, 'recommendations.json', {
        'target': rational(target),
        'bench': bench,
        'bench_upkeep': rational(upkeep),
        'residual_after_bench': rational(target - upkeep)})

    write_report(report_dir, 'data_quality.json', {
        'dropped_retired': run['dropped_retired'],
        'dropped_offwindow': run['dropped_offwindow'],
        'dropped_amount_total': rational(run['dropped_amount']),
        'decoded_amount_total': rational(run['decoded_amount']),
        'settled_amount_total': rational(settled_amount),
        'conservation_residual': rational(run['decoded_amount'] - settled_amount
                                          - run['dropped_amount'])})

    write_report(report_dir, 'bottleneck_analysis.json', {
        'quantities': [{'name': row['name'], 'value': quantities[row['name']],
                        'control': row['control'],
                        'rejected': rejected[row['name']]} for row in rows],
        'settling_passes': settling_passes(context['register'], context['order']),
        'calibration_table': [{'control': row['control'],
                               'published': published.get(row['control'], ''),
                               'produced': produce(row['name'], quantities, context)}
                              for row in rows]})


# ----------------------------------------------------------------------- main

def main(argv):
    if len(argv) < 3:
        print(__doc__.strip())
        return 2
    capture_dir, report_dir = argv[1], argv[2]
    os.makedirs(report_dir, exist_ok=True)
    for name in REPORT_NAMES:
        stale = os.path.join(report_dir, name)
        if os.path.exists(stale):
            os.remove(stale)

    notes = parse_notes(capture_dir)
    rows, published = parse_calibration(capture_dir)
    register, order = parse_roster(capture_dir)
    charters = list(notes['charters'])
    for word in order:
        if register[word]['charter'] not in charters:
            charters.append(register[word]['charter'])
    charters.sort()
    baselines, counts = charter_baselines(register, order, charters)

    context = {'key': notes['key'], 'labels': notes['labels'],
               'unit_words': notes['unit_words'], 'cadence': notes['cadence'],
               'charters': charters, 'captures': parse_captures(capture_dir),
               'register': register, 'order': order,
               'opening_charter': {w: register[w]['charter'] for w in order},
               'windows': parse_windows(capture_dir),
               'bench': parse_bench(capture_dir),
               'baselines': baselines, 'counts': counts, 'settled_cache': {}}

    quantities, rejected = calibrate(context, rows, published)
    build_reports(context, quantities, rows, published, rejected, report_dir)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
