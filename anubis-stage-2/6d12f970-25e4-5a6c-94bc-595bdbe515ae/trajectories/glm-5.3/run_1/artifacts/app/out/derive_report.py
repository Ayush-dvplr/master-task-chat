#!/usr/bin/env python3
"""Derive the season settlement of a dispatch authority corpus.

Usage:  derive_report.py <input-directory> <output-directory>

Everything written to the output directory is derived from the files in the
input directory: the withheld wire constants are recovered against the
calibration population and its published control figures, the field population
is then decoded, scored, admitted, placed on lanes and settled for money, and
the reports are written from that single final derivation.

No figure recovered from a corpus appears here as a fixed literal; the policy
constants the documents state in prose (rebate bands, ceilings, tier factors,
granularity list, the HMAC key, the declared domain of each withheld constant)
are parsed out of the policy documents that ship with the corpus.
"""

import csv
import hashlib
import hmac
import itertools
import json
import os
import re
import sys
import zlib

sys.setrecursionlimit(100000)

WORD_NUM = {'no': 0, 'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4,
            'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10}

RESERVED_BIT = 0x800
REC_BASE_LEN = 13
REC_EXT_LEN = 15
WORD_MOD = 65536
DAY_MOD = 251

# The order in which the withheld constants resolve.  The published control
# figures settle them in this order: each figure is separated from a wrong
# assignment by that figure alone once every figure above it has been settled.
CONSTANT_ORDER = ['rotate_step', 'shadow_bias', 'count_bias', 'island_offset',
                  'permute_rounds', 'stream_label', 'chain_seed', 'delta_span',
                  'drift_modulus', 'alias_rotor', 'window_span', 'quant_mode']

# The quantisation modes capacity_policy.md lists, in the order it lists them.
QUANT_MODES = ['floor', 'ceil', 'half', 'three_quarters']


class CorpusError(Exception):
    pass


# --------------------------------------------------------------------------
# reading files
# --------------------------------------------------------------------------

def read_text(path):
    with open(path, 'r', encoding='utf-8') as fh:
        return fh.read()


def read_table(path):
    """Read a CSV table; spaces around header names and cells are not part of them."""
    with open(path, 'r', encoding='utf-8', newline='') as fh:
        rows = list(csv.reader(fh))
    if not rows:
        return []
    header = [h.strip() for h in rows[0]]
    out = []
    for raw in rows[1:]:
        if not raw:
            continue
        row = {}
        for i, key in enumerate(header):
            row[key] = raw[i].strip() if i < len(raw) else ''
        out.append(row)
    return out


def parse_kv_list(text):
    """'commercial=320, public=260' -> {'commercial': 320, 'public': 260}"""
    out = {}
    for chunk in text.split(','):
        if '=' not in chunk:
            continue
        k, v = chunk.split('=', 1)
        out[k.strip()] = int(v.strip())
    return out


def parse_int_list(text):
    return [int(t) for t in re.findall(r'-?\d+', text)]


def parse_range(text):
    """'0 through 255' or '97, 101, 103' -> the declared candidate values."""
    text = text.strip()
    m = re.match(r'^(-?\d+)\s+through\s+(-?\d+)$', text)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        return list(range(lo, hi + 1))
    parts = [p.strip() for p in text.split(',') if p.strip()]
    if all(re.match(r'^-?\d+$', p) for p in parts):
        return [int(p) for p in parts]
    return parts


# --------------------------------------------------------------------------
# corpus and policy
# --------------------------------------------------------------------------

class Policy(object):
    """Constants the policy documents state in prose, parsed out of them."""

    def __init__(self, indir):
        self.encoding = read_text(os.path.join(indir, 'packet_encoding.md'))
        self.calibration = read_text(os.path.join(indir, 'calibration_slice.md'))
        self.dispatch = read_text(os.path.join(indir, 'dispatch_policy.md'))
        self.cost = read_text(os.path.join(indir, 'cost_policy.md'))
        self.capacity = read_text(os.path.join(indir, 'capacity_policy.md'))
        self._parse()

    def _line_value(self, text, key):
        m = re.search(r'^\s*[-*]?\s*%s\s*:\s*(.+?)\s*$' % re.escape(key), text,
                      re.MULTILINE | re.IGNORECASE)
        return m.group(1) if m else None

    def _parse(self):
        # --- transform flag table: bit -> (name, constant, declared range)
        self.flag_bits = {}
        for m in re.finditer(
                r'^\|\s*(0x[0-9A-Fa-f]+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*$',
                self.encoding, re.MULTILINE):
            bit = int(m.group(1), 16)
            if bit & RESERVED_BIT:
                continue
            self.flag_bits[bit] = {
                'name': m.group(2).strip(),
                'constant': m.group(3).strip(),
                'range': m.group(4).strip(),
            }
        self.bit_for_constant = {}
        for bit, info in self.flag_bits.items():
            self.bit_for_constant[info['constant']] = bit
        # --- HMAC key and block seed prefix
        m = re.search(r'over the key `([^`]+)`', self.encoding)
        if not m:
            raise CorpusError('packet encoding names no HMAC key')
        self.hmac_key = m.group(1).encode('utf-8')
        m = re.search(r'the ASCII text `([^`]+)`', self.encoding)
        self.block_seed_prefix = (m.group(1) if m else 'block|').encode('utf-8')
        # --- granularity list
        m = re.search(r'granularity\s+from\s+the\s+list\s+([0-9,\s]+?)\s+by\s+position',
                      self.encoding)
        if not m:
            raise CorpusError('packet encoding names no granularity list')
        self.granularity = parse_int_list(m.group(1))
        # --- incompatible process families
        val = self._line_value(self.dispatch, 'incompatible_families')
        if val is None:
            raise CorpusError('dispatch policy names no incompatible families')
        self.incompatible = set()
        for chunk in val.split(','):
            names = [t.strip() for t in chunk.split('|')]
            if len(names) == 2:
                self.incompatible.add(frozenset(names))
        # --- rebate bands
        val = self._line_value(self.cost, 'rebate_band')
        if val is None:
            raise CorpusError('cost policy names no rebate band')
        self.rebate_band = parse_kv_list(val)
        # --- congestion bounds, base ceilings, tier factors
        val = self._line_value(self.capacity, 'congestion_bounds')
        if val is None:
            raise CorpusError('capacity policy names no congestion bounds')
        self.congestion_bounds = parse_int_list(val)
        val = self._line_value(self.capacity, 'base_ceiling')
        if val is None:
            raise CorpusError('capacity policy names no base ceiling')
        self.base_ceiling = parse_kv_list(val)
        val = self._line_value(self.capacity, 'tier_factor')
        if val is None:
            raise CorpusError('capacity policy names no tier factor')
        self.tier_factor = {int(k): v for k, v in parse_kv_list(val).items()}
        # --- quantisation modes
        m = re.search(r'the\s+(\w+)\s+quantisation\s+modes', self.capacity,
                      re.IGNORECASE)
        count = WORD_NUM.get(m.group(1).lower()) if m else None
        if count is None or count != len(QUANT_MODES):
            raise CorpusError('capacity policy names an unexpected number of '
                              'quantisation modes')
        self.quant_mode_count = count
        # --- published control figures, in the order they are published
        self.controls = []
        for m in re.finditer(r'^-\s*(\w+)\s*=\s*(-?\d+)\s*$',
                             self.calibration, re.MULTILINE):
            self.controls.append((m.group(1), int(m.group(2))))
        if not self.controls:
            raise CorpusError('calibration slice publishes no control figures')
        if len(self.controls) != len(CONSTANT_ORDER):
            raise CorpusError('calibration slice publishes %d control figures '
                              'for %d withheld constants'
                              % (len(self.controls), len(CONSTANT_ORDER)))

    def complete(self, constants):
        """Fill the not yet resolved constants with neutral values.

        A control figure depends only on the constants resolved before it and
        on its own candidate, so the figures stay exact whatever the later
        constants hold.
        """
        out = dict(constants)
        for name in CONSTANT_ORDER:
            if name not in out:
                domain = self.domain(name)
                out[name] = domain[0] if domain else 0
        return out

    def domain(self, constant):
        """The declared candidate values of a withheld constant."""
        for info in self.flag_bits.values():
            if info['constant'].replace(' ', '_') == constant:
                return parse_range(info['range'])
        if constant == 'quant_mode':
            return list(range(self.quant_mode_count))
        raise CorpusError('no declared range for constant %s' % constant)

    def bit(self, constant):
        if constant == 'quant_mode':
            return None
        for info in self.flag_bits.values():
            if info['constant'].replace(' ', '_') == constant:
                return self.bit_for_constant[info['constant']]
        raise CorpusError('no transform bit for constant %s' % constant)


class Corpus(object):
    """The directories, the block manifest and the packet populations."""

    def __init__(self, indir):
        self.dir = indir
        self.clients = read_table(os.path.join(indir, 'client_directory.csv'))
        self.registry = read_table(os.path.join(indir, 'program_registry.csv'))
        self.lanes = read_table(os.path.join(indir, 'lane_roster.csv'))
        self.sites = read_table(os.path.join(indir, 'site_directory.csv'))
        self.manifest = read_table(os.path.join(indir, 'block_manifest.csv'))
        self._resolve_clients()
        self._resolve_registry()
        self._resolve_sites()
        self._load_populations()

    # ---- directories -----------------------------------------------------
    def _resolve_clients(self):
        self.clients_by_id = {c['client_id']: c for c in self.clients}
        if len(self.clients_by_id) != len(self.clients):
            raise CorpusError('client directory holds a repeated identifier')
        for c in self.clients:
            c['governing'] = self._governing_client(c)

    def _governing_client(self, row):
        """Follow the merge chain to its end; on a closed chain the identifier
        that sorts first among the identifiers on that closed chain governs."""
        seen = []
        ids_seen = set()
        cur = row
        while True:
            if cur['client_id'] in ids_seen:
                cycle = seen[seen.index(cur['client_id']):]
                return self.clients_by_id[min(cycle)]
            seen.append(cur['client_id'])
            ids_seen.add(cur['client_id'])
            target = cur['merged_into']
            if not target:
                return cur
            if target not in self.clients_by_id:
                raise CorpusError('client %s merges into unknown %s'
                                  % (cur['client_id'], target))
            cur = self.clients_by_id[target]

    def _resolve_registry(self):
        self.programs = sorted({r['program_id'] for r in self.registry})
        self.program_pos = {p: i for i, p in enumerate(self.programs)}
        for r in self.registry:
            r['revision_n'] = int(r['revision'])
            r['from_d'] = int(r['effective_from'])
            r['to_d'] = int(r['effective_to'])

    def _resolve_sites(self):
        self.site_by_name = {s['name']: s for s in self.sites}
        self.site_of_client = {}
        for c in self.clients:
            self.site_of_client[c['client_id']] = c['site']
        self.penalty_rate = {s['name']: int(s['penalty_rate_micros'])
                             for s in self.sites}
        self.site_capacity = {s['name']: int(s['capacity_slots'])
                              for s in self.sites}
        self.site_region = {s['name']: s['region'] for s in self.sites}

    # ---- populations -----------------------------------------------------
    def _payload_files(self):
        """CSV files carrying a payload_hex column."""
        out = []
        for name in sorted(os.listdir(self.dir)):
            if not name.endswith('.csv'):
                continue
            path = os.path.join(self.dir, name)
            with open(path, 'r', encoding='utf-8', newline='') as fh:
                first = fh.readline()
            cols = [c.strip() for c in first.strip().split(',')]
            if 'payload_hex' in cols and 'block_id' in cols:
                out.append((name, set(cols)))
        return out

    def _load_populations(self):
        pops = {}
        for row in self.manifest:
            pops.setdefault(row['population'], []).append(row)
        self.populations = {}
        files = self._payload_files()
        for pop, rows in pops.items():
            rows.sort(key=lambda r: int(r['block_id']))
            blocks = []
            payload = None
            for name, cols in files:
                if pop.lower() in name.lower() and 'payload_hex' in cols:
                    payload = read_table(os.path.join(self.dir, name))
                    break
            if payload is None:
                raise CorpusError('no payload table found for population %s' % pop)
            pay = {int(r['block_id']): r['payload_hex'] for r in payload}
            for row in rows:
                header = bytes.fromhex(row['header_hex'])
                if len(header) != 24:
                    raise CorpusError('block header of %s is %d bytes'
                                      % (row['block_id'], len(header)))
                if int.from_bytes(header[0:2], 'big') != 0x4C44:
                    raise CorpusError('block %s carries a bad magic word'
                                      % row['block_id'])
                if zlib.crc32(header[0:20]) != int.from_bytes(header[20:24], 'big'):
                    raise CorpusError('block %s fails its header checksum'
                                      % row['block_id'])
                bid = int.from_bytes(header[2:4], 'big')
                if bid != int(row['block_id']):
                    raise CorpusError('block header id disagrees with the manifest')
                payload_hex = pay.get(bid)
                if payload_hex is None:
                    raise CorpusError('no payload for block %d of %s' % (bid, pop))
                body = bytes.fromhex(payload_hex)
                if zlib.crc32(body) != int.from_bytes(header[16:20], 'big'):
                    raise CorpusError('block %d of %s fails its payload checksum'
                                      % (bid, pop))
                blocks.append({
                    'bid': bid,
                    'stored': int.from_bytes(header[4:6], 'big'),
                    'flags': int.from_bytes(header[6:8], 'big'),
                    'header': header,
                    'payload': body,
                })
            self.populations[pop] = blocks

    def classify_populations(self):
        """Split the populations into probe, calibration and field."""
        probe = []
        for pop, blocks in self.populations.items():
            if all(b['flags'] == 0 for b in blocks):
                probe.append(pop)
        rest = [p for p in self.populations if p not in probe]
        if len(rest) != 2:
            raise CorpusError('expected a calibration and a field population, '
                              'found %s' % (rest,))
        return probe, rest


# --------------------------------------------------------------------------
# wire decoding
# --------------------------------------------------------------------------

def xorshift64(state):
    state ^= (state << 13) & 0xFFFFFFFFFFFFFFFF
    state &= 0xFFFFFFFFFFFFFFFF
    state ^= state >> 7
    state ^= (state << 17) & 0xFFFFFFFFFFFFFFFF
    state &= 0xFFFFFFFFFFFFFFFF
    return state


class Wire(object):
    def __init__(self, corpus, policy):
        self.corpus = corpus
        self.policy = policy
        self.bits = {c: policy.bit(c) for c in CONSTANT_ORDER if c != 'quant_mode'}

    # ---- header helpers --------------------------------------------------
    def aux_words(self, block, constants):
        """The four auxiliary header words in their intended byte order."""
        island = constants['island_offset']
        out = []
        header = block['header']
        flags = block['flags']
        for j in range(4):
            off = 8 + 2 * j
            little = (flags & self.bits['island_offset']) and off == island
            out.append(int.from_bytes(header[off:off + 2],
                                       'little' if little else 'big'))
        return out

    def block_seed(self, block, constants):
        words = self.aux_words(block, constants)
        msg = (self.policy.block_seed_prefix
               + block['bid'].to_bytes(2, 'big')
               + b''.join(w.to_bytes(2, 'big') for w in words))
        digest = hmac.new(self.policy.hmac_key, msg, hashlib.sha256).digest()
        return int.from_bytes(digest[:8], 'big')

    def permutation(self, block, constants):
        """perm[p] is the logical ordinal of the record travelling at position p."""
        n = block['stored']
        perm = list(range(n))
        if not (block['flags'] & self.bits['permute_rounds']):
            return perm
        state = self.block_seed(block, constants)
        for _ in range(constants['permute_rounds']):
            for i in range(n - 1, 0, -1):
                state = xorshift64(state)
                j = state % (i + 1)
                perm[i], perm[j] = perm[j], perm[i]
        return perm

    def payload_at_origin(self, block, constants):
        body = block['payload']
        if not (block['flags'] & self.bits['rotate_step']):
            return body
        k = (block['bid'] * constants['rotate_step']) % len(body)
        if k == 0:
            return body
        return body[-k:] + body[:-k]

    def parse_records(self, block, constants):
        """Split the payload at its origin into records, in physical order."""
        body = self.payload_at_origin(block, constants)
        flags = block['flags']
        stored = block['stored']
        records = []
        off = 0
        for pos in range(stored):
            if off >= len(body):
                raise CorpusError('block %d payload ends early' % block['bid'])
            ctrl = body[off]
            length_code = ctrl >> 4
            if flags & self.bits['shadow_bias']:
                length_code ^= constants['shadow_bias']
            if length_code not in (0, 1):
                raise CorpusError('block %d record %d carries length code %d'
                                  % (block['bid'], pos, length_code))
            size = REC_EXT_LEN if length_code == 1 else REC_BASE_LEN
            raw = body[off:off + size]
            if len(raw) != size:
                raise CorpusError('block %d payload ends early' % block['bid'])
            records.append({
                'position': pos,
                'length_code': length_code,
                'dispatch_mode': ctrl & 0x0F,
                'alias_byte': raw[1],
                'programme_byte': raw[2],
                'load_raw': int.from_bytes(raw[3:7], 'big'),
                'due_raw': int.from_bytes(raw[7:9], 'big'),
                'weight_raw': int.from_bytes(raw[9:11], 'big'),
                'granularity_code': raw[11],
                'day_raw': raw[12],
                'extended_slack': (int.from_bytes(raw[13:15], 'big')
                                   if length_code == 1 else 0),
            })
            off += size
        if off != len(body):
            raise CorpusError('block %d payload holds %d bytes beyond its records'
                              % (block['bid'], len(body) - off))
        return records

    # ---- population decoding --------------------------------------------
    def decode(self, pop, constants):
        """Decode one population into records carrying logical values.

        Returns a list of record dicts, in block order then logical ordinal
        order, each with 'genuine' set once filler has been discarded.
        """
        corpus = self.corpus
        policy = self.policy
        nclients = len(corpus.clients)
        nprograms = len(corpus.programs)
        granularity = policy.granularity
        if len(granularity) < 1:
            raise CorpusError('granularity list is empty')
        out = []
        running_load = 0
        for block in self.populations_blocks(pop):
            flags = block['flags']
            records = self.parse_records(block, constants)
            stored = block['stored']
            genuine_count = stored
            if flags & self.bits['count_bias']:
                genuine_count = stored - constants['count_bias']
                if genuine_count < 0:
                    raise CorpusError('block %d holds more filler than records'
                                      % block['bid'])
            perm = self.permutation(block, constants)
            if len(perm) != stored:
                raise CorpusError('block %d permutation covers %d of %d records'
                                  % (block['bid'], len(perm), stored))
            logical = [None] * stored
            for pos in range(stored):
                logical[perm[pos]] = records[pos]
            # dispatch weights: second order differences in groups
            weights = {}
            if flags & self.bits['delta_span']:
                span = constants['delta_span']
                start = 0
                while start < stored:
                    end = min(start + span, stored)
                    vals = []
                    for t, o in enumerate(range(start, end)):
                        raw = logical[o]['weight_raw']
                        if t == 0:
                            vals.append(raw % WORD_MOD)
                        elif t == 1:
                            vals.append((raw + vals[0]) % WORD_MOD)
                        else:
                            vals.append((raw + 2 * vals[t - 1] - vals[t - 2]) % WORD_MOD)
                    for t, o in enumerate(range(start, end)):
                        weights[o] = vals[t]
                    start += span
            # due offsets: folded on the record one logical ordinal earlier
            dues = {}
            if flags & self.bits['chain_seed']:
                previous = constants['chain_seed'] % WORD_MOD
                for o in range(stored):
                    dues[o] = (logical[o]['due_raw'] - previous) % WORD_MOD
                    previous = dues[o]
            # programme selection, with backward references
            programmes = {}
            for o in range(stored):
                byte = logical[o]['programme_byte']
                if (flags & self.bits['window_span']) and byte >= 0xF0:
                    back = ((byte - 0xF0) % constants['window_span']) + 1
                    programmes[o] = programmes[o - back] if o - back >= 0 else None
                else:
                    programmes[o] = corpus.programs[byte % nprograms]
            aux = self.aux_words(block, constants)
            horizon = aux[1]
            for o in range(stored):
                rec = logical[o]
                genuine = o < genuine_count
                flags_live = flags
                load = rec['load_raw']
                if flags_live & self.bits['stream_label']:
                    mask = hmac.new(
                        policy.hmac_key,
                        constants['stream_label'].encode('utf-8') + b'|'
                        + block['bid'].to_bytes(2, 'big')
                        + o.to_bytes(2, 'big'),
                        hashlib.sha256).digest()[:4]
                    load ^= int.from_bytes(mask, 'big')
                position = rec['alias_byte']
                if flags_live & self.bits['alias_rotor']:
                    position = (position - constants['alias_rotor']) % nclients
                else:
                    position = position % nclients
                client = corpus.clients[position]['governing']
                day = rec['day_raw']
                if flags_live & self.bits['drift_modulus']:
                    modulus = constants['drift_modulus']
                    factor = 1 + (running_load % (modulus - 1))
                    day = (rec['day_raw'] * pow(factor, -1, DAY_MOD)) % DAY_MOD
                out.append({
                    'block': block['bid'],
                    'ordinal': o,
                    'genuine': genuine,
                    'order_id': 'W%04d%02d' % (block['bid'], o),
                    'dispatch_mode': rec['dispatch_mode'],
                    'granularity': granularity[rec['granularity_code'] % len(granularity)],
                    'load': load,
                    'due_offset': dues.get(o, rec['due_raw']),
                    'extended_slack': rec['extended_slack'],
                    'weight': weights.get(o, rec['weight_raw']),
                    'submission_day': day,
                    'horizon': horizon,
                    'client': client,
                    'programme': programmes[o],
                    'length_code': rec['length_code'],
                })
                if genuine:
                    running_load += load
        return out

    def populations_blocks(self, pop):
        return self.corpus.populations[pop]


# --------------------------------------------------------------------------
# control figures
# --------------------------------------------------------------------------

def governing_revision(corpus, programme, day):
    """The revision of a programme that governs a submission day, if any."""
    best = None
    for row in corpus.registry:
        if row['program_id'] != programme:
            continue
        if row['from_d'] <= day < row['to_d']:
            if best is None or row['revision_n'] > best['revision_n']:
                best = row
    return best


def client_able_to_hold(client, day):
    """A client holds work on or after its retirement day never, and before
    its first active day it is unable to accept work."""
    retired = client['retired_on']
    if retired and day >= int(retired):
        return False
    if day < int(client['effective_from']):
        return False
    return True


def numeric_part(identifier):
    digits = ''.join(ch for ch in identifier if ch.isdigit())
    return int(digits) if digits else 0


def quantise(load, granularity, mode):
    if granularity <= 0:
        return load
    whole, remainder = divmod(load, granularity)
    if mode == 0:
        return whole * granularity
    if mode == 1:
        return (whole + 1) * granularity if remainder else whole * granularity
    if mode == 2:
        return (whole + 1) * granularity if 2 * remainder >= granularity else whole * granularity
    return (whole + 1) * granularity if 4 * remainder >= 3 * granularity else whole * granularity


def control_figure(name, wire, population, constants):
    """Compute one published control figure for a population.

    The figures that need no record parse are computed straight from the
    blocks, so they stay exact before the constants that shape the records
    have been settled.
    """
    if name == 'payload_origin_total':
        total = 0
        for block in wire.populations_blocks(population):
            total += int.from_bytes(wire.payload_at_origin(block, constants)[0:4], 'big')
        return total
    if name == 'island_field_total':
        total = 0
        for block in wire.populations_blocks(population):
            total += sum(wire.aux_words(block, constants))
        return total
    if name == 'ordinal_position_checksum':
        total = 0
        for block in wire.populations_blocks(population):
            perm = wire.permutation(block, constants)
            for pos in range(len(perm)):
                total += (1 + pos) * (1 + perm[pos])
        return total
    if name not in ('record_span_total', 'calibration_order_total'):
        records = wire.decode(population, constants)
    else:
        records = None
    if name == 'record_span_total':
        total = 0
        for block in wire.populations_blocks(population):
            for rec in wire.parse_records(block, constants):
                if rec['length_code'] == 1:
                    total += 1
        return total
    if name == 'calibration_order_total':
        total = 0
        for block in wire.populations_blocks(population):
            stored = block['stored']
            if block['flags'] & wire.bits['count_bias']:
                stored -= constants['count_bias']
            total += stored
        return total
    if name == 'masked_load_total':
        return sum(r['load'] for r in records if r['genuine'])
    if name == 'folded_slack_total':
        return sum(r['due_offset'] for r in records if r['genuine'])
    if name == 'delta_weight_total':
        return sum(r['weight'] for r in records if r['genuine'])
    if name == 'drift_day_total':
        return sum(r['submission_day'] * (1 + r['ordinal'])
                   for r in records if r['genuine'])
    if name == 'canonical_client_total':
        return sum(numeric_part(r['client']['client_id']) * (1 + r['ordinal'])
                   for r in records if r['genuine'])
    if name == 'backref_program_total':
        total = 0
        for r in records:
            if not r['genuine']:
                continue
            if r['programme'] is None or r['programme'] not in wire.corpus.program_pos:
                raise CorpusError('record %s carries no selectable programme'
                                  % r['order_id'])
            total += wire.corpus.program_pos[r['programme']] * (1 + r['ordinal'])
        return total
    if name == 'billable_slot_total':
        total = 0
        for r in records:
            if not r['genuine']:
                continue
            if not client_able_to_hold(r['client'], r['submission_day']):
                continue
            revision = governing_revision(wire.corpus, r['programme'],
                                          r['submission_day'])
            if revision is None:
                continue
            total += quantise(r['load'], r['granularity'], constants['quant_mode'])
        return total
    raise CorpusError('unknown control figure %s' % name)


# --------------------------------------------------------------------------
# constant resolution
# --------------------------------------------------------------------------

def resolve_constants(policy, wire, calibration_pop, controls):
    """Settle every withheld constant against the calibration population.

    Returns (constants, candidate_space, calibration_comparison).
    """
    constants = {}
    candidate_space = []
    examined = 0
    rejected = 0
    for constant, (control_name, published) in zip(CONSTANT_ORDER, controls):
        domain = policy.domain(constant)
        verdicts = []
        accepted = None
        for value in domain:
            trial = policy.complete(constants)
            trial[constant] = value
            try:
                reproduced = control_figure(control_name, wire, calibration_pop, trial)
            except CorpusError:
                reproduced = None
            ok = (reproduced == published)
            verdicts.append({'value': value, 'verdict': 'accepted' if ok else 'rejected'})
            examined += 1
            if ok:
                if accepted is not None:
                    raise CorpusError('control %s accepts both %r and %r for %s'
                                      % (control_name, accepted, value, constant))
                accepted = value
            else:
                rejected += 1
        if accepted is None:
            raise CorpusError('no candidate for %s reproduces %s'
                              % (constant, control_name))
        constants[constant] = accepted
        candidate_space.append({
            'parameter': constant,
            'control': control_name,
            'domain_size': len(domain),
            'resolved': accepted,
            'rejected': len(domain) - 1,
            'verdicts': verdicts,
        })
    comparison = []
    for control_name, published in controls:
        reproduced = control_figure(control_name, wire, calibration_pop, constants)
        comparison.append({'control': control_name,
                           'published': published,
                           'reproduced': reproduced})
    return constants, candidate_space, comparison, examined, rejected


# --------------------------------------------------------------------------
# settlement
# --------------------------------------------------------------------------

class _SearchExhausted(Exception):
    """Raised when the pruned search reaches its node budget."""
    pass


class SitePlacer(object):
    """Exact minimum lane cost placement for the admitted orders of one site.

    The settled schedule is the placement whose total of billable slots
    multiplied by lane rate, summed over every admitted order at the site, is
    smallest.  Where two admitted orders contend for the last slots of the
    cheapest lane both are eligible for, the order carrying the larger
    remaining slack keeps the lane, and where the slack is equal the larger
    billable slot count keeps it, and where that is equal too the identifier
    that sorts first keeps it.  The orders are therefore offered the lanes they
    are eligible for in ascending order of rate in the order that contention
    rule ranks them, and the first whole placement at the smallest cost that
    the offering meets is the placement the schedule holds.

    An order that carries no billable slots costs nothing on any lane and
    frees no capacity, so it takes no part in settling the smallest cost: it
    only needs the cheapest lane that still leaves that cost within reach.
    """

    NODE_BUDGET = 300000

    def __init__(self, lanes, incompatible):
        # lanes: list of dict(lane_id, cap (None = unlimited), rate, class_lock,
        #                     exclusive_client, relief)
        # incompatible: set of frozenset family name pairs that may not share a lane
        self.lanes = lanes
        self.nl = len(lanes)
        self.incompatible = incompatible
        self.penalty = max(L['rate'] for L in lanes)
        self.laneorder = sorted(range(self.nl),
                                 key=lambda li: (lanes[li]['rate'], lanes[li]['lane_id']))
        self.leaves = 0

    def eligible(self, item, li):
        lane = self.lanes[li]
        if lane['class_lock'] and lane['class_lock'] != item['service_class']:
            return False
        if lane['exclusive_client'] and lane['exclusive_client'] != item['client_id']:
            return False
        return True

    def _bad_pairs(self, famcodes):
        bad = set()
        for pair in self.incompatible:
            a, b = tuple(pair)
            if a in famcodes and b in famcodes:
                bad.add(frozenset((famcodes[a], famcodes[b])))
        return bad

    def _prep(self, items, famcodes):
        """Tables the search needs: eligibility, suffix sums, family bad pairs."""
        n = len(items)
        eligible = []
        for item in items:
            eligible.append([li for li in self.laneorder if self.eligible(item, li)])
        cheap = []
        for e in eligible:
            if not e:
                return None
            cheap.append(min(self.lanes[li]['rate'] for li in e))
        suffix = [0] * (n + 1)
        for i in range(n - 1, -1, -1):
            suffix[i] = suffix[i + 1] + items[i]['size'] * cheap[i]
        per_lane = [[0] * (n + 1) for _ in range(self.nl)]
        for li in range(self.nl):
            row = per_lane[li]
            for i in range(n - 1, -1, -1):
                row[i] = row[i + 1] + (items[i]['size'] if li in eligible[i] else 0)
        relief_total = [0] * (n + 1)
        penalty = self.penalty
        for i in range(n - 1, -1, -1):
            relief_total[i] = relief_total[i + 1] + items[i]['size'] * penalty
        return eligible, cheap, suffix, per_lane, relief_total

    def _fam_ok(self, bad, famm, li, famcode):
        mask = famm[li]
        while mask:
            present = (mask & -mask).bit_length() - 1
            if frozenset((present, famcode)) in bad:
                return False
            mask &= mask - 1
        return True

    def _lower(self, i, caps, tables):
        """A lower bound on the cost of placing items i and later.

        The first bound prices every remaining item at the cheapest rate of any
        lane it may rest on.  The second fills the lanes with the largest gains
        first, each capped by its room and by the size eligible for it, and
        takes the relief cost less that saving.
        """
        eligible, cheap, suffix, per_lane, relief_total = tables
        bound = suffix[i]
        remaining = relief_total[i] // self.penalty
        saved = 0
        for li in self.laneorder:
            lane = self.lanes[li]
            gain = self.penalty - lane['rate']
            if gain <= 0:
                continue
            room = per_lane[li][i] if lane['cap'] is None else min(lane['cap'] - caps[li],
                                                                  per_lane[li][i])
            if room <= 0:
                continue
            take = room if room < remaining else remaining
            saved += take * gain
            remaining -= take
            if remaining <= 0:
                break
        other = relief_total[i] - saved
        return bound if bound > other else other

    def _ordered(self, items):
        """Largest first: the search fills the lanes early and prunes hard."""
        return sorted(items, key=lambda it: (-it['size'], it['order_id']))

    def _greedy(self, items, famcodes):
        """Cheapest-feasible-lane seed for the search: an upper bound."""
        bad = self._bad_pairs(famcodes)
        caps = [0] * self.nl
        famm = [0] * self.nl
        cost = 0
        for item in items:
            for li in self.laneorder:
                if not self.eligible(item, li):
                    continue
                lane = self.lanes[li]
                if lane['cap'] is not None and caps[li] + item['size'] > lane['cap']:
                    continue
                if item['famcode'] is not None and not lane['relief'] and \
                        not self._fam_ok(bad, famm, li, item['famcode']):
                    continue
                caps[li] += item['size']
                if item['famcode'] is not None:
                    famm[li] |= 1 << item['famcode']
                cost += item['size'] * lane['rate']
                break
            else:
                return None
        return cost

    def min_cost(self, items, famcodes=None, caps=None, fammask=None):
        """The exact minimum total lane cost of placing every item.

        A pruned search settles it when it settles fast; a search that meets
        the node budget turns into a table over the states it reaches, which
        holds the same answer and cannot be made to miss one.
        """
        search = [it for it in items if it['size'] > 0]
        if not search:
            return 0
        search = self._ordered(search)
        tables = self._prep(search, famcodes)
        if tables is None:
            return float('inf')
        bad = self._bad_pairs(famcodes)
        eligible = tables[0]
        lanes = self.lanes
        n = len(search)
        caps0 = list(caps) if caps is not None else [0] * self.nl
        famm0 = list(fammask) if fammask is not None else [0] * self.nl
        total = sum(it['size'] for it in search)
        base = self._lower(0, caps0, tables)

        best = [float('inf')]
        for candidate in (search, sorted(search, key=lambda it: it['order_id'])):
            cost = self._greedy(candidate, famcodes)
            if cost is not None and cost < best[0]:
                best[0] = cost
        if best[0] <= base:
            return best[0]

        budget = [self.NODE_BUDGET]

        def dfs(i, caps, famm, cost, remaining):
            if i == n:
                self.leaves += 1
                if cost < best[0]:
                    best[0] = cost
                return
            if cost + self._lower(i, caps, tables) >= best[0]:
                return
            budget[0] -= 1
            if budget[0] < 0:
                raise _SearchExhausted()
            item = search[i]
            famcode = item['famcode']
            size = item['size']
            for li in eligible[i]:
                lane = lanes[li]
                if lane['cap'] is not None and caps[li] + size > lane['cap']:
                    continue
                if famcode is not None and not lane['relief'] and \
                        not self._fam_ok(bad, famm, li, famcode):
                    continue
                ncaps = list(caps)
                ncaps[li] += size
                nfamm = list(famm)
                if famcode is not None:
                    nfamm[li] |= 1 << famcode
                dfs(i + 1, ncaps, nfamm, cost + size * lane['rate'], remaining - size)

        try:
            dfs(0, caps0, famm0, 0, total)
            return best[0]
        except _SearchExhausted:
            return self._table_min(search, tables, bad, famcodes, caps0, famm0)

    def _table_min(self, search, tables, bad, famcodes, caps0, famm0):
        """The same smallest cost, held in a table over the states reached."""
        eligible = tables[0]
        lanes = self.lanes
        n = len(search)
        table = {}

        def value(i, caps, famm):
            if i == n:
                return 0
            key = (i, caps, famm)
            got = table.get(key)
            if got is not None:
                return got
            item = search[i]
            famcode = item['famcode']
            size = item['size']
            best = None
            for li in eligible[i]:
                lane = lanes[li]
                if lane['cap'] is not None and caps[li] + size > lane['cap']:
                    continue
                if famcode is not None and not lane['relief'] and \
                        not self._fam_ok(bad, famm, li, famcode):
                    continue
                ncaps = list(caps)
                ncaps[li] += size
                nfamm = list(famm)
                if famcode is not None:
                    nfamm[li] |= 1 << famcode
                sub = value(i + 1, tuple(ncaps), tuple(nfamm))
                if sub == float('inf'):
                    continue
                total = size * lane['rate'] + sub
                if best is None or total < best:
                    best = total
            if best is None:
                best = float('inf')
            table[key] = best
            return best

        return value(0, tuple(caps0), tuple(famm0))

    def place(self, items, famcodes):
        """Canonical minimum cost placement.

        items need keys: size, famcode, service_class, client_id, slack, order_id.
        Returns (cost, {order_id: lane index}, leaves).
        """
        if not items:
            return 0, {}, 0
        priority = sorted(items, key=lambda it: (-it['slack'], -it['size'],
                                                it['order_id']))
        # the smallest cost is settled by the orders that carry slots alone;
        # every order, free or not, is then offered the lanes in the order the
        # contention rule ranks them, and the first placement that meets that
        # smallest cost is the one the schedule holds
        optimum = self.min_cost(priority, famcodes=famcodes)
        queue = list(priority)
        bad = self._bad_pairs(famcodes)
        tables = self._prep(queue, famcodes)
        caps = [0] * self.nl
        famm = [0] * self.nl
        assign = {}

        def descent(k, caps, famm, cost):
            if k == len(queue):
                self.leaves += 1
                return {}
            if tables is not None and cost + self._lower(k, caps, tables) > optimum:
                return None
            item = queue[k]
            famcode = item['famcode']
            size = item['size']
            for li in self.laneorder:
                if not self.eligible(item, li):
                    continue
                lane = self.lanes[li]
                if lane['cap'] is not None and caps[li] + size > lane['cap']:
                    continue
                if famcode is not None and not lane['relief'] and \
                        not self._fam_ok(bad, famm, li, famcode):
                    continue
                step = size * lane['rate']
                if cost + step > optimum:
                    continue
                ncaps = list(caps)
                ncaps[li] += size
                nfamm = list(famm)
                if famcode is not None:
                    nfamm[li] |= 1 << famcode
                tail = descent(k + 1, ncaps, nfamm, cost + step)
                if tail is not None:
                    tail[item['order_id']] = li
                    return tail
            return None

        if queue:
            result = descent(0, caps, famm, 0)
            if result is None:
                raise CorpusError('no minimum cost placement holds every order')
            assign.update(result)
        return optimum, assign, self.leaves


def settle_admission(corpus, policy, orders):
    """Offer the whole admission order at the standing tiers until stable.

    A pass offers every order at the tiers standing when the offering begins;
    the first pass is offered with every site at tier zero, and the settlement
    is complete on the first pass that leaves every tier where it found it,
    that confirming pass counted along with the passes that moved a tier.

    Returns (admitted orders, passes, congestion index, congestion tier).
    """
    sites = [s['name'] for s in corpus.sites]
    capacity = corpus.site_capacity
    bounds = sorted(policy.congestion_bounds)
    n_tiers = len(bounds) + 1

    def ceiling_of(tiers):
        ceiling = {}
        for client in corpus.clients:
            base = policy.base_ceiling.get(client['service_class'])
            factor = policy.tier_factor.get(tiers[client['site']])
            if base is None or factor is None:
                raise CorpusError('no admission ceiling for service class %s at '
                                  'tier %s' % (client['service_class'],
                                               tiers[client['site']]))
            ceiling[client['client_id']] = (base * factor) // 100
        return ceiling

    def tier_of(index):
        tier = n_tiers - 1
        for i, bound in enumerate(bounds):
            if index < bound:
                tier = i
                break
        return tier

    def offer(tiers):
        ceiling = ceiling_of(tiers)
        running = {}
        admitted = []
        for order in orders:
            key = order['client']['client_id']
            if running.get(key, 0) + order['slots'] <= ceiling[key]:
                running[key] = running.get(key, 0) + order['slots']
                admitted.append(order)
        slots = {s: 0 for s in sites}
        for order in admitted:
            slots[order['client']['site']] += order['slots']
        index = {s: (1000 * slots[s]) // capacity[s] for s in sites}
        new_tiers = {s: tier_of(index[s]) for s in sites}
        return admitted, index, new_tiers

    tiers = {s: 0 for s in sites}
    passes = 0
    seen = set()
    limit = (n_tiers ** len(sites)) + 2
    while True:
        passes += 1
        admitted, index, new_tiers = offer(tiers)
        if new_tiers == tiers:
            return admitted, passes, index, tiers
        if passes > limit:
            break
        key = tuple(sorted(new_tiers.items()))
        if key in seen:
            break
        seen.add(key)
        tiers = new_tiers

    # the documented offering never settled: fall back on the stable
    # congestion assignment the policy says is unique
    stable = [dict(zip(sites, combo))
              for combo in itertools.product(range(n_tiers), repeat=len(sites))
              if offer(dict(zip(sites, combo)))[2] == dict(zip(sites, combo))]
    if len(stable) != 1:
        raise CorpusError('the admission tiers never settle and %d congestion '
                          'assignments are stable' % len(stable))
    tiers = stable[0]
    passes = 0
    seen = set()
    while True:
        passes += 1
        admitted, index, new_tiers = offer(tiers)
        if new_tiers == tiers:
            return admitted, passes, index, tiers
        key = tuple(sorted(new_tiers.items()))
        if key in seen:
            raise CorpusError('the stable congestion assignment never confirms')
        seen.add(key)
        tiers = new_tiers


def build_site_lanes(corpus, site):
    """The lanes of one site, with the relief lane recognised."""
    penalty = corpus.penalty_rate[site]
    out = []
    for row in corpus.lanes:
        if row['site'] != site:
            continue
        cap = int(row['slot_capacity'])
        lock = row['class_lock']
        exclusive = row['exclusive_client']
        relief = cap == 0 and not lock and not exclusive
        rate = penalty if relief else int(row['rate_micros'])
        out.append({
            'lane_id': row['lane_id'],
            'cap': None if relief else cap,
            'rate': rate,
            'class_lock': lock,
            'exclusive_client': exclusive,
            'relief': relief,
        })
    if not out:
        raise CorpusError('lane roster holds no lane for site %s' % site)
    return out


def settle_population(corpus, policy, wire, population, constants):
    """Decode, score, admit, place and settle one population."""
    records = wire.decode(population, constants)
    genuine = [r for r in records if r['genuine']]
    quant_mode = constants['quant_mode']
    for r in genuine:
        r['due_slot'] = r['horizon'] + r['due_offset'] + r['extended_slack']
        r['slots'] = quantise(r['load'], r['granularity'], quant_mode)
        r['slack'] = r['due_slot'] - r['submission_day']
        # the client is resolved to its governing form before any governing
        # programme revision is selected
        client = r['client']
        day = r['submission_day']
        retired = client['retired_on']
        if retired and day >= int(retired):
            r['status'] = 'rejected'
        elif day < int(client['effective_from']):
            r['status'] = 'deferred'
        else:
            revision = (governing_revision(corpus, r['programme'], day)
                        if r['programme'] is not None else None)
            if revision is None:
                r['status'] = 'rejected'
            else:
                r['status'] = 'scored'
                r['revision'] = revision
    scored = [r for r in genuine if r['status'] == 'scored']
    # work is offered in descending dispatch weight, ties by ascending identifier
    scored.sort(key=lambda r: (-r['weight'], r['order_id']))
    admitted, passes, congestion, tiers = settle_admission(corpus, policy, scored)
    held = {r['order_id'] for r in scored} - {r['order_id'] for r in admitted}
    # families
    famcodes = {}
    for row in corpus.registry:
        if row['family'] not in famcodes:
            famcodes[row['family']] = len(famcodes)
    # placement, one site at a time
    placement = {}
    site_cost = {}
    leaves = 0
    displaced = 0
    sites = [s['name'] for s in corpus.sites]
    for site in sites:
        lanes = build_site_lanes(corpus, site)
        items = []
        for order in admitted:
            if order['client']['site'] != site:
                continue
            revision = order['revision']
            items.append({
                'order_id': order['order_id'],
                'size': order['slots'],
                'family': revision['family'],
                'famcode': famcodes.get(revision['family']),
                'service_class': order['client']['service_class'],
                'client_id': order['client']['client_id'],
                'slack': order['slack'],
            })
        placer = SitePlacer(lanes, policy.incompatible)
        cost, assign, examined = placer.place(items, famcodes)
        for order_id, li in assign.items():
            placement[order_id] = lanes[li]['lane_id']
            if lanes[li]['relief']:
                displaced += 1
        site_cost[site] = cost
        leaves += examined
    # money
    lane_by_id = {}
    for site in sites:
        for lane in build_site_lanes(corpus, site):
            lane_by_id[lane['lane_id']] = lane
    rebate_band = policy.rebate_band
    placed = []
    for order in admitted:
        lane_id = placement[order['order_id']]
        lane = lane_by_id[lane_id]
        order['placement'] = lane_id
        charge = order['slots'] * lane['rate']
        band = rebate_band.get(str(order['dispatch_mode']))
        if band is None:
            raise CorpusError('rebate band names no rebate for dispatch mode %d'
                              % order['dispatch_mode'])
        rebate = min(order['slots'] * band, charge)
        order['lane'] = lane
        order['charge'] = charge
        order['rebate'] = rebate
        order['net'] = charge - rebate
        placed.append(order)
    # budget ceilings accumulate in ascending order of identifier
    running = {}
    for order in sorted(placed, key=lambda o: o['order_id']):
        client = order['client']
        key = client['client_id']
        ceiling = int(client['budget_cap_micros'])
        total = running.get(key, 0) + order['net']
        if total > ceiling:
            capped = total - ceiling
            running[key] = ceiling
        else:
            capped = 0
            running[key] = total
        order['capped'] = capped
    return {
        'records': records,
        'genuine': genuine,
        'scored': scored,
        'admitted': admitted,
        'held': held,
        'placed': placed,
        'placement': placement,
        'passes': passes,
        'congestion': congestion,
        'tiers': tiers,
        'site_cost': site_cost,
        'leaves': leaves,
        'displaced': displaced,
        'famcodes': famcodes,
    }


# --------------------------------------------------------------------------
# reports
# --------------------------------------------------------------------------

def order_row(order):
    return {
        'billable_slots': order['slots'],
        'capped_micros': order['capped'],
        'charge_micros': order['charge'],
        'client_id': order['client']['client_id'],
        'lane_id': order['placement'],
        'net_micros': order['net'],
        'order_id': order['order_id'],
        'program_id': order['programme'],
        'rebate_micros': order['rebate'],
        'revision': order['revision']['revision_n'],
        'slack': order['slack'],
    }


def totals_of(rows):
    return {
        'billable_slots': sum(r['billable_slots'] for r in rows),
        'capped_micros': sum(r['capped_micros'] for r in rows),
        'charge_micros': sum(r['charge_micros'] for r in rows),
        'net_micros': sum(r['net_micros'] for r in rows),
        'rebate_micros': sum(r['rebate_micros'] for r in rows),
    }


def region_key(region):
    return region[:1].upper() + region[1:] if region else region


def write_json(path, obj):
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(obj, fh, indent=2, sort_keys=True)
        fh.write('\n')


def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: %s <input-directory> <output-directory>\n'
                         % os.path.basename(argv[0]))
        return 2
    indir, outdir = argv[1], argv[2]
    if not os.path.isdir(indir):
        sys.stderr.write('not a directory: %s\n' % indir)
        return 2
    os.makedirs(outdir, exist_ok=True)

    policy = Policy(indir)
    corpus = Corpus(indir)
    probe, rest = corpus.classify_populations()

    # ---- settle every withheld constant against the calibration population
    wire = Wire(corpus, policy)
    resolution = None
    calibration_pop = None
    for pop in rest:
        try:
            result = resolve_constants(policy, wire, pop, policy.controls)
        except CorpusError:
            continue
        if resolution is not None:
            raise CorpusError('more than one population reproduces the '
                              'published control figures')
        resolution = result
        calibration_pop = pop
    if resolution is None:
        raise CorpusError('no population reproduces the published control figures')
    constants, candidate_space, comparison, examined, rejected = resolution
    field_pop = [p for p in rest if p != calibration_pop]
    if len(field_pop) != 1:
        raise CorpusError('no single field population remains')
    field_pop = field_pop[0]

    # ---- complete derivation from scratch with the settled constants
    field = settle_population(corpus, policy, wire, field_pop, constants)
    calibration = settle_population(corpus, policy, wire, calibration_pop, constants)

    # ---- rollups
    sites = [s['name'] for s in corpus.sites]
    region_of_site = corpus.site_region
    rows = {o['order_id']: order_row(o) for o in field['placed']}
    for order in field['placed']:
        order['row'] = rows[order['order_id']]
    by_region = {}
    by_segment = {}
    for order in field['placed']:
        site = order['client']['site']
        region = region_of_site[site]
        segment = order['client']['service_class']
        by_region.setdefault(region, []).append(order)
        by_segment.setdefault(segment, []).append(order)
    regions = []
    for site in sites:
        region = region_of_site[site]
        if region not in regions:
            regions.append(region)
    region_rollups = {}
    for region in regions:
        members = sorted(by_region.get(region, []), key=lambda o: o['order_id'])
        orows = [o['row'] for o in members]
        region_rollups[region] = {
            'order_count': len(members),
            'orders': orows,
            'region': region_key(region),
            'totals': totals_of(orows),
        }
    segments = []
    for order in field['placed']:
        seg = order['client']['service_class']
        if seg not in segments:
            segments.append(seg)
    segment_rollups = {}
    for seg in segments:
        members = sorted(by_segment.get(seg, []), key=lambda o: o['order_id'])
        orows = [o['row'] for o in members]
        segment_rollups[seg] = {
            'order_count': len(members),
            'orders': orows,
            'service_class': seg,
            'totals': totals_of(orows),
        }

    # ---- summary
    placed = field['placed']
    lanes_used = len({o['placement'] for o in placed})
    summary = {
        'order_rows': len(field['genuine']),
        'decoded_rows': len(field['records']),
        'orders_scored': len(field['scored']),
        'orders_placed': len(placed),
        'orders_deferred': sum(1 for r in field['genuine'] if r['status'] == 'deferred')
                           + len(field['held']),
        'orders_rejected': sum(1 for r in field['genuine'] if r['status'] == 'rejected'),
        'billable_slots_total': sum(o['slots'] for o in placed),
        'charge_micros_total': sum(o['charge'] for o in placed),
        'rebate_micros_total': sum(o['rebate'] for o in placed),
        'capped_micros_total': sum(o['capped'] for o in placed),
        'net_micros_total': sum(o['net'] for o in placed),
        'lanes_used': lanes_used,
    }

    # ---- reconciliation
    region_net = {}
    for region in regions:
        region_net[region_key(region)] = region_rollups[region]['totals']['net_micros']
    segment_net = {}
    for seg in segments:
        segment_net[seg] = segment_rollups[seg]['totals']['net_micros']
    conservation_residual = summary['net_micros_total'] - sum(region_net.values())
    segment_residual = summary['net_micros_total'] - sum(segment_net.values())
    region_ids = []
    for region in regions:
        region_ids.extend(o['order_id'] for o in region_rollups[region]['orders'])
    segment_ids = []
    for seg in segments:
        segment_ids.extend(o['order_id'] for o in segment_rollups[seg]['orders'])
    placed_ids = [o['order_id'] for o in placed]
    region_closed = (len(region_ids) == len(set(region_ids))
                     and sorted(region_ids) == sorted(placed_ids))
    segment_closed = (len(segment_ids) == len(set(segment_ids))
                      and sorted(segment_ids) == sorted(placed_ids))
    identity_unique = len(set(placed_ids)) == len(placed_ids)
    capacity_ok = True
    for order in placed:
        lane = order['lane']
        if lane['cap'] is not None and order['slots'] > lane['cap']:
            capacity_ok = False
    load = {}
    for order in placed:
        lane_id = order['placement']
        lane = order['lane']
        if lane['cap'] is not None:
            load[lane_id] = load.get(lane_id, 0) + order['slots']
    for order in placed:
        lane = order['lane']
        if lane['cap'] is not None and load.get(order['placement'], 0) > lane['cap']:
            capacity_ok = False
    data_quality = {
        'order_rows': summary['order_rows'],
        'decoded_rows': summary['decoded_rows'],
        'rejected_orders': sorted(r['order_id'] for r in field['genuine']
                                  if r['status'] == 'rejected'),
        'deferred_orders': sorted(
            [r['order_id'] for r in field['genuine'] if r['status'] == 'deferred']
            + sorted(field['held'])),
        'region_net_micros': region_net,
        'segment_net_micros': segment_net,
        'conservation_residual_micros': conservation_residual,
        'segment_residual_micros': segment_residual,
        'calibration_net_micros': sum(o['net'] for o in calibration['placed']),
        'invariants': {
            'region_partition_closed': bool(region_closed),
            'segment_partition_closed': bool(segment_closed),
            'order_identity_unique': bool(identity_unique),
            'capacity_respected': bool(capacity_ok),
        },
    }

    # ---- derivation record
    fixpoint = {
        'passes': field['passes'],
        'congestion_index': {s: field['congestion'][s] for s in sites},
        'congestion_tier': {s: field['tiers'][s] for s in sites},
    }
    assignment_search = {
        'sites_searched': len(sites),
        'feasible_leaves': field['leaves'],
        'displaced_orders': field['displaced'],
        'site_cost_micros': {s: field['site_cost'][s] for s in sites},
    }
    audit = {
        'candidate_space': candidate_space,
        'resolved_parameters': {c: constants[c] for c in CONSTANT_ORDER},
        'calibration_comparison': comparison,
        'fixpoint': fixpoint,
        'assignment_search': assignment_search,
        'candidates_examined': examined,
        'candidates_rejected': rejected,
    }

    # ---- write
    write_json(os.path.join(outdir, 'summary.json'), summary)
    write_json(os.path.join(outdir, 'data_quality.json'), data_quality)
    for region in regions:
        write_json(os.path.join(outdir, 'region_%s.json' % region_key(region)),
                   region_rollups[region])
    for seg in segments:
        write_json(os.path.join(outdir, 'segment_%s.json' % seg), segment_rollups[seg])
    write_json(os.path.join(outdir, 'policy_audit.json'), audit)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
