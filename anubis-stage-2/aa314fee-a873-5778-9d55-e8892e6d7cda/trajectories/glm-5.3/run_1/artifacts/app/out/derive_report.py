#!/usr/bin/env python3
"""Derive the wafer start apportionment report from a corpus.

Reads the corpus handed to it (--data) and writes the nine documents
described in output_contract.md into --out.  Every rule is read from the
corpus at run time; nothing about the corpus is assumed.
"""

import argparse
import configparser
import csv
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

UTC = timezone.utc


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------

def parse_dt(text):
    """Parse an instant string ('...Z' or '...+00:00' or compact) to aware UTC."""
    t = text.strip()
    if re.fullmatch(r'\d{14}', t):
        return datetime.strptime(t, '%Y%m%d%H%M%S').replace(tzinfo=UTC)
    if t.endswith('Z'):
        t = t[:-1] + '+00:00'
    dt = datetime.fromisoformat(t)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def half_up(num, den):
    """Round num/den half up (a value exactly halfway goes to the larger)."""
    if den < 0:
        num, den = -num, -den
    if num >= 0:
        return (2 * num + den) // (2 * den)
    # half up towards the larger (i.e. towards zero for negatives)
    return -((-2 * num + den) // (2 * den))


def read_lines(path):
    with open(path, 'r', encoding='utf-8') as fh:
        return fh.read().splitlines()


def split_rows(lines, sep, ncols=None):
    """Split comment-headed record files.  Returns (declared, header, rows)."""
    declared = None
    header = None
    rows = []
    for line in lines:
        if not line.strip():
            continue
        if line.startswith('#') and header is None:
            for part in line.split():
                if part.startswith('declared_rows='):
                    declared = int(part.split('=', 1)[1])
            continue
        if header is None:
            header = next(csv.reader([line], delimiter=sep))
            continue
        f = next(csv.reader([line], delimiter=sep))
        if ncols and len(f) < ncols:
            f = f + [''] * (ncols - len(f))
        rows.append(f)
    return declared, header, rows


def zipped(header, fields):
    out = {}
    for i, key in enumerate(header):
        if key not in out:            # the order book carries two 'quantity'
            out[key] = fields[i] if i < len(fields) else ''
    return out


# --------------------------------------------------------------------------
# machine readable policy
# --------------------------------------------------------------------------

def load_ini(path):
    cp = configparser.ConfigParser()
    cp.optionxform = str
    cp.read(path)
    return cp


def ini_get(cp, section, key):
    """Resolve a key through the inherits chain, nearest first."""
    seen = set()
    sec = section
    while sec and sec not in seen:
        seen.add(sec)
        if sec in cp and key in cp[sec]:
            return cp[sec][key]
        if sec not in cp:
            return None
        sec = cp[sec].get('inherits') if cp[sec] is not None else None
    return None


def load_properties(path):
    """Parse a .properties file with backslash continuations and ':'/'=' keys."""
    raw = []
    with open(path, 'r', encoding='utf-8') as fh:
        buf = ''
        for line in fh:
            line = line.rstrip('\n')
            if line.endswith('\\'):
                buf += line[:-1]
                continue
            buf += line
            raw.append(buf)
            buf = ''
        if buf:
            raw.append(buf)
    props = {}
    for line in raw:
        s = line.strip()
        if not s or s.startswith('#') or s.startswith('!'):
            continue
        for sep in ('=', ':'):
            if sep in line:
                key, val = line.split(sep, 1)
                props[key.strip()] = val.strip()
                break
    return props


def parse_int_list(text):
    return [int(x) for x in text.split(',') if x.strip()]


# --------------------------------------------------------------------------
# corpus
# --------------------------------------------------------------------------

class Corpus(object):
    def __init__(self, data_dir, variant=None):
        self.dir = data_dir
        self.variant = variant or {}
        self.dq = defaultdict(int)          # data quality scratch
        self.dq_sources = {}               # code -> counts
        self.tally = defaultdict(int)      # policy audit scratch
        self.substitution_hops = defaultdict(int)
        self.cutover_sides = defaultdict(int)
        self.withheld = {}
        self.fold_disambiguated = 0
        self.gap_shifted = 0
        self.header_gaps = {}
        self.late_by_source = defaultdict(int)

        # ---- rule documents
        self.temporal_doc = self._read_md('temporal_rules.md')
        self.output_doc = self._read_md('output_contract.md')

        # ---- clock marks come first: the year reading falls back on them
        self._load_clock_marks()
        self.horizon_year = self._horizon_year()
        self.close_year = self._close_year()

        # ---- derivation policy
        cp = load_ini(os.path.join(data_dir, 'derivation_policy.ini'))
        self.cp = cp
        self.as_of_text = ini_get(cp, 'defaults', 'as_of_instant')
        self.as_of = parse_dt(self.as_of_text)
        self.as_of_reported = self.as_of_text
        if self.variant.get('lift_admission'):
            self.as_of = datetime.max.replace(tzinfo=UTC)
        self.first_cycle = ini_get(cp, 'defaults', 'horizon_first_cycle')
        self.last_cycle = ini_get(cp, 'defaults', 'horizon_last_cycle')
        self.cycle_start_time = ini_get(cp, 'defaults', 'cycle_start_local_time')
        self.cycle_start_days = parse_int_list(ini_get(cp, 'defaults', 'cycle_start_days'))
        self.collapse_window = int(ini_get(cp, 'defaults', 'collapse_window_minutes'))
        self.max_hops = int(ini_get(cp, 'defaults', 'max_substitution_hops'))
        self.unranked_rank = int(ini_get(cp, 'defaults', 'unranked_commitment_rank'))
        self.site_skew = {}
        for sec in cp.sections():
            if sec.startswith('site:'):
                site = sec.split(':', 1)[1]
                val = ini_get(cp, sec, 'recorder_skew_seconds')
                if val is None:
                    val = ini_get(cp, 'defaults', 'recorder_skew_seconds')
                self.site_skew[site] = int(val or 0)

        # ---- unit declarations
        ucp = load_ini(os.path.join(data_dir, 'unit_declarations.ini'))
        self.lot_size = {}
        for sec in ucp.sections():
            for key in ucp[sec]:
                if key.endswith('_wafers') or key == 'lot_size_wafers':
                    self.lot_size[sec] = int(ucp[sec][key])

        # ---- reason codes
        with open(os.path.join(data_dir, 'reason_codes.json'), 'r', encoding='utf-8') as fh:
            self.reasons = json.load(fh)
        self.reason_precedence = list(self.reasons['reason_precedence'])
        self.outcome_names = list(self.reasons['outcomes'])

        # ---- source declarations
        self.props = load_properties(os.path.join(data_dir, 'source_declarations.properties'))
        self.source_codes = []
        self.source_files = {}
        self.source_extra = {}
        for key in self.props:
            m = re.match(r'^source\.([A-Za-z0-9_]+)\.files$', key)
            if m:
                code = m.group(1)
                if code not in self.source_codes:
                    self.source_codes.append(code)
                self.source_files[code] = [f.strip() for f in self.props[key].split(',') if f.strip()]
            m = re.match(r'^source\.([A-Za-z0-9_]+)\.audit$', key)
            if m:
                code = m.group(1)
                self.source_extra[code] = [f.strip() for f in self.props[key].split(',') if f.strip()]
        for key in self.props:
            m = re.match(r'^source\.([A-Za-z0-9_]+)\.name$', key)
            if m and m.group(1) not in self.source_codes:
                self.source_codes.append(m.group(1))
        for code in self.source_codes:
            self.dq_sources[code] = {'declared_rows': 0, 'parsed_rows': 0, 'admitted_rows': 0}
        self.cutover_cycle = self.props.get('precedence.cutover_cycle')
        self.precedence = {}
        for key, val in self.props.items():
            m = re.match(r'^precedence\.(before_cutover|from_cutover)\.([a-z_]+)$', key)
            if m:
                self.precedence[(m.group(1), m.group(2))] = val
        if self.variant.get('quantity_before_cutover'):
            self.precedence[('before_cutover', 'quantity')] = \
                self.variant['quantity_before_cutover']

        # ---- clock marks
        self._load_clock_marks()

        # ---- withheld rules are settled from the observation logs
        self._settle_withheld()

        # ---- everything else
        self._load_master()
        self._load_alias()
        self._load_audit()
        self._load_roles()
        self._load_retractions()
        self._load_registers()
        self._load_requests()

    # ---------------- rule documents
    def _read_md(self, name):
        path = os.path.join(self.dir, name)
        if not os.path.exists(path):
            return ''
        return read_lines(path)

    def _horizon_year(self):
        text = ' '.join(self.temporal_doc)
        m = re.search(r'calendar year (\d{4})', text)
        if m:
            return int(m.group(1))
        m = re.search(r'C01 starts on 1 January and C24 starts on 16 December', text)
        if m:
            # fall back on the year most represented among the clock marks
            years = defaultdict(int)
            for site in self._clock_years:
                years[site] += self._clock_years[site]
            if years:
                return max(years.items(), key=lambda kv: kv[1])[0]
        return 2031

    def _close_year(self):
        text = ' '.join(self.temporal_doc)
        m = re.search(r'closes at 06:00:00 site local on 1 January (\d{4})', text)
        if m:
            return int(m.group(1))
        return self.horizon_year + 1

    # ---------------- clock marks
    def _load_clock_marks(self):
        path = os.path.join(self.dir, 'site_clock_marks.csv')
        self.marks = defaultdict(list)
        years = defaultdict(int)
        if not os.path.exists(path):
            return
        with open(path, 'r', encoding='utf-8') as fh:
            for row in csv.DictReader(fh):
                self.marks[row['site']].append(row)
                years[int(row['local_date'][:4])] += 1
        self._clock_years = years
        for site in self.marks:
            self.marks[site].sort(key=lambda m: (m['local_date'], m['from_local_time']))
        self.sites = self._site_order(sorted(self.marks.keys()))

    def _site_order(self, found):
        """The order the output contract names the sites in."""
        text = ' '.join(self.output_doc)
        order = []
        m = re.search(r'Every site is named ([^.]*?)\.', text)
        if m:
            order = re.findall(r'`([A-Za-z]+)`', m.group(1))
        if not order:
            for name in re.findall(r'region_([A-Za-z]+)\.json', text):
                if name not in order:
                    order.append(name)
        out = [s for s in order if s in found]
        out.extend(s for s in found if s not in out)
        return out

    def _mark_before(self, site, local_date, before_time=None):
        ms = self.marks.get(site, [])
        prior = [m for m in ms
                 if m['local_date'] < local_date or
                 (m['local_date'] == local_date and
                  (before_time is None or m['from_local_time'] < before_time))]
        if prior:
            return prior[-1]
        prior = [m for m in ms if m['local_date'] <= local_date]
        if prior:
            return prior[-1]
        return None

    def classify_stamp(self, site, stamp):
        """Classify a site local wall stamp.  Returns a tuple."""
        d = stamp[:10]
        t = stamp[11:19] if len(stamp) > 10 else '00:00:00'
        ms = self.marks.get(site, [])
        for m in ms:
            if m['local_date'] != d:
                continue
            before = self._mark_before(site, d, m['from_local_time'])
            off_before = int(before['utc_offset_minutes']) if before else 0
            off_after = int(m['utc_offset_minutes'])
            delta = abs(off_after - off_before)
            base = datetime.strptime(m['from_local_time'], '%H:%M:%S')
            if m['mark_kind'] == 'clocks_back':
                lo = (base - timedelta(minutes=delta)).strftime('%H:%M:%S')
                if lo <= t < m['from_local_time']:
                    return ('fold', off_before, off_after)
            elif m['mark_kind'] == 'clocks_forward':
                hi = (base + timedelta(minutes=delta)).strftime('%H:%M:%S')
                if m['from_local_time'] <= t < hi:
                    return ('gap', off_after, delta)
        mark = self._mark_before(site, d, t)
        off = int(mark['utc_offset_minutes']) if mark else 0
        return ('normal', off, None)

    def to_utc(self, site, stamp, fold=0):
        """Resolve a site local wall stamp to an aware UTC instant."""
        kind, a, b = self.classify_stamp(site, stamp)
        loc = datetime.strptime(stamp, '%Y-%m-%dT%H:%M:%S')
        if kind == 'fold':
            off = a if fold == 0 else b
            self.fold_disambiguated += 1
            return loc.replace(tzinfo=timezone(timedelta(minutes=off)))
        if kind == 'gap':
            self.gap_shifted += 1
            return (loc + timedelta(minutes=b)).replace(tzinfo=timezone(timedelta(minutes=a)))
        return loc.replace(tzinfo=timezone(timedelta(minutes=a)))

    # ---------------- withheld rules
    def _settle_withheld(self):
        """Settle the two rules the contract withholds, from the observation logs."""
        # 1. which source governs the quantity before the cutover
        readings = []
        path = os.path.join(self.dir, 'governance_observations.log')
        if os.path.exists(path):
            for line in read_lines(path):
                if not line.strip():
                    continue
                fields = dict(kv.split('=', 1) for kv in line.split() if '=' in kv)
                readings.append(fields)
        survivors = []
        for cand in ('order_book', 'contract_registry', 'later_recorded'):
            ok = True
            for r in readings:
                gov = r.get('governed_by')
                if cand == 'later_recorded':
                    expect = 'order_book' if r.get('later_recorded') == 'order_book' \
                        else 'contract_registry'
                else:
                    expect = cand
                if gov is not None and gov != expect:
                    ok = False
                    break
            if ok:
                survivors.append(cand)
        if survivors:
            self.withheld['quantity_governed_before_cutover'] = survivors[0]
        else:
            self.withheld['quantity_governed_before_cutover'] = 'order_book'

        # 2. how many later cycles a deficit lot survives
        obs = []
        path = os.path.join(self.dir, 'deficit_observations.log')
        if os.path.exists(path):
            for line in read_lines(path):
                if not line.strip():
                    continue
                fields = dict(kv.split('=', 1) for kv in line.split() if '=' in kv)
                obs.append((int(fields['lot_age']), fields['deficit_state']))
        reading = 'unbounded'
        for cand in (1, 2, 3, 'unbounded'):
            ok = True
            for age, state in obs:
                alive = (state == 'carried')
                expect = True if cand == 'unbounded' else (age <= cand)
                if alive != expect:
                    ok = False
                    break
            if ok:
                reading = cand
                break
        self.withheld['carry_forward_age'] = reading

    # ---------------- registers
    def _load_master(self):
        path = os.path.join(self.dir, 'customer_master.csv')
        declared, header, rows = split_rows(read_lines(path), ',')
        parsed = len(rows)
        admitted = []
        for r in rows:
            rec = parse_dt(zipped(header, r)['recorded_utc'])
            if rec <= self.as_of:
                admitted.append(zipped(header, r))
        self._count_source('MST', declared, parsed, len(admitted))
        self.master = admitted

    def _load_alias(self):
        path = os.path.join(self.dir, 'customer_alias_map.csv')
        declared, header, rows = split_rows(read_lines(path), ',')
        admitted = []
        for r in rows:
            d = zipped(header, r)
            if parse_dt(d['recorded_utc']) <= self.as_of:
                admitted.append(d)
        self._count_source('ALS', declared, len(rows), len(admitted))
        self.alias = defaultdict(list)
        for d in admitted:
            self.alias[d['alias_code']].append(d)

    def _load_roles(self):
        path = os.path.join(self.dir, 'authority_roles.csv')
        declared, header, rows = split_rows(read_lines(path), ',')
        admitted = []
        for r in rows:
            d = zipped(header, r)
            if parse_dt(d['recorded_utc']) <= self.as_of:
                admitted.append(d)
        self._count_source('AUT', declared, len(rows), len(admitted))
        self.roles = defaultdict(list)
        for d in admitted:
            self.roles[d['approver_id']].append(d)

    def _load_audit(self):
        entries = []
        cont = 0
        files = self.source_extra.get('AUT', [])
        for name in files:
            path = os.path.join(self.dir, name)
            if not os.path.exists(path):
                continue
            for line in read_lines(path):
                if not line.strip():
                    continue
                if line.startswith('  '):
                    cont += 1
                    if entries:
                        entries[-1]['continuations'] += 1
                    continue
                fields = dict(kv.split('=', 1) for kv in line.split() if '=' in kv)
                stamp = line.split()[0]
                site = fields.get('site')
                instant = self.to_utc(site, stamp) - timedelta(seconds=self.site_skew.get(site, 0))
                entries.append({'fields': fields, 'instant': instant,
                                'continuations': 0, 'stamp': stamp})
        self.log_continuations = cont
        self.audit_entries = entries
        self.audit_by_apl = {}
        self.audit_by_ref = {}
        late = 0
        for e in entries:
            if e['instant'] > self.as_of:
                late += 1
                continue
            apl = e['fields'].get('apl')
            ref = e['fields'].get('ref')
            if apl and apl not in self.audit_by_apl:
                self.audit_by_apl[apl] = e
            if ref and ref not in self.audit_by_ref:
                self.audit_by_ref[ref] = e
        self.dq_sources['AUT']['parsed_rows'] += len(entries)
        self.dq_sources['AUT']['admitted_rows'] += len(entries) - late

    def _load_retractions(self):
        path = os.path.join(self.dir, 'retraction_notices.csv')
        declared, header, rows = split_rows(read_lines(path), ',')
        parsed = []
        for r in rows:
            d = zipped(header, r)
            d['_rec'] = parse_dt(d['recorded_utc'])
            parsed.append(d)
        admitted = [d for d in parsed if d['_rec'] <= self.as_of]
        self._count_source('RTR', declared, len(rows), len(admitted))
        self.retractions = admitted
        self.retraction_by_id = {d['retraction_id']: d for d in admitted}
        self._live_cache = {}

    def _retraction_live(self, retraction_id, seen):
        """A retraction is live when no live retraction targets it."""
        cached = self._live_cache.get(retraction_id)
        if cached is not None:
            return cached
        if retraction_id in seen:
            return True
        seen = seen | set([retraction_id])
        for d in self.retractions:
            if d['target_id'] == retraction_id and d['target_kind'] == 'retraction':
                if self._retraction_live(d['retraction_id'], seen):
                    self._live_cache[retraction_id] = False
                    return False
        self._live_cache[retraction_id] = True
        return True

    def is_retracted(self, target_id, kind):
        """True when a live retraction targets target_id."""
        for d in self.retractions:
            if d['target_id'] == target_id and d['target_kind'] == kind:
                if self._retraction_live(d['retraction_id'], set()):
                    return True
        return False

    def _load_registers(self):
        # ceilings
        self.ceilings = defaultdict(list)
        declared = 0
        parsed = 0
        for name in self.source_files.get('CEIL', []):
            path = os.path.join(self.dir, name)
            d, header, rows = split_rows(read_lines(path), ',')
            declared += d or 0
            parsed += len(rows)
            if (d or 0) != len(rows):
                self.header_gaps[name] = (d or 0) - len(rows)
            for r in rows:
                x = zipped(header, r)
                self._lot_row(x['unit'])
                fold = int(x.get('fold') or 0)
                inst = self.to_utc(x['declaring_site'], x['effective_local'], fold)
                x['_eff'] = inst
                x['_rec'] = parse_dt(x['recorded_utc'])
                if x['_rec'] <= self.as_of:
                    x['_num'], x['_den'] = self._figure(x['ceiling'], x['unit'], 'ceilings')
                    self.ceilings[(x['customer_id'], x['epoch_seq'])].append(x)
        self._count_source('CEIL', declared, parsed,
                           sum(len(v) for v in self.ceilings.values()))

        # capacity
        self.capacity_rows = defaultdict(list)
        declared = parsed = 0
        for name in self.source_files.get('CAP', []):
            path = os.path.join(self.dir, name)
            d, header, rows = split_rows(read_lines(path), ',')
            declared += d or 0
            parsed += len(rows)
            if (d or 0) != len(rows):
                self.header_gaps[name] = (d or 0) - len(rows)
            for r in rows:
                x = zipped(header, r)
                self._lot_row(x['unit'])
                if x['value'].strip().startswith('('):
                    self.dq['paren_negatives'] += 1
                    val = -int(x['value'].strip()[1:-1])
                else:
                    val = int(x['value'])
                x['_value'] = val
                x['_eff'] = self.to_utc(x['site'], x['effective_local'], int(x.get('fold') or 0))
                x['_rec'] = parse_dt(x['recorded_utc'])
                if x['_rec'] <= self.as_of:
                    self.capacity_rows[(x['site'], x['cycle'])].append(x)
        self._count_source('CAP', declared, parsed,
                           sum(len(v) for v in self.capacity_rows.values()))

        # substitution factors
        self.sub_rows = defaultdict(list)
        declared = parsed = 0
        for name in self.source_files.get('SUB', []):
            path = os.path.join(self.dir, name)
            d, header, rows = split_rows(read_lines(path), ',')
            declared += d or 0
            parsed += len(rows)
            if (d or 0) != len(rows):
                self.header_gaps[name] = (d or 0) - len(rows)
            for r in rows:
                x = zipped(header, r)
                x['_factor'] = int(x['factor_per_100'])
                x['_eff'] = self.to_utc(x['site'], x['effective_local'], int(x.get('fold') or 0))
                x['_rec'] = parse_dt(x['recorded_utc'])
                if x['_rec'] <= self.as_of:
                    self.sub_rows[(x['site'], x['cycle'], x['from_node'], x['to_node'])].append(x)
        self._count_source('SUB', declared, parsed,
                           sum(len(v) for v in self.sub_rows.values()))

        # agreements
        self.agreements = defaultdict(list)
        declared = parsed = admitted = 0
        path = os.path.join(self.dir, 'commitment_agreements.csv')
        d, header, rows = split_rows(read_lines(path), ',')
        declared = d or 0
        parsed = len(rows)
        for r in rows:
            x = zipped(header, r)
            self._lot_row(x['unit'])
            x['_eff'] = self.to_utc(x['site'], x['effective_local'], 0)
            x['_rec'] = parse_dt(x['recorded_utc'])
            if x['_rec'] <= self.as_of:
                admitted += 1
                self.agreements[x['agreement_id']].append(x)
        self._count_source('AGR', declared, parsed, admitted)

        # priority register (site local of the agreement site)
        self.priority = defaultdict(list)
        declared = parsed = admitted = 0
        path = os.path.join(self.dir, 'priority_register.csv')
        d, header, rows = split_rows(read_lines(path), ',')
        declared = d or 0
        parsed = len(rows)
        for r in rows:
            x = zipped(header, r)
            x['_rec'] = parse_dt(x['recorded_utc'])
            if x['_rec'] <= self.as_of:
                admitted += 1
                self.priority[x['agreement_id']].append(x)
        self._count_source('PRI', declared, parsed, admitted)
        # resolve the effective instants once the agreements are known
        for aid, rows2 in self.priority.items():
            for x in rows2:
                ag = self.agreements.get(aid)
                site = ag[0]['site'] if ag else sorted(self.marks.keys())[0]
                x['_eff'] = self.to_utc(site, x['effective_local'], 0)

        # commitment exceptions
        self.exceptions = defaultdict(list)
        declared = parsed = 0
        path = os.path.join(self.dir, 'commitment_exceptions.csv')
        d, header, rows = split_rows(read_lines(path), ',')
        declared = d or 0
        parsed = len(rows)
        for r in rows:
            x = zipped(header, r)
            x['_rec'] = parse_dt(x['recorded_utc'])
            if x['_rec'] <= self.as_of:
                self.exceptions[x['agreement_id']].append(x)
        self._count_source('EXC', declared, parsed,
                           sum(len(v) for v in self.exceptions.values()))

        # observation logs (counted only)
        declared = parsed = admitted = 0
        for name in self.source_files.get('OBS', []):
            path = os.path.join(self.dir, name)
            lines = [l for l in read_lines(path) if l.strip()]
            parsed += len(lines)
            admitted += len(lines)      # settled prior periods, always before the as of
        self._count_source('OBS', 0, parsed, admitted)

        # clock marks (no recorded instant)
        self._count_source('CLK', 0, sum(len(v) for v in self.marks.values()),
                           sum(len(v) for v in self.marks.values()))

    def _figure(self, text, unit, section):
        """A stated figure as (numerator, denominator) in wafers."""
        val = text.strip()
        if '.' in val:
            num = int(round(float(val) * 100))
            den = 100
        else:
            num = int(val)
            den = 1
        lot = self.lot_size.get(section, 25)
        if unit and 'lot' in unit:
            num *= lot
        return num, den

    def _count_source(self, code, declared, parsed, admitted):
        slot = self.dq_sources.setdefault(code, {'declared_rows': 0,
                                                  'parsed_rows': 0,
                                                  'admitted_rows': 0})
        slot['declared_rows'] += declared or 0
        slot['parsed_rows'] += parsed
        slot['admitted_rows'] += admitted
        if parsed - admitted:
            self.late_by_source[code] += parsed - admitted

    # ---------------- customer resolution
    def canonical_id(self, ref):
        """Canonicalise a customer reference spelling."""
        t = ref.strip()
        m = re.fullmatch(r'[A-Za-z]-0*(\d+)', t)
        if m:
            return 'CUS-' + m.group(1).zfill(4)
        m = re.fullmatch(r'CUS-0*(\d+)', t)
        if m:
            return 'CUS-' + m.group(1).zfill(4)
        return t

    def resolve_customer(self, ref, instant):
        """Resolve a customer reference at an instant; None when it cannot be.

        A target can itself be an alias, so resolution follows at most three
        hops and then must stand on a canonical id in the master register.
        """
        cur = ref.strip()
        hops = 0
        while True:
            if not cur[:4] in ('LGC-', 'VND-', 'OLD-'):
                cid = self.canonical_id(cur)
                return cid if cid in self.master_ids else None
            hops += 1
            if hops > 3:
                return None
            cands = [r for r in self.alias.get(cur, [])
                     if parse_dt(r['effective_utc']) <= instant < parse_dt(r['expires_utc'])]
            if not cands:
                return None
            best = max(cands, key=lambda r: (r['effective_utc'], int(r['revision_seq'])))
            cur = best['target_code']

    def epoch_of(self, cid, instant):
        """The epoch of a canonical id at an instant, or None."""
        best = None
        for row in self.master_by_id.get(cid, []):
            if parse_dt(row['epoch_from_utc']) <= instant < parse_dt(row['epoch_to_utc']):
                if best is None or int(row['epoch_seq']) < best:
                    best = int(row['epoch_seq'])
        return best

    # ---------------- request evidence
    def _load_requests(self):
        self.master_ids = set()
        self.master_by_id = defaultdict(list)
        for row in self.master:
            self.master_ids.add(row['customer_id'])
            self.master_by_id[row['customer_id']].append(row)

        rows = []
        # order book
        declared = parsed = admitted = 0
        for name in self.source_files.get('OBK', []):
            path = os.path.join(self.dir, name)
            d, header, raw = split_rows(read_lines(path), ',')
            declared += d or 0
            parsed += len(raw)
            if (d or 0) != len(raw):
                self.header_gaps[name] = (d or 0) - len(raw)
            for i, f in enumerate(raw):
                x = {'src': 'OBK', 'fileorder': (name, i)}
                x['ref'] = f[0]
                x['rawref'] = f[1]
                x['site'] = f[2]
                x['node'] = None if f[3].strip() in ('', '\\N') else f[3].strip()
                self._lot_row(f[6])
                x['qty_num'], x['qty_den'] = self._figure(f[4], f[6], 'order_book')
                x['eff'] = self.to_utc(f[2], f[7], int(f[8] or 0))
                x['rec'] = parse_dt(f[9])
                x['batch'] = f[10]
                x['note'] = f[11] if len(f) > 11 else ''
                if f[4] != f[5]:
                    self.dq['restatement_gaps'] += 1
                if x['rec'] <= self.as_of:
                    admitted += 1
                    rows.append(x)
                else:
                    self.dq['late_OBK'] += 1
        self._count_source('OBK', declared, parsed, admitted)

        # contract registry
        declared = parsed = admitted = 0
        nulls = {'node_empty': 0, 'node_backslash_n': 0, 'row_truncated': 0}
        for name in self.source_files.get('REG', []):
            path = os.path.join(self.dir, name)
            d, header, raw = split_rows(read_lines(path), '\t')
            declared += d or 0
            parsed += len(raw)
            if (d or 0) != len(raw):
                self.header_gaps[name] = (d or 0) - len(raw)
            for i, f in enumerate(raw):
                if len(f) < 10:
                    nulls['row_truncated'] += 1
                    f = f + [''] * (10 - len(f))
                node = f[3].strip()
                if node == '':
                    nulls['node_empty'] += 1
                    node = None
                elif node == '\\N':
                    nulls['node_backslash_n'] += 1
                    node = None
                x = {'src': 'REG', 'fileorder': (name, i)}
                x['ref'] = f[0]
                x['rawref'] = f[1]
                x['site'] = f[2]
                x['node'] = node
                self._lot_row(f[5])
                x['qty_num'], x['qty_den'] = self._figure(f[4], f[5], 'contract_registry')
                x['eff'] = parse_dt(f[6])
                x['rec'] = parse_dt(f[7])
                x['batch'] = f[8]
                x['note'] = f[9]
                if x['rec'] <= self.as_of:
                    admitted += 1
                    rows.append(x)
                else:
                    self.dq['late_REG'] += 1
        self._count_source('REG', declared, parsed, admitted)
        self.null_forms = nulls

        # legacy intake (fixed width, no header)
        declared = parsed = admitted = 0
        for name in self.source_files.get('LGI', []):
            path = os.path.join(self.dir, name)
            lines = [l for l in read_lines(path) if l.strip()]
            parsed += len(lines)
            for i, line in enumerate(lines):
                x = {'src': 'LGI', 'fileorder': (name, i)}
                x['ref'] = line[0:12].strip()
                x['rawref'] = line[12:26].strip()
                x['site'] = line[26:34].strip()
                x['node'] = None if line[34:40].strip() in ('', '\\N') else line[34:40].strip()
                x['qty_num'], x['qty_den'] = int(line[40:50]), 100
                eff = line[50:64].strip()
                x['eff'] = self.to_utc(x['site'],
                                       '%s-%s-%sT%s:%s:%s' % (eff[:4], eff[4:6], eff[6:8],
                                                             eff[8:10], eff[10:12], eff[12:14]), 0)
                x['rec'] = parse_dt(line[64:78].strip())
                x['batch'] = line[78:84].strip()
                x['note'] = line[84:].strip()
                if x['rec'] <= self.as_of:
                    admitted += 1
                    rows.append(x)
                else:
                    self.dq['late_LGI'] += 1
        self._count_source('LGI', declared, parsed, admitted)

        self.request_rows = rows

    def _lot_row(self, unit):
        if unit and 'lot' in unit:
            self.dq['lot_unit_rows'] += 1

    # ------------------------------------------------------------------
    # cycles
    # ------------------------------------------------------------------
    def cycle_index(self, n):
        """The 0 based index of cycle number n (C01 -> 0)."""
        return n - 1

    def cycle_name(self, idx):
        return 'C%02d' % (idx + 1)

    def cycle_start(self, site, idx):
        month = idx // 2 + 1
        day = self.cycle_start_days[idx % 2]
        hh, mm, ss = self.cycle_start_time.split(':')
        stamp = '%04d-%02d-%02dT%s' % (self.horizon_year, month, day,
                                       self.cycle_start_time)
        return self.to_utc(site, stamp, 0)

    def horizon_end(self, site):
        return self.to_utc(site, '%04d-01-01T%s' % (self.close_year,
                                                   self.cycle_start_time), 0)

    def build_cycles(self):
        self.n_cycles = int(self.last_cycle[1:]) - int(self.first_cycle[1:]) + 1
        self.first_idx = int(self.first_cycle[1:]) - 1
        self.cycle_bounds = {}
        for site in self.sites:
            starts = []
            for i in range(self.first_idx, self.first_idx + self.n_cycles):
                starts.append(self.cycle_start(site, i))
            self.cycle_bounds[site] = starts
        self.horizon_ends = {s: self.horizon_end(s) for s in self.sites}

    def cycle_of(self, site, instant):
        starts = self.cycle_bounds[site]
        if instant < starts[0] or instant >= self.horizon_ends[site]:
            return None
        lo, hi = 0, len(starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if starts[mid] <= instant:
                lo = mid
            else:
                hi = mid - 1
        return lo

    def cutover_start(self, site):
        """The start of the cutover cycle at a site."""
        idx = int(self.cutover_cycle[1:]) - 1
        return self.cycle_start(site, idx)

    # ------------------------------------------------------------------
    # requests
    # ------------------------------------------------------------------
    def row_identity(self, row):
        cid = self.resolve_customer(row['rawref'], row['eff'])
        row['cid'] = cid
        return cid

    def group_requests(self):
        """Collapse the admitted rows into requests."""
        for row in self.request_rows:
            self.row_identity(row)
        by_key = defaultdict(list)
        for row in self.request_rows:
            key = ('C', row['cid']) if row['cid'] else ('R', row['rawref'])
            by_key[(key, row['site'])].append(row)

        window = self.collapse_window * 60
        requests = []
        for key, rows in by_key.items():
            rows.sort(key=lambda r: (r['eff'], r['src'], r['ref'], r['fileorder']))
            groups = []
            cur = [rows[0]]
            for r in rows[1:]:
                if (r['eff'] - cur[0]['eff']).total_seconds() <= window:
                    cur.append(r)
                else:
                    groups.append(cur)
                    cur = [r]
            groups.append(cur)
            for g in groups:
                requests.append(self._make_request(key, g))
        self.requests = requests
        return requests

    def _payload(self, row):
        return (row['cid'], row['site'], row['node'], row['qty_num'], row['qty_den'], row['eff'])

    def _make_request(self, key, rows):
        """One request: pick the governing row of each source."""
        by_src = defaultdict(list)
        for r in rows:
            by_src[r['src']].append(r)
        governing = {}
        for src, rs in by_src.items():
            by_ref = defaultdict(list)
            for r in rs:
                by_ref[r['ref']].append(r)
            reps = []
            for ref, same in by_ref.items():
                if len(same) > 1:
                    payloads = set(self._payload(r) for r in same)
                    if len(payloads) == 1:
                        self.tally['duplicate_identical'] += len(same) - 1
                    else:
                        self.tally['duplicate_conflicting'] += len(same) - 1
                    best = sorted(same, key=lambda r: (r['rec'], r['ref'], r['fileorder']))[-1]
                else:
                    best = same[0]
                reps.append(best)
            governing[src] = sorted(reps, key=lambda r: (r['rec'], r['ref'], r['fileorder']))[-1]
        self.tally['cross_source_collapsed'] += len(governing) - 1
        req = {'rows': rows, 'governing': governing, 'key': key,
               'site': rows[0]['site']}
        req['sources'] = sorted(governing.keys())
        return req

    # ------------------------------------------------------------------
    # endorsement
    # ------------------------------------------------------------------
    def has_role(self, approver, scope, instant):
        best = None
        for row in self.roles.get(approver, []):
            if row['scope'] not in (scope, 'any'):
                continue
            eff = parse_dt(row['effective_utc'])
            exp = parse_dt(row['expires_utc'])
            if not (eff <= instant < exp):
                continue
            if best is None or int(row['revision_seq']) > int(best['revision_seq']):
                best = row
        return best is not None

    def endorse(self, apl, scope):
        entry = self.audit_by_apl.get(apl)
        if not entry:
            return False
        return self.has_role(entry['fields'].get('approver'), scope, entry['instant'])

    # ------------------------------------------------------------------
    # notices and events
    # ------------------------------------------------------------------
    def load_changes(self):
        notices = []
        declared = parsed = admitted = 0
        for name in self.source_files.get('AMD', []):
            path = os.path.join(self.dir, name)
            for line in read_lines(path):
                if not line.strip():
                    continue
                parsed += 1
                d = json.loads(line)
                if parse_dt(d['recorded_utc']) <= self.as_of:
                    admitted += 1
                    notices.append(d)
        self._count_source('AMD', 0, parsed, admitted)

        events = []
        parsed = admitted = 0
        for name in self.source_files.get('EVT', []):
            path = os.path.join(self.dir, name)
            for line in read_lines(path):
                if not line.strip():
                    continue
                parsed += 1
                d = json.loads(line)
                if parse_dt(d['recorded_utc']) <= self.as_of:
                    admitted += 1
                    events.append(d)
        self._count_source('EVT', 0, parsed, admitted)

        self.notices = notices
        self.events = events
        self.notices_by_ref = defaultdict(list)
        for n in notices:
            self.notices_by_ref[n['request_ref']].append(n)
        self.events_by_ref = defaultdict(list)
        for e in events:
            self.events_by_ref[e['request_ref']].append(e)

    def chain_cycles(self, notices):
        """True when a supersedes chain visits a notice twice."""
        ids = {n['notice_id']: n for n in notices}
        for start in ids:
            seen = set()
            cur = start
            while cur in ids:
                if cur in seen:
                    return True
                seen.add(cur)
                nxt = ids[cur].get('supersedes')
                if not nxt:
                    break
                cur = nxt
        return False

    # ------------------------------------------------------------------
    # field provenance
    # ------------------------------------------------------------------
    def source_rank(self):
        """The source order the contract names: order book, registry, intake."""
        if getattr(self, '_rank', None):
            return self._rank
        names = []
        text = ' '.join(self._read_md('provenance_rules.md'))
        m = re.search(r'in the order ([^.]*?)\.\s', text)
        if m:
            names = [n.strip().strip('`') for n in m.group(1).split(',')]
        by_name = {}
        for code in self.source_codes:
            by_name[self.source_name(code)] = code
            by_name[self.source_name(code).replace('_', ' ')] = code
        rank = []
        for name in names:
            code = by_name.get(name) or by_name.get(name.replace(' ', '_'))
            if code and code not in rank:
                rank.append(code)
        for code in ('OBK', 'REG', 'LGI'):
            if code not in rank and code in self.source_codes:
                rank.append(code)
        self._rank = rank
        return rank

    def apply_notices(self, req):
        """Attach the governing amendment notices to a request."""
        refs = set(r['ref'] for r in req['rows'])
        notices = []
        for ref in refs:
            notices.extend(self.notices_by_ref.get(ref, []))
        req['unresolvable_chain'] = False
        if not notices:
            req['notices'] = {}
            return
        if self.chain_cycles(notices):
            self.tally['amendment_chains_unresolvable'] += 1
            req['unresolvable_chain'] = True
            req['notices'] = {}
            return
        latest_rec = max(r['rec'] for r in req['rows'])
        survivors = []
        for n in notices:
            if parse_dt(n['recorded_utc']) <= latest_rec:
                self.tally['amendments_early'] += 1
                continue
            if self.is_retracted(n['notice_id'], 'notice'):
                self.tally['amendments_retracted'] += 1
                continue
            if not self.variant.get('apply_unendorsed_notices') and \
                    not self.endorse(n['approval_ref'], n['field']):
                self.tally['amendments_unendorsed'] += 1
                continue
            survivors.append(n)
        superseded = set()
        for n in survivors:
            if n.get('supersedes'):
                superseded.add(n['supersedes'])
        final = [n for n in survivors if n['notice_id'] not in superseded]
        by_field = defaultdict(list)
        for n in final:
            by_field[n['field']].append(n)
        chosen = {}
        for field, ns in by_field.items():
            chosen[field] = sorted(ns, key=lambda n: (n['recorded_utc'], n['notice_id']))[-1]
            self.tally['amendments_applied'] += 1
        req['notices'] = chosen

    def resolve_fields(self, req):
        """Field by field precedence, then the amendments."""
        site = req['site']
        earliest = min(r['eff'] for r in req['rows'])
        req['earliest_eff'] = earliest
        req['side'] = 'from' if earliest >= self.cutover_start(site) else 'before'
        gov = req['governing']
        order = self.source_rank()

        # reported reference: the highest ranked source present
        for code in order:
            if code in gov:
                req['ref'] = gov[code]['ref']
                break
        else:
            req['ref'] = req['rows'][0]['ref']

        def pick(field):
            key = (req['side'] + '_cutover', field)
            first = self.precedence.get(key)
            chain = []
            if first:
                # map the source name in the table to a code
                for code in order:
                    if self.source_name(code) == first:
                        chain.append(code)
                        break
            chain.extend(order)
            seen = set()
            for code in chain:
                if code in seen or code not in gov:
                    continue
                seen.add(code)
                yield code

        # node
        node = None
        for code in pick('node'):
            if gov[code]['node'] is not None:
                node = gov[code]['node']
                break
        # effective
        eff = None
        for code in pick('effective'):
            eff = gov[code]['eff']
            break
        # quantity
        qty = None
        for code in pick('quantity'):
            qty = (gov[code]['qty_num'], gov[code]['qty_den'])
            break

        req['node'] = node
        req['eff'] = eff
        req['qty'] = qty

        # amendments
        chosen = req.get('notices') or {}
        if 'quantity' in chosen:
            v = chosen['quantity']['value']
            req['qty'] = self._figure(str(v), 'wafers', 'order_book')
        if 'node' in chosen:
            req['node'] = str(chosen['node']['value']).strip() or None
        if 'effective' in chosen:
            req['eff'] = parse_dt(chosen['effective']['value'])

    def source_name(self, code):
        return self.props.get('source.%s.name' % code, code)

    # ------------------------------------------------------------------
    # state machine
    # ------------------------------------------------------------------
    def apply_events(self, req):
        refs = set(r['ref'] for r in req['rows'])
        events = []
        for ref in refs:
            events.extend(self.events_by_ref.get(ref, []))
        events.sort(key=lambda e: (e['recorded_utc'], e['version'], e['event_id']))
        state = 'approved'
        maxver = 0
        seen_versions = set()
        for e in events:
            if e['version'] <= maxver:
                self.tally['stale_events'] += 1
                continue
            if e['version'] in seen_versions:
                self.tally['duplicate_version_events'] += 1
            seen_versions.add(e['version'])
            legal = False
            act = e['action']
            if act == 'hold' and state == 'approved':
                state = 'held'
                legal = True
            elif act == 'release' and state == 'held':
                state = 'approved'
                legal = True
            elif act == 'withdraw' and state in ('approved', 'held'):
                state = 'withdrawn'
                legal = True
            elif act == 'reject' and state == 'approved':
                state = 'rejected'
                legal = True
            elif act == 'reinstate' and state == 'withdrawn':
                ok = False
                if 'authority_ref' in e:
                    if isinstance(e['authority_ref'], str):
                        entry = self.audit_by_apl.get(e['authority_ref'])
                        if entry:
                            ok = self.has_role(entry['fields'].get('approver'),
                                               'state', entry['instant'])
                else:
                    entry = self.audit_by_ref.get(e['event_id'])
                    if entry:
                        ok = self.has_role(entry['fields'].get('approver'),
                                           'state', entry['instant'])
                if ok:
                    state = 'approved'
                    legal = True
                else:
                    legal = False
            elif state == 'rejected':
                legal = False
            if not legal:
                self.tally['illegal_transitions'] += 1
            maxver = e['version']
        req['state'] = state

    # ------------------------------------------------------------------
    # substitution walk
    # ------------------------------------------------------------------
    def site_cycle_capacity(self, site, idx):
        """(capacity, qualified node set) of a site cycle."""
        name = self.cycle_name(idx)
        rows = self.capacity_rows.get((site, name), [])
        start = self.cycle_bounds[site][idx]
        groups = set(r['tool_group'] for r in rows)
        cap = 0
        qualified = set()
        for g in sorted(groups):
            abs_rows = [r for r in rows
                        if r['tool_group'] == g and r['basis'] == 'absolute'
                        and r['_eff'] <= start]
            if not abs_rows:
                continue
            base = max(abs_rows, key=lambda r: (r['_eff'], int(r['revision_seq'])))
            if base['status'] != 'online':
                continue
            value = base['_value']
            if base['unit'] and 'lot' in base['unit']:
                value = value * self.lot_size.get('capacity', 25)
            deltas = [r for r in rows
                      if r['tool_group'] == g and r['basis'] == 'delta'
                      and base['_eff'] <= r['_eff'] <= start]
            deltas.sort(key=lambda r: (r['_eff'], int(r['revision_seq'])))
            for d in deltas:
                dv = d['_value']
                if d['unit'] and 'lot' in d['unit']:
                    dv = dv * self.lot_size.get('capacity', 25)
                value += dv
            if value > 0:
                cap += value
                qualified.update(n for n in base['nodes'].split('|') if n)
        return cap, qualified

    def edges_in_force(self, site, idx):
        start = self.cycle_bounds[site][idx]
        name = self.cycle_name(idx)
        out = defaultdict(list)
        for (s, cyc, frm, to), rows in self.sub_rows.items():
            if s != site or cyc != name:
                continue
            elig = [r for r in rows if r['_eff'] <= start]
            if not elig:
                continue
            best = max(elig, key=lambda r: (r['_eff'], int(r['revision_seq'])))
            if best['status'] == 'in_force':
                out[frm].append((int(best['_factor']), to))
        for frm in out:
            out[frm].sort(key=lambda e: (e[0], e[1]))
        return out

    def walk(self, site, idx, node, qualified, edges):
        """Returns (served_node, hops, numerator, denominator, reason_or_None)."""
        if node is None:
            return ('', 0, 1, 1, None)
        if node in qualified:
            return (node, 0, 1, 1, None)
        cur = node
        seen = set([cur])
        num = 1
        den = 1
        hops = 0
        while hops < self.max_hops:
            cands = edges.get(cur, [])
            if not cands:
                return ('', hops, num, den, 'NO_QUALIFIED_NODE')
            factor, target = cands[0]
            num *= factor
            den *= 100
            hops += 1
            cur = target
            if cur in qualified:
                return (cur, hops, num, den, None)
            if cur in seen:
                return ('', hops, num, den, 'UNRESOLVABLE_SUB_CYCLE')
            seen.add(cur)
        return ('', hops, num, den, 'NO_QUALIFIED_NODE')

    # ------------------------------------------------------------------
    # ceilings, status, segment
    # ------------------------------------------------------------------
    def governing_ceiling(self, cid, epoch, idx, site):
        key = (cid, str(epoch))
        start = self.cycle_bounds[site][idx]
        rows = [r for r in self.ceilings.get(key, []) if r['_eff'] <= start]
        if not rows:
            return None
        return max(rows, key=lambda r: (r['_eff'], int(r['revision_seq'])))

    def governing_status(self, cid, epoch, idx, site):
        start = self.cycle_bounds[site][idx]
        rows = [r for r in self.master_by_id.get(cid, [])
                if r['epoch_seq'] == str(epoch)]
        elig = [r for r in rows if parse_dt(r['effective_utc']) <= start]
        if not elig:
            return None
        best = max(elig, key=lambda r: (r['effective_utc'], int(r['revision_seq'])))
        return best['status']

    def segment_of(self, cid, epoch):
        for r in self.master_by_id.get(cid, []):
            if r['epoch_seq'] == str(epoch):
                return r['segment']
        return None

    # ------------------------------------------------------------------
    # commitments
    # ------------------------------------------------------------------
    def agreement_due(self, aid, idx):
        rows = self.agreements.get(aid, [])
        if not rows:
            return False
        row = rows[0]
        first = int(row['first_cycle'][1:]) - 1
        until = int(row['until_cycle'][1:]) - 1
        if idx < first or idx > until:
            return False
        rec = row['recurrence']
        if rec == 'every_cycle':
            return True
        if rec == 'first_cycle_of_month':
            return idx % 2 == 0
        if rec == 'alternate_from_first':
            return (idx - first) % 2 == 0
        return True

    def agreement_floor(self, aid, idx):
        rows = self.agreements.get(aid, [])
        if not rows:
            return None
        site = rows[0]['site']
        start = self.cycle_bounds[site][idx]
        elig = [r for r in rows if r['_eff'] <= start]
        if not elig:
            return None
        best = max(elig, key=lambda r: (r['_eff'], int(r['revision_seq'])))
        num, den = self._figure(best['floor'], best['unit'], 'commitments')
        return (num, den)

    def agreement_rank(self, aid, idx):
        rows = self.priority.get(aid, [])
        if not rows:
            return None
        site = self.agreements[aid][0]['site']
        elig = [r for r in rows if r['_eff'] <= self.cycle_bounds[site][idx]]
        if not elig:
            return None
        best = max(elig, key=lambda r: (r['_eff'], int(r['revision_seq'])))
        return int(best['priority_rank'])

    def agreement_site(self, aid):
        return self.agreements[aid][0]['site']

    def obligation_cycles(self):
        """The cycles each agreement is due in, once exceptions are applied."""
        due = {}
        self.tally['exceptions_applied'] = 0
        self.tally['exceptions_unendorsed'] = 0
        self.tally['exceptions_retracted'] = 0
        for aid in self.agreements:
            cycles = set()
            for idx in range(self.first_idx, self.first_idx + self.n_cycles):
                if self.agreement_due(aid, idx):
                    cycles.add(idx)
            for exc in self.exceptions.get(aid, []):
                if not self.exception_applies(exc):
                    continue
                src = int(exc['cycle'][1:]) - 1
                if exc['action'] == 'skip':
                    cycles.discard(src)
                elif exc['action'] == 'move_to' and exc['target_cycle']:
                    tgt = int(exc['target_cycle'][1:]) - 1
                    if self.first_idx <= tgt < self.first_idx + self.n_cycles:
                        cycles.discard(src)
                        cycles.add(tgt)
            due[aid] = cycles
        return due

    def exception_applies(self, exc):
        if self.is_retracted(exc['exception_id'], 'exception'):
            self.tally['exceptions_retracted'] += 1
            return False
        if not self.endorse(exc['approval_ref'], 'commitment'):
            self.tally['exceptions_unendorsed'] += 1
            return False
        self.tally['exceptions_applied'] += 1
        return True

    # ------------------------------------------------------------------
    # the apportionment
    # ------------------------------------------------------------------
    def apportion(self, claims, floors, capacity):
        """Return (grants, level, residual) for one site cycle."""
        if not claims:
            return {}, 0, capacity
        grants = {k: floors.get(k, 0) for k in claims}
        total_claims = sum(claims.values())
        maxclaim = max(claims.values())
        if maxclaim <= 0:
            return grants, 0, capacity
        if total_claims <= capacity:
            level = maxclaim
        else:
            lo, hi = 0, maxclaim
            while lo < hi:
                mid = (lo + hi + 1) // 2
                tot = 0
                for k, c in claims.items():
                    tot += max(floors.get(k, 0), min(c, mid))
                if tot <= capacity:
                    lo = mid
                else:
                    hi = mid - 1
            level = lo
        for k in claims:
            grants[k] = max(floors.get(k, 0), min(claims[k], level))
        used = sum(grants.values())
        rest = capacity - used
        if rest <= 0:
            return grants, level, 0
        unmet = {k: claims[k] - grants[k] for k in claims if claims[k] - grants[k] > 0}
        if not unmet:
            return grants, level, rest
        order = sorted(unmet.keys(),
                       key=lambda k: (-unmet[k], self.eff_of[k], self.id_of[k],
                                      self.ref_of[k]))
        guard = 0
        while rest > 0 and unmet:
            progressed = False
            for k in order:
                if rest <= 0:
                    break
                if unmet.get(k, 0) <= 0:
                    continue
                grants[k] += 1
                unmet[k] -= 1
                rest -= 1
                progressed = True
                self.tally['remainder_distributed'] += 1
            guard += 1
            if not progressed or guard > 100000:
                break
        return grants, level, capacity - sum(grants.values())

    # ------------------------------------------------------------------
    # the whole derivation
    # ------------------------------------------------------------------
    def derive(self):
        self.build_cycles()
        self.group_requests()
        self.load_changes()

        for req in self.requests:
            self.apply_notices(req)
            self.resolve_fields(req)
            self.apply_events(req)

        ledger = []
        out_of_scope = []
        for req in self.requests:
            req['identity'] = None
            if req['key'][0][0] == 'R':
                req['reason_oos'] = 'UNKNOWN_CUSTOMER'
                out_of_scope.append(req)
                self.dq['unknown_customer_rows'] += 1
                continue
            cid = req['key'][0][1]
            epoch = self.epoch_of(cid, req['eff'])
            if epoch is None:
                req['reason_oos'] = 'UNKNOWN_CUSTOMER'
                out_of_scope.append(req)
                self.dq['unknown_customer_rows'] += 1
                continue
            req['cid'] = cid
            req['epoch'] = epoch
            req['identity'] = '%s#%d' % (cid, epoch)
            req['segment'] = self.segment_of(cid, epoch)
            first_epoch = min(int(r['epoch_seq']) for r in self.master_by_id.get(cid, []))
            if epoch != first_epoch:
                self.tally['epoch_reassignments'] += 1
            idx = self.cycle_of(req['site'], req['eff'])
            req['cycle_idx'] = idx
            if idx is None:
                req['reason_oos'] = 'OUT_OF_HORIZON'
                out_of_scope.append(req)
                self.dq['out_of_horizon_rows'] += 1
                continue
            ledger.append(req)

        for req in ledger:
            self.cutover_sides[req['side']] += 1

        self.ref_of = {}
        self.eff_of = {}
        self.id_of = {}
        for req in ledger:
            key = id(req)
            self.ref_of[key] = req['ref']
            self.eff_of[key] = req['eff']
            self.id_of[key] = req['identity']

        self.remainder_units = 0
        self.remainder_cells = 0
        self.lots = {s: [] for s in self.sites}
        self.granted_to_date = defaultdict(int)
        self.deficit_to_date = defaultdict(int)
        self.obligations = self.obligation_cycles()
        records = []
        self.cycle_rows = defaultdict(list)
        for req in ledger:
            self.cycle_rows[(req['site'], req['cycle_idx'])].append(req)
        for site in self.sites:
            for idx in range(self.first_idx, self.first_idx + self.n_cycles):
                records.extend(self.run_cycle(site, idx))
        self.ledger = [r for r in records if r is not None]
        return self.ledger, out_of_scope

    # ------------------------------------------------------------------
    # one site cycle
    # ------------------------------------------------------------------
    def run_cycle(self, site, idx):
        out = []
        capacity, qualified = self.site_cycle_capacity(site, idx)
        edges = self.edges_in_force(site, idx)
        start = self.cycle_bounds[site][idx]
        reqs = self.cycle_rows.get((site, idx), [])

        # per request derivation
        for req in reqs:
            served, hops, num, den, wreason = self.walk(site, idx, req['node'],
                                                       qualified, edges)
            qnum, qden = req['qty']
            req['quantity_equiv'] = half_up(qnum * num, qden * den)
            ceil_row = self.governing_ceiling(req['cid'], req['epoch'], idx, site)
            if ceil_row is None:
                req['ceiling_equiv'] = 0
            else:
                req['ceiling_equiv'] = half_up(ceil_row['_num'] * num,
                                               ceil_row['_den'] * den)
            req['ceiling_row'] = ceil_row
            req['hops'] = hops
            req['served'] = served
            req['num'] = num
            req['den'] = den
            self.substitution_hops[str(hops)] += 1
            if wreason == 'NO_QUALIFIED_NODE':
                self.tally['no_qualified_node'] += 1
            elif wreason == 'UNRESOLVABLE_SUB_CYCLE':
                self.tally['substitution_cycles'] += 1
            status = self.governing_status(req['cid'], req['epoch'], idx, site)
            req['status'] = status
            # the reasons that apply, and the highest of them in the order the
            # reason vocabulary declares
            applicable = []
            if req['node'] is None:
                applicable.append('NODE_NOT_STATED')
            if req.get('unresolvable_chain'):
                applicable.append('UNRESOLVABLE_CHAIN')
            if wreason:
                applicable.append(wreason)
            if status == 'suspended':
                applicable.append('CUSTOMER_SUSPENDED')
            if req['state'] == 'rejected':
                applicable.append('REJECTED')
            elif req['state'] == 'withdrawn':
                applicable.append('WITHDRAWN')
            elif req['state'] == 'held':
                applicable.append('ON_HOLD')
            cap_zero = ceil_row is not None and req['ceiling_equiv'] <= 0
            if cap_zero:
                applicable.append('CAP_ZERO')
            reason = None
            for code in self.reason_precedence:
                if code in applicable:
                    reason = code
                    break
            req['pre_reason'] = reason

        # claiming requests
        for r in reqs:
            if r['pre_reason'] == 'CAP_ZERO':
                self.tally['ceiling_zero'] += 1
        claiming = [r for r in reqs if r['pre_reason'] is None]

        # carry forward attaches to the earliest claiming request
        age = self.withheld['carry_forward_age']
        if 'carry_age' in self.variant:
            age = self.variant['carry_age']
        no_carry = bool(self.variant.get('no_carry_forward'))
        pool_key = defaultdict(list)
        if not no_carry:
            if age != 'unbounded':
                for lot in self.lots[site]:
                    if idx - lot['origin'] <= age and lot['origin'] < idx:
                        pool_key[lot['identity']].append(lot)
            else:
                for lot in self.lots[site]:
                    if lot['origin'] < idx:
                        pool_key[lot['identity']].append(lot)
        carrier = {}
        by_identity = defaultdict(list)
        for r in claiming:
            by_identity[(r['identity'], )].append(r)
        for ident, group in by_identity.items():
            group.sort(key=lambda r: (r['eff'], r['ref']))
            carrier[ident[0]] = group[0]
        carried_in = {}
        for r in reqs:
            carried_in[id(r)] = 0
        for ident, lots in pool_key.items():
            c = carrier.get(ident)
            if c is None:
                continue
            carried_in[id(c)] = sum(l['amt'] for l in lots)
            c['carried_lots'] = lots

        # claims
        claims = {}
        for r in claiming:
            ci = carried_in[id(r)]
            r['carried_in'] = ci
            if r['ceiling_row'] is None:
                claim = r['quantity_equiv'] + ci
                r['ceiling_binding'] = False
            else:
                claim = min(r['quantity_equiv'] + ci, r['ceiling_equiv'])
                r['ceiling_binding'] = (r['quantity_equiv'] + ci) > claim
            r['claim'] = claim
            if claim > 0:
                claims[id(r)] = claim
            if r['ceiling_binding'] and claim > 0:
                self.tally['ceiling_binding'] += 1

        # commitments
        floors = {}
        obligations = []
        for aid, cycles in self.obligations.items():
            if idx not in cycles:
                continue
            if self.agreements[aid][0]['site'] != site:
                continue
            fl = self.agreement_floor(aid, idx)
            if fl is None:
                continue
            cid = self.agreements[aid][0]['customer_id']
            covered = None
            for r in sorted(claiming, key=lambda r: (r['eff'], r['ref'])):
                if r['cid'] == cid:
                    covered = r
                    break
            rank = self.agreement_rank(aid, idx)
            if rank is None:
                rank = self.unranked_rank
            if covered is None:
                self.tally['floors_unmatched'] += 1
                continue
            obligations.append((rank, aid, covered, fl))
        obligations.sort(key=lambda o: (o[0], o[1]))
        remaining = capacity
        for rank, aid, covered, fl in obligations:
            fnum, fden = fl
            floor = half_up(fnum * covered['num'], fden * covered['den'])
            claim = claims.get(id(covered), 0)
            already = floors.get(id(covered), 0)
            allowed = min(floor, claim, remaining, max(0, claim - already))
            floors[id(covered)] = already + allowed
            remaining -= allowed
            if allowed == floor:
                self.tally['floors_honoured_full'] += 1
            else:
                self.tally['floors_honoured_short'] += 1

        # apportion
        grants, level, residual = self.apportion(claims, floors, capacity)

        # outcomes, lots, running totals
        cycle_granted = 0
        gtd = {}
        dtd = {}
        for r in reqs:
            g = grants.get(id(r), 0)
            if r['pre_reason'] is not None:
                g = 0
            r['grant'] = g
            claim = r.get('claim', 0)
            if r['pre_reason'] is not None:
                outcome = 'EXCLUDED'
                reason = r['pre_reason']
            elif claim > 0 and g == claim:
                outcome = 'FULL'
                reason = 'NONE'
            elif g > 0 and g < claim:
                outcome = 'PARTIAL'
                reason = 'NONE'
            elif claim > 0 and g == 0:
                outcome = 'ZERO'
                reason = 'NONE'
            else:
                outcome = 'EXCLUDED'
                reason = 'CAP_ZERO' if r['pre_reason'] == 'CAP_ZERO' else 'NONE'
            r['outcome'] = outcome
            r['reason'] = reason

            # discharge
            deficit = claim - g
            new_lot = 0
            carried_out = 0
            if r['pre_reason'] is None:
                ci = r.get('carried_in', 0)
                carried_part = min(ci, claim)
                lots = r.get('carried_lots', [])
                pay = min(g, carried_part)
                left = pay
                for lot in sorted(lots, key=lambda l: l['origin']):
                    if left <= 0:
                        break
                    take = min(left, lot['amt'])
                    lot['amt'] -= take
                    left -= take
                current_part = claim - carried_part
                paid_current = g - pay
                new_lot = current_part - paid_current
                if new_lot < 0:
                    new_lot = 0
                if carried_part > 0 or new_lot > 0:
                    pass
                r['new_lot'] = new_lot
                # what survives into the next cycle from this row
                survive = sum(l['amt'] for l in lots
                              if self.lot_survives(idx, l))
                carried_out = survive + (new_lot if self.new_lot_survives(idx) else 0)
            else:
                r['new_lot'] = 0
                carried_out = 0
                deficit = 0
            r['deficit'] = deficit
            r['carried_out'] = carried_out
            key = (r['identity'], site)
            self.granted_to_date[key] += g
            self.deficit_to_date[key] += deficit
            gtd[key] = self.granted_to_date[key]
            dtd[key] = self.deficit_to_date[key]
            cycle_granted += g

        # create the new lots
        if not no_carry:
            for r in reqs:
                if r.get('new_lot', 0) > 0 and r['pre_reason'] is None:
                    self.lots[site].append({'origin': idx, 'amt': r['new_lot'],
                                            'identity': r['identity'],
                                            'owner': id(r)})

        # end of cycle: expire or clear
        if residual > 0 and not self.variant.get('no_clearing'):
            self.tally['resets'] += 1
            self.tally['lots_cleared'] += len(self.lots[site])
            self.lots[site] = []
        else:
            if age == 'unbounded':
                pass
            else:
                dead = [l for l in self.lots[site] if idx - l['origin'] >= age]
                self.tally['lots_expired'] += len(dead)
                self.lots[site] = [l for l in self.lots[site]
                                   if idx - l['origin'] < age]

        # build the ledger rows
        for r in reqs:
            key = (r['identity'], site)
            out.append({
                'site': site,
                'cycle': self.cycle_name(idx),
                'request_ref': r['ref'],
                'customer': r['identity'],
                'segment': r['segment'],
                'requested_node': r['node'] or '',
                'served_node': r['served'],
                'hops': r['hops'],
                'quantity_equiv': r['quantity_equiv'],
                'carried_in_equiv': r.get('carried_in', 0) if r['pre_reason'] is None else 0,
                'ceiling_equiv': r['ceiling_equiv'],
                'claim_equiv': r.get('claim', 0) if r['pre_reason'] is None else 0,
                'floor_equiv': floors.get(id(r), 0),
                'granted_equiv': r['grant'],
                'granted_wafers': self.granted_wafers(r['grant'], r['num'], r['den']),
                'deficit_equiv': r['deficit'],
                'carried_out_equiv': r['carried_out'],
                'granted_to_date_equiv': gtd.get(key, self.granted_to_date[key]),
                'deficit_to_date_equiv': dtd.get(key, self.deficit_to_date[key]),
                'outcome': r['outcome'],
                'reason': r['reason'],
            })
        self.cycle_stats[(site, idx)] = {
            'capacity': capacity, 'level': level, 'granted': cycle_granted,
            'residual': capacity - cycle_granted,
            'floor_total': sum(floors.values()),
            'request_count': len(reqs),
        }
        self.remainder_stats[(site, idx)] = self.tally['remainder_distributed']
        self.remainder_units += self.tally['remainder_distributed']
        if self.tally['remainder_distributed']:
            self.remainder_cells += 1
        self.tally['remainder_distributed'] = 0
        return out

    def lot_survives(self, idx, lot):
        age = self.variant.get('carry_age', self.withheld['carry_forward_age'])
        if age == 'unbounded':
            return True
        return (idx + 1) - lot['origin'] <= age

    def new_lot_survives(self, idx):
        age = self.variant.get('carry_age', self.withheld['carry_forward_age'])
        if age == 'unbounded':
            return True
        return 1 <= age

    def granted_wafers(self, grant, num, den):
        if grant == 0:
            return 0
        if num == 0:
            return 0
        return (grant * den) // num

    # ------------------------------------------------------------------
    # documents
    # ------------------------------------------------------------------
    def out_of_scope_rows(self, out_of_scope):
        rows = []
        for req in out_of_scope:
            if req['key'][0][0] == 'R':
                customer = req['key'][0][1]
            else:
                customer = req['identity']
            rows.append({
                'request_ref': req['ref'],
                'customer': customer,
                'site': req['site'],
                'reason': req['reason_oos'],
            })
        rows.sort(key=lambda r: (r['request_ref'], r['customer'], r['site']))
        return rows

    def region_document(self, site, ledger, out_of_scope):
        cycles = []
        for idx in range(self.first_idx, self.first_idx + self.n_cycles):
            st = self.cycle_stats[(site, idx)]
            cycles.append({
                'cycle': self.cycle_name(idx),
                'capacity_equiv': st['capacity'],
                'fill_level': st['level'],
                'floor_total_equiv': st['floor_total'],
                'granted_equiv': st['granted'],
                'residual_equiv': st['residual'],
                'request_count': st['request_count'],
                'binding': st['residual'] == 0,
            })
        rows = [r for r in ledger if r['site'] == site]
        rows = sorted(rows, key=lambda r: (r['cycle'], r['customer'], r['request_ref']))
        oos = [r for r in out_of_scope if r['site'] == site]
        totals = {
            'ledger_rows': len(rows),
            'granted_equiv': sum(r['granted_equiv'] for r in rows),
            'claim_equiv': sum(r['claim_equiv'] for r in rows),
            'deficit_equiv': sum(r['deficit_equiv'] for r in rows),
            'capacity_equiv': sum(c['capacity_equiv'] for c in cycles),
            'residual_equiv': sum(c['residual_equiv'] for c in cycles),
        }
        return {
            'site': site,
            'as_of': self.as_of_text,
            'cycles': cycles,
            'ledger': rows,
            'out_of_scope': oos,
            'totals': totals,
        }

    def segment_document(self, segment, ledger):
        rows = [r for r in ledger if r['segment'] == segment]
        sites = []
        for site in self.sites:
            srows = [r for r in rows if r['site'] == site]
            sites.append({
                'site': site,
                'granted_equiv': sum(r['granted_equiv'] for r in srows),
                'claim_equiv': sum(r['claim_equiv'] for r in srows),
                'deficit_equiv': sum(r['deficit_equiv'] for r in srows),
                'ledger_rows': len(srows),
            })
        cycles = []
        for idx in range(self.first_idx, self.first_idx + self.n_cycles):
            crows = [r for r in rows if r['cycle'] == self.cycle_name(idx)]
            cycles.append({
                'cycle': self.cycle_name(idx),
                'granted_equiv': sum(r['granted_equiv'] for r in crows),
                'claim_equiv': sum(r['claim_equiv'] for r in crows),
                'deficit_equiv': sum(r['deficit_equiv'] for r in crows),
                'ledger_rows': len(crows),
            })
        outcome_counts = {o: 0 for o in self.outcome_names}
        reason_counts = defaultdict(int)
        for r in rows:
            outcome_counts[r['outcome']] += 1
            reason_counts[r['reason']] += 1
        return {
            'segment': segment,
            'as_of': self.as_of_text,
            'sites': sites,
            'cycles': cycles,
            'outcome_counts': outcome_counts,
            'reason_counts': dict(reason_counts),
            'totals': {
                'granted_equiv': sum(r['granted_equiv'] for r in rows),
                'claim_equiv': sum(r['claim_equiv'] for r in rows),
                'deficit_equiv': sum(r['deficit_equiv'] for r in rows),
                'ledger_rows': len(rows),
                'customers': len(set(r['customer'] for r in rows)),
            },
        }

    def summary_document(self, region_docs, segment_docs, ledger, out_of_scope):
        sites = []
        for site in self.sites:
            doc = region_docs[site]
            sites.append({
                'site': site,
                'capacity_equiv': doc['totals']['capacity_equiv'],
                'granted_equiv': doc['totals']['granted_equiv'],
                'claim_equiv': doc['totals']['claim_equiv'],
                'deficit_equiv': doc['totals']['deficit_equiv'],
                'residual_equiv': doc['totals']['residual_equiv'],
                'ledger_rows': doc['totals']['ledger_rows'],
            })
        segments = [{
            'segment': d['segment'],
            'granted_equiv': d['totals']['granted_equiv'],
            'claim_equiv': d['totals']['claim_equiv'],
            'deficit_equiv': d['totals']['deficit_equiv'],
            'ledger_rows': d['totals']['ledger_rows'],
        } for d in segment_docs]
        cycles = []
        for idx in range(self.first_idx, self.first_idx + self.n_cycles):
            name = self.cycle_name(idx)
            cap = sum(self.cycle_stats[(s, idx)]['capacity'] for s in self.sites)
            gr = sum(self.cycle_stats[(s, idx)]['granted'] for s in self.sites)
            res = sum(self.cycle_stats[(s, idx)]['residual'] for s in self.sites)
            crows = [r for r in ledger if r['cycle'] == name]
            cycles.append({
                'cycle': name,
                'capacity_equiv': cap,
                'granted_equiv': gr,
                'claim_equiv': sum(r['claim_equiv'] for r in crows),
                'deficit_equiv': sum(r['deficit_equiv'] for r in crows),
                'residual_equiv': res,
                'ledger_rows': len(crows),
            })
        binding = 0
        non_binding = 0
        for site in self.sites:
            for idx in range(self.first_idx, self.first_idx + self.n_cycles):
                if self.cycle_stats[(site, idx)]['residual'] == 0:
                    binding += 1
                else:
                    non_binding += 1
        best = None
        for r in ledger:
            if best is None or r['deficit_to_date_equiv'] > best[0]:
                best = (r['deficit_to_date_equiv'], r['customer'], r['site'])
        spine_largest = None
        if best is not None:
            cands = [(r['deficit_to_date_equiv'], r['customer'], r['site'])
                     for r in ledger]
            cands.sort(key=lambda t: (-t[0], t[1], t[2]))
            spine_largest = {'customer': cands[0][1], 'site': cands[0][2],
                             'value': cands[0][0]}
        totals = {
            'ledger_rows': len(ledger),
            'granted_equiv': sum(r['granted_equiv'] for r in ledger),
            'claim_equiv': sum(r['claim_equiv'] for r in ledger),
            'deficit_equiv': sum(r['deficit_equiv'] for r in ledger),
            'capacity_equiv': sum(s['capacity_equiv'] for s in sites),
            'residual_equiv': sum(s['residual_equiv'] for s in sites),
            'out_of_scope_rows': len(out_of_scope),
            'customers_served': len(set(r['customer'] for r in ledger)),
        }
        region_granted = sum(s['granted_equiv'] for s in sites)
        segment_granted = sum(s['granted_equiv'] for s in segments)
        totals['identity_checks'] = {
            'region_minus_segment_granted': region_granted - segment_granted,
            'capacity_minus_granted_minus_residual':
                totals['capacity_equiv'] - totals['granted_equiv'] - totals['residual_equiv'],
            'claim_minus_granted_minus_deficit':
                totals['claim_equiv'] - totals['granted_equiv'] - totals['deficit_equiv'],
        }
        totals['spine'] = {
            'binding_cells': binding,
            'non_binding_cells': non_binding,
            'largest_deficit_to_date': spine_largest,
        }
        return {'as_of': self.as_of_text, 'sites': sites, 'segments': segments,
                'cycles': cycles, 'totals': totals}

    def policy_document(self):
        out = {
            'floors_honoured_full': self.tally['floors_honoured_full'],
            'floors_honoured_short': self.tally['floors_honoured_short'],
            'floors_unmatched': self.tally['floors_unmatched'],
            'exceptions_applied': self.tally['exceptions_applied'],
            'exceptions_unendorsed': self.tally['exceptions_unendorsed'],
            'exceptions_retracted': self.tally['exceptions_retracted'],
            'illegal_transitions': self.tally['illegal_transitions'],
            'stale_events': self.tally['stale_events'],
            'duplicate_version_events': self.tally['duplicate_version_events'],
            'amendments_applied': self.tally['amendments_applied'],
            'amendments_unendorsed': self.tally['amendments_unendorsed'],
            'amendments_early': self.tally['amendments_early'],
            'amendments_retracted': self.tally['amendments_retracted'],
            'amendment_chains_unresolvable': self.tally['amendment_chains_unresolvable'],
            'no_qualified_node': self.tally['no_qualified_node'],
            'substitution_cycles': self.tally['substitution_cycles'],
            'resets': self.tally['resets'],
            'lots_expired': self.tally['lots_expired'],
            'lots_cleared': self.tally['lots_cleared'],
            'ceiling_binding': self.tally['ceiling_binding'],
            'ceiling_zero': self.tally['ceiling_zero'],
            'epoch_reassignments': self.tally['epoch_reassignments'],
            'substitution_hops': {str(i): self.substitution_hops[str(i)]
                                 for i in range(0, self.max_hops + 1)},
            'cutover_sides': {'before': self.cutover_sides.get('before', 0),
                              'from': self.cutover_sides.get('from', 0)},
            'withheld': {
                'quantity_governed_before_cutover':
                    self.withheld['quantity_governed_before_cutover'],
                'carry_forward_age': self.withheld['carry_forward_age'],
            },
        }
        return out

    def quality_document(self):
        sources = {}
        for code in self.source_codes:
            s = self.dq_sources.get(code, {'declared_rows': 0, 'parsed_rows': 0,
                                           'admitted_rows': 0})
            sources[code] = {'declared_rows': s['declared_rows'],
                             'parsed_rows': s['parsed_rows'],
                             'admitted_rows': s['admitted_rows']}
        late = {}
        for code in self.source_codes:
            late[code] = self.late_by_source.get(code, 0)
        return {
            'sources': sources,
            'header_gaps': self.header_gaps,
            'null_forms': self.null_forms,
            'late_recorded': late,
            'duplicate_identical': self.tally['duplicate_identical'],
            'duplicate_conflicting': self.tally['duplicate_conflicting'],
            'cross_source_collapsed': self.tally['cross_source_collapsed'],
            'fold_disambiguated': self.fold_disambiguated,
            'gap_shifted': self.gap_shifted,
            'log_continuations': self.log_continuations,
            'unknown_customer_rows': self.dq['unknown_customer_rows'],
            'out_of_horizon_rows': self.dq['out_of_horizon_rows'],
            'lot_unit_rows': self.dq['lot_unit_rows'],
            'paren_negatives': self.dq['paren_negatives'],
            'restatement_gaps': self.dq['restatement_gaps'],
        }


def write_json(path, obj):
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(obj, fh, indent=1, sort_keys=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description='Derive the allocation report.')
    ap.add_argument('--data', default='/app/data')
    ap.add_argument('--out', default='/app/out')
    args = ap.parse_args(argv)
    data_dir = os.path.abspath(args.data)
    out_dir = os.path.abspath(args.out)
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)

    corp = Corpus(data_dir)
    corp.cycle_stats = {}
    corp.remainder_stats = {}
    corp.region_docs = {}
    ledger, out_of_scope = corp.derive()
    oos_rows = corp.out_of_scope_rows(out_of_scope)

    for site in corp.sites:
        corp.region_docs[site] = corp.region_document(site, ledger, oos_rows)
    segment_docs = [corp.segment_document('commercial', ledger),
                    corp.segment_document('public', ledger)]
    summary = corp.summary_document(corp.region_docs, segment_docs, ledger, oos_rows)
    policy = corp.policy_document()
    quality = corp.quality_document()

    for site in corp.sites:
        doc = corp.region_docs[site]
        for row in doc['ledger']:
            row.pop('site', None)
        write_json(os.path.join(out_dir, 'region_%s.json' % site), doc)
    for seg, doc in zip(('commercial', 'public'), segment_docs):
        write_json(os.path.join(out_dir, 'segment_%s.json' % seg), doc)
    write_json(os.path.join(out_dir, 'summary.json'), summary)
    write_json(os.path.join(out_dir, 'policy_audit.json'), policy)
    write_json(os.path.join(out_dir, 'data_quality.json'), quality)
    return 0


if __name__ == '__main__':
    sys.exit(main())


