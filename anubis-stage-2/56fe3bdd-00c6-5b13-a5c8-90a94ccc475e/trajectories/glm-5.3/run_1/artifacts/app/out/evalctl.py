#!/usr/bin/env python3
"""PES-3 review engine: evaluates a delivered estate and writes the eight review artifacts.

Usage: python3 evalctl.py ESTATE_DIR OUT_DIR
"""

import csv
import io
import json
import math
import os
import re
import sqlite3
import sys
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from fractions import Fraction

import openpyxl
import pdfplumber
import tomllib
import yaml
from docx import Document
from lxml import etree

CUTOFF = datetime(2026, 11, 12, 18, 0, 0, tzinfo=timezone.utc)
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
WIN_START = datetime(2026, 9, 14, 0, 0, 0, tzinfo=timezone.utc)
WIN_END = datetime(2026, 11, 9, 0, 0, 0, tzinfo=timezone.utc)

CLASSES = ['pedestrian', 'cyclist', 'wheelchair_user', 'stroller', 'dog', 'car', 'truck',
           'bus', 'motorcycle', 'parked_bicycle', 'traffic_cone', 'bollard']
PROTECTED = ['pedestrian', 'cyclist', 'wheelchair_user', 'stroller']
TARGET_PROTECTED = Fraction(90, 100)
TARGET_OTHER = Fraction(80, 100)

EXCLUSION_ORDER = ['WITHDRAWN', 'OUT_OF_WINDOW', 'CORRUPT', 'PRIVACY_HOLD', 'BOARD_OVERRIDE',
                   'LEAK_EXACT', 'LEAK_NEAR', 'LEAK_SEQUENCE', 'UNLABELED']

SYNONYMS = {
    'frame': 'image_id', 'camera': 'camera_id', 'local_time': 'captured_local',
    'fold': 'dst_fold', 'width_px': 'stored_width', 'height_px': 'stored_height',
    'sequence': 'sequence_id', 'frame_no': 'frame_index', 'hash': 'dhash_u64',
    'status': 'state', 'ann_id': 'annotation_id', 'annotation': 'annotation_id',
    'decided': 'decided_at', 'category': 'label', 'rev': 'revision',
    'img': 'image_id', 'project': 'proj', 'det': 'det_id', 'cls': 'class_index',
    'request': 'request_id', 'item': 'item_id', 'box': 'box_id',
}


# --------------------------------------------------------------------------- helpers


import time as _time
_T0 = [_time.time()]

def _dbg(msg):
    if os.environ.get('EVALCTL_DEBUG'):
        now = _time.time()
        print('[%.1fs] %s' % (now - _T0[0], msg), file=sys.stderr)


def is_utf8(b):
    try:
        b.decode('utf-8')
        return True
    except UnicodeDecodeError:
        return False


def read_text_lines(path):
    data = open(path, 'rb').read()
    if data[:3] == b'\xef\xbb\xbf':
        data = data[3:]
    out = []
    for lb in data.split(b'\n'):
        if lb.endswith(b'\r'):
            lb = lb[:-1]
        out.append(lb.decode('utf-8') if is_utf8(lb) else lb.decode('latin-1'))
    if out and out[-1] == '':
        out.pop()
    return out


IDENT_RE = re.compile(r'[A-Za-z][A-Za-z0-9_]*')


def _cells_of(row):
    vals = []
    for c in row:
        if c is None:
            vals.append('')
        elif isinstance(c, str):
            vals.append(c.strip())
        else:
            vals.append(str(c))
    return vals


class Estate:
    """Column-name vocabulary and file access for one estate."""

    def __init__(self, root):
        self.root = root
        self.vocabulary = set()
        self._rows_cache = {}

    def path(self, name):
        return os.path.join(self.root, name)

    def exists(self, name):
        return os.path.isfile(self.path(name))

    # -- delimited files ----------------------------------------------------

    def delim_rows(self, name, delim):
        """Raw csv rows of a delimited delivery (may contain repeated headers)."""
        if (name, delim) in self._rows_cache:
            return self._rows_cache[(name, delim)]
        lines = read_text_lines(self.path(name))
        rows = list(csv.reader(io.StringIO(''.join(l + '\n' for l in lines)), delimiter=delim))
        self._rows_cache[(name, delim)] = rows
        return rows

    def csv_rows(self, name):
        return self.delim_rows(name, ',')

    def tsv_rows(self, name):
        return self.delim_rows(name, '\t')

    def xlsx_rows(self, name):
        if (name, None) in self._rows_cache:
            return self._rows_cache[(name, None)]
        wb = openpyxl.load_workbook(self.path(name), read_only=True, data_only=True)
        out = {}
        for sn in wb.sheetnames:
            out[sn] = [r for r in wb[sn].iter_rows(values_only=True)]
        wb.close()
        self._rows_cache[(name, None)] = out
        return out

    # -- header detection ---------------------------------------------------

    def is_header_row(self, cells):
        toks = []
        for c in cells:
            if c == '':
                continue
            if not IDENT_RE.fullmatch(c):
                return False
            toks.append(c)
        if len(toks) < 2:
            return False
        for c in toks:
            if c.isdigit():
                return False
            if SYNONYMS.get(c, c) not in self.vocabulary:
                return False
        return True

    def build_vocabulary(self):
        """Learn the column-name vocabulary from the estate's own header rows."""
        cands = []
        for f in sorted(os.listdir(self.root)):
            p = self.path(f)
            if not os.path.isfile(p):
                continue
            if f.endswith('.csv'):
                cands += self.csv_rows(f)
            elif f.endswith('.tsv'):
                cands += self.tsv_rows(f)
            elif f.endswith('.xlsx'):
                for sn, rows in self.xlsx_rows(f).items():
                    cands += rows
        for row in cands:
            cells = _cells_of(row)
            toks = []
            ok = True
            for c in cells:
                if c == '':
                    continue
                if not IDENT_RE.fullmatch(c):
                    ok = False
                    break
                toks.append(c)
            if ok and len(toks) >= 2 and any('_' in t for t in toks):
                for t in toks:
                    self.vocabulary.add(SYNONYMS.get(t, t))
        for cls in CLASSES:
            self.vocabulary.discard(cls)

    def data_records(self, name, delim):
        """(data_rows, header_rows, comment_rows) of a delimited delivery."""
        rows = self.delim_rows(name, delim)
        data, hdrs, comments = [], 0, 0
        for r in rows:
            cells = _cells_of(r)
            if not any(c != '' for c in cells):
                continue
            if cells[0].startswith('#'):
                comments += 1
                continue
            if self.is_header_row(cells):
                hdrs += 1
                continue
            data.append(cells)
        return data, hdrs, comments

    def tabular_dicts(self, name, delim):
        """List of dicts, honouring repeated and reordered header rows."""
        rows = self.delim_rows(name, delim)
        out = []
        header = None
        for r in rows:
            cells = _cells_of(r)
            if not any(c != '' for c in cells):
                continue
            if cells[0].startswith('#'):
                continue
            if self.is_header_row(cells):
                header = [SYNONYMS.get(c, c) for c in cells if c != '']
                continue
            if header is None:
                continue
            d = {}
            for i, h in enumerate(header):
                if i < len(cells):
                    d[h] = cells[i]
                else:
                    d[h] = ''
            out.append(d)
        return out

    def xlsx_dicts(self, name):
        """{sheet: [dicts]} honouring repeated and reordered header rows."""
        out = {}
        for sn, rows in self.xlsx_rows(name).items():
            recs = []
            header = None
            for r in rows:
                cells = _cells_of(r)
                if not any(c != '' for c in cells):
                    continue
                if self.is_header_row(cells):
                    header = [SYNONYMS.get(c, c) for c in cells if c != '']
                    continue
                if header is None:
                    continue
                d = {}
                for i, h in enumerate(header):
                    if i < len(cells):
                        d[h] = cells[i]
                    else:
                        d[h] = ''
                recs.append(d)
            out[sn] = recs
        return out

    # -- other formats ------------------------------------------------------

    def jsonl(self, name):
        out = []
        for line in read_text_lines(self.path(name)):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            out.append(json.loads(line))
        return out

    def json_doc(self, name):
        return json.loads('\n'.join(read_text_lines(self.path(name))))

    def yaml_doc(self, name):
        return yaml.safe_load('\n'.join(read_text_lines(self.path(name))))

    def toml_doc(self, name):
        with open(self.path(name), 'rb') as fh:
            return tomllib.load(fh)

    def ini_doc(self, name):
        sections = {}
        cur = None
        for line in read_text_lines(self.path(name)):
            s = line.strip()
            if not s or s.startswith(';') or s.startswith('#'):
                continue
            m = re.match(r'^\[(.+)\]$', s)
            if m:
                cur = m.group(1).strip()
                sections[cur] = {}
                continue
            if cur is None:
                continue
            if '=' not in s:
                continue
            k, v = s.split('=', 1)
            sections[cur][k.strip()] = v.strip()
        return sections

    def xml_root(self, name):
        return etree.parse(self.path(name)).getroot()

    def parquet_dicts(self, name):
        import pyarrow.parquet as pq
        t = pq.read_table(self.path(name))
        cols = t.to_pydict()
        n = t.num_rows
        keys = list(cols.keys())
        return [{k: cols[k][i] for k in keys} for i in range(n)]

    def sqlite_tables(self, name):
        con = sqlite3.connect(self.path(name))
        try:
            tables = [r[0] for r in con.execute(
                "select name from sqlite_master where type='table'")]
            out = {}
            for t in tables:
                rows = [list(r) for r in con.execute('select * from "%s"' % t)]
                cur = con.execute('select * from "%s"' % t)
                names = [d[0] for d in cur.description]
                out[t] = [dict(zip(names, r)) for r in rows]
            return out
        finally:
            con.close()

    def mbox(self, name):
        out = []
        cur = None
        for line in read_text_lines(self.path(name)):
            if line.startswith('From ') and not line.startswith('From:'):
                if cur is not None:
                    out.append(cur)
                cur = {'headers': [], 'body': []}
                continue
            if cur is None:
                continue
            if not cur['body']:
                if line == '':
                    cur['body'] = ['']
                    continue
                cur['headers'].append(line)
            else:
                cur['body'].append(line)
        if cur is not None:
            out.append(cur)
        return out

    def ics_events(self, name):
        raw = open(self.path(name), 'rb').read()
        text = raw.decode('utf-8', 'replace')
        # unfold continuation lines
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        text = re.sub(r'\n[ \t]', '', text)
        events = []
        cur = None
        for line in text.split('\n'):
            if line == 'BEGIN:VEVENT':
                cur = {}
                continue
            if line == 'END:VEVENT':
                if cur is not None:
                    events.append(cur)
                cur = None
                continue
            if cur is None or ':' not in line:
                continue
            k, v = line.split(':', 1)
            if k == 'DESCRIPTION':
                v = self._ics_unescape(v)
            cur[k] = v
        return events

    @staticmethod
    def _ics_unescape(v):
        v = v.replace('\\n', '\n').replace('\\,', ',').replace('\\;', ';')
        return v

    def pdf_lines(self, name):
        with pdfplumber.open(self.path(name)) as pdf:
            out = []
            for p in pdf.pages:
                out.extend((p.extract_text() or '').split('\n'))
        return out

    def docx_blocks(self, name):
        """Ordered paragraphs and tables of a policy document."""
        doc = Document(self.path(name))
        body = doc.element.body
        from docx.table import Table
        from docx.text.paragraph import Paragraph
        out = []
        for child in body.iterchildren():
            tag = child.tag.split('}')[1]
            if tag == 'p':
                p = Paragraph(child, doc)
                if p.text.strip():
                    out.append(('p', p.text.strip()))
            elif tag == 'tbl':
                t = Table(child, doc)
                rows = []
                for r in t.rows:
                    rows.append([c.text.strip() for c in r.cells])
                out.append(('table', rows))
        return out

    def docx_appendix(self, name):
        """(header, rows) of the Appendix table of a docx document."""
        blocks = self.docx_blocks(name)
        table = None
        for i, (kind, payload) in enumerate(blocks):
            if kind == 'p' and payload.lower().startswith('appendix'):
                for j in range(i + 1, len(blocks)):
                    if blocks[j][0] == 'table':
                        table = blocks[j][1]
                        break
                break
        if table is None:
            for kind, payload in blocks:
                if kind == 'table':
                    table = payload
                    break
        if not table:
            return [], []
        header = table[0]
        return header, table[1:]

    def docx_errata(self, name):
        blocks = self.docx_blocks(name)
        out = []
        started = False
        for kind, payload in blocks:
            if kind == 'p':
                if payload.lower().startswith('errata'):
                    started = True
                continue
            if started and kind == 'table':
                for r in payload[1:]:
                    out.append([c.strip() for c in r])
        return out

    def pdf_register(self, name):
        """(header, rows, errata_paragraphs) of a PDF register."""
        lines = self.pdf_lines(name)
        header = None
        rows = []
        started = False
        errata = []
        i = 0
        n = len(lines)
        while i < n:
            line = lines[i].strip()
            if line.startswith('APPENDIX REGISTER'):
                started = True
                i += 1
                continue
            if started:
                if line.startswith('ERRATA TO THE REGISTER') or line.startswith('END OF REGISTER'):
                    break
                if ' | ' in line:
                    if header is None:
                        header = [c.strip() for c in line.split(' | ')]
                    else:
                        rows.append([c.strip() for c in line.split(' | ')])
            i += 1
        # errata section
        j = 0
        while j < n:
            if lines[j].strip().startswith('ERRATA TO THE REGISTER'):
                for k in range(j + 1, n):
                    s = lines[k].strip()
                    if not s:
                        continue
                    if s.startswith('END OF'):
                        break
                    errata.append(s)
                break
            j += 1
        return header or [], rows, errata

    def md_register(self, name):
        """(header, rows, errata_lines) of a Markdown register."""
        lines = read_text_lines(self.path(name))
        header = None
        rows = []
        errata = []
        in_appendix = False
        in_errata = False

        def is_separator(cells):
            return all(re.fullmatch(r'[\s:\-]*', c) for c in cells)

        for line in lines:
            s = line.strip()
            if s.startswith('## '):
                low = s.lower()
                if low.startswith('## appendix'):
                    in_appendix = True
                    in_errata = False
                elif low.startswith('## errata'):
                    in_errata = True
                else:
                    in_appendix = False
                continue
            if in_errata:
                if s.startswith('|'):
                    cells = [c.strip() for c in s.strip('|').split('|')]
                    if not is_separator(cells):
                        errata.append('|'.join(cells))
                elif s:
                    errata.append(s)
                continue
            if not s.startswith('|'):
                continue
            cells = [c.strip() for c in s.strip('|').split('|')]
            if is_separator(cells):
                continue
            if in_appendix:
                if header is None:
                    header = cells
                else:
                    rows.append(cells)
        return header or [], rows, errata

    def html_tables(self, name):
        text = '\n'.join(read_text_lines(self.path(name)))
        out = []
        for m in re.finditer(r'<table[^>]*>(.*?)</table>', text, re.S):
            body = m.group(1)
            rows = []
            for rm in re.finditer(r'<tr[^>]*>(.*?)</tr>', body, re.S):
                cells = re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>', rm.group(1), re.S)
                rows.append([re.sub(r'<[^>]+>', '', c).strip() for c in cells])
            out.append(rows)
        return out

    def html_headings(self, name):
        text = '\n'.join(read_text_lines(self.path(name)))
        out = []
        for m in re.finditer(r'<h(\d)[^>]*>(.*?)</h\1>', text, re.S):
            out.append((int(m.group(1)), re.sub(r'<[^>]+>', '', m.group(2)).strip()))
        return out

    def html_appendix(self, name):
        """(header, rows) of the Appendix table of an HTML register, plus errata lines."""
        text = '\n'.join(read_text_lines(self.path(name)))
        tabs = self.html_tables(name)
        # locate the heading position of each table
        pos = []
        idx = 0
        for t in tabs:
            start = text.find('<table', idx)
            pos.append(start)
            idx = start + 1
        chosen = None
        for m in re.finditer(r'<h\d[^>]*>(.*?)</h\d>', text, re.S):
            h = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if h.lower().startswith('appendix'):
                # first table after this heading
                for i, p in enumerate(pos):
                    if p > m.start():
                        chosen = tabs[i]
                        break
                break
        if chosen is None:
            chosen = tabs[-1] if tabs else []
        errata = []
        m = re.search(r'<h\d[^>]*>[^<]*Errata[^<]*</h\d>(.*?)</body>', text, re.S)
        if m:
            for li in re.findall(r'<li[^>]*>(.*?)</li>', m.group(1), re.S):
                errata.append(re.sub(r'<[^>]+>', '', li).strip())
        header = chosen[0] if chosen else []
        return header, chosen[1:] if chosen else [], errata


# --------------------------------------------------------------------------- numbers

def parse_number(value):
    """Parse a delivered number into an exact Fraction, or None."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return Fraction(value)
    if isinstance(value, float):
        return Fraction(value)
    s = str(value).strip()
    if s == '':
        return None
    if s.startswith('(') and s.endswith(')'):
        inner = s[1:-1].strip()
        v = parse_number(inner)
        return -v if v is not None else None
    neg = False
    if s.startswith('-'):
        neg = True
        s = s[1:].strip()
    elif s.startswith('+'):
        s = s[1:].strip()
    # decimal separator: the last of point or comma is the decimal separator
    last_dot = s.rfind('.')
    last_comma = s.rfind(',')
    if last_dot >= 0 and last_comma >= 0:
        if last_comma > last_dot:
            s = s.replace('.', '').replace(',', '.')
        else:
            s = s.replace(',', '')
    elif last_comma >= 0:
        # comma only: decimal comma if one comma group of 1-3 digits at the end
        head, _, tail = s.rpartition(',')
        if 1 <= len(tail) <= 3 and head.isdigit() and len(tail) < 3 or (len(tail) == 3 and not head.isdigit()):
            s = s.replace(',', '.')
        else:
            s = s.replace(',', '')
    v = None
    try:
        v = Fraction(s)
    except (ValueError, ZeroDivisionError):
        return None
    return -v if neg else v


def parse_int(value):
    f = parse_number(value)
    if f is None or f.denominator != 1:
        return None
    return int(f)


def fmt6(frac):
    """Format an exact value as a six-decimal string, rounding half to even."""
    if frac is None:
        return 'NA'
    from decimal import Decimal, ROUND_HALF_EVEN, localcontext
    with localcontext() as ctx:
        ctx.prec = 60
        d = Decimal(frac.numerator) / Decimal(frac.denominator)
        q = d.quantize(Decimal('0.000001'), rounding=ROUND_HALF_EVEN)
        return str(q)


def round_half_even(frac):
    """Round an exact Fraction to the nearest integer, halves to even."""
    if frac.denominator == 1:
        return int(frac)
    n = frac.numerator
    d = frac.denominator
    q, r = divmod(n, d)
    twice = 2 * r
    if twice > d or (twice == d and q % 2 == 1):
        q += 1
    return q


def parse_instant(text):
    """Parse a timestamp carrying an offset or Z into an aware datetime."""
    if isinstance(text, datetime):
        return text if text.tzinfo else text.replace(tzinfo=timezone.utc)
    s = str(text).strip()
    if s == '':
        return None
    s = s.replace('T', ' ')
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})[ ](\d{2}):(\d{2})(?::(\d{2})(?:\.(\d+))?)?'
                 r'(Z|[+-]\d{2}:?\d{2})?$', s)
    if not m:
        return None
    y, mo, d, h, mi, sec, frac, off = m.groups()
    micro = int((frac or '0').ljust(6, '0')[:6])
    dt = datetime(int(y), int(mo), int(d), int(h), int(mi), int(sec or 0), micro,
                  tzinfo=timezone.utc)
    if off and off != 'Z':
        sign = 1 if off[0] == '+' else -1
        off2 = off[1:].replace(':', '')
        delta = timedelta(hours=int(off2[:2]), minutes=int(off2[2:4] if len(off2) > 2 else 0))
        dt = dt - sign * delta
    return dt


def excel_serial_to_datetime(serial):
    """1900 date system: serial 1 is 1900-01-01, serial 60 is the nonexistent 1900-02-29."""
    f = parse_number(serial)
    if f is None:
        return None
    days = int(f)
    fracpart = f - days
    if days >= 60:
        days -= 1
    elif days == 60:
        days = 59
    base = datetime(1899, 12, 31, tzinfo=timezone.utc)
    dt = base + timedelta(days=days)
    total = fracpart * 86400
    secs = int(total)
    micro = int((total - secs) * 1000000)
    dt = dt + timedelta(seconds=secs, microseconds=micro)
    return dt


def ts_to_datetime(text):
    """Parse a delivered timestamp value (ISO text or Excel serial)."""
    if isinstance(text, datetime):
        return text if text.tzinfo else text.replace(tzinfo=timezone.utc)
    if isinstance(text, (int, float)):
        return excel_serial_to_datetime(text)
    s = str(text).strip()
    if s == '':
        return None
    if re.match(r'^\d+(\.\d+)?$', s):
        return excel_serial_to_datetime(s)
    return parse_instant(s)


def date_only(text):
    s = str(text).strip()
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})', s)
    if not m:
        return None
    return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)


# --------------------------------------------------------------------------- registers

def strip_md_identifier(cell):
    s = cell.strip()
    if s.startswith('~~') and s.endswith('~~'):
        return s[2:-2].strip(), True
    return s, False


class Reg:
    """A document register with errata applied."""

    def __init__(self, header, rows, errata):
        self.header = [h.strip().lower() for h in header]
        self.rows = [[c for c in r] for r in rows]
        self.errata = [e for e in errata]
        self.base_count = len(self.rows)
        self.apply_errata()

    def col(self, name):
        name = name.strip().lower()
        if name in self.header:
            return self.header.index(name)
        return None

    def get(self, row, name, default=''):
        i = self.col(name)
        if i is None or i >= len(row):
            return default
        return row[i]

    def set(self, row, name, value):
        i = self.col(name)
        if i is None:
            return False
        while len(row) <= i:
            row.append('')
        row[i] = value
        return True

    def dict_rows(self):
        out = []
        for r in self.rows:
            d = {}
            for i, h in enumerate(self.header):
                d[h] = r[i] if i < len(r) else ''
            out.append(d)
        return out

    def apply_errata(self):
        for line in self.errata:
            self._apply_one(line)

    def _apply_one(self, line):
        s = line.strip()
        if not s:
            return
        m = re.match(r'^Row (\d+)\s*\((.*?)\)\s*:\s*(.*?)\s+is\s+(.*?)\.?\s*$', s)
        if m:
            idx = int(m.group(1)) - 1
            field = m.group(3).strip().lower()
            value = clean_errata_value(m.group(4))
            if 0 <= idx < len(self.rows):
                self.set(self.rows[idx], field, value)
            return
        m = re.match(r'^(?:Batch|Image)\s+(\S+)\s*:\s*received at (\S+)\.?\s*$', s)
        if m:
            for r in self.rows:
                if any(c.strip() == m.group(1) for c in r):
                    self.set(r, 'received_at', m.group(2))
            return
        m = re.match(r'^(.*?)\s*:\s*(.*?)\s+is\s+(.*?)\.?\s*$', s)
        if not m:
            return
        prefix = m.group(1).strip()
        field = m.group(2).strip().lower()
        value = clean_errata_value(m.group(3))
        tokens = [t for t in re.split(r'\s+', prefix)
                  if t and t.lower() not in ERRATA_STOPWORDS]
        if not tokens:
            return
        for exact in (True, False):
            hits = []
            for r in self.rows:
                ok = True
                for t in tokens:
                    if exact:
                        if not any(c.strip() == t for c in r):
                            ok = False
                            break
                    else:
                        if not any(t in c for c in r):
                            ok = False
                            break
                if ok:
                    hits.append(r)
            if hits:
                for r in hits:
                    self.set(r, field, value)
                return


ERRATA_STOPWORDS = {'request', 'decision', 'line', 'sequence', 'batch', 'project', 'label',
                    'class', 'knot', 'run', 'image', 'row', 'correction', 'code', 'from',
                    'assigned', 'on', 'the', 'value', 'status', 'node'}


def clean_errata_value(v):
    v = v.strip().rstrip('.').strip()
    return re.sub(r'\s*\([^)]*\)\s*$', '', v).strip()


COORD_FORMAT_SYNONYMS = {
    'x,y,w,h': 'xywh', 'x1,y1,x2,y2': 'xyxy',
    'cx,cy,w,h/norm': 'cxcywh_norm', 'x1,y1,x2,y2/incl': 'xyxy_inclusive',
    'xywh': 'xywh', 'xyxy': 'xyxy', 'cxcywh_norm': 'cxcywh_norm',
    'xyxy_inclusive': 'xyxy_inclusive',
}
VENDOR_DEFAULT_FRAME = {'NL': 'stored', 'KS': 'upright', 'OB': 'upright'}
VENDOR_DEFAULT_FORMAT = {'NL': 'xywh', 'KS': 'cxcywh_norm', 'OB': 'xyxy_inclusive'}


def manifest_partitions(estate, name):
    """Ordered manifest partitions of a file that count."""
    doc = estate.toml_doc('delivery_manifest.toml')
    out = []
    for p in doc.get('partition') or []:
        if p.get('file') != name:
            continue
        if p.get('status') in ('superseded', 'voided', 'withdrawn'):
            continue
        out.append((p.get('part'), p.get('records', 0)))
    return out


def recover_batch02(estate, name, reextract_name):
    """Northlake batch rows with the missing partitions recovered from the re-extract."""
    rows = estate.tabular_dicts(name, ',')
    parts = manifest_partitions(estate, name)
    if not parts or not estate.exists(reextract_name):
        return rows
    alt = estate.tabular_dicts(reextract_name, ',')
    out = []
    pos = 0
    for part, cnt in parts:
        cnt = int(cnt or 0)
        avail = max(0, len(rows) - pos)
        take = min(cnt, avail)
        out.extend(rows[pos:pos + take])
        pos += take
        if take < cnt:
            start = 100 * (int(part) - 1)
            out.extend(alt[start:start + cnt])
    if pos < len(rows):
        out.extend(rows[pos:])
    return out





# --------------------------------------------------------------------------- annotations

class Annotation:
    __slots__ = ('vendor', 'ann_id', 'image', 'batch', 'project', 'coords', 'fmt',
                 'crowd', 'revision', 'deleted', 'ts', 'code', 'label', 'resubmitted')

    def __init__(self):
        self.vendor = ''
        self.ann_id = ''
        self.image = None
        self.batch = ''
        self.project = ''
        self.coords = [None, None, None, None]
        self.fmt = None
        self.crowd = False
        self.revision = 1
        self.deleted = False
        self.ts = None
        self.code = None
        self.label = None
        self.resubmitted = False


class VendorRecords:
    """Every vendor annotation record of an estate."""

    def __init__(self, estate, ids):
        self.e = estate
        self.ids = ids
        self.records = defaultdict(list)   # image -> [Annotation]
        self.delivered_images = set()      # images with a delivered record in a batch that counts

    def build(self, on_time_batches, resub_batches):
        e = self.e
        by_batch = defaultdict(list)
        for rec in self._collect():
            if rec.image is None or not rec.batch:
                continue
            by_batch[rec.batch].append(rec)
        for batch, recs in by_batch.items():
            if batch not in on_time_batches:
                continue
            accepted = batch in resub_batches
            for rec in recs:
                if rec.resubmitted:
                    if accepted:
                        self._add(rec)
                else:
                    self.delivered_images.add(rec.image)
                    if accepted:
                        continue
                    self._add(rec)

    def _add(self, rec):
        self.records[rec.image].append(rec)
        self.delivered_images.add(rec.image)

    def _collect(self):
        e = self.e
        out = []
        out.extend(self._nl())
        out.extend(self._ks())
        out.extend(self._ob())
        return out

    def _nl(self):
        e = self.e
        out = []
        sources = []
        for name in ('nl_boxes_batch01.csv', 'nl_boxes_batch04.csv'):
            if e.exists(name):
                sources.append(e.tabular_dicts(name, ','))
        if e.exists('nl_boxes_batch03.tsv'):
            sources.append(e.tabular_dicts('nl_boxes_batch03.tsv', '\t'))
        if e.exists('nl_boxes_batch02.csv'):
            sources.append(recover_batch02(e, 'nl_boxes_batch02.csv',
                                           'nl_boxes_batch02_reextract.csv'))
        if e.exists('nl_boxes_q3_extra.xlsx'):
            for sn, rows in e.xlsx_dicts('nl_boxes_q3_extra.xlsx').items():
                sources.append(rows)
        for rows in sources:
            for d in rows:
                rec = Annotation()
                rec.vendor = 'NL'
                rec.ann_id = canon_annotation(d.get('annotation_id'))
                rec.image = self.ids.canonical_id(d.get('image_id'))
                rec.batch = canon_batch(d.get('batch_id'))
                rec.project = canon_project(d.get('proj'))
                rec.label = d.get('label')
                rec.coords = [parse_number(d.get('coord_1')), parse_number(d.get('coord_2')),
                              parse_number(d.get('coord_3')), parse_number(d.get('coord_4'))]
                rec.crowd = str(d.get('crowd', '')).strip().upper() == 'Y'
                rev = parse_int(d.get('revision'))
                rec.revision = rev if rev is not None else 1
                rec.deleted = str(d.get('state', '')).strip().lower() == 'deleted'
                out.append(rec)
        return out

    def _ks(self):
        e = self.e
        out = []

        def from_dict(d, resub):
            rec = Annotation()
            rec.vendor = 'KS'
            rec.ann_id = canon_annotation(d.get('id'), 'KS')
            rec.image = self.ids.canonical_id(d.get('image_id') or d.get('img'))
            rec.batch = canon_batch(d.get('batch'))
            rec.project = canon_project(d.get('proj'))
            rec.code = parse_int(d.get('code'))
            unit = str(d.get('bbox_unit', '') or '').strip().lower()
            if d.get('bbox_px') is not None:
                box = d.get('bbox_px')
                rec.fmt = 'px'
            elif d.get('bbox') is not None:
                box = d.get('bbox')
                rec.fmt = 'px' if unit == 'px' else None
            else:
                box = [d.get('b1'), d.get('b2'), d.get('b3'), d.get('b4')]
                rec.fmt = 'px' if unit == 'px' else None
            rec.coords = [parse_number(v) for v in box]
            cr = parse_int(d.get('crowd'))
            rec.crowd = (cr == 1)
            rev = parse_int(d.get('rev'))
            rec.revision = rev if rev is not None else 1
            rec.deleted = str(d.get('state', '')).strip().lower() == 'void'
            ts = parse_number(d.get('ts'))
            if ts is not None:
                if ts < 100000000000:
                    ts = ts * 1000
                rec.ts = EPOCH + timedelta(milliseconds=ts.numerator // ts.denominator)
            rec.resubmitted = resub
            out.append(rec)

        for name in ('ks_boxes_part1.jsonl', 'ks_boxes_part2.jsonl'):
            if e.exists(name):
                for d in e.jsonl(name):
                    from_dict(d, False)
        for name in ('ks_boxes_part3.json', 'ks_boxes_part5.json', 'ks_boxes_resubmitted.json'):
            if not e.exists(name):
                continue
            resub = name.endswith('resubmitted.json')
            for d in e.json_doc(name).get('records') or []:
                from_dict(d, resub)
        for name in ('ks_boxes_part4.parquet',):
            if e.exists(name):
                for d in e.parquet_dicts(name):
                    from_dict(d, False)
        for name in ('ks_boxes_part6.csv',):
            if e.exists(name):
                for d in e.tabular_dicts(name, ','):
                    from_dict(d, False)
        return out

    def _ob(self):
        e = self.e
        out = []
        for name in ('ob_boxes_east.xml', 'ob_boxes_west.xml', 'ob_boxes_resubmitted.xml'):
            if not e.exists(name):
                continue
            resub = name.endswith('resubmitted.xml')
            root = e.xml_root(name)
            for obj in root.iter('object'):
                rec = Annotation()
                rec.vendor = 'OB'
                rec.ann_id = canon_annotation(obj.get('id'))
                rec.image = self.ids.canonical_id(obj.get('image'))
                rec.batch = canon_batch(obj.get('batch'))
                rec.project = canon_project(obj.get('project'))
                rec.label = obj.findtext('name')
                bb = obj.find('bndbox')
                if bb is not None:
                    rec.coords = [parse_number(bb.get('c1')), parse_number(bb.get('c2')),
                                  parse_number(bb.get('c3')), parse_number(bb.get('c4'))]
                cr = parse_int(obj.findtext('crowd'))
                rec.crowd = (cr == 1)
                rev = parse_int(obj.findtext('revision'))
                rec.revision = rev if rev is not None else 1
                rec.deleted = parse_int(obj.findtext('deleted')) == 1
                rec.resubmitted = resub
                out.append(rec)
        return out


# --------------------------------------------------------------------------- geometry

def upright_from_stored(box, orientation, W, H):
    """Turn a stored-frame box upright (exact Fractions in, exact Fractions out)."""
    x1, y1, x2, y2 = box
    if orientation == 3:
        return (Fraction(W) - x2, Fraction(H) - y2, Fraction(W) - x1, Fraction(H) - y1)
    if orientation == 6:
        return (Fraction(H) - y2, x1, Fraction(H) - y1, x2)
    if orientation == 8:
        return (y1, Fraction(W) - x2, y2, Fraction(W) - x1)
    return (x1, y1, x2, y2)


def raw_box_from_format(coords, fmt, W, H):
    """x1,y1,x2,y2 (possibly fractional) from a vendor box in the given format."""
    a, b, c, d = coords
    if fmt == 'xywh':
        return (a, b, a + c, b + d)
    if fmt == 'xyxy':
        return (a, b, c, d)
    if fmt == 'xyxy_inclusive':
        return (a, b, c + 1, d + 1)
    if fmt == 'cxcywh_norm':
        cx, cy, w, h = a, b, c, d
        return (cx * W - w * W / 2, cy * H - h * H / 2, cx * W + w * W / 2, cy * H + h * H / 2)
    if fmt == 'px':
        cx, cy, w, h = a, b, c, d
        return (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
    return None


def canonical_box(raw, orientation, W, H, upright):
    """Exact raw box (x1,y1,x2,y2) to integer canonical upright box, or None."""
    if raw is None or any(v is None for v in raw):
        return None
    x1, y1, x2, y2 = raw
    if not upright:
        x1, y1, x2, y2 = upright_from_stored((x1, y1, x2, y2), orientation, W, H)
    cx1 = round_half_even(x1)
    cy1 = round_half_even(y1)
    cx2 = round_half_even(x2)
    cy2 = round_half_even(y2)
    cx1 = max(0, min(W, cx1))
    cy1 = max(0, min(H, cy1))
    cx2 = max(0, min(W, cx2))
    cy2 = max(0, min(H, cy2))
    if cx2 <= cx1 or cy2 <= cy1:
        return None
    return (cx1, cy1, cx2, cy2)


# --------------------------------------------------------------------------- ground truth

class GT:
    __slots__ = ('gt_id', 'cls', 'x1', 'y1', 'x2', 'y2', 'ignore', 'source')

    def __init__(self, gt_id, cls, box, ignore, source):
        self.gt_id = gt_id
        self.cls = cls
        self.x1, self.y1, self.x2, self.y2 = box
        self.ignore = ignore
        self.source = source


def label_class(rec, cfg):
    """(class, disposition) of a vendor record."""
    if rec.vendor == 'NL':
        return cfg['nl_labels'].get((rec.project, rec.label), (None, None))
    if rec.vendor == 'KS':
        best = None
        for proj, code, cls, disp, vf, vt in cfg['ks_codebook']:
            if proj != rec.project or code != rec.code:
                continue
            if vf is None:
                vf = EPOCH
            if rec.ts is None or not (vf <= rec.ts and (vt is None or rec.ts < vt)):
                continue
            if best is None or vf > best[0]:
                best = (vf, cls, disp)
        if best is None:
            return None, None
        return best[1], best[2]
    if rec.vendor == 'OB':
        return cfg['ob_aliases'].get((rec.project, rec.label), (None, None))
    return None, None


def build_ground_truth(ident, cfg):
    """Ground truth of one image: list of GT."""
    campaign = cfg['campaign'].get(ident)
    if campaign:
        out = []
        for box_id, d in campaign:
            cls = str(d.get('class', '')).strip()
            coords = [parse_number(d.get('x1')), parse_number(d.get('y1')),
                      parse_number(d.get('x2')), parse_number(d.get('y2'))]
            box = canonical_box(coords, cfg['orientation'], cfg['W'], cfg['H'], True)
            if box is None:
                continue
            cr = parse_int(d.get('crowd'))
            area = (box[2] - box[0]) * (box[3] - box[1])
            ignore = (cr == 1) or area < 64
            out.append(GT(box_id, cls, box, ignore, 'CAMPAIGN'))
        return out
    recs = cfg['records'].get(ident) or []
    if not recs:
        return []
    by_ann = defaultdict(list)
    for rec in recs:
        if rec.vendor != cfg['vendor']:
            continue
        by_ann[rec.ann_id].append(rec)
    err_by_ann = defaultdict(list)
    for ann, action, value in cfg['errata']:
        err_by_ann[ann].append((action, value))
    boxes = []
    for ann_id, lst in by_ann.items():
        usable = [r for r in lst if (ann_id, r.revision) not in cfg['rejected']]
        if not usable:
            continue
        rec = max(usable, key=lambda r: r.revision)
        if rec.deleted:
            continue
        cls, disp = label_class(rec, cfg)
        coords = rec.coords
        upright_override = False
        if ann_id in err_by_ann:
            for action, value in err_by_ann[ann_id]:
                if action == 'VOID':
                    rec = None
                    break
                if action == 'RECLASS':
                    cls = value
                elif action == 'REBOX':
                    parts = [parse_number(v) for v in value.split(',')]
                    if len(parts) == 4 and all(v is not None for v in parts):
                        coords = parts
                        upright_override = True
            if rec is None:
                continue
        if cls is None or disp == 'drop':
            continue
        batch = cfg['batches'].get(rec.batch)
        fmt = batch[1] if batch else None
        frame = batch[2] if batch else None
        fmt = COORD_FORMAT_SYNONYMS.get(fmt, fmt)
        if fmt is None:
            fmt = VENDOR_DEFAULT_FORMAT.get(rec.vendor)
        if frame in (None, '', '-'):
            frame = VENDOR_DEFAULT_FRAME.get(rec.vendor, 'upright')
        upright = (frame == 'upright')
        if upright_override:
            raw = tuple(coords)
            upright = True
        else:
            raw = raw_box_from_format(coords, rec.fmt or fmt, cfg['W'], cfg['H'])
        if raw is None:
            raw = raw_box_from_format(coords, fmt, cfg['W'], cfg['H'])
        if raw is None:
            continue
        box = canonical_box(raw, cfg['orientation'], cfg['W'], cfg['H'], upright)
        if box is None:
            continue
        area = (box[2] - box[0]) * (box[3] - box[1])
        ignore = (disp == 'ignore') or rec.crowd or area < 64
        boxes.append(GT(ann_id, cls, box, ignore, rec.vendor))
    return boxes


class IdNormalizer:
    def __init__(self, estate):
        ini = estate.ini_doc('image_id_aliases.ini')
        self.homoglyphs = {}
        for key, val in ini.get('homoglyphs', {}).items():
            m = re.match(r'^U\+([0-9A-Fa-f]+)\s*$', key.strip())
            if m:
                self.homoglyphs[chr(int(m.group(1), 16))] = val.strip()
        self.aliases = {}
        self.aliases_flat = {}
        for k, v in ini.get('aliases', {}).items():
            key = k.strip()
            self.aliases[key] = (v.split(';')[0]).strip()
            self.aliases_flat[key.replace('-', '').replace('_', '')] = (v.split(';')[0]).strip()

    def _shape(self, raw):
        s = unicodedata.normalize('NFKC', str(raw))
        s = s.strip()
        for ch, rep in self.homoglyphs.items():
            s = s.replace(ch, rep)
        return s.upper()

    def canonical_id(self, raw):
        """Canonical IMG identifier, or None when it resolves to nothing known."""
        if raw is None:
            return None
        s = self._shape(raw)
        if s.startswith('IMG'):
            s = s.replace('-', '').replace('_', '')
            digits = s[3:]
            if not digits.isdigit():
                return None
            return 'IMG' + digits.zfill(7)
        if s.startswith('LGC'):
            seen = set()
            cur = s
            while cur.startswith('LGC') and cur not in seen:
                seen.add(cur)
                flat = cur.replace('-', '').replace('_', '')
                nxt = self.aliases.get(cur)
                if nxt is None:
                    nxt = self.aliases_flat.get(flat)
                if nxt is None:
                    return None
                cur = self._shape(nxt)
            if cur.startswith('IMG') and cur[3:].isdigit():
                return 'IMG' + cur[3:].zfill(7)
            return None
        return None

    def raw_alias_value(self, raw):
        """Resolve an identifier that is already canonical-shaped, without LGC lookup."""
        return self.canonical_id(raw)


def canon_camera(raw):
    s = str(raw).strip().upper()
    s = s.replace(' ', '-').replace('_', '-')
    return s


def canon_sequence(raw):
    s = str(raw).strip().upper()
    s = s.replace('-', '').replace('_', '')
    if s.startswith('SEQ'):
        digits = s[3:]
    else:
        digits = s
    if not digits.isdigit():
        return None
    return 'SEQ-' + digits.zfill(5)


def canon_batch(raw):
    return str(raw).strip().upper()


def canon_project(raw):
    return str(raw).strip().upper()


def canon_annotation(raw, vendor=None):
    s = str(raw).strip().upper()
    if s == '':
        return None
    if s.isdigit():
        if vendor == 'KS':
            return 'KS-' + s.zfill(7)
        return s
    m = re.match(r'^OB[:\-]?(\d+)$', s)
    if m:
        return 'OB-' + m.group(1).zfill(7)
    m = re.match(r'^KS[:\-]?(\d+)$', s)
    if m:
        return 'KS-' + m.group(1).zfill(7)
    return s


def canon_det_id(raw):
    s = str(raw).strip().upper()
    s = re.sub(r'^D+', '', s)
    s = s.lstrip('0')
    if s == '' or not s.isdigit():
        return None
    return int(s)


# --------------------------------------------------------------------------- freeze

def parse_freeze(estate, ids):
    """Frozen candidate register: (header, rows, errata) with errata applied."""
    header, rows, errata = estate.md_register('eval_standard_v3.md')
    ident_idx = 0
    # errata of the register: a row listing X is a transcription error; the frozen image is Y
    replacements = {}
    for line in errata:
        m = re.match(r'^Row listing (.+?)\.?\s+is a transcription error; the frozen image is (.+?)\.?\s*$',
                     line.strip())
        if m:
            a = ids.canonical_id(m.group(1).strip())
            b = ids.canonical_id(m.group(2).strip())
            if a is not None:
                replacements[a] = b
    out = []
    for r in rows:
        while len(r) < len(header):
            r = r + ['']
        raw_ident, is_void = strip_md_identifier(r[ident_idx])
        ident = ids.canonical_id(raw_ident)
        if is_void:
            continue
        if ident is None:
            continue
        if ident in replacements:
            ident = replacements[ident]
        out.append(ident)
    out = list(dict.fromkeys(out))
    # Appendix A' of the PES-3.1 draft: ratified rows apply in table order
    if estate.exists('eval_standard_v3_1_draft.md'):
        h2, rows2, err2 = estate.md_register('eval_standard_v3_1_draft.md')
        action_rows = []
        for r in rows2:
            while len(r) < len(h2):
                r = r + ['']
            raw_ident, is_void = strip_md_identifier(r[0])
            ident = ids.canonical_id(raw_ident)
            if ident is None:
                continue
            action = r[1].strip().lower()
            status = r[2].strip().lower() if len(r) > 2 else ''
            action_rows.append((ident, action, status))
        for i, e in enumerate(err2):
            m = re.match(r'^Row (\d+) \(([^)]+)\): action is (\S+)\.?$', ' '.join(e).strip())
            if not m:
                continue
            rowno = int(m.group(1)) - 1
            if 0 <= rowno < len(action_rows):
                ident, _, status = action_rows[rowno]
                action_rows[rowno] = (ident, m.group(3), status)
        present = set(out)
        for ident, action, status in action_rows:
            if status != 'ratified':
                continue
            if action == 'add':
                present.add(ident)
            elif action == 'remove':
                present.discard(ident)
        out = [i for i in out if i in present] + [i for i in present if i not in set(out)]
    return out


# --------------------------------------------------------------------------- capture

def load_frames_index(estate, ids):
    """image_id -> (camera_id, captured_local, dst_fold)."""
    primary_cams = set()
    recs = {}
    for name in ('frames_index_east.csv', 'frames_index_west.csv'):
        if not estate.exists(name):
            continue
        for d in estate.tabular_dicts(name, ','):
            ident = ids.canonical_id(d.get('image_id', ''))
            if ident is None:
                continue
            cam = canon_camera(d.get('camera_id', ''))
            local = d.get('captured_local', '')
            fold = d.get('dst_fold', '')
            primary_cams.add(cam)
            recs[ident] = (cam, local, fold)
    if estate.exists('frames_index_east_v2.csv'):
        extra = {}
        for d in estate.tabular_dicts('frames_index_east_v2.csv', ','):
            ident = ids.canonical_id(d.get('image_id', ''))
            if ident is None:
                continue
            cam = canon_camera(d.get('camera_id', ''))
            if cam in primary_cams:
                continue
            if str(d.get('captured_utc', '')).strip() == '':
                continue
            extra[ident] = (cam, d.get('captured_local', ''), d.get('dst_fold', ''))
        for k, v in extra.items():
            if k not in recs:
                recs[k] = v
    return recs


def load_roster(estate):
    """(camera, date) -> roster entry, main roster authoritative per camera."""
    main_by_cam = defaultdict(dict)
    for entry in estate.yaml_doc('camera_deployment_roster.yaml').get('roster') or []:
        cam = canon_camera(entry.get('camera', ''))
        d = entry.get('date')
        if isinstance(d, str):
            d = date_only(d)
        if d is None or not cam:
            continue
        key = (d.date() if isinstance(d, datetime) else d)
        main_by_cam[cam][key] = entry
    combined = {}
    for cam, bydate in main_by_cam.items():
        for k, v in bydate.items():
            combined[(cam, k)] = v
    if estate.exists('camera_deployment_roster_ops.yaml'):
        ops_by_cam = defaultdict(dict)
        for entry in estate.yaml_doc('camera_deployment_roster_ops.yaml').get('roster') or []:
            if entry.get('active') is False:
                continue
            cam = canon_camera(entry.get('camera', ''))
            d = entry.get('date')
            if isinstance(d, str):
                d = date_only(d)
            if d is None or not cam:
                continue
            key = (d.date() if isinstance(d, datetime) else d)
            ops_by_cam[cam][key] = entry
        for cam, bydate in ops_by_cam.items():
            if cam in main_by_cam:
                continue
            for k, v in bydate.items():
                combined[(cam, k)] = v
    return combined



def parse_offset(text):
    """Offset string like +08:00 into a timedelta."""
    s = str(text).strip()
    m = re.match(r'^([+-])(\d{2}):?(\d{2})$', s)
    if not m:
        return timedelta(0)
    sign = 1 if m.group(1) == '+' else -1
    return sign * timedelta(hours=int(m.group(2)), minutes=int(m.group(3)))


def parse_local_datetime(text):
    """A wall-clock timestamp without offset: returns naive datetime."""
    s = str(text).strip().replace('T', ' ')
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})[ ](\d{2}):(\d{2}):(\d{2})$', s)
    if not m:
        m2 = re.match(r'^(\d{4})-(\d{2})-(\d{2})[ ](\d{2}):(\d{2})$', s)
        if m2:
            return datetime(int(m2.group(1)), int(m2.group(2)), int(m2.group(3)),
                            int(m2.group(4)), int(m2.group(5)))
        return None
    return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                    int(m.group(4)), int(m.group(5)), int(m.group(6)))


def parse_clock_time(text):
    s = str(text).strip()
    m = re.match(r'^(\d{2}):(\d{2}):(\d{2})$', s)
    if not m:
        m = re.match(r'^(\d{2}):(\d{2})$', s)
        if m:
            return int(m.group(1)), int(m.group(2)), 0
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


class ClockSync:
    """Camera clock skew events from the sync calendar."""

    def __init__(self, estate):
        self.by_camera = defaultdict(list)
        for ev in estate.ics_events('camera_clock_sync.ics'):
            status = ev.get('STATUS', '')
            if status.upper() != 'CONFIRMED':
                continue
            summary = ev.get('SUMMARY', '')
            m = re.search(r'CAM-[A-Z0-9]+', summary)
            if not m:
                continue
            cam = canon_camera(m.group(0))
            start = parse_dt_compact(ev.get('DTSTART'))
            end = parse_dt_compact(ev.get('DTEND'))
            if start is None or end is None:
                continue
            desc = ev.get('DESCRIPTION', '')
            skew = None
            m2 = re.search(r'skew_ms\s*=\s*(-?[\d.,]+)', desc)
            if m2:
                skew = parse_number(m2.group(1))
            else:
                m2 = re.search(r'skew_s\s*=\s*(-?[\d.,]+)', desc)
                if m2:
                    skew = parse_number(m2.group(1))
            if skew is None:
                skew = Fraction(0)
            self.by_camera[cam].append((start, end, skew))

    def skew_for(self, camera, instant):
        for start, end, skew in self.by_camera.get(camera, ()):
            if start <= instant < end:
                return skew
        return Fraction(0)


def parse_dt_compact(text):
    """Parse an iCalendar UTC datetime like 20260910T000000Z."""
    s = str(text).strip()
    m = re.match(r'^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z$', s)
    if not m:
        m = re.match(r'^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})$', s)
        if m:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                            int(m.group(4)), int(m.group(5)), int(m.group(6)), tzinfo=timezone.utc)
        return parse_instant(s)
    return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                    int(m.group(4)), int(m.group(5)), int(m.group(6)), tzinfo=timezone.utc)


def subtract_seconds(dt, frac):
    """Subtract an exact number of seconds from an aware datetime."""
    micro = frac * 1000000
    usec = int(micro.numerator // micro.denominator)
    rem = micro - usec
    if rem >= Fraction(1, 2):
        usec += 1
    return dt - timedelta(microseconds=usec)


def corrected_capture(rec, roster, sync):
    """(captured_utc datetime, local_date) for a frames-index record."""
    cam, local, fold = rec
    naive = parse_local_datetime(local)
    if naive is None:
        return None, None
    entry = roster.get((cam, naive.date()))
    if entry is None:
        return None, naive.date()
    before = parse_offset(entry.get('utc_offset', '+00:00'))
    after = parse_offset(entry.get('offset_after', entry.get('utc_offset', '+00:00')))
    sw = entry.get('switch_local')
    offset = before
    if sw:
        swt = parse_clock_time(sw)
        if swt is not None:
            switch_dt = naive.replace(hour=swt[0], minute=swt[1], second=swt[2], microsecond=0)
            if naive >= switch_dt:
                offset = after
            elif switch_dt - timedelta(hours=1) <= naive < switch_dt:
                # the hour before the switch occurs twice when clocks went back
                if str(fold).strip() == '1':
                    offset = after
    camera_instant = (naive - offset).replace(tzinfo=timezone.utc)
    skew = sync.skew_for(cam, camera_instant)
    corrected = subtract_seconds(camera_instant, skew)
    return corrected, naive.date()


# --------------------------------------------------------------------------- catalogues

class Catalogues:
    """Every lookup the review needs, built once from the estate."""

    def __init__(self, estate, ids):
        self.e = estate
        self.ids = ids

    # -- sequence membership ------------------------------------------------

    def sequences(self):
        seqs = {}
        if self.e.exists('sequence_membership.xlsx'):
            for sn, rows in self.e.xlsx_dicts('sequence_membership.xlsx').items():
                for d in rows:
                    ident = self.ids.canonical_id(d.get('image_id', ''))
                    seq = canon_sequence(d.get('sequence_id', ''))
                    if ident is None or seq is None:
                        continue
                    seqs[ident] = seq
        return seqs

    # -- integrity audit ----------------------------------------------------

    def integrity(self):
        out = {}
        header, rows, errata = self.e.pdf_register('frame_integrity_audit.pdf')
        reg = Reg(header, rows, errata)
        for r in reg.rows:
            ident = self.ids.canonical_id(reg.get(r, 'image_id'))
            if ident is None:
                continue
            status = reg.get(r, 'status').strip().upper()
            if status == 'N/A':
                status = 'PASS'
            dw = parse_int(reg.get(r, 'decoded_w'))
            dh = parse_int(reg.get(r, 'decoded_h'))
            out[ident] = (status, dw, dh)
        return out

    # -- geometry -----------------------------------------------------------

    def geometry(self, integrity):
        out = {}
        for d in self.e.tabular_dicts('frame_geometry.tsv', '\t'):
            ident = self.ids.canonical_id(d.get('image_id', ''))
            if ident is None:
                continue
            w = parse_int(d.get('stored_width'))
            h = parse_int(d.get('stored_height'))
            scale = parse_number(d.get('dim_scale'))
            if scale is None:
                scale = Fraction(1)
            aud = integrity.get(ident)
            if (w == 0 and h == 0) or (aud is not None and aud[0] == 'REENCODED'):
                if aud is not None and aud[1] is not None and aud[2] is not None:
                    w, h = aud[1], aud[2]
                else:
                    w, h = 0, 0
            if w is None or h is None:
                w, h = 0, 0
            sw = round_half_even(Fraction(w) * scale)
            sh = round_half_even(Fraction(h) * scale)
            out[ident] = (sw, sh)
        return out

    # -- orientation --------------------------------------------------------

    def orientation(self):
        base = {}
        for d in self.e.jsonl('exif_orientation_scan.jsonl'):
            ident = self.ids.canonical_id(d.get('image', d.get('image_id')))
            if ident is None:
                continue
            code = parse_int(d.get('exif_orientation'))
            if code is None:
                code = 1
            if code == 0:
                code = 1
            base[ident] = code
        header, rows, errata = self.e.pdf_register('orientation_corrections.pdf')
        reg = Reg(header, rows, errata)
        best = {}
        for r in reg.rows:
            status = reg.get(r, 'status').strip().lower()
            if status != 'confirmed':
                continue
            decided = parse_instant(reg.get(r, 'decided_at'))
            if decided is None or decided > CUTOFF:
                continue
            ident = self.ids.canonical_id(reg.get(r, 'image_id'))
            if ident is None:
                continue
            code = parse_int(reg.get(r, 'orientation'))
            if code is None:
                continue
            key = (decided, reg.get(r, 'correction_id').strip())
            if ident not in best or key > best[ident][0]:
                best[ident] = (key, code)
        for ident, (_, code) in best.items():
            base[ident] = code
        return base

    # -- run registry -------------------------------------------------------

    def run_registry(self):
        e = self.e
        runs = {}
        labels = defaultdict(dict)
        if e.exists('inference_run_registry.html'):
            tabs = e.html_tables('inference_run_registry.html')
            for t in tabs:
                if not t:
                    continue
                hdr = [c.strip().lower() for c in t[0]]
                if 'run_id' in hdr and 'status' in hdr and 'model' in hdr:
                    for r in t[1:]:
                        d = dict(zip(hdr, r))
                        rid = d.get('run_id', '').strip().upper()
                        if rid:
                            runs[rid] = {
                                'run_id': rid,
                                'model': d.get('model', '').strip(),
                                'status': d.get('status', '').strip().lower(),
                                'input_size': parse_int(d.get('input_size')),
                                'score_threshold': parse_number(d.get('score_threshold')),
                                'nms_iou': parse_number(d.get('nms_iou')),
                                'max_detections': parse_int(d.get('max_detections')),
                                'training_index': d.get('training_index', '').strip().lower(),
                            }
                elif 'run_id' in hdr and 'class_index' in hdr:
                    for r in t[1:]:
                        d = dict(zip(hdr, r))
                        rid = d.get('run_id', '').strip().upper()
                        idx = parse_int(d.get('class_index'))
                        if rid and idx is not None:
                            labels[rid][idx] = d.get('label', '').strip()
        nodeassign = {}
        for name in ('inference_run_registry.html',):
            if not e.exists(name):
                continue
            header, rows, errata = e.html_appendix(name)
            reg = Reg(header, rows, errata)
            for r in reg.rows:
                rid = reg.get(r, 'run_id').strip().upper()
                seq = canon_sequence(reg.get(r, 'sequence_id'))
                node = reg.get(r, 'node').strip().lower()
                if rid and seq:
                    nodeassign[(rid, seq)] = node
        return runs, labels, nodeassign

    def run_registry_mirror(self):
        e = self.e
        if not e.exists('inference_run_registry_mirror.html'):
            return {}
        header, rows, errata = e.html_appendix('inference_run_registry_mirror.html')
        reg = Reg(header, rows, errata)
        assign = {}
        for r in reg.rows:
            rid = reg.get(r, 'run_id').strip().upper()
            seq = canon_sequence(reg.get(r, 'sequence_id'))
            node = reg.get(r, 'node').strip().lower()
            if rid and seq:
                assign[(rid, seq)] = node
        return assign

    # -- hashes and leakage -------------------------------------------------

    @staticmethod
    def _hash_from_value(raw):
        """64-bit unsigned hash from hex or decimal text."""
        if raw is None:
            return None
        s = str(raw).strip().lower()
        if s == '':
            return None
        if s.startswith('0x') or s.startswith('x'):
            s = s[2:] if s.startswith('0x') else s[1:]
            if s == '' or not re.fullmatch(r'[0-9a-f]+', s):
                return None
            return int(s, 16)
        if re.fullmatch(r'[0-9a-f]+', s) and any(c in 'abcdef' for c in s):
            return int(s, 16)
        if s.isdigit():
            return int(s)
        if re.fullmatch(r'[0-9a-f]+', s):
            return int(s, 16)
        return None

    def training_index(self, index_name):
        """Set of 64-bit training hashes of a named index."""
        e = self.e
        out = set()
        name = index_name.strip().lower()

        def add(h, tag, purged):
            if h is None or h == 0:
                return
            if purged:
                return
            if str(tag).strip().lower() != name:
                return
            out.add(h)

        if name == 'v7-train':
            if e.exists('train_hash_index_a.parquet'):
                for d in e.parquet_dicts('train_hash_index_a.parquet'):
                    add(self._hash_from_value(d.get('dhash_hex')), d.get('set_tag'),
                        str(d.get('status', '')).strip().lower() == 'purged')
            if e.exists('train_hash_index_b.csv'):
                for d in e.tabular_dicts('train_hash_index_b.csv', ','):
                    state = str(d.get('state', '')).strip().upper()
                    add(self._hash_from_value(d.get('dhash_u64')), d.get('set_tag'), state == 'P')
            if e.exists('train_hash_index_c.db'):
                for tab in e.sqlite_tables('train_hash_index_c.db').values():
                    for d in tab:
                        add(self._hash_from_value(d.get('h')), d.get('set_tag'),
                            str(d.get('purged')).strip() in ('1', 'True', 'true'))
            if e.exists('train_hash_index_d.txt'):
                for line in read_text_lines(e.path('train_hash_index_d.txt')):
                    s = line.rstrip('\n')
                    if not s.strip() or s.lstrip().startswith('#'):
                        continue
                    hx = s[0:16].strip()
                    tag = s[17:25].strip()
                    flag = (s[26:27] or '').strip()
                    add(self._hash_from_value(hx), tag, flag.upper() == 'P')
            if e.exists('train_hash_index_e.jsonl'):
                for d in e.jsonl('train_hash_index_e.jsonl'):
                    raw = d.get('h')
                    if raw is None:
                        raw = d.get('h_dec')
                    add(self._hash_from_value(raw), d.get('tag'), bool(d.get('purged')))
            if e.exists('train_hash_index_h.txt'):
                for line in read_text_lines(e.path('train_hash_index_h.txt')):
                    s = line.rstrip('\n')
                    if not s.strip() or s.lstrip().startswith('#'):
                        continue
                    dec = s[0:20].strip()
                    tag = s[21:29].strip()
                    flag = (s[30:31] or '').strip()
                    add(self._hash_from_value(dec), tag, flag.upper() == 'P')
            if e.exists('train_hash_index_f_dedup.parquet'):
                for d in e.parquet_dicts('train_hash_index_f_dedup.parquet'):
                    if str(d.get('source_shard', '')).strip().lower() != 'g':
                        continue
                    add(self._hash_from_value(d.get('dhash_hex')), name, bool(d.get('purged')))
        elif e.exists('train_hash_index_legacy.txt'):
            for line in read_text_lines(e.path('train_hash_index_legacy.txt')):
                s = line.rstrip('\n')
                if not s.strip() or s.lstrip().startswith('#'):
                    continue
                hx = s[0:16].strip()
                tag = s[17:29].strip()
                flag = (s[30:31] or '').strip()
                add(self._hash_from_value(hx), tag, flag.upper() == 'P')
        return out

    def candidate_hashes(self):
        e = self.e
        out = {}
        if not e.exists('frame_dhash.parquet'):
            return out
        for d in e.parquet_dicts('frame_dhash.parquet'):
            ident = self.ids.canonical_id(d.get('image_id'))
            if ident is None:
                continue
            v = d.get('dhash')
            if v is None:
                continue
            u = int(v) & 0xFFFFFFFFFFFFFFFF
            if str(d.get('byte_order', '')).strip().lower() == 'be':
                b = u.to_bytes(8, 'big')
                u = int.from_bytes(b[::-1], 'big')
            out[ident] = u
        return out

    def waivers(self):
        e = self.e
        out = {}
        if not e.exists('leakage_waivers.json'):
            return out
        doc = e.json_doc('leakage_waivers.json')
        for w in doc.get('waivers') or []:
            ident = self.ids.canonical_id(w.get('image'))
            h = self._hash_from_value(w.get('train_dhash'))
            if ident is None or h is None:
                continue
            out.setdefault((ident, h), []).append(w)
        granted = set()
        for (ident, h), lst in out.items():
            best = None
            for w in lst:
                at = parse_instant(w.get('decided_at'))
                if at is None:
                    continue
                wid = str(w.get('waiver_id', ''))
                key = (at, wid)
                if best is None or key > best[0]:
                    best = (key, w)
            if best is None:
                continue
            w = best[1]
            if str(w.get('status', '')).strip().lower() != 'granted':
                continue
            exp = w.get('expires_at')
            if exp is not None:
                e_at = parse_instant(exp)
                if e_at is not None and e_at <= CUTOFF:
                    continue
            granted.add((ident, h))
        return granted

    def trained_sequences(self):
        e = self.e
        out = {}
        header, rows, errata = e.pdf_register('training_sequence_register.pdf')
        reg = Reg(header, rows, errata)
        for r in reg.rows:
            seq = canon_sequence(reg.get(r, 'sequence_id'))
            status = reg.get(r, 'status').strip().lower()
            idx = reg.get(r, 'training_index').strip().lower()
            if seq is None:
                continue
            out[seq] = (status, idx)
        return out

    # -- vendor / annotation registers --------------------------------------

    def vendor_assignment(self):
        header, rows = self.e.docx_appendix('data_authority_policy.docx')
        reg = Reg(header, rows, self.e.docx_errata('data_authority_policy.docx'))
        out = {}
        for r in reg.rows:
            ident = self.ids.canonical_id(reg.get(r, 'image_id'))
            vendor = reg.get(r, 'vendor').strip().upper()
            when = date_only(reg.get(r, 'assigned_on'))
            if ident is None or not vendor:
                continue
            key = when or datetime(1970, 1, 1, tzinfo=timezone.utc)
            if ident not in out or key > out[ident][0]:
                out[ident] = (key, vendor)
        return {k: v[1] for k, v in out.items()}

    def batch_receipts(self):
        header, rows = self.e.docx_appendix('vendor_batch_receipts.docx')
        reg = Reg(header, rows, self.e.docx_errata('vendor_batch_receipts.docx'))
        out = {}
        for r in reg.rows:
            b = canon_batch(reg.get(r, 'batch_id'))
            when = parse_instant(reg.get(r, 'received_at'))
            if not b:
                continue
            out[b] = when
        return out

    def batch_conventions(self):
        e = self.e
        header, rows = e.docx_appendix('annotation_batch_conventions.docx')
        errata = e.docx_errata('annotation_batch_conventions.docx')
        reg = Reg(header, rows, errata)
        for line in errata:
            m = re.match(r'^Batch\s+(\S+)\s+was delivered as\s+(\S+)\s+in the\s+(\S+)\s+frame', line.strip())
            if not m:
                continue
            bid = canon_batch(m.group(1))
            fmt = m.group(2).strip().lower()
            frame = m.group(3).strip().lower()
            for r in reg.rows:
                if any(c.strip().upper() == bid for c in r):
                    reg.set(r, 'coord_format', fmt)
                    reg.set(r, 'frame', frame)
        out = {}
        for r in reg.rows:
            b = canon_batch(reg.get(r, 'batch_id'))
            vendor = reg.get(r, 'vendor').strip().upper()
            fmt = reg.get(r, 'coord_format').strip().lower()
            frame = reg.get(r, 'frame').strip().lower()
            resub = reg.get(r, 'resubmission_accepted').strip().upper()
            if not b:
                continue
            out[b] = (vendor, fmt, frame, resub)
        return out

    def taxonomy_crosswalk(self):
        e = self.e
        blocks = e.docx_blocks('taxonomy_v3_charter.docx')
        crosswalk = {}
        appendix = None
        for i, (kind, payload) in enumerate(blocks):
            if kind == 'p' and payload.lower().startswith('appendix'):
                appendix = i
                break
        table = None
        cross = None
        for i, (kind, payload) in enumerate(blocks):
            if kind != 'table':
                continue
            hdr = [c.strip().lower() for c in payload[0]]
            if 'model_label' in hdr:
                cross = payload
            elif appendix is not None and i > appendix:
                table = payload
        if cross:
            hdr = [c.strip().lower() for c in cross[0]]
            for r in cross[1:]:
                d = dict(zip(hdr, r))
                crosswalk[d.get('model_label', '').strip()] = (
                    d.get('class', '').strip(), d.get('disposition', '').strip().lower())
        errata = e.docx_errata('taxonomy_v3_charter.docx')
        reg = Reg(table[0] if table else [], table[1:] if table else [], errata)
        nl = {}
        for r in reg.rows:
            proj = canon_project(reg.get(r, 'project'))
            label = reg.get(r, 'raw_label')
            cls = reg.get(r, 'class').strip()
            disp = reg.get(r, 'disposition').strip().lower()
            nl[(proj, label)] = (cls, disp)
        return crosswalk, nl

    def ks_codebook(self):
        e = self.e
        header, rows, errata = e.pdf_register('ks_class_codebook.pdf')
        reg = Reg(header, rows, errata)
        out = []
        for r in reg.rows:
            proj = canon_project(reg.get(r, 'project'))
            code = parse_int(reg.get(r, 'code'))
            cls = reg.get(r, 'class').strip()
            disp = reg.get(r, 'disposition').strip().lower()
            vf = parse_instant(reg.get(r, 'valid_from'))
            vt = reg.get(r, 'valid_to').strip()
            vto = None if vt in ('-', '') else parse_instant(vt)
            if proj and code is not None:
                out.append((proj, code, cls, disp, vf, vto))
        return out

    def ob_aliases(self):
        e = self.e
        out = {}
        if not e.exists('ob_label_aliases.yaml'):
            return out
        for a in e.yaml_doc('ob_label_aliases.yaml').get('aliases') or []:
            proj = canon_project(a.get('project'))
            alias = a.get('alias')
            if proj is None or alias is None:
                continue
            cls = a.get('class')
            disp = a.get('disposition')
            if disp is None:
                disp = 'eval'
            out[(proj, str(alias).strip())] = (cls, str(disp).strip().lower())
        return out

    def qa_decisions(self):
        """(annotation_id, revision) -> True when the latest decision rejects it."""
        e = self.e
        snapshot = None
        decisions = []
        if e.exists('labeling_qa_portal.html'):
            for h, t in e.html_headings('labeling_qa_portal.html'):
                m = re.search(r'snapshot\s+(\S+)', t)
                if m:
                    snapshot = parse_instant(m.group(1).strip('()'))
                    break
            header, rows, errata = e.html_appendix('labeling_qa_portal.html')
            reg = Reg(header, rows, errata)
            for r in reg.rows:
                ann = canon_annotation(reg.get(r, 'annotation_id'))
                rev = parse_int(reg.get(r, 'revision'))
                dec = reg.get(r, 'decision').strip().lower()
                at = parse_instant(reg.get(r, 'decided_at'))
                if ann and rev is not None and at is not None:
                    decisions.append((ann, rev, dec, at, 0))
        if e.exists('labeling_qa_export.xlsx'):
            for sn, rows in e.xlsx_dicts('labeling_qa_export.xlsx').items():
                for d in rows:
                    ann = canon_annotation(d.get('annotation_id'))
                    rev = parse_int(d.get('revision'))
                    dec = d.get('decision')
                    dec = dec.strip().lower() if isinstance(dec, str) else dec
                    state = d.get('state')
                    state = state.strip().lower() if isinstance(state, str) else ''
                    at = ts_to_datetime(d.get('decided_at'))
                    if ann and rev is not None and at is not None:
                        if state != 'final':
                            continue
                        if snapshot is not None and at <= snapshot:
                            continue
                        if at > CUTOFF:
                            continue
                        decisions.append((ann, rev, dec, at, 1))
        latest = {}
        order = 0
        for ann, rev, dec, at, src in decisions:
            key = (at, src, order)
            order += 1
            if (ann, rev) not in latest or key > latest[(ann, rev)][0]:
                latest[(ann, rev)] = (key, dec)
        rejected = set()
        for (ann, rev), (_, dec) in latest.items():
            if dec == 'rejected':
                rejected.add((ann, rev))
        return rejected

    def annotation_errata(self):
        e = self.e
        if not e.exists('annotation_errata_register.md'):
            return []
        header, rows, errata = e.md_register('annotation_errata_register.md')
        reg = Reg(header, rows, errata)
        out = []
        for r in reg.rows:
            eid = reg.get(r, 'errata_id').strip()
            ann = canon_annotation(reg.get(r, 'annotation_id'))
            action = reg.get(r, 'action').strip().upper()
            value = reg.get(r, 'value').strip()
            eff = date_only(reg.get(r, 'effective'))
            out.append((eff, eid, ann, action, value))
        out.sort(key=lambda x: (x[0] or datetime(1970, 1, 1, tzinfo=timezone.utc), x[1]))
        return [x for x in out if x[0] is not None and x[0] <= CUTOFF]

    def campaign(self):
        e = self.e
        items = {}
        boxes = []
        if not e.exists('relabel_campaign_2026q3.xlsx'):
            return items, boxes
        sheets = e.xlsx_dicts('relabel_campaign_2026q3.xlsx')
        for d in sheets.get('items', []):
            item = d.get('item_id')
            ident = self.ids.canonical_id(d.get('image_id'))
            if item and ident:
                items[str(item).strip().upper()] = ident
        approved_items = set()
        if e.exists('relabel_campaign_status.json'):
            statuses = e.json_doc('relabel_campaign_status.json').get('statuses') or []
            latest = {}
            order = 0
            for s in statuses:
                item = str(s.get('item', '')).strip().upper()
                at = parse_instant(s.get('at'))
                if not item or at is None:
                    continue
                if at > CUTOFF:
                    continue
                key = (at, order)
                order += 1
                if item not in latest or key > latest[item][0]:
                    latest[item] = (key, str(s.get('status', '')).strip().lower())
            for item, (_, st) in latest.items():
                if st == 'approved':
                    approved_items.add(item)
        for d in sheets.get('boxes', []):
            box = d.get('box_id')
            item = d.get('item_id')
            if isinstance(item, str):
                item = item.strip().upper()
            elif item is not None:
                item = str(item).strip().upper()
            if box is None or item is None:
                continue
            boxes.append((str(box).strip().upper(), item, d))
        campaign = defaultdict(list)
        for box, item, d in boxes:
            ident = items.get(item)
            if ident is None or item not in approved_items:
                continue
            campaign[ident].append((box, d))
        return items, campaign










# --------------------------------------------------------------------------- exclusions

def load_lifecycle(estate, ids):
    """image -> True when its lifecycle ends withdrawn."""
    if not estate.exists('image_lifecycle_events.xml'):
        return set()
    root = estate.xml_root('image_lifecycle_events.xml')
    events = []
    for ev in root.iter('event'):
        ident = ids.canonical_id(ev.get('image'))
        if ident is None:
            continue
        at = parse_instant(ev.get('at'))
        if at is None:
            continue
        seq = parse_int(ev.get('seq'))
        if seq is None:
            seq = 0
        events.append((at, seq, ev.get('id'), ev.get('type'), ident))
    events.sort(key=lambda x: (x[0], x[1]))
    state = {}
    seen = set()
    withdrawn = set()
    for at, seq, eid, kind, ident in events:
        if at > CUTOFF:
            continue
        if eid in seen:
            continue
        seen.add(eid)
        if kind == 'withdrawn':
            withdrawn.add(ident)
            state[ident] = 'withdrawn'
        elif kind == 'restored':
            withdrawn.discard(ident)
            state[ident] = 'active'
    return withdrawn


def load_privacy(estate, ids):
    """image -> True when the image is held."""
    register_date = None
    held = set()
    if estate.exists('exclusion_policy.docx'):
        header, rows = estate.docx_appendix('exclusion_policy.docx')
        reg = Reg(header, rows, estate.docx_errata('exclusion_policy.docx'))
        lines = [p for kind, p in estate.docx_blocks('exclusion_policy.docx') if kind == 'p']
        for p in lines:
            m = re.search(r'as of\s+(\d{4}-\d{2}-\d{2}T\S+)', p)
            if m:
                register_date = parse_instant(m.group(1))
                break
        by_image = defaultdict(dict)
        for r in reg.rows:
            ident = ids.canonical_id(reg.get(r, 'image_id'))
            rid = reg.get(r, 'request_id').strip()
            if ident is None:
                continue
            by_image[ident][rid] = reg.get(r, 'status').strip().upper()
        for ident, statuses in by_image.items():
            vals = list(statuses.values())
            if any(v == 'HOLD' for v in vals):
                held.add(ident)
    released_by_mail = set()
    held_by_mail = set()
    if estate.exists('privacy_requests.mbox'):
        import email.utils
        from email.header import decode_header
        for msg in estate.mbox('privacy_requests.mbox'):
            headers = msg['headers']
            h = {}
            for line in headers:
                if ':' in line:
                    k, v = line.split(':', 1)
                    h.setdefault(k.strip().lower(), []).append(v.strip())
            sender = (h.get('from') or [''])[0]
            if 'privacy-office.skye.example' not in sender:
                continue
            date_hdr = (h.get('date') or [None])[0]
            if date_hdr is None:
                continue
            try:
                at = email.utils.parsedate_to_datetime(date_hdr)
            except (TypeError, ValueError):
                continue
            if at.tzinfo is None:
                at = at.replace(tzinfo=timezone.utc)
            subject = (h.get('subject') or [''])[0]
            try:
                parts = decode_header(subject)
                text = ''
                for data, charset in parts:
                    if isinstance(data, bytes):
                        text += data.decode(charset or 'utf-8', 'replace')
                    else:
                        text += data
            except Exception:
                text = subject
            text = text.strip()
            action = None
            m = re.match(r'^(?:Fwd:\s*)?(TAKEDOWN|RELEASE|ACK)\s+(.*)$', text)
            if not m:
                continue
            action = m.group(1)
            ident = ids.canonical_id(m.group(2).strip())
            if ident is None:
                continue
            if register_date is not None and at <= register_date:
                continue
            if at > CUTOFF:
                continue
            if action == 'TAKEDOWN':
                held.add(ident)
                released_by_mail.discard(ident)
            elif action == 'RELEASE':
                held.discard(ident)
                released_by_mail.add(ident)
    if estate.exists('privacy_register_export.tsv'):
        for d in estate.tabular_dicts('privacy_register_export.tsv', '\t'):
            ident = ids.canonical_id(d.get('image_id'))
            if ident is None:
                continue
            if str(d.get('status', '')).strip().upper() == 'LEGAL-HOLD':
                held.add(ident)
    return held


def load_board_decisions(estate, ids):
    """image -> True when the latest board decision is EXCLUDE."""
    latest = {}
    for name in ('release_governance.docx', 'release_governance_v2_signed.docx'):
        if not estate.exists(name):
            continue
        header, rows = estate.docx_appendix(name)
        reg = Reg(header, rows, estate.docx_errata(name))
        for r in reg.rows:
            ident = ids.canonical_id(reg.get(r, 'image_id'))
            did = reg.get(r, 'decision_id').strip()
            when = date_only(reg.get(r, 'decided_on'))
            if ident is None or when is None:
                continue
            if when > CUTOFF:
                continue
            key = (when, did)
            if ident not in latest or key > latest[ident][0]:
                latest[ident] = (key, reg.get(r, 'decision').strip().upper())
    return {k: v[1] == 'EXCLUDE' for k, v in latest.items() if v[1] in ('EXCLUDE', 'CONFIRM')}


def popcount(x):
    n = 0
    while x:
        x &= x - 1
        n += 1
    return n


def build_buckets(hashes):
    hi = defaultdict(list)
    lo = defaultdict(list)
    for h in hashes:
        hi[h >> 32].append(h)
        lo[h & 0xFFFFFFFF].append(h)
    return hi, lo


def variants32(x):
    yield x
    for i in range(32):
        yield x ^ (1 << i)
    for i in range(32):
        for j in range(i + 1, 32):
            yield x ^ (1 << i) ^ (1 << j)


def nearest_matches(cand, buckets, limit=4):
    """All training hashes within the Hamming distance limit of a candidate hash."""
    hi, lo = buckets
    out = {}
    c_hi = cand >> 32
    c_lo = cand & 0xFFFFFFFF
    for v in variants32(c_hi):
        lst = hi.get(v)
        if lst:
            for h in lst:
                if h not in out:
                    d = popcount(cand ^ h)
                    if d <= limit:
                        out[h] = d
    for v in variants32(c_lo):
        lst = lo.get(v)
        if lst:
            for h in lst:
                if h not in out:
                    d = popcount(cand ^ h)
                    if d <= limit:
                        out[h] = d
    return out


# --------------------------------------------------------------------------- detections

class NodeDump:
    """Raw detection records of every delivered node dump, keyed by run."""

    def __init__(self, estate, ids):
        self.e = estate
        self.ids = ids
        self.by_node = defaultdict(list)     # node -> [(run, image, det_id, cls, box, score, lb)]
        self.stores = {}

    def build(self):
        e = self.e
        for node in ('n1', 'n2', 'n3', 'n4', 'n5', 'n7'):
            for name in sorted(os.listdir(e.root)):
                if not re.match(r'^preds_.*_%s\.[a-z0-9]+$' % node, name):
                    continue
                if not os.path.isfile(e.path(name)):
                    continue
                for rec in self._read_file(name, node):
                    self.by_node[node].append(rec)
        for name in ('node6_rerun_store.db', 'node6_ingest_replica.db'):
            if not e.exists(name):
                continue
            store = 'n6' if name == 'node6_rerun_store.db' else 'n6-replica'
            recs = []
            tables = e.sqlite_tables(name)
            for d in tables.get('dets', []):
                lb = None
                recs.append(self._from_store(d, tables.get('preprocess', []), store))
            self.by_node[store] = [r for r in recs if r is not None]
        if e.exists('preds_r3_n2_replay.jsonl'):
            recs = []
            for d in e.jsonl('preds_r3_n2_replay.jsonl'):
                r = self._from_jsonl(d, 'n2-replay')
                if r is not None:
                    recs.append(r)
            self.by_node['n2-replay'] = recs

    def _read_file(self, name, node):
        e = self.e
        ext = name.rsplit('.', 1)[1]
        out = []
        if ext in ('csv', 'tsv'):
            delim = ',' if ext == 'csv' else '\t'
            for d in e.tabular_dicts(name, delim):
                r = self._from_row(d, node)
                if r is not None:
                    out.append(r)
        elif ext == 'jsonl':
            for d in e.jsonl(name):
                r = self._from_jsonl(d, node)
                if r is not None:
                    out.append(r)
        elif ext == 'parquet':
            for d in e.parquet_dicts(name):
                r = self._from_row(d, node)
                if r is not None:
                    out.append(r)
        elif ext == 'xml':
            root = e.xml_root(name)
            for det in root.iter('det'):
                box = det.find('box')
                d = {
                    'det_id': det.get('id'),
                    'image_id': det.get('image'),
                    'run': det.get('run'),
                    'class_index': det.get('cls'),
                    'x1': box.get('x1') if box is not None else None,
                    'y1': box.get('y1') if box is not None else None,
                    'x2': box.get('x2') if box is not None else None,
                    'y2': box.get('y2') if box is not None else None,
                    'score': det.findtext('score'),
                }
                r = self._from_row(d, node)
                if r is not None:
                    out.append(r)
        elif ext == 'xlsx':
            for sn, rows in e.xlsx_dicts(name).items():
                for d in rows:
                    r = self._from_row(d, node)
                    if r is not None:
                        out.append(r)
        return out

    def _from_row(self, d, node):
        det = canon_det_id(d.get('det_id'))
        image = self.ids.canonical_id(d.get('image_id'))
        run = str(d.get('run') or d.get('model') or '').strip()
        cls = parse_int(d.get('class_index'))
        if det is None or image is None or cls is None or not run:
            return None
        if node == 'n2':
            box = d.get('box_cxcywh')
            if box is None:
                box = [d.get('x1'), d.get('y1'), d.get('x2'), d.get('y2')]
                kind = 'xyxy'
            else:
                kind = 'cxcywh'
        else:
            box = [d.get('x1'), d.get('y1'), d.get('x2'), d.get('y2')]
            kind = 'xyxy'
        score, unit = self._score_of(d, node)
        lb = None
        if 'lb_scale' in d and d.get('lb_scale') not in (None, ''):
            lb = self._letterbox(d.get('lb_scale'), d.get('lb_pad_x'), d.get('lb_pad_y'))
        return self._make(run, image, det, cls, box, kind, score, unit, lb)

    def _from_jsonl(self, d, node):
        det = canon_det_id(d.get('det'))
        image = self.ids.canonical_id(d.get('image'))
        run = str(d.get('run') or '').strip()
        cls = parse_int(d.get('cls'))
        if det is None or image is None or cls is None or not run:
            return None
        box = d.get('box_cxcywh') or [d.get('x1'), d.get('y1'), d.get('x2'), d.get('y2')]
        kind = 'cxcywh' if d.get('box_cxcywh') else 'xyxy'
        if 'score_pct' in d:
            score, unit = d.get('score_pct'), 'pct'
        elif 'score_bp' in d:
            score, unit = d.get('score_bp'), 'bp'
        else:
            score, unit = self._score_of(d, node)
        lb = None
        if isinstance(d.get('letterbox'), dict):
            lbd = d['letterbox']
            lb = self._letterbox(lbd.get('scale'), lbd.get('pad_x'), lbd.get('pad_y'))
        return self._make(run, image, det, cls, box, kind, score, unit, lb)

    def _from_store(self, d, preprocess, store):
        det = canon_det_id(d.get('det_id'))
        image = self.ids.canonical_id(d.get('image_id'))
        run = str(d.get('run_id') or '').strip()
        cls = parse_int(d.get('class_index'))
        if det is None or image is None or cls is None or not run:
            return None
        lb = None
        for p in preprocess:
            if p.get('run_id') == run and self.ids.canonical_id(p.get('image_id')) == image:
                if str(p.get('status', '')).strip().lower() == 'ok':
                    lb = self._letterbox(p.get('scale'), p.get('pad_x'), p.get('pad_y'))
                    break
        box = [d.get('cx'), d.get('cy'), d.get('w'), d.get('h')]
        return self._make(run, image, det, cls, box, 'cxcywh', d.get('score_bp'), 'bp', lb)

    @staticmethod
    def _letterbox(scale, pad_x, pad_y):
        sc = parse_fraction(scale)
        px = parse_number(pad_x)
        py = parse_number(pad_y)
        if sc is None or sc == 0:
            return None
        return (sc, px or Fraction(0), py or Fraction(0))

    @staticmethod
    def _make(run, image, det, cls, box, kind, score, unit, lb):
        if score is None:
            return None
        coords = []
        for v in box:
            if v is None:
                return None
            f = parse_number(v)
            if f is None:
                return None
            coords.append(quantize_coord(f))
        return {'run': run, 'image': image, 'det': det, 'cls': cls, 'box': coords,
                'kind': kind, 'score': parse_number(score), 'unit': unit, 'lb': lb}

    @staticmethod
    def _score_of(d, node):
        for key in ('score_pct', 'score_bp'):
            if key in d and d.get(key) is not None:
                return d.get(key), 'pct' if key == 'score_pct' else 'bp'
        if 'score' in d and d.get('score') is not None:
            unit = str(d.get('score_unit', '') or '').strip().lower()
            if unit in ('pct', 'percent'):
                return d.get('score'), 'pct'
            if unit == 'bp':
                return d.get('score'), 'bp'
            if unit == 'permille':
                return d.get('score'), 'permille'
            return d.get('score'), 'fraction'
        return None, 'fraction'


def parse_fraction(text):
    """An exact fraction from a delivered value like 7/15, 0.56 or 1.0."""
    if text is None:
        return None
    if isinstance(text, Fraction):
        return text
    s = str(text).strip()
    if s == '':
        return None
    if s.startswith('(') and s.endswith(')'):
        s = s[1:-1]
    neg = False
    if s.startswith('-'):
        neg = True
        s = s[1:]
    if '/' in s:
        head, _, tail = s.partition('/')
        num = parse_number(head)
        den = parse_number(tail)
        if num is None or den is None or den == 0:
            return None
        v = num / den
    else:
        v = parse_number(s)
        if v is None:
            return None
    return -v if neg else v


def quantize_coord(f):
    """Model coordinates are recorded to 0.01 px; binary floats are read as the nearest 0.01."""
    if f.denominator == 1:
        return f
    cents = f * 100
    return Fraction(round_half_even(cents), 100)
# --------------------------------------------------------------------------- preprocess logs

def _parse_prep_line(line, node):
    """One preprocess log line -> (run, image, scale, pad_x, pad_y, attempt, ok)."""
    s = line.strip()
    if not s or s.startswith('#'):
        return None
    # generic grammar: PREP|time|run|image|scale|pad_x|pad_y|a/n|status  (or node-prefixed)
    m = re.match(r'^(?:PREP|n[1-7])\|(?:[^|]*\|)?([^|]+)\|([^|]+)\|([^|]+)\|([^|]*)\|([^|]*)\|'
                 r'([0-9]+(?:/[0-9]+)?)\|([A-Za-z]+)\s*$', s)
    if m:
        scale = parse_fraction(m.group(3))
        px = parse_number(m.group(4))
        py = parse_number(m.group(5))
        parts = m.group(6).split('/')
        attempt = parse_int(parts[0])
        ok = m.group(7).strip().lower() == 'ok'
        return (m.group(1), m.group(2), scale, px, py, attempt, ok)
    # n1: key=value pairs
    if 'run=' in s and 'pad=' in s and 'attempt=' in s:
        d = dict(re.findall(r'(\w+)=("[^"]*"|[^ ]+)', s))
        run = d.get('run')
        img = d.get('img')
        if not run or not img:
            return None
        scale = parse_fraction(d.get('scale'))
        pads = d.get('pad', '')
        parts = pads.split(',')
        px = parse_number(parts[0]) if parts else None
        py = parse_number(parts[1]) if len(parts) > 1 else None
        att = d.get('attempt', '')
        attempt = parse_int(att.split('/')[0]) if att else None
        ok = str(d.get('status', '')).strip().lower() == 'ok'
        return (run, img, scale, px, py, attempt, ok)
    # n2: letterbox(scale=..., pad_x=..., pad_y=...) try=a of n OK
    m = re.match(r'^.*?PREP\s+image="([^"]+)"\s+run="([^"]+)"\s+'
                 r'letterbox\(scale=([^,)]+),\s*pad_x=([^,)]+),\s*pad_y=([^)]+)\)\s+'
                 r'try=(\d+)\s+of\s+\d+\s+(OK|FAILED)\s*$', s)
    if m:
        scale = parse_fraction(m.group(3))
        px = parse_number(m.group(4))
        py = parse_number(m.group(5))
        attempt = parse_int(m.group(6))
        ok = m.group(7) == 'OK'
        return (m.group(2), m.group(1), scale, px, py, attempt, ok)
    # n4: scale S pads X Y attempt a of n -> status
    m = re.match(r'^.*?:\s*(\S+)\s+(\S+)\s+scale\s+(\S+)\s+pads\s+(\S+)\s+(\S+)\s+'
                 r'attempt\s+(\d+)\s+of\s+\d+\s+->\s*(\S+)\s*$', s)
    if m:
        scale = parse_fraction(m.group(3))
        px = parse_number(m.group(4))
        py = parse_number(m.group(5))
        attempt = parse_int(m.group(6))
        ok = m.group(7).strip().lower() == 'ok'
        return (m.group(1), m.group(2), scale, px, py, attempt, ok)
    # n5: run=R3 image=... s=decimal (frac) px= py= a=a/n OK
    m = re.match(r'^.*?run=(\S+)\s+image=(\S+)\s+s=(\S+)(?:\s+\(([^)]+)\))?\s+'
                 r'px=(\S+)\s+py=(\S+)\s+a=(\d+)(?:/\d+)?\s+(OK|ERR)\s*$', s)
    if m:
        scale = parse_fraction(m.group(4)) if m.group(4) else parse_fraction(m.group(3))
        px = parse_number(m.group(5))
        py = parse_number(m.group(6))
        attempt = parse_int(m.group(7))
        ok = m.group(8) == 'OK'
        return (m.group(1), m.group(2), scale, px, py, attempt, ok)
    return None


def load_preprocess(estate, node, resolve_run, canonical_id):
    """(run, image) -> (scale, pad_x, pad_y) of the ok attempt with the highest number."""
    name = 'preprocess_%s.log' % node
    if not estate.exists(name):
        return {}
    best = {}
    for line in read_text_lines(estate.path(name)):
        parsed = _parse_prep_line(line, node)
        if parsed is None:
            continue
        run_raw, image_raw, scale, px, py, attempt, ok = parsed
        if not ok or scale is None or scale == 0:
            continue
        run = resolve_run(run_raw)
        image = canonical_id(image_raw)
        if run is None or image is None:
            continue
        key = (run, image)
        cur = best.get(key)
        if cur is None or (attempt or 0) > cur[0]:
            best[key] = (attempt or 0, scale, px or Fraction(0), py or Fraction(0))
    return {k: (v[1], v[2], v[3]) for k, v in best.items()}


# --------------------------------------------------------------------------- calibration

def load_calibration(estate, model_to_run):
    """run -> class -> list of (x, y) knots, ascending by k."""
    maps = {}

    def put(run, cls, k, x, y):
        if run is None or cls is None:
            return
        entry = maps.setdefault(run, {})
        lst = entry.setdefault(cls, {})
        lst[k] = (x, y)

    # YAML delivery
    for name in sorted(os.listdir(estate.root)):
        if not name.endswith('.yaml') or not name.startswith('calibration'):
            continue
        doc = estate.yaml_doc(name)
        cal = doc.get('calibration') if isinstance(doc, dict) else None
        if not cal:
            continue
        run = model_to_run.get(str(cal.get('model', '')).strip()) or str(cal.get('run', '')).strip()
        for kn in cal.get('knots') or []:
            cls = str(kn.get('class', '')).strip()
            k = parse_int(kn.get('k'))
            x = parse_number(kn.get('x'))
            if kn.get('y_pct') is not None:
                y = parse_number(kn.get('y_pct'))
                if y is not None:
                    y = y / 100
            else:
                y = parse_number(kn.get('y'))
            if k is None or x is None or y is None:
                continue
            put(run, cls, k, x, y)
    # TOML delivery
    for name in sorted(os.listdir(estate.root)):
        if not name.endswith('.toml') or not name.startswith('calibration'):
            continue
        doc = estate.toml_doc(name)
        run = str(doc.get('run', '')).strip()
        if not run:
            continue
        for kn in doc.get('knot') or []:
            cls = str(kn.get('class', '')).strip()
            k = parse_int(kn.get('k'))
            x = parse_number(kn.get('x'))
            unit = str(kn.get('unit', '') or '').strip().lower()
            if kn.get('y_pct') is not None:
                y = parse_number(kn.get('y_pct'))
                if y is not None:
                    y = y / 100
            else:
                y = parse_number(kn.get('y'))
            if y is not None and unit == 'pct':
                y = y / 100
            if k is None or x is None or y is None:
                continue
            put(run, cls, k, x, y)
    # INI delivery
    for name in sorted(os.listdir(estate.root)):
        if not name.endswith('.ini') or not name.startswith('calibration'):
            continue
        sections = estate.ini_doc(name)
        run = None
        for key, val in sections.get('meta', {}).items():
            if key.strip().lower() == 'run':
                run = str(val).strip()
        if not run:
            continue
        for sec, entries in sections.items():
            if sec == 'meta' or not entries:
                continue
            cls = sec.strip()
            for key, val in entries.items():
                m = re.match(r'^k(\d+)$', key.strip())
                if not m:
                    continue
                k = int(m.group(1))
                xm = re.search(r'x=(-?[\d.,]+)', val)
                ym = re.search(r'y%=(-?[\d.,]+)', val)
                if ym is None:
                    ym = re.search(r'y=(-?[\d.,]+)', val)
                if xm is None or ym is None:
                    continue
                x = parse_number(xm.group(1))
                y = parse_number(ym.group(1))
                if '%=' in ym.group(0):
                    y = y / 100 if y is not None else None
                if x is None or y is None:
                    continue
                put(run, cls, k, x, y)
    # PDF certificates
    cert_files = [n for n in sorted(os.listdir(estate.root))
                  if n.startswith('calibration_certificate') and n.endswith('.pdf')]
    for name in cert_files:
        lines = estate.pdf_lines(name)
        title = ' '.join(lines[:3])
        m = re.search(r'CALIBRATION CERTIFICATE\s*-\s*(\S+)', title)
        if not m:
            continue
        model = m.group(1)
        run = model_to_run.get(model)
        if run is None:
            continue
        deferred = set()
        for line in lines[:12]:
            m2 = re.search(r'classes ([\w, ]+?) are deferred', line)
            if m2:
                for cls in re.split(r',\s*', m2.group(1).strip()):
                    cls = cls.strip()
                    if cls:
                        deferred.add(cls)
                break
        header, rows, errata = estate.pdf_register(name)
        reg = Reg(header, rows, errata)
        knots = defaultdict(dict)
        for r in reg.rows:
            cls = reg.get(r, 'class').strip()
            k = parse_int(reg.get(r, 'k'))
            x = parse_number(reg.get(r, 'x'))
            ytxt = reg.get(r, 'y').strip()
            pct = ytxt.endswith('%')
            if pct:
                ytxt = ytxt[:-1]
            y = parse_number(ytxt)
            if pct and y is not None:
                y = y / 100
            if k is None or x is None or y is None:
                continue
            if cls in deferred:
                continue
            knots[cls][k] = (x, y)
        for cls, lst in knots.items():
            if not lst:
                continue
            for k, (x, y) in lst.items():
                put(run, cls, k, x, y)
        if deferred and estate.exists('calibration_certificate_rc2_reissue.pdf'):
            header2, rows2, errata2 = estate.pdf_register('calibration_certificate_rc2_reissue.pdf')
            reg2 = Reg(header2, rows2, errata2)
            for r in reg2.rows:
                cls = reg2.get(r, 'class').strip()
                if cls not in deferred:
                    continue
                k = parse_int(reg2.get(r, 'k'))
                x = parse_number(reg2.get(r, 'x'))
                ytxt = reg2.get(r, 'y').strip()
                pct = ytxt.endswith('%')
                if pct:
                    ytxt = ytxt[:-1]
                y = parse_number(ytxt)
                if pct and y is not None:
                    y = y / 100
                if k is None or x is None or y is None:
                    continue
                put(run, cls, k, x, y)
    out = {}
    for run, classes in maps.items():
        conv = {}
        for cls, lst in classes.items():
            items = sorted(lst.items())
            conv[cls] = ([x for _, (x, _) in items], [y for _, (_, y) in items])
        out[run] = conv
    return out


def calibrate(value, xs, ys):
    """Isotonic calibration of a raw score with the run's knot list."""
    if not xs:
        return Fraction(0)
    i = 0
    n = len(xs)
    while i + 1 < n and xs[i + 1] <= value:
        i += 1
    if value < xs[0]:
        return ys[0]
    if value >= xs[-1]:
        return ys[-1]
    x0, x1 = xs[i], xs[i + 1]
    y0, y1 = ys[i], ys[i + 1]
    if x1 == x0:
        return y1
    return y0 + (y1 - y0) * (value - x0) / (x1 - x0)

# --------------------------------------------------------------------------- quarantine

def load_quarantine(estate, ids):
    if not estate.exists('node_quarantine_report.pdf'):
        return set()
    header, rows, errata = estate.pdf_register('node_quarantine_report.pdf')
    reg = Reg(header, rows, errata)
    out = set()
    for r in reg.rows:
        run = reg.get(r, 'run').strip().upper()
        node = reg.get(r, 'node').strip().lower()
        ident = ids.canonical_id(reg.get(r, 'image_id'))
        status = reg.get(r, 'status').strip().lower()
        if status != 'quarantined':
            continue
        if run and node and ident:
            out.add((run, node, ident))
    return out


# --------------------------------------------------------------------------- helpers

def write_csv(path, header, rows):
    with open(path, 'w', encoding='utf-8', newline='') as fh:
        fh.write(','.join(header) + '\n')
        for r in rows:
            fh.write(','.join(str(c) for c in r) + '\n')


def write_json(path, obj):
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(obj, fh, indent=1, ensure_ascii=False)
        fh.write('\n')


def iou(a, b):
    ix = max(a[0], b[0])
    iy = max(a[1], b[1])
    jx = min(a[2], b[2])
    jy = min(a[3], b[3])
    iw = jx - ix
    ih = jy - iy
    if iw <= 0 or ih <= 0:
        return Fraction(0)
    inter = iw * ih
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    union = area_a + area_b - inter
    if union == 0:
        return Fraction(0)
    return Fraction(inter, union)


def intersection_over_det(det, region):
    ix = max(det[0], region[0])
    iy = max(det[1], region[1])
    jx = min(det[2], region[2])
    jy = min(det[3], region[3])
    iw = jx - ix
    ih = jy - iy
    if iw <= 0 or ih <= 0:
        return Fraction(0)
    area = (det[2] - det[0]) * (det[3] - det[1])
    if area == 0:
        return Fraction(0)
    return Fraction(iw * ih, area)


def ap_from_ranking(ranked, gt_count):
    """101-point AP from [(score, det_id, is_tp)] ranked by score desc, det id asc."""
    if gt_count == 0:
        return None
    precisions = []
    recalls = []
    tp = 0
    for rank, (score, det_id, is_tp) in enumerate(ranked, 1):
        if is_tp:
            tp += 1
        precisions.append(Fraction(tp, rank))
        recalls.append(Fraction(tp, gt_count))
    envelope = [None] * len(precisions)
    best = Fraction(0)
    for i in range(len(precisions) - 1, -1, -1):
        if precisions[i] > best:
            best = precisions[i]
        envelope[i] = best
    total = Fraction(0)
    ptr = 0
    for i in range(101):
        r = Fraction(i, 100)
        while ptr < len(recalls) and recalls[ptr] < r:
            ptr += 1
        if ptr >= len(recalls):
            break
        total += envelope[ptr]
    return total / 101

def count_parsed(estate, name):
    """The records actually present in a delivered file."""
    ext = name.rsplit('.', 1)[1] if '.' in name else ''
    if ext == 'csv':
        data, hdrs, comments = estate.data_records(name, ',')
        return len(data)
    if ext == 'tsv':
        data, hdrs, comments = estate.data_records(name, '\t')
        return len(data)
    if ext in ('txt', 'log'):
        n = 0
        for line in read_text_lines(estate.path(name)):
            if line.strip() and not line.lstrip().startswith('#'):
                n += 1
        return n
    if ext == 'jsonl':
        return len(estate.jsonl(name))
    if ext == 'json':
        doc = estate.json_doc(name)
        for key in ('records', 'waivers', 'statuses'):
            if isinstance(doc.get(key), list):
                return len(doc[key])
        for v in doc.values():
            if isinstance(v, list):
                return len(v)
        return 0
    if ext == 'xml':
        root = estate.xml_root(name)
        total = 0
        for tag in ('event', 'object', 'det'):
            total += len(list(root.iter(tag)))
        return total
    if ext == 'xlsx':
        total = 0
        for sn, rows in estate.xlsx_rows(name).items():
            for r in rows:
                if any(c is not None for c in r):
                    if estate.is_header_row(_cells_of(r)):
                        continue
                    total += 1
        return total
    if ext == 'parquet':
        import pyarrow.parquet as pq
        return pq.read_table(estate.path(name)).num_rows
    if ext == 'db':
        total = 0
        for tname, rows in estate.sqlite_tables(name).items():
            if tname in ('preprocess', 'meta'):
                continue
            total += len(rows)
        return total
    if ext == 'mbox':
        return len(estate.mbox(name))
    if ext == 'ics':
        return len(estate.ics_events(name))
    if ext == 'yaml':
        doc = estate.yaml_doc(name)
        best = 0
        stack = [doc]
        while stack:
            cur = stack.pop()
            if isinstance(cur, list):
                if len(cur) > best:
                    best = len(cur)
                continue
            if isinstance(cur, dict):
                stack.extend(cur.values())
        return best
    if ext == 'toml':
        doc = estate.toml_doc(name)
        total = 0
        for v in doc.values():
            if isinstance(v, list):
                total += len(v)
        return total
    if ext == 'ini':
        sections = {}
        cur = None
        for line in read_text_lines(estate.path(name)):
            t = line.strip()
            if not t or t.startswith(';') or t.startswith('#'):
                continue
            m = re.match(r'^\[(.+)\]$', t)
            if m:
                cur = m.group(1).strip()
                sections[cur] = 0
                continue
            if cur is not None and '=' in t:
                sections[cur] += 1
        if name == 'image_id_aliases.ini':
            return sections.get('aliases', 0)
        if name.startswith('calibration'):
            return sum(v for k, v in sections.items() if k != 'meta')
        return sum(sections.values())
    if ext == 'docx':
        header, rows = estate.docx_appendix(name)
        return len(rows)
    if ext == 'pdf':
        header, rows, errata = estate.pdf_register(name)
        return len(rows)
    if ext == 'md':
        header, rows, errata = estate.md_register(name)
        return len(rows)
    if ext == 'html':
        header, rows, errata = estate.html_appendix(name)
        return len(rows)
    return 0


def declared_counts(estate):
    out = defaultdict(int)
    if estate.exists('delivery_manifest.toml'):
        doc = estate.toml_doc('delivery_manifest.toml')
        for p in doc.get('partition') or []:
            f = p.get('file', '')
            if not f or not estate.exists(f):
                continue
            if p.get('status') in ('superseded', 'voided', 'withdrawn'):
                continue
            out[f] += int(p.get('records', 0) or 0)
    return dict(out)

IOU_THRESHOLDS = [Fraction(50 + 5 * i, 100) for i in range(10)]


def main(estate_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    estate = Estate(estate_dir)
    estate.build_vocabulary()
    _dbg('vocabulary')
    ids = IdNormalizer(estate)
    cat = Catalogues(estate, ids)

    freeze = parse_freeze(estate, ids)
    frames = load_frames_index(estate, ids)
    roster = load_roster(estate)
    sync = ClockSync(estate)
    seqs = cat.sequences()
    integrity = cat.integrity()
    geometry = cat.geometry(integrity)
    orientation = cat.orientation()
    _dbg('catalogues')
    runs, labels, nodeassign = cat.run_registry()
    mirror_assign = cat.run_registry_mirror()
    model_to_run = {}
    for rid, info in runs.items():
        model_to_run[info['model']] = rid

    def resolve_run(name):
        if name is None:
            return None
        n = str(name).strip()
        if n in runs:
            return n
        return model_to_run.get(n)

    reviewed = sorted(rid for rid, info in runs.items() if info['status'] == 'review')
    incumbent = None
    for rid, info in runs.items():
        if info['status'] == 'review' and info['model'] == 'skye-v6.4':
            incumbent = rid
            break
    if incumbent is None and reviewed:
        incumbent = reviewed[0]

    candidates = sorted(i for i in dict.fromkeys(freeze) if i in frames)
    captured = {}
    site_of = {}
    for ident in candidates:
        rec = frames[ident]
        inst, local_date = corrected_capture(rec, roster, sync)
        captured[ident] = inst
        entry = roster.get((rec[0], local_date)) if local_date is not None else None
        site_of[ident] = (entry.get('site') or '') if entry else ''

    # ---- exclusion evidence
    withdrawn = load_lifecycle(estate, ids)
    privacy_held = load_privacy(estate, ids)
    board_exclude = load_board_decisions(estate, ids)
    candidate_hashes = cat.candidate_hashes()
    waivers = cat.waivers()
    trained_seq = cat.trained_sequences()
    used_indexes = sorted({runs[r]['training_index'] for r in reviewed})
    index_buckets = {idx: build_buckets(cat.training_index(idx)) for idx in used_indexes}

    receipts = cat.batch_receipts()
    on_time = {b for b, w in receipts.items() if w is not None and w <= CUTOFF}
    conventions = cat.batch_conventions()
    resub = {b for b, v in conventions.items() if v[3] == 'Y'}
    vendassign = cat.vendor_assignment()
    records = VendorRecords(estate, ids)
    records.build(on_time, resub)
    rejected = cat.qa_decisions()
    errata = [(e[2], e[3], e[4]) for e in cat.annotation_errata()]
    crosswalk, nl_labels = cat.taxonomy_crosswalk()
    ks_codebook = cat.ks_codebook()
    ob_aliases = cat.ob_aliases()
    campaign_items, campaign = cat.campaign()

    exclusions = {}
    for ident in candidates:
        if ident in withdrawn:
            exclusions[ident] = 'WITHDRAWN'
            continue
        inst = captured.get(ident)
        if inst is None or not (WIN_START <= inst < WIN_END):
            exclusions[ident] = 'OUT_OF_WINDOW'
            continue
        aud = integrity.get(ident)
        if aud is not None and aud[0] == 'FAIL':
            exclusions[ident] = 'CORRUPT'
            continue
        if ident in privacy_held:
            exclusions[ident] = 'PRIVACY_HOLD'
            continue
        if board_exclude.get(ident):
            exclusions[ident] = 'BOARD_OVERRIDE'
            continue
        h = candidate_hashes.get(ident)
        leak = None
        if h:
            for idx in used_indexes:
                found = nearest_matches(h, index_buckets[idx], 4)
                for th, dist in found.items():
                    if (ident, th) in waivers:
                        continue
                    if dist == 0:
                        leak = 'LEAK_EXACT'
                        break
                    if leak is None:
                        leak = 'LEAK_NEAR'
                if leak == 'LEAK_EXACT':
                    break
        if leak:
            exclusions[ident] = leak
            continue
        seq = seqs.get(ident)
        if seq is not None:
            info = trained_seq.get(seq)
            if info is not None and info[0] == 'trained' and info[1] in used_indexes:
                exclusions[ident] = 'LEAK_SEQUENCE'
                continue
        if ident not in campaign and ident not in records.delivered_images:
            exclusions[ident] = 'UNLABELED'

    evaluated = [i for i in candidates if i not in exclusions]
    _dbg('exclusions')

    # ---- ground truth
    gt_by_image = {}
    cfg = {
        'vendor': None, 'records': records.records, 'rejected': rejected,
        'errata': errata, 'batches': conventions, 'nl_labels': nl_labels,
        'ks_codebook': ks_codebook, 'ob_aliases': ob_aliases, 'campaign': campaign,
        'orientation': 1, 'W': 0, 'H': 0,
    }
    for ident in evaluated:
        W, H = geometry.get(ident, (0, 0))
        cfg['W'] = W
        cfg['H'] = H
        cfg['orientation'] = orientation.get(ident, 1)
        cfg['vendor'] = vendassign.get(ident)
        gt_by_image[ident] = build_ground_truth(ident, cfg)

    _dbg('ground truth')
    # ---- detections
    dump = NodeDump(estate, ids)
    dump.build()
    node_records = {}
    for node, recs in dump.by_node.items():
        idx = defaultdict(list)
        for r in recs:
            idx[(r['run'], r['image'])].append(r)
        node_records[node] = idx
    letterboxes = {node: load_preprocess(estate, node, resolve_run, ids.canonical_id)
                   for node in ('n1', 'n2', 'n3', 'n4', 'n5')}
    quarantine = load_quarantine(estate, ids)
    reruns = {}
    if estate.exists('rerun_batches.toml'):
        for entry in estate.toml_doc('rerun_batches.toml').get('rerun') or []:
            reruns[(str(entry.get('run', '')).strip().upper(),
                    ids.canonical_id(entry.get('image')))] = (
                str(entry.get('store', '')).strip().lower(),
                str(entry.get('status', '')).strip().lower())
    calib = load_calibration(estate, model_to_run)

    det_by_image = defaultdict(list)
    counts = {r: {'accepted': 0, 'after_threshold': 0, 'after_nms': 0, 'final': 0}
              for r in reviewed}
    for run in reviewed:
        info = runs[run]
        threshold = info['score_threshold']
        if threshold is None:
            threshold = Fraction(0)
        nms_thr = info['nms_iou']
        if nms_thr is None:
            nms_thr = Fraction(1)
        maxd = info['max_detections']
        cmap = calib.get(run) or {}
        label_map = labels.get(run, {})
        for ident in evaluated:
            W, H = geometry.get(ident, (0, 0))
            pair = (run, ident)
            routed = reruns.get(pair)
            if routed is not None and routed[1] == 'completed' and routed[0] in node_records:
                raw = node_records[routed[0]].get(pair, [])
                lb_pair = None
                has_own = True
            else:
                seq = seqs.get(ident)
                node = nodeassign.get((run, seq))
                if node is None and seq is not None:
                    node = mirror_assign.get((run, seq))
                if node is None or (run, node, ident) in quarantine:
                    continue
                if node not in node_records:
                    continue
                raw = node_records[node].get(pair, [])
                if node in letterboxes:
                    if pair not in letterboxes[node]:
                        continue
                    lb_pair = letterboxes[node][pair]
                else:
                    lb_pair = None
                has_own = node not in letterboxes
            seen = set()
            accepted = []
            for rec in raw:
                score_raw = rec['score']
                if score_raw is None or score_raw < 0:
                    continue
                key = (rec['det'], rec['image'])
                if key in seen:
                    continue
                seen.add(key)
                label = label_map.get(rec['cls'])
                if label is None:
                    continue
                if label in crosswalk:
                    cls, disp = crosswalk[label]
                elif label in CLASSES:
                    cls, disp = label, 'eval'
                else:
                    continue
                if disp == 'drop' or cls not in CLASSES:
                    continue
                if rec['kind'] == 'cxcywh':
                    cx, cy, w, hh = rec['box']
                    box = (cx - w / 2, cy - hh / 2, cx + w / 2, cy + hh / 2)
                else:
                    box = tuple(rec['box'])
                lb = rec['lb'] if has_own else lb_pair
                if lb is None:
                    continue
                scale, pad_x, pad_y = lb
                if scale == 0:
                    continue
                raw_box = ((box[0] - pad_x) / scale, (box[1] - pad_y) / scale,
                           (box[2] - pad_x) / scale, (box[3] - pad_y) / scale)
                cbox = canonical_box(raw_box, 1, W, H, True)
                if cbox is None:
                    continue
                unit = rec['unit']
                sv = score_raw
                if unit == 'pct':
                    sv = sv / 100
                elif unit == 'permille':
                    sv = sv / 1000
                elif unit == 'bp':
                    sv = sv / 10000
                knots = cmap.get(cls)
                score = calibrate(sv, knots[0], knots[1]) if knots else sv
                accepted.append((score, rec['det'], cls, cbox))
            counts[run]['accepted'] += len(accepted)
            kept = [a for a in accepted if a[0] >= threshold]
            counts[run]['after_threshold'] += len(kept)
            by_cls = defaultdict(list)
            for a in kept:
                by_cls[a[2]].append(a)
            nms_out = []
            for cls in by_cls:
                lst = sorted(by_cls[cls], key=lambda x: (-x[0], x[1]))
                keep = []
                for a in lst:
                    sup = False
                    for b in keep:
                        if iou(a[3], b[3]) > nms_thr:
                            sup = True
                            break
                    if not sup:
                        keep.append(a)
                nms_out.extend(keep)
            counts[run]['after_nms'] += len(nms_out)
            nms_out.sort(key=lambda x: (-x[0], x[1]))
            final = nms_out[:maxd] if maxd else nms_out
            counts[run]['final'] += len(final)
            for score, det, cls, cbox in final:
                det_by_image[ident].append((run, det, cls, cbox, score))

    _dbg('detections')
    # ---- matching and metrics
    metrics = {}
    ops = {}
    for run in reviewed:
        for cls in CLASSES:
            ranked = {t: [] for t in IOU_THRESHOLDS}
            gt_count = 0
            det_count = 0
            for ident in evaluated:
                gts = [g for g in gt_by_image.get(ident, [])
                       if g.cls == cls and not g.ignore]
                regions = [(g.x1, g.y1, g.x2, g.y2) for g in gt_by_image.get(ident, [])
                           if g.cls == cls and g.ignore]
                dets = [(d, cbox, s) for (r, d, c, cbox, s) in det_by_image.get(ident, [])
                        if r == run and c == cls]
                det_count += len(dets)
                gt_count += len(gts)
                if not dets:
                    continue
                dets.sort(key=lambda x: (-x[2], x[0]))
                ious = [[iou(d[1], (g.x1, g.y1, g.x2, g.y2)) for g in gts] for d in dets]
                ratios = []
                for d in dets:
                    best_r = Fraction(0)
                    for region in regions:
                        r = intersection_over_det(d[1], region)
                        if r > best_r:
                            best_r = r
                    ratios.append(best_r)
                for t in IOU_THRESHOLDS:
                    matched = set()
                    for di, d in enumerate(dets):
                        best = None
                        for gi, g in enumerate(gts):
                            if gi in matched:
                                continue
                            v = ious[di][gi]
                            if v == 0:
                                continue
                            if best is None or v > best[0] or (v == best[0] and g.gt_id < best[1].gt_id):
                                best = (v, g, gi)
                        if best is not None and best[0] >= t:
                            matched.add(best[2])
                            ranked[t].append((d[2], d[0], True))
                        elif ratios[di] >= t:
                            pass
                        else:
                            ranked[t].append((d[2], d[0], False))
            aps = {}
            for t in IOU_THRESHOLDS:
                lst = sorted(ranked[t], key=lambda x: (-x[0], x[1]))
                aps[t] = ap_from_ranking(lst, gt_count)
            tp50 = sum(1 for x in ranked[IOU_THRESHOLDS[0]] if x[2])
            fp50 = sum(1 for x in ranked[IOU_THRESHOLDS[0]] if not x[2])
            metrics[(run, cls)] = {
                'gt_count': gt_count, 'det_count': det_count,
                'tp_50': tp50, 'fp_50': fp50, 'aps': aps,
            }
            target = TARGET_PROTECTED if cls in PROTECTED else TARGET_OTHER
            best_op = None
            if gt_count > 0:
                lst = sorted(ranked[IOU_THRESHOLDS[0]], key=lambda x: (-x[0], x[1]))
                taus = sorted({x[0] for x in lst}, reverse=True)
                for tau in taus:
                    subset = [x for x in lst if x[0] >= tau]
                    tp = sum(1 for x in subset if x[2])
                    prec = Fraction(tp, len(subset))
                    rec = Fraction(tp, gt_count)
                    if prec >= target:
                        if best_op is None or rec > best_op[1] or (rec == best_op[1] and tau > best_op[0]):
                            best_op = (tau, rec, prec)
            ops[(run, cls)] = best_op

    _dbg('metrics')
    return dict(estate=estate, ids=ids, cat=cat, freeze=freeze, frames=frames,
                candidates=candidates, exclusions=exclusions, evaluated=evaluated,
                captured=captured, site_of=site_of, seqs=seqs, geometry=geometry,
                orientation=orientation, runs=runs, reviewed=reviewed,
                incumbent=incumbent, gt_by_image=gt_by_image, det_by_image=det_by_image,
                counts=counts, metrics=metrics, ops=ops, campaign=campaign)

# --------------------------------------------------------------------------- artifacts

def render(result, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    _dbg('render start')
    ids = result['ids']
    estate = result['estate']
    evaluated = result['evaluated']
    gt_by_image = result['gt_by_image']
    det_by_image = result['det_by_image']
    geometry = result['geometry']
    orientation = result['orientation']
    seqs = result['seqs']
    frames = result['frames']
    reviewed = result['reviewed']
    runs = result['runs']
    metrics = result['metrics']
    ops = result['ops']
    counts = result['counts']
    campaign = result['campaign']

    # eval_images.csv
    rows = []
    for ident in evaluated:
        W, H = geometry.get(ident, (0, 0))
        code = orientation.get(ident, 1)
        uW, uH = (H, W) if code in (6, 8) else (W, H)
        gts = gt_by_image.get(ident, [])
        gt_boxes = sum(1 for g in gts if not g.ignore)
        ignore_regions = sum(1 for g in gts if g.ignore)
        inst = result['captured'].get(ident)
        rows.append([
            ident,
            seqs.get(ident, ''),
            frames[ident][0],
            result['site_of'].get(ident, ''),
            inst.strftime('%Y-%m-%dT%H:%M:%SZ') if inst is not None else '',
            uW, uH, code, gt_boxes, ignore_regions,
        ])
    write_csv(os.path.join(out_dir, 'eval_images.csv'),
              ['image_id', 'sequence_id', 'camera_id', 'site_id', 'captured_utc',
               'width', 'height', 'orientation', 'gt_boxes', 'ignore_regions'], rows)

    # exclusions.csv
    rows = []
    for ident in sorted(result['exclusions']):
        rows.append([ident, result['exclusions'][ident]])
    write_csv(os.path.join(out_dir, 'exclusions.csv'), ['image_id', 'reason'], rows)

    # ground_truth.csv
    rows = []
    for ident in evaluated:
        for g in gt_by_image.get(ident, []):
            rows.append([ident, g.gt_id, g.cls, g.x1, g.y1, g.x2, g.y2,
                         1 if g.ignore else 0])
    rows.sort(key=lambda r: (r[0], r[1]))
    write_csv(os.path.join(out_dir, 'ground_truth.csv'),
              ['image_id', 'gt_id', 'class', 'x1', 'y1', 'x2', 'y2', 'ignore'], rows)

    # detections.csv
    rows = []
    for ident in evaluated:
        for (run, det, cls, cbox, score) in det_by_image.get(ident, []):
            rows.append([run, ident, 'D%09d' % det, cls,
                         cbox[0], cbox[1], cbox[2], cbox[3], fmt6(score)])
    rows.sort(key=lambda r: (r[0], r[1], r[2]))
    write_csv(os.path.join(out_dir, 'detections.csv'),
              ['run_id', 'image_id', 'det_id', 'class', 'x1', 'y1', 'x2', 'y2', 'score'], rows)

    # class_metrics.csv
    rows = []
    for run in reviewed:
        for cls in CLASSES:
            m = metrics[(run, cls)]
            aps = m['aps']
            rows.append([
                run, cls, m['gt_count'], m['det_count'], m['tp_50'], m['fp_50'],
                fmt6(aps[IOU_THRESHOLDS[0]]),
                fmt6(aps[IOU_THRESHOLDS[5]]),
                fmt6(sum((aps[t] for t in IOU_THRESHOLDS if aps[t] is not None),
                         Fraction(0)) / 10
                     if all(aps[t] is not None for t in IOU_THRESHOLDS) else None),
            ])
    write_csv(os.path.join(out_dir, 'class_metrics.csv'),
              ['run_id', 'class', 'gt_count', 'det_count', 'tp_50', 'fp_50',
               'ap_50', 'ap_75', 'ap_50_95'], rows)

    # operating_points.csv
    rows = []
    for run in reviewed:
        for cls in CLASSES:
            target = TARGET_PROTECTED if cls in PROTECTED else TARGET_OTHER
            op = ops[(run, cls)]
            if op is None:
                rows.append([run, cls, fmt6(target), 'NA', 'NA', 'NA'])
            else:
                tau, rec, prec = op
                rows.append([run, cls, fmt6(target), fmt6(tau), fmt6(prec), fmt6(rec)])
    write_csv(os.path.join(out_dir, 'operating_points.csv'),
              ['run_id', 'class', 'target_precision', 'threshold', 'precision', 'recall'], rows)

    # leaderboard.json
    written_ap = {}
    for run in reviewed:
        for cls in CLASSES:
            written_ap[(run, cls)] = metrics[(run, cls)]['aps'][IOU_THRESHOLDS[0]]
    ap50_str = {}
    ap75_str = {}
    map_str = {}
    for run in reviewed:
        vals50 = []
        vals75 = []
        valsall = []
        for cls in CLASSES:
            m = metrics[(run, cls)]
            if m['gt_count'] == 0:
                continue
            vals50.append(m['aps'][IOU_THRESHOLDS[0]])
            vals75.append(m['aps'][IOU_THRESHOLDS[5]])
            valsall.append(m['aps'][IOU_THRESHOLDS[0]])
        map50 = sum(vals50, Fraction(0)) / len(vals50) if vals50 else None
        map75 = sum(vals75, Fraction(0)) / len(vals75) if vals75 else None
        mean5095 = {}
        for cls in CLASSES:
            m = metrics[(run, cls)]
            if m['gt_count'] == 0:
                continue
            aps = m['aps']
            if all(aps[t] is not None for t in IOU_THRESHOLDS):
                mean5095[cls] = sum((aps[t] for t in IOU_THRESHOLDS), Fraction(0)) / 10
        map5095 = sum(mean5095.values(), Fraction(0)) / len(mean5095) if mean5095 else None
        map_str[run] = (map50, map75, map5095)
    incumbent = result['incumbent']
    inc_map5095 = map_str[incumbent][2] if incumbent in map_str else None
    inc_map5095_s = fmt6(inc_map5095) if incumbent else None
    runs_list = []
    for run in reviewed:
        map50, map75, map5095 = map_str[run]
        prot = {}
        for cls in PROTECTED:
            mine = written_ap.get((run, cls))
            theirs = written_ap.get((incumbent, cls))
            if run == incumbent:
                prot[cls] = '0.000000'
            elif mine is None or theirs is None:
                prot[cls] = 'NA'
            else:
                a = Fraction(fmt6(mine))
                b = Fraction(fmt6(theirs))
                prot[cls] = fmt6(a - b)
        if run == incumbent:
            decision = 'INCUMBENT'
        else:
            mine_s = Fraction(fmt6(map5095)) if map5095 is not None else None
            inc_s = Fraction(inc_map5095_s) if inc_map5095_s not in (None, 'NA') else None
            ok = (mine_s is not None and inc_s is not None and mine_s - inc_s >= Fraction(5, 1000))
            if ok:
                for cls in PROTECTED:
                    mine = written_ap.get((run, cls))
                    theirs = written_ap.get((incumbent, cls))
                    if mine is None or theirs is None:
                        continue
                    a = Fraction(fmt6(mine))
                    b = Fraction(fmt6(theirs))
                    if b - a > Fraction(10, 1000):
                        ok = False
                        break
            decision = 'PROMOTE' if ok else 'HOLD'
        runs_list.append({
            'run_id': run,
            'model': runs[run]['model'],
            'map_50': fmt6(map50),
            'map_75': fmt6(map75),
            'map_50_95': fmt6(map5095),
            'protected_ap_50_delta': prot,
            'decision': decision,
        })
    promoted = [r['run_id'] for r in runs_list if r['decision'] == 'PROMOTE']
    release_candidate = None
    if promoted:
        best = None
        for rid in promoted:
            m = map_str[rid][2]
            if m is None:
                continue
            mv = Fraction(fmt6(m))
            if best is None or mv > best[1] or (mv == best[1] and rid < best[0]):
                best = (rid, mv)
        if best is not None:
            release_candidate = best[0]
    write_json(os.path.join(out_dir, 'leaderboard.json'), {
        'incumbent': incumbent,
        'release_candidate': release_candidate,
        'runs': runs_list,
    })

    # reconciliation.json
    excl_counts = {reason: 0 for reason in EXCLUSION_ORDER}
    for ident, reason in result['exclusions'].items():
        excl_counts[reason] = excl_counts.get(reason, 0) + 1
    gt_by_source = {'CAMPAIGN': 0, 'KS': 0, 'NL': 0, 'OB': 0}
    gt_total = 0
    ignore_total = 0
    for ident in evaluated:
        for g in gt_by_image.get(ident, []):
            gt_total += 1
            if g.ignore:
                ignore_total += 1
            if g.source in gt_by_source:
                gt_by_source[g.source] += 1
    deliveries = {}
    declared = declared_counts(estate)
    for name in sorted(declared):
        deliveries[name] = {
            'declared': declared[name],
            'parsed': count_parsed(estate, name),
        }
    write_json(os.path.join(out_dir, 'reconciliation.json'), {
        'freeze_list_ids': len(dict.fromkeys(result['freeze'])),
        'candidates': len(result['candidates']),
        'eval_images': len(evaluated),
        'excluded': excl_counts,
        'gt_boxes': gt_total,
        'ignore_regions': ignore_total,
        'gt_by_source': gt_by_source,
        'detections': {run: counts[run] for run in reviewed},
        'deliveries': deliveries,
    })


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.stderr.write('usage: evalctl.py ESTATE_DIR OUT_DIR\n')
        sys.exit(2)
    res = main(sys.argv[1], sys.argv[2])
    render(res, sys.argv[2])
