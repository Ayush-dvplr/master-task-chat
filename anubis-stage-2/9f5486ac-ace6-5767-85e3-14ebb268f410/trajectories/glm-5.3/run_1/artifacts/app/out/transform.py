#!/usr/bin/env python3
"""Sentinel card-fraud training-set release builder.

Usage:
    python3 transform.py <DATA_DIR> <OUT_DIR> [--prior <PRIOR_OUT_DIR>]
"""

import argparse
import collections
import csv
import datetime as _dt
import hashlib
import io
import json
import math
import os
import re
import sqlite3
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_EVEN, getcontext

getcontext().prec = 60

import tomli
import yaml
import openpyxl
import pyarrow.parquet as pq
from pdfminer.high_level import extract_text as _pdf_text
from docx import Document as _Docx
from docx.table import Table as _DocxTable
from docx.text.paragraph import Paragraph as _DocxPara
from docx.oxml.ns import qn as _qn

# ---------------------------------------------------------------------------
# generic helpers
# ---------------------------------------------------------------------------

FMT6 = Decimal('0.000001')


def f6(x):
    """Format a number as a 6-decimal string, rounded half to even."""
    return str(Decimal(x).quantize(FMT6, rounding=ROUND_HALF_EVEN))


def half_even_6(x):
    """Round a Decimal to 6 decimals, half to even; returns Decimal."""
    return Decimal(x).quantize(FMT6, rounding=ROUND_HALF_EVEN)


def read_bytes(path):
    with open(path, 'rb') as f:
        return f.read()


def decode_bytes(data):
    if data[:3] == b'\xef\xbb\xbf':
        data = data[3:]
    out = []
    for b in data.replace(b'\r\n', b'\n').replace(b'\r', b'\n').split(b'\n'):
        try:
            out.append(b.decode('utf-8'))
        except UnicodeDecodeError:
            out.append(b.decode('iso-8859-1'))
    return out


def read_lines(path):
    return [l for l in decode_bytes(read_bytes(path)) if l != '']


def parse_ini(path):
    """INI with padded section names; returns {section: {key: value}}."""
    secs = {}
    cur = None
    for line in read_lines(path):
        s = line.strip()
        if not s or s[0] in '#;':
            continue
        m = re.match(r'^\[\s*(.*?)\s*\]$', s)
        if m:
            cur = m.group(1)
            secs.setdefault(cur, {})
            continue
        if cur is None or '=' not in s:
            continue
        k, v = s.split('=', 1)
        secs[cur][k.strip()] = v.strip()
    return secs


def parse_toml(path):
    data = read_bytes(path)
    return tomli.loads(data.decode('utf-8-sig'))


def parse_json(path):
    return json.loads('\n'.join(decode_bytes(read_bytes(path))))


def parse_yaml(path):
    return yaml.safe_load('\n'.join(decode_bytes(read_bytes(path))))


def _split_records(lines):
    """Join physical lines into logical records honouring RFC4180 quoting."""
    out = []
    cur = None
    for ln in lines:
        if cur is None:
            s = ln.lstrip()
            if s.startswith('#CONTROL'):
                out.append(('control', s))
                continue
            if s.startswith('#'):
                out.append(('comment', s))
                continue
            if s == '':
                continue
            cur = ln
        else:
            cur = cur + '\n' + ln
        if cur.count('"') % 2 == 0:
            out.append(('record', cur))
            cur = None
    if cur is not None:
        out.append(('record', cur))
    return out


def parse_delim(path, delim, known_cols=None, field_map=None):
    """Delimited file reader per the source register conventions."""
    known_cols = known_cols or set()
    field_map = field_map or {}
    header = None
    width = 0
    records = []
    controls = []
    for kind, payload in _split_records(read_lines(path)):
        if kind == 'control':
            body = payload[len('#CONTROL|'):]
            controls.append(tuple(p.strip() for p in body.split('|')))
            continue
        if kind == 'comment':
            continue
        cells = next(csv.reader(io.StringIO(payload), delimiter=delim, quotechar='"'))
        if header is None:
            header = [c.strip() for c in cells]
            width = len(header)
            continue
        while len(cells) > width and cells[-1].strip() == '':
            cells.pop()
        cs = [c.strip() for c in cells]
        if len(cs) == width and len(set(cs)) == width and set(cs) <= (set(header) | known_cols):
            header = cs
            continue
        if len(cs) < width:
            cs = cs + [''] * (width - len(cs))
        rec = {}
        for k, v in zip(header, cs):
            rec[field_map.get(k, k)] = v
        records.append(rec)
    return header, records, controls


def parse_jsonl(path):
    """JSON Lines: objects with _meta/_control are not records."""
    recs = []
    controls = []
    for line in read_lines(path):
        s = line.strip()
        if not s:
            continue
        obj = json.loads(s)
        if '_control' in obj:
            controls.append(obj['_control'])
            continue
        if '_meta' in obj:
            continue
        recs.append(obj)
    return recs, controls


def parse_sqlite(path):
    con = sqlite3.connect('file:%s?mode=ro' % os.path.abspath(path), uri=True)
    con.row_factory = sqlite3.Row
    tables = [r[0] for r in con.execute(
        "select name from sqlite_master where type='table' order by name")]
    out = {}
    for t in tables:
        out[t] = [dict(r) for r in con.execute('select * from "%s"' % t)]
    con.close()
    return out


def read_xlsx(path):
    """Returns {sheet: [header, rows-as-dicts]} with raw cell values kept."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    out = {}
    for ws in wb.worksheets:
        rows = []
        for row in ws.iter_rows(values_only=True):
            rows.append(list(row))
        out[ws.title.strip()] = rows
    wb.close()
    return out


def sheet_records(rows, aliases=None):
    """Header + list of dicts from a sheet's raw rows (header restates honoured)."""
    aliases = aliases or set()
    header = None
    width = 0
    out = []
    for r in rows:
        cells = [('' if c is None else c) for c in r]
        while cells and (cells[-1] is None or cells[-1] == ''):
            cells.pop()
        if not cells:
            continue
        if header is None:
            header = cells
            width = len(header)
            continue
        cs = list(cells)
        while len(cs) > width and cs[-1] == '':
            cs.pop()
        if len(cs) == width and all(isinstance(c, str) for c in cs) and \
                len(set(c.strip() for c in cs)) == width and \
                set(c.strip() for c in cs) <= set(header) | aliases:
            header = [c.strip() for c in cs]
            continue
        if len(cs) < width:
            cs = cs + [None] * (width - len(cs))
        out.append(dict(zip(header, cs)))
    return header, out


# ---------------------------------------------------------------------------
# document tables (docx / pdf / html / md)
# ---------------------------------------------------------------------------

def _md_tables(text):
    """Markdown tables -> {caption: (header, rows)}."""
    lines = text.split('\n')
    tables = {}
    cap = None
    buf = []

    def flush():
        nonlocal cap
        if cap is not None and buf:
            hdr = [c.strip() for c in buf[0].strip().strip('|').split('|')]
            rows = []
            for r in buf[2:]:
                cells = [c.strip() for c in r.strip().strip('|').split('|')]
                cells = cells + [''] * (len(hdr) - len(cells))
                rows.append(cells)
            if cap in tables:
                tables[cap] = (tables[cap][0], tables[cap][1] + rows)
            else:
                tables[cap] = (hdr, rows)
        cap = None

    for ln in lines:
        if ln.startswith('**Table:'):
            flush()
            cap = ln[len('**Table:'):].rstrip('*').strip()
            buf = []
            continue
        if ln.startswith('|'):
            buf.append(ln)
    flush()
    return tables


def _md_body_tables(path):
    text = '\n'.join(decode_bytes(read_bytes(path)))
    return _md_tables(text)


def docx_tables(path):
    doc = _Docx(path)
    items = []
    for child in doc.element.body.iterchildren():
        if child.tag == _qn('w:p'):
            items.append(('p', _DocxPara(child, doc).text))
        elif child.tag == _qn('w:tbl'):
            items.append(('t', _DocxTable(child, doc)))
    out = []
    last = ''
    for kind, item in items:
        if kind == 'p':
            t = item.strip()
            if t:
                last = t
        else:
            rows = [[c.text.strip() for c in row.cells] for row in item.rows]
            out.append((last, rows[0], rows[1:]))
    return out


def pdf_tables(path):
    lines = _pdf_text(path).split('\n')
    tables = {}
    cur = None
    pending = False
    footnotes = []
    for raw in lines:
        s = raw.strip()
        m = re.match(r'^Table:\s*(.*?)\s*(\(continued\))?\s*$', s)
        if m:
            cur = m.group(1).strip()
            tables.setdefault(cur, {'header': None, 'rows': []})
            pending = True
            continue
        if s.startswith('Footnote: override'):
            parts = [p.strip() for p in s[len('Footnote: override'):].split(';')]
            if len(parts) == 4:
                footnotes.append(tuple(parts))
            continue
        if s == '' or re.match(r'^Page \d+$', s):
            continue
        if cur is None or '|' not in raw:
            continue
        cells = [c.strip() for c in raw.split('|')]
        if all((re.match(r'^-+$', c) or c == '') for c in cells):
            pending = False
            continue
        t = tables[cur]
        if pending or t['header'] is None:
            if t['header'] is None or cells == t['header'] or pending:
                t['header'] = cells
                pending = False
                continue
        if cells == t['header']:
            continue
        if len(cells) < len(t['header']):
            cells = cells + [''] * (len(t['header']) - len(cells))
        t['rows'].append(cells)
    return tables, footnotes


def html_tables(path):
    raw = '\n'.join(decode_bytes(read_bytes(path)))
    import html as _html
    tables = {}
    footnotes = []

    def strip_tags(s):
        return _html.unescape(re.sub(r'<[^>]+>', '', s)).strip()

    for m in re.finditer(r'<table[^>]*>\s*<caption>(.*?)</caption>(.*?)</table>', raw, re.S):
        cap = strip_tags(m.group(1))
        body = m.group(2)
        thead = re.search(r'<thead>(.*?)</thead>', body, re.S)
        hdr = []
        if thead:
            hdr = [strip_tags(x) for x in re.findall(r'<th[^>]*>(.*?)</th>', thead.group(1), re.S)]
        rows = []
        for tr in re.findall(r'<tr[^>]*>(.*?)</tr>', body, re.S):
            cells = [strip_tags(x) for x in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', tr, re.S)]
            if cells and cells != hdr:
                rows.append(cells)
        tables[cap] = (hdr, rows)
    for m in re.finditer(r'<p[^>]*class="footnote"[^>]*>(.*?)</p>', raw, re.S):
        txt = strip_tags(m.group(1))
        if txt.startswith('Footnote: override'):
            parts = [p.strip() for p in txt[len('Footnote: override'):].split(';')]
            if len(parts) == 4:
                footnotes.append(tuple(parts))
    return tables, footnotes


def apply_footnotes(rows, header, footnotes):
    """rows: list of lists (mutated); footnotes: (caption, key, column, value)."""
    hdr = [h.strip() for h in header]
    for cap, key, col, val in footnotes:
        if col not in hdr:
            continue
        ci = hdr.index(col)
        parts = key.split('/')
        for r in rows:
            if len(parts) == 1:
                if r and r[0].strip() == key:
                    r[ci] = val
            else:
                if len(r) >= 2 and r[0].strip() + '/' + r[1].strip() == key:
                    r[ci] = val


# ---------------------------------------------------------------------------
# time helpers
# ---------------------------------------------------------------------------

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def to_epoch(dt):
    return int((dt - EPOCH).total_seconds())


def parse_instant(s):
    """ISO-8601 instant with Z or offset."""
    s = s.strip()
    if s.endswith('Z'):
        s = s[:-1] + '+00:00'
    return datetime.fromisoformat(s).astimezone(timezone.utc)


def parse_date(s):
    s = s.strip()
    if re.match(r'^\d{4}-\d{2}-\d{2}$', s):
        return datetime.strptime(s, '%Y-%m-%d').date()
    if re.match(r'^\d{2}\.\d{2}\.\d{4}$', s):
        return datetime.strptime(s, '%d.%m.%Y').date()
    return None


def excel_serial(value, system='1900'):
    """Excel serial (float) or datetime cell -> UTC datetime, rounded to seconds."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, _dt.date):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    if value is None or value == '':
        return None
    d = Decimal(str(value))
    if system == '1904':
        base = datetime(1904, 1, 1, tzinfo=timezone.utc)
    else:
        base = datetime(1899, 12, 30, tzinfo=timezone.utc)
    days = int(d)
    frac = d - days
    secs = (frac * 86400).quantize(Decimal('1'), rounding=ROUND_HALF_EVEN)
    return base + timedelta(days=days, seconds=int(secs))


# ---------------------------------------------------------------------------
# zones
# ---------------------------------------------------------------------------

def _last_weekday(year, month, weekday):
    if month == 12:
        d = datetime(year, 12, 31)
    else:
        d = datetime(year, month + 1, 1) - timedelta(days=1)
    while d.weekday() != weekday:
        d -= timedelta(days=1)
    return d


def _nth_weekday(year, month, weekday, n):
    d = datetime(year, month, 1)
    while d.weekday() != weekday:
        d += timedelta(days=1)
    return d + timedelta(days=7 * (n - 1))


def _dst_window(rule, year):
    """Returns (start, end) naive datetimes marking the DST window, or None."""
    if rule == 'none':
        return None
    if rule == 'eu':
        return _last_weekday(year, 3, 6).replace(hour=1), _last_weekday(year, 10, 6).replace(hour=1)
    if rule == 'us':
        return _nth_weekday(year, 3, 6, 2).replace(hour=2), \
            (lambda d: d.replace(hour=2))(_first_weekday(year, 11, 6))
    if rule == 'il':
        return (_last_weekday(year, 3, 6) - timedelta(days=2)).replace(hour=0), \
            _last_weekday(year, 10, 6).replace(hour=0)
    if rule == 'south':
        return _first_weekday(year, 10, 6).replace(hour=2), _first_weekday(year, 4, 6).replace(hour=3)
    if rule == 'nz':
        return _last_weekday(year, 9, 6).replace(hour=2), _first_weekday(year, 4, 6).replace(hour=3)
    if rule == 'cl':
        return _first_weekday(year, 9, 6).replace(hour=4), _first_weekday(year, 4, 6).replace(hour=3)
    raise ValueError('unknown dst rule %r' % rule)


def _first_weekday(year, month, weekday):
    d = datetime(year, month, 1)
    while d.weekday() != weekday:
        d += timedelta(days=1)
    return d


class Zones:
    def __init__(self, rules):
        self.z = {}
        for name, r in rules.items():
            if 'std' not in r and 'std_offset_minutes' in r:
                r = {'std': r['std_offset_minutes'],
                     'rule': r.get('dst_rule', 'none'),
                     'shift': r.get('dst_shift_minutes', 60)}
            self.z[name] = r

    def offsets(self, zone, year):
        r = self.z.get(zone)
        if r is None:
            return None
        std = timedelta(minutes=r['std'])
        shift = timedelta(minutes=r.get('shift', 60))
        return std, std + shift, r['rule']

    def _dst_in_force(self, zone, t):
        r = self.z.get(zone)
        if r is None:
            return False
        rule = r['rule']
        if rule == 'none':
            return False
        std = timedelta(minutes=r['std'])
        shift = timedelta(minutes=r.get('shift', 60))
        for year in (t.year - 1, t.year, t.year + 1):
            w = _dst_window(rule, year)
            if w is None:
                continue
            start, end = w
            if rule in ('eu', 'il', 'cl'):
                s_utc = start.replace(tzinfo=timezone.utc)
                e_utc = end.replace(tzinfo=timezone.utc)
            else:
                s_utc = (start - std).replace(tzinfo=timezone.utc)
                e_utc = (end - (std + shift)).replace(tzinfo=timezone.utc)
            if s_utc <= t < e_utc:
                return True
        return False

    def local_to_utc(self, zone, naive):
        r = self.z.get(zone)
        if r is None:
            return None
        std = timedelta(minutes=r['std'])
        shift = timedelta(minutes=r.get('shift', 60))
        cands = []
        for off in (std, std + shift):
            t = (naive - off).replace(tzinfo=timezone.utc)
            want = (off == std + shift)
            if self._dst_in_force(zone, t) == want:
                cands.append(t)
        if not cands:
            # spring-forward gap: offset in force before the transition
            return (naive - std).replace(tzinfo=timezone.utc)
        return min(cands)


# ---------------------------------------------------------------------------
# source register
# ---------------------------------------------------------------------------

def load_register(path):
    text = '\n'.join(decode_bytes(read_bytes(path)))
    lines = text.split('\n')
    caps = {}
    cur = None
    for ln in lines:
        s = ln.rstrip('\r')
        if s.startswith('**Table:'):
            cur = s[len('**Table:'):].rstrip('**').strip()
            caps[cur] = []
            continue
        if s.startswith('|') and cur is not None:
            caps[cur].append(s)
    out = {}
    for cap, rows in caps.items():
        hdr = [c.strip() for c in rows[0].strip().strip('|').split('|')]
        recs = []
        for r in rows[2:]:
            cells = [c.strip() for c in r.strip().strip('|').split('|')]
            cells = cells + [''] * (len(hdr) - len(cells))
            recs.append(dict(zip(hdr, cells)))
        out[cap] = recs
    catalog = out['Catalog']
    colmap = out['Column map']
    fields = {}
    known = {}
    for r in colmap:
        f = r['file']
        c = r['column']
        fld = r['field']
        conv = r['convention']
        known.setdefault(f, set()).add(c)
        if fld and fld != '-':
            fields.setdefault(f, {})[c] = fld
    for f, mp in list(fields.items()):
        for r in colmap:
            if r['file'] != f:
                continue
            conv = r['convention']
            if conv.startswith('alias of '):
                base = conv[len('alias of '):].strip()
                if base in mp:
                    mp[r['column']] = mp[base]
    return {
        'catalog': catalog,
        'colmap': colmap,
        'fields': fields,
        'known': known,
        'batches': {r['batch_id']: r['file'] for r in out['Batch index']},
    }


# ---------------------------------------------------------------------------
# documents bundle
# ---------------------------------------------------------------------------

class Docs:
    """All published rule tables and reference data."""

    def __init__(self, D):
        self.D = D
        self._docx = {}
        self._pdf = {}
        self._html = {}
        self._md = {}
        self.load_all()

    def path(self, name):
        return os.path.join(self.D, name)

    def load_all(self):
        for name in ['release_build_specification', 'data_governance_charter',
                     'label_policy_v3', 'preprocessing_standard',
                     'split_and_leakage_policy', 'dedup_runbook', 'label_policy_v4']:
            self._docx[name] = docx_tables(self.path(name + '.docx'))
        for name in ['reason_code_catalog', 'currency_and_fx_handbook',
                     'timezone_and_clock_handbook', 'annotation_guidelines',
                     'feature_availability_spec', 'feature_availability_spec_rev2',
                     'baseline_scorer_card']:
            self._pdf[name] = pdf_tables(self.path(name + '.pdf'))
        for name in ['entry_mode_codes', 'errata_bulletins_2026-09',
                     'errata_bulletins_2026-09_consolidated']:
            self._html[name] = html_tables(self.path(name + '.html'))
        for name in ['data_dictionary', 'release_notes_TR-2026.05']:
            self._md[name] = _md_body_tables(self.path(name + '.md'))

    def docx_table(self, name, caption):
        for cap, hdr, rows in self._docx[name]:
            c = cap.strip()
            m = re.match(r'(?i)^table:\s*(.*)$', c)
            if m:
                c = m.group(1).strip()
            if c == caption:
                return hdr, rows
        return None

    def docx_first_table(self, name):
        return self._docx[name][0] if self._docx[name] else None

    def pdf_table(self, name, caption):
        t, f = self._pdf[name]
        if caption not in t:
            return None
        rows = [list(r) for r in t[caption]['rows']]
        return t[caption]['header'], rows

    def pdf_footnotes(self, name):
        return list(self._pdf[name][1])

    def html_table(self, name, caption):
        t, f = self._html[name]
        if caption not in t:
            return None
        return t[caption][0], [list(r) for r in t[caption][1]]

    def md_table(self, name, caption):
        t = self._md[name]
        if caption not in t:
            return None
        return t[caption][0], [list(r) for r in t[caption][1]]

    def md_footnotes(self, name):
        text = '\n'.join(decode_bytes(read_bytes(self.path(name + '.md'))))
        out = []
        for m in re.finditer(r'^Footnote:\s*override\s+(.*)$', text, re.M):
            parts = [p.strip() for p in m.group(1).split(';')]
            if len(parts) == 4:
                out.append(tuple(parts))
        return out


# ---------------------------------------------------------------------------
# calendar (ics)
# ---------------------------------------------------------------------------

def parse_ics_events(path):
    """Returns list of dicts with uid, dtstart (UTC datetime), status, summary."""
    events = []
    cur = None
    for line in read_lines(path):
        if line.startswith('BEGIN:VEVENT'):
            cur = {}
            continue
        if line.startswith('END:VEVENT'):
            if cur is not None:
                events.append(cur)
            cur = None
            continue
        if cur is None:
            continue
        m = re.match(r'^([A-Za-z-]+)(?:;([^:]*))?:(.*)$', line)
        if not m:
            continue
        name = m.group(1).upper()
        params = m.group(2) or ''
        value = m.group(3).strip()
        if name == 'DTSTART':
            tzid = None
            pm = re.search(r'TZID=([^;:]+)', params)
            if pm:
                tzid = pm.group(1)
            cur['tzid'] = tzid
            cur['dtstart_raw'] = value
        else:
            cur[name] = value
    return events


# ---------------------------------------------------------------------------
# mbox
# ---------------------------------------------------------------------------

def parse_mbox(path):
    """Returns list of (date_str, body_text)."""
    import base64
    import quopri
    from email.utils import parsedate_to_datetime
    data = '\n'.join(decode_bytes(read_bytes(path)))
    chunks = re.split(r'(?m)^From ', data)
    out = []
    for chunk in chunks:
        if not chunk.strip():
            continue
        head, _, body = chunk.partition('\n\n')
        headers = {}
        for ln in head.split('\n'):
            if ':' in ln:
                k, v = ln.split(':', 1)
                headers.setdefault(k.strip().lower(), v.strip())
        enc = headers.get('content-transfer-encoding', '').strip().lower()
        if enc == 'base64':
            try:
                body = base64.b64decode(re.sub(r'\s+', '', body)).decode('utf-8', 'replace')
            except Exception:
                body = ''
        elif enc == 'quoted-printable':
            try:
                body = quopri.decodestring(body.encode('utf-8', 'replace')).decode('utf-8', 'replace')
            except Exception:
                body = ''
        out.append((headers.get('date'), body))
    return out


def mbox_date(s):
    from email.utils import parsedate_to_datetime
    if not s:
        return None
    return parsedate_to_datetime(s).astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# the release build
# ---------------------------------------------------------------------------

NBSP = ' '
NNBSP = ' '
_WS = ' \t\n\r\v\f' + NBSP + NNBSP


def canon(value):
    """Trim ASCII whitespace and no-break spaces, then upper-case."""
    s = str(value)
    return s.strip(_WS).upper()


def canon_account(value):
    """Canonicalize an account id; returns None when the pattern fails."""
    s = canon(value)
    if not s.isascii():
        return None
    if re.match(r'^AC-\d{1,6}$', s):
        return 'AC-' + s[3:].zfill(6)
    return None


def canon_legacy(value):
    s = canon(value)
    if not s.isascii():
        return None
    if re.match(r'^L-\d{1,7}$', s):
        return 'L-' + s[2:].zfill(7)
    return None


def canon_merchant(value):
    s = canon(value)
    if not s.isascii():
        return None
    if re.match(r'^MR-\d{1,5}$', s):
        return 'MR-' + s[3:].zfill(5)
    return s  # descriptor: caller resolves it


def canon_device(value):
    s = canon(value)
    if not s or s == 'UNKNOWN' or s == 'NULL':
        return None
    if not s.isascii():
        return None
    if re.match(r'^DV-[0-9A-F]{8}$', s):
        return s
    return None


NO_IP = {'', '-', 'UNKNOWN', '0.0.0.0', 'NULL', 'N/A'}


def canon_ip(value):
    s = canon(value)
    if s in NO_IP:
        return None
    if not s.isascii():
        return None
    if re.match(r'^IP-[0-9A-F]{7}$', s):
        return s
    return None


def canon_currency(value):
    s = canon(value)
    if not s.isascii():
        return None
    if re.match(r'^[A-Z]{3}$', s):
        return s
    return None


SYSTEMS = {
    'settlement_nbp_2026-05.csv': 'SET', 'settlement_nbp_2026-06.csv': 'SET',
    'settlement_nbp_2026-07.csv': 'SET', 'settlement_nbp_2026-08.csv': 'SET',
    'settlement_nbp_lookback_2026-04.csv': 'SET',
    'settlement_nbp_2026-08_final.csv': 'SET',
    'gateway_auth_2026-05.tsv': 'GW', 'gateway_auth_2026-06.tsv': 'GW',
    'gateway_auth_2026-07.tsv': 'GW', 'gateway_auth_2026-08.tsv': 'GW',
    'gateway_auth_2026-07_replay.tsv': 'GW',
    'sdk_events_2026-05_2026-06.jsonl': 'SDK', 'sdk_events_2026-07_2026-08.jsonl': 'SDK',
    'sdk_events_2026-07_2026-08_dedup.jsonl': 'SDK',
    'core_legacy_batch_2026-05_2026-06.txt': 'LEG',
    'core_legacy_batch_2026-07_2026-08.txt': 'LEG',
    'core_legacy_batch_2026-07_2026-08_reextract.txt': 'LEG',
    'partner_api_orders_eu_2026-05_2026-06.xml': 'PAR',
    'partner_api_orders_eu_2026-07_2026-08.xml': 'PAR',
    'partner_api_orders_eu_2026-07_2026-08_resend.xml': 'PAR',
    'terminal_batches_2026-05_2026-06.parquet': 'TRM',
    'terminal_batches_2026-07_2026-08.parquet': 'TRM',
}
SYSTEM_PRECEDENCE = {'SET': 0, 'TRM': 1, 'LEG': 2, 'PAR': 3, 'GW': 4, 'SDK': 5}


class Build:
    def __init__(self, data_dir, out_dir, prior_dir=None):
        self.D = data_dir
        self.out = out_dir
        self.prior = prior_dir
        self.p = os.path.join

    # -- path helpers ------------------------------------------------------
    def path(self, name):
        return os.path.join(self.D, name)

    # -- load reference data ----------------------------------------------
    def load_config(self):
        cfg = parse_toml(self.path('release_config.toml'))
        self.config = cfg['release']
        self.pinned = cfg.get('pinned', [])

    def load_reference_tables(self):
        D = self.docs
        # status codes
        hdr, rows = D.md_table('data_dictionary', 'Status codes')
        apply_footnotes(rows, hdr, D.md_footnotes('data_dictionary'))
        self.status_meaning = {}
        for r in rows:
            self.status_meaning[(r[0].strip().upper(), r[1].strip().upper())] = r[2].strip()
        # entry modes
        hdr, rows = D.html_table('entry_mode_codes', 'Entry mode codes')
        fns = D._html['entry_mode_codes'][1]
        apply_footnotes(rows, hdr, fns)
        self.entry_mode = {}
        for r in rows:
            self.entry_mode[(r[0].strip().upper(), r[1].strip().upper())] = r[2].strip()
        # region / segment groups
        hdr, rows = D.md_table('data_dictionary', 'Region groups')
        apply_footnotes(rows, hdr, D.md_footnotes('data_dictionary'))
        self.region_group = {r[0].strip().upper(): r[1].strip() for r in rows}
        hdr, rows = D.md_table('data_dictionary', 'Segment groups')
        apply_footnotes(rows, hdr, D.md_footnotes('data_dictionary'))
        self.segment_group = {r[0].strip().upper(): r[1].strip() for r in rows}
        # reason codes
        hdr, rows = D.pdf_table('reason_code_catalog', 'Reason codes')
        fns = D.pdf_footnotes('reason_code_catalog')
        apply_footnotes(rows, hdr, fns)
        self.reason_class = {}
        for r in rows:
            self.reason_class[(r[0].strip().upper(), r[1].strip().upper())] = r[2].strip()
        # orbis renumbering
        hdr, rows = D.docx_table('label_policy_v4', 'Orbis reason code renumbering')
        self.orbis_renumber = {}
        for r in rows:
            if r[0].strip() and r[1].strip():
                self.orbis_renumber[r[0].strip().upper()] = r[1].strip().upper()
        # merchant dispute profiles
        hdr, rows = D.docx_table('label_policy_v3', 'Merchant dispute-handling profiles')
        fns = None
        self.merchant_profile = {}
        for r in rows:
            if r[0].strip():
                self.merchant_profile[r[0].strip().upper()] = r[1].strip()
        # mcc risk groups
        hdr, rows = D.docx_table('preprocessing_standard', 'MCC sub-code risk groups')
        self.mcc_risk = {}
        for r in rows:
            if r[0].strip():
                self.mcc_risk[r[0].strip().upper()] = r[1].strip()
        # gold checks
        hdr, rows = D.pdf_table('annotation_guidelines', 'Gold check results')
        fns = D.pdf_footnotes('annotation_guidelines')
        apply_footnotes(rows, hdr, fns)
        self.gold_fail = set()
        for r in rows:
            if r[2].strip().lower() == 'fail':
                self.gold_fail.add((r[0].strip().upper(), r[1].strip().upper()))
        # retracted examples
        hdr, rows = D.md_table('release_notes_TR-2026.05', 'Retracted examples')
        self.retracted = set()
        for r in rows:
            self.retracted.add(r[0].strip().upper())
        # split tender exceptions
        hdr, rows = D.docx_table('release_build_specification', 'Split-tender exceptions')
        self.split_tender = set()
        for r in rows:
            f = r[0].strip().upper()
            ref = r[1].strip().upper()
            if f.endswith('.CSV'):
                f = f[:-4] + '.csv'
            self.split_tender.add((f, ref))
        # replay batches
        hdr, rows = D.docx_table('dedup_runbook', 'Replay batch register')
        self.replay_of = {}
        for r in rows:
            bid = r[0].strip().upper()
            kind = r[1].strip().lower()
            replays = r[2].strip().upper()
            if kind == 'replay' and replays:
                self.replay_of[bid] = replays
        # shared device exemptions
        hdr, rows = D.docx_table('split_and_leakage_policy', 'Shared-device exemptions')
        self.exempt_devices = set()
        for r in rows:
            if r[0].strip():
                self.exempt_devices.add(r[0].strip().upper())
        # merchant offsets + coefficients
        hdr, rows = D.pdf_table('baseline_scorer_card', 'Merchant offsets')
        fns = D.pdf_footnotes('baseline_scorer_card')
        apply_footnotes(rows, hdr, fns)
        self.merchant_offset = {}
        for r in rows:
            if r[0].strip():
                self.merchant_offset[r[0].strip().upper()] = Decimal(
                    r[1].strip().replace(',', '.'))
        hdr, rows = D.pdf_table('baseline_scorer_card', 'Coefficients')
        self.coefficients = {}
        for r in rows:
            self.coefficients[r[0].strip()] = Decimal(r[1].strip().replace(',', '.'))
        # minor units + fixing calendar
        hdr, rows = D.pdf_table('currency_and_fx_handbook', 'Minor units')
        fns = D.pdf_footnotes('currency_and_fx_handbook')
        apply_footnotes(rows, hdr, fns)
        self.exponent = {r[0].strip().upper(): int(r[1]) for r in rows}
        hdr, rows = D.pdf_table('currency_and_fx_handbook', 'Fixing calendar')
        apply_footnotes(rows, hdr, fns)
        self.fixing = {}
        for r in rows:
            cur = r[0].strip().upper()
            date = r[1].strip()
            status = r[2].strip().lower()
            subst = r[3].strip()
            self.fixing[(cur, date)] = (status, subst)
        self.treasury_currencies = {c for (c, d) in self.fixing}
        # zone aliases
        hdr, rows = D.pdf_table('timezone_and_clock_handbook', 'Zone aliases')
        fns = D.pdf_footnotes('timezone_and_clock_handbook')
        apply_footnotes(rows, hdr, fns)
        self.zone_alias = {canon(r[0]): canon(r[1]) for r in rows}
        # ip partition schedule (revision 1 governs the published_at table)
        hdr, rows = D.pdf_table('feature_availability_spec',
                               'IP reputation partition schedule')
        self.ip_published = {}
        for r in rows:
            self.ip_published[r[0].strip().upper()] = parse_instant(r[1].strip())
        self.ip_rev2_from = parse_instant('2026-08-15T00:00:00Z')

    # -- entities -----------------------------------------------------------
    def load_entities(self):
        D = self.D
        # accounts: base snapshot and revision are authoritative for attributes
        base = parse_yaml(self.path('account_registry_2026-04.yaml'))
        rev = parse_yaml(self.path('account_registry_2026-07.yaml'))
        nxt = parse_yaml(self.path('account_registry_2026-09.yaml'))
        self.account_rows = collections.defaultdict(list)
        for snap, src in ((datetime(2026, 4, 1, tzinfo=timezone.utc), base),
                          (datetime(2026, 7, 1, tzinfo=timezone.utc), rev)):
            for a in src['accounts']:
                aid = canon_account(a['id'])
                if aid is None:
                    aid = canon(a['id'])
                eff = a.get('effective_from')
                eff_dt = parse_instant(eff + 'T00:00:00Z') if eff else None
                self.account_rows[aid].append((eff_dt, snap, a))
        # a canonical account list (base snapshot or revision)
        self.listed_accounts = set(self.account_rows)
        # legacy crosswalk
        self.legacy_of = {}
        for a in nxt['accounts']:
            lid = a.get('legacy_id')
            if lid:
                l = canon_legacy(lid)
                aid = canon_account(a['id'])
                if l and aid:
                    self.legacy_of[l] = aid
        # account merge chains
        self.account_merge = {}
        for line in read_lines(self.path('account_merge_events_2026-09.log')):
            m = re.match(r'^(\S+)\s+MERGE\s+account=(\S+)\s+into=(\S+)', line.strip())
            if m:
                src_a = canon_account(m.group(2)) or canon(m.group(2))
                dst_a = canon_account(m.group(3)) or canon(m.group(3))
                if src_a and dst_a:
                    self.account_merge[src_a] = dst_a
        mmap = parse_json(self.path('account_merge_map_2026-09.json'))
        for row in mmap['map']:
            src_a = canon_account(row['account']) or canon(row['account'])
            dst_a = canon_account(row['canonical']) or canon(row['canonical'])
            if src_a and dst_a and src_a != dst_a and src_a not in self.account_merge:
                self.account_merge[src_a] = dst_a
        # merchants
        m1 = pq.read_table(self.path('merchant_master.parquet')).to_pylist()
        m2 = pq.read_table(self.path('merchant_master_2026-09.parquet')).to_pylist()
        self.merchant_attrs = {}
        self.merchant_merge = {}
        for x in m1:
            mid = canon_merchant(x['merchant_id'])
            if mid:
                self.merchant_attrs[mid] = x
        for x in m1 + m2:
            mid = canon_merchant(x['merchant_id'])
            tgt = x.get('merged_into')
            if mid and tgt:
                t = canon_merchant(tgt)
                if t and t != mid:
                    self.merchant_merge[mid] = t
        self.listed_merchants = set(self.merchant_attrs)
        # merchant aliases (effective dated)
        self.aliases = collections.defaultdict(list)
        hdr, rows, _ = parse_delim(self.path('merchant_aliases_v2.csv'), ',')
        for r in rows:
            a = canon(r['alias'])
            m = canon_merchant(r['merchant_id'])
            vf = r['valid_from'].strip()
            vt = r['valid_to'].strip()
            if not a or not m:
                continue
            vf_d = parse_date(vf) if vf and vf != '0000-00-00' else None
            vt_d = parse_date(vt) if vt and vt != '0000-00-00' else None
            self.aliases[a].append((vf_d, vt_d, m))
        # merchant classification history
        hist = parse_json(self.path('merchant_mcc_reassignments_2026-09.json'))
        self.mcc_history = collections.defaultdict(list)
        for h in hist['history']:
            mid = canon_merchant(h['merchant_id'])
            if mid:
                self.mcc_history[mid].append(
                    (parse_instant(h['effective_from']), h['mcc_subcode'].strip().upper()))
        # merchant zones
        mtz = parse_ini(self.path('merchant_settlement_tz.ini'))
        self.merchant_zone = {}
        for sec, kv in mtz.items():
            mid = canon_merchant(sec)
            z = kv.get('zone', '')
            if mid and z:
                self.merchant_zone[mid] = self.zone_alias.get(canon(z), canon(z))
        # bin ranges
        hdr, rows, _ = parse_delim(self.path('bin_ranges_issuer.csv'), ',')
        self.bin_ranges = []
        for r in rows:
            self.bin_ranges.append((r['bin_prefix'].strip(), r['issuer_group'].strip()))
        # device registry
        dreg = parse_yaml(self.path('device_registry.yaml'))
        self.device_kind = {}
        for x in dreg['devices']:
            did = canon_device(x['device_id'])
            if did:
                self.device_kind[did] = (x.get('kind') or '').strip().upper()
        # device fingerprints
        fp = pq.read_table(self.path('device_fingerprints_2026-09_reexport.parquet')).to_pylist()
        self.device_first_seen = {}
        for x in fp:
            did = canon_device(x['device_id'])
            aid = canon_account(x['account_id'])
            if not did or not aid:
                continue
            ts = x['first_seen']
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            self.device_first_seen[(aid, did)] = ts.astimezone(timezone.utc)
        # device link events
        self.device_links = []
        for line in read_lines(self.path('device_link_events_2026-09.log')):
            m = re.match(r'^(\S+)\s+device-graph\s+(\w+)\s+account=(\S+)\s+device=(\S+)', line.strip())
            if m:
                self.device_links.append((parse_instant(m.group(1)), m.group(2).upper(),
                                          canon_account(m.group(3)), canon_device(m.group(4))))
        # device link revocations
        hdr, rows, _ = parse_delim(self.path('device_link_revocations_2026-09.csv'), ',')
        self.device_revocations = []
        for r in rows:
            self.device_revocations.append((canon_account(r['account_id']),
                                            canon_device(r['device_id']),
                                            r['action'].strip().upper(),
                                            parse_instant(r['at'])))
        # kyc
        wb = read_xlsx(self.path('account_kyc_reviews_2026-09.xlsx'))
        hdr, revs = sheet_records(wb['Reviews'])
        hdr, apps = sheet_records(wb['Appeals'])
        self.kyc_reviews = []
        for r in revs:
            aid = canon_account(r['account_id'])
            t = excel_serial(r['effective_at'], '1900')
            tier = r['tier']
            if aid and t and tier not in (None, ''):
                self.kyc_reviews.append((aid, t, int(tier), str(r['review_id'])))
        self.kyc_overturned = set()
        for r in apps:
            if str(r['outcome']).strip().lower() == 'overturned':
                self.kyc_overturned.add(str(r['review_id']).strip().upper())
        # kyc default
        fdef = parse_toml(self.path('feature_definitions.toml'))
        self.kyc_default = {}
        for row in fdef['kyc_default']:
            self.kyc_default[(row['segment'].strip().upper(),
                              row['region'].strip().upper())] = int(row['tier'])
        # consent
        hdr, rows, _ = parse_delim(self.path('consent_withdrawals_portal_2026-09.csv'), ',')
        self.consent_events = collections.defaultdict(list)
        for r in rows:
            aid = canon_account(r['account_id'])
            if aid:
                self.consent_events[aid].append(
                    (parse_instant(r['at']), r['action'].strip().upper(),
                     r['scope'].strip().upper()))
        legal = parse_json(self.path('erasure_orders_legal_2026-09.json'))
        self.erasure = set()
        for o in legal['orders']:
            aid = canon_account(o['account_id'])
            if aid and o.get('type', '').strip().lower() == 'erasure' and \
                    o.get('status', '').strip().lower() == 'executed':
                self.erasure.add(aid)
        sup = parse_ini(self.path('opt_out_registry_support.ini'))
        self.support_withdrawn = set()
        for sec, kv in sup.items():
            aid = canon_account(sec)
            if aid and kv.get('status', '').strip().lower() == 'withdrawn':
                self.support_withdrawn.add(aid)
        # terminal skew
        skew = parse_ini(self.path('terminal_clock_skew.ini'))
        self.terminal_skew = {}
        for sec, kv in skew.items():
            v = kv.get('skew_seconds', '').strip()
            if v:
                self.terminal_skew[sec.strip().upper()] = int(v.replace('+', ''))
        # timezone rules
        zrules = parse_toml(self.path('timezone_rules.toml'))
        self.zones = Zones({canon(z['name']): {'std': z['std_offset_minutes'],
                                               'rule': z.get('dst_rule', 'none'),
                                               'shift': z.get('dst_shift_minutes', 60)}
                            for z in zrules.get('zone', [])})
        self.postal_zone = {canon(z['prefix']): canon(z['zone'])
                            for z in zrules.get('postal_zone', [])}
        # region crosswalk
        hdr, rows, _ = parse_delim(self.path('region_crosswalk_postal.csv'), ',')
        self.postal_region = {}
        for r in rows:
            self.postal_region[r['postal'].strip().upper()] = r['region'].strip().upper()

    # -- feature sources ----------------------------------------------------
    def load_feature_sources(self):
        D = self.D
        # publication calendar
        ev = parse_ics_events(self.path('snapshot_publication_calendar_2026-09.ics'))
        self.calendar = {}
        for e in ev:
            uid = e.get('UID', '').strip().upper()
            raw = e.get('dtstart_raw', '')
            ts = None
            if raw.endswith('Z'):
                ts = datetime.strptime(raw, '%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)
            else:
                naive = datetime.strptime(raw, '%Y%m%dT%H%M%S')
                zone = e.get('tzid') or 'UTC'
                ts = self.zones.local_to_utc(zone, naive)
            self.calendar[uid] = (ts, (e.get('STATUS') or '').strip().upper())
        # snapshot registry
        reg = parse_json(self.path('feature_snapshot_registry_2026-09.json'))
        self.snapshot_status = {}
        for s in reg['snapshots']:
            self.snapshot_status[s['snapshot_id'].strip().upper()] = \
                s['status'].strip().lower()
        # feature store manifest: quarantine
        man = parse_json(self.path('feature_store_export_manifest_2026-09.json'))
        self.quarantined = set()
        for p in man['partitions']:
            if p.get('quarantined'):
                self.quarantined.add(p['partition'].strip().upper())
        # merchant risk snapshots + corrections + void evidence
        self.merchant_risk_rows = collections.defaultdict(list)
        self.merchant_risk_corr = collections.defaultdict(list)
        for month, fn in (('2026-05', 'merchant_risk_snapshots_2026-05.xlsx'),
                          ('2026-06', 'merchant_risk_snapshots_2026-06.xlsx'),
                          ('2026-07', 'merchant_risk_snapshots_2026-07.xlsx'),
                          ('2026-08', 'merchant_risk_snapshots_2026-08.xlsx')):
            wb = read_xlsx(self.path(fn))
            hdr, rows = sheet_records(wb['Snapshot'])
            for r in rows:
                mid = canon_merchant(r['merchant_id'])
                if not mid:
                    continue
                sid = str(r['snapshot_id']).strip().upper()
                as_of = r['as_of']
                if isinstance(as_of, _dt.date):
                    as_of_d = as_of
                elif re.match(r'^\d{4}-\d{2}-\d{2}$', str(as_of).strip()):
                    as_of_d = parse_date(str(as_of).strip())
                else:
                    as_of_d = (excel_serial(as_of, '1900')).date()
                self.merchant_risk_rows[mid].append((sid, as_of_d, r['cb_rate_bps']))
            hdr, rows = sheet_records(wb['Corrections'])
            for i, r in enumerate(rows):
                mid = canon_merchant(r['merchant_id'])
                if not mid:
                    continue
                sid = str(r['snapshot_id']).strip().upper()
                at = excel_serial(r['corrected_at'], '1900')
                self.merchant_risk_corr[(sid, mid)].append(
                    (at, i, r['corrected_bps']))
        # void evidence from the v2 snapshot file (only its void flags are usable)
        wb = read_xlsx(self.path('merchant_risk_snapshots_2026-08_v2.xlsx'))
        hdr, rows = sheet_records(wb['Snapshot'])
        self.void_snapshots = set()
        for r in rows:
            mid = canon_merchant(r['merchant_id'])
            sid = str(r['snapshot_id']).strip().upper()
            if mid and str(r.get('status', '')).strip().lower() == 'void':
                self.void_snapshots.add((sid, mid))
        # ip reputation feeds
        self.ip_obs = collections.defaultdict(list)
        for fn in ['ip_reputation_feed_2026-05_2026-06.jsonl',
                   'ip_reputation_feed_2026-07_2026-08.jsonl']:
            recs, _ = parse_jsonl(self.path(fn))
            for i, o in enumerate(recs):
                ip = canon_ip(o.get('ip', ''))
                if not ip:
                    continue
                oid = str(o.get('obs_id', '')).strip().upper()
                ts = o.get('observed_at')
                if isinstance(ts, (int, float)):
                    t = datetime.fromtimestamp(int(ts), tz=timezone.utc)
                else:
                    s = str(ts).strip()
                    if re.match(r'^\d{9,}$', s):
                        t = datetime.fromtimestamp(int(s), tz=timezone.utc)
                    else:
                        t = parse_instant(s)
                scale = str(o.get('score_scale', '')).strip().lower()
                score = o.get('score')
                if score is None or str(score).strip() == '':
                    continue
                if scale == 'x10':
                    sc = Decimal(str(score).replace(',', '.')) / Decimal(10)
                else:
                    sc = Decimal(str(score).replace(',', '.'))
                self.ip_obs[ip].append((oid, t, str(o.get('partition', '')).strip().upper(), sc))
        # ip corrections
        hdr, rows, _ = parse_delim(self.path('ip_reputation_corrections_2026-09.tsv'), '\t')
        self.ip_corr = collections.defaultdict(list)
        for i, r in enumerate(rows):
            oid = r['obs_id'].strip().upper()
            act = r['action'].strip().lower()
            at = parse_instant(r['reviewed_at']) if r['reviewed_at'].strip() else None
            ns = r['new_score'].strip()
            self.ip_corr[oid].append((at, i, act, ns))
        # lag overrides
        hdr, rows, _ = parse_delim(self.path('feature_lag_overrides_2026-09.csv'), ',')
        self.lag_override = {}
        for r in rows:
            v = r['lag_minutes'].strip()
            if not v:
                continue
            key = (r['source'].strip().lower(),
                   r['date'].strip(),
                   int(r['hour'].strip()))
            self.lag_override[key] = int(v.replace(',', '').replace('.', ''))
        # incident log
        self.incidents = collections.defaultdict(list)
        for line in read_lines(self.path('pipeline_incident_log_2026-09.log')):
            m = re.match(r'^(\S+)\s+(\S+)\s+(\S+)\s*(.*)$', line.strip())
            if not m:
                continue
            ts, inc, kind, rest = m.groups()
            fields = {}
            for kv in rest.split():
                if '=' in kv:
                    k, v = kv.split('=', 1)
                    fields[k.strip().lower()] = v.strip()
            self.incidents[inc.strip()].append(
                (parse_instant(ts), kind.strip().upper(),
                 fields.get('system', ''), fields))
        self.incident_system = {}
        for inc, evs in self.incidents.items():
            for e in evs:
                if e[2]:
                    self.incident_system[inc] = e[2]
                    break
        self.outages = {}
        for inc, evs in self.incidents.items():
            wins = [e for e in evs if e[1] == 'WINDOW_REVISED']
            if not wins:
                continue
            last = wins[-1]
            self.outages[inc] = (last[3].get('start'), last[3].get('end'))
        # fx rates
        ttab = ET.parse(self.path('fx_reference_rates_treasury_2026-09.xml')).getroot()
        self.treasury = {}
        for fx in ttab:
            if fx.tag != 'Fixing':
                continue
            date = fx.get('date').strip()
            cur = fx.get('currency').strip().upper()
            unit = Decimal(fx.get('unit').strip().replace(',', '.'))
            rate = Decimal(fx.get('rate').strip().replace(',', '.'))
            self.treasury[(cur, date)] = rate / unit
        vrates = pq.read_table(self.path('fx_rates_daily_2026-09.parquet')).to_pylist()
        self.vendor_rate = {}
        for r in vrates:
            self.vendor_rate[(r['currency'].strip().upper(),
                              r['rate_date'].isoformat())] = Decimal(str(r['usd_per_unit']))
        hdr, rows, _ = parse_delim(self.path('fx_corrections_2026-09_final.csv'), ',')
        self.fx_correction = {}
        for r in rows:
            cur = r['currency'].strip().upper()
            date = r['rate_date'].strip()
            verdict = r['verdict'].strip().lower()
            val = r['corrected_usd_per_unit'].strip()
            if verdict == 'corrected' and val:
                self.fx_correction[(cur, date)] = Decimal(val.replace(',', '.'))

    # -- authority ----------------------------------------------------------
    def load_authority(self):
        hdr, rows = self.docs.docx_table('data_governance_charter',
                                         'Source authority windows')
        self.charter = collections.defaultdict(list)
        for r in rows:
            f = r[0].strip()
            grp = r[1].strip().lower()
            vf = r[2].strip()
            vt = r[3].strip()
            auth = r[4].strip().lower()
            inc = r[5].strip()
            self.charter[(f, grp)].append((vf, vt, auth, inc))

    def has_authority(self, fname, group, when):
        rows = self.charter.get((fname, group))
        if not rows:
            return False
        for vf, vt, auth, inc in rows:
            if auth != 'primary':
                continue
            if re.match(r'^INC-\d{4}-\d+$', inc):
                w = self.outages.get(inc)
                if not w:
                    continue
                start = parse_instant(w[0])
                end = parse_instant(w[1])
            else:
                start = parse_instant(vf + 'T00:00:00Z')
                end = parse_instant(vt + 'T00:00:00Z')
            if start <= when < end:
                return True
        return False

    # -- errata -------------------------------------------------------------
    def load_errata(self):
        hdr, rows = self.docs.html_table('errata_bulletins_2026-09',
                                         'Errata register')
        fns = self.docs._html['errata_bulletins_2026-09'][1]
        apply_footnotes(rows, hdr, fns)
        withdrawn = set()
        hdr2, rows2 = self.docs.html_table('errata_bulletins_2026-09_consolidated',
                                           'Withdrawn errata')
        if rows2:
            for r in rows2:
                withdrawn.add(r[0].strip().upper())
        best = {}
        for r in rows:
            eid = r[0].strip().upper()
            if eid in withdrawn:
                continue
            fname = r[1].strip()
            ref = r[2].strip().upper()
            field = r[3].strip().lower()
            issued = parse_instant(r[5].strip())
            if field == 'remark':
                continue
            key = (fname, ref, field)
            if key not in best or issued >= best[key][0]:
                best[key] = (issued, r[4].strip())
        self.errata = collections.defaultdict(dict)
        self.voided_refs = set()
        for (fname, ref, field), (issued, value) in best.items():
            if field == 'void':
                self.voided_refs.add((fname, ref))
            else:
                self.errata[(fname, ref)][field] = value

    # -- identifier resolution ---------------------------------------------
    def resolve_account(self, raw):
        """Returns the canonical account or None."""
        if raw is None:
            return None
        key = raw
        if key in self._acct_cache:
            return self._acct_cache[key]
        s = canon(raw)
        res = None
        if s.isascii():
            if re.match(r'^AC-\d{1,6}$', s):
                cur = 'AC-' + s[3:].zfill(6)
            else:
                cur = None
            if cur is not None:
                seen = set()
                while True:
                    if cur in self.listed_accounts:
                        res = cur
                        break
                    nxt = self.account_merge.get(cur)
                    if nxt is None or cur in seen:
                        break
                    seen.add(cur)
                    cur = nxt
        if res is None and s.isascii() and re.match(r'^L-\d{1,7}$', s):
            l = 'L-' + s[2:].zfill(7)
            a = self.legacy_of.get(l)
            if a:
                cur = a
                seen = set()
                while True:
                    if cur in self.listed_accounts:
                        res = cur
                        break
                    nxt = self.account_merge.get(cur)
                    if nxt is None or cur in seen:
                        break
                    seen.add(cur)
                    cur = nxt
        self._acct_cache[key] = res
        return res

    def resolve_merchant(self, raw, at=None):
        """Returns the canonical merchant id (resolved through merges) or None."""
        if raw is None:
            return None
        key = (raw, at.date().isoformat() if at is not None else '')
        if key in self._merch_cache:
            return self._merch_cache[key]
        s = canon(raw)
        res = None
        mid = None
        if s.isascii() and re.match(r'^MR-\d{1,5}$', s):
            mid = 'MR-' + s[3:].zfill(5)
        else:
            # descriptor alias
            best = None
            for vf, vt, m in self.aliases.get(s, ()):  # type: ignore[union-attr]
                if vf is not None and at is not None:
                    d = at.date()
                    if d < vf:
                        continue
                    if vt is not None and d >= vt:
                        continue
                elif vf is not None and at is None:
                    continue
                if best is None or (vf is not None and best[0] is not None and vf > best[0]):
                    best = (vf, m)
            if best:
                mid = best[1]
            elif s.isascii() and re.match(r'^MR-\d{1,5}$', s):
                mid = 'MR-' + s[3:].zfill(5)
        if mid:
            cur = mid
            seen = set()
            while True:
                if cur in self.listed_merchants:
                    res = cur
                    break
                nxt = self.merchant_merge.get(cur)
                if nxt is None or cur in seen:
                    break
                seen.add(cur)
                cur = nxt
        self._merch_cache[key] = res
        return res

    def account_zone(self, acct, at):
        """Zone of the account's postal prefix at the given instant."""
        key = (acct, at)
        if key in self._zone_cache:
            return self._zone_cache[key]
        attrs = self.account_attrs(acct, at)
        z = None
        if attrs is not None:
            postal = str(attrs.get('postal', '')).strip()
            if len(postal) >= 4:
                z = self.postal_zone.get(postal[:4].upper())
        self._zone_cache[key] = z
        return z

    def account_attrs(self, acct, at):
        """Account attributes effective at the given instant (None if none)."""
        key = (acct, at)
        if key in self._attr_cache:
            return self._attr_cache[key]
        rows = self.account_rows.get(acct)
        res = None
        best_key = None
        for eff, snap, a in rows or ():
            if eff is not None and at < eff:
                continue
            k = (eff is not None, eff or datetime(1, 1, 1, tzinfo=timezone.utc), snap)
            if best_key is None or k > best_key:
                best_key = k
                res = a
        self._attr_cache[key] = res
        return res

    # -- amount parsing -----------------------------------------------------
    def parse_major(self, text, currency):
        """'.' decimal, ',' grouping allowed."""
        s = str(text).strip()
        if not s:
            return None
        s = s.replace(',', '')
        try:
            d = Decimal(s)
        except Exception:
            return None
        e = self.exponent.get(currency, 2)
        return int((d * (Decimal(10) ** e)).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))

    def parse_major_eu(self, text, currency):
        """',' decimal, '.', space or U+202F grouping."""
        s = str(text).strip().replace('.', '').replace(' ', '').replace(NNBSP, '')
        s = s.replace(',', '.')
        if not s:
            return None
        try:
            d = Decimal(s)
        except Exception:
            return None
        e = self.exponent.get(currency, 2)
        return int((d * (Decimal(10) ** e)).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))

    def parse_minor(self, text):
        s = str(text).strip().replace(',', '').replace('.', '')
        if not re.match(r'^[+-]?\d+$', s):
            return None
        return int(s)

    # -- event file readers -------------------------------------------------
    def read_event_file(self, fname):
        """Returns a list of raw record dicts for one event export."""
        system = SYSTEMS[fname]
        reg = self.register
        recs = []
        if fname.endswith('.csv') or fname.endswith('.tsv'):
            delim = ',' if fname.endswith('.csv') else '\t'
            hdr, rows, controls = parse_delim(self.path(fname), delim,
                                              reg['known'].get(fname, set()),
                                              reg['fields'].get(fname, {}))
            for r in rows:
                ref = (r.get('record_ref') or '').strip().upper()
                if not ref:
                    continue
                rec = {'file': fname, 'system': system, 'record_ref': ref,
                       'batch': (r.get('batch') or '').strip().upper(),
                       'acct_raw': r.get('account', ''),
                       'merch_raw': r.get('merchant', ''),
                       'currency': (r.get('currency') or '').strip().upper(),
                       'status': (r.get('status') or '').strip().upper(),
                       'auth_code': (r.get('auth_code') or '').strip().upper(),
                       'bin': (r.get('bin') or '').strip(),
                       'entry': (r.get('entry_code') or '').strip().upper(),
                       'ip_raw': r.get('ip', ''),
                       'device_raw': '',
                       'terminal': '',
                       'arn': (r.get('arn') or '').strip(),
                       'amount_unit': 'minor' if system == 'SET' else 'major',
                       'amount_raw': r.get('amount', ''),
                       'event_time_raw': r.get('event_time', ''),
                       'local_time': None}
                recs.append(rec)
            return recs, controls
        if fname.endswith('.jsonl'):
            objs, controls = parse_jsonl(self.path(fname))
            for o in objs:
                ref = str(o.get('event_id', '')).strip().upper()
                if not ref:
                    continue
                has_minor = o.get('amount_minor') not in (None, '')
                has_major = o.get('amount') not in (None, '')
                unit = 'minor' if has_minor else ('major' if has_major else 'minor')
                raw = o['amount_minor'] if has_minor else (o.get('amount') or '')
                ts = o.get('ts')
                ts_ms = o.get('ts_ms')
                rec = {'file': fname, 'system': system, 'record_ref': ref,
                       'batch': str(o.get('batch', '')).strip().upper(),
                       'acct_raw': o.get('account', ''),
                       'merch_raw': o.get('merchant', ''),
                       'currency': str(o.get('currency', '')).strip().upper(),
                       'status': str(o.get('status', '')).strip().upper(),
                       'auth_code': str(o.get('auth_code', '')).strip().upper(),
                       'bin': str(o.get('bin', '') or '').strip(),
                       'entry': str(o.get('entry', '')).strip().upper(),
                       'ip_raw': o.get('ip_ref', ''),
                       'device_raw': o.get('device_id', ''),
                       'terminal': '',
                       'arn': '',
                       'amount_unit': unit,
                       'amount_raw': raw,
                       'event_time_raw': ts if ts not in (None, '') else ts_ms,
                       'local_time': None}
                recs.append(rec)
            return recs, controls
        if fname.endswith('.parquet'):
            rows = pq.read_table(self.path(fname)).to_pylist()
            for r in rows:
                ref = str(r['trm_event_id']).strip().upper()
                rec = {'file': fname, 'system': system, 'record_ref': ref,
                       'batch': str(r['batch_id']).strip().upper(),
                       'acct_raw': r['account_id'],
                       'merch_raw': r['merchant_id'],
                       'currency': str(r['currency']).strip().upper(),
                       'status': str(r['status_code']).strip().upper(),
                       'auth_code': str(r['auth_code']).strip().upper(),
                       'bin': str(r['card_bin'] or '').strip(),
                       'entry': str(r['entry_mode_raw'] or '').strip().upper(),
                       'ip_raw': '',
                       'device_raw': '',
                       'terminal': str(r['terminal_id'] or '').strip().upper(),
                       'arn': '',
                       'amount_unit': 'minor',
                       'amount_raw': r['amount_minor'],
                       'event_time_raw': r['recorded_at'],
                       'local_time': None}
                recs.append(rec)
            return recs, []
        if fname.endswith('.xml'):
            root = ET.parse(self.path(fname)).getroot()
            controls = []
            for el in root:
                if el.tag == 'Control':
                    controls.append((el.get('partition'), el.get('rows'), el.get('hash')))
                elif el.tag == 'Order':
                    ref = (el.get('ref') or '').strip().upper()
                    d = {}
                    amount = None
                    unit = 'major'
                    cur = ''
                    for ch in el:
                        if ch.tag == 'Amount':
                            amount = (ch.text or '').strip()
                            unit = (ch.get('unit') or 'major').strip().lower()
                            cur = (ch.get('currency') or '').strip().upper()
                        else:
                            d[ch.tag] = (ch.text or '').strip()
                    rec = {'file': fname, 'system': system, 'record_ref': ref,
                           'batch': (el.get('batch') or '').strip().upper(),
                           'acct_raw': d.get('Customer', ''),
                           'merch_raw': d.get('Merchant', ''),
                           'currency': cur,
                           'status': (d.get('Status') or '').strip().upper(),
                           'auth_code': (d.get('AuthCode') or '').strip().upper(),
                           'bin': (d.get('Bin') or '').strip(),
                           'entry': (d.get('Entry') or '').strip().upper(),
                           'ip_raw': d.get('Ip', ''),
                           'device_raw': '',
                           'terminal': '',
                           'arn': '',
                           'amount_unit': unit,
                           'amount_raw': amount,
                           'event_time_raw': None,
                           'local_time': _parse_local(d.get('PlacedAt', ''))}
                    recs.append(rec)
            return recs, controls
        if fname.endswith('.txt'):
            controls = []
            for line in read_lines(self.path(fname)):
                s = line.rstrip()
                if not s:
                    continue
                if s[0] == 'T':
                    controls.append((s[1:14], s[14:23], s[23:38]))
                    continue
                if s[0] != 'D':
                    continue
                rec = {'file': fname, 'system': system,
                       'record_ref': s[1:13].strip().upper(),
                       'batch': s[80:90].strip().upper(),
                       'acct_raw': s[13:22].strip(),
                       'merch_raw': s[22:30].strip(),
                       'currency': s[57:60].strip().upper(),
                       'status': s[60:64].strip().upper(),
                       'auth_code': s[64:70].strip().upper(),
                       'bin': s[70:76].strip(),
                       'entry': s[76:80].strip().upper(),
                       'ip_raw': '', 'device_raw': '', 'terminal': '', 'arn': '',
                       'amount_unit': 'minor',
                       'amount_raw': s[44:57].strip(),
                       'event_time_raw': None,
                       'local_time': _parse_compact(s[30:44].strip())}
                recs.append(rec)
            return recs, controls
        raise ValueError('unknown event file ' + fname)

    def delivered_amount(self, rec):
        cur = rec['currency']
        if rec['amount_unit'] == 'minor':
            return self.parse_minor(rec['amount_raw'])
        if rec['amount_unit'] == 'major':
            return self.parse_major(rec['amount_raw'], cur)
        if rec['amount_unit'] == 'major_eu':
            return self.parse_major_eu(rec['amount_raw'], cur)
        return None

    def delivered_time(self, rec):
        """Normalized event time as delivered (before errata)."""
        raw = rec['event_time_raw']
        if rec['system'] == 'TRM':
            t = raw
            if t.tzinfo is None:
                t = t.replace(tzinfo=timezone.utc)
            skew = self.terminal_skew.get(rec['terminal'], 0)
            return t.astimezone(timezone.utc) + timedelta(seconds=skew)
        if rec['system'] == 'LEG':
            acct = self.resolve_account(rec['acct_raw'])
            zone = self.account_zone(acct, rec['local_time'].replace(tzinfo=timezone.utc)) \
                if acct else None
            if zone is None:
                zone = 'UTC'
            return self.zones.local_to_utc(zone, rec['local_time'])
        if rec['system'] == 'PAR':
            mid = self.resolve_merchant(rec['merch_raw'], rec['local_time'])
            zone = self.merchant_zone.get(mid) if mid else None
            if zone is None:
                zone = 'UTC'
            return self.zones.local_to_utc(zone, rec['local_time'])
        if rec['system'] in ('SET',):
            s = str(raw).strip()
            return parse_instant(s)
        if rec['system'] == 'GW':
            return datetime.fromtimestamp(int(str(raw)) / 1000, tz=timezone.utc)
        if rec['system'] == 'SDK':
            if isinstance(raw, (int, float)):
                return datetime.fromtimestamp(int(raw) / 1000, tz=timezone.utc)
            s = str(raw).strip()
            if re.match(r'^\d{10,}$', s):
                return datetime.fromtimestamp(int(s) / (1000 if len(s) > 10 else 1),
                                              tz=timezone.utc)
            return parse_instant(s)
        return None


def _parse_local(s):
    s = s.strip()
    if not s:
        return None
    return datetime.strptime(s, '%Y-%m-%dT%H:%M:%S')


def _parse_compact(s):
    if not re.match(r'^\d{14}$', s):
        return None
    return datetime.strptime(s, '%Y%m%d%H%M%S')
