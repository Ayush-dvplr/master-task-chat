#!/usr/bin/env python3
"""Recover the six withheld registry constants from a published index directory,
replay the benchmark workspaces against the recovered index and write the nine
reports.

usage: optimize.py INPUT_DIRECTORY OUTPUT_DIRECTORY
"""

import csv
import json
import os
import re
import struct
import sys
import zlib

M32 = 0xffffffff
M16 = 0xffff
MODULUS = 1000003
FULL_FLAG_SET = 0x07ff

FLAG_MASK_BYTES = 0x0001
FLAG_CHAIN_VERSION = 0x0002
FLAG_DELTA2_DAY = 0x0004
FLAG_DRIFT_KEY = 0x0008
FLAG_BLOCK_PERMUTE = 0x0010
FLAG_BACKREF_DEPS = 0x0020
FLAG_ENDIAN_ISLAND = 0x0040
FLAG_BIASED_COUNT = 0x0080
FLAG_ROT_STATUS = 0x0100
FLAG_XREF_KEY = 0x0200
FLAG_SPLIT_TAIL = 0x0400

PARAM_ORDER = ['salt', 'window_span', 'bias_limit', 'rotation_base',
               'permutation_multiplier', 'quarantine_days']
CALIBRATION_PARAM = {
    'salt word': 'salt',
    'window span': 'window_span',
    'bias limit': 'bias_limit',
    'rotation base': 'rotation_base',
    'shuffle multiplier': 'permutation_multiplier',
    'quarantine days': 'quarantine_days',
}
CONTROL_ORDER = ['CTRL-1', 'CTRL-2', 'CTRL-3', 'CTRL-4', 'CTRL-5', 'CTRL-6']
UNREADABLE = 'UNREADABLE'


class Unreadable(Exception):
    """A shard that cannot be read under the assignment being tested."""


# --------------------------------------------------------------------------
# binary shard format
# --------------------------------------------------------------------------

def read_header(data):
    if len(data) < 20:
        raise Unreadable('truncated header')
    magic, version, tier, flags, nonce, area_len, stored, check = struct.unpack_from(
        '<4sBBHIIHH', data, 0)
    if magic != b'PIDX' or version != 2:
        raise Unreadable('bad magic')
    if check != (zlib.crc32(data[:18]) & 0xffff):
        raise Unreadable('header check mismatch')
    if flags & FLAG_ENDIAN_ISLAND:
        nonce = struct.unpack_from('>I', data, 8)[0]
    if 20 + area_len > len(data):
        raise Unreadable('block area past end of file')
    return {'tier': tier, 'flags': flags, 'nonce': nonce,
            'area_len': area_len, 'stored': stored}


def parse_block(area, pos, flags, window_span, rotation_base):
    """Read the block at pos and verify its trailer."""
    if pos + 10 > len(area):
        raise Unreadable('block header past end of area')
    key, count, block_nonce = struct.unpack_from('<IHI', area, pos)
    if flags & FLAG_ENDIAN_ISLAND:
        count = struct.unpack_from('>H', area, pos + 4)[0]
    start = pos
    p = pos + 10
    ring = [(0, 0, 0, 0, 0)] * window_span
    records = []
    prev_code = 0
    day_prev1 = 0
    day_prev2 = 0
    for ordinal in range(count):
        if p + 12 > len(area):
            raise Unreadable('record past end of area')
        code, stored_bytes, day, status = struct.unpack_from('<IIHH', area, p)
        p += 12
        if flags & FLAG_ROT_STATUS:
            shift = (rotation_base + (ordinal % 8)) % 16
            if shift:
                status = ((status >> shift) | (status << (16 - shift))) & M16
        if flags & FLAG_CHAIN_VERSION and ordinal:
            code = (prev_code + code) & M32
        if flags & FLAG_DELTA2_DAY:
            day = (day + 2 * day_prev1 - day_prev2) & M16
        n_entries = status & 0xff
        entries = []
        backrefs = 0
        for _ in range(n_entries):
            if flags & FLAG_BACKREF_DEPS:
                if p + 1 > len(area):
                    raise Unreadable('tag byte past end of area')
                tag = area[p]
                p += 1
                if tag == 0:
                    if p + 14 > len(area):
                        raise Unreadable('dependency entry past end of area')
                    entry = struct.unpack_from('<IIIBB', area, p)
                    p += 14
                else:
                    if tag > window_span:
                        raise Unreadable('back reference tag above window span')
                    entry = ring[window_span - tag]
                    backrefs += 1
            else:
                if p + 14 > len(area):
                    raise Unreadable('dependency entry past end of area')
                entry = struct.unpack_from('<IIIBB', area, p)
                p += 14
            entries.append(entry)
            ring.insert(0, entry)
            if len(ring) > window_span:
                ring.pop()
        records.append({'ordinal': ordinal, 'vc': code, 'ab_stored': stored_bytes,
                        'day': day, 'status': status, 'entries': entries,
                        'backrefs': backrefs})
        day_prev2 = day_prev1
        day_prev1 = day
        prev_code = code
    if p + 4 > len(area):
        raise Unreadable('block trailer past end of area')
    trailer = struct.unpack_from('<I', area, p)[0]
    end = p + 4
    if trailer != (zlib.crc32(area[start:end - 4]) & M32):
        raise Unreadable('block trailer mismatch')
    if flags & FLAG_SPLIT_TAIL:
        tail = block_nonce % 7
        if end + tail > len(area):
            raise Unreadable('split tail past end of area')
        if any(area[end:end + tail]):
            raise Unreadable('split tail not zero filled')
        end += tail
    return {'key': key, 'count': count, 'nonce': block_nonce, 'start': start,
            'end': end, 'records': records}


def block_order(count, nonce, multiplier):
    """Logical order of the blocks as written, for BLOCK_PERMUTE."""
    order = list(range(count))
    state = nonce & M32
    for i in range(count - 1, 0, -1):
        state = (state * multiplier + 0x9E3779B9) & M32
        j = state % (i + 1)
        order[i], order[j] = order[j], order[i]
    return order


def decode_shard(data, consts, companion_nonce):
    """Decode one shard, applying every optional transform its flag word names."""
    head = read_header(data)
    flags = head['flags']
    nonce = head['nonce']
    area = data[20:20 + head['area_len']]
    if flags & FLAG_BIASED_COUNT:
        crc = zlib.crc32(consts['salt'] + struct.pack('<I', nonce)) & M32
        bias = (crc & 0xff) % consts['bias_limit']
    else:
        bias = 0
    count = head['stored'] - bias
    if count < 0:
        raise Unreadable('negative true block count')
    blocks = []
    pos = 0
    for _ in range(count):
        block = parse_block(area, pos, flags, consts['window_span'],
                            consts['rotation_base'])
        blocks.append(block)
        pos = block['end']
    if pos != head['area_len']:
        raise Unreadable('block area ends before or after its last block')
    if flags & FLAG_BLOCK_PERMUTE:
        written = block_order(count, nonce, consts['permutation_multiplier'])
        slot = [0] * count
        for file_index, logical_index in enumerate(written):
            slot[logical_index] = file_index
        logical = [blocks[slot[i]] for i in range(count)]
    else:
        logical = blocks
    drift = 0
    for position, block in enumerate(logical, 1):
        block['position'] = position
        if flags & FLAG_XREF_KEY:
            block['key'] = (block['key'] ^ companion_nonce) & M32
        block_key = block['nonce']
        if flags & FLAG_DRIFT_KEY:
            block_key = (block['nonce'] ^ drift) & M32
        block['block_key'] = block_key
        for record in block['records']:
            if flags & FLAG_MASK_BYTES:
                stream = zlib.crc32(consts['salt'] + struct.pack('<I', nonce) +
                                    struct.pack('<I', block_key) +
                                    struct.pack('<H', record['ordinal'])) & M32
                record['ab'] = (record['ab_stored'] ^ stream) & M32
            else:
                record['ab'] = record['ab_stored']
            drift = (drift + record['ab']) & M32
    result = dict(head)
    result['bias'] = bias
    result['count'] = count
    result['blocks'] = blocks
    result['logical'] = logical
    return result


def walk_area(data, flags, window_span, rotation_base):
    """Walk the block area without trusting the stored count."""
    head = read_header(data)
    area = data[20:20 + head['area_len']]
    blocks = []
    pos = 0
    while pos < len(area):
        block = parse_block(area, pos, flags, window_span, rotation_base)
        blocks.append(block)
        pos = block['end']
    if pos != len(area):
        raise Unreadable('block area ends before or after its last block')
    return blocks


def companion_nonces(pairs):
    """pairs: list of (name, nonce).  XREF companion of the same tier."""
    order = sorted(pairs, key=lambda item: item[1])
    result = {}
    for index, (name, nonce) in enumerate(order):
        result[name] = order[index - 1][1] if index else order[-1][1]
    return result


# --------------------------------------------------------------------------
# calibration controls
# --------------------------------------------------------------------------

def calibration_controls(shards, consts, snapshot_day):
    """The six control figures of the calibration population."""
    companions = companion_nonces(
        [(name, read_header(data)['nonce']) for name, data in shards])
    decoded = [decode_shard(data, consts, companions[name]) for name, data in shards]
    figures = {}
    figures['CTRL-1'] = sum(shard['count'] for shard in decoded)
    total = 0
    for shard in decoded:
        for block in shard['logical']:
            total = (total + block['key'] * block['position']) % MODULUS
    figures['CTRL-2'] = total
    total = 0
    for shard in decoded:
        for block in shard['logical']:
            for record in block['records']:
                total = (total + (record['ab'] + record['vc']) *
                         (record['ordinal'] + 1)) % MODULUS
    figures['CTRL-3'] = total
    total = 0
    for shard in decoded:
        for block in shard['logical']:
            for record in block['records']:
                for index, entry in enumerate(record['entries']):
                    value = ((entry[0] ^ entry[1]) & M32) + 7 * entry[3] + entry[4]
                    total = (total + value * (index + 1) *
                             (record['ordinal'] + 1)) % MODULUS
    figures['CTRL-4'] = total
    total = 0
    for shard in decoded:
        for block in shard['logical']:
            for record in block['records']:
                total = (total + (3 * (record['status'] >> 8) +
                                  (record['status'] & 0xff)) *
                         (record['ordinal'] + 1)) % MODULUS
    figures['CTRL-5'] = total
    count = 0
    for shard in decoded:
        for block in shard['logical']:
            for record in block['records']:
                if record['status'] & 0x0100:
                    continue
                day = record['day']
                if day <= snapshot_day and \
                        snapshot_day - day >= consts['quarantine_days']:
                    count += 1
    figures['CTRL-6'] = count
    return figures


def typed_value(parameter, value):
    """The typed constant behind a published candidate string."""
    if parameter == 'salt':
        return value.encode('ascii')
    if parameter == 'permutation_multiplier':
        return int(value, 16)
    return int(value)


def recover_constants(shards, candidates, published, snapshot_day):
    """The one assignment of the six constants that reproduces every figure."""
    wide = max(int(v) for v in candidates['window_span'])

    feasible = []
    for rotation in (int(v) for v in candidates['rotation_base']):
        counts = {}
        ok = True
        for name, data in shards:
            head = read_header(data)
            try:
                blocks = walk_area(data, head['flags'], wide, rotation)
            except Unreadable:
                ok = False
                break
            counts[name] = len(blocks)
        if ok:
            feasible.append((rotation, counts))
    if not feasible:
        raise SystemExit('no rotation base reads the calibration shards')

    survivors = []
    first_multiplier = int(candidates['permutation_multiplier'][0], 16)
    for rotation, counts in feasible:
        for salt in candidates['salt']:
            for bias_limit in (int(v) for v in candidates['bias_limit']):
                good = True
                for name, data in shards:
                    head = read_header(data)
                    crc = zlib.crc32(salt.encode('ascii') +
                                     struct.pack('<I', head['nonce'])) & M32
                    if head['stored'] - ((crc & 0xff) % bias_limit) != counts[name]:
                        good = False
                        break
                if not good:
                    continue
                for window in (int(v) for v in candidates['window_span']):
                    base = {'salt': salt.encode('ascii'), 'window_span': window,
                            'bias_limit': bias_limit, 'rotation_base': rotation,
                            'permutation_multiplier': first_multiplier,
                            'quarantine_days': 0}
                    try:
                        structural = calibration_controls(shards, base, snapshot_day)
                    except Unreadable:
                        continue
                    if any(structural[c] != published[c] for c in
                           ['CTRL-1', 'CTRL-4', 'CTRL-5']):
                        continue
                    for multiplier in (int(v, 16) for v in
                                       candidates['permutation_multiplier']):
                        base = dict(base)
                        base['permutation_multiplier'] = multiplier
                        try:
                            figures = calibration_controls(shards, base, snapshot_day)
                        except Unreadable:
                            continue
                        if any(figures[c] != published[c] for c in
                               ['CTRL-2', 'CTRL-3']):
                            continue
                        for quarantine in (int(v) for v in candidates['quarantine_days']):
                            consts = dict(base)
                            consts['quarantine_days'] = quarantine
                            try:
                                figures = calibration_controls(shards, consts, snapshot_day)
                            except Unreadable:
                                continue
                            if all(figures[c] == published[c] for c in CONTROL_ORDER):
                                survivors.append(consts)
    unique = []
    for consts in survivors:
        if consts not in unique:
            unique.append(consts)
    if len(unique) != 1:
        raise SystemExit('expected one constant assignment, found %d' % len(unique))
    return unique[0]


def weigh_candidates(shards, candidates, published, snapshot_day, recovered):
    """Verdict and falsifier of each candidate, in the order they were weighed."""
    rows = []
    for parameter in PARAM_ORDER:
        for value in candidates[parameter]:
            consts = dict(recovered)
            consts[parameter] = typed_value(parameter, value)
            if consts == recovered:
                rows.append({'parameter': parameter, 'value': value,
                             'verdict': 'accepted', 'falsifier': 'none'})
                continue
            try:
                figures = calibration_controls(shards, consts, snapshot_day)
            except Unreadable:
                rows.append({'parameter': parameter, 'value': value,
                             'verdict': 'rejected', 'falsifier': UNREADABLE})
                continue
            label = None
            for control in CONTROL_ORDER:
                if figures[control] != published[control]:
                    label = control
                    break
            if label is None:
                raise SystemExit('candidate %s %s is not falsified'
                                 % (parameter, value))
            rows.append({'parameter': parameter, 'value': value,
                         'verdict': 'rejected', 'falsifier': label})
    return rows


# --------------------------------------------------------------------------
# published documents
# --------------------------------------------------------------------------

def read_text(path):
    with open(path, 'r') as handle:
        return handle.read()


def parse_calibration(text):
    candidates = {}
    published = {}
    snapshot_day = None
    for line in text.splitlines():
        row = [cell.strip() for cell in line.strip().strip('|').split('|')]
        if len(row) == 2 and row[0] in CALIBRATION_PARAM:
            candidates[CALIBRATION_PARAM[row[0]]] = row[1].split()
        elif len(row) == 3 and row[0] in CONTROL_ORDER:
            published[row[0]] = {'figure': row[1], 'value': int(row[2])}
        else:
            match = re.match(r'^Calibration snapshot day:\s*(\d+)\s*$', line.strip())
            if match:
                snapshot_day = int(match.group(1))
    if len(candidates) != 6 or len(published) != 6 or snapshot_day is None:
        raise SystemExit('calibration slice is incomplete')
    return candidates, published, snapshot_day


def parse_licences(text):
    families = {'permissive': set(), 'copyleft': set()}
    for line in text.splitlines():
        match = re.match(r'^(Permissive|Copyleft):\s*(.+?)\s*\.?\s*$', line.strip())
        if match:
            families[match.group(1).lower()] = set(
                token.strip() for token in match.group(2).split(',') if token.strip())
    if not families['permissive'] or not families['copyleft']:
        raise SystemExit('licence families are missing')
    return families


def licence_family(expression, families):
    def family_of(identifier):
        if identifier in families['permissive']:
            return 'permissive'
        if identifier in families['copyleft']:
            return 'copyleft'
        raise SystemExit('unknown licence identifier %r' % identifier)

    tokens = expression.split()
    identifiers = tokens[0::2]
    joiners = tokens[1::2]
    if any(joiner != joiners[0] for joiner in joiners):
        raise SystemExit('mixed licence expression %r' % expression)
    if not joiners:
        return family_of(identifiers[0])
    if joiners[0].upper() == 'OR':
        for identifier in identifiers:
            if family_of(identifier) == 'permissive':
                return 'permissive'
        return 'copyleft'
    for identifier in identifiers:
        if family_of(identifier) == 'copyleft':
            return 'copyleft'
    return 'permissive'


def parse_version(text):
    parts = text.strip().split('.')
    if len(parts) != 3:
        raise SystemExit('bad version %r' % text)
    major, minor, patch = (int(part) for part in parts)
    return (major << 16) | (minor << 8) | patch


def version_text(code):
    return '%d.%d.%d' % (code >> 16, (code >> 8) & 0xff, code & 0xff)


def read_registry(path):
    rows = []
    with open(path, newline='') as handle:
        for row in csv.DictReader(handle):
            rows.append({'name': row['package'].strip(),
                        'key': int(row['package_key'].strip(), 16),
                        'renamed_from': (row['renamed_from'] or '').strip(),
                        'licence': row['licence'].strip()})
    return rows


def build_chains(rows):
    """Group the registry rows into rename chains, earliest name first.

    Returns the chain table keyed by chain identifier (the earliest name), the
    name to chain identifier map and the package key to chain identifier map.
    """
    by_name = {row['name']: row for row in rows}
    children = {}
    roots = []
    for row in rows:
        if row['renamed_from']:
            children.setdefault(row['renamed_from'], []).append(row['name'])
        else:
            roots.append(row['name'])
    chains = {}
    chain_of_name = {}
    key_to_chain = {}
    for root in roots:
        names = [root]
        while names[-1] in children:
            following = children[names[-1]]
            if len(following) != 1:
                raise SystemExit('ambiguous rename chain at %s' % names[-1])
            names.append(following[0])
        chain = {'names': names, 'reported': names[-1],
                 'licence': by_name[root]['licence'],
                 'newest_licence': by_name[names[-1]]['licence']}
        chains[root] = chain
        for name in names:
            if name in chain_of_name:
                raise SystemExit('registry name %s used twice' % name)
            chain_of_name[name] = root
            key_to_chain[by_name[name]['key']] = root
    return chains, chain_of_name, key_to_chain


def read_workspaces(path):
    workspaces = []
    with open(path, newline='') as handle:
        for row in csv.DictReader(handle):
            workspaces.append({'workspace': row['workspace'].strip(),
                               'snapshot_day': int(row['snapshot_day']),
                               'copyleft': row['copyleft'].strip()})
    return workspaces


def read_requirements(path):
    requirements = {}
    with open(path, newline='') as handle:
        for row in csv.DictReader(handle):
            entry = {'workspace': row['workspace'].strip(),
                     'package': row['package'].strip(),
                     'lowest': parse_version(row['lowest']),
                     'below': parse_version(row['below']),
                     'features': int(row['features'])}
            requirements.setdefault(entry['workspace'], []).append(entry)
    return requirements


# --------------------------------------------------------------------------
# index model
# --------------------------------------------------------------------------

class Index(object):
    """The decoded field population."""

    def __init__(self, directory, consts, chains, chain_of_name, key_to_chain,
                 families):
        self.consts = consts
        self.chains = chains
        self.chain_of_name = chain_of_name
        self.key_to_chain = key_to_chain
        self.families = families
        self.shards = []
        self.blocks = 0
        self.records = 0
        self.entries = 0
        self.backrefs = 0
        self.decoded_bytes = 0
        self.full_flag_shards = 0
        self.yanked_registered = 0
        self.deprecated = 0
        self.unregistered_records = 0
        self.unregistered_bytes = 0
        self.yanked_bytes = 0
        self.unregistered_targets = 0
        self.versions = {}
        self._load(directory)

    def _load(self, directory):
        files = []
        for name in sorted(os.listdir(directory)):
            if not name.endswith('.pidx'):
                continue
            data = open(os.path.join(directory, name), 'rb').read()
            if read_header(data)['tier'] == 2:
                files.append((name, data))
        companions = companion_nonces(
            [(name, read_header(data)['nonce']) for name, data in files])
        for name, data in files:
            shard = decode_shard(data, self.consts, companions[name])
            self.shards.append(shard)
            self.blocks += shard['count']
            if shard['flags'] == FULL_FLAG_SET:
                self.full_flag_shards += 1
            for block in shard['logical']:
                chain = self.key_to_chain.get(block['key'])
                for record in block['records']:
                    self.records += 1
                    self.entries += len(record['entries'])
                    self.backrefs += record['backrefs']
                    self.decoded_bytes += record['ab']
                    yanked = bool(record['status'] & 0x0100)
                    if record['status'] & 0x0200:
                        self.deprecated += 1
                    for entry in record['entries']:
                        if entry[0] not in self.key_to_chain:
                            self.unregistered_targets += 1
                    if chain is None:
                        self.unregistered_records += 1
                        self.unregistered_bytes += record['ab']
                        continue
                    if yanked:
                        self.yanked_registered += 1
                        self.yanked_bytes += record['ab']
                    self.versions.setdefault(chain, []).append({
                        'vc': record['vc'], 'ab': record['ab'], 'day': record['day'],
                        'yanked': yanked, 'entries': record['entries']})

    def family(self, chain, mode):
        text = self.chains[chain]['licence'] if mode == 'governing' \
            else self.chains[chain]['newest_licence']
        return licence_family(text, self.families)

    def eligible(self, snapshot_day, record):
        return (not record['yanked'] and record['day'] <= snapshot_day and
                snapshot_day - record['day'] >= self.consts['quarantine_days'])

    def quarantined(self, snapshot_day, record):
        return (not record['yanked'] and record['day'] <= snapshot_day and
                snapshot_day - record['day'] < self.consts['quarantine_days'])


# --------------------------------------------------------------------------
# resolution
# --------------------------------------------------------------------------

def settlement(state, direct, key_to_chain):
    """Least fixpoint of the enabled feature masks, with the pass count."""
    masks = {chain: direct.get(chain, 0) for chain in state}
    passes = 0
    while True:
        fresh = dict(masks)
        for chain, record in state.items():
            mask = masks[chain]
            for entry in record['entries']:
                gate = entry[4]
                if gate != 255 and not (mask >> gate) & 1:
                    continue
                target = key_to_chain.get(entry[0])
                if target in state:
                    fresh[target] |= entry[3]
        passes += 1
        if fresh == masks:
            return masks, passes
        masks = fresh


def resolve(workspace, requirements, index, mode):
    """The valid lock plan the workspace receives, or None when none exists."""
    snapshot_day = workspace['snapshot_day']
    copyleft_allowed = workspace['copyleft'] != 'forbidden'
    key_to_chain = index.key_to_chain
    direct = {}
    bounds = {}
    required = []
    for requirement in requirements:
        chain = index.chain_of_name.get(requirement['package'])
        if chain is None:
            return None
        if chain not in required:
            required.append(chain)
        direct[chain] = direct.get(chain, 0) | requirement['features']
        bounds.setdefault(chain, []).append((requirement['lowest'], requirement['below']))
    allowed = {}
    for chain in index.versions:
        allowed[chain] = copyleft_allowed or index.family(chain, mode) != 'copyleft'

    pool = {}
    for chain, records in index.versions.items():
        candidates = [r for r in records if index.eligible(snapshot_day, r)]
        candidates.sort(key=lambda r: r['vc'])
        pool[chain] = candidates

    def inside(chain, record, extra):
        for low, high in list(bounds.get(chain, [])) + list(extra):
            if not (low <= record['vc'] < high):
                return False
        return True

    best = [None]
    visited = set()

    def report(state):
        footprint = sum(record['ab'] for record in state.values())
        codes = sum(record['vc'] for record in state.values())
        ordered = sorted(state, key=lambda c: index.chains[c]['reported'])
        plan_text = ','.join('%s@%08x' % (index.chains[c]['reported'], state[c]['vc'])
                             for c in ordered)
        rank = (footprint, -codes, plan_text)
        if best[0] is None or rank < best[0][0]:
            best[0] = (rank, dict(state))

    def search(state, todo):
        marker = frozenset((chain, record['vc']) for chain, record in state.items())
        if marker in visited:
            return
        visited.add(marker)
        if todo:
            chain = todo[0]
            if not allowed.get(chain, False):
                return
            for record in pool[chain]:
                if not inside(chain, record, []):
                    continue
                nxt = dict(state)
                nxt[chain] = record
                search(nxt, todo[1:])
            return
        masks, _ = settlement(state, direct, key_to_chain)
        demands = {}
        broken = False
        for chain, record in state.items():
            mask = masks[chain]
            for entry in record['entries']:
                gate = entry[4]
                if gate != 255 and not (mask >> gate) & 1:
                    continue
                target = key_to_chain.get(entry[0])
                if target is None:
                    broken = True
                    break
                if target in state:
                    if not (entry[1] <= state[target]['vc'] < entry[2]):
                        broken = True
                        break
                else:
                    demands.setdefault(target, []).append((entry[1], entry[2]))
            if broken:
                break
        if broken:
            return
        if demands:
            chain = sorted(demands, key=lambda c: index.chains[c]['reported'])[0]
            if not allowed.get(chain, False):
                return
            for record in pool[chain]:
                if not inside(chain, record, demands[chain]):
                    continue
                nxt = dict(state)
                nxt[chain] = record
                search(nxt, [])
            return
        report(state)

    search({}, required)
    if best[0] is None:
        return None
    rank, state = best[0]
    masks, passes = settlement(state, direct, key_to_chain)
    return {'state': state, 'masks': masks, 'passes': passes,
            'footprint': rank[0], 'plan_text': rank[2]}


# --------------------------------------------------------------------------
# reports
# --------------------------------------------------------------------------

def write_json(path, payload):
    with open(path, 'w') as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write('\n')


def lock_plan_document(workspace, plan, index, quarantined):
    packages = []
    for chain in sorted(plan['state'], key=lambda c: index.chains[c]['reported']):
        record = plan['state'][chain]
        packages.append({
            'package': index.chains[chain]['reported'],
            'version': version_text(record['vc']),
            'features': plan['masks'][chain],
            'licence_family': index.family(chain, 'governing'),
            'bytes': record['ab'],
        })
    return {
        'workspace': workspace['workspace'],
        'snapshot_day': workspace['snapshot_day'],
        'copyleft': workspace['copyleft'],
        'footprint_bytes': plan['footprint'],
        'package_count': len(packages),
        'quarantined_records': quarantined,
        'packages': packages,
    }


def main():
    if len(sys.argv) != 3:
        raise SystemExit('usage: optimize.py INPUT_DIRECTORY OUTPUT_DIRECTORY')
    source = sys.argv[1]
    target = sys.argv[2]
    if not os.path.isdir(target):
        os.makedirs(target)

    candidates, published, snapshot_day = parse_calibration(
        read_text(os.path.join(source, 'calibration.md')))
    families = parse_licences(read_text(os.path.join(source, 'licence-policy.md')))
    chains, chain_of_name, key_to_chain = build_chains(
        read_registry(os.path.join(source, 'package-registry.csv')))
    workspaces = read_workspaces(os.path.join(source, 'workspaces.csv'))
    requirements = read_requirements(
        os.path.join(source, 'workspace-requirements.csv'))
    figures = {control: published[control]['value'] for control in published}

    calibration = []
    for name in sorted(os.listdir(source)):
        if not name.endswith('.pidx'):
            continue
        data = open(os.path.join(source, name), 'rb').read()
        if read_header(data)['tier'] == 1:
            calibration.append((name, data))

    consts = recover_constants(calibration, candidates, figures, snapshot_day)
    verdicts = weigh_candidates(calibration, candidates, figures, snapshot_day, consts)
    reproduced = calibration_controls(calibration, consts, snapshot_day)

    index = Index(source, consts, chains, chain_of_name, key_to_chain,
                   families)

    plans = {}
    divergence = []
    for workspace in workspaces:
        name = workspace['workspace']
        plan = resolve(workspace, requirements.get(name, []), index, 'governing')
        if plan is None:
            raise SystemExit('workspace %s admits no valid lock plan' % name)
        plans[name] = plan
        quarantined = sum(1 for chain in index.versions
                          for record in index.versions[chain]
                          if index.quarantined(workspace['snapshot_day'], record))
        write_json(os.path.join(target, 'scenario_%s.json' % name),
                   lock_plan_document(workspace, plan, index, quarantined))
        newest = resolve(workspace, requirements.get(name, []), index, 'newest')
        if newest is None or newest['plan_text'] != plan['plan_text']:
            divergence.append(name)

    locked = {}
    for plan in plans.values():
        for chain, record in plan['state'].items():
            locked[(chain, record['vc'])] = record['ab']
    locked_bytes = sum(locked.values())
    excluded_bytes = index.unregistered_bytes + index.yanked_bytes

    write_json(os.path.join(target, 'perf_report.json'), {
        'shards_decoded': len(index.shards),
        'blocks_decoded': index.blocks,
        'records_decoded': index.records,
        'dependency_entries_decoded': index.entries,
        'decoded_bytes': index.decoded_bytes,
        'excluded_bytes': excluded_bytes,
        'locked_bytes': locked_bytes,
        'byte_residual': index.decoded_bytes - excluded_bytes - locked_bytes,
        'workspaces_resolved': len(plans),
        'footprint_by_workspace': {name: plans[name]['footprint'] for name in plans},
        'recovered_parameters': {
            'salt': consts['salt'].decode('ascii'),
            'window_span': consts['window_span'],
            'bias_limit': consts['bias_limit'],
            'rotation_base': consts['rotation_base'],
            'permutation_multiplier': '0x%08x' % consts['permutation_multiplier'],
            'quarantine_days': consts['quarantine_days'],
        },
    })

    bottleneck = []
    for workspace in sorted(workspaces, key=lambda w: w['workspace']):
        name = workspace['workspace']
        plan = plans[name]
        held = []
        permissive = []
        copyleft = []
        for chain in sorted(plan['state'], key=lambda c: index.chains[c]['reported']):
            record = plan['state'][chain]
            reachable = [r for r in index.versions[chain]
                         if index.eligible(workspace['snapshot_day'], r)]
            newest = max(r['vc'] for r in reachable) if reachable else record['vc']
            if record['vc'] < newest:
                held.append({
                    'package': index.chains[chain]['reported'],
                    'locked': version_text(record['vc']),
                    'newest_eligible': version_text(newest),
                })
            family = index.family(chain, 'governing')
            (permissive if family == 'permissive' else copyleft).append(
                index.chains[chain]['reported'])
        bottleneck.append({
            'workspace': name,
            'held_back': held,
            'permissive_packages': sorted(permissive),
            'copyleft_packages': sorted(copyleft),
        })
    write_json(os.path.join(target, 'bottleneck_analysis.json'),
               {'workspaces': bottleneck})

    write_json(os.path.join(target, 'data_quality.json'), {
        'total_shards': len(index.shards),
        'shards_with_full_flag_set': index.full_flag_shards,
        'records_yanked': index.yanked_registered,
        'records_deprecated': index.deprecated,
        'records_unregistered_package': index.unregistered_records,
        'dependency_entries_back_referenced': index.backrefs,
        'dependency_entries_unregistered_target': index.unregistered_targets,
        'excluded_bytes_by_cause': {
            'unregistered_package': index.unregistered_bytes,
            'yanked': index.yanked_bytes,
        },
    })

    totals = {}
    for row in verdicts:
        if row['verdict'] == 'rejected':
            totals[row['falsifier']] = totals.get(row['falsifier'], 0) + 1
    write_json(os.path.join(target, 'recommendations.json'), {
        'candidates': verdicts,
        'falsifier_totals': totals,
        'calibration_table': [
            {'control': control, 'figure': published[control]['figure'],
             'published': figures[control], 'reproduced': reproduced[control]}
            for control in CONTROL_ORDER],
        'settlement_passes_by_workspace': {name: plans[name]['passes']
                                           for name in plans},
        'licence_divergence': sorted(divergence),
    })


if __name__ == '__main__':
    main()
