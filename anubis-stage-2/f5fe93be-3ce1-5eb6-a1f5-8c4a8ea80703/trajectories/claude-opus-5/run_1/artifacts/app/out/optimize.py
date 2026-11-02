#!/usr/bin/env python3
"""Halvard playout centre close: reconcile one channel week.

Usage: python3 optimize.py DATA_DIR WORKLOAD
"""
import bisect
import configparser
import csv
import datetime
import json
import os
import sys
from collections import defaultdict

TICKS = 30000               # ticks per second
EPOCH_ORD = datetime.date(1970, 1, 1).toordinal()
WEEKDAY_NAMES = ('MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU')
ASRUN_FIELDS = ('seq', 'date', 'tc', 'evt', 'spot', 'house', 'frames', 'status')
DISPOSITIONS = ('AIRED', 'OUT_OF_WINDOW', 'WRONG_COPY', 'PARTIAL',
                'PREEMPTED', 'MISSED', 'UNRESOLVED')
OCCUPYING = frozenset(('AIRED', 'OUT_OF_WINDOW', 'WRONG_COPY', 'UNRESOLVED'))

_DATE_CACHE = {}
_ISO_CACHE = {}


def days_of(iso):
    d = _DATE_CACHE.get(iso)
    if d is None:
        d = datetime.date(int(iso[0:4]), int(iso[5:7]), int(iso[8:10])).toordinal() - EPOCH_ORD
        _DATE_CACHE[iso] = d
    return d


def iso_of(days):
    s = _ISO_CACHE.get(days)
    if s is None:
        s = datetime.date.fromordinal(days + EPOCH_ORD).isoformat()
        _ISO_CACHE[days] = s
    return s


def weekday_of(days):
    return WEEKDAY_NAMES[(days + 3) % 7]


def utc_ticks(stamp):
    """`YYYY-MM-DDTHH:MM:SS[.mmm]Z` to ticks since the epoch."""
    days = days_of(stamp[0:10])
    h = int(stamp[11:13]); m = int(stamp[14:16]); s = int(stamp[17:19])
    ms = 0
    if len(stamp) > 20 and stamp[19] == '.':
        ms = int((stamp[20:].rstrip('Z') + '000')[:3])
    return ((days * 86400 + h * 3600 + m * 60 + s) * 1000 + ms) * 30


def open_file(path):
    return open(path, 'r', encoding='utf-8', newline='')


def hms_of(text):
    parts = text.split(':')
    h = int(parts[0])
    m = int(parts[1]) if len(parts) > 1 else 0
    s = int(parts[2]) if len(parts) > 2 else 0
    return (h, m, s)


# ---------------------------------------------------------------- channel ---

class Channel(object):
    def __init__(self, sec, zones, variant):
        self.name = sec.name
        self.channel = sec['channel'].strip()
        rate = sec['frame_rate'].strip()
        self.nominal = 25 if rate == '25' else 30
        self.frame_ticks = 1200 if self.nominal == 25 else 1001
        self.drop = sec['timecode'].strip() == 'drop'
        self.sep = ';' if self.drop else ':'
        self.flat = bool(variant.get('nondrop_math'))
        self.zone = sec['zone'].strip()
        self.transitions = zones[self.zone]
        self.week_start = days_of(sec['week_start'].strip())
        self.broadcast_days = int(sec['broadcast_days'])
        self.daypart_set = sec['daypart_set'].strip()
        self.tolerance = int(sec['sync_tolerance_frames'])
        self.DAY = self.bound_count('24:00:00')
        self.day_start = self.bound_count(sec['broadcast_day_start'].strip())
        self.dates = [self.week_start + i for i in range(self.broadcast_days)]
        self.date_set = frozenset(self.dates)

    def count(self, h, m, s, f):
        if self.drop and not self.flat:
            t = 60 * h + m
            return ((h * 60 + m) * 60 + s) * 30 + f - 2 * (t - t // 10)
        return ((h * 60 + m) * 60 + s) * self.nominal + f

    def bound_count(self, text):
        h, m, s = hms_of(text)
        return self.count(h, m, s, 0)

    def parse_label(self, tc):
        """Return (count, reason); reason is None when the label is good."""
        if len(tc) != 11 or tc[2] != ':' or tc[5] != ':' or tc[8] != self.sep:
            return None, 'BAD_TIMECODE'
        a, b, c, d = tc[0:2], tc[3:5], tc[6:8], tc[9:11]
        if not (a.isdigit() and b.isdigit() and c.isdigit() and d.isdigit()):
            return None, 'BAD_TIMECODE'
        h = int(a); m = int(b); s = int(c); f = int(d)
        if h > 23 or m > 59 or s > 59 or f >= self.nominal:
            return None, 'BAD_TIMECODE'
        if self.drop and s == 0 and f < 2 and m % 10:
            return None, 'DROPPED_LABEL'
        return self.count(h, m, s, f), None

    def utc_of(self, days, count):
        local = days * 86400 * TICKS + count * self.frame_ticks
        tr = self.transitions
        n = len(tr)
        for i in range(n):
            start, off = tr[i]
            utc = local - off * 60 * TICKS
            if utc >= start and (i + 1 == n or utc < tr[i + 1][0]):
                return utc
        for i in range(n - 1, -1, -1):
            if local >= tr[i][0]:
                return local - tr[i][1] * 60 * TICKS
        return local - tr[0][1] * 60 * TICKS

    def broadcast_of(self, index):
        """Absolute index to (broadcast date in days, broadcast clock count)."""
        day, cnt = divmod(index, self.DAY)
        if cnt < self.day_start:
            return day - 1, cnt + self.DAY
        return day, cnt


# ------------------------------------------------------------ prior close ---

STRADDLE_RULES = (
    lambda ex, comp, off, tol: ex and comp and off <= tol,
    lambda ex, comp, off, tol: ex and comp and off < tol,
    lambda ex, comp, off, tol: ex and off <= tol,
    lambda ex, comp, off, tol: ex and off < tol,
    lambda ex, comp, off, tol: ex and comp,
)

WINDOW_RULES = (
    lambda bc, e, ws, we: ws <= bc and bc + e <= we,
    lambda bc, e, ws, we: ws <= bc < we,
    lambda bc, e, ws, we: ws <= bc + e - 1 < we,
    lambda bc, e, ws, we: ws <= bc and bc + e < we,
)

TIE_DESKS = ('traffic', 'mcr', None)


def prior_close_settlements(path):
    """The three readings of the rules that the previous close settled."""
    straddle_recs = []
    window_recs = []
    tie_recs = []
    with open_file(path) as fh:
        for line in fh:
            if not line.strip():
                continue
            rec = json.loads(line)
            kind = rec.get('kind')
            if kind == 'failover_straddle':
                straddle_recs.append(rec)
            elif kind == 'window_edge':
                window_recs.append(rec)
            elif kind == 'correction_tie':
                tie_recs.append(rec)

    def label_count(tc, drop):
        h = int(tc[0:2]); m = int(tc[3:5]); s = int(tc[6:8]); f = int(tc[9:11])
        if drop:
            t = 60 * h + m
            return ((h * 60 + m) * 60 + s) * 30 + f - 2 * (t - t // 10)
        return ((h * 60 + m) * 60 + s) * 25 + f

    def bound_count(text, drop):
        h, m = (int(x) for x in text.split(':'))
        if drop:
            t = 60 * h + m
            return ((h * 60 + m) * 60) * 30 - 2 * (t - t // 10)
        return ((h * 60 + m) * 60) * 25

    straddle_cases = []
    for rec in straddle_recs:
        drop = rec['rate'] != '25'
        other = rec.get('other_start_tc')
        exists = other is not None
        off = (abs(label_count(other, drop) - label_count(rec['on_air_start_tc'], drop))
               if exists else 0)
        straddle_cases.append((exists, bool(rec.get('other_complete')), off,
                               rec['tolerance_frames'], rec['outcome'] == 'aired'))

    window_cases = []
    for rec in window_recs:
        drop = rec['rate'] != '25'
        bc = label_count(rec['start_tc'], drop)
        if rec.get('after_local_midnight'):
            bc += bound_count('24:00', drop)
        lo, hi = rec['window'].split('-')
        window_cases.append((bc, rec['frames'], bound_count(lo, drop),
                             bound_count(hi, drop), rec['outcome'] == 'in_window'))

    straddle_rule = STRADDLE_RULES[0]
    for rule in STRADDLE_RULES:
        if all(bool(rule(ex, cp, of, tl)) == out for ex, cp, of, tl, out in straddle_cases):
            straddle_rule = rule
            break

    window_rule = WINDOW_RULES[0]
    for rule in WINDOW_RULES:
        if all(bool(rule(bc, e, ws, we)) == out for bc, e, ws, we, out in window_cases):
            window_rule = rule
            break

    tie_desk = TIE_DESKS[0]
    for desk in TIE_DESKS:
        good = True
        for rec in tie_recs:
            versions = rec['versions']
            top_rev = max(v['rev'] for v in versions)
            top = [v for v in versions if v['rev'] == top_rev]
            best = max(top, key=lambda v: (1 if (desk and v['desk'] == desk) else 0,
                                           v['recorded_at'], v.get('order_line') or ''))
            if best['order_line'] != rec['outcome_order_line']:
                good = False
                break
        if good:
            tie_desk = desk
            break

    return straddle_rule, window_rule, tie_desk


# ------------------------------------------------------------ shared load ---

def normalize_house(raw):
    s = raw.strip().upper().replace(' ', '').replace('-', '')
    if len(s) < 4 or len(s) > 8:
        return None
    head = s[0:3]
    digits = s[3:]
    if not (head.isascii() and head.isalpha() and digits.isascii() and digits.isdigit()):
        return None
    return head + '-' + digits.zfill(5)


class Corpus(object):
    """Everything in the data directory that is not per workload."""

    def __init__(self, data_dir, variant):
        self.dir = data_dir
        self.variant = variant
        with open_file(os.path.join(data_dir, 'channels.ini')) as fh:
            cfg = configparser.ConfigParser()
            cfg.read_file(fh)
        self.cfg = cfg
        with open_file(os.path.join(data_dir, 'utc_offsets.json')) as fh:
            zones_raw = json.load(fh)['zones']
        self.zones = {}
        for name, items in zones_raw.items():
            self.zones[name] = sorted((utc_ticks(it['from_utc']), it['offset_minutes'])
                                      for it in items)
        with open_file(os.path.join(data_dir, 'dayparts.json')) as fh:
            self.daypart_sets = json.load(fh)['sets']
        with open_file(os.path.join(data_dir, 'holidays.json')) as fh:
            self.blackouts = json.load(fh)['blackout_broadcast_dates']
        with open_file(os.path.join(data_dir, 'close_policy.json')) as fh:
            self.policy = json.load(fh)
        with open_file(os.path.join(data_dir, 'advertisers.json')) as fh:
            self.advertisers = json.load(fh)['advertisers']

        self.registry = {}
        with open_file(os.path.join(data_dir, 'copy_registry.csv')) as fh:
            for row in csv.DictReader(fh):
                self.registry[row['house_id']] = (int(row['master_rate']), int(row['frames']))

        self.aliases = {}
        with open_file(os.path.join(data_dir, 'house_aliases.csv')) as fh:
            for row in csv.DictReader(fh):
                old = normalize_house(row['old_house_id'])
                if old is not None:
                    self.aliases[old] = (normalize_house(row['new_house_id']),
                                         days_of(row['effective_from']))

        self.orders = {}
        self.orders_by_workload = defaultdict(list)
        with open_file(os.path.join(data_dir, 'orders.csv')) as fh:
            for row in csv.DictReader(fh):
                info = {
                    'order_line': row['order_line'],
                    'workload': row['workload'],
                    'advertiser': row['advertiser'],
                    'daypart': row['daypart'],
                    'weekdays': frozenset(row['weekdays'].split()),
                    'spots_per_day': int(row['spots_per_day']),
                    'flight_start': days_of(row['flight_start']),
                    'flight_end': days_of(row['flight_end']),
                    'unit_rate_cents': int(row['unit_rate_cents']),
                    'priority': int(row['priority']),
                    'house_id': row['house_id'],
                }
                self.orders[row['order_line']] = info
                self.orders_by_workload[row['workload']].append(info)

        self.amendments = defaultdict(list)
        with open_file(os.path.join(data_dir, 'order_amendments.jsonl')) as fh:
            for line in fh:
                if not line.strip():
                    continue
                rec = json.loads(line)
                self.amendments[rec['order_line']].append(rec)

        self.straddle_rule, self.window_rule, self.tie_desk = prior_close_settlements(
            os.path.join(data_dir, 'prior_close_decisions.jsonl'))

        self.resolve_cache = {}

    def resolve(self, raw, date_days, undated):
        """Return (registry id or None, whether an alias row was used)."""
        key = (raw, -1 if undated else date_days)
        hit = self.resolve_cache.get(key)
        if hit is not None:
            return hit
        cur = normalize_house(raw)
        aliased = False
        if cur is not None:
            seen = set()
            while cur in self.aliases and cur not in seen:
                new, eff = self.aliases[cur]
                if (not undated) and eff > date_days:
                    break
                seen.add(cur)
                cur = new
                aliased = True
            if cur not in self.registry:
                cur = None
        out = (cur, aliased)
        self.resolve_cache[key] = out
        return out


# --------------------------------------------------------------- workload ---

class Play(object):
    __slots__ = ('chain', 'spot', 'seq', 'order', 'frames', 'house', 'index',
                 'utc', 'bdate', 'bclock')

    def __init__(self, chain, spot, seq, order, frames, house, index, utc):
        self.chain = chain
        self.spot = spot
        self.seq = seq
        self.order = order
        self.frames = frames
        self.house = house
        self.index = index
        self.utc = utc
        self.bdate = 0
        self.bclock = 0


def seq_order(seq):
    try:
        return (0, int(seq), '')
    except ValueError:
        return (1, 0, seq)


def read_corrections(path, cutoff, admit_late):
    kept = []
    n_admitted = 0
    n_late = 0
    with open_file(path) as fh:
        for line in fh:
            if not line.strip():
                continue
            rec = json.loads(line)
            late = utc_ticks(rec['recorded_at']) >= cutoff
            if late:
                n_late += 1
            else:
                n_admitted += 1
            if (not late) or admit_late:
                kept.append(rec)
    return kept, n_admitted, n_late


def parse_asrun(path, chain, channel, retract_evts, rejects, stats):
    seen = set()
    dup = 0
    nonblank = 0
    retracted = 0
    kept = []
    with open_file(path) as fh:
        for raw in fh:
            line = raw.rstrip('\n').rstrip('\r')
            if not line.strip():
                continue
            nonblank += 1
            if line in seen:
                dup += 1
                continue
            seen.add(line)
            rec = {}
            for part in line.split('|'):
                key, eq, val = part.partition('=')
                if eq:
                    rec[key] = val
            if rec.get('type') != 'SPOT':
                continue
            if rec.get('evt', '').strip() in retract_evts:
                retracted += 1
                continue
            kept.append(rec)
    stats['asrun_lines'][chain] = nonblank
    stats['duplicate_lines'] += dup
    stats['retracted_lines'] += retracted

    plays = []
    for rec in kept:
        reason = None
        for field in ASRUN_FIELDS:
            val = rec.get(field)
            if val is None or not val.strip():
                reason = 'MISSING_FIELD'
                break
        count = None
        if reason is None:
            count, reason = channel.parse_label(rec['tc'])
        if reason is not None:
            rejects.append((chain, rec.get('seq', ''), reason))
            stats['rejects'][reason] += 1
            continue
        if rec['status'] != 'PLAYED':
            continue
        days = days_of(rec['date'])
        index = days * channel.DAY + count
        plays.append(Play(chain, rec['spot'], rec['seq'], seq_order(rec['seq']),
                          int(rec['frames']), rec['house'], index,
                          channel.utc_of(days, count)))
    return plays


def probe_offsets(path, variant, stats):
    rows = []
    relock_printed = bool(variant.get('relock_printed'))
    with open_file(path) as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            parts = line.split()
            fields = {}
            for p in parts[1:]:
                key, eq, val = p.partition('=')
                if eq:
                    fields[key] = val
            if fields.get('chain') != 'B':
                continue
            lock = fields.get('lock')
            if lock == 'RELOCK':
                stats['relock_probes'] += 1
            elif lock == 'STALE':
                stats['stale_probes'] += 1
                continue
            value = int(fields.get('offset_frames', '0'))
            if lock == 'RELOCK' and not relock_printed:
                value = 0
            rows.append((utc_ticks(parts[0]), value))
    rows.sort()
    return [r[0] for r in rows], [r[1] for r in rows]


def read_switcher(path):
    rows = []
    with open_file(path) as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            bus = None
            src = None
            for p in parts[1:]:
                if p.startswith('BUS='):
                    bus = p[4:]
                elif p.startswith('SRC='):
                    src = p[4:]
            if bus != 'PGM':
                continue
            rows.append((utc_ticks(parts[0]), src))
    rows.sort()
    return [r[0] for r in rows], [r[1] for r in rows]


class OnAir(object):
    def __init__(self, starts, sources, variant):
        self.always_a = bool(variant.get('chain_a_always'))
        self.starts = starts
        self.sources = sources

    def at(self, instant):
        if self.always_a:
            return 'A'
        i = bisect.bisect_right(self.starts, instant) - 1
        if i < 0:
            return None
        return self.sources[i]

    def in_span(self, start, end):
        if self.always_a:
            return ('A',)
        if end <= start:
            return ()
        starts = self.starts
        i = bisect.bisect_right(starts, start) - 1
        if i < 0:
            i = 0
        out = []
        n = len(starts)
        while i < n and starts[i] < end:
            out.append(self.sources[i])
            i += 1
        return out


def governing_amendment(amendments, date_days):
    best = None
    best_key = None
    for rec in amendments:
        eff = rec['_eff']
        if eff > date_days:
            continue
        key = (eff, rec['recorded_at'], rec['spots_per_day'])
        if best_key is None or key > best_key:
            best_key = key
            best = rec
    return best


def half_up(numerator, denominator):
    return (numerator * 2 + denominator) // (denominator * 2)


def compute(data_dir, workload, variant=None, corpus=None):
    variant = variant or {}
    if corpus is None:
        corpus = Corpus(data_dir, variant)
    cfg = corpus.cfg
    if not cfg.has_section(workload):
        raise KeyError(workload)
    channel = Channel(cfg[workload], corpus.zones, variant)
    daypart_bounds = {}
    daypart_order = []
    for dp in corpus.daypart_sets[channel.daypart_set]:
        daypart_order.append(dp['daypart'])
        daypart_bounds[dp['daypart']] = (channel.bound_count(dp['start']),
                                         channel.bound_count(dp['end']))
    cutoff = utc_ticks(corpus.policy['cutoff_utc'][workload])
    grace = int(corpus.policy['makegood_grace_days'])
    blackout = frozenset(days_of(d) for d in corpus.blackouts.get(channel.channel, []))

    def path(name):
        return os.path.join(data_dir, name)

    stats = {
        'asrun_lines': {'A': 0, 'B': 0},
        'duplicate_lines': 0,
        'rejects': {'BAD_TIMECODE': 0, 'DROPPED_LABEL': 0, 'MISSING_FIELD': 0},
        'retracted_lines': 0,
        'relock_probes': 0,
        'stale_probes': 0,
    }

    corrections, n_admitted, n_late = read_corrections(
        path('%s_corrections.jsonl' % workload), cutoff,
        bool(variant.get('late_corrections')))

    retract_evts = {'A': set(), 'B': set()}
    spot_corrections = defaultdict(list)
    for rec in corrections:
        kind = rec.get('kind')
        if kind == 'retract':
            chain, _, evt = rec.get('target', '').partition(':')
            if chain in retract_evts:
                retract_evts[chain].add(evt)
        elif kind in ('reattribute', 'restore'):
            if rec.get('rev', 0) == 0:
                continue
            spot_corrections[rec['target']].append(rec)

    rejects = []
    plays_a = parse_asrun(path('%s_asrun_a.log' % workload), 'A', channel,
                          retract_evts['A'], rejects, stats)
    plays_b = parse_asrun(path('%s_asrun_b.log' % workload), 'B', channel,
                          retract_evts['B'], rejects, stats)

    instants, offsets = probe_offsets(path('%s_sync_probes.log' % workload), variant, stats)
    if not variant.get('b_zero_offset') and instants:
        for play in plays_b:
            i = bisect.bisect_right(instants, play.utc) - 1
            if i >= 0 and offsets[i]:
                k = offsets[i]
                play.index -= k
                play.utc -= k * channel.frame_ticks

    governing = {}
    reairs = 0
    for play in plays_a:
        key = ('A', play.spot)
        cur = governing.get(key)
        if cur is None:
            governing[key] = play
        else:
            reairs += 1
            if (play.utc, play.order) < (cur.utc, cur.order):
                governing[key] = play
    for play in plays_b:
        key = ('B', play.spot)
        cur = governing.get(key)
        if cur is None:
            governing[key] = play
        else:
            reairs += 1
            if (play.utc, play.order) < (cur.utc, cur.order):
                governing[key] = play
    for play in governing.values():
        play.bdate, play.bclock = channel.broadcast_of(play.index)

    starts, sources = read_switcher(path('%s_switcher.log' % workload))
    onair = OnAir(starts, sources, variant)

    orders = corpus.orders
    workload_orders = corpus.orders_by_workload.get(workload, [])
    amend_admitted = 0
    amend_late = 0
    amend_by_line = {}
    for info in workload_orders:
        kept = []
        for rec in corpus.amendments.get(info['order_line'], ()):
            if utc_ticks(rec['recorded_at']) < cutoff:
                amend_admitted += 1
                item = dict(rec)
                item['_eff'] = days_of(rec['effective_from'])
                kept.append(item)
            else:
                amend_late += 1
        amend_by_line[info['order_line']] = kept

    undated = bool(variant.get('alias_undated'))
    raw_frames = bool(variant.get('raw_frames'))
    start_only = bool(variant.get('start_only_window'))
    window_rule = corpus.window_rule
    straddle_rule = corpus.straddle_rule
    tie_desk = corpus.tie_desk
    tolerance = channel.tolerance
    frame_ticks = channel.frame_ticks
    nominal = channel.nominal
    registry = corpus.registry
    expected_cache = {}

    def expected_frames(reg_id):
        value = expected_cache.get(reg_id)
        if value is None:
            master_rate, frames = registry[reg_id]
            value = frames if raw_frames else -((-frames * nominal) // master_rate)
            expected_cache[reg_id] = value
        return value

    spots_out = []
    dispositions = {}
    gov_lines = {}
    disp_counts = dict((d, 0) for d in DISPOSITIONS)
    alias_spots = 0
    reattributed = 0
    delivered_counter = defaultdict(int)
    held_counter = defaultdict(int)
    occupied = defaultdict(int)

    with open_file(path('%s_schedule.csv' % workload)) as fh:
        schedule = list(csv.DictReader(fh))
    schedule.sort(key=lambda r: r['spot_id'])

    for row in schedule:
        spot_id = row['spot_id']
        sched_date = days_of(row['broadcast_date'])
        sched_line = row['order_line']

        line = sched_line
        cands = spot_corrections.get(spot_id)
        if cands:
            best = None
            best_key = None
            for rec in cands:
                key = (rec['rev'],
                       1 if (tie_desk and rec['desk'] == tie_desk) else 0,
                       rec['recorded_at'], rec['correction_id'])
                if best_key is None or key > best_key:
                    best_key = key
                    best = rec
            if best['kind'] == 'reattribute':
                line = best['payload']['order_line']
        if line != sched_line:
            reattributed += 1
        gov_lines[spot_id] = line

        sched_reg, aliased = corpus.resolve(row['house_id'], sched_date, undated)

        play_a = governing.get(('A', spot_id))
        play_b = governing.get(('B', spot_id))
        partner = None
        if play_a is not None and onair.at(play_a.utc) == 'A':
            ref = play_a
            partner = play_b
        elif play_b is not None and onair.at(play_b.utc) == 'B':
            ref = play_b
            partner = play_a
        else:
            ref = None

        ref_reg = None
        if ref is not None:
            ref_reg, ref_alias = corpus.resolve(ref.house, sched_date, undated)
            aliased = aliased or ref_alias
        if aliased:
            alias_spots += 1

        chain = None
        if sched_reg is None:
            disp = 'UNRESOLVED'
            if ref is not None:
                chain = ref.chain
                bdate = ref.bdate
            else:
                bdate = sched_date
        elif ref is None:
            disp = None
            bdate = sched_date
            for cand in (play_a, play_b):
                if cand is None:
                    continue
                src = onair.at(cand.utc)
                if src is not None and src != 'A' and src != 'B':
                    disp = 'PREEMPTED'
                    chain = cand.chain
                    bdate = cand.bdate
                    break
            if disp is None:
                disp = 'MISSED'
        else:
            chain = ref.chain
            bdate = ref.bdate
            exp = expected_frames(sched_reg)
            span_sources = onair.in_span(ref.utc, ref.utc + exp * frame_ticks)
            disp = None
            for src in span_sources:
                if src is not None and src != 'A' and src != 'B':
                    disp = 'PREEMPTED'
                    break
            if disp is None:
                other = 'B' if ref.chain == 'A' else 'A'
                if other in span_sources:
                    if partner is not None:
                        saved = bool(straddle_rule(True, partner.frames >= exp,
                                                   abs(partner.index - ref.index), tolerance))
                    else:
                        saved = bool(straddle_rule(False, False, 0, tolerance))
                    if not saved:
                        disp = 'PARTIAL'
                elif ref.frames < exp:
                    disp = 'PARTIAL'
            if disp is None:
                if ref_reg is None:
                    disp = 'UNRESOLVED'
                elif ref_reg != sched_reg:
                    disp = 'WRONG_COPY'
                else:
                    info = orders.get(line)
                    bounds = daypart_bounds.get(info['daypart']) if info else None
                    if bounds is None:
                        disp = 'OUT_OF_WINDOW'
                    else:
                        ws, we = bounds
                        if start_only:
                            ok = ws <= ref.bclock < we
                        else:
                            ok = bool(window_rule(ref.bclock, exp, ws, we))
                        disp = 'AIRED' if ok else 'OUT_OF_WINDOW'

        dispositions[spot_id] = disp
        disp_counts[disp] += 1
        spots_out.append({'spot_id': spot_id, 'order_line': line,
                          'broadcast_date': iso_of(bdate), 'chain': chain,
                          'disposition': disp})

        if ref is not None and disp in OCCUPYING:
            occupied[row['break_id']] += ref.frames
        if bdate in channel.date_set:
            if disp == 'AIRED':
                delivered_counter[(line, bdate)] += 1
            elif disp == 'UNRESOLVED':
                held_counter[(line, bdate)] += 1

    committed_counter = {}
    for info in workload_orders:
        line = info['order_line']
        amends = amend_by_line.get(line, ())
        weekdays = info['weekdays']
        start = info['flight_start']
        end = info['flight_end']
        for d in channel.dates:
            if not (start <= d < end):
                continue
            if weekday_of(d) not in weekdays:
                continue
            if d in blackout:
                continue
            amend = governing_amendment(amends, d) if amends else None
            spd = amend['spots_per_day'] if amend else info['spots_per_day']
            if spd:
                committed_counter[(line, d)] = spd

    pairs = set(committed_counter)
    pairs.update(delivered_counter)
    pairs.update(held_counter)
    deliveries = []
    for line, d in sorted(pairs):
        committed = committed_counter.get((line, d), 0)
        delivered = delivered_counter.get((line, d), 0)
        held = held_counter.get((line, d), 0)
        if committed <= 0 and delivered <= 0 and held <= 0:
            continue
        effective = committed - held
        if effective < 0:
            effective = 0
        billable = delivered if delivered < effective else effective
        deliveries.append({'order_line': line, 'broadcast_date': iso_of(d),
                           'committed': committed, 'held': held, 'delivered': delivered,
                           'billable': billable, 'shortfall': effective - billable,
                           'bonus': delivered - billable, '_date': d})

    breaks = {}
    by_daypart = defaultdict(list)
    with open_file(path('%s_breaks.tsv' % workload)) as fh:
        for row in csv.DictReader(fh, delimiter='\t'):
            bid = row['break_id']
            count, _reason = channel.parse_label(row['open_tc'])
            if count is None:
                count = 0
            local_days = days_of(row['local_date'])
            _day, bclock = channel.broadcast_of(local_days * channel.DAY + count)
            cap = int(row['capacity_frames'])
            occ = occupied.get(bid, 0)
            dp = None
            for name in daypart_order:
                ws, we = daypart_bounds[name]
                if ws <= bclock < we:
                    dp = name
                    break
            item = {'break_id': bid, 'bdate': days_of(row['broadcast_date']),
                    'bclock': bclock, 'capacity': cap, 'occupied': occ,
                    'spare': cap - occ if cap > occ else 0, 'daypart': dp,
                    'makegood_frames': 0}
            breaks[bid] = item
            if dp is not None:
                by_daypart[dp].append(item)
    for items in by_daypart.values():
        items.sort(key=lambda b: (b['bdate'], b['bclock'], b['break_id']))
    daypart_dates = dict((dp, [b['bdate'] for b in items])
                         for dp, items in by_daypart.items())

    units = []
    for row in deliveries:
        if row['shortfall'] <= 0:
            continue
        info = orders.get(row['order_line'])
        if info is None:
            continue
        for n in range(1, row['shortfall'] + 1):
            units.append((info['priority'], row['_date'], -info['unit_rate_cents'],
                          row['order_line'], n, info))
    units.sort(key=lambda u: u[:5])

    last_date = channel.dates[-1] if channel.dates else None
    need_cache = {}
    makegoods = []
    credited_by_line = defaultdict(int)
    placed_by_line = defaultdict(int)
    units_by_line = defaultdict(int)
    placements = defaultdict(list)
    for priority, from_date, neg_rate, line, number, info in units:
        key = (line, from_date)
        need = need_cache.get(key)
        if need is None:
            reg_id, _alias = corpus.resolve(info['house_id'], from_date, undated)
            need = expected_frames(reg_id) if reg_id is not None else 0
            need_cache[key] = need
        limit = info['flight_end'] - 1 + grace
        if last_date is not None and last_date < limit:
            limit = last_date
        chosen = None
        items = by_daypart.get(info['daypart'])
        if items:
            i = bisect.bisect_right(daypart_dates[info['daypart']], from_date)
            n = len(items)
            while i < n:
                item = items[i]
                if item['bdate'] > limit:
                    break
                if item['spare'] >= need:
                    chosen = item
                    break
                i += 1
        units_by_line[line] += 1
        if chosen is None:
            credited_by_line[line] += 1
            makegoods.append({'order_line': line, 'from_date': iso_of(from_date),
                              'unit': number, 'status': 'credited',
                              'break_id': None, 'broadcast_date': None})
        else:
            chosen['spare'] -= need
            chosen['makegood_frames'] += need
            placed_by_line[line] += 1
            placements[line].append(chosen)
            makegoods.append({'order_line': line, 'from_date': iso_of(from_date),
                              'unit': number, 'status': 'placed',
                              'break_id': chosen['break_id'],
                              'broadcast_date': iso_of(chosen['bdate'])})
    makegoods.sort(key=lambda m: (m['order_line'], m['from_date'], m['unit']))

    billable_by_line = defaultdict(int)
    delivered_by_line = defaultdict(int)
    effective_by_line = defaultdict(int)
    for row in deliveries:
        billable_by_line[row['order_line']] += row['billable']
        delivered_by_line[row['order_line']] += row['delivered']
        effective_by_line[row['order_line']] += row['billable'] + row['shortfall']
    billing = []
    for line in sorted(billable_by_line):
        info = orders.get(line)
        rate = info['unit_rate_cents'] if info else 0
        advertiser = info['advertiser'] if info else None
        bps = corpus.advertisers.get(advertiser, {}).get('commission_bps', 0)
        gross = billable_by_line[line] * rate
        commission = half_up(gross * bps, 10000)
        credit = credited_by_line.get(line, 0) * rate
        billing.append({'order_line': line, 'advertiser': advertiser,
                        'gross_cents': gross, 'commission_cents': commission,
                        'credit_cents': credit,
                        'net_cents': gross - commission - credit})

    totals = {'scheduled_spots': len(schedule), 'aired': disp_counts['AIRED'],
              'committed': 0, 'held': 0, 'delivered': 0, 'billable': 0,
              'shortfall': 0, 'bonus': 0,
              'placed_units': sum(placed_by_line.values()),
              'credited_units': sum(credited_by_line.values()),
              'gross_cents': 0, 'commission_cents': 0, 'credit_cents': 0, 'net_cents': 0}
    for row in deliveries:
        for key in ('committed', 'held', 'delivered', 'billable', 'shortfall', 'bonus'):
            totals[key] += row[key]
    for row in billing:
        for key in ('gross_cents', 'commission_cents', 'credit_cents', 'net_cents'):
            totals[key] += row[key]

    rejects.sort(key=lambda r: (r[0], r[1], r[2]))
    scenario = {
        'workload': workload,
        'channel': channel.channel,
        'spots': spots_out,
        'deliveries': [dict((k, v) for k, v in row.items() if k != '_date')
                       for row in deliveries],
        'makegoods': makegoods,
        'billing': billing,
        'rejects': [{'chain': c, 'seq': s, 'reason': r} for c, s, r in rejects],
        'totals': totals,
    }

    quality = {
        'workload': workload,
        'asrun_lines': stats['asrun_lines'],
        'duplicate_lines': stats['duplicate_lines'],
        'rejects': stats['rejects'],
        'reairs': reairs,
        'retracted_lines': stats['retracted_lines'],
        'corrections': {'admitted': n_admitted, 'late': n_late,
                        'reattributed_spots': reattributed},
        'amendments': {'admitted': amend_admitted, 'late': amend_late},
        'alias_spots': alias_spots,
        'relock_probes': stats['relock_probes'],
        'stale_probes': stats['stale_probes'],
        'dispositions': dict((d, disp_counts[d]) for d in DISPOSITIONS),
        'partition_residual': len(schedule) - sum(disp_counts.values()),
    }

    return {
        'scenario': scenario,
        'quality': quality,
        'channel': channel,
        'daypart_order': daypart_order,
        'breaks': breaks,
        'break_lists': by_daypart,
        'deliveries': deliveries,
        'dispositions': dispositions,
        'governing_lines': gov_lines,
        'placements': placements,
        'credited_by_line': credited_by_line,
        'placed_by_line': placed_by_line,
        'units_by_line': units_by_line,
        'delivered_by_line': delivered_by_line,
        'effective_by_line': effective_by_line,
        'billable_by_line': billable_by_line,
        'orders': workload_orders,
    }


def reconcile(data_dir, workload):
    """Return the scenario object of `workload` for the data directory."""
    return compute(data_dir, workload)['scenario']


def main(argv):
    if len(argv) != 3:
        return 2
    try:
        text = json.dumps(reconcile(argv[1], argv[2]), sort_keys=True)
    except (OSError, IOError):
        return 1
    sys.stdout.write(text + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
