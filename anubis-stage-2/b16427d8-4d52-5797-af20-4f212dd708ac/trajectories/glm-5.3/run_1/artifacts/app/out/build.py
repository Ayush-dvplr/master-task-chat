#!/usr/bin/env python3
"""Aurelis Labs preference corpus release builder.

Usage: python3 build.py <DATA_DIR> <OUT_DIR>

Reads the release exports in DATA_DIR, applies the release policy published in
corpus_policy.md together with the companion contract documents, and writes the
release artifacts into OUT_DIR. Only the standard library and the packages
shipped in the image are used.
"""

import collections
import csv
import json
import os
import re
import sqlite3
import sys
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from zipfile import ZipFile

UTC = timezone.utc
EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
SERIAL_ZERO = datetime(1899, 12, 30, tzinfo=UTC)

# -------------------------------------------------------------- identifiers --

CYRILLIC = {
    '\u0410': 'A', '\u0412': 'B', '\u0421': 'C', '\u0415': 'E',
    '\u041e': 'O', '\u0420': 'P',
    '\u0430': 'A', '\u0432': 'B', '\u0441': 'C', '\u0435': 'E',
    '\u043e': 'O', '\u0440': 'P',
}
ID_RE = re.compile(r'^([A-Z]+)-(\d+)$')
SPACES = ' \u00a0\u3000\t\r\n'
STRIP = '"' + SPACES
SENTINELS = ('-1', 'n/a')


def canon(value, width):
    """Canonicalise an identifier variant to its registered form."""
    if value is None:
        return None
    out = []
    for ch in str(value):
        o = ord(ch)
        if ch in CYRILLIC:
            out.append(CYRILLIC[ch])
        elif 0xFF10 <= o <= 0xFF19:
            out.append(chr(o - 0xFEE0))
        elif 0xFF21 <= o <= 0xFF3A:
            out.append(chr(o - 0x20))
        elif 0xFF41 <= o <= 0xFF5A:
            out.append(chr(o - 0x20))
        elif ch in SPACES:
            continue
        else:
            out.append(ch.upper())
    text = ''.join(out)
    m = ID_RE.match(text)
    if m:
        return m.group(1) + '-' + m.group(2).zfill(width)
    return text


def text(value):
    """Normalise a text cell: trimmed, folded to lower case."""
    if value is None:
        return None
    t = str(value).strip(STRIP)
    return t.lower() if t else None


def locale_code(value):
    """Resolve a locale code to its registered form (xx_XX)."""
    t = text(value)
    if t is None:
        return None
    m = re.match(r'^([a-z]{2})[-_]([a-z]{2})$', t)
    if m:
        return m.group(1) + '_' + m.group(2).upper()
    return t


# ------------------------------------------------------------------- values --

GROUP_SEP = re.compile(r'(?<=\d)[.,\u00a0 ](?=\d{3}(\D|$))')


def parse_number(value, scaled=False):
    """Read a value cell: thousands grouping, excess precision, scale."""
    if value is None:
        return None
    s = str(value).strip(STRIP)
    if s == '' or s.lower() in SENTINELS:
        return None
    if re.fullmatch(r'-?\d+', s):
        num = int(s)
    else:
        t = s
        prev = None
        while prev != t:
            prev = t
            t = GROUP_SEP.sub(lambda m: m.group(1) or '', t)
        if re.fullmatch(r'-?\d+', t):
            num = int(t)
        elif re.fullmatch(r'-?\d+\.\d{2}', t):
            num = _round_half_even(t)
        else:
            try:
                num = float(t)
            except ValueError:
                return None
    if scaled:
        scaled_value = Fraction(num, 1000)
        return int(scaled_value) if scaled_value.denominator == 1 else scaled_value
    return num


def as_int(value):
    """A count written as an integer whenever it is whole."""
    if isinstance(value, Fraction):
        return int(value) if value.denominator == 1 else value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value if value is not None else 0


def _round_half_even(s):
    """Round a string with exactly two decimal places half to even."""
    neg = s.startswith('-')
    body = s[1:] if neg else s
    whole, frac = body.split('.')
    units = int(whole)
    rest = int(frac)
    if rest > 50 or (rest == 50 and units % 2 == 1):
        units += 1
    return -units if neg else units


def _serial_seconds(s):
    """Serial day count read to the nearest second, half to even."""
    whole, _, frac = s.partition('.')
    days = int(whole)
    if not frac:
        return days * 86400
    frac = frac.ljust(6, '0')[:6]
    total = int(frac) * 86400
    carry, rem = divmod(total, 1_000_000)
    if rem > 500_000 or (rem == 500_000 and carry % 2 == 1):
        carry += 1
    return days * 86400 + carry


ISO_RE = re.compile(r'^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(\.\d+)?(Z|[+-]\d{2}:?\d{2})?$')
LOCAL_RE = re.compile(r'^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})(\.\d+)?$')
EPOCH_MS_RE = re.compile(r'^\d{13}$')
NUMBER_RE = re.compile(r'^\d+(\.\d+)?$')


def parse_instant(value, station=None):
    """Decode an instant in any of the published encodings."""
    if value is None:
        return None
    s = str(value).strip(STRIP)
    if len(s) == 20 and s[-1] == 'Z' and s[10] == 'T':
        return datetime(int(s[0:4]), int(s[5:7]), int(s[8:10]),
                        int(s[11:13]), int(s[14:16]), int(s[17:19]), tzinfo=UTC)
    m = ISO_RE.match(s)
    if m:
        micro = int(round(float(m.group(7) or 0) * 1_000_000))
        dt = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                      int(m.group(4)), int(m.group(5)), int(m.group(6)), micro, tzinfo=UTC)
        off = m.group(8)
        if off and off != 'Z':
            sign = -1 if off[0] == '-' else 1
            body = off[1:].replace(':', '')
            dt -= sign * timedelta(hours=int(body[:2]), minutes=int(body[2:]))
        return dt
    if EPOCH_MS_RE.match(s):
        return EPOCH + timedelta(milliseconds=int(s))
    if LOCAL_RE.match(s):
        local = LOCAL_RE.match(s)
        micro = int(round(float(local.group(7) or 0) * 1_000_000))
        dt = datetime(int(local.group(1)), int(local.group(2)), int(local.group(3)),
                      int(local.group(4)), int(local.group(5)), int(local.group(6)), micro, tzinfo=UTC)
        if station is not None:
            dt -= timedelta(seconds=station[0] + station[1])
        return dt
    if NUMBER_RE.match(s):
        return SERIAL_ZERO + timedelta(seconds=_serial_seconds(s))
    return None


def parse_ics_instant(value):
    if not value:
        return None
    s = str(value).strip(STRIP)
    m = re.match(r'^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z$', s)
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                        int(m.group(4)), int(m.group(5)), int(m.group(6)), tzinfo=UTC)
    return parse_instant(s)


def q6(ratio):
    """Quantise a ratio to six decimal places, half to even."""
    if ratio is None:
        return None
    if not isinstance(ratio, Fraction):
        ratio = Fraction(str(ratio)) if isinstance(ratio, float) else Fraction(ratio)
    scaled = ratio * 1_000_000
    whole, rem = divmod(scaled.numerator, scaled.denominator)
    twice = 2 * rem
    if twice > scaled.denominator or (twice == scaled.denominator and whole % 2 == 1):
        whole += 1
    return whole / 1_000_000


def ratio_field(num, den):
    """A reported ratio: null when the denominator is zero."""
    if not den:
        return None
    return q6(Fraction(num, den))



def q6_fraction(ratio):
    """Quantise a ratio to six decimal places, half to even, as a fraction."""
    if ratio is None:
        return None
    if not isinstance(ratio, Fraction):
        ratio = Fraction(str(ratio)) if isinstance(ratio, float) else Fraction(ratio)
    scaled = ratio * 1_000_000
    whole, rem = divmod(scaled.numerator, scaled.denominator)
    twice = 2 * rem
    if twice > scaled.denominator or (twice == scaled.denominator and whole % 2 == 1):
        whole += 1
    return Fraction(whole, 1_000_000)


# ----------------------------------------------------------- record layout ---

CANON_FIELD = {
    'rid': 'rid', 'rec': 'rid',
    'par': 'par', 'pnt': 'par',
    'val': 'val', 'val_x1000': 'val',
    'at': 'at', 'ts': 'at',
    'fa': 'fa', 'a': 'fa',
    'fb': 'fb', 'b': 'fb',
}
DEFAULT_FIELDS = ['rid', 'par', 'val', 'at', 'fa', 'fb']


def is_header(cells):
    if not cells:
        return False
    first = str(cells[0]).strip(STRIP).lower() if cells[0] is not None else ''
    return first in ('rid', 'rec')


def header_map(cells):
    """Map canonical field name -> column index for a header band."""
    fmap = {}
    scaled = False
    for idx, cell in enumerate(cells):
        key = str(cell).strip(STRIP).lower() if cell is not None else ''
        if not key:
            continue
        if key == 'val_x1000':
            scaled = True
            fmap['val'] = idx
        elif key in CANON_FIELD:
            fmap[CANON_FIELD[key]] = idx
    return fmap, scaled


def row_record(cells, fmap, scaled):
    rec = {}
    for field, idx in fmap.items():
        if idx < len(cells):
            rec[field] = cells[idx]
    if scaled:
        rec['_scaled'] = True
    return rec


def default_map():
    return header_map(DEFAULT_FIELDS)


# -------------------------------------------------------------- raw readers --

def read_delimited(path, delimiter=','):
    with open(path, 'r', encoding='utf-8-sig', newline='') as f:
        reader = csv.reader(f, delimiter=delimiter)
        fmap, scaled = default_map()
        for cells in reader:
            if not cells or all(str(c).strip() == '' for c in cells):
                continue
            if is_header(cells):
                fmap, scaled = header_map(cells)
                continue
            yield row_record(cells, fmap, scaled)


def normalize_record(rec):
    """Map raw field names of a record to the canonical record layout."""
    out = {}
    for key, value in rec.items():
        k = str(key).strip(STRIP).lower()
        if k == 'val_x1000':
            out['val'] = value
            out['_scaled'] = True
        elif k in CANON_FIELD:
            out.setdefault(CANON_FIELD[k], value)
    return out


def read_xml_records(path):
    for _, elem in ET.iterparse(path, events=('end',)):
        if elem.tag.rsplit('}', 1)[-1].lower() == 'record':
            yield normalize_record(elem.attrib)
            elem.clear()


def read_jsonl_records(path):
    with open(path, 'r', encoding='utf-8-sig') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if isinstance(obj, dict):
                yield normalize_record(obj)


def read_ini_records(path):
    with open(path, 'r', encoding='utf-8-sig') as f:
        for line in f:
            line = line.strip()
            if not line or line[0] in '[#;':
                continue
            if '=' not in line:
                continue
            key, rest = line.split('=', 1)
            rec = {'rid': key.split('@')[0]}
            for part in rest.split(';'):
                if '=' in part:
                    k, v = part.split('=', 1)
                    k = k.strip().lower()
                    if k in CANON_FIELD:
                        rec[CANON_FIELD[k]] = v.strip()
            yield rec


def read_log_records(path):
    kv_re = re.compile(r'(\w+)=([^\s]+)')
    with open(path, 'r', encoding='utf-8-sig') as f:
        for line in f:
            if not line.strip():
                continue
            rec = {}
            for k, v in kv_re.findall(line):
                k = k.lower()
                if k in CANON_FIELD and CANON_FIELD[k] not in rec:
                    rec[CANON_FIELD[k]] = v
            if 'rid' in rec:
                yield rec


def read_mbox_records(path):
    import mailbox
    box = mailbox.mbox(path)
    try:
        for msg in box:
            payload = msg.get_payload()
            if not isinstance(payload, str):
                continue
            rec = {}
            for line in payload.splitlines():
                if ':' not in line:
                    continue
                k, v = line.split(':', 1)
                k = k.strip().lower()
                if k in CANON_FIELD:
                    rec.setdefault(CANON_FIELD[k], v.strip())
            if 'rid' in rec:
                yield rec
    finally:
        box.close()


def read_db_records(path):
    uri = 'file:' + urllib.parse.quote(os.path.abspath(path)) + '?mode=ro'
    con = sqlite3.connect(uri, uri=True)
    try:
        tables = [r[0] for r in con.execute("select name from sqlite_master where type='table'")]
        for table in tables:
            cols = [r[1].lower() for r in con.execute('PRAGMA table_info(%s)' % table)]
            mapped = [(i, c, CANON_FIELD[c]) for i, c in enumerate(cols) if c in CANON_FIELD]
            if len(mapped) < 6:
                continue
            for row in con.execute('select * from %s' % table):
                yield {field: row[i] for i, _c, field in mapped}
    finally:
        con.close()


def read_parquet_records(path):
    import pyarrow.parquet as pq
    table = pq.read_table(path)
    for row in table.to_pylist():
        yield normalize_record(row)


XLSX_NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
XLSX_REL_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
XLSX_ROW = '{%s}row' % XLSX_NS
XLSX_CELL = '{%s}c' % XLSX_NS
XLSX_VALUE = '{%s}v' % XLSX_NS
XLSX_TEXT = '{%s}t' % XLSX_NS
XLSX_SHEET = '{%s}sheet' % XLSX_NS


def read_xlsx_sheets(path):
    """Yield (header_cells, data_rows) per worksheet."""
    with ZipFile(path) as z:
        shared = []
        if 'xl/sharedStrings.xml' in z.namelist():
            sroot = ET.fromstring(z.read('xl/sharedStrings.xml'))
            for si in sroot:
                shared.append(''.join(t.text or '' for t in si.iter(XLSX_TEXT)))
        wb = ET.fromstring(z.read('xl/workbook.xml'))
        rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        relmap = {rel.get('Id'): rel.get('Target') for rel in rels}
        for sheet in wb.iter(XLSX_SHEET):
            target = (relmap.get(sheet.get('{%s}id' % XLSX_REL_NS)) or '').lstrip('/')
            if not target.startswith('xl/'):
                target = 'xl/' + target
            if target not in z.namelist():
                continue
            rows = []
            for _, row in ET.iterparse(z.open(target), events=('end',)):
                if row.tag != XLSX_ROW:
                    continue
                cells = []
                for c in row:
                    if c.tag != XLSX_CELL:
                        continue
                    col = 0
                    m = re.match(r'^([A-Z]+)', c.get('r') or '')
                    if m:
                        for ch in m.group(1):
                            col = col * 26 + (ord(ch) - 64)
                    kind = c.get('t')
                    value = None
                    v = c.find(XLSX_VALUE)
                    if kind == 's':
                        if v is not None and v.text is not None:
                            idx = int(v.text)
                            value = shared[idx] if idx < len(shared) else None
                    elif kind == 'inlineStr':
                        value = ''.join(t.text or '' for t in c.iter(XLSX_TEXT))
                    elif v is not None:
                        value = v.text
                    while len(cells) < col - 1:
                        cells.append(None)
                    cells.append(value)
                rows.append(cells)
                row.clear()
            yield (rows[0] if rows else []), rows[1:]


def read_xlsx_records(path):
    for header, rows in read_xlsx_sheets(path):
        fmap, scaled = header_map(header) if is_header(header) else default_map()
        for cells in rows:
            if all(c is None or str(c).strip() == '' for c in cells):
                continue
            yield row_record(cells, fmap, scaled)

DOCX_NS = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def read_docx_tables(path):
    """Yield (header_cells, data_rows) per table of a docx export."""
    try:
        with ZipFile(path) as z:
            root = ET.fromstring(z.read('word/document.xml'))
    except Exception:
        return
    for table in root.iter(DOCX_NS + 'tbl'):
        rows = []
        for tr in table.iter(DOCX_NS + 'tr'):
            rows.append([''.join(t.text or '' for t in tc.iter(DOCX_NS + 't'))
                         for tc in tr.iter(DOCX_NS + 'tc')])
        if rows:
            yield rows[0], rows[1:]


def _python_docx_tables(path):
    """Table extraction with python-docx, used when the XML shape differs."""
    import docx
    doc = docx.Document(path)
    tables = []
    for table in doc.tables:
        rows = [[c.text for c in row.cells] for row in table.rows]
        if rows:
            tables.append((rows[0], rows[1:]))
    return tables


def read_docx_records(path):
    tables = list(read_docx_tables(path))
    if not tables:
        tables = _python_docx_tables(path)
    for header, rows in tables:
        if not rows:
            continue
        fmap, scaled = header_map(header) if is_header(header) else default_map()
        for cells in rows:
            yield row_record(cells, fmap, scaled)


# ------------------------------------------------------------------- corpus --

FALLBACK_WIDTHS = {'prompt': 5, 'completion': 6, 'comparison': 6, 'verdict': 7,
                   'annotator': 4, 'cluster': 4, 'family': 4, 'workstation': 4}
CHOICE_SOURCES = {
    'calder': 'verdicts_vendor_a.jsonl',
    'northwind': 'verdicts_vendor_b.jsonl',
    'orbit': 'verdicts_shard1.parquet',
    'tessel': 'verdicts_shard2.parquet',
}
FAR_FUTURE = datetime(9999, 12, 31, tzinfo=UTC)


class Corpus:
    """Loaded exports and the release parameters they publish."""

    def __init__(self, data_dir):
        self.dir = data_dir
        self.audit = {}
        self.params = load_policy(self.path('corpus_policy.md'))
        self.zones, widths = load_conventions(self.path('source_conventions.md'))
        self.width = dict(FALLBACK_WIDTHS)
        self.width.update(widths)
        self.window_start = parse_instant(self.params['collection_window_start'])
        self.window_end = parse_instant(self.params['collection_window_end'])
        self.cutoff = parse_instant(self.params['adjudication_cutoff'])
        self.choices = {}
        self.load_all()

    def path(self, name):
        return os.path.join(self.dir, name)

    def records(self, filename):
        """Records of an export, or nothing when the export is absent."""
        path = self.path(filename)
        if not os.path.exists(path):
            return
        reader = READERS.get(os.path.splitext(filename)[1].lower())
        if reader is None:
            return
        for rec in reader(path):
            yield rec

    def param_int(self, key):
        return int(str(self.params[key]).strip())

    def param_frac(self, key):
        return Fraction(str(self.params[key]).strip())

    def load_all(self):
        self.load_prompts()
        self.load_completions()
        self.load_comparisons()
        self.load_annotators()
        self.load_stations()
        self.load_verdicts()
        self.load_gold()
        self.load_adjudications()
        self.load_errata()
        self.load_freezes()
        self.load_contamination()
        self.load_clusters()
        self.load_mixture()

    # -- registries --------------------------------------------------------

    def load_prompts(self):
        w_p, w_f = self.width['prompt'], self.width['family']
        self.prompts = {}
        n = 0
        for rec in self.records('prompt_registry.csv'):
            n += 1
            pid = canon(rec.get('rid'), w_p)
            if pid not in self.prompts:
                self.prompts[pid] = {
                    'family': canon(rec.get('par'), w_f),
                    'tokens': parse_number(rec.get('val'), rec.get('_scaled')),
                    'domain': text(rec.get('fa')),
                    'source': text(rec.get('fb')),
                    'cluster': None,
                }
        self.audit['prompt_registry.csv'] = n
        n = 0
        for rec in self.records('slice_attributes.csv'):
            n += 1
            pid = canon(rec.get('rid'), w_p)
            info = self.prompts.get(pid)
            if info is not None:
                info['locale'] = locale_code(rec.get('fa'))
                info['difficulty'] = text(rec.get('fb'))
        self.audit['slice_attributes.csv'] = n
        n = 0
        for rec in self.records('prompt_locales.tsv'):
            n += 1
            pid = canon(rec.get('rid'), w_p)
            info = self.prompts.get(pid)
            if info is not None:
                info['risk'] = text(rec.get('fa'))
        self.audit['prompt_locales.tsv'] = n

    def load_completions(self):
        w_c, w_p = self.width['completion'], self.width['prompt']
        self.completions = {}
        n = 0
        for rec in self.records('completion_index.csv'):
            n += 1
            cid = canon(rec.get('rid'), w_c)
            if cid not in self.completions:
                self.completions[cid] = {
                    'prompt': canon(rec.get('par'), w_p),
                    'tokens': parse_number(rec.get('val'), rec.get('_scaled')),
                }
        self.audit['completion_index.csv'] = n
        amend = {}
        n = 0
        for rec in self.records('completion_amendments.xml'):
            n += 1
            cid = canon(rec.get('rid'), w_c)
            when = parse_instant(rec.get('at'))
            if cid not in amend:
                amend[cid] = when
            elif when is not None and (amend[cid] is None or when > amend[cid]):
                amend[cid] = when
        self.audit['completion_amendments.xml'] = n
        self.amendments = amend

    def load_comparisons(self):
        w_m, w_p, w_c = self.width['comparison'], self.width['prompt'], self.width['completion']
        self.comparisons = {}
        n = 0
        for rec in self.records('batch_registry.xml'):
            n += 1
            mid = canon(rec.get('rid'), w_m)
            if mid not in self.comparisons:
                self.comparisons[mid] = {
                    'prompt': canon(rec.get('par'), w_p),
                    'left': canon(rec.get('fa'), w_c),
                    'right': canon(rec.get('fb'), w_c),
                    'balanced': None,
                }
        self.audit['batch_registry.xml'] = n
        n = 0
        for rec in self.records('harness_events.log'):
            n += 1
            mid = canon(rec.get('rid'), w_m)
            info = self.comparisons.get(mid)
            if info is not None:
                info['balanced'] = (text(rec.get('fb')) == 'balanced')
        self.audit['harness_events.log'] = n

    def load_annotators(self):
        w_a = self.width['annotator']
        self.annotators = {}
        n = 0
        for rec in self.records('annotator_roster.csv'):
            n += 1
            aid = canon(rec.get('rid'), w_a)
            if aid not in self.annotators:
                self.annotators[aid] = text(rec.get('par'))
        self.audit['annotator_roster.csv'] = n

    def load_stations(self):
        w_s = self.width['workstation']
        self.stations = {}
        n = 0
        for rec in self.records('workstation_inventory.ini'):
            n += 1
            ws = canon(rec.get('rid'), w_s)
            if ws not in self.stations:
                zone = (text(rec.get('fa')) or '').upper()
                offset = parse_number(rec.get('fb'))
                self.stations[ws] = (self.zones.get(zone, 0), int(offset or 0))
        self.audit['workstation_inventory.ini'] = n

    def load_verdicts(self):
        w_v, w_m, w_a, w_s = (self.width['verdict'], self.width['comparison'],
                              self.width['annotator'], self.width['workstation'])
        self.verdicts = {}
        n = 0
        for rec in self.records('annotation_store.db'):
            n += 1
            vid = canon(rec.get('rid'), w_v)
            if vid in self.verdicts:
                continue
            ws = canon(rec.get('fb'), w_s)
            self.verdicts[vid] = {
                'comparison': canon(rec.get('par'), w_m),
                'confidence': parse_number(rec.get('val'), rec.get('_scaled')),
                'instant': parse_instant(rec.get('at'), self.stations.get(ws)),
                'annotator': canon(rec.get('fa'), w_a),
                'station': ws,
                'choice': None,
            }
        self.audit['annotation_store.db'] = n
        for vendor, filename in sorted(CHOICE_SOURCES.items()):
            choices = {}
            n = 0
            for rec in self.records(filename):
                n += 1
                vid = canon(rec.get('rid'), w_v)
                if vid not in choices:
                    choices[vid] = text(rec.get('fb'))
            if n:
                self.audit[filename] = n
            self.choices[vendor] = choices
        for vid, info in self.verdicts.items():
            vendor = self.annotators.get(info['annotator'])
            info['choice'] = self.choices.get(vendor, {}).get(vid)

    def load_gold(self):
        w_m, w_c = self.width['comparison'], self.width['completion']
        answers = {}
        n = 0
        for rec in self.records('gold_set.tsv'):
            n += 1
            mid = canon(rec.get('rid'), w_m)
            if mid not in answers:
                answers[mid] = canon(rec.get('fb'), w_c)
        self.audit['gold_set.tsv'] = n
        self.gold = answers
        retired = {}
        n = 0
        for rec in self.records('gold_answers_revised.csv'):
            n += 1
            value = str(rec.get('val')).strip(STRIP).lower()
            if value in SENTINELS:
                continue
            if text(rec.get('fa')) != 'retired':
                continue
            mid = canon(rec.get('rid'), w_m)
            when = parse_instant(rec.get('at'))
            if mid not in retired:
                retired[mid] = when
            elif when is not None and (retired[mid] is None or when < retired[mid]):
                retired[mid] = when
        self.audit['gold_answers_revised.csv'] = n
        self.gold_retired = retired

    def load_adjudications(self):
        w_m = self.width['comparison']
        adjudications = {}
        n = 0
        for rec in self.records('adjudications.jsonl'):
            n += 1
            mid = canon(rec.get('rid'), w_m)
            if mid in adjudications:
                continue
            adjudications[mid] = {
                'instant': parse_instant(rec.get('at')),
                'choice': text(rec.get('fa')),
            }
        self.audit['adjudications.jsonl'] = n
        self.adjudications = adjudications
        approvals = {}
        n = 0
        for rec in self.records('review_minutes.docx'):
            n += 1
            approvals[canon(rec.get('rid'), w_m)] = (text(rec.get('fa')) == 'approved')
        self.audit['review_minutes.docx'] = n
        self.approvals = approvals

    def load_errata(self):
        w_p, w_v = self.width['prompt'], self.width['verdict']
        prompt_flags = collections.defaultdict(set)
        verdict_flags = collections.defaultdict(set)
        n = 0
        for rec in self.records('errata_register.docx'):
            n += 1
            entity = text(rec.get('par'))
            action = text(rec.get('fa'))
            if entity == 'prompt':
                prompt_flags[canon(rec.get('rid'), w_p)].add(action)
            elif entity == 'verdict':
                verdict_flags[canon(rec.get('rid'), w_v)].add(action)
        self.audit['errata_register.docx'] = n
        self.prompt_retired = {p for p, a in prompt_flags.items() if 'retire' in a}
        self.prompt_opted_out = {p for p, a in prompt_flags.items() if 'optout' in a}
        self.verdict_voided = {v for v, a in verdict_flags.items() if 'void' in a}
        self.verdict_restored = {v for v, a in verdict_flags.items() if 'restore' in a}

    def load_freezes(self):
        w_s = self.width['workstation']
        lines = []
        ics_path = self.path('freeze_windows.ics')
        if not os.path.exists(ics_path):
            self.freezes = {}
            return
        with open(ics_path, 'r', encoding='utf-8-sig') as f:
            for line in f:
                line = line.rstrip('\r\n')
                if not line.strip():
                    continue
                if line[:1] in (' ', '\t') and lines:
                    lines[-1] += line.strip()
                else:
                    lines.append(line)
        freezes = collections.defaultdict(list)
        event = {}
        for line in lines + ['END:VEVENT']:
            if ':' not in line:
                continue
            key, value = line.split(':', 1)
            key = key.strip().upper()
            value = value.strip()
            if key == 'BEGIN' and value.upper() == 'VEVENT':
                event = {}
            elif key == 'END' and value.upper() == 'VEVENT':
                if event:
                    ws = canon(event.get('X-WORKSTATION'), w_s)
                    start = parse_ics_instant(event.get('DTSTART'))
                    hours = parse_number(event.get('X-HOURS'))
                    if ws and start is not None and hours is not None:
                        end = start + timedelta(seconds=int(hours * 3600))
                        freezes[ws].append((start, end))
                event = {}
            else:
                event[key] = value
        self.freezes = {ws: sorted(v) for ws, v in freezes.items()}

    def load_contamination(self):
        w_p = self.width['prompt']
        best = {}
        n = 0
        for rec in self.records('contamination_hits.jsonl'):
            n += 1
            pid = canon(rec.get('rid'), w_p)
            value = parse_number(rec.get('val'), rec.get('_scaled'))
            if value is None:
                continue
            if pid not in best or value > best[pid]:
                best[pid] = value
        self.audit['contamination_hits.jsonl'] = n
        self.similarity = best

    def load_clusters(self):
        w_d, w_p = self.width['cluster'], self.width['prompt']
        members = collections.defaultdict(set)
        effective = {}
        n = 0
        for rec in self.records('dedup_clusters.tsv'):
            n += 1
            cid = canon(rec.get('rid'), w_d)
            pid = canon(rec.get('par'), w_p)
            members[cid].add(pid)
            when = parse_instant(rec.get('at'))
            key = (cid, pid)
            if key not in effective or (when is not None and
                                        (effective[key] is None or when < effective[key])):
                effective[key] = when
        self.audit['dedup_clusters.tsv'] = n
        self.clusters = {}
        for cid, pids in members.items():
            canonical = min(pids, key=lambda p: (effective.get((cid, p)) is None,
                                                effective.get((cid, p)) or FAR_FUTURE, p))
            self.clusters[cid] = {
                'canonical': canonical,
                'members': sorted(pids),
                'effective': effective.get((cid, canonical)),
            }
        for cid, info in self.clusters.items():
            for pid in info['members']:
                prompt = self.prompts.get(pid)
                if prompt is not None:
                    prompt['cluster'] = cid

    def load_mixture(self):
        targets = {}
        n = 0
        for rec in self.records('mixture_targets.xlsx'):
            n += 1
            source = text(rec.get('fa'))
            weight = parse_number(rec.get('fb'))
            if source and weight is not None and source not in targets:
                targets[source] = weight
        self.audit['mixture_targets.xlsx'] = n
        self.targets = targets


def _entries_of(data):
    if isinstance(data, dict):
        for value in data.values():
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        yield item
            elif isinstance(value, dict):
                yield from _entries_of(value)
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                yield item


def read_yaml_records(path):
    import yaml
    loader = getattr(yaml, 'CSafeLoader', yaml.SafeLoader)
    with open(path, 'r', encoding='utf-8-sig') as f:
        yield from _entries_of(yaml.load(f, Loader=loader))


def read_toml_records(path):
    import tomllib
    with open(path, 'rb') as f:
        yield from _entries_of(tomllib.load(f))


def read_json_records(path):
    with open(path, 'r', encoding='utf-8-sig') as f:
        yield from _entries_of(json.load(f))


def count_lines(path):
    n = 0
    with open(path, 'r', encoding='utf-8-sig') as f:
        for line in f:
            s = line.strip()
            if not s or s[0] in '#;[':
                continue
            n += 1
    return n


def count_markup_records(path):
    n = 0
    id_cell = re.compile(r'^[A-Za-z]{1,6}-\d+$')
    with open(path, 'r', encoding='utf-8-sig') as f:
        for line in f:
            if '|' not in line:
                continue
            cells = [c.strip(STRIP) for c in line.strip().strip('|').split('|')]
            if len(cells) >= 6 and id_cell.match(cells[0]):
                n += 1
    return n


READERS = {
    '.csv': lambda p: read_delimited(p, ','),
    '.tsv': lambda p: read_delimited(p, '\t'),
    '.xml': read_xml_records,
    '.jsonl': read_jsonl_records,
    '.json': read_json_records,
    '.yaml': read_yaml_records,
    '.toml': read_toml_records,
    '.ini': read_ini_records,
    '.mbox': read_mbox_records,
    '.db': read_db_records,
    '.parquet': read_parquet_records,
    '.xlsx': read_xlsx_records,
    '.docx': read_docx_records,
    '.log': read_log_records,
}
COUNT_READERS = {'.txt': count_lines, '.md': count_markup_records,
                 '.html': count_markup_records, '.htm': count_markup_records}
FAST_COUNTS = {'.yaml': None, '.toml': None, '.mbox': None}
NO_RECORDS = {'.pdf', '.ics'}


YAML_ITEM = re.compile(r'^\s*-\s+(rid|rec|par|pnt|val|val_x1000|at|ts|fa|a|fb|b)\s*:',
                       re.IGNORECASE)
TOML_TABLE = re.compile(r'^\s*\[\[\s*\w+\s*\]\]')
MBOX_RECORD = re.compile(r'^\s*(rid|rec)\s*:', re.IGNORECASE)


def count_records(path):
    """Count the records a file carries in the published record layout."""
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext in NO_RECORDS:
            return 0
        if ext in COUNT_READERS:
            return COUNT_READERS[ext](path)
        fast = FAST_COUNTS.get(ext)
        if fast is not None:
            counted = fast(path)
            if counted:
                return counted
        reader = READERS.get(ext)
        if reader is None:
            return 0
        return sum(1 for _ in reader(path))
    except Exception:
        return 0


def _count_yaml(path):
    n = 0
    with open(path, 'r', encoding='utf-8-sig') as f:
        for line in f:
            if YAML_ITEM.match(line):
                n += 1
    return n


def _count_toml(path):
    n = 0
    with open(path, 'r', encoding='utf-8-sig') as f:
        for line in f:
            if TOML_TABLE.match(line):
                n += 1
    return n


def _count_mbox(path):
    n = 0
    with open(path, 'r', encoding='utf-8-sig') as f:
        for line in f:
            if MBOX_RECORD.match(line):
                n += 1
    return n


FAST_COUNTS['.yaml'] = _count_yaml
FAST_COUNTS['.toml'] = _count_toml
FAST_COUNTS['.mbox'] = _count_mbox


# ------------------------------------------------------------------- policy --

PARAM_KEY = re.compile(r'^[a-z_][a-z0-9_.]*$')
REGISTERED_FORM = re.compile(r'^([A-Za-z]+)-(\d+)$')
ZONE_OFFSET = re.compile(r'^([+-])(\d{2}):(\d{2})$')


def load_policy(path):
    """Release parameters as published in corpus_policy.md."""
    params = {}
    with open(path, 'r', encoding='utf-8-sig') as f:
        for line in f:
            line = line.strip()
            if not line.startswith('|'):
                continue
            cells = [c.strip() for c in line.strip('|').split('|')]
            if len(cells) != 2:
                continue
            key, value = cells
            if not PARAM_KEY.match(key) or not value:
                continue
            params[key] = value
    return params


def load_conventions(path):
    """Zone offsets and registered identifier forms from source_conventions.md."""
    zones = {}
    widths = {}
    with open(path, 'r', encoding='utf-8-sig') as f:
        for line in f:
            line = line.strip()
            if not line.startswith('|'):
                continue
            cells = [c.strip() for c in line.strip('|').split('|')]
            if len(cells) == 2:
                m = ZONE_OFFSET.match(cells[1])
                if m:
                    sign = 1 if m.group(1) == '+' else -1
                    zones[cells[0].upper()] = sign * (int(m.group(2)) * 3600 + int(m.group(3)) * 60)
            elif len(cells) == 3:
                m = REGISTERED_FORM.match(cells[2])
                if m:
                    widths[cells[0].lower()] = len(m.group(2))
    return zones, widths


# ------------------------------------------------------------------ release --

CHOICES = ('left', 'right', 'tie', 'both_bad')
AGREEMENT_CHOICES = ('left', 'right', 'tie')


class Release:
    """The release computed over a loaded corpus."""

    def __init__(self, corpus):
        self.c = corpus
        self.floors = {key.split('.', 1)[1]: Fraction(str(value))
                       for key, value in corpus.params.items()
                       if key.startswith('gold_floor.')}
        self.compute_standing()
        self.compute_admissibility()
        self.compute_resolution()
        self.compute_agreement()
        self.compute_eligibility()
        self.compute_pairs()
        self.compute_split()
        self.compute_mixture()
        self.compute_packing()

    # -- annotator standing ------------------------------------------------

    def compute_standing(self):
        c = self.c
        min_items = c.param_int('gold_min_items')
        bias_limit = c.param_frac('bias_limit')
        stats = {aid: {'gold_items': 0, 'gold_hits': 0, 'balanced': 0, 'left': 0}
                 for aid in c.annotators}
        for vid, info in c.verdicts.items():
            stat = stats.get(info['annotator'])
            if stat is None:
                continue
            choice = info['choice']
            mid = info['comparison']
            comp = c.comparisons.get(mid)
            gold = c.gold.get(mid)
            if gold is not None:
                when = c.gold_retired.get(mid)
                instant = info['instant']
                if not (when is not None and instant is not None and when <= instant):
                    stat['gold_items'] += 1
                    if comp is not None:
                        if choice == 'left' and comp['left'] == gold:
                            stat['gold_hits'] += 1
                        elif choice == 'right' and comp['right'] == gold:
                            stat['gold_hits'] += 1
            if comp is not None and comp['balanced'] is True and choice in ('left', 'right'):
                stat['balanced'] += 1
                if choice == 'left':
                    stat['left'] += 1
        self.standing = {}
        for aid, vendor in c.annotators.items():
            stat = stats.get(aid)
            items, hits = stat['gold_items'], stat['gold_hits']
            balanced, left = stat['balanced'], stat['left']
            agreement = Fraction(hits, items) if items else None
            bias = Fraction(left, balanced) - Fraction(1, 2) if balanced else None
            biased = bias is not None and abs(bias) > bias_limit
            floor = self.floors.get(vendor, Fraction(0))
            admitted = (items >= min_items and agreement is not None and agreement >= floor)
            self.standing[aid] = {
                'vendor': vendor,
                'gold_items': items,
                'gold_hits': hits,
                'gold_agreement': q6(agreement) if agreement is not None else None,
                'balanced_verdicts': balanced,
                'a_side_bias': q6(bias) if bias is not None else None,
                'biased': bool(biased),
                'standing': 'admitted' if admitted else 'gated',
            }
        self.gated = {aid for aid, s in self.standing.items() if s['standing'] == 'gated'}
        self.biased = {aid for aid, s in self.standing.items() if s['biased']}

    # -- verdict admissibility ---------------------------------------------

    def compute_admissibility(self):
        c = self.c
        start, end = c.window_start, c.window_end
        latest_amend = {}
        for mid, comp in c.comparisons.items():
            times = [t for t in (c.amendments.get(comp['left']),
                                 c.amendments.get(comp['right'])) if t is not None]
            latest_amend[mid] = max(times) if times else None
        self.admissible = {}
        self.admissibility = []
        self.by_comparison = collections.defaultdict(list)
        for vid, info in c.verdicts.items():
            reason = None
            mid = info['comparison']
            instant = info['instant']
            if info['annotator'] in self.gated:
                reason = 'annotator_gated'
            elif instant is None or not (start <= instant < end):
                reason = 'outside_window'
            elif self.frozen(info['station'], instant):
                reason = 'freeze_window'
            elif latest_amend.get(mid) is not None and instant <= latest_amend[mid]:
                reason = 'stale_amendment'
            elif (info['annotator'] in self.biased and
                  c.comparisons.get(mid, {}).get('balanced') is not True):
                reason = 'unbalanced_biased'
            elif vid in c.verdict_voided and vid not in c.verdict_restored:
                reason = 'voided'
            ok = reason is None
            self.admissible[vid] = ok
            if ok:
                self.by_comparison[mid].append(vid)
            self.admissibility.append({
                'verdict_id': vid,
                'comparison': mid,
                'annotator': info['annotator'],
                'admissible': ok,
                'reason': reason,
            })
        self.admissibility.sort(key=lambda r: r['verdict_id'])

    def frozen(self, station, instant):
        if instant is None:
            return False
        for start, end in self.c.freezes.get(station, ()):
            if start <= instant < end:
                return True
        return False

    # -- comparison resolution ----------------------------------------------

    def compute_resolution(self):
        c = self.c
        min_votes = c.param_int('min_votes')
        self.resolution = []
        self.resolved = {}
        for mid in sorted(c.comparisons):
            comp = c.comparisons[mid]
            amend = [t for t in (c.amendments.get(comp['left']),
                                 c.amendments.get(comp['right'])) if t is not None]
            latest = max(amend) if amend else None
            adj = c.adjudications.get(mid)
            votes = len(self.by_comparison.get(mid, ()))
            valid = (adj is not None and adj['choice'] in CHOICES
                     and adj['instant'] is not None
                     and c.approvals.get(mid) is True
                     and (latest is None or adj['instant'] > latest)
                     and adj['instant'] < c.cutoff)
            if valid:
                route, choice, margin = 'adjudicated', adj['choice'], Fraction(1)
            elif votes < min_votes:
                route, choice, margin = 'insufficient', None, None
            else:
                route = 'majority'
                counts = {ch: 0 for ch in CHOICES}
                weight = {ch: 0 for ch in CHOICES}
                for vid in self.by_comparison[mid]:
                    choice_v = c.verdicts[vid]['choice']
                    if choice_v in counts:
                        counts[choice_v] += 1
                        conf = c.verdicts[vid]['confidence']
                        if conf is not None:
                            weight[choice_v] += conf
                best = min(CHOICES, key=lambda ch: (-counts[ch], -weight[ch], ch))
                others = [counts[ch] for ch in CHOICES if ch != best]
                choice, margin = best, Fraction(counts[best] - max(others), votes)
            self.resolved[mid] = choice
            self.resolution.append({
                'comparison_id': mid,
                'resolved': choice,
                'route': route,
                'votes': votes,
                'margin': q6(margin) if margin is not None else None,
            })
        self.resolution.sort(key=lambda r: r['comparison_id'])
        self.resolution_by_id = {r['comparison_id']: r for r in self.resolution}

    # -- agreement ---------------------------------------------------------

    @staticmethod
    def _fold(choice):
        if choice == 'both_bad':
            return 'tie'
        return choice if choice in AGREEMENT_CHOICES else None

    def compute_agreement(self):
        c = self.c
        overall_units = []
        vendor_units = collections.defaultdict(list)
        domain_units = collections.defaultdict(list)
        for mid in sorted(c.comparisons):
            vids = self.by_comparison.get(mid)
            if not vids or len(vids) < 2:
                continue
            cats = [self._fold(c.verdicts[v]['choice']) for v in vids]
            overall_units.append(cats)
            comp = c.comparisons[mid]
            prompt = c.prompts.get(comp['prompt'])
            if prompt is not None and prompt.get('domain'):
                domain_units[prompt['domain']].append(cats)
            per_vendor = collections.defaultdict(list)
            for v, cat in zip(vids, cats):
                vendor = c.annotators.get(c.verdicts[v]['annotator'])
                if vendor is not None:
                    per_vendor[vendor].append(cat)
            for vendor, group in per_vendor.items():
                if len(group) >= 2:
                    vendor_units[vendor].append(group)
        self.agreement = {
            'overall': self._agreement_stats(overall_units),
            'by_vendor': {v: self._agreement_stats(g) for v, g in sorted(vendor_units.items())},
            'by_domain': {d: self._agreement_stats(g) for d, g in sorted(domain_units.items())},
        }
        self.kappa_fraction = self._kappa_fraction(overall_units)

    @staticmethod
    def _raw_agreement(units):
        """Observed agreement and kappa as exact fractions."""
        counts = {ch: 0 for ch in AGREEMENT_CHOICES}
        total = 0
        observed_num = 0
        observed_den = 0
        for cats in units:
            n = 0
            local = collections.Counter()
            for cat in cats:
                if cat is None:
                    continue
                n += 1
                local[cat] += 1
                counts[cat] += 1
            total += n
            observed_num += sum(k * (k - 1) for k in local.values())
            observed_den += n * (n - 1)
        observed = Fraction(observed_num, observed_den) if observed_den else None
        expected = None
        if total:
            expected = sum(Fraction(counts[ch], total) ** 2 for ch in AGREEMENT_CHOICES)
        if observed is None or expected is None:
            kappa = None
        elif expected == 1:
            kappa = Fraction(0)
        else:
            kappa = (observed - expected) / (1 - expected)
        return observed, kappa

    @classmethod
    def _agreement_stats(cls, units):
        """Agreement statistics over a group of rating units."""
        observed, kappa = cls._raw_agreement(units)
        pairs = 0
        for cats in units:
            n = sum(1 for cat in cats if cat is not None)
            pairs += n * (n - 1) // 2
        return {
            'observed_agreement': q6(observed) if observed is not None else None,
            'kappa': q6(kappa) if kappa is not None else None,
            'rated_units': len(units),
            'rater_pairs': pairs,
        }

    def _kappa_fraction(self, units):
        """The reported kappa as an exact fraction."""
        _observed, kappa = self._raw_agreement(units)
        if kappa is None:
            return None
        return q6_fraction(kappa)

    # -- prompt eligibility ------------------------------------------------

    def compute_eligibility(self):
        c = self.c
        hard = c.param_frac('contamination_hard')
        max_prompt_tokens = c.param_int('max_prompt_tokens')
        resolved_side = collections.defaultdict(int)
        for mid, choice in self.resolved.items():
            if choice in ('left', 'right'):
                resolved_side[c.comparisons[mid]['prompt']] += 1
        self.eligibility = []
        self.eligible = {}
        for pid in sorted(c.prompts):
            info = c.prompts[pid]
            sim = c.similarity.get(pid)
            cluster = info.get('cluster')
            canonical = (cluster is not None
                         and c.clusters[cluster]['canonical'] == pid)
            if pid in c.prompt_retired:
                reason = 'retired'
            elif pid in c.prompt_opted_out:
                reason = 'opted_out'
            elif sim is not None and sim >= hard:
                reason = 'contaminated'
            elif cluster is not None and not canonical:
                reason = 'duplicate'
            elif (info.get('tokens') is not None
                  and info['tokens'] > max_prompt_tokens):
                reason = 'over_length'
            elif not resolved_side.get(pid):
                reason = 'no_resolved_pair'
            else:
                reason = None
            ok = reason is None
            self.eligible[pid] = ok
            self.eligibility.append({
                'prompt_id': pid,
                'eligible': ok,
                'reason': reason,
                'cluster': cluster,
                'family': info.get('family'),
                'source': info.get('source'),
            })
        self.eligibility.sort(key=lambda r: r['prompt_id'])

    # -- preference pairs ---------------------------------------------------

    def compute_pairs(self):
        c = self.c
        max_pair_tokens = c.param_int('max_pair_tokens')
        self.pairs = []
        for mid in sorted(c.comparisons):
            choice = self.resolved.get(mid)
            if choice not in ('left', 'right'):
                continue
            comp = c.comparisons[mid]
            prompt = c.prompts.get(comp['prompt'])
            if prompt is None or not self.eligible.get(comp['prompt']):
                continue
            left_tokens = c.completions.get(comp['left'], {}).get('tokens')
            right_tokens = c.completions.get(comp['right'], {}).get('tokens')
            tokens = as_int((prompt.get('tokens') or 0) + (left_tokens or 0) + (right_tokens or 0))
            if tokens > max_pair_tokens:
                continue
            chosen = comp['left'] if choice == 'left' else comp['right']
            rejected = comp['right'] if choice == 'left' else comp['left']
            row = self.resolution_by_id[mid]
            self.pairs.append({
                'pair_id': 'PP-' + mid.split('-', 1)[1],
                'comparison': mid,
                'prompt': comp['prompt'],
                'family': prompt.get('family'),
                'source': prompt.get('source'),
                'chosen': chosen,
                'rejected': rejected,
                'margin': row['margin'],
                'route': row['route'],
                'tokens': tokens,
                '_split': None,
            })
        self.pairs.sort(key=lambda p: p['pair_id'])

    # -- split --------------------------------------------------------------

    def compute_split(self):
        c = self.c
        soft = c.param_frac('contamination_soft')
        hard = c.param_frac('contamination_hard')
        validation_fraction = c.param_frac('validation_fraction')
        family_pairs = collections.defaultdict(int)
        for pair in self.pairs:
            if pair['family'] is not None:
                family_pairs[pair['family']] += 1
        total = len(self.pairs)
        soft_families = set()
        for pid, info in c.prompts.items():
            sim = c.similarity.get(pid)
            if sim is not None and soft <= sim < hard:
                soft_families.add(info.get('family'))
        self.split = {}
        validation_pairs = 0
        for family in sorted(family_pairs):
            if family in soft_families:
                self.split[family] = 'validation'
                validation_pairs += family_pairs[family]
        target = validation_fraction * total
        for family in sorted(family_pairs):
            if family in self.split:
                continue
            if validation_pairs < target:
                self.split[family] = 'validation'
                validation_pairs += family_pairs[family]
            else:
                self.split[family] = 'train'
        pair_counts = {'train': 0, 'validation': 0}
        for pair in self.pairs:
            split = self.split.get(pair['family'], 'train')
            pair_counts[split] += 1
            pair['_split'] = split
        family_counts = {'train': 0, 'validation': 0}
        for family, split in self.split.items():
            family_counts[split] += 1
        self.split_summary = {
            'families': self.split,
            'family_counts': family_counts,
            'pair_counts': pair_counts,
            'validation_share': ratio_field(pair_counts['validation'], total),
        }

    # -- mixture -----------------------------------------------------------

    def compute_mixture(self):
        c = self.c
        epoch_cap = c.param_int('epoch_cap')
        available = collections.defaultdict(int)
        for pair in self.pairs:
            if pair['_split'] == 'train':
                available[pair['source']] += 1
        budget = sum(available.values())
        sources = set(c.targets) | set(available)
        targets = {s: Fraction(c.targets.get(s, 0), 100) for s in sources}
        caps = {s: epoch_cap * available[s] for s in sources}
        allocated = {s: Fraction(0) for s in sources}
        free = {s for s in sources if available[s] > 0}
        capped = {s: False for s in sources}
        remaining = Fraction(budget)
        while free:
            target_sum = sum(targets[s] for s in free)
            if not target_sum:
                break
            offers = {s: remaining * targets[s] / target_sum for s in free}
            over = {s for s in free if offers[s] > caps[s]}
            if not over:
                for s in free:
                    allocated[s] = offers[s]
                break
            for s in over:
                allocated[s] = Fraction(caps[s])
                capped[s] = True
                free.discard(s)
                remaining -= Fraction(caps[s])
        plan = {}
        total_allocated = 0
        for source in sorted(sources):
            value = allocated[source]
            whole = value.numerator // value.denominator if value.denominator else 0
            total_allocated += whole
            plan[source] = {
                'available_pairs': available[source],
                'target_weight': q6(targets[source]),
                'allocated_pairs': whole,
                'effective_weight': ratio_field(value, budget),
                'epochs': ratio_field(value, available[source]),
                'capped': bool(capped[source]),
            }
        plan['_total'] = {'budget_pairs': budget, 'allocated_pairs': total_allocated}
        self.mixture = plan

    # -- packing and schedule ------------------------------------------------

    def compute_packing(self):
        c = self.c
        seq_len = c.param_int('sequence_length')
        global_batch = c.param_int('global_batch')
        micro_batch = c.param_int('micro_batch')
        shard_sequences = c.param_int('shard_sequences')
        warmup_fraction = c.param_frac('warmup_fraction')
        train = [p for p in self.pairs if p['_split'] == 'train']
        packed = 0
        dropped = 0
        sequences = 0
        used = 0
        current = 0
        for pair in sorted(train, key=lambda p: p['pair_id']):
            tokens = pair['tokens']
            if tokens > seq_len:
                dropped += 1
                continue
            if current and current + tokens <= seq_len:
                current += tokens
            else:
                if current:
                    sequences += 1
                current = tokens
            packed += 1
            used += tokens
        if current:
            sequences += 1
        used = as_int(used)
        capacity = sequences * seq_len
        self.packing = {
            'sequence_length': seq_len,
            'packed_pairs': packed,
            'dropped_pairs': dropped,
            'sequences': sequences,
            'token_capacity': capacity,
            'tokens_used': used,
            'padding_tokens': capacity - used,
            'packing_efficiency': ratio_field(used, capacity),
        }
        optimizer_steps = sequences // global_batch
        warmup = warmup_fraction * optimizer_steps
        warmup_steps = warmup.numerator // warmup.denominator
        remainder = (warmup - warmup_steps)
        if remainder > Fraction(1, 2) or (remainder == Fraction(1, 2) and warmup_steps % 2 == 1):
            warmup_steps += 1
        self.schedule = {
            'sequences': sequences,
            'global_batch': global_batch,
            'micro_batch': micro_batch,
            'gradient_accumulation': global_batch // micro_batch,
            'optimizer_steps': optimizer_steps,
            'warmup_steps': warmup_steps,
            'shards': -(-sequences // shard_sequences),
            'shard_sequences': shard_sequences,
            'dropped_tail_sequences': sequences % global_batch,
        }

    # -- slices ------------------------------------------------------------

    def compute_slices(self):
        c = self.c
        stats = collections.defaultdict(lambda: [0, 0, 0, 0])
        for pair in self.pairs:
            prompt = c.prompts.get(pair['prompt'])
            if prompt is None:
                continue
            keys = []
            if prompt.get('domain'):
                keys.append('domain-' + prompt['domain'])
            if prompt.get('difficulty'):
                keys.append('difficulty-' + prompt['difficulty'])
            if prompt.get('risk'):
                keys.append('risk-' + prompt['risk'])
            if prompt.get('locale'):
                keys.append('locale-' + prompt['locale'])
            if pair.get('source'):
                keys.append('source-' + pair['source'])
            for key in keys:
                entry = stats[key]
                entry[0] += 1
                entry[1 if pair['_split'] == 'train' else 2] += 1
                entry[3] += pair['tokens']

        return {key: {'pairs': v[0], 'train': v[1], 'validation': v[2],
                     'tokens': as_int(v[3])}
                for key, v in sorted(stats.items())}

    # -- gates and reconciliation ------------------------------------------

    def compute_gates(self, slices):
        c = self.c
        min_slice_pairs = c.param_int('min_slice_pairs')
        soft = c.param_frac('contamination_soft')
        limit = c.param_frac('max_train_contamination_rate')
        min_kappa = c.param_frac('min_kappa')
        undersized = sorted(k for k, v in slices.items() if v['pairs'] < min_slice_pairs)
        straddles = False
        family_splits = collections.defaultdict(set)
        for pair in self.pairs:
            family_splits[pair['family']].add(pair['_split'])
        if any(len(v) > 1 for v in family_splits.values()):
            straddles = True
        contaminated_train = 0
        for pair in self.pairs:
            if pair['_split'] != 'train':
                continue
            sim = c.similarity.get(pair['prompt'])
            if sim is not None and sim >= soft:
                # soft covers every screened prompt at or above the soft bound,
                # which includes the hard contaminated ones
                contaminated_train += 1
        rate = (Fraction(contaminated_train, len(self.pairs))
                if self.pairs else None)
        kappa = self.kappa_fraction
        gates = {
            'min_slice_pairs_met': not undersized,
            'no_family_straddles_split': not straddles,
            'train_contamination_within_limit': (rate is not None and rate <= limit),
            'kappa_above_floor': (kappa is not None and kappa >= min_kappa),
            'packing_efficiency_reported': self.packing['sequences'] >= 1,
        }
        gates['release_approved'] = all(gates.values())
        return {
            'gates': gates,
            'undersized_slices': undersized,
            'train_contamination_rate': q6(rate) if rate is not None else None,
            'total_pairs': len(self.pairs),
        }

    def compute_reconciliation(self):
        c = self.c
        return {
            'prompts': len(c.prompts),
            'completions': len(c.completions),
            'comparisons': len(c.comparisons),
            'verdicts': len(c.verdicts),
            'admissible': sum(1 for v in self.admissible.values() if v),
            'resolved': sum(1 for choice in self.resolved.values() if choice is not None),
            'eligible': sum(1 for v in self.eligible.values() if v),
            'pairs': len(self.pairs),
        }


# ----------------------------------------------------------------- artifacts --

def write_json(path, obj):
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(obj, f, ensure_ascii=False, sort_keys=True)
        f.write('\n')


def write_jsonl(path, rows, id_key):
    rows = sorted(rows, key=lambda r: r[id_key])
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            f.write('\n')


def iso(moment):
    if moment is None:
        return None
    return moment.strftime('%Y-%m-%dT%H:%M:%SZ')


def build(data_dir, out_dir):
    corpus = Corpus(data_dir)
    release = Release(corpus)
    os.makedirs(out_dir, exist_ok=True)

    write_json(os.path.join(out_dir, 'annotator_standing.json'), release.standing)
    write_jsonl(os.path.join(out_dir, 'verdict_admissibility.jsonl'),
                release.admissibility, 'verdict_id')
    write_jsonl(os.path.join(out_dir, 'comparison_resolution.jsonl'),
                release.resolution, 'comparison_id')
    write_json(os.path.join(out_dir, 'agreement.json'), release.agreement)
    write_jsonl(os.path.join(out_dir, 'prompt_eligibility.jsonl'),
                release.eligibility, 'prompt_id')

    clusters = {}
    for cid, info in corpus.clusters.items():
        clusters[cid] = {
            'canonical': info['canonical'],
            'members': info['members'],
            'dropped': [p for p in info['members'] if p != info['canonical']],
            'canonical_effective_at': iso(info['effective']),
        }
    write_json(os.path.join(out_dir, 'dedup_clusters.json'), clusters)

    pairs_out = []
    for pair in release.pairs:
        pairs_out.append({k: v for k, v in pair.items() if not k.startswith('_')})
    write_jsonl(os.path.join(out_dir, 'preference_pairs.jsonl'), pairs_out, 'pair_id')

    write_json(os.path.join(out_dir, 'split_assignment.json'), release.split_summary)
    write_json(os.path.join(out_dir, 'mixture_plan.json'), release.mixture)
    write_json(os.path.join(out_dir, 'packing_plan.json'), release.packing)
    write_json(os.path.join(out_dir, 'training_schedule.json'), release.schedule)

    slices = release.compute_slices()
    write_json(os.path.join(out_dir, 'slice_coverage.json'), slices)

    audit = {}
    for name in sorted(os.listdir(data_dir)):
        path = os.path.join(data_dir, name)
        if not os.path.isfile(path):
            continue
        audit[name] = corpus.audit.get(name)
        if audit[name] is None:
            audit[name] = count_records(path)
    write_json(os.path.join(out_dir, 'source_audit.json'), audit)

    write_json(os.path.join(out_dir, 'control_reconciliation.json'),
               release.compute_reconciliation())
    write_json(os.path.join(out_dir, 'release_gates.json'),
               release.compute_gates(slices))


def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: build.py <DATA_DIR> <OUT_DIR>\n')
        return 2
    build(argv[1], argv[2])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))

