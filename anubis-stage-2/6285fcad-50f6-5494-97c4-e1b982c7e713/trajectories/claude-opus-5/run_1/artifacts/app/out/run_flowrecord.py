#!/usr/bin/env python3
"""CBHS quarterly streamflow record computation (handbook revision 11).

Usage: run_flowrecord.py DATA_DIR OUT_DIR
"""
import csv
import datetime as dt
import hashlib
import json
import math
import os
import re
import sqlite3
import sys
import xml.etree.ElementTree as ET
import zipfile
import zlib
from decimal import Decimal
from fractions import Fraction

# ---------------------------------------------------------------- numbers


def _round_half_even(num, den):
    q, r = divmod(num, den)
    twice = 2 * r
    if twice > den or (twice == den and q % 2 == 1):
        q += 1
    return q


def rnd(x, nd):
    """Round a Fraction/int/Decimal to nd decimals, half to even -> Decimal."""
    f = Fraction(x) * Fraction(10) ** nd
    q = _round_half_even(f.numerator, f.denominator)
    return Decimal(q).scaleb(-nd)


def dec_exp10(a):
    """Exponent e with 10**e <= a < 10**(e+1), a > 0."""
    e = 0
    ten = Fraction(10)
    while a >= ten:
        a /= ten
        e += 1
    while a < 1:
        a *= ten
        e -= 1
    return e


def sigfig(x, n):
    f = Fraction(x)
    if f == 0:
        return Decimal(0).scaleb(-(n - 1))
    e = dec_exp10(abs(f))
    return rnd(f, n - 1 - e)


def fmt(d):
    return format(d, 'f')


def disch(x):
    a = abs(Fraction(x))
    if a < 1:
        return rnd(x, 2)
    if a < 10:
        return rnd(x, 1)
    if a < 1000:
        return rnd(x, 0)
    return sigfig(x, 3)


def F(s):
    """Exact Fraction from decimal text or number."""
    if isinstance(s, Fraction):
        return s
    if isinstance(s, float):
        return Fraction(Decimal(repr(s)))
    if isinstance(s, (int, Decimal)):
        return Fraction(s)
    return Fraction(Decimal(str(s).strip()))


def dstr(s):
    """Normalised plain-decimal text of a numeric cell."""
    return format(Decimal(str(s).strip()), 'f')


# ---------------------------------------------------------------- JSON out


class Raw(object):
    __slots__ = ('text',)

    def __init__(self, text):
        self.text = text


def jenc(o, indent=0, compact=False):
    sp = '' if compact else ' ' * indent
    nl = '' if compact else '\n'
    pad = '' if compact else ' ' * (indent + 2)
    if isinstance(o, Raw):
        return o.text
    if o is None:
        return 'null'
    if o is True:
        return 'true'
    if o is False:
        return 'false'
    if isinstance(o, str):
        return json.dumps(o, ensure_ascii=False)
    if isinstance(o, int):
        return str(o)
    if isinstance(o, dict):
        if not o:
            return '{}'
        items = [pad + json.dumps(str(k), ensure_ascii=False) + ': ' +
                 jenc(v, indent + 2, compact) for k, v in o.items()]
        return '{' + nl + (', ' if compact else ',' + nl).join(items) + nl + sp + '}'
    if isinstance(o, (list, tuple)):
        if not o:
            return '[]'
        items = [pad + jenc(v, indent + 2, compact) for v in o]
        return '[' + nl + (', ' if compact else ',' + nl).join(items) + nl + sp + ']'
    raise TypeError(repr(o))


def jline(o):
    return jenc(o, 0, True)


# ---------------------------------------------------------------- mini YAML


def _strip_comment(s):
    out = []
    q = None
    for i, c in enumerate(s):
        if q:
            out.append(c)
            if c == q:
                q = None
        elif c in '"\'':
            q = c
            out.append(c)
        elif c == '#' and (i == 0 or s[i - 1] in ' \t'):
            break
        else:
            out.append(c)
    return ''.join(out).rstrip()


def _scalar(s):
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in '"\'':
        return s[1:-1]
    if s in ('null', '~', ''):
        return None
    return s


def _split_kv(s):
    """Split 'key: value' at the first colon outside quotes and brackets."""
    q = None
    depth = 0
    for i, c in enumerate(s):
        if q:
            if c == q:
                q = None
            continue
        if c in '"\'':
            q = c
        elif c in '[{':
            depth += 1
        elif c in ']}':
            depth -= 1
        elif c == ':' and depth == 0 and (i + 1 == len(s) or s[i + 1] in ' \t'):
            return s[:i], s[i + 1:]
    return s, ''


def _split_flow(s):
    parts = []
    depth = 0
    q = None
    cur = ''
    for c in s:
        if q:
            cur += c
            if c == q:
                q = None
            continue
        if c in '"\'':
            q = c
            cur += c
            continue
        if c in '[{':
            depth += 1
        elif c in ']}':
            depth -= 1
        if c == ',' and depth == 0:
            parts.append(cur)
            cur = ''
        else:
            cur += c
    if cur.strip():
        parts.append(cur)
    return parts


def _parse_value(s):
    s = s.strip()
    if s.startswith('['):
        return [_parse_value(p) for p in _split_flow(s[1:-1])]
    if s.startswith('{'):
        d = {}
        for p in _split_flow(s[1:-1]):
            if not p.strip():
                continue
            k, v = _split_kv(p.strip())
            d[_scalar(k)] = _parse_value(v)
        return d
    return _scalar(s)


def yaml_load(text):
    lines = []
    for raw in text.split('\n'):
        if not raw.strip() or raw.lstrip().startswith('#'):
            continue
        body = _strip_comment(raw)
        if not body.strip():
            continue
        indent = len(body) - len(body.lstrip(' '))
        lines.append((indent, body.strip()))

    def mapping_entry(i, d):
        key, val = _split_kv(lines[i][1])
        key = _scalar(key)
        ind = lines[i][0]
        if val.strip():
            d[key] = _parse_value(val)
            return i + 1
        i += 1
        if i < len(lines) and lines[i][0] > ind:
            v, i = block(i, lines[i][0])
        else:
            v = None
        d[key] = v
        return i

    def block(i, indent):
        if i >= len(lines):
            return None, i
        if lines[i][1].startswith('- '):
            seq = []
            while i < len(lines) and lines[i][0] == indent and lines[i][1].startswith('- '):
                item = lines[i][1][2:].strip()
                if item.startswith('[') or item.startswith('{'):
                    seq.append(_parse_value(item))
                    i += 1
                elif _split_kv(item)[0] != item:
                    d = {}
                    key, val = _split_kv(item)
                    if val.strip():
                        d[_scalar(key)] = _parse_value(val)
                        i += 1
                    else:
                        i += 1
                        if i < len(lines) and lines[i][0] > indent:
                            v, i = block(i, lines[i][0])
                        else:
                            v = None
                        d[_scalar(key)] = v
                    while (i < len(lines) and lines[i][0] > indent
                           and not lines[i][1].startswith('- ')):
                        i = mapping_entry(i, d)
                    seq.append(d)
                else:
                    seq.append(_scalar(item))
                    i += 1
            return seq, i
        d = {}
        while i < len(lines) and lines[i][0] == indent and not lines[i][1].startswith('- '):
            i = mapping_entry(i, d)
        return d, i

    val, _ = block(0, lines[0][0] if lines else 0)
    return val


# ---------------------------------------------------------------- xlsx

XNS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
XNSR = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'


class Workbook(object):
    def __init__(self, path):
        self.z = zipfile.ZipFile(path)
        wb = ET.fromstring(self.z.read('xl/workbook.xml'))
        pr = wb.find(XNS + 'workbookPr')
        flag = pr.get('date1904') if pr is not None else None
        self.date1904 = str(flag).strip().lower() in ('1', 'true')
        rels = {}
        for r in ET.fromstring(self.z.read('xl/_rels/workbook.xml.rels')):
            rels[r.get('Id')] = r.get('Target')
        self.sheets = {}
        for s in wb.find(XNS + 'sheets'):
            t = rels[s.get(XNSR + 'id')]
            if t.startswith('/'):
                t = t[1:]
            elif not t.startswith('xl/'):
                t = 'xl/' + t
            self.sheets[s.get('name')] = t
        self.ss = []
        try:
            sst = ET.fromstring(self.z.read('xl/sharedStrings.xml'))
        except KeyError:
            sst = []
        for si in sst:
            self.ss.append(''.join(t.text or '' for t in si.iter(XNS + 't')))

    def rows(self, name):
        sh = ET.fromstring(self.z.read(self.sheets[name]))
        out = []
        for row in sh.iter(XNS + 'row'):
            cells = {}
            for c in row.iter(XNS + 'c'):
                ref = c.get('r') or ''
                t = c.get('t')
                v = c.find(XNS + 'v')
                isel = c.find(XNS + 'is')
                if t == 's' and v is not None:
                    val = self.ss[int(v.text)]
                elif t == 'inlineStr':
                    val = ''.join(x.text or '' for x in isel.iter(XNS + 't')) \
                        if isel is not None else ''
                elif v is not None:
                    val = v.text
                else:
                    val = None
                m = re.match(r'([A-Z]+)', ref)
                if val is not None and str(val).strip() != '':
                    cells[m.group(1) if m else ''] = val
            out.append(cells)
        return out

    def table(self, name):
        """Rows after the header row as dicts keyed by header text."""
        hdr = None
        out = []
        for cells in self.rows(name):
            if hdr is None:
                if len(cells) >= 2:
                    hdr = {c: str(v).strip() for c, v in cells.items()}
                continue
            if len(cells) < 2:
                continue
            out.append({h: cells.get(c) for c, h in hdr.items()})
        return out


# ---------------------------------------------------------------- pdf tables


def _pdf_strings(s):
    out = []
    i = 0
    while i < len(s):
        c = s[i]
        if c == '(':
            depth = 1
            i += 1
            buf = ''
            while i < len(s) and depth > 0:
                ch = s[i]
                if ch == '\\':
                    buf += s[i + 1]
                    i += 2
                    continue
                if ch == '(':
                    depth += 1
                elif ch == ')':
                    depth -= 1
                    if depth == 0:
                        i += 1
                        break
                buf += ch
                i += 1
            out.append(buf)
        elif c == '<':
            j = s.index('>', i)
            out.append(bytes.fromhex(re.sub(r'\s', '', s[i + 1:j])).decode('latin-1'))
            i = j + 1
        else:
            i += 1
    return ''.join(out)


def pdf_pages(path):
    data = open(path, 'rb').read()
    pages = []
    for m in re.finditer(rb'<<(.*?)>>\s*stream\r?\n', data, re.S):
        hdr = m.group(1)
        start = m.end()
        raw = data[start:data.find(b'endstream', start)]
        if b'FlateDecode' in hdr:
            try:
                raw = zlib.decompress(raw)
            except zlib.error:
                continue
        txt = raw.decode('latin-1')
        items = []
        for bm in re.finditer(r'BT(.*?)ET', txt, re.S):
            b = bm.group(1)
            tm = re.search(r'([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)'
                           r'\s+([-\d.]+)\s+Tm', b)
            if not tm:
                continue
            x = float(tm.group(5))
            y = float(tm.group(6))
            rest = b[tm.end():]
            mm = re.search(r'\[(.*?)\]\s*TJ', rest, re.S)
            if mm:
                s = _pdf_strings(mm.group(1))
            else:
                mm = re.search(r'(\(.*?\)|<[0-9A-Fa-f\s]*>)\s*Tj', rest, re.S)
                s = _pdf_strings(mm.group(1)) if mm else ''
            items.append((y, x, s.strip()))
        if items:
            pages.append(items)
    return pages


def pdf_tables(path):
    """{table_id: {'status', 'header', 'rows'}} from a minutes PDF."""
    tables = {}
    cur = None
    for items in pdf_pages(path):
        rows = {}
        for y, x, s in items:
            if s == '':
                continue
            rows.setdefault(y, []).append((x, s))
        for y in sorted(rows, reverse=True):
            cells = sorted(rows[y])
            text = cells[0][1]
            if len(cells) < 2:
                m = re.match(r'^Table\s+(\S+?):\s*(.*?)\[([^\]]*)\]\s*$', text)
                if m:
                    tid = m.group(1)
                    tables[tid] = {'status': m.group(3).strip().upper(), 'header': None,
                                   'rows': []}
                    cur = tid
                    continue
                m = re.match(r'^Table\s+(\S+?)\s*\(continued\)\s*$', text)
                if m:
                    cur = m.group(1) if m.group(1) in tables else None
                    if cur:
                        tables[cur]['header'] = None
                    continue
                continue
            if cur is None:
                continue
            t = tables[cur]
            cols = [c[0] for c in cells]
            vals = [c[1] for c in cells]
            if t['header'] is None:
                t['header'] = (cols, vals)
                continue
            hcols, hnames = t['header']
            d = {name: '' for name in hnames}
            for col, val in zip(cols, vals):
                best = min(range(len(hcols)), key=lambda k: abs(hcols[k] - col))
                d[hnames[best]] = val
            t['rows'].append(d)
    return tables


# ---------------------------------------------------------------- clock

EPOCH = dt.datetime(1970, 1, 1)


def naive(d):
    return int((d - EPOCH).total_seconds())


def iso_utc(s):
    s = str(s).strip()
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2}))?'
                 r'(Z|z|[+-]\d{2}:?\d{2})?$', s)
    if not m:
        raise ValueError('time %r' % s)
    base = naive(dt.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                             int(m.group(4)), int(m.group(5)), int(m.group(6) or 0)))
    off = m.group(7)
    if off in (None, 'Z', 'z'):
        return base
    sign = 1 if off[0] == '+' else -1
    off = off[1:].replace(':', '')
    return base - sign * (int(off[:2]) * 3600 + int(off[2:]) * 60)


def iso_naive(s):
    s = str(s).strip()
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2}))?$', s)
    if not m:
        raise ValueError('time %r' % s)
    return naive(dt.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                             int(m.group(4)), int(m.group(5)), int(m.group(6) or 0)))


def fmt_time(lst_epoch):
    return (EPOCH + dt.timedelta(seconds=lst_epoch)).strftime('%Y-%m-%d %H:%M')


class Clock(object):
    def __init__(self, cfg):
        self.offset = int(str(cfg['standard_offset_minutes']).strip()) * 60
        self.rule = str(cfg['dst_rule']).strip()
        self.spans = sorted((iso_utc(tr['start_utc']), iso_utc(tr['end_utc']))
                            for tr in (cfg.get('transitions') or []))

    def is_dst(self, u):
        for a, b in self.spans:
            if a <= u < b:
                return True
        return False

    def lst(self, u):
        return u + self.offset

    def utc_from_lst(self, l):
        return l - self.offset

    def utc_from_wall(self, w):
        u2 = w - 3600 - self.offset
        if self.is_dst(u2):
            return u2
        return w - self.offset


def serial_to_lst(serial, date1904):
    base = naive(dt.datetime(1904, 1, 1) if date1904 else dt.datetime(1899, 12, 30))
    secs = F(serial) * 86400 / 60
    return base + _round_half_even(secs.numerator, secs.denominator) * 60


# ---------------------------------------------------------------- units

FT_PER = {'FT': Fraction(1), 'M': Fraction(10000, 3048),
          'CM': Fraction(100, 3048), 'MM': Fraction(10, 3048)}


def norm_unit(u):
    if u is None:
        return None
    u = str(u).strip().upper()
    if u in ('FT', 'FEET'):
        return 'FT'
    if u in ('M', 'METRE', 'METER'):
        return 'M'
    if u in ('CM', 'MM'):
        return u
    raise ValueError('unit %r' % u)


def to_ft(value, unit):
    return F(value) * FT_PER[unit]


# ---------------------------------------------------------------- tokens


def norm_token(tok):
    t = str(tok).strip().upper()
    if t.isdigit() and len(t) < 8:
        t = t.rjust(8, '0')
    return t


class Resolver(object):
    def __init__(self, master_ids, rows):
        self.master = master_ids
        self.rows = {}
        for tok, target, vf, vt in rows:
            self.rows.setdefault(tok, []).append((vf, vt, target))
        for v in self.rows.values():
            v.sort()
        self.cache = {}

    def _row(self, tok, u):
        for vf, vt, target in self.rows.get(tok, ()):
            if vf <= u and (vt is None or u < vt):
                return target
        return None

    def resolve(self, tok, u):
        key = (tok, u)
        if key in self.cache:
            return self.cache[key]
        cur = norm_token(tok)
        res = None
        for hops in range(7):
            if cur in self.master:
                res = cur
                break
            if hops == 6:
                break
            target = self._row(cur, u)
            if target is None:
                break
            cur = norm_token(target)
        self.cache[key] = res
        return res


# ---------------------------------------------------------------- shards

QUAL = {
    'GSEX': {'G': 'G', 'S': 'S', 'E': 'E', 'X': 'X'},
    'L03': {'OK': 'G', 'SUS': 'S', 'EST': 'E', 'FLT': 'X'},
    'L04': {'A': 'G', 'S': 'S', 'E': 'E', 'F': 'X'},
    'L05': {'0': 'G', '1': 'S', '2': 'E', '9': 'X'},
    'L08': {'GOOD': 'G', 'SUSPECT': 'S', 'ESTIMATED': 'E', 'FAULT': 'X'},
    'L11': {'GOOD': 'G', 'SUSP': 'S', 'EST': 'E', 'FAULT': 'X'},
    'L12': {'10': 'G', '30': 'S', '40': 'E', '90': 'X'},
    'L19': {'': 'G', 'S': 'S', 'E': 'E', 'X': 'X'},
}


class Rec(object):
    __slots__ = ('tok', 'sensor', 'u', 'val', 'unit', 'q', 'rev', 'void', 'idx')

    def __init__(self, tok, sensor, u, val, unit, q, rev, void, idx):
        self.tok = tok
        self.sensor = sensor
        self.u = u
        self.val = val
        self.unit = unit
        self.q = q
        self.rev = rev
        self.void = void
        self.idx = idx


def read_shard(path, layout, clock):
    recs = []

    def add(tok, sensor, u, val, unit, q, rev, void):
        recs.append(Rec(tok, sensor, u, None if val is None else str(val).strip(),
                        unit, q, int(str(rev).strip()), void, len(recs)))

    if layout == 'L01':
        hdr = None
        for line in open(path):
            line = line.rstrip('\n')
            if not line.strip() or line.startswith('#'):
                continue
            parts = next(csv.reader([line]))
            if hdr is None:
                hdr = parts
                continue
            d = dict(zip(hdr, parts))
            void = str(d['void']).strip() == '1'
            add(d['station'], d['sensor'].strip().upper(), iso_utc(d['obs_utc']),
                None if void else d['stage'], None, QUAL['GSEX'][d['qual'].strip().upper()],
                d['rev'], void)
    elif layout == 'L02':
        with open(path, newline='') as fh:
            for d in csv.DictReader(fh):
                if str(d['hour']).strip().upper() == 'MEAN':
                    continue
                hour = int(str(d['hour']).strip())
                unit = norm_unit(d['unit'])
                for mi, key in ((0, 'm00'), (15, 'm15'), (30, 'm30'), (45, 'm45')):
                    v = d.get(key)
                    if v is None or str(v).strip() == '':
                        continue
                    lst = iso_naive('%s %02d:%02d' % (str(d['date_lst']).strip(), hour, mi))
                    add(d['site_id'], 'P', clock.utc_from_lst(lst), v, unit, 'G', d['rev'], False)
    elif layout == 'L03':
        hdr = None
        for line in open(path):
            line = line.rstrip('\n')
            if not line.strip() or line.startswith('#'):
                continue
            parts = line.split('\t')
            if hdr is None:
                hdr = parts
                continue
            d = dict(zip(hdr, parts))
            void = d['status'].strip().upper() == 'VOID'
            add(d['gauge'], 'P' if d['chan'].strip() == '1' else 'B', int(d['t_epoch']),
                None if void else d['h'].strip().replace(',', '.'), norm_unit(d['unit']),
                QUAL['L03'][d['flag'].strip().upper()], d['revision'], void)
    elif layout == 'L04':
        hdr = None
        for line in open(path):
            line = line.rstrip('\n')
            if not line.strip():
                continue
            parts = line.split('\t')
            if hdr is None:
                hdr = parts
                continue
            if [p.strip() for p in parts[:2]] == [h.strip() for h in hdr[:2]]:
                continue
            d = dict(zip(hdr, parts))
            add(d['STN'], 'P' if d['SENSOR'].strip().upper() == 'PRI' else 'B',
                clock.utc_from_wall(iso_naive(d['WALLCLOCK'])), d['GH'], None,
                QUAL['L04'][d['Q'].strip().upper()], d['REV'], False)
    elif layout == 'L05':
        hdr = None
        for line in open(path):
            line = line.rstrip('\n')
            if not line.strip():
                continue
            parts = line.split('|')
            if hdr is None:
                hdr = parts
                continue
            d = dict(zip(hdr, parts))
            void = d['vd'].strip().upper() == 'Y'
            add(d['site'], 'P' if d['sens'].strip() == '1' else 'B', int(d['ts_ms']) // 1000,
                None if void else d['value_cm'], 'CM', QUAL['L05'][d['q'].strip()],
                d['rv'], void)
    elif layout == 'L06':
        hdr = None
        for line in open(path):
            line = line.rstrip('\n')
            if not line.strip():
                continue
            parts = line.split('|')
            if hdr is None:
                hdr = parts
                continue
            d = dict(zip(hdr, parts))
            m = re.match(r'^\s*(-?[\d.]+)\s*([A-Za-z]+)\s*$', d['stage'])
            add(d['alias'], 'P', iso_utc(d['when']), m.group(1), norm_unit(m.group(2)),
                QUAL['GSEX'][d['code'].strip().upper()], d['ver'], False)
    elif layout == 'L07':
        for line in open(path):
            line = line.strip()
            if not line:
                continue
            o = json.loads(line)
            if str(o.get('type', '')).strip().lower() == 'hb':
                continue
            void = bool(o.get('x'))
            t = str(o['t']).strip()
            lst = iso_naive('%s-%s-%s %s:%s' % (t[0:4], t[4:6], t[6:8], t[9:11], t[11:13]))
            add(o['s'], str(o['k']).strip().upper(), clock.utc_from_lst(lst),
                None if void else o.get('v'), norm_unit(o.get('u')),
                QUAL['GSEX'][str(o['q']).strip().upper()], o.get('r', 1), void)
    elif layout == 'L08':
        for line in open(path):
            line = line.strip()
            if not line:
                continue
            o = json.loads(line)
            meta = o.get('meta', {})
            gh = o['reading']['gh']
            val = gh.get('value')
            void = bool(meta.get('void')) or val is None
            add(o['station']['id'],
                'P' if str(meta['channel']).strip().lower() == 'primary' else 'B',
                iso_utc(o['reading']['time_utc']), None if void else val,
                norm_unit(gh.get('unit')), QUAL['L08'][str(meta['quality']).strip().upper()],
                meta.get('rev', 1), void)
    elif layout == 'L09':
        for line in open(path):
            line = line.strip()
            if not line:
                continue
            o = json.loads(line)
            base = iso_naive(str(o['hour_utc']).strip().replace('T', ' ') + ':00')
            unit = norm_unit(o.get('unit'))
            for k, v in enumerate(o['vals']):
                if v is None:
                    continue
                add(o['site'], 'P', base + k * 900, v, unit, 'G', o.get('rev', 1), False)
    elif layout == 'L10':
        for line in open(path):
            line = line.strip()
            if not line:
                continue
            o = json.loads(line)
            void = str(o.get('deleted', 0)).strip().lower() in ('1', 'true')
            if o.get('stage_m') is None:
                void = True
            add(o['id'], 'B', int(o['epoch']), None if void else o.get('stage_m'), 'M',
                QUAL['GSEX'][str(o['qa']).strip().upper()], o.get('rev', 1), void)
    elif layout == 'L11':
        for site in ET.parse(path).getroot().iter('site'):
            tok = site.get('code')
            for r in site.iter('r'):
                void = str(r.get('void', '0')).strip() == '1'
                add(tok, str(r.get('s')).strip().upper(), iso_utc(r.get('t')),
                    None if void else r.get('v'), None,
                    QUAL['L11'][str(r.get('q')).strip().upper()], r.get('rev', 1), void)
    elif layout == 'L12':
        for rd in ET.parse(path).getroot().iter('reading'):
            tel = rd.find('time')
            zone = str(tel.get('zone')).strip().upper()
            m = re.match(r'^\s*(\d{2})/(\d{2})/(\d{4})\s+(\d{2}):(\d{2})\s*$', tel.text)
            t = naive(dt.datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)),
                                  int(m.group(4)), int(m.group(5))))
            if zone == 'UTC':
                u = t
            elif zone == 'LST':
                u = clock.utc_from_lst(t)
            else:
                u = clock.utc_from_wall(t)
            vel = rd.find('value')
            add(rd.findtext('station'), 'P', u, vel.text, norm_unit(vel.get('unit')),
                QUAL['L12'][rd.findtext('qual').strip()], rd.findtext('rev'), False)
    elif layout == 'L13':
        for line in open(path):
            line = line.rstrip('\n')
            s = line.strip()
            if (not s or s.startswith('CBHS') or s.startswith('STATION')
                    or s.startswith('---') or s.startswith('PAGE')
                    or s.startswith('END OF REPORT')):
                continue
            lst = iso_naive('%s %s:%s' % (line[10:20].strip(), line[21:25].strip()[:2],
                                          line[21:25].strip()[2:]))
            add(line[0:10].strip(), 'P', clock.utc_from_lst(lst), line[26:33].strip(),
                norm_unit(line[34:36]), QUAL['GSEX'][line[37:38].strip().upper()],
                line[39:41].strip(), False)
    elif layout == 'L14':
        for line in open(path):
            line = line.strip()
            if not line or line.startswith('NOTE'):
                continue
            if line.startswith('VOID'):
                d = dict(re.findall(r'(\w+)=(\S+)', line))
                add(d['stn'], d['sensor'].strip().upper(), iso_utc(d['t']), None, None,
                    'G', d['rev'], True)
                continue
            m = re.match(r'^(.*?)\s+stn=(\S+)\s+sensor=(\S+)\s+gh=(-?[\d.]+)\s*([A-Za-z]+)'
                         r'\s+q=(\S+)\s+rev=(\d+)\s*$', line)
            add(m.group(2), m.group(3).strip().upper(), iso_utc(m.group(1)), m.group(4),
                norm_unit(m.group(5)), QUAL['GSEX'][m.group(6).strip().upper()],
                m.group(7), False)
    elif layout == 'L15':
        for blk in yaml_load(open(path).read())['blocks']:
            sensor = 'P' if str(blk['sensor']).strip().lower() == 'primary' else 'B'
            unit = norm_unit(blk['unit'])
            for row in blk['rows']:
                add(blk['station'], sensor, int(str(row[0]).strip()), row[1], unit,
                    QUAL['GSEX'][str(row[2]).strip().upper()], row[3], False)
    elif layout == 'L16':
        doc = yaml_load(open(path).read())
        for tok, minutes in doc['stations'].items():
            for key, val in minutes.items():
                u = iso_utc(key)
                for e in (val if isinstance(val, list) else [val]):
                    add(tok, 'P', u, e['v'], norm_unit(e['u']), 'G', e.get('r', 1), False)
    elif layout == 'L17':
        doc = json.load(open(path))
        default_unit = norm_unit(doc.get('meta', {}).get('unit'))
        for run in doc['series']:
            unit = norm_unit(run['unit']) if run.get('unit') else default_unit
            start = int(run['start'])
            step = int(run['step'])
            sensor = str(run.get('sensor', 'P')).strip().upper()
            for k, v in enumerate(run['values']):
                if v is None:
                    continue
                add(run['site'], sensor, start + k * step, v, unit, 'G',
                    run.get('rev', 1), False)
    elif layout == 'L18':
        con = sqlite3.connect('file:%s?mode=ro' % path, uri=True)
        sites = dict(con.execute('select sid, token from sites'))
        for sid, sensor, t_serial, value, unit, q, rev, void in con.execute(
                'select sid, sensor, t_serial, value, unit, q, rev, void from readings '
                'order by rid'):
            isvoid = str(void).strip() in ('1', 'True')
            lst = serial_to_lst(repr(t_serial) if isinstance(t_serial, float) else t_serial,
                                False)
            val = None
            if value is not None:
                val = repr(value) if isinstance(value, float) else str(value)
            add(sites[sid], str(sensor).strip().upper(), clock.utc_from_lst(lst),
                None if isvoid else val, norm_unit(unit),
                QUAL['GSEX'][str(q).strip().upper()], rev, isvoid)
        con.close()
    elif layout == 'L19':
        con = sqlite3.connect('file:%s?mode=ro' % path, uri=True)
        for stn, ts, gh_mm, sensor, rev, flag in con.execute(
                'select stn, ts, gh_mm, sensor, rev, flag from obs'):
            add(stn, str(sensor).strip().upper(), int(ts), gh_mm, 'MM',
                QUAL['L19'][str(flag or '').strip().upper()], rev, False)
        for stn, ts, sensor, rev in con.execute('select stn, ts, sensor, rev from voids'):
            add(stn, str(sensor).strip().upper(), int(ts), None, None, 'G', rev, True)
        con.close()
    elif layout == 'L20':
        with open(path, newline='') as fh:
            for d in csv.DictReader(fh):
                add(d['site'], 'P', clock.utc_from_lst(iso_naive(d['time_lst'])),
                    d['gh_ft'], 'FT', 'G', 1, False)
    else:
        raise ValueError('layout %s' % layout)
    return recs


# ---------------------------------------------------------------- rating


class Rating(object):
    def __init__(self, rating_id, site, eff_lst, points, texts):
        self.rating_id = rating_id
        self.site = site
        self.eff = eff_lst
        self.points = points
        self.texts = texts
        self.fp = [(float(g), float(q), float(e)) for g, q, e in points]

    def _seg(self, h):
        p = self.fp
        if h < p[0][0]:
            return 0
        for i in range(len(p) - 1):
            if p[i][0] <= h < p[i + 1][0]:
                return i
        return len(p) - 2

    def eval(self, gh):
        h = float(gh)
        p = self.fp
        for g, q, e in p:
            if h == g:
                return sigfig(F(q), 4)
        if len(p) == 1:
            return sigfig(F(p[0][1]), 4)
        i = self._seg(h)
        g0, q0, e0 = p[i]
        if h < p[0][0] and h <= e0:
            return sigfig(Fraction(0), 4)
        g1, q1, _ = p[i + 1]
        beta = math.log(q1 / q0) / math.log((g1 - e0) / (g0 - e0))
        return sigfig(F(q0 * ((h - e0) / (g0 - e0)) ** beta), 4)

    def inverse(self, q):
        Q = float(q)
        p = self.fp
        if len(p) == 1:
            return rnd(F(p[0][0]), 2)
        i = len(p) - 2
        if Q < p[0][1]:
            i = 0
        else:
            for k in range(len(p) - 1):
                if p[k][1] <= Q < p[k + 1][1]:
                    i = k
                    break
        g0, q0, e0 = p[i]
        g1, q1, _ = p[i + 1]
        beta = math.log(q1 / q0) / math.log((g1 - e0) / (g0 - e0))
        return rnd(F(e0 + (g0 - e0) * (Q / q0) ** (1.0 / beta)), 2)

    def above(self, gh):
        return float(gh) > self.fp[-1][0]


# ---------------------------------------------------------------- main

REPORTS = [
    'unit_values.csv', 'gh_corrections.tsv', 'visit_errors.psv', 'measurement_eval.csv',
    'shift_curves.json', 'ice_periods.jsonl', 'rating_tables_used.json', 'daily_values.csv',
    'monthly_summary.xml', 'period_statistics.json', 'alias_resolution.csv',
    'dedup_report.json', 'source_lineage.json', 'reading_exclusions.jsonl',
    'amendment_ledger.psv', 'parameters_used.yaml', 'variance_vs_published.csv',
    'shift_vs_published.csv', 'dashboard_disagreements.tsv', 'cache_divergence.jsonl',
    'reconciliation.md',
]


def xml_escape(s):
    return (str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            .replace('"', '&quot;'))


def main(argv):
    data_dir, out_dir = argv[1], argv[2]

    def dp(name):
        return os.path.join(data_dir, name)

    os.makedirs(out_dir, exist_ok=True)
    out = {}

    # ---- settings -------------------------------------------------------
    profile = yaml_load(open(dp('dv_profile.yml')).read())
    network = str(profile['network']).strip()
    net = profile['networks'][network]
    period_start_date = str(profile['period_start']).strip()
    period_end_date = str(profile['period_end']).strip()
    clock = Clock(yaml_load(open(dp('site_clock.yaml')).read()))
    overlay = (yaml_load(open(dp('site_overlay.yaml')).read()) or {}).get('sites') or {}

    wb = Workbook(dp('cbhs_rt_26q2.xlsx'))
    rating_sheet = str(net['rating_sheet']).strip()
    index_sheet = str(net['index_sheet']).strip()
    site_sheet = str(net['site_sheet']).strip()
    max_gap_default = int(str(net['max_gap_minutes']).strip())
    min_cov = F(net['min_coverage_fraction'])
    margin_h = int(str(net['record_margin_hours']).strip())
    drift_default = F(net['drift_tolerance_ft'])

    tables = pdf_tables(dp('hrb_26-04_minutes.pdf'))

    def find_table(column):
        hits = [(tid, t) for tid, t in sorted(tables.items())
                if t['status'] == 'IN FORCE' and t['header'] and column in t['header'][1]]
        return hits[0] if hits else (None, None)

    tol_id, tol_tab = find_table('tolerance_pct')
    win_id, win_tab = find_table('default_k')
    err_id, err_tab = find_table('was_q_cfs')
    meas_id, meas_tab = find_table('verdict')
    vis_id, vis_tab = find_table('visit_id')

    tolerances = {}
    for r in tol_tab['rows']:
        v = str(r['tolerance_pct']).strip()
        tolerances[str(r['grade']).strip().upper()] = \
            None if v.lower() in ('n/a', 'na', '-', '') else F(v)
    winter_k = {}
    for r in win_tab['rows']:
        winter_k[norm_token(r['station'])] = dstr(r['default_k'])
    errata_by_id = {}
    for r in err_tab['rows']:
        errata_by_id.setdefault(str(r['rating_id']).strip(), []).append(
            (F(r['gh_ft']), str(r['q_cfs']).strip()))
    meas_review = {}
    for r in meas_tab['rows']:
        meas_review[int(str(r['meas_no']).strip())] = (str(r['verdict']).strip().upper(),
                                                       str(r['grade']).strip().upper())
    disregard_visits = set(int(str(r['visit_id']).strip()) for r in vis_tab['rows'])

    # ---- stations -------------------------------------------------------
    master = {}
    with open(dp('stn_master.csv'), newline='') as fh:
        for row in csv.DictReader(fh):
            master[str(row['station_id']).strip()] = row
    master_ids = set(master)
    sites = sorted(sid for sid, row in master.items()
                   if str(row['status']).strip().upper() == 'ACTIVE'
                   and str(row['network']).strip() == network)
    site_set = set(sites)

    con = sqlite3.connect('file:%s?mode=ro' % dp('stn_xref.sqlite'), uri=True)
    reg_rows = con.execute('select token, target, valid_from, valid_to from xref').fetchall()
    con.close()
    add_rows = (yaml_load(open(dp('xref_addendum.yml')).read()) or {}).get('rows') or []
    replaced = set((norm_token(a['token']), iso_utc(a['valid_from'])) for a in add_rows)
    xrows = []
    for tok, target, vf, vt in reg_rows:
        key = (norm_token(tok), iso_utc(vf))
        if key in replaced:
            continue
        xrows.append((key[0], str(target).strip(), key[1],
                      None if vt in (None, '', 'null') else iso_utc(vt)))
    for a in add_rows:
        vt = a.get('valid_to')
        xrows.append((norm_token(a['token']), str(a['target']).strip(),
                      iso_utc(a['valid_from']),
                      None if vt in (None, '', 'null') else iso_utc(vt)))
    resolver = Resolver(master_ids, xrows)

    site_rows = {}
    for r in wb.table(site_sheet):
        key = str(r.get('site') or '').strip()
        if key:
            site_rows[key] = r
    drift, maxgap, area = {}, {}, {}
    for s in sites:
        ov = overlay.get(s) or {}
        sr = site_rows.get(s) or {}
        if ov.get('drift_tolerance_ft') not in (None, ''):
            drift[s] = F(ov['drift_tolerance_ft'])
        elif sr.get('drift_tol_ft') not in (None, ''):
            drift[s] = F(sr['drift_tol_ft'])
        else:
            drift[s] = drift_default
        if ov.get('max_gap_minutes') not in (None, ''):
            maxgap[s] = int(str(ov['max_gap_minutes']).strip())
        else:
            maxgap[s] = max_gap_default
        a = sr.get('drainage_area_mi2')
        area[s] = F(a) if a not in (None, '') else None

    ps_lst = iso_naive(period_start_date + ' 00:00')
    pe_lst = iso_naive(period_end_date + ' 00:00')
    win_lo_utc = clock.utc_from_lst(ps_lst - margin_h * 3600)
    win_hi_utc = clock.utc_from_lst(pe_lst + margin_h * 3600)

    # ---- ratings --------------------------------------------------------
    points_by_id = {}
    for r in wb.table(rating_sheet):
        rid = str(r.get('rating_id') or '').strip()
        if not rid:
            continue
        points_by_id.setdefault(rid, []).append(
            (str(r['gh_ft']).strip(), str(r['q_cfs']).strip(), str(r['offset_ft']).strip()))

    ratings, site_versions, errata_applied = {}, {}, {}
    for r in wb.table(index_sheet):
        if str(r.get('status') or '').strip().upper() != 'ACTIVE':
            continue
        site = str(r.get('site') or '').strip()
        if site not in site_set:
            continue
        rid = str(r.get('rating_id') or '').strip()
        eff = serial_to_lst(str(r['effective_date']).strip(), wb.date1904)
        hh, mm = str(r['effective_time']).strip().split(':')[0:2]
        eff += int(hh) * 3600 + int(mm) * 60
        pts = sorted(points_by_id.get(rid, []), key=lambda p: F(p[0]))
        applied, newpts, texts = [], [], []
        for gh, q, e in pts:
            nq = q
            for egh, eq in errata_by_id.get(rid, []):
                if egh == F(gh):
                    nq = eq
                    applied.append((F(gh), dstr(gh), dstr(q), dstr(eq)))
            newpts.append((F(gh), F(nq), F(e)))
            texts.append((dstr(gh), dstr(nq), dstr(e)))
        errata_applied[rid] = sorted(applied)
        rt = Rating(rid, site, eff, newpts, texts)
        ratings[rid] = rt
        site_versions.setdefault(site, []).append(rt)
    for v in site_versions.values():
        v.sort(key=lambda r: (r.eff, r.rating_id))

    def version_at(site, lst):
        vs = site_versions.get(site, ())
        best = None
        for r in vs:
            if r.eff <= lst:
                best = r
        # no version is in force before the earliest one; keep the record computable
        return best if best is not None else (vs[0] if vs else None)

    # ---- ingest ---------------------------------------------------------
    catalog = json.load(open(dp('ingest_catalog.json')))
    layout_of = {f['file']: f['layout'] for f in catalog['files']}
    routes = {}
    for r in catalog['routes']:
        if str(r['status']).strip().upper() != 'ACTIVE':
            continue
        routes.setdefault((r['file'], str(r['site']).strip(),
                           str(r['sensor']).strip().upper()), []).append(
            (iso_utc(r['from_utc']), iso_utc(r['to_utc'])))

    counters = dict(files_read=0, records_read=0, unknown_site=0, out_of_scope=0, unrouted=0,
                    out_of_window=0, admitted=0, superseded=0, duplicates=0, voided=0,
                    edits_applied=0, edits_ignored=0, edit_deleted=0, sensor_fault=0,
                    backup_unused=0, kept=0)
    lineage = []
    alias_counts = {}
    groups = {}

    for fidx, fname in enumerate(f for f in catalog['file_order'] if os.path.exists(dp(f))):
        layout = layout_of[fname]
        counters['files_read'] += 1
        stats = dict(file=fname, layout=layout, records=0, unknown_site=0, out_of_scope=0,
                     unrouted=0, out_of_window=0, admitted=0)
        for rec in read_shard(dp(fname), layout, clock):
            stats['records'] += 1
            site = resolver.resolve(rec.tok, rec.u)
            if site is None:
                stats['unknown_site'] += 1
                continue
            if site in site_set:
                tk = norm_token(rec.tok)
                if tk != site:
                    alias_counts[(tk, site)] = alias_counts.get((tk, site), 0) + 1
            else:
                stats['out_of_scope'] += 1
                continue
            spans = routes.get((fname, site, rec.sensor))
            if not spans or not any(a <= rec.u < b for a, b in spans):
                stats['unrouted'] += 1
                continue
            if not (win_lo_utc <= rec.u < win_hi_utc):
                stats['out_of_window'] += 1
                continue
            stats['admitted'] += 1
            groups.setdefault((site, rec.sensor, rec.u), []).append(
                (rec.rev, fidx, rec.idx, rec, fname))
        lineage.append(stats)
        counters['records_read'] += stats['records']
        for k in ('unknown_site', 'out_of_scope', 'unrouted', 'out_of_window', 'admitted'):
            counters[k] += stats[k]

    # ---- H6 revisions, duplicates, voids --------------------------------
    readings = {}
    excluded = []
    for key, copies in groups.items():
        best = max(copies, key=lambda c: (c[0], c[1], c[2]))
        for c in copies:
            if c[0] < best[0]:
                counters['superseded'] += 1
            elif c is not best:
                counters['duplicates'] += 1
        rec = best[3]
        if rec.void:
            counters['voided'] += 1
            excluded.append((key[0], key[1], key[2], 'VOIDED', best[4]))
            continue
        readings[key] = {'val': rec.val, 'unit': rec.unit, 'q': rec.q, 'file': best[4],
                         'deleted': False, 'snap': None}

    # ---- H7 unit-value edits --------------------------------------------
    edits = []
    for line in open(dp('uv_edits.jsonl')):
        line = line.strip()
        if line:
            edits.append(json.loads(line))
    edits.sort(key=lambda e: int(e['seq']))
    ledger = []
    for e in edits:
        lst = iso_naive(e['time_lst'])
        u = clock.utc_from_lst(lst)
        site = resolver.resolve(e['station'], u)
        if site is None or site not in site_set:
            continue
        sensor = str(e['sensor']).strip().upper()
        op = str(e['op']).strip().upper()
        r = readings.get((site, sensor, u))
        status = 'IGNORED'
        if op == 'SET':
            if r is not None and not r['deleted']:
                r['val'] = str(e['value']).strip()
                r['unit'] = norm_unit(e['unit'])
                r['q'] = 'G'
                status = 'APPLIED'
        elif op == 'DELETE':
            if r is not None and not r['deleted']:
                r['deleted'] = True
                r['snap'] = (r['val'], r['unit'], r['q'])
                status = 'APPLIED'
        elif op == 'RESTORE':
            if r is not None and r['deleted'] and r['snap'] is not None:
                r['val'], r['unit'], r['q'] = r['snap']
                r['deleted'] = False
                status = 'APPLIED'
        counters['edits_applied' if status == 'APPLIED' else 'edits_ignored'] += 1
        ledger.append((int(e['seq']), site, sensor, fmt_time(lst), op, status))

    for key, r in list(readings.items()):
        if r['deleted']:
            counters['edit_deleted'] += 1
            excluded.append((key[0], key[1], key[2], 'EDIT_DELETED', r['file']))
            del readings[key]

    # ---- H8 quality, units, datum, sensors -------------------------------
    for key, r in list(readings.items()):
        if r['q'] == 'X':
            counters['sensor_fault'] += 1
            excluded.append((key[0], key[1], key[2], 'SENSOR_FAULT', r['file']))
            del readings[key]

    eqp = {}
    with open(dp('eqp_reg.tsv'), newline='') as fh:
        for row in csv.DictReader(fh, delimiter='\t'):
            eqp.setdefault((str(row['site']).strip(), str(row['sensor']).strip().upper()),
                           []).append((iso_naive(row['valid_from_lst']),
                                       norm_unit(row['unit'])))
    for v in eqp.values():
        v.sort()
    datum = {}
    with open(dp('dtm_hist.psv'), newline='') as fh:
        for row in csv.DictReader(fh, delimiter='|'):
            if str(row['status']).strip().upper() != 'ACTIVE':
                continue
            datum.setdefault((str(row['site']).strip(), str(row['sensor']).strip().upper()),
                             []).append((iso_utc(row['valid_from_utc']), F(row['offset_ft'])))
    for v in datum.values():
        v.sort()

    def unit_for(site, sensor, u):
        lst = clock.lst(u)
        best = None
        for vf, unit in eqp.get((site, sensor), ()):
            if vf <= lst:
                best = unit
        return best

    def offset_for(site, sensor, u):
        best = Fraction(0)
        for vf, off in datum.get((site, sensor), ()):
            if vf <= u:
                best = off
        return best

    have_p = set()
    for (site, sensor, u) in readings:
        if sensor == 'P':
            have_p.add((site, u))
    selected = {}
    for key, r in readings.items():
        site, sensor, u = key
        if sensor == 'B' and (site, u) in have_p:
            counters['backup_unused'] += 1
            excluded.append((site, sensor, u, 'BACKUP_UNUSED', r['file']))
            continue
        selected[key] = r
    counters['kept'] = len(selected)

    for key, r in selected.items():
        site, sensor, u = key
        unit = r['unit'] or unit_for(site, sensor, u) or 'FT'
        r['stage_ft'] = to_ft(r['val'], unit) + offset_for(site, sensor, u)

    # ---- H9 field visits -------------------------------------------------
    con = sqlite3.connect('file:%s?mode=ro' % dp('fv_ledger_q2.db'), uri=True)
    visits = {}
    for vid, stn, vdate, vtime, logger_ft, action, party in con.execute(
            'select vid, stn, vdate, vtime, logger_ft, action, party from visit'):
        vt = str(vtime).strip()
        visits[int(vid)] = dict(
            stn=stn, time=iso_naive('%s %s:%s' % (str(vdate).strip(), vt[:2], vt[2:])),
            logger=str(logger_ft).strip(), action=str(action or '').strip().upper(),
            refs={}, void=False)
    for vid, method, reading_ft, note in con.execute(
            'select vid, method, reading_ft, note from vref'):
        v = visits.get(int(vid))
        if v is not None:
            v['refs'][str(method).strip().upper()] = str(reading_ft).strip()
    con.close()

    amends = sorted((int(a.get('no')), int(a.get('visit')), str(a.get('field')).strip().lower(),
                     a.get('method'), (a.text or '').strip())
                    for a in ET.parse(dp('fv_amend.xml')).getroot().iter('amend'))
    for no, vid, field, method, text in amends:
        v = visits.get(vid)
        if v is None or v['void']:
            continue
        if field == 'void':
            v['void'] = True
        elif field == 'reference':
            v['refs'][str(method).strip().upper()] = text
        elif field == 'action':
            v['action'] = text.upper()
        elif field == 'time':
            v['time'] = iso_naive(text)
        elif field == 'logger':
            v['logger'] = text

    visit_rows = []
    used_visits = {}
    for vid in sorted(visits):
        v = visits[vid]
        site = resolver.resolve(v['stn'], clock.utc_from_lst(v['time']))
        if site is None or site not in site_set:
            continue
        method = None
        for m in ('TAPE', 'WIRE', 'STAFF'):
            if v['refs'].get(m) not in (None, ''):
                method = m
                break
        logger = F(v['logger'])
        ref = F(v['refs'][method]) if method else None
        err = (ref - logger) if method else None
        if v['void']:
            status = 'VOID'
        elif vid in disregard_visits or method is None:
            status = 'DISREGARDED'
        else:
            status = 'USED'
        action = 'RESET' if v['action'] == 'RESET' else 'NONE'
        applied = None
        if status == 'USED':
            applied = err if abs(err) >= drift[site] else Fraction(0)
            used_visits.setdefault(site, []).append(
                dict(vid=vid, time=v['time'], applied=applied, action=action))
        visit_rows.append(dict(site=site, vid=vid, time=v['time'], method=method or '',
                               ref=ref, logger=logger, err=err, applied=applied,
                               action=action, status=status))
    for v in used_visits.values():
        v.sort(key=lambda d: (d['time'], d['vid']))

    def correction(site, lst):
        vs = used_visits.get(site)
        if not vs or lst < vs[0]['time']:
            return Fraction(0)
        for k in range(len(vs) - 1):
            if vs[k]['time'] <= lst < vs[k + 1]['time']:
                ak = Fraction(0) if vs[k]['action'] == 'RESET' else vs[k]['applied']
                bk = vs[k + 1]['applied']
                return ak + (bk - ak) * Fraction(lst - vs[k]['time'],
                                                 vs[k + 1]['time'] - vs[k]['time'])
        last = vs[-1]
        return Fraction(0) if last['action'] == 'RESET' else last['applied']

    for key, r in selected.items():
        site, sensor, u = key
        r['gh'] = rnd(r['stage_ft'] + correction(site, clock.lst(u)), 2)

    site_readings = {}
    for (site, sensor, u), r in selected.items():
        site_readings.setdefault(site, []).append((u, sensor, r))
    for v in site_readings.values():
        v.sort(key=lambda t: t[0])

    # ---- H13 ice events ---------------------------------------------------
    ice_entries = []
    for line in open(dp('ice_obs_j2.ndjson')):
        line = line.strip()
        if line:
            ice_entries.append(json.loads(line))
    ice_entries.sort(key=lambda e: int(e['entry']))
    events = {}
    for e in ice_entries:
        kind = str(e['kind']).strip().upper()
        if kind in ('ON', 'OFF'):
            lst = iso_naive(e['at_lst'])
            events[int(e['entry'])] = dict(
                entry=int(e['entry']), kind=kind, time=lst,
                site=resolver.resolve(e['station'], clock.utc_from_lst(lst)))
        elif kind == 'AMEND':
            t = events.get(int(e['target']))
            if t is not None:
                t['time'] = iso_naive(e['at_lst'])
        elif kind == 'WITHDRAW':
            events.pop(int(e['target']), None)

    ice_periods = {}
    for site in sites:
        evs = sorted((e for e in events.values() if e['site'] == site),
                     key=lambda e: (e['time'], e['entry']))
        periods = []
        cur = None
        for e in evs:
            if e['kind'] == 'ON' and cur is None:
                cur = dict(on=e['time'], on_entry=e['entry'], off=None, off_entry=None,
                           k_points=[])
            elif e['kind'] == 'OFF' and cur is not None:
                cur['off'] = e['time']
                cur['off_entry'] = e['entry']
                periods.append(cur)
                cur = None
        if cur is not None:
            periods.append(cur)
        periods.sort(key=lambda p: p['on'])
        ice_periods[site] = periods

    def in_ice(site, lst):
        for p in ice_periods.get(site, ()):
            if p['on'] <= lst and (p['off'] is None or lst < p['off']):
                return p
        return None

    # ---- H11 measurements --------------------------------------------------
    meas = {}
    with open(dp('qm_main_26q2.csv'), newline='') as fh:
        for row in csv.DictReader(fh):
            no = int(str(row['meas_no']).strip())
            meas[no] = dict(no=no, token=row['station'], start=row['start'], end=row['end'],
                            q=F(row['q_cfs']), grade=str(row['grade']).strip().upper(),
                            cover=str(row['cover']).strip(), entered=iso_utc(row['entered_utc']))
    for m in ET.parse(dp('qm_late.xml')).getroot().iter('measurement'):
        no = int(str(m.get('no')).strip())
        entered = iso_utc(m.findtext('entered'))
        if no in meas and meas[no]['entered'] >= entered:
            continue
        meas[no] = dict(no=no, token=m.findtext('station'), start=m.findtext('start'),
                        end=m.findtext('end'),
                        q=F(m.findtext('q')) / F('0.028316846592'),
                        grade=str(m.findtext('grade')).strip().upper(),
                        cover=str(m.findtext('cover')).strip(), entered=entered)

    def meas_time(s):
        s = str(s).strip()
        if re.search(r'(Z|z|[+-]\d{2}:?\d{2})$', s):
            return iso_utc(s)
        return clock.utc_from_lst(iso_naive(s))

    mlist = []
    for no in sorted(meas):
        m = meas[no]
        su = meas_time(m['start'])
        eu = meas_time(m['end'])
        inst = ((su + eu) // 120) * 60
        site = resolver.resolve(m['token'], inst)
        if site is None or site not in site_set:
            continue
        verdict, newgrade = meas_review.get(no, ('ACCEPT', None))
        grade = newgrade if verdict == 'REGRADE' else m['grade']
        ghs = [r['gh'] for (u, sensor, r) in site_readings.get(site, ()) if su <= u <= eu]
        gh = rnd(sum(F(g) for g in ghs) / len(ghs), 2) if ghs else None
        mlist.append(dict(no=no, site=site, start=su, end=eu, inst=inst, grade=grade,
                          verdict=verdict, cover=m['cover'], q=m['q'], gh=gh, rating=None,
                          decision=None, shift_in_use=None, rated=None, dev=None, tol=None,
                          shift=None, k=None))
    mlist.sort(key=lambda m: (m['site'], m['inst'], m['no']))

    shift_pts = {}
    for m in mlist:
        if m['verdict'] == 'REJECT':
            m['decision'] = 'REJECTED'
            continue
        if m['gh'] is None:
            m['decision'] = 'NO_RECORD'
            continue
        lst = clock.lst(m['inst'])
        rt = version_at(m['site'], lst)
        m['rating'] = rt
        if rt is None:
            m['decision'] = 'NO_RECORD'
            continue
        if in_ice(m['site'], lst) is not None:
            m['decision'] = 'ICE'
            continue
        pts = shift_pts.get(rt.rating_id, [])
        siu = pts[-1][1] if pts else Decimal('0.00')
        m['shift_in_use'] = siu
        rated = rt.eval(F(m['gh']) + F(siu))
        m['rated'] = rated
        m['dev'] = rnd((m['q'] - F(rated)) / F(rated) * 100, 1)
        m['tol'] = tolerances.get(m['grade'])
        if m['tol'] is not None and abs(F(m['dev'])) > m['tol']:
            m['decision'] = 'SHIFT'
            m['shift'] = rt.inverse(m['q']) - m['gh']
            shift_pts.setdefault(rt.rating_id, []).append((m['inst'], m['shift'], m['no']))
        else:
            m['decision'] = 'CHECK'

    # ---- H12 shift curves --------------------------------------------------
    curves = {}
    for site in sites:
        for rt in site_versions.get(site, ()):
            pts = [(clock.utc_from_lst(rt.eff), Decimal('0.00'), 'START')]
            for inst, sh, no in sorted(shift_pts.get(rt.rating_id, [])):
                pts.append((inst, sh, str(no)))
            curves[rt.rating_id] = pts

    def shift_at(rating_id, u):
        pts = curves[rating_id]
        if u <= pts[0][0]:
            return rnd(F(pts[0][1]), 2)
        for k in range(len(pts) - 1):
            if pts[k][0] <= u < pts[k + 1][0]:
                t0, s0, _ = pts[k]
                t1, s1, _ = pts[k + 1]
                return rnd(F(s0) + (F(s1) - F(s0)) * Fraction(u - t0, t1 - t0), 2)
        return rnd(F(pts[-1][1]), 2)

    for m in mlist:
        if m['decision'] != 'ICE':
            continue
        rt = m['rating']
        s = shift_at(rt.rating_id, m['inst'])
        m['shift_in_use'] = s
        m['rated'] = rt.eval(F(m['gh']) + F(s))
        m['k'] = rnd(m['q'] / F(m['rated']), 3) if F(m['rated']) != 0 else None
        p = in_ice(m['site'], clock.lst(m['inst']))
        if p is not None:
            p['k_points'].append((m['inst'], m['k'], m['no']))
    for site in sites:
        for p in ice_periods[site]:
            p['k_points'].sort()
            p['default_k'] = None if p['k_points'] else winter_k.get(site)

    def k_at(period, u):
        pts = period['k_points']
        if not pts:
            dk = period['default_k']
            return rnd(F(dk), 3) if dk is not None else None
        if u <= pts[0][0]:
            return rnd(F(pts[0][1]), 3)
        for k in range(len(pts) - 1):
            if pts[k][0] <= u < pts[k + 1][0]:
                t0, k0, _ = pts[k]
                t1, k1, _ = pts[k + 1]
                return rnd(F(k0) + (F(k1) - F(k0)) * Fraction(u - t0, t1 - t0), 3)
        return rnd(F(pts[-1][1]), 3)

    # ---- H14 unit values ----------------------------------------------------
    uv_rows = []
    uv_by_site = {}
    for site in sites:
        for (u, sensor, r) in site_readings.get(site, ()):
            lst = clock.lst(u)
            rt = version_at(site, lst)
            sh = shift_at(rt.rating_id, u) if rt else Decimal('0.00')
            gh_eff = rnd(F(r['gh']) + F(sh), 2)
            q_open = rt.eval(gh_eff) if rt else Decimal('0.00')
            p = in_ice(site, lst)
            flags = ''
            if sensor == 'B':
                flags += 'B'
            if p is not None:
                flags += 'I'
            if rt is not None and rt.above(gh_eff):
                flags += '>'
            k = k_at(p, u) if p is not None else None
            q = sigfig(F(k) * F(q_open), 4) if k is not None else q_open
            row = dict(site=site, u=u, lst=lst, sensor=sensor, gh=r['gh'], shift=sh,
                       gh_eff=gh_eff, q_open=q_open, k=k, q=q, flags=flags, period=p)
            uv_rows.append(row)
            uv_by_site.setdefault(site, []).append(row)
    for v in uv_by_site.values():
        v.sort(key=lambda d: d['u'])

    # ---- H15 daily values ----------------------------------------------------
    period_days = []
    d = dt.datetime.strptime(period_start_date, '%Y-%m-%d').date()
    dend = dt.datetime.strptime(period_end_date, '%Y-%m-%d').date()
    while d < dend:
        period_days.append(d)
        d += dt.timedelta(days=1)
    day_set = set(period_days)

    daily = {}
    for site in sites:
        rows = uv_by_site.get(site, [])
        gap = maxgap[site] * 60
        segs = []
        for i in range(len(rows) - 1):
            a, b = rows[i], rows[i + 1]
            if 0 < b['lst'] - a['lst'] <= gap:
                segs.append((a['lst'], F(a['q']), b['lst'], F(b['q'])))
        for day in period_days:
            ds = naive(dt.datetime(day.year, day.month, day.day))
            de = ds + 86400
            integral = Fraction(0)
            cover = 0
            for (t0, q0, t1, q1) in segs:
                if t1 <= ds or t0 >= de:
                    continue
                a = max(t0, ds)
                b = min(t1, de)
                if b <= a:
                    continue
                va = q0 + (q1 - q0) * Fraction(a - t0, t1 - t0)
                vb = q0 + (q1 - q0) * Fraction(b - t0, t1 - t0)
                integral += (va + vb) / 2 * (b - a)
                cover += b - a
            dayrows = [r for r in rows if ds <= r['lst'] < de]
            codes = []
            mean = None
            if cover < min_cov * 86400:
                codes.append('INC')
            else:
                mean = disch(integral / cover)
            if any('I' in r['flags'] for r in dayrows):
                codes.append('ICE')
            if any('B' in r['flags'] for r in dayrows):
                codes.append('B')
            if any('>' in r['flags'] for r in dayrows):
                codes.append('>')
            daily[(site, day)] = dict(mean=mean, cover_h=rnd(Fraction(cover, 3600), 2),
                                      n=len(dayrows), codes=';'.join(codes))

    # ---- H16 monthly, period -------------------------------------------------
    months = []
    for day in period_days:
        if (day.year, day.month) not in months:
            months.append((day.year, day.month))

    monthly = []
    for site in sites:
        for (y, mo) in months:
            days = [d for d in period_days if d.year == y and d.month == mo]
            vals = [daily[(site, d)]['mean'] for d in days
                    if daily[(site, d)]['mean'] is not None]
            row = dict(site=site, month='%04d-%02d' % (y, mo), days=len(days),
                       complete_days=len(vals), complete=len(vals) == len(days),
                       mean=None, min=None, max=None, volume=None, runoff=None)
            if vals:
                total = sum(F(v) for v in vals)
                row['mean'] = disch(total / len(vals))
                row['min'] = min(vals, key=F)
                row['max'] = max(vals, key=F)
                row['volume'] = rnd(total * 86400 / 43560, 1)
                if area[site]:
                    row['runoff'] = rnd(F(row['volume']) * 12 / (area[site] * 640), 2)
            monthly.append(row)

    stats = []
    for site in sites:
        peak = None
        for r in uv_by_site.get(site, []):
            if ps_lst <= r['lst'] < pe_lst and (peak is None or F(r['q']) > F(peak['q'])):
                peak = r
        vals = [daily[(site, d)]['mean'] for d in period_days]
        best = None
        best_start = None
        for i in range(len(period_days) - 6):
            w = vals[i:i + 7]
            if any(v is None for v in w):
                continue
            mean = sum(F(v) for v in w) / 7
            if best is None or mean < best:
                best = mean
                best_start = period_days[i]
        have = [v for v in vals if v is not None]
        codes = [daily[(site, d)]['codes'].split(';') for d in period_days]
        stats.append(dict(
            site=site, peak_q=peak['q'] if peak else None,
            peak_time=fmt_time(peak['lst']) if peak else None,
            min7=disch(best) if best is not None else None,
            min7_start=best_start.isoformat() if best_start else None,
            mean=disch(sum(F(v) for v in have) / len(have)) if have else None,
            complete_days=len(have),
            inc_days=sum(1 for c in codes if 'INC' in c),
            ice_days=sum(1 for c in codes if 'ICE' in c),
            backup_days=sum(1 for c in codes if 'B' in c),
            above_days=sum(1 for c in codes if '>' in c),
            shift_points=sum(1 for m in mlist if m['site'] == site and m['decision'] == 'SHIFT'),
            ice_meas=sum(1 for m in mlist if m['site'] == site and m['decision'] == 'ICE')))

    # ===================== reports =====================

    # unit_values.csv
    buf = ['site,time_lst,sensor,gh_ft,shift_ft,gh_eff_ft,q_open_cfs,k_factor,q_cfs,flags']
    for r in sorted(uv_rows, key=lambda d: (d['site'], d['lst'])):
        buf.append(','.join([
            r['site'], fmt_time(r['lst']), r['sensor'], fmt(r['gh']), fmt(r['shift']),
            fmt(r['gh_eff']), fmt(r['q_open']), fmt(r['k']) if r['k'] is not None else '',
            fmt(r['q']), r['flags']]))
    out['unit_values.csv'] = '\n'.join(buf) + '\n'

    # gh_corrections.tsv
    buf = ['site\tfrom_lst\tto_lst\tstart_ft\tend_ft']
    for site in sites:
        vs = used_visits.get(site, [])
        for k, v in enumerate(vs):
            ak = Fraction(0) if v['action'] == 'RESET' else v['applied']
            if k < len(vs) - 1:
                buf.append('\t'.join([site, fmt_time(v['time']), fmt_time(vs[k + 1]['time']),
                                      fmt(rnd(ak, 2)), fmt(rnd(vs[k + 1]['applied'], 2))]))
            else:
                buf.append('\t'.join([site, fmt_time(v['time']), '', fmt(rnd(ak, 2)),
                                      fmt(rnd(ak, 2))]))
    out['gh_corrections.tsv'] = '\n'.join(buf) + '\n'

    # visit_errors.psv
    buf = ['site|visit_id|time_lst|method|reference_ft|logger_ft|error_ft|applied_ft|'
           'action|status']
    for v in sorted(visit_rows, key=lambda d: (d['site'], d['time'], d['vid'])):
        buf.append('|'.join([
            v['site'], str(v['vid']), fmt_time(v['time']), v['method'],
            fmt(rnd(v['ref'], 2)) if v['ref'] is not None else '',
            fmt(rnd(v['logger'], 2)),
            fmt(rnd(v['err'], 2)) if v['err'] is not None else '',
            fmt(rnd(v['applied'], 2)) if v['applied'] is not None else '',
            v['action'], v['status']]))
    out['visit_errors.psv'] = '\n'.join(buf) + '\n'

    # measurement_eval.csv
    buf = ['meas_no,site,instant_lst,grade,verdict,cover,gh_ft,rating_id,shift_in_use_ft,'
           'rated_q_cfs,measured_q_cfs,deviation_pct,tolerance_pct,decision,shift_ft,k_factor']
    for m in sorted(mlist, key=lambda d: d['no']):
        dec = m['decision']
        full = dec not in ('REJECTED', 'NO_RECORD')
        ow = dec in ('SHIFT', 'CHECK')
        buf.append(','.join([
            str(m['no']), m['site'], fmt_time(clock.lst(m['inst'])), m['grade'], m['verdict'],
            m['cover'], fmt(m['gh']) if m['gh'] is not None else '',
            m['rating'].rating_id if full else '',
            fmt(m['shift_in_use']) if full else '',
            fmt(m['rated']) if full else '',
            fmt(rnd(m['q'], 2)),
            fmt(m['dev']) if ow else '',
            fmt(rnd(m['tol'], 1)) if ow and m['tol'] is not None else '',
            dec, fmt(m['shift']) if dec == 'SHIFT' else '',
            fmt(m['k']) if dec == 'ICE' and m['k'] is not None else '']))
    out['measurement_eval.csv'] = '\n'.join(buf) + '\n'

    # shift_curves.json
    arr = []
    for site in sites:
        for rt in site_versions.get(site, ()):
            pts = [{'time_lst': fmt_time(clock.lst(u)), 'shift_ft': Raw(fmt(rnd(F(sh), 2))),
                    'source': src} for u, sh, src in curves[rt.rating_id]]
            arr.append({'site': site, 'rating_id': rt.rating_id,
                        'effective_lst': fmt_time(rt.eff), 'points': pts})
    out['shift_curves.json'] = jenc({'curves': arr}) + '\n'

    # ice_periods.jsonl
    lines = []
    for site in sites:
        for p in ice_periods[site]:
            n_uv = sum(1 for r in uv_by_site.get(site, []) if r['period'] is p)
            kp = [{'meas_no': no, 'time_lst': fmt_time(clock.lst(inst)), 'k': Raw(fmt(k))}
                  for inst, k, no in p['k_points']]
            lines.append(jline({
                'site': site, 'on_lst': fmt_time(p['on']),
                'off_lst': fmt_time(p['off']) if p['off'] is not None else None,
                'on_entry': p['on_entry'], 'off_entry': p['off_entry'], 'k_points': kp,
                'default_k': Raw(p['default_k']) if p['default_k'] is not None else None,
                'unit_values': n_uv}))
    out['ice_periods.jsonl'] = ''.join(l + '\n' for l in lines)

    # rating_tables_used.json
    arr = []
    n_errata = 0
    for site in sites:
        for rt in site_versions.get(site, ()):
            pts = [{'gh_ft': Raw(g), 'q_cfs': Raw(q), 'offset_ft': Raw(e)}
                   for g, q, e in rt.texts]
            er = [{'gh_ft': Raw(gt), 'from_q_cfs': Raw(a), 'to_q_cfs': Raw(b)}
                  for _, gt, a, b in errata_applied.get(rt.rating_id, [])]
            n_errata += len(er)
            arr.append({'rating_id': rt.rating_id, 'site': site,
                        'effective_lst': fmt_time(rt.eff), 'points': pts,
                        'errata_applied': er})
    out['rating_tables_used.json'] = jenc({'ratings': arr}) + '\n'

    # daily_values.csv
    buf = ['site,date,q_mean_cfs,coverage_h,n_readings,codes']
    for site in sites:
        for day in period_days:
            r = daily[(site, day)]
            buf.append(','.join([site, day.isoformat(),
                                 fmt(r['mean']) if r['mean'] is not None else '',
                                 fmt(r['cover_h']), str(r['n']), r['codes']]))
    out['daily_values.csv'] = '\n'.join(buf) + '\n'

    # monthly_summary.xml
    buf = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<monthly_summary network="%s" period_start="%s" period_end="%s">'
           % (xml_escape(network), period_start_date, period_end_date)]
    for r in monthly:
        buf.append('  <month site="%s" month="%s" days="%d" complete_days="%d" mean_cfs="%s"'
                   ' min_cfs="%s" max_cfs="%s" volume_af="%s" runoff_in="%s" complete="%s"/>'
                   % (r['site'], r['month'], r['days'], r['complete_days'],
                      fmt(r['mean']) if r['mean'] is not None else '',
                      fmt(r['min']) if r['min'] is not None else '',
                      fmt(r['max']) if r['max'] is not None else '',
                      fmt(r['volume']) if r['volume'] is not None else '',
                      fmt(r['runoff']) if r['runoff'] is not None else '',
                      'true' if r['complete'] else 'false'))
    buf.append('</monthly_summary>')
    out['monthly_summary.xml'] = '\n'.join(buf) + '\n'

    # period_statistics.json
    arr = []
    for s in stats:
        arr.append({
            'site': s['site'],
            'peak_q_cfs': Raw(fmt(s['peak_q'])) if s['peak_q'] is not None else None,
            'peak_time_lst': s['peak_time'],
            'min_7day_cfs': Raw(fmt(s['min7'])) if s['min7'] is not None else None,
            'min_7day_start': s['min7_start'],
            'mean_cfs': Raw(fmt(s['mean'])) if s['mean'] is not None else None,
            'complete_days': s['complete_days'], 'inc_days': s['inc_days'],
            'ice_days': s['ice_days'], 'backup_days': s['backup_days'],
            'above_rating_days': s['above_days'], 'shift_points': s['shift_points'],
            'ice_measurements': s['ice_meas']})
    out['period_statistics.json'] = jenc({'sites': arr}) + '\n'

    # alias_resolution.csv
    buf = ['token,site,records']
    for (tok, site) in sorted(alias_counts):
        buf.append('%s,%s,%d' % (tok, site, alias_counts[(tok, site)]))
    out['alias_resolution.csv'] = '\n'.join(buf) + '\n'

    # dedup_report.json
    order = ['files_read', 'records_read', 'unknown_site', 'out_of_scope', 'unrouted',
             'out_of_window', 'admitted', 'superseded', 'duplicates', 'voided',
             'edits_applied', 'edits_ignored', 'edit_deleted', 'sensor_fault',
             'backup_unused', 'kept']
    out['dedup_report.json'] = jenc(dict((k, counters[k]) for k in order)) + '\n'

    # source_lineage.json
    out['source_lineage.json'] = jenc({'files': [
        dict((k, s[k]) for k in ('file', 'layout', 'records', 'unknown_site', 'out_of_scope',
                                 'unrouted', 'out_of_window', 'admitted')) for s in lineage]
    }) + '\n'

    # reading_exclusions.jsonl
    lines = []
    for site, sensor, u, reason, fname in sorted(excluded,
                                                 key=lambda e: (e[0], e[2], e[1])):
        lines.append(jline({'site': site, 'sensor': sensor,
                            'time_lst': fmt_time(clock.lst(u)), 'reason': reason,
                            'file': fname}))
    out['reading_exclusions.jsonl'] = ''.join(l + '\n' for l in lines)

    # amendment_ledger.psv
    buf = ['seq|site|sensor|time_lst|op|status']
    for e in ledger:
        buf.append('|'.join([str(e[0]), e[1], e[2], e[3], e[4], e[5]]))
    out['amendment_ledger.psv'] = '\n'.join(buf) + '\n'

    # parameters_used.yaml
    buf = ['network: %s' % network,
           'period_start: %s' % period_start_date,
           'period_end: %s' % period_end_date,
           'rating_sheet: %s' % rating_sheet,
           'index_sheet: %s' % index_sheet,
           'site_sheet: %s' % site_sheet,
           'max_gap_minutes: %d' % max_gap_default,
           'min_coverage_fraction: %s' % fmt(rnd(min_cov, 2)),
           'record_margin_hours: %d' % margin_h,
           'drift_tolerance_default_ft: %s' % fmt(rnd(drift_default, 2)),
           'tolerance_table: %s' % tol_id]
    for g in ('E', 'G', 'F'):
        buf.append('tolerance_%s_pct: %s' % (g, fmt(rnd(tolerances[g], 1))))
    buf.append('winter_table: %s' % win_id)
    buf.append('errata_table: %s' % err_id)
    buf.append('errata_applied: %d' % n_errata)
    buf.append('date_system: %s' % ('1904' if wb.date1904 else '1900'))
    buf.append('clock_standard_offset_minutes: %d' % (clock.offset // 60))
    buf.append('dst_rule: %s' % clock.rule)
    for s in sites:
        buf.append('drift_tolerance_%s: %s' % (s, fmt(rnd(drift[s], 2))))
    for s in sites:
        buf.append('max_gap_%s: %d' % (s, maxgap[s]))
    for s in sites:
        buf.append('winter_k_%s: %s' % (s, winter_k.get(s, '')))
    out['parameters_used.yaml'] = '\n'.join(buf) + '\n'

    # variance_vs_published.csv
    pub = {}
    with open(dp('dv_pub_26q2.csv'), newline='') as fh:
        for row in csv.DictReader(fh):
            pub[(str(row['site']).strip(), str(row['date']).strip())] = \
                str(row['q_mean_cfs']).strip()
    buf = ['site,date,published_cfs,recomputed_cfs,diff_cfs,status']
    keys = set()
    for (site, date), val in pub.items():
        if site in site_set and val != '':
            keys.add((site, date))
    for site in sites:
        for day in period_days:
            if daily[(site, day)]['mean'] is not None:
                keys.add((site, day.isoformat()))
    for site, date in sorted(keys):
        p = pub.get((site, date), '')
        day = dt.datetime.strptime(date, '%Y-%m-%d').date()
        r = daily[(site, day)]['mean'] if (site, day) in daily else None
        if p != '' and r is not None:
            diff = Decimal(fmt(r)) - Decimal(p)
            buf.append(','.join([site, date, p, fmt(r), fmt(diff),
                                 'MATCH' if diff == 0 else 'DIFF']))
        elif p != '':
            buf.append(','.join([site, date, p, '', '', 'ONLY_PUBLISHED']))
        else:
            buf.append(','.join([site, date, '', fmt(r), '', 'ONLY_RECOMPUTED']))
    out['variance_vs_published.csv'] = '\n'.join(buf) + '\n'

    # shift_vs_published.csv
    mby = dict((m['no'], m) for m in mlist)
    buf = ['meas_no,site,published_decision,published_shift_ft,recomputed_decision,'
           'recomputed_shift_ft,status']
    prows = []
    with open(dp('shift_wksht_pub.csv'), newline='') as fh:
        for row in csv.DictReader(fh):
            prows.append(row)
    for row in sorted(prows, key=lambda r: int(str(r['meas_no']).strip())):
        no = int(str(row['meas_no']).strip())
        pdec = str(row['decision']).strip()
        pshift = str(row['shift_ft']).strip()
        pst = fmt(rnd(F(pshift), 2)) if pshift else ''
        m = mby.get(no)
        if m is None:
            buf.append(','.join([str(no), str(row['site']).strip(), pdec, pst, '', '',
                                 'NOT_FOUND']))
            continue
        rdec = m['decision']
        rshift = fmt(m['shift']) if rdec == 'SHIFT' else ''
        agree = pdec == rdec and (rdec != 'SHIFT'
                                  or (pshift != '' and F(pshift) == F(m['shift'])))
        buf.append(','.join([str(no), m['site'], pdec, pst, rdec, rshift,
                             'AGREE' if agree else 'DIFFER']))
    out['shift_vs_published.csv'] = '\n'.join(buf) + '\n'

    # dashboard_disagreements.tsv
    buf = ['site\tdate\tdashboard_cfs\trecomputed_cfs\tdashboard_ice\trecomputed_ice\t'
           'q_agrees\tice_agrees']
    drows = []
    with open(dp('hydro_dash_export.tsv'), newline='') as fh:
        for row in csv.DictReader(fh, delimiter='\t'):
            date = str(row['date']).strip()
            lst = iso_naive(date + ' 12:00')
            site = resolver.resolve(row['station'], clock.utc_from_lst(lst))
            if site is None or site not in site_set:
                continue
            day = dt.datetime.strptime(date, '%Y-%m-%d').date()
            if day not in day_set:
                continue
            rec = daily[(site, day)]
            dv = str(row['daily_cfs']).strip()
            rv = rec['mean']
            if dv == '' and rv is None:
                q_ok = True
            elif dv == '' or rv is None:
                q_ok = False
            else:
                q_ok = F(dv) == F(rv)
            dice = str(row['ice_flag']).strip().upper()
            rice = 'Y' if 'ICE' in rec['codes'].split(';') else 'N'
            ice_ok = dice == rice
            if q_ok and ice_ok:
                continue
            drows.append((site, date, dv, fmt(rv) if rv is not None else '', dice, rice,
                          'Y' if q_ok else 'N', 'Y' if ice_ok else 'N'))
    for row in sorted(drows, key=lambda r: (r[0], r[1])):
        buf.append('\t'.join(row))
    out['dashboard_disagreements.tsv'] = '\n'.join(buf) + '\n'

    # cache_divergence.jsonl
    uv_index = dict(((r['site'], r['lst']), r) for r in uv_rows)
    centries = []
    for line in open(dp('uv_cache_r3.jsonl')):
        line = line.strip()
        if not line:
            continue
        o = json.loads(line)
        lst = iso_naive(o['t_lst'])
        site = resolver.resolve(o['station'], clock.utc_from_lst(lst))
        if site is None or site not in site_set:
            continue
        r = uv_index.get((site, lst))
        cached = dstr(o['q_cfs'])
        rec = fmt(r['q']) if r is not None else None
        if rec is None:
            status = 'MISSING'
        else:
            status = 'CURRENT' if F(rec) == F(cached) else 'STALE'
        centries.append((site, lst, jline({
            'site': site, 'time_lst': fmt_time(lst), 'cached_cfs': Raw(cached),
            'recomputed_cfs': Raw(rec) if rec is not None else None, 'status': status})))
    centries.sort(key=lambda e: (e[0], e[1]))
    out['cache_divergence.jsonl'] = ''.join(e[2] + '\n' for e in centries)

    # reconciliation.md
    lines = ['# Reconciliation', '', '## Summary', '',
             '| site | published_days | recomputed_days | compared | diff_count |'
             ' mean_diff_cfs |', '| --- | --- | --- | --- | --- | --- |']
    for site in sites:
        pdays = sum(1 for (s, d), v in pub.items() if s == site and v != '')
        rdays = sum(1 for day in period_days if daily[(site, day)]['mean'] is not None)
        compared = 0
        diffc = 0
        total = Fraction(0)
        for day in period_days:
            p = pub.get((site, day.isoformat()), '')
            r = daily[(site, day)]['mean']
            if p != '' and r is not None:
                compared += 1
                diff = F(r) - F(p)
                total += diff
                if diff != 0:
                    diffc += 1
        lines.append('| %s | %d | %d | %d | %d | %s |'
                     % (site, pdays, rdays, compared, diffc,
                        fmt(rnd(total / compared, 2)) if compared else ''))
    lines += ['', '## Run settings', '', '| setting | published_run | in_force |',
              '| --- | --- | --- |']
    pack = []
    insec = False
    for line in open(dp('dv_compute_pack.md')).read().split('\n'):
        if line.strip().lower().startswith('## run settings'):
            insec = True
            continue
        if insec:
            if line.startswith('#'):
                break
            m = re.match(r'^\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|\s*$', line)
            if m and m.group(1) != 'setting' and set(m.group(1)) - set('-: '):
                pack.append((m.group(1), m.group(2)))
    others = ['record_mean', 'shift_in_use', 'time_weighted_discharge', 'local_standard_time',
              'prorated_visit_errors', 'seq_order']
    oi = 0
    for setting, value in pack:
        if setting == 'rating_sheet':
            force = rating_sheet
        elif setting == 'tolerance_table':
            force = tol_id
        elif setting == 'errata':
            force = err_id
        else:
            force = others[oi] if oi < len(others) else ''
            oi += 1
        lines.append('| %s | %s | %s |' % (setting, value, force))
    lines += ['', '## Measurement decisions', '',
              '| site | measurements | shift | check | ice | rejected | no_record |',
              '| --- | --- | --- | --- | --- | --- | --- |']
    for site in sites:
        ms = [m for m in mlist if m['site'] == site]
        cnt = dict((d, sum(1 for m in ms if m['decision'] == d))
                   for d in ('SHIFT', 'CHECK', 'ICE', 'REJECTED', 'NO_RECORD'))
        lines.append('| %s | %d | %d | %d | %d | %d | %d |'
                     % (site, len(ms), cnt['SHIFT'], cnt['CHECK'], cnt['ICE'],
                        cnt['REJECTED'], cnt['NO_RECORD']))
    out['reconciliation.md'] = '\n'.join(lines) + '\n'

    # ---- write -------------------------------------------------------------
    files = []
    for name in REPORTS:
        data = out[name].encode('utf-8')
        with open(os.path.join(out_dir, name), 'wb') as fh:
            fh.write(data)
        files.append({'name': name, 'bytes': len(data),
                      'sha256': hashlib.sha256(data).hexdigest()})
    with open(os.path.join(out_dir, 'manifest.json'), 'wb') as fh:
        fh.write((jenc({'files': files}) + '\n').encode('utf-8'))


if __name__ == '__main__':
    main(sys.argv)
