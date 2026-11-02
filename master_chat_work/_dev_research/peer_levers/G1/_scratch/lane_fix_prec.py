#!/usr/bin/env python3
"""Settle a dispatch-authority season from an encoded work-order corpus.

Usage: derive_report.py <input_dir> <output_dir>

Everything written is derived from the files in <input_dir>: the withheld packet
constants are recovered from the calibration population against its published
control figures, the field population is then decoded and settled, and the
reports are written to <output_dir>.
"""

import csv
import hashlib
import hmac
import json
import math
import os
import re
import struct
import sys
import zlib
from collections import defaultdict

WORD = 1 << 16
HEADER_BYTES = 24
BASE_RECORD_BYTES = 13
SLACK_FIELD_BYTES = 2


# --------------------------------------------------------------------------
# policy documents
# --------------------------------------------------------------------------

def read_text(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def flatten(text):
    return re.sub(r'\s+', ' ', text)


def labelled_value(text, label):
    m = re.search(r'^\s*[-*]?\s*%s\s*:\s*(.+)$' % re.escape(label), text, re.M)
    if m is None:
        raise ValueError('policy label %r not found' % label)
    return m.group(1).strip()


def int_list(spec):
    return [int(x) for x in re.findall(r'-?\d+', spec)]


def keyed_ints(spec):
    out = {}
    for key, val in re.findall(r'([A-Za-z0-9_]+)\s*=\s*(-?\d+)', spec):
        out[key] = int(val)
    return out


def parse_domain(spec):
    """Candidate values of a withheld constant, as its declared range spells them."""
    m = re.match(r'^(\d+)\s+through\s+(\d+)$', spec)
    if m:
        return list(range(int(m.group(1)), int(m.group(2)) + 1))
    if re.match(r'^[\d,\s]+$', spec):
        return int_list(spec)
    return [tok.strip() for tok in spec.split(',') if tok.strip()]


# cues are matched most specific first; the candidate order is the order the
# policy document lists the modes in
QUANT_MODES = (
    ('discard_unless_three_quarters', ('discard the remainder', 'unless')),
    ('discard_remainder', ('discard the remainder',)),
    ('advance_next_multiple', ('next multiple', 'advance')),
    ('closer_multiple_midpoint_up', ('closer multiple', 'midpoint')),
)


def parse_quant_domain(text):
    """The quantisation modes capacity_policy.md offers, in the order it lists them."""
    m = re.search(r'withholds which of the \w+ quantisation modes it applies:(.*?)\. ', text)
    if m is None:
        raise ValueError('quantisation mode list not found')
    phrases = [p.strip() for p in re.split(r',\s*(?:or\s+)?|\s+or\s+', m.group(1)) if p.strip()]
    domain = []
    for phrase in phrases:
        low = phrase.lower()
        hit = None
        for name, cues in QUANT_MODES:
            if all(cue in low for cue in cues):
                hit = name
                break
        if hit is None or hit in domain:
            raise ValueError('unrecognised quantisation mode %r' % phrase)
        domain.append(hit)
    return domain


class Policy:
    """Every constant the rule set publishes, read out of the rule set."""

    def __init__(self, root):
        enc = read_text(os.path.join(root, 'packet_encoding.md'))
        cap = read_text(os.path.join(root, 'capacity_policy.md'))
        cost = read_text(os.path.join(root, 'cost_policy.md'))
        disp = read_text(os.path.join(root, 'dispatch_policy.md'))
        cal = read_text(os.path.join(root, 'calibration_slice.md'))
        prose = flatten(enc)

        self.hmac_key = re.search(r'the key `([^`]+)`', prose).group(1).encode()
        self.block_seed_tag = re.search(r'ASCII text `([^`]+)`', prose).group(1).encode()
        self.magic = int(re.search(r'magic word, always (0x[0-9A-Fa-f]+)', prose).group(1), 16)
        self.granularities = int_list(
            re.search(r'granularity from the list ([\d, ]+) by position', prose).group(1))
        self.day_modulus = int(re.search(r'drifting factor modulo (\d+)', prose).group(1))
        self.backref_floor = int(re.search(r'a value of (0x[0-9A-Fa-f]+) or above', prose).group(1), 16)

        self.flag_bit = {}
        self.constant_of_flag = {}
        self.domain = {}
        for bit, name, const, rng in re.findall(
                r'^\|\s*(0x[0-9A-Fa-f]+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*$', enc, re.M):
            key = const.strip().replace(' ', '_')
            self.flag_bit[name.strip()] = int(bit, 16)
            self.constant_of_flag[name.strip()] = key
            self.domain[key] = parse_domain(rng.strip())
        self.domain['quant_mode'] = parse_quant_domain(flatten(cap))

        self.congestion_bounds = int_list(labelled_value(cap, 'congestion_bounds'))
        self.base_ceiling = keyed_ints(labelled_value(cap, 'base_ceiling'))
        self.tier_factor = {int(k): v for k, v in keyed_ints(labelled_value(cap, 'tier_factor')).items()}
        self.rebate_band = {int(k): v for k, v in keyed_ints(labelled_value(cost, 'rebate_band')).items()}
        self.incompatible = []
        for pair in labelled_value(disp, 'incompatible_families').split(','):
            a, b = [x.strip() for x in pair.strip().split('|')]
            self.incompatible.append((a, b))

        self.controls = []
        for name, value in re.findall(r'^\s*[-*]\s*([a-z_]+)\s*=\s*(-?\d+)\s*$', cal, re.M):
            self.controls.append((name, int(value)))

    def tier_of(self, index):
        for i, bound in enumerate(self.congestion_bounds):
            if index < bound:
                return i
        return len(self.congestion_bounds)


# the constant each published control figure pins down, and the semantics of
# the transform that constant governs; the resolution order is the order the
# calibration slice lists its controls in.
CONTROL_PARAMETER = {
    'payload_origin_total': 'rotate_step',
    'record_span_total': 'shadow_bias',
    'calibration_order_total': 'count_bias',
    'island_field_total': 'island_offset',
    'ordinal_position_checksum': 'permute_rounds',
    'masked_load_total': 'stream_label',
    'folded_slack_total': 'chain_seed',
    'delta_weight_total': 'delta_span',
    'drift_day_total': 'drift_modulus',
    'canonical_client_total': 'alias_rotor',
    'backref_program_total': 'window_span',
    'billable_slot_total': 'quant_mode',
}


# --------------------------------------------------------------------------
# directories
# --------------------------------------------------------------------------

def read_rows(path):
    with open(path, encoding='utf-8-sig') as fh:
        rows = []
        for row in csv.DictReader(fh):
            rows.append({(k or '').strip(): (v or '').strip() for k, v in row.items()})
        return rows


def opt_int(text):
    return int(text) if text != '' else None


class Directories:
    def __init__(self, root):
        self.clients = read_rows(os.path.join(root, 'client_directory.csv'))
        self.sites = read_rows(os.path.join(root, 'site_directory.csv'))
        self.lanes = read_rows(os.path.join(root, 'lane_roster.csv'))
        self.registry = read_rows(os.path.join(root, 'program_registry.csv'))

        self.client_by_id = {c['client_id']: c for c in self.clients}
        self.site_by_name = {s['name']: s for s in self.sites}
        self.programs = sorted({r['program_id'] for r in self.registry})
        self.revisions = defaultdict(list)
        for r in self.registry:
            self.revisions[r['program_id']].append(r)
        self._governing = {}

    def governing_client(self, client_id):
        """Follow the merge chain to its end, or to the first identifier on its cycle."""
        if client_id in self._governing:
            return self._governing[client_id]
        seen = []
        cur = client_id
        while True:
            if cur in seen:
                answer = min(seen[seen.index(cur):])
                break
            seen.append(cur)
            target = self.client_by_id[cur]['merged_into']
            if not target:
                answer = cur
                break
            cur = target
        for cid in seen:
            self._governing[cid] = answer
        return answer

    def governing_revision(self, program_id, day):
        best = None
        for r in self.revisions.get(program_id, ()):
            if int(r['effective_from']) <= day < int(r['effective_to']):
                if best is None or int(r['revision']) > int(best['revision']):
                    best = r
        return best

    def region_of_site(self, site):
        return self.site_by_name[site]['region'].capitalize()


# --------------------------------------------------------------------------
# packet stream
# --------------------------------------------------------------------------

class Block:
    __slots__ = ('population', 'block_id', 'stored_count', 'flags', 'raw_aux', 'wire_payload')


class Stream:
    """Block headers and wire payloads, keyed by population."""

    def __init__(self, root, policy):
        headers = {}
        for row in read_rows(os.path.join(root, 'block_manifest.csv')):
            headers[(row['population'], int(row['block_id']))] = bytes.fromhex(row['header_hex'])
        payloads = {}
        for name in sorted(os.listdir(root)):
            m = re.match(r'^(.+)_orders\.csv$', name)
            if not m:
                continue
            for row in read_rows(os.path.join(root, name)):
                payloads[(m.group(1), int(row['block_id']))] = bytes.fromhex(row['payload_hex'])

        self.blocks = defaultdict(list)
        for key in sorted(payloads):
            head = headers[key]
            if len(head) != HEADER_BYTES:
                raise ValueError('block header of %s is not %d bytes' % (key, HEADER_BYTES))
            block = Block()
            block.population, block.block_id = key
            magic, bid, count, flags = struct.unpack('>HHHH', head[:8])
            block.stored_count = count
            block.flags = flags
            block.raw_aux = head[8:16]
            block.wire_payload = payloads[key]
            payload_crc, header_crc = struct.unpack('>II', head[16:24])
            if magic != policy.magic or bid != block.block_id:
                raise ValueError('block header of %s does not match the manifest' % (key,))
            if zlib.crc32(head[:20]) != header_crc:
                raise ValueError('header checksum of %s fails' % (key,))
            if zlib.crc32(block.wire_payload) != payload_crc:
                raise ValueError('payload checksum of %s fails' % (key,))
            self.blocks[block.population].append(block)


def xorshift64(state):
    state ^= (state << 13) & 0xFFFFFFFFFFFFFFFF
    state ^= state >> 7
    state ^= (state << 17) & 0xFFFFFFFFFFFFFFFF
    return state & 0xFFFFFFFFFFFFFFFF


class Decoder:
    """Undoes the wire transforms under a (possibly partial) constant assignment."""

    def __init__(self, policy, dirs, stream, params):
        self.policy = policy
        self.dirs = dirs
        self.stream = stream
        self.p = params
        self.bit = policy.flag_bit

    def live(self, block, transform):
        return bool(block.flags & self.bit[transform])

    def origin_payload(self, block):
        data = block.wire_payload
        if self.live(block, 'payload rotation'):
            step = (block.block_id * self.p['rotate_step']) % len(data)
            if step:
                data = data[-step:] + data[:-step]
        return data

    def aux_words(self, block):
        words = list(struct.unpack('>HHHH', block.raw_aux))
        if self.live(block, 'byte order island'):
            idx = (self.p['island_offset'] - 8) // 2
            words[idx], = struct.unpack('<H', block.raw_aux[idx * 2:idx * 2 + 2])
        return words

    def records(self, block):
        """Record bytes in the order they travel."""
        data = self.origin_payload(block)
        shadow = self.p['shadow_bias'] if self.live(block, 'length shadow') else 0
        out = []
        off = 0
        for _ in range(block.stored_count):
            if off >= len(data):
                raise ValueError('payload exhausted')
            code = (data[off] >> 4) ^ shadow
            if code not in (0, 1):
                raise ValueError('length code out of range')
            width = BASE_RECORD_BYTES + SLACK_FIELD_BYTES * code
            if off + width > len(data):
                raise ValueError('record runs past the payload')
            out.append(data[off:off + width])
            off += width
        if off != len(data):
            raise ValueError('payload not consumed exactly')
        return out

    def block_seed(self, block):
        words = self.aux_words(block)
        msg = self.policy.block_seed_tag + struct.pack('>HHHHH', block.block_id, *words)
        digest = hmac.new(self.policy.hmac_key, msg, hashlib.sha256).digest()
        return struct.unpack('>Q', digest[:8])[0]

    def permutation(self, block):
        """perm[physical position] = logical ordinal travelling there."""
        count = block.stored_count
        perm = list(range(count))
        if not self.live(block, 'block permutation'):
            return perm
        state = self.block_seed(block)
        for _ in range(self.p['permute_rounds']):
            for i in range(count - 1, 0, -1):
                state = xorshift64(state)
                j = state % (i + 1)
                perm[i], perm[j] = perm[j], perm[i]
        return perm

    def logical_records(self, block):
        travelling = self.records(block)
        out = [None] * len(travelling)
        for physical, ordinal in enumerate(self.permutation(block)):
            out[ordinal] = travelling[physical]
        return out

    def genuine_count(self, block):
        bias = self.p['count_bias'] if self.live(block, 'count bias') else 0
        return block.stored_count - bias

    def load_mask(self, block, ordinal):
        msg = (self.p['stream_label'].encode('utf-8') + b'|'
               + struct.pack('>HH', block.block_id, ordinal))
        digest = hmac.new(self.policy.hmac_key, msg, hashlib.sha256).digest()
        return struct.unpack('>I', digest[:4])[0]

    def decode_weights(self, wire, span):
        out = []
        value = delta = 0
        for i, x in enumerate(wire):
            place = i % span
            if place == 0:
                value, delta = x, 0
            elif place == 1:
                delta = x
                value = (value + delta) % WORD
            else:
                delta = (delta + x) % WORD
                value = (value + delta) % WORD
            out.append(value)
        return out

    def decode_population(self, population):
        """Decode as far as the settled constants allow; genuine records only."""
        p = self.p
        orders = []
        drift_sum = 0
        for block in self.stream.blocks[population]:
            records = self.logical_records(block)
            genuine = self.genuine_count(block)
            words = self.aux_words(block)
            horizon = words[1]
            count = len(records)

            loads = None
            if 'stream_label' in p:
                loads = []
                for i, rec in enumerate(records):
                    value, = struct.unpack('>I', rec[3:7])
                    if self.live(block, 'load mask'):
                        value ^= self.load_mask(block, i)
                    loads.append(value)

            dues = None
            if 'chain_seed' in p:
                dues = []
                previous = p['chain_seed']
                for rec in records:
                    raw, = struct.unpack('>H', rec[7:9])
                    if self.live(block, 'slack fold'):
                        raw = (raw - previous) % WORD
                        previous = raw
                    dues.append(raw)

            weights = None
            if 'delta_span' in p:
                wire = [struct.unpack('>H', rec[9:11])[0] for rec in records]
                weights = (self.decode_weights(wire, p['delta_span'])
                           if self.live(block, 'weight difference') else wire)

            programs = None
            if 'window_span' in p:
                programs = []
                for i, rec in enumerate(records):
                    ref = rec[2]
                    if ref >= self.policy.backref_floor and self.live(block, 'backward reference'):
                        back = ((ref - self.policy.backref_floor) % p['window_span']) + 1
                        if i - back < 0:
                            raise ValueError('backward reference before the first ordinal')
                        programs.append(programs[i - back])
                    else:
                        programs.append(ref % len(self.dirs.programs))

            days = None
            if 'drift_modulus' in p and loads is not None:
                days = []
                for i in range(count):
                    raw = records[i][12]
                    if i < genuine:
                        factor = 1 + drift_sum % (p['drift_modulus'] - 1)
                        drift_sum += loads[i]
                    else:
                        factor = None
                    if self.live(block, 'day drift'):
                        if factor is None:
                            days.append(None)
                            continue
                        raw = raw * pow(factor, -1, self.policy.day_modulus) % self.policy.day_modulus
                    days.append(raw)

            aliases = None
            if 'alias_rotor' in p:
                aliases = []
                size = len(self.dirs.clients)
                for rec in records:
                    position = rec[1] % size
                    if self.live(block, 'alias rotor'):
                        position = (position - p['alias_rotor']) % size
                    aliases.append(position)

            for i in range(genuine):
                rec = records[i]
                order = {
                    'order_id': 'W%04d%02d' % (block.block_id, i),
                    'block_id': block.block_id,
                    'ordinal': i,
                    'dispatch_mode': rec[0] & 0x0F,
                    'granularity': self.policy.granularities[rec[11]],
                }
                if loads is not None:
                    order['load_units'] = loads[i]
                if dues is not None:
                    extended = (struct.unpack('>H', rec[13:15])[0]
                                if len(rec) > BASE_RECORD_BYTES else 0)
                    order['due_offset'] = dues[i]
                    order['due_slot'] = horizon + dues[i] + extended
                if weights is not None:
                    order['dispatch_weight'] = weights[i]
                if days is not None:
                    order['submitted_day'] = days[i]
                if programs is not None:
                    order['program_id'] = self.dirs.programs[programs[i]]
                    order['program_index'] = programs[i]
                if aliases is not None:
                    row = self.dirs.clients[aliases[i]]
                    order['alias_key'] = row['alias_key']
                    order['client_id'] = self.dirs.governing_client(row['client_id'])
                if 'submitted_day' in order and 'due_slot' in order:
                    order['slack'] = order['due_slot'] - order['submitted_day']
                orders.append(order)
        return orders


def billable_slots(load, granularity, mode):
    whole, remainder = divmod(load, granularity)
    if mode == 'discard_remainder':
        advance = 0
    elif mode == 'advance_next_multiple':
        advance = 1 if remainder else 0
    elif mode == 'closer_multiple_midpoint_up':
        advance = 1 if remainder * 2 >= granularity else 0
    elif mode == 'discard_unless_three_quarters':
        advance = 1 if remainder * 4 >= granularity * 3 else 0
    else:
        raise ValueError('unknown quantisation mode %r' % mode)
    return (whole + advance) * granularity


# --------------------------------------------------------------------------
# control figures
# --------------------------------------------------------------------------

def numeric_tail(identifier):
    return int(re.search(r'(\d+)\s*$', identifier).group(1))


class Calibrator:
    """Reproduces each published control figure under a constant assignment."""

    def __init__(self, policy, dirs, stream, population):
        self.policy = policy
        self.dirs = dirs
        self.stream = stream
        self.population = population

    def blocks(self):
        return self.stream.blocks[self.population]

    def figure(self, name, params):
        dec = Decoder(self.policy, self.dirs, self.stream, params)
        return getattr(self, '_' + name)(dec)

    def _payload_origin_total(self, dec):
        return sum(struct.unpack('>I', dec.origin_payload(b)[:4])[0] for b in self.blocks())

    def _record_span_total(self, dec):
        return sum(1 for b in self.blocks() for rec in dec.records(b)
                   if len(rec) > BASE_RECORD_BYTES)

    def _calibration_order_total(self, dec):
        return sum(dec.genuine_count(b) for b in self.blocks())

    def _island_field_total(self, dec):
        return sum(sum(dec.aux_words(b)) for b in self.blocks())

    def _ordinal_position_checksum(self, dec):
        total = 0
        for b in self.blocks():
            for physical, ordinal in enumerate(dec.permutation(b)):
                total += (1 + physical) * (1 + ordinal)
        return total

    def _masked_load_total(self, dec):
        return sum(o['load_units'] for o in dec.decode_population(self.population))

    def _folded_slack_total(self, dec):
        return sum(o['due_offset'] for o in dec.decode_population(self.population))

    def _delta_weight_total(self, dec):
        return sum(o['dispatch_weight'] for o in dec.decode_population(self.population))

    def _drift_day_total(self, dec):
        return sum(o['submitted_day'] * (1 + o['ordinal'])
                   for o in dec.decode_population(self.population))

    def _canonical_client_total(self, dec):
        return sum(numeric_tail(o['client_id']) * (1 + o['ordinal'])
                   for o in dec.decode_population(self.population))

    def _backref_program_total(self, dec):
        return sum(o['program_index'] * (1 + o['ordinal'])
                   for o in dec.decode_population(self.population))

    def _billable_slot_total(self, dec):
        total = 0
        for o in dec.decode_population(self.population):
            if classify(o, self.dirs)[0] != 'scored':
                continue
            total += billable_slots(o['load_units'], o['granularity'], dec.p['quant_mode'])
        return total


def resolve_constants(policy, dirs, stream, population):
    """Settle every withheld constant against the calibration population.

    Each control figure resolves one constant: every candidate in that
    constant's declared range is tried, and a candidate survives only if it
    reproduces the control exactly with every constant above it already
    settled.
    """
    cal = Calibrator(policy, dirs, stream, population)
    params = {}
    audit = []
    for control, published in policy.controls:
        key = CONTROL_PARAMETER[control]
        domain = policy.domain[key]
        verdicts = []
        accepted = []
        for candidate in domain:
            trial = dict(params)
            trial[key] = candidate
            try:
                reproduced = cal.figure(control, trial)
            except (ValueError, IndexError, KeyError, struct.error):
                reproduced = None
            ok = reproduced == published
            verdicts.append({'value': candidate, 'verdict': 'accepted' if ok else 'rejected'})
            if ok:
                accepted.append(candidate)
        if not accepted:
            raise ValueError('%s rules out every candidate for %s' % (control, key))
        # more than one survivor means the transform the constant governs is
        # inert over this corpus, so the survivors decode alike
        params[key] = accepted[0]
        audit.append({
            'parameter': key,
            'control': control,
            'domain_size': len(domain),
            'resolved': accepted[0],
            'rejected': len(domain) - len(accepted),
            'verdicts': verdicts,
        })
    return params, audit, cal


# --------------------------------------------------------------------------
# settlement
# --------------------------------------------------------------------------

class LanePlacer:
    """Exact cheapest lane placement for the admitted work of one site.

    The cost of a placement depends only on how many billable slots rest on
    each capacitated lane, so the search enumerates reachable lane loadings
    rather than assignments: a loading sits at bit index sum(load_l * stride_l)
    of one integer, and that one integer holds every loading the items offered
    so far can reach. Offering an item of s slots to lane l shifts the whole
    set by s * stride_l once the loadings that lane has no room for are masked
    off, so each item costs a handful of big-integer operations instead of a
    walk over the assignment tree. Process families of an incompatible pair in
    turn and a lane's family state collapses as soon as its pair is spent.
    """

    STATE_LIMIT = 1 << 22

    def __init__(self, site, orders, lanes, dirs, conflicts):
        self.orders = sorted(orders, key=lambda o: (-o['slack'], -o['billable_slots'],
                                                    o['order_id']))
        self.lanes = lanes
        self.conflicts = conflicts
        self.held = [i for i, lane in enumerate(lanes) if not lane['relief']]
        relief = [lane['rate'] for lane in lanes if lane['relief']]
        if not relief:
            raise ValueError('%s publishes no relief capacity' % site)
        self.relief_rate = min(relief)
        self.total_slots = sum(o['billable_slots'] for o in self.orders)

        sizes = [o['billable_slots'] for o in self.orders if o['billable_slots']]
        self.grain = 0
        for size in sizes:
            self.grain = size if not self.grain else math.gcd(self.grain, size)
        self.grain = self.grain or 1
        self.room = [lanes[i]['capacity'] // self.grain for i in self.held]
        self.stride = []
        span = 1
        for room in self.room:
            self.stride.append(span)
            span *= room + 1
        self.space = span
        self.rates = [lanes[i]['rate'] for i in self.held]

        self.eligible = []
        for order in self.orders:
            client = dirs.client_by_id[order['client_id']]
            row = []
            for idx, lane in enumerate(lanes):
                if lane['class_lock'] and lane['class_lock'] != client['service_class']:
                    continue
                if lane['exclusive'] and lane['exclusive'] != order['client_id']:
                    continue
                if not lane['relief'] and order['billable_slots'] > lane['capacity']:
                    continue
                row.append(idx)
            self.eligible.append(row)

        self.slot_of = {lane: slot for slot, lane in enumerate(self.held)}
        self.groups = self._family_groups()
        self._masks = {}
        self._gain = None
        self._by_gain = None

    def gains(self):
        """What each loading saves against carrying the same work on relief."""
        if self._gain is None:
            gain = [0]
            for slot, room in enumerate(self.room):
                step = self.relief_rate - self.rates[slot]
                gain = [held + load * step for load in range(room + 1) for held in gain]
            self._gain = gain
            self._by_gain = sorted(range(self.space), key=lambda i: -gain[i])
        return self._gain

    def _family_groups(self):
        """Items grouped so that each incompatible pair is spent in one stretch."""
        present = sorted({o['family'] for o in self.orders})
        seen = set()
        groups = []
        for family in present:
            if family in seen:
                continue
            component = []
            stack = [family]
            while stack:
                here = stack.pop()
                if here in seen:
                    continue
                seen.add(here)
                component.append(here)
                for other in sorted(self.conflicts.get(here, ())):
                    if other in present and other not in seen:
                        stack.append(other)
            component.sort()
            constrained = len(component) > 1
            groups.append((component, constrained))
        return groups

    def mask(self, slot, size):
        """Loadings where lane `slot` still has room for `size` scaled slots."""
        key = (slot, size)
        hit = self._masks.get(key)
        if hit is None:
            stride, width = self.stride[slot], self.room[slot] + 1
            period = stride * width
            block = (1 << (stride * (self.room[slot] - size + 1))) - 1
            hit = block
            reach = period
            while reach < self.space:
                hit |= hit << reach
                reach *= 2
            hit &= (1 << self.space) - 1
            self._masks[key] = hit
        return hit

    def reachable(self, start, index, marks):
        """Every lane loading the items from `start` onward can reach."""
        bits = 1 << index
        for families, constrained in self.groups:
            items = [i for i in range(start, len(self.orders))
                     if self.orders[i]['family'] in families]
            if not items:
                continue
            if not constrained:
                for i in items:
                    nxt = bits
                    for lane in self.eligible[i]:
                        if self.lanes[lane]['relief']:
                            continue
                        slot = self.slot_of[lane]
                        size = self.orders[i]['billable_slots'] // self.grain
                        nxt |= (bits & self.mask(slot, size)) << (self.stride[slot] * size)
                    bits = nxt
                continue
            state = {tuple(frozenset(m & set(families)) for m in marks): bits}
            for position, family in enumerate(families):
                last = position == len(families) - 1
                clash = self.conflicts.get(family, set())
                for i in items:
                    order = self.orders[i]
                    if order['family'] != family:
                        continue
                    size = order['billable_slots'] // self.grain
                    nxt = {}
                    for key, reached in state.items():
                        nxt[key] = nxt.get(key, 0) | reached
                        for lane in self.eligible[i]:
                            if self.lanes[lane]['relief']:
                                continue
                            slot = self.slot_of[lane]
                            if clash & key[slot]:
                                continue
                            moved = ((reached & self.mask(slot, size))
                                     << (self.stride[slot] * size))
                            if not moved:
                                continue
                            if last or family in key[slot]:
                                fresh = key
                            else:
                                grown = list(key)
                                grown[slot] = key[slot] | {family}
                                fresh = tuple(grown)
                            nxt[fresh] = nxt.get(fresh, 0) | moved
                    state = nxt
            bits = 0
            for reached in state.values():
                bits |= reached
        return bits

    def cheapest(self, bits):
        """Lowest site cost among the loadings in `bits`."""
        if not bits:
            return None
        gain = self.gains()
        buffer = bits.to_bytes((self.space + 7) // 8, 'little')
        for index in self._by_gain:
            if buffer[index >> 3] >> (index & 7) & 1:
                return self.total_slots * self.relief_rate - self.grain * gain[index]
        return None

    def index_of(self, loads):
        return sum(load * stride for load, stride in zip(loads, self.stride))

    def place(self):
        """The cheapest placement the contention rule settles on.

        Orders are offered in the order the contention rule prefers and each
        takes the cheapest lane that still leaves the site able to reach its
        lowest total cost, so the larger remaining slack holds cheap capacity.
        """
        marks = [set() for _ in self.held]
        loads = [0] * len(self.held)
        whole = self.reachable(0, 0, marks)
        target = self.cheapest(whole)
        if target is None:
            raise ValueError('no feasible placement')
        leaves = bin(whole).count('1')
        placement = {}
        for i, order in enumerate(self.orders):
            size = order['billable_slots'] // self.grain
            for lane in self.eligible[i]:
                slot = None
                if not self.lanes[lane]['relief']:
                    slot = self.slot_of[lane]
                    if loads[slot] + size > self.room[slot]:
                        continue
                    if self.conflicts.get(order['family'], set()) & marks[slot]:
                        continue
                trial_loads = list(loads)
                trial_marks = [set(m) for m in marks]
                if slot is not None:
                    trial_loads[slot] += size
                    trial_marks[slot].add(order['family'])
                rest = self.reachable(i + 1, self.index_of(trial_loads), trial_marks)
                if self.cheapest(rest) != target:
                    continue
                loads, marks = trial_loads, trial_marks
                placement[order['order_id']] = self.lanes[lane]
                break
            else:
                raise ValueError('order %s found no lane' % order['order_id'])
        return placement, target, leaves


def classify(order, dirs):
    """Admission standing of one order under the identity and revision policies."""
    client = dirs.client_by_id[order['client_id']]
    day = order['submitted_day']
    retired = opt_int(client['retired_on'])
    if retired is not None and day >= retired:
        return 'rejected', None
    revision = dirs.governing_revision(order['program_id'], day)
    if revision is None:
        return 'rejected', None
    if opt_int(client['effective_from']) > day:
        return 'deferred', None
    return 'scored', revision


class Settlement:
    def __init__(self, policy, dirs, params):
        self.policy = policy
        self.dirs = dirs
        self.params = params
        self.search = {'sites_searched': 0, 'feasible_leaves': 0, 'displaced_orders': 0,
                       'site_cost_micros': {}}
        self.conflicts = {}
        for a, b in policy.incompatible:
            self.conflicts.setdefault(a, set()).add(b)
            self.conflicts.setdefault(b, set()).add(a)

    # -- admission ---------------------------------------------------------
    def admit(self, scored):
        """One stable congestion assignment over the sites, by repeated offering."""
        policy = self.policy
        sites = [s['name'] for s in self.dirs.sites]
        offering = sorted(scored, key=lambda o: (-o['dispatch_weight'], o['order_id']))
        tiers = {s: 0 for s in sites}
        passes = 0
        while True:
            passes += 1
            standing = dict(tiers)
            running = defaultdict(int)
            admitted = []
            for order in offering:
                client = self.dirs.client_by_id[order['client_id']]
                ceiling = (policy.base_ceiling[client['service_class']]
                           * policy.tier_factor[standing[client['site']]]) // 100
                if running[order['client_id']] + order['billable_slots'] <= ceiling:
                    running[order['client_id']] += order['billable_slots']
                    admitted.append(order)
            slots = defaultdict(int)
            for order in admitted:
                slots[self.dirs.client_by_id[order['client_id']]['site']] += order['billable_slots']
            index = {s: 1000 * slots[s] // int(self.dirs.site_by_name[s]['capacity_slots'])
                     for s in sites}
            tiers = {s: policy.tier_of(index[s]) for s in sites}
            if tiers == standing:
                return admitted, passes, index, tiers

    # -- placement ---------------------------------------------------------
    def lanes_of_site(self, site):
        lanes = []
        for row in self.dirs.lanes:
            if row['site'] != site:
                continue
            capacity = int(row['slot_capacity'])
            relief = capacity == 0 and not row['class_lock'] and not row['exclusive_client']
            rate = (int(self.dirs.site_by_name[site]['penalty_rate_micros']) if relief
                    else int(row['rate_micros']))
            lanes.append({'lane_id': row['lane_id'], 'rate': rate, 'capacity': capacity,
                          'class_lock': row['class_lock'], 'exclusive': row['exclusive_client'],
                          'relief': relief})
        lanes.sort(key=lambda l: (l['rate'], l['lane_id']))
        return lanes

    def place_site(self, site, orders):
        """Cheapest lane assignment for one site, settled by the contention rule."""
        lanes = self.lanes_of_site(site)
        self.search['sites_searched'] += 1
        if not orders:
            self.search['site_cost_micros'][site] = 0
            return {}
        placer = LanePlacer(site, orders, lanes, self.dirs, self.conflicts)
        if placer.space > LanePlacer.STATE_LIMIT:
            return self.search_site(site, orders, lanes)
        placement, cost, leaves = placer.place()
        self.search['feasible_leaves'] += leaves
        self.search['site_cost_micros'][site] = cost
        for lane in placement.values():
            if lane['relief']:
                self.search['displaced_orders'] += 1
        return placement

    def search_site(self, site, orders, lanes):
        """Branch and bound placement, for rosters too wide to enumerate loadings.

        Orders are offered in the order the contention rule prefers (larger
        remaining slack first, then the larger slot count, then the identifier)
        and each is tried on the cheapest lane first, so the first assignment
        reaching the lowest total cost is the one the authority settles.
        """
        orders = sorted(orders, key=lambda o: (-o['slack'], -o['billable_slots'], o['order_id']))
        relief_rate = min(l['rate'] for l in lanes if l['relief'])

        eligible = []
        for order in orders:
            client = self.dirs.client_by_id[order['client_id']]
            row = []
            for idx, lane in enumerate(lanes):
                if lane['class_lock'] and lane['class_lock'] != client['service_class']:
                    continue
                if lane['exclusive'] and lane['exclusive'] != order['client_id']:
                    continue
                if not lane['relief'] and order['billable_slots'] > lane['capacity']:
                    continue
                row.append(idx)
            eligible.append(row)

        slots = [o['billable_slots'] for o in orders]
        families = [o['family'] for o in orders]
        n = len(orders)
        suffix = [0] * (n + 1)
        for i in range(n - 1, -1, -1):
            suffix[i] = suffix[i + 1] + slots[i]
        held_index = [i for i, lane in enumerate(lanes) if not lane['relief']]
        held_slot = {idx: slot for slot, idx in enumerate(held_index)}
        rates = [lane['rate'] for lane in lanes]
        held_rates = [lanes[i]['rate'] for i in held_index]

        def bound(i, free):
            """Cheapest completion if work could be split and families ignored."""
            remaining = suffix[i]
            total = 0
            for slot, rate in zip(free, held_rates):
                if remaining <= 0 or rate >= relief_rate:
                    break
                take = slot if slot < remaining else remaining
                total += take * rate
                remaining -= take
            return total + remaining * relief_rate

        # a lane's family set may not hold both halves of an incompatible pair
        conflicts = self.conflicts
        best = [None, None]
        leaves = [0]
        seen = {}

        def dfs(i, free, marks, cost):
            if best[0] is not None and cost + bound(i, free) >= best[0]:
                return
            if i == n:
                best[0] = cost
                best[1] = list(current)
                leaves[0] += 1
                return
            state = (i, free, marks)
            if state in seen and seen[state] <= cost:
                return
            seen[state] = cost
            for idx in eligible[i]:
                lane = lanes[idx]
                if lane['relief']:
                    nfree, nmarks = free, marks
                else:
                    slot = held_slot[idx]
                    if free[slot] < slots[i]:
                        continue
                    mark = marks[slot]
                    if families[i] in conflicts and conflicts[families[i]] & mark:
                        continue
                    lfree = list(free)
                    lfree[slot] -= slots[i]
                    nfree = tuple(lfree)
                    lmarks = list(marks)
                    lmarks[slot] = mark | {families[i]} if families[i] not in mark else mark
                    nmarks = tuple(frozenset(m) for m in lmarks)
                current[i] = idx
                dfs(i + 1, nfree, nmarks, cost + slots[i] * rates[idx])
                current[i] = None

        current = [None] * n
        start_free = tuple(lanes[i]['capacity'] for i in held_index)
        start_marks = tuple(frozenset() for _ in held_index)
        dfs(0, start_free, start_marks, 0)
        if best[1] is None:
            raise ValueError('no feasible placement at %s' % site)

        self.search['feasible_leaves'] += leaves[0]
        self.search['site_cost_micros'][site] = best[0]
        placement = {}
        for order, idx in zip(orders, best[1]):
            placement[order['order_id']] = lanes[idx]
            if lanes[idx]['relief']:
                self.search['displaced_orders'] += 1
        return placement

    # -- money -------------------------------------------------------------
    def settle(self, orders):
        """Decode-to-money for one population. Returns placed orders and tallies."""
        rejected, deferred, scored = [], [], []
        for order in orders:
            standing, revision = classify(order, self.dirs)
            order['billable_slots'] = billable_slots(
                order['load_units'], order['granularity'], self.params['quant_mode'])
            if standing == 'rejected':
                rejected.append(order)
            elif standing == 'deferred':
                deferred.append(order)
            else:
                order['revision'] = int(revision['revision'])
                order['family'] = revision['family']
                scored.append(order)

        admitted, passes, index, tiers = self.admit(scored)
        admitted_ids = {o['order_id'] for o in admitted}
        held = [o for o in scored if o['order_id'] not in admitted_ids]

        by_site = defaultdict(list)
        for order in admitted:
            by_site[self.dirs.client_by_id[order['client_id']]['site']].append(order)
        placement = {}
        for site in sorted(s['name'] for s in self.dirs.sites):
            placement.update(self.place_site(site, by_site.get(site, [])))

        placed = sorted(admitted, key=lambda o: o['order_id'])
        for order in placed:
            lane = placement[order['order_id']]
            slots = order['billable_slots']
            charge = slots * lane['rate']
            rebate = slots * self.policy.rebate_band[order['dispatch_mode']]
            order['lane_id'] = lane['lane_id']
            order['charge_micros'] = charge
            order['rebate_micros'] = rebate if rebate <= charge else charge
            order['net_micros'] = charge - order['rebate_micros']

        running = defaultdict(int)
        for order in placed:
            ceiling = int(self.dirs.client_by_id[order['client_id']]['budget_cap_micros'])
            over = running[order['client_id']] + order['net_micros'] - ceiling
            capped = over if over > 0 else 0
            if capped > order['net_micros']:
                capped = order['net_micros']
            order['capped_micros'] = capped
            running[order['client_id']] += order['net_micros'] - capped

        return {
            'orders': orders,
            'rejected': rejected,
            'deferred': deferred + held,
            'scored': scored,
            'placed': placed,
            'passes': passes,
            'congestion_index': index,
            'congestion_tier': tiers,
            'search': self.search,
        }


# --------------------------------------------------------------------------
# reports
# --------------------------------------------------------------------------
ORDER_FIELDS = ('billable_slots', 'capped_micros', 'charge_micros', 'client_id', 'lane_id',
                'net_micros', 'order_id', 'program_id', 'rebate_micros', 'revision', 'slack')
TOTAL_FIELDS = ('billable_slots', 'capped_micros', 'charge_micros', 'net_micros', 'rebate_micros')


def rollup(discriminator, name, orders):
    rows = [{k: o[k] for k in ORDER_FIELDS} for o in sorted(orders, key=lambda o: o['order_id'])]
    totals = {k: sum(o[k] for o in rows) for k in TOTAL_FIELDS}
    return {'order_count': len(rows), 'orders': rows, discriminator: name, 'totals': totals}


def write_json(path, payload):
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write('\n')


def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: %s <input_dir> <output_dir>\n' % os.path.basename(argv[0]))
        return 2
    source, target = argv[1], argv[2]
    os.makedirs(target, exist_ok=True)

    policy = Policy(source)
    dirs = Directories(source)
    stream = Stream(source, policy)

    params, audit, cal = resolve_constants(policy, dirs, stream, 'calibration')
    comparison = [{'control': name, 'published': published,
                   'reproduced': cal.figure(name, params)}
                  for name, published in policy.controls]

    decoder = Decoder(policy, dirs, stream, params)
    field = Settlement(policy, dirs, params).settle(decoder.decode_population('field'))
    calibration = Settlement(policy, dirs, params).settle(decoder.decode_population('calibration'))

    decoded_rows = sum(b.stored_count for b in stream.blocks['field'])
    placed = field['placed']
    summary = {
        'order_rows': len(field['orders']),
        'decoded_rows': decoded_rows,
        'orders_scored': len(field['scored']),
        'orders_placed': len(placed),
        'orders_deferred': len(field['deferred']),
        'orders_rejected': len(field['rejected']),
        'billable_slots_total': sum(o['billable_slots'] for o in placed),
        'charge_micros_total': sum(o['charge_micros'] for o in placed),
        'rebate_micros_total': sum(o['rebate_micros'] for o in placed),
        'capped_micros_total': sum(o['capped_micros'] for o in placed),
        'net_micros_total': sum(o['net_micros'] for o in placed),
        'lanes_used': len({o['lane_id'] for o in placed}),
    }

    by_region = defaultdict(list)
    by_segment = defaultdict(list)
    for order in placed:
        client = dirs.client_by_id[order['client_id']]
        by_region[dirs.region_of_site(client['site'])].append(order)
        by_segment[client['service_class']].append(order)
    regions = sorted({dirs.region_of_site(s['name']) for s in dirs.sites})
    segments = sorted({c['service_class'] for c in dirs.clients})

    for region in regions:
        write_json(os.path.join(target, 'region_%s.json' % region),
                   rollup('region', region, by_region.get(region, [])))
    for segment in segments:
        write_json(os.path.join(target, 'segment_%s.json' % segment),
                   rollup('service_class', segment, by_segment.get(segment, [])))

    region_net = {r: sum(o['net_micros'] for o in by_region.get(r, [])) for r in regions}
    segment_net = {s: sum(o['net_micros'] for o in by_segment.get(s, [])) for s in segments}
    seen = set()
    unique = True
    for order in placed:
        if order['order_id'] in seen:
            unique = False
        seen.add(order['order_id'])
    lane_load = defaultdict(int)
    for order in placed:
        lane_load[order['lane_id']] += order['billable_slots']
    capacity_ok = True
    for row in dirs.lanes:
        limit = int(row['slot_capacity'])
        if limit > 0 and lane_load.get(row['lane_id'], 0) > limit:
            capacity_ok = False
    region_count = sum(len(v) for v in by_region.values())
    segment_count = sum(len(v) for v in by_segment.values())
    region_ids = sorted(o['order_id'] for v in by_region.values() for o in v)
    segment_ids = sorted(o['order_id'] for v in by_segment.values() for o in v)

    quality = {
        'order_rows': summary['order_rows'],
        'decoded_rows': summary['decoded_rows'],
        'rejected_orders': sorted(o['order_id'] for o in field['rejected']),
        'deferred_orders': sorted(o['order_id'] for o in field['deferred']),
        'region_net_micros': region_net,
        'segment_net_micros': segment_net,
        'conservation_residual_micros': summary['net_micros_total'] - sum(region_net.values()),
        'segment_residual_micros': summary['net_micros_total'] - sum(segment_net.values()),
        'calibration_net_micros': sum(o['net_micros'] for o in calibration['placed']),
        'invariants': {
            'region_partition_closed': region_count == len(placed) and region_ids == sorted(seen),
            'segment_partition_closed': segment_count == len(placed) and segment_ids == region_ids,
            'order_identity_unique': unique and len(seen) == len(placed),
            'capacity_respected': capacity_ok,
        },
    }

    audit_out = {
        'candidate_space': audit,
        'resolved_parameters': dict(params),
        'calibration_comparison': comparison,
        'fixpoint': {
            'passes': field['passes'],
            'congestion_index': field['congestion_index'],
            'congestion_tier': field['congestion_tier'],
        },
        'assignment_search': {
            'sites_searched': field['search']['sites_searched'],
            'feasible_leaves': field['search']['feasible_leaves'],
            'displaced_orders': field['search']['displaced_orders'],
            'site_cost_micros': field['search']['site_cost_micros'],
        },
        'candidates_examined': sum(e['domain_size'] for e in audit),
        'candidates_rejected': sum(e['rejected'] for e in audit),
    }

    write_json(os.path.join(target, 'summary.json'), summary)
    write_json(os.path.join(target, 'data_quality.json'), quality)
    write_json(os.path.join(target, 'policy_audit.json'), audit_out)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
