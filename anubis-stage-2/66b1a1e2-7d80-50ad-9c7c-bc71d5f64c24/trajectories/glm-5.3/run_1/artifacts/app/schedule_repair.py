#!/usr/bin/env python3
"""EXEC-OPS calendar store reconciliation pass.

Usage: python3 schedule_repair.py DATA_DIR OUT_DIR
"""

import bisect
import hashlib
import json
import os
import re
import sqlite3
import sys
import zipfile
import zlib
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_HALF_UP
from xml.etree import ElementTree as ET

# ---------------------------------------------------------------- basic time

EPOCH_ORD = date(1970, 1, 1).toordinal()


def wall_to_date(ws):
    return date.fromordinal(ws // 86400 + EPOCH_ORD)


def date_to_wall(d):
    return (d.toordinal() - EPOCH_ORD) * 86400


def weekday_of_wall(ws):
    return (ws // 86400 + EPOCH_ORD - 1) % 7  # MO = 0


WEEKDAYS = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU']
WD_INDEX = {n: i for i, n in enumerate(WEEKDAYS)}


def to_basic(text):
    """Normalise an extended or basic date/time value to basic form."""
    s = text.strip()
    s = s.replace('-', '').replace(':', '')
    if s.endswith('Z') or s.endswith('z'):
        s = s[:-1] + 'Z'
    return s


def parse_dt_value(text):
    """Return (is_utc, wall_seconds) for a basic or extended date/time value."""
    s = text.strip()
    if re.fullmatch(r'\d{8}', s):
        d = date(int(s[0:4]), int(s[4:6]), int(s[6:8]))
        return False, date_to_wall(d)
    m = re.fullmatch(r'(\d{4})-?(\d{2})-?(\d{2})'
                     r'(?:[T ](\d{2}):?(\d{2})(?::?(\d{2}))?)?(Z?)', s)
    if not m:
        raise ValueError('bad date time value %r' % text)
    y, mo, dd = int(m.group(1)), int(m.group(2)), int(m.group(3))
    hh = int(m.group(4) or 0)
    mi = int(m.group(5) or 0)
    ss = int(m.group(6) or 0)
    utc = m.group(7) in ('Z', 'z')
    wall = date_to_wall(date(y, mo, dd)) + hh * 3600 + mi * 60 + ss
    return utc, wall


def fmt_wall(ws):
    ws //= 1
    days, rem = divmod(ws, 86400)
    d = date.fromordinal(days + EPOCH_ORD)
    return '%04d%02d%02dT%02d%02d%02d' % (d.year, d.month, d.day,
                                          rem // 3600, (rem % 3600) // 60, rem % 60)


def fmt_instant(epoch):
    ws = int(epoch)
    days, rem = divmod(ws, 86400)
    d = date.fromordinal(days + EPOCH_ORD)
    return '%04d%02d%02dT%02d%02d%02dZ' % (d.year, d.month, d.day,
                                            rem // 3600, (rem % 3600) // 60, rem % 60)


def parse_offset(text):
    """+HHMM / -HHMM -> seconds."""
    s = text.strip()
    sign = 1
    if s.startswith('-'):
        sign = -1
        s = s[1:]
    elif s.startswith('+'):
        s = s[1:]
    if len(s) == 4:
        return sign * (int(s[0:2]) * 3600 + int(s[2:4]) * 60)
    if len(s) == 5 and s[2] == ':':
        return sign * (int(s[0:2]) * 3600 + int(s[3:5]) * 60)
    if len(s) == 2:
        return sign * int(s) * 3600
    raise ValueError('bad offset %r' % text)


# ---------------------------------------------------------------- serialising

def jdump(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True)


def json_document(obj):
    return (jdump(obj) + '\n').encode('utf-8')


def json_lines(objs):
    out = []
    for o in objs:
        out.append(jdump(o) + '\n')
    return ''.join(out).encode('utf-8')


def field_text(value, delim):
    if value is None:
        value = ''
    if isinstance(value, bool):
        s = 'true' if value else 'false'
    elif isinstance(value, list):
        s = ';'.join('' if v is None else str(v) for v in value)
    else:
        s = str(value)
    if s == '':
        return s
    if delim in s or '"' in s or '\r' in s or '\n' in s:
        return '"' + s.replace('"', '""') + '"'
    return s


def table_document(delim, header, rows):
    out = []
    out.append(delim.join(field_text(h, delim) for h in header) + '\n')
    for row in rows:
        out.append(delim.join(field_text(c, delim) for c in row) + '\n')
    return ''.join(out).encode('utf-8')


def sha256_hex(data):
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------- yaml subset

def _yaml_strip_comment(line):
    out = []
    quote = None
    i = 0
    while i < len(line):
        ch = line[i]
        if quote:
            if quote == '"' and ch == '\\':
                out.append(line[i:i + 2])
                i += 2
                continue
            if ch == quote:
                quote = None
            out.append(ch)
        else:
            if ch in ('"', "'"):
                quote = ch
                out.append(ch)
            elif ch == '#' and (i == 0 or line[i - 1] in ' \t'):
                break
            else:
                out.append(ch)
        i += 1
    return ''.join(out).rstrip()


def _yaml_scalar(text):
    s = text.strip()
    if s.startswith('"'):
        body = []
        i = 1
        while i < len(s):
            ch = s[i]
            if ch == '\\' and i + 1 < len(s):
                body.append(s[i + 1])
                i += 2
                continue
            if ch == '"':
                break
            body.append(ch)
            i += 1
        s = ''.join(body)
    elif s.startswith("'"):
        body = []
        i = 1
        while i < len(s):
            ch = s[i]
            if ch == "'":
                if i + 1 < len(s) and s[i + 1] == "'":
                    body.append("'")
                    i += 2
                    continue
                break
            body.append(ch)
            i += 1
        s = ''.join(body)
    if re.fullmatch(r'[-+]?\d+', s):
        return int(s)
    return s


def _yaml_split_key(text):
    """Split 'key: value' honouring quotes.  Returns (key, value) or None."""
    s = text.strip()
    quote = None
    i = 0
    while i < len(s):
        ch = s[i]
        if quote:
            if quote == '"' and ch == '\\':
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in ('"', "'"):
            quote = ch
        elif ch == ':':
            if i + 1 == len(s) or s[i + 1] in ' \t':
                key = s[:i].strip()
                if key.startswith('"') and key.endswith('"') and len(key) >= 2:
                    key = key[1:-1]
                elif key.startswith("'") and key.endswith("'") and len(key) >= 2:
                    key = key[1:-1].replace("''", "'")
                return key, s[i + 1:].strip()
        i += 1
    return None


def yaml_load(text):
    items = []
    for raw in text.split('\n'):
        line = _yaml_strip_comment(raw.replace('\t', ' '))
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(' '))
        s = line.strip()
        if s == '-' or s.startswith('- '):
            body = s[1:].strip()
            items.append([indent, True, body])
        else:
            items.append([indent, False, s])
    return _yaml_block(items, 0, 0)[0]


def _yaml_extent(items, i, indent):
    """Number of following items belonging to a block opened at indent."""
    n = 0
    while i + n < len(items) and items[i + n][0] > indent:
        n += 1
    return n


def _yaml_block(items, i, indent):
    if i >= len(items):
        return None, i
    if items[i][1]:
        result = []
        while i < len(items) and items[i][0] == indent and items[i][1]:
            body = items[i][2]
            i += 1
            n = _yaml_extent(items, i, indent)
            sub = items[i:i + n]
            if body == '':
                val = _yaml_block(sub, 0, sub[0][0])[0] if sub else None
            else:
                kv = _yaml_split_key(body)
                if kv is None:
                    val = _yaml_scalar(body)
                else:
                    cont = _yaml_block(sub, 0, sub[0][0])[0] if sub else None
                    if kv[1] == '':
                        val = cont if isinstance(cont, dict) else None
                    else:
                        val = {kv[0]: _yaml_scalar(kv[1])}
                        if isinstance(cont, dict):
                            val.update(cont)
            result.append(val)
            i += n
        return result, i
    result = {}
    while i < len(items) and items[i][0] == indent and not items[i][1]:
        kv = _yaml_split_key(items[i][2])
        if kv is None:
            i += 1
            continue
        key, rest = kv
        i += 1
        n = _yaml_extent(items, i, indent)
        sub = items[i:i + n]
        if rest == '':
            val = _yaml_block(sub, 0, sub[0][0])[0] if sub else None
        else:
            val = _yaml_scalar(rest)
        result[key] = val
        i += n
    return result, i


# ---------------------------------------------------------------- pdf

def _pdf_objects(data):
    objs = {}
    for m in re.finditer(rb'(\d+)\s+(\d+)\s+obj\b', data):
        num = int(m.group(1))
        start = m.end()
        end = data.find(b'endobj', start)
        if end < 0:
            end = len(data)
        objs[num] = (start, end)
    return objs


def _pdf_stream(data, seg):
    s = seg.find(b'stream')
    if s < 0:
        return None
    p = s + len(b'stream')
    while p < len(seg) and seg[p:p + 1] in (b'\r', b'\n', b' ', b'\t'):
        p += 1
    e = seg.rfind(b'endstream')
    if e < 0 or e < p:
        return None
    raw = seg[p:e]
    while raw.endswith(b'\n') or raw.endswith(b'\r'):
        raw = raw[:-1]
    if b'FlateDecode' in seg[:s]:
        try:
            return zlib.decompress(raw)
        except zlib.error:
            try:
                return zlib.decompressobj().decompress(raw)
            except zlib.error:
                return None
    return raw


def _pdf_unescape(seg):
    out = bytearray()
    i = 0
    n = len(seg)
    while i < n:
        c = seg[i]
        if c != 0x5c or i + 1 >= n:
            out.append(c)
            i += 1
            continue
        nxt = seg[i + 1]
        if 0x30 <= nxt <= 0x37:
            digits = bytearray([nxt])
            j = i + 2
            while j < n and 0x30 <= seg[j] <= 0x37 and len(digits) < 3:
                digits.append(seg[j])
                j += 1
            out.append(int(digits.decode('ascii'), 8) & 0xFF)
            i = j
            continue
        mapping = {0x6e: 0x0a, 0x72: 0x0d, 0x74: 0x09, 0x62: 0x08, 0x66: 0x0c}
        out.append(mapping.get(nxt, nxt))
        i += 2
    return bytes(out)


def _pdf_literal_end(body, i):
    depth = 1
    n = len(body)
    while i < n:
        c = body[i]
        if c == 0x5c:
            i += 2
            continue
        if c == 0x28:
            depth += 1
        elif c == 0x29:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return n - 1


def _pdf_shown_text(body):
    """Concatenate the text of the show operators of one text run."""
    out = bytearray()
    i = 0
    n = len(body)
    while i < n:
        c = body[i:i + 1]
        if c == b'(':
            e = _pdf_literal_end(body, i + 1)
            out += _pdf_unescape(body[i + 1:e])
            i = e + 1
        elif c == b'<':
            e = body.find(b'>', i)
            if e < 0:
                break
            hx = re.sub(rb'\s', b'', body[i + 1:e])
            if len(hx) % 2:
                hx += b'0'
            try:
                out += bytes.fromhex(hx.decode('ascii'))
            except ValueError:
                pass
            i = e + 1
        else:
            i += 1
    return out.decode('latin-1')


def _pdf_text_rows(content):
    """Rows of (x, text) grouped by y coordinate, top of the page down."""
    rows = {}
    for m in re.finditer(rb'BT(.*?)ET', content, re.S):
        block = m.group(1)
        tm = re.search(rb'([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+'
                       rb'([-\d.]+)\s+([-\d.]+)\s*\bTm\b', block)
        if not tm:
            continue
        x = tm.group(5).decode('latin-1')
        y = float(tm.group(6).decode('latin-1'))
        text = _pdf_shown_text(block[tm.end():])
        rows.setdefault(y, []).append((x, text))
    ordered = []
    for y in sorted(rows, key=lambda v: -v):
        cells = sorted(rows[y], key=lambda t: float(t[0]))
        ordered.append((y, [c[1] for c in cells], [c[0] for c in cells]))
    return ordered


def pdf_tables(path):
    """Parse the governance PDF into {table name: [row dicts]}."""
    with open(path, 'rb') as fh:
        data = fh.read()
    objs = _pdf_objects(data)
    pages = []
    catalog = None
    for num in sorted(objs):
        start, end = objs[num]
        seg = data[start:end]
        if b'/Type /Catalog' in seg:
            catalog = num
    if catalog is not None:
        start, end = objs[catalog]
        m = re.search(rb'/Pages\s+(\d+)\s+0\s+R', data[start:end])
        pagesobj = int(m.group(1)) if m else None
    else:
        pagesobj = None
    page_nums = []
    if pagesobj is not None:
        start, end = objs[pagesobj]
        seg = data[start:end]
        m = re.search(rb'/Kids\s*\[(.*?)\]', seg, re.S)
        if m:
            page_nums = [int(x) for x in re.findall(rb'(\d+)\s+0\s+R', m.group(1))]
    if not page_nums:
        for num in sorted(objs):
            start, end = objs[num]
            if b'/Type /Page' in data[start:end] and b'/Contents' in data[start:end]:
                page_nums.append(num)
    tables = {}
    current = None
    header = None
    for pnum in page_nums:
        start, end = objs[pnum]
        seg = data[start:end]
        m = re.search(rb'/Contents\s+(\d+)\s+0\s+R', seg)
        if not m:
            continue
        cnum = int(m.group(1))
        cstart, cend = objs[cnum]
        content = _pdf_stream(data, data[cstart:cend])
        if content is None:
            continue
        for y, cells, xs in _pdf_text_rows(content):
            joined = ''.join(cells).strip()
            if not joined:
                continue
            if re.fullmatch(r'page\s+\d+\s+of\s+\d+', joined, re.I):
                continue
            cap = re.match(r'Table\s+\d+\.\s*(.*?)(\s*\(continued\))?$', joined)
            if cap:
                name = cap.group(1).strip()
                current = name
                header = None
                continue
            if current is None:
                continue
            if header is None:
                header = list(zip(cells, xs))
                tables.setdefault(current, {'rows': []})
                continue
            row = {}
            for text, x in zip(cells, xs):
                best = None
                bestd = None
                for col, hx in header:
                    d = abs(float(x) - float(hx))
                    if bestd is None or d < bestd:
                        best = col
                        bestd = d
                if best is not None and best not in row:
                    row[best] = text
            tables[current]['rows'].append(row)
    return dict((name, {'rows': tab['rows']}) for name, tab in
                tables.items())


# ---------------------------------------------------------------- xlsx

XLSX_NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
XLSX_REL_NS = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'


def _xlsx_cell_value(cell, shared):
    t = cell.get('t')
    if t == 's':
        v = cell.find(XLSX_NS + 'v')
        if v is None or v.text is None:
            return ''
        idx = int(v.text)
        return shared[idx] if 0 <= idx < len(shared) else ''
    if t == 'inlineStr':
        return ''.join(x.text or '' for x in cell.iter(XLSX_NS + 't'))
    v = cell.find(XLSX_NS + 'v')
    if v is None or v.text is None:
        return ''
    return v.text


def _col_index(ref):
    m = re.match(r'([A-Z]+)', ref)
    n = 0
    for ch in m.group(1):
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def xlsx_sheets(path):
    """Return {sheet name: {'cells': {(col,row): text}, 'epoch': date}}."""
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        shared = []
        if 'xl/sharedStrings.xml' in names:
            root = ET.fromstring(zf.read('xl/sharedStrings.xml'))
            for si in root.iter(XLSX_NS + 'si'):
                shared.append(''.join(t.text or '' for t in si.iter(XLSX_NS + 't')))
        workbook = ET.fromstring(zf.read('xl/workbook.xml'))
        epoch = date(1899, 12, 30)
        wp = workbook.find(XLSX_NS + 'workbookPr')
        if wp is not None and wp.get('date1904') in ('1', 'true'):
            epoch = date(1904, 1, 1)
        rels = {}
        if 'xl/_rels/workbook.xml.rels' in names:
            rroot = ET.fromstring(zf.read('xl/_rels/workbook.xml.rels'))
            for rel in rroot:
                rels[rel.get('Id')] = rel.get('Target')
        sheets = {}
        order = []
        for sh in workbook.iter(XLSX_NS + 'sheet'):
            name = sh.get('name')
            rid = sh.get(XLSX_REL_NS + 'id')
            target = rels.get(rid, '')
            if not target:
                continue
            part = target if target.startswith('xl/') else 'xl/' + target.lstrip('/')
            if part not in names:
                continue
            root = ET.fromstring(zf.read(part))
            cells = {}
            for cell in root.iter(XLSX_NS + 'c'):
                ref = cell.get('r')
                if not ref:
                    continue
                m = re.match(r'([A-Z]+)(\d+)', ref)
                if not m:
                    continue
                key = (_col_index(m.group(1)), int(m.group(2)))
                cells[key] = _xlsx_cell_value(cell, shared)
            sheets[name] = cells
            order.append(name)
    return sheets, epoch, order


def sheet_rows(cells):
    """Yield (row number, {column index: text}) for rows with any cell."""
    rows = {}
    for (col, row), text in cells.items():
        rows.setdefault(row, {})[col] = text
    for row in sorted(rows):
        yield row, rows[row]


def sheet_cell(cells, ref):
    m = re.match(r'([A-Z]+)(\d+)$', ref)
    return cells.get((_col_index(m.group(1)), int(m.group(2))), '')


# ---------------------------------------------------------------- calendars

ICAL_NS = '{urn:ietf:params:xml:ns:icalendar-2.0}'

DT_PROPS = ('DTSTART', 'DTEND', 'RECURRENCE-ID', 'EXDATE', 'RDATE',
            'LAST-MODIFIED', 'DTSTAMP')


def _ical_unfold(raw):
    lines = raw.split(b'\n')
    out = []
    for ln in lines:
        s = ln.rstrip(b'\r')
        if s[:1] in (b' ', b'\t') and out:
            out[-1] += s[1:]
        else:
            out.append(s)
    return out


def _ical_unescape(text):
    out = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == '\\' and i + 1 < n:
            nxt = text[i + 1]
            if nxt in ('n', 'N'):
                out.append('\n')
            else:
                out.append(nxt)
            i += 2
            continue
        out.append(ch)
        i += 1
    return ''.join(out)


def _ical_split_line(line):
    """Split a content line into (name, params, value) on raw octets."""
    data = line
    inq = False
    cpos = -1
    for i in range(len(data)):
        c = data[i:i + 1]
        if c == b'"':
            inq = not inq
        elif c == b':' and not inq:
            cpos = i
            break
    if cpos < 0:
        return None
    head = data[:cpos]
    value = data[cpos + 1:]
    # parameters: split on ';' outside quotes
    parts = []
    cur = bytearray()
    inq = False
    for i in range(len(head)):
        c = head[i:i + 1]
        if c == b'"':
            inq = not inq
            cur += c
            continue
        if c == b';' and not inq:
            parts.append(bytes(cur))
            cur = bytearray()
            continue
        cur += c
    parts.append(bytes(cur))
    name = parts[0].decode('ascii', 'replace').strip().upper()
    params = []
    for p in parts[1:]:
        eq = p.find(b'=')
        if eq < 0:
            continue
        pname = p[:eq].decode('ascii', 'replace').strip().upper()
        pval = p[eq + 1:]
        values = []
        cur = bytearray()
        inq = False
        for i in range(len(pval)):
            c = pval[i:i + 1]
            if c == b'"':
                inq = not inq
                continue
            if c == b',' and not inq:
                values.append(bytes(cur).decode('utf-8', 'replace'))
                cur = bytearray()
                continue
            cur += c
        values.append(bytes(cur).decode('utf-8', 'replace'))
        params.append((pname, values))
    return name, params, value


def _parse_duration(text):
    """ISO 8601 duration -> (weeks, days, hours, minutes, seconds)."""
    s = text.strip()
    m = re.fullmatch(
        r'([+-]?)P(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?',
        s.upper())
    if not m:
        raise ValueError('bad duration %r' % text)
    sign = -1 if m.group(1) == '-' else 1
    return (sign * int(m.group(2) or 0), sign * int(m.group(3) or 0),
            sign * int(m.group(4) or 0), sign * int(m.group(5) or 0),
            sign * int(m.group(6) or 0))


def _parse_rrule(text):
    """RRULE text -> dict of UPPER part -> list of values."""
    parts = {}
    for chunk in text.split(';'):
        if not chunk:
            continue
        if '=' not in chunk:
            continue
        k, v = chunk.split('=', 1)
        parts[k.strip().upper()] = v.split(',')
    return parts


class Comp(object):
    __slots__ = ('name', 'props')

    def __init__(self, name):
        self.name = name
        self.props = []          # list of (name, params, values)

    def all(self, name):
        name = name.upper()
        return [p for p in self.props if p[0] == name]

    def first(self, name):
        found = self.all(name)
        return found[0] if found else None

    def values(self, name):
        p = self.first(name)
        return p[2] if p else []

    def value(self, name):
        v = self.values(name)
        return v[0] if v else None

    def param(self, name, param):
        p = self.first(name)
        if p is None:
            return None
        for pname, pvalues in p[1]:
            if pname == param.upper():
                return pvalues[0] if pvalues else None
        return None

    def param_all(self, name, param):
        p = self.first(name)
        if p is None:
            return []
        for pname, pvalues in p[1]:
            if pname == param.upper():
                return pvalues
        return []


def _mk_prop(name, params, values):
    return (name.upper(), [(k.upper(), v) for k, v in params], values)


def _ical_components(raw):
    """Decode iCalendar octets into a flat list of Comp, document order."""
    out = []
    stack = []
    for line in _ical_unfold(raw):
        if not line:
            continue
        parsed = _ical_split_line(line)
        if parsed is None:
            continue
        name, params, valraw = parsed
        if name == 'BEGIN':
            sub = Comp(valraw.strip().decode('utf-8', 'replace').upper())
            if stack:
                stack[-1].props.append(('SUBCOMPONENT', [], [sub]))
            stack.append(sub)
            continue
        if name == 'END':
            if stack:
                done = stack.pop()
                if not stack:
                    out.append(done)
            continue
        if not stack:
            continue
        values = _ical_values(name, params, valraw)
        stack[-1].props.append(_mk_prop(name, params, values))
    flat = []
    for comp in out:
        _flatten(comp, flat)
    return flat


def _flatten(comp, flat):
    flat.append(comp)
    for p in comp.props:
        if p[0] == 'SUBCOMPONENT':
            _flatten(p[2][0], flat)


def prop_text(comp, name):
    """The plain text of the first value of the named property."""
    p = comp.first(name)
    if p is None:
        return None
    if not p[2]:
        return ''
    kind, val = p[2][0]
    return val


def _ical_values(name, params, valraw):
    text = valraw.decode('utf-8', 'replace')
    if name in ('EXDATE', 'RDATE'):
        vals = []
        for item in text.split(','):
            if not item:
                continue
            if '/' in item:
                a, b = item.split('/', 1)
                vals.append(('period', (a, b)))
            else:
                vals.append(('datetime', item))
        return vals
    if name in ('DTSTART', 'DTEND', 'RECURRENCE-ID', 'LAST-MODIFIED',
                'DTSTAMP'):
        return [('datetime', text)]
    if name == 'DURATION':
        return [('duration', text)]
    if name == 'RRULE':
        return [('recur', _parse_rrule(text))]
    if name == 'SEQUENCE':
        return [('integer', text)]
    if name == 'ATTENDEE':
        return [('text', _ical_unescape(text))]
    return [('text', _ical_unescape(text))]


def _xcal_components(data):
    root = ET.fromstring(data)
    out = []

    def walk(el):
        for child in el:
            tag = child.tag.split('}')[-1].lower()
            if tag in ('vevent', 'vtimezone', 'vtodo', 'vjournal', 'standard',
                       'daylight'):
                comp = Comp(tag.upper())
                _xcal_fill(comp, child)
                if tag in ('vevent', 'vtimezone'):
                    out.append(comp)
            else:
                walk(child)

    walk(root)
    return out


def _xcal_text(el):
    return ''.join(el.itertext())


def _xcal_fill(comp, el):
    for child in el:
        tag = child.tag.split('}')[-1].lower()
        if tag == 'properties':
            for p in child:
                pname = p.tag.split('}')[-1].upper()
                params = []
                par = p.find(ICAL_NS + 'parameters')
                if par is not None:
                    for pp in par:
                        key = pp.tag.split('}')[-1].upper()
                        vals = [_xcal_text(t) for t in pp.iter(ICAL_NS + 'text')]
                        if not vals:
                            vals = [_xcal_text(pp)]
                        params.append((key, vals))
                values = []
                for v in p:
                    vtag = v.tag.split('}')[-1].lower()
                    if vtag == 'parameters':
                        continue
                    if vtag == 'date-time':
                        values.append(('datetime', _xcal_text(v)))
                    elif vtag == 'date':
                        values.append(('datetime', _xcal_text(v)))
                    elif vtag == 'period':
                        st = v.find(ICAL_NS + 'start')
                        en = v.find(ICAL_NS + 'end')
                        du = v.find(ICAL_NS + 'duration')
                        if en is not None:
                            values.append(('period', (_xcal_text(st),
                                                     _xcal_text(en))))
                        else:
                            values.append(('period', (_xcal_text(st),
                                                       _xcal_text(du))))
                    elif vtag == 'recur':
                        rule = {}
                        for part in v:
                            key = part.tag.split('}')[-1].lower()
                            rule.setdefault(key.upper(), []).append(
                                _xcal_text(part))
                        values.append(('recur', rule))
                    elif vtag == 'integer':
                        values.append(('integer', _xcal_text(v)))
                    elif vtag == 'duration':
                        values.append(('duration', _xcal_text(v)))
                    else:
                        values.append(('text', _xcal_text(v)))
                comp.props.append(_mk_prop(pname, params, values))
        elif tag == 'components':
            for sub in child:
                stag = sub.tag.split('}')[-1].lower()
                if stag in ('standard', 'daylight', 'vevent'):
                    subc = Comp(stag.upper())
                    _xcal_fill(subc, sub)
                    comp.props.append(('SUBCOMPONENT', [], [subc]))
        elif tag in ('standard', 'daylight'):
            subc = Comp(tag.upper())
            _xcal_fill(subc, child)
            comp.props.append(('SUBCOMPONENT', [], [subc]))


def _jcal_components(data):
    doc = json.loads(data.decode('utf-8'))
    out = []

    def walk(node):
        if not isinstance(node, list) or not node:
            return
        name = node[0].lower()
        if name in ('vevent', 'vtimezone'):
            comp = Comp(name.upper())
            for p in node[1]:
                if not isinstance(p, list) or len(p) < 3:
                    continue
                pname = str(p[0]).upper()
                params = []
                if isinstance(p[1], dict):
                    for k, v in p[1].items():
                        if isinstance(v, list):
                            params.append((str(k).upper(), [str(x) for x in v]))
                        else:
                            params.append((str(k).upper(), [str(v)]))
                vtype = str(p[2]).lower()
                values = []
                for raw in p[3:]:
                    if vtype == 'date-time' or vtype == 'date':
                        values.append(('datetime', str(raw)))
                    elif vtype == 'period':
                        if isinstance(raw, list) and len(raw) >= 2:
                            values.append(('period', (str(raw[0]), str(raw[1]))))
                    elif vtype == 'recur':
                        rule = {}
                        if isinstance(raw, dict):
                            for k, v in raw.items():
                                key = str(k).upper()
                                if isinstance(v, list):
                                    rule[key] = [str(x) for x in v]
                                else:
                                    rule[key] = [str(v)]
                        values.append(('recur', rule))
                    elif vtype == 'integer':
                        values.append(('integer', str(raw)))
                    elif vtype == 'duration':
                        values.append(('duration', str(raw)))
                    else:
                        values.append(('text', str(raw)))
                comp.props.append(_mk_prop(pname, params, values))
            for sub in node[2]:
                walk(sub)
            out.append(comp)
        else:
            for sub in node[2] if len(node) > 2 else []:
                walk(sub)

    walk(doc)
    return out


def decode_calendar(path):
    """Decode a replica file, choosing the encoding by its first octet."""
    with open(path, 'rb') as fh:
        raw = fh.read()
    i = 0
    while i < len(raw) and raw[i:i + 1].isspace():
        i += 1
    first = raw[i:i + 1] if i < len(raw) else b''
    if first == b'<':
        return _xcal_components(raw)
    if first == b'[':
        return _jcal_components(raw)
    return _ical_components(raw)


def subcomponents(comp, name):
    name = name.upper()
    return [p[2][0] for p in comp.props
            if p[0] == 'SUBCOMPONENT' and p[2][0].name == name]


# ---------------------------------------------------------------- zone model

class Zone(object):
    __slots__ = ('tzid', 'transitions', 'offsets', 'first_from',
                 'observances', '_onsets', '_tos')

    def __init__(self, tzid):
        self.tzid = tzid
        self.transitions = []     # list of (onset_utc, from_off, to_off)
        self.offsets = set()
        self.first_from = None
        self.observances = 0
        self._onsets = []
        self._tos = []

    def build(self):
        seen = set()
        for onset, offrom, offto in self.transitions:
            seen.add((onset, offrom, offto))
        merged = sorted(seen)
        self.transitions = merged
        for _onset, offrom, offto in merged:
            self.offsets.add(offrom)
            self.offsets.add(offto)
        if merged:
            self.first_from = merged[0][1]
        self._onsets = [t[0] for t in merged]
        self._tos = [t[2] for t in merged]

    def offset_at(self, instant):
        onsets = self._onsets
        if not onsets:
            return self.first_from
        idx = bisect.bisect_right(onsets, instant)
        if idx == 0:
            return self.first_from
        return self._tos[idx - 1]

    def wall_at(self, instant):
        return instant + self.offset_at(instant)

    def resolve(self, wall):
        cands = []
        for off in sorted(self.offsets):
            inst = wall - off
            if self.offset_at(inst) == off:
                cands.append((inst, off))
        if len(cands) == 1:
            inst = cands[0][0]
            return inst, 'unique', 0
        if len(cands) >= 2:
            cands.sort()
            inst = cands[0][0]
            return inst, 'ambiguous', 0
        for onset, offrom, offto in self.transitions:
            gap = offto - offrom
            if gap <= 0:
                continue
            lo = onset + offrom
            hi = onset + offto
            if lo <= wall < hi:
                newwall = wall + gap
                return newwall - offto, 'nonexistent', gap // 60
        return wall - (self.first_from or 0), 'unique', 0


def _zone_yearly_days(year, rule, wkst, dtstart_wall):
    """Days selected by a VTIMEZONE YEARLY rule for one year."""
    byyearday = rule.get('BYYEARDAY')
    byweekno = rule.get('BYWEEKNO')
    bymonth = rule.get('BYMONTH')
    bymonthday = rule.get('BYMONTHDAY')
    byday = rule.get('BYDAY')
    dtstart_date = wall_to_date(dtstart_wall)
    if byyearday is None and byweekno is None:
        if bymonth:
            months = [int(x) for x in bymonth if 1 <= int(x) <= 12]
        else:
            months = [dtstart_date.month]
        days = set()
        for month in months:
            days |= _month_selection(year, month, bymonthday, byday,
                                     dtstart_date.day)
        return days
    if byyearday is not None:
        yd = set()
        for tok in byyearday:
            n = int(tok)
            if n > 0:
                d = date(year, 1, 1) + timedelta(n - 1)
            else:
                d = date(year, 12, 31) + timedelta(n + 1)
            if d.year == year:
                yd.add(d)
    if byweekno is not None:
        wd = _weekno_days(year, wkst, byweekno)
    if byyearday is not None and byweekno is not None:
        days = yd & wd
    elif byweekno is not None:
        days = wd
    else:
        days = yd
    keep = set()
    dt_wd = dtstart_date.weekday()
    for d in days:
        if bymonth and d.month not in [int(x) for x in bymonth]:
            continue
        if bymonthday and not _day_matches_monthday(d, bymonthday):
            continue
        if byday:
            if not _day_matches_byday(d, byday):
                continue
        elif byweekno is not None:
            if d.weekday() != dt_wd:
                continue
        keep.add(d)
    return keep


def _month_selection(year, month, bymonthday, byday, dtstart_day):
    ndays = (date(year + (month == 12), (month % 12) + 1, 1)
             - timedelta(1)).day
    s1 = None
    if bymonthday is not None:
        s1 = set()
        for tok in bymonthday:
            n = int(tok)
            dd = n if n > 0 else ndays + n + 1
            if 1 <= dd <= ndays:
                s1.add(dd)
    s2 = None
    if byday is not None:
        s2 = set()
        for tok in byday:
            ordinal, wd = _parse_byday(tok)
            cands = [dd for dd in range(1, ndays + 1)
                     if weekday_of_wall(date_to_wall(date(year, month, dd))) == wd]
            if ordinal is None:
                s2 |= set(cands)
            elif ordinal > 0:
                if len(cands) >= ordinal:
                    s2.add(cands[ordinal - 1])
            else:
                if len(cands) >= -ordinal:
                    s2.add(cands[ordinal])
    if s1 is not None and s2 is not None:
        sel = s1 & s2
    elif s2 is not None:
        sel = s2
    elif s1 is not None:
        sel = s1
    else:
        sel = {dtstart_day} if 1 <= dtstart_day <= ndays else set()
    return set(date(year, month, dd) for dd in sel)


def _day_matches_monthday(d, toks):
    ndays = (date(d.year + (d.month == 12), (d.month % 12) + 1, 1)
             - timedelta(1)).day
    for tok in toks:
        n = int(tok)
        dd = n if n > 0 else ndays + n + 1
        if d.day == dd:
            return True
    return False


def _day_matches_byday(d, toks):
    wd = weekday_of_wall(date_to_wall(d))
    for tok in toks:
        ordinal, w = _parse_byday(tok)
        if w == wd:
            return True
    return False


def _parse_byday(tok):
    tok = tok.strip().upper()
    m = re.fullmatch(r'([+-]?\d+)?(MO|TU|WE|TH|FR|SA|SU)', tok)
    if not m:
        return None, None
    ordinal = int(m.group(1)) if m.group(1) else None
    return ordinal, WD_INDEX[m.group(2)]


def _weekno_days(year, wkst, toks):
    """The days inside `year` of the weeks named by BYWEEKNO."""
    jan1 = date(year, 1, 1)
    dec31 = date(year, 12, 31)
    delta = (jan1.weekday() - wkst) % 7
    cur = jan1 - timedelta(delta)
    weeks = []
    while cur <= dec31:
        inside = sum(1 for k in range(7) if (cur + timedelta(k)).year == year)
        if inside >= 4:
            weeks.append(cur)
        elif weeks:
            break
        cur = cur + timedelta(7)
    out = set()
    for tok in toks:
        n = int(tok)
        idx = n - 1 if n > 0 else len(weeks) + n
        if 0 <= idx < len(weeks):
            s = weeks[idx]
            for k in range(7):
                d = s + timedelta(k)
                if d.year == year:
                    out.add(d)
    return out


def build_zones(path, horizon_wall):
    comps = [c for c in decode_calendar(path) if c.name == 'VTIMEZONE']
    zones = {}
    for tz in comps:
        tzid = prop_text(tz, 'TZID')
        zone = Zone(tzid)
        for kind in ('STANDARD', 'DAYLIGHT'):
            subs = subcomponents(tz, kind)
            zone.observances += len(subs)
            for sub in subs:
                _zone_onsets(zone, sub, horizon_wall)
        zones[tzid] = zone
    for z in zones.values():
        z.build()
    return zones


def _zone_onsets(zone, sub, horizon_wall):
    dts = sub.first('DTSTART')
    if dts is None or not dts[2]:
        return
    _kind, dtval = dts[2][0]
    is_utc, dtwall = parse_dt_value(to_basic(dtval))
    offrom = parse_offset(prop_text(sub, 'TZOFFSETFROM'))
    offto = parse_offset(prop_text(sub, 'TZOFFSETTO'))
    time_of_day = dtwall % 86400
    rule = None
    rrp = sub.first('RRULE')
    if rrp is not None and rrp[2]:
        rule = rrp[2][0][1]
    until = None
    if rule and rule.get('UNTIL'):
        u = rule['UNTIL'][0].strip()
        isz, uwall = parse_dt_value(to_basic(u))
        if isz:
            until = uwall
        else:
            until = uwall - offrom
    onset_walls = set()
    if dtwall <= horizon_wall:
        onset_walls.add(dtwall)
    rdates = sub.all('RDATE')
    for rp in rdates:
        for _kind, val in rp[2]:
            if isinstance(val, tuple):
                v = val[0]
            else:
                v = val
            _z, w = parse_dt_value(to_basic(v))
            if w < dtwall or w > horizon_wall:
                continue
            onset_walls.add(w)
    if rule is not None:
        freq = (rule.get('FREQ') or [''])[0].strip().upper()
        if freq == 'YEARLY':
            interval = int((rule.get('INTERVAL') or ['1'])[0])
            wkst = WD_INDEX.get((rule.get('WKST') or ['MO'])[0].strip().upper(), 0)
            base_year = wall_to_date(dtwall).year
            year = base_year
            while True:
                for d in _zone_yearly_days(year, rule, wkst, dtwall):
                    w = date_to_wall(d) + time_of_day
                    if w < dtwall or w > horizon_wall:
                        continue
                    onset_walls.add(w)
                if date_to_wall(date(year + 1, 1, 1)) > horizon_wall:
                    break
                year += interval
    for w in onset_walls:
        onset_utc = w - offrom
        if until is not None and onset_utc > until:
            continue
        zone.transitions.append((onset_utc, offrom, offto))


# ---------------------------------------------------------------- rrule for events

def _int_list(rule, key, default=None):
    vals = rule.get(key)
    if not vals:
        return default
    out = []
    for v in vals:
        for item in str(v).split(','):
            item = item.strip()
            if item:
                out.append(int(item))
    return out


def _str_list(rule, key, default=None):
    vals = rule.get(key)
    if not vals:
        return default
    out = []
    for v in vals:
        for item in str(v).split(','):
            item = item.strip()
            if item:
                out.append(item.upper())
    return out


def _rule_int(rule, key, default):
    vals = rule.get(key)
    if not vals:
        return default
    try:
        return int(str(vals[0]).strip())
    except ValueError:
        return default


def _days_in_month(year, month):
    if month == 12:
        return 31
    return (date(year, month + 1, 1) - timedelta(1)).day


def _add_months(year, month, count):
    idx = (year * 12 + (month - 1)) + count
    return idx // 12, idx % 12 + 1


def expand_rrule(rule, dtstart_wall, horizon_wall, count, until_instant,
                 resolve_wall):
    """Return the list of produced wall clock candidates, ascending."""
    freq = _str_list(rule, 'FREQ', [''])[0]
    interval = max(1, _rule_int(rule, 'INTERVAL', 1))
    wkst = WD_INDEX.get(_str_list(rule, 'WKST', ['MO'])[0], 0)
    bymonth = _int_list(rule, 'BYMONTH')
    bymonthday = _int_list(rule, 'BYMONTHDAY')
    byday = _str_list(rule, 'BYDAY')
    byhour = _int_list(rule, 'BYHOUR')
    byminute = _int_list(rule, 'BYMINUTE')
    bysetpos = _int_list(rule, 'BYSETPOS')
    byyearday = _int_list(rule, 'BYYEARDAY')
    byweekno = _int_list(rule, 'BYWEEKNO')
    dt_date = wall_to_date(dtstart_wall)
    dt_tod = dtstart_wall % 86400
    produced = []
    periods = 0

    def candidate_times():
        hours = byhour if byhour is not None else [dt_tod // 3600]
        minutes = byminute if byminute is not None else [(dt_tod % 3600) // 60]
        seconds = dt_tod % 60
        return [(h * 3600 + mi * 60 + seconds)
                for h in hours for mi in minutes]

    while True:
        period_days = None
        period_cands = None
        if freq == 'DAILY':
            day = dt_date + timedelta(periods * interval)
            period_days = [day]
        elif freq == 'WEEKLY':
            first = dt_date - timedelta((dt_date.weekday() - wkst) % 7)
            start = first + timedelta(weeks=periods * interval)
            if byday is not None:
                wds = set()
                for tok in byday:
                    ordinal, wd = _parse_byday(tok)
                    if wd is not None:
                        wds.add(wd)
            else:
                wds = {dt_date.weekday()}
            period_days = []
            for k in range(7):
                d = start + timedelta(k)
                if d.weekday() in wds:
                    period_days.append(d)
        elif freq == 'MONTHLY':
            year, month = _add_months(dt_date.year, dt_date.month,
                                      periods * interval)
            if bymonth is not None and month not in bymonth:
                period_days = []
            else:
                period_days = None
                period_cands = _month_selection(
                    year, month, bymonthday, byday, dt_date.day)
        elif freq == 'YEARLY':
            year = dt_date.year + periods * interval
            period_cands = _yearly_days(year, bymonth, bymonthday, byday,
                                        byyearday, byweekno, wkst, dt_date)
        else:
            return [dtstart_wall]
        if period_cands is None:
            period_cands = set(period_days)
        elif period_days is not None:
            period_cands = set(period_days) & period_cands
        if freq in ('DAILY', 'WEEKLY'):
            keepdays = set()
            for d in period_cands:
                if bymonth is not None and d.month not in bymonth:
                    continue
                if bymonthday is not None and \
                        not _day_matches_monthday(d, bymonthday):
                    continue
                if byday is not None and not _day_matches_byday(d, byday):
                    continue
                keepdays.add(d)
            period_cands = keepdays
        cands = []
        times = candidate_times()
        for d in sorted(period_cands):
            for tod in times:
                cands.append(date_to_wall(d) + tod)
        cands.sort()
        if bysetpos is not None:
            chosen = []
            for pos in bysetpos:
                idx = pos - 1 if pos > 0 else len(cands) + pos
                if 0 <= idx < len(cands):
                    chosen.append(cands[idx])
            cands = sorted(set(chosen))
        kept = []
        for w in cands:
            if w < dtstart_wall:
                continue
            if until_instant is not None:
                inst, _cls, _shift = resolve_wall(w)
                if inst > until_instant:
                    continue
            kept.append(w)
        produced.extend(kept)
        if count is not None and len(produced) >= count:
            return produced[:count]
        periods += 1
        if periods > 100000:
            return produced
        if freq == 'DAILY':
            nxt = dt_date + timedelta(periods * interval)
        elif freq == 'WEEKLY':
            nxt = dt_date + timedelta(weeks=periods * interval)
        elif freq == 'MONTHLY':
            y, mth = _add_months(dt_date.year, dt_date.month,
                                 periods * interval)
            nxt = date(y, mth, 1)
        else:
            nxt = date(dt_date.year + periods * interval, 1, 1)
        if date_to_wall(nxt) > horizon_wall:
            return produced


def _yearly_days(year, bymonth, bymonthday, byday, byyearday, byweekno, wkst,
                 dt_date):
    if byyearday is None and byweekno is None:
        months = bymonth if bymonth is not None else [dt_date.month]
        days = set()
        for month in months:
            if not 1 <= month <= 12:
                continue
            days |= _month_selection(year, month, bymonthday, byday,
                                      dt_date.day)
        return days
    if byyearday is not None:
        yd = set()
        for n in byyearday:
            if n > 0:
                d = date(year, 1, 1) + timedelta(n - 1)
            else:
                d = date(year, 12, 31) + timedelta(n + 1)
            if d.year == year:
                yd.add(d)
    if byweekno is not None:
        wdays = _weekno_days(year, wkst, byweekno)
    if byyearday is not None and byweekno is not None:
        days = yd & wdays
    elif byweekno is not None:
        days = wdays
    else:
        days = yd
    keep = set()
    for d in days:
        if bymonth is not None and d.month not in bymonth:
            continue
        if bymonthday is not None and not _day_matches_monthday(d, bymonthday):
            continue
        if byday is not None:
            if not _day_matches_byday(d, byday):
                continue
        elif byweekno is not None and d.weekday() != dt_date.weekday():
            continue
        keep.add(d)
    return keep


# ---------------------------------------------------------------- store input

def read_text(path):
    with open(path, 'r', encoding='utf-8') as fh:
        return fh.read()


def read_bytes(path):
    with open(path, 'rb') as fh:
        return fh.read()


def find_index(data_dir):
    found = []
    for name in sorted(os.listdir(data_dir)):
        path = os.path.join(data_dir, name)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, 'rb') as fh:
                head = fh.read(4096)
            if head.lstrip()[:1] != b'{':
                continue
            with open(path, 'rb') as fh:
                doc = json.loads(fh.read().decode('utf-8'))
        except (OSError, ValueError, UnicodeDecodeError):
            continue
        if isinstance(doc, dict) and doc.get('format') == 'exec-ops-store/2':
            found.append(doc)
    if len(found) != 1:
        raise SystemExit('store index not found or not unique')
    return found[0]


def split_rows(text, delim):
    out = []
    for line in text.split('\n'):
        line = line.rstrip('\r')
        if line == '':
            continue
        out.append(line.split(delim))
    return out


def keyed_rows(text, delim):
    """One {column: value} per data row of a delimited file with a header."""
    rows = [r for r in split_rows(text, delim)
            if not (r and r[0].startswith('#'))]
    if not rows:
        return []
    header = [h.strip() for h in rows[0]]
    out = []
    for line in rows[1:]:
        rec = {}
        for i, name in enumerate(header):
            rec[name] = line[i] if i < len(line) else ''
        out.append(rec)
    return out


def psv_rows(text):
    """Rows of a pipe separated file with backslash escapes."""
    out = []
    for line in text.split('\n'):
        line = line.rstrip('\r')
        if line == '' or line.startswith('#'):
            continue
        fields = []
        cur = []
        i = 0
        while i < len(line):
            ch = line[i]
            if ch == '\\' and i + 1 < len(line):
                cur.append(line[i + 1])
                i += 2
                continue
            if ch == '|':
                fields.append(''.join(cur))
                cur = []
                i += 1
                continue
            cur.append(ch)
            i += 1
        fields.append(''.join(cur))
        out.append(fields)
    if not out:
        return []
    header = [h.strip() for h in out[0]]
    result = []
    for fields in out[1:]:
        rec = {}
        for i, name in enumerate(header):
            rec[name] = fields[i] if i < len(fields) else ''
        result.append(rec)
    return result


DURATION_RE = re.compile(r'[-+]?P(?:[0-9]+[WDHMS])*(?:T(?:[0-9]+[HMS])*)?')


def is_duration(text):
    return bool(DURATION_RE.fullmatch(str(text).strip().upper()))


def parse_date_text(text):
    s = text.strip()
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', s):
        return date(int(s[0:4]), int(s[5:7]), int(s[8:10]))
    if re.fullmatch(r'\d{8}', s):
        return date(int(s[0:4]), int(s[4:6]), int(s[6:8]))
    raise ValueError('bad date %r' % text)


def num(text):
    """Read a number that may be text with comma separators."""
    if isinstance(text, int):
        return text
    s = str(text).strip().replace(',', '')
    if s == '':
        return None
    return int(s)


def serial_date(value, epoch):
    n = int(value)
    return epoch + timedelta(n)


def load_register(path, edition):
    sheets, epoch, order = xlsx_sheets(path)
    offices = {}
    office_order = []
    rates = {}
    for name in order:
        cells = sheets[name]
        a1 = sheet_cell(cells, 'A1')
        b1 = sheet_cell(cells, 'B1')
        b2 = sheet_cell(cells, 'B2')
        if a1 not in ('office register', 'attendee rates'):
            continue
        if b1 != edition or b2 != 'in force':
            continue
        header = {}
        for row, values in sheet_rows(cells):
            if row == 4:
                for col, text in values.items():
                    header[text.strip().lower()] = col
                continue
            if row < 5:
                continue
            def col(key):
                return values.get(header.get(key, -1), '')
            if a1 == 'office register':
                code = col('office')
                if not code:
                    continue
                eff = col('effective from')
                rec = {
                    'tzid': col('tzid'),
                    'longitude': col('longitude'),
                    'weekday': col('weekday'),
                    'working': col('working'),
                    'open': num(col('open minute')),
                    'close': num(col('close minute')),
                    'solar_open': num(col('solar open')),
                    'solar_close': num(col('solar close')),
                    'effective': serial_date(eff, epoch),
                }
                offices.setdefault(code, {'rows': []})
                if 'tzid' not in offices[code]:
                    offices[code]['tzid'] = rec['tzid']
                    offices[code]['longitude'] = rec['longitude']
                    office_order.append(code)
                offices[code]['rows'].append(rec)
            else:
                att = col('attendee')
                if not att:
                    continue
                rates.setdefault(att, []).append(
                    (serial_date(col('effective from'), epoch),
                     num(col('cents per hour'))))
    return offices, office_order, rates


def solar_offset_minutes(longitude_text):
    d = Decimal(str(longitude_text).strip()) * Decimal(4)
    rounded = d.quantize(Decimal(1), rounding='ROUND_HALF_UP')
    if rounded == 0:
        return 0
    return int(rounded)


# ---------------------------------------------------------------- components

def comp_uid(comp):
    return prop_text(comp, 'UID') or ''


def comp_rid_raw(comp):
    p = comp.first('RECURRENCE-ID')
    if p is None or not p[2]:
        return ''
    return to_basic(str(p[2][0][1]))


def comp_sequence(comp):
    p = comp.first('SEQUENCE')
    if p is None or not p[2]:
        return 0
    try:
        return int(str(p[2][0][1]).strip())
    except ValueError:
        return 0


def comp_modified(comp):
    """LAST-MODIFIED if present, else DTSTAMP, else None."""
    for name in ('LAST-MODIFIED', 'DTSTAMP'):
        p = comp.first(name)
        if p is not None and p[2]:
            return to_basic(str(p[2][0][1]))
    return None


def comp_attendees(comp):
    """The required participant references of a component, as written."""
    out = []
    for p in comp.all('ATTENDEE'):
        role = None
        ident = None
        for pname, pvals in p[1]:
            if pname == 'ROLE':
                role = pvals[0] if pvals else None
            elif pname == 'X-ATT-ID':
                ident = pvals[0] if pvals else None
        if role is not None and role.strip().upper() != 'REQ-PARTICIPANT':
            continue
        if ident is None or ident == '':
            continue
        out.append(ident)
    return out


def comp_status(comp):
    return prop_text(comp, 'STATUS') or ''


def comp_is_cancelled(comp):
    return comp_status(comp).strip().upper() == 'CANCELLED'


def comp_range(comp):
    val = None
    p = comp.first('RECURRENCE-ID')
    if p is not None:
        for pname, pvals in p[1]:
            if pname == 'RANGE':
                val = pvals[0] if pvals else None
    if val is None:
        return ''
    return val.strip().upper()


def set_prop(comp, name, kind, value):
    comp.props = [p for p in comp.props if p[0] != name]
    comp.props.append(_mk_prop(name, [], [(kind, value)]))


def remove_props(comp, names):
    names = set(n.upper() for n in names)
    comp.props = [p for p in comp.props if p[0] not in names]


def rrule_of(comp):
    p = comp.first('RRULE')
    if p is None or not p[2]:
        return None
    return p[2][0][1]


def count_of(rule):
    if rule is None:
        return None
    vals = rule.get('COUNT')
    if not vals:
        return None
    try:
        return int(str(vals[0]))
    except ValueError:
        return None


def until_of(rule):
    if rule is None:
        return None, None
    vals = rule.get('UNTIL')
    if not vals:
        return None, None
    text = str(vals[0]).strip()
    isz, wall = parse_dt_value(to_basic(text))
    return isz, wall


# ---------------------------------------------------------------- the pass

class Pass(object):

    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.index = find_index(data_dir)
        self.files = self.index.get('files') or {}
        self.store = self.index.get('store') or {}
        self.collections = list(self.store.get('collections') or [])
        self.coll_ids = [c.get('id') for c in self.collections]
        self.coll_pos = {c.get('id'): i for i, c in enumerate(self.collections)}
        win = self.store.get('window') or {}
        self.win_start_date = parse_date_text(win.get('start'))
        self.win_end_date = parse_date_text(win.get('end'))
        self.win_start = date_to_wall(self.win_start_date)
        self.win_end = date_to_wall(self.win_end_date + timedelta(1))
        self.policy = self.store.get('conflict_policy') or ''
        self.duration_semantics = self.store.get('duration_semantics') or ''
        self.authority_replica = self.store.get('authority_replica') or ''
        self.policy_revision = int(self.store.get('policy_revision') or 0)
        self.register_edition = str(self.store.get('register_edition') or '')
        self.path = {}
        for role, name in self.files.items():
            self.path[role] = os.path.join(data_dir, name)
        self.alias_links = {}
        self.zones = {}
        self.zone_alias = {}

    # -- loading

    def load(self):
        self.load_governance()
        self.load_zone_aliases()
        horizon = self.win_end + 400 * 86400
        self.zones = build_zones(self.path['zones'], horizon)
        self.offices, self.office_order, self.rates = \
            load_register(self.path['register'], self.register_edition)
        self.solar = {}
        for code, info in self.offices.items():
            self.solar[code] = solar_offset_minutes(info['longitude'])
        self.office_zone = {}
        for code, info in self.offices.items():
            self.office_zone[code] = self.zones.get(
                self.zone_name(info['tzid']))
        self.default_zone = None
        if self.office_order:
            self.default_zone = self.office_zone.get(self.office_order[0])
        self.load_attendees()
        self.load_handles()
        self.load_closures()
        self.load_busy()
        self.load_legs()

    def load_governance(self):
        tables = pdf_tables(self.path['governance'])
        revisions = []
        status = {}
        for row in self._rows(tables, 'Revision register'):
            rev = int(row['revision'])
            revisions.append(rev)
            status[rev] = (row.get('status') or '').strip()
        approved = sorted(r for r in revisions if status.get(r) == 'approved')
        greatest = approved[-1] if approved else 0
        self.effective_revision = min(self.policy_revision, greatest)
        usable = set(r for r in approved if r <= self.effective_revision)
        self.usable_revisions = usable
        self.approved_revisions = set(approved)
        params = None
        for row in self._rows(tables, 'Settling parameters'):
            rev = int(row['revision'])
            if rev in usable:
                if params is None or rev > params[0]:
                    params = (rev, row)
        if params is None:
            raise SystemExit('no settling parameters in force')
        row = params[1]
        self.buffer_minutes = self._int(row.get('buffer min'))
        self.quantum_minutes = self._int(row.get('quantum min'))
        self.round_cap = self._int(row.get('round cap'))
        self.pin_rank = self._int(row.get('pin rank'))
        self.default_rank = self._int(row.get('default rank'))
        self.class_ranks = {}
        for r in self._rows(tables, 'Series class ranks'):
            rev = int(r['revision'])
            if rev not in usable:
                continue
            cls = (r.get('class') or '').strip()
            rank = self._int(r.get('rank'))
            cur = self.class_ranks.get(cls)
            if cur is None or rev > cur[0]:
                self.class_ranks[cls] = (rev, rank)
        self.class_ranks = {k: v[1] for k, v in self.class_ranks.items()}
        self.conversion = {}
        for r in self._rows(tables, 'Office conversion'):
            rev = int(r['revision'])
            if rev not in usable:
                continue
            office = (r.get('office') or '').strip()
            bps = self._int(r.get('basis points'))
            cur = self.conversion.get(office)
            if cur is None or rev > cur[0]:
                self.conversion[office] = (rev, bps)
        self.conversion = {k: v[1] for k, v in self.conversion.items()}

    def _rows(self, tables, name):
        for key in tables:
            if key.strip().lower() == name.strip().lower():
                return tables[key]['rows']
        return []

    def _int(self, text):
        try:
            return int(str(text).strip().replace(',', ''))
        except (ValueError, TypeError):
            return 0

    def load_zone_aliases(self):
        path = self.path.get('zone_aliases')
        self.zone_alias = {}
        if not path or not os.path.exists(path):
            return
        try:
            doc = json.loads(read_bytes(path).decode('utf-8'))
        except ValueError:
            return
        for entry in doc.get('aliases') or []:
            if str(entry.get('status', '')).lower() != 'active':
                continue
            self.zone_alias[str(entry.get('alias'))] = str(entry.get('target'))

    def zone_name(self, name):
        seen = set()
        while name in self.zone_alias and name not in seen:
            seen.add(name)
            name = self.zone_alias[name]
        return name

    def zone_for(self, tzid):
        name = self.zone_name(tzid) if tzid else tzid
        if name is None:
            return None
        return self.zones.get(name)

    def load_attendees(self):
        self.attendees = {}
        self.attendee_order = []
        for rec in keyed_rows(read_text(self.path['attendees']), '\t'):
            ident = rec.get('id', '').strip()
            if not ident:
                continue
            if ident not in self.attendees:
                self.attendee_order.append(ident)
            self.attendees[ident] = {
                'home_office': rec.get('home_office', '').strip(),
            }

    def load_handles(self):
        self.alias_links = {}
        for rec in keyed_rows(read_text(self.path['aliases']), ','):
            if str(rec.get('status', '')).strip().lower() != 'active':
                continue
            handle = rec.get('handle', '')
            target = rec.get('target', '')
            eff = parse_date_text(rec.get('effective_from', ''))
            self.alias_links.setdefault(handle, []).append((eff, target))

    def load_closures(self):
        self.closures = {}
        if 'closures' not in self.path:
            return
        conn = sqlite3.connect(self.path['closures'])
        try:
            rows = conn.execute(
                'SELECT office, day, revision, state FROM closures').fetchall()
        finally:
            conn.close()
        for office, day, revision, state in rows:
            key = (office, day)
            cur = self.closures.get(key)
            if cur is None or int(revision) > cur[0]:
                self.closures[key] = (int(revision), state)

    def load_busy(self):
        self.periods = []
        conn = sqlite3.connect(self.path['freebusy'])
        try:
            rows = conn.execute(
                'SELECT source, attendee, fbtype, start, finish, withdrawn '
                'FROM periods').fetchall()
        finally:
            conn.close()
        for source, attendee, fbtype, start, finish, withdrawn in rows:
            try:
                wval = int(str(withdrawn).strip() or '0')
            except ValueError:
                wval = 1
            if wval != 0:
                continue
            if (fbtype or '') == 'FREE':
                continue
            _isz, startwall = parse_dt_value(to_basic(start))
            inst = startwall
            endtext = str(finish).strip()
            if is_duration(endtext):
                wk, dd, hh, mm, ss = _parse_duration(endtext)
                endinst = inst + (wk * 604800 + dd * 86400 + hh * 3600 +
                                  mm * 60 + ss)
            else:
                _eisz, endwall = parse_dt_value(to_basic(endtext))
                endinst = endwall
            self.periods.append({
                'attendee': attendee,
                'fbtype': 'BUSY' if fbtype is None else fbtype,
                'start': inst,
                'end': endinst,
            })

    def load_legs(self):
        self.legs = []
        root = ET.fromstring(read_bytes(self.path['itineraries']))
        for leg in root.iter('leg'):
            status = leg.get('status')
            if status is not None and status.strip().lower() != 'confirmed':
                continue
            ident = leg.get('id') or ''
            attendee = leg.get('attendee') or ''
            depart = None
            arrive = None
            for child in leg:
                tag = child.tag.split('}')[-1].lower()
                if tag not in ('depart', 'arrive'):
                    continue
                office = child.get('office') or ''
                local = child.get('local') or ''
                rec = {'office': office, 'local': to_basic(local)}
                if tag == 'depart':
                    depart = rec
                else:
                    arrive = rec
            if depart is None or arrive is None:
                continue
            self.legs.append({'id': ident, 'attendee': attendee,
                              'depart': depart, 'arrive': arrive})


    # -- office and attendee helpers

    def zone_of_office(self, office):
        zone = self.office_zone.get(office)
        if zone is not None:
            return zone
        return self.default_zone

    def office_row(self, office, day):
        """The register row in force for an office on a date."""
        wd = day.weekday()
        best = None
        info = self.offices.get(office)
        if info is None:
            return None
        for row in info['rows']:
            if row['weekday'] != WEEKDAYS[wd]:
                continue
            if row['effective'] > day:
                continue
            if best is None or row['effective'] > best['effective']:
                best = row
        return best

    def rate_for(self, attendee, day):
        rows = self.rates.get(attendee)
        if not rows:
            return 0
        best = None
        for eff, cents in rows:
            if eff > day:
                continue
            if best is None or eff > best[0]:
                best = (eff, cents)
        return best[1] if best else 0

    def closure_state(self, office, day):
        """True when the office is closed on that day."""
        cur = self.closures.get((office, day.isoformat()))
        if cur is None:
            return False
        return cur[1] != 'withdrawn'

    def resolve_value(self, value, tzid):
        """(instant, classification, shift, zone name) for a property value."""
        basic = to_basic(str(value))
        isz, wall = parse_dt_value(basic)
        zname = self.zone_name(tzid) if tzid else None
        if isz:
            return wall, 'unique', 0, zname
        zone = self.zones.get(zname) if zname else None
        if zone is None:
            return wall, 'unique', 0, zname
        inst, cls, shift = zone.resolve(wall)
        return inst, cls, shift, zone.tzid

    def instant_of(self, comp, name):
        p = comp.first(name)
        if p is None or not p[2]:
            return None, None, None
        tzid = None
        for pname, pvals in p[1]:
            if pname == 'TZID':
                tzid = pvals[0] if pvals else None
        inst, cls, shift, zname = self.resolve_value(p[2][0][1], tzid)
        return inst, cls, zname

    # -- handle resolution

    def resolve_handle(self, ref, day):
        """(result, hops, outcome) for one reference on one date."""
        walk = [ref]
        current = ref
        hops = 0
        while True:
            links = self.alias_links.get(current)
            best = None
            if links:
                for eff, target in links:
                    if eff > day:
                        continue
                    if best is None:
                        best = (eff, target)
                    elif eff > best[0]:
                        best = (eff, target)
                    elif eff == best[0] and target < best[1]:
                        best = (eff, target)
            if best is None:
                break
            hops += 1
            target = best[1]
            if target in walk:
                start = walk.index(target)
                names = walk[start:] + [target]
                result = min(names)
                if result not in self.attendees:
                    return '', hops, 'unresolved'
                return result, hops, 'cycle'
            walk.append(target)
            current = target
        if current not in self.attendees:
            return '', hops, 'unresolved'
        if hops == 0:
            return current, 0, 'direct'
        return current, hops, 'resolved'

    # -- replicas and outbox

    def decode_replicas(self):
        self.replicas = {}
        for coll in self.collections:
            cid = coll.get('id')
            reps = coll.get('replicas') or {}
            for rep in ('local', 'server'):
                name = reps.get(rep)
                if not name:
                    self.replicas[(cid, rep)] = []
                    continue
                path = os.path.join(self.data_dir, name)
                if not os.path.exists(path):
                    path = self.path.get(rep) or path
                comps = [c for c in decode_calendar(path) if c.name == 'VEVENT']
                self.replicas[(cid, rep)] = comps

    def replay_outbox(self):
        ops = psv_rows(read_text(self.path['outbox']))
        ops = [o for o in ops if o.get('collection') in self.coll_pos]
        ops.sort(key=lambda o: int(o.get('op_seq') or 0))
        self.server_index = {}
        for comp in self.replicas.get(('x', 'server'), []) or []:
            pass
        for coll in self.collections:
            cid = coll.get('id')
            index = {}
            for comp in self.replicas[(cid, 'server')]:
                index[(comp_uid(comp), comp_rid_raw(comp))] = comp
            self.server_index[cid] = index
        self.outbox_report = []
        for op in ops:
            cid = op.get('collection')
            uid = op.get('uid') or ''
            rid = to_basic(op.get('recurrence_id') or '')
            index = self.server_index.get(cid) or {}
            target = index.get((uid, rid))
            kind = (op.get('op') or '').strip().upper()
            if target is None:
                outcome = 'missing'
                seq_after = None
            else:
                base = int(op.get('base_sequence') or 0)
                current = comp_sequence(target)
                if current != base:
                    outcome = 'stale-base'
                    seq_after = current
                else:
                    outcome = 'applied'
                    if kind == 'DELETE':
                        del index[(uid, rid)]
                        seq_after = None
                    else:
                        seq_after = current
                        field = (op.get('field') or '').strip().upper()
                        value = op.get('value') or ''
                        if field == 'SEQUENCE':
                            set_prop(target, 'SEQUENCE', 'integer', value)
                            seq_after = int(value)
                        elif field == 'SUMMARY':
                            set_prop(target, 'SUMMARY', 'text', value)
                        elif field == 'STATUS':
                            set_prop(target, 'STATUS', 'text', value)
                        elif field == 'X-SERIES-CLASS':
                            set_prop(target, 'X-SERIES-CLASS', 'text', value)
                        elif field == 'DURATION':
                            remove_props(target, ['DTEND'])
                            set_prop(target, 'DURATION', 'duration', value)
                    stamp = op.get('stamp') or ''
                    if stamp:
                        set_prop(target, 'LAST-MODIFIED', 'datetime', stamp)
            self.outbox_report.append({
                'op_seq': int(op.get('op_seq') or 0),
                'collection': cid,
                'uid': uid,
                'recurrence_id': op.get('recurrence_id') or '',
                'op': kind,
                'field': '' if kind == 'DELETE' else (op.get('field') or ''),
                'outcome': outcome,
                'sequence_after': seq_after,
            })

    # -- change log

    def load_journal(self):
        records = {}
        order = []

        def add(coll, rep, uid, rid, rev, is_delete, current):
            key = (coll, rep, uid, rid, rev)
            if current:
                if key in records and records[key][2]:
                    return
                records[key] = (is_delete, True)
            else:
                if key in records:
                    return
                records[key] = (is_delete, False)
            order.append(key)

        for line in split_rows(read_text(self.path['journal']), '\x00'):
            pass
        for line in read_text(self.path['journal']).split('\n'):
            line = line.strip()
            if not line:
                continue
            try:
                doc = json.loads(line)
            except ValueError:
                continue
            rid = doc.get('recurrence_id')
            if rid is None:
                rid = ''
            add(str(doc.get('collection') or ''), str(doc.get('replica') or ''),
                str(doc.get('uid') or ''), str(rid),
                int(doc.get('revision') or 0),
                str(doc.get('op') or '').lower() == 'delete', True)
        for line in read_text(self.path['journal_legacy']).split('\n'):
            line = line.strip()
            if not line:
                continue
            try:
                doc = json.loads(line)
            except ValueError:
                continue
            side = str(doc.get('side') or '')
            rep = 'local' if side.upper() == 'L' else 'server'
            action = str(doc.get('action') or '').upper()
            rid = doc.get('rid')
            if rid is None or rid == '':
                rid = ''
            else:
                rid = to_basic(str(rid))
            add(str(doc.get('cal') or ''), rep, str(doc.get('object') or ''),
                rid, int(doc.get('rev') or 0), action == 'DEL', False)
        self.revisions = {}
        self.deletes = {}
        for (coll, rep, uid, rid, rev) in order:
            is_delete, current = records[(coll, rep, uid, rid, rev)]
            key = (coll, rep, uid, rid)
            if is_delete:
                cur = self.deletes.get(key)
                if cur is None or rev > cur:
                    self.deletes[key] = rev
            else:
                cur = self.revisions.get(key)
                if cur is None or rev > cur:
                    self.revisions[key] = rev

    def revision_of(self, coll, rep, uid, rid):
        val = self.revisions.get((coll, rep, uid, rid))
        return val if val is not None else -1

    # -- merge

    def merge(self):
        self.by_key = {}
        for coll in self.collections:
            cid = coll.get('id')
            for rep in ('local', 'server'):
                for comp in self.replicas[(cid, rep)]:
                    key = (cid, comp_uid(comp), comp_rid_raw(comp))
                    self.by_key.setdefault(key, {})[rep] = comp
        self.decisions = []
        self.merged = {}
        self.tombstoned = set()
        counts = {'components': 0, 'contested': 0, 'sole_replica': 0,
                  'tombstoned': 0}
        hrefs = {}
        for key in sorted(self.by_key, key=lambda k: (k[0], k[1], k[2])):
            coll, uid, rid = key
            holders = self.by_key[key]
            has_local = 'local' in holders
            has_server = 'server' in holders
            href = self.collection_href(coll, uid)
            if has_local and has_server:
                counts['contested'] += 1
                winner, loser, rule = self.contest(key, holders)
                winning_seq = comp_sequence(holders[winner])
                losing_seq = comp_sequence(holders[loser])
                self.merged[key] = holders[winner]
                counts['components'] += 1
            elif has_local or has_server:
                holder = 'local' if has_local else 'server'
                other = 'server' if has_local else 'local'
                seq = comp_sequence(holders[holder])
                del_rev = self.deletes.get((coll, other, uid, rid))
                hold_rev = self.revision_of(coll, holder, uid, rid)
                if del_rev is not None and del_rev > hold_rev:
                    winner = other
                    loser = holder
                    rule = 'tombstone'
                    winning_seq = -1
                    losing_seq = seq
                    self.tombstoned.add(key)
                    counts['tombstoned'] += 1
                else:
                    winner = holder
                    loser = ''
                    rule = 'sole-replica'
                    winning_seq = seq
                    losing_seq = -1
                    self.merged[key] = holders[holder]
                    counts['components'] += 1
                    counts['sole_replica'] += 1
            else:
                continue
            self.decisions.append({
                'collection': coll,
                'uid': uid,
                'recurrence_id': rid,
                'href': href,
                'winner': winner,
                'loser': loser,
                'rule': rule,
                'winning_sequence': winning_seq,
                'losing_sequence': losing_seq,
            })
        self.counts = counts
        self.holders = {}
        for key, comp in self.merged.items():
            coll, uid, rid = key
            self.holders.setdefault((coll, uid), []).append(rid)
        self.primary = {}
        self.duplicate_uids = []
        by_uid = {}
        for coll, uid in self.holders:
            by_uid.setdefault(uid, []).append(coll)
        for uid in sorted(by_uid):
            colls = by_uid[uid]
            ordered = sorted(set(colls), key=lambda c: self.coll_pos.get(c, 0))
            if len(ordered) > 1:
                self.duplicate_uids.append({
                    'uid': uid,
                    'collections': ordered,
                    'primary_collection': ordered[0],
                })
            for c in ordered:
                self.primary[(c, uid)] = ordered[0]

    def collection_href(self, coll, uid):
        href = ''
        for entry in self.collections:
            if entry.get('id') == coll:
                href = entry.get('href') or ''
                break
        if not href.endswith('/') and href != '':
            href += '/'
        return href + uid + '.ics'

    def contest(self, key, holders):
        coll, uid, rid = key
        if self.policy == 'sequence-major':
            lseq = comp_sequence(holders['local'])
            sseq = comp_sequence(holders['server'])
            if lseq != sseq:
                return ('local', 'server', 'sequence') if lseq > sseq else \
                       ('server', 'local', 'sequence')
        else:
            lmod = comp_modified(holders['local'])
            smod = comp_modified(holders['server'])
            if lmod is not None or smod is not None:
                if lmod is None:
                    return 'server', 'local', 'last-modified'
                if smod is None:
                    return 'local', 'server', 'last-modified'
                if lmod != smod:
                    return ('local', 'server', 'last-modified') if lmod > smod \
                        else ('server', 'local', 'last-modified')
        lrev = self.revision_of(coll, 'local', uid, rid)
        srev = self.revision_of(coll, 'server', uid, rid)
        if lrev != srev:
            return ('local', 'server', 'revision') if lrev > srev else \
                   ('server', 'local', 'revision')
        return ('local', 'server', 'authority') if \
            self.authority_replica == 'local' else ('server', 'local',
                                                   'authority')

    # -- durations

    def span_of(self, comp):
        """(seconds, source) from DTEND, DURATION or the default."""
        dtend = comp.first('DTEND')
        if dtend is not None and dtend[2]:
            start, _cls, _z = self.instant_of(comp, 'DTSTART')
            end, _c2, _z2 = self.instant_of(comp, 'DTEND')
            if start is None or end is None:
                return None, None
            return end - start, 'DTEND'
        dur = comp.first('DURATION')
        if dur is not None and dur[2]:
            return dur[2][0][1], 'DURATION'
        return None, 'DEFAULT'

    def duration_span(self, spec, start_instant, office):
        """Seconds of a duration spec applied to a start instant."""
        if spec is None:
            return 3600
        if isinstance(spec, int):
            return spec
        weeks, days, hours, minutes, seconds = _parse_duration(str(spec))
        if weeks == 0 and days == 0:
            return (weeks * 604800 + days * 86400 + hours * 3600 +
                    minutes * 60 + seconds)
        if self.duration_semantics == 'exact':
            return (weeks * 604800 + days * 86400 + hours * 3600 +
                    minutes * 60 + seconds)
        zone = self.zone_of_office(office)
        if zone is None:
            return (weeks * 604800 + days * 86400 + hours * 3600 +
                    minutes * 60 + seconds)
        wall = zone.wall_at(start_instant)
        newinst = zone.resolve(wall + (weeks * 7 + days) * 86400)[0]
        return newinst - start_instant + hours * 3600 + minutes * 60 + seconds

    # -- expansion

    def series_candidates(self, coll, uid, master):
        """Candidate entries of a series, each a dict."""
        dt = master.first('DTSTART')
        if dt is None or not dt[2]:
            return None
        dtval = str(dt[2][0][1])
        tzid = None
        for pname, pvals in dt[1]:
            if pname == 'TZID':
                tzid = pvals[0] if pvals else None
        basic = to_basic(dtval)
        isz, dtwall = parse_dt_value(basic)
        zone = self.zone_for(tzid)
        zname = zone.tzid if zone is not None else (tzid or '')
        if isz or zone is None:
            resolve = lambda w: (w, 'unique', 0)
        else:
            resolve = zone.resolve
        horizon = self.win_end + 400 * 86400
        rule = rrule_of(master)
        if rule is None:
            cands = [dtwall]
        else:
            until_isz, until_wall = until_of(rule)
            until_inst = None
            if until_wall is not None:
                until_inst = until_wall
                if not until_isz and zone is not None:
                    until_inst = zone.resolve(until_wall)[0]
            cands = expand_rrule(rule, dtwall, horizon, count_of(rule),
                                 until_inst, resolve)
        entries = []
        seen = set()
        for w in cands:
            inst, cls, shift = resolve(w)
            entries.append({
                'instant': inst,
                'tzid': zname,
                'nominal': fmt_wall(w),
                'classification': cls,
                'shift': shift,
                'period': None,
                'rule': True,
            })
            seen.add(inst)
        for prop in master.all('RDATE'):
            rtzid = None
            for pname, pvals in prop[1]:
                if pname == 'TZID':
                    rtzid = pvals[0] if pvals else None
            for kind, val in prop[2]:
                if isinstance(val, tuple):
                    first, second = val
                    period = {'end': str(second), 'tzid': rtzid}
                else:
                    first = val
                    period = None
                fbasic = to_basic(str(first))
                fisz, fwall = parse_dt_value(fbasic)
                if fisz:
                    finst = fwall
                    if zone is not None:
                        nominal = fmt_wall(zone.wall_at(finst))
                    else:
                        nominal = fmt_wall(finst)
                    entry = {'instant': finst, 'tzid': zname,
                             'nominal': nominal, 'classification': 'unique',
                             'shift': 0, 'period': period, 'rule': False}
                else:
                    finst, cls, shift, fzname = self.resolve_value(first,
                                                                  rtzid)
                    entry = {'instant': finst, 'tzid': fzname or '',
                             'nominal': fmt_wall(fwall), 'classification': cls,
                             'shift': shift, 'period': period, 'rule': False}
                if entry['instant'] in seen:
                    continue
                seen.add(entry['instant'])
                entries.append(entry)
        return entries

    def expand_series(self, coll, uid, master, overrides):
        entries = self.series_candidates(coll, uid, master)
        if entries is None:
            return
        series = []
        for entry in entries:
            if not (self.win_start <= entry['instant'] < self.win_end):
                continue
            self.resolutions.append({
                'collection': coll, 'uid': uid, 'entry': entry})
            occ = {
                'collection': coll,
                'uid': uid,
                'instant': entry['instant'],
                'period': entry['period'],
                'period_tzid': None,
                'from_rdate': entry['period'] is not None,
            }
            series.append(occ)
        occs = dict((o['instant'], o) for o in series)
        # exclusions
        for prop in master.all('EXDATE'):
            etzid = None
            for pname, pvals in prop[1]:
                if pname == 'TZID':
                    etzid = pvals[0] if pvals else None
            for kind, val in prop[2]:
                inst, cls, shift, zname = self.resolve_value(val, etzid)
                if inst in occs:
                    del occs[inst]
                    self.exceptions['exdate-applied'].append({
                        'kind': 'exdate-applied', 'collection': coll,
                        'uid': uid, 'exdate_utc': fmt_instant(inst)})
                else:
                    self.exceptions['exdate-unmatched'].append({
                        'kind': 'exdate-unmatched', 'collection': coll,
                        'uid': uid, 'exdate_utc': fmt_instant(inst)})
        # overrides
        groups = {}
        for ov in overrides:
            rid = ov.first('RECURRENCE-ID')
            if rid is None or not rid[2]:
                continue
            otzid = None
            for pname, pvals in rid[1]:
                if pname == 'TZID':
                    otzid = pvals[0] if pvals else None
            inst, cls, shift, zname = self.resolve_value(rid[2][0][1], otzid)
            groups.setdefault(inst, []).append(ov)
        applied = {}
        for inst in groups:
            group = groups[inst]
            if inst not in occs:
                for ov in group:
                    self.exceptions['override-rejected'].append({
                        'kind': 'override-rejected', 'collection': coll,
                        'uid': uid, 'recurrence_id_utc': fmt_instant(inst),
                        'reason': 'orphan-recurrence-id'})
                continue
            group.sort(key=lambda c: (comp_sequence(c), comp_rid_raw(c)))
            chosen = group[-1]
            for other in group[:-1]:
                self.exceptions['override-rejected'].append({
                    'kind': 'override-rejected', 'collection': coll,
                    'uid': uid, 'recurrence_id_utc': fmt_instant(inst),
                    'reason': 'superseded-recurrence-id'})
            start, _cls, _z = self.instant_of(chosen, 'DTSTART')
            if start is None:
                start = inst
            delta = start - inst
            self.exceptions['override-applied'].append({
                'kind': 'override-applied', 'collection': coll, 'uid': uid,
                'recurrence_id_utc': fmt_instant(inst),
                'range': comp_range(chosen),
                'delta_minutes': delta // 60})
            applied[inst] = (chosen, start, delta)
            if comp_is_cancelled(chosen):
                del occs[inst]
        ranged = sorted(
            [(inst, v[1], v[0], v[2]) for inst, v in applied.items()
             if not comp_is_cancelled(v[0]) and comp_range(v[0]) ==
             'THISANDFUTURE'], key=lambda t: t[0])
        for inst in occs:
            occ = occs[inst]
            target = applied.get(inst)
            if target is not None:
                comp = target[0]
                start = target[1]
                shift = 0
                override = True
                office, summary, klass, refs = self.content_of(comp, master)
                spec, source = self.span_of(comp)
                if spec is None:
                    spec, source = self.base_spec(occ, master)
                else:
                    source = source
                if isinstance(spec, str):
                    seconds = self.duration_span(spec, start, office)
                else:
                    seconds = spec
            else:
                src = None
                shift = 0
                for item in ranged:
                    if item[0] < inst:
                        src = item
                        shift += item[3]
                    else:
                        break
                override = False
                if src is not None:
                    comp = src[2]
                    office, summary, klass, refs = self.content_of(comp,
                                                                  master)
                    spec, source = self.span_of(comp)
                    if isinstance(spec, str):
                        start = inst + shift
                        seconds = self.duration_span(spec, start, office)
                    else:
                        seconds = spec if spec is not None else 3600
                    source = source if spec is not None else 'DEFAULT'
                else:
                    office, summary, klass, refs = self.content_of(master,
                                                                  master)
                    spec, source = self.base_spec(occ, master)
                    if isinstance(spec, str):
                        start = inst + shift
                        seconds = self.duration_span(spec, start, office)
                    else:
                        seconds = spec if spec is not None else 3600
                start = inst + shift
            if shift != 0:
                self.exceptions['shift'].append({
                    'kind': 'shift',
                    'occurrence_id': '%s:%s:%s' % (coll, uid,
                                                   fmt_instant(inst)),
                    'applied_shift_minutes': shift // 60})
            occ.update({
                'occurrence_id': '%s:%s:%s' % (coll, uid, fmt_instant(inst)),
                'office': office,
                'summary': summary,
                'series_class': klass,
                'refs': refs,
                'start': start,
                'duration': seconds,
                'duration_source': source,
                'shift': shift,
                'override': override,
            })
            self.occurrences.append(occ)

    def content_of(self, comp, master):
        office = prop_text(comp, 'X-OFFICE') or prop_text(master, 'X-OFFICE')
        summary = prop_text(comp, 'SUMMARY') or prop_text(master, 'SUMMARY')
        klass = prop_text(comp, 'X-SERIES-CLASS') or \
            prop_text(master, 'X-SERIES-CLASS')
        refs = comp_attendees(comp) or comp_attendees(master)
        return office or '', summary or '', klass or '', refs

    def base_spec(self, occ, master):
        """(spec, source) an occurrence has without any override."""
        if occ['from_rdate']:
            period = occ['period']
            if period is None:
                return self.span_of(master)
            endtext = period['end']
            if is_duration(endtext):
                return endtext, 'RDATE'
            end_instant, _cls, _shift, _z = self.resolve_value(
                endtext, period['tzid'])
            return end_instant - occ['instant'], 'RDATE'
        return self.span_of(master)

    # -- occurrence list

    def build_occurrences(self):
        self.occurrences = []
        self.resolutions = []
        self.exceptions = {
            'exdate-applied': [], 'exdate-unmatched': [],
            'override-applied': [], 'override-rejected': [], 'shift': []}
        for (coll, uid) in sorted(self.holders):
            if self.primary.get((coll, uid), coll) != coll:
                continue
            rids = self.holders[(coll, uid)]
            master = self.merged.get((coll, uid, ''))
            overrides = [self.merged[(coll, uid, r)] for r in rids
                         if r != '' and (coll, uid, r) in self.merged]
            if master is None:
                for ov in overrides:
                    rid = ov.first('RECURRENCE-ID')
                    if rid is None or not rid[2]:
                        continue
                    otzid = None
                    for pname, pvals in rid[1]:
                        if pname == 'TZID':
                            otzid = pvals[0] if pvals else None
                    inst, _cls, _shift, _z = self.resolve_value(
                        rid[2][0][1], otzid)
                    self.exceptions['override-rejected'].append({
                        'kind': 'override-rejected', 'collection': coll,
                        'uid': uid, 'recurrence_id_utc': fmt_instant(inst),
                        'reason': 'missing-master'})
                continue
            self.expand_series(coll, uid, master, overrides)
        for occ in self.occurrences:
            occ['end'] = occ['start'] + occ['duration']
            self.finish_occurrence(occ)

    def finish_occurrence(self, occ):
        office = occ['office']
        zone = self.zone_of_office(office)
        refs = sorted(set(occ['refs']))
        occ['refs_sorted'] = refs
        occ['resolutions'] = []
        resolved = []
        day = wall_to_date(occ['instant'])
        for ref in refs:
            result, hops, outcome = self.resolve_handle(ref, day)
            occ['resolutions'].append((ref, result, hops, outcome))
            if result:
                resolved.append(result)
        occ['attendees'] = sorted(set(resolved))
        if zone is not None:
            wall_start = zone.wall_at(occ['start'])
            wall_end = zone.wall_at(occ['end'])
            offset = zone.offset_at(occ['start'])
        else:
            wall_start = occ['start']
            wall_end = occ['end']
            offset = 0
        occ['local_start'] = fmt_wall(wall_start)
        occ['local_end'] = fmt_wall(wall_end)
        occ['utc_offset_minutes'] = offset // 60
        start_date = wall_to_date(wall_start)
        row = self.office_row(office, start_date)
        solar = self.solar.get(office, 0)
        minute = (occ['start'] // 60 + solar) % 1440
        occ['solar_minutes'] = minute
        if row is None:
            occ['solar_in_window'] = False
        else:
            occ['solar_in_window'] = (row['solar_open'] <= minute <
                                      row['solar_close'])

    # -- conflicts and settling

    def is_pinned(self, occ):
        master = self.merged.get((occ['collection'], occ['uid'], ''))
        if master is not None:
            val = prop_text(master, 'X-PINNED')
            if val is not None and val.strip().upper() == 'TRUE':
                return True
        rank = self.rank_of(occ)
        return rank >= self.pin_rank

    def rank_of(self, occ):
        rank = self.class_ranks.get(occ['series_class'])
        if rank is None:
            return self.default_rank
        return rank

    def conflict_scan(self, schedule):
        """All conflicting pairs of a schedule, with their shared attendees."""
        order = sorted(schedule, key=lambda o: (o['start'], o['occurrence_id']))
        pos = {id(o): i for i, o in enumerate(order)}
        by_attendee = {}
        for i, occ in enumerate(order):
            for att in occ['attendees']:
                by_attendee.setdefault(att, []).append(i)
        pairs = {}
        for att in sorted(by_attendee):
            lst = by_attendee[att]
            for a in range(len(lst)):
                i = lst[a]
                occ = order[i]
                bound = occ['end'] + self.buffer_minutes * 60
                for b in range(a + 1, len(lst)):
                    j = lst[b]
                    other = order[j]
                    if other['start'] >= bound:
                        break
                    if occ['office'] != other['office']:
                        eff_end = occ['end'] + self.buffer_minutes * 60
                    else:
                        eff_end = occ['end']
                    if eff_end <= other['start']:
                        continue
                    key = (i, j)
                    entry = pairs.get(key)
                    if entry is None:
                        overlap = eff_end - other['start']
                        entry = {
                            'first': occ['occurrence_id'],
                            'second': other['occurrence_id'],
                            'first_obj': occ,
                            'second_obj': other,
                            'offices': [occ['office'], other['office']],
                            'buffer_applied':
                                self.buffer_minutes *
                                (1 if occ['office'] != other['office'] else 0),
                            'overlap_minutes': overlap // 60,
                            'shared': set(),
                            'sort': (occ['start'], occ['occurrence_id'],
                                     other['occurrence_id']),
                        }
                        pairs[key] = entry
                    entry['shared'].add(att)
        out = []
        for entry in pairs.values():
            entry['shared_attendees'] = sorted(entry['shared'])
            del entry['shared']
            out.append(entry)
        out.sort(key=lambda e: (e['first'], e['second']))
        return out

    def next_move(self, schedule):
        """The first pair with a movable member, or None."""
        order = sorted(schedule, key=lambda o: (o['start'], o['occurrence_id']))
        by_attendee = {}
        for i, occ in enumerate(order):
            for att in occ['attendees']:
                by_attendee.setdefault(att, []).append(i)
        pinned = [self.is_pinned(o) for o in order]
        for i, occ in enumerate(order):
            bound = occ['end'] + self.buffer_minutes * 60
            seen = {}
            for att in occ['attendees']:
                lst = by_attendee[att]
                lo, hi = 0, len(lst)
                while lo < hi:
                    mid = (lo + hi) // 2
                    if lst[mid] < i:
                        lo = mid + 1
                    else:
                        hi = mid
                for j in lst[lo:]:
                    if j == i:
                        continue
                    if order[j]['start'] >= bound:
                        break
                    if j < i:
                        continue
                    if occ['office'] != order[j]['office']:
                        eff_end = occ['end'] + self.buffer_minutes * 60
                    else:
                        eff_end = occ['end']
                    if eff_end <= order[j]['start']:
                        continue
                    if pinned[i] and pinned[j]:
                        continue
                    seen[j] = True
            if seen:
                best = min(seen, key=lambda j: order[j]['occurrence_id'])
                return (occ, order[best])
        return None

    def settle(self):
        self.moves = []
        rounds = 0
        stop = None
        residual = []
        while True:
            pick = self.next_move(self.occurrences)
            if pick is None:
                conflicts = self.conflict_scan(self.occurrences)
                if conflicts:
                    stop = 'pinned'
                    residual = conflicts
                else:
                    stop = 'clear'
                break
            if rounds >= self.round_cap:
                stop = 'cap'
                residual = self.conflict_scan(self.occurrences)
                break
            rounds += 1
            first, second = pick
            if self.is_pinned(first) != self.is_pinned(second):
                mover = second if self.is_pinned(first) else first
            else:
                r1 = self.rank_of(first)
                r2 = self.rank_of(second)
                if r1 != r2:
                    mover = first if r1 < r2 else second
                else:
                    mover = second if first['occurrence_id'] > \
                        second['occurrence_id'] else first
            self.defer(mover, rounds, first, second)
        self.settle_rounds = rounds
        self.stop_reason = stop
        self.residual = residual
        for occ in self.occurrences:
            occ['end'] = occ['start'] + occ['duration']

    def defer(self, occ, round_no, first, second):
        zone = self.zone_of_office(occ['office'])
        from_start = occ['start']
        if zone is None:
            wall = from_start
            target_wall = wall + self.quantum_minutes * 60
            newinst = target_wall
            shift = 0
        else:
            wall = zone.wall_at(from_start)
            target_wall = wall + self.quantum_minutes * 60
            newinst, _cls, shift = zone.resolve(target_wall)
            new_date = wall_to_date(target_wall)
            row = self.office_row(occ['office'], new_date)
            if row is not None:
                endwall = zone.wall_at(newinst + occ['duration'])
                days = (wall_to_date(endwall) - new_date).days
                end_minute = days * 1440 + (endwall % 86400) // 60
                if end_minute > row['close']:
                    target_wall = None
                    day = new_date
                    for _ in range(400):
                        day = day + timedelta(1)
                        nrow = self.office_row(occ['office'], day)
                        if nrow is None or nrow['working'] != 'Y':
                            continue
                        if self.closure_state(occ['office'], day):
                            continue
                        target_wall = date_to_wall(day) + nrow['open'] * 60
                        break
                    if target_wall is None:
                        target_wall = date_to_wall(day) + 0
                    newinst, _cls2, shift = zone.resolve(target_wall)
        occ['start'] = newinst
        occ['end'] = newinst + occ['duration']
        self.moves.append({
            'round': round_no,
            'occurrence_id': occ['occurrence_id'],
            'from_utc': fmt_instant(from_start),
            'to_utc': fmt_instant(newinst),
            'deferred_minutes': (target_wall - wall) // 60,
            'gap_shift_minutes': shift,
            'reason_first': first['occurrence_id'],
            'reason_second': second['occurrence_id'],
        })

    # -- legs

    def prepare_legs(self):
        self.legs_by_att = {}
        prepared = []
        for leg in self.legs:
            dzone = self.zone_of_office(leg['depart']['office'])
            azone = self.zone_of_office(leg['arrive']['office'])
            if dzone is None or azone is None:
                continue
            _isz, dwall = parse_dt_value(leg['depart']['local'])
            _isz2, awall = parse_dt_value(leg['arrive']['local'])
            dinstant, dcls, dshift = dzone.resolve(dwall)
            ainstant, acls, ashift = azone.resolve(awall)
            rec = {
                'id': leg['id'],
                'attendee': leg['attendee'],
                'depart_office': leg['depart']['office'],
                'arrive_office': leg['arrive']['office'],
                'depart_utc': dinstant,
                'arrive_utc': ainstant,
                'depart_classification': dcls,
                'arrive_classification': acls,
                'depart_shift': dshift,
                'arrive_shift': ashift,
                'depart_local_date': wall_to_date(dwall),
                'arrive_local_date': wall_to_date(awall),
                'blocked_from': dinstant - 120 * 60,
                'blocked_to': ainstant + 90 * 60,
            }
            rec['duration_minutes'] = (ainstant - dinstant) // 60
            rec['local_date_shift_days'] = (
                rec['arrive_local_date'] - rec['depart_local_date']).days
            rec['utc_date_shift_days'] = (
                wall_to_date(ainstant) - wall_to_date(dinstant)).days
            rec['date_line_crossing'] = (rec['local_date_shift_days'] !=
                                         rec['utc_date_shift_days'])
            prepared.append(rec)
        prepared.sort(key=lambda r: (r['depart_utc'], r['id']))
        self.legs_prepared = prepared
        for rec in prepared:
            self.legs_by_att.setdefault(rec['attendee'], []).append(rec)

    def effective_office(self, att, instant):
        home = ''
        info = self.attendees.get(att)
        if info:
            home = info.get('home_office') or ''
        best = None
        for leg in self.legs_by_att.get(att, []):
            if leg['arrive_utc'] <= instant:
                if best is None or (leg['arrive_utc'], leg['id']) > \
                        (best['arrive_utc'], best['id']):
                    best = leg
        if best is None:
            return home
        return best['arrive_office']

    # -- load fold

    def load_fold(self):
        self.load_steps = []
        floor = -30
        decay_unit = 3
        unit_minutes = 15
        cap = 8
        self.load_floor = floor
        self.load_decay = decay_unit
        self.load_unit = unit_minutes
        self.load_cap = cap
        atts = {}
        for occ in self.occurrences:
            for att in occ['attendees']:
                atts.setdefault(att, []).append(occ)
        self.load_attendees = {}
        self.load_over = []
        for att in sorted(atts):
            lst = sorted(atts[att],
                         key=lambda o: (o['pre_start'], o['occurrence_id']))
            debt = 0
            peak = None
            prev_office = None
            prev_end_date = None
            for step, occ in enumerate(lst, 1):
                office = self.effective_office(att, occ['pre_start'])
                zone = self.zone_of_office(office)
                wall_start = zone.wall_at(occ['pre_start']) if zone else \
                    occ['pre_start']
                local_date = wall_to_date(wall_start)
                row = self.office_row(office, local_date)
                minute = (occ['pre_start'] // 60 + self.solar.get(office, 0)) \
                    % 1440
                if row is not None:
                    deviation = max(row['solar_open'] - minute,
                                   minute - row['solar_close'])
                else:
                    deviation = 0
                cost = deviation // unit_minutes
                wall_end = zone.wall_at(occ['pre_end']) if zone else \
                    occ['pre_end']
                end_date = wall_to_date(wall_end)
                if prev_end_date is None:
                    rest = 0
                else:
                    rest = (local_date - prev_end_date).days - 1
                decay = decay_unit * (rest - 1) if rest > 1 else 0
                debt = max(floor, debt - decay + cost)
                changed = prev_office is not None and office != prev_office
                if changed:
                    debt = 0
                if peak is None or debt > peak:
                    peak = debt
                self.load_steps.append([
                    att, step, occ['occurrence_id'], office, deviation, cost,
                    rest, decay, changed, debt])
                prev_office = office
                prev_end_date = end_date
            final = debt
            peak_debt = max(0, peak if peak is not None else 0)
            self.load_attendees[att] = {'peak_debt': peak_debt,
                                        'final_debt': final}
            if peak_debt > cap:
                self.load_over.append({'attendee': att,
                                       'peak_debt': peak_debt,
                                       'excess': peak_debt - cap})
        self.load_over.sort(key=lambda r: r['attendee'])

    # -- attendance

    def attendance(self):
        self.violations = []
        for occ in self.occurrences:
            for att in occ['attendees']:
                office = self.effective_office(att, occ['start'])
                zone = self.zone_of_office(office)
                wall_start = zone.wall_at(occ['start']) if zone else occ['start']
                wall_end = zone.wall_at(occ['end']) if zone else occ['end']
                local_date = wall_to_date(wall_start)
                row = self.office_row(office, local_date)
                closure = self.closure_state(office, local_date)
                non_working = row is not None and row['working'] == 'N'
                kinds = []
                if closure:
                    kinds.append(('office-holiday', 0))
                if non_working:
                    kinds.append(('non-working-day', 0))
                if not closure and not non_working and row is not None:
                    start_minute = (wall_start % 86400) // 60
                    days = (wall_to_date(wall_end) - local_date).days
                    end_minute = days * 1440 + (wall_end % 86400) // 60
                    outside = max(row['open'] - start_minute,
                                  end_minute - row['close'])
                    if outside > 0:
                        kinds.append(('outside-working-window', outside))
                for kind, minutes in kinds:
                    self.violations.append([
                        att, occ['occurrence_id'], office, kind,
                        fmt_wall(wall_start), minutes])
        self.violations.sort(key=lambda r: (r[0], r[1], r[3]))

    # -- travel blocks, busy conflicts

    def travel_blocks(self):
        self.blocks = []
        self.busy_conflicts = []
        for occ in self.occurrences:
            start = occ['start']
            end = occ['end']
            for att in occ['attendees']:
                for leg in self.legs_by_att.get(att, []):
                    if start < leg['blocked_to'] and leg['blocked_from'] < end:
                        if start < leg['arrive_utc'] and \
                                leg['depart_utc'] < end:
                            kind = 'airborne'
                        else:
                            kind = 'ground-buffer'
                        self.blocks.append([occ['occurrence_id'], att,
                                            leg['id'], kind])
                for period in self.busy_by_att.get(att, []):
                    if start < period['end'] and period['start'] < end:
                        self.busy_conflicts.append([
                            occ['occurrence_id'], att,
                            fmt_instant(period['start']),
                            fmt_instant(period['end']), period['fbtype']])
        self.blocks.sort(key=lambda r: (r[0], r[2]))
        self.busy_conflicts.sort(key=lambda r: (r[0], r[2], r[1]))

    def prepare_busy(self):
        by_att = {}
        for period in self.periods:
            by_att.setdefault(period['attendee'], []).append(period)
        self.busy_by_att = {}
        for att, periods in by_att.items():
            periods.sort(key=lambda p: (p['start'], p['end'], p['fbtype']))
            merged = []
            for period in periods:
                if merged and period['start'] <= merged[-1]['end']:
                    last = merged[-1]
                    if period['end'] > last['end']:
                        last['end'] = period['end']
                    last['types'].append(period['fbtype'])
                else:
                    merged.append({'start': period['start'],
                                   'end': period['end'],
                                   'types': [period['fbtype']]})
            for entry in merged:
                entry['fbtype'] = _fbtype_precedence(entry['types'])
            self.busy_by_att[att] = merged

    # -- chargeback

    def chargeback(self):
        lines = []
        office_data = {}
        for occ in self.occurrences:
            office = occ['office']
            bps = self.conversion.get(office)
            if bps is None:
                bps = 10000
            day = wall_to_date(occ['start'])
            for att in occ['attendees']:
                rate = self.rate_for(att, day)
                base = round_half_even(rate * occ['duration'], 3600)
                converted = round_half_up(base * bps, 10000)
                lines.append({'office': office, 'collection': occ['collection'],
                              'base': base, 'converted': converted})
                entry = office_data.setdefault(office, {
                    'lines': 0, 'base': 0, 'converted': 0, 'bps': bps,
                    'collections': {}})
                entry['lines'] += 1
                entry['base'] += base
                entry['converted'] += converted
                coll = entry['collections'].setdefault(
                    occ['collection'], {'base': 0, 'lines': 0})
                coll['base'] += base
                coll['lines'] += 1
        self.charge_lines = lines
        self.charge_offices = office_data
        allocations = {}
        totals = {}
        for office in sorted(office_data):
            entry = office_data[office]
            conv = entry['converted']
            base_total = entry['base']
            colls = sorted(entry['collections'])
            alloc = {}
            if base_total == 0:
                for c in colls:
                    alloc[c] = 0
            else:
                remain = conv
                shares = []
                for c in colls:
                    cbase = entry['collections'][c]['base']
                    whole = (conv * cbase) // base_total
                    alloc[c] = whole
                    remain -= whole
                    shares.append((c, conv * cbase - whole * base_total))
                shares.sort(key=lambda t: (-t[1], t[0]))
                idx = 0
                while remain > 0 and shares:
                    c = shares[idx][0]
                    alloc[c] += 1
                    remain -= 1
                    idx = (idx + 1) % len(shares)
            for c in colls:
                allocations.setdefault(c, {})[office] = alloc[c]
                totals[c] = totals.get(c, 0) + alloc[c]
        self.charge_allocations = allocations
        self.charge_totals = totals


    # -- synchronisation

    def comp_projection(self, comp):
        office = prop_text(comp, 'X-OFFICE') or ''
        refs = sorted(set(comp_attendees(comp)))
        start, _cls, _z = self.instant_of(comp, 'DTSTART')
        if start is None:
            start = 0
        spec, source = self.span_of(comp)
        if isinstance(spec, str):
            seconds = self.duration_span(spec, start, office)
        elif spec is None:
            seconds = 3600
        else:
            seconds = spec
        return {
            'attendees': refs,
            'duration_seconds': seconds,
            'office': office,
            'recurrence_id': comp_rid_raw(comp),
            'sequence': comp_sequence(comp),
            'start_utc': fmt_instant(start),
            'summary': prop_text(comp, 'SUMMARY') or '',
            'uid': prop_text(comp, 'UID') or '',
        }

    def projection(self, comps):
        return [self.comp_projection(c) for c in
                sorted(comps, key=lambda c: (comp_rid_raw(c),
                                             comp_sequence(c)))]

    def sync_report(self):
        status = yaml_load(read_text(self.path['status']))
        book = status.get('collections') or {}
        self.sync_rows = []
        self.sync_tokens = []
        changed_count = 0
        resource_count = 0
        for coll in self.collections:
            cid = coll.get('id')
            local_comps = self.replicas.get((cid, 'local'), [])
            server_comps = list((self.server_index.get(cid) or {}).values())
            by_uid_local = {}
            for comp in local_comps:
                by_uid_local.setdefault(comp_uid(comp), []).append(comp)
            by_uid_server = {}
            for comp in server_comps:
                by_uid_server.setdefault(comp_uid(comp), []).append(comp)
            uids = sorted(set(list(by_uid_local) + list(by_uid_server)))
            merged_by_uid = {}
            for key, comp in self.merged.items():
                if key[0] == cid:
                    merged_by_uid.setdefault(key[1], []).append(comp)
            coll_status = book.get(cid) or {}
            revmaps = {}
            for rep in ('local', 'server'):
                revmap = {}
                section = (coll_status.get(rep) or {})
                for entry in (section.get('entries') or []):
                    if isinstance(entry, dict) and entry.get('href'):
                        try:
                            revmap[entry['href']] = int(str(
                                entry.get('revision')).strip())
                        except (ValueError, TypeError):
                            revmap[entry['href']] = 0
                revmaps[rep] = revmap
            token_data = []
            coll_rows = []
            for uid in uids:
                href = self.collection_href(cid, uid)
                merged = self.projection(merged_by_uid.get(uid, []))
                local = self.projection(by_uid_local.get(uid, []))
                server = self.projection(by_uid_server.get(uid, []))
                digest = sha256_hex(jdump(merged).encode('utf-8'))
                etag = '"%s"' % digest
                changed_local = merged != local
                changed_server = merged != server
                rlocal = revmaps['local'].get(href, 0)
                rserver = revmaps['server'].get(href, 0)
                revision = max(rlocal, rserver)
                if changed_local or changed_server:
                    revision += 1
                coll_rows.append([
                    cid, href, etag, revision, changed_local, changed_server])
                token_data.append('%s\t%s\n' % (href, etag))
                resource_count += 1
                if changed_local or changed_server:
                    changed_count += 1
            coll_rows.sort(key=lambda r: r[1])
            self.sync_rows.extend(coll_rows)
            token = '%s-%s' % (cid, sha256_hex(''.join(token_data)
                                               .encode('utf-8')))
            self.sync_tokens.append({
                'collection': cid,
                'href': coll.get('href') or '',
                'sync_token': token,
                'resources': len(uids),
            })
        self.sync_counts = {
            'collections': len(self.collections),
            'resources': resource_count,
            'changed_resources': changed_count,
        }

    # -- authority audit

    def authority_audit(self):
        rows = []
        draft = yaml_load(read_text(self.path['escalation_draft']))
        dsettle = draft.get('settling') or {}
        params = {
            'buffer_minutes': self.buffer_minutes,
            'quantum_minutes': self.quantum_minutes,
            'round_cap': self.round_cap,
            'pin_rank': self.pin_rank,
            'default_rank': self.default_rank,
        }
        for key in sorted(params):
            in_force = str(params[key])
            raw = dsettle.get(key)
            lower = '' if raw is None else str(raw)
            rows.append(['settling-parameter', key, in_force,
                         'escalation_draft', lower,
                         in_force == lower])
        dclasses = draft.get('class_ranks') or {}
        table_classes = set()
        for name in ('Series class ranks',):
            for row in self._rows(self._audit_tables, name):
                cls = (row.get('class') or '').strip()
                if cls:
                    table_classes.add(cls)
        for cls in sorted(table_classes | set(dclasses)):
            rank = self.class_ranks.get(cls)
            if rank is None:
                rank = self.default_rank
            raw = dclasses.get(cls)
            lower = '' if raw is None else str(raw)
            rows.append(['class-rank', cls, str(rank), 'escalation_draft',
                         lower, str(rank) == lower])
        conv = draft.get('conversion_bps') or {}
        table_offices = set()
        for row in self._rows(self._audit_tables, 'Office conversion'):
            office = (row.get('office') or '').strip()
            if office:
                table_offices.add(office)
        for office in sorted(table_offices | set(conv)):
            bps = self.conversion.get(office)
            in_force = '' if bps is None else str(bps)
            raw = conv.get(office)
            lower = '' if raw is None else str(raw)
            rows.append(['conversion-bps', office, in_force,
                         'escalation_draft', lower, in_force == lower])
        snapshot = keyed_rows(read_text(self.path['office_snapshot']), ',')
        snap_by_key = {}
        for rec in snapshot:
            snap_by_key.setdefault((rec.get('code', ''),
                                    rec.get('weekday', '')), rec)
        for office in sorted(self.offices):
            in_force = self.offices[office]['longitude']
            rec = snap_by_key.get((office, 'MO'))
            lower = rec.get('longitude', '') if rec else ''
            rows.append(['office-longitude', office, in_force,
                         'office_snapshot', lower, in_force == lower])
        for office in sorted(self.offices):
            for wd in WEEKDAYS:
                day = self.win_start_date
                while day.weekday() != WD_INDEX[wd]:
                    day = day + timedelta(1)
                row = self.office_row(office, day)
                if row is None:
                    in_force = ''
                else:
                    in_force = '%d-%d' % (row['open'], row['close'])
                rec = snap_by_key.get((office, wd))
                lower = '%s-%s' % (rec.get('open_minute', ''),
                                   rec.get('close_minute', '')) if rec \
                    else ''
                rows.append(['office-window', '%s:%s' % (office, wd),
                             in_force, 'office_snapshot', lower,
                             in_force == lower])
        payroll = keyed_rows(read_text(self.path['payroll_export']), ';')
        pay = {}
        for rec in payroll:
            att = rec.get('attendee', '')
            if att and att not in pay:
                pay[att] = rec.get('cents_per_hour', '')
        rate_keys = set(self.attendees) | set(pay)
        for att in sorted(rate_keys):
            in_force = str(self.rate_for(att, self.win_start_date))
            raw = pay.get(att)
            lower = '' if raw is None else str(raw)
            rows.append(['attendee-rate', att, in_force, 'payroll_export',
                         lower, in_force == lower])
        cache = keyed_rows(read_text(self.path['zone_cache']), '\t')
        cache_by_zone = {}
        for rec in cache:
            zone = rec.get('tzid', '')
            onset = rec.get('onset_utc', '')
            try:
                inst = parse_dt_value(to_basic(onset))[1]
            except ValueError:
                continue
            if not (self.win_start <= inst < self.win_end):
                continue
            cache_by_zone.setdefault(zone, []).append(
                '%s/%s/%s' % (onset, rec.get('from_minutes', ''),
                              rec.get('to_minutes', '')))
        for tzid in sorted(self.zones):
            zone = self.zones[tzid]
            parts = []
            for onset, offrom, offto in zone.transitions:
                if self.win_start <= onset < self.win_end:
                    parts.append('%s/%d/%d' % (fmt_instant(onset),
                                              offrom // 60, offto // 60))
            in_force = ';'.join(parts)
            lower_rows = cache_by_zone.get(tzid, [])
            lower = ';'.join(sorted(lower_rows))
            rows.append(['zone-transitions', tzid, in_force, 'zone_cache',
                         lower, in_force == lower])
        self.audit_rows = rows

    # -- drift

    def drift_report(self):
        doc = json.loads(read_bytes(self.path['previous_run']).decode('utf-8'))
        listed = {}
        for rec in doc.get('series_summary') or []:
            listed[(rec.get('collection'), rec.get('uid'))] = \
                int(rec.get('occurrence_count'))
        counts = {}
        for occ in self.occurrences:
            key = (occ['collection'], occ['uid'])
            counts[key] = counts.get(key, 0) + 1
        keys = set(listed) | set(
            (coll, uid) for (coll, uid) in self.holders
            if self.primary.get((coll, uid), coll) == coll)
        rows = []
        for coll, uid in sorted(keys):
            v3 = listed.get((coll, uid))
            v5 = counts.get((coll, uid), 0)
            if v3 is None:
                rows.append([coll, uid, '', str(v5), ''])
            else:
                rows.append([coll, uid, str(v3), str(v5), str(v5 - v3)])
        self.drift_rows = rows

    # -- report assembly

    def build_reports(self):
        reports = {}

        def put(name, data):
            reports[name] = data

        put('decisions.jsonl', json_lines(self.decisions))
        put('reconciliation.json', json_document({
            'policy': self.policy,
            'effective_revision': self.effective_revision,
            'counts': self.counts,
            'duplicate_uids': self.duplicate_uids,
        }))
        put('outbox_replay.jsonl', json_lines(self.outbox_report))
        occ_rows = []
        for occ in sorted(self.occurrences,
                          key=lambda o: (o['pre_start'], o['occurrence_id'])):
            occ_rows.append([
                occ['occurrence_id'], occ['collection'], occ['uid'],
                occ['office'], fmt_instant(occ['instant']),
                fmt_instant(occ['pre_start']), fmt_instant(occ['pre_end']),
                occ['duration'], occ['duration_source'],
                occ['shift'] // 60, occ['override'], occ['local_start'],
                occ['local_end'], occ['utc_offset_minutes'],
                occ['solar_minutes'], occ['solar_in_window'],
                occ['series_class'], occ['attendees'], occ['summary'],
            ])
        put('occurrences.csv', table_document(',', [
            'occurrence_id', 'collection', 'uid', 'office', 'original_utc',
            'start_utc', 'end_utc', 'duration_seconds', 'duration_source',
            'applied_shift_minutes', 'override', 'local_start', 'local_end',
            'utc_offset_minutes', 'solar_minutes', 'solar_in_window',
            'series_class', 'required_attendees', 'summary'], occ_rows))
        alias_rows = []
        for occ in sorted(self.occurrences,
                          key=lambda o: o['occurrence_id']):
            for ref, result, hops, outcome in occ['resolutions']:
                alias_rows.append([occ['occurrence_id'], ref, result, hops,
                                   outcome])
        put('alias_resolutions.tsv', table_document('\t', [
            'occurrence_id', 'ref', 'resolved', 'hops', 'outcome'],
            alias_rows))
        res_rows = []
        res_sorted = sorted(self.resolutions,
                            key=lambda r: ('%s:%s:%s' % (
                                r['collection'], r['uid'],
                                fmt_instant(r['entry']['instant'])),
                                r['entry']['nominal']))
        for rec in res_sorted:
            entry = rec['entry']
            zone = self.zones.get(entry['tzid'])
            offset = zone.offset_at(entry['instant']) if zone else 0
            res_rows.append([
                '%s:%s:%s' % (rec['collection'], rec['uid'],
                              fmt_instant(entry['instant'])),
                entry['tzid'], entry['nominal'], entry['classification'],
                entry['shift'], offset // 60])
        put('resolutions.tsv', table_document('\t', [
            'occurrence_id', 'tzid', 'nominal_local', 'classification',
            'shift_minutes', 'utc_offset_minutes'], res_rows))
        put('exceptions.jsonl', json_lines(self.exception_records()))
        put('zone_transitions.tsv', table_document('\t', [
            'tzid', 'observance_count', 'onset_utc', 'from_offset_minutes',
            'to_offset_minutes'], self.zone_transition_rows()))
        conf_rows = []
        for entry in self.conflicts_before:
            conf_rows.append({
                'first': entry['first'],
                'second': entry['second'],
                'shared_attendees': entry['shared_attendees'],
                'offices': entry['offices'],
                'buffer_applied': entry['buffer_applied'],
                'overlap_minutes': entry['overlap_minutes'],
            })
        put('conflicts.jsonl', json_lines(conf_rows))
        put('settle_moves.csv', table_document(',', [
            'round', 'occurrence_id', 'from_utc', 'to_utc',
            'deferred_minutes', 'gap_shift_minutes', 'reason_first',
            'reason_second'], [[mv['round'], mv['occurrence_id'],
                                 mv['from_utc'], mv['to_utc'],
                                 mv['deferred_minutes'],
                                 mv['gap_shift_minutes'], mv['reason_first'],
                                 mv['reason_second']] for mv in self.moves]))
        settled_rows = []
        for occ in sorted(self.occurrences,
                          key=lambda o: o['occurrence_id']):
            settled_rows.append([occ['occurrence_id'], occ['office'],
                                 fmt_instant(occ['start']),
                                 fmt_instant(occ['end'])])
        put('settled_schedule.csv', table_document(',', [
            'occurrence_id', 'office', 'start_utc', 'end_utc'], settled_rows))
        residual = []
        for entry in self.residual:
            residual.append({
                'first': entry['first'],
                'second': entry['second'],
                'shared_attendees': entry['shared_attendees'],
                'offices': entry['offices'],
                'buffer_applied': entry['buffer_applied'],
                'overlap_minutes': entry['overlap_minutes'],
            })
        put('settle_summary.json', json_document({
            'rounds': self.settle_rounds,
            'converged': self.stop_reason == 'clear',
            'stop_reason': self.stop_reason,
            'buffer_minutes': self.buffer_minutes,
            'quantum_minutes': self.quantum_minutes,
            'round_cap': self.round_cap,
            'pin_rank': self.pin_rank,
            'default_rank': self.default_rank,
            'effective_revision': self.effective_revision,
            'residual_conflicts': residual,
        }))
        put('load_steps.tsv', table_document('\t', [
            'attendee', 'step', 'occurrence_id', 'effective_office',
            'deviation_minutes', 'cost_units', 'rest_days', 'decay_applied',
            'office_changed', 'debt_after'], self.load_steps))
        put('load_summary.json', json_document({
            'floor': self.load_floor,
            'decay_per_rest_day': self.load_decay,
            'unit_minutes': self.load_unit,
            'cap': self.load_cap,
            'attendees': self.load_attendees,
            'over_cap': self.load_over,
        }))
        put('attendance.psv', table_document('|', [
            'attendee', 'occurrence_id', 'effective_office', 'kind',
            'local_start', 'minutes_outside'], self.violations))
        legs_json = {
            'legs': [{
                'leg_id': leg['id'],
                'attendee': leg['attendee'],
                'depart_office': leg['depart_office'],
                'arrive_office': leg['arrive_office'],
                'depart_utc': fmt_instant(leg['depart_utc']),
                'arrive_utc': fmt_instant(leg['arrive_utc']),
                'depart_classification': leg['depart_classification'],
                'arrive_classification': leg['arrive_classification'],
                'depart_shift_minutes': leg['depart_shift'],
                'arrive_shift_minutes': leg['arrive_shift'],
                'duration_minutes': leg['duration_minutes'],
                'local_date_shift_days': leg['local_date_shift_days'],
                'utc_date_shift_days': leg['utc_date_shift_days'],
                'date_line_crossing': leg['date_line_crossing'],
                'blocked_from_utc': fmt_instant(leg['blocked_from']),
                'blocked_to_utc': fmt_instant(leg['blocked_to']),
            } for leg in self.legs_prepared],
            'counts': {
                'legs': len(self.legs_prepared),
                'date_line_crossings': sum(
                    1 for leg in self.legs_prepared if leg['date_line_crossing']),
                'blocked_occurrences': len(self.blocks),
                'freebusy_conflicts': len(self.busy_conflicts),
            },
        }
        put('legs.json', json_document(legs_json))
        put('travel_blocks.csv', table_document(',', [
            'occurrence_id', 'attendee', 'leg_id', 'kind'], self.blocks))
        put('busy_conflicts.tsv', table_document('\t', [
            'occurrence_id', 'attendee', 'block_start_utc', 'block_end_utc',
            'fbtype'], self.busy_conflicts))
        put('sync_entries.tsv', table_document('\t', [
            'collection', 'href', 'etag', 'revision', 'changed_local',
            'changed_server'], self.sync_rows))
        put('sync_tokens.json', json_document({
            'collections': self.sync_tokens,
            'counts': self.sync_counts,
        }))
        offices = {}
        for office in sorted(self.charge_offices):
            entry = self.charge_offices[office]
            offices[office] = {
                'lines': entry['lines'],
                'base_cents': entry['base'],
                'converted_cents': entry['converted'],
                'fx_bps': entry['bps'],
            }
        put('chargeback_offices.json', json_document({
            'offices': offices,
            'totals': {
                'lines': sum(v['lines'] for v in offices.values()),
                'base_cents': sum(v['base_cents'] for v in offices.values()),
                'converted_cents': sum(v['converted_cents']
                                       for v in offices.values()),
            },
        }))
        put('chargeback_collections.json', json_document({
            'allocations': self.charge_allocations,
            'totals': self.charge_totals,
        }))
        put('authority_audit.csv', table_document(',', [
            'subject', 'key', 'in_force', 'source', 'lower_value',
            'agrees'], self.audit_rows))
        put('drift.csv', table_document(',', [
            'collection', 'uid', 'v3_count', 'v5_count', 'delta'],
            self.drift_rows))
        order = ['decisions.jsonl', 'reconciliation.json',
                 'outbox_replay.jsonl', 'occurrences.csv',
                 'alias_resolutions.tsv', 'resolutions.tsv',
                 'exceptions.jsonl', 'zone_transitions.tsv', 'conflicts.jsonl',
                 'settle_moves.csv', 'settled_schedule.csv',
                 'settle_summary.json', 'load_steps.tsv', 'load_summary.json',
                 'attendance.psv', 'legs.json', 'travel_blocks.csv',
                 'busy_conflicts.tsv', 'sync_entries.tsv', 'sync_tokens.json',
                 'chargeback_offices.json', 'chargeback_collections.json',
                 'authority_audit.csv', 'drift.csv']
        links = []
        chain = sha256_hex(b'')
        for name in order:
            data = reports[name]
            digest = sha256_hex(data)
            chain = sha256_hex(('%s\n%s\n%s' % (chain, name, digest))
                                .encode('utf-8'))
            links.append({'name': name, 'file_sha256': digest,
                          'chain_sha256': chain})
        reports['manifest.json'] = json_document({
            'algorithm': 'sha256-chain',
            'order': order,
            'links': links,
            'chain_root': sha256_hex(b''),
            'chain_head': chain,
        })
        return reports

    def exception_records(self):
        out = []
        for rec in sorted(self.exceptions['exdate-applied'],
                          key=lambda r: (r['collection'], r['uid'],
                                         r['exdate_utc'])):
            out.append(rec)
        for rec in sorted(self.exceptions['exdate-unmatched'],
                          key=lambda r: (r['collection'], r['uid'],
                                         r['exdate_utc'])):
            out.append(rec)
        for rec in sorted(self.exceptions['override-applied'],
                          key=lambda r: (r['collection'], r['uid'],
                                         r['recurrence_id_utc'], r.get('range',
                                                                       ''))):
            out.append(rec)
        for rec in sorted(self.exceptions['override-rejected'],
                          key=lambda r: (r['collection'], r['uid'],
                                         r['recurrence_id_utc'], r['reason'])):
            out.append(rec)
        for rec in sorted(self.exceptions['shift'],
                          key=lambda r: r['occurrence_id']):
            out.append(rec)
        return out

    def zone_transition_rows(self):
        rows = []
        for tzid in sorted(self.zones):
            zone = self.zones[tzid]
            for onset, offrom, offto in zone.transitions:
                if onset >= self.win_end:
                    continue
                rows.append([tzid, zone.observances, fmt_instant(onset),
                             offrom // 60, offto // 60])
        return rows

    # -- run

    def run(self, out_dir):
        self.load()
        self._audit_tables = pdf_tables(self.path['governance'])
        self.decode_replicas()
        self.replay_outbox()
        self.load_journal()
        self.merge()
        self.build_occurrences()
        for occ in self.occurrences:
            occ['pre_start'] = occ['start']
            occ['pre_end'] = occ['end']
        self.conflicts_before = self.conflict_scan(self.occurrences)
        self.prepare_legs()
        self.prepare_busy()
        self.load_fold()
        self.settle()
        self.attendance()
        self.travel_blocks()
        self.chargeback()
        self.sync_report()
        self.authority_audit()
        self.drift_report()
        return self.build_reports()



def _fbtype_precedence(types):
    order = ['BUSY-UNAVAILABLE', 'BUSY', 'BUSY-TENTATIVE']
    for name in order:
        if name in types:
            return name
    others = sorted(t for t in types if t not in order)
    return others[0] if others else ''


def round_half_even(numerator, denominator):
    q, r = divmod(numerator, denominator)
    twice = 2 * r
    if twice > denominator:
        return q + 1
    if twice < denominator:
        return q
    return q if q % 2 == 0 else q + 1


def round_half_up(numerator, denominator):
    q, r = divmod(numerator, denominator)
    if 2 * r >= denominator:
        return q + 1
    return q

def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: schedule_repair.py DATA_DIR OUT_DIR\n')
        return 2
    data_dir = argv[1]
    out_dir = argv[2]
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    else:
        for name in sorted(os.listdir(out_dir)):
            path = os.path.join(out_dir, name)
            if os.path.isfile(path):
                os.unlink(path)
    p = Pass(data_dir)
    reports = p.run(out_dir)
    for name in sorted(reports):
        with open(os.path.join(out_dir, name), 'wb') as fh:
            fh.write(reports[name])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
