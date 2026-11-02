#!/usr/bin/env python3
"""Aurelis R7 post-training preference corpus release builder.

usage: build.py <DATA_DIR> <OUT_DIR>
"""

import bisect
import csv
import json
import os
import re
import sqlite3
import sys
import zipfile
from fractions import Fraction

# =============================================================== conventions

_CYR = {
    0x410: 'A', 0x412: 'B', 0x415: 'E', 0x41A: 'K', 0x41C: 'M', 0x41D: 'H',
    0x41E: 'O', 0x420: 'P', 0x421: 'C', 0x422: 'T', 0x423: 'Y', 0x425: 'X',
    0x405: 'S', 0x406: 'I', 0x408: 'J', 0x430: 'a', 0x432: 'b', 0x435: 'e',
    0x43A: 'k', 0x43C: 'm', 0x43D: 'h', 0x43E: 'o', 0x440: 'p', 0x441: 'c',
    0x442: 't', 0x443: 'y', 0x445: 'x', 0x455: 's', 0x456: 'i', 0x458: 'j',
}
_TRANS = dict(_CYR)
for _i in range(10):
    _TRANS[0xFF10 + _i] = chr(0x30 + _i)
_TRANS[0x00A0] = None
_TRANS[0xFEFF] = None

_PAD = {'PRM': 5, 'CMP': 6, 'CMR': 6, 'VD': 7, 'ANN': 4, 'DUP': 4, 'PF': 4,
        'WS': 4}
_SHOWN = {'WS': 'ws'}

_idc = {}
_txc = {}


def nid(raw):
    """The registered form of an identifier written in any variant."""
    if raw is None:
        return None
    out = _idc.get(raw)
    if out is not None:
        return out
    t = raw.translate(_TRANS).strip()
    cut = t.find('-')
    out = t
    if cut > 0:
        pre = t[:cut].upper()
        rest = t[cut + 1:]
        width = _PAD.get(pre)
        if width is not None and rest.isdigit():
            out = _SHOWN.get(pre, pre) + '-' + rest.lstrip('0').rjust(width,
                                                                     '0')
    _idc[raw] = out
    return out


def txt(raw):
    """A text cell folded for case and look-alike letters."""
    if raw is None:
        return None
    out = _txc.get(raw)
    if out is None:
        out = raw.translate(_TRANS).strip().lower()
        _txc[raw] = out
    return out


_LOCALES = {'de_de': 'de_DE', 'en_in': 'en_IN', 'en_us': 'en_US',
            'es_es': 'es_ES', 'fr_fr': 'fr_FR', 'ja_jp': 'ja_JP'}

_GROUPED = re.compile(r'-?[0-9]{1,3}(?:[.,\u00a0 ][0-9]{3})+\Z')
_TWODEC = re.compile(r'-?[0-9]+\.[0-9]{2}\Z')
_INT = re.compile(r'-?[0-9]+\Z')
_SEPS = str.maketrans({'.': None, ',': None, ' ': None, '\u00a0': None})

_numc = {}


def _half_even(num_, den):
    """Nearest integer to num_/den with halves to even; den > 0."""
    q, r = divmod(num_, den)
    r2 = 2 * r
    if r2 > den or (r2 == den and (q & 1)):
        q += 1
    return q


def raw_num(s):
    """A numeric cell as written, before any x1000 descaling."""
    if s is None:
        return None
    hit = _numc.get(s)
    if hit is not None:
        return hit[0]
    t = s.translate(_TRANS).strip()
    if _INT.match(t):
        out = int(t)
    elif _GROUPED.match(t):
        out = int(t.translate(_SEPS))
    elif _TWODEC.match(t):
        neg = t[0] == '-'
        body = t[1:] if neg else t
        whole, frac = body.split('.')
        out = _half_even(int(whole) * 100 + int(frac), 100)
        if neg:
            out = -out
    elif t.upper() in ('N/A', ''):
        out = None
    else:
        try:
            out = Fraction(t)
        except (ValueError, ZeroDivisionError):
            out = None
    _numc[s] = (out,)
    return out


def num(s, scaled=False):
    """A val cell, honouring a val_x1000 heading."""
    v = raw_num(s)
    if v is None or not scaled:
        return v
    v = Fraction(v, 1000)
    return int(v) if v.denominator == 1 else v


# ================================================================== instants

def _days(y, m, d):
    """Days from 1970-01-01 to y-m-d, proleptic Gregorian."""
    y -= 1 if m <= 2 else 0
    era = (y if y >= 0 else y - 399) // 400
    yoe = y - era * 400
    doy = (153 * (m - 3 if m > 2 else m + 9) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


_ISO = re.compile(r'([0-9]{4})-([0-9]{2})-([0-9]{2})T'
                  r'([0-9]{2}):([0-9]{2}):([0-9]{2})Z\Z')
_LOC = re.compile(r'([0-9]{4})-([0-9]{2})-([0-9]{2}) '
                  r'([0-9]{2}):([0-9]{2}):([0-9]{2})\.[0-9]{3}\Z')
_BASIC = re.compile(r'([0-9]{4})([0-9]{2})([0-9]{2})T'
                    r'([0-9]{2})([0-9]{2})([0-9]{2})Z\Z')
_EPMS = re.compile(r'-?[0-9]{10,}\Z')
_SER = re.compile(r'[0-9]{1,6}(?:\.[0-9]+)?\Z')

_SERIAL_EPOCH = -2209161600  # 1899-12-30T00:00:00Z
_ZONES = {'utc': 0, 'europe/berlin': 7200, 'america/chicago': -18000,
          'asia/kolkata': 19800, 'america/sao_paulo': -10800,
          'australia/sydney': 36000, 'europe/london': 3600}

_atc = {}


def _civil(m):
    return (_days(int(m.group(1)), int(m.group(2)), int(m.group(3))) * 86400
            + int(m.group(4)) * 3600 + int(m.group(5)) * 60
            + int(m.group(6)))


def parse_at(raw, local_shift=0):
    """Epoch seconds for an instant written in any of the conventions.

    local_shift is the zone offset plus clock offset of the workstation the
    record names; it applies only to workstation local time.
    """
    if raw is None:
        return None
    key = (raw, local_shift)
    hit = _atc.get(key)
    if hit is not None:
        return hit[0]
    t = raw.translate(_TRANS).strip()
    m = _ISO.match(t)
    if m is not None:
        out = _civil(m)
    else:
        m = _LOC.match(t)
        if m is not None:
            out = _civil(m) - local_shift
        elif _EPMS.match(t):
            out = int(t) // 1000
        elif _SER.match(t):
            dot = t.find('.')
            if dot < 0:
                out = _SERIAL_EPOCH + int(t) * 86400
            else:
                frac = t[dot + 1:]
                out = (_SERIAL_EPOCH + int(t[:dot]) * 86400
                       + _half_even(int(frac) * 86400, 10 ** len(frac)))
        else:
            m = _BASIC.match(t)
            if m is not None:
                out = _civil(m)
            elif _GROUPED.match(t):
                out = int(t.translate(_SEPS)) // 1000
            else:
                out = None
    _atc[key] = (out,)
    return out


def iso(ts):
    """ISO 8601 UTC rendering of epoch seconds."""
    days, rem = divmod(ts, 86400)
    z = days + 719468
    era = (z if z >= 0 else z - 146096) // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    y = yoe + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = mp + 3 if mp < 10 else mp - 9
    if m <= 2:
        y += 1
    h, rem = divmod(rem, 3600)
    mi, s = divmod(rem, 60)
    return '%04d-%02d-%02dT%02d:%02d:%02dZ' % (y, m, d, h, mi, s)


# =================================================================== readers

_HEADS = ('rid', 'rec')
_KEYMAP = {'rid': 0, 'rec': 0, 'par': 1, 'pnt': 1, 'val': 2, 'val_x1000': 2,
           'at': 3, 'ts': 3, 'fa': 4, 'a': 4, 'fb': 5, 'b': 5}


def _row(mapping):
    out = [None] * 6
    scaled = False
    for k, v in mapping.items():
        i = _KEYMAP.get(k)
        if i is None:
            continue
        out[i] = v
        if k == 'val_x1000':
            scaled = True
    out.append(scaled)
    return out


def read_delim(path, delim):
    """CSV/TSV whose header band may rename or rescale the columns."""
    out = []
    add = out.append
    with open(path, 'r', encoding='utf-8-sig', newline='') as fh:
        scaled = False
        for r in csv.reader(fh, delimiter=delim):
            if not r:
                continue
            if r[0] in _HEADS:
                scaled = len(r) > 2 and r[2] == 'val_x1000'
                continue
            add((r[0], r[1], r[2], r[3], r[4], r[5], scaled))
    return out


def read_jsonl(path):
    out = []
    loads = json.loads
    with open(path, 'r', encoding='utf-8') as fh:
        for line in fh:
            if line.strip():
                out.append(_row(loads(line)))
    return out


_XREC = re.compile(r'<record\s+([^>]*?)/?>')
_XATTR = re.compile(r'([A-Za-z_0-9]+)="([^"]*)"')


def read_xml(path):
    with open(path, 'r', encoding='utf-8') as fh:
        blob = fh.read()
    return [_row(dict(_XATTR.findall(m.group(1))))
            for m in _XREC.finditer(blob)]


def read_sqlite(path):
    con = sqlite3.connect('file:%s?mode=ro' % path, uri=True)
    try:
        cur = con.execute('select * from records')
        names = [c[0] for c in cur.description]
        idx = [_KEYMAP.get(n) for n in names]
        scaled = 'val_x1000' in names
        out = []
        for rec in cur:
            row = [None] * 6
            for i, v in zip(idx, rec):
                if i is not None:
                    row[i] = v
            row.append(scaled)
            out.append(row)
        return out
    finally:
        con.close()


def read_parquet(path, columns=None):
    import pyarrow.parquet as pq
    table = pq.read_table(path, columns=columns)
    return ({n: table.column(n).to_pylist() for n in table.schema.names},
            table.num_rows)


_XSHEET = re.compile(r'^xl/worksheets/sheet([0-9]+)\.xml$')
_XROW = re.compile(r'<row[ >](.*?)</row>', re.S)
_XCELL = re.compile(r'<c r="([A-Z]+)[0-9]+"([^>]*?)(?:/>|>(.*?)</c>)', re.S)
_XTEXT = re.compile(r'<t[^>]*>(.*?)</t>', re.S)
_XV = re.compile(r'<v[^>]*>(.*?)</v>', re.S)
_XSI = re.compile(r'<si>(.*?)</si>', re.S)


def _xml_text(s):
    if '&' not in s:
        return s
    return (s.replace('&lt;', '<').replace('&gt;', '>')
             .replace('&quot;', '"').replace('&apos;', "'")
             .replace('&amp;', '&'))


def _col(letters):
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def read_xlsx(path):
    """Worksheet rows of an xlsx workbook, sheet by sheet."""
    with zipfile.ZipFile(path) as z:
        sheets = []
        for name in z.namelist():
            m = _XSHEET.match(name)
            if m:
                sheets.append((int(m.group(1)), name))
        sheets.sort()
        shared = None
        if 'xl/sharedStrings.xml' in z.namelist():
            blob = z.read('xl/sharedStrings.xml').decode('utf-8')
            shared = [_xml_text(''.join(_XTEXT.findall(si.group(1))))
                      for si in _XSI.finditer(blob)]
        out = []
        for _, name in sheets:
            blob = z.read(name).decode('utf-8')
            scaled = False
            for rm in _XROW.finditer(blob):
                cells = ['', '', '', '', '', '']
                for cm in _XCELL.finditer(rm.group(1)):
                    i = _col(cm.group(1))
                    if i > 5:
                        continue
                    body = cm.group(3)
                    if body is None:
                        continue
                    kind = cm.group(2)
                    if 't="inlineStr"' in kind:
                        val = ''.join(_XTEXT.findall(body))
                    elif 't="s"' in kind:
                        vm = _XV.search(body)
                        cells[i] = (shared[int(vm.group(1))]
                                    if vm is not None and shared else '')
                        continue
                    elif 't="str"' in kind:
                        vm = _XV.search(body)
                        val = vm.group(1) if vm is not None else ''
                    else:
                        vm = _XV.search(body)
                        val = (''.join(_XTEXT.findall(body)) if vm is None
                               else vm.group(1))
                    cells[i] = _xml_text(val)
                if not cells[0]:
                    continue
                if cells[0] in _HEADS:
                    scaled = cells[2] == 'val_x1000'
                    continue
                out.append((cells[0], cells[1], cells[2], cells[3],
                            cells[4], cells[5], scaled))
    return out


_LOGKV = re.compile(
    r'(?:^| )(rid|rec|par|pnt|val_x1000|val|at|ts|fa|a|fb|b)='
    r'([0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}|\S*)')


def read_log(path):
    out = []
    with open(path, 'r', encoding='utf-8') as fh:
        for line in fh:
            found = _LOGKV.findall(line)
            if found:
                out.append(_row(dict(found)))
    return out


def read_yaml(path):
    """A flat `entries:` list of single level mappings."""
    out = []
    cur = None
    with open(path, 'r', encoding='utf-8') as fh:
        for line in fh:
            s = line.strip()
            if not s or s.startswith('#'):
                continue
            if s.startswith('- '):
                if cur is not None:
                    out.append(_row(cur))
                cur = {}
                s = s[2:]
            if cur is None:
                continue
            k, sep, v = s.partition(':')
            if not sep:
                continue
            v = v.strip()
            if len(v) > 1 and v[0] == '"' and v[-1] == '"':
                v = v[1:-1]
            cur[k.strip()] = v
    if cur is not None:
        out.append(_row(cur))
    return out


def read_ini(path):
    out = []
    with open(path, 'r', encoding='utf-8') as fh:
        for line in fh:
            s = line.strip()
            if not s or s[0] in '[#;':
                continue
            key, sep, rest = s.partition(' = ')
            if not sep:
                continue
            d = {'rid': key.split('@')[0]}
            for part in rest.split(';'):
                k, sep2, v = part.strip().partition('=')
                if sep2:
                    d[k.strip()] = v.strip()
            out.append(_row(d))
    return out


_WTR = re.compile(r'<w:tr[ >](.*?)</w:tr>', re.S)
_WTC = re.compile(r'<w:tc[ >](.*?)</w:tc>', re.S)
_WT = re.compile(r'<w:t(?: [^>]*)?>(.*?)</w:t>', re.S)


def read_docx(path):
    with zipfile.ZipFile(path) as z:
        doc = z.read('word/document.xml').decode('utf-8')
    out = []
    scaled = False
    for tr in _WTR.finditer(doc):
        cells = [''.join(_WT.findall(tc.group(1)))
                 for tc in _WTC.finditer(tr.group(1))]
        if len(cells) < 6:
            continue
        if cells[0] in _HEADS:
            scaled = cells[2] == 'val_x1000'
            continue
        out.append((cells[0], cells[1], cells[2], cells[3], cells[4],
                    cells[5], scaled))
    return out


def read_ics(path):
    """VEVENT records keyed by their iCalendar property names."""
    out = []
    cur = None
    with open(path, 'r', encoding='utf-8') as fh:
        for line in fh:
            s = line.strip()
            if s == 'BEGIN:VEVENT':
                cur = {}
            elif s == 'END:VEVENT':
                if cur is not None:
                    out.append(cur)
                cur = None
            elif cur is not None:
                k, sep, v = s.partition(':')
                if sep:
                    cur[k] = v
    return out


_DOC_EXT = frozenset(('.md', '.html', '.htm', '.pdf', '.rst'))


def generic_rows(path):
    """The record count of a file the release rules do not read."""
    ext = os.path.splitext(path)[1].lower()
    if ext in _DOC_EXT:
        return 0
    if ext == '.csv':
        return len(read_delim(path, ','))
    if ext == '.tsv':
        return len(read_delim(path, '\t'))
    if ext == '.jsonl':
        n = 0
        with open(path, 'rb') as fh:
            for line in fh:
                if line.strip():
                    n += 1
        return n
    if ext == '.json':
        with open(path, 'r', encoding='utf-8') as fh:
            doc = json.load(fh)
        return len(doc['entries'] if isinstance(doc, dict) else doc)
    if ext == '.xml':
        with open(path, 'r', encoding='utf-8') as fh:
            return fh.read().count('<record')
    if ext == '.db':
        con = sqlite3.connect('file:%s?mode=ro' % path, uri=True)
        try:
            return con.execute('select count(*) from records').fetchone()[0]
        finally:
            con.close()
    if ext == '.parquet':
        import pyarrow.parquet as pq
        return pq.ParquetFile(path).metadata.num_rows
    if ext == '.xlsx':
        return len(read_xlsx(path))
    if ext == '.log':
        n = 0
        with open(path, 'rb') as fh:
            for line in fh:
                if b'rid=' in line or b'rec=' in line:
                    n += 1
        return n
    if ext in ('.yaml', '.yml'):
        n = 0
        with open(path, 'rb') as fh:
            for line in fh:
                s = line.lstrip()
                if s.startswith(b'- rid:') or s.startswith(b'- rec:'):
                    n += 1
        return n
    if ext == '.toml':
        n = 0
        with open(path, 'rb') as fh:
            for line in fh:
                if line.startswith(b'[['):
                    n += 1
        return n
    if ext == '.ini':
        return len(read_ini(path))
    if ext == '.txt':
        n = 0
        with open(path, 'rb') as fh:
            for line in fh:
                if line.strip() and not line.startswith(b'#'):
                    n += 1
        return n
    if ext == '.mbox':
        n = 0
        with open(path, 'rb') as fh:
            for line in fh:
                if line.startswith(b'rid: ') or line.startswith(b'rec: '):
                    n += 1
        return n
    if ext == '.docx':
        return len(read_docx(path))
    if ext == '.ics':
        n = 0
        with open(path, 'rb') as fh:
            for line in fh:
                if line.strip() == b'BEGIN:VEVENT':
                    n += 1
        return n
    return 0


# ================================================================= reporting

def q6(value):
    """A ratio quantised to six decimal places, half to even."""
    if value is None:
        return None
    f = value if isinstance(value, Fraction) else Fraction(value)
    n, d = f.numerator, f.denominator
    neg = n < 0
    if neg:
        n = -n
    scaled = _half_even(n * 1000000, d)
    return (-scaled if neg else scaled) / 1000000.0


def ratio(n, d):
    """A reported ratio, null when the denominator is zero."""
    return None if d == 0 else q6(Fraction(n, d))


def write_json(path, obj):
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(json.dumps(obj, sort_keys=True, ensure_ascii=False,
                            allow_nan=False))
        fh.write('\n')


def write_jsonl(path, rows):
    dumps = json.dumps
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        for row in rows:
            fh.write(dumps(row, sort_keys=True, ensure_ascii=False,
                           allow_nan=False))
            fh.write('\n')


# =========================================================== release policy

POLICY = {
    'collection_window_start': '2025-07-01T00:00:00Z',
    'collection_window_end': '2025-10-01T00:00:00Z',
    'adjudication_cutoff': '2025-10-03T18:00:00Z',
    'gold_min_items': 13,
    'gold_floor': {'calder': Fraction(76, 100),
                   'northwind': Fraction(72, 100),
                   'orbit': Fraction(69, 100),
                   'tessel': Fraction(72, 100)},
    'bias_limit': Fraction(12, 100),
    'min_votes': 2,
    'max_prompt_tokens': 768,
    'max_pair_tokens': 1600,
    'contamination_hard': 95,
    'contamination_soft': 80,
    'validation_fraction': Fraction(14, 100),
    'epoch_cap': 2,
    'sequence_length': 1536,
    'global_batch': 16,
    'micro_batch': 4,
    'warmup_fraction': Fraction(3, 100),
    'shard_sequences': 128,
    'min_slice_pairs': 40,
    'max_train_contamination_rate': Fraction(2, 100),
    'min_kappa': Fraction(40, 100),
}

VENDOR_CHOICE_SOURCE = {
    'calder': 'verdicts_vendor_a.jsonl',
    'northwind': 'verdicts_vendor_b.jsonl',
    'orbit': 'verdicts_shard1.parquet',
    'tessel': 'verdicts_shard2.parquet',
}

DIMENSIONS = ('domain', 'difficulty', 'risk', 'locale', 'source')

_PARAM = re.compile(r'^\|\s*([a-z_0-9.]+)\s*\|\s*([^|]+?)\s*\|\s*$', re.M)


def read_policy(path):
    """The release parameters published in corpus_policy.md."""
    out = {}
    with open(path, 'r', encoding='utf-8') as fh:
        body = fh.read()
    for key, value in _PARAM.findall(body):
        if key == 'parameter':
            continue
        if _INT.match(value):
            out[key] = int(value)
        elif re.match(r'-?[0-9]*\.[0-9]+\Z', value):
            out[key] = Fraction(value)
        else:
            out[key] = value
    policy = dict(POLICY)
    floors = dict(POLICY['gold_floor'])
    for key, value in out.items():
        if key.startswith('gold_floor.'):
            floors[key.split('.', 1)[1]] = value
        else:
            policy[key] = value
    policy['gold_floor'] = floors
    return policy


_REGISTRY = re.compile(r'^\|[^|]*\|[^|]*\|\s*([A-Za-z]+)-([0-9]+)\s*\|\s*$',
                       re.M)
_ZONEROW = re.compile(r'^\|\s*([A-Za-z_/]+)\s*\|\s*([+-][0-9]{2}):([0-9]{2})'
                      r'\s*\|\s*$', re.M)


def read_conventions(path):
    """Registered identifier forms and zone offsets from the conventions."""
    with open(path, 'r', encoding='utf-8') as fh:
        body = fh.read()
    for prefix, digits in _REGISTRY.findall(body):
        _PAD[prefix.upper()] = len(digits)
        if prefix != prefix.upper():
            _SHOWN[prefix.upper()] = prefix
    zones = {}
    for zone, hh, mm in _ZONEROW.findall(body):
        sign = -1 if hh[0] == '-' else 1
        zones[zone.lower()] = sign * (int(hh[1:]) * 3600 + int(mm) * 60)
    if zones:
        _ZONES.clear()
        _ZONES.update(zones)
    _idc.clear()


_CHOICE_SRC = re.compile(r'([A-Za-z_0-9.\-]+\.[a-z]+)\s*\(([A-Za-z_]+)\)')


def read_choice_sources(path):
    """The verdict choice export that governs each vendor."""
    with open(path, 'r', encoding='utf-8') as fh:
        body = fh.read()
    m = re.search(r'verdict choice</td><td>(.*?)</td>', body, re.S)
    if m is None:
        return dict(VENDOR_CHOICE_SOURCE)
    found = {v.lower(): f for f, v in _CHOICE_SRC.findall(m.group(1))}
    return found or dict(VENDOR_CHOICE_SOURCE)


def agreement_stats(units):
    """Observed agreement, kappa, rated units and rater pairs for units.

    A unit is a list of category labels.
    """
    obs_num = 0
    obs_den = 0
    pairs = 0
    totals = {}
    grand = 0
    for cats in units:
        n = len(cats)
        obs_den += n * (n - 1)
        pairs += n * (n - 1) // 2
        grand += n
        counts = {}
        for c in cats:
            counts[c] = counts.get(c, 0) + 1
        for c, k in counts.items():
            obs_num += k * (k - 1)
            totals[c] = totals.get(c, 0) + k
    out = {'rated_units': len(units), 'rater_pairs': pairs}
    if obs_den == 0:
        out['observed_agreement'] = None
        out['kappa'] = None
        return out
    observed = Fraction(obs_num, obs_den)
    expected = sum((Fraction(v, grand) ** 2 for v in totals.values()),
                   Fraction(0))
    out['observed_agreement'] = q6(observed)
    if expected == 1:
        out['kappa'] = q6(Fraction(0))
    else:
        out['kappa'] = q6((observed - expected) / (1 - expected))
    return out


def build(data_dir, out_dir):
    names = sorted(n for n in os.listdir(data_dir)
                   if os.path.isfile(os.path.join(data_dir, n)))

    def src(name):
        return os.path.join(data_dir, name)

    read_conventions(src('source_conventions.md'))
    P = read_policy(src('corpus_policy.md'))
    choice_source = read_choice_sources(src('field_precedence.html'))
    win_start = parse_at(P['collection_window_start'])
    win_end = parse_at(P['collection_window_end'])
    adj_cut = parse_at(P['adjudication_cutoff'])

    audit = {}

    # -- workstation zones and clock offsets --------------------------------
    ws_shift = {}
    rows = read_ini(src('workstation_inventory.ini'))
    audit['workstation_inventory.ini'] = len(rows)
    for r in rows:
        w = nid(r[0])
        if w not in ws_shift:
            ws_shift[w] = _ZONES[txt(r[4])] + int(raw_num(r[5]))

    # -- prompts ------------------------------------------------------------
    p_tokens = {}
    p_family = {}
    p_domain = {}
    p_source = {}
    rows = read_delim(src('prompt_registry.csv'), ',')
    audit['prompt_registry.csv'] = len(rows)
    for r in rows:
        p = nid(r[0])
        p_family[p] = nid(r[1])
        p_tokens[p] = num(r[2], r[6])
        p_domain[p] = txt(r[4])
        p_source[p] = txt(r[5])

    p_locale = {}
    p_difficulty = {}
    rows = read_delim(src('slice_attributes.csv'), ',')
    audit['slice_attributes.csv'] = len(rows)
    for r in rows:
        p = nid(r[0])
        loc = txt(r[4])
        p_locale[p] = _LOCALES.get(loc, loc)
        p_difficulty[p] = txt(r[5])

    p_risk = {}
    rows = read_delim(src('prompt_locales.tsv'), '\t')
    audit['prompt_locales.tsv'] = len(rows)
    for r in rows:
        p_risk[nid(r[0])] = txt(r[4])

    # -- completions --------------------------------------------------------
    c_tokens = {}
    rows = read_delim(src('completion_index.csv'), ',')
    audit['completion_index.csv'] = len(rows)
    for r in rows:
        c_tokens[nid(r[0])] = num(r[2], r[6])

    amended = {}
    rows = read_xml(src('completion_amendments.xml'))
    audit['completion_amendments.xml'] = len(rows)
    for r in rows:
        c = nid(r[0])
        t = parse_at(r[3])
        if t is not None and t > amended.get(c, -1 << 62):
            amended[c] = t

    # -- comparisons --------------------------------------------------------
    m_prompt = {}
    m_left = {}
    m_right = {}
    rows = read_xml(src('batch_registry.xml'))
    audit['batch_registry.xml'] = len(rows)
    for r in rows:
        c = nid(r[0])
        m_prompt[c] = nid(r[1])
        m_left[c] = nid(r[4])
        m_right[c] = nid(r[5])
    comparisons = sorted(m_prompt)

    m_amend = {}
    for c in comparisons:
        a = amended.get(m_left[c])
        b = amended.get(m_right[c])
        if a is None:
            if b is not None:
                m_amend[c] = b
        elif b is None or a >= b:
            m_amend[c] = a
        else:
            m_amend[c] = b

    m_balanced = {}
    rows = read_log(src('harness_events.log'))
    audit['harness_events.log'] = len(rows)
    for r in rows:
        c = nid(r[0])
        if c in m_prompt:
            m_balanced[c] = txt(r[5]) == 'balanced'

    # -- annotators ---------------------------------------------------------
    vendor = {}
    rows = read_delim(src('annotator_roster.csv'), ',')
    audit['annotator_roster.csv'] = len(rows)
    for r in rows:
        vendor[nid(r[0])] = txt(r[1])

    # -- verdicts -----------------------------------------------------------
    rows = read_sqlite(src('annotation_store.db'))
    audit['annotation_store.db'] = len(rows)
    v_cmp = {}
    v_ann = {}
    v_ws = {}
    v_at = {}
    v_conf = {}
    for r in rows:
        v = nid(r[0])
        w = nid(r[5])
        v_cmp[v] = nid(r[1])
        v_conf[v] = num(r[2], r[6])
        v_ann[v] = nid(r[4])
        v_ws[v] = w
        v_at[v] = parse_at(r[3], ws_shift.get(w, 0))
    verdicts = sorted(v_cmp)

    v_choice = {}
    for vend in sorted(choice_source):
        name = choice_source[vend]
        if name.endswith('.parquet'):
            cols, nrows = read_parquet(src(name), ['rid', 'fb'])
            audit[name] = nrows
            items = zip(cols['rid'], cols['fb'])
        else:
            rows = read_jsonl(src(name))
            audit[name] = len(rows)
            items = ((r[0], r[5]) for r in rows)
        for rid, fb in items:
            v = nid(rid)
            if vendor.get(v_ann.get(v)) == vend:
                v_choice[v] = txt(fb)

    # -- gold calibration ---------------------------------------------------
    gold_answer = {}
    rows = read_delim(src('gold_set.tsv'), '\t')
    audit['gold_set.tsv'] = len(rows)
    for r in rows:
        gold_answer[nid(r[0])] = nid(r[5])

    gold_retired = {}
    rows = read_delim(src('gold_answers_revised.csv'), ',')
    audit['gold_answers_revised.csv'] = len(rows)
    for r in rows:
        if txt(r[4]) == 'retired':
            c = nid(r[0])
            t = parse_at(r[3])
            if t is not None and t < gold_retired.get(c, 1 << 62):
                gold_retired[c] = t

    # -- errata -------------------------------------------------------------
    retired_prompts = set()
    optout_prompts = set()
    voided = set()
    restored = set()
    rows = read_docx(src('errata_register.docx'))
    audit['errata_register.docx'] = len(rows)
    for r in rows:
        action = txt(r[4])
        ident = nid(r[0])
        if action == 'retire':
            retired_prompts.add(ident)
        elif action == 'optout':
            optout_prompts.add(ident)
        elif action == 'void':
            voided.add(ident)
        elif action == 'restore':
            restored.add(ident)
    voided -= restored

    # -- adjudications ------------------------------------------------------
    adj_choice = {}
    adj_at = {}
    rows = read_jsonl(src('adjudications.jsonl'))
    audit['adjudications.jsonl'] = len(rows)
    for r in rows:
        c = nid(r[0])
        adj_choice[c] = txt(r[4])
        t = parse_at(r[3])
        if t is not None and t > adj_at.get(c, -1 << 62):
            adj_at[c] = t

    approved = set()
    rows = read_docx(src('review_minutes.docx'))
    audit['review_minutes.docx'] = len(rows)
    for r in rows:
        if txt(r[4]) == 'approved':
            approved.add(nid(r[0]))

    # -- collection freezes -------------------------------------------------
    spans = {}
    events = read_ics(src('freeze_windows.ics'))
    audit['freeze_windows.ics'] = len(events)
    for ev in events:
        w = nid(ev['X-WORKSTATION'])
        start = parse_at(ev['DTSTART'])
        hours = raw_num(ev['X-HOURS'])
        if start is None or hours is None:
            continue
        spans.setdefault(w, []).append((start, start + int(hours) * 3600))
    freeze_start = {}
    freeze_end = {}
    for w, items in spans.items():
        items.sort()
        starts = [a for a, _ in items]
        ends = []
        best = -1 << 62
        for _, b in items:
            best = b if b > best else best
            ends.append(best)
        freeze_start[w] = starts
        freeze_end[w] = ends

    def frozen_at(w, t):
        starts = freeze_start.get(w)
        if not starts:
            return False
        i = bisect.bisect_right(starts, t)
        return i > 0 and freeze_end[w][i - 1] > t

    # -- contamination ------------------------------------------------------
    contamination = {}
    rows = read_jsonl(src('contamination_hits.jsonl'))
    audit['contamination_hits.jsonl'] = len(rows)
    for r in rows:
        p = nid(r[0])
        s = num(r[2], r[6])
        if s is not None and s > contamination.get(p, -(1 << 62)):
            contamination[p] = s

    # -- near duplicate clusters -------------------------------------------
    cluster_of = {}
    members = {}
    effective = {}
    rows = read_delim(src('dedup_clusters.tsv'), '\t')
    audit['dedup_clusters.tsv'] = len(rows)
    for r in rows:
        cl = nid(r[0])
        p = nid(r[1])
        cluster_of[p] = cl
        bag = members.get(cl)
        if bag is None:
            members[cl] = bag = set()
        bag.add(p)
        t = parse_at(r[3])
        if t is not None and t < effective.get(p, 1 << 62):
            effective[p] = t

    clusters = {}
    canonical_of = {}
    for cl in sorted(members):
        mem = sorted(members[cl])
        canon = min(mem, key=lambda p: (effective.get(p, 1 << 62), p))
        canonical_of[cl] = canon
        eff = effective.get(canon)
        clusters[cl] = {
            'canonical': canon,
            'members': mem,
            'dropped': [p for p in mem if p != canon],
            'canonical_effective_at': iso(eff) if eff is not None else None,
        }

    # -- mixture targets ----------------------------------------------------
    target = {}
    rows = read_xlsx(src('mixture_targets.xlsx'))
    audit['mixture_targets.xlsx'] = len(rows)
    for r in rows:
        w = raw_num(r[5])
        if w is not None:
            target[txt(r[4])] = Fraction(w, 100)

    # -- slice universe -----------------------------------------------------
    slice_keys = set()
    rows = read_yaml(src('slice_definitions.yaml'))
    audit['slice_definitions.yaml'] = len(rows)
    for r in rows:
        dim, _, val = r[0].translate(_TRANS).strip().partition('-')
        dim = dim.lower()
        val = _LOCALES.get(val.lower(), val) if dim == 'locale' else val.lower()
        slice_keys.add(dim + '-' + val)

    # -- every other export -------------------------------------------------
    for name in names:
        if name not in audit:
            audit[name] = generic_rows(src(name))

    # ========================================================== standing ===
    gold_items = {}
    gold_hits = {}
    bal_total = {}
    bal_left = {}
    for v in verdicts:
        ann = v_ann[v]
        cmr = v_cmp[v]
        ch = v_choice.get(v)
        g = gold_answer.get(cmr)
        if g is not None:
            rt = gold_retired.get(cmr)
            t = v_at[v]
            if rt is None or t is None or rt > t:
                gold_items[ann] = gold_items.get(ann, 0) + 1
                if ((ch == 'left' and m_left.get(cmr) == g)
                        or (ch == 'right' and m_right.get(cmr) == g)):
                    gold_hits[ann] = gold_hits.get(ann, 0) + 1
        if m_balanced.get(cmr) and (ch == 'left' or ch == 'right'):
            bal_total[ann] = bal_total.get(ann, 0) + 1
            if ch == 'left':
                bal_left[ann] = bal_left.get(ann, 0) + 1

    standing = {}
    biased = {}
    annotator_standing = {}
    for ann in sorted(vendor):
        gi = gold_items.get(ann, 0)
        gh = gold_hits.get(ann, 0)
        bt = bal_total.get(ann, 0)
        bl = bal_left.get(ann, 0)
        agree = Fraction(gh, gi) if gi else None
        bias = Fraction(bl, bt) - Fraction(1, 2) if bt else None
        vend = vendor[ann]
        floor = P['gold_floor'].get(vend)
        admitted = (gi >= P['gold_min_items'] and agree is not None
                    and floor is not None and agree >= floor)
        standing[ann] = 'admitted' if admitted else 'gated'
        biased[ann] = bias is not None and abs(bias) > P['bias_limit']
        annotator_standing[ann] = {
            'vendor': vend,
            'gold_items': gi,
            'gold_hits': gh,
            'gold_agreement': q6(agree),
            'balanced_verdicts': bt,
            'a_side_bias': q6(bias),
            'biased': biased[ann],
            'standing': standing[ann],
        }

    # ===================================================== admissibility ===
    adm_rows = []
    adm_by_cmp = {}
    admissible_total = 0
    for v in verdicts:
        ann = v_ann[v]
        cmr = v_cmp[v]
        t = v_at[v]
        latest = m_amend.get(cmr)
        if standing.get(ann, 'gated') != 'admitted':
            reason = 'annotator_gated'
        elif t is None or t < win_start or t >= win_end:
            reason = 'outside_window'
        elif frozen_at(v_ws[v], t):
            reason = 'freeze_window'
        elif latest is not None and t <= latest:
            reason = 'stale_amendment'
        elif biased.get(ann) and not m_balanced.get(cmr, False):
            reason = 'unbalanced_biased'
        elif v in voided:
            reason = 'voided'
        else:
            reason = None
        adm_rows.append({'verdict_id': v, 'comparison': cmr,
                         'annotator': ann, 'admissible': reason is None,
                         'reason': reason})
        if reason is None:
            admissible_total += 1
            bag = adm_by_cmp.get(cmr)
            if bag is None:
                adm_by_cmp[cmr] = bag = []
            bag.append(v)

    # ======================================================== resolution ===
    res_rows = []
    resolved_of = {}
    margin_of = {}
    route_of = {}
    resolved_total = 0
    for cmr in comparisons:
        adm = adm_by_cmp.get(cmr, ())
        votes = len(adm)
        choice = None
        route = None
        margin = None
        a_choice = adj_choice.get(cmr)
        a_at = adj_at.get(cmr)
        latest = m_amend.get(cmr)
        valid = (a_choice is not None and a_at is not None
                 and cmr in approved and a_at < adj_cut
                 and (latest is None or a_at > latest))
        if valid:
            choice = a_choice
            route = 'adjudicated'
            margin = Fraction(1)
        elif votes < P['min_votes']:
            route = 'insufficient'
        else:
            route = 'majority'
            counts = {}
            conf = {}
            for v in adm:
                ch = v_choice.get(v)
                counts[ch] = counts.get(ch, 0) + 1
                c = v_conf.get(v)
                conf[ch] = conf.get(ch, 0) + (0 if c is None else c)
            ranked = sorted(counts,
                            key=lambda c: (-counts[c], -conf[c], str(c)))
            choice = ranked[0]
            other = max((counts[c] for c in ranked[1:]), default=0)
            margin = Fraction(counts[choice] - other, votes)
        if choice is not None:
            resolved_total += 1
            resolved_of[cmr] = choice
            margin_of[cmr] = margin
            route_of[cmr] = route
        res_rows.append({'comparison_id': cmr, 'resolved': choice,
                         'route': route, 'votes': votes,
                         'margin': q6(margin)})

    # ========================================================= agreement ===
    rated = []
    for cmr in comparisons:
        adm = adm_by_cmp.get(cmr)
        if adm is None or len(adm) < 2:
            continue
        cats = []
        for v in adm:
            ch = v_choice.get(v)
            cats.append('tie' if ch == 'both_bad' else ch)
        rated.append((cmr, adm, cats))

    overall_units = [cats for _, _, cats in rated]
    by_domain_units = {}
    by_vendor_units = {}
    for cmr, adm, cats in rated:
        dom = p_domain.get(m_prompt[cmr])
        by_domain_units.setdefault(dom, []).append(cats)
        split = {}
        for v, cat in zip(adm, cats):
            split.setdefault(vendor.get(v_ann[v]), []).append(cat)
        for vend, group in split.items():
            if len(group) >= 2:
                by_vendor_units.setdefault(vend, []).append(group)

    agreement = {
        'overall': agreement_stats(overall_units),
        'by_vendor': {k: agreement_stats(v)
                      for k, v in sorted(by_vendor_units.items())},
        'by_domain': {k: agreement_stats(v)
                      for k, v in sorted(by_domain_units.items())},
    }

    # ======================================================= eligibility ===
    prompts = sorted(p_tokens)
    resolved_lr = set()
    for cmr, ch in resolved_of.items():
        if ch == 'left' or ch == 'right':
            resolved_lr.add(m_prompt[cmr])

    hard = P['contamination_hard']
    soft = P['contamination_soft']
    eligible = set()
    elig_rows = []
    for p in prompts:
        cl = cluster_of.get(p)
        sim = contamination.get(p)
        tok = p_tokens.get(p)
        if p in retired_prompts:
            reason = 'retired'
        elif p in optout_prompts:
            reason = 'opted_out'
        elif sim is not None and sim >= hard:
            reason = 'contaminated'
        elif cl is not None and canonical_of[cl] != p:
            reason = 'duplicate'
        elif tok is not None and tok > P['max_prompt_tokens']:
            reason = 'over_length'
        elif p not in resolved_lr:
            reason = 'no_resolved_pair'
        else:
            reason = None
            eligible.add(p)
        elig_rows.append({'prompt_id': p, 'eligible': reason is None,
                          'reason': reason, 'cluster': cl,
                          'family': p_family.get(p),
                          'source': p_source.get(p)})

    # ============================================================= pairs ===
    pairs = []
    for cmr in comparisons:
        ch = resolved_of.get(cmr)
        if ch != 'left' and ch != 'right':
            continue
        p = m_prompt[cmr]
        if p not in eligible:
            continue
        left = m_left[cmr]
        right = m_right[cmr]
        tok = p_tokens.get(p)
        lt = c_tokens.get(left)
        rt = c_tokens.get(right)
        if tok is None or lt is None or rt is None:
            continue
        total = tok + lt + rt
        if total > P['max_pair_tokens']:
            continue
        pairs.append({
            'pair_id': 'PP-' + cmr.split('-', 1)[1],
            'comparison': cmr,
            'prompt': p,
            'family': p_family.get(p),
            'source': p_source.get(p),
            'chosen': left if ch == 'left' else right,
            'rejected': right if ch == 'left' else left,
            'margin': q6(margin_of[cmr]),
            'route': route_of[cmr],
            'tokens': total,
        })
    pairs.sort(key=lambda r: r['pair_id'])
    total_pairs = len(pairs)

    # ============================================================= split ===
    fam_pairs = {}
    for row in pairs:
        f = row['family']
        fam_pairs[f] = fam_pairs.get(f, 0) + 1

    soft_families = set()
    for p, sim in contamination.items():
        if soft <= sim < hard:
            f = p_family.get(p)
            if f in fam_pairs:
                soft_families.add(f)

    threshold = P['validation_fraction'] * total_pairs
    families = {}
    val_pairs = 0
    for f in sorted(soft_families):
        families[f] = 'validation'
        val_pairs += fam_pairs[f]
    for f in sorted(fam_pairs):
        if f in families:
            continue
        if val_pairs < threshold:
            families[f] = 'validation'
            val_pairs += fam_pairs[f]
        else:
            families[f] = 'train'

    train_pairs = [r for r in pairs if families[r['family']] == 'train']
    validation_pairs = [r for r in pairs
                        if families[r['family']] == 'validation']

    split_assignment = {
        'families': families,
        'family_counts': {
            'train': sum(1 for v in families.values() if v == 'train'),
            'validation': sum(1 for v in families.values()
                              if v == 'validation'),
        },
        'pair_counts': {'train': len(train_pairs),
                        'validation': len(validation_pairs)},
        'validation_share': ratio(len(validation_pairs), total_pairs),
    }

    # =========================================================== mixture ===
    available = {s: 0 for s in target}
    for row in train_pairs:
        s = row['source']
        available[s] = available.get(s, 0) + 1
    budget = len(train_pairs)
    cap = {s: P['epoch_cap'] * available.get(s, 0) for s in available}

    allocation = {s: Fraction(0) for s in available}
    capped = {s: False for s in available}
    free = set(s for s in available if available[s] > 0)
    unallocated = Fraction(budget)
    while free:
        weight = sum((target.get(s, Fraction(0)) for s in free), Fraction(0))
        if weight == 0:
            for s in free:
                allocation[s] = Fraction(0)
            break
        offers = {s: unallocated * target.get(s, Fraction(0)) / weight
                  for s in free}
        over = sorted(s for s in free if offers[s] > cap[s])
        if not over:
            for s in free:
                allocation[s] = offers[s]
            break
        for s in over:
            allocation[s] = Fraction(cap[s])
            capped[s] = True
            unallocated -= cap[s]
            free.discard(s)

    mixture_plan = {}
    allocated_sum = 0
    for s in sorted(available):
        alloc = allocation[s]
        whole = alloc.numerator // alloc.denominator
        allocated_sum += whole
        mixture_plan[s] = {
            'available_pairs': available[s],
            'target_weight': q6(target.get(s)),
            'allocated_pairs': whole,
            'effective_weight': ratio(alloc, budget),
            'epochs': (q6(alloc / available[s]) if available[s] else None),
            'capped': capped[s],
        }
    mixture_plan['_total'] = {'budget_pairs': budget,
                              'allocated_pairs': allocated_sum}

    # =========================================================== packing ===
    seq_len = P['sequence_length']
    packed = 0
    dropped = 0
    sequences = 0
    tokens_used = 0
    current = 0
    for row in train_pairs:
        t = row['tokens']
        if t > seq_len:
            dropped += 1
            continue
        if sequences == 0 or current + t > seq_len:
            sequences += 1
            current = 0
        current += t
        tokens_used += t
        packed += 1
    capacity = sequences * seq_len
    packing_plan = {
        'sequence_length': seq_len,
        'packed_pairs': packed,
        'dropped_pairs': dropped,
        'sequences': sequences,
        'token_capacity': capacity,
        'tokens_used': tokens_used,
        'padding_tokens': capacity - tokens_used,
        'packing_efficiency': ratio(tokens_used, capacity),
    }

    # ========================================================== schedule ===
    gb = P['global_batch']
    steps = sequences // gb
    shard_seq = P['shard_sequences']
    training_schedule = {
        'sequences': sequences,
        'global_batch': gb,
        'micro_batch': P['micro_batch'],
        'gradient_accumulation': gb // P['micro_batch'],
        'optimizer_steps': steps,
        'warmup_steps': _half_even(
            (P['warmup_fraction'] * steps).numerator,
            (P['warmup_fraction'] * steps).denominator),
        'shards': -(-sequences // shard_seq),
        'shard_sequences': shard_seq,
        'dropped_tail_sequences': sequences - steps * gb,
    }

    # ==================================================== slice coverage ===
    slice_pairs = {k: 0 for k in slice_keys}
    slice_train = {k: 0 for k in slice_keys}
    slice_val = {k: 0 for k in slice_keys}
    slice_tokens = {k: 0 for k in slice_keys}
    attrs = {'domain': p_domain, 'difficulty': p_difficulty,
             'risk': p_risk, 'locale': p_locale, 'source': p_source}
    for row in pairs:
        p = row['prompt']
        is_train = families[row['family']] == 'train'
        for dim in DIMENSIONS:
            val = attrs[dim].get(p)
            if val is None:
                continue
            key = dim + '-' + val
            slice_pairs[key] = slice_pairs.get(key, 0) + 1
            slice_tokens[key] = slice_tokens.get(key, 0) + row['tokens']
            if is_train:
                slice_train[key] = slice_train.get(key, 0) + 1
            else:
                slice_val[key] = slice_val.get(key, 0) + 1
    slice_coverage = {k: {'pairs': slice_pairs[k], 'train': slice_train[k],
                          'validation': slice_val[k],
                          'tokens': slice_tokens[k]}
                      for k in sorted(slice_pairs) if slice_pairs[k] > 0}

    # ============================================================ gates ===
    universe = set(slice_keys) | set(k for k, v in slice_pairs.items() if v)
    undersized = sorted(k for k in universe
                        if slice_pairs.get(k, 0) < P['min_slice_pairs'])
    fam_splits = {}
    for row in pairs:
        fam_splits.setdefault(row['family'], set()).add(
            families[row['family']])
    straddle = any(len(s) > 1 for s in fam_splits.values())
    contaminated_train = sum(
        1 for row in train_pairs
        if contamination.get(row['prompt'], -1) >= soft)
    rate = (Fraction(contaminated_train, total_pairs) if total_pairs else None)
    kappa = agreement['overall']['kappa']
    gates = {
        'min_slice_pairs_met': not undersized,
        'no_family_straddles_split': not straddle,
        'train_contamination_within_limit':
            rate is not None and rate <= P['max_train_contamination_rate'],
        'kappa_above_floor': kappa is not None and kappa >= P['min_kappa'],
        'packing_efficiency_reported': sequences >= 1,
    }
    gates['release_approved'] = all(gates.values())
    release_gates = {
        'gates': gates,
        'undersized_slices': undersized,
        'train_contamination_rate': q6(rate),
        'total_pairs': total_pairs,
    }

    # ========================================================== artifacts ===
    control = {
        'prompts': len(p_tokens),
        'completions': len(c_tokens),
        'comparisons': len(m_prompt),
        'verdicts': len(verdicts),
        'admissible': admissible_total,
        'resolved': resolved_total,
        'eligible': len(eligible),
        'pairs': total_pairs,
    }

    def out(name):
        return os.path.join(out_dir, name)

    os.makedirs(out_dir, exist_ok=True)
    write_json(out('annotator_standing.json'), annotator_standing)
    write_jsonl(out('verdict_admissibility.jsonl'), adm_rows)
    write_jsonl(out('comparison_resolution.jsonl'), res_rows)
    write_json(out('agreement.json'), agreement)
    write_jsonl(out('prompt_eligibility.jsonl'), elig_rows)
    write_json(out('dedup_clusters.json'), clusters)
    write_jsonl(out('preference_pairs.jsonl'), pairs)
    write_json(out('split_assignment.json'), split_assignment)
    write_json(out('mixture_plan.json'), mixture_plan)
    write_json(out('packing_plan.json'), packing_plan)
    write_json(out('training_schedule.json'), training_schedule)
    write_json(out('slice_coverage.json'), slice_coverage)
    write_json(out('source_audit.json'), audit)
    write_json(out('control_reconciliation.json'), control)
    write_json(out('release_gates.json'), release_gates)


def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: build.py <DATA_DIR> <OUT_DIR>\n')
        return 2
    build(argv[1], argv[2])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
