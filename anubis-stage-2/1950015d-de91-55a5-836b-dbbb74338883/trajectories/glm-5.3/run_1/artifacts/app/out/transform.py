#!/usr/bin/env python3
"""Normalize a LedgerPort settlement drop into its quarter deliverables.

Usage: python3 transform.py <DATA_DIR> <OUT_DIR>

The drop is a flat directory of transaction feeds and reference registers. The
contract that governs it ships inside the drop; every rule the pipeline applies
is read from the register that publishes it, so the same code normalizes a drop
it has never seen.
"""

import bisect
import configparser
import csv
import datetime
import io
import json
import os
import re
import sqlite3
import sys
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from fractions import Fraction

FEED_COLUMNS = ['event_id', 'event_ts', 'customer_id', 'sku', 'warehouse',
                'terminal', 'kind', 'quantity', 'unit_price', 'currency',
                'revision', 'ref_event']

REGISTRY_COLUMNS = {
    'parties': ['customer_id', 'valid_from', 'valid_to', 'segment', 'postal_code'],
    'postal': ['postal_prefix', 'valid_from', 'valid_to', 'region'],
    'items': ['sku', 'valid_from', 'valid_to', 'category', 'active'],
    'price': ['sku', 'version_id', 'valid_from', 'valid_to', 'list_price_minor', 'currency'],
    'warehouses': ['warehouse', 'valid_from', 'valid_to', 'postal_code'],
    'terminals': ['terminal', 'valid_from', 'valid_to', 'channel_group', 'utc_offset_minutes'],
    'fx': ['rate_date', 'currency', 'quote_source', 'usd_rate'],
    'fiscal': ['calendar_date', 'region', 'variant', 'fiscal_week'],
    'crosswalk': ['legacy_code', 'code_kind', 'current_code'],
}

SALE_REFUND = ('sale', 'refund')
REGION_NAMES = ['central', 'east', 'north', 'south', 'west']
SEGMENT_NAMES = ['consumer', 'corporate', 'enterprise', 'smb']

EPOCH_ORDINAL = datetime.date(1970, 1, 1).toordinal()
EXCEL_SERIAL_1970 = Fraction(25569)

_YAML_LOADER = None


def yaml_load(text):
    """Parse YAML with the fast C loader when it is available."""
    global _YAML_LOADER
    import yaml
    if _YAML_LOADER is None:
        _YAML_LOADER = getattr(yaml, 'CSafeLoader', yaml.SafeLoader)
    return yaml.load(text, Loader=_YAML_LOADER)

_MD_CELL = re.compile(r'\s*\|\s*')
_MD_RULE = re.compile(r'^\s*\|[\s:\-|]+\|\s*$')
_TR_RE = re.compile(r'<tr[^>]*>(.*?)</tr>', re.S)
_CELL_RE = re.compile(r'<(t[hd])[^>]*>(.*?)</\1>', re.S)
_TAG_RE = re.compile(r'<[^>]*>')
_IDENT_LINE = re.compile(r'^[a-z_0-9]+$')
_TS_ISO = re.compile(r'^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})$')
_TS_US = re.compile(r'^(\d{2})/(\d{2})/(\d{4}) (\d{2}):(\d{2}):(\d{2})$')
_TS_EU = re.compile(r'^(\d{2})\.(\d{2})\.(\d{4}) (\d{2}):(\d{2}):(\d{2})$')
_DIGITS = re.compile(r'^\d+$')


# ---------------------------------------------------------------------------
# text decoding
# ---------------------------------------------------------------------------

def read_text(path, encoding=None):
    """Decode a published text file, tolerating a byte order mark."""
    with open(path, 'rb') as fh:
        raw = fh.read()
    for bom, enc in ((b'\xef\xbb\xbf', 'utf-8'), (b'\xff\xfe', 'utf-16-le'),
                     (b'\xfe\xff', 'utf-16-be')):
        if raw.startswith(bom):
            return raw[len(bom):].decode(enc)
    if encoding:
        try:
            return raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            pass
    try:
        return raw.decode('utf-8')
    except UnicodeDecodeError:
        return raw.decode('latin-1')


def as_text(value):
    if value is None:
        return ''
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, float):
        return repr(value)
    return str(value)


# ---------------------------------------------------------------------------
# container readers
#
# Every reader returns (header, rows): a list of lower case column names and a
# list of dicts mapping those names to stripped strings.  A comment line, a
# blank line and a `_note` object are filler wherever they appear.
# ---------------------------------------------------------------------------

def _from_dicts(dicts):
    if not dicts:
        return [], []
    header = []
    seen = set()
    for item in dicts:
        for key in item:
            if key not in seen:
                seen.add(key)
                header.append(key)
    return header, [{key: item.get(key, '') for key in header} for item in dicts]


def _grid_to_dicts(grid):
    if not grid:
        return [], []
    header = [as_text(h).strip().lstrip('\ufeff').lower() for h in grid[0]]
    rows = []
    for values in grid[1:]:
        row = {}
        for i, key in enumerate(header):
            row[key] = as_text(values[i]).strip() if i < len(values) else ''
        rows.append(row)
    return header, rows


def _read_csv(path, encoding, delim):
    grid = []
    for row in csv.reader(io.StringIO(read_text(path, encoding)), delimiter=delim):
        if not row or not ''.join(row).strip():
            continue
        if row[0].lstrip().startswith('#'):
            continue
        grid.append([as_text(c) for c in row])
    return _grid_to_dicts(grid)


def _read_fixed(path, encoding):
    lines = [l.rstrip('\r') for l in read_text(path, encoding).split('\n')]
    body = [l for l in lines if l.strip() and not l.lstrip().startswith('#')]
    if not body:
        return [], []
    header_line = body[0]
    tokens = [m.group() for m in re.finditer(r'\S+(?:\s+|$)', header_line)]
    starts = []
    at = 0
    for token in tokens:
        starts.append(header_line.index(token, at))
        at = starts[-1] + len(token)
    header = [t.strip().lstrip('\ufeff').lower() for t in tokens]
    rows = []
    for line in body[1:]:
        row = {}
        for i, start in enumerate(starts):
            end = starts[i + 1] if i + 1 < len(starts) else len(line)
            row[header[i]] = line[start:end].strip() if start < len(line) else ''
        rows.append(row)
    return header, rows


def _read_jsonl(path, encoding):
    objs = []
    for line in read_text(path, encoding).split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if isinstance(obj, dict) and set(obj) == {'_note'}:
            continue
        if isinstance(obj, dict):
            objs.append({str(k).strip().lstrip('\ufeff').lower(): as_text(v)
                         for k, v in obj.items()})
    return _from_dicts(objs)


def _read_log(path, encoding):
    objs = []
    for line in read_text(path, encoding).split('\n'):
        line = line.rstrip('\r')
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        row = {}
        for token in line.split(' '):
            if '=' in token:
                key, value = token.split('=', 1)
                row[key.strip().lstrip('\ufeff').lower()] = value.replace('\xa0', ' ')
        objs.append(row)
    header, rows = _from_dicts(objs)
    for row in rows:
        for key in list(row):
            if row[key] == '-':
                row[key] = ''
    return header, rows


def _read_json(path, encoding):
    doc = json.loads(read_text(path, encoding))
    if not isinstance(doc, dict) or not isinstance(doc.get('rows'), list):
        return [], []
    rows = [{str(k).strip().lstrip('\ufeff').lower(): as_text(v)
             for k, v in r.items()} for r in doc['rows'] if isinstance(r, dict)]
    if not rows:
        return [], []
    cols = doc.get('columns')
    header = [as_text(c).strip().lstrip('\ufeff').lower() for c in cols] if cols else list(rows[0])
    return header, [{key: row.get(key, '') for key in header} for row in rows]


def _read_xml(path, encoding):
    objs = []
    for row in ET.parse(path).getroot().iter('row'):
        objs.append({child.tag.strip().lstrip('\ufeff').lower(): (child.text or '')
                     for child in row})
    return _from_dicts(objs)


def _read_ini(path, encoding):
    parser = configparser.ConfigParser(strict=False, interpolation=None)
    parser.optionxform = str
    parser.read_string(read_text(path, encoding))
    rows = []
    for section in parser.sections():
        if section.startswith('row.'):
            rows.append({k.strip().lstrip('\ufeff').lower(): v
                         for k, v in parser[section].items()})
    return _from_dicts(rows)


def _read_toml(path, encoding):
    import tomllib
    doc = tomllib.loads(read_text(path, encoding))
    lines = doc.get('lines') if isinstance(doc, dict) else None
    if not isinstance(lines, list):
        return [], []
    rows = [{str(k).strip().lstrip('\ufeff').lower(): as_text(v) for k, v in r.items()}
            for r in lines if isinstance(r, dict)]
    return _from_dicts(rows)


def _read_yaml(path, encoding):
    doc = yaml_load(read_text(path, encoding))
    lines = doc.get('lines') if isinstance(doc, dict) else None
    if not isinstance(lines, list):
        return [], []
    rows = [{str(k).strip().lstrip('\ufeff').lower(): as_text(v) for k, v in r.items()}
            for r in lines if isinstance(r, dict)]
    return _from_dicts(rows)


def _read_parquet(path, encoding):
    import pyarrow.parquet as pq
    rows = [{str(k).strip().lstrip('\ufeff').lower(): as_text(v)
             for k, v in r.items()} for r in pq.read_table(path).to_pylist()]
    return _from_dicts(rows)


def _read_db(path, encoding):
    con = sqlite3.connect(path)
    try:
        cur = con.execute('select * from lines')
        grid = [[c[0] for c in cur.description]]
        grid.extend([list(r) for r in cur])
    finally:
        con.close()
    return _grid_to_dicts(grid)


def _read_xlsx(path, encoding):
    import openpyxl
    book = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = book['lines']
        grid = [list(r) for r in sheet.iter_rows(values_only=True)]
    finally:
        book.close()
    grid = [r for r in grid if any(c is not None and str(c).strip() for c in r)]
    return _grid_to_dicts(grid)


def _read_docx(path, encoding):
    wns = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read('word/document.xml'))
    tables = list(root.iter(wns + 'tbl'))
    if not tables:
        return [], []
    grid = []
    for tr in tables[-1].iter(wns + 'tr'):
        grid.append([''.join(t.text or '' for t in tc.iter(wns + 't')).strip()
                     for tc in tr.findall(wns + 'tc')])
    return _grid_to_dicts(grid)


def _read_html(path, encoding):
    import html as html_mod
    text = read_text(path, encoding)
    tables = []
    pos = 0
    while True:
        start = text.find('<table', pos)
        if start < 0:
            break
        end = text.find('</table>', start)
        if end < 0:
            break
        grid = []
        for tr in _TR_RE.finditer(text[start:end]):
            cells = [html_mod.unescape(_TAG_RE.sub('', c.group(2))).strip()
                     for c in _CELL_RE.finditer(tr.group(1))]
            if cells:
                grid.append(cells)
        if grid:
            tables.append(grid)
        pos = end + 8
    if not tables:
        return [], []
    return _grid_to_dicts(tables[-1])


def read_md_tables(path, encoding=None):
    lines = [l.rstrip('\r') for l in read_text(path, encoding).split('\n')]
    tables = []
    i = 0
    while i < len(lines):
        if lines[i].lstrip().startswith('|') and i + 1 < len(lines) \
                and _MD_RULE.match(lines[i + 1]):
            header = [c.strip().lstrip('\ufeff').lower()
                      for c in _MD_CELL.split(lines[i].strip().strip('|'))]
            j = i + 2
            rows = []
            while j < len(lines) and lines[j].lstrip().startswith('|'):
                values = [c.strip() for c in _MD_CELL.split(lines[j].strip().strip('|'))]
                rows.append({key: (values[k] if k < len(values) else '')
                             for k, key in enumerate(header)})
                j += 1
            tables.append((header, rows))
            i = j
        else:
            i += 1
    return tables


def _read_pdf(path, encoding):
    lines = []

    def collect(text):
        for raw in text.split('\n'):
            line = raw.strip()
            if line:
                lines.append([c.strip() for c in line.split(' | ')])

    # pypdf reads these appendices several orders of magnitude faster than a
    # layout aware reader; the fallback keeps the program working either way.
    try:
        from pypdf import PdfReader
        for page in PdfReader(path).pages:
            collect(page.extract_text() or '')
    except ImportError:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                collect(page.extract_text() or '')
    header_at = None
    for i, cells in enumerate(lines):
        if len(cells) >= 2 and all(_IDENT_LINE.match(c) for c in cells):
            header_at = i
            break
    if header_at is None:
        return [], []
    grid = [lines[header_at]]
    grid.extend([row for row in lines[header_at + 1:] if len(row) > 1])
    return _grid_to_dicts(grid)


def _read_mbox(path, encoding):
    messages = []
    current = None
    in_body = False
    for line in read_text(path, encoding).split('\n'):
        line = line.rstrip('\r')
        if line.startswith('From ') and ' ' in line[5:]:
            if current is not None:
                messages.append(current)
            current = {}
            in_body = False
            continue
        if current is None:
            continue
        if not line.strip():
            in_body = True
            continue
        if in_body and ':' in line:
            key, value = line.split(':', 1)
            current[key.strip().lstrip('\ufeff').lower()] = value.strip()
    if current is not None:
        messages.append(current)
    return _from_dicts(messages)


def _read_ics(path, encoding):
    rows = []
    current = None
    for line in read_text(path, encoding).split('\n'):
        line = line.rstrip('\r')
        if line == 'BEGIN:VEVENT':
            current = {}
        elif line == 'END:VEVENT':
            if current is not None:
                rows.append(current)
            current = None
        elif current is not None and ':' in line:
            name, value = line.split(':', 1)
            if name.upper().startswith('X-'):
                current[name[2:].replace('-', '_').lower()] = value.strip()
    return _from_dicts(rows)


def _read_md_single(path, encoding):
    tables = read_md_tables(path, encoding)
    return tables[-1] if tables else ([], [])


READERS = {
    'csv': lambda p, e: _read_csv(p, e, ','),
    'tsv': lambda p, e: _read_csv(p, e, '\t'),
    'txt': _read_fixed,
    'jsonl': _read_jsonl,
    'json': _read_json,
    'xml': _read_xml,
    'parquet': _read_parquet,
    'db': _read_db,
    'xlsx': _read_xlsx,
    'docx': _read_docx,
    'pdf': _read_pdf,
    'md': _read_md_single,
    'html': _read_html,
    'log': _read_log,
    'ini': _read_ini,
    'toml': _read_toml,
    'yaml': _read_yaml,
    'mbox': _read_mbox,
    'ics': _read_ics,
}


def sniff_container(path):
    with open(path, 'rb') as fh:
        head = fh.read(16)
    if head.startswith(b'PK\x03\x04'):
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
        return 'docx' if 'word/document.xml' in names else 'xlsx'
    if head.startswith(b'PAR1'):
        return 'parquet'
    if head.startswith(b'SQLite format 3'):
        return 'db'
    if head.startswith(b'%PDF'):
        return 'pdf'
    low = path.lower()
    for ext in ('.csv', '.tsv', '.txt', '.jsonl', '.json', '.xml', '.log', '.ini',
                '.toml', '.yaml', '.yml', '.md', '.html', '.mbox', '.ics'):
        if low.endswith(ext):
            return ext[1:]
    return 'csv'


def read_table(path, container, encoding=None):
    """Every table a container holds; most hold exactly one."""
    if container == 'md':
        return read_md_tables(path, encoding)
    header, rows = READERS[container](path, encoding)
    return [(header, rows)] if rows else []


# ---------------------------------------------------------------------------
# dates and rounding
# ---------------------------------------------------------------------------

def parse_date(value):
    text = as_text(value).strip()
    if len(text) != 10 or text[4] != '-' or text[7] != '-':
        return None
    try:
        return datetime.date(int(text[0:4]), int(text[5:7]), int(text[8:10])).toordinal()
    except ValueError:
        return None


def parse_local_epoch(value, style):
    """Seconds since 1970-01-01 00:00:00 as an exact Fraction, or None."""
    text = as_text(value).strip()
    if style in ('epoch_s', 'epoch_ms'):
        if not _DIGITS.match(text):
            return None
        number = Fraction(int(text))
        return number if style == 'epoch_s' else number / 1000
    if style == 'excel_serial':
        try:
            serial = Fraction(text)
        except (ValueError, ZeroDivisionError):
            return None
        return (serial - EXCEL_SERIAL_1970) * 86400
    if style == 'iso':
        m = _TS_ISO.match(text)
        if not m:
            return None
        y, mo, d, h, mi, s = (int(g) for g in m.groups())
    elif style == 'us_slash':
        m = _TS_US.match(text)
        if not m:
            return None
        mo, d, y, h, mi, s = (int(g) for g in m.groups())
    elif style == 'eu_dot':
        m = _TS_EU.match(text)
        if not m:
            return None
        d, mo, y, h, mi, s = (int(g) for g in m.groups())
    else:
        return None
    if h > 23 or mi > 59 or s > 59:
        return None
    try:
        ordinal = datetime.date(y, mo, d).toordinal()
    except ValueError:
        return None
    return Fraction((ordinal - EPOCH_ORDINAL) * 86400 + h * 3600 + mi * 60 + s)


def date_of(seconds):
    whole = int(seconds)
    days = whole // 86400 if whole >= 0 else -((-whole + 86399) // 86400)
    return EPOCH_ORDINAL + days


def date_text(ordinal):
    return datetime.date.fromordinal(ordinal).isoformat() if ordinal else ''


def round_fraction(value, mode):
    """Round an exact Fraction to a whole number under the named mode.

    `half_up` and `half_down` send an exact half away from and toward zero,
    `floor` and `ceiling` round toward negative and positive infinity, and
    `up` and `down` round away from and toward zero.
    """
    n, d = value.numerator, value.denominator
    if n == 0:
        return 0
    sign = 1 if n > 0 else -1
    whole, rest = divmod(abs(n), d)
    if rest == 0:
        return sign * whole
    if mode == 'floor':
        return sign * (whole + 1) if sign < 0 else whole
    if mode == 'ceiling':
        return sign * whole if sign < 0 else whole + 1
    if mode == 'up':
        return sign * (whole + 1)
    if mode == 'down':
        return sign * whole
    twice = 2 * rest
    if mode == 'half_up':
        magnitude = whole + 1 if twice >= d else whole
    elif mode == 'half_down':
        magnitude = whole + 1 if twice > d else whole
    else:  # half_even, and anything unrecognised
        if twice > d:
            magnitude = whole + 1
        elif twice < d:
            magnitude = whole
        else:
            magnitude = whole if whole % 2 == 0 else whole + 1
    return sign * magnitude


# ---------------------------------------------------------------------------
# identifiers
# ---------------------------------------------------------------------------

def homoglyph_table(section):
    table = {}
    for key, value in section.items():
        try:
            table[chr(int(key, 16))] = value
        except ValueError:
            table[key] = value
    return table


class Canonicaliser:
    """The five step canonical form of section 1 of the contract."""

    def __init__(self, homoglyphs, upper=True, strip_zeros=True):
        self.homoglyphs = homoglyphs
        self.upper = upper
        self.strip_zeros = strip_zeros
        self.cache = {}

    def __call__(self, value):
        text = as_text(value)
        cached = self.cache.get(text)
        if cached is not None:
            return cached
        s = ''.join(self.homoglyphs.get(ch, ch) for ch in text) if self.homoglyphs else text
        s = s.strip()
        if self.upper:
            s = s.upper()
        s = ''.join(ch for ch in s if ch in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-')
        if self.strip_zeros and '-' in s:
            prefix, body = s.split('-', 1)
            s = prefix + '-' + body.lstrip('0')
        self.cache[text] = s
        return s


# ---------------------------------------------------------------------------
# policy registers
# ---------------------------------------------------------------------------

def read_ini(path):
    parser = configparser.ConfigParser(strict=False, interpolation=None)
    parser.optionxform = str
    if os.path.exists(path):
        parser.read_string(read_text(path, 'utf-8'))
    return parser


def load_policies(data_dir):
    join = os.path.join
    pol = {}

    profiles = {}
    path = join(data_dir, 'postal_region_supplement.yaml')
    if os.path.exists(path):
        doc = yaml_load(read_text(path, 'utf-8')) or {}
        for name, profile in (doc.get('source_profiles') or {}).items():
            if isinstance(profile, dict):
                profiles[str(name)] = profile
    pol['source_profiles'] = profiles

    parser = read_ini(join(data_dir, 'code_crosswalk_overrides.ini'))
    pol['homoglyphs'] = homoglyph_table(parser['homoglyphs']) \
        if parser.has_section('homoglyphs') else {}
    ident = parser['identifier'] if parser.has_section('identifier') else {}
    pol['strip_zeros'] = str(ident.get('strip_leading_zeros_after_hyphen', 'yes')).lower() != 'no'
    pol['upper'] = str(ident.get('upper_case', 'yes')).lower() != 'no'

    parser = read_ini(join(data_dir, 'terminal_channel_map.ini'))
    window = parser['settlement_window'] if parser.has_section('settlement_window') else {}
    pol['window_start'] = parse_date(window.get('start', ''))
    pol['window_end_exclusive'] = parse_date(window.get('end_exclusive', ''))

    fx = {}
    path = join(data_dir, 'fx_policy_register.toml')
    if os.path.exists(path):
        import tomllib
        fx = tomllib.loads(read_text(path, 'utf-8')).get('fx') or {}
    pol['quote_source'] = str(fx.get('quote_source', '')).strip()
    try:
        pol['carry_forward_days'] = int(fx.get('carry_forward_days', 0))
    except (TypeError, ValueError):
        pol['carry_forward_days'] = 0
    pol['rounding_mode'] = str(fx.get('rounding_mode', 'half_even')).strip()

    pol['fiscal_variant'] = ''
    path = join(data_dir, 'fiscal_calendar_policy.yaml')
    if os.path.exists(path):
        doc = yaml_load(read_text(path, 'utf-8')) or {}
        pol['fiscal_variant'] = str((doc.get('fiscal_calendar') or {}).get('variant', '')).strip()

    minor = {}
    path = join(data_dir, 'price_tier_registry.yaml')
    if os.path.exists(path):
        doc = yaml_load(read_text(path, 'utf-8')) or {}
        for key, value in (doc.get('minor_units') or {}).items():
            try:
                minor[str(key).strip().upper()] = int(value)
            except (TypeError, ValueError):
                continue
    pol['minor_units'] = minor

    parser = read_ini(join(data_dir, 'terminal_offsets.ini'))
    pol['authority_fee'] = dict(parser['authority_fee']) if parser.has_section('authority_fee') else {}
    pol['authority_credit'] = dict(parser['authority_credit']) if parser.has_section('authority_credit') else {}

    registry = {}
    path = join(data_dir, 'warehouse_registry.toml')
    if os.path.exists(path):
        import tomllib
        registry = tomllib.loads(read_text(path, 'utf-8'))
    pol['authority_sale'] = dict(registry.get('authority_sale') or {})
    pol['authority_refund'] = dict(registry.get('authority_refund') or {})

    scope = {}
    path = join(data_dir, 'code_crosswalk_supplement.yaml')
    if os.path.exists(path):
        doc = yaml_load(read_text(path, 'utf-8')) or {}
        for name, window in (doc.get('scope_windows') or {}).items():
            if not isinstance(window, dict):
                continue
            scope[str(name).strip()] = (parse_date(window.get('scope_start', '')),
                                        parse_date(window.get('scope_end_exclusive', '')))
    pol['scope_windows'] = scope

    retired = {}
    path = join(data_dir, 'price_policy_notes.md')
    if os.path.exists(path):
        for header, rows in read_md_tables(path, 'utf-8'):
            if [h.lower() for h in header] == ['retired_source', 'superseded_from']:
                for row in rows:
                    name = str(row.get('retired_source', '')).strip()
                    if name:
                        retired[name] = parse_date(row.get('superseded_from', ''))
    pol['retired'] = retired
    return pol


def load_void_register(data_dir, canon):
    """The void register is the table that publishes `voided_event_id`."""
    path = os.path.join(data_dir, 'counterparty_notice_board.html')
    voided = set()
    if not os.path.exists(path):
        return voided
    import html as html_mod
    text = read_text(path, 'utf-8')
    pos = 0
    while True:
        start = text.find('<table', pos)
        if start < 0:
            break
        end = text.find('</table>', start)
        if end < 0:
            break
        grid = []
        for tr in _TR_RE.finditer(text[start:end]):
            cells = [html_mod.unescape(_TAG_RE.sub('', c.group(2))).strip()
                     for c in _CELL_RE.finditer(tr.group(1))]
            if cells:
                grid.append(cells)
        if grid:
            header = [c.lower() for c in grid[0]]
            if 'voided_event_id' in header:
                column = header.index('voided_event_id')
                for values in grid[1:]:
                    if column < len(values):
                        value = canon(values[column])
                        if value:
                            voided.add(value)
                return voided
        pos = end + 8
    return voided


# ---------------------------------------------------------------------------
# reference registries
# ---------------------------------------------------------------------------

class EffectiveDated:
    """Windows are half open at the upper end and never overlap."""

    def __init__(self):
        self.rows = defaultdict(list)
        self.starts = {}

    def add(self, key, start, end, payload):
        if start is None or end is None or end <= start:
            return
        self.rows[key].append((start, end, payload))

    def finish(self):
        for key, rows in self.rows.items():
            rows.sort()
            self.starts[key] = [row[0] for row in rows]

    def lookup(self, key, day):
        rows = self.rows.get(key)
        if not rows:
            return None
        i = bisect.bisect_right(self.starts[key], day) - 1
        while i >= 0:
            start, end, payload = rows[i]
            if start <= day < end:
                return payload
            if end > day:
                i -= 1
                continue
            break
        return None


class Registers:
    def __init__(self):
        self.parties = EffectiveDated()
        self.postal = EffectiveDated()
        self.items = EffectiveDated()
        self.price = EffectiveDated()
        self.warehouses = EffectiveDated()
        self.terminals = EffectiveDated()
        self.fx = {}
        self.fiscal = {}
        self.crosswalk = {}


def absorb(reg, target, row, canon):
    if target == 'parties':
        reg.parties.add(canon(row.get('customer_id', '')),
                        parse_date(row.get('valid_from')), parse_date(row.get('valid_to')),
                        (str(row.get('segment', '')).strip(),
                         str(row.get('postal_code', '')).strip()))
    elif target == 'postal':
        reg.postal.add(str(row.get('postal_prefix', '')).strip(),
                       parse_date(row.get('valid_from')), parse_date(row.get('valid_to')),
                       str(row.get('region', '')).strip())
    elif target == 'items':
        reg.items.add(canon(row.get('sku', '')),
                      parse_date(row.get('valid_from')), parse_date(row.get('valid_to')),
                      (str(row.get('category', '')).strip(),
                       str(row.get('active', '')).strip()))
    elif target == 'price':
        reg.price.add(canon(row.get('sku', '')),
                      parse_date(row.get('valid_from')), parse_date(row.get('valid_to')),
                      str(row.get('version_id', '')).strip())
    elif target == 'warehouses':
        reg.warehouses.add(canon(row.get('warehouse', '')),
                           parse_date(row.get('valid_from')), parse_date(row.get('valid_to')),
                           str(row.get('postal_code', '')).strip())
    elif target == 'terminals':
        try:
            offset = int(str(row.get('utc_offset_minutes', '')).strip())
        except ValueError:
            offset = 0
        reg.terminals.add(canon(row.get('terminal', '')),
                          parse_date(row.get('valid_from')), parse_date(row.get('valid_to')),
                          (str(row.get('channel_group', '')).strip(), offset))
    elif target == 'fx':
        day = parse_date(row.get('rate_date'))
        if day is None:
            return
        key = (day, str(row.get('currency', '')).strip().upper())
        reg.fx.setdefault(key, {})[str(row.get('quote_source', '')).strip()] = \
            str(row.get('usd_rate', '')).strip()
    elif target == 'fiscal':
        day = parse_date(row.get('calendar_date'))
        if day is None:
            return
        key = (day, str(row.get('region', '')).strip())
        reg.fiscal.setdefault(key, {})[str(row.get('variant', '')).strip()] = \
            str(row.get('fiscal_week', '')).strip()
    elif target == 'crosswalk':
        reg.crosswalk[(canon(row.get('legacy_code', '')),
                       str(row.get('code_kind', '')).strip())] = \
            canon(row.get('current_code', ''))


def build_registers(data_dir, canon, feed_names):
    """Concatenate every shard of every registry named in the contract."""
    reg = Registers()
    wanted = [(set(columns), name) for name, columns in REGISTRY_COLUMNS.items()]
    for entry in sorted(os.listdir(data_dir)):
        if entry in feed_names:
            continue
        path = os.path.join(data_dir, entry)
        if not os.path.isfile(path):
            continue
        container = sniff_container(path)
        for header, rows in read_table(path, container):
            if not rows or not header:
                continue
            present = set(header)
            for columns, target in wanted:
                if columns <= present and present - columns <= {'seq'}:
                    for row in rows:
                        absorb(reg, target, row, canon)
                    break
    for registry in (reg.parties, reg.postal, reg.items, reg.price,
                     reg.warehouses, reg.terminals):
        registry.finish()
    return reg


# ---------------------------------------------------------------------------
# money
# ---------------------------------------------------------------------------

def parse_money(value, style, exponent):
    """A price in major units, read as the currency's minor units.

    The number of fraction digits is the currency's minor unit exponent, so a
    price that carries more cannot be read as its declared type.
    """
    text = as_text(value).strip()
    if text.startswith('(') and text.endswith(')'):
        text = text[1:-1].strip()
    if not text:
        return None
    if style == 'comma':
        if ',' in text:
            head, _, fraction = text.rpartition(',')
            digits = head.replace('.', '').replace(' ', '') + fraction
        else:
            digits = text.replace('.', '').replace(' ', '')
            fraction = ''
    else:
        if '.' in text:
            head, _, fraction = text.rpartition('.')
            digits = head.replace(',', '').replace(' ', '') + fraction
        else:
            digits = text.replace(',', '').replace(' ', '')
            fraction = ''
    if not digits or not digits.isdigit():
        return None
    shift = exponent - len(fraction)
    if shift < 0:
        return None
    return int(digits) * (10 ** shift) if shift else int(digits)


# ---------------------------------------------------------------------------
# the ordered chain
# ---------------------------------------------------------------------------

def run(data_dir, out_dir):
    pol = load_policies(data_dir)
    canon = Canonicaliser(pol['homoglyphs'], pol['upper'], pol['strip_zeros'])
    profiles = pol['source_profiles']
    feed_names = sorted(profiles)
    reg = build_registers(data_dir, canon, set(feed_names))
    voided = load_void_register(data_dir, canon)

    by_stem = {}
    for name in feed_names:
        by_stem.setdefault(os.path.splitext(name)[0], name)
    scope = {}
    for stem, window in sorted(pol['scope_windows'].items()):
        if stem in by_stem:
            scope[by_stem[stem]] = window
    retired = {}
    for stem, when in sorted(pol['retired'].items()):
        if stem in by_stem:
            retired[by_stem[stem]] = when

    minor_units = pol['minor_units']
    quote_source = pol['quote_source']
    carry = pol['carry_forward_days']
    rounding_mode = pol['rounding_mode']
    variant = pol['fiscal_variant']
    win_start = pol['window_start']
    win_end = pol['window_end_exclusive']
    rank_tables = {'sale': pol['authority_sale'], 'refund': pol['authority_refund'],
                   'fee': pol['authority_fee'], 'credit': pol['authority_credit']}

    rejected_by_code = defaultdict(int)
    rejected_by_source = {name: 0 for name in feed_names}
    accepted_by_source = {name: 0 for name in feed_names}

    def reject(source, code):
        rejected_by_code[code] += 1
        rejected_by_source[source] = rejected_by_source.get(source, 0) + 1

    candidates = []

    for name in feed_names:
        profile = profiles[name]
        path = os.path.join(data_dir, name)
        if not os.path.isfile(path):
            continue
        container = str(profile.get('container', 'csv'))
        encoding = profile.get('encoding')
        offset_minutes = int(profile.get('utc_offset_minutes', 0) or 0)
        date_style = str(profile.get('date_style', 'iso'))
        decimal_style = str(profile.get('decimal_style', 'point'))
        feed_scope = scope.get(name)
        retired_from = retired.get(name)

        for position, raw in enumerate(
                [row for header, rows in read_table(path, container, encoding)
                 for row in rows]):
            row = {col: str(raw.get(col, '')).strip() for col in FEED_COLUMNS}
            kind = row['kind']
            currency = row['currency'].upper()

            # 1 MALFORMED_ROW
            if not row['event_id'] or not kind or not currency or not row['unit_price']:
                reject(name, 'MALFORMED_ROW')
                continue
            local = parse_local_epoch(row['event_ts'], date_style)
            if local is None:
                reject(name, 'MALFORMED_ROW')
                continue
            exponent = minor_units.get(currency)
            price_minor = parse_money(row['unit_price'], decimal_style,
                                      exponent if exponent is not None else 2)
            if price_minor is None:
                reject(name, 'MALFORMED_ROW')
                continue

            # 2 NON_NUMERIC_QUANTITY
            if not _DIGITS.match(row['quantity']):
                reject(name, 'NON_NUMERIC_QUANTITY')
                continue
            quantity = int(row['quantity'])

            # 3 capture date and terminal
            utc = local - offset_minutes * 60
            capture = date_of(utc)
            if kind in SALE_REFUND:
                terminal = canon(row['terminal'])
                terminal = reg.crosswalk.get((terminal, 'terminal'), terminal)
                hit = reg.terminals.lookup(terminal, capture)
                if hit is None:
                    reject(name, 'UNKNOWN_TERMINAL')
                    continue
                channel_group, terminal_offset = hit
            else:
                channel_group, terminal_offset = 'contract', 0

            # 4 posting date
            posting = capture
            if channel_group == 'branch':
                posting = date_of(utc + terminal_offset * 60)

            # 5 OUT_OF_SCOPE
            if (win_start is not None and posting < win_start) or \
                    (win_end is not None and posting >= win_end):
                reject(name, 'OUT_OF_SCOPE')
                continue
            if feed_scope is not None:
                start, end = feed_scope
                if (start is not None and posting < start) or \
                        (end is not None and posting >= end):
                    reject(name, 'OUT_OF_SCOPE')
                    continue

            # 6 SUPERSEDED_SOURCE
            if retired_from is not None and retired_from <= posting:
                reject(name, 'SUPERSEDED_SOURCE')
                continue

            # 7 VOIDED
            event_id = canon(row['event_id'])
            if event_id in voided:
                reject(name, 'VOIDED')
                continue

            # 8 UNKNOWN_CUSTOMER
            customer_id = canon(row['customer_id'])
            party = reg.parties.lookup(customer_id, posting)
            if party is None:
                reject(name, 'UNKNOWN_CUSTOMER')
                continue
            segment, customer_postal = party

            # 9 UNKNOWN_SKU / INACTIVE_SKU
            sku = canon(row['sku'])
            sku = reg.crosswalk.get((sku, 'sku'), sku)
            item = reg.items.lookup(sku, posting)
            if item is None:
                reject(name, 'UNKNOWN_SKU')
                continue
            category, active = item
            if active == 'N':
                reject(name, 'INACTIVE_SKU')
                continue

            # 10 region
            if kind in SALE_REFUND:
                warehouse = canon(row['warehouse'])
                warehouse = reg.crosswalk.get((warehouse, 'warehouse'), warehouse)
                postal_code = reg.warehouses.lookup(warehouse, posting)
                if postal_code is None:
                    reject(name, 'UNKNOWN_WAREHOUSE')
                    continue
                prefix = postal_code.split('-')[0]
            else:
                prefix = customer_postal.split('-')[0]
            region = reg.postal.lookup(prefix, posting)
            if region is None:
                reject(name, 'UNKNOWN_WAREHOUSE')
                continue

            # 11 price list version
            if kind in SALE_REFUND:
                price_list_version = reg.price.lookup(sku, posting)
                if price_list_version is None:
                    reject(name, 'NO_PRICE_VERSION')
                    continue
            else:
                price_list_version = 'n/a'

            # 12 NO_FX_RATE
            if exponent is None:
                reject(name, 'NO_FX_RATE')
                continue
            rate = None
            for back in range(carry + 1):
                quotes = reg.fx.get((posting - back, currency))
                if not quotes:
                    continue
                written = quotes.get(quote_source)
                if not written:
                    continue
                try:
                    rate = Fraction(written)
                except (ValueError, ZeroDivisionError):
                    continue
                break
            if rate is None:
                reject(name, 'NO_FX_RATE')
                continue

            # 13 NO_FISCAL_WEEK
            fiscal_week = reg.fiscal.get((posting, region), {}).get(variant)
            if not fiscal_week:
                reject(name, 'NO_FISCAL_WEEK')
                continue

            if kind == 'sale':
                native = quantity * price_minor
            elif kind == 'refund':
                native = -(quantity * price_minor)
            elif kind == 'credit':
                native = -price_minor
            else:
                native = price_minor
            amount = round_fraction(
                Fraction(native) / (10 ** exponent) * rate * 100, rounding_mode)

            revision = int(row['revision']) if _DIGITS.match(row['revision']) else 0
            table = rank_tables.get(kind) or {}
            written_rank = table.get(name)
            try:
                rank = int(str(written_rank).strip())
            except (TypeError, ValueError):
                rank = 0

            candidates.append({
                'event_id': event_id,
                'source': name,
                'position': position,
                'rank': rank,
                'revision': revision,
                'posting': posting,
                'kind': kind,
                'ref': canon(row['ref_event']),
                'record': {
                    'amount_usd_cents': amount,
                    'category': category,
                    'channel_group': channel_group,
                    'currency': currency,
                    'customer_id': customer_id,
                    'event_id': event_id,
                    'fiscal_week': fiscal_week,
                    'kind': kind,
                    'native_amount_minor': native,
                    'posting_date': date_text(posting),
                    'price_list_version': price_list_version,
                    'quantity': quantity if kind in SALE_REFUND else 0,
                    'region': region,
                    'segment': segment,
                    'sku': sku,
                    'source_file': name,
                },
            })

    # 5 duplicates
    groups = defaultdict(list)
    for row in candidates:
        groups[row['event_id']].append(row)
    duplicate_groups = 0
    survivors = []
    for event_id, rows in groups.items():
        if len(rows) > 1:
            duplicate_groups += 1
            rows.sort(key=lambda r: (r['rank'], -r['revision'], r['source'], r['position']))
            survivors.append(rows[0])
            for row in rows[1:]:
                reject(row['source'], 'DUPLICATE_LOWER_AUTHORITY')
        else:
            survivors.append(rows[0])
    del candidates, groups

    # 6 reversals
    survivors.sort(key=lambda r: (r['posting'], r['event_id'], r['source']))
    live = {row['event_id'] for row in survivors}
    source_of = {row['event_id']: row['source'] for row in survivors}
    kind_of = {row['event_id']: row['kind'] for row in survivors}
    reversed_pairs = 0
    reversal_orphans = 0
    for row in survivors:
        event_id = row['event_id']
        if event_id not in live or kind_of[event_id] != 'credit' or not row['ref']:
            continue
        target = row['ref']
        if target in live and target != event_id:
            reversed_pairs += 1
            live.discard(target)
            live.discard(event_id)
            reject(row['source'], 'REVERSED')
            reject(source_of[target], 'REVERSED')
        else:
            reversal_orphans += 1
            live.discard(event_id)
            reject(row['source'], 'REVERSAL_ORPHAN')
    ledger = [row for row in survivors if row['event_id'] in live]

    write_outputs(out_dir, data_dir, ledger, feed_names, rejected_by_code,
                  rejected_by_source, accepted_by_source, pol, duplicate_groups,
                  reversed_pairs, reversal_orphans, sorted(scope), sorted(retired))
    return {'accepted': len(ledger),
            'rejected': sum(rejected_by_code.values()),
            'by_code': dict(rejected_by_code)}


# ---------------------------------------------------------------------------
# deliverables
# ---------------------------------------------------------------------------

def write_json(out_dir, name, payload):
    with open(os.path.join(out_dir, name), 'w', encoding='utf-8') as fh:
        json.dump(payload, fh, sort_keys=True, indent=2)
        fh.write('\n')


def net_units(records):
    return sum(r['quantity'] if r['kind'] == 'sale'
               else -r['quantity'] if r['kind'] == 'refund' else 0
               for r in records)


def write_outputs(out_dir, data_dir, ledger, feed_names, rejected_by_code,
                  rejected_by_source, accepted_by_source, pol, duplicate_groups,
                  reversed_pairs, reversal_orphans, scoped_sources,
                  superseded_sources):
    os.makedirs(out_dir, exist_ok=True)
    records = []
    for index, row in enumerate(ledger, 1):
        record = dict(row['record'])
        record['ledger_index'] = index
        records.append(record)
    for record in records:
        accepted_by_source[record['source_file']] += 1

    with open(os.path.join(out_dir, 'normalized.jsonl'), 'w', encoding='utf-8') as fh:
        for record in records:
            fh.write(json.dumps(record, sort_keys=True, separators=(',', ':')))
            fh.write('\n')

    def rollup(field):
        totals = defaultdict(int)
        for record in records:
            totals[record[field]] += record['amount_usd_cents']
        return {key: totals[key] for key in sorted(totals)}

    write_json(out_dir, 'summary.json', {
        'accepted_count': len(records),
        'by_category': rollup('category'),
        'by_channel_group': rollup('channel_group'),
        'by_currency': rollup('currency'),
        'by_kind': rollup('kind'),
        'by_region': rollup('region'),
        'by_segment': rollup('segment'),
        'net_units': net_units(records),
        'rejected_count': sum(rejected_by_code.values()),
        'settlement_window': {'end_exclusive': date_text(pol['window_end_exclusive']),
                              'start': date_text(pol['window_start'])},
        'total_usd_cents': sum(r['amount_usd_cents'] for r in records),
    })

    write_json(out_dir, 'data_quality.json', {
        'accepted_by_source': {n: accepted_by_source.get(n, 0) for n in feed_names},
        'duplicate_groups': duplicate_groups,
        'input_file_count': sum(1 for entry in os.listdir(data_dir)
                                if os.path.isfile(os.path.join(data_dir, entry))),
        'rejected_by_code': {code: rejected_by_code[code] for code in sorted(rejected_by_code)},
        'rejected_by_source': {n: rejected_by_source.get(n, 0) for n in feed_names},
        'reversal_orphans': reversal_orphans,
        'reversed_pairs': reversed_pairs,
        'scoped_sources': scoped_sources,
        'superseded_sources': superseded_sources,
    })

    grouped = defaultdict(list)
    for record in records:
        grouped[record['sku']].append(record)
    products = []
    for sku in sorted(grouped):
        records_ = grouped[sku]
        products.append({
            'category': records_[0]['category'],
            'net_units': net_units(records_),
            'price_list_versions': sorted({r['price_list_version'] for r in records_}),
            'record_count': len(records_),
            'sku': sku,
            'total_usd_cents': sum(r['amount_usd_cents'] for r in records_),
        })
    write_json(out_dir, 'product_summary.json',
               {'product_count': len(products), 'products': products})

    for region in REGION_NAMES:
        write_group(out_dir, 'region', region,
                    [r for r in records if r['region'] == region])
    for segment in SEGMENT_NAMES:
        write_group(out_dir, 'segment', segment,
                    [r for r in records if r['segment'] == segment])


def write_group(out_dir, grouping, value, records):
    by_category, by_channel, by_kind, customers = {}, {}, {}, {}
    for record in records:
        by_category[record['category']] = by_category.get(record['category'], 0) + record['amount_usd_cents']
        by_channel[record['channel_group']] = by_channel.get(record['channel_group'], 0) + record['amount_usd_cents']
        by_kind[record['kind']] = by_kind.get(record['kind'], 0) + record['amount_usd_cents']
        customers[record['customer_id']] = customers.get(record['customer_id'], 0) + record['amount_usd_cents']
    top = sorted(customers.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    write_json(out_dir, '%s_%s.json' % (grouping, value), {
        grouping: value,
        'by_category': {k: by_category[k] for k in sorted(by_category)},
        'by_channel_group': {k: by_channel[k] for k in sorted(by_channel)},
        'by_kind': {k: by_kind[k] for k in sorted(by_kind)},
        'customer_count': len(customers),
        'net_units': net_units(records),
        'record_count': len(records),
        'top_customers': [{'customer_id': c, 'total_usd_cents': v} for c, v in top],
        'total_usd_cents': sum(r['amount_usd_cents'] for r in records),
    })


def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: transform.py <DATA_DIR> <OUT_DIR>\n')
        return 2
    run(argv[1], argv[2])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
