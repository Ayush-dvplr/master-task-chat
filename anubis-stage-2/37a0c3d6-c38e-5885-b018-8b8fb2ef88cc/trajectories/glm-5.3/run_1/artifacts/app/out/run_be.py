#!/usr/bin/env python3
"""VRX-BE-2614 bioequivalence recomputation from the LC-MS/MS injection exports.

Usage: python3 run_be.py DATA_DIR OUT_DIR

Implements handbook revision 5 (be_analysis_handbook.md) rules H1-H22 and the output
contract (output_contract.md). Only the Python standard library is used.
"""

import csv
import hashlib
import json
import math
import os
import re
import sqlite3
import sys
import xml.etree.ElementTree as ET
import zlib
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP, getcontext
from fractions import Fraction

getcontext().prec = 80

# --------------------------------------------------------------------------- #
# number formatting (H21, H22)
# --------------------------------------------------------------------------- #


def to_dec(v):
    if isinstance(v, Decimal):
        return v
    if isinstance(v, bool):
        return Decimal(int(v))
    if isinstance(v, int):
        return Decimal(v)
    if isinstance(v, float):
        return Decimal(repr(float(v)))
    if isinstance(v, Fraction):
        return Decimal(v.numerator) / Decimal(v.denominator)
    s = str(v).strip()
    if s == '':
        return Decimal(0)
    return Decimal(s)


def sig(v, n):
    """Round to n significant digits, half away from zero."""
    d = to_dec(v)
    if d == 0:
        return Decimal(0)
    exp = d.adjusted() - n + 1
    return d.scaleb(-exp).quantize(Decimal(1), rounding=ROUND_HALF_UP).scaleb(exp)


def dec_round(v, places):
    """Round to `places` decimals, half away from zero."""
    d = to_dec(v)
    q = Decimal(1).scaleb(-places)
    return d.quantize(q, rounding=ROUND_HALF_UP)


def fmt(d):
    """Canonical plain string: no trailing zeros, no exponent notation."""
    d = to_dec(d)
    if d == 0:
        return '0'
    s = format(d, 'f')
    if '.' in s:
        s = s.rstrip('0').rstrip('.')
    if s in ('', '-'):
        s = '0'
    if s == '-0':
        s = '0'
    return s


def num(v):
    """General number per H21: rounded half away from zero to six significant digits."""
    return fmt(sig(v, 6))


class Raw:
    """A value already rounded at an H22 stage; written exactly as it is."""

    __slots__ = ('d',)

    def __init__(self, v):
        self.d = to_dec(v)

    def __repr__(self):
        return 'Raw(%s)' % self.d


def jdump(o, indent=0):
    pad = '  ' * indent
    npad = '  ' * (indent + 1)
    if o is None:
        return 'null'
    if o is True:
        return 'true'
    if o is False:
        return 'false'
    if isinstance(o, str):
        return json.dumps(o)
    if isinstance(o, int):
        return str(o)
    if isinstance(o, Raw):
        return fmt(o.d)
    if isinstance(o, (Decimal, float)):
        return num(o)
    if isinstance(o, dict):
        if not o:
            return '{}'
        items = []
        for k, v in o.items():
            items.append(npad + json.dumps(str(k)) + ': ' + jdump(v, indent + 1))
        return '{\n' + ',\n'.join(items) + '\n' + pad + '}'
    if isinstance(o, (list, tuple)):
        if not o:
            return '[]'
        items = [npad + jdump(v, indent + 1) for v in o]
        return '[\n' + ',\n'.join(items) + '\n' + pad + ']'
    raise TypeError('cannot serialize %r' % (o,))


def write_json(path, obj):
    with open(path, 'w', newline='\n') as f:
        f.write(jdump(obj) + '\n')


def jdump_flat(o):
    """Single-line JSON (jsonl records)."""
    if o is None:
        return 'null'
    if o is True:
        return 'true'
    if o is False:
        return 'false'
    if isinstance(o, str):
        return json.dumps(o)
    if isinstance(o, int):
        return str(o)
    if isinstance(o, Raw):
        return fmt(o.d)
    if isinstance(o, (Decimal, float)):
        return num(o)
    if isinstance(o, dict):
        if not o:
            return '{}'
        return '{' + ', '.join(json.dumps(str(k)) + ': ' + jdump_flat(v)
                               for k, v in o.items()) + '}'
    if isinstance(o, (list, tuple)):
        if not o:
            return '[]'
        return '[' + ', '.join(jdump_flat(v) for v in o) + ']'
    raise TypeError('cannot serialize %r' % (o,))


# --------------------------------------------------------------------------- #
# PDF memo reader
# --------------------------------------------------------------------------- #

TM_RE = re.compile(rb'(?:(?:-?[\d.]+)\s+){6}Tm')
SHOW_RE = re.compile(rb"(Tj|TJ|')")


def _unescape(s):
    s = re.sub(rb'\\([()\\])', rb'\1', s)
    s = s.replace(b'\\n', b'\n').replace(b'\\r', b'\r')
    return s


def _decode_item(item):
    if item.startswith(b'<'):
        return bytes.fromhex(re.sub(rb'\s', b'', item[1:-1]).decode())
    if item.startswith(b'['):
        parts = []
        k = 0
        while k < len(item):
            if item[k] == 0x28:  # (
                op = _read_paren(item, k)
                if op is None:
                    break
                parts.append(op[1:-1])
                k += len(op)
                continue
            k += 1
        return b''.join(parts)
    return _unescape(item[1:-1])




def _read_paren(block, pos):
    """Read a (string) operand starting at block[pos]; return the operand bytes."""
    depth = 1
    k = pos + 1
    while k < len(block):
        ch = block[k]
        if ch in (0x5c,):  # backslash
            k += 2
            continue
        if ch == 0x28:  # (
            depth += 1
        elif ch == 0x29:  # )
            depth -= 1
            if depth == 0:
                return block[pos:k + 1]
        k += 1
    return None


def _read_text_operand(block, pos):
    """Read the text-showing operand after a Tm inside a BT..ET block."""
    n = len(block)
    while pos < n and block[pos:pos + 1].isspace():
        pos += 1
    if pos >= n:
        return None
    c = block[pos:pos + 1]
    if c == b'(':
        return _read_paren(block, pos)
    if c == b'<':
        e = block.find(b'>', pos)
        return block[pos:e + 1] if e >= 0 else None
    if c == b'[':
        depth = 1
        k = pos + 1
        while k < len(block):
            ch = block[k]
            if ch == 0x5c:  # backslash
                k += 2
                continue
            if ch == 0x28:  # ( -> skip a nested string
                op = _read_paren(block, k)
                if op is None:
                    return None
                k += len(op)
                continue
            if ch == 0x5b:  # [
                depth += 1
            elif ch == 0x5d:  # ]
                depth -= 1
                if depth == 0:
                    return block[pos:k + 1]
            k += 1
        return None
    return None


def pdf_rows(path):
    """Return memo pages as rows: list of (y, texts, xs) per page, top-down."""
    data = open(path, 'rb').read()
    streams = []
    for m in re.finditer(rb'(\d+)\s+(\d+)\s+obj\b', data):
        start = m.end()
        end = data.find(b'endobj', start)
        chunk = data[start:end]
        sm = re.search(rb'stream\r?\n', chunk)
        if not sm:
            continue
        head = chunk[:sm.start()]
        if b'/FlateDecode' not in head:
            continue
        body_start = start + sm.end()
        stream_end = data.find(b'endstream', body_start)
        body = data[body_start:stream_end]
        try:
            body = zlib.decompress(body)
        except Exception:
            continue
        streams.append(body)
    pages = []
    for body in streams:
        cells = []
        pos = 0
        n = len(body)
        while pos < n:
            j = body.find(b'BT', pos)
            if j < 0:
                break
            e = body.find(b'ET', j + 2)
            block = body[j + 2:(e if e >= 0 else n)]
            for tm in TM_RE.finditer(block):
                nums = tm.group(0)[:-2].split()
                x = float(nums[-2])
                y = float(nums[-1])
                rest = block[tm.end():]
                show = SHOW_RE.search(rest[:400])
                if not show:
                    continue
                limit = tm.end() + show.start()
                operand = None
                p = tm.end()
                while p < limit:
                    if block[p:p + 1] in (b'(', b'<', b'['):
                        operand = _read_text_operand(block, p)
                        break
                    p += 1
                if operand is None:
                    continue
                txt = _decode_item(operand).decode('utf-8', 'replace')
                cells.append((y, x, txt))
            pos = (e + 2) if e >= 0 else n
        rows = []
        for y, x, t in sorted(cells, key=lambda c: (-c[0], c[1])):
            if rows and abs(rows[-1][0] - y) <= 2.0:
                rows[-1][1].append((x, t))
            else:
                rows.append((y, [(x, t)]))
        out = []
        for y, items in rows:
            items.sort()
            out.append((y, [t for _x, t in items], [x for x, _t in items]))
        pages.append(out)
    return pages


FOOTER_RE = re.compile(r'^Governance memo .*page \d+ of \d+$')
TITLE_RE = re.compile(r'^\s*Table\s+([A-Z])-(\d+)\s*(\(continued\))?\s*:\s*(.*)$')


def read_memo(path):
    """Parse the governance memo into tables keyed by table id."""
    tables = {}
    order = []
    current = None
    pending_header = False
    for page in pdf_rows(path):
        for _y, texts, xs in page:
            joined = ' '.join(texts).strip()
            if not joined or FOOTER_RE.match(joined):
                continue
            m = TITLE_RE.match(joined)
            if m:
                tid = '%s-%s' % (m.group(1), m.group(2))
                if tid not in tables:
                    tables[tid] = {'title': m.group(4), 'header': None, 'data': []}
                    order.append(tid)
                current = tid
                pending_header = True
                continue
            if current is None:
                continue
            t = tables[current]
            if pending_header:
                if t['header'] is None:
                    t['header'] = list(zip(texts, xs))
                pending_header = False
                continue
            if t['header'] is not None:
                hj = ' '.join(h for h, _x in t['header']).strip()
                if joined == hj:
                    continue
            if joined.startswith('Table '):
                continue
            t['data'].append((texts, xs))
    return tables, order


def table_records(tables, tid):
    """Rows of a memo table as dicts keyed by header cell text (nearest x)."""
    t = tables.get(tid)
    if not t or not t.get('header'):
        return []
    hdr = [(h.strip(), x) for h, x in t['header']]
    out = []
    for texts, xs in t['data']:
        rec = {}
        for txt, x in zip(texts, xs):
            col = None
            bestd = None
            for name, hx in hdr:
                d = abs(hx - x)
                if bestd is None or d < bestd:
                    bestd = d
                    col = name
            rec[col] = txt.strip()
        out.append(rec)
    return out


# --------------------------------------------------------------------------- #
# XLSX reader
# --------------------------------------------------------------------------- #

XLSX_NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
REL_NS = '{http://schemas.openxmlformats.org/package/2006/relationships}'
DOC_REL = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'


def _colnum(c):
    n = 0
    for ch in c:
        n = n * 26 + ord(ch) - 64
    return n


def _colletter(n):
    s = ''
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def read_xlsx(path):
    import zipfile
    z = zipfile.ZipFile(path)
    wbx = ET.fromstring(z.read('xl/workbook.xml'))
    date1904 = False
    pr = wbx.find(XLSX_NS + 'workbookPr')
    if pr is not None and pr.get('date1904') in ('1', 'true'):
        date1904 = True
    rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
    rmap = {}
    for r in rels.findall(REL_NS + 'Relationship'):
        rmap[r.get('Id')] = r.get('Target')
    sst = []
    if 'xl/sharedStrings.xml' in z.namelist():
        sroot = ET.fromstring(z.read('xl/sharedStrings.xml'))
        for si in sroot.findall(XLSX_NS + 'si'):
            sst.append(''.join(t.text or '' for t in si.iter(XLSX_NS + 't')))
    sheets = {}
    names = []
    for sh in wbx.iter(XLSX_NS + 'sheet'):
        name = sh.get('name')
        rid = sh.get(DOC_REL + 'id')
        target = rmap.get(rid, '')
        if not target.startswith('xl/'):
            target = 'xl/' + target
        root = ET.fromstring(z.read(target))
        rows = []
        for rowel in root.iter(XLSX_NS + 'row'):
            cells = {}
            for c in rowel.iter(XLSX_NS + 'c'):
                ref = c.get('r') or ''
                cm = re.match(r'([A-Z]+)', ref)
                col = cm.group(1) if cm else _colletter(len(cells) + 1)
                t = c.get('t')
                v = c.find(XLSX_NS + 'v')
                if v is None:
                    isel = c.find(XLSX_NS + 'is')
                    val = ''.join(t2.text or '' for t2 in isel.iter(XLSX_NS + 't')) if isel is not None else ''
                else:
                    val = v.text or ''
                    if t == 's':
                        val = sst[int(val)]
                cells[col] = val
            rows.append(cells)
        sheets[name] = rows
        names.append(name)
    z.close()
    return sheets, names, date1904


def sheet_table(rows, first_cell):
    """Sheet rows as lists of trimmed strings; header = first row whose first
    cell equals `first_cell`."""
    lists = []
    for cells in rows:
        mx = max((_colnum(k) for k in cells), default=0)
        lists.append([cells.get(_colletter(i), '') for i in range(1, mx + 1)])
    header_idx = None
    for i, r in enumerate(lists):
        if r and (r[0] or '').strip() == first_cell:
            header_idx = i
            break
    if header_idx is None:
        return [], []
    out = []
    for r in lists[header_idx + 1:]:
        vals = [(c or '').strip() for c in r]
        while vals and vals[-1] == '':
            vals.pop()
        if vals:
            out.append(vals)
    return [(c or '').strip() for c in lists[header_idx]], out


def read_csv_rows(path, delim=','):
    with open(path, newline='', encoding='utf-8') as f:
        return [dict((k.strip(), (v or '').strip()) for k, v in r.items())
                for r in csv.DictReader(f, delimiter=delim)]


# --------------------------------------------------------------------------- #
# injection feeds
# --------------------------------------------------------------------------- #

VOID_TOKENS = {'VOID', '9', 'VOIDED', 'TRUE', '1', 'X', 'N', 'CXL', 'DROP', 'DEAD',
               'RETRACTED'}
MANUAL_TOKENS = {'MANUAL', 'M'}
AUTO_TOKENS = {'AUTO', 'A'}

KIND_TOKENS = {
    'i_csv': {'STD': 'STD', 'QC': 'QC', 'DQC': 'DQC', 'UNK': 'UNK', 'BLANK': 'BLANK',
              'ZERO': 'ZERO'},
    'i_tsv': {'STANDARD': 'STD', 'QC': 'QC', 'DILQC': 'DQC', 'UNKNOWN': 'UNK',
              'BLANK': 'BLANK', 'ZERO': 'ZERO'},
    'i_psv': {'STD': 'STD', 'QC': 'QC', 'DQC': 'DQC', 'UNK': 'UNK', 'BLANK': 'BLANK',
              'ZERO': 'ZERO'},
    'i_jsonl': {'STD': 'STD', 'QC': 'QC', 'DQC': 'DQC', 'SAMPLE': 'UNK', 'BLANK': 'BLANK',
                'ZERO': 'ZERO'},
    'i_ndjson': {'CAL': 'STD', 'QC': 'QC', 'DILQC': 'DQC', 'STUDY': 'UNK', 'BLANK': 'BLANK',
                 'ZERO': 'ZERO'},
    'i_xml': {'STD': 'STD', 'QC': 'QC', 'DQC': 'DQC', 'UNK': 'UNK', 'BLANK': 'BLANK',
              'ZERO': 'ZERO'},
    'i_sqlite': {'S': 'STD', 'Q': 'QC', 'D': 'DQC', 'U': 'UNK', 'B': 'BLANK', 'Z': 'ZERO'},
    'i_db': {'STD': 'STD', 'QC': 'QC', 'DQC': 'DQC', 'UNK': 'UNK', 'BLK': 'BLANK',
             'ZERO': 'ZERO'},
    'i_json': {'STANDARD': 'STD', 'QC': 'QC', 'DILQC': 'DQC', 'UNKNOWN': 'UNK',
               'BLANK': 'BLANK', 'ZERO': 'ZERO'},
    'i_yaml': {'STD': 'STD', 'QC': 'QC', 'DQC': 'DQC', 'UNK': 'UNK', 'BLANK': 'BLANK',
               'ZERO': 'ZERO'},
    'i_yml': {'STD': 'STD', 'QC': 'QC', 'DQC': 'DQC', 'UNK': 'UNK', 'BLANK': 'BLANK',
              'ZERO': 'ZERO'},
    'i_txt': {'STD': 'STD', 'QC': 'QC', 'DQC': 'DQC', 'UNK': 'UNK', 'BLANK': 'BLANK',
              'ZERO': 'ZERO'},
    'i_csvsemi': {'STD': 'STD', 'QC': 'QC', 'DQC': 'DQC', 'UNK': 'UNK', 'BLANK': 'BLANK',
                  'ZERO': 'ZERO'},
    'i_tsv2': {'STD': 'STD', 'QC': 'QC', 'DQC': 'DQC', 'UNK': 'UNK', 'BLANK': 'BLANK',
               'ZERO': 'ZERO'},
    'i_jsonl2': {'STD': 'STD', 'QC': 'QC', 'DQC': 'DQC', 'UNK': 'UNK', 'BLANK': 'BLANK',
                 'ZERO': 'ZERO'},
    'i_psv2': {'S': 'STD', 'Q': 'QC', 'D': 'DQC', 'U': 'UNK', 'B': 'BLANK', 'Z': 'ZERO'},
}


def _kv_int(v, kilo=False, comma=False):
    """Parse an area field; kilocounts are multiplied by 1000 and rounded."""
    s = str(v).strip()
    if comma:
        s = s.replace(',', '.')
    d = Decimal(s)
    if kilo:
        d = d * 1000
    return int(d.to_integral_value(rounding=ROUND_HALF_UP))


def _dilution(v):
    """Dilution tokens: N, 1:N, xN all mean N."""
    s = str(v).strip().upper()
    if s.startswith('1:'):
        s = s[2:]
    if s.startswith('X'):
        s = s[1:]
    if s == '':
        return 1
    return int(Decimal(s).to_integral_value(rounding=ROUND_HALF_UP))


def read_feed(path, layout):
    """Read an injection export into raw record dicts."""
    out = []

    def rec(**kw):
        out.append(kw)

    if layout == 'i_csv':
        for r in read_csv_rows(path):
            rec(inj=r['injection_id'], run=r['run_ref'], seq=r['seq'], kind=r['sample_type'],
                ref=r['sample_ref'], dil=r['dilution'], a=r['analyte_area'], i=r['is_area'],
                integ=r['integration'], rev=r['revision'], void=r['state'])
    elif layout == 'i_tsv':
        for r in read_csv_rows(path, '\t'):
            rec(inj=r['INJ'], run=r['RUN'], seq=r['SEQ'], kind=r['TYPE'], ref=r['REF'],
                dil=r['DIL'], a=r['A_AREA'], i=r['IS_AREA'], integ=r['INTEG'], rev=r['REV'],
                void=r['ST'])
    elif layout == 'i_psv':
        for r in read_csv_rows(path, '|'):
            rec(inj=r['inj'], run=r['run'], seq=r['seq'], kind=r['kind'], ref=r['ref'],
                dil=r['df'], a=r['area_counts'], i=r['is_area_kcounts'], kilo_i=True,
                integ=r['int'], rev=r['rev'], void=r['status'])
    elif layout == 'i_jsonl':
        for line in open(path, encoding='utf-8'):
            if not line.strip():
                continue
            d = json.loads(line)
            rec(inj=d['injectionId'], run=d['runRef'], seq=d['seqNo'], kind=d['sampleType'],
                ref=d['sampleRef'], dil=d['dilutionFactor'], a=d['analyteArea'], i=d['isArea'],
                integ=d['integration'], rev=d['revision'], void=d['status'])
    elif layout == 'i_ndjson':
        for line in open(path, encoding='utf-8'):
            if not line.strip():
                continue
            d = json.loads(line)
            s = d['sample']
            ar = d['areas']
            pr = d['proc']
            rec(inj=d['id'], run=d['run'], seq=d['order'], kind=s['type'], ref=s['ref'],
                dil=s['df'], a=ar['analyte'], i=ar['istd'], integ=pr['mode'], rev=pr['rev'],
                void=d['void'])
    elif layout == 'i_xml':
        root = ET.parse(path).getroot()
        for e in root.findall('inj'):
            areas = {c.get('kind'): (c.text or '').strip() for c in e.findall('area')}
            rec(inj=e.get('id'), run=e.get('run'), seq=e.get('seq'), kind=e.get('type'),
                ref=e.get('ref'), dil=e.get('df'), a=areas.get('analyte'),
                i=areas.get('istd'), integ=e.get('integ'), rev=e.get('rev'),
                void=e.get('status'))
    elif layout == 'i_sqlite':
        con = sqlite3.connect(path)
        for row in con.execute('SELECT inj_id, run_token, seq, stype, sref, dil, a_area, '
                               'is_area, integ, rev, voided FROM injection'):
            rec(inj=row[0], run=row[1], seq=row[2], kind=row[3], ref=row[4], dil=row[5],
                a=row[6], i=row[7], integ=row[8], rev=row[9], void=row[10])
        con.close()
    elif layout == 'i_db':
        con = sqlite3.connect(path)
        areas = {}
        for inj_id, rev, ch, val in con.execute('SELECT inj_id, rev, channel, value FROM area'):
            areas[(inj_id, rev, ch)] = val
        for row in con.execute('SELECT id, run, seq, stype, sref, dil, integ, rev, flag FROM inj'):
            areas_a = areas.get((row[0], row[7], 'A'))
            areas_i = areas.get((row[0], row[7], 'IS'))
            if areas_a is None or areas_i is None:
                for ch in ('A', 'IS'):
                    if areas.get((row[0], row[7], ch)) is not None:
                        pass
            rec(inj=row[0], run=row[1], seq=row[2], kind=row[3], ref=row[4], dil=row[5],
                a=areas_a, i=areas_i, integ=row[6], rev=row[7], void=row[8])
        con.close()
    elif layout == 'i_json':
        d = json.load(open(path, encoding='utf-8'))['export']
        cols = d['columns']
        for row in d['rows']:
            r = dict(zip(cols, row))
            rec(inj=r['inj'], run=r['run'], seq=r['seq'], kind=r['type'], ref=r['ref'],
                dil=r['df'], a=r['area_analyte'], i=r['area_istd'], integ=r['integration'],
                rev=r['rev'], void=r['state'])
    elif layout in ('i_yaml', 'i_yml'):
        data = read_yaml(path)
        items = data.get('injections' if layout == 'i_yaml' else 'records') or []
        for r in items:
            if layout == 'i_yaml':
                rec(inj=r['inj'], run=r['run'], seq=r['seq'], kind=r['type'], ref=r['ref'],
                    dil=r['df'], a=r['area_a'], i=r['area_is'], integ=r['integ'],
                    rev=r['rev'], void=r['st'])
            else:
                rec(inj=r['injection'], run=r['batch'], seq=r['position'], kind=r['kind'],
                    ref=r['label'], dil=r['dilution'], a=r['analyte_counts'],
                    i=r['istd_kcounts'], kilo_i=True, integ=r['mode'], rev=r['revision'],
                    void=r['state'])
    elif layout == 'i_txt':
        for line in open(path, encoding='utf-8'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            fields = {}
            for part in line.split(';'):
                if '=' in part:
                    k, v = part.split('=', 1)
                    fields[k.strip()] = v.strip()
            rec(inj=fields.get('INJ'), run=fields.get('RUN'), seq=fields.get('SEQ'),
                kind=fields.get('TYPE'), ref=fields.get('REF'), dil=fields.get('DF'),
                a=fields.get('AREA'), i=fields.get('ISAREA'), integ=fields.get('MODE'),
                rev=fields.get('REV'), void=fields.get('ST'))
    elif layout == 'i_csvsemi':
        for r in read_csv_rows(path, ';'):
            rec(inj=r['Injection'], run=r['Batch'], seq=r['Pos'], kind=r['Type'],
                ref=r['Sample'], dil=r['Dilution'], a=r['Area (kcounts)'],
                i=r['IS Area (kcounts)'], kilo_a=True, kilo_i=True, comma=True,
                integ=r['Integration'], rev=r['Rev'], void=r['Valid'])
    elif layout == 'i_tsv2':
        for r in read_csv_rows(path, '\t'):
            rec(inj=r['injection'], run=r['run'], seq=r['seq'], kind=r['type'], ref=r['ref'],
                dil=r['df'], a=r['analyte_area'], i=r['is_area'], integ=r['integration'],
                rev=r['revision'], void=r['status'])
    elif layout == 'i_jsonl2':
        for line in open(path, encoding='utf-8'):
            if not line.strip():
                continue
            d = json.loads(line)
            rec(inj=d['inj'], run=d['run'], seq=d['seq'], kind=d['type'], ref=d['ref'],
                dil=d['df'], a=d['a'], i=d['is'], integ=d['mode'], rev=d['rev'],
                void=d['st'])
    elif layout == 'i_psv2':
        for r in read_csv_rows(path, '|'):
            rec(inj=r['inj'], run=r['run'], seq=r['pos'], kind=r['t'], ref=r['ref'],
                dil=r['df'], a=r['area'], i=r['is_area'], integ=r['integ'], rev=r['rev'],
                void=r['keep'])
    else:
        raise ValueError('unknown layout %s' % layout)
    return out


STD_LEVEL_RE = re.compile(r'^(?:CS|STD[-]|L|CAL\s*)[-\s]*(\d)$')


def norm_level(ref):
    """Reference token to a standard level (CSk) or QC level (LQC/MQC/HQC/DQC)."""
    s = str(ref).strip().upper()
    if s in ('LQC', 'QC-L', 'LOW', 'QCL'):
        return 'LQC'
    if s in ('MQC', 'QC-M', 'MID', 'QCM'):
        return 'MQC'
    if s in ('HQC', 'QC-H', 'HIGH', 'QCH'):
        return 'HQC'
    if s in ('DQC', 'QC-D', 'DIL', 'QCD'):
        return 'DQC'
    m = STD_LEVEL_RE.match(s)
    if m:
        return 'CS' + m.group(1)
    return None

def serial_to_date(serial, date1904):
    n = int(serial)
    base = datetime(1904, 1, 1) if date1904 else datetime(1899, 12, 30)
    return base + timedelta(days=n)


# --------------------------------------------------------------------------- #
# minimal YAML reader (block style subset)
# --------------------------------------------------------------------------- #

def _yaml_scalar(s):
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        return s[1:-1]
    return s


def _indent(line):
    return len(line) - len(line.lstrip(' '))


def _parse_yaml_block(lines, i, indent):
    if i < len(lines) and re.match(r'^\s*-\s', lines[i]) and _indent(lines[i]) >= indent:
        items = []
        while i < len(lines) and re.match(r'^\s*-\s', lines[i]) and _indent(lines[i]) >= indent:
            ind = _indent(lines[i])
            rest = lines[i][ind + 2:]
            i += 1
            if rest.strip() and ':' in rest and not rest.strip().startswith(('[', '{', '"', "'")):
                sub = [rest]
                while i < len(lines) and not re.match(r'^\s*-\s', lines[i]) and _indent(lines[i]) > ind:
                    sub.append(lines[i])
                    i += 1
                pad = ' ' * (ind + 2)
                val, _ = _parse_yaml_block([pad + s for s in sub], 0, ind + 2)
                items.append(val)
            else:
                items.append(_yaml_scalar(rest))
        return items, i
    mapping = {}
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.strip().startswith('#'):
            i += 1
            continue
        ind = _indent(line)
        if ind < indent:
            break
        m = re.match(r'^([^:]+):\s*(.*)$', line)
        if not m:
            i += 1
            continue
        key = m.group(1).strip()
        rest = m.group(2).strip()
        if rest == '':
            nxt = lines[i + 1] if i + 1 < len(lines) else ''
            if nxt.strip() and (re.match(r'^\s*-\s', nxt) or _indent(nxt) > ind):
                val, i2 = _parse_yaml_block(lines, i + 1, _indent(lines[i + 1]))
                mapping[key] = val
                i = i2
            else:
                mapping[key] = None
                i += 1
        else:
            mapping[key] = _yaml_scalar(rest)
            i += 1
    return mapping, i


def read_yaml(path):
    text = open(path, encoding='utf-8').read()
    cleaned = []
    for l in text.replace('\r\n', '\n').split('\n'):
        if l.strip().startswith('#'):
            continue
        cleaned.append(l)
    val, _ = _parse_yaml_block(cleaned, 0, 0)
    return val


def read_csv_rows(path, delim=','):
    with open(path, newline='', encoding='utf-8') as f:
        return [dict((k.strip(), (v or '').strip()) for k, v in r.items())
                for r in csv.DictReader(f, delimiter=delim)]

# --------------------------------------------------------------------------- #
# site calendar and instants
# --------------------------------------------------------------------------- #

def parse_offset(s):
    s = str(s).strip()
    m = re.match(r'^([+-])(\d{2}):?(\d{2})$', s)
    if not m:
        raise ValueError('bad utc offset %r' % s)
    sign = 1 if m.group(1) == '+' else -1
    return sign * timedelta(hours=int(m.group(2)), minutes=int(m.group(3)))


def parse_naive(s):
    s = str(s).strip()
    if not s:
        return None
    for f in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%dT%H:%M:%S',
              '%Y-%m-%dT%H:%M', '%Y-%m-%d'):
        try:
            return datetime.strptime(s, f)
        except ValueError:
            continue
    raise ValueError('bad wall clock %r' % s)


def parse_instant(s):
    """ISO 8601 with offset (or Z) to an aware UTC datetime."""
    s = str(s).strip()
    if not s:
        return None
    if s.endswith('Z') or s.endswith('z'):
        s = s[:-1] + '+00:00'
    dt = None
    try:
        dt = datetime.fromisoformat(s)
    except Exception:
        for f in ('%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M%z', '%Y-%m-%d %H:%M:%S%z',
                  '%Y-%m-%d %H:%M%z'):
            try:
                dt = datetime.strptime(s, f)
                break
            except ValueError:
                continue
    if dt is None:
        raise ValueError('bad instant %r' % s)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def iso_utc(dt):
    if dt is None:
        return ''
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')


class Calendar(object):
    def __init__(self, base_offset, transitions):
        self.base = parse_offset(base_offset)
        self.trans = sorted(transitions, key=lambda t: t[0])

    def offset_at(self, inst):
        off = self.base
        for at, o in self.trans:
            if inst >= at:
                off = o
            else:
                break
        return off

    def wall_to_instant(self, dt):
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        offs = [self.base] + [o for _at, o in self.trans]
        candidates = []
        for o in offs:
            inst = (dt - o).replace(tzinfo=timezone.utc)
            if self.offset_at(inst) == o:
                candidates.append(inst)
        if candidates:
            return min(candidates)
        for i, (at, o) in enumerate(self.trans):
            prev = self.trans[i - 1][1] if i > 0 else self.base
            if (dt - prev).replace(tzinfo=timezone.utc) >= at and \
                    (dt - o).replace(tzinfo=timezone.utc) < at:
                return (dt - prev).replace(tzinfo=timezone.utc)
        return (dt - self.base).replace(tzinfo=timezone.utc)


# --------------------------------------------------------------------------- #
# calibration mathematics
# --------------------------------------------------------------------------- #

def solve_linear_system(mat, rhs):
    """Exact solve of a small square system with Fractions; None if singular."""
    n = len(rhs)
    m = [row[:] + [rhs[i]] for i, row in enumerate(mat)]
    for col in range(n):
        piv = None
        for r in range(col, n):
            if m[r][col] != 0:
                piv = r
                break
        if piv is None:
            return None
        m[col], m[piv] = m[piv], m[col]
        pv = m[col][col]
        m[col] = [v / pv for v in m[col]]
        for r in range(n):
            if r != col and m[r][col] != 0:
                factor = m[r][col]
                m[r] = [a - factor * b for a, b in zip(m[r], m[col])]
    return [m[i][n] for i in range(n)]


def weighted_fit(points, model, weighting):
    """Exact weighted least squares fit. points: [(Fraction x, Fraction y)]."""
    pmax = 1 if model == 'linear' else 2
    ws = []
    for x, _y in points:
        if weighting == '1/x^2':
            w = Fraction(1) / (x * x)
        elif weighting == '1/x':
            w = Fraction(1) / x
        else:
            w = Fraction(1)
        ws.append(w)
    dim = pmax + 1
    mat = [[Fraction(0)] * dim for _ in range(dim)]
    rhs = [Fraction(0)] * dim
    for (x, y), w in zip(points, ws):
        xp = [Fraction(1)]
        for _i in range(1, dim):
            xp.append(xp[-1] * x)
        for p in range(dim):
            for q in range(dim):
                mat[p][q] += w * xp[p] * xp[q]
            rhs[p] += w * xp[p] * y
    sol = solve_linear_system(mat, rhs)
    if sol is None:
        return None
    if model == 'linear':
        return {'a': sol[0], 'b': sol[1], 'c': None}
    return {'a': sol[0], 'b': sol[1], 'c': sol[2]}


def back_calculate(response, model, coefs):
    """Reading x for a response y with the rounded coefficients (Decimals)."""
    a = to_dec(coefs['a'])
    b = to_dec(coefs['b'])
    c = to_dec(coefs['c']) if coefs.get('c') is not None else None
    y = to_dec(response)
    if model == 'linear':
        if b == 0:
            return None
        return (y - a) / b
    rad = b * b + 4 * c * (y - a)
    if rad < 0:
        return None
    s = rad.sqrt()
    denom = b + s
    if denom == 0:
        return None
    return 2 * (y - a) / denom


def deviation_pct(reading, nominal):
    if nominal == 0:
        return None
    return Decimal(100) * (reading - nominal) / nominal


def ols_regression(pts):
    """OLS of y on x over pts [(x, y)] -> (slope, intercept, r2, n)."""
    n = len(pts)
    sx = sum(p[0] for p in pts)
    sy = sum(p[1] for p in pts)
    sxx = sum(p[0] * p[0] for p in pts)
    sxy = sum(p[0] * p[1] for p in pts)
    syy = sum(p[1] * p[1] for p in pts)
    denom = n * sxx - sx * sx
    if denom == 0:
        return None
    slope = (n * sxy - sx * sy) / denom
    intercept = (sy - slope * sx) / n
    sst = n * syy - sy * sy
    sse = syy - (intercept * sy + slope * sxy)
    if sst == 0:
        r2 = 1.0 if abs(sse) < 1e-300 else 0.0
    else:
        r2 = 1.0 - sse / sst
    return slope, intercept, r2, n


# --------------------------------------------------------------------------- #
# alias resolution
# --------------------------------------------------------------------------- #

def chain_resolve(token, mapping, canonical):
    """Resolve a token through `mapping` until it reaches a member of `canonical`."""
    cur = str(token).strip().upper()
    seen = set()
    while True:
        if cur in canonical:
            return cur
        if cur in seen:
            return None
        seen.add(cur)
        nxt = mapping.get(cur)
        if not nxt:
            return None
        cur = nxt


def build_chain_mapping(pairs):
    m = {}
    for token, target in pairs:
        m[str(token).strip().upper()] = str(target).strip().upper()
    return m



# --------------------------------------------------------------------------- #
# analysis
# --------------------------------------------------------------------------- #

NORM_PARAM = {'cmax': 'Cmax', 'auclast': 'AUClast', 'aucinf': 'AUCinf',
              'auc_last': 'AUClast', 'auc_inf': 'AUCinf', 'lambda_z': 'lambda_z',
              'halflife': 'half_life', 'half_life': 'half_life', 'tmax': 'Tmax',
              'clast': 'Clast', 'tlast': 'Tlast'}


def norm_param_key(name):
    k = re.sub(r'[^a-z0-9]', '', str(name).lower())
    if k in NORM_PARAM:
        return NORM_PARAM[k]
    if k == 'auclast':
        return 'AUClast'
    if k == 'aucinf':
        return 'AUCinf'
    if k == 'cmax':
        return 'Cmax'
    return str(name)


def pick_table(tables, tid, keyword=None):
    """Choose a memo table by id, skipping withdrawn / reference-only tables."""
    t = tables.get(tid)
    if t:
        title = t['title'].upper()
        if 'WITHDRAWN' not in title and 'REFERENCE ONLY' not in title:
            return tid
    if keyword:
        for k in tables:
            ttl = tables[k]['title'].upper()
            if 'WITHDRAWN' in ttl or 'REFERENCE ONLY' in ttl:
                continue
            if keyword in ttl:
                return k
    return tid if tid in tables else None


def median3(vals):
    xs = sorted(vals)
    return xs[1]


def tube_info(subject, period, nominal, status):
    def to_period(p):
        try:
            return int(str(p).strip())
        except (TypeError, ValueError):
            return None
    nom = str(nominal or '').strip().upper()
    if nom in ('PRE', '0', '0.0', '0.00'):
        nomval = Decimal(0)
    elif nom in ('UNS', 'UNSHEDULED', 'UNSCHEDULED', ''):
        nomval = None
    else:
        try:
            nomval = Decimal(nom)
        except Exception:
            nomval = None
    return {
        'subject_token': str(subject or '').strip(),
        'period': to_period(period),
        'nominal': nomval,
        'status': str(status or '').strip().upper(),
    }


def load_profile_and_memo(b, data_dir):
    """Analysis profile and governance memo (H1)."""
    def p(name):
        return os.path.join(data_dir, name)

    prof_path = None
    for cand in ('analysis_profile_be.yml', 'analysis_profile_be.yaml'):
        if os.path.exists(p(cand)):
            prof_path = p(cand)
            break
    if prof_path is None:
        raise SystemExit('analysis profile not found in %s' % data_dir)
    profile = read_yaml(prof_path)
    b['profile'] = profile
    b['study_id'] = str(profile.get('study_id', '')).strip()
    study = b['study_id']
    b['analytes'] = [str(a).strip().upper() for a in (profile.get('analytes') or [])]
    b['pivotal'] = [str(a).strip().upper() for a in (profile.get('pivotal_analytes') or [])]
    b['parameters'] = [str(x).strip() for x in (profile.get('parameters') or [])]
    b['nominal_sheet'] = str(profile.get('nominal_sheet', '')).strip()
    b['alpha'] = to_dec(profile.get('alpha', '0.05'))
    b['be_lower'] = to_dec(profile.get('be_lower_pct', '80'))
    b['be_upper'] = to_dec(profile.get('be_upper_pct', '125'))
    b['lz_min_points'] = int(to_dec(profile.get('lambda_z_min_points', '3')))
    b['lz_tol'] = to_dec(profile.get('lambda_z_adj_r2_tolerance', '0.0001'))
    b['extrap_pct'] = to_dec(profile.get('extrap_limit_pct', '20'))
    b['carryover_pct'] = to_dec(profile.get('carryover_limit_pct', '5'))
    b['emesis_factor'] = to_dec(profile.get('emesis_window_factor', '2'))
    b['isr_pct'] = to_dec(profile.get('isr_limit_pct', '20'))
    b['scope'] = [str(s).strip().upper() for s in (profile.get('subjects_in_scope') or [])]
    b['scope_set'] = set(b['scope'])

    memo_path = p('ba_stat_governance_memo.pdf')
    tables, torder = (read_memo(memo_path) if os.path.exists(memo_path) else ({}, []))
    b['memo_tables'] = tables
    b['conventions_table'] = 'P-1'
    b['method_table'] = 'M-2'
    b['t_table'] = 'T-1'

    tid = pick_table(tables, 'P-1', 'ANALYSIS CONVENTIONS')
    conv = {}
    if tid:
        for r in table_records(tables, tid):
            conv[(r.get('parameter') or '').strip().lower()] = (r.get('value') or '').strip()
    b['conventions'] = conv

    tid = pick_table(tables, 'M-2', 'BIOANALYTICAL METHOD PARAMETERS')
    if tid:
        b['method_table'] = tid
    b['methods'] = {}
    if tid:
        for r in table_records(tables, tid):
            key = (r.get('analyte') or '').strip().upper()
            if not key:
                continue
            b['methods'][key] = {
                'model': (r.get('model') or 'linear').strip().lower(),
                'weighting': (r.get('weighting') or '1/x').strip().lower(),
                'std_limit_pct': to_dec(r.get('std_limit_pct') or '15'),
                'lloq_std_limit_pct': to_dec(r.get('lloq_std_limit_pct') or '20'),
                'qc_limit_pct': to_dec(r.get('qc_limit_pct') or '15'),
                'dqc_limit_pct': to_dec(r.get('dqc_limit_pct') or '15'),
                'min_std_fraction': Fraction(str(r.get('min_std_fraction') or '0')),
                'min_levels': int(to_dec(r.get('min_levels') or '0')),
                'min_qc_fraction': Fraction(str(r.get('min_qc_fraction') or '0')),
                'min_qc_level_fraction': (None if (r.get('min_qc_level_fraction') or '')
                                          .strip().lower() in ('none', '')
                                          else Fraction(str(r.get('min_qc_level_fraction')))),
                'unit': (r.get('unit') or '').strip(),
            }

    tid = pick_table(tables, 'C-1', 'MANUAL INTEGRATION REASON CODES')
    b['integ_codes'] = set()
    if tid:
        for r in table_records(tables, tid):
            if (r.get('allowed') or '').strip().upper() == 'Y':
                b['integ_codes'].add((r.get('code') or '').strip().upper())

    tid = pick_table(tables, 'C-2', 'ASSIGNABLE CAUSES')
    b['std_excl_codes'] = set()
    if tid:
        for r in table_records(tables, tid):
            if (r.get('allowed') or '').strip().upper() == 'Y':
                b['std_excl_codes'].add((r.get('code') or '').strip().upper())

    tid = pick_table(tables, 'E-1', 'EMESIS PREFERRED TERMS')
    b['emesis_pts'] = set()
    if tid:
        for r in table_records(tables, tid):
            if (r.get('counts_as_emesis') or '').strip().upper() == 'Y':
                b['emesis_pts'].add((r.get('preferred_term') or '').strip().upper())

    tid = pick_table(tables, 'T-1', 'STUDENT T QUANTILES')
    if tid:
        b['t_table'] = tid
    ttab = {}
    if tid:
        for r in table_records(tables, tid):
            df = (r.get('df') or '').strip()
            if not df:
                continue
            row = {}
            for k, v in r.items():
                m = re.match(r'^p\s*=\s*(.*)$', str(k))
                if m:
                    row[Decimal(m.group(1))] = to_dec(v)
            if row:
                ttab[int(to_dec(df))] = row
    b['t_quantiles'] = ttab

    tid = pick_table(tables, 'R-1', 'RULINGS')
    b['rulings'] = []
    if tid:
        for r in table_records(tables, tid):
            b['rulings'].append({
                'id': (r.get('ruling_id') or '').strip(),
                'study': (r.get('study') or '').strip(),
                'action': (r.get('action') or '').strip().upper(),
                'target': (r.get('target') or '').strip(),
                'status': (r.get('status') or '').strip().upper(),
                'note': (r.get('note') or '').strip(),
            })
    return b


def load_workbook(b, data_dir):
    """Workbook sheets: RunPlan, nominal, QC lots, Randomization (H1, H4)."""
    def p(name):
        return os.path.join(data_dir, name)

    wb_path = p('bioanalytical_workbook_v3.xlsx')
    if not os.path.exists(wb_path):
        for cand in sorted(os.listdir(data_dir)):
            if cand.lower().endswith('.xlsx'):
                wb_path = p(cand)
                break
    sheets, snames, date1904 = read_xlsx(wb_path)
    b['date1904'] = date1904
    b['runplan'] = []
    hdr, rows = sheet_table(sheets.get('RunPlan', []), 'run_id')
    if hdr:
        hidx = dict((h.strip().lower(), i) for i, h in enumerate(hdr))
        for r in rows:
            def g(name, rr=r, hh=hidx):
                i = hh.get(name)
                return rr[i] if i is not None and i < len(rr) else ''
            b['runplan'].append({
                'run_id': g('run_id').strip(),
                'study': g('study').strip(),
                'analyte': g('analyte').strip().upper(),
                'run_type': g('run_type').strip().upper(),
                'cal_lot': g('cal_lot').strip(),
                'qc_lot': g('qc_lot').strip(),
                'analysis_date': g('analysis_date').strip(),
            })
    b['nominal'] = {}
    nsheet = b['nominal_sheet']
    if nsheet in sheets:
        hdr, rows = sheet_table(sheets[nsheet], 'lot')
        if hdr:
            hidx = dict((h.strip().lower(), i) for i, h in enumerate(hdr))
            for r in rows:
                def g(name, rr=r, hh=hidx):
                    i = hh.get(name)
                    return rr[i] if i is not None and i < len(rr) else ''
                b['nominal'][(g('lot').strip().upper(),
                             (g('level') or '').strip().upper())] = to_dec(g('certified'))
    b['qclots'] = {}
    hdr, rows = sheet_table(sheets.get('QCLots', []), 'lot')
    if hdr:
        hidx = dict((h.strip().lower(), i) for i, h in enumerate(hdr))
        for r in rows:
            def g(name, rr=r, hh=hidx):
                i = hh.get(name)
                return rr[i] if i is not None and i < len(rr) else ''
            b['qclots'][(g('lot').strip().upper(),
                         (g('level') or '').strip().upper())] = to_dec(g('certified'))
    b['randomization'] = []
    hdr, rows = sheet_table(sheets.get('Randomization', []), 'subject')
    if hdr:
        hidx = dict((h.strip().lower(), i) for i, h in enumerate(hdr))
        for r in rows:
            subj = (r[0] or '').strip()
            if not subj:
                continue
            def g(name, rr=r, hh=hidx):
                i = hh.get(name)
                return rr[i] if i is not None and i < len(rr) else ''
            b['randomization'].append({'subject': subj,
                                       'sequence': (g('sequence') or '').strip().upper()})
    b['rand_subjects'] = set(r['subject'].strip().upper() for r in b['randomization'])
    b['sequence'] = dict((r['subject'].strip().upper(), r['sequence'])
                         for r in b['randomization'])
    return b


def load_registers(b, data_dir):
    """Catalog, alias register, audit trail, requests and manifests."""
    def p(name):
        return os.path.join(data_dir, name)
    study = b['study_id']

    cat_path = p('ingest_catalog_be.json')
    catalog = json.load(open(cat_path)) if os.path.exists(cat_path) else {'shards': []}
    b['catalog'] = catalog
    b['shards'] = [s for s in (catalog.get('shards') or []) if s.get('active')]
    b['inactive'] = [s.get('file') for s in (catalog.get('shards') or [])
                      if not s.get('active')]

    reg_path = p('entity_alias_register.sqlite')
    b['run_alias'] = {}
    b['known_runs'] = set()
    b['subject_alias'] = {}
    if os.path.exists(reg_path):
        con = sqlite3.connect(reg_path)
        for tok, rid in con.execute('SELECT token, run_id FROM run_alias'):
            tok = str(tok).strip().upper()
            rid = str(rid).strip().upper()
            b['run_alias'].setdefault(tok, rid)
            b['known_runs'].add(rid)
        for tok, sid, st in con.execute('SELECT token, subject_id, study FROM subject_alias'):
            if (st or '').strip().upper() != study.upper():
                continue
            b['subject_alias'].setdefault(str(tok).strip().upper(),
                                          str(sid).strip().upper())
        con.close()
    for r in b['runplan']:
        if r['run_id']:
            b['known_runs'].add(r['run_id'].strip().upper())

    b['audit'] = defaultdict(list)
    audit_path = p('integration_audit_trail.db')
    if os.path.exists(audit_path):
        con = sqlite3.connect(audit_path)
        cols = [d[1] for d in con.execute('PRAGMA table_info(audit_entry)')]
        sel = ', '.join('"%s"' % c for c in cols)
        for row in con.execute('SELECT %s FROM audit_entry' % sel):
            d = dict(zip(cols, row))
            b['audit'][(str(d.get('injection_ref') or '').strip().upper(),
                        int(d.get('revision') or 0))].append(
                (str(d.get('ts') or '').strip(),
                 str(d.get('status') or '').strip().upper(),
                 str(d.get('reason_code') or '').strip().upper()))
        con.close()

    b['std_requests'] = []
    if os.path.exists(p('std_exclusion_requests.jsonl')):
        for line in open(p('std_exclusion_requests.jsonl'), encoding='utf-8'):
            if line.strip():
                b['std_requests'].append(json.loads(line))

    b['reassay'] = []
    if os.path.exists(p('reassay_request_log.csv')):
        b['reassay'] = read_csv_rows(p('reassay_request_log.csv'))

    b['tubes'] = {}
    if os.path.exists(p('tube_manifest_main.csv')):
        for r in read_csv_rows(p('tube_manifest_main.csv')):
            tid = (r.get('tube_id') or r.get('tube') or '').strip().upper()
            if tid:
                b['tubes'][tid] = tube_info(r.get('subject'), r.get('period'),
                                           r.get('nominal_h'), r.get('status'))
    if os.path.exists(p('tube_manifest_addendum.yaml')):
        add = read_yaml(p('tube_manifest_addendum.yaml')) or {}
        for r in (add.get('tubes') or []):
            tid = str(r.get('tube') or '').strip().upper()
            if tid and tid not in b['tubes']:
                b['tubes'][tid] = tube_info(r.get('subject'), r.get('period'),
                                           r.get('nominal_h'), r.get('status'))

    b['relabel'] = {}
    b['relabel_rows'] = []
    if os.path.exists(p('tube_relabel_journal.xml')):
        root = ET.parse(p('tube_relabel_journal.xml')).getroot()
        jstudy = (root.get('study') or study).strip().upper()
        for e in root.findall('relabel'):
            rstudy = (e.get('study') or jstudy).strip().upper()
            row = {
                'old': (e.get('old') or '').strip().upper(),
                'new': (e.get('new') or '').strip().upper(),
                'status': (e.get('status') or '').strip().upper(),
            }
            b['relabel_rows'].append(row)
            if rstudy == study.upper() and row['status'] == 'ACTIVE' and row['new']:
                b['relabel'][row['new']] = row['old']

    # subject of each tube (H4 resolution, H11 scope)
    b['tube_subject'] = {}
    for tid, info in b['tubes'].items():
        subj = chain_resolve(info['subject_token'], b['subject_alias'], b['rand_subjects'])
        b['tube_subject'][tid] = subj
    return b


def load_events(b, data_dir):
    """Dose logs, draw-time logs, corrections, calendar, AEs, disposition."""
    def p(name):
        return os.path.join(data_dir, name)

    b['dose'] = {}
    b['dose_tokens'] = set()
    if os.path.exists(p('dose_admin_p1.csv')):
        for r in read_csv_rows(p('dose_admin_p1.csv')):
            if (r.get('subject') or '').strip():
                b['dose_tokens'].add(r['subject'].strip().upper())
            if (r.get('event') or '').strip().upper() != 'DOSE':
                continue
            subj = chain_resolve(r.get('subject'), b['subject_alias'], b['rand_subjects'])
            try:
                per = int(str(r.get('period') or '').strip())
            except (TypeError, ValueError):
                per = None
            wall = parse_naive(r.get('local_time'))
            if subj is None or per is None or wall is None:
                continue
            b['dose'].setdefault((subj, per), ('wall', wall))
    if os.path.exists(p('dose_admin_p2.xml')):
        root = ET.parse(p('dose_admin_p2.xml')).getroot()
        rperiod = root.get('period')
        for e in root.findall('event'):
            if (e.get('subject') or '').strip():
                b['dose_tokens'].add(e.get('subject').strip().upper())
            if (e.get('type') or '').strip().upper() != 'DOSE':
                continue
            subj = chain_resolve(e.get('subject'), b['subject_alias'], b['rand_subjects'])
            per = e.get('period') or rperiod
            try:
                per = int(str(per).strip())
            except (TypeError, ValueError):
                per = None
            inst = parse_instant(e.get('at'))
            if subj is None or per is None or inst is None:
                continue
            b['dose'].setdefault((subj, per), ('iso', inst))
    b['dose_periods'] = set(per for _s, per in b['dose'])

    if os.path.exists(p('site_calendar.yml')):
        cy = read_yaml(p('site_calendar.yml')) or {}
        trans = []
        for t in (cy.get('transitions') or []):
            if not isinstance(t, dict):
                continue
            trans.append((parse_instant(t.get('at_utc')),
                          parse_offset(t.get('offset_after'))))
        b['calendar'] = Calendar(cy.get('base_offset', '+00:00'), trans)
    else:
        b['calendar'] = Calendar('+00:00', [])

    b['draw_raw'] = {}
    b['draw_tokens'] = set()
    if os.path.exists(p('draw_times_g1.tsv')):
        for r in read_csv_rows(p('draw_times_g1.tsv'), '\t'):
            if (r.get('subject') or '').strip():
                b['draw_tokens'].add(r['subject'].strip().upper())
            tid = (r.get('tube') or '').strip().upper()
            if tid and tid not in b['draw_raw']:
                b['draw_raw'][tid] = ('wall', (r.get('drawn_local') or '').strip())
    if os.path.exists(p('draw_times_g2.jsonl')):
        for line in open(p('draw_times_g2.jsonl'), encoding='utf-8'):
            if not line.strip():
                continue
            d = json.loads(line)
            if str(d.get('subj') or '').strip():
                b['draw_tokens'].add(str(d['subj']).strip().upper())
            tid = str(d.get('tube') or '').strip().upper()
            if tid and tid not in b['draw_raw']:
                b['draw_raw'][tid] = ('iso', d.get('drawn_at'))
    b['corrections'] = defaultdict(list)
    if os.path.exists(p('draw_time_corrections.ndjson')):
        for line in open(p('draw_time_corrections.ndjson'), encoding='utf-8'):
            if not line.strip():
                continue
            d = json.loads(line)
            if str(d.get('field') or '').strip().lower() != 'drawn_local':
                continue
            if str(d.get('status') or '').strip().upper() != 'POSTED':
                continue
            tid = str(d.get('tube') or '').strip().upper()
            action = str(d.get('action') or 'SET').strip().upper()
            if action not in ('SET', 'REVERSE'):
                continue
            b['corrections'][tid].append({
                'seq': int(d.get('seq')),
                'action': action,
                'reverses': (int(d.get('reverses'))
                             if d.get('reverses') not in (None, '') else None),
                'value': ('' if d.get('value') is None else str(d.get('value')).strip()),
            })

    b['aes'] = []
    ae_path = p('ae_listing.db')
    if os.path.exists(ae_path):
        con = sqlite3.connect(ae_path)
        cols = [d[1] for d in con.execute('PRAGMA table_info(ae_events)')]
        sel = ', '.join('"%s"' % c for c in cols)
        for row in con.execute('SELECT %s FROM ae_events' % sel):
            d = dict(zip(cols, row))
            if (str(d.get('study') or '').strip().upper() != b['study_id'].upper()):
                continue
            subj = chain_resolve(d.get('subject'), b['subject_alias'], b['rand_subjects'])
            try:
                per = int(str(d.get('period') or '').strip())
            except (TypeError, ValueError):
                per = None
            onset = (parse_naive(d.get('onset_local'))
                     if str(d.get('onset_local') or '').strip() else None)
            b['aes'].append({
                'subject': subj,
                'subject_token': str(d.get('subject') or '').strip(),
                'period': per,
                'pt': str(d.get('pt') or '').strip().upper(),
                'onset': onset,
                'ae_id': d.get('ae_id'),
            })
        con.close()

    b['disposition'] = []
    b['disposition_tokens'] = set()
    if os.path.exists(p('subject_disposition.psv')):
        for r in read_csv_rows(p('subject_disposition.psv'), '|'):
            tok = (r.get('subject') or '').strip()
            if tok:
                b['disposition_tokens'].add(tok.upper())
            subj = chain_resolve(r.get('subject'), b['subject_alias'], b['rand_subjects'])
            b['disposition'].append({
                'subject': subj,
                'subject_token': tok,
                'event': (r.get('event') or '').strip().upper(),
                'period': (r.get('period') or '').strip(),
            })

    b['lab_status'] = {}
    if os.path.exists(p('run_status_dashboard.csv')):
        for r in read_csv_rows(p('run_status_dashboard.csv')):
            rid = (r.get('run_id') or '').strip().upper()
            if rid:
                b['lab_status'][rid] = (r.get('lab_status') or '').strip()

    b['published'] = []
    if os.path.exists(p('be_report_published.csv')):
        b['published'] = read_csv_rows(p('be_report_published.csv'))
    b['published_stats'] = {}
    if os.path.exists(p('be_statistics_published.json')):
        d = json.load(open(p('be_statistics_published.json'), encoding='utf-8'))
        stack = [d]
        while stack:
            o = stack.pop()
            if isinstance(o, dict):
                if 'analyte' in o and 'parameter' in o:
                    b['published_stats'][(str(o['analyte']).strip().upper(),
                                           norm_param_key(o['parameter']))] = o
                else:
                    stack.extend(o.values())
            elif isinstance(o, list):
                stack.extend(o)
    return b


def load_corpus(data_dir):
    b = {'data_dir': data_dir}
    load_profile_and_memo(b, data_dir)
    load_workbook(b, data_dir)
    load_registers(b, data_dir)
    load_events(b, data_dir)
    return b


# --------------------------------------------------------------------------- #
# H2/H3 records, revisions and voids
# --------------------------------------------------------------------------- #

GENERIC_KINDS = {'STD': 'STD', 'QC': 'QC', 'DQC': 'DQC', 'UNK': 'UNK',
                 'BLANK': 'BLANK', 'ZERO': 'ZERO'}
NOT_VOID = {'FALSE', '0', 'OK', 'VALID', 'ACTIVE', 'KEEP', 'V', 'Y', 'A', 'LIVE', 'L'}
DEFAULT_METHOD = {
    'model': 'linear', 'weighting': '1/x', 'std_limit_pct': Decimal(15),
    'lloq_std_limit_pct': Decimal(20), 'qc_limit_pct': Decimal(15),
    'dqc_limit_pct': Decimal(15), 'min_std_fraction': Fraction(0),
    'min_levels': 0, 'min_qc_fraction': Fraction(0), 'min_qc_level_fraction': None,
    'unit': ''}


def resolve_tube(b, token):
    """Resolve a sample token through the ACTIVE relabels (new -> old)."""
    cur = str(token or '').strip().upper()
    seen = set()
    while cur and cur not in seen:
        seen.add(cur)
        nxt = b['relabel'].get(cur)
        if not nxt:
            break
        cur = nxt
    return cur


def resolve_records(b):
    records = []
    rows_read = 0
    for shard in b['shards']:
        layout = shard.get('layout')
        path = os.path.join(b['data_dir'], shard['file'])
        kmap = KIND_TOKENS.get(layout, {})
        for raw in read_feed(path, layout):
            ktok = str(raw.get('kind') or '').strip().upper()
            kind = kmap.get(ktok, GENERIC_KINDS.get(ktok))
            vt = str(raw.get('void') or '').strip().upper()
            is_void = (vt in VOID_TOKENS) and (vt not in NOT_VOID)
            comma = bool(raw.get('comma'))
            rec = {
                'inj': str(raw.get('inj') or '').strip().upper(),
                'run_token': str(raw.get('run') or '').strip(),
                'seq': int(str(raw.get('seq') or '0').strip() or 0),
                'kind': kind,
                'ref': str(raw.get('ref') or '').strip(),
                'dil': _dilution(raw.get('dil')),
                'a_area': _kv_int(raw.get('a'), bool(raw.get('kilo_a')), comma),
                'i_area': _kv_int(raw.get('i'), bool(raw.get('kilo_i')), comma),
                'integ': str(raw.get('integ') or '').strip().upper(),
                'rev': int(str(raw.get('rev') or '0').strip() or 0),
                'void': is_void,
                'shard': shard['file'],
                'layout': layout,
                'manual': str(raw.get('integ') or '').strip().upper() in MANUAL_TOKENS,
            }
            records.append(rec)
            rows_read += 1
    b['records'] = records
    b['rows_read'] = rows_read

    groups = defaultdict(list)
    for rec in records:
        groups[(rec['inj'], rec['rev'])].append(rec)
    b['duplicate_copies'] = sum(len(v) - 1 for v in groups.values())

    inadmissible_manual = 0
    admissible = defaultdict(set)
    inadmissible_groups = set()
    for (inj, rev), recs in groups.items():
        manual_recs = [r for r in recs if r['manual']]
        if manual_recs:
            ents = b['audit'].get((inj, rev)) or []
            ok = False
            if ents:
                latest = max(ents, key=lambda e: e[0])
                ok = latest[1] == 'APPROVED' and latest[2] in b['integ_codes']
            if not ok:
                inadmissible_manual += len(manual_recs)
            else:
                admissible[inj].add(rev)
                continue
        auto_recs = [r for r in recs if not r['manual']]
        if auto_recs:
            admissible[inj].add(rev)
    b['inadmissible_manual'] = inadmissible_manual

    effective = {}
    for inj, revs in admissible.items():
        if not revs:
            continue
        effective[inj] = max(revs)
    superseded = 0
    for (inj, rev), recs in groups.items():
        top = effective.get(inj)
        if top is None or rev >= top:
            continue
        for rec in recs:
            if not rec['manual']:
                superseded += 1
            else:
                ents = b['audit'].get((inj, rev)) or []
                ok = False
                if ents:
                    latest = max(ents, key=lambda e: e[0])
                    ok = latest[1] == 'APPROVED' and latest[2] in b['integ_codes']
                if ok:
                    superseded += 1
    b['superseded'] = superseded
    b['effective_rev'] = effective

    kept = {}
    voided = 0
    for inj, rev in effective.items():
        rec = groups[(inj, rev)][0]
        if rec['void']:
            voided += 1
        else:
            kept[inj] = rec
    b['voided'] = voided
    b['kept'] = kept
    b['effective_injections'] = len(kept)

    shard_eff = defaultdict(int)
    for inj, rev in effective.items():
        if inj not in kept:
            continue
        for rec in groups[(inj, rev)]:
            shard_eff[rec['shard']] += 1
    b['shard_effective'] = dict(shard_eff)

    b['inj_run'] = {}
    run_tokens = set()
    for inj, rec in kept.items():
        tok = rec['run_token'].strip().upper()
        run_tokens.add(tok)
        if tok in b['known_runs']:
            b['inj_run'][inj] = tok
        else:
            b['inj_run'][inj] = b['run_alias'].get(tok)
    b['run_tokens'] = run_tokens

    b['inj_tube'] = {}
    b['study_inj'] = set()
    tube_tokens = set()
    n_std = n_qc = n_bz = n_study = n_foreign = 0
    for inj, rec in kept.items():
        kind = rec['kind']
        if kind in ('QC', 'DQC'):
            n_qc += 1
        elif kind == 'STD':
            n_std += 1
        elif kind in ('BLANK', 'ZERO'):
            n_bz += 1
        elif kind == 'UNK':
            tube = resolve_tube(b, rec['ref'])
            b['inj_tube'][inj] = tube
            tube_tokens.add(rec['ref'].strip().upper())
            if tube in b['tubes']:
                n_study += 1
                b['study_inj'].add(inj)
            else:
                n_foreign += 1
        else:
            n_foreign += 1
    b['tube_tokens'] = tube_tokens
    b['n_standards'] = n_std
    b['n_qcs'] = n_qc
    b['n_blank_zero'] = n_bz
    b['n_study_samples'] = n_study
    b['n_foreign'] = n_foreign
    return records


# --------------------------------------------------------------------------- #
# H4 runs
# --------------------------------------------------------------------------- #

def compute_runs(b):
    study = b['study_id']
    runs = {}
    seen = set()
    for r in b['runplan']:
        if r['study'].strip().upper() != study.upper():
            continue
        rid = r['run_id'].strip().upper()
        if not rid or rid in seen:
            continue
        if r['analyte'] not in b['analytes']:
            continue
        seen.add(rid)
        try:
            serial = int(to_dec(r['analysis_date']))
        except Exception:
            continue
        runs[rid] = {
            'run_id': rid,
            'analyte': r['analyte'],
            'run_type': r['run_type'],
            'cal_lot': r['cal_lot'].strip().upper(),
            'qc_lot': r['qc_lot'].strip().upper(),
            'analysis_date': serial_to_date(serial, b['date1904']).date(),
            'method': b['methods'].get(r['analyte'], dict(DEFAULT_METHOD)),
        }
    order = sorted(runs, key=lambda rid: (runs[rid]['analysis_date'], rid))
    b['runs'] = runs
    b['run_order'] = order
    b['run_rank'] = dict((rid, i) for i, rid in enumerate(order))

    rejected = set()
    for r in b['rulings']:
        if r['status'] == 'IN FORCE' and r['action'] == 'REJECT_RUN':
            tok = r['target'].strip().upper()
            if tok in b['known_runs']:
                rejected.add(tok)
            else:
                rid = b['run_alias'].get(tok)
                if rid is not None:
                    rejected.add(rid)
    b['rejected_runs'] = rejected

    b['run_injections'] = defaultdict(list)
    for inj, rec in b['kept'].items():
        rid = b['inj_run'].get(inj)
        if rid is None or rid not in runs:
            continue
        b['run_injections'][rid].append(rec)
    for rid in runs:
        b['run_injections'][rid].sort(key=lambda rec: rec['seq'])
    return runs


# --------------------------------------------------------------------------- #
# H6-H10 calibration, QC and run acceptance
# --------------------------------------------------------------------------- #

def qclot_nominal(b, rid, level):
    run = b['runs'][rid]
    return b['qclots'].get((run['qc_lot'], level))


def std_entry(b, rid, rec):
    run = b['runs'][rid]
    level = norm_level(rec['ref'])
    nominal = b['nominal'].get((run['cal_lot'], level)) if level else None
    return {'rec': rec, 'level': level, 'nominal': nominal,
            'response': (Fraction(rec['a_area'], rec['i_area'])
                         if rec['i_area'] else None),
            'reading': None, 'dev': None, 'limit': None}


def round_coef(v):
    """H22.1: six significant digits."""
    return sig(v, 6)


def fit_run(b, rid):
    """H6/H7 calibration of one analysed run."""
    run = b['runs'][rid]
    method = run['method']
    model = method['model']
    weighting = method['weighting']
    ncoef = 2 if model == 'linear' else 3
    stds = [r for r in b['run_injections'][rid] if r['kind'] == 'STD']
    entries = [std_entry(b, rid, r) for r in stds]

    assignable = set()
    for req in b['std_requests']:
        if str(req.get('status') or '').strip().upper() != 'APPROVED':
            continue
        if str(req.get('code') or '').strip().upper() not in b['std_excl_codes']:
            continue
        inj = str(req.get('injection') or '').strip().upper()
        rtoken = str(req.get('run') or '').strip().upper()
        rid_req = (rtoken if rtoken in b['known_runs'] else b['run_alias'].get(rtoken))
        if rid_req != rid:
            continue
        for e in entries:
            if e['rec']['inj'] == inj:
                assignable.add(inj)
                break

    usable = [e for e in entries
              if e['rec']['inj'] not in assignable
              and e['nominal'] is not None and e['level'] is not None
              and e['response'] is not None]

    removed = []
    removed_ids = set()
    curve = None
    iterations = 0
    if len(usable) >= ncoef + 1:
        pts = [(Fraction(e['nominal']), e['response']) for e in usable]
        fit = weighted_fit(pts, model, weighting)
        iterations = 1
        if fit is not None:
            curve = {'a': round_coef(fit['a']), 'b': round_coef(fit['b']),
                     'c': (round_coef(fit['c']) if fit['c'] is not None else None)}
            while True:
                worst = None
                out = False
                for e in usable:
                    if e['rec']['inj'] in removed_ids:
                        continue
                    reading = back_calculate(e['response'], model, curve)
                    dev = (deviation_pct(reading, e['nominal'])
                           if reading is not None else None)
                    limit = (method['lloq_std_limit_pct'] if e['level'] == 'CS1'
                             else method['std_limit_pct'])
                    if dev is not None and abs(dev) > limit:
                        out = True
                    if dev is not None:
                        ratio = abs(dev) / limit
                        better = False
                        if worst is None:
                            better = True
                        elif ratio > worst[0]:
                            better = True
                        elif ratio == worst[0]:
                            if e['nominal'] > worst[1]['nominal']:
                                better = True
                            elif e['nominal'] == worst[1]['nominal'] and \
                                    e['rec']['seq'] > worst[1]['rec']['seq']:
                                better = True
                        if better:
                            worst = (ratio, e)
                if not out:
                    break
                if len(usable) - len(removed_ids) <= ncoef + 1:
                    break
                removed.append(worst[1])
                removed_ids.add(worst[1]['rec']['inj'])
                pts = [(Fraction(e['nominal']), e['response']) for e in usable
                       if e['rec']['inj'] not in removed_ids]
                fit2 = weighted_fit(pts, model, weighting)
                iterations += 1
                if fit2 is None:
                    break
                curve = {'a': round_coef(fit2['a']), 'b': round_coef(fit2['b']),
                         'c': (round_coef(fit2['c']) if fit2['c'] is not None else None)}

    retained_ids = set(e['rec']['inj'] for e in usable) - removed_ids
    for e in entries:
        e['limit'] = ((method['lloq_std_limit_pct'] if e['level'] == 'CS1'
                       else method['std_limit_pct']) if e['level'] else None)
        if curve is not None and e['response'] is not None:
            e['reading'] = back_calculate(e['response'], model, curve)
            e['dev'] = (deviation_pct(e['reading'], e['nominal'])
                        if (e['reading'] is not None and e['nominal'] is not None
                            and e['nominal'] != 0) else None)
        else:
            e['reading'] = None
            e['dev'] = None
    retained_nominals = [e['nominal'] for e in entries if e['rec']['inj'] in retained_ids]

    b['calibration'][rid] = {
        'run_id': rid,
        'analyte': run['analyte'],
        'model': model,
        'weighting': weighting,
        'cal_lot': run['cal_lot'],
        'coefficients': curve,
        'n_standards': len(stds),
        'n_assignable': len(assignable),
        'n_retained': len(retained_ids),
        'removed': [x['rec']['inj'] for x in removed],
        'iterations': iterations,
        'lloq': (min(retained_nominals) if retained_nominals else None),
        'uloq': (max(retained_nominals) if retained_nominals else None),
        'entries': entries,
        'assignable_ids': assignable,
        'removed_ids': removed_ids,
        'retained_ids': retained_ids,
    }
    return b['calibration'][rid]


def run_reading(b, rid, rec):
    """Back-calculated reading of an injection in a run (H6)."""
    cal = b['calibration'].get(rid)
    if not cal or not cal['coefficients'] or rec['i_area'] == 0:
        return None
    return back_calculate(Fraction(rec['a_area'], rec['i_area']),
                          cal['model'], cal['coefficients'])


def qc_eval(b, rid, rec, level, nominal):
    """Value and pass/fail of a QC or DQC injection (H9, H10)."""
    cal = b['calibration'][rid]
    if not cal['coefficients'] or nominal is None:
        return None, False
    reading = run_reading(b, rid, rec)
    if reading is None:
        return None, False
    value = reading * rec['dil'] if level == 'DQC' else reading
    dev = deviation_pct(value, nominal)
    if dev is None:
        return None, False
    method = b['runs'][rid]['method']
    limit = method['dqc_limit_pct'] if level == 'DQC' else method['qc_limit_pct']
    return value, (abs(dev) <= limit)


def accept_run(b, rid):
    """H9 run acceptance and H10 dilution QC status."""
    run = b['runs'][rid]
    method = run['method']
    cal = b['calibration'][rid]
    recs = b['run_injections'][rid]
    qcs = [r for r in recs if r['kind'] == 'QC']
    dqcs = [r for r in recs if r['kind'] == 'DQC']

    study_dil = any(r['dil'] > 1 for r in recs
                    if r['kind'] == 'UNK' and r['inj'] in b['study_inj'])
    dqc_status = 'NA'
    if study_dil:
        ok = len(dqcs) >= 2
        for r in dqcs:
            _v, passed = qc_eval(b, rid, r, 'DQC', qclot_nominal(b, rid, 'DQC'))
            if not passed:
                ok = False
                break
        dqc_status = 'PASS' if ok else 'FAIL'

    qc_total = len(qcs)
    qc_pass_n = 0
    by_level = {}
    for r in qcs:
        level = norm_level(r['ref'])
        nominal = qclot_nominal(b, rid, level) if level else None
        _v, passed = qc_eval(b, rid, r, level, nominal)
        if passed:
            qc_pass_n += 1
        if level:
            cur = by_level.setdefault(level, [0, 0])
            cur[1] += 1
            if passed:
                cur[0] += 1

    levels = set(e['level'] for e in cal['entries'] if e['level']
                 and e['rec']['inj'] in cal['retained_ids'])
    status = 'ACCEPTED'
    reason = ''
    if rid in b['rejected_runs']:
        status = 'REJECTED'
        reason = 'RULING'
    elif not cal['coefficients']:
        status = 'REJECTED'
        reason = 'NO_CURVE'
    else:
        for e in cal['entries']:
            if e['rec']['inj'] not in cal['retained_ids']:
                continue
            if e['dev'] is not None and abs(e['dev']) > e['limit']:
                status = 'REJECTED'
                reason = 'STD_LIMIT'
                break
        if status == 'ACCEPTED' and cal['n_standards'] > 0:
            if Fraction(cal['n_retained'], cal['n_standards']) < method['min_std_fraction']:
                status = 'REJECTED'
                reason = 'STD_COUNT'
        if status == 'ACCEPTED' and len(levels) < method['min_levels']:
            status = 'REJECTED'
            reason = 'STD_LEVELS'
        if status == 'ACCEPTED' and qc_total > 0:
            if Fraction(qc_pass_n, qc_total) < method['min_qc_fraction']:
                status = 'REJECTED'
                reason = 'QC_TOTAL'
        if status == 'ACCEPTED' and method['min_qc_level_fraction'] is not None:
            for level in sorted(by_level):
                p, t = by_level[level]
                if t > 0 and Fraction(p, t) < method['min_qc_level_fraction']:
                    status = 'REJECTED'
                    reason = 'QC_LEVEL'
                    break
    return {
        'run_id': rid,
        'analyte': run['analyte'],
        'run_type': run['run_type'],
        'analysis_date': run['analysis_date'],
        'n_std_total': cal['n_standards'],
        'n_std_retained': cal['n_retained'],
        'n_levels_retained': len(levels),
        'qc_total': qc_total,
        'qc_pass': qc_pass_n,
        'status': status,
        'reason': reason,
        'dqc_status': dqc_status,
        'lab_status': b['lab_status'].get(rid, ''),
        'by_level': by_level,
    }


def compute_calibration(b):
    b['calibration'] = {}
    b['acceptance'] = {}
    for rid in b['run_order']:
        fit_run(b, rid)
        b['acceptance'][rid] = accept_run(b, rid)
    return b


# --------------------------------------------------------------------------- #
# H11 study-sample results
# --------------------------------------------------------------------------- #

def reassay_reasons(b):
    """Map (tube, analyte, run) to the reassay log reason (H11)."""
    out = {}
    for r in b['reassay']:
        if (r.get('status') or '').strip().upper() == 'CANCELLED':
            continue
        rtube = resolve_tube(b, r.get('tube'))
        if not rtube:
            continue
        analyte = (r.get('analyte') or '').strip().upper()
        rtoken = (r.get('run') or '').strip().upper()
        rrid = (rtoken if rtoken in b['known_runs'] else b['run_alias'].get(rtoken))
        out[(rtube, analyte, rrid)] = re.sub(r'[\s-]+', '_', (r.get('reason') or '')
                                            .strip().upper())
    return out


def reassay_reason(b, tube, analyte, rid):
    """Reason of the matching reassay log row (H11)."""
    return b.get('reason_map', {}).get((tube, analyte, rid), 'ORIGINAL')


def compute_results(b):
    """H11 study-sample results and the per-run result tables."""
    b['reason_map'] = reassay_reasons(b)
    b['results'] = []
    tube_results = defaultdict(list)
    for rid in b['run_order']:
        run = b['runs'][rid]
        acc = b['acceptance'][rid]
        cal = b['calibration'][rid]
        for rec in b['run_injections'][rid]:
            kind = rec['kind']
            if kind == 'UNK':
                if rec['inj'] not in b['study_inj']:
                    continue
                tube = b['inj_tube'][rec['inj']]
                subj = b['tube_subject'].get(tube)
                if subj is None or subj not in b['scope_set']:
                    continue
                if run['run_type'] == 'ISR':
                    reason = 'ISR'
                else:
                    reason = reassay_reason(b, tube, run['analyte'], rid)
                reading = run_reading(b, rid, rec)
                if acc['status'] != 'ACCEPTED':
                    flag = 'RUN_REJECTED'
                elif rec['dil'] > 1 and acc['dqc_status'] == 'FAIL':
                    flag = 'DQC_FAIL'
                elif reading is None:
                    flag = 'ALQ'
                elif reading < cal['lloq']:
                    flag = 'BLQ'
                elif reading > cal['uloq']:
                    flag = 'ALQ'
                else:
                    flag = 'OK'
                conc = None
                if flag == 'OK' and reading is not None:
                    conc = sig(reading * rec['dil'], 4)
                res = {
                    'inj': rec['inj'],
                    'run_id': rid,
                    'run_rank': b['run_rank'][rid],
                    'seq': rec['seq'],
                    'tube': tube,
                    'subject': subj,
                    'analyte': run['analyte'],
                    'kind': kind,
                    'reason': reason,
                    'dil': rec['dil'],
                    'response': (Fraction(rec['a_area'], rec['i_area'])
                                 if rec['i_area'] else None),
                    'reading': reading,
                    'concentration': conc,
                    'flag': flag,
                    'used': False,
                }
                b['results'].append(res)
                tube_results[(tube, run['analyte'])].append(res)
            elif kind in ('QC', 'DQC'):
                level = norm_level(rec['ref'])
                nominal = qclot_nominal(b, rid, level) if level else None
                value, passed = qc_eval(b, rid, rec, level, nominal)
                dev = (deviation_pct(value, nominal)
                       if (value is not None and nominal is not None) else None)
                b.setdefault('qc_rows', []).append({
                    'run_id': rid,
                    'inj': rec['inj'],
                    'level': level,
                    'nominal': nominal,
                    'dil': rec['dil'],
                    'value': value,
                    'dev': dev,
                    'passed': bool(passed),
                    'kind': kind,
                    'seq': rec['seq'],
                })
    for key in tube_results:
        tube_results[key].sort(key=lambda r: (r['run_rank'], r['seq']))
    b['tube_results'] = tube_results
    b.setdefault('qc_rows', []).sort(key=lambda q: (q['run_id'], q['seq']))
    return b


# --------------------------------------------------------------------------- #
# H12 reported concentrations
# --------------------------------------------------------------------------- #

def compute_reported(b):
    """H12 reported concentration of every scheduled tube and analyte."""
    exclud = set()
    for r in b['rulings']:
        if r['action'] != 'EXCLUDE_SAMPLE' or r['status'] != 'IN FORCE':
            continue
        if (r['study'] or '').strip().upper() != b['study_id'].upper():
            continue
        exclud.add(resolve_tube(b, r['target']))
    b['excluded_tubes'] = exclud

    rows = []
    b['reported'] = {}
    b['used_injections'] = set()
    for tube in sorted(b['tubes']):
        info = b['tubes'][tube]
        subj = b['tube_subject'].get(tube)
        if subj is None or subj not in b['scope_set']:
            continue
        if info['nominal'] is None:
            continue
        for analyte in b['analytes']:
            res_list = b['tube_results'].get((tube, analyte), [])
            status = 'NR'
            rule = 'NONE'
            value = None
            source_run = ''
            if tube in exclud:
                status = 'EXCL'
                rule = 'RULING'
            elif info['status'] == 'NOT_COLLECTED':
                status = 'NOT_COLLECTED'
                rule = 'NONE'
            else:
                cands = [r for r in res_list
                         if r['flag'] in ('OK', 'BLQ', 'ALQ') and r['reason'] != 'ISR']
                base = None
                for r in cands:
                    if r['reason'] in ('ORIGINAL', 'RUN_FAIL'):
                        base = r
                        break
                if base is None:
                    status = 'NR'
                    rule = 'NONE'
                elif base['flag'] == 'ALQ':
                    dil_res = None
                    for r in cands:
                        if r['reason'] == 'ALQ' and r['flag'] == 'OK':
                            dil_res = r
                            break
                    if dil_res is None:
                        status = 'NR'
                        rule = 'ALQ_NO_DILUTION'
                    else:
                        status = 'OK'
                        rule = 'ALQ_DILUTION'
                        value = dil_res['concentration']
                        source_run = dil_res['run_id']
                        b['used_injections'].add(dil_res['inj'])
                elif base['flag'] == 'BLQ':
                    status = 'BLQ'
                    rule = base['reason']
                    b['used_injections'].add(base['inj'])
                else:
                    repeats = [r for r in cands
                               if r['reason'] == 'PK_REPEAT' and r['flag'] in ('OK', 'BLQ')]
                    if len(repeats) >= 2:
                        vals = [base['concentration'] if base['flag'] == 'OK'
                                else Decimal(0)]
                        for r in repeats[:2]:
                            vals.append(r['concentration'] if r['flag'] == 'OK'
                                        else Decimal(0))
                        med = median3(vals)
                        if med == 0:
                            status = 'BLQ'
                        else:
                            status = 'OK'
                        rule = 'PK_REPEAT_MEDIAN'
                        value = med
                        source_run = base['run_id']
                        b['used_injections'].add(base['inj'])
                        for r in repeats[:2]:
                            b['used_injections'].add(r['inj'])
                    else:
                        status = 'OK'
                        rule = base['reason']
                        value = base['concentration']
                        source_run = base['run_id']
                        b['used_injections'].add(base['inj'])
            row = {
                'subject': subj,
                'period': info['period'],
                'analyte': analyte,
                'nominal': info['nominal'],
                'tube': tube,
                'value': value,
                'status': status,
                'rule': rule,
                'source_run': source_run,
            }
            rows.append(row)
            b['reported'][(tube, analyte)] = row
    rows.sort(key=lambda r: (r['subject'], r['period'] or 0,
                             b['analytes'].index(r['analyte']), r['nominal']))
    b['reported_rows'] = rows
    return b


# --------------------------------------------------------------------------- #
# H13 times
# --------------------------------------------------------------------------- #

def compute_times(b):
    b['dose_instant'] = {}
    for (subj, per), (kind, val) in b['dose'].items():
        if kind == 'wall':
            b['dose_instant'][(subj, per)] = b['calendar'].wall_to_instant(val)
        else:
            b['dose_instant'][(subj, per)] = val

    # correction journal: SET entries in effect (H13)
    b['draw_wall'] = {}
    for tube, entries in b['corrections'].items():
        decided = {}
        for e in sorted(entries, key=lambda x: -x['seq']):
            cancelled = False
            for r in entries:
                if (r['seq'] > e['seq'] and r['action'] == 'REVERSE'
                        and r['reverses'] == e['seq'] and decided.get(r['seq'])):
                    cancelled = True
                    break
            decided[e['seq']] = (not cancelled)
        sets = [e for e in entries if e['action'] == 'SET' and decided.get(e['seq'])]
        if sets:
            b['draw_wall'][tube] = max(sets, key=lambda e: e['seq'])['value']

    b['draw_instant'] = {}
    b['draw_has_time'] = {}
    tubes = set(b['tubes']) | set(b['draw_raw']) | set(b['corrections'])
    for tube in tubes:
        wall = b['draw_wall'].get(tube)
        if wall is not None:
            if wall == '':
                b['draw_has_time'][tube] = False
                b['draw_instant'][tube] = None
            else:
                b['draw_has_time'][tube] = True
                b['draw_instant'][tube] = b['calendar'].wall_to_instant(parse_naive(wall))
            continue
        raw = b['draw_raw'].get(tube)
        if raw is None:
            b['draw_has_time'][tube] = False
            b['draw_instant'][tube] = None
        elif raw[0] == 'wall':
            if raw[1] == '':
                b['draw_has_time'][tube] = False
                b['draw_instant'][tube] = None
            else:
                b['draw_has_time'][tube] = True
                b['draw_instant'][tube] = b['calendar'].wall_to_instant(parse_naive(raw[1]))
        else:
            inst = parse_instant(raw[1]) if raw[1] else None
            b['draw_has_time'][tube] = inst is not None
            b['draw_instant'][tube] = inst

    # elapsed hours of every scheduled tube of an in-scope subject
    b['elapsed'] = {}
    for tube, info in b['tubes'].items():
        subj = b['tube_subject'].get(tube)
        if subj is None or subj not in b['scope_set']:
            continue
        if info['nominal'] is None:
            continue
        per = info['period']
        dose = b['dose_instant'].get((subj, per)) if per is not None else None
        draw = b['draw_instant'].get(tube)
        has_time = b['draw_has_time'].get(tube, False)
        if not has_time or draw is None:
            b['elapsed'][tube] = None
            continue
        if info['nominal'] == 0 or dose is None:
            b['elapsed'][tube] = (dec_round(0, 4) if info['nominal'] == 0 else None)
            if dose is None:
                b['elapsed'][tube] = None
            continue
        delta = (draw - dose).total_seconds() / 3600.0
        b['elapsed'][tube] = dec_round(delta, 4)
    return b


# --------------------------------------------------------------------------- #
# H15 non-compartmental analysis
# --------------------------------------------------------------------------- #

def compute_nca(b):
    b['nca'] = {}
    b['nca_rows'] = []
    subjects = sorted(s for s in set(b['tube_subject'].values())
                      if s and s in b['scope_set'])
    for subject in subjects:
        periods = sorted(set(p for (s, p) in b['dose_instant'] if s == subject))
        for period in periods:
            for ai, analyte in enumerate(b['analytes']):
                pts = []
                for row in b['reported_rows']:
                    if (row['subject'] != subject or row['period'] != period
                            or row['analyte'] != analyte):
                        continue
                    tube = row['tube']
                    elapsed = b['elapsed'].get(tube)
                    if elapsed is None:
                        continue
                    status = row['status']
                    if status == 'OK':
                        pts.append({'t': elapsed, 'v': row['value'], 'st': 'OK',
                                    'tube': tube})
                    elif status == 'BLQ':
                        pts.append({'t': elapsed, 'v': None, 'st': 'BLQ', 'tube': tube})
                pts.sort(key=lambda p: (p['t'], b['tubes'][p['tube']]['nominal']))
                first_ok = None
                for i, p in enumerate(pts):
                    if p['st'] == 'OK':
                        first_ok = i
                        break
                points = []
                for i, p in enumerate(pts):
                    if p['st'] == 'OK':
                        points.append((p['t'], p['v']))
                    elif p['st'] == 'BLQ' and first_ok is not None and i < first_ok:
                        points.append((p['t'], Decimal(0)))
                n_points = len(points)
                positive = [(t, v) for t, v in points if v > 0]
                profile = {
                    'subject': subject, 'period': period, 'analyte': analyte,
                    'n_points': n_points, 'points': points,
                    'flag': 'NOT_EVALUABLE', 'cmax': None, 'tmax': None,
                    'clast': None, 'tlast': None, 'auc_last': None,
                    'lambda_z': None, 'lz_points': None, 'lz_adj_r2': None,
                    'half_life': None, 'clast_pred': None, 'auc_inf': None,
                    'auc_extrap_pct': None, 'candidates': [],
                }
                if len(positive) >= 3:
                    cmax = max(v for _t, v in points)
                    for t, v in points:
                        if v == cmax:
                            tmax = t
                            break
                    clast = positive[-1][1]
                    tlast = positive[-1][0]
                    auc = Decimal(0)
                    for i in range(1, len(points)):
                        t1, c1 = points[i - 1]
                        t2, c2 = points[i]
                        if t2 == t1:
                            continue
                        if c1 > c2 and c1 > 0 and c2 > 0:
                            dt = t2 - t1
                            seg = (c1 - c2) / (c1.ln() - c2.ln()) * dt
                        else:
                            dt = t2 - t1
                            seg = (c1 + c2) / 2 * dt
                        auc += seg
                    profile['cmax'] = cmax
                    profile['tmax'] = tmax
                    profile['clast'] = clast
                    profile['tlast'] = tlast
                    profile['auc_last'] = auc
                    profile['flag'] = 'OK'
                    # terminal phase candidates
                    cidx = None
                    for i, (t, v) in enumerate(points):
                        if v == cmax and t == tmax:
                            cidx = i
                            break
                    cands = [(t, v) for t, v in points[cidx + 1:] if v > 0]
                    best = None
                    chosen = None
                    cand_list = []
                    for n in range(b['lz_min_points'], len(cands) + 1):
                        subset = cands[-n:]
                        xs = [float(t) for t, _v in subset]
                        ys = [math.log(float(v)) for _t, v in subset]
                        reg = ols_regression(list(zip(xs, ys)))
                        if reg is None:
                            continue
                        slope, intercept, r2, _n = reg
                        eligible = slope < 0
                        adj = None
                        if n >= 3:
                            adj = 1.0 - (1.0 - r2) * (n - 1) / (n - 2)
                        cand_list.append({'n': n, 'slope': slope,
                                          'intercept': intercept,
                                          'adj_r2': adj, 'eligible': eligible})
                        if eligible and adj is not None:
                            if best is None or adj > best:
                                best = adj
                    profile['candidates'] = cand_list
                    if best is None:
                        profile['flag'] = 'NO_LAMBDA_Z'
                    else:
                        tol = float(b['lz_tol'])
                        pool = [c for c in cand_list
                                if c['eligible'] and c['adj_r2'] is not None
                                and c['adj_r2'] >= best - tol]
                        chosen = max(pool, key=lambda c: c['n'])
                        profile['lz_points'] = chosen['n']
                        profile['lz_adj_r2'] = chosen['adj_r2']
                        lz = -chosen['slope']
                        profile['lambda_z'] = lz
                        profile['half_life'] = math.log(2) / lz
                        profile['clast_pred'] = math.exp(chosen['intercept'] - lz
                                                         * float(tlast))
                        profile['auc_inf'] = float(auc) + profile['clast_pred'] / lz
                        profile['auc_extrap_pct'] = (100.0 * (profile['clast_pred'] / lz)
                                                      / profile['auc_inf'])
                        if profile['auc_extrap_pct'] > float(b['extrap_pct']):
                            profile['flag'] = 'EXTRAP_GT_LIMIT'
                        else:
                            profile['flag'] = 'OK'
                    profile['chosen_n'] = profile['lz_points']
                b['nca'][(subject, period, analyte)] = profile
                b['nca_rows'].append(profile)
    return b


def formulation_of(b, subject, period):
    seq = b['sequence'].get(subject, '')
    if seq == 'TR':
        return 'T' if period == 1 else ('R' if period == 2 else None)
    if seq == 'RT':
        return 'R' if period == 1 else ('T' if period == 2 else None)
    return None


def reference_period(b, subject):
    seq = b['sequence'].get(subject, '')
    if seq == 'TR':
        return 2
    if seq == 'RT':
        return 1
    return None


# --------------------------------------------------------------------------- #
# H16 analysis populations
# --------------------------------------------------------------------------- #

def emesis_passes(b, candidates):
    """H16 emesis passes; returns (passes, settlement, settled index)."""
    pivotal = b['pivotal'][0] if b['pivotal'] else (b['analytes'][0] if b['analytes']
                                                    else None)
    factor = b['emesis_factor']
    passes = []
    prev = set()
    while True:
        ref = [s for s in candidates if s not in prev]
        tmaxes = []
        for s in ref:
            per = reference_period(b, s)
            prof = b['nca'].get((s, per, pivotal)) if per is not None else None
            if prof is not None and prof['flag'] != 'NOT_EVALUABLE' and \
                    prof['tmax'] is not None:
                tmaxes.append(prof['tmax'])
        if tmaxes:
            mean_tmax = sum(tmaxes) / Decimal(len(tmaxes))
            window = factor * mean_tmax
        else:
            mean_tmax = None
            window = Decimal(0)
        emetic = set()
        events = defaultdict(list)
        for ae in b['aes']:
            if ae['pt'] not in b['emesis_pts']:
                continue
            if ae['subject'] not in candidates:
                continue
            dose = b['dose_instant'].get((ae['subject'], ae['period'])) \
                if ae['period'] is not None else None
            if dose is None or ae['onset'] is None:
                continue
            onset = b['calendar'].wall_to_instant(ae['onset'])
            el = dec_round((onset - dose).total_seconds() / 3600.0, 4)
            if Decimal(0) <= el <= window:
                emetic.add(ae['subject'])
                events[ae['subject']].append((ae['period'], el))
        passes.append({'window': window, 'mean': mean_tmax, 'emetic': set(emetic),
                       'events': dict(events)})
        repeated = None
        for i, p in enumerate(passes[:-1]):
            if p['emetic'] == passes[-1]['emetic']:
                repeated = i
                break
        if repeated is not None:
            if repeated == len(passes) - 2:
                settlement = 'CONVERGED'
                settled = len(passes) - 1
            else:
                settlement = 'CYCLE'
                best = None
                settled = None
                for i in range(repeated, len(passes) - 1):
                    w = passes[i]['window']
                    if best is None or w > best:
                        best = w
                        settled = i
            return passes, settlement, settled
        prev = set(emetic)
        if len(passes) > 1000:
            return passes, 'CYCLE', len(passes) - 1


def carryover_of(b, subj, analyte):
    """H16.7: first offending period and 100 x pre-dose / Cmax."""
    co = None
    for per in (1, 2):
        prof = b['nca'].get((subj, per, analyte))
        if prof is None or prof['cmax'] is None:
            continue
        predose = None
        for row in b['reported_rows']:
            if (row['subject'] == subj and row['period'] == per
                    and row['analyte'] == analyte
                    and row['nominal'] == 0 and row['status'] == 'OK'):
                predose = row['value']
                break
        if predose is not None:
            limit = b['carryover_pct'] / Decimal(100) * prof['cmax']
            if predose > limit:
                val = Decimal(100) * predose / prof['cmax']
                if co is None or per < co[0]:
                    co = (per, val)
    return co


def compute_populations(b):
    study = b['study_id']
    ruled = {}
    for r in b['rulings']:
        if r['action'] != 'EXCLUDE_SUBJECT' or r['status'] != 'IN FORCE':
            continue
        if (r['study'] or '').strip().upper() != study.upper():
            continue
        subj = chain_resolve(r['target'], b['subject_alias'], b['rand_subjects'])
        if subj is not None:
            ruled[subj] = r['id']
    withdrawn = set()
    for d in b['disposition']:
        if d['event'] == 'WITHDRAWN' and d['subject'] is not None:
            withdrawn.add(d['subject'])
    incomplete = {}
    for subj in b['scope_set']:
        missing = [p for p in sorted(b['dose_periods'])
                   if (subj, p) not in b['dose_instant']]
        if missing:
            incomplete[subj] = missing[0]
    candidates = [s for s in sorted(b['scope_set'])
                  if s not in ruled and s not in withdrawn and s not in incomplete]
    passes, settlement, settled = emesis_passes(b, candidates)
    b['emesis_passes'] = passes
    b['emesis_settlement'] = settlement
    b['emesis_settled'] = settled
    b['emesis_subjects'] = passes[settled]['emetic'] if passes else set()
    b['emesis_events'] = passes[settled]['events'] if passes else {}
    b['emesis_candidates'] = candidates

    b['subject_reason'] = {}
    rows = []
    excluded = []
    randomized = [r['subject'].strip().upper() for r in b['randomization']]
    for subj in randomized:
        for analyte in b['analytes']:
            reason = ''
            period = None
            value = None
            if subj not in b['scope_set']:
                reason = 'NOT_IN_SCOPE'
            elif subj in ruled:
                reason = 'RULING'
            elif subj in withdrawn:
                reason = 'WITHDRAWN'
            elif subj in incomplete:
                reason = 'INCOMPLETE'
                period = incomplete[subj]
            elif subj in b['emesis_subjects']:
                reason = 'EMESIS'
                evs = sorted(b['emesis_events'].get(subj, []))
                if evs:
                    period = evs[0][0]
                    value = evs[0][1]
            else:
                ne = None
                for per in (1, 2):
                    prof = b['nca'].get((subj, per, analyte))
                    if prof is None or prof['flag'] == 'NOT_EVALUABLE':
                        if ne is None:
                            ne = per
                if ne is not None:
                    reason = 'NOT_EVALUABLE'
                    period = ne
                else:
                    co = carryover_of(b, subj, analyte)
                    if co is not None:
                        reason = 'CARRYOVER'
                        period = co[0]
                        value = co[1]
            b['subject_reason'][(subj, analyte)] = (reason, period, value)
            if reason and subj in b['scope_set']:
                excluded.append({'subject': subj, 'analyte': analyte, 'reason': reason,
                                 'period': period, 'value': value,
                                 'value_stage': (reason == 'EMESIS')})
            for param in b['parameters']:
                inc = True
                preason = ''
                if reason:
                    inc = False
                    preason = reason
                elif param == 'AUCinf':
                    profs = [b['nca'].get((subj, per, analyte)) for per in (1, 2)]
                    if any(p is None or p['lambda_z'] is None for p in profs):
                        inc = False
                        preason = 'PARAM_NA'
                    elif any(p['flag'] == 'EXTRAP_GT_LIMIT' for p in profs):
                        inc = False
                        preason = 'EXTRAP'
                rows.append({'subject': subj, 'analyte': analyte, 'parameter': param,
                             'included': inc, 'reason': preason})
    excluded.sort(key=lambda r: (r['subject'], b['analytes'].index(r['analyte'])))
    b['excluded_subjects'] = excluded
    aidx = dict((a, i) for i, a in enumerate(b['analytes']))
    pidx = dict((p, i) for i, p in enumerate(b['parameters']))
    rows.sort(key=lambda r: (r['subject'], aidx[r['analyte']], pidx[r['parameter']]))
    b['population_rows'] = rows
    return b


# --------------------------------------------------------------------------- #
# H17 average bioequivalence
# --------------------------------------------------------------------------- #

def t_quantile(b, df, p):
    row = b['t_quantiles'].get(df)
    if not row:
        return None
    best = None
    for key, val in row.items():
        if best is None or abs(key - p) < abs(best[0] - p):
            best = (key, val)
    return best[1] if best else None


def compute_stats(b):
    alpha = b['alpha']
    p_quant = Decimal(1) - alpha
    included = {}
    for row in b['population_rows']:
        if row['parameter'] == 'Cmax' and row['included']:
            included.setdefault(row['analyte'], set()).add(row['subject'])
    b['cmax_included'] = included
    stats = {}
    for analyte in b['analytes']:
        params = {}
        pivotal = analyte in b['pivotal']
        for param in b['parameters']:
            subj_params = set()
            for row in b['population_rows']:
                if row['analyte'] == analyte and row['parameter'] == param and \
                        row['included']:
                    subj_params.add(row['subject'])
            vals = {}
            for subj in subj_params:
                ys = []
                ok = True
                for per in (1, 2):
                    prof = b['nca'].get((subj, per, analyte))
                    if prof is None:
                        ok = False
                        break
                    if param == 'Cmax':
                        v = prof['cmax']
                    elif param == 'AUClast':
                        v = prof['auc_last']
                    elif param == 'AUCinf':
                        v = prof['auc_inf']
                    else:
                        v = prof.get(param.lower())
                    if v is None or not math.isfinite(float(v)):
                        ok = False
                        break
                    ys.append(math.log(float(v)))
                if ok:
                    vals[subj] = ys
            tr = sorted(s for s in vals if b['sequence'].get(s) == 'TR')
            rt = sorted(s for s in vals if b['sequence'].get(s) == 'RT')
            n_tr = len(tr)
            n_rt = len(rt)
            df = n_tr + n_rt - 2
            entry = {'n_TR': n_tr, 'n_RT': n_rt, 'df': df}
            if n_tr < 1 or n_rt < 1 or df <= 0:
                entry.update({'t_quantile': None, 'estimate_log': None, 'se_log': None,
                              'mse': None, 'cv_intra_pct': None, 'lsmean_T': None,
                              'lsmean_R': None, 'ratio_pct': None, 'ci_lower_pct': None,
                              'ci_upper_pct': None, 'ratio_pct_r': None,
                              'ci_lower_r': None, 'ci_upper_r': None,
                              'result': 'NOT_ESTIMABLE'})
            else:
                d = dict((s, (vals[s][1] - vals[s][0]) / 2.0) for s in vals)
                mean_tr = sum(d[s] for s in tr) / n_tr
                mean_rt = sum(d[s] for s in rt) / n_rt
                estimate = mean_rt - mean_tr
                sstr = sum((d[s] - mean_tr) ** 2 for s in tr)
                ssrt = sum((d[s] - mean_rt) ** 2 for s in rt)
                s2 = (sstr + ssrt) / df
                se = math.sqrt(s2 * (1.0 / n_tr + 1.0 / n_rt))
                mse = 2.0 * s2
                cv = 100.0 * math.sqrt(math.expm1(mse))
                y_tr1 = sum(vals[s][0] for s in tr) / n_tr
                y_tr2 = sum(vals[s][1] for s in tr) / n_tr
                y_rt1 = sum(vals[s][0] for s in rt) / n_rt
                y_rt2 = sum(vals[s][1] for s in rt) / n_rt
                lsm_t = (y_tr1 + y_rt2) / 2.0
                lsm_r = (y_tr2 + y_rt1) / 2.0
                tq = t_quantile(b, df, p_quant)
                ratio = 100.0 * math.exp(estimate)
                lower = 100.0 * math.exp(estimate - float(tq) * se)
                upper = 100.0 * math.exp(estimate + float(tq) * se)
                r_ratio = dec_round(ratio, 2)
                r_lower = dec_round(lower, 2)
                r_upper = dec_round(upper, 2)
                if pivotal:
                    res = 'PASS' if (r_lower >= b['be_lower'] and
                                     r_upper <= b['be_upper']) else 'FAIL'
                else:
                    res = 'INFO'
                entry.update({'t_quantile': tq, 'estimate_log': estimate,
                              'se_log': se, 'mse': mse, 'cv_intra_pct': cv,
                              'lsmean_T': math.exp(lsm_t), 'lsmean_R': math.exp(lsm_r),
                              'ratio_pct': ratio, 'ci_lower_pct': lower,
                              'ci_upper_pct': upper, 'ratio_pct_r': r_ratio,
                              'ci_lower_r': r_lower, 'ci_upper_r': r_upper,
                              'result': res})
            params[param] = entry
        all_pass = all(params[p]['result'] == 'PASS' for p in b['parameters'])
        if pivotal:
            conclusion = 'BIOEQUIVALENT' if all_pass else 'NOT_BIOEQUIVALENT'
        else:
            conclusion = 'SUPPORTIVE'
        stats[analyte] = {'role': 'PIVOTAL' if pivotal else 'SUPPORTIVE',
                          'conclusion': conclusion, 'parameters': params}
    b['be_stats'] = stats
    return b


# --------------------------------------------------------------------------- #
# H18 mean profiles and H19 incurred sample reanalysis
# --------------------------------------------------------------------------- #

def compute_mean_profiles(b):
    rows = []
    for analyte in b['analytes']:
        subjects = b['cmax_included'].get(analyte, set())
        buckets = defaultdict(list)
        for row in b['reported_rows']:
            if row['subject'] not in subjects or row['analyte'] != analyte:
                continue
            if row['status'] == 'OK':
                val = row['value'] if row['value'] is not None else Decimal(0)
            elif row['status'] == 'BLQ':
                val = Decimal(0)
            else:
                continue
            form = formulation_of(b, row['subject'], row['period'])
            if form is None:
                continue
            buckets[(form, row['nominal'])].append(val)
        for form in ('R', 'T'):
            keys = sorted(k for k in buckets if k[0] == form)
            for key in keys:
                vals = buckets[key]
                n = len(vals)
                mean = sum(vals) / Decimal(n)
                sd = None
                if n >= 2:
                    acc = Decimal(0)
                    for v in vals:
                        acc += (v - mean) ** 2
                    sd = (acc / Decimal(n - 1)).sqrt()
                rows.append({'analyte': analyte, 'formulation': form,
                             'nominal': key[1], 'n': n, 'mean': mean, 'sd': sd})
    b['mean_profiles'] = rows
    return b


def compute_isr(b):
    limit = b['isr_pct']
    out = {}
    for analyte in b['analytes']:
        pairs = []
        for tube in sorted(b['tubes']):
            info = b['tubes'][tube]
            subj = b['tube_subject'].get(tube)
            if subj is None or subj not in b['scope_set'] or info['nominal'] is None:
                continue
            row = b['reported'].get((tube, analyte))
            if row is None or row['status'] != 'OK':
                continue
            reported = row['value']
            isr = [r for r in b['tube_results'].get((tube, analyte), [])
                   if r['reason'] == 'ISR' and r['flag'] == 'OK']
            if not isr or reported is None:
                continue
            rep = isr[0]
            repeat = rep['concentration']
            if repeat is None:
                continue
            mean = (repeat + reported) / Decimal(2)
            if mean == 0:
                continue
            diff = Decimal(100) * (repeat - reported) / mean
            within = abs(diff) <= limit
            pairs.append({'tube': tube, 'run_id': rep['run_id'], 'reported': reported,
                          'repeat': repeat, 'diff_pct': diff, 'within': within})
        n_pairs = len(pairs)
        n_within = sum(1 for p in pairs if p['within'])
        passed = bool(n_pairs) and (n_within * 3 >= n_pairs * 2)
        out[analyte] = {'pairs': pairs, 'n_pairs': n_pairs, 'n_within': n_within,
                        'pct_within': (Decimal(100) * n_within / n_pairs)
                        if n_pairs else None,
                        'pass': passed}
    b['isr'] = out
    return b


# --------------------------------------------------------------------------- #
# report writers
# --------------------------------------------------------------------------- #

def write_delim(path, header, rows, delim=','):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f, delimiter=delim, lineterminator='\n')
        w.writerow(header)
        for r in rows:
            w.writerow([(c if c is not None else '') for c in r])


def cell(v, raw=False):
    """Format one output cell per H21/H22."""
    if v is None:
        return ''
    if isinstance(v, str):
        return v
    if isinstance(v, bool):
        return 'Y' if v else 'N'
    if isinstance(v, Raw):
        return fmt(v.d)
    if raw:
        return fmt(v)
    return num(v)


def w_calibration_fits(b, out):
    runs = []
    for rid in sorted(b['runs']):
        cal = b['calibration'][rid]
        coefs = None
        if cal['coefficients'] is not None:
            c = cal['coefficients']
            coefs = {'a': Raw(c['a']), 'b': Raw(c['b']),
                     'c': (Raw(c['c']) if c['c'] is not None else None)}
        runs.append({
            'run_id': rid,
            'analyte': cal['analyte'],
            'model': cal['model'],
            'weighting': cal['weighting'],
            'cal_lot': cal['cal_lot'],
            'coefficients': coefs,
            'n_standards': cal['n_standards'],
            'n_assignable': cal['n_assignable'],
            'n_retained': cal['n_retained'],
            'removed': list(cal['removed']),
            'iterations': cal['iterations'],
            'lloq': (Raw(cal['lloq']) if cal['lloq'] is not None else None),
            'uloq': (Raw(cal['uloq']) if cal['uloq'] is not None else None),
        })
    write_json(os.path.join(out, 'calibration_fits.json'), {
        'study_id': b['study_id'], 'nominal_sheet': b['nominal_sheet'], 'runs': runs})


def w_standard_backcalc(b, out):
    rows = []
    for rid in sorted(b['runs']):
        cal = b['calibration'][rid]
        for e in sorted(cal['entries'], key=lambda x: x['rec']['seq']):
            inj = e['rec']['inj']
            if inj in cal['assignable_ids']:
                status = 'ASSIGNABLE'
            elif cal['coefficients'] is None:
                status = 'NO_CURVE'
            elif inj in cal['removed_ids']:
                status = 'REMOVED'
            else:
                status = 'RETAINED'
            rows.append([rid, inj, (e['level'] or ''), cell(e['nominal'], True),
                         cell(e['response']), cell(e['reading']), cell(e['dev']),
                         status])
    write_delim(os.path.join(out, 'standard_backcalc.tsv'),
                 ['run_id', 'injection_id', 'level', 'nominal', 'response',
                  'back_calculated', 'deviation_pct', 'status'], rows, '\t')


def w_qc_results(b, out):
    rows = []
    for q in b.get('qc_rows', []):
        rows.append([q['run_id'], q['inj'], (q['level'] or ''),
                     cell(q['nominal'], True), cell(q['dil']),
                     cell(q['value']), cell(q['dev']),
                     'Y' if q['passed'] else 'N'])
    write_delim(os.path.join(out, 'qc_results.csv'),
                ['run_id', 'injection_id', 'qc_level', 'nominal', 'dilution_factor',
                 'back_calculated', 'deviation_pct', 'pass'], rows)


def w_run_acceptance(b, out):
    rows = []
    for rid in sorted(b['runs']):
        acc = b['acceptance'][rid]
        agrees = 'Y' if acc['lab_status'] == acc['status'] else 'N'
        rows.append([rid, acc['analyte'], acc['run_type'],
                     acc['analysis_date'].isoformat(),
                     cell(acc['n_std_total']), cell(acc['n_std_retained']),
                     cell(acc['n_levels_retained']), cell(acc['qc_total']),
                     cell(acc['qc_pass']), acc['status'], acc['reason'],
                     acc['dqc_status'], acc['lab_status'], agrees])
    write_delim(os.path.join(out, 'run_acceptance.csv'),
                ['run_id', 'analyte', 'run_type', 'analysis_date', 'n_std_total',
                 'n_std_retained', 'n_levels_retained', 'qc_total', 'qc_pass',
                 'status', 'reason', 'dqc_status', 'lab_status', 'agrees'], rows)


def w_tube_results(b, out):
    aidx = dict((a, i) for i, a in enumerate(b['analytes']))
    res = [r for r in b['results']]
    res.sort(key=lambda r: (r['tube'], aidx[r['analyte']], r['run_rank'], r['seq']))
    rows = []
    for r in res:
        rows.append([r['run_id'], r['inj'], r['tube'], r['analyte'], r['reason'],
                     cell(r['dil']), cell(r['response']), cell(r['reading']),
                     (cell(r['concentration'], True) if r['concentration'] is not None
                      else ''),
                     r['flag'], 'Y' if r['inj'] in b['used_injections'] else 'N'])
    write_delim(os.path.join(out, 'tube_results.psv'),
                ['run_id', 'injection_id', 'tube', 'analyte', 'reason',
                 'dilution_factor', 'response', 'back_calculated', 'concentration',
                 'flag', 'used'], rows, '|')


def w_reported_concentrations(b, out):
    rows = []
    for row in b['reported_rows']:
        form = formulation_of(b, row['subject'], row['period'])
        elapsed = b['elapsed'].get(row['tube'])
        if row['status'] == 'NOT_COLLECTED' or elapsed is None:
            actual = ''
        else:
            actual = cell(Raw(elapsed))
        rows.append([row['subject'], cell(row['period']), (form or ''), row['analyte'],
                     cell(row['nominal'], True), row['tube'], actual,
                     (cell(row['value'], True) if row['value'] is not None else ''),
                     row['status'], row['rule'], row['source_run']])
    write_delim(os.path.join(out, 'reported_concentrations.csv'),
                ['subject_id', 'period', 'formulation', 'analyte', 'nominal_h', 'tube',
                 'actual_h', 'concentration', 'status', 'rule', 'source_run'], rows)


def xml_escape(s):
    return (str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            .replace('"', '&quot;'))


def w_sampling_times(b, out):
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<sampling_times study="%s">' % xml_escape(b['study_id'])]
    tubes = []
    for tube, info in b['tubes'].items():
        subj = b['tube_subject'].get(tube)
        if subj is None or subj not in b['scope_set'] or info['nominal'] is None:
            continue
        dose = b['dose_instant'].get((subj, info['period'])) \
            if info['period'] is not None else None
        tubes.append((subj, info['period'] or 0, info['nominal'], tube, dose))
    tubes.sort()
    for subj, per, nominal, tube, dose in tubes:
        draw = b['draw_instant'].get(tube)
        elapsed = b['elapsed'].get(tube)
        lines.append('  <tube id="%s" subject="%s" period="%s" nominal_h="%s" '
                     'dose_utc="%s" drawn_utc="%s" elapsed_h="%s"/>' % (
                         xml_escape(tube), xml_escape(subj), per, cell(nominal, True),
                         iso_utc(dose), (iso_utc(draw) if draw is not None else ''),
                         (cell(Raw(elapsed)) if elapsed is not None else '')))
    lines.append('</sampling_times>')
    with open(os.path.join(out, 'sampling_times.xml'), 'w', encoding='utf-8',
              newline='\n') as f:
        f.write('\n'.join(lines) + '\n')


def w_isr_assessment(b, out):
    analytes = {}
    for analyte in b['analytes']:
        data = b['isr'].get(analyte, {})
        pairs = []
        for p in data.get('pairs', []):
            pairs.append({'tube': p['tube'], 'run_id': p['run_id'],
                          'reported': Raw(p['reported']), 'repeat': Raw(p['repeat']),
                          'diff_pct': p['diff_pct'], 'within': p['within']})
        analytes[analyte] = {
            'pairs': pairs,
            'n_pairs': data.get('n_pairs', 0),
            'n_within': data.get('n_within', 0),
            'pct_within': (num(data['pct_within'])
                           if data.get('pct_within') is not None else None),
            'pass': data.get('pass', False),
        }
    write_json(os.path.join(out, 'isr_assessment.json'), {
        'limit_pct': b['isr_pct'], 'analytes': analytes})


def w_nca_parameters(b, out):
    rows = []
    for p in b['nca_rows']:
        form = formulation_of(b, p['subject'], p['period'])
        flag = p['flag']
        cmax = cell(p['cmax'], True) if p['cmax'] is not None else ''
        tmax = cell(p['tmax'], True) if p['tmax'] is not None else ''
        clast = cell(p['clast'], True) if p['clast'] is not None else ''
        tlast = cell(p['tlast'], True) if p['tlast'] is not None else ''
        auc = cell(p['auc_last']) if p['auc_last'] is not None else ''
        lz = cell(p['lambda_z']) if p['lambda_z'] is not None else ''
        lzp = cell(p['lz_points']) if p['lz_points'] is not None else ''
        lza = cell(p['lz_adj_r2']) if p['lz_adj_r2'] is not None else ''
        hl = cell(p['half_life']) if p['half_life'] is not None else ''
        cp = cell(p['clast_pred']) if p['clast_pred'] is not None else ''
        ai = cell(p['auc_inf']) if p['auc_inf'] is not None else ''
        ex = cell(p['auc_extrap_pct']) if p['auc_extrap_pct'] is not None else ''
        rows.append([p['subject'], cell(p['period']), (form or ''), p['analyte'],
                     cell(p['n_points']), cmax, tmax, clast, tlast, auc, lz, lzp, lza,
                     hl, cp, ai, ex, flag])
    write_delim(os.path.join(out, 'nca_parameters.csv'),
                ['subject_id', 'period', 'formulation', 'analyte', 'n_points', 'cmax',
                 'tmax', 'clast', 'tlast', 'auc_last', 'lambda_z', 'lz_points',
                 'lz_adj_r2', 'half_life', 'clast_pred', 'auc_inf', 'auc_extrap_pct',
                 'flag'], rows)


def w_lambda_z_selection(b, out):
    path = os.path.join(out, 'lambda_z_selection.jsonl')
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        for p in b['nca_rows']:
            cands = []
            for c in p.get('candidates', []):
                cands.append({'n': c['n'], 'slope': c['slope'],
                              'intercept': c['intercept'],
                              'adj_r2': c['adj_r2'],
                              'eligible': bool(c['eligible'])})
            obj = {'subject_id': p['subject'], 'period': p['period'],
                   'analyte': p['analyte'], 'candidates': cands,
                   'chosen_n': p.get('chosen_n')}
            f.write(jdump_flat(obj) + '\n')


def w_be_statistics(b, out):
    analytes = {}
    for analyte in b['analytes']:
        st = b['be_stats'].get(analyte, {})
        params = {}
        for param in b['parameters']:
            e = st.get('parameters', {}).get(param)
            if e is None:
                continue
            params[param] = {
                'n_TR': e['n_TR'], 'n_RT': e['n_RT'], 'df': e['df'],
                't_quantile': e['t_quantile'],
                'estimate_log': e['estimate_log'], 'se_log': e['se_log'],
                'mse': e['mse'], 'cv_intra_pct': e['cv_intra_pct'],
                'lsmean_T': e['lsmean_T'], 'lsmean_R': e['lsmean_R'],
                'ratio_pct': e['ratio_pct'], 'ci_lower_pct': e['ci_lower_pct'],
                'ci_upper_pct': e['ci_upper_pct'],
                'ratio_pct_r': (Raw(e['ratio_pct_r'])
                                if e['ratio_pct_r'] is not None else None),
                'ci_lower_r': (Raw(e['ci_lower_r'])
                                if e['ci_lower_r'] is not None else None),
                'ci_upper_r': (Raw(e['ci_upper_r'])
                               if e['ci_upper_r'] is not None else None),
                'result': e['result'],
            }
        analytes[analyte] = {'role': st.get('role', ''), 'conclusion':
                             st.get('conclusion', ''), 'parameters': params}
    write_json(os.path.join(out, 'be_statistics.json'), {
        'study_id': b['study_id'],
        'alpha': b['alpha'],
        'ci_level_pct': (Decimal(100) * (Decimal(1) - 2 * b['alpha'])),
        'limits_pct': [b['be_lower'], b['be_upper']],
        'analytes': analytes})


def w_be_summary(b, out):
    lines = ['# %s bioequivalence summary' % b['study_id']]
    cols = ['analyte', 'parameter', 'n', 'ratio_pct', 'ci_lower', 'ci_upper',
            'cv_intra_pct', 'result']
    lines.append('| ' + ' | '.join(cols) + ' |')
    lines.append('|' + '---|' * len(cols))
    for analyte in b['analytes']:
        st = b['be_stats'].get(analyte, {})
        for param in b['parameters']:
            e = st.get('parameters', {}).get(param)
            if e is None:
                continue
            n = e['n_TR'] + e['n_RT']
            lines.append('| ' + ' | '.join([
                analyte, param, str(n),
                (fmt(e['ratio_pct_r']) if e['ratio_pct_r'] is not None else ''),
                (fmt(e['ci_lower_r']) if e['ci_lower_r'] is not None else ''),
                (fmt(e['ci_upper_r']) if e['ci_upper_r'] is not None else ''),
                (num(e['cv_intra_pct']) if e['cv_intra_pct'] is not None else ''),
                e['result']]) + ' |')
    with open(os.path.join(out, 'be_summary.md'), 'w', encoding='utf-8',
              newline='\n') as f:
        f.write('\n'.join(lines) + '\n')


def w_analysis_populations(b, out):
    rows = []
    for r in b['population_rows']:
        rows.append([r['subject'], r['analyte'], r['parameter'],
                     'Y' if r['included'] else 'N', r['reason']])
    write_delim(os.path.join(out, 'analysis_populations.csv'),
                ['subject_id', 'analyte', 'parameter', 'included', 'reason'], rows)


def w_excluded_subjects(b, out):
    path = os.path.join(out, 'excluded_subjects.jsonl')
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        for r in b['excluded_subjects']:
            obj = {'subject_id': r['subject'], 'analyte': r['analyte'],
                   'reason': r['reason'], 'period': r['period'],
                   'value': ((Raw(r['value']) if r.get('value_stage')
                             else r['value']) if r['value'] is not None else None)}
            f.write(jdump_flat(obj) + '\n')


def w_mean_profiles(b, out):
    rows = []
    for r in b['mean_profiles']:
        rows.append([r['analyte'], r['formulation'], cell(r['nominal'], True),
                     cell(r['n']), cell(r['mean']),
                     (cell(r['sd']) if r['sd'] is not None else '')])
    write_delim(os.path.join(out, 'mean_profiles.csv'),
                ['analyte', 'formulation', 'nominal_h', 'n', 'mean', 'sd'], rows)


def w_dedup_report(b, out):
    write_json(os.path.join(out, 'dedup_report.json'), {
        'rows_read': b['rows_read'],
        'duplicate_copies': b['duplicate_copies'],
        'superseded': b['superseded'],
        'inadmissible_manual': b['inadmissible_manual'],
        'voided': b['voided'],
        'effective_injections': b['effective_injections'],
        'standards': b['n_standards'],
        'qcs': b['n_qcs'],
        'blank_zero': b['n_blank_zero'],
        'study_sample_injections': b['n_study_samples'],
        'foreign_injections': b['n_foreign'],
    })


def w_source_lineage(b, out):
    shards = []
    counts = defaultdict(int)
    for rec in b['records']:
        counts[rec['shard']] += 1
    for s in b['shards']:
        shards.append({'file': s.get('file'), 'layout': s.get('layout'),
                       'rows': counts.get(s.get('file'), 0),
                       'effective': b['shard_effective'].get(s.get('file'), 0)})
    write_json(os.path.join(out, 'source_lineage.json'),
               {'shards': shards, 'inactive': b['inactive']})


def collect_alias_rows(b):
    """H4/H11 tokens observed in the governing sources, with their canonical ids."""
    rows = []
    # runs: active shards, exclusion requests, reassay log, Table R-1
    run_tokens = set(t for t in b['run_tokens'] if t)
    for r in b['std_requests']:
        tok = str(r.get('run') or '').strip().upper()
        if tok:
            run_tokens.add(tok)
    for r in b['reassay']:
        tok = (r.get('run') or '').strip().upper()
        if tok:
            run_tokens.add(tok)
    for r in b['rulings']:
        if r['action'] == 'REJECT_RUN':
            tok = (r['target'] or '').strip().upper()
            if tok:
                run_tokens.add(tok)
    for tok in run_tokens:
        if tok in b['known_runs']:
            rows.append(('run', tok, tok))
        else:
            rid = b['run_alias'].get(tok)
            if rid is not None:
                rows.append(('run', tok, rid))

    # subjects: manifests, dose logs, draw logs, AE rows of this study,
    # disposition log and Table R-1 rows of this study
    subject_tokens = set()
    for info in b['tubes'].values():
        if info['subject_token']:
            subject_tokens.add(info['subject_token'].strip().upper())
    for tok in b.get('dose_tokens', set()):
        subject_tokens.add(tok)
    for tok in b.get('draw_tokens', set()):
        subject_tokens.add(tok)
    for ae in b['aes']:
        if ae.get('subject_token'):
            subject_tokens.add(ae['subject_token'].strip().upper())
    for d in b['disposition']:
        if d.get('subject_token'):
            subject_tokens.add(d['subject_token'].strip().upper())
    for tok in b.get('disposition_tokens', set()):
        subject_tokens.add(tok)
    for r in b['rulings']:
        if (r['action'] == 'EXCLUDE_SUBJECT' and
                (r['study'] or '').strip().upper() == b['study_id'].upper()):
            tok = (r['target'] or '').strip().upper()
            if tok:
                subject_tokens.add(tok)
    for tok in subject_tokens:
        subj = chain_resolve(tok, b['subject_alias'], b['rand_subjects'])
        if subj is not None:
            rows.append(('subject', tok, subj))

    # tubes: active shards, reassay log and Table R-1 rows of this study that
    # resolve through an ACTIVE relabel
    tube_tokens = set(t for t in b['tube_tokens'] if t)
    for r in b['reassay']:
        tok = (r.get('tube') or '').strip().upper()
        if tok:
            tube_tokens.add(tok)
    for r in b['rulings']:
        if (r['action'] == 'EXCLUDE_SAMPLE' and
                (r['study'] or '').strip().upper() == b['study_id'].upper()):
            tok = (r['target'] or '').strip().upper()
            if tok:
                tube_tokens.add(tok)
    for tok in tube_tokens:
        if tok in b['relabel']:
            rows.append(('tube', tok, resolve_tube(b, tok)))
    rows = sorted(set(rows), key=lambda r: (r[0], r[1], r[2]))
    return rows


def w_alias_resolution(b, out):
    rows = [[k, t, c] for k, t, c in collect_alias_rows(b)]
    write_delim(os.path.join(out, 'alias_resolution.csv'),
                ['kind', 'token', 'canonical'], rows)


def w_parameters_used(b, out):
    settled = b['emesis_passes'][b['emesis_settled']] if b['emesis_passes'] else None
    lines = []
    lines.append('study_id: %s' % b['study_id'])
    lines.append('nominal_sheet: %s' % b['nominal_sheet'])
    lines.append('alpha: %s' % num(b['alpha']))
    lines.append('ci_level_pct: %s' % num(Decimal(100) * (Decimal(1) - 2 * b['alpha'])))
    lines.append('be_lower_pct: %s' % num(b['be_lower']))
    lines.append('be_upper_pct: %s' % num(b['be_upper']))
    lines.append('t_quantile_p: %s' % num(Decimal(1) - b['alpha']))
    lines.append('lambda_z_min_points: %d' % b['lz_min_points'])
    lines.append('lambda_z_adj_r2_tolerance: %s' % num(b['lz_tol']))
    lines.append('extrap_limit_pct: %s' % num(b['extrap_pct']))
    lines.append('carryover_limit_pct: %s' % num(b['carryover_pct']))
    lines.append('emesis_window_factor: %s' % num(b['emesis_factor']))
    lines.append('emesis_reference_mean_tmax_h: %s' %
                 (num(settled['mean']) if settled and settled['mean'] is not None else ''))
    lines.append('emesis_window_h: %s' % (num(settled['window']) if settled else ''))
    lines.append('emesis_passes: %d' % len(b['emesis_passes']))
    lines.append('emesis_settlement: %s' % b['emesis_settlement'])
    lines.append('isr_limit_pct: %s' % num(b['isr_pct']))
    for analyte in b['analytes']:
        m = b['methods'].get(analyte, {})
        lines.append('%s.model: %s' % (analyte, m.get('model', '')))
        lines.append('%s.weighting: %s' % (analyte, m.get('weighting', '')))
        lines.append('%s.std_limit_pct: %s' % (analyte, num(m.get('std_limit_pct', 0))))
        lines.append('%s.lloq_std_limit_pct: %s'
                     % (analyte, num(m.get('lloq_std_limit_pct', 0))))
        lines.append('%s.qc_limit_pct: %s' % (analyte, num(m.get('qc_limit_pct', 0))))
    lines.append('conventions_table: %s' % b['conventions_table'])
    lines.append('method_table: %s' % b['method_table'])
    lines.append('t_table: %s' % b['t_table'])
    with open(os.path.join(out, 'parameters_used.yaml'), 'w', encoding='utf-8',
              newline='\n') as f:
        f.write('\n'.join(lines) + '\n')


def w_variance_vs_published(b, out):
    pub = {}
    for r in b['published']:
        subj = (r.get('subject') or '').strip().upper()
        try:
            per = int(str(r.get('period') or '').strip())
        except (TypeError, ValueError):
            per = None
        an = (r.get('analyte') or '').strip().upper()
        if not subj or per is None:
            continue
        pub[(subj, per, an)] = r
    pmap = {'Cmax': 'cmax', 'AUClast': 'auc_last', 'AUCinf': 'auc_inf'}
    rows = []
    keys = set()
    for (subj, per, an) in pub:
        for param in ('Cmax', 'AUClast', 'AUCinf'):
            col = pmap[param]
            val = pub[(subj, per, an)].get(col)
            if val is not None and str(val).strip() != '':
                keys.add((subj, per, an, param))
    for p in b['nca_rows']:
        for param in ('Cmax', 'AUClast', 'AUCinf'):
            if param == 'Cmax' and p['cmax'] is not None:
                keys.add((p['subject'], p['period'], p['analyte'], param))
            elif param == 'AUClast' and p['auc_last'] is not None:
                keys.add((p['subject'], p['period'], p['analyte'], param))
            elif param == 'AUCinf' and p['flag'] == 'OK' and p['auc_inf'] is not None:
                keys.add((p['subject'], p['period'], p['analyte'], param))
    porder = {'Cmax': 0, 'AUClast': 1, 'AUCinf': 2}
    for key in sorted(keys, key=lambda k: (k[0], k[1], k[2], porder[k[3]])):
        subj, per, an, param = key
        prow = pub.get((subj, per, an))
        pval = ''
        if prow is not None:
            raw = prow.get(pmap[param])
            if raw is not None and str(raw).strip() != '':
                pval = str(raw).strip()
        rval = ''
        prof = b['nca'].get((subj, per, an))
        if prof is not None:
            if param == 'Cmax':
                v = prof['cmax']
            elif param == 'AUClast':
                v = prof['auc_last']
            else:
                v = prof['auc_inf'] if prof['flag'] == 'OK' else None
            if v is not None:
                rval = num(v)
        if pval == '' and rval == '':
            continue
        if pval == '':
            status = 'ONLY_RECOMPUTED'
            diff = ''
        elif rval == '':
            status = 'ONLY_PUBLISHED'
            diff = ''
        else:
            pv = to_dec(pval)
            rv = to_dec(rval)
            diff = Decimal(100) * (rv - pv) / pv
            status = 'MATCH' if abs(diff) <= 1 else 'DIFF'
        rows.append([subj, cell(per), an, param, pval, rval,
                     (num(diff) if diff != '' else ''), status])
    write_delim(os.path.join(out, 'variance_vs_published.csv'),
                ['subject_id', 'period', 'analyte', 'parameter', 'published',
                 'recomputed', 'diff_pct', 'status'], rows)


def w_reconciliation(b, out):
    lines = ['# %s published versus recomputed' % b['study_id']]
    cols = ['analyte', 'parameter', 'published_ratio', 'published_lower',
            'published_upper', 'published_result', 'recomputed_ratio',
            'recomputed_lower', 'recomputed_upper', 'recomputed_result']
    lines.append('| ' + ' | '.join(cols) + ' |')
    lines.append('|' + '---|' * len(cols))
    order = []
    for analyte in b['analytes']:
        for param in b['parameters']:
            order.append((analyte, param))
    pidx = dict((p, i) for i, p in enumerate(b['parameters']))
    aidx = dict((a, i) for i, a in enumerate(b['analytes']))
    extras = set(b['published_stats']) - set(order)
    for key in sorted(extras, key=lambda k: (aidx.get(k[0], len(aidx)),
                                             pidx.get(k[1], len(pidx)), k[0], k[1])):
        order.append(key)
    for analyte, param in order:
        pub = b['published_stats'].get((analyte, param))
        st = b['be_stats'].get(analyte, {}).get('parameters', {}).get(param)
        prow = ['', '', '', '']
        if pub is not None:
            prow = [num(pub.get('ratio_pct')), num(pub.get('ci_lower_pct')),
                    num(pub.get('ci_upper_pct')), str(pub.get('result') or '')]
        rrow = ['', '', '', '']
        if st is not None:
            rrow = [(num(x) if x is not None else '')
                    for x in (st['ratio_pct_r'], st['ci_lower_r'], st['ci_upper_r'])] + \
                   [st['result']]
        lines.append('| ' + ' | '.join([analyte, param] + prow + rrow) + ' |')
    with open(os.path.join(out, 'reconciliation.md'), 'w', encoding='utf-8',
              newline='\n') as f:
        f.write('\n'.join(lines) + '\n')


CONTRACT_ORDER = [
    'calibration_fits.json', 'standard_backcalc.tsv', 'qc_results.csv',
    'run_acceptance.csv', 'tube_results.psv', 'reported_concentrations.csv',
    'sampling_times.xml', 'isr_assessment.json', 'nca_parameters.csv',
    'lambda_z_selection.jsonl', 'be_statistics.json', 'be_summary.md',
    'analysis_populations.csv', 'excluded_subjects.jsonl', 'mean_profiles.csv',
    'dedup_report.json', 'source_lineage.json', 'alias_resolution.csv',
    'parameters_used.yaml', 'variance_vs_published.csv', 'reconciliation.md',
]


def write_all_reports(b, out):
    w_calibration_fits(b, out)
    w_standard_backcalc(b, out)
    w_qc_results(b, out)
    w_run_acceptance(b, out)
    w_tube_results(b, out)
    w_reported_concentrations(b, out)
    w_sampling_times(b, out)
    w_isr_assessment(b, out)
    w_nca_parameters(b, out)
    w_lambda_z_selection(b, out)
    w_be_statistics(b, out)
    w_be_summary(b, out)
    w_analysis_populations(b, out)
    w_excluded_subjects(b, out)
    w_mean_profiles(b, out)
    w_dedup_report(b, out)
    w_source_lineage(b, out)
    w_alias_resolution(b, out)
    w_parameters_used(b, out)
    w_variance_vs_published(b, out)
    w_reconciliation(b, out)
    files = []
    for name in CONTRACT_ORDER:
        path = os.path.join(out, name)
        data = open(path, 'rb').read()
        files.append({'name': name, 'bytes': len(data),
                      'sha256': hashlib.sha256(data).hexdigest()})
    write_json(os.path.join(out, 'manifest.json'), {'files': files})


def analyse(data_dir, out_dir):
    b = load_corpus(data_dir)
    resolve_records(b)
    compute_runs(b)
    compute_calibration(b)
    compute_results(b)
    compute_reported(b)
    compute_times(b)
    compute_nca(b)
    compute_populations(b)
    compute_stats(b)
    compute_mean_profiles(b)
    compute_isr(b)
    write_all_reports(b, out_dir)
    return b


def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: run_be.py DATA_DIR OUT_DIR\n')
        return 2
    data_dir = argv[1]
    out_dir = argv[2]
    if not os.path.isdir(data_dir):
        sys.stderr.write('data directory not found: %s\n' % data_dir)
        return 2
    os.makedirs(out_dir, exist_ok=True)
    analyse(data_dir, out_dir)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
