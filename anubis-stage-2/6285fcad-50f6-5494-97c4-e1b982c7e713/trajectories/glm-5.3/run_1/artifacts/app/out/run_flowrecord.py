#!/usr/bin/env python3
"""CBHS streamflow record recomputation (handbook revision 11).

Usage: python3 run_flowrecord.py DATA_DIR OUT_DIR
"""
import csv
import datetime
import hashlib
import json
import math
import os
import re
import sqlite3
import sys
import zipfile
import zlib
import xml.etree.ElementTree as ET
from decimal import Decimal
from fractions import Fraction

# ---------------------------------------------------------------- utilities

DAY = 86400
MIN = 60


def round_half_even(frac, unit_den):
    if frac < 0:
        return -round_half_even(-frac, unit_den)
    n = frac * unit_den
    whole = n.numerator // n.denominator
    rem = n - whole
    half = Fraction(1, 2)
    if rem > half or (rem == half and whole % 2 == 1):
        whole += 1
    return Fraction(whole, unit_den)


def round_dec(frac, places):
    return round_half_even(frac, 10 ** places)


def round_sig(frac, n):
    if frac == 0:
        return Fraction(0)
    if frac < 0:
        return -round_sig(-frac, n)
    try:
        e = int(math.floor(math.log10(float(frac))))
    except (OverflowError, ValueError):
        e = 400 if float(frac) > 1 else -400
    ten = Fraction(10)
    while ten ** e > frac:
        e -= 1
    while ten ** (e + 1) <= frac:
        e += 1
    unit = ten ** (e - n + 1)
    scaled = frac / unit
    whole = scaled.numerator // scaled.denominator
    rem = scaled - whole
    half = Fraction(1, 2)
    if rem > half or (rem == half and whole % 2 == 1):
        whole += 1
    return Fraction(whole) * unit


def _plain_decimal(frac):
    """Plain decimal text of a Fraction whose denominator divides a power of ten."""
    r = frac
    t = 0
    while r.denominator != 1 and t < 400:
        r *= 10
        t += 1
    if r.denominator != 1:
        return None
    return format(Decimal(r.numerator).scaleb(-t), 'f')


def fmt_places(frac, places):
    """Format a value with exactly `places` decimals, half to even."""
    r = round_dec(frac, places)
    scaled = r * (10 ** places)
    if scaled.denominator == 1:
        return format(Decimal(scaled.numerator).scaleb(-places), 'f')
    return format(Decimal(r.numerator) / Decimal(r.denominator), 'f')


def fmt_rsig(frac):
    """Format a value that is already rounded to significant figures."""
    out = _plain_decimal(frac)
    if out is None:
        return format(Decimal(frac.numerator) / Decimal(frac.denominator), 'f')
    return out


def discharge_round(frac):
    if frac < 0:
        return -discharge_round(-frac)
    if frac < 1:
        return round_dec(frac, 2)
    if frac < 10:
        return round_dec(frac, 1)
    if frac < 1000:
        return round_dec(frac, 0)
    return round_sig(frac, 3)


def discharge_fmt(frac):
    """Discharge-table text of an exact value."""
    if frac < 1:
        return fmt_places(frac, 2)
    if frac < 10:
        return fmt_places(frac, 1)
    if frac < 1000:
        return fmt_places(frac, 0)
    return fmt_rsig(round_sig(frac, 3))


# ---------------------------------------------------------------- time

ISO_RE = re.compile(r'^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2}))?'
                    r'(?:([+-])(\d{2}):?(\d{2})|Z)?$')


def epoch_days(d):
    return (d - datetime.date(1970, 1, 1)).days


def days_epoch(n):
    return datetime.date(1970, 1, 1) + datetime.timedelta(days=n)


def naive_to_epoch(s):
    s = s.strip()
    s = s.replace('T', ' ')
    parts = s.split(' ')
    y, m, d = [int(x) for x in parts[0].split('-')]
    if len(parts) > 1 and parts[1]:
        hh = parts[1].replace('Z', '')
        if ':' in hh:
            h, mi = [int(x) for x in hh.split(':')[:2]]
        else:
            hh = hh[:4]
            h, mi = int(hh[:2]), int(hh[2:4])
    else:
        h = mi = 0
    return epoch_days(datetime.date(y, m, d)) * DAY + h * 3600 + mi * MIN


def epoch_to_naive(t):
    t = int(t)
    d = days_epoch(t // DAY)
    rem = t % DAY
    return '%s %02d:%02d' % (d.isoformat(), rem // 3600, (rem % 3600) // MIN)


def iso_to_epoch(s):
    m = ISO_RE.match(s.strip())
    if not m:
        return naive_to_epoch(s)
    y, mo, d, h, mi, se, sign, oh, om = m.groups()
    t = epoch_days(datetime.date(int(y), int(mo), int(d))) * DAY + int(h) * 3600 + int(mi) * MIN + (int(se or 0))
    if sign:
        t -= (int(oh) * 3600 + int(om) * MIN) * (1 if sign == '+' else -1)
    return t


def serial_to_date(serial, system1904):
    base = datetime.date(1904, 1, 1) if system1904 else datetime.date(1899, 12, 30)
    return base + datetime.timedelta(days=int(serial))


class Clock(object):
    def __init__(self, cfg):
        self.offset = int(cfg['standard_offset_minutes']) * MIN
        self.rule = cfg.get('dst_rule')
        self.spans = []
        for t in cfg.get('transitions') or []:
            self.spans.append((iso_to_epoch(t['start_utc']), iso_to_epoch(t['end_utc'])))

    def dst(self, t):
        if self.rule in (None, 'none', ''):
            return False
        for a, b in self.spans:
            if a <= t < b:
                return True
        return False

    def lst_to_epoch(self, s):
        return naive_to_epoch(s) - self.offset

    def epoch_to_lst(self, t):
        return epoch_to_naive(t + self.offset)

    def wall_to_epoch(self, s):
        base = naive_to_epoch(s) - self.offset
        if self.dst(base - 3600):
            return base - 3600
        return base


# ---------------------------------------------------------------- YAML subset

def yaml_load(path):
    text = open(path, encoding='utf-8').read()
    return yaml_parse(text.split('\n'))


def _scalar(s):
    s = s.strip()
    if s == '':
        return None
    if '#' in s and not (s[0] == '\'' or s[0] == '"'):
        s = s.split('#', 1)[0].rstrip()
        if s == '':
            return None
    if s in ('null', '~'):
        return None
    if (s[0] == '\'' and s[-1] == '\'') or (s[0] == '"' and s[-1] == '"'):
        return s[1:-1]
    if s in ('true', 'True'):
        return True
    if s in ('false', 'False'):
        return False
    return s


def _is_flow(s):
    s = s.strip()
    return s.startswith('[') or s.startswith('{')


def _split_flow(s):
    out = []
    depth = 0
    cur = ''
    quote = None
    for ch in s:
        if quote:
            cur += ch
            if ch == quote:
                quote = None
            continue
        if ch in '\'"':
            quote = ch
            cur += ch
        elif ch in '[{':
            depth += 1
            cur += ch
        elif ch in ']}':
            depth -= 1
            cur += ch
        elif ch == ',' and depth == 0:
            if cur.strip():
                out.append(cur)
            cur = ''
        else:
            cur += ch
    if cur.strip():
        out.append(cur)
    return out


def _flow(s):
    s = s.strip()
    if s.startswith('['):
        items = _split_flow(s[1:-1])
        return [_flow(i) if _is_flow(i) else _scalar(i) for i in items]
    if s.startswith('{'):
        items = _split_flow(s[1:-1])
        out = {}
        for it in items:
            if ':' in it:
                k, v = it.split(':', 1)
                v = v.strip()
                out[_scalar(k)] = _flow(v) if _is_flow(v) else _scalar(v)
        return out
    return _scalar(s)


def _indent(line):
    return len(line) - len(line.lstrip(' '))


def yaml_parse(lines):
    lines = [l for l in lines if l.strip() and not l.strip().startswith('#')]
    pos = [0]

    def parse_map(indent):
        out = {}
        while pos[0] < len(lines):
            line = lines[pos[0]]
            ind = _indent(line)
            if ind < indent:
                break
            body = line.strip()
            if body.startswith('- '):
                if ind == indent:
                    break
                pos[0] += 1
                continue
            if ':' not in body:
                pos[0] += 1
                continue
            if body[0] in '\'"':
                q = body[0]
                end = body.find(q, 1)
                if end < 0:
                    pos[0] += 1
                    continue
                key = _scalar(body[:end + 1])
                rest = body[end + 1:].lstrip()
                if not rest.startswith(':'):
                    pos[0] += 1
                    continue
                rest = rest[1:].strip()
            else:
                key, rest = body.split(':', 1)
                key = _scalar(key)
                rest = rest.strip()
            pos[0] += 1
            if rest:
                out[key] = _flow(rest) if _is_flow(rest) else _scalar(rest)
            else:
                if pos[0] < len(lines):
                    nxt = lines[pos[0]]
                    ni = _indent(nxt)
                    if ni > indent:
                        out[key] = parse_block(ni)
                    elif ni == indent and nxt.strip().startswith('- '):
                        out[key] = parse_seq(ni)
                    else:
                        out[key] = None
                else:
                    out[key] = None
        return out

    def parse_seq(indent):
        out = []
        while pos[0] < len(lines):
            line = lines[pos[0]]
            ind = _indent(line)
            if ind != indent:
                break
            body = line.strip()
            if not body.startswith('-'):
                break
            item = body[1:].strip()
            if item and ':' in item and not _is_flow(item):
                offset = line.index('-') + 1
                lines[pos[0]] = ' ' * offset + item
                out.append(parse_map(offset))
                continue
            pos[0] += 1
            if not item:
                continue
            if _is_flow(item):
                out.append(_flow(item))
            else:
                out.append(_scalar(item))
                if pos[0] < len(lines) and _indent(lines[pos[0]]) > indent:
                    out[-1] = parse_block(_indent(lines[pos[0]]))
        return out

    def parse_block(indent):
        if lines[pos[0]].lstrip().startswith('- '):
            return parse_seq(indent)
        return parse_map(indent)

    if not lines:
        return {}
    return parse_block(_indent(lines[0]))


# ---------------------------------------------------------------- PDF minutes

def _pdf_streams(path):
    data = open(path, 'rb').read()
    objs = {}
    for m in re.finditer(rb'(\d+)\s+(\d+)\s+obj\b(.*?)\bendobj', data, re.S):
        objs[int(m.group(1))] = m.group(3)
    root = None
    m = re.search(rb'/Root\s+(\d+)\s+0\s+R', data)
    if m:
        root = int(m.group(1))
    page_order = []
    if root in objs:
        m = re.search(rb'/Pages\s+(\d+)\s+0\s+R', objs[root])
        if m and int(m.group(1)) in objs:
            kids = re.search(rb'/Kids\s*\[(.*?)\]', objs[int(m.group(1))], re.S)
            if kids:
                page_order = [int(x) for x in re.findall(rb'(\d+)\s+0\s+R', kids.group(1))]
    if not page_order:
        page_order = sorted(n for n, b in objs.items()
                            if b.lstrip().startswith(b'<<') and b'/Type/Page' in b and b'/Type/Pages' not in b)
    out = []
    for pn in page_order:
        b = objs.get(pn, b'')
        m = re.search(rb'/Contents\s+(\d+)\s+0\s+R', b)
        if not m:
            continue
        c = objs.get(int(m.group(1)), b'')
        mm = re.search(rb'stream\r?\n(.*?)\r?\nendstream', c, re.S)
        if not mm:
            continue
        raw = mm.group(1)
        if b'/FlateDecode' in c:
            raw = zlib.decompress(raw)
        out.append(raw.decode('latin1'))
    return out


def _pdf_literal(s):
    out = []
    i = 0
    while i < len(s):
        c = s[i]
        if c == '\\' and i + 1 < len(s):
            i += 1
            n = s[i]
            if n == 'n':
                out.append('\n')
            elif n == 'r':
                out.append('\r')
            elif n == 't':
                out.append('\t')
            elif n in '01234567':
                j = i
                while j < len(s) and j < i + 3 and s[j] in '01234567':
                    j += 1
                out.append(chr(int(s[i:j]) & 0xFF))
                i = j
                continue
            else:
                out.append(n)
            i += 1
        else:
            out.append(c)
            i += 1
    return ''.join(out)


_STR_RE = re.compile(r'\(((?:[^()\\]|\\.)*)\)|<([0-9A-Fa-f\s]*)>')


def _pdf_text_items(stream):
    """Return list of (x, y, text) from a PDF content stream."""
    items = []
    for m in re.finditer(r'BT(?:(?!\bET\b).)*?Tm(?:(?!\bET\b).)*?(?=\bET\b)', stream, re.S):
        body = m.group(0)[2:]
        tm = None
        for mm in re.finditer(r'(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+'
                              r'(-?[\d.]+)\s+(-?[\d.]+)\s+Tm', body):
            tm = (float(mm.group(5)), float(mm.group(6)))
        if tm is None:
            continue
        text = []
        for sm in re.finditer(r'\(((?:[^()\\]|\\.)*)\)\s*Tj|<([0-9A-Fa-f\s]*)>\s*Tj'
                               r'|\[(.*?)\]\s*TJ', body, re.S):
            if sm.group(1) is not None:
                text.append(_pdf_literal(sm.group(1)))
            elif sm.group(2) is not None:
                try:
                    text.append(bytes.fromhex(re.sub(r'\s', '', sm.group(2))).decode('latin1'))
                except Exception:
                    pass
            else:
                inner = sm.group(3)
                for pm in _STR_RE.finditer(inner):
                    if pm.group(1) is not None:
                        text.append(_pdf_literal(pm.group(1)))
                    else:
                        try:
                            text.append(bytes.fromhex(re.sub(r'\s', '', pm.group(2))).decode('latin1'))
                        except Exception:
                            pass
        joined = ''.join(text)
        if not joined:
            m2 = re.search(r'Tm\s+\(([^)]*)\)', body)
            if m2:
                joined = _pdf_literal(m2.group(1))
        if joined:
            items.append((tm[0], tm[1], joined))
    return items


def pdf_minutes(path):
    """Parse the review board minutes into {table_id: {'status':..., 'header':[...], 'rows':[[...]]}}."""
    streams = _pdf_streams(path)
    pages = []
    allx = set()
    for s in streams:
        items = _pdf_text_items(s)
        pages.append(items)
        for x, y, t in items:
            allx.add(x)
    xs = sorted(allx)
    clusters = []
    for x in xs:
        if clusters and x - clusters[-1][-1] < 43:
            clusters[-1].append(x)
        else:
            clusters.append([x])
    centers = [sum(c) / len(c) for c in clusters]
    ncols = len(centers)

    # build page rows
    page_rows = []
    for items in pages:
        grid = {}
        for x, y, t in items:
            ci = min(range(ncols), key=lambda i: abs(centers[i] - x))
            grid.setdefault((y, ci), []).append((x, t))
        # rows sharing one baseline; text drawn at nearly the same y is one row
        buckets = []
        for (y, ci) in sorted(grid, key=lambda k: (-k[0], k[1])):
            for b in buckets:
                if abs(b[0] - y) < 3:
                    b[1].setdefault(ci, []).extend(grid[(y, ci)])
                    break
            else:
                buckets.append([y, {ci: list(grid[(y, ci)])}])
        rows = []
        for y, cells in buckets:
            d = {}
            for ci, parts in cells.items():
                d[ci] = ''.join(p[1] for p in sorted(parts))
            rows.append(d)
        page_rows.append(rows)

    tables = []
    order = []
    for rows in page_rows:
        current = None
        for cells in rows:
            c0 = cells.get(0, '')
            m = re.match(r'^Table ([A-Za-z0-9-]+): (.*?)\s*\[([^\]]*)\]\s*$', c0.strip())
            mc = re.match(r'^Table ([A-Za-z0-9-]+) \(continued\)\s*$', c0.strip())
            if m:
                current = {'id': m.group(1), 'title': m.group(2).strip(),
                           'status': m.group(3).strip(), 'header': None, 'rows': []}
                tables.append(current)
                order.append(current['id'])
                continue
            if mc:
                tid = mc.group(1)
                current = None
                for t in tables:
                    if t['id'] == tid:
                        current = t
                        break
                if current is None:
                    current = {'id': tid, 'title': '', 'status': '', 'header': None, 'rows': []}
                    tables.append(current)
                    order.append(tid)
                continue
            if current is None:
                continue
            vals = [cells.get(i, '').strip() for i in range(ncols)]
            nonempty = [v for v in vals if v]
            if len(nonempty) < 2:
                # single-cell rows are notes, except a lone column-1 cell that
                # belongs to the last accepted row (kerned station ids)
                if len(nonempty) == 1 and 1 in cells and cells[1].strip() and current['rows']:
                    prev = current['rows'][-1]
                    if not prev[1]:
                        prev[1] = cells[1].strip()
                continue
            if current['header'] is None:
                current['header'] = vals
            else:
                current['rows'].append(vals)
    out = {}
    for t in tables:
        out[t['id']] = t
    return out



# ---------------------------------------------------------------- xlsx reader

NS_MAIN = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
NS_REL = '{http://schemas.openxmlformats.org/package/2006/relationships}'


def xlsx_sheets(path):
    """Return {sheet_name: [row, ...]} where row is a list of cell texts (None for empty)."""
    z = zipfile.ZipFile(path)
    shared = []
    if 'xl/sharedStrings.xml' in z.namelist():
        d = z.read('xl/sharedStrings.xml').decode('utf-8')
        for m in re.finditer(r'<si>(.*?)</si>', d, re.S):
            shared.append(''.join(re.findall(r'<t[^>]*>(.*?)</t>', m.group(1), re.S)))
    wbx = z.read('xl/workbook.xml').decode('utf-8')
    rels = {}
    d = z.read('xl/_rels/workbook.xml.rels').decode('utf-8')
    for m in re.finditer(r'<Relationship\b[^>]*/?>', d):
        tag = m.group(0)
        rid = re.search(r'Id="([^"]*)"', tag).group(1)
        tgt = re.search(r'Target="([^"]*)"', tag).group(1)
        rels[rid] = tgt
    date1904 = 'date1904="1"' in wbx or 'date1904="true"' in wbx.lower()
    sheets = {}
    for m in re.finditer(r'<sheet\b[^>]*/?>', wbx):
        tag = m.group(0)
        name = re.search(r'name="([^"]*)"', tag).group(1)
        rid = re.search(r'r:id="([^"]*)"', tag).group(1)
        tgt = rels.get(rid)
        if not tgt:
            continue
        part = tgt if tgt.startswith('xl/') else 'xl/' + tgt.lstrip('/')
        rows = []
        root = ET.fromstring(z.read(part))
        for row in root.iter(NS_MAIN + 'row'):
            out = []
            for c in row.iter(NS_MAIN + 'c'):
                ref = c.get('r') or ''
                mm = re.match(r'([A-Z]+)', ref)
                if mm:
                    col = 0
                    for ch in mm.group(1):
                        col = col * 26 + (ord(ch) - 64)
                    idx = col - 1
                else:
                    idx = len(out)
                while len(out) < idx:
                    out.append(None)
                t = c.get('t')
                is_ = c.find(NS_MAIN + 'is')
                v = c.find(NS_MAIN + 'v')
                if is_ is not None:
                    val = ''.join(x.text or '' for x in is_.iter(NS_MAIN + 't'))
                elif v is None:
                    val = None
                elif t == 's':
                    val = shared[int(v.text)]
                else:
                    val = v.text
                out.append(val)
            rows.append(out)
        sheets[name] = rows
    return sheets, date1904


# ---------------------------------------------------------------- shard readers
#
# Every reader yields records as dicts:
#   token, sensor ('P'/'B'), instant (UTC epoch seconds), value (str or None),
#   unit (str or None: 'ft','m','cm','mm'), qual ('G','S','E','X'), rev (int), void (bool)


def _num(text):
    s = str(text).strip()
    return s if s else None


def _read_L01(path):
    with open(path, encoding='utf-8') as fh:
        for row in _csv_rows(fh):
            tok = row['station']
            if tok is None:
                continue
            yield {'token': tok, 'sensor': (row['sensor'] or 'P').strip() or 'P',
                   'instant': iso_to_epoch(row['obs_utc']), 'value': _num(row['stage']),
                   'unit': None, 'qual': (row['qual'] or 'G').strip() or 'G',
                   'rev': int(row['rev'] or 1),
                   'void': str(row['void']).strip() in ('1', 'true', 'True')}


def _csv_rows(fh, delim=','):
    """csv rows as dicts, skipping whole-line comments, blank lines and repeated headers."""
    rd = csv.reader(fh, delimiter=delim)
    header = None
    for parts in rd:
        if not parts:
            continue
        if parts[0].lstrip().startswith('#'):
            continue
        if header is None:
            header = [p.strip() for p in parts]
            continue
        if len(parts) == len(header) and [p.strip() for p in parts] == header:
            continue
        d = {}
        for i, h in enumerate(header):
            d[h] = parts[i] if i < len(parts) else None
        yield d


def _read_L02(path, clock):
    with open(path, encoding='utf-8') as fh:
        for row in csv.DictReader(fh):
            if (row['hour'] or '').strip().upper() == 'MEAN':
                continue
            hour = int(row['hour'])
            base = row['date_lst'].strip() + ' %02d:00' % hour
            t = clock.lst_to_epoch(base)
            unit = (row['unit'] or '').strip().lower()
            rev = int(row['rev'] or 1)
            for col, minute in (('m00', 0), ('m15', 15), ('m30', 30), ('m45', 45)):
                v = _num(row.get(col))
                if v is None:
                    continue
                yield {'token': row['site_id'].strip(), 'sensor': 'P', 'instant': t + minute * MIN,
                       'value': v, 'unit': unit, 'qual': 'G', 'rev': rev, 'void': False}


def _read_L03(path):
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            line = line.rstrip('\n')
            if not line.strip() or line.startswith('#'):
                continue
            parts = line.split('\t')
            if parts[0].strip() == 'gauge':
                continue
            gauge, chan, t, h, unit, flag, rev, status = (parts + [''] * 8)[:8]
            yield {'token': gauge.strip(), 'sensor': 'B' if chan.strip() == '2' else 'P',
                   'instant': int(t), 'value': _num(h.replace(',', '.')),
                   'unit': unit.strip().lower(),
                   'qual': {'OK': 'G', 'SUS': 'S', 'EST': 'E', 'FLT': 'X'}.get(flag.strip(), 'G'),
                   'rev': int(rev or 1), 'void': status.strip().upper() == 'VOID'}


def _read_L04(path, clock):
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            line = line.rstrip('\n')
            if not line.strip():
                continue
            parts = line.split('\t')
            if parts[0].strip() == 'STN':
                continue
            stn, sensor, wall, gh, q, rev = (parts + [''] * 6)[:6]
            yield {'token': stn.strip(), 'sensor': 'B' if sensor.strip().upper() == 'BAK' else 'P',
                   'instant': clock.wall_to_epoch(wall.strip()), 'value': _num(gh),
                   'unit': None,
                   'qual': {'A': 'G', 'S': 'S', 'E': 'E', 'F': 'X'}.get(q.strip().upper(), 'G'),
                   'rev': int(rev or 1), 'void': False}


def _read_L05(path):
    with open(path, encoding='utf-8') as fh:
        for row in csv.DictReader(fh, delimiter='|'):
            v = _num(row['value_cm'])
            yield {'token': row['site'].strip(), 'sensor': 'B' if row['sens'].strip() == '2' else 'P',
                   'instant': int(int(row['ts_ms']) / 1000), 'value': v, 'unit': 'cm',
                   'qual': {'0': 'G', '1': 'S', '2': 'E', '9': 'X'}.get((row['q'] or '').strip(), 'G'),
                   'rev': int(row['rv'] or 1),
                   'void': (row['vd'] or '').strip().upper() == 'Y'}


def _read_L06(path):
    with open(path, encoding='utf-8') as fh:
        for row in csv.DictReader(fh, delimiter='|'):
            m = re.match(r'^\s*(-?[\d.,]+)\s*(ft|m)?\s*$', row['stage'] or '', re.I)
            if not m:
                continue
            yield {'token': row['alias'].strip(), 'sensor': 'P',
                   'instant': iso_to_epoch(row['when']), 'value': m.group(1).replace(',', '.'),
                   'unit': (m.group(2) or '').lower() or None,
                   'qual': (row['code'] or 'g').strip().upper() or 'G',
                   'rev': int(row['ver'] or 1), 'void': False}


def _read_L07(path, clock):
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            o = json.loads(line)
            if o.get('type') == 'hb':
                continue
            t = o['t']
            lst = '%s-%s-%s %s:%s' % (t[0:4], t[4:6], t[6:8], t[9:11], t[11:13])
            yield {'token': str(o['s']), 'sensor': o.get('k', 'P') or 'P',
                   'instant': clock.lst_to_epoch(lst), 'value': _num(o.get('v')),
                   'unit': (o.get('u') or '').lower(),
                   'qual': (o.get('q') or 'G').upper() or 'G',
                   'rev': int(o.get('r', 1) or 1), 'void': bool(o.get('x'))}


def _read_L08(path):
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            o = json.loads(line)
            gh = o.get('reading', {}).get('gh', {}) or {}
            meta = o.get('meta', {}) or {}
            yield {'token': str(o['station']['id']),
                   'sensor': 'B' if (meta.get('channel') == 'backup') else 'P',
                   'instant': iso_to_epoch(o['reading']['time_utc']), 'value': _num(gh.get('value')),
                   'unit': (gh.get('unit') or '').lower(),
                   'qual': {'good': 'G', 'suspect': 'S', 'estimated': 'E', 'fault': 'X'}.get(meta.get('quality'), 'G'),
                   'rev': int(meta.get('rev', 1) or 1), 'void': bool(meta.get('void'))}


def _read_L09(path):
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            o = json.loads(line)
            t = iso_to_epoch(o['hour_utc'] + ':00Z')
            unit = (o.get('unit') or '').lower()
            rev = int(o.get('rev', 1) or 1)
            for i, v in enumerate(o.get('vals') or []):
                if v is None:
                    continue
                yield {'token': str(o['site']), 'sensor': 'P', 'instant': t + i * 15 * MIN,
                       'value': _num(v), 'unit': unit, 'qual': 'G', 'rev': rev, 'void': False}


def _read_L10(path):
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            o = json.loads(line)
            yield {'token': str(o['id']), 'sensor': 'B', 'instant': int(o['epoch']),
                   'value': _num(o.get('stage_m')), 'unit': 'm',
                   'qual': (o.get('qa') or 'G').upper() or 'G', 'rev': int(o.get('rev', 1) or 1),
                   'void': str(o.get('deleted')) == '1' or o.get('deleted') is True}


def _read_L11(path):
    site = None
    for ev, el in ET.iterparse(path, events=('start', 'end')):
        if ev == 'start':
            if el.tag.endswith('site'):
                site = (el.get('code') or '').strip()
            continue
        if el.tag.endswith('site'):
            el.clear()
        elif el.tag.endswith('r') and site is not None:
            yield {'token': site, 'sensor': (el.get('s') or 'P'),
                   'instant': iso_to_epoch(el.get('t')), 'value': _num(el.get('v')), 'unit': None,
                   'qual': {'GOOD': 'G', 'SUSP': 'S', 'EST': 'E', 'FAULT': 'X'}.get((el.get('q') or 'GOOD').upper(), 'G'),
                   'rev': int(el.get('rev') or 1),
                   'void': (el.get('void') or '0').strip() == '1'}
            el.clear()


def _read_L12(path, clock):
    for ev, el in ET.iterparse(path, events=('end',)):
        if not el.tag.endswith('reading'):
            continue
        st = el.find('station')
        time = el.find('time')
        value = el.find('value')
        qual = el.find('qual')
        rev = el.find('rev')
        zone = (time.get('zone') or 'UTC').upper()
        txt = (time.text or '').strip()
        dd, tm = txt.split(' ')
        iso = '%s-%s-%s %s' % (dd[6:10], dd[3:5], dd[0:2], tm)
        if zone == 'UTC':
            instant = iso_to_epoch(iso.replace(' ', 'T') + 'Z')
        elif zone == 'LST':
            instant = clock.lst_to_epoch(iso)
        else:
            instant = clock.wall_to_epoch(iso)
        yield {'token': (st.text or '').strip(), 'sensor': 'P', 'instant': instant,
               'value': _num(value.text), 'unit': (value.get('unit') or '').lower(),
               'qual': {'10': 'G', '30': 'S', '40': 'E', '90': 'X'}.get((qual.text or '10').strip(), 'G'),
               'rev': int(rev.text) if rev is not None else 1, 'void': False}
        el.clear()


def _read_L13(path, clock):
    date_re = re.compile(r'^\d{4}-\d{2}-\d{2}$')
    time_re = re.compile(r'^\d{4}$')
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            line = line.rstrip('\n')
            if len(line) < 34:
                continue
            st = line[0:10].strip()
            dt = line[10:20].strip()
            tm = line[21:25].strip()
            val = line[26:33].strip()
            unit = line[34:36].strip().lower()
            q = line[37:38].strip().upper() or 'G'
            rv = line[39:41].strip() or '1'
            # title, header, dashed rules, PAGE and END OF REPORT lines carry no
            # date and time in the fixed columns
            if not st or not val or not date_re.match(dt) or not time_re.match(tm):
                continue
            yield {'token': st, 'sensor': 'P',
                   'instant': clock.lst_to_epoch(dt + ' ' + tm[:2] + ':' + tm[2:4]),
                   'value': val, 'unit': unit, 'qual': q, 'rev': int(rv), 'void': False}


_READLINE_RE = re.compile(r'^(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})Z\s+stn=(\S+)\s+'
                          r'sensor=(\S+)\s+gh=(-?[\d.,]+)\s*(ft|m)\s+q=(\S+)\s+rev=(\d+)\s*$',
                          re.IGNORECASE)
_VOIDLINE_RE = re.compile(r'^VOID stn=(\S+) sensor=(\S+) t=(\S+) rev=(\d+)\s*$')


def _read_L14(path):
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            s = line.strip()
            if not s or s.startswith('NOTE'):
                continue
            m = _VOIDLINE_RE.match(s)
            if m:
                yield {'token': m.group(1), 'sensor': m.group(2), 'instant': iso_to_epoch(m.group(3)),
                       'value': None, 'unit': None, 'qual': 'G', 'rev': int(m.group(4)), 'void': True}
                continue
            m = _READLINE_RE.match(s)
            if m:
                yield {'token': m.group(3), 'sensor': m.group(4),
                       'instant': iso_to_epoch(m.group(1) + 'T' + m.group(2) + 'Z'),
                       'value': m.group(5).replace(',', '').strip(), 'unit': m.group(6).lower(),
                       'qual': m.group(7).upper(), 'rev': int(m.group(8)), 'void': False}


def _read_L15(path):
    data = yaml_load(path)
    for block in data.get('blocks') or []:
        tok = str(block.get('station'))
        sensor = 'B' if str(block.get('sensor')).lower() == 'backup' else 'P'
        unit = str(block.get('unit') or '').lower()
        for row in block.get('rows') or []:
            yield {'token': tok, 'sensor': sensor, 'instant': int(str(row[0])),
                   'value': _num(row[1]), 'unit': unit,
                   'qual': str(row[2]).strip().upper() if len(row) > 2 else 'G',
                   'rev': int(row[3]) if len(row) > 3 else 1, 'void': False}


def _read_L16(path):
    data = yaml_load(path)
    for tok, minutes in (data.get('stations') or {}).items():
        for key, val in (minutes or {}).items():
            t = iso_to_epoch(str(key))
            reads = val if isinstance(val, list) else [val]
            for rd in reads:
                yield {'token': str(tok), 'sensor': 'P', 'instant': t,
                       'value': _num(rd.get('v')), 'unit': str(rd.get('u') or '').lower(),
                       'qual': 'G', 'rev': int(rd.get('r') or 1), 'void': False}


def _read_L17(path):
    with open(path, encoding='utf-8') as fh:
        doc = json.load(fh)
    dflt = str((doc.get('meta') or {}).get('unit') or '').lower()
    for run in doc.get('series') or []:
        unit = str(run.get('unit') or dflt).lower()
        tok = str(run.get('site'))
        sensor = run.get('sensor') or 'P'
        start = int(run['start'])
        step = int(run['step'])
        rev = int(run.get('rev') or 1)
        for i, v in enumerate(run.get('values') or []):
            if v is None:
                continue
            yield {'token': tok, 'sensor': sensor, 'instant': start + i * step,
                   'value': _num(v), 'unit': unit, 'qual': 'G', 'rev': rev, 'void': False}


def _read_L18(path, clock):
    con = sqlite3.connect('file:%s?mode=ro' % path, uri=True)
    try:
        sites = {}
        for sid, token in con.execute('select sid, token from sites'):
            sites[sid] = token
        for sid, sensor, tser, value, unit, q, rev, void in con.execute(
                'select sid, sensor, t_serial, value, unit, q, rev, void from readings order by rid'):
            ser = float(tser)
            total = Fraction(ser) * DAY
            mins = round_half_even(total / 60, 1)
            instant = clock.lst_to_epoch('1899-12-30 00:00') + int(mins) * 60
            val = repr(value) if value is not None else None
            yield {'token': sites.get(sid, ''), 'sensor': (sensor or 'P'),
                   'instant': instant, 'value': val, 'unit': (unit or '').lower(),
                   'qual': (q or 'G').upper() or 'G', 'rev': int(rev or 1),
                   'void': int(void or 0) == 1}
    finally:
        con.close()


def _read_L19(path):
    con = sqlite3.connect('file:%s?mode=ro' % path, uri=True)
    try:
        for stn, ts, gh, sensor, rev, flag in con.execute(
                'select stn, ts, gh_mm, sensor, rev, flag from obs'):
            yield {'token': stn, 'sensor': (sensor or 'P'), 'instant': int(ts),
                   'value': _num(gh), 'unit': 'mm',
                   'qual': (flag or 'G').strip().upper() or 'G', 'rev': int(rev or 1), 'void': False}
        for stn, ts, sensor, rev in con.execute('select stn, ts, sensor, rev from voids'):
            yield {'token': stn, 'sensor': (sensor or 'P'), 'instant': int(ts),
                   'value': None, 'unit': 'mm', 'qual': 'G', 'rev': int(rev or 1), 'void': True}
    finally:
        con.close()


def _read_L20(path, clock):
    with open(path, encoding='utf-8') as fh:
        for row in csv.DictReader(fh):
            v = _num(row['gh_ft'])
            if v is None:
                continue
            yield {'token': row['site'].strip(), 'sensor': 'P',
                   'instant': clock.lst_to_epoch(row['time_lst'].strip()), 'value': v,
                   'unit': 'ft', 'qual': 'G', 'rev': 1, 'void': False}


def read_shard(path, layout, clock):
    if layout == 'L01':
        return _read_L01(path)
    if layout == 'L02':
        return _read_L02(path, clock)
    if layout == 'L03':
        return _read_L03(path)
    if layout == 'L04':
        return _read_L04(path, clock)
    if layout == 'L05':
        return _read_L05(path)
    if layout == 'L06':
        return _read_L06(path)
    if layout == 'L07':
        return _read_L07(path, clock)
    if layout == 'L08':
        return _read_L08(path)
    if layout == 'L09':
        return _read_L09(path)
    if layout == 'L10':
        return _read_L10(path)
    if layout == 'L11':
        return _read_L11(path)
    if layout == 'L12':
        return _read_L12(path, clock)
    if layout == 'L13':
        return _read_L13(path, clock)
    if layout == 'L14':
        return _read_L14(path)
    if layout == 'L15':
        return _read_L15(path)
    if layout == 'L16':
        return _read_L16(path)
    if layout == 'L17':
        return _read_L17(path)
    if layout == 'L18':
        return _read_L18(path, clock)
    if layout == 'L19':
        return _read_L19(path)
    if layout == 'L20':
        return _read_L20(path, clock)
    raise SystemExit('run_flowrecord: unknown layout ' + str(layout))

# ---------------------------------------------------------------- registers


class Registry(object):
    """All static inputs of one data directory."""

    def __init__(self, data):
        self.dir = data
        p = lambda name: os.path.join(data, name)
        self.clock = Clock(yaml_load(p('site_clock.yaml')))
        self.profile = yaml_load(p('dv_profile.yml'))
        self.overlay = (yaml_load(p('site_overlay.yaml')) or {}).get('sites') or {}
        self.minutes = pdf_minutes(p('hrb_26-04_minutes.pdf'))
        self.catalog = json.load(open(p('ingest_catalog.json'), encoding='utf-8'))
        self.sheets, self.date1904 = xlsx_sheets(p('cbhs_rt_26q2.xlsx'))
        self.net = self.profile['network']
        blk = self.profile['networks'][self.net]
        self.rating_sheet = blk['rating_sheet']
        self.index_sheet = blk['index_sheet']
        self.site_sheet = blk['site_sheet']
        self.period_start = str(self.profile['period_start']).strip()
        self.period_end = str(self.profile['period_end']).strip()
        self.max_gap_minutes = int(blk['max_gap_minutes'])
        self.min_coverage = Fraction(str(blk['min_coverage_fraction']).strip())
        self.record_margin_hours = int(blk['record_margin_hours'])
        self.drift_default_text = str(blk['drift_tolerance_ft']).strip()
        self.drift_default = Fraction(self.drift_default_text)

        # station master
        self.station_net = {}
        self.station_status = {}
        with open(p('stn_master.csv'), encoding='utf-8') as fh:
            for row in _csv_rows(fh):
                sid = (row['station_id'] or '').strip()
                self.station_net[sid] = (row['network'] or '').strip()
                self.station_status[sid] = (row['status'] or '').strip().upper()
        self.sites = sorted(s for s in self.station_net
                            if self.station_status[s] == 'ACTIVE' and self.station_net[s] == self.net)

        # cross-reference
        self.xref = _load_xref(p('stn_xref.sqlite'), p('xref_addendum.yml'))

        # equipment register
        self.equipment = {}
        with open(p('eqp_reg.tsv'), encoding='utf-8') as fh:
            rd = csv.DictReader(fh, delimiter='\t')
            for row in rd:
                key = ((row['site'] or '').strip(), (row['sensor'] or '').strip())
                vf = (row['valid_from_lst'] or '').strip()
                unit = (row['unit'] or '').strip().lower()
                self.equipment.setdefault(key, []).append((vf, unit))

        # datum history
        self.datum = {}
        with open(p('dtm_hist.psv'), encoding='utf-8') as fh:
            rd = csv.DictReader(fh, delimiter='|')
            for row in rd:
                key = ((row['site'] or '').strip(), (row['sensor'] or '').strip())
                vf = (row['valid_from_utc'] or '').strip()
                off = (row['offset_ft'] or '').strip()
                st = (row['status'] or '').strip().upper()
                self.datum.setdefault(key, []).append((vf, off, st))

        self.visits = _load_visits(p('fv_ledger_q2.db'), p('fv_amend.xml'), self.clock)
        self.measurements = _load_measurements(p('qm_main_26q2.csv'), p('qm_late.xml'))
        self.ice_obs = []
        with open(p('ice_obs_j2.ndjson'), encoding='utf-8') as fh:
            for line in fh:
                line = line.strip()
                if line:
                    self.ice_obs.append(json.loads(line))
        self.edits = []
        with open(p('uv_edits.jsonl'), encoding='utf-8') as fh:
            for line in fh:
                line = line.strip()
                if line:
                    self.edits.append(json.loads(line))
        self.pub_daily = _load_pub_daily(p('dv_pub_26q2.csv'))
        self.shift_pub = _load_shift_pub(p('shift_wksht_pub.csv'))
        self.dashboard = _load_dashboard(p('hydro_dash_export.tsv'))
        self.cache = _load_cache(p('uv_cache_r3.jsonl'))

    # -- settings resolution ------------------------------------------------
    def site_row(self, sid):
        rows = self.sheets.get(self.site_sheet) or []
        header = None
        for r in rows:
            vals = [v for v in r if v not in (None, '')]
            if len(vals) < 2:
                continue
            if header is None:
                header = [(v or '').strip() for v in r]
                continue
            d = {}
            for i, h in enumerate(header):
                d[h] = r[i] if i < len(r) else None
            if (d.get('site') or '').strip() == sid:
                return d
        return {}

    def drift_tol(self, sid):
        v = self.drift_tol_text(sid)
        return Fraction(v) if v else self.drift_default

    def drift_tol_text(self, sid):
        ov = self.overlay.get(sid) or {}
        if ov.get('drift_tolerance_ft') not in (None, ''):
            return str(ov['drift_tolerance_ft']).strip()
        row = self.site_row(sid)
        v = (row.get('drift_tol_ft') or '').strip()
        if v:
            return v
        return self.drift_default_text

    def max_gap(self, sid):
        ov = self.overlay.get(sid) or {}
        if ov.get('max_gap_minutes') not in (None, ''):
            return int(ov['max_gap_minutes'])
        return self.max_gap_minutes

    def drainage_area(self, sid):
        row = self.site_row(sid)
        v = (row.get('drainage_area_mi2') or '').strip()
        return Fraction(v) if v else None

    def eq_unit(self, sid, sensor, instant):
        rows = self.equipment.get((sid, sensor)) or []
        best = None
        for vf, unit in rows:
            if not vf:
                continue
            t = self.clock.lst_to_epoch(vf)
            if t <= instant and (best is None or t >= best[0]):
                best = (t, unit)
        return best[1] if best else None

    def offset(self, sid, sensor, instant):
        rows = self.datum.get((sid, sensor)) or []
        best = None
        for vf, off, st in rows:
            if st == 'WITHDRAWN':
                continue
            t = iso_to_epoch(vf)
            if t <= instant and (best is None or t >= best[0]):
                best = (t, off)
        if best is None:
            return Fraction(0)
        v = best[1].strip()
        return Fraction(v) if v else Fraction(0)

    def resolve(self, token, instant, depth=0):
        """H5 token resolution; returns station id or None."""
        tok = norm_token(token)
        if tok in self.station_net:
            return tok
        if depth >= 6:
            return None
        rows = self.xref.get(tok)
        if not rows:
            return None
        for vf, vt, target in rows:
            f = iso_to_epoch(vf) if vf else None
            t = iso_to_epoch(vt) if vt else None
            if f is not None and f > instant:
                continue
            if t is not None and t <= instant:
                continue
            return self.resolve(target, instant, depth + 1)
        return None


def norm_token(tok):
    s = (str(tok)).strip().upper()
    if not s:
        return s
    if s.isdigit() and len(s) < 8:
        s = s.rjust(8, '0')
    return s


def _load_xref(dbpath, ymlpath):
    rows = {}
    con = sqlite3.connect('file:%s?mode=ro' % dbpath, uri=True)
    try:
        for tok, target, vf, vt, kind in con.execute(
                'select token, target, valid_from, valid_to, kind from xref'):
            rows.setdefault((norm_token(tok), str(vf or '').strip()), []).append(
                (str(target or '').strip(), str(vt or '').strip() or None))
    finally:
        con.close()
    data = yaml_load(ymlpath) or {}
    for r in data.get('rows') or []:
        tok = norm_token(r.get('token'))
        vf = str(r.get('valid_from') or '').strip()
        target = str(r.get('target') or '').strip()
        vt = r.get('valid_to')
        vt = None if vt in (None, '', 'null', 'None') else str(vt).strip()
        rows[(tok, vf)] = [(target, vt)]
    out = {}
    for (tok, vf), targets in rows.items():
        out.setdefault(tok, []).extend((vf, vt, target) for target, vt in targets)
    return out


def _load_visits(dbpath, xmlpath, clock):
    con = sqlite3.connect('file:%s?mode=ro' % dbpath, uri=True)
    visits = {}
    try:
        for vid, stn, vdate, vtime, logger_ft, action, party in con.execute(
                'select vid, stn, vdate, vtime, logger_ft, action, party from visit'):
            visits[int(vid)] = {'vid': int(vid), 'stn': (stn or '').strip(),
                                'vdate': (vdate or '').strip(), 'vtime': (vtime or '').strip(),
                                'logger_ft': (logger_ft or '').strip(),
                                'action': (action or '').strip(), 'party': (party or '').strip(),
                                'refs': {}, 'void': False}
        for vid, method, reading, note in con.execute(
                'select vid, method, reading_ft, note from vref'):
            v = visits.get(int(vid))
            if v is not None:
                v['refs'][(method or '').strip().upper()] = (reading or '').strip()
    finally:
        con.close()
    root = ET.parse(xmlpath).getroot()
    amends = []
    for el in root:
        if not el.tag.lower().endswith('amend'):
            continue
        amends.append((int(el.get('no')), el))
    amends.sort(key=lambda x: x[0])
    for no, el in amends:
        vid = int(el.get('visit'))
        v = visits.get(vid)
        if v is None or v['void']:
            continue
        field = (el.get('field') or '').strip().lower()
        if field == 'void':
            v['void'] = True
        elif field == 'reference':
            meth = (el.get('method') or '').strip().upper()
            txt = (el.text or '').strip()
            if meth:
                v['refs'][meth] = txt
        elif field == 'action':
            v['action'] = (el.text or '').strip()
        elif field == 'time':
            txt = (el.text or '').strip().replace('T', ' ')
            parts = txt.split(' ')
            v['vdate'] = parts[0]
            v['vtime'] = parts[1].replace(':', '') if len(parts) > 1 else '0000'
        elif field == 'logger':
            v['logger_ft'] = (el.text or '').strip()
    for v in visits.values():
        v['instant'] = clock.lst_to_epoch(v['vdate'] + ' ' + _hhmm(v['vtime']))
        v['time_lst'] = v['vdate'] + ' ' + _hhmm(v['vtime'])
    return visits


def _hhmm(s):
    s = (s or '').strip().replace(':', '')
    if len(s) < 4:
        s = s.rjust(4, '0')
    return s[:2] + ':' + s[2:4]


def _load_measurements(csvpath, xmlpath):
    out = {}
    with open(csvpath, encoding='utf-8') as fh:
        for row in _csv_rows(fh):
            no = int(row['meas_no'])
            out[no] = {'meas_no': no, 'station': (row['station'] or '').strip(),
                       'start': (row['start'] or '').strip(), 'end': (row['end'] or '').strip(),
                       'q': Fraction((row['q_cfs'] or '0').strip()),
                       'grade': (row['grade'] or '').strip().upper(),
                       'cover': (row['cover'] or '').strip(),
                       'field_gh': (row['field_gh_ft'] or '').strip(),
                       'entered': (row['entered_utc'] or '').strip()}
    root = ET.parse(xmlpath).getroot()
    for el in root:
        if not el.tag.lower().endswith('measurement'):
            continue
        no = int(el.get('no'))

        def txt(tag):
            c = el.find(tag)
            return (c.text or '').strip() if c is not None else ''
        st = txt('station')
        start = txt('start').replace('T', ' ')
        end = txt('end').replace('T', ' ')
        qel = el.find('q')
        unit = (qel.get('unit') or '').strip().lower() if qel is not None else 'cms'
        qv = Fraction(txt('q'))
        if unit in ('cms', 'm3/s'):
            q = qv / Fraction('0.028316846592')
        else:
            q = qv
        rec = {'meas_no': no, 'station': st, 'start': start, 'end': end, 'q': q,
               'grade': txt('grade').upper(), 'cover': txt('cover'),
               'field_gh': txt('field_gh_ft'), 'entered': txt('entered')}
        prev = out.get(no)
        if prev is None:
            out[no] = rec
        else:
            def ep(s):
                return iso_to_epoch(s.replace(' ', 'T')) if 'T' in s else naive_to_epoch(s)
            if ep(rec['entered']) >= ep(prev['entered']):
                out[no] = rec
    return out


def _load_pub_daily(path):
    out = {}
    with open(path, encoding='utf-8') as fh:
        for row in _csv_rows(fh):
            sid = (row['site'] or '').strip()
            date = (row['date'] or '').strip()
            v = (row['q_mean_cfs'] or '').strip()
            out[(sid, date)] = (Fraction(v) if v else None, (row['codes'] or '').strip())
    return out


def _load_shift_pub(path):
    out = []
    with open(path, encoding='utf-8') as fh:
        for row in _csv_rows(fh):
            out.append({'meas_no': int(row['meas_no']), 'site': (row['site'] or '').strip(),
                        'decision': (row['decision'] or '').strip(),
                        'shift': (row['shift_ft'] or '').strip(),
                        'deviation': (row['deviation_pct'] or '').strip()})
    out.sort(key=lambda r: r['meas_no'])
    return out


def _load_dashboard(path):
    out = {}
    with open(path, encoding='utf-8') as fh:
        for row in _csv_rows(fh, '\t'):
            sid = (row['station'] or '').strip()
            date = (row['date'] or '').strip()
            v = (row['daily_cfs'] or '').strip()
            out[(sid, date)] = (Fraction(v) if v else None, (row['ice_flag'] or '').strip())
    return out


def _load_cache(path):
    out = []
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            o = json.loads(line, parse_float=Decimal)
            out.append(o)
    return out

# ---------------------------------------------------------------- rating


class Rating(object):
    def __init__(self, rating_id, points):
        # points: list of (gh Fraction, q Fraction, offset Fraction) ascending gh
        self.id = rating_id
        self.points = points

    def eval(self, h):
        """R(h) rounded to 4 significant figures (Fraction)."""
        return round_sig(self.eval_exact(h), 4)

    def eval_exact(self, h):
        """binary64 evaluation of R(h) as an exact Fraction of the float result."""
        pts = self.points
        if not pts:
            return Fraction(0)
        for gh, q, e in pts:
            if h == gh:
                return Fraction(q)
        n = len(pts)
        if h < pts[0][0]:
            i = 0
            if h <= pts[0][2]:
                return Fraction(0)
        elif h >= pts[n - 1][0]:
            i = n - 2
        else:
            i = 0
            for k in range(n - 1):
                if pts[k][0] <= h < pts[k + 1][0]:
                    i = k
                    break
        gh1, q1, e1 = pts[i]
        gh2, q2, _ = pts[i + 1]
        if gh1 == gh2:
            return Fraction(q1)
        beta = math.log(q2 / q1) / math.log((gh2 - e1) / (gh1 - e1))
        val = q1 * ((h - e1) / (gh1 - e1)) ** beta
        return Fraction(val)

    def inverse(self, q):
        """R^-1(Q) rounded to 2 decimals (Fraction)."""
        return round_dec(self.inverse_exact(q), 2)

    def inverse_exact(self, q):
        pts = self.points
        if not pts:
            return Fraction(0)
        for gh, qq, e in pts:
            if q == qq:
                return Fraction(gh)
        n = len(pts)
        if q < pts[0][1]:
            i = 0
        elif q >= pts[n - 1][1]:
            i = n - 2
        else:
            i = 0
            for k in range(n - 1):
                if pts[k][1] <= q < pts[k + 1][1]:
                    i = k
                    break
        gh1, q1, e1 = pts[i]
        gh2, q2, _ = pts[i + 1]
        if q1 <= 0 or q2 == q1:
            return Fraction(gh1)
        beta = math.log(q2 / q1) / math.log((gh2 - e1) / (gh1 - e1))
        if q <= 0:
            return Fraction(e1)
        val = e1 + (gh1 - e1) * (q / q1) ** (1.0 / beta)
        return Fraction(val)



def _in_force(tbl):
    return (tbl.get('status') or '').strip().upper() == 'IN FORCE'


def table_by_title(minutes, expected_id, title_key):
    """Find the IN FORCE table for a role: prefer the handbook's id, else by title."""
    cands = [t for t in minutes.values()
             if _in_force(t) and title_key in (t.get('title') or '').lower()]
    if not cands:
        return None
    for t in cands:
        if t['id'] == expected_id:
            return t
    return cands[0]


def table_cols(tbl):
    """Map header name -> column index for a minutes table."""
    out = {}
    hdr = (tbl.get('header') or [])
    for i, h in enumerate(hdr):
        name = (h or '').strip().lower()
        if name and name not in out:
            out[name] = i
    return out


def cell(row, cols, name, default=''):
    i = cols.get(name)
    if i is None or i >= len(row):
        return default
    return (row[i] or '').strip()


def build_ratings(reg):
    """Read the rating and index sheets, apply errata; return {rating_id: (site, effective, Rating)}.
    Only ACTIVE versions of in-scope sites are kept."""
    errata_rows = []
    tbl = table_by_title(reg.minutes, 'R-2', 'rating errata')
    if tbl is not None:
        cols = table_cols(tbl)
        for r in tbl['rows']:
            rid = cell(r, cols, 'rating_id')
            gh = cell(r, cols, 'gh_ft')
            q = cell(r, cols, 'q_cfs')
            was = cell(r, cols, 'was_q_cfs')
            if rid and gh:
                try:
                    errata_rows.append((rid, Fraction(gh), Fraction(q), Fraction(was)))
                except Exception:
                    pass

    # index sheet
    versions = []
    rows = reg.sheets.get(reg.index_sheet) or []
    header = None
    for r in rows:
        vals = [v for v in r if v not in (None, '')]
        if len(vals) < 2:
            continue
        if header is None:
            header = [(v or '').strip() for v in r]
            continue
        d = {}
        for i, h in enumerate(header):
            d[h] = (r[i] or '').strip() if i < len(r) else ''
        status = (d.get('status') or '').strip().upper()
        if status != 'ACTIVE':
            continue
        rid = d.get('rating_id') or ''
        site = d.get('site') or ''
        if site not in set(reg.sites):
            continue
        serial = d.get('effective_date') or ''
        etime = d.get('effective_time') or ''
        if etime and ':' not in etime and len(etime) >= 4:
            etime = etime[:2] + ':' + etime[2:4]
        date = serial_to_date(Fraction(serial), reg.date1904)
        eff = reg.clock.lst_to_epoch('%s %s' % (date.isoformat(), (etime or '00:00')))
        versions.append((site, eff, rid))
    versions.sort()

    # rating sheet points
    pts = {}
    rows = reg.sheets.get(reg.rating_sheet) or []
    header = None
    for r in rows:
        vals = [v for v in r if v not in (None, '')]
        if len(vals) < 2:
            continue
        if header is None:
            header = [(v or '').strip() for v in r]
            continue
        d = {}
        for i, h in enumerate(header):
            d[h] = (r[i] or '').strip() if i < len(r) else ''
        rid = d.get('rating_id') or ''
        gh = _clean_num(d.get('gh_ft'))
        q = _clean_num(d.get('q_cfs'))
        off = _clean_num(d.get('offset_ft'))
        if not rid or gh is None:
            continue
        pts.setdefault(rid, []).append((Fraction(gh), Fraction(q) if q is not None else Fraction(0),
                                        Fraction(off) if off is not None else Fraction(0)))

    ratings = {}
    errata_applied = []
    for site, eff, rid in versions:
        plist = sorted(pts.get(rid) or [])
        applied = []
        for (erid, egh, eq, ewas) in errata_rows:
            if erid != rid:
                continue
            for idx, (gh, q, off) in enumerate(plist):
                if gh == egh:
                    plist[idx] = (gh, eq, off)
                    applied.append((gh, ewas, eq))
                    break
        applied.sort(key=lambda x: x[0])
        errata_applied.extend((rid, x) for x in applied)
        ratings[rid] = {'site': site, 'eff': eff, 'rating': Rating(rid, plist), 'errata': applied}
    return ratings, errata_rows


def _clean_num(text):
    s = (str(text) if text is not None else '').strip()
    if s == '':
        return None
    try:
        Fraction(s)
    except Exception:
        return None
    return s


# ---------------------------------------------------------------- correction curve


class Correction(object):
    """c(t) from used visits of one site."""

    def __init__(self, knots):
        # knots: list of (t, a, b) sorted by t; segment [t_i, t_i+1) goes a_i -> b_i+1
        self.knots = knots

    def at(self, t):
        ks = self.knots
        if not ks:
            return Fraction(0)
        if t < ks[0][0]:
            return Fraction(0)
        for i in range(len(ks) - 1):
            t0 = ks[i][0]
            a = ks[i][1]
            t1, b, _ = ks[i + 1]
            if t0 <= t < t1:
                if t1 == t0:
                    return a
                return a + (b - a) * Fraction(t - t0, t1 - t0)
        return ks[-1][1]


def build_corrections(reg):
    """Return {site: Correction} plus the visit records used."""
    v1 = table_by_title(reg.minutes, 'V-1', 'disregard')
    disregard = set()
    if v1 is not None:
        cols = table_cols(v1)
        for r in v1['rows']:
            vid = cell(r, cols, 'visit_id')
            if vid:
                try:
                    disregard.add(int(vid))
                except ValueError:
                    pass
    out = {}
    visit_rows = []
    for vid in sorted(reg.visits):
        v = reg.visits[vid]
        site = reg.resolve(v['stn'], v['instant'])
        if site is None or site not in set(reg.sites):
            continue
        ref = None
        method = ''
        for m in ('TAPE', 'WIRE', 'STAFF'):
            if m in v['refs']:
                ref = v['refs'][m]
                method = m
                break
        tol = reg.drift_tol(site)
        logger = v['logger_ft'].strip()
        refv = Fraction(ref) if ref not in (None, '') else None
        logv = Fraction(logger) if logger not in (None, '') else None
        if refv is not None and logv is not None:
            err = refv - logv
        else:
            err = None
        applied = None
        if err is not None:
            applied = err if abs(err) >= tol else Fraction(0)
        action = (v['action'] or '').strip().upper()
        if vid in disregard:
            status = 'DISREGARDED'
        elif v['void']:
            status = 'VOID'
        else:
            status = 'USED'
        row = {'site': site, 'visit_id': vid, 'time_lst': v['time_lst'], 'method': method,
               'reference': refv, 'logger': logv, 'error': err,
               'applied': applied if status == 'USED' else None,
               'action': 'RESET' if action == 'RESET' else 'NONE', 'status': status,
               'instant': v['instant'], 'refs': v['refs']}
        visit_rows.append(row)
    visit_rows.sort(key=lambda r: (r['site'], r['instant'], r['visit_id']))
    for site in reg.sites:
        used = [r for r in visit_rows if r['site'] == site and r['status'] == 'USED']
        used.sort(key=lambda r: (r['instant'], r['visit_id']))
        knots = []
        for r in used:
            a = Fraction(0) if r['action'] == 'RESET' else (r['applied'] or Fraction(0))
            knots.append((r['instant'], a, r['applied'] if r['applied'] is not None else Fraction(0)))
        out[site] = Correction(knots)
    return out, visit_rows


# ---------------------------------------------------------------- shift curve


class ShiftCurve(object):
    def __init__(self, points):
        # points: list of (t, shift Fraction, source)
        self.points = points

    def at(self, t):
        pts = self.points
        if not pts:
            return Fraction(0)
        if t <= pts[0][0]:
            return pts[0][1]
        for i in range(len(pts) - 1):
            t0, s0, _ = pts[i]
            t1, s1, _ = pts[i + 1]
            if t0 <= t < t1:
                if t1 == t0:
                    return s0
                return round_dec(s0 + (s1 - s0) * Fraction(t - t0, t1 - t0), 2)
        return pts[-1][1]

# ---------------------------------------------------------------- compute


def _parse_meas_time(s, clock):
    s = str(s).strip().replace('T', ' ')
    if re.search(r'[+-]\d{2}:?\d{2}$', s) or s.rstrip().endswith('Z'):
        return iso_to_epoch(s)
    return clock.lst_to_epoch(s)


class Compute(object):
    def __init__(self, reg):
        self.reg = reg
        self.clock = reg.clock
        self.sites = reg.sites
        self.site_set = set(reg.sites)
        self.p0 = reg.clock.lst_to_epoch(reg.period_start + ' 00:00')
        self.p1 = reg.clock.lst_to_epoch(reg.period_end + ' 00:00')
        self.window_start = self.p0 - reg.record_margin_hours * 3600
        self.window_end = self.p1 + reg.record_margin_hours * 3600
        self.ratings, self.errata_rows = build_ratings(reg)
        self.versions = {}
        for rid, v in self.ratings.items():
            self.versions.setdefault(v['site'], []).append((v['eff'], rid))
        for s in self.versions:
            self.versions[s].sort()
        self.corrections, self.visit_rows = build_corrections(reg)
        self.counters = dict.fromkeys(
            ['files_read', 'records_read', 'unknown_site', 'out_of_scope', 'unrouted',
             'out_of_window', 'admitted', 'superseded', 'duplicates', 'voided',
             'edits_applied', 'edits_ignored', 'edit_deleted', 'sensor_fault',
             'backup_unused', 'kept'], 0)
        self.lineage = []
        self.aliases = {}
        self.pool = {}
        self.exclusions = []
        self.amendments = []
        self.unit_rows = []
        self.daily = {}

    def version_at(self, site, t):
        best = None
        for eff, rid in (self.versions.get(site) or []):
            if eff <= t:
                best = rid
            else:
                break
        if best is None:
            items = self.versions.get(site) or []
            if items:
                best = items[0][1]
        return best

    # ------------------------------------------------------------
    def ingest(self):
        reg = self.reg
        routes = {}
        for r in reg.catalog.get('routes') or []:
            if str(r.get('status') or '').upper() != 'ACTIVE':
                continue
            routes.setdefault((r['file'], r['site'], r['sensor']), []).append(
                (iso_to_epoch(r['from_utc']), iso_to_epoch(r['to_utc'])))
        layouts = {}
        for f in reg.catalog.get('files') or []:
            layouts[f['file']] = f['layout']
        order = 0
        for name in reg.catalog.get('file_order') or []:
            path = os.path.join(reg.dir, name)
            if not os.path.exists(path):
                continue
            lay = layouts.get(name)
            if lay is None:
                continue
            st = dict.fromkeys(['records', 'unknown_site', 'out_of_scope', 'unrouted',
                                'out_of_window', 'admitted'], 0)
            for rec in read_shard(path, lay, self.clock):
                st['records'] += 1
                instant = rec['instant']
                site = reg.resolve(rec['token'], instant)
                if site is None:
                    st['unknown_site'] += 1
                    continue
                if site not in self.site_set:
                    st['out_of_scope'] += 1
                    continue
                tok = norm_token(rec['token'])
                if tok != site:
                    self.aliases[(tok, site)] = self.aliases.get((tok, site), 0) + 1
                ok = False
                for a, b in routes.get((name, site, rec['sensor']), []):
                    if a <= instant < b:
                        ok = True
                        break
                if not ok:
                    st['unrouted'] += 1
                    continue
                if not (self.window_start <= instant < self.window_end):
                    st['out_of_window'] += 1
                    continue
                st['admitted'] += 1
                rec['file'] = name
                rec['order'] = order
                rec['sensor'] = (str(rec['sensor']).strip().upper() or 'P')
                rec['qual'] = str(rec['qual']).strip().upper() or 'G'
                self.pool.setdefault((site, rec['sensor'], instant), []).append(rec)
            self.lineage.append({'file': name, 'layout': lay,
                                 'records': st['records'], 'unknown_site': st['unknown_site'],
                                 'out_of_scope': st['out_of_scope'], 'unrouted': st['unrouted'],
                                 'out_of_window': st['out_of_window'], 'admitted': st['admitted']})
            order += 1
        self.counters['records_read'] = sum(l['records'] for l in self.lineage)
        self.counters['files_read'] = len(self.lineage)
        self.counters['unknown_site'] = sum(l['unknown_site'] for l in self.lineage)
        self.counters['out_of_scope'] = sum(l['out_of_scope'] for l in self.lineage)
        self.counters['unrouted'] = sum(l['unrouted'] for l in self.lineage)
        self.counters['out_of_window'] = sum(l['out_of_window'] for l in self.lineage)
        self.counters['admitted'] = sum(l['admitted'] for l in self.lineage)

    # ------------------------------------------------------------
    def dedup(self):
        self.winners = {}
        sup = dup = voided = 0
        for key, recs in self.pool.items():
            best = recs[0]
            for r in recs[1:]:
                if r['rev'] > best['rev'] or (r['rev'] == best['rev'] and r['order'] > best['order']):
                    best = r
            for r in recs:
                if r is best:
                    continue
                if r['rev'] < best['rev']:
                    sup += 1
                else:
                    dup += 1
            self.winners[key] = best
            if best['void']:
                voided += 1
        self.counters['superseded'] = sup
        self.counters['duplicates'] = dup
        self.counters['voided'] = voided

    # ------------------------------------------------------------
    def apply_edits(self):
        reg = self.reg
        edits = sorted(reg.edits, key=lambda e: int(e['seq']))
        live = {}
        for key, rec in self.winners.items():
            if not rec['void']:
                live[key] = dict(rec)
        deleted = {}
        for e in edits:
            sensor = str(e.get('sensor') or 'P')
            t = self.clock.lst_to_epoch(str(e.get('time_lst') or '').strip().replace('T', ' '))
            site = reg.resolve(e.get('station'), t)
            if site is None or site not in self.site_set:
                continue
            op = str(e.get('op') or '').strip().upper()
            key = (site, sensor, t)
            status = 'IGNORED'
            if op == 'SET':
                if key in live:
                    live[key]['value'] = str(e.get('value'))
                    live[key]['unit'] = str(e.get('unit') or '').strip().lower() or None
                    live[key]['qual'] = 'G'
                    status = 'APPLIED'
            elif op == 'DELETE':
                if key in live:
                    deleted[key] = dict(live[key])
                    del live[key]
                    status = 'APPLIED'
            elif op == 'RESTORE':
                if key in deleted:
                    live[key] = deleted.pop(key)
                    status = 'APPLIED'
            self.amendments.append({'seq': int(e['seq']), 'site': site, 'sensor': sensor,
                                   'time_lst': self.clock.epoch_to_lst(t), 'op': op,
                                   'status': status})
            if status == 'APPLIED':
                self.counters['edits_applied'] += 1
            else:
                self.counters['edits_ignored'] += 1
        self.counters['edit_deleted'] = len(deleted)
        self.live = live

    # ------------------------------------------------------------
    def select(self):
        self.selected = {}
        self.fault_keys = set()
        for key in sorted(self.live):
            site, sensor, t = key
            rec = self.live[key]
            if rec['qual'] == 'X':
                self.counters['sensor_fault'] += 1
                self.fault_keys.add(key)
                self.exclusions.append({'site': site, 'sensor': sensor, 'instant': t,
                                        'reason': 'SENSOR_FAULT', 'file': rec['file']})
                continue
            self.selected[key] = rec
        by_instant = {}
        for (site, sensor, t) in self.selected:
            by_instant.setdefault((site, t), []).append(sensor)
        for (site, t) in list(by_instant):
            sensors = by_instant[(site, t)]
            if 'P' in sensors and 'B' in sensors:
                rec = self.selected.pop((site, 'B', t))
                self.counters['backup_unused'] += 1
                self.exclusions.append({'site': site, 'sensor': 'B', 'instant': t,
                                        'reason': 'BACKUP_UNUSED', 'file': rec['file']})
        for key, rec in self.winners.items():
            if rec['void']:
                self.exclusions.append({'site': key[0], 'sensor': key[1], 'instant': key[2],
                                        'reason': 'VOIDED', 'file': rec['file']})
            elif key not in self.live:
                self.exclusions.append({'site': key[0], 'sensor': key[1], 'instant': key[2],
                                        'reason': 'EDIT_DELETED', 'file': rec['file']})
        self.counters['kept'] = len(self.selected)

    # ------------------------------------------------------------
    def gage_heights(self):
        reg = self.reg
        self.gh = {}
        for key in self.selected:
            site, sensor, t = key
            rec = self.selected[key]
            unit = str(rec.get('unit') or '').strip().lower()
            if unit == '':
                unit = str(reg.eq_unit(site, sensor, t) or 'ft').lower()
            try:
                val = Fraction(str(rec['value']).strip())
            except Exception:
                continue
            if unit in ('ft', 'feet'):
                feet = val
            elif unit == 'm':
                feet = val * Fraction(10000, 3048)
            elif unit == 'cm':
                feet = val * Fraction(100, 3048)
            elif unit == 'mm':
                feet = val * Fraction(10, 3048)
            else:
                feet = val
            off = reg.offset(site, sensor, t)
            corr = self.corrections[site].at(t)
            self.gh[key] = round_dec(feet + off + corr, 2)

    # ------------------------------------------------------------
    def build_ice(self):
        reg = self.reg
        events = {}
        order = []
        for o in sorted(reg.ice_obs, key=lambda x: int(x['entry'])):
            kind = str(o.get('kind') or '').strip().upper()
            entry = int(o['entry'])
            if kind in ('ON', 'OFF'):
                t = self.clock.lst_to_epoch(str(o.get('at_lst') or '').strip().replace('T', ' '))
                site = reg.resolve(o.get('station'), t)
                events[entry] = {'entry': entry, 'kind': kind, 'site': site, 't': t}
                order.append(entry)
            elif kind == 'AMEND':
                tgt = events.get(int(o.get('target')))
                if tgt is None:
                    continue
                tgt['t'] = self.clock.lst_to_epoch(str(o.get('at_lst') or '').strip().replace('T', ' '))
            elif kind == 'WITHDRAW':
                tgt = int(o.get('target'))
                if tgt in events:
                    if tgt in order:
                        order.remove(tgt)
                    events.pop(tgt, None)
        per_site = {}
        for entry in order:
            ev = events.get(entry)
            if ev is None or ev['site'] is None or ev['site'] not in self.site_set:
                continue
            per_site.setdefault(ev['site'], []).append(ev)
        periods = {}
        for site, evs in per_site.items():
            evs.sort(key=lambda e: (e['t'], e['entry']))
            open_ev = None
            out = []
            for e in evs:
                if e['kind'] == 'ON':
                    if open_ev is None:
                        open_ev = e
                elif open_ev is not None:
                    out.append({'on': open_ev, 'off': e})
                    open_ev = None
            if open_ev is not None:
                out.append({'on': open_ev, 'off': None})
            periods[site] = out
        self.ice_periods = periods

    def ice_at(self, site, t):
        for p in self.ice_periods.get(site, []):
            a = p['on']['t']
            b = p['off']['t'] if p['off'] else None
            if a <= t and (b is None or t < b):
                return p
        return None

    # ------------------------------------------------------------
    def evaluate_measurements(self):
        reg = self.reg
        m1 = table_by_title(reg.minutes, 'M-1', 'measurement review')
        verdicts = {}
        if m1 is not None:
            cols = table_cols(m1)
            for r in m1['rows']:
                no = cell(r, cols, 'meas_no')
                if no:
                    try:
                        no = int(no)
                    except ValueError:
                        continue
                    verdicts[no] = (cell(r, cols, 'verdict').upper(),
                                    cell(r, cols, 'grade').upper())
        t2 = table_by_title(reg.minutes, 'T-2', 'grade tolerance')
        tol = {}
        tol_text = {}
        if t2 is not None:
            cols = table_cols(t2)
            for r in t2['rows']:
                g = cell(r, cols, 'grade')
                if g:
                    v = cell(r, cols, 'tolerance_pct')
                    key = g.upper()
                    if v in ('', 'n/a'):
                        tol[key] = None
                        tol_text[key] = None
                    else:
                        try:
                            tol[key] = Fraction(v)
                            tol_text[key] = v
                        except Exception:
                            tol[key] = None
                            tol_text[key] = None
        self.tolerance_table = t2
        self.tolerances = tol
        self.tolerances_text = tol_text
        w1 = table_by_title(reg.minutes, 'W-1', 'winter coefficient')
        self.winter_table = w1
        self.winter = {}
        self.winter_text = {}
        if w1 is not None:
            cols = table_cols(w1)
            for r in w1['rows']:
                stn = cell(r, cols, 'station')
                dk = cell(r, cols, 'default_k')
                if stn and dk:
                    self.winter_text[stn] = dk
                    try:
                        self.winter[stn] = Fraction(dk)
                    except Exception:
                        pass

        meas = []
        for no in sorted(reg.measurements):
            m = reg.measurements[no]
            start = _parse_meas_time(m['start'], self.clock)
            end = _parse_meas_time(m['end'], self.clock)
            instant = start + (end - start) // 2
            instant = (instant // MIN) * MIN
            site = reg.resolve(m['station'], instant)
            if site is None or site not in self.site_set:
                continue
            meas.append({'no': no, 'site': site, 'start': start, 'end': end,
                         'instant': instant, 'q': m['q'], 'cover': m['cover'],
                         'raw_grade': m['grade']})
        meas.sort(key=lambda x: (x['site'], x['instant'], x['no']))

        curves = {}
        for site in self.sites:
            for eff, rid in self.versions.get(site, []):
                curves[rid] = [(eff, Fraction(0), 'START')]
        last_shift = {}
        rows = []
        for m in meas:
            v = verdicts.get(m['no'])
            verdict = v[0] if v else 'ACCEPT'
            grade = v[1] if (v and v[0] == 'REGRADE') else m['raw_grade']
            row = {'meas_no': m['no'], 'site': m['site'], 'instant': m['instant'],
                   'grade': grade, 'verdict': verdict, 'cover': m['cover'],
                   'gh': None, 'rating_id': '', 'shift_in_use': None, 'rated': None,
                   'measured': m['q'], 'deviation': None, 'tolerance': None,
                   'decision': '', 'shift': None, 'k': None}
            ghs = [self.gh[k] for k in self.gh
                   if k[0] == m['site'] and m['start'] <= k[2] <= m['end']]
            if ghs:
                row['gh'] = round_dec(sum(ghs) / len(ghs), 2)
            if verdict == 'REJECT':
                row['decision'] = 'REJECTED'
                rows.append(row)
                continue
            if not ghs:
                row['decision'] = 'NO_RECORD'
                rows.append(row)
                continue
            rid = self.version_at(m['site'], m['instant'])
            row['rating_id'] = rid
            rating = self.ratings[rid]['rating']
            ip = self.ice_at(m['site'], m['instant'])
            if ip is not None:
                s = ShiftCurve(curves[rid]).at(m['instant'])
                row['shift_in_use'] = s
                rated = rating.eval(row['gh'] + s)
                row['rated'] = rated
                if rated != 0:
                    row['k'] = round_dec(m['q'] / rated, 3)
                row['decision'] = 'ICE'
            else:
                s = last_shift.get(rid, Fraction(0))
                row['shift_in_use'] = s
                rated = rating.eval(row['gh'] + s)
                row['rated'] = rated
                dev = (m['q'] - rated) / rated * 100 if rated != 0 else Fraction(0)
                row['deviation'] = round_dec(dev, 1)
                t = tol.get(grade)
                if t is not None:
                    row['tolerance'] = round_dec(t, 1)
                if t is not None and abs(row['deviation']) > t:
                    row['decision'] = 'SHIFT'
                    row['shift'] = round_dec(rating.inverse(m['q']) - row['gh'], 2)
                    curves[rid].append((m['instant'], row['shift'], str(m['no'])))
                    last_shift[rid] = row['shift']
                else:
                    row['decision'] = 'CHECK'
            rows.append(row)
        self.meas_rows = rows
        self.curves = curves
        # ICE measurements use the completed curve of their version (H12)
        for row in rows:
            if row['decision'] != 'ICE':
                continue
            rid = row['rating_id']
            rating = self.ratings[rid]['rating']
            s = ShiftCurve(curves.get(rid) or [(0, Fraction(0), 'START')]).at(row['instant'])
            row['shift_in_use'] = s
            rated = rating.eval(row['gh'] + s)
            row['rated'] = rated
            if rated != 0:
                row['k'] = round_dec(row['measured'] / rated, 3)

    # ------------------------------------------------------------
    def build_kpoints(self):
        self.kpoints = {}
        for row in self.meas_rows:
            if row['decision'] != 'ICE':
                continue
            p = self.ice_at(row['site'], row['instant'])
            if p is None:
                continue
            self.kpoints.setdefault(id(p), []).append((row['instant'], row['k'], row['meas_no']))
        for k in self.kpoints:
            self.kpoints[k].sort()

    def k_at(self, site, period, t):
        kps = self.kpoints.get(id(period), [])
        if not kps:
            return self.winter.get(site)
        if t <= kps[0][0]:
            return kps[0][1]
        for i in range(len(kps) - 1):
            t0, k0, _ = kps[i]
            t1, k1, _ = kps[i + 1]
            if t0 <= t < t1:
                return round_dec(k0 + (k1 - k0) * Fraction(t - t0, t1 - t0), 3)
        return kps[-1][1]

    # ------------------------------------------------------------
    def build_unit_values(self):
        rows = []
        for key in sorted(self.selected):
            site, sensor, t = key
            gh = self.gh.get(key)
            if gh is None:
                continue
            rid = self.version_at(site, t)
            rating = self.ratings[rid]['rating']
            shift = ShiftCurve(self.curves.get(rid) or [(0, Fraction(0), 'START')]).at(t)
            gh_eff = gh + shift
            q_open = rating.eval(gh_eff)
            flags = ''
            if sensor == 'B':
                flags += 'B'
            ip = self.ice_at(site, t)
            if ip is not None:
                flags += 'I'
            if rating.points and gh_eff > rating.points[-1][0]:
                flags += '>'
            if ip is not None:
                kk = self.k_at(site, ip, t)
                q = round_sig(kk * q_open, 4) if kk is not None else q_open
            else:
                kk = None
                q = q_open
            rows.append({'site': site, 'instant': t, 'time_lst': self.clock.epoch_to_lst(t),
                         'sensor': sensor, 'gh': gh, 'shift': shift, 'gh_eff': gh_eff,
                         'q_open': q_open, 'k': kk, 'q': q, 'flags': flags})
        rows.sort(key=lambda r: (r['site'], r['instant']))
        self.unit_rows = rows

    # ------------------------------------------------------------
    def build_daily(self):
        reg = self.reg
        d0 = datetime.date(*[int(x) for x in reg.period_start.split('-')])
        d1 = datetime.date(*[int(x) for x in reg.period_end.split('-')])
        days = []
        cur = d0
        while cur < d1:
            days.append(cur.isoformat())
            cur += datetime.timedelta(days=1)
        self.period_days = days
        self.daily = {}
        mincov = reg.min_coverage * Fraction(DAY)
        for site in self.sites:
            recs = [r for r in self.unit_rows if r['site'] == site]
            recs.sort(key=lambda r: r['instant'])
            gap = reg.max_gap(site) * MIN
            ts = [r['instant'] for r in recs]
            qs = [r['q'] for r in recs]
            segs = [(ts[i], ts[i + 1], qs[i], qs[i + 1])
                    for i in range(len(recs) - 1) if ts[i + 1] - ts[i] <= gap]
            for day in days:
                a = self.clock.lst_to_epoch(day + ' 00:00')
                b = a + DAY
                cov = Fraction(0)
                integral = Fraction(0)
                for (t0, t1, q0, q1) in segs:
                    lo = max(t0, a)
                    hi = min(t1, b)
                    if hi <= lo:
                        continue
                    qa = q0 + (q1 - q0) * Fraction(lo - t0, t1 - t0)
                    qb = q0 + (q1 - q0) * Fraction(hi - t0, t1 - t0)
                    integral += (qa + qb) * Fraction(hi - lo, 2)
                    cov += Fraction(hi - lo)
                dayrecs = [r for r in recs if a <= r['instant'] < b]
                codes = []
                value = integral / cov if cov > 0 and cov >= mincov else None
                if value is None:
                    codes.append('INC')
                if any('I' in r['flags'] for r in dayrecs):
                    codes.append('ICE')
                if any('B' in r['flags'] for r in dayrecs):
                    codes.append('B')
                if any('>' in r['flags'] for r in dayrecs):
                    codes.append('>')
                self.daily[(site, day)] = {
                    'value': value, 'rounded': discharge_round(value) if value is not None else None,
                    'coverage': cov, 'n_readings': len(dayrecs), 'codes': codes}

    def run(self):
        self.ingest()
        self.dedup()
        self.apply_edits()
        self.select()
        self.gage_heights()
        self.build_ice()
        self.evaluate_measurements()
        self.build_kpoints()
        self.build_unit_values()
        self.build_daily()

# ---------------------------------------------------------------- output


class J(object):
    """Preformatted JSON number."""
    def __init__(self, text):
        self.text = text


def _jnum(v):
    if isinstance(v, J):
        return v.text
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if v is None:
        return 'null'
    if isinstance(v, int):
        return str(v)
    if isinstance(v, Decimal):
        return format(v, 'f')
    if isinstance(v, Fraction):
        out = _plain_decimal(v)
        return out if out is not None else format(Decimal(v.numerator) / Decimal(v.denominator), 'f')
    if isinstance(v, float):
        return repr(v)
    raise TypeError(repr(v))


def jdump(obj, indent=0, pretty=True):
    if pretty:
        pad = '  ' * indent
    else:
        pad = ''
    if isinstance(obj, dict):
        if not obj:
            return '{}'
        items = []
        for k, v in obj.items():
            if pretty:
                items.append('%s  %s: %s' % (pad, _jstr(k), jdump(v, indent + 1, True)))
            else:
                items.append('%s: %s' % (_jstr(k), jdump(v, 0, False)))
        if pretty:
            return '{\n' + ',\n'.join(items) + '\n' + pad + '}'
        return '{' + ', '.join(items) + '}'
    if isinstance(obj, (list, tuple)):
        if not obj:
            return '[]'
        items = []
        for v in obj:
            if pretty:
                items.append('%s  %s' % (pad, jdump(v, indent + 1, True)))
            else:
                items.append(jdump(v, 0, False))
        if pretty:
            return '[\n' + ',\n'.join(items) + '\n' + pad + ']'
        return '[' + ', '.join(items) + ']'
    if isinstance(obj, str):
        return _jstr(obj)
    return _jnum(obj)


def _jstr(s):
    out = []
    for ch in s:
        if ch == '"':
            out.append('\\"')
        elif ch == '\\':
            out.append('\\\\')
        elif ch == '\n':
            out.append('\\n')
        elif ch == '\r':
            out.append('\\r')
        elif ch == '\t':
            out.append('\\t')
        elif ord(ch) < 32:
            out.append('\\u%04x' % ord(ch))
        else:
            out.append(ch)
    return '"' + ''.join(out) + '"'


def write_text(path, text):
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text)


def xml_esc(s):
    return (str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            .replace('"', '&quot;'))


def render(c, outdir):
    reg = c.reg

    def put(name, text):
        write_text(os.path.join(outdir, name), text)

    # ---- unit_values.csv
    hdr = ['site', 'time_lst', 'sensor', 'gh_ft', 'shift_ft', 'gh_eff_ft',
           'q_open_cfs', 'k_factor', 'q_cfs', 'flags']
    rows = []
    for r in c.unit_rows:
        rows.append([r['site'], r['time_lst'], r['sensor'],
                     fmt_places(r['gh'], 2), fmt_places(r['shift'], 2),
                     fmt_places(r['gh_eff'], 2), fmt_rsig(r['q_open']),
                     fmt_places(r['k'], 3) if r['k'] is not None else '',
                     fmt_rsig(r['q']), r['flags']])
    put('unit_values.csv', _delim_text(hdr, rows, ','))

    # ---- gh_corrections.tsv
    hdr = ['site', 'from_lst', 'to_lst', 'start_ft', 'end_ft']
    rows = []
    for site in c.sites:
        ks = c.corrections[site].knots
        for i in range(len(ks)):
            t0, a, b = ks[i]
            if i + 1 < len(ks):
                t1 = ks[i + 1][0]
                end = ks[i + 1][2]
                to = c.clock.epoch_to_lst(t1)
            else:
                end = a
                to = ''
            rows.append([site, c.clock.epoch_to_lst(t0), to,
                         fmt_places(a, 2), fmt_places(end, 2)])
    put('gh_corrections.tsv', _delim_text(hdr, rows, '\t'))

    # ---- visit_errors.psv
    hdr = ['site', 'visit_id', 'time_lst', 'method', 'reference_ft', 'logger_ft',
           'error_ft', 'applied_ft', 'action', 'status']
    rows = []
    for v in c.visit_rows:
        rows.append([v['site'], v['visit_id'], v['time_lst'], v['method'],
                     fmt_places(v['reference'], 2) if v['reference'] is not None else '',
                     fmt_places(v['logger'], 2) if v['logger'] is not None else '',
                     fmt_places(v['error'], 2) if v['error'] is not None else '',
                     fmt_places(v['applied'], 2) if v['applied'] is not None else '',
                     v['action'], v['status']])
    put('visit_errors.psv', _delim_text(hdr, rows, '|'))

    # ---- measurement_eval.csv
    hdr = ['meas_no', 'site', 'instant_lst', 'grade', 'verdict', 'cover', 'gh_ft',
           'rating_id', 'shift_in_use_ft', 'rated_q_cfs', 'measured_q_cfs',
           'deviation_pct', 'tolerance_pct', 'decision', 'shift_ft', 'k_factor']
    rows = []
    for m in sorted(c.meas_rows, key=lambda x: x['meas_no']):
        rows.append([m['meas_no'], m['site'], c.clock.epoch_to_lst(m['instant']),
                     m['grade'], m['verdict'], m['cover'],
                     fmt_places(m['gh'], 2) if m['gh'] is not None else '',
                     m['rating_id'],
                     fmt_places(m['shift_in_use'], 2) if m['shift_in_use'] is not None else '',
                     fmt_rsig(m['rated']) if m['rated'] is not None else '',
                     fmt_places(m['measured'], 2),
                     fmt_places(m['deviation'], 1) if m['deviation'] is not None else '',
                     fmt_places(m['tolerance'], 1) if m['tolerance'] is not None else '',
                     m['decision'],
                     fmt_places(m['shift'], 2) if m['shift'] is not None else '',
                     fmt_places(m['k'], 3) if m['k'] is not None else ''])
    put('measurement_eval.csv', _delim_text(hdr, rows, ','))

    # ---- shift_curves.json
    curves = []
    items = []
    for rid, v in c.ratings.items():
        items.append((v['site'], v['eff'], rid))
    items.sort()
    for site, eff, rid in items:
        pts = c.curves.get(rid) or []
        curves.append({'site': site, 'rating_id': rid,
                       'effective_lst': c.clock.epoch_to_lst(eff),
                       'points': [{'time_lst': c.clock.epoch_to_lst(t),
                                   'shift_ft': J(fmt_places(s, 2)), 'source': src}
                                  for (t, s, src) in pts]})
    put('shift_curves.json', jdump({'curves': curves}) + '\n')

    # ---- ice_periods.jsonl
    uv_index = {}
    for r in c.unit_rows:
        uv_index[(r['site'], r['instant'])] = r
    per_site_instants = {}
    for r in c.unit_rows:
        per_site_instants.setdefault(r['site'], []).append(r['instant'])
    lines = []
    ip_all = []
    for site in c.sites:
        for p in c.ice_periods.get(site, []):
            ip_all.append((site, p['on']['t'], p))
    ip_all.sort(key=lambda x: (x[0], x[1]))
    for site, on_t, p in ip_all:
        kps = c.kpoints.get(id(p)) or []
        default_k = None
        if not kps:
            default_k = c.winter.get(site)
            if default_k is not None:
                default_k = J(_plain_decimal(default_k))
        off_t = p['off']['t'] if p['off'] else None
        n_uv = 0
        for t in per_site_instants.get(site, []):
            if t >= on_t and (off_t is None or t < off_t):
                n_uv += 1
        obj = {'site': site, 'on_lst': c.clock.epoch_to_lst(on_t),
               'off_lst': c.clock.epoch_to_lst(off_t) if off_t is not None else None,
               'on_entry': p['on']['entry'],
               'off_entry': p['off']['entry'] if p['off'] else None,
               'k_points': [{'meas_no': no, 'time_lst': c.clock.epoch_to_lst(t),
                             'k': J(fmt_places(k, 3))} for (t, k, no) in kps],
               'default_k': default_k,
               'unit_values': n_uv}
        lines.append(jdump(obj, pretty=False))
    put('ice_periods.jsonl', ('\n'.join(lines) + '\n') if lines else '')

    # ---- rating_tables_used.json
    ratings = []
    for site, eff, rid in items:
        v = c.ratings[rid]
        ratings.append({'rating_id': rid, 'site': site,
                        'effective_lst': c.clock.epoch_to_lst(eff),
                        'points': [_point_obj(p) for p in v['rating'].points],
                        'errata_applied': [{'gh_ft': J(_plain_decimal(g)),
                                            'from_q_cfs': J(_plain_decimal(w)),
                                            'to_q_cfs': J(_plain_decimal(q))}
                                           for (g, w, q) in v['errata']]})
    put('rating_tables_used.json', jdump({'ratings': ratings}) + '\n')

    # ---- daily_values.csv
    hdr = ['site', 'date', 'q_mean_cfs', 'coverage_h', 'n_readings', 'codes']
    rows = []
    for site in c.sites:
        for day in c.period_days:
            d = c.daily[(site, day)]
            rows.append([site, day,
                         discharge_fmt(d['value']) if d['value'] is not None else '',
                         fmt_places(d['coverage'] / 3600, 2),
                         d['n_readings'], ';'.join(d['codes'])])
    put('daily_values.csv', _delim_text(hdr, rows, ','))

    # ---- monthly_summary.xml
    months = _month_list(reg.period_start, reg.period_end)
    mrows = []
    for site in c.sites:
        for (ym, ndays) in months:
            days = [d for d in c.period_days if d[:7] == ym]
            vals = [c.daily[(site, d)]['rounded'] for d in days
                    if c.daily[(site, d)]['value'] is not None]
            complete_days = len(vals)
            complete = 'true' if complete_days == ndays else 'false'
            if vals:
                total = sum(vals)
                mean = discharge_round(total / len(vals))
                mn = min(vals)
                mx = max(vals)
                vol = round_dec(total * Fraction(DAY) / Fraction(43560), 1)
                area = reg.drainage_area(site)
                runoff = round_dec(vol * 12 / (area * 640), 2) if area else None
                mrows.append((site, ym, ndays, complete_days, mean, mn, mx, vol, runoff, complete))
            else:
                mrows.append((site, ym, ndays, complete_days, None, None, None, None, None, complete))
    buf = ['<?xml version="1.0" encoding="UTF-8"?>']
    buf.append('<monthly_summary network=%s period_start=%s period_end=%s>' % (
        _attr(reg.net), _attr(reg.period_start), _attr(reg.period_end)))
    for (site, ym, ndays, cd, mean, mn, mx, vol, runoff, complete) in mrows:
        buf.append('  <month site=%s month=%s days=%s complete_days=%s mean_cfs=%s min_cfs=%s '
                   'max_cfs=%s volume_af=%s runoff_in=%s complete=%s/>' % (
                       _attr(site), _attr(ym), _attr(ndays), _attr(cd),
                       _attr(discharge_fmt(mean)) if mean is not None else '""',
                       _attr(discharge_fmt(mn)) if mn is not None else '""',
                       _attr(discharge_fmt(mx)) if mx is not None else '""',
                       _attr(fmt_places(vol, 1)) if vol is not None else '""',
                       _attr(fmt_places(runoff, 2)) if runoff is not None else '""',
                       _attr(complete)))
    buf.append('</monthly_summary>')
    put('monthly_summary.xml', '\n'.join(buf) + '\n')

    # ---- period_statistics.json
    sites = []
    for site in c.sites:
        rows_uv = [r for r in c.unit_rows if r['site'] == site and c.p0 <= r['instant'] < c.p1]
        peak = None
        peak_t = None
        for r in rows_uv:
            if peak is None or r['q'] > peak:
                peak = r['q']
                peak_t = r['instant']
        days = c.period_days
        vals = []
        for i, d in enumerate(days):
            if c.daily[(site, d)]['value'] is not None:
                vals.append((i, c.daily[(site, d)]['rounded']))
        best7 = None
        for i in range(len(days) - 6):
            window = [v for (idx, v) in vals if i <= idx <= i + 6]
            if len(window) == 7:
                m = sum(window) / 7
                if best7 is None or m < best7[0]:
                    best7 = (m, i)
        allvals = [v for (_, v) in vals]
        inc_days = sum(1 for d in days if 'INC' in c.daily[(site, d)]['codes'])
        ice_days = sum(1 for d in days if 'ICE' in c.daily[(site, d)]['codes'])
        b_days = sum(1 for d in days if 'B' in c.daily[(site, d)]['codes'])
        a_days = sum(1 for d in days if '>' in c.daily[(site, d)]['codes'])
        n_shift = sum(1 for m in c.meas_rows if m['site'] == site and m['decision'] == 'SHIFT')
        n_ice = sum(1 for m in c.meas_rows if m['site'] == site and m['decision'] == 'ICE')
        obj = {'site': site,
               'peak_q_cfs': J(fmt_rsig(peak)) if peak is not None else None,
               'peak_time_lst': c.clock.epoch_to_lst(peak_t) if peak_t is not None else None,
               'min_7day_cfs': J(discharge_fmt(best7[0])) if best7 else None,
               'min_7day_start': days[best7[1]] if best7 else None,
               'mean_cfs': J(discharge_fmt(sum(allvals) / len(allvals))) if allvals else None,
               'complete_days': len(allvals), 'inc_days': inc_days, 'ice_days': ice_days,
               'backup_days': b_days, 'above_rating_days': a_days,
               'shift_points': n_shift, 'ice_measurements': n_ice}
        sites.append(obj)
    put('period_statistics.json', jdump({'sites': sites}) + '\n')

    # ---- alias_resolution.csv
    hdr = ['token', 'site', 'records']
    rows = [[t, s, c.aliases[(t, s)]] for (t, s) in sorted(c.aliases)]
    put('alias_resolution.csv', _delim_text(hdr, rows, ','))

    # ---- dedup_report.json
    order = ['files_read', 'records_read', 'unknown_site', 'out_of_scope', 'unrouted',
             'out_of_window', 'admitted', 'superseded', 'duplicates', 'voided',
             'edits_applied', 'edits_ignored', 'edit_deleted', 'sensor_fault',
             'backup_unused', 'kept']
    put('dedup_report.json', jdump({k: c.counters[k] for k in order}) + '\n')

    # ---- source_lineage.json
    put('source_lineage.json', jdump({'files': c.lineage}) + '\n')

    # ---- reading_exclusions.jsonl
    lines = []
    ex = sorted(c.exclusions, key=lambda e: (e['site'], e['instant'], e['sensor']))
    for e in ex:
        lines.append(jdump({'site': e['site'], 'sensor': e['sensor'],
                            'time_lst': c.clock.epoch_to_lst(e['instant']),
                            'reason': e['reason'], 'file': e['file']}, pretty=False))
    put('reading_exclusions.jsonl', ('\n'.join(lines) + '\n') if lines else '')

    # ---- amendment_ledger.psv
    hdr = ['seq', 'site', 'sensor', 'time_lst', 'op', 'status']
    rows = [[a['seq'], a['site'], a['sensor'], a['time_lst'], a['op'], a['status']]
            for a in sorted(c.amendments, key=lambda x: x['seq'])]
    put('amendment_ledger.psv', _delim_text(hdr, rows, '|'))

    # ---- parameters_used.yaml
    lines = []
    lines.append('network: %s' % reg.net)
    lines.append('period_start: %s' % reg.period_start)
    lines.append('period_end: %s' % reg.period_end)
    lines.append('rating_sheet: %s' % reg.rating_sheet)
    lines.append('index_sheet: %s' % reg.index_sheet)
    lines.append('site_sheet: %s' % reg.site_sheet)
    lines.append('max_gap_minutes: %d' % reg.max_gap_minutes)
    lines.append('min_coverage_fraction: %s' % fmt_places(reg.min_coverage, 2))
    lines.append('record_margin_hours: %d' % reg.record_margin_hours)
    lines.append('drift_tolerance_default_ft: %s' % reg.drift_default_text)
    tol_table = c.tolerance_table['id'] if c.tolerance_table else ''
    lines.append('tolerance_table: %s' % tol_table)
    for g in ('E', 'G', 'F'):
        v = c.tolerances_text.get(g)
        lines.append('tolerance_%s_pct: %s' % (g, v if v is not None else ''))
    lines.append('winter_table: %s' % (c.winter_table['id'] if c.winter_table else ''))
    r2 = table_by_title(reg.minutes, 'R-2', 'rating errata')
    lines.append('errata_table: %s' % (r2['id'] if r2 else ''))
    n_err = sum(len(v['errata']) for v in c.ratings.values())
    lines.append('errata_applied: %d' % n_err)
    lines.append('date_system: %s' % ('1904' if reg.date1904 else '1900'))
    lines.append('clock_standard_offset_minutes: %d' % (reg.clock.offset // MIN))
    lines.append('dst_rule: %s' % (reg.clock.rule or ''))
    for site in c.sites:
        lines.append('drift_tolerance_%s: %s' % (site, reg.drift_tol_text(site)))
    for site in c.sites:
        lines.append('max_gap_%s: %d' % (site, reg.max_gap(site)))
    for site in c.sites:
        v = c.winter_text.get(site)
        lines.append('winter_k_%s: %s' % (site, v if v is not None else ''))
    put('parameters_used.yaml', '\n'.join(lines) + '\n')

    # ---- variance_vs_published.csv
    hdr = ['site', 'date', 'published_cfs', 'recomputed_cfs', 'diff_cfs', 'status']
    rows = []
    keys = set()
    for (site, date), (val, codes) in reg.pub_daily.items():
        if site in c.site_set and val is not None:
            keys.add((site, date))
    for (site, date), d in c.daily.items():
        if d['value'] is not None:
            keys.add((site, date))
    for (site, date) in sorted(keys):
        pub = reg.pub_daily.get((site, date), (None, ''))[0]
        rec = c.daily.get((site, date))
        recv = rec['rounded'] if rec and rec['value'] is not None else None
        recv_exact = rec['value'] if rec and rec['value'] is not None else None
        if pub is not None and recv is not None:
            status = 'MATCH' if pub == recv else 'DIFF'
            diff = recv - pub
        elif pub is not None:
            status = 'ONLY_PUBLISHED'
            diff = None
        else:
            status = 'ONLY_RECOMPUTED'
            diff = None
        rows.append([site, date,
                     _plain_decimal(pub) if pub is not None else '',
                     discharge_fmt(recv_exact) if recv_exact is not None else '',
                     _plain_decimal(diff) if diff is not None else '',
                     status])
    put('variance_vs_published.csv', _delim_text(hdr, rows, ','))

    # ---- shift_vs_published.csv
    hdr = ['meas_no', 'site', 'published_decision', 'published_shift_ft',
           'recomputed_decision', 'recomputed_shift_ft', 'status']
    by_no = {m['meas_no']: m for m in c.meas_rows}
    rows = []
    for p in reg.shift_pub:
        m = by_no.get(p['meas_no'])
        if m is None:
            rows.append([p['meas_no'], p['site'], p['decision'],
                         fmt_places(Fraction(p['shift']), 2) if p['shift'] else '',
                         '', '', 'NOT_FOUND'])
            continue
        rd = m['decision']
        rs = fmt_places(m['shift'], 2) if m['shift'] is not None else ''
        ps = fmt_places(Fraction(p['shift']), 2) if p['shift'] else ''
        if p['decision'] == rd and (rd != 'SHIFT' or ps == rs):
            status = 'AGREE'
        else:
            status = 'DIFFER'
        rows.append([p['meas_no'], p['site'], p['decision'], ps, rd, rs, status])
    put('shift_vs_published.csv', _delim_text(hdr, rows, ','))

    # ---- dashboard_disagreements.tsv
    hdr = ['site', 'date', 'dashboard_cfs', 'recomputed_cfs', 'dashboard_ice',
           'recomputed_ice', 'q_agrees', 'ice_agrees']
    rows = []
    keys = []
    for (tok, date), (val, ice) in reg.dashboard.items():
        t = reg.clock.lst_to_epoch(date + ' 12:00')
        site = reg.resolve(tok, t)
        if site is None or site not in c.site_set:
            continue
        if date not in set(c.period_days):
            continue
        keys.append((site, date, val, ice))
    for (site, date, dval, dice) in sorted(keys):
        rec = c.daily.get((site, date))
        rv = rec['rounded'] if rec and rec['value'] is not None else None
        rv_exact = rec['value'] if rec and rec['value'] is not None else None
        rice = 'Y' if rec and 'ICE' in rec['codes'] else 'N'
        q_ok = (dval is None and rv is None) or (dval is not None and rv is not None and dval == rv)
        i_ok = (dice == rice)
        if q_ok and i_ok:
            continue
        rows.append([site, date,
                     _plain_decimal(dval) if dval is not None else '',
                     discharge_fmt(rv_exact) if rv_exact is not None else '',
                     dice, rice, 'Y' if q_ok else 'N', 'Y' if i_ok else 'N'])
    put('dashboard_disagreements.tsv', _delim_text(hdr, rows, '\t'))

    # ---- cache_divergence.jsonl
    lines = []
    entries = []
    for o in reg.cache:
        t = reg.clock.lst_to_epoch(str(o.get('t_lst') or '').strip().replace('T', ' '))
        site = reg.resolve(o.get('station'), t)
        if site is None or site not in c.site_set:
            continue
        entries.append((site, t, o))
    entries.sort(key=lambda x: (x[0], x[1]))
    for site, t, o in entries:
        cached = o.get('q_cfs')
        row = uv_index.get((site, t))
        rec = row['q'] if row is not None else None
        if rec is None:
            status = 'MISSING'
        elif cached is not None and Fraction(cached) == rec:
            status = 'CURRENT'
        else:
            status = 'STALE'
        lines.append(jdump({'site': site, 'time_lst': reg.clock.epoch_to_lst(t),
                            'cached_cfs': J(format(cached, 'f') if isinstance(cached, Decimal) else str(cached)),
                            'recomputed_cfs': J(fmt_rsig(rec)) if rec is not None else None,
                            'status': status}, pretty=False))
    put('cache_divergence.jsonl', ('\n'.join(lines) + '\n') if lines else '')

    # ---- reconciliation.md
    put('reconciliation.md', _reconciliation(c, reg))

    # ---- manifest
    order = ['unit_values.csv', 'gh_corrections.tsv', 'visit_errors.psv',
             'measurement_eval.csv', 'shift_curves.json', 'ice_periods.jsonl',
             'rating_tables_used.json', 'daily_values.csv', 'monthly_summary.xml',
             'period_statistics.json', 'alias_resolution.csv', 'dedup_report.json',
             'source_lineage.json', 'reading_exclusions.jsonl', 'amendment_ledger.psv',
             'parameters_used.yaml', 'variance_vs_published.csv', 'shift_vs_published.csv',
             'dashboard_disagreements.tsv', 'cache_divergence.jsonl', 'reconciliation.md']
    manifest = []
    for name in order:
        p = os.path.join(outdir, name)
        data = open(p, 'rb').read()
        manifest.append({'name': name, 'bytes': len(data),
                         'sha256': hashlib.sha256(data).hexdigest()})
    write_text(os.path.join(outdir, 'manifest.json'), jdump({'files': manifest}) + '\n')


def _delim_text(header, rows, delim):
    buf = [delim.join(header)]
    for r in rows:
        vals = []
        for v in r:
            if v is None:
                v = ''
            s = str(v)
            if delim in s or '"' in s or '\n' in s:
                s = '"' + s.replace('"', '""') + '"'
            vals.append(s)
        buf.append(delim.join(vals))
    return '\n'.join(buf) + '\n'


def _attr(v):
    return '"%s"' % xml_esc(v)


def _point_obj(p):
    return {'gh_ft': J(_plain_decimal(p[0])),
            'q_cfs': J(_plain_decimal(p[1])),
            'offset_ft': J(_plain_decimal(p[2]))}


def _month_list(start, end):
    d0 = datetime.date(*[int(x) for x in start.split('-')])
    d1 = datetime.date(*[int(x) for x in end.split('-')])
    out = []
    cur = datetime.date(d0.year, d0.month, 1)
    while cur < d1:
        nxt = datetime.date(cur.year + (cur.month == 12), (cur.month % 12) + 1, 1)
        ndays = (nxt - cur).days
        out.append(('%04d-%02d' % (cur.year, cur.month), ndays))
        cur = nxt
    return out


def _parse_pack_settings(path):
    settings = []
    in_table = False
    header_seen = False
    for line in open(path, encoding='utf-8'):
        s = line.strip()
        if s.startswith('## '):
            in_table = s[3:].strip().lower() == 'run settings'
            continue
        if not in_table:
            continue
        if s.startswith('|') and s.endswith('|'):
            cells = [x.strip() for x in s.strip('|').split('|')]
            if cells and set(cells[0]) <= set('-: '):
                continue
            if not header_seen:
                header_seen = True
                continue
            if len(cells) >= 2:
                settings.append(cells[:2])
    return settings


def _reconciliation(c, reg):
    pack = _parse_pack_settings(os.path.join(reg.dir, 'dv_compute_pack.md'))
    t2 = table_by_title(reg.minutes, 'T-2', 'grade tolerance')
    r2 = table_by_title(reg.minutes, 'R-2', 'rating errata')
    in_force = [reg.rating_sheet, (t2['id'] if t2 else 'T-2'),
                (r2['id'] if r2 else 'R-2'), 'record_mean', 'shift_in_use',
                'time_weighted_discharge', 'local_standard_time', 'prorated_visit_errors',
                'seq_order']
    buf = []
    buf.append('## Summary')
    buf.append('')
    buf.append('| site | published_days | recomputed_days | compared | diff_count | mean_diff_cfs |')
    buf.append('| --- | --- | --- | --- | --- | --- |')
    for site in c.sites:
        pub_days = 0
        rec_days = 0
        compared = 0
        diffs = []
        for day in c.period_days:
            pub = reg.pub_daily.get((site, day), (None, ''))[0]
            d = c.daily.get((site, day))
            rv = d['rounded'] if d and d['value'] is not None else None
            if pub is not None:
                pub_days += 1
            if rv is not None:
                rec_days += 1
            if pub is not None and rv is not None:
                compared += 1
                if pub != rv:
                    diffs.append(rv - pub)
        mean_diff = sum(diffs) / len(diffs) if diffs else None
        buf.append('| %s | %d | %d | %d | %d | %s |' % (
            site, pub_days, rec_days, compared, len(diffs),
            fmt_places(mean_diff, 2) if mean_diff is not None else ''))
    buf.append('')
    buf.append('## Run settings')
    buf.append('')
    buf.append('| setting | published_run | in_force |')
    buf.append('| --- | --- | --- |')
    idx = 0
    for cells in pack:
        setting = cells[0]
        value = cells[1]
        if setting == 'rating_sheet':
            force = reg.rating_sheet
        elif setting == 'tolerance_table':
            force = (t2['id'] if t2 else 'T-2')
        elif setting == 'errata':
            force = (r2['id'] if r2 else 'R-2')
        else:
            force = in_force[3 + idx] if 3 + idx < len(in_force) else ''
            idx += 1
        buf.append('| %s | %s | %s |' % (setting, value, force))
    buf.append('')
    buf.append('## Measurement decisions')
    buf.append('')
    buf.append('| site | measurements | shift | check | ice | rejected | no_record |')
    buf.append('| --- | --- | --- | --- | --- | --- | --- |')
    for site in c.sites:
        ms = [m for m in c.meas_rows if m['site'] == site]
        counts = {}
        for m in ms:
            counts[m['decision']] = counts.get(m['decision'], 0) + 1
        buf.append('| %s | %d | %d | %d | %d | %d | %d |' % (
            site, len(ms), counts.get('SHIFT', 0), counts.get('CHECK', 0),
            counts.get('ICE', 0), counts.get('REJECTED', 0), counts.get('NO_RECORD', 0)))
    buf.append('')
    return '\n'.join(buf)


def main():
    if len(sys.argv) != 3:
        sys.stderr.write('usage: run_flowrecord.py DATA_DIR OUT_DIR\n')
        return 2
    data, outdir = sys.argv[1], sys.argv[2]
    if not os.path.isdir(outdir):
        os.makedirs(outdir)
    reg = Registry(data)
    c = Compute(reg)
    c.run()
    render(c, outdir)
    return 0


if __name__ == '__main__':
    sys.exit(main())
