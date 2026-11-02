#!/usr/bin/env python3
"""VRX-BE-2614 bioequivalence rerun.

Usage: python3 run_be.py DATA_DIR OUT_DIR
"""
import csv
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
from datetime import datetime, timedelta
from fractions import Fraction

# --------------------------------------------------------------------------
# numeric helpers
# --------------------------------------------------------------------------

F0 = Fraction(0)


def to_frac(s):
    """Decimal string -> exact Fraction."""
    if s is None:
        return None
    s = str(s).strip()
    if s == '':
        return None
    neg = s.startswith('-')
    if s[0] in '+-':
        s = s[1:]
    if '/' in s:
        a, b = s.split('/', 1)
        v = Fraction(int(a), int(b))
        return -v if neg else v
    if 'e' in s.lower():
        m, e = re.split('[eE]', s)
        v = to_frac(m) * Fraction(10) ** int(e)
        return -v if neg else v
    if '.' in s:
        a, b = s.split('.', 1)
        a = a or '0'
        b = b or '0'
        v = Fraction(int(a) * 10 ** len(b) + int(b), 10 ** len(b))
    else:
        v = Fraction(int(s))
    return -v if neg else v


def _digits10(n):
    return len(str(n))


def round_sig(v, nd):
    """round a Fraction to nd significant digits, half away from zero"""
    if v is None:
        return None
    if v == 0:
        return F0
    sign = -1 if v < 0 else 1
    a = -v if v < 0 else v
    k = nd - _digits10(a.numerator) + _digits10(a.denominator)
    lo = Fraction(10) ** (nd - 1)
    hi = Fraction(10) ** nd
    while True:
        s = a * Fraction(10) ** k
        if s < lo:
            k += 1
        elif s >= hi:
            k -= 1
        else:
            break
    scaled = a * Fraction(10) ** k
    q, r = divmod(scaled.numerator, scaled.denominator)
    if 2 * r >= scaled.denominator:
        q += 1
    return sign * Fraction(q) / Fraction(10) ** k


def round_dp(v, nd):
    """round a Fraction to nd decimal places, half away from zero"""
    if v is None:
        return None
    sign = -1 if v < 0 else 1
    a = -v if v < 0 else v
    scaled = a * 10 ** nd
    q, r = divmod(scaled.numerator, scaled.denominator)
    if 2 * r >= scaled.denominator:
        q += 1
    return sign * Fraction(q, 10 ** nd)


def frac_sqrt(f):
    """sqrt of a non-negative Fraction, accurate to ~1e-60"""
    if f == 0:
        return F0
    scale = 10 ** 60
    n = f.numerator * scale * scale // f.denominator
    return Fraction(math.isqrt(n), scale)


def fmt_num(v, sig=6):
    """H21 number rendering"""
    if v is None:
        return ''
    if isinstance(v, bool):
        return 'Y' if v else 'N'
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        v = to_frac(repr(v))
    r = round_sig(v, sig)
    if r == 0:
        return '0'
    neg = r < 0
    a = -r if neg else r
    m = 0
    x = a
    while x.denominator != 1:
        x *= 10
        m += 1
    digits = str(x.numerator)
    if m == 0:
        s = digits
    else:
        digits = digits.rjust(m + 1, '0')
        s = digits[:-m] + '.' + digits[-m:]
        s = s.rstrip('0').rstrip('.')
        if s == '':
            s = '0'
    return ('-' if neg and s != '0' else '') + s


class Num(object):
    """marker carrying a pre-rendered number for the JSON writer"""

    __slots__ = ('s',)

    def __init__(self, s):
        self.s = s


def jnum(v, sig=6):
    if v is None:
        return None
    return Num(fmt_num(v, sig))


def jint(v):
    if v is None:
        return None
    return Num(str(int(v)))


def _jstr(s):
    return json.dumps(s, ensure_ascii=False)


def jdump(obj, indent=None, level=0):
    """JSON serialiser matching json.dumps conventions, number-exact"""
    if isinstance(obj, Num):
        return obj.s
    if obj is None:
        return 'null'
    if obj is True:
        return 'true'
    if obj is False:
        return 'false'
    if isinstance(obj, str):
        return _jstr(obj)
    if isinstance(obj, int):
        return str(obj)
    if isinstance(obj, dict):
        if not obj:
            return '{}'
        if indent is None:
            return '{' + ', '.join(
                _jstr(k) + ': ' + jdump(v, None) for k, v in obj.items()) + '}'
        pad = ' ' * (indent * (level + 1))
        inner = ',\n'.join(
            pad + _jstr(k) + ': ' + jdump(v, indent, level + 1)
            for k, v in obj.items())
        return '{\n' + inner + '\n' + ' ' * (indent * level) + '}'
    if isinstance(obj, (list, tuple)):
        if not obj:
            return '[]'
        if indent is None:
            return '[' + ', '.join(jdump(v, None) for v in obj) + ']'
        pad = ' ' * (indent * (level + 1))
        inner = ',\n'.join(pad + jdump(v, indent, level + 1) for v in obj)
        return '[\n' + inner + '\n' + ' ' * (indent * level) + ']'
    raise TypeError(repr(obj))


# --------------------------------------------------------------------------
# tiny YAML reader (block style)
# --------------------------------------------------------------------------

def _yaml_strip_comment(line):
    out = []
    q = None
    for i, ch in enumerate(line):
        if q:
            out.append(ch)
            if ch == q:
                q = None
            continue
        if ch in '"\'':
            q = ch
            out.append(ch)
        elif ch == '#' and (i == 0 or line[i - 1] in ' \t'):
            break
        else:
            out.append(ch)
    return ''.join(out).rstrip()


def _yaml_scalar(s):
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in '"\'':
        return s[1:-1]
    return s


def _yaml_flow(s):
    s = s.strip()[1:-1]
    out = {}
    for part in s.split(','):
        if ':' in part:
            k, v = part.split(':', 1)
            out[k.strip()] = _yaml_scalar(v)
    return out


def _yaml_lines(text):
    res = []
    for raw in text.split('\n'):
        line = _yaml_strip_comment(raw)
        if not line.strip() or line.strip() == '---':
            continue
        res.append((len(line) - len(line.lstrip(' ')), line.strip()))
    return res


def _yaml_parse(lines, i, ind):
    if lines[i][1].startswith('- '):
        return _yaml_list(lines, i, ind)
    return _yaml_map(lines, i, ind)


def _yaml_list(lines, i, ind):
    out = []
    while i < len(lines) and lines[i][0] == ind and lines[i][1].startswith('- '):
        content = lines[i][1][2:].strip()
        j = i + 1
        sub = []
        while j < len(lines) and lines[j][0] > ind:
            sub.append(lines[j])
            j += 1
        if content.startswith('{'):
            out.append(_yaml_flow(content))
        elif re.match(r'^[^:]+:(\s|$)', content):
            block = [(ind + 2, content)] + sub
            v, _ = _yaml_parse(block, 0, ind + 2)
            out.append(v)
        elif content == '':
            if sub:
                v, _ = _yaml_parse(sub, 0, sub[0][0])
                out.append(v)
        else:
            out.append(_yaml_scalar(content))
        i = j
    return out, i


def _yaml_map(lines, i, ind):
    out = {}
    while i < len(lines) and lines[i][0] == ind:
        line = lines[i][1]
        if line.startswith('- '):
            break
        k, _, v = line.partition(':')
        k = k.strip()
        v = v.strip()
        if v.startswith('{'):
            out[k] = _yaml_flow(v)
            i += 1
        elif v != '':
            out[k] = _yaml_scalar(v)
            i += 1
        elif (i + 1 < len(lines) and lines[i + 1][0] == ind
              and lines[i + 1][1].startswith('- ')):
            out[k], i = _yaml_list(lines, i + 1, ind)
        else:
            j = i + 1
            sub = []
            while j < len(lines) and lines[j][0] > ind:
                sub.append(lines[j])
                j += 1
            if sub:
                out[k], _ = _yaml_parse(sub, 0, sub[0][0])
            else:
                out[k] = ''
            i = j
    return out, i


def read_yaml(path):
    lines = _yaml_lines(open(path, encoding='utf-8').read())
    if not lines:
        return {}
    v, _ = _yaml_parse(lines, 0, lines[0][0])
    return v


# --------------------------------------------------------------------------
# governance memo (PDF)
# --------------------------------------------------------------------------

def _pdf_unescape(s):
    out = []
    i = 0
    while i < len(s):
        c = s[i]
        if c == '\\' and i + 1 < len(s):
            n = s[i + 1]
            if n in 'nrtbf':
                out.append({'n': '\n', 'r': '\r', 't': '\t', 'b': '\b',
                            'f': '\f'}[n])
                i += 2
            elif n.isdigit():
                j = i + 1
                oc = ''
                while j < len(s) and len(oc) < 3 and s[j].isdigit():
                    oc += s[j]
                    j += 1
                out.append(chr(int(oc, 8)))
                i = j
            else:
                out.append(n)
                i += 2
        else:
            out.append(c)
            i += 1
    return ''.join(out)


def _pdf_strings(seg):
    res = []
    i = 0
    while i < len(seg):
        if seg[i] == '(':
            depth = 1
            j = i + 1
            buf = ''
            while j < len(seg):
                if seg[j] == '\\':
                    buf += seg[j:j + 2]
                    j += 2
                    continue
                if seg[j] == '(':
                    depth += 1
                elif seg[j] == ')':
                    depth -= 1
                    if depth == 0:
                        break
                buf += seg[j]
                j += 1
            res.append(_pdf_unescape(buf))
            i = j + 1
        elif seg[i] == '<' and (i + 1 >= len(seg) or seg[i + 1] != '<'):
            j = seg.find('>', i)
            if j < 0:
                break
            h = re.sub(r'[^0-9A-Fa-f]', '', seg[i + 1:j])
            if len(h) % 2:
                h += '0'
            res.append(bytes.fromhex(h).decode('latin-1'))
            i = j + 1
        else:
            i += 1
    return res


def read_memo(path):
    data = open(path, 'rb').read()
    rows = []
    for m in re.finditer(rb'stream\r?\n', data):
        start = m.end()
        end = data.find(b'endstream', start)
        try:
            page = zlib.decompress(data[start:end]).decode('latin-1')
        except Exception:
            continue
        cells = {}
        for bt in re.finditer(r'BT(.*?)ET', page, re.S):
            body = bt.group(1)
            tm = re.search(r'([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+'
                           r'([-\d.]+)\s+([-\d.]+)\s+Tm', body)
            if not tm:
                continue
            x = float(tm.group(5))
            y = float(tm.group(6))
            cells.setdefault(y, []).append(
                (x, ''.join(_pdf_strings(body[tm.end():]))))
        for y in sorted(cells, reverse=True):
            rows.append([t for _, t in sorted(cells[y], key=lambda p: p[0])])

    tables = {}
    cur = None
    want_header = False
    for row in rows:
        c0 = row[0].strip()
        if c0.startswith('Governance memo') or c0.startswith('End of memo'):
            continue
        m = re.match(r'^Table ([A-Z]-\d+) \(continued\)$', c0)
        if m:
            cur = m.group(1)
            want_header = True
            continue
        m = re.match(r'^Table ([A-Z]-\d+):\s*(.*)$', c0)
        if m:
            cur = m.group(1)
            title = m.group(2)
            st = re.search(r'\[([^\]]+)\]\s*$', title)
            tables[cur] = {'status': st.group(1).strip() if st else '',
                           'title': title, 'header': None, 'rows': []}
            want_header = True
            continue
        if cur is None or cur not in tables:
            continue
        t = tables[cur]
        if want_header:
            if t['header'] is None:
                t['header'] = [c.strip() for c in row]
            want_header = False
            continue
        if t['header'] is None:
            continue
        if len(row) != len(t['header']):
            cur = None
            continue
        t['rows'].append(dict(zip(t['header'], [c.strip() for c in row])))
    return tables


# --------------------------------------------------------------------------
# workbook (xlsx)
# --------------------------------------------------------------------------

XNS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
XRNS = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'


def _colnum(c):
    n = 0
    for ch in c:
        n = n * 26 + ord(ch) - 64
    return n


def read_workbook(path):
    z = zipfile.ZipFile(path)
    wb = ET.fromstring(z.read('xl/workbook.xml'))
    pr = wb.find(XNS + 'workbookPr')
    d1904 = False
    if pr is not None:
        d1904 = (pr.get('date1904') or '').strip().lower() in ('1', 'true')
    rels = {}
    for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels')):
        rels[r.get('Id')] = r.get('Target')
    shared = []
    if 'xl/sharedStrings.xml' in z.namelist():
        for si in ET.fromstring(z.read('xl/sharedStrings.xml')):
            shared.append(''.join(t.text or '' for t in si.iter(XNS + 't')))
    sheets = {}
    for sh in wb.find(XNS + 'sheets'):
        target = rels[sh.get(XRNS + 'id')]
        if not target.startswith('xl/'):
            target = 'xl/' + target.lstrip('/')
        ws = ET.fromstring(z.read(target))
        rows = []
        for row in ws.iter(XNS + 'row'):
            cells = {}
            for c in row.iter(XNS + 'c'):
                col = re.match(r'([A-Z]+)', c.get('r')).group(1)
                if c.get('t') == 'inlineStr':
                    val = ''.join(x.text or '' for x in c.iter(XNS + 't'))
                else:
                    v = c.find(XNS + 'v')
                    val = v.text if v is not None and v.text is not None else ''
                    if c.get('t') == 's' and val != '':
                        val = shared[int(val)]
                cells[col] = val
            rows.append(cells)
        sheets[sh.get('name')] = rows
    return {'date1904': d1904, 'sheets': sheets}


HEADER_FIRSTS = ('run_id', 'lot', 'subject')


def sheet_table(rows):
    head = None
    for i, r in enumerate(rows):
        if not r:
            continue
        cols = sorted(r, key=_colnum)
        if (r[cols[0]] or '').strip().lower() in HEADER_FIRSTS:
            head = i
            break
    if head is None:
        return []
    hrow = rows[head]
    cols = sorted(hrow, key=_colnum)
    header = [(hrow[c] or '').strip() for c in cols]
    out = []
    for r in rows[head + 1:]:
        if not r:
            continue
        rec = {}
        for c, h in zip(cols, header):
            rec[h] = (r.get(c) or '').strip()
        if any(v for v in rec.values()):
            out.append(rec)
    return out


def serial_date(serial, d1904):
    n = int(to_frac(serial))
    base = datetime(1904, 1, 1) if d1904 else datetime(1899, 12, 30)
    return (base + timedelta(days=n)).strftime('%Y-%m-%d')


# --------------------------------------------------------------------------
# injection shard readers (feed_layouts.md)
# --------------------------------------------------------------------------

KIND_A = {'STD': 'STD', 'QC': 'QC', 'DQC': 'DQC', 'UNK': 'UNK',
          'BLANK': 'BLANK', 'ZERO': 'ZERO'}
KIND_WORDS = {'STANDARD': 'STD', 'QC': 'QC', 'DILQC': 'DQC',
              'UNKNOWN': 'UNK', 'BLANK': 'BLANK', 'ZERO': 'ZERO'}
KIND_SAMPLE = {'STD': 'STD', 'QC': 'QC', 'DQC': 'DQC', 'SAMPLE': 'UNK',
               'BLANK': 'BLANK', 'ZERO': 'ZERO'}
KIND_CAL = {'CAL': 'STD', 'QC': 'QC', 'DILQC': 'DQC', 'STUDY': 'UNK',
            'BLANK': 'BLANK', 'ZERO': 'ZERO'}
KIND_LETTER = {'S': 'STD', 'Q': 'QC', 'D': 'DQC', 'U': 'UNK', 'B': 'BLANK',
               'Z': 'ZERO'}
KIND_BLK = {'STD': 'STD', 'QC': 'QC', 'DQC': 'DQC', 'UNK': 'UNK',
            'BLK': 'BLANK', 'ZERO': 'ZERO'}

INTEG = {'A': 'AUTO', 'M': 'MANUAL', 'AUTO': 'AUTO', 'MANUAL': 'MANUAL'}


def _tok(v):
    if v is None:
        return ''
    return str(v).strip().upper()


def _dil(v):
    s = _tok(v)
    if s == '':
        return 1
    if s.startswith('X'):
        return int(to_frac(s[1:]))
    if ':' in s:
        return int(to_frac(s.split(':', 1)[1]))
    return int(to_frac(s))


def _count(v, kilo=False, comma=False):
    s = str(v if v is not None else '').strip()
    if s == '':
        return None
    if comma:
        s = s.replace('.', '').replace(',', '.')
    f = to_frac(s)
    if f is None:
        return None
    if kilo:
        f = f * 1000
    q, r = divmod(f.numerator, f.denominator)
    if 2 * r >= f.denominator:
        q += 1
    return q


def _rec(inj, run, seq, kind, ref, dil, a, i_s, integ, rev, void):
    return {'inj': _tok(inj), 'run_tok': _tok(run), 'seq': int(to_frac(seq)),
            'kind': kind, 'ref': _tok(ref), 'dil': dil, 'a_area': a,
            'is_area': i_s, 'integ': integ, 'rev': int(to_frac(rev)),
            'void': bool(void)}


def _delim(path, sep):
    with open(path, newline='', encoding='utf-8') as fh:
        for row in csv.DictReader(fh, delimiter=sep):
            yield {(k.strip() if k else k): (v.strip() if isinstance(v, str) else v)
                   for k, v in row.items()}


def read_i_csv(path):
    out = []
    for r in _delim(path, ','):
        out.append(_rec(r['injection_id'], r['run_ref'], r['seq'],
                        KIND_A.get(_tok(r['sample_type'])), r['sample_ref'],
                        _dil(r['dilution']), _count(r['analyte_area']),
                        _count(r['is_area']), INTEG.get(_tok(r['integration'])),
                        r['revision'], _tok(r['state']) == 'VOID'))
    return out


def read_i_tsv(path):
    out = []
    for r in _delim(path, '\t'):
        out.append(_rec(r['INJ'], r['RUN'], r['SEQ'],
                        KIND_WORDS.get(_tok(r['TYPE'])), r['REF'],
                        _dil(r['DIL']), _count(r['A_AREA']), _count(r['IS_AREA']),
                        INTEG.get(_tok(r['INTEG'])), r['REV'],
                        _tok(r['ST']) == '9'))
    return out


def read_i_psv(path):
    out = []
    for r in _delim(path, '|'):
        out.append(_rec(r['inj'], r['run'], r['seq'], KIND_A.get(_tok(r['kind'])),
                        r['ref'], _dil(r['df']), _count(r['area_counts']),
                        _count(r['is_area_kcounts'], kilo=True),
                        INTEG.get(_tok(r['int'])), r['rev'],
                        _tok(r['status']) == 'DEAD'))
    return out


def read_i_jsonl(path):
    out = []
    for line in open(path, encoding='utf-8'):
        if not line.strip():
            continue
        r = json.loads(line)
        out.append(_rec(r['injectionId'], r['runRef'], r['seqNo'],
                        KIND_SAMPLE.get(_tok(r['sampleType'])), r['sampleRef'],
                        _dil(r['dilutionFactor']), _count(r['analyteArea']),
                        _count(r['isArea']), INTEG.get(_tok(r['integration'])),
                        r['revision'], _tok(r['status']) == 'VOID'))
    return out


def read_i_ndjson(path):
    out = []
    for line in open(path, encoding='utf-8'):
        if not line.strip():
            continue
        r = json.loads(line)
        v = r.get('void')
        if isinstance(v, str):
            v = _tok(v) == 'TRUE'
        out.append(_rec(r['id'], r['run'], r['order'],
                        KIND_CAL.get(_tok(r['sample']['type'])),
                        r['sample']['ref'], _dil(r['sample']['df']),
                        _count(r['areas']['analyte']), _count(r['areas']['istd']),
                        INTEG.get(_tok(r['proc']['mode'])), r['proc']['rev'],
                        bool(v)))
    return out


def read_i_xml(path):
    out = []
    root = ET.parse(path).getroot()
    for e in root.iter('inj'):
        a = i_s = None
        for ar in e.iter('area'):
            if _tok(ar.get('kind')) == 'ANALYTE':
                a = _count(ar.text)
            elif _tok(ar.get('kind')) == 'ISTD':
                i_s = _count(ar.text)
        out.append(_rec(e.get('id'), e.get('run'), e.get('seq'),
                        KIND_A.get(_tok(e.get('type'))), e.get('ref'),
                        _dil(e.get('df')), a, i_s,
                        INTEG.get(_tok(e.get('integ'))), e.get('rev'),
                        _tok(e.get('status')) == 'VOIDED'))
    return out


def read_i_sqlite(path):
    out = []
    con = sqlite3.connect(path)
    for r in con.execute('select inj_id, run_token, seq, stype, sref, dil, '
                         'a_area, is_area, integ, rev, voided from injection'):
        out.append(_rec(r[0], r[1], r[2], KIND_LETTER.get(_tok(r[3])), r[4],
                        _dil(r[5]), _count(r[6]), _count(r[7]),
                        INTEG.get(_tok(r[8])), r[9], int(r[10] or 0) == 1))
    con.close()
    return out


def read_i_db(path):
    out = []
    con = sqlite3.connect(path)
    areas = {}
    for inj_id, rev, chan, val in con.execute(
            'select inj_id, rev, channel, value from area'):
        areas.setdefault((_tok(inj_id), int(rev)), {})[_tok(chan)] = _count(val)
    for r in con.execute('select id, run, seq, stype, sref, dil, integ, rev, '
                         'flag from inj'):
        ar = areas.get((_tok(r[0]), int(r[7])), {})
        out.append(_rec(r[0], r[1], r[2], KIND_BLK.get(_tok(r[3])), r[4],
                        _dil(r[5]), ar.get('A'), ar.get('IS'),
                        INTEG.get(_tok(r[6])), r[7], _tok(r[8]) == 'X'))
    con.close()
    return out


def read_i_json(path):
    out = []
    doc = json.load(open(path, encoding='utf-8'))
    cols = [c.strip() for c in doc['export']['columns']]
    for row in doc['export']['rows']:
        r = dict(zip(cols, row))
        out.append(_rec(r['inj'], r['run'], r['seq'],
                        KIND_WORDS.get(_tok(r['type'])), r['ref'],
                        _dil(r['df']), _count(r['area_analyte']),
                        _count(r['area_istd']), INTEG.get(_tok(r['integration'])),
                        r['rev'], _tok(r['state']) == 'RETRACTED'))
    return out


def read_i_yaml(path):
    out = []
    doc = read_yaml(path)
    for r in doc.get('injections', []):
        out.append(_rec(r['inj'], r['run'], r['seq'], KIND_A.get(_tok(r['type'])),
                        r['ref'], _dil(r['df']), _count(r['area_a']),
                        _count(r['area_is']), INTEG.get(_tok(r['integ'])),
                        r['rev'], _tok(r['st']) == 'V'))
    return out


def read_i_yml(path):
    out = []
    doc = read_yaml(path)
    for r in doc.get('records', []):
        out.append(_rec(r['injection'], r['batch'], r['position'],
                        KIND_A.get(_tok(r['kind'])), r['label'],
                        _dil(r['dilution']), _count(r['analyte_counts']),
                        _count(r['istd_kcounts'], kilo=True),
                        INTEG.get(_tok(r['mode'])), r['revision'],
                        _tok(r['state']) == 'CXL'))
    return out


def read_i_txt(path):
    out = []
    for line in open(path, encoding='utf-8'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        r = {}
        for part in line.split(';'):
            if '=' in part:
                k, v = part.split('=', 1)
                r[k.strip()] = v.strip()
        out.append(_rec(r['INJ'], r['RUN'], r['SEQ'], KIND_A.get(_tok(r['TYPE'])),
                        r['REF'], _dil(r['DF']), _count(r['AREA']),
                        _count(r['ISAREA']), INTEG.get(_tok(r['MODE'])),
                        r['REV'], _tok(r['ST']) == 'X'))
    return out


def read_i_csvsemi(path):
    out = []
    for r in _delim(path, ';'):
        out.append(_rec(r['Injection'], r['Batch'], r['Pos'],
                        KIND_A.get(_tok(r['Type'])), r['Sample'],
                        _dil(r['Dilution']),
                        _count(r['Area (kcounts)'], kilo=True, comma=True),
                        _count(r['IS Area (kcounts)'], kilo=True, comma=True),
                        INTEG.get(_tok(r['Integration'])), r['Rev'],
                        _tok(r['Valid']) == 'N'))
    return out


def read_i_tsv2(path):
    out = []
    for r in _delim(path, '\t'):
        out.append(_rec(r['injection'], r['run'], r['seq'],
                        KIND_A.get(_tok(r['type'])), r['ref'], _dil(r['df']),
                        _count(r['analyte_area']), _count(r['is_area']),
                        INTEG.get(_tok(r['integration'])), r['revision'],
                        _tok(r['status']) == 'VOID'))
    return out


def read_i_jsonl2(path):
    out = []
    for line in open(path, encoding='utf-8'):
        if not line.strip():
            continue
        r = json.loads(line)
        out.append(_rec(r['inj'], r['run'], r['seq'], KIND_A.get(_tok(r['type'])),
                        r['ref'], _dil(r['df']), _count(r['a']), _count(r['is']),
                        INTEG.get(_tok(r['mode'])), r['rev'],
                        _tok(r['st']) == 'VOID'))
    return out


def read_i_psv2(path):
    out = []
    for r in _delim(path, '|'):
        out.append(_rec(r['inj'], r['run'], r['pos'],
                        KIND_LETTER.get(_tok(r['t'])), r['ref'], _dil(r['df']),
                        _count(r['area']), _count(r['is_area']),
                        INTEG.get(_tok(r['integ'])), r['rev'],
                        _tok(r['keep']) == 'DROP'))
    return out


LAYOUTS = {
    'i_csv': read_i_csv, 'i_tsv': read_i_tsv, 'i_psv': read_i_psv,
    'i_jsonl': read_i_jsonl, 'i_ndjson': read_i_ndjson, 'i_xml': read_i_xml,
    'i_sqlite': read_i_sqlite, 'i_db': read_i_db, 'i_json': read_i_json,
    'i_yaml': read_i_yaml, 'i_yml': read_i_yml, 'i_txt': read_i_txt,
    'i_csvsemi': read_i_csvsemi, 'i_tsv2': read_i_tsv2,
    'i_jsonl2': read_i_jsonl2, 'i_psv2': read_i_psv2,
}


# --------------------------------------------------------------------------
# reference token parsing (H5 / feed_layouts)
# --------------------------------------------------------------------------

QC_LEVEL = {
    'LQC': 'LQC', 'QC-L': 'LQC', 'LOW': 'LQC', 'QCL': 'LQC',
    'MQC': 'MQC', 'QC-M': 'MQC', 'MID': 'MQC', 'QCM': 'MQC',
    'HQC': 'HQC', 'QC-H': 'HQC', 'HIGH': 'HQC', 'QCH': 'HQC',
    'DQC': 'DQC', 'QC-D': 'DQC', 'DIL': 'DQC', 'QCD': 'DQC',
}


def std_level(ref):
    m = re.match(r'^(?:CS|STD-|L|CAL\s*)(\d)$', ref)
    if m:
        return 'CS' + m.group(1)
    return None


# --------------------------------------------------------------------------
# instants and the site calendar (H13)
# --------------------------------------------------------------------------

EPOCH = datetime(1970, 1, 1)


def _secs(dt):
    return int((dt - EPOCH).total_seconds())


def parse_wall(s):
    """site wall clock without an offset -> seconds as if UTC"""
    s = (s or '').strip()
    if not s:
        return None
    s = s.replace('T', ' ')
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'):
        try:
            return _secs(datetime.strptime(s, fmt))
        except ValueError:
            pass
    return None


def off_secs(s):
    s = (s or '').strip()
    if s in ('', 'Z'):
        return 0
    sign = -1 if s[0] == '-' else 1
    body = s[1:] if s[0] in '+-' else s
    body = body.replace(':', '')
    return sign * (int(body[:2]) * 3600 + int(body[2:4]) * 60)


def parse_iso(s):
    s = (s or '').strip()
    if not s:
        return None
    m = re.match(r'^(\d{4}-\d\d-\d\d)[T ](\d\d:\d\d(?::\d\d)?)'
                 r'(Z|[+-]\d\d:?\d\d)?$', s)
    if not m:
        return None
    base = parse_wall(m.group(1) + ' ' + m.group(2))
    return base - off_secs(m.group(3) or 'Z')


def fmt_instant(sec):
    if sec is None:
        return ''
    return (EPOCH + timedelta(seconds=sec)).strftime('%Y-%m-%dT%H:%M:%SZ')


class SiteCalendar(object):
    def __init__(self, doc):
        self.base = off_secs(doc.get('base_offset'))
        trs = []
        for t in doc.get('transitions') or []:
            trs.append((parse_iso(t['at_utc']), off_secs(t['offset_after'])))
        self.trs = sorted(trs)

    def offset_at(self, instant):
        off = self.base
        for at, o in self.trs:
            if at <= instant:
                off = o
            else:
                break
        return off

    def to_utc(self, wall):
        if wall is None:
            return None
        cands = []
        for o in dict.fromkeys([self.base] + [o for _, o in self.trs]):
            t = wall - o
            if self.offset_at(t) == o:
                cands.append(t)
        if cands:
            return min(cands)
        prev = self.base
        for at, o in self.trs:
            if o > prev and at + prev <= wall < at + o:
                return wall - prev
            prev = o
        return wall - self.base


# --------------------------------------------------------------------------
# calibration algebra (H6)
# --------------------------------------------------------------------------

def fit_curve(points, model, weighting):
    """points: list of (x Fraction, y Fraction); exact weighted least squares"""
    deg = 2 if model == 'linear' else 3
    mats = [[F0] * deg for _ in range(deg)]
    rhs = [F0] * deg
    for x, y in points:
        w = Fraction(1, 1) / (x * x) if weighting == '1/x^2' else Fraction(1, 1) / x
        basis = [Fraction(1), x] if deg == 2 else [Fraction(1), x, x * x]
        for i in range(deg):
            for j in range(deg):
                mats[i][j] += w * basis[i] * basis[j]
            rhs[i] += w * basis[i] * y
    sol = solve(mats, rhs)
    if sol is None:
        return None
    coeffs = [round_sig(v, 6) for v in sol]
    if deg == 2:
        return {'a': coeffs[0], 'b': coeffs[1], 'c': None}
    return {'a': coeffs[0], 'b': coeffs[1], 'c': coeffs[2]}


def solve(m, r):
    n = len(m)
    a = [row[:] + [r[i]] for i, row in enumerate(m)]
    for col in range(n):
        piv = None
        for row in range(col, n):
            if a[row][col] != 0:
                piv = row
                break
        if piv is None:
            return None
        a[col], a[piv] = a[piv], a[col]
        pv = a[col][col]
        a[col] = [v / pv for v in a[col]]
        for row in range(n):
            if row != col and a[row][col] != 0:
                f = a[row][col]
                a[row] = [v - f * w for v, w in zip(a[row], a[col])]
    return [a[i][n] for i in range(n)]


def read_back(y, coef):
    """H6 back-calculation; returns a Fraction or None"""
    if y is None or coef is None:
        return None
    a, b, c = coef['a'], coef['b'], coef['c']
    if c is None:
        if b == 0:
            return None
        return (y - a) / b
    rad = b * b + 4 * c * (y - a)
    if rad < 0:
        return None
    den = b + frac_sqrt(rad)
    if den == 0:
        return None
    return 2 * (y - a) / den


# --------------------------------------------------------------------------
# corpus loading
# --------------------------------------------------------------------------

class Corpus(object):
    def __init__(self, d):
        self.dir = d
        p = lambda *a: os.path.join(d, *a)
        self.profile = read_yaml(p('analysis_profile_be.yml'))
        self.catalog = json.load(open(p('ingest_catalog_be.json'), encoding='utf-8'))
        self.memo = read_memo(p('ba_stat_governance_memo.pdf'))
        self.wb = read_workbook(p('bioanalytical_workbook_v3.xlsx'))
        self.calendar = SiteCalendar(read_yaml(p('site_calendar.yml')))
        self.study = self.profile['study_id']

        self.analytes = [a.strip().upper() for a in self.profile['analytes']]
        self.pivotal = [a.strip().upper() for a in self.profile['pivotal_analytes']]
        self.parameters = [x.strip() for x in self.profile['parameters']]
        self.alpha = to_frac(self.profile['alpha'])
        self.be_lower = to_frac(self.profile['be_lower_pct'])
        self.be_upper = to_frac(self.profile['be_upper_pct'])
        self.lz_min = int(to_frac(self.profile['lambda_z_min_points']))
        self.lz_tol = to_frac(self.profile['lambda_z_adj_r2_tolerance'])
        self.extrap_limit = to_frac(self.profile['extrap_limit_pct'])
        self.carryover_limit = to_frac(self.profile['carryover_limit_pct'])
        self.emesis_factor = to_frac(self.profile['emesis_window_factor'])
        self.isr_limit = to_frac(self.profile['isr_limit_pct'])
        self.in_scope = [s.strip().upper() for s in self.profile['subjects_in_scope']]
        self.in_scope_set = set(self.in_scope)
        self.nominal_sheet = self.profile['nominal_sheet']

        self._memo_tables()
        self._workbook()
        self._aliases(p)
        self._clinical(p)
        self._lab(p)

    # -- memo ----------------------------------------------------------
    def _pick(self, letter, keyword=None):
        best = None
        for tid, t in self.memo.items():
            if not tid.startswith(letter + '-'):
                continue
            if t['status'].upper() != 'IN FORCE':
                continue
            if keyword and keyword.lower() not in t['title'].lower():
                continue
            if best is None or tid < best:
                best = tid
        return best

    def _memo_tables(self):
        self.t_conventions = self._pick('P')
        self.t_method = self._pick('M')
        self.t_tquant = self._pick('T')
        c_manual = self._pick('C', 'manual integration')
        c_assign = self._pick('C', 'assignable')
        self.t_emesis = self._pick('E')
        r_id = None
        for tid in self.memo:
            if tid.startswith('R-'):
                r_id = tid if r_id is None else min(r_id, tid)
        self.t_rulings = r_id

        self.method = {}
        for row in self.memo[self.t_method]['rows']:
            self.method[row['analyte'].strip().upper()] = {
                'model': row['model'].strip().lower(),
                'weighting': row['weighting'].strip(),
                'std_limit_pct': to_frac(row['std_limit_pct']),
                'lloq_std_limit_pct': to_frac(row['lloq_std_limit_pct']),
                'qc_limit_pct': to_frac(row['qc_limit_pct']),
                'dqc_limit_pct': to_frac(row['dqc_limit_pct']),
                'min_std_fraction': to_frac(row['min_std_fraction']),
                'min_levels': int(to_frac(row['min_levels'])),
                'min_qc_fraction': to_frac(row['min_qc_fraction']),
                'min_qc_level_fraction': to_frac(row['min_qc_level_fraction']),
            }
        self.manual_codes = {r['code'].strip().upper(): r['allowed'].strip().upper()
                             for r in self.memo[c_manual]['rows']}
        self.assign_codes = {r['code'].strip().upper(): r['allowed'].strip().upper()
                             for r in self.memo[c_assign]['rows']}
        self.emesis_terms = set()
        for r in self.memo[self.t_emesis]['rows']:
            if r['counts_as_emesis'].strip().upper() == 'Y':
                self.emesis_terms.add(r['preferred_term'].strip().upper())
        tt = self.memo[self.t_tquant]
        pcol = None
        want = fmt_num(1 - self.alpha)
        for h in tt['header']:
            if h.startswith('p='):
                if to_frac(h[2:]) == 1 - self.alpha:
                    pcol = h
        self.t_table = {}
        if pcol:
            for r in tt['rows']:
                self.t_table[int(to_frac(r['df']))] = to_frac(r[pcol])
        self.t_p = want
        self.rulings = []
        for r in self.memo[self.t_rulings]['rows']:
            self.rulings.append({
                'id': r['ruling_id'].strip(), 'study': r['study'].strip(),
                'action': r['action'].strip().upper(),
                'target': r['target'].strip().upper(),
                'status': r['status'].strip().upper()})

    # -- workbook ------------------------------------------------------
    def _workbook(self):
        sh = self.wb['sheets']
        d1904 = self.wb['date1904']
        self.runplan = []
        for r in sheet_table(sh['RunPlan']):
            if r.get('study', '').strip() != self.study:
                continue
            self.runplan.append({
                'run_id': r['run_id'].strip().upper(),
                'analyte': r['analyte'].strip().upper(),
                'run_type': r['run_type'].strip().upper(),
                'cal_lot': r['cal_lot'].strip().upper(),
                'qc_lot': r['qc_lot'].strip().upper(),
                'analysis_date': serial_date(r['analysis_date'], d1904)})
        self.nominals = {}
        for r in sheet_table(sh[self.nominal_sheet]):
            self.nominals[(r['lot'].strip().upper(), r['level'].strip().upper())] = \
                to_frac(r['certified'])
        self.qclots = {}
        for r in sheet_table(sh['QCLots']):
            self.qclots[(r['lot'].strip().upper(), r['level'].strip().upper())] = \
                to_frac(r['certified'])
        self.randomization = []
        for r in sheet_table(sh['Randomization']):
            self.randomization.append({'subject': r['subject'].strip().upper(),
                                       'sequence': r['sequence'].strip().upper()})
        self.rand_subjects = [r['subject'] for r in self.randomization]
        self.rand_set = set(self.rand_subjects)
        self.sequence = {r['subject']: r['sequence'] for r in self.randomization}

    # -- aliases -------------------------------------------------------
    def _aliases(self, p):
        con = sqlite3.connect(p('entity_alias_register.sqlite'))
        self.run_alias = {}
        for tok, rid, _src in con.execute('select token, run_id, source from run_alias'):
            self.run_alias[_tok(tok)] = _tok(rid)
        self.subject_alias = {}
        for tok, sid, study in con.execute(
                'select token, subject_id, study from subject_alias'):
            if (study or '').strip() != self.study:
                continue
            self.subject_alias[_tok(tok)] = _tok(sid)
        con.close()
        self.runplan_ids = set(r['run_id'] for r in self.runplan)
        self._run_cache = {}
        self._subj_cache = {}
        self._tube_cache = {}

    def resolve_run(self, token):
        t = _tok(token)
        if t in self._run_cache:
            return self._run_cache[t]
        if t in self.run_alias:
            v = self.run_alias[t]
        elif t in self.runplan_ids:
            v = t
        else:
            v = None
        self._run_cache[t] = v
        return v

    def resolve_subject(self, token):
        t = _tok(token)
        if t in self._subj_cache:
            return self._subj_cache[t]
        seen = set()
        cur = t
        res = None
        while True:
            if cur in self.rand_set:
                res = cur
                break
            if cur in seen or cur not in self.subject_alias:
                break
            seen.add(cur)
            cur = self.subject_alias[cur]
        self._subj_cache[t] = res
        return res

    def resolve_tube(self, token):
        t = _tok(token)
        if t in self._tube_cache:
            return self._tube_cache[t]
        seen = set()
        cur = t
        while cur in self.relabel and cur not in seen:
            seen.add(cur)
            cur = self.relabel[cur]
        self._tube_cache[t] = cur
        return cur

    # -- clinical ------------------------------------------------------
    def _clinical(self, p):
        root = ET.parse(p('tube_relabel_journal.xml')).getroot()
        rstudy = (root.get('study') or '').strip()
        self.relabel = {}
        self.relabel_rows = []
        for e in root.iter('relabel'):
            st = (e.get('study') or rstudy).strip()
            self.relabel_rows.append(e)
            if st != self.study:
                continue
            if _tok(e.get('status')) != 'ACTIVE':
                continue
            self.relabel[_tok(e.get('new'))] = _tok(e.get('old'))

        self.tubes = {}
        with open(p('tube_manifest_main.csv'), newline='', encoding='utf-8') as fh:
            for r in csv.DictReader(fh):
                nom = r['nominal_h'].strip()
                tid = _tok(r['tube_id'])
                if tid in self.tubes:
                    continue
                self.tubes[tid] = {
                    'tube': tid, 'subject_token': _tok(r['subject']),
                    'period': int(to_frac(r['period'])),
                    'nominal': F0 if _tok(nom) == 'PRE' else to_frac(nom),
                    'status': _tok(r['status'])}
        add = read_yaml(p('tube_manifest_addendum.yaml'))
        for r in add.get('tubes') or []:
            tid = _tok(r['tube'])
            if tid in self.tubes:
                continue
            nom = _tok(r['nominal_h'])
            self.tubes[tid] = {
                'tube': tid, 'subject_token': _tok(r['subject']),
                'period': int(to_frac(r['period'])),
                'nominal': None if nom == 'UNS' else (F0 if nom == 'PRE'
                                                      else to_frac(nom)),
                'status': _tok(r['status'])}
        for t in self.tubes.values():
            t['subject'] = self.resolve_subject(t['subject_token'])

        # dose instants
        self.dose = {}
        self.dose_subject_tokens = []
        with open(p('dose_admin_p1.csv'), newline='', encoding='utf-8') as fh:
            for r in csv.DictReader(fh):
                self.dose_subject_tokens.append(_tok(r['subject']))
                if _tok(r['event']) != 'DOSE':
                    continue
                s = self.resolve_subject(r['subject'])
                if s is None:
                    continue
                inst = self.calendar.to_utc(parse_wall(r['local_time']))
                self.dose[(s, int(to_frac(r['period'])))] = inst
        droot = ET.parse(p('dose_admin_p2.xml')).getroot()
        dper = droot.get('period')
        for e in droot.iter('event'):
            self.dose_subject_tokens.append(_tok(e.get('subject')))
            if _tok(e.get('type')) != 'DOSE':
                continue
            s = self.resolve_subject(e.get('subject'))
            if s is None:
                continue
            per = int(to_frac(e.get('period') or dper))
            self.dose[(s, per)] = parse_iso(e.get('at'))

        # logged draw times
        self.draw_logged = {}
        self.draw_subject_tokens = []
        with open(p('draw_times_g1.tsv'), newline='', encoding='utf-8') as fh:
            for r in csv.DictReader(fh, delimiter='\t'):
                self.draw_subject_tokens.append(_tok(r['subject']))
                tid = _tok(r['tube'])
                v = (r['drawn_local'] or '').strip()
                self.draw_logged.setdefault(
                    tid, self.calendar.to_utc(parse_wall(v)) if v else None)
        for line in open(p('draw_times_g2.jsonl'), encoding='utf-8'):
            if not line.strip():
                continue
            r = json.loads(line)
            self.draw_subject_tokens.append(_tok(r['subj']))
            tid = _tok(r['tube'])
            v = r.get('drawn_at')
            self.draw_logged.setdefault(tid, parse_iso(v) if v else None)

        # correction journal
        self.corrections = {}
        for line in open(p('draw_time_corrections.ndjson'), encoding='utf-8'):
            if not line.strip():
                continue
            r = json.loads(line)
            if (r.get('field') or '').strip().lower() != 'drawn_local':
                continue
            if _tok(r.get('status')) != 'POSTED':
                continue
            self.corrections.setdefault(_tok(r['tube']), []).append({
                'seq': int(to_frac(r['seq'])),
                'action': _tok(r.get('action') or 'SET') or 'SET',
                'value': (r.get('value') or '').strip(),
                'reverses': (int(to_frac(r['reverses']))
                             if r.get('reverses') not in (None, '') else None)})
        self.draw_instant = {}
        for tid in set(list(self.draw_logged) + list(self.corrections)):
            self.draw_instant[tid] = self._draw_for(tid)

        # adverse events
        con = sqlite3.connect(p('ae_listing.db'))
        self.ae = []
        self.ae_subject_tokens = []
        for r in con.execute('select ae_id, study, subject, period, pt, '
                             'onset_local from ae_events'):
            if (r[1] or '').strip() != self.study:
                continue
            self.ae_subject_tokens.append(_tok(r[2]))
            self.ae.append({'id': r[0], 'subject': self.resolve_subject(r[2]),
                            'period': int(to_frac(r[3])),
                            'pt': (r[4] or '').strip(),
                            'onset': self.calendar.to_utc(parse_wall(r[5]))})
        con.close()

        # disposition
        self.withdrawn = set()
        self.disp_subject_tokens = []
        with open(p('subject_disposition.psv'), newline='', encoding='utf-8') as fh:
            for r in csv.DictReader(fh, delimiter='|'):
                self.disp_subject_tokens.append(_tok(r['subject']))
                if _tok(r['event']) == 'WITHDRAWN':
                    s = self.resolve_subject(r['subject'])
                    if s:
                        self.withdrawn.add(s)

    def _draw_for(self, tid):
        entries = self.corrections.get(tid, [])
        in_effect = {}
        for e in sorted(entries, key=lambda x: -x['seq']):
            killed = any(o['action'] == 'REVERSE' and o['reverses'] == e['seq']
                         and in_effect.get(o['seq']) for o in entries
                         if o['seq'] > e['seq'])
            in_effect[e['seq']] = not killed
        sets = [e for e in entries if e['action'] == 'SET' and in_effect[e['seq']]]
        if sets:
            e = max(sets, key=lambda x: x['seq'])
            if e['value'] == '':
                return None
            return self.calendar.to_utc(parse_wall(e['value']))
        return self.draw_logged.get(tid)

    # -- lab -----------------------------------------------------------
    def _lab(self, p):
        con = sqlite3.connect(p('integration_audit_trail.db'))
        latest = {}
        for r in con.execute('select injection_ref, revision, reason_code, '
                             'status, ts from audit_entry'):
            key = (_tok(r[0]), int(r[1]))
            ts = (r[4] or '').strip()
            if key not in latest or ts > latest[key][0]:
                latest[key] = (ts, _tok(r[2]), _tok(r[3]))
        con.close()
        self.audit = latest

        self.std_requests = []
        for line in open(p('std_exclusion_requests.jsonl'), encoding='utf-8'):
            if not line.strip():
                continue
            r = json.loads(line)
            self.std_requests.append({'run_token': _tok(r['run']),
                                      'injection': _tok(r['injection']),
                                      'code': _tok(r['code']),
                                      'status': _tok(r['status'])})
        self.reassay = []
        with open(p('reassay_request_log.csv'), newline='', encoding='utf-8') as fh:
            for r in csv.DictReader(fh):
                self.reassay.append({'tube_token': _tok(r['tube']),
                                     'analyte': _tok(r['analyte']),
                                     'run_token': _tok(r['run']),
                                     'reason': re.sub(r'[-\s]+', '_',
                                                      _tok(r['reason'])),
                                     'status': _tok(r['status'])})
        self.lab_status = {}
        with open(p('run_status_dashboard.csv'), newline='', encoding='utf-8') as fh:
            for r in csv.DictReader(fh):
                self.lab_status[_tok(r['run_id'])] = r['lab_status'].strip().upper()
        self.published = []
        with open(p('be_report_published.csv'), newline='', encoding='utf-8') as fh:
            for r in csv.DictReader(fh):
                self.published.append({k: (v or '').strip() for k, v in r.items()})
        self.pub_stats = json.load(open(p('be_statistics_published.json'),
                                       encoding='utf-8'))


# --------------------------------------------------------------------------
# ingestion, revisions and voids (H2, H3)
# --------------------------------------------------------------------------

def ingest(c):
    shards = []
    inactive = []
    uniq = {}
    hits = {}
    rows_read = 0
    duplicate_copies = 0
    for sh in c.catalog['shards']:
        if not sh.get('active'):
            inactive.append(sh['file'])
            continue
        recs = LAYOUTS[sh['layout']](os.path.join(c.dir, sh['file']))
        idx = len(shards)
        shards.append({'file': sh['file'], 'layout': sh['layout'],
                       'rows': len(recs), 'effective': 0})
        for r in recs:
            rows_read += 1
            key = (r['inj'], r['rev'])
            if key in uniq:
                duplicate_copies += 1
            else:
                uniq[key] = r
            hits.setdefault(key, []).append(idx)

    inadmissible_manual = 0
    by_inj = {}
    for key, r in uniq.items():
        admissible = True
        if not r['void'] and r['integ'] == 'MANUAL':
            ent = c.audit.get(key)
            admissible = bool(ent and ent[2] == 'APPROVED'
                              and c.manual_codes.get(ent[1]) == 'Y')
            if not admissible:
                inadmissible_manual += 1
        if admissible:
            by_inj.setdefault(r['inj'], []).append(r)

    superseded = 0
    voided = 0
    effective = []
    for inj, recs in by_inj.items():
        recs.sort(key=lambda x: x['rev'])
        superseded += len(recs) - 1
        eff = recs[-1]
        if eff['void']:
            voided += 1
            continue
        effective.append(eff)
        for i in hits[(eff['inj'], eff['rev'])]:
            shards[i]['effective'] += 1

    effective.sort(key=lambda r: (r['inj'],))
    return {'shards': shards, 'inactive': inactive, 'rows_read': rows_read,
            'duplicate_copies': duplicate_copies, 'superseded': superseded,
            'inadmissible_manual': inadmissible_manual, 'voided': voided,
            'effective': effective, 'all_records': list(uniq.values())}


# --------------------------------------------------------------------------
# analysis
# --------------------------------------------------------------------------

def build_runs(c):
    runs = {}
    order = []
    for r in c.runplan:
        if r['analyte'] not in c.analytes:
            continue
        runs[r['run_id']] = dict(r)
        order.append(r['run_id'])
    seq = sorted(runs.values(), key=lambda r: (r['analysis_date'], r['run_id']))
    for i, r in enumerate(seq):
        r['order'] = i
    return runs


def ruling_rows(c, action, study_only):
    out = []
    for r in c.rulings:
        if r['action'] != action or r['status'] != 'IN FORCE':
            continue
        if study_only and r['study'] != c.study:
            continue
        out.append(r)
    return out


def calibrate(c, runs, inj_by_run):
    """H6 - H10 per analysed run"""
    rejected_by_ruling = set()
    for r in ruling_rows(c, 'REJECT_RUN', False):
        rid = c.resolve_run(r['target'])
        if rid:
            rejected_by_ruling.add(rid)

    assignable_requests = {}
    for q in c.std_requests:
        if q['status'] != 'APPROVED':
            continue
        if c.assign_codes.get(q['code']) != 'Y':
            continue
        rid = c.resolve_run(q['run_token'])
        if rid:
            assignable_requests.setdefault(rid, set()).add(q['injection'])

    for rid, run in runs.items():
        meth = c.method[run['analyte']]
        ncoef = 2 if meth['model'] == 'linear' else 3
        injs = inj_by_run.get(rid, [])
        stds = sorted([i for i in injs if i['kind'] == 'STD'],
                      key=lambda x: (x['seq'], x['inj']))
        for s in stds:
            s['level'] = std_level(s['ref'])
            s['nominal'] = c.nominals.get((run['cal_lot'], s['level'] or ''))
            s['response'] = (Fraction(s['a_area'], s['is_area'])
                             if s['a_area'] is not None and s['is_area'] else None)
            s['limit'] = (meth['lloq_std_limit_pct'] if s['level'] == 'CS1'
                          else meth['std_limit_pct'])
        want = assignable_requests.get(rid, set())
        assigned = [s for s in stds if s['inj'] in want]
        retained = [s for s in stds
                    if s['inj'] not in want and s['nominal'] and s['response']
                    is not None]
        removed = []
        coef = None
        iterations = 0
        if len(stds) - len(assigned) < ncoef + 1:
            retained = []
        else:
            while True:
                coef = fit_curve([(s['nominal'], s['response']) for s in retained],
                                 meth['model'], meth['weighting'])
                iterations += 1
                worst = None
                any_out = False
                for s in retained:
                    rd = read_back(s['response'], coef)
                    if rd is None:
                        ratio = None
                    else:
                        dev = 100 * (rd - s['nominal']) / s['nominal']
                        ratio = (dev if dev >= 0 else -dev) / s['limit']
                    out = ratio is None or ratio > 1
                    if out:
                        any_out = True
                    key = ((1, 0, 0) if ratio is None
                           else (0, ratio, s['nominal']))
                    if out and (worst is None or
                                (key[0], key[1], key[2], s['seq']) >
                                (worst[0][0], worst[0][1], worst[0][2],
                                 worst[1]['seq'])):
                        worst = (key, s)
                if any_out and len(retained) > ncoef + 1:
                    retained.remove(worst[1])
                    removed.append(worst[1])
                    continue
                break
        run['coef'] = coef if retained else None
        run['model'] = meth['model']
        run['weighting'] = meth['weighting']
        run['stds'] = stds
        run['assigned'] = set(s['inj'] for s in assigned)
        run['retained'] = set(s['inj'] for s in retained)
        run['removed_order'] = [s['inj'] for s in removed]
        run['iterations'] = iterations
        run['n_standards'] = len(stds)
        run['n_assignable'] = len(assigned)
        run['n_retained'] = len(retained)
        noms = [s['nominal'] for s in retained]
        run['lloq'] = min(noms) if noms else None
        run['uloq'] = max(noms) if noms else None
        run['levels_retained'] = len(set(s['level'] for s in retained))

        # standards back-calculation rows
        rows = []
        std_limit_breach = False
        for s in stds:
            if s['inj'] in run['assigned']:
                status = 'ASSIGNABLE'
            elif run['coef'] is None:
                status = 'NO_CURVE'
            elif s['inj'] in run['retained']:
                status = 'RETAINED'
            else:
                status = 'REMOVED'
            rd = read_back(s['response'], run['coef']) if run['coef'] else None
            dev = (100 * (rd - s['nominal']) / s['nominal']
                   if rd is not None and s['nominal'] else None)
            if status == 'RETAINED':
                if dev is None or abs(dev) > s['limit']:
                    std_limit_breach = True
            rows.append({'run_id': rid, 'injection_id': s['inj'],
                         'level': s['level'] or '', 'nominal': s['nominal'],
                         'response': s['response'], 'back': rd,
                         'dev': dev, 'status': status})
        run['std_rows'] = rows

        # QC / DQC
        qc_rows = []
        for q in sorted([i for i in injs if i['kind'] in ('QC', 'DQC')],
                        key=lambda x: (x['seq'], x['inj'])):
            lvl = QC_LEVEL.get(q['ref'])
            nom = c.qclots.get((run['qc_lot'], lvl or ''))
            resp = (Fraction(q['a_area'], q['is_area'])
                    if q['a_area'] is not None and q['is_area'] else None)
            rd = read_back(resp, run['coef']) if run['coef'] else None
            bc = rd * q['dil'] if (rd is not None and q['kind'] == 'DQC') else rd
            dev = (100 * (bc - nom) / nom if bc is not None and nom else None)
            limit = (meth['dqc_limit_pct'] if q['kind'] == 'DQC'
                     else meth['qc_limit_pct'])
            ok = dev is not None and abs(dev) <= limit
            qc_rows.append({'run_id': rid, 'injection_id': q['inj'],
                            'kind': q['kind'], 'qc_level': lvl or '',
                            'nominal': nom, 'dil': q['dil'], 'back': bc,
                            'dev': dev, 'pass': ok, 'seq': q['seq']})
        run['qc_rows'] = qc_rows

        # DQC status (H10)
        has_dil = any(i['kind'] == 'UNK' and i['dil'] > 1 for i in injs)
        dqcs = [q for q in qc_rows if q['kind'] == 'DQC']
        if not has_dil:
            run['dqc_status'] = 'NA'
        elif len(dqcs) >= 2 and all(q['pass'] for q in dqcs):
            run['dqc_status'] = 'PASS'
        else:
            run['dqc_status'] = 'FAIL'

        # acceptance (H9)
        lqc = [q for q in qc_rows if q['kind'] == 'QC']
        qc_total = len(lqc)
        qc_pass = sum(1 for q in lqc if q['pass'])
        run['qc_total'] = qc_total
        run['qc_pass'] = qc_pass
        reason = ''
        if rid in rejected_by_ruling:
            reason = 'RULING'
        elif run['coef'] is None:
            reason = 'NO_CURVE'
        elif std_limit_breach:
            reason = 'STD_LIMIT'
        elif (run['n_standards'] == 0 or
              Fraction(run['n_retained'], run['n_standards'])
              < meth['min_std_fraction']):
            reason = 'STD_COUNT'
        elif run['levels_retained'] < meth['min_levels']:
            reason = 'STD_LEVELS'
        elif qc_total == 0 or Fraction(qc_pass, qc_total) < meth['min_qc_fraction']:
            reason = 'QC_TOTAL'
        else:
            for lvl in ('LQC', 'MQC', 'HQC'):
                at = [q for q in lqc if q['qc_level'] == lvl]
                if not at:
                    continue
                if Fraction(sum(1 for q in at if q['pass']), len(at)) \
                        < meth['min_qc_level_fraction']:
                    reason = 'QC_LEVEL'
                    break
        run['status'] = 'REJECTED' if reason else 'ACCEPTED'
        run['reason'] = reason
    return runs


def sample_results(c, runs, inj_by_run):
    """H11"""
    results = []
    for rid in sorted(runs, key=lambda r: (runs[r]['order'], r)):
        run = runs[rid]
        for i in sorted([x for x in inj_by_run.get(rid, []) if x['kind'] == 'UNK'],
                        key=lambda x: (x['seq'], x['inj'])):
            tube = c.resolve_tube(i['ref'])
            info = c.tubes.get(tube)
            if info is None:
                continue
            if info['subject'] not in c.in_scope_set:
                continue
            if run['run_type'] == 'ISR':
                reason = 'ISR'
            else:
                reason = 'ORIGINAL'
                for q in c.reassay:
                    if q['status'] == 'CANCELLED':
                        continue
                    if q['analyte'] != run['analyte']:
                        continue
                    if c.resolve_tube(q['tube_token']) != tube:
                        continue
                    if c.resolve_run(q['run_token']) != rid:
                        continue
                    reason = q['reason']
                    break
            resp = (Fraction(i['a_area'], i['is_area'])
                    if i['a_area'] is not None and i['is_area'] else None)
            rd = read_back(resp, run['coef']) if run['coef'] else None
            if run['status'] != 'ACCEPTED':
                flag = 'RUN_REJECTED'
            elif i['dil'] > 1 and run['dqc_status'] == 'FAIL':
                flag = 'DQC_FAIL'
            elif rd is not None and rd < run['lloq']:
                flag = 'BLQ'
            elif rd is None or rd > run['uloq']:
                flag = 'ALQ'
            else:
                flag = 'OK'
            conc = round_sig(rd * i['dil'], 4) if flag == 'OK' else None
            results.append({'run_id': rid, 'injection_id': i['inj'],
                            'tube': tube, 'analyte': run['analyte'],
                            'reason': reason, 'dil': i['dil'],
                            'response': resp, 'back': rd, 'conc': conc,
                            'flag': flag, 'seq': i['seq'],
                            'order': run['order'], 'used': False})
    return results


def report_concentrations(c, results):
    """H12"""
    excl_tubes = set()
    for r in ruling_rows(c, 'EXCLUDE_SAMPLE', True):
        excl_tubes.add(c.resolve_tube(r['target']))
    by_key = {}
    for r in results:
        by_key.setdefault((r['tube'], r['analyte']), []).append(r)
    reported = {}
    keys = set(by_key)
    for tube, info in c.tubes.items():
        if info['subject'] in c.in_scope_set:
            for a in c.analytes:
                keys.add((tube, a))
    for key in keys:
        tube, analyte = key
        info = c.tubes.get(tube)
        rows = sorted(by_key.get(key, []), key=lambda r: (r['order'], r['seq']))
        out = {'status': 'NR', 'rule': 'NONE', 'value': None, 'source_run': '',
               'used': []}
        if tube in excl_tubes:
            out = {'status': 'EXCL', 'rule': 'RULING', 'value': None,
                   'source_run': '', 'used': []}
        elif info is not None and info['status'] == 'NOT_COLLECTED':
            out = {'status': 'NOT_COLLECTED', 'rule': 'NONE', 'value': None,
                   'source_run': '', 'used': []}
        else:
            cands = [r for r in rows if r['flag'] in ('OK', 'BLQ', 'ALQ')
                     and r['reason'] != 'ISR']
            base = None
            for r in cands:
                if r['reason'] in ('ORIGINAL', 'RUN_FAIL'):
                    base = r
                    break
            if base is None:
                out = {'status': 'NR', 'rule': 'NONE', 'value': None,
                       'source_run': '', 'used': []}
            elif base['flag'] == 'ALQ':
                dil = None
                for r in cands:
                    if r['reason'] == 'ALQ' and r['flag'] == 'OK':
                        dil = r
                        break
                if dil is None:
                    out = {'status': 'NR', 'rule': 'ALQ_NO_DILUTION',
                           'value': None, 'source_run': base['run_id'],
                           'used': []}
                else:
                    out = {'status': 'OK', 'rule': 'ALQ_DILUTION',
                           'value': dil['conc'], 'source_run': dil['run_id'],
                           'used': [base, dil]}
            elif base['flag'] == 'BLQ':
                out = {'status': 'BLQ', 'rule': base['reason'], 'value': None,
                       'source_run': base['run_id'], 'used': [base]}
            else:
                reps = [r for r in cands if r['reason'] == 'PK_REPEAT'
                        and r['flag'] in ('OK', 'BLQ')]
                if len(reps) >= 2:
                    members = [base] + reps[:2]
                    vals = [(m['conc'] if m['flag'] == 'OK' else F0)
                            for m in members]
                    med = sorted(vals)[1]
                    if med == 0:
                        out = {'status': 'BLQ', 'rule': 'PK_REPEAT_MEDIAN',
                               'value': None, 'source_run': base['run_id'],
                               'used': members}
                    else:
                        out = {'status': 'OK', 'rule': 'PK_REPEAT_MEDIAN',
                               'value': med, 'source_run': base['run_id'],
                               'used': members}
                else:
                    out = {'status': 'OK', 'rule': base['reason'],
                           'value': base['conc'], 'source_run': base['run_id'],
                           'used': [base]}
        if out['status'] in ('OK', 'BLQ'):
            for r in out['used']:
                r['used'] = True
        reported[key] = out
    return reported


def tube_times(c):
    """H13"""
    out = {}
    for tube, info in c.tubes.items():
        if info['subject'] not in c.in_scope_set:
            continue
        dose = c.dose.get((info['subject'], info['period']))
        drawn = c.draw_instant.get(tube)
        if drawn is None or dose is None:
            elapsed = None
        elif info['nominal'] == 0:
            elapsed = F0
        else:
            elapsed = round_dp(Fraction(drawn - dose, 3600), 4)
        out[tube] = {'dose': dose, 'drawn': drawn, 'elapsed': elapsed}
    return out


# --------------------------------------------------------------------------
# non-compartmental analysis (H15)
# --------------------------------------------------------------------------

def nca_profile(c, points):
    """points: [(elapsed Fraction, nominal, tube, status, value)] ordered"""
    pts = []
    first_ok = None
    for i, p in enumerate(points):
        if p[3] == 'OK':
            first_ok = i
            break
    for i, p in enumerate(points):
        if p[3] == 'OK':
            pts.append((p[0], p[4], p[2]))
        elif p[3] == 'BLQ':
            if first_ok is not None and i < first_ok:
                pts.append((p[0], F0, p[2]))
    res = {'n_points': len(pts), 'flag': 'OK', 'candidates': [], 'chosen_n': None}
    positives = [p for p in pts if p[1] > 0]
    if len(positives) < 3:
        res['flag'] = 'NOT_EVALUABLE'
        return res
    cmax = max(p[1] for p in pts)
    tmax = next(p[0] for p in pts if p[1] == cmax)
    icmax = next(i for i, p in enumerate(pts) if p[1] == cmax)
    last_pos = max(i for i, p in enumerate(pts) if p[1] > 0)
    tlast = pts[last_pos][0]
    clast = pts[last_pos][1]
    auc = 0.0
    for i in range(last_pos):
        t1, c1 = float(pts[i][0]), float(pts[i][1])
        t2, c2 = float(pts[i + 1][0]), float(pts[i + 1][1])
        if c2 < c1 and c1 > 0 and c2 > 0:
            auc += (c1 - c2) / math.log(c1 / c2) * (t2 - t1)
        else:
            auc += (c1 + c2) / 2.0 * (t2 - t1)
    res.update({'cmax': cmax, 'tmax': tmax, 'clast': clast, 'tlast': tlast,
                'auc_last': auc})

    cands = [p for p in pts[icmax + 1:] if p[1] > 0]
    fits = []
    for n in range(c.lz_min, len(cands) + 1):
        sel = cands[-n:]
        xs = [float(p[0]) for p in sel]
        ys = [math.log(float(p[1])) for p in sel]
        mx = sum(xs) / n
        my = sum(ys) / n
        sxx = sum((x - mx) ** 2 for x in xs)
        sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        if sxx == 0:
            continue
        slope = sxy / sxx
        intercept = my - slope * mx
        sst = sum((y - my) ** 2 for y in ys)
        ssr = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys))
        r2 = 1 - ssr / sst if sst else 1.0
        adj = 1 - (1 - r2) * (n - 1) / (n - 2)
        fits.append({'n': n, 'slope': slope, 'intercept': intercept,
                     'adj_r2': adj, 'eligible': slope < 0})
    res['candidates'] = fits
    elig = [f for f in fits if f['eligible']]
    if not elig:
        res['flag'] = 'NO_LAMBDA_Z'
        return res
    best = max(f['adj_r2'] for f in elig)
    thresh = best - float(c.lz_tol)
    pick = max([f for f in elig if f['adj_r2'] >= thresh], key=lambda f: f['n'])
    res['chosen_n'] = pick['n']
    lz = -pick['slope']
    res['lambda_z'] = lz
    res['lz_points'] = pick['n']
    res['lz_adj_r2'] = pick['adj_r2']
    res['half_life'] = math.log(2) / lz
    cpred = math.exp(pick['intercept'] - lz * float(tlast))
    res['clast_pred'] = cpred
    res['auc_inf'] = auc + cpred / lz
    res['auc_extrap_pct'] = 100 * (cpred / lz) / res['auc_inf']
    if to_frac(repr(res['auc_extrap_pct'])) > c.extrap_limit:
        res['flag'] = 'EXTRAP_GT_LIMIT'
    return res


def run_nca(c, reported, times):
    """per in-scope subject, dosed period and analysed analyte"""
    tubes_by = {}
    for tube, info in c.tubes.items():
        if info['subject'] not in c.in_scope_set:
            continue
        if info['nominal'] is None:
            continue
        tubes_by.setdefault((info['subject'], info['period']), []).append(tube)
    profiles = {}
    for s in c.in_scope:
        for per in (1, 2):
            if (s, per) not in c.dose:
                continue
            for a in c.analytes:
                pts = []
                for tube in tubes_by.get((s, per), []):
                    rep = reported.get((tube, a))
                    t = times.get(tube)
                    if rep is None or t is None or t['elapsed'] is None:
                        continue
                    if rep['status'] not in ('OK', 'BLQ'):
                        continue
                    pts.append((t['elapsed'], c.tubes[tube]['nominal'], tube,
                                rep['status'], rep['value']))
                pts.sort(key=lambda p: (p[0], p[1], p[2]))
                profiles[(s, per, a)] = nca_profile(c, pts)
    return profiles


def formulation(c, subject, period):
    seq = c.sequence.get(subject, '')
    if seq == 'TR':
        return 'T' if period == 1 else 'R'
    if seq == 'RT':
        return 'R' if period == 1 else 'T'
    return ''


# --------------------------------------------------------------------------
# populations (H16)
# --------------------------------------------------------------------------

def populations(c, reported, times, profiles):
    ruled = set()
    for r in ruling_rows(c, 'EXCLUDE_SUBJECT', True):
        s = c.resolve_subject(r['target'])
        if s:
            ruled.add(s)

    base = {}
    for s in c.rand_subjects:
        if s not in c.in_scope_set:
            base[s] = ('NOT_IN_SCOPE', None, None)
        elif s in ruled:
            base[s] = ('RULING', None, None)
        elif s in c.withdrawn:
            base[s] = ('WITHDRAWN', None, None)
        else:
            missing = [p for p in (1, 2) if (s, p) not in c.dose]
            if missing:
                base[s] = ('INCOMPLETE', missing[0], None)
            else:
                base[s] = (None, None, None)

    candidates = [s for s in c.rand_subjects
                  if s in c.in_scope_set and base[s][0] is None]
    pivotal = c.pivotal[0]

    aes = []
    for e in c.ae:
        if e['subject'] is None or e['onset'] is None:
            continue
        if e['pt'].strip().upper() not in c.emesis_terms:
            continue
        dose = c.dose.get((e['subject'], e['period']))
        if dose is None:
            continue
        aes.append({'subject': e['subject'], 'period': e['period'],
                    'onset_h': round_dp(Fraction(e['onset'] - dose, 3600), 4)})

    def mean_tmax(subset):
        vals = []
        for s in subset:
            for per in (1, 2):
                if formulation(c, s, per) != 'R':
                    continue
                pr = profiles.get((s, per, pivotal))
                if pr and pr['flag'] != 'NOT_EVALUABLE':
                    vals.append(pr['tmax'])
        if not vals:
            return None
        return sum(vals, F0) / len(vals)

    def emetic_set(window):
        hit = {}
        for ev in aes:
            if ev['subject'] not in candidates:
                continue
            if ev['onset_h'] < 0 or ev['onset_h'] > window:
                continue
            key = ev['subject']
            cand = (ev['period'], ev['onset_h'])
            if key not in hit or cand < hit[key]:
                hit[key] = cand
        return hit

    passes = []
    prev_emetic = set()
    settlement = 'CONVERGED'
    repeat_at = None
    while True:
        subset = [s for s in candidates if s not in prev_emetic]
        mt = mean_tmax(subset)
        window = c.emesis_factor * mt if mt is not None else F0
        hit = emetic_set(window)
        es = frozenset(hit)
        passes.append({'mean_tmax': mt, 'window': window, 'hits': hit, 'set': es})
        earlier = None
        for i in range(len(passes) - 1):
            if passes[i]['set'] == es:
                earlier = i
                break
        if earlier is not None:
            if earlier == len(passes) - 2:
                settlement = 'CONVERGED'
                settled = len(passes) - 1
            else:
                settlement = 'CYCLE'
                best = None
                for i in range(earlier, len(passes) - 1):
                    if best is None or passes[i]['window'] > passes[best]['window']:
                        best = i
                settled = best
            repeat_at = earlier
            break
        prev_emetic = set(es)
        if len(passes) > 200:
            settled = len(passes) - 1
            break
    settled_pass = passes[settled]

    pre_tubes = {}
    for tube, info in c.tubes.items():
        if info['nominal'] == 0:
            pre_tubes.setdefault((info['subject'], info['period']), []).append(tube)

    reasons = {}
    for s in c.rand_subjects:
        r, per, val = base[s]
        for a in c.analytes:
            if r is not None:
                reasons[(s, a)] = (r, per, val)
                continue
            if s in settled_pass['hits']:
                p, onset = settled_pass['hits'][s]
                reasons[(s, a)] = ('EMESIS', p, onset)
                continue
            ne = [p for p in (1, 2)
                  if profiles.get((s, p, a), {}).get('flag') == 'NOT_EVALUABLE']
            if ne:
                reasons[(s, a)] = ('NOT_EVALUABLE', ne[0], None)
                continue
            co = None
            for p in (1, 2):
                pr = profiles.get((s, p, a))
                if not pr or 'cmax' not in pr:
                    continue
                pre = None
                for tube in pre_tubes.get((s, p), []):
                    rep = reported.get((tube, a))
                    if rep and rep['status'] == 'OK':
                        if pre is None or rep['value'] > pre:
                            pre = rep['value']
                if pre is None:
                    continue
                if pre > c.carryover_limit / 100 * pr['cmax']:
                    co = (p, 100 * pre / pr['cmax'])
                    break
            if co:
                reasons[(s, a)] = ('CARRYOVER', co[0], co[1])
                continue
            reasons[(s, a)] = (None, None, None)

    param_reasons = {}
    for s in c.rand_subjects:
        for a in c.analytes:
            r = reasons[(s, a)][0]
            for p in c.parameters:
                if r is not None:
                    param_reasons[(s, a, p)] = r
                elif p == 'AUCinf':
                    flags = [profiles.get((s, per, a), {}) for per in (1, 2)]
                    if any(f.get('lambda_z') is None for f in flags):
                        param_reasons[(s, a, p)] = 'PARAM_NA'
                    elif any(f.get('flag') == 'EXTRAP_GT_LIMIT' for f in flags):
                        param_reasons[(s, a, p)] = 'EXTRAP'
                    else:
                        param_reasons[(s, a, p)] = None
                else:
                    param_reasons[(s, a, p)] = None
    return {'subject_reasons': reasons, 'param_reasons': param_reasons,
            'passes': passes, 'settled': settled, 'settlement': settlement,
            'repeat_at': repeat_at}


# --------------------------------------------------------------------------
# average bioequivalence (H17)
# --------------------------------------------------------------------------

PARAM_KEY = {'Cmax': 'cmax', 'AUClast': 'auc_last', 'AUCinf': 'auc_inf'}


def be_stats(c, profiles, pop):
    out = {}
    for a in c.analytes:
        pars = {}
        for p in c.parameters:
            key = PARAM_KEY[p]
            subs = [s for s in c.rand_subjects
                    if pop['param_reasons'][(s, a, p)] is None]
            rows = []
            for s in subs:
                v1 = profiles.get((s, 1, a), {}).get(key)
                v2 = profiles.get((s, 2, a), {}).get(key)
                if v1 is None or v2 is None:
                    continue
                y1 = math.log(float(v1))
                y2 = math.log(float(v2))
                rows.append({'s': s, 'seq': c.sequence.get(s, ''),
                             'y1': y1, 'y2': y2, 'd': (y2 - y1) / 2.0})
            tr = [r for r in rows if r['seq'] == 'TR']
            rt = [r for r in rows if r['seq'] == 'RT']
            n_tr, n_rt = len(tr), len(rt)
            df = n_tr + n_rt - 2
            rec = {'n_TR': n_tr, 'n_RT': n_rt, 'df': df}
            if n_tr < 1 or n_rt < 1 or df <= 0 or df not in c.t_table:
                rec.update({'t': None, 'estimate': None, 'se': None,
                            'mse': None, 'cv': None, 'ls_t': None, 'ls_r': None,
                            'ratio': None, 'lo': None, 'hi': None,
                            'result': 'NOT_ESTIMABLE', 'n': len(rows)})
                pars[p] = rec
                continue
            m_tr = sum(r['d'] for r in tr) / n_tr
            m_rt = sum(r['d'] for r in rt) / n_rt
            est = m_rt - m_tr
            ss = (sum((r['d'] - m_tr) ** 2 for r in tr)
                  + sum((r['d'] - m_rt) ** 2 for r in rt))
            s2 = ss / df
            se = math.sqrt(s2 * (1.0 / n_tr + 1.0 / n_rt))
            mse = 2 * s2
            cv = 100 * math.sqrt(math.exp(mse) - 1)
            t_t1 = sum(r['y1'] for r in tr) / n_tr
            t_r2 = sum(r['y2'] for r in tr) / n_tr
            r_r1 = sum(r['y1'] for r in rt) / n_rt
            r_t2 = sum(r['y2'] for r in rt) / n_rt
            ls_t = (t_t1 + r_t2) / 2.0
            ls_r = (t_r2 + r_r1) / 2.0
            tq = float(c.t_table[df])
            ratio = 100 * math.exp(est)
            lo = 100 * math.exp(est - tq * se)
            hi = 100 * math.exp(est + tq * se)
            lo_r = round_dp(to_frac(repr(lo)), 2)
            hi_r = round_dp(to_frac(repr(hi)), 2)
            if a in c.pivotal:
                res = 'PASS' if (lo_r >= c.be_lower and hi_r <= c.be_upper) \
                    else 'FAIL'
            else:
                res = 'INFO'
            rec.update({'t': c.t_table[df], 'estimate': est, 'se': se,
                        'mse': mse, 'cv': cv,
                        'ls_t': math.exp(ls_t), 'ls_r': math.exp(ls_r),
                        'ratio': ratio, 'lo': lo, 'hi': hi,
                        'ratio_r': round_dp(to_frac(repr(ratio)), 2),
                        'lo_r': lo_r, 'hi_r': hi_r,
                        'pass': lo_r >= c.be_lower and hi_r <= c.be_upper,
                        'result': res, 'n': len(rows)})
            pars[p] = rec
        role = 'PIVOTAL' if a in c.pivotal else 'SUPPORTIVE'
        if role == 'PIVOTAL':
            ok = all(pars[p].get('result') == 'PASS' for p in c.parameters)
            conclusion = 'BIOEQUIVALENT' if ok else 'NOT_BIOEQUIVALENT'
        else:
            conclusion = 'SUPPORTIVE'
        out[a] = {'role': role, 'conclusion': conclusion, 'parameters': pars}
    return out


def mean_profiles(c, reported, pop):
    rows = []
    noms = sorted(set(t['nominal'] for t in c.tubes.values()
                      if t['nominal'] is not None))
    index = {}
    for tube, info in c.tubes.items():
        if info['nominal'] is None:
            continue
        index.setdefault((info['subject'], info['period'], info['nominal']),
                         []).append(tube)
    for a in c.analytes:
        subs = [s for s in c.rand_subjects
                if pop['param_reasons'][(s, a, 'Cmax')] is None]
        for form in ('R', 'T'):
            for nom in noms:
                vals = []
                for s in subs:
                    for per in (1, 2):
                        if formulation(c, s, per) != form:
                            continue
                        for tube in index.get((s, per, nom), []):
                            rep = reported.get((tube, a))
                            if not rep:
                                continue
                            if rep['status'] == 'OK':
                                vals.append(rep['value'])
                            elif rep['status'] == 'BLQ':
                                vals.append(F0)
                if not vals:
                    continue
                n = len(vals)
                mean = sum(vals, F0) / n
                sd = None
                if n >= 2:
                    var = sum((v - mean) ** 2 for v in vals) / (n - 1)
                    sd = math.sqrt(float(var))
                rows.append({'analyte': a, 'formulation': form, 'nominal': nom,
                             'n': n, 'mean': mean, 'sd': sd})
    return rows


def isr(c, results, reported):
    out = {}
    by_tube = {}
    for r in results:
        if r['reason'] == 'ISR' and r['flag'] == 'OK':
            by_tube.setdefault((r['tube'], r['analyte']), []).append(r)
    for a in c.analytes:
        pairs = []
        for (tube, an), rows in by_tube.items():
            if an != a:
                continue
            rep = reported.get((tube, a))
            if not rep or rep['status'] != 'OK':
                continue
            rows = sorted(rows, key=lambda r: (r['order'], r['seq']))
            rpt = rows[0]
            reported_v = rep['value']
            repeat_v = rpt['conc']
            mean = (repeat_v + reported_v) / 2
            diff = 100 * (repeat_v - reported_v) / mean if mean else None
            within = diff is not None and abs(diff) <= c.isr_limit
            pairs.append({'tube': tube, 'run_id': rpt['run_id'],
                          'reported': reported_v, 'repeat': repeat_v,
                          'diff_pct': diff, 'within': within})
        pairs.sort(key=lambda p: p['tube'])
        n = len(pairs)
        w = sum(1 for p in pairs if p['within'])
        out[a] = {'pairs': pairs, 'n_pairs': n, 'n_within': w,
                  'pct_within': (Fraction(100 * w, n) if n else None),
                  'pass': bool(n and w * 3 >= n * 2)}
    return out


def variance_vs_published(c, profiles):
    pub = {}
    for r in c.published:
        s = _tok(r['subject'])
        per = int(to_frac(r['period']))
        a = _tok(r['analyte'])
        for name, col in (('Cmax', 'cmax'), ('AUClast', 'auc_last'),
                          ('AUCinf', 'auc_inf')):
            v = to_frac(r.get(col))
            if v is not None:
                pub[(s, per, a, name)] = v
    rec = {}
    for (s, per, a), pr in profiles.items():
        for name, col in (('Cmax', 'cmax'), ('AUClast', 'auc_last'),
                          ('AUCinf', 'auc_inf')):
            if col == 'auc_inf' and pr.get('flag') != 'OK':
                continue
            v = pr.get(col)
            if v is None:
                continue
            rec[(s, per, a, name)] = v
    order = {'Cmax': 0, 'AUClast': 1, 'AUCinf': 2}
    rows = []
    for key in sorted(set(pub) | set(rec),
                      key=lambda k: (k[0], k[1], k[2], order[k[3]])):
        p = pub.get(key)
        q = rec.get(key)
        if p is not None and q is not None:
            qf = q if isinstance(q, Fraction) else to_frac(repr(q))
            diff = 100 * (qf - p) / p if p else None
            status = ('MATCH' if diff is not None and abs(diff) <= 1 else 'DIFF')
        elif p is not None:
            diff = None
            status = 'ONLY_PUBLISHED'
        else:
            diff = None
            status = 'ONLY_RECOMPUTED'
        rows.append({'subject_id': key[0], 'period': key[1], 'analyte': key[2],
                     'parameter': key[3], 'published': p, 'recomputed': q,
                     'diff_pct': diff, 'status': status})
    return rows


def alias_rows(c, all_records):
    seen = set()
    rows = []

    def add(kind, token, canonical):
        if canonical is None:
            return
        key = (kind, token, canonical)
        if key in seen:
            return
        seen.add(key)
        rows.append(key)

    run_tokens = set()
    tube_tokens = set()
    for r in all_records:
        run_tokens.add(r['run_tok'])
        if r['kind'] == 'UNK':
            tube_tokens.add(r['ref'])
    for q in c.std_requests:
        run_tokens.add(q['run_token'])
    for q in c.reassay:
        run_tokens.add(q['run_token'])
        tube_tokens.add(q['tube_token'])
    for r in c.rulings:
        run_tokens.add(r['target'])
        if r['study'] == c.study:
            tube_tokens.add(r['target'])
    for t in sorted(run_tokens):
        add('run', t, c.resolve_run(t))

    subj_tokens = set()
    for t in c.tubes.values():
        subj_tokens.add(t['subject_token'])
    subj_tokens.update(c.dose_subject_tokens)
    subj_tokens.update(c.draw_subject_tokens)
    subj_tokens.update(c.ae_subject_tokens)
    subj_tokens.update(c.disp_subject_tokens)
    for r in c.rulings:
        if r['study'] == c.study:
            subj_tokens.add(r['target'])
    for t in sorted(subj_tokens):
        add('subject', t, c.resolve_subject(t))

    for t in sorted(tube_tokens):
        if t in c.relabel:
            add('tube', t, c.resolve_tube(t))
    rows.sort(key=lambda r: (r[0], r[1]))
    return rows


# --------------------------------------------------------------------------
# output
# --------------------------------------------------------------------------

CONTRACT_ORDER = [
    'calibration_fits.json', 'standard_backcalc.tsv', 'qc_results.csv',
    'run_acceptance.csv', 'tube_results.psv', 'reported_concentrations.csv',
    'sampling_times.xml', 'isr_assessment.json', 'nca_parameters.csv',
    'lambda_z_selection.jsonl', 'be_statistics.json', 'be_summary.md',
    'analysis_populations.csv', 'excluded_subjects.jsonl', 'mean_profiles.csv',
    'dedup_report.json', 'source_lineage.json', 'alias_resolution.csv',
    'parameters_used.yaml', 'variance_vs_published.csv', 'reconciliation.md',
]


def table_text(header, rows, sep):
    lines = [sep.join(header)]
    for r in rows:
        lines.append(sep.join(r))
    return '\n'.join(lines) + '\n'


def yn(v):
    return 'Y' if v else 'N'


def main():
    if len(sys.argv) != 3:
        sys.stderr.write('usage: run_be.py DATA_DIR OUT_DIR\n')
        return 2
    data_dir, out_dir = sys.argv[1], sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)
    c = Corpus(data_dir)
    ing = ingest(c)
    runs = build_runs(c)
    inj_by_run = {}
    for r in ing['effective']:
        rid = c.resolve_run(r['run_tok'])
        if rid in runs:
            inj_by_run.setdefault(rid, []).append(r)
    calibrate(c, runs, inj_by_run)
    results = sample_results(c, runs, inj_by_run)
    reported = report_concentrations(c, results)
    times = tube_times(c)
    profiles = run_nca(c, reported, times)
    pop = populations(c, reported, times, profiles)
    stats = be_stats(c, profiles, pop)
    means = mean_profiles(c, reported, pop)
    isr_res = isr(c, results, reported)
    var_rows = variance_vs_published(c, profiles)
    aliases = alias_rows(c, ing['all_records'])

    ai = {a: i for i, a in enumerate(c.analytes)}
    files = {}

    # 1 calibration_fits.json
    runs_out = []
    for rid in sorted(runs):
        r = runs[rid]
        coef = r['coef']
        runs_out.append({
            'run_id': rid, 'analyte': r['analyte'], 'model': r['model'],
            'weighting': r['weighting'], 'cal_lot': r['cal_lot'],
            'coefficients': (None if coef is None else
                             {'a': jnum(coef['a']), 'b': jnum(coef['b']),
                              'c': jnum(coef['c'])}),
            'n_standards': r['n_standards'], 'n_assignable': r['n_assignable'],
            'n_retained': r['n_retained'], 'removed': r['removed_order'],
            'iterations': r['iterations'], 'lloq': jnum(r['lloq']),
            'uloq': jnum(r['uloq'])})
    files['calibration_fits.json'] = jdump(
        {'study_id': c.study, 'nominal_sheet': c.nominal_sheet,
         'runs': runs_out}, indent=2) + '\n'

    # 2 standard_backcalc.tsv
    rows = []
    for rid in sorted(runs):
        for s in runs[rid]['std_rows']:
            rows.append([rid, s['injection_id'], s['level'],
                         fmt_num(s['nominal']), fmt_num(s['response']),
                         fmt_num(s['back']), fmt_num(s['dev']), s['status']])
    files['standard_backcalc.tsv'] = table_text(
        ['run_id', 'injection_id', 'level', 'nominal', 'response',
         'back_calculated', 'deviation_pct', 'status'], rows, '\t')

    # 3 qc_results.csv
    rows = []
    for rid in sorted(runs):
        for q in runs[rid]['qc_rows']:
            rows.append([rid, q['injection_id'], q['qc_level'],
                         fmt_num(q['nominal']), str(q['dil']),
                         fmt_num(q['back']), fmt_num(q['dev']),
                         yn(q['pass'])])
    files['qc_results.csv'] = table_text(
        ['run_id', 'injection_id', 'qc_level', 'nominal', 'dilution_factor',
         'back_calculated', 'deviation_pct', 'pass'], rows, ',')

    # 4 run_acceptance.csv
    rows = []
    for rid in sorted(runs):
        r = runs[rid]
        lab = c.lab_status.get(rid, '')
        rows.append([rid, r['analyte'], r['run_type'], r['analysis_date'],
                     str(r['n_standards']), str(r['n_retained']),
                     str(r['levels_retained']), str(r['qc_total']),
                     str(r['qc_pass']), r['status'], r['reason'],
                     r['dqc_status'], lab, yn(lab == r['status'])])
    files['run_acceptance.csv'] = table_text(
        ['run_id', 'analyte', 'run_type', 'analysis_date', 'n_std_total',
         'n_std_retained', 'n_levels_retained', 'qc_total', 'qc_pass',
         'status', 'reason', 'dqc_status', 'lab_status', 'agrees'], rows, ',')

    # 5 tube_results.psv
    rows = []
    for r in sorted(results, key=lambda x: (x['tube'], ai[x['analyte']],
                                            x['order'], x['seq'])):
        rows.append([r['run_id'], r['injection_id'], r['tube'], r['analyte'],
                     r['reason'], str(r['dil']), fmt_num(r['response']),
                     fmt_num(r['back']), fmt_num(r['conc']), r['flag'],
                     yn(r['used'])])
    files['tube_results.psv'] = table_text(
        ['run_id', 'injection_id', 'tube', 'analyte', 'reason',
         'dilution_factor', 'response', 'back_calculated', 'concentration',
         'flag', 'used'], rows, '|')

    # 6 reported_concentrations.csv  /  7 sampling_times.xml
    sched = [t for t in c.tubes.values()
             if t['subject'] in c.in_scope_set and t['nominal'] is not None]
    rows = []
    for t in sorted(sched, key=lambda x: (x['subject'], x['period'],
                                          x['nominal'], x['tube'])):
        for a in c.analytes:
            rep = reported[(t['tube'], a)]
            tm = times[t['tube']]
            actual = ('' if rep['status'] == 'NOT_COLLECTED'
                      else fmt_num(tm['elapsed']))
            rows.append([t['subject'], str(t['period']),
                         formulation(c, t['subject'], t['period']), a,
                         fmt_num(t['nominal']), t['tube'], actual,
                         fmt_num(rep['value']), rep['status'], rep['rule'],
                         rep['source_run']])
    rows.sort(key=lambda r: (r[0], int(r[1]), ai[r[3]], to_frac(r[4]), r[5]))
    files['reported_concentrations.csv'] = table_text(
        ['subject_id', 'period', 'formulation', 'analyte', 'nominal_h', 'tube',
         'actual_h', 'concentration', 'status', 'rule', 'source_run'],
        rows, ',')

    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<sampling_times study="%s">' % c.study]
    for t in sorted(sched, key=lambda x: (x['subject'], x['period'],
                                          x['nominal'], x['tube'])):
        tm = times[t['tube']]
        lines.append('  <tube id="%s" subject="%s" period="%d" nominal_h="%s" '
                     'dose_utc="%s" drawn_utc="%s" elapsed_h="%s"/>'
                     % (t['tube'], t['subject'], t['period'],
                        fmt_num(t['nominal']), fmt_instant(tm['dose']),
                        fmt_instant(tm['drawn']), fmt_num(tm['elapsed'])))
    lines.append('</sampling_times>')
    files['sampling_times.xml'] = '\n'.join(lines) + '\n'

    # 8 isr_assessment.json
    an = {}
    for a in c.analytes:
        d = isr_res[a]
        an[a] = {
            'pairs': [{'tube': p['tube'], 'run_id': p['run_id'],
                       'reported': jnum(p['reported']),
                       'repeat': jnum(p['repeat']),
                       'diff_pct': jnum(p['diff_pct']),
                       'within': p['within']} for p in d['pairs']],
            'n_pairs': d['n_pairs'], 'n_within': d['n_within'],
            'pct_within': jnum(d['pct_within']), 'pass': d['pass']}
    files['isr_assessment.json'] = jdump(
        {'limit_pct': jnum(c.isr_limit), 'analytes': an}, indent=2) + '\n'

    # 9 nca_parameters.csv / 10 lambda_z_selection.jsonl
    keys = sorted(profiles, key=lambda k: (k[0], k[1], ai[k[2]]))
    rows = []
    lz_lines = []
    for k in keys:
        s, per, a = k
        pr = profiles[k]
        rows.append([s, str(per), formulation(c, s, per), a,
                     str(pr['n_points']), fmt_num(pr.get('cmax')),
                     fmt_num(pr.get('tmax')), fmt_num(pr.get('clast')),
                     fmt_num(pr.get('tlast')), fmt_num(pr.get('auc_last')),
                     fmt_num(pr.get('lambda_z')),
                     ('' if pr.get('lz_points') is None
                      else str(pr['lz_points'])),
                     fmt_num(pr.get('lz_adj_r2')), fmt_num(pr.get('half_life')),
                     fmt_num(pr.get('clast_pred')), fmt_num(pr.get('auc_inf')),
                     fmt_num(pr.get('auc_extrap_pct')), pr['flag']])
        lz_lines.append(jdump({
            'subject_id': s, 'period': per, 'analyte': a,
            'candidates': [{'n': f['n'], 'slope': jnum(f['slope']),
                            'intercept': jnum(f['intercept']),
                            'adj_r2': jnum(f['adj_r2']),
                            'eligible': f['eligible']}
                           for f in pr['candidates']],
            'chosen_n': pr['chosen_n']}))
    files['nca_parameters.csv'] = table_text(
        ['subject_id', 'period', 'formulation', 'analyte', 'n_points', 'cmax',
         'tmax', 'clast', 'tlast', 'auc_last', 'lambda_z', 'lz_points',
         'lz_adj_r2', 'half_life', 'clast_pred', 'auc_inf', 'auc_extrap_pct',
         'flag'], rows, ',')
    files['lambda_z_selection.jsonl'] = ''.join(l + '\n' for l in lz_lines)

    # 11 be_statistics.json / 12 be_summary.md
    an = {}
    for a in c.analytes:
        st = stats[a]
        pars = {}
        for p in c.parameters:
            r = st['parameters'][p]
            pars[p] = {
                'n_TR': r['n_TR'], 'n_RT': r['n_RT'], 'df': r['df'],
                't_quantile': jnum(r.get('t')),
                'estimate_log': jnum(r.get('estimate')),
                'se_log': jnum(r.get('se')), 'mse': jnum(r.get('mse')),
                'cv_intra_pct': jnum(r.get('cv')),
                'lsmean_T': jnum(r.get('ls_t')), 'lsmean_R': jnum(r.get('ls_r')),
                'ratio_pct': jnum(r.get('ratio')),
                'ci_lower_pct': jnum(r.get('lo')),
                'ci_upper_pct': jnum(r.get('hi')),
                'ratio_pct_r': jnum(r.get('ratio_r')),
                'ci_lower_r': jnum(r.get('lo_r')),
                'ci_upper_r': jnum(r.get('hi_r')),
                'result': r['result']}
        an[a] = {'role': st['role'], 'conclusion': st['conclusion'],
                 'parameters': pars}
    files['be_statistics.json'] = jdump({
        'study_id': c.study, 'alpha': jnum(c.alpha),
        'ci_level_pct': jnum(100 * (1 - 2 * c.alpha)),
        'limits_pct': [jnum(c.be_lower), jnum(c.be_upper)],
        'analytes': an}, indent=2) + '\n'

    lines = ['# %s bioequivalence summary' % c.study, '',
             '| analyte | parameter | n | ratio_pct | ci_lower | ci_upper | '
             'cv_intra_pct | result |',
             '|---|---|---|---|---|---|---|---|']
    for a in c.analytes:
        for p in c.parameters:
            r = stats[a]['parameters'][p]
            lines.append('| %s | %s | %d | %s | %s | %s | %s | %s |' % (
                a, p, r['n_TR'] + r['n_RT'], fmt_num(r.get('ratio_r')),
                fmt_num(r.get('lo_r')), fmt_num(r.get('hi_r')),
                fmt_num(round_dp(to_frac(repr(r['cv'])), 2)
                        if r.get('cv') is not None else None),
                r['result']))
    files['be_summary.md'] = '\n'.join(lines) + '\n'

    # 13 analysis_populations.csv / 14 excluded_subjects.jsonl
    rows = []
    for s in sorted(c.rand_subjects):
        for a in c.analytes:
            for p in c.parameters:
                r = pop['param_reasons'][(s, a, p)]
                rows.append([s, a, p, yn(r is None), r or ''])
    files['analysis_populations.csv'] = table_text(
        ['subject_id', 'analyte', 'parameter', 'included', 'reason'], rows, ',')

    lz_lines = []
    for s in sorted(c.rand_subjects):
        if s not in c.in_scope_set:
            continue
        for a in c.analytes:
            reason, per, val = pop['subject_reasons'][(s, a)]
            if reason is None or reason == 'NOT_IN_SCOPE':
                continue
            lz_lines.append(jdump({'subject_id': s, 'analyte': a,
                                   'reason': reason,
                                   'period': per if per is not None else None,
                                   'value': jnum(val)}))
    files['excluded_subjects.jsonl'] = ''.join(l + '\n' for l in lz_lines)

    # 15 mean_profiles.csv
    rows = []
    for m in means:
        rows.append([m['analyte'], m['formulation'], fmt_num(m['nominal']),
                     str(m['n']), fmt_num(m['mean']), fmt_num(m['sd'])])
    files['mean_profiles.csv'] = table_text(
        ['analyte', 'formulation', 'nominal_h', 'n', 'mean', 'sd'], rows, ',')

    # 16 dedup_report.json
    eff = ing['effective']
    kinds = {'STD': 0, 'QC': 0, 'BZ': 0, 'UNK': 0, 'FOR': 0}
    for r in eff:
        if r['kind'] == 'STD':
            kinds['STD'] += 1
        elif r['kind'] in ('QC', 'DQC'):
            kinds['QC'] += 1
        elif r['kind'] in ('BLANK', 'ZERO'):
            kinds['BZ'] += 1
        else:
            tube = c.resolve_tube(r['ref'])
            if tube in c.tubes:
                kinds['UNK'] += 1
            else:
                kinds['FOR'] += 1
    files['dedup_report.json'] = jdump({
        'rows_read': ing['rows_read'],
        'duplicate_copies': ing['duplicate_copies'],
        'superseded': ing['superseded'],
        'inadmissible_manual': ing['inadmissible_manual'],
        'voided': ing['voided'], 'effective_injections': len(eff),
        'standards': kinds['STD'], 'qcs': kinds['QC'],
        'blank_zero': kinds['BZ'],
        'study_sample_injections': kinds['UNK'],
        'foreign_injections': kinds['FOR']}, indent=2) + '\n'

    # 17 source_lineage.json
    files['source_lineage.json'] = jdump({
        'shards': [{'file': s['file'], 'layout': s['layout'],
                    'rows': s['rows'], 'effective': s['effective']}
                   for s in ing['shards']],
        'inactive': ing['inactive']}, indent=2) + '\n'

    # 18 alias_resolution.csv
    files['alias_resolution.csv'] = table_text(
        ['kind', 'token', 'canonical'], [list(r) for r in aliases], ',')

    # 19 parameters_used.yaml
    sp = pop['passes'][pop['settled']]
    pu = [('study_id', c.study), ('nominal_sheet', c.nominal_sheet),
          ('alpha', fmt_num(c.alpha)),
          ('ci_level_pct', fmt_num(100 * (1 - 2 * c.alpha))),
          ('be_lower_pct', fmt_num(c.be_lower)),
          ('be_upper_pct', fmt_num(c.be_upper)),
          ('t_quantile_p', fmt_num(1 - c.alpha)),
          ('lambda_z_min_points', str(c.lz_min)),
          ('lambda_z_adj_r2_tolerance', fmt_num(c.lz_tol)),
          ('extrap_limit_pct', fmt_num(c.extrap_limit)),
          ('carryover_limit_pct', fmt_num(c.carryover_limit)),
          ('emesis_window_factor', fmt_num(c.emesis_factor)),
          ('emesis_reference_mean_tmax_h', fmt_num(sp['mean_tmax'])),
          ('emesis_window_h', fmt_num(sp['window'])),
          ('emesis_passes', str(len(pop['passes']))),
          ('emesis_settlement', pop['settlement']),
          ('isr_limit_pct', fmt_num(c.isr_limit))]
    for a in c.analytes:
        m = c.method[a]
        pu.append((a + '.model', m['model']))
        pu.append((a + '.weighting', m['weighting']))
        pu.append((a + '.std_limit_pct', fmt_num(m['std_limit_pct'])))
        pu.append((a + '.lloq_std_limit_pct', fmt_num(m['lloq_std_limit_pct'])))
        pu.append((a + '.qc_limit_pct', fmt_num(m['qc_limit_pct'])))
    pu.append(('conventions_table', c.t_conventions))
    pu.append(('method_table', c.t_method))
    pu.append(('t_table', c.t_tquant))
    files['parameters_used.yaml'] = ''.join('%s: %s\n' % kv for kv in pu)

    # 20 variance_vs_published.csv
    rows = []
    for r in var_rows:
        rows.append([r['subject_id'], str(r['period']), r['analyte'],
                     r['parameter'], fmt_num(r['published']),
                     fmt_num(r['recomputed']), fmt_num(r['diff_pct']),
                     r['status']])
    files['variance_vs_published.csv'] = table_text(
        ['subject_id', 'period', 'analyte', 'parameter', 'published',
         'recomputed', 'diff_pct', 'status'], rows, ',')

    # 21 reconciliation.md
    pubmap = {}
    for r in c.pub_stats.get('results', []):
        pubmap[(_tok(r['analyte']), r['parameter'])] = r
    lines = ['# %s published versus recomputed' % c.study, '',
             '| analyte | parameter | published_ratio | published_lower | '
             'published_upper | published_result | recomputed_ratio | '
             'recomputed_lower | recomputed_upper | recomputed_result |',
             '|---|---|---|---|---|---|---|---|---|---|']
    for a in c.analytes:
        for p in c.parameters:
            pb = pubmap.get((a, p))
            r = stats[a]['parameters'][p]
            lines.append('| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |' % (
                a, p,
                fmt_num(to_frac(repr(pb['ratio_pct']))) if pb else '',
                fmt_num(to_frac(repr(pb['ci_lower_pct']))) if pb else '',
                fmt_num(to_frac(repr(pb['ci_upper_pct']))) if pb else '',
                pb['result'] if pb else '',
                fmt_num(r.get('ratio_r')), fmt_num(r.get('lo_r')),
                fmt_num(r.get('hi_r')), r['result']))
    files['reconciliation.md'] = '\n'.join(lines) + '\n'

    manifest = []
    for name in CONTRACT_ORDER:
        body = files[name].encode('utf-8')
        with open(os.path.join(out_dir, name), 'wb') as fh:
            fh.write(body)
        manifest.append({'name': name, 'bytes': len(body),
                         'sha256': hashlib.sha256(body).hexdigest()})
    with open(os.path.join(out_dir, 'manifest.json'), 'wb') as fh:
        fh.write((jdump({'files': manifest}, indent=2) + '\n').encode('utf-8'))
    return 0


if __name__ == '__main__':
    sys.exit(main())

