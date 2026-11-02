#!/usr/bin/env python3
"""Derive the occupancy measurement of the national band coexistence register.

Usage: python3 derive_report.py <corpus_dir> <output_dir>

Reads a corpus laid out like the one it was cut from, writes nine json
documents into the output directory.  Uses only the python standard library,
reads nothing outside the corpus directory it is given and writes nothing
outside the output directory it is given.
"""

import csv
import json
import os
import sys
from collections import defaultdict

EPOCH_DAY = 86400
GRANT_LAYERS = ('core', 'office', 'coord')
PUBLISHED_RANK = ['coord', 'core', 'office']
FIELD_GROUPS = ('identity', 'time', 'frequency')
ZONES = ('North', 'South', 'West', 'East')
NOTE_RECORD_ACTION = 'note'
RETRACT_ACTION = 'retract'


# --------------------------------------------------------------------------
# generic helpers
# --------------------------------------------------------------------------

def md_tables(text):
    """Parse every markdown table of a document into a list of dicts."""
    out = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith('|') and i + 1 < len(lines) and set(lines[i + 1].replace('|', '').replace(' ', '')) <= set('-:'):
            header = [c.strip() for c in line.strip().strip('|').split('|')]
            rows = []
            j = i + 2
            while j < len(lines) and lines[j].startswith('|'):
                cells = [c.strip() for c in lines[j].strip().strip('|').split('|')]
                rows.append(dict(zip(header, cells)))
                j += 1
            out.append(rows)
            i = j
        else:
            i += 1
    return out


def read_csv(path, delimiter=','):
    with open(path, newline='') as fh:
        return list(csv.DictReader(fh, delimiter=delimiter))


def read_jsonl(path):
    rows = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def parse_ini(path):
    """Minimal ini reader for the flat scalar sections of the corpus."""
    sections = {}
    cur = None
    with open(path) as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith('#') or line.startswith(';'):
                continue
            if line.startswith('[') and line.endswith(']'):
                cur = line[1:-1]
                sections[cur] = {}
                continue
            if '=' in line and cur is not None:
                k, v = line.split('=', 1)
                sections[cur][k.strip()] = v.strip()
    return sections


def to_int(value):
    """Exact integer conversion; anything not whole is a fault."""
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError('not an integer')
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value != int(value):
            raise ValueError('not exact')
        return int(value)
    text = str(value).strip()
    if not text:
        return None
    neg = text.startswith('-')
    if neg:
        text = text[1:]
    if not text.isdigit():
        raise ValueError('not exact')
    n = int(text)
    return -n if neg else n


def round_half_even(num, den):
    """Round num/den once, halves to even, with exact integers."""
    if den == 0:
        return 0
    neg = (num < 0) != (den < 0)
    num, den = abs(num), abs(den)
    q, r = divmod(num, den)
    if 2 * r > den or (2 * r == den and q % 2 == 1):
        q += 1
    return -q if neg else q


def largest_remainder_shares(values, total):
    """Allocate `total` integer points over `values` by largest remainder."""
    keys = sorted(values)
    base = sum(values[k] for k in keys)
    if base == 0:
        return dict((k, 0) for k in keys)
    shares = {}
    remainders = []
    assigned = 0
    for k in keys:
        q, r = divmod(values[k] * total, base)
        shares[k] = q
        assigned += q
        remainders.append((r, k))
    remainders.sort(key=lambda t: (-t[0], t[1]))
    for i in range(total - assigned):
        shares[remainders[i % len(remainders)][1]] += 1
    return shares


# --------------------------------------------------------------------------
# exact time
# --------------------------------------------------------------------------

def parse_clock(text):
    """Parse a hh:mm[:ss] clock into seconds."""
    if text is None:
        return 0
    text = str(text).strip()
    if not text:
        return 0
    parts = text.split(':')
    hh = int(parts[0])
    mm = int(parts[1]) if len(parts) > 1 else 0
    ss = int(parts[2]) if len(parts) > 2 else 0
    return hh * 3600 + mm * 60 + ss


def days_from_civil(y, m, d):
    y -= m <= 2
    era = (y if y >= 0 else y - 399) // 400
    yoe = y - era * 400
    doy = (153 * (m + (-3 if m > 2 else 9)) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def civil_from_days(z):
    z += 719468
    era = (z if z >= 0 else z - 146096) // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    y = yoe + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = mp + (3 if mp < 10 else -9)
    return y + (m <= 2), m, d


def month_key(y, m):
    return '%04d-%02d' % (y, m)


def month_of_key(key):
    y, m = key.split('-')
    return int(y), int(m)


class Stamp(object):
    """Wall clock stamps on an exact second grid."""

    @staticmethod
    def parse(text):
        if text is None:
            return None
        text = str(text).strip()
        if text == '':
            return None
        body = text.replace('T', ' ')
        date, _, clock = body.partition(' ')
        y, m, d = [int(p) for p in date.split('-')]
        hh = mm = ss = 0
        if clock:
            parts = clock.split(':')
            hh = int(parts[0])
            if len(parts) > 1:
                mm = int(parts[1])
            if len(parts) > 2:
                tail = parts[2].split('.')[0]
                tail = tail.rstrip('Zz')
                ss = int(tail) if tail else 0
        return days_from_civil(y, m, d) * EPOCH_DAY + hh * 3600 + mm * 60 + ss

    @staticmethod
    def parse_offset(text):
        """Parse a stamp carrying an explicit utc offset; return utc seconds."""
        if text is None:
            return None
        text = str(text).strip()
        if text == '':
            return None
        if text.endswith('Z'):
            return Stamp.parse(text[:-1])
        for i in range(len(text) - 1, max(len(text) - 8, 0) - 1, -1):
            if text[i] in '+-' and ':' in text[i + 1:]:
                body = text[:i]
                sign = 1 if text[i] == '+' else -1
                hh, mm = text[i + 1:].split(':')
                off = sign * (int(hh) * 3600 + int(mm) * 60)
                return Stamp.parse(body) - off
        return Stamp.parse(text)

    @staticmethod
    def render(seconds):
        days, rem = divmod(seconds, EPOCH_DAY)
        y, m, d = civil_from_days(days)
        return '%04d-%02d-%02dT%02d:%02d:%02dZ' % (y, m, d, rem // 3600, (rem % 3600) // 60, rem % 60)


class ZoneClock(object):
    """The local wall clock of a zone, with its annual summer window."""

    def __init__(self, std_sec, summer_sec, summer_from, summer_to, keying):
        self.std = std_sec
        self.summer = summer_sec
        self.window = None
        if summer_from and summer_to:
            lo = Stamp.parse(summer_from)
            hi = Stamp.parse(summer_to)
            shift = std_sec if keying == 'local_standard' else 0
            self.window = (lo - shift, hi - shift)

    def offset_at(self, t):
        w = self.window
        if w is not None and w[0] <= t < w[1]:
            return self.summer
        return self.std

    def utc_to_local(self, t):
        return t + self.offset_at(t)

    def local_to_utc(self, local):
        cands = set([local - self.std])
        if self.window is not None:
            cands.add(local - self.summer)
        good = [c for c in cands if c + self.offset_at(c) == local]
        if len(good) == 1:
            return good[0]
        return local - self.std

    def month_bounds(self, key):
        y, m = month_of_key(key)
        start = days_from_civil(y, m, 1) * EPOCH_DAY
        if m == 12:
            nxt = days_from_civil(y + 1, 1, 1) * EPOCH_DAY
        else:
            nxt = days_from_civil(y, m + 1, 1) * EPOCH_DAY
        return self.local_to_utc(start), self.local_to_utc(nxt)


# --------------------------------------------------------------------------
# geometry: rectangles are (f_lo, f_hi, t_lo, t_hi)
# --------------------------------------------------------------------------

def rect_area(r):
    return (r[1] - r[0]) * (r[3] - r[2])


def rect_clip(a, b):
    lo = a[0] if a[0] > b[0] else b[0]
    hi = a[1] if a[1] < b[1] else b[1]
    tlo = a[2] if a[2] > b[2] else b[2]
    thi = a[3] if a[3] < b[3] else b[3]
    if lo < hi and tlo < thi:
        return (lo, hi, tlo, thi)
    return None


def _span(segs):
    if not segs:
        return 0
    segs = sorted(segs)
    total = 0
    lo, hi = segs[0]
    for a, b in segs[1:]:
        if a > hi:
            total += hi - lo
            lo, hi = a, b
        elif b > hi:
            hi = b
    return total + hi - lo


def _union_small(rects):
    total = 0
    ts = sorted(set([r[2] for r in rects] + [r[3] for r in rects]))
    for i in range(len(ts) - 1):
        t0, t1 = ts[i], ts[i + 1]
        segs = [(r[0], r[1]) for r in rects if r[2] <= t0 and r[3] >= t1]
        total += _span(segs) * (t1 - t0)
    return total


class _FreqTree(object):
    """Segment tree over atomic frequency intervals with coverage counts."""

    def __init__(self, coords):
        self.coords = coords
        self.n = len(coords) - 1
        size = 1
        while size < max(self.n, 1):
            size *= 2
        self.size = size
        m = 2 * size
        self.cov = [0] * m
        self.m1 = [0] * m
        self.m2 = [0] * m

    def _pull(self, node, lo, hi):
        length = self.coords[hi + 1] - self.coords[lo]
        c = self.cov[node]
        l = 2 * node
        if c == 0:
            self.m1[node] = self.m1[l] + self.m1[l + 1]
            self.m2[node] = self.m2[l] + self.m2[l + 1]
        elif c == 1:
            below = self.m1[l] + self.m2[l] + self.m1[l + 1] + self.m2[l + 1]
            self.m1[node] = length - below
            self.m2[node] = below
        else:
            self.m1[node] = 0
            self.m2[node] = length

    def _leaf_pull(self, node, lo, hi):
        length = self.coords[hi + 1] - self.coords[lo]
        c = self.cov[node]
        if c == 0:
            self.m1[node] = 0
            self.m2[node] = 0
        elif c == 1:
            self.m1[node] = length
            self.m2[node] = 0
        else:
            self.m1[node] = 0
            self.m2[node] = length

    def update(self, qlo, qhi, delta):
        if qlo > qhi:
            return
        self._update(1, 0, self.n - 1, qlo, qhi, delta)

    def _update(self, node, lo, hi, qlo, qhi, delta):
        if qlo <= lo and hi <= qhi:
            self.cov[node] += delta
            if lo == hi:
                self._leaf_pull(node, lo, hi)
            else:
                self._pull(node, lo, hi)
            return
        mid = (lo + hi) // 2
        if qlo <= mid:
            self._update(2 * node, lo, mid, qlo, qhi, delta)
        if qhi > mid:
            self._update(2 * node + 1, mid + 1, hi, qlo, qhi, delta)
        if lo == hi:
            self._leaf_pull(node, lo, hi)
        else:
            self._pull(node, lo, hi)


def _sweep(rects):
    """(union, covered once, covered twice or more) of a rectangle set."""
    coords = sorted(set([r[0] for r in rects] + [r[1] for r in rects]))
    index = dict((v, i) for i, v in enumerate(coords))
    tree = _FreqTree(coords)
    events = defaultdict(list)
    for r in rects:
        events[r[2]].append((index[r[0]], index[r[1]] - 1, 1))
        events[r[3]].append((index[r[0]], index[r[1]] - 1, -1))
    times = sorted(events)
    union = excl = shared = 0
    for i, t in enumerate(times):
        for lo, hi, delta in events[t]:
            tree.update(lo, hi, delta)
        if i + 1 < len(times):
            dt = times[i + 1] - t
            union += (tree.m1[1] + tree.m2[1]) * dt
            excl += tree.m1[1] * dt
            shared += tree.m2[1] * dt
    return (union, excl, shared)


def sweep_measures(rects):
    """(union, exclusive, shared) of a rectangle set; exact integers."""
    rects = [r for r in rects if r[0] < r[1] and r[2] < r[3]]
    if not rects:
        return (0, 0, 0)
    return _sweep(rects)


def union_area(rects):
    rects = [r for r in rects if r[0] < r[1] and r[2] < r[3]]
    if not rects:
        return 0
    if len(rects) <= 40:
        return _union_small(rects)
    return _sweep(rects)[0]


def subtract_rect(pieces, hole):
    """Subtract one rectangle from a list of disjoint rectangles."""
    out = []
    h_lo, h_hi, h_tlo, h_thi = hole
    for (lo, hi, tlo, thi) in pieces:
        if lo >= h_hi or hi <= h_lo or tlo >= h_thi or thi <= h_tlo:
            out.append((lo, hi, tlo, thi))
            continue
        fparts = []
        if lo < h_lo:
            fparts.append((lo, h_lo))
        fparts.append((h_lo if lo < h_lo else lo, h_hi if hi > h_hi else hi))
        if h_hi < hi:
            fparts.append((h_hi, hi))
        tparts = []
        if tlo < h_tlo:
            tparts.append((tlo, h_tlo))
        tparts.append((h_tlo if tlo < h_tlo else tlo, h_thi if thi > h_thi else thi))
        if h_thi < thi:
            tparts.append((h_thi, thi))
        for fa, fb in fparts:
            if fa >= fb:
                continue
            for ta, tb in tparts:
                if ta >= tb:
                    continue
                if fa >= h_lo and fb <= h_hi and ta >= h_tlo and tb <= h_thi:
                    continue
                out.append((fa, fb, ta, tb))
    return out


def reduce_extents(pieces):
    """Merge touching extents of one grant until nothing merges."""
    cur = sorted(set([p for p in pieces if p[0] < p[1] and p[2] < p[3]]))
    while True:
        changed = False
        by_time = defaultdict(list)
        for p in cur:
            by_time[(p[2], p[3])].append(p)
        nxt = []
        for key in sorted(by_time):
            group = sorted(by_time[key])
            merged = []
            for p in group:
                if merged and merged[-1][1] == p[0]:
                    merged[-1][1] = p[1]
                else:
                    merged.append([p[0], p[1]])
            for a, b in merged:
                nxt.append((a, b, key[0], key[1]))
        if len(nxt) != len(cur):
            changed = True
        cur = sorted(set(nxt))
        by_freq = defaultdict(list)
        for p in cur:
            by_freq[(p[0], p[1])].append(p)
        nxt = []
        for key in sorted(by_freq):
            group = sorted(by_freq[key], key=lambda p: p[2])
            merged = []
            for p in group:
                if merged and merged[-1][1] == p[2]:
                    merged[-1][1] = p[3]
                else:
                    merged.append([p[2], p[3]])
            for a, b in merged:
                nxt.append((key[0], key[1], a, b))
        if len(nxt) != len(cur):
            changed = True
        cur = sorted(set(nxt))
        if not changed:
            return cur


# --------------------------------------------------------------------------
# holder references
# --------------------------------------------------------------------------

def normalise_holder(text):
    s = ''.join(ch for ch in text.upper() if ch.isalnum())
    if s.startswith('HL'):
        s = s[2:]
    if len(s) > 6:
        s = s[-6:]
    if len(s) < 6:
        s = s.rjust(6, '0')
    return s


class AliasMap(object):
    """Redirection of canonical identifiers to a fixpoint."""

    def __init__(self, rows):
        self.target = {}
        for r in rows:
            self.target.setdefault(r['alias_id'], r['canonical_id'])
        self.cycles = []
        self.cache = {}
        done = set()
        for a in sorted(self.target):
            if a in done:
                continue
            chain = []
            visited = {}
            cur = a
            while cur is not None and cur not in visited and cur not in done:
                visited[cur] = len(chain)
                chain.append(cur)
                cur = self.target.get(cur)
            for member in chain:
                done.add(member)
            if cur is not None and cur in visited and self.target.get(cur) != cur:
                self.cycles.append(sorted(chain[visited[cur]:]))

    def resolve(self, canon):
        if canon in self.cache:
            return self.cache[canon]
        seen = []
        cur = canon
        steps = 0
        while True:
            nxt = self.target.get(cur)
            if nxt is None:
                res = cur
                break
            if nxt == cur:
                res = cur
                break
            if nxt in seen:
                i = seen.index(nxt)
                res = min(seen[i:])
                steps += 1
                break
            seen.append(cur)
            cur = nxt
            steps += 1
            if steps > 1000:
                res = cur
                break
        self.cache[canon] = (res, steps)
        return self.cache[canon]

    def depth(self, canon):
        return self.resolve(canon)[1]


# --------------------------------------------------------------------------
# corpus
# --------------------------------------------------------------------------

class Corpus(object):
    def __init__(self, corpus_dir):
        self.dir = corpus_dir
        self.files = {}
        self.declared = {}
        self.rows_read = {}
        self.rows_visible = {}
        self.rows_governing = defaultdict(int)
        self._load_index()
        self._load_manifest()
        self._load_config()
        self._load_units()
        self._load_reason_codes()
        self._load_band_plan()
        self._load_zone_rules()
        self._load_raster()
        self._load_holders()
        self._load_notices()
        self._load_guards()
        self._load_duty()
        self._load_grant_records()
        self.tiebreak = self.settle_tiebreak()
        self.count_reference_rows()

    def path(self, name):
        return os.path.join(self.dir, name)

    def text(self, name):
        with open(self.path(name)) as fh:
            return fh.read()

    def tables(self, name):
        return md_tables(self.text(name))

    # -- index and manifest ---------------------------------------------
    def _load_index(self):
        for row in self.tables('corpus_index.md')[0]:
            self.files[row['file']] = row['layer']
        self.record_files = sorted(self.files)

    def _load_manifest(self):
        for row in self.tables('source_manifest.md')[0]:
            self.declared[row['file']] = int(row['rows_declared'])

    def _load_config(self):
        cfg = parse_ini(self.path('measure_config.ini'))
        self.horizon_start = Stamp.parse_offset(cfg['horizon']['start'])
        self.horizon_end = Stamp.parse_offset(cfg['horizon']['end'])
        self.as_of = Stamp.parse_offset(cfg['horizon']['as_of'])
        self.share_total_bp = int(cfg['measure']['share_total_bp'])
        self.ppm_scale = int(cfg['measure']['ppm_scale'])
        self.rounding = cfg['measure']['rounding']
        self.shared_min = int(cfg['measure']['shared_multiplicity_min'])
        self.top_holders = int(cfg['limits']['top_holders'])
        self.top_excess = int(cfg['limits']['top_excess'])
        self.top_deficit = int(cfg['limits']['top_deficit'])
        self.visibility_rule = cfg['visibility']['rule']

    def _load_units(self):
        self.units = parse_ini(self.path('unit_declarations.ini'))

    def _load_reason_codes(self):
        tables = self.tables('reason_codes.md')
        self.reject_codes = [r['code'] for r in tables[0]]
        self.note_codes = [r['note'] for r in tables[1]]

    def _load_band_plan(self):
        self.bands = []
        for r in self.tables('band_plan.md')[0]:
            self.bands.append((r['band'], int(r['f_low_khz']), int(r['f_high_khz']), int(r['raster_khz'])))
        self.band_ids = [b[0] for b in self.bands]

    def _load_zone_rules(self):
        self.zone_params = {}
        for r in self.tables('zone_time_rules.md')[0]:
            self.zone_params[r['zone']] = (
                int(r['standard_offset_sec']), int(r['summer_offset_sec']),
                None if r['summer_from'] == 'none' else r['summer_from'],
                None if r['summer_to'] == 'none' else r['summer_to'])
        self.clock_keying = self._settle_clock_keying()
        self.clocks = {}
        for zone, p in self.zone_params.items():
            self.clocks[zone] = ZoneClock(p[0], p[1], p[2], p[3], self.clock_keying)

    def _register_marks(self):
        marks = defaultdict(list)
        want = self.units['zone_clock_marks'].get('authoritative_jurisdiction')
        for r in read_csv(self.path('zone_clock_marks.csv')):
            if r['jurisdiction'] != want:
                continue
            marks[r['zone']].append((Stamp.parse(r['utc_stamp']), Stamp.parse(r['local_stamp'])))
        return marks

    def _settle_clock_keying(self):
        """Published summer window bounds are local standard or utc readings."""
        marks = self._register_marks()
        score = {'local_standard': 0, 'utc': 0}
        for keying in ('local_standard', 'utc'):
            for zone, p in self.zone_params.items():
                std, summer = p[0], p[1]
                if not p[2] or not p[3] or summer == std:
                    continue
                obs = sorted(marks.get(zone, []))
                if not obs:
                    continue
                offs = [local - utc for utc, local in obs]
                if summer not in offs or std not in offs:
                    continue
                first_summer = min(u for (u, l) in obs if l - u == summer)
                back_std = min(u for (u, l) in obs if l - u == std and u > first_summer)
                window = ZoneClock(std, summer, p[2], p[3], keying).window
                if window[0] == first_summer:
                    score[keying] += 1
                if window[1] == back_std:
                    score[keying] += 1
        return 'local_standard' if score['local_standard'] >= score['utc'] else 'utc'

    # -- raster -----------------------------------------------------------
    def _load_raster(self):
        self.channels = []
        for r in read_csv(self.path('channel_raster.csv')):
            self.channels.append((int(r['f_low_khz']), int(r['f_high_khz']), r['status']))
        self.channels.sort()
        self.usable = [(c[0], c[1]) for c in self.channels if c[2] == 'usable']
        self.low_edges = set([c[0] for c in self.channels])
        self.high_edges = set([c[1] for c in self.channels])

    def bound_ok(self, freq, is_low):
        if is_low:
            return freq in self.low_edges
        return freq in self.high_edges

    def usable_runs(self, f_lo, f_hi):
        runs = []
        cur = None
        for lo, hi in self.usable:
            if hi <= f_lo:
                continue
            if lo >= f_hi:
                break
            a = lo if lo > f_lo else f_lo
            b = hi if hi < f_hi else f_hi
            if a >= b:
                continue
            if cur is not None and cur[1] == a:
                cur = (cur[0], b)
            else:
                if cur is not None:
                    runs.append(cur)
                cur = (a, b)
        if cur is not None:
            runs.append(cur)
        return runs

    # -- holders ----------------------------------------------------------
    def _load_holders(self):
        self.registry = defaultdict(list)
        for zone in ZONES:
            for r in read_csv(self.path('holder_registry_%s.csv' % zone.lower())):
                self.registry[r['canonical_id']].append((zone, r))
        self.alias = AliasMap(read_csv(self.path('holder_alias_map.csv')))
        self.status_rows = defaultdict(list)
        for r in read_csv(self.path('holder_status_history.csv')):
            self.status_rows[r['canonical_id']].append((Stamp.parse(r['status_from']), r['status']))

    def registry_row(self, canon, zone):
        """Holder registry conflicts: the latest as_of wins, then the row
        whose zone_of_record equals the grant zone, then the zone_of_record
        that sorts first."""
        rows = self.registry.get(canon)
        if not rows:
            return None
        latest = max([r['as_of'] for z, r in rows])
        cands = [(z, r) for z, r in rows if r['as_of'] == latest]
        match = [(z, r) for z, r in cands if z == zone]
        if match:
            cands = match
        cands = sorted(cands, key=lambda t: t[0])
        return cands[0]

    def registry_zone(self, canon):
        """Zone the holder is filed against: the latest as_of wins, then
        the zone name that sorts first."""
        rows = self.registry.get(canon)
        if not rows:
            return None
        latest = max([r['as_of'] for z, r in rows])
        cands = sorted([(z, r) for z, r in rows if r['as_of'] == latest], key=lambda t: t[0])
        return cands[0][0]

    def holder_status(self, canon, at):
        best = None
        for start, status in self.status_rows.get(canon, ()):
            if start <= at:
                if best is None or start > best[0] or (start == best[0] and status > best[1]):
                    best = (start, status)
        return best[1] if best else 'provisional'

    # -- notices -----------------------------------------------------------
    def _load_notices(self):
        self.notices = defaultdict(list)
        for r in read_csv(self.path('retraction_notices.csv')):
            self.notices[r['assignment_id']].append(r)

    def live_notice(self, aid):
        full = {}
        cancelled = set()
        for r in self.notices.get(aid, ()):
            if Stamp.parse_offset(r['recorded_at']) >= self.as_of:
                continue
            key = (r['assignment_id'], r['notice_date'])
            if r['scope'] == 'full':
                full[key] = r
            elif r['scope'] == 'withdrawn':
                cancelled.add(key)
        return any(k not in cancelled for k in full)

    # -- guards ------------------------------------------------------------
    def _load_guards(self):
        self.guard_rules = {}
        for zone in ZONES:
            rules = []
            for r in read_csv(self.path('guard_windows_%s.csv' % zone.lower())):
                if r['status'] == 'active':
                    rules.append(r)
            self.guard_rules[zone] = rules
        self.guard_exc = defaultdict(list)
        for r in read_csv(self.path('guard_exceptions.csv')):
            self.guard_exc[r['zone']].append(r)

    def _load_duty(self):
        self.duty = {}
        for seg in ('commercial', 'public'):
            self.duty[seg] = read_csv(self.path('duty_budget_%s.csv' % seg))

    # -- grant records -------------------------------------------------------
    def _load_grant_records(self):
        self.records = dict((layer, defaultdict(list)) for layer in GRANT_LAYERS)
        for name in self.record_files:
            if self.files[name] not in GRANT_LAYERS:
                self.rows_visible[name] = 0
                self.rows_governing[name] = 0
            layer = self.files[name]
            if layer not in GRANT_LAYERS:
                continue
            if name.endswith('.tsv'):
                rows = read_csv(self.path(name), delimiter='\t')
            elif name.endswith('.jsonl'):
                rows = read_jsonl(self.path(name))
            else:
                rows = read_csv(self.path(name))
            self.rows_read[name] = len(rows)
            zone = None
            if layer == 'office':
                zone = name.split('_')[3].capitalize()
            visible = 0
            for i, r in enumerate(rows):
                if layer == 'office':
                    rec = self.clocks[zone].local_to_utc(Stamp.parse(r['recorded_at_local']))
                else:
                    rec = Stamp.parse_offset(r['recorded_at'])
                if rec is None:
                    continue
                if rec < self.as_of:
                    visible += 1
                self.records[layer][r['assignment_id']].append((int(r['revision']), rec, i, name, r, zone))
            self.rows_visible[name] = visible

    def read_state_events(self):
        """Visible state events of every grant, in event order."""
        index = defaultdict(list)
        for zone in ZONES:
            name = 'state_events_%s.csv' % zone.lower()
            rows = read_csv(self.path(name))
            self.rows_read[name] = len(rows)
            for i, r in enumerate(rows):
                if Stamp.parse_offset(r['recorded_at']) >= self.as_of:
                    continue
                index[(zone, r['assignment_id'])].append(
                    (Stamp.parse_offset(r['event_ts']), r['event'], i))
        for key in index:
            index[key].sort(key=lambda e: (e[0], EVENT_ORDER.get(e[1], 9), e[2]))
        return index

    def settle_tiebreak(self):
        """The duplicate tiebreak, from the records the register published."""
        votes = {'earliest_recorded_at': 0, 'latest_recorded_at': 0}
        rows = read_csv(self.path('register_governing_flags.csv'))
        self.rows_read['register_governing_flags.csv'] = len(rows)
        for r in rows:
            if r['governing'] != 'true':
                continue
            layer = r['layer']
            if layer not in self.records:
                continue
            recs = [x for x in self.records[layer].get(r['assignment_id'], ())
                    if x[1] < self.as_of and x[0] == int(r['revision'])]
            if len(recs) < 2:
                continue
            chosen = Stamp.parse_offset(r['recorded_at'])
            if chosen == min(x[1] for x in recs):
                votes['earliest_recorded_at'] += 1
            if chosen == max(x[1] for x in recs):
                votes['latest_recorded_at'] += 1
        if votes['latest_recorded_at'] > votes['earliest_recorded_at']:
            return 'latest_recorded_at'
        return 'earliest_recorded_at'

    def count_reference_rows(self):
        for name in self.record_files:
            if name in self.rows_read:
                continue
            layer = self.files[name]
            if layer in GRANT_LAYERS:
                continue
            if name.endswith('.jsonl'):
                self.rows_read[name] = len(read_jsonl(self.path(name)))
            else:
                delim = '\t' if name.endswith('.tsv') else ','
                self.rows_read[name] = len(read_csv(self.path(name), delimiter=delim))


EVENT_ORDER = {'terminate': 0, 'suspend': 1, 'restore': 2, 'activate': 3}

# --------------------------------------------------------------------------
# the register
# --------------------------------------------------------------------------

class Grant(object):
    __slots__ = ('aid', 'zone', 'holder', 'holder_ref', 'segment', 'parent', 'layers',
                 'notes', 'reject', 'extents', 'own', 'pieces', 'pre_pieces', 'post_guard', 'alias_steps',
                 'registry_zone', 'withdrawn', 'freq_runs', 'freq_lo', 'freq_hi',
                 'eff_start', 'eff_end', 'anomalies', 'registry_row')


def supplies(layer, rec):
    """Field groups a governing record carries values for."""
    if rec is None:
        return set()
    r = rec[4]
    if layer == 'coord' and r.get('action') == NOTE_RECORD_ACTION:
        return set()
    out = set()
    if layer == 'core':
        if r.get('holder_ref'):
            out.add('identity')
        if r.get('effective_from'):
            out.add('time')
        if r.get('f_low_khz'):
            out.add('frequency')
    elif layer == 'office':
        if r.get('holder_label'):
            out.add('identity')
        if r.get('effective_from_local'):
            out.add('time')
        if r.get('f_low_hz'):
            out.add('frequency')
    else:
        if r.get('holder_ref') is not None:
            out.add('identity')
        if r.get('effective_from') is not None:
            out.add('time')
        if r.get('f_low_khz') is not None:
            out.add('frequency')
    return out


def identity_values(layer, rec):
    r = rec[4]
    if layer == 'core':
        return r['zone'], r['holder_ref'], r['parent_id']
    if layer == 'coord':
        return r.get('zone'), r.get('holder_ref') or '', r.get('parent_id') or ''
    return rec[5], r['holder_label'], ''


def time_values(layer, rec, clock):
    """(start, end, deferred) of a time record, in utc seconds."""
    r = rec[4]
    deferred = False
    if layer == 'core':
        start = Stamp.parse_offset(r['effective_from'])
        end = Stamp.parse_offset(r['effective_to']) if r['effective_to'] else None
    elif layer == 'coord':
        start = Stamp.parse_offset(r['effective_from'])
        if r.get('effective_to') is None:
            deferred = True
            end = None
        else:
            end = Stamp.parse_offset(r['effective_to'])
    else:
        start = clock.local_to_utc(Stamp.parse(r['effective_from_local']))
        end = clock.local_to_utc(Stamp.parse(r['effective_to_local'])) if r['effective_to_local'] else None
    return start, end, deferred


def frequency_values(corpus, layer, rec):
    """(f_low, f_high, width) in kilohertz, or None when not exact."""
    r = rec[4]
    if layer == 'core':
        f_low = to_int(r['f_low_khz'])
        explicit = to_int(r['f_high_khz']) if r['f_high_khz'] else None
        width = to_int(r['bandwidth_khz']) if r['bandwidth_khz'] else None
    elif layer == 'office':
        f_low_hz = to_int(r['f_low_hz'])
        width_hz = to_int(r['bandwidth_hz'])
        if f_low_hz is None or width_hz is None:
            return None
        if f_low_hz % 1000 or width_hz % 1000:
            return None
        f_low, width, explicit = f_low_hz // 1000, width_hz // 1000, None
    else:
        token = r.get('bandwidth_unit')
        accepted = [t.strip() for t in corpus.units['coordination_decisions']['accepted_unit_tokens'].split(',')]
        if token is None or token not in accepted:
            return None
        f_low = to_int(r.get('f_low_khz'))
        width = to_int(r.get('bandwidth'))
        explicit = to_int(r.get('f_high_khz')) if r.get('f_high_khz') is not None else None
        if f_low is None or width is None:
            return None
        if token.strip().lower() == 'hz':
            if width % 1000:
                return None
            width = width // 1000
    if f_low is None:
        return None
    if explicit is not None:
        return (f_low, explicit, width)
    if width is None:
        return None
    return (f_low, f_low + width, width)


def settle_exception(obs, info):
    """The promoted layer for one segment and one field group, from the sample."""
    cache = {}
    for aid, (g, recs, sup, row) in info.items():
        cache[aid] = (recs, sup, g.segment)
    best = None
    for seg in ('commercial', 'public'):
        for group in ('time', 'frequency'):
            for layer in GRANT_LAYERS:
                if layer == PUBLISHED_RANK[0]:
                    continue
                bad = 0
                for o in obs:
                    entry = cache.get(o['assignment_id'])
                    if entry is None or o['field_group'] != group:
                        continue
                    recs, sup, segment = entry
                    if segment == seg:
                        rank = [layer] + [l for l in PUBLISHED_RANK if l != layer]
                    else:
                        rank = PUBLISHED_RANK
                    chosen = None
                    for l in rank:
                        if recs[l] is not None and group in sup[l]:
                            chosen = l
                            break
                    if chosen != o['layer_followed']:
                        bad += 1
                cand = (bad, seg, group, layer)
                if best is None or cand < best:
                    best = cand
    bad, seg, group, layer = best
    return {'segment': seg, 'field_group': group, 'layer': layer, 'mismatch': bad}


def active_intervals(events, start, end):
    """Intervals in which a grant is active, and the ignored restore anomalies."""
    ivs = []
    state = 'active'
    cur = start
    anomalies = 0
    for (ts, ev, idx) in events:
        if ts >= end:
            break
        t = ts if ts > start else start
        prev = state
        if state == 'terminated':
            pass
        elif ev == 'activate':
            pass
        elif ev == 'suspend':
            if state == 'active':
                state = 'suspended'
        elif ev == 'restore':
            if state == 'suspended':
                state = 'active'
            else:
                anomalies += 1
        elif ev == 'terminate':
            state = 'terminated'
        if prev == 'active' and state != 'active':
            ivs.append((cur, t))
        elif prev != 'active' and state == 'active':
            cur = t
    if state == 'active':
        ivs.append((cur, end))
    return [(a, b) for (a, b) in ivs if a < b], anomalies


def guard_rects(corpus, zone):
    """Reservation occurrences of a zone: expansion, horizon trim, exceptions."""
    clock = corpus.clocks[zone]
    occ = {}
    count_raw = 0
    for rule in corpus.guard_rules.get(zone, ()):
        vf = Stamp.parse(rule['valid_from'])
        vt = Stamp.parse(rule['valid_to'])
        start_local = parse_clock(rule['local_start'])
        dur = int(rule['duration_min']) * 60
        f_lo = int(rule['f_lo_khz'])
        f_hi = int(rule['f_hi_khz'])
        rec = rule['recurrence']
        d = vf - (vf % EPOCH_DAY)
        while d < vt:
            y, m, dd = civil_from_days(d // EPOCH_DAY)
            if rec == 'daily':
                ok = True
            elif rec.startswith('weekly:'):
                ok = ((d // EPOCH_DAY + 3) % 7 + 1) == int(rec.split(':')[1])
            elif rec.startswith('monthly:'):
                ok = dd == int(rec.split(':')[1])
            else:
                ok = False
            if ok:
                s = clock.local_to_utc(d + start_local)
                lo = s if s > corpus.horizon_start else corpus.horizon_start
                hi = min(s + dur, corpus.horizon_end)
                if lo < hi:
                    occ.setdefault((rule['rule_id'], d), []).append((f_lo, f_hi, lo, hi))
                    count_raw += 1
            d += EPOCH_DAY
    cancelled = 0
    for r in corpus.guard_exc.get(zone, ()):
        if r['kind'] != 'cancel':
            continue
        key = (r['rule_id'], Stamp.parse(r['occurrence_date']))
        if key in occ:
            cancelled += len(occ.pop(key))
    added = 0
    rule_by_id = dict((r['rule_id'], r) for r in corpus.guard_rules.get(zone, ()))
    for r in corpus.guard_exc.get(zone, ()):
        if r['kind'] != 'add':
            continue
        rule = rule_by_id.get(r['rule_id'])
        if rule is None:
            continue
        d = Stamp.parse(r['occurrence_date'])
        s = clock.local_to_utc(d + parse_clock(r['local_start']))
        lo = s if s > corpus.horizon_start else corpus.horizon_start
        hi = min(s + int(r['duration_min']) * 60, corpus.horizon_end)
        if lo >= hi:
            continue
        occ.setdefault((r['rule_id'], d), []).append((int(rule['f_lo_khz']), int(rule['f_hi_khz']), lo, hi))
        added += 1
    rects = []
    for key in sorted(occ):
        rects.extend(occ[key])
    return {'occurrences': len(rects), 'rects': rects, 'cancelled': cancelled,
            'added': added, 'no_exceptions': count_raw}


def build_register(corpus):
    """Every grant of the register with its groups, faults, notes and extents."""
    gov = {}
    pick = (lambda x: x[1]) if corpus.tiebreak == 'earliest_recorded_at' else (lambda x: -x[1])
    for layer in GRANT_LAYERS:
        for aid, recs in corpus.records[layer].items():
            vis = [x for x in recs if x[1] < corpus.as_of]
            if not vis:
                continue
            top = max(x[0] for x in vis)
            tied = [x for x in vis if x[0] == top]
            best = min(tied, key=lambda x: (pick(x), x[2], x[3]))
            gov[(layer, aid)] = best
            corpus.rows_governing[best[3]] += 1

    order = sorted(set([aid for layer in GRANT_LAYERS for aid in corpus.records[layer]]))
    info = {}
    for aid in order:
        recs = {}
        sup = {}
        for layer in GRANT_LAYERS:
            recs[layer] = gov.get((layer, aid))
            sup[layer] = supplies(layer, recs[layer])
        g = Grant()
        g.aid = aid
        g.notes = set()
        g.reject = None
        g.extents = []
        g.own = 0
        g.pieces = []
        g.pre_pieces = []
        g.post_guard = []
        g.alias_steps = 0
        g.withdrawn = False
        g.anomalies = 0
        g.freq_runs = None
        g.freq_lo = g.freq_hi = None
        g.eff_start = g.eff_end = None
        g.layers = {}
        idl = None
        for layer in PUBLISHED_RANK:
            if 'identity' in sup[layer]:
                idl = layer
                break
        g.layers['identity'] = idl
        if idl is None:
            g.zone = g.holder = g.holder_ref = g.segment = g.parent = None
            g.registry_row = None
            g.registry_zone = None
            info[aid] = (g, recs, sup, None)
            continue
        zone, href, parent = identity_values(idl, recs[idl])
        g.zone = zone
        g.holder_ref = href
        g.parent = parent if parent else None
        canon, steps = corpus.alias.resolve(normalise_holder(href))
        g.holder = canon
        g.alias_steps = steps
        row = corpus.registry_row(canon, zone)
        g.registry_row = row
        g.registry_zone = row[0] if row else None
        g.segment = row[1]['holder_class'] if row else None
        info[aid] = (g, recs, sup, row)

    obs = read_csv(corpus.path('precedence_observations.csv'))
    corpus.rows_read['precedence_observations.csv'] = len(obs)
    exception = settle_exception(obs, info)

    for aid in order:
        g, recs, sup, row = info[aid]
        for group in FIELD_GROUPS:
            if group == 'identity':
                rank = PUBLISHED_RANK
            elif g.segment == exception['segment'] and group == exception['field_group']:
                rank = [exception['layer']] + [l for l in PUBLISHED_RANK if l != exception['layer']]
            else:
                rank = PUBLISHED_RANK
            chosen = None
            for layer in rank:
                if recs[layer] is not None and group in sup[layer]:
                    chosen = layer
                    break
            g.layers[group] = chosen

    for aid in order:
        g, recs, sup, row = info[aid]
        idl = g.layers['identity']
        act = recs[idl][4].get('action') if idl is not None else None
        if act == RETRACT_ACTION or corpus.live_notice(aid):
            g.withdrawn = True

    ev_index = corpus.read_state_events()

    reject_of = {}

    def chain_cycle(aid):
        seen = [aid]
        cur = aid
        while True:
            entry = info.get(cur)
            if entry is None:
                return False
            p = entry[0].parent
            if not p:
                return False
            if p in seen:
                return True
            seen.append(p)
            cur = p

    def test_grant(aid, stack):
        if aid in reject_of:
            return reject_of[aid]
        g, recs, sup, row = info[aid]
        if g.withdrawn:
            reject_of[aid] = None
            return None
        clock = corpus.clocks.get(g.zone)
        tl = g.layers['time']
        if tl is None:
            reject_of[aid] = 'TERM_MISSING'
            return 'TERM_MISSING'
        start, end, deferred = time_values(tl, recs[tl], clock)
        if deferred:
            reject_of[aid] = 'TERM_MISSING'
            return 'TERM_MISSING'
        if end is None:
            end = corpus.horizon_end
        if end < start:
            reject_of[aid] = 'SPAN_INVERTED'
            return 'SPAN_INVERTED'
        fl = g.layers['frequency']
        if fl is None:
            reject_of[aid] = 'UNIT_AMBIGUOUS'
            return 'UNIT_AMBIGUOUS'
        freq = frequency_values(corpus, fl, recs[fl])
        if freq is None:
            reject_of[aid] = 'UNIT_AMBIGUOUS'
            return 'UNIT_AMBIGUOUS'
        f_lo, f_hi, width = freq
        runs = corpus.usable_runs(f_lo, f_hi)
        if not runs:
            reject_of[aid] = 'BAND_OUTSIDE'
            return 'BAND_OUTSIDE'
        if not corpus.bound_ok(f_lo, True) or not corpus.bound_ok(f_hi, False):
            reject_of[aid] = 'RASTER_MISALIGNED'
            return 'RASTER_MISALIGNED'
        if row is None:
            reject_of[aid] = 'HOLDER_UNKNOWN'
            return 'HOLDER_UNKNOWN'
        status = corpus.holder_status(g.holder, start)
        if g.registry_zone != g.zone and status == 'provisional':
            reject_of[aid] = 'ZONE_MISMATCH'
            return 'ZONE_MISMATCH'
        parent = g.parent
        if parent:
            pentry = info.get(parent)
            if pentry is None or pentry[0].zone != g.zone:
                reject_of[aid] = 'PARENT_UNKNOWN'
                return 'PARENT_UNKNOWN'
            if chain_cycle(aid):
                reject_of[aid] = 'PARENT_CYCLE'
                return 'PARENT_CYCLE'
            if parent in stack:
                reject_of[aid] = 'PARENT_RETRACTED'
                return 'PARENT_RETRACTED'
            pcode = test_grant(parent, stack | set([aid]))
            if info[parent][0].withdrawn or pcode is not None:
                reject_of[aid] = 'PARENT_RETRACTED'
                return 'PARENT_RETRACTED'
        reject_of[aid] = None
        return None

    for aid in order:
        test_grant(aid, set([aid]))

    guards = dict((z, guard_rects(corpus, z)) for z in ZONES)
    for aid in order:
        g, recs, sup, row = info[aid]
        g.reject = reject_of.get(aid)
        if g.withdrawn:
            continue
        if g.reject is not None:
            continue
        clock = corpus.clocks.get(g.zone)
        tl = g.layers['time']
        start, end, deferred = time_values(tl, recs[tl], clock)
        fl = g.layers['frequency']
        f_lo, f_hi, width = frequency_values(corpus, fl, recs[fl])
        runs = corpus.usable_runs(f_lo, f_hi)
        if len(runs) > 1:
            g.notes.add('SPLIT_BY_RASTER')
        if runs and (runs[0][0] != f_lo or runs[-1][1] != f_hi):
            g.notes.add('CLIPPED_TO_BAND')
        if width is not None and f_hi - f_lo != width:
            g.notes.add('WIDTH_MISMATCH')
        g.freq_lo, g.freq_hi = f_lo, f_hi
        g.freq_runs = runs
        eff_end = corpus.horizon_end if end is None else end
        if end is None:
            g.notes.add('OPEN_ENDED')
        g.eff_start, g.eff_end = start, eff_end
        if start < corpus.horizon_start or eff_end > corpus.horizon_end:
            g.notes.add('CLIPPED_TO_HORIZON')
        if eff_end == start:
            g.notes.add('ZERO_SPAN')
        if g.reject is not None:
            continue
        if g.alias_steps > 0:
            g.notes.add('ALIAS_RESOLVED')
        if g.registry_zone != g.zone:
            g.notes.add('ZONE_OF_RECORD_DIFFERS')
        ivs, anomalies = active_intervals(ev_index.get((g.zone, aid), ()), start, eff_end)
        g.anomalies = anomalies
        if anomalies:
            g.notes.add('STATE_ANOMALY')
        pieces = []
        for (a, b) in runs:
            for (t0, t1) in ivs:
                lo = t0 if t0 > corpus.horizon_start else corpus.horizon_start
                hi = t1 if t1 < corpus.horizon_end else corpus.horizon_end
                if lo < hi:
                    pieces.append((a, b, lo, hi))
        g.pre_pieces = pieces
        for hole in guards[g.zone]['rects']:
            if not pieces:
                break
            pieces = subtract_rect(pieces, hole)
        g.pieces = pieces
        g.post_guard = pieces

    done = set()

    def finish(aid, stack):
        if aid in done:
            return
        g, recs, sup, row = info[aid]
        if g.withdrawn or g.reject is not None:
            g.extents = []
            done.add(aid)
            return
        if g.parent and g.parent not in stack:
            finish(g.parent, stack | set([aid]))
        pieces = g.pieces
        if g.parent:
            parent = info[g.parent][0]
            clipped = []
            for p in pieces:
                for q in parent.extents:
                    c = rect_clip(p, q)
                    if c is not None:
                        clipped.append(c)
            pieces = clipped
        g.extents = reduce_extents(pieces)
        g.own = sum([rect_area(r) for r in g.extents])
        done.add(aid)

    for aid in order:
        finish(aid, set([aid]))
    return info, order, exception, guards, ev_index


def month_list(corpus, zone):
    """Local calendar months of a zone that meet the horizon."""
    clock = corpus.clocks[zone]
    out = []
    lo_local = clock.utc_to_local(corpus.horizon_start)
    hi_local = clock.utc_to_local(corpus.horizon_end - 1)
    sy, sm, _ = civil_from_days(lo_local // EPOCH_DAY)
    ey, em, _ = civil_from_days(hi_local // EPOCH_DAY)
    y, m = sy, sm
    while (y, m) <= (ey, em):
        lo, hi = clock.month_bounds(month_key(y, m))
        if lo < corpus.horizon_end and hi > corpus.horizon_start:
            out.append(month_key(y, m))
        if m == 12:
            y, m = y + 1, 1
        else:
            m += 1
    return out


def clip_time(r, lo, hi):
    t0 = r[2] if r[2] > lo else lo
    t1 = r[3] if r[3] < hi else hi
    if t0 < t1:
        return (r[0], r[1], t0, t1)
    return None


def clip_freq(r, blo, bhi):
    a = r[0] if r[0] > blo else blo
    b = r[1] if r[1] < bhi else bhi
    if a < b:
        return (a, b, r[2], r[3])
    return None


def charge_excess(info, measurable):
    """Charge every overlapping cell to all but its best ranked covering grant."""
    by_zone = defaultdict(list)
    for aid in measurable:
        by_zone[info[aid][0].zone].append(aid)
    charges = defaultdict(int)
    bucket = 30 * EPOCH_DAY
    for zone in ZONES:
        ranked = sorted(by_zone.get(zone, ()), key=lambda a: (-info[a][0].own, a))
        claimed = defaultdict(list)
        for aid in ranked:
            g = info[aid][0]
            hit = 0
            for e in g.extents:
                seen = set()
                cand = []
                for blk in range(e[2] // bucket, e[3] // bucket + 1):
                    for (r, i) in claimed.get(blk, ()):
                        if r not in seen:
                            seen.add(r)
                            cand.append(r)
                clipped = []
                for r in cand:
                    c = rect_clip(e, r)
                    if c is not None:
                        clipped.append(c)
                hit += union_area(clipped)
            charges[aid] = hit
            for e in g.extents:
                for blk in range(e[2] // bucket, e[3] // bucket + 1):
                    claimed[blk].append((e, aid))
    return charges


def duty_audit(corpus, info, order, ev_index):
    """Duty budget audit over the local months of every audited holder."""
    grants_by_holder = defaultdict(list)
    for aid in order:
        g = info[aid][0]
        if g.reject is None and not g.withdrawn and g.extents:
            grants_by_holder[(g.holder, g.zone)].append(aid)
    susp = defaultdict(list)
    for (zone, aid), evs in ev_index.items():
        entry = info.get(aid)
        if entry is None:
            continue
        holder = entry[0].holder
        for (ts, ev, idx) in evs:
            if ev == 'suspend':
                susp[holder].append(ts)
    per_seg = {}
    holders_audited = 0
    months_in_deficit = 0
    total_allow = 0
    total_consumed = 0
    carry_total = 0
    resets = 0
    deficits = []
    for seg in ('commercial', 'public'):
        rows = corpus.duty[seg]
        by_holder = defaultdict(dict)
        for r in rows:
            by_holder[r['canonical_id']][r['month']] = r
        seg_carry = 0
        seg_def = 0
        for holder in sorted(by_holder):
            zone = corpus.registry_zone(holder)
            if zone is None or zone not in corpus.clocks:
                continue
            clock = corpus.clocks[zone]
            months = []
            for key in sorted(by_holder[holder]):
                lo, hi = clock.month_bounds(key)
                if lo < corpus.horizon_end and hi > corpus.horizon_start:
                    months.append(key)
            if not months:
                continue
            holders_audited += 1
            carry = 0
            last = 0
            for key in months:
                lo, hi = clock.month_bounds(key)
                occupancy = 0
                for zone in ZONES:
                    rects = []
                    for aid in grants_by_holder.get((holder, zone), ()):
                        for r in info[aid][0].extents:
                            c = clip_time(r, lo, hi)
                            if c is not None:
                                rects.append(c)
                    occupancy += union_area(rects)
                row = by_holder[holder][key]
                allow = to_int(row['allowance_khz_s'])
                if row.get('notes') == 'unit=khz_min':
                    allow = allow * 60
                available = allow + carry
                consumed = available if available < occupancy else occupancy
                deficit = occupancy - available if occupancy > available else 0
                out = available - occupancy if available > occupancy else 0
                if any(lo <= t < hi for t in susp.get(holder, ())):
                    if out > 0:
                        resets += 1
                    out = 0
                if deficit > 0:
                    months_in_deficit += 1
                    seg_def += 1
                    deficits.append((holder, key, deficit))
                total_allow += allow
                total_consumed += consumed
                carry = out
                last = out
            seg_carry += last
        carry_total += seg_carry
        per_seg[seg] = {'carry_end': seg_carry, 'deficit_months': seg_def}
    deficits.sort(key=lambda t: (-t[2], t[0], t[1]))
    top = [[h, k, d] for (h, k, d) in deficits[:corpus.top_deficit]]
    return {
        'per_segment': per_seg,
        'holders_audited': holders_audited,
        'months_in_deficit': months_in_deficit,
        'total_allowance': total_allow,
        'total_consumed': total_consumed,
        'carry_forward_end': carry_total,
        'carry_resets': resets,
        'top_deficit': top,
    }


def measure(corpus, info, order, guards, ev_index):
    """Every published figure of the measurement."""
    ok = [aid for aid in order if info[aid][0].reject is None and not info[aid][0].withdrawn]
    measurable = [aid for aid in ok if info[aid][0].extents]

    zone_rects = dict((z, []) for z in ZONES)
    zone_pre = dict((z, []) for z in ZONES)
    zone_post = dict((z, []) for z in ZONES)
    for aid in ok:
        g = info[aid][0]
        if g.pre_pieces:
            zone_pre[g.zone].extend(g.pre_pieces)
            zone_post[g.zone].extend(g.post_guard)
    for aid in measurable:
        zone_rects[info[aid][0].zone].extend(info[aid][0].extents)

    zone_union = {}
    zone_excl = {}
    zone_shared = {}
    zone_month = {}
    zone_band = {}
    zone_sub = {}
    for zone in ZONES:
        u, e, s = sweep_measures(zone_rects[zone])
        zone_union[zone], zone_excl[zone], zone_shared[zone] = u, e, s
        mm = {}
        for key in month_list(corpus, zone):
            lo, hi = corpus.clocks[zone].month_bounds(key)
            rects = []
            for r in zone_rects[zone]:
                c = clip_time(r, lo, hi)
                if c is not None:
                    rects.append(c)
            mm[key] = union_area(rects)
        zone_month[zone] = mm
        bb = {}
        for bid, blo, bhi, raster in corpus.bands:
            rects = []
            for r in zone_rects[zone]:
                c = clip_freq(r, blo, bhi)
                if c is not None:
                    rects.append(c)
            bb[bid] = union_area(rects)
        zone_band[zone] = bb
        zone_sub[zone] = union_area(zone_pre[zone]) - union_area(zone_post[zone])

    total_union = sum(zone_union.values())
    total_excl = sum(zone_excl.values())
    total_shared = sum(zone_shared.values())
    total_assigned = sum([info[aid][0].own for aid in measurable])

    charges = charge_excess(info, measurable)
    charge_total = sum(charges.values())

    seg = {}
    for name in ('commercial', 'public'):
        aids = [aid for aid in measurable if info[aid][0].segment == name]
        zz = {}
        u = e = sh = 0
        for zone in ZONES:
            rr = []
            for aid in aids:
                if info[aid][0].zone == zone:
                    rr.extend(info[aid][0].extents)
            zu, ze, zs = sweep_measures(rr)
            zz[zone] = zu
            u += zu
            e += ze
            sh += zs
        seg[name] = {'aids': aids, 'union': u, 'excl': e, 'shared': sh, 'zone': zz}

    holder_rects = defaultdict(list)
    for aid in measurable:
        g = info[aid][0]
        holder_rects[(g.holder, g.zone)].extend(g.extents)
    holder_union = defaultdict(int)
    for (h, zone), rects in holder_rects.items():
        holder_union[h] += union_area(rects)

    duty = duty_audit(corpus, info, order, ev_index)

    layer_wins = defaultdict(int)
    for aid in order:
        g = info[aid][0]
        if g.withdrawn:
            continue
        for group in FIELD_GROUPS:
            layer = g.layers[group]
            if layer is not None:
                layer_wins[layer] += 1

    refs = set()
    for layer in GRANT_LAYERS:
        for aid, recs in corpus.records[layer].items():
            for x in recs:
                href = holder_ref_of(layer, x)
                if href:
                    refs.add(normalise_holder(href))
    alias_depth = 0
    for canon in refs:
        d = corpus.alias.depth(canon)
        if d > alias_depth:
            alias_depth = d

    memo = {}

    def chain_len(aid):
        if aid in memo:
            return memo[aid]
        g = info[aid][0]
        n = chain_len(g.parent) + 1 if (g.parent and g.parent in info) else 1
        memo[aid] = n
        return n

    parent_depth = 0
    for aid in measurable:
        d = chain_len(aid)
        if d > parent_depth:
            parent_depth = d

    return {
        'ok': ok, 'measurable': measurable,
        'total_assigned': total_assigned, 'total_union': total_union,
        'total_excl': total_excl, 'total_shared': total_shared,
        'zone_union': zone_union, 'zone_excl': zone_excl, 'zone_shared': zone_shared,
        'zone_month': zone_month, 'zone_band': zone_band, 'zone_sub': zone_sub,
        'charges': charges, 'charge_total': charge_total,
        'seg': seg, 'holder_union': holder_union, 'duty': duty,
        'layer_wins': layer_wins, 'alias_depth': alias_depth,
        'parent_depth': parent_depth,
    }


def holder_ref_of(layer, rec):
    r = rec[4]
    if layer == 'office':
        return r.get('holder_label')
    return r.get('holder_ref')


def build_documents(corpus, info, order, exception, guards, m):
    ok = m['ok']
    measurable = m['measurable']
    retracted = [aid for aid in order if info[aid][0].withdrawn]
    zero_span = [aid for aid in ok if 'ZERO_SPAN' in info[aid][0].notes]

    rejects = defaultdict(int)
    for code in corpus.reject_codes:
        rejects[code] = 0
    for aid in order:
        g = info[aid][0]
        if g.reject is not None:
            rejects[g.reject] += 1
    notes = defaultdict(int)
    for code in corpus.note_codes:
        notes[code] = 0
    for aid in ok:
        for note in info[aid][0].notes:
            notes[note] += info[aid][0].anomalies if note == 'STATE_ANOMALY' else 1

    source_counts = {}
    for name in corpus.record_files:
        source_counts[name] = {
            'rows_read': corpus.rows_read.get(name, 0),
            'rows_visible': corpus.rows_visible.get(name, 0),
            'rows_governing': corpus.rows_governing.get(name, 0),
        }
    mismatches = sorted([name for name in corpus.record_files
                         if corpus.rows_read.get(name, 0) != corpus.declared.get(name)])
    rows_total = sum([corpus.rows_read.get(name, 0) for name in corpus.record_files])

    total_union = m['total_union']
    shared_ratio = round_half_even(m['total_shared'] * corpus.ppm_scale, total_union)
    zone_share = largest_remainder_shares(m['zone_union'], corpus.share_total_bp)
    seg_base = dict((s, m['seg'][s]['union']) for s in ('commercial', 'public'))
    seg_share = largest_remainder_shares(seg_base, corpus.share_total_bp)

    summary = {
        'horizon': {
            'start': Stamp.render(corpus.horizon_start),
            'end': Stamp.render(corpus.horizon_end),
            'as_of': Stamp.render(corpus.as_of),
        },
        'assignments_total': len(order),
        'assignments_measurable': len(measurable),
        'rectangles': sum([len(info[aid][0].extents) for aid in measurable]),
        'area_total_assigned': m['total_assigned'],
        'area_union': total_union,
        'area_exclusive': m['total_excl'],
        'area_shared': m['total_shared'],
        'area_excess': m['total_assigned'] - total_union,
        'excess_charge_total': m['charge_total'],
        'shared_ratio_ppm': shared_ratio,
        'zone_area_union': dict((z, m['zone_union'][z]) for z in ZONES),
        'zone_share_bp': zone_share,
        'segment_area_union': dict((s, m['seg'][s]['union']) for s in ('commercial', 'public')),
        'segment_share_bp': seg_share,
        'cross_segment_shared_area': sum(seg_base.values()) - total_union,
        'guard_subtracted_area': sum([m['zone_sub'][z] for z in ZONES]),
    }

    regions = {}
    for zone in ZONES:
        aids = [aid for aid in measurable if info[aid][0].zone == zone]
        assigned = sum([info[aid][0].own for aid in aids])
        union = m['zone_union'][zone]
        clock = corpus.clocks[zone]
        ranked = sorted([(m['charges'][aid], aid) for aid in aids if m['charges'][aid] > 0],
                        key=lambda t: (-t[0], t[1]))
        regions[zone] = {
            'zone': zone,
            'utc_offset_standard_sec': clock.std,
            'utc_offset_summer_sec': clock.summer,
            'summer_window_utc': [Stamp.render(clock.window[0]), Stamp.render(clock.window[1])] if clock.window else None,
            'assignments_measurable': len(aids),
            'rectangles': sum([len(info[aid][0].extents) for aid in aids]),
            'area_total_assigned': assigned,
            'area_union': union,
            'area_exclusive': m['zone_excl'][zone],
            'area_shared': m['zone_shared'][zone],
            'area_excess': assigned - union,
            'guard_occurrences': guards[zone]['occurrences'],
            'guard_subtracted_area': m['zone_sub'][zone],
            'excess_charge_top': [[aid, ch] for (ch, aid) in ranked[:corpus.top_excess]],
            'band_area_union': dict((b, m['zone_band'][zone][b]) for b in corpus.band_ids),
            'month_area_union': dict((k, m['zone_month'][zone][k]) for k in sorted(m['zone_month'][zone])),
        }

    segments = {}
    for name in ('commercial', 'public'):
        aids = m['seg'][name]['aids']
        holders = set([info[aid][0].holder for aid in aids])
        top = sorted([(m['holder_union'].get(h, 0), h) for h in holders],
                     key=lambda t: (-t[0], t[1]))[:corpus.top_holders]
        segments[name] = {
            'segment': name,
            'holders': len(holders),
            'assignments_measurable': len(aids),
            'area_union': m['seg'][name]['union'],
            'area_exclusive': m['seg'][name]['excl'],
            'area_shared': m['seg'][name]['shared'],
            'zone_area_union': dict((z, m['seg'][name]['zone'][z]) for z in ZONES),
            'top_holders': [[h, v] for (v, h) in top],
            'duty_deficit_months': m['duty']['per_segment'][name]['deficit_months'],
            'duty_carry_end': m['duty']['per_segment'][name]['carry_end'],
        }

    parent_rejects = dict((code, rejects[code]) for code in ('PARENT_UNKNOWN', 'PARENT_CYCLE', 'PARENT_RETRACTED'))
    audit = {
        'as_of': Stamp.render(corpus.as_of),
        'precedence_exception': {
            'segment': exception['segment'],
            'field_group': exception['field_group'],
            'layer': exception['layer'],
        },
        'duplicate_tiebreak': corpus.tiebreak,
        'clock_keying': corpus.clock_keying,
        'layer_governing_counts': dict((l, m['layer_wins'][l]) for l in GRANT_LAYERS),
        'alias_fixpoint_depth': m['alias_depth'],
        'alias_cycles': len(corpus.alias.cycles),
        'parent_chain_max_depth': m['parent_depth'],
        'parent_rejects': parent_rejects,
        'duty': {
            'holders_audited': m['duty']['holders_audited'],
            'months_in_deficit': m['duty']['months_in_deficit'],
            'total_allowance': m['duty']['total_allowance'],
            'total_consumed': m['duty']['total_consumed'],
            'carry_forward_end': m['duty']['carry_forward_end'],
            'carry_resets': m['duty']['carry_resets'],
            'top_deficit': m['duty']['top_deficit'],
        },
        'guard': {
            'occurrences': sum([guards[z]['occurrences'] for z in ZONES]),
            'cancelled': sum([guards[z]['cancelled'] for z in ZONES]),
            'added': sum([guards[z]['added'] for z in ZONES]),
            'subtracted_area': sum([m['zone_sub'][z] for z in ZONES]),
        },
    }

    quality = {
        'assignments_total': len(order),
        'rows_read_total': rows_total,
        'rejects': dict((c, rejects[c]) for c in corpus.reject_codes),
        'notes': dict((c, notes[c]) for c in corpus.note_codes),
        'retracted': len(retracted),
        'zero_span': len(zero_span),
        'manifest_mismatches': mismatches,
        'source_counts': source_counts,
    }
    return summary, regions, segments, audit, quality


def write_documents(out_dir, summary, regions, segments, audit, quality):
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    docs = {
        'summary.json': summary,
        'policy_audit.json': audit,
        'data_quality.json': quality,
    }
    for zone in ZONES:
        docs['region_%s.json' % zone] = regions[zone]
    for name in ('commercial', 'public'):
        docs['segment_%s.json' % name] = segments[name]
    for name, doc in docs.items():
        with open(os.path.join(out_dir, name), 'w') as fh:
            json.dump(doc, fh, sort_keys=True, indent=2)
            fh.write('\n')


def run(corpus_dir, out_dir):
    corpus = Corpus(corpus_dir)
    info, order, exception, guards, ev_index = build_register(corpus)
    m = measure(corpus, info, order, guards, ev_index)
    docs = build_documents(corpus, info, order, exception, guards, m)
    write_documents(out_dir, *docs)
    return docs


def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: derive_report.py <corpus_dir> <output_dir>\n')
        return 2
    corpus_dir = os.path.abspath(argv[1])
    out_dir = os.path.abspath(argv[2])
    run(corpus_dir, out_dir)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
