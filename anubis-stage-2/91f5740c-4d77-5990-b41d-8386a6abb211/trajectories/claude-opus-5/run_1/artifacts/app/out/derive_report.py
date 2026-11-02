#!/usr/bin/env python3
"""Meridian corridor authority season settlement.

Usage: derive_report.py <input_dir> <output_dir>

Everything the program writes is derived from the corpus it is handed: the wire
constants are recovered from the published calibration controls, the policy
parameters are read out of the policy documents, and no figure of any supplied
corpus is baked in.
"""

import binascii
import csv
import hashlib
import hmac
import json
import os
import re
import sys
import zlib
from math import gcd

# ---------------------------------------------------------------------------
# wire format structure (packet_encoding.md, "Block header" / "Work order record")
# ---------------------------------------------------------------------------

HEADER_WIDTH = 24
AUX_OFFSETS = (8, 10, 12, 14)
SHORT_RECORD = 13
LONG_RECORD = 15
MASK64 = (1 << 64) - 1
DAY_MODULUS = 251

FLAG_LOAD_MASK = 0x001
FLAG_SLACK_FOLD = 0x002
FLAG_WEIGHT_DIFF = 0x004
FLAG_DAY_DRIFT = 0x008
FLAG_PERMUTE = 0x010
FLAG_BACKREF = 0x020
FLAG_ISLAND = 0x040
FLAG_LEN_SHADOW = 0x080
FLAG_ALIAS_ROTOR = 0x100
FLAG_ROTATION = 0x200
FLAG_COUNT_BIAS = 0x400

BACKREF_FLOOR = 0xF0

# the four quantisation modes capacity_policy.md names, in the order it names them
QUANT_MODES = (
    'discard_remainder',
    'advance_to_next_multiple',
    'closer_multiple_midpoint_up',
    'discard_unless_three_quarters',
)

# the constant each control figure settles, in the order the controls are published
CONTROL_FOR_PARAM = (
    ('rotate_step', 'payload_origin_total'),
    ('shadow_bias', 'record_span_total'),
    ('count_bias', 'calibration_order_total'),
    ('island_offset', 'island_field_total'),
    ('permute_rounds', 'ordinal_position_checksum'),
    ('stream_label', 'masked_load_total'),
    ('chain_seed', 'folded_slack_total'),
    ('delta_span', 'delta_weight_total'),
    ('drift_modulus', 'drift_day_total'),
    ('alias_rotor', 'canonical_client_total'),
    ('window_span', 'backref_program_total'),
    ('quant_mode', 'billable_slot_total'),
)

# the transform table of packet_encoding.md spells the constants in prose
DOC_PARAM_NAMES = {
    'stream label': 'stream_label',
    'chain seed': 'chain_seed',
    'delta span': 'delta_span',
    'drift modulus': 'drift_modulus',
    'permute rounds': 'permute_rounds',
    'window span': 'window_span',
    'island offset': 'island_offset',
    'shadow bias': 'shadow_bias',
    'alias rotor': 'alias_rotor',
    'rotate step': 'rotate_step',
    'count bias': 'count_bias',
}


# ---------------------------------------------------------------------------
# corpus reading
# ---------------------------------------------------------------------------

def read_table(path):
    with open(path, newline='', encoding='utf-8') as fh:
        reader = csv.DictReader(fh)
        out = []
        for row in reader:
            out.append({(k or '').strip(): (v or '').strip() for k, v in row.items()})
        return out


def read_text(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def parse_labelled_list(text, label):
    """Pull `label: a, b, c` out of a policy document."""
    m = re.search(r'^\s*[-*]?\s*' + re.escape(label) + r'\s*:\s*(.+)$', text, re.M)
    if not m:
        raise ValueError('policy label %r not found' % label)
    return [piece.strip() for piece in m.group(1).split(',') if piece.strip()]


def parse_labelled_map(text, label):
    out = {}
    for piece in parse_labelled_list(text, label):
        key, _, value = piece.partition('=')
        out[key.strip()] = int(value.strip())
    return out


def parse_domain(cell):
    """Read a `Constant range` cell of the transform table."""
    through = re.match(r'^(\d+)\s+through\s+(\d+)$', cell)
    if through:
        lo, hi = int(through.group(1)), int(through.group(2))
        return list(range(lo, hi + 1))
    pieces = [p.strip() for p in cell.split(',') if p.strip()]
    if all(re.match(r'^\d+$', p) for p in pieces):
        return [int(p) for p in pieces]
    return pieces


def parse_encoding_doc(text):
    """Domains of the withheld constants, and the wire format literals the
    encoding document publishes."""
    key = re.search(r'key\s+`([^`]+)`', text)
    magic = re.search(r'magic word, always (0[xX][0-9A-Fa-f]+)', text)
    prefix = re.search(r'ASCII text `([^`]+)` followed by', text)
    if not (key and magic and prefix):
        raise ValueError('the encoding document does not publish the wire literals')
    literals = {'hmac_key': key.group(1).encode('utf-8'),
                'magic_word': int(magic.group(1), 16),
                'seed_prefix': prefix.group(1).encode('ascii')}
    domains = {}
    for line in text.splitlines():
        if not line.strip().startswith('|'):
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) != 4:
            continue
        name = DOC_PARAM_NAMES.get(cells[2].lower())
        if name:
            domains[name] = parse_domain(cells[3])
    m = re.search(r'granularity from the list ([0-9,\s]+) by position', text)
    if not m:
        raise ValueError('granularity list not found')
    literals['granularities'] = [int(p) for p in m.group(1).split(',') if p.strip()]
    return domains, literals


def parse_controls(text):
    out = {}
    for m in re.finditer(r'^\s*[-*]\s*([a-z_]+)\s*=\s*(-?\d+)\s*$', text, re.M):
        out[m.group(1)] = int(m.group(2))
    return out


class Corpus(object):
    def __init__(self, indir):
        self.dir = indir
        encoding_doc = read_text(os.path.join(indir, 'packet_encoding.md'))
        self.domains, literals = parse_encoding_doc(encoding_doc)
        self.hmac_key = literals['hmac_key']
        self.magic_word = literals['magic_word']
        self.seed_prefix = literals['seed_prefix']
        self.granularities = literals['granularities']
        self.domains['quant_mode'] = list(QUANT_MODES)
        self.controls = parse_controls(read_text(os.path.join(indir, 'calibration_slice.md')))

        capacity_doc = read_text(os.path.join(indir, 'capacity_policy.md'))
        self.congestion_bounds = [int(x) for x in parse_labelled_list(capacity_doc, 'congestion_bounds')]
        self.base_ceiling = parse_labelled_map(capacity_doc, 'base_ceiling')
        self.tier_factor = {int(k): v for k, v in parse_labelled_map(capacity_doc, 'tier_factor').items()}

        cost_doc = read_text(os.path.join(indir, 'cost_policy.md'))
        self.rebate_band = {int(k): v for k, v in parse_labelled_map(cost_doc, 'rebate_band').items()}

        dispatch_doc = read_text(os.path.join(indir, 'dispatch_policy.md'))
        self.incompatible = []
        for piece in parse_labelled_list(dispatch_doc, 'incompatible_families'):
            left, _, right = piece.partition('|')
            self.incompatible.append((left.strip(), right.strip()))

        self.sites = read_table(os.path.join(indir, 'site_directory.csv'))
        self.clients = read_table(os.path.join(indir, 'client_directory.csv'))
        self.lanes = read_table(os.path.join(indir, 'lane_roster.csv'))
        self.registry = read_table(os.path.join(indir, 'program_registry.csv'))

        manifest = read_table(os.path.join(indir, 'block_manifest.csv'))
        headers = {}
        for row in manifest:
            headers[(row['population'], int(row['block_id']))] = binascii.unhexlify(row['header_hex'])
        self.headers = headers
        self.populations = {}
        for pop, fname in (('calibration', 'calibration_orders.csv'), ('field', 'field_orders.csv')):
            path = os.path.join(indir, fname)
            blocks = []
            for row in read_table(path):
                bid = int(row['block_id'])
                blocks.append(Block(bid, headers[(pop, bid)],
                                    binascii.unhexlify(row['payload_hex']), self.magic_word))
            blocks.sort(key=lambda b: b.bid)
            self.populations[pop] = blocks

        self.prog_ids = sorted({r['program_id'] for r in self.registry})
        self.families = sorted({r['family'] for r in self.registry})


class Block(object):
    __slots__ = ('bid', 'header', 'payload', 'flags', 'stored')

    def __init__(self, bid, header, payload, magic_word):
        self.bid = bid
        self.header = header
        self.payload = payload
        if len(header) != HEADER_WIDTH:
            raise ValueError('block %d: header width' % bid)
        if int.from_bytes(header[0:2], 'big') != magic_word:
            raise ValueError('block %d: magic word' % bid)
        if int.from_bytes(header[2:4], 'big') != bid:
            raise ValueError('block %d: identifier' % bid)
        if zlib.crc32(header[0:20]) != int.from_bytes(header[20:24], 'big'):
            raise ValueError('block %d: header checksum' % bid)
        if zlib.crc32(payload) != int.from_bytes(header[16:20], 'big'):
            raise ValueError('block %d: payload checksum' % bid)
        self.flags = int.from_bytes(header[6:8], 'big')
        self.stored = int.from_bytes(header[4:6], 'big')

    def has(self, bit):
        return bool(self.flags & bit)


# ---------------------------------------------------------------------------
# wire transforms
# ---------------------------------------------------------------------------

def xorshift64(x):
    x ^= (x << 13) & MASK64
    x &= MASK64
    x ^= x >> 7
    x ^= (x << 17) & MASK64
    return x & MASK64


def block_seed(corpus, bid, aux):
    msg = corpus.seed_prefix + bid.to_bytes(2, 'big') \
        + b''.join(w.to_bytes(2, 'big') for w in aux)
    return int.from_bytes(hmac.new(corpus.hmac_key, msg, hashlib.sha256).digest()[:8], 'big')


def permutation(count, seed, rounds):
    out = list(range(count))
    state = seed
    for _ in range(rounds):
        for i in range(count - 1, 0, -1):
            state = xorshift64(state)
            j = state % (i + 1)
            out[i], out[j] = out[j], out[i]
    return out


def load_mask(corpus, label, bid, ordinal):
    msg = label.encode('utf-8') + b'|' + bid.to_bytes(2, 'big') + ordinal.to_bytes(2, 'big')
    return int.from_bytes(hmac.new(corpus.hmac_key, msg, hashlib.sha256).digest()[:4], 'big')


def unrotate(block, rotate_step):
    payload = block.payload
    if not block.has(FLAG_ROTATION):
        return payload
    n = len(payload)
    k = (block.bid * rotate_step) % n
    return payload[n - k:] + payload[:n - k]


def aux_words(block, island_offset):
    out = []
    for off in AUX_OFFSETS:
        word = block.header[off:off + 2]
        little = block.has(FLAG_ISLAND) and off == island_offset
        out.append(int.from_bytes(word, 'little' if little else 'big'))
    return out


class Record(object):
    __slots__ = ('bid', 'ordinal', 'physical', 'order_id', 'genuine', 'length_code',
                 'mode', 'alias_raw', 'prog_raw', 'load', 'due_offset', 'weight',
                 'gran_code', 'day', 'ext_slack', 'due_slot', 'granularity',
                 'alias_key', 'program_id')


def split_records(block, params):
    """Physical record split of the de-rotated payload."""
    payload = unrotate(block, params['rotate_step'])
    bias = params['shadow_bias'] if block.has(FLAG_LEN_SHADOW) else 0
    out = []
    i = 0
    n = len(payload)
    while i < n:
        code = (payload[i] >> 4) ^ bias
        if code == 0:
            width = SHORT_RECORD
        elif code == 1:
            width = LONG_RECORD
        else:
            return None
        if i + width > n:
            return None
        out.append((code, payload[i:i + width]))
        i += width
    if i != n or len(out) != block.stored:
        return None
    return out


def decode_blocks(blocks, params, corpus):
    """Decode one population. Returns a list of block dicts or None on a bad parse."""
    label = params['stream_label']
    rotor = params['alias_rotor']
    span = params['delta_span']
    modulus = params['drift_modulus']
    seed_value = params['chain_seed']
    window = params['window_span']
    bias = params['count_bias']
    rounds = params['permute_rounds']
    island = params['island_offset']
    clients = corpus.clients
    nclients = len(clients)
    prog_ids = corpus.prog_ids
    nprogs = len(prog_ids)
    grans = corpus.granularities

    running_load = 0
    out = []
    for block in blocks:
        physical = split_records(block, params)
        if physical is None:
            return None
        count = block.stored
        aux = aux_words(block, island)
        if block.has(FLAG_PERMUTE):
            perm = permutation(count, block_seed(corpus, block.bid, aux), rounds)
        else:
            perm = list(range(count))
        logical = [None] * count
        for pos in range(count):
            logical[perm[pos]] = (pos, physical[pos])
        genuine = count - (bias if block.has(FLAG_COUNT_BIAS) else 0)
        if genuine < 0:
            return None
        horizon = aux[1]

        records = []
        prev_due = seed_value
        group_prev = 0
        group_delta = 0
        for ordinal in range(count):
            pos, (code, raw) = logical[ordinal]
            rec = Record()
            rec.bid = block.bid
            rec.ordinal = ordinal
            rec.physical = pos
            rec.order_id = 'W%04d%02d' % (block.bid, ordinal)
            rec.genuine = ordinal < genuine
            rec.length_code = code
            rec.mode = raw[0] & 0x0F
            rec.alias_raw = raw[1]
            rec.prog_raw = raw[2]
            rec.ext_slack = int.from_bytes(raw[13:15], 'big') if code == 1 else 0
            rec.gran_code = raw[11]
            if rec.gran_code >= len(grans):
                raise ValueError('block %d ordinal %d: granularity code %d is off the list'
                                 % (block.bid, ordinal, rec.gran_code))
            rec.granularity = grans[rec.gran_code]

            load = int.from_bytes(raw[3:7], 'big')
            if block.has(FLAG_LOAD_MASK):
                load ^= load_mask(corpus, label, block.bid, ordinal)
            rec.load = load

            due = int.from_bytes(raw[7:9], 'big')
            if block.has(FLAG_SLACK_FOLD):
                due = (due - prev_due) % 65536
            prev_due = due
            rec.due_offset = due
            rec.due_slot = horizon + due + rec.ext_slack

            weight = int.from_bytes(raw[9:11], 'big')
            if block.has(FLAG_WEIGHT_DIFF):
                place = ordinal % span
                if place == 0:
                    group_prev = weight
                    group_delta = 0
                elif place == 1:
                    group_delta = weight
                    group_prev = (group_prev + group_delta) % 65536
                else:
                    group_delta = (group_delta + weight) % 65536
                    group_prev = (group_prev + group_delta) % 65536
                weight = group_prev
            rec.weight = weight

            day = raw[12]
            if block.has(FLAG_DAY_DRIFT):
                factor = 1 + running_load % (modulus - 1)
                day = day * pow(factor, -1, DAY_MODULUS) % DAY_MODULUS
            rec.day = day
            if rec.genuine:
                running_load += rec.load

            pos_alias = rec.alias_raw % nclients
            if block.has(FLAG_ALIAS_ROTOR):
                pos_alias = (pos_alias - rotor) % nclients
            rec.alias_key = clients[pos_alias]['alias_key']

            rec.program_id = None
            records.append(rec)

        for rec in records:
            if rec.prog_raw >= BACKREF_FLOOR and block.has(FLAG_BACKREF):
                continue
            rec.program_id = prog_ids[rec.prog_raw % nprogs]
        for rec in records:
            if rec.program_id is not None:
                continue
            target = rec.ordinal
            for _ in range(count):
                back = (records[target].prog_raw - BACKREF_FLOOR) % window + 1
                target -= back
                if target < 0:
                    break
                if records[target].program_id is not None:
                    rec.program_id = records[target].program_id
                    break
        out.append({'block': block, 'aux': aux, 'perm': perm, 'genuine': genuine,
                    'records': records})
    return out


# ---------------------------------------------------------------------------
# identity, revision and quantisation rules
# ---------------------------------------------------------------------------

def client_tables(clients):
    by_alias = {}
    by_id = {}
    for row in clients:
        if row['alias_key'] in by_alias:
            raise ValueError('alias key %s is not unique' % row['alias_key'])
        by_alias[row['alias_key']] = row
        by_id[row['client_id']] = row
    governing = {}
    for row in clients:
        seen = [row['client_id']]
        cur = row
        while True:
            target = cur.get('merged_into', '')
            if not target:
                governing[row['client_id']] = cur['client_id']
                break
            if target in seen:
                cycle = seen[seen.index(target):]
                governing[row['client_id']] = min(cycle)
                break
            seen.append(target)
            cur = by_id[target]
    return by_alias, by_id, governing


def revision_index(registry):
    out = {}
    for row in registry:
        out.setdefault(row['program_id'], []).append(
            (int(row['revision']), int(row['effective_from']), int(row['effective_to']), row['family']))
    for key in out:
        out[key].sort(key=lambda t: -t[0])
    return out


def governing_revision(index, program_id, day):
    for revision, start, stop, family in index.get(program_id, ()):
        if start <= day < stop:
            return revision, family
    return None


def quantise(load, granularity, mode):
    remainder = load % granularity
    if remainder == 0:
        return load
    down = load - remainder
    if mode == 'discard_remainder':
        return down
    if mode == 'advance_to_next_multiple':
        return down + granularity
    if mode == 'closer_multiple_midpoint_up':
        return down + granularity if 2 * remainder >= granularity else down
    if mode == 'discard_unless_three_quarters':
        return down + granularity if 4 * remainder >= 3 * granularity else down
    raise ValueError('unknown quantisation mode %r' % mode)


def numeric_part(identifier):
    digits = re.findall(r'\d+', identifier)
    return int(digits[-1]) if digits else 0


# ---------------------------------------------------------------------------
# control figures
# ---------------------------------------------------------------------------

def control_payload_origin(corpus, params):
    total = 0
    for block in corpus.populations['calibration']:
        total += int.from_bytes(unrotate(block, params['rotate_step'])[0:4], 'big')
    return total


def control_record_span(corpus, params):
    total = 0
    for block in corpus.populations['calibration']:
        physical = split_records(block, params)
        if physical is None:
            return None
        total += sum(1 for code, _ in physical if code == 1)
    return total


def control_order_count(corpus, params):
    total = 0
    for block in corpus.populations['calibration']:
        genuine = block.stored - (params['count_bias'] if block.has(FLAG_COUNT_BIAS) else 0)
        if genuine < 0:
            return None
        total += genuine
    return total


def control_island(corpus, params):
    total = 0
    for block in corpus.populations['calibration']:
        total += sum(aux_words(block, params['island_offset']))
    return total


def control_ordinal_positions(corpus, params):
    total = 0
    for block in corpus.populations['calibration']:
        count = block.stored
        if block.has(FLAG_PERMUTE):
            aux = aux_words(block, params['island_offset'])
            perm = permutation(count, block_seed(corpus, block.bid, aux),
                               params['permute_rounds'])
        else:
            perm = list(range(count))
        total += sum((pos + 1) * (perm[pos] + 1) for pos in range(count))
    return total


def _genuine(decoded):
    for blk in decoded:
        for rec in blk['records']:
            if rec.genuine:
                yield rec


def control_from_decode(name, corpus, params):
    decoded = decode_blocks(corpus.populations['calibration'], params, corpus)
    if decoded is None:
        return None
    if name == 'masked_load_total':
        return sum(r.load for r in _genuine(decoded))
    if name == 'folded_slack_total':
        return sum(r.due_offset for r in _genuine(decoded))
    if name == 'delta_weight_total':
        return sum(r.weight for r in _genuine(decoded))
    if name == 'drift_day_total':
        return sum(r.day * (1 + r.ordinal) for r in _genuine(decoded))
    if name == 'canonical_client_total':
        by_alias, _, governing = client_tables(corpus.clients)
        total = 0
        for rec in _genuine(decoded):
            row = by_alias.get(rec.alias_key)
            if row is None:
                return None
            total += numeric_part(governing[row['client_id']]) * (1 + rec.ordinal)
        return total
    if name == 'backref_program_total':
        position = {pid: i for i, pid in enumerate(corpus.prog_ids)}
        total = 0
        for rec in _genuine(decoded):
            if rec.program_id is None:
                return None
            total += position[rec.program_id] * (1 + rec.ordinal)
        return total
    if name == 'billable_slot_total':
        scored = score_population(decoded, corpus, params)
        return sum(o['billable'] for o in scored['scored'])
    raise ValueError('unknown control %r' % name)


CONTROL_FUNCS = {
    'payload_origin_total': control_payload_origin,
    'record_span_total': control_record_span,
    'calibration_order_total': control_order_count,
    'island_field_total': control_island,
    'ordinal_position_checksum': control_ordinal_positions,
}


def evaluate_control(name, corpus, params):
    func = CONTROL_FUNCS.get(name)
    try:
        if func is not None:
            return func(corpus, params)
        return control_from_decode(name, corpus, params)
    except (ValueError, IndexError, KeyError, ZeroDivisionError):
        return None


def resolve_constants(corpus):
    """Settle every withheld constant against the calibration controls, in order."""
    params = {}
    for name, _ in CONTROL_FOR_PARAM:
        params[name] = corpus.domains[name][0]
    audit = []
    for name, control in CONTROL_FOR_PARAM:
        if control not in corpus.controls:
            raise ValueError('control %r is not published' % control)
        published = corpus.controls[control]
        domain = corpus.domains[name]
        verdicts = []
        accepted = None
        for candidate in domain:
            params[name] = candidate
            value = evaluate_control(control, corpus, params)
            ok = value == published
            verdicts.append({'value': candidate, 'verdict': 'accepted' if ok else 'rejected'})
            if ok:
                if accepted is not None:
                    raise ValueError('control %r does not separate %r' % (control, name))
                accepted = candidate
        if accepted is None:
            raise ValueError('no candidate for %r reproduces %s' % (name, control))
        params[name] = accepted
        audit.append({
            'parameter': name,
            'control': control,
            'domain_size': len(domain),
            'resolved': accepted,
            'rejected': len(domain) - 1,
            'verdicts': verdicts,
        })
    return params, audit


# ---------------------------------------------------------------------------
# admission
# ---------------------------------------------------------------------------

def score_population(decoded, corpus, params):
    """Apply the identity and revision policies to a decoded population."""
    by_alias, by_id, governing = client_tables(corpus.clients)
    index = revision_index(corpus.registry)
    mode = params['quant_mode']
    scored, deferred_identity, rejected = [], [], []
    for blk in decoded:
        for rec in blk['records']:
            if not rec.genuine:
                continue
            row = by_alias[rec.alias_key]
            client = by_id[governing[row['client_id']]]
            retired = client.get('retired_on', '')
            if retired != '' and rec.day >= int(retired):
                rejected.append(rec.order_id)
                continue
            revision = governing_revision(index, rec.program_id, rec.day)
            if revision is None:
                rejected.append(rec.order_id)
                continue
            effective = client.get('effective_from', '')
            if effective != '' and int(effective) > rec.day:
                deferred_identity.append(rec.order_id)
                continue
            scored.append({
                'order_id': rec.order_id,
                'client_id': client['client_id'],
                'site': client['site'],
                'service_class': client['service_class'],
                'budget_cap': int(client['budget_cap_micros']),
                'program_id': rec.program_id,
                'revision': revision[0],
                'family': revision[1],
                'load': rec.load,
                'granularity': rec.granularity,
                'billable': quantise(rec.load, rec.granularity, mode),
                'weight': rec.weight,
                'mode': rec.mode,
                'day': rec.day,
                'due_slot': rec.due_slot,
                'slack': rec.due_slot - rec.day,
            })
    scored.sort(key=lambda o: o['order_id'])
    return {'scored': scored, 'deferred_identity': sorted(deferred_identity),
            'rejected': sorted(rejected)}


def congestion_tier(index, bounds):
    for tier, bound in enumerate(bounds):
        if index < bound:
            return tier
    return len(bounds)


def admission_fixpoint(scored, corpus):
    """Settle the congestion assignment that is stable under the admission rules."""
    site_capacity = {row['name']: int(row['capacity_slots']) for row in corpus.sites}
    offer = sorted(scored, key=lambda o: (-o['weight'], o['order_id']))
    tiers = {name: 0 for name in site_capacity}
    passes = 0
    while True:
        passes += 1
        running = {}
        admitted, held = [], []
        for order in offer:
            ceiling = (corpus.base_ceiling[order['service_class']]
                       * corpus.tier_factor[tiers[order['site']]]) // 100
            used = running.get(order['client_id'], 0)
            if used + order['billable'] > ceiling:
                held.append(order)
            else:
                running[order['client_id']] = used + order['billable']
                admitted.append(order)
        slots = {name: 0 for name in site_capacity}
        for order in admitted:
            slots[order['site']] += order['billable']
        index = {name: (1000 * slots[name]) // site_capacity[name] for name in site_capacity}
        fresh = {name: congestion_tier(index[name], corpus.congestion_bounds) for name in site_capacity}
        if fresh == tiers:
            return {'passes': passes, 'tiers': tiers, 'index': index,
                    'admitted': admitted, 'held': held}
        tiers = fresh


# ---------------------------------------------------------------------------
# lane placement
# ---------------------------------------------------------------------------

def maximal_independent_sets(items, conflicts):
    """All maximal conflict-free family sets drawn from `items`."""
    items = sorted(items)
    results = []

    def walk(i, chosen):
        if i == len(items):
            results.append(frozenset(chosen))
            return
        item = items[i]
        if all((item, c) not in conflicts and (c, item) not in conflicts for c in chosen):
            walk(i + 1, chosen + [item])
            # leaving `item` out only yields a maximal set when something blocks it
            if any((item, c) in conflicts or (c, item) in conflicts
                   for c in items[i + 1:]):
                walk(i + 1, chosen)
        else:
            walk(i + 1, chosen)

    walk(0, [])
    maximal = []
    for cand in results:
        if not any(cand < other for other in results):
            if cand not in maximal:
                maximal.append(cand)
    return maximal


class ReachSpace(object):
    """Bitset reachability over the used-capacity lattice of one site's lanes."""

    def __init__(self, caps):
        self.caps = caps
        self.dims = [c + 1 for c in caps]
        self.stride = [1] * len(caps)
        for i in range(len(caps) - 2, -1, -1):
            self.stride[i] = self.stride[i + 1] * self.dims[i + 1]
        self.total = self.stride[0] * self.dims[0] if caps else 1
        full = (1 << self.total) - 1
        self._coord_masks = []
        for lane in range(len(caps)):
            stride = self.stride[lane]
            period = stride * self.dims[lane]
            reps = self.total // period
            rep = (1 << stride) - 1
            done = 1
            while done < reps:
                rep |= rep << (period * done)
                done *= 2
            rep &= full
            cumulative = []
            acc = 0
            for value in range(self.dims[lane]):
                acc |= (rep << (value * stride)) & full
                cumulative.append(acc)
            self._coord_masks.append(cumulative)

    def room_mask(self, lane, size):
        limit = self.caps[lane] - size
        if limit < 0:
            return 0
        return self._coord_masks[lane][limit]

    def index(self, coords):
        return sum(c * s for c, s in zip(coords, self.stride))

    def enumerate_coords(self):
        """Every lattice point, in flat index order."""
        out = [()]
        for dim in self.dims:
            out = [point + (value,) for point in out for value in range(dim)]
        return out


def site_placement(site, orders, corpus, conflicts):
    """Minimum lane cost placement for one site, with the contention tie-break."""
    lanes = [row for row in corpus.lanes if row['site'] == site]
    relief = [l for l in lanes if int(l['slot_capacity']) == 0
              and not l['class_lock'] and not l['exclusive_client']]
    if len(relief) != 1:
        raise ValueError('site %s does not hold exactly one relief lane' % site)
    relief = relief[0]
    capped = [l for l in lanes if int(l['slot_capacity']) > 0]
    capped.sort(key=lambda l: (int(l['rate_micros']), l['lane_id']))
    relief_rate = int(relief['rate_micros'])

    # contention order: larger remaining slack first, then larger slot count,
    # then identifier (dispatch_policy.md, Contention)
    orders = sorted(orders, key=lambda o: (-o['slack'], -o['billable'], o['order_id']))
    if not orders:
        return {'assign': {}, 'cost': 0, 'leaves': 0, 'displaced': 0}

    sizes = [o['billable'] for o in orders]
    caps = [int(l['slot_capacity']) for l in capped]
    # every lane total is a whole multiple of the common divisor of the order
    # sizes, so the capacity lattice may be measured in those units
    divisor = 0
    for v in sizes:
        divisor = gcd(divisor, v)
    if divisor == 0:
        divisor = 1
    scaled_sizes = [s // divisor for s in sizes]
    scaled_caps = [c // divisor for c in caps]

    present = {o['family'] for o in orders}
    regimes_per_lane = maximal_independent_sets(present, conflicts)

    base_eligible = []
    for order in orders:
        row = []
        for lane in capped:
            ok = True
            if lane['class_lock'] and lane['class_lock'] != order['service_class']:
                ok = False
            if lane['exclusive_client'] and lane['exclusive_client'] != order['client_id']:
                ok = False
            row.append(ok)
        base_eligible.append(row)

    space = ReachSpace(scaled_caps)
    full = (1 << space.total) - 1
    savings = [relief_rate - int(l['rate_micros']) for l in capped]
    relief_cost = sum(o['billable'] * relief_rate for o in orders)
    nbytes = (space.total + 7) // 8

    # savings of every point of the used-capacity lattice, and the lattice points
    # in descending order of savings, so that the best reachable total of a
    # regime is found by scanning until the first reachable point
    lattice = space.enumerate_coords()
    value_of = [sum(c * divisor * savings[l] for l, c in enumerate(coords))
                for coords in lattice]
    descending = sorted(range(space.total), key=lambda i: -value_of[i])

    best_cost = None
    best_leaves = []
    for regime in _regime_product(regimes_per_lane, len(capped)):
        eligible = []
        for i, order in enumerate(orders):
            row = [base_eligible[i][l] and order['family'] in regime[l] for l in range(len(capped))]
            eligible.append(row)
        suffix = [1] * (len(orders) + 1)  # index 0 reachable with nothing placed
        for i in range(len(orders) - 1, -1, -1):
            cur = suffix[i + 1]
            size = scaled_sizes[i]
            nxt = cur
            for lane in range(len(capped)):
                if not eligible[i][lane]:
                    continue
                room = space.room_mask(lane, size)
                if not room:
                    continue
                nxt |= (cur & room) << (size * space.stride[lane])
            suffix[i] = nxt & full
        data = suffix[0].to_bytes(nbytes, 'little')
        top = None
        targets = []
        for idx in descending:
            if top is not None and value_of[idx] < top:
                break
            if (data[idx >> 3] >> (idx & 7)) & 1:
                top = value_of[idx]
                targets.append(lattice[idx])
        if top is None:
            continue
        cost = relief_cost - top
        if best_cost is None or cost < best_cost:
            best_cost = cost
            best_leaves = [(regime, target, suffix) for target in targets]
        elif cost == best_cost:
            best_leaves += [(regime, target, suffix) for target in targets]

    if best_cost is None:
        raise ValueError('no feasible placement at site %s' % site)

    # every optimal target of every optimal regime is a leaf of the search; walk
    # each one greedily in contention order and keep the lexicographically
    # cheapest lane sequence
    winner = None
    as_bytes = {}
    for regime, coords, suffix in best_leaves:
        key = id(suffix)
        if key not in as_bytes:
            as_bytes[key] = [s.to_bytes(nbytes, 'little') for s in suffix]
        assign = _greedy_fill(orders, scaled_sizes, capped, relief, regime, base_eligible,
                              space, coords, as_bytes[key])
        if assign is None:
            continue
        rates = [int(assign[o['order_id']]['rate_micros']) for o in orders]
        if winner is None or rates < winner[0]:
            winner = (rates, assign)
    if winner is None:
        raise ValueError('optimal placement at site %s could not be realised' % site)
    assign = winner[1]
    cost = sum(o['billable'] * int(assign[o['order_id']]['rate_micros']) for o in orders)
    if cost != best_cost:
        raise ValueError('placement at site %s missed the optimum' % site)
    displaced = sum(1 for o in orders if assign[o['order_id']]['lane_id'] == relief['lane_id'])
    return {'assign': {k: v['lane_id'] for k, v in assign.items()}, 'cost': cost,
            'leaves': len(best_leaves), 'displaced': displaced}


def _regime_product(choices, lanes):
    out = [()]
    for _ in range(lanes):
        out = [item + (choice,) for item in out for choice in choices]
    return out


def _greedy_fill(orders, scaled_sizes, capped, relief, regime, base_eligible,
                 space, target, suffix_bytes):
    """Walk the contention order, taking the cheapest lane that keeps the
    optimal lane totals reachable from what is left to place."""

    def reachable(step, remaining):
        if any(r < 0 for r in remaining):
            return False
        idx = space.index(remaining)
        return bool((suffix_bytes[step][idx >> 3] >> (idx & 7)) & 1)

    used = [0] * len(capped)
    assign = {}
    for i, order in enumerate(orders):
        size = scaled_sizes[i]
        placed = None
        for lane in range(len(capped)):
            if not base_eligible[i][lane] or order['family'] not in regime[lane]:
                continue
            if used[lane] + size > space.caps[lane]:
                continue
            trial = list(used)
            trial[lane] += size
            if reachable(i + 1, [target[l] - trial[l] for l in range(len(capped))]):
                used = trial
                placed = capped[lane]
                break
        if placed is None:
            if not reachable(i + 1, [target[l] - used[l] for l in range(len(capped))]):
                return None
            placed = relief
        assign[order['order_id']] = placed
    if used != list(target):
        return None
    return assign


# ---------------------------------------------------------------------------
# settlement
# ---------------------------------------------------------------------------

def settle(population, corpus, params):
    decoded = decode_blocks(corpus.populations[population], params, corpus)
    if decoded is None:
        raise ValueError('population %s does not decode' % population)
    decoded_rows = sum(blk['block'].stored for blk in decoded)
    order_rows = sum(blk['genuine'] for blk in decoded)
    graded = score_population(decoded, corpus, params)
    scored = graded['scored']
    fix = admission_fixpoint(scored, corpus)
    conflicts = set()
    for left, right in corpus.incompatible:
        conflicts.add((left, right))
        conflicts.add((right, left))

    by_site = {}
    for order in fix['admitted']:
        by_site.setdefault(order['site'], []).append(order)
    lane_by_id = {row['lane_id']: row for row in corpus.lanes}
    placement = {}
    site_cost = {}
    leaves = 0
    displaced = 0
    for row in corpus.sites:
        site = row['name']
        result = site_placement(site, by_site.get(site, []), corpus, conflicts)
        placement.update(result['assign'])
        site_cost[site] = result['cost']
        leaves += result['leaves']
        displaced += result['displaced']

    region_of = {row['name']: row['region'] for row in corpus.sites}
    placed = []
    for order in sorted(fix['admitted'], key=lambda o: o['order_id']):
        lane = lane_by_id[placement[order['order_id']]]
        charge = order['billable'] * int(lane['rate_micros'])
        rebate = min(order['billable'] * corpus.rebate_band[order['mode']], charge)
        placed.append({
            'order_id': order['order_id'],
            'client_id': order['client_id'],
            'program_id': order['program_id'],
            'revision': order['revision'],
            'lane_id': lane['lane_id'],
            'billable_slots': order['billable'],
            'charge_micros': charge,
            'rebate_micros': rebate,
            'net_micros': charge - rebate,
            'capped_micros': 0,
            'slack': order['slack'],
            'site': order['site'],
            'region': region_of[order['site']].capitalize(),
            'service_class': order['service_class'],
            'budget_cap': order['budget_cap'],
        })

    running = {}
    for order in placed:
        used = running.get(order['client_id'], 0)
        cap = order['budget_cap']
        if used + order['net_micros'] > cap:
            order['capped_micros'] = used + order['net_micros'] - cap
            running[order['client_id']] = cap
        else:
            running[order['client_id']] = used + order['net_micros']

    deferred = sorted(graded['deferred_identity'] + [o['order_id'] for o in fix['held']])
    return {
        'decoded_rows': decoded_rows,
        'order_rows': order_rows,
        'scored': scored,
        'rejected': graded['rejected'],
        'deferred': deferred,
        'placed': placed,
        'fixpoint': fix,
        'site_cost': site_cost,
        'leaves': leaves,
        'displaced': displaced,
        'lane_by_id': lane_by_id,
    }


def rollup(discriminator_field, discriminator_value, orders):
    fields = ('billable_slots', 'capped_micros', 'charge_micros', 'net_micros', 'rebate_micros')
    rows = []
    for order in sorted(orders, key=lambda o: o['order_id']):
        rows.append({
            'billable_slots': order['billable_slots'],
            'capped_micros': order['capped_micros'],
            'charge_micros': order['charge_micros'],
            'client_id': order['client_id'],
            'lane_id': order['lane_id'],
            'net_micros': order['net_micros'],
            'order_id': order['order_id'],
            'program_id': order['program_id'],
            'rebate_micros': order['rebate_micros'],
            'revision': order['revision'],
            'slack': order['slack'],
        })
    totals = {f: sum(r[f] for r in rows) for f in fields}
    return {
        'order_count': len(rows),
        'orders': rows,
        discriminator_field: discriminator_value,
        'totals': totals,
    }


def write_json(path, payload):
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write('\n')


def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: %s <input_dir> <output_dir>\n' % argv[0])
        return 2
    indir, outdir = argv[1], argv[2]
    corpus = Corpus(indir)
    params, audit = resolve_constants(corpus)

    comparison = []
    for _, control in CONTROL_FOR_PARAM:
        comparison.append({'control': control, 'published': corpus.controls[control],
                           'reproduced': evaluate_control(control, corpus, params)})

    calibration = settle('calibration', corpus, params)
    field = settle('field', corpus, params)

    os.makedirs(outdir, exist_ok=True)
    placed = field['placed']
    regions = sorted({row['region'].capitalize() for row in corpus.sites})
    segments = sorted({row['service_class'] for row in corpus.clients})

    region_net, segment_net = {}, {}
    for region in regions:
        rows = [o for o in placed if o['region'] == region]
        write_json(os.path.join(outdir, 'region_%s.json' % region), rollup('region', region, rows))
        region_net[region] = sum(o['net_micros'] for o in rows)
    for segment in segments:
        rows = [o for o in placed if o['service_class'] == segment]
        write_json(os.path.join(outdir, 'segment_%s.json' % segment),
                   rollup('service_class', segment, rows))
        segment_net[segment] = sum(o['net_micros'] for o in rows)

    net_total = sum(o['net_micros'] for o in placed)
    summary = {
        'order_rows': field['order_rows'],
        'decoded_rows': field['decoded_rows'],
        'orders_scored': len(field['scored']),
        'orders_placed': len(placed),
        'orders_deferred': len(field['deferred']),
        'orders_rejected': len(field['rejected']),
        'billable_slots_total': sum(o['billable_slots'] for o in placed),
        'charge_micros_total': sum(o['charge_micros'] for o in placed),
        'rebate_micros_total': sum(o['rebate_micros'] for o in placed),
        'capped_micros_total': sum(o['capped_micros'] for o in placed),
        'net_micros_total': net_total,
        'lanes_used': len({o['lane_id'] for o in placed}),
    }
    write_json(os.path.join(outdir, 'summary.json'), summary)

    region_ids = {o['order_id'] for o in placed}
    region_cover = []
    for region in regions:
        region_cover += [o['order_id'] for o in placed if o['region'] == region]
    segment_cover = []
    for segment in segments:
        segment_cover += [o['order_id'] for o in placed if o['service_class'] == segment]
    lane_load = {}
    for o in placed:
        lane_load[o['lane_id']] = lane_load.get(o['lane_id'], 0) + o['billable_slots']
    capacity_ok = True
    for lane_id, load in lane_load.items():
        cap = int(field['lane_by_id'][lane_id]['slot_capacity'])
        if cap > 0 and load > cap:
            capacity_ok = False

    quality = {
        'order_rows': field['order_rows'],
        'decoded_rows': field['decoded_rows'],
        'rejected_orders': sorted(field['rejected']),
        'deferred_orders': sorted(field['deferred']),
        'region_net_micros': region_net,
        'segment_net_micros': segment_net,
        'conservation_residual_micros': net_total - sum(region_net.values()),
        'segment_residual_micros': net_total - sum(segment_net.values()),
        'calibration_net_micros': sum(o['net_micros'] for o in calibration['placed']),
        'invariants': {
            'region_partition_closed': sorted(region_cover) == sorted(region_ids)
                                       and len(region_cover) == len(region_ids),
            'segment_partition_closed': sorted(segment_cover) == sorted(region_ids)
                                        and len(segment_cover) == len(region_ids),
            'order_identity_unique': len(region_ids) == len(placed),
            'capacity_respected': capacity_ok,
        },
    }
    write_json(os.path.join(outdir, 'data_quality.json'), quality)

    fix = field['fixpoint']
    audit_doc = {
        'candidate_space': audit,
        'resolved_parameters': dict(params),
        'calibration_comparison': comparison,
        'fixpoint': {
            'passes': fix['passes'],
            'congestion_index': fix['index'],
            'congestion_tier': fix['tiers'],
        },
        'assignment_search': {
            'sites_searched': len(corpus.sites),
            'feasible_leaves': field['leaves'],
            'displaced_orders': field['displaced'],
            'site_cost_micros': field['site_cost'],
        },
        'candidates_examined': sum(e['domain_size'] for e in audit),
        'candidates_rejected': sum(e['rejected'] for e in audit),
    }
    write_json(os.path.join(outdir, 'policy_audit.json'), audit_doc)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
