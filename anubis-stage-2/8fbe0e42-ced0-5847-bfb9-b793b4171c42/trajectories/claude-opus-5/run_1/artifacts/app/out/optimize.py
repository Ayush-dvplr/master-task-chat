#!/usr/bin/env python3
"""Ninefold Marches replay settlement.

usage: optimize.py <capture-dir> <report-dir>

Reads an RPL1 capture set, recovers the withheld engine quantities from the
calibration notes shipped beside the captures, settles the match and writes
the scenario reports.
"""
import csv
import glob
import hashlib
import json
import os
import re
import sys
from fractions import Fraction

ENGINE_KEY = b'MRD-2031'

FALLBACK_WORDS = ['aurochs', 'basilisk', 'cockatrice', 'dryad', 'ettin', 'fenrir',
                  'golem', 'hydra', 'ifrit', 'jotun', 'kelpie', 'lamia', 'manticore',
                  'nixie', 'ogre', 'pegasus', 'quasit', 'roc', 'sylph', 'troll',
                  'undine', 'vodyanoi', 'wyvern', 'xorn']
FALLBACK_LABELS = ['aegis', 'banner', 'cinder', 'dagger', 'ember', 'falcon', 'gale',
                   'harrow', 'ingot', 'javelin', 'kestrel', 'lantern']
FALLBACK_CADENCE = ['peak', 'steady', 'burst', 'latency']

SEALED, CHAINED, STEPPED, DRIFTED, WOVEN, ECHOED = 1, 2, 4, 8, 16, 32
FLIPPED, PADDED, SHADOWED, SPUN, ALIASED, WARDED = 64, 128, 256, 512, 1024, 2048

ZERO24 = '0' * 24


# --------------------------------------------------------------------------
# keyed masks and control digests
# --------------------------------------------------------------------------
_mask_cache = {}


def mask(label, nums):
    key = (label, nums)
    got = _mask_cache.get(key)
    if got is None:
        h = hashlib.sha256()
        h.update(ENGINE_KEY)
        h.update(label.encode())
        for n in nums:
            h.update(b':')
            h.update(str(n).encode())
        got = h.digest()[:12]
        _mask_cache[key] = got
    return got


def control_digest(fragments):
    h = hashlib.sha256()
    h.update(ENGINE_KEY)
    for frag in fragments:
        h.update(b'|')
        h.update(frag.encode('utf-8'))
    return h.hexdigest()[:12]


def xorb(a, b):
    return bytes(x ^ y for x, y in zip(a, b))


def rot_right(buf, amount):
    amount %= len(buf)
    if amount == 0:
        return buf
    return buf[-amount:] + buf[:-amount]


# --------------------------------------------------------------------------
# shipped notes
# --------------------------------------------------------------------------
def read_text(path):
    try:
        with open(path, encoding='utf-8') as fh:
            return fh.read()
    except OSError:
        return ''


def parse_listing(text, lead, fallback):
    """Pull the backticked words out of the sentence that starts with `lead`."""
    idx = text.find(lead)
    if idx < 0:
        return list(fallback)
    stop = text.find('\n\n', idx)
    chunk = text[idx:stop if stop > 0 else len(text)]
    words = re.findall(r'`([a-z_]+)`', chunk)
    return words if words else list(fallback)


class Notes(object):
    def __init__(self, capture_dir):
        scale = read_text(os.path.join(capture_dir, 'charter-scale.md'))
        self.words = parse_listing(scale, 'The twenty four unit words', FALLBACK_WORDS)
        self.labels = parse_listing(scale, 'The twelve label words', FALLBACK_LABELS)
        self.cadence = parse_listing(scale, 'The four cadence classes', FALLBACK_CADENCE)
        calib = read_text(os.path.join(capture_dir, 'calibration.md'))
        self.quantities = []
        for line in calib.split('\n'):
            m = re.match(r'^\|\s*`([a-z_]+)`\s*\|\s*([^|]+?)\s*\|\s*(CTRL-[A-Z])\s*\|', line)
            if m:
                self.quantities.append((m.group(1), parse_candidates(m.group(2)), m.group(3)))
        self.published = {}
        for line in calib.split('\n'):
            m = re.match(r'^\|\s*(CTRL-[A-Z])\s*\|\s*`([0-9a-f]+)`\s*\|', line)
            if m:
                self.published[m.group(1)] = m.group(2)


def parse_candidates(cell):
    m = re.match(r'^(\d+)\s+through\s+(\d+)$', cell.strip())
    if m:
        return list(range(int(m.group(1)), int(m.group(2)) + 1))
    return [int(x) for x in re.findall(r'\d+', cell)]


def load_register(capture_dir):
    rows = []
    with open(os.path.join(capture_dir, 'roster-register.csv')) as fh:
        for r in csv.DictReader(fh):
            closed = r['closed'].strip()
            rows.append({'word': r['word'].strip(),
                         'charter': r['charter'].strip(),
                         'opened': int(r['opened']),
                         'closed': int(closed) if closed else 0,
                         'successor': r['successor'].strip()})
    return rows


def load_windows(capture_dir):
    out = []
    with open(os.path.join(capture_dir, 'tick-schedule.csv')) as fh:
        for r in csv.DictReader(fh):
            out.append({'window': r['window'].strip(),
                        'first': int(r['first_tick']),
                        'last': int(r['last_tick']),
                        'live': r['live'].strip() in ('1', 'true', 'True', 'yes')})
    return out


def load_bench(capture_dir):
    out = []
    with open(os.path.join(capture_dir, 'bench-candidates.csv')) as fh:
        for r in csv.DictReader(fh):
            out.append((r['word'].strip(), int(r['upkeep'])))
    return out


# --------------------------------------------------------------------------
# captures
# --------------------------------------------------------------------------
class Capture(object):
    __slots__ = ('name', 'ordinal', 'flags', 'nblocks', 'frames', 'words',
                 'seal', 'blocks', 'lines')

    def has(self, bit):
        return bool(self.flags & bit)


def parse_captures(capture_dir):
    caps = []
    for path in sorted(glob.glob(os.path.join(capture_dir, '*.rpl'))):
        lines = [l for l in read_text(path).split('\n') if l.strip()]
        if not lines or not lines[0].startswith('#RPL1'):
            continue
        fields = {}
        for kv in lines[0].split()[1:]:
            if '=' in kv:
                k, v = kv.split('=', 1)
                fields[k] = v
        cap = Capture()
        cap.name = fields.get('capture', os.path.basename(path))
        cap.ordinal = int(fields['number'])
        cap.flags = int(fields['flags'], 16)
        cap.nblocks = int(fields['blocks'])
        cap.frames = int(fields['frames'])
        cap.words = fields['words'].split(',')
        cap.seal = fields.get('seal', '')
        cap.blocks = []
        cur = None
        for line in lines[1:]:
            if line.startswith('B '):
                parts = line.split()
                cur = [int(parts[1]), int(parts[2]), []]
                cap.blocks.append(cur)
            elif line.startswith('R '):
                cur[2].append(line.split()[1])
        caps.append(cap)
    caps.sort(key=lambda c: c.ordinal)
    return caps


# --------------------------------------------------------------------------
# wire transforms, undone one at a time
# --------------------------------------------------------------------------
def weave_order(seed_offset, cord, bord, width):
    seed = (seed_offset + 97 * cord + 7 * bord) & 0xffffffff
    seed = (seed * 2654435761 + 1013904223) & 0xffffffff
    if seed == 0:
        seed = 2654435769
    state = seed
    order = list(range(width))
    for i in range(width - 1, 0, -1):
        state ^= (state << 13) & 0xffffffff
        state ^= state >> 17
        state ^= (state << 5) & 0xffffffff
        j = state % (i + 1)
        order[i], order[j] = order[j], order[i]
    return order


def unweave(caps, seed_offset):
    out = {}
    for cap in caps:
        rows = []
        for bord, width, pays in cap.blocks:
            if cap.has(WOVEN):
                order = weave_order(seed_offset, cap.ordinal, bord, width)
                restored = [None] * width
                for pos in range(width):
                    restored[order[pos]] = pays[pos]
                pays = restored
            for pay in pays:
                rows.append((bord, pay))
        out[cap.ordinal] = rows
    return out


def unward_payload(hexpay, sentinel):
    raw = bytes.fromhex(hexpay)
    out = bytearray()
    i = 0
    n = len(raw)
    while i < n:
        if raw[i] == sentinel:
            if i + 1 < n and raw[i + 1] == sentinel:
                out.append(sentinel)
                i += 2
            else:
                return ZERO24
        else:
            out.append(raw[i])
            i += 1
    if len(out) != 12:
        return ZERO24
    return bytes(out).hex()


def unward(caps, woven, sentinel):
    out = {}
    for cap in caps:
        rows = []
        for bord, pay in woven[cap.ordinal]:
            if cap.has(WARDED):
                pay = unward_payload(pay, sentinel)
            elif len(pay) != 24:
                pay = ZERO24
            rows.append((bord, pay))
        out[cap.ordinal] = rows
    return out


def undrift(caps, warded, drift_modulus):
    out = {}
    for cap in caps:
        rows = []
        for bord, pay in warded[cap.ordinal]:
            buf = bytes.fromhex(pay)
            if cap.has(DRIFTED):
                counter = (bord + 1 + 5 * cap.ordinal) % drift_modulus
                buf = xorb(buf, mask('drift', (cap.ordinal, counter)))
            rows.append((bord, buf))
        out[cap.ordinal] = rows
    return out


def unpack(buf, flipped):
    if len(buf) != 12:
        return None
    if mask('entry', tuple(buf[:10]))[:2] != buf[10:12]:
        return None
    if flipped:
        return (buf[1] << 8 | buf[0], buf[3] << 8 | buf[2], buf[4],
                int.from_bytes(buf[5:9], 'little'), buf[9])
    return (buf[0] << 8 | buf[1], buf[2] << 8 | buf[3], buf[4],
            int.from_bytes(buf[5:9], 'big'), buf[9])


def unseal(caps, drifted, pad_base, seal_label, spin_modulus):
    """Drop filler, lift the chain and label masks, unspin and unpack."""
    out = {}
    for cap in caps:
        rows = list(drifted[cap.ordinal])
        if cap.has(SHADOWED):
            npad = pad_base - 3
            spots = [i for i, (bord, _) in enumerate(rows) if bord == 0]
            take = min(max(npad, 0), len(spots))
            drop = set(spots[len(spots) - take:]) if take > 0 else set()
            rows = [row for i, row in enumerate(rows) if i not in drop]
        flipblock = cap.ordinal % cap.nblocks if cap.nblocks else -1
        prev_tick = 0
        prev_amount = 0
        entries = []
        for eord, (bord, buf) in enumerate(rows):
            if cap.has(CHAINED):
                buf = xorb(buf, mask('chain', (cap.ordinal, prev_tick, prev_amount)))
            if cap.has(SEALED):
                buf = xorb(buf, mask(seal_label, (cap.ordinal, eord)))
            if cap.has(SPUN):
                buf = rot_right(buf, (eord + 1) * spin_modulus)
            entry = unpack(buf, cap.has(FLIPPED) and bord == flipblock)
            if entry is None:
                prev_tick, prev_amount = 0, 0
            else:
                prev_tick, prev_amount = entry[0], entry[3]
            entries.append((bord, entry))
        out[cap.ordinal] = entries
    return out


def unstep_and_name(caps, words, raw, donor_shift):
    """Restore the tick series and read the unit index against the right table."""
    ring = len(caps)
    by_ordinal = {c.ordinal: c for c in caps}
    out = {}
    for cap in caps:
        entries = raw[cap.ordinal]
        if cap.has(STEPPED):
            ticks = []
            prev1 = prev2 = None
            for _, entry in entries:
                stored = 0 if entry is None else entry[0]
                if prev1 is None:
                    tick = stored
                elif prev2 is None:
                    tick = (stored + prev1) & 0xffff
                else:
                    tick = (stored + 2 * prev1 - prev2) & 0xffff
                ticks.append(tick)
                prev2, prev1 = prev1, tick
        else:
            ticks = [0 if entry is None else entry[0] for _, entry in entries]
        if cap.has(ALIASED):
            donor = by_ordinal[(cap.ordinal + donor_shift) % ring]
            table = list(donor.words)
            turn = donor_shift % len(table)
            table = table[turn:] + table[:turn]
        else:
            table = words
        named = []
        for i, (_, entry) in enumerate(entries):
            if entry is None:
                named.append(None)
            else:
                named.append((ticks[i], table[entry[1] % len(table)],
                              entry[2], entry[3], entry[4]))
        out[cap.ordinal] = named
    return out


def resolve_echoes(caps, named, echo_span):
    out = {}
    for cap in caps:
        entries = list(named[cap.ordinal])
        if cap.has(ECHOED):
            for i, entry in enumerate(entries):
                if entry is None or entry[2] != 224:
                    continue
                distance = i % (echo_span - 1) + 1
                src = i - distance
                if src < 0 or entries[src] is None:
                    continue
                donor = entries[src]
                entries[i] = (entry[0], donor[1], donor[2], donor[3], donor[4])
        out[cap.ordinal] = entries
    return out


def entry_text(entry):
    if entry is None:
        return 'none'
    return '%d/%d/%d/%d/%d' % entry


def word_entry_text(entry):
    if entry is None:
        return 'none'
    return '%d/%s/%d/%d/%d' % entry


# --------------------------------------------------------------------------
# identity, windows and settlement
# --------------------------------------------------------------------------
def settling_passes(rows):
    by = {r['word']: r for r in rows}
    canon = {r['word']: r['charter'] for r in rows}
    passes = 0
    while True:
        passes += 1
        stale = False
        for row in rows:
            word = row['word']
            succ = row['successor']
            if not succ or succ == word or succ not in by:
                continue
            if canon[word] != canon[succ]:
                canon[word] = canon[succ]
                stale = True
        if not stale:
            return passes


def canonical(by, word, tick):
    seen = set()
    cur = word
    while True:
        row = by.get(cur)
        if row is None:
            return None
        if row['successor'] == cur:
            return cur
        if row['closed'] == 0 or tick <= row['closed']:
            return cur
        if not row['successor'] or cur in seen:
            return None
        seen.add(cur)
        cur = row['successor']


class Settlement(object):
    pass


def settle(caps, entries, rows, windows):
    """Run the whole settlement bar the two scale quantities."""
    by = {r['word']: r for r in rows}
    baseline = {}
    opened_count = {}
    for row in rows:
        baseline[row['charter']] = baseline.get(row['charter'], 0) + row['opened']
        opened_count[row['charter']] = opened_count.get(row['charter'], 0) + 1
    live = sorted([w for w in windows if w['live'] and w['first'] <= w['last']],
                  key=lambda w: w['first'])

    st = Settlement()
    st.baseline = baseline
    st.opened_count = opened_count
    st.charters = sorted(baseline)
    st.entry_total = len(entries)
    st.decoded_amount = sum((e['amount'] for e in entries), Fraction(0))
    st.reversal_count = sum(1 for e in entries if e['kind'] == 3)

    st.dropped_retired = 0
    st.dropped_offwindow = 0
    st.dropped_amount = Fraction(0)
    survivors = []
    for e in entries:
        canon = canonical(by, e['word'], e['tick'])
        if canon is None:
            st.dropped_retired += 1
            st.dropped_amount += e['amount']
            continue
        if not any(w['first'] <= e['tick'] <= w['last'] for w in live):
            st.dropped_offwindow += 1
            st.dropped_amount += e['amount']
            continue
        rec = dict(e)
        rec['canon'] = canon
        rec['charter'] = by[canon]['charter']
        rec['opening_charter'] = by[e['word']]['charter'] if e['word'] in by else None
        survivors.append(rec)

    per_unit = {}
    for rec in survivors:
        per_unit.setdefault(rec['canon'], []).append(rec)

    st.promoted_reversals = 0
    settled = []
    for unit in sorted(per_unit):
        lst = sorted(per_unit[unit], key=lambda r: (r['tick'], r['cap'], r['eord']))
        n = len(lst)
        kinds = [r['kind'] for r in lst]
        cancelled = [False] * n
        spent = [False] * n
        for i in range(n):
            if lst[i]['kind'] != 3:
                continue
            target = lst[i]['mark']
            found = None
            for j in range(i):
                if cancelled[j] or spent[j]:
                    continue
                if kinds[j] == target:
                    found = j
                    break
            if found is None:
                st.promoted_reversals += 1
                kinds[i] = target
            else:
                cancelled[found] = True
                spent[i] = True
        for i in range(n):
            if cancelled[i] or spent[i]:
                continue
            rec = lst[i]
            rec['effective_kind'] = kinds[i]
            settled.append(rec)

    # allowances, drawn in the walk order with a renewal at each live window
    caps_by_charter = {c: Fraction(baseline[c] * opened_count[c]) for c in baseline}
    allowance = dict(caps_by_charter)
    settled.sort(key=lambda r: (r['tick'], r['cap'], r['eord']))
    widx = 0
    for rec in settled:
        while widx < len(live) and live[widx]['first'] <= rec['tick']:
            for ch in allowance:
                allowance[ch] = caps_by_charter[ch]
            widx += 1
        ch = rec['charter']
        left = allowance[ch]
        drawn = rec['amount'] if rec['amount'] <= left else left
        allowance[ch] = left - drawn
        rec['settled_amount'] = drawn

    st.settled = settled
    st.settled_count = len(settled)
    st.settled_amount = sum((r['settled_amount'] for r in settled), Fraction(0))
    st.conservation_residual = st.decoded_amount - st.settled_amount - st.dropped_amount

    units = {}
    for unit in per_unit:
        units[unit] = {'unit': unit, 'charter': by[unit]['charter'],
                       'tick_total': 0, 'amount_total': Fraction(0),
                       'kind_totals': [Fraction(0), Fraction(0), Fraction(0)]}
    for rec in settled:
        u = units[rec['canon']]
        u['tick_total'] += rec['tick']
        u['amount_total'] += rec['settled_amount']
        k = rec['effective_kind']
        if 0 <= k <= 2:
            u['kind_totals'][k] += rec['settled_amount']
    st.units = [units[u] for u in sorted(units)]

    total_baseline = sum(baseline.values())
    flow = {}
    for rec in settled:
        if rec['effective_kind'] != 1:
            continue
        src = rec['opening_charter']
        dst = rec['charter']
        if src is None or src == dst:
            continue
        flow[(src, dst)] = flow.get((src, dst), Fraction(0)) + rec['settled_amount']
    st.stocks = solve_stocks(st.charters, baseline, flow, total_baseline)
    return st


def solve_stocks(charters, baseline, flow, total_baseline):
    """stock[b] = baseline[b] + sum over a of stock[a] * share[a][b]."""
    n = len(charters)
    idx = {c: i for i, c in enumerate(charters)}
    rows = []
    for b in range(n):
        row = [Fraction(0)] * (n + 1)
        row[b] += Fraction(1)
        for (src, dst), amount in flow.items():
            if idx[dst] == b:
                row[idx[src]] -= Fraction(amount, total_baseline)
        row[n] = Fraction(baseline[charters[b]])
        rows.append(row)
    for col in range(n):
        pivot = None
        for r in range(col, n):
            if rows[r][col] != 0:
                pivot = r
                break
        if pivot is None:
            continue
        rows[col], rows[pivot] = rows[pivot], rows[col]
        pv = rows[col][col]
        rows[col] = [x / pv for x in rows[col]]
        for r in range(n):
            if r != col and rows[r][col] != 0:
                factor = rows[r][col]
                rows[r] = [x - factor * y for x, y in zip(rows[r], rows[col])]
    return {charters[i]: rows[i][n] for i in range(n)}


def pick_bench(bench, target):
    """The one subset of the candidates whose upkeep hits the target exactly."""
    if target == 0:
        return []
    if target.denominator != 1:
        return None
    goal = target.numerator
    reach = {0: ()}
    for word, upkeep in bench:
        nxt = dict(reach)
        for total, chosen in reach.items():
            new = total + upkeep
            if new <= goal and new not in nxt:
                nxt[new] = chosen + (word,)
        reach = nxt
        if goal in reach:
            break
    got = reach.get(goal)
    return sorted(got) if got is not None else None


# --------------------------------------------------------------------------
# control figures
# --------------------------------------------------------------------------
class Engine(object):
    def __init__(self, capture_dir):
        self.notes = Notes(capture_dir)
        self.caps = parse_captures(capture_dir)
        self.rows = load_register(capture_dir)
        self.windows = load_windows(capture_dir)
        self.bench = load_bench(capture_dir)
        self._cache = {}

    # memoised stages -----------------------------------------------------
    def stage(self, name, key, build):
        full = (name, key)
        got = self._cache.get(full)
        if got is None:
            got = build()
            self._cache[full] = got
        return got

    def s_weave(self, q):
        k = (q['weave_seed_offset'],)
        return self.stage('b', k, lambda: unweave(self.caps, k[0]))

    def s_ward(self, q):
        k = (q['weave_seed_offset'], q['sentinel_code_value'])
        return self.stage('c', k, lambda: unward(self.caps, self.s_weave(q), k[1]))

    def s_drift(self, q):
        k = (q['weave_seed_offset'], q['sentinel_code_value'], q['drift_modulus'])
        return self.stage('d', k, lambda: undrift(self.caps, self.s_ward(q), k[2]))

    def s_raw(self, q):
        k = (q['weave_seed_offset'], q['sentinel_code_value'], q['drift_modulus'],
             q['shadow_pad_base'], q['seal_label_index'], q['spin_modulus'])
        return self.stage('g', k, lambda: unseal(
            self.caps, self.s_drift(q), k[3],
            self.notes.labels[k[4] % len(self.notes.labels)], k[5]))

    def s_named(self, q):
        k = (q['weave_seed_offset'], q['sentinel_code_value'], q['drift_modulus'],
             q['shadow_pad_base'], q['seal_label_index'], q['spin_modulus'],
             q['alias_donor_shift'])
        return self.stage('h', k, lambda: unstep_and_name(
            self.caps, self.notes.words, self.s_raw(q), k[6]))

    def s_echo(self, q):
        k = (q['weave_seed_offset'], q['sentinel_code_value'], q['drift_modulus'],
             q['shadow_pad_base'], q['seal_label_index'], q['spin_modulus'],
             q['alias_donor_shift'], q['echo_window_span'])
        return self.stage('i', k, lambda: resolve_echoes(
            self.caps, self.s_named(q), k[7]))

    def decoded(self, q):
        key = tuple(sorted(q.items()))
        def build():
            out = []
            for cap in self.caps:
                for eord, entry in enumerate(self.s_echo(q)[cap.ordinal]):
                    if entry is None:
                        continue
                    out.append({'cap': cap.ordinal, 'eord': eord, 'tick': entry[0],
                                'word': entry[1], 'kind': entry[2],
                                'amount': Fraction(entry[3]), 'mark': entry[4]})
            return out
        return self.stage('entries', key, build)

    def settlement(self, q):
        key = tuple(sorted(q.items()))
        return self.stage('settle', key, lambda: settle(
            self.caps, self.decoded(q), self.rows, self.windows))

    # control figures -----------------------------------------------------
    def first_payload(self, q, cap):
        buf = self.s_drift(q)[cap.ordinal][0][1]
        if cap.has(CHAINED):
            buf = xorb(buf, mask('chain', (cap.ordinal, 0, 0)))
        if cap.has(SEALED):
            label = self.notes.labels[q['seal_label_index'] % len(self.notes.labels)]
            buf = xorb(buf, mask(label, (cap.ordinal, 0)))
        return buf

    def produce(self, control, q):
        letter = control.rsplit('-', 1)[-1]
        if letter == 'A':
            limit = q['frame_bias_limit']
            return control_digest([
                '%d:%d' % (c.ordinal, (3 * c.ordinal + 1) % limit if c.has(PADDED) else 0)
                for c in self.caps])
        if letter == 'B':
            rows = self.s_weave(q)
            return control_digest([
                '%d:%s' % (c.ordinal, ','.join(p for _, p in rows[c.ordinal]))
                for c in self.caps])
        if letter == 'C':
            rows = self.s_ward(q)
            return control_digest([
                '%d:%s' % (c.ordinal, ','.join(p for _, p in rows[c.ordinal]))
                for c in self.caps])
        if letter == 'D':
            rows = self.s_drift(q)
            return control_digest([
                '%d:%s' % (c.ordinal, ','.join(b.hex() for _, b in rows[c.ordinal]))
                for c in self.caps])
        if letter == 'E':
            return control_digest([
                '%d:%s' % (c.ordinal, self.first_payload(q, c).hex()) for c in self.caps])
        if letter == 'F':
            frags = []
            for c in self.caps:
                buf = self.first_payload(q, c)
                if c.has(SPUN):
                    buf = rot_right(buf, q['spin_modulus'])
                flip = c.has(FLIPPED) and (c.ordinal % c.nblocks if c.nblocks else -1) == 0
                frags.append('%d:%s' % (c.ordinal, entry_text(unpack(buf, flip))))
            return control_digest(frags)
        if letter == 'G':
            rows = self.s_raw(q)
            return control_digest([
                '%d:%s' % (c.ordinal, ','.join(entry_text(e) for _, e in rows[c.ordinal]))
                for c in self.caps])
        if letter == 'H':
            rows = self.s_named(q)
            return control_digest([
                '%d:%s' % (c.ordinal, ','.join(word_entry_text(e) for e in rows[c.ordinal]))
                for c in self.caps])
        if letter == 'I':
            rows = self.s_echo(q)
            return control_digest([
                '%d:%s' % (c.ordinal, ','.join(word_entry_text(e) for e in rows[c.ordinal]))
                for c in self.caps])
        if letter == 'J':
            st = self.settlement(q)
            modulus = q['cadence_modulus']
            classes = self.notes.cadence
            return control_digest([
                '%s:%s' % (u['unit'], classes[(u['tick_total'] // modulus) % len(classes)])
                for u in st.units])
        if letter == 'K':
            target = Fraction(q['upkeep_target_scale'] * sum(
                r['opened'] for r in self.rows))
            return control_digest(['%d/%d' % (target.numerator, target.denominator)])
        raise ValueError('unknown control ' + control)


# --------------------------------------------------------------------------
# calibration search
# --------------------------------------------------------------------------
def calibrate(engine):
    quantities = engine.notes.quantities
    published = engine.notes.published
    rejected = {name: {} for name, _, _ in quantities}

    def note(name, candidate, control):
        if candidate not in rejected[name]:
            rejected[name][candidate] = control

    def walk(level, state):
        if level == len(quantities):
            return state, None
        name, candidates, control = quantities[level]
        passing = []
        for cand in candidates:
            trial = dict(state)
            trial[name] = cand
            if engine.produce(control, trial) == published.get(control):
                passing.append(cand)
            else:
                note(name, cand, control)
        for cand in passing:
            trial = dict(state)
            trial[name] = cand
            found, stuck = walk(level + 1, trial)
            if found is not None:
                return found, None
            note(name, cand, stuck)
        return None, control

    state, _ = walk(0, {})
    if state is None:
        raise SystemExit('calibration failed: no candidate chain reproduces the controls')
    return state, rejected


# --------------------------------------------------------------------------
# reports
# --------------------------------------------------------------------------
def rat(value):
    f = Fraction(value)
    return '%d/%d' % (f.numerator, f.denominator)


def write_report(report_dir, name, payload):
    with open(os.path.join(report_dir, name), 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(payload, indent=2) + '\n')


def main(argv):
    if len(argv) < 3:
        raise SystemExit('usage: optimize.py <capture-dir> <report-dir>')
    capture_dir, report_dir = argv[1], argv[2]
    os.makedirs(report_dir, exist_ok=True)

    engine = Engine(capture_dir)
    quantities, rejected = calibrate(engine)
    st = engine.settlement(quantities)
    classes = engine.notes.cadence
    modulus = quantities['cadence_modulus']

    for unit in st.units:
        unit['cadence'] = classes[(unit['tick_total'] // modulus) % len(classes)]

    write_report(report_dir, 'scenario_visible.json', {
        'capture_count': len(engine.caps),
        'entry_total': st.entry_total,
        'settled_total': st.settled_count,
        'units': [{'unit': u['unit'], 'charter': u['charter'],
                   'tick_total': u['tick_total'],
                   'amount_total': rat(u['amount_total']),
                   'cadence': u['cadence'],
                   'kind_totals': [rat(x) for x in u['kind_totals']]}
                  for u in st.units],
    })

    for cname in classes:
        members = [u for u in st.units if u['cadence'] == cname]
        write_report(report_dir, 'scenario_%s.json' % cname, {
            'cadence': cname,
            'unit_count': len(members),
            'amount_total': rat(sum((u['amount_total'] for u in members), Fraction(0))),
            'units': [{'unit': u['unit'], 'charter': u['charter'],
                       'tick_total': u['tick_total'],
                       'amount_total': rat(u['amount_total'])} for u in members],
        })

    write_report(report_dir, 'perf_report.json', {
        'charter_stocks': [{'charter': c, 'stock': rat(st.stocks[c])}
                           for c in st.charters],
        'settled_total': rat(st.settled_amount),
        'decoded_total': rat(st.decoded_amount),
        'reversal_count': st.reversal_count,
        'promoted_reversal_count': st.promoted_reversals,
    })

    target = Fraction(quantities['upkeep_target_scale'] * sum(
        r['opened'] for r in engine.rows))
    bench = pick_bench(engine.bench, target)
    if bench is None:
        bench = []
    upkeep = Fraction(sum(dict(engine.bench)[w] for w in bench))
    write_report(report_dir, 'recommendations.json', {
        'target': rat(target),
        'bench': bench,
        'bench_upkeep': rat(upkeep),
        'residual_after_bench': rat(target - upkeep),
    })

    write_report(report_dir, 'data_quality.json', {
        'dropped_retired': st.dropped_retired,
        'dropped_offwindow': st.dropped_offwindow,
        'dropped_amount_total': rat(st.dropped_amount),
        'decoded_amount_total': rat(st.decoded_amount),
        'settled_amount_total': rat(st.settled_amount),
        'conservation_residual': rat(st.conservation_residual),
    })

    write_report(report_dir, 'bottleneck_analysis.json', {
        'quantities': [{'name': name,
                        'value': quantities[name],
                        'control': control,
                        'rejected': [{'candidate': c, 'falsifier': rejected[name][c]}
                                     for c in sorted(rejected[name])]}
                       for name, _, control in engine.notes.quantities],
        'settling_passes': settling_passes(engine.rows),
        'calibration_table': [{'control': control,
                               'published': engine.notes.published.get(control),
                               'produced': engine.produce(control, quantities)}
                              for _, _, control in engine.notes.quantities],
    })


if __name__ == '__main__':
    main(sys.argv)
