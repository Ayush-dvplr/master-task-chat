#!/usr/bin/env python3
"""Replay benchmark workspaces against a binary registry index.

Reads a registry directory (shards, registry tables and policy documents),
recovers the six withheld registry constants from the calibration slice, and
writes the five workspace lock plans plus the performance, bottleneck,
integrity and derivation documents.
"""

import csv
import itertools
import json
import os
import re
import struct
import sys
import zlib

MOD = 1000003

F_MASK_BYTES = 0x0001
F_CHAIN_VERSION = 0x0002
F_DELTA2_DAY = 0x0004
F_DRIFT_KEY = 0x0008
F_BLOCK_PERMUTE = 0x0010
F_BACKREF_DEPS = 0x0020
F_ENDIAN_ISLAND = 0x0040
F_BIASED_COUNT = 0x0080
F_ROT_STATUS = 0x0100
F_XREF_KEY = 0x0200
F_SPLIT_TAIL = 0x0400

TIER_REHEARSAL, TIER_CALIBRATION, TIER_FIELD = 0, 1, 2

ZERO_ENTRY = (0, 0, 0, 0, 0)

PARAM_ORDER = ['salt', 'window_span', 'bias_limit', 'rotation_base',
               'permutation_multiplier', 'quarantine_days']
PARAM_ALIASES = {
    'salt word': 'salt',
    'window span': 'window_span',
    'bias limit': 'bias_limit',
    'rotation base': 'rotation_base',
    'shuffle multiplier': 'permutation_multiplier',
    'quarantine days': 'quarantine_days',
}


class Unreadable(Exception):
    """A shard cannot be read under the assignment being weighed."""


# --------------------------------------------------------------------------
# document parsing
# --------------------------------------------------------------------------

def read_text(path):
    with open(path, 'r', encoding='utf-8') as fh:
        return fh.read()


def table_rows(text):
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith('|'):
            continue
        cells = [c.strip() for c in line.strip('|').split('|')]
        if all(set(c) <= set('-: ') and c for c in cells):
            continue
        yield cells


def parse_calibration(path):
    text = read_text(path)
    candidates = {}
    published = []
    for cells in table_rows(text):
        if len(cells) == 2:
            key = PARAM_ALIASES.get(cells[0].lower())
            if key:
                candidates[key] = cells[1].split()
        elif len(cells) == 3 and re.fullmatch(r'CTRL-\d+', cells[0]):
            published.append((cells[0], cells[1], int(cells[2])))
    snap = int(re.search(r'[Cc]alibration snapshot day:\s*(\d+)', text).group(1))
    missing = [p for p in PARAM_ORDER if p not in candidates]
    if missing:
        raise ValueError('calibration slice lists no candidates for %s' % missing)
    published.sort(key=lambda r: int(r[0].split('-')[1]))
    return candidates, published, snap


def parse_licence_families(path):
    text = read_text(path)
    fams = {}
    for fam in ('permissive', 'copyleft'):
        m = re.search(r'^%s:\s*(.+?)\.$' % fam.capitalize(), text, re.M | re.S)
        for ident in m.group(1).replace('\n', ' ').split(','):
            fams[ident.strip()] = fam
    return fams


def licence_family(expr, fams):
    expr = expr.strip()
    if ' OR ' in expr:
        parts = [p.strip() for p in expr.split(' OR ')]
        return 'permissive' if any(fams.get(p) == 'permissive' for p in parts) else 'copyleft'
    if ' AND ' in expr:
        parts = [p.strip() for p in expr.split(' AND ')]
        return 'copyleft' if any(fams.get(p) == 'copyleft' for p in parts) else 'permissive'
    return fams.get(expr, 'copyleft')


def read_csv(path):
    with open(path, newline='', encoding='utf-8') as fh:
        return list(csv.DictReader(fh))


def version_string(code):
    return '%d.%d.%d' % ((code >> 16) & 0xFFFF, (code >> 8) & 0xFF, code & 0xFF)


def version_code(text):
    major, minor, patch = (int(x) for x in text.split('.'))
    return major * 65536 + minor * 256 + patch


# --------------------------------------------------------------------------
# shard decoding
# --------------------------------------------------------------------------

def rotr16(value, amount):
    amount %= 16
    if amount == 0:
        return value & 0xFFFF
    return ((value >> amount) | (value << (16 - amount))) & 0xFFFF


def read_header(data):
    if len(data) < 20 or data[0:4] != b'PIDX':
        raise Unreadable('magic')
    flags = struct.unpack_from('<H', data, 6)[0]
    if zlib.crc32(data[0:18]) & 0xFFFF != struct.unpack_from('<H', data, 18)[0]:
        raise Unreadable('header check')
    nonce = struct.unpack_from('>I' if flags & F_ENDIAN_ISLAND else '<I', data, 8)[0]
    return {
        'version': data[4],
        'tier': data[5],
        'flags': flags,
        'nonce': nonce,
        'area': struct.unpack_from('<I', data, 12)[0],
        'stored': struct.unpack_from('<H', data, 16)[0],
    }


def load_shards(dirpath):
    shards = []
    for name in sorted(os.listdir(dirpath)):
        path = os.path.join(dirpath, name)
        if not os.path.isfile(path) or not name.endswith('.pidx'):
            continue
        with open(path, 'rb') as fh:
            data = fh.read()
        shards.append((name, data, read_header(data)))
    return shards


def parse_structure(data, hdr, salt, bias_limit, rotation_base, window_span):
    """Structural pass in file order; everything that fixes byte lengths."""
    flags = hdr['flags']
    count = hdr['stored']
    if flags & F_BIASED_COUNT:
        keystream = salt.encode('ascii') + struct.pack('<I', hdr['nonce'])
        count -= (zlib.crc32(keystream) & 0xFF) % bias_limit
    if count < 0:
        raise Unreadable('negative block count')
    end = 20 + hdr['area']
    if end > len(data):
        raise Unreadable('block area past end of file')
    big_counts = bool(flags & F_ENDIAN_ISLAND)
    rot = bool(flags & F_ROT_STATUS)
    backref = bool(flags & F_BACKREF_DEPS)
    pos = 20
    blocks = []
    for _ in range(count):
        if pos + 10 > end:
            raise Unreadable('block header past end')
        start = pos
        key_raw = struct.unpack_from('<I', data, pos)[0]
        rec_count = struct.unpack_from('>H' if big_counts else '<H', data, pos + 4)[0]
        block_nonce = struct.unpack_from('<I', data, pos + 6)[0]
        pos += 10
        ring = [ZERO_ENTRY] * window_span
        records = []
        for ordinal in range(rec_count):
            if pos + 12 > end:
                raise Unreadable('version record past end')
            v_raw, a_raw, d_raw, s_raw = struct.unpack_from('<IIHH', data, pos)
            pos += 12
            status = rotr16(s_raw, rotation_base + (ordinal % 8)) if rot else s_raw
            dep_count = status & 0xFF
            deps = []
            for _entry in range(dep_count):
                if backref:
                    if pos + 1 > end:
                        raise Unreadable('entry tag past end')
                    tag = data[pos]
                    pos += 1
                    if tag == 0:
                        if pos + 14 > end:
                            raise Unreadable('dependency entry past end')
                        tk, lo, hi = struct.unpack_from('<III', data, pos)
                        entry = (tk, lo, hi, data[pos + 12], data[pos + 13])
                        pos += 14
                        was_backref = False
                    else:
                        if tag > window_span:
                            raise Unreadable('back reference tag above window span')
                        entry = ring[window_span - tag]
                        was_backref = True
                    ring = [entry] + ring[:-1]
                else:
                    if pos + 14 > end:
                        raise Unreadable('dependency entry past end')
                    tk, lo, hi = struct.unpack_from('<III', data, pos)
                    entry = (tk, lo, hi, data[pos + 12], data[pos + 13])
                    pos += 14
                    was_backref = False
                deps.append((entry, was_backref))
            records.append((v_raw, a_raw, d_raw, status >> 8, dep_count, deps))
        if pos + 4 > end:
            raise Unreadable('block trailer past end')
        if zlib.crc32(data[start:pos]) != struct.unpack_from('<I', data, pos)[0]:
            raise Unreadable('block trailer mismatch')
        pos += 4
        if flags & F_SPLIT_TAIL:
            pos += block_nonce % 7
            if pos > end:
                raise Unreadable('split tail past end of file')
        blocks.append((key_raw, block_nonce, records))
    if pos != end:
        raise Unreadable('block area ends before or after its last block')
    return blocks


def permutation(count, nonce, multiplier):
    order = list(range(count))
    state = nonce
    for i in range(count - 1, 0, -1):
        state = (state * multiplier + 0x9E3779B9) & 0xFFFFFFFF
        j = state % (i + 1)
        order[i], order[j] = order[j], order[i]
    return order


def resolve_shard(hdr, blocks, salt, multiplier, companion_nonce):
    """Put blocks in logical order and undo the value level transforms."""
    flags = hdr['flags']
    nonce = hdr['nonce']
    if flags & F_BLOCK_PERMUTE:
        order = permutation(len(blocks), nonce, multiplier)
        logical = [None] * len(blocks)
        for file_pos, logical_pos in enumerate(order):
            logical[logical_pos] = blocks[file_pos]
    else:
        logical = list(blocks)

    salt_bytes = salt.encode('ascii')
    mask_bytes = bool(flags & F_MASK_BYTES)
    drift = 0
    out = []
    for key_raw, block_nonce, raw_records in logical:
        key = key_raw ^ companion_nonce if flags & F_XREF_KEY else key_raw
        block_key = block_nonce ^ drift if flags & F_DRIFT_KEY else block_nonce
        records = []
        previous_version = 0
        day_1 = day_2 = 0
        block_sum = 0
        for ordinal, (v_raw, a_raw, d_raw, status_byte, dep_count, deps) in \
                enumerate(raw_records):
            if mask_bytes:
                stream = salt_bytes + struct.pack('<IIH', nonce, block_key, ordinal)
                artifact_bytes = a_raw ^ zlib.crc32(stream)
            else:
                artifact_bytes = a_raw
            if flags & F_CHAIN_VERSION and ordinal:
                code = (previous_version + v_raw) & 0xFFFFFFFF
            else:
                code = v_raw
            previous_version = code
            if flags & F_DELTA2_DAY:
                day = (d_raw + 2 * day_1 - day_2) & 0xFFFF
            else:
                day = d_raw
            day_2, day_1 = day_1, day
            block_sum += artifact_bytes
            records.append({
                'version_code': code,
                'artifact_bytes': artifact_bytes,
                'publish_day': day,
                'status_byte': status_byte,
                'dep_count': dep_count,
                'deps': deps,
                'ordinal': ordinal,
            })
        drift = (drift + block_sum) & 0xFFFFFFFF
        out.append({'key': key, 'block_nonce': block_nonce, 'records': records})
    return out


def companion_nonces(shards):
    """Same tier shard whose nonce is the next smaller one, wrapping around."""
    ordered = sorted({hdr['nonce'] for _n, _d, hdr in shards})
    return {n: (ordered[i - 1] if i else ordered[-1]) for i, n in enumerate(ordered)}


def decode_tier(shards, salt, bias_limit, rotation_base, window_span, multiplier,
                structures=None):
    companions = companion_nonces(shards)
    out = []
    for name, data, hdr in shards:
        if structures is None:
            blocks = parse_structure(data, hdr, salt, bias_limit, rotation_base, window_span)
        else:
            blocks = structures[name]
        out.append((name, hdr,
                    resolve_shard(hdr, blocks, salt, multiplier, companions[hdr['nonce']])))
    return out


# --------------------------------------------------------------------------
# calibration controls
# --------------------------------------------------------------------------

def control_figures(decoded, snapshot_day, quarantine_days):
    """The six published control figures, in CTRL-1 to CTRL-6 order.

    Positions and ordinals are one based here, as the figure notes require,
    while the shard transforms use the zero based ordinal of the format.
    """
    blocks = key_digest = size_digest = dep_digest = status_digest = eligible = 0
    for _name, _hdr, logical in decoded:
        blocks += len(logical)
        for position, block in enumerate(logical, 1):
            key_digest += block['key'] * position
            for record in block['records']:
                ordinal = record['ordinal'] + 1
                size_digest += (record['artifact_bytes'] + record['version_code']) * ordinal
                status_digest += (3 * record['status_byte'] + record['dep_count']) * ordinal
                for entry_pos, (entry, _back) in enumerate(record['deps'], 1):
                    value = (entry[0] ^ entry[1]) + 7 * entry[3] + entry[4]
                    dep_digest += value * entry_pos * ordinal
                if (not record['status_byte'] & 1
                        and record['publish_day'] <= snapshot_day
                        and record['publish_day'] <= snapshot_day - quarantine_days):
                    eligible += 1
    return [blocks, key_digest % MOD, size_digest % MOD, dep_digest % MOD,
            status_digest % MOD, eligible]


def recover_constants(calib_shards, candidates, published, snapshot_day):
    """Find the one assignment of the six constants that reproduces every figure."""
    targets = [row[2] for row in published]
    structure_cache = {}

    def structures(salt, bias_limit, rotation_base, window_span):
        key = (salt, bias_limit, rotation_base, window_span)
        if key not in structure_cache:
            try:
                structure_cache[key] = {
                    name: parse_structure(data, hdr, salt, bias_limit,
                                          rotation_base, window_span)
                    for name, data, hdr in calib_shards}
            except Unreadable:
                structure_cache[key] = None
        return structure_cache[key]

    found = []
    for salt, bias_limit, rotation_base, window_span in itertools.product(
            candidates['salt'],
            [int(v) for v in candidates['bias_limit']],
            [int(v) for v in candidates['rotation_base']],
            [int(v) for v in candidates['window_span']]):
        built = structures(salt, bias_limit, rotation_base, window_span)
        if built is None:
            continue
        for multiplier in [int(v, 16) for v in candidates['permutation_multiplier']]:
            decoded = decode_tier(calib_shards, salt, bias_limit, rotation_base,
                                  window_span, multiplier, built)
            for quarantine in [int(v) for v in candidates['quarantine_days']]:
                if control_figures(decoded, snapshot_day, quarantine) == targets:
                    found.append({'salt': salt, 'bias_limit': bias_limit,
                                  'rotation_base': rotation_base,
                                  'window_span': window_span,
                                  'permutation_multiplier': multiplier,
                                  'quarantine_days': quarantine})
    if len(found) != 1:
        raise ValueError('expected exactly one assignment, found %d' % len(found))
    return found[0]


def falsifier_of(calib_shards, assignment, snapshot_day, targets):
    """UNREADABLE, or the first control whose figure differs, or 'none'."""
    try:
        decoded = decode_tier(calib_shards, assignment['salt'], assignment['bias_limit'],
                              assignment['rotation_base'], assignment['window_span'],
                              assignment['permutation_multiplier'])
    except Unreadable:
        return 'UNREADABLE'
    figures = control_figures(decoded, snapshot_day, assignment['quarantine_days'])
    for index, (got, want) in enumerate(zip(figures, targets)):
        if got != want:
            return 'CTRL-%d' % (index + 1)
    return 'none'


# --------------------------------------------------------------------------
# registry identity
# --------------------------------------------------------------------------

def build_registry(rows, fams):
    renamed_to = {}
    by_name = {}
    for row in rows:
        by_name[row['package']] = row
        if row['renamed_from']:
            renamed_to[row['renamed_from']] = row['package']
    chains = []
    for row in rows:
        if row['renamed_from']:
            continue
        chain = [row['package']]
        while chain[-1] in renamed_to:
            chain.append(renamed_to[chain[-1]])
        chains.append(chain)

    reported = {}
    key_to_package = {}
    governing = {}
    newest_reading = {}
    for chain in chains:
        name = chain[-1]
        for member in chain:
            reported[member] = name
            key_to_package[int(by_name[member]['package_key'], 16)] = name
        governing[name] = licence_family(by_name[chain[0]]['licence'], fams)
        newest_reading[name] = licence_family(by_name[chain[-1]]['licence'], fams)
    return {'chains': chains, 'reported': reported, 'key_to_package': key_to_package,
            'governing': governing, 'newest_reading': newest_reading}


# --------------------------------------------------------------------------
# resolution
# --------------------------------------------------------------------------

def plan_text(assignment):
    return ','.join('%s@%08x' % (name, record['version_code'])
                    for name, record in sorted(assignment.items()))


def feature_state(assignment, direct, key_to_package):
    """Smallest feature assignment, and the number of settlement passes."""
    state = {name: direct.get(name, 0) for name in assignment}
    passes = 0
    while True:
        passes += 1
        nxt = dict(state)
        for name, record in assignment.items():
            mask = state[name]
            for entry, _back in record['deps']:
                if entry[4] != 255 and not (mask >> entry[4]) & 1:
                    continue
                target = key_to_package.get(entry[0])
                if target in nxt:
                    nxt[target] |= entry[3]
        if nxt == state:
            return state, passes
        state = nxt


def solve_workspace(workspace, requirements, packages, registry, quarantine_days, families):
    """The valid lock plan with the smallest footprint, or None."""
    snapshot = workspace['snapshot_day']
    allow_copyleft = workspace['copyleft'] == 'allowed'
    key_to_package = registry['key_to_package']

    def permitted(name):
        return allow_copyleft or families[name] == 'permissive'

    eligible = {}
    for name, records in packages.items():
        eligible[name] = [r for r in records
                          if not r['status_byte'] & 1
                          and r['publish_day'] <= snapshot
                          and r['publish_day'] <= snapshot - quarantine_days]

    direct = {}
    bounds = {}
    for req in requirements:
        name = registry['reported'].get(req['package'])
        if name is None:
            return None
        direct[name] = direct.get(name, 0) | int(req['features'])
        low, high = version_code(req['lowest']), version_code(req['below'])
        if name in bounds:
            previous = bounds[name]
            bounds[name] = (max(previous[0], low), min(previous[1], high))
        else:
            bounds[name] = (low, high)

    seeds = []
    for name, (low, high) in sorted(bounds.items()):
        if not permitted(name):
            return None
        choices = [r for r in eligible.get(name, [])
                   if low <= r['version_code'] < high]
        if not choices:
            return None
        seeds.append([(name, r) for r in choices])

    best = [None]

    def consider(assignment, footprint, state):
        key = (footprint,
               -sum(r['version_code'] for r in assignment.values()),
               plan_text(assignment))
        if best[0] is None or key < best[0][0]:
            _final, passes = feature_state(assignment, direct, key_to_package)
            best[0] = (key, dict(assignment), state, passes, footprint)

    def search(assignment, footprint):
        if best[0] is not None and footprint > best[0][0][0]:
            return
        state, _passes = feature_state(assignment, direct, key_to_package)
        for name, record in list(assignment.items()):
            mask = state[name]
            for entry, _back in record['deps']:
                if entry[4] != 255 and not (mask >> entry[4]) & 1:
                    continue
                target = key_to_package.get(entry[0])
                if target is None:
                    return
                if target in assignment:
                    if not entry[1] <= assignment[target]['version_code'] < entry[2]:
                        return
                    continue
                if not permitted(target):
                    return
                for choice in eligible.get(target, []):
                    if entry[1] <= choice['version_code'] < entry[2]:
                        assignment[target] = choice
                        search(assignment, footprint + choice['artifact_bytes'])
                        del assignment[target]
                return
        consider(assignment, footprint, state)

    for combination in itertools.product(*seeds):
        assignment = dict(combination)
        if len(assignment) != len(seeds):
            continue
        search(assignment, sum(r['artifact_bytes'] for r in assignment.values()))

    if best[0] is None:
        return None
    _key, assignment, state, passes, footprint = best[0]
    return {'assignment': assignment, 'features': state, 'passes': passes,
            'footprint': footprint, 'eligible': eligible}


# --------------------------------------------------------------------------
# documents
# --------------------------------------------------------------------------

def write_json(path, payload):
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write('\n')


def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: optimize.py <input-dir> <output-dir>\n')
        return 2
    src, dst = argv[1], argv[2]
    os.makedirs(dst, exist_ok=True)

    candidates, published, calib_day = parse_calibration(os.path.join(src, 'calibration.md'))
    fams = parse_licence_families(os.path.join(src, 'licence-policy.md'))
    registry_rows = read_csv(os.path.join(src, 'package-registry.csv'))
    workspace_rows = read_csv(os.path.join(src, 'workspaces.csv'))
    requirement_rows = read_csv(os.path.join(src, 'workspace-requirements.csv'))

    shards = load_shards(src)
    calib_shards = [s for s in shards if s[2]['tier'] == TIER_CALIBRATION]
    field_shards = [s for s in shards if s[2]['tier'] == TIER_FIELD]

    recovered = recover_constants(calib_shards, candidates, published, calib_day)
    targets = [row[2] for row in published]
    reproduced = control_figures(
        decode_tier(calib_shards, recovered['salt'], recovered['bias_limit'],
                    recovered['rotation_base'], recovered['window_span'],
                    recovered['permutation_multiplier']),
        calib_day, recovered['quarantine_days'])

    recovered_text = {
        'salt': recovered['salt'],
        'window_span': str(recovered['window_span']),
        'bias_limit': str(recovered['bias_limit']),
        'rotation_base': str(recovered['rotation_base']),
        'permutation_multiplier': '0x%08x' % recovered['permutation_multiplier'],
        'quarantine_days': str(recovered['quarantine_days']),
    }
    candidate_records = []
    totals = {}
    for parameter in PARAM_ORDER:
        for value in candidates[parameter]:
            accepted = value == recovered_text[parameter]
            if accepted:
                label = 'none'
            else:
                trial = dict(recovered)
                trial[parameter] = value if parameter == 'salt' else (
                    int(value, 16) if parameter == 'permutation_multiplier' else int(value))
                label = falsifier_of(calib_shards, trial, calib_day, targets)
                totals[label] = totals.get(label, 0) + 1
            candidate_records.append({
                'parameter': parameter,
                'value': value,
                'verdict': 'accepted' if accepted else 'rejected',
                'falsifier': label,
            })

    registry = build_registry(registry_rows, fams)
    key_to_package = registry['key_to_package']

    decoded_field = decode_tier(field_shards, recovered['salt'], recovered['bias_limit'],
                                recovered['rotation_base'], recovered['window_span'],
                                recovered['permutation_multiplier'])

    packages = {}
    blocks_decoded = records_decoded = entries_decoded = 0
    decoded_bytes = 0
    bytes_unregistered = bytes_yanked = 0
    records_yanked = records_deprecated = records_unregistered = 0
    entries_back_referenced = entries_unregistered_target = 0
    for _name, _hdr, logical in decoded_field:
        blocks_decoded += len(logical)
        for block in logical:
            name = key_to_package.get(block['key'])
            for record in block['records']:
                records_decoded += 1
                entries_decoded += len(record['deps'])
                decoded_bytes += record['artifact_bytes']
                yanked = bool(record['status_byte'] & 1)
                if record['status_byte'] & 2:
                    records_deprecated += 1
                if name is None:
                    records_unregistered += 1
                    bytes_unregistered += record['artifact_bytes']
                else:
                    if yanked:
                        records_yanked += 1
                        bytes_yanked += record['artifact_bytes']
                    packages.setdefault(name, []).append(record)
                for entry, was_backref in record['deps']:
                    if was_backref:
                        entries_back_referenced += 1
                    if entry[0] not in key_to_package:
                        entries_unregistered_target += 1

    requirements = {}
    for row in requirement_rows:
        requirements.setdefault(row['workspace'], []).append(row)

    workspaces = []
    for row in workspace_rows:
        workspaces.append({'workspace': row['workspace'],
                           'snapshot_day': int(row['snapshot_day']),
                           'copyleft': row['copyleft']})

    quarantine_days = recovered['quarantine_days']
    results = {}
    divergence = []
    for workspace in workspaces:
        name = workspace['workspace']
        reqs = requirements.get(name, [])
        solved = solve_workspace(workspace, reqs, packages, registry,
                                 quarantine_days, registry['governing'])
        if solved is None:
            raise ValueError('no valid lock plan for workspace %s' % name)
        results[name] = solved
        alternative = solve_workspace(workspace, reqs, packages, registry,
                                      quarantine_days, registry['newest_reading'])
        if alternative is None or plan_text(alternative['assignment']) != \
                plan_text(solved['assignment']):
            divergence.append(name)

    locked_versions = {}
    for solved in results.values():
        for name, record in solved['assignment'].items():
            locked_versions[(name, record['version_code'])] = record['artifact_bytes']
    locked_bytes = sum(locked_versions.values())
    excluded_bytes = bytes_unregistered + bytes_yanked

    for workspace in workspaces:
        name = workspace['workspace']
        solved = results[name]
        snapshot = workspace['snapshot_day']
        quarantined = 0
        for records in packages.values():
            for record in records:
                if (not record['status_byte'] & 1
                        and record['publish_day'] <= snapshot
                        and record['publish_day'] > snapshot - quarantine_days):
                    quarantined += 1
        entries = []
        for package, record in sorted(solved['assignment'].items()):
            entries.append({
                'package': package,
                'version': version_string(record['version_code']),
                'features': solved['features'][package],
                'licence_family': registry['governing'][package],
                'bytes': record['artifact_bytes'],
            })
        write_json(os.path.join(dst, 'scenario_%s.json' % name), {
            'workspace': name,
            'snapshot_day': snapshot,
            'copyleft': workspace['copyleft'],
            'footprint_bytes': solved['footprint'],
            'package_count': len(solved['assignment']),
            'quarantined_records': quarantined,
            'packages': entries,
        })

    write_json(os.path.join(dst, 'perf_report.json'), {
        'shards_decoded': len(field_shards),
        'blocks_decoded': blocks_decoded,
        'records_decoded': records_decoded,
        'dependency_entries_decoded': entries_decoded,
        'decoded_bytes': decoded_bytes,
        'excluded_bytes': excluded_bytes,
        'locked_bytes': locked_bytes,
        'byte_residual': decoded_bytes - excluded_bytes - locked_bytes,
        'workspaces_resolved': len(workspaces),
        'footprint_by_workspace': {w['workspace']: results[w['workspace']]['footprint']
                                   for w in workspaces},
        'recovered_parameters': {
            'salt': recovered['salt'],
            'window_span': recovered['window_span'],
            'bias_limit': recovered['bias_limit'],
            'rotation_base': recovered['rotation_base'],
            'quarantine_days': recovered['quarantine_days'],
            'permutation_multiplier': '0x%08x' % recovered['permutation_multiplier'],
        },
    })

    analysis = []
    for workspace in sorted(workspaces, key=lambda w: w['workspace']):
        name = workspace['workspace']
        solved = results[name]
        held_back = []
        permissive = []
        copyleft = []
        for package, record in sorted(solved['assignment'].items()):
            newest = max(r['version_code'] for r in solved['eligible'][package])
            if record['version_code'] < newest:
                held_back.append({'package': package,
                                  'locked': version_string(record['version_code']),
                                  'newest_eligible': version_string(newest)})
            if registry['governing'][package] == 'permissive':
                permissive.append(package)
            else:
                copyleft.append(package)
        analysis.append({'workspace': name, 'held_back': held_back,
                         'permissive_packages': permissive,
                         'copyleft_packages': copyleft})
    write_json(os.path.join(dst, 'bottleneck_analysis.json'), {'workspaces': analysis})

    write_json(os.path.join(dst, 'data_quality.json'), {
        'total_shards': len(field_shards),
        'shards_with_full_flag_set': sum(1 for _n, _d, h in field_shards
                                         if h['flags'] == 0x07FF),
        'records_yanked': records_yanked,
        'records_deprecated': records_deprecated,
        'records_unregistered_package': records_unregistered,
        'dependency_entries_back_referenced': entries_back_referenced,
        'dependency_entries_unregistered_target': entries_unregistered_target,
        'excluded_bytes_by_cause': {'unregistered_package': bytes_unregistered,
                                    'yanked': bytes_yanked},
    })

    write_json(os.path.join(dst, 'recommendations.json'), {
        'candidates': candidate_records,
        'falsifier_totals': totals,
        'calibration_table': [
            {'control': control, 'figure': figure, 'published': value,
             'reproduced': reproduced[index]}
            for index, (control, figure, value) in enumerate(published)],
        'settlement_passes_by_workspace': {w['workspace']: results[w['workspace']]['passes']
                                           for w in workspaces},
        'licence_divergence': sorted(divergence),
    })
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
