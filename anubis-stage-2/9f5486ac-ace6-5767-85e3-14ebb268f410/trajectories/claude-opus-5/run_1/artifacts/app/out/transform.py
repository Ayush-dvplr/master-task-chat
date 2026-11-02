#!/usr/bin/env python3
"""Sentinel training-set release builder.

Usage: transform.py <DATA_DIR> <OUT_DIR> [--prior <PRIOR_OUT_DIR>]
"""
import argparse
import bisect
import collections
import csv
import datetime as dt
import hashlib
import io
import json
import os
import re
import sqlite3
import sys
import xml.etree.ElementTree as ET
import zipfile
from decimal import Decimal, ROUND_HALF_EVEN, localcontext, getcontext
from email.utils import parsedate_to_datetime
from fractions import Fraction

getcontext().prec = 60

BOM = '\ufeff'
UTC = dt.timezone.utc
TRIM = ' \t\r\n\v\f\u00a0\u202f'

SYSTEMS = ['SET', 'TRM', 'LEG', 'PAR', 'GW', 'SDK']
SYS_PREC = {s: i for i, s in enumerate(SYSTEMS)}

SPLITS = ['train', 'val', 'test', 'oot']
EVAL_SPLITS = ['val', 'test', 'oot']
REGION_GROUPS = ['central', 'east', 'north', 'south', 'west']
SEGMENT_GROUPS = ['consumer', 'corporate', 'enterprise', 'smb']
TIER_WEIGHT = {'gold': 3, 'silver': 2, 'bronze': 1, 'probation': 0}

Q6 = Decimal('0.000001')
RARE = '~RARE~'

IP_NONE = {'-', 'UNKNOWN', '0.0.0.0', 'NULL', 'N/A', ''}
DEV_NONE = {'', 'UNKNOWN'}


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------

def q6(x):
    return str(Decimal(x).quantize(Q6, rounding=ROUND_HALF_EVEN))


def frac_round(fr, places=6):
    scale = 10 ** places
    n = fr.numerator * scale
    d = fr.denominator
    neg = n < 0
    if neg:
        n = -n
    q, r = divmod(n, d)
    if 2 * r > d or (2 * r == d and q % 2 == 1):
        q += 1
    s = str(q).rjust(places + 1, '0')
    out = s[:-places] + '.' + s[-places:]
    return ('-' + out) if neg else out


def ceil_div(a, b):
    return -((-a) // b)


def nearest_rank(vals, num, den):
    n = len(vals)
    idx = ceil_div(num * n, den)
    if idx < 1:
        idx = 1
    if idx > n:
        idx = n
    return vals[idx - 1]


def trim(s):
    return s.strip(TRIM) if isinstance(s, str) else s


def canon(s):
    if s is None:
        return ''
    if not isinstance(s, str):
        s = str(s)
    return s.strip(TRIM).upper()


def is_ascii(s):
    return all(ord(c) < 128 for c in s)


def iso_z(t):
    return t.astimezone(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')


def epoch_to_dt(v):
    if isinstance(v, str):
        v = Decimal(v)
    else:
        v = Decimal(str(v))
    if abs(v) > 100000000000:
        v = v / 1000
    secs = int(v.to_integral_value(rounding='ROUND_FLOOR'))
    return dt.datetime.fromtimestamp(secs, UTC)


def parse_instant(s):
    if s is None:
        return None
    if isinstance(s, dt.datetime):
        return s if s.tzinfo else s.replace(tzinfo=UTC)
    if isinstance(s, dt.date):
        return dt.datetime(s.year, s.month, s.day, tzinfo=UTC)
    if isinstance(s, (int, float)):
        return epoch_to_dt(s)
    s = trim(str(s))
    if not s:
        return None
    if re.fullmatch(r'-?\d+(\.\d+)?', s):
        return epoch_to_dt(s)
    t = s.replace('Z', '+00:00')
    d = dt.datetime.fromisoformat(t)
    if d.tzinfo is None:
        d = d.replace(tzinfo=UTC)
    return d.astimezone(UTC)


def parse_naive(s):
    s = trim(str(s))
    if re.fullmatch(r'\d{14}', s):
        return dt.datetime(int(s[0:4]), int(s[4:6]), int(s[6:8]),
                           int(s[8:10]), int(s[10:12]), int(s[12:14]))
    return dt.datetime.fromisoformat(s.replace('Z', ''))


def date_at(s):
    y, m, d = [int(x) for x in trim(str(s)).split('-')]
    return dt.datetime(y, m, d, tzinfo=UTC)


def parse_date(s):
    if isinstance(s, dt.datetime):
        return s.date()
    if isinstance(s, dt.date):
        return s
    s = trim(str(s))
    m = re.fullmatch(r'(\d{4})-(\d{1,2})-(\d{1,2})', s)
    if m:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.fullmatch(r'(\d{1,2})\.(\d{1,2})\.(\d{4})', s)
    if m:
        return dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    return parse_instant(s).date()


def dec_major(s):
    s = trim(str(s))
    for ch in (',', ' ', '\u00a0', '\u202f'):
        s = s.replace(ch, '')
    return Decimal(s)


def dec_major_eu(s):
    s = trim(str(s))
    for ch in ('.', ' ', '\u00a0', '\u202f'):
        s = s.replace(ch, '')
    return Decimal(s.replace(',', '.'))


def dec_loose(s):
    s = trim(str(s))
    if ',' in s and '.' not in s:
        s = s.replace(',', '.')
    else:
        s = s.replace(',', '')
    return Decimal(s)


def excel_instant(v, system=1900):
    if v is None:
        return None
    if isinstance(v, dt.datetime):
        return v if v.tzinfo else v.replace(tzinfo=UTC)
    if isinstance(v, dt.date):
        return dt.datetime(v.year, v.month, v.day, tzinfo=UTC)
    if isinstance(v, str):
        s = trim(v)
        if not s:
            return None
        if not re.fullmatch(r'-?\d+(\.\d+)?', s):
            return parse_instant(s)
        v = float(s)
    base = dt.datetime(1899, 12, 30, tzinfo=UTC) if system == 1900 else \
        dt.datetime(1904, 1, 1, tzinfo=UTC)
    return base + dt.timedelta(seconds=round(float(v) * 86400))


# --------------------------------------------------------------------------
# raw readers
# --------------------------------------------------------------------------

def decode_line(b):
    if b.endswith(b'\r'):
        b = b[:-1]
    try:
        return b.decode('utf-8')
    except UnicodeDecodeError:
        return b.decode('iso-8859-1')


def raw_lines(path):
    with open(path, 'rb') as f:
        data = f.read()
    parts = data.split(b'\n')
    if parts and parts[-1] == b'':
        parts.pop()
    out = [decode_line(p) for p in parts]
    if out:
        out[0] = out[0].lstrip(BOM)
    return out


def read_text(path):
    with open(path, 'rb') as f:
        data = f.read()
    try:
        s = data.decode('utf-8')
    except UnicodeDecodeError:
        s = data.decode('iso-8859-1')
    return s.lstrip(BOM)


def read_delimited(path, delim, known_cols):
    header = None
    buf = []
    controls = []
    rows = []
    known = set(c.casefold() for c in known_cols)
    for ln in raw_lines(path):
        if not buf:
            if ln.strip() == '':
                continue
            if ln.startswith('#'):
                if ln.startswith('#CONTROL|'):
                    controls.append(ln[len('#CONTROL|'):])
                continue
        buf.append(ln)
        text = '\n'.join(buf)
        if text.count('"') % 2 == 1:
            continue
        buf = []
        cells = next(csv.reader(io.StringIO(text), delimiter=delim))
        if header is None:
            header = [trim(c).lstrip(BOM) for c in cells]
            known |= set(c.casefold() for c in header if c)
            continue
        stripped = [trim(c) for c in cells]
        ne = [c for c in stripped if c]
        if ne and len(ne) >= len(header) - 1 and \
                all(c.casefold() in known for c in ne):
            header = stripped
            continue
        row = {}
        for i, name in enumerate(header):
            row[name] = cells[i] if i < len(cells) else ''
        rows.append(row)
    return rows, controls


def read_jsonl(path):
    for ln in raw_lines(path):
        s = ln.strip()
        if s:
            yield json.loads(s)


def read_ini(path):
    out = []
    cur = None
    for ln in raw_lines(path):
        s = ln.strip()
        if not s or s[0] in ';#':
            continue
        if s.startswith('[') and s.endswith(']'):
            cur = (trim(s[1:-1]), {})
            out.append(cur)
        elif '=' in s and cur is not None:
            k, v = s.split('=', 1)
            cur[1][trim(k)] = trim(v)
    return out


def read_parquet(path):
    import pyarrow.parquet as pq
    t = pq.read_table(path)
    names = t.schema.names
    d = t.to_pydict()
    for i in range(t.num_rows):
        yield {c: d[c][i] for c in names}


def read_xlsx(path):
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    out = collections.OrderedDict()
    for ws in wb.worksheets:
        rows = []
        header = None
        for r in ws.iter_rows(values_only=True):
            if header is None:
                header = [trim(c) if isinstance(c, str) else c for c in r]
                continue
            if all(c is None for c in r):
                continue
            rows.append({header[i]: (r[i] if i < len(r) else None)
                         for i in range(len(header))})
        out[ws.title] = rows
    wb.close()
    return out


# --------------------------------------------------------------------------
# document tables
# --------------------------------------------------------------------------

FOOTNOTE_RE = re.compile(r'^Footnote:\s*override\s+(.*?);\s*(.*?);\s*(.*?);\s*(.*)$')


def parse_footnote(text):
    m = FOOTNOTE_RE.match(text.strip())
    if not m:
        return None
    return tuple(g.strip() for g in m.groups())


class DocTable(object):
    def __init__(self, caption, rows):
        self.caption = caption
        self.header = [trim(c) for c in rows[0]] if rows else []
        self.rows = [list(r) for r in rows[1:]]

    def apply_footnotes(self, notes):
        if not self.rows:
            return
        first = [r[0] for r in self.rows]
        repeats = len(set(first)) != len(first)
        index = {}
        for r in self.rows:
            if repeats and len(r) > 1:
                key = canon(r[0]) + '/' + canon(r[1])
            else:
                key = canon(r[0])
            index.setdefault(key, []).append(r)
        colmap = {c.casefold(): i for i, c in enumerate(self.header)}
        for cap, key, col, value in notes:
            if canon(cap) != canon(self.caption):
                continue
            ci = colmap.get(col.casefold())
            if ci is None:
                continue
            for r in index.get(canon(key), ()):
                while len(r) <= ci:
                    r.append('')
                r[ci] = value

    def dicts(self):
        h = self.header
        for r in self.rows:
            yield {h[i]: (r[i] if i < len(r) else '') for i in range(len(h))}


W_NS = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def docx_tables(path):
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read('word/document.xml'))
    body = root.find(W_NS + 'body')
    caption = None
    tables = []
    notes = []
    for child in list(body):
        if child.tag == W_NS + 'p':
            text = ''.join(child.itertext()).strip()
            if not text:
                continue
            fn = parse_footnote(text)
            if fn:
                notes.append(fn)
            elif text.startswith('Table:'):
                caption = text[len('Table:'):].strip()
        elif child.tag == W_NS + 'tbl':
            rows = []
            for tr in child.findall(W_NS + 'tr'):
                rows.append([''.join(tc.itertext()).strip()
                             for tc in tr.findall(W_NS + 'tc')])
            tables.append(DocTable(caption or 'table', rows))
            caption = None
    for t in tables:
        t.apply_footnotes(notes)
    return {t.caption: t for t in tables}


def html_tables(path):
    import html.parser
    tables = []
    notes = []

    class P(html.parser.HTMLParser):
        def __init__(self):
            html.parser.HTMLParser.__init__(self, convert_charrefs=True)
            self.cap = None
            self.rows = None
            self.row = None
            self.cell = None
            self.text = []

        def handle_starttag(self, tag, attrs):
            if tag == 'table':
                self.rows = []
                self.cap = None
            elif tag == 'caption':
                self.text = []
            elif tag == 'tr':
                self.row = []
            elif tag in ('td', 'th'):
                self.cell = []
            elif tag == 'p':
                self.text = []

        def handle_endtag(self, tag):
            if tag == 'table':
                if self.rows:
                    tables.append(DocTable(self.cap or '', self.rows))
                self.rows = None
            elif tag == 'caption':
                self.cap = ''.join(self.text).strip()
            elif tag == 'tr':
                if self.row is not None and self.rows is not None:
                    self.rows.append(self.row)
                self.row = None
            elif tag in ('td', 'th'):
                if self.cell is not None and self.row is not None:
                    self.row.append(''.join(self.cell).strip())
                self.cell = None
            elif tag == 'p':
                fn = parse_footnote(''.join(self.text).strip())
                if fn:
                    notes.append(fn)
                self.text = []

        def handle_data(self, data):
            if self.cell is not None:
                self.cell.append(data)
            else:
                self.text.append(data)

    p = P()
    p.feed(read_text(path))
    p.close()
    for t in tables:
        t.apply_footnotes(notes)
    return {t.caption: t for t in tables}


def md_tables(path):
    lines = read_text(path).split('\n')
    tables = []
    notes = []
    i = 0
    while i < len(lines):
        ln = lines[i].strip()
        fn = parse_footnote(ln)
        if fn:
            notes.append(fn)
            i += 1
            continue
        m = re.fullmatch(r'\*\*Table:\s*(.*?)\*\*', ln)
        if m:
            cap = m.group(1).strip()
            j = i + 1
            while j < len(lines) and not lines[j].lstrip().startswith('|'):
                j += 1
            rows = []
            while j < len(lines) and lines[j].lstrip().startswith('|'):
                cells = [trim(c) for c in lines[j].strip().strip('|').split('|')]
                if not all(re.fullmatch(r':?-{2,}:?', c) for c in cells):
                    rows.append(cells)
                j += 1
            tables.append(DocTable(cap, rows))
            i = j
            continue
        i += 1
    for t in tables:
        t.apply_footnotes(notes)
    return {t.caption: t for t in tables}


def pdf_tables(path, max_pages=None):
    import pdfplumber
    acc = collections.OrderedDict()
    notes = []
    prose = []
    with pdfplumber.open(path) as pdf:
        pages = pdf.pages if max_pages is None else pdf.pages[:max_pages]
        for page in pages:
            text = page.extract_text() or ''
            cur = None
            for raw in text.split('\n'):
                ln = raw.strip()
                if not ln or re.fullmatch(r'Page \d+', ln):
                    continue
                fn = parse_footnote(ln)
                if fn:
                    notes.append(fn)
                    cur = None
                    continue
                if ln.startswith('Table:'):
                    cap = ln[len('Table:'):].strip()
                    if cap.endswith('(continued)'):
                        cap = cap[:-len('(continued)')].strip()
                    cur = cap
                    acc.setdefault(cur, [])
                    continue
                if cur is not None and ' | ' in ln:
                    acc[cur].append([c.strip() for c in ln.split(' | ')])
                else:
                    prose.append(ln)
                    if ' | ' not in ln:
                        cur = cur
    out = {}
    for cap, rows in acc.items():
        if not rows:
            continue
        hdr = rows[0]
        body = [r for r in rows[1:] if r != hdr]
        t = DocTable(cap, [hdr] + body)
        t.apply_footnotes(notes)
        out[cap] = t
    return out, prose


# --------------------------------------------------------------------------
# timezones
# --------------------------------------------------------------------------

def nth_weekday(year, month, weekday, n):
    if n > 0:
        d = dt.date(year, month, 1)
        return d + dt.timedelta(days=(weekday - d.weekday()) % 7 + 7 * (n - 1))
    nxt = dt.date(year + 1, 1, 1) if month == 12 else dt.date(year, month + 1, 1)
    d = nxt - dt.timedelta(days=1)
    return d - dt.timedelta(days=(d.weekday() - weekday) % 7)


SUN = 6


class Zone(object):
    def __init__(self, name, std_minutes, rule, shift_minutes):
        self.name = name
        self.std = dt.timedelta(minutes=std_minutes)
        self.rule = rule
        self.shift = dt.timedelta(minutes=shift_minutes)
        self._cache = {}

    def _bounds(self, year):
        if year in self._cache:
            return self._cache[year]
        std, dst = self.std, self.std + self.shift
        r = self.rule
        if r == 'eu':
            res = ('north',
                   dt.datetime.combine(nth_weekday(year, 3, SUN, -1), dt.time(1), UTC),
                   dt.datetime.combine(nth_weekday(year, 10, SUN, -1), dt.time(1), UTC))
        elif r == 'il':
            res = ('north',
                   dt.datetime.combine(nth_weekday(year, 3, SUN, -1) - dt.timedelta(days=2),
                                       dt.time(0), UTC),
                   dt.datetime.combine(nth_weekday(year, 10, SUN, -1), dt.time(0), UTC))
        elif r == 'us':
            res = ('north',
                   dt.datetime.combine(nth_weekday(year, 3, SUN, 2), dt.time(2), UTC) - std,
                   dt.datetime.combine(nth_weekday(year, 11, SUN, 1), dt.time(2), UTC) - dst)
        elif r == 'south':
            res = ('south',
                   dt.datetime.combine(nth_weekday(year, 10, SUN, 1), dt.time(2), UTC) - std,
                   dt.datetime.combine(nth_weekday(year, 4, SUN, 1), dt.time(3), UTC) - dst)
        elif r == 'nz':
            res = ('south',
                   dt.datetime.combine(nth_weekday(year, 9, SUN, -1), dt.time(2), UTC) - std,
                   dt.datetime.combine(nth_weekday(year, 4, SUN, 1), dt.time(3), UTC) - dst)
        elif r == 'cl':
            res = ('south',
                   dt.datetime.combine(nth_weekday(year, 9, SUN, 1), dt.time(4), UTC),
                   dt.datetime.combine(nth_weekday(year, 4, SUN, 1), dt.time(3), UTC))
        else:
            res = None
        self._cache[year] = res
        return res

    def is_dst(self, instant):
        b = self._bounds(instant.year)
        if b is None:
            return False
        kind, s, e = b
        if kind == 'north':
            return s <= instant < e
        return instant >= s or instant < e

    def to_utc(self, naive):
        if self.rule == 'none':
            return (naive - self.std).replace(tzinfo=UTC)
        cands = []
        for off in (self.std + self.shift, self.std):
            t = (naive - off).replace(tzinfo=UTC)
            if (off != self.std) == self.is_dst(t):
                cands.append(t)
        if not cands:
            return (naive - self.std).replace(tzinfo=UTC)
        return min(cands)


# --------------------------------------------------------------------------

class Record(object):
    __slots__ = ('file', 'system', 'ref', 'account_raw', 'merchant_raw',
                 'amount', 'currency', 'status_raw', 'auth_code', 'bin',
                 'entry_raw', 'batch', 'ip_raw', 'device_raw', 'terminal',
                 'arn', 'time_raw', 'event_time', 'delivered_time',
                 'delivered_amount', 'account', 'merchant', 'reason',
                 'candidate', 'group', 'order', 'skey')

    def __init__(self):
        for s in Record.__slots__:
            setattr(self, s, None)


class Group(object):
    __slots__ = ('fp', 'members', 'keeper', 'example_id', 'event_time',
                 'account', 'merchant', 'cluster', 'split', 'label',
                 'label_source', 'features', 'categorical', 'imputed',
                 'reason', 'bin', 'entry', 'ip', 'device', 'scaled', 'score',
                 'sample_weight')

    def __init__(self, fp):
        self.fp = fp
        self.members = []
        self.imputed = set()
        self.reason = None
        self.label = None
        self.label_source = None


class Build(object):

    def __init__(self, data_dir, out_dir, prior_dir):
        self.data = data_dir
        self.out = out_dir
        self.prior_dir = prior_dir
        self.delta = prior_dir is not None
        self.file_controls = {}
        self.rawn = {}

    def p(self, name):
        return os.path.join(self.data, name)

    # ------------------------------------------------------------------
    def run(self):
        self.load_register()
        self.status = 'PUBLISHED'
        self.missing = [f for f in self.catalog if not os.path.exists(self.p(f))]
        self.prior = None
        if self.delta:
            pp = os.path.join(self.prior_dir, 'product_summary.json')
            if os.path.exists(pp):
                with open(pp, 'rb') as f:
                    self.prior = json.load(f)
            if not self.prior or self.prior.get('status') != 'PUBLISHED':
                self.status = 'HELD'
        if self.missing or self.status == 'HELD':
            self.status = 'HELD'
            self.release_id = self.read_release_id()
            self.write_held()
            return
        self.load_config()
        self.load_rules()
        self.load_entities()
        self.load_events()
        con = sqlite3.connect(self.p(self.f('lineage_controls')))
        self.controls_rows = list(con.execute(
            'select source_file, scope, partition, row_count, hash_total, '
            'delivered_with from controls'))
        con.close()
        self.load_label_sources()
        self.reconcile()
        if not self.controls_all_ok:
            self.status = 'HELD'
        if self.status == 'HELD':
            self.write_held()
            return
        self.build()
        self.write_outputs()

    def read_release_id(self):
        try:
            import tomllib
            with open(self.p(self.f('release_config')), 'rb') as f:
                cfg = tomllib.loads(f.read().decode('utf-8-sig'))
            return cfg['release']['release_id']
        except Exception:
            return None

    # ------------------------------------------------------------------
    def note(self, fname, scope, n):
        self.rawn[(fname, scope)] = n

    def note_tables(self, fname, tables):
        for cap, tab in tables.items():
            self.note(fname, cap, len(tab.rows))

    def f(self, source_id):
        return self.byid[source_id]

    def fs(self, pattern):
        rx = re.compile(pattern)
        return [f for sid, f in self.sid_files if rx.fullmatch(sid)]

    def load_register(self):
        t = md_tables(self.p('source_register.md'))
        self.reg = t
        self.note_tables('source_register.md', t)
        self.catalog_rows = list(t['Catalog'].dicts())
        self.catalog = [trim(r['file']) for r in self.catalog_rows]
        self.sid_files = [(trim(r['source_id']), trim(r['file']))
                          for r in self.catalog_rows]
        self.byid = dict((sid, f) for sid, f in self.sid_files)
        self.cols = collections.defaultdict(set)
        for r in t['Column map'].dicts():
            self.cols[trim(r['file'])].add(trim(r['column']))

    def load_config(self):
        import tomllib
        with open(self.p(self.f('release_config')), 'rb') as f:
            cfg = tomllib.loads(f.read().decode('utf-8-sig'))
        self.cfg = cfg['release']
        c = self.cfg
        self.release_id = c['release_id']
        self.window_start = date_at(c['window_start'])
        self.window_end = date_at(c['window_end'])
        self.lookback_start = date_at(c['lookback_start'])
        self.cutoff = date_at(c['label_cutoff'])
        self.oot_start = date_at(c['oot_start'])
        self.maturity = int(c['maturity_days'])
        self.salt = c['split_salt']
        self.train_below = int(c['split_train_below'])
        self.val_below = int(c['split_val_below'])
        self.beta = Fraction(Decimal(str(c['class_weight_beta'])))
        self.min_vocab = int(c['min_vocab_count'])
        self.vel_count_w = int(c['velocity_count_window_s'])
        self.vel_sum_w = int(c['velocity_sum_window_s'])
        self.pins = cfg.get('pinned', [])
        self.note(self.f('release_config'), 'pinned', len(self.pins))
        with open(self.p(self.f('feature_definitions')), 'rb') as f:
            fd = tomllib.loads(f.read().decode('utf-8-sig'))
        self.numeric = list(fd['features']['numeric'])
        self.categ = list(fd['features']['categorical'])
        self.kyc_default = {}
        for r in fd.get('kyc_default', []):
            self.kyc_default[(canon(r['segment']), canon(r['region']))] = int(r['tier'])
        self.note(self.f('feature_definitions'), 'kyc_default',
                  len(fd.get('kyc_default', [])))

    # ------------------------------------------------------------------
    def load_rules(self):
        self.load_charter()
        dd = md_tables(self.p(self.f('data_dictionary')))
        self.note_tables('data_dictionary.md', dd)
        self.status_meaning = {}
        for r in dd['Status codes'].dicts():
            self.status_meaning[(canon(r['system']), canon(r['raw_code']))] = \
                trim(r['meaning']).lower()
        self.region_group = {canon(r['region']): trim(r['group'])
                             for r in dd['Region groups'].dicts()}
        self.segment_group = {canon(r['segment']): trim(r['group'])
                              for r in dd['Segment groups'].dicts()}

        spec = docx_tables(self.p(self.f('build_spec')))
        self.note_tables('release_build_specification.docx', spec)
        self.split_tender = set()
        for r in spec['Split-tender exceptions'].dicts():
            self.split_tender.add((trim(r['file']).casefold(), canon(r['record_ref'])))

        pre = docx_tables(self.p(self.f('preprocessing_standard')))
        self.note_tables('preprocessing_standard.docx', pre)
        self.mcc_group = {canon(r['mcc_subcode']): trim(r['risk_group'])
                          for r in pre['MCC sub-code risk groups'].dicts()}

        sp = docx_tables(self.p(self.f('split_policy')))
        self.note_tables('split_and_leakage_policy.docx', sp)
        self.device_exempt = set(canon(r['device_id'])
                                 for r in sp['Shared-device exemptions'].dicts())

        lp3 = docx_tables(self.p(self.f('label_policy.v3')))
        self.note_tables('label_policy_v3.docx', lp3)
        self.merchant_profile = {canon(r['merchant_id']): trim(r['profile'])
                                 for r in lp3['Merchant dispute-handling profiles'].dicts()}

        lp4 = docx_tables(self.p(self.f('label_policy.v4')))
        self.note_tables('label_policy_v4.docx', lp4)
        self.orbis_renumber = {canon(r['legacy_code']): canon(r['current_code'])
                               for r in lp4['Orbis reason code renumbering'].dicts()}

        dr = docx_tables(self.p(self.f('dedup_runbook')))
        self.note_tables('dedup_runbook.docx', dr)
        self.replay_batches = set(canon(r['batch_id'])
                                  for r in dr['Replay batch register'].dicts()
                                  if trim(r['kind']).lower() == 'replay')

        rn = md_tables(self.p(self.f('prior_release_notes')))
        self.note_tables('release_notes_TR-2026.05.md', rn)
        self.retracted_refs = set(canon(r['event_ref'])
                                  for r in rn['Retracted examples'].dicts())

        entt = html_tables(self.p(self.f('entry_codes')))
        self.note_tables('entry_mode_codes.html', entt)
        ent = entt['Entry mode codes']
        self.entry_mode = {(canon(r['system']), canon(r['raw_code'])): trim(r['entry_mode'])
                           for r in ent.dicts()}

        rc, _ = pdf_tables(self.p(self.f('reason_codes')))
        self.note_tables('reason_code_catalog.pdf', rc)
        self.reason_class = {(canon(r['network']), canon(r['reason_code'])):
                             trim(r['class']).lower()
                             for r in rc['Reason codes'].dicts()}

        sc, sc_prose = pdf_tables(self.p(self.f('scorer_card')))
        self.note_tables('baseline_scorer_card.pdf', sc)
        self.coef = {trim(r['term']): dec_loose(r['coefficient'])
                     for r in sc['Coefficients'].dicts()}
        self.merch_offset = {canon(r['merchant_id']): dec_loose(r['offset'])
                             for r in sc['Merchant offsets'].dicts()}

        fx, _ = pdf_tables(self.p(self.f('fx_handbook')))
        self.note_tables('currency_and_fx_handbook.pdf', fx)
        self.fix_cal = {}
        for r in fx['Fixing calendar'].dicts():
            self.fix_cal[(canon(r['currency']), parse_date(r['date']))] = \
                (trim(r['status']).lower(), parse_date(r['substitute_date']))
        self.minor_exp = {canon(r['currency']): int(trim(r['exponent']))
                          for r in fx['Minor units'].dicts()}

        tzh, _ = pdf_tables(self.p(self.f('clock_handbook')))
        self.note_tables('timezone_and_clock_handbook.pdf', tzh)
        self.zone_alias = {canon(r['alias']): trim(r['zone'])
                           for r in tzh['Zone aliases'].dicts()}

        ag, _ = pdf_tables(self.p(self.f('annotation_guidelines')))
        self.note_tables('annotation_guidelines.pdf', ag)
        self.gold_fail = set()
        for r in ag['Gold check results'].dicts():
            if trim(r['result']).lower() == 'fail':
                self.gold_fail.add((canon(r['annotator_id']), canon(r['batch_id'])))

        av, av_prose = pdf_tables(self.p(self.f('availability_spec')))
        self.note_tables('feature_availability_spec.pdf', av)
        self.ip_pub = {canon(r['partition']): parse_instant(r['published_at'])
                       for r in av['IP reputation partition schedule'].dicts()}
        self.lag_default = self.parse_default_lags(av_prose)
        revs = self.fs(r'availability_spec\..+')
        self.rev2_file = revs[-1] if revs else None
        self.lag_rev2 = {}
        if self.rev2_file:
            rev2t, rev2_prose = pdf_tables(self.p(self.rev2_file))
            self.note_tables(self.rev2_file, rev2t)
            self.lag_rev2 = self.parse_rev2(rev2_prose)

        import tomllib
        with open(self.p(self.f('timezone_rules')), 'rb') as f:
            tzr = tomllib.loads(f.read().decode('utf-8-sig'))
        self.zones = {canon(z['name']): Zone(z['name'], int(z['std_offset_minutes']),
                                             trim(z['dst_rule']).lower(),
                                             int(z['dst_shift_minutes']))
                      for z in tzr['zone']}
        self.postal_zone = {canon(r['prefix']): canon(r['zone'])
                            for r in tzr['postal_zone']}
        self.note(self.f('timezone_rules'), 'postal_zone', len(tzr['postal_zone']))

        rows, _ = read_delimited(self.p(self.f('region_crosswalk')), ',',
                                 self.cols[self.f('region_crosswalk')] |
                                 {'postal', 'region'})
        self.postal_region = {canon(r['postal']): canon(r['region']) for r in rows}
        self.note(self.f('region_crosswalk'), 'rows', len(rows))
        self.load_errata()
        self.load_fx()
        self.load_lag_overrides()

    def parse_default_lags(self, prose):
        text = ' '.join(prose)
        out = {'merchant_risk': 180, 'ip_reputation': 45}
        m = re.search(r'Default lags:\s*merchant_risk\s+(\d+)\s*minutes,\s*'
                      r'ip_reputation\s+(\d+)\s*minutes', text)
        if m:
            out['merchant_risk'] = int(m.group(1))
            out['ip_reputation'] = int(m.group(2))
        return out

    def parse_rev2(self, prose):
        """Default lags the revision sets, limited to what the charter grants."""
        text = ' '.join(prose)
        out = {}
        for src in ('ip_reputation', 'merchant_risk'):
            m = re.search(src + r' lag to (\d+) minutes', text)
            if m:
                out[src] = int(m.group(1))
        note = self.charter_notes.get((self.rev2_file, 'rule_tables'), '')
        granted = [s for s in out if s in note]
        if granted:
            out = {s: out[s] for s in granted}
        return out

    def load_charter(self):
        self.load_incidents()
        t = docx_tables(self.p(self.f('governance_charter')))
        self.note_tables('data_governance_charter.docx', t)
        self.charter = collections.defaultdict(list)
        self.charter_notes = {}
        for r in t['Source authority windows'].dicts():
            f = trim(r['file'])
            g = trim(r['field_group'])
            auth = trim(r['authority'])
            inc = trim(r.get('incident', ''))
            vf, vt = trim(r['valid_from']), trim(r['valid_to'])
            if inc and re.match(r'INC-\d', inc) and not vf and not vt:
                w = self.incident_window.get(inc)
                if w:
                    self.charter[(f, g)].append((w[0], w[1], auth))
                continue
            if not vf or not vt:
                continue
            self.charter[(f, g)].append((date_at(vf), date_at(vt), auth))
            if inc:
                self.charter_notes[(f, g)] = inc

    def load_incidents(self):
        self.incident_window = {}
        self.outages = collections.defaultdict(list)
        opened = {}
        revised = {}
        resolved = {}
        for ln in raw_lines(self.p(self.f('incident_log'))):
            s = ln.strip()
            if not s:
                continue
            parts = s.split()
            if len(parts) < 3:
                continue
            inc, action = parts[1], parts[2]
            kv = dict(p.split('=', 1) for p in parts[3:] if '=' in p)
            if action == 'OPENED':
                opened[inc] = kv
            elif action == 'WINDOW_REVISED':
                revised[inc] = kv
            elif action == 'RESOLVED':
                resolved[inc] = kv
        order = []
        for d in (opened, revised, resolved):
            for inc in d:
                if inc not in order:
                    order.append(inc)
        for inc in order:
            kv = revised.get(inc)
            if kv and kv.get('start') and kv.get('end'):
                w = (parse_instant(kv['start']), parse_instant(kv['end']))
            else:
                st = (opened.get(inc) or {}).get('start')
                en = (resolved.get(inc) or {}).get('end')
                if not st or not en:
                    continue
                w = (parse_instant(st), parse_instant(en))
            self.incident_window[inc] = w
            sysname = (opened.get(inc) or {}).get('system')
            if sysname:
                self.outages[sysname].append(w)

    def authority(self, f, group, when):
        best = 'none'
        for vf, vt, auth in self.charter.get((f, group), ()):
            if vf <= when < vt:
                if auth == 'primary':
                    return 'primary'
                best = auth
        return best

    def effective_publication(self, instant, system):
        """Publications inside an outage become effective when the outage ends."""
        ends = [e for s, e in self.outages.get(system, ()) if s <= instant < e]
        return max(ends) if ends else instant

    # ------------------------------------------------------------------
    def load_errata(self):
        register = []
        withdrawn = set()
        for f in self.fs(r'errata.*'):
            tabs = html_tables(self.p(f))
            self.note_tables(f, tabs)
            if self.authority(f, 'void_evidence', self.cutoff) == 'primary':
                for cap, tab in tabs.items():
                    if 'withdrawn' in cap.casefold():
                        withdrawn |= set(canon(r['erratum_id'])
                                         for r in tab.dicts())
            if self.authority(f, 'rule_tables', self.cutoff) == 'primary':
                for cap, tab in tabs.items():
                    if 'withdrawn' not in cap.casefold():
                        register.extend(tab.dicts())
        best = {}
        for r in register:
            eid = canon(r['erratum_id'])
            if eid in withdrawn:
                continue
            key = (trim(r['file']), canon(r['record_ref']), trim(r['field']).lower())
            issued = parse_instant(r['issued_at'])
            prev = best.get(key)
            if prev is None or issued > prev[0] or (issued == prev[0] and eid > prev[2]):
                best[key] = (issued, trim(r['new_value']), eid)
        self.errata = collections.defaultdict(dict)
        for (f, ref, field), (_, value, _) in best.items():
            self.errata[(f, ref)][field] = value

    def load_fx(self):
        self.vendor_rate = {}
        self.nvendor = 0
        for r in read_parquet(self.p(self.f('fx.vendor'))):
            self.nvendor += 1
            self.vendor_rate[(canon(r['currency']), parse_date(r['rate_date']))] = \
                Decimal(str(r['usd_per_unit']))
        self.treasury_rate = {}
        self.ntreas = 0
        root = ET.parse(self.p(self.f('fx.treasury'))).getroot()
        for fx in root.iter('Fixing'):
            self.ntreas += 1
            cur = canon(fx.get('currency'))
            unit = dec_loose(fx.get('unit') or '1')
            self.treasury_rate[(cur, parse_date(fx.get('date')))] = \
                dec_loose(fx.get('rate')) / unit
        self.treasury_cur = set(c for c, _ in self.treasury_rate)
        self.note(self.f('fx.vendor'), 'rates', self.nvendor)
        self.note(self.f('fx.treasury'), 'fixings', self.ntreas)
        rows, _ = read_delimited(self.p(self.f('fx.corrections')), ',',
                                 self.cols[self.f('fx.corrections')] |
                                 {'currency', 'rate_date', 'verdict',
                                  'corrected_usd_per_unit', 'reviewed_at'})
        self.fx_correction = {}
        for r in rows:
            if trim(r['verdict']).lower() == 'corrected' and \
                    trim(r['corrected_usd_per_unit']):
                self.fx_correction[(canon(r['currency']), parse_date(r['rate_date']))] = \
                    dec_loose(r['corrected_usd_per_unit'])
        self.note(self.f('fx.corrections'), 'rows', len(rows))
        self._rate_cache = {}

    def load_lag_overrides(self):
        rows, _ = read_delimited(self.p(self.f('lag_overrides')), ',',
                                 self.cols[self.f('lag_overrides')] |
                                 {'source', 'date', 'hour', 'lag_minutes'})
        self.lag_over = {}
        for r in rows:
            v = trim(r['lag_minutes'])
            if not v:
                continue
            v = v.replace(',', '')
            self.lag_over[(trim(r['source']).lower(), parse_date(r['date']),
                           int(trim(r['hour'])))] = int(v)
        self.note(self.f('lag_overrides'), 'rows', len(rows))

    def lag_for(self, source, instant):
        key = (source, instant.date(), instant.hour)
        if key in self.lag_over:
            return dt.timedelta(minutes=self.lag_over[key])
        base = self.lag_default[source]
        rev = self.lag_rev2.get(source)
        if rev is not None and self.rev2_file and \
                self.authority(self.rev2_file, 'rule_tables', instant) == 'primary':
            base = rev
        return dt.timedelta(minutes=base)

    def usd_per_unit(self, cur, day):
        key = (cur, day)
        if key in self._rate_cache:
            return self._rate_cache[key]
        if cur == 'USD':
            r = Decimal(1)
        elif cur in self.treasury_cur:
            st = self.fix_cal.get(key)
            use = st[1] if (st and st[0] == 'holiday') else day
            r = self.treasury_rate.get((cur, use))
        else:
            r = self.fx_correction.get(key)
            if r is None:
                r = self.vendor_rate.get(key)
        self._rate_cache[key] = r
        return r

    def to_usd_cents(self, amount_minor, cur, instant):
        rate = self.usd_per_unit(cur, instant.date())
        exp = self.minor_exp.get(cur)
        if rate is None or exp is None:
            return None
        v = Decimal(amount_minor) * rate * 100 / (Decimal(10) ** exp)
        return int(v.quantize(Decimal(1), rounding=ROUND_HALF_EVEN))

    # ------------------------------------------------------------------
    def zone_for(self, name):
        z = self.zones.get(canon(name))
        if z is not None:
            return z
        alias = self.zone_alias.get(canon(name))
        return self.zones.get(canon(alias)) if alias else None

    def load_entities(self):
        self.load_accounts()
        self.load_merchants()
        self.load_devices()
        self.load_consent()
        rows, _ = read_delimited(self.p(self.f('bin_ranges')), ',',
                                 self.cols[self.f('bin_ranges')] |
                                 {'bin_prefix', 'issuer_group', 'network'})
        self.bin_pref = {canon(r['bin_prefix']): trim(r['issuer_group']) for r in rows}
        self.note(self.f('bin_ranges'), 'rows', len(rows))
        self.terminal_skew = {}
        tsec = read_ini(self.p(self.f('terminal_skew')))
        self.note(self.f('terminal_skew'), 'sections', len(tsec))
        for name, kv in tsec:
            if 'skew_seconds' in kv:
                self.terminal_skew[canon(name)] = int(trim(kv['skew_seconds']).replace('+', ''))
        self.merchant_zone = {}
        msec = read_ini(self.p(self.f('merchant_zones')))
        self.note(self.f('merchant_zones'), 'sections', len(msec))
        for name, kv in msec:
            if 'zone' in kv:
                self.merchant_zone[canon(name)] = trim(kv['zone'])
        self.load_ingestion()

    def load_ingestion(self):
        self.batch_ok = {}
        n = 0
        for ln in raw_lines(self.p(self.f('ingestion_audit'))):
            s = ln.strip()
            if not s:
                continue
            n += 1
            parts = s.split()
            kv = dict(p.split('=', 1) for p in parts[1:] if '=' in p)
            if kv.get('status') != 'ok':
                continue
            b = canon(kv.get('batch'))
            if b:
                self.batch_ok[b] = parse_instant(parts[0])
        self.note(self.f('ingestion_audit'), 'lines', n)

    def load_accounts(self):
        import yaml
        base = yaml.safe_load(read_text(self.p(self.f('accounts.base'))))
        rev = yaml.safe_load(read_text(self.p(self.f('accounts.revision'))))
        nxt = yaml.safe_load(read_text(self.p(self.f('accounts.next'))))
        self.note(self.f('accounts.base'), 'accounts', len(base['accounts']))
        self.note(self.f('accounts.revision'), 'accounts', len(rev['accounts']))
        self.note(self.f('accounts.next'), 'accounts', len(nxt['accounts']))
        self.acct_base = {canon(a['id']): a for a in base['accounts']}
        self.acct_rev = {canon(a['id']): a for a in rev['accounts']}
        self.known_accounts = set(self.acct_base) | set(self.acct_rev)
        self.legacy_map = {}
        for a in nxt['accounts']:
            if a.get('legacy_id'):
                self.legacy_map[canon(a['legacy_id'])] = canon(a['id'])
        merge = {}
        nmerge = 0
        for ln in raw_lines(self.p(self.f('account_merges.log'))):
            s = ln.strip()
            if s:
                nmerge += 1
            if ' MERGE ' not in s:
                continue
            kv = dict(p.split('=', 1) for p in s.split() if '=' in p)
            a, b = canon(kv.get('account')), canon(kv.get('into'))
            if a and b and a != b:
                merge[a] = b
        self.note(self.f('account_merges.log'), 'lines', nmerge)
        mm = json.loads(read_text(self.p(self.f('account_merges.map'))))
        self.note(self.f('account_merges.map'), 'map', len(mm['map']))
        for r in mm['map']:
            a, b = canon(r['account']), canon(r['canonical'])
            if a and b and a != b:
                merge[a] = b
        self.acct_merge = merge
        self._acct_cache = {}

    def canon_account(self, raw):
        k = raw if isinstance(raw, str) else str(raw)
        if k in self._acct_cache:
            return self._acct_cache[k]
        r = self._canon_account(k)
        self._acct_cache[k] = r
        return r

    def _canon_account(self, raw):
        s = canon(raw)
        if not s or not is_ascii(s):
            return None
        if re.fullmatch(r'L-\d{7}', s):
            s = self.legacy_map.get(s)
            if not s:
                return None
        elif not re.fullmatch(r'AC-\d{6}', s):
            return None
        seen = set()
        while s in self.acct_merge and s not in seen:
            seen.add(s)
            s = self.acct_merge[s]
        return s if s in self.known_accounts else None

    def acct_attr(self, acct, field, when):
        r = self.acct_rev.get(acct)
        if r is not None:
            ef = r.get('effective_from')
            if ef is None or date_at(str(ef)) <= when:
                if field in r:
                    return r[field]
        b = self.acct_base.get(acct)
        if b is not None and field in b:
            return b[field]
        return r.get(field) if r is not None else None

    def load_merchants(self):
        self.merch_master = {}
        nmm = 0
        for r in read_parquet(self.p(self.f('merchants.master'))):
            nmm += 1
            self.merch_master[canon(r['merchant_id'])] = r
        self.note(self.f('merchants.master'), 'merchants', nmm)
        merge = {}
        for mid, r in self.merch_master.items():
            tgt = canon(r.get('merged_into') or '')
            if tgt and tgt != mid:
                merge[mid] = tgt
        nmn = 0
        for r in read_parquet(self.p(self.f('merchants.next'))):
            nmn += 1
            mid = canon(r['merchant_id'])
            tgt = canon(r.get('merged_into') or '')
            if tgt and tgt != mid:
                merge[mid] = tgt
        self.note(self.f('merchants.next'), 'merchants', nmn)
        self.merch_merge = merge
        rows, _ = read_delimited(self.p(self.f('merchant_aliases')), ',',
                                 self.cols[self.f('merchant_aliases')] |
                                 {'alias', 'merchant_id', 'valid_from', 'valid_to'})
        self.alias_rows = collections.defaultdict(list)
        for r in rows:
            vfr = trim(r['valid_from'])
            vtr = trim(r['valid_to'])
            vf = date_at(vfr) if vfr and vfr != '0000-00-00' else None
            vt = date_at(vtr) if vtr and vtr != '0000-00-00' else None
            self.alias_rows[canon(r['alias'])].append((vf, vt, canon(r['merchant_id'])))
        self.note(self.f('merchant_aliases'), 'rows', len(rows))
        hist = json.loads(read_text(self.p(self.f('merchant_classification'))))
        self.note(self.f('merchant_classification'), 'history',
                  len(hist['history']))
        self.mcc_hist = collections.defaultdict(list)
        for r in hist['history']:
            self.mcc_hist[canon(r['merchant_id'])].append(
                (parse_instant(r['effective_from']), canon(r['mcc_subcode'])))
        for k in self.mcc_hist:
            self.mcc_hist[k].sort(key=lambda x: x[0])
        self._merch_cache = {}

    def canon_merchant(self, raw, when):
        key = (raw if isinstance(raw, str) else str(raw), when)
        if key in self._merch_cache:
            return self._merch_cache[key]
        r = self._canon_merchant(key[0], when)
        self._merch_cache[key] = r
        return r

    def _canon_merchant(self, raw, when):
        s = canon(raw)
        if not s or not is_ascii(s):
            return None
        if not re.fullmatch(r'MR-\d{5}', s):
            rows = self.alias_rows.get(s)
            if not rows:
                return None
            best = None
            for vf, vt, mid in rows:
                if (vf is None or vf <= when) and (vt is None or when < vt):
                    if best is None or (vf is not None and
                                        (best[0] is None or vf > best[0])):
                        best = (vf, mid)
            if best is None:
                return None
            s = best[1]
        seen = set()
        while s in self.merch_merge and s not in seen:
            seen.add(s)
            s = self.merch_merge[s]
        return s if s in self.merch_master else None

    def mcc_subcode(self, merchant, when):
        best = None
        for eff, code in self.mcc_hist.get(merchant, ()):
            if eff <= when:
                best = code
            else:
                break
        if best is None:
            m = self.merch_master.get(merchant)
            best = canon(m.get('mcc_subcode')) if m else None
        return best

    def load_devices(self):
        import yaml
        reg = yaml.safe_load(read_text(self.p(self.f('device_registry'))))
        self.device_kind = {canon(d['device_id']): trim(str(d.get('kind') or '')).lower()
                            for d in reg['devices']}
        self.note(self.f('device_registry'), 'devices', len(reg['devices']))
        self.link_events = []
        nlink = 0
        for ln in raw_lines(self.p(self.f('device_links.log'))):
            s = ln.strip()
            if not s:
                continue
            nlink += 1
            parts = s.split()
            if len(parts) < 3:
                continue
            kv = dict(p.split('=', 1) for p in parts[3:] if '=' in p)
            self.link_events.append((parse_instant(parts[0]), parts[2],
                                     canon(kv.get('account')), canon(kv.get('device'))))
        self.note(self.f('device_links.log'), 'lines', nlink)
        self.fingerprints = [(canon(r['account_id']), canon(r['device_id']),
                              parse_instant(r['first_seen']))
                             for r in read_parquet(
                                 self.p(self.f('device_links.fingerprints')))]
        self.note(self.f('device_links.fingerprints'), 'obs',
                  len(self.fingerprints))
        rows, _ = read_delimited(self.p(self.f('device_link_revocations')), ',',
                                 self.cols[self.f('device_link_revocations')] |
                                 {'account_id', 'device_id', 'action', 'at'})
        self.revocations = [(canon(r['account_id']), canon(r['device_id']),
                             trim(r['action']).lower(), parse_instant(r['at']))
                            for r in rows]
        self.note(self.f('device_link_revocations'), 'rows', len(rows))

    def load_consent(self):
        rows, _ = read_delimited(self.p(self.f('consent.portal')), ',',
                                 self.cols[self.f('consent.portal')] |
                                 {'account_id', 'action', 'scope', 'at'})
        self.note(self.f('consent.portal'), 'rows', len(rows))
        latest = {}
        for r in rows:
            if trim(r['scope']).lower() not in ('training', 'all'):
                continue
            at = parse_instant(r['at'])
            if at is None or at > self.cutoff:
                continue
            a = canon(r['account_id'])
            prev = latest.get(a)
            if prev is None or at >= prev[0]:
                latest[a] = (at, trim(r['action']).lower())
        self.withdrawn = set(a for a, v in latest.items() if v[1] == 'withdraw')
        osec = read_ini(self.p(self.f('consent.support')))
        self.note(self.f('consent.support'), 'sections', len(osec))
        for name, kv in osec:
            if trim(kv.get('status', '')).lower() == 'withdrawn':
                up = parse_instant(kv.get('updated'))
                if up is None or up <= self.cutoff:
                    self.withdrawn.add(canon(name))
        orders = json.loads(read_text(self.p(self.f('consent.legal'))))
        self.note(self.f('consent.legal'), 'orders', len(orders['orders']))
        for o in orders['orders']:
            if trim(str(o.get('type') or '')).lower() != 'erasure':
                continue
            if trim(str(o.get('status') or '')).lower() != 'executed':
                continue
            ex = parse_instant(o.get('executed_at'))
            if ex is not None and ex > self.cutoff:
                continue
            self.withdrawn.add(canon(o['account_id']))

    def issuer_group(self, card_bin):
        b = canon(card_bin)
        for n in range(len(b), 0, -1):
            g = self.bin_pref.get(b[:n])
            if g:
                return g
        return 'UNMAPPED'

    # ------------------------------------------------------------------
    # event exports
    # ------------------------------------------------------------------
    def load_events(self):
        self.records = []
        self.by_file = collections.OrderedDict()
        order = 0
        for row in self.catalog_rows:
            if trim(row['role']) != 'events':
                continue
            f = trim(row['file'])
            recs = self.parse_event_file(f, trim(row['source_id']).split('.')[0])
            for r in recs:
                r.order = order
                order += 1
            self.by_file[f] = recs
            self.records.extend(recs)
        self.normalize_times()
        self.apply_errata()

    EVENT_PARSERS = {'settlement': 'parse_settlement', 'gateway': 'parse_gateway',
                     'sdk': 'parse_sdk', 'legacy': 'parse_legacy',
                     'partner': 'parse_partner', 'terminal': 'parse_terminal'}

    def parse_event_file(self, f, family):
        name = self.EVENT_PARSERS.get(family)
        if name is None:
            self.file_controls[f] = []
            return []
        return getattr(self, name)(f)

    @staticmethod
    def _pick(row, names):
        for n in names:
            if n in row and trim(row[n]) != '':
                return row[n]
        for n in names:
            if n in row:
                return row[n]
        return None

    def _minor(self, value, cur, eu=False):
        exp = self.minor_exp.get(cur, 2)
        d = dec_major_eu(value) if eu else dec_major(value)
        return int((d * (Decimal(10) ** exp)).quantize(Decimal(1),
                                                       rounding=ROUND_HALF_EVEN))

    def parse_settlement(self, f):
        rows, controls = read_delimited(self.p(f), ',', self.cols[f])
        self.file_controls[f] = controls
        out = []
        for row in rows:
            r = Record()
            r.file, r.system = f, 'SET'
            r.ref = canon(self._pick(row, ['settlement_ref']))
            r.time_raw = self._pick(row, ['auth_ts', 'authorized_at'])
            r.account_raw = self._pick(row, ['account_id', 'acct_id'])
            r.merchant_raw = self._pick(row, ['merchant_id'])
            r.currency = canon(self._pick(row, ['currency']))
            r.amount = int(trim(self._pick(row, ['amount_minor', 'amt_minor_units'])))
            r.status_raw = canon(self._pick(row, ['status_code']))
            r.auth_code = canon(self._pick(row, ['auth_code']))
            r.bin = canon(self._pick(row, ['card_bin']))
            r.entry_raw = canon(self._pick(row, ['pos_entry']))
            r.batch = canon(self._pick(row, ['batch_id']))
            r.delivered_time = parse_instant(r.time_raw)
            out.append(r)
        return out

    def parse_gateway(self, f):
        rows, controls = read_delimited(self.p(f), '\t', self.cols[f])
        self.file_controls[f] = controls
        out = []
        for row in rows:
            r = Record()
            r.file, r.system = f, 'GW'
            r.ref = canon(self._pick(row, ['gw_txn_id']))
            r.time_raw = self._pick(row, ['auth_time', 'auth_ts'])
            r.account_raw = self._pick(row, ['acct', 'account'])
            r.merchant_raw = self._pick(row, ['descriptor'])
            r.currency = canon(self._pick(row, ['ccy']))
            r.amount = self._minor(self._pick(row, ['amount', 'amount_major']), r.currency)
            r.status_raw = canon(self._pick(row, ['resp_code']))
            r.auth_code = canon(self._pick(row, ['auth_id']))
            r.bin = canon(self._pick(row, ['bin6']))
            r.entry_raw = canon(self._pick(row, ['entry']))
            r.ip_raw = self._pick(row, ['ip_ref'])
            r.batch = canon(self._pick(row, ['batch']))
            if 'arn' in row:
                r.arn = canon(row['arn'])
            r.delivered_time = parse_instant(r.time_raw)
            out.append(r)
        return out

    def parse_sdk(self, f):
        controls = []
        out = []
        for o in read_jsonl(self.p(f)):
            if '_meta' in o:
                continue
            if '_control' in o:
                c = o['_control']
                controls.append('%s|%s|%s' % (c['partition'], c['row_count'],
                                              c['hash_total']))
                continue
            r = Record()
            r.file, r.system = f, 'SDK'
            r.ref = canon(o.get('event_id'))
            r.delivered_time = parse_instant(o['ts'] if o.get('ts') is not None
                                             else o.get('ts_ms'))
            r.account_raw = o.get('account')
            r.merchant_raw = o.get('merchant')
            r.currency = canon(o.get('currency'))
            if o.get('amount_minor') is not None:
                r.amount = int(o['amount_minor'])
            else:
                r.amount = self._minor(o['amount'], r.currency)
            r.status_raw = canon(o.get('status'))
            r.auth_code = canon(o.get('auth_code'))
            r.entry_raw = canon(o.get('entry'))
            r.device_raw = o.get('device_id')
            r.ip_raw = o.get('ip_ref')
            r.batch = canon(o.get('batch'))
            out.append(r)
        self.file_controls[f] = controls
        return out

    def parse_legacy(self, f):
        controls = []
        out = []
        with open(self.p(f), 'rb') as fh:
            for raw in fh:
                s = raw.decode('iso-8859-1').rstrip('\r\n')
                if not s:
                    continue
                if s[0] == 'T':
                    controls.append('%s|%d|%d' % (s[1:14], int(s[14:23]), int(s[23:38])))
                    continue
                if s[0] != 'D':
                    continue
                r = Record()
                r.file, r.system = f, 'LEG'
                r.ref = canon(s[1:13])
                r.account_raw = s[13:22]
                r.merchant_raw = s[22:30]
                r.time_raw = s[30:44]
                r.amount = int(s[44:57])
                r.currency = canon(s[57:60])
                r.status_raw = canon(s[60:64])
                r.auth_code = canon(s[64:70])
                r.bin = canon(s[70:76])
                r.entry_raw = canon(s[76:80])
                r.batch = canon(s[80:90])
                out.append(r)
        self.file_controls[f] = controls
        return out

    def parse_partner(self, f):
        controls = []
        out = []
        root = ET.parse(self.p(f)).getroot()
        for el in root.iter():
            if el.tag == 'Control':
                controls.append('%s|%s|%s' % (el.get('partition'), el.get('rows'),
                                              el.get('hash')))
            elif el.tag == 'Order':
                r = Record()
                r.file, r.system = f, 'PAR'
                r.ref = canon(el.get('ref'))
                r.batch = canon(el.get('batch'))
                r.account_raw = el.findtext('Customer')
                r.merchant_raw = el.findtext('Merchant')
                r.time_raw = el.findtext('PlacedAt')
                am = el.find('Amount')
                r.currency = canon(am.get('currency'))
                txt = ''.join(am.itertext())
                if trim(am.get('unit') or 'major') == 'minor':
                    r.amount = int(trim(txt))
                else:
                    r.amount = self._minor(txt, r.currency, eu=True)
                r.status_raw = canon(el.findtext('Status'))
                r.auth_code = canon(el.findtext('AuthCode'))
                r.bin = canon(el.findtext('Bin'))
                r.entry_raw = canon(el.findtext('Entry'))
                r.ip_raw = el.findtext('Ip')
                out.append(r)
        self.file_controls[f] = controls
        return out

    def parse_terminal(self, f):
        out = []
        for row in read_parquet(self.p(f)):
            r = Record()
            r.file, r.system = f, 'TRM'
            r.ref = canon(row['trm_event_id'])
            r.terminal = canon(row['terminal_id'])
            r.merchant_raw = row['merchant_id']
            r.account_raw = row['account_id']
            r.time_raw = row['recorded_at']
            r.amount = int(row['amount_minor'])
            r.currency = canon(row['currency'])
            r.status_raw = canon(row['status_code'])
            r.auth_code = canon(row['auth_code'])
            r.bin = canon(row['card_bin'])
            r.entry_raw = canon(row['entry_mode_raw'])
            r.batch = canon(row['batch_id'])
            skew = self.terminal_skew.get(r.terminal, 0) if r.terminal else 0
            r.delivered_time = parse_instant(row['recorded_at']) + \
                dt.timedelta(seconds=skew)
            out.append(r)
        self.file_controls[f] = []
        return out

    def normalize_times(self):
        """Local wall-clock systems need entity context to resolve a zone."""
        for r in self.records:
            if r.delivered_time is not None:
                continue
            naive = parse_naive(r.time_raw)
            if r.system == 'LEG':
                acct = self.canon_account(r.account_raw)
                guess = naive.replace(tzinfo=UTC)
                inst = guess
                for _ in range(2):
                    z = self.account_zone(acct, inst) if acct else None
                    if z is None:
                        inst = guess
                        break
                    inst = z.to_utc(naive)
                r.delivered_time = inst
            else:
                mid = self.canon_merchant(r.merchant_raw, naive.replace(tzinfo=UTC))
                z = None
                if mid:
                    zname = self.merchant_zone.get(mid)
                    if zname:
                        z = self.zone_for(zname)
                r.delivered_time = z.to_utc(naive) if z else naive.replace(tzinfo=UTC)
        for r in self.records:
            r.delivered_amount = r.amount
            r.event_time = r.delivered_time

    def account_zone(self, acct, when):
        postal = canon(self.acct_attr(acct, 'postal', when) or '')
        z = self.postal_zone.get(postal[:4])
        return self.zone_for(z) if z else None

    def apply_errata(self):
        for r in self.records:
            e = self.errata.get((r.file, r.ref))
            if not e:
                continue
            if 'void' in e:
                r.reason = 'voided'
            if 'event_time' in e:
                r.event_time = parse_instant(e['event_time'])
            if 'amount_minor' in e:
                r.amount = int(trim(e['amount_minor']))
            if 'merchant_id' in e:
                r.merchant_raw = trim(e['merchant_id'])

    # ------------------------------------------------------------------
    # lineage reconciliation
    # ------------------------------------------------------------------
    def scope_count(self, src, scope):
        """Record count of one table; a single-table file may name it freely."""
        if (src, scope) in self.rawn:
            return self.rawn[(src, scope)]
        own = [v for (f, s), v in self.rawn.items() if f == src]
        return own[0] if len(own) == 1 else None

    def reconcile(self):
        part = collections.defaultdict(dict)
        for f, recs in self.by_file.items():
            for r in recs:
                key = partition_of(r.delivered_time)
                cur = part[f].setdefault(key, [0, 0])
                cur[0] += 1
                cur[1] += r.delivered_amount
        delivered = {}
        for f, lines in self.file_controls.items():
            if not lines:
                continue
            d = {}
            for ln in lines:
                p, rc, ht = ln.split('|')[:3]
                d[trim(p)] = (int(rc), int(ht))
            delivered[f] = d
        ok = collections.defaultdict(lambda: True)
        seen_part = collections.defaultdict(set)
        for f in self.catalog:
            ok[f] = True
        for src, scope, pkey, rc, ht, dw in self.controls_rows:
            if scope == 'event_rows':
                if dw:
                    exp = delivered.get(dw, {})
                    got = part.get(src, {})
                    if set(exp) != set(got):
                        ok[src] = False
                    else:
                        for k, v in exp.items():
                            if tuple(got[k]) != v:
                                ok[src] = False
                                break
                else:
                    got = part.get(src, {}).get(pkey)
                    seen_part[src].add(pkey)
                    if got is None or got[0] != rc or got[1] != ht:
                        ok[src] = False
            else:
                got = self.scope_count(src, scope)
                if got is None or got != rc:
                    ok[src] = False
        for f, got in part.items():
            if f in seen_part and set(got) != seen_part[f]:
                ok[f] = False
        self.controls_ok = ok
        self.controls_all_ok = all(ok[f] for f in self.catalog)

    # ------------------------------------------------------------------
    def build(self):
        self.mark_candidates()
        self.group_records()
        self.resolve_labels()
        self.build_clusters()
        self.assign_splits()
        self.compute_features()
        self.finalize()

    def mark_candidates(self):
        for r in self.records:
            r.candidate = self.authority(r.file, 'event_rows', r.event_time) == 'primary'
        self.candidates = [r for r in self.records if r.candidate]

    def group_records(self):
        self.groups = collections.OrderedDict()
        for r in self.candidates:
            voided = r.reason == 'voided'
            r.reason = None
            acct = self.canon_account(r.account_raw)
            mid = self.canon_merchant(r.merchant_raw, r.event_time)
            if acct is None or mid is None or \
                    not re.fullmatch(r'[A-Z]{3}', r.currency or ''):
                r.reason = 'invalid_key'
                continue
            r.account, r.merchant = acct, mid
            if r.batch in self.replay_batches:
                r.reason = 'replay'
                continue
            if voided:
                r.reason = 'voided'
                continue
            fp = '|'.join([acct, mid, str(r.amount), r.currency,
                           str(int(r.event_time.timestamp())),
                           canon(r.auth_code)])
            if (r.file.casefold(), r.ref) in self.split_tender:
                fp = fp + '|' + r.ref
            g = self.groups.get(fp)
            if g is None:
                g = Group(fp)
                self.groups[fp] = g
            g.members.append(r)
            r.group = g
        self.ref_group = {}
        for g in self.groups.values():
            g.members.sort(key=self.keeper_key)
            g.keeper = g.members[0]
            g.event_time = g.keeper.event_time
            g.account = g.keeper.account
            g.merchant = g.keeper.merchant
            g.example_id = 'EX-' + hashlib.sha256(
                g.fp.encode('utf-8')).hexdigest()[:16]
            for m in g.members:
                self.ref_group[(m.system, m.ref)] = g
                if m is not g.keeper:
                    m.reason = 'duplicate'
            g.bin = self.first_of(g, lambda m: m.bin or None)
            g.entry = self.first_pair(g, lambda m: m.entry_raw or None)
            g.ip = self.first_of(g, self.ip_of)
            g.device = self.first_of(g, self.device_of)

    @staticmethod
    def ip_of(m):
        v = canon(m.ip_raw)
        return None if v in IP_NONE else v

    @staticmethod
    def device_of(m):
        v = canon(m.device_raw)
        return None if v in DEV_NONE else v

    @staticmethod
    def first_of(g, fn):
        for m in g.members:
            v = fn(m)
            if v:
                return v
        return None

    @staticmethod
    def first_pair(g, fn):
        for m in g.members:
            v = fn(m)
            if v:
                return (m.system, v)
        return None

    def keeper_key(self, r):
        ing = self.batch_ok.get(r.batch)
        return (SYS_PREC.get(r.system, 99),
                ing if ing is not None else dt.datetime.max.replace(tzinfo=UTC),
                r.ref)

    # ------------------------------------------------------------------
    def load_label_sources(self):
        self.load_counts_misc()
        self.load_cases()
        self.load_chargebacks()
        self.load_annotations()
        self.load_feature_sources()

    def load_counts_misc(self):
        self.db_counts = {}
        dbs = [(f, ['cases', 'decisions'])
               for f in self.fs(r'cases\.(?!audit).*')]
        dbs.append((self.f('arn_crosswalk'), ['arn_links']))
        for f, tables in dbs:
            con = sqlite3.connect(self.p(f))
            for t in tables:
                self.note(f, t, con.execute(
                    'select count(*) from "%s"' % t).fetchone()[0])
            con.close()
        self.sheets = {}
        for f in ([self.f('kyc_reviews'), self.f('annotator_roster'),
                   self.f('chargeback_tracker')] +
                  self.fs(r'merchant_risk\..*')):
            sh = read_xlsx(self.p(f))
            self.sheets[f] = sh
            for name, rows in sh.items():
                self.note(f, name, len(rows))
        self.jsonl_recs = {}
        for f in (self.fs(r'annotations\..*') +
                  self.fs(r'ip_reputation\.(?!corrections).*')):
            recs = [o for o in read_jsonl(self.p(f))
                    if '_meta' not in o and '_control' not in o]
            self.jsonl_recs[f] = recs
            self.note(f, 'rows', len(recs))
        rows, _ = read_delimited(self.p(self.f('label_taxonomy')), '\t',
                                 self.cols[self.f('label_taxonomy')] |
                                 {'vendor', 'guideline_version', 'raw_label', 'class'})
        self.note(self.f('label_taxonomy'), 'rows', len(rows))
        self.taxonomy = {}
        for r in rows:
            self.taxonomy[(canon(r['vendor']), canon(r['guideline_version']),
                           canon(r['raw_label']))] = trim(r['class']).lower()
        rows, _ = read_delimited(self.p(self.f('ip_reputation.corrections')), '\t',
                                 self.cols[self.f('ip_reputation.corrections')] |
                                 {'obs_id', 'action', 'new_score', 'reviewed_at'})
        self.ip_corr_rows = rows
        self.note(self.f('ip_reputation.corrections'), 'rows', len(rows))
        self.note(self.f('lineage_controls'), 'controls', len(self.controls_rows))
        nlines = 0
        for ln in raw_lines(self.p(self.f('incident_log'))):
            if ln.strip():
                nlines += 1
        self.note(self.f('incident_log'), 'lines', nlines)


    def load_cases(self):
        self.reverted = set()
        nrev = 0
        for ln in raw_lines(self.p(self.f('cases.audit'))):
            s = ln.strip()
            if s:
                nrev += 1
            if 'DECISION_REVERTED' not in s:
                continue
            parts = s.split()
            kv = dict(p.split('=', 1) for p in parts[1:] if '=' in p)
            when = parse_instant(parts[0])
            if when is not None and when <= self.cutoff:
                self.reverted.add(canon(kv.get('decision')))
        self.note(self.f('cases.audit'), 'lines', nrev)
        con = sqlite3.connect(self.p(self.f('cases.primary')))
        self.cases = {}
        for cid, sysname, ref, opened in con.execute(
                'select case_id, event_system, event_ref, opened_at from cases'):
            self.cases[canon(cid)] = (canon(sysname), canon(ref))
        decisions = {}
        for did, cid, dec, at, who in con.execute(
                'select decision_id, case_id, decision, decided_at, analyst_id '
                'from decisions'):
            decisions[canon(did)] = (canon(cid), trim(str(dec)).lower(),
                                     parse_instant(at))
        con.close()
        for rf in self.fs(r'cases\.(?!audit|primary).*'):
            self.load_replica_cases(rf, decisions)
        self.decisions = decisions

    def load_replica_cases(self, rf, decisions):
        con = sqlite3.connect(self.p(rf))
        for did, cid, dec, at in con.execute(
                'select decision_id, case_id, decision, decided_at from decisions'):
            did = canon(did)
            when = parse_instant(at)
            if did in decisions:
                continue
            if self.authority(rf, 'label_evidence', when) == 'primary':
                decisions[did] = (canon(cid), trim(str(dec)).lower(), when)
        for cid, sysname, ref in con.execute(
                'select case_id, event_system, event_ref from cases'):
            self.cases.setdefault(canon(cid), (canon(sysname), canon(ref)))
        con.close()

    def load_chargebacks(self):
        tracker = self.sheets[self.f('chargeback_tracker')]['Disputes']
        self.arn_original = {}
        self.tracker_withdrawn = {}
        for r in tracker:
            orig = canon(r['arn_original'])
            cur = canon(r['arn_current'])
            if cur and orig and cur != orig:
                self.arn_original[cur] = orig
            w = r.get('withdrawn_on')
            if w:
                wi = excel_instant(w)
                if wi is not None:
                    net = canon(r['network'])
                    for a in (orig, cur):
                        if a:
                            self.tracker_withdrawn[(net, a)] = wi
        self.arn_links = collections.defaultdict(list)
        con = sqlite3.connect(self.p(self.f('arn_crosswalk')))
        for arn, sysname, ref, at in con.execute(
                'select arn, system, record_ref, linked_at from arn_links'):
            self.arn_links[canon(arn)].append((canon(sysname), canon(ref)))
        con.close()
        for f, recs in self.by_file.items():
            if self.authority(f, 'crosswalk', self.cutoff) != 'primary':
                continue
            for r in recs:
                if r.arn:
                    self.arn_links[r.arn].append((r.system, r.ref))
        self.disputes = []
        rows, _ = read_delimited(self.p(self.f('chargebacks.kestrel')), ',',
                                 self.cols[self.f('chargebacks.kestrel')] |
                                 {'dispute_id', 'arn', 'stage', 'stage_date',
                                  'reason_code', 'amount', 'currency', 'network_ref'})
        self.note(self.f('chargebacks.kestrel'), 'rows', len(rows))
        by = collections.OrderedDict()
        for r in rows:
            by.setdefault(canon(r['dispute_id']),
                          {'network': 'KESTREL', 'arn': canon(r['arn']),
                           'stages': []})['stages'].append(
                (trim(r['stage']).lower(), parse_date(r['stage_date']),
                 canon(r['reason_code'])))
        self.disputes.extend(by.values())
        rows, _ = read_delimited(self.p(self.f('chargebacks.orbis')), '\t',
                                 self.cols[self.f('chargebacks.orbis')] |
                                 {'case_no', 'arn', 'phase', 'phase_date', 'reason',
                                  'amt', 'ccy'})
        self.note(self.f('chargebacks.orbis'), 'rows', len(rows))
        by = collections.OrderedDict()
        for r in rows:
            by.setdefault(canon(r['case_no']),
                          {'network': 'ORBIS', 'arn': canon(r['arn']),
                           'stages': []})['stages'].append(
                (trim(r['phase']).lower(), parse_date(r['phase_date']),
                 canon(r['reason'])))
        self.disputes.extend(by.values())
        root = ET.parse(self.p(self.f('chargebacks.vantage'))).getroot()
        nstage = 0
        for d in root.iter('Dispute'):
            stages = []
            for s in d.findall('Stage'):
                nstage += 1
                stages.append((trim(s.get('kind')).lower(), parse_date(s.get('date')),
                               canon(s.get('reason'))))
            self.disputes.append({'network': 'VANTAGE', 'arn': canon(d.get('arn')),
                                  'stages': stages, 'id': canon(d.get('id'))})
        self.note(self.f('chargebacks.vantage'), 'disputes', nstage)
        self.load_notices()

    def load_notices(self):
        self.notice = {}
        count = 0
        import email
        import email.policy
        cur = []
        msgs = []
        for ln in raw_lines(self.p(self.f('dispute_notices'))):
            if ln.startswith('From ') and cur:
                msgs.append(cur)
                cur = [ln]
            else:
                cur.append(ln)
        if cur:
            msgs.append(cur)
        for raw in msgs:
            count += 1
            msg = email.message_from_string('\n'.join(raw[1:]),
                                            policy=email.policy.default)
            try:
                body = msg.get_content()
            except Exception:
                body = msg.get_payload(decode=True).decode('utf-8', 'replace')
            when = None
            try:
                when = parsedate_to_datetime(msg['Date']).astimezone(UTC)
            except Exception:
                when = None
            arn = None
            action = None
            for line in str(body).split('\n'):
                line = line.strip()
                if line.upper().startswith('ARN:'):
                    arn = canon(line.split(':', 1)[1])
                elif line.upper().startswith('ACTION:'):
                    action = canon(line.split(':', 1)[1])
            if not arn or action not in ('WITHDRAWN', 'REINSTATED'):
                continue
            if when is None or when > self.cutoff:
                continue
            prev = self.notice.get(arn)
            if prev is None or when >= prev[0]:
                self.notice[arn] = (when, action)
        self.note(self.f('dispute_notices'), 'messages', count)

    def load_annotations(self):
        self.tasks = {}
        ntask = 0
        root = ET.parse(self.p(self.f('annotation_tasks'))).getroot()
        for t in root.iter('Task'):
            ntask += 1
            ev = t.find('EventRef')
            self.tasks[canon(t.get('id'))] = (canon(ev.get('system')),
                                              canon(ev.text))
        self.note(self.f('annotation_tasks'), 'tasks', ntask)
        man = json.loads(read_text(self.p(self.f('annotation_batches'))))
        self.note(self.f('annotation_batches'), 'tasks', len(man['tasks']))
        self.batch_manifest = {}
        for t in man['tasks']:
            self.batch_manifest[canon(t['task_id'])] = (
                canon(t.get('batch_id')),
                trim(str(t['guideline_version'])) if t.get('guideline_version') else None,
                trim(str(t.get('batch_status') or '')).lower())
        roster = self.sheets[self.f('annotator_roster')]
        self.annot_vendor = {}
        for r in roster['Annotators']:
            self.annot_vendor[canon(r['annotator_id'])] = canon(r['vendor'])
        self.tier_hist = collections.defaultdict(list)
        for r in roster['TierHistory']:
            self.tier_hist[canon(r['annotator_id'])].append(
                (excel_instant(r['effective_from'], 1904), trim(str(r['tier'])).lower()))
        for k in self.tier_hist:
            self.tier_hist[k].sort(key=lambda x: x[0])
        self.vt_cross = {}
        self.annot_withdrawn = set()
        for o in read_jsonl(self.p(self.f('annotations.b.r2'))):
            if '_crosswalk' in o:
                cw = o['_crosswalk']
                self.vt_cross[canon(cw['old_annotator'])] = canon(cw['annotator'])
            elif trim(str(o.get('status') or '')).lower() == 'withdrawn':
                self.annot_withdrawn.add(canon(o['annotation_id']))
        self.annotations = []
        for f in self.fs(r'annotations\..*'):
            if self.authority(f, 'label_evidence', self.cutoff) != 'primary':
                continue
            self.annotations.extend(self.jsonl_recs[f])

    def load_feature_sources(self):
        self.snap_registry = {}
        reg = json.loads(read_text(self.p(self.f('snapshot_registry'))))
        self.note(self.f('snapshot_registry'), 'snapshots',
                  len(reg['snapshots']))
        for s in reg['snapshots']:
            self.snap_registry[canon(s['snapshot_id'])] = trim(str(s.get('status') or '')).lower()
        man = json.loads(read_text(self.p(self.f('feature_store_manifest'))))
        self.note(self.f('feature_store_manifest'), 'partitions',
                  len(man['partitions']))
        self.ip_partitions = {}
        for p in man['partitions']:
            self.ip_partitions[canon(p['partition'])] = bool(p.get('quarantined'))
        self.calendar = self.load_calendar()
        self.load_merchant_risk()
        self.load_ip_rep()
        self.load_kyc()

    def load_calendar(self):
        events = []
        cur = None
        for ln in raw_lines(self.p(self.f('publication_calendar'))):
            s = ln.strip()
            if s == 'BEGIN:VEVENT':
                cur = {}
            elif s == 'END:VEVENT':
                if cur is not None:
                    events.append(cur)
                cur = None
            elif cur is not None and ':' in s:
                name, value = s.split(':', 1)
                parts = name.split(';')
                key = parts[0]
                params = dict(p.split('=', 1) for p in parts[1:] if '=' in p)
                cur[key] = (value, params)
        out = []
        self.cal_by_uid = {}
        for e in events:
            uid = canon(e.get('UID', ('', {}))[0])
            dtv, params = e.get('DTSTART', ('', {}))
            status = trim(e.get('STATUS', ('', {}))[0]).upper()
            inst = self.parse_ics_dt(dtv, params)
            out.append((uid, inst, status))
            self.cal_by_uid[uid] = (inst, status)
        self.note(self.f('publication_calendar'), 'events', len(out))
        return out

    def parse_ics_dt(self, value, params):
        v = trim(value)
        if v.endswith('Z'):
            return dt.datetime(int(v[0:4]), int(v[4:6]), int(v[6:8]), int(v[9:11]),
                               int(v[11:13]), int(v[13:15]), tzinfo=UTC)
        naive = dt.datetime(int(v[0:4]), int(v[4:6]), int(v[6:8]), int(v[9:11]),
                            int(v[11:13]), int(v[13:15]))
        z = self.zone_for(params.get('TZID', ''))
        return z.to_utc(naive) if z else naive.replace(tzinfo=UTC)

    def load_merchant_risk(self):
        self.void_snap = set()
        for f in self.fs(r'merchant_risk\..*'):
            if self.authority(f, 'void_evidence', self.cutoff) != 'primary':
                continue
            for rows in self.sheets[f].values():
                for r in rows:
                    if trim(str(r.get('status') or '')).lower() == 'void':
                        self.void_snap.add((canon(r['snapshot_id']),
                                            canon(r['merchant_id'])))
        self.risk_rows = collections.defaultdict(list)
        self.risk_corr = collections.defaultdict(list)
        for f in self.fs(r'merchant_risk\..*'):
            if self.authority(f, 'feature_values', self.cutoff) != 'primary':
                continue
            sh = self.sheets[f]
            for r in sh['Snapshot']:
                sid = canon(r['snapshot_id'])
                mid = canon(r['merchant_id'])
                raw = r['cb_rate_bps']
                if raw is None or canon(raw) == 'N/A':
                    continue
                if (sid, mid) in self.void_snap:
                    continue
                if self.snap_registry.get(sid) == 'withdrawn':
                    continue
                cal = self.cal_by_uid.get(sid)
                if cal is None or cal[0] is None or cal[1] == 'CANCELLED':
                    continue
                pub = self.effective_publication(cal[0], 'feature-store')
                avail = pub + self.lag_for('merchant_risk', pub)
                self.risk_rows[mid].append((parse_date(r['as_of']), pub, sid,
                                            int(raw), avail))
            for r in sh.get('Corrections', ()):
                sid = canon(r['snapshot_id'])
                mid = canon(r['merchant_id'])
                at = excel_instant(r['corrected_at'])
                if at is None:
                    continue
                eff = at + self.lag_for('merchant_risk', at)
                self.risk_corr[(sid, mid)].append((at, eff, int(r['corrected_bps'])))
        for k in self.risk_rows:
            self.risk_rows[k].sort(key=lambda x: (x[0], x[1], x[2]))
        for k in self.risk_corr:
            self.risk_corr[k].sort(key=lambda x: x[0])

    def merchant_cb_rate(self, merchant, when):
        best = None
        for as_of, pub, sid, val, avail in self.risk_rows.get(merchant, ()):
            if avail <= when:
                key = (as_of, pub, sid)
                if best is None or key > best[0]:
                    best = (key, sid, val)
        if best is None:
            return None
        sid, val = best[1], best[2]
        for at, eff, cval in self.risk_corr.get((sid, merchant), ()):
            if eff <= when:
                val = cval
        return val

    def load_ip_rep(self):
        corr = {}
        for r in self.ip_corr_rows:
            oid = canon(r['obs_id'])
            act = trim(r['action']).lower()
            rv = parse_instant(r['reviewed_at'])
            if rv is None:
                continue
            prev = corr.get(oid)
            if prev is None or rv >= prev[0]:
                corr[oid] = (rv, act, trim(r['new_score']))
        self.ip_obs = collections.defaultdict(list)
        for f in self.fs(r'ip_reputation\.(?!corrections).*'):
            if self.authority(f, 'feature_values', self.cutoff) != 'primary':
                continue
            for o in self.jsonl_recs[f]:
                oid = canon(o['obs_id'])
                part = canon(o['partition'])
                if self.ip_partitions.get(part):
                    continue
                score = o['score']
                c = corr.get(oid)
                if c:
                    if c[1] == 'void':
                        continue
                    if c[1] == 'rescore' and c[2] != '':
                        score = int(trim(c[2]))
                score = int(score)
                if score == -1:
                    continue
                pub = self.ip_pub.get(part)
                if pub is None:
                    continue
                pub = self.effective_publication(pub, 'feature-store-ip')
                avail = pub + self.lag_for('ip_reputation', pub)
                self.ip_obs[canon(o['ip'])].append(
                    (parse_instant(o['observed_at']), oid, score, avail))
        for k in self.ip_obs:
            self.ip_obs[k].sort(key=lambda x: (x[0], x[1]))

    def ip_risk(self, ip, when):
        best = None
        for observed, oid, score, avail in self.ip_obs.get(ip, ()):
            if avail <= when:
                if best is None or (observed, oid) > best[0]:
                    best = ((observed, oid), score)
        return best[1] if best else None

    def load_kyc(self):
        sh = self.sheets[self.f('kyc_reviews')]
        overturned = set()
        for r in sh['Appeals']:
            if trim(str(r['outcome'] or '')).lower() != 'overturned':
                continue
            at = excel_instant(r['decided_at'])
            if at is None or at <= self.cutoff:
                overturned.add(canon(r['review_id']))
        self.kyc_rows = collections.defaultdict(list)
        for r in sh['Reviews']:
            rid = canon(r['review_id'])
            if rid in overturned:
                continue
            tier = int(r['tier'])
            if tier == 9:
                continue
            at = excel_instant(r['effective_at'])
            if at is None:
                continue
            self.kyc_rows[canon(r['account_id'])].append((at, rid, tier))
        for k in self.kyc_rows:
            self.kyc_rows[k].sort(key=lambda x: (x[0], x[1]))

    def kyc_tier(self, acct, when):
        best = None
        for at, rid, tier in self.kyc_rows.get(acct, ()):
            if at <= when:
                best = tier
            else:
                break
        if best is not None:
            return best
        seg = canon(self.acct_attr(acct, 'segment', when) or '')
        postal = canon(self.acct_attr(acct, 'postal', when) or '')
        region = self.postal_region.get(postal)
        if region is None:
            return None
        return self.kyc_default.get((seg, region))

    # ------------------------------------------------------------------
    def resolve_labels(self):
        self.case_decision = self.pick_case_decisions()
        self.cb_evidence = self.pick_chargebacks()
        self.vendor_votes = self.pick_vendor()

    def pick_case_decisions(self):
        per_case = {}
        for did, (cid, dec, when) in self.decisions.items():
            if did in self.reverted:
                continue
            if when is None:
                continue
            prev = per_case.get(cid)
            key = (when, did)
            if prev is None or key > prev[0]:
                per_case[cid] = (key, dec)
        out = {}
        for cid, (key, dec) in per_case.items():
            ev = self.cases.get(cid)
            if ev is None:
                continue
            g = self.ref_group.get(ev)
            if g is None:
                continue
            prev = out.get(id(g))
            if prev is None or key > prev[0]:
                out[id(g)] = (key, dec)
        return out

    def dispute_void(self, d):
        for kind, when, reason in d['stages']:
            if kind in ('cb_reversal', 'cb reversal', 'reversal'):
                if when is not None and \
                        dt.datetime.combine(when, dt.time(), UTC) <= self.cutoff:
                    return True
        n = self.notice.get(d['arn'])
        if n and n[1] == 'WITHDRAWN':
            return True
        w = self.tracker_withdrawn.get((d['network'], d['arn']))
        if w is not None and w <= self.cutoff:
            return True
        return False

    def pick_chargebacks(self):
        out = {}
        for d in self.disputes:
            firsts = [s for s in d['stages']
                      if s[0] in ('first_cb', '1st cb', 'first')]
            if not firsts:
                continue
            firsts.sort(key=lambda s: s[1])
            kind, when, reason = firsts[0]
            if when is None or not reason:
                continue
            if self.dispute_void(d):
                continue
            arn = d['arn']
            arn = self.arn_original.get(arn, arn)
            targets = self.arn_links.get(arn)
            if not targets:
                continue
            code = reason
            if d['network'] == 'ORBIS' and when < dt.date(2026, 7, 1):
                code = self.orbis_renumber.get(code, code)
            if self.reason_class.get((d['network'], code)) != 'fraud':
                continue
            for ev in targets:
                g = self.ref_group.get(ev)
                if g is None:
                    continue
                if self.merchant_profile.get(g.merchant) == 'friendly_fraud_prone':
                    continue
                ed = g.event_time.date()
                if when < ed or when >= ed + dt.timedelta(days=self.maturity):
                    continue
                out[id(g)] = True
        return out

    def tier_at(self, annot, when):
        best = None
        for at, tier in self.tier_hist.get(annot, ()):
            if at is not None and at <= when:
                best = tier
            else:
                break
        return best

    def pick_vendor(self):
        tally = collections.defaultdict(lambda: [0, 0])
        for a in self.annotations:
            aid = canon(a['annotation_id'])
            if aid in self.annot_withdrawn:
                continue
            tid = canon(a['task_id'])
            man = self.batch_manifest.get(tid)
            if man is None or man[1] is None:
                continue
            batch, gver, bstatus = man
            if bstatus == 'recalled':
                continue
            ev = self.tasks.get(tid)
            if ev is None:
                continue
            g = self.ref_group.get(ev)
            if g is None:
                continue
            annot = canon(a['annotator'])
            annot = self.vt_cross.get(annot, annot)
            vendor = self.annot_vendor.get(annot)
            if vendor is None:
                continue
            if (annot, batch) in self.gold_fail:
                continue
            when = parse_instant(a['submitted_at'])
            if when is None or when > self.cutoff:
                continue
            tier = self.tier_at(annot, when)
            w = TIER_WEIGHT.get(tier, 0) if tier else 0
            if w == 0:
                continue
            cls = self.taxonomy.get((vendor, canon(gver), canon(a['label'])))
            if cls == 'fraud':
                tally[id(g)][0] += w
            elif cls == 'legit':
                tally[id(g)][1] += w
        return tally

    # ------------------------------------------------------------------
    def build_clusters(self):
        link_start = {}
        unlink = {}
        for when, action, acct, dev in self.link_events:
            if when is None or when > self.cutoff:
                continue
            a = self.canon_account(acct)
            if a is None or not dev:
                continue
            key = (a, dev)
            if action == 'LINK':
                if key not in link_start or when < link_start[key]:
                    link_start[key] = when
            elif action == 'UNLINK':
                if key not in unlink or when > unlink[key]:
                    unlink[key] = when
        for acct, dev, first in self.fingerprints:
            if first is None or first > self.cutoff:
                continue
            a = self.canon_account(acct)
            if a is None or not dev:
                continue
            key = (a, dev)
            if key not in link_start or first < link_start[key]:
                link_start[key] = first
        revoked = {}
        for acct, dev, action, when in self.revocations:
            if when is None or when > self.cutoff:
                continue
            a = self.canon_account(acct)
            if a is None:
                continue
            key = (a, dev)
            prev = revoked.get(key)
            if prev is None or when >= prev[0]:
                revoked[key] = (when, action)
        dev_accounts = collections.defaultdict(set)
        for (a, dev), start in link_start.items():
            if self.device_kind.get(dev) == 'kiosk' or dev in self.device_exempt:
                continue
            u = unlink.get((a, dev))
            if u is not None and u > start:
                continue
            rv = revoked.get((a, dev))
            if rv is not None and rv[1] == 'revoke':
                continue
            dev_accounts[dev].add(a)
        parent = {}

        def find(x):
            parent.setdefault(x, x)
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                if ra < rb:
                    parent[rb] = ra
                else:
                    parent[ra] = rb

        for dev, accts in dev_accounts.items():
            accts = sorted(accts)
            for a in accts[1:]:
                union(accts[0], a)
        self.cluster_of = {}
        for a in list(parent):
            self.cluster_of[a] = find(a)
        comp = collections.defaultdict(list)
        for a, root in self.cluster_of.items():
            comp[root].append(a)
        self.cluster_id = {}
        for root, members in comp.items():
            cid = min(members)
            for m in members:
                self.cluster_id[m] = cid

    def cluster_for(self, acct):
        return self.cluster_id.get(acct, acct)

    def assign_splits(self):
        prior_split = {}
        prior_ids = set()
        if self.prior:
            for c in self.prior.get('clusters', ()):
                prior_split[canon(c['account_id'])] = trim(c['split'])
            prior_ids = set(self.prior.get('released_example_ids', ()))
        self.prior_ids = prior_ids
        self.candidate_groups = []
        for g in self.groups.values():
            r = self.group_reason(g)
            g.reason = r
            if r is None:
                self.candidate_groups.append(g)
        cluster_members = collections.defaultdict(set)
        for g in self.candidate_groups:
            cluster_members[self.cluster_for(g.account)].add(g.account)
        pin_split = {}
        for pin in self.pins:
            if trim(str(pin.get('status') or '')).lower() != 'active':
                continue
            ev = canon(pin['event_ref'])
            if ':' not in ev:
                continue
            sysname, ref = ev.split(':', 1)
            g = self.ref_group.get((sysname, ref))
            if g is None or g.reason is not None:
                continue
            cid = self.cluster_for(g.account)
            s = trim(pin['split'])
            cur = pin_split.get(cid)
            if cur != 'test':
                pin_split[cid] = 'test' if s == 'test' else (cur or s)
        prior_cluster = collections.defaultdict(set)
        if prior_split:
            allaccts = set()
            for g in self.candidate_groups:
                allaccts.add(g.account)
            cl_accounts = collections.defaultdict(set)
            for a in set(list(allaccts) + list(prior_split)):
                cl_accounts[self.cluster_for(a)].add(a)
            for cid, accts in cl_accounts.items():
                for a in accts:
                    if a in prior_split:
                        prior_cluster[cid].add(prior_split[a])
        self.cluster_split = {}
        for cid in set(list(cluster_members) +
                       [self.cluster_for(g.account) for g in self.candidate_groups]):
            s = self.bucket_split(cid)
            if cid in pin_split:
                s = pin_split[cid]
            pr = prior_cluster.get(cid)
            if pr:
                for cand in ('test', 'val', 'train'):
                    if cand in pr:
                        s = cand
                        break
            self.cluster_split[cid] = s
        for g in self.candidate_groups:
            cid = self.cluster_for(g.account)
            g.cluster = cid
            g.split = 'oot' if g.event_time >= self.oot_start else self.cluster_split[cid]

    def bucket_split(self, cid):
        h = hashlib.sha256((self.salt + ':' + cid).encode('utf-8')).hexdigest()
        b = int(h[:8], 16) % 100
        if b < self.train_below:
            return 'train'
        if b < self.val_below:
            return 'val'
        return 'test'

    def group_reason(self, g):
        """Reason the example is not released, or None."""
        k = g.keeper
        meaning = self.status_meaning.get((k.system, k.status_raw))
        if meaning in ('declined', 'reversed', 'refund'):
            return meaning
        if meaning == 'test':
            return 'test_transaction'
        if self.delta and g.example_id in self.prior_ids:
            return 'already_released'
        if g.event_time < self.window_start:
            return 'lookback_context'
        if g.event_time >= self.window_end:
            return 'outside_window'
        if g.account in self.withdrawn:
            return 'consent_withdrawn'
        for m in g.members:
            if (m.system + ':' + m.ref) in self.retracted_refs:
                return 'retracted'
        mature = g.event_time + dt.timedelta(seconds=self.maturity * 86400) <= self.cutoff
        dec = self.case_decision.get(id(g))
        analyst = dec[1] if dec else None
        if analyst == 'confirmed_fraud':
            g.label, g.label_source = 1, 'analyst'
            return None
        if not mature:
            return 'immature_label'
        if analyst == 'confirmed_legit':
            g.label, g.label_source = 0, 'analyst'
            return None
        if self.cb_evidence.get(id(g)):
            g.label, g.label_source = 1, 'chargeback'
            return None
        votes = self.vendor_votes.get(id(g))
        if votes and (votes[0] or votes[1]):
            if votes[0] > votes[1]:
                g.label, g.label_source = 1, 'vendor'
            elif votes[0] < votes[1]:
                g.label, g.label_source = 0, 'vendor'
            else:
                return 'unresolved_label'
            return None
        g.label, g.label_source = 0, 'no_chargeback'
        return None

    # ------------------------------------------------------------------
    def compute_features(self):
        kept = [g for g in self.groups.values()]
        by_acct = collections.defaultdict(list)
        for g in kept:
            g.features = {}
            usd = self.to_usd_cents(g.keeper.amount, g.keeper.currency, g.event_time)
            g.features['amount_usd_cents'] = usd
            by_acct[g.account].append(g)
        for acct, gs in by_acct.items():
            gs.sort(key=lambda x: int(x.event_time.timestamp()))
        self.by_acct = by_acct
        for g in self.candidate_groups:
            t = int(g.event_time.timestamp())
            gs = by_acct[g.account]
            times = [int(x.event_time.timestamp()) for x in gs]
            lo = bisect.bisect_left(times, t - self.vel_count_w)
            hi = bisect.bisect_left(times, t)
            cnt = hi - lo
            lo2 = bisect.bisect_left(times, t - self.vel_sum_w)
            total = 0
            for x in gs[lo2:hi]:
                v = x.features.get('amount_usd_cents')
                if v is not None:
                    total += v
            created = self.acct_attr(g.account, 'created_at', g.event_time)
            ci = parse_instant(created) if created else None
            age = None
            if ci is not None:
                age = int((g.event_time - ci).total_seconds() // 86400)
            f = g.features
            f['account_age_days'] = age
            f['txn_count_24h'] = cnt
            f['amount_sum_7d_usd_cents'] = total
            f['merchant_cb_rate_bps'] = self.merchant_cb_rate(g.merchant, g.event_time)
            f['ip_risk_score'] = self.ip_risk(g.ip, g.event_time) if g.ip else None
            f['kyc_tier'] = self.kyc_tier(g.account, g.event_time)
            ent = 'UNKNOWN'
            if g.entry and canon(g.entry[1]) != '????':
                ent = self.entry_mode.get((g.entry[0], canon(g.entry[1]))) or 'UNKNOWN'
            sub = self.mcc_subcode(g.merchant, g.event_time)
            g.categorical = {
                'entry_mode': ent,
                'mcc_risk_group': self.mcc_group.get(canon(sub), 'UNMAPPED') if sub
                else 'UNMAPPED',
                'issuer_group': self.issuer_group(g.bin or ''),
            }

    # ------------------------------------------------------------------
    def finalize(self):
        rel = self.candidate_groups
        self.released = sorted(rel, key=lambda g: (g.event_time, g.example_id))
        train = [g for g in self.released if g.split == 'train']
        frozen = self.prior if self.delta else None
        self.fit = {}
        for name in self.numeric:
            if frozen:
                fs = frozen['features'][name]
                p01 = Decimal(fs['p01'])
                p99 = Decimal(fs['p99'])
                med = Decimal(fs['median'])
                q1 = Decimal(fs['q1'])
                q3 = Decimal(fs['q3'])
            else:
                vals = sorted(Decimal(g.features[name]) for g in train
                              if g.features.get(name) is not None)
                if vals:
                    p01 = nearest_rank(vals, 1, 100)
                    p99 = nearest_rank(vals, 99, 100)
                    clipped = sorted(min(max(v, p01), p99) for v in vals)
                    med = nearest_rank(clipped, 1, 2)
                    q1 = nearest_rank(clipped, 1, 4)
                    q3 = nearest_rank(clipped, 3, 4)
                else:
                    p01 = p99 = med = q1 = q3 = Decimal(0)
            self.fit[name] = (p01, p99, med, q1, q3)
        for g in self.released:
            g.scaled = {}
            for name in self.numeric:
                p01, p99, med, q1, q3 = self.fit[name]
                v = g.features.get(name)
                if v is None:
                    v = med
                    g.imputed.add(name)
                else:
                    v = Decimal(v)
                    if v < p01:
                        v = p01
                    elif v > p99:
                        v = p99
                if q3 == q1:
                    s = v - med
                else:
                    s = (v - med) / (q3 - q1)
                g.scaled[name] = Decimal(q6(s))
        # vocabularies
        self.vocab = {}
        self.vocab_index = {}
        for name in self.categ:
            if frozen:
                tokens = list(frozen['vocab'][name])
            else:
                cnt = collections.Counter(g.categorical[name] for g in train)
                keep = [(-n, t) for t, n in cnt.items() if n >= self.min_vocab]
                keep.sort()
                tokens = [RARE] + [t for _, t in keep]
            self.vocab[name] = tokens
            self.vocab_index[name] = {t: i for i, t in enumerate(tokens)}
        for g in self.released:
            g.categorical = {n: self.vocab_index[n].get(g.categorical[n], 0)
                             for n in self.categ}
        # class weights
        if frozen:
            self.class_weights = {'0': frozen['class_weights']['0'],
                                  '1': frozen['class_weights']['1']}
        else:
            n0 = sum(1 for g in train if g.label == 0)
            n1 = sum(1 for g in train if g.label == 1)
            self.class_weights = self.compute_weights(n0, n1)
        for g in self.released:
            if g.split == 'train':
                g.sample_weight = self.class_weights[str(g.label)]
            else:
                g.sample_weight = '1.000000'
        for g in self.released:
            total = self.coef.get('intercept', Decimal(0))
            for name in self.numeric:
                total += self.coef.get(name, Decimal(0)) * g.scaled[name]
            total += self.merch_offset.get(g.merchant, Decimal(0))
            g.score = Decimal(q6(total))
        self.fit_psi(train)

    def compute_weights(self, n0, n1):
        beta = self.beta
        num = beta.numerator
        den = beta.denominator

        def E(n):
            if n <= 0:
                return None
            return Fraction(den ** n - num ** n, den ** n) / (1 - beta)
        e0, e1 = E(n0), E(n1)
        if e0 is None or e1 is None:
            out = {}
            for key, e in (('0', e0), ('1', e1)):
                out[key] = '1.000000'
            return out
        s = 1 / e0 + 1 / e1
        return {'0': frac_round((1 / e0) * 2 / s),
                '1': frac_round((1 / e1) * 2 / s)}

    def fit_psi(self, train):
        oot = [g for g in self.released if g.split == 'oot']
        self.psi_edges = {}
        self.psi_train_props = {}
        self.psi = {}
        for name in self.numeric:
            if self.delta:
                edges = [Decimal(e) for e in self.prior['psi_edges'][name]]
                tprops = [Decimal(p) for p in self.prior['psi_train_props'][name]]
            else:
                vals = sorted(g.scaled[name] for g in train)
                if vals:
                    edges = [nearest_rank(vals, k, 10) for k in range(1, 10)]
                else:
                    edges = [Decimal(0)] * 9
                counts = [0] * (len(edges) + 1)
                for v in vals:
                    counts[psi_bin(edges, v)] += 1
                n = len(vals)
                tprops = [props_value(c, n) for c in counts]
            self.psi_edges[name] = [str(e.quantize(Q6)) if isinstance(e, Decimal)
                                    else str(e) for e in edges]
            self.psi_train_props[name] = [str(p.quantize(Q6)) for p in tprops]
            ocounts = [0] * (len(edges) + 1)
            for g in oot:
                ocounts[psi_bin(edges, g.scaled[name])] += 1
            on = len(oot)
            oprops = [props_value(c, on) for c in ocounts]
            self.psi[name] = psi_value(tprops, oprops)

    # ------------------------------------------------------------------
    def write_held(self):
        ensure_dir(self.out)
        rid = getattr(self, 'release_id', None) or self.read_release_id()
        write_text(os.path.join(self.out, 'normalized.jsonl'), '')
        small = {'release_id': rid, 'status': 'HELD'}
        write_json(os.path.join(self.out, 'summary.json'), small)
        write_json(os.path.join(self.out, 'product_summary.json'), small)
        for grp in REGION_GROUPS:
            write_json(os.path.join(self.out, 'region_%s.json' % grp), small)
        for grp in SEGMENT_GROUPS:
            write_json(os.path.join(self.out, 'segment_%s.json' % grp), small)
        sources = [{'file': f, 'present': os.path.exists(self.p(f))}
                   for f in self.catalog]
        write_json(os.path.join(self.out, 'data_quality.json'),
                   {'release_id': rid, 'status': 'HELD', 'sources': sources,
                    'exclusions': []})

    def write_outputs(self):
        ensure_dir(self.out)
        lines = []
        for g in self.released:
            obj = collections.OrderedDict()
            obj['example_id'] = g.example_id
            obj['event_ref'] = g.keeper.system + ':' + g.keeper.ref
            obj['account_id'] = g.account
            obj['cluster_id'] = g.cluster
            obj['split'] = g.split
            obj['event_time'] = iso_z(g.event_time)
            obj['label'] = g.label
            obj['label_source'] = g.label_source
            obj['sample_weight'] = g.sample_weight
            obj['features'] = collections.OrderedDict(
                (n, str(g.scaled[n])) for n in self.numeric)
            obj['categorical'] = collections.OrderedDict(
                (n, g.categorical[n]) for n in self.categ)
            obj['score'] = str(g.score)
            lines.append(json.dumps(obj, ensure_ascii=False))
        write_text(os.path.join(self.out, 'normalized.jsonl'),
                   ''.join(ln + '\n' for ln in lines))

        counts = collections.OrderedDict()
        for s in SPLITS:
            gs = [g for g in self.released if g.split == s]
            counts[s] = collections.OrderedDict(
                [('n', len(gs)), ('positives', sum(1 for g in gs if g.label == 1))])
        auc = collections.OrderedDict()
        for s in EVAL_SPLITS:
            auc[s] = compute_auc([g for g in self.released if g.split == s])
        summary = collections.OrderedDict()
        summary['release_id'] = self.release_id
        summary['status'] = self.status
        summary['counts'] = counts
        summary['auc'] = auc
        summary['psi'] = collections.OrderedDict(
            (n, self.psi[n]) for n in self.numeric)
        summary['imputed'] = collections.OrderedDict(
            (n, sum(1 for g in self.released if n in g.imputed)) for n in self.numeric)
        write_json(os.path.join(self.out, 'summary.json'), summary)

        prod = collections.OrderedDict()
        prod['release_id'] = self.release_id
        prod['status'] = self.status
        prod['parameters'] = collections.OrderedDict(
            (k, v) for k, v in self.cfg.items())
        prod['features'] = collections.OrderedDict()
        for n in self.numeric:
            p01, p99, med, q1, q3 = self.fit[n]
            prod['features'][n] = collections.OrderedDict(
                [('p01', q6(p01)), ('p99', q6(p99)), ('median', q6(med)),
                 ('q1', q6(q1)), ('q3', q6(q3))])
        prod['vocab'] = collections.OrderedDict(
            (n, list(self.vocab[n])) for n in self.categ)
        prod['class_weights'] = collections.OrderedDict(
            [('0', self.class_weights['0']), ('1', self.class_weights['1'])])
        prod['psi_edges'] = collections.OrderedDict(
            (n, self.psi_edges[n]) for n in self.numeric)
        prod['psi_train_props'] = collections.OrderedDict(
            (n, self.psi_train_props[n]) for n in self.numeric)
        accounts = {}
        for g in self.released:
            accounts[g.account] = g.cluster
        clusters = []
        for acct in sorted(accounts):
            cid = accounts[acct]
            clusters.append(collections.OrderedDict(
                [('account_id', acct), ('cluster_id', cid),
                 ('split', self.cluster_split[cid])]))
        prod['clusters'] = clusters
        prod['released_example_ids'] = sorted(g.example_id for g in self.released)
        write_json(os.path.join(self.out, 'product_summary.json'), prod)

        for grp in REGION_GROUPS:
            sel = [g for g in self.released if self.region_of(g) == grp]
            write_json(os.path.join(self.out, 'region_%s.json' % grp),
                       self.slice_report('region_group:' + grp, sel))
        for grp in SEGMENT_GROUPS:
            sel = [g for g in self.released if self.segment_of(g) == grp]
            write_json(os.path.join(self.out, 'segment_%s.json' % grp),
                       self.slice_report('segment_group:' + grp, sel))

        self.write_data_quality()

    def region_of(self, g):
        postal = canon(self.acct_attr(g.account, 'postal', g.event_time) or '')
        region = self.postal_region.get(postal)
        return self.region_group.get(region) if region else None

    def segment_of(self, g):
        seg = canon(self.acct_attr(g.account, 'segment', g.event_time) or '')
        return self.segment_group.get(seg)

    def slice_report(self, name, sel):
        counts = collections.OrderedDict()
        for s in SPLITS:
            gs = [g for g in sel if g.split == s]
            counts[s] = collections.OrderedDict(
                [('n', len(gs)), ('positives', sum(1 for g in gs if g.label == 1))])
        auc = collections.OrderedDict()
        for s in EVAL_SPLITS:
            auc[s] = compute_auc([g for g in sel if g.split == s])
        out = collections.OrderedDict()
        out['release_id'] = self.release_id
        out['status'] = self.status
        out['slice'] = name
        out['counts'] = counts
        out['auc'] = auc
        return out

    def write_data_quality(self):
        records = collections.Counter()
        for src, scope, pkey, rc, ht, dw in self.controls_rows:
            if scope == 'event_rows':
                continue
            records[src] += self.scope_count(src, scope) or 0
        for f, recs in self.by_file.items():
            records[f] = len(recs)
        cand = collections.Counter()
        for r in self.candidates:
            cand[r.file] += 1
        rel = collections.Counter()
        for g in self.released:
            rel[g.keeper.file] += 1
        sources = []
        for f in self.catalog:
            sources.append(collections.OrderedDict(
                [('file', f), ('records', records.get(f, 0)),
                 ('controls_ok', bool(self.controls_ok[f])),
                 ('candidates', cand.get(f, 0)),
                 ('released', rel.get(f, 0))]))
        exclusions = []
        released_groups = set(id(g) for g in self.candidate_groups)
        for r in self.candidates:
            reason = r.reason
            if reason is None:
                g = r.group
                if g is None:
                    continue
                if id(g) in released_groups:
                    continue
                reason = g.reason
            if reason is None:
                continue
            exclusions.append((r.file, r.ref, reason))
        exclusions.sort(key=lambda x: (x[0], x[1]))
        out = collections.OrderedDict()
        out['release_id'] = self.release_id
        out['status'] = self.status
        out['sources'] = sources
        out['exclusions'] = [collections.OrderedDict(
            [('file', f), ('record_ref', ref), ('reason', reason)])
            for f, ref, reason in exclusions]
        write_json(os.path.join(self.out, 'data_quality.json'), out)


def partition_of(instant):
    t = instant.astimezone(UTC)
    return '%04d-%02d-%02dT%02d' % (t.year, t.month, t.day, (t.hour // 3) * 3)


def psi_bin(edges, v):
    return sum(1 for e in edges if e < v)


def props_value(count, total):
    floor = Decimal('0.0001')
    if total <= 0:
        return floor
    with localcontext() as ctx:
        ctx.prec = 40
        p = Decimal(count) / Decimal(total)
    p = p.quantize(Q6, rounding=ROUND_HALF_EVEN)
    return floor if p < floor else p


def psi_value(tprops, oprops):
    with localcontext() as ctx:
        ctx.prec = 40
        total = Decimal(0)
        for e, a in zip(tprops, oprops):
            if a <= 0 or e <= 0:
                continue
            total += (a - e) * (a / e).ln()
    return str(total.quantize(Q6, rounding=ROUND_HALF_EVEN))


def compute_auc(groups):
    pos = [g.score for g in groups if g.label == 1]
    neg = [g.score for g in groups if g.label == 0]
    if not pos or not neg:
        return None
    allscores = sorted(set(pos) | set(neg))
    pc = collections.Counter(pos)
    nc = collections.Counter(neg)
    below = 0
    halves = 0
    for s in allscores:
        p = pc.get(s, 0)
        m = nc.get(s, 0)
        if p:
            halves += p * (2 * below + m)
        below += m
    num = Fraction(halves, 2 * len(pos) * len(neg))
    return frac_round(num)


def ensure_dir(path):
    if not os.path.isdir(path):
        os.makedirs(path)


def write_text(path, text):
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)


def write_json(path, obj):
    write_text(path, json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('data_dir')
    ap.add_argument('out_dir')
    ap.add_argument('--prior', default=None)
    args = ap.parse_args(argv)
    b = Build(os.path.abspath(args.data_dir), os.path.abspath(args.out_dir),
              os.path.abspath(args.prior) if args.prior else None)
    b.run()
    return 0


if __name__ == '__main__':
    sys.exit(main())
