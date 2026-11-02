#!/usr/bin/env python3
"""Corrected WAVE-26Q3 experiment portfolio readout.

Usage: python3 run_readout.py DATA_DIR OUT_DIR

Standard library only.
"""

import csv
import hashlib
import io
import json
import math
import os
import re
import sqlite3
import sys
import zipfile
import zlib
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from statistics import NormalDist
from fractions import Fraction
from xml.etree import ElementTree as ET

# ---------------------------------------------------------------- helpers


def norm_id(v):
    """H1.1: strip outer whitespace and quotes, upper case."""
    if v is None:
        return ''
    s = str(v).strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        s = s[1:-1].strip()
    return s.upper()


def norm_text(v):
    if v is None:
        return ''
    s = str(v).strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        s = s[1:-1].strip()
    return s


def strip_ws(v):
    return '' if v is None else str(v).strip()


def parse_bool(v):
    s = norm_text(v).lower()
    return s in ('y', 'yes', 'true', 't', '1')


def to_int(v):
    s = norm_text(v)
    if s in ('', '-'):
        return None
    try:
        return int(s)
    except ValueError:
        return int(float(s))


def to_num(v):
    """Exact Fraction from a source number (integer, decimal or fraction text)."""
    s = norm_text(v)
    if s in ('', '-', 'None', 'null'):
        return None
    return Fraction(Decimal(s))


EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def parse_iso_offset(s):
    """ISO 8601 with explicit offset -> aware datetime."""
    s = norm_text(s)
    if s.endswith('Z') or s.endswith('z'):
        s = s[:-1] + '+00:00'
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def ts_to_dt(value, convention, exp_offsets=None, reporting_offset=None):
    """Convert a raw feed time value to an aware UTC datetime."""
    if convention == 'iso_z':
        return parse_iso_offset(value)
    if convention == 'iso_offset':
        return parse_iso_offset(value)
    if convention == 'epoch_s':
        return EPOCH + timedelta(seconds=int(norm_text(value)))
    if convention == 'epoch_ms':
        ms = int(norm_text(value))
        return EPOCH + timedelta(milliseconds=ms)  # sub-second dropped by int sec below
    if convention == 'compact_utc':
        s = norm_text(value)
        return datetime.strptime(s, '%Y%m%d%H%M%S').replace(tzinfo=timezone.utc)
    if convention == 'local_experiment':
        off = exp_offsets
        dt = datetime.fromisoformat(norm_text(value))
        return dt.replace(tzinfo=timezone(timedelta(minutes=off))).astimezone(timezone.utc)
    if convention == 'local_reporting':
        dt = datetime.fromisoformat(norm_text(value))
        return dt.replace(tzinfo=timezone(timedelta(minutes=reporting_offset))).astimezone(timezone.utc)
    raise ValueError('unknown ts convention %r' % convention)


def parse_offset_min(s):
    """'+05:45' / '-03:00' (optionally with a UTC or GMT prefix) -> minutes."""
    s = norm_text(s).upper().replace('UTC', '').replace('GMT', '').strip()
    m = re.match(r'^([+-])(\d{1,2}):(\d{2})$', s)
    if not m:
        raise ValueError('bad offset %r' % s)
    sign = 1 if m.group(1) == '+' else -1
    return sign * (int(m.group(2)) * 60 + int(m.group(3)))


def fmt_ts(dt):
    return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def round_half_even_frac(fr, places=6):
    """Round an exact Fraction half to even to `places` decimals, return Fraction."""
    fr = Fraction(fr)
    scale = 10 ** places
    x = fr * scale
    n = x.numerator
    d = x.denominator
    q, r = divmod(n, d)
    twice = 2 * r
    if twice > d or (twice == d and q % 2 == 1):
        q += 1
    return Fraction(q, scale)


def fmt6(fr):
    """Format an exact rational with exactly six decimals, half to even."""
    r = round_half_even_frac(Fraction(fr), 6)
    neg = r < 0
    r = abs(r)
    scaled = r * 1000000
    assert scaled.denominator == 1
    s = '%07d' % scaled.numerator
    out = s[:-6] + '.' + s[-6:]
    out = out.lstrip('0')
    if out[0] == '.':
        out = '0' + out
    if neg and scaled.numerator != 0:
        out = '-' + out
    return out


def fmt6f(x):
    """Format a double with six decimals (no minus sign for zero)."""
    s = '%.6f' % x
    if s.startswith('-') and float(s) == 0.0:
        s = s[1:]
    return s


def fmt_exp(x):
    s = format(x, '.6e')
    if s.startswith('-') and float(s) == 0.0:
        s = s[1:]
    return s



# ---------------------------------------------------------------- PDF

def _pdf_objects(data):
    objs = {}
    for m in re.finditer(rb'(\d+)\s+0\s+obj(.*?)endobj', data, re.S):
        objs[int(m.group(1))] = m.group(2)
    return objs


def _pdf_page_list(data, objs):
    pages_obj = None
    for num, body in objs.items():
        if b'/Type /Pages' in body:
            pages_obj = num
            break
    if pages_obj is None:
        return []
    body = objs[pages_obj]
    return [int(k) for k in re.findall(rb'(\d+)\s+0\s+R', body[body.index(b'/Kids'):])]


def _pdf_stream(objs, num):
    d = objs[num]
    si = d.find(b'stream')
    raw = d[si + len(b'stream'):]
    if raw.startswith(b'\r\n'):
        raw = raw[2:]
    elif raw.startswith(b'\n'):
        raw = raw[1:]
    ei = raw.find(b'endstream')
    raw = raw[:ei]
    if b'/FlateDecode' in d[:si]:
        return zlib.decompress(raw)
    return raw


def _pdf_literal_unescape(s):
    out = bytearray()
    i = 0
    while i < len(s):
        c = s[i]
        if c == 0x5c:
            i += 1
            if i >= len(s):
                break
            c2 = s[i]
            if c2 in (0x28, 0x29, 0x5c):
                out.append(c2)
                i += 1
            elif c2 == 0x6e:
                out.append(0x0a)
                i += 1
            elif c2 == 0x72:
                out.append(0x0d)
                i += 1
            elif c2 == 0x74:
                out.append(0x09)
                i += 1
            elif c2 == 0x62:
                out.append(0x08)
                i += 1
            elif c2 == 0x66:
                out.append(0x0c)
                i += 1
            elif 0x30 <= c2 <= 0x37:
                j = i
                digits = b''
                while j < len(s) and len(digits) < 3 and 0x30 <= s[j] <= 0x37:
                    digits += bytes([s[j]])
                    j += 1
                out.append(int(digits, 8) & 0xff)
                i = j
            elif c2 in (0x0a, 0x0d):
                i += 1
                if c2 == 0x0d and i < len(s) and s[i] == 0x0a:
                    i += 1
            else:
                out.append(c2)
                i += 1
        else:
            out.append(c)
            i += 1
    return bytes(out)


def _pdf_hex_unescape(s):
    h = re.sub(rb'\s', b'', s)
    if len(h) % 2:
        h += b'0'
    try:
        return bytes.fromhex(h.decode('ascii'))
    except ValueError:
        return b''


def _pdf_tokenize(content):
    toks = []
    i = 0
    n = len(content)
    while i < n:
        c = content[i:i + 1]
        if c in b' \t\r\n':
            i += 1
            continue
        if c == b'(':
            depth = 1
            j = i + 1
            buf = bytearray()
            while j < n and depth > 0:
                ch = content[j]
                if ch == 0x5c:
                    buf.append(ch)
                    j += 1
                    if j < n:
                        buf.append(content[j])
                        j += 1
                    continue
                if ch == 0x28:
                    depth += 1
                elif ch == 0x29:
                    depth -= 1
                    if depth == 0:
                        j += 1
                        break
                buf.append(ch)
                j += 1
            toks.append(('str', bytes(buf)))
            i = j
        elif c == b'[':
            depth = 1
            j = i + 1
            while j < n and depth > 0:
                if content[j] == 0x5b:
                    depth += 1
                elif content[j] == 0x5d:
                    depth -= 1
                j += 1
            toks.append(('arr', content[i + 1:j - 1]))
            i = j
        elif c == b'<' and content[i + 1:i + 2] == b'<':
            depth = 2
            j = i + 2
            while j < n and depth > 0:
                if content[j] == 0x3c and content[j + 1:j + 2] == b'<':
                    depth += 2
                    j += 2
                    continue
                if content[j] == 0x3e and content[j + 1:j + 2] == b'>':
                    depth -= 2
                    j += 2
                    continue
                j += 1
            toks.append(('dict', content[i:j]))
            i = j
        elif c == b'<':
            j = content.find(b'>', i)
            toks.append(('hexstr', content[i + 1:j]))
            i = j + 1
        elif c == b'/':
            j = i + 1
            while j < n and content[j:j + 1] not in b' \t\r\n/[]<>()':
                j += 1
            toks.append(('name', content[i + 1:j]))
            i = j
        else:
            j = i
            while j < n and content[j:j + 1] not in b' \t\r\n/[]<>()':
                j += 1
            toks.append(('op', content[i:j]))
            i = j
    return toks


def _pdf_runs(content):
    """Text runs as (x, y, text) using absolute Tm matrices."""
    runs = []
    cur_x = cur_y = 0.0
    operands = []
    for kind, val in _pdf_tokenize(content):
        if kind == 'str':
            operands.append(('s', _pdf_literal_unescape(val)))
        elif kind == 'hexstr':
            operands.append(('s', _pdf_hex_unescape(val)))
        elif kind == 'arr':
            parts = []
            for k3, v3 in _pdf_tokenize(val):
                if k3 == 'str':
                    parts.append(_pdf_literal_unescape(v3))
                elif k3 == 'hexstr':
                    parts.append(_pdf_hex_unescape(v3))
            operands.append(('s', b''.join(parts)))
        elif kind == 'dict':
            operands.append(('d', val))
        else:
            op = val
            if op == b'Tm':
                nums = [o for k2, o in operands if k2 == 'o']
                if len(nums) >= 2:
                    try:
                        cur_x = float(nums[-2])
                        cur_y = float(nums[-1])
                    except ValueError:
                        pass
                operands = []
            elif op in (b'Tj', b'TJ'):
                runs.append((cur_x, cur_y, b''.join(o for k2, o in operands if k2 == 's')))
                operands = []
            elif op in (b'BT', b'ET'):
                operands = []
            else:
                operands.append(('o', op))
                if len(operands) > 64:
                    operands = operands[-64:]
    return runs


def _pdf_lines(runs, tol=2.0):
    """Group runs into text lines by y; returns list of strings top to bottom."""
    rows = {}
    for x, y, text in runs:
        placed = False
        for yy in rows:
            if abs(yy - y) <= tol:
                rows[yy].append((x, text))
                placed = True
                break
        if not placed:
            rows[y] = [(x, text)]
    out = []
    for y in sorted(rows, reverse=True):
        cells = sorted(rows[y])
        out.append(' | '.join(t.decode('latin-1') for x, t in cells))
    return out


def pdf_page_lines(path):
    """All pages of a PDF, each a list of text lines (top to bottom)."""
    data = open(path, 'rb').read()
    objs = _pdf_objects(data)
    pages = _pdf_page_list(data, objs)
    result = []
    for p in pages:
        body = objs[p]
        m = re.search(rb'/Contents\s+(\d+)\s+0\s+R', body)
        content = _pdf_stream(objs, int(m.group(1))) if m else b''
        result.append(_pdf_lines(_pdf_runs(content)))
    return result


def pdf_tables(path):
    """Extract the memo's tables.

    Returns {table_key: {'header': [...], 'rows': [[...], ...]}} where table_key
    is the label on the 'Table X-N' line (e.g. 'Table P-1'). Rows are split on
    the ' | ' cell separator; blank cells preserved.
    """
    flat = []
    for lines in pdf_page_lines(path):
        flat.extend(lines)
    tables = {}
    current = None
    header = None
    for i, line in enumerate(flat):
        text = line.strip()
        m = re.match(r'^(Table [A-Z]-\d+)\b(.*)$', text)
        if m and not text.endswith('.'):
            nxt = flat[i + 1].strip() if i + 1 < len(flat) else ''
            if ' | ' in nxt:
                key = m.group(1)
                cont = m.group(2).strip() == '(continued)'
                current = key
                header = None
                if cont or key not in tables:
                    tables.setdefault(key, {'title': key, 'header': None, 'rows': []})
                continue
        if current is None or '|' not in line:
            continue
        cells = [c.strip() for c in line.split(' | ')]
        if header is None:
            if all(c for c in cells):
                header = cells
                tables[current]['header'] = header
            continue
        if cells == header:
            continue
        if len(cells) == len(header):
            tables[current]['rows'].append(cells)
        elif len(cells) < len(header):
            tables[current]['rows'].append(cells + [''] * (len(header) - len(cells)))
    return tables




# ---------------------------------------------------------------- YAML

def _yaml_lines(text):
    """Strip comments, drop blank lines; return list of (indent, text)."""
    out_lines = []
    for raw in text.split('\n'):
        raw = raw.rstrip('\r')
        buf = []
        quote = None
        i = 0
        while i < len(raw):
            c = raw[i]
            if quote:
                if c == quote:
                    quote = None
                buf.append(c)
            elif c in ('"', "'"):
                quote = c
                buf.append(c)
            elif c == '#' and (i == 0 or raw[i - 1] in ' \t'):
                break
            else:
                buf.append(c)
            i += 1
        line = ''.join(buf).rstrip()
        if line.strip() == '':
            continue
        out_lines.append((len(line) - len(line.lstrip(' ')), line.strip()))
    return out_lines


def _yaml_scalar(s):
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        inner = s[1:-1]
        return inner.strip() if s[0] == "'" else inner
    return s


def _yaml_is_mapping_start(txt):
    return bool(re.match(r"^[^:\s\"'][^:]*:(\s|$)", txt))


def _yaml_mapping(lines, i, indent):
    """Parse a block mapping; returns (dict, next index)."""
    mapping = {}
    while i < len(lines):
        ind, txt = lines[i]
        if ind != indent:
            break
        if txt.startswith('- ') or ':' not in txt:
            break
        key, _, rest = txt.partition(':')
        key = _yaml_scalar(key.strip())
        rest = rest.strip()
        i += 1
        if rest:
            mapping[key] = _yaml_scalar(rest)
            continue
        if i < len(lines) and lines[i][0] == indent and lines[i][1].startswith('- '):
            val, i = _yaml_sequence(lines, i, indent)
            mapping[key] = val
        elif i < len(lines) and lines[i][0] > indent:
            val, i = _yaml_node(lines, i, lines[i][0])
            mapping[key] = val
        else:
            mapping[key] = None
    return mapping, i


def _yaml_sequence(lines, i, indent):
    """Parse a block sequence; returns (list, next index)."""
    seq = []
    while i < len(lines):
        ind, txt = lines[i]
        if ind != indent or not txt.startswith('- '):
            break
        item = txt[2:].strip()
        i += 1
        if item == '':
            if i < len(lines) and lines[i][0] > indent:
                val, i = _yaml_node(lines, i, lines[i][0])
            else:
                val = None
            seq.append(val)
        elif _yaml_is_mapping_start(item):
            sub = [(indent + 2, item)]
            while i < len(lines):
                cind, ctxt = lines[i]
                if cind <= indent:
                    break
                sub.append((cind, ctxt))
                i += 1
            val, _ = _yaml_mapping(sub, 0, sub[0][0])
            seq.append(val)
        else:
            seq.append(_yaml_scalar(item))
    return seq, i


def _yaml_node(lines, i, indent):
    if i >= len(lines):
        return None, i
    if lines[i][1].startswith('- '):
        return _yaml_sequence(lines, i, indent)
    return _yaml_mapping(lines, i, indent)


def yaml_load(text):
    """Small YAML subset parser: block mappings, sequences, scalars, comments."""
    lines = _yaml_lines(text)
    value, _ = _yaml_node(lines, 0, lines[0][0] if lines else 0)
    return value


def yaml_load_file(path):
    with open(path, encoding='utf-8') as fh:
        return yaml_load(fh.read())


# ---------------------------------------------------------------- XLSX

XLSX_NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
XLSX_RNS = '{http://schemas.openxmlformats.org/package/2006/relationships}'
XLSX_ODNS = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'


def xlsx_col_index(ref):
    m = re.match(r'([A-Z]+)', ref)
    n = 0
    for ch in m.group(1):
        n = n * 26 + (ord(ch) - 64)
    return n


def xlsx_read(path):
    z = zipfile.ZipFile(path)
    wb = ET.fromstring(z.read('xl/workbook.xml'))
    rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
    relmap = {r.get('Id'): r.get('Target') for r in rels}
    date1904 = False
    wbp = wb.find(XLSX_NS + 'workbookPr')
    if wbp is not None and wbp.get('date1904') in ('1', 'true'):
        date1904 = True
    sheet_target = {}
    for sh in wb.find(XLSX_NS + 'sheets'):
        target = relmap[sh.get(XLSX_ODNS + 'id')]
        if target.startswith('/'):
            target = target.lstrip('/')
        elif not target.startswith('xl/'):
            target = 'xl/' + target
        sheet_target[sh.get('name')] = target
    sst = []
    if 'xl/sharedStrings.xml' in z.namelist():
        for si in ET.fromstring(z.read('xl/sharedStrings.xml')):
            sst.append(''.join(t.text or '' for t in si.iter(XLSX_NS + 't')))
    sheets = {}
    for name, target in sheet_target.items():
        root = ET.fromstring(z.read(target))
        rows = []
        for row in root.iter(XLSX_NS + 'row'):
            cells = {}
            for c in row.findall(XLSX_NS + 'c'):
                ref = c.get('r')
                ctype = c.get('t')
                v = c.find(XLSX_NS + 'v')
                isel = c.find(XLSX_NS + 'is')
                val = None
                if ctype == 's' and v is not None:
                    val = sst[int(v.text)]
                elif ctype == 'inlineStr' and isel is not None:
                    val = ''.join(t.text or '' for t in isel.iter(XLSX_NS + 't'))
                elif v is not None:
                    val = v.text
                cells[xlsx_col_index(ref)] = val
            rows.append(cells)
        sheets[name] = {'rows': rows, 'date1904': date1904}
    return sheets


def xlsx_sheet_table(sheets, name):
    """Sheet -> list of row lists (list of cell strings)."""
    info = sheets[name]
    rows = info['rows']
    maxc = 0
    for r in rows:
        if r:
            maxc = max(maxc, max(r))
    out = []
    for r in rows:
        out.append([(r.get(c) if c in r else None) for c in range(1, maxc + 1)])
    return out


def xlsx_date(value, date1904):
    """A date cell: text YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS, or a serial day count."""
    s = norm_text(value)
    if s == '':
        return None
    if re.match(r'^-?\d+(\.\d+)?$', s):
        n = float(s)
        base = datetime(1904, 1, 1) if date1904 else datetime(1899, 12, 30)
        return base + timedelta(days=n)
    if 'T' in s:
        return datetime.fromisoformat(s)
    return datetime.fromisoformat(s + 'T00:00:00')


def xlsx_cell_text(value):
    return norm_text(value)


# ---------------------------------------------------------------- corpus

DATA_FILES = {
    'profile': 'analysis_profile_w26.yml',
    'aliases': 'experiment_aliases.yaml',
    'catalog': 'ingest_catalog_w26.json',
    'memo': 'stats_governance_memo_w26.pdf',
    'workbook': 'experiment_workbook_w26.xlsx',
    'links': 'identity_links.psv',
    'registry_main': 'unit_registry_main.csv',
    'registry_legacy': 'unit_registry_legacy.tsv',
    'refund_jsonl': 'refund_journal.jsonl',
    'refund_xml': 'refund_journal_late.xml',
}


def find_data_file(data_dir, key):
    """Locate a corpus file by key: exact name first, then by pattern."""
    names = DATA_FILES[key]
    if isinstance(names, str):
        names = [names]
    for name in names:
        p = os.path.join(data_dir, name)
        if os.path.exists(p):
            return p
    # fall back: match by characteristic suffix/pattern
    patterns = {
        'profile': ['analysis_profile'],
        'aliases': ['experiment_aliases'],
        'catalog': ['ingest_catalog'],
        'memo': ['stats_governance_memo'],
        'workbook': ['experiment_workbook'],
        'links': ['identity_links'],
        'registry_main': ['unit_registry_main'],
        'registry_legacy': ['unit_registry_legacy'],
        'refund_jsonl': ['refund'],
        'refund_xml': ['refund'],
    }
    suffixes = {
        'profile': ('.yml', '.yaml'),
        'aliases': ('.yaml', '.yml'),
        'catalog': ('.json',),
        'memo': ('.pdf',),
        'workbook': ('.xlsx',),
        'links': ('.psv',),
        'registry_main': ('.csv',),
        'registry_legacy': ('.tsv',),
        'refund_jsonl': ('.jsonl',),
        'refund_xml': ('.xml',),
    }
    candidates = []
    for entry in sorted(os.listdir(data_dir)):
        if not entry.lower().endswith(suffixes.get(key, ('',))):
            continue
        for pat in patterns.get(key, []):
            if pat in entry:
                candidates.append(entry)
                break
    if candidates:
        return os.path.join(data_dir, candidates[0])
    raise SystemExit('cannot find %s in %s' % (key, data_dir))


class Corpus(object):
    """Everything the readout is computed from."""

    def __init__(self, data_dir):
        self.dir = data_dir
        self.profile = yaml_load_file(find_data_file(data_dir, 'profile'))
        self.portfolio_id = norm_text(self.profile.get('portfolio_id'))
        self.registry_version = norm_text(self.profile.get('registry_version'))
        self.fx_sheet = norm_text(self.profile.get('fx_sheet'))
        self.data_cutoff = parse_iso_offset(self.profile['data_cutoff_utc'])
        self.pre_period_days = to_int(self.profile['pre_period_days'])
        self.reporting_offset = parse_offset_min(self.profile['reporting_offset'])
        self.published_name = norm_text(self.profile.get('published_readout')) or 'readout_published.csv'
        self.in_scope = []
        for entry in self.profile.get('experiments_in_scope') or []:
            if isinstance(entry, dict):
                self.in_scope.append(norm_text(entry.get('experiment')))
            else:
                self.in_scope.append(norm_text(entry))
        self.internal_units_raw = []
        for entry in self.profile.get('internal_units') or []:
            if isinstance(entry, dict):
                self.internal_units_raw.append(entry.get('unit'))
            else:
                self.internal_units_raw.append(entry)
        self.catalog = json.load(open(find_data_file(data_dir, 'catalog'), encoding='utf-8'))
        self.aliases = yaml_load_file(find_data_file(data_dir, 'aliases'))
        self.sheets = xlsx_read(find_data_file(data_dir, 'workbook'))
        self.memo = pdf_tables(find_data_file(data_dir, 'memo'))
        self._load_aliases()
        self._load_workbook()
        self._load_memo()

    # -- aliases --------------------------------------------------------
    def _load_aliases(self):
        self.exp_alias = {}
        for entry in self.aliases.get('experiments') or []:
            key = norm_id(entry.get('alias'))
            self.exp_alias[key] = norm_id(entry.get('canonical'))
        self.variant_arm = {}
        for entry in self.aliases.get('variants') or []:
            exp = norm_id(entry.get('experiment'))
            var = norm_id(entry.get('variant'))
            self.variant_arm[(exp, var)] = norm_text(entry.get('arm'))

    def canonical_experiment(self, token):
        key = norm_id(token)
        return self.exp_alias.get(key, key)

    def arm_for(self, canonical_exp, variant):
        return self.variant_arm.get((norm_id(canonical_exp), norm_id(variant)))

    # -- workbook -------------------------------------------------------
    @staticmethod
    def _sheet_header(rows):
        """First row of a sheet that looks like a header (all cells non-empty)."""
        for row in rows:
            cells = [xlsx_cell_text(c) for c in row]
            if cells and all(cells):
                return cells
        return None

    @staticmethod
    def _find_header_rows(rows, header):
        """Index of the header row within the sheet table."""
        for i, row in enumerate(rows):
            cells = [xlsx_cell_text(c) for c in row]
            if cells == header:
                return i
        return None

    def _load_workbook(self):
        # Experiments
        rows = xlsx_sheet_table(self.sheets, 'Experiments')
        header = self._sheet_header(rows)
        hi = self._find_header_rows(rows, header)
        idx = {name: i for i, name in enumerate(header)}
        date1904 = self.sheets['Experiments']['date1904']
        self.experiments = {}
        for row in rows[hi + 1:]:
            code = norm_text(row[idx['experiment']])
            if not code:
                continue
            tz = norm_text(row[idx['tz_offset']])
            self.experiments[code] = {
                'code': code,
                'tz_offset': tz,
                'tz_minutes': parse_offset_min(tz),
                'start_local': xlsx_date(row[idx['start_local']], date1904),
                'end_local': xlsx_date(row[idx['end_local']], date1904),
                'primary_metric': norm_text(row[idx['primary_metric']]).lower(),
                'owner_team': norm_text(row[idx['owner_team']]).lower(),
            }
        # Allocation
        rows = xlsx_sheet_table(self.sheets, 'Allocation')
        header = self._sheet_header(rows)
        hi = self._find_header_rows(rows, header)
        idx = {name: i for i, name in enumerate(header)}
        self.allocation = defaultdict(list)
        for row in rows[hi + 1:]:
            code = norm_text(row[idx['experiment']])
            if not code or code not in self.experiments:
                continue
            self.allocation[code].append({
                'arm': norm_text(row[idx['arm']]),
                'role': norm_text(row[idx['role']]).lower(),
                'weight_pct': norm_text(row[idx['weight_pct']]),
            })
        for code in self.allocation:
            self.allocation[code].sort(key=lambda a: a['arm'])
        # Currencies
        rows = xlsx_sheet_table(self.sheets, 'Currencies')
        header = self._sheet_header(rows)
        hi = self._find_header_rows(rows, header)
        idx = {name: i for i, name in enumerate(header)}
        self.minor_units = {}
        for row in rows[hi + 1:]:
            cur = norm_text(row[idx['currency']]).upper()
            if not cur:
                continue
            self.minor_units[cur] = to_int(row[idx['minor_units']])
        # FX sheets
        self.fx = {}
        for sheet in self.sheets:
            if not re.match(r'^FX-', sheet):
                continue
            rows = xlsx_sheet_table(self.sheets, sheet)
            header = self._sheet_header(rows)
            hi = self._find_header_rows(rows, header)
            idx = {name: i for i, name in enumerate(header)}
            date1904 = self.sheets[sheet]['date1904']
            table = defaultdict(list)
            for row in rows[hi + 1:]:
                date = xlsx_date(row[idx['date']], date1904)
                cur = norm_text(row[idx['currency']]).upper()
                if date is None or not cur:
                    continue
                table[cur].append({
                    'date': date.date(),
                    'quote': norm_text(row[idx['quote']]).upper(),
                    'rate': to_num(row[idx['rate']]),
                })
            for cur in table:
                table[cur].sort(key=lambda r: (r['date'], r['quote'], r['rate']))
            self.fx[sheet] = table
        # Metric registries: sheets with a METRIC section
        self.registries = {}
        for sheet in self.sheets:
            rows = xlsx_sheet_table(self.sheets, sheet)
            header = self._sheet_header(rows)
            if header is None or 'section' not in header or 'metric' not in header:
                continue
            hi = self._find_header_rows(rows, header)
            sec_i = header.index('section')
            met_i = header.index('metric')
            metrics = {}
            for row in rows[hi + 1:]:
                if norm_text(row[sec_i]) != 'METRIC':
                    continue
                code = norm_text(row[met_i]).lower()
                rec = {}
                for i, name in enumerate(header):
                    if name in ('section', 'metric'):
                        continue
                    rec[name] = row[i] if i < len(row) else None
                metrics[code] = rec
            if metrics:
                self.registries[sheet] = metrics

    def registry(self):
        return self.registries[self.registry_version]

    def fx_table(self):
        return self.fx[self.fx_sheet]

    # -- memo -----------------------------------------------------------
    def _load_memo(self):
        self.params = {}
        for key in ('Table P-1',):
            if key in self.memo:
                for row in self.memo[key]['rows']:
                    self.params[row[0].strip()] = row[1].strip()
        self.ship_capacity = {}
        if 'Table C-1' in self.memo:
            for row in self.memo['Table C-1']['rows']:
                self.ship_capacity[row[0].strip().lower()] = to_int(row[1])
        self.amendments = []
        if 'Table A-1' in self.memo:
            hdr = self.memo['Table A-1']['header']
            for row in self.memo['Table A-1']['rows']:
                rec = dict(zip(hdr, row))
                self.amendments.append(rec)
        self.window_rulings = []
        if 'Table X-1' in self.memo:
            hdr = self.memo['Table X-1']['header']
            for row in self.memo['Table X-1']['rows']:
                self.window_rulings.append(dict(zip(hdr, row)))
        self.unit_rulings = []
        if 'Table U-1' in self.memo:
            hdr = self.memo['Table U-1']['header']
            for row in self.memo['Table U-1']['rows']:
                self.unit_rulings.append(dict(zip(hdr, row)))

    def param_num(self, name):
        return to_num(self.params.get(name))


# ---------------------------------------------------------------- identity

class Ledger(object):
    """identity_links.psv: token resolution with dates and cycles."""

    def __init__(self, path):
        self.links = {}
        with open(path, encoding='utf-8') as fh:
            reader = csv.DictReader(fh, delimiter='|')
            for row in reader:
                src = norm_id(row['from_id'])
                dst = norm_id(row['linked_to'])
                day = norm_text(row['linked_on'])
                eff = datetime.strptime(day, '%Y-%m-%d').replace(tzinfo=timezone.utc)
                cur = self.links.get(src)
                if cur is None or eff >= cur[0]:
                    self.links[src] = (eff, dst)
        self.cache = {}

    def from_ids_effective(self, at):
        return set(src for src, (eff, dst) in self.links.items() if eff <= at)

    def resolve(self, token, at):
        """Returns (unit_id, hops)."""
        start = norm_id(token)
        key = (start, at)
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        visited = [start]
        seen = {start}
        cur = start
        hops = 0
        while True:
            link = self.links.get(cur)
            if link is None or link[0] > at:
                break
            nxt = link[1]
            if nxt in seen:
                idx = visited.index(nxt)
                cycle = visited[idx:]
                result = (min(cycle), hops)
                self.cache[key] = result
                return result
            visited.append(nxt)
            seen.add(nxt)
            cur = nxt
            hops += 1
        result = (cur, hops)
        self.cache[key] = result
        return result


# ---------------------------------------------------------------- feeds

def _split_words(value):
    return str(value).strip().split()


def extract_field(rec, src):
    """Read one field of a raw feed row, by the catalog's field source syntax."""
    m = re.match(r'^col(?:s)?\s+(\d+)(?:-(\d+))?$', src)
    if m:
        a = int(m.group(1))
        b = int(m.group(2) or m.group(1))
        line = rec.get('__line__') or ''
        return line[a - 1:b].strip() if len(line) >= a else ''
    m = re.match(r'^(.*?)\s*\((first|second)\s+word\)$', src)
    if m:
        base = m.group(1).strip()
        which = m.group(2)
        parts = _split_words(extract_field(rec, base) or '')
        if which == 'first':
            return parts[0] if parts else ''
        return parts[1] if len(parts) > 1 else ''
    value = rec.get(src)
    if value is None or value == '':
        value = deep_get(rec, src)
    if (value is None or value == '') and ('.' in src or '/' in src or '@' in src):
        tail = re.split(r'[./@]', src)[-1]
        value = rec.get(tail)
    return value


def jsonl_rows(path):
    out = []
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def xml_rows(path, row_tag):
    tree = ET.parse(path)
    return tree.getroot().findall('.//' + row_tag)


def sqlite_rows(path, table):
    con = sqlite3.connect(path)
    try:
        con.row_factory = sqlite3.Row
        rows = [dict(r) for r in con.execute('select * from %s' % table)]
    finally:
        con.close()
    return rows


def delimited_rows(path, delimiter, bom=False):
    opener = 'utf-8-sig' if bom else 'utf-8'
    with open(path, encoding=opener, newline='') as fh:
        reader = csv.reader(fh, delimiter=delimiter)
        return list(reader)


def json_object_rows(path):
    """Rows of a JSON object keyed by id, keeping duplicate keys."""
    text = open(path, encoding='utf-8').read()
    decoder = json.JSONDecoder()
    rows = []
    i = 0
    n = len(text)
    while i < n and text[i].isspace():
        i += 1
    if i >= n or text[i] != '{':
        return rows
    i += 1
    while True:
        while i < n and text[i].isspace():
            i += 1
        if i < n and text[i] == '}':
            i += 1
            break
        key, i = decoder.raw_decode(text, idx=i)
        while i < n and text[i].isspace():
            i += 1
        if i >= n or text[i] != ':':
            break
        i += 1
        while i < n and text[i].isspace():
            i += 1
        value, i = decoder.raw_decode(text, idx=i)
        rows.append((key, value))
        while i < n and text[i].isspace():
            i += 1
        if i < n and text[i] == ',':
            i += 1
            continue
        if i < n and text[i] == '}':
            i += 1
            break
    return rows


def fixed_width_rows(path):
    """x_txt layout: one record per data line, keyed by '__line__'."""
    out = []
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            line = line.rstrip('\n').rstrip('\r')
            if line.startswith('#') or line.strip() == '':
                continue
            out.append({'__line__': line})
    return out


def deep_get(obj, path):
    """Fetch nested values by an 'a.b[].c' style path with one [] step."""
    parts = path.split('.')
    cur = obj
    for i, p in enumerate(parts):
        m = re.match(r'^(.*)\[\]$', p)
        if m:
            head = m.group(1)
            if isinstance(cur, dict):
                cur = cur.get(head)
            else:
                return None
            if not isinstance(cur, list):
                return None
            rest = '.'.join(parts[i + 1:])
            if rest == '':
                return cur
            return [deep_get(item, rest) for item in cur]
        if isinstance(cur, dict):
            cur = cur.get(p)
        else:
            return None
    return cur


def read_shard_rows(corpus, shard):
    """Read the data rows of one listed shard as a list of meaning -> value."""
    layout = shard['layout']
    path = os.path.join(corpus.dir, shard['file'])
    if not os.path.exists(path):
        return []
    if layout in ('x_jsonl', 'x_ndjson'):
        raw = jsonl_rows(path)
    elif layout == 'x_json':
        doc = json.load(open(path, encoding='utf-8'))
        raw = [r for r in (deep_get(doc, 'export.rows[]') or []) if isinstance(r, dict)]
    elif layout in ('x_csv', 'x_tsv', 'x_psv'):
        delim = {'x_csv': ',', 'x_tsv': '\t', 'x_psv': '|'}[layout]
        rows = delimited_rows(path, delim, bom=(layout == 'x_csv'))
        header = [norm_text(c) for c in rows[0]] if rows else []
        raw = [dict(zip(header, r)) for r in rows[1:]]
    elif layout == 'x_txt':
        raw = fixed_width_rows(path)
    elif layout == 'x_xml':
        raw = [dict(el.attrib) for el in xml_rows(path, 'x')]
    elif layout == 'x_yaml':
        raw = list((yaml_load_file(path) or {}).get('records') or [])
    elif layout == 'x_sqlite':
        raw = sqlite_rows(path, 'exposure')
    elif layout == 'o_db':
        raw = sqlite_rows(path, 'ord')
    elif layout == 'o_csv':
        rows = delimited_rows(path, ',')
        header = [norm_text(c) for c in rows[0]] if rows else []
        raw = [dict(zip(header, r)) for r in rows[1:]]
    elif layout == 'o_xml':
        raw = []
        for el in xml_rows(path, 'order'):
            rec = {}
            for child in el:
                rec[child.tag] = (child.text or '')
            raw.append(rec)
    elif layout == 'o_yml':
        raw = list(yaml_load_file(path) or [])
    elif layout == 'o_json':
        raw = []
        for key, value in json_object_rows(path):
            rec = {'(key)': key}
            rec.update(value)
            raw.append(rec)
    else:
        raise SystemExit('unknown layout %s' % layout)
    mapped = []
    for rec in raw:
        out = {}
        for src, meaning in shard['fields'].items():
            out[meaning] = extract_field(rec, src)
        mapped.append(out)
    return mapped


def row_value(rec, src):
    return extract_field(rec, src)


# ---------------------------------------------------------------- analysis

STREAM_STATUS = {'exposure': ('LIVE', 'VOID'), 'order': ('PLACED', 'CANCELLED')}


def status_map_for(shard, stream):
    live, dead = STREAM_STATUS[stream]
    mapping = {}
    for code, value in (shard.get('status_codes') or {}).items():
        mapping[code.strip()] = norm_text(value).upper()
    return mapping


def read_all_feeds(corpus, ledger):
    """Read every listed shard and return raw parsed rows plus lineage."""
    exposure_rows = []
    order_rows = []
    lineage = {}
    counter = {'exposure': 0, 'order': 0}
    for shard in corpus.catalog.get('shards', []):
        stream = shard['stream']
        mapping = status_map_for(shard, stream)
        rows = read_shard_rows(corpus, shard)
        lineage[shard['file']] = {'stream': stream, 'rows': len(rows), 'kept': 0}
        parsed = []
        for row in rows:
            rec_id = norm_id(row.get('id'))
            status = norm_text(row.get('status'))
            value = mapping.get(status)
            live = (value == STREAM_STATUS[stream][0])
            revision = to_int(row.get('revision'))
            if revision is None:
                revision = 0
            canon = corpus.canonical_experiment(norm_id(row.get('experiment')))
            exp_info = corpus.experiments.get(canon)
            tz = exp_info['tz_minutes'] if exp_info else 0
            ts = ts_to_dt(row.get('time'), shard['ts_convention'], tz, corpus.reporting_offset)
            rec = {
                'id': rec_id,
                'revision': revision,
                'live': live,
                'ts': ts,
                'unit_token': norm_id(row.get('unit')),
                'experiment': canon,
                'variant': norm_id(row.get('variant')),
                'currency': norm_text(row.get('currency')).upper(),
                'amount': row.get('amount'),
                'seq': counter[stream],
                'shard': shard['file'],
                'stream': stream,
            }
            if stream == 'order':
                rec['amount_unit'] = shard.get('amount_unit', 'minor')
            parsed.append(rec)
            counter[stream] += 1
        if stream == 'exposure':
            exposure_rows.extend(parsed)
        else:
            order_rows.extend(parsed)
    return exposure_rows, order_rows, lineage


def pick_winners(rows):
    """H3.2: largest revision wins; returns (winners, per-stream counters)."""
    best = {}
    for rec in rows:
        rid = rec['id']
        cur = best.get(rid)
        if cur is None or rec['revision'] > cur['revision']:
            best[rid] = rec
    return best


def amount_to_minor(corpus, amount, currency, amount_unit):
    """H2.2: exact minor units of an order amount."""
    frac = to_num(amount)
    if frac is None:
        return Fraction(0)
    if amount_unit == 'major':
        digits = corpus.minor_units.get(currency, 2)
        frac = frac * (10 ** digits)
    return Fraction(frac)


def apply_refund_journal(corpus, orders_by_id):
    """H8.2: apply both halves of the refund journal in ascending seq order.

    Returns (outcomes, held) where outcomes is the ordered list of result
    objects and held maps refund id -> (order id, amount).
    """
    entries = []
    path = find_data_file(corpus.dir, 'refund_jsonl')
    for row in jsonl_rows(path):
        entries.append(('jsonl', row))
    path = find_data_file(corpus.dir, 'refund_xml')
    for el in xml_rows(path, 'refund'):
        rec = dict(el.attrib)
        for child in el:
            rec[child.tag] = (child.text or '')
        entries.append(('xml', rec))
    parsed = []
    for journal, rec in entries:
        seq = to_int(rec.get('seq'))
        kind = norm_text(rec.get('kind') or 'refund').lower()
        refund_id = norm_id(rec.get('id') or rec.get('refund_id'))
        order_id = norm_id(rec.get('order') or rec.get('order_id'))
        amount = to_int(rec.get('minor') or rec.get('amount_minor')) or 0
        posted = parse_iso_offset(rec.get('posted') or rec.get('posted_utc'))
        parsed.append({
            'journal': journal,
            'seq': seq,
            'kind': 'reversal' if kind == 'reversal' else 'refund',
            'refund_id': refund_id,
            'order_id': order_id,
            'amount': Fraction(amount),
            'posted': posted,
            'status': norm_text(rec.get('status')).upper(),
        })
    parsed.sort(key=lambda e: e['seq'])
    outcomes = []
    held = {}
    for entry in parsed:
        if entry['status'] != 'POSTED':
            continue
        order = orders_by_id.get(entry['order_id'])
        if entry['posted'] >= corpus.data_cutoff:
            outcome = 'AFTER_CUTOFF'
        elif order is None:
            outcome = 'NO_ORDER'
        elif not order['live']:
            outcome = 'ORDER_CANCELLED'
        elif entry['kind'] == 'reversal':
            if entry['refund_id'] in held:
                del held[entry['refund_id']]
                outcome = 'REVERSED'
            else:
                outcome = 'NOTHING_TO_REVERSE'
        else:
            if entry['refund_id'] in held:
                outcome = 'REPLACED'
            else:
                outcome = 'APPLIED'
            held[entry['refund_id']] = (entry['order_id'], entry['amount'])
        outcomes.append({
            'journal': entry['journal'],
            'seq': entry['seq'],
            'kind': entry['kind'],
            'refund_id': entry['refund_id'],
            'order_id': entry['order_id'],
            'outcome': outcome,
        })
    return outcomes, held


def fx_fixing(corpus, currency, on_date):
    """H8.4: the latest fixing of a currency on or before a date."""
    table = corpus.fx_table()
    rows = table.get(currency) or []
    best = None
    for row in rows:
        if row['date'] <= on_date and (best is None or row['date'] > best['date']):
            best = row
    return best


def usd_value(corpus, major_amount, currency, on_date):
    """Exact USD value of a major-unit amount; returns (usd Fraction, fx_date)."""
    if currency == 'USD':
        return major_amount, None
    fixing = fx_fixing(corpus, currency, on_date)
    if fixing is None:
        raise SystemExit('no FX fixing for %s on or before %s' % (currency, on_date))
    if fixing['quote'] == 'USD_PER_UNIT':
        return major_amount * fixing['rate'], fixing['date']
    if fixing['quote'] == 'UNIT_PER_USD':
        return major_amount / fixing['rate'], fixing['date']
    if fixing['quote'] == 'UNIT_PER_EUR':
        eur = fx_fixing(corpus, 'EUR', on_date)
        if eur is None:
            raise SystemExit('no EUR fixing on or before %s' % on_date)
        if eur['quote'] == 'USD_PER_UNIT':
            eur_usd = eur['rate']
        elif eur['quote'] == 'UNIT_PER_USD':
            eur_usd = Fraction(1) / eur['rate']
        else:
            eur_usd = Fraction(1)
        return (major_amount / fixing['rate']) * eur_usd, fixing['date']
    raise SystemExit('unknown FX quote %s' % fixing['quote'])


# ---------------------------------------------------------------- engine

VALUE_KINDS = {
    'conv7': 'conv', 'pre_conv': 'conv',
    'rev14': 'rev', 'pre_rev': 'rev',
    'ord14': 'ord', 'pre_ord': 'ord',
    'rfd14': 'rfd', 'pre_rfd': 'rfd',
    'conv': 'conv', 'rev': 'rev', 'ord': 'ord', 'rfd': 'rfd',
}


def metric_value_kind(code):
    code = norm_text(code).lower()
    if code in VALUE_KINDS:
        return VALUE_KINDS[code]
    m = re.match(r'^pre_([a-z]+)', code)
    if m:
        return m.group(1)
    m = re.match(r'^([a-z]+)', code)
    if m:
        return m.group(1)
    return code


def in_force(status):
    return norm_text(status).upper() == 'IN FORCE'


def window_rulings_for(corpus):
    """H5.2: per experiment code -> {'ruling', 'aborted', 'end_local'}."""
    per = {}
    for row in corpus.window_rulings:
        code = corpus.canonical_experiment(row.get('experiment'))
        if not in_force(row.get('status')):
            continue
        ruling = norm_text(row.get('ruling')).upper()
        info = corpus.experiments.get(code)
        if info is None:
            continue
        state = per.setdefault(code, {
            'ruling': 'NONE', 'aborted': False,
            'end_local': info['end_local'], 'start_local': info['start_local'],
        })
        state['ruling'] = ruling
        if ruling in ('EXTENDED', 'SHORTENED'):
            revised = norm_text(row.get('revised_end_local'))
            if revised and revised != '-':
                state['end_local'] = datetime.fromisoformat(revised)
        if ruling == 'ABORTED':
            state['aborted'] = True
    return per


def registered_units(corpus, ledger):
    """H4: registry ids, retired accounts ignored, main registry wins."""
    registered = {}
    retired = ledger.from_ids_effective(corpus.data_cutoff)
    main_path = find_data_file(corpus.dir, 'registry_main')
    if os.path.exists(main_path):
        with open(main_path, encoding='utf-8', newline='') as fh:
            for row in csv.DictReader(fh):
                uid = norm_id(row.get('unit_id'))
                if not uid or uid in retired:
                    continue
                registered[uid] = norm_text(row.get('account_type')).lower()
    legacy_path = find_data_file(corpus.dir, 'registry_legacy')
    if os.path.exists(legacy_path):
        with open(legacy_path, encoding='utf-8', newline='') as fh:
            for row in csv.DictReader(fh, delimiter='\t'):
                uid = norm_id(row.get('UNIT'))
                if not uid or uid in retired:
                    continue
                if uid in registered:
                    continue
                registered[uid] = norm_text(row.get('AccountType')).lower()
    return registered


def unit_rulings(corpus, ledger):
    """H4.3: U-1 rulings resolved at the data cutoff."""
    excluded = set()
    reinstated = set()
    for row in corpus.unit_rulings:
        if not in_force(row.get('status')):
            continue
        token = norm_id(row.get('unit_token'))
        unit, _hops = ledger.resolve(token, corpus.data_cutoff)
        ruling = norm_text(row.get('ruling')).upper()
        if ruling == 'EXCLUDE':
            excluded.add(unit)
        elif ruling == 'REINSTATE':
            reinstated.add(unit)
    return excluded, reinstated


def internal_units(corpus, ledger):
    out = set()
    for token in corpus.internal_units_raw:
        unit, _hops = ledger.resolve(token, corpus.data_cutoff)
        out.add(unit)
    return out


def eligibility_reason(unit, registered, excluded, reinstated, internal):
    if unit not in registered:
        return 'UNREGISTERED'
    if unit in excluded:
        return 'RULING_EXCLUDED'
    if unit in internal:
        return 'INTERNAL_LIST'
    account = 'human' if unit in reinstated else registered[unit]
    if account != 'human':
        return account.upper()
    return None


def metric_configs(corpus, exp_code):
    """H9.1, H9.2: registry rows amended by Table A-1."""
    registry = corpus.registry()
    codes = sorted(registry.keys())
    configs = {}
    for code in codes:
        rec = registry[code]
        cfg = {
            'code': code,
            'kind': norm_text(rec.get('kind')).lower(),
            'attribution_days': to_int(rec.get('attribution_days')),
            'winsor_pct': norm_text(rec.get('winsor_pct')),
            'cuped': parse_bool(rec.get('cuped')),
            'covariate': norm_text(rec.get('covariate')),
            'role': norm_text(rec.get('role')).lower(),
            'higher_is_better': parse_bool(rec.get('higher_is_better')),
            'numerator': norm_text(rec.get('numerator')),
            'denominator': norm_text(rec.get('denominator')),
            'amendments': [],
        }
        if cfg['winsor_pct'] in ('', '-'):
            cfg['winsor_pct'] = None
        if cfg['covariate'] in ('', '-'):
            cfg['covariate'] = None
        if cfg['numerator'] in ('', '-'):
            cfg['numerator'] = None
        if cfg['denominator'] in ('', '-'):
            cfg['denominator'] = None
        if cfg['attribution_days'] is None:
            cfg['attribution_days'] = 0
        cfg['cuped'] = bool(cfg['cuped'] and cfg['covariate'])
        configs[code] = cfg

    def apply(amp):
        code = norm_text(amp.get('metric')).lower()
        if code not in configs:
            return
        cfg = configs[code]
        field = norm_text(amp.get('field')).lower()
        if field not in ('kind', 'attribution_days', 'winsor_pct', 'cuped', 'covariate',
                         'role', 'higher_is_better', 'numerator', 'denominator'):
            return
        value = norm_text(amp.get('new_value'))
        if field == 'attribution_days':
            cfg['attribution_days'] = to_int(value) or 0
        elif field == 'winsor_pct':
            if value in ('', '-'):
                cfg['winsor_pct'] = None
            else:
                cfg['winsor_pct'] = value
        elif field == 'cuped':
            cfg['cuped'] = parse_bool(value)
        elif field == 'covariate':
            cfg['covariate'] = None if value in ('', '-') else value.lower()
        elif field == 'kind':
            cfg['kind'] = value.lower()
        elif field == 'role':
            cfg['role'] = value.lower()
        elif field == 'higher_is_better':
            cfg['higher_is_better'] = parse_bool(value)
        elif field == 'numerator':
            cfg['numerator'] = None if value in ('', '-') else value.lower()
        elif field == 'denominator':
            cfg['denominator'] = None if value in ('', '-') else value.lower()
        cfg['amendments'].append(norm_text(amp.get('amendment_id')))

    amps = [a for a in corpus.amendments if in_force(a.get('status'))]
    for amp in amps:
        if norm_text(amp.get('experiment')).lower() == 'all':
            apply(amp)
    for amp in amps:
        code = corpus.canonical_experiment(amp.get('experiment'))
        if norm_text(amp.get('experiment')).lower() != 'all' and code == exp_code:
            apply(amp)
    for cfg in configs.values():
        cfg['cuped'] = bool(cfg['cuped'] and cfg['covariate'])
    return configs


def sample_variance(values):
    n = len(values)
    if n < 2:
        return Fraction(0)
    mean = sum(values) / n
    return sum((v - mean) ** 2 for v in values) / (n - 1)


def sample_covariance(xs, ys):
    n = len(xs)
    if n < 2:
        return Fraction(0)
    mx = sum(xs) / n
    my = sum(ys) / n
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (n - 1)


def nearest_rank(values, pct):
    """H10.2: the value at 1-based position ceil(pct/100 x n) of the sorted values."""
    n = len(values)
    if n == 0:
        return None
    pos = int(math.ceil(Fraction(pct) / 100 * n))
    if pos < 1:
        pos = 1
    if pos > n:
        pos = n
    return values[pos - 1]


def chi2_sf(chi2, dof):
    """Upper tail of the chi-square distribution (H12 formulas for 1..3 dof)."""
    if dof == 1:
        return math.erfc(math.sqrt(chi2 / 2.0))
    if dof == 2:
        return math.exp(-chi2 / 2.0)
    if dof == 3:
        return math.erfc(math.sqrt(chi2 / 2.0)) + \
            math.sqrt(2.0 * chi2 / math.pi) * math.exp(-chi2 / 2.0)
    # general regularised upper incomplete gamma for even/odd dof
    half = dof / 2.0
    x = chi2 / 2.0
    if x <= 0:
        return 1.0
    # series for x < half+1, continued fraction otherwise
    if x < half + 1.0:
        term = 1.0 / half
        total = term
        k = half
        while True:
            k += 1.0
            term *= x / k
            total += term
            if abs(term) < abs(total) * 1e-16:
                break
        return total * math.exp(-x + half * math.log(x) - math.lgamma(half))
    # continued fraction (Lentz)
    tiny = 1e-300
    b = x + 1.0 - half
    c = 1.0 / tiny
    d = 1.0 / b
    h = d
    for i in range(1, 500):
        an = -i * (i - half)
        b += 2.0
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-16:
            break
    return math.exp(-x + half * math.log(x) - math.lgamma(half)) * h


# ---------------------------------------------------------------- main run

def run(data_dir, out_dir):
    corpus = Corpus(data_dir)
    ledger = Ledger(find_data_file(data_dir, 'links'))
    cutoff = corpus.data_cutoff

    exposure_rows, order_rows, lineage = read_all_feeds(corpus, ledger)
    exposure_win = pick_winners(exposure_rows)
    order_win = pick_winners(order_rows)

    # ---- dedup counters and lineage
    dedup = {}
    for stream, rows, winners in (('exposure', exposure_rows, exposure_win),
                                  ('order', order_rows, order_win)):
        live_word = STREAM_STATUS[stream][0]
        dead_word = STREAM_STATUS[stream][1]
        live = sum(1 for r in winners.values() if r['live'])
        dead = sum(1 for r in winners.values() if not r['live'])
        keys = {'exposure': ('live', 'voided'), 'order': ('live', 'cancelled')}
        live_key, dead_key = keys[stream]
        dedup[stream] = {
            'rows_read': len(rows),
            'duplicate_rows_dropped': len(rows) - len(winners),
            live_key: live,
            dead_key: dead,
        }
        kept = set(r['seq'] for r in winners.values() if r['live'])
        for shard in corpus.catalog['shards']:
            if shard['stream'] != stream:
                continue
    # kept per shard: count rows whose seq is a kept winner
    kept_by_shard = defaultdict(int)
    rows_by_shard = defaultdict(int)
    for rec in exposure_rows + order_rows:
        rows_by_shard[rec['shard']] += 1
    for rec in list(exposure_win.values()) + list(order_win.values()):
        if rec['live']:
            kept_by_shard[rec['shard']] += 1
    for shard in corpus.catalog['shards']:
        lineage[shard['file']]['rows'] = rows_by_shard[shard['file']]
        lineage[shard['file']]['kept'] = kept_by_shard[shard['file']]

    # ---- orders valuation
    orders_by_id = order_win
    refund_outcomes, held = apply_refund_journal(corpus, orders_by_id)
    refunds_by_order = defaultdict(list)
    for refund_id, (order_id, amount) in held.items():
        refunds_by_order[order_id].append(amount)

    live_orders = []
    for order in orders_by_id.values():
        if not order['live'] or order['ts'] >= cutoff:
            continue
        unit, _hops = ledger.resolve(order['unit_token'], order['ts'])
        amount_minor = amount_to_minor(corpus, order['amount'], order['currency'],
                                       order.get('amount_unit', 'minor'))
        refunded = sum(refunds_by_order.get(order['id'], []), Fraction(0))
        net = amount_minor - refunded
        if net < 0:
            net = Fraction(0)
        refunded_minor = amount_minor - net
        digits = corpus.minor_units.get(order['currency'], 2)
        major = amount_minor / (10 ** digits)
        net_major = net / (10 ** digits)
        rfd_major = refunded_minor / (10 ** digits)
        day = order['ts'].astimezone(timezone.utc).date()
        usd_net, fx_date = usd_value(corpus, net_major, order['currency'], day)
        usd_rfd, _fx2 = usd_value(corpus, rfd_major, order['currency'], day)
        live_orders.append({
            'id': order['id'],
            'unit': unit,
            'currency': order['currency'],
            'amount_minor': amount_minor,
            'refund_minor': refunded_minor,
            'net_minor': net,
            'ts': order['ts'],
            'fx_date': fx_date,
            'usd_net': round_half_even_frac(usd_net, 6),
            'usd_refunded': round_half_even_frac(usd_rfd, 6),
        })
    live_orders.sort(key=lambda o: o['id'])
    orders_by_unit = defaultdict(list)
    for order in live_orders:
        orders_by_unit[order['unit']].append(order)
    for unit in orders_by_unit:
        orders_by_unit[unit].sort(key=lambda o: o['ts'])

    # ---- windows and scope
    in_scope = []
    for token in corpus.in_scope:
        code = corpus.canonical_experiment(token)
        if code in corpus.experiments and code not in in_scope:
            in_scope.append(code)
    in_scope.sort()
    in_scope_set = set(in_scope)
    rulings = window_rulings_for(corpus)
    aborted = set(code for code in in_scope if rulings.get(code, {}).get('aborted'))
    analysed = [code for code in in_scope if code not in aborted]
    analysed.sort()

    window = {}
    for code in in_scope:
        info = corpus.experiments[code]
        state = rulings.get(code)
        end_local = state['end_local'] if state else info['end_local']
        tz = timezone(timedelta(minutes=info['tz_minutes']))
        start_local = info['start_local'].replace(tzinfo=tz)
        end_utc = end_local.replace(tzinfo=tz).astimezone(timezone.utc)
        window[code] = {
            'start_utc': start_local.astimezone(timezone.utc),
            'end_utc': end_utc,
            'ruling': state['ruling'] if state else 'NONE',
        }

    # ---- live exposures of in-scope experiments
    dedup['exposure']['out_of_scope'] = 0
    dedup['exposure']['unmapped_variant'] = 0
    exposures_by_exp = defaultdict(list)   # experiment -> list of live mapped exposures
    for rec in exposure_win.values():
        if not rec['live']:
            continue
        if rec['experiment'] not in in_scope_set:
            dedup['exposure']['out_of_scope'] += 1
            continue
        arm = corpus.arm_for(rec['experiment'], rec['variant'])
        if arm is None:
            dedup['exposure']['unmapped_variant'] += 1
            continue
        unit, _hops = ledger.resolve(rec['unit_token'], rec['ts'])
        exposures_by_exp[rec['experiment']].append({
            'unit': unit, 'arm': arm, 'ts': rec['ts'],
        })

    # ---- eligibility
    registered = registered_units(corpus, ledger)
    excluded_units_set, reinstated_set = unit_rulings(corpus, ledger)
    internal_set = internal_units(corpus, ledger)

    # ---- participants
    participants = {}      # experiment -> {unit: {...}}
    candidates = []        # excluded candidates
    for code in analysed:
        start = window[code]['start_utc']
        end = window[code]['end_utc']
        by_unit = defaultdict(list)
        for exp in exposures_by_exp.get(code, []):
            if exp['ts'] >= end:
                continue
            by_unit[exp['unit']].append(exp)
        parts = {}
        for unit in sorted(by_unit.keys()):
            exps = by_unit[unit]
            reason = eligibility_reason(unit, registered, excluded_units_set,
                                       reinstated_set, internal_set)
            arms = set(e['arm'] for e in exps)
            if reason is None and len(arms) > 1:
                reason = 'CROSSOVER'
            if reason is None and min(e['ts'] for e in exps) < start:
                reason = 'PRE_START'
            if reason is not None:
                candidates.append({'experiment': code, 'unit_id': unit, 'reason': reason})
                continue
            parts[unit] = {
                'arm': sorted(arms)[0],
                'fe': min(e['ts'] for e in exps),
                'exposures': len(exps),
            }
        participants[code] = parts
    candidates.sort(key=lambda c: (c['experiment'], c['unit_id']))

    # ---- per experiment analysis
    analysis = {}
    for code in analysed:
        analysis[code] = analyse_experiment(corpus, code, participants[code],
                                           orders_by_unit, window[code])
    return {
        'corpus': corpus, 'ledger': ledger,
        'dedup': dedup, 'lineage': lineage,
        'refund_outcomes': refund_outcomes, 'live_orders': live_orders,
        'participants': participants, 'candidates': candidates,
        'analysis': analysis, 'in_scope': in_scope, 'aborted': aborted,
        'window': window, 'analysed': analysed,
        'registered': registered,
    }


def window_values(orders, lo, hi):
    """H9.4 per-participant values over [lo, hi)."""
    conv = 0
    rev = Fraction(0)
    ordc = 0
    rfd = Fraction(0)
    for order in orders:
        ts = order['ts']
        if ts < lo:
            continue
        if ts >= hi:
            break
        if order['net_minor'] > 0:
            conv = 1
            ordc += 1
        rev += order['usd_net']
        rfd += order['usd_refunded']
    return {'conv': conv, 'rev': rev, 'ord': ordc, 'rfd': rfd}


def analyse_experiment(corpus, code, parts, orders_by_unit, window):
    cutoff = corpus.data_cutoff
    configs = metric_configs(corpus, code)
    info = corpus.experiments[code]
    allocation = corpus.allocation.get(code, [])
    arm_roles = {a['arm']: a['role'] for a in allocation}
    control_arm = None
    for arm in sorted(arm_roles):
        if arm_roles[arm] == 'control':
            control_arm = arm
    treatment_arms = [a for a in sorted(arm_roles) if arm_roles[a] == 'treatment']
    holdout_arms = [a for a in sorted(arm_roles) if arm_roles[a] == 'holdout']
    weights = {a['arm']: a['weight_pct'] for a in allocation}

    # SRM (H12): observed counts over all arms including holdout
    observed = {a: 0 for a in sorted(arm_roles)}
    for unit, p in parts.items():
        if p['arm'] in observed:
            observed[p['arm']] += 1
    total = sum(observed.values())
    chi2 = Fraction(0)
    srm_rows = []
    for arm in sorted(observed):
        w = to_num(weights.get(arm)) or Fraction(0)
        expected = Fraction(total) * w / 100
        chi2 += (Fraction(observed[arm]) - expected) ** 2 / expected if expected != 0 else Fraction(0)
        srm_rows.append({'arm': arm, 'weight_pct': weights.get(arm),
                         'observed': observed[arm], 'expected': expected})
    dof = max(len(observed) - 1, 1)
    srm_alpha = corpus.param_num('srm_alpha')
    srm_p = chi2_sf(float(chi2), dof) if total > 0 else 1.0
    srm_fail = srm_p < float(srm_alpha)

    analysed_arms = [control_arm] + treatment_arms
    metrics = {}
    for metric_code in sorted(configs):
        cfg = configs[metric_code]
        metrics[metric_code] = compute_metric(corpus, code, cfg, parts, orders_by_unit,
                                              analysed_arms, control_arm)
    return {
        'code': code, 'info': info, 'configs': configs, 'metrics': metrics,
        'control_arm': control_arm, 'treatment_arms': treatment_arms,
        'holdout_arms': holdout_arms, 'arm_roles': arm_roles, 'weights': weights,
        'srm_rows': srm_rows, 'chi2': chi2, 'dof': dof, 'srm_p': srm_p,
        'srm_fail': srm_fail, 'observed': observed,
    }


def compute_metric(corpus, exp_code, cfg, parts, orders_by_unit, analysed_arms, control_arm):
    cutoff = corpus.data_cutoff
    pre_days = corpus.pre_period_days
    code = cfg['code']
    kind = cfg['kind']
    days = cfg['attribution_days']
    matured = []
    for unit in sorted(parts):
        p = parts[unit]
        if p['arm'] not in analysed_arms:
            continue
        if p['fe'] + timedelta(days=days) <= cutoff:
            matured.append((unit, p['arm'], p['fe']))
    matured.sort()

    # per participant outcome value and covariate
    ys = {}
    xs = {}
    if kind != 'ratio':
        y_kind = metric_value_kind(code)
        for unit, arm, fe in matured:
            orders = orders_by_unit.get(unit, [])
            values = window_values(orders, fe, fe + timedelta(days=days))
            ys[unit] = values[y_kind]
            if cfg['cuped']:
                cov_kind = metric_value_kind(cfg['covariate'])
                pre = window_values(orders, fe - timedelta(days=pre_days), fe)
                xs[unit] = pre[cov_kind]

    pooled_units = [u for u, a, fe in matured]
    by_arm = defaultdict(list)
    for unit, arm, fe in matured:
        by_arm[arm].append(unit)

    result = {
        'cfg': cfg, 'n_pooled': len(matured), 'by_arm': by_arm,
        'ys': ys, 'xs': xs, 'kind': kind,
    }

    if kind == 'ratio':
        num_kind = metric_value_kind(cfg['numerator'])
        den_kind = metric_value_kind(cfg['denominator'])
        num = {}
        den = {}
        for unit, arm, fe in matured:
            orders = orders_by_unit.get(unit, [])
            values = window_values(orders, fe, fe + timedelta(days=days))
            num[unit] = values[num_kind]
            den[unit] = values[den_kind]
        result['num'] = num
        result['den'] = den
        result['values'] = {unit: None for unit in pooled_units}
        result['adj'] = {unit: None for unit in pooled_units}
        return result

    # winsorization (H10.2) for mean metrics with a winsor_pct
    values = dict(ys)
    cov_values = dict(xs)
    cap = None
    cov_cap = None
    capped_units = 0
    pct = cfg['winsor_pct'] if kind != 'binary' else None
    if pct is not None:
        ordered = sorted(values[u] for u in pooled_units)
        cap = nearest_rank(ordered, to_num(pct))
        if cap is not None:
            for unit in pooled_units:
                if values[unit] > cap:
                    values[unit] = cap
                    capped_units += 1
        if cfg['cuped']:
            cov_ordered = sorted(cov_values[u] for u in pooled_units)
            cov_cap = nearest_rank(cov_ordered, to_num(pct))
            if cov_cap is not None:
                for unit in pooled_units:
                    if cov_values[unit] > cov_cap:
                        cov_values[unit] = cov_cap
    result['cap'] = cap
    result['cov_cap'] = cov_cap
    result['capped_units'] = capped_units
    result['values'] = values

    # CUPED (H10.3)
    theta = Fraction(0)
    mean_x = Fraction(0)
    adj = {}
    if cfg['cuped']:
        xs_list = [cov_values[u] for u in pooled_units]
        ys_list = [values[u] for u in pooled_units]
        var_x = sample_variance(xs_list)
        if var_x != 0:
            theta = round_half_even_frac(sample_covariance(ys_list, xs_list) / var_x, 6)
        mean_x = sum(xs_list) / len(xs_list) if xs_list else Fraction(0)
        for unit in pooled_units:
            adj[unit] = values[unit] - theta * (cov_values[unit] - mean_x)
        var_y = sample_variance(ys_list)
        var_adj = sample_variance([adj[u] for u in pooled_units])
        vr = Fraction(100) * (Fraction(1) - var_adj / var_y) if var_y != 0 else Fraction(0)
        result['theta'] = theta
        result['mean_x'] = mean_x
        result['variance_reduction_pct'] = vr
    else:
        for unit in pooled_units:
            adj[unit] = values[unit]
    result['adj'] = adj
    return result


# ---------------------------------------------------------------- statistics


def normal_quantile(p):
    """Standard normal quantile; p in (0, 1)."""
    return NormalDist().inv_cdf(p)


def arm_stats(metric, arm, control=False):
    """Per-arm figures for one metric (H10, H11)."""
    units = metric['by_arm'].get(arm, [])
    n = len(units)
    if metric['kind'] == 'ratio':
        num = [metric['num'][u] for u in units]
        den = [metric['den'][u] for u in units]
        s_num = sum(num, Fraction(0))
        s_den = sum(den, Fraction(0))
        R = (s_num / s_den) if s_den != 0 else Fraction(0)
        if n > 0:
            mx = s_den / n
            my = s_num / n
            s_yy = sample_variance(num)
            s_xx = sample_variance(den)
            s_xy = sample_covariance(den, num)
            V = (Fraction(1) / n) * (s_yy / (mx * mx)
                                     - Fraction(2) * my * s_xy / (mx ** 3)
                                     + my * my * s_xx / (mx ** 4))
        else:
            V = Fraction(0)
        return {'n': n, 'raw_mean': R, 'adj_mean': R, 'variance': V, 'R': R, 'V': V}
    values = [metric['values'][u] for u in units]
    adj = [metric['adj'][u] for u in units]
    raw_mean = sum(values, Fraction(0)) / n if n else Fraction(0)
    adj_mean = sum(adj, Fraction(0)) / n if n else Fraction(0)
    var = sample_variance(adj)
    return {'n': n, 'raw_mean': raw_mean, 'adj_mean': adj_mean, 'variance': var}


def compute_tests(corpus, analysis, decisions_alpha, z_crit):
    """H11: tests of every treatment arm against control on every metric."""
    tests = {}
    for code in sorted(analysis):
        exp = analysis[code]
        control = exp['control_arm']
        for metric_code in sorted(exp['metrics']):
            metric = exp['metrics'][metric_code]
            c_stats = arm_stats(metric, control)
            for arm in exp['treatment_arms']:
                t_stats = arm_stats(metric, arm)
                if metric['kind'] == 'ratio':
                    diff = t_stats['R'] - c_stats['R']
                    se = math.sqrt(float(t_stats['V']) + float(c_stats['V']))
                else:
                    diff = t_stats['adj_mean'] - c_stats['adj_mean']
                    if t_stats['n'] and c_stats['n']:
                        se = math.sqrt(float(t_stats['variance']) / t_stats['n']
                                       + float(c_stats['variance']) / c_stats['n'])
                    else:
                        se = 0.0
                if se > 0:
                    z = float(diff) / se
                    p_value = math.erfc(abs(z) / math.sqrt(2))
                else:
                    z = 0.0
                    p_value = 1.0
                base = c_stats['raw_mean']
                if base != 0:
                    lift = Fraction(100) * diff / base
                    lift_ci_low = 100.0 * (float(diff) - z_crit * se) / float(base)
                    lift_ci_high = 100.0 * (float(diff) + z_crit * se) / float(base)
                else:
                    lift = None
                    lift_ci_low = None
                    lift_ci_high = None
                tests[(code, arm, metric_code)] = {
                    'experiment': code, 'arm': arm, 'metric': metric_code,
                    'role': 'primary' if metric_code == exp['info']['primary_metric']
                            else metric['cfg']['role'],
                    'n_control': c_stats['n'], 'n_treatment': t_stats['n'],
                    'mean_control': c_stats['adj_mean'], 'mean_treatment': t_stats['adj_mean'],
                    'raw_mean_control': c_stats['raw_mean'],
                    'diff': diff, 'se': se, 'z': z, 'p_value': p_value,
                    'ci_low': float(diff) - z_crit * se,
                    'ci_high': float(diff) + z_crit * se,
                    'lift': lift, 'lift_ci_low': lift_ci_low, 'lift_ci_high': lift_ci_high,
                    'base': base, 'kind': metric['kind'],
                    'higher_is_better': metric['cfg']['higher_is_better'],
                }
    return tests


def bh_family(corpus, analysis, tests):
    """H13.1: the primary family and Benjamini-Hochberg q values."""
    family = []
    for code in sorted(analysis):
        exp = analysis[code]
        if exp['srm_fail']:
            continue
        for arm in exp['treatment_arms']:
            key = (code, arm, exp['info']['primary_metric'])
            if key in tests:
                family.append(tests[key])
    family.sort(key=lambda t: (t['p_value'], t['experiment'], t['arm']))
    m = len(family)
    bh_q = corpus.param_num('bh_q')
    q_values = [None] * m
    running = None
    for i in range(m, 0, -1):
        t = family[i - 1]
        value = min(1.0, m * t['p_value'] / i)
        running = value if running is None else min(running, value)
        q_values[i - 1] = running
    for t, q in zip(family, q_values):
        t['q_value'] = q
        t['significant'] = (q <= float(bh_q))
    return family


# ---------------------------------------------------------------- outputs

# ---------------------------------------------------------------- outputs

CONTRACT_FILES = [
    'readout.csv', 'arm_metrics.tsv', 'winsor_caps.psv', 'cuped.json',
    'srm_report.csv', 'bh_family.csv', 'guardrails.csv', 'decisions.json',
    'unit_assignments.csv', 'excluded_units.jsonl', 'identity_resolution.csv',
    'dedup_report.json', 'source_lineage.json', 'refund_outcomes.jsonl',
    'order_valuation.psv', 'metric_config_used.json', 'experiment_windows.xml',
    'portfolio_summary.json', 'variance_vs_published.csv', 'reconciliation.md',
]


def write_text(out_dir, name, text):
    if not text.endswith('\n'):
        text += '\n'
    with open(os.path.join(out_dir, name), 'w', encoding='utf-8', newline='') as fh:
        fh.write(text)
    return text


def write_json(out_dir, name, obj):
    text = json.dumps(obj, sort_keys=True, indent=2)
    return write_text(out_dir, name, text)


def write_jsonl(out_dir, name, rows):
    lines = []
    for row in rows:
        lines.append(json.dumps(row, sort_keys=True))
    return write_text(out_dir, name, '\n'.join(lines) + ('\n' if lines else ''))


def write_delimited(out_dir, name, header, rows, delimiter):
    lines = [delimiter.join(header)]
    for row in rows:
        lines.append(delimiter.join(str(c) for c in row))
    return write_text(out_dir, name, '\n'.join(lines))


def fmt_int(value):
    """An integer count of minor units, written without a decimal point."""
    frac = Fraction(value)
    if frac.denominator == 1:
        return str(frac.numerator)
    scaled = frac * 10 ** 6
    scaled = round_half_even_frac(scaled, 0)
    return str(scaled.numerator)


def six(fr):
    if fr is None:
        return ''
    return fmt6(fr)


def sixf(x):
    if x is None:
        return ''
    return fmt6f(x)


def guardrail_breaches(corpus, tests, analysis):
    """H13.2: breached guardrail metrics per (experiment, arm)."""
    breaches = defaultdict(list)
    rows = []
    alpha = float(corpus.param_num('alpha_two_sided'))
    for code in sorted(analysis):
        exp = analysis[code]
        for arm in exp['treatment_arms']:
            for metric_code in sorted(exp['metrics']):
                cfg = exp['metrics'][metric_code]['cfg']
                if cfg['role'] != 'guardrail':
                    continue
                test = tests.get((code, arm, metric_code))
                if test is None:
                    continue
                margin_raw = corpus.params.get('guardrail_margin_pct.%s' % metric_code)
                margin = to_num(margin_raw) if margin_raw is not None else None
                breach = 'N'
                if margin is not None and test['p_value'] < alpha \
                        and test['lift'] is not None:
                    higher = test['higher_is_better']
                    if higher and test['diff'] < 0 and test['lift'] < -margin:
                        breach = 'Y'
                    if not higher and test['diff'] > 0 and test['lift'] > margin:
                        breach = 'Y'
                if breach == 'Y':
                    breaches[(code, arm)].append(metric_code)
                rows.append({
                    'experiment': code, 'arm': arm, 'metric': metric_code,
                    'lift': test['lift'],
                    'lift_ci_low': test['lift_ci_low'],
                    'lift_ci_high': test['lift_ci_high'],
                    'margin_pct': norm_text(margin_raw),
                    'breach': breach,
                })
    return breaches, rows


def first_pass_decisions(corpus, analysis, tests, breaches, aborted):
    """H13.3: first-pass decision per treatment arm."""
    decisions = {}
    for code in sorted(analysis):
        exp = analysis[code]
        for arm in exp['treatment_arms']:
            primary = exp['info']['primary_metric']
            test = tests.get((code, arm, primary))
            breached = sorted(breaches.get((code, arm), []))
            if exp['srm_fail']:
                decision = 'INVALID_SRM'
            elif breached:
                decision = 'NO_SHIP_GUARDRAIL'
            elif test is not None and test.get('significant'):
                if test['diff'] > 0 if test['higher_is_better'] else test['diff'] < 0:
                    decision = 'SHIP'
                else:
                    decision = 'NO_SHIP'
            else:
                decision = 'INCONCLUSIVE'
            decisions[(code, arm)] = {
                'decision': decision,
                'primary_metric': primary,
                'q_value': test.get('q_value') if test is not None else None,
                'guardrail_breaches': breached,
            }
    for code in sorted(aborted):
        exp_info = corpus.experiments.get(code)
        for arm in [a['arm'] for a in corpus.allocation.get(code, [])
                   if a['role'] == 'treatment']:
            decisions[(code, arm)] = {
                'decision': 'ABORTED',
                'primary_metric': exp_info['primary_metric'] if exp_info else '',
                'q_value': None,
                'guardrail_breaches': [],
            }
    return decisions


def apply_ship_capacity(corpus, analysis, decisions):
    """H13.5: ship capacity per owner team."""
    ships = defaultdict(list)
    for (code, arm), info in decisions.items():
        if info['decision'] != 'SHIP':
            continue
        team = corpus.experiments[code]['owner_team']
        ships[team].append((code, arm))
    deferred = []
    for team, arms in ships.items():
        max_ship = corpus.ship_capacity.get(team)
        if max_ship is None or len(arms) <= max_ship:
            continue
        ranked = sorted(arms, key=lambda ca: (
            decisions[(ca[0], ca[1])]['q_value'], '%s/%s' % ca))
        for code, arm in ranked[max_ship:]:
            decisions[(code, arm)]['decision'] = 'SHIP_DEFERRED'
            deferred.append('%s/%s' % (code, arm))
    deferred.sort()
    return decisions, deferred




def write_all_outputs(out_dir, run_result, tests, family, breaches, guardrail_rows,
                      decisions, deferred):
    corpus = run_result['corpus']
    analysis = run_result['analysis']
    aborted = run_result['aborted']
    in_scope = run_result['in_scope']
    window = run_result['window']
    alpha = float(corpus.param_num('alpha_two_sided'))

    # ---- readout.csv
    test_rows = []
    for (code, arm, metric), test in sorted(tests.items()):
        primary = metric == corpus.experiments[code]['primary_metric']
        significant = ''
        if primary:
            if not analysis[code]['srm_fail']:
                significant = 'Y' if test.get('significant') else 'N'
        else:
            significant = 'Y' if test['p_value'] < alpha else 'N'
        test_rows.append([
            code, arm, metric, test['role'],
            test['n_control'], test['n_treatment'],
            six(test['mean_control']), six(test['mean_treatment']), six(test['diff']),
            six(test['lift']), sixf(test['se']), sixf(test['z']), fmt_exp(test['p_value']),
            sixf(test['ci_low']), sixf(test['ci_high']),
            fmt_exp(test['q_value']) if test.get('q_value') is not None else '',
            significant,
        ])
    write_delimited(out_dir, 'readout.csv',
                    ['experiment', 'arm', 'metric', 'role', 'n_control', 'n_treatment',
                     'mean_control', 'mean_treatment', 'diff', 'lift_pct', 'se', 'z',
                     'p_value', 'ci_low', 'ci_high', 'q_value', 'significant'],
                    test_rows, ',')

    # ---- arm_metrics.tsv
    arm_rows = []
    for code in sorted(analysis):
        exp = analysis[code]
        for metric_code in sorted(exp['metrics']):
            metric = exp['metrics'][metric_code]
            for arm in [exp['control_arm']] + exp['treatment_arms']:
                if arm is None:
                    continue
                stats = arm_stats(metric, arm)
                arm_rows.append([
                    code, arm, metric_code, stats['n'],
                    six(stats['raw_mean']), six(stats['adj_mean']), six(stats['variance']),
                ])
    write_delimited(out_dir, 'arm_metrics.tsv',
                    ['experiment', 'arm', 'metric', 'n', 'raw_mean', 'adj_mean', 'variance'],
                    arm_rows, '\t')

    # ---- winsor_caps.psv
    cap_rows = []
    for code in sorted(analysis):
        exp = analysis[code]
        for metric_code in sorted(exp['metrics']):
            metric = exp['metrics'][metric_code]
            cfg = metric['cfg']
            if metric['kind'] == 'binary' or cfg['winsor_pct'] is None:
                continue
            cap_rows.append([
                code, metric_code, cfg['winsor_pct'], metric['n_pooled'],
                six(metric.get('cap')),
                six(metric.get('cov_cap')) if cfg['cuped'] else '',
                metric['capped_units'],
            ])
    write_delimited(out_dir, 'winsor_caps.psv',
                    ['experiment', 'metric', 'winsor_pct', 'n_pooled', 'cap',
                     'covariate_cap', 'capped_units'],
                    cap_rows, '|')

    # ---- cuped.json
    cuped = {}
    for code in sorted(analysis):
        exp = analysis[code]
        for metric_code in sorted(exp['metrics']):
            metric = exp['metrics'][metric_code]
            if not metric['cfg']['cuped']:
                continue
            cuped.setdefault(code, {})[metric_code] = {
                'theta': six(metric.get('theta', Fraction(0))),
                'mean_x': six(metric.get('mean_x', Fraction(0))),
                'variance_reduction_pct': six(metric.get('variance_reduction_pct',
                                                         Fraction(0))),
            }
    write_json(out_dir, 'cuped.json', cuped)

    # ---- srm_report.csv
    srm_rows = []
    for code in sorted(analysis):
        exp = analysis[code]
        for row in exp['srm_rows']:
            srm_rows.append([
                code, row['arm'], exp['arm_roles'].get(row['arm'], ''),
                row['weight_pct'] if row['weight_pct'] is not None else '',
                row['observed'], six(row['expected']), six(exp['chi2']), exp['dof'],
                fmt_exp(exp['srm_p']), 'FAIL' if exp['srm_fail'] else 'PASS',
            ])
    write_delimited(out_dir, 'srm_report.csv',
                    ['experiment', 'arm', 'role', 'weight_pct', 'observed', 'expected',
                     'chi2', 'dof', 'p_value', 'status'],
                    srm_rows, ',')

    # ---- bh_family.csv
    bh_rows = []
    for i, test in enumerate(family, start=1):
        bh_rows.append([
            i, test['experiment'], test['arm'], test['metric'],
            fmt_exp(test['p_value']), fmt_exp(test['q_value']),
            'Y' if test.get('significant') else 'N',
        ])
    write_delimited(out_dir, 'bh_family.csv',
                    ['rank', 'experiment', 'arm', 'metric', 'p_value', 'q_value',
                     'significant'],
                    bh_rows, ',')

    # ---- guardrails.csv
    guard_rows = []
    for row in guardrail_rows:
        guard_rows.append([
            row['experiment'], row['arm'], row['metric'],
            six(row['lift']), sixf(row['lift_ci_low']), sixf(row['lift_ci_high']),
            row['margin_pct'], row['breach'],
        ])
    write_delimited(out_dir, 'guardrails.csv',
                    ['experiment', 'arm', 'metric', 'lift_pct', 'lift_ci_low',
                     'lift_ci_high', 'margin_pct', 'breach'],
                    guard_rows, ',')

    # ---- decisions.json
    decisions_obj = {}
    for (code, arm) in sorted(decisions):
        info = decisions[(code, arm)]
        q = info['q_value']
        decisions_obj.setdefault(code, {})[arm] = {
            'decision': info['decision'],
            'primary_metric': info['primary_metric'],
            'q_value': fmt_exp(q) if q is not None else None,
            'guardrail_breaches': info['guardrail_breaches'],
        }
    write_json(out_dir, 'decisions.json', decisions_obj)

    # ---- unit_assignments.csv
    ua_rows = []
    for code in sorted(run_result['participants']):
        parts = run_result['participants'][code]
        for unit in sorted(parts):
            p = parts[unit]
            ua_rows.append([code, unit, p['arm'], fmt_ts(p['fe']), p['exposures']])
    write_delimited(out_dir, 'unit_assignments.csv',
                    ['experiment', 'unit_id', 'arm', 'first_exposure_utc', 'exposures'],
                    ua_rows, ',')

    # ---- excluded_units.jsonl
    excluded_rows = []
    for cand in run_result['candidates']:
        excluded_rows.append({
            'experiment': cand['experiment'],
            'reason': cand['reason'],
            'unit_id': cand['unit_id'],
        })
    write_jsonl(out_dir, 'excluded_units.jsonl', excluded_rows)

    # ---- identity_resolution.csv
    ledger = run_result['ledger']
    id_rows = []
    for from_id in sorted(ledger.links):
        unit, hops = ledger.resolve(from_id, corpus.data_cutoff)
        id_rows.append([from_id, unit, hops])
    write_delimited(out_dir, 'identity_resolution.csv',
                    ['from_id', 'unit_id', 'hops'], id_rows, ',')

    # ---- dedup_report.json
    dedup_obj = {
        'exposure': {
            'rows_read': run_result['dedup']['exposure']['rows_read'],
            'duplicate_rows_dropped':
                run_result['dedup']['exposure']['duplicate_rows_dropped'],
            'voided': run_result['dedup']['exposure']['voided'],
            'live': run_result['dedup']['exposure']['live'],
            'out_of_scope': run_result['dedup']['exposure']['out_of_scope'],
            'unmapped_variant': run_result['dedup']['exposure']['unmapped_variant'],
        },
        'order': {
            'rows_read': run_result['dedup']['order']['rows_read'],
            'duplicate_rows_dropped':
                run_result['dedup']['order']['duplicate_rows_dropped'],
            'cancelled': run_result['dedup']['order']['cancelled'],
            'live': run_result['dedup']['order']['live'],
        },
    }
    write_json(out_dir, 'dedup_report.json', dedup_obj)

    # ---- source_lineage.json
    lineage = {}
    for shard in corpus.catalog['shards']:
        info = run_result['lineage'][shard['file']]
        lineage[shard['file']] = {
            'stream': info['stream'], 'rows': info['rows'], 'kept': info['kept'],
        }
    write_json(out_dir, 'source_lineage.json', lineage)

    # ---- refund_outcomes.jsonl
    refund_rows = []
    for outcome in run_result['refund_outcomes']:
        refund_rows.append({
            'journal': outcome['journal'], 'seq': outcome['seq'],
            'kind': outcome['kind'], 'refund_id': outcome['refund_id'],
            'order_id': outcome['order_id'], 'outcome': outcome['outcome'],
        })
    write_jsonl(out_dir, 'refund_outcomes.jsonl', refund_rows)

    # ---- order_valuation.psv
    order_rows = []
    for order in run_result['live_orders']:
        order_rows.append([
            order['id'], order['unit'], order['currency'],
            fmt_int(order['amount_minor']), fmt_int(order['refund_minor']),
            fmt_int(order['net_minor']),
            order['fx_date'].isoformat() if order['fx_date'] else '',
            six(order['usd_net']), six(order['usd_refunded']),
        ])
    write_delimited(out_dir, 'order_valuation.psv',
                    ['order_id', 'unit_id', 'currency', 'amount_minor', 'refund_minor',
                     'net_minor', 'fx_date', 'usd_net', 'usd_refunded'],
                    order_rows, '|')

    # ---- metric_config_used.json
    config_obj = {'registry_version': corpus.registry_version, 'fx_sheet': corpus.fx_sheet}
    for code in sorted(analysis):
        exp = analysis[code]
        config_obj[code] = {}
        for metric_code in sorted(exp['configs']):
            cfg = exp['configs'][metric_code]
            config_obj[code][metric_code] = {
                'kind': cfg['kind'],
                'attribution_days': cfg['attribution_days'],
                'winsor_pct': cfg['winsor_pct'],
                'cuped': cfg['cuped'],
                'covariate': cfg['covariate'],
                'role': cfg['role'],
                'higher_is_better': cfg['higher_is_better'],
                'numerator': cfg['numerator'],
                'denominator': cfg['denominator'],
                'amendments': cfg['amendments'],
            }
    write_json(out_dir, 'metric_config_used.json', config_obj)

    # ---- experiment_windows.xml
    xml_lines = ['<?xml version="1.0" encoding="UTF-8"?>',
                 '<portfolio id="%s">' % xml_escape(corpus.portfolio_id)]
    for code in in_scope:
        info = corpus.experiments[code]
        status = 'ABORTED' if code in aborted else 'ANALYSED'
        xml_lines.append('  <experiment code="%s" tz_offset="%s" owner_team="%s" '
                         'start_utc="%s" end_utc="%s" ruling="%s" status="%s"/>' % (
                             xml_escape(code), xml_escape(info['tz_offset']),
                             xml_escape(info['owner_team']),
                             fmt_ts(window[code]['start_utc']),
                             fmt_ts(window[code]['end_utc']),
                             window[code]['ruling'], status))
    xml_lines.append('</portfolio>')
    write_text(out_dir, 'experiment_windows.xml', '\n'.join(xml_lines))

    # ---- portfolio_summary.json
    decision_counts = Counter()
    for info in decisions.values():
        decision_counts[info['decision']] += 1
    usd_net_total = sum((o['usd_net'] for o in run_result['live_orders']), Fraction(0))
    summary = {
        'portfolio_id': corpus.portfolio_id,
        'registry_version': corpus.registry_version,
        'experiments_analysed': len(analysis),
        'experiments_aborted': len(aborted),
        'srm_failures': sum(1 for code in analysis if analysis[code]['srm_fail']),
        'family_size': len(family),
        'decisions': {k: decision_counts[k] for k in sorted(decision_counts)},
        'deferred_arms': deferred,
        'participants': sum(len(p) for p in run_result['participants'].values()),
        'excluded_candidates': len(run_result['candidates']),
        'live_orders': len(run_result['live_orders']),
        'usd_net_total': six(usd_net_total),
    }
    write_json(out_dir, 'portfolio_summary.json', summary)

    # ---- variance_vs_published.csv
    published = read_published(corpus)
    pub_all = published.get('ALL', {})
    corr_signif = {}
    for (code, arm, metric), test in tests.items():
        primary = metric == corpus.experiments[code]['primary_metric']
        if primary and analysis[code]['srm_fail']:
            corr_signif[(code, arm, metric)] = 'N'
        elif primary:
            corr_signif[(code, arm, metric)] = 'Y' if test.get('significant') else 'N'
        else:
            corr_signif[(code, arm, metric)] = 'Y' if test['p_value'] < alpha else 'N'
    keys = set(pub_all) | set(corr_signif)
    var_rows = []
    for code, arm, metric in sorted(keys):
        pub = pub_all.get((code, arm, metric))
        corrected = (code, arm, metric) in corr_signif
        corr_diff = tests.get((code, arm, metric))
        pub_sig = pub['significant'] if pub else ''
        corr_sig = corr_signif.get((code, arm, metric), '')
        if pub is None and corrected:
            status = 'NEW'
        elif pub is not None and not corrected:
            status = 'DROPPED'
        elif (pub_sig or 'N') != (corr_sig or 'N'):
            status = 'FLIPPED'
        else:
            status = 'SAME'
        var_rows.append([
            code, arm, metric,
            sixf(pub['diff_value']) if pub else '',
            six(corr_diff['diff']) if corr_diff else '',
            pub_sig, corr_sig, status,
        ])
    write_delimited(out_dir, 'variance_vs_published.csv',
                    ['experiment', 'arm', 'metric', 'published_diff', 'corrected_diff',
                     'published_significant', 'corrected_significant', 'status'],
                    var_rows, ',')

    # ---- reconciliation.md
    lines = ['# Portfolio %s readout reconciliation' % corpus.portfolio_id, '',
             '| experiment | arm | published_decision | corrected_decision |',
             '|---|---|---|---|']
    for code in in_scope:
        primary = corpus.experiments[code]['primary_metric']
        arms = [a['arm'] for a in corpus.allocation.get(code, []) if a['role'] == 'treatment']
        for arm in sorted(arms):
            pub = pub_all.get((code, arm, primary))
            if pub is None:
                pub_decision = 'MISSING'
            elif pub['significant'] == 'Y' and pub['diff_value'] > 0:
                pub_decision = 'SHIP'
            elif pub['significant'] == 'Y':
                pub_decision = 'NO_SHIP'
            else:
                pub_decision = 'INCONCLUSIVE'
            corrected_decision = decisions.get((code, arm), {}).get('decision', 'MISSING')
            lines.append('| %s | %s | %s | %s |' % (code, arm, pub_decision,
                                                    corrected_decision))
    write_text(out_dir, 'reconciliation.md', '\n'.join(lines))

    # ---- manifest.json
    manifest = {'files': []}
    for name in CONTRACT_FILES:
        data = open(os.path.join(out_dir, name), 'rb').read()
        manifest['files'].append({
            'name': name,
            'bytes': len(data),
            'sha256': hashlib.sha256(data).hexdigest(),
        })
    write_json(out_dir, 'manifest.json', manifest)


def xml_escape(value):
    return (str(value).replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace('"', '&quot;'))


def read_published(corpus):
    """The published readout, keyed by cut, then by (experiment, arm, metric)."""
    path = os.path.join(corpus.dir, corpus.published_name)
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding='utf-8', newline='') as fh:
        for row in csv.DictReader(fh):
            cut = norm_text(row.get('cut'))
            key = (norm_text(row.get('experiment')), norm_text(row.get('arm')),
                   norm_text(row.get('metric')).lower())
            out.setdefault(cut, {})[key] = {
                'diff': norm_text(row.get('diff')),
                'diff_value': float(norm_text(row.get('diff')) or 0),
                'significant': norm_text(row.get('significant')),
            }
    return out


def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: run_readout.py DATA_DIR OUT_DIR\n')
        return 2
    data_dir, out_dir = argv[1], argv[2]
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    result = run(data_dir, out_dir)
    corpus = result['corpus']
    alpha = float(corpus.param_num('alpha_two_sided'))
    z_crit = normal_quantile(1 - alpha / 2.0)
    tests = compute_tests(corpus, result['analysis'], alpha, z_crit)
    family = bh_family(corpus, result['analysis'], tests)
    breaches, guardrail_rows = guardrail_breaches(corpus, tests, result['analysis'])
    decisions = first_pass_decisions(corpus, result['analysis'], tests, breaches,
                                    result['aborted'])
    decisions, deferred = apply_ship_capacity(corpus, result['analysis'], decisions)
    write_all_outputs(out_dir, result, tests, family, breaches, guardrail_rows,
                      decisions, deferred)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
