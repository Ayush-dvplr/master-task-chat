#!/usr/bin/env python3
"""Build-minute chargeback settlement for the Kestrel monorepo CI fleets.

Usage: settle.py DATA_DIR OUT_DIR

The program reads only DATA_DIR, writes only into OUT_DIR and takes every
rule from the policy documents shipped in DATA_DIR.
"""
import calendar
import csv
import gzip
import json
import os
import re
import sqlite3
import sys
import time
import zipfile
import zlib
from fractions import Fraction
from urllib.request import pathname2url

# --------------------------------------------------------------------------
# numeric helpers
# --------------------------------------------------------------------------


def round_half_even(fr):
    """Round a Fraction to the nearest integer, ties to even."""
    fr = Fraction(fr)
    q, r = divmod(fr.numerator, fr.denominator)
    twice = 2 * r
    if twice > fr.denominator:
        q += 1
    elif twice == fr.denominator and q % 2 != 0:
        q += 1
    return q


# --------------------------------------------------------------------------
# codec decoders
# --------------------------------------------------------------------------

XL_EPOCH_DAYS = 25569  # 1899-12-30 -> 1970-01-01

_ISO_Z = re.compile(r'^(\d{4})-(\d\d)-(\d\d)[T ](\d\d):(\d\d):(\d\d)Z$')
_NAIVE = re.compile(r'^(\d{4})-(\d\d)-(\d\d)[T ](\d\d):(\d\d):(\d\d)(\+fold)?$')
_OFFSET = re.compile(r'^(\d{4})-(\d\d)-(\d\d)[T ](\d\d):(\d\d):(\d\d)'
                     r'([+-])(\d\d):?(\d\d)$')


def _ymdhms(m):
    return calendar.timegm((int(m.group(1)), int(m.group(2)), int(m.group(3)),
                            int(m.group(4)), int(m.group(5)), int(m.group(6)),
                            0, 0, 0))


def iso_from_epoch(sec):
    if sec is None:
        return None
    st = time.gmtime(sec)
    return '%04d-%02d-%02dT%02d:%02d:%02dZ' % (st.tm_year, st.tm_mon,
                                               st.tm_mday, st.tm_hour,
                                               st.tm_min, st.tm_sec)


class Zones(object):
    """Clock zone offsets as published by the rate methodology."""

    def __init__(self, rules):
        self.rules = rules

    def resolve(self, naive_epoch, zone, fold):
        """Translate a wall-clock reading (parsed as if UTC) into an instant."""
        off1, switch, off2 = self.rules[zone]
        if switch is None:
            return naive_epoch - off1
        if fold:
            return naive_epoch - off2
        if naive_epoch < switch + off1:
            return naive_epoch - off1
        return naive_epoch - off2


def decode_timestamp(raw, codec, zones=None, zone=None):
    s = raw.strip()
    if s == '':
        return None
    if codec == 'epoch':
        return int(s)
    if codec == 'epoch_ms':
        v = int(s)
        return v // 1000 if v >= 0 else -((-v) // 1000)
    if codec == 'xl1900':
        return round_half_even((Fraction(s) - XL_EPOCH_DAYS) * 86400)
    if codec == 'iso_off':
        m = _OFFSET.match(s)
        off = int(m.group(8)) * 3600 + int(m.group(9)) * 60
        if m.group(7) == '-':
            off = -off
        return _ymdhms(m) - off
    if codec in ('iso_z', 'utc_naive'):
        m = _ISO_Z.match(s) or _NAIVE.match(s)
        return _ymdhms(m)
    if codec == 'local':
        m = _NAIVE.match(s)
        if m is None:
            return _ymdhms(_ISO_Z.match(s))
        return zones.resolve(_ymdhms(m), zone, bool(m.group(7)))
    raise ValueError('timestamp codec %r' % codec)


def decode_duration(raw, codec):
    """Return integer milliseconds."""
    s = raw.strip()
    if s == '':
        return None
    if codec == 'ms':
        return int(s)
    if codec == 'us':
        return round_half_even(Fraction(int(s), 1000))
    if codec == 'ns':
        return round_half_even(Fraction(int(s), 1000000))
    if codec == 's3':
        return round_half_even(Fraction(s) * 1000)
    raise ValueError('duration codec %r' % codec)


def decode_money(raw, codec):
    """Return integer micro-dollars."""
    s = raw.strip()
    if s == '':
        return None
    if codec == 'micro':
        return int(s)
    if codec == 'usd6':
        return round_half_even(Fraction(s) * 1000000)
    if codec == 'eu6':
        return round_half_even(
            Fraction(s.replace('.', '').replace(',', '.')) * 1000000)
    if codec == 'kusd9':
        return round_half_even(Fraction(s) * 1000000000)
    raise ValueError('money codec %r' % codec)


def decode_integer(raw, codec):
    s = raw.strip()
    if s == '':
        return None
    if codec == 'plain':
        return int(s)
    if codec == 'sep':
        return int(s.replace(',', ''))
    if codec == 'eu':
        return int(s.replace('.', ''))
    if codec == 'kib':
        return int(s.replace(',', '')) * 1024
    raise ValueError('integer codec %r' % codec)


def decode_identifier(raw, codec):
    if codec == 'exact':
        return raw
    if codec == 'ws':
        return raw.strip()
    if codec == 'upper':
        return raw.strip().lower()
    raise ValueError('identifier codec %r' % codec)


# the kind names this program uses, as the Codec glossary names them
GLOSSARY_KIND = {'ts': 'timestamp', 'dur': 'duration', 'money': 'money',
                 'int': 'integer', 'id': 'identifier', 'txt': 'identifier'}


def cid(s):
    """Canonical form of a coded identifier: padding and case carry no meaning."""
    if s is None:
        return None
    return s.strip().lower()


# --------------------------------------------------------------------------
# document tables
# --------------------------------------------------------------------------


def _unesc(s):
    return (s.replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"')
             .replace('&#39;', "'").replace('&amp;', '&'))


def _norm_caption(s):
    s = s.replace('\\(', '(').replace('\\)', ')').strip()
    return re.sub(r'\s*\((?:continued|cont)\)$', '', s).strip()


def _rows_to_dicts(rows):
    """Turn raw table rows into dicts, honouring restated headers."""
    out = []
    header = None
    hset = None
    for r in rows:
        if header is None:
            header, hset = r, frozenset(r)
            continue
        if len(r) == len(header) and frozenset(r) == hset:
            header = r
            continue
        out.append(dict(zip(header, r)))
    return out


def md_tables(path):
    tabs = {}
    name = None
    rows = None
    for line in read_lines(path):
            line = line.rstrip('\r')
            m = re.match(r'^\*\*Table:\s*(.*?)\*\*\s*$', line)
            if m:
                if name is not None:
                    tabs.setdefault(name, []).extend(rows)
                name = _norm_caption(m.group(1))
                rows = []
                continue
            if name is None:
                continue
            if line.startswith('|'):
                cells = [c.strip() for c in line.split('|')[1:-1]]
                if all(re.fullmatch(r'-{2,}', c) for c in cells):
                    continue
                rows.append(cells)
            elif line.strip() == '':
                continue
            else:
                tabs.setdefault(name, []).extend(rows)
                name, rows = None, None
    if name is not None:
        tabs.setdefault(name, []).extend(rows)
    return tabs


def html_tables(path):
    data = read_text(path)
    tabs = {}
    for m in re.finditer(r'<table>\s*<caption>(.*?)</caption>(.*?)</table>',
                         data, re.S):
        rows = []
        for rm in re.finditer(r'<tr>(.*?)</tr>', m.group(2), re.S):
            rows.append([_unesc(re.sub(r'<[^>]*>', '', c)) for c in
                         re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>',
                                    rm.group(1), re.S)])
        tabs.setdefault(_norm_caption(m.group(1)), []).extend(rows)
    return tabs


def pdf_lines(path):
    raw = open(path, 'rb').read()
    out = []
    for m in re.finditer(rb'stream\r?\n(.*?)endstream', raw, re.S):
        s = m.group(1)
        try:
            s = zlib.decompress(s)
        except Exception:
            pass
        for tm in re.finditer(rb'\((.*?)\)\s*Tj', s, re.S):
            out.append(re.sub(r'\\([()\\])', r'\1',
                              tm.group(1).decode('latin-1')))
    return out


def pdf_tables(path):
    tabs = {}
    name = None
    rows = None
    for line in pdf_lines(path):
        m = re.match(r'^\s*Table:\s*(.*?)\s*$', line)
        if m:
            if name is not None:
                tabs.setdefault(name, []).extend(rows)
            name = _norm_caption(m.group(1))
            rows = []
            continue
        if name is None:
            continue
        if '|' in line:
            rows.append([c.strip() for c in line.split('|')])
        elif line.strip() == '':
            continue
        else:
            tabs.setdefault(name, []).extend(rows)
            name, rows = None, None
    if name is not None:
        tabs.setdefault(name, []).extend(rows)
    return tabs


def docx_tables(path):
    d = zipfile.ZipFile(path).read('word/document.xml').decode('utf-8')
    tabs = {}
    pending = None
    for m in re.finditer(r'<w:p[ >].*?</w:p>|<w:tbl>.*?</w:tbl>', d, re.S):
        t = m.group(0)
        if t.startswith('<w:tbl'):
            rows = []
            for rm in re.finditer(r'<w:tr[ >].*?</w:tr>', t, re.S):
                cells = []
                for cm in re.finditer(r'<w:tc[ >].*?</w:tc>', rm.group(0), re.S):
                    cells.append(_unesc(''.join(re.findall(
                        r'<w:t(?:\s[^>]*)?>(.*?)</w:t>', cm.group(0), re.S))))
                rows.append(cells)
            if pending:
                tabs.setdefault(pending, []).extend(rows)
            pending = None
        else:
            mm = re.match(r'^\s*Table:\s*(.*?)\s*$', _unesc(''.join(
                re.findall(r'<w:t(?:\s[^>]*)?>(.*?)</w:t>', t, re.S))))
            if mm:
                pending = _norm_caption(mm.group(1))
    return tabs


def doc_text(path):
    if path.endswith('.md'):
        return read_text(path)
    if path.endswith('.html'):
        body = re.sub(r'<table>.*?</table>', ' ', read_text(path), flags=re.S)
        return _unesc(re.sub(r'<[^>]*>', ' ', body))
    if path.endswith('.pdf'):
        return '\n'.join(pdf_lines(path))
    if path.endswith('.docx'):
        d = zipfile.ZipFile(path).read('word/document.xml').decode('utf-8')
        d = re.sub(r'<w:tbl>.*?</w:tbl>', ' ', d, flags=re.S)
        return _unesc(' '.join(re.findall(
            r'<w:t(?:\s[^>]*)?>(.*?)</w:t>', d, re.S)))
    raise ValueError(path)


DOC_READERS = {
    'settlement_authority.md': md_tables,
    'scope_rules.md': md_tables,
    'field_precedence.html': html_tables,
    'control_totals_draft.html': html_tables,
    'rate_methodology.pdf': pdf_tables,
    'audit_annex.pdf': pdf_tables,
    'amendment_minutes.docx': docx_tables,
    'errata_register.docx': docx_tables,
}


def read_documents(data_dir):
    tables = {}
    prose = {}
    for fn, reader in DOC_READERS.items():
        path = os.path.join(data_dir, fn)
        tables[fn] = dict((n, _rows_to_dicts(rows))
                          for n, rows in reader(path).items())
        prose[fn] = doc_text(path)
    return tables, prose


def parse_zones(prose):
    """Clock zone offsets written in the rate methodology."""
    pat = re.compile(
        r'([A-Z]{2}[+-]\d+(?::\d+)?) is UTC([+-]\d+(?::\d+)?)'
        r'(?: until (\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ) and '
        r'UTC([+-]\d+(?::\d+)?) after)?')

    def off(tok):
        sign = -1 if tok[0] == '-' else 1
        body = tok[1:]
        h, mi = (body.split(':') + ['0'])[:2]
        return sign * (int(h) * 3600 + int(mi) * 60)

    rules = {}
    text = re.sub(r'\s+', ' ', prose['rate_methodology.pdf'])
    for m in pat.finditer(text):
        switch = decode_timestamp(m.group(3), 'iso_z') if m.group(3) else None
        rules[m.group(1)] = (off(m.group(2)), switch,
                             off(m.group(4)) if m.group(4) else None)
    return Zones(rules)


# --------------------------------------------------------------------------
# raw readers: one list of column -> raw text dicts per file, in file order
# --------------------------------------------------------------------------

def _decode(data):
    """Exports mix UTF-8 and Latin-1 bytes in their reviewer notes."""
    try:
        return data.decode('utf-8')
    except UnicodeDecodeError:
        return data.decode('latin-1')


def read_text(path):
    opener = gzip.open if path.endswith('.gz') else open
    with opener(path, 'rb') as fh:
        return _decode(fh.read())


def read_lines(path):
    return read_text(path).split('\n')


_KV = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)=("(?:[^"]*)"|[^\s]*)')


def read_logfmt(path):
    rows = []
    for line in read_lines(path):
            if not line.strip():
                continue
            row = {}
            for k, v in _KV.findall(line):
                row[k] = v[1:-1] if v.startswith('"') else v
            if row:
                rows.append(row)
    return rows


def read_lockfile(path):
    rows = []
    for line in read_lines(path):
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            row = {}
            for k, v in _KV.findall(line):
                row[k] = v[1:-1] if v.startswith('"') else v
            rows.append(row)
    return rows


def read_jsonl(path):
    rows = []
    for line in read_lines(path):
        if line.strip():
            rows.append(json.loads(line))
    return rows


def read_delimited(path, delim):
    lines = read_text(path).splitlines()
    if delim == ',':
        cells = [r for r in csv.reader(lines)]
    else:
        cells = [line.split(delim) for line in lines]
    cells = [c for c in cells if c and any(x != '' for x in c)]
    if delim != ',':
        width = len(cells[0])
        cells = [c + [''] * (width - len(c)) if len(c) < width else c[:width]
                 for c in cells]
    return _rows_to_dicts(cells)


def read_fixed_width(path, layouts):
    """layouts: {layout id: [(column, width)]} in declared position order."""
    rows = []
    cur = None
    for line in read_lines(path):
            line = line.rstrip('\r')
            if not line:
                continue
            if line[0] == 'H':
                cur = layouts[line[1:].strip()]
                continue
            body = line[1:]
            row = {}
            pos = 0
            for col, width in cur:
                row[col] = body[pos:pos + width].strip()
                pos += width
            rows.append(row)
    return rows


def read_ini(path):
    rows = []
    row = None
    for line in read_lines(path):
            line = line.rstrip('\r')
            if line.startswith(';') or line.startswith('#'):
                continue
            if line.startswith('['):
                if row is not None:
                    rows.append(row)
                row = {}
                continue
            if '=' in line and row is not None:
                k, v = line.split('=', 1)
                row[k.strip()] = v.strip()
    if row:
        rows.append(row)
    return rows


_TOML_PAIR = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)\s*=\s*("(?:[^"]*)"|[^,}]+)')


def read_toml(path):
    """Return (scalars, {array name: [row dict]})."""
    scalars = {}
    arrays = {}
    cur = None
    for line in read_lines(path):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if line == ']':
                cur = None
                continue
            m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\[\s*$', line)
            if m:
                cur = m.group(1)
                arrays.setdefault(cur, [])
                continue
            if cur is not None and line.startswith('{'):
                row = {}
                for k, v in _TOML_PAIR.findall(line):
                    v = v.strip()
                    row[k] = v[1:-1] if v.startswith('"') else v
                arrays[cur].append(row)
                continue
            m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$', line)
            if m and cur is None:
                v = m.group(2).strip()
                scalars[m.group(1)] = v[1:-1] if v.startswith('"') else v
    return scalars, arrays


def read_yaml(path):
    """Minimal reader for the flow-mapping lists used by the exports."""
    sections = {}
    cur = None
    for raw in read_lines(path):
            raw = raw.rstrip('\r')
            if not raw.strip() or raw.lstrip().startswith('#'):
                continue
            m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*):\s*$', raw)
            if m:
                cur = m.group(1)
                sections.setdefault(cur, [])
                continue
            body = raw.strip()
            if body.startswith('-'):
                body = body[1:].strip()
            if body.startswith('{'):
                row = {}
                for k, v in re.findall(
                        r'([A-Za-z_][A-Za-z0-9_]*):\s*("(?:[^"]*)"|[^,}]+)',
                        body):
                    v = v.strip()
                    row[k] = v[1:-1] if v.startswith('"') else v
                sections[cur].append(row)
    return sections


def _propname(name):
    """ICS and mail headers name the columns in upper case with hyphens."""
    name = re.sub(r'^X-', '', name).lower().replace('-', '_')
    return 'flag' if name == 'review_flag' else name


def read_ics(path):
    rows = []
    row = None
    for line in read_lines(path):
            line = line.rstrip('\r')
            if line == 'BEGIN:VEVENT':
                row = {}
                continue
            if line == 'END:VEVENT':
                rows.append(row)
                row = None
                continue
            if row is None or ':' not in line:
                continue
            k, v = line.split(':', 1)
            row[_propname(k)] = v
    return rows


def read_mbox(path):
    rows = []
    row = None
    for line in read_lines(path):
            line = line.rstrip('\r')
            if line.startswith('From '):
                if row:
                    rows.append(row)
                row = {}
                continue
            if row is None:
                continue
            m = re.match(r'^([A-Za-z][A-Za-z0-9-]*):\s?(.*)$', line)
            if m:
                row[_propname(m.group(1))] = m.group(2)
    if row:
        rows.append(row)
    return rows


def read_xml_elements(path, tag):
    data = read_text(path)
    rows = []
    for m in re.finditer(r'<%s\s+([^>]*?)/>' % tag, data):
        rows.append(dict((k, _unesc(v)) for k, v in
                         re.findall(r'([A-Za-z_][\w.-]*)="([^"]*)"',
                                    m.group(1))))
    return rows


def read_sqlite(path, base):
    rows = []
    con = sqlite3.connect('file:%s?mode=ro' % pathname2url(os.path.abspath(path)),
                          uri=True)
    con.text_factory = _decode
    try:
        names = [r[0] for r in con.execute(
            "select name from sqlite_master where type='table'")]
        order = [base] + sorted(n for n in names
                                if n != base and n.startswith(base))
        for name in order:
            if name not in names:
                continue
            cur = con.execute('select * from "%s"' % name)
            cols = [d[0] for d in cur.description]
            for r in cur:
                rows.append(dict(zip(cols, r)))
    finally:
        con.close()
    return rows


def read_xlsx(path):
    """Return {sheet name: [[cell text]]} with cells placed by column letter."""
    z = zipfile.ZipFile(path)
    names = z.namelist()
    shared = []
    if 'xl/sharedStrings.xml' in names:
        s = z.read('xl/sharedStrings.xml').decode('utf-8')
        for si in re.findall(r'<si>(.*?)</si>', s, re.S):
            shared.append(''.join(re.findall(r'<t[^>]*>(.*?)</t>', si, re.S)))
    rels = dict(re.findall(r'Id="([^"]+)"[^>]*Target="([^"]+)"',
                           z.read('xl/_rels/workbook.xml.rels').decode('utf-8')))
    out = {}
    wb = z.read('xl/workbook.xml').decode('utf-8')
    for m in re.finditer(r'<sheet [^>]*/>', wb):
        tag = m.group(0)
        name = _unesc(re.search(r'name="([^"]*)"', tag).group(1))
        rid = re.search(r'r:id="([^"]*)"', tag).group(1)
        target = rels[rid].lstrip('/')
        if target not in names:
            target = 'xl/' + target.split('xl/')[-1]
        rows = []
        data = z.read(target).decode('utf-8')
        for rm in re.finditer(r'<row[^>]*>(.*?)</row>', data, re.S):
            cells = {}
            for cm in re.finditer(r'<c([^>]*?)(?:/>|>(.*?)</c>)', rm.group(1),
                                  re.S):
                attr, body = cm.group(1) or '', cm.group(2) or ''
                ref = re.search(r'r="([A-Z]+)\d+"', attr)
                col = ref.group(1) if ref else None
                ty = re.search(r't="([^"]*)"', attr)
                ty = ty.group(1) if ty else 'n'
                if ty == 'inlineStr':
                    val = ''.join(re.findall(r'<t[^>]*>(.*?)</t>', body, re.S))
                else:
                    v = re.search(r'<v>(.*?)</v>', body, re.S)
                    if v is None:
                        val = ''
                    elif ty == 's':
                        val = shared[int(v.group(1))]
                    else:
                        val = v.group(1)
                cells[col] = _unesc(val)
            if not cells:
                continue
            width = max(_colnum(c) for c in cells if c) + 1
            rows.append([cells.get(_colname(i), '') for i in range(width)])
        out[name] = rows
    return out


def _colnum(letters):
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def _colname(idx):
    s = ''
    idx += 1
    while idx:
        idx, r = divmod(idx - 1, 26)
        s = chr(65 + r) + s
    return s


def read_xlsx_table(path, base):
    """Concatenate the sheet named `base` with its continuation sheets."""
    sheets = read_xlsx(path)
    cells = []
    for name in [base] + sorted(n for n in sheets
                                if n != base and _norm_caption(n) == base):
        cells.extend(sheets[name])
    return _rows_to_dicts(cells)


# --------------------------------------------------------------------------
# the kind of every column of every primary table
# --------------------------------------------------------------------------

COLKIND = {
    'action_keys.lock': {'action': 'id', 'target': 'txt', 'digest': 'txt',
                         'recorded': 'ts', 'flag': 'txt'},
    'amendment_minutes.docx': {'id': 'txt', 'job': 'id', 'class': 'txt',
                               'ratified_on': 'ts', 'flag': 'txt'},
    'approval_thread.mbox': {'message_id': 'txt', 'date': 'txt',
                             'subject': 'txt', 'erratum': 'txt',
                             'decision': 'txt', 'decided_at': 'ts',
                             'flag': 'txt'},
    'artifact_registry.db': {'artifact': 'id', 'target': 'txt',
                             'bytes': 'int', 'created': 'ts', 'flag': 'txt'},
    'attempt_events.jsonl': {'attempt_id': 'id', 'job_id': 'id',
                             'attempt': 'int', 'runner': 'id',
                             'target': 'txt', 'status': 'txt',
                             'started': 'ts', 'duration_ms': 'dur',
                             'flag': 'txt'},
    'attempt_events_v3.jsonl': {'attempt_id': 'id', 'job_id': 'id',
                                'runner': 'id', 'status': 'txt',
                                'started_utc': 'ts', 'duration_ms': 'dur',
                                'cancel_origin': 'txt', 'schema': 'txt',
                                'flag': 'txt'},
    'audit_annex.pdf': {'control_id': 'txt', 'file': 'txt', 'block': 'int',
                        'records': 'int', 'control_sum': 'int',
                        'status': 'txt', 'batch': 'txt', 'flag': 'txt'},
    'change_freeze.ics': {'uid': 'txt', 'sequence': 'int', 'status': 'txt',
                          'dtstart': 'ts', 'dtend': 'ts', 'runner': 'id',
                          'flag': 'txt'},
    'clock_sync.txt': {'runner': 'id', 'window_from': 'ts',
                       'window_to': 'ts', 'skew_ms': 'int', 'flag': 'txt',
                       'note': 'txt'},
    'close_parameters.toml': {'id': 'txt', 'runner': 'id', 'day': 'ts',
                              'flag': 'txt'},
    'control_totals_draft.html': {'control_id': 'txt', 'file': 'txt',
                                  'block': 'int', 'records': 'int',
                                  'control_sum': 'int', 'batch': 'txt',
                                  'flag': 'txt'},
    'cost_centers.csv': {'handle': 'txt', 'cost_center': 'id',
                         'effective_from': 'ts', 'flag': 'txt',
                         'note': 'txt'},
    'edges.csv': {'child': 'txt', 'parent': 'txt', 'kind': 'txt',
                  'declared_at': 'ts', 'flag': 'txt', 'note': 'txt'},
    'env_allowlist.json': {'action': 'id', 'reads': 'list',
                           'observed': 'ts', 'flag': 'txt'},
    'errata_register.docx': {'id': 'txt', 'attempt': 'id', 'field': 'txt',
                             'old': 'txt', 'new': 'txt', 'filed': 'ts',
                             'flag': 'txt'},
    'evictions.log': {'ts': 'ts', 'shard': 'int', 'action': 'id',
                      'eviction': 'id', 'flag': 'txt'},
    'field_precedence.html': {'job': 'id', 'target': 'txt',
                              'submitter': 'txt', 'opened': 'ts',
                              'batch': 'txt', 'flag': 'txt'},
    'flaky_windows.tsv': {'target': 'txt', 'testcase': 'txt', 'from': 'ts',
                          'until': 'ts', 'flag': 'txt', 'note': 'txt'},
    'fleet_north.log': {'ts': 'ts', 'attempt': 'id', 'job': 'id',
                        'no': 'int', 'runner': 'id', 'target': 'txt',
                        'status': 'txt', 'mono_start': 'dur',
                        'mono_end': 'dur', 'wall_end': 'ts', 'flag': 'txt'},
    'fleet_policy.ini': {'runner': 'id', 'rev': 'int',
                         'effective_from': 'ts', 'sku': 'id',
                         'agent_version': 'txt', 'region': 'txt',
                         'flag': 'txt'},
    'fleet_south.log': {'ts': 'ts', 'attempt': 'id', 'job': 'id',
                        'no': 'int', 'runner': 'id', 'target': 'txt',
                        'status': 'txt', 'mono_start': 'dur',
                        'mono_end': 'dur', 'wall_end': 'ts', 'flag': 'txt'},
    'gc_events.csv': {'artifact': 'id', 'at': 'ts', 'action': 'txt',
                      'flag': 'txt', 'note': 'txt'},
    'input_manifests.tsv': {'action': 'id', 'path': 'txt',
                            'declared': 'txt', 'size': 'int', 'flag': 'txt',
                            'note': 'txt'},
    'instance_classes.csv': {'sku': 'id', 'instance_class': 'txt',
                             'arch': 'txt', 'spot': 'txt',
                             'listed_at': 'ts', 'flag': 'txt',
                             'note': 'txt'},
    'invoice_lines.xlsx': {'line_id': 'id', 'runner': 'id',
                           'week_start': 'ts', 'vendor': 'txt',
                           'billed': 'money', 'flag': 'txt'},
    'invoice_restatement.csv': {'line_id': 'id', 'type': 'txt',
                                'restated': 'money', 'flag': 'txt',
                                'note': 'txt'},
    'junit_results.xml': {'attempt': 'id', 'testcase': 'txt',
                          'time': 'dur', 'flag': 'txt'},
    'lookups_archive.jsonl.gz': {'kind': 'txt', 'id': 'id', 'action': 'id',
                                 'at': 'ts', 'result': 'txt', 'flag': 'txt'},
    'lookups_shard1.jsonl': {'lookup': 'id', 'attempt': 'id',
                             'action': 'id', 'result': 'txt', 'at': 'ts',
                             'bytes': 'int', 'flag': 'txt'},
    'opening_balances.json': {'cost_center': 'id', 'bucket': 'txt',
                              'amount': 'money', 'batch': 'txt',
                              'flag': 'txt'},
    'owners_registry.txt': {'seq': 'int', 'pattern': 'txt',
                            'handle': 'txt', 'batch': 'txt', 'flag': 'txt',
                            'note': 'txt'},
    'ownership_patterns_approved.tsv': {'kind': 'txt', 'target': 'txt',
                                        'handle': 'txt', 'effective': 'ts',
                                        'batch': 'txt', 'flag': 'txt',
                                        'note': 'txt'},
    'package_metadata.xml': {'target': 'txt', 'language': 'txt',
                             'toolchain': 'txt', 'manifest_bytes': 'int',
                             'batch': 'txt', 'flag': 'txt'},
    'rate_card.xlsx': {'rate_id': 'txt', 'instance_class': 'txt',
                       'region': 'txt', 'effective_from': 'ts',
                       'recorded_at': 'ts', 'micro_per_min': 'money',
                       'flag': 'txt'},
    'rate_card_final.xlsx': {'rate_id': 'txt', 'instance_class': 'txt',
                             'region': 'txt', 'effective_from': 'ts',
                             'micro_per_min': 'money', 'status': 'txt',
                             'flag': 'txt'},
    'rate_methodology.pdf': {'sku': 'id', 'granularity_s': 'int',
                             'batch': 'txt', 'flag': 'txt'},
    'retry_policy.yaml': {'job': 'id', 'budget': 'int', 'flag': 'txt'},
    'scope_rules.md': {'target': 'txt', 'scope': 'txt', 'reviewed': 'ts',
                       'batch': 'txt', 'flag': 'txt'},
    'settlement_authority.md': {'runner': 'id', 'rev': 'int',
                                'region': 'txt', 'batch': 'txt',
                                'flag': 'txt'},
    'settlement_ledger.db': {'posting': 'id', 'cost_center': 'id',
                             'amount': 'money', 'posted_at': 'ts',
                             'reverses': 'txt', 'batch': 'txt',
                             'flag': 'txt'},
    'shard_index.tsv': {'prefix': 'id', 'shard': 'int',
                        'assigned_at': 'ts', 'flag': 'txt', 'note': 'txt'},
    'targets.csv': {'target': 'txt', 'kind': 'txt', 'registered_at': 'ts',
                    'flag': 'txt', 'note': 'txt'},
    'team_roster.xlsx': {'handle': 'txt', 'team': 'txt',
                         'effective_from': 'ts', 'batch': 'txt',
                         'flag': 'txt'},
    'toolchain_pins.yaml': {'target': 'txt', 'constraint': 'txt',
                            'pinned_at': 'ts', 'flag': 'txt'},
    'toolchain_pins_resolved.json': {'target': 'txt',
                                     'resolved_open': 'txt',
                                     'resolved_close': 'txt',
                                     'resolved_at': 'ts', 'flag': 'txt'},
    'usage_events.jsonl': {'idem': 'txt', 'attempt': 'id', 'job': 'id',
                           'seq': 'int', 'runner': 'id', 'target': 'txt',
                           'state': 'txt', 'start': 'ts', 'elapsed': 'dur',
                           'received': 'ts', 'flag': 'txt'},
    'usage_export_legacy.log': {'kind': 'txt', 'ts': 'ts', 'attempt': 'id',
                                'runner': 'id', 'elapsed': 'dur',
                                'flag': 'txt'},
    'vendor_statement.xml': {'line': 'id', 'vendor': 'txt',
                             'locale': 'txt', 'credit': 'money',
                             'runner': 'id', 'flag': 'txt'},
}
COLKIND['lookups_shard2.jsonl'] = COLKIND['lookups_shard1.jsonl']
COLKIND['lookups_shard3.jsonl.gz'] = COLKIND['lookups_shard1.jsonl']

ATTEMPT_FILES = ['fleet_north.log', 'fleet_south.log', 'attempt_events.jsonl',
                 'usage_events.jsonl']
# S-3 names fleet_north, fleet_south, attempt_events and usage_events as the
# attempt records of fleets north, south, east and west.
FLEET_OF_FILE = {'fleet_north.log': 'north', 'fleet_south.log': 'south',
                 'attempt_events.jsonl': 'east', 'usage_events.jsonl': 'west'}
SHARD_FILES = ['lookups_shard1.jsonl', 'lookups_shard2.jsonl',
               'lookups_shard3.jsonl.gz']

# column names of the attempt sources, per file
ATTEMPT_COLS = {
    'fleet_north.log': ('attempt', 'job', 'no', 'runner', 'ts', 'status'),
    'fleet_south.log': ('attempt', 'job', 'no', 'runner', 'ts', 'status'),
    'attempt_events.jsonl': ('attempt_id', 'job_id', 'attempt', 'runner',
                             'started', 'status'),
    'usage_events.jsonl': ('attempt', 'job', 'seq', 'runner', 'start',
                           'state'),
}


# --------------------------------------------------------------------------
# the corpus: raw rows, contexts, decoded rows
# --------------------------------------------------------------------------


class Corpus(object):
    """Every primary table of the close, read and decoded."""

    def __init__(self, data_dir):
        self.dir = data_dir
        self.docs, self.prose = read_documents(data_dir)
        self.zones = parse_zones(self.prose)
        self._load_policy()
        self.raw = {}
        self.rows = {}
        self._read_everything()

    # -- policy from the documents ----------------------------------------

    def _all_doc_rows(self, table):
        out = []
        for tabs in self.docs.values():
            out.extend(tabs.get(table, []))
        return out

    def _load_policy(self):
        self.conventions = {}
        for r in self._all_doc_rows('Field conventions'):
            key = (r['file'], r['column'])
            dim, mapping = self.conventions.setdefault(key, (r['context'], {}))
            mapping[r['value']] = r['codec']
        self.aliases = {}
        for r in self._all_doc_rows('Column aliases'):
            self.aliases.setdefault(r['file'], {})[r['alias']] = r['column']
        self.sentinels = {}
        for r in self._all_doc_rows('Sentinel register'):
            self.sentinels[(r['file'], r['column'])] = r['token']
        self.region_zone = dict((r['region'], r['zone'])
                                for r in self._all_doc_rows('Region zones'))
        # a column no convention names uses the first codec of its kind
        first = {}
        for r in self._all_doc_rows('Codec glossary'):
            first.setdefault(r['kind'], r['codec'])
        self.default_codec = dict((k, first[g])
                                  for k, g in GLOSSARY_KIND.items())
        self.catalog = dict((r['file'], r)
                            for r in self._all_doc_rows('Source catalog'))
        layouts = {}
        for r in self._all_doc_rows('Fixed-width layouts'):
            layouts.setdefault(r['file'], {}).setdefault(r['layout'], []) \
                .append((int(r['position']), r['column'], int(r['width'])))
        self.layouts = {}
        for f, lays in layouts.items():
            self.layouts[f] = dict(
                (lid, [(c, w) for _, c, w in sorted(cols)])
                for lid, cols in lays.items())

    # -- decoding ----------------------------------------------------------

    def codec_for(self, fname, column, kind, ctx):
        entry = self.conventions.get((fname, column))
        if entry is None:
            return self.default_codec[kind]
        dim, mapping = entry
        return mapping.get(ctx.get(dim), self.default_codec[kind])

    def decode(self, fname, raw, ctx, zone):
        out = {}
        for col, kind in COLKIND[fname].items():
            val = raw.get(col)
            if kind == 'list':
                out[col] = list(val) if val is not None else None
                continue
            if val is None:
                out[col] = None
                continue
            val = str(val)
            sent = self.sentinels.get((fname, col))
            if sent is not None and val.strip() == sent.strip():
                out[col] = None
                continue
            codec = self.codec_for(fname, col, kind, ctx)
            if kind == 'ts':
                out[col] = decode_timestamp(val, codec, self.zones, zone)
            elif kind == 'dur':
                out[col] = decode_duration(val, codec)
            elif kind == 'money':
                out[col] = decode_money(val, codec)
            elif kind == 'int':
                out[col] = decode_integer(val, codec)
            elif kind == 'id':
                out[col] = decode_identifier(val, codec)
            else:
                out[col] = val
        return out

    def _normalise(self, fname, rows):
        """Resolve the column aliases of one export."""
        alias = self.aliases.get(fname, {})
        out = []
        for r in rows:
            out.append(dict((alias.get(k, k), v) for k, v in r.items()))
        return out

    def _ingest(self, fname, rows, ctx_fn):
        """Store raw and decoded rows of one primary table."""
        rows = self._normalise(fname, rows)
        self.raw[fname] = rows
        dec = []
        for r in rows:
            ctx, zone = ctx_fn(r)
            if 'batch' in r:
                ctx.setdefault('batch', r['batch'])
            dec.append(self.decode(fname, r, ctx, zone))
        self.rows[fname] = dec
        return dec

    # -- context helpers ---------------------------------------------------

    def _zone_of_region(self, region):
        return self.region_zone.get(region)

    def ctx_batch(self, row):
        return {'batch': row.get('batch')}, None

    def _ctx_region(self, region):
        return {'region': region}, self._zone_of_region(region)

    def _ctx_lang(self, lang, runner=None):
        zone = None
        if runner is not None:
            zone = self._zone_of_region(self.runner_region.get(cid(runner)))
        return {'lang': lang}, zone

    def lang_of_target(self, target):
        return self.target_language.get(target)

    def lang_of_job(self, job):
        return self.lang_of_target(self.job_target.get(cid(job)))

    def lang_of_attempt(self, attempt):
        return self.lang_of_job(self.attempt_job.get(cid(attempt)))

    # -- reading -----------------------------------------------------------

    def path(self, fname):
        return os.path.join(self.dir, fname)

    def _read_everything(self):
        d = self.path

        # --- documents whose coded columns key on the printed batch -------
        self._ingest('settlement_authority.md',
                     self.docs['settlement_authority.md']['Runner placements'],
                     self.ctx_batch)
        self.runner_region = {}
        for r in self.rows['settlement_authority.md']:
            if r['rev'] == 1:
                self.runner_region.setdefault(cid(r['runner']), r['region'])

        self._ingest('package_metadata.xml',
                     read_xml_elements(d('package_metadata.xml'), 'Package'),
                     self.ctx_batch)
        self.target_language = {}
        self.target_toolchain = {}
        for r in self.rows['package_metadata.xml']:
            self.target_language.setdefault(r['target'], r['language'])
            self.target_toolchain.setdefault(r['target'], r['toolchain'])

        self._ingest('field_precedence.html',
                     self.docs['field_precedence.html']['Job register'],
                     self.ctx_batch)
        self.job_target = {}
        self.job_submitter = {}
        for r in self.rows['field_precedence.html']:
            self.job_target.setdefault(cid(r['job']), r['target'])
            self.job_submitter.setdefault(cid(r['job']), r['submitter'])

        self._ingest('scope_rules.md',
                     self.docs['scope_rules.md']['Target scope register'],
                     self.ctx_batch)
        self._ingest('rate_methodology.pdf',
                     self.docs['rate_methodology.pdf']['Billing granularity'],
                     self.ctx_batch)
        self._ingest('audit_annex.pdf',
                     self.docs['audit_annex.pdf']['Block controls'],
                     self.ctx_batch)
        self._ingest('control_totals_draft.html',
                     self.docs['control_totals_draft.html']['Draft controls'],
                     self.ctx_batch)
        self._ingest('owners_registry.txt',
                     read_fixed_width(d('owners_registry.txt'),
                                      self.layouts['owners_registry.txt']),
                     self.ctx_batch)
        self._ingest('ownership_patterns_approved.tsv',
                     read_delimited(d('ownership_patterns_approved.tsv'), '\t'),
                     self.ctx_batch)
        self._ingest('opening_balances.json',
                     json.loads(read_text(d('opening_balances.json')))['balances'],
                     self.ctx_batch)
        self._ingest('settlement_ledger.db',
                     read_sqlite(d('settlement_ledger.db'), 'postings'),
                     self.ctx_batch)
        self._ingest('team_roster.xlsx',
                     read_xlsx_table(d('team_roster.xlsx'), 'Roster'),
                     self.ctx_batch)

        # --- rows keyed on the language of a target -----------------------
        by_target = lambda col: (
            lambda row: self._ctx_lang(self.lang_of_target(row.get(col))))

        self._ingest('action_keys.lock',
                     read_lockfile(d('action_keys.lock')), by_target('target'))
        self.action_target = {}
        for r in self.rows['action_keys.lock']:
            self.action_target.setdefault(cid(r['action']), r['target'])

        self._ingest('targets.csv', read_delimited(d('targets.csv'), ','),
                     by_target('target'))
        self._ingest('edges.csv', read_delimited(d('edges.csv'), ','),
                     by_target('child'))
        self._ingest('flaky_windows.tsv',
                     read_delimited(d('flaky_windows.tsv'), '\t'),
                     by_target('target'))
        self._ingest('toolchain_pins.yaml',
                     read_yaml(d('toolchain_pins.yaml'))['pins'],
                     by_target('target'))
        resolved = json.loads(read_text(d('toolchain_pins_resolved.json')))
        self._ingest('toolchain_pins_resolved.json', resolved['resolved'],
                     by_target('target'))
        self.digest_version = dict((r['digest'], (r['toolchain'], r['version']))
                                   for r in resolved['digests'])
        self._ingest('artifact_registry.db',
                     read_sqlite(d('artifact_registry.db'), 'artifacts'),
                     by_target('target'))
        self.artifact_target = {}
        for r in self.rows['artifact_registry.db']:
            self.artifact_target.setdefault(cid(r['artifact']), r['target'])
        self._ingest('gc_events.csv', read_delimited(d('gc_events.csv'), ','),
                     lambda row: self._ctx_lang(self.lang_of_target(
                         self.artifact_target.get(cid(row.get('artifact'))))))

        by_action = lambda row: self._ctx_lang(self.lang_of_target(
            self.action_target.get(cid(row.get('action')))))
        self._ingest('input_manifests.tsv',
                     read_delimited(d('input_manifests.tsv'), '\t'), by_action)
        allow = json.loads(read_text(d('env_allowlist.json')))
        self._ingest('env_allowlist.json', allow['observations'], by_action)
        self.allowed_env = set(r['variable'] for r in allow['allowed'])
        self._ingest('evictions.log', read_logfmt(d('evictions.log')),
                     by_action)
        self._ingest('lookups_archive.jsonl.gz',
                     read_jsonl(d('lookups_archive.jsonl.gz')), by_action)
        for f in SHARD_FILES:
            self._ingest(f, read_jsonl(d(f)), by_action)

        prefix_action = {}
        for key in self.action_target:
            prefix_action.setdefault(key[:6], key)
        self._ingest('shard_index.tsv',
                     read_delimited(d('shard_index.tsv'), '\t'),
                     lambda row: self._ctx_lang(self.lang_of_target(
                         self.action_target.get(
                             prefix_action.get(cid(row.get('prefix')))))))

        # --- rows keyed on the language of a job --------------------------
        by_job = lambda jcol, rcol: (
            lambda row: self._ctx_lang(self.lang_of_job(row.get(jcol)),
                                       row.get(rcol)))
        self._ingest('fleet_north.log', read_logfmt(d('fleet_north.log')),
                     by_job('job', 'runner'))
        self._ingest('fleet_south.log', read_logfmt(d('fleet_south.log')),
                     by_job('job', 'runner'))
        self._ingest('attempt_events.jsonl',
                     read_jsonl(d('attempt_events.jsonl')),
                     by_job('job_id', 'runner'))
        self._ingest('usage_events.jsonl',
                     read_jsonl(d('usage_events.jsonl')),
                     by_job('job', 'runner'))
        self._ingest('retry_policy.yaml',
                     read_yaml(d('retry_policy.yaml'))['budgets'],
                     lambda row: self._ctx_lang(self.lang_of_job(
                         row.get('job'))))
        self._ingest('amendment_minutes.docx',
                     self.docs['amendment_minutes.docx']['Amendments'],
                     lambda row: self._ctx_lang(self.lang_of_job(
                         row.get('job'))))

        self.attempt_job = {}
        self.attempt_runner = {}
        for f in ATTEMPT_FILES:
            acol, jcol = ATTEMPT_COLS[f][0], ATTEMPT_COLS[f][1]
            for r in self.rows[f]:
                self.attempt_job.setdefault(cid(r[acol]), r[jcol])
                self.attempt_runner.setdefault(cid(r[acol]), r['runner'])

        # --- rows keyed on the language of an attempt ---------------------
        by_attempt = lambda col: (
            lambda row: self._ctx_lang(self.lang_of_attempt(row.get(col)),
                                       self.attempt_runner.get(
                                           cid(row.get(col)))))
        self._ingest('attempt_events_v3.jsonl',
                     read_jsonl(d('attempt_events_v3.jsonl')),
                     by_job('job_id', 'runner'))
        self._ingest('usage_export_legacy.log',
                     read_logfmt(d('usage_export_legacy.log')),
                     by_attempt('attempt'))
        self._ingest('junit_results.xml',
                     read_xml_elements(d('junit_results.xml'), 'testcase'),
                     by_attempt('attempt'))
        self._ingest('errata_register.docx',
                     self.docs['errata_register.docx']['Errata'],
                     by_attempt('attempt'))
        self.erratum_attempt = dict((cid(r['id']), r['attempt'])
                                    for r in self.rows['errata_register.docx'])
        self._ingest('approval_thread.mbox', read_mbox(d('approval_thread.mbox')),
                     lambda row: self._ctx_lang(
                         self.lang_of_attempt(self.erratum_attempt.get(
                             cid(row.get('erratum')))),
                         self.attempt_runner.get(cid(self.erratum_attempt.get(
                             cid(row.get('erratum')))))))

        # --- rows keyed on a region ---------------------------------------
        by_runner = lambda col: (
            lambda row: self._ctx_region(
                self.runner_region.get(cid(row.get(col)))))
        self._ingest('clock_sync.txt',
                     read_fixed_width(d('clock_sync.txt'),
                                      self.layouts['clock_sync.txt']),
                     by_runner('runner'))
        self._ingest('change_freeze.ics', read_ics(d('change_freeze.ics')),
                     by_runner('runner'))
        self._ingest('fleet_policy.ini', read_ini(d('fleet_policy.ini')),
                     by_runner('runner'))
        self.params, arrays = read_toml(d('close_parameters.toml'))
        self._ingest('close_parameters.toml', arrays['reservation'],
                     by_runner('runner'))
        sku_runner = {}
        for r in self.rows['fleet_policy.ini']:
            sku_runner.setdefault(cid(r['sku']), r['runner'])
        self._ingest('instance_classes.csv',
                     read_delimited(d('instance_classes.csv'), ','),
                     lambda row: self._ctx_region(self.runner_region.get(
                         cid(sku_runner.get(cid(row.get('sku')))))))
        self._ingest('rate_card.xlsx',
                     read_xlsx_table(d('rate_card.xlsx'), 'Rates'),
                     lambda row: self._ctx_region(row.get('region')))
        final = read_xlsx(d('rate_card_final.xlsx'))
        self._ingest('rate_card_final.xlsx',
                     read_xlsx_table(d('rate_card_final.xlsx'), 'Final rates'),
                     lambda row: self._ctx_region(row.get('region')))
        spot = _rows_to_dicts(final['Spot credits'])
        self.spot_credit = dict((r['instance_class'],
                                 int(r['spot_credit_permille'])) for r in spot)
        self._ingest('vendor_statement.xml',
                     read_xml_elements(d('vendor_statement.xml'), 'Line'),
                     by_runner('runner'))
        self.vendor_locale = {}
        self.line_locale = {}
        for r in self.rows['vendor_statement.xml']:
            self.vendor_locale.setdefault(r['vendor'], r['locale'])
            self.line_locale.setdefault(cid(r['line']), r['locale'])

        # --- rows keyed on an organisation or a vendor locale -------------
        self.handle_team_roster = {}
        for r in self.rows['team_roster.xlsx']:
            self.handle_team_roster.setdefault(r['handle'], r['team'])
        self._ingest('cost_centers.csv',
                     read_delimited(d('cost_centers.csv'), ','),
                     lambda row: ({'org': (self.handle_team_roster.get(
                         row.get('handle')) or '').split('-')[0]}, None))
        self._ingest('invoice_lines.xlsx',
                     read_xlsx_table(d('invoice_lines.xlsx'), 'Lines'),
                     lambda row: ({'locale': self.vendor_locale.get(
                         row.get('vendor'))}, None))
        self._ingest('invoice_restatement.csv',
                     read_delimited(d('invoice_restatement.csv'), ','),
                     lambda row: ({'locale': self.line_locale.get(
                         cid(row.get('line_id')))}, None))

        # --- extra tables used by the rules -------------------------------
        self.transfers = _rows_to_dicts(
            read_xlsx(d('team_roster.xlsx'))['Transfers'])
        policy = read_yaml(d('retry_policy.yaml'))
        self.fleet_grace = dict((r['fleet'], int(r['grace_s']))
                                for r in policy['preemption_grace'])
        self.policy_defaults = dict((r['key'], r['value'])
                                    for r in policy['defaults'])
        self.toolchain_releases = self.docs['scope_rules.md']['Toolchain releases']
        self.billing_classes = dict(
            (r['class'], int(r['multiplier_permille']))
            for r in self.docs['rate_methodology.pdf']['Billing classes'])
        self.cc_merges = self.docs['field_precedence.html']['Cost center merges']
        self.late_voids = set(
            cid(r['posting'])
            for r in self.docs['control_totals_draft.html']['Late voids'])

    # -- distinct records --------------------------------------------------

    def distinct_flags(self, fname):
        """One flag per data row: True when the row is not a re-export."""
        seen = set()
        out = []
        cols = set()
        for r in self.raw[fname]:
            cols.update(r)
        cols = sorted(cols)
        for r in self.raw[fname]:
            key = tuple(_hashable(r.get(c)) for c in cols)
            fresh = key not in seen
            seen.add(key)
            out.append(fresh)
        return out


def _hashable(v):
    if isinstance(v, list):
        return tuple(v)
    return v if v is None else str(v)


# --------------------------------------------------------------------------
# target label patterns and toolchain constraints
# --------------------------------------------------------------------------


def pattern_regex(pattern):
    """`*` matches inside one path segment, `**` matches anything."""
    out = []
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        if ch == '*':
            if pattern[i:i + 2] == '**':
                out.append('.*')
                i += 2
            else:
                out.append('[^/:]*')
                i += 1
            continue
        out.append(re.escape(ch))
        i += 1
    return re.compile('^' + ''.join(out) + '$')


def version_tuple(v):
    return tuple(int(p) for p in v.split('.'))


def constraint_filter(constraint):
    """Return a predicate on version tuples for one pin constraint."""
    c = constraint.strip()
    m = re.match(r'^=\s*([\d.]+)$', c)
    if m:
        want = version_tuple(m.group(1))
        return lambda v: v == want
    m = re.match(r'^~\s*([\d.]+)$', c)
    if m:
        low = version_tuple(m.group(1))
        return lambda v: v >= low and v[:2] == low[:2]
    m = re.match(r'^>=\s*([\d.]+)\s*<\s*([\d.]+)$', c)
    if m:
        low, high = version_tuple(m.group(1)), version_tuple(m.group(2))
        return lambda v: low <= v < high
    m = re.match(r'^\^\s*([\d.]+)$', c)
    if m:
        low = version_tuple(m.group(1))
        idx = 0
        while idx < len(low) and low[idx] == 0:
            idx += 1
        if idx >= len(low):
            return lambda v: v == low
        high = list(low[:idx + 1])
        high[idx] += 1
        high = tuple(high)
        return lambda v: low <= v < high
    raise ValueError('constraint %r' % constraint)


# --------------------------------------------------------------------------
# settlement
# --------------------------------------------------------------------------

GIB = 1073741824


class Settlement(object):

    def __init__(self, corpus):
        self.c = corpus
        self._parameters()
        self._records()
        self._revisions()
        self._clocks()
        self._rates()
        self._ownership()
        self._toolchains()
        self._attempts()
        self._actions()
        self._lookups()
        self._targets()
        self._artifacts()
        self._invoices()
        self._ledger()
        self._aggregates()

    # -- small helpers -----------------------------------------------------

    def recs(self, fname):
        """Distinct records of a primary table, in file order."""
        if fname not in self._distinct:
            flags = self.c.distinct_flags(fname)
            self._distinct[fname] = [r for r, ok in zip(self.c.rows[fname],
                                                        flags) if ok]
        return self._distinct[fname]

    def _parameters(self):
        self._distinct = {}
        p = self.c.params
        self.period_start = decode_timestamp(p['period_start'], 'iso_z')
        self.period_end = decode_timestamp(p['period_end'], 'iso_z')
        self.cutoff = decode_timestamp(p['knowledge_cutoff'], 'iso_z')
        self.period_last = self.period_end - 1
        self.storage_rate = int(p['storage_micro_per_gib_hour'])
        self.cache_credit = int(p['cache_credit_micro'])
        self.reserved_permille = int(p['reserved_permille'])

    def _records(self):
        for f in list(COLKIND):
            self.recs(f)

    # -- runner revisions --------------------------------------------------

    def _revisions(self):
        c = self.c
        placement = {}
        for r in self.recs('settlement_authority.md'):
            placement[(cid(r['runner']), r['rev'])] = r['region']
        self.revisions = {}
        for r in self.recs('fleet_policy.ini'):
            self.revisions.setdefault(cid(r['runner']), []).append(
                (r['effective_from'], r['rev'], cid(r['sku'])))
        for v in self.revisions.values():
            v.sort()
        self.placement = placement
        self.sku_class = {}
        for r in self.recs('instance_classes.csv'):
            self.sku_class.setdefault(cid(r['sku']),
                                      (r['instance_class'], r['arch'],
                                       r['spot'] == 'true'))
        self.sku_granularity = {}
        for r in self.recs('rate_methodology.pdf'):
            self.sku_granularity.setdefault(cid(r['sku']), r['granularity_s'])
        self.reservations = set()
        for r in self.recs('close_parameters.toml'):
            if r['day'] is not None:
                self.reservations.add((cid(r['runner']),
                                       r['day'] // 86400))

    def revision_at(self, runner, t):
        """(rev, region, sku, instance_class, spot) in force at t."""
        revs = self.revisions.get(cid(runner))
        if not revs or t is None:
            return (None, None, None, None, False)
        chosen = None
        for eff, rev, sku in revs:
            if eff is not None and eff <= t:
                chosen = (eff, rev, sku)
            else:
                break
        if chosen is None:
            return (None, None, None, None, False)
        _, rev, sku = chosen
        region = self.placement.get((cid(runner), rev))
        klass, _arch, spot = self.sku_class.get(sku, (None, None, False))
        return (rev, region, sku, klass, spot)

    # -- clock correction --------------------------------------------------

    def _clocks(self):
        self.windows = {}
        for r in self.recs('clock_sync.txt'):
            if r['window_from'] is None or r['window_to'] is None:
                continue
            self.windows.setdefault(cid(r['runner']), []).append(
                (r['window_from'], r['window_to'], r['skew_ms']))
        for v in self.windows.values():
            v.sort()

    def corrected_start(self, runner, reported):
        if reported is None:
            return None
        for lo, hi, skew in self.windows.get(cid(runner), ()):
            if lo <= reported < hi:
                return reported - round_half_even(Fraction(skew or 0, 1000))
        return reported

    # -- rates -------------------------------------------------------------

    def _rates(self):
        best = {}
        for r in self.recs('rate_card.xlsx'):
            if r['recorded_at'] is None or r['recorded_at'] > self.cutoff:
                continue
            key = (r['instance_class'], r['region'])
            prev = best.setdefault(key, {}).get(r['effective_from'])
            if prev is None or r['recorded_at'] >= prev[0]:
                best[key][r['effective_from']] = (r['recorded_at'],
                                                  r['micro_per_min'])
        self.rate_rows = {}
        for key, byeff in best.items():
            self.rate_rows[key] = sorted((eff, v[1]) for eff, v in
                                         byeff.items())
        self.spot_credit = self.c.spot_credit

    def rate_at(self, klass, region, t):
        rows = self.rate_rows.get((klass, region))
        if not rows or t is None:
            return None
        out = None
        for eff, rate in rows:
            if eff is not None and eff <= t:
                out = rate
            else:
                break
        return out

    # -- ownership, teams and cost centres ---------------------------------

    def _ownership(self):
        c = self.c
        rows = sorted(((r['seq'], i, r['pattern'], r['handle'])
                       for i, r in enumerate(self.recs('owners_registry.txt'))
                       if r['seq'] is not None and r['pattern']),
                      reverse=True)
        globals_ = []
        buckets = {}
        for seq, i, pattern, handle in rows:
            negated = pattern.startswith('!')
            body = pattern[1:] if negated else pattern
            entry = (pattern_regex(body), negated, handle)
            seg = body[2:].split('/')[0] if body.startswith('//') else ''
            if '*' in seg or not body.startswith('//'):
                globals_.append((seq, i, entry))
            else:
                buckets.setdefault(seg, []).append((seq, i, entry))
        self._owner_globals = globals_
        self._owner_buckets = {}
        for seg, lst in buckets.items():
            self._owner_buckets[seg] = sorted(lst + globals_, reverse=True)
        self._owner_cache = {}

        # handle_rename rows carry the earlier name in `target` and the new
        # name in `handle`; only renames inside the cutoff are reported, but
        # the earlier name is always the one the roster records.
        self.rename_map = {}
        self.rename_inverse = {}
        for r in self.recs('ownership_patterns_approved.tsv'):
            if r['kind'] != 'handle_rename' or not r['handle'] \
                    or not r['target']:
                continue
            self.rename_inverse[r['handle']] = r['target']
            if r['effective'] is not None and r['effective'] <= self.cutoff:
                self.rename_map[r['target']] = r['handle']

        self.roster = {}
        for r in self.recs('team_roster.xlsx'):
            self.roster.setdefault(r['handle'], r['team'])
        self.transfers = {}
        for r in c.transfers:
            self.transfers.setdefault(r['handle'], []).append(
                (decode_timestamp(r['effective_from'], 'iso_z'), r['team']))
        for v in self.transfers.values():
            v.sort()
        self.cost_rows = {}
        for r in self.recs('cost_centers.csv'):
            self.cost_rows.setdefault(r['handle'], []).append(
                (r['effective_from'], cid(r['cost_center'])))
        for v in self.cost_rows.values():
            v.sort(key=lambda x: (x[0] is None, x[0]))
        self.merges = {}
        for r in c.cc_merges:
            self.merges[cid(r['cost_center'])] = (
                decode_timestamp(r['effective_at'], 'iso_z'),
                cid(r['successor']))

    def registry_owner(self, target):
        """The handle recorded in the ownership registry, or None."""
        if target in self._owner_cache:
            return self._owner_cache[target]
        seg = target[2:].split('/')[0] if target.startswith('//') else ''
        cands = self._owner_buckets.get(seg)
        if cands is None:
            cands = sorted(self._owner_globals, reverse=True)
        out = None
        for _seq, _i, (rx, negated, handle) in cands:
            if rx.match(target):
                out = None if negated else handle
                break
        self._owner_cache[target] = out
        return out

    def recorded_handle(self, handle):
        """The earlier name, which the roster and cost centres still use."""
        seen = set()
        while handle in self.rename_inverse and handle not in seen:
            seen.add(handle)
            handle = self.rename_inverse[handle]
        return handle

    def reported_handle(self, handle):
        handle = self.recorded_handle(handle)
        seen = set()
        while handle in self.rename_map and handle not in seen:
            seen.add(handle)
            handle = self.rename_map[handle]
        return handle

    def team_of(self, handle, t):
        if handle is None:
            return None
        team = self.roster.get(handle)
        for eff, newteam in self.transfers.get(handle, ()):
            if eff is not None and eff <= t:
                team = newteam
        return team

    def cost_center_of(self, handle, t):
        if handle is None:
            return None
        cc = None
        for eff, value in self.cost_rows.get(handle, ()):
            if eff is not None and eff <= t:
                cc = value
        if cc is None:
            return None
        seen = set()
        while cc in self.merges and cc not in seen:
            seen.add(cc)
            eff, succ = self.merges[cc]
            if eff is None or eff > t:
                break
            cc = succ
        return cc

    def charge_handles(self, target, submitter):
        """(reported handle, recorded handle) charged for a target."""
        handle = self.registry_owner(target)
        if handle is None:
            handle = submitter
        if handle is None:
            return None, None
        return self.reported_handle(handle), self.recorded_handle(handle)

    # -- toolchain resolution ---------------------------------------------

    def _toolchains(self):
        c = self.c
        self.releases = {}
        for r in c.toolchain_releases:
            yanked = None if r['yanked_at'] == 'never' else \
                decode_timestamp(r['yanked_at'], 'iso_z')
            self.releases.setdefault(r['toolchain'], []).append(
                (version_tuple(r['version']), r['version'],
                 decode_timestamp(r['released_at'], 'iso_z'), yanked))
        for v in self.releases.values():
            v.sort()
        self.constraints = {}
        for r in self.recs('toolchain_pins.yaml'):
            self.constraints.setdefault(r['target'], r['constraint'])
        self._cand_cache = {}

    def candidates(self, target):
        if target in self._cand_cache:
            return self._cand_cache[target]
        toolchain = self.c.target_toolchain.get(target)
        constraint = self.constraints.get(target)
        out = []
        if toolchain is not None and constraint is not None:
            keep = constraint_filter(constraint)
            out = [row for row in self.releases.get(toolchain, ())
                   if keep(row[0])]
        self._cand_cache[target] = out
        return out

    def resolve_version(self, target, t):
        best = None
        for vt, vs, released, yanked in self.candidates(target):
            if released is None or released > t:
                continue
            if yanked is not None and yanked <= t:
                continue
            if best is None or vt > best[0]:
                best = (vt, vs)
        return None if best is None else best[1]

    # -- attempts ----------------------------------------------------------

    def _status_errata(self):
        """Attempt -> new status, for errata whose latest decision approved."""
        decisions = {}
        for i, r in enumerate(self.recs('approval_thread.mbox')):
            at = r['decided_at']
            if at is None or at > self.cutoff:
                continue
            key = (at, i)
            er = cid(r['erratum'])
            if er not in decisions or key > decisions[er][0]:
                decisions[er] = (key, r['decision'])
        out = {}
        for i, r in enumerate(self.recs('errata_register.docx')):
            if r['field'] != 'status':
                continue
            decided = decisions.get(cid(r['id']))
            if decided is None or decided[1] != 'APPROVED':
                continue
            key = (r['filed'] if r['filed'] is not None else 0, i)
            aid = cid(r['attempt'])
            if aid not in out or key > out[aid][0]:
                out[aid] = (key, r['new'])
        return dict((k, v[1]) for k, v in out.items())

    def _drain_windows(self):
        latest = {}
        for i, r in enumerate(self.recs('change_freeze.ics')):
            key = (r['sequence'] if r['sequence'] is not None else -1, i)
            uid = r['uid']
            if uid not in latest or key > latest[uid][0]:
                latest[uid] = (key, r)
        out = {}
        for key, r in latest.values():
            if (r['status'] or '').upper() == 'CANCELLED':
                continue
            if r['dtstart'] is None or r['dtend'] is None:
                continue
            out.setdefault(cid(r['runner']), []).append((r['dtstart'],
                                                         r['dtend']))
        for v in out.values():
            v.sort()
        return out

    def _attempts(self):
        c = self.c
        self.status_errata = self._status_errata()
        self.drains = self._drain_windows()
        self.cancel_origin = {}
        for r in self.recs('attempt_events_v3.jsonl'):
            self.cancel_origin.setdefault(cid(r['attempt_id']),
                                          r['cancel_origin'])
        self.revoked = set(cid(r['attempt'])
                           for r in self.recs('usage_export_legacy.log')
                           if r['kind'] == 'REVOKE')
        self.junit = {}
        for r in self.recs('junit_results.xml'):
            self.junit.setdefault(cid(r['attempt']), []).append(r['testcase'])
        self.flaky = {}
        for r in self.recs('flaky_windows.tsv'):
            self.flaky.setdefault((r['target'], r['testcase']), []).append(
                (r['from'], r['until']))
        self.budgets = {}
        for r in self.recs('retry_policy.yaml'):
            self.budgets.setdefault(cid(r['job']), r['budget'])
        self.default_budget = int(c.policy_defaults['budget'])
        self.job_class = {}
        for i, r in enumerate(self.recs('amendment_minutes.docx')):
            if r['ratified_on'] is None or r['ratified_on'] > self.cutoff:
                continue
            key = (r['ratified_on'], i)
            job = cid(r['job'])
            if job not in self.job_class or key > self.job_class[job][0]:
                self.job_class[job] = (key, r['class'])
        self.scope = {}
        for r in self.recs('scope_rules.md'):
            self.scope.setdefault(r['target'], r['scope'])

        self.attempts = {}
        for fname in ATTEMPT_FILES:
            fleet = FLEET_OF_FILE[fname]
            acol, jcol, ncol, rcol, scol, stcol = ATTEMPT_COLS[fname]
            for r in self.recs(fname):
                a = self._settle_attempt(fname, fleet, r, acol, jcol, ncol,
                                         rcol, scol, stcol)
                self.attempts.setdefault(a['attempt_id'], a)

    def _settle_attempt(self, fname, fleet, r, acol, jcol, ncol, rcol, scol,
                        stcol):
        c = self.c
        aid = cid(r[acol])
        job = cid(r[jcol])
        runner = cid(r[rcol])
        reported = r[scol]
        t = self.corrected_start(runner, reported)
        if fname in ('fleet_north.log', 'fleet_south.log'):
            if r['mono_end'] is None or r['mono_start'] is None:
                duration = None
            else:
                duration = r['mono_end'] - r['mono_start']
        elif fname == 'attempt_events.jsonl':
            duration = r['duration_ms']
        else:
            duration = r['elapsed']
        status = self.status_errata.get(aid, r[stcol])
        target = c.job_target.get(job)
        submitter = c.job_submitter.get(job)
        rev, region, sku, klass, spot = self.revision_at(runner, t)
        exclusion = self._exclusion(aid, t, runner, status, duration, target,
                                    r[ncol], job, fleet)
        gran = self.sku_granularity.get(sku) or 1
        if exclusion is None and duration is not None and duration > 0:
            billable = -(-duration // (gran * 1000)) * gran
        else:
            billable = 0
        rate = self.rate_at(klass, region, t)
        billing_class = self.job_class.get(job, (None, 'standard'))[1]
        multiplier = c.billing_classes.get(billing_class, 1000)
        reserved = t is not None and (runner, t // 86400) in self.reservations
        cost = 0
        if billable and rate is not None:
            amount = Fraction(billable * rate * multiplier, 60 * 1000)
            if spot:
                amount *= Fraction(1000 - self.spot_credit.get(klass, 0), 1000)
            if reserved:
                amount *= Fraction(self.reserved_permille, 1000)
            cost = round_half_even(amount)
        reported_handle, recorded = self.charge_handles(target, submitter)
        team = self.team_of(recorded, t)
        cost_center = self.cost_center_of(recorded, t)
        return {
            'attempt_id': aid,
            'job_id': job,
            'attempt_no': r[ncol],
            'fleet': fleet,
            'runner': runner,
            'runner_rev': rev,
            'region': region,
            'sku': sku,
            'instance_class': klass,
            'target': target,
            'started_at': iso_from_epoch(t),
            'duration_ms': duration,
            'status': status,
            'exclusion': exclusion,
            'billable_seconds': billable,
            'rate_micro_per_min': rate,
            'billing_class': billing_class,
            'reserved': reserved,
            'cost_micro': cost,
            'owner_handle': reported_handle,
            'team': team,
            'cost_center': cost_center,
            '_start': t,
        }

    def _exclusion(self, aid, t, runner, status, duration, target, attempt_no,
                   job, fleet):
        if t is None or not (self.period_start <= t < self.period_end):
            return 'out_of_period'
        if aid in self.revoked:
            return 'revoked'
        for lo, hi in self.drains.get(runner, ()):
            if lo <= t < hi:
                return 'provider_drain'
        if status == 'cancelled' and \
                self.cancel_origin.get(aid) == 'platform':
            return 'platform_cancel'
        if status == 'failed':
            cases = self.junit.get(aid)
            if cases and all(
                    any(lo is not None and hi is not None and lo <= t <= hi
                        for lo, hi in self.flaky.get((target, case), ()))
                    for case in cases):
                return 'quarantined_flake'
        if status == 'preempted' and duration is not None:
            grace = self.c.fleet_grace.get(fleet)
            if grace is not None and duration < grace * 1000:
                return 'preempt_grace'
        budget = self.budgets.get(job)
        if budget is None:
            budget = self.default_budget
        if attempt_no is not None and attempt_no > budget:
            return 'over_budget'
        if self.scope.get(target) == 'exempt':
            return 'exempt_scope'
        return None

    # -- cached actions ----------------------------------------------------

    def _actions(self):
        c = self.c
        self.home_shard = {}
        for r in self.recs('shard_index.tsv'):
            self.home_shard.setdefault(cid(r['prefix']), r['shard'])
        manifests = {}
        for r in self.recs('input_manifests.tsv'):
            manifests.setdefault(cid(r['action']), []).append(r)
        reads = {}
        for r in self.recs('env_allowlist.json'):
            reads.setdefault(cid(r['action']), set()).update(r['reads'] or ())
        self.actions = {}
        for r in self.recs('action_keys.lock'):
            key = cid(r['action'])
            rows = manifests.get(key, [])
            undeclared = sorted(set(m['path'] for m in rows
                                    if m['declared'] != 'true'))
            disallowed = sorted(reads.get(key, set()) - c.allowed_env)
            version = None
            if r['digest'] is not None:
                named = c.digest_version.get(r['digest'])
                version = named[1] if named else None
            self.actions.setdefault(key, {
                'action_key': key,
                'target': r['target'],
                'home_shard': self.home_shard.get(key[:6]),
                'hermetic': not undeclared and not disallowed,
                'undeclared_inputs': undeclared,
                'disallowed_env': disallowed,
                'input_bytes': sum(m['size'] or 0 for m in rows),
                'toolchain_version': version,
            })

    # -- cache lookups -----------------------------------------------------

    def _lookups(self):
        c = self.c
        writes = {}
        for r in self.recs('lookups_archive.jsonl.gz'):
            if r['kind'] == 'write':
                writes.setdefault(cid(r['action']), []).append(r['at'])
        for v in writes.values():
            v.sort()
        evictions = {}
        for r in self.recs('evictions.log'):
            evictions.setdefault((cid(r['action']), r['shard']), []).append(
                (r['ts'], cid(r['eviction'])))
        for v in evictions.values():
            v.sort()
        self.lookups = {}
        for fname in SHARD_FILES:
            shard = int(re.search(r'shard(\d+)', fname).group(1))
            for r in self.recs(fname):
                self.lookups.setdefault(
                    cid(r['lookup']),
                    self._settle_lookup(r, shard, writes, evictions))

    def _settle_lookup(self, r, shard, writes, evictions):
        key = cid(r['action'])
        action = self.actions.get(key)
        home = self.home_shard.get(key[:6])
        at = r['at']
        outcome = None
        eviction = None
        if home != shard:
            outcome = 'replay'
        elif (r['result'] or '').upper() == 'MISS':
            outcome = 'miss'
        elif action is not None and not action['hermetic']:
            outcome = 'nonhermetic_hit'
        else:
            last_write = None
            for w in writes.get(key, ()):
                if w is not None and at is not None and w <= at:
                    last_write = w
                else:
                    break
            if last_write is not None:
                for ts, evid in evictions.get((key, home), ()):
                    if ts is not None and last_write < ts <= at:
                        eviction = evid
                        break
            if eviction is not None:
                outcome = 'evicted_hit'
            else:
                target = action['target'] if action else None
                if last_write is not None and target is not None and \
                        self.resolve_version(target, last_write) != \
                        self.resolve_version(target, at):
                    outcome = 'stale_hit'
                else:
                    outcome = 'hit'
        return {
            'lookup_id': cid(r['lookup']),
            'attempt_id': cid(r['attempt']),
            'action_key': key,
            'shard': shard,
            'at': iso_from_epoch(at),
            'bytes': r['bytes'],
            'outcome': outcome,
            'eviction_id': eviction,
        }

    # -- build targets -----------------------------------------------------

    def _targets(self):
        c = self.c
        kinds = {}
        order = []
        for r in self.recs('targets.csv'):
            if r['target'] not in kinds:
                kinds[r['target']] = r['kind']
                order.append(r['target'])
        changed = set()
        versions = {}
        for target in order:
            vo = self.resolve_version(target, self.period_start)
            vc = self.resolve_version(target, self.period_last)
            versions[target] = (vo, vc)
            if vo != vc:
                changed.add(target)
        children = {}
        for r in self.recs('edges.csv'):
            if r['kind'] in ('src', 'toolchain'):
                children.setdefault(r['parent'], []).append(r['child'])
        invalid = set(changed)
        stack = list(changed)
        while stack:
            node = stack.pop()
            for child in children.get(node, ()):
                if child not in invalid:
                    invalid.add(child)
                    stack.append(child)
        self.targets = {}
        for target in order:
            registered = self.registry_owner(target)
            owner = self.reported_handle(registered) if registered else None
            recorded = self.recorded_handle(registered) if registered else None
            vo, vc = versions[target]
            self.targets[target] = {
                'target': target,
                'kind': kinds[target],
                'language': c.target_language.get(target),
                'toolchain': c.target_toolchain.get(target),
                'constraint': self.constraints.get(target),
                'version_at_open': vo,
                'version_at_close': vc,
                'invalidated': target in invalid,
                'scope': self.scope.get(target),
                'owner_handle': owner,
                'team': self.team_of(recorded, self.period_last),
            }

    # -- stored artifacts --------------------------------------------------

    def _artifacts(self):
        events = {}
        for i, r in enumerate(self.recs('gc_events.csv')):
            events.setdefault(cid(r['artifact']), []).append(
                (r['at'], i, r['action']))
        for v in events.values():
            v.sort(key=lambda x: (x[0] is None, x[0], x[1]))
        self.artifacts = {}
        for r in self.recs('artifact_registry.db'):
            key = cid(r['artifact'])
            if key in self.artifacts:
                continue
            seconds = self._retained(r['created'], events.get(key, ()))
            size = r['bytes'] or 0
            cost = round_half_even(
                Fraction(size * seconds * self.storage_rate, GIB * 3600))
            target = r['target']
            registered = self.registry_owner(target)
            recorded = self.recorded_handle(registered) if registered else None
            self.artifacts[key] = {
                'artifact_id': key,
                'target': target,
                'bytes': r['bytes'],
                'retained_seconds': seconds,
                'storage_cost_micro': cost,
                'team': self.team_of(recorded, self.period_last),
                'cost_center': self.cost_center_of(recorded,
                                                   self.period_last),
            }

    def _retained(self, created, events):
        """Seconds of retention inside the period."""
        if created is None:
            return 0
        total = 0
        open_at = created
        for at, _i, action in events:
            if at is None:
                continue
            if action == 'delete' and open_at is not None:
                total += self._overlap(open_at, at)
                open_at = None
            elif action == 'restore' and open_at is None:
                open_at = at
        if open_at is not None:
            total += self._overlap(open_at, self.period_end)
        return total

    def _overlap(self, lo, hi):
        lo = max(lo, self.period_start)
        hi = min(hi, self.period_end)
        return max(0, hi - lo)

    # -- vendor invoices ---------------------------------------------------

    def _invoices(self):
        week = 7 * 86400
        starts = []
        t = self.period_start
        while t < self.period_end:
            starts.append(t)
            t += week
        self.week_starts = starts
        credits = {}
        for r in self.recs('vendor_statement.xml'):
            credits.setdefault(cid(r['line']), r['credit'])
        closures = set(cid(r['line_id'])
                       for r in self.recs('invoice_restatement.csv')
                       if r['type'] == 'dispute_closure')
        computed = {}
        for a in self.attempts.values():
            if a['exclusion'] is not None:
                continue
            idx = self._week_index(a['_start'])
            computed[(a['runner'], idx)] = \
                computed.get((a['runner'], idx), 0) + a['cost_micro']
        self.invoices = {}
        for r in self.recs('invoice_lines.xlsx'):
            key = cid(r['line_id'])
            if key in self.invoices:
                continue
            idx = self._week_index(r['week_start'])
            billed = r['billed']
            credit = credits.get(key)
            value = computed.get((cid(r['runner']), idx), 0)
            if key in closures:
                status = 'closed'
            elif billed == value:
                status = 'match'
            elif credit is not None and billed - credit == value:
                status = 'credited'
            else:
                status = 'mismatch'
            self.invoices[key] = {
                'line_id': key,
                'runner': cid(r['runner']),
                'week': idx,
                'billed_micro': billed,
                'credit_micro': credit,
                'computed_micro': value,
                'status': status,
            }

    def _week_index(self, t):
        if t is None:
            return None
        return (t - self.period_start) // (7 * 86400)

    # -- cost centre ledger ------------------------------------------------

    def _ledger(self):
        opening = {}
        for r in self.recs('opening_balances.json'):
            key = cid(r['cost_center'])
            opening[key] = opening.get(key, 0) + (r['amount'] or 0)
        postings = self.recs('settlement_ledger.db')
        reversed_by = set()
        for r in postings:
            if r['reverses']:
                reversed_by.add(cid(r['reverses']))
        counted = {}
        for r in postings:
            at = r['posted_at']
            if at is None or not (self.period_start <= at < self.period_end):
                continue
            key = cid(r['posting'])
            if key in self.c.late_voids or r['reverses'] or \
                    key in reversed_by:
                continue
            cc = self._route(cid(r['cost_center']), at)
            counted[cc] = counted.get(cc, 0) + (r['amount'] or 0)
        charges = {}
        for a in self.attempts.values():
            if a['exclusion'] is None and a['cost_center'] is not None:
                charges[a['cost_center']] = charges.get(a['cost_center'], 0) \
                    + a['cost_micro']
        for art in self.artifacts.values():
            if art['cost_center'] is not None:
                charges[art['cost_center']] = \
                    charges.get(art['cost_center'], 0) \
                    + art['storage_cost_micro']
        self.ledger = {}
        for cc in sorted(opening):
            post = counted.get(cc, 0)
            charge = charges.get(cc, 0)
            self.ledger[cc] = {
                'opening_micro': opening[cc],
                'postings_micro': post,
                'charges_micro': charge,
                'closing_micro': opening[cc] + post + charge,
            }

    def _route(self, cc, t):
        seen = set()
        while cc in self.merges and cc not in seen:
            seen.add(cc)
            eff, succ = self.merges[cc]
            if eff is None or eff > t:
                break
            cc = succ
        return cc

    # -- aggregates --------------------------------------------------------

    OUTCOMES = ('hit', 'miss', 'stale_hit', 'evicted_hit', 'nonhermetic_hit',
                'replay')

    def _aggregates(self):
        self._rate_resolution()
        self._controls()
        self._chargeback()
        self._cache_effectiveness()
        self._source_audit()
        self._close_summary()

    def _rate_resolution(self):
        out = {}
        pairs = []
        for r in self.recs('rate_card.xlsx'):
            key = (r['instance_class'], r['region'])
            if key not in out:
                out[key] = None
                pairs.append(key)
        out = {}
        for key in pairs:
            klass, region = key
            rows = self.rate_rows.get(key, [])
            windows = []
            opening = None
            for eff, rate in rows:
                if eff is None:
                    continue
                if eff <= self.period_start:
                    opening = rate
                elif eff < self.period_end:
                    windows.append([iso_from_epoch(eff), rate])
            entries = []
            if opening is not None:
                entries.append([iso_from_epoch(self.period_start), opening])
            entries.extend(windows)
            out['%s|%s' % (klass, region)] = entries
        self.rate_resolution = out

    def _block_figures(self, fname):
        if fname in self._blocks:
            return self._blocks[fname]
        column = self.c.catalog[fname]['control column']
        flags = self.c.distinct_flags(fname)
        rows = self.c.rows[fname]
        out = {}
        for i, (row, fresh) in enumerate(zip(rows, flags)):
            block = i // 50 + 1
            count, total = out.get(block, (0, 0))
            if fresh:
                value = row.get(column)
                count += 1
                total += value if value is not None else 0
            out[block] = (count, total)
        self._blocks[fname] = out
        return out

    def _controls(self):
        self._blocks = {}
        published = []
        for r in self.recs('audit_annex.pdf'):
            published.append(r)
        for r in self.recs('control_totals_draft.html'):
            if r['file'] == 'audit_annex.pdf':
                published.append(r)
        out = {}
        for r in published:
            fname = r['file']
            if fname not in COLKIND:
                continue
            count, total = self._block_figures(fname).get(r['block'], (0, 0))
            out[r['control_id']] = {
                'file': fname,
                'block': r['block'],
                'expected_records': r['records'],
                'expected_sum': r['control_sum'],
                'records': count,
                'sum': total,
                'match': count == r['records'] and total == r['control_sum'],
            }
        self.controls = out

    def _chargeback(self):
        teams = {}

        def bucket(team):
            return teams.setdefault(team, {'attempts_billed': 0,
                                           'compute_micro': 0,
                                           'storage_micro': 0,
                                           'cache_credit_micro': 0,
                                           'net_micro': 0})

        for a in self.attempts.values():
            if a['team'] is None:
                continue
            b = bucket(a['team'])
            if a['exclusion'] is None:
                b['attempts_billed'] += 1
                b['compute_micro'] += a['cost_micro']
        for art in self.artifacts.values():
            if art['team'] is None:
                continue
            bucket(art['team'])['storage_micro'] += art['storage_cost_micro']
        for lk in self.lookups.values():
            if lk['outcome'] != 'hit':
                continue
            attempt = self.attempts.get(lk['attempt_id'])
            if attempt is None or attempt['team'] is None:
                continue
            bucket(attempt['team'])['cache_credit_micro'] += self.cache_credit
        for b in teams.values():
            b['net_micro'] = (b['compute_micro'] + b['storage_micro']
                              - b['cache_credit_micro'])
        self.chargeback = teams

    def _cache_effectiveness(self):
        out = {}
        for lk in self.lookups.values():
            attempt = self.attempts.get(lk['attempt_id'])
            team = attempt['team'] if attempt else None
            if team is None:
                continue
            row = out.setdefault(team, dict((k, 0) for k in self.OUTCOMES))
            row[lk['outcome']] += 1
        for row in out.values():
            considered = sum(row[k] for k in self.OUTCOMES if k != 'replay')
            row['valid_hit_permille'] = (
                (1000 * row['hit']) // considered if considered else 0)
        self.cache_effectiveness = out

    def _source_audit(self):
        self.source_audit = dict(
            (fname, {'records': len(self.recs(fname))})
            for fname in COLKIND)

    def _close_summary(self):
        billed = [a for a in self.attempts.values() if a['exclusion'] is None]
        compute = sum(a['cost_micro'] for a in billed)
        storage = sum(a['storage_cost_micro'] for a in self.artifacts.values())
        credit = sum(self.cache_credit for lk in self.lookups.values()
                     if lk['outcome'] == 'hit')
        self.close_summary = {
            'attempts_listed': len(self.attempts),
            'attempts_billed': len(billed),
            'compute_micro': compute,
            'storage_micro': storage,
            'cache_credit_micro': credit,
            'net_micro': compute + storage - credit,
            'invoice_mismatches': sum(1 for r in self.invoices.values()
                                      if r['status'] == 'mismatch'),
            'controls_mismatched': sum(1 for r in self.controls.values()
                                       if not r['match']),
            'closing_micro': sum(v['closing_micro']
                                 for v in self.ledger.values()),
        }


# --------------------------------------------------------------------------
# writing
# --------------------------------------------------------------------------

ATTEMPT_KEYS = ['attempt_id', 'job_id', 'attempt_no', 'fleet', 'runner',
                'runner_rev', 'region', 'sku', 'instance_class', 'target',
                'started_at', 'duration_ms', 'status', 'exclusion',
                'billable_seconds', 'rate_micro_per_min', 'billing_class',
                'reserved', 'cost_micro', 'owner_handle', 'team',
                'cost_center']
LOOKUP_KEYS = ['lookup_id', 'attempt_id', 'action_key', 'shard', 'at',
               'bytes', 'outcome', 'eviction_id']
TARGET_KEYS = ['target', 'kind', 'language', 'toolchain', 'constraint',
               'version_at_open', 'version_at_close', 'invalidated', 'scope',
               'owner_handle', 'team']
ACTION_KEYS = ['action_key', 'target', 'home_shard', 'hermetic',
               'undeclared_inputs', 'input_bytes', 'disallowed_env',
               'toolchain_version']
ARTIFACT_KEYS = ['artifact_id', 'target', 'bytes', 'retained_seconds',
                 'storage_cost_micro', 'team', 'cost_center']
INVOICE_KEYS = ['line_id', 'runner', 'week', 'billed_micro', 'credit_micro',
                'computed_micro', 'status']


def _dump(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':'),
                      sort_keys=True)


def write_jsonl(path, rows, keys, row_key):
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        for row in sorted(rows, key=lambda r: str(r[row_key])):
            fh.write(_dump(dict((k, row[k]) for k in keys)) + '\n')


def write_json(path, obj):
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(_dump(obj) + '\n')


def write_artifacts(s, out_dir):
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    j = lambda name: os.path.join(out_dir, name)
    write_jsonl(j('attempts.jsonl'), s.attempts.values(), ATTEMPT_KEYS,
                'attempt_id')
    write_jsonl(j('lookups.jsonl'), s.lookups.values(), LOOKUP_KEYS,
                'lookup_id')
    write_jsonl(j('targets.jsonl'), s.targets.values(), TARGET_KEYS, 'target')
    write_jsonl(j('actions.jsonl'), s.actions.values(), ACTION_KEYS,
                'action_key')
    write_jsonl(j('artifacts.jsonl'), s.artifacts.values(), ARTIFACT_KEYS,
                'artifact_id')
    write_jsonl(j('invoice_reconciliation.jsonl'), s.invoices.values(),
                INVOICE_KEYS, 'line_id')
    write_json(j('team_chargeback.json'), s.chargeback)
    write_json(j('cost_center_ledger.json'), s.ledger)
    write_json(j('rate_resolution.json'), s.rate_resolution)
    write_json(j('cache_effectiveness.json'), s.cache_effectiveness)
    write_json(j('control_reconciliation.json'), s.controls)
    write_json(j('source_audit.json'), s.source_audit)
    write_json(j('close_summary.json'), s.close_summary)


def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: settle.py DATA_DIR OUT_DIR\n')
        return 2
    corpus = Corpus(argv[1])
    settlement = Settlement(corpus)
    write_artifacts(settlement, argv[2])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))

