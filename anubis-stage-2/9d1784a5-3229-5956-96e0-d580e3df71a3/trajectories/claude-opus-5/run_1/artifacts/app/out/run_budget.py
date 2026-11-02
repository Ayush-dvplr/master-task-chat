#!/usr/bin/env python3
"""Recompute the KTC heat-load budget from a raw DAQ corpus.

Usage: python3 run_budget.py DATA_DIR OUT_DIR
"""
import sys
import os
import re
import json
import zlib
import zipfile
import sqlite3
import hashlib
import datetime
from fractions import Fraction
import xml.etree.ElementTree as ET

# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------

F0 = Fraction(0)


def rhe(x):
    """Round a Fraction half to even, to the nearest integer."""
    n = x.numerator
    d = x.denominator
    q, r = divmod(n, d)
    twice = 2 * r
    if twice > d:
        q += 1
    elif twice == d:
        if q % 2:
            q += 1
    return q


def rhe_step(x, step):
    """Round Fraction x half-even to a multiple of Fraction step."""
    return rhe(x / step) * step


def dec_places(text):
    t = text.strip()
    if '.' in t:
        return len(t.split('.')[1])
    return 0


def fmt_places(x, places):
    """Format Fraction x with exactly `places` decimals, round half even."""
    scale = 10 ** places
    n = rhe(x * scale)
    neg = n < 0
    n = abs(n)
    s = str(n).rjust(places + 1, '0')
    if places:
        s = s[:-places] + '.' + s[-places:]
    return ('-' if neg else '') + s


def trim_zeros(text):
    if '.' not in text:
        return text
    text = text.rstrip('0').rstrip('.')
    return text if text else '0'


def frac_str(x, maxp=12):
    """Exact decimal string of a Fraction with trailing zeros removed."""
    d = Fraction(x).denominator
    places = 0
    while d % 2 == 0:
        d //= 2
        places += 1
    while d % 5 == 0:
        d //= 5
        places += 1
    if d != 1:
        places = maxp
    return trim_zeros(fmt_places(x, max(places, 1)))


def parse_dec(text):
    return Fraction(text.strip())


EPOCH = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)


def iso_z_to_epoch(s):
    s = s.strip()
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})', s)
    if not m:
        raise ValueError('bad instant %r' % s)
    y, mo, d, h, mi, se = (int(g) for g in m.groups())
    dt = datetime.datetime(y, mo, d, h, mi, se, tzinfo=datetime.timezone.utc)
    return int((dt - EPOCH).total_seconds())


def iso_offset_to_epoch(s):
    s = s.strip()
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})'
                 r'(Z|[+-]\d{2}:?\d{2})$', s)
    if not m:
        raise ValueError('bad instant %r' % s)
    y, mo, d, h, mi, se = (int(g) for g in m.groups()[:6])
    off = m.group(7)
    dt = datetime.datetime(y, mo, d, h, mi, se, tzinfo=datetime.timezone.utc)
    base = int((dt - EPOCH).total_seconds())
    if off == 'Z':
        return base
    sign = 1 if off[0] == '+' else -1
    off = off[1:].replace(':', '')
    return base - sign * (int(off[:2]) * 3600 + int(off[2:]) * 60)


def date_to_epoch(s):
    y, mo, d = (int(x) for x in s.strip().split('-'))
    return int((datetime.datetime(y, mo, d, tzinfo=datetime.timezone.utc)
                - EPOCH).total_seconds())


def epoch_to_date(ts):
    return (EPOCH + datetime.timedelta(seconds=ts)).strftime('%Y-%m-%d')


# --------------------------------------------------------------------------
# YAML (restricted subset) reader
# --------------------------------------------------------------------------

def _yaml_scalar(text):
    t = text.strip()
    if t.startswith('#'):
        return None
    if (len(t) >= 2 and t[0] == "'" and t[-1] == "'"):
        return t[1:-1].replace("''", "'")
    if (len(t) >= 2 and t[0] == '"' and t[-1] == '"'):
        return t[1:-1]
    if t.startswith('{') and t.endswith('}'):
        out = {}
        for part in _split_flow(t[1:-1]):
            if not part.strip():
                continue
            k, _, v = part.partition(':')
            out[_yaml_scalar(k)] = _yaml_scalar(v)
        return out
    if t.startswith('[') and t.endswith(']'):
        return [_yaml_scalar(p) for p in _split_flow(t[1:-1]) if p.strip()]
    if t in ('true', 'True'):
        return True
    if t in ('false', 'False'):
        return False
    if t in ('null', '~', ''):
        return None
    if re.match(r'^-?\d+$', t):
        return int(t)
    if re.match(r'^-?\d*\.\d+$', t):
        return t
    return t


def _split_flow(text):
    out = []
    depth = 0
    cur = ''
    q = None
    for ch in text:
        if q:
            cur += ch
            if ch == q:
                q = None
            continue
        if ch in '\'"':
            q = ch
            cur += ch
        elif ch in '[{':
            depth += 1
            cur += ch
        elif ch in ']}':
            depth -= 1
            cur += ch
        elif ch == ',' and depth == 0:
            out.append(cur)
            cur = ''
        else:
            cur += ch
    out.append(cur)
    return out


def yaml_load(text):
    lines = []
    for raw in text.split('\n'):
        if not raw.strip() or raw.lstrip().startswith('#'):
            continue
        indent = len(raw) - len(raw.lstrip(' '))
        lines.append((indent, raw.strip()))
    val, _ = _yaml_block(lines, 0, 0)
    return val


def _yaml_block(lines, i, indent):
    if i >= len(lines):
        return None, i
    if lines[i][1].startswith('- '):
        return _yaml_seq(lines, i, lines[i][0])
    if lines[i][1] == '-':
        return _yaml_seq(lines, i, lines[i][0])
    return _yaml_map(lines, i, lines[i][0])


def _yaml_map(lines, i, indent):
    out = {}
    while i < len(lines):
        ind, text = lines[i]
        if ind < indent:
            break
        if ind > indent:
            raise ValueError('bad yaml indent %r' % text)
        if text.startswith('- '):
            break
        key, sep, rest = text.partition(':')
        key = _yaml_scalar(key)
        rest = rest.strip()
        i += 1
        if rest:
            out[key] = _yaml_scalar(rest)
        else:
            if i < len(lines) and (lines[i][0] > indent
                                   or (lines[i][1].startswith('-')
                                       and lines[i][0] >= indent)):
                sub, i = _yaml_block(lines, i, lines[i][0])
                out[key] = sub
            else:
                out[key] = None
    return out, i


def _yaml_seq(lines, i, indent):
    out = []
    while i < len(lines):
        ind, text = lines[i]
        if ind != indent or not text.startswith('-'):
            break
        body = text[1:].strip()
        i += 1
        if body:
            scal = _yaml_scalar(body)
            if body[0] in '\'"[{':
                out.append(scal)
            elif ':' in body:
                sub_lines = [(indent + 2, body)]
                while i < len(lines) and lines[i][0] > indent:
                    sub_lines.append(lines[i])
                    i += 1
                sub, _ = _yaml_map(sub_lines, 0, indent + 2)
                out.append(sub)
            else:
                out.append(scal)
        else:
            sub, i = _yaml_block(lines, i, lines[i][0])
            out.append(sub)
    return out, i


# --------------------------------------------------------------------------
# PDF text extraction
# --------------------------------------------------------------------------

def _pdf_unescape(s):
    out = []
    i = 0
    while i < len(s):
        c = s[i]
        if c == '\\' and i + 1 < len(s):
            n = s[i + 1]
            if n in 'nrtbf':
                out.append({'n': '\n', 'r': '\r', 't': '\t',
                            'b': '\b', 'f': '\f'}[n])
                i += 2
            elif n.isdigit():
                j = i + 1
                d = ''
                while j < len(s) and s[j].isdigit() and len(d) < 3:
                    d += s[j]
                    j += 1
                out.append(chr(int(d, 8)))
                i = j
            else:
                out.append(n)
                i += 2
        else:
            out.append(c)
            i += 1
    return ''.join(out)


def _pdf_strings(blob):
    res = []
    i = 0
    while i < len(blob):
        c = blob[i]
        if c == '(':
            depth = 1
            j = i + 1
            buf = ''
            while j < len(blob):
                if blob[j] == '\\':
                    buf += blob[j:j + 2]
                    j += 2
                    continue
                if blob[j] == '(':
                    depth += 1
                elif blob[j] == ')':
                    depth -= 1
                    if depth == 0:
                        break
                buf += blob[j]
                j += 1
            res.append(_pdf_unescape(buf))
            i = j + 1
        elif c == '<':
            j = blob.index('>', i)
            h = re.sub(r'\s', '', blob[i + 1:j])
            if len(h) % 2:
                h += '0'
            res.append(bytes.fromhex(h).decode('latin1'))
            i = j + 1
        else:
            i += 1
    return ''.join(res)


def pdf_rows(path):
    """Return a list of pages; each page is a list of rows (list of cells)."""
    raw = open(path, 'rb').read()
    pages = []
    for m in re.finditer(rb'stream\r?\n(.*?)\r?\nendstream', raw, re.S):
        data = zlib.decompress(m.group(1)).decode('latin1')
        items = []
        for line in data.split('\n'):
            tm = re.search(r'1 0 0 1 (-?[\d.]+) (-?[\d.]+) Tm', line)
            if not tm:
                continue
            x = float(tm.group(1))
            y = float(tm.group(2))
            rest = line[tm.end():]
            cut = max(rest.rfind(' Tj'), rest.rfind(' TJ'))
            txt = _pdf_strings(rest[:cut]) if cut >= 0 else ''
            items.append((y, x, txt))
        by_y = {}
        for y, x, t in items:
            by_y.setdefault(y, []).append((x, t))
        rows = []
        for y in sorted(by_y, reverse=True):
            rows.append([t for _, t in sorted(by_y[y])])
        pages.append(rows)
    return pages


class Memo(object):
    """Tables of the governance memo, keyed by label."""

    def __init__(self, path):
        self.tables = {}
        self.labels = {}
        pages = pdf_rows(path)
        flat = []
        for rows in pages:
            flat.extend(rows)
        cur = None
        header = None
        for row in flat:
            if len(row) == 1:
                text = row[0]
                m = re.match(r'^Table ([A-Z]-\d+): (.*?)\((IN FORCE|WITHDRAWN)\)\s*$',
                             text)
                if m:
                    cur = (m.group(1), m.group(3))
                    self.tables.setdefault(cur, [])
                    header = None
                    continue
                m = re.match(r'^Table ([A-Z]-\d+) \(continued\)\s*$', text)
                if m:
                    for key in self.tables:
                        if key[0] == m.group(1):
                            cur = key
                    header = None
                    continue
                if not text.strip():
                    cur = None
                continue
            if cur is None:
                continue
            if header is None:
                header = row
                continue
            if row == header:
                continue
            self.tables[cur].append(row)

    def table(self, label, status='IN FORCE'):
        return self.tables.get((label, status), [])

    def in_force(self, prefix):
        """Return (label, rows) for the IN FORCE table whose label starts with
        prefix (e.g. 'J')."""
        best = None
        for (label, status), rows in self.tables.items():
            if status != 'IN FORCE':
                continue
            if label.split('-')[0] == prefix:
                if best is None or label > best[0]:
                    best = (label, rows)
        if best is None:
            raise KeyError(prefix)
        return best


# --------------------------------------------------------------------------
# xlsx
# --------------------------------------------------------------------------

XNS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
XRNS = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'


def _colnum(s):
    n = 0
    for ch in s:
        n = n * 26 + ord(ch) - 64
    return n


def _colname(n):
    s = ''
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


class Workbook(object):
    def __init__(self, path):
        self.z = zipfile.ZipFile(path)
        wb = ET.fromstring(self.z.read('xl/workbook.xml'))
        pr = wb.find(XNS + 'workbookPr')
        self.date1904 = pr is not None and pr.get('date1904') in ('1', 'true')
        rels = {}
        for r in ET.fromstring(self.z.read('xl/_rels/workbook.xml.rels')):
            rels[r.get('Id')] = r.get('Target')
        self.parts = {}
        for s in wb.find(XNS + 'sheets'):
            tgt = rels[s.get(XRNS + 'id')]
            self.parts[s.get('name')] = 'xl/' + tgt.lstrip('/')
        self.shared = []
        try:
            ss = ET.fromstring(self.z.read('xl/sharedStrings.xml'))
        except KeyError:
            ss = []
        for si in ss:
            self.shared.append(''.join(t.text or '' for t in si.iter(XNS + 't')))
        self._cache = {}

    def rows(self, name):
        if name in self._cache:
            return self._cache[name]
        sh = ET.fromstring(self.z.read(self.parts[name]))
        out = []
        for row in sh.iter(XNS + 'row'):
            cells = {}
            for c in row.findall(XNS + 'c'):
                col = re.match(r'([A-Z]+)', c.get('r')).group(1)
                t = c.get('t')
                if t == 's':
                    v = self.shared[int(c.find(XNS + 'v').text)]
                elif t == 'inlineStr':
                    node = c.find(XNS + 'is')
                    v = ''.join(x.text or '' for x in node.iter(XNS + 't'))
                else:
                    vn = c.find(XNS + 'v')
                    v = vn.text if vn is not None else ''
                cells[col] = v
            if cells:
                n = max(_colnum(k) for k in cells)
                out.append([cells.get(_colname(i), '')
                            for i in range(1, n + 1)])
        self._cache[name] = out
        return out

    def serial_date(self, serial):
        n = int(str(serial).split('.')[0])
        base = datetime.date(1904, 1, 1) if self.date1904 else datetime.date(1899, 12, 30)
        return (base + datetime.timedelta(days=n)).strftime('%Y-%m-%d')


# --------------------------------------------------------------------------
# token canonicalisation
# --------------------------------------------------------------------------

CAMPAIGN = {'prefix': 'KTC', 'code': '26B'}


def set_campaign(name):
    m = re.match(r'^([A-Za-z]+)-(\S+)$', (name or '').strip())
    if m:
        CAMPAIGN['prefix'] = m.group(1).upper()
        CAMPAIGN['code'] = m.group(2).upper()


def canon_run(token):
    """Return canonical run id or None when the token is of another campaign."""
    t = (token or '').strip()
    if not t:
        return None
    up = t.upper()
    code = CAMPAIGN['code']
    m = re.match(r'^[A-Z]+-([0-9]{2}[A-Z])[/-]', up)
    if m is None:
        m = re.match(r'^([0-9]{2}[A-Z])[/-]', up)
    if m and m.group(1) != code:
        return None
    m = re.search(r'(\d+)\s*$', up)
    if not m:
        return None
    return '%s-R%02d' % (CAMPAIGN['prefix'], int(m.group(1)))


def canon_serial(token):
    t = (token or '').strip().upper()
    t = t.replace(' ', '').replace('-', '').replace('_', '')
    m = re.match(r'^([A-Z]+)(\d+)$', t)
    if not m:
        return None
    return '%s-%s' % (m.group(1), m.group(2))


def canon_channel(token):
    t = (token or '').strip().upper()
    m = re.match(r'^D(\d+)C(\d+)$', t)
    if not m:
        m = re.match(r'^DAQ(\d+)[-_/](\d+)$', t)
    if not m:
        m = re.match(r'^(\d+)/(\d+)$', t)
    if not m:
        m = re.match(r'^CH(\d+)@DAQ(\d+)$', t)
        if m:
            return 'D%dC%02d' % (int(m.group(2)), int(m.group(1)))
    if not m:
        return None
    return 'D%dC%02d' % (int(m.group(1)), int(m.group(2)))


def canon_link(token):
    t = (token or '').strip().upper()
    t = t.replace(' ', '').replace('-', '').replace('_', '')
    m = re.match(r'^([A-Z]+)(\d+)$', t)
    if not m:
        return None
    return '%s-%03d' % (m.group(1), int(m.group(2)))


# --------------------------------------------------------------------------
# site time
# --------------------------------------------------------------------------

class SiteTime(object):
    def __init__(self, cal):
        self.base = self._off(cal['base_offset'])
        self.trans = []
        for t in cal.get('transitions') or []:
            self.trans.append((iso_z_to_epoch(t['at_utc']),
                               self._off(t['offset_after'])))
        self.trans.sort()
        offs = set([self.base] + [o for _, o in self.trans])
        self.offsets = sorted(offs)

    @staticmethod
    def _off(text):
        t = str(text).strip()
        sign = 1 if t[0] == '+' else -1
        h, m = t[1:].split(':')
        return sign * (int(h) * 3600 + int(m) * 60)

    def offset_at(self, ts):
        off = self.base
        for at, o in self.trans:
            if ts >= at:
                off = o
            else:
                break
        return off

    def wall_to_utc(self, wall_epoch):
        """wall_epoch: the wall-clock time read as if it were UTC."""
        best = None
        for off in self.offsets:
            t = wall_epoch - off
            if self.offset_at(t) == off:
                if best is None or t < best:
                    best = t
        if best is not None:
            return best
        # skipped hour: use the offset in effect before the jump
        cands = []
        for at, _o in self.trans:
            cands.append(at)
        off = self.base
        for at, o in self.trans:
            if wall_epoch - o >= at:
                pass
        # find the transition whose gap contains the wall time
        prev = self.base
        for at, o in self.trans:
            if prev != o:
                lo = at + prev
                hi = at + o
                if lo <= wall_epoch < hi:
                    return wall_epoch - prev
            prev = o
        return wall_epoch - self.base


# --------------------------------------------------------------------------
# conductivity
# --------------------------------------------------------------------------

class Conductivity(object):
    """k(T) tables and the exact integral theta(T) with T in mK."""

    def __init__(self, rows):
        tab = {}
        for row in rows:
            mat, t_k, k, unit = row[0], row[1], row[2], row[3]
            kv = Fraction(k.strip())
            if unit.strip() == 'mW/cm-K':
                kv = kv * Fraction(1, 10)
            elif unit.strip() != 'W/m-K':
                raise ValueError('unit %r' % unit)
            tab.setdefault(mat.strip(), []).append(
                (int(rhe(Fraction(t_k.strip()) * 1000)), kv))
        self.materials = {}
        for mat, pts in tab.items():
            pts.sort()
            theta = [F0]
            for i in range(1, len(pts)):
                t0, k0 = pts[i - 1]
                t1, k1 = pts[i]
                theta.append(theta[-1] + Fraction(t1 - t0) * (k0 + k1) / 2)
            # prepend the constant-k stretch from 0 to the first point
            t_first, k_first = pts[0]
            base = Fraction(t_first) * k_first
            self.materials[mat] = {
                'pts': pts,
                'theta': [base + v for v in theta],
                'k_first': k_first,
                'k_last': pts[-1][1],
            }
        self._fcache = {}

    def codes(self):
        return set(self.materials)

    def k(self, mat, t_mK):
        m = self.materials[mat]
        pts = m['pts']
        if t_mK <= pts[0][0]:
            return m['k_first']
        if t_mK >= pts[-1][0]:
            return m['k_last']
        lo, hi = 0, len(pts) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if pts[mid][0] <= t_mK:
                lo = mid
            else:
                hi = mid
        t0, k0 = pts[lo]
        t1, k1 = pts[hi]
        return k0 + (k1 - k0) * Fraction(t_mK - t0, t1 - t0)

    def theta(self, mat, t):
        """Exact integral of k from 0 to t (t in mK, may be fractional)."""
        m = self.materials[mat]
        pts = m['pts']
        th = m['theta']
        if t <= pts[0][0]:
            return m['k_first'] * t
        if t >= pts[-1][0]:
            return th[-1] + m['k_last'] * (t - pts[-1][0])
        lo, hi = 0, len(pts) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if pts[mid][0] <= t:
                lo = mid
            else:
                hi = mid
        t0, k0 = pts[lo]
        t1, k1 = pts[hi]
        dt = t - t0
        slope = (k1 - k0) / Fraction(t1 - t0)
        return th[lo] + k0 * dt + slope * dt * dt / 2

    def theta_max(self, mat):
        m = self.materials[mat]
        return m['theta'][-1]

    def _floats(self, mat):
        f = self._fcache.get(mat)
        if f is None:
            m = self.materials[mat]
            f = ([p[0] for p in m['pts']], [float(x) for x in m['theta']],
                 [float(p[1]) for p in m['pts']])
            self._fcache[mat] = f
        return f

    def theta_inv_round(self, mat, target):
        """Largest-precision inverse of theta, rounded half-even to whole mK.

        Returns None when target < 0 (a failed march)."""
        if target < 0:
            return None
        ts, ths, ks = self._floats(mat)
        ft = float(target)
        # approximate
        if ft <= ths[0]:
            approx = ft / ks[0] if ks[0] else 0.0
        elif ft >= ths[-1]:
            approx = ts[-1] + (ft - ths[-1]) / ks[-1]
        else:
            lo, hi = 0, len(ts) - 1
            while hi - lo > 1:
                mid = (lo + hi) // 2
                if ths[mid] <= ft:
                    lo = mid
                else:
                    hi = mid
            t0 = ts[lo]
            k0 = ks[lo]
            k1 = ks[hi]
            dT = ts[hi] - t0
            c = ft - ths[lo]
            a = (k1 - k0) / (2.0 * dT)
            if a == 0.0:
                approx = t0 + c / k0
            else:
                disc = k0 * k0 + 4 * a * c
                if disc < 0:
                    disc = 0.0
                approx = t0 + (-k0 + disc ** 0.5) / (2 * a)
        n = int(approx)
        if n < 0:
            n = 0
        while n > 0 and self.theta(mat, n) > target:
            n -= 1
        while self.theta(mat, n + 1) <= target:
            n += 1
        mid = self.theta(mat, Fraction(2 * n + 1, 2))
        if target < mid:
            return n
        if target > mid:
            return n + 1
        return n if n % 2 == 0 else n + 1


# --------------------------------------------------------------------------
# corpus
# --------------------------------------------------------------------------

UNIT_MAP = {
    'ohm': 'ohm', 'kohm': 'kohm', 'v': 'V', 'volt': 'V',
    'mv': 'mV', 'mvolt': 'mV',
}

MEASURED = ('ST300', 'ST50', 'ST4')


class Reading(object):
    __slots__ = ('shard', 'order', 'index', 'run', 'serial_token',
                 'channel_token', 'instant', 'raw_text', 'unit', 'rev',
                 'void', 'missing', 'final', 'bad')

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))


class Corpus(object):
    def __init__(self, data_dir):
        self.dir = data_dir
        self.names = {}
        for key, pattern in (('profile', r'campaign_profile_.*\.ya?ml'),
                             ('catalog', r'ingest_catalog_.*\.json'),
                             ('memo', r'governance_memo_.*\.pdf'),
                             ('workbook', r'.*\.xlsx'),
                             ('sensor_map', r'sensor_map_.*\.ya?ml'),
                             ('run_log', r'run_log_.*\.csv'),
                             ('bulletin', r'ops_bulletin_.*\.txt'),
                             ('quick_reference', r'quick_reference_.*\.txt'),
                             ('draft', r'handbook_draft_.*\.md')):
            self.names[key] = self._find(pattern)
        self.profile = yaml_load(self._read(self.names['profile']))
        set_campaign(self.profile['campaign'])
        self.catalog = json.loads(self._read(self.names['catalog']))
        self.calendar = yaml_load(self._read('site_calendar.yml'))
        self.site = SiteTime(self.calendar)
        self.memo = Memo(self.path(self.names['memo']))
        self.wb = Workbook(self.path(self.names['workbook']))
        self._load_memo_tables()
        self._load_aliases()
        self._load_inventory()
        self._load_sensor_map()
        self._load_runs()
        self._load_rulings()
        self._load_calibration()
        self.cond = Conductivity(
            self.wb.rows(self.profile['conductivity_sheet'])[1:])
        self._load_capacity()
        self._load_service_log()
        self._load_intercepts()
        self._load_harness()
        self._load_lots()

    # -- plumbing ----------------------------------------------------------
    def path(self, name):
        return os.path.join(self.dir, name)

    def _read(self, name, binary=False):
        mode = 'rb' if binary else 'r'
        with open(self.path(name), mode) as fh:
            return fh.read()

    def _find(self, pattern):
        rx = re.compile(pattern + '$')
        for name in sorted(os.listdir(self.dir)):
            if rx.match(name):
                return name
        raise IOError(pattern)

    # -- memo --------------------------------------------------------------
    def _load_memo_tables(self):
        self.tbl_joint_label, joint = self.memo.in_force('J')
        self.tbl_par_label, par = self.memo.in_force('P')
        self.tbl_solver_label, solver = self.memo.in_force('S')
        self.tbl_gauge_label, gauge = self.memo.in_force('W')
        self.tbl_limit_label, limit = self.memo.in_force('L')
        self.tbl_ruling_label, rulings = self.memo.in_force('R')
        self.h_base = {}
        for cls, band, val in [(r[0], r[1], r[2]) for r in joint]:
            self.h_base[(cls.strip(), band.strip())] = Fraction(val.strip())
        self.parasitic = {}
        for cfg, stage, val in [(r[0], r[1], r[2]) for r in par]:
            self.parasitic[(cfg.strip(), stage.strip())] = int(val.strip())
        self.solver = {}
        for row in solver:
            self.solver[row[0].strip()] = row[1].strip() if len(row) > 1 else ''
        self.gauge = {}
        for row in gauge:
            self.gauge[row[0].strip()] = Fraction(row[1].strip())
        self.limits = {}
        for row in limit:
            self.limits[row[0].strip()] = int(row[1].strip())
        self.raw_rulings = rulings
        self.h_increment = Fraction(self.solver['h_increment_mW_per_K'])
        self.indium_factor = Fraction(self.solver['indium_factor'])
        self.low_torque_factor = Fraction(self.solver['low_torque_factor'])
        self.lot_materials = self.solver['lot_scale_materials'].split()

    # -- aliases -----------------------------------------------------------
    def _load_aliases(self):
        con = sqlite3.connect(self.path('entity_alias_register.sqlite'))
        self.mat_alias = {}
        for token, target, status in con.execute(
                'select token, target, status from material_alias'):
            if (status or '').strip().upper() == 'ACTIVE':
                self.mat_alias[(token or '').strip().lower()] = (target or '').strip()
        self.node_alias = {}
        for token, node in con.execute('select token, node from node_alias'):
            self.node_alias[(token or '').strip().lower()] = (node or '').strip()
        self.link_alias = {}
        for old, new, _eff in con.execute(
                'select old_id, new_id, effective from link_alias'):
            key = canon_link(old)
            if key:
                self.link_alias[key] = canon_link(new)
        self.relabel = {}
        for old, new, _eff in con.execute(
                'select old_serial, new_serial, effective_utc from sensor_relabel'):
            key = canon_serial(old)
            if key:
                self.relabel[key] = canon_serial(new)
        con.close()
        con = sqlite3.connect(self.path('channel_map_history.db'))
        self.chan_map = {}
        for ch, serial, vf, vt in con.execute(
                'select channel, serial, valid_from_utc, valid_to_utc'
                ' from channel_assignment'):
            key = canon_channel(ch) or (ch or '').strip().upper()
            lo = iso_z_to_epoch(vf) if vf else None
            hi = iso_z_to_epoch(vt) if vt else None
            self.chan_map.setdefault(key, []).append((lo, hi, canon_serial(serial)))
        con.close()

    def resolve_material(self, token):
        cur = (token or '').strip()
        seen = set()
        codes = self.cond.codes() if hasattr(self, 'cond') else None
        for _ in range(64):
            key = cur.lower()
            if key in seen:
                break
            seen.add(key)
            nxt = self.mat_alias.get(key)
            if nxt is None:
                break
            cur = nxt
        if codes is None or cur in codes:
            return cur
        return None

    def resolve_node(self, token):
        t = (token or '').strip()
        hit = self.node_alias.get(t.lower())
        if hit:
            return hit
        if t in MEASURED:
            return t
        if t in getattr(self, 'intercept_ids', ()):
            return t
        return None

    def resolve_link(self, token):
        cur = canon_link(token)
        if cur is None:
            return None
        seen = set()
        while cur in self.link_alias and cur not in seen:
            seen.add(cur)
            cur = self.link_alias[cur]
        return cur

    def resolve_serial_chain(self, serial):
        cur = serial
        seen = set()
        while cur in self.relabel and cur not in seen:
            seen.add(cur)
            cur = self.relabel[cur]
        return cur

    def resolve_channel(self, channel, instant):
        rows = self.chan_map.get(channel)
        if not rows:
            return None
        for lo, hi, serial in rows:
            if lo is not None and instant < lo:
                continue
            if hi is not None and instant >= hi:
                continue
            return serial
        return None

    # -- inventory / sensor map -------------------------------------------
    def _load_inventory(self):
        data = json.loads(self._read('sensor_inventory.json'))
        self.inventory = {}
        for s in data['sensors']:
            self.inventory[s['serial'].strip()] = s
        rows = []
        for line in self._read('calibration_generic_curves.tsv').split('\n'):
            if not line.strip():
                continue
            rows.append(line.split('\t'))
        head = rows[0]
        self.generic = {}
        for row in rows[1:]:
            rec = dict(zip(head, row))
            self.generic.setdefault(rec['curve'], []).append(
                (int(rec['point']), rec['raw'].strip(), rec['unit'].strip(),
                 rec['T_K'].strip()))
        for key in self.generic:
            self.generic[key].sort()

    def _load_sensor_map(self):
        data = yaml_load(self._read(self.names['sensor_map']))
        self.sensor_stages = {}
        for entry in data['assignments']:
            hist = []
            for h in entry['history']:
                hist.append((iso_z_to_epoch(h['from_utc']), h['stage']))
            hist.sort()
            self.sensor_stages[entry['serial'].strip()] = hist

    def stage_of(self, serial, instant):
        hist = self.sensor_stages.get(serial)
        if not hist:
            return None
        token = None
        for ts, stage in hist:
            if ts <= instant:
                token = stage
            else:
                break
        if token is None:
            return None
        return self.resolve_node(token)

    # -- runs --------------------------------------------------------------
    def _load_runs(self):
        self.run_ids = [r['id'] for r in self.profile['runs']]
        self.run_profile = {r['id']: r for r in self.profile['runs']}
        overlay = None
        for name in sorted(os.listdir(self.dir)):
            if not re.match(r'profile_overlay_.*\.ya?ml$', name):
                continue
            data = yaml_load(self._read(name))
            if data.get('base_revision') == self.profile['profile_revision']:
                overlay = data
                self.overlay_name = name
        self.overlay = overlay
        self.overlay_applied = overlay is not None
        rows = list(csv_rows(self._read(self.names['run_log'])))
        eff = {}
        for row in rows:
            run = canon_run(row['run'])
            if run is None:
                continue
            event = row['event'].strip()
            if event == 'NOTE':
                continue
            rev = int(row['rev'])
            key = (run, event)
            if key not in eff or rev >= eff[key][0]:
                eff[key] = (rev, row)
        self.run_events = eff
        self.windows = {}
        self.configs = {}
        self.aborted = set()
        runs_seen = set(run for run, _ in eff)
        for run in runs_seen:
            start = eff.get((run, 'PLATEAU_START'))
            end = eff.get((run, 'PLATEAU_END'))
            if start and end:
                self.windows[run] = (
                    self.site.wall_to_utc(
                        iso_z_to_epoch(start[1]['local_time'].strip() + ':00')),
                    self.site.wall_to_utc(
                        iso_z_to_epoch(end[1]['local_time'].strip() + ':00')))
            cfg = eff.get((run, 'CONFIG'))
            if cfg:
                self.configs[run] = cfg[1]['value'].strip()
            ab = eff.get((run, 'ABORT'))
            if ab and ab[1]['value'].strip().upper() == 'ACTIVE':
                self.aborted.add(run)
        self.active_runs = [r for r in self.run_ids if r not in self.aborted]

    def setting(self, run, key):
        val = self.profile.get(key)
        entry = self.run_profile.get(run) or {}
        if key in entry:
            val = entry[key]
        if self.overlay:
            keys = self.overlay.get('overridable_keys') or []
            runs = self.overlay.get('runs') or {}
            if key in keys and run in runs and key in (runs[run] or {}):
                val = runs[run][key]
        return val

    def reserve_pct(self, run, stage):
        base = self.profile['reserve_pct'][stage]
        entry = self.run_profile.get(run) or {}
        key = 'reserve_pct_' + stage
        if isinstance(entry.get('reserve_pct'), dict):
            base = entry['reserve_pct'].get(stage, base)
        if key in entry:
            base = entry[key]
        if self.overlay:
            keys = self.overlay.get('overridable_keys') or []
            runs = self.overlay.get('runs') or {}
            if key in keys and run in runs and key in (runs[run] or {}):
                base = runs[run][key]
        return base

    def run_date(self, run):
        win = self.windows.get(run)
        if not win:
            return ''
        return epoch_to_date(win[0])

    # -- rulings -----------------------------------------------------------
    def _load_rulings(self):
        status = {}
        order = []
        info = {}
        for row in self.raw_rulings:
            rid = row[0].strip()
            status[rid] = row[5].strip().upper()
            info[rid] = row
            order.append(rid)
        root = ET.fromstring(self._read('ruling_addendum.xml'))
        entries = []
        for e in root.findall('entry'):
            entries.append((int(e.get('seq')), e.get('ref').strip(),
                            e.get('action').strip().upper(),
                            e.get('status').strip().upper()))
        entries.sort()
        for _seq, ref, action, st in entries:
            if st != 'ISSUED' or ref not in status:
                continue
            if action == 'RESCIND':
                status[ref] = 'RESCINDED'
            elif action == 'REINSTATE':
                status[ref] = 'IN FORCE'
        self.excluded_sensors = {}
        self.sensor_offsets = {}
        self.excluded_links = {}
        for rid in order:
            if status[rid] != 'IN FORCE':
                continue
            row = info[rid]
            run = canon_run(row[1])
            if run is None:
                continue
            action = row[3].strip().upper()
            target = row[2].strip()
            value = row[4].strip()
            if action == 'EXCLUDE_SENSOR':
                serial = self.resolve_serial_chain(canon_serial(target))
                self.excluded_sensors.setdefault(run, set()).add(serial)
            elif action == 'OFFSET_SENSOR':
                serial = self.resolve_serial_chain(canon_serial(target))
                self.sensor_offsets.setdefault(run, {})[serial] = int(value)
            elif action == 'EXCLUDE_LINK':
                link = self.resolve_link(target)
                self.excluded_links.setdefault(run, set()).add(link)

    # -- calibration -------------------------------------------------------
    def _load_calibration(self):
        rows = self.wb.rows(self.profile['calibration_sheet'])
        head = [c.strip() for c in rows[0]]
        versions = {}
        for row in rows[1:]:
            rec = dict(zip(head, row))
            serial = rec['serial'].strip()
            ver = rec['version'].strip()
            key = (serial, ver)
            versions.setdefault(key, {'from': self.wb.serial_date(rec['valid_from']),
                                      'pts': []})
            versions[key]['pts'].append(
                (int(float(rec['point'])), rec['raw'].strip(),
                 rec['unit'].strip(), rec['T_K'].strip()))
        self.cal = {}
        for (serial, ver), data in versions.items():
            data['pts'].sort()
            self.cal.setdefault(serial, []).append(
                (date_to_epoch(data['from']), ver, data['pts']))
        for serial in self.cal:
            self.cal[serial].sort()

    # -- capacity ----------------------------------------------------------
    def _load_capacity(self):
        rows = self.wb.rows(self.profile['capacity_sheet'])
        self.capmap = {}
        for row in rows[1:]:
            model, stage, t_k, cap = (row[0].strip(), row[1].strip(),
                                      row[2].strip(), row[3].strip())
            self.capmap.setdefault((model, stage), []).append(
                (int(rhe(Fraction(t_k) * 1000)), Fraction(cap)))
        for key in self.capmap:
            self.capmap[key].sort()

    def _load_service_log(self):
        self.service = {}
        for row in tsv_rows(self._read('cooler_service_log.tsv')):
            action = row['action'].strip().upper()
            if action not in ('DERATE', 'RESTORE'):
                continue
            cooler = row['cooler'].strip()
            val = F0 if action == 'RESTORE' else Fraction(row['value'].strip())
            self.service.setdefault(cooler, []).append(
                (row['date'].strip(), val))
        for key in self.service:
            self.service[key].sort(key=lambda x: x[0])

    def derate(self, cooler, date):
        val = F0
        for d, v in self.service.get(cooler, []):
            if d <= date:
                val = v
            else:
                break
        return val

    # -- intercepts / harness / lots --------------------------------------
    def _load_intercepts(self):
        root = ET.fromstring(self._read('intercept_register.xml'))
        self.intercepts = {}
        self.intercept_ids = set()
        self.bundle_nodes = {}
        for e in root.findall('intercept'):
            run = canon_run(e.get('run'))
            iid = e.get('id').strip()
            self.intercept_ids.add(iid)
            self.intercepts[(run, iid)] = {
                'band': e.get('band').strip(),
                'nominal_K': e.get('nominal_K'),
            }
        for e in root.findall('bundle'):
            run = canon_run(e.get('run'))
            self.bundle_nodes[(run, e.get('id').strip())] = e.get('node').strip()

    def _load_harness(self):
        best = {}
        for row in psv_rows(self._read('harness_dissipation.psv')):
            bundle = row['bundle'].strip()
            run = canon_run(row['run'])
            rev = int(row['rev'])
            key = (run, bundle)
            if key not in best or rev >= best[key][0]:
                best[key] = (rev, row)
        self.harness = {}
        for (run, bundle), (_rev, row) in best.items():
            if row['void'].strip().upper() == 'VOID':
                continue
            unit = row['unit'].strip()
            val = Fraction(row['dissipation'].strip())
            if unit == 'mW':
                val = val * 1000
            node_token = self.bundle_nodes.get((run, bundle))
            if node_token is None:
                continue
            node = self.resolve_node(node_token)
            if node is None:
                continue
            cur = self.harness.setdefault(run, {})
            cur[node] = cur.get(node, F0) + val

    def _load_lots(self):
        root = ET.fromstring(self._read('material_lot_certs.xml'))
        self.lots = {}
        for e in root.findall('lot'):
            self.lots[e.get('id').strip()] = (
                e.get('status').strip().upper(), Fraction(e.get('k_scale').strip()))


# --------------------------------------------------------------------------
# delimited readers
# --------------------------------------------------------------------------

def _split_line(line, delim):
    out = []
    cur = ''
    q = False
    i = 0
    while i < len(line):
        ch = line[i]
        if q:
            if ch == '"':
                if i + 1 < len(line) and line[i + 1] == '"':
                    cur += '"'
                    i += 2
                    continue
                q = False
            else:
                cur += ch
        else:
            if ch == '"':
                q = True
            elif ch == delim:
                out.append(cur)
                cur = ''
            else:
                cur += ch
        i += 1
    out.append(cur)
    return out


def delim_rows(text, delim):
    lines = [l for l in text.split('\n') if l != '']
    if not lines:
        return
    head = [h.strip() for h in _split_line(lines[0], delim)]
    for line in lines[1:]:
        cells = _split_line(line, delim)
        if len(cells) < len(head):
            cells = cells + [''] * (len(head) - len(cells))
        yield dict(zip(head, cells))


def csv_rows(text):
    return delim_rows(text, ',')


def tsv_rows(text):
    return delim_rows(text, '\t')


def psv_rows(text):
    return delim_rows(text, '|')



# --------------------------------------------------------------------------
# reading shard parsers
# --------------------------------------------------------------------------

def _unit(text):
    t = (text or '').strip().lower()
    return UNIT_MAP.get(t)


def _rec(run, instant, rev, void, raw, unit, serial=None, channel=None):
    return {'run': run, 'instant': instant, 'rev': rev, 'void': void,
            'raw': raw, 'unit': unit, 'serial': serial, 'channel': channel}


def _dmy_to_wall(text):
    m = re.match(r'^(\d{2})/(\d{2})/(\d{4})\s+(\d{2}):(\d{2}):(\d{2})$',
                 text.strip())
    d, mo, y, h, mi, s = (int(g) for g in m.groups())
    return int((datetime.datetime(y, mo, d, h, mi, s,
                                  tzinfo=datetime.timezone.utc) - EPOCH)
               .total_seconds())


def _iso_to_wall(text):
    return iso_z_to_epoch(text.strip())


def parse_L01(text, site):
    out = []
    for row in csv_rows(text):
        raw = row['raw'].strip()
        out.append(_rec(row['run'], iso_z_to_epoch(row['ts_utc']),
                        int(row['rev']), row['void'].strip() == 'Y',
                        None if raw in ('', 'NaN') else raw,
                        _unit(row['unit']), serial=row['sensor']))
    return out


def parse_L02(text, site):
    out = []
    for row in tsv_rows(text):
        raw = row['VALUE'].strip()
        out.append(_rec(row['RUN'], int(row['EPOCH_S']), int(row['REVISION']),
                        row['STATUS'].strip() == 'VOID',
                        None if raw in ('', '-9999') else raw,
                        _unit(row['UNITS']), serial=row['SERIAL']))
    return out


def parse_L03(text, site):
    out = []
    for row in psv_rows(text):
        wall = _dmy_to_wall(row['local_time'])
        isdst = row['isdst'].strip()
        off = max(site.offsets) if isdst == '1' else min(site.offsets)
        raw = row['reading'].strip()
        out.append(_rec(row['run_tag'], wall - off, int(row['rev']),
                        row['flag'].strip() == 'x',
                        None if raw in ('', 'OVL') else raw,
                        'native', channel=row['chan']))
    return out


def parse_L04(text, site):
    out = []
    for line in text.split('\n'):
        if not line.strip():
            continue
        d = json.loads(line)
        raw = d['v']
        out.append(_rec(d['r'], d['t_ms'] // 1000, int(d['rv']),
                        bool(d['del']),
                        None if raw is None or str(raw).strip() == '' else str(raw),
                        _unit(d['u']), serial=d['s']))
    return out


def parse_L05(text, site):
    out = []
    for line in text.split('\n'):
        if not line.strip():
            continue
        d = json.loads(line)
        raw = d['value']['x']
        raw = None if raw is None else str(raw).strip()
        out.append(_rec(d['meta']['run'], iso_offset_to_epoch(d['at']),
                        int(d['meta']['rev']), str(d.get('void')) == '1',
                        None if raw in (None, '', 'ERR') else raw,
                        _unit(d['value']['unit']), serial=d['sensor']))
    return out


def parse_L06(text, site):
    out = []
    root = ET.fromstring(text)
    for batch in root.iter('batch'):
        run = batch.get('run')
        for r in batch.findall('r'):
            raw = (r.get('raw') or '').strip()
            out.append(_rec(run, iso_z_to_epoch(r.get('t')), int(r.get('rev')),
                            (r.get('void') or '').strip().lower() == 'true',
                            None if raw == '' else raw, _unit(r.get('u')),
                            serial=r.get('s')))
    return out


def parse_L07(path, site):
    con = sqlite3.connect(path)
    out = []
    for run, sensor, epoch, raw, unit, rev, voided in con.execute(
            'select run, sensor, epoch, raw, unit, rev, voided from readings'):
        t = None if raw is None or str(raw).strip() == '' else str(raw).strip()
        out.append(_rec(run, int(epoch), int(rev), int(voided or 0) == 1,
                        t, _unit(unit), serial=sensor))
    con.close()
    return out


def parse_L08(path, site):
    con = sqlite3.connect(path)
    frames = {}
    for fid, run, ms, rev, void in con.execute(
            'select frame_id, run, epoch_ms, rev, void from frames'):
        frames[fid] = (run, ms, rev, void)
    out = []
    for fid, channel, micro in con.execute(
            'select frame_id, channel, micro from samples order by rowid'):
        fr = frames.get(fid)
        if fr is None:
            continue
        run, ms, rev, void = fr
        out.append(_rec(run, ms // 1000, int(rev), int(void or 0) == 1,
                        None if micro is None else str(micro),
                        'micro', channel=channel))
    con.close()
    return out


def parse_L09(text, site):
    out = []
    for d in yaml_load(text):
        raw = d.get('raw')
        raw = None if raw is None else str(raw).strip()
        out.append(_rec(d['run'], int(d['at']), int(d['rev']),
                        str(d.get('void')).strip().lower() == 'yes',
                        None if raw in (None, '') else raw,
                        _unit(d['unit']), serial=d['sensor']))
    return out


def parse_L10(text, site):
    out = []
    data = yaml_load(text)
    for serial, block in data.items():
        unit = _unit(block['unit'])
        for s in block['samples']:
            parts = [p.strip() for p in str(s).split('|')]
            raw = parts[2]
            out.append(_rec(parts[0], iso_z_to_epoch(parts[1]), int(parts[3]),
                            parts[4] == '1',
                            None if raw in ('', '-') else raw,
                            unit, serial=serial))
    return out


def parse_L11(text, site):
    out = []
    d = json.loads(text)
    units = d['units']
    data = d['data']
    n = len(data['run'])
    for i in range(n):
        sensor = data['sensor'][i]
        raw = data['raw'][i]
        raw = None if raw is None else str(raw).strip()
        out.append(_rec(data['run'][i], iso_offset_to_epoch(data['t'][i]),
                        int(data['rev'][i]), bool(data['void'][i]),
                        None if raw in (None, '') else raw,
                        _unit(units.get(sensor)), serial=sensor))
    return out


L12_SUFFIX = {'R': 'ohm', 'K': 'kohm', 'V': 'V', 'M': 'mV'}


def parse_L12(text, site):
    out = []
    for line in text.split('\n'):
        if not line.strip() or line.startswith('#'):
            continue
        if line.startswith('RUN '):
            continue
        run = line[0:10].strip()
        sensor = line[10:21].strip()
        ts = line[21:38].strip()
        raw = line[38:53].strip()
        rev = line[53:57].strip()
        void = line[57:58].strip()
        inst = iso_z_to_epoch('%s-%s-%sT%s:%s:%sZ' % (
            ts[0:4], ts[4:6], ts[6:8], ts[9:11], ts[11:13], ts[13:15]))
        if raw == '*****' or raw == '':
            val, unit = None, None
        else:
            unit = L12_SUFFIX[raw[-1]]
            val = raw[:-1]
        out.append(_rec(run, inst, int(rev), void == 'Y', val, unit,
                        serial=sensor))
    return out


def parse_L13(text, site):
    out = []
    run = None
    for line in text.split('\n'):
        s = line.strip()
        if s.startswith('## Run'):
            run = s[len('## Run'):].strip()
            continue
        if not s.startswith('|'):
            continue
        cells = [c.strip() for c in s.strip('|').split('|')]
        if len(cells) < 6:
            continue
        if cells[0] == 'sensor' or set(cells[0]) <= set('-:'):
            continue
        raw = cells[2].replace(',', '')
        out.append(_rec(run, iso_z_to_epoch(cells[1]), int(cells[4]),
                        cells[5] == 'void',
                        None if cells[2] in ('', 'n/a') else raw,
                        _unit(cells[3]), serial=cells[0]))
    return out


def parse_L14(text, site):
    out = []
    for row in delim_rows(text, ';'):
        wall = _iso_to_wall(row['time_local'])
        isdst = row['isdst'].strip()
        off = max(site.offsets) if isdst == '1' else min(site.offsets)
        raw = row['value'].strip().replace(',', '.')
        out.append(_rec(row['run'], wall - off, int(row['rev']),
                        row['cancelled'].strip() == '1',
                        None if row['value'].strip() == '' else raw,
                        _unit(row['unit']), serial=row['probe']))
    return out


def parse_L15(text, site):
    out = []
    for row in tsv_rows(text):
        raw = row['val'].strip()
        out.append(_rec(row['run'], int(row['epoch_ms']) // 1000,
                        int(row['rev']), row['void'].strip() == '1',
                        None if raw in ('', 'NA') else raw,
                        _unit(row['unit']), channel=row['ch']))
    return out


def parse_L16(text, site):
    out = []
    for line in text.split('\n'):
        if not line.strip():
            continue
        d = json.loads(line)
        t0 = iso_z_to_epoch(d['t0'])
        unit = _unit(d['unit'])
        voids = set(d.get('void') or [])
        for i, dt in enumerate(d['dt']):
            raw = d['v'][i]
            raw = None if raw is None else str(raw).strip()
            out.append(_rec(d['run'], t0 + int(dt), int(d['rev']),
                            i in voids,
                            None if raw in (None, '') else raw,
                            unit, serial=d['sensor']))
    return out


TEXT_PARSERS = {
    'L01': parse_L01, 'L02': parse_L02, 'L03': parse_L03, 'L04': parse_L04,
    'L05': parse_L05, 'L06': parse_L06, 'L09': parse_L09, 'L10': parse_L10,
    'L11': parse_L11, 'L12': parse_L12, 'L13': parse_L13, 'L14': parse_L14,
    'L15': parse_L15, 'L16': parse_L16,
}
PATH_PARSERS = {'L07': parse_L07, 'L08': parse_L08}


def parse_shard(corpus, entry):
    layout = entry['layout']
    path = corpus.path(entry['file'])
    if layout in PATH_PARSERS:
        return PATH_PARSERS[layout](path, corpus.site)
    with open(path, 'r') as fh:
        return TEXT_PARSERS[layout](fh.read(), corpus.site)



# --------------------------------------------------------------------------
# calibration
# --------------------------------------------------------------------------

def raw_base(unit, text, family):
    v = Fraction(text)
    if unit == 'ohm' or unit == 'V' or unit == 'native':
        return v
    if unit == 'kohm':
        return v * 1000
    if unit == 'mV':
        return v / 1000
    if unit == 'micro':
        return v / 1000000
    raise ValueError('unit %r' % unit)


class Calibrator(object):
    def __init__(self, corpus):
        self.c = corpus
        self._tables = {}

    def _table(self, key, pts, family):
        tab = self._tables.get(key)
        if tab is not None:
            return tab
        xs = []
        raws = []
        temps = []
        for _pt, raw, unit, t_k in pts:
            r = raw_base(_unit(unit) or 'ohm', raw, family)
            raws.append(r)
            if family == 'NTC':
                xs.append(1 / r)
            else:
                xs.append(r)
            temps.append(Fraction(t_k))
        tab = (xs, raws, temps, min(raws), max(raws))
        self._tables[key] = tab
        return tab

    def version_for(self, serial, instant):
        best = None
        for start, ver, pts in self.c.cal.get(serial, []):
            if start <= instant:
                best = (start, ver, pts)
        return best

    def temperature(self, serial, instant, unit, raw_text):
        """Return (status, t_mK). status OK, NO_CALIBRATION or OUT_OF_RANGE."""
        inv = self.c.inventory[serial]
        family = inv['family']
        ver = self.version_for(serial, instant)
        if ver is not None:
            key = ('S', serial, ver[1])
            pts = ver[2]
        else:
            if inv['cal_policy'] != 'GENERIC_OK':
                return ('NO_CALIBRATION', None)
            curve = inv['generic_curve']
            pts = self.c.generic.get(curve)
            if not pts:
                return ('NO_CALIBRATION', None)
            key = ('G', curve, family)
        xs, raws, temps, lo, hi = self._table(key, pts, family)
        r = raw_base(unit, raw_text, family)
        if r < lo or r > hi:
            return ('OUT_OF_RANGE', None)
        x = 1 / r if family == 'NTC' else r
        for i in range(len(xs) - 1):
            x0 = xs[i]
            x1 = xs[i + 1]
            if (x0 <= x <= x1) or (x1 <= x <= x0):
                if x1 == x0:
                    t = temps[i]
                else:
                    t = temps[i] + (temps[i + 1] - temps[i]) * (x - x0) / (x1 - x0)
                return ('OK', rhe(t * 1000))
        return ('OUT_OF_RANGE', None)


# --------------------------------------------------------------------------
# reading pipeline
# --------------------------------------------------------------------------

EXCL_ORDER = ['UNMAPPED_CHANNEL', 'UNKNOWN_SENSOR', 'INVALID_VALUE',
              'OUT_OF_WINDOW', 'MAINTENANCE', 'EXCLUDED_SENSOR',
              'NO_CALIBRATION', 'OUT_OF_RANGE', 'SPIKE']


class Readings(object):
    def __init__(self, corpus):
        self.c = corpus
        self.cal = Calibrator(corpus)
        self.exclusions = {}
        self.shard_stats = []
        self.sensor_tokens = set()
        self._ingest()

    def _bump(self, run, serial, reason):
        key = (run, serial, reason)
        self.exclusions[key] = self.exclusions.get(key, 0) + 1

    def _reportable(self, run):
        c = self.c
        return run in c.run_profile and run not in c.aborted

    def _ingest(self):
        c = self.c
        shards = [s for s in c.catalog['shards']
                  if s.get('kind') == 'readings' and s.get('status') == 'ACTIVE']
        shards.sort(key=lambda s: s['order'])
        self.records_read = 0
        self.unresolved = 0
        keys = {}
        stats = []
        for si, entry in enumerate(shards):
            recs = parse_shard(c, entry)
            resolved = 0
            for index, rec in enumerate(recs):
                self.records_read += 1
                run = canon_run(rec['run'])
                if rec['serial'] is not None:
                    tok = canon_serial(rec['serial'])
                    self.sensor_tokens.add(tok)
                    final = c.resolve_serial_chain(tok)
                    if final not in c.inventory:
                        self.unresolved += 1
                        if self._reportable(run):
                            self._bump(run, tok, 'UNKNOWN_SENSOR')
                        continue
                else:
                    tok = canon_channel(rec['channel'])
                    serial = c.resolve_channel(tok, rec['instant'])
                    if serial is None:
                        self.unresolved += 1
                        if self._reportable(run):
                            self._bump(run, tok, 'UNMAPPED_CHANNEL')
                        continue
                    final = c.resolve_serial_chain(serial)
                    if final not in c.inventory:
                        self.unresolved += 1
                        if self._reportable(run):
                            self._bump(run, final, 'UNKNOWN_SENSOR')
                        continue
                resolved += 1
                key = (final, rec['instant'])
                cand = (rec['rev'], si, index)
                cur = keys.get(key)
                if cur is None or cand > cur[0]:
                    keys[key] = (cand, rec, run, final, si)
            stats.append({'file': entry['file'], 'layout': entry['layout'],
                          'records': len(recs), 'resolved': resolved,
                          'winning': 0})
        self.unique = []
        voided = 0
        for key, (cand, rec, run, final, si) in keys.items():
            if rec['void']:
                voided += 1
                continue
            stats[si]['winning'] += 1
            self.unique.append((run, final, rec))
        resolved_total = sum(s['resolved'] for s in stats)
        self.copies_superseded = resolved_total - len(keys)
        self.voided_keys = voided
        self.unique_readings = len(self.unique)
        self.shard_stats = stats
        self.out_of_scope = sum(1 for run, _f, _r in self.unique
                                if not self._reportable(run))

    # -- screens ---------------------------------------------------------
    def screen(self):
        c = self.c
        self.windows_by_sensor = {}
        self.sensor_rows = {}
        for run, final, rec in self.unique:
            if not self._reportable(run):
                continue
            win = c.windows.get(run)
            if win is None:
                continue
            stage = c.stage_of(final, win[0])
            if stage not in MEASURED:
                continue
            key = (run, final, stage)
            info = self.sensor_rows.setdefault(
                key, {'window': [], 'excluded': 0})
            reason = self._reason(c, run, final, stage, rec, win)
            if reason is not None:
                self._bump(run, final, reason)
                continue
            status, t = self.cal.temperature(final, rec['instant'],
                                             rec['unit'], rec['raw'])
            if status != 'OK':
                self._bump(run, final, status)
                continue
            off = (c.sensor_offsets.get(run) or {}).get(final)
            if off:
                t += off
            info['window'].append(t)

    def _reason(self, c, run, final, stage, rec, win):
        if rec['raw'] is None:
            return 'INVALID_VALUE'
        inst = rec['instant']
        if not (win[0] <= inst < win[1]):
            return 'OUT_OF_WINDOW'
        for block in c.calendar.get('maintenance') or []:
            s = iso_z_to_epoch(block['start_utc'])
            e = iso_z_to_epoch(block['end_utc'])
            if not (s <= inst < e):
                continue
            scope = str(block['scope']).strip()
            if scope == 'ALL':
                return 'MAINTENANCE'
            if c.resolve_node(scope) == stage:
                return 'MAINTENANCE'
        if final in (c.excluded_sensors.get(run) or set()):
            return 'EXCLUDED_SENSOR'
        return None

    # -- means -----------------------------------------------------------
    def means(self):
        c = self.c
        self.sensor_mean = {}
        self.rows = []
        for (run, final, stage), info in self.sensor_rows.items():
            vals = sorted(info['window'])
            n = len(vals)
            spike = c.setting(run, 'spike_mK')
            minr = c.setting(run, 'min_readings')
            if n:
                if n % 2:
                    med = Fraction(vals[n // 2])
                else:
                    med = Fraction(vals[n // 2 - 1] + vals[n // 2], 2)
                kept = [v for v in vals if abs(Fraction(v) - med) <= spike]
            else:
                kept = []
            dropped = n - len(kept)
            if dropped:
                key = (run, final, 'SPIKE')
                self.exclusions[key] = self.exclusions.get(key, 0) + dropped
            if not kept:
                status = 'NO_READINGS'
                mean = None
            elif len(kept) < minr:
                status = 'SPARSE'
                mean = None
            else:
                status = 'OK'
                mean = rhe(Fraction(sum(kept), len(kept)))
            self.rows.append({'run': run, 'serial': final, 'stage': stage,
                              'window': n, 'spikes': dropped,
                              'used': len(kept), 'mean': mean,
                              'status': status})
            if mean is not None:
                self.sensor_mean[(run, stage, final)] = mean

    # -- stage temperatures ----------------------------------------------
    def stages(self):
        c = self.c
        self.stage_rows = []
        self.stage_temp = {}
        for run in c.run_ids:
            if run in c.aborted:
                continue
            for stage in MEASURED:
                items = sorted((s, m) for (r, st, s), m
                               in self.sensor_mean.items()
                               if r == run and st == stage)
                if not items:
                    self.stage_rows.append(
                        {'run': run, 'stage': stage, 'used': [],
                         'dropped': [], 'temp': None, 'status': 'NO_SENSORS'})
                    continue
                vals = sorted(m for _s, m in items)
                n = len(vals)
                if n % 2:
                    med = Fraction(vals[n // 2])
                else:
                    med = Fraction(vals[n // 2 - 1] + vals[n // 2], 2)
                lim = c.setting(run, 'outlier_mK')
                used = [s for s, m in items if abs(Fraction(m) - med) <= lim]
                dropped = [s for s, m in items if abs(Fraction(m) - med) > lim]
                keep = [m for s, m in items if s in set(used)]
                temp = rhe(Fraction(sum(keep), len(keep)))
                self.stage_rows.append(
                    {'run': run, 'stage': stage, 'used': sorted(used),
                     'dropped': sorted(dropped), 'temp': temp,
                     'status': 'OK'})
                self.stage_temp[(run, stage)] = temp



# --------------------------------------------------------------------------
# links
# --------------------------------------------------------------------------

def parse_length(text, unit):
    v = Fraction(str(text).strip())
    u = (unit or 'mm').strip().lower()
    if u == 'mm':
        return v
    if u == 'cm':
        return v * 10
    if u == 'in':
        return v * Fraction(254, 10)
    raise ValueError('length unit %r' % unit)


def parse_area(spec, gauge):
    s = str(spec).strip()
    m = re.match(r'^A:\s*([\d.]+)\s*(mm2|cm2)$', s)
    if m:
        v = Fraction(m.group(1))
        return v if m.group(2) == 'mm2' else v * 100
    m = re.match(r'^R:\s*([\d.]+)\s*x\s*([\d.]+)\s*(mm|cm|in)$', s)
    if m:
        a = parse_length(m.group(1), m.group(3))
        b = parse_length(m.group(2), m.group(3))
        return a * b
    m = re.match(r'^W:\s*(\d+)\s*x\s*(\d+)\s*AWG$', s)
    if m:
        return int(m.group(1)) * gauge[m.group(2)]
    raise ValueError('area spec %r' % spec)


class LinkLibrary(object):
    def __init__(self, corpus):
        c = self.c = corpus
        self.link_tokens = set()
        self.material_tokens = set()
        self.node_tokens = set()
        byname = {}
        for s in corpus.catalog['shards']:
            if s.get('status') != 'ACTIVE':
                continue
            byname.setdefault(s['kind'], []).append(s)
        self.catalog_rows = {}
        for entry in sorted(byname.get('link_catalog', []),
                            key=lambda s: s['order']):
            for row in csv_rows(c._read(entry['file'])):
                self.link_tokens.add(row['link'].strip())
                lid = c.resolve_link(row['link'])
                self.catalog_rows.setdefault(lid, []).append(
                    (row['effective_from'].strip(), int(row['rev']),
                     row['status'].strip().upper()))
        self.segs = {}
        for entry in sorted(byname.get('segments', []), key=lambda s: s['order']):
            if entry['layout'] == 'S1':
                root = ET.fromstring(c._read(entry['file']))
                for link in root.findall('link'):
                    self.link_tokens.add(link.get('id').strip())
                    lid = c.resolve_link(link.get('id'))
                    rev = int(link.get('rev'))
                    for seg in link.findall('seg'):
                        mat = (seg.get('mat') or '').strip()
                        self.material_tokens.add(mat)
                        lot = (seg.get('lot') or '').strip()
                        self.segs.setdefault((lid, rev), {})[int(seg.get('n'))] = {
                            'material': mat,
                            'length': parse_length(
                                re.sub(r'[a-zA-Z]+$', '', seg.get('len')),
                                re.search(r'[a-zA-Z]+$', seg.get('len')).group(0)),
                            'area': (seg.get('area') or '').strip(),
                            'lot': '' if lot in ('', '-') else lot,
                        }
            else:
                for row in psv_rows(c._read(entry['file'])):
                    self.link_tokens.add(row['link'].strip())
                    lid = c.resolve_link(row['link'])
                    rev = int(row['rev'])
                    mat = row['material'].strip()
                    self.material_tokens.add(mat)
                    lot = row['lot'].strip()
                    self.segs.setdefault((lid, rev), {})[int(row['seq'])] = {
                        'material': mat,
                        'length': parse_length(row['length'], row['length_unit']),
                        'area': row['area_spec'].strip(),
                        'lot': '' if lot in ('', '-') else lot,
                    }
        self.joints = {}
        for entry in sorted(byname.get('joints', []), key=lambda s: s['order']):
            for line in c._read(entry['file']).split('\n'):
                if not line.strip():
                    continue
                d = json.loads(line)
                self.link_tokens.add(str(d['link']).strip())
                lid = c.resolve_link(d['link'])
                rev = int(d['rev'])
                self.joints.setdefault((lid, rev), {})[int(d['pos'])] = {
                    'class': str(d['class']).strip(),
                    'bolts': int(d['bolts']),
                    'torque': str(d['torque']).strip().upper(),
                    'indium': str(d['indium']).strip().lower() in ('true', 'yes'),
                }
        self.installs = {}
        for entry in sorted(byname.get('installs', []), key=lambda s: s['order']):
            for row in tsv_rows(c._read(entry['file'])):
                self.link_tokens.add(row['link'].strip())
                self.node_tokens.add(row['hot'].strip())
                self.node_tokens.add(row['cold'].strip())
                run = canon_run(row['run'])
                lid = c.resolve_link(row['link'])
                rev = int(row['rev'])
                key = (run, lid)
                cur = self.installs.get(key)
                if cur is None or rev >= cur[0]:
                    self.installs[key] = (rev, row)
        self.amendments = []
        for entry in sorted(byname.get('amendments', []),
                            key=lambda s: s['order']):
            for line in c._read(entry['file']).split('\n'):
                if not line.strip():
                    continue
                d = json.loads(line)
                self.link_tokens.add(str(d['link']).strip())
                self.amendments.append({
                    'seq': int(d['seq']),
                    'link': c.resolve_link(d['link']),
                    'rev': int(d['rev']),
                    'field': str(d['field']).strip(),
                    'value': d.get('value'),
                    'action': str(d['action']).strip().upper(),
                    'status': str(d['status']).strip().upper(),
                    'target': d.get('reverses'),
                })
        self.amendments.sort(key=lambda a: a['seq'])
        self._settle()

    def _settle(self):
        effect = {}
        for a in sorted(self.amendments, key=lambda x: -x['seq']):
            if a['status'] != 'POSTED':
                effect[a['seq']] = False
                continue
            killed = False
            for b in self.amendments:
                if (effect.get(b['seq']) and b['action'] == 'REVERSE'
                        and b['target'] is not None
                        and int(b['target']) == a['seq']):
                    killed = True
                    break
            effect[a['seq']] = not killed
        self.in_effect = effect
        self.overrides = {}
        for a in sorted(self.amendments, key=lambda x: x['seq']):
            if not effect.get(a['seq']) or a['action'] != 'SET':
                continue
            self.overrides[(a['link'], a['rev'], a['field'])] = a['value']

    def field(self, lid, rev, field, default):
        val = self.overrides.get((lid, rev, field))
        return default if val is None else val

    def revision(self, lid, date):
        best = None
        for eff, rev, status in self.catalog_rows.get(lid, []):
            if eff <= date:
                cand = (eff, rev)
                if best is None or cand > (best[0], best[1]):
                    best = (eff, rev, status)
        return best


class LinkGeometry(object):
    """Resolved geometry and joints of one (run, link) pair."""

    def __init__(self, ctx, run, lid, rev):
        c = ctx.c
        lib = ctx.lib
        self.segments = []
        raw = lib.segs.get((lid, rev), {})
        for seq in sorted(raw):
            s = raw[seq]
            mat_token = lib.field(lid, rev, 'seg%d.material' % seq, s['material'])
            length = Fraction(str(lib.field(lid, rev, 'seg%d.length_mm' % seq,
                                            s['length'])))
            area_spec = lib.field(lid, rev, 'seg%d.area' % seq, s['area'])
            code = c.resolve_material(mat_token)
            area = parse_area(area_spec, c.gauge)
            lot = s['lot']
            scale = Fraction(1)
            if lot:
                cert = c.lots.get(lot)
                if (cert and cert[0] == 'CERTIFIED'
                        and code in c.lot_materials):
                    scale = cert[1]
            self.segments.append({
                'seq': seq, 'material': code, 'material_token': mat_token,
                'length': length, 'area': area, 'lot': lot, 'scale': scale,
                'g': area / length,
            })
        self.joints = []
        rawj = lib.joints.get((lid, rev), {})
        for pos in sorted(rawj):
            j = rawj[pos]
            bolts = int(lib.field(lid, rev, 'joint%d.bolts' % pos, j['bolts']))
            torque = str(lib.field(lid, rev, 'joint%d.torque' % pos,
                                   j['torque'])).strip().upper()
            ind = lib.field(lid, rev, 'joint%d.indium' % pos, j['indium'])
            if isinstance(ind, str):
                indium = ind.strip().lower() in ('true', 'yes', '1')
            else:
                indium = bool(ind)
            self.joints.append({'pos': pos, 'class': j['class'], 'bolts': bolts,
                                'torque': torque, 'indium': indium})

    def finish(self, ctx, band):
        c = ctx.c
        self.band = band
        self.broken = any(s['material'] is None for s in self.segments)
        for j in self.joints:
            base = c.h_base.get((j['class'], band))
            if base is None:
                j['h_base'] = None
                j['h_eff'] = None
                self.broken = True
                continue
            h = base * j['bolts']
            if j['torque'] == 'LOW':
                h = h * c.low_torque_factor
            if j['indium'] and j['class'].startswith('BOLT_'):
                h = h * c.indium_factor
            j['h_base'] = base
            j['h_eff'] = rhe_step(h, c.h_increment)
        self.elements = []
        jmap = {j['pos']: j for j in self.joints}
        if 0 in jmap:
            self.elements.append(('joint', jmap[0]))
        for s in self.segments:
            self.elements.append(('segment', s))
            if s['seq'] in jmap:
                self.elements.append(('joint', jmap[s['seq']]))

    def march(self, cond, q, hot):
        t = hot
        out = []
        for kind, item in self.elements:
            if kind == 'segment':
                denom = item['scale'] * item['g']
                target = cond.theta(item['material'], t) - Fraction(q) / denom
                if target < 0:
                    return None
                t = cond.theta_inv_round(item['material'], target)
                if t is None or t < 0:
                    return None
                out.append(('segment', item['seq'], t))
            else:
                t = t - rhe(Fraction(q) / item['h_eff'])
                if t < 0:
                    return None
                out.append(('joint', item['pos'], t))
        return out

    def solve(self, cond, hot, cold):
        if not self.elements:
            return 0, []

        def ok(q):
            m = self.march(cond, q, hot)
            if m is None or m[-1][2] < cold:
                return None
            return m
        if ok(0) is None:
            return 0, self.march(cond, 0, hot) or []
        hi = 1
        while ok(hi) is not None:
            hi *= 2
        lo = hi // 2
        while lo + 1 < hi:
            mid = (lo + hi) // 2
            if ok(mid) is not None:
                lo = mid
            else:
                hi = mid
        return lo, ok(lo)



# --------------------------------------------------------------------------
# solver context
# --------------------------------------------------------------------------

BAND_OF_STAGE = {'ST50': 'W', 'ST4': 'C'}
MODEL_OF_COOLER = {'CC-0417': 'GM-K15', 'CC-0522': 'PT-K41'}
SEVERITY = ['PASS', 'MARGINAL', 'OVERLOAD', 'OVER_TEMP']


class Context(object):
    def __init__(self, corpus):
        self.c = corpus
        self.lib = LinkLibrary(corpus)
        self.readings = Readings(corpus)
        self.readings.screen()
        self.readings.means()
        self.readings.stages()
        self.stage_temp = self.readings.stage_temp
        self.links = {}
        self.intercepts = {}
        for run in corpus.run_ids:
            if run in corpus.aborted:
                continue
            self._prepare(run)
            self._intercepts(run)
            self._finish(run)
        self._loads()

    # -- per-run link set -------------------------------------------------
    def _prepare(self, run):
        c = self.c
        lib = self.lib
        date = c.run_date(run)
        rows = []
        for (r, lid), (_rev, row) in lib.installs.items():
            if r != run:
                continue
            if row['state'].strip().upper() != 'INSTALLED':
                continue
            hot = c.resolve_node(row['hot'])
            cold = c.resolve_node(row['cold'])
            info = {'run': run, 'link': lid, 'hot': hot, 'cold': cold,
                    'rev': None, 'status': None, 'geom': None, 'q': None,
                    'elements': []}
            rows.append(info)
            if lid in (c.excluded_links.get(run) or set()):
                info['status'] = 'EXCLUDED'
                rev = lib.revision(lid, date)
                info['rev'] = rev[1] if rev else None
                continue
            rev = lib.revision(lid, date)
            if rev is None or rev[2] == 'VOID':
                info['status'] = 'NO_GEOMETRY'
                info['rev'] = rev[1] if rev else None
                continue
            info['rev'] = rev[1]
            band = BAND_OF_STAGE.get(cold)
            if band is None:
                band = (c.intercepts.get((run, cold)) or {}).get('band')
            geom = LinkGeometry(self, run, lid, rev[1])
            geom.finish(self, band)
            info['geom'] = geom
        rows.sort(key=lambda x: x['link'])
        self.links[run] = rows

    def node_temp(self, run, node):
        if node in BAND_OF_STAGE or node == 'ST300':
            return self.stage_temp.get((run, node))
        sol = self.intercepts.get((run, node))
        if sol is None:
            return None
        return sol['temperature']

    # -- intercepts -------------------------------------------------------
    def _intercepts(self, run):
        c = self.c
        for (r, iid), meta in sorted(c.intercepts.items()):
            if r != run:
                continue
            attached = [i for i in self.links[run]
                        if i['geom'] is not None and not i['geom'].broken
                        and (i['hot'] == iid or i['cold'] == iid)]
            ins = [i for i in attached if i['cold'] == iid]
            outs = [i for i in attached if i['hot'] == iid]
            harness = (c.harness.get(run) or {}).get(iid, F0)
            sol = {'run': run, 'node': iid, 'band': meta['band'],
                   't_lo': None, 't_hi': None, 'temperature': None,
                   'harness': harness, 'residual': None, 'next': None,
                   'links_in': sorted(i['link'] for i in ins),
                   'links_out': sorted(i['link'] for i in outs),
                   'status': 'UNSOLVED'}
            self.intercepts[(run, iid)] = sol
            hot_temps = [self.stage_temp.get((run, i['hot'])) for i in ins]
            cold_temps = [self.stage_temp.get((run, i['cold'])) for i in outs]
            if (not ins or not outs or None in hot_temps
                    or None in cold_temps):
                continue
            t_lo = max(cold_temps)
            t_hi = min(hot_temps)
            sol['t_lo'] = t_lo
            sol['t_hi'] = t_hi
            if t_lo > t_hi:
                continue

            def f(t):
                total = harness
                for i in ins:
                    q, _ = i['geom'].solve(c.cond,
                                           self.stage_temp[(run, i['hot'])], t)
                    total += q
                for i in outs:
                    q, _ = i['geom'].solve(c.cond, t,
                                           self.stage_temp[(run, i['cold'])])
                    total -= q
                return total
            if f(t_hi) >= 0:
                temp, status = t_hi, 'CEILING'
            elif f(t_lo) < 0:
                temp, status = t_lo, 'FLOOR'
            else:
                lo, hi = t_lo, t_hi
                while lo + 1 < hi:
                    mid = (lo + hi) // 2
                    if f(mid) >= 0:
                        lo = mid
                    else:
                        hi = mid
                temp, status = lo, 'BALANCED'
            sol['temperature'] = temp
            sol['status'] = status
            sol['residual'] = f(temp)
            sol['next'] = None if temp == t_hi else f(temp + 1)

    # -- final link solve -------------------------------------------------
    def _finish(self, run):
        c = self.c
        for info in self.links[run]:
            hot = self.node_temp(run, info['hot'])
            cold = self.node_temp(run, info['cold'])
            info['hot_mK'] = hot
            info['cold_mK'] = cold
            if info['status'] in ('EXCLUDED', 'NO_GEOMETRY'):
                continue
            if hot is None or cold is None or info['geom'].broken:
                info['status'] = 'UNSOLVED'
                continue
            if hot <= cold:
                info['status'] = 'NO_GRADIENT'
                info['q'] = 0
                info['elements'] = info['geom'].march(c.cond, 0, hot) or []
                continue
            q, elements = info['geom'].solve(c.cond, hot, cold)
            info['status'] = 'OK'
            info['q'] = q
            info['elements'] = elements

    # -- loads and margins ------------------------------------------------
    def _loads(self):
        c = self.c
        self.load_rows = []
        self.margin_rows = []
        for run in c.run_ids:
            if run in c.aborted:
                continue
            for stage in ('ST50', 'ST4'):
                links = [i for i in self.links[run] if i['cold'] == stage]
                unsolved = any(i['status'] == 'UNSOLVED' for i in links)
                harness = (c.harness.get(run) or {}).get(stage, F0)
                cfg = c.configs.get(run)
                par = c.parasitic.get((cfg, stage))
                if unsolved or par is None:
                    links_uW = None
                    total = None
                    unsolved = True
                else:
                    links_uW = sum(i['q'] for i in links
                                   if i['q'] is not None)
                    total = links_uW + as_int(harness) + par
                self.load_rows.append(
                    {'run': run, 'stage': stage, 'links': links_uW,
                     'harness': as_int(harness), 'parasitic': par,
                     'total': total,
                     'status': 'INCOMPLETE' if unsolved else 'OK'})
                self.margin_rows.append(
                    self._margin(run, stage, total))

    def _margin(self, run, stage, load):
        c = self.c
        cooler = (c.run_profile.get(run) or {}).get('cooler')
        model = MODEL_OF_COOLER.get(cooler)
        temp = self.stage_temp.get((run, stage))
        derate = c.derate(cooler, c.run_date(run))
        row = {'run': run, 'name': stage, 'cooler': cooler, 'model': model,
               'temperature': temp, 'derate': derate, 'capacity': None,
               'map_status': None, 'load': load,
               'reserve_pct': c.reserve_pct(run, stage), 'reserve': None,
               'margin': None, 'verdict': 'INCOMPLETE'}
        if temp is not None and model is not None:
            pts = c.capmap.get((model, stage)) or []
            if pts:
                cap, in_map = interp_capacity(pts, temp)
                row['map_status'] = 'IN_MAP' if in_map else 'OUT_OF_MAP'
                row['capacity'] = rhe(cap * 1000000 * (100 - derate) / 100)
                row['reserve'] = rhe(Fraction(row['capacity'])
                                     * Fraction(row['reserve_pct']) / 100)
        if row['capacity'] is not None and load is not None:
            row['margin'] = row['capacity'] - load
            limit = c.limits.get(stage)
            if limit is not None and temp > limit:
                row['verdict'] = 'OVER_TEMP'
            elif row['margin'] < 0:
                row['verdict'] = 'OVERLOAD'
            elif row['margin'] < row['reserve']:
                row['verdict'] = 'MARGINAL'
            else:
                row['verdict'] = 'PASS'
        return row

    # -- verdicts ---------------------------------------------------------
    def run_verdicts(self):
        c = self.c
        margins = {}
        for row in self.margin_rows:
            margins[(row['run'], row['name'])] = row
        out = []
        for run in c.run_ids:
            if run in c.aborted:
                out.append({'run': run, 'verdict': 'ABORTED', 'ST50': None,
                            'ST4': None, 'unsolved_links': 0})
                continue
            unsolved = sum(1 for i in self.links[run]
                           if i['status'] == 'UNSOLVED')
            no_sensors = any(self.stage_temp.get((run, s)) is None
                             for s in MEASURED)
            v50 = margins[(run, 'ST50')]['verdict']
            v4 = margins[(run, 'ST4')]['verdict']
            if unsolved or no_sensors:
                verdict = 'INCOMPLETE'
            else:
                worst = max([v50, v4],
                            key=lambda v: SEVERITY.index(v)
                            if v in SEVERITY else len(SEVERITY))
                verdict = worst
            out.append({'run': run, 'verdict': verdict, 'ST50': v50,
                        'ST4': v4, 'unsolved_links': unsolved})
        return out


def interp_capacity(pts, t_mK):
    if t_mK <= pts[0][0]:
        return pts[0][1], t_mK == pts[0][0]
    if t_mK >= pts[-1][0]:
        return pts[-1][1], t_mK == pts[-1][0]
    lo, hi = 0, len(pts) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if pts[mid][0] <= t_mK:
            lo = mid
        else:
            hi = mid
    t0, c0 = pts[lo]
    t1, c1 = pts[hi]
    return c0 + (c1 - c0) * Fraction(t_mK - t0, t1 - t0), True



# --------------------------------------------------------------------------
# report writing
# --------------------------------------------------------------------------

REPORTS = [
    'sensor_means.tsv', 'stage_temperatures.csv', 'intercept_solutions.json',
    'link_heat_flows.psv', 'junction_profiles.jsonl', 'link_geometry.csv',
    'joint_conductances.tsv', 'stage_loads.csv', 'cooler_margins.xml',
    'run_verdicts.json', 'alias_resolution.csv', 'reading_exclusions.jsonl',
    'dedup_report.json', 'source_lineage.json', 'amendment_ledger.csv',
    'parameters_used.yaml', 'authority_audit.csv', 'variance_vs_published.csv',
    'reconciliation.md', 'budget_summary.md',
]


def cell(value, delim):
    if value is None:
        return ''
    s = str(value)
    if delim in s or '"' in s or '\n' in s:
        return '"' + s.replace('"', '""') + '"'
    return s


def table(header, rows, delim):
    out = [delim.join(header)]
    for row in rows:
        out.append(delim.join(cell(v, delim) for v in row))
    return '\n'.join(out) + '\n'


def as_int(x):
    if isinstance(x, Fraction):
        return x.numerator if x.denominator == 1 else rhe(x)
    return int(x)


class Writer(object):
    def __init__(self, ctx, out_dir):
        self.ctx = ctx
        self.c = ctx.c
        self.out = out_dir
        self.run_index = {r: i for i, r in enumerate(self.c.run_ids)}
        self.files = []

    def emit(self, name, text):
        path = os.path.join(self.out, name)
        data = text.encode('utf-8')
        with open(path, 'wb') as fh:
            fh.write(data)
        self.files.append({'name': name, 'bytes': len(data),
                           'sha256': hashlib.sha256(data).hexdigest()})

    def rkey(self, run):
        return self.run_index.get(run, len(self.run_index))

    # ------------------------------------------------------------------
    def write_all(self):
        self.sensor_means()
        self.stage_temperatures()
        self.intercept_solutions()
        self.link_heat_flows()
        self.junction_profiles()
        self.link_geometry()
        self.joint_conductances()
        self.stage_loads()
        self.cooler_margins()
        self.run_verdicts()
        self.alias_resolution()
        self.reading_exclusions()
        self.dedup_report()
        self.source_lineage()
        self.amendment_ledger()
        self.parameters_used()
        self.authority_audit()
        self.variance_vs_published()
        self.reconciliation()
        self.budget_summary()
        self.manifest()

    def sensor_means(self):
        rows = sorted(self.ctx.readings.rows,
                      key=lambda r: (self.rkey(r['run']),
                                     MEASURED.index(r['stage']), r['serial']))
        body = [[r['run'], r['serial'], r['stage'], r['window'], r['spikes'],
                 r['used'], '' if r['mean'] is None else r['mean'],
                 r['status']] for r in rows]
        self.emit('sensor_means.tsv', table(
            ['run', 'serial', 'stage', 'window_readings', 'spikes_dropped',
             'used_readings', 'mean_mK', 'status'], body, '\t'))

    def stage_temperatures(self):
        rows = sorted(self.ctx.readings.stage_rows,
                      key=lambda r: (self.rkey(r['run']),
                                     MEASURED.index(r['stage'])))
        body = [[r['run'], r['stage'], ';'.join(r['used']),
                 ';'.join(r['dropped']),
                 '' if r['temp'] is None else r['temp'], r['status']]
                for r in rows]
        self.emit('stage_temperatures.csv', table(
            ['run', 'stage', 'sensors_used', 'sensors_dropped',
             'temperature_mK', 'status'], body, ','))

    def intercept_solutions(self):
        items = []
        for (run, node), sol in sorted(
                self.ctx.intercepts.items(),
                key=lambda kv: (self.rkey(kv[0][0]), kv[0][1])):
            unsolved = sol['status'] == 'UNSOLVED'
            obj = {}
            obj['run'] = run
            obj['node'] = node
            obj['band'] = sol['band']
            obj['t_lo_mK'] = None if unsolved else sol['t_lo']
            obj['t_hi_mK'] = None if unsolved else sol['t_hi']
            obj['temperature_mK'] = None if unsolved else sol['temperature']
            obj['harness_uW'] = as_int(sol['harness'])
            obj['residual_uW'] = (None if unsolved
                                  else as_int(sol['residual']))
            obj['next_residual_uW'] = (None if unsolved or sol['next'] is None
                                       else as_int(sol['next']))
            obj['links_in'] = sol['links_in']
            obj['links_out'] = sol['links_out']
            obj['status'] = sol['status']
            items.append(obj)
        doc = {'count': len(items), 'intercepts': items}
        self.emit('intercept_solutions.json', json.dumps(doc) + '\n')

    def _link_rows(self):
        out = []
        for run in self.c.run_ids:
            for info in self.ctx.links.get(run, []):
                out.append(info)
        out.sort(key=lambda i: (self.rkey(i['run']), i['link']))
        return out

    def link_heat_flows(self):
        body = []
        for i in self._link_rows():
            q = i['q'] if i['status'] in ('OK', 'NO_GRADIENT') else None
            body.append([i['run'], i['link'],
                         '' if i['rev'] is None else i['rev'],
                         i['hot'], i['cold'],
                         '' if i.get('hot_mK') is None else i['hot_mK'],
                         '' if i.get('cold_mK') is None else i['cold_mK'],
                         '' if q is None else q, i['status']])
        self.emit('link_heat_flows.psv', table(
            ['run', 'link', 'rev', 'hot_node', 'cold_node', 'hot_mK',
             'cold_mK', 'q_uW', 'status'], body, '|'))

    def junction_profiles(self):
        lines = []
        for i in self._link_rows():
            if i['status'] not in ('OK', 'NO_GRADIENT'):
                continue
            elements = []
            for kind, idx, t in i['elements']:
                if kind == 'joint':
                    elements.append({'kind': 'joint', 'pos': idx, 't_mK': t})
                else:
                    elements.append({'kind': 'segment', 'seq': idx, 't_mK': t})
            obj = {'elements': elements, 'link': i['link'], 'q_uW': i['q'],
                   'run': i['run']}
            lines.append(json.dumps(obj, sort_keys=True))
        self.emit('junction_profiles.jsonl',
                  ''.join(l + '\n' for l in lines))

    def link_geometry(self):
        body = []
        for i in self._link_rows():
            if i['status'] not in ('OK', 'NO_GRADIENT', 'UNSOLVED'):
                continue
            for s in i['geom'].segments:
                body.append([i['run'], i['link'], i['rev'], s['seq'],
                             s['material'], frac_str(s['length']),
                             frac_str(s['area']), s['lot'],
                             frac_str(s['scale']),
                             fmt_places(s['g'], 9)])
        self.emit('link_geometry.csv', table(
            ['run', 'link', 'rev', 'seq', 'material', 'length_mm', 'area_mm2',
             'lot', 'lot_scale', 'g_mm'], body, ','))

    def joint_conductances(self):
        body = []
        for i in self._link_rows():
            if i['status'] not in ('OK', 'NO_GRADIENT', 'UNSOLVED'):
                continue
            for j in i['geom'].joints:
                body.append([i['run'], i['link'], j['pos'], j['class'],
                             i['geom'].band, j['bolts'], j['torque'],
                             'Y' if j['indium'] else 'N',
                             frac_str(j['h_base']), frac_str(j['h_eff'])])
        self.emit('joint_conductances.tsv', table(
            ['run', 'link', 'pos', 'class', 'band', 'bolts', 'torque',
             'indium', 'h_base_mW_per_K', 'h_eff_mW_per_K'], body, '\t'))

    def stage_loads(self):
        body = []
        for r in self.ctx.load_rows:
            body.append([r['run'], r['stage'],
                         '' if r['links'] is None else r['links'],
                         r['harness'], r['parasitic'],
                         '' if r['total'] is None else r['total'],
                         r['status']])
        self.emit('stage_loads.csv', table(
            ['run', 'stage', 'links_uW', 'harness_uW', 'parasitic_uW',
             'total_uW', 'status'], body, ','))

    def cooler_margins(self):
        lines = ['<?xml version="1.0" encoding="UTF-8"?>',
                 '<margins campaign="%s">' % xml_attr(self.c.profile['campaign'])]
        for r in self.ctx.margin_rows:
            attrs = [
                ('run', r['run']),
                ('name', r['name']),
                ('cooler', r['cooler']),
                ('model', r['model'] or ''),
                ('temperature_mK', '' if r['temperature'] is None
                 else r['temperature']),
                ('derate_pct', frac_str(r['derate'])),
                ('capacity_uW', '' if r['capacity'] is None else r['capacity']),
                ('map_status', r['map_status'] or ''),
                ('load_uW', '' if r['load'] is None else r['load']),
                ('reserve_pct', r['reserve_pct']),
                ('reserve_uW', '' if r['reserve'] is None else r['reserve']),
                ('margin_uW', '' if r['margin'] is None else r['margin']),
                ('verdict', r['verdict']),
            ]
            text = ' '.join('%s="%s"' % (k, xml_attr(v)) for k, v in attrs)
            lines.append('  <stage %s/>' % text)
        lines.append('</margins>')
        self.emit('cooler_margins.xml', '\n'.join(lines) + '\n')

    def run_verdicts(self):
        runs = self.ctx.run_verdicts()
        out = []
        summary = {}
        for r in runs:
            out.append({'run': r['run'], 'verdict': r['verdict'],
                        'ST50': r['ST50'], 'ST4': r['ST4'],
                        'unsolved_links': r['unsolved_links']})
            summary[r['verdict']] = summary.get(r['verdict'], 0) + 1
        doc = {'campaign': self.c.profile['campaign'], 'runs': out,
               'summary': {k: summary[k] for k in sorted(summary)}}
        self.emit('run_verdicts.json', json.dumps(doc) + '\n')

    def alias_resolution(self):
        c = self.c
        lib = self.ctx.lib
        rows = []
        for token in sorted(lib.link_tokens):
            rows.append(('link', token, c.resolve_link(token) or 'UNRESOLVED'))
        for token in sorted(lib.material_tokens):
            rows.append(('material', token,
                         c.resolve_material(token) or 'UNRESOLVED'))
        nodes = set(lib.node_tokens)
        for hist in c.sensor_stages.values():
            for _ts, stage in hist:
                nodes.add(str(stage).strip())
        for node in c.bundle_nodes.values():
            nodes.add(str(node).strip())
        for token in sorted(nodes):
            rows.append(('node', token, c.resolve_node(token) or 'UNRESOLVED'))
        for token in sorted(self.ctx.readings.sensor_tokens):
            rows.append(('sensor', token, c.resolve_serial_chain(token)))
        rows.sort(key=lambda r: (r[0], r[1]))
        self.emit('alias_resolution.csv', table(
            ['kind', 'token', 'resolved'], rows, ','))

    def reading_exclusions(self):
        items = sorted(self.ctx.readings.exclusions.items(),
                       key=lambda kv: (self.rkey(kv[0][0]), kv[0][1], kv[0][2]))
        lines = []
        for (run, serial, reason), count in items:
            if not count:
                continue
            lines.append(json.dumps({'count': count, 'reason': reason,
                                     'run': run, 'serial': serial},
                                    sort_keys=True))
        self.emit('reading_exclusions.jsonl',
                  ''.join(l + '\n' for l in lines))

    def dedup_report(self):
        rd = self.ctx.readings
        doc = {'records_read': rd.records_read, 'unresolved': rd.unresolved,
               'copies_superseded': rd.copies_superseded,
               'voided_keys': rd.voided_keys,
               'unique_readings': rd.unique_readings,
               'out_of_scope_readings': rd.out_of_scope}
        self.emit('dedup_report.json', json.dumps(doc) + '\n')

    def source_lineage(self):
        doc = {'shards': [{'file': s['file'], 'layout': s['layout'],
                           'records': s['records'], 'resolved': s['resolved'],
                           'winning': s['winning']}
                          for s in self.ctx.readings.shard_stats]}
        self.emit('source_lineage.json', json.dumps(doc) + '\n')

    def amendment_ledger(self):
        rows = []
        for a in sorted(self.ctx.lib.amendments, key=lambda x: x['seq']):
            rows.append([a['seq'], a['link'], a['rev'], a['field'],
                         a['action'], a['status'],
                         'Y' if self.ctx.lib.in_effect.get(a['seq']) else 'N'])
        self.emit('amendment_ledger.csv', table(
            ['seq', 'link', 'rev', 'field', 'action', 'status', 'in_effect'],
            rows, ','))

    def parameters_used(self):
        c = self.c
        lines = []
        lines.append('campaign: %s' % c.profile['campaign'])
        lines.append('profile_revision: %s' % c.profile['profile_revision'])
        lines.append('overlay_applied: %s'
                     % ('true' if c.overlay_applied else 'false'))
        lines.append('sheets:')
        lines.append('  conductivity: %s' % c.profile['conductivity_sheet'])
        lines.append('  calibration: %s' % c.profile['calibration_sheet'])
        lines.append('  capacity: %s' % c.profile['capacity_sheet'])
        lines.append('memo_tables:')
        lines.append('  joint: %s' % c.tbl_joint_label)
        lines.append('  parasitic: %s' % c.tbl_par_label)
        lines.append('  solver: %s' % c.tbl_solver_label)
        lines.append('  gauge: %s' % c.tbl_gauge_label)
        lines.append('  limits: %s' % c.tbl_limit_label)
        lines.append('constants:')
        lines.append("  h_increment_mW_per_K: '%s'"
                     % c.solver['h_increment_mW_per_K'])
        lines.append("  indium_factor: '%s'" % c.solver['indium_factor'])
        lines.append("  low_torque_factor: '%s'"
                     % c.solver['low_torque_factor'])
        lines.append("  lot_scale_materials: '%s'"
                     % c.solver['lot_scale_materials'])
        lines.append('limits_mK:')
        lines.append('  ST50: %s' % c.limits['ST50'])
        lines.append('  ST4: %s' % c.limits['ST4'])
        lines.append('runs:')
        for run in c.run_ids:
            if run in c.aborted:
                continue
            cooler = (c.run_profile.get(run) or {}).get('cooler', '')
            lines.append('  %s:' % run)
            lines.append('    spike_mK: %s' % c.setting(run, 'spike_mK'))
            lines.append('    outlier_mK: %s' % c.setting(run, 'outlier_mK'))
            lines.append('    min_readings: %s' % c.setting(run, 'min_readings'))
            lines.append('    reserve_pct_ST50: %s' % c.reserve_pct(run, 'ST50'))
            lines.append('    reserve_pct_ST4: %s' % c.reserve_pct(run, 'ST4'))
            lines.append('    shield: %s' % c.configs.get(run, ''))
            lines.append('    cooler: %s' % cooler)
            lines.append("    derate_pct: '%s'"
                         % frac_str(c.derate(cooler, c.run_date(run))))
        self.emit('parameters_used.yaml', '\n'.join(lines) + '\n')

    def authority_audit(self):
        rows = audit_rows(self.ctx)
        rows.sort(key=lambda r: (r[0], r[1]))
        self.emit('authority_audit.csv', table(
            ['source', 'item', 'quoted', 'in_force', 'verdict'], rows, ','))

    def variance_vs_published(self):
        c = self.c
        published = {}
        for row in csv_rows(c._read('heatload_budget_published.csv')):
            run = canon_run(row['run'])
            link = c.resolve_link(row['link'])
            published[(run, link)] = as_int(Fraction(row['q_mW'].strip()) * 1000)
        recomputed = {}
        for i in self._link_rows():
            if i['status'] in ('OK', 'NO_GRADIENT'):
                recomputed[(i['run'], i['link'])] = i['q']
        keys = sorted(set(published) | set(recomputed),
                      key=lambda k: (self.rkey(k[0]), k[1]))
        body = []
        for key in keys:
            p = published.get(key)
            r = recomputed.get(key)
            if p is None:
                status = 'MISSING_PUBLISHED'
                delta = ''
            elif r is None:
                status = 'MISSING_RECOMPUTED'
                delta = ''
            else:
                delta = r - p
                status = 'MATCH' if delta == 0 else 'DIFFERENT'
            body.append([key[0], key[1], '' if p is None else p,
                         '' if r is None else r, delta, status])
        self.emit('variance_vs_published.csv', table(
            ['run', 'link', 'published_uW', 'recomputed_uW', 'delta_uW',
             'status'], body, ','))

    def reconciliation(self):
        c = self.c
        doc = json.loads(c._read('stage_margins_published.json'))
        verdicts = {}
        for row in self.ctx.margin_rows:
            verdicts[(row['run'], row['name'])] = row['verdict']
        items = []
        for s in doc['stages']:
            run = canon_run(s['run'])
            items.append((run, s['stage'].strip(), s['verdict'].strip()))
        items.sort(key=lambda t: (self.rkey(t[0]),
                                 MEASURED.index(t[1])
                                 if t[1] in MEASURED else len(MEASURED)))
        lines = ['# Reconciliation with the published stage margins', '',
                 '| run | stage | published_verdict | recomputed_verdict'
                 ' | change |', '|---|---|---|---|---|']
        changed = 0
        for run, stage, pub in items:
            if run in c.aborted:
                rec = 'ABORTED'
            else:
                rec = verdicts.get((run, stage), '')
            same = 'same' if rec == pub else 'changed'
            if rec != pub:
                changed += 1
            lines.append('| %s | %s | %s | %s | %s |'
                         % (run, stage, pub, rec, same))
        lines.append('')
        lines.append('Changed verdicts: %d of %d.' % (changed, len(items)))
        self.emit('reconciliation.md', '\n'.join(lines) + '\n')

    def budget_summary(self):
        c = self.c
        verdicts = {r['run']: r for r in self.ctx.run_verdicts()}
        loads = {}
        for r in self.ctx.load_rows:
            loads[(r['run'], r['stage'])] = r
        margins = {}
        for r in self.ctx.margin_rows:
            margins[(r['run'], r['name'])] = r
        lines = ['# Heat-load budget summary', '',
                 '| run | verdict | ST50_load_uW | ST50_margin_uW |'
                 ' ST4_load_uW | ST4_margin_uW |',
                 '|---|---|---|---|---|---|']
        passing = 0
        for run in c.run_ids:
            v = verdicts[run]['verdict']
            if v == 'PASS':
                passing += 1
            cells = [run, v]
            for stage in ('ST50', 'ST4'):
                load = loads.get((run, stage))
                marg = margins.get((run, stage))
                cells.append('' if load is None or load['total'] is None
                             else str(load['total']))
                cells.append('' if marg is None or marg['margin'] is None
                             else str(marg['margin']))
            lines.append('| ' + ' | '.join(cells) + ' |')
        lines.append('')
        lines.append('Runs passing: %d of %d.' % (passing, len(c.run_ids)))
        self.emit('budget_summary.md', '\n'.join(lines) + '\n')

    def manifest(self):
        order = {name: i for i, name in enumerate(REPORTS)}
        files = sorted(self.files, key=lambda f: order[f['name']])
        doc = {'files': files}
        path = os.path.join(self.out, 'manifest.json')
        with open(path, 'wb') as fh:
            fh.write((json.dumps(doc) + '\n').encode('utf-8'))


def xml_attr(value):
    s = '' if value is None else str(value)
    return (s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            .replace('"', '&quot;'))


# --------------------------------------------------------------------------
# authority audit
# --------------------------------------------------------------------------

def _constant_in_force(c, key):
    """Governing value of a printed constant key, or None."""
    m = re.match(r'^JOINT\s+(\S+)/(\S+)$', key)
    if m:
        return c.h_base.get((m.group(1), m.group(2)))
    m = re.match(r'^AWG\s+(\S+)$', key)
    if m:
        return c.gauge.get(m.group(1))
    m = re.match(r'^PARASITIC\s+(\S+)/(\S+)$', key)
    if m:
        v = c.parasitic.get((m.group(1), m.group(2)))
        return None if v is None else Fraction(v)
    m = re.match(r'^FACTOR\s+(\S+)$', key)
    if m:
        v = c.solver.get(m.group(1))
        if v is None:
            return None
        try:
            return Fraction(v)
        except ValueError:
            return None
    return None


def _audit_value(quoted, value):
    if value is None:
        return ('', 'DISAGREE')
    text = fmt_places(value, dec_places(quoted))
    return (text, 'AGREE' if text == quoted.strip() else 'DISAGREE')


def _constant_rows(c, source, pairs):
    rows = []
    for key, quoted in pairs:
        value = _constant_in_force(c, key)
        text, verdict = _audit_value(quoted, value)
        rows.append((source, key, quoted, text, verdict))
    return rows


def _md_constants(text):
    pairs = []
    for line in text.split('\n'):
        s = line.strip()
        if not s.startswith('|'):
            continue
        cells = [x.strip() for x in s.strip('|').split('|')]
        if len(cells) != 2:
            continue
        if cells[0] == 'key' or set(cells[0]) <= set('-:'):
            continue
        pairs.append((cells[0], cells[1]))
    return pairs


def audit_rows(ctx):
    c = ctx.c
    rows = []
    rows.extend(_constant_rows(
        c, 'budget_solve_pack.md',
        _md_constants(c._read('budget_solve_pack.md'))))
    rows.extend(_constant_rows(
        c, c.names['draft'],
        _md_constants(c._read(c.names['draft']))))
    pairs = []
    for line in c._read(c.names['bulletin']).split('\n'):
        m = re.match(r'^NOTICE\s+\S+\s*\|\s*(.*?)\s*\|\s*(.*?)\s*$', line)
        if m:
            pairs.append((m.group(1), m.group(2)))
    rows.extend(_constant_rows(c, c.names['bulletin'], pairs))

    def cond_row(source, token, t_k, quoted):
        code = c.resolve_material(token)
        item = '%s@%s' % (code if code else token, t_k)
        if code is None:
            rows.append((source, item, quoted, '', 'DISAGREE'))
            return
        t_mK = rhe(Fraction(t_k) * 1000)
        value = c.cond.k(code, t_mK)
        text, verdict = _audit_value(quoted, value)
        rows.append((source, item, quoted, text, verdict))

    for line in c._read('conductivity_cache.jsonl').split('\n'):
        if not line.strip():
            continue
        d = json.loads(line)
        cond_row('conductivity_cache.jsonl', d['mat'], d['T_K'],
                 str(d['k_W_per_mK']))
    for line in c._read(c.names['quick_reference']).split('\n'):
        m = re.match(r'^(\S+)\s+([\d.]+)\s+([\d.]+)\s*$', line)
        if m and not line.startswith('material'):
            cond_row(c.names['quick_reference'], m.group(1), m.group(2),
                     m.group(3))
    legacy = yaml_load(c._read('materials_legacy.yaml'))
    for mat, pts in (legacy.get('materials') or {}).items():
        for pt in pts:
            cond_row('materials_legacy.yaml', mat, str(pt['T_K']),
                     str(pt['k']))

    for row in csv_rows(c._read('daq_dashboard_export.csv')):
        if row['sensor'].strip() != 'ALL':
            continue
        run = canon_run(row['run'])
        stage = row['stage'].strip()
        quoted = row['live_K'].strip()
        temp = ctx.stage_temp.get((run, stage))
        if temp is None:
            rows.append(('daq_dashboard_export.csv', '%s/%s' % (run, stage),
                         quoted, '', 'DISAGREE'))
        else:
            text, verdict = _audit_value(quoted, Fraction(temp, 1000))
            rows.append(('daq_dashboard_export.csv', '%s/%s' % (run, stage),
                         quoted, text, verdict))

    keys = ('spike_mK', 'outlier_mK', 'min_readings', 'reserve_pct_ST50',
            'reserve_pct_ST4')
    for name in sorted(os.listdir(c.dir)):
        if not re.match(r'profile_overlay_.*\.ya?ml$', name):
            continue
        if name == getattr(c, 'overlay_name', None):
            continue
        data = yaml_load(c._read(name))
        for run, settings in (data.get('runs') or {}).items():
            run_id = canon_run(run)
            if run_id not in c.run_profile:
                continue
            for key in keys:
                if key not in (settings or {}):
                    continue
                quoted = str(settings[key])
                if key.startswith('reserve_pct_'):
                    value = Fraction(c.reserve_pct(run_id, key[12:]))
                else:
                    value = Fraction(c.setting(run_id, key))
                text, verdict = _audit_value(quoted, value)
                rows.append((name, '%s/%s' % (run_id, key), quoted, text,
                             verdict))
    return rows


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: run_budget.py DATA_DIR OUT_DIR\n')
        return 2
    data_dir, out_dir = argv[1], argv[2]
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    corpus = Corpus(data_dir)
    ctx = Context(corpus)
    Writer(ctx, out_dir).write_all()
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))

