#!/usr/bin/env python3
"""VDO precise levelling recomputation (handbook revision 7).

Usage: python3 run_levelnet.py DATA_DIR OUT_DIR
"""

import csv
import hashlib
import json
import os
import re
import sqlite3
import sys
import zipfile
import zlib
from datetime import date, datetime, timedelta, timezone
from fractions import Fraction as Fr
from math import isqrt
from xml.etree import ElementTree as ET

# --------------------------------------------------------------------------
# numbers
# --------------------------------------------------------------------------


def dec(s):
    """Exact Fraction of a decimal string."""
    if s is None:
        return None
    s = str(s).strip().replace(' ', '')
    if s == '':
        return None
    neg = s.startswith('-')
    if s[0] in '+-':
        s = s[1:]
    if 'e' in s or 'E' in s:
        v = Fr(s)
        return -v if neg else v
    if '.' in s:
        a, b = s.split('.', 1)
        v = Fr(int(a or '0') * 10 ** len(b) + int(b or '0'), 10 ** len(b))
    else:
        v = Fr(int(s))
    return -v if neg else v


def rhe(x, nd):
    """Round a Fraction half to even to nd decimals, returning a Fraction."""
    scale = 10 ** nd
    y = Fr(x) * scale
    n, d = y.numerator, y.denominator
    q, r = divmod(n, d)
    twice = 2 * r
    if twice > d or (twice == d and q % 2 != 0):
        q += 1
    return Fr(q, scale)


def fmt(x, nd):
    """Format a Fraction with nd decimals, half to even, never negative zero."""
    if x is None:
        return ''
    scale = 10 ** nd
    y = Fr(x) * scale
    n, d = y.numerator, y.denominator
    q, r = divmod(n, d)
    twice = 2 * r
    if twice > d or (twice == d and q % 2 != 0):
        q += 1
    neg = q < 0
    q = abs(q)
    if nd == 0:
        s = str(q)
    else:
        s = str(q).rjust(nd + 1, '0')
        s = s[:-nd] + '.' + s[-nd:]
    if neg and q != 0:
        s = '-' + s
    return s


def sqrt_round(z, nd):
    """Round sqrt(z) (z a non-negative Fraction) half to even to nd decimals."""
    if z is None:
        return None
    z = Fr(z)
    if z < 0:
        z = Fr(0)
    y = z * (10 ** (2 * nd))
    a, b = y.numerator, y.denominator
    n = isqrt(a * b) // b
    lhs = 4 * a
    rhs = b * (2 * n + 1) ** 2
    if lhs > rhs or (lhs == rhs and n % 2 != 0):
        n += 1
    return Fr(n, 10 ** nd)


# --------------------------------------------------------------------------
# YAML (subset) parser; every scalar is returned as text or None
# --------------------------------------------------------------------------

def _strip_comment(line):
    out = []
    quote = None
    i = 0
    while i < len(line):
        c = line[i]
        if quote:
            out.append(c)
            if c == quote:
                quote = None
        elif c in '"\'':
            quote = c
            out.append(c)
        elif c == '#' and (i == 0 or line[i - 1] in ' \t'):
            break
        else:
            out.append(c)
        i += 1
    return ''.join(out).rstrip()


def _scalar(text):
    t = text.strip()
    if t == '' or t in ('~', 'null', 'Null', 'NULL'):
        return None
    if len(t) >= 2 and t[0] == t[-1] and t[0] in '"\'':
        body = t[1:-1]
        if t[0] == "'":
            return body.replace("''", "'")
        return body.replace('\\"', '"').replace('\\\\', '\\')
    return t


class _Flow:
    def __init__(self, s):
        self.s = s
        self.i = 0

    def ws(self):
        while self.i < len(self.s) and self.s[self.i] in ' \t':
            self.i += 1

    def parse(self):
        self.ws()
        c = self.s[self.i] if self.i < len(self.s) else ''
        if c == '[':
            self.i += 1
            out = []
            while True:
                self.ws()
                if self.i >= len(self.s):
                    break
                if self.s[self.i] == ']':
                    self.i += 1
                    break
                out.append(self.parse())
                self.ws()
                if self.i < len(self.s) and self.s[self.i] == ',':
                    self.i += 1
            return out
        if c == '{':
            self.i += 1
            out = {}
            while True:
                self.ws()
                if self.i >= len(self.s):
                    break
                if self.s[self.i] == '}':
                    self.i += 1
                    break
                k = self.parse_until(':,}')
                self.ws()
                if self.i < len(self.s) and self.s[self.i] == ':':
                    self.i += 1
                    v = self.parse()
                else:
                    v = None
                out[_scalar(k) if isinstance(k, str) else k] = v
                self.ws()
                if self.i < len(self.s) and self.s[self.i] == ',':
                    self.i += 1
            return out
        return _scalar(self.parse_until(',]}'))

    def parse_until(self, stops):
        self.ws()
        if self.i < len(self.s) and self.s[self.i] in '[{':
            return self.parse()
        start = self.i
        quote = None
        while self.i < len(self.s):
            c = self.s[self.i]
            if quote:
                if c == quote:
                    quote = None
            elif c in '"\'':
                quote = c
            elif c in stops:
                break
            self.i += 1
        return self.s[start:self.i].strip()


def _value_text(t):
    t = t.strip()
    if t.startswith('[') or t.startswith('{'):
        return _Flow(t).parse()
    return _scalar(t)


_KEY_RE = re.compile(r'^(?:"[^"]*"|\'[^\']*\'|[^:#]+?)\s*:(?:\s|$)')


class YamlParser:
    def __init__(self, text):
        self.lines = []
        for raw in text.replace('\r\n', '\n').replace('\r', '\n').split('\n'):
            if raw.strip() in ('---', '...'):
                continue
            s = _strip_comment(raw)
            if not s.strip():
                continue
            ind = len(s) - len(s.lstrip(' \t'))
            self.lines.append((ind, s.strip()))
        self.i = 0

    def peek(self):
        if self.i >= len(self.lines):
            return None, None
        return self.lines[self.i]

    def parse(self):
        if not self.lines:
            return None
        return self.node(self.lines[0][0])

    def node(self, indent):
        ind, content = self.peek()
        if ind is None or ind < indent:
            return None
        if content == '-' or content.startswith('- '):
            return self.seq(ind)
        return self.mapping(ind)

    def seq(self, indent):
        out = []
        while True:
            ind, content = self.peek()
            if ind != indent or not (content == '-' or content.startswith('- ')):
                break
            self.i += 1
            rest = content[1:]
            off = indent + 1 + (len(rest) - len(rest.lstrip(' ')))
            rest = rest.strip()
            if rest == '':
                out.append(self.deeper(indent))
            elif rest.startswith('[') or rest.startswith('{'):
                out.append(_value_text(rest))
            elif _KEY_RE.match(rest):
                out.append(self.mapping(off, first=rest))
            else:
                out.append(_scalar(rest))
        return out

    def mapping(self, indent, first=None):
        out = {}
        while True:
            if first is not None:
                content = first
                first = None
            else:
                ind, content = self.peek()
                if ind is None or ind != indent or not _KEY_RE.match(content):
                    break
                self.i += 1
            m = _KEY_RE.match(content)
            if not m:
                break
            kv = m.group(0)
            key = _scalar(kv[:kv.rstrip().rfind(':')])
            val = content[len(kv):].strip()
            if val == '':
                out[key] = self.deeper(indent)
            else:
                out[key] = _value_text(val)
        return out

    def deeper(self, indent):
        ind, content = self.peek()
        if ind is None:
            return None
        if ind > indent:
            return self.node(ind)
        if ind == indent and (content == '-' or content.startswith('- ')):
            return self.seq(ind)
        return None


def parse_yaml_text(text):
    return YamlParser(text).parse()


# --------------------------------------------------------------------------
# PDF text extraction (positions kept, rows rebuilt)
# --------------------------------------------------------------------------

def _pdf_unescape(s):
    out = []
    i = 0
    while i < len(s):
        c = s[i]
        if c == '\\' and i + 1 < len(s):
            n = s[i + 1]
            simple = {'n': '\n', 'r': '\r', 't': '\t', 'b': '\b', 'f': '\f',
                      '(': '(', ')': ')', '\\': '\\'}
            if n in simple:
                out.append(simple[n])
                i += 2
            elif n.isdigit():
                j = i + 1
                o = ''
                while j < len(s) and len(o) < 3 and s[j].isdigit():
                    o += s[j]
                    j += 1
                out.append(chr(int(o, 8)))
                i = j
            else:
                out.append(n)
                i += 2
        else:
            out.append(c)
            i += 1
    return ''.join(out)


_TOK_RE = re.compile(r'\((?:[^()\\]|\\.)*\)|<[0-9A-Fa-f\s]*>')


def _pdf_text_operand(body):
    res = ''
    for tok in _TOK_RE.finditer(body.strip()):
        t = tok.group(0)
        if t.startswith('('):
            res += _pdf_unescape(t[1:-1])
        else:
            hx = re.sub(r'\s', '', t[1:-1])
            if len(hx) % 2:
                hx += '0'
            try:
                res += bytes.fromhex(hx).decode('latin-1')
            except ValueError:
                pass
    return res


_PDF_OP_RE = re.compile(
    r'(?P<nums>(?:-?[\d.]+\s+){2,6})(?P<op>Tm|Td|TD)'
    r'|(?P<str>\[.*?\]|\((?:[^()\\]|\\.)*\)|<[0-9A-Fa-f\s]*>)\s*(?:TJ|Tj)', re.S)


def pdf_rows(path):
    """Return the text rows of a PDF (each row a list of (x, text) cells)."""
    with open(path, 'rb') as fh:
        data = fh.read()
    pages = []
    for m in re.finditer(rb'stream\r?\n', data):
        s = m.end()
        e = data.find(b'endstream', s)
        if e < 0:
            continue
        chunk = data[s:e]
        txt = None
        try:
            txt = zlib.decompress(chunk)
        except zlib.error:
            try:
                txt = zlib.decompressobj().decompress(chunk)
            except zlib.error:
                txt = chunk
        try:
            txt = txt.decode('latin-1')
        except Exception:
            continue
        if 'BT' not in txt:
            continue
        pages.append(txt)
    rows = []
    for page in pages:
        items = []
        for m in re.finditer(r'BT(.*?)ET', page, re.S):
            seg = m.group(1)
            x = y = 0.0
            for op in _PDF_OP_RE.finditer(seg):
                if op.group('op'):
                    nums = [float(v) for v in op.group('nums').split()]
                    if op.group('op') == 'Tm' and len(nums) >= 6:
                        x, y = nums[-2], nums[-1]
                    elif len(nums) >= 2:
                        x, y = x + nums[-2], y + nums[-1]
                    continue
                txt = _pdf_text_operand(op.group('str'))
                if txt:
                    items.append((y, x, txt))
        items.sort(key=lambda t: (-t[0], t[1]))
        cur = None
        line = []
        for y, x, t in items:
            if cur is None or abs(y - cur) > 0.6:
                if line:
                    rows.append(line)
                line = []
                cur = y
            line.append((x, t))
        if line:
            rows.append(line)
    return rows


# --------------------------------------------------------------------------
# XLSX reader
# --------------------------------------------------------------------------

_XN = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
_XO = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'


def read_xlsx(path):
    """Return (date1904, {sheet_name: [{column letter: text}]})."""
    z = zipfile.ZipFile(path)
    wb = ET.fromstring(z.read('xl/workbook.xml'))
    pr = wb.find(_XN + 'workbookPr')
    d1904 = pr is not None and (pr.get('date1904') or '').lower() in ('1', 'true')
    rels = {}
    for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels')):
        rels[r.get('Id')] = r.get('Target')
    sst = []
    try:
        for si in ET.fromstring(z.read('xl/sharedStrings.xml')):
            sst.append(''.join(t.text or '' for t in si.iter(_XN + 't')))
    except KeyError:
        pass
    sheets = {}
    for sh in wb.find(_XN + 'sheets'):
        tgt = rels.get(sh.get(_XO + 'id'))
        if not tgt:
            continue
        tgt = tgt.lstrip('/')
        if not tgt.startswith('xl/'):
            tgt = 'xl/' + tgt
        ws = ET.fromstring(z.read(tgt))
        rows = []
        for row in ws.iter(_XN + 'row'):
            cells = {}
            for c in row.iter(_XN + 'c'):
                ref = c.get('r') or ''
                mm = re.match(r'([A-Z]+)', ref)
                col = mm.group(1) if mm else ''
                t = c.get('t')
                v = c.find(_XN + 'v')
                isn = c.find(_XN + 'is')
                if t == 's' and v is not None:
                    val = sst[int(v.text)]
                elif t == 'inlineStr':
                    val = ''.join(x.text or '' for x in isn.iter(_XN + 't')) if isn is not None else ''
                else:
                    val = v.text if v is not None else ''
                cells[col] = (val or '').strip()
            rows.append(cells)
        sheets[sh.get('name')] = rows
    return d1904, sheets


def sheet_table(rows, first_header):
    """Rows of a sheet below its header row, as dicts keyed by header text."""
    hdr = None
    out = []
    for cells in rows:
        vals = [v for v in cells.values() if v]
        if hdr is None:
            if vals and vals[0].strip().lower() == first_header:
                hdr = {col: v.strip().lower() for col, v in cells.items() if v}
            continue
        if not vals:
            continue
        if len(vals) == 1 and vals[0].strip().lower() == 'continued':
            continue
        out.append({name: cells.get(col, '') for col, name in hdr.items()})
    return out


def xl_date(value, d1904):
    """A workbook date cell (serial number or ISO text) as a date."""
    v = (value or '').strip()
    if not v:
        return None
    if re.match(r'^\d{4}-\d{2}-\d{2}', v):
        return date(int(v[0:4]), int(v[5:7]), int(v[8:10]))
    try:
        n = int(round(float(v)))
    except ValueError:
        return None
    if d1904:
        return date(1904, 1, 1) + timedelta(days=n)
    if n >= 60:
        n -= 1
    return date(1899, 12, 31) + timedelta(days=n)


# --------------------------------------------------------------------------
# small readers
# --------------------------------------------------------------------------

def read_text(path):
    with open(path, 'r', encoding='utf-8', errors='replace') as fh:
        return fh.read()


def read_rows(path, delim):
    """Delimited file as a list of raw field lists (comments and blanks dropped)."""
    out = []
    with open(path, 'r', encoding='utf-8', errors='replace', newline='') as fh:
        for row in csv.reader(fh, delimiter=delim):
            if not row:
                continue
            if row[0].startswith('#'):
                continue
            out.append(row)
    return out


def read_dicts(path, delim):
    rows = read_rows(path, delim)
    if not rows:
        return [], []
    hdr = [h.strip() for h in rows[0]]
    out = []
    for r in rows[1:]:
        rec = {}
        for i, h in enumerate(hdr):
            rec[h] = r[i].strip() if i < len(r) else ''
        rec['__row__'] = r
        out.append(rec)
    return hdr, out


def read_ndjson(path):
    out = []
    for line in read_text(path).split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        out.append(obj)
    return out


def sql_rows(path, table):
    con = sqlite3.connect('file:%s?mode=ro' % path, uri=True)
    try:
        cur = con.execute('select * from %s' % table)
        names = [d[0] for d in cur.description]
        return [dict(zip(names, r)) for r in cur.fetchall()]
    finally:
        con.close()


def sql_tables(path):
    try:
        con = sqlite3.connect('file:%s?mode=ro' % path, uri=True)
    except sqlite3.Error:
        return set()
    try:
        return {r[0] for r in con.execute(
            "select name from sqlite_master where type='table'")}
    except sqlite3.Error:
        return set()
    finally:
        con.close()


def is_sqlite(path):
    try:
        with open(path, 'rb') as fh:
            return fh.read(16).startswith(b'SQLite format 3')
    except OSError:
        return False


# --------------------------------------------------------------------------
# dates and the site clock
# --------------------------------------------------------------------------

def pdate(s):
    """ISO date text to a date (None when empty)."""
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})', s)
    if not m:
        return None
    return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))


EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def ts_of(dt):
    return int((dt - EPOCH).total_seconds())


def iso_z(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def parse_offset(txt):
    m = re.match(r'^([+-])(\d{2}):?(\d{2})$', (txt or '').strip())
    if not m:
        return 0
    sec = int(m.group(2)) * 3600 + int(m.group(3)) * 60
    return sec if m.group(1) == '+' else -sec


def parse_iso_instant(txt):
    """ISO 8601 with Z or an explicit offset, to epoch seconds."""
    s = (txt or '').strip().replace(' ', 'T')
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?'
                 r'(?:\.\d+)?(Z|[+-]\d{2}:?\d{2})?$', s)
    if not m:
        raise ValueError('bad instant %r' % txt)
    y, mo, d, hh, mi = (int(m.group(i)) for i in range(1, 6))
    ss = int(m.group(6) or 0)
    off = m.group(7)
    base = ts_of(datetime(y, mo, d, hh, mi, ss, tzinfo=timezone.utc))
    if off and off != 'Z':
        base -= parse_offset(off)
    return base


def parse_wall(txt):
    """Local wall clock text to seconds counted as if it were UTC."""
    s = (txt or '').strip()
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})$', s)
    if not m:
        m = re.match(r'^(\d{4})(\d{2})(\d{2})[ T]?(\d{2})(\d{2})(\d{2})$', s)
    if not m:
        m2 = re.match(r'^(\d{2})\.(\d{2})\.(\d{4})[ T](\d{2}):(\d{2}):(\d{2})$', s)
        if not m2:
            raise ValueError('bad wall clock %r' % txt)
        d, mo, y, hh, mi, ss = (int(x) for x in m2.groups())
        return ts_of(datetime(y, mo, d, hh, mi, ss, tzinfo=timezone.utc))
    y, mo, d, hh, mi, ss = (int(x) for x in m.groups())
    return ts_of(datetime(y, mo, d, hh, mi, ss, tzinfo=timezone.utc))


class SiteClock:
    def __init__(self, doc):
        self.standard = parse_offset((doc or {}).get('standard_offset') or '+00:00')
        trs = []
        for t in (doc or {}).get('transitions') or []:
            trs.append((parse_iso_instant(t.get('utc')), parse_offset(t.get('offset'))))
        trs.sort()
        self.trs = trs
        self.offsets = sorted({o for _, o in trs} | {self.standard}, reverse=True)

    def offset_at(self, ts):
        lo, hi = 0, len(self.trs) - 1
        cur = self.standard
        while lo <= hi:
            mid = (lo + hi) // 2
            if self.trs[mid][0] <= ts:
                cur = self.trs[mid][1]
                lo = mid + 1
            else:
                hi = mid - 1
        return cur

    def local_to_utc(self, local_ts):
        for off in self.offsets:
            ts = local_ts - off
            if self.offset_at(ts) == off:
                return ts
        return local_ts - self.offset_at(local_ts)

    def local_date(self, ts):
        return datetime.fromtimestamp(ts + self.offset_at(ts), timezone.utc).date()


# --------------------------------------------------------------------------
# governance memo
# --------------------------------------------------------------------------

_TITLE_RE = re.compile(r'^Table\s+([A-Za-z]+-\d+)\s*(\(continued\))?\s*:\s*(.*?)'
                       r'\s*\[(IN FORCE|WITHDRAWN|SUPERSEDED)\]\s*$')
_ERRATUM_RE = re.compile(r'^Erratum\s+([^:]+):\s*(.*)$')
_STOP_WORDS = {'mark', 'class', 'column', 'row', 'heading', 'the', 'for', 'read',
               'value', 'entry', 'line', 'rod', 'type', 'and', 'of', 'table'}


class MemoTable:
    def __init__(self, tid, title, status):
        self.id = tid
        self.title = title
        self.status = status
        self.header = None
        self.rows = []

    def cols(self):
        return [t for _, t in (self.header or [])]

    def records(self):
        """Rows as lists of cell texts aligned to the header columns."""
        if self.header is None:
            return []
        xs = [x for x, _ in self.header]
        out = []
        for row in self.rows:
            cells = [''] * len(xs)
            for x, t in row:
                ci = min(range(len(xs)), key=lambda i: abs(xs[i] - x))
                cells[ci] = (cells[ci] + ' ' + t).strip() if cells[ci] else t
            out.append(cells)
        return out


def parse_memo(path):
    rows = pdf_rows(path)
    tables = {}
    order = []
    errata = []
    cur = None
    for row in rows:
        text = ' '.join(t for _, t in row).strip()
        if re.search(r'page\s+\d+\s+of\s+\d+', text, re.I):
            continue
        m = _TITLE_RE.match(text)
        if m:
            tid, cont, title, status = m.group(1), m.group(2), m.group(3), m.group(4)
            key = (tid, status)
            if cont and key in tables:
                cur = tables[key]
            else:
                cur = MemoTable(tid, title, status)
                while key in tables:
                    key = (key[0], key[1] + ' ')
                tables[key] = cur
                order.append(cur)
            if cont:
                cur.header = cur.header
                cur.pending_header = True
            else:
                cur.pending_header = True
            continue
        em = _ERRATUM_RE.match(text)
        if em:
            errata.append(text)
            cur = None
            continue
        if text.lower().startswith('errata'):
            cur = None
            continue
        if cur is None:
            continue
        if getattr(cur, 'pending_header', False):
            if cur.header is None:
                cur.header = row
            cur.pending_header = False
            continue
        if len(row) >= 1:
            cur.rows.append(row)
    in_force = {}
    for t in order:
        if t.status == 'IN FORCE' and t.id not in in_force:
            in_force[t.id] = t
    _apply_errata(in_force, errata)
    return in_force, order, errata


def _apply_errata(in_force, errata):
    for text in errata:
        em = _ERRATUM_RE.match(text)
        if not em:
            continue
        body = em.group(2)
        tm = re.match(r'\s*Table\s+([A-Za-z]+-\d+)\s*(.*)$', body)
        if not tm:
            continue
        tid, rest = tm.group(1), tm.group(2)
        vm = re.search(r'\bfor\s+(\S+)\s+read\s+(\S+?)[\.\s]*$', rest)
        if not vm:
            continue
        old, new = vm.group(1).strip(' ,.'), vm.group(2).strip(' ,.')
        if not re.match(r'^-?\d+(\.\d+)?$', old) or not re.match(r'^-?\d+(\.\d+)?$', new):
            continue
        table = in_force.get(tid)
        if table is None:
            continue
        desc = rest[:vm.start()]
        toks = [t for t in re.findall(r'[A-Za-z0-9][A-Za-z0-9\-\.]*', desc)
                if t.lower() not in _STOP_WORDS]
        hdr = [t.lower() for t in table.cols()]
        cell_values = set()
        for cells in table.records():
            cell_values.update(c.strip() for c in cells)
        row_toks = [t for t in toks if t in cell_values]
        col_toks = [t for t in toks if t not in cell_values
                    and any(t.lower() in h for h in hdr)]
        for row in table.rows:
            texts = [t.strip() for _, t in row]
            if row_toks and not all(any(rt == tx for tx in texts) for rt in row_toks):
                continue
            xs = [x for x, _ in (table.header or [])]
            for i, (x, t) in enumerate(row):
                if t.strip() != old:
                    continue
                if col_toks and xs:
                    ci = min(range(len(xs)), key=lambda k: abs(xs[k] - x))
                    if not all(ct.lower() in hdr[ci] for ct in col_toks):
                        continue
                row[i] = (x, new)


def memo_param_map(table):
    """A two column parameter/value table as a dict."""
    out = {}
    if table is None:
        return out
    for cells in table.records():
        if len(cells) >= 2 and cells[0]:
            out[cells[0].strip().lower()] = cells[1].strip()
    return out


# --------------------------------------------------------------------------
# field book shards
# --------------------------------------------------------------------------

FT = Fr(1200, 3937)
VOID_WORDS = {'1', 'true', 'yes', 'y', 'ja', 'void', 'voided', 'deleted', 'v'}


def truthy(v):
    if v is None:
        return False
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in VOID_WORDS


def d_m(s):
    return dec(s)


def d_dm(s):
    v = dec(s)
    return None if v is None else v / 10


def d_ft(s):
    v = dec(s)
    return None if v is None else rhe(v * FT, 1)


def r_m(s):
    return dec(s)


def r_mm(s):
    v = dec(s)
    return None if v is None else v / 1000


def r_e5(s):
    v = dec(s)
    return None if v is None else v / 100000


def t_c(s):
    if s is None:
        return None
    s = str(s).strip()
    if s in ('', '~', 'null', 'None'):
        return None
    return dec(s)


def t_f(s):
    v = t_c(s)
    return None if v is None else rhe((v - 32) * 5 / 9, 1)


def t_tenths(s):
    v = t_c(s)
    return None if v is None else v / 10


class Rec(object):
    __slots__ = ('file', 'order', 'run', 'seq', 'rev', 'void', 'ts',
                 'btok', 'ftok', 'pair', 'bs', 'fs', 'db', 'df', 'temp',
                 'prec', 'bser', 'fser', 'bm', 'fm', 'temp_src', 'dh', 'dh_raw')

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))


RUNID_RE = re.compile(r'^R?-?(\d{2})[-/]?(\d{4})$')


def norm_run(tok):
    if tok is None:
        return None
    s = str(tok).strip().upper().replace(' ', '')
    m = RUNID_RE.match(s)
    if m:
        return 'R-%s-%s' % (m.group(1), m.group(2))
    m = re.match(r'^R?-?(\d{2})\D?(\d{1,4})$', s)
    if m:
        return 'R-%s-%s' % (m.group(1), m.group(2).zfill(4))
    return None


def parse_L01(path, clock):
    _, recs = read_dicts(path, ',')
    out = []
    for r in recs:
        out.append(Rec(run=norm_run(r.get('run')), seq=int(r['setup']), rev=int(r['rev']),
                       void=truthy(r.get('void')),
                       ts=parse_iso_instant(r.get('time_utc')),
                       btok=r.get('rod_bs'), ftok=r.get('rod_fs'),
                       bs=r_m(r.get('bs_m')), fs=r_m(r.get('fs_m')),
                       db=d_m(r.get('dist_bs_m')), df=d_m(r.get('dist_fs_m')),
                       temp=t_c(r.get('rod_temp_c'))))
    return out


def parse_L02(path, clock):
    _, recs = read_dicts(path, '\t')
    out = []
    for r in recs:
        if not (r.get('run') or '').strip():
            continue
        out.append(Rec(run=norm_run(r.get('run')), seq=int(r['set']), rev=int(r['r']),
                       void=truthy(r.get('status')),
                       ts=parse_iso_instant(r.get('time')),
                       pair=(r.get('pair') or '').strip(),
                       bs=r_mm(r.get('bs_mm')), fs=r_mm(r.get('fs_mm')),
                       db=d_dm(r.get('dbs_dm')), df=d_dm(r.get('dfs_dm')),
                       temp=None))
    return out


def parse_L03(path, clock):
    _, recs = read_dicts(path, '|')
    out = []
    for r in recs:
        out.append(Rec(run=norm_run(r.get('RUN')), seq=int(r['SETUP']), rev=int(r['REV']),
                       void=truthy(r.get('VOIDED')),
                       ts=clock.local_to_utc(parse_wall(r.get('LOCAL_TIME'))),
                       btok=r.get('BACK_ROD'), ftok=r.get('FORE_ROD'),
                       bs=r_m(r.get('BACK_READING_M')), fs=r_m(r.get('FORE_READING_M')),
                       db=d_m(r.get('BACK_DIST_M')), df=d_m(r.get('FORE_DIST_M')),
                       temp=t_c(r.get('TEMP_C'))))
    return out


_L04_COLS = [('run', 0, 8), ('seq', 8, 12), ('rev', 12, 14), ('void', 14, 15),
             ('date', 15, 23), ('time', 23, 29), ('pair', 29, 33), ('bs', 33, 40),
             ('fs', 40, 47), ('dbs', 47, 51), ('dfs', 51, 55), ('temp', 55, 60)]


def parse_L04(path, clock):
    lines = read_text(path).split('\n')
    out = []
    for line in lines[2:]:
        if not line.strip():
            continue
        f = {n: line[a:b].strip() for n, a, b in _L04_COLS}
        if not f['run']:
            continue
        out.append(Rec(run=norm_run(f['run']), seq=int(f['seq']), rev=int(f['rev']),
                       void=truthy(f['void']),
                       ts=clock.local_to_utc(parse_wall(f['date'] + ' ' + f['time'])),
                       pair=f['pair'],
                       bs=r_e5(f['bs']), fs=r_e5(f['fs']),
                       db=d_dm(f['dbs']), df=d_dm(f['dfs']),
                       temp=t_tenths(f['temp'])))
    return out


def parse_L05(path, clock):
    out = []
    for o in read_ndjson(path):
        st = o.get('setup') or {}
        bs = o.get('bs') or {}
        fs = o.get('fs') or {}
        out.append(Rec(run=norm_run((o.get('run') or {}).get('id')),
                       seq=int(st.get('n')), rev=int(st.get('rev')),
                       void=truthy(st.get('void')),
                       ts=parse_iso_instant(o.get('time')),
                       btok=bs.get('rod'), ftok=fs.get('rod'),
                       bs=r_m(bs.get('r')), fs=r_m(fs.get('r')),
                       db=d_m(bs.get('d')), df=d_m(fs.get('d')),
                       temp=t_c(o.get('temp_c'))))
    return out


def parse_L06(path, clock):
    out = []
    for o in read_ndjson(path):
        out.append(Rec(run=norm_run(o.get('run_ref')), seq=int(o.get('seq')),
                       rev=int(o.get('rev')), void=truthy(o.get('deleted')),
                       ts=int(o.get('epoch_s')),
                       pair=(o.get('pair') or '').strip(),
                       bs=r_mm(o.get('bs_mm')), fs=r_mm(o.get('fs_mm')),
                       db=d_m(o.get('dbs_m')), df=d_m(o.get('dfs_m')),
                       temp=t_f(o.get('temp_f'))))
    return out


def parse_L07(path, clock):
    doc = json.loads(read_text(path))
    out = []
    for o in doc.get('setups') or []:
        b = o.get('back') or {}
        f = o.get('fore') or {}
        out.append(Rec(run=norm_run(o.get('run')), seq=int(o.get('seq')),
                       rev=int(o.get('revision')),
                       void=truthy(o.get('state')),
                       ts=parse_iso_instant(o.get('utc')),
                       btok=b.get('rod'), ftok=f.get('rod'),
                       bs=r_m(b.get('reading_m')), fs=r_m(f.get('reading_m')),
                       db=d_m(b.get('distance_m')), df=d_m(f.get('distance_m')),
                       temp=None))
    return out


def parse_L08(path, clock):
    root = ET.fromstring(read_text(path))
    out = []
    for e in root.iter('setup'):
        a = e.attrib
        out.append(Rec(run=norm_run(a.get('run')), seq=int(a.get('seq')),
                       rev=int(a.get('rev')), void=truthy(a.get('void')),
                       ts=clock.local_to_utc(parse_wall(a.get('local'))),
                       btok=a.get('brod'), ftok=a.get('frod'),
                       bs=r_mm(a.get('bs_mm')), fs=r_mm(a.get('fs_mm')),
                       db=d_dm(a.get('dbs_dm')), df=d_dm(a.get('dfs_dm')),
                       temp=t_c(a.get('temp_c'))))
    return out


def parse_L09(path, clock):
    doc = parse_yaml_text(read_text(path)) or {}
    out = []
    for o in doc.get('setups') or []:
        out.append(Rec(run=norm_run(o.get('run')), seq=int(o.get('set')),
                       rev=int(o.get('rev')), void=truthy(o.get('void')),
                       ts=parse_iso_instant(o.get('time')),
                       pair=(o.get('pair') or '').strip(),
                       bs=r_m(o.get('bs')), fs=r_m(o.get('fs')),
                       db=d_m(o.get('d_bs')), df=d_m(o.get('d_fs')),
                       temp=t_c(o.get('temp'))))
    return out


def parse_L10(path, clock):
    doc = parse_yaml_text(read_text(path)) or {}
    out = []
    for run, items in (doc.get('runs') or {}).items():
        for it in items or []:
            out.append(Rec(run=norm_run(run), seq=int(it[0]), rev=int(it[1]),
                           void=truthy(it[2]), ts=int(it[3]),
                           btok=it[4], ftok=it[5],
                           bs=r_mm(it[6]), fs=r_mm(it[7]),
                           db=d_m(it[8]), df=d_m(it[9]),
                           temp=None))
    return out


def parse_L11(path, clock):
    out = []
    for line in read_text(path).split('\n'):
        s = line.strip()
        if not s.startswith('|'):
            continue
        cells = [c.strip() for c in s.strip('|').split('|')]
        if len(cells) < 12:
            continue
        if re.match(r'^-+$', cells[0].replace(' ', '')) or cells[0].lower() == 'run':
            continue
        if not norm_run(cells[0]):
            continue
        out.append(Rec(run=norm_run(cells[0]), seq=int(cells[1]), rev=int(cells[2]),
                       void=truthy(cells[3]),
                       ts=clock.local_to_utc(parse_wall(cells[4])),
                       btok=cells[5], ftok=cells[6],
                       bs=r_m(cells[7]), fs=r_m(cells[8]),
                       db=d_m(cells[9]), df=d_m(cells[10]),
                       temp=t_f(cells[11])))
    return out


def parse_L12(path, clock):
    out = []
    for r in sql_rows(path, 'obs'):
        out.append(Rec(run=norm_run(r.get('run')), seq=int(r.get('seq')),
                       rev=int(r.get('rev')), void=truthy(r.get('void')),
                       ts=int(r.get('epoch')),
                       pair=(r.get('pair') or '').strip(),
                       bs=r_e5(r.get('bs')), fs=r_e5(r.get('fs')),
                       db=d_dm(r.get('dbs')), df=d_dm(r.get('dfs')),
                       temp=t_c(r.get('temp_c'))))
    return out


def parse_L13(path, clock):
    keys = sql_rows(path, 'setup_key')
    attrs = {}
    for a in sql_rows(path, 'setup_attr'):
        attrs.setdefault(a['uid'], {})[a['attr']] = a['value']
    out = []
    for k in keys:
        at = attrs.get(k['uid'], {})
        out.append(Rec(run=norm_run(k.get('run')), seq=int(k.get('seq')),
                       rev=int(k.get('rev')), void=truthy(at.get('void')),
                       ts=parse_iso_instant(at.get('time_utc')),
                       btok=at.get('rod_b'), ftok=at.get('rod_f'),
                       bs=r_m(at.get('bs_m')), fs=r_m(at.get('fs_m')),
                       db=d_m(at.get('dist_b_m')), df=d_m(at.get('dist_f_m')),
                       temp=t_c(at.get('temp_c'))))
    return out


def parse_L14(path, clock):
    _, recs = read_dicts(path, ';')

    def cm(v):
        return (v or '').replace(',', '.')
    out = []
    for r in recs:
        out.append(Rec(run=norm_run(r.get('run')), seq=int(r['opstelling']),
                       rev=int(r['rev']), void=truthy(r.get('vervallen')),
                       ts=clock.local_to_utc(parse_wall(r.get('tijd'))),
                       btok=r.get('baak_a'), ftok=r.get('baak_v'),
                       bs=r_mm(cm(r.get('a_mm'))), fs=r_mm(cm(r.get('v_mm'))),
                       db=d_m(cm(r.get('afst_a_m'))), df=d_m(cm(r.get('afst_v_m'))),
                       temp=t_c(cm(r.get('temp_c')))))
    return out


def parse_L15(path, clock):
    _, recs = read_dicts(path, '\t')
    out = []
    for r in recs:
        out.append(Rec(run=norm_run(r.get('run')), seq=int(r['seq']), rev=int(r['rev']),
                       void=truthy(r.get('void')),
                       ts=parse_iso_instant(r.get('time')),
                       btok=r.get('rod_b'), ftok=r.get('rod_f'),
                       bs=r_m(r.get('bs_m')), fs=r_m(r.get('fs_m')),
                       db=d_ft(r.get('dist_b_ft')), df=d_ft(r.get('dist_f_ft')),
                       temp=t_f(r.get('temp_f'))))
    return out


def parse_L16(path, clock):
    root = ET.fromstring(read_text(path))
    out = []
    for e in root.iter('setup'):
        g = {c.tag: (c.text or '').strip() for c in e}
        out.append(Rec(run=norm_run(g.get('run')), seq=int(g.get('seq')),
                       rev=int(g.get('rev')), void=truthy(g.get('void')),
                       ts=parse_iso_instant(g.get('utc')),
                       pair=g.get('pair'),
                       bs=r_e5(g.get('bs')), fs=r_e5(g.get('fs')),
                       db=d_ft(g.get('dbs_ft')), df=d_ft(g.get('dfs_ft')),
                       temp=None))
    return out


LAYOUTS = {
    'L01': parse_L01, 'L02': parse_L02, 'L03': parse_L03, 'L04': parse_L04,
    'L05': parse_L05, 'L06': parse_L06, 'L07': parse_L07, 'L08': parse_L08,
    'L09': parse_L09, 'L10': parse_L10, 'L11': parse_L11, 'L12': parse_L12,
    'L13': parse_L13, 'L14': parse_L14, 'L15': parse_L15, 'L16': parse_L16,
}


def parse_shard(path, layout, clock):
    recs = LAYOUTS[layout](path, clock)
    name = os.path.basename(path)
    for i, r in enumerate(recs):
        r.file = name
        r.order = i
    return recs


def sniff_shard(path, clock):
    """True when the file parses as a setup shard under some layout."""
    for layout, fn in sorted(LAYOUTS.items()):
        try:
            recs = fn(path, clock)
        except Exception:
            continue
        if len(recs) >= 3 and all(r.run and r.seq is not None and r.rev is not None
                                  and r.bs is not None and r.fs is not None
                                  for r in recs[:5]):
            return True
    return False


# --------------------------------------------------------------------------
# campaign input
# --------------------------------------------------------------------------

RUNREG_HDR = ['run_id', 'campaign', 'start_bm', 'end_bm', 'booked', 'level', 'pair',
              'observer', 'setups', 'status', 'note']
BM_HDR = ['mark', 'block', 'description', 'established', 'status', 'easting', 'northing']
STATION_HDR = ['station_id', 'tokens', 'name', 'log_file', 'unit', 'status']


def _first_row(text, delim):
    for line in text.split('\n'):
        if not line.strip() or line.startswith('#'):
            continue
        return [c.strip() for c in next(csv.reader([line], delimiter=delim))]
    return []


class Inputs:
    """Everything read from the campaign folder."""

    def __init__(self, data_dir):
        self.dir = data_dir
        self.names = sorted(os.listdir(data_dir))
        self.memo_path = None
        self.wb_path = None
        self.catalog = None
        self.runreg = None
        self.amendments = []
        self.sections = []
        self.lines = None
        self.marks = []
        self.alias_path = None
        self.tp_path = None
        self.ep_path = None
        self.stations = []
        self.roster = []
        self.loops = None
        self.legacy_rods = None
        self.journal = None
        self.addendum = None
        self.profile = None
        self.overlay = None
        self.clock_doc = None
        self.qrc = None
        self.bulletin = None
        self.pub_heights = []
        self.pub_rates = None
        self.dashboard = []
        self.cache = []
        self.runpack = None
        self.candidates = []
        self._classify()

    def path(self, name):
        return os.path.join(self.dir, name)

    def _classify(self):
        for name in self.names:
            path = self.path(name)
            if not os.path.isfile(path):
                continue
            ext = name.rsplit('.', 1)[-1].lower() if '.' in name else ''
            if ext == 'pdf':
                self.memo_path = path
                continue
            if ext == 'xlsx':
                self.wb_path = path
                continue
            if is_sqlite(path):
                tabs = sql_tables(path)
                if 'bm_alias' in tabs:
                    self.alias_path = path
                elif {'instrument_alias', 'two_peg'} <= tabs:
                    self.tp_path = path
                elif {'epochs', 'heights'} <= tabs:
                    self.ep_path = path
                else:
                    self.candidates.append(name)
                continue
            try:
                text = read_text(path)
            except OSError:
                continue
            if self._try_json(name, text):
                continue
            if self._try_ndjson(name, text):
                continue
            if self._try_xml(name, text):
                continue
            if self._try_delim(name, text):
                continue
            if self._try_yaml(name, text):
                continue
            if self._try_doc(name, text):
                continue
            self.candidates.append(name)

    def _try_json(self, name, text):
        t = text.lstrip()
        if not t.startswith('{'):
            return False
        try:
            obj = json.loads(text)
        except ValueError:
            return False
        if not isinstance(obj, dict):
            return False
        if 'catalog' in obj and 'entries' in obj:
            self.catalog = obj
        elif str(obj.get('register', '')).lower() == 'levelling lines' and 'lines' in obj:
            self.lines = obj
        elif 'rates' in obj:
            self.pub_rates = obj
        elif 'setups' in obj:
            self.candidates.append(name)
        else:
            self.candidates.append(name)
        return True

    def _try_ndjson(self, name, text):
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        if not lines or not all(l.startswith('{') for l in lines):
            return False
        objs = []
        for l in lines:
            try:
                objs.append(json.loads(l))
            except ValueError:
                return False
        keys = set()
        for o in objs[:20]:
            if isinstance(o, dict):
                keys |= set(o.keys())
        if {'amend_no', 'campaign', 'run', 'field', 'value'} <= keys:
            self.amendments = objs
        elif {'observer', 'level', 'valid_from', 'valid_to'} <= keys:
            self.roster = objs
        elif {'mark', 'epoch', 'height_m'} <= keys:
            self.cache = objs
        else:
            self.candidates.append(name)
        return True

    def _try_xml(self, name, text):
        if not text.lstrip().startswith('<'):
            return False
        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            return False
        tag = root.tag.lower()
        if tag == 'journal':
            self.journal = root
        elif tag == 'addendum':
            self.addendum = root
        else:
            self.candidates.append(name)
        return True

    def _try_delim(self, name, text):
        for delim in (',', '\t', '|', ';'):
            hdr = _first_row(text, delim)
            if len(hdr) < 2:
                continue
            low = [h.lower() for h in hdr]
            if low == RUNREG_HDR:
                _, self.runreg = read_dicts(self.path(name), delim)
                return True
            if low[:4] == ['section_id', 'from_mark', 'to_mark', 'line_id']:
                _, self.sections = read_dicts(self.path(name), delim)
                return True
            if low == BM_HDR:
                self.marks = [r[0].strip() for r in read_rows(self.path(name), delim)[1:]
                              if r and r[0].strip()]
                return True
            if low == STATION_HDR:
                _, self.stations = read_dicts(self.path(name), delim)
                return True
            if low == ['section_id', 'status', 'updated']:
                _, self.dashboard = read_dicts(self.path(name), delim)
                return True
            if low == ['mark', 'height_m', 'status']:
                _, self.pub_heights = read_dicts(self.path(name), delim)
                return True
            if low[:2] == ['epoch_s', 'temp_c'] or low[:2] == ['utc', 'temp']:
                self.metlogs = getattr(self, 'metlogs', [])
                self.metlogs.append(name)
                return True
        return False

    def _try_yaml(self, name, text):
        try:
            doc = parse_yaml_text(text)
        except Exception:
            return False
        if not isinstance(doc, dict):
            return False
        if 'campaign_id' in doc:
            self.profile = doc
        elif 'overlay' in doc:
            self.overlay = doc
        elif 'transitions' in doc:
            self.clock_doc = doc
        elif 'loops' in doc:
            self.loops = doc
        elif 'rods' in doc:
            self.legacy_rods = doc
        else:
            return False
        return True

    def _try_doc(self, name, text):
        """Plain documents: the reference card, the bulletin and the run pack.

        The handbook, the contract and the layout notes mention the phrases the
        other documents are recognised by, so they are set aside first.
        """
        low = text.lower()
        for marker in ('recomputation handbook', 'h1 authority', '# output contract',
                       'field book shard layouts', 'every shard holds setup records'):
            if marker in low:
                return True
        if 'mean earth radius' in low:
            self.qrc = text
            return True
        if 'operational notice' in low or 'field bulletin' in low:
            self.bulletin = text
            return True
        if 'run pack' in low and '## settings' in low:
            self.runpack = text
            return True
        return False


# --------------------------------------------------------------------------
# engine
# --------------------------------------------------------------------------

def first_digits(tok):
    m = re.search(r'\d+', str(tok or ''))
    if not m:
        return ''
    return str(int(m.group(0)))


class Engine:
    def __init__(self, data_dir):
        self.inp = Inputs(data_dir)
        self.bm_log = {}
        self._load_memo()
        self._load_settings()
        self._load_workbook()
        self._load_registers()
        self._read_shards()
        self._settle()
        self._build_runs()
        self._sections()
        self._control()
        self._adjust()
        self._loops()
        self._rates()

    # ---------------- governance ----------------

    def _load_memo(self):
        self.tables, self.memo_order, self.errata = parse_memo(self.inp.memo_path)
        t = self.tables
        tol = {}
        for cells in t['T-1'].records():
            if cells[0]:
                tol[cells[0].strip()] = (dec(cells[1]), dec(cells[2]))
        self.tol_section = {k: v[0] for k, v in tol.items()}
        self.tol_loop = {k: v[1] for k, v in tol.items()}
        self.tol_text = {k: (cells[1], cells[2]) for k, cells in
                         [(c[0].strip(), c) for c in t['T-1'].records()] if k}
        k1 = memo_param_map(t['K-1'])
        self.sigma_class = {}
        self.sigma_text = {}
        for key, val in k1.items():
            m = re.match(r'^sigma class (\S+) mm', key)
            if m:
                self.sigma_class[m.group(1).upper()] = dec(val)
                self.sigma_text[m.group(1).upper()] = val
        self.critical_w = dec(k1.get('critical value of w'))
        self.critical_w_text = k1.get('critical value of w')
        self.min_redundancy = int(dec(k1.get('minimum redundancy after a removal')))
        self.max_removals = int(dec(k1.get('maximum removals per component')))
        i1 = memo_param_map(t['I-1'])
        self.collimation_limit = dec(i1.get('collimation limit mm per 100 m'))
        self.collimation_limit_text = i1.get('collimation limit mm per 100 m')
        self.refraction_k = dec(i1.get('refraction coefficient'))
        self.refraction_k_text = i1.get('refraction coefficient')
        self.rod_types = {}
        for cells in t['A-1'].records():
            if cells[0]:
                self.rod_types[cells[0].strip()] = (cells[1].strip(), dec(cells[2]),
                                                    cells[2].strip())
        r1 = memo_param_map(t['R-1'])
        self.alert_rate = dec(r1.get('alert rate mm per yr'))
        self.alert_rate_text = r1.get('alert rate mm per yr')
        self.k_rate = dec(r1.get('significance factor'))
        self.k_rate_text = r1.get('significance factor')
        self.control_table = {}
        for cells in t['C-2'].records():
            if cells[0] and re.match(r'^-?\d', cells[1] or ''):
                self.control_table[cells[0].strip()] = dec(cells[1])
        m = re.search(r'adjustment\s+(\S+)', t['C-2'].title or '')
        self.control_epoch = m.group(1) if m else ''
        self.chi2 = {}
        for cells in t['X-2'].records():
            if cells[0] and cells[0].strip().isdigit():
                self.chi2[int(cells[0])] = (dec(cells[1]), dec(cells[2]))
        self.rulings_table = []
        cols = [c.lower() for c in t['J-1'].cols()]
        for cells in t['J-1'].records():
            rec = dict(zip(cols, [c.strip() for c in cells]))
            if rec.get('ruling'):
                self.rulings_table.append(rec)
        # quick reference card: the mean earth radius only
        m = re.search(r'mean earth radius[^\d]*([\d.]+)', self.inp.qrc or '', re.I)
        self.earth_radius_text = m.group(1) if m else '6371000'
        self.earth_radius = dec(self.earth_radius_text)

    def _load_settings(self):
        prof = self.inp.profile or {}
        self.campaign = prof.get('campaign_id')
        self.reference_date = pdate(prof.get('reference_date'))
        self.epoch_reference = prof.get('epoch_reference')
        self.settings = {
            'rod_certificate_sheet': prof.get('rod_certificate_sheet'),
            'fallback_temp_c': prof.get('fallback_temp_c'),
            'met_max_gap_min': prof.get('met_max_gap_min'),
        }
        for entry in (self.inp.overlay or {}).get('overlay') or []:
            if entry.get('campaign') != self.campaign:
                continue
            eff = pdate(entry.get('effective'))
            if eff is None or eff > self.reference_date:
                continue
            self.settings[entry.get('key')] = entry.get('value')
        self.cert_sheet = self.settings['rod_certificate_sheet']
        self.fallback_temp = dec(self.settings['fallback_temp_c'])
        self.met_gap = int(dec(self.settings['met_max_gap_min']))
        self.clock = SiteClock(self.inp.clock_doc)
        self.rod_pairs = {}
        for pid, pair in (prof.get('rod_pairs') or {}).items():
            self.rod_pairs[pid] = [first_digits(p) for p in pair]
        self.line_stations = prof.get('line_stations') or {}
        self.control_tokens = [str(t) for t in (prof.get('control_points') or [])]

    def _load_workbook(self):
        self.d1904, sheets = read_xlsx(self.inp.wb_path)
        self.rod_type_of = {}
        self.former = {}
        for row in sheet_table(sheets.get('Rods') or [], 'serial'):
            ser = first_digits(row.get('serial'))
            if not ser:
                continue
            self.rod_type_of[ser] = (row.get('type') or '').strip()
            fs = first_digits(row.get('former_serial'))
            if fs:
                self.former[fs] = ser
        self.certs = {}
        rows = sheet_table(sheets.get(self.cert_sheet) or [], 'rod_serial')
        for row in rows:
            ser = first_digits(row.get('rod_serial'))
            if not ser:
                continue
            vf = xl_date(row.get('valid_from'), self.d1904)
            vt = xl_date(row.get('valid_to'), self.d1904)
            self.certs.setdefault(ser, []).append({
                'certificate': (row.get('certificate') or '').strip(),
                'scale': dec(row.get('scale_ppm')),
                't0': dec(row.get('t0_c')),
                'valid_from': vf,
                'valid_to': vt,
            })
        for ser in self.certs:
            self.certs[ser].sort(key=lambda c: (c['valid_from'] or date.min,
                                                c['certificate']))

    def rod_serial(self, token):
        ser = first_digits(token)
        return self.former.get(ser, ser)

    def rod_type(self, serial):
        t = self.rod_type_of.get(serial)
        if t:
            return t
        return self.legacy_type.get(serial, '')

    def rod_graduation(self, serial):
        info = self.rod_types.get(self.rod_type(serial))
        return info[0] if info else 'FULL'

    def rod_alpha(self, serial):
        info = self.rod_types.get(self.rod_type(serial))
        return info[1] if info else Fr(0)

    def certificate(self, serial, d):
        best = None
        for c in self.certs.get(serial, []):
            if c['valid_from'] is None or c['valid_to'] is None:
                continue
            if c['valid_from'] <= d <= c['valid_to']:
                if best is None or c['valid_from'] >= best['valid_from']:
                    best = c
        return best

    # ---------------- registers ----------------

    def _load_registers(self):
        self.legacy_type = {}
        for r in (self.inp.legacy_rods or {}).get('rods') or []:
            ser = first_digits(r.get('serial'))
            if ser:
                self.legacy_type[ser] = (r.get('type') or '').strip()
        self.alias_rows = sql_rows(self.inp.alias_path, 'bm_alias')
        self.alias_by_token = {}
        for r in self.alias_rows:
            self.alias_by_token.setdefault((r.get('token') or '').strip(), []).append(r)
        self.mark_set = set(self.inp.marks)
        self.instr_alias = {}
        for r in sql_rows(self.inp.tp_path, 'instrument_alias'):
            self.instr_alias[(r.get('token') or '').strip().upper()] = r.get('instrument')
        self.two_peg = {}
        for r in sql_rows(self.inp.tp_path, 'two_peg'):
            if (r.get('result') or '').strip().upper() == 'RETEST':
                continue
            self.two_peg.setdefault(r.get('instrument'), []).append({
                'test_id': r.get('test_id'),
                'ts': parse_iso_instant(r.get('tested_utc')),
                'c': dec(r.get('c_mm_per_100m')),
            })
        for k in self.two_peg:
            self.two_peg[k].sort(key=lambda t: (t['ts'], t['test_id']))
        self.epochs = {r['epoch_id']: r for r in sql_rows(self.inp.ep_path, 'epochs')}
        self.epoch_heights = {}
        for r in sql_rows(self.inp.ep_path, 'heights'):
            self.epoch_heights.setdefault(r['epoch_id'], []).append(r)
        self.station_by_token = {}
        self.station_by_id = {}
        for r in self.inp.stations:
            sid = (r.get('station_id') or '').strip()
            self.station_by_id[sid] = r
            toks = [sid] + [t.strip() for t in (r.get('tokens') or '').split(';')]
            for t in toks:
                if t:
                    self.station_by_token[t.upper()] = r
        self.roster = {}
        for r in self.inp.roster:
            self.roster.setdefault(str(r.get('observer') or '').upper(), []).append(r)
        self.line_class_hist = {}
        for ln in (self.inp.lines or {}).get('lines') or []:
            self.line_class_hist[ln.get('line')] = ln.get('class_history') or []
        self._load_journal()
        self._load_rulings()
        self._load_notices()
        self._metlog_cache = {}

    def _load_journal(self):
        entries = []
        cancelled = set()
        for e in (self.inp.journal if self.inp.journal is not None else []):
            a = e.attrib
            try:
                eid = int(a.get('id'))
            except (TypeError, ValueError):
                continue
            ev = (a.get('event') or '').strip().upper()
            entries.append({'id': eid, 'mark': (a.get('mark') or '').strip(),
                            'event': ev, 'date': pdate(a.get('date')),
                            'refers': (a.get('refers') or '').strip()})
            if ev == 'ERRATUM' and a.get('refers'):
                try:
                    cancelled.add(int(a.get('refers')))
                except ValueError:
                    pass
        entries.sort(key=lambda e: e['id'])
        self.journal_entries = entries
        self.journal_cancelled = cancelled

    def _load_rulings(self):
        cancel = set()
        reject_run = {}
        reject_sec = {}
        for r in (self.inp.addendum if self.inp.addendum is not None else []):
            a = r.attrib
            if a.get('campaign') != self.campaign:
                continue
            issued = pdate(a.get('issued'))
            if issued is None or issued > self.reference_date:
                continue
            action = (a.get('action') or '').strip().upper()
            target = (a.get('target') or '').strip()
            if action == 'CANCEL':
                cancel.add(target)
            elif action == 'REJECT_RUN':
                reject_run[target] = a.get('id')
            elif action == 'REJECT_SECTION':
                reject_sec[target] = a.get('id')
        for rec in self.rulings_table:
            eff = pdate(rec.get('effective'))
            if eff is None or eff > self.reference_date:
                continue
            if rec.get('ruling') in cancel:
                continue
            action = (rec.get('action') or '').upper()
            target = rec.get('target')
            if action == 'REJECT_RUN':
                reject_run[target] = rec.get('ruling')
            elif action == 'REJECT_SECTION':
                reject_sec[target] = rec.get('ruling')
        self.ruled_runs = reject_run
        self.ruled_sections = reject_sec

    def _load_notices(self):
        self.notices = []
        text = self.inp.bulletin or ''
        blocks = re.split(r'\n\s*\n', text)
        for b in blocks:
            if 'OPERATIONAL NOTICE' not in b.upper():
                continue
            status = ''
            ms = re.search(r'status:\s*(.+)', b)
            if ms:
                status = ms.group(1).strip().upper()
            mc = re.search(r'campaign:\s*(\S+)', b)
            camp = mc.group(1).strip() if mc else ''
            if status != 'IN FORCE' or camp != self.campaign:
                continue
            mst = re.search(r'met station\s+(\S+)', b, re.I)
            mdt = re.search(r'from\s+(\d{4}-\d{2}-\d{2})\s+to\s+(\d{4}-\d{2}-\d{2})', b)
            msub = re.search(r'substitute station:\s*(\S+)', b, re.I)
            if not (mst and mdt and msub):
                continue
            self.notices.append({'station': mst.group(1).strip(),
                                 'from': pdate(mdt.group(1)),
                                 'to': pdate(mdt.group(2)),
                                 'sub': msub.group(1).strip()})

    # ---------------- benchmark tokens ----------------

    def norm_token(self, tok):
        t = str(tok or '').strip().upper().replace(' ', '')
        m = re.match(r'^VD-?(\d{1,4})$', t)
        if m:
            return 'VD-' + m.group(1).zfill(4)
        m = re.match(r'^(\d{1,4})$', t)
        if m:
            return 'VD-' + m.group(1).zfill(4)
        m = re.match(r'^MB-?(\d{1,3})$', t)
        if m:
            return 'MB-' + m.group(1).zfill(3)
        return t

    def resolve_bm(self, context, token, d, log=True):
        key = (context, str(token), d.isoformat())
        if log and key in self.bm_log:
            return self.bm_log[key]
        cur = self.norm_token(token)
        hops = 0
        for _ in range(64):
            best = None
            for r in self.alias_by_token.get(cur, []):
                vf = pdate(r.get('valid_from'))
                vt = pdate(r.get('valid_to'))
                if vf is None or vf > d:
                    continue
                if vt is not None and vt <= d:
                    continue
                if best is None or vf > pdate(best.get('valid_from')):
                    best = r
            if best is None:
                break
            cur = (best.get('canonical') or '').strip()
            hops += 1
        ok = cur in self.mark_set
        res = (cur if ok else '', hops, 'RESOLVED' if ok else 'UNRESOLVED')
        if log:
            self.bm_log[key] = res
        return res

    # ---------------- shards and settlement ----------------

    def _read_shards(self):
        entries = (self.inp.catalog or {}).get('entries') or []
        present = {n for n in self.inp.names
                   if os.path.isfile(self.inp.path(n))}
        metlogs = {(r.get('log_file') or '').strip() for r in self.inp.stations}
        metlogs |= {os.path.basename(m) for m in metlogs}
        read_list = []
        for e in entries:
            if e.get('campaign') != self.campaign:
                continue
            if (e.get('status') or '').upper() != 'ACTIVE':
                continue
            if e.get('file') not in present:
                continue
            if e.get('layout') not in LAYOUTS:
                continue
            read_list.append(e)
        self.read_entries = read_list
        self.read_files = [e['file'] for e in read_list]
        self.prec_of = {e['file']: i for i, e in enumerate(read_list)}
        self.records = []
        self.file_stats = {}
        for e in read_list:
            recs = parse_shard(self.inp.path(e['file']), e['layout'], self.clock)
            for r in recs:
                r.prec = self.prec_of[e['file']]
            self.records.extend(recs)
            self.file_stats[e['file']] = {'file': e['file'], 'status': 'READ',
                                          'records': len(recs), 'kept': 0,
                                          'superseded': 0, 'void_selected': 0,
                                          'duplicates': 0, 'conflicts_lost': 0}
        cat_status = {}
        for e in entries:
            if e.get('file') in present:
                cat_status.setdefault(e['file'], (e.get('status') or '').upper())
        ignored = set(f for f in cat_status if f not in self.prec_of)
        for name in self.inp.candidates:
            if name in self.prec_of or name in metlogs:
                continue
            try:
                if sniff_shard(self.inp.path(name), self.clock):
                    ignored.add(name)
            except Exception:
                pass
        self.ignored_files = sorted(ignored)
        for name in self.ignored_files:
            self.file_stats[name] = {
                'file': name,
                'status': 'RETIRED' if cat_status.get(name) == 'RETIRED' else 'UNCATALOGUED',
                'records': 0, 'kept': 0, 'superseded': 0, 'void_selected': 0,
                'duplicates': 0, 'conflicts_lost': 0}

    def _load_runreg(self):
        self.run_rows = {}
        order = []
        for r in self.inp.runreg or []:
            if r.get('campaign') != self.campaign:
                continue
            rid = (r.get('run_id') or '').strip()
            rec = {'run_id': rid, 'start_bm': r.get('start_bm'), 'end_bm': r.get('end_bm'),
                   'booked': r.get('booked'), 'level': r.get('level'),
                   'pair': (r.get('pair') or '').strip(), 'observer': r.get('observer'),
                   'setups': r.get('setups'), 'status': r.get('status')}
            self.run_rows[rid] = rec
            order.append(rid)
        self.run_order = sorted(order)
        amends = []
        for a in self.inp.amendments or []:
            if a.get('campaign') != self.campaign:
                continue
            try:
                no = int(a.get('amend_no'))
            except (TypeError, ValueError):
                continue
            amends.append((no, a))
        amends.sort(key=lambda t: t[0])
        for _, a in amends:
            rid = (a.get('run') or '').strip()
            if rid not in self.run_rows:
                continue
            field = (a.get('field') or '').strip()
            if field in ('status', 'setups', 'level', 'observer'):
                self.run_rows[rid][field] = a.get('value')

    def _rods_of(self, rec):
        if rec.btok or rec.ftok:
            return self.rod_serial(rec.btok), self.rod_serial(rec.ftok)
        row = self.run_rows.get(rec.run)
        pair = (row or {}).get('pair') or ''
        pr = self.rod_pairs.get(pair)
        if not pr or len(pr) < 2:
            return '', ''
        a = self.former.get(pr[0], pr[0])
        b = self.former.get(pr[1], pr[1])
        if rec.seq % 2 == 1:
            return a, b
        return b, a

    def _settle(self):
        self._load_runreg()
        for r in self.records:
            r.bser, r.fser = self._rods_of(r)
            r.bm = r.bs / 2 if self.rod_graduation(r.bser) == 'HALF' else r.bs
            r.fm = r.fs / 2 if self.rod_graduation(r.fser) == 'HALF' else r.fs
        groups = {}
        for r in self.records:
            groups.setdefault((r.run, r.seq), []).append(r)
        self.kept = {}
        self.void_setups = []
        counts = {'records_read': len(self.records), 'setup_keys': len(groups),
                  'superseded_revisions': 0, 'duplicates': 0, 'conflicts': 0,
                  'void_setups': 0, 'kept_setups': 0}
        for key in sorted(groups, key=lambda k: (k[0] or '', k[1] or 0)):
            group = groups[key]
            maxrev = max(r.rev for r in group)
            comp = sorted((r for r in group if r.rev == maxrev),
                          key=lambda r: (r.prec, r.order))
            low = [r for r in group if r.rev < maxrev]
            counts['superseded_revisions'] += len(low)
            for r in low:
                self.file_stats[r.file]['superseded'] += 1
            winner = comp[0]
            wkey = self._content(winner)
            for r in comp[1:]:
                if self._content(r) == wkey:
                    counts['duplicates'] += 1
                    self.file_stats[r.file]['duplicates'] += 1
                else:
                    counts['conflicts'] += 1
                    self.file_stats[r.file]['conflicts_lost'] += 1
            if winner.void:
                counts['void_setups'] += 1
                self.file_stats[winner.file]['void_selected'] += 1
                self.void_setups.append('%s#%d' % (key[0], key[1]))
            else:
                counts['kept_setups'] += 1
                self.file_stats[winner.file]['kept'] += 1
                self.kept[key] = winner
        self.dedup = counts
        self.setups_by_run = {}
        for (run, seq), rec in self.kept.items():
            self.setups_by_run.setdefault(run, {})[seq] = rec

    @staticmethod
    def _content(r):
        return (r.ts, r.bm, r.fm, r.db, r.df, r.temp, r.bser, r.fser, bool(r.void))

    # ---------------- met temperature ----------------

    def _metlog(self, station):
        name = (station.get('log_file') or '').strip()
        if name in self._metlog_cache:
            return self._metlog_cache[name]
        unit = (station.get('unit') or '').strip().lower()
        path = os.path.join(self.inp.dir, name)
        if not os.path.isfile(path):
            path = self.inp.path(os.path.basename(name))
        recs = []
        if os.path.isfile(path):
            if 'degf' in unit.replace(' ', ''):
                _, rows = read_dicts(path, '\t')
                for r in rows:
                    v = dec(r.get('temp'))
                    if v is None:
                        continue
                    recs.append((parse_iso_instant(r.get('utc')), (v - 32) * 5 / 9))
            elif 'tenth' in unit:
                for o in read_ndjson(path):
                    v = dec(o.get('ta'))
                    if v is None:
                        continue
                    recs.append((parse_iso_instant(o.get('t')), v / 10))
            else:
                _, rows = read_dicts(path, ',')
                for r in rows:
                    v = dec(r.get('temp_c'))
                    if v is None:
                        continue
                    recs.append((int(r.get('epoch_s')), v))
        recs.sort(key=lambda t: t[0])
        self._metlog_cache[name] = recs
        return recs

    def _station_for(self, line, local_date):
        best = None
        for e in self.line_stations.get(line) or []:
            f = pdate(e.get('from'))
            if f is None or f > local_date:
                continue
            if best is None or f > pdate(best.get('from')):
                best = e
        if best is None:
            return None
        st = self.station_by_token.get(str(best.get('station') or '').strip().upper())
        if st is None:
            return None
        for n in self.notices:
            target = self.station_by_token.get(n['station'].upper())
            if target is None or target.get('station_id') != st.get('station_id'):
                continue
            if n['from'] and n['to'] and n['from'] <= local_date <= n['to']:
                sub = self.station_by_token.get(n['sub'].upper())
                if sub is not None:
                    st = sub
        return st

    def _temp_of(self, rec, line):
        if rec.temp is not None:
            return rec.temp, 'FIELD'
        st = self._station_for(line, self.clock.local_date(rec.ts))
        if st is not None:
            recs = self._metlog(st)
            lo, hi = 0, len(recs) - 1
            i0 = -1
            while lo <= hi:
                mid = (lo + hi) // 2
                if recs[mid][0] <= rec.ts:
                    i0 = mid
                    lo = mid + 1
                else:
                    hi = mid - 1
            i1 = i0 + 1
            if i0 >= 0 and recs[i0][0] == rec.ts:
                return rhe(recs[i0][1], 1), 'MET'
            if i0 >= 0 and i1 < len(recs):
                t0, v0 = recs[i0]
                t1, v1 = recs[i1]
                if t1 - t0 <= self.met_gap * 60:
                    v = v0 + (v1 - v0) * Fr(rec.ts - t0, t1 - t0)
                    return rhe(v, 1), 'MET'
        return self.fallback_temp, 'FALLBACK'

    # ---------------- two peg tests ----------------

    def _test_for(self, level, ts):
        tok = re.sub(r'\s+', ' ', str(level or '').strip()).upper()
        instr = self.instr_alias.get(tok)
        if not instr:
            return None
        best = None
        for t in self.two_peg.get(instr) or []:
            if t['ts'] > ts:
                continue
            if best is None or (t['ts'], t['test_id']) > (best['ts'], best['test_id']):
                best = t
        return best

    # ---------------- runs ----------------

    def _build_runs(self):
        self.section_rows = []
        self.pair_to_section = {}
        for s in self.inp.sections:
            if (s.get('status') or '').upper() != 'ACTIVE':
                continue
            self.section_rows.append(s)
            self.pair_to_section[(s.get('from_mark'), s.get('to_mark'))] = \
                (s.get('section_id'), 'F')
            self.pair_to_section.setdefault((s.get('to_mark'), s.get('from_mark')),
                                            (s.get('section_id'), 'B'))
        self.section_rows.sort(key=lambda s: s.get('section_id'))
        self.section_of_id = {s['section_id']: s for s in self.section_rows}
        self.runs = {}
        self.cert_usage = {}
        for rid in self.run_order:
            row = self.run_rows[rid]
            setups = self.setups_by_run.get(rid, {})
            info = {'run_id': rid, 'section': '', 'direction': '', 'start': '',
                    'end': '', 'date': None, 'n_setups': len(setups),
                    'length': None, 'dh': None, 'test': None, 'status': None,
                    'setups': setups, 'line': None}
            self.runs[rid] = info
            if str(row.get('status') or '').strip().upper() == 'VOID':
                info['status'] = 'VOID'
                continue
            if not setups:
                info['status'] = 'NO_SETUPS'
                continue
            first = min(setups.values(), key=lambda r: (r.ts, r.seq))
            rdate = self.clock.local_date(first.ts)
            info['date'] = rdate
            smark, _, sst = self.resolve_bm('run', row.get('start_bm'), rdate)
            emark, _, est = self.resolve_bm('run', row.get('end_bm'), rdate)
            info['start'] = smark
            info['end'] = emark
            if sst != 'RESOLVED' or est != 'RESOLVED':
                info['status'] = 'UNRESOLVED_BM'
                continue
            match = self.pair_to_section.get((smark, emark))
            if not match:
                info['status'] = 'UNKNOWN_SECTION'
                continue
            info['section'], info['direction'] = match
            info['line'] = self.section_of_id[match[0]].get('line_id')
            try:
                nset = int(dec(row.get('setups')))
            except (TypeError, ValueError):
                nset = -1
            if sorted(setups) != list(range(1, nset + 1)):
                info['status'] = 'SEQUENCE_GAP'
                continue
            obs = str(row.get('observer') or '').strip().upper()
            ok = False
            for r in self.roster.get(obs, []):
                vf, vt = pdate(r.get('valid_from')), pdate(r.get('valid_to'))
                if vf and vt and vf <= rdate <= vt:
                    ok = True
            if not ok:
                info['status'] = 'UNCERTIFIED_OBSERVER'
                continue
            test = self._test_for(row.get('level'), first.ts)
            info['test'] = test
            if test is None:
                info['status'] = 'NO_TEST'
                continue
            if abs(test['c']) > self.collimation_limit:
                info['status'] = 'INVALID_COLLIMATION'
                continue
            missing = False
            for seq in sorted(setups):
                rec = setups[seq]
                for ser in (rec.bser, rec.fser):
                    if self.certificate(ser, rdate) is None:
                        missing = True
            if missing:
                info['status'] = 'NO_CERTIFICATE'
                continue
            if rid in self.ruled_runs:
                info['status'] = 'RULED_OUT'
                continue
            info['status'] = 'VALID'
            self._reduce_run(info)

    def _reduce_run(self, info):
        c = info['test']['c']
        rdate = info['date']
        total = Fr(0)
        length = Fr(0)
        for seq in sorted(info['setups']):
            rec = info['setups'][seq]
            temp, src = self._temp_of(rec, info['line'])
            rec.temp_src = src
            rc = []
            for reading, dist, ser in ((rec.bm, rec.db, rec.bser),
                                       (rec.fm, rec.df, rec.fser)):
                cert = self.certificate(ser, rdate)
                scale = cert['scale']
                t0 = cert['t0']
                alpha = self.rod_alpha(ser)
                val = (reading * (1 + scale * Fr(1, 10 ** 6)
                                  + alpha * Fr(1, 10 ** 6) * (temp - t0))
                       - c * dist / 100000
                       - (1 - self.refraction_k) * dist * dist / (2 * self.earth_radius))
                rc.append(val)
                key = (ser, cert['certificate'])
                if key not in self.cert_usage:
                    self.cert_usage[key] = {'serial': ser, 'cert': cert, 'readings': 0}
                self.cert_usage[key]['readings'] += 1
            rec.temp = temp
            rec.dh = rhe(rc[0] - rc[1], 5)
            rec.dh_raw = rec.bm - rec.fm
            total += rec.dh
            length += rec.db + rec.df
        info['dh'] = total
        info['length'] = length

    # ---------------- sections ----------------

    def _line_class(self, line_id):
        best = None
        for h in self.line_class_hist.get(line_id) or []:
            f = pdate(h.get('from'))
            if f is None or f > self.reference_date:
                continue
            if best is None or f > pdate(best.get('from')):
                best = h
        return (best or {}).get('class') or ''

    def _sections(self):
        by_sec = {}
        for rid in self.run_order:
            info = self.runs[rid]
            if info['status'] != 'VALID':
                continue
            by_sec.setdefault(info['section'], {'F': [], 'B': []})
            by_sec[info['section']][info['direction']].append(info)
        self.sections_out = []
        for s in self.section_rows:
            sid = s['section_id']
            cls = self._line_class(s.get('line_id'))
            tol = self.tol_section.get(cls)
            dirs = by_sec.get(sid) or {'F': [], 'B': []}
            fwd = sorted(dirs['F'], key=lambda i: i['run_id'])
            bwd = sorted(dirs['B'], key=lambda i: i['run_id'])
            cands = []
            for f in fwd:
                for b in bwd:
                    d = f['dh'] + b['dh']
                    K = (f['length'] + b['length']) / 2000
                    ok = tol is not None and (1000 * d) ** 2 <= tol * tol * K
                    cands.append({'f': f, 'b': b, 'd': d, 'K': K, 'ok': ok})
            rec = {'section_id': sid, 'from': s.get('from_mark'), 'to': s.get('to_mark'),
                   'line': s.get('line_id'), 'class': cls, 'candidates': len(cands),
                   'status': None, 'forward': '', 'backward': '', 'dh_f': None,
                   'dh_b': None, 'd': None, 'K': None, 'tol': tol, 'value': None}
            good = [c for c in cands if c['ok']]
            if sid in self.ruled_sections:
                rec['status'] = 'RULED_OUT'
            elif not fwd or not bwd:
                rec['status'] = 'INCOMPLETE'
            elif not good:
                rec['status'] = 'REJECTED_TOLERANCE'
            else:
                good.sort(key=lambda c: (abs(c['d']),
                                         tuple(-x for x in max(c['f']['date'],
                                                               c['b']['date']).timetuple()[:3]),
                                         c['f']['run_id'], c['b']['run_id']))
                best = good[0]
                rec['status'] = 'ACCEPTED'
                rec['forward'] = best['f']['run_id']
                rec['backward'] = best['b']['run_id']
                rec['dh_f'] = best['f']['dh']
                rec['dh_b'] = best['b']['dh']
                rec['d'] = best['d']
                rec['K'] = best['K']
                rec['value'] = rhe((best['f']['dh'] - best['b']['dh']) / 2, 5)
            self.sections_out.append(rec)
        self.section_by_id = {r['section_id']: r for r in self.sections_out}
        self.accepted = [r for r in self.sections_out if r['status'] == 'ACCEPTED']

    # ---------------- control ----------------

    def _control(self):
        disturbed = set()
        for e in self.journal_entries:
            if e['id'] in self.journal_cancelled or e['event'] == 'ERRATUM':
                continue
            if e['date'] is None or e['date'] > self.reference_date:
                continue
            if e['event'] == 'DISTURBED':
                disturbed.add(e['mark'])
            elif e['event'] == 'REVERIFIED':
                disturbed.discard(e['mark'])
        self.disturbed_marks = disturbed
        self.controls = []
        self.fixed_heights = {}
        for tok in self.control_tokens:
            mark, _, st = self.resolve_bm('control', tok, self.reference_date)
            if st != 'RESOLVED':
                status, height = 'UNRESOLVED', None
            elif mark not in self.control_table:
                status, height = 'NOT_IN_TABLE', None
            elif mark in disturbed:
                status, height = 'DEMOTED_DISTURBED', self.control_table[mark]
            else:
                status, height = 'FIXED', self.control_table[mark]
                self.fixed_heights[mark] = height
            self.controls.append({'token': tok, 'mark': mark, 'status': status,
                                  'height': height})

    # ---------------- least squares ----------------

    @staticmethod
    def _inverse(mat, n):
        """Exact inverse of an n x n Fraction matrix (Gauss-Jordan)."""
        a = [row[:] + [Fr(1) if i == j else Fr(0) for j in range(n)]
             for i, row in enumerate(mat)]
        for col in range(n):
            piv = None
            for r in range(col, n):
                if a[r][col] != 0:
                    piv = r
                    break
            if piv is None:
                raise ArithmeticError('singular normal matrix')
            if piv != col:
                a[col], a[piv] = a[piv], a[col]
            inv = 1 / a[col][col]
            row = a[col]
            for j in range(col, 2 * n):
                row[j] *= inv
            for r in range(n):
                if r == col:
                    continue
                f = a[r][col]
                if f == 0:
                    continue
                rr = a[r]
                for j in range(col, 2 * n):
                    rr[j] -= f * row[j]
        return [row[n:] for row in a]

    def _solve(self, obs, unknowns, fixed):
        """One weighted least squares adjustment of a set of observations."""
        idx = {m: i for i, m in enumerate(unknowns)}
        n = len(unknowns)
        N = [[Fr(0)] * n for _ in range(n)]
        rhs = [Fr(0)] * n
        rows = []
        for o in obs:
            a = {}
            if o['to'] in idx:
                a[idx[o['to']]] = a.get(idx[o['to']], Fr(0)) + 1
            if o['from'] in idx:
                a[idx[o['from']]] = a.get(idx[o['from']], Fr(0)) - 1
            fixpart = Fr(0)
            if o['to'] in fixed:
                fixpart += fixed[o['to']]
            if o['from'] in fixed:
                fixpart -= fixed[o['from']]
            l = o['value_mm'] - fixpart
            p = o['p']
            rows.append((a, l, p))
            for i, ai in a.items():
                rhs[i] += p * ai * l
                for j, aj in a.items():
                    N[i][j] += p * ai * aj
        if n == 0:
            Q = []
            x = []
        else:
            Q = self._inverse(N, n)
            x = [sum(Q[i][j] * rhs[j] for j in range(n)) for i in range(n)]
        out = {'x': x, 'Q': Q, 'idx': idx, 'unknowns': unknowns, 'obs': obs}
        vtpv = Fr(0)
        res = []
        for (a, l, p), o in zip(rows, obs):
            v = sum(ai * x[i] for i, ai in a.items()) - l
            qvv = Fr(1, 1) / p
            for i, ai in a.items():
                for j, aj in a.items():
                    qvv -= ai * Q[i][j] * aj
            vtpv += p * v * v
            res.append({'obs': o, 'v': v, 'qvv': qvv})
        out['res'] = res
        out['vtpv'] = vtpv
        return out

    def _adjust(self):
        parent = {}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        obsall = []
        for rec in self.accepted:
            a, b = rec['from'], rec['to']
            for m in (a, b):
                parent.setdefault(m, m)
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb
            sigma = self.sigma_class.get(rec['class'])
            obsall.append({'section_id': rec['section_id'], 'from': a, 'to': b,
                           'value_mm': rec['value'] * 1000, 'K': rec['K'],
                           'p': Fr(1) / (sigma * sigma * rec['K']) if sigma else None})
        comp_marks = {}
        for m in parent:
            comp_marks.setdefault(find(m), []).append(m)
        comps = {}
        for root, marks in comp_marks.items():
            name = min(marks)
            comps[name] = sorted(marks)
        comp_of_mark = {}
        for name, marks in comps.items():
            for m in marks:
                comp_of_mark[m] = name
        self.comp_of_mark = comp_of_mark
        comp_obs = {}
        for o in obsall:
            comp_obs.setdefault(comp_of_mark[o['from']], []).append(o)
        self.iterations = []
        self.components = []
        self.heights = {}
        self.sigmas = {}
        self.residual_info = {}
        self.snooped = []
        for name in sorted(comps):
            marks = comps[name]
            obs = sorted(comp_obs.get(name, []), key=lambda o: o['section_id'])
            fixed = {m: self.fixed_heights[m] * 1000 for m in marks
                     if m in self.fixed_heights}
            if not fixed:
                self.components.append({
                    'component': name, 'marks': marks, 'observations': len(obs),
                    'unknowns': None, 'redundancy': None, 'fixed': [],
                    'status': 'UNCONSTRAINED', 'removed': [], 'vtpv': None,
                    's0': None, 'lower': None, 'upper': None,
                    'global': 'UNCONSTRAINED'})
                for o in obs:
                    self.residual_info[o['section_id']] = {
                        'component': name, 'status': 'UNCONSTRAINED',
                        'v': None, 'qvv': None}
                continue
            unknowns = [m for m in marks if m not in fixed]
            removed = []
            it = 0
            sol = None
            while True:
                it += 1
                active = [o for o in obs if o['section_id'] not in removed]
                sol = self._solve(active, unknowns, fixed)
                tested = [r for r in sol['res'] if r['qvv'] != 0]
                worst = None
                for r in tested:
                    w2 = r['v'] * r['v'] / r['qvv']
                    if worst is None or w2 > worst[0] or (
                            w2 == worst[0] and r['obs']['section_id'] < worst[1]):
                        worst = (w2, r['obs']['section_id'])
                red = len(active) - len(unknowns)
                cw2 = self.critical_w * self.critical_w
                if worst is None or worst[0] <= cw2:
                    action = 'STOP_CLEAN'
                elif len(removed) >= self.max_removals:
                    action = 'STOP_BUDGET'
                elif (len(active) - 1) - len(unknowns) < self.min_redundancy:
                    action = 'STOP_REDUNDANCY'
                else:
                    action = 'REMOVE'
                self.iterations.append({
                    'component': name, 'iteration': it, 'observations': len(active),
                    'unknowns': len(unknowns), 'redundancy': red,
                    'vtpv': sol['vtpv'],
                    'max_w': None if worst is None else sqrt_round(worst[0], 2),
                    'max_w_section': None if worst is None else worst[1],
                    'action': action})
                if action != 'REMOVE':
                    break
                removed.append(worst[1])
                self.snooped.append(worst[1])
            status = {'STOP_CLEAN': 'SNOOPED' if removed else 'CLEAN',
                      'STOP_BUDGET': 'STOP_BUDGET',
                      'STOP_REDUNDANCY': 'STOP_REDUNDANCY'}[action]
            final_h = {}
            for m, h in fixed.items():
                final_h[m] = h
            for i, m in enumerate(unknowns):
                final_h[m] = sol['x'][i]
            for m in marks:
                self.heights[m] = (final_h[m], name,
                                   'FIXED' if m in fixed else 'ADJUSTED')
                if m in fixed:
                    self.sigmas[m] = Fr(0)
                else:
                    i = sol['idx'][m]
                    self.sigmas[m] = sol['Q'][i][i]
            for r in sol['res']:
                sid = r['obs']['section_id']
                self.residual_info[sid] = {
                    'component': name, 'v': r['v'], 'qvv': r['qvv'],
                    'status': 'USED' if r['qvv'] != 0 else 'UNTESTABLE'}
            for sid in removed:
                o = next(o for o in obs if o['section_id'] == sid)
                v = final_h[o['to']] - final_h[o['from']] - o['value_mm']
                self.residual_info[sid] = {'component': name, 'v': v, 'qvv': None,
                                           'status': 'REMOVED'}
            nobs = len(sol['obs'])
            red = nobs - len(unknowns)
            bounds = self.chi2.get(red, (None, None)) if red > 0 else (None, None)
            if red > 0:
                s0 = sqrt_round(sol['vtpv'] / red, 3)
                gt = 'PASS' if (bounds[0] is not None
                                and bounds[0] <= sol['vtpv'] <= bounds[1]) else 'FAIL'
            else:
                s0 = None
                gt = 'NO_REDUNDANCY'
            self.components.append({
                'component': name, 'marks': marks, 'observations': nobs,
                'unknowns': len(unknowns), 'redundancy': red,
                'fixed': sorted(fixed), 'status': status, 'removed': list(removed),
                'vtpv': sol['vtpv'], 's0': s0, 'lower': bounds[0],
                'upper': bounds[1], 'global': gt})

    # ---------------- loops ----------------

    def _loops(self):
        pair_sec = {}
        for rec in self.accepted:
            pair_sec.setdefault((rec['from'], rec['to']), (rec['section_id'], 1))
            pair_sec.setdefault((rec['to'], rec['from']), (rec['section_id'], -1))
        self.loops_out = []
        loops = (self.inp.loops or {}).get('loops') or []
        for lp in sorted(loops, key=lambda l: str(l.get('id'))):
            toks = [str(t) for t in (lp.get('marks') or [])]
            marks = []
            ok = True
            for t in toks:
                mark, _, st = self.resolve_bm('loop', t, self.reference_date)
                if st != 'RESOLVED':
                    ok = False
                marks.append(mark)
            cls = str(lp.get('class') or '')
            tol = self.tol_loop.get(cls)
            rec = {'id': lp.get('id'), 'class': cls, 'marks': len(toks),
                   'mis': None, 'K': None, 'tol': None, 'status': 'INCOMPLETE'}
            if ok and len(marks) >= 2:
                mis = Fr(0)
                ktot = Fr(0)
                good = True
                for i in range(len(marks)):
                    a = marks[i]
                    b = marks[(i + 1) % len(marks)]
                    hit = pair_sec.get((a, b))
                    if hit is None:
                        good = False
                        break
                    sec = self.section_by_id[hit[0]]
                    mis += hit[1] * sec['value'] * 1000
                    ktot += sec['K']
                if good:
                    rec['mis'] = mis
                    rec['K'] = ktot
                    rec['tol'] = tol
                    passed = tol is not None and mis * mis <= tol * tol * ktot
                    rec['status'] = 'PASS' if passed else 'FAIL'
            self.loops_out.append(rec)

    # ---------------- rates ----------------

    def _rates(self):
        ep = self.epochs.get(self.epoch_reference) or {}
        epdate = pdate(ep.get('reference_date'))
        self.prior_epoch_date = epdate
        self.years = None
        prior = {}
        if epdate is not None:
            self.years = Fr((self.reference_date - epdate).days) / Fr(36525, 100)
            for r in self.epoch_heights.get(self.epoch_reference) or []:
                mark, _, st = self.resolve_bm('epoch', r.get('mark'), epdate)
                h = dec(r.get('height_m'))
                if st == 'RESOLVED' and h is not None:
                    prior[mark] = (h, dec(r.get('sigma_mm')) or Fr(0))
        self.prior = prior
        dist = set()
        for e in self.journal_entries:
            if e['id'] in self.journal_cancelled or e['event'] != 'DISTURBED':
                continue
            if e['date'] is None or epdate is None:
                continue
            if epdate < e['date'] <= self.reference_date:
                dist.add(e['mark'])
        self.rates = []
        for mark in sorted(self.heights):
            hmm, comp, status = self.heights[mark]
            h_rep = rhe(hmm / 1000, 5)
            sigma_rep = sqrt_round(self.sigmas[mark], 2)
            pri = prior.get(mark)
            rate = None
            sigma_rate = None
            if status == 'FIXED':
                cls = 'CONTROL'
            elif mark in dist:
                cls = 'DISTURBED'
            elif pri is None:
                cls = 'NEW'
            else:
                rate = (h_rep - pri[0]) * 1000 / self.years
                var = sigma_rep * sigma_rep + pri[1] * pri[1]
                sigma_rate_sq = var / (self.years * self.years)
                sigma_rate = sqrt_round(sigma_rate_sq, 2)
                sig = rate * rate > self.k_rate * self.k_rate * sigma_rate_sq
                if sig and rate <= self.alert_rate:
                    cls = 'ALERT'
                elif sig and rate < 0:
                    cls = 'SUBSIDING'
                elif sig and rate > 0:
                    cls = 'UPLIFT'
                else:
                    cls = 'STABLE'
            self.rates.append({'mark': mark, 'prior': pri[0] if pri else None,
                               'height': h_rep, 'rate': rate,
                               'sigma_rate': sigma_rate, 'class': cls,
                               'sigma': sigma_rep})

    # ---------------- run pack settings ----------------

    @property
    def pack_settings(self):
        out = []
        text = self.inp.runpack or ''
        m = re.search(r'##\s*Settings.*?```(.*?)```', text, re.S)
        block = m.group(1) if m else ''
        for line in block.split('\n'):
            line = line.strip()
            if not line or ':' not in line:
                continue
            k, v = line.split(':', 1)
            out.append((k.strip(), v.strip()))
        return out

    FIXED_USED = {
        'control_table': None,
        'snooping_variance': 'A_PRIORI',
        'pair_selection': 'MIN_DISCREPANCY',
        'run_date_source': 'FIRST_SETUP_INSTANT',
        'rod_scale_applied_to': 'EACH_READING',
        'thermal_correction': 'APPLIED',
    }

    def used_setting(self, key, pack_value):
        if key == 'control_table':
            return 'C-2'
        if key in self.FIXED_USED:
            return self.FIXED_USED[key]
        if 'certificate_sheet' in key:
            return self.cert_sheet
        if key == 'refraction_coefficient':
            return self.refraction_k_text
        if key == 'earth_radius_m':
            return self.earth_radius_text
        if key == 'met_max_gap_min':
            return self.settings['met_max_gap_min']
        if key == 'fallback_temp_c':
            return self.settings['fallback_temp_c']
        m = re.match(r'^tolerance_class_(\S+)_section_mm$', key)
        if m and m.group(1) in self.tol_text:
            return self.tol_text[m.group(1)][0]
        m = re.match(r'^tolerance_class_(\S+)_loop_mm$', key)
        if m and m.group(1) in self.tol_text:
            return self.tol_text[m.group(1)][1]
        if key == 'collimation_limit_mm_per_100m':
            return self.collimation_limit_text
        if key == 'critical_w':
            return self.critical_w_text
        return pack_value


# --------------------------------------------------------------------------
# JSON writing with controlled number formats
# --------------------------------------------------------------------------

class Raw(str):
    pass


def num(x, nd):
    if x is None:
        return None
    return Raw(fmt(x, nd))


def jenc(v, indent=None, level=0):
    if v is None:
        return 'null'
    if isinstance(v, Raw):
        return str(v)
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return repr(v)
    if isinstance(v, str):
        return json.dumps(v)
    if isinstance(v, (list, tuple)):
        if not v:
            return '[]'
        if indent is None:
            return '[' + ', '.join(jenc(x, None, 0) for x in v) + ']'
        pad = ' ' * (indent * (level + 1))
        inner = (',\n').join(pad + jenc(x, indent, level + 1) for x in v)
        return '[\n' + inner + '\n' + ' ' * (indent * level) + ']'
    if isinstance(v, dict):
        if not v:
            return '{}'
        items = list(v.items())
        if indent is None:
            return '{' + ', '.join('%s: %s' % (json.dumps(str(k)), jenc(x, None, 0))
                                   for k, x in items) + '}'
        pad = ' ' * (indent * (level + 1))
        inner = (',\n').join(pad + '%s: %s' % (json.dumps(str(k)),
                                               jenc(x, indent, level + 1))
                             for k, x in items)
        return '{\n' + inner + '\n' + ' ' * (indent * level) + '}'
    raise TypeError(type(v))


# --------------------------------------------------------------------------
# reports
# --------------------------------------------------------------------------

REPORTS = [
    'setup_ledger.csv', 'run_summaries.tsv', 'section_pairs.psv',
    'benchmark_resolution.csv', 'control_points.json',
    'adjustment_iterations.jsonl', 'adjusted_heights.csv', 'residuals.tsv',
    'network_summary.json', 'loop_closures.xml', 'subsidence_rates.csv',
    'excluded_records.jsonl', 'dedup_report.json', 'source_lineage.json',
    'rod_certificates_used.tsv', 'parameters_used.yaml',
    'variance_vs_published.csv', 'rate_vs_published.psv',
    'dashboard_disagreements.csv', 'cache_divergence.jsonl', 'reconciliation.md',
]


class Writer:
    def __init__(self, eng, out_dir):
        self.e = eng
        self.out = out_dir

    def _write(self, name, text):
        path = os.path.join(self.out, name)
        with open(path, 'w', encoding='utf-8', newline='') as fh:
            fh.write(text)

    def _delim(self, name, header, rows, sep):
        lines = [sep.join(header)]
        for r in rows:
            lines.append(sep.join('' if c is None else str(c) for c in r))
        self._write(name, '\n'.join(lines) + '\n')

    def write_all(self):
        self.setup_ledger()
        self.run_summaries()
        self.section_pairs()
        self.benchmark_resolution()
        self.control_points()
        self.adjustment_iterations()
        self.adjusted_heights()
        self.residuals()
        self.network_summary()
        self.loop_closures()
        self.subsidence_rates()
        self.excluded_records()
        self.dedup_report()
        self.source_lineage()
        self.rod_certificates_used()
        self.parameters_used()
        self.variance_vs_published()
        self.rate_vs_published()
        self.dashboard_disagreements()
        self.cache_divergence()
        self.reconciliation()
        self.manifest()

    def setup_ledger(self):
        e = self.e
        rows = []
        for rid in e.run_order:
            info = e.runs[rid]
            if info['status'] != 'VALID':
                continue
            for seq in sorted(info['setups']):
                r = info['setups'][seq]
                rows.append([rid, seq, iso_z(r.ts), r.bser, r.fser,
                             fmt(r.bm, 5), fmt(r.fm, 5), fmt(r.db, 1), fmt(r.df, 1),
                             fmt(r.temp, 1), r.temp_src, fmt(r.dh_raw, 5),
                             fmt(r.dh, 5)])
        self._delim('setup_ledger.csv',
                    ['run_id', 'seq', 'instant_utc', 'back_rod', 'fore_rod', 'back_m',
                     'fore_m', 'back_dist_m', 'fore_dist_m', 'temp_c', 'temp_source',
                     'dh_raw_m', 'dh_m'], rows, ',')

    def run_summaries(self):
        e = self.e
        rows = []
        for rid in e.run_order:
            i = e.runs[rid]
            test = i['test']
            rows.append([rid, i['section'], i['direction'], i['start'], i['end'],
                         i['date'].isoformat() if i['date'] else '',
                         i['n_setups'],
                         fmt(i['length'], 1) if i['status'] == 'VALID' else '',
                         fmt(i['dh'], 5) if i['status'] == 'VALID' else '',
                         test['test_id'] if test else '',
                         fmt(test['c'], 3) if test else '',
                         i['status']])
        self._delim('run_summaries.tsv',
                    ['run_id', 'section_id', 'direction', 'start_mark', 'end_mark',
                     'run_date', 'setups', 'length_m', 'dh_m', 'test_id',
                     'collimation_mm_per_100m', 'status'], rows, '\t')

    def section_pairs(self):
        rows = []
        for r in self.e.sections_out:
            acc = r['status'] == 'ACCEPTED'
            rows.append([r['section_id'], r['from'], r['to'], r['line'], r['class'],
                         r['forward'], r['backward'],
                         fmt(r['dh_f'], 5) if acc else '',
                         fmt(r['dh_b'], 5) if acc else '',
                         fmt(1000 * r['d'], 2) if acc else '',
                         fmt(r['K'], 5) if acc else '',
                         fmt(sqrt_round(r['tol'] ** 2 * r['K'], 2), 2) if acc else '',
                         r['candidates'], r['status'],
                         fmt(r['value'], 5) if acc else ''])
        self._delim('section_pairs.psv',
                    ['section_id', 'from_mark', 'to_mark', 'line_id', 'class',
                     'forward_run', 'backward_run', 'dh_forward_m', 'dh_backward_m',
                     'discrepancy_mm', 'length_km', 'tolerance_mm', 'candidates',
                     'status', 'value_m'], rows, '|')

    def benchmark_resolution(self):
        rows = []
        for key in sorted(self.e.bm_log):
            ctx, tok, d = key
            mark, hops, st = self.e.bm_log[key]
            rows.append([ctx, tok, d, mark, hops, st])
        self._delim('benchmark_resolution.csv',
                    ['context', 'token', 'resolve_date', 'mark', 'hops', 'status'],
                    rows, ',')

    def control_points(self):
        e = self.e
        doc = {
            'campaign': e.campaign,
            'reference_date': e.reference_date.isoformat(),
            'table': 'C-2',
            'controls': [{'token': c['token'], 'mark': c['mark'],
                          'status': c['status'],
                          'height_m': num(c['height'], 5)} for c in e.controls],
        }
        self._write('control_points.json', jenc(doc, indent=1) + '\n')

    def adjustment_iterations(self):
        lines = []
        for it in self.e.iterations:
            obj = {'component': it['component'], 'iteration': it['iteration'],
                   'observations': it['observations'], 'unknowns': it['unknowns'],
                   'redundancy': it['redundancy'], 'vtpv': num(it['vtpv'], 4),
                   'max_w': num(it['max_w'], 2), 'max_w_section': it['max_w_section'],
                   'action': it['action']}
            lines.append(jenc(obj))
        self._write('adjustment_iterations.jsonl', ''.join(l + '\n' for l in lines))

    def adjusted_heights(self):
        e = self.e
        rows = []
        for mark in sorted(e.heights):
            hmm, comp, status = e.heights[mark]
            rows.append([mark, comp, fmt(hmm / 1000, 5),
                         fmt(sqrt_round(e.sigmas[mark], 2), 2), status])
        self._delim('adjusted_heights.csv',
                    ['mark', 'component', 'height_m', 'sigma_mm', 'status'], rows, ',')

    def residuals(self):
        e = self.e
        rows = []
        for rec in sorted(e.accepted, key=lambda r: r['section_id']):
            sid = rec['section_id']
            info = e.residual_info.get(sid) or {}
            st = info.get('status')
            v = info.get('v')
            qvv = info.get('qvv')
            w = ''
            if st == 'USED':
                mag = sqrt_round(v * v / qvv, 2)
                w = fmt(-mag if v < 0 else mag, 2)
            rows.append([sid, info.get('component', ''),
                         '' if v is None else fmt(v, 2),
                         '' if qvv is None else fmt(qvv, 4),
                         w, st])
        self._delim('residuals.tsv',
                    ['section_id', 'component', 'v_mm', 'qvv_mm2', 'w', 'status'],
                    rows, '\t')

    def network_summary(self):
        e = self.e
        comps = []
        for c in sorted(e.components, key=lambda c: c['component']):
            comps.append({
                'component': c['component'], 'marks': c['marks'],
                'observations': c['observations'], 'unknowns': c['unknowns'],
                'redundancy': c['redundancy'], 'fixed': c['fixed'],
                'status': c['status'], 'removed': c['removed'],
                'vtpv': num(c['vtpv'], 4), 's0': num(c['s0'], 3),
                'chi2_lower': num(c['lower'], 3), 'chi2_upper': num(c['upper'], 3),
                'global_test': c['global']})
        doc = {'campaign': e.campaign, 'components': comps}
        self._write('network_summary.json', jenc(doc, indent=1) + '\n')

    def loop_closures(self):
        e = self.e
        out = ['<loops campaign="%s">' % e.campaign]
        for lp in e.loops_out:
            inc = lp['status'] == 'INCOMPLETE'
            out.append('  <loop id="%s" class="%s" marks="%d" misclosure_mm="%s" '
                       'length_km="%s" tolerance_mm="%s" status="%s"/>' % (
                           lp['id'], lp['class'], lp['marks'],
                           '' if inc else fmt(lp['mis'], 2),
                           '' if inc else fmt(lp['K'], 5),
                           '' if inc else fmt(sqrt_round(lp['tol'] ** 2 * lp['K'], 2), 2),
                           lp['status']))
        out.append('</loops>')
        self._write('loop_closures.xml', '\n'.join(out) + '\n')

    def subsidence_rates(self):
        rows = []
        for r in self.e.rates:
            show = r['class'] in ('ALERT', 'SUBSIDING', 'UPLIFT', 'STABLE')
            rows.append([r['mark'],
                         fmt(r['prior'], 5) if show and r['prior'] is not None else '',
                         fmt(r['height'], 5),
                         fmt(r['rate'], 2) if show else '',
                         fmt(r['sigma_rate'], 2) if show else '',
                         r['class']])
        self._delim('subsidence_rates.csv',
                    ['mark', 'height_2024_m', 'height_2026_m', 'rate_mm_per_yr',
                     'sigma_rate_mm_per_yr', 'class'], rows, ',')

    def excluded_records(self):
        e = self.e
        recs = []
        for sid in e.void_setups:
            recs.append(('setup', sid, 'VOID_SETUP'))
        for rid in e.run_order:
            st = e.runs[rid]['status']
            if st != 'VALID':
                recs.append(('run', rid, st))
        for r in e.sections_out:
            if r['status'] != 'ACCEPTED':
                recs.append(('section', r['section_id'], r['status']))
        for sid in e.snooped:
            recs.append(('section', sid, 'SNOOPED'))
        recs.sort()
        lines = [jenc({'kind': k, 'id': i, 'reason': r}) for k, i, r in recs]
        self._write('excluded_records.jsonl', ''.join(l + '\n' for l in lines))

    def dedup_report(self):
        e = self.e
        d = e.dedup
        doc = {'records_read': d['records_read'], 'setup_keys': d['setup_keys'],
               'superseded_revisions': d['superseded_revisions'],
               'duplicates': d['duplicates'], 'conflicts': d['conflicts'],
               'void_setups': d['void_setups'], 'kept_setups': d['kept_setups'],
               'files_read': len(e.read_files), 'files_ignored': e.ignored_files}
        self._write('dedup_report.json', jenc(doc, indent=1) + '\n')

    def source_lineage(self):
        e = self.e
        files = []
        for name in e.read_files + e.ignored_files:
            s = e.file_stats[name]
            files.append({'file': s['file'], 'status': s['status'],
                          'records': s['records'], 'kept': s['kept'],
                          'superseded': s['superseded'],
                          'void_selected': s['void_selected'],
                          'duplicates': s['duplicates'],
                          'conflicts_lost': s['conflicts_lost']})
        self._write('source_lineage.json', jenc({'files': files}, indent=1) + '\n')

    def rod_certificates_used(self):
        e = self.e
        rows = []
        for key in sorted(e.cert_usage, key=lambda k: (k[0], k[1])):
            u = e.cert_usage[key]
            c = u['cert']
            ser = u['serial']
            rows.append([ser, e.rod_type(ser), e.rod_graduation(ser), c['certificate'],
                         fmt(c['scale'], 1), fmt(c['t0'], 1),
                         c['valid_from'].isoformat(), c['valid_to'].isoformat(),
                         u['readings']])
        self._delim('rod_certificates_used.tsv',
                    ['rod_serial', 'rod_type', 'graduation', 'certificate',
                     'scale_ppm', 't0_c', 'valid_from', 'valid_to', 'readings'],
                    rows, '\t')

    def parameters_used(self):
        e = self.e
        lines = [
            ('campaign', e.campaign),
            ('reference_date', e.reference_date.isoformat()),
            ('epoch_reference', e.epoch_reference),
            ('rod_certificate_sheet', e.cert_sheet),
            ('fallback_temp_c', e.settings['fallback_temp_c']),
            ('met_max_gap_min', e.settings['met_max_gap_min']),
            ('refraction_coefficient', e.refraction_k_text),
            ('earth_radius_m', e.earth_radius_text),
            ('collimation_limit_mm_per_100m', e.collimation_limit_text),
            ('critical_w', e.critical_w_text),
            ('min_redundancy', str(e.min_redundancy)),
            ('max_removals', str(e.max_removals)),
            ('alert_rate_mm_per_yr', e.alert_rate_text),
            ('k_rate', e.k_rate_text),
        ]
        classes = [c[0].strip() for c in e.tables['T-1'].records() if c[0].strip()]
        for cls in classes:
            lines.append(('tolerance_section_%s_mm' % cls, e.tol_text[cls][0]))
        for cls in classes:
            lines.append(('tolerance_loop_%s_mm' % cls, e.tol_text[cls][1]))
        for cls in classes:
            lines.append(('sigma_%s_mm_per_sqrt_km' % cls, e.sigma_text.get(cls, '')))
        types = sorted(e.rod_types)
        for t in types:
            lines.append(('graduation_%s' % t, e.rod_types[t][0]))
        for t in types:
            lines.append(('alpha_%s_ppm_per_c' % t, e.rod_types[t][2]))
        self._write('parameters_used.yaml',
                    ''.join('%s: %s\n' % (k, v) for k, v in lines))

    def variance_vs_published(self):
        e = self.e
        pub = {}
        for r in e.inp.pub_heights:
            pub[r.get('mark')] = dec(r.get('height_m'))
        rec = {m: rhe(e.heights[m][0] / 1000, 5) for m in e.heights}
        rows = []
        for mark in sorted(set(pub) | set(rec)):
            p = pub.get(mark)
            c = rec.get(mark)
            if p is None:
                status = 'MISSING_PUBLISHED'
            elif c is None:
                status = 'MISSING_RECOMPUTED'
            elif fmt(p, 5) == fmt(c, 5):
                status = 'MATCH'
            else:
                status = 'DIFFERENT'
            both = p is not None and c is not None
            rows.append([mark, '' if p is None else fmt(p, 5),
                         '' if c is None else fmt(c, 5),
                         fmt((c - p) * 1000, 2) if both else '',
                         status])
        self.variance_rows = rows
        self._delim('variance_vs_published.csv',
                    ['mark', 'published_m', 'recomputed_m', 'diff_mm', 'status'],
                    rows, ',')

    def rate_vs_published(self):
        e = self.e
        pub = {}
        for r in (e.inp.pub_rates or {}).get('rates') or []:
            pub[r.get('mark')] = (dec(r.get('rate_mm_per_yr')), r.get('class') or '')
        mine = {}
        for r in e.rates:
            show = r['class'] in ('ALERT', 'SUBSIDING', 'UPLIFT', 'STABLE')
            mine[r['mark']] = (r['rate'] if show else None, r['class'])
        rows = []
        for mark in sorted(set(pub) | set(mine)):
            p = pub.get(mark)
            m = mine.get(mark)
            if p is None:
                status = 'MISSING_PUBLISHED'
            elif m is None:
                status = 'MISSING_RECOMPUTED'
            elif p[1] != m[1]:
                status = 'CLASS_DIFFERS'
            elif (fmt(p[0], 2) if p[0] is not None else '') != \
                    (fmt(m[0], 2) if m[0] is not None else ''):
                status = 'RATE_DIFFERS'
            else:
                status = 'MATCH'
            rows.append([mark,
                         fmt(p[0], 2) if (p and p[0] is not None) else '',
                         fmt(m[0], 2) if (m and m[0] is not None) else '',
                         p[1] if p else '', m[1] if m else '', status])
        self._delim('rate_vs_published.psv',
                    ['mark', 'published_rate', 'recomputed_rate', 'published_class',
                     'recomputed_class', 'status'], rows, '|')

    def dashboard_disagreements(self):
        e = self.e
        dash = {r.get('section_id'): (r.get('status') or '') for r in e.inp.dashboard}
        mine = {r['section_id']: r['status'] for r in e.sections_out}
        for sid in e.snooped:
            mine[sid] = 'SNOOPED'
        rows = []
        for sid in sorted(set(dash) | set(mine)):
            d = dash.get(sid, '')
            m = mine.get(sid, '')
            if d != m:
                rows.append([sid, d, m])
        self._delim('dashboard_disagreements.csv',
                    ['section_id', 'dashboard_status', 'recomputed_status'], rows, ',')

    def cache_divergence(self):
        e = self.e
        rows = []
        for r in e.inp.cache:
            if str(r.get('epoch')) != e.control_epoch:
                continue
            tok = str(r.get('mark'))
            mark, _, st = e.resolve_bm('cache', tok, e.reference_date, log=False)
            if st != 'RESOLVED':
                continue
            inforce = e.control_table.get(mark)
            if inforce is None:
                continue
            cached = dec(r.get('height_m'))
            if cached == inforce:
                continue
            rows.append((mark, tok, cached, inforce))
        rows.sort(key=lambda t: (t[0], t[1]))
        lines = []
        for mark, tok, cached, inforce in rows:
            lines.append(jenc({'mark': mark, 'cache_token': tok,
                               'cache_m': num(cached, 5),
                               'in_force_m': num(inforce, 5),
                               'diff_mm': num((cached - inforce) * 1000, 2)}))
        self._write('cache_divergence.jsonl', ''.join(l + '\n' for l in lines))

    def reconciliation(self):
        e = self.e
        runs_valid = sum(1 for r in e.run_order if e.runs[r]['status'] == 'VALID')
        runs_rej = len(e.run_order) - runs_valid
        sec_acc = len(e.accepted)
        sec_not = len(e.sections_out) - sec_acc
        comps = len(e.components)
        comps_un = sum(1 for c in e.components if c['status'] == 'UNCONSTRAINED')
        alerts = sum(1 for r in e.rates if r['class'] == 'ALERT')
        loops_fail = sum(1 for l in e.loops_out if l['status'] == 'FAIL')
        out = ['# %s recomputation summary' % e.campaign, '']
        out += ['## Counts', '', '| item | value |', '| --- | --- |']
        for k, v in [('runs_valid', runs_valid), ('runs_rejected', runs_rej),
                     ('sections_accepted', sec_acc),
                     ('sections_not_accepted', sec_not),
                     ('components', comps), ('components_unconstrained', comps_un),
                     ('sections_snooped', len(e.snooped)),
                     ('marks_adjusted', len(e.heights)),
                     ('marks_alert', alerts), ('loops_failing', loops_fail)]:
            out.append('| %s | %d |' % (k, v))
        out += ['', '## Run pack settings', '', '| setting | pack | used |',
                '| --- | --- | --- |']
        for key, val in e.pack_settings:
            out.append('| %s | %s | %s |' % (key, val, e.used_setting(key, val)))
        out += ['', '## Largest height differences', '',
                '| mark | published_m | recomputed_m | diff_mm |',
                '| --- | --- | --- | --- |']
        both = [r for r in self.variance_rows if r[3] != '']
        both.sort(key=lambda r: (-abs(dec(r[3])), r[0]))
        for r in both[:10]:
            out.append('| %s | %s | %s | %s |' % (r[0], r[1], r[2], r[3]))
        self._write('reconciliation.md', '\n'.join(out) + '\n')

    def manifest(self):
        files = []
        for name in REPORTS:
            path = os.path.join(self.out, name)
            with open(path, 'rb') as fh:
                data = fh.read()
            files.append({'name': name, 'bytes': len(data),
                          'sha256': hashlib.sha256(data).hexdigest()})
        self._write('manifest.json', jenc({'files': files}, indent=1) + '\n')


def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: run_levelnet.py DATA_DIR OUT_DIR\n')
        return 2
    data_dir, out_dir = argv[1], argv[2]
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    eng = Engine(data_dir)
    Writer(eng, out_dir).write_all()
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
