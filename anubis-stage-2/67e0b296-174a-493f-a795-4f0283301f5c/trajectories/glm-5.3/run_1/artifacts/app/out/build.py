#!/usr/bin/env python3
"""Rack power cap compiler.

Stages:
  phase1 <DATA_DIR> <P1_DIR>          settle the facts from the fleet sources
  phase2 <P1_DIR> <P2_DIR>            plan budgets, allocations, energy, alarms, pools
  phase3 <P1_DIR> <P2_DIR> <P3_DIR>   emit the pushed configuration and the release record

Reading of the sources follows the rack power cap standard; the shape of every
output follows the output contract.
"""

import csv
import datetime
import hashlib
import json
import os
import re
import sqlite3
import sys
from decimal import Decimal

PROG = 'build.py'

FREEZE_DEFAULT = '2026-03-30T00:00:00Z'
WINDOW_DEFAULT = '2026-03-23T00:00:00Z'

P1_NAMES = ['amendments.csv', 'circuits.csv', 'demand.csv', 'hosts.csv', 'psu.csv', 'registry.json']
P2_NAMES = ['circuit_alarms.csv', 'fleet_summary.json', 'host_alloc.csv', 'rack_budget.csv',
            'site_energy.csv', 'tenant_pool.csv']
P1_KEYS = ['p1/' + n for n in P1_NAMES]
P2_KEYS = ['p2/' + n for n in P2_NAMES]

RECORD_KINDS = frozenset('RD HV CV MV PR QV SP TN PV AL VO ER CA PF RT AM'.split())
SUPERSEDED_RE = re.compile(r're-?export|replay|backfill|legacy|prev|draft|rescan|prelim', re.I)

UNIT_FACTORS = {
    'w': (1000, 1),
    'kw': (1000000, 1),
    'mw': (1, 1),
    'va': (1000, 1),
    'kva': (1000000, 1),
    'btu/h': (293071, 1000),
}
VA_UNITS = frozenset(('va', 'kva'))
SRC_RANK = {'pdu': 0, 'bmc': 1, 'agent': 2}
PRIORITIES = ('gold', 'silver', 'bronze')

GROUP_CHARS = (' ', '\u00a0', '\u202f', '\u2009', "'", '`')
MISSING_WORDS = frozenset(('', '-', 'n/a', 'null', 'nan'))
NUMBER_RE = re.compile(
    r'^[+-]?(?:[0-9.,\' \u00a0\u202f\u2009`]*[0-9])(?:[eE][+-]?[0-9]+)?$')
NUMBER_PREFIX_RE = re.compile(
    r'^[+-]?(?:[0-9.,\' \u00a0\u202f\u2009`]*[0-9])(?:[eE][+-]?[0-9]+)?')


class BuildError(Exception):
    """A malformed or unusable input."""


def fail(message, code=3):
    text = ' '.join(str(message).split())
    sys.stderr.write('%s: error: %s\n' % (PROG, text))
    sys.exit(code)


# ---------------------------------------------------------------- numbers

def split_number(text):
    """Split a written value into its exact number and any trailing unit text.

    Returns (numerator, denominator, tail) or (None, None, '') for a missing value.
    """
    s = (text or '').strip()
    if s.lower() in MISSING_WORDS:
        return None, None, ''
    percent = ''
    if s.endswith('%'):
        percent = '%'
        s = s[:-1].rstrip()
    m = NUMBER_PREFIX_RE.match(s)
    if not m:
        raise BuildError('not a number: %r' % text)
    num = m.group(0)
    tail = s[m.end():].strip()
    if percent:
        tail = (tail + ' ' + percent).strip()
    last_dot = num.rfind('.')
    last_com = num.rfind(',')
    if last_dot >= 0 and last_com >= 0:
        sep = '.' if last_dot > last_com else ','
    elif last_dot >= 0:
        sep = '.' if num.count('.') == 1 else None
    elif last_com >= 0:
        sep = ',' if num.count(',') == 1 else None
    else:
        sep = None
    if sep:
        head, frac = num.rsplit(sep, 1)
    else:
        head, frac = num, ''
    for ch in GROUP_CHARS + ('.', ','):
        head = head.replace(ch, '')
    if not head:
        head = '0'
    if frac:
        d = Decimal(head + '.' + frac)
    else:
        d = Decimal(head)
    ratio = d.as_integer_ratio()
    return ratio[0], ratio[1], tail


def is_number(text):
    s = (text or '').strip()
    if not s or s.lower() in MISSING_WORDS:
        return False
    return bool(NUMBER_RE.match(s))


def num_ratio(text):
    n, d, tail = split_number(text)
    if n is None:
        raise BuildError('missing number: %r' % text)
    if tail:
        raise BuildError('unexpected text after number: %r' % text)
    return n, d


def round_ratio_half_even(n, d):
    """Round the exact rational n/d half to even to an integer."""
    if d < 0:
        n, d = -n, -d
    q, r = divmod(n, d)
    twice = 2 * r
    if twice > d or (twice == d and q % 2 != 0):
        q += 1
    return q


def round_ratio_down(n, d):
    if d < 0:
        n, d = -n, -d
    return n // d


def dec_str(scaled, places):
    """Format an integer scaled by 10^-places with exactly `places` decimals."""
    sign = '-' if scaled < 0 else ''
    scaled = abs(scaled)
    if places == 0:
        return sign + str(scaled)
    whole, frac = divmod(scaled, 10 ** places)
    return '%s%d.%0*d' % (sign, whole, places, frac)


def scaled_round(n, d, places):
    """Round n/d half to even, returned as an integer scaled by 10^places."""
    if d < 0:
        n, d = -n, -d
    return round_ratio_half_even(n * 10 ** places, d)


def attr_number_int(text):
    """A number written in attrs, as a plain integer."""
    n, d = num_ratio(text)
    return round_ratio_half_even(n, d)


# ---------------------------------------------------------------- times

MONTHS = {'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
          'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12}
EPOCH_S_RE = re.compile(r'^\d{10}$')
EPOCH_MS_RE = re.compile(r'^\d{13}$')
COMPACT_RE = re.compile(r'^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z$')
ISO_RE = re.compile(r'^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})'
                    r'(Z|[+-]\d{2}:?\d{2})?$')
RFC2822_RE = re.compile(r'^(?:[A-Za-z]{3}, )?(\d{1,2}) ([A-Za-z]{3}) (\d{4}) '
                        r'(\d{2}):(\d{2}):(\d{2}) ([+-])(\d{2})(\d{2})$')
SERIAL_DAY_RE = re.compile(r'^[+-]?[0-9]+(?:[.,][0-9]+)?$')

EPOCH = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
SERIAL_ORIGIN = datetime.datetime(1899, 12, 30, tzinfo=datetime.timezone.utc)
STD_OFFSET = {'fra1': 3600, 'iad2': -18000, 'den1': -25200, 'sin1': 28800}
DST_OFFSET = {'fra1': 7200, 'iad2': -14400, 'den1': -21600}


def _nth_weekday(year, month, weekday, n):
    d = datetime.date(year, month, 1)
    offset = (weekday - d.weekday()) % 7
    return d + datetime.timedelta(days=offset + 7 * (n - 1))


def _last_weekday(year, month, weekday):
    nxt = datetime.date(year + (month == 12), month % 12 + 1, 1)
    back = 1 + ((nxt.weekday() - weekday - 1) % 7)
    return nxt - datetime.timedelta(days=back)


def dst_bounds(site, year):
    """(start_utc, end_utc) of the daylight period touching `year`."""
    if site == 'fra1':
        start = datetime.datetime.combine(_last_weekday(year, 3, 6), datetime.time(1, 0))
        end = datetime.datetime.combine(_last_weekday(year, 10, 6), datetime.time(1, 0))
    elif site == 'iad2':
        start = datetime.datetime.combine(_nth_weekday(year, 3, 6, 2), datetime.time(7, 0))
        end = datetime.datetime.combine(_nth_weekday(year, 11, 6, 1), datetime.time(6, 0))
    elif site == 'den1':
        start = datetime.datetime.combine(_nth_weekday(year, 3, 6, 2), datetime.time(9, 0))
        end = datetime.datetime.combine(_nth_weekday(year, 11, 6, 1), datetime.time(8, 0))
    else:
        return None
    return (start.replace(tzinfo=datetime.timezone.utc), end.replace(tzinfo=datetime.timezone.utc))


def local_to_utc(site, naive):
    std = STD_OFFSET.get(site, 0)
    cand = (naive - datetime.timedelta(seconds=std)).replace(tzinfo=datetime.timezone.utc)
    bounds = dst_bounds(site, naive.year)
    if bounds is not None and bounds[0] <= cand < bounds[1]:
        cand = (naive - datetime.timedelta(seconds=DST_OFFSET[site])).replace(
            tzinfo=datetime.timezone.utc)
    return cand


def parse_time(text, site):
    """Parse a written time to a UTC datetime. `site` is used for offset-less times."""
    s = (text or '').strip()
    if not s:
        return None
    m = ISO_RE.match(s)
    if m:
        y, mo, d, h, mi, sec, off = m.groups()
        try:
            naive = datetime.datetime(int(y), int(mo), int(d), int(h), int(mi), int(sec))
        except ValueError:
            raise BuildError('bad time: %r' % text)
        if off is None:
            return local_to_utc(site, naive)
        if off == 'Z':
            return naive.replace(tzinfo=datetime.timezone.utc)
        sign = 1 if off[0] == '+' else -1
        digits = off[1:].replace(':', '')
        delta = datetime.timedelta(hours=int(digits[:2]), minutes=int(digits[2:4]))
        return (naive - sign * delta).replace(tzinfo=datetime.timezone.utc)
    m = COMPACT_RE.match(s)
    if m:
        y, mo, d, h, mi, sec = (int(x) for x in m.groups())
        try:
            return datetime.datetime(y, mo, d, h, mi, sec, tzinfo=datetime.timezone.utc)
        except ValueError:
            raise BuildError('bad time: %r' % text)
    if EPOCH_S_RE.match(s):
        return EPOCH + datetime.timedelta(seconds=int(s))
    if EPOCH_MS_RE.match(s):
        return EPOCH + datetime.timedelta(milliseconds=int(s))
    m = RFC2822_RE.match(s)
    if m:
        day, mon, year, h, mi, sec, sign, oh, om = m.groups()
        if mon.lower() not in MONTHS:
            raise BuildError('bad time: %r' % text)
        try:
            naive = datetime.datetime(int(year), MONTHS[mon.lower()], int(day),
                                       int(h), int(mi), int(sec))
        except ValueError:
            raise BuildError('bad time: %r' % text)
        delta = datetime.timedelta(hours=int(oh), minutes=int(om))
        return (naive + (-1 if sign == '+' else 1) * delta).replace(tzinfo=datetime.timezone.utc)
    if SERIAL_DAY_RE.match(s):
        n, d = num_ratio(s)
        secs = round_ratio_half_even(n * 86400, d)
        return SERIAL_ORIGIN + datetime.timedelta(seconds=secs)
    raise BuildError('bad time: %r' % text)


def utc_str(dt):
    if dt is None:
        return ''
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')


# ---------------------------------------------------------------- source readers

SLOT_NAMES = ('id', 'kind', 'subject', 'at', 'value', 'unit', 'attrs', 'note')
WORD2SLOT = {
    'rec_id': 'id', 'record': 'id', 'id': 'id', 'entry': 'id',
    'rtype': 'kind', 'class': 'kind', 'type': 'kind', 'kind': 'kind',
    'node': 'subject', 'subject': 'subject', 'target': 'subject', 'object': 'subject',
    'when': 'at', 'at': 'at', 'ts': 'at', 'time': 'at',
    'val': 'value', 'reading': 'value', 'amount': 'value', 'value': 'value',
    'u': 'unit', 'units': 'unit', 'unit': 'unit', 'uom': 'unit',
    'attrs': 'attrs', 'meta': 'attrs', 'props': 'attrs', 'detail': 'attrs',
    'memo': 'note', 'remark': 'note', 'note': 'note', 'comment': 'note',
}
_STRIP_WORD = re.compile(r'^(?:x-)?(?:columns?)[:\s]*|^[#+\s]*')


def slot_of(word):
    return WORD2SLOT.get(_STRIP_WORD.sub('', (word or '').strip().strip('"').lower()).strip())


def blank_record():
    return dict.fromkeys(SLOT_NAMES, '')


def cells_to_records(cellrows, slots=None):
    out = []
    for cells in cellrows:
        rec = blank_record()
        if slots:
            for slot, cell in zip(slots, cells):
                if slot:
                    rec[slot] = cell
        else:
            rec['id'] = cells[0] if cells else ''
            for slot, cell in zip(('kind', 'subject', 'at', 'value', 'unit', 'attrs', 'note'),
                                  cells[1:]):
                rec[slot] = cell
        out.append(rec)
    return out


def pipe_cells(line):
    return [c.strip() for c in line.split('|')]


def is_header(cells):
    slots = [slot_of(c) for c in cells]
    return bool(slots) and slots[0] == 'id' and all(slots)


def pipe_rows(lines):
    slots = None
    rows = []
    for line in lines:
        cells = pipe_cells(line)
        if len(cells) < 3:
            continue
        if is_header(cells):
            if slots is None:
                slots = [slot_of(c) for c in cells]
            continue
        rows.append(cells)
    return cells_to_records(rows, slots)


def read_csv(path, delim):
    rows = []
    slots = None
    with open(path, encoding='utf-8', errors='replace', newline='') as fh:
        for cells in csv.reader(fh, delimiter=delim):
            if not cells or not any(c.strip() for c in cells):
                continue
            if slots is None and is_header(cells):
                slots = [slot_of(c) for c in cells]
                continue
            rows.append(cells)
    return cells_to_records(rows, slots)


def read_md(path):
    lines = []
    with open(path, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            line = line.rstrip('\n')
            if line.startswith('|') and line.rstrip().endswith('|'):
                cells = [c.strip() for c in line.strip().strip('|').split('|')]
                if len(cells) >= 3 and not all(set(c) <= set('- ') for c in cells):
                    lines.append(' | '.join(cells))
    return pipe_rows(lines)


def read_ini(path):
    rows = []
    with open(path, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            s = line.strip()
            if not s or s[0] in ';#[' or '=' not in s:
                continue
            key, rest = s.split('=', 1)
            cells = pipe_cells(rest)
            if len(cells) >= 3:
                rows.append([key.strip()] + cells)
    return cells_to_records(rows)


def object_records(obj, out):
    if isinstance(obj, list):
        for item in obj:
            object_records(item, out)
    elif isinstance(obj, dict):
        if obj and all(not isinstance(v, (list, dict)) for v in obj.values()):
            rec = blank_record()
            for key, val in obj.items():
                slot = slot_of(key)
                if slot:
                    rec[slot] = '' if val is None else str(val)
            out.append(rec)
        else:
            for val in obj.values():
                if isinstance(val, (list, dict)):
                    object_records(val, out)
    return out


def read_json(path):
    with open(path, encoding='utf-8', errors='replace') as fh:
        return object_records(json.load(fh), [])


def read_jsonl(path):
    out = []
    with open(path, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            s = line.strip()
            if not s:
                continue
            obj = json.loads(s)
            if isinstance(obj, dict):
                rec = blank_record()
                for key, val in obj.items():
                    slot = slot_of(key)
                    if slot:
                        rec[slot] = '' if val is None else str(val)
                out.append(rec)
    return out


def read_yaml(path):
    import yaml
    with open(path, encoding='utf-8', errors='replace') as fh:
        return object_records(yaml.safe_load(fh), [])


def read_toml(path):
    import tomllib
    with open(path, 'rb') as fh:
        return object_records(tomllib.load(fh), [])


def read_xml(path):
    import xml.etree.ElementTree as ET
    out = []
    try:
        for _ev, el in ET.iterparse(path, events=('end',)):
            if not el.attrib:
                continue
            rec = blank_record()
            for key, val in el.attrib.items():
                slot = slot_of(key)
                if slot:
                    rec[slot] = val if val is not None else ''
            if any(rec[s] for s in SLOT_NAMES):
                out.append(rec)
            el.clear()
    except ET.ParseError as exc:
        raise BuildError('%s: %s' % (os.path.basename(path), exc))
    return out


def read_html(path):
    text = open(path, encoding='utf-8', errors='replace').read()
    rows = []
    for m in re.finditer(r'<tr[^>]*>(.*?)</tr>', text, re.S):
        cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', m.group(1), re.S)
        cells = [re.sub(r'<[^>]*>', '', c).strip() for c in cells]
        if len(cells) >= 3:
            rows.append(' | '.join(cells))
    return pipe_rows(rows)


def read_docx(path):
    import docx
    rows = []
    for para in docx.Document(path).paragraphs:
        text = para.text or ''
        if '|' in text:
            cells = pipe_cells(text)
            if len(cells) >= 3:
                rows.append(' | '.join(cells))
    return pipe_rows(rows)


def read_pdf(path):
    import logging
    import warnings
    from pypdf import PdfReader
    logging.getLogger('pypdf').setLevel(logging.CRITICAL)
    rows = []
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        for page in PdfReader(path).pages:
            for line in (page.extract_text() or '').split('\n'):
                if '|' in line:
                    cells = pipe_cells(line)
                    if len(cells) >= 3:
                        rows.append(' | '.join(cells))
    return pipe_rows(rows)


def read_xlsx(path):
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = []
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            cells = ['' if c is None else str(c) for c in row]
            if len(cells) >= 3 and any(c.strip() for c in cells):
                rows.append(' | '.join(cells))
    wb.close()
    return pipe_rows(rows)


def read_db(path):
    con = sqlite3.connect('file:%s?mode=ro' % path.replace('?', '%3f'), uri=True)
    try:
        cur = con.cursor()
        tables = [r[0] for r in cur.execute("select name from sqlite_master where type='table'")]
        out = []
        for table in tables:
            cur.execute('select * from "%s"' % table.replace('"', '""'))
            slots = [slot_of(d[0]) for d in cur.description]
            for row in cur.fetchall():
                rec = blank_record()
                for slot, val in zip(slots, row):
                    if slot:
                        rec[slot] = '' if val is None else str(val)
                out.append(rec)
        return out
    finally:
        con.close()


def read_parquet(path):
    import pyarrow.parquet as pq
    table = pq.read_table(path)
    names = table.schema.names
    slots = [slot_of(n) for n in names]
    columns = [table.column(n).to_pylist() for n in names]
    out = []
    for i in range(table.num_rows):
        rec = blank_record()
        for slot, col in zip(slots, columns):
            if slot:
                val = col[i]
                rec[slot] = '' if val is None else str(val)
        out.append(rec)
    return out


def read_ics(path):
    slots = None
    rows = []
    with open(path, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            s = line.rstrip('\n')
            upper = s.upper()
            if upper.startswith('X-COLUMNS:'):
                slots = [slot_of(c) for c in pipe_cells(s.split(':', 1)[1])]
            elif upper.startswith('X-REC:'):
                cells = pipe_cells(s.split(':', 1)[1])
                if len(cells) >= 3:
                    rows.append(cells)
    return cells_to_records(rows, slots)


def read_mbox(path):
    slots = None
    rows = []
    with open(path, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            s = line.rstrip('\n')
            if s.lower().startswith('x-columns:'):
                slots = [slot_of(c) for c in pipe_cells(s.split(':', 1)[1])]
                continue
            if s.startswith('From ') or re.match(r'^(From|To|Subject|Date|Message-ID):', s):
                continue
            if '|' in s:
                cells = pipe_cells(s)
                if len(cells) >= 3:
                    rows.append(cells)
    return cells_to_records(rows, slots)


KV_RE = re.compile(r'([A-Za-z_ -]+?)="([^"]*)"')


def read_log(path):
    out = []
    with open(path, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            s = line.strip()
            if not s or '"' not in s:
                continue
            rec = blank_record()
            for key, val in KV_RE.findall(s):
                slot = slot_of(key)
                if slot and not rec[slot]:
                    rec[slot] = val
            if not rec['id']:
                continue
            out.append(rec)
    return out


def pipe_rows_file(path):
    with open(path, encoding='utf-8', errors='replace') as fh:
        return pipe_rows(fh)


READERS = {
    '.csv': lambda p: read_csv(p, ','),
    '.tsv': lambda p: read_csv(p, '\t'),
    '.md': read_md,
    '.ini': read_ini,
    '.jsonl': read_jsonl,
    '.json': read_json,
    '.yaml': read_yaml,
    '.yml': read_yaml,
    '.toml': read_toml,
    '.xml': read_xml,
    '.html': read_html,
    '.htm': read_html,
    '.docx': read_docx,
    '.pdf': read_pdf,
    '.xlsx': read_xlsx,
    '.db': read_db,
    '.sqlite': read_db,
    '.parquet': read_parquet,
    '.ics': read_ics,
    '.mbox': read_mbox,
    '.log': read_log,
}


def read_source(path):
    ext = os.path.splitext(path)[1].lower()
    reader = READERS.get(ext, pipe_rows_file)
    try:
        return reader(path)
    except BuildError:
        raise
    except Exception as exc:
        raise BuildError('%s: %s' % (os.path.basename(path), exc))


def parse_attrs(text, where):
    out = {}
    for part in (text or '').split(';'):
        if not part.strip():
            continue
        if '=' not in part:
            raise BuildError('%s: bad attrs %r' % (where, text))
        key, val = part.split('=', 1)
        key = key.strip().lower()
        if key in out:
            raise BuildError('%s: duplicate attr %r' % (where, key))
        out[key] = val.strip()
    return out


# ---------------------------------------------------------------- the fleet

HOST_RE = re.compile(r'^n\d{5}$')
HOST_SUFFIX_RE = re.compile(r'\.pwr\.corp$', re.I)
REC_PREFIX_RE = re.compile(r'^rec:', re.I)
SP_PARAMS = ('cont', 'derate', 'volts', 'tariff', 'pue', 'step', 'margin', 'warn', 'crit',
             'pool', 'corr')
AMEND_FIELDS = ('floor_w', 'cap_ceiling_w', 'priority', 'breaker_a')
PRIORITY_SET = frozenset(PRIORITIES)


def canonical_host(name):
    s = HOST_SUFFIX_RE.sub('', (name or '').strip()).lower()
    return s if HOST_RE.match(s) else None


def rec_target_id(subject):
    """The record id named by a VO, ER or RT subject."""
    return REC_PREFIX_RE.sub('', (subject or '').strip()).lower()


def unit_word(text):
    """A written unit word, normalised for the unit factor table."""
    s = (text or '').strip().lower()
    if s in ('watt', 'watts'):
        return 'w'
    if s in ('btu/hr', 'btu/hour'):
        return 'btu/h'
    return s


def reading_unit(rec):
    """The unit a reading is written in, from the unit column or the value itself."""
    unit = unit_word(rec.unit)
    if unit:
        return unit
    _n, _d, tail = split_number(rec.value)
    return unit_word(tail)


class Source(object):
    __slots__ = ('name', 'path', 'superseded', 'records')

    def __init__(self, name, path, superseded, records):
        self.name = name
        self.path = path
        self.superseded = superseded
        self.records = records


class Rec(object):
    __slots__ = ('src', 'index', 'kind', 'subject', 'at', 'value', 'unit', 'attrs', 'note',
                 'id', 'key', 'attr', 'time', 'host', 'in_force', 'voided')

    def __init__(self, src, index, raw):
        rid = (raw['id'] or '').strip()
        if not rid:
            raise BuildError('%s: data line %d has no record id' % (src.name, index + 1))
        kind = (raw['kind'] or '').strip().upper()
        if kind not in RECORD_KINDS:
            raise BuildError('%s: unknown record kind %r in %s'
                             % (src.name, raw['kind'], rid))
        where = '%s %s' % (src.name, rid)
        self.src = src
        self.index = index
        self.id = rid
        self.key = rid.lower()
        self.kind = kind
        self.subject = (raw['subject'] or '').strip()
        self.at = (raw['at'] or '').strip()
        self.value = (raw['value'] or '').strip()
        self.unit = (raw['unit'] or '').strip()
        self.attrs = (raw['attrs'] or '').strip()
        self.note = (raw['note'] or '').strip()
        self.attr = parse_attrs(self.attrs, where) if self.attrs else {}
        self.time = None
        self.host = None
        self.in_force = False
        self.voided = False

    def where(self):
        return '%s %s' % (self.src.name, self.id)


class Fleet(object):
    """Phase 1: the settled facts of one source tree."""

    def __init__(self, data_dir):
        if not os.path.isdir(data_dir):
            fail('source directory not found: %s' % data_dir)
        try:
            names = sorted(os.listdir(data_dir))
        except OSError as exc:
            fail('cannot read source directory %s: %s' % (data_dir, exc))
        self.data_dir = data_dir
        self.sources = []
        for name in names:
            path = os.path.join(data_dir, name)
            if not os.path.isfile(path):
                continue
            self.sources.append(Source(name, path, bool(SUPERSEDED_RE.search(name)),
                                       read_source(path)))
        if not self.sources:
            raise BuildError('no source files in %s' % data_dir)
        self.records = []
        self.by_key = {}
        for src in self.sources:
            for index, raw in enumerate(src.records):
                rec = Rec(src, index, raw)
                self.records.append(rec)
                self.by_key.setdefault(rec.key, []).append(rec)
        self.freeze_str, self.window_str = self.standard_times()
        self.freeze = parse_time(self.freeze_str, None)
        self.window_start = parse_time(self.window_str, None)
        self.circuit_sites = {}
        for rec in self.records:
            if rec.kind in ('CV', 'CA'):
                cid = rec.subject.strip().lower()
                if len(cid) >= 4:
                    self.circuit_sites.setdefault(cid, cid[:4])
        self.host_site = {}
        self.serial_hosts = {}
        self.aliases = {}
        self.ratified = set()
        self.voided_keys = set()
        self.effective = {}

    # -- the standard itself ----------------------------------------------

    def standard_times(self):
        freeze, window = FREEZE_DEFAULT, WINDOW_DEFAULT
        pat = re.compile(r'freeze is\s+(\S+)\s+and the telemetry window runs from\s+(\S+)')
        for src in self.sources:
            if src.superseded:
                continue
            with open(src.path, encoding='utf-8', errors='replace') as fh:
                text = fh.read()
            m = pat.search(text)
            if m:
                return m.group(1), m.group(2)
        return freeze, window

    # -- names ------------------------------------------------------------

    def serial_host(self, name):
        return self.serial_hosts.get((name or '').strip().lower())

    def resolve_alias(self, name, when, depth=0):
        if depth > 8:
            return None
        entries = self.aliases.get((name or '').strip().lower())
        if not entries:
            return None
        best = None
        for start, until, target, rid in entries:
            if when is None or start is None:
                continue
            if start <= when < until:
                if best is None or (start, rid) > (best[0], best[1]):
                    best = (start, rid, target)
        if best is None:
            return None
        return self.subject_host(best[2], when, depth + 1)

    def subject_host(self, name, when, depth=0):
        direct = canonical_host(name)
        if direct:
            return direct
        serial = self.serial_host(name)
        if serial:
            return serial
        if depth > 8:
            return None
        return self.resolve_alias(name, when, depth)

    # -- settling records -------------------------------------------------

    def settle(self, rec, depth=0):
        """Work out a record's reading time and, for host records, its host."""
        if rec.kind == 'PV' or not rec.at:
            rec.time = None
            return
        if rec.kind in ('HV', 'QV', 'RD'):
            host = canonical_host(rec.subject) or self.serial_host(rec.subject)
            site = self.host_site.get(host)
            try:
                when = parse_time(rec.at, site)
            except BuildError as exc:
                raise BuildError('%s: %s' % (rec.where(), exc))
            for _round in range(3):
                resolved = self.subject_host(rec.subject, when)
                if resolved == host:
                    break
                host = resolved
                site = self.host_site.get(host)
                try:
                    when = parse_time(rec.at, site)
                except BuildError as exc:
                    raise BuildError('%s: %s' % (rec.where(), exc))
            rec.host = host
            rec.time = when
            return
        if rec.kind == 'AM':
            host = canonical_host(rec.subject)
            site = self.host_site.get(host) if host else \
                self.circuit_sites.get(rec.subject.strip().lower())
            rec.time = self.parse_at(rec, site)
            return
        if rec.kind in ('CV', 'CA'):
            rec.time = self.parse_at(rec, self.circuit_sites.get(rec.subject.strip().lower()))
            return
        if rec.kind == 'TN':
            parts = rec.subject.split('@')
            site = parts[1].strip().lower() if len(parts) == 2 else None
            rec.time = self.parse_at(rec, site)
            return
        if rec.kind == 'SP':
            parts = rec.subject.split(':')
            site = parts[0].strip().lower() if len(parts) == 2 else None
            rec.time = self.parse_at(rec, site)
            return
        if rec.kind in ('VO', 'ER', 'RT'):
            site = None
            if depth < 4:
                named = self.by_key.get(rec_target_id(rec.subject))
                if named:
                    for other in named:
                        self.settle(other, depth + 1)
                    site = self.record_site(named[0])
            rec.time = self.parse_at(rec, site)
            return
        rec.time = self.parse_at(rec, None)

    def parse_at(self, rec, site):
        try:
            return parse_time(rec.at, site)
        except BuildError as exc:
            raise BuildError('%s: %s' % (rec.where(), exc))

    def record_site(self, rec):
        if rec.kind in ('HV', 'QV', 'RD'):
            return self.host_site.get(rec.host)
        if rec.kind == 'AM':
            host = canonical_host(rec.subject)
            if host:
                return self.host_site.get(host)
            return self.circuit_sites.get(rec.subject.strip().lower())
        if rec.kind in ('CV', 'CA'):
            return self.circuit_sites.get(rec.subject.strip().lower())
        if rec.kind == 'TN':
            parts = rec.subject.split('@')
            return parts[1].strip().lower() if len(parts) == 2 else None
        if rec.kind == 'SP':
            parts = rec.subject.split(':')
            return parts[0].strip().lower() if len(parts) == 2 else None
        if rec.kind in ('VO', 'ER', 'RT'):
            named = self.by_key.get(rec_target_id(rec.subject))
            return self.record_site(named[0]) if named else None
        return None

    def settle_all(self):
        for rec in self.records:
            if rec.kind not in ('VO', 'ER', 'RT'):
                self.settle(rec)
        for rec in self.records:
            if rec.kind in ('VO', 'ER', 'RT'):
                self.settle(rec)

    # -- in force, voiding, names -----------------------------------------

    def apply_force_rules(self):
        ratified = set()
        for rec in self.records:
            if rec.kind != 'RT' or rec.src.superseded or rec.time is None:
                continue
            if rec.time >= self.freeze:
                continue
            named = rec.attr.get('file', '').strip()
            if not named:
                raise BuildError('%s: ratification without a file' % rec.where())
            ratified.add((rec_target_id(rec.subject), named))
        self.ratified = ratified
        for rec in self.records:
            rec.in_force = (not rec.src.superseded) or ((rec.key, rec.src.name) in ratified)
        voided = set()
        for rec in self.records:
            if rec.kind != 'VO' or not rec.in_force or rec.time is None:
                continue
            if rec.time >= self.freeze:
                continue
            voided.add(rec_target_id(rec.subject))
        self.voided_keys = voided
        for rec in self.records:
            rec.voided = rec.kind not in ('VO', 'RT') and rec.key in voided

    def build_names(self):
        self.serial_hosts = {}
        for rec in self.records:
            if rec.kind != 'HV' or not rec.in_force or rec.voided:
                continue
            if rec.time is None or rec.time >= self.freeze:
                continue
            host = canonical_host(rec.subject)
            serial = rec.attr.get('serial', '').strip().lower()
            if host and serial and serial not in self.serial_hosts:
                self.serial_hosts[serial] = host
        self.aliases = {}
        for rec in self.records:
            if rec.kind != 'AL' or not rec.in_force or rec.voided:
                continue
            if rec.time is None or rec.time >= self.freeze:
                continue
            target = rec.attr.get('target', '').strip()
            if not target:
                raise BuildError('%s: alias without a target' % rec.where())
            until_text = rec.attr.get('until', '').strip()
            if not until_text:
                raise BuildError('%s: alias without an until time' % rec.where())
            until = self.parse_at(rec, None)
            until = parse_time(until_text, None)
            self.aliases.setdefault(rec.subject.strip().lower(), []).append(
                (rec.time, until, target, rec.key))

    # -- effective records -------------------------------------------------

    def revision_rank(self, rec):
        try:
            return num_ratio(rec.value)
        except BuildError as exc:
            raise BuildError('%s: %s' % (rec.where(), exc))

    def select_effective(self):
        groups = {}
        for rec in self.records:
            if not rec.in_force or rec.voided:
                continue
            if rec.kind not in ('HV', 'CV', 'MV', 'PR', 'QV', 'SP', 'TN'):
                continue
            if rec.time is None or rec.time >= self.freeze:
                continue
            if rec.kind in ('HV', 'QV'):
                subject = rec.host
            else:
                subject = rec.subject.strip().lower()
            if subject is None:
                continue
            groups.setdefault((rec.kind, subject), []).append(rec)
        effective = {}
        for key, recs in groups.items():
            best = None
            for rec in recs:
                rank = (self.revision_rank(rec), rec.time, rec.key)
                if best is None or rank > best[0]:
                    best = (rank, rec)
            effective[key] = best[1]
        self.effective = effective

    def signature(self):
        hv = tuple(sorted((host, rec.key) for host, rec in self.effective.items()
                          if rec.kind == 'HV'))
        return (hv, frozenset(self.voided_keys), frozenset(self.ratified),
                tuple(sorted(self.host_site.items())))

    def build(self):
        prov = {}
        for rec in self.records:
            if rec.kind != 'HV':
                continue
            host = canonical_host(rec.subject)
            rack = rec.attr.get('rack', '').strip()
            if host and rack and host not in prov:
                prov[host] = rack[:4]
        self.host_site = prov
        self.apply_force_rules()
        self.build_names()
        previous = None
        for _round in range(5):
            self.settle_all()
            self.apply_force_rules()
            self.build_names()
            self.select_effective()
            sites = {}
            for (kind, subject), rec in self.effective.items():
                if kind == 'HV':
                    sites[subject] = rec.attr.get('rack', '')[:4]
            sig = self.signature()
            if sig == previous and sites == self.host_site:
                break
            previous = sig
            self.host_site = sites
        self.settle_all()
        self.apply_force_rules()
        self.build_names()
        self.select_effective()
        self.effective_hv = {k[1]: r for k, r in self.effective.items() if k[0] == 'HV'}
        self.effective_cv = {k[1]: r for k, r in self.effective.items() if k[0] == 'CV'}
        self.effective_mv = {k[1]: r for k, r in self.effective.items() if k[0] == 'MV'}
        self.effective_pr = {k[1]: r for k, r in self.effective.items() if k[0] == 'PR'}
        self.effective_qv = {k[1]: r for k, r in self.effective.items() if k[0] == 'QV'}
        self.effective_sp = {k[1]: r for k, r in self.effective.items() if k[0] == 'SP'}
        self.effective_tn = {k[1]: r for k, r in self.effective.items() if k[0] == 'TN'}

    def live(self, rec):
        return rec.in_force and not rec.voided

    def site_params(self, site):
        values = {}
        for param in SP_PARAMS:
            rec = self.effective_sp.get('%s:%s' % (site, param))
            if rec is None:
                raise BuildError('no effective %s parameter for site %s' % (param, site))
            if param not in rec.attr:
                raise BuildError('%s: parameter record without %s' % (rec.where(), param))
            values[param] = attr_number_int(rec.attr[param])
        return values

# ---------------------------------------------------------------- phase 1: the tables

def attrs_extra(attr):
    """Attrs as key=value pairs, keys lower case and sorted, numbers as integers."""
    parts = []
    for key in sorted(attr):
        val = attr[key]
        if is_number(val):
            try:
                n, d = num_ratio(val)
            except BuildError:
                parts.append('%s=%s' % (key, val))
                continue
            parts.append('%s=%d' % (key, round_ratio_half_even(n, d)))
        else:
            parts.append('%s=%s' % (key, val))
    return ';'.join(parts)


def efficiency_bp(rec):
    """A PSU efficiency point, in basis points."""
    n, d, tail = split_number(rec.value)
    if n is None:
        raise BuildError('%s: efficiency point without a value' % rec.where())
    unit = unit_word(rec.unit) or unit_word(tail)
    if unit == '%':
        return round_ratio_half_even(n * 100, d)
    if unit == 'frac':
        return round_ratio_half_even(n * 10000, d)
    if unit == 'bp':
        return round_ratio_half_even(n, d)
    if unit == 'permille':
        return round_ratio_half_even(n * 10, d)
    raise BuildError('%s: efficiency point without a unit' % rec.where())


def reading_base_mw(rec, unit):
    """The written number times its unit factor, in milliwatts, half to even."""
    n, d, tail = split_number(rec.value)
    if n is None:
        return None
    if unit not in UNIT_FACTORS:
        raise BuildError('%s: unknown unit %r' % (rec.where(), unit))
    factor_n, factor_d = UNIT_FACTORS[unit]
    return round_ratio_half_even(n * factor_n, d * factor_d)


class Host(object):
    __slots__ = ('host', 'site', 'rack', 'model', 'psu', 'psu_count', 'tenant', 'priority',
                 'domain', 'nameplate_w', 'idle_w', 'floor_w', 'ceiling_w', 'model_rec',
                 'demand')

    def __init__(self, host):
        self.host = host


def phase1_data(fleet):
    """Everything the phase-1 outputs need, in output order."""
    data = {}
    data['freeze_utc'] = fleet.freeze_str
    data['window_start_utc'] = fleet.window_str

    # ---- hosts ---------------------------------------------------------
    hosts = {}
    for host, hv in fleet.effective_hv.items():
        attr = hv.attr
        for key in ('rack', 'model', 'psu', 'n', 'tenant', 'status', 'serial'):
            if key not in attr:
                raise BuildError('%s: host revision of %s without %s' % (hv.where(), host, key))
        if attr['status'].strip().lower() != 'active':
            continue
        info = Host(host)
        info.rack = attr['rack'].strip()
        info.site = info.rack[:4]
        info.model = attr['model'].strip()
        info.psu = attr['psu'].strip()
        try:
            info.psu_count = attr_number_int(attr['n'])
        except BuildError as exc:
            raise BuildError('%s: %s' % (hv.where(), exc))
        info.tenant = attr['tenant'].strip()
        model_rec = fleet.effective_mv.get(info.model.lower())
        if model_rec is None:
            raise BuildError('%s: no effective model revision for %s' % (hv.where(), info.model))
        for key in ('va', 'pf', 'idle', 'domain'):
            if key not in model_rec.attr:
                raise BuildError('%s: model revision without %s' % (model_rec.where(), key))
        info.model_rec = model_rec
        va = attr_number_int(model_rec.attr['va'])
        pf = attr_number_int(model_rec.attr['pf'])
        info.nameplate_w = round_ratio_half_even(va * pf, 1000)
        info.idle_w = attr_number_int(model_rec.attr['idle'])
        info.domain = model_rec.attr['domain'].strip().upper()
        policy = fleet.effective_qv.get(host)
        if policy is None:
            info.priority = 'bronze'
            policy_floor = 0
        else:
            for key in ('prio', 'floor'):
                if key not in policy.attr:
                    raise BuildError('%s: policy revision without %s' % (policy.where(), key))
            info.priority = policy.attr['prio'].strip().lower()
            if info.priority not in PRIORITY_SET:
                raise BuildError('%s: unknown priority %r' % (policy.where(),
                                                              policy.attr['prio']))
            policy_floor = attr_number_int(policy.attr['floor'])
        info.floor_w = info.idle_w if info.idle_w > policy_floor else policy_floor
        info.ceiling_w = None
        hosts[host] = info

    # ---- amendments ----------------------------------------------------
    pre_freeze_amendments = []
    carried_amendments = []
    for rec in fleet.records:
        if rec.kind != 'AM' or not fleet.live(rec):
            continue
        if rec.time is None:
            raise BuildError('%s: amendment without a time' % rec.where())
        field = rec.attr.get('field', '').strip().lower()
        if field not in AMEND_FIELDS:
            raise BuildError('%s: unknown amendment field %r' % (rec.where(),
                                                                 rec.attr.get('field')))
        value_text = rec.attr.get('value', '')
        if field == 'priority':
            value = value_text.strip().lower()
            if value not in PRIORITY_SET:
                raise BuildError('%s: unknown priority %r' % (rec.where(), value_text))
        else:
            try:
                value = attr_number_int(value_text)
            except BuildError as exc:
                raise BuildError('%s: %s' % (rec.where(), exc))
        host = canonical_host(rec.subject)
        target = host
        if host is None:
            target = rec.subject.strip().lower()
            if target not in fleet.effective_cv:
                continue
        item = (rec.time, rec.key, rec.id, target, field, value)
        if rec.time < fleet.freeze:
            pre_freeze_amendments.append(item)
        else:
            carried_amendments.append(item)
    pre_freeze_amendments.sort(key=lambda item: (item[0], item[1]))
    carried_amendments.sort(key=lambda item: (item[0], item[1]))

    for _when, _key, _rid, target, field, value in pre_freeze_amendments:
        info = hosts.get(target)
        if info is not None:
            if field == 'floor_w':
                info.floor_w = value
            elif field == 'cap_ceiling_w':
                info.ceiling_w = value
            elif field == 'priority':
                info.priority = value

    # ---- circuits -------------------------------------------------------
    circuits = {}
    for cid, cv in fleet.effective_cv.items():
        attr = cv.attr
        for key in ('rack', 'feed', 'volts', 'amps'):
            if key not in attr:
                raise BuildError('%s: circuit revision without %s' % (cv.where(), key))
        volts = attr_number_int(attr['volts'])
        breaker = attr_number_int(attr['amps'])
        circuits[cid] = {
            'circuit_id': cv.subject.strip(),
            'site': cid[:4],
            'rack_id': attr['rack'].strip(),
            'feed': attr['feed'].strip().upper(),
            'voltage_v': volts,
            'breaker_a': breaker,
        }
    for _when, _key, _rid, target, field, value in pre_freeze_amendments:
        if field == 'breaker_a' and target in circuits:
            circuits[target]['breaker_a'] = value
    for cid, circuit in circuits.items():
        params = fleet.site_params(circuit['site'])
        circuit['cont_pm'] = params['cont']
        circuit['derate_pm'] = params['derate']
        watts = circuit['voltage_v'] * circuit['breaker_a'] * params['cont'] * params['derate']
        circuit['usable_w'] = round_ratio_down(watts, 1000000)

    # ---- PSU tables -----------------------------------------------------
    psu_rows = []
    psu_models = {}
    for rec in fleet.records:
        if rec.kind != 'PV' or not fleet.live(rec):
            continue
        model = rec.subject.strip()
        key = model.lower()
        if 'load' not in rec.attr:
            raise BuildError('%s: efficiency point without a load' % rec.where())
        load = attr_number_int(rec.attr['load'])
        psu_rows.append((model, key, load, efficiency_bp(rec), rec))
        psu_models.setdefault(key, model)
    psu_rated = {}
    for key in psu_models:
        pr = fleet.effective_pr.get(key)
        if pr is None:
            raise BuildError('no effective PSU revision for %s' % psu_models[key])
        if 'rated' not in pr.attr:
            raise BuildError('%s: PSU revision without a rating' % pr.where())
        psu_rated[key] = attr_number_int(pr.attr['rated'])
    psu_rows.sort(key=lambda row: (row[1], row[2]))
    data['psu_rows'] = psu_rows
    data['psu_rated'] = psu_rated
    data['psu_models'] = psu_models

    # ---- efficiency lookups --------------------------------------------
    psu_eff = {}
    for model, key, load, eff_bp, _rec in psu_rows:
        psu_eff.setdefault(key, {})[load] = eff_bp

    def eff_at(psu_key, load_pm):
        table = psu_eff.get(psu_key)
        if not table:
            raise BuildError('no efficiency points for PSU model %s' % psu_key)
        eff = table.get(load_pm)
        if eff is None:
            raise BuildError('no efficiency point for %s at load %d' % (psu_key, load_pm))
        return eff

    def load_pm_of(watts_milli, psu_key, count):
        """The load in per mille of a draw over the PSUs, held between 1 and 1000."""
        rated = psu_rated.get(psu_key)
        if rated is None:
            raise BuildError('no effective PSU revision for %s' % psu_key)
        load = round_ratio_half_even(watts_milli, count * rated)
        if load < 1:
            return 1
        if load > 1000:
            return 1000
        return load

    # ---- readings -------------------------------------------------------
    ca_table = {}
    for rec in fleet.records:
        if rec.kind != 'CA' or not fleet.live(rec):
            continue
        if rec.time is None or rec.time >= fleet.freeze:
            continue
        outlet = rec.subject.strip().lower()
        for key in ('gain', 'offset'):
            if key not in rec.attr:
                raise BuildError('%s: calibration without %s' % (rec.where(), key))
        ca_table.setdefault(outlet, []).append(rec)
    for entries in ca_table.values():
        entries.sort(key=lambda rec: (rec.time, rec.key))

    pf_table = {}
    for rec in fleet.records:
        if rec.kind != 'PF' or not fleet.live(rec):
            continue
        if rec.time is None or rec.time >= fleet.freeze:
            continue
        if 'scale' not in rec.attr:
            raise BuildError('%s: export profile without a scale' % rec.where())
        batch = rec.subject.strip().lower()
        current = pf_table.get(batch)
        if current is None or (rec.time, rec.key) > (current.time, current.key):
            pf_table[batch] = rec

    er_by_target = {}
    for rec in fleet.records:
        if rec.kind != 'ER' or not fleet.live(rec):
            continue
        if rec.time is None or rec.time >= fleet.freeze:
            continue
        target = rec_target_id(rec.subject)
        current = er_by_target.get(target)
        if current is None or (rec.time, rec.key) > (current.time, current.key):
            er_by_target[target] = rec

    readings = {}
    for rec in fleet.records:
        if rec.kind != 'RD' or not fleet.live(rec):
            continue
        if rec.time is None or not (fleet.window_start <= rec.time < fleet.freeze):
            continue
        host = rec.host
        if host is None or host not in hosts:
            continue
        for key in ('src', 'dom', 'batch'):
            if key not in rec.attr:
                raise BuildError('%s: reading without %s' % (rec.where(), key))
        src = rec.attr['src'].strip().lower()
        dom = rec.attr['dom'].strip().upper()
        if src not in SRC_RANK:
            raise BuildError('%s: unknown reading source %r' % (rec.where(), rec.attr['src']))
        if dom not in ('AC', 'DC'):
            raise BuildError('%s: unknown domain %r' % (rec.where(), rec.attr['dom']))
        unit = reading_unit(rec)
        if unit and unit not in UNIT_FACTORS:
            raise BuildError('%s: unknown unit %r' % (rec.where(), unit))
        base = reading_base_mw(rec, unit) if unit else None
        value = None
        if base is not None:
            batch = rec.attr['batch'].strip().lower()
            profile = pf_table.get(batch)
            if profile is not None:
                scale = attr_number_int(profile.attr['scale'])
                base = round_ratio_half_even(base * scale, 1000)
            info = hosts[host]
            if unit in VA_UNITS:
                pf = attr_number_int(info.model_rec.attr['pf'])
                base = round_ratio_half_even(base * pf, 1000)
            if src == 'pdu':
                outlet = rec.attr.get('outlet', '').strip().lower()
                if not outlet:
                    raise BuildError('%s: pdu reading without an outlet' % rec.where())
                best = None
                for cal in ca_table.get(outlet, ()):
                    if cal.time <= rec.time:
                        best = cal
                    else:
                        break
                if best is not None:
                    gain = attr_number_int(best.attr['gain'])
                    offset = attr_number_int(best.attr['offset'])
                    base = round_ratio_half_even(base * (1000000 + gain), 1000000) + offset
            if dom == 'DC':
                psu_key = info.psu.lower()
                if info.psu_count <= 0:
                    raise BuildError('%s: host %s has no PSUs' % (rec.where(), host))
                load = load_pm_of(base, psu_key, info.psu_count)
                base = round_ratio_half_even(base * 10000, eff_at(psu_key, load))
            value = base
        if value is not None:
            replacement = er_by_target.get(rec.key)
            if replacement is not None:
                try:
                    n, d = num_ratio(replacement.value)
                except BuildError as exc:
                    raise BuildError('%s: %s' % (replacement.where(), exc))
                value = round_ratio_half_even(n * 1000, d)
        if value is None:
            continue
        entry = readings.get((host, rec.time))
        rank = SRC_RANK[src]
        if entry is None or rank < entry[0] or (rank == entry[0] and rec.key > entry[2]):
            readings[(host, rec.time)] = (rank, value, rec.key)

    # ---- demand ---------------------------------------------------------
    by_host = {}
    for (host, when), (rank, value, key) in readings.items():
        by_host.setdefault(host, []).append((when, value))
    data['readings'] = by_host
    for host, info in hosts.items():
        samples = by_host.get(host, [])
        samples.sort()
        values = sorted(value for _when, value in samples)
        info.demand = {'samples': len(samples)}
        if values:
            total = sum(values)
            info.demand['mean_w'] = dec_str(scaled_round(total, len(values) * 1000, 1), 1)
            rank = -(-len(values) * 95 // 100)
            info.demand['p95_w'] = dec_str(scaled_round(values[rank - 1], 1000, 1), 1)
            info.demand['peak_w'] = dec_str(scaled_round(max(values), 1000, 1), 1)
            info.demand['energy_wh'] = dec_str(scaled_round(total, 4000, 2), 2)
            info.demand['mean_mw'] = scaled_round(total, len(values), 0)
            info.demand['p95_mw'] = values[rank - 1]
            info.demand['peak_mw'] = max(values)
            info.demand['energy_cwh'] = scaled_round(total, 4000, 2)
        else:
            info.demand['mean_w'] = ''
            info.demand['p95_w'] = ''
            info.demand['peak_w'] = ''
            info.demand['energy_wh'] = ''
            info.demand['mean_mw'] = None
            info.demand['p95_mw'] = None
            info.demand['peak_mw'] = None
            info.demand['energy_cwh'] = None

    order = sorted(hosts.values(), key=lambda info: (info.rack, PRIORITIES.index(info.priority),
                                                      info.host))
    data['hosts'] = hosts
    data['host_order'] = order
    data['circuits'] = circuits
    data['amendments_carried'] = carried_amendments
    data['pre_freeze_amendments'] = pre_freeze_amendments
    data['psu_eff'] = psu_eff
    data['eff_at'] = eff_at
    data['load_pm_of'] = load_pm_of
    return data


# ---------------------------------------------------------------- canonical lines

def canonical_lines(fleet, records):
    lines = []
    for rec in records:
        kind = rec.kind
        if kind == 'RD':
            subject = rec.host if rec.host else rec.subject
            unit = reading_unit(rec)
            if unit and unit not in UNIT_FACTORS:
                raise BuildError('%s: unknown unit %r' % (rec.where(), unit))
            base = reading_base_mw(rec, unit) if unit else None
            value = 'null' if base is None else str(base)
            uc = 'VA' if unit in VA_UNITS else 'W'
            extra = 'batch=%s;dom=%s;outlet=%s;src=%s;uc=%s' % (
                rec.attr.get('batch', ''), rec.attr.get('dom', ''),
                rec.attr.get('outlet', ''), rec.attr.get('src', ''), uc)
        elif kind in ('HV', 'QV'):
            subject = rec.host if rec.host else rec.subject
            value = rec.value
            extra = attrs_extra(rec.attr)
        elif kind in ('CV', 'MV', 'PR', 'SP', 'TN'):
            subject = rec.subject
            value = rec.value
            extra = attrs_extra(rec.attr)
        elif kind == 'PV':
            subject = rec.subject
            value = str(efficiency_bp(rec))
            extra = attrs_extra(rec.attr)
        elif kind == 'ER':
            subject = rec_target_id(rec.subject)
            try:
                n, d = num_ratio(rec.value)
            except BuildError as exc:
                raise BuildError('%s: %s' % (rec.where(), exc))
            value = str(round_ratio_half_even(n * 1000, d))
            extra = attrs_extra(rec.attr)
        elif kind == 'AL':
            subject = rec.subject
            target = rec.attr.get('target', '')
            until_text = rec.attr.get('until', '')
            if not target or not until_text:
                raise BuildError('%s: alias without a target or until time' % rec.where())
            until = parse_time(until_text, None)
            extra = 'target=%s;until=%s' % (target, utc_str(until))
            value = ''
        else:
            subject = rec.subject
            if kind in ('VO', 'RT'):
                subject = rec_target_id(rec.subject)
            value = ''
            extra = attrs_extra(rec.attr)
        when = '' if kind == 'PV' else utc_str(rec.time)
        lines.append('|'.join((kind, rec.id, subject, when, value, extra)))
    return lines


def source_digest(fleet, src, records):
    lines = canonical_lines(fleet, records)
    text = ('\n'.join(lines) + '\n') if lines else ''
    voided = 0
    post_cut = 0
    for rec in records:
        if rec.kind not in ('VO', 'RT') and rec.key in fleet.voided_keys:
            voided += 1
        if rec.time is not None and rec.time >= fleet.freeze:
            post_cut += 1
    return {
        'file': src.name,
        'records': len(src.records),
        'voided': voided,
        'post_cut': post_cut,
        'digest': hashlib.sha256(text.encode('utf-8')).hexdigest(),
    }


def site_registry(fleet):
    sites = {}
    for key in fleet.effective_sp:
        site = key.split(':')[0].strip().lower()
        if site:
            sites.setdefault(site, None)
    for site in sites:
        sites[site] = fleet.site_params(site)
    out = []
    for site in sorted(sites):
        params = sites[site]
        out.append({
            'site': site,
            'cont_pm': params['cont'],
            'derate_pm': params['derate'],
            'volts': params['volts'],
            'tariff_mc': params['tariff'],
            'pue_milli': params['pue'],
            'cap_step_w': params['step'],
            'margin_pm': params['margin'],
            'warn_pm': params['warn'],
            'crit_pm': params['crit'],
            'pool_pm': params['pool'],
            'correction_ms': params['corr'],
        })
    return out


def tenant_registry(fleet):
    tenants = []
    for subject, rec in fleet.effective_tn.items():
        parts = subject.split('@')
        if len(parts) != 2:
            raise BuildError('%s: tenant entitlement without a site' % rec.where())
        tenant = parts[0].strip().lower()
        site = parts[1].strip().lower()
        if 'watts' not in rec.attr:
            raise BuildError('%s: tenant entitlement without watts' % rec.where())
        tenants.append((site, tenant, attr_number_int(rec.attr['watts'])))
    tenants.sort()
    return [{'site': site, 'tenant': tenant, 'entitlement_w': watts}
            for site, tenant, watts in tenants]


# ---------------------------------------------------------------- phase 1 output

def write_text(path, text):
    with open(path, 'w', encoding='utf-8', newline='') as fh:
        fh.write(text)


def csv_text(header, rows):
    lines = [','.join(header)]
    for row in rows:
        cells = []
        for cell in row:
            cell = '' if cell is None else str(cell)
            cells.append(cell)
            if ',' in cell or '\n' in cell:
                raise BuildError('output value holds a separator: %r' % cell)
        lines.append(','.join(cells))
    return '\n'.join(lines) + '\n'


def json_text(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False) + '\n'


def lineage_of(path, label):
    try:
        with open(path, 'rb') as fh:
            blob = fh.read()
    except OSError as exc:
        fail('cannot read %s: %s' % (label, exc))
    return {'sha256': hashlib.sha256(blob).hexdigest(), 'bytes': len(blob),
            'lines': blob.count(b'\n')}


def phase1(data_dir, out_dir):
    fleet = Fleet(data_dir)
    fleet.build()
    data = phase1_data(fleet)

    host_rows = []
    for info in data['host_order']:
        host_rows.append([info.host, info.site, info.rack, info.model, info.psu,
                          info.psu_count, info.tenant, info.priority, info.domain,
                          info.nameplate_w, info.idle_w, info.floor_w,
                          '' if info.ceiling_w is None else info.ceiling_w])
    demand_rows = []
    for info in data['host_order']:
        demand = info.demand
        demand_rows.append([info.host, demand['samples'], demand['mean_w'], demand['p95_w'],
                            demand['peak_w'], demand['energy_wh']])
    circuit_rows = []
    for cid in sorted(data['circuits']):
        circuit = data['circuits'][cid]
        circuit_rows.append([circuit['circuit_id'], circuit['site'], circuit['rack_id'],
                             circuit['feed'], circuit['voltage_v'], circuit['breaker_a'],
                             circuit['usable_w']])
    psu_rows = []
    for model, key, load, eff_bp, _rec in data['psu_rows']:
        psu_rows.append([model, data['psu_rated'][key], load, eff_bp])
    amendment_rows = []
    for when, key, rid, target, field, value in data['amendments_carried']:
        if field == 'breaker_a' and target not in data['circuits']:
            continue
        amendment_rows.append([rid, utc_str(when), target, field, value])

    by_source = {}
    for rec in fleet.records:
        by_source.setdefault(rec.src.name, []).append(rec)
    sources = []
    for src in fleet.sources:
        sources.append(source_digest(fleet, src, by_source.get(src.name, [])))
    registry = {
        'freeze_utc': fleet.freeze_str,
        'window_start_utc': fleet.window_str,
        'sites': site_registry(fleet),
        'tenants': tenant_registry(fleet),
        'sources': sources,
    }

    os.makedirs(out_dir, exist_ok=True)
    write_text(os.path.join(out_dir, 'hosts.csv'),
               csv_text(['host_id', 'site', 'rack_id', 'model', 'psu_model', 'psu_count',
                         'tenant', 'priority', 'cap_domain', 'nameplate_w', 'idle_w',
                         'floor_w', 'cap_ceiling_w'], host_rows))
    write_text(os.path.join(out_dir, 'circuits.csv'),
               csv_text(['circuit_id', 'site', 'rack_id', 'feed', 'voltage_v', 'breaker_a',
                         'usable_w'], circuit_rows))
    write_text(os.path.join(out_dir, 'demand.csv'),
               csv_text(['host_id', 'samples', 'mean_w', 'p95_w', 'peak_w', 'energy_wh'],
                        demand_rows))
    write_text(os.path.join(out_dir, 'psu.csv'),
               csv_text(['psu_model', 'rated_w', 'load_pm', 'eff_bp'], psu_rows))
    write_text(os.path.join(out_dir, 'amendments.csv'),
               csv_text(['amendment_id', 'effective_utc', 'target', 'field', 'value'],
                        amendment_rows))
    write_text(os.path.join(out_dir, 'registry.json'), json_text(registry))
    return 0

# ---------------------------------------------------------------- upstream tables

def read_upstream_csv(directory, label, name, header):
    path = os.path.join(directory, name)
    if not os.path.isfile(path):
        fail('missing input file %s in %s' % (name, label))
    try:
        with open(path, encoding='utf-8', newline='') as fh:
            rows = list(csv.reader(fh))
    except OSError as exc:
        fail('cannot read %s: %s' % (name, exc))
    if not rows or rows[0] != header:
        fail('unexpected header in %s' % name)
    out = []
    for row in rows[1:]:
        if len(row) != len(header):
            fail('malformed row in %s' % name)
        out.append(dict(zip(header, row)))
    return out


def read_upstream_json(directory, label, name):
    path = os.path.join(directory, name)
    if not os.path.isfile(path):
        fail('missing input file %s in %s' % (name, label))
    try:
        with open(path, encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, ValueError) as exc:
        fail('cannot read %s: %s' % (name, exc))
    return None


def want_int(text, where):
    try:
        return int(text)
    except (TypeError, ValueError):
        fail('bad integer %r in %s' % (text, where))


def want_dec(text, places, where):
    """A decimal string with exactly `places` decimals, as a scaled integer."""
    if text is None or text == '':
        return None
    if '.' not in text:
        fail('bad decimal %r in %s' % (text, where))
    whole, frac = text.split('.', 1)
    sign = 1
    digits = whole
    if digits.startswith('-'):
        sign, digits = -1, digits[1:]
    if len(frac) != places or not digits.isdigit() or not frac.isdigit():
        fail('bad decimal %r in %s' % (text, where))
    return sign * (int(digits or '0') * 10 ** places + int(frac))


def ceil_ratio(n, d):
    if d < 0:
        n, d = -n, -d
    return -((-n) // d)


HOSTS_HEADER = ['host_id', 'site', 'rack_id', 'model', 'psu_model', 'psu_count', 'tenant',
                'priority', 'cap_domain', 'nameplate_w', 'idle_w', 'floor_w', 'cap_ceiling_w']
CIRCUITS_HEADER = ['circuit_id', 'site', 'rack_id', 'feed', 'voltage_v', 'breaker_a',
                   'usable_w']
DEMAND_HEADER = ['host_id', 'samples', 'mean_w', 'p95_w', 'peak_w', 'energy_wh']
PSU_HEADER = ['psu_model', 'rated_w', 'load_pm', 'eff_bp']
AMENDMENTS_HEADER = ['amendment_id', 'effective_utc', 'target', 'field', 'value']


class P1(object):
    """The phase-1 tables as phase 2 and phase 3 read them."""

    def __init__(self, directory, label):
        self.directory = directory
        self.label = label
        self.hosts = read_upstream_csv(directory, label, 'hosts.csv', HOSTS_HEADER)
        self.circuits = read_upstream_csv(directory, label, 'circuits.csv', CIRCUITS_HEADER)
        self.demand = read_upstream_csv(directory, label, 'demand.csv', DEMAND_HEADER)
        self.psu = read_upstream_csv(directory, label, 'psu.csv', PSU_HEADER)
        self.amendments = read_upstream_csv(directory, label, 'amendments.csv',
                                            AMENDMENTS_HEADER)
        self.registry = read_upstream_json(directory, label, 'registry.json')
        for key in ('freeze_utc', 'window_start_utc', 'sites', 'tenants', 'sources'):
            if key not in self.registry:
                fail('registry.json without %s' % key)
        self.freeze = self.registry['freeze_utc']
        self.sites = {site['site']: site for site in self.registry['sites']}
        self.tenants = {(t['site'], t['tenant']): t['entitlement_w']
                        for t in self.registry['tenants']}
        self.psu_rated = {}
        self.psu_eff = {}
        for row in self.psu:
            model = row['psu_model']
            self.psu_rated[model] = want_int(row['rated_w'], 'psu.csv')
            self.psu_eff.setdefault(model, {})[want_int(row['load_pm'], 'psu.csv')] = \
                want_int(row['eff_bp'], 'psu.csv')
        self.host_demand = {row['host_id']: row for row in self.demand}
        for row in self.hosts:
            if row['host_id'] not in self.host_demand:
                fail('demand.csv has no row for %s' % row['host_id'])
        for row in self.demand:
            if row['host_id'] not in {h['host_id'] for h in self.hosts}:
                fail('demand.csv row for unknown host %s' % row['host_id'])

    def param(self, site, key):
        if site not in self.sites:
            fail('registry.json has no site %s' % site)
        return self.sites[site][key]

    def load_pm(self, model, count, milli_watts):
        """The load in per mille of a draw over the PSUs, held between 1 and 1000."""
        if model not in self.psu_rated:
            fail('psu.csv has no model %s' % model)
        rated = self.psu_rated[model]
        if count <= 0 or rated <= 0:
            fail('host with no usable PSUs for %s' % model)
        load = round_ratio_half_even(milli_watts, count * rated)
        if load < 1:
            return 1
        if load > 1000:
            return 1000
        return load

    def efficiency(self, model, load):
        table = self.psu_eff.get(model)
        if not table or load not in table:
            fail('psu.csv has no efficiency for %s at load %d' % (model, load))
        return table[load]


# ---------------------------------------------------------------- phase 2

class Phase2(object):
    def __init__(self, p1, directory, label):
        self.p1 = p1
        self.directory = directory
        self.label = label
        self.racks = {}
        self.rack_circuits = {}
        for row in p1.circuits:
            rack = row['rack_id']
            feed = row['feed']
            entry = self.rack_circuits.setdefault(rack, {})
            if feed in entry:
                fail('rack %s has two %s feeds' % (rack, feed))
            entry[feed] = row
            self.racks.setdefault(rack, {'site': row['site'], 'feeds': {}})
            self.racks[rack]['feeds'][feed] = row
        self.host_amendments = {}
        self.circuit_amendments = {}
        for row in p1.amendments:
            target = row['target']
            if any(h['host_id'] == target for h in p1.hosts):
                self.host_amendments.setdefault(target, []).append(row)
            elif any(c['circuit_id'] == target for c in p1.circuits):
                self.circuit_amendments.setdefault(target, []).append(row)
        self.host_rack = {row['host_id']: row['rack_id'] for row in p1.hosts}
        self.circuit_rack = {row['circuit_id']: row['rack_id'] for row in p1.circuits}
        self.host_overcommit = {}
        self.host_request = {}
        self.host_alloc = {}
        self.compute_budgets()
        self.compute_alloc()
        self.compute_energy()
        self.compute_alarms()
        self.compute_pools()

    # -- racks -----------------------------------------------------------

    def compute_budgets(self):
        p1 = self.p1
        self.rack_budget = {}
        self.rack_feed_w = {}
        self.site_racks = {}
        for rack, info in self.racks.items():
            site = info['site']
            step = p1.param(site, 'cap_step_w')
            if step <= 0:
                fail('site %s has a cap step of 0' % site)
            feeds = info['feeds']
            usable = {}
            for feed in ('A', 'B'):
                row = feeds.get(feed)
                usable[feed] = want_int(row['usable_w'], 'circuits.csv') if row else None
            values = [v for v in usable.values() if v is not None]
            if not values:
                fail('rack %s has no usable feed' % rack)
            smaller = min(values)
            budget = round_ratio_down(smaller, step) * step
            self.rack_budget[rack] = budget
            self.rack_feed_w[rack] = usable
            self.site_racks.setdefault(site, []).append(rack)
        for site in self.site_racks:
            self.site_racks[site].sort()

    def rack_pending(self, rack):
        count = 0
        for row in self.p1.amendments:
            target = row['target']
            if target in self.circuit_amendments:
                if self.circuit_rack.get(target) == rack:
                    count += 1
            elif self.host_rack.get(target) == rack:
                count += 1
        return count

    # -- allocations -----------------------------------------------------

    def compute_alloc(self):
        p1 = self.p1
        self.host_alloc = {}
        self.host_request = {}
        remaining = dict(self.rack_budget)
        for host in p1.hosts:
            hid = host['host_id']
            site = host['site']
            rack = host['rack_id']
            step = p1.param(site, 'cap_step_w')
            margin = p1.param(site, 'margin_pm')
            demand = p1.host_demand[hid]
            samples = want_int(demand['samples'], 'demand.csv')
            psu_count = want_int(host['psu_count'], 'hosts.csv')
            rated = p1.psu_rated.get(host['psu_model'])
            if rated is None:
                fail('psu.csv has no model %s' % host['psu_model'])
            ceiling = want_int(host['nameplate_w'], 'hosts.csv')
            limit = rated * psu_count
            if limit < ceiling:
                ceiling = limit
            cap = host['cap_ceiling_w']
            if cap != '':
                cap_w = want_int(cap, 'hosts.csv')
                if cap_w < ceiling:
                    ceiling = cap_w
            floor_w = want_int(host['floor_w'], 'hosts.csv')
            if samples > 0:
                p95 = want_dec(demand['p95_w'], 1, 'demand.csv')
                base = ceil_ratio(p95 * (1000 + margin), 10000 * step) * step
            else:
                base = want_int(host['nameplate_w'], 'hosts.csv')
            if base < floor_w:
                base = floor_w
            if ceiling is not None and base > ceiling:
                base = ceiling
            request = base
            left = remaining.get(rack, 0)
            alloc = request if request < left else left
            if alloc < 0:
                alloc = 0
            overcommit = 0
            if alloc < floor_w:
                alloc = floor_w
                overcommit = 1
            remaining[rack] = left - alloc
            self.host_request[hid] = request
            self.host_alloc[hid] = alloc
            self.host_overcommit[hid] = overcommit
        self.remaining = remaining

    def host_amended(self, hid):
        return 1 if self.host_amendments.get(hid) else 0

    # -- site energy -----------------------------------------------------

    def compute_energy(self):
        p1 = self.p1
        self.site_energy = {}
        for site in sorted({row['site'] for row in p1.hosts} |
                           {row['site'] for row in p1.circuits}):
            hosts = [row for row in p1.hosts if row['site'] == site]
            it_cwh = 0
            dc_wh = 0
            null_hosts = 0
            zero_hosts = 0
            for host in hosts:
                demand = p1.host_demand[host['host_id']]
                samples = want_int(demand['samples'], 'demand.csv')
                if samples <= 0:
                    null_hosts += 1
                    continue
                peak = want_dec(demand['peak_w'], 1, 'demand.csv')
                if peak == 0:
                    zero_hosts += 1
                cwh = want_dec(demand['energy_wh'], 2, 'demand.csv')
                it_cwh += cwh
                mean = want_dec(demand['mean_w'], 1, 'demand.csv')
                count = want_int(host['psu_count'], 'hosts.csv')
                load = p1.load_pm(host['psu_model'], count, mean * 100)
                eff = p1.efficiency(host['psu_model'], load)
                dc_wh += round_ratio_half_even(cwh * eff, 1000000)
            pue = p1.param(site, 'pue_milli')
            tariff = p1.param(site, 'tariff_mc')
            it_scaled = scaled_round(it_cwh, 100000, 2)
            facility_scaled = scaled_round(it_scaled * pue, 100000, 2)
            cost = round_ratio_half_even(facility_scaled * tariff, 100000)
            capacity_w = 0
            for rack in self.site_racks.get(site, []):
                values = [v for v in self.rack_feed_w[rack].values() if v is not None]
                capacity_w += min(values)
            pending = sum(len(self.host_amendments.get(h['host_id'], [])) for h in hosts)
            for rack in self.site_racks.get(site, []):
                pending += sum(len(self.circuit_amendments.get(c['circuit_id'], []))
                               for c in p1.circuits if c['rack_id'] == rack)
            self.site_energy[site] = {
                'hosts': len(hosts), 'null_hosts': null_hosts, 'zero_hosts': zero_hosts,
                'it_scaled': it_scaled, 'dc_wh': dc_wh, 'facility_scaled': facility_scaled,
                'cost_cents': cost, 'capacity_w': capacity_w, 'pending': pending,
            }

    # -- circuit alarms --------------------------------------------------

    def compute_alarms(self):
        p1 = self.p1
        self.circuit_alarms = {}
        for row in p1.circuits:
            cid = row['circuit_id']
            rack = row['rack_id']
            site = row['site']
            feed = row['feed']
            volts = want_int(row['voltage_v'], 'circuits.csv')
            breaker = want_int(row['breaker_a'], 'circuits.csv')
            cont = p1.param(site, 'cont_pm')
            derate = p1.param(site, 'derate_pm')
            warn_pm = p1.param(site, 'warn_pm')
            crit_pm = p1.param(site, 'crit_pm')
            hosts = [h for h in p1.hosts if h['rack_id'] == rack]
            load = 0
            failover = 0
            psu_over = 0
            for host in hosts:
                demand = p1.host_demand[host['host_id']]
                count = want_int(host['psu_count'], 'hosts.csv')
                mean = want_dec(demand['mean_w'], 1, 'demand.csv')
                peak = want_dec(demand['peak_w'], 1, 'demand.csv')
                mean = 0 if mean is None else mean
                peak = 0 if peak is None else peak
                if count == 1:
                    load += 2 * mean
                elif count == 2:
                    load += mean
                if count == 2:
                    rated = p1.psu_rated.get(host['psu_model'])
                    if rated is not None and peak > rated * 10:
                        psu_over += 1
                if feed == 'A':
                    failover += peak
                elif count == 2:
                    failover += peak
            expected = round_ratio_half_even(load * 100, 20 * volts)
            failover_a = round_ratio_half_even(failover * 100, 10 * volts)
            warn_a = round_ratio_down(breaker * cont * derate * warn_pm, 10 ** 8)
            crit_a = round_ratio_down(breaker * cont * derate * crit_pm, 10 ** 8)
            if failover_a >= crit_a * 10:
                state = 'crit'
            elif failover_a >= warn_a * 10:
                state = 'warn'
            else:
                state = 'ok'
            self.circuit_alarms[cid] = {
                'circuit_id': cid, 'rack_id': rack, 'feed': feed, 'voltage_v': volts,
                'expected_a': expected, 'failover_a': failover_a, 'warn_a': warn_a,
                'crit_a': crit_a, 'state': state, 'psu_over': psu_over,
                'pending': len(self.circuit_amendments.get(cid, [])),
            }

    # -- tenant pools ----------------------------------------------------

    def compute_pools(self):
        p1 = self.p1
        pairs = set(self.tenant_pairs())
        pools = {}
        for site in {p[0] for p in pairs}:
            budget = 0
            for rack in self.site_racks.get(site, []):
                budget += self.rack_budget[rack]
            pools[site] = round_ratio_down(budget * p1.param(site, 'pool_pm'), 1000)
        self.tenant_rows = []
        left = dict(pools)
        for site, tenant in sorted(pairs):
            hosts = [h for h in p1.hosts if h['site'] == site and h['tenant'] == tenant]
            request = sum(self.host_alloc[h['host_id']] for h in hosts)
            entitlement = p1.tenants.get((site, tenant), 0)
            pool = left.get(site, 0)
            granted = min(request, entitlement, pool)
            if granted < 0:
                granted = 0
            left[site] = pool - granted
            pending = sum(len(self.host_amendments.get(h['host_id'], [])) for h in hosts)
            self.tenant_rows.append({
                'site': site, 'tenant': tenant, 'hosts': len(hosts), 'request_w': request,
                'entitlement_w': entitlement, 'granted_w': granted,
                'cut_w': request - granted, 'pending': pending,
            })
        self.site_pool = pools

    def tenant_pairs(self):
        p1 = self.p1
        pairs = set(p1.tenants)
        for host in p1.hosts:
            pairs.add((host['site'], host['tenant']))
        return pairs


def phase2(p1_dir, out_dir):
    if not os.path.isdir(p1_dir):
        fail('input directory not found: %s' % p1_dir)
    p1 = P1(p1_dir, 'the phase-1 directory')
    plan = Phase2(p1, p1_dir, 'the phase-1 directory')

    rack_rows = []
    for rack in sorted(plan.racks):
        info = plan.racks[rack]
        hosts = [h for h in p1.hosts if h['rack_id'] == rack]
        nameplate = sum(want_int(h['nameplate_w'], 'hosts.csv') for h in hosts)
        p95_tenths = 0
        psu_n1_ok = 0
        for host in hosts:
            demand = p1.host_demand[host['host_id']]
            if want_int(demand['samples'], 'demand.csv') > 0:
                p95_tenths += want_dec(demand['p95_w'], 1, 'demand.csv')
                count = want_int(host['psu_count'], 'hosts.csv')
                rated = p1.psu_rated.get(host['psu_model'])
                p95 = want_dec(demand['p95_w'], 1, 'demand.csv')
                if count == 2 and rated is not None and p95 <= rated * 10:
                    psu_n1_ok += 1
        feeds = info['feeds']
        row_a = feeds.get('A')
        row_b = feeds.get('B')
        budget = plan.rack_budget[rack]
        headroom = budget - round_ratio_half_even(p95_tenths, 10)
        rack_rows.append([
            rack, info['site'], len(hosts),
            row_a['usable_w'] if row_a else '',
            row_b['usable_w'] if row_b else '',
            budget, nameplate, round_ratio_half_even(p95_tenths, 10), headroom,
            psu_n1_ok, plan.rack_pending(rack),
        ])

    host_rows = []
    for host in p1.hosts:
        hid = host['host_id']
        request = plan.host_request[hid]
        alloc = plan.host_alloc[hid]
        host_rows.append([hid, host['rack_id'], request, alloc, request - alloc,
                          plan.host_overcommit[hid], plan.host_amended(hid)])

    site_rows = []
    for site in sorted(plan.site_energy):
        energy = plan.site_energy[site]
        site_rows.append([
            site, energy['hosts'], energy['null_hosts'], energy['zero_hosts'],
            dec_str(energy['it_scaled'], 2), dec_str(round_ratio_half_even(energy['dc_wh'], 10), 2),
            dec_str(energy['facility_scaled'], 2), energy['cost_cents'],
            dec_str(scaled_round(energy['capacity_w'], 1000, 2), 2), energy['pending'],
        ])

    alarm_rows = []
    for cid in sorted(plan.circuit_alarms):
        alarm = plan.circuit_alarms[cid]
        alarm_rows.append([
            cid, alarm['rack_id'], alarm['feed'], alarm['voltage_v'],
            dec_str(alarm['expected_a'], 2), dec_str(alarm['failover_a'], 2),
            dec_str(alarm['warn_a'], 1), dec_str(alarm['crit_a'], 1), alarm['state'],
            alarm['psu_over'], alarm['pending'],
        ])

    pool_rows = []
    for row in plan.tenant_rows:
        pool_rows.append([row['site'], row['tenant'], row['hosts'], row['request_w'],
                          row['entitlement_w'], row['granted_w'], row['cut_w'], row['pending']])

    inputs = {}
    for name in P1_NAMES:
        inputs['p1/' + name] = lineage_of(os.path.join(p1_dir, name), 'the phase-1 directory')
    sites = []
    for site in sorted(plan.site_energy):
        hosts = [h for h in p1.hosts if h['site'] == site]
        sites.append({
            'site': site,
            'hosts': len(hosts),
            'budget_w': sum(plan.rack_budget[r] for r in plan.site_racks.get(site, [])),
            'request_w': sum(plan.host_request[h['host_id']] for h in hosts),
            'alloc_w': sum(plan.host_alloc[h['host_id']] for h in hosts),
            'pending': plan.site_energy[site]['pending'],
        })
    summary = {'freeze_utc': p1.freeze, 'inputs': inputs, 'sites': sites}

    os.makedirs(out_dir, exist_ok=True)
    write_text(os.path.join(out_dir, 'rack_budget.csv'),
               csv_text(['rack_id', 'site', 'hosts', 'feed_a_w', 'feed_b_w', 'budget_w',
                         'nameplate_w', 'p95_w', 'headroom_w', 'psu_n1_ok', 'pending'],
                        rack_rows))
    write_text(os.path.join(out_dir, 'host_alloc.csv'),
               csv_text(['host_id', 'rack_id', 'request_w', 'alloc_w', 'short_w',
                         'overcommit', 'amended'], host_rows))
    write_text(os.path.join(out_dir, 'site_energy.csv'),
               csv_text(['site', 'hosts', 'null_hosts', 'zero_hosts', 'it_kwh', 'dc_kwh',
                         'facility_kwh', 'cost_cents', 'capacity_kw', 'pending'], site_rows))
    write_text(os.path.join(out_dir, 'circuit_alarms.csv'),
               csv_text(['circuit_id', 'rack_id', 'feed', 'voltage_v', 'expected_a',
                         'failover_a', 'warn_a', 'crit_a', 'state', 'psu_over', 'pending'],
                        alarm_rows))
    write_text(os.path.join(out_dir, 'tenant_pool.csv'),
               csv_text(['site', 'tenant', 'hosts', 'request_w', 'entitlement_w', 'granted_w',
                         'cut_w', 'pending'], pool_rows))
    write_text(os.path.join(out_dir, 'fleet_summary.json'), json_text(summary))
    return 0

# ---------------------------------------------------------------- phase 3

RACK_HEADER = ['rack_id', 'site', 'hosts', 'feed_a_w', 'feed_b_w', 'budget_w', 'nameplate_w',
               'p95_w', 'headroom_w', 'psu_n1_ok', 'pending']
ALLOC_HEADER = ['host_id', 'rack_id', 'request_w', 'alloc_w', 'short_w', 'overcommit',
                'amended']
ENERGY_HEADER = ['site', 'hosts', 'null_hosts', 'zero_hosts', 'it_kwh', 'dc_kwh',
                 'facility_kwh', 'cost_cents', 'capacity_kw', 'pending']
ALARM_HEADER = ['circuit_id', 'rack_id', 'feed', 'voltage_v', 'expected_a', 'failover_a',
                'warn_a', 'crit_a', 'state', 'psu_over', 'pending']
POOL_HEADER = ['site', 'tenant', 'hosts', 'request_w', 'entitlement_w', 'granted_w', 'cut_w',
               'pending']
P2_LOOKUP = {
    'rack_budget.csv': RACK_HEADER,
    'host_alloc.csv': ALLOC_HEADER,
    'site_energy.csv': ENERGY_HEADER,
    'circuit_alarms.csv': ALARM_HEADER,
    'tenant_pool.csv': POOL_HEADER,
}


class P2(object):
    def __init__(self, directory, label):
        self.directory = directory
        self.label = label
        self.tables = {}
        for name, header in P2_LOOKUP.items():
            self.tables[name] = read_upstream_csv(directory, label, name, header)
        self.summary = read_upstream_json(directory, label, 'fleet_summary.json')
        for key in ('freeze_utc', 'inputs', 'sites'):
            if key not in self.summary:
                fail('fleet_summary.json without %s' % key)
        self.rack = {row['rack_id']: row for row in self.tables['rack_budget.csv']}
        self.alloc = {row['host_id']: row for row in self.tables['host_alloc.csv']}
        self.energy = {row['site']: row for row in self.tables['site_energy.csv']}
        self.alarm = {row['circuit_id']: row for row in self.tables['circuit_alarms.csv']}
        self.pool = {(row['site'], row['tenant']): row for row in self.tables['tenant_pool.csv']}
        self.site_alloc = {row['site']: row for row in self.summary['sites']}


def phase3(p1_dir, p2_dir, out_dir):
    if not os.path.isdir(p1_dir):
        fail('input directory not found: %s' % p1_dir)
    if not os.path.isdir(p2_dir):
        fail('input directory not found: %s' % p2_dir)
    p1 = P1(p1_dir, 'the phase-1 directory')
    p2 = P2(p2_dir, 'the phase-2 directory')

    circuits = {row['circuit_id']: row for row in p1.circuits}
    rack_circuits = {}
    for row in p1.circuits:
        rack_circuits.setdefault(row['rack_id'], []).append(row)

    circuit_breaker = {cid: want_int(row['breaker_a'], 'circuits.csv')
                       for cid, row in circuits.items()}
    caps = {}
    caps_order = []
    amendments_by_target = {}
    for row in p1.amendments:
        amendments_by_target.setdefault(row['target'], []).append(row)
    host_site = {row['host_id']: row['site'] for row in p1.hosts}

    for host in p1.hosts:
        hid = host['host_id']
        site = host['site']
        step = p1.param(site, 'cap_step_w')
        alloc_row = p2.alloc.get(hid)
        if alloc_row is None:
            fail('host_alloc.csv has no row for %s' % hid)
        alloc = want_int(alloc_row['alloc_w'], 'host_alloc.csv')
        pool_row = p2.pool.get((site, host['tenant']))
        if pool_row is None:
            fail('tenant_pool.csv has no row for %s at %s' % (host['tenant'], site))
        cut = want_int(pool_row['cut_w'], 'tenant_pool.csv')
        request_row = want_int(pool_row['request_w'], 'tenant_pool.csv')
        cap = alloc
        if cut > 0:
            cap = round_ratio_down(alloc * want_int(pool_row['granted_w'], 'tenant_pool.csv'),
                                   request_row) if request_row else 0
        floor_w = want_int(host['floor_w'], 'hosts.csv')
        priority = host['priority']
        domain = host['cap_domain']
        count = want_int(host['psu_count'], 'hosts.csv')
        model = host['psu_model']
        for row in amendments_by_target.get(hid, []):
            field = row['field']
            value = want_int(row['value'], 'amendments.csv') if field != 'priority' \
                else row['value']
            if field == 'cap_ceiling_w':
                if value < cap:
                    cap = value
            elif field == 'floor_w':
                floor_w = value
            elif field == 'priority':
                priority = value
        if step > 0:
            cap = round_ratio_down(cap, step) * step
        if cap < floor_w:
            cap = floor_w
        native = cap
        if domain == 'DC':
            load = p1.load_pm(model, count, cap * 1000)
            native = round_ratio_half_even(cap * p1.efficiency(model, load), 10000)
        demand = p1.host_demand[hid]
        samples = want_int(demand['samples'], 'demand.csv')
        rack = host['rack_id']
        rack_row = p2.rack.get(rack)
        if rack_row is None:
            fail('rack_budget.csv has no row for %s' % rack)
        headroom = want_int(rack_row['headroom_w'], 'rack_budget.csv')
        if samples <= 0:
            throttle = 'static'
        elif headroom < 0:
            throttle = 'aggressive'
        elif priority == 'gold':
            throttle = 'protect'
        elif priority == 'silver':
            throttle = 'standard'
        else:
            throttle = 'aggressive'
        correction = p1.param(site, 'correction_ms')
        for row in rack_circuits.get(rack, []):
            alarm = p2.alarm.get(row['circuit_id'])
            if alarm is not None and alarm['state'] != 'ok':
                correction = correction * 2
                break
        site_alloc = p2.site_alloc.get(site)
        site_alloc_w = want_int(site_alloc['alloc_w'], 'fleet_summary.json') if site_alloc else 0
        share = 0 if site_alloc_w == 0 else round_ratio_half_even(cap * 1000, site_alloc_w)
        breakers = [want_int(row['breaker_a'], 'circuits.csv')
                    for row in rack_circuits.get(rack, [])]
        feed_breaker = min(breakers) if breakers else 0
        caps[hid] = {
            'host_id': hid, 'cap_w': cap, 'domain': domain, 'native_cap_w': native,
            'correction_ms': correction, 'throttle': throttle, 'site_share_pm': share,
            'feed_breaker_a': feed_breaker, 'psu_model': model, 'psu_count': count,
        }
        caps_order.append(hid)

    # -- pdu alarms -----------------------------------------------------
    pdu_circuits = []
    pdu_state = {}
    for cid in sorted(circuits):
        row = circuits[cid]
        site = row['site']
        rack = row['rack_id']
        feed = row['feed']
        volts = want_int(row['voltage_v'], 'circuits.csv')
        alarm = p2.alarm.get(cid)
        if alarm is None:
            fail('circuit_alarms.csv has no row for %s' % cid)
        breaker = circuit_breaker[cid]
        changed = False
        for amendment in amendments_by_target.get(cid, []):
            if amendment['field'] == 'breaker_a':
                breaker = want_int(amendment['value'], 'amendments.csv')
                changed = True
        if changed:
            cont = p1.param(site, 'cont_pm')
            derate = p1.param(site, 'derate_pm')
            warn_a = round_ratio_down(breaker * cont * derate * p1.param(site, 'warn_pm'),
                                      10 ** 8)
            crit_a = round_ratio_down(breaker * cont * derate * p1.param(site, 'crit_pm'),
                                      10 ** 8)
        else:
            warn_a = want_dec(alarm['warn_a'], 1, 'circuit_alarms.csv')
            crit_a = want_dec(alarm['crit_a'], 1, 'circuit_alarms.csv')
        failover = want_dec(alarm['failover_a'], 2, 'circuit_alarms.csv')
        if failover >= crit_a * 10:
            state = 'crit'
        elif failover >= warn_a * 10:
            state = 'warn'
        else:
            state = 'ok'
        halves = 0
        for host in p1.hosts:
            if host['rack_id'] != rack:
                continue
            alloc = want_int(p2.alloc[host['host_id']]['alloc_w'], 'host_alloc.csv')
            count = want_int(host['psu_count'], 'hosts.csv')
            if feed == 'A':
                halves += alloc * 2 if count == 1 else (alloc if count == 2 else 0)
            elif count == 2:
                halves += alloc
        alloc_a = round_ratio_half_even(halves * 100, 2 * volts)
        pdu_state[cid] = state
        pdu_circuits.append({
            'circuit_id': cid, 'breaker_a': breaker, 'warn_a': dec_str(warn_a, 1),
            'crit_a': dec_str(crit_a, 1), 'expected_a': alarm['expected_a'],
            'alloc_a': dec_str(alloc_a, 2), 'state': state,
            'failover_a': dec_str(failover, 2), 'crit_a_scaled': crit_a,
        })

    # -- chargeback -------------------------------------------------------
    site_cost = {site: want_int(row['cost_cents'], 'site_energy.csv')
                 for site, row in p2.energy.items()}
    chargeback = []
    for site in sorted({row['site'] for row in p1.hosts}):
        hosts = [h for h in p1.hosts if h['site'] == site]
        pairs = sorted({h['tenant'] for h in hosts})
        energies = {}
        for tenant in pairs:
            total = 0
            for host in hosts:
                if host['tenant'] != tenant:
                    continue
                demand = p1.host_demand[host['host_id']]
                if want_int(demand['samples'], 'demand.csv') > 0:
                    total += want_dec(demand['energy_wh'], 2, 'demand.csv')
            energies[tenant] = total
        site_total = sum(energies.values())
        cost = site_cost.get(site, 0)
        shares = []
        for tenant in pairs:
            energy = energies[tenant]
            ppm = 0 if site_total == 0 else round_ratio_half_even(energy * 1000000,
                                                                  site_total)
            exact = (energy * cost, site_total)
            shares.append({'site': site, 'tenant': tenant, 'energy': energy,
                           'share_ppm': ppm, 'exact': exact})
        if site_total > 0:
            floors = [round_ratio_down(s['exact'][0], site_total) if cost else 0
                      for s in shares]
        else:
            floors = [0 for _s in shares]
        left = cost - sum(floors)
        order = sorted(range(len(shares)),
                       key=lambda i: (-((shares[i]['exact'][0] - floors[i] * site_total)),
                                      shares[i]['tenant']))
        give = [0] * len(shares)
        for i in order[:left]:
            give[i] = 1
        for i, s in enumerate(shares):
            chargeback.append({
                'site': s['site'], 'tenant': s['tenant'],
                'energy_wh': dec_str(s['energy'], 2), 'share_ppm': s['share_ppm'],
                'cost_cents': floors[i] + give[i],
            })

    # -- exceptions -------------------------------------------------------
    exceptions = []
    for hid in caps_order:
        cap = caps[hid]['cap_w']
        demand = p1.host_demand[hid]
        peak = want_dec(demand['peak_w'], 1, 'demand.csv')
        if peak is not None and cap * 10 < peak:
            exceptions.append({'type': 'cap_below_peak', 'id': hid,
                               'detail': 'cap=%d;peak=%s' % (cap, demand['peak_w'])})
    for hid in caps_order:
        row = p2.alloc[hid]
        if want_int(row['overcommit'], 'host_alloc.csv') == 1:
            exceptions.append({'type': 'overcommit', 'id': hid,
                               'detail': 'alloc=%s;request=%s' % (row['alloc_w'],
                                                                 row['request_w'])})
    for rack in sorted(p2.rack):
        row = p2.rack[rack]
        if want_int(row['headroom_w'], 'rack_budget.csv') < 0:
            exceptions.append({'type': 'rack_over_budget', 'id': rack,
                               'detail': 'headroom=%s' % row['headroom_w']})
    for circuit in pdu_circuits:
        if circuit['state'] == 'crit':
            exceptions.append({'type': 'circuit_crit', 'id': circuit['circuit_id'],
                               'detail': 'failover=%s;crit=%s' % (circuit['failover_a'],
                                                                  circuit['crit_a'])})
    for (site, tenant) in sorted(p2.pool):
        row = p2.pool[(site, tenant)]
        if want_int(row['cut_w'], 'tenant_pool.csv') > 0:
            exceptions.append({'type': 'tenant_cut', 'id': '%s@%s' % (tenant, site),
                               'detail': 'cut=%s' % row['cut_w']})
    exceptions.sort(key=lambda item: (item['type'], item['id']))

    # -- capacity ---------------------------------------------------------
    capacity = []
    for site in sorted({row['site'] for row in p1.hosts} | set(p2.energy)):
        rack_free = {}
        for rack, row in p2.rack.items():
            if row['site'] != site:
                continue
            used = sum(caps[h['host_id']]['cap_w'] for h in p1.hosts
                       if h['rack_id'] == rack)
            rack_free[rack] = want_int(row['budget_w'], 'rack_budget.csv') - used
        free_w = sum(rack_free.values())
        racks_full = sum(1 for free in rack_free.values() if free < 500)
        pool = 0
        for rack, row in p2.rack.items():
            if row['site'] == site:
                pool += want_int(row['budget_w'], 'rack_budget.csv')
        pool = round_ratio_down(pool * p1.param(site, 'pool_pm'), 1000)
        for row in p2.tables['tenant_pool.csv']:
            if row['site'] == site:
                pool -= want_int(row['granted_w'], 'tenant_pool.csv')
        slots = 0
        for rack in sorted(rack_free):
            take = rack_free[rack]
            if take < 0:
                take = 0
            if pool < 0:
                pool = 0
            take = take if take < pool else pool
            rack_slots = round_ratio_down(take, 500)
            slots += rack_slots
            pool -= rack_slots * 500
        capacity.append({'site': site, 'free_w': free_w, 'slots_500w': slots,
                         'racks_full': racks_full})

    # -- release ----------------------------------------------------------
    applied = []
    values = {}
    for host in p1.hosts:
        values[('host', host['host_id'], 'floor_w')] = want_int(host['floor_w'],
                                                                'hosts.csv')
        values[('host', host['host_id'], 'priority')] = host['priority']
        ceiling = host['cap_ceiling_w']
        values[('host', host['host_id'], 'cap_ceiling_w')] = \
            want_int(ceiling, 'hosts.csv') if ceiling != '' else None
    for cid, row in circuits.items():
        values[('circuit', cid, 'breaker_a')] = want_int(row['breaker_a'], 'circuits.csv')
    for row in p1.amendments:
        target = row['target']
        field = row['field']
        kind = 'circuit' if target in circuits else 'host'
        key = (kind, target, field)
        before = values.get(key)
        after = row['value'] if field == 'priority' else str(want_int(row['value'],
                                                                     'amendments.csv'))
        values[key] = after
        applied.append({
            'amendment_id': row['amendment_id'], 'target': target, 'field': field,
            'before': None if before is None else str(before), 'after': after,
        })
    totals = {
        'hosts': len(caps_order),
        'cap_w': sum(caps[hid]['cap_w'] for hid in caps_order),
        'native_cap_w': sum(caps[hid]['native_cap_w'] for hid in caps_order),
    }

    lineage = {}
    for name in P1_NAMES:
        lineage['p1/' + name] = lineage_of(os.path.join(p1_dir, name),
                                           'the phase-1 directory')
    for name in P2_NAMES:
        lineage['p2/' + name] = lineage_of(os.path.join(p2_dir, name),
                                           'the phase-2 directory')

    # -- write ------------------------------------------------------------
    os.makedirs(out_dir, exist_ok=True)
    lines = []
    for hid in caps_order:
        cap = caps[hid]
        lines.append('[%s]' % hid)
        lines.append('cap_w = %d' % cap['cap_w'])
        lines.append('domain = %s' % cap['domain'])
        lines.append('native_cap_w = %d' % cap['native_cap_w'])
        lines.append('correction_ms = %d' % cap['correction_ms'])
        lines.append('throttle = %s' % cap['throttle'])
        lines.append('site_share_pm = %d' % cap['site_share_pm'])
        lines.append('feed_breaker_a = %d' % cap['feed_breaker_a'])
        site = host_site[hid]
        energy = p2.energy.get(site)
        if energy is None:
            fail('site_energy.csv has no row for %s' % site)
        it = want_dec(energy['it_kwh'], 2, 'site_energy.csv')
        facility = want_dec(energy['facility_kwh'], 2, 'site_energy.csv')
        if it == 0:
            pue = p1.param(site, 'pue_milli')
        else:
            pue = round_ratio_half_even(facility * 1000, it)
        lines.append('pue_milli = %d' % pue)
        lines.append('')
    lines.append('[lineage]')
    for key in P1_KEYS + P2_KEYS:
        info = lineage[key]
        lines.append('%s = %s:%d:%d' % (key, info['sha256'], info['bytes'], info['lines']))
    write_text(os.path.join(out_dir, 'bmc_caps.ini'), '\n'.join(lines) + '\n')

    write_text(os.path.join(out_dir, 'pdu_alarms.json'), json_text({
        'circuits': [{'circuit_id': c['circuit_id'], 'breaker_a': c['breaker_a'],
                      'warn_a': c['warn_a'], 'crit_a': c['crit_a'],
                      'expected_a': c['expected_a'], 'alloc_a': c['alloc_a'],
                      'state': c['state']} for c in pdu_circuits],
        'lineage': lineage,
    }))
    write_text(os.path.join(out_dir, 'chargeback.json'), json_text({
        'tenants': [{'site': t['site'], 'tenant': t['tenant'], 'energy_wh': t['energy_wh'],
                     'share_ppm': t['share_ppm'], 'cost_cents': t['cost_cents']}
                    for t in chargeback],
        'lineage': lineage,
    }))
    write_text(os.path.join(out_dir, 'exceptions.json'), json_text({
        'exceptions': exceptions, 'lineage': lineage}))
    write_text(os.path.join(out_dir, 'capacity.json'), json_text({
        'sites': capacity, 'lineage': lineage}))
    write_text(os.path.join(out_dir, 'release.json'), json_text({
        'freeze_utc': p1.freeze, 'applied': applied, 'totals': totals,
        'lineage': lineage}))
    return 0


# ---------------------------------------------------------------- entry point

USAGE = """usage: build.py phase1 <DATA_DIR> <P1_DIR>
       build.py phase2 <P1_DIR> <P2_DIR>
       build.py phase3 <P1_DIR> <P2_DIR> <P3_DIR>"""


def main(argv):
    if len(argv) < 2:
        sys.stderr.write('%s: error: %s\n' % (PROG, USAGE.replace('\n', ' ')))
        return 2
    stage = argv[1]
    args = argv[2:]
    if stage == 'phase1' and len(args) == 2:
        data_dir, out_dir = args
    elif stage == 'phase2' and len(args) == 2:
        data_dir, out_dir = args
    elif stage == 'phase3' and len(args) == 3:
        data_dir, out_dir = args[0], args[2]
        other = args[1]
    else:
        sys.stderr.write('%s: error: %s\n' % (PROG, USAGE.replace('\n', ' ')))
        return 2
    try:
        if stage == 'phase1':
            return phase1(data_dir, out_dir)
        if stage == 'phase2':
            return phase2(data_dir, out_dir)
        return phase3(data_dir, other, out_dir)
    except BuildError as exc:
        fail(str(exc))
    except OSError as exc:
        fail(str(exc))
    return 3


if __name__ == '__main__':
    sys.exit(main(sys.argv))
