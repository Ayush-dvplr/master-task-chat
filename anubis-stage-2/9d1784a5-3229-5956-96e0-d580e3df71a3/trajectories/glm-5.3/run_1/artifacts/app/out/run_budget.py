#!/usr/bin/env python3
"""Recompute the KTC-26B heat-load budget from the raw DAQ corpus.

Usage: python3 run_budget.py DATA_DIR OUT_DIR

Implements the thermal budget handbook (revision 9) and the output contract.
Standard library only.
"""

import csv
import hashlib
import json
import os
import re
import sqlite3
import sys
import zlib
import xml.etree.ElementTree as ET
from fractions import Fraction

MEASURED_STAGES = ['ST300', 'ST50', 'ST4']
LOAD_STAGES = ['ST50', 'ST4']

REPORTS = [
    'sensor_means.tsv', 'stage_temperatures.csv', 'intercept_solutions.json',
    'link_heat_flows.psv', 'junction_profiles.jsonl', 'link_geometry.csv',
    'joint_conductances.tsv', 'stage_loads.csv', 'cooler_margins.xml',
    'run_verdicts.json', 'alias_resolution.csv', 'reading_exclusions.jsonl',
    'dedup_report.json', 'source_lineage.json', 'amendment_ledger.csv',
    'parameters_used.yaml', 'authority_audit.csv', 'variance_vs_published.csv',
    'reconciliation.md', 'budget_summary.md', 'manifest.json',
]
REPORT_ORDER = REPORTS[:-1]


# --------------------------------------------------------------------------
# exact arithmetic helpers
# --------------------------------------------------------------------------

def frac(s):
    """Exact Fraction from a decimal/integer string (no binary floats)."""
    s = str(s).strip()
    if s == '':
        return None
    return Fraction(s)


def rhe(fr, places=0):
    """Round a Fraction half-even to `places` decimals; returns Fraction."""
    scale = 10 ** places
    x = fr * scale
    n, d = x.numerator, x.denominator
    q, r = divmod(n, d)
    if 2 * r > d:
        q += 1
    elif 2 * r == d and (q % 2) != 0:
        q += 1
    return Fraction(q, scale)


def rhe_int(fr):
    return rhe(fr, 0).numerator


def fmt(fr, places):
    """Format a Fraction with exactly `places` decimals, half-even."""
    if fr is None:
        return ''
    scale = 10 ** places
    x = fr * scale
    n, d = x.numerator, x.denominator
    q, r = divmod(n, d)
    if 2 * r > d:
        q += 1
    elif 2 * r == d and (q % 2) != 0:
        q += 1
    neg = q < 0
    q = abs(q)
    if places == 0:
        body = str(q)
    else:
        i, f = divmod(q, scale)
        body = '%d.%0*d' % (i, places, f)
    return ('-' + body) if neg else body


def trimz(s):
    """Trim trailing zeros of a decimal string ('1.50'->'1.5', '2.0'->'2')."""
    if s == '':
        return s
    if '.' in s:
        s = s.rstrip('0').rstrip('.')
    if s in ('-0', ''):
        s = '0'
    return s


def dec_trim(fr, places=12):
    """Exact decimal string of a Fraction, trailing zeros trimmed."""
    if fr is None:
        return ''
    return trimz(fmt(fr, places))


# --------------------------------------------------------------------------
# YAML subset parser
# --------------------------------------------------------------------------

def _yaml_scalar(tok):
    tok = tok.strip()
    if tok == '':
        return None
    if len(tok) >= 2 and tok[0] == "'" and tok[-1] == "'":
        return tok[1:-1].replace("''", "'")
    if len(tok) >= 2 and tok[0] == '"' and tok[-1] == '"':
        return tok[1:-1]
    if tok in ('null', '~'):
        return None
    if re.match(r'^[-+]?\d+$', tok):
        return int(tok)
    return tok


def _split_flow(body):
    parts, depth, cur, instr = [], 0, '', None
    for ch in body:
        if instr:
            cur += ch
            if ch == instr:
                instr = None
            continue
        if ch in ('"', "'"):
            instr = ch
            cur += ch
        elif ch in '{[':
            depth += 1
            cur += ch
        elif ch in '}]':
            depth -= 1
            cur += ch
        elif ch == ',' and depth == 0:
            parts.append(cur)
            cur = ''
        else:
            cur += ch
    if cur.strip():
        parts.append(cur)
    return parts


def _yaml_flow(text):
    text = text.strip()
    if text.startswith('{') and text.endswith('}'):
        out = {}
        body = text[1:-1].strip()
        if not body:
            return out
        for p in _split_flow(body):
            k, _, v = p.partition(':')
            v = v.strip()
            out[_yaml_scalar(k)] = _yaml_flow(v) if v.startswith(('{', '[')) else _yaml_scalar(v)
        return out
    if text.startswith('[') and text.endswith(']'):
        body = text[1:-1].strip()
        if not body:
            return []
        return [_yaml_flow(p) for p in _split_flow(body)]
    return _yaml_scalar(text)


class _YLines(object):
    def __init__(self, text):
        self.items = []
        for raw in text.split('\n'):
            line = raw.rstrip()
            if line.strip() == '' or line.lstrip().startswith('#'):
                continue
            self.items.append(line)

    def ind(self, i):
        s = self.items[i]
        return len(s) - len(s.lstrip())


def _yaml_block(yl, i, ind):
    if i >= len(yl.items):
        return None, i
    cur = yl.ind(i)
    if cur < ind:
        return None, i
    stripped = yl.items[i].strip()
    if stripped.startswith('- ') or stripped == '-':
        out = []
        while i < len(yl.items):
            s = yl.items[i].strip()
            if yl.ind(i) != cur or not (s == '-' or s.startswith('- ')):
                break
            body = s[1:].strip()
            if body == '':
                i += 1
                val, i = _yaml_block(yl, i, cur + 1)
                out.append(val)
            elif body[0] in '{[':
                out.append(_yaml_flow(body))
                i += 1
            elif body[0] in ('"', "'"):
                out.append(_yaml_scalar(body))
                i += 1
            elif ':' not in body:
                out.append(_yaml_scalar(body))
                i += 1
            else:
                yl.items[i] = ' ' * (cur + 2) + body
                val, i = _yaml_block(yl, i, cur + 2)
                out.append(val)
        return out, i
    out = {}
    while i < len(yl.items):
        cur2 = yl.ind(i)
        if cur2 < ind:
            break
        s = yl.items[i].strip()
        if s == '-' or s.startswith('- '):
            if cur2 == ind:
                break
            i += 1
            continue
        m = re.match(r'^([^:]+):\s*(.*)$', s)
        if not m:
            i += 1
            continue
        key = _yaml_scalar(m.group(1))
        rest = m.group(2).strip()
        if i + 1 < len(yl.items) and yl.ind(i + 1) > cur2:
            val, i = _yaml_block(yl, i + 1, yl.ind(i + 1))
            out[key] = val
        elif i + 1 < len(yl.items) and yl.ind(i + 1) == cur2 and (
                yl.items[i + 1].strip().startswith('- ') or yl.items[i + 1].strip() == '-'):
            val, i = _yaml_block(yl, i + 1, cur2)
            out[key] = val
        else:
            out[key] = _yaml_flow(rest) if rest else None
            i += 1
    return out, i


# --------------------------------------------------------------------------
# xlsx reader
# --------------------------------------------------------------------------

NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
RELS_NS = '{http://schemas.openxmlformats.org/package/2006/relationships}'


def xlsx_sheets(path):
    """Return {sheet name: [row, ...]} where each row is a list of cell strings."""
    import zipfile
    z = zipfile.ZipFile(path)
    shared = []
    if 'xl/sharedStrings.xml' in z.namelist():
        root = ET.fromstring(z.read('xl/sharedStrings.xml'))
        for si in root.findall(NS + 'si'):
            shared.append(''.join(t.text or '' for t in si.iter(NS + 't')))
    wb = ET.fromstring(z.read('xl/workbook.xml'))
    rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
    target = {}
    for rel in rels:
        target[rel.get('Id')] = rel.get('Target')
    date1904 = False
    wbp = wb.find(NS + 'workbookPr')
    if wbp is not None and wbp.get('date1904') in ('1', 'true'):
        date1904 = True
    sheets = {}
    for sh in wb.find(NS + 'sheets'):
        name = sh.get('name')
        rid = sh.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
        tgt = target.get(rid, '')
        part = 'xl/' + tgt.lstrip('/xl/').lstrip('/')
        part = tgt if tgt.startswith('xl/') else ('xl/' + tgt)
        if part not in z.namelist():
            continue
        root = ET.fromstring(z.read(part))
        rows = []
        for row in root.iter(NS + 'row'):
            cells = {}
            for c in row.findall(NS + 'c'):
                ref = c.get('r') or ''
                col = ''.join(ch for ch in ref if ch.isalpha())
                t = c.get('t')
                v = c.find(NS + 'v')
                isel = c.find(NS + 'is')
                if t == 's' and v is not None:
                    val = shared[int(v.text)]
                elif t == 'inlineStr' and isel is not None:
                    val = ''.join(x.text or '' for x in isel.iter(NS + 't'))
                elif v is not None:
                    val = v.text
                else:
                    val = None
                if col:
                    cells[col] = val
            rows.append(cells)
        sheets[name] = rows
    return sheets, date1904


def xlsx_rows(sheets, name):
    """Rows of a sheet as lists of strings keyed by the header row (first row)."""
    rows = sheets.get(name)
    if rows is None:
        return []
    out = []
    if not rows:
        return out
    hdr = {}
    for col, val in rows[0].items():
        if val:
            hdr[col] = str(val).strip()
    for cells in rows[1:]:
        d = {}
        for col, val in cells.items():
            key = hdr.get(col)
            if key is not None:
                d[key] = '' if val is None else str(val)
        out.append(d)
    return out


# --------------------------------------------------------------------------
# pdf memo reader
# --------------------------------------------------------------------------

def _pdf_streams(data):
    out = []
    for m in re.finditer(rb'<<[^>]*>>\s*stream\r?\n', data):
        start = m.end()
        end = data.find(b'endstream', start)
        raw = data[start:end]
        if raw.endswith(b'\r\n'):
            raw = raw[:-2]
        elif raw.endswith(b'\n'):
            raw = raw[:-1]
        try:
            out.append(zlib.decompress(raw))
        except Exception:
            out.append(raw)
    return out


def _pdf_unescape(s):
    return s.replace('\\(', '(').replace('\\)', ')').replace('\\\\', '\\')


def _pdf_text(blob):
    """Decode one pdf text-showing operand into a string."""
    if blob.startswith(b'<'):
        hs = re.sub(rb'[^0-9A-Fa-f]', b'', blob[1:-1])
        if not hs:
            return ''
        if len(hs) % 2:
            hs += b'0'
        return bytes.fromhex(hs.decode()).decode('latin-1')
    if blob.startswith(b'['):
        t = ''
        for lm in re.finditer(rb'\(((?:[^()\\]|\\.)*)\)', blob):
            t += lm.group(1).decode('latin-1')
        return _pdf_unescape(t)
    inner = blob
    if inner.endswith(b'Tj'):
        inner = inner[:-2].rstrip()
    return _pdf_unescape(inner[1:-1].decode('latin-1'))


def pdf_pages(path):
    """Return a list of pages; each page is a list of rows (top first),
    each row a list of cell strings sorted by x."""
    data = open(path, 'rb').read()
    pages = []
    for stream in _pdf_streams(data):
        if b'Tm' not in stream or (b'Tj' not in stream and b'TJ' not in stream):
            continue
        rows = {}
        for m in re.finditer(rb'1 0 0 1 (-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?) Tm\s*(.*?)\s*(?:Tj|TJ)\s*ET',
                             stream, re.S):
            x = int(float(m.group(1)))
            y = int(float(m.group(2)))
            t = _pdf_text(m.group(3))
            if t == '':
                continue
            rows.setdefault(y, {})
            if x not in rows[y]:
                rows[y][x] = t
        if not rows:
            continue
        page = []
        for y in sorted(rows, reverse=True):
            page.append([rows[y][k] for k in sorted(rows[y])])
        pages.append(page)
    return pages


def memo_tables(path):
    """Parse the governance memo into {label: {'status':..,'rows':[...]}}."""
    lines = []
    for page in pdf_pages(path):
        for row in page:
            lines.append(row)
    tables = {}
    cur = None
    hdr_len = None
    skip = False
    title_re = re.compile(r'^Table\s+([A-Z]-\d+)\s*:?\s*(.*?)\s*$')
    foot_re = re.compile(r'^Governance memo .* page \d+ of \d+$')
    for cells in lines:
        first = cells[0].strip()
        if foot_re.match(first):
            cur = None
            hdr_len = None
            skip = False
            continue
        m = title_re.match(first)
        if m:
            label = m.group(1)
            rest = (m.group(2) or '').strip()
            if rest.endswith('(continued)'):
                cur = label
                skip = True
                continue
            if rest.endswith('(IN FORCE)'):
                status = 'IN FORCE'
            elif rest.endswith('(WITHDRAWN)'):
                status = 'WITHDRAWN'
            else:
                status = None
            cur = label
            if label in tables:
                tables[label]['status'] = status
            else:
                tables[label] = {'status': status, 'rows': []}
            skip = True
            hdr_len = None
            continue
        if not any(c.strip() for c in cells):
            cur = None
            hdr_len = None
            skip = False
            continue
        if skip:
            hdr_len = len(cells)
            skip = False
            continue
        if cur is None:
            continue
        if hdr_len is not None and len(cells) != hdr_len:
            cur = None
            hdr_len = None
            continue
        tables[cur]['rows'].append([c.strip() for c in cells])
    return tables


# --------------------------------------------------------------------------
# token canonicalisation
# --------------------------------------------------------------------------

def canon_run(tok, campaign):
    """Canonicalise a run token; 'OTHER' if it names another campaign."""
    if tok is None:
        return 'OTHER'
    t = str(tok).strip()
    if not t:
        return 'OTHER'
    m = re.search(r'(\d+)\s*$', t)
    if not m:
        return 'OTHER'
    digits = m.group(1)
    stem = t[:m.start()].strip().upper()
    if '/' in t:
        head = t.split('/')[0].strip().upper()
        if _norm_token(head) != _norm_token(campaign):
            return 'OTHER'
    else:
        st = _norm_token(stem)
        camp = _norm_token(campaign)
        body = re.sub(r'^[A-Z]+', '', camp)
        prefix = re.sub(r'[0-9].*$', '', camp)
        if st not in ('', 'R', camp, camp + 'R', body, body + 'R', prefix, prefix + 'R'):
            return 'OTHER'
    return 'KTC-R' + digits.zfill(2)


def _norm_token(s):
    return re.sub(r'[\s\-_]+', '', str(s).upper())


def canon_serial(tok):
    t = str(tok).strip().upper()
    t = re.sub(r'[\s\-_]+', '', t)
    m = re.match(r'^([A-Z]+)(\d+)$', t)
    if not m:
        return None
    return m.group(1) + '-' + m.group(2)


def canon_link(tok):
    t = str(tok).strip().upper()
    t = re.sub(r'[\s\-_]+', '', t)
    m = re.match(r'^([A-Z]+)(\d+)$', t)
    if not m:
        return None
    digits = m.group(2)
    if len(digits) < 3:
        digits = digits.zfill(3)
    return m.group(1) + '-' + digits


def canon_channel(tok):
    """D1C07, DAQ1-07, 1/07, ch07@daq1 all mean D1C07."""
    t = str(tok).strip().upper()
    t = re.sub(r'\s+', '', t)
    m = re.match(r'^D(\d+)C(\d+)$', t)
    if m:
        return 'D%sC%02d' % (m.group(1), int(m.group(2)))
    m = re.match(r'^DAQ(\d+)-(\d+)$', t)
    if m:
        return 'D%sC%02d' % (m.group(1), int(m.group(2)))
    m = re.match(r'^(\d+)/(\d+)$', t)
    if m:
        return 'D%sC%02d' % (m.group(1), int(m.group(2)))
    m = re.match(r'^CH(\d+)@DAQ(\d+)$', t)
    if m:
        return 'D%sC%02d' % (m.group(2), int(m.group(1)))
    return None


def yaml_load(text):
    yl = _YLines(text)
    if not yl.items:
        return None
    val, _ = _yaml_block(yl, 0, yl.ind(0))
    return val


# --------------------------------------------------------------------------
# time handling
# --------------------------------------------------------------------------

def parse_iso_z(s):
    """ISO 8601 (Z, offset or none; also compact YYYYMMDDTHHMMSSZ)."""
    t = str(s).strip()
    m = re.match(r'^(\d{4})-?(\d{2})-?(\d{2})[T ](\d{2}):?(\d{2})(?::?(\d{2}))?(?:\.(\d+))?'
                 r'(Z|[+-]\d{2}:?\d{2})?$', t)
    if not m:
        return None
    y, mo, d, hh, mm = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5))
    ss = int(m.group(6) or 0)
    epoch = _days_from_civil(y, mo, d) * 86400 + hh * 3600 + mm * 60 + ss
    off = m.group(8)
    if off and off != 'Z':
        sign = 1 if off[0] == '+' else -1
        o = off[1:].replace(':', '')
        oh = int(o[:2])
        om = int(o[2:4]) if len(o) > 2 else 0
        epoch -= sign * (oh * 3600 + om * 60)
    return epoch


def _days_from_civil(y, m, d):
    y -= m <= 2
    era = (y if y >= 0 else y - 399) // 400
    yoe = y - era * 400
    doy = (153 * (m + (-3 if m > 2 else 9)) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def civil_from_days(z):
    z += 719468
    era = z // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    y = yoe + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = mp + (3 if mp < 10 else -9)
    return (y + (m <= 2), m, d)


def date_epoch(y, m, d):
    return _days_from_civil(y, m, d) * 86400


def ymd_of_epoch(sec):
    return civil_from_days(sec // 86400)


def iso_of_epoch(sec):
    y, m, d = ymd_of_epoch(sec)
    rest = sec % 86400
    return '%04d-%02d-%02dT%02d:%02d:%02dZ' % (y, m, d, rest // 3600, (rest % 3600) // 60, rest % 60)


def parse_offset(s):
    """'+02:00' -> seconds."""
    t = str(s).strip()
    m = re.match(r'^([+-])(\d{1,2}):?(\d{2})$', t)
    if not m:
        return 0
    sign = 1 if m.group(1) == '+' else -1
    return sign * (int(m.group(2)) * 3600 + int(m.group(3)) * 60)


class SiteCal(object):
    """Site offsets and maintenance blocks."""

    def __init__(self, cal):
        self.base = parse_offset(cal.get('base_offset', '+00:00'))
        self.trans = []
        for tr in (cal.get('transitions') or []):
            at = parse_iso_z(tr['at_utc'])
            self.trans.append((at, parse_offset(tr['offset_after'])))
        self.trans.sort()
        self.maint = []
        for mb in (cal.get('maintenance') or []):
            s = parse_iso_z(mb['start_utc'])
            e = parse_iso_z(mb['end_utc'])
            self.maint.append((s, e, str(mb.get('scope', 'ALL'))))

    def offset_at(self, sec):
        off = self.base
        for at, o in self.trans:
            if at <= sec:
                off = o
            else:
                break
        return off

    def offsets(self):
        out = {self.base}
        for _, o in self.trans:
            out.add(o)
        return sorted(out)

    def wall_to_utc(self, wall_sec, extra_hint=None):
        """Earliest UTC instant whose site offset turns it into that wall time."""
        cands = []
        for o in self.offsets():
            t = wall_sec - o
            if self.offset_at(t) == o:
                cands.append(t)
        if cands:
            return min(cands)
        # wall time inside a skipped hour: offset in effect before the jump
        before = self.base
        for at, o in self.trans:
            if wall_sec - o < at:
                break
            before = o
        return wall_sec - before



# --------------------------------------------------------------------------
# conductivity model
# --------------------------------------------------------------------------

import bisect


class KTable(object):
    """Material conductivity: theta(T) = integral of k from 0 to T (T in mK)."""

    def __init__(self, material, points):
        # points: [(T_mK Fraction/int, k Fraction W/m-K)]
        self.material = material
        pts = sorted(points, key=lambda p: p[0])
        self.ts = [p[0] for p in pts]
        self.ks = [p[1] for p in pts]
        self.cum = [Fraction(0)]
        for i in range(1, len(pts)):
            dt = Fraction(self.ts[i] - self.ts[i - 1])
            self.cum.append(self.cum[-1] + dt * (self.ks[i - 1] + self.ks[i]) / 2)

    def theta(self, t):
        """theta at temperature t (mK, int or Fraction)."""
        ts = self.ts
        if t <= ts[0]:
            return self.ks[0] * Fraction(t)
        if t >= ts[-1]:
            return self.cum[-1] + self.ks[-1] * (Fraction(t) - ts[-1])
        i = bisect.bisect_right(ts, t) - 1
        t0 = Fraction(ts[i])
        k0 = self.ks[i]
        dt = Fraction(ts[i + 1] - ts[i])
        if dt == 0:
            return self.cum[i]
        x = Fraction(t) - t0
        k1 = self.ks[i + 1]
        return self.cum[i] + k0 * x + (k1 - k0) * x * x / (2 * dt)

    def theta_inv(self, target):
        """Largest-integer search: return T' (int mK) with theta(T') closest
        to target, rounded half-even; None if target < 0."""
        if target < 0:
            return None
        if target == 0:
            return 0
        hi = self._upper_bound(target)
        lo = 0
        # largest n with theta(n) <= target
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self.theta(mid) <= target:
                lo = mid
            else:
                hi = mid - 1
        n = lo
        if self.theta(n) == target:
            return n
        half = Fraction(n) + Fraction(1, 2)
        th = self.theta(half)
        if th < target:
            return n + 1
        if th > target:
            return n
        # exact tie: round half-even between n and n+1
        return n if n % 2 == 0 else n + 1

    def _upper_bound(self, target):
        ts = self.ts
        if target >= self.cum[-1]:
            # linear tail
            if self.ks[-1] == 0:
                return ts[-1]
            t = ts[-1] + (target - self.cum[-1]) / self.ks[-1]
            return int(t) + 2
        i = bisect.bisect_right(self.cum, target) - 1
        # target lies between cum[i] and cum[i+1]
        hi = ts[i + 1] if i + 1 < len(ts) else ts[i]
        while self.theta(hi) < target:
            hi += 1
        return hi


def k_of_T(table, t):
    """Conductivity k at temperature t (mK)."""
    ts = table.ts
    if t <= ts[0]:
        return table.ks[0]
    if t >= ts[-1]:
        return table.ks[-1]
    i = bisect.bisect_right(ts, t) - 1
    if ts[i + 1] == ts[i]:
        return table.ks[i]
    return table.ks[i] + (table.ks[i + 1] - table.ks[i]) * (Fraction(t) - ts[i]) / (ts[i + 1] - ts[i])


# --------------------------------------------------------------------------
# calibration model
# --------------------------------------------------------------------------

class CalTable(object):
    """Calibration points in the family's interpolation space."""

    def __init__(self, points):
        # points: [(x Fraction, T_mK Fraction)]
        pts = sorted(points, key=lambda p: p[0])
        self.xs = [p[0] for p in pts]
        self.ts = [p[1] for p in pts]

    def interp(self, x):
        """Temperature (mK, Fraction) or None when out of range."""
        xs = self.xs
        if x < xs[0] or x > xs[-1]:
            return None
        i = bisect.bisect_right(xs, x) - 1
        if i >= len(xs) - 1:
            # x == xs[-1] or beyond: exact top
            return self.ts[len(xs) - 1]
        x0 = xs[i]
        x1 = xs[i + 1]
        if x1 == x0:
            return self.ts[i]
        t0 = self.ts[i]
        t1 = self.ts[i + 1]
        return t0 + (t1 - t0) * (x - x0) / (x1 - x0)


def family_space(family, value):
    """Interpolation abscissa for a calibrated value (ohm or volt)."""
    if family == 'NTC':
        return 1 / Fraction(value)
    return Fraction(value)


# --------------------------------------------------------------------------
# raw value conversion (H8)
# --------------------------------------------------------------------------

def to_canonical(raw_text, unit, family):
    """Convert a raw value to the family's canonical unit (ohm or volt).
    Returns Fraction or None when the value is missing."""
    if raw_text is None:
        return None
    s = str(raw_text).strip()
    if s == '':
        return None
    u = str(unit or '').strip().upper()
    v = Fraction(s)
    if u in ('OHM', 'OHMS'):
        return v
    if u in ('KOHM', 'KILOHM'):
        return v * 1000
    if u in ('V', 'VOLT', 'VOLTS'):
        return v
    if u in ('MV', 'MVOLT', 'MVOLTS', 'MILLIVOLT'):
        return v / 1000
    if u == 'MICRO':
        return v / 1000000
    if u == 'NATIVE':
        return v
    # unknown unit: treat as-is
    return v


# --------------------------------------------------------------------------
# reading shard readers
# --------------------------------------------------------------------------

def _rec(run, kind, tok, t, raw, unit, rev, void):
    return {'run': run, 'kind': kind, 'tok': tok, 't': t, 'raw': raw,
            'unit': unit, 'rev': rev, 'void': void}


def _int(x, default=0):
    try:
        return int(str(x).strip())
    except Exception:
        return default


def _bool(x):
    if isinstance(x, bool):
        return x
    s = str(x).strip().lower()
    return s in ('true', '1', 'y', 'yes', 'void', 'x')


def read_L01(path, site):
    out = []
    with open(path, newline='') as fh:
        for r in csv.DictReader(fh):
            t = parse_iso_z(r.get('ts_utc'))
            out.append(_rec(r.get('run'), 'serial', r.get('sensor'), t,
                            r.get('raw'), r.get('unit'), _int(r.get('rev')),
                            _bool(r.get('void'))))
    return out


def read_L02(path, site):
    out = []
    with open(path, newline='') as fh:
        for r in csv.DictReader(fh, delimiter='\t'):
            out.append(_rec(r.get('RUN'), 'serial', r.get('SERIAL'), _int(r.get('EPOCH_S')),
                            r.get('VALUE'), r.get('UNITS'), _int(r.get('REVISION')),
                            str(r.get('STATUS') or '').strip().upper() == 'VOID'))
    return out


def read_L03(path, site):
    out = []
    small, large = min(site.offsets()), max(site.offsets())
    with open(path, newline='') as fh:
        for r in csv.DictReader(fh, delimiter='|'):
            m = re.match(r'^(\d{2})/(\d{2})/(\d{4})\s+(\d{2}):(\d{2}):(\d{2})$',
                         str(r.get('local_time')).strip())
            if m:
                wall = date_epoch(int(m.group(3)), int(m.group(2)), int(m.group(1))) + \
                    int(m.group(4)) * 3600 + int(m.group(5)) * 60 + int(m.group(6))
                off = large if str(r.get('isdst')).strip() == '1' else small
                t = wall - off
            else:
                t = None
            out.append(_rec(r.get('run_tag'), 'channel', r.get('chan'), t,
                            r.get('reading'), 'NATIVE', _int(r.get('rev')),
                            str(r.get('flag') or '').strip().lower() == 'x'))
    return out


def read_L04(path, site):
    out = []
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        out.append(_rec(d.get('r'), 'serial', d.get('s'), int(d.get('t_ms')) // 1000,
                        d.get('v'), d.get('u'), _int(d.get('rv')), bool(d.get('del'))))
    return out


def read_L05(path, site):
    out = []
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        meta = d.get('meta') or {}
        val = d.get('value') or {}
        out.append(_rec(meta.get('run'), 'serial', d.get('sensor'), parse_iso_z(d.get('at')),
                        val.get('x'), val.get('unit'), _int(meta.get('rev')),
                        _int(d.get('void')) == 1))
    return out


def read_L06(path, site):
    out = []
    root = ET.parse(path).getroot()
    for batch in root.iter('batch'):
        run = batch.get('run')
        for r in batch.iter('r'):
            out.append(_rec(run, 'serial', r.get('s'), parse_iso_z(r.get('t')),
                            r.get('raw'), r.get('u'), _int(r.get('rev')),
                            str(r.get('void') or '').strip().lower() == 'true'))
    return out


def read_L07(path, site):
    out = []
    c = sqlite3.connect(path)
    for run, sensor, epoch, raw, unit, rev, voided in c.execute(
            'select run, sensor, epoch, raw, unit, rev, voided from readings'):
        out.append(_rec(run, 'serial', sensor, _int(epoch), raw, unit, _int(rev), _int(voided) == 1))
    c.close()
    return out


def read_L08(path, site):
    out = []
    c = sqlite3.connect(path)
    frames = {}
    for fid, run, epoch_ms, rev, void in c.execute(
            'select frame_id, run, epoch_ms, rev, void from frames'):
        frames[fid] = (run, int(epoch_ms), _int(rev), _int(void) == 1)
    for fid, ch, micro in c.execute('select frame_id, channel, micro from samples'):
        fr = frames.get(fid)
        if fr is None:
            continue
        out.append(_rec(fr[0], 'channel', ch, fr[1] // 1000, micro, 'MICRO', fr[2], fr[3]))
    c.close()
    return out


def read_L09(path, site):
    out = []
    data = yaml_load(open(path).read()) or []
    for d in data:
        out.append(_rec(d.get('run'), 'serial', d.get('sensor'), _int(d.get('at')),
                        d.get('raw'), d.get('unit'), _int(d.get('rev')),
                        str(d.get('void') or '').strip().lower() == 'yes'))
    return out


def read_L10(path, site):
    out = []
    data = yaml_load(open(path).read()) or {}
    for sensor, block in data.items():
        unit = (block or {}).get('unit')
        for s in (block or {}).get('samples') or []:
            parts = [p.strip() for p in str(s).split('|')]
            while len(parts) < 5:
                parts.append('')
            out.append(_rec(parts[0], 'serial', sensor, parse_iso_z(parts[1]),
                            parts[2] if parts[2] != '-' else None, unit,
                            _int(parts[3]), parts[4] == '1'))
    return out


def read_L11(path, site):
    out = []
    d = json.load(open(path))
    units = d.get('units') or {}
    data = d.get('data') or {}
    n = len(data.get('run') or [])
    for i in range(n):
        sensor = data['sensor'][i]
        raw = data['raw'][i]
        out.append(_rec(data['run'][i], 'serial', sensor, parse_iso_z(data['t'][i]),
                        raw, units.get(sensor), _int(data['rev'][i]), bool(data['void'][i])))
    return out


def read_L12(path, site):
    out = []
    for line in open(path):
        line = line.rstrip('\n')
        if not line.strip() or line.startswith('#') or line.startswith('RUN '):
            continue
        if len(line) < 57:
            continue
        run = line[0:10].strip()
        sensor = line[10:21].strip()
        t = parse_iso_z(line[21:37].strip())
        rawfield = line[37:52].strip()
        rev = _int(line[52:56])
        void = line[56:58].strip().upper() == 'Y'
        raw, unit = None, None
        if rawfield and rawfield != '*****':
            m = re.match(r'^(-?[\d.]+)\s*([RKVM])$', rawfield)
            if m:
                raw = m.group(1)
                unit = {'R': 'ohm', 'K': 'kohm', 'V': 'V', 'M': 'mV'}[m.group(2)]
            else:
                raw, unit = rawfield, ''
        out.append(_rec(run, 'serial', sensor, t, raw, unit, rev, void))
    return out


def read_L13(path, site):
    out = []
    run = None
    in_table = False
    for line in open(path):
        s = line.strip()
        m = re.match(r'^##\s*Run\s+(.+)$', s)
        if m:
            run = m.group(1).strip()
            in_table = False
            continue
        if s.startswith('(continued)'):
            in_table = False
            continue
        if s.startswith('|'):
            cells = [c.strip() for c in s.strip('|').split('|')]
            if cells and cells[0] == 'sensor':
                in_table = True
                continue
            if cells and cells[0] and set(cells[0]) <= set('-'):
                continue
            if not in_table or len(cells) < 6:
                continue
            raw = cells[2].replace(',', '') if cells[2] != 'n/a' else None
            out.append(_rec(run, 'serial', cells[0], parse_iso_z(cells[1]),
                            raw, cells[3], _int(cells[4]), cells[5].lower() == 'void'))
    return out


def read_L14(path, site):
    out = []
    small, large = min(site.offsets()), max(site.offsets())
    with open(path, newline='') as fh:
        for r in csv.DictReader(fh, delimiter=';'):
            wall = parse_iso_z(str(r.get('time_local')).strip())
            off = large if str(r.get('isdst')).strip() == '1' else small
            t = wall - off if wall is not None else None
            val = r.get('value')
            val = val.replace(',', '.') if val is not None else None
            out.append(_rec(r.get('run'), 'serial', r.get('probe'), t, val,
                            r.get('unit'), _int(r.get('rev')),
                            str(r.get('cancelled')).strip() == '1'))
    return out


def read_L15(path, site):
    out = []
    with open(path, newline='') as fh:
        for r in csv.DictReader(fh, delimiter='\t'):
            out.append(_rec(r.get('run'), 'channel', r.get('ch'), _int(r.get('epoch_ms')) // 1000,
                            r.get('val'), r.get('unit'), _int(r.get('rev')),
                            str(r.get('void')).strip() == '1'))
    return out


def read_L16(path, site):
    out = []
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        t0 = parse_iso_z(d.get('t0'))
        dt = d.get('dt') or []
        vs = d.get('v') or []
        voids = set(d.get('void') or [])
        for i in range(len(dt)):
            raw = vs[i] if i < len(vs) else None
            out.append(_rec(d.get('run'), 'serial', d.get('sensor'),
                            (t0 or 0) + _int(dt[i]), raw, d.get('unit'),
                            _int(d.get('rev')), i in voids))
    return out


READERS = {
    'L01': read_L01, 'L02': read_L02, 'L03': read_L03, 'L04': read_L04,
    'L05': read_L05, 'L06': read_L06, 'L07': read_L07, 'L08': read_L08,
    'L09': read_L09, 'L10': read_L10, 'L11': read_L11, 'L12': read_L12,
    'L13': read_L13, 'L14': read_L14, 'L15': read_L15, 'L16': read_L16,
}


# --------------------------------------------------------------------------
# corpus loading
# --------------------------------------------------------------------------

def find(data_dir, *prefixes):
    out = []
    for name in sorted(os.listdir(data_dir)):
        p = os.path.join(data_dir, name)
        if not os.path.isfile(p):
            continue
        for pre in prefixes:
            if name.startswith(pre):
                out.append(p)
                break
    return out


def load_corpus(data_dir):
    ctx = {}
    ctx['dir'] = data_dir

    # catalog
    cat = None
    for p in find(data_dir, 'ingest_catalog_'):
        cat = json.load(open(p))
        break
    ctx['catalog'] = cat or {'shards': [], 'field_maps': [], 'value_maps': []}
    sentinels = {}
    for vm in ctx['catalog'].get('value_maps') or []:
        sentinels[vm['layout']] = vm.get('missing_value')
    ctx['sentinels'] = sentinels

    # profile
    prof = None
    for p in find(data_dir, 'campaign_profile_'):
        prof = yaml_load(open(p).read())
        break
    ctx['profile'] = prof
    campaign = prof.get('campaign')
    ctx['campaign'] = campaign
    ctx['profile_revision'] = prof.get('profile_revision')
    run_ids = []
    for r in prof.get('runs') or []:
        rid = str(r.get('id'))
        crun = canon_run(rid, campaign)
        if crun and crun != 'OTHER':
            run_ids.append(crun)
    ctx['run_ids'] = run_ids
    ctx['runs_in_scope'] = set(run_ids)
    ctx['run_entry'] = {}
    for r in prof.get('runs') or []:
        rid = str(r.get('id'))
        crun = canon_run(rid, campaign)
        if crun in ctx['runs_in_scope']:
            ctx['run_entry'][crun] = r

    # overlays
    overlays = []
    for p in find(data_dir, 'profile_overlay_'):
        o = yaml_load(open(p).read())
        if o:
            o['_path'] = p
            overlays.append(o)
    applied = [o for o in overlays
               if str(o.get('base_revision')) == str(ctx['profile_revision'])]
    ctx['overlays'] = overlays
    ctx['applied_overlays'] = applied
    ctx['overlay_applied'] = bool(applied)

    # site calendar
    site = None
    for p in find(data_dir, 'site_calendar'):
        site = SiteCal(yaml_load(open(p).read()) or {})
        break
    ctx['site'] = site

    # handbook (cooler -> model mapping, measured stages)
    hb = ''
    for p in find(data_dir, 'thermal_budget_handbook'):
        hb = open(p).read()
        break
    ctx['handbook'] = hb
    cooler_models = {}
    for m in re.finditer(r'\b([A-Z]{2,4}-\d+)\s+is\s+([A-Z0-9][A-Z0-9\-]*)', hb):
        cooler_models[m.group(1)] = m.group(2)
    ctx['cooler_models'] = cooler_models
    stages = list(MEASURED_STAGES)
    ms = re.search(r'([A-Z0-9]+(?:,\s*[A-Z0-9]+)*\s+and\s+[A-Z0-9]+)\s+are\s+the\s+measured\s+stages', hb)
    if ms:
        parts = re.split(r',|\s+and\s+', ms.group(1))
        got = [p.strip() for p in parts if p.strip()]
        if got:
            stages = got
    ctx['measured_stages'] = stages
    ctx['stage_index'] = {s: i for i, s in enumerate(stages)}

    # workbook
    sheets = {}
    for p in find(data_dir, 'cryo_property_workbook', '*.xlsx'):
        sheets, date1904 = xlsx_sheets(p)
        ctx['date1904'] = date1904
        break
    ctx['sheets'] = sheets
    base_days = _days_from_civil(1904, 1, 1) if date1904 else _days_from_civil(1899, 12, 30)
    ctx['serial_base_days'] = base_days
    ctx['sheet_materials'] = set()
    for r in xlsx_rows(sheets, prof.get('conductivity_sheet')):
        m = str(r.get('material') or '').strip()
        if m:
            ctx['sheet_materials'].add(m.upper())

    # memo
    memo = {}
    for p in find(data_dir, 'governance_memo_'):
        memo = memo_tables(p)
        break
    ctx['memo'] = memo
    inflabel = {}
    for label, t in memo.items():
        if t['status'] == 'IN FORCE':
            inflabel[label[0]] = label
    ctx['memo_labels'] = inflabel
    solver = {}
    for row in memo.get(inflabel.get('S', ''), {}).get('rows') or []:
        if len(row) >= 2:
            solver[row[0]] = row[1]
    ctx['solver'] = solver
    joints = {}
    for row in memo.get(inflabel.get('J', ''), {}).get('rows') or []:
        if len(row) >= 3:
            joints[(row[0], row[1])] = frac(row[2])
    ctx['joint_base'] = joints
    parasitic = {}
    for row in memo.get(inflabel.get('P', ''), {}).get('rows') or []:
        if len(row) >= 3:
            parasitic[(row[0], row[1])] = int(frac(row[2]))
    ctx['parasitic'] = parasitic
    gauge = {}
    for row in memo.get(inflabel.get('W', ''), {}).get('rows') or []:
        if len(row) >= 2:
            gauge[str(row[0])] = frac(row[1])
    ctx['gauge'] = gauge
    limits = {}
    for row in memo.get(inflabel.get('L', ''), {}).get('rows') or []:
        if len(row) >= 2:
            limits[row[0]] = int(frac(row[1]))
    ctx['limits'] = limits
    lot_scale_materials = set((solver.get('lot_scale_materials') or '').split())

    # rulings + addendum
    rulings = []
    for row in memo.get(inflabel.get('R', ''), {}).get('rows') or []:
        if len(row) >= 6:
            rulings.append({'ref': row[0], 'run': row[1], 'target': row[2],
                            'action': row[3], 'value': row[4], 'status': row[5]})
    state = {r['ref']: r['status'].strip().upper() for r in rulings}
    add = []
    for p in find(data_dir, 'ruling_addendum'):
        root = ET.parse(p).getroot()
        for e in root.iter('entry'):
            add.append((int(e.get('seq')), e.get('ref'),
                        str(e.get('action') or '').strip().upper(),
                        str(e.get('status') or '').strip().upper()))
    add.sort()
    for seq, ref, action, status in add:
        if status == 'ISSUED' and ref in state:
            state[ref] = 'RESCINDED' if action == 'RESCIND' else 'IN FORCE'
    in_force = []
    for r in rulings:
        if state.get(r['ref']) == 'IN FORCE':
            in_force.append(r)
    ctx['rulings_all'] = rulings
    ctx['rulings'] = in_force
    excl_sensor = {}
    excl_link = {}
    offset_sensor = {}
    for r in in_force:
        crun = canon_run(r['run'], campaign)
        if crun not in ctx['runs_in_scope']:
            continue
        act = r['action'].strip().upper()
        if act == 'EXCLUDE_SENSOR':
            s = canon_serial(r['target'])
            if s:
                excl_sensor[(crun, s)] = True
        elif act == 'EXCLUDE_LINK':
            l = canon_link(r['target'])
            if l:
                excl_link[(crun, l)] = True
        elif act == 'OFFSET_SENSOR':
            s = canon_serial(r['target'])
            if s:
                offset_sensor[(crun, s)] = int(frac(r['value']))
    ctx['excl_sensor'] = excl_sensor
    ctx['excl_link'] = excl_link
    ctx['offset_sensor'] = offset_sensor

    # run log
    log = {}
    for p in find(data_dir, 'run_log_'):
        with open(p, newline='') as fh:
            rows = list(csv.DictReader(fh))
        best = {}
        for i, r in enumerate(rows):
            crun = canon_run(r.get('run'), campaign)
            if crun not in ctx['runs_in_scope']:
                continue
            ev = str(r.get('event') or '').strip().upper()
            if ev == 'NOTE':
                continue
            rev = _int(r.get('rev'))
            k = (crun, ev)
            if k not in best or rev > best[k][0] or (rev == best[k][0] and i > best[k][1]):
                best[k] = (rev, i, r.get('local_time'), r.get('value'))
        log = best
        break
    ctx['run_log'] = log
    runs = {}
    for rid in run_ids:
        ps = log.get((rid, 'PLATEAU_START'))
        pe = log.get((rid, 'PLATEAU_END'))
        cf = log.get((rid, 'CONFIG'))
        ab = log.get((rid, 'ABORT'))
        start = end = None
        if ps is not None:
            start = site.wall_to_utc(_wall_seconds(ps[2]))
        if pe is not None:
            end = site.wall_to_utc(_wall_seconds(pe[2]))
        aborted = bool(ab is not None and str(ab[3]).strip().upper() == 'ACTIVE')
        runs[rid] = {
            'run': rid, 'start': start, 'end': end,
            'shield': (str(cf[3]).strip() if cf is not None else None),
            'aborted': aborted,
            'date': (ymd_of_epoch(start) if start is not None else None),
        }
    ctx['runs'] = runs

    # sensor inventory
    inv = {}
    for p in find(data_dir, 'sensor_inventory'):
        d = json.load(open(p))
        for s in d.get('sensors') or []:
            inv[str(s.get('serial'))] = s
        break
    ctx['inventory'] = inv

    # sensor map
    smap = {}
    for p in find(data_dir, 'sensor_map_'):
        d = yaml_load(open(p).read()) or {}
        for a in d.get('assignments') or []:
            ser = canon_serial(a.get('serial'))
            hist = []
            for h in a.get('history') or []:
                hist.append((parse_iso_z(h.get('from_utc')), h.get('stage')))
            hist.sort(key=lambda x: (x[0] if x[0] is not None else -1 << 40))
            if ser:
                smap[ser] = hist
        break
    ctx['sensor_map'] = smap

    # alias register
    alias_path = find(data_dir, 'entity_alias_register', '*alias*')
    mat_alias = {}
    node_alias = {}
    link_alias = {}
    sensor_relabel = {}
    if alias_path:
        c = sqlite3.connect(alias_path[0])
        for tok, tgt, st in c.execute('select token, target, status from material_alias'):
            if str(st).strip().upper() == 'ACTIVE':
                mat_alias[str(tok).strip().upper()] = str(tgt).strip()
        for tok, node in c.execute('select token, node from node_alias'):
            node_alias[str(tok).strip().upper()] = str(node).strip()
        for old, new, eff in c.execute('select old_id, new_id, effective from link_alias'):
            link_alias[str(old).strip()] = str(new).strip()
        for old, new, eff in c.execute('select old_serial, new_serial, effective_utc from sensor_relabel'):
            sensor_relabel[str(old).strip()] = str(new).strip()
        c.close()
    ctx['mat_alias'] = mat_alias
    ctx['node_alias'] = node_alias
    ctx['link_alias'] = link_alias
    ctx['sensor_relabel'] = sensor_relabel

    # channel map
    chanmap = {}
    for p in find(data_dir, 'channel_map'):
        c = sqlite3.connect(p)
        for ch, ser, vf, vt in c.execute('select channel, serial, valid_from_utc, valid_to_utc '
                                         'from channel_assignment'):
            chanmap.setdefault(str(ch).strip(), []).append(
                (parse_iso_z(vf), parse_iso_z(vt) if vt else None, str(ser).strip()))
        c.close()
    for ch in chanmap:
        chanmap[ch].sort(key=lambda x: (x[0] if x[0] is not None else -1 << 40))
    ctx['channel_map'] = chanmap

    # generic calibration curves
    generic = {}
    for p in find(data_dir, 'calibration_generic_curves'):
        with open(p, newline='') as fh:
            for r in csv.DictReader(fh, delimiter='\t'):
                generic.setdefault(r['curve'].strip(), []).append(r)
        break
    ctx['generic_curves'] = generic

    # lot certificates
    lots = {}
    for p in find(data_dir, 'material_lot_certs'):
        root = ET.parse(p).getroot()
        for lot in root.iter('lot'):
            lots[lot.get('id')] = {'k_scale': frac(lot.get('k_scale')),
                                   'status': str(lot.get('status') or '').strip().upper()}
        break
    ctx['lots'] = lots
    ctx['lot_scale_materials'] = lot_scale_materials

    # intercept register
    intercepts = []
    bundle_node = {}
    for p in find(data_dir, 'intercept_register'):
        root = ET.parse(p).getroot()
        for it in root.iter('intercept'):
            crun = canon_run(it.get('run'), campaign)
            intercepts.append({'id': str(it.get('id')), 'run': crun,
                               'band': str(it.get('band')), 'nominal': frac(it.get('nominal_K'))})
        for b in root.iter('bundle'):
            crun = canon_run(b.get('run'), campaign)
            bundle_node[(str(b.get('id')), crun)] = str(b.get('node'))
        break
    ctx['intercepts'] = intercepts
    ctx['bundle_node'] = bundle_node

    # harness ledger
    harness = []
    for p in find(data_dir, 'harness_dissipation'):
        with open(p, newline='') as fh:
            rows = list(csv.DictReader(fh, delimiter='|'))
        best = {}
        for i, r in enumerate(rows):
            bid = str(r.get('bundle') or '').strip()
            rev = _int(r.get('rev'))
            if bid not in best or rev > best[bid][0] or (rev == best[bid][0] and i > best[bid][1]):
                best[bid] = (rev, i, r)
        harness = [v[2] for v in best.values() if str(v[2].get('void') or '').strip().upper() != 'VOID']
        break
    ctx['harness_rows'] = harness

    # cooler service log
    service = []
    for p in find(data_dir, 'cooler_service_log'):
        with open(p, newline='') as fh:
            service = list(csv.DictReader(fh, delimiter='\t'))
        break
    ctx['service'] = service

    # link catalog / segments / joints / installs / amendments
    linkcat = {}
    segments = {}
    joints = {}
    installs = []
    amendments = []
    for sh in sorted(ctx['catalog'].get('shards') or [], key=lambda x: x.get('order', 0)):
        if str(sh.get('status') or '').strip().upper() != 'ACTIVE':
            continue
        p = os.path.join(data_dir, sh.get('file'))
        if not os.path.isfile(p):
            continue
        kind = sh.get('kind')
        lay = sh.get('layout')
        if kind == 'link_catalog':
            with open(p, newline='') as fh:
                for r in csv.DictReader(fh):
                    lid = canon_link(r.get('link'))
                    if lid is None:
                        continue
                    linkcat.setdefault(lid, []).append({
                        'rev': _int(r.get('rev')),
                        'effective': _ymd_epoch(str(r.get('effective_from'))),
                        'status': str(r.get('status') or '').strip().upper(),
                        'kind': r.get('kind')})
        elif kind == 'segments':
            if lay == 'S1':
                root = ET.parse(p).getroot()
                for lk in root.iter('link'):
                    lid = canon_link(lk.get('id'))
                    rev = _int(lk.get('rev'))
                    if lid is None:
                        continue
                    for seg in lk.iter('seg'):
                        segments.setdefault((lid, rev), []).append({
                            'seq': _int(seg.get('n')),
                            'material': seg.get('mat'),
                            'length': seg.get('len'),
                            'area': seg.get('area'),
                            'lot': seg.get('lot') or None})
            elif lay == 'S2':
                with open(p, newline='') as fh:
                    for r in csv.DictReader(fh, delimiter='|'):
                        lid = canon_link(r.get('link'))
                        if lid is None:
                            continue
                        lot = r.get('lot')
                        segments.setdefault((lid, _int(r.get('rev'))), []).append({
                            'seq': _int(r.get('seq')),
                            'material': r.get('material'),
                            'length': r.get('length'),
                            'length_unit': r.get('length_unit'),
                            'area': r.get('area_spec'),
                            'lot': None if (lot is None or lot.strip() == '-') else lot.strip()})
        elif kind == 'joints':
            for line in open(p):
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                lid = canon_link(d.get('link'))
                if lid is None:
                    continue
                ind = str(d.get('indium') or '').strip().lower()
                joints.setdefault((lid, _int(d.get('rev'))), []).append({
                    'pos': _int(d.get('pos')),
                    'class': str(d.get('class') or '').strip(),
                    'bolts': _int(d.get('bolts')),
                    'torque': str(d.get('torque') or '').strip().upper(),
                    'indium': ind in ('true', 'yes', 'y', '1')})
        elif kind == 'installs':
            with open(p, newline='') as fh:
                for r in csv.DictReader(fh, delimiter='\t'):
                    installs.append(r)
        elif kind == 'amendments':
            for line in open(p):
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                amendments.append(d)
    ctx['linkcat'] = linkcat
    ctx['segments'] = segments
    ctx['joints'] = joints
    ctx['install_rows'] = installs
    ctx['amendment_rows'] = amendments
    return ctx


def _wall_seconds(s):
    """'YYYY-MM-DD HH:MM' (or with seconds) -> wall-clock epoch seconds."""
    t = str(s).strip()
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2}))?$', t)
    if not m:
        return None
    return (date_epoch(int(m.group(1)), int(m.group(2)), int(m.group(3))) +
            int(m.group(4)) * 3600 + int(m.group(5)) * 60 + int(m.group(6) or 0))


def _ymd_epoch(s):
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})', str(s).strip())
    if not m:
        return None
    return date_epoch(int(m.group(1)), int(m.group(2)), int(m.group(3)))


# --------------------------------------------------------------------------
# alias resolution
# --------------------------------------------------------------------------

def walk_alias(mapping, key):
    """Follow a token->token alias chain to its end."""
    seen = {key}
    cur = key
    while cur in mapping:
        nxt = mapping[cur]
        if nxt in seen:
            break
        seen.add(nxt)
        cur = nxt
    return cur


def resolve_material(ctx, token):
    t = str(token or '').strip()
    if t == '':
        return None
    cur = t.upper()
    seen = {cur}
    while cur in ctx['mat_alias']:
        nxt = ctx['mat_alias'][cur].strip().upper()
        if nxt in seen:
            break
        seen.add(nxt)
        cur = nxt
    if cur not in ctx['sheet_materials']:
        return None
    return cur


def resolve_node(ctx, token):
    t = str(token or '').strip()
    if t == '':
        return None
    u = t.upper()
    if u in ctx['node_alias']:
        return ctx['node_alias'][u]
    if t in ctx['intercept_ids']:
        return t
    if t in ctx['stage_index']:
        return t
    return None


def resolve_link(ctx, token):
    c = canon_link(token)
    if c is None:
        return None
    return walk_alias(ctx['link_alias'], c)


def collect_alias_tokens(ctx, data_dir):
    mats, nodes, links = set(), set(), set()
    for sh in sorted(ctx['catalog'].get('shards') or [], key=lambda x: x.get('order', 0)):
        if str(sh.get('status') or '').strip().upper() != 'ACTIVE':
            continue
        p = os.path.join(data_dir, sh.get('file'))
        if not os.path.isfile(p):
            continue
        kind, lay = sh.get('kind'), sh.get('layout')
        if kind == 'link_catalog':
            with open(p, newline='') as fh:
                for r in csv.DictReader(fh):
                    if r.get('link'):
                        links.add(str(r['link']).strip())
        elif kind == 'segments':
            if lay == 'S1':
                root = ET.parse(p).getroot()
                for lk in root.iter('link'):
                    if lk.get('id'):
                        links.add(str(lk.get('id')).strip())
                    for seg in lk.iter('seg'):
                        if seg.get('mat'):
                            mats.add(str(seg.get('mat')).strip())
            elif lay == 'S2':
                with open(p, newline='') as fh:
                    for r in csv.DictReader(fh, delimiter='|'):
                        if r.get('link'):
                            links.add(str(r['link']).strip())
                        if r.get('material'):
                            mats.add(str(r['material']).strip())
        elif kind in ('joints', 'amendments'):
            for line in open(p):
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                if d.get('link'):
                    links.add(str(d['link']).strip())
        elif kind == 'installs':
            with open(p, newline='') as fh:
                for r in csv.DictReader(fh, delimiter='\t'):
                    if r.get('link'):
                        links.add(str(r['link']).strip())
                    if r.get('hot'):
                        nodes.add(str(r['hot']).strip())
                    if r.get('cold'):
                        nodes.add(str(r['cold']).strip())
    for hist in ctx['sensor_map'].values():
        for _, stage in hist:
            if stage is not None:
                nodes.add(str(stage).strip())
    for node in ctx['bundle_node'].values():
        if node is not None:
            nodes.add(str(node).strip())
    return {'material': mats, 'node': nodes, 'link': links}


# --------------------------------------------------------------------------
# readings: resolve, dedup, screen, calibrate
# --------------------------------------------------------------------------

def calibration_tables(ctx):
    """Per-serial sorted (valid_from, version, CalTable) and generic curves."""
    fam_of = {s: str(e.get('family') or '').strip().upper() for s, e in ctx['inventory'].items()}
    out = {}
    groups = {}
    for r in xlsx_rows(ctx['sheets'], ctx['profile'].get('calibration_sheet')):
        ser = str(r.get('serial') or '').strip()
        if ser not in fam_of:
            continue
        fam = fam_of[ser]
        val = to_canonical(r.get('raw'), r.get('unit'), fam)
        if val is None:
            continue
        ver = str(r.get('version') or '').strip()
        vf = (ctx['serial_base_days'] + _int(r.get('valid_from'))) * 86400
        groups.setdefault((ser, ver, vf), []).append((val, frac(r.get('T_K')) * 1000))
    for (ser, ver, vf), pts in groups.items():
        fam = fam_of[ser]
        out.setdefault(ser, []).append(
            (vf, ver, CalTable([(family_space(fam, v), tk) for v, tk in pts])))
    for ser in out:
        out[ser].sort(key=lambda x: (x[0], x[1]))
    gen = {}
    for name, rows2 in ctx['generic_curves'].items():
        byfam = {}
        for r in rows2:
            fam = str(r.get('family') or '').strip().upper()
            val = to_canonical(r.get('raw'), r.get('unit'), fam)
            if val is None:
                continue
            byfam.setdefault(fam, []).append((family_space(fam, val), frac(r.get('T_K')) * 1000))
        gen[name] = {fam: CalTable(pts) for fam, pts in byfam.items()}
    return out, gen


def process_readings(ctx, calib, generic):
    site = ctx['site']
    campaign = ctx['campaign']
    inv = ctx['inventory']
    relabel = ctx['sensor_relabel']
    chanmap = ctx['channel_map']
    runs = ctx['runs']
    in_scope = ctx['runs_in_scope']
    sentinels = ctx['sentinels']

    sensor_tokens = set()
    records_read = 0
    unresolved = 0
    lineage = []
    shard_index = []
    copies = {}
    exclusions = {}
    present = {}
    for sh in sorted(ctx['catalog'].get('shards') or [], key=lambda x: x.get('order', 0)):
        if str(sh.get('status') or '').strip().upper() != 'ACTIVE':
            continue
        if sh.get('kind') != 'readings':
            continue
        p = os.path.join(ctx['dir'], sh.get('file'))
        if not os.path.isfile(p):
            continue
        lay = sh.get('layout')
        order = sh.get('order', 0)
        recs = READERS[lay](p, site)
        sentinel = sentinels.get(lay)
        nres = 0
        lin = {'file': sh.get('file'), 'layout': lay, 'records': len(recs),
               'resolved': 0, 'winning': 0, '_pos': len(shard_index)}
        shard_index.append(lin)
        for idx, rec in enumerate(recs):
            records_read += 1
            tok = str(rec['tok'] or '').strip()
            t = rec['t']
            serial = None
            if rec['kind'] == 'serial':
                c0 = canon_serial(tok)
                if c0 is not None and t is not None:
                    sensor_tokens.add(c0)
                    serial = walk_alias(relabel, c0)
                    if serial not in inv:
                        serial = None
            else:
                ch = canon_channel(tok)
                if ch is not None and t is not None:
                    hit = None
                    for vf, vt, ser in chanmap.get(ch, ()):
                        if vf is not None and vf <= t and (vt is None or t < vt):
                            hit = ser
                            break
                    if hit is not None:
                        serial = walk_alias(relabel, hit)
                        if serial not in inv:
                            serial = None
            if serial is None:
                unresolved += 1
                crun = canon_run(rec['run'], campaign)
                if crun in in_scope and not runs.get(crun, {}).get('aborted'):
                    rep = canon_channel(tok) if rec['kind'] == 'channel' else canon_serial(tok)
                    rep = rep if rep else tok
                    reason = 'UNMAPPED_CHANNEL' if rec['kind'] == 'channel' else 'UNKNOWN_SENSOR'
                    k = (crun, rep, reason)
                    exclusions[k] = exclusions.get(k, 0) + 1
                continue
            nres += 1
            key = (serial, t)
            ent = (rec['rev'], order, idx, rec, lin)
            prev = copies.get(key)
            if prev is None or (ent[0], ent[1], ent[2]) > (prev[0], prev[1], prev[2]):
                copies[key] = ent
        lin['resolved'] = nres
    # winning counts: records whose copy won and was not void
    for ent in copies.values():
        if not ent[3]['void']:
            ent[4]['winning'] += 1

    winners = {}
    voided = 0
    for key, ent in copies.items():
        if ent[3]['void']:
            voided += 1
        else:
            winners[key] = ent
    superseded = records_read - unresolved - len(copies)
    unique_readings = len(winners)

    out_of_scope = 0
    window_by = {}
    for (serial, t), ent in winners.items():
        rec = ent[3]
        sentinel = sentinels.get(ent[4]['layout'])
        crun = canon_run(rec['run'], campaign)
        if crun not in in_scope or runs.get(crun, {}).get('aborted'):
            out_of_scope += 1
            continue
        present[(crun, serial)] = present.get((crun, serial), 0) + 1
        run = runs[crun]
        raw = rec['raw']
        missing = raw is None or str(raw).strip() == '' or str(raw).strip() == str(sentinel)
        reason = None
        if missing:
            reason = 'INVALID_VALUE'
        elif run['start'] is None or run['end'] is None or not (run['start'] <= t < run['end']):
            reason = 'OUT_OF_WINDOW'
        else:
            stage = stage_of(ctx, crun, serial, run['start'])
            in_maint = False
            for ms, me, scope in site.maint:
                if ms <= t < me:
                    if scope.strip().upper() == 'ALL':
                        in_maint = True
                        break
                    sc = resolve_node(ctx, scope)
                    if sc is not None and sc == stage:
                        in_maint = True
                        break
            if in_maint:
                reason = 'MAINTENANCE'
            elif ctx['excl_sensor'].get((crun, serial)):
                reason = 'EXCLUDED_SENSOR'
            else:
                fam = str(inv[serial].get('family') or '').strip().upper()
                table = None
                for vf, ver, tab in reversed(calib.get(serial, ())):
                    if vf <= t:
                        table = tab
                        break
                if table is None:
                    pol = str(inv[serial].get('cal_policy') or '').strip().upper()
                    gname = str(inv[serial].get('generic_curve') or '').strip()
                    if pol == 'GENERIC_OK' and gname in generic and fam in generic[gname]:
                        table = generic[gname][fam]
                if table is None:
                    reason = 'NO_CALIBRATION'
                else:
                    val = to_canonical(raw, rec['unit'], fam)
                    tm = table.interp(family_space(fam, val))
                    if tm is None:
                        reason = 'OUT_OF_RANGE'
                    else:
                        tmk = rhe_int(tm) + ctx['offset_sensor'].get((crun, serial), 0)
                        window_by.setdefault((crun, serial), []).append(tmk)
        if reason is not None:
            k = (crun, serial, reason)
            exclusions[k] = exclusions.get(k, 0) + 1

    return {
        'records_read': records_read,
        'unresolved': unresolved,
        'copies_superseded': superseded,
        'voided_keys': voided,
        'unique_readings': unique_readings,
        'out_of_scope_readings': out_of_scope,
        'lineage': shard_index,
        'exclusions': exclusions,
        'window': window_by,
        'sensor_tokens': sensor_tokens,
        'present': present,
    }


def stage_of(ctx, run, serial, at):
    hist = ctx['sensor_map'].get(serial)
    if not hist:
        return None
    best = None
    for vf, stage in hist:
        if vf is not None and vf <= at:
            if best is None or vf >= best[0]:
                best = (vf, stage)
    if best is None:
        return None
    return resolve_node(ctx, best[1])


# --------------------------------------------------------------------------
# effective per-run settings (H13)
# --------------------------------------------------------------------------

def effective_settings(ctx):
    prof = ctx['profile']
    runs = ctx['runs']
    out = {}
    glob = {
        'spike_mK': prof.get('spike_mK'),
        'outlier_mK': prof.get('outlier_mK'),
        'min_readings': prof.get('min_readings'),
    }
    rpct = prof.get('reserve_pct') or {}
    for rid, run in runs.items():
        e = run['entry'] = ctx['run_entry'].get(rid) or {}
        s = {
            'spike_mK': glob['spike_mK'],
            'outlier_mK': glob['outlier_mK'],
            'min_readings': glob['min_readings'],
            'reserve_pct_ST50': rpct.get('ST50'),
            'reserve_pct_ST4': rpct.get('ST4'),
        }
        for key in ('spike_mK', 'outlier_mK', 'min_readings'):
            if key in e:
                s[key] = e[key]
        if isinstance(e.get('reserve_pct'), dict):
            for st in ('ST50', 'ST4'):
                if st in e['reserve_pct']:
                    s['reserve_pct_' + st] = e['reserve_pct'][st]
        for st in ('ST50', 'ST4'):
            k = 'reserve_pct_' + st
            if k in e:
                s[k] = e[k]
        s['shield'] = run['shield']
        s['cooler'] = e.get('cooler')
        out[rid] = s
    for ov in ctx['applied_overlays']:
        keys = ov.get('overridable_keys') or []
        for rid, vals in (ov.get('runs') or {}).items():
            crun = canon_run(rid, ctx['campaign'])
            if crun not in out:
                continue
            if not isinstance(vals, dict):
                continue
            for key in keys:
                if key in vals:
                    out[crun][key] = vals[key]
    return out


# --------------------------------------------------------------------------
# sensor means (H11) and stage temperatures (H12)
# --------------------------------------------------------------------------

def median(xs):
    ys = sorted(xs)
    n = len(ys)
    if n == 0:
        return None
    if n % 2 == 1:
        return Fraction(ys[n // 2])
    return (Fraction(ys[n // 2 - 1]) + Fraction(ys[n // 2])) / 2


def sensor_means(ctx, rd, settings):
    rows = []
    by_run = {}
    present = {}
    # sensors with at least one deduplicated reading of the run, and their stage
    for (crun, serial), vals in rd['window'].items():
        by_run.setdefault((crun, serial), []).extend(vals)
    present = rd['present']
    means = {}
    for (crun, serial) in sorted(set(list(by_run.keys()) + list(present.keys()))):
        run = ctx['runs'][crun]
        stage = stage_of(ctx, crun, serial, run['start'])
        if stage not in ctx['stage_index']:
            continue
        vals = by_run.get((crun, serial), [])
        st = settings[crun]
        spike = _int(st['spike_mK'])
        minr = _int(st['min_readings'])
        if not vals:
            rows.append({'run': crun, 'serial': serial, 'stage': stage,
                         'window': 0, 'spikes': 0, 'used': 0, 'mean': None,
                         'status': 'NO_READINGS'})
            continue
        med = median(vals)
        kept = [v for v in vals if abs(Fraction(v) - med) <= spike]
        dropped = len(vals) - len(kept)
        if not kept:
            rows.append({'run': crun, 'serial': serial, 'stage': stage,
                         'window': len(vals), 'spikes': dropped, 'used': 0,
                         'mean': None, 'status': 'NO_READINGS'})
            continue
        if len(kept) < minr:
            rows.append({'run': crun, 'serial': serial, 'stage': stage,
                         'window': len(vals), 'spikes': dropped, 'used': len(kept),
                         'mean': None, 'status': 'SPARSE'})
            continue
        m = rhe_int(sum(Fraction(v) for v in kept) / len(kept))
        means[(crun, serial)] = m
        rows.append({'run': crun, 'serial': serial, 'stage': stage,
                     'window': len(vals), 'spikes': dropped, 'used': len(kept),
                     'mean': m, 'status': 'OK'})
    return rows, means


def stage_temperatures(ctx, means, settings):
    rows = []
    temps = {}
    by_stage = {}
    for (crun, serial), m in means.items():
        run = ctx['runs'][crun]
        stage = stage_of(ctx, crun, serial, run['start'])
        by_stage.setdefault((crun, stage), []).append((serial, m))
    for rid in ctx['run_ids']:
        run = ctx['runs'][rid]
        if run['aborted']:
            continue
        for stage in ctx['measured_stages']:
            pairs = by_stage.get((rid, stage)) or []
            if not pairs:
                rows.append({'run': rid, 'stage': stage, 'used': [], 'dropped': [],
                             't': None, 'status': 'NO_SENSORS'})
                continue
            ms = [m for _, m in pairs]
            med = median(ms)
            keep = [(s, m) for s, m in pairs
                    if abs(Fraction(m) - med) <= _int(settings[rid]['outlier_mK'])]
            used = sorted(s for s, _ in keep)
            dropped = sorted(s for s, m in pairs if (s, m) not in keep)
            vals = [m for _, m in keep]
            t = rhe_int(sum(Fraction(v) for v in vals) / len(vals))
            temps[(rid, stage)] = t
            rows.append({'run': rid, 'stage': stage, 'used': used, 'dropped': dropped,
                         't': t, 'status': 'OK'})
    return rows, temps





# --------------------------------------------------------------------------
# amendments, links, geometry
# --------------------------------------------------------------------------

def settle_amendments(ctx):
    ents = []
    for d in ctx['amendment_rows']:
        lid = resolve_link(ctx, d.get('link'))
        ents.append({
            'seq': _int(d.get('seq')), 'link': lid, 'rev': _int(d.get('rev')),
            'field': str(d.get('field') or '').strip(),
            'value': d.get('value'),
            'action': str(d.get('action') or '').strip().upper(),
            'status': str(d.get('status') or '').strip().upper(),
            'reverses': d.get('reverses')})
    ents.sort(key=lambda e: e['seq'])
    cancelled = set()
    in_effect = {}
    for e in reversed(ents):
        ok = e['status'] == 'POSTED' and e['seq'] not in cancelled
        in_effect[e['seq']] = ok
        if ok and e['action'] == 'REVERSE' and e.get('reverses') is not None:
            cancelled.add(_int(e['reverses']))
    values = {}
    for e in ents:
        if e['action'] == 'SET' and in_effect[e['seq']]:
            values[(e['link'], e['rev'], e['field'])] = e['value']
    return ents, in_effect, values


def area_of_spec(ctx, spec):
    """Area in mm2 from an area spec (H16.2)."""
    s = str(spec or '').strip()
    m = re.match(r'^A:([\d.]+)\s*(mm2|cm2)$', s, re.I)
    if m:
        v = frac(m.group(1))
        return v * 100 if m.group(2).lower() == 'cm2' else v
    m = re.match(r'^R:([\d.]+)x([\d.]+)\s*mm$', s, re.I)
    if m:
        return frac(m.group(1)) * frac(m.group(2))
    m = re.match(r'^W:(\d+)x(\d+)AWG$', s, re.I)
    if m:
        awg = m.group(2)
        if awg in ctx['gauge']:
            return frac(m.group(1)) * ctx['gauge'][awg]
        return None
    return None


def length_mm(spec, unit):
    s = str(spec or '').strip()
    m = re.match(r'^(-?[\d.]+)\s*mm$', s)
    if m:
        return frac(m.group(1))
    if s == '':
        return None
    v = frac(s)
    u = str(unit or '').strip().lower()
    if u == 'mm':
        return v
    if u == 'cm':
        return v * 10
    if u in ('in', 'inch'):
        return v * frac('25.4')
    return v


def rev_in_use(ctx, lid, run_date_epoch):
    rows = ctx['linkcat'].get(lid) or []
    best = None
    for r in rows:
        if r['effective'] is None or run_date_epoch is None:
            continue
        if r['effective'] <= run_date_epoch:
            if best is None or (r['effective'], r['rev']) > (best['effective'], best['rev']):
                best = r
    return best


def build_links(ctx):
    """Installed links per (run, link id) with resolved nodes."""
    installs = {}
    for i, r in enumerate(ctx['install_rows']):
        crun = canon_run(r.get('run'), ctx['campaign'])
        if crun not in ctx['runs_in_scope'] or ctx['runs'][crun]['aborted']:
            continue
        lid = resolve_link(ctx, r.get('link'))
        if lid is None:
            continue
        rev = _int(r.get('rev'))
        k = (crun, lid)
        prev = installs.get(k)
        if prev is None or rev > prev[0] or (rev == prev[0] and i > prev[1]):
            installs[k] = (rev, i, str(r.get('state') or '').strip().upper(),
                           str(r.get('hot') or '').strip(), str(r.get('cold') or '').strip())
    out = {}
    for (crun, lid), v in installs.items():
        if v[2] != 'INSTALLED':
            continue
        out[(crun, lid)] = (resolve_node(ctx, v[3]), resolve_node(ctx, v[4]))
    return out


def link_geometry(ctx, lid, rev, band, values):
    """Geometry and joint conductances of (link, rev) for a link band."""
    segs = list(ctx['segments'].get((lid, rev)) or [])
    segs.sort(key=lambda s: s['seq'])
    out_segs = []
    for s in segs:
        mat = s['material']
        lot = s['lot']
        if 'length_unit' in s:
            length = length_mm(s['length'], s['length_unit'])
            area_spec = s['area']
        else:
            length = length_mm(s['length'], 'mm')
            area_spec = s['area']
        am = values.get((lid, rev, 'seg%d.length_mm' % s['seq']))
        if am is not None and str(am).strip() != '':
            length = frac(am)
        am = values.get((lid, rev, 'seg%d.area' % s['seq']))
        if am is not None and str(am).strip() != '':
            area_spec = am
        am = values.get((lid, rev, 'seg%d.material' % s['seq']))
        if am is not None and str(am).strip() != '':
            mat = am
        code = resolve_material(ctx, mat)
        lotid = lot if lot else None
        scale = Fraction(1)
        if lotid and lotid in ctx['lots']:
            lc = ctx['lots'][lotid]
            if lc['status'] == 'CERTIFIED' and code in ctx['lot_scale_materials']:
                scale = lc['k_scale']
        area = area_of_spec(ctx, area_spec)
        out_segs.append({
            'seq': s['seq'], 'material': code, 'material_token': mat,
            'length': length, 'area_spec': area_spec, 'area': area,
            'lot': lotid, 'scale': scale,
            'g': (None if length in (None, 0) else
                  (None if area is None else area / length)),
        })
    out_joints = []
    jrows = list(ctx['joints'].get((lid, rev)) or [])
    jrows.sort(key=lambda j: j['pos'])
    base = ctx['joint_base']
    hinc = frac(ctx['solver'].get('h_increment_mW_per_K') or '1')
    lowf = frac(ctx['solver'].get('low_torque_factor') or '1')
    indf = frac(ctx['solver'].get('indium_factor') or '1')
    for j in jrows:
        cls = j['class']
        bolts = j['bolts']
        torque = j['torque']
        indium = j['indium']
        am = values.get((lid, rev, 'joint%d.bolts' % j['pos']))
        if am is not None and str(am).strip() != '':
            bolts = _int(am)
        am = values.get((lid, rev, 'joint%d.torque' % j['pos']))
        if am is not None and str(am).strip() != '':
            torque = str(am).strip().upper()
        am = values.get((lid, rev, 'joint%d.indium' % j['pos']))
        if am is not None and str(am).strip() != '':
            indium = str(am).strip().lower() in ('true', 'yes', 'y', '1')
        hb = base.get((cls, band))
        if hb is None:
            return None, None
        h = hb * bolts
        if torque == 'LOW':
            h = h * lowf
        if indium and cls.startswith('BOLT_'):
            h = h * indf
        if hinc:
            h = rhe(h / hinc) * hinc
        else:
            h = rhe(h, 6)
        out_joints.append({
            'pos': j['pos'], 'class': cls, 'band': band, 'bolts': bolts,
            'torque': torque, 'indium': indium, 'h_base': hb, 'h_eff': h})
    return out_segs, out_joints


def march_elements(link, q, hot):
    """Run the march; returns (end temperature, elements) or None."""
    segs = link['segs']
    joints = link['jmap']
    n = len(segs)
    T = hot
    els = []
    j0 = joints.get(0)
    if j0 is not None:
        drop = rhe_int(Fraction(q) / j0['h_eff'])
        T = T - drop
        if T < 0:
            return None
        els.append({'kind': 'joint', 'pos': 0, 't': T})
    for i in range(n):
        s = segs[i]
        table = link['tables'][i]
        g = s['g']
        if table is None or g is None or g == 0:
            return None
        target = table.theta(T) - Fraction(q) / (s['scale'] * g)
        if target < 0:
            return None
        T = table.theta_inv(target)
        els.append({'kind': 'segment', 'seq': s['seq'], 't': T})
        j = joints.get(i + 1)
        if j is not None:
            drop = rhe_int(Fraction(q) / j['h_eff'])
            T = T - drop
            if T < 0:
                return None
            els.append({'kind': 'joint', 'pos': j['pos'], 't': T})
    return T, els


def solve_link_q(link, hot, cold):
    """Largest whole q whose march succeeds and ends at or above cold."""
    def ok(q):
        r = march_elements(link, q, hot)
        return r is not None and r[0] >= cold
    if hot < cold:
        return 0
    if not ok(0):
        return None
    sum_inv = Fraction(0)
    for i, s in enumerate(link['segs']):
        if link['tables'][i] is None or s['g'] is None or s['g'] == 0:
            return None
        sum_inv += 1 / (s['scale'] * s['g'])
    for j in link['joints']:
        sum_inv += 1 / j['h_eff']
    if sum_inv == 0:
        return 0
    table0 = link['tables'][0]
    qa = (table0.theta(hot) - table0.theta(cold)) / sum_inv
    guess = int(qa) if qa > 0 else 0
    lo = 0
    hi = max(1, guess + 4)
    if ok(hi):
        lo = hi
        hi *= 2
        guard = 0
        while ok(hi) and guard < 60:
            lo = hi
            hi *= 2
            guard += 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if ok(mid):
            lo = mid
        else:
            hi = mid
    return lo


# --------------------------------------------------------------------------
# thermal network
# --------------------------------------------------------------------------

def conductivity_tables(ctx):
    out = {}
    rows = xlsx_rows(ctx['sheets'], ctx['profile'].get('conductivity_sheet'))
    pts = {}
    for r in rows:
        mat = str(r.get('material') or '').strip()
        t = frac(r.get('T_K')) * 1000
        k = frac(r.get('k'))
        unit = str(r.get('unit') or '').strip().lower()
        if unit in ('mw/cm-k', 'mw/cm k', 'mw/cm-k', 'mw/cm-k'.lower()):
            k = k * frac('0.1')
        pts.setdefault(mat, []).append((t, k))
    for mat, pp in pts.items():
        pp.sort(key=lambda x: x[0])
        out[mat] = KTable(mat, pp)
    return out


def capacity_map(ctx):
    rows = xlsx_rows(ctx['sheets'], ctx['profile'].get('capacity_sheet'))
    out = {}
    for r in rows:
        model = str(r.get('model') or '').strip()
        stage = str(r.get('stage') or '').strip()
        out.setdefault((model, stage), []).append(
            (frac(r.get('T_K')), frac(r.get('capacity_W'))))
    for k in out:
        out[k].sort(key=lambda x: x[0])
    return out


def derate_of(ctx, cooler, run_date):
    best = None
    for r in ctx['service']:
        if str(r.get('cooler') or '').strip() != str(cooler).strip():
            continue
        act = str(r.get('action') or '').strip().upper()
        if act not in ('DERATE', 'RESTORE'):
            continue
        d = _ymd_epoch(r.get('date'))
        if d is None or run_date is None:
            continue
        if d <= run_date:
            if best is None or d > best[0]:
                best = (d, (0 if act == 'RESTORE' else frac(r.get('value'))))
    if best is None:
        return Fraction(0)
    return best[1]


def harness_by_node(ctx):
    out = {}
    for r in ctx['harness_rows']:
        crun = canon_run(r.get('run'), ctx['campaign'])
        if crun not in ctx['runs_in_scope'] or ctx['runs'][crun]['aborted']:
            continue
        bid = str(r.get('bundle') or '').strip()
        node = ctx['bundle_node'].get((bid, crun))
        if node is None:
            continue
        node = resolve_node(ctx, node)
        val = frac(r.get('dissipation'))
        unit = str(r.get('unit') or '').strip().upper()
        if unit in ('MW', 'MILLIWATT'):
            val = val * 1000
        out.setdefault((crun, node), Fraction(0))
        out[(crun, node)] += val
    return out


def _intercept_balance(ins, outs, hr, temp_of):
    """Balance function of an intercept: closes over its own link lists."""
    def f(T):
        tot = hr
        for l in ins:
            q = link_q_at(l, temp_of(l['hot']), T)
            tot += q if q is not None else 0
        for l in outs:
            q = link_q_at(l, T, temp_of(l['cold']))
            tot -= q if q is not None else 0
        return tot
    return f


def solve_network(ctx, settings, temps, ktables, values):
    installed = build_links(ctx)
    ctx['installed'] = installed
    harness = harness_by_node(ctx)
    intercept_band = {}
    for it in ctx['intercepts']:
        intercept_band[(it['run'], it['id'])] = it['band']

    results = {}
    for rid in ctx['run_ids']:
        run = ctx['runs'][rid]
        if run['aborted']:
            continue
        rdate = date_epoch(*run['date']) if run['date'] else None
        links = {}
        for (r2, lid), (hot, cold) in sorted(installed.items()):
            if r2 != rid:
                continue
            o = {'run': rid, 'link': lid, 'hot': hot, 'cold': cold,
                 'rev': None, 'status': None, 'q': None, 'segs': None,
                 'joints': None, 'tables': None, 'jmap': {}, 'elements': None}
            rv = rev_in_use(ctx, lid, rdate)
            if rv is not None:
                o['rev'] = rv['rev']
            if ctx['excl_link'].get((rid, lid)):
                o['status'] = 'EXCLUDED'
            elif rv is None:
                o['status'] = 'NO_GEOMETRY'
            else:
                if rv['status'] == 'VOID':
                    o['status'] = 'NO_GEOMETRY'
                else:
                    band = intercept_band.get((rid, cold))
                    if cold in ctx['stage_index']:
                        band = 'W' if cold == 'ST50' else 'C'
                    if band is None:
                        band = 'C'
                    segs, jts = link_geometry(ctx, lid, rv['rev'], band, values)
                    if segs is None or not segs:
                        o['status'] = 'NO_GEOMETRY'
                    else:
                        tables = []
                        broken = False
                        for s in segs:
                            tab = ktables.get(s['material']) if s['material'] else None
                            if tab is None or s['g'] is None:
                                broken = True
                            tables.append(tab)
                        if broken:
                            o['status'] = 'NO_GEOMETRY'
                        else:
                            o['segs'] = segs
                            o['joints'] = jts
                            o['tables'] = tables
                            o['jmap'] = {j['pos']: j for j in jts}
                            o['status'] = 'GEOM'
            links[lid] = o

        def temp_of(node):
            if node in ctx['stage_index']:
                return temps.get((rid, node))
            return None

        # links whose nodes are both stages
        for lid, o in links.items():
            if o['status'] != 'GEOM':
                continue
            if o['hot'] in ctx['stage_index'] and o['cold'] in ctx['stage_index']:
                th = temp_of(o['hot'])
                tc = temp_of(o['cold'])
                if th is None or tc is None:
                    o['status'] = 'UNSOLVED'
                    continue
                o['hot_t'] = th
                o['cold_t'] = tc
                if th <= tc:
                    o['status'] = 'NO_GRADIENT'
                    o['q'] = 0
                    o['elements'] = march_elements(o, 0, th)[1]
                else:
                    q = solve_link_q(o, th, tc)
                    o['q'] = q
                    o['elements'] = march_elements(o, q, th)[1]
                    o['status'] = 'OK'

        # intercepts
        ic_res = []
        for it in ctx['intercepts']:
            if it['run'] != rid:
                continue
            iid = it['id']
            ins = [l for l in links.values()
                   if l['status'] == 'GEOM' and l['cold'] == iid]
            outs = [l for l in links.values()
                    if l['status'] == 'GEOM' and l['hot'] == iid]
            hr = harness.get((rid, iid), Fraction(0))
            entry = {'run': rid, 'node': iid, 'band': it['band'],
                     'harness': hr, 'links_in': sorted(l['link'] for l in ins),
                     'links_out': sorted(l['link'] for l in outs)}
            unsolved = False
            for l in ins:
                if temp_of(l['hot']) is None:
                    unsolved = True
            for l in outs:
                if temp_of(l['cold']) is None:
                    unsolved = True
            if unsolved or (not ins and not outs):
                entry['status'] = 'UNSOLVED'
                entry['t_lo'] = entry['t_hi'] = entry['t'] = None
                entry['residual'] = entry['next_residual'] = None
                ic_res.append(entry)
                for l in ins + outs:
                    l['status'] = 'UNSOLVED'
                continue
            t_lo = max([temp_of(l['cold']) for l in outs]) if outs else None
            t_hi = min([temp_of(l['hot']) for l in ins]) if ins else None
            if t_lo is None:
                t_lo = t_hi if t_hi is not None else None
            if t_hi is None:
                t_hi = t_lo
            entry['t_lo'] = t_lo
            entry['t_hi'] = t_hi
            entry['status'] = None

            entry['_f'] = _intercept_balance(ins, outs, hr, temp_of)
            ic_res.append(entry)

        # solve each intercept by binary search on T (f is non-increasing)
        for entry in ic_res:
            if entry['status'] == 'UNSOLVED':
                continue
            t_lo, t_hi = entry['t_lo'], entry['t_hi']
            f = entry['_f']

            def qsum(T):
                return f(T)
            if t_hi is None:
                entry['status'] = 'UNSOLVED'
                entry['t_lo'] = entry['t_hi'] = entry['t'] = None
                entry['residual'] = entry['next_residual'] = None
                continue
            fhi = f(t_hi)
            flo = f(t_lo)
            if fhi >= 0:
                entry['t'] = t_hi
                entry['status'] = 'CEILING'
                entry['residual'] = fhi
                entry['next_residual'] = None
            elif flo < 0:
                entry['t'] = t_lo
                entry['status'] = 'FLOOR'
                entry['residual'] = flo
                entry['next_residual'] = f(t_lo + 1)
            else:
                lo, hi = t_lo, t_hi
                # largest T with f(T) >= 0
                while hi - lo > 1:
                    mid = (lo + hi) // 2
                    if f(mid) >= 0:
                        lo = mid
                    else:
                        hi = mid
                entry['t'] = lo
                entry['status'] = 'BALANCED'
                entry['residual'] = f(lo)
                entry['next_residual'] = f(lo + 1)

        itemp = {e['node']: e['t'] for e in ic_res if e.get('t') is not None}
        iunsolved = {e['node'] for e in ic_res if e['status'] == 'UNSOLVED'}

        # links attached to intercepts
        for lid, o in links.items():
            if o['status'] != 'GEOM':
                continue
            hot, cold = o['hot'], o['cold']
            if (hot in ctx['stage_index']) and (cold in ctx['stage_index']):
                continue
            if hot in iunsolved or cold in iunsolved:
                o['status'] = 'UNSOLVED'
                continue
            th = temp_of(hot) if hot in ctx['stage_index'] else itemp.get(hot)
            tc = temp_of(cold) if cold in ctx['stage_index'] else itemp.get(cold)
            if th is None or tc is None:
                o['status'] = 'UNSOLVED'
                continue
            o['hot_t'] = th
            o['cold_t'] = tc
            if th <= tc:
                o['status'] = 'NO_GRADIENT'
                o['q'] = 0
                o['elements'] = march_elements(o, 0, th)[1]
            else:
                q = solve_link_q(o, th, tc)
                o['q'] = q
                o['elements'] = march_elements(o, q, th)[1]
                o['status'] = 'OK'

        for entry in ic_res:
            entry.pop('_f', None)
        nodetemp = {}
        for s in ctx['measured_stages']:
            if (rid, s) in temps:
                nodetemp[s] = temps[(rid, s)]
        for e in ic_res:
            if e.get('t') is not None:
                nodetemp[e['node']] = e['t']
        results[rid] = {'links': links, 'intercepts': ic_res,
                        'harness': harness, 'nodetemp': nodetemp}
    return results


def link_q_at(link, hot, cold):
    if hot is None or cold is None:
        return None
    if hot <= cold:
        return 0
    q = solve_link_q(link, hot, cold)
    return q


# --------------------------------------------------------------------------
# stage loads, capacity, verdicts
# --------------------------------------------------------------------------

def capacity_at(cmap, model, stage, tmk):
    pts = cmap.get((model, stage))
    if not pts:
        return None, None
    t = Fraction(tmk) / 1000
    if t < pts[0][0]:
        return pts[0][1], 'OUT_OF_MAP'
    if t > pts[-1][0]:
        return pts[-1][1], 'OUT_OF_MAP'
    for i in range(len(pts) - 1):
        t0, c0 = pts[i]
        t1, c1 = pts[i + 1]
        if t0 <= t <= t1:
            if t1 == t0:
                return c0, 'IN_MAP'
            return c0 + (c1 - c0) * (t - t0) / (t1 - t0), 'IN_MAP'
    return pts[-1][1], 'IN_MAP'


def stage_results(ctx, settings, temps, net, cmap):
    """Loads, capacity, margins and verdicts per run and load stage."""
    out = {}
    for rid in ctx['run_ids']:
        run = ctx['runs'][rid]
        if run['aborted']:
            continue
        links = net[rid]['links']
        harness = net[rid]['harness']
        res = {}
        for stage in LOAD_STAGES:
            row = {'run': rid, 'stage': stage}
            load_links = [l for l in links.values() if l['cold'] == stage]
            unsolved = [l for l in load_links if l['status'] == 'UNSOLVED']
            qsum = sum(l['q'] for l in load_links
                       if l['status'] in ('OK', 'NO_GRADIENT') and l['q'] is not None)
            hu = harness.get((rid, stage), Fraction(0))
            par = ctx['parasitic'].get((run['shield'], stage))
            row['harness_uW'] = rhe_int(hu)
            row['parasitic_uW'] = par
            if unsolved:
                row['status'] = 'INCOMPLETE'
                row['links_uW'] = None
                row['total_uW'] = None
            elif par is None:
                row['status'] = 'INCOMPLETE'
                row['links_uW'] = rhe_int(Fraction(qsum))
                row['total_uW'] = None
            else:
                row['status'] = 'OK'
                row['links_uW'] = rhe_int(Fraction(qsum))
                total = Fraction(row['links_uW']) + hu + Fraction(par)
                row['total_uW'] = rhe_int(total)
            # capacity
            tmk = temps.get((rid, stage))
            row['temperature_mK'] = tmk
            cooler = settings[rid]['cooler']
            model = ctx['cooler_models'].get(str(cooler))
            row['cooler'] = cooler
            row['model'] = model
            rdate = date_epoch(*run['date']) if run['date'] else None
            derate = derate_of(ctx, cooler, rdate)
            row['derate'] = derate
            cap = None
            mapstatus = None
            if model is not None and tmk is not None:
                cap, mapstatus = capacity_at(cmap, model, stage, tmk)
            if cap is not None:
                cap_uw = rhe_int(cap * 1000000 * (100 - derate) / 100)
                row['capacity_uW'] = cap_uw
                row['map_status'] = mapstatus
                rpct = settings[rid]['reserve_pct_' + stage]
                row['reserve_pct'] = rpct
                row['reserve_uW'] = None if rpct is None else \
                    rhe_int(Fraction(cap_uw) * frac(rpct) / 100)
            else:
                row['capacity_uW'] = None
                row['map_status'] = None
                row['reserve_pct'] = settings[rid]['reserve_pct_' + stage]
                row['reserve_uW'] = None
            # margin and verdict
            if row['total_uW'] is None or row['capacity_uW'] is None:
                row['margin_uW'] = None
                row['verdict'] = 'INCOMPLETE'
            else:
                row['margin_uW'] = row['capacity_uW'] - row['total_uW']
                limit = ctx['limits'].get(stage)
                if limit is not None and tmk is not None and tmk > limit:
                    row['verdict'] = 'OVER_TEMP'
                elif row['margin_uW'] < 0:
                    row['verdict'] = 'OVERLOAD'
                elif row['reserve_uW'] is not None and row['margin_uW'] < row['reserve_uW']:
                    row['verdict'] = 'MARGINAL'
                else:
                    row['verdict'] = 'PASS'
            res[stage] = row
        out[rid] = res
    return out


def run_verdicts(ctx, net, stages):
    out = {}
    for rid in ctx['run_ids']:
        run = ctx['runs'][rid]
        if run['aborted']:
            out[rid] = {'verdict': 'ABORTED', 'ST50': None, 'ST4': None,
                        'unsolved_links': 0}
            continue
        links = net[rid]['links']
        unsolved = [l for l in links.values() if l['status'] == 'UNSOLVED']
        no_sensors = [s for s in ctx['measured_stages']
                      if ctx['_stage_status'].get((rid, s)) == 'NO_SENSORS']
        if unsolved or no_sensors:
            out[rid] = {'verdict': 'INCOMPLETE',
                        'ST50': stages[rid]['ST50']['verdict'],
                        'ST4': stages[rid]['ST4']['verdict'],
                        'unsolved_links': len(unsolved)}
            continue
        order = ['OVER_TEMP', 'OVERLOAD', 'MARGINAL', 'PASS']
        worst = None
        for st in LOAD_STAGES:
            v = stages[rid][st]['verdict']
            if v == 'INCOMPLETE':
                v = 'PASS'
            if worst is None or order.index(v) < order.index(worst):
                worst = v
        out[rid] = {'verdict': worst,
                    'ST50': stages[rid]['ST50']['verdict'],
                    'ST4': stages[rid]['ST4']['verdict'],
                    'unsolved_links': len(unsolved)}
    return out


# --------------------------------------------------------------------------
# report writers
# --------------------------------------------------------------------------

def wf(path, text):
    with open(path, 'w', newline='\n') as fh:
        fh.write(text)


def csv_field(v):
    s = '' if v is None else str(v)
    if any(ch in s for ch in ',\r\n"'):
        s = '"' + s.replace('"', '""') + '"'
    return s


def tsv_field(v):
    s = '' if v is None else str(v)
    if any(ch in s for ch in '\t\r\n'):
        s = '"' + s.replace('"', '""') + '"'
    return s


def psv_field(v):
    s = '' if v is None else str(v)
    if any(ch in s for ch in '|\r\n'):
        s = '"' + s.replace('"', '""') + '"'
    return s


def csv_line(vals, delim=','):
    if delim == ',':
        return delim.join(csv_field(v) for v in vals)
    if delim == '\t':
        return delim.join(tsv_field(v) for v in vals)
    return delim.join(psv_field(v) for v in vals)


def json_dumps(obj):
    return json.dumps(obj, indent=1) + '\n'


def jsonl_lines(objs):
    return ''.join(json.dumps(o) + '\n' for o in objs)


def write_sensor_means(path, rows, ctx):
    order = {r: i for i, r in enumerate(ctx['run_ids'])}
    rows = sorted(rows, key=lambda r: (order.get(r['run'], 999), ctx['stage_index'][r['stage']], r['serial']))
    lines = ['run\tserial\tstage\twindow_readings\tspikes_dropped\tused_readings\tmean_mK\tstatus']
    for r in rows:
        lines.append('\t'.join([r['run'], r['serial'], r['stage'], str(r['window']),
                                str(r['spikes']), str(r['used']),
                                '' if r['mean'] is None else str(r['mean']),
                                r['status']]))
    wf(path, '\n'.join(lines) + '\n')


def write_stage_temperatures(path, rows, ctx):
    order = {r: i for i, r in enumerate(ctx['run_ids'])}
    rows = sorted(rows, key=lambda r: (order.get(r['run'], 999), ctx['stage_index'][r['stage']]))
    lines = ['run,stage,sensors_used,sensors_dropped,temperature_mK,status']
    for r in rows:
        lines.append(','.join([
            r['run'], r['stage'], ';'.join(r['used']), ';'.join(r['dropped']),
            '' if r['t'] is None else str(r['t']), r['status']]))
    wf(path, '\n'.join(lines) + '\n')


def write_intercept_solutions(path, net, ctx):
    order = {r: i for i, r in enumerate(ctx['run_ids'])}
    objs = []
    for rid, res in net.items():
        for e in res['intercepts']:
            objs.append(e)
    objs = sorted(objs, key=lambda e: (order.get(e['run'], 999), e['node']))
    out = []
    for e in objs:
        out.append({
            'run': e['run'], 'node': e['node'], 'band': e['band'],
            't_lo_mK': e['t_lo'], 't_hi_mK': e['t_hi'], 'temperature_mK': e['t'],
            'harness_uW': rhe_int(e['harness']),
            'residual_uW': None if e['residual'] is None else rhe_int(e['residual']),
            'next_residual_uW': None if e['next_residual'] is None else rhe_int(e['next_residual']),
            'links_in': e['links_in'], 'links_out': e['links_out'],
            'status': e['status']})
    wf(path, json_dumps({'count': len(out), 'intercepts': out}))


def write_link_heat_flows(path, net, ctx, temps):
    order = {r: i for i, r in enumerate(ctx['run_ids'])}
    lines = ['run|link|rev|hot_node|cold_node|hot_mK|cold_mK|q_uW|status']
    rows = []
    for rid, res in net.items():
        for lid, o in res['links'].items():
            rows.append(o)
    rows = sorted(rows, key=lambda o: (order.get(o['run'], 999), o['link']))
    for o in rows:
        nt = net[o['run']]['nodetemp']
        hot = nt.get(o['hot'], o.get('hot_t'))
        cold = nt.get(o['cold'], o.get('cold_t'))
        lines.append('|'.join([
            o['run'], o['link'], '' if o['rev'] is None else str(o['rev']),
            o['hot'], o['cold'],
            '' if hot is None else str(hot),
            '' if cold is None else str(cold),
            '' if o['q'] is None else str(o['q']), o['status']]))
    wf(path, '\n'.join(lines) + '\n')


def write_junction_profiles(path, net, ctx):
    order = {r: i for i, r in enumerate(ctx['run_ids'])}
    rows = []
    for rid, res in net.items():
        for lid, o in res['links'].items():
            if o['status'] in ('OK', 'NO_GRADIENT'):
                rows.append(o)
    rows = sorted(rows, key=lambda o: (order.get(o['run'], 999), o['link']))
    out = []
    for o in rows:
        els = []
        for e in o['elements']:
            d = {'kind': e['kind'], 't_mK': e['t']}
            if e['kind'] == 'joint':
                d['pos'] = e['pos']
            else:
                d['seq'] = e['seq']
            out_el = {k: d[k] for k in sorted(d)}
            els.append(out_el)
        out.append({'elements': els, 'link': o['link'], 'q_uW': o['q'], 'run': o['run']})
    wf(path, jsonl_lines(out))


def write_link_geometry(path, net, ctx):
    order = {r: i for i, r in enumerate(ctx['run_ids'])}
    rows = []
    for rid, res in net.items():
        for lid, o in res['links'].items():
            if o['status'] in ('OK', 'NO_GRADIENT', 'UNSOLVED'):
                for s in o['segs']:
                    rows.append((o, s))
    rows = sorted(rows, key=lambda rs: (order.get(rs[0]['run'], 999), rs[0]['link'], rs[1]['seq']))
    lines = ['run,link,rev,seq,material,length_mm,area_mm2,lot,lot_scale,g_mm']
    for o, s in rows:
        lines.append(','.join([
            o['run'], o['link'], '' if o['rev'] is None else str(o['rev']),
            str(s['seq']), '' if s['material'] is None else s['material'],
            dec_trim(s['length']), dec_trim(s['area']),
            '' if s['lot'] is None else s['lot'], dec_trim(s['scale']),
            fmt(s['g'], 9)]))
    wf(path, '\n'.join(lines) + '\n')


def write_joint_conductances(path, net, ctx):
    order = {r: i for i, r in enumerate(ctx['run_ids'])}
    rows = []
    for rid, res in net.items():
        for lid, o in res['links'].items():
            if o['status'] in ('OK', 'NO_GRADIENT', 'UNSOLVED'):
                for j in o['joints']:
                    rows.append((o, j))
    rows = sorted(rows, key=lambda rj: (order.get(rj[0]['run'], 999), rj[0]['link'], rj[1]['pos']))
    lines = ['run\tlink\tpos\tclass\tband\tbolts\ttorque\tindium\th_base_mW_per_K\th_eff_mW_per_K']
    for o, j in rows:
        lines.append('\t'.join([
            o['run'], o['link'], str(j['pos']), j['class'], j['band'], str(j['bolts']),
            j['torque'], 'Y' if j['indium'] else 'N',
            dec_trim(j['h_base']), dec_trim(j['h_eff'])]))
    wf(path, '\n'.join(lines) + '\n')


def write_stage_loads(path, stages, ctx):
    order = {r: i for i, r in enumerate(ctx['run_ids'])}
    lines = ['run,stage,links_uW,harness_uW,parasitic_uW,total_uW,status']
    rows = []
    for rid, res in stages.items():
        for st in LOAD_STAGES:
            rows.append(res[st])
    rows = sorted(rows, key=lambda r: (order.get(r['run'], 999), ctx['stage_index'][r['stage']]))
    for r in rows:
        lines.append(','.join([
            r['run'], r['stage'],
            '' if r['links_uW'] is None else str(r['links_uW']),
            str(r['harness_uW']),
            '' if r['parasitic_uW'] is None else str(r['parasitic_uW']),
            '' if r['total_uW'] is None else str(r['total_uW']),
            r['status']]))
    wf(path, '\n'.join(lines) + '\n')


def esc_attr(s):
    return (str(s).replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace('"', '&quot;'))


def write_cooler_margins(path, stages, ctx):
    order = {r: i for i, r in enumerate(ctx['run_ids'])}
    rows = []
    for rid, res in stages.items():
        for st in LOAD_STAGES:
            rows.append(res[st])
    rows = sorted(rows, key=lambda r: (order.get(r['run'], 999), ctx['stage_index'][r['stage']]))
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<margins campaign="%s">' % esc_attr(ctx['campaign'])]
    for r in rows:
        attrs = [
            ('run', r['run']), ('name', r['stage']),
            ('cooler', '' if r['cooler'] is None else r['cooler']),
            ('model', '' if r['model'] is None else r['model']),
            ('temperature_mK', '' if r['temperature_mK'] is None else str(r['temperature_mK'])),
            ('derate_pct', dec_trim(r['derate'])),
            ('capacity_uW', '' if r['capacity_uW'] is None else str(r['capacity_uW'])),
            ('map_status', '' if r['map_status'] is None else r['map_status']),
            ('load_uW', '' if r['total_uW'] is None else str(r['total_uW'])),
            ('reserve_pct', '' if r['reserve_pct'] is None else str(r['reserve_pct'])),
            ('reserve_uW', '' if r['reserve_uW'] is None else str(r['reserve_uW'])),
            ('margin_uW', '' if r['margin_uW'] is None else str(r['margin_uW'])),
            ('verdict', r['verdict'])]
        lines.append('  <stage ' + ' '.join('%s="%s"' % (k, esc_attr(v)) for k, v in attrs) + '/>')
    lines.append('</margins>')
    wf(path, '\n'.join(lines) + '\n')


def write_run_verdicts(path, verdicts, ctx):
    runs = []
    for rid in ctx['run_ids']:
        v = verdicts[rid]
        runs.append({'run': rid, 'verdict': v['verdict'], 'ST50': v['ST50'],
                     'ST4': v['ST4'], 'unsolved_links': v['unsolved_links']})
    summary = {}
    for v in verdicts.values():
        summary[v['verdict']] = summary.get(v['verdict'], 0) + 1
    obj = {'campaign': ctx['campaign'], 'runs': runs,
           'summary': {k: summary[k] for k in sorted(summary)}}
    wf(path, json_dumps(obj))


def write_alias_resolution(path, tokens, ctx):
    rows = []
    for tok in tokens['link']:
        res = resolve_link(ctx, tok)
        rows.append(('link', tok, res if res else 'UNRESOLVED'))
    for tok in tokens['material']:
        res = resolve_material(ctx, tok)
        rows.append(('material', tok, res if res else 'UNRESOLVED'))
    for tok in tokens['node']:
        res = resolve_node(ctx, tok)
        rows.append(('node', tok, res if res else 'UNRESOLVED'))
    for tok in tokens['sensor']:
        res = walk_alias(ctx['sensor_relabel'], tok)
        rows.append(('sensor', tok, res if res else 'UNRESOLVED'))
    rows.sort(key=lambda r: (r[0], r[1]))
    lines = ['kind,token,resolved']
    for k, t, r in rows:
        lines.append(','.join([k, csv_field(t), csv_field(r)]))
    wf(path, '\n'.join(lines) + '\n')


def write_reading_exclusions(path, exclusions, ctx):
    order = {r: i for i, r in enumerate(ctx['run_ids'])}
    keys = sorted(exclusions.keys(),
                  key=lambda k: (order.get(k[0], 999), k[1], k[2]))
    out = []
    for (run, serial, reason) in keys:
        n = exclusions[(run, serial, reason)]
        if not n:
            continue
        out.append({'count': n, 'reason': reason, 'run': run, 'serial': serial})
    wf(path, jsonl_lines(out))


def write_dedup(path, rd):
    wf(path, json_dumps({
        'records_read': rd['records_read'],
        'unresolved': rd['unresolved'],
        'copies_superseded': rd['copies_superseded'],
        'voided_keys': rd['voided_keys'],
        'unique_readings': rd['unique_readings'],
        'out_of_scope_readings': rd['out_of_scope_readings']}))


def write_lineage(path, rd):
    shards = [{'file': l['file'], 'layout': l['layout'], 'records': l['records'],
               'resolved': l['resolved'], 'winning': l['winning']}
              for l in rd['lineage']]
    wf(path, json_dumps({'shards': shards}))


def write_amendment_ledger(path, ents, in_effect):
    lines = ['seq,link,rev,field,action,status,in_effect']
    for e in sorted(ents, key=lambda e: e['seq']):
        lines.append(','.join([
            str(e['seq']), csv_field(e['link'] if e['link'] else 'UNRESOLVED'),
            str(e['rev']), csv_field(e['field']), csv_field(e['action']),
            csv_field(e['status']), 'Y' if in_effect[e['seq']] else 'N']))
    wf(path, '\n'.join(lines) + '\n')


def write_parameters(path, ctx, settings, stages):
    prof = ctx['profile']
    lines = []
    lines.append('campaign: %s' % ctx['campaign'])
    lines.append('profile_revision: %s' % ctx['profile_revision'])
    lines.append('overlay_applied: %s' % ('true' if ctx['overlay_applied'] else 'false'))
    lines.append('sheets:')
    lines.append('  conductivity: %s' % prof.get('conductivity_sheet'))
    lines.append('  calibration: %s' % prof.get('calibration_sheet'))
    lines.append('  capacity: %s' % prof.get('capacity_sheet'))
    ml = ctx['memo_labels']
    lines.append('memo_tables:')
    lines.append('  joint: %s' % ml.get('J', ''))
    lines.append('  parasitic: %s' % ml.get('P', ''))
    lines.append('  solver: %s' % ml.get('S', ''))
    lines.append('  gauge: %s' % ml.get('W', ''))
    lines.append('  limits: %s' % ml.get('L', ''))
    lines.append('constants:')
    lines.append("  h_increment_mW_per_K: '%s'" % ctx['solver'].get('h_increment_mW_per_K', ''))
    lines.append("  indium_factor: '%s'" % ctx['solver'].get('indium_factor', ''))
    lines.append("  low_torque_factor: '%s'" % ctx['solver'].get('low_torque_factor', ''))
    lines.append("  lot_scale_materials: '%s'" % (ctx['solver'].get('lot_scale_materials') or ''))
    lines.append('limits_mK:')
    lines.append('  ST50: %s' % ctx['limits'].get('ST50', ''))
    lines.append('  ST4: %s' % ctx['limits'].get('ST4', ''))
    lines.append('runs:')
    for rid in ctx['run_ids']:
        if ctx['runs'][rid]['aborted']:
            continue
        s = settings[rid]
        derate = stages[rid]['ST50']['derate']
        lines.append('  %s:' % rid)
        lines.append('    spike_mK: %s' % s['spike_mK'])
        lines.append('    outlier_mK: %s' % s['outlier_mK'])
        lines.append('    min_readings: %s' % s['min_readings'])
        lines.append('    reserve_pct_ST50: %s' % s['reserve_pct_ST50'])
        lines.append('    reserve_pct_ST4: %s' % s['reserve_pct_ST4'])
        lines.append('    shield: %s' % s['shield'])
        lines.append('    cooler: %s' % s['cooler'])
        lines.append("    derate_pct: '%s'" % dec_trim(derate))
    wf(path, '\n'.join(lines) + '\n')


def decimals_of(s):
    s = str(s).strip()
    if '.' in s:
        return len(s.split('.', 1)[1])
    return 0


def norm_num(s):
    """Exact Fraction of a quoted numeric text, or None."""
    try:
        return Fraction(str(s).strip())
    except Exception:
        return None


def audit_rows(ctx, data_dir, temps, settings):
    rows = []  # (source, item, quoted, in_force, verdict)
    ktables = ctx['_ktables']

    def governing_k(mat_token, t_k_text):
        code = resolve_material(ctx, mat_token)
        tab = ktables.get(code) if code else None
        if tab is None:
            return None
        t = norm_num(t_k_text)
        if t is None:
            return None
        return k_of_T(tab, t * 1000)

    def add(source, item, quoted, gov):
        q = str(quoted)
        n = norm_num(q)
        places = decimals_of(q)
        if n is None:
            in_force = '' if gov is None else str(gov)
            ok = (in_force != '' and in_force == q.strip())
            rows.append((source, item, q, in_force, 'AGREE' if ok else 'DISAGREE'))
            return
        if gov is None:
            rows.append((source, item, q, '', 'DISAGREE'))
            return
        in_force = fmt(gov, places)
        ok = (rhe(gov, places) == n)
        rows.append((source, item, q, in_force, 'AGREE' if ok else 'DISAGREE'))

    # conductivity cache
    for p in find(data_dir, 'conductivity_cache'):
        for line in open(p):
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            mat = str(d.get('mat') or '').strip()
            tk = str(d.get('T_K') or '').strip()
            code = resolve_material(ctx, mat)
            item = '%s@%s' % (code if code else mat, tk)
            add('conductivity_cache.jsonl', item, str(d.get('k_W_per_mK')), governing_k(mat, tk))
        break

    # quick reference card
    for p in find(data_dir, 'quick_reference_'):
        for line in open(p):
            s = line.strip()
            if not s or not s[0].isalpha():
                continue
            parts = s.split()
            if len(parts) < 3 or not re.match(r'^[A-Z0-9_\-]+$', parts[0]):
                continue
            try:
                float(parts[1])
            except ValueError:
                continue
            try:
                float(parts[2])
            except ValueError:
                continue
            code0 = resolve_material(ctx, parts[0])
            item = '%s@%s' % (code0 if code0 else parts[0], parts[1])
            add('quick_reference', item, parts[2], governing_k(parts[0], parts[1]))
        break

    # materials legacy
    for p in find(data_dir, 'materials_legacy'):
        data = yaml_load(open(p).read()) or {}
        for mat, pts in (data.get('materials') or {}).items():
            for pt in pts or []:
                tk = pt.get('T_K')
                k = pt.get('k')
                if tk is None or k is None:
                    continue
                code0 = resolve_material(ctx, mat)
                item = '%s@%s' % (code0 if code0 else mat, tk)
                add('materials_legacy', item, k, governing_k(mat, tk))
        break

    # dashboard
    for p in find(data_dir, 'daq_dashboard_export'):
        with open(p, newline='') as fh:
            for r in csv.DictReader(fh):
                run = r.get('run')
                stage = r.get('stage')
                item = '%s/%s' % (run, stage)
                tmk = temps.get((run, stage))
                if tmk is None:
                    rows.append(('daq_dashboard_export.csv', item,
                                 str(r.get('live_K')), '', 'DISAGREE'))
                else:
                    add('daq_dashboard_export.csv', item, r.get('live_K'),
                        Fraction(tmk) / 1000)
        break

    # bulletin / draft handbook / solve pack constants
    def governing_const(key):
        parts = key.split()
        if len(parts) >= 2 and parts[0] == 'JOINT':
            rest = key[len('JOINT '):].strip()
            if '/' in rest:
                cls, band = rest.rsplit('/', 1)
                return ctx['joint_base'].get((cls.strip(), band.strip()))
            return None
        if len(parts) >= 2 and parts[0] == 'AWG':
            return ctx['gauge'].get(parts[1])
        if len(parts) >= 2 and parts[0] == 'PARASITIC':
            rest = key[len('PARASITIC '):].strip()
            if '/' in rest:
                cfg, stage = rest.rsplit('/', 1)
                v = ctx['parasitic'].get((cfg.strip(), stage.strip()))
                return None if v is None else Fraction(v)
            return None
        if len(parts) >= 2 and parts[0] == 'FACTOR':
            name = key[len('FACTOR '):].strip()
            v = ctx['solver'].get(name)
            return None if v is None else norm_num(v)
        return None

    for p in find(data_dir, 'ops_bulletin_'):
        for line in open(p):
            m = re.match(r'^NOTICE\s+\d+\s*\|\s*(.+?)\s*\|\s*(\S+)\s*$', line.strip())
            if m:
                add('bulletin', m.group(1), m.group(2), governing_const(m.group(1)))
        break

    for p in find(data_dir, 'handbook_draft_'):
        for line in open(p):
            s = line.strip()
            if not s.startswith('|'):
                continue
            cells = [c.strip() for c in s.strip('|').split('|')]
            if len(cells) != 2 or cells[0] in ('key', ''):
                continue
            if not re.match(r'^(JOINT|AWG|PARASITIC|FACTOR)\s', cells[0]):
                continue
            add('draft handbook', cells[0], cells[1], governing_const(cells[0]))
        break

    for p in find(data_dir, 'budget_solve_pack'):
        started = False
        for line in open(p):
            s = line.strip()
            if s.startswith('|'):
                cells = [c.strip() for c in s.strip('|').split('|')]
                if len(cells) >= 2 and re.match(r'^(JOINT|AWG|PARASITIC|FACTOR)\s', cells[0]):
                    add('solve pack', cells[0], cells[1], governing_const(cells[0]))
        break

    # lab overlay
    for p in find(data_dir, 'profile_overlay_lab'):
        ov = yaml_load(open(p).read()) or {}
        for rid, vals in (ov.get('runs') or {}).items():
            if not isinstance(vals, dict):
                continue
            crun = canon_run(rid, ctx['campaign'])
            for key in ('spike_mK', 'outlier_mK', 'min_readings',
                        'reserve_pct_ST50', 'reserve_pct_ST4'):
                if key in vals:
                    eff = settings.get(crun, {}).get(key)
                    add('profile_overlay_lab.yaml', '%s/%s' % (rid, key), vals[key],
                        None if eff is None else frac(eff))
        break

    rows.sort(key=lambda r: (r[0], r[1]))
    return rows


def write_authority_audit(path, rows):
    lines = ['source,item,quoted,in_force,verdict']
    for source, item, quoted, in_force, verdict in rows:
        lines.append(','.join([csv_field(source), csv_field(item),
                               csv_field(quoted), csv_field(in_force), verdict]))
    wf(path, '\n'.join(lines) + '\n')


def published_budget(ctx, data_dir):
    out = {}
    for p in find(data_dir, 'heatload_budget_published'):
        with open(p, newline='') as fh:
            for r in csv.DictReader(fh):
                crun = canon_run(r.get('run'), ctx['campaign'])
                lid = resolve_link(ctx, r.get('link'))
                if crun is None or crun == 'OTHER' or lid is None:
                    continue
                q = norm_num(r.get('q_mW'))
                if q is None:
                    continue
                out[(crun, lid)] = q * 1000
        break
    return out


def published_margins(ctx, data_dir):
    out = {}
    for p in find(data_dir, 'stage_margins_published'):
        d = json.load(open(p))
        for s in d.get('stages') or []:
            crun = canon_run(s.get('run'), ctx['campaign'])
            if crun is None or crun == 'OTHER':
                continue
            out[(crun, str(s.get('stage')))] = str(s.get('verdict') or '')
        break
    return out


def write_variance(path, published, net, ctx):
    order = {r: i for i, r in enumerate(ctx['run_ids'])}
    recomputed = {}
    for rid, res in net.items():
        for lid, o in res['links'].items():
            if o['status'] in ('OK', 'NO_GRADIENT') and o['q'] is not None:
                recomputed[(rid, lid)] = o['q']
    keys = sorted(set(list(published.keys()) + list(recomputed.keys())),
                  key=lambda k: (order.get(k[0], 999), k[0], k[1]))
    lines = ['run,link,published_uW,recomputed_uW,delta_uW,status']
    for k in keys:
        pv = published.get(k)
        rv = recomputed.get(k)
        if pv is not None:
            pis = rhe_int(pv)
        else:
            pis = None
        ris = rv if rv is not None else None
        if pv is None:
            status = 'MISSING_PUBLISHED'
            delta = None
        elif rv is None:
            status = 'MISSING_RECOMPUTED'
            delta = None
        else:
            delta = rv - pis
            status = 'MATCH' if delta == 0 else 'DIFFERENT'
        lines.append(','.join([k[0], k[1],
                               '' if pis is None else str(pis),
                               '' if ris is None else str(ris),
                               '' if delta is None else str(delta),
                               status]))
    wf(path, '\n'.join(lines) + '\n')


def write_reconciliation(path, published, stages, ctx):
    order = {r: i for i, r in enumerate(ctx['run_ids'])}
    keys = sorted(published.keys(),
                  key=lambda k: (order.get(k[0], 999), k[0],
                                  ctx['stage_index'].get(k[1], 9)))
    lines = ['# Reconciliation with the published stage margins', '',
             '| run | stage | published_verdict | recomputed_verdict | change |',
             '|---|---|---|---|---|']
    changed = 0
    for k in keys:
        pv = published[k]
        if ctx['runs'].get(k[0], {}).get('aborted'):
            rv = 'ABORTED'
        else:
            rv = stages.get(k[0], {}).get(k[1], {}).get('verdict', '')
        chg = 'same' if pv == rv else 'changed'
        if chg == 'changed':
            changed += 1
        lines.append('| %s | %s | %s | %s | %s |' % (k[0], k[1], pv, rv, chg))
    lines.append('')
    lines.append('Changed verdicts: %d of %d.' % (changed, len(keys)))
    wf(path, '\n'.join(lines) + '\n')


def write_budget_summary(path, verdicts, stages, ctx):
    lines = ['# Heat-load budget summary', '',
             '| run | verdict | ST50_load_uW | ST50_margin_uW | ST4_load_uW | ST4_margin_uW |',
             '|---|---|---|---|---|---|']
    passing = 0
    for rid in ctx['run_ids']:
        v = verdicts[rid]
        if v['verdict'] == 'PASS':
            passing += 1
        if ctx['runs'][rid]['aborted']:
            lines.append('| %s | %s |  |  |  |  |' % (rid, v['verdict']))
            continue
        st = stages[rid]
        c = [rid, v['verdict'],
             '' if st['ST50']['total_uW'] is None else str(st['ST50']['total_uW']),
             '' if st['ST50']['margin_uW'] is None else str(st['ST50']['margin_uW']),
             '' if st['ST4']['total_uW'] is None else str(st['ST4']['total_uW']),
             '' if st['ST4']['margin_uW'] is None else str(st['ST4']['margin_uW'])]
        lines.append('| ' + ' | '.join(c) + ' |')
    lines.append('')
    lines.append('Runs passing: %d of %d.' % (passing, len(ctx['run_ids'])))
    wf(path, '\n'.join(lines) + '\n')


def write_manifest(path, out_dir):
    files = []
    for name in REPORT_ORDER:
        p = os.path.join(out_dir, name)
        if not os.path.isfile(p):
            continue
        data = open(p, 'rb').read()
        files.append({'name': name, 'bytes': len(data),
                      'sha256': hashlib.sha256(data).hexdigest()})
    wf(path, json_dumps({'files': files}))


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main(argv):
    data_dir = argv[1]
    out_dir = argv[2]
    os.makedirs(out_dir, exist_ok=True)
    ctx = load_corpus(data_dir)
    ctx['intercept_ids'] = {i['id'] for i in ctx['intercepts']}
    calib, generic = calibration_tables(ctx)
    rd = process_readings(ctx, calib, generic)
    settings = effective_settings(ctx)
    srows, means = sensor_means(ctx, rd, settings)
    trows, temps = stage_temperatures(ctx, means, settings)
    ctx['_stage_status'] = {(r['run'], r['stage']): r['status'] for r in trows}
    ktables = conductivity_tables(ctx)
    ctx['_ktables'] = ktables
    ents, in_effect, values = settle_amendments(ctx)
    net = solve_network(ctx, settings, temps, ktables, values)
    cmap = capacity_map(ctx)
    stages = stage_results(ctx, settings, temps, net, cmap)
    verdicts = run_verdicts(ctx, net, stages)
    tokens = collect_alias_tokens(ctx, data_dir)
    tokens['sensor'] = rd['sensor_tokens']
    pub_links = published_budget(ctx, data_dir)
    pub_margins = published_margins(ctx, data_dir)
    audit = audit_rows(ctx, data_dir, temps, settings)

    P = lambda name: os.path.join(out_dir, name)
    write_sensor_means(P('sensor_means.tsv'), srows, ctx)
    write_stage_temperatures(P('stage_temperatures.csv'), trows, ctx)
    write_intercept_solutions(P('intercept_solutions.json'), net, ctx)
    write_link_heat_flows(P('link_heat_flows.psv'), net, ctx, temps)
    write_junction_profiles(P('junction_profiles.jsonl'), net, ctx)
    write_link_geometry(P('link_geometry.csv'), net, ctx)
    write_joint_conductances(P('joint_conductances.tsv'), net, ctx)
    write_stage_loads(P('stage_loads.csv'), stages, ctx)
    write_cooler_margins(P('cooler_margins.xml'), stages, ctx)
    write_run_verdicts(P('run_verdicts.json'), verdicts, ctx)
    write_alias_resolution(P('alias_resolution.csv'), tokens, ctx)
    write_reading_exclusions(P('reading_exclusions.jsonl'), rd['exclusions'], ctx)
    write_dedup(P('dedup_report.json'), rd)
    write_lineage(P('source_lineage.json'), rd)
    write_amendment_ledger(P('amendment_ledger.csv'), ents, in_effect)
    write_parameters(P('parameters_used.yaml'), ctx, settings, stages)
    write_authority_audit(P('authority_audit.csv'), audit)
    write_variance(P('variance_vs_published.csv'), pub_links, net, ctx)
    write_reconciliation(P('reconciliation.md'), pub_margins, stages, ctx)
    write_budget_summary(P('budget_summary.md'), verdicts, stages, ctx)
    write_manifest(P('manifest.json'), out_dir)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
