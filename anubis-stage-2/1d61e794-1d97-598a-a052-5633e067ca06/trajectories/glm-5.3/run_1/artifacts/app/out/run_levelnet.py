#!/usr/bin/env python3
"""VDO precise levelling recomputation (handbook rev 7).

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
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from fractions import Fraction

# --------------------------------------------------------------------------
# numeric helpers
# --------------------------------------------------------------------------


def _dec(x):
    """Convert str/int/float/Fraction/Decimal to Fraction exactly."""
    if x is None:
        return None
    if isinstance(x, Fraction):
        return x
    if isinstance(x, int):
        return Fraction(x)
    if isinstance(x, Decimal):
        return Fraction(x)
    if isinstance(x, float):
        return Fraction(Decimal(repr(x)))
    s = str(x).strip()
    if s == '':
        return None
    s = s.replace(',', '.') if ';' in str(x) else s
    return Fraction(Decimal(s))


def round_scaled(x, scale):
    """Round x (Fraction) half to even to a multiple of 1/scale; return int."""
    x = _dec(x)
    y = x * scale
    n, d = y.numerator, y.denominator
    q = n // d
    rem = n - q * d
    tw = 2 * rem
    if tw > d or (tw == d and (q % 2 == 1)):
        q += 1
    return q


def fmt(x, places):
    """Format with the given number of decimals, half to even, no -0."""
    scale = 10 ** places
    q = round_scaled(x, scale)
    neg = q < 0
    q = abs(q)
    s = str(q)
    if places:
        s = s.rjust(places + 1, '0')
        s = s[:-places] + '.' + s[-places:]
    if neg:
        s = '-' + s
    return s


def fmt0(x, places):
    """Same as fmt but strips a redundant '-0.00' to '0.00'."""
    s = fmt(x, places)
    if s.startswith('-') and float(s) == 0.0:
        s = s[1:]
    return s


def iso(d):
    return d.isoformat()


def parse_date(s):
    s = (s or '').strip()
    if not s:
        return None
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})', s)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.match(r'^(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})', s)
    if m:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    return None


# --------------------------------------------------------------------------
# YAML subset parser
# --------------------------------------------------------------------------


class _YLine:
    __slots__ = ('indent', 'text')

    def __init__(self, indent, text):
        self.indent = indent
        self.text = text


def _strip_comment(s):
    out = []
    i = 0
    n = len(s)
    quote = None
    while i < n:
        c = s[i]
        if quote:
            out.append(c)
            if c == '\\' and quote == '"' and i + 1 < n:
                out.append(s[i + 1])
                i += 2
                continue
            if c == quote:
                quote = None
            i += 1
            continue
        if c in '\'"':
            quote = c
            out.append(c)
            i += 1
            continue
        if c == '#' and (i == 0 or s[i - 1] in ' \t'):
            break
        out.append(c)
        i += 1
    return ''.join(out)


def _split_key(text):
    """Split 'key: value' respecting quotes and flow brackets."""
    i = 0
    n = len(text)
    quote = None
    depth = 0
    while i < n:
        c = text[i]
        if quote:
            if c == '\\':
                i += 2
                continue
            if c == quote:
                quote = None
            i += 1
            continue
        if c in '\'"':
            quote = c
        elif c in '[{':
            depth += 1
        elif c in ']}':
            depth -= 1
        elif c == ':' and depth == 0:
            if i + 1 >= n or text[i + 1] in ' \t':
                return text[:i].strip(), text[i + 1:].strip()
        i += 1
    return None, text.strip()


def _unquote(s):
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in '\'"':
        body = s[1:-1]
        if s[0] == '"':
            body = body.replace('\\"', '"').replace('\\\\', '\\').replace('\\n', '\n')
        return body
    return s


def _scalar(s):
    s = s.strip()
    if s == '':
        return None
    if s in ('~', 'null', 'Null', 'NULL'):
        return None
    if len(s) >= 2 and s[0] == s[-1] and s[0] in '\'"':
        return _unquote(s)
    low = s.lower()
    if low in ('true', 'yes', 'on', "'yes'", '"yes"'):
        return True
    if low in ('false', 'no', 'off', "'no'", '"no"'):
        return False
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def _flow(text):
    """Parse a flow collection or scalar."""
    text = text.strip()
    pos = [0]

    def skip_ws():
        while pos[0] < len(text) and text[pos[0]] in ' \t':
            pos[0] += 1

    def quoted():
        q = text[pos[0]]
        pos[0] += 1
        buf = []
        while pos[0] < len(text):
            c = text[pos[0]]
            if c == '\\' and q == '"':
                if pos[0] + 1 < len(text):
                    buf.append(text[pos[0] + 1])
                    pos[0] += 2
                    continue
            if c == q:
                if q == "'" and pos[0] + 1 < len(text) and text[pos[0] + 1] == "'":
                    buf.append(q)
                    pos[0] += 2
                    continue
                pos[0] += 1
                break
            buf.append(c)
            pos[0] += 1
        return ''.join(buf)

    def parse_one(keymode=False):
        skip_ws()
        if pos[0] >= len(text):
            return None
        c = text[pos[0]]
        if c == '[':
            pos[0] += 1
            out = []
            while True:
                skip_ws()
                if pos[0] < len(text) and text[pos[0]] == ']':
                    pos[0] += 1
                    break
                if pos[0] >= len(text):
                    break
                out.append(parse_one())
                skip_ws()
                if pos[0] < len(text) and text[pos[0]] == ',':
                    pos[0] += 1
                elif pos[0] < len(text) and text[pos[0]] == ']':
                    pos[0] += 1
                    break
                elif pos[0] >= len(text):
                    break
            return out
        if c == '{':
            pos[0] += 1
            out = {}
            while True:
                skip_ws()
                if pos[0] < len(text) and text[pos[0]] == '}':
                    pos[0] += 1
                    break
                if pos[0] >= len(text):
                    break
                k = parse_one(True)
                skip_ws()
                if pos[0] < len(text) and text[pos[0]] == ':':
                    pos[0] += 1
                    v = parse_one()
                else:
                    v = None
                if k is not None:
                    out[str(k)] = v
                skip_ws()
                if pos[0] < len(text) and text[pos[0]] == ',':
                    pos[0] += 1
                elif pos[0] < len(text) and text[pos[0]] == '}':
                    pos[0] += 1
                    break
                elif pos[0] >= len(text):
                    break
            return out
        if c in '\'"':
            return quoted()
        j = pos[0]
        stop = ',]}:' if keymode else ',]}'
        while j < len(text) and text[j] not in stop:
            j += 1
        val = _scalar(text[pos[0]:j])
        pos[0] = j
        return val

    return parse_one()


class _YParser:
    def __init__(self, text):
        self.lines = []
        for raw in text.splitlines():
            s = _strip_comment(raw.replace('\t', '    ')).rstrip()
            if not s.strip():
                continue
            if s.strip() in ('---', '...'):
                continue
            indent = len(s) - len(s.lstrip(' '))
            self.lines.append(_YLine(indent, s.strip()))
        self.i = 0

    def cur(self):
        return self.lines[self.i] if self.i < len(self.lines) else None

    def parse_doc(self):
        if not self.lines:
            return None
        return self.parse_block(self.lines[0].indent)

    def parse_block(self, indent):
        ln = self.cur()
        if ln is None:
            return None
        if ln.text == '-' or ln.text.startswith('- '):
            return self.parse_seq(indent)
        return self.parse_map(indent)

    def parse_seq(self, indent):
        out = []
        while True:
            ln = self.cur()
            if ln is None or ln.indent != indent:
                break
            if ln.text != '-' and not ln.text.startswith('- '):
                break
            m = re.match(r'-( *)', ln.text)
            off = 1 + len(m.group(1))
            rest = ln.text[off:]
            key, _ = _split_key(rest)
            if rest == '':
                self.i += 1
                nxt = self.cur()
                if nxt is not None and nxt.indent > indent:
                    out.append(self.parse_block(nxt.indent))
                else:
                    out.append(None)
            elif key is None:
                self.i += 1
                out.append(_flow(rest))
            else:
                self.lines[self.i] = _YLine(indent + off, rest)
                out.append(self.parse_block(indent + off))
        return out

    def parse_map(self, indent):
        out = {}
        while True:
            ln = self.cur()
            if ln is None or ln.indent != indent:
                break
            if ln.text == '-' or ln.text.startswith('- '):
                break
            key, rest = _split_key(ln.text)
            if key is None:
                self.i += 1
                continue
            key = _unquote(key)
            self.i += 1
            rest = rest.strip()
            if rest == '':
                nxt = self.cur()
                if nxt is not None and nxt.indent > indent:
                    out[key] = self.parse_block(nxt.indent)
                elif nxt is not None and nxt.indent == indent and (
                        nxt.text == '-' or nxt.text.startswith('- ')):
                    out[key] = self.parse_seq(indent)
                else:
                    out[key] = None
            else:
                out[key] = _flow(rest)
        return out


def yaml_load(text):
    if isinstance(text, bytes):
        text = text.decode('utf-8', 'replace')
    return _YParser(text).parse_doc()


# --------------------------------------------------------------------------
# XLSX reader
# --------------------------------------------------------------------------

_XNS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'


def _col_index(ref):
    m = re.match(r'([A-Z]+)', ref)
    n = 0
    for ch in m.group(1):
        n = n * 26 + ord(ch) - 64
    return n - 1


def xlsx_sheets(path):
    """Return {sheet_name: [ [cell, ...], ... ]}."""
    z = zipfile.ZipFile(path)
    wbx = z.read('xl/workbook.xml').decode('utf-8', 'replace')
    relsx = z.read('xl/_rels/workbook.xml.rels').decode('utf-8', 'replace')
    relmap = {}
    for tag in re.findall(r'<Relationship\b[^>]*>', relsx):
        rid = re.search(r'\bId="([^"]+)"', tag)
        tgt = re.search(r'\bTarget="([^"]+)"', tag)
        typ = re.search(r'\bType="([^"]+)"', tag)
        if rid and tgt and typ and typ.group(1).endswith('/worksheet'):
            relmap[rid.group(1)] = tgt.group(1)
    sheet_tags = re.findall(r'<sheet\b[^>]*?/>', wbx)
    if not sheet_tags:
        sheet_tags = re.findall(r'<sheet\b[^>]*?>', wbx)
    names = []
    for tag in sheet_tags:
        nm = re.search(r'name="([^"]*)"', tag)
        rid = re.search(r'r:id="([^"]+)"', tag)
        names.append((nm.group(1) if nm else '', rid.group(1) if rid else ''))
    shared = []
    if 'xl/sharedStrings.xml' in z.namelist():
        sst = z.read('xl/sharedStrings.xml').decode('utf-8', 'replace')
        for item in re.findall(r'<si>(.*?)</si>', sst, re.S):
            txt = ''.join(re.findall(r'<t[^>]*>(.*?)</t>', item, re.S))
            shared.append(_xml_unescape(txt))
    date1904 = 'date1904="1"' in wbx or "date1904='1'" in wbx
    out = {}
    for name, rid in names:
        target = relmap.get(rid, '')
        if not target:
            continue
        if target.startswith('/'):
            target = target[1:]
        elif not target.startswith('xl/'):
            target = 'xl/' + target
        if target not in z.namelist():
            continue
        out[name] = _xlsx_sheet(z, target, shared)
    out['__date1904__'] = date1904
    return out


def _xml_unescape(s):
    return (s.replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"')
            .replace('&apos;', "'").replace('&#13;', '\r').replace('&#10;', '\n')
            .replace('&amp;', '&'))


def _xlsx_sheet(z, target, shared):
    xml = z.read(target).decode('utf-8', 'replace')
    rows = []
    for rowxml in re.findall(r'<row\b[^>]*?/>|<row\b[^>]*?>(.*?)</row>', xml, re.S):
        cells = []
        for cm in re.finditer(r'<c\b([^>]*)>(.*?)</c>|<c\b([^>]*)/>', rowxml, re.S):
            attrs = cm.group(1) or cm.group(3) or ''
            body = cm.group(2) or ''
            ref = re.search(r'\br="([A-Z]+\d+)"', attrs)
            idx = _col_index(ref.group(1)) if ref else len(cells)
            t = re.search(r'\bt="([^"]+)"', attrs)
            t = t.group(1) if t else 'n'
            txt = None
            if t == 'inlineStr':
                is_ = re.search(r'<is>(.*?)</is>', body, re.S)
                if is_:
                    txt = ''.join(_xml_unescape(x) for x in re.findall(r'<t[^>]*>(.*?)</t>', is_.group(1), re.S))
            else:
                vm = re.search(r'<v>(.*?)</v>', body, re.S)
                if vm:
                    v = _xml_unescape(vm.group(1))
                    if t == 's':
                        try:
                            txt = shared[int(v)]
                        except Exception:
                            txt = v
                    elif t == 'b':
                        txt = 'TRUE' if v.strip() == '1' else 'FALSE'
                    else:
                        txt = v
                else:
                    tm = re.search(r'<t[^>]*>(.*?)</t>', body, re.S)
                    if tm:
                        txt = _xml_unescape(tm.group(1))
            while len(cells) <= idx:
                cells.append(None)
            cells[idx] = txt
        rows.append(cells)
    return rows


def xlsx_table(sheet_rows, header_first_cell):
    """Return list of dicts using the row whose first cell equals the header."""
    hdr = None
    hidx = None
    for i, r in enumerate(sheet_rows):
        if r and r[0] == header_first_cell:
            hdr = r
            hidx = i
            break
    if hdr is None:
        for i, r in enumerate(sheet_rows[:10]):
            if r and sum(1 for c in r if c not in (None, '')) >= 3:
                hdr = r
                hidx = i
                break
    if hdr is None:
        return []
    out = []
    for r in sheet_rows[hidx + 1:]:
        if not any(c for c in r if c is not None):
            continue
        if len(r) >= 1 and (r[0] or '').strip() == 'continued':
            continue
        d = {}
        for j, k in enumerate(hdr):
            if k is None:
                continue
            d[k] = r[j] if j < len(r) else None
        out.append(d)
    return out


# --------------------------------------------------------------------------
# PDF text extraction and memo tables
# --------------------------------------------------------------------------


def _pdf_objects(data):
    objs = {}
    for m in re.finditer(rb'(\d+)\s+(\d+)\s+obj\b', data):
        num = int(m.group(1))
        start = m.end()
        end = data.find(b'endobj', start)
        if end < 0:
            end = len(data)
        objs[num] = data[start:end]
    return objs


def _pdf_dict(body):
    """Return the first top-level <<...>> dict text of an object body."""
    idx = body.find(b'<<')
    if idx < 0:
        return b''
    depth = 0
    i = idx
    while i < len(body) - 1:
        if body[i:i + 2] == b'<<':
            depth += 1
            i += 2
        elif body[i:i + 2] == b'>>':
            depth -= 1
            i += 2
            if depth == 0:
                return body[idx:i]
        else:
            i += 1
    return body[idx:]


def _pdf_stream(body):
    m = re.search(rb'stream\r?\n', body)
    if not m:
        return None
    start = m.end()
    end = body.find(b'endstream', start)
    if end < 0:
        end = len(body)
    raw = body[start:end]
    if raw.endswith(b'\n'):
        raw = raw[:-1]
    return raw


def _pdf_pages(data, objs):
    """Return content stream bytes per page, in page order."""
    kids = []

    def refs(text):
        out = []
        for m in re.finditer(rb'(\d+)\s+(\d+)\s+R', text):
            out.append(int(m.group(1)))
        return out

    catalog = None
    for num, body in objs.items():
        if b'/Type /Catalog' in _pdf_dict(body) or b'/Type/Catalog' in _pdf_dict(body):
            catalog = num
            break
    if catalog is None:
        return []
    pages_root = refs(_pdf_dict(objs[catalog]))
    for n in pages_root:
        if n in objs and b'/Kids' in _pdf_dict(objs[n]):
            pages_root = [n]
            break
    stack = list(pages_root)
    order = []
    while stack:
        num = stack.pop(0)
        if num not in objs:
            continue
        d = _pdf_dict(objs[num])
        if b'/Type /Pages' in d or b'/Type/Pages' in d:
            stack = refs(d) + stack
        else:
            order.append(num)
    out = []
    for num in order:
        d = _pdf_dict(objs[num])
        crefs = refs(d)
        buf = b''
        for c in crefs:
            if c in objs:
                s = _pdf_stream(objs[c])
                if s is None:
                    continue
                buf += s + b'\n'
        if buf:
            out.append(buf)
    return out


def _tokenize(content):
    i = 0
    n = len(content)
    out = []
    while i < n:
        c = content[i:i + 1]
        if c in b' \t\r\n\f\v':
            i += 1
            continue
        if c == b'(':
            depth = 1
            j = i + 1
            buf = bytearray()
            while j < n and depth:
                ch = content[j:j + 1]
                if ch == b'\\':
                    nxt = content[j + 1:j + 2]
                    if nxt == b'n':
                        buf += b'\n'
                    elif nxt == b'r':
                        buf += b'\r'
                    elif nxt == b't':
                        buf += b'\t'
                    elif nxt == b'b':
                        buf += b'\x08'
                    elif nxt == b'f':
                        buf += b'\x0c'
                    elif nxt in b'()\\':
                        buf += nxt
                    elif nxt.isdigit():
                        oct_ = nxt
                        k = j + 2
                        while k < n and len(oct_) < 3 and content[k:k + 1].isdigit():
                            oct_ += content[k:k + 1]
                            k += 1
                        buf.append(int(oct_, 8) & 0xFF)
                        j = k - 2
                    else:
                        buf += nxt
                    j += 2
                    continue
                if ch == b'(':
                    depth += 1
                    buf += ch
                elif ch == b')':
                    depth -= 1
                    if depth == 0:
                        j += 1
                        break
                    buf += ch
                else:
                    buf += ch
                j += 1
            out.append(('str', bytes(buf)))
            i = j
            continue
        if c == b'<':
            if content[i + 1:i + 2] == b'<':
                depth = 0
                j = i
                while j < n:
                    if content[j:j + 2] == b'<<':
                        depth += 1
                        j += 2
                    elif content[j:j + 2] == b'>>':
                        depth -= 1
                        j += 2
                        if depth == 0:
                            break
                    else:
                        j += 1
                out.append(('dict', content[i:j]))
                i = j
                continue
            j = content.find(b'>', i)
            if j < 0:
                j = n
            hexs = re.sub(rb'\s', b'', content[i + 1:j])
            if len(hexs) % 2:
                hexs += b'0'
            try:
                out.append(('str', bytes.fromhex(hexs.decode('ascii'))))
            except Exception:
                out.append(('str', b''))
            i = j + 1
            continue
        if c == b'[':
            out.append(('arr_open', None))
            i += 1
            continue
        if c == b']':
            out.append(('arr_close', None))
            i += 1
            continue
        if c == b'/':
            j = i + 1
            while j < n and content[j:j + 1] not in b' \t\r\n\f\v/[]<>()':
                j += 1
            out.append(('name', content[i + 1:j]))
            i = j
            continue
        if c.isdigit() or c in b'+-.':
            j = i
            while j < n and content[j:j + 1] in b'+-.0123456789':
                j += 1
            txt = content[i:j]
            try:
                if b'.' in txt:
                    out.append(('num', float(txt)))
                else:
                    out.append(('num', int(txt)))
            except ValueError:
                out.append(('other', txt))
            i = j
            continue
        j = i
        while j < n and content[j:j + 1] not in b' \t\r\n\f\v/[]<>(){}':
            j += 1
        if j == i:
            j = i + 1
        out.append(('op', content[i:j]))
        i = j
    return out


def _matmul(m1, m2):
    a, b, c, d, e, f = m1
    a2, b2, c2, d2, e2, f2 = m2
    return (a * a2 + b * c2, a * b2 + b * d2,
            c * a2 + d * c2, c * b2 + d * d2,
            e * a2 + f * c2 + e2, e * b2 + f * d2 + f2)


def _apply(m, x, y):
    a, b, c, d, e, f = m
    return (a * x + c * y + e, b * x + d * y + f)


def pdf_text_items(content):
    """Return [(x, y, text, size)] for a content stream."""
    toks = _tokenize(content)
    items = []
    stack = []
    tm = (1, 0, 0, 1, 0, 0)
    ctm = (1, 0, 0, 1, 0, 0)
    leading = 0.0
    size = 0.0
    ops = []
    i = 0
    n = len(toks)

    def flush_text(x, y, txt):
        if txt:
            items.append((x, y, txt, size))

    while i < n:
        kind, val = toks[i]
        if kind in ('str', 'num', 'name', 'dict', 'other'):
            ops.append((kind, val))
            i += 1
            continue
        if kind == 'arr_open':
            depth = 1
            j = i + 1
            while j < n and depth:
                if toks[j][0] == 'arr_open':
                    depth += 1
                elif toks[j][0] == 'arr_close':
                    depth -= 1
                j += 1
            arr = toks[i + 1:j - 1]
            ops.append(('array', arr))
            i = j
            continue
        if kind == 'arr_close':
            i += 1
            continue
        # operator
        op = val.decode('latin1')
        args = ops
        ops = []
        if op == 'BT':
            tm = (1, 0, 0, 1, 0, 0)
        elif op == 'ET':
            pass
        elif op == 'Tm' and len(args) >= 6:
            nums = [a[1] for a in args[-6:] if a[0] == 'num']
            if len(nums) == 6:
                tm = tuple(nums)
        elif op in ('Td', 'TD') and len(args) >= 2:
            tx, ty = args[-2][1], args[-1][1]
            if op == 'TD':
                leading = -ty
            tm = _matmul((1, 0, 0, 1, tx, ty), tm)
        elif op == 'TL' and args:
            leading = args[-1][1]
        elif op == 'T*':
            tm = _matmul((1, 0, 0, 1, 0, -leading), tm)
        elif op == 'Tf' and len(args) >= 2:
            size = args[-2][1]
        elif op == 'cm' and len(args) >= 6:
            nums = [a[1] for a in args[-6:] if a[0] == 'num']
            if len(nums) == 6:
                ctm = _matmul(tuple(nums), ctm)
        elif op == 'q':
            stack.append((tm, ctm))
        elif op == 'Q':
            if stack:
                tm, ctm = stack.pop()
        elif op == 'Tj':
            if args and args[-1][0] == 'str':
                x, y = _apply(_matmul(ctm, tm), 0, 0)
                flush_text(x, y, args[-1][1].decode('latin1'))
        elif op == 'TJ':
            if args and args[-1][0] == 'array':
                txt = b''
                for k, v in args[-1][1]:
                    if k == 'str':
                        txt += v
                x, y = _apply(_matmul(ctm, tm), 0, 0)
                flush_text(x, y, txt.decode('latin1'))
        elif op == "'":
            tm = _matmul((1, 0, 0, 1, 0, -leading), tm)
            if args and args[-1][0] == 'str':
                x, y = _apply(_matmul(ctm, tm), 0, 0)
                flush_text(x, y, args[-1][1].decode('latin1'))
        elif op == '"':
            tm = _matmul((1, 0, 0, 1, 0, -leading), tm)
            if args and args[-1][0] == 'str':
                x, y = _apply(_matmul(ctm, tm), 0, 0)
                flush_text(x, y, args[-1][1].decode('latin1'))
        i += 1
    return items


def pdf_rows(path):
    """Return ordered rows across pages: list of (page, y, [(x, text, size), ...])."""
    data = open(path, 'rb').read()
    objs = _pdf_objects(data)
    pages = _pdf_pages(data, objs)
    if not pages:
        cands = []
        for num in sorted(objs):
            s = _pdf_stream(objs[num])
            if s is None:
                continue
            try:
                s = zlib.decompress(s)
            except Exception:
                pass
            if b'BT' in s and (b'Tj' in s or b'TJ' in s):
                cands.append(s)
        pages = cands
    rows = []
    for pno, content in enumerate(pages):
        try:
            content = zlib.decompress(content)
        except Exception:
            pass
        items = pdf_text_items(content)
        grouped = {}
        for x, y, txt, size in items:
            key = round(y, 1)
            grouped.setdefault(key, []).append((x, txt, size))
        for y in sorted(grouped, reverse=True):
            cells = sorted(grouped[y], key=lambda c: c[0])
            rows.append((pno, y, cells))
    return rows


def pdf_tables(path):
    """Extract memo tables keyed by table id.

    Returns {table_id: {'title': str, 'status': str, 'header': [..],
                        'columns': [x, ...], 'rows': [[cell, ...], ...]}}
    plus 'errata': list of erratum text strings.
    """
    rows = pdf_rows(path)
    tables = {}
    order = []
    cur = None
    errata = []
    title_re = re.compile(r'Table\s+([A-Z]-\d+)\s*(?:\(continued\))?\s*:?\s*(.*?)\s*'
                          r'\[(IN FORCE|WITHDRAWN|SUPERSEDED)\]\s*$')
    for pno, y, cells in rows:
        text = ' '.join(c[1] for c in cells).strip()
        text = re.sub(r'\s+', ' ', text)
        m = title_re.match(text)
        if m:
            tid = m.group(1)
            if tid not in tables:
                tables[tid] = {'title': m.group(2).strip(), 'status': m.group(3),
                               'header': None, 'columns': [], 'rows': []}
                order.append(tid)
            cur = tables[tid]
            continue
        if re.match(r'Errata\b', text):
            cur = None
            continue
        m2 = re.match(r'Erratum\s+([A-Z]-\d+)\s*:\s*(.*)$', text)
        if m2:
            errata.append(m2.group(2).strip())
            continue
        if cur is None:
            continue
        if cur['header'] is None:
            joined = ' '.join(cells[c][1] for c in range(len(cells)))
            joined = re.sub(r'\s+', ' ', joined).strip()
            if re.match(r'^(class|parameter|mark|rod type|degrees of freedom|ruling)\b', joined):
                cur['header'] = [c[1] for c in cells]
                cur['columns'] = [c[0] for c in cells]
                continue
        row = []
        for x, txt, size in cells:
            row.append((x, txt, size))
        cur['rows'].append(row)
    return tables, errata


def _cell_text(row_cells, columns):
    """Group (x, text, size) items into column texts."""
    if not columns:
        return [' '.join(c[1] for c in row_cells).strip()]
    out = [''] * len(columns)
    for x, txt, size in row_cells:
        best = 0
        bestdist = None
        for ci, cx in enumerate(columns):
            d = x - cx
            if d >= -1.0:
                if bestdist is None or d < bestdist:
                    bestdist = d
                    best = ci
        if bestdist is None:
            best = len(columns) - 1
        prev = out[best]
        if prev == '':
            out[best] = txt
        else:
            width = len(prev) * 0.5 * (row_cells[0][2] or 7)
            gap = x - (columns[best] + width)
            out[best] = prev + (' ' if gap > 1.0 else '') + txt
    return [re.sub(r'\s+', ' ', c).strip() for c in out]


def table_records(table):
    """Yield dicts {label:..., values: {header: text}} for a memo table."""
    cols = table['columns']
    hdr = table['header'] or []
    for row in table['rows']:
        cells = _cell_text(row, cols)
        rec = {}
        for i, h in enumerate(hdr):
            rec[h] = cells[i] if i < len(cells) else ''
        rec['__cells__'] = cells
        rec['__text__'] = ' '.join(cells)
        yield rec


def xlsx_table(sheet_rows, header_first_cell):
    """Return list of dicts using the row whose first cell equals the header."""
    hdr = None
    hidx = None
    for i, r in enumerate(sheet_rows):
        if r and r[0] == header_first_cell:
            hdr = r
            hidx = i
            break
    if hdr is None:
        for i, r in enumerate(sheet_rows[:10]):
            if r and sum(1 for c in r if c not in (None, '')) >= 3:
                hdr = r
                hidx = i
                break
    if hdr is None:
        return []
    out = []
    for r in sheet_rows[hidx + 1:]:
        if not any(c for c in r if c is not None):
            continue
        if len(r) >= 1 and (r[0] or '').strip() == 'continued':
            continue
        d = {}
        for j, k in enumerate(hdr):
            if k is None:
                continue
            d[k] = r[j] if j < len(r) else None
        out.append(d)
    return out


# --------------------------------------------------------------------------
# time handling
# --------------------------------------------------------------------------

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def to_utc(dt):
    if dt.tzinfo is None:
        raise ValueError('naive datetime')
    return dt.astimezone(timezone.utc)


def parse_instant(s, clock, style):
    """Return a timezone-aware UTC datetime for a shard time field."""
    if isinstance(s, (int, float)) and not isinstance(s, bool):
        if style == 'epoch':
            return _EPOCH + timedelta(seconds=int(s))
        s = repr(s)
    s = str(s if s is not None else '').strip()
    if not s:
        return None
    if style == 'epoch':
        return _EPOCH + timedelta(seconds=int(float(s)))
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?\s*(Z|UTC|[+-]\d{2}:?\d{2})?$',
                 s)
    if m:
        y, mo, d, h, mi, sec = (int(m.group(i)) for i in range(1, 7))
        frac = m.group(7)
        tz = m.group(8)
        if frac:
            sec += float('0.' + frac)
        base = datetime(y, mo, d, h, mi, int(sec))
        if int(sec) != sec:
            base = base.replace(microsecond=int(round((sec - int(sec)) * 1e6)))
        if tz in (None, '', 'Z', 'UTC'):
            return base.replace(tzinfo=timezone.utc)
        sign = 1 if tz[0] == '+' else -1
        t = tz[1:].replace(':', '')
        off = timedelta(hours=int(t[:2]), minutes=int(t[2:4])) * sign
        return base.replace(tzinfo=timezone(off)).astimezone(timezone.utc)
    m = re.match(r'^(\d{4})(\d{2})(\d{2})\s*(\d{2})(\d{2})(\d{2})$', s)
    if m:
        y, mo, d, h, mi, sec = (int(m.group(i)) for i in range(1, 7))
        return clock.local_to_utc(datetime(y, mo, d, h, mi, sec))
    m = re.match(r'^(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})\s+(\d{2}):(\d{2}):(\d{2})$', s)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        h, mi, sec = int(m.group(4)), int(m.group(5)), int(m.group(6))
        return clock.local_to_utc(datetime(y, mo, d, h, mi, sec))
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})[ ](\d{2}):(\d{2}):(\d{2})$', s)
    if m:
        y, mo, d, h, mi, sec = (int(m.group(i)) for i in range(1, 7))
        return clock.local_to_utc(datetime(y, mo, d, h, mi, sec))
    d = parse_date(s)
    if d is not None:
        return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    raise ValueError('bad time %r' % s)


class SiteClock:
    def __init__(self, cfg):
        self.trans = []
        self.std = '+01:00'
        if isinstance(cfg, dict):
            self.std = str(cfg.get('standard_offset') or '+01:00')
            for t in (cfg.get('transitions') or []):
                utc = t.get('utc')
                off = t.get('offset')
                if utc and off:
                    self.trans.append((parse_instant(utc, None, 'iso'),
                                       self._offset(off)))
            self.trans.sort(key=lambda x: x[0])
        if not self.trans:
            self.trans = [(datetime(1900, 1, 1, tzinfo=timezone.utc),
                           self._offset(self.std))]

    @staticmethod
    def _offset(txt):
        txt = str(txt).strip()
        sign = 1
        if txt.startswith('-'):
            sign = -1
        t = txt.lstrip('+-').replace(':', '')
        h = int(t[:2]) if len(t) >= 2 else 0
        m = int(t[2:4]) if len(t) >= 4 else 0
        return timedelta(hours=h, minutes=m) * sign

    def offset_at(self, utc_dt):
        off = self._offset(self.std)
        for t, o in self.trans:
            if t <= utc_dt:
                off = o
            else:
                break
        return off

    def utc_to_local(self, utc_dt):
        return (utc_dt + self.offset_at(utc_dt)).replace(tzinfo=None)

    def local_to_utc(self, local_dt):
        if local_dt.tzinfo is not None:
            local_dt = local_dt.replace(tzinfo=None)
        for t, o in self.trans:
            if (local_dt - o) >= t.replace(tzinfo=None):
                cand = (local_dt - o).replace(tzinfo=timezone.utc)
                if self.offset_at(cand) == o:
                    return cand
        for t, o in self.trans:
            cand = (local_dt - o).replace(tzinfo=timezone.utc)
            if self.offset_at(cand) == o:
                return cand
        return local_dt.replace(tzinfo=timezone.utc)


def local_date(utc_dt, clock):
    return clock.utc_to_local(utc_dt).date()


def fmt_instant(dt):
    dt = to_utc(dt).replace(microsecond=0)
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')


# --------------------------------------------------------------------------
# registers
# --------------------------------------------------------------------------


def read_delim(path, delim):
    rows = []
    with open(path, newline='', encoding='utf-8-sig') as f:
        rdr = csv.reader(f, delimiter=delim)
        for r in rdr:
            rows.append(r)
    return rows


def table_from_rows(rows):
    if not rows:
        return []
    hdr = rows[0]
    out = []
    for r in rows[1:]:
        d = {}
        for i, k in enumerate(hdr):
            d[k] = r[i] if i < len(r) else ''
        out.append(d)
    return out


def detect(path):
    """Content sniffing: return a register kind or None."""
    try:
        with open(path, 'rb') as f:
            head = f.read(4096)
    except OSError:
        return None
    if head.startswith(b'SQLite format 3'):
        return 'sqlite'
    if head.lstrip()[:5] == b'%PDF-':
        return 'pdf'
    if head.lstrip()[:2] == b'PK':
        return 'xlsx'
    low = head.decode('utf-8', 'replace').lower()
    first = low.splitlines()[0].strip() if low.splitlines() else ''
    if first.startswith('{') or first.startswith('"'):
        return 'json'
    return 'text'


def load_json(path):
    with open(path, encoding='utf-8-sig') as f:
        return json.load(f)


def load_jsonl(path):
    out = []
    with open(path, encoding='utf-8-sig') as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


class Registers:
    pass


def sniff_layout(path):
    """Return a layout id if the file looks like a setup shard, else None."""
    try:
        kind = detect(path)
    except Exception:
        return None
    if kind in ('pdf', 'xlsx'):
        return None
    if kind == 'sqlite':
        try:
            con = sqlite3.connect('file:%s?mode=ro' % path, uri=True)
            tabs = set(r[0] for r in con.execute(
                "select name from sqlite_master where type='table'"))
            cols = {}
            for t in ('obs', 'setup_key', 'setup_attr'):
                try:
                    cols[t] = [r[1] for r in con.execute('pragma table_info(%s)' % t)]
                except Exception:
                    cols[t] = []
            con.close()
            if 'setup_key' in tabs and 'setup_attr' in tabs:
                return 'L13'
            if 'obs' in tabs and 'run' in cols.get('obs', []):
                return 'L12'
        except Exception:
            return None
        return None
    try:
        with open(path, 'rb') as f:
            txt = f.read(1 << 20).decode('utf-8', 'replace')
    except Exception:
        return None
    lines = txt.splitlines()
    nonempty = [l for l in lines if l.strip()]
    stripped = [l for l in lines if l.strip() and not l.lstrip().startswith('#')]
    if not stripped:
        return None
    # JSON document
    if stripped[0].lstrip().startswith('{'):
        blob = '\n'.join(l for l in lines if l.strip() and not l.lstrip().startswith('#'))
        try:
            doc = json.loads(blob)
        except Exception:
            doc = None
        if isinstance(doc, dict) and isinstance(doc.get('setups'), list) and doc['setups']:
            return 'L07'
        # JSON Lines
        first = stripped[0]
        try:
            obj = json.loads(first)
        except Exception:
            obj = None
        if isinstance(obj, dict):
            keys = set(obj.keys())
            if {'run_ref', 'seq', 'rev'} <= keys:
                return 'L06'
            if 'setup' in keys and isinstance(obj.get('run'), dict):
                return 'L05'
        return None
    # XML
    if txt.lstrip().startswith('<'):
        m = re.match(r'<\s*(\w+)', txt.lstrip())
        root = m.group(1) if m else ''
        if root == 'setups':
            return 'L16'
        if root == 'fieldbook':
            return 'L08'
        return None
    # YAML
    yhead = stripped[0].strip()
    if re.match(r'^setups\s*:\s*$', yhead, re.I):
        return 'L09'
    if re.match(r'^runs\s*:\s*$', yhead, re.I):
        return 'L10'
    # markdown table
    for l in stripped:
        if re.match(r'^\|\s*run\s*\|\s*setup\s*\|', l, re.I):
            return 'L11'
    # delimited headers
    head = stripped[0]
    for delim in ('\t', ',', ';', '|'):
        cells = [c.strip() for c in head.split(delim)]
        if len(cells) < 4:
            continue
        low = [c.lower() for c in cells]
        if delim == '\t' and low[0] == 'run' and low[1] == 'seq' and low[3] == 'void':
            return 'L15'
        if delim == '\t' and low[0] == 'run' and low[1] == 'set' and low[2] == 'r':
            return 'L02'
        if delim == ',' and low[0] == 'run' and low[1] == 'setup' and low[2] == 'rev':
            return 'L01'
        if delim == ';' and low[0] == 'run' and low[1] == 'opstelling':
            return 'L14'
        if delim == '|' and low[0] == 'run' and low[1] == 'setup' and low[2] == 'rev':
            return 'L03'
    # fixed width
    for l in lines:
        if re.match(r'^RUN\s+SEQ RVVDATE', l):
            return 'L04'
    return None


def norm_run_id(tok):
    t = str(tok).strip()
    m = re.match(r'^R-26-(\d+)$', t)
    if m:
        return 'R-26-%04d' % int(m.group(1))
    m = re.match(r'^R26(\d+)$', t)
    if m:
        return 'R-26-%04d' % int(m.group(1))
    m = re.match(r'^26/(\d+)$', t)
    if m:
        return 'R-26-%04d' % int(m.group(1))
    return t


def norm_token(tok):
    t = str(tok).strip().upper().replace(' ', '')
    m = re.match(r'^VD-?(\d{1,4})$', t)
    if m:
        return 'VD-%04d' % int(m.group(1))
    if re.match(r'^\d{1,4}$', t):
        return 'VD-%04d' % int(t)
    m = re.match(r'^MB-?(\d{1,3})$', t)
    if m:
        return 'MB-%03d' % int(m.group(1))
    return t


def rod_serial(tok):
    m = re.search(r'(\d+)', str(tok or ''))
    if not m:
        return None
    return str(int(m.group(1)))


# --------------------------------------------------------------------------
# campaign loading
# --------------------------------------------------------------------------

FT_PER_M = Fraction(1200, 3937)


class Campaign:
    pass


def _first_meaningful(text):
    for line in text.splitlines():
        s = line.strip()
        if s and not s.startswith('#'):
            return s
    return ''


def load_campaign(data_dir):
    C = Campaign()
    C.data_dir = data_dir
    C.files = sorted(os.listdir(data_dir))

    C.catalog = None
    C.run_register = []
    C.amendments = []
    C.sections = []
    C.lines = []
    C.bm_master = {}
    C.bm_alias = []
    C.instrument_alias = {}
    C.two_peg = []
    C.journal = []
    C.addendum = []
    C.epochs = {}
    C.epoch_heights = {}
    C.stations = []
    C.roster = []
    C.loops = []
    C.legacy_rods = []
    C.memo_path = None
    C.workbook_path = None
    C.profile_path = None
    C.overlay_path = None
    C.clock_path = None
    C.bulletin_path = None
    C.dashboard_path = None
    C.published_path = None
    C.pubrates_path = None
    C.cache_path = None
    C.runpack_path = None
    C.log_files = []
    C.card_path = None

    for name in C.files:
        path = os.path.join(data_dir, name)
        if not os.path.isfile(path):
            continue
        with open(path, 'rb') as f:
            raw = f.read(1 << 22)
        if raw.lstrip().startswith(b'%PDF'):
            if C.memo_path is None:
                C.memo_path = name
            continue
        if raw[:2] == b'PK':
            if C.workbook_path is None:
                C.workbook_path = name
            continue
        if raw.startswith(b'SQLite format 3'):
            try:
                con = sqlite3.connect('file:%s?mode=ro' % path, uri=True)
                tabs = set(r[0] for r in con.execute(
                    "select name from sqlite_master where type='table'"))
                if 'bm_alias' in tabs:
                    for r in con.execute('select token, canonical, valid_from, valid_to'
                                         ' from bm_alias'):
                        C.bm_alias.append((r[0], r[1], r[2], r[3]))
                if 'instrument_alias' in tabs or 'two_peg' in tabs:
                    for r in con.execute('select token, instrument from instrument_alias'):
                        C.instrument_alias[str(r[0]).strip()] = str(r[1]).strip()
                    for r in con.execute('select test_id, instrument, tested_utc,'
                                         ' c_mm_per_100m, result from two_peg'):
                        C.two_peg.append({'test_id': r[0], 'instrument': r[1],
                                          'tested_utc': r[2], 'c': r[3],
                                          'result': r[4]})
                if 'epochs' in tabs or 'heights' in tabs:
                    for r in con.execute('select epoch_id, reference_date, status from epochs'):
                        C.epochs[r[0]] = {'reference_date': r[1], 'status': r[2]}
                    for r in con.execute('select epoch_id, mark, height_m, sigma_mm from heights'):
                        C.epoch_heights.setdefault(r[0], {})[r[1]] = {
                            'height_m': r[2], 'sigma_mm': r[3]}
                con.close()
            except Exception:
                pass
            continue
        text = raw.decode('utf-8', 'replace')
        fm = _first_meaningful(text)
        fml = fm.lower()
        # ingest catalog (JSON with a catalog key and an entries list)
        if '"catalog"' in text[:200] and '"entries"' in text[:400]:
            try:
                doc = load_json(path)
            except Exception:
                doc = None
            if isinstance(doc, dict) and isinstance(doc.get('entries'), list) \
                    and 'catalog' in doc and C.catalog is None:
                C.catalog = doc
                C.catalog_path = name
                continue
        # run register
        if fml.startswith('run_id,') and 'campaign' in fml:
            C.run_register = table_from_rows(read_delim(path, ','))
            continue
        # section register
        if re.match(r'^section_id\s*\t\s*from_mark', fml):
            C.sections = table_from_rows(read_delim(path, '\t'))
            continue
        # line register
        if '"levelling lines"' in text[:400]:
            try:
                doc = load_json(path)
            except Exception:
                doc = None
            if isinstance(doc, dict) and isinstance(doc.get('lines'), list):
                C.lines = doc['lines']
                continue
        # benchmark master
        if re.match(r'^mark\s*,\s*block\s*,\s*description', fml):
            for r in table_from_rows(read_delim(path, ',')):
                C.bm_master[r['mark'].strip()] = r
            continue
        # met station register
        if re.match(r'^station_id\s*\|\s*tokens\s*\|\s*name', fml):
            for r in table_from_rows(read_delim(path, '|')):
                C.stations.append(r)
            continue
        # dashboard
        if re.match(r'^section_id\s*,\s*status\s*,', fml):
            C.dashboard = table_from_rows(read_delim(path, ','))
            C.dashboard_path = name
            continue
        # published heights
        if re.match(r'^mark\s*,\s*height_m\s*,\s*status\s*$', fml):
            rows = []
            for r in read_delim(path, ','):
                if not r or (r[0] or '').strip().startswith('#'):
                    continue
                if [c.strip().lower() for c in r[:3]] == ['mark', 'height_m', 'status']:
                    continue
                rows.append(r)
            hdr = ['mark', 'height_m', 'status']
            C.published = [dict(zip(hdr, r)) for r in rows]
            C.published_path = name
            continue
        # XML registers
        if text.lstrip().startswith('<journal'):
            C.journal = ET.fromstring(text)
            continue
        if text.lstrip().startswith('<addendum'):
            C.addendum = ET.fromstring(text)
            continue
        # JSON / JSONL registers
        if text.lstrip().startswith('{'):
            obj = None
            try:
                obj = json.loads(text)
            except Exception:
                pass
            if isinstance(obj, dict) and isinstance(obj.get('rates'), list):
                C.pubrates = obj
                C.pubrates_path = name
                continue
            if isinstance(obj, dict) and isinstance(obj.get('overlay'), list):
                C.overlay = obj
                C.overlay_path = name
                continue
            if isinstance(obj, dict) and obj.get('transitions') and \
                    'standard_offset' in obj:
                C.clock = obj
                C.clock_path = name
                continue
            try:
                objs = load_jsonl(path)
            except Exception:
                objs = None
            if objs and isinstance(objs[0], dict):
                keys = set(objs[0].keys())
                if 'amend_no' in keys and 'run' in keys:
                    C.amendments = objs
                    continue
                if 'observer' in keys and 'valid_from' in keys:
                    C.roster = objs
                    continue
                if 'epoch' in keys and 'height_m' in keys and 'mark' in keys:
                    C.cache = objs
                    C.cache_path = name
                    continue
                if 'ta' in keys and 't' in keys:
                    C.log_files.append(name)
                    continue
            continue
        # YAML registers
        if re.match(r'^loops\s*:', fml):
            doc = yaml_load(text)
            if isinstance(doc, dict) and isinstance(doc.get('loops'), list):
                C.loops = doc['loops']
                continue
        if re.match(r'^rods\s*:', fml):
            doc = yaml_load(text)
            if isinstance(doc, dict) and isinstance(doc.get('rods'), list):
                C.legacy_rods = doc['rods']
                continue
        if re.match(r'^overlay\s*:', fml):
            doc = yaml_load(text)
            if isinstance(doc, dict) and isinstance(doc.get('overlay'), list):
                C.overlay = doc
                C.overlay_path = name
                continue
        if re.match(r'^campaign_id\s*:', fml) and 'reference_date' in text[:2000]:
            doc = yaml_load(text)
            if isinstance(doc, dict) and doc.get('campaign_id'):
                C.profile = doc
                C.profile_path = name
                continue
        if 'standard_offset' in text[:200] and 'transitions:' in text[:400]:
            doc = yaml_load(text)
            if isinstance(doc, dict) and doc.get('transitions'):
                C.clock = doc
                C.clock_path = name
                continue
        # bulletin
        if 'OPERATIONAL NOTICE' in text and 'IN FORCE' in text:
            if C.bulletin_path is None:
                C.bulletin_path = name
                C.bulletin = text
            continue
        # run pack
        if 'control_table:' in text and 'pair_selection:' in text:
            if C.runpack_path is None:
                C.runpack_path = name
                C.runpack = text
            continue
        # met station logs
        if re.match(r'^epoch_s\s*,\s*temp_c', fml) or \
                re.match(r'^utc\s+temp\s', fml) or fml.startswith('"t"'):
            C.log_files.append(name)
            continue
        # quick reference card (mean earth radius only)
        if 'mean earth radius' in text and 'QUICK REFERENCE' in text.upper():
            if C.card_path is None:
                C.card_path = name
                C.card = text
            continue
    return C




# --------------------------------------------------------------------------
# shard reading
# --------------------------------------------------------------------------

class Rec:
    __slots__ = ('file', 'findex', 'rindex', 'run', 'seq', 'rev', 'void', 'instant',
                 'back_m', 'fore_m', 'back_d', 'fore_d', 'temp', 'back_rod',
                 'fore_rod', 'content', 'state', 'orig_temp')


def _dec_num(v, div=None):
    """Exact Fraction from a shard numeric field."""
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, Fraction):
        f = v
    elif isinstance(v, (int,)):
        f = Fraction(v)
    elif isinstance(v, float):
        f = Fraction(Decimal(repr(v)))
    elif isinstance(v, Decimal):
        f = Fraction(v)
    else:
        s = str(v).strip().replace(',', '.')
        if s == '':
            return None
        if s in ('~', 'null', 'None', 'NaN', 'nan'):
            return None
        try:
            f = Fraction(Decimal(s))
        except Exception:
            return None
    if div:
        f = f / div
    return f


def read_shard(path, layout, ctx):
    """Return a list of Rec for one shard file."""
    recs = []
    D = ctx
    clock = D.clock

    def rods_from_pair(pair_id, seq, run):
        pid = str(pair_id or '').strip()
        pair = D.rod_pairs.get(pid)
        if not pair:
            return None, None
        a, b = pair
        if seq % 2 == 1:
            return a, b
        return b, a

    def finish(run, seq, rev, void, instant, btoken, ftoken, bs, fs, bd, fd,
               temp, findex, rindex):
        r = Rec()
        r.file = os.path.basename(path)
        r.findex = findex
        r.rindex = rindex
        r.run = norm_run_id(run)
        try:
            r.seq = int(str(seq).strip())
        except Exception:
            r.seq = None
        try:
            r.rev = int(str(rev).strip())
        except Exception:
            r.rev = 0
        r.void = bool(void)
        r.instant = instant
        # rods
        if btoken is None and ftoken is None:
            bt, ft = None, None
        else:
            bt = rod_serial(btoken)
            ft = rod_serial(ftoken)
            if bt is not None:
                bt = D.former.get(bt, bt)
            if ft is not None:
                ft = D.former.get(ft, ft)
        if bt is None and ft is None:
            bt, ft = rods_from_pair(D.run_pair.get(r.run), r.seq, r.run)
        r.back_rod = bt
        r.fore_rod = ft
        r.back_d = bd
        r.fore_d = fd
        r.orig_temp = temp
        # half graduation decoding
        bm = _dec_num(bs)
        fm = _dec_num(fs)
        if bm is not None and D.rod_half.get(bt):
            bm = bm / 2
        if fm is not None and D.rod_half.get(ft):
            fm = fm / 2
        r.back_m = bm
        r.fore_m = fm
        r.temp = temp
        r.content = (r.instant, r.back_m, r.fore_m, r.back_d, r.fore_d,
                     r.temp, r.back_rod, r.fore_rod, r.void)
        r.state = 'read'
        recs.append(r)

    findex = ctx.findex_of.get(os.path.basename(path), 0)
    if layout == 'L01':
        rows = [r for r in read_delim(path, ',')
                if r and not (r[0] or '').lstrip().startswith('#')]
        data = table_from_rows(rows)
        for i, d in enumerate(data):
            t = d.get('time_utc', '')
            inst = parse_instant(t, clock, 'iso')
            temp = _dec_num(d.get('rod_temp_c'))
            finish(d.get('run'), d.get('setup'), d.get('rev'),
                   str(d.get('void', '0')).strip() in ('1', 'true', 'TRUE', 'yes'),
                   inst, d.get('rod_bs'), d.get('rod_fs'),
                   _dec_num(d.get('bs_m')), _dec_num(d.get('fs_m')),
                   _dec_num(d.get('dist_bs_m')), _dec_num(d.get('dist_fs_m')),
                   temp, findex, i)
    elif layout == 'L02':
        rows = [r for r in read_delim(path, '\t') if r and any(c.strip() for c in r)]
        data = table_from_rows(rows)
        for i, d in enumerate(data):
            inst = parse_instant(d.get('time', ''), clock, 'iso')
            temp = None
            finish(d.get('run'), d.get('set'), d.get('r'),
                   str(d.get('status', '')).strip().upper() == 'VOID',
                   inst, None, None,
                   _dec_num(d.get('bs_mm'), 1000), _dec_num(d.get('fs_mm'), 1000),
                   _dec_num(d.get('dbs_dm'), 10), _dec_num(d.get('dfs_dm'), 10),
                   None, findex, i)
    elif layout == 'L03':
        rows = [r for r in read_delim(path, '|') if r and any(c.strip() for c in r)]
        data = table_from_rows(rows)
        for i, d in enumerate(data):
            inst = parse_instant(d.get('LOCAL_TIME', ''), clock, 'local')
            temp = _dec_num(d.get('TEMP_C'))
            finish(d.get('RUN'), d.get('SETUP'), d.get('REV'),
                   str(d.get('VOIDED', '')).strip().upper() == 'Y',
                   inst, d.get('BACK_ROD'), d.get('FORE_ROD'),
                   _dec_num(d.get('BACK_READING_M')), _dec_num(d.get('FORE_READING_M')),
                   _dec_num(d.get('BACK_DIST_M')), _dec_num(d.get('FORE_DIST_M')),
                   temp, findex, i)
    elif layout == 'L04':
        lines = [l.rstrip('\n') for l in open(path, encoding='utf-8-sig')]
        ri = 0
        for line in lines:
            if not line.strip():
                continue
            if re.match(r'^RUN\s+SEQ', line) or line.startswith('VDO '):
                continue
            if len(line) < 55:
                continue
            run = line[0:8].strip()
            seq = line[8:12].strip()
            rev = line[12:14].strip()
            vflag = line[14:15]
            dpart = line[15:23].strip()
            tpart = line[23:29].strip()
            pair = line[29:33].strip()
            bs = line[33:40].strip()
            fs = line[40:47].strip()
            dbs = line[47:51].strip()
            dfs = line[51:55].strip()
            ts = line[55:60].strip()
            void = vflag == 'V'
            inst = parse_instant(dpart + ' ' + tpart, clock, 'compact')
            temp = None
            if ts:
                temp = _dec_num(ts, 10)
            pid = pair or D.run_pair.get(norm_run_id(run))
            bt, ft = rods_from_pair(pid, int(seq), norm_run_id(run))
            finish(run, seq, rev, void, inst, bt, ft,
                   _dec_num(bs, 100000), _dec_num(fs, 100000),
                   _dec_num(dbs, 10), _dec_num(dfs, 10), temp, findex, ri)
            ri += 1
    elif layout == 'L05':
        for i, o in enumerate(load_jsonl(path)):
            inst = parse_instant(o.get('time', ''), clock, 'iso')
            su = o.get('setup') or {}
            temp = _dec_num(o.get('temp_c'))
            bs = o.get('bs') or {}
            fs = o.get('fs') or {}
            rid = (o.get('run') or {}).get('id')
            finish(rid, su.get('n'), su.get('rev'), bool(su.get('void')),
                   inst, bs.get('rod'), fs.get('rod'),
                   _dec_num(bs.get('r')), _dec_num(fs.get('r')),
                   _dec_num(bs.get('d')), _dec_num(fs.get('d')),
                   temp, findex, i)
    elif layout == 'L06':
        for i, o in enumerate(load_jsonl(path)):
            inst = parse_instant(o.get('epoch_s'), clock, 'epoch')
            temp = None
            tf = _dec_num(o.get('temp_f'))
            if tf is not None:
                temp = Fraction(round_scaled((tf - 32) * Fraction(5, 9), 10), 10)
            finish(o.get('run_ref'), o.get('seq'), o.get('rev'),
                   bool(o.get('deleted')), inst, None, None,
                   _dec_num(o.get('bs_mm'), 1000), _dec_num(o.get('fs_mm'), 1000),
                   _dec_num(o.get('dbs_m')), _dec_num(o.get('dfs_m')),
                   temp, findex, i)
    elif layout == 'L07':
        doc = load_json(path)
        for i, o in enumerate(doc.get('setups') or []):
            inst = parse_instant(o.get('utc', ''), clock, 'iso')
            b = o.get('back') or {}
            f = o.get('fore') or {}
            finish(o.get('run'), o.get('seq'), o.get('revision'),
                   str(o.get('state', '')).strip().lower() == 'void',
                   inst, b.get('rod'), f.get('rod'),
                   _dec_num(b.get('reading_m')), _dec_num(f.get('reading_m')),
                   _dec_num(b.get('distance_m')), _dec_num(f.get('distance_m')),
                   None, findex, i)
    elif layout == 'L08':
        root = ET.parse(path).getroot()
        for i, e in enumerate(root.iter('setup')):
            inst = parse_instant(e.get('local', ''), clock, 'local')
            tc = (e.get('temp_c') or '').strip()
            temp = _dec_num(tc) if tc else None
            finish(e.get('run'), e.get('seq'), e.get('rev'),
                   str(e.get('void', '')).strip().lower() == 'true',
                   inst, e.get('brod'), e.get('frod'),
                   _dec_num(e.get('bs_mm'), 1000), _dec_num(e.get('fs_mm'), 1000),
                   _dec_num(e.get('dbs_dm'), 10), _dec_num(e.get('dfs_dm'), 10),
                   temp, findex, i)
    elif layout == 'L09':
        doc = yaml_load(open(path, encoding='utf-8-sig').read())
        for i, o in enumerate(doc.get('setups') or []):
            inst = parse_instant(str(o.get('time', '')), clock, 'iso')
            temp = _dec_num(o.get('temp'))
            finish(o.get('run'), o.get('set'), o.get('rev'),
                   _truthy(o.get('void')), inst, None, None,
                   _dec_num(o.get('bs')), _dec_num(o.get('fs')),
                   _dec_num(o.get('d_bs')), _dec_num(o.get('d_fs')),
                   temp, findex, i)
    elif layout == 'L10':
        doc = yaml_load(open(path, encoding='utf-8-sig').read())
        for run, items in (doc.get('runs') or {}).items():
            for i, o in enumerate(items):
                inst = parse_instant(o[3], clock, 'epoch')
                finish(run, o[0], o[1], _truthy(o[2]), inst, o[4], o[5],
                       _dec_num(o[6], 1000), _dec_num(o[7], 1000),
                       _dec_num(o[8]), _dec_num(o[9]), None, findex, i)
    elif layout == 'L11':
        rows = []
        for line in open(path, encoding='utf-8-sig'):
            line = line.rstrip('\n')
            if not line.startswith('|'):
                continue
            cells = [c.strip() for c in line.strip('|').split('|')]
            if cells and cells[0].lower() == 'run':
                continue
            if cells and set(cells[0]) <= set('-: '):
                continue
            rows.append(cells)
        for i, c in enumerate(rows):
            inst = parse_instant(c[4], clock, 'local')
            tf = c[11].strip()
            temp = None
            if tf:
                f = _dec_num(tf)
                if f is not None:
                    temp = Fraction(round_scaled((f - 32) * Fraction(5, 9), 10), 10)
            finish(c[0], c[1], c[2], c[3].strip().lower() == 'void', inst,
                   c[5], c[6], _dec_num(c[7]), _dec_num(c[8]),
                   _dec_num(c[9]), _dec_num(c[10]), temp, findex, i)
    elif layout == 'L12':
        con = sqlite3.connect('file:%s?mode=ro' % path, uri=True)
        rows = list(con.execute('select run, seq, rev, void, epoch, pair, bs, fs,'
                                ' dbs, dfs, temp_c from obs'))
        con.close()
        for i, r in enumerate(rows):
            inst = parse_instant(r[4], clock, 'epoch')
            temp = _dec_num(r[10])
            pid = r[5] or D.run_pair.get(norm_run_id(r[0]))
            bt, ft = rods_from_pair(pid, int(r[1]), norm_run_id(r[0]))
            finish(r[0], r[1], r[2], bool(r[3]), inst, bt, ft,
                   _dec_num(r[6], 100000), _dec_num(r[7], 100000),
                   _dec_num(r[8], 10), _dec_num(r[9], 10), temp, findex, i)
    elif layout == 'L13':
        con = sqlite3.connect('file:%s?mode=ro' % path, uri=True)
        keys = list(con.execute('select uid, run, seq, rev from setup_key'))
        attrs = {}
        for uid, k, v in con.execute('select uid, attr, value from setup_attr'):
            attrs.setdefault(uid, {})[k] = v
        con.close()
        for i, (uid, run, seq, rev) in enumerate(keys):
            a = attrs.get(uid, {})
            inst = parse_instant(a.get('time_utc', ''), clock, 'iso')
            temp = _dec_num(a.get('temp_c'))
            finish(run, seq, rev, str(a.get('void', '0')).strip() == '1',
                   inst, a.get('rod_b'), a.get('rod_f'),
                   _dec_num(a.get('bs_m')), _dec_num(a.get('fs_m')),
                   _dec_num(a.get('dist_b_m')), _dec_num(a.get('dist_f_m')),
                   temp, findex, i)
    elif layout == 'L14':
        rows = [r for r in read_delim(path, ';') if r and any(c.strip() for c in r)]
        data = table_from_rows(rows)
        for i, d in enumerate(data):
            inst = parse_instant(d.get('tijd', ''), clock, 'local')
            temp = _dec_num(d.get('temp_c'))
            finish(d.get('run'), d.get('opstelling'), d.get('rev'),
                   str(d.get('vervallen', '')).strip().lower() in ('ja', 'yes', 'true'),
                   inst, d.get('baak_a'), d.get('baak_v'),
                   _dec_num(d.get('a_mm'), 1000), _dec_num(d.get('v_mm'), 1000),
                   _dec_num(d.get('afst_a_m')), _dec_num(d.get('afst_v_m')),
                   temp, findex, i)
    elif layout == 'L15':
        rows = [r for r in read_delim(path, '\t') if r and any(c.strip() for c in r)]
        data = table_from_rows(rows)
        for i, d in enumerate(data):
            inst = parse_instant(d.get('time', ''), clock, 'iso')
            tf = _dec_num(d.get('temp_f'))
            temp = None
            if tf is not None:
                temp = Fraction(round_scaled((tf - 32) * Fraction(5, 9), 10), 10)
            finish(d.get('run'), d.get('seq'), d.get('rev'),
                   str(d.get('void', '0')).strip() in ('1', 'true', 'yes'),
                   inst, d.get('rod_b'), d.get('rod_f'),
                   _dec_num(d.get('bs_m')), _dec_num(d.get('fs_m')),
                   _ft_to_m(d.get('dist_b_ft')), _ft_to_m(d.get('dist_f_ft')),
                   temp, findex, i)
    elif layout == 'L16':
        root = ET.parse(path).getroot()
        for i, e in enumerate(root.iter('setup')):
            inst = parse_instant(e.findtext('utc', '').strip(), clock, 'iso')
            pid = (e.findtext('pair') or '').strip() or \
                D.run_pair.get(norm_run_id(e.findtext('run', '')))
            seq = int(e.findtext('seq', '0'))
            bt, ft = rods_from_pair(pid, seq, norm_run_id(e.findtext('run', '')))
            finish(e.findtext('run'), seq, e.findtext('rev'),
                   str(e.findtext('void', '0')).strip() == '1',
                   inst, bt, ft,
                   _dec_num(e.findtext('bs'), 100000),
                   _dec_num(e.findtext('fs'), 100000),
                   _ft_to_m(e.findtext('dbs_ft')), _ft_to_m(e.findtext('dfs_ft')),
                   None, findex, i)
    return recs


def _truthy(v):
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    return s in ('1', 'true', 'yes', 'y', 'ja')


def _ft_to_m(v):
    f = _dec_num(v)
    if f is None:
        return None
    return Fraction(round_scaled(f * FT_PER_M, 10), 10)


# --------------------------------------------------------------------------
# campaign computations
# --------------------------------------------------------------------------


class Memo:
    pass


def memo_params(C):
    """Parse the governance memo tables (IN FORCE) and apply the errata."""
    M = Memo()
    tables, errata = pdf_tables(os.path.join(C.data_dir, C.memo_path))
    M.tables = tables

    def inforce(tid):
        t = tables.get(tid)
        if t is None or t.get('status') != 'IN FORCE':
            return None
        return t

    M.raw = {}
    # Table I-1
    t = inforce('I-1')
    params = {}
    if t:
        for rec in table_records(t):
            params[rec.get('parameter', '').strip().lower()] = rec.get('value', '').strip()
    M.raw['collimation'] = params.get('collimation limit mm per 100 m', '')
    M.raw['refraction'] = params.get('refraction coefficient', '')
    M.collimation_limit = _dec_num(M.raw['collimation'])
    M.refraction = _dec_num(M.raw['refraction'])

    # Table K-1
    t = inforce('K-1')
    kparams = {}
    if t:
        for rec in table_records(t):
            kparams[rec.get('parameter', '').strip().lower()] = rec.get('value', '').strip()
    M.sigma = {}
    M.raw['sigma'] = {}
    for cls in ('I', 'II', 'III'):
        for k, v in kparams.items():
            if k.startswith('sigma class') and re.search(r'\b%s\b' % cls.lower(), k):
                M.sigma[cls] = _dec_num(v)
                M.raw['sigma'][cls] = v
    M.raw['critical_w'] = kparams.get('critical value of w', '')
    M.raw['min_redundancy'] = kparams.get('minimum redundancy after a removal', '')
    M.raw['max_removals'] = kparams.get('maximum removals per component', '')
    M.critical_w = _dec_num(M.raw['critical_w'])
    M.min_redundancy = int(_dec_num(kparams.get('minimum redundancy after a removal')
                                   or 0) or 0)
    M.max_removals = int(_dec_num(kparams.get('maximum removals per component') or 0) or 0)

    # Table R-1
    t = inforce('R-1')
    rparams = {}
    if t:
        for rec in table_records(t):
            rparams[rec.get('parameter', '').strip().lower()] = rec.get('value', '').strip()
    M.raw['alert'] = rparams.get('alert rate mm per yr', '')
    M.raw['k_rate'] = rparams.get('significance factor', '')
    M.alert_rate = _dec_num(M.raw['alert'])
    M.k_rate = _dec_num(M.raw['k_rate'])

    # Table T-1 (tolerances)
    t = inforce('T-1')
    M.tol_section = {}
    M.tol_loop = {}
    if t:
        hdr = [h.strip().lower() for h in (t.get('header') or [])]
        sc = next((i for i, h in enumerate(hdr) if 'section' in h), 1)
        lc = next((i for i, h in enumerate(hdr) if 'loop' in h), 2)
        for rec in table_records(t):
            cells = rec['__cells__']
            cls = cells[0].strip().upper()
            if cls in ('I', 'II', 'III'):
                stxt = cells[sc] if sc < len(cells) else ''
                ltxt = cells[lc] if lc < len(cells) else ''
                M.tol_section[cls] = _dec_num(stxt)
                M.tol_loop[cls] = _dec_num(ltxt)
                M.raw.setdefault('tol_section', {})[cls] = stxt
                M.raw.setdefault('tol_loop', {})[cls] = ltxt

    # Table A-1 (rod types)
    t = inforce('A-1')
    M.graduation = {}
    M.alpha = {}
    if t:
        for rec in table_records(t):
            cells = rec['__cells__']
            typ = cells[0].strip().upper()
            if typ:
                M.graduation[typ] = (cells[1] if len(cells) > 1 else '').strip().upper()
                atxt = cells[2] if len(cells) > 2 else ''
                M.alpha[typ] = _dec_num(atxt)
                M.raw.setdefault('alpha', {})[typ] = atxt

    # Table C-2 (control heights)
    t = inforce('C-2')
    M.control = {}
    if t:
        for rec in table_records(t):
            cells = rec['__cells__']
            mark = cells[0].strip()
            if mark:
                v = _dec_num(cells[1] if len(cells) > 1 else '')
                if v is not None:
                    M.control[mark] = v

    # Table X-2 (chi-square bounds)
    t = inforce('X-2')
    M.chi2 = {}
    if t:
        for rec in table_records(t):
            cells = rec['__cells__']
            try:
                df = int(cells[0].strip())
            except Exception:
                continue
            try:
                lo = _dec_num(cells[1])
                hi = _dec_num(cells[2])
            except Exception:
                continue
            if lo is not None and hi is not None:
                M.chi2[df] = (lo, hi)

    # Table J-1 (rulings)
    t = inforce('J-1')
    M.rulings = []
    if t:
        for rec in table_records(t):
            cells = rec['__cells__']
            if len(cells) >= 4 and cells[0].strip():
                M.rulings.append({'id': cells[0].strip(), 'target': cells[1].strip(),
                                  'action': cells[2].strip().upper(),
                                  'effective': cells[3].strip()})

    # errata
    M.errata = errata
    for text in errata:
        m = re.search(r'Table\s+([A-Z]-\d+)', text)
        if not m:
            continue
        tid = m.group(1)
        tab = tables.get(tid)
        if tab is None:
            continue
        mv = re.search(r'\bfor\s+(-?[\d.]+)\s+read\s+(-?[\d.]+)\b', text)
        if not mv:
            continue
        old, new = mv.group(1), mv.group(2)
        target_col = None
        if re.search(r'section\s+column', text, re.I):
            hdr = [h.strip().lower() for h in (tab.get('header') or [])]
            for i, h in enumerate(hdr):
                if 'section' in h:
                    target_col = i
        elif re.search(r'loop\s+column', text, re.I):
            hdr = [h.strip().lower() for h in (tab.get('header') or [])]
            for i, h in enumerate(hdr):
                if 'loop' in h:
                    target_col = i
        # target row
        mk = re.search(r'\b((?:VD|MB)-?\s?\d{1,4})\b', text)
        clsm = re.search(r'\bclass\s+(I{1,3}|IV)\b', text, re.I)
        key = None
        if tid == 'C-2' and mk:
            key = norm_token(mk.group(1))
        elif tid in ('T-0', 'T-1') and clsm:
            key = clsm.group(1).upper()
        if tid == 'C-2' and key is not None:
            if key in M.control and fmt(M.control[key], 5) == fmt(_dec_num(old), 5):
                M.control[key] = _dec_num(new)
        elif tid in ('T-0', 'T-1') and key is not None and target_col is not None:
            if target_col == 1 and key in M.tol_section:
                if fmt(M.tol_section[key], 3) == fmt(_dec_num(old), 3):
                    M.tol_section[key] = _dec_num(new)
                    M.raw['tol_section'][key] = new
            elif target_col == 2 and key in M.tol_loop:
                if fmt(M.tol_loop[key], 3) == fmt(_dec_num(old), 3):
                    M.tol_loop[key] = _dec_num(new)
                    M.raw['tol_loop'][key] = new
    return M


def bulletin_notices(C):
    """Parse IN FORCE OPERATIONAL NOTICE entries of the campaign."""
    out = []
    text = getattr(C, 'bulletin', '')
    campaign = C.profile.get('campaign_id')
    blocks = re.split(r'\n\s*\n', text)
    for b in blocks:
        if 'OPERATIONAL NOTICE' not in b:
            continue
        st = re.search(r'^status:\s*(.+)$', b, re.M)
        camp = re.search(r'^campaign:\s*(.+)$', b, re.M)
        if not st or not camp:
            continue
        if st.group(1).strip().upper() != 'IN FORCE':
            continue
        if camp.group(1).strip() != campaign:
            continue
        m = re.search(r'met station\s+(.+?)\s+offline from (\S+) to (\S+)', b)
        sub = re.search(r'^substitute station:\s*(.+)$', b, re.M)
        if m and sub:
            out.append({'station': m.group(1).strip(),
                        'from': parse_date(m.group(2)),
                        'to': parse_date(m.group(3)),
                        'substitute': sub.group(1).strip()})
    return out


def runpack_settings(C):
    """Read the settings block of the saved run pack (for reconciliation only)."""
    text = getattr(C, 'runpack', '')
    out = []
    m = re.search(r'##\s*Settings\s*\n+```(.*?)```', text, re.S)
    body = m.group(1) if m else text
    for line in body.splitlines():
        line = line.strip()
        if not line or ':' not in line or line.startswith('#'):
            continue
        k, v = line.split(':', 1)
        out.append((k.strip(), v.strip()))
    return out


def resolve_token(C, token, d):
    """H13 token resolution. Returns (mark or '', hops)."""
    cur = norm_token(token)
    hops = 0
    seen = set()
    while True:
        if cur in seen:
            break
        seen.add(cur)
        rows = []
        for tok, canon, vf, vt in C.bm_alias:
            if tok != cur:
                continue
            vf_d = parse_date(vf)
            vt_d = parse_date(vt)
            if vf_d is None:
                continue
            if vf_d > d:
                continue
            if vt is not None and str(vt).strip() != '' and vt_d is not None and vt_d <= d:
                continue
            rows.append((vf_d, canon))
        if not rows:
            break
        rows.sort(key=lambda r: r[0])
        cur = rows[-1][1]
        hops += 1
    if cur in C.bm_master:
        return cur, hops
    return '', hops


class Engine:
    pass


def build_engine(C, M):
    E = Engine()
    E.C = C
    E.M = M
    P = C.profile
    E.campaign = str(P.get('campaign_id'))
    E.ref_date = parse_date(str(P.get('reference_date')))
    E.clock = SiteClock(getattr(C, 'clock', None))

    # overlay
    E.sheet = str(P.get('rod_certificate_sheet') or '')
    E.fallback = _dec_num(P.get('fallback_temp_c'))
    E.gap_min = _dec_num(P.get('met_max_gap_min'))
    E.fallback_text = _setting_text(P.get('fallback_temp_c'))
    E.gap_min_text = _setting_text(P.get('met_max_gap_min'))
    E.epoch_ref = str(P.get('epoch_reference') or '')
    for ent in (C.overlay or {}).get('overlay', []) or []:
        if str(ent.get('campaign')) != E.campaign:
            continue
        eff = parse_date(str(ent.get('effective')))
        if eff is None or eff > E.ref_date:
            continue
        key = str(ent.get('key'))
        val = ent.get('value')
        if key == 'rod_certificate_sheet':
            E.sheet = str(val)
        elif key == 'fallback_temp_c':
            E.fallback = _dec_num(val)
            E.fallback_text = _setting_text(val)
        elif key == 'met_max_gap_min':
            E.gap_min = _dec_num(val)
            E.gap_min_text = _setting_text(val)

    # workbook
    wb = xlsx_sheets(os.path.join(C.data_dir, C.workbook_path))
    E.date1904 = wb.get('__date1904__')
    rods = xlsx_table(wb.get('Rods') or [], 'serial')
    E.rod_type = {}
    E.former = {}
    for r in rods:
        s = (str(r.get('serial') or '').strip())
        if not s:
            continue
        E.rod_type[s] = (str(r.get('type') or '').strip().upper())
        fs = (str(r.get('former_serial') or '').strip())
        if fs:
            E.former[fs] = s
    for r in C.legacy_rods:
        s = str(r.get('serial') or '').strip()
        if s and s not in E.rod_type:
            E.rod_type[s] = str(r.get('type') or '').strip().upper()
    E.rod_half = {s: M.graduation.get(t) == 'HALF' for s, t in E.rod_type.items()}
    certs = xlsx_table(wb.get(E.sheet) or [], 'rod_serial')
    E.certs = []
    for r in certs:
        vf = _wb_date(r.get('valid_from'), E.date1904)
        vt = _wb_date(r.get('valid_to'), E.date1904)
        E.certs.append({'serial': (str(r.get('rod_serial') or '').strip()),
                        'cert': (str(r.get('certificate') or '').strip()),
                        'scale': _dec_num(r.get('scale_ppm')),
                        't0': _dec_num(r.get('t0_c')),
                        'from': vf, 'to': vt})

    # rod pairs from the profile
    E.rod_pairs = {}
    for pid, pair in (P.get('rod_pairs') or {}).items():
        toks = [str(t) for t in (pair or [])]
        if len(toks) >= 2:
            a = rod_serial(toks[0])
            b = rod_serial(toks[1])
            a = E.former.get(a, a) if a else a
            b = E.former.get(b, b) if b else b
            E.rod_pairs[str(pid)] = (a, b)

    # run register
    E.runs = {}
    for r in C.run_register:
        if str(r.get('campaign')).strip() != E.campaign:
            continue
        rid = norm_run_id(r.get('run_id'))
        E.runs[rid] = {
            'run_id': rid,
            'start_bm': (r.get('start_bm') or '').strip(),
            'end_bm': (r.get('end_bm') or '').strip(),
            'booked': (r.get('booked') or '').strip(),
            'level': (r.get('level') or '').strip(),
            'pair': (r.get('pair') or '').strip(),
            'observer': (r.get('observer') or '').strip(),
            'setups': _dec_num(r.get('setups')),
            'status': (r.get('status') or '').strip(),
        }
    E.run_pair = {rid: v['pair'] for rid, v in E.runs.items()}
    for a in sorted((a for a in C.amendments if str(a.get('campaign')) == E.campaign),
                    key=lambda a: (a.get('amend_no') if isinstance(a.get('amend_no'), int)
                                   else 0)):
        rid = norm_run_id(a.get('run'))
        if rid not in E.runs:
            continue
        fld = str(a.get('field')).strip()
        val = a.get('value')
        if fld == 'status':
            E.runs[rid]['status'] = str(val).strip()
        elif fld == 'setups':
            E.runs[rid]['setups'] = _dec_num(val)
        elif fld == 'level':
            E.runs[rid]['level'] = str(val).strip()
        elif fld == 'observer':
            E.runs[rid]['observer'] = str(val).strip()

    # sections
    E.sections = []
    for s in C.sections:
        if str(s.get('status')).strip().upper() != 'ACTIVE':
            continue
        E.sections.append({'section_id': s['section_id'].strip(),
                           'from': s['from_mark'].strip(),
                           'to': s['to_mark'].strip(),
                           'line': s['line_id'].strip(),
                           'raw_status': s.get('status', '')})
    E.lines = {}
    for l in C.lines:
        E.lines[l.get('line')] = l

    # stations
    E.station_by_id = {}
    E.station_tokens = {}
    for s in C.stations:
        sid = (s.get('station_id') or '').strip()
        toks = [t.strip() for t in (s.get('tokens') or '').split(';') if t.strip()]
        rec = {'id': sid, 'tokens': toks, 'log': (s.get('log_file') or '').strip(),
               'unit': (s.get('unit') or '').strip(),
               'status': (s.get('status') or '').strip()}
        E.station_by_id[sid.upper()] = rec
        for t in toks:
            E.station_tokens.setdefault(t.upper(), rec)
    E.line_stations = P.get('line_stations') or {}
    E.notices = bulletin_notices(C)
    E.station_logs = {}
    for name in C.log_files:
        E.station_logs[name] = load_station_log(os.path.join(C.data_dir, name), E)

    # roster
    E.roster = []
    for o in C.roster:
        E.roster.append({'observer': str(o.get('observer') or '').strip().upper(),
                         'from': parse_date(str(o.get('valid_from'))),
                         'to': parse_date(str(o.get('valid_to')))})
    # instrument alias / tests
    E.instr = {}
    for k, v in C.instrument_alias.items():
        E.instr[k.upper()] = v
    E.tests = []
    for t in C.two_peg:
        E.tests.append({'test_id': t['test_id'], 'instrument': t['instrument'],
                        'utc': parse_instant(t['tested_utc'], None, 'iso'),
                        'c': _dec_num(t['c']), 'result': (t['result'] or '').strip().upper()})

    # rulings
    E.cancelled_rulings = set()
    E.rejected_runs = set()
    E.rejected_sections = set()
    for r in C.addendum:
        if str(r.get('campaign')).strip() != E.campaign:
            continue
        issued = parse_date(r.get('issued'))
        if issued is None or issued > E.ref_date:
            continue
        action = str(r.get('action')).strip().upper()
        target = str(r.get('target')).strip()
        if action == 'CANCEL':
            E.cancelled_rulings.add(target)
        elif action == 'REJECT_RUN':
            E.rejected_runs.add(target)
        elif action == 'REJECT_SECTION':
            E.rejected_sections.add(target)
    for r in M.rulings:
        eff = parse_date(r['effective'])
        if eff is None or eff > E.ref_date:
            continue
        if r['id'] in E.cancelled_rulings:
            continue
        if r['action'] == 'REJECT_RUN':
            E.rejected_runs.add(r['target'])
        elif r['action'] == 'REJECT_SECTION':
            E.rejected_sections.add(r['target'])

    # journal replay
    E.journal = []
    entries = []
    for e in C.journal:
        try:
            eid = int(e.get('id'))
        except Exception:
            continue
        entries.append((eid, e))
    entries.sort(key=lambda x: x[0])
    cancelled = set()
    for eid, e in entries:
        if str(e.get('event')).strip().upper() == 'ERRATUM':
            try:
                cancelled.add(int(e.get('refers')))
            except Exception:
                pass
    for eid, e in entries:
        if eid in cancelled:
            continue
        ev = str(e.get('event') or '').strip().upper()
        if ev == 'ERRATUM':
            continue
        E.journal.append({'id': eid, 'mark': (e.get('mark') or '').strip(),
                          'event': ev,
                          'date': parse_date(e.get('date'))})
    return E


def _setting_text(v):
    """Text of a profile/overlay setting as written."""
    if v is None:
        return ''
    if isinstance(v, str):
        return v
    if isinstance(v, float):
        return repr(v)
    return str(v)


def _wb_date(v, date1904):
    s = (str(v).strip() if v is not None else '')
    if s == '':
        return None
    if re.match(r'^-?\d+(\.0)?$', s):
        n = int(float(s))
        base = date(1904, 1, 1) if date1904 else date(1899, 12, 30)
        return base + timedelta(days=n)
    d = parse_date(s)
    if d is None:
        return None
    return d


def load_station_log(path, E):
    """Return a sorted list of (epoch_seconds, temp_degC) for a log file."""
    name = os.path.basename(path)
    unit = None
    for st in E.station_by_id.values():
        if os.path.basename(st['log']) == name:
            unit = st['unit']
            break
    rows = []
    if unit is None:
        for st in E.station_by_id.values():
            rows = []
            break
    text = open(path, encoding='utf-8-sig').read()
    first = _first_meaningful(text)
    fml = first.lower()
    kind = None
    if re.match(r'^epoch_s\s*,\s*temp_c', fml):
        kind = 'epoch_degC'
    elif re.match(r'^utc\s+temp', fml):
        kind = 'iso_degF'
    elif text.lstrip().startswith('{') and '"ta"' in text[:200]:
        kind = 'local_tenths'
    if kind is None:
        return None
    if kind == 'epoch_degC':
        for r in table_from_rows(read_delim(path, ',')):
            ep = r.get('epoch_s')
            tc = r.get('temp_c')
            if ep == '' or ep is None:
                continue
            try:
                t = int(float(ep))
            except Exception:
                continue
            f = _dec_num(tc)
            if f is None:
                continue
            rows.append((t, f))
    elif kind == 'iso_degF':
        for r in table_from_rows(read_delim(path, '\t')):
            utc = (r.get('utc') or '').strip()
            temp = (r.get('temp') or '').strip()
            if not utc:
                continue
            try:
                dt = parse_instant(utc, None, 'iso')
            except Exception:
                continue
            f = _dec_num(temp)
            if f is None:
                continue
            rows.append((int((dt - _EPOCH).total_seconds()), (f - 32) * Fraction(5, 9)))
    else:
        for o in load_jsonl(path):
            try:
                dt = parse_instant(str(o.get('t')), None, 'iso')
            except Exception:
                continue
            ta = _dec_num(o.get('ta'))
            if ta is None:
                continue
            rows.append((int((dt - _EPOCH).total_seconds()), ta / 10))
    rows.sort(key=lambda r: r[0])
    return rows


def card_radius(C):
    m = re.search(r'mean\s+earth\s+radius\s+R\s*[.*\s]*([0-9]+(?:\.[0-9]+)?)\s*m',
                  getattr(C, 'card', ''))
    if m:
        return _dec_num(m.group(1)), m.group(1)
    return Fraction(6371000), '6371000'


class CertUse:
    pass


def compute(E):
    C = E.C
    M = E.M
    O = {}
    E.radius, E.radius_text = card_radius(C)

    # ---- catalog ---------------------------------------------------------
    entries = []
    for e in (C.catalog or {}).get('entries', []):
        if str(e.get('campaign')).strip() == E.campaign:
            entries.append(e)
    read_entries = [e for e in entries if str(e.get('status')).strip().upper() == 'ACTIVE']
    read_names = []
    for e in read_entries:
        nm = str(e.get('file') or '').strip()
        if os.path.isfile(os.path.join(C.data_dir, nm)) and nm not in read_names:
            read_names.append(nm)
    E.findex_of = {nm: i for i, nm in enumerate(read_names)}

    # read shards
    all_recs = []
    per_file = {}
    for i, nm in enumerate(read_names):
        layout = None
        for e in read_entries:
            if str(e.get('file')).strip() == nm:
                layout = str(e.get('layout')).strip()
                break
        recs = read_shard(os.path.join(C.data_dir, nm), layout, E)
        per_file[nm] = {'records': len(recs), 'kept': 0, 'superseded': 0,
                        'void_selected': 0, 'duplicates': 0, 'conflicts_lost': 0,
                        'status': 'READ'}
        for r in recs:
            r.findex = i
        all_recs.extend(recs)

    # ---- settlement (H5) -------------------------------------------------
    groups = {}
    for r in all_recs:
        groups.setdefault((r.run, r.seq), []).append(r)
    O['records_read'] = len(all_recs)
    O['setup_keys'] = len(groups)
    superseded = 0
    duplicates = 0
    conflicts = 0
    kept_setups = {}
    void_setups = []
    for key, rs in groups.items():
        maxrev = max(r.rev for r in rs)
        comp = [r for r in rs if r.rev == maxrev]
        for r in rs:
            if r.rev < maxrev:
                r.state = 'superseded'
                per_file[r.file]['superseded'] += 1
        superseded += len(rs) - len(comp)
        same = all(r.content == comp[0].content for r in comp)
        winner = min(comp, key=lambda r: (r.findex, r.rindex))
        for r in comp:
            if r is winner:
                continue
            if same or r.content == winner.content:
                r.state = 'duplicate'
                per_file[r.file]['duplicates'] += 1
                duplicates += 1
            else:
                r.state = 'conflict'
                per_file[r.file]['conflicts_lost'] += 1
                conflicts += 1
        winner.state = 'void' if winner.void else 'kept'
        if winner.void:
            per_file[winner.file]['void_selected'] += 1
            void_setups.append(key)
        else:
            per_file[winner.file]['kept'] += 1
            kept_setups[key] = winner
    O['superseded_revisions'] = superseded
    O['duplicates'] = duplicates
    O['conflicts'] = conflicts

    # ignored setup shards
    camp_status = {}
    for e in entries:
        nm = str(e.get('file') or '').strip()
        camp_status[nm] = str(e.get('status')).strip().upper()
    ignored = []
    for nm in C.files:
        if nm in read_names:
            continue
        path = os.path.join(C.data_dir, nm)
        if not os.path.isfile(path):
            continue
        lay = sniff_layout(path)
        if lay is None:
            continue
        ignored.append(nm)
        per_file[nm] = {'records': 0, 'kept': 0, 'superseded': 0, 'void_selected': 0,
                        'duplicates': 0, 'conflicts_lost': 0,
                        'status': 'RETIRED' if camp_status.get(nm) == 'RETIRED'
                        else 'UNCATALOGUED'}
    O['files_read'] = len(read_names)
    O['files_ignored'] = sorted(ignored)
    O['lineage'] = [dict(per_file[nm], file=nm) for nm in
                    read_names + sorted(ignored)]

    # ---- benchmark resolution log ---------------------------------------
    resolutions = {}

    def resolve(ctxname, token, d):
        key = (ctxname, str(token), d.isoformat() if d else '')
        if key in resolutions:
            return resolutions[key]
        mark, hops = resolve_token(C, token, d)
        resolutions[key] = {'context': ctxname, 'token': str(token),
                            'resolve_date': d.isoformat() if d else '',
                            'mark': mark, 'hops': hops,
                            'status': 'RESOLVED' if mark else 'UNRESOLVED'}
        return resolutions[key]

    # ---- sections: classes ----------------------------------------------
    for s in E.sections:
        line = E.lines.get(s['line']) or {}
        best = None
        for ch in line.get('class_history') or []:
            f = parse_date(str(ch.get('from')))
            if f is None:
                continue
            if f <= E.ref_date and (best is None or f >= best[0]):
                best = (f, str(ch.get('class')).strip().upper())
        s['class'] = best[1] if best else ''
        s['from_mark'] = resolve_token(C, s['from'], E.ref_date)[0]
        s['to_mark'] = resolve_token(C, s['to'], E.ref_date)[0]

    O['sections'] = E.sections
    O['resolutions'] = resolutions
    O['resolve'] = resolve
    O['kept_setups'] = len(kept_setups)
    O['void_setups'] = len(void_setups)
    O['kept_setup_map'] = kept_setups
    O['void_setup_keys'] = void_setups
    O['per_file'] = per_file
    O['read_names'] = read_names

    # ---- runs ------------------------------------------------------------
    section_of_pair = {}
    for s in E.sections:
        section_of_pair.setdefault((s['from_mark'], s['to_mark']), []).append(s)

    run_results = {}
    cert_cache = {}

    def cert_of(serial, d):
        key = (serial, d)
        if key in cert_cache:
            return cert_cache[key]
        best = None
        for c in E.certs:
            if c['serial'] != serial:
                continue
            if c['from'] is None or c['from'] > d:
                continue
            if c['to'] is not None and c['to'] < d:
                continue
            if best is None or c['from'] > best['from']:
                best = c
        cert_cache[key] = best
        return best

    def effective_test(instr_token, instant):
        tok = re.sub(r'\s+', ' ', str(instr_token or '').strip().upper())
        inst = E.instr.get(tok)
        if inst is None:
            for k, v in E.instr.items():
                if k.replace(' ', '') == tok.replace(' ', ''):
                    inst = v
                    break
        if inst is None:
            return None
        best = None
        for t in E.tests:
            if t['instrument'] != inst:
                continue
            if t['result'] == 'RETEST':
                continue
            if t['utc'] > instant:
                continue
            if best is None or (t['utc'], t['test_id']) > (best['utc'], best['test_id']):
                best = t
        return best

    for rid in sorted(E.runs):
        R = E.runs[rid]
        rec = {'run_id': rid, 'section_id': '', 'direction': '',
               'start_mark': '', 'end_mark': '', 'run_date': '',
               'setups': 0, 'length_m': None, 'dh_m': None, 'test_id': '',
               'collimation': None, 'status': ''}
        setups = sorted(k[1] for k in kept_setups if k[0] == rid)
        rec['setups'] = len(setups)
        kept = [kept_setups[(rid, sq)] for sq in setups]
        earliest = None
        for r in kept:
            if r.instant is not None and (earliest is None or r.instant < earliest):
                earliest = r.instant
        run_date = None
        if earliest is not None:
            run_date = local_date(earliest, E.clock)
        R['run_date'] = run_date
        R['earliest'] = earliest
        R['kept'] = kept

    # per run processing
    for rid in sorted(E.runs):
        R = E.runs[rid]
        rec = {'run_id': rid, 'section_id': '', 'direction': '',
               'start_mark': '', 'end_mark': '', 'run_date': '',
               'setups': len(R['kept']), 'length_m': None, 'dh_m': None,
               'test_id': '', 'collimation': None, 'status': ''}
        run_date = R['run_date']
        if run_date:
            rec['run_date'] = run_date.isoformat()
        test_found = None
        if R['kept'] and R.get('earliest') is not None:
            test_found = effective_test(R['level'], R['earliest'])
        status = None
        if str(R['status']).strip().upper() == 'VOID':
            status = 'VOID'
        elif not R['kept']:
            status = 'NO_SETUPS'
        else:
            sm = resolve('run', R['start_bm'], run_date)
            em = resolve('run', R['end_bm'], run_date)
            rec['start_mark'] = sm['mark']
            rec['end_mark'] = em['mark']
            if not sm['mark'] or not em['mark']:
                status = 'UNRESOLVED_BM'
            else:
                sec = None
                direction = ''
                cands = section_of_pair.get((sm['mark'], em['mark']), [])
                if cands:
                    sec = sorted(cands, key=lambda s: s['section_id'])[0]
                    direction = 'F'
                else:
                    cands = section_of_pair.get((em['mark'], sm['mark']), [])
                    if cands:
                        sec = sorted(cands, key=lambda s: s['section_id'])[0]
                        direction = 'B'
                if sec is None:
                    status = 'UNKNOWN_SECTION'
                else:
                    rec['section_id'] = sec['section_id']
                    rec['direction'] = direction
                    R['section'] = sec
                    nsetups = R['setups']
                    nsetups = int(nsetups) if nsetups is not None else None
                    got = sorted(r.seq for r in R['kept'])
                    if nsetups is None or got != list(range(1, nsetups + 1)):
                        status = 'SEQUENCE_GAP'
                    else:
                        obs_ok = False
                        for o in E.roster:
                            if o['observer'] == R['observer'].strip().upper() and \
                                    o['from'] and o['to'] and \
                                    o['from'] <= run_date <= o['to']:
                                obs_ok = True
                                break
                        if not obs_ok:
                            status = 'UNCERTIFIED_OBSERVER'
                        else:
                            test = test_found
                            if test is None:
                                status = 'NO_TEST'
                            else:
                                rec['test_id'] = str(test['test_id'])
                                rec['collimation'] = test['c']
                                R['test'] = test
                                if abs(test['c']) > M.collimation_limit:
                                    status = 'INVALID_COLLIMATION'
                                else:
                                    nocert = False
                                    for r in R['kept']:
                                        for s in (r.back_rod, r.fore_rod):
                                            ser = E.former.get(s, s)
                                            if cert_of(ser, run_date) is None:
                                                nocert = True
                                    if nocert:
                                        status = 'NO_CERTIFICATE'
                                    elif rid in E.rejected_runs:
                                        status = 'RULED_OUT'
                                    else:
                                        status = 'VALID'
        if status is None:
            status = 'VALID' if str(R['status']).strip().upper() != 'VOID' else 'VOID'
        if status == 'VOID' and not R['kept']:
            rec['run_date'] = ''
        if status in ('VOID', 'NO_SETUPS'):
            rec['start_mark'] = ''
            rec['end_mark'] = ''
            rec['section_id'] = ''
            rec['direction'] = ''
            rec['run_date'] = ''
            rec['setups'] = len(R['kept'])
        if test_found is not None and not rec['test_id']:
            rec['test_id'] = str(test_found['test_id'])
            rec['collimation'] = test_found['c']
            if status in ('UNRESOLVED_BM',):
                sm = resolve('run', R['start_bm'], run_date)
                em = resolve('run', R['end_bm'], run_date)
                rec['start_mark'] = sm['mark']
                rec['end_mark'] = em['mark']
                if rec['start_mark'] or rec['end_mark']:
                    sec = None
                    direction = ''
                    cands = section_of_pair.get((rec['start_mark'], rec['end_mark']), [])
                    if cands:
                        sec = sorted(cands, key=lambda s: s['section_id'])[0]
                        direction = 'F'
                    else:
                        cands = section_of_pair.get((rec['end_mark'], rec['start_mark']), [])
                        if cands:
                            sec = sorted(cands, key=lambda s: s['section_id'])[0]
                            direction = 'B'
                    if sec is not None:
                        rec['section_id'] = sec['section_id']
                        rec['direction'] = direction
        rec['status'] = status
        R['status_final'] = status
        R['rec'] = rec
        run_results[rid] = rec
    O['runs'] = run_results

    # ---- temperatures and reductions (H11, H12) ---------------------------
    log_cache = {}

    def station_log(station):
        key = station.get('id')
        if key in log_cache:
            return log_cache[key]
        base = os.path.basename(station.get('log') or '')
        rows = E.station_logs.get(base)
        if rows is None:
            for nm, rws in E.station_logs.items():
                if nm == base:
                    rows = rws
                    break
        log_cache[key] = rows
        return rows

    def find_station(token):
        t = str(token).strip()
        rec = E.station_by_id.get(t.upper())
        if rec is None:
            rec = E.station_tokens.get(t.upper())
        return rec

    def met_temp(line_id, instant):
        """Return (temp Fraction or None, station used or None)."""
        sdate = local_date(instant, E.clock)
        lst = E.line_stations.get(line_id) or []
        best = None
        for ent in lst:
            f = parse_date(str(ent.get('from')))
            if f is None:
                continue
            if f <= sdate and (best is None or f >= best[0]):
                best = (f, str(ent.get('station')))
        if best is None:
            return None, None
        st = find_station(best[1])
        if st is None:
            return None, None
        for nt in E.notices:
            tok = re.split(r'\s*\(', nt['station'].strip(), 1)[0].strip()
            nst = find_station(tok)
            if nst is not None and nst.get('id') == st.get('id') and \
                    nt['from'] and nt['to'] and nt['from'] <= sdate <= nt['to']:
                sub = find_station(nt['substitute'])
                if sub is not None:
                    st = sub
                break
        rows = station_log(st)
        if not rows:
            return None, st
        ep = int((instant - _EPOCH).total_seconds())
        lo = None
        hi = None
        import bisect
        times = [r[0] for r in rows]
        i = bisect.bisect_right(times, ep)
        if i > 0:
            lo = rows[i - 1]
        if i < len(rows):
            hi = rows[i]
        if lo is None or hi is None:
            return None, st
        if (hi[0] - lo[0]) > int(E.gap_min * 60):
            return None, st
        if lo[0] == hi[0]:
            t = lo[1]
        else:
            t = lo[1] + (hi[1] - lo[1]) * Fraction(ep - lo[0], hi[0] - lo[0])
        return t, st

    cert_use = {}
    ledger = []
    k = M.refraction
    R_earth = E.radius
    for rid in sorted(E.runs):
        R = E.runs[rid]
        if R['status_final'] != 'VALID':
            continue
        c = R['test']['c']
        line_id = R['section']['line']
        total_dh = Fraction(0)
        total_len = Fraction(0)
        for r in R['kept']:
            if r.temp is not None:
                T = r.temp
                src = 'FIELD'
            else:
                T, _st = met_temp(line_id, r.instant)
                if T is None:
                    T = E.fallback
                    src = 'FALLBACK'
                else:
                    T = Fraction(round_scaled(T, 10), 10)
                    src = 'MET'
            parts = []
            for (rd, dist, serial) in ((r.back_m, r.back_d, r.back_rod),
                                       (r.fore_m, r.fore_d, r.fore_rod)):
                if rd is None or dist is None:
                    raise AssertionError('missing reading %s %s %r' % (rid, r.seq, r.content))
                ser = E.former.get(serial, serial)
                cert = cert_of(ser, R['run_date'])
                typ = E.rod_type.get(ser)
                alpha = M.alpha.get(typ, Fraction(0))
                s = cert['scale']
                t0 = cert['t0']
                rc = rd * (1 + s * Fraction(1, 1000000)
                           + alpha * Fraction(1, 1000000) * (T - t0)) \
                    - c * dist / 100000 \
                    - (1 - k) * dist * dist / (2 * R_earth)
                parts.append(rc)
                ukey = (ser, cert['cert'])
                if ukey not in cert_use:
                    cert_use[ukey] = {'serial': ser, 'type': typ, 'cert': cert,
                                      'readings': 0}
                cert_use[ukey]['readings'] += 1
            dh = parts[0] - parts[1]
            dh_r = Fraction(round_scaled(dh, 100000), 100000)
            raw = r.back_m - r.fore_m
            total_dh += dh_r
            total_len += (r.back_d or 0) + (r.fore_d or 0)
            ledger.append({
                'run_id': rid, 'seq': r.seq, 'instant_utc': fmt_instant(r.instant),
                'back_rod': E.former.get(r.back_rod, r.back_rod),
                'fore_rod': E.former.get(r.fore_rod, r.fore_rod),
                'back_m': fmt(r.back_m, 5), 'fore_m': fmt(r.fore_m, 5),
                'back_dist_m': fmt(r.back_d, 1), 'fore_dist_m': fmt(r.fore_d, 1),
                'temp_c': fmt(T, 1), 'temp_source': src,
                'dh_raw_m': fmt(raw, 5), 'dh_m': fmt(dh_r, 5),
                '_dh': dh_r,
            })
        R['rec']['length_m'] = fmt(total_len, 1)
        R['rec']['dh_m'] = fmt(total_dh, 5)
        R['total_dh'] = total_dh
        R['total_len'] = total_len
    ledger.sort(key=lambda x: (x['run_id'], x['seq']))
    O['ledger'] = ledger
    O['cert_use'] = cert_use

    # ---- sections (H14) ---------------------------------------------------
    runs_by_section = {}
    for rid, R in E.runs.items():
        if R['status_final'] != 'VALID':
            continue
        sid = R['rec']['section_id']
        if not sid:
            continue
        runs_by_section.setdefault(sid, []).append(R)

    section_results = []
    for s in E.sections:
        sid = s['section_id']
        fwd = sorted([R for R in runs_by_section.get(sid, [])
                      if R['rec']['direction'] == 'F'], key=lambda R: R['run_id'])
        bwd = sorted([R for R in runs_by_section.get(sid, [])
                      if R['rec']['direction'] == 'B'], key=lambda R: R['run_id'])
        cls = s['class']
        tol = M.tol_section.get(cls, Fraction(0))
        res = {'section_id': sid, 'from_mark': s['from'], 'to_mark': s['to'],
               'line_id': s['line'], 'class': cls,
               'forward_run': '', 'backward_run': '', 'dh_forward_m': '',
               'dh_backward_m': '', 'discrepancy_mm': '', 'length_km': '',
               'tolerance_mm': '', 'candidates': len(fwd) * len(bwd),
               'status': '', 'value_m': ''}
        if sid in E.rejected_sections:
            res['status'] = 'RULED_OUT'
        elif not fwd or not bwd:
            res['status'] = 'INCOMPLETE'
        else:
            cands = []
            for f in fwd:
                for b in bwd:
                    d = f['total_dh'] + b['total_dh']
                    K = (f['total_len'] + b['total_len']) / 2000
                    ok = (d * 1000) ** 2 <= tol ** 2 * K
                    later = max(f['run_date'], b['run_date'])
                    cands.append({'f': f, 'b': b, 'd': d, 'K': K,
                                  'ok': ok, 'later': later})
            res['candidates'] = len(cands)
            good = [c for c in cands if c['ok']]
            if not good:
                res['status'] = 'REJECTED_TOLERANCE'
            else:
                best = min(good, key=lambda c: (abs(c['d']), -c['later'].toordinal(),
                                                c['f']['run_id'], c['b']['run_id']))
                f = best['f']
                b = best['b']
                val = (f['total_dh'] - b['total_dh']) / 2
                val = Fraction(round_scaled(val, 100000), 100000)
                res['forward_run'] = f['run_id']
                res['backward_run'] = b['run_id']
                res['dh_forward_m'] = fmt(f['total_dh'], 5)
                res['dh_backward_m'] = fmt(b['total_dh'], 5)
                res['discrepancy_mm'] = fmt(best['d'] * 1000, 2)
                res['length_km'] = fmt(best['K'], 5)
                res['tolerance_mm'] = fmt(tol * _sqrt(best['K']), 2)
                res['status'] = 'ACCEPTED'
                res['value_m'] = fmt(val, 5)
                s['value'] = val
                s['K'] = best['K']
                s['fwd_run'] = f
                s['bwd_run'] = b
        section_results.append(res)
    O['sections_out'] = section_results

    # ---- control points (H16) --------------------------------------------
    def journal_state():
        state = {}
        for e in E.journal:
            if e['date'] is None or e['date'] > E.ref_date:
                continue
            mk = e['mark']
            if e['event'] == 'DISTURBED':
                state[mk] = 'DISTURBED'
            elif e['event'] == 'REVERIFIED':
                state[mk] = 'SOUND'
        return state

    jstate = journal_state()
    controls = []
    fixed_marks = {}
    for tok in (C.profile.get('control_points') or []):
        res = resolve('control', tok, E.ref_date)
        c = {'token': str(tok), 'mark': res['mark'], 'status': '',
             'height_m': None}
        if not res['mark']:
            c['status'] = 'UNRESOLVED'
        elif res['mark'] not in M.control:
            c['status'] = 'NOT_IN_TABLE'
        elif jstate.get(res['mark']) == 'DISTURBED':
            c['status'] = 'DEMOTED_DISTURBED'
        else:
            c['status'] = 'FIXED'
            c['height_m'] = M.control[res['mark']]
            fixed_marks[res['mark']] = M.control[res['mark']]
        controls.append(c)
    O['controls'] = controls
    O['fixed_marks'] = fixed_marks

    # ---- adjustment (H17, H18) -------------------------------------------
    accepted = [s for s in E.sections if 'value' in s]
    parent = {}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    comp_of = {}
    for s in accepted:
        for mk in (s['from_mark'], s['to_mark']):
            if mk not in parent:
                parent[mk] = mk
    for s in accepted:
        union(s['from_mark'], s['to_mark'])
    comps = {}
    for mk in parent:
        comps.setdefault(find(mk), []).append(mk)
    comp_names = {}
    for root, marks in comps.items():
        name = min(marks)
        comp_names[root] = name
    comp_list = []
    for root, marks in comps.items():
        comp_list.append((comp_names[root], root, sorted(marks)))
    comp_list.sort(key=lambda x: x[0])

    iterations_out = []
    residuals_out = {}
    heights_out = []
    summary_out = []
    for name, root, marks in comp_list:
        obs = [s for s in accepted if find(s['from_mark']) == root]
        obs.sort(key=lambda s: s['section_id'])
        fixed_in = [mk for mk in marks if mk in fixed_marks]
        comp = {'component': name, 'marks': sorted(marks),
                'fixed': sorted(fixed_in)}
        if not fixed_in:
            comp['status'] = 'UNCONSTRAINED'
            comp['observations'] = len(obs)
            comp['unknowns'] = None
            comp['redundancy'] = None
            comp['removed'] = []
            comp['vtpv'] = None
            comp['s0'] = None
            comp['chi2_lower'] = None
            comp['chi2_upper'] = None
            comp['global_test'] = 'UNCONSTRAINED'
            summary_out.append(comp)
            for s in obs:
                residuals_out[s['section_id']] = {
                    'section_id': s['section_id'], 'component': name,
                    'v_mm': '', 'qvv_mm2': '', 'w': '', 'status': 'UNCONSTRAINED'}
            continue
        unknown = [mk for mk in sorted(marks) if mk not in fixed_marks]
        uidx = {mk: i for i, mk in enumerate(unknown)}
        hfix = {mk: fixed_marks[mk] * 1000 for mk in fixed_marks}
        n = len(unknown)
        rows = []
        for s in obs:
            K = s['K']
            sig = M.sigma.get(s['class'], Fraction(1))
            p = 1 / (sig * sig * K)
            fr = s['from_mark']
            to = s['to_mark']
            arow = [Fraction(0)] * n
            if fr in uidx:
                arow[uidx[fr]] -= 1
            if to in uidx:
                arow[uidx[to]] += 1
            contrib = hfix.get(to, Fraction(0)) - hfix.get(fr, Fraction(0))
            b = s['value'] * 1000 - contrib
            rows.append({'s': s, 'a': arow, 'b': b, 'p': p})
        removed = []
        it = 0
        while True:
            it += 1
            cur = [r for r in rows if r['s']['section_id'] not in removed]
            nn = len(cur)
            red = nn - n
            # normal matrix
            N = [[Fraction(0)] * n for _ in range(n)]
            rhs = [Fraction(0)] * n
            for r in cur:
                ar = r['a']
                pv = r['p'] * r['b']
                for i in range(n):
                    ai = ar[i]
                    if ai:
                        rhs[i] += ai * pv
                        for j in range(n):
                            aj = ar[j]
                            if aj:
                                N[i][j] += ai * r['p'] * aj
            Q = mat_inverse(N, n)
            x = [sum(Q[i][j] * rhs[j] for j in range(n)) for i in range(n)]
            v = {}
            qvv = {}
            vtpv = Fraction(0)
            for r in cur:
                av = sum(r['a'][j] * x[j] for j in range(n) if r['a'][j])
                vi = av - r['b']
                v[r['s']['section_id']] = vi
                vtpv += r['p'] * vi * vi
                q = r['p'] ** -1 if False else Fraction(1) / r['p']
                aq = sum(r['a'][i] * sum(Q[i][j] * r['a'][j] for j in range(n))
                         for i in range(n) if r['a'][i])
                qvv[r['s']['section_id']] = q - aq
            # test
            worst = None
            best_w2 = None
            for r in cur:
                sid = r['s']['section_id']
                q = qvv[sid]
                if q == 0:
                    continue
                w2 = (v[sid] ** 2) / q
                if best_w2 is None or w2 > best_w2[1] or (w2 == best_w2[1] and
                                                        sid < best_w2[0]):
                    best_w2 = (sid, w2)
                if w2 > M.critical_w ** 2:
                    if worst is None or w2 > worst[1] or (w2 == worst[1] and
                                                         sid < worst[0]):
                        worst = (sid, w2)
            iter_rec = {'component': name, 'iteration': it, 'observations': nn,
                        'unknowns': n, 'redundancy': red}
            iter_rec['vtpv'] = fmt(vtpv, 4)
            if best_w2 is None:
                iter_rec['max_w'] = None
                iter_rec['max_w_section'] = None
            else:
                iter_rec['max_w'] = fmt(_sqrt(best_w2[1]), 2)
                iter_rec['max_w_section'] = best_w2[0]
            if worst is None:
                action = 'STOP_CLEAN'
            elif len(removed) >= M.max_removals:
                action = 'STOP_BUDGET'
            elif (nn - 1) - n < M.min_redundancy:
                action = 'STOP_REDUNDANCY'
            else:
                action = 'REMOVE'
            iter_rec['action'] = action
            iterations_out.append(iter_rec)
            final = {'rows': cur, 'v': v, 'qvv': qvv, 'vtpv': vtpv, 'red': red,
                     'Q': Q, 'x': x, 'n': n, 'nn': nn, 'removed': list(removed)}
            if action != 'REMOVE':
                break
            removed.append(worst[0])
        # component bookkeeping
        comp['observations'] = final['nn']
        comp['unknowns'] = final['n']
        comp['redundancy'] = final['red']
        comp['removed'] = removed
        comp['vtpv'] = fmt(final['vtpv'], 4)
        if final['red'] > 0:
            comp['s0'] = fmt(_sqrt(final['vtpv'] / final['red']), 3)
            bounds = M.chi2.get(final['red'])
            comp['chi2_lower'] = fmt(bounds[0], 3) if bounds else None
            comp['chi2_upper'] = fmt(bounds[1], 3) if bounds else None
            lo = bounds[0] if bounds else None
            hi = bounds[1] if bounds else None
            if lo is not None and hi is not None and lo <= final['vtpv'] <= hi:
                comp['global_test'] = 'PASS'
            else:
                comp['global_test'] = 'FAIL'
        else:
            comp['s0'] = None
            comp['chi2_lower'] = None
            comp['chi2_upper'] = None
            comp['global_test'] = 'NO_REDUNDANCY'
        if action == 'STOP_CLEAN':
            comp['status'] = 'CLEAN' if not removed else 'SNOOPED'
        else:
            comp['status'] = action
        summary_out.append(comp)
        for mk in sorted(marks):
            if mk in fixed_marks:
                heights_out.append({'mark': mk, 'component': name,
                                   'height_m': fmt(fixed_marks[mk], 5),
                                   'sigma_mm': fmt(0, 2), 'status': 'FIXED'})
            else:
                i = uidx[mk]
                h = hfix.get(mk, Fraction(0))
                qxx = final['Q'][i][i]
                heights_out.append({'mark': mk, 'component': name,
                                   'height_m': fmt(final['x'][i] / 1000, 5),
                                   'sigma_mm': fmt(_sqrt(qxx), 2),
                                   'status': 'ADJUSTED',
                                   '_h_mm': final['x'][i], '_qxx': qxx})
        for r in final['rows']:
            sid = r['s']['section_id']
            q = final['qvv'][sid]
            if sid in removed:
                st = 'REMOVED'
                w = ''
                qq = ''
            elif q == 0:
                st = 'UNTESTABLE'
                w = ''
                qq = fmt(q, 4)
            else:
                st = 'USED'
                w = fmt(final['v'][sid] / _sqrt(q), 2)
                qq = fmt(q, 4)
            residuals_out[sid] = {'section_id': sid, 'component': name,
                                  'v_mm': fmt(final['v'][sid], 2),
                                  'qvv_mm2': qq, 'w': w, 'status': st}
        for sid in removed:
            s0 = [s for s in E.sections if s['section_id'] == sid][0]
            fr = s0['from_mark']
            to = s0['to_mark']
            hfr = final['x'][uidx[fr]] if fr in uidx else hfix[fr]
            hto = final['x'][uidx[to]] if to in uidx else hfix[to]
            rv = hto - hfr - s0['value'] * 1000
            residuals_out[sid] = {'section_id': sid, 'component': name,
                                  'v_mm': fmt(rv, 2), 'qvv_mm2': '', 'w': '',
                                  'status': 'REMOVED'}
    O['iterations'] = iterations_out
    O['residuals'] = residuals_out
    O['heights'] = heights_out
    O['summary'] = summary_out
    O['removed_all'] = []
    for comp in summary_out:
        O['removed_all'].extend(comp.get('removed') or [])

    # ---- loops (H19) ------------------------------------------------------
    sec_by_marks = {}
    for s in E.sections:
        if s.get('value') is None:
            continue
        sec_by_marks[(s['from_mark'], s['to_mark'])] = s
    loops_out = []
    for lp in (C.loops or []):
        lid = str(lp.get('id'))
        lcls = str(lp.get('class') or '').strip().upper()
        toks = [str(t) for t in (lp.get('marks') or [])]
        marks = []
        for t in toks:
            marks.append(resolve('loop', t, E.ref_date)['mark'])
        complete = True
        misc = Fraction(0)
        K = Fraction(0)
        n = len(marks)
        for i in range(n):
            a = marks[i]
            b = marks[(i + 1) % n]
            s = sec_by_marks.get((a, b))
            if s is not None:
                misc += s['value'] * 1000
                K += s['K']
            else:
                s2 = sec_by_marks.get((b, a))
                if s2 is not None:
                    misc -= s2['value'] * 1000
                    K += s2['K']
                else:
                    complete = False
        tol = M.tol_loop.get(lcls, Fraction(0))
        rec = {'id': lid, 'class': lcls, 'marks': n}
        if complete:
            rec['misclosure_mm'] = fmt(misc, 2)
            rec['length_km'] = fmt(K, 5)
            rec['tolerance_mm'] = fmt(tol * _sqrt(K), 2)
            rec['status'] = 'PASS' if misc ** 2 <= tol ** 2 * K else 'FAIL'
        else:
            rec['misclosure_mm'] = ''
            rec['length_km'] = ''
            rec['tolerance_mm'] = ''
            rec['status'] = 'INCOMPLETE'
        loops_out.append(rec)
    loops_out.sort(key=lambda r: r['id'])
    O['loops'] = loops_out

    # ---- rates (H20) ------------------------------------------------------
    epoch_id = E.epoch_ref
    ep = C.epochs.get(epoch_id) or {}
    prior_ref = parse_date(ep.get('reference_date'))
    prior_rows = C.epoch_heights.get(epoch_id, {})
    days = (E.ref_date - prior_ref).days if prior_ref else 0
    years = Fraction(days) / Fraction(36525, 100)
    prior = {}
    for tok, row in prior_rows.items():
        pm = resolve('epoch', tok, prior_ref)
        if pm['mark']:
            prior.setdefault(pm['mark'], row)
    heights_by_mark = {h['mark']: h for h in heights_out}
    disturbed_marks = set()
    for e in E.journal:
        if e['event'] != 'DISTURBED':
            continue
        if e['date'] is None or prior_ref is None:
            continue
        if prior_ref < e['date'] <= E.ref_date:
            disturbed_marks.add(e['mark'])
    rates_out = []
    for h in sorted(heights_out, key=lambda x: x['mark']):
        mk = h['mark']
        h26 = _dec_num(h['height_m'])
        sig26 = _dec_num(h['sigma_mm'])
        ph = prior.get(mk)
        fixed = h['status'] == 'FIXED'
        rec = {'mark': mk, 'height_2024_m': '', 'height_2026_m': h['height_m'],
              'rate_mm_per_yr': '', 'sigma_rate_mm_per_yr': '', 'class': ''}
        if fixed:
            rec['class'] = 'CONTROL'
        elif mk in disturbed_marks:
            rec['class'] = 'DISTURBED'
        elif ph is None:
            rec['class'] = 'NEW'
        else:
            pheight = _dec_num(ph.get('height_m'))
            psig = _dec_num(ph.get('sigma_mm'))
            rec['height_2024_m'] = fmt(pheight, 5)
            if years == 0:
                rec['class'] = 'NEW'
                rates_out.append(rec)
                continue
            rate = (h26 - pheight) * 1000 / years
            srate = _sqrt(sig26 ** 2 + psig ** 2) / years
            rec['rate_mm_per_yr'] = fmt(rate, 2)
            rec['sigma_rate_mm_per_yr'] = fmt(srate, 2)
            sig = rate ** 2 > (M.k_rate ** 2) * (srate ** 2)
            if sig and rate <= M.alert_rate:
                rec['class'] = 'ALERT'
            elif sig and rate < 0:
                rec['class'] = 'SUBSIDING'
            elif sig and rate > 0:
                rec['class'] = 'UPLIFT'
            else:
                rec['class'] = 'STABLE'
        rates_out.append(rec)
    O['rates'] = rates_out
    O['years'] = years
    O['prior_ref'] = prior_ref
    return O


def mat_inverse(N, n):
    """Exact inverse of an n x n matrix of Fractions (None entries = zero)."""
    if n == 0:
        return []
    A = [[Fraction(N[i][j]) for j in range(n)] + [
        Fraction(1) if i == j else Fraction(0) for j in range(n)]
        for i in range(n)]
    for col in range(n):
        piv = None
        for r in range(col, n):
            if A[r][col] != 0:
                piv = r
                break
        if piv is None:
            raise ValueError('singular normal matrix')
        A[col], A[piv] = A[piv], A[col]
        pv = A[col][col]
        A[col] = [x / pv for x in A[col]]
        for r in range(n):
            if r != col and A[r][col] != 0:
                f = A[r][col]
                A[r] = [a - f * b for a, b in zip(A[r], A[col])]
    return [row[n:] for row in A]


def _sqrt(x):
    """Square root of a Fraction as a Fraction-free high precision Fraction."""
    import decimal
    with decimal.localcontext() as ctx:
        ctx.prec = 60
        d = decimal.Decimal(x.numerator) / decimal.Decimal(x.denominator)
        r = d.sqrt()
        return Fraction(r)



# --------------------------------------------------------------------------
# report writing
# --------------------------------------------------------------------------

REPORTS = [
    'setup_ledger.csv', 'run_summaries.tsv', 'section_pairs.psv',
    'benchmark_resolution.csv', 'control_points.json',
    'adjustment_iterations.jsonl', 'adjusted_heights.csv', 'residuals.tsv',
    'network_summary.json', 'loop_closures.xml', 'subsidence_rates.csv',
    'excluded_records.jsonl', 'dedup_report.json', 'source_lineage.json',
    'rod_certificates_used.tsv', 'parameters_used.yaml',
    'variance_vs_published.csv', 'rate_vs_published.psv',
    'dashboard_disagreements.csv', 'cache_divergence.jsonl',
    'reconciliation.md',
]


def _write(path, text):
    if isinstance(text, str):
        data = text.encode('utf-8')
    else:
        data = text
    with open(path, 'wb') as f:
        f.write(data)


def _delim_text(header, rows):
    out = [','.join(header)]
    for r in rows:
        out.append(','.join('' if r.get(k) is None else str(r.get(k, ''))
                            for k in header))
    return '\n'.join(out) + '\n'


def _delim(header, rows, sep):
    out = [sep.join(header)]
    for r in rows:
        out.append(sep.join('' if r.get(k) is None else str(r.get(k, ''))
                            for k in header))
    return '\n'.join(out) + '\n'


def _jnum(text):
    """A JSON number literal from a formatted decimal string."""
    return text


def write_reports(E, O, out_dir):
    C = E.C
    M = E.M
    os.makedirs(out_dir, exist_ok=True)

    def W(name, text):
        _write(os.path.join(out_dir, name), text)

    # 1 setup_ledger.csv
    hdr = ['run_id', 'seq', 'instant_utc', 'back_rod', 'fore_rod', 'back_m',
           'fore_m', 'back_dist_m', 'fore_dist_m', 'temp_c', 'temp_source',
           'dh_raw_m', 'dh_m']
    W('setup_ledger.csv', _delim(hdr, O['ledger'], ','))

    # 2 run_summaries.tsv
    hdr = ['run_id', 'section_id', 'direction', 'start_mark', 'end_mark',
           'run_date', 'setups', 'length_m', 'dh_m', 'test_id',
           'collimation_mm_per_100m', 'status']
    rows = []
    for rid in sorted(O['runs']):
        r = O['runs'][rid]
        rows.append({
            'run_id': r['run_id'], 'section_id': r['section_id'],
            'direction': r['direction'], 'start_mark': r['start_mark'],
            'end_mark': r['end_mark'], 'run_date': r['run_date'],
            'setups': r['setups'],
            'length_m': r['length_m'] if r['status'] == 'VALID' else '',
            'dh_m': r['dh_m'] if r['status'] == 'VALID' else '',
            'test_id': r['test_id'],
            'collimation_mm_per_100m': fmt(r['collimation'], 3)
            if r['collimation'] is not None else '',
            'status': r['status']})
    W('run_summaries.tsv', _delim(hdr, rows, '\t'))

    # 3 section_pairs.psv
    hdr = ['section_id', 'from_mark', 'to_mark', 'line_id', 'class',
           'forward_run', 'backward_run', 'dh_forward_m', 'dh_backward_m',
           'discrepancy_mm', 'length_km', 'tolerance_mm', 'candidates',
           'status', 'value_m']
    secs = sorted(O['sections_out'], key=lambda r: r['section_id'])
    W('section_pairs.psv', _delim(hdr, secs, '|'))

    # 4 benchmark_resolution.csv
    hdr = ['context', 'token', 'resolve_date', 'mark', 'hops', 'status']
    res = sorted(O['resolutions'].values(),
                 key=lambda r: (r['context'], r['token'], r['resolve_date']))
    W('benchmark_resolution.csv', _delim(hdr, res, ','))

    # 5 control_points.json
    ctrls = []
    for c in O['controls']:
        ctrls.append({'token': c['token'], 'mark': c['mark'],
                      'status': c['status'],
                      'height_m': (fmt(c['height_m'], 5)
                                   if c['height_m'] is not None else None)})
    parts = ['{',
             ' "campaign": %s,' % _jstr(E.campaign),
             ' "reference_date": %s,' % _jstr(E.ref_date.isoformat()),
             ' "table": "C-2",',
             ' "controls": [']
    lines = []
    for c in ctrls:
        lines.append('  {"token": %s, "mark": %s, "status": %s, "height_m": %s}' % (
            _jstr(c['token']), _jstr(c['mark']), _jstr(c['status']),
            ('null' if c['height_m'] is None else c['height_m'])))
    parts.append(',\n'.join(lines))
    parts.append(' ]')
    parts.append('}')
    W('control_points.json', '\n'.join(parts) + '\n')

    # 6 adjustment_iterations.jsonl
    lines = []
    for it in O['iterations']:
        lines.append('{"component": %s, "iteration": %d, "observations": %d, '
                      '"unknowns": %d, "redundancy": %d, "vtpv": %s, '
                      '"max_w": %s, "max_w_section": %s, "action": %s}' % (
                          _jstr(it['component']), it['iteration'],
                          it['observations'], it['unknowns'],
                          it['redundancy'], it['vtpv'],
                          ('null' if it['max_w'] is None else it['max_w']),
                          ('null' if it['max_w_section'] is None
                           else _jstr(it['max_w_section'])),
                          _jstr(it['action'])))
    W('adjustment_iterations.jsonl', '\n'.join(lines) + ('\n' if lines else ''))

    # 7 adjusted_heights.csv
    hdr = ['mark', 'component', 'height_m', 'sigma_mm', 'status']
    hs = sorted(O['heights'], key=lambda h: h['mark'])
    rows = [{'mark': h['mark'], 'component': h['component'],
             'height_m': h['height_m'], 'sigma_mm': h['sigma_mm'],
             'status': h['status']} for h in hs]
    W('adjusted_heights.csv', _delim(hdr, rows, ','))

    # 8 residuals.tsv
    hdr = ['section_id', 'component', 'v_mm', 'qvv_mm2', 'w', 'status']
    rows = []
    for sid in sorted(O['residuals']):
        r = O['residuals'][sid]
        rows.append({'section_id': r['section_id'], 'component': r['component'],
                     'v_mm': r['v_mm'], 'qvv_mm2': r['qvv_mm2'], 'w': r['w'],
                     'status': r['status']})
    W('residuals.tsv', _delim(hdr, rows, '\t'))

    # 9 network_summary.json
    comps = sorted(O['summary'], key=lambda c: c['component'])
    lines = ['{', ' "campaign": %s,' % _jstr(E.campaign), ' "components": [']
    items = []
    for c in comps:
        items.append('  {"component": %s, "marks": [%s], "observations": %s, '
                     '"unknowns": %s, "redundancy": %s, "fixed": [%s], '
                     '"status": %s, "removed": [%s], "vtpv": %s, "s0": %s, '
                     '"chi2_lower": %s, "chi2_upper": %s, "global_test": %s}' % (
                         _jstr(c['component']),
                         ', '.join(_jstr(x) for x in c['marks']),
                         _num_or_null(c['observations']),
                         _num_or_null(c['unknowns']),
                         _num_or_null(c['redundancy']),
                         ', '.join(_jstr(x) for x in c['fixed']),
                         _jstr(c['status']),
                         ', '.join(_jstr(x) for x in (c.get('removed') or [])),
                         ('null' if c['vtpv'] is None else c['vtpv']),
                         ('null' if c['s0'] is None else c['s0']),
                         ('null' if c['chi2_lower'] is None else c['chi2_lower']),
                         ('null' if c['chi2_upper'] is None else c['chi2_upper']),
                         _jstr(c['global_test'])))
    lines.append(',\n'.join(items))
    lines.append(' ]')
    lines.append('}')
    W('network_summary.json', '\n'.join(lines) + '\n')

    # 10 loop_closures.xml
    out = ['<?xml version="1.0" encoding="UTF-8"?>']
    out.append('<loops campaign=%s>' % _xattr(E.campaign))
    for lp in O['loops']:
        out.append('  <loop id=%s class=%s marks=%s misclosure_mm=%s '
                   'length_km=%s tolerance_mm=%s status=%s/>' % (
                       _xattr(lp['id']), _xattr(lp['class']),
                       _xattr(str(lp['marks'])), _xattr(lp['misclosure_mm']),
                       _xattr(lp['length_km']), _xattr(lp['tolerance_mm']),
                       _xattr(lp['status'])))
    out.append('</loops>')
    W('loop_closures.xml', '\n'.join(out) + '\n')

    # 11 subsidence_rates.csv
    hdr = ['mark', 'height_2024_m', 'height_2026_m', 'rate_mm_per_yr',
           'sigma_rate_mm_per_yr', 'class']
    W('subsidence_rates.csv', _delim(hdr, O['rates'], ','))

    # 12 excluded_records.jsonl
    excl = []
    for key in O['void_setup_keys']:
        run, seq = key
        if run not in E.runs:
            continue
        excl.append({'kind': 'setup', 'id': '%s#%s' % (run, seq),
                     'reason': 'VOID_SETUP'})
    for rid in sorted(O['runs']):
        r = O['runs'][rid]
        if r['status'] != 'VALID':
            excl.append({'kind': 'run', 'id': rid, 'reason': r['status']})
    snooped = set(O['removed_all'])
    for s in secs:
        if s['status'] != 'ACCEPTED':
            excl.append({'kind': 'section', 'id': s['section_id'],
                         'reason': s['status']})
    for sid in sorted(snooped):
        excl.append({'kind': 'section', 'id': sid, 'reason': 'SNOOPED'})
    excl.sort(key=lambda r: (r['kind'], r['id'], r['reason']))
    lines = ['{"kind": %s, "id": %s, "reason": %s}' % (
        _jstr(e['kind']), _jstr(e['id']), _jstr(e['reason'])) for e in excl]
    W('excluded_records.jsonl', '\n'.join(lines) + ('\n' if lines else ''))

    # 13 dedup_report.json
    lin = O['lineage']
    W('dedup_report.json', json.dumps({
        'records_read': O['records_read'],
        'setup_keys': O['setup_keys'],
        'superseded_revisions': O['superseded_revisions'],
        'duplicates': O['duplicates'],
        'conflicts': O['conflicts'],
        'void_setups': O['void_setups'],
        'kept_setups': O['kept_setups'],
        'files_read': O['files_read'],
        'files_ignored': O['files_ignored'],
    }, indent=2) + '\n')

    # 14 source_lineage.json
    lines = ['{', ' "files": [']
    items = []
    for f in lin:
        items.append('  {"file": %s, "status": %s, "records": %d, "kept": %d, '
                     '"superseded": %d, "void_selected": %d, '
                     '"duplicates": %d, "conflicts_lost": %d}' % (
                         _jstr(f['file']), _jstr(f['status']), f['records'],
                         f['kept'], f['superseded'], f['void_selected'],
                         f['duplicates'], f['conflicts_lost']))
    lines.append(',\n'.join(items))
    lines.append(' ]')
    lines.append('}')
    W('source_lineage.json', '\n'.join(lines) + '\n')

    # 15 rod_certificates_used.tsv
    hdr = ['rod_serial', 'rod_type', 'graduation', 'certificate', 'scale_ppm',
           't0_c', 'valid_from', 'valid_to', 'readings']
    rows = []
    for u in O['cert_use'].values():
        rows.append({
            'rod_serial': u['serial'], 'rod_type': u['type'],
            'graduation': M.graduation.get(u['type'], ''),
            'certificate': u['cert']['cert'],
            'scale_ppm': fmt(u['cert']['scale'], 1),
            't0_c': fmt(u['cert']['t0'], 1),
            'valid_from': u['cert']['from'].isoformat(),
            'valid_to': u['cert']['to'].isoformat() if u['cert']['to'] else '',
            'readings': u['readings']})
    rows.sort(key=lambda r: (r['rod_serial'], r['certificate']))
    W('rod_certificates_used.tsv', _delim(hdr, rows, '\t'))

    # 16 parameters_used.yaml
    L = []
    L.append('campaign: %s' % E.campaign)
    L.append('reference_date: %s' % E.ref_date.isoformat())
    L.append('epoch_reference: %s' % E.epoch_ref)
    L.append('rod_certificate_sheet: %s' % E.sheet)
    L.append('fallback_temp_c: %s' % E.fallback_text)
    L.append('met_max_gap_min: %s' % E.gap_min_text)
    L.append('refraction_coefficient: %s' % M.raw.get('refraction', ''))
    L.append('earth_radius_m: %s' % E.radius_text)
    L.append('collimation_limit_mm_per_100m: %s' % M.raw.get('collimation', ''))
    L.append('critical_w: %s' % M.raw.get('critical_w', ''))
    L.append('min_redundancy: %s' % M.raw.get('min_redundancy', M.min_redundancy))
    L.append('max_removals: %s' % M.raw.get('max_removals', M.max_removals))
    L.append('alert_rate_mm_per_yr: %s' % M.raw.get('alert', ''))
    L.append('k_rate: %s' % M.raw.get('k_rate', ''))
    for cls in ('I', 'II', 'III'):
        L.append('tolerance_section_%s_mm: %s' % (cls, M.raw['tol_section'].get(cls, '')))
        L.append('tolerance_loop_%s_mm: %s' % (cls, M.raw['tol_loop'].get(cls, '')))
        L.append('sigma_%s_mm_per_sqrt_km: %s' % (cls, M.raw['sigma'].get(cls, '')))
    for t in sorted(M.graduation):
        L.append('graduation_%s: %s' % (t, M.graduation[t]))
        L.append('alpha_%s_ppm_per_c: %s' % (t, M.raw['alpha'].get(t, '')))
    W('parameters_used.yaml', '\n'.join(L) + '\n')


def _jstr(s):
    return json.dumps(str(s))


def _xattr(s):
    s = str(s)
    return '"%s"' % s.replace('&', '&amp;').replace('<', '&lt;').replace(
        '>', '&gt;').replace('"', '&quot;')


def _num_or_null(v):
    if v is None:
        return 'null'
    return str(v)


def _yaml_num(v):
    if v is None:
        return 'null'
    if isinstance(v, Fraction):
        d = Decimal(v.numerator) / Decimal(v.denominator)
        s = format(d.normalize(), 'f')
        if '.' not in s:
            s = s + '.0'
        return s
    return str(v)


def write_comparisons(E, O, out_dir):
    C = E.C
    M = E.M

    def W(name, text):
        _write(os.path.join(out_dir, name), text)

    pub = {}
    for r in (getattr(C, 'published', None) or []):
        mk = (r.get('mark') or '').strip()
        if mk:
            pub[mk] = (r.get('height_m') or '').strip()
    heights = {h['mark']: h for h in O['heights']}

    # 17 variance_vs_published.csv
    rows = []
    for mk in sorted(set(pub) | set(heights)):
        p = pub.get(mk)
        h = heights.get(mk)
        rec = {'mark': mk, 'published_m': '', 'recomputed_m': '', 'diff_mm': '',
               'status': ''}
        if p is not None:
            rec['published_m'] = fmt(_dec_num(p), 5)
        if h is not None:
            rec['recomputed_m'] = h['height_m']
        if p is not None and h is not None:
            diff = _dec_num(h['height_m']) - _dec_num(p)
            rec['diff_mm'] = fmt(diff * 1000, 2)
            rec['status'] = 'MATCH' if rec['diff_mm'] == '0.00' else 'DIFFERENT'
        elif p is None:
            rec['status'] = 'MISSING_PUBLISHED'
        else:
            rec['status'] = 'MISSING_RECOMPUTED'
        rows.append(rec)
    hdr = ['mark', 'published_m', 'recomputed_m', 'diff_mm', 'status']
    W('variance_vs_published.csv', _delim(hdr, rows, ','))

    # 18 rate_vs_published.psv
    pubrate = {}
    for r in (getattr(C, 'pubrates', None) or {}).get('rates', []) or []:
        mk = (r.get('mark') or '').strip()
        if mk:
            pubrate[mk] = r
    mine = {r['mark']: r for r in O['rates']}
    rows = []
    for mk in sorted(set(pubrate) | set(mine)):
        p = pubrate.get(mk)
        r = mine.get(mk)
        rec = {'mark': mk, 'published_rate': '', 'recomputed_rate': '',
               'published_class': '', 'recomputed_class': '', 'status': ''}
        if p is not None:
            v = p.get('rate_mm_per_yr')
            rec['published_rate'] = fmt(_dec_num(v), 2) if v is not None else ''
            rec['published_class'] = str(p.get('class') or '')
        if r is not None:
            rec['recomputed_rate'] = r['rate_mm_per_yr']
            rec['recomputed_class'] = r['class']
        if p is None:
            rec['status'] = 'MISSING_PUBLISHED'
        elif r is None:
            rec['status'] = 'MISSING_RECOMPUTED'
        elif (rec['published_class'] or '') != (rec['recomputed_class'] or ''):
            rec['status'] = 'CLASS_DIFFERS'
        elif rec['published_rate'] != rec['recomputed_rate']:
            rec['status'] = 'RATE_DIFFERS'
        else:
            rec['status'] = 'MATCH'
        rows.append(rec)
    hdr = ['mark', 'published_rate', 'recomputed_rate', 'published_class',
           'recomputed_class', 'status']
    W('rate_vs_published.psv', _delim(hdr, rows, '|'))

    # 19 dashboard_disagreements.csv
    dash = {}
    for r in (getattr(C, 'dashboard', None) or []):
        sid = (r.get('section_id') or '').strip()
        if sid:
            dash[sid] = (r.get('status') or '').strip()
    snooped = set(O['removed_all'])
    secmap = {s['section_id']: s for s in O['sections_out']}
    rows = []
    for sid in sorted(dash):
        st = secmap.get(sid)
        recomputed = st['status'] if st else ''
        if sid in snooped:
            recomputed = 'SNOOPED'
        if recomputed != dash[sid]:
            rows.append({'section_id': sid, 'dashboard_status': dash[sid],
                         'recomputed_status': recomputed})
    hdr = ['section_id', 'dashboard_status', 'recomputed_status']
    W('dashboard_disagreements.csv', _delim(hdr, rows, ','))

    # 20 cache_divergence.jsonl
    rows = []
    for o in (getattr(C, 'cache', None) or []):
        tok = o.get('mark')
        ep = str(o.get('epoch') or '').strip()
        if ep != 'VDH-2025' or tok is None:
            continue
        mark = resolve_token(C, tok, E.ref_date)[0]
        if not mark or mark not in M.control:
            continue
        cv = _dec_num(o.get('height_m'))
        iv = M.control[mark]
        if cv is None or cv == iv:
            continue
        rows.append({'mark': mark, 'cache_token': str(tok),
                     'cache_m': fmt(cv, 5), 'in_force_m': fmt(iv, 5),
                     'diff_mm': fmt((cv - iv) * 1000, 2)})
    rows.sort(key=lambda r: (r['mark'], r['cache_token']))
    lines = ['{"mark": %s, "cache_token": %s, "cache_m": %s, "in_force_m": %s, '
             '"diff_mm": %s}' % (_jstr(r['mark']), _jstr(r['cache_token']),
                                 r['cache_m'], r['in_force_m'], r['diff_mm'])
            for r in rows]
    W('cache_divergence.jsonl', '\n'.join(lines) + ('\n' if lines else ''))

    # 21 reconciliation.md
    runs_valid = sum(1 for r in O['runs'].values() if r['status'] == 'VALID')
    runs_rejected = len(O['runs']) - runs_valid
    secs = O['sections_out']
    sec_acc = sum(1 for s in secs if s['status'] == 'ACCEPTED')
    sec_not = len(secs) - sec_acc
    comps = O['summary']
    unc = sum(1 for c in comps if c['status'] == 'UNCONSTRAINED')
    snooped = len(O['removed_all'])
    alerts = sum(1 for r in O['rates'] if r['class'] == 'ALERT')
    loops_fail = sum(1 for l in O['loops'] if l['status'] == 'FAIL')
    lines = []
    lines.append('# %s recomputation summary' % E.campaign)
    lines.append('')
    lines.append('## Counts')
    lines.append('')
    lines.append('| item | value |')
    lines.append('| --- | --- |')
    lines.append('| runs_valid | %d |' % runs_valid)
    lines.append('| runs_rejected | %d |' % runs_rejected)
    lines.append('| sections_accepted | %d |' % sec_acc)
    lines.append('| sections_not_accepted | %d |' % sec_not)
    lines.append('| components | %d |' % len(comps))
    lines.append('| components_unconstrained | %d |' % unc)
    lines.append('| sections_snooped | %d |' % snooped)
    lines.append('| marks_adjusted | %d |' % len(O['heights']))
    lines.append('| marks_alert | %d |' % alerts)
    lines.append('| loops_failing | %d |' % loops_fail)
    lines.append('')
    lines.append('## Run pack settings')
    lines.append('')
    lines.append('| setting | pack | used |')
    lines.append('| --- | --- | --- |')
    used_map = {
        'control_table': 'C-2',
        'certificate_sheet': E.sheet,
        'refraction_coefficient': M.raw.get('refraction', ''),
        'earth_radius_m': E.radius_text,
        'tolerance_class_II_section_mm': M.raw['tol_section'].get('II', ''),
        'snooping_variance': 'A_PRIORI',
        'met_max_gap_min': E.gap_min_text,
        'fallback_temp_c': E.fallback_text,
        'pair_selection': 'MIN_DISCREPANCY',
        'run_date_source': 'FIRST_SETUP_INSTANT',
        'rod_scale_applied_to': 'EACH_READING',
        'thermal_correction': 'APPLIED',
    }
    for k, v in runpack_settings(C):
        lines.append('| %s | %s | %s |' % (k, v, used_map.get(k, '')))
    lines.append('')
    lines.append('## Largest height differences')
    lines.append('')
    lines.append('| mark | published_m | recomputed_m | diff_mm |')
    lines.append('| --- | --- | --- | --- |')
    diffs = []
    for mk in sorted(set(pub) | set(heights)):
        p = pub.get(mk)
        h = heights.get(mk)
        if p is None or h is None:
            continue
        d = (_dec_num(h['height_m']) - _dec_num(p)) * 1000
        diffs.append((mk, fmt(_dec_num(p), 5), h['height_m'], fmt(d, 2),
                      abs(_dec_num(d))))
    diffs.sort(key=lambda r: (-r[4], r[0]))
    for d in diffs[:10]:
        lines.append('| %s | %s | %s | %s |' % (d[0], d[1], d[2], d[3]))
    lines.append('')
    W('reconciliation.md', '\n'.join(lines))

    manifest = {'files': []}
    for name in REPORTS:
        path = os.path.join(out_dir, name)
        data = open(path, 'rb').read()
        manifest['files'].append({'name': name, 'bytes': len(data),
                                  'sha256': hashlib.sha256(data).hexdigest()})
    W('manifest.json', json.dumps(manifest, indent=2) + '\n')


def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: run_levelnet.py DATA_DIR OUT_DIR\n')
        return 2
    data_dir, out_dir = argv[1], argv[2]
    C = load_campaign(data_dir)
    M = memo_params(C)
    E = build_engine(C, M)
    O = compute(E)
    write_reports(E, O, out_dir)
    write_comparisons(E, O, out_dir)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
