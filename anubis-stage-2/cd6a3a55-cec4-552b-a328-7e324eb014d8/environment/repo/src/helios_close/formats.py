"""helios_close.formats: part of the Q3 close program (see README.md)."""
from __future__ import annotations

from .domain import *  # noqa: F401,F403
import configparser
from decimal import Decimal, ROUND_HALF_EVEN
import csv
import html.parser
import io
import json
import re
import sqlite3
import struct
import tomllib
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

class InputError(Exception):
    pass
ENVF = ['rid', 'rev', 'st', 'rec_at']
SCHEMA = {'registry_pypi.jsonl': [('releases', ['name:pkg', 'version:ver', 'published:ts', 'yanked:bool'])], 'registry_npm.csv': [('releases', ['name:pkg', 'version:ver', 'published:ts', 'yanked:bool'])], 'registry_maven.xml': [('releases', ['name:pkg', 'version:ver', 'published:ts', 'yanked:bool'])], 'registry_cargo.tsv': [('releases', ['name:pkg', 'version:ver', 'published:ts', 'yanked:bool'])], 'registry_mirror.parquet': [('mirror', ['eco:enum:eco', 'name:pkg', 'version:ver', 'published:ts', 'yanked:bool', 'quarantined:bool', 'license:spdx'])], 'name_aliases.tsv': [('aliases', ['eco:enum:eco', 'alias:pkg', 'target:pkg', 'kind:enum:alias_kind', 'effective:ts'])], 'name_aliases_legacy.tsv': [('aliases', ['eco:enum:eco', 'alias:pkg', 'target:pkg', 'kind:enum:alias_kind', 'effective:ts', 'note:text'])], 'yank_notices.mbox': [('notices', ['action:enum:notice', 'eco:enum:eco', 'name:pkg', 'version:ver', 'ref:id'])], 'package_owners.json': [('owners', ['eco:enum:eco', 'name:pkg', 'team:id', 'role:enum:role', 'effective:ts'])], 'lock_overrides.toml': [('overrides', ['service:svcid', 'eco:enum:eco', 'name:pkg', 'version:ver', 'valid_from:date', 'valid_to:date'])], 'service_catalog.xlsx': [('services', ['service:svcid', 'name:text', 'tier:int', 'region:enum:region', 'manifest:enum:home']), ('ownership', ['service:svcid', 'team:id', 'effective:ts']), ('lifecycle', ['service:svcid', 'event:enum:life', 'at:ts'])], 'service_catalog_final.xlsx': [('services', ['service:svcid', 'name:text', 'tier:int', 'region:enum:region', 'manifest:enum:home']), ('ownership', ['service:svcid', 'team:id', 'effective:ts']), ('legacy_lifecycle', ['service:svcid', 'event:enum:life', 'at:ts'])], 'clock_offsets.txt': [('offsets', ['host:id', 'day:date', 'offset:int'])], 'change_freeze.ics': [('windows', ['service:svcid', 'start:date', 'end:date'])], 'advisories_ghsa.json': [('ghsa', ['ghsa:vid', 'eco:enum:eco', 'name:pkg', 'vector:vec', 'reviewed:bool', 'published:ts'])], 'advisories_feed_cache.json': [('cache', ['ghsa:vid', 'eco:enum:eco', 'name:pkg', 'vector:vec', 'score:dec', 'fetched:ts'])], 'advisories_nvd.xml': [('nvd', ['cve:vid', 'vector:vec', 'source:enum:nvdsrc', 'modified:ts'])], 'advisory_aliases.csv': [('aliases', ['a:vid', 'b:vid'])], 'advisory_rescores.parquet': [('rescores', ['vuln:vid', 'vector:vec', 'approved:bool', 'scored:ts'])], 'precedence.yaml': [('authority', ['vuln:vid', 'field:enum:pfield', 'order:text'])], 'vex_statements.xml': [('vex', ['service:svcid', 'vuln:vid', 'status:enum:vex', 'justification:enum:just', 'issued:ts'])], 'waivers.db': [('waivers', ['service:svcid', 'vuln:vid', 'granted:ts', 'expires:ts', 'approver:text'])], 'license_scan.parquet': [('scans', ['eco:enum:eco', 'name:pkg', 'version:ver', 'expression:spdx', 'scanned:ts'])], 'license_overrides.csv': [('overrides', ['eco:enum:eco', 'name:pkg', 'range:cons', 'expression:spdx', 'status:enum:lstat', 'decided:ts'])], 'license_policy.md': [('exceptions', ['eco:enum:eco', 'name:pkg', 'range:cons', 'class:enum:cls', 'granted:date', 'revoked:date'])], 'engineer_roster.ini': [('alloc', ['engineer:id', 'team:id', 'fte:dec', 'oncall:dec', 'start:date', 'end:date']), ('teams', ['team:id', 'model:enum:model'])], 'engineer_rates.xlsx': [(f'rates_{m}', ['engineer:id', 'month:date', 'rate:money', 'currency:enum:cur']) for m in ('jul', 'aug', 'sep')], 'fx_fixings.tsv': [('fixings', ['currency:enum:cur', 'at:ts', 'rate:dec'])], 'remediation_timesheets.csv': [('timesheets', ['engineer:id', 'service:svcid', 'vuln:vid', 'hours:hours', 'worked:ts', 'note:text'])], 'ledger_journal.db': [('entries', ['team:id', 'kind:enum:jkind', 'amount:money', 'currency:enum:cur', 'booked:ts', 'reverses:id'])], 'close_contract.md': [('crosswalk', ['legacy:text', 'service:id', 'valid_from:date', 'valid_to:date'])], 'source_conventions.html': [('register', ['file:text', 'batch:text', 'field:text', 'conv:text', 'token:text'])], 'control_totals.html': [('controls', ['control:id', 'scope:text', 'measure:enum:measure', 'value:int', 'signed:ts'])], 'errata_register.docx': [('errata', ['file:text', 'target:id', 'action:enum:err', 'field:text', 'value:text', 'issued:ts'])], 'review_minutes.docx': [('minutes', ['subject:id', 'decision:enum:dec', 'decided:ts', 'chair:text'])], 'scoring_methodology.pdf': [('factors', ['eco:enum:eco', 'name:pkg', 'major:int', 'factor:dec', 'effective:date'])], 'sla_policy.pdf': [('sla_overrides', ['service:svcid', 'severity:enum:sev', 'days:int', 'effective:date'])], 'remediation_estimates.xlsx': [(f'est_{e}', ['name:pkg', 'major:int', 'hours:hours', 'effective:date']) for e in ECOS]}
_DECL = ['service:svcid', 'eco:enum:eco', 'name:pkg', 'constraint:cons', 'scope:enum:scope', 'locked:ts']
for _f in ('manifests_core.csv', 'manifests_edge.jsonl', 'manifests_data.yaml', 'manifests_legacy.txt', 'manifests_snapshot.csv'):
    SCHEMA[_f] = [('declarations', list(_DECL))]
for _f in ('deploy_events_east.log', 'deploy_events_west.log', 'deploy_events_central.log', 'deploy_events_legacy.log'):
    SCHEMA[_f] = [('deploys', ['host:id', 'service:svcid', 'outcome:enum:outcome', 'at:ts'])]
for _f in ('advisories_osv.jsonl', 'advisories_osv_replay.jsonl'):
    SCHEMA[_f] = [('osv', ['osv:vid', 'eco:enum:eco', 'name:pkg', 'events:events', 'published:ts', 'withdrawn:ts'])]
SCHEMA['scanner_findings.jsonl'] = [('findings', ['service:svcid', 'eco:enum:eco', 'name:pkg', 'version:ver', 'seen:ts', 'image:text'])]
FILE_LIST = sorted(SCHEMA)
ENV_KINDS = {'rid': 'id', 'rev': 'int', 'st': 'enum:st', 'rec_at': 'ts'}
VOC = {'st': {'word': ['active', 'void', 'draft'], 'letter': ['A', 'V', 'D'], 'code': ['1', '9', '0']}, 'scope': {'word': ['runtime', 'dev', 'test'], 'letter': ['R', 'D', 'T'], 'alt': ['prod', 'development', 'testing']}, 'eco': {'word': ['pypi', 'npm', 'maven', 'cargo'], 'upper': ['PYPI', 'NPM', 'MAVEN', 'CARGO'], 'alt': ['pip', 'node', 'mvn', 'crates']}, 'alias_kind': {'word': ['rename', 'spelling', 'typo', 'vendor'], 'letter': ['R', 'S', 'T', 'V']}, 'notice': {'word': ['yank', 'unyank', 'rename'], 'upper': ['YANK', 'UNYANK', 'RENAME']}, 'role': {'word': ['owner', 'maintainer', 'reviewer'], 'letter': ['O', 'M', 'R']}, 'home': {'word': ['core', 'edge', 'data', 'legacy', 'image'], 'upper': ['CORE', 'EDGE', 'DATA', 'LEGACY', 'IMAGE']}, 'region': {'word': REGIONS, 'alt': ['euw1', 'usc1', 'aps1', 'apn1', 'apse1', 'glb']}, 'life': {'word': ['archived', 'decommissioned', 'restored', 'paused', 'renamed'], 'letter': ['A', 'X', 'R', 'P', 'N']}, 'outcome': {'word': ['succeeded', 'failed', 'rolled_back'], 'letter': ['S', 'F', 'R'], 'alt': ['ok', 'error', 'rollback']}, 'nvdsrc': {'word': ['NVD', 'CNA']}, 'pfield': {'word': ['cvss_vector', 'published']}, 'vex': {'word': ['not_affected', 'affected', 'fixed', 'under_investigation'], 'alt': ['NA', 'A', 'F', 'UI']}, 'just': {'word': ['vulnerable_code_not_present', 'vulnerable_code_not_in_execute_path', 'inline_mitigations_already_exist', 'component_not_present', 'none']}, 'cls': {'word': ['permissive', 'weak', 'strong', 'network', 'unknown']}, 'model': {'word': ['capped', 'uncapped']}, 'cur': {'word': ['EUR', 'USD', 'GBP', 'INR', 'JPY']}, 'jkind': {'word': ['opening', 'adjust', 'reversal'], 'letter': ['O', 'A', 'R']}, 'measure': {'word': ['open_exposures', 'runtime_pins', 'closing_cents', 'capacity_hours', 'records', 'in_force', 'pool_hours', 'total_open', 'waived_total']}, 'err': {'word': ['void', 'correct'], 'upper': ['VOID', 'CORRECT']}, 'dec': {'word': ['approve', 'reject', 'defer'], 'letter': ['Y', 'N', 'D']}, 'sev': {'word': ['critical', 'high', 'medium', 'low']}, 'lstat': {'word': ['decided', 'proposed', 'withdrawn'], 'letter': ['D', 'P', 'W']}}
DEFAULT_CONV = {'ts': 'iso', 'date': 'iso', 'dec': 'plain', 'int': 'plain', 'hours': 'h', 'money': 'minor', 'bool': 'tf', 'id': 'canon', 'svcid': 'canon', 'pkg': 'canon', 'ver': 'semver', 'vid': 'canon', 'vec': 'canon', 'spdx': 'canon', 'events': 'semver'}
NO_LAYOUT_EXT = {'.xlsx', '.parquet', '.db', '.ini', '.ics', '.mbox', '.toml', '.html', '.docx', '.pdf', '.md'}
ENCODING = {'manifests_legacy.txt': 'latin-1'}

def fields_of(fname, table):
    for t, fs in SCHEMA[fname]:
        if t == table:
            return ENVF + [x.split(':', 1)[0] for x in fs]
    raise KeyError(table)

def kinds_of(fname, table):
    out = dict(ENV_KINDS)
    for t, fs in SCHEMA[fname]:
        if t == table:
            for x in fs:
                n, k = x.split(':', 1)
                out[n] = k
    return out

class Raw:
    __slots__ = ('table', 'batch', 'cells')

    def __init__(self, table, batch, cells):
        self.table, self.batch, self.cells = (table, batch, cells)

def _text(p, fname):
    enc = ENCODING.get(fname, 'utf-8')
    b = p.read_bytes()
    if b.startswith(b'\xef\xbb\xbf'):
        b = b[3:]
    return b.decode(enc)

def read_delim(p, fname, delim):
    rows, header = ([], None)
    for rec in csv.reader(io.StringIO(_text(p, fname), newline=''), delimiter=delim):
        if not rec or rec[0].startswith('#'):
            continue
        if rec[0] == 'batch':
            header = rec[1:]
            continue
        rows.append(Raw(SCHEMA[fname][0][0], rec[0], dict(zip(header, rec[1:]))))
    return rows

def read_txt(p, fname):
    rows, b, starts, heads = ([], None, None, None)
    lines = _text(p, fname).split('\n')
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith('== BATCH '):
            b = ln[9:].strip()
            ruler = lines[i + 1]
            starts = [m.start() for m in re.finditer('\\S+', ruler)]
            heads = ruler.split()
            i += 2
            continue
        if b and ln.strip():
            vals = [ln[starts[k]:starts[k + 1] if k + 1 < len(starts) else None].strip() for k in range(len(starts))]
            vals = ['' if v == '.' else v for v in vals]
            rows.append(Raw(SCHEMA[fname][0][0], b, dict(zip(heads, vals))))
        i += 1
    return rows

def read_jsonl(p, fname):
    rows, b = ([], None)
    for ln in _text(p, fname).splitlines():
        if ln.strip():
            d = json.loads(ln)
            if list(d) == ['batch']:
                b = d['batch']
                continue
            rows.append(Raw(SCHEMA[fname][0][0], b, {k: '' if v is None else str(v) for k, v in d.items()}))
    return rows

def read_json(p, fname):
    d = json.loads(_text(p, fname))
    rows = []
    for bl in d['batches']:
        for r in bl['records']:
            rows.append(Raw(SCHEMA[fname][0][0], bl['batch'], {k: '' if v is None else str(v) for k, v in r.items()}))
    return rows
_YREC = re.compile('(\\w+): ("(?:[^"\\\\]|\\\\.)*"|null)')

def read_yaml(p, fname):
    rows, b = ([], None)
    for ln in _text(p, fname).splitlines():
        s = ln.strip()
        if s.startswith('- batch:'):
            b = json.loads(s.split(':', 1)[1].strip())
        elif s.startswith('- {'):
            d = {k: json.loads(v) if v != 'null' else '' for k, v in _YREC.findall(s)}
            rows.append(Raw(SCHEMA[fname][0][0], b, d))
    return rows

def read_xml(p, fname):
    root = ET.fromstring(p.read_bytes())
    rows = []
    for el in root:
        if el.tag == 'batch':
            for r in el:
                rows.append(Raw(SCHEMA[fname][0][0], el.get('id'), dict(r.attrib)))
    return rows

def read_toml(p, fname):
    d = tomllib.loads(_text(p, fname))
    rows = []
    for bl in d.get('batch', []):
        for e in bl.get('entries', []):
            rows.append(Raw(SCHEMA[fname][0][0], bl['label'], {k: str(v) for k, v in e.items()}))
    return rows

def read_ini(p, fname):
    cp = configparser.RawConfigParser(interpolation=None, strict=False)
    cp.optionxform = str
    cp.read_string(_text(p, fname))
    rows = []
    for sec in cp.sections():
        d = dict(cp[sec])
        b = d.pop('batch')
        rows.append(Raw(sec.split('.')[0], b, d))
    return rows
_KV = re.compile('(\\w+)=("(?:[^"\\\\]|\\\\.)*"|\\S*)')

def _unq(v):
    if v.startswith('"'):
        return v[1:-1].replace('\\"', '"').replace('\\\\', '\\')
    return v

def read_log(p, fname):
    rows = []
    for ln in _text(p, fname).splitlines():
        if ln.startswith('EVT '):
            d = {k: _unq(v) for k, v in _KV.findall(ln[4:])}
            b = d.pop('batch')
            rows.append(Raw(SCHEMA[fname][0][0], b, d))
    return rows

def read_mbox(p, fname):
    rows = []
    for m in re.split('\\n(?=From \\S+ \\w{3} \\w{3} )', '\n' + _text(p, fname)):
        if not m.strip():
            continue
        head = m.strip('\n').split('\n\n', 1)[0]
        h = {}
        for ln in head.split('\n')[1:]:
            k, _, v = ln.partition(': ')
            h[k] = v
        d = {}
        for f in fields_of(fname, 'notices'):
            hk = 'X-' + f.replace('_', '-').title()
            if hk in h:
                d[f] = h[hk]
        rows.append(Raw('notices', h['X-Batch'], d))
    return rows

def read_ics(p, fname):
    rows, cur = ([], None)
    for ln in _text(p, fname).splitlines():
        if ln == 'BEGIN:VEVENT':
            cur = {}
        elif ln == 'END:VEVENT':
            b = cur.pop('batch')
            rows.append(Raw('windows', b, cur))
            cur = None
        elif cur is not None:
            k, _, v = ln.partition(':')
            name = k.split(';')[0]
            key = {'UID': 'rid', 'DTSTART': 'start', 'DTEND': 'end', 'X-BATCH': 'batch', 'X-REV': 'rev', 'X-ST': 'st', 'X-RECORDED': 'rec_at', 'X-SERVICE': 'service'}.get(name)
            if key in ('start', 'end'):
                v = f'{v[0:4]}-{v[4:6]}-{v[6:8]}'
            if key:
                cur[key] = v
    return rows

def _md_cells(line):
    out, cur, i = ([], '', 1)
    s = line.strip()
    while i < len(s) - 1:
        ch = s[i]
        if ch == '\\' and i + 1 < len(s):
            cur += s[i + 1]
            i += 2
            continue
        if ch == '|':
            out.append(cur.strip())
            cur = ''
        else:
            cur += ch
        i += 1
    out.append(cur.strip())
    return out

def read_md(p, fname):
    text = _text(p, fname)
    reg = text.split('\n## Register\n', 1)[1]
    rows, head, lines = ([], None, reg.split('\n'))
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith('### Batch '):
            head = ln[10:].strip()
        if ln.startswith('| ') and i + 1 < len(lines) and lines[i + 1].startswith('|---'):
            hdr = _md_cells(ln)
            i += 2
            while i < len(lines) and lines[i].startswith('| '):
                rows.append(Raw(SCHEMA[fname][0][0], head, dict(zip(hdr, _md_cells(lines[i])))))
                i += 1
            continue
        i += 1
    return rows

class _HT(html.parser.HTMLParser):

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables, self.cur, self.cell, self.row = ([], None, None, None)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'table':
            self.cur = {'batch': a.get('data-batch'), 'head': [], 'rows': []}
        elif tag == 'tr' and self.cur is not None:
            self.row = []
        elif tag in ('td', 'th') and self.row is not None:
            self.cell = ''

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.cell is not None:
            self.row.append(self.cell)
            self.cell = None
        elif tag == 'tr' and self.row is not None:
            if self.cur['head']:
                self.cur['rows'].append(self.row)
            else:
                self.cur['head'] = self.row
            self.row = None
        elif tag == 'table' and self.cur is not None:
            self.tables.append(self.cur)
            self.cur = None

    def handle_data(self, data):
        if self.cell is not None:
            self.cell += data

def read_html(p, fname):
    ps = _HT()
    ps.feed(_text(p, fname))
    rows = []
    for t in ps.tables:
        if t['batch'] is None:
            continue
        for r in t['rows']:
            rows.append(Raw(SCHEMA[fname][0][0], t['batch'], dict(zip(t['head'], r))))
    return rows
_WNS = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'

def read_docx(p, fname):
    with zipfile.ZipFile(p) as z:
        root = ET.fromstring(z.read('word/document.xml'))
    body = root.find(_WNS + 'body')
    rows, last = ([], None)
    for el in body:
        if el.tag == _WNS + 'p':
            last = ''.join((t.text or '' for t in el.iter(_WNS + 't')))
        elif el.tag == _WNS + 'tbl':
            trs = [[''.join((t.text or '' for t in tc.iter(_WNS + 't'))) for tc in tr.findall(_WNS + 'tc')] for tr in el.findall(_WNS + 'tr')]
            b = last.split()[-1]
            for r in trs[1:]:
                rows.append(Raw(SCHEMA[fname][0][0], b, dict(zip(trs[0], r))))
    return rows
_SNS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
_RNS = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'

def read_xlsx(p, fname):
    rows = []
    with zipfile.ZipFile(p) as z:
        wb = ET.fromstring(z.read('xl/workbook.xml'))
        rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        target = {r.get('Id'): r.get('Target') for r in rels}
        for sh in wb.iter(_SNS + 'sheet'):
            name = sh.get('name')
            data = ET.fromstring(z.read('xl/' + target[sh.get(_RNS + 'id')]))
            table = []
            for r in data.iter(_SNS + 'row'):
                vals = {}
                for c in r.iter(_SNS + 'c'):
                    ref = re.match('([A-Z]+)', c.get('r')).group(1)
                    col = 0
                    for ch in ref:
                        col = col * 26 + ord(ch) - 64
                    if c.get('t') == 'inlineStr':
                        vals[col - 1] = ''.join((t.text or '' for t in c.iter(_SNS + 't')))
                    else:
                        v = c.find(_SNS + 'v')
                        vals[col - 1] = v.text if v is not None else ''
                table.append([vals.get(i, '') for i in range(max(vals) + 1 if vals else 0)])
            hdr = table[0]
            for r in table[1:]:
                r = r + [''] * (len(hdr) - len(r))
                rows.append(Raw(name, r[0], dict(zip(hdr[1:], r[1:]))))
    return rows

def read_sqlite(p, fname):
    con = sqlite3.connect(f'file:{p}?mode=ro', uri=True)
    rows = []
    for t, fs in SCHEMA[fname]:
        cols = fields_of(fname, t)
        for r in con.execute(f"SELECT batch,{','.join(cols)} FROM {t} ORDER BY rowid"):
            rows.append(Raw(t, r[0], {c: '' if v is None else str(v) for c, v in zip(cols, r[1:])}))
    con.close()
    return rows

class _TR:

    def __init__(self, b, p=0):
        self.b, self.p = (b, p)

    def byte(self):
        v = self.b[self.p]
        self.p += 1
        return v

    def uvar(self):
        s = r = 0
        while True:
            x = self.byte()
            r |= (x & 127) << s
            s += 7
            if not x & 128:
                return r

    def zz(self):
        n = self.uvar()
        return n >> 1 ^ -(n & 1)

    def val(self, t):
        if t in (1, 2):
            return t == 1
        if t == 3:
            return self.byte()
        if t in (4, 5, 6):
            return self.zz()
        if t == 7:
            v = struct.unpack('<d', self.b[self.p:self.p + 8])[0]
            self.p += 8
            return v
        if t == 8:
            n = self.uvar()
            v = bytes(self.b[self.p:self.p + n])
            self.p += n
            return v
        if t in (9, 10):
            h = self.byte()
            n, et = (h >> 4, h & 15)
            if n == 15:
                n = self.uvar()
            return [self.val(et) for _ in range(n)]
        if t == 12:
            return self.struct()
        raise ValueError(t)

    def struct(self):
        out, last = ({}, 0)
        while True:
            h = self.byte()
            if h == 0:
                return out
            d, t = (h >> 4, h & 15)
            fid = last + d if d else self.zz()
            last = fid
            out[fid] = self.val(t)

def read_parquet(p, fname):
    b = p.read_bytes()
    n = struct.unpack('<I', b[-8:-4])[0]
    md = _TR(b, len(b) - 8 - n).struct()
    nrows = md[3]
    data = {}
    for cc in md[4][0][1]:
        meta = cc[3]
        name = meta[3][0].decode()
        r = _TR(b, meta[9])
        r.struct()
        q_ = r.p
        vals = []
        for _ in range(nrows):
            ln = struct.unpack('<I', b[q_:q_ + 4])[0]
            vals.append(b[q_ + 4:q_ + 4 + ln].decode('utf-8'))
            q_ += 4 + ln
        data[name] = vals
    t = SCHEMA[fname][0][0]
    cols = [c for c in data if c != 'batch']
    return [Raw(t, data['batch'][i], {c: data[c][i] for c in cols}) for i in range(nrows)]

def _pdf_lines(b):
    out = []
    for m in re.finditer(b'stream\\n(.*?)\\nendstream', b, re.S):
        for s in re.finditer(b"\\(((?:[^\\\\)]|\\\\.)*)\\) '", m.group(1)):
            out.append(re.sub(b'\\\\(.)', b'\\1', s.group(1)).decode('latin-1'))
    return out

def read_pdf(p, fname):
    lines = _pdf_lines(p.read_bytes())
    rows, b, hdr = ([], None, None)
    t = SCHEMA[fname][0][0]
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith('BATCH '):
            b = ln[6:].strip()
            hdr = lines[i + 1].split(' | ')
            i += 2
            continue
        if b and ln:
            rows.append(Raw(t, b, dict(zip(hdr, ln.split(' | ')))))
        elif not ln:
            b = None
        i += 1
    return rows
READERS = {'.csv': lambda p, f: read_delim(p, f, ','), '.tsv': lambda p, f: read_delim(p, f, '\t'), '.txt': read_txt, '.jsonl': read_jsonl, '.json': read_json, '.yaml': read_yaml, '.xml': read_xml, '.toml': read_toml, '.ini': read_ini, '.log': read_log, '.mbox': read_mbox, '.ics': read_ics, '.md': read_md, '.html': read_html, '.docx': read_docx, '.xlsx': read_xlsx, '.db': read_sqlite, '.parquet': read_parquet, '.pdf': read_pdf}

def read_file(d, fname):
    p = Path(d) / fname
    if not p.is_file():
        raise InputError(f'missing input file {fname}')
    try:
        return READERS[p.suffix](p, fname)
    except InputError:
        raise
    except Exception as exc:
        raise InputError(f'cannot parse {fname}: {exc}')

def from_wall(wall, zone):
    """UTC instant whose wall clock in zone equals wall (seconds)."""
    if zone == 'UTC':
        return wall
    for cand in sorted({wall - zone_offset(zone, wall - h * 3600) for h in (-13, 0, 13)}):
        if cand + zone_offset(zone, cand) == wall:
            return cand
    return wall - zone_offset(zone, wall)

def _ymd_hms(s):
    y, m, d = (int(s[0:4]), int(s[5:7]), int(s[8:10]))
    hh, mi, ss = (int(s[11:13]), int(s[14:16]), int(s[17:19]) if len(s) >= 19 else 0)
    return days_from_civil(y, m, d) * DAY + hh * 3600 + mi * 60 + ss

def dec_ts(s, conv):
    s = s.strip()
    if conv == 'iso':
        return _ymd_hms(s.replace('T', ' ').rstrip('Z'))
    if conv == 'epoch':
        return int(s)
    if conv == 'epochms':
        return int(s) // 1000
    kind, _, zone = conv.partition(':')
    if kind == 'off':
        base = _ymd_hms(s[:19].replace('T', ' '))
        sign = 1 if s[19] == '+' else -1
        off = sign * (int(s[20:22]) * 3600 + int(s[23:25]) * 60)
        return base - off
    if kind == 'naive':
        return from_wall(_ymd_hms(s), zone)
    if kind in ('xl', 'xl4'):
        base = XL1900_DAY + 1 if kind == 'xl' else XL1900_DAY
        minutes = int((Decimal(s) * 1440).to_integral_value(rounding=ROUND_HALF_EVEN))
        return from_wall(base * DAY + minutes * 60, zone)
    if kind in ('dmy', 'mdy'):
        a, b_, rest = (s[0:2], s[3:5], s[6:])
        d, m = (b_, a) if kind == 'dmy' else (a, b_)
        wall = days_from_civil(int(rest[0:4]), int(m), int(d)) * DAY + int(rest[5:7]) * 3600 + int(rest[8:10]) * 60
        return from_wall(wall, zone)
    raise ValueError(conv)

def dec_date(s, conv):
    s = s.strip()
    if conv == 'iso':
        return days_from_civil(int(s[0:4]), int(s[5:7]), int(s[8:10]))
    if conv == 'dmy':
        return days_from_civil(int(s[6:10]), int(s[3:5]), int(s[0:2]))
    if conv == 'mdy':
        return days_from_civil(int(s[6:10]), int(s[0:2]), int(s[3:5]))
    if conv == 'compact':
        return days_from_civil(int(s[0:4]), int(s[4:6]), int(s[6:8]))
    if conv == 'xl':
        return XL1900_DAY + int(s)
    raise ValueError(conv)

def dec_dec(s, conv):
    s = s.strip()
    if conv == 'de':
        s = s.replace(',', '')
    elif conv == 'fr':
        s = s.replace(' ', '').replace(',', '.')
    return Decimal(s)

def dec_int(s, conv):
    s = s.strip()
    if conv == 'grouped':
        s = s.replace(',', '')
    elif conv == 'de':
        s = s.replace('.', '')
    v = int(s)
    return -v if conv == 'neg' else v

def dec_hours(s, conv):
    s = s.strip()
    if conv == 'h':
        return Decimal(s)
    if conv == 'min':
        return Decimal(s)
    if conv == 'hm':
        m = re.fullmatch('(\\d+)h(\\d+)m', s)
        return Decimal(int(m.group(1)) * 60 + int(m.group(2))) / Decimal(60)
    if conv == 'iso':
        m = re.fullmatch('PT(?:(\\d+)H)?(?:(\\d+)M)?', s)
        return Decimal(int(m.group(1) or 0) * 60 + int(m.group(2) or 0)) / Decimal(60)
    raise ValueError(conv)

def dec_money(s, conv, cur):
    s = s.strip()
    exp = 2
    if conv == 'minor':
        return int(s)
    neg = False
    if conv == 'paren' and s.startswith('('):
        neg, s = (True, s[1:-1])
    if conv == 'de':
        s = s.replace('.', '').replace(',', '.')
    if s.startswith('-'):
        neg, s = (True, s[1:])
    v = int((Decimal(s) * 10 ** exp).to_integral_value())
    return -v if neg else v

def dec_bool(s, conv):
    s = s.strip()
    v = {'true': True, 'false': False, '1': True, '0': False, 'yes': True, 'no': False, 'Y': True, 'N': False}[s]
    return v

def canon_id(s):
    s = s.strip().replace('_', '-')
    if re.fullmatch('[tT]\\d{3}', s):
        return s.upper()
    return s.lower()
SVC_RE = re.compile('(?i)svc-(\\d+)')

def norm_name(eco, raw):
    s = unicodedata.normalize('NFKC', raw).replace('\u200b', '').strip()
    if eco == 'pypi':
        return re.sub('[-_.]+', '-', s.lower())
    if eco == 'npm':
        return s.lower()
    if eco == 'cargo':
        return s.lower().replace('_', '-')
    return s.lower()
_PRE = {'a': 'alpha', 'alpha': 'alpha', 'b': 'beta', 'beta': 'beta', 'rc': 'rc'}

def parse_ver(s):
    s = s.strip()
    if s[:1] in 'vV':
        s = s[1:]
    s = s.split('+', 1)[0]
    m = re.fullmatch('(\\d+)(?:\\.(\\d+))?(?:\\.(\\d+))?(?:-?\\.?(alpha|beta|rc|a|b)\\.?(\\d+))?', s, re.I)
    if not m:
        raise ValueError(f'version {s!r}')
    pre = (_PRE[m.group(4).lower()], int(m.group(5))) if m.group(4) else None
    return Ver(int(m.group(1)), int(m.group(2) or 0), int(m.group(3) or 0), pre)

def norm_vid(s):
    s = s.strip()
    up = s.upper()
    if up.startswith('CVE-'):
        y, n = up[4:].split('-')
        return up
    if up.startswith('GHSA-'):
        return 'GHSA-' + s[5:].lower()
    return up

def norm_vec(s):
    s = s.strip().upper()
    return s if s.startswith('CVSS:') else 'CVSS:3.1/' + s

def dec_events(s):
    out = []
    for part in s.split('|'):
        k, _, v = part.partition(':')
        out.append((k, '0' if v == '0' else parse_ver(v)))
    return out

def dec_enum(s, vocab, conv):
    V = VOC[vocab]
    s = s.strip()
    return V['word'][V[conv].index(s)]

def decode_cell(kind, s, conv, row):
    g = 'enum' if kind.startswith('enum:') else kind
    if g == 'ts':
        return dec_ts(s, conv)
    if g == 'date':
        return dec_date(s, conv)
    if g == 'dec':
        return dec_dec(s, conv)
    if g == 'int':
        return dec_int(s, conv)
    if g == 'hours':
        return dec_hours(s, conv)
    if g == 'money':
        return dec_money(s, conv, row.get('currency', 'EUR'))
    if g == 'bool':
        return dec_bool(s, conv)
    if g == 'id':
        return canon_id(s)
    if g == 'svcid':
        return s.strip()
    if g == 'pkg':
        return s
    if g == 'ver':
        return parse_ver(s)
    if g == 'vid':
        return norm_vid(s)
    if g == 'vec':
        return norm_vec(s)
    if g == 'spdx':
        return canon_spdx(s.strip())
    if g == 'events':
        return dec_events(s)
    if g == 'enum':
        return dec_enum(s, kind[5:], conv)
    return s
