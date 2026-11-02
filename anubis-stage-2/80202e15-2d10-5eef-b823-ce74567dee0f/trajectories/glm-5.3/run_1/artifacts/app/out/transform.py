#!/usr/bin/env python3
"""Corvid Cloud Platform monthly SLA service-credit close.

Reads the collector exports of one calendar month, grades every subscription
that is active in the month and not excluded, and writes the close outputs.

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
import os
import re
import sqlite3
import sys
import zipfile
from decimal import Decimal, ROUND_HALF_EVEN

import xml.etree.ElementTree as ET

# --------------------------------------------------------------------------
# character sets and small helpers

IGNORABLE = '\u00a0\u200b\u202f\u2009\u2006\ufeff \t\r\n\v\f'
ID_RE = re.compile(r'([A-Za-z]+)[-_]?([0-9]+)')
ID_WIDTH = {'SUB': 6, 'ACC': 5, 'INS': 7}


def read_text(path):
    with open(path, 'rb') as fh:
        return fh.read().decode('utf-8', 'surrogateescape')


def fix_str(s):
    if not isinstance(s, str):
        return s
    try:
        s.encode('utf-8')
        return s
    except UnicodeEncodeError:
        return s.encode('utf-8', 'surrogateescape').decode('latin-1')


def clean(s):
    if s is None:
        return None
    s = fix_str(s)
    return ''.join(ch for ch in str(s) if ch not in IGNORABLE)


def canon_id(v):
    """Return (canonical, malformed).  canonical is None when empty/invalid."""
    if v is None:
        return None, False
    if not isinstance(v, str):
        return None, True
    s = ''.join(ch for ch in v if ch not in IGNORABLE)
    if s == '':
        return None, False
    if any(ord(ch) > 127 for ch in s):
        return None, True
    m = ID_RE.fullmatch(s)
    if not m:
        return None, True
    pref = m.group(1).upper()
    digits = m.group(2)
    width = ID_WIDTH.get(pref)
    if width:
        digits = digits.zfill(width)
    return '%s-%s' % (pref, digits), False


def snake(k):
    if not isinstance(k, str):
        return k
    return re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', k).lower()


def norm_obj(o):
    if isinstance(o, dict):
        return {snake(k): norm_obj(v) for k, v in o.items()
                if not (isinstance(k, str) and k.startswith('_'))}
    if isinstance(o, list):
        return [norm_obj(x) for x in o]
    return o


def fix_dict(o):
    if isinstance(o, dict):
        return {k: fix_str(v) if isinstance(v, str) else fix_dict(v) for k, v in o.items()}
    if isinstance(o, list):
        return [fix_dict(x) for x in o]
    return o


def r_half_even(x):
    return int(Decimal(repr(float(x))).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


GROUP_CHARS = re.compile(r"[\s\u00a0\u202f\u2009']")


def parse_count(v):
    """Counts; -1 / N/A / missing -> None (placeholder)."""
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        if isinstance(v, float) and v != int(v):
            return r_half_even(v)
        n = int(v)
        return None if n == -1 else n
    s = clean(v)
    if s is None or s == '':
        return None
    low = s.lower()
    if low in ('n/a', 'na', '-1', 'list', 'none'):
        return None
    s2 = GROUP_CHARS.sub('', low)
    if s2.endswith('k'):
        return int(float(s2[:-1]) * 1000)
    if ',' in s2 and '.' not in s2:
        s2 = s2.replace(',', '.')
    return r_half_even(float(s2))


def parse_amount(v, exponent=2):
    """Money: minor units, or '<major> <CCY>' converted with half-even."""
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        if float(v) == int(v):
            return int(v)
        return r_half_even(float(v) * (10 ** exponent))
    s = clean(v)
    if s is None or s == '':
        return None
    low = s.lower()
    if low in ('n/a', 'na', '-1', 'none', 'list'):
        return None
    m = re.fullmatch(r'(-?[\d\u00a0\u202f\u2009 ]+(?:[.,]\d+)?)\s*([A-Za-z]{3})', s)
    if m:
        num = GROUP_CHARS.sub('', m.group(1))
        if ',' in num and '.' not in num:
            num = num.replace(',', '.')
        exp = exponent
        cur = m.group(2).upper()
        return r_half_even(float(num) * (10 ** exp))
    s2 = GROUP_CHARS.sub('', low)
    if s2.endswith('k'):
        return int(float(s2[:-1]) * 1000)
    if ',' in s2 and '.' not in s2:
        s2 = s2.replace(',', '.')
    return r_half_even(float(s2))


def parse_decimal(v):
    """Percentages and other small decimals; placeholders -> None."""
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return Decimal(str(v))
    s = clean(v)
    if s is None or s == '':
        return None
    low = s.lower()
    if low in ('n/a', 'na', '-1', 'none', 'list'):
        return None
    s2 = GROUP_CHARS.sub('', s)
    if ',' in s2 and '.' not in s2:
        s2 = s2.replace(',', '.')
    try:
        return Decimal(s2)
    except Exception:
        return None


def parse_date(v):
    """Calendar date -> YYYYMMDD int; 9999-12-31 / empty -> None (open-ended)."""
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        f = float(v)
        if f >= 10 ** 11:
            f = f / 1000.0
        if f >= 2958466:
            return None
        if f < 0:
            return None
        base = _dt.date(1899, 12, 30)
        try:
            d = base + _dt.timedelta(days=int(f))
        except OverflowError:
            return None
        return d.year * 10000 + d.month * 100 + d.day
    if isinstance(v, _dt.datetime):
        return v.year * 10000 + v.month * 100 + v.day
    if isinstance(v, _dt.date):
        return v.year * 10000 + v.month * 100 + v.day
    s = clean(v)
    if s is None or s == '':
        return None
    if s in ('9999-12-31', '99991231', '31.12.9999'):
        return None
    m = re.fullmatch(r'(\d{4})-(\d{2})-(\d{2})', s)
    if m:
        return int(m.group(1) + m.group(2) + m.group(3))
    m = re.fullmatch(r'(\d{2})\.(\d{2})\.(\d{4})', s)
    if m:
        return int(m.group(3) + m.group(2) + m.group(1))
    m = re.fullmatch(r'(\d{4})(\d{2})(\d{2})', s)
    if m:
        return int(s)
    return None


def parse_instant(v):
    """Instant -> epoch seconds (float).  None when missing/unparsable."""
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        f = float(v)
        if abs(f) >= 10 ** 12:
            f = f / 1000.0
        return f
    if isinstance(v, _dt.datetime):
        d = v
        if d.tzinfo is None:
            d = d.replace(tzinfo=_dt.timezone.utc)
        return d.timestamp()
    s = fix_str(v) if isinstance(v, str) else v
    if s is None:
        return None
    if not isinstance(s, str):
        return None
    s = s.strip()
    if s == '':
        return None
    m = re.fullmatch(r'-?\d+(\.\d+)?', s)
    if m:
        f = float(s)
        if abs(f) >= 10 ** 12:
            f = f / 1000.0
        return f
    m = re.fullmatch(r'(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})(Z)?', s)
    if m:
        y, mo, d, hh, mm, ss = (int(m.group(i)) for i in range(1, 7))
        return _dt.datetime(y, mo, d, hh, mm, ss, tzinfo=_dt.timezone.utc).timestamp()
    m = re.fullmatch(
        r'(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?'
        r'(Z|[+-]\d{2}:?\d{2})?', s)
    if m:
        y, mo, d, hh, mm, ss = (int(m.group(i)) for i in range(1, 7))
        frac = float('0.' + m.group(7)) if m.group(7) else 0.0
        off = 0
        if m.group(8) and m.group(8) != 'Z':
            t = m.group(8).replace(':', '')
            sign = -1 if t[0] == '-' else 1
            off = sign * (int(t[1:3]) * 3600 + int(t[3:5]) * 60)
        dt = _dt.datetime(y, mo, d, hh, mm, ss, tzinfo=_dt.timezone.utc)
        return dt.timestamp() + frac - off
    m = re.fullmatch(r'(\d{4})-(\d{2})-(\d{2})', s)
    if m:
        return _dt.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                            tzinfo=_dt.timezone.utc).timestamp()
    # RFC 2822 message dates
    m = re.fullmatch(r'[A-Za-z]{3},\s+(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})\s+'
                     r'(\d{2}):(\d{2}):(\d{2})(?:\s+([+-]\d{4}))?', s)
    if m:
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        mon = months.index(m.group(2)) + 1
        off = 0
        if m.group(7):
            t = m.group(7)
            sign = -1 if t[0] == '-' else 1
            off = sign * (int(t[1:3]) * 3600 + int(t[3:5]) * 60)
        return _dt.datetime(int(m.group(3)), mon, int(m.group(1)),
                            int(m.group(4)), int(m.group(5)), int(m.group(6)),
                            tzinfo=_dt.timezone.utc).timestamp() - off
    if re.fullmatch(r'-?\d+\.\d*', s) or re.fullmatch(r'\.\d+', s):
        return float(s)
    # spreadsheet serial with a fraction
    if re.fullmatch(r'\d+(\.\d+)?', s.replace(',', '.')):
        f = float(s.replace(',', '.'))
        if f >= 10 ** 12:
            f = f / 1000.0
        else:
            d0 = _dt.date(1899, 12, 30)
            day = int(f)
            frac = f - day
            d = d0 + _dt.timedelta(days=day)
            return _dt.datetime(d.year, d.month, d.day, tzinfo=_dt.timezone.utc).timestamp() \
                + frac * 86400.0
    raise ValueError('unparsable instant %r' % (v,))


def instant_to_utc(ts):
    return _dt.datetime.fromtimestamp(ts, _dt.timezone.utc)


def fmt_instant(ts):
    return instant_to_utc(ts).strftime('%Y-%m-%dT%H:%M:%SZ')


def days_in_month(y, m):
    n = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]
    if m == 2 and (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)):
        n = 29
    return n


def ymd(y, m, d):
    return y * 10000 + m * 100 + d


# --------------------------------------------------------------------------
# zone handling (register's own rules; no tz database needed)

class Zone(object):
    def __init__(self, std_offset_min, dst_rule, tzid=None):
        self.std = std_offset_min * 60
        self.dst_rule = dst_rule
        self.tzid = tzid

    def _dst_bounds(self, year):
        """(start_utc, end_utc) of the DST period for EU zones."""
        def last_sunday(month):
            if month == 3:
                last = _dt.date(year, 3, 31)
            else:
                last = _dt.date(year, 10, 31)
            for i in range(7):
                d = last - _dt.timedelta(days=i)
                if d.weekday() == 6:
                    return d
            return last
        s = last_sunday(3)
        e = last_sunday(10)
        start = _dt.datetime(s.year, s.month, s.day, 1, 0, 0,
                             tzinfo=_dt.timezone.utc).timestamp()
        end = _dt.datetime(e.year, e.month, e.day, 1, 0, 0,
                           tzinfo=_dt.timezone.utc).timestamp()
        return start, end

    def offset_at(self, ts):
        if self.dst_rule != 'EU':
            return self.std
        start, end = self._dst_bounds(instant_to_utc(ts).year)
        if start <= ts < end:
            return self.std + 3600
        return self.std

    def local_to_utc(self, naive):
        """naive datetime (no tzinfo) -> epoch seconds using this zone."""
        base = _dt.datetime(naive.year, naive.month, naive.day, naive.hour,
                            naive.minute, naive.second,
                            tzinfo=_dt.timezone.utc).timestamp()
        candidates = []
        for off in (self.std, self.std + 3600):
            ts = base - off
            if self.offset_at(ts) == off:
                candidates.append(ts)
        if candidates:
            return min(candidates)
        # skipped hour: offset in force before the change
        return base - self.std

    def utc_to_local(self, ts):
        off = self.offset_at(ts)
        return instant_to_utc(ts + off)

    def local_date(self, ts):
        return self.utc_to_local(ts).date()


def parse_naive_dt(v):
    """'YYYY-MM-DDTHH:MM:SS' / epoch / serial -> naive datetime."""
    if v is None:
        return None
    if isinstance(v, _dt.datetime):
        return v if v.tzinfo is None else v.replace(tzinfo=None)
    if isinstance(v, (int, float)):
        f = float(v)
        if f >= 10 ** 12:
            f = f / 1000.0
        day = int(f)
        frac = f - day
        d = _dt.date(1899, 12, 30) + _dt.timedelta(days=day)
        base = _dt.datetime(d.year, d.month, d.day)
        return base + _dt.timedelta(seconds=round(frac * 86400.0))
    s = clean(v)
    if not s:
        return None
    m = re.fullmatch(r'(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?', s)
    if m:
        frac = float('0.' + m.group(7)) if m.group(7) else 0.0
        return _dt.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                            int(m.group(4)), int(m.group(5)), int(m.group(6))) + \
            _dt.timedelta(seconds=frac)
    m = re.fullmatch(r'(\d{4})-(\d{2})-(\d{2})', s)
    if m:
        return _dt.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    raise ValueError('unparsable local time %r' % (v,))


# --------------------------------------------------------------------------
# file readers

def read_delimited(path, delim=','):
    text = read_text(path).replace('\r\n', '\n')
    if text[:1] == '\ufeff':
        text = text[1:]
    reader = csv.reader(io.StringIO(text, newline=''), delimiter=delim, quotechar='"')
    rows = []
    header = None
    header_set = None
    for raw in reader:
        vals = [fix_str(x) if isinstance(x, str) else x for x in raw]
        if not vals or all((x is None or str(x).strip() == '') for x in vals):
            continue
        first = str(vals[0]).lstrip()
        if first.startswith('#'):
            continue
        cand = [str(c).strip() for c in vals]
        if header is None:
            header = cand
            header_set = set(c.lower() for c in cand if c != '')
            continue
        rowset = set(c.lower() for c in cand if c != '')
        if rowset == header_set and len(cand) == len(header):
            header = cand
            continue
        rec = {}
        for i, h in enumerate(header):
            rec[h] = vals[i] if i < len(vals) else None
        rows.append(rec)
    return rows


def read_jsonl(path):
    out = []
    for line in read_text(path).split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        o = json.loads(line)
        if not isinstance(o, dict) or '_meta' in o:
            continue
        out.append(norm_obj(fix_dict(o)))
    return out


def read_json(path):
    return norm_obj(fix_dict(json.loads(read_text(path))))


def read_xml(path):
    root = ET.fromstring(read_text(path))
    out = []
    for el in list(root):
        rec = {}
        for k, v in el.attrib.items():
            rec[snake(k)] = fix_str(v)
        for child in el:
            rec[snake(child.tag)] = fix_str(child.text)
        out.append(rec)
    return out


def read_yaml_lists(path):
    import yaml
    d = yaml.safe_load(read_text(path))
    out = []
    if isinstance(d, dict):
        for k, v in d.items():
            if isinstance(v, list):
                for item in v:
                    out.append(norm_obj(fix_dict(item)) if isinstance(item, dict) else item)
    elif isinstance(d, list):
        for item in d:
            out.append(norm_obj(fix_dict(item)) if isinstance(item, dict) else item)
    return out


def read_toml_tables(path):
    import tomllib
    with open(path, 'rb') as fh:
        d = tomllib.load(fh)
    out = []
    for k, v in d.items():
        if isinstance(v, list):
            for item in v:
                out.append(norm_obj(fix_dict(item)) if isinstance(item, dict) else item)
    return out


def read_ini(path):
    text = read_text(path)
    if text[:1] == '\ufeff':
        text = text[1:]
    out = []
    cur = None
    for line in text.split('\n'):
        line = line.strip()
        if not line or line[0] in ';#':
            continue
        if line.startswith('[') and line.endswith(']'):
            if cur is not None:
                out.append(cur)
            cur = (line[1:-1], {})
            continue
        if cur is None or '=' not in line:
            continue
        k, v = line.split('=', 1)
        cur[1][k.strip()] = v.strip().strip('"')
    if cur is not None:
        out.append(cur)
    return out


def read_sqlite(path):
    con = sqlite3.connect('file:%s?mode=ro' % path, uri=True)
    try:
        names = [r[0] for r in con.execute(
            "select name from sqlite_master where type='table' order by rowid")]
        names = [n for n in names if not n.startswith('sqlite_')]
        out = []
        for n in names:
            cur = con.execute('select * from "%s" order by rowid' % n)
            cols = [d[0] for d in cur.description]
            for row in cur:
                rec = {}
                for c, v in zip(cols, row):
                    rec[c] = fix_str(v) if isinstance(v, str) else v
                rec['_caption'] = n
                out.append(rec)
        return out
    finally:
        con.close()


def read_parquet(path):
    import pyarrow.parquet as pq
    t = pq.read_table(path)
    cols = t.column_names
    out = []
    for rec in t.to_pylist():
        out.append({snake(c): (fix_str(rec[c]) if isinstance(rec[c], str) else rec[c])
                    for c in cols})
    return out


def read_xlsx_rows(path):
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    out = []
    try:
        for sh in wb.sheetnames:
            ws = wb[sh]
            header = None
            for row in ws.iter_rows(values_only=True):
                vals = [fix_str(v) if isinstance(v, str) else v for v in row]
                while vals and vals[-1] is None:
                    vals.pop()
                if not vals:
                    continue
                if header is None:
                    header = [str(c).strip() if c is not None else '' for c in vals]
                    continue
                rec = {}
                for i, h in enumerate(header):
                    if h:
                        rec[h] = vals[i] if i < len(vals) else None
                rec['_caption'] = sh
                out.append(rec)
    finally:
        wb.close()
    return out


def read_docx_tables(path):
    W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read('word/document.xml'))
    body = root.find(W + 'body')
    tables = []
    pending = None
    for el in body:
        tag = el.tag.split('}')[1]
        if tag == 'p':
            txt = ''.join(t.text or '' for t in el.iter(W + 't'))
            if txt.startswith('Table:'):
                pending = txt[len('Table:'):].strip()
        elif tag == 'tbl':
            rows = []
            for tr in el.findall(W + 'tr'):
                cells = []
                for tc in tr.findall(W + 'tc'):
                    cells.append(''.join(t.text or '' for t in tc.iter(W + 't')))
                rows.append([fix_str(c).strip() for c in cells])
            tables.append((pending, rows))
            pending = None
    return tables


def read_log_events(path):
    """`<ts> LEVEL <logger> key=value ...` lines -> dicts (meta under '_')."""
    out = []
    for line in read_text(path).split('\n'):
        s = line.strip()
        if not s or s.startswith('#'):
            continue
        fields = []
        i = 0
        n = len(s)
        while i < n:
            m = re.compile(r'\s([A-Za-z_][A-Za-z0-9_]*)=').search(s, i)
            if not m:
                break
            key = m.group(1)
            j = m.end()
            if j < n and s[j] == '"':
                k = s.find('"', j + 1)
                if k < 0:
                    k = len(s)
                val = s[j + 1:k]
                i = k + 1
            else:
                k = s.find(' ', j)
                if k < 0:
                    k = len(s)
                val = s[j:k]
                i = k
            fields.append((key, fix_str(val)))
        rec = {}
        for k, v in fields:
            rec[k] = v
        m = re.match(r'(\S+)', s)
        if m:
            try:
                rec['_ts'] = parse_instant(m.group(1))
            except Exception:
                rec['_ts'] = None
        out.append(rec)
    return out


def _pdf_pages_text(path):
    import pypdf
    reader = pypdf.PdfReader(path)
    return [(p.extract_text() or '') for p in reader.pages]


def read_pdf_tables(path):
    out = []
    pending = None
    header = None
    for text in _pdf_pages_text(path):
        lines = [l.strip() for l in text.split('\n')]
        i = 0
        while i < len(lines):
            s = lines[i]
            if not s:
                i += 1
                continue
            if s.startswith('Table:'):
                pending = s[len('Table:'):].strip()
                header = None
                i += 1
                continue
            if re.fullmatch(r'Page \d+', s):
                i += 1
                continue
            if '|' not in s:
                i += 1
                continue
            cells = [c.strip() for c in s.split('|')]
            cells = [c for c in cells if c != '']
            if len(cells) < 2:
                i += 1
                continue
            if header is None:
                header = cells
                i += 1
                continue
            if cells == header:
                i += 1
                continue
            if len(cells) == len(header):
                out.append((pending, header, [fix_str(c) for c in cells]))
            i += 1
        header = None
    return out


def read_html_tables(path):
    text = read_text(path)
    out = []
    for m in re.finditer(r'<table>(.*?)</table>', text, re.S):
        blob = m.group(1)
        cap = re.search(r'<caption>(.*?)</caption>', blob, re.S)
        caption = cap.group(1).strip() if cap else None
        body = re.search(r'<tbody>(.*?)</tbody>', blob, re.S)
        if not body:
            continue
        head = re.findall(r'<th>(.*?)</th>', blob, re.S)
        rows = []
        for tr in re.finditer(r'<tr>(.*?)</tr>', body.group(1), re.S):
            cells = [re.sub(r'<[^>]+>', '', c).strip()
                     for c in re.findall(r'<td[^>]*>(.*?)</td>', tr.group(1), re.S)]
            cells = [fix_str(c) for c in cells]
            if cells:
                rows.append(cells)
        out.append((caption, [h.strip() for h in head], rows))
    return out


def split_md_row(s):
    """Split a markdown table row honouring escaped pipes."""
    parts = []
    cur = []
    i = 0
    while i < len(s):
        if s[i] == '\\' and i + 1 < len(s) and s[i + 1] == '|':
            cur.append('|')
            i += 2
            continue
        if s[i] == '|':
            parts.append(''.join(cur))
            cur = []
            i += 1
            continue
        cur.append(s[i])
        i += 1
    parts.append(''.join(cur))
    return [fix_str(c.strip()) for c in parts]


def read_md_tables(path):
    out = []
    pending = None
    header = None
    for line in read_text(path).split('\n'):
        s = line.strip()
        if not s:
            continue
        if s.startswith('**Table:') and s.endswith('**'):
            pending = s[len('**Table:'):-2].strip()
            header = None
            continue
        if not s.startswith('|'):
            continue
        cells = split_md_row(s.strip('|'))
        if cells and all(re.fullmatch(r':?-+:?', c) for c in cells if c):
            continue
        if header is None:
            header = cells
            continue
        if len(cells) == len(header):
            out.append((pending, header, cells))
    return out


def read_mbox(path):
    text = read_text(path)
    msgs = []
    starts = [m.start() for m in re.finditer(r'(?m)^From .*(?:\n|$)', text)]
    if not starts:
        starts = [0]
    for idx, st in enumerate(starts):
        end = starts[idx + 1] if idx + 1 < len(starts) else len(text)
        blob = text[st:end]
        if blob.startswith('From ') and '\n\n' in blob:
            head, body = blob.split('\n\n', 1)
        elif '\n\n' in blob:
            head, body = blob.split('\n\n', 1)
        else:
            head, body = blob, ''
        headers = {}
        last = None
        for line in head.split('\n'):
            if line.startswith('From '):
                continue
            if not line.strip():
                continue
            if line[0] in ' \t' and last:
                headers[last] += ' ' + line.strip()
                continue
            if ':' in line:
                k, v = line.split(':', 1)
                last = k.strip()
                headers[last] = fix_str(v.strip())
        msgs.append((headers, fix_str(body)))
    return msgs


def read_ics(path):
    lines = []
    for raw in read_text(path).split('\n'):
        raw = raw.rstrip('\r')
        if raw[:1] in (' ', '\t') and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    out = []
    cur = None
    for line in lines:
        s = line.strip()
        if s == 'BEGIN:VEVENT':
            cur = {}
            continue
        if s == 'END:VEVENT':
            if cur is not None:
                out.append(cur)
            cur = None
            continue
        if cur is None or ':' not in s:
            continue
        name, val = s.split(':', 1)
        params = {}
        if ';' in name:
            parts = name.split(';')
            name = parts[0]
            for p in parts[1:]:
                if '=' in p:
                    k, v = p.split('=', 1)
                    params[k] = v
        cur[name] = fix_str(val)
        if params:
            cur.setdefault('_params', {})[name] = params
    return out



# --------------------------------------------------------------------------
# source register and catalog

class Catalog(object):
    def __init__(self, path, data_dir):
        self.path = path
        self.data_dir = data_dir
        self.tables = {}          # caption -> [row lists]
        self.order = []
        self.params = {}
        self.regions = {}
        self.currencies = {}
        self.catalog = []
        self.legacy_orders = {}
        self._load()

    def _load(self):
        pending = None
        header = None
        for line in read_text(self.path).split('\n'):
            s = line.strip()
            if not s:
                continue
            if s.startswith('**Table:') and s.endswith('**'):
                pending = s[len('**Table:'):-2].strip()
                header = None
                self.order.append(pending)
                continue
            if not s.startswith('|'):
                continue
            cells = split_md_row(s.strip('|'))
            if cells and all(re.fullmatch(r':?-+:?', c) for c in cells if c):
                continue
            if header is None:
                header = cells
                continue
            if len(cells) == len(header):
                self.tables.setdefault(pending, []).append(cells)
        for row in self.tables.get('Close parameters', []):
            if len(row) >= 2:
                self.params[row[0]] = row[1]
        for row in self.tables.get('Regions', []):
            if len(row) >= 6 and row[0] != 'region':
                self.regions[row[0]] = {
                    'city': row[1], 'region_group': row[2], 'tzid': row[3],
                    'std_offset_min': int(row[4]), 'dst_rule': row[5]}
        for row in self.tables.get('Currencies', []):
            if len(row) >= 2 and row[0] != 'currency':
                self.currencies[row[0]] = int(row[1])
        for row in self.tables.get('Source catalog', []):
            if len(row) >= 5 and row[0] != 'file':
                self.catalog.append({'file': row[0], 'format': row[1], 'role': row[2],
                                     'control_field': row[3]})
        for row in self.tables.get('Legacy order references', []):
            if len(row) >= 2 and row[0] != 'order_ref':
                self.legacy_orders[row[0]] = row[1]

    def entry(self, name):
        for e in self.catalog:
            if e['file'] == name:
                return e
        return None

    def path_of(self, name):
        return os.path.join(self.data_dir, name)


# identifier fields per file (fields that must hold well formed identifiers)
ID_FIELDS = {
    'account_aliases.tsv': {'alias_id', 'account_id'},
    'account_caps.xlsx': {'cap_id', 'account_ref'},
    'account_snapshot_legacy.sqlite': {'account_id', 'ban'},
    'accounts_master.csv': {'account_id'},
    'audit_control_register.pdf': {'control_id'},
    'cdn_attestations.xlsx': {'record_id', 'subscription', 'batch_id'},
    'cdn_logs_akamoto.xml': {'record_id', 'subscription', 'batch_id'},
    'cdn_logs_fastedge.xml': {'record_id', 'subscription', 'batch_id'},
    'change_calendar.ics': {'UID'},
    'claims_backoffice.xlsx': {'receipt_id', 'decision_id', 'subscription_id', 'ban'},
    'claims_crm_legacy.csv': {'case_id', 'subscription_id'},
    'claims_portal.csv': {'claim_id', 'subscription_id'},
    'claims_workflow.log': {'event_id', 'ref'},
    'client_sdk_dedup.jsonl': {'record_id', 'install_id', 'subscription'},
    'collector_schema_proposed.yaml': {'event_id'},
    'contracts_register.xlsx': {'contract_id', 'account_id', 'amendment_id'},
    'credit_ledger.sqlite': {'posting_id', 'grant_id', 'account_ref'},
    'credit_operations_manual.docx': {'account_id'},
    'credit_preferences.json': {'account_id'},
    'credit_tiers_2026.xlsx': {'target_id', 'revocation_id', 'schedule_id'},
    'dependency_links.tsv': {'link_id', 'downstream', 'upstream'},
    'deploy_events.log': {'event_id', 'wave'},
    'deploy_manifests.xml': {'member_id', 'wave'},
    'edge_legacy_a.txt': {'record_id', 'subscription', 'batch_id'},
    'edge_legacy_b.txt': {'record_id', 'subscription', 'batch_id'},
    'edge_legacy_c.txt': {'record_id', 'subscription', 'batch_id'},
    'enterprise_sla_schedules.pdf': {'schedule_id', 'subscription_id'},
    'fee_overrides.xlsx': {'override_id', 'subscription_id'},
    'fx_hourly_treasury.csv': {'fixing_id'},
    'fx_rates_unofficial.json': {'fixing_id', 'recall_id'},
    'governance_charter.docx': {'decision_id', 'from_account', 'to_account'},
    'host_clock_edge_a.ini': set(),
    'host_clock_edge_b.ini': set(),
    'host_clock_edge_c.ini': set(),
    'host_inventory.csv': set(),
    'incident_attribution_policy.docx': {'link_id', 'downstream', 'upstream'},
    # the Service dependencies table carries product codes, not identifiers
    'incident_attribution_policy.docx|Service dependencies': set(),
    'incident_register.xml': {'incident_id', 'update_id', 'ref'},
    'incident_register_preliminary.xml': {'prelim_id', 'final_id', 'retraction_id', 'noc_id'},
    'ingest_batches.jsonl': {'batch_id'},
    'ingest_reprocess.log': {'event_id', 'batch'},
    'lb_errors_central.csv': {'record_id', 'subscription', 'batch_id'},
    'lb_errors_east.csv': {'record_id', 'subscription', 'batch_id'},
    'lb_errors_east_replay.csv': {'record_id', 'subscription', 'batch_id'},
    'lb_errors_north.csv': {'record_id', 'subscription', 'batch_id'},
    'lb_errors_south.csv': {'record_id', 'subscription', 'batch_id'},
    'lb_errors_west.csv': {'record_id', 'subscription', 'batch_id'},
    'lb_sampling.parquet': {'sampling_id'},
    'lifecycle_events.log': {'event_id', 'subscription'},
    'maintenance_changes.xlsx': {'change_id', 'approval_id'},
    'maintenance_notices.mbox': set(),
    'noc_outage_declarations.pdf': {'noc_id', 'prelim_ref'},
    'plan_changes_central.tsv': {'change_id', 'subscription_id', 'reverts'},
    'plan_changes_east.json': {'change_id', 'subscription_id', 'reverts'},
    'plan_changes_north.xml': {'change_id', 'subscription_id', 'reverts'},
    'plan_changes_south.yaml': {'change_id', 'subscription_id', 'reverts'},
    'plan_changes_west.log': {'change_id', 'subscription_id', 'reverts'},
    'price_book.toml': {'price_id'},
    'probe_results_mirror.tsv': {'row_id', 'probe_id', 'vantage', 'vantage_id', 'target'},
    'probe_targets.json': {'target_id'},
    'probes_compute.tsv': {'probe_id', 'vantage', 'target'},
    'probes_core.tsv': {'probe_id', 'vantage', 'target'},
    'probes_data.tsv': {'probe_id', 'vantage', 'target'},
    'quota_changes.tsv': {'change_id', 'subscription'},
    'quotas_central.yaml': {'subscription'},
    'quotas_east.toml': {'subscription'},
    'quotas_north.sqlite': {'subscription'},
    'quotas_south.md': {'subscription'},
    'quotas_west.html': {'subscription'},
    'region_groups_2025.toml': {'control_id'},
    'schema_registry.yaml': set(),
    'sdk_events_1.jsonl': {'event_id', 'install_id', 'batch_id'},
    'sdk_events_2.jsonl': {'event_id', 'install_id', 'batch_id'},
    'sdk_events_3.jsonl': {'event_id', 'install_id', 'batch_id'},
    'sdk_server_receipts.csv': {'event_id'},
    'sla_enrollment_central.md': {'enrollment_id', 'subscription_id'},
    'sla_enrollment_east.html': {'enrollment_id', 'subscription_id'},
    'sla_enrollment_north.pdf': {'enrollment_id', 'subscription_id'},
    'sla_enrollment_south.pdf': {'enrollment_id', 'subscription_id'},
    'sla_enrollment_west.csv': {'enrollment_id', 'subscription_id'},
    'sla_policy_2026.docx': {'pin_id', 'subscription_id'},
    'sla_policy_v4_draft.docx': {'pin_id', 'subscription_id'},
    'sla_report_draft.pdf': {'void_ref', 'posting_id', 'ref', 'claim_id'},
    'source_register.md': {'order_ref', 'subscription_id'},
    'subscriptions_central.csv': {'subscription_id', 'account_ref'},
    'subscriptions_east.parquet': {'subscription_id', 'account_ref'},
    'subscriptions_north.sqlite': {'subscription_id', 'account_ref'},
    'subscriptions_south.jsonl': {'subscription_id', 'account_ref'},
    'subscriptions_west.xlsx': {'subscription_id', 'account_ref', 'discount_id'},
    'support_tickets.jsonl': {'ticket_id', 'crm_case', 'order_ref'},
    'suspension_orders.pdf': {'order_id', 'subscription'},
    'svc_metrics_compacted.parquet': {'record_id', 'subscription', 'batch_id', 'target'},
    'svc_metrics_part1.parquet': {'record_id', 'subscription', 'batch_id'},
    'svc_metrics_part2.parquet': {'record_id', 'subscription', 'batch_id'},
    'svc_metrics_part3.parquet': {'record_id', 'subscription', 'batch_id'},
    'telemetry_collection_standard.docx': {'gap_id'},
    'telemetry_quarantine.json': {'quarantine_id'},
    'telemetry_voids.jsonl': {'void_id', 'target'},
    'uptime_dashboard_snapshot.html': {'row_id', 'retired_id', 'target_id', 'beta_id'},
}


class RecordSet(object):
    """Records of one file, plus the control value of every record."""

    def __init__(self, name, fmt, control_field, records=None, error=None):
        self.name = name
        self.fmt = fmt
        self.control_field = control_field
        self.records = records if records is not None else []
        self.error = error

    def control_value(self, rec):
        if self.fmt == 'ini':
            sec = rec.get('_section', '')
            return sec.split('.', 1)[1] if '.' in sec else sec
        if self.fmt == 'mbox':
            return rec.get('_message_local', '')
        if self.fmt == 'fwf':
            return rec.get('record_id', '')
        if self.fmt == 'ics':
            return rec.get('UID', '')
        for k, v in rec.items():
            if k.startswith('_'):
                continue
            return v
        return ''

    def block_sums(self):
        vals = [self.control_value(r) for r in self.records]
        out = []
        for i in range(0, len(vals), 100):
            chunk = vals[i:i + 100]
            out.append((i // 100 + 1, len(chunk), sum(digits_value(v) for v in chunk)))
        return out


def digits_value(text):
    if text is None:
        return 0
    s = str(text)
    ds = ''.join(ch for ch in s if '0' <= ch <= '9')
    if not ds:
        return 0
    try:
        return int(ds)
    except ValueError:
        return 0


EDGE_V6 = [('record_id', 12), ('host', 16), ('subscription', 10), ('reading', 14),
           ('requests', 7), ('err_5xx', 6), ('err_429', 6), ('err_4xx', 6),
           ('seq', 4), ('batch_id', 14)]


def read_edge_file(path, v7_layout):
    text = read_text(path)
    rows = []
    layout = EDGE_V6
    for line in text.split('\n'):
        if not line.strip():
            continue
        if line[0] == 'H':
            layout = v7_layout if line[1:3] == 'V7' else EDGE_V6
            continue
        if line[0] == 'T':
            continue
        if line[0] == 'D' and layout:
            rec = {}
            pos = 1
            for name, width in layout:
                rec[name] = fix_str(line[pos:pos + width])
                pos += width
            rows.append(rec)
    return rows


def read_table_records(name, fmt, data_dir, v7_layout=None):
    """Read one file into RecordSet (records in catalog order)."""
    path = os.path.join(data_dir, name)
    if not os.path.exists(path):
        return RecordSet(name, fmt, None, None, error='missing')
    try:
        if fmt == 'csv':
            recs = read_delimited(path, ',')
        elif fmt == 'tsv':
            recs = read_delimited(path, '\t')
        elif fmt == 'jsonl':
            recs = read_jsonl(path)
        elif fmt == 'json':
            d = read_json(path)
            recs = [item for v in d.values() if isinstance(v, list)
                    for item in v if isinstance(item, dict)]
        elif fmt == 'xml':
            recs = read_xml(path)
        elif fmt == 'yaml':
            recs = read_yaml_lists(path)
        elif fmt == 'toml':
            recs = read_toml_tables(path)
        elif fmt == 'ini':
            recs = []
            for sec, vals in read_ini(path):
                r = dict(vals)
                r['_section'] = sec
                recs.append(r)
        elif fmt == 'sqlite':
            recs = read_sqlite(path)
        elif fmt == 'parquet':
            recs = read_parquet(path)
        elif fmt == 'xlsx':
            recs = read_xlsx_rows(path)
        elif fmt == 'log':
            recs = read_log_events(path)
        elif fmt == 'md':
            recs = []
            for cap, header, row in read_md_tables(path):
                r = dict(zip(header, row))
                r['_caption'] = cap
                recs.append(r)
        elif fmt == 'html':
            recs = []
            for cap, header, rows in read_html_tables(path):
                for row in rows:
                    r = dict(zip(header, row))
                    r['_caption'] = cap
                    recs.append(r)
        elif fmt == 'pdf':
            recs = []
            for cap, header, row in read_pdf_tables(path):
                if not any(re.search(r'[a-z_]', h or '') for h in header):
                    continue
                r = dict(zip(header, row))
                r['_caption'] = cap
                recs.append(r)
        elif fmt == 'docx':
            recs = []
            for cap, rows in read_docx_tables(path):
                if not rows:
                    continue
                header = rows[0]
                for row in rows[1:]:
                    r = dict(zip(header, row))
                    r['_caption'] = cap
                    recs.append(r)
        elif fmt == 'mbox':
            recs = []
            for headers, body in read_mbox(path):
                r = dict(headers)
                r['_body'] = body
                mid = r.get('Message-ID', '')
                m = re.match(r'<([^@]*)@?', mid)
                r['_message_local'] = m.group(1) if m else ''
                recs.append(r)
        elif fmt == 'ics':
            recs = []
            for ev in read_ics(path):
                r = {}
                for k, v in ev.items():
                    if k == '_params':
                        for pk, pv in v.items():
                            r['_' + pk + '_params'] = pv
                        continue
                    r[k] = v
                recs.append(r)
        elif fmt == 'fwf':
            recs = read_edge_file(path, v7_layout or [])
        else:
            raise ValueError('unknown format %s' % fmt)
        return RecordSet(name, fmt, None, recs)
    except Exception as exc:  # unreadable
        return RecordSet(name, fmt, None, None, error='unreadable: %s' % exc)


def valid_records(rs):
    """Records whose identifier fields are all well formed."""
    out = []
    default_fields = ID_FIELDS.get(rs.name, set())
    for rec in rs.records:
        fields = default_fields
        cap = rec.get('_caption')
        if cap is not None:
            override = ID_FIELDS.get('%s|%s' % (rs.name, cap))
            if override is not None:
                fields = override
        ok = True
        for f in fields:
            v = rec.get(f)
            if v is None or (isinstance(v, str) and clean(v) == ''):
                continue
            canon, malformed = canon_id(v)
            if malformed:
                ok = False
                break
            if canon is not None:
                rec[f] = canon
        if ok:
            out.append(rec)
    return out



# --------------------------------------------------------------------------
# controls

def expected_blocks_from_register(records):
    """{(file, block): (records, control_sum)} keeping the highest revision."""
    out = {}
    for r in records:
        cid = r.get('control_id')
        if not cid:
            continue
        try:
            block = int(r.get('block'))
            revision = int(r.get('revision'))
        except (TypeError, ValueError):
            continue
        recs = parse_count(r.get('records'))
        s = parse_count(r.get('control_sum'))
        if recs is None or s is None:
            continue
        key = (r.get('file'), block)
        cur = out.get(key)
        if cur is None or revision > cur[2]:
            out[key] = (recs, s, revision)
    return out


def check_controls(cat, files, reg_blocks, external_blocks):
    """Return (per-file info, held reasons)."""
    info = {}
    reasons = []
    for entry in cat.catalog:
        name = entry['file']
        rs = files[name]
        if name == 'audit_control_register.pdf':
            info[name] = {'records': len(rs.records), 'control_blocks': 0,
                          'control_ok': True}
            continue
        if rs.error == 'missing':
            info[name] = {'records': 0, 'control_blocks': 0, 'control_ok': False}
            reasons.append('MISSING:%s' % name)
            continue
        if rs.error:
            info[name] = {'records': 0, 'control_blocks': 0, 'control_ok': False}
            reasons.append('UNREADABLE:%s' % name)
            continue
        exp = {}
        for (f, b), v in reg_blocks.items():
            if f == name:
                exp[b] = (v[0], v[1])
        if not exp and name in external_blocks:
            exp = dict(external_blocks[name])
        if not exp:
            info[name] = {'records': len(rs.records), 'control_blocks': 0,
                          'control_ok': True}
            continue
        blocks = rs.block_sums()
        ok = len(blocks) == len(exp)
        if ok:
            for bno, cnt, s in blocks:
                e = exp.get(bno)
                if e is None or e[0] != cnt or e[1] != s:
                    ok = False
                    break
        if ok:
            for b in exp:
                if b < 1 or b > len(blocks):
                    ok = False
                    break
        info[name] = {'records': len(rs.records), 'control_blocks': len(exp),
                      'control_ok': ok}
        if not ok:
            reasons.append('CONTROL_MISMATCH:%s' % name)
    return info, reasons


def blocks_match(records, control_of, exp):
    blocks = []
    vals = [control_of(r) for r in records]
    for i in range(0, len(vals), 100):
        chunk = vals[i:i + 100]
        blocks.append((i // 100 + 1, len(chunk), sum(digits_value(v) for v in chunk)))
    if len(blocks) != len(exp):
        return False
    for bno, cnt, s in blocks:
        e = exp.get(bno)
        if e is None or e[0] != cnt or e[1] != s:
            return False
    return all(1 <= b <= len(blocks) for b in exp)


def table_groups(rs):
    """Group the records of a multi-table file by their source table.

    Returns (group_keys, groups) where groups maps a key to a record list in
    file order; keys are ordered as they first appear in the file.
    """
    if rs.fmt in ('docx', 'pdf', 'md', 'html'):
        keys = []
        groups = collections.OrderedDict()
        for rec in rs.records:
            k = rec.get('_caption')
            if k not in groups:
                groups[k] = []
                keys.append(k)
            groups[k].append(rec)
        return keys, groups
    if rs.fmt == 'sqlite':
        # table name unknown per record; assume one group keyed by the first field
        pass
    if rs.fmt == 'xlsx':
        # openpyxl read only order; sheets cannot be distinguished afterwards,
        # so this is handled by the caller via a sheet-aware reader
        pass
    return None, None


# --------------------------------------------------------------------------
# sheet aware readers (needed to order multi-table files like the register)

def read_xlsx_sheets(path):
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    out = []
    try:
        for sh in wb.sheetnames:
            ws = wb[sh]
            header = None
            recs = []
            for row in ws.iter_rows(values_only=True):
                vals = [fix_str(v) if isinstance(v, str) else v for v in row]
                while vals and vals[-1] is None:
                    vals.pop()
                if not vals:
                    continue
                if header is None:
                    header = [str(c).strip() if c is not None else '' for c in vals]
                    continue
                rec = {}
                for i, h in enumerate(header):
                    if h:
                        rec[h] = vals[i] if i < len(vals) else None
                rec['_caption'] = sh
                recs.append(rec)
            out.append((sh, recs))
    finally:
        wb.close()
    return out


def read_sqlite_tables(path):
    con = sqlite3.connect('file:%s?mode=ro' % path, uri=True)
    try:
        names = [r[0] for r in con.execute(
            "select name from sqlite_master where type='table' order by rowid")]
        names = [n for n in names if not n.startswith('sqlite_')]
        out = []
        for n in names:
            cur = con.execute('select * from "%s" order by rowid' % n)
            cols = [d[0] for d in cur.description]
            recs = []
            for row in cur:
                rec = {}
                for c, v in zip(cols, row):
                    rec[c] = fix_str(v) if isinstance(v, str) else v
                rec['_caption'] = n
                recs.append(rec)
            out.append((n, recs))
        return out
    finally:
        con.close()


def _first_field(rec):
    for k, v in rec.items():
        if k.startswith('_'):
            continue
        return v
    return ''


def ordered_tables(fmt, path, exp):
    """Read a multi-table file, choosing the table order that matches `exp`."""
    if fmt == 'xlsx':
        groups = read_xlsx_sheets(path)
    elif fmt == 'sqlite':
        groups = read_sqlite_tables(path)
    else:
        return None
    if len(groups) <= 1:
        return [r for _, recs in groups for r in recs]
    table = {k: recs for k, recs in groups}
    default = [k for k, _ in groups]

    def flat(order):
        return [r for key in order for r in table[key]]

    if blocks_match(flat(default), _first_field, exp):
        return flat(default)
    from itertools import permutations
    for n in range(len(default) - 1, 0, -1):
        for perm in permutations(default, n):
            order = list(perm) + [k for k in default if k not in perm]
            if blocks_match(flat(order), _first_field, exp):
                return flat(order)
    return flat(default)



# --------------------------------------------------------------------------
# the close

class Close(object):

    def __init__(self, data_dir, out_dir, prior_dir):
        self.data_dir = data_dir
        self.out_dir = out_dir
        self.prior_dir = prior_dir
        self.cat = Catalog(os.path.join(data_dir, 'source_register.md'), data_dir)
        period = self.cat.params.get('period')
        y, m = int(period[:4]), int(period[5:7])
        self.period = period
        self.year = y
        self.month = m
        self.days = days_in_month(y, m)
        self.month_start = _dt.datetime(y, m, 1, tzinfo=_dt.timezone.utc).timestamp()
        self.month_end = _dt.datetime(y + (m == 12), 1 if m == 12 else m + 1, 1,
                                      tzinfo=_dt.timezone.utc).timestamp()
        self.eom_date = ymd(y, m, self.days)
        self.next_month_start = self.month_end
        self.n_windows = self.days * 288
        qstart = self.cat.params.get('quarter_start')
        self.quarter_start = parse_instant(qstart)
        self.crm_cutover = parse_instant(self.cat.params.get('crm_cutover'))
        self.zones = {}
        for r, z in self.cat.regions.items():
            self.zones[r] = Zone(z['std_offset_min'], z['dst_rule'], z['tzid'])
        self.exponents = dict(self.cat.currencies)
        self.files = {}
        self.info = {}
        self.reasons = []

    # ---------------------------------------------------------------- load

    def load(self):
        cat = self.cat
        path_of = lambda n: os.path.join(self.data_dir, n)
        # the fixed-width layout must be known before the edge files
        schema_rs = read_table_records('collector_schema_proposed.yaml', 'yaml',
                                       self.data_dir)
        v7 = []
        for r in schema_rs.records:
            if 'field' in r and 'width' in r:
                v7.append((r['field'], parse_count(r['width'])))
        self.aborted_rollouts = set()
        for r in schema_rs.records:
            if r.get('event_id'):
                self.aborted_rollouts.add(r['event_id'])
        # audit register first: it fixes the table order of the other files
        reg_rs = read_table_records('audit_control_register.pdf', 'pdf', self.data_dir)
        self.reg_blocks = expected_blocks_from_register(reg_rs.records)
        groups_rs = read_table_records('region_groups_2025.toml', 'toml', self.data_dir)
        self.external_blocks = {}
        ext = {}
        for r in groups_rs.records:
            if r.get('file') == 'price_book.toml':
                b = parse_count(r.get('block'))
                recs = parse_count(r.get('records'))
                s = parse_count(r.get('control_sum'))
                if b and recs is not None and s is not None:
                    ext[b] = (recs, s)
        self.external_blocks['price_book.toml'] = ext
        # ingest CONTROL events for edge_legacy_c.txt
        rep_rs = read_table_records('ingest_reprocess.log', 'log', self.data_dir)
        ext2 = {}
        for r in rep_rs.records:
            if r.get('event') == 'CONTROL' and r.get('file') == 'edge_legacy_c.txt':
                b = parse_count(r.get('block'))
                recs = parse_count(r.get('records'))
                s = parse_count(r.get('control_sum'))
                if b and recs is not None and s is not None:
                    ext2[b] = (recs, s)
        self.external_blocks['edge_legacy_c.txt'] = ext2
        self.replay_batches = set()
        for r in rep_rs.records:
            if r.get('event') == 'REPLAY' and r.get('batch'):
                self.replay_batches.add(r['batch'])
        self.ingest_reprocess = rep_rs

        for entry in cat.catalog:
            name = entry['file']
            fmt = entry['format']
            if name == 'collector_schema_proposed.yaml':
                rs = schema_rs
            elif name == 'audit_control_register.pdf':
                rs = reg_rs
            elif name == 'region_groups_2025.toml':
                rs = groups_rs
            elif name == 'ingest_reprocess.log':
                rs = rep_rs
            elif name in ('price_book.toml', 'edge_legacy_c.txt'):
                exp = self.external_blocks.get(name, {})
                recs = ordered_tables(fmt, path_of(name), exp) if fmt in ('xlsx', 'sqlite') \
                    else None
                if recs is not None:
                    rs = RecordSet(name, fmt, None, recs)
                else:
                    rs = read_table_records(name, fmt, self.data_dir, v7)
            else:
                exp = {}
                for (f, b), val in self.reg_blocks.items():
                    if f == name:
                        exp[b] = (val[0], val[1])
                recs = ordered_tables(fmt, path_of(name), exp) if fmt in ('xlsx', 'sqlite') \
                    else None
                if recs is not None:
                    rs = RecordSet(name, fmt, None, recs)
                else:
                    rs = read_table_records(name, fmt, self.data_dir, v7)
            self.files[name] = rs
        self.info, self.reasons = check_controls(cat, self.files, self.reg_blocks,
                                                 self.external_blocks)
        # reference data
        self._build_reference()

    # ------------------------------------------------------------ reference

    def _build_reference(self):
        cat = self.cat
        # region aliases and sites
        self.region_alias = {}
        self.region_site = {}
        for r in valid_records(self.files['region_groups_2025.toml']):
            if r.get('alias') and r.get('region'):
                self.region_alias[r['alias']] = r['region']
            if r.get('region') and r.get('site'):
                self.region_site[r['region']] = r['site']
        # charter tables
        charter = self.files['governance_charter.docx'].records
        self.plan_segments = {}
        self.region_regroups = []
        self.account_decisions = []
        for r in valid_records(self.files['governance_charter.docx']):
            cap = r.get('_caption')
            if cap == 'Plan segments' and r.get('plan_code'):
                self.plan_segments[r['plan_code']] = r.get('segment')
            elif cap == 'Region regroupings' and r.get('region'):
                self.region_regroups.append((r['region'], r.get('region_group'),
                                             parse_date(r.get('effective'))))
            elif cap == 'Account decisions' and r.get('decision_id'):
                self.account_decisions.append(r)
        # accounts
        self.accounts = {}
        for r in valid_records(self.files['accounts_master.csv']):
            aid = r.get('account_id')
            if not aid:
                continue
            self.accounts[aid] = {
                'created': parse_date(r.get('created')),
                'currency': r.get('currency'),
                'home_region': self.canon_region(r.get('home_region')),
                'status': r.get('status')}
        self.account_alias = {}
        for r in valid_records(self.files['account_aliases.tsv']):
            a = r.get('alias_id')
            b = r.get('account_id')
            if a and b:
                self.account_alias[a] = b
        self.account_map = {}
        for r in self.account_decisions:
            dec = parse_date(r.get('decided_on'))
            if dec is None or dec > self.eom_date:
                continue
            frm = r.get('from_account')
            to = r.get('to_account')
            if not frm or not to:
                continue
            self.account_map[frm] = to
        for a, b in self.account_alias.items():
            self.account_map.setdefault(a, b)
        self.snapshot = {}
        for r in valid_records(self.files['account_snapshot_legacy.sqlite']):
            aid = r.get('account_id')
            if not aid:
                continue
            self.snapshot[aid] = {'ban': r.get('ban'),
                                  'internal': (str(r.get('internal_flag')).upper() == 'Y')}
        self.ban_to_account = {}
        for aid, s in self.snapshot.items():
            if s['ban']:
                self.ban_to_account[s['ban']] = aid
        # calendar sites per account
        self.account_site = {}
        for r in valid_records(self.files['credit_operations_manual.docx']):
            if r.get('account_id') and r.get('calendar_site'):
                self.account_site[r['account_id']] = r['calendar_site']
        # business-day calendars per site
        self.site_calendar = collections.defaultdict(dict)
        for r in valid_records(self.files['maintenance_policy.docx']):
            if r.get('site') and r.get('date'):
                d = parse_date(r.get('date'))
                if d:
                    self.site_calendar[r['site']][d] = (r.get('business').upper() == 'Y')
        # credit preferences
        self.auto_credit = set()
        for r in valid_records(self.files['credit_preferences.json']):
            if r.get('account_id') and r.get('auto_credit') in (True, 'true', 'True', 'Y'):
                self.auto_credit.add(r['account_id'])
        # contracts and amendments
        self.contract_account = {}
        self.contract_dates = collections.defaultdict(list)
        for r in valid_records(self.files['contracts_register.xlsx']):
            if r.get('contract_id') and r.get('account_id'):
                acc = self.resolve_account(r['account_id'])
                if acc:
                    self.contract_account[r['contract_id']] = acc
        for r in valid_records(self.files['contracts_register.xlsx']):
            if r.get('amendment_id') and r.get('contract_id'):
                cid = r['contract_id']
                d = parse_date(r.get('signed_on'))
                acc = self.contract_account.get(cid)
                if acc and d:
                    self.contract_dates[acc].append((d, r['amendment_id']))
        for r in valid_records(self.files['contracts_register.xlsx']):
            if r.get('contract_id') and r.get('account_id') and not r.get('amendment_id'):
                d = parse_date(r.get('signed_on'))
                if d:
                    self.contract_dates[r['account_id']].append((d, r['contract_id']))
        # policy tables
        self.version_cutovers = []
        self.service_targets = {}
        self.credit_tiers = collections.defaultdict(list)
        self.bad_threshold = {}
        self.pins = collections.defaultdict(list)
        for r in valid_records(self.files['sla_policy_2026.docx']):
            cap = r.get('_caption')
            if cap == 'Version cutovers':
                self.version_cutovers.append((parse_date(r.get('signed_from')), r['version']))
            elif cap == 'Service targets':
                self.service_targets[(r['version'], r['sla_class'])] = \
                    parse_decimal(r.get('target_pct'))
            elif cap == 'Credit tiers':
                self.credit_tiers[r['version']].append(
                    (r['tier'], r['kind'], parse_decimal(r.get('threshold')),
                     parse_decimal(r.get('credit_pct'))))
            elif cap == 'Bad window thresholds':
                self.bad_threshold[r['version']] = parse_count(r.get('permille'))
            elif cap == 'Subscription pins':
                sid = r.get('subscription_id')
                if sid:
                    self.pins[sid].append((parse_date(r.get('pinned_on')), r['version']))
        # legacy schedule v2 tables from the draft (designated by the charter)
        self.legacy_plan_codes = {}
        for r in valid_records(self.files['sla_policy_v4_draft.docx']):
            cap = r.get('_caption')
            if cap == 'Legacy schedule v2 targets':
                self.service_targets[(r['version'], r['sla_class'])] = \
                    parse_decimal(r.get('target_pct'))
            elif cap == 'Legacy schedule v2 tiers':
                self.credit_tiers[r['version']].append(
                    (r['tier'], r['kind'], parse_decimal(r.get('threshold')),
                     parse_decimal(r.get('credit_pct'))))
            elif cap == 'Legacy schedule v2 thresholds':
                self.bad_threshold[r['version']] = parse_count(r.get('permille'))
            elif cap == 'Legacy plan codes' and r.get('legacy_code'):
                self.legacy_plan_codes[r['legacy_code']] = r.get('plan_code')
        # v5 ratified targets
        self.v5_targets = collections.defaultdict(list)
        for r in valid_records(self.files['credit_tiers_2026.xlsx']):
            if (r.get('_caption') or '').lower() != 'ratified':
                continue
            if r.get('target_id') and r.get('product') is not None:
                eff = parse_date(r.get('effective'))
                tgt = parse_decimal(r.get('target_pct'))
                if eff is None or tgt is None:
                    continue
                self.v5_targets[(self.canon_region(r.get('region')), r['product'],
                                 r['sla_class'])].append((eff, tgt))
        # enterprise schedules and revocations
        self.schedules = collections.defaultdict(list)
        for r in valid_records(self.files['enterprise_sla_schedules.pdf']):
            tgt = parse_decimal(r.get('target_pct'))
            pct = parse_decimal(r.get('credit_pct'))
            eff = parse_date(r.get('effective'))
            sid = r.get('subscription_id')
            if tgt is None or pct is None or eff is None or not sid:
                continue
            self.schedules[sid].append((eff, r['schedule_id'], tgt, pct))
        self.revoked_schedules = set()
        for r in valid_records(self.files['credit_tiers_2026.xlsx']):
            if r.get('revocation_id') and r.get('schedule_id'):
                self.revoked_schedules.add(r['schedule_id'])
        # probe targets and vantage points
        self.targets = {}
        for r in valid_records(self.files['probe_targets.json']):
            tid = r.get('target_id')
            if tid:
                self.targets[tid] = (self.canon_region(r.get('region')), r.get('product'))
        self.retired_target = {}
        self.beta = []
        for r in valid_records(self.files['uptime_dashboard_snapshot.html']):
            if r.get('retired_id') and r.get('target_id'):
                self.retired_target[r['retired_id']] = r['target_id']
            if r.get('beta_id') and r.get('product'):
                self.beta.append((r['product'], self.canon_region(r.get('region')),
                                  parse_date(r.get('beta_from')),
                                  parse_date(r.get('beta_to'))))
        self.vantage_point = {}
        for r in valid_records(self.files['probe_results_mirror.tsv']):
            if r.get('kind') == 'VANTAGE' and r.get('vantage') and r.get('vantage_id'):
                self.vantage_point[r['vantage']] = r['vantage_id']

    def canon_region(self, r):
        if r is None:
            return None
        s = clean(r)
        if not s:
            return None
        s = s.lower()
        return self.region_alias.get(s, s)

    def resolve_account(self, ref):
        seen = set()
        cur = ref
        while cur is not None and cur in self.account_map and cur not in seen:
            seen.add(cur)
            cur = self.account_map[cur]
        if cur in self.accounts:
            return cur
        return None

    # ------------------------------------------------------------ business days

    @staticmethod
    def date_of(ymd_int):
        if isinstance(ymd_int, _dt.date):
            return ymd_int
        return _dt.date(ymd_int // 10000, (ymd_int // 100) % 100, ymd_int % 100)

    @staticmethod
    def ymd_of(d):
        return d.year * 10000 + d.month * 100 + d.day

    def is_business(self, site, d):
        cal = self.site_calendar.get(site)
        if cal and d in cal:
            return cal[d]
        return self.date_of(d).weekday() < 5

    def nth_business_after(self, site, start_date, n):
        d = self.date_of(start_date)
        count = 0
        while count < n:
            d += _dt.timedelta(days=1)
            if self.is_business(site, self.ymd_of(d)):
                count += 1
        return self.ymd_of(d)

    def nth_business_before(self, site, start_date, n):
        d = self.date_of(start_date)
        count = 0
        while count < n:
            d -= _dt.timedelta(days=1)
            if self.is_business(site, self.ymd_of(d)):
                count += 1
        return self.ymd_of(d)

    # ------------------------------------------------------------ windows

    def window_of(self, ts):
        if ts is None:
            return None
        w = int((ts - self.month_start) // 300)
        if 0 <= w < self.n_windows:
            return w
        return None

    def window_start_ts(self, w):
        return self.month_start + w * 300

    def mask_range(self, a, b):
        if b <= a:
            return 0
        return ((1 << (b - a)) - 1) << a

    def windows_of_interval(self, start, end):
        """Window indices whose start instant lies inside [start, end)."""
        if start is None or end is None or end <= start:
            return 0
        a = int((start - self.month_start) // 300) + (0 if (start - self.month_start) % 300 == 0 else 1)
        if start < self.month_start:
            a = 0
        else:
            a = int((start - self.month_start) // 300)
        b = int((end - self.month_start) // 300)
        if (end - self.month_start) % 300 == 0:
            b = int((end - self.month_start) // 300)
        else:
            b = int((end - self.month_start) // 300) + 1
        a = max(a, 0)
        b = min(b, self.n_windows)
        return self.mask_range(a, b)

    # ------------------------------------------------------------ subscriptions

    SUBS_FILES = ['subscriptions_central.csv', 'subscriptions_east.parquet',
                  'subscriptions_north.sqlite', 'subscriptions_south.jsonl',
                  'subscriptions_west.xlsx']

    def fee_value(self, raw, currency):
        """Monthly fee -> minor units, 'LIST', or None for a placeholder."""
        if raw is None:
            return None
        s = clean(raw)
        if s is None or s == '':
            return None
        up = s.upper()
        if up in ('N/A', 'NA', 'NONE', '-1'):
            return None
        if up == 'LIST':
            return 'LIST'
        exp = self.exponents.get((currency or '').upper(), 2)
        return parse_amount(raw, exp)

    def load_subscriptions(self):
        subs = {}
        order = []
        for name in self.SUBS_FILES:
            for r in valid_records(self.files[name]):
                if not r.get('subscription_id'):
                    continue
                if 'product' not in r or 'start_date' not in r:
                    continue
                cur = (r.get('currency') or '').upper()
                fee = self.fee_value(r.get('monthly_fee'), cur)
                if fee is None:
                    continue          # placeholder record
                sid = r['subscription_id']
                if sid in subs:
                    continue
                subs[sid] = {
                    'subscription_id': sid,
                    'account_ref': r.get('account_ref'),
                    'product': (r.get('product') or '').upper(),
                    'region': self.canon_region(r.get('region')),
                    'start_date': parse_date(r.get('start_date')),
                    'end_date': parse_date(r.get('end_date')),
                    'plan_code': r.get('plan_code'),
                    'currency': (r.get('currency') or '').upper(),
                    'fee': fee,
                }
                order.append(sid)
        self.subs = subs
        self.sub_order = order
        # active days and window masks
        first = ymd(self.year, self.month, 1)
        for sid, s in subs.items():
            st = s['start_date'] if s['start_date'] else 0
            en = s['end_date'] if s['end_date'] else 99999999
            lo = max(st, first)
            hi = min(en, self.eom_date)
            days = 0
            mask = 0
            if hi >= lo:
                d0 = _dt.date(lo // 10000, (lo // 100) % 100, lo % 100)
                d1 = _dt.date(hi // 10000, (hi // 100) % 100, hi % 100)
                n = (d1 - d0).days + 1
                days = n
                a = int((d0 - _dt.date(self.year, self.month, 1)).days) * 288
                mask = self.mask_range(a, a + n * 288)
            s['active_days'] = days
            s['active_mask'] = mask
        # plan at month end
        self._load_plan_changes()
        for sid, s in subs.items():
            s['plan'] = self.plan_at_month_end(s['plan_code'], sid)
            s['segment'] = self.plan_segments.get(s['plan'])
        # suspensions
        self._load_suspensions()
        for sid, s in subs.items():
            s['suspended_mask'] = self.suspension_mask(sid) & s['active_mask']

    def _load_plan_changes(self):
        self.plan_changes = collections.defaultdict(list)
        files = ['plan_changes_central.tsv', 'plan_changes_east.json',
                 'plan_changes_north.xml', 'plan_changes_south.yaml',
                 'plan_changes_west.log']
        for name in files:
            for r in valid_records(self.files[name]):
                if not r.get('change_id'):
                    continue
                sid = r.get('subscription_id')
                eff = parse_instant(r.get('effective'))
                if eff is None:
                    d = parse_date(r.get('effective'))
                    if d is None:
                        continue
                    eff = parse_instant(_dt.datetime(d // 10000, (d // 100) % 100,
                                                    d % 100).strftime('%Y-%m-%dT00:00:00Z'))
                action = (r.get('action') or '').upper()
                self.plan_changes[sid].append((eff, r['change_id'], action,
                                               r.get('plan_code'), r.get('reverts')))

    def plan_at_month_end(self, own_plan, sid):
        changes = self.plan_changes.get(sid)
        applied = None
        if changes:
            voided = set()
            cand = []
            for eff, cid, action, plan, reverts in changes:
                if eff is None or eff > self.next_month_start:
                    continue
                cand.append((eff, cid, action, plan, reverts))
            for eff, cid, action, plan, reverts in cand:
                if action == 'REVERT' and reverts:
                    voided.add(reverts)
            best = None
            for eff, cid, action, plan, reverts in cand:
                if action != 'APPLY' or cid in voided:
                    continue
                key = (eff, cid)
                if best is None or key > best[0]:
                    best = (key, plan)
            if best is not None:
                applied = best[1]
        plan = applied if applied else own_plan
        if plan is None:
            return None
        plan = clean(plan)
        if not plan:
            return None
        return self.legacy_plan_codes.get(plan, plan)

    def _load_suspensions(self):
        # lifecycle events
        self.suspension_events = collections.defaultdict(list)
        for r in valid_records(self.files['lifecycle_events.log']):
            if not r.get('subscription'):
                continue
            ev = (r.get('event') or '').upper()
            if ev not in ('SUSPEND', 'RESUME'):
                continue
            ts = r.get('_ts')
            if ts is None:
                continue
            self.suspension_events[r['subscription']].append((ts, r.get('event_id'), ev))
        self.suspension_orders = collections.defaultdict(list)
        for r in valid_records(self.files['suspension_orders.pdf']):
            if not r.get('subscription'):
                continue
            if (r.get('status') or '').upper() != 'ACTIVE':
                continue
            f = parse_instant(r.get('from'))
            t = parse_instant(r.get('to'))
            if f is None:
                continue
            self.suspension_orders[r['subscription']].append((f, t if t else self.month_end))

    def suspension_intervals(self, sid):
        out = []
        evs = sorted(self.suspension_events.get(sid, []))
        start = None
        for ts, eid, ev in evs:
            if ev == 'SUSPEND' and start is None:
                start = ts
            elif ev == 'RESUME' and start is not None:
                out.append((start, ts))
                start = None
        if start is not None:
            out.append((start, None))
        out += list(self.suspension_orders.get(sid, []))
        return out

    def suspension_mask(self, sid):
        mask = 0
        for f, t in self.suspension_intervals(sid):
            end = t if t is not None else self.month_end + 1e9
            mask |= self.windows_of_interval(f, end)
        return mask


    # ------------------------------------------------------------ telemetry

    def _host_context(self):
        self.host_region = {}
        for r in valid_records(self.files['host_inventory.csv']):
            h = r.get('host')
            if h:
                self.host_region[h] = (self.canon_region(r.get('region')),
                                       (r.get('product') or '').upper())
        # lane assignments
        self.host_lane = {}
        for r in valid_records(self.files['telemetry_collection_standard.docx']):
            h = r.get('host')
            if h and r.get('assigned_on'):
                d = parse_date(r.get('assigned_on'))
                lane = r.get('lane')
                if d is None or d > self.eom_date:
                    continue
                cur = self.host_lane.get(h)
                if cur is None or d >= cur[0]:
                    if cur is None or d > cur[0]:
                        self.host_lane[h] = (d, lane)
        # quarantines
        self.quarantines = collections.defaultdict(list)
        for r in valid_records(self.files['telemetry_quarantine.json']):
            if (r.get('status') or '').upper() != 'ACTIVE':
                continue
            h = r.get('host')
            f = parse_instant(r.get('from'))
            t = parse_instant(r.get('to'))
            if h and f is not None:
                self.quarantines[h].append((f, t if t is not None else self.month_end + 1e9))
        # collector precedence and lanes
        self.collector_prec = {}
        self.collector_lane = {}
        for r in valid_records(self.files['telemetry_collection_standard.docx']):
            if r.get('collector') and r.get('precedence'):
                self.collector_prec[r['collector']] = parse_count(r['precedence'])
                self.collector_lane[r['collector']] = r.get('lane')
        # collector gaps
        self.gaps = collections.defaultdict(list)
        for r in valid_records(self.files['telemetry_collection_standard.docx']):
            if r.get('gap_id') and r.get('region'):
                f = parse_instant(r.get('from'))
                t = parse_instant(r.get('to'))
                if f is not None:
                    self.gaps[(r['region'], r.get('collector'))].append(
                        (f, t if t is not None else self.month_end + 1e9))
        # ingest batches: latest registration wins
        self.batch_status = {}
        for r in valid_records(self.files['ingest_batches.jsonl']):
            bid = r.get('batch_id')
            if not bid:
                continue
            ts = parse_instant(r.get('loaded_at'))
            cur = self.batch_status.get(bid)
            if cur is None or (ts, bid) > cur[0]:
                self.batch_status[bid] = ((ts, bid), (r.get('status') or '').upper())
        # sampling factors
        self.sampling = collections.defaultdict(list)
        for r in valid_records(self.files['lb_sampling.parquet']):
            h = r.get('host')
            eff = parse_instant(r.get('effective_from'))
            one = parse_count(r.get('one_in'))
            if h and eff is not None and one is not None:
                self.sampling[h].append((eff, one if one > 0 else 1))
        # log schemas
        self.schema_versions = {}
        for r in valid_records(self.files['schema_registry.yaml']):
            if r.get('version') and 'err_5xx_includes_429' in r:
                self.schema_versions[r['version']] = bool(r['err_5xx_includes_429'])
        self.schema_baseline = {}
        for r in valid_records(self.files['schema_registry.yaml']):
            if r.get('host') and r.get('schema'):
                d = parse_date(r.get('as_of'))
                if d is None:
                    continue
                cur = self.schema_baseline.get(r['host'])
                if cur is None or d >= cur[0]:
                    self.schema_baseline[r['host']] = (d, r['schema'])
        # deploy waves
        wave_rev = collections.defaultdict(list)
        for r in valid_records(self.files['deploy_manifests.xml']):
            if r.get('wave') and r.get('host'):
                rev = parse_count(r.get('revision'))
                wave_rev[r['wave']].append((rev if rev is not None else 0, r['host']))
        self.wave_hosts = {}
        for wave, members in wave_rev.items():
            best = max(m[0] for m in members)
            self.wave_hosts[wave] = set(h for rev, h in members if rev == best)
        self.deploy_events = collections.defaultdict(list)
        for r in valid_records(self.files['deploy_events.log']):
            ev = (r.get('event') or '').upper()
            if ev not in ('ROLLOUT', 'ROLLBACK'):
                continue
            if r.get('event_id') in self.aborted_rollouts:
                continue
            ts = r.get('_ts')
            wave = r.get('wave')
            seq = parse_count(r.get('seq'))
            schema = r.get('schema')
            if ts is None or wave is None or seq is None or schema is None:
                continue
            hosts = self.wave_hosts.get(wave, ())
            for h in hosts:
                self.deploy_events[h].append((ts, seq, schema, r['event_id']))
        for h in self.deploy_events:
            self.deploy_events[h].sort()
        # host clocks
        self.host_clock = collections.defaultdict(list)
        for name in ('host_clock_edge_a.ini', 'host_clock_edge_b.ini',
                     'host_clock_edge_c.ini'):
            for sec, vals in read_ini(os.path.join(self.data_dir, name)):
                h = clean(vals.get('host'))
                ts = parse_instant(vals.get('measured_at'))
                skew = parse_count(vals.get('skew_s'))
                if h and ts is not None:
                    self.host_clock[h].append((ts, skew if skew is not None else 0))
        for h in self.host_clock:
            self.host_clock[h].sort()
        # voids from telemetry_voids plus designated evidence
        self.void_state = {}
        void_rows = [r for r in valid_records(self.files['telemetry_voids.jsonl'])]
        void_rows.sort(key=lambda r: (parse_instant(r.get('at')) or 0, r.get('void_id') or ''))
        for r in void_rows:
            tgt = r.get('target')
            if not tgt:
                continue
            act = (r.get('action') or '').upper()
            if act == 'VOID':
                self.void_state[tgt] = True
            elif act == 'RESTORE':
                self.void_state[tgt] = False
        for r in valid_records(self.files['lb_errors_east_replay.csv']):
            if (r.get('marker') or '').upper() == 'VOID' and r.get('record_id'):
                self.void_state[r['record_id']] = True
        for r in valid_records(self.files['svc_metrics_compacted.parquet']):
            if r.get('kind') == 'TOMBSTONE' and r.get('target'):
                self.void_state[r['target']] = True
        self.node_host = {}
        for r in valid_records(self.files['svc_metrics_compacted.parquet']):
            if r.get('kind') == 'ALIAS' and r.get('node') and r.get('host'):
                self.node_host[r['node']] = r['host']
        # sdk install map, withdrawn builds, builds
        self.install_sub = {}
        for r in valid_records(self.files['client_sdk_dedup.jsonl']):
            if r.get('kind') == 'INSTALL' and r.get('install_id') and r.get('subscription'):
                self.install_sub[r['install_id']] = r['subscription']
        self.withdrawn_builds = set()
        for r in valid_records(self.files['client_sdk_dedup.jsonl']):
            if r.get('kind') == 'WITHDRAWN_BUILD' and r.get('build'):
                self.withdrawn_builds.add(r['build'])
        self.builds = {}
        for r in valid_records(self.files['sdk_builds.json']):
            if r.get('build'):
                self.builds[r['build']] = {'clock': (r.get('clock') or '').upper(),
                                           'status': (r.get('status') or '').upper()}
        self.receipts = {}
        for r in valid_records(self.files['sdk_server_receipts.csv']):
            if r.get('event_id'):
                ts = parse_instant(r.get('received_at'))
                if ts is not None:
                    self.receipts[r['event_id']] = ts

    def batch_ok(self, bid):
        if not bid:
            return False
        st = self.batch_status.get(bid)
        if st is None:
            return False
        return st[1] == 'LOADED' and bid not in self.replay_batches

    def sampling_factor(self, host, ts):
        best = None
        for eff, one in self.sampling.get(host, ()):
            if eff <= ts and (best is None or eff > best[0]):
                best = (eff, one)
        return best[1] if best else 1

    def host_schema(self, host, ts):
        best = None
        for ev_ts, seq, schema, eid in self.deploy_events.get(host, ()):
            if ev_ts <= ts and (best is None or seq > best[0]):
                best = (seq, schema)
        if best is not None:
            return best[1]
        cur = self.schema_baseline.get(host)
        return cur[1] if cur else None

    def clock_skew(self, host, ts):
        best = None
        for m_ts, skew in self.host_clock.get(host, ()):
            if m_ts <= ts and (best is None or m_ts > best[0]):
                best = (m_ts, skew)
        return best[1] if best else 0

    def in_gap(self, region, collector, ts):
        for f, t in self.gaps.get((region, collector), ()):
            if f <= ts < t:
                return True
        return False

    def quarantined(self, host, ts):
        for f, t in self.quarantines.get(host, ()):
            if f <= ts < t:
                return True
        return False

    def load_telemetry(self):
        """Build the used telemetry record per (subscription, window)."""
        self._host_context()
        best = collections.defaultdict(dict)   # (sid, window) -> {prec: (seq, rid, R, E5, E429)}
        subs = self.subs
        region_of_sub = {sid: s['region'] for sid, s in subs.items()}
        product_of_sub = {sid: s['product'] for sid, s in subs.items()}
        active_of_sub = {sid: s['active_mask'] for sid, s in subs.items()}

        def offer(sid, window, prec, seq, rid, r_count, e5, e429):
            if sid not in subs or window is None:
                return
            if not (active_of_sub[sid] >> window) & 1:
                return
            d = best[(sid, window)]
            cur = d.get(prec)
            key = (seq, rid)
            if cur is None or key > cur[0]:
                d[prec] = (key, rid, r_count, e5, e429)

        def counts_ok(rq, e5, e429, e4xx):
            return None not in (rq, e5, e429, e4xx)

        # ---- load balancer
        for name in ['lb_errors_central.csv', 'lb_errors_east.csv',
                     'lb_errors_north.csv', 'lb_errors_south.csv',
                     'lb_errors_west.csv']:
            for r in valid_records(self.files[name]):
                rid = r.get('record_id')
                if not rid or self.void_state.get(rid):
                    continue
                sid = r.get('subscription')
                host = r.get('host')
                rq = parse_count(r.get('requests'))
                e5 = parse_count(r.get('err_5xx'))
                e429 = parse_count(r.get('err_429'))
                e4xx = parse_count(r.get('err_4xx'))
                if not counts_ok(rq, e5, e429, e4xx):
                    continue
                if not self.batch_ok(r.get('batch_id')):
                    continue
                ts = parse_instant(r.get('window_start'))
                if ts is None:
                    continue
                window = self.window_of(ts)
                if window is None:
                    continue
                hr = self.host_region.get(host)
                if hr is None or hr[0] != region_of_sub.get(sid) or hr[1] != product_of_sub.get(sid):
                    continue
                lane = self.host_lane.get(host)
                lane = lane[1] if lane else None
                if lane != 'LB':
                    continue
                if self.quarantined(host, ts):
                    continue
                one = self.sampling_factor(host, ts)
                rq *= one
                e5 = e5 * one
                e429 = e429 * one
                e4xx = e4xx * one
                schema = self.host_schema(host, ts)
                if schema and self.schema_versions.get(schema):
                    e5 = max(0, e5 - e429)
                seq = parse_count(r.get('seq'))
                if seq is None:
                    seq = -1
                offer(sid, window, 1, seq, rid, rq, e5, e429)
        # ---- load balancer gap fill
        for r in valid_records(self.files['lb_errors_east_replay.csv']):
            marker = (r.get('marker') or '').upper()
            if marker != 'GAPFILL':
                continue
            rid = r.get('record_id')
            if not rid or self.void_state.get(rid):
                continue
            sid = r.get('subscription')
            host = r.get('host')
            rq = parse_count(r.get('requests'))
            e5 = parse_count(r.get('err_5xx'))
            e429 = parse_count(r.get('err_429'))
            e4xx = parse_count(r.get('err_4xx'))
            if not counts_ok(rq, e5, e429, e4xx):
                continue
            if not self.batch_ok(r.get('batch_id')):
                continue
            ts = parse_instant(r.get('window_start'))
            if ts is None:
                continue
            window = self.window_of(ts)
            if window is None:
                continue
            hr = self.host_region.get(host)
            if hr is None or hr[0] != region_of_sub.get(sid) or hr[1] != product_of_sub.get(sid):
                continue
            if not self.in_gap(hr[0], 'LB', ts):
                continue
            lane = self.host_lane.get(host)
            lane = lane[1] if lane else None
            if lane != 'LB':
                continue
            if self.quarantined(host, ts):
                continue
            one = self.sampling_factor(host, ts)
            rq *= one
            e5 = e5 * one
            e429 = e429 * one
            schema = self.host_schema(host, ts)
            if schema and self.schema_versions.get(schema):
                e5 = max(0, e5 - e429)
            seq = parse_count(r.get('seq'))
            if seq is None:
                seq = -1
            offer(sid, window, 1, seq, rid, rq, e5, e429)
        # ---- service metrics
        for name in ['svc_metrics_part1.parquet', 'svc_metrics_part2.parquet',
                     'svc_metrics_part3.parquet']:
            for r in valid_records(self.files[name]):
                rid = r.get('record_id')
                if not rid or self.void_state.get(rid):
                    continue
                sid = r.get('subscription')
                node = r.get('node')
                host = self.node_host.get(node)
                if host is None:
                    continue
                if 'requests_k' in r:
                    rq = parse_count(r.get('requests_k'))
                    if rq is not None:
                        rq = rq * 1000
                else:
                    rq = parse_count(r.get('requests'))
                e5 = parse_count(r.get('err_5xx'))
                e429 = parse_count(r.get('err_429'))
                e4xx = parse_count(r.get('err_4xx'))
                if not counts_ok(rq, e5, e429, e4xx):
                    continue
                if not self.batch_ok(r.get('batch_id')):
                    continue
                ts = parse_instant(r.get('window_start_ms'))
                if ts is None:
                    continue
                window = self.window_of(ts)
                if window is None:
                    continue
                hr = self.host_region.get(host)
                if hr is None or hr[0] != region_of_sub.get(sid) or hr[1] != product_of_sub.get(sid):
                    continue
                lane = self.host_lane.get(host)
                lane = lane[1] if lane else None
                if lane != 'SVC':
                    continue
                if self.quarantined(host, ts):
                    continue
                schema = self.host_schema(host, ts)
                if schema and self.schema_versions.get(schema):
                    e5 = max(0, e5 - e429)
                seq = parse_count(r.get('seq'))
                if seq is None:
                    seq = -1
                offer(sid, window, 2, seq, rid, rq, e5, e429)
        # ---- edge legacy
        for name in ['edge_legacy_a.txt', 'edge_legacy_b.txt', 'edge_legacy_c.txt']:
            for r in valid_records(self.files[name]):
                rid = r.get('record_id')
                if not rid or self.void_state.get(rid):
                    continue
                sid = r.get('subscription')
                host = r.get('host')
                rq = parse_count(r.get('requests'))
                e5 = parse_count(r.get('err_5xx'))
                e429 = parse_count(r.get('err_429'))
                e4xx = parse_count(r.get('err_4xx'))
                if not counts_ok(rq, e5, e429, e4xx):
                    continue
                if not self.batch_ok(r.get('batch_id')):
                    continue
                hr = self.host_region.get(host)
                if hr is None:
                    continue
                zone = self.zones.get(hr[0])
                if zone is None:
                    continue
                naive = parse_naive_dt(r.get('reading'))
                if naive is None:
                    continue
                u = zone.local_to_utc(naive)
                ts = u - self.clock_skew(host, u)
                window = self.window_of(ts)
                if window is None:
                    continue
                if hr[0] != region_of_sub.get(sid) or hr[1] != product_of_sub.get(sid):
                    continue
                lane = self.host_lane.get(host)
                lane = lane[1] if lane else None
                if lane != 'EDGE':
                    continue
                if self.quarantined(host, ts):
                    continue
                schema = self.host_schema(host, ts)
                if schema and self.schema_versions.get(schema):
                    e5 = max(0, e5 - e429)
                seq = parse_count(r.get('seq'))
                if seq is None:
                    seq = -1
                offer(sid, window, 3, seq, rid, rq, e5, e429)
        # ---- CDN attestations
        for r in valid_records(self.files['cdn_attestations.xlsx']):
            rid = r.get('record_id')
            if not rid or self.void_state.get(rid):
                continue
            sid = r.get('subscription')
            host = r.get('host')
            rq = parse_count(r.get('requests'))
            e5 = parse_count(r.get('err_5xx'))
            e429 = parse_count(r.get('err_429'))
            e4xx = parse_count(r.get('err_4xx'))
            if not counts_ok(rq, e5, e429, e4xx):
                continue
            if not self.batch_ok(r.get('batch_id')):
                continue
            ts = parse_instant(r.get('window_start'))
            if ts is None:
                continue
            window = self.window_of(ts)
            if window is None:
                continue
            hr = self.host_region.get(host)
            if hr is None or hr[0] != region_of_sub.get(sid) or hr[1] != product_of_sub.get(sid):
                continue
            lane = self.host_lane.get(host)
            lane = lane[1] if lane else None
            if lane != 'CDN':
                continue
            if self.quarantined(host, ts):
                continue
            schema = self.host_schema(host, ts)
            if schema and self.schema_versions.get(schema):
                e5 = max(0, e5 - e429)
            seq = parse_count(r.get('seq'))
            if seq is None:
                seq = -1
            offer(sid, window, 4, seq, rid, rq, e5, e429)
        # ---- CDN XML logs
        for name in ['cdn_logs_akamoto.xml', 'cdn_logs_fastedge.xml']:
            for r in valid_records(self.files[name]):
                rid = r.get('record_id')
                if not rid or self.void_state.get(rid):
                    continue
                sid = r.get('subscription')
                host = r.get('host')
                rq = parse_count(r.get('requests'))
                e5 = parse_count(r.get('err_5xx'))
                e429 = parse_count(r.get('err_429'))
                e4xx = parse_count(r.get('err_4xx'))
                if not counts_ok(rq, e5, e429, e4xx):
                    continue
                if not self.batch_ok(r.get('batch_id')):
                    continue
                ts = parse_instant(r.get('window_epoch'))
                if ts is None:
                    continue
                window = self.window_of(ts)
                if window is None:
                    continue
                hr = self.host_region.get(host)
                if hr is None or hr[0] != region_of_sub.get(sid) or hr[1] != product_of_sub.get(sid):
                    continue
                lane = self.host_lane.get(host)
                lane = lane[1] if lane else None
                if lane != 'CDN':
                    continue
                if self.quarantined(host, ts):
                    continue
                schema = self.host_schema(host, ts)
                if schema and self.schema_versions.get(schema):
                    e5 = max(0, e5 - e429)
                seq = parse_count(r.get('seq'))
                if seq is None:
                    seq = -1
                offer(sid, window, 5, seq, rid, rq, e5, e429)
        # ---- SDK events
        for name in ['sdk_events_1.jsonl', 'sdk_events_2.jsonl', 'sdk_events_3.jsonl']:
            for r in valid_records(self.files[name]):
                rid = r.get('event_id')
                if not rid or self.void_state.get(rid):
                    continue
                sid = self.install_sub.get(r.get('install_id'))
                if sid is None:
                    continue
                build = self.builds.get(r.get('build'))
                if build is None or build['status'] == 'RECALLED' \
                        or r.get('build') in self.withdrawn_builds:
                    continue
                ts = r.get('_ts')
                if build['clock'] == 'DEVICE':
                    ts = self.receipts.get(rid)
                    if ts is None:
                        continue
                else:
                    ts = r.get('_ts')
                if ts is None:
                    continue
                window = self.window_of(ts)
                if window is None:
                    continue
                rq = parse_count(r.get('requests'))
                e5 = parse_count(r.get('errors_5xx'))
                e429 = parse_count(r.get('errors_429'))
                e4xx = parse_count(r.get('errors_4xx'))
                if not counts_ok(rq, e5, e429, e4xx):
                    continue
                if not self.batch_ok(r.get('batch_id')):
                    continue
                seq = parse_count(r.get('seq'))
                if seq is None:
                    seq = -1
                offer(sid, window, 6, seq, rid, rq, e5, e429)
        self.telemetry = {}
        for (sid, window), d in best.items():
            prec = min(d)
            key, rid, rq, e5, e429 = d[prec]
            self.telemetry.setdefault(sid, {})[window] = (rq, e5, e429, prec)


    # ------------------------------------------------------------ outages

    def load_outages(self):
        # voided probe results
        flapvoid = set()
        for r in valid_records(self.files['probe_results_mirror.tsv']):
            if (r.get('kind') or '').upper() == 'FLAPVOID' and r.get('probe_id'):
                flapvoid.add(r['probe_id'])
        down = collections.defaultdict(lambda: collections.defaultdict(set))
        files = ['probes_core.tsv', 'probes_compute.tsv', 'probes_data.tsv']
        for name in files:
            for r in valid_records(self.files[name]):
                pid = r.get('probe_id')
                if not pid or pid in flapvoid:
                    continue
                if (r.get('status') or '').upper() != 'DOWN':
                    continue
                vp = self.vantage_point.get(r.get('vantage'))
                if vp is None:
                    continue
                target = r.get('target')
                if not target:
                    continue
                target = self.retired_target.get(target, target)
                info = self.targets.get(target)
                if info is None:
                    continue
                region, product = info
                ts = parse_instant(r.get('observed_at'))
                if ts is None:
                    continue
                w = self.window_of(ts)
                if w is None:
                    continue
                down[(product, region)][w].add(vp)
        self.outage = {}
        for key, per_window in down.items():
            mask = 0
            for w, vps in per_window.items():
                if len(vps) >= 2:
                    mask |= 1 << w
            self.outage[key] = mask
        # NOC declarations (confirmed, not retracted)
        retracted = set()
        for r in valid_records(self.files['incident_register_preliminary.xml']):
            if r.get('retraction_id') and r.get('noc_id'):
                retracted.add(r['noc_id'])
        for r in valid_records(self.files['noc_outage_declarations.pdf']):
            if (r.get('status') or '').upper() != 'CONFIRMED':
                continue
            noc = r.get('noc_id')
            if noc in retracted:
                continue
            product = (r.get('product') or '').upper()
            region = self.canon_region(r.get('region'))
            f = parse_instant(r.get('start'))
            t = parse_instant(r.get('end'))
            if f is None:
                continue
            mask = self.windows_of_interval(f, t if t is not None else self.month_end)
            key = (product, region)
            self.outage[key] = self.outage.get(key, 0) | mask

    # ------------------------------------------------------------ incidents

    def load_incidents(self):
        prelim_to_final = {}
        for r in valid_records(self.files['incident_register_preliminary.xml']):
            if r.get('prelim_id') and r.get('final_id'):
                prelim_to_final[r['prelim_id']] = r['final_id']
        intervals = collections.defaultdict(list)
        updates = collections.defaultdict(list)
        for r in valid_records(self.files['incident_register.xml']):
            if r.get('incident_id') and r.get('opened'):
                product = (r.get('product') or '').upper()
                region = self.canon_region(r.get('region'))
                opened = parse_instant(r.get('opened'))
                closed = parse_instant(r.get('closed'))
                if opened is None:
                    continue
                end = closed if closed is not None else self.month_end
                intervals[(product, region, r['incident_id'])].append((opened, end))
            elif r.get('update_id') and r.get('ref'):
                ref = r['ref']
                ref = prelim_to_final.get(ref, ref)
                at = parse_instant(r.get('at'))
                until = parse_instant(r.get('until'))
                if at is None:
                    continue
                updates[ref].append((at, r['update_id'],
                                     (r.get('action') or '').upper(), until))
        for ref, ups in updates.items():
            ups.sort()
        self.incident_intervals = {}
        for (product, region, iid), ivs in intervals.items():
            ivs = sorted(ivs)
            cur = list(ivs)
            for at, uid, action, until in updates.get(iid, []):
                if not cur:
                    if action in ('REOPEN', 'EXTEND', 'CLOSE'):
                        cur.append((at, until if until is not None else self.month_end))
                    continue
                s, e = cur[-1]
                if action == 'EXTEND':
                    if until is not None and until > e:
                        cur[-1] = (s, until)
                elif action == 'CLOSE':
                    cur[-1] = (s, until if until is not None else e)
                elif action == 'REOPEN':
                    cur[-1] = (s, at)
                    cur.append((at, until if until is not None else self.month_end))
            key = (product, region)
            self.incident_intervals.setdefault(key, []).extend(cur)

    # ------------------------------------------------------------ maintenance

    def load_maintenance(self):
        # approvals
        approvals = collections.defaultdict(list)
        for r in valid_records(self.files['maintenance_changes.xlsx']):
            if (r.get('_caption') or '').lower() != 'approvals':
                continue
            if r.get('approval_id') and r.get('change_id'):
                seq = parse_count(r.get('seq'))
                if seq is None:
                    seq = -1
                approvals[r['change_id']].append((seq, r.get('decision'),
                                                  r.get('approval_id')))
        # notices: earliest message about a change
        notices = {}
        for headers, body in read_mbox(os.path.join(self.data_dir,
                                                    'maintenance_notices.mbox')):
            subject = headers.get('Subject', '') or ''
            mid = headers.get('Message-ID', '')
            m = re.search(r'(CHG-\d+)', subject)
            cid = m.group(1) if m else None
            if cid is None:
                m = re.search(r'change[_ ]?id:\s*(CHG-\d+)', body or '', re.I)
                cid = m.group(1) if m else None
            if cid is None:
                continue
            try:
                ts = parse_instant(headers.get('Date'))
            except Exception:
                ts = None
            if ts is None:
                continue
            cur = notices.get(cid)
            if cur is None or ts < cur:
                notices[cid] = ts
        # calendar
        calendar = {}
        for ev in read_ics(os.path.join(self.data_dir, 'change_calendar.ics')):
            uid = ev.get('UID')
            if not uid:
                continue
            seq = parse_count(ev.get('SEQUENCE'))
            if seq is None:
                seq = 0
            cur = calendar.get(uid)
            if cur is None or seq >= cur[0]:
                calendar[uid] = (seq, ev, seq)
        # changes
        self.maintenance = {}
        regions_with_zone = self.zones
        for r in valid_records(self.files['maintenance_changes.xlsx']):
            if (r.get('_caption') or '').lower() != 'changes':
                continue
            if not r.get('change_id'):
                continue
            if (r.get('type') or '').upper() != 'PLANNED':
                continue
            cid = r['change_id']
            aps = approvals.get(cid, [])
            if not aps:
                continue
            best_seq = max(a[0] for a in aps)
            decisions = [a[1] for a in aps if a[0] == best_seq]
            if not any((d or '').upper() == 'APPROVED' for d in decisions):
                continue
            region = self.canon_region(r.get('region'))
            product = (r.get('product') or '').upper()
            zone = regions_with_zone.get(region)
            if zone is None:
                continue
            # times
            start_local = parse_naive_dt(r.get('start_local'))
            end_local = parse_naive_dt(r.get('end_local'))
            ev = calendar.get(cid)
            if ev is not None:
                e = ev[1]
                status = (e.get('STATUS') or '').upper()
                if status == 'CANCELLED':
                    continue
                params = e.get('_params', {})
                ds = e.get('DTSTART')
                de = e.get('DTEND')
                if ds and de:
                    start_local = self._ics_naive(ds, params.get('DTSTART', {}))
                    end_local = self._ics_naive(de, params.get('DTEND', {}))
            if start_local is None or end_local is None:
                continue
            start = zone.local_to_utc(start_local)
            end = zone.local_to_utc(end_local)
            # notice
            notice_ts = notices.get(cid)
            if notice_ts is None:
                continue
            site = self.region_site.get(region)
            local_start = zone.local_date(start)
            limit = self.nth_business_before(site, self.ymd_of(local_start), 5)
            if self.ymd_of(zone.local_date(notice_ts)) > limit:
                continue
            mask = self.windows_of_interval(start, end)
            if mask:
                key = (product, region)
                self.maintenance[key] = self.maintenance.get(key, 0) | mask

    def _ics_naive(self, value, params):
        s = clean(value)
        if not s:
            return None
        tzid = params.get('TZID')
        m = re.fullmatch(r'(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z?', s)
        if not m:
            return None
        if s.endswith('Z'):
            ts = _dt.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                             int(m.group(4)), int(m.group(5)), int(m.group(6)),
                             tzinfo=_dt.timezone.utc).timestamp()
            zone = self._zone_for_tzid(tzid) if tzid else None
            if zone is None:
                return instant_to_utc(ts).replace(tzinfo=None)
            return zone.utc_to_local(ts).replace(tzinfo=None)
        return _dt.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                            int(m.group(4)), int(m.group(5)), int(m.group(6)))

    def _zone_for_tzid(self, tzid):
        if not tzid:
            return None
        for region, z in self.zones.items():
            if z.tzid == tzid:
                return z
        return None

    # ------------------------------------------------------------ attribution

    def load_attribution(self):
        deps = {}
        for r in valid_records(self.files['incident_attribution_policy.docx']):
            if r.get('product') and r.get('upstream') and r.get('_caption') == 'Service dependencies':
                deps.setdefault((r.get('product') or '').upper(), set()).add(
                    (r.get('upstream') or '').upper())
        self.upstream_products = deps
        links = collections.defaultdict(list)
        for r in valid_records(self.files['dependency_links.tsv']):
            if r.get('link_id') and r.get('downstream') and r.get('upstream'):
                ts = parse_instant(r.get('registered_at'))
                if ts is None:
                    continue
                links[(r['downstream'], r['upstream'])].append(
                    (ts, r['link_id'], (r.get('action') or '').upper()))
        for r in valid_records(self.files['incident_attribution_policy.docx']):
            if r.get('link_id') and r.get('downstream') and r.get('upstream') \
                    and r.get('_caption') == 'Dependency declarations':
                ts = parse_instant(r.get('registered_at'))
                if ts is None:
                    continue
                links[(r['downstream'], r['upstream'])].append(
                    (ts, r['link_id'], (r.get('action') or '').upper()))
        for k in links:
            links[k].sort()
        self.dep_links = links

    def link_in_force(self, downstream, upstream, ts):
        state = None
        best = None
        for t, lid, action in self.dep_links.get((downstream, upstream), ()):
            if t <= ts and (best is None or (t, lid) >= best):
                best = (t, lid)
                state = action
        return state == 'ADD'

    def incident_covers(self, product, region, ts):
        for f, t in self.incident_intervals.get((product, region), ()):
            if f is not None and f <= ts and (t is None or t > ts):
                return True
        return False


    # ------------------------------------------------------------ SLA model

    def sla_version(self, s, sid):
        if s.get('segment') == 'enterprise':
            scheds = self.schedules.get(sid)
            if scheds:
                cands = [(eff, scid, tgt, pct) for eff, scid, tgt, pct in scheds
                         if eff is not None and eff <= self.eom_date
                         and scid not in self.revoked_schedules]
                if cands:
                    best = max(cands)
                    return 'custom', best[2], best[3]
        pins = self.pins.get(sid)
        if pins:
            cands = [(d, v) for d, v in pins if d is not None and d <= self.eom_date]
            if cands:
                best = max(cands)
                return best[1], None, None
        acc = s.get('account')
        best = None
        for d, ident in self.contract_dates.get(acc, ()):
            if d is not None and d <= self.eom_date:
                if best is None or (d, ident) > best:
                    best = (d, ident)
        if best is None:
            d = self.accounts.get(acc, {}).get('created')
            if d is not None:
                best = (d, '')
        if best is not None:
            version = None
            for cutoff, ver in sorted(self.version_cutovers):
                if cutoff is not None and cutoff <= best[0]:
                    version = ver
            if version:
                return version, None, None
        return None, None, None

    def target_of(self, version, s, sla_class, sched_target):
        if version == 'custom':
            return sched_target
        if version == 'v5':
            key = (s['region'], s['product'], sla_class)
            cands = [(eff, tgt) for eff, tgt in self.v5_targets.get(key, ()) if eff <= self.eom_date]
            if cands:
                return max(cands)[1]
            return None
        return self.service_targets.get((version, sla_class))

    def credit_pct_of(self, version, target, uptime, sched_pct):
        if version == 'custom':
            if uptime < target:
                return sched_pct
            return Decimal(0)
        best = Decimal(0)
        for tier, kind, threshold, pct in self.credit_tiers.get(version, ()):
            if pct is None:
                continue
            if kind == 'rel':
                if uptime < target - threshold:
                    best = max(best, pct)
            elif kind == 'abs':
                if uptime < threshold:
                    best = max(best, pct)
        return best

    def threshold_of(self, version):
        if version == 'custom':
            version = 'v5'
        return self.bad_threshold.get(version)

    # ------------------------------------------------------------ enrollment

    def load_enrollment(self):
        self.enrollments = collections.defaultdict(list)
        files = ['sla_enrollment_central.md', 'sla_enrollment_east.html',
                 'sla_enrollment_north.pdf', 'sla_enrollment_south.pdf',
                 'sla_enrollment_west.csv']
        for name in files:
            for r in valid_records(self.files[name]):
                if not r.get('enrollment_id'):
                    continue
                sid = r.get('subscription_id')
                eff = parse_date(r.get('effective'))
                if sid is None or eff is None:
                    continue
                self.enrollments[sid].append((eff, r['enrollment_id'],
                                              (r.get('action') or '').upper(),
                                              r.get('sla_class')))

    def enrollment_in_force(self, sid):
        cands = [(eff, eid, action, cls) for eff, eid, action, cls
                 in self.enrollments.get(sid, ()) if eff <= self.eom_date]
        if not cands:
            return None
        best = max(cands)
        if best[2] == 'ENROLLED':
            return best[3]
        return None

    # ------------------------------------------------------------ quotas

    def load_quotas(self):
        self.quota_changes = collections.defaultdict(list)
        for r in valid_records(self.files['quota_changes.tsv']):
            if not r.get('change_id'):
                continue
            sid = r.get('subscription')
            eff = parse_instant(r.get('effective'))
            q = parse_count(r.get('quota'))
            if sid is None or eff is None or q is None:
                continue
            self.quota_changes[sid].append((eff, r['change_id'], q))
        self.base_quotas = collections.defaultdict(list)
        for name in ['quotas_central.yaml', 'quotas_east.toml', 'quotas_north.sqlite',
                     'quotas_south.md', 'quotas_west.html']:
            for r in valid_records(self.files[name]):
                if not r.get('subscription'):
                    continue
                d = parse_date(r.get('as_of'))
                q = parse_count(r.get('quota_per_window'))
                if d is None or q is None:
                    continue
                self.base_quotas[r['subscription']].append((d, q))

    def quota_at(self, sid, ts):
        best = None
        for eff, cid, q in self.quota_changes.get(sid, ()):
            if eff <= ts and (best is None or (eff, cid) > best[0]):
                best = ((eff, cid), q)
        if best is not None:
            return best[1]
        best = None
        for d, q in self.base_quotas.get(sid, ()):
            if d <= self.eom_date and (best is None or d > best[0]):
                best = (d, q)
        if best is not None:
            return best[1]
        return None

    # ------------------------------------------------------------ fees

    def load_fees(self):
        self.fee_overrides = collections.defaultdict(list)
        for r in valid_records(self.files['fee_overrides.xlsx']):
            if not r.get('override_id'):
                continue
            sid = r.get('subscription_id')
            rev = parse_count(r.get('revision'))
            appr = parse_date(r.get('approved_on'))
            if sid is None or rev is None or appr is None:
                continue
            if (r.get('status') or '').upper() != 'APPROVED' or appr > self.eom_date:
                continue
            self.fee_overrides[sid].append((rev, r['override_id'],
                                           parse_amount(r.get('fee_minor'))))
        self.price_book = collections.defaultdict(list)
        for r in valid_records(self.files['price_book.toml']):
            if not r.get('price_id'):
                continue
            eff = parse_date(r.get('effective'))
            amount = parse_amount(r.get('amount'))
            if eff is None or amount is None:
                continue
            key = ((r.get('plan') or '').upper(), (r.get('product') or '').upper(),
                   (r.get('currency') or '').upper())
            self.price_book[key].append((eff, amount, r['price_id']))
        self.discounts = collections.defaultdict(list)
        for r in valid_records(self.files['subscriptions_west.xlsx']):
            if not r.get('discount_id'):
                continue
            acc = self.resolve_account(r.get('account_ref'))
            eff = parse_date(r.get('effective'))
            bp = parse_count(r.get('discount_bp'))
            if acc is None or eff is None or bp is None:
                continue
            self.discounts[acc].append((eff, bp, r['discount_id']))

    def discount_bp(self, account):
        best = None
        for eff, bp, did in self.discounts.get(account, ()):
            if best is None or (eff, did) > best[0]:
                best = ((eff, did), bp)
        return best[1] if best else 0

    def fee_minor(self, s, sid, account):
        ov = self.fee_overrides.get(sid)
        if ov:
            best = max(ov)
            if best[2] is not None:
                return best[2]
        if s['fee'] not in (None, 'LIST') and isinstance(s['fee'], int):
            return s['fee']
        if s['fee'] == 'LIST':
            key = (s.get('plan') or '', s['product'], s['currency'])
            cands = [(eff, amount, pid) for eff, amount, pid in self.price_book.get(key, ())
                     if eff <= self.eom_date]
            if cands:
                best = max(cands)
                amount = best[1]
                bp = self.discount_bp(account)
                if bp:
                    return r_half_even(float(amount) * (1 - bp / 10000.0))
                return amount
        return None

    # ------------------------------------------------------------ claims

    def load_claims(self):
        # withdrawn refs (claim references from the draft report are authoritative)
        ref_to_claim = {}
        for r in valid_records(self.files['sla_report_draft.pdf']):
            if r.get('ref') and r.get('claim_id'):
                ref_to_claim[r['ref']] = r['claim_id']
        withdrawn_claims = set()
        for r in valid_records(self.files['claims_workflow.log']):
            if (r.get('event') or '').upper() != 'WITHDRAWN':
                continue
            claim = ref_to_claim.get(r.get('ref'))
            if claim:
                withdrawn_claims.add(claim)
        self.withdrawn_claims = withdrawn_claims
        # CRM crosswalk and legacy claims
        self.crm_to_sub = {}
        self.crm_claims = []
        for r in valid_records(self.files['claims_crm_legacy.csv']):
            if not r.get('case_id'):
                continue
            filed = parse_instant(r.get('filed_at'))
            if r.get('subscription_id'):
                self.crm_to_sub[r['case_id']] = r['subscription_id']
            if filed is not None:
                self.crm_claims.append((r['case_id'], r['subscription_id'], filed))
        # portal claims
        self.portal_claims = []
        for r in valid_records(self.files['claims_portal.csv']):
            if not r.get('claim_id'):
                continue
            filed = parse_instant(r.get('filed_at'))
            if filed is not None:
                self.portal_claims.append((r['claim_id'], r.get('subscription_id'), filed))
        # back office receipts
        decisions = collections.defaultdict(list)
        for r in valid_records(self.files['claims_backoffice.xlsx']):
            if r.get('decision_id') and r.get('receipt_id'):
                d = parse_date(r.get('decided_on'))
                if d is None:
                    continue
                decisions[r['receipt_id']].append((d, r['decision_id'],
                                                  (r.get('decision') or '').upper()))
        self.receipt_claims = []
        for r in valid_records(self.files['claims_backoffice.xlsx']):
            if not r.get('receipt_id') or r.get('decision_id'):
                continue
            filed = parse_instant(r.get('received'))
            ban = r.get('ban')
            if filed is None or not ban:
                continue
            dec = decisions.get(r['receipt_id'])
            if not dec:
                continue
            best = max(dec)
            if best[2] == 'REJECTED':
                continue
            self.receipt_claims.append((r['receipt_id'], r.get('subscription_id'),
                                        filed, ban))
        # support tickets
        self.ticket_claims = []
        for r in valid_records(self.files['support_tickets.jsonl']):
            if (r.get('category') or '').upper() != 'SLA_CLAIM':
                continue
            if not r.get('ticket_id'):
                continue
            filed = parse_instant(r.get('opened_at'))
            if filed is None:
                continue
            sub = None
            if r.get('crm_case'):
                sub = self.crm_to_sub.get(r['crm_case'])
            if sub is None and r.get('order_ref'):
                sub = self.cat.legacy_orders.get(r['order_ref'])
            if sub is not None:
                self.ticket_claims.append((r['ticket_id'], sub, filed))

    def claims_for(self, sid, account, segment):
        cands = []
        deadline_date = self.nth_business_after(self.account_site.get(account), self.eom_date, 10)
        for claim_id, sub, filed, *rest in self.portal_claims:
            if sub == sid:
                cands.append((claim_id, filed))
        for claim_id, sub, filed in self.ticket_claims:
            if sub == sid:
                cands.append((claim_id, filed))
        for claim_id, sub, filed, ban in self.receipt_claims:
            if sub != sid:
                continue
            acc = self.ban_to_account.get(ban)
            if acc is None:
                acc = self.resolve_account(ban)
            if acc != account:
                continue
            cands.append((claim_id, filed))
        if segment == 'smb':
            for case_id, sub, filed in self.crm_claims:
                if sub == sid and filed < self.crm_cutover:
                    cands.append((case_id, filed))
        out = []
        for claim_id, filed in cands:
            if filed < self.month_start:
                continue
            if claim_id in self.withdrawn_claims:
                continue
            site = self.account_site.get(account)
            if site is not None:
                zone = self.zones.get(self.accounts.get(account, {}).get('home_region'))
                if zone is None:
                    local_date = instant_to_utc(filed).date()
                else:
                    local_date = zone.local_date(filed)
                d = local_date.year * 10000 + local_date.month * 100 + local_date.day
                if deadline_date is not None and d > deadline_date:
                    continue
            out.append((claim_id, filed))
        if not out:
            return None, None
        out.sort()
        return out[0][0], out[0][1]

    # ------------------------------------------------------------ fx

    def load_fx(self):
        treasury = collections.defaultdict(list)
        for r in valid_records(self.files['fx_hourly_treasury.csv']):
            if not r.get('fixing_id'):
                continue
            cur = (r.get('currency') or '').upper()
            hour = parse_instant(r.get('hour'))
            rev = parse_count(r.get('revision'))
            rate = parse_decimal(r.get('usd_per_unit'))
            if hour is None or rev is None or rate is None:
                continue
            treasury[(cur, int(hour // 3600) * 3600)].append((rev, r['fixing_id'], rate))
        recalled = set()
        for r in valid_records(self.files['fx_rates_unofficial.json']):
            if r.get('recall_id') and r.get('fixing_id'):
                recalled.add(r['fixing_id'])
        self.treasury = {}
        for (cur, hour), rows in treasury.items():
            rows = [x for x in rows if x[1] not in recalled]
            if not rows:
                continue
            best = max(rows)
            self.treasury.setdefault(cur, {})[hour] = best[2]
        for cur in self.treasury:
            self.treasury[cur] = dict(sorted(self.treasury[cur].items()))
        unofficial = collections.defaultdict(dict)
        for r in valid_records(self.files['fx_rates_unofficial.json']):
            if not r.get('fixing_id') or not r.get('currency'):
                continue
            hour = parse_instant(r.get('hour'))
            rate = parse_decimal(r.get('usd_per_unit'))
            if hour is None or rate is None:
                continue
            cur = r['currency'].upper()
            hour = int(hour // 3600) * 3600
            cur_d = unofficial[cur]
            if hour not in cur_d or rate > cur_d[hour]:
                cur_d[hour] = rate
        self.unofficial = {}
        for cur, d in unofficial.items():
            self.unofficial[cur] = dict(sorted(d.items()))

    # ------------------------------------------------------------ grading

    def region_group_of(self, region):
        group = None
        for r, z in self.cat.regions.items():
            if r == region:
                group = z['region_group']
        for reg, grp, eff in self.region_regroups:
            if reg == region and eff is not None and eff <= self.eom_date:
                group = grp
        return group

    def grade(self):
        self.load_subscriptions()
        self.load_enrollment()
        self.load_quotas()
        self.load_fees()
        self.load_claims()
        self.load_fx()
        self.load_caps()
        self.load_telemetry()
        self.load_outages()
        self.load_incidents()
        self.load_maintenance()
        self.load_attribution()
        for sid, s in self.subs.items():
            s['account'] = self.resolve_account(s['account_ref'])
        # subscriptions by account (for upstream attribution lookups)
        subs_by_account_region = collections.defaultdict(list)
        for sid, s in self.subs.items():
            if s['active_days'] > 0 and s['account'] is not None:
                subs_by_account_region[(s['account'], s['region'])].append(sid)
        self.subs_by_account_region = subs_by_account_region
        records = []
        excluded = []
        for sid in sorted(self.subs):
            s = self.subs[sid]
            if s['active_days'] <= 0:
                continue
            if s['account'] is None:
                excluded.append((sid, 'UNKNOWN_ACCOUNT'))
                continue
            snap = self.snapshot.get(s['account'])
            if snap and snap['internal']:
                excluded.append((sid, 'INTERNAL_ACCOUNT'))
                continue
            beta = False
            for product, region, bfrom, bto in self.beta:
                if product == s['product'] and region == s['region'] \
                        and bfrom is not None and bfrom <= self.eom_date \
                        and (bto is None or bto > self.eom_date):
                    beta = True
                    break
            if beta:
                excluded.append((sid, 'BETA_PRODUCT_REGION'))
                continue
            sla_class = self.enrollment_in_force(sid)
            if sla_class is None:
                excluded.append((sid, 'NO_SLA_ENROLLMENT'))
                continue
            version, sched_target, sched_pct = self.sla_version(s, sid)
            if version is None:
                excluded.append((sid, 'NO_SLA_ENROLLMENT'))
                continue
            target = self.target_of(version, s, sla_class, sched_target)
            if target is None:
                excluded.append((sid, 'NO_SLA_ENROLLMENT'))
                continue
            rec = self.grade_one(sid, s, sla_class, version, target, sched_pct)
            if rec is not None:
                records.append(rec)
            else:
                excluded.append((sid, 'NO_SLA_ENROLLMENT'))
        return records, excluded

    def grade_one(self, sid, s, sla_class, version, target, sched_pct):
        active = s['active_mask']
        suspended = s['suspended_mask']
        remaining = active & ~suspended
        key = (s['product'], s['region'])
        maint = self.maintenance.get(key, 0)
        maintenance = remaining & maint
        eligible = remaining & ~maint
        tel = self.telemetry.get(sid, {})
        threshold = self.threshold_of(version)
        bad = 0
        telemetry_windows = 0
        outage_mask = self.outage.get(key, 0)
        outage_windows = 0
        for w, (rq, e5, e429, prec) in tel.items():
            if not (eligible >> w) & 1:
                continue
            telemetry_windows += 1
            quota = self.quota_at(sid, self.window_start_ts(w))
            count429 = 0
            if quota is None or quota == 0 or rq <= quota:
                count429 = e429
            if rq > 0 and threshold is not None and \
                    (e5 + count429) * 1000 >= threshold * rq:
                bad |= 1 << w
        bad |= outage_mask & eligible
        outage_windows = int((outage_mask & eligible).bit_count())
        # upstream attribution
        attributed = 0
        ups = self.upstream_products.get(s['product'])
        if ups:
            candidates = self.subs_by_account_region.get((s['account'], s['region']), ())
            if candidates:
                bits = bad
                while bits:
                    lsb = bits & -bits
                    w = lsb.bit_length() - 1
                    bits ^= lsb
                    ts = self.window_start_ts(w)
                    ok = False
                    for other in candidates:
                        if other == sid:
                            continue
                        o = self.subs[other]
                        if o['product'] not in ups:
                            continue
                        if not (o['active_mask'] >> w) & 1:
                            continue
                        if not self.link_in_force(sid, other, ts):
                            continue
                        if self.incident_covers(o['product'], s['region'], ts):
                            ok = True
                            break
                    if ok:
                        bad &= ~lsb
                        attributed += 1
        eligible_windows = int(eligible.bit_count())
        bad_windows = int(bad.bit_count())
        if eligible_windows > 0:
            uptime = (Decimal(eligible_windows - bad_windows) * 100) / Decimal(eligible_windows)
        else:
            uptime = Decimal(100)
        credit_pct = self.credit_pct_of(version, target, uptime, sched_pct)
        fee = self.fee_minor(s, sid, s['account'])
        if fee is None:
            fee = 0
        credit_minor = r_half_even(Decimal(fee) * s['active_days'] * credit_pct /
                                   (self.days * 100))
        segment = s['segment']
        auto = segment == 'enterprise' or \
            (segment == 'corporate' and s['account'] in self.auto_credit)
        claim_id = None
        claim_ts = None
        status = None
        fx_rate = None
        credit_usd = 0
        if credit_pct == 0:
            status = 'MET'
        elif auto:
            claim_id = 'AUTO'
            claim_ts = self.month_end - 3600
        else:
            claim_id, claim_ts = self.claims_for(sid, s['account'], segment)
            if claim_id is None:
                status = 'UNCLAIMED'
        if status is None:
            rate = self.fx_rate(s['currency'], claim_ts)
            if rate is None:
                rate = Decimal(0)
            fx_rate = rate
            exp = self.exponents.get(s['currency'], 2)
            credit_usd = r_half_even(Decimal(credit_minor) / (10 ** exp) * rate * 100)
        record = {
            'subscription_id': sid,
            'account_id': s['account'],
            'product': s['product'],
            'region': s['region'],
            'region_group': self.region_group_of(s['region']),
            'segment': segment,
            'plan': s['plan'],
            'sla_class': sla_class,
            'sla_version': version,
            'target_pct': ('%.3f' % round(float(target), 3)) if target is not None else None,
            'currency': s['currency'],
            'fee_minor': fee,
            'active_days': s['active_days'],
            'active_windows': int(active.bit_count()),
            'suspended_windows': int(suspended.bit_count()),
            'maintenance_windows': int(maintenance.bit_count()),
            'eligible_windows': eligible_windows,
            'telemetry_windows': telemetry_windows,
            'outage_windows': outage_windows,
            'bad_windows': bad_windows,
            'attributed_windows': attributed,
        }
        digest = hashlib.sha256()
        bits = bad
        parts = []
        while bits:
            lsb = bits & -bits
            parts.append(str(lsb.bit_length() - 1))
            bits ^= lsb
        digest.update(','.join(parts).encode('utf-8'))
        record['bad_window_digest'] = digest.hexdigest()[:16]
        record['uptime_pct'] = '%.3f' % uptime.quantize(Decimal('0.001'), rounding=ROUND_HALF_EVEN)
        record['credit_pct'] = int(credit_pct) if credit_pct == credit_pct.to_integral_value() else float(credit_pct)
        record['credit_minor'] = credit_minor
        record['claim_id'] = claim_id
        record['claim_filed_utc'] = fmt_instant(claim_ts) if (claim_ts is not None and claim_id not in (None, 'AUTO')) else None
        record['fx_rate'] = ('%.6f' % fx_rate) if fx_rate is not None else None
        record['credit_usd_cents'] = credit_usd
        record['qtd_before_usd_cents'] = 0
        record['cap_usd_cents'] = None
        record['status'] = status
        return record

    # ------------------------------------------------------------ caps pass

    def apply_caps(self, records):
        accounts = {}
        for rec in records:
            accounts.setdefault(rec['account_id'], []).append(rec)
        for acc in accounts:
            accounts[acc].sort(key=lambda r: r['subscription_id'])
        for acc, recs in accounts.items():
            caps = self.caps.get(acc, ())
            cap = None
            if caps:
                best = max(caps)
                if best[1] is not None:
                    cap = best[1]
            qtd = self.qtd_ledger.get(acc, 0) + self.goodwill.get(acc, 0) \
                + self.prior_credits.get(acc, 0)
            for rec in recs:
                rec['cap_usd_cents'] = cap
                rec['qtd_before_usd_cents'] = qtd
                if rec['status'] is None:
                    if cap is None or qtd + rec['credit_usd_cents'] <= cap:
                        rec['status'] = 'CREDITED'
                        qtd += rec['credit_usd_cents']
                    else:
                        rec['status'] = 'CAP_EXHAUSTED'
        return records


    def fx_rate(self, currency, ts):
        if currency in self.treasury:
            table = self.treasury[currency]
            source = 'treasury'
        elif currency in self.unofficial:
            table = self.unofficial[currency]
            source = 'unofficial'
        else:
            return None
        if not table:
            return None
        key = int(ts // 3600) * 3600
        best = None
        for hour in sorted(table):
            if hour <= key and (best is None or hour > best):
                best = hour
        if best is None:
            return None
        return table[best]

    # ------------------------------------------------------------ caps

    def load_caps(self):
        self.caps = collections.defaultdict(list)
        for r in valid_records(self.files['account_caps.xlsx']):
            if not r.get('cap_id'):
                continue
            acc = self.resolve_account(r.get('account_ref'))
            eff = parse_date(r.get('effective'))
            if acc is None or eff is None or eff > self.eom_date:
                continue
            cap = parse_amount(r.get('quarterly_cap_usd'))
            self.caps[acc].append((eff, cap, r['cap_id']))
        self.voided_postings = set()
        for r in valid_records(self.files['sla_report_draft.pdf']):
            if r.get('void_ref') and r.get('posting_id'):
                self.voided_postings.add(r['posting_id'])
        self.qtd_ledger = collections.defaultdict(int)
        for r in valid_records(self.files['credit_ledger.sqlite']):
            kind = (r.get('kind') or '').upper()
            if kind not in ('CREDIT', 'REVERSAL'):
                continue
            posted = parse_instant(r.get('posted_at'))
            if posted is None or not (self.quarter_start <= posted < self.month_start):
                continue
            if r.get('posting_id') in self.voided_postings:
                continue
            acc = self.resolve_account(r.get('account_ref'))
            if acc is None:
                continue
            amount = parse_amount(r.get('amount_usd_cents'))
            if amount is None:
                continue
            if kind == 'CREDIT':
                self.qtd_ledger[acc] += amount
            else:
                self.qtd_ledger[acc] -= amount
        self.goodwill = collections.defaultdict(int)
        for r in valid_records(self.files['credit_ledger.sqlite']):
            if not r.get('grant_id'):
                continue
            granted = parse_instant(r.get('granted_at'))
            if granted is None or not (self.quarter_start <= granted < self.month_end):
                continue
            acc = self.resolve_account(r.get('account_ref'))
            if acc is None:
                continue
            amount = parse_amount(r.get('amount_usd_cents'))
            if amount is not None:
                self.goodwill[acc] += amount
        self.prior_credits = collections.defaultdict(int)
        if self.prior_dir:
            prior_summary = os.path.join(self.prior_dir, 'summary.json')
            prior_norm = os.path.join(self.prior_dir, 'normalized.jsonl')
            prior_period = None
            try:
                with open(prior_summary, 'r', encoding='utf-8') as fh:
                    prior_period = json.load(fh).get('period')
            except Exception:
                prior_period = None
            if prior_period:
                quarter_start_date = instant_to_utc(self.quarter_start).strftime('%Y-%m')
                if prior_period >= quarter_start_date and prior_period < self.period:
                    try:
                        with open(prior_norm, 'r', encoding='utf-8') as fh:
                            for line in fh:
                                line = line.strip()
                                if not line:
                                    continue
                                o = json.loads(line)
                                if o.get('status') == 'CREDITED':
                                    acc = o.get('account_id')
                                    cents = o.get('credit_usd_cents') or 0
                                    self.prior_credits[acc] += int(cents)
                    except Exception:
                        pass



    # ------------------------------------------------------------ outputs

    def write_outputs(self, records, excluded):
        os.makedirs(self.out_dir, exist_ok=True)
        records = sorted(records, key=lambda r: r['subscription_id'])
        status_counts = collections.Counter(r['status'] for r in records)
        by_currency = collections.Counter()
        for r in records:
            if r['status'] == 'CREDITED':
                by_currency[r['currency']] += r['credit_minor']
        # normalized.jsonl
        fields = ['subscription_id', 'account_id', 'product', 'region', 'region_group',
                  'segment', 'plan', 'sla_class', 'sla_version', 'target_pct', 'currency',
                  'fee_minor', 'active_days', 'active_windows', 'suspended_windows',
                  'maintenance_windows', 'eligible_windows', 'telemetry_windows',
                  'outage_windows', 'bad_windows', 'attributed_windows',
                  'bad_window_digest', 'uptime_pct', 'credit_pct', 'credit_minor',
                  'claim_id', 'claim_filed_utc', 'fx_rate', 'credit_usd_cents',
                  'qtd_before_usd_cents', 'cap_usd_cents', 'status']
        with open(os.path.join(self.out_dir, 'normalized.jsonl'), 'w',
                  encoding='utf-8') as fh:
            for r in records:
                out = {}
                for f in fields:
                    v = r.get(f)
                    if isinstance(v, Decimal):
                        v = int(v) if v == v.to_integral_value() else float(v)
                    out[f] = v
                fh.write(json.dumps(out, sort_keys=True, separators=(',', ':')))
                fh.write('\n')
        # summary.json
        recon_files = len(self.cat.catalog)
        recon_records = sum(self.info[n]['records'] for n in self.info)
        recon_blocks = sum(self.info[n]['control_blocks'] for n in self.info)
        recon_fail = sum(1 for n in self.info if not self.info[n]['control_ok'])
        summary = {
            'status': 'PUBLISHED',
            'period': self.period,
            'records': len(records),
            'excluded': len(excluded),
            'status_counts': {k: status_counts.get(k, 0)
                              for k in ('MET', 'UNCLAIMED', 'CREDITED', 'CAP_EXHAUSTED')},
            'credited_usd_cents': sum(r['credit_usd_cents'] for r in records
                                      if r['status'] == 'CREDITED'),
            'credit_minor_by_currency': {k: by_currency[k] for k in sorted(by_currency)},
            'eligible_windows': sum(r['eligible_windows'] for r in records),
            'bad_windows': sum(r['bad_windows'] for r in records),
            'attributed_windows': sum(r['attributed_windows'] for r in records),
            'reconciliation': {'files': recon_files, 'records': recon_records,
                               'control_blocks': recon_blocks,
                               'control_failures': recon_fail},
        }
        with open(os.path.join(self.out_dir, 'summary.json'), 'w', encoding='utf-8') as fh:
            json.dump(summary, fh, sort_keys=True, indent=2)
            fh.write('\n')
        # data_quality.json
        sources = [{'file': n, 'records': self.info[n]['records'],
                    'control_blocks': self.info[n]['control_blocks'],
                    'control_ok': self.info[n]['control_ok']}
                   for n in sorted(self.info)]
        dq = {'sources': sources,
              'exclusions': [{'subscription_id': sid, 'reason': reason}
                             for sid, reason in sorted(excluded)]}
        with open(os.path.join(self.out_dir, 'data_quality.json'), 'w',
                  encoding='utf-8') as fh:
            json.dump(dq, fh, sort_keys=True, indent=2)
            fh.write('\n')
        # product_summary.json
        products = {}
        for r in records:
            p = products.setdefault(r['product'], {
                'records': 0, 'eligible_windows': 0, 'bad_windows': 0,
                'attributed_windows': 0, 'credited_usd_cents': 0,
                'status_counts': {k: 0 for k in ('MET', 'UNCLAIMED', 'CREDITED',
                                                 'CAP_EXHAUSTED')}})
            p['records'] += 1
            p['eligible_windows'] += r['eligible_windows']
            p['bad_windows'] += r['bad_windows']
            p['attributed_windows'] += r['attributed_windows']
            if r['status'] == 'CREDITED':
                p['credited_usd_cents'] += r['credit_usd_cents']
            p['status_counts'][r['status']] += 1
        with open(os.path.join(self.out_dir, 'product_summary.json'), 'w',
                  encoding='utf-8') as fh:
            json.dump({'products': products}, fh, sort_keys=True, indent=2)
            fh.write('\n')
        # region files
        groups = collections.defaultdict(list)
        for r in records:
            groups[r['region_group'] or ''].append(r)
        all_groups = set(z['region_group'] for z in self.cat.regions.values())
        all_groups |= set(g for g in groups if g)
        for g in sorted(all_groups):
            recs = groups.get(g, [])
            regions = collections.defaultdict(list)
            for r in recs:
                regions[r['region']].append(r)
            doc = {
                'region_group': g,
                'records': len(recs),
                'status_counts': {k: sum(1 for r in recs if r['status'] == k)
                                  for k in ('MET', 'UNCLAIMED', 'CREDITED',
                                            'CAP_EXHAUSTED')},
                'credited_usd_cents': sum(r['credit_usd_cents'] for r in recs
                                          if r['status'] == 'CREDITED'),
                'regions': {rk: {'records': len(rr),
                                'eligible_windows': sum(x['eligible_windows'] for x in rr),
                                'bad_windows': sum(x['bad_windows'] for x in rr),
                                'credited_usd_cents': sum(
                                    x['credit_usd_cents'] for x in rr
                                    if x['status'] == 'CREDITED')}
                            for rk, rr in sorted(regions.items())},
            }
            with open(os.path.join(self.out_dir, 'region_%s.json' % g), 'w',
                      encoding='utf-8') as fh:
                json.dump(doc, fh, sort_keys=True, indent=2)
                fh.write('\n')
        # segment files
        segs = collections.defaultdict(list)
        for r in records:
            segs[r['segment'] or ''].append(r)
        all_segs = set(self.plan_segments.values())
        all_segs |= set(s for s in segs if s)
        for sg in sorted(all_segs):
            recs = segs.get(sg, [])
            plans = collections.defaultdict(list)
            for r in recs:
                plans[r['plan']].append(r)
            doc = {
                'segment': sg,
                'records': len(recs),
                'status_counts': {k: sum(1 for r in recs if r['status'] == k)
                                  for k in ('MET', 'UNCLAIMED', 'CREDITED',
                                            'CAP_EXHAUSTED')},
                'credited_usd_cents': sum(r['credit_usd_cents'] for r in recs
                                          if r['status'] == 'CREDITED'),
                'plans': {pk: {'records': len(pp),
                               'credited_usd_cents': sum(
                                   x['credit_usd_cents'] for x in pp
                                   if x['status'] == 'CREDITED')}
                          for pk, pp in sorted(plans.items())},
            }
            with open(os.path.join(self.out_dir, 'segment_%s.json' % sg), 'w',
                      encoding='utf-8') as fh:
                json.dump(doc, fh, sort_keys=True, indent=2)
                fh.write('\n')

    def write_held(self):
        os.makedirs(self.out_dir, exist_ok=True)
        reasons = sorted(set(self.reasons))
        summary = {'status': 'HELD', 'period': self.period,
                   'held_reasons': reasons}
        with open(os.path.join(self.out_dir, 'summary.json'), 'w', encoding='utf-8') as fh:
            json.dump(summary, fh, sort_keys=True, indent=2)
            fh.write('\n')
        sources = [{'file': n, 'records': self.info[n]['records'],
                    'control_blocks': self.info[n]['control_blocks'],
                    'control_ok': self.info[n]['control_ok']}
                   for n in sorted(self.info)]
        dq = {'sources': sources, 'exclusions': []}
        with open(os.path.join(self.out_dir, 'data_quality.json'), 'w',
                  encoding='utf-8') as fh:
            json.dump(dq, fh, sort_keys=True, indent=2)
            fh.write('\n')
        with open(os.path.join(self.out_dir, 'normalized.jsonl'), 'w',
                  encoding='utf-8') as fh:
            pass
        for name in ('product_summary.json', 'region_central.json', 'region_east.json',
                     'region_north.json', 'region_south.json', 'region_west.json',
                     'segment_consumer.json', 'segment_corporate.json',
                     'segment_enterprise.json', 'segment_smb.json'):
            with open(os.path.join(self.out_dir, name), 'w', encoding='utf-8') as fh:
                json.dump({'status': 'HELD'}, fh, sort_keys=True, indent=2)
                fh.write('\n')

    def run(self):
        self.load()
        if self.reasons:
            self.write_held()
            return
        records, excluded = self.grade()
        records = self.apply_caps(records)
        self.write_outputs(records, excluded)


def main(argv=None):
    ap = argparse.ArgumentParser(description='Corvid SLA monthly service-credit close')
    ap.add_argument('data_dir', nargs='?', default='/app/data')
    ap.add_argument('out_dir', nargs='?', default='/app/out')
    ap.add_argument('--prior', dest='prior', default=None)
    args = ap.parse_args(argv)
    close = Close(args.data_dir, args.out_dir, args.prior)
    close.run()
    return 0


if __name__ == '__main__':
    sys.exit(main())

