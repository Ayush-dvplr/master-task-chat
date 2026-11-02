#!/usr/bin/env python3
"""Derive the season settlement for a Meridian corridor corpus.

Usage: derive_report.py INPUT_DIR OUTPUT_DIR

Everything written is derived from the files in INPUT_DIR: the withheld
packet constants are recovered against the published calibration control
figures, the field population is then decoded, resolved, admitted, placed
and settled.
"""

import csv
import hashlib
import hmac
import json
import math
import os
import re
import sys

MASK64 = (1 << 64) - 1
DAY_MODULUS = 251          # submission days travel below this modulus
FAMILY_PAIRS = None         # filled from dispatch_policy.md


# --------------------------------------------------------------------------
# tables
# --------------------------------------------------------------------------

def read_table(path):
    """UTF-8 CSV with one header row; BOM and padding spaces stripped."""
    with open(path, 'rb') as fh:
        data = fh.read()
    if data.startswith(b'\xef\xbb\xbf'):
        data = data[3:]
    text = data.decode('utf-8')
    rows = list(csv.reader(text.splitlines()))
    rows = [r for r in rows if r and any(c.strip() for c in r)]
    header = [h.strip() for h in rows[0]]
    out = []
    for r in rows[1:]:
        out.append({header[i]: (r[i].strip() if i < len(r) else '') for i in range(len(header))})
    return header, out


def read_doc(path):
    with open(path, 'rb') as fh:
        data = fh.read()
    if data.startswith(b'\xef\xbb\xbf'):
        data = data[3:]
    return data.decode('utf-8')


# --------------------------------------------------------------------------
# policy parsing
# --------------------------------------------------------------------------

def parse_domain(text):
    """'0 through 255' -> [0..255]; '97, 101' -> [97, 101]; 'a, b' -> ['a','b']."""
    text = text.strip()
    m = re.match(r'^(\d+)\s+through\s+(\d+)$', text)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        return list(range(lo, hi + 1))
    parts = [p.strip() for p in text.split(',')]
    if all(re.match(r'^\d+$', p) for p in parts):
        return [int(p) for p in parts]
    return parts


def parse_policies(indir):
    enc = read_doc(os.path.join(indir, 'packet_encoding.md'))
    cap = read_doc(os.path.join(indir, 'capacity_policy.md'))
    cost = read_doc(os.path.join(indir, 'cost_policy.md'))
    disp = read_doc(os.path.join(indir, 'dispatch_policy.md'))
    slice_doc = read_doc(os.path.join(indir, 'calibration_slice.md'))

    pol = {}

    # transform table: | bit | name | constant | domain |
    transforms = []
    for line in enc.splitlines():
        m = re.match(r'^\|\s*(0x[0-9A-Fa-f]+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|$', line)
        if m:
            bit = int(m.group(1), 16)
            name = m.group(2).strip()
            constant = m.group(3).strip()
            domain = parse_domain(m.group(4))
            transforms.append(dict(bit=bit, name=name, constant=constant, domain=domain))
    pol['transforms'] = transforms
    pol['transform_bits'] = {t['name']: t['bit'] for t in transforms}
    pol['domains'] = {t['constant'].replace(' ', '_'): t['domain'] for t in transforms}

    m = re.search(r'over the key `([^`]+)`', enc)
    pol['hmac_key'] = m.group(1).encode('utf-8') if m else b''
    m = re.search(r'the list ([0-9,\s]+?) by position', enc)
    pol['granularity_list'] = [int(x) for x in re.findall(r'\d+', m.group(1))]
    m = re.search(r'A record is (\w+) bytes, or (\w+) bytes', enc)
    pol['record_sizes'] = ('thirteen' in m.group(1), 'fifteen' in m.group(2))
    m = re.search(r'A length code of zero means a (\w+) byte record', enc)
    pol['size_by_code'] = {0: 13, 1: 15}

    # control figures
    figures = {}
    for m in re.finditer(r'^-\s*(\w+)\s*=\s*(-?\d+)\s*$', slice_doc, re.M):
        figures[m.group(1)] = int(m.group(2))
    pol['figures'] = figures

    # capacity policy
    m = re.search(r'congestion_bounds:\s*([0-9,\s]+)', cap)
    pol['congestion_bounds'] = [int(x) for x in re.findall(r'\d+', m.group(1))]
    m = re.search(r'base_ceiling:\s*(.+)', cap)
    pol['base_ceiling'] = dict((p.split('=')[0].strip(), int(p.split('=')[1]))
                               for p in m.group(1).split(','))
    m = re.search(r'tier_factor:\s*(.+)', cap)
    pol['tier_factor'] = dict((int(p.split('=')[0].strip()), int(p.split('=')[1]))
                              for p in m.group(1).split(','))
    m = re.search(r'Report mode labels are ([^,]+), ([^,]+), ([^,]+), and ([^,]+), in that order', cap)
    pol['quant_modes'] = [x.strip().strip('`') for x in m.groups()]
    # the labels are listed in the same order as the four described modes
    described = ['floor', 'ceil', 'nearest', 'band']
    pol['quant_impl'] = dict(zip(pol['quant_modes'], described))

    # cost policy
    m = re.search(r'rebate_band:\s*(.+)', cost)
    pol['rebate_band'] = dict((int(p.split('=')[0].strip()), int(p.split('=')[1]))
                              for p in m.group(1).split(','))

    # dispatch policy
    m = re.search(r'incompatible_families:\s*(.+)', disp)
    pol['incompatible_families'] = [tuple(p.strip().split('|')) for p in m.group(1).split(',')]
    return pol


# --------------------------------------------------------------------------
# block headers and wire decoding
# --------------------------------------------------------------------------

def parse_header(hexstr):
    raw = bytes.fromhex(hexstr.strip())
    return dict(
        raw=raw,
        magic=int.from_bytes(raw[0:2], 'big'),
        block_id=int.from_bytes(raw[2:4], 'big'),
        stored=int.from_bytes(raw[4:6], 'big'),
        flags=int.from_bytes(raw[6:8], 'big'),
        payload_crc=int.from_bytes(raw[16:20], 'big'),
        header_crc=int.from_bytes(raw[20:24], 'big'),
    )


def xorshift64(x):
    x ^= (x << 13) & MASK64
    x ^= x >> 7
    x ^= (x << 17) & MASK64
    return x & MASK64


def hmac_digest(key, msg):
    return hmac.new(key, msg, hashlib.sha256).digest()


class Decoder(object):
    """Decodes one population once the withheld constants are known."""

    def __init__(self, pol, headers, payloads, consts):
        self.pol = pol
        self.key = pol['hmac_key']
        self.gran = pol['granularity_list']
        self.headers = headers          # block_id -> header dict
        self.payloads = payloads        # block_id -> bytes
        self.consts = consts

    # -- low level ---------------------------------------------------------
    def _mask(self, label, bid, ordinal):
        msg = (label.encode('utf-8') + b'|' + bid.to_bytes(2, 'big')
               + ordinal.to_bytes(2, 'big'))
        return hmac_digest(self.key, msg)[:4]

    def _rotate(self, payload, bid):
        n = len(payload)
        k = (bid * self.consts['rotate_step']) % n
        if k == 0:
            return payload
        return payload[n - k:] + payload[:n - k]

    def _block_seed(self, header):
        """block| + block id + the four auxiliary words in travelling order."""
        raw = header['raw']
        island = self.consts['island_offset']
        msg = b'block|' + raw[2:4]
        for off in (8, 10, 12, 14):
            word = raw[off:off + 2]
            if (header['flags'] & 0x040) and off == island:
                word = word[::-1]
            msg += word
        return int.from_bytes(hmac_digest(self.key, msg)[:8], 'big')

    def _perm(self, n, seed, rounds):
        a = list(range(n))
        state = seed
        for _ in range(rounds):
            for i in range(n - 1, 0, -1):
                state = xorshift64(state)
                j = state % (i + 1)
                a[i], a[j] = a[j], a[i]
        return a

    def _split(self, payload, bias):
        """Split a payload at origin into records; None if it does not parse."""
        recs = []
        off = 0
        while off < len(payload):
            if off >= len(payload):
                return None
            cb = payload[off]
            code = (cb >> 4) ^ bias
            if code not in (0, 1):
                return None
            size = self.pol['size_by_code'][code]
            if off + size > len(payload):
                return None
            b = payload[off:off + size]
            if (cb & 0x0F) > 3:
                return None
            if b[11] >= len(self.gran):
                return None
            if b[12] >= DAY_MODULUS:
                return None
            recs.append(dict(
                control=b[0], code=code, mode=b[0] & 0x0F,
                alias=b[1], prog=b[2],
                load_raw=b[3:7],
                due=int.from_bytes(b[7:9], 'big'),
                wt=int.from_bytes(b[9:11], 'big'),
                gran_code=b[11], day=b[12],
                ext=int.from_bytes(b[13:15], 'big') if size == 15 else 0,
            ))
            off += size
        return recs

    # -- per block ---------------------------------------------------------
    def decode_block(self, bid):
        header = self.headers[bid]
        payload = self.payloads[bid]
        flags = header['flags']
        at_origin = self._rotate(payload, bid) if (flags & 0x200) else payload
        bias = self.consts['shadow_bias'] if (flags & 0x080) else 0
        recs = self._split(at_origin, bias)
        n = header['stored']
        if recs is None or len(recs) != n:
            raise ValueError('block %d does not parse' % bid)
        if flags & 0x010:
            perm = self._perm(n, self._block_seed(header), self.consts['permute_rounds'])
        else:
            perm = list(range(n))
        logical = [None] * n
        for pos, lo in enumerate(perm):
            logical[lo] = recs[pos]
        island = self.consts['island_offset']
        aux = {}
        for off in (8, 10, 12, 14):
            word = header['raw'][off:off + 2]
            little = (flags & 0x040) and off == island
            aux[off] = int.from_bytes(word, 'little' if little else 'big')
        return dict(header=header, logical=logical, perm=perm, aux=aux,
                    payload=payload, flags=flags, n=n)

    def decode_population(self):
        return {bid: self.decode_block(bid) for bid in sorted(self.payloads)}

    def load_of(self, block, bid, ordinal):
        rec = block['logical'][ordinal]
        value = int.from_bytes(rec['load_raw'], 'big')
        if block['flags'] & 0x001:
            value ^= int.from_bytes(self._mask(self.consts['stream_label'], bid, ordinal), 'big')
        return value

    def genuine_count(self, block):
        if block['flags'] & 0x400:
            return block['n'] - self.consts['count_bias']
        return block['n']

    # -- full record resolution -------------------------------------------
    def records(self, blocks, corpus):
        """Yield resolved records (genuine and filler) for a population."""
        progs, govern, byid = corpus['progs'], corpus['govern'], corpus['clients']
        ncl = len(corpus['client_rows'])
        out = []
        run = 0
        for bid, block in blocks.items():
            n = block['n']
            gen = self.genuine_count(block)
            progpos = {}
            prev = self.consts['chain_seed']
            recs = []
            for o in range(n):
                raw = block['logical'][o]
                load = self.load_of(block, bid, o)
                factor = 1 + (run % (self.consts['drift_modulus'] - 1))
                if o < gen:
                    run += load
                if block['flags'] & 0x008:
                    day = (raw['day'] * pow(factor, -1, DAY_MODULUS)) % DAY_MODULUS
                else:
                    day = raw['day']
                if block['flags'] & 0x002:
                    duo = (raw['due'] - prev) & 0xFFFF
                else:
                    duo = raw['due']
                prev = duo
                due = block['aux'][10] + duo + raw['ext']
                p = raw['prog']
                if (block['flags'] & 0x020) and p >= 0xF0:
                    back = ((p - 0xF0) % self.consts['window_span']) + 1
                    pid = progpos.get(o - back)
                elif p >= 0xF0:
                    back = ((p - 0xF0) % self.consts['window_span']) + 1
                    pid = progpos.get(o - back)
                else:
                    pid = progs[p % len(progs)]
                progpos[o] = pid
                if block['flags'] & 0x100:
                    alias_client = corpus['client_rows'][(raw['alias'] - self.consts['alias_rotor']) % ncl]['client_id']
                else:
                    alias_client = corpus['client_rows'][raw['alias'] % ncl]['client_id']
                client = govern(alias_client)
                recs.append(dict(
                    order_id='W%04d%02d' % (bid, o), block=bid, ordinal=o,
                    day=day, due=due, duo=duo, programme=pid,
                    client=client, alias_client=alias_client,
                    load=load, granularity=self.gran[raw['gran_code']],
                    mode=raw['mode'], ext=raw['ext'], genuine=o < gen,
                ))
            if block['flags'] & 0x004:
                span = self.consts['delta_span']
                weights = []
                for start in range(0, n, span):
                    grp = [block['logical'][o]['wt'] for o in range(start, min(start + span, n))]
                    w = [grp[0]]
                    if len(grp) > 1:
                        w.append((grp[1] + w[0]) & 0xFFFF)
                    for k in range(2, len(grp)):
                        w.append((grp[k] + 2 * w[k - 1] - w[k - 2]) & 0xFFFF)
                    weights.extend(w)
            else:
                weights = [block['logical'][o]['wt'] for o in range(n)]
            for o in range(n):
                recs[o]['weight'] = weights[o]
            for rec in recs:
                rec['slack'] = rec['due'] - rec['day']
            out.extend(recs)
        return out


# --------------------------------------------------------------------------
# figure computation for constant resolution
# --------------------------------------------------------------------------

def payload_origin_total(decoder):
    """Sum of the first four payload bytes once each payload sits at origin."""
    total = 0
    for bid, payload in decoder.payloads.items():
        flags = decoder.headers[bid]['flags']
        at = decoder._rotate(payload, bid) if (flags & 0x200) else payload
        total += int.from_bytes(at[:4], 'big')
    return total


def _split_with(decoder):
    """Split every block with the standing shadow bias; None unless all parse."""
    out = {}
    for bid, payload in decoder.payloads.items():
        flags = decoder.headers[bid]['flags']
        at = decoder._rotate(payload, bid) if (flags & 0x200) else payload
        use = decoder.consts['shadow_bias'] if (flags & 0x080) else 0
        recs = decoder._split(at, use)
        if recs is None or len(recs) != decoder.headers[bid]['stored']:
            return None
        out[bid] = recs
    return out


def record_span_total(decoder):
    recs = _split_with(decoder)
    if recs is None:
        return None
    return sum(1 for rows in recs.values() for r in rows if r['code'] == 1)


def order_total(decoder):
    recs = _split_with(decoder)
    if recs is None:
        return None
    total = 0
    for bid, rows in recs.items():
        flags = decoder.headers[bid]['flags']
        n = len(rows) - decoder.consts['count_bias'] if (flags & 0x400) else len(rows)
        total += n
    return total


def island_total(decoder):
    island = decoder.consts['island_offset']
    total = 0
    for bid, header in decoder.headers.items():
        raw = header['raw']
        flags = header['flags']
        for off in (8, 10, 12, 14):
            word = raw[off:off + 2]
            little = (flags & 0x040) and off == island
            total += int.from_bytes(word, 'little' if little else 'big')
    return total


def ordinal_checksum(decoder):
    rounds = decoder.consts['permute_rounds']
    total = 0
    for bid, header in decoder.headers.items():
        n = header['stored']
        flags = header['flags']
        if flags & 0x010:
            perm = decoder._perm(n, decoder._block_seed(header), rounds)
        else:
            perm = list(range(n))
        for pos, lo in enumerate(perm):
            total += (1 + pos) * (1 + lo)
    return total


def masked_load_total(decoder):
    blocks = decoder.decode_population()
    total = 0
    for bid, block in blocks.items():
        gen = decoder.genuine_count(block)
        for o in range(gen):
            total += decoder.load_of(block, bid, o)
    return total


def folded_slack_total(decoder, corpus):
    recs = decoder.records(decoder.decode_population(), corpus)
    return sum(r['duo'] for r in recs if r['genuine'])


def delta_weight_total(decoder, corpus):
    recs = decoder.records(decoder.decode_population(), corpus)
    return sum(r['weight'] for r in recs if r['genuine'])


def drift_day_total(decoder, corpus):
    recs = decoder.records(decoder.decode_population(), corpus)
    return sum(r['day'] * (1 + r['ordinal']) for r in recs if r['genuine'])


def canonical_client_total(decoder, corpus):
    recs = decoder.records(decoder.decode_population(), corpus)
    total = 0
    for r in recs:
        if not r['genuine']:
            continue
        digits = re.findall(r'(\d+)', r['client'])
        total += int(digits[-1]) * (1 + r['ordinal'])
    return total


def backref_program_total(decoder, corpus):
    recs = decoder.records(decoder.decode_population(), corpus)
    progs = corpus['progs']
    total = 0
    for r in recs:
        if not r['genuine']:
            continue
        total += progs.index(r['programme']) * (1 + r['ordinal'])
    return total


def billable_slot_total(decoder, corpus):
    mode = decoder.pol['quant_impl'][decoder.consts['quant_mode']]
    recs = decoder.records(decoder.decode_population(), corpus)
    status = classify(recs, corpus)
    total = 0
    for r in recs:
        if not r['genuine']:
            continue
        if status[r['order_id']] != 'scored':
            continue
        total += quantise(r['load'], r['granularity'], mode)
    return total


# --------------------------------------------------------------------------
# settlement
# --------------------------------------------------------------------------

def quantise(load, granularity, mode):
    """Load units brought to a whole multiple of the granularity."""
    whole, remainder = divmod(load, granularity)
    if mode == 'floor':
        return whole * granularity
    if mode == 'ceil':
        return (whole + (1 if remainder else 0)) * granularity
    if mode == 'nearest':
        return (whole + (1 if 2 * remainder >= granularity else 0)) * granularity
    if mode == 'band':
        return (whole + (1 if 4 * remainder >= 3 * granularity else 0)) * granularity
    raise ValueError(mode)


def classify(records, corpus):
    """Per record status: rejected_retired / rejected_revision / deferred / scored."""
    status = {}
    for r in records:
        if not r['genuine']:
            status[r['order_id']] = 'filler'
            continue
        row = corpus['clients'][r['client']]
        if row['retired_on'] and r['day'] >= int(row['retired_on']):
            status[r['order_id']] = 'rejected_retired'
            continue
        rev = corpus['find_revision'](r['programme'], r['day'])
        if rev is None:
            status[r['order_id']] = 'rejected_revision'
            continue
        if int(row['effective_from']) > r['day']:
            status[r['order_id']] = 'deferred_client'
            continue
        r['revision'] = rev['revision']
        r['family'] = rev['family']
        status[r['order_id']] = 'scored'
    return status


def admission(scored, corpus, pol, consts):
    """Congestion fixpoint.  Returns passes, tiers, indexes, admitted, held."""
    sites = corpus['sites']
    capacity = corpus['site_capacity']
    base_ceiling = pol['base_ceiling']
    tier_factor = pol['tier_factor']
    bounds = pol['congestion_bounds']
    order = sorted(scored, key=lambda o: (-o['weight'], o['order_id']))
    tiers = {s: 0 for s in sites}
    passes = 0
    while True:
        ceilings = {}
        for o in order:
            if o['client'] not in ceilings:
                ceilings[o['client']] = (base_ceiling[o['service_class']]
                                         * tier_factor[tiers[o['site']]]) // 100
        running = {}
        admitted = []
        for o in order:
            cur = running.get(o['client'], 0)
            if cur + o['slots'] <= ceilings[o['client']]:
                running[o['client']] = cur + o['slots']
                admitted.append(o)
        passes += 1
        index = {}
        for s in sites:
            filled = sum(o['slots'] for o in admitted if o['site'] == s)
            index[s] = (1000 * filled) // capacity[s]
        new_tiers = {}
        for s in sites:
            tier = 0
            for bound in bounds:
                if index[s] >= bound:
                    tier += 1
            new_tiers[s] = tier
        if new_tiers == tiers:
            return passes, tiers, index, admitted
        tiers = new_tiers


# ---- placement -----------------------------------------------------------

def place_site(orders, lanes, families, stats=None):
    """Exact minimum cost lane assignment with the lexicographic tie-break.

    The charge of a schedule is the sum over orders of billable slots times the
    rate of the lane the order rests on, so once the orders offered are fixed
    it depends only on how many slots each lane fills.  The search is a dynamic
    program over the orders in contention order; its state is, for each lane
    with a positive slot capacity, the slots filled so far and the set of
    process families resting there.

    Three cuts keep it small.  A walk with the family rule relaxed gives, for
    every partial fill level, a lower bound on what the orders still to come
    can cost; a state whose charge so far plus that bound passes the optimum
    lies on no minimum cost schedule.  A state whose family sets are supersets
    of a sibling state with the same fill levels cannot lead anywhere cheaper.
    And a state whose charge so far already passes the optimum cannot either.
    None of the three removes a state a minimum cost schedule uses, so offering
    the lanes in eligible order and keeping the first lane that preserves the
    optimum reproduces the lexicographically first minimum cost sequence.
    """
    relief_lanes = [l for l in lanes
                    if int(l['slot_capacity']) == 0 and not l['class_lock']
                    and not l['exclusive_client']]
    real = sorted([l for l in lanes if l not in relief_lanes],
                  key=lambda l: (int(l['rate_micros']), l['lane_id']))
    relief = sorted(relief_lanes, key=lambda l: (int(l['rate_micros']), l['lane_id']))
    k = len(real)
    caps = [int(l['slot_capacity']) for l in real]
    rates = [int(l['rate_micros']) for l in real]
    relief_id = relief[0]['lane_id'] if relief else None
    relief_rate = int(relief[0]['rate_micros']) if relief else 0

    fams = sorted(set(o['family'] for o in orders))
    bit = {f: 1 << i for i, f in enumerate(fams)}
    nbits = max(1, len(fams))
    valid = [True] * (1 << nbits)
    for a, b in families:
        if a in bit and b in bit:
            for m in range(1 << nbits):
                if (m & bit[a]) and (m & bit[b]):
                    valid[m] = False

    scale = 0
    for o in orders:
        scale = math.gcd(scale, o['slots'])
    for c in caps:
        scale = math.gcd(scale, c)
    scale = scale or 1
    cap_s = [c // scale for c in caps]

    seq = sorted(orders, key=lambda o: (-o['slack'], o['order_id']))
    per = []
    for o in seq:
        cands = []
        for j, lane in enumerate(real):
            if lane['class_lock'] and lane['class_lock'] != o['service_class']:
                continue
            if lane['exclusive_client'] and lane['exclusive_client'] != o['client']:
                continue
            cands.append(j)
        per.append(dict(order=o, slots=o['slots'] // scale,
                        cands=cands, fam=bit[o['family']],
                        costs=[o['slots'] * rates[j] for j in cands],
                        relief_ok=relief_id is not None,
                        relief_cost=o['slots'] * relief_rate))
    n = len(per)

    fb = 1
    for c in cap_s:
        fb = max(fb, (c + 1).bit_length())
    mb = nbits
    fmask = (1 << fb) - 1
    mmask = (1 << mb) - 1
    fill_part = 0
    for j in range(k):
        fill_part |= fmask << (fb * j)
    prof_part = 0
    for j in range(k):
        prof_part |= mmask << (fb * k + mb * j)
    prof_shift = fb * k

    prefix = [0] * (n + 1)
    for i, p in enumerate(per):
        prefix[i + 1] = prefix[i] + p['order']['slots']

    def child(v, j, slots, fam):
        old = (v >> (prof_shift + mb * j)) & mmask
        new = old | fam
        return v + (slots << (fb * j)) + ((new - old) << (prof_shift + mb * j))

    def charge_of(v, i):
        filled = 0
        real_charge = 0
        for j in range(k):
            f = ((v >> (fb * j)) & fmask) * scale
            filled += f
            real_charge += f * rates[j]
        return real_charge + (prefix[i] - filled) * relief_rate

    def options(v, p):
        out = []
        for idx, j in enumerate(p['cands']):
            if (((v >> (fb * j)) & fmask) + p['slots']) > cap_s[j]:
                continue
            if not valid[((v >> (prof_shift + mb * j)) & mmask) | p['fam']]:
                continue
            out.append((child(v, j, p['slots'], p['fam']), p['costs'][idx], j))
        if p['relief_ok']:
            out.append((v, p['relief_cost'], -1))
        return out

    start = 0

    # ---- a first fit schedule bounds the optimum from above ---------------
    limit = 0
    v = start
    for p in per:
        for nv, cost, _j in options(v, p):
            v = nv
            limit += cost
            break

    # ---- a floor on the charge still to come ------------------------------
    # every order still to be offered costs at least its cheapest eligible rate
    floor = [0] * (n + 1)
    for i in range(n - 1, -1, -1):
        p = per[i]
        cheapest = relief_rate
        for j in p['cands']:
            if rates[j] < cheapest:
                cheapest = rates[j]
        floor[i] = floor[i + 1] + p['order']['slots'] * cheapest

    # ---- relaxed walk: lower bound on the charge still to come ------------
    cap_layers = [set() for _ in range(n + 1)]
    cap_layers[0].add(0)
    for i, p in enumerate(per):
        nxt = set()
        for f in cap_layers[i]:
            if charge_of(f, i) + floor[i] > limit:
                continue
            for j in p['cands']:
                if (((f >> (fb * j)) & fmask) + p['slots']) > cap_s[j]:
                    continue
                nxt.add(f + (p['slots'] << (fb * j)))
            if p['relief_ok']:
                nxt.add(f)
        cap_layers[i + 1] = nxt
    cap_tail = [None] * (n + 1)
    cap_tail[n] = {f: 0 for f in cap_layers[n]}
    for i in range(n - 1, -1, -1):
        p = per[i]
        cur = {}
        for f in cap_layers[i]:
            here = None
            for idx, j in enumerate(p['cands']):
                if (((f >> (fb * j)) & fmask) + p['slots']) > cap_s[j]:
                    continue
                rest = cap_tail[i + 1].get(f + (p['slots'] << (fb * j)))
                if rest is None:
                    continue
                total = p['costs'][idx] + rest
                if here is None or total < here:
                    here = total
            if p['relief_ok']:
                rest = cap_tail[i + 1].get(f)
                if rest is not None and (here is None or p['relief_cost'] + rest < here):
                    here = p['relief_cost'] + rest
            if here is not None:
                cur[f] = here
        cap_tail[i] = cur

    def forward(limit, dominance, bound_cut):
        layers = [None] * (n + 1)
        layers[0] = {start}
        for i, p in enumerate(per):
            nxt = set()
            for v in layers[i]:
                if charge_of(v, i) + floor[i] > limit:
                    continue
                if bound_cut:
                    rest = cap_tail[i].get(v & fill_part)
                    if rest is None or charge_of(v, i) + rest > limit:
                        continue
                for nv, _cost, _j in options(v, p):
                    nxt.add(nv)
            if dominance:
                groups = {}
                for v in nxt:
                    groups.setdefault(v & fill_part, []).append(v)
                keep = set()
                for _fills, vs in groups.items():
                    if len(vs) == 1:
                        keep.add(vs[0])
                        continue
                    kept = []
                    for v in vs:
                        mv = (v & prof_part) >> prof_shift
                        dominated = False
                        for w in kept:
                            if (((w & prof_part) >> prof_shift) | mv) == mv:
                                dominated = True
                                break
                        if not dominated:
                            kept = [w for w in kept
                                    if not ((mv | ((w & prof_part) >> prof_shift))
                                            == ((w & prof_part) >> prof_shift))]
                            kept.append(v)
                    keep.update(kept)
                nxt = keep
            layers[i + 1] = nxt
        return layers

    layers = forward(limit, True, True)
    best = min(charge_of(v, n) for v in layers[n])
    layers = forward(best, False, True)

    tail = [None] * (n + 1)
    tail[n] = {v: 0 for v in layers[n]}
    for i in range(n - 1, -1, -1):
        p = per[i]
        cur = {}
        for v in layers[i]:
            here = None
            for nv, cost, _j in options(v, p):
                rest = tail[i + 1].get(nv)
                if rest is None:
                    continue
                total = cost + rest
                if here is None or total < here:
                    here = total
            if here is not None:
                cur[v] = here
        tail[i] = cur

    assign = {}
    v = start
    remaining = best
    for i, p in enumerate(per):
        choice = None
        for nv, cost, j in options(v, p):
            rest = tail[i + 1].get(nv)
            if rest is not None and cost + rest == remaining:
                choice = (real[j]['lane_id'] if j >= 0 else relief_id, cost, nv)
                break
        if choice is None:
            raise AssertionError('no minimum cost lane for %s' % p['order']['order_id'])
        lane_id, cost, nv = choice
        assign[p['order']['order_id']] = lane_id
        remaining -= cost
        v = nv
    if stats is not None:
        stats['states'] = sum(len(l) for l in layers if l)
        stats['max_states'] = max(len(l) for l in layers if l)
        stats['relaxed_states'] = sum(len(l) for l in cap_layers)
    return assign, best


# --------------------------------------------------------------------------
# settlement driver
# --------------------------------------------------------------------------

def settle(decoder, blocks, corpus, pol, consts):
    records = decoder.records(blocks, corpus)
    status = classify(records, corpus)
    for r in records:
        r['status'] = status[r['order_id']]
        row = corpus['clients'][r['client']]
        r['site'] = row['site']
        r['service_class'] = row['service_class']
        r['slots'] = quantise(r['load'], r['granularity'],
                               pol['quant_impl'][consts['quant_mode']])
    scored = [r for r in records if r['status'] == 'scored']
    passes, tiers, index, admitted = admission(scored, corpus, pol, consts)
    admitted_ids = set(o['order_id'] for o in admitted)
    for r in scored:
        r['placed'] = r['order_id'] in admitted_ids
        r['status'] = 'placed' if r['placed'] else 'deferred_ceiling'
    # placement
    placement = {}
    site_cost = {}
    search_stats = {}
    for site in corpus['sites']:
        site_orders = [o for o in admitted if o['site'] == site]
        st = {}
        assign, cost = place_site(site_orders, corpus['lanes'][site],
                                  pol['incompatible_families'], st)
        placement.update(assign)
        site_cost[site] = cost
        search_stats[site] = st
    for o in admitted:
        o['lane'] = placement[o['order_id']]
        lane = corpus['lane_by_id'][o['lane']]
        o['charge'] = o['slots'] * int(lane['rate_micros'])
        o['rebate'] = o['slots'] * pol['rebate_band'][o['mode']]
        o['net'] = o['charge'] - o['rebate']
    # budget capping, ascending order of identifier per client
    placed = sorted(admitted, key=lambda o: o['order_id'])
    running = {}
    for o in placed:
        client = o['client']
        cur = running.get(client, 0)
        ceiling = int(corpus['clients'][client]['budget_cap_micros'])
        if cur + o['net'] <= ceiling:
            o['capped'] = 0
            running[client] = cur + o['net']
        else:
            o['capped'] = cur + o['net'] - ceiling
            running[client] = ceiling
    return dict(records=records, scored=scored, admitted=admitted,
                passes=passes, tiers=tiers, index=index,
                site_cost=site_cost, search_stats=search_stats,
                placement=placement, placed=placed)


# --------------------------------------------------------------------------
# corpus loading
# --------------------------------------------------------------------------

def load_corpus(indir, pol):
    _, client_rows = read_table(os.path.join(indir, 'client_directory.csv'))
    _, program_rows = read_table(os.path.join(indir, 'program_registry.csv'))
    _, lane_rows = read_table(os.path.join(indir, 'lane_roster.csv'))
    _, site_rows = read_table(os.path.join(indir, 'site_directory.csv'))
    _, manifest_rows = read_table(os.path.join(indir, 'block_manifest.csv'))

    clients = {r['client_id']: r for r in client_rows}
    merges = {r['client_id']: (r['merged_into'] or None) for r in client_rows}

    def govern(cid):
        chain = []
        cur = cid
        while True:
            nxt = merges.get(cur)
            if not nxt:
                return cur
            if cur in chain:
                return min(set(chain))
            chain.append(cur)
            cur = nxt

    programmes = {}
    for r in program_rows:
        programmes.setdefault(r['program_id'], []).append(
            (int(r['revision']), int(r['effective_from']), int(r['effective_to']), r['family']))

    def find_revision(pid, day):
        if pid is None:
            return None
        for rev, lo, hi, family in programmes.get(pid, []):
            if lo <= day < hi:
                return dict(revision=rev, family=family)
        return None

    progs = sorted(set(r['program_id'] for r in program_rows))
    sites = [r['name'] for r in site_rows]
    site_capacity = {r['name']: int(r['capacity_slots']) for r in site_rows}
    site_region = {r['name']: r['region'] for r in site_rows}
    lanes = {}
    for r in lane_rows:
        lanes.setdefault(r['site'], []).append(r)
    lane_by_id = {r['lane_id']: r for r in lane_rows}

    return dict(client_rows=client_rows, clients=clients, govern=govern,
                progs=progs, find_revision=find_revision, sites=sites,
                site_capacity=site_capacity, site_region=site_region,
                lanes=lanes, lane_by_id=lane_by_id)


def discover_populations(indir, manifest_rows):
    """Map each manifest population to the payload table that carries it."""
    payloads = {}
    for fname in sorted(os.listdir(indir)):
        if not fname.endswith('.csv'):
            continue
        path = os.path.join(indir, fname)
        try:
            header, rows = read_table(path)
        except Exception:
            continue
        if 'payload_hex' not in header or 'block_id' not in header:
            continue
        payloads[fname] = {int(r['block_id']): bytes.fromhex(r['payload_hex'])
                           for r in rows if r['payload_hex']}
    names = []
    for r in manifest_rows:
        if r['population'] not in names:
            names.append(r['population'])
    wanted = {n: set(int(r['block_id']) for r in manifest_rows
                    if r['population'] == n) for n in names}
    pops = {}
    used = set()
    for name in names:
        ids = wanted[name]
        chosen = None
        for fname, data in sorted(payloads.items()):
            if fname in used or not set(data) <= ids:
                continue
            if name.lower() in fname.lower():
                chosen = fname
                break
        if chosen is None:
            fits = [fname for fname, data in sorted(payloads.items())
                    if fname not in used and set(data) <= ids]
            if len(fits) == 1:
                chosen = fits[0]
        if chosen is not None:
            used.add(chosen)
            pops[name] = (chosen, payloads[chosen])
    headers = {}
    for r in manifest_rows:
        headers.setdefault(r['population'], {})
        headers[r['population']][int(r['block_id'])] = parse_header(r['header_hex'])
    return pops, headers


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def resolve_constants(pol, corpus, blocks_headers, blocks_payloads, indir):
    """Recover every withheld constant against the calibration figures."""
    figures = pol['figures']
    domains = pol['domains']
    consts = {}
    audit = []

    dummy = dict(consts)
    for key in domains:
        dummy[key] = domains[key][0]
    decoder = Decoder(pol, blocks_headers, blocks_payloads, dummy)

    def resolve(name, control, domain, compute):
        verdicts = []
        chosen = None
        for value in domain:
            decoder.consts[name] = value
            try:
                got = compute()
            except Exception:
                got = None
            ok = (got == figures[control])
            verdicts.append(dict(value=value, verdict='accepted' if ok else 'rejected'))
            if ok and chosen is None:
                chosen = value
        if chosen is None:
            raise SystemExit('no candidate for %s reproduces %s' % (name, control))
        decoder.consts[name] = chosen
        consts[name] = chosen
        audit.append(dict(parameter=name, control=control,
                          domain_size=len(domain), resolved=chosen,
                          rejected=len(domain) - 1, verdicts=verdicts))
        return chosen

    # 1. payload rotation
    resolve('rotate_step', 'payload_origin_total', domains['rotate_step'],
            lambda: payload_origin_total(decoder))

    # 2. length shadow
    resolve('shadow_bias', 'record_span_total', domains['shadow_bias'],
            lambda: record_span_total(decoder))

    # 3. count bias
    resolve('count_bias', 'calibration_order_total', domains['count_bias'],
            lambda: order_total(decoder))

    # 4. island offset
    resolve('island_offset', 'island_field_total', domains['island_offset'],
            lambda: island_total(decoder))

    # 5. permute rounds
    resolve('permute_rounds', 'ordinal_position_checksum', domains['permute_rounds'],
            lambda: ordinal_checksum(decoder))

    # 6. stream label
    resolve('stream_label', 'masked_load_total', domains['stream_label'],
            lambda: masked_load_total(decoder))

    # 7. chain seed
    resolve('chain_seed', 'folded_slack_total', domains['chain_seed'],
            lambda: folded_slack_total(decoder, corpus))

    # 8. delta span
    resolve('delta_span', 'delta_weight_total', domains['delta_span'],
            lambda: delta_weight_total(decoder, corpus))

    # 9. drift modulus
    resolve('drift_modulus', 'drift_day_total', domains['drift_modulus'],
            lambda: drift_day_total(decoder, corpus))

    # 10. alias rotor
    resolve('alias_rotor', 'canonical_client_total', domains['alias_rotor'],
            lambda: canonical_client_total(decoder, corpus))

    # 11. window span
    resolve('window_span', 'backref_program_total', domains['window_span'],
            lambda: backref_program_total(decoder, corpus))

    # 12. quantisation mode
    resolve('quant_mode', 'billable_slot_total', pol['quant_modes'],
            lambda: billable_slot_total(decoder, corpus))

    repro = [
        dict(control='payload_origin_total', published=figures['payload_origin_total'],
             reproduced=payload_origin_total(decoder)),
        dict(control='record_span_total', published=figures['record_span_total'],
             reproduced=record_span_total(decoder)),
        dict(control='calibration_order_total', published=figures['calibration_order_total'],
             reproduced=order_total(decoder)),
        dict(control='island_field_total', published=figures['island_field_total'],
             reproduced=island_total(decoder)),
        dict(control='ordinal_position_checksum', published=figures['ordinal_position_checksum'],
             reproduced=ordinal_checksum(decoder)),
        dict(control='masked_load_total', published=figures['masked_load_total'],
             reproduced=masked_load_total(decoder)),
        dict(control='folded_slack_total', published=figures['folded_slack_total'],
             reproduced=folded_slack_total(decoder, corpus)),
        dict(control='delta_weight_total', published=figures['delta_weight_total'],
             reproduced=delta_weight_total(decoder, corpus)),
        dict(control='drift_day_total', published=figures['drift_day_total'],
             reproduced=drift_day_total(decoder, corpus)),
        dict(control='canonical_client_total', published=figures['canonical_client_total'],
             reproduced=canonical_client_total(decoder, corpus)),
        dict(control='backref_program_total', published=figures['backref_program_total'],
             reproduced=backref_program_total(decoder, corpus)),
        dict(control='billable_slot_total', published=figures['billable_slot_total'],
             reproduced=billable_slot_total(decoder, corpus)),
    ]
    blocks = decoder.decode_population()
    return consts, audit, repro, decoder, blocks


def rollup(orders, key_field, key_value):
    """One region or service class rollup, in the shape of the probe example."""
    entries = []
    for o in sorted(orders, key=lambda x: x['order_id']):
        entries.append(dict(
            billable_slots=o['slots'], capped_micros=o['capped'],
            charge_micros=o['charge'], client_id=o['client'],
            lane_id=o['lane'], net_micros=o['net'], order_id=o['order_id'],
            program_id=o['programme'], rebate_micros=o['rebate'],
            revision=o['revision'], slack=o['slack']))
    totals = dict(
        billable_slots=sum(o['slots'] for o in orders),
        capped_micros=sum(o['capped'] for o in orders),
        charge_micros=sum(o['charge'] for o in orders),
        net_micros=sum(o['net'] for o in orders),
        rebate_micros=sum(o['rebate'] for o in orders))
    return dict(order_count=len(orders), orders=entries,
                **{key_field: key_value}, totals=totals)


def main():
    if len(sys.argv) < 3:
        raise SystemExit('usage: derive_report.py INPUT_DIR OUTPUT_DIR')
    indir, outdir = sys.argv[1], sys.argv[2]
    os.makedirs(outdir, exist_ok=True)

    pol = parse_policies(indir)
    corpus = load_corpus(indir, pol)
    _, manifest_rows = read_table(os.path.join(indir, 'block_manifest.csv'))
    pops, headers = discover_populations(indir, manifest_rows)

    calibration = None
    field = None
    for name in pops:
        if 'calib' in name.lower():
            calibration = name
        else:
            field = field or name
    if calibration is None or field is None:
        raise SystemExit('the corpus carries no calibration and field population')

    # ---- recover the withheld constants against the published figures ----
    consts, audit, comparison, _decoder, _blocks = resolve_constants(
        pol, corpus, headers[calibration], pops[calibration][1], indir)

    # ---- settle the calibration population ------------------------------
    cal_decoder = Decoder(pol, headers[calibration], pops[calibration][1], consts)
    cal = settle(cal_decoder, cal_decoder.decode_population(), corpus, pol, consts)

    # ---- settle the field population ------------------------------------
    field_decoder = Decoder(pol, headers[field], pops[field][1], consts)
    res = settle(field_decoder, field_decoder.decode_population(), corpus, pol, consts)

    records = res['records']
    placed = res['placed']
    genuine = [r for r in records if r['genuine']]
    rejected = sorted(r['order_id'] for r in records
                      if r['genuine'] and r['status'].startswith('rejected'))
    deferred = sorted(r['order_id'] for r in records
                      if r['genuine'] and r['status'].startswith('deferred'))

    regions = []
    for site in corpus['sites']:
        name = corpus['site_region'][site]
        regions.append(name[0].upper() + name[1:])
    regions = sorted(set(regions))
    segments = sorted(set(r['service_class'] for r in corpus['client_rows']))

    region_orders = {name: [] for name in regions}
    for o in placed:
        name = corpus['site_region'][o['site']]
        region_orders[name[0].upper() + name[1:]].append(o)
    segment_orders = {name: [] for name in segments}
    for o in placed:
        segment_orders[o['service_class']].append(o)

    for name in regions:
        with open(os.path.join(outdir, 'region_%s.json' % name), 'w') as fh:
            json.dump(rollup(region_orders[name], 'region', name), fh,
                      indent=2, sort_keys=True)
            fh.write('\n')
    for name in segments:
        with open(os.path.join(outdir, 'segment_%s.json' % name), 'w') as fh:
            json.dump(rollup(segment_orders[name], 'service_class', name), fh,
                      indent=2, sort_keys=True)
            fh.write('\n')

    region_net = {name: sum(o['net'] for o in region_orders[name]) for name in regions}
    segment_net = {name: sum(o['net'] for o in segment_orders[name]) for name in segments}
    total_net = sum(o['net'] for o in placed)

    summary = dict(
        order_rows=len(genuine),
        decoded_rows=len(records),
        orders_scored=len(res['scored']),
        orders_placed=len(placed),
        orders_deferred=len(deferred),
        orders_rejected=len(rejected),
        billable_slots_total=sum(o['slots'] for o in placed),
        charge_micros_total=sum(o['charge'] for o in placed),
        rebate_micros_total=sum(o['rebate'] for o in placed),
        capped_micros_total=sum(o['capped'] for o in placed),
        net_micros_total=total_net,
        lanes_used=len(set(o['lane'] for o in placed)),
    )
    with open(os.path.join(outdir, 'summary.json'), 'w') as fh:
        json.dump(summary, fh, indent=2, sort_keys=True)
        fh.write('\n')

    region_ids = [o['order_id'] for name in regions for o in region_orders[name]]
    segment_ids = [o['order_id'] for name in segments for o in segment_orders[name]]
    dq = dict(
        order_rows=len(genuine),
        decoded_rows=len(records),
        rejected_orders=rejected,
        deferred_orders=deferred,
        region_net_micros=region_net,
        segment_net_micros=segment_net,
        conservation_residual_micros=total_net - sum(region_net.values()),
        segment_residual_micros=total_net - sum(segment_net.values()),
        calibration_net_micros=sum(o['net'] for o in cal['placed']),
        invariants=dict(
            region_partition_closed=(sorted(region_ids) ==
                                     sorted(o['order_id'] for o in placed)
                                     and len(region_ids) == len(set(region_ids))
                                     and total_net == sum(region_net.values())),
            segment_partition_closed=(sorted(segment_ids) ==
                                       sorted(o['order_id'] for o in placed)
                                       and len(segment_ids) == len(set(segment_ids))
                                       and total_net == sum(segment_net.values())),
            order_identity_unique=(len(set(o['order_id'] for o in placed)) == len(placed)),
            capacity_respected=check_capacity(placed, corpus),
        ),
    )
    with open(os.path.join(outdir, 'data_quality.json'), 'w') as fh:
        json.dump(dq, fh, indent=2, sort_keys=True)
        fh.write('\n')

    audit_report = dict(
        candidate_space=audit,
        resolved_parameters={key: consts[key] for key in
                             ['rotate_step', 'shadow_bias', 'count_bias', 'island_offset',
                              'permute_rounds', 'stream_label', 'chain_seed', 'delta_span',
                              'drift_modulus', 'alias_rotor', 'window_span', 'quant_mode']},
        calibration_comparison=comparison,
        fixpoint=dict(passes=res['passes'],
                      congestion_index=res['index'],
                      congestion_tier=res['tiers']),
        assignment_search=dict(
            sites_searched=len(res['search_stats']),
            feasible_leaves=sum(s['states'] for s in res['search_stats'].values()),
            displaced_orders=sum(1 for o in placed
                                 if int(corpus['lane_by_id'][o['lane']]['slot_capacity']) == 0),
            site_cost_micros=res['site_cost'],
        ),
        candidates_examined=sum(a['domain_size'] for a in audit),
        candidates_rejected=sum(a['rejected'] for a in audit),
    )
    with open(os.path.join(outdir, 'policy_audit.json'), 'w') as fh:
        json.dump(audit_report, fh, indent=2, sort_keys=True)
        fh.write('\n')


def check_capacity(placed, corpus):
    """No lane with a positive slot capacity carries slots beyond it."""
    load = {}
    for o in placed:
        load[o['lane']] = load.get(o['lane'], 0) + o['slots']
    for lane_id, filled in load.items():
        cap = int(corpus['lane_by_id'][lane_id]['slot_capacity'])
        if cap > 0 and filled > cap:
            return False
    return True


if __name__ == '__main__':
    main()
