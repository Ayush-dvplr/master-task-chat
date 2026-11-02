#!/usr/bin/env python3
"""Recompute an EA-IRMS batch (d15N vs AIR, d13C vs VPDB) from raw peak exports.

Usage: python3 run_irms.py DATA_DIR OUT_DIR
"""
import collections
import datetime
import hashlib
import json
import os
import re
import sqlite3
import sys
import xml.etree.ElementTree as ET
import zlib
from fractions import Fraction

# ---------------------------------------------------------------- helpers


def norm(tok):
    return str(tok if tok is not None else '').strip().upper()


CANON_SESSION_RE = re.compile(r'^(SQ|LN)-\d{4}-\d{2}$')


def read_text(path):
    with open(path, 'r', encoding='utf-8-sig', newline='') as fh:
        return fh.read()


def split_rows(text, delim):
    lines = text.split('\n')
    out = []
    for ln in lines:
        if ln.endswith('\r'):
            ln = ln[:-1]
        if ln == '':
            continue
        out.append(ln.split(delim))
    return out


def parse_delimited(path, delim):
    rows = split_rows(read_text(path), delim)
    hdr = [h.strip() for h in rows[0]]
    out = []
    for r in rows[1:]:
        r = r + [''] * (len(hdr) - len(r))
        out.append(dict(zip(hdr, r)))
    return out


def dec(s):
    """Exact value as Fraction from a written decimal (or numeric) value."""
    if isinstance(s, (int, float)):
        return Fraction(s).limit_denominator(10 ** 9)
    s = (s if s is not None else '').strip()
    if s == '':
        return Fraction(0)
    if ',' in s and ('.' not in s or s.rfind(',') > s.rfind('.')):
        s = s.replace('.', '').replace(',', '.') if '.' in s else s.replace(',', '.')
    neg = False
    if s.startswith('-'):
        neg = True
        s = s[1:]
    elif s.startswith('+'):
        s = s[1:]
    if '.' in s:
        a, b = s.split('.', 1)
    else:
        a, b = s, ''
    a = a or '0'
    v = Fraction(int(a) * (10 ** len(b)) + int(b or '0'), 10 ** len(b))
    return -v if neg else v


def rnd(val, places):
    """Round half to even on an exact Fraction (or int)."""
    val = Fraction(val)
    q = Fraction(10) ** places
    x = val * q
    neg = x < 0
    if neg:
        x = -x
    n = x.numerator
    d = x.denominator
    whole, rem = divmod(n, d)
    if 2 * rem > d or (2 * rem == d and whole % 2 == 1):
        whole += 1
    res = Fraction(whole, 10 ** places)
    return -res if neg else res


def fmt(val, places):
    """Format an exact Fraction at fixed decimals (round half to even)."""
    if val is None:
        return ''
    r = rnd(val, places)
    neg = r < 0
    r = -r if neg else r
    scaled = r * (10 ** places)
    n = scaled.numerator // scaled.denominator
    s = str(n).rjust(places + 1, '0')
    if places:
        s = s[:-places] + '.' + s[-places:]
    return ('-' if neg else '') + s


def round_dec(v, places):
    """Round a Decimal half to even at `places` decimals, as an exact Fraction."""
    import decimal
    ctx = decimal.Context(prec=90)
    q = ctx.scaleb(v, places)
    n = q.to_integral_value(rounding=decimal.ROUND_HALF_EVEN)
    return Fraction(str(ctx.scaleb(n, -places)))


def sqrt_round(val, places):
    """Round sqrt(val) half to even at `places` decimals."""
    import decimal
    ctx = decimal.Context(prec=90)
    if isinstance(val, decimal.Decimal):
        v = val
    else:
        v = ctx.divide(decimal.Decimal(Fraction(val).numerator),
                       decimal.Decimal(Fraction(val).denominator))
    if v == 0:
        return Fraction(0)
    return round_dec(v.sqrt(), places)


def jnum(val, places):
    """JSON number for a value rounded at `places`."""
    if val is None:
        return None
    return json.loads(fmt(val, places))


def mean(vals):
    return sum(vals, Fraction(0)) / len(vals)


def ls_fit(pts):
    """Return exact (slope, intercept) of the least squares line."""
    n = len(pts)
    sx = sum(p[0] for p in pts)
    sy = sum(p[1] for p in pts)
    sxx = sum(p[0] * p[0] for p in pts)
    sxy = sum(p[0] * p[1] for p in pts)
    den = n * sxx - sx * sx
    if den == 0:
        return None, None
    slope = Fraction(n * sxy - sx * sy, den)
    intercept = Fraction(sy - slope * sx, n)
    return slope, intercept


# ---------------------------------------------------------------- mini YAML


def parse_yaml(text):
    lines = text.split('\n')
    lines = [l[:-1] if l.endswith('\r') else l for l in lines]
    pos = [0]

    def indent(l):
        return len(l) - len(l.lstrip(' '))

    def scalar(s):
        s = s.strip()
        if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
            return s[1:-1]
        if len(s) >= 2 and s[0] == "'" and s[-1] == "'":
            return s[1:-1]
        if not (s.startswith('"') or s.startswith("'")):
            q = s.find(' #')
            if q >= 0:
                s = s[:q].strip()
        if s in ('true', 'True'):
            return True
        if s in ('false', 'False'):
            return False
        if s in ('null', '~', ''):
            return None
        try:
            return int(s)
        except ValueError:
            pass
        try:
            return float(s)
        except ValueError:
            pass
        return s

    def skip():
        while pos[0] < len(lines):
            s = lines[pos[0]].strip()
            if s == '' or s.startswith('#'):
                pos[0] += 1
            else:
                return True
        return False

    def parse_block(ind):
        if not skip():
            return None
        raw = lines[pos[0]]
        if indent(raw) < ind:
            return None
        if raw.strip().startswith('- '):
            return parse_list(indent(raw))
        return parse_map(indent(raw))

    def parse_list(ind):
        out = []
        while pos[0] < len(lines):
            if not skip():
                break
            raw = lines[pos[0]]
            st = raw.strip()
            if indent(raw) != ind or not (st == '-' or st.startswith('- ')):
                break
            rest = st[1:].strip()
            pos[0] += 1
            if rest == '':
                out.append(parse_block(ind + 1))
            elif ':' in rest and not rest.startswith('"'):
                key, _, val = rest.partition(':')
                sub = {}
                if val.strip() == '':
                    sub[key.strip()] = parse_block(ind + 2)
                else:
                    sub[key.strip()] = scalar(val)
                out.append(sub)
                while pos[0] < len(lines):
                    if not skip():
                        break
                    raw2 = lines[pos[0]]
                    if indent(raw2) <= ind:
                        break
                    sub.update(parse_map(indent(raw2)))
            else:
                out.append(scalar(rest))
        return out

    def parse_map(ind):
        out = {}
        while pos[0] < len(lines):
            if not skip():
                break
            raw = lines[pos[0]]
            st = raw.strip()
            if indent(raw) != ind or st == '-' or st.startswith('- '):
                break
            if ':' not in st:
                break
            key, _, val = st.partition(':')
            pos[0] += 1
            if val.strip() == '':
                out[key.strip()] = parse_block(ind + 1)
            else:
                out[key.strip()] = scalar(val)
        return out

    return parse_block(0)


# ---------------------------------------------------------------- site clock


class Clock:
    def __init__(self, cfg):
        self.base = self._parse_off(cfg['base_offset'])
        self.trans = []
        for t in cfg.get('transitions') or []:
            self.trans.append((self._parse_instant(t['at_utc']), self._parse_off(t['offset_after'])))
        self.trans.sort()
        self.offsets = sorted(set([self.base] + [o for _, o in self.trans]))

    @staticmethod
    def _parse_off(s):
        s = s.strip()
        sign = 1
        if s[0] == '-':
            sign = -1
            s = s[1:]
        elif s[0] == '+':
            s = s[1:]
        h, m = s.split(':')[:2]
        return sign * (int(h) * 3600 + int(m) * 60)

    @staticmethod
    def _parse_instant(s):
        s = s.strip().replace('Z', '+00:00')
        dt = datetime.datetime.fromisoformat(s)
        return (dt - datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)) // datetime.timedelta(seconds=1)

    def offset_at(self, u):
        off = self.base
        for at, o in self.trans:
            if at <= u:
                off = o
            else:
                break
        return off

    def to_local(self, u):
        return u + self.offset_at(u)

    def local_date(self, u):
        return self.to_local(u) // 86400

    def from_wall(self, day, secs):
        """Map a local wall time to an instant (H3)."""
        local = day * 86400 + secs
        valid = []
        for o in self.offsets:
            u = local - o
            if self.offset_at(u) == o:
                valid.append(u)
        if valid:
            return min(valid)
        off = self.base
        for at, o in self.trans:
            if at <= local - self.base:
                off = o
            else:
                break
        return local - off


# ---------------------------------------------------------------- memo PDF

TOK_RE = re.compile(r"\((?:\\.|[^()\\])*\)|<[0-9A-Fa-f]*>|\[|\]|/[^\s/\[\]<>()]+|[-+]?[0-9]+(?:\.[0-9]+)?|[A-Za-z'\"*]+")


def pdf_string(tok):
    if isinstance(tok, bytes):
        tok = tok.decode('latin-1')
    if tok.startswith('('):
        body = tok[1:-1].encode('latin-1')
        out = bytearray()
        i = 0
        while i < len(body):
            ch = body[i]
            if ch == 0x5c:
                i += 1
                if i >= len(body):
                    break
                c = body[i]
                if c == 0x6e:
                    out.append(10)
                elif c == 0x72:
                    out.append(13)
                elif c == 0x74:
                    out.append(9)
                elif c == 0x62:
                    out.append(8)
                elif c == 0x66:
                    out.append(12)
                elif c == 0x28:
                    out.append(40)
                elif c == 0x29:
                    out.append(41)
                elif c == 0x5c:
                    out.append(92)
                elif 0x30 <= c <= 0x37:
                    o = ''
                    while i < len(body) and 0x30 <= body[i] <= 0x37 and len(o) < 3:
                        o += chr(body[i])
                        i += 1
                    i -= 1
                    out.append(int(o, 8) & 0xFF)
                else:
                    out.append(c)
            else:
                out.append(ch)
            i += 1
        return out.decode('latin-1')
    if tok.startswith('<'):
        h = tok[1:-1]
        if len(h) % 2:
            h += '0'
        try:
            return bytes.fromhex(h).decode('latin-1')
        except Exception:
            return ''
    return ''


def pdf_items(content):
    toks = TOK_RE.findall(content)
    items = []
    tx = ty = 0
    leading = 0.0
    i = 0
    n = len(toks)

    def nums_before(idx, count):
        out = []
        j = idx - 1
        while j >= 0 and len(out) < count:
            if re.fullmatch(r'[-+]?[0-9]+(\.[0-9]+)?', toks[j]):
                out.insert(0, float(toks[j]))
                j -= 1
            else:
                break
        return out

    while i < n:
        t = toks[i]
        if t == 'BT':
            tx = ty = 0.0
        elif t == 'Tm':
            v = nums_before(i, 6)
            if len(v) == 6:
                tx, ty = v[4], v[5]
        elif t in ('Td', 'TD'):
            v = nums_before(i, 2)
            if len(v) == 2:
                tx += v[0]
                ty += v[1]
                if t == 'TD':
                    leading = v[1]
        elif t == 'T*':
            ty -= leading
        elif t == 'TL':
            v = nums_before(i, 1)
            if v:
                leading = v[0]
        elif t == 'Tj':
            s = pdf_string(toks[i - 1])
            if s:
                items.append((tx, ty, s))
        elif t == 'TJ':
            if toks[i - 1] == ']':
                arr = []
                k = i - 1
                depth = 0
                while k >= 0:
                    if toks[k] == ']':
                        depth += 1
                    elif toks[k] == '[':
                        depth -= 1
                        if depth == 0:
                            break
                    if depth == 1 and (toks[k].startswith('(') or toks[k].startswith('<')):
                        arr.insert(0, toks[k])
                    k -= 1
                txt = ''.join(pdf_string(a) for a in arr)
                if txt:
                    items.append((tx, ty, txt))
        i += 1
    return items


def pdf_rows(items, tol=2.0):
    bys = {}
    for x, y, s in items:
        bys.setdefault(round(y, 1), []).append((x, s))
    ys = sorted(bys.keys(), reverse=True)
    clusters = []
    for y in ys:
        if clusters and abs(y - clusters[-1][-1]) <= tol:
            clusters[-1].append(y)
        else:
            clusters.append([y])
    rows = []
    for cl in clusters:
        cell = []
        for y in cl:
            cell.extend(bys[y])
        cell.sort(key=lambda p: p[0])
        merged = []
        for x, s in cell:
            if merged and abs(x - merged[-1][0]) < 0.5:
                merged[-1] = (merged[-1][0], merged[-1][1] + s)
            else:
                merged.append((x, s))
        rows.append((max(cl), [s for x, s in merged]))
    rows.sort(key=lambda r: -r[0])
    return [cells for _, cells in rows]


def memo_tables(path):
    data = open(path, 'rb').read()
    pages = []
    for m in re.finditer(rb'stream\r?\n(.*?)\r?\nendstream', data, re.S):
        raw = m.group(1)
        try:
            raw = zlib.decompress(raw)
        except Exception:
            pass
        pages.append(pdf_rows(pdf_items(raw.decode('latin-1'))))
    tables = {}
    order = []
    cur = None
    header = None
    title_re = re.compile(r'^Table\s+([A-Z]-\d+):\s*(.*?)\s*\[(.*)\]\s*$')
    cont_re = re.compile(r'^Table\s+([A-Z]-\d+)\s+\(continued\)\s*$')
    for rows in pages:
        for cells in rows:
            first = cells[0].strip() if cells else ''
            mt = title_re.match(first)
            mc = cont_re.match(first)
            if mt:
                tid, title, status = mt.group(1), mt.group(2).strip(), mt.group(3).strip()
                cur = tid
                if tid not in tables:
                    tables[tid] = {'id': tid, 'title': title, 'status': status, 'rows': [], 'header': None}
                    order.append(tid)
                header = None
                continue
            if mc:
                cur = mc.group(1)
                header = None
                continue
            if cur is None:
                continue
            t = tables[cur]
            if header is None:
                header = [c.strip() for c in cells]
                t['header'] = header
                continue
            if len(cells) != len(header):
                continue
            t['rows'].append(dict(zip(header, cells)))
    return tables, order


# ---------------------------------------------------------------- workbook


NS_MAIN = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
NS_DOC = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'


class Workbook:
    def __init__(self, path):
        import zipfile
        self.z = zipfile.ZipFile(path)
        self.strings = []
        if 'xl/sharedStrings.xml' in self.z.namelist():
            ss = ET.fromstring(self.z.read('xl/sharedStrings.xml'))
            for si in ss:
                self.strings.append(''.join(t.text or '' for t in si.iter(NS_MAIN + 't')))
        wb = ET.fromstring(self.z.read('xl/workbook.xml'))
        pr = wb.find(NS_MAIN + 'workbookPr')
        self.date1904 = pr is not None and pr.get('date1904') in ('1', 'true')
        rels = ET.fromstring(self.z.read('xl/_rels/workbook.xml.rels'))
        relmap = {r.get('Id'): r.get('Target') for r in rels}
        self.parts = {}
        for sh in wb.find(NS_MAIN + 'sheets'):
            target = relmap[sh.get(NS_DOC + 'id')]
            if target.startswith('/'):
                target = target[1:]
            elif not target.startswith('xl/'):
                target = 'xl/' + target
            self.parts[sh.get('name')] = target

    def serial_date(self, serial):
        epoch = datetime.date(1904, 1, 1) if self.date1904 else datetime.date(1899, 12, 30)
        return epoch + datetime.timedelta(days=int(serial))

    def sheet_rows(self, name):
        """Return list of dict {col: text} for each row, in sheet order."""
        root = ET.fromstring(self.z.read(self.parts[name]))
        out = []
        for row in root.iter(NS_MAIN + 'row'):
            cells = {}
            for c in row:
                col = re.match(r'([A-Z]+)', c.get('r')).group(1)
                t = c.get('t')
                if t == 's':
                    v = c.find(NS_MAIN + 'v')
                    val = self.strings[int(v.text)] if v is not None else ''
                elif t == 'inlineStr':
                    ist = c.find(NS_MAIN + 'is')
                    val = ''.join(x.text or '' for x in ist.iter(NS_MAIN + 't')) if ist is not None else ''
                elif t == 'str':
                    v = c.find(NS_MAIN + 'v')
                    val = v.text if v is not None else ''
                else:
                    v = c.find(NS_MAIN + 'v')
                    val = v.text if v is not None else ''
                cells[col] = val
            out.append(cells)
        return out

    def table(self, name, key):
        """Rows of the sheet with the header row whose first cell equals `key`."""
        rows = self.sheet_rows(name)
        hdr = None
        cols = None
        start = 0
        for i, cells in enumerate(rows):
            if norm(cells.get('A', '')) == key.upper():
                cols = sorted(cells.keys(), key=col_index)
                hdr = [cells[c].strip() for c in cols]
                start = i + 1
                break
        if hdr is None:
            return [], []
        out = []
        for cells in rows[start:]:
            rec = dict(zip(hdr, [cells.get(c, '').strip() for c in cols]))
            if rec.get(hdr[1], '') == '':
                continue  # note row (H16)
            out.append(rec)
        return hdr, out


def col_index(col):
    n = 0
    for ch in col:
        n = n * 26 + (ord(ch) - 64)
    return n


# ---------------------------------------------------------------- feed layouts

ELEMENT_MAPS = {
    'E1': {'N2': 'N', 'CO2': 'C'},
    'E2': {'N': 'N', 'C': 'C'},
    'E3': {'15N': 'N', '13C': 'C'},
    'E4': {'28': 'N', '44': 'C'},
    'E5': {'NITROGEN': 'N', 'CARBON': 'C'},
}

PEAK_MAPS = {
    'P1': {'S': True, 'R': False},
    'P2': {'SAMPLE': True, 'REF': False},
    'P3': {'1': True, '0': False},
    'P3i': {'1': True, '0': False},
    'P4': {'ANALYTE': True, 'REFERENCE': False},
    'P5': {'PK': True, 'RG': False},
}

# layout -> (family, time kind, area kind, amp kind, delta kind, element map, peak map, void true, void false)
LAYOUTS = {
    'L01': ('csv', 'local_iso', 'Vs', 'mV', 'permil', 'E1', 'P1', 'V', ''),
    'L02': ('tsv', 'epoch_s', 'mVs', 'V', 'permil', 'E2', 'P2', 'VOID', 'OK'),
    'L03': ('psv', 'local_dmy', 'Vs', 'mV', 'permil', 'E3', 'P3', 'DEAD', 'LIVE'),
    'L04': ('jsonl_flat', 'epoch_ms', 'Vs', 'mV', 'milli', 'E3', 'P3i', True, False),
    'L05': ('ndjson_nested', 'iso_off', 'Vs', 'mV', 'permil', 'E2', 'P2', 'Y', 'N'),
    'L06': ('xml_attr', 'iso_z', 'mVs', 'mV', 'permil', 'E1', 'P1', '1', '0'),
    'L07': ('sqlite_split', 'local_compact', 'Vs', 'mV', 'milli', 'E1', 'P2', 1, 0),
    'L08': ('sqlite_flat', 'epoch_s', 'Vs', 'V', 'permil', 'E2', 'P1', 'VOID', ''),
    'L09': ('yaml_blocks', 'iso_off', 'Vs', 'mV', 'permil', 'E1', 'P2', 'true', 'false'),
    'L10': ('yml_grouped', 'local_iso', 'mVs', 'mV', 'permil', 'E5', 'P4', 'void', 'ok'),
    'L11': ('json_columnar', 'epoch_s', 'mVs', 'mV', 'milli', 'E2', 'P1', 1, 0),
    'L12': ('fixed', 'local_compact', 'Vs', 'mV', 'permil', 'E1', 'P5', 'X', '-'),
    'L13': ('md', 'iso_z', 'Vs', 'V', 'permil', 'E3', 'P2', 'VOID', ''),
    'L14': ('csv_semi', 'local_dmy_slash', 'Vs', 'mV', 'permil', 'E2', 'P1', 'V', ''),
    'L15': ('tsv_wide', 'epoch_ms', 'Vs', 'mV', 'permil', None, None, '1', ''),
    'L16': ('jsonl_nested', 'iso_z', 'Vs', 'mV', 'ratio', 'E1', 'P2', True, False),
    'L17': ('csv_comment', 'iso_off', 'mVs', 'V', 'permil', 'E4', 'P3', '1', '0'),
    'L18': ('psv', 'epoch_ms', 'mVs', 'mV', 'milli', 'E4', 'P5', 'Y', 'N'),
    'L19': ('xml_child', 'local_t', 'Vs', 'mV', 'milli', 'E5', 'P4', 'true', 'false'),
    'L20': ('ndjson_flat', 'basic_z', 'Vs', 'V', 'permil', 'E1', 'P1', 'void', 'ok'),
    'L21': ('sqlite_runlog', 'iso_off', 'mVs', 'mV', 'permil', 'E1', 'P2', 'VOID', ''),
    'L22': ('sqlite_eav', 'epoch_s', 'Vs', 'mV', 'permil', 'E2', 'P1', '1', '0'),
}

FIELDS = {
    'L01': ['proj', 'seq', 'inst', 'pos', 'gas', 'ptype', 'rev', 'void', 't_local', 'area_vs', 'amp_mv', 'd_permil'],
    'L02': ['Project', 'Sequence', 'Line', 'Counter', 'Species', 'PeakKind', 'Revision', 'Status', 'EpochS', 'Area_mVs', 'Amp_V', 'dRaw'],
    'L03': ['projekt', 'lauf', 'geraet', 'position', 'isotop', 'peaktyp', 'revision', 'zustand', 'zeit', 'flaeche_vs', 'amplitude_mv', 'delta'],
    'L04': ['prj', 'run', 'ln', 'slot', 'el', 'pk', 'rv', 'void', 'ts_ms', 'a', 'amp', 'dm'],
    'L05': ['project', 'sequence', 'instrument', 'position', 'gas', 'type', 'rev', 'void', 'time', 'area', 'height_mv', 'delta'],
    'L06': ['project', 'seq', 'inst', 'pos', 'el', 'kind', 'rev', 'void', 't', 'area_mvs', 'amp_mv', 'd'],
    'L07': ['project', 'seq', 'inst', 'pos', 'el', 'kind', 'rev', 'void', 't', 'area_vs', 'amp_mv', 'd'],
    'L08': ['project', 'sequence', 'instrument', 'counter', 'gas', 'peaktype', 'revision', 'void_flag', 'epoch', 'area', 'amplitude', 'delta'],
    'L09': ['project', 'sequence', 'instrument', 'position', 'gas', 'type', 'revision', 'void', 'time', 'area_vs', 'amp_mv', 'delta'],
    'L10': ['project', 'sequence', 'instrument', 'pos', 'species', 'kind', 'rev', 'state', 't', 'area_mvs', 'amp_mv', 'd'],
    'L11': ['project', 'sequence', 'instrument', 'counter', 'species', 'peak', 'revision', 'void', 'epoch_s', 'area_mvs', 'amp_mv', 'd_milli'],
    'L12': ['PROJECT', 'SEQUENCE', 'INST', 'POS', 'GAS', 'PT', 'REV', 'VOID', 'TIME', 'AREA_VS', 'AMP_MV', 'D_PERMIL'],
    'L13': ['project', 'sequence', 'instrument', 'position', 'isotope', 'peak', 'rev', 'void', 'time_utc', 'area_vs', 'amp_v', 'delta'],
    'L14': ['Projekt', 'Sequenz', 'Geraet', 'Pos', 'Element', 'Typ', 'Rev', 'Void', 'Zeit', 'Flaeche', 'Amplitude', 'Delta'],
    'L16': ['project', 'sequence', 'instrument', 'position', 'gas', 'type', 'rev', 'void', 'time', 'area', 'amp', 'ratio'],
    'L17': ['project', 'sequence', 'instrument', 'counter', 'mass', 'peak', 'rev', 'void', 'ts', 'area_mvs', 'amp_v', 'd'],
    'L18': ['PRJ', 'SEQ', 'INST', 'CTR', 'MZ', 'PT', 'REV', 'VD', 'EPOCHMS', 'AREA_MVS', 'AMP_MV', 'D_MILLI'],
    'L19': ['project', 'sequence', 'instrument', 'counter', 'species', 'kind', 'revision', 'void', 'time', 'area_vs', 'amp_mv', 'd_milli'],
    'L20': ['PROJ', 'SEQ', 'INST', 'POS', 'GAS', 'PT', 'REV', 'STATUS', 'TS', 'AREA', 'AMP_V', 'DELTA'],
    'L21': ['project', 'sequence', 'instrument', 'counter', 'gas', 'peak', 'rev', 'flag', 't', 'area_mvs', 'amp_mv', 'delta'],
    'L22': ['project', 'seq', 'inst', 'pos', 'el', 'type', 'rev', 'void', 't', 'area', 'amp', 'd'],
}

FIXED_COLS = [('PROJECT', 1), ('SEQUENCE', 11), ('INST', 27), ('POS', 36), ('GAS', 41), ('PT', 46),
              ('REV', 50), ('VOID', 54), ('TIME', 59), ('AREA_VS', 75), ('AMP_MV', 86), ('D_PERMIL', 93)]


def raw_records(path, layout):
    """Yield dicts with the 12 canonical fields, in document order."""
    fam, tkind, akind, ampkind, dkind, emap, pmap = LAYOUTS[layout][:7]
    out = []

    def base(project, seq, inst, pos, el, pk, rev, void, t, area, amp, delta):
        return {'project': project, 'session': seq, 'instrument': inst, 'counter': pos,
                'element': el, 'peak': pk, 'rev': rev, 'void': void,
                'time': t, 'area': area, 'amp': amp, 'delta': delta}

    if fam == 'csv':
        for r in parse_delimited(path, ','):
            f = [r.get(k, '') for k in FIELDS[layout]]
            out.append(base(*f))
    elif fam == 'tsv':
        for r in parse_delimited(path, '\t'):
            f = [r.get(k, '') for k in FIELDS[layout]]
            out.append(base(*f))
    elif fam == 'csv_semi':
        for r in parse_delimited(path, ';'):
            f = [r.get(k, '') for k in FIELDS[layout]]
            out.append(base(*f))
    elif fam == 'psv':
        for r in parse_delimited(path, '|'):
            f = [r.get(k, '') for k in FIELDS[layout]]
            out.append(base(*f))
    elif fam in ('jsonl_flat', 'ndjson_flat'):
        for line in read_text(path).splitlines():
            if not line.strip():
                continue
            o = json.loads(line)
            f = [o.get(k, '') for k in FIELDS[layout]]
            out.append(base(*f))
    elif fam == 'ndjson_nested':
        for line in read_text(path).splitlines():
            if not line.strip():
                continue
            o = json.loads(line)
            f = [o['meta'].get('project'), o['meta'].get('sequence'), o['meta'].get('instrument'),
                 o['inj'].get('position'), o['peak'].get('gas'), o['peak'].get('type'),
                 o.get('rev'), o.get('void'), o['inj'].get('time'), o['peak'].get('area'),
                 o['peak'].get('height_mv'), o['peak'].get('delta')]
            out.append(base(*f))
    elif fam == 'jsonl_nested':
        for line in read_text(path).splitlines():
            if not line.strip():
                continue
            o = json.loads(line)
            for pk in o.get('peaks', []):
                out.append(base(o.get('project'), o.get('sequence'), o.get('instrument'),
                                o.get('position'), pk.get('gas'), pk.get('type'), pk.get('rev'),
                                pk.get('void'), o.get('time'), pk.get('area'), pk.get('amp'), pk.get('ratio')))
    elif fam == 'json_columnar':
        o = json.loads(read_text(path))
        cols = o['export']['columns']
        for row in o['export']['rows']:
            d = dict(zip(cols, row))
            f = [d.get(k, '') for k in FIELDS[layout]]
            out.append(base(*f))
    elif fam == 'yaml_blocks':
        data = parse_yaml(read_text(path))
        for blk in data:
            for pk in blk.get('peaks') or []:
                out.append(base(blk.get('project'), blk.get('sequence'), blk.get('instrument'),
                                blk.get('position'), pk.get('gas'), pk.get('type'), pk.get('revision'),
                                pk.get('void'), blk.get('time'), pk.get('area_vs'), pk.get('amp_mv'), pk.get('delta')))
    elif fam == 'yml_grouped':
        data = parse_yaml(read_text(path))
        for grp in data.get('sequences', []):
            for pk in grp.get('peaks') or []:
                out.append(base(grp.get('project'), grp.get('sequence'), grp.get('instrument'),
                                pk.get('pos'), pk.get('species'), pk.get('kind'), pk.get('rev'),
                                pk.get('state'), pk.get('t'), pk.get('area_mvs'), pk.get('amp_mv'), pk.get('d')))
    elif fam == 'xml_attr':
        root = ET.parse(path).getroot()
        for inj in root:
            for pk in inj:
                out.append(base(inj.get('project'), inj.get('seq'), inj.get('inst'), inj.get('pos'),
                                pk.get('el'), pk.get('kind'), pk.get('rev'), pk.get('void'),
                                inj.get('t'), pk.get('area_mvs'), pk.get('amp_mv'), pk.get('d')))
    elif fam == 'xml_child':
        root = ET.parse(path).getroot()
        for rec in root:
            g = {ch.tag: (ch.text or '') for ch in rec}
            f = [g.get(k, '') for k in FIELDS[layout]]
            out.append(base(*f))
    elif fam == 'md':
        lines = read_text(path).splitlines()
        start = None
        for i, l in enumerate(lines):
            if l.strip().startswith('|') and norm(md_cell(l, 0)) == norm(FIELDS[layout][0]):
                start = i
                break
        if start is None:
            return out
        hdr = md_cell(lines[start], None)
        hdrmap = {h: i for i, h in enumerate(hdr)}
        order = [hdrmap[k] for k in FIELDS[layout]]
        for l in lines[start + 2:]:
            if not l.strip().startswith('|'):
                break
            vals = md_cell(l, None)
            out.append(base(*(vals[i] if i < len(vals) else '' for i in order)))
    elif fam == 'csv_comment':
        lines = [l for l in read_text(path).splitlines() if l.strip() and not l.strip().startswith('#')]
        hdr = [h.strip() for h in lines[0].split(',')]
        order = [hdr.index(k) for k in FIELDS[layout]]
        for l in lines[1:]:
            parts = l.split(',')
            out.append(base(*(parts[i] if i < len(parts) else '' for i in order)))
    elif fam == 'fixed':
        lines = [l for l in read_text(path).splitlines() if l.strip()]
        for l in lines[2:]:
            d = {}
            for i, (name, st) in enumerate(FIXED_COLS):
                end = FIXED_COLS[i + 1][1] - 1 if i + 1 < len(FIXED_COLS) else len(l)
                d[name] = l[st - 1:end].strip()
            f = [d.get(k, '') for k in FIELDS[layout]]
            out.append(base(*f))
    elif fam == 'tsv_wide':
        for r in parse_delimited(path, '\t'):
            for e in ('N', 'C'):
                if r.get('area_' + e, '').strip() == '':
                    continue
                out.append(base(r.get('project'), r.get('sequence'), r.get('instrument'),
                                r.get('counter'), e, 'analyte', r.get('rev_' + e), r.get('void_' + e),
                                r.get('epoch_ms'), r.get('area_' + e), r.get('amp_' + e), r.get('d_' + e)))
    elif fam == 'sqlite_flat':
        con = sqlite3.connect('file:%s?mode=ro' % path, uri=True)
        tname = wide_table(con)[0]
        cur = con.execute('select * from "%s" %s' % (tname, order_by(con, tname)))
        cols = [x[0] for x in cur.description]
        for row in cur:
            d = dict(zip(cols, row))
            f = [d.get(k, '') for k in FIELDS[layout]]
            out.append(base(*f))
        con.close()
    elif fam == 'sqlite_split':
        con = sqlite3.connect('file:%s?mode=ro' % path, uri=True)
        inj = {}
        for r in con.execute('select * from injections'):
            inj[r[0]] = r
        icols = [x[0] for x in con.execute('select * from injections limit 0').description]
        pcur = con.execute('select * from peaks %s' % order_by(con, 'peaks'))
        pcols = [x[0] for x in pcur.description]
        for r in pcur:
            d = dict(zip(pcols, r))
            i = dict(zip(icols, inj[d['inj_id']]))
            out.append(base(i.get('project'), i.get('seq'), i.get('inst'), i.get('pos'),
                            d.get('el'), d.get('kind'), d.get('rev'), d.get('voided'),
                            i.get('t_local'), d.get('area_vs'), d.get('amp_mv'), d.get('d_milli')))
        con.close()
    elif fam == 'sqlite_runlog':
        con = sqlite3.connect('file:%s?mode=ro' % path, uri=True)
        rl = {}
        rcur = con.execute('select * from runlog')
        rcols = [x[0] for x in rcur.description]
        for r in rcur:
            rl[r[0]] = dict(zip(rcols, r))
        pcur = con.execute('select * from peaktab %s' % order_by(con, 'peaktab'))
        pcols = [x[0] for x in pcur.description]
        for r in pcur:
            d = dict(zip(pcols, r))
            g = rl[d['run_key']]
            out.append(base(g.get('project'), g.get('sequence'), g.get('instrument'), d.get('counter'),
                            d.get('gas'), d.get('peak'), d.get('rev'), d.get('flag'),
                            d.get('t'), d.get('area_mvs'), d.get('amp_mv'), d.get('delta')))
        con.close()
    elif fam == 'sqlite_eav':
        con = sqlite3.connect('file:%s?mode=ro' % path, uri=True)
        recs = collections.OrderedDict()
        for rec, field, value in con.execute('select rec, field, value from kv %s'
                                             % order_by(con, 'kv')):
            recs.setdefault(rec, {})[field] = value
        for rec, d in recs.items():
            f = [d.get(k, '') for k in FIELDS[layout]]
            out.append(base(*f))
        con.close()
    else:
        raise ValueError('unknown family ' + fam)
    return out


def wide_table(con):
    cur = con.execute("select name from sqlite_master where type='table'")
    names = [x[0] for x in cur]
    return [n for n in names if n != 'sqlite_sequence']


def order_by(con, table):
    """Ascending primary key order, else rowid order (H4)."""
    info = list(con.execute('pragma table_info("%s")' % table))
    pk = [x for x in info if x[5] > 0]
    if len(pk) == 1 and 'INT' in (pk[0][2] or '').upper():
        return 'order by "%s"' % pk[0][1]
    return 'order by rowid'


def md_cell(line, i):
    parts = line.strip().strip('|').split('|')
    parts = [p.strip() for p in parts]
    if i is None:
        return parts
    return parts[i] if i < len(parts) else ''


def norm_record(rec, layout, clock):
    """Convert a raw record to canonical typed values."""
    fam, tkind, akind, ampkind, dkind, emap, pmap, vtrue, vfalse = LAYOUTS[layout]
    proj = str(rec['project']).strip()
    sess = str(rec['session']).strip()
    inst = str(rec['instrument']).strip()
    counter = int(norm(rec['counter']))
    elmap = ELEMENT_MAPS[emap] if emap else {}
    element = elmap.get(norm(rec['element'])) if emap else norm(rec['element'])
    if element is None:
        element = ''
    if pmap:
        pk = norm(rec['peak'])
        analyte = PEAK_MAPS[pmap].get(pk)
        if analyte is None:
            analyte = pk in ('ANALYTE', 'S', 'SAMPLE', 'PK', '1')
    else:
        analyte = True
    rev = int(norm(rec['rev']))
    rawvoid = rec['void']
    if isinstance(rawvoid, bool):
        isvoid = rawvoid is True
    else:
        isvoid = norm(rawvoid) == norm(vtrue) if isinstance(vtrue, str) else (rawvoid == vtrue)
    instant = parse_time(rec['time'], tkind, clock)
    area = dec(str(rec['area'])) * (Fraction(1, 1000) if akind == 'mVs' else Fraction(1))
    if ampkind == 'V':
        amp = dec(str(rec['amp'])) * 1000
    else:
        amp = dec(str(rec['amp']))
    if dkind == 'permil':
        delta = dec(str(rec['delta']))
    elif dkind == 'milli':
        delta = dec(str(rec['delta'])) / 1000
    else:  # ratio
        delta = (dec(str(rec['delta'])) - 1) * 1000
    return {'project': proj, 'session': sess, 'instrument': inst, 'counter': counter,
            'element': element, 'analyte': analyte, 'rev': rev, 'void': isvoid,
            'instant': instant, 'area': area, 'amp': amp, 'delta': delta}


def parse_time(val, kind, clock):
    s = str(val).strip()
    if kind == 'epoch_s':
        return int(dec(s))
    if kind == 'epoch_ms':
        n = dec(s)
        return int(n / 1000)
    if kind == 'iso_z':
        return parse_iso(s.replace('T', ' ').replace('Z', ''), clock, utc=True)
    if kind == 'basic_z':
        m = re.match(r'^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z$', s)
        y, mo, d, h, mi, se = (int(x) for x in m.groups())
        return day_secs(y, mo, d, h, mi, se, clock, utc=True)
    if kind == 'iso_off':
        m = re.match(r'^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})([+-])(\d{2}):?(\d{2})?$', s)
        if m:
            y, mo, d, h, mi, se = (int(x) for x in m.groups()[:6])
            sign = -1 if m.group(7) == '-' else 1
            oh = int(m.group(8))
            om = int(m.group(9) or 0)
            day = (datetime.date(y, mo, d) - datetime.date(1970, 1, 1)).days
            return day * 86400 + h * 3600 + mi * 60 + se - sign * (oh * 3600 + om * 60)
        return parse_iso(s, clock)
    if kind == 'local_iso':
        m = re.match(r'^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})$', s)
        y, mo, d, h, mi, se = (int(x) for x in m.groups())
        return day_secs(y, mo, d, h, mi, se, clock)
    if kind == 'local_compact':
        m = re.match(r'^(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})$', s)
        y, mo, d, h, mi, se = (int(x) for x in m.groups())
        return day_secs(y, mo, d, h, mi, se, clock)
    if kind == 'local_dmy':
        m = re.match(r'^(\d{2})\.(\d{2})\.(\d{4}) (\d{2}):(\d{2}):(\d{2})$', s)
        d, mo, y, h, mi, se = (int(x) for x in m.groups())
        return day_secs(y, mo, d, h, mi, se, clock)
    if kind == 'local_dmy_slash':
        m = re.match(r'^(\d{2})/(\d{2})/(\d{4}) (\d{2}):(\d{2}):(\d{2})$', s)
        d, mo, y, h, mi, se = (int(x) for x in m.groups())
        return day_secs(y, mo, d, h, mi, se, clock)
    if kind == 'local_t':
        m = re.match(r'^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})$', s)
        y, mo, d, h, mi, se = (int(x) for x in m.groups())
        return day_secs(y, mo, d, h, mi, se, clock)
    raise ValueError('unknown time kind ' + kind)


def parse_iso(s, clock, utc=False):
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})$', s.strip())
    y, mo, d, h, mi, se = (int(x) for x in m.groups())
    return day_secs(y, mo, d, h, mi, se, clock, utc=utc)


def day_secs(y, mo, d, h, mi, se, clock, utc=False):
    day = (datetime.date(y, mo, d) - datetime.date(1970, 1, 1)).days
    secs = h * 3600 + mi * 60 + se
    if utc:
        return day * 86400 + secs
    return clock.from_wall(day, secs)


def utc_text(u):
    d = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc) + datetime.timedelta(seconds=int(u))
    return d.strftime('%Y-%m-%dT%H:%M:%SZ')


def day_to_date(day):
    return datetime.date(1970, 1, 1) + datetime.timedelta(days=int(day))


def date_key(y, mo, d):
    return (datetime.date(y, mo, d) - datetime.date(1970, 1, 1)).days


# ---------------------------------------------------------------- aliases


class Aliases:
    def __init__(self, path, project, samples, clients, session_date):
        con = sqlite3.connect('file:%s?mode=ro' % path, uri=True)
        self.salias = collections.defaultdict(list)
        for t, can, p in con.execute('select token, canonical, project from session_alias order by rowid'):
            self.salias[norm(t)].append((norm(can), norm(p)))
        self.ialias = collections.defaultdict(list)
        for t, can in con.execute('select token, canonical from instrument_alias order by rowid'):
            self.ialias[norm(t)].append(norm(can))
        con.close()
        self.project = project
        self.samples = set(samples)
        self.clients = dict(clients)
        self.session_date = session_date
        self.cache = {}

    def session(self, token, project=None):
        project = project or self.project
        key = ('s', project, norm(token))
        if key in self.cache:
            return self.cache[key]
        t = norm(token)
        steps = 0
        while steps < 32:
            if CANON_SESSION_RE.match(t):
                break
            rows = [c for c, p in self.salias.get(t, []) if p == '*' or p == project]
            if not rows:
                break
            t = rows[0]
            steps += 1
        self.cache[key] = t
        return t

    def instrument(self, token):
        t = norm(token)
        steps = 0
        while steps < 32:
            if t in ('K1', 'K2'):
                return t
            rows = self.ialias.get(t, [])
            if not rows:
                return t
            t = rows[0]
            steps += 1
        return t

    def material(self, token, project=None, session_day=None):
        """Resolve a material token; returns canonical or the token itself."""
        project = project or self.project
        t = norm(token)
        steps = 0
        while steps < 32:
            if t in CANON_MATERIALS or t in self.samples:
                return t
            rows = []
            for can, p, vf, order in self.malias.get(t, []):
                if p != '*' and p != project:
                    continue
                if session_day is None or vf <= session_day:
                    rows.append((vf, order, can))
            if not rows:
                break
            rows.sort()
            t = rows[-1][2]
            steps += 1
        if t in self.clients:
            return self.clients[t]
        return t

    def set_material_rows(self, rows):
        """(token, canonical, project, valid_from, order) rows; ties keep document order."""
        self.malias = collections.defaultdict(list)
        for i, row in enumerate(rows):
            token, can, proj, vf = row[0], row[1], row[2], row[3]
            d = vf.strip()
            day = (datetime.date(int(d[:4]), int(d[5:7]), int(d[8:10])) - datetime.date(1970, 1, 1)).days
            self.malias[norm(token)].append((norm(can), norm(proj), day, i))

    def material_paths(self, token, project=None):
        """All canonical values a token can take (for the alias report)."""
        project = project or self.project
        t = norm(token)
        outs = []
        seen = set()
        frontier = [(t, None)]
        while frontier:
            cur, vf = frontier.pop(0)
            if (cur, vf) in seen:
                continue
            seen.add((cur, vf))
            if cur in CANON_MATERIALS or cur in self.samples:
                outs.append((cur, vf))
                continue
            rows = []
            for can, p, v, order in self.malias.get(cur, []):
                if p == '*' or p == project:
                    rows.append((v, order, can))
            if rows:
                for v, order, can in sorted(rows):
                    frontier.append((can, v))
            else:
                if cur in self.clients:
                    outs.append((self.clients[cur], vf))
                else:
                    outs.append((cur, vf))
        return outs


CANON_MATERIALS = {'RM-GLU-L', 'RM-GLU-H', 'RM-CAF', 'QC-SED', 'QC-MUS', 'QC-ALG',
                   'ELM-ACT', 'BLK', 'COND'}
MATERIAL_CLASS = {'RM-GLU-L': 'RM', 'RM-GLU-H': 'RM', 'RM-CAF': 'RM',
                  'QC-SED': 'QC', 'QC-MUS': 'QC', 'QC-ALG': 'QC',
                  'ELM-ACT': 'ELM', 'BLK': 'BLK', 'COND': 'COND'}


# ---------------------------------------------------------------- batch


class Batch:
    def __init__(self, data_dir):
        self.dir = data_dir
        self.path = lambda name: os.path.join(data_dir, name)
        self.profile = parse_yaml(read_text(self.path('analysis_profile.yml')))
        self.project = self.profile['project']
        self.elements = list(self.profile['elements'])
        self.clock = Clock(parse_yaml(read_text(self.path('site_clock.yaml'))))
        self.memo, self.memo_order = memo_tables(self.path('governance_memo.pdf'))
        self.tables = {}
        for tid in self.memo_order:
            if self.memo[tid]['status'] == 'IN FORCE':
                self.tables[tid] = self.memo[tid]
        self.workbook = Workbook(self.path('reference_workbook.xlsx'))
        # manifest samples
        self.samples = {}
        self.clients = {}
        for r in parse_delimited(self.path('sample_manifest.csv'), ','):
            sid = r['sample_id'].strip()
            self.samples[sid] = r
            self.clients[norm(r['client_id'])] = sid
        self.alias = Aliases(self.path('alias_register.sqlite'), self.project,
                             self.samples.keys(), self.clients, None)
        con = sqlite3.connect('file:%s?mode=ro' % self.path('alias_register.sqlite'), uri=True)
        rows = list(con.execute('select token, canonical, project, valid_from from material_alias'))
        con.close()
        self.alias.set_material_rows(rows)
        self._load_reference()
        self._load_sequences()
        self._load_events()
        self._ingest()

    # ---------------- reference data

    def _load_reference(self):
        p = self.profile
        self.rm_sheet = p['rm_sheet']
        self.qc_sheet = p['qc_sheet']
        self.elemental_sheet = p['elemental_sheet']
        self.weights_sheet = p['weights_sheet']
        _, rows = self.workbook.table(self.rm_sheet, 'material')
        self.rm_value = {}
        for r in rows:
            if norm(r.get('status', '')) != 'CERTIFIED':
                continue
            self.rm_value[(norm(r['material']), norm(r['lot']))] = r
        _, rows = self.workbook.table(self.qc_sheet, 'material')
        self.qc_assigned = {}
        for r in rows:
            if norm(r.get('status', '')) != 'CURRENT':
                continue
            self.qc_assigned[norm(r['material'])] = r
        _, rows = self.workbook.table(self.elemental_sheet, 'material')
        self.elemental_pct = {}
        for r in rows:
            if norm(r.get('status', '')) != 'IN USE':
                continue
            self.elemental_pct[norm(r['lot'])] = r
        _, rows = self.workbook.table(self.weights_sheet, 'capsule_id')
        self.weights = {}
        for r in rows:
            self.weights[norm(r['capsule_id'])] = r
        # balance calibration
        self.balance = collections.defaultdict(list)
        for r in parse_delimited(self.path('balance_calibration.tsv'), '\t'):
            self.balance[r['balance'].strip()].append(r)
        # capsule register
        self.capsule = {}
        for r in parse_delimited(self.path('rm_capsule_register.psv'), '|'):
            self.capsule[norm(r['capsule_id'])] = r
        # capsule flags
        self.flags = collections.defaultdict(list)
        for line in read_text(self.path('capsule_flags.jsonl')).splitlines():
            if not line.strip():
                continue
            o = json.loads(line)
            self.flags[norm(o['capsule'])].append(o)
        self.flag_effect = {}
        for r in self.tables['X-1']['rows']:
            self.flag_effect[norm(r['code'])] = norm(r['effect'])
        self.reason_status = {}
        for r in self.tables['C-1']['rows']:
            self.reason_status[norm(r['code'])] = norm(r['status'])
        # molar masses
        txt = read_text(self.path('stat_quick_reference.txt'))
        cur = False
        self.molar = {}
        for line in txt.splitlines():
            s = line.strip()
            if s.lower().startswith('section'):
                cur = s.startswith('Section AW')
                continue
            if not cur or '|' not in s:
                continue
            parts = [x.strip() for x in s.split('|')]
            if len(parts) >= 2 and parts[0] in ('element', 'C', 'N', 'H', 'O', 'S'):
                try:
                    self.molar[parts[0]] = dec(parts[1])
                except Exception:
                    pass

    def _load_sequences(self):
        root = ET.parse(self.path('sequence_tables.xml')).getroot()
        self.sequences = {}
        for seq in root:
            if norm(seq.get('project')) != norm(self.project):
                continue
            sid = self.alias.session(seq.get('id'), self.project)
            slots = {}
            for sl in seq:
                slots[int(sl.get('tray'))] = {'token': (sl.get('token') or '').strip(),
                                              'capsule': norm(sl.get('capsule'))}
            self.sequences[sid] = {'id': sid, 'token_id': seq.get('id'),
                                   'instrument': self.alias.instrument(seq.get('instrument')),
                                   'kind': norm(seq.get('kind')), 'slots': slots}
        # tray corrections journal
        self.journal = {}
        for line in read_text(self.path('tray_corrections.ndjson')).splitlines():
            if not line.strip():
                continue
            o = json.loads(line)
            if norm(o.get('project')) != norm(self.project):
                continue
            sid = self.alias.session(o.get('session'), norm(o.get('project')))
            self.journal.setdefault(sid, []).append(o)

    def _load_events(self):
        # session events
        self.session_events = collections.defaultdict(list)
        for r in parse_delimited(self.path('session_events.psv'), '|'):
            sid = self.alias.session(r['session'], r['project'])
            self.session_events[sid].append({
                'id': int(r['event_id']), 'event': norm(r['event']),
                'instant': self.wall_instant(r['local_time'], norm(r['project'])),
                'detail': r['detail'].strip(), 'project': r['project'].strip()})
        # autosampler
        self.skip = collections.defaultdict(list)
        seen = set()
        for line in read_text(self.path('autosampler_events.txt')).splitlines():
            if line.startswith('#') or not line.strip():
                continue
            parts = [x.strip() for x in line.split('|')]
            if len(parts) < 7 or parts[4].upper() != 'SKIP':
                continue
            if parts[6].lower() != 'ok':
                continue
            eid = parts[0]
            if eid in seen:
                continue
            seen.add(eid)
            m = re.search(r'(\d+)', parts[5])
            if not m:
                continue
            sid = self.alias.session(parts[3], self.project)
            self.skip[sid].append(int(m.group(1)))
        # audit trail
        con = sqlite3.connect('file:%s?mode=ro' % self.path('reintegration_audit.db'), uri=True)
        self.audit = collections.defaultdict(list)
        for r in con.execute('select entry_id, project, sequence, counter, gas, revision, action, reason_code, entered_utc from audit_trail'):
            self.audit[(norm(r[1]), self.alias.session(r[2], norm(r[1])), int(r[3]), self.gas_element(r[4]))].append(r)
        con.close()
        for k in self.audit:
            self.audit[k].sort(key=lambda r: (r[8], r[0]))
        # rulings
        self.rulings = []
        for r in self.tables['R-1']['rows']:
            self.rulings.append(r)

    @staticmethod
    def gas_element(tok):
        t = norm(tok)
        if t in ('N2', 'N', '15N', '28', 'NITROGEN'):
            return 'N'
        if t in ('CO2', 'C', '13C', '44', 'CARBON'):
            return 'C'
        return t

    def wall_instant(self, text, project):
        s = text.strip()
        if 'T' in s:
            m = re.match(r'^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?$', s)
        else:
            m = re.match(r'^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2})(?::(\d{2}))?$', s)
        if not m:
            return None
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        h, mi = int(m.group(4)), int(m.group(5))
        se = int(m.group(6) or 0)
        return self.clock.from_wall((datetime.date(y, mo, d) - datetime.date(1970, 1, 1)).days,
                                    h * 3600 + mi * 60 + se)

    # ---------------- ingestion

    def _ingest(self):
        cat = json.loads(read_text(self.path('ingest_catalog.json')))
        self.catalog_project = norm(cat.get('project', self.project))
        events = sorted(cat['events'], key=lambda e: e['event'])
        segstate = {}
        layout = {}
        firstreg = {}
        for e in events:
            act = norm(e['action'])
            if act == 'VERIFY':
                continue
            key = (e['file'], norm(e['session']))
            if act == 'REGISTER':
                segstate[key] = True
                layout[key] = e.get('layout')
                firstreg[e['file']] = min(firstreg.get(e['file'], 1 << 30), e['event'])
            elif act == 'RETIRE':
                segstate[key] = False
        self.seg_active = {k for k, v in segstate.items() if v}
        self.seg_by_file = collections.defaultdict(set)
        for (fname, stok) in self.seg_active:
            self.seg_by_file[fname].add(self.alias.session(stok, self.catalog_project))
        # processing order
        order = sorted({f for f, _ in self.seg_active},
                       key=lambda f: (firstreg.get(f, 1 << 30), f))
        counters = collections.Counter()
        lineage = []
        kept = {}
        seen_keys = set()
        self.seen_tokens = collections.defaultdict(set)
        for fname in order:
            layout_id = None
            for (f, s) in self.seg_active:
                if f == fname:
                    layout_id = layout[(f, s)]
                    break
            if layout_id is None or layout_id not in LAYOUTS:
                continue
            recs = raw_records(self.path(fname), layout_id)
            fc = collections.Counter()
            for raw in recs:
                r = norm_record(raw, layout_id, self.clock)
                fc['records'] += 1
                counters['records_read'] += 1
                if norm(r['project']) != norm(self.project):
                    fc['other_project'] += 1
                    counters['other_project'] += 1
                    continue
                if not r['analyte']:
                    fc['reference_peaks'] += 1
                    counters['reference_peaks'] += 1
                    continue
                sid = self.alias.session(r['session'], norm(r['project']))
                if sid not in self.seg_by_file.get(fname, set()):
                    fc['inactive_segment'] += 1
                    counters['inactive_segment'] += 1
                    continue
                self.seen_tokens['session'].add(norm(r['session']))
                self.seen_tokens['instrument'].add(norm(r['instrument']))
                key = (sid, r['counter'], r['element'], r['rev'])
                if key in seen_keys:
                    fc['duplicates'] += 1
                    counters['duplicates'] += 1
                    continue
                seen_keys.add(key)
                fc['unique'] += 1
                r['session'] = sid
                r['instrument'] = self.alias.instrument(r['instrument'])
                r['file'] = fname
                kept.setdefault(key, r)
            lineage.append({'file': fname, 'layout': layout_id, 'counts': fc})
        self.lineage = lineage
        self.counters = counters
        self.uniques = kept
        # group per injection element
        groups = collections.defaultdict(dict)
        for (sid, counter, element, rev), r in kept.items():
            groups[(sid, counter, element)][rev] = r
        self.groups = groups
        # revision admission and void test
        self.admitted = {}
        not_admitted = 0
        superseded = 0
        voided = 0
        selected = {}
        for key, revs in groups.items():
            adm = {}
            for rev, rec in revs.items():
                if rev == 0:
                    adm[rev] = rec
                    continue
                entries = self.audit.get((norm(rec['project']), key[0], key[1], key[2]))
                entry = None
                if entries:
                    cand = [e for e in entries if e[5] == rev]
                    if cand:
                        entry = cand[-1]
                if entry is not None and norm(entry[6]) == 'APPROVE' and \
                        self.reason_status.get(norm(entry[7])) == 'ACCEPTED':
                    adm[rev] = rec
                else:
                    not_admitted += 1
            if not adm:
                continue
            sel = max(adm)
            for rev in adm:
                if rev < sel:
                    superseded += 1
            if adm[sel]['void']:
                voided += 1
                continue
            selected[key] = adm[sel]
        self.counters['revisions_not_admitted'] = not_admitted
        self.counters['revisions_superseded'] = superseded
        self.counters['voided'] = voided
        self.counters['kept'] = len(selected)
        self.selected = selected
        self.counters['files_read'] = len(order)
        self._resolve_sessions()
        self._resolve_positions()

    # ---------------- sessions, positions, materials

    def _resolve_sessions(self):
        """Session start, date, kind, instrument, run minutes, leak, pauses."""
        self.sessions = {}
        recs = collections.defaultdict(list)
        for (sid, counter, element), r in self.selected.items():
            recs[sid].append(r)
        for sid in set(list(self.sequences.keys()) + list(recs.keys())):
            seq = self.sequences.get(sid)
            info = {'id': sid, 'kind': seq['kind'] if seq else None,
                    'instrument': seq['instrument'] if seq else None,
                    'start': None, 'date': None, 'leak': False, 'pauses': []}
            rl = [r for r in recs.get(sid, []) if r['counter'] == 1]
            if rl:
                info['start'] = min(r['instant'] for r in rl)
                info['date'] = self.clock.local_date(info['start'])
            if seq is None and rl:
                info['instrument'] = rl[0]['instrument']
            evs = sorted(self.session_events.get(sid, []), key=lambda e: (e['instant'], e['id']))
            leaks = [e for e in evs if e['event'] == 'LEAK_CHECK']
            if leaks:
                info['leak'] = norm(leaks[-1]['detail']) == 'FAIL'
            pauses = []
            pending = None
            for e in evs:
                if e['event'] == 'PAUSE':
                    pending = e
                elif e['event'] == 'RESUME' and pending is not None:
                    pauses.append((pending['instant'], e['instant']))
                    pending = None
            info['pauses'] = pauses
            self.sessions[sid] = info
        # fill session starts from uniques when no kept counter 1 exists
        for sid, info in self.sessions.items():
            if info['start'] is None:
                rl = [r for k, r in self.uniques.items() if k[0] == sid and r['counter'] == 1]
                if rl:
                    info['start'] = min(r['instant'] for r in rl)
                    info['date'] = self.clock.local_date(info['start'])
                else:
                    rl = [r for k, r in self.uniques.items() if k[0] == sid]
                    if rl:
                        info['start'] = min(r['instant'] for r in rl)
                        info['date'] = self.clock.local_date(info['start'])

    def run_minutes(self, sid, instant):
        info = self.sessions.get(sid)
        if info is None or info['start'] is None:
            return Fraction(0)
        base = info['start']
        elapsed = instant - base
        for p0, p1 in info['pauses']:
            lo = max(p0, base)
            hi = min(p1, instant)
            if hi > lo:
                elapsed -= (hi - lo)
        return Fraction(elapsed, 60)

    def _resolve_positions(self):
        """Tray positions, materials, exclusions."""
        self.tray_of = {}
        self.position = {}
        self.excluded = {}
        self.ruling_target = collections.defaultdict(list)
        for r in self.rulings:
            if norm(r['status']) != 'IN FORCE' or norm(r['action']) != 'EXCLUDE_POSITION':
                continue
            if norm(r['project']) != norm(self.project):
                continue
            parts = r['target'].rsplit('/', 1)
            if len(parts) != 2:
                continue
            sid = self.alias.session(parts[0], norm(r['project']))
            self.ruling_target[(sid, parts[1].strip())].append(r)
        for sid, info in self.sessions.items():
            skips = self.skip.get(sid, [])
            counters = {}
            for (s, counter, element), r in self.selected.items():
                if s != sid:
                    continue
                counters.setdefault(counter, r)
            for counter, r in counters.items():
                tray = counter + sum(1 for c in skips if c <= counter)
                self.tray_of[(sid, counter)] = tray
            info['counters'] = counters
        # material per (session, tray)
        for sid, info in self.sessions.items():
            seq = self.sequences.get(sid)
            slots = seq['slots'] if seq else {}
            for tray in sorted(set(list(slots.keys()) + [t for (s, t) in self.tray_of if s == sid])):
                rec = self.tray_material(sid, tray, slots, info['date'])
                self.position[(sid, tray)] = rec
            # exclusions
            for counter, r in info['counters'].items():
                tray = self.tray_of[(sid, counter)]
                pos = self.position[(sid, tray)]
                why = None
                for rl in self.ruling_target.get((sid, str(tray)), []):
                    why = 'RULING:' + rl['ruling']
                    break
                if why is None:
                    for f in self.flags.get(pos['capsule'], []):
                        if self.flag_effect.get(norm(f['code'])) == 'EXCLUDE':
                            why = 'FLAG:' + norm(f['code'])
                            break
                if why is not None:
                    self.excluded[sid + '|' + str(counter)] = why

    def tray_material(self, sid, tray, slots, session_day):
        """Resolve the material of a tray, honouring the journal (H5)."""
        entry = self.journal_effective(sid, tray)
        slot = slots.get(tray)
        seq_token = slot['token'] if slot else ''
        if entry is not None:
            token = (entry.get('value') or '').strip()
            jseq = entry['seq']
        else:
            token = seq_token
            jseq = None
        material = self.alias.material(token, self.project, session_day)
        capsule = slots.get(tray, {}).get('capsule', '') if slots.get(tray) else ''
        mass = None
        w = self.weights.get(capsule)
        if w is not None:
            mass = self.capsule_mass(w)
        return {'token': seq_token, 'journal_value': token, 'seq': jseq,
                'material': material,
                'class': MATERIAL_CLASS.get(material, 'SAMPLE' if material in self.samples else ''),
                'capsule': capsule, 'mass': mass}

    def journal_effective(self, sid, tray):
        """The SET entry in effect for the tray, or None (H5)."""
        rows = [r for r in self.journal.get(sid, [])
                if int(r.get('tray', -1)) == tray
                and norm(r.get('field')) == 'TOKEN'
                and norm(r.get('status')) == 'POSTED']
        if not rows:
            return None
        byseq = {r['seq']: r for r in rows}
        active = {}

        def toggle(entry):
            if norm(entry.get('action')) == 'SET':
                active[entry['seq']] = not active.get(entry['seq'], False)
            else:
                tgt = byseq.get(entry.get('reverses'))
                if tgt is not None:
                    toggle(tgt)

        for r in sorted(rows, key=lambda x: x['seq']):
            if norm(r.get('action')) == 'SET':
                active[r['seq']] = True
            else:
                tgt = byseq.get(r.get('reverses'))
                if tgt is not None:
                    toggle(tgt)
        in_effect = [byseq[s] for s in active if active[s] and norm(byseq[s].get('action')) == 'SET']
        if not in_effect:
            return None
        in_effect.sort(key=lambda r: r['seq'])
        return in_effect[-1]

    def capsule_mass(self, w):
        """mass_mg * balance factor for the weigh date (H12)."""
        serial = w.get('weighed', '').strip()
        wdate = self.workbook.serial_date(serial)
        bal = w.get('balance', '').strip()
        factor = None
        for r in self.balance.get(bal, []):
            vf = datetime.date.fromisoformat(r['valid_from'].strip())
            vt = datetime.date.fromisoformat(r['valid_to'].strip())
            if vf <= wdate < vt:
                factor = dec(r['factor'])
                break
        mass = dec(w.get('mass_mg', '0'))
        if factor is None:
            return mass
        return rnd(mass * factor, 4)

    # ---------------- computations

    def table_row(self, tid, key, value):
        for r in self.tables[tid]['rows']:
            if norm(r[key]) == norm(value):
                return r
        return None

    def norm_set(self, element):
        r = self.table_row('N-2', 'element', element)
        return [x.strip() for x in r['reference_set'].split(';')], r

    def compute(self):
        p = self.profile
        self.elements = list(p['elements'])
        self.a_ref = {e: dec(str(p['a_ref_vs'][e])) for e in self.elements}
        self.lin_min = int(p['linearity_min_points'])
        self.lookback = int(p['linearity_lookback_days'])
        self.drift_material = p['drift_material'].strip()
        self.drift_min = int(p['drift_min_points'])
        self.grubbs_alpha = str(p['grubbs_alpha']).strip()
        self.A1 = {e: self.table_row('A-1', 'element', e) for e in self.elements}
        self.L1 = {e: self.table_row('L-1', 'element', e) for e in self.elements}
        self.N2 = {e: self.norm_set(e) for e in self.elements}
        self.grubbs = {}
        for r in self.tables['G-1']['rows']:
            self.grubbs[int(r['n'])] = dec(r['alpha_' + self.grubbs_alpha])
        self.qc_tols = {}
        for r in self.tables['Q-1']['rows']:
            self.qc_tols[(norm(r['material']), norm(r['element']))] = dec(r['tolerance_permil'])

        # injection elements with derived context
        self.inj = {}
        for (sid, counter, element), r in self.selected.items():
            tray = self.tray_of[(sid, counter)]
            pos = self.position[(sid, tray)]
            ex = self.excluded.get(sid + '|' + str(counter))
            self.inj[(sid, counter, element)] = {
                'rec': r, 'session': sid, 'counter': counter, 'element': element,
                'tray': tray, 'material': pos['material'], 'class': pos['class'],
                'capsule': pos['capsule'], 'mass': pos['mass'],
                'instrument': self.sessions[sid]['instrument'],
                'excluded': ex, 'run_minutes': self.run_minutes(sid, r['instant']),
                'area': r['area'], 'amp': r['amp'], 'd_raw': r['delta'],
                'rev': r['rev'], 'instant': r['instant']}
        self.analytical = sorted([s for s, i in self.sessions.items() if i['kind'] == 'ANALYTICAL'])
        self.linearity_sessions = sorted([s for s, i in self.sessions.items() if i['kind'] == 'LINEARITY'])

        # ---- H8 linearity
        self.lin_sessions = []
        self.lin_slope = {}
        for sid in self.linearity_sessions:
            for e in self.elements:
                pts = [(v['area'], v['d_raw']) for v in self.inj.values()
                       if v['session'] == sid and v['element'] == e
                       and not v['excluded'] and v['material'] == 'ELM-ACT']
                pts.sort(key=lambda t: (t[0], t[1]))
                slope = None
                if len(pts) >= self.lin_min:
                    slope = rnd(ls_fit(pts)[0], 6)
                self.lin_slope[(sid, e)] = {'n_points': len(pts), 'slope': slope}
                self.lin_sessions.append((sid, e, len(pts), slope))
        self.lin_assignment = {}
        for sid in self.analytical:
            info = self.sessions[sid]
            for e in self.elements:
                cand = [s for s in self.linearity_sessions
                        if self.sessions[s]['instrument'] == info['instrument']
                        and self.sessions[s]['date'] == info['date']
                        and self.sessions[s]['start'] is not None
                        and self.sessions[s]['start'] < info['start']
                        and self.lin_slope[(s, e)]['slope'] is not None]
                use = None
                if cand:
                    use = max(cand, key=lambda s: (self.sessions[s]['start'], s))
                else:
                    lo = info['date'] - self.lookback
                    cand = [s for s in self.linearity_sessions
                            if self.sessions[s]['instrument'] == info['instrument']
                            and self.lin_slope[(s, e)]['slope'] is not None
                            and lo <= self.sessions[s]['date'] <= info['date'] - 1]
                    if cand:
                        use = max(cand, key=lambda s: (self.sessions[s]['date'],
                                                       self.sessions[s]['start'], s))
                slope = self.lin_slope[(use, e)]['slope'] if use else None
                status = 'NONE'
                applied = Fraction(0)
                if slope is not None:
                    thr = dec(self.L1[e]['threshold_permil_per_vs'])
                    if abs(slope) >= thr:
                        status = 'APPLIED'
                        applied = slope
                    else:
                        status = 'BELOW_THRESHOLD'
                self.lin_assignment[(sid, e)] = {'lin_session': use, 'lin_slope': slope,
                                                 'applied': applied, 'status': status}
        # d_lin
        for v in self.inj.values():
            a = self.lin_assignment.get((v['session'], v['element']))
            k = a['applied'] if a else Fraction(0)
            v['d_lin'] = rnd(v['d_raw'] - k * (v['area'] - self.a_ref[v['element']]), 4)

        # ---- H9 drift
        self.drift = {}
        for sid in self.analytical:
            for e in self.elements:
                pts = [(v['run_minutes'], v['d_lin']) for v in self.inj.values()
                       if v['session'] == sid and v['element'] == e
                       and not v['excluded'] and v['material'] == self.drift_material]
                if len(pts) >= self.drift_min:
                    slope = rnd(ls_fit(pts)[0], 8)
                    anchor = rnd(mean([p[0] for p in pts]), 4)
                    status = 'FITTED'
                else:
                    slope = Fraction(0)
                    anchor = Fraction(0)
                    status = 'INSUFFICIENT'
                self.drift[(sid, e)] = {'n_points': len(pts), 'slope': slope,
                                        'anchor': anchor, 'status': status}
        for v in self.inj.values():
            d = self.drift.get((v['session'], v['element']))
            if d and d['status'] == 'FITTED':
                v['d_drift'] = rnd(v['d_lin'] - d['slope'] * (v['run_minutes'] - d['anchor']), 4)
            else:
                v['d_drift'] = v['d_lin']

        # ---- H10 blank
        self.blank = {}
        for sid in self.analytical:
            for e in self.elements:
                limit = dec(self.A1[e]['blank_area_max_vs'])
                bl = [v for v in self.inj.values()
                      if v['session'] == sid and v['element'] == e
                      and not v['excluded'] and v['material'] == 'BLK']
                kept = [v for v in bl if v['area'] <= limit]
                rej = [v for v in bl if v['area'] > limit]
                if kept:
                    area = rnd(mean([v['area'] for v in kept]), 4)
                    delta = rnd(mean([v['d_raw'] for v in kept]), 3)
                else:
                    area = Fraction(0)
                    delta = Fraction(0)
                self.blank[(sid, e)] = {'n_blanks': len(kept), 'n_rejected': len(rej),
                                        'area': area, 'delta': delta}
        for v in self.inj.values():
            b = self.blank.get((v['session'], v['element']))
            if b is None:
                v['d_blank'] = v['d_drift']
                continue
            A = v['area']
            if A == b['area']:
                v['d_blank'] = v['d_drift']
            else:
                v['d_blank'] = rnd((v['d_drift'] * A - b['delta'] * b['area']) / (A - b['area']), 4)

        # ---- H11 normalization
        self.norm_fit = {}
        for sid in self.analytical:
            for e in self.elements:
                refset, nrow = self.N2[e]
                limit = dec(nrow['reject_limit_permil'])
                maxrej = int(nrow['max_rejections'])
                amin = dec(self.A1[e]['amplitude_min_mv'])
                amax = dec(self.A1[e]['amplitude_max_mv'])
                cands = []
                for v in self.inj.values():
                    if v['session'] != sid or v['element'] != e or v['excluded']:
                        continue
                    if v['material'] not in refset:
                        continue
                    if not (amin <= v['amp'] <= amax):
                        continue
                    cap = self.capsule.get(v['capsule'])
                    if cap is None:
                        continue
                    key = (norm(cap['material']), norm(cap['lot']))
                    row = self.rm_value.get(key)
                    if row is None:
                        continue
                    y = dec(row['d15N_air' if e == 'N' else 'd13C_vpdb'])
                    cands.append({'v': v, 'material': v['material'], 'y': y,
                                  'x': v['d_blank'], 'tray': v['tray']})
                counts = collections.Counter(c['material'] for c in cands)
                if any(counts[m] < 2 for m in refset):
                    status = 'NO_NORMALIZATION'
                    self.norm_fit[(sid, e)] = {'reference_set': refset, 'n_points': None,
                                               'fits': 0, 'slope': None, 'intercept': None,
                                               'removed': [], 'status': status}
                    continue
                pts = [(c['x'], c['y']) for c in cands]
                slope, intercept = ls_fit(pts)
                nfits = 1
                removed = []
                status = 'CONVERGED'
                cur = list(cands)
                while True:
                    worst = None
                    for c in cur:
                        resid = c['y'] - (slope * c['x'] + intercept)
                        if worst is None or abs(resid) > abs(worst[0]):
                            worst = (resid, c)
                    if worst is None or abs(worst[0]) <= limit:
                        status = 'CONVERGED'
                        break
                    resid, c = worst
                    mcount = collections.Counter(x['material'] for x in cur if x is not c)
                    if any(mcount[m] < 2 for m in refset):
                        status = 'LIMIT_STOP'
                        break
                    if len(removed) >= maxrej:
                        status = 'MAX_REJECT'
                        break
                    removed.append({'tray_position': c['tray'], 'material': c['material'],
                                    'residual': rnd(resid, 4)})
                    cur = [x for x in cur if x is not c]
                    slope, intercept = ls_fit([(x['x'], x['y']) for x in cur])
                    nfits += 1
                self.norm_fit[(sid, e)] = {'reference_set': refset, 'n_points': len(cur),
                                           'fits': nfits, 'slope': rnd(slope, 6) if slope is not None else None,
                                           'intercept': rnd(intercept, 6) if intercept is not None else None,
                                           'removed': removed, 'status': status}
        for v in self.inj.values():
            if v['session'] not in self.analytical:
                continue
            f = self.norm_fit.get((v['session'], v['element']))
            if f and f['status'] != 'NO_NORMALIZATION' and f['slope'] is not None:
                v['d_norm'] = rnd(f['slope'] * v['d_blank'] + f['intercept'], 3)
            else:
                v['d_norm'] = None

        # ---- H12 elemental
        self.factors = {}
        for sid in self.analytical:
            for e in self.elements:
                b = self.blank.get((sid, e), {'area': Fraction(0)})
                vals = []
                for v in self.inj.values():
                    if v['session'] != sid or v['element'] != e or v['excluded']:
                        continue
                    if v['material'] != 'ELM-ACT':
                        continue
                    cap = self.capsule.get(v['capsule'])
                    row = self.elemental_pct.get(norm(cap['lot'])) if cap else None
                    if row is None or v['mass'] is None:
                        continue
                    pct = dec(row['N_pct' if e == 'N' else 'C_pct'])
                    denom = v['area'] - b['area']
                    if denom == 0:
                        continue
                    vals.append((v['mass'] * 1000 * pct / 100) / denom)
                factor = rnd(mean(vals), 6) if vals else None
                self.factors[(sid, e)] = {'n_standards': len(vals), 'factor': factor}
        for v in self.inj.values():
            if v['session'] not in self.analytical:
                continue
            f = self.factors.get((v['session'], v['element']))
            b = self.blank.get((v['session'], v['element']), {'area': Fraction(0)})
            if v['material'] == 'ELM-ACT' or v['class'] == 'ELM':
                v['pct'] = None
            elif f and f['factor'] is not None and v['mass'] is not None and v['mass'] != 0:
                v['pct'] = rnd((v['area'] - b['area']) * f['factor'] / (v['mass'] * 1000) * 100, 3)
            else:
                v['pct'] = None

        # ---- H13 session acceptance
        self.acceptance = {}
        self.qc_checks = {}
        for sid in self.analytical:
            for e in self.elements:
                f = self.norm_fit[(sid, e)]
                reasons = []
                if f['status'] == 'NO_NORMALIZATION':
                    reasons.append('NO_NORMALIZATION')
                slope = f['slope']
                if slope is not None:
                    _, nrow = self.N2[e]
                    if not (dec(nrow['slope_min']) <= slope <= dec(nrow['slope_max'])):
                        reasons.append('SLOPE')
                checks = []
                for mat in self.qc_table_order(e):
                    vals = [v['d_norm'] for v in self.inj.values()
                            if v['session'] == sid and v['element'] == e
                            and not v['excluded'] and v['material'] == mat
                            and v.get('d_norm') is not None]
                    if not vals:
                        continue
                    mean_v = rnd(mean(vals), 3)
                    assigned = dec(self.qc_assigned[mat]['d15N_air' if e == 'N' else 'd13C_vpdb'])
                    dev = rnd(mean_v - assigned, 3)
                    tol = self.qc_tols.get((mat, e))
                    result = 'FAIL' if (tol is None or abs(dev) > tol) else 'PASS'
                    checks.append({'material': mat, 'n': len(vals), 'mean': mean_v,
                                   'assigned': assigned, 'deviation': dev,
                                   'tolerance': tol, 'result': result})
                    if result == 'FAIL':
                        reasons.append('QC:' + mat)
                if self.sessions[sid]['leak']:
                    reasons.append('LEAK')
                self.qc_checks[(sid, e)] = checks
                computed = 'ACCEPT' if not reasons else 'REJECT'
                self.acceptance[(sid, e)] = {'reasons': reasons, 'computed': computed}

        # rulings on decisions
        for (sid, e), a in self.acceptance.items():
            best = None
            for r in self.rulings:
                if norm(r['status']) != 'IN FORCE':
                    continue
                if norm(r['action']) not in ('ACCEPT_SESSION', 'REJECT_SESSION'):
                    continue
                if norm(r['project']) != norm(self.project):
                    continue
                if norm(r['element']) not in ('ALL', e):
                    continue
                tgt = self.alias.session(r['target'], norm(r['project']))
                if tgt != sid:
                    continue
                key = (r['date'], r['ruling'])
                if best is None or key > best[0]:
                    best = (key, r)
            a['ruling'] = best[1]['ruling'] if best else ''
            if best:
                a['decision'] = 'ACCEPT' if norm(best[1]['action']) == 'ACCEPT_SESSION' else 'REJECT'
            else:
                a['decision'] = a['computed']

    def qc_table_order(self, element):
        out = []
        for r in self.tables['Q-1']['rows']:
            mat = norm(r['material'])
            if norm(r['element']) != element:
                continue
            if mat in out:
                continue
            if mat == norm(self.drift_material):
                continue
            out.append(mat)
        return out

    # ---------------- H14 results

    def results(self):
        in_scope = [s for s in self.profile['samples_in_scope']]
        requests = collections.defaultdict(list)
        for r in parse_delimited(self.path('client_requests.tsv'), '\t'):
            requests[r['sample_ref'].strip()].append(r)
        self.results = {}
        self.screening = []
        for sid in in_scope:
            rec = {'sample_id': sid}
            srow = self.samples.get(sid)
            refs = [sid]
            if srow is not None:
                refs.append(srow['client_id'].strip())
            cands = []
            for ref in refs:
                for r in requests.get(ref, []):
                    if norm(r['status']) != 'ACTIVE':
                        continue
                    cands.append(r)
            if cands:
                cands.sort(key=lambda r: (r['requested_on'].strip(), r['request_id'].strip()))
                req = cands[-1]
                els = [x.strip().upper() for x in req['elements'].split('+')]
            else:
                req = None
                els = []
            rec['elements'] = els
            for e in self.elements:
                col = 'd15N_air' if e == 'N' else 'd13C_vpdb'
                if e not in els:
                    rec[e] = {'status': 'NOT_REQUESTED', 'n': None, 'mean': None,
                              'sd': None, 'pct': None, 'values': []}
                    continue
                vals = []
                for v in self.inj.values():
                    if v['material'] != sid or v['element'] != e or v['excluded']:
                        continue
                    if v['session'] not in self.analytical:
                        continue
                    if self.acceptance[(v['session'], e)]['decision'] != 'ACCEPT':
                        continue
                    if v.get('d_norm') is None:
                        continue
                    vals.append(v)
                vals.sort(key=lambda v: (self.sessions[v['session']]['start'], v['tray']))
                values = [v['d_norm'] for v in vals]
                screen = self.screen(values)
                kept = screen['kept']
                entry = {'status': None, 'n': len(kept), 'values': values,
                         'kept': kept, 'removed': screen['removed']}
                if len(kept) >= 2:
                    entry['status'] = 'REPORTED'
                    entry['mean'] = rnd(mean(kept), 2)
                    entry['sd'] = self.sample_sd(kept)
                elif len(kept) == 1:
                    entry['status'] = 'SINGLE'
                    entry['mean'] = rnd(mean(kept), 2)
                    entry['sd'] = None
                else:
                    entry['status'] = 'NO_DATA'
                    entry['mean'] = None
                    entry['sd'] = None
                pcts = [vals[i]['pct'] for i in screen['kept_idx']
                        if vals[i].get('pct') is not None]
                entry['pct'] = rnd(mean(pcts), 2) if pcts else None
                rec[e] = entry
                if values:
                    self.screening.append({'sample': sid, 'element': e,
                                           'initial_n': len(values),
                                           'values': values, 'removed': screen['removed'],
                                           'final_n': len(kept)})
            # C:N
            en, ec = self.elements[0], self.elements[1] if len(self.elements) > 1 else self.elements[0]
            pn = rec.get('N', {}).get('pct') if 'N' in rec else None
            pc = rec.get('C', {}).get('pct') if 'C' in rec else None
            stn = rec.get('N', {}).get('status')
            stc = rec.get('C', {}).get('status')
            if pn is not None and pc is not None and stn in ('REPORTED', 'SINGLE') \
                    and stc in ('REPORTED', 'SINGLE') and pn != 0:
                rec['cn'] = rnd((pc / self.molar['C']) / (pn / self.molar['N']), 2)
            else:
                rec['cn'] = None
            self.results[sid] = rec

    @staticmethod
    def sample_sd(vals):
        """n-1 standard deviation rounded to 2 decimals."""
        n = len(vals)
        mu = mean(vals)
        ss = sum((v - mu) ** 2 for v in vals) / (n - 1)
        return sqrt_round(ss, 2)

    def screen(self, values):
        """Grubbs screening (H14). Comparisons are exact on squared quantities."""
        vals = list(values)
        removed = []
        idx = list(range(len(vals)))
        while len(vals) >= 3:
            n = len(vals)
            mu = mean(vals)
            ss = sum((v - mu) ** 2 for v in vals) / (n - 1)
            if ss == 0:
                break
            best = None
            for i, v in enumerate(vals):
                d = abs(v - mu)
                if best is None or d > best[0]:
                    best = (d, i, v)
            d, i, v = best
            crit = self.grubbs.get(n)
            if crit is None or d * d > crit * crit * ss:
                removed.append({'value': v, 'g': self.g_stat(d, ss),
                                'g_crit': rnd(crit, 4), 'n': n})
                vals.pop(i)
                idx.pop(i)
            else:
                break
        return {'kept': vals, 'kept_idx': idx, 'removed': removed}

    @staticmethod
    def g_stat(d, ss):
        """G = d / sqrt(ss) rounded to 4 decimals."""
        import decimal
        ctx = decimal.Context(prec=80)
        dd = ctx.divide(decimal.Decimal(d.numerator), decimal.Decimal(d.denominator))
        s2 = ctx.divide(decimal.Decimal(ss.numerator), decimal.Decimal(ss.denominator))
        return round_dec(ctx.divide(dd, s2.sqrt()), 4)

    # ---------------- report data

    def ledger_rows(self):
        rows = []
        for v in self.inj.values():
            rows.append(v)
        rows.sort(key=lambda v: (v['session'], v['counter'], self.elements.index(v['element'])))
        return rows

    def position_rows(self):
        rows = []
        for sid in sorted(self.sessions.keys()):
            trays = sorted(set([t for (s, t) in self.position if s == sid]
                               + [t for (s, c), t in self.tray_of.items() if s == sid]))
            seq = self.sequences.get(sid)
            counters = self.sessions[sid].get('counters', {})
            tray_to_counter = {}
            for c, t in self.tray_of.items():
                if c[0] == sid:
                    tray_to_counter[t] = c[1]
            for tray in trays:
                pos = self.position[(sid, tray)]
                counter = tray_to_counter.get(tray)
                ex = False
                if counter is not None and (sid + '|' + str(counter)) in self.excluded:
                    ex = True
                status = 'SKIPPED' if counter is None else ('EXCLUDED' if ex else 'MEASURED')
                rows.append({'session': sid, 'tray': tray, 'counter': counter,
                             'token': pos['token'], 'seq': pos['seq'],
                             'material': pos['material'], 'class': pos['class'],
                             'capsule': pos['capsule'], 'mass': pos['mass'],
                             'status': status})
        return rows

    def alias_rows(self):
        """kind, token, canonical triples that need reporting."""
        seen_tokens = collections.defaultdict(set)
        for k, v in self.seen_tokens.items():
            seen_tokens[k] |= set(v)
        for sid, seq in self.sequences.items():
            seen_tokens['session'].add(norm(seq['token_id']))
            for tray, slot in seq['slots'].items():
                seen_tokens['material'].add(norm(slot['token']))
        for sid, entries in self.journal.items():
            for e in entries:
                seen_tokens['session'].add(norm(e.get('session')))
                if norm(e.get('field')) == 'TOKEN' and (e.get('value') or '').strip():
                    seen_tokens['material'].add(norm(e['value']))
        rows = set()
        for t in seen_tokens['session']:
            c = self.alias.session(t, self.project)
            if c != t:
                rows.add(('session', t, c))
        for t in seen_tokens['instrument']:
            c = self.alias.instrument(t)
            if c != t:
                rows.add(('instrument', t, c))
        for t in seen_tokens['material']:
            for c, vf in self.alias.material_paths(t, self.project):
                if c != t:
                    rows.add(('material', t, c))
        return sorted(rows, key=lambda r: (r[0], r[1], r[2]))

    def lineage_layout(self, fname):
        for l in self.lineage:
            if l['file'] == fname:
                return l['layout']
        return None

    # ---------------- comparison inputs

    def locate(self, name, signature):
        """Find an input file by preferred name, else by content signature."""
        p = self.path(name)
        if os.path.exists(p):
            return p
        for fn in sorted(os.listdir(self.dir)):
            fp = os.path.join(self.dir, fn)
            if not os.path.isfile(fp) or fn == name:
                continue
            try:
                head = open(fp, 'rb').read(4096)
            except OSError:
                continue
            if signature(head):
                return fp
        return p

    def load_published(self):
        pub = {}
        for r in parse_delimited(self.locate('published_results.csv',
                                             lambda h: h.startswith(b'sample_id,')), ','):
            pub[r['sample_id'].strip()] = r
        self.published = pub
        params = json.loads(read_text(self.locate(
            'published_session_params.json',
            lambda h: b'rm_points' in h and b'sessions' in h)))
        self.published_params = sorted(
            params['sessions'], key=lambda s: (self.alias.session(s['session'], self.project),
                                               self.elements.index(s['element'])))
        dash = collections.defaultdict(list)
        for r in parse_delimited(self.locate('qc_dashboard.csv',
                                             lambda h: b'dashboard_delta' in h), ','):
            sid = self.alias.session(r['session'], self.project)
            dash[(sid, r['element'].strip())].append(r)
        self.dashboard = dash
        cache = []
        for line in read_text(self.locate('lims_result_cache.jsonl',
                                          lambda h: b'cached_utc' in h)).splitlines():
            if line.strip():
                cache.append(json.loads(line))
        cache.sort(key=lambda o: (o['sample'], self.elements.index(o['element'])))
        self.cache = cache

    def rerun_settings(self):
        """The Run settings table of the saved rerun pack."""
        text = read_text(self.locate('rerun_pack.md',
                                     lambda h: b'Run settings' in h))
        rows = []
        section = False
        for line in text.splitlines():
            s = line.strip()
            if s.startswith('## '):
                section = s == '## Run settings'
                continue
            if not section or not s.startswith('|'):
                continue
            cells = [c.strip() for c in s.strip('|').split('|')]
            if all(re.fullmatch(r'[-: ]*', c) for c in cells):
                continue
            if not cells or cells[0].lower() == 'setting':
                continue
            if len(cells) >= 2:
                rows.append((cells[0], cells[1]))
        return rows

    def in_force_setting(self, key):
        if key == 'rm_sheet':
            return self.rm_sheet
        if key == 'normalization_table':
            return 'N-2'
        if key.startswith('reference_set_'):
            e = key.split('_')[-1]
            return ','.join(self.N2[e][0])
        if key == 'grubbs_table':
            return 'G-1'
        fixed = {
            'drift_axis': 'run_minutes',
            'linearity_partition': 'instrument_local_day',
            'correction_order': 'linearity,drift,blank,normalization',
            'revision_rule': 'audit_admitted',
            'autosampler_skips': 'applied',
            'session_rulings': 'R-1_in_force',
            'arithmetic': 'exact_decimal_stage_rounding',
        }
        return fixed.get(key)

    def notices(self):
        """REFERENCE notices with their parsed values."""
        out = []
        for line in read_text(self.locate('lab_noticeboard.txt',
                                          lambda h: b'notice | posted' in h)).splitlines():
            if '|' not in line:
                continue
            parts = [x.strip() for x in line.split('|')]
            if len(parts) < 4:
                continue
            if parts[2].upper() != 'REFERENCE':
                continue
            m = re.match(r'^(\S+)\s+lot\s+(\S+)\s+(d15N|d13C)\s+([-+0-9.]+)\s*permil', parts[3])
            if not m:
                continue
            out.append({'notice': parts[0], 'material': m.group(1), 'lot': m.group(2),
                        'element': m.group(3), 'value': m.group(4), 'posted': parts[1]})
        return out

    # ---------------- parameters_used

    def parameters_used(self):
        out = []
        clock = parse_yaml(read_text(self.path('site_clock.yaml')))
        out.append(('project', self.project))
        out.append(('rm_sheet', self.rm_sheet))
        out.append(('normalization_table', 'N-2'))
        for e in self.elements:
            out.append(('reference_set_' + e, ','.join(self.N2[e][0])))
        for e in self.elements:
            out.append(('reject_limit_' + e, self.N2[e][1]['reject_limit_permil'].strip()))
        for e in self.elements:
            out.append(('max_reject_' + e, self.N2[e][1]['max_rejections'].strip()))
        for e in self.elements:
            out.append(('linearity_threshold_' + e, self.L1[e]['threshold_permil_per_vs'].strip()))
        for e in self.elements:
            out.append(('a_ref_' + e, str(self.profile['a_ref_vs'][e]).strip()))
        for e in self.elements:
            out.append(('amplitude_min_' + e, self.A1[e]['amplitude_min_mv'].strip()))
        for e in self.elements:
            out.append(('amplitude_max_' + e, self.A1[e]['amplitude_max_mv'].strip()))
        for e in self.elements:
            out.append(('blank_area_max_' + e, self.A1[e]['blank_area_max_vs'].strip()))
        out.append(('slope_min', self.N2[self.elements[0]][1]['slope_min'].strip()))
        out.append(('slope_max', self.N2[self.elements[0]][1]['slope_max'].strip()))
        out.append(('linearity_lookback_days', str(self.profile['linearity_lookback_days']).strip()))
        out.append(('drift_material', self.drift_material))
        out.append(('drift_min_points', str(self.profile['drift_min_points']).strip()))
        out.append(('grubbs_table', 'G-1'))
        out.append(('grubbs_alpha', self.grubbs_alpha))
        out.append(('molar_mass_C', fmt(self.molar['C'], 4)))
        out.append(('molar_mass_N', fmt(self.molar['N'], 4)))
        out.append(('date_system', '1904' if self.workbook.date1904 else '1900'))
        out.append(('clock_base_offset', str(clock['base_offset']).strip()))
        for mat in self.qc_material_order():
            for e in self.elements:
                if (mat, e) in self.qc_tols:
                    out.append(('qc_tolerance_%s_%s' % (mat, e), self.qc_tol_text(mat, e)))
        return out

    def qc_tol_text(self, mat, e):
        for r in self.tables['Q-1']['rows']:
            if norm(r['material']) == mat and norm(r['element']) == e:
                return r['tolerance_permil'].strip()
        return ''

    def qc_material_order(self):
        out = []
        for r in self.tables['Q-1']['rows']:
            mat = norm(r['material'])
            if mat in out:
                continue
            out.append(mat)
        return [m for m in out if m != norm(self.drift_material)]

    # ---------------- report builders

    def report_injection_ledger(self):
        hdr = ['session', 'instrument', 'counter_position', 'tray_position', 'material',
               'element', 'revision', 'area_vs', 'amplitude_mv', 'delta_raw', 'utc_time',
               'run_minutes', 'excluded']
        lines = [','.join(hdr)]
        for v in self.ledger_rows():
            lines.append(','.join([
                v['session'], v['instrument'], str(v['counter']), str(v['tray']),
                v['material'], v['element'], str(v['rev']),
                fmt(v['area'], 4), str(int(v['amp'])), fmt(v['d_raw'], 3),
                utc_text(v['instant']), fmt(v['run_minutes'], 4), v['excluded'] or '']))
        return '\n'.join(lines) + '\n'

    def report_position_resolution(self):
        hdr = ['session', 'tray_position', 'counter_position', 'sequence_token', 'journal_seq',
               'material', 'material_class', 'capsule_id', 'mass_mg', 'status']
        lines = [','.join(hdr)]
        for r in self.position_rows():
            lines.append(','.join([
                r['session'], str(r['tray']), '' if r['counter'] is None else str(r['counter']),
                r['token'], '' if r['seq'] is None else str(r['seq']),
                r['material'], r['class'], r['capsule'],
                '' if r['mass'] is None else fmt(r['mass'], 4), r['status']]))
        return '\n'.join(lines) + '\n'

    def report_alias_resolution(self):
        lines = ['kind|token|canonical']
        for kind, token, canon in self.alias_rows():
            lines.append('%s|%s|%s' % (kind, token, canon))
        return '\n'.join(lines) + '\n'

    def report_dedup(self):
        c = self.counters
        return json.dumps({
            'files_read': c['files_read'], 'records_read': c['records_read'],
            'other_project': c['other_project'], 'reference_peaks': c['reference_peaks'],
            'inactive_segment': c['inactive_segment'], 'duplicates': c['duplicates'],
            'revisions_not_admitted': c['revisions_not_admitted'],
            'revisions_superseded': c['revisions_superseded'],
            'voided': c['voided'], 'kept': c['kept']}, indent=2) + '\n'

    def report_lineage(self):
        files = []
        for l in self.lineage:
            c = l['counts']
            files.append({'file': l['file'], 'layout': l['layout'],
                          'records': c['records'], 'other_project': c['other_project'],
                          'reference_peaks': c['reference_peaks'],
                          'inactive_segment': c['inactive_segment'],
                          'duplicates': c['duplicates'], 'unique': c['unique']})
        return json.dumps({'files': files}, indent=2) + '\n'

    def report_linearity(self):
        lins = []
        for sid in self.linearity_sessions:
            for e in self.elements:
                d = self.lin_slope[(sid, e)]
                lins.append({'session': sid, 'instrument': self.sessions[sid]['instrument'],
                             'local_date': day_to_date(self.sessions[sid]['date']).isoformat(),
                             'element': e, 'n_points': d['n_points'],
                             'slope': jnum(d['slope'], 6)})
        assigns = []
        for sid in self.analytical:
            for e in self.elements:
                a = self.lin_assignment[(sid, e)]
                assigns.append({'session': sid, 'element': e,
                                'lin_session': a['lin_session'],
                                'lin_slope': jnum(a['lin_slope'], 6),
                                'applied_slope': jnum(a['applied'], 6),
                                'status': a['status']})
        return json.dumps({'lin_sessions': lins, 'assignments': assigns}, indent=2) + '\n'

    def report_drift(self):
        lines = ['session\telement\tdrift_material\tn_points\tslope_per_min\tanchor_min\tstatus']
        for sid in self.analytical:
            for e in self.elements:
                d = self.drift[(sid, e)]
                lines.append('\t'.join([sid, e, self.drift_material, str(d['n_points']),
                                        fmt(d['slope'], 8), fmt(d['anchor'], 4), d['status']]))
        return '\n'.join(lines) + '\n'

    def report_blank(self):
        lines = ['session|element|n_blanks|n_rejected|mean_area_vs|mean_delta']
        for sid in self.analytical:
            for e in self.elements:
                d = self.blank[(sid, e)]
                lines.append('|'.join([sid, e, str(d['n_blanks']), str(d['n_rejected']),
                                       fmt(d['area'], 4), fmt(d['delta'], 3)]))
        return '\n'.join(lines) + '\n'

    def report_normalization(self):
        fits = []
        for sid in self.analytical:
            for e in self.elements:
                f = self.norm_fit[(sid, e)]
                fits.append({
                    'session': sid, 'element': e, 'reference_set': f['reference_set'],
                    'n_points': f['n_points'], 'fits': f['fits'],
                    'slope': jnum(f['slope'], 6), 'intercept': jnum(f['intercept'], 6),
                    'removed': [{'tray_position': r['tray_position'], 'material': r['material'],
                                 'residual': jnum(r['residual'], 4)} for r in f['removed']],
                    'status': f['status']})
        return json.dumps({'fits': fits}, indent=2) + '\n'

    def report_corrected(self):
        rows = []
        for v in self.inj.values():
            if v['session'] not in self.analytical:
                continue
            if v['excluded']:
                continue
            if v['class'] not in ('RM', 'QC', 'ELM', 'SAMPLE'):
                continue
            rows.append(v)
        rows.sort(key=lambda v: (v['session'], v['tray'], self.elements.index(v['element'])))
        out = []
        for v in rows:
            out.append(json.dumps({
                'session': v['session'], 'tray_position': v['tray'],
                'material': v['material'], 'material_class': v['class'],
                'element': v['element'], 'd_lin': jnum(v['d_lin'], 4),
                'd_drift': jnum(v['d_drift'], 4), 'd_blank': jnum(v['d_blank'], 4),
                'd_norm': jnum(v['d_norm'], 3), 'pct': jnum(v['pct'], 3)}))
        return '\n'.join(out) + ('\n' if out else '')

    def report_elemental(self):
        lines = ['session\telement\tn_standards\tfactor_ug_per_vs']
        for sid in self.analytical:
            for e in self.elements:
                f = self.factors[(sid, e)]
                lines.append('\t'.join([sid, e, str(f['n_standards']),
                                        '' if f['factor'] is None else fmt(f['factor'], 6)]))
        return '\n'.join(lines) + '\n'

    def report_acceptance(self):
        hdr = ['session', 'element', 'instrument', 'norm_slope', 'slope_ok', 'qc_checks',
               'leak', 'computed', 'ruling', 'decision', 'reasons']
        lines = [','.join(hdr)]
        for sid in self.analytical:
            for e in self.elements:
                a = self.acceptance[(sid, e)]
                f = self.norm_fit[(sid, e)]
                slope = f['slope']
                ok = ''
                if slope is not None:
                    _, nrow = self.N2[e]
                    ok = 'Y' if (dec(nrow['slope_min']) <= slope <= dec(nrow['slope_max'])) else 'N'
                checks = ';'.join('%s:%s:%s' % (c['material'], fmt(c['deviation'], 3), c['result'])
                                  for c in self.qc_checks[(sid, e)])
                lines.append(','.join([
                    sid, e, self.sessions[sid]['instrument'],
                    '' if slope is None else fmt(slope, 6), ok, checks,
                    'Y' if self.sessions[sid]['leak'] else 'N',
                    a['computed'], a['ruling'], a['decision'], ';'.join(a['reasons'])]))
        return '\n'.join(lines) + '\n'

    def report_qc_xml(self):
        out = ['<?xml version="1.0" encoding="UTF-8"?>',
               '<qc_results project="%s">' % self.project]
        for sid in self.analytical:
            for e in self.elements:
                for c in self.qc_checks[(sid, e)]:
                    out.append('  <check session="%s" element="%s" material="%s" n="%d" '
                               'mean="%s" assigned="%s" deviation="%s" tolerance="%s" '
                               'result="%s"/>' % (
                                   sid, e, c['material'], c['n'], fmt(c['mean'], 3),
                                   fmt(c['assigned'], 2), fmt(c['deviation'], 3),
                                   fmt(c['tolerance'], 2), c['result']))
        out.append('</qc_results>')
        return '\n'.join(out) + '\n'

    def report_isotope_results(self):
        hdr = ['sample_id', 'd15N_air', 'd15N_sd', 'n_N', 'pct_N', 'status_N',
               'd13C_vpdb', 'd13C_sd', 'n_C', 'pct_C', 'status_C', 'cn_molar']
        lines = [','.join(hdr)]

        def cell(entry, mean, sd, n, pct, status):
            return ','.join([
                '' if entry[mean] is None else fmt(entry[mean], 2),
                '' if entry[sd] is None else fmt(entry[sd], 2),
                '' if entry[n] is None else str(entry[n]),
                '' if entry[pct] is None else fmt(entry[pct], 2),
                entry[status]])
        for sid in sorted(self.results):
            r = self.results[sid]
            lines.append(','.join([sid, cell(r['N'], 'mean', 'sd', 'n', 'pct', 'status'),
                                   cell(r['C'], 'mean', 'sd', 'n', 'pct', 'status'),
                                   '' if r['cn'] is None else fmt(r['cn'], 2)]))
        return '\n'.join(lines) + '\n'

    def report_replicates(self):
        order = {s: i for i, s in enumerate(self.profile['samples_in_scope'])}
        rows = sorted(self.screening,
                      key=lambda s: (order.get(s['sample'], 1 << 30), self.elements.index(s['element'])))
        out = []
        for s in rows:
            out.append(json.dumps({
                'sample': s['sample'], 'element': s['element'], 'initial_n': s['initial_n'],
                'values': [jnum(v, 3) for v in s['values']],
                'removed': [{'value': jnum(r['value'], 3), 'g': jnum(r['g'], 4),
                             'g_crit': jnum(r['g_crit'], 4), 'n': r['n']}
                            for r in s['removed']],
                'final_n': s['final_n']}))
        return '\n'.join(out) + ('\n' if out else '')

    def report_parameters(self):
        return '\n'.join('%s: %s' % (k, v) for k, v in self.parameters_used()) + '\n'

    def report_variance(self):
        hdr = ['sample_id', 'element', 'published', 'recomputed', 'diff', 'status']
        lines = [','.join(hdr)]
        rows = []
        for sid in set(self.results) | set(self.published):
            for e in self.elements:
                r = self.results.get(sid, {}).get(e)
                pub = self.published.get(sid)
                pval = None
                if pub is not None:
                    col = 'd15N_air' if e == 'N' else 'd13C_vpdb'
                    if (pub.get(col) or '').strip():
                        pval = dec(pub[col])
                have_recomputed = bool(r) and r['status'] in ('REPORTED', 'SINGLE')
                if pval is None and not have_recomputed:
                    continue
                rows.append((sid, e, pval, r['mean'] if have_recomputed else None))
        rows.sort(key=lambda t: (t[0], self.elements.index(t[1])))
        for sid, e, pval, rval in rows:
            if pval is not None and rval is not None:
                diff = rnd(rval - pval, 2)
                status = 'MATCH' if abs(diff) <= dec('0.05') else 'DIFF'
                lines.append(','.join([sid, e, fmt(pval, 2), fmt(rval, 2), fmt(diff, 2), status]))
            elif pval is not None:
                lines.append(','.join([sid, e, fmt(pval, 2), '', '', 'ONLY_PUBLISHED']))
            else:
                lines.append(','.join([sid, e, '', fmt(rval, 2), '', 'ONLY_RECOMPUTED']))
        return '\n'.join(lines) + '\n'

    def report_session_param_diff(self):
        sessions = []
        for s in self.published_params:
            sid = self.alias.session(s['session'], self.project)
            e = s['element']
            f = self.norm_fit.get((sid, e))
            ps = dec(s['slope'])
            pi = dec(s['intercept'])
            rs = f['slope'] if f else None
            ri = f['intercept'] if f else None
            sessions.append({
                'session': sid, 'element': e,
                'published_slope': jnum(ps, 6),
                'recomputed_slope': jnum(rs, 6),
                'published_intercept': jnum(pi, 6),
                'recomputed_intercept': jnum(ri, 6),
                'slope_diff': jnum(rs - ps, 6) if rs is not None else None,
                'intercept_diff': jnum(ri - pi, 6) if ri is not None else None,
                'published_points': s.get('rm_points'),
                'recomputed_points': f['n_points'] if f else None})
        return json.dumps({'sessions': sessions}, indent=2) + '\n'

    def report_dashboard(self):
        hdr = ['session', 'element', 'dashboard_status', 'recomputed_decision', 'agrees']
        lines = [','.join(hdr)]
        keys = sorted(self.dashboard.keys(),
                      key=lambda k: (k[0], self.elements.index(k[1])))
        for (sid, e) in keys:
            rows = self.dashboard[(sid, e)]
            status = 'FAIL' if any(norm(r['status']) == 'FAIL' for r in rows) else 'PASS'
            a = self.acceptance.get((sid, e))
            dec_ = a['decision'] if a else 'REJECT'
            agrees = 'Y' if (status == 'PASS') == (dec_ == 'ACCEPT') else 'N'
            lines.append(','.join([sid, e, status, dec_, agrees]))
        return '\n'.join(lines) + '\n'

    def report_cache(self):
        out = []
        for o in self.cache:
            sid = o['sample']
            e = o['element']
            cached = dec(str(o['value']))
            r = self.results.get(sid, {}).get(e)
            rec = r['mean'] if (r and r['status'] in ('REPORTED', 'SINGLE')) else None
            status = 'CURRENT' if (rec is not None and abs(rnd(rec - cached, 2)) <= dec('0.05')) else 'STALE'
            out.append(json.dumps({'sample': sid, 'element': e,
                                   'cached': jnum(cached, 2),
                                   'recomputed': jnum(rec, 2), 'status': status}))
        return '\n'.join(out) + ('\n' if out else '')

    def report_reconciliation(self):
        pub_rows = []
        for e in self.elements:
            recomputed_reported = 0
            published_reported = 0
            compared = 0
            diff_count = 0
            shifts = []
            for sid in set(self.results) | set(self.published):
                entry = self.results.get(sid, {}).get(e)
                if entry is None:
                    pub = self.published.get(sid)
                    col = 'd15N_air' if e == 'N' else 'd13C_vpdb'
                    if pub and (pub.get(col) or '').strip():
                        published_reported += 1
                    continue
                pub = self.published.get(sid)
                col = 'd15N_air' if e == 'N' else 'd13C_vpdb'
                pval = dec(pub[col]) if pub and (pub.get(col) or '').strip() else None
                has_rec = entry['status'] in ('REPORTED', 'SINGLE')
                if has_rec:
                    recomputed_reported += 1
                if pval is not None:
                    published_reported += 1
                if pval is not None and has_rec:
                    compared += 1
                    d = rnd(entry['mean'] - pval, 2)
                    if abs(d) > dec('0.05'):
                        diff_count += 1
                    shifts.append(d)
            mean_shift = rnd(mean(shifts), 3) if shifts else Fraction(0)
            pub_rows.append([e, recomputed_reported, published_reported, compared,
                             diff_count, fmt(mean_shift, 3)])
        lines = ['# Reconciliation', '', '## Summary', '',
                 '| element | recomputed_reported | published_reported | compared | diff_count | mean_shift |',
                 '|---|---|---|---|---|---|']
        for r in pub_rows:
            lines.append('| ' + ' | '.join(str(x) for x in r) + ' |')
        lines += ['', '## Session decisions', '',
                  '| session | element | computed | ruling | decision | reasons |',
                  '|---|---|---|---|---|---|']
        for sid in self.analytical:
            for e in self.elements:
                a = self.acceptance[(sid, e)]
                if a['computed'] == 'REJECT' or a['decision'] == 'REJECT' or a['ruling']:
                    lines.append('| %s | %s | %s | %s | %s | %s |' % (
                        sid, e, a['computed'], a['ruling'], a['decision'],
                        ';'.join(a['reasons'])))
        lines += ['', '## Run settings', '',
                  '| setting | published_run | in_force |', '|---|---|---|']
        for key, val in self.rerun_settings():
            lines.append('| %s | %s | %s |' % (key, val, self.in_force_setting(key)))
        lines += ['', '## Superseded notices', '',
                  '| notice | material | lot | element | notice_value | in_force_value |',
                  '|---|---|---|---|---|---|']
        for n in sorted(self.notices(), key=lambda x: x['notice']):
            row = self.rm_value.get((norm(n['material']), norm(n['lot'])))
            if row is None:
                continue
            col = 'd15N_air' if n['element'] == 'd15N' else 'd13C_vpdb'
            inforce = dec(row[col])
            if inforce == dec(n['value']):
                continue
            lines.append('| %s | %s | %s | %s | %s | %s |' % (
                n['notice'], n['material'], n['lot'], n['element'], n['value'], fmt(inforce, 2)))
        return '\n'.join(lines) + '\n'

    def reports(self):
        out = []
        out.append(('injection_ledger.csv', self.report_injection_ledger()))
        out.append(('position_resolution.csv', self.report_position_resolution()))
        out.append(('alias_resolution.psv', self.report_alias_resolution()))
        out.append(('dedup_report.json', self.report_dedup()))
        out.append(('source_lineage.json', self.report_lineage()))
        out.append(('linearity_slopes.json', self.report_linearity()))
        out.append(('drift_fits.tsv', self.report_drift()))
        out.append(('blank_corrections.psv', self.report_blank()))
        out.append(('normalization_fits.json', self.report_normalization()))
        out.append(('corrected_injections.jsonl', self.report_corrected()))
        out.append(('elemental_factors.tsv', self.report_elemental()))
        out.append(('session_acceptance.csv', self.report_acceptance()))
        out.append(('qc_results.xml', self.report_qc_xml()))
        out.append(('isotope_results.csv', self.report_isotope_results()))
        out.append(('replicate_screening.jsonl', self.report_replicates()))
        out.append(('parameters_used.yaml', self.report_parameters()))
        out.append(('variance_vs_published.csv', self.report_variance()))
        out.append(('session_param_diff.json', self.report_session_param_diff()))
        out.append(('dashboard_disagreements.csv', self.report_dashboard()))
        out.append(('cache_divergence.jsonl', self.report_cache()))
        out.append(('reconciliation.md', self.report_reconciliation()))
        return out


def main():
    if len(sys.argv) != 3:
        sys.stderr.write('usage: run_irms.py DATA_DIR OUT_DIR\n')
        return 2
    data_dir, out_dir = sys.argv[1], sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)
    batch = Batch(data_dir)
    batch.compute()
    batch.results()
    batch.load_published()
    files = []
    for name, text in batch.reports():
        with open(os.path.join(out_dir, name), 'w', encoding='utf-8', newline='') as fh:
            fh.write(text)
        files.append((name, text))
    manifest = {'files': []}
    for name, text in files:
        data = text.encode('utf-8')
        manifest['files'].append({'name': name, 'bytes': len(data),
                                   'sha256': hashlib.sha256(data).hexdigest()})
    with open(os.path.join(out_dir, 'manifest.json'), 'w', encoding='utf-8', newline='') as fh:
        fh.write(json.dumps(manifest, indent=2) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
