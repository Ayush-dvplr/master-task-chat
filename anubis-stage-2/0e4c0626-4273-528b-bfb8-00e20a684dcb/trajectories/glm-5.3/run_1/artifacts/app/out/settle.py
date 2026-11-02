#!/usr/bin/env python3
"""Kestrel CI build-minute settlement for a monthly close.

Usage:  python3 settle.py DATA_DIR OUT_DIR

Reads only DATA_DIR, writes the thirteen settlement artifacts into OUT_DIR.
"""

import collections
import csv
import datetime
import gzip
import io
import json
import os
import re
import sqlite3
import sys
import zipfile
import zlib

EPOCH = datetime.timezone.utc

ATTEMPT_SOURCES = ('fleet_north.log', 'fleet_south.log', 'attempt_events.jsonl',
                   'usage_events.jsonl')
ATTEMPT_COLUMNS = {'fleet_north.log': ('attempt', 'job'),
                   'fleet_south.log': ('attempt', 'job'),
                   'attempt_events.jsonl': ('attempt_id', 'job_id'),
                   'usage_events.jsonl': ('attempt', 'job')}
MIRROR_SOURCES = ('attempt_events_v3.jsonl', 'usage_export_legacy.log')
LOOKUP_SOURCES = ('lookups_shard1.jsonl', 'lookups_shard2.jsonl', 'lookups_shard3.jsonl.gz')

# ---------------------------------------------------------------- file readers


def read_bytes(path):
    with open(path, 'rb') as fh:
        return fh.read()


def read_text(path):
    return read_bytes(path).decode('utf-8', 'replace')


def md_text_tables(text):
    """Return [(caption, header, rows)] for every markdown pipe table."""
    out = []
    caption = None
    header = None
    rows = []
    for line in text.split('\n'):
        s = line.strip()
        m = re.fullmatch(r'\*\*Table: (.+?)\*\*', s)
        if m:
            if header and rows:
                out.append((caption, header, rows))
            caption, header, rows = m.group(1).strip(), None, []
            continue
        if s.startswith('|'):
            cells = [c.strip() for c in s.strip('|').split('|')]
            if all(set(c) <= set('-: ') for c in cells):
                continue
            if header is None:
                header = cells
                continue
            rows.append(cells)
        elif s and header and rows:
            out.append((caption, header, rows))
            caption, header, rows = caption, None, []
    if header and rows:
        out.append((caption, header, rows))
    return out


def html_text_tables(text):
    out = []
    for tm in re.finditer(r'<table><caption>(.*?)</caption>(.*?)</table>', text, re.S):
        cap = re.sub(r'<[^>]+>', '', tm.group(1)).strip()
        header = None
        rows = []
        for r in re.findall(r'<tr>(.*?)</tr>', tm.group(2), re.S):
            cells = [re.sub(r'<[^>]+>', '', c).strip()
                     for c in re.findall(r'<t[dh]>(.*?)</t[dh]>', r, re.S)]
            if not cells:
                continue
            if header is None:
                header = cells
                continue
            if len(cells) == len(header):
                rows.append(cells)
        if header and rows:
            out.append((cap, header, rows))
    return out


def docx_text_tables(path):
    """Return [(caption, header, rows)] with the caption of the nearest paragraph."""
    xml = zipfile.ZipFile(path).read('word/document.xml').decode('utf-8', 'replace')
    out = []
    last = ''
    for part in re.split(r'(<w:tbl>.*?</w:tbl>)', xml, flags=re.S):
        if part.startswith('<w:tbl>'):
            header = None
            rows = []
            for tr in re.findall(r'<w:tr>(.*?)</w:tr>', part, re.S):
                cells = [''.join(re.findall(r'<w:t[^>]*>(.*?)</w:t>', tc, re.S))
                         for tc in re.findall(r'<w:tc>(.*?)</w:tc>', tr, re.S)]
                cells = [c.strip() for c in cells]
                if not cells:
                    continue
                if header is None:
                    header = cells
                    continue
                if len(cells) == len(header):
                    rows.append(cells)
            cap = last
            if cap.startswith('Table: '):
                cap = cap[len('Table: '):]
            if header and rows:
                out.append((cap.strip(), header, rows))
        else:
            paras = re.findall(r'<w:p[ >].*?</w:p>', part, re.S)
            if paras:
                last = ''.join(re.findall(r'<w:t[^>]*>(.*?)</w:t>', paras[-1], re.S)).strip()
    return out


def pdf_runs(path):
    """Return the text runs of every page of a simple pdf.

    The published /Length values cannot be trusted, so each stream is fed to a
    decompress object that stops at the end of its own zlib data.  Every
    table row of these documents is a single text run.
    """
    data = read_bytes(path)
    runs = []
    for m in re.finditer(rb'<<(.*?)>>\s*stream\r?\n', data, re.S):
        info = m.group(1)
        if b'/FlateDecode' not in info:
            continue
        start = m.end()
        try:
            content = zlib.decompressobj().decompress(data[start:])
        except Exception:
            continue
        for tm in re.finditer(rb'\((?:[^()\\]|\\.)*\)', content):
            s = tm.group(0)[1:-1]
            s = s.replace(b'\\(', b'(').replace(b'\\)', b')').replace(b'\\\\', b'\\')
            runs.append(s.decode('latin1'))
        runs.append('\f')
    return runs


def pdf_pages(path):
    """Group the pdf text runs per page, one line per page."""
    pages = []
    cur = []
    for run in pdf_runs(path):
        if run == '\f':
            pages.append(' '.join(cur))
            cur = []
        else:
            cur.append(run)
    if cur:
        pages.append(' '.join(cur))
    return [p for p in pages if p]


def pdf_text(path):
    return '\n'.join(pdf_pages(path))


PDF_TABLE_COLUMNS = {
    'Block controls': ('control_id', 'file', 'block', 'records', 'control_sum',
                       'status', 'batch', 'flag'),
    'Field conventions': ('file', 'column', 'context', 'value', 'codec'),
    'Column aliases': ('file', 'alias', 'column', 'from_record'),
    'Billing granularity': ('sku', 'granularity_s', 'batch', 'flag'),
    'Billing classes': ('class', 'multiplier_permille'),
}

PDF_TABLE_CHECKS = {
    'Block controls': lambda d: re.fullmatch(r'[A-Z]{2}-\d+', d.get('control_id') or '') is not None,
    'Field conventions': lambda d: d.get('codec') in CODEC_KIND,
    'Column aliases': lambda d: re.fullmatch(r'\d+', d.get('from_record') or '') is not None,
    'Billing granularity': lambda d: re.fullmatch(r'\d+', d.get('granularity_s') or '') is not None,
    'Billing classes': lambda d: re.fullmatch(r'\d+', d.get('multiplier_permille') or '') is not None,
}


def pdf_table_rows(runs):
    """Parse the pipe tables of a pdf from its text runs (each row is one run)."""
    out = []
    i = 0
    n = len(runs)
    while i < n:
        m = re.fullmatch(r'Table: ([A-Za-z0-9 ()]+)', runs[i].strip())
        if not m:
            i += 1
            continue
        cap = m.group(1).strip()
        i += 1
        cols = None
        for key, names in PDF_TABLE_COLUMNS.items():
            if cap.startswith(key):
                cols = names
                break
        if cols is None or i >= n:
            continue
        header = None
        if runs[i] != '\f' and ' | ' in runs[i]:
            cand = [c.strip() for c in runs[i].split(' | ')]
            if cand and all(h in cols for h in cand):
                header = cand
        if not header:
            continue
        i += 1
        rows = []
        check = None
        for key, fn in PDF_TABLE_CHECKS.items():
            if cap.startswith(key):
                check = fn
                break
        while i < n:
            run = runs[i]
            if run == '\f':
                i += 1
                continue
            if ' | ' not in run:
                break
            cells = [c.strip() for c in run.split(' | ')]
            if len(cells) != len(header):
                break
            if check is not None and not check(dict(zip(header, cells))):
                break
            rows.append(cells)
            i += 1
        if rows:
            out.append((cap, header, rows))
    return out


def pdf_tables_for(path):
    return pdf_table_rows(pdf_runs(path))


def pdf_tables(text):
    return pdf_table_rows(text.split('\n'))


def xlsx_tables(path):
    z = zipfile.ZipFile(path)
    wb = z.read('xl/workbook.xml').decode('utf-8', 'replace')
    names = re.findall(r'<sheet name="([^"]*)"', wb)
    out = []
    for idx, name in enumerate(names, start=1):
        try:
            xml = z.read('xl/worksheets/sheet%d.xml' % idx).decode('utf-8', 'replace')
        except KeyError:
            continue
        header = None
        rows = []
        for rm in re.finditer(r'<row[^>]*>(.*?)</row>', xml, re.S):
            cells = []
            for cm in re.finditer(
                    r'<c r="[A-Z]+\d+"[^>]*>(?:<is[^>]*><t[^>]*>(.*?)</t></is>|<v>(.*?)</v>)</c>',
                    rm.group(1), re.S):
                cells.append(cm.group(1) if cm.group(1) is not None else cm.group(2))
            cells = [c.strip() if c is not None else '' for c in cells]
            if not cells:
                continue
            if header is None:
                header = cells
                continue
            if len(cells) == len(header):
                rows.append(cells)
        if header and rows:
            out.append((name, header, rows))
    return out


def sqlite_tables(path):
    con = sqlite3.connect(path)
    out = []
    for (name,) in con.execute("select name from sqlite_master where type='table' order by rowid"):
        cols = [r[1] for r in con.execute('pragma table_info(%s)' % name)]
        rows = [list(r) for r in con.execute('select * from %s' % name)]
        out.append((name, cols, rows))
    con.close()
    return out


def xml_elements(path, tag):
    out = []
    for m in re.finditer(r'<%s\b([^>]*)/?>' % tag, read_text(path)):
        out.append(dict(re.findall(r'([A-Za-z_0-9]+)="([^"]*)"', m.group(1))))
    return out


def ics_events(path):
    out = []
    cur = None
    for line in read_text(path).split('\n'):
        s = line.strip()
        if s == 'BEGIN:VEVENT':
            cur = {}
        elif s == 'END:VEVENT':
            if cur is not None:
                out.append(cur)
            cur = None
        elif cur is not None and ':' in s:
            k, v = s.split(':', 1)
            cur[k] = v
    return out


def mbox_messages(path):
    out = []
    cur = None
    for line in read_text(path).split('\n'):
        if line.startswith('From '):
            if cur is not None:
                out.append(cur)
            cur = {'headers': [], 'body': []}
        elif cur is not None:
            cur['body'].append(line)
    if cur is not None:
        out.append(cur)
    return out


def ini_sections(path):
    out = []
    cur = None
    for line in read_text(path).split('\n'):
        s = line.strip()
        if not s or s.startswith(';') or s.startswith('#'):
            continue
        m = re.match(r'\[(.+)\]$', s)
        if m:
            cur = {}
            out.append(cur)
            continue
        if cur is not None and '=' in s:
            k, v = s.split('=', 1)
            cur[k.strip()] = v.strip()
    return out


def csv_rows(path, delimiter=None):
    """Tabular rows with restated headers; returns dicts keyed by the active header."""
    text = read_text(path)
    if delimiter is None:
        delimiter = '\t' if path.endswith('.tsv') else ','
    header = None
    out = []
    for r in csv.reader(io.StringIO(text), delimiter=delimiter):
        if not r or not r[0].strip():
            continue
        if header is None:
            header = [c.strip() for c in r]
            continue
        if r[0].strip() in header and len(r) == len(header):
            header = [c.strip() for c in r]
            continue
        if len(r) == len(header):
            out.append(dict(zip(header, r)))
    return out


def fixed_width_records(path, layouts):
    """layouts: {layout_id: [(position, column, width)]}"""
    out = []
    current = None
    for line in read_text(path).split('\n'):
        if not line.strip():
            continue
        if line.startswith('H'):
            current = line[1:].strip()
            continue
        if line.startswith('D') and current in layouts:
            body = line[1:]
            rec = {}
            for pos, col, width in layouts[current]:
                rec[col] = body[:width]
                body = body[width:]
            out.append(rec)
    return out


def _toml_value(v):
    if v.startswith('"') and v.endswith('"'):
        return v[1:-1]
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        return v


def toml_lite(path):
    scalars = {}
    arrays = {}
    name = None
    for line in read_text(path).split('\n'):
        s = line.strip()
        if not s or s.startswith('#'):
            continue
        m = re.match(r'([A-Za-z_0-9]+)\s*=\s*\[', s)
        if m:
            name = m.group(1)
            arrays.setdefault(name, [])
            s = s[s.index('[') + 1:]
            if s.strip().startswith(']'):
                name = None
                continue
        m = re.match(r'([A-Za-z_0-9]+)\s*=\s*(.*)$', s)
        if m and name is None:
            scalars[m.group(1)] = _toml_value(m.group(2).strip())
            continue
        if name is not None:
            for mm in re.finditer(r'\{(.*?)\}', s):
                rec = {}
                for part in mm.group(1).split(','):
                    if '=' not in part:
                        continue
                    k, v = part.split('=', 1)
                    rec[k.strip()] = _toml_value(v.strip())
                arrays[name].append(rec)
            if s.strip().endswith(']'):
                name = None
    return scalars, arrays


def _split_top(s):
    parts = []
    depth = 0
    cur = ''
    quote = False
    for ch in s:
        if ch == '"':
            quote = not quote
            cur += ch
        elif ch == '{' and not quote:
            depth += 1
            cur += ch
        elif ch == '}' and not quote:
            depth -= 1
            cur += ch
        elif ch == ',' and depth == 0 and not quote:
            parts.append(cur)
            cur = ''
        else:
            cur += ch
    if cur.strip():
        parts.append(cur)
    return [p.strip() for p in parts if p.strip()]


def yaml_lite(path):
    out = collections.OrderedDict()
    section = None
    for line in read_text(path).split('\n'):
        if line.startswith('#') or not line.strip():
            continue
        m = re.match(r'^([A-Za-z_0-9]+):\s*$', line)
        if m:
            section = m.group(1)
            out[section] = []
            continue
        m = re.match(r'^\s*-\s*\{(.*)\}\s*$', line)
        if m and section:
            rec = {}
            for part in _split_top(m.group(1)):
                if ':' not in part:
                    continue
                k, v = part.split(':', 1)
                rec[k.strip()] = v.strip().strip('"')
            out[section].append(rec)
    return out


def jsonl_records(path, gz=False):
    op = gzip.open if gz else open
    out = []
    with op(path, 'rb') as fh:
        for raw in fh:
            if not raw.strip():
                continue
            out.append(json.loads(raw.decode('utf-8', 'replace')))
    return out


# ---------------------------------------------------------------- codecs

CODEC_KIND = collections.OrderedDict([
    ('iso_z', 'timestamp'), ('epoch', 'timestamp'), ('epoch_ms', 'timestamp'),
    ('utc_naive', 'timestamp'), ('local', 'timestamp'), ('iso_off', 'timestamp'),
    ('xl1900', 'timestamp'),
    ('ms', 'duration'), ('us', 'duration'), ('ns', 'duration'), ('s3', 'duration'),
    ('usd6', 'money'), ('micro', 'money'), ('eu6', 'money'), ('kusd9', 'money'),
    ('plain', 'integer'), ('sep', 'integer'), ('eu', 'integer'), ('kib', 'integer'),
    ('exact', 'identifier'), ('upper', 'identifier'), ('ws', 'identifier'),
])


def _keyval(value):
    if isinstance(value, (list, tuple)):
        return tuple(_keyval(v) for v in value)
    if isinstance(value, dict):
        return tuple(sorted((k, _keyval(v)) for k, v in value.items()))
    return value


def canon_id(value):
    """Canonical identifier: surrounding space is not part of it, canonical ids are lower case."""
    if value is None:
        return None
    v = str(value).strip()
    if v and v == v.upper():
        v = v.lower()
    return v


def _dec_to_int(v):
    if '.' in v:
        whole, frac = v.split('.', 1)
    else:
        whole, frac = v, ''
    sign = -1 if whole.startswith('-') else 1
    whole = whole.lstrip('+-') or '0'
    frac = (frac + '000000')[:6]
    return sign * (int(whole) * 1000000 + int(frac))


class Decoder:
    """Codec decoder; knows the clock zones and their DST rules."""

    def __init__(self, zones, dst_rules):
        self.zones = zones
        self.dst = dst_rules

    def zone_offsets(self, zone, instant):
        """The UTC offsets of a clock zone at an instant."""
        if zone in self.dst:
            t, before, after = self.dst[zone]
            return [before] if instant < t else [after]
        m = re.fullmatch(r'[A-Z]+([+-])(\d+)(?::(\d+))?', zone or '')
        if not m:
            return [0]
        off = int(m.group(2)) * 3600 + int(m.group(3) or 0) * 60
        return [-off if m.group(1) == '-' else off]

    def wall_to_instant(self, naive, zone, fold=False):
        cands = set()
        for probe in (naive, naive - 90000, naive + 90000):
            cands.update(self.zone_offsets(zone, probe))
        good = []
        for off in sorted(cands):
            inst = naive - off
            if off in self.zone_offsets(zone, inst):
                good.append(inst)
        if not good:
            good = [naive - self.zone_offsets(zone, naive)[0]]
        good.sort()
        return int(good[-1] if fold else good[0])

    def timestamp(self, value, codec, zone=None):
        v = (value or '').strip()
        if codec == 'iso_z':
            return int(datetime.datetime.strptime(v, '%Y-%m-%dT%H:%M:%SZ')
                       .replace(tzinfo=EPOCH).timestamp())
        if codec == 'epoch':
            return int(v)
        if codec == 'epoch_ms':
            return int(v) // 1000
        if codec == 'utc_naive':
            return int(datetime.datetime.strptime(v, '%Y-%m-%d %H:%M:%S')
                       .replace(tzinfo=EPOCH).timestamp())
        if codec == 'local':
            fold = v.endswith('+fold')
            if fold:
                v = v[:-len('+fold')]
            naive = int(datetime.datetime.strptime(v, '%Y-%m-%d %H:%M:%S')
                        .replace(tzinfo=EPOCH).timestamp())
            return self.wall_to_instant(naive, zone, fold)
        if codec == 'iso_off':
            if v.endswith('+fold'):
                v = v[:-len('+fold')]
            return int(datetime.datetime.strptime(v, '%Y-%m-%dT%H:%M:%S%z').timestamp())
        if codec == 'xl1900':
            base = datetime.datetime(1899, 12, 30, tzinfo=EPOCH)
            return int((base + datetime.timedelta(days=float(v))).timestamp())
        raise ValueError('timestamp codec %r for %r' % (codec, value))

    def duration_ms(self, value, codec):
        v = (value or '').strip()
        if codec == 'ms':
            return int(v)
        if codec == 'us':
            return int(v) // 1000
        if codec == 'ns':
            return int(v) // 1000000
        if codec == 's3':
            return int(round(float(v) * 1000))
        raise ValueError('duration codec %r for %r' % (codec, value))

    def money_micro(self, value, codec):
        v = (value or '').strip()
        neg = v.startswith('-')
        if neg:
            v = v[1:]
        if codec == 'usd6':
            out = _dec_to_int(v)
        elif codec == 'micro':
            out = int(v)
        elif codec == 'eu6':
            out = _dec_to_int(v.replace('.', '').replace(',', '.'))
        elif codec == 'kusd9':
            whole, _, frac = v.partition('.')
            frac = (frac + '000000000')[:9]
            out = int(whole or '0') * 1000000000 + int(frac or '0')
        else:
            raise ValueError('money codec %r for %r' % (codec, value))
        return -out if neg else out

    def integer(self, value, codec):
        v = (value or '').strip()
        if codec == 'kib':
            return int(v) * 1024
        if codec in ('plain', None):
            return int(v)
        if codec == 'sep':
            return int(v.replace(',', ''))
        if codec == 'eu':
            return int(v.replace('.', ''))
        raise ValueError('integer codec %r for %r' % (codec, value))

    def value(self, raw, codec, zone=None):
        kind = CODEC_KIND.get(codec)
        if kind == 'timestamp':
            return self.timestamp(raw, codec, zone)
        if kind == 'duration':
            return self.duration_ms(raw, codec)
        if kind == 'money':
            return self.money_micro(raw, codec)
        if kind == 'integer':
            return self.integer(raw, codec)
        return canon_id(raw)


def iso(instant):
    if instant is None:
        return None
    return datetime.datetime.fromtimestamp(int(instant), EPOCH).strftime('%Y-%m-%dT%H:%M:%SZ')


def parse_iso(s):
    return int(datetime.datetime.strptime(s.strip(), '%Y-%m-%dT%H:%M:%SZ')
               .replace(tzinfo=EPOCH).timestamp())


def round_half_even(num, den):
    """Exact rational rounding, half to even."""
    if den == 0:
        return 0
    sign = -1 if (num < 0) != (den < 0) else 1
    n = abs(num)
    d = abs(den)
    q, r = divmod(n, d)
    if 2 * r > d or (2 * r == d and q % 2 == 1):
        q += 1
    return sign * q


# ---------------------------------------------------------------- registry


class Registry:
    """Everything the written rules publish, decoded from the documents."""

    def __init__(self, data_dir):
        self.dir = data_dir
        self._load()

    def path(self, name):
        return os.path.join(self.dir, name)

    def exists(self, name):
        return os.path.exists(self.path(name))

    # -- loading ---------------------------------------------------------
    def _load(self):
        auth = read_text(self.path('settlement_authority.md'))
        scope = read_text(self.path('scope_rules.md'))
        prec = read_text(self.path('field_precedence.html'))
        rmeth = pdf_text(self.path('rate_methodology.pdf'))
        annex = pdf_text(self.path('audit_annex.pdf'))
        draft = read_text(self.path('control_totals_draft.html'))

        # codec glossary first (a document may list codecs the shipped table does not)
        self.glossary = collections.OrderedDict()
        for cap, hdr, rows in md_text_tables(auth):
            if cap == 'Codec glossary':
                for r in rows:
                    if len(r) == len(hdr):
                        self.glossary[r[0]] = r[1]
        for name, kind in self.glossary.items():
            if name not in CODEC_KIND:
                CODEC_KIND[name] = kind

        # conventions / aliases / sentinels from every document
        self.conventions = collections.defaultdict(dict)
        self.aliases = collections.defaultdict(dict)
        self.sentinels = {}
        self._collect_md(auth)
        self._collect_md(scope)
        self._collect_html(prec)
        for name in ('errata_register.docx', 'amendment_minutes.docx'):
            if self.exists(name):
                self._collect_docx(self.path(name))
        for name in ('audit_annex.pdf', 'rate_methodology.pdf'):
            if self.exists(name):
                self._collect_pdf(self.path(name))

        auth_tables = md_text_tables(auth)
        scope_tables = md_text_tables(scope)
        prec_tables = html_text_tables(prec)
        rm_tables = pdf_tables_for(self.path('rate_methodology.pdf'))
        annex_tables = pdf_tables_for(self.path('audit_annex.pdf'))
        draft_tables = html_text_tables(draft)

        # runner placements
        self.placements = {}
        self.placement_rows = []
        for cap, hdr, rows in auth_tables:
            if cap.startswith('Runner placements'):
                for r in rows:
                    rec = dict(zip(hdr, r))
                    run = canon_id(rec.get('runner'))
                    rev = int(rec.get('rev'))
                    self.placements[(run, rev)] = canon_id(rec.get('region'))
                    self.placement_rows.append(rec)

        # region zones and DST rules
        self.zones = {}
        for cap, hdr, rows in auth_tables:
            if cap == 'Region zones':
                for r in rows:
                    rec = dict(zip(hdr, r))
                    self.zones[canon_id(rec.get('region'))] = rec.get('zone')
        self.dst_rules = {}
        for m in re.finditer(r'([A-Z]+[+-]\d+(?::\d+)?) is UTC([+-]\d+(?::\d+)?) until (\S+) and '
                             r'UTC([+-]\d+(?::\d+)?) after', rmeth):
            self.dst_rules[m.group(1)] = (parse_iso(m.group(3)),
                                          self._offset(m.group(2)),
                                          self._offset(m.group(4)))
        self.decoder = Decoder(self.zones, self.dst_rules)

        # sentinel register
        for cap, hdr, rows in auth_tables:
            if cap == 'Sentinel register':
                for r in rows:
                    rec = dict(zip(hdr, r))
                    self.sentinels[(rec.get('file'), rec.get('column'))] = rec.get('token')

        # source catalog
        self.catalog = {}
        for cap, hdr, rows in auth_tables:
            if cap == 'Source catalog':
                for r in rows:
                    rec = dict(zip(hdr, r))
                    self.catalog[rec.get('file')] = {
                        'primary': rec.get('primary table'),
                        'context': rec.get('context'),
                        'link': rec.get('context link'),
                        'control': rec.get('control column'),
                    }

        # fixed width layouts
        lay = collections.defaultdict(dict)
        for cap, hdr, rows in scope_tables:
            if cap == 'Fixed-width layouts':
                for r in rows:
                    rec = dict(zip(hdr, r))
                    lay[rec.get('file')].setdefault(rec.get('layout'), []).append(
                        (int(rec.get('position')), rec.get('column'), int(rec.get('width'))))
        self.layouts = {k: {lid: sorted(v) for lid, v in d.items()} for k, d in lay.items()}

        # target scope register
        self.scope = {}
        for cap, hdr, rows in scope_tables:
            if cap.startswith('Target scope register'):
                for r in rows:
                    rec = dict(zip(hdr, r))
                    self.scope[canon_id(rec.get('target'))] = rec.get('scope')

        # toolchain releases
        self.releases = []
        for cap, hdr, rows in scope_tables:
            if cap == 'Toolchain releases':
                for r in rows:
                    rec = dict(zip(hdr, r))
                    self.releases.append({
                        'toolchain': canon_id(rec.get('toolchain')),
                        'version': rec.get('version'),
                        'released_at': self.decoder.timestamp(rec.get('released_at'), 'iso_z'),
                        'yanked_at': (None if rec.get('yanked_at') in (None, '', 'never')
                                      else self.decoder.timestamp(rec.get('yanked_at'), 'iso_z')),
                    })

        # job register
        self.jobs = {}
        for cap, hdr, rows in prec_tables:
            if cap.startswith('Job register'):
                for r in rows:
                    rec = dict(zip(hdr, r))
                    key = canon_id(rec.get('job'))
                    self.jobs[key] = {
                        'target': canon_id(rec.get('target')),
                        'submitter': canon_id(rec.get('submitter')),
                        'opened_raw': rec.get('opened'),
                        'batch': rec.get('batch'),
                    }

        # cost center merges
        self.merges = []
        for cap, hdr, rows in prec_tables:
            if cap == 'Cost center merges':
                for r in rows:
                    rec = dict(zip(hdr, r))
                    self.merges.append((canon_id(rec.get('cost_center')),
                                        canon_id(rec.get('successor')),
                                        parse_iso(rec.get('effective_at'))))

        # billing granularity and classes
        self.granularity = {}
        self.classes = {}
        for cap, hdr, rows in rm_tables:
            if cap.startswith('Billing granularity'):
                for r in rows:
                    rec = dict(zip(hdr, r))
                    self.granularity[canon_id(rec.get('sku'))] = int(rec.get('granularity_s'))
            elif cap == 'Billing classes':
                for r in rows:
                    rec = dict(zip(hdr, r))
                    self.classes[canon_id(rec.get('class'))] = int(rec.get('multiplier_permille'))

        # published controls and the late void list
        self.controls = collections.OrderedDict()
        for cap, hdr, rows in annex_tables:
            if cap.startswith('Block controls'):
                for r in rows:
                    rec = dict(zip(hdr, r))
                    cid = rec.get('control_id')
                    if not cid:
                        continue
                    if cid in self.controls:
                        continue
                    self.controls[cid] = {
                        'file': rec.get('file'),
                        'block': int(rec.get('block')),
                        'records_raw': rec.get('records'),
                        'sum_raw': rec.get('control_sum'),
                        'batch': rec.get('batch'),
                        'status': rec.get('status'),
                        'source': 'audit_annex.pdf',
                    }
        for cap, hdr, rows in draft_tables:
            if cap.startswith('Draft controls'):
                for r in rows:
                    rec = dict(zip(hdr, r))
                    cid = rec.get('control_id')
                    if rec.get('file') != 'audit_annex.pdf' or cid in self.controls:
                        continue
                    self.controls[cid] = {
                        'file': rec.get('file'),
                        'block': int(rec.get('block')),
                        'records_raw': rec.get('records'),
                        'sum_raw': rec.get('control_sum'),
                        'batch': rec.get('batch'),
                        'status': 'final',
                        'source': 'control_totals_draft.html',
                    }
        self.late_voids = set()
        for cap, hdr, rows in draft_tables:
            if cap == 'Late voids':
                for r in rows:
                    rec = dict(zip(hdr, r))
                    self.late_voids.add(canon_id(rec.get('posting')))

        # close parameters
        scalars, arrays = toml_lite(self.path('close_parameters.toml'))
        self.params = scalars
        self.reservations = arrays.get('reservation', [])
        self.period_start = parse_iso(scalars['period_start'])
        self.period_end = parse_iso(scalars['period_end'])
        self.cutoff = parse_iso(scalars['knowledge_cutoff'])

    @staticmethod
    def _offset(s):
        m = re.fullmatch(r'([+-])(\d+)(?::(\d+))?', s)
        off = int(m.group(2)) * 3600 + int(m.group(3) or 0) * 60
        return -off if m.group(1) == '-' else off

    # -- convention collectors -------------------------------------------
    def _collect_md(self, text):
        for cap, hdr, rows in md_text_tables(text):
            self._absorb(cap, hdr, rows)

    def _collect_html(self, text):
        for cap, hdr, rows in html_text_tables(text):
            self._absorb(cap, hdr, rows)

    def _collect_docx(self, path):
        for cap, hdr, rows in docx_text_tables(path):
            self._absorb(cap, hdr, rows)

    def _collect_pdf(self, path):
        for cap, hdr, rows in pdf_tables_for(path):
            self._absorb(cap, hdr, rows)

    def _absorb(self, cap, hdr, rows):
        if cap.startswith('Field conventions'):
            for r in rows:
                if len(r) == len(hdr) and hdr[:2] == ['file', 'column']:
                    self.conventions[(r[0], r[1])][r[3]] = r[4]
        elif cap.startswith('Column aliases'):
            for r in rows:
                if len(r) == len(hdr) and hdr[:2] == ['file', 'alias']:
                    self.aliases[r[0]][r[1]] = r[2]

    # -- codecs ----------------------------------------------------------
    def codec(self, fname, column, ctx):
        """The codec in force for one field; the context value may carry padding or case."""
        entry = self.conventions.get((fname, column))
        if not entry or ctx is None:
            return None
        if ctx in entry:
            return entry[ctx]
        base = str(ctx).strip()
        for cand in (base, base.upper(), base.lower()):
            if cand in entry:
                return entry[cand]
        return None

    def default_codec(self, kind=None):
        """The first codec of the column's kind in the glossary."""
        if kind in CODEC_KIND:
            return kind
        for name, k in CODEC_KIND.items():
            if k == kind:
                return name
        return None

    def zone_of(self, runner):
        region = self.placements.get((canon_id(runner), 1))
        return self.zones.get(region)

    def region_of(self, runner):
        return self.placements.get((canon_id(runner), 1))

    def decode(self, fname, column, ctx, raw, zone=None):
        """Decode one field of one record honouring the published codec."""
        if raw is None:
            return None
        token = self.sentinels.get((fname, column))
        if token is not None and str(raw).strip() == token:
            return None
        codec = self.codec(fname, column, ctx)
        return self.decoder.value(raw, codec, zone)

    def decode_or_default(self, fname, column, ctx, raw, kind, zone=None):
        if raw is None:
            return None
        token = self.sentinels.get((fname, column))
        if token is not None and str(raw).strip() == token:
            return None
        codec = self.codec(fname, column, ctx)
        if codec is None:
            codec = self.default_codec(kind)
        return self.decoder.value(raw, codec, zone)

# ---------------------------------------------------------------- corpus



class Table:
    """One file's primary table: raw data rows plus their canonical control values."""

    def __init__(self, name):
        self.name = name
        self.rows = []        # raw data rows in file order, keys alias-normalised
        self.keys = []        # raw field tuples, for re-export detection
        self.controls = []    # canonical control value of each row (same length)
        self._first = {}

    def add(self, row, control):
        self.rows.append(row)
        self.keys.append(tuple(sorted((k, _keyval(v)) for k, v in row.items())))
        self.controls.append(control)

    def first_index(self, i):
        key = self.keys[i]
        if key not in self._first:
            self._first[key] = i
        return self._first[key]

    def records(self):
        """The distinct records of the file in file order (re-exports collapse)."""
        return [self.rows[i] for i in range(len(self.rows)) if self.first_index(i) == i]

    def blocks(self, size=50):
        """Yield (block_no, record_count, control_sum) for the annex block controls."""
        for start in range(0, len(self.rows), size):
            count = 0
            total = 0
            for i in range(start, min(start + size, len(self.rows))):
                if self.first_index(i) == i:
                    count += 1
                    value = self.controls[i]
                    if isinstance(value, int):
                        total += value
            yield start // size + 1, count, total


class Corpus:
    """Every export of the close, decoded under the published conventions."""

    def __init__(self, reg):
        self.reg = reg
        self.tables = {}
        self.packages = {}
        self.lang_of_target = {}
        self.lang_of_job = {}
        self.lang_of_action = {}
        self.lang_of_artifact = {}
        self.lang_of_prefix = {}
        self.job_of_attempt = {}
        self.runner_of_attempt = {}
        self.roster = []
        self.transfers = []
        self.vendor_locale = {}
        self.actions = {}
        self.artifact_target = {}
        self.revisions = []
        self.sku_region = {}
        self.erratum_attempt = {}
        self.invoice_lines = {}
        self._teams = {}
        self._load_context()
        self._load_tables()

    # ------------------------------------------------------------------ utils
    def alias(self, fname, key):
        return self.reg.aliases.get(fname, {}).get(key, key)

    def normalise(self, fname, rec):
        return {self.alias(fname, k): v for k, v in rec.items()}

    def path(self, name):
        return self.reg.path(name)

    # ------------------------------------------------------------- context
    def _load_context(self):
        reg = self.reg
        for attrs in xml_elements(self.path('package_metadata.xml'), 'Package'):
            tgt = canon_id(attrs.get('target'))
            self.packages[tgt] = {
                'language': canon_id(attrs.get('language')),
                'toolchain': canon_id(attrs.get('toolchain')),
            }
            self.lang_of_target[tgt] = canon_id(attrs.get('language'))
        for job, info in reg.jobs.items():
            self.lang_of_job[job] = self.lang_of_target.get(info['target'])

        # roster and transfers
        for name, hdr, rows in xlsx_tables(self.path('team_roster.xlsx')):
            if name.startswith('Roster'):
                for r in rows:
                    rec = self.normalise('team_roster.xlsx', dict(zip(hdr, r)))
                    self.roster.append({
                        'handle': canon_id(rec.get('handle')),
                        'team': canon_id(rec.get('team')),
                        'effective_from': rec.get('effective_from'),
                        'batch': rec.get('batch'),
                    })
            elif name.startswith('Transfers'):
                for r in rows:
                    rec = dict(zip(hdr, r))
                    self.transfers.append({
                        'handle': canon_id(rec.get('handle')),
                        'team': canon_id(rec.get('team')),
                        'effective_from': rec.get('effective_from'),
                    })

        for attrs in xml_elements(self.path('vendor_statement.xml'), 'Line'):
            self.vendor_locale[canon_id(attrs.get('vendor'))] = canon_id(attrs.get('locale'))

        # fleet policy revisions
        for sec in ini_sections(self.path('fleet_policy.ini')):
            sec = self.normalise('fleet_policy.ini', sec)
            self.revisions.append(sec)
            sku = canon_id(sec.get('sku'))
            region = reg.region_of(canon_id(sec.get('runner')))
            if sku and region and sku not in self.sku_region:
                self.sku_region[sku] = region

        # action keys
        for line in self.log_lines(self.path('action_keys.lock')):
            row = self.kv_row(line)
            row = self.normalise('action_keys.lock', row)
            aid = canon_id(row.get('action'))
            tgt = canon_id(row.get('target'))
            self.actions[aid] = tgt
            if aid:
                self.lang_of_action[aid] = self.lang_of_target.get(tgt)
                self.lang_of_prefix[aid[:6]] = self.lang_of_target.get(tgt)

        # artifacts
        for name, cols, rows in sqlite_tables(self.path('artifact_registry.db')):
            for r in rows:
                rec = self.normalise('artifact_registry.db', dict(zip(cols, r)))
                aid = canon_id(rec.get('artifact'))
                tgt = canon_id(rec.get('target'))
                self.artifact_target[aid] = tgt
                self.lang_of_artifact[aid] = self.lang_of_target.get(tgt)

        # errata register: erratum -> attempt
        for cap, hdr, rows in docx_text_tables(self.path('errata_register.docx')):
            if cap.startswith('Errata'):
                for r in rows:
                    rec = dict(zip(hdr, r))
                    self.erratum_attempt[rec.get('id')] = canon_id(rec.get('attempt'))

        # invoice lines (for the locale context of restatements)
        for name, hdr, rows in xlsx_tables(self.path('invoice_lines.xlsx')):
            if name.startswith('Lines'):
                for r in rows:
                    rec = self.normalise('invoice_lines.xlsx', dict(zip(hdr, r)))
                    self.invoice_lines[canon_id(rec.get('line_id'))] = rec

        # attempts: attempt -> job (all four attempt sources)
        for name in ATTEMPT_SOURCES:
            acol, jcol = ATTEMPT_COLUMNS[name]
            for row in self.attempt_rows(name):
                aid = canon_id(row.get(acol))
                job = canon_id(row.get(jcol))
                if aid and job:
                    self.job_of_attempt[aid] = job
                if aid:
                    self.runner_of_attempt[aid] = canon_id(row.get('runner'))

    @staticmethod
    def log_lines(path):
        out = []
        for line in read_text(path).split('\n'):
            s = line.strip()
            if not s or s.startswith('#') or s.startswith(';'):
                continue
            out.append(s)
        return out

    @staticmethod
    def kv_row(line):
        row = {}
        for m in re.finditer(r'(?:^|\s)([A-Za-z_0-9]+)=(?:"([^"]*)"|(\S+))', line):
            row[m.group(1)] = m.group(2) if m.group(2) is not None else m.group(3)
        return row

    def attempt_rows(self, name):
        """Raw attempt rows of one attempt source, with alias-normalised keys."""
        out = []
        if name in ('fleet_north.log', 'fleet_south.log'):
            for line in self.log_lines(self.path(name)):
                raw = self.kv_row(line)
                row = self.normalise(name, raw)
                out.append(row)
        else:
            for raw in jsonl_records(self.path(name)):
                out.append(self.normalise(name, raw))
        return out

    def lang_of_attempt(self, attempt):
        job = self.job_of_attempt.get(canon_id(attempt))
        if job is None:
            job = self.job_of_erratum_attempt(canon_id(attempt))
        return self.lang_of_job.get(job)

    def job_of_erratum_attempt(self, attempt):
        for eid, att in self.erratum_attempt.items():
            if att == canon_id(attempt):
                return self.job_of_attempt.get(canon_id(attempt))
        return None

    def org_of_handle(self, handle):
        team = self.team_of_handle(handle)
        return team.split('-')[0] if team else None

    def team_of_handle(self, handle):
        key = canon_id(handle)
        if key in self._teams:
            return self._teams[key]
        team = None
        for r in self.roster:
            if r['handle'] == key:
                team = r['team']
                break
        self._teams[key] = team
        return team

    def locale_of_line(self, line_id):
        rec = self.invoice_lines.get(canon_id(line_id))
        if not rec:
            return None
        return self.vendor_locale.get(canon_id(rec.get('vendor')))

    # ------------------------------------------------------------- decoding
    def ctx_for(self, name, rec):
        """The context value of one row of one file, following the source catalog."""
        entry = self.reg.catalog.get(name) or {}
        kind = entry.get('context')
        if kind == 'batch':
            return rec.get('batch') or rec.get('context')
        if kind == 'lang':
            link = entry.get('link') or ''
            if link.startswith('job'):
                return self.lang_of_job.get(canon_id(rec.get('job') or rec.get('job_id')))
            if link.startswith('attempt'):
                return self.lang_of_attempt(rec.get('attempt') or rec.get('attempt_id'))
            if link.startswith('erratum'):
                return self.lang_of_attempt(self.erratum_attempt.get(rec.get('erratum')))
            if link.startswith('action'):
                return self.lang_of_action.get(canon_id(rec.get('action')))
            if link.startswith('artifact'):
                return self.lang_of_artifact.get(canon_id(rec.get('artifact')))
            if link.startswith('prefix'):
                prefix = canon_id(rec.get('prefix'))
                return self.lang_of_prefix.get(prefix[:6] if prefix else '')
            for col in ('target', 'child'):
                if rec.get(col):
                    return self.lang_of_target.get(canon_id(rec.get(col)))
            return None
        if kind == 'region':
            link = entry.get('link') or ''
            if link.startswith('region'):
                return canon_id(rec.get('region'))
            if link.startswith('sku'):
                return self.sku_region.get(canon_id(rec.get('sku')))
            return self.reg.region_of(canon_id(rec.get('runner')))
        if kind == 'org':
            return self.org_of_handle(rec.get('handle'))
        if kind == 'locale':
            link = entry.get('link') or ''
            if link.startswith('batch'):
                return self.locale_of_line(rec.get('line_id'))
            return self.vendor_locale.get(canon_id(rec.get('vendor')))
        return None

    def zone_for(self, name, rec):
        """The clock zone of the runner the row is about."""
        entry = self.reg.catalog.get(name) or {}
        if entry.get('context') == 'region':
            region = self.ctx_for(name, rec)
            return self.reg.zones.get(region) if region else None
        runner = canon_id(rec.get('runner'))
        if runner:
            return self.reg.zone_of(runner)
        attempt = None
        link = entry.get('link') or ''
        if link.startswith('attempt'):
            attempt = canon_id(rec.get('attempt') or rec.get('attempt_id'))
        elif link.startswith('erratum'):
            attempt = self.erratum_attempt.get(rec.get('erratum'))
        if attempt:
            return self.reg.zone_of(self.runner_of_attempt.get(attempt))
        return None

    def decode(self, name, column, rec, ctx, raw, zone=None):
        return self.reg.decode(name, column, ctx, raw, zone)

    def control_value(self, name, rec, ctx, zone):
        col = (self.reg.catalog.get(name) or {}).get('control')
        if col is None:
            return None
        raw = rec.get(col)
        kind = CODEC_KIND.get(self.reg.codec(name, col, ctx), '')
        if not kind:
            kind = self.column_kind(name, col)
        return self.reg.decode_or_default(name, col, ctx, raw, kind, zone)

    def column_kind(self, name, column):
        """The kind of a column that no convention table lists."""
        hint = {'ts': 'timestamp', 'at': 'timestamp', 'from': 'timestamp', 'until': 'timestamp',
                'filed': 'timestamp', 'day': 'timestamp', 'pinned_at': 'timestamp',
                'observed': 'timestamp', 'recorded': 'timestamp', 'reviewed': 'integer',
                'seq': 'integer', 'rev': 'integer', 'shard': 'integer',
                'duration_ms': 'duration', 'elapsed': 'duration', 'time': 'duration',
                'mono_end': 'duration', 'mono_start': 'duration', 'skew_ms': 'duration',
                'budget': 'integer', 'size': 'integer', 'bytes': 'integer',
                'amount': 'money', 'billed': 'money', 'credit': 'money',
                'restated': 'money', 'micro_per_min': 'money',
                'granularity_s': 'integer', 'multiplier_permille': 'integer',
                'records': 'integer', 'control_sum': 'integer',
                'manifest_bytes': 'integer', 'effective': 'timestamp',
                'declared_at': 'timestamp', 'registered_at': 'timestamp',
                'listed_at': 'timestamp', 'assigned_at': 'timestamp',
                'resolved_at': 'timestamp', 'effective_from': 'timestamp',
                'posted_at': 'timestamp', 'opened': 'timestamp', 'ratified_on': 'timestamp',
                'decided_at': 'timestamp', 'window_from': 'timestamp',
                'window_to': 'timestamp', 'dtstart': 'timestamp', 'dtend': 'timestamp'}
        return hint.get(column, 'identifier')

    # ------------------------------------------------------------- loaders
    def _load_tables(self):
        reg = self.reg
        for name in sorted(reg.catalog):
            if not os.path.exists(self.path(name)):
                continue
            loader = getattr(self, 'load_' + re.sub(r'\W', '_', name), None)
            if loader is None:
                continue
            table = Table(name)
            loader(table)
            self.tables[name] = table

    def _finish(self, name, table, rows):
        """Compute the context, zone and canonical control value of each row."""
        for rec in rows:
            ctx = self.ctx_for(name, rec)
            zone = self.zone_for(name, rec)
            table.add(rec, self.control_value(name, rec, ctx, zone))

    def _add(self, name, table, rows):
        self._finish(name, table, rows)

    # --- simple text logs (key=value) -----------------------------------
    def load_action_keys_lock(self, table):
        rows = [self.normalise('action_keys.lock', self.kv_row(l))
                for l in self.log_lines(self.path('action_keys.lock'))]
        self._add('action_keys.lock', table, rows)

    def load_evictions_log(self, table):
        rows = [self.normalise('evictions.log', self.kv_row(l))
                for l in self.log_lines(self.path('evictions.log'))]
        self._add('evictions.log', table, rows)

    def load_usage_export_legacy_log(self, table):
        rows = [self.normalise('usage_export_legacy.log', self.kv_row(l))
                for l in self.log_lines(self.path('usage_export_legacy.log'))]
        self._add('usage_export_legacy.log', table, rows)

    def load_fleet_north_log(self, table):
        rows = [self.normalise('fleet_north.log', self.kv_row(l))
                for l in self.log_lines(self.path('fleet_north.log'))]
        self._add('fleet_north.log', table, rows)

    def load_fleet_south_log(self, table):
        rows = [self.normalise('fleet_south.log', self.kv_row(l))
                for l in self.log_lines(self.path('fleet_south.log'))]
        self._add('fleet_south.log', table, rows)

    # --- jsonl -----------------------------------------------------------
    def _jsonl_rows(self, name, gz=False):
        raws = jsonl_records(self.path(name), gz)
        return [self.normalise(name, r) for r in raws]

    def load_attempt_events_jsonl(self, table):
        self._add('attempt_events.jsonl', table, self._jsonl_rows('attempt_events.jsonl'))

    def load_attempt_events_v3_jsonl(self, table):
        self._add('attempt_events_v3.jsonl', table, self._jsonl_rows('attempt_events_v3.jsonl'))

    def load_usage_events_jsonl(self, table):
        self._add('usage_events.jsonl', table, self._jsonl_rows('usage_events.jsonl'))

    def load_lookups_shard1_jsonl(self, table):
        self._add('lookups_shard1.jsonl', table, self._jsonl_rows('lookups_shard1.jsonl'))

    def load_lookups_shard2_jsonl(self, table):
        self._add('lookups_shard2.jsonl', table, self._jsonl_rows('lookups_shard2.jsonl'))

    def load_lookups_shard3_jsonl_gz(self, table):
        self._add('lookups_shard3.jsonl.gz', table,
                  self._jsonl_rows('lookups_shard3.jsonl.gz', gz=True))

    def load_lookups_archive_jsonl_gz(self, table):
        self._add('lookups_archive.jsonl.gz', table,
                  self._jsonl_rows('lookups_archive.jsonl.gz', gz=True))

    def load_env_allowlist_json(self, table):
        doc = json.loads(read_text(self.path('env_allowlist.json')))
        rows = [self.normalise('env_allowlist.json', r) for r in doc.get('observations', [])]
        self.allowed_env = [a.get('variable') for a in doc.get('allowed', [])]
        self._add('env_allowlist.json', table, rows)

    def load_opening_balances_json(self, table):
        doc = json.loads(read_text(self.path('opening_balances.json')))
        rows = [self.normalise('opening_balances.json', r) for r in doc.get('balances', [])]
        self._add('opening_balances.json', table, rows)

    def load_toolchain_pins_resolved_json(self, table):
        doc = json.loads(read_text(self.path('toolchain_pins_resolved.json')))
        rows = [self.normalise('toolchain_pins_resolved.json', r)
                for r in doc.get('resolved', [])]
        self.digests = [self.normalise('toolchain_pins_resolved.json', d)
                        for d in doc.get('digests', [])]
        self._add('toolchain_pins_resolved.json', table, rows)

    # --- csv / tsv -------------------------------------------------------
    def _csv_rows(self, name):
        return [self.normalise(name, r) for r in csv_rows(self.path(name))]

    def load_cost_centers_csv(self, table):
        self._add('cost_centers.csv', table, self._csv_rows('cost_centers.csv'))

    def load_edges_csv(self, table):
        self._add('edges.csv', table, self._csv_rows('edges.csv'))

    def load_gc_events_csv(self, table):
        self._add('gc_events.csv', table, self._csv_rows('gc_events.csv'))

    def load_instance_classes_csv(self, table):
        self._add('instance_classes.csv', table, self._csv_rows('instance_classes.csv'))

    def load_invoice_restatement_csv(self, table):
        self._add('invoice_restatement.csv', table, self._csv_rows('invoice_restatement.csv'))

    def load_targets_csv(self, table):
        self._add('targets.csv', table, self._csv_rows('targets.csv'))

    def load_shard_index_tsv(self, table):
        self._add('shard_index.tsv', table, self._csv_rows('shard_index.tsv'))

    def load_input_manifests_tsv(self, table):
        self._add('input_manifests.tsv', table, self._csv_rows('input_manifests.tsv'))

    def load_flaky_windows_tsv(self, table):
        self._add('flaky_windows.tsv', table, self._csv_rows('flaky_windows.tsv'))

    def load_ownership_patterns_approved_tsv(self, table):
        self._add('ownership_patterns_approved.tsv', table,
                  self._csv_rows('ownership_patterns_approved.tsv'))

    # --- fixed width -----------------------------------------------------
    def _fixed_rows(self, name):
        return [self.normalise(name, r)
                for r in fixed_width_records(self.path(name), self.reg.layouts.get(name, {}))]

    def load_clock_sync_txt(self, table):
        self._add('clock_sync.txt', table, self._fixed_rows('clock_sync.txt'))

    def load_owners_registry_txt(self, table):
        self._add('owners_registry.txt', table, self._fixed_rows('owners_registry.txt'))

    # --- xml -------------------------------------------------------------
    def load_package_metadata_xml(self, table):
        rows = [self.normalise('package_metadata.xml', a)
                for a in xml_elements(self.path('package_metadata.xml'), 'Package')]
        self._add('package_metadata.xml', table, rows)

    def load_junit_results_xml(self, table):
        rows = [self.normalise('junit_results.xml', a)
                for a in xml_elements(self.path('junit_results.xml'), 'testcase')]
        self._add('junit_results.xml', table, rows)

    def load_vendor_statement_xml(self, table):
        rows = [self.normalise('vendor_statement.xml', a)
                for a in xml_elements(self.path('vendor_statement.xml'), 'Line')]
        self._add('vendor_statement.xml', table, rows)

    # --- xlsx ------------------------------------------------------------
    def _xlsx_rows(self, name, prefix):
        rows = []
        for sheet, hdr, body in xlsx_tables(self.path(name)):
            if sheet.startswith(prefix):
                for r in body:
                    rows.append(self.normalise(name, dict(zip(hdr, r))))
        return rows

    def load_invoice_lines_xlsx(self, table):
        self._add('invoice_lines.xlsx', table, self._xlsx_rows('invoice_lines.xlsx', 'Lines'))

    def load_rate_card_xlsx(self, table):
        self._add('rate_card.xlsx', table, self._xlsx_rows('rate_card.xlsx', 'Rates'))

    def load_rate_card_final_xlsx(self, table):
        rows = self._xlsx_rows('rate_card_final.xlsx', 'Final rates')
        self.spot_credits = {}
        for sheet, hdr, body in xlsx_tables(self.path('rate_card_final.xlsx')):
            if sheet.startswith('Spot credits'):
                for r in body:
                    rec = dict(zip(hdr, r))
                    self.spot_credits[canon_id(rec.get('instance_class'))] = rec.get(
                        'spot_credit_permille')
        self._add('rate_card_final.xlsx', table, rows)

    def load_team_roster_xlsx(self, table):
        self._add('team_roster.xlsx', table, self._xlsx_rows('team_roster.xlsx', 'Roster'))

    # --- sqlite ----------------------------------------------------------
    def load_artifact_registry_db(self, table):
        rows = []
        for name, cols, body in sqlite_tables(self.path('artifact_registry.db')):
            for r in body:
                rows.append(self.normalise('artifact_registry.db', dict(zip(cols, r))))
        self._add('artifact_registry.db', table, rows)

    def load_settlement_ledger_db(self, table):
        rows = []
        for name, cols, body in sqlite_tables(self.path('settlement_ledger.db')):
            for r in body:
                rows.append(self.normalise('settlement_ledger.db', dict(zip(cols, r))))
        self._add('settlement_ledger.db', table, rows)

    # --- ini / toml / yaml ------------------------------------------------
    def load_fleet_policy_ini(self, table):
        rows = [self.normalise('fleet_policy.ini', s) for s in ini_sections(self.path('fleet_policy.ini'))]
        self._add('fleet_policy.ini', table, rows)

    def load_close_parameters_toml(self, table):
        scalars, arrays = toml_lite(self.path('close_parameters.toml'))
        rows = [self.normalise('close_parameters.toml', r) for r in arrays.get('reservation', [])]
        self._add('close_parameters.toml', table, rows)

    def load_retry_policy_yaml(self, table):
        doc = yaml_lite(self.path('retry_policy.yaml'))
        rows = [self.normalise('retry_policy.yaml', r) for r in doc.get('budgets', [])]
        self.preemption_grace = {r.get('fleet'): r.get('grace_s')
                                 for r in doc.get('preemption_grace', [])}
        self.policy_defaults = {r.get('key'): r.get('value') for r in doc.get('defaults', [])}
        self._add('retry_policy.yaml', table, rows)

    def load_toolchain_pins_yaml(self, table):
        doc = yaml_lite(self.path('toolchain_pins.yaml'))
        rows = [self.normalise('toolchain_pins.yaml', r) for r in doc.get('pins', [])]
        self._add('toolchain_pins.yaml', table, rows)

    # --- docx ------------------------------------------------------------
    def _docx_rows(self, name, path, prefix):
        rows = []
        for cap, hdr, body in docx_text_tables(path):
            if cap.startswith(prefix):
                for r in body:
                    rows.append(self.normalise(name, dict(zip(hdr, r))))
        return rows

    def load_errata_register_docx(self, table):
        rows = self._docx_rows('errata_register.docx', self.path('errata_register.docx'), 'Errata')
        self._add('errata_register.docx', table, rows)

    def load_amendment_minutes_docx(self, table):
        rows = self._docx_rows('amendment_minutes.docx', self.path('amendment_minutes.docx'),
                               'Amendments')
        self._add('amendment_minutes.docx', table, rows)

    # --- ics / mbox -------------------------------------------------------
    def load_change_freeze_ics(self, table):
        rows = []
        for ev in ics_events(self.path('change_freeze.ics')):
            rec = {}
            for key, value in ev.items():
                name = key[2:] if key.startswith('X-') else key
                name = name.lower().replace('-', '_')
                rec[name] = value
            rows.append(self.normalise('change_freeze.ics', rec))
        self._add('change_freeze.ics', table, rows)

    def load_approval_thread_mbox(self, table):
        rows = []
        for msg in mbox_messages(self.path('approval_thread.mbox')):
            body = {}
            for line in msg['body']:
                if ':' in line:
                    k, v = line.split(':', 1)
                    body[k.strip().lower().replace('-', '_')] = v.strip()
            rows.append(self.normalise('approval_thread.mbox', body))
        self._add('approval_thread.mbox', table, rows)

    # --- pdf / html rule documents ---------------------------------------
    def load_rate_methodology_pdf(self, table):
        rows = []
        for cap, hdr, body in pdf_tables_for(self.path('rate_methodology.pdf')):
            if cap.startswith('Billing granularity'):
                for r in body:
                    rows.append(self.normalise('rate_methodology.pdf', dict(zip(hdr, r))))
        self._add('rate_methodology.pdf', table, rows)

    def load_audit_annex_pdf(self, table):
        rows = []
        for cap, hdr, body in pdf_tables_for(self.path('audit_annex.pdf')):
            if cap.startswith('Block controls'):
                for r in body:
                    rows.append(self.normalise('audit_annex.pdf', dict(zip(hdr, r))))
        self._add('audit_annex.pdf', table, rows)

    def load_control_totals_draft_html(self, table):
        rows = []
        for cap, hdr, body in html_text_tables(read_text(self.path('control_totals_draft.html'))):
            if cap.startswith('Draft controls'):
                for r in body:
                    rows.append(self.normalise('control_totals_draft.html', dict(zip(hdr, r))))
        self._add('control_totals_draft.html', table, rows)

    def load_scope_rules_md(self, table):
        rows = []
        for cap, hdr, body in md_text_tables(read_text(self.path('scope_rules.md'))):
            if cap.startswith('Target scope register'):
                for r in body:
                    rows.append(self.normalise('scope_rules.md', dict(zip(hdr, r))))
        self._add('scope_rules.md', table, rows)

    def load_settlement_authority_md(self, table):
        rows = []
        for cap, hdr, body in md_text_tables(read_text(self.path('settlement_authority.md'))):
            if cap.startswith('Runner placements'):
                for r in body:
                    rows.append(self.normalise('settlement_authority.md', dict(zip(hdr, r))))
        self._add('settlement_authority.md', table, rows)

    def load_field_precedence_html(self, table):
        rows = []
        for cap, hdr, body in html_text_tables(read_text(self.path('field_precedence.html'))):
            if cap.startswith('Job register'):
                for r in body:
                    rows.append(self.normalise('field_precedence.html', dict(zip(hdr, r))))
        self._add('field_precedence.html', table, rows)

# ---------------------------------------------------------------- settlement


class Settlement:
    """The settlement rules applied to a decoded corpus."""

    def __init__(self, reg, cor):
        self.reg = reg
        self.cor = cor
        self._build_indexes()

    # ---------------------------------------------------------- indexes
    def _build_indexes(self):
        reg, cor = self.reg, self.cor
        self.period_start = reg.period_start
        self.period_end = reg.period_end
        self.cutoff = reg.cutoff

        # revisions of a runner, in file order
        self.revisions = collections.defaultdict(list)
        for sec in cor.revisions:
            run = canon_id(sec.get('runner'))
            region = reg.region_of(run)
            ctx = region
            eff = self._decode('fleet_policy.ini', 'effective_from', ctx, sec, 'timestamp')
            self.revisions[run].append({
                'rev': sec.get('rev'), 'sku': canon_id(sec.get('sku')),
                'effective_from': eff, 'region': region,
            })
        for run in self.revisions:
            self.revisions[run].sort(key=lambda r: (r['effective_from'], int(r['rev'] or 0)))

        # instance classes
        self.instance = {}
        for rec in cor.tables['instance_classes.csv'].records():
            sku = canon_id(rec.get('sku'))
            self.instance[sku] = {
                'instance_class': canon_id(rec.get('instance_class')),
                'arch': canon_id(rec.get('arch')),
                'spot': str(rec.get('spot')).strip().lower() == 'true',
            }
        # sku of a runner revision
        self.sku_of = {}
        for run, revs in self.revisions.items():
            for r in revs:
                self.sku_of[(run, r['rev'])] = r['sku']

        # rates from the rate card in force
        self.rates = collections.defaultdict(list)
        for rec in cor.tables['rate_card.xlsx'].records():
            region = canon_id(rec.get('region'))
            recorded = self._decode('rate_card.xlsx', 'recorded_at', region, rec, 'timestamp')
            if recorded is None or recorded > self.cutoff:
                continue
            eff = self._decode('rate_card.xlsx', 'effective_from', region, rec, 'timestamp')
            micro = self._decode('rate_card.xlsx', 'micro_per_min', region, rec, 'money')
            self.rates[(canon_id(rec.get('instance_class')), region)].append(
                (eff, recorded, micro))
        for key in self.rates:
            best = {}
            for eff, recorded, micro in self.rates[key]:
                cur = best.get(eff)
                if cur is None or (recorded, micro) >= (cur[0], cur[1]):
                    best[eff] = (recorded, micro)
            self.rates[key] = sorted((eff, v[1]) for eff, v in best.items())

        # spot credits
        self.spot_credit = {}
        for cls, permille in (cor.spot_credits or {}).items():
            try:
                self.spot_credit[cls] = int(permille)
            except (TypeError, ValueError):
                pass

        # granularity and billing classes
        self.granularity = reg.granularity
        self.classes = reg.classes

        # amendments
        self.job_class = {}
        for rec in cor.tables['amendment_minutes.docx'].records():
            job = canon_id(rec.get('job'))
            ctx = cor.lang_of_job.get(job)
            ratified = self._decode('amendment_minutes.docx', 'ratified_on', ctx, rec,
                                    'timestamp')
            if ratified is None or ratified > self.cutoff:
                continue
            cls = canon_id(rec.get('class'))
            cur = self.job_class.get(job)
            if cur is None or ratified >= cur[0]:
                self.job_class[job] = (ratified, cls)

        # errata: the latest decision at or before the cutoff
        self.erratum_status = {}
        decisions = collections.defaultdict(list)
        for rec in cor.tables['approval_thread.mbox'].records():
            eid = rec.get('erratum')
            ctx = None
            att = cor.erratum_attempt.get(eid)
            ctx = cor.lang_of_job.get(cor.job_of_attempt.get(att))
            decided = self._decode('approval_thread.mbox', 'decided_at', ctx, rec, 'timestamp')
            if decided is None or decided > self.cutoff:
                continue
            decisions[eid].append((decided, canon_id(rec.get('decision'))))
        self.errata = {}
        for rec in cor.tables['errata_register.docx'].records():
            eid = rec.get('id')
            att = canon_id(rec.get('attempt'))
            lang = cor.lang_of_job.get(cor.job_of_attempt.get(att))
            ctx = lang
            new = canon_id(rec.get('new'))
            best = None
            for decided, decision in sorted(decisions.get(eid, [])):
                best = decision
            self.errata[att] = (eid, new if best == 'approved' else None)

        # cancel origin (the mirror is the only source)
        self.cancel_origin = {}
        for rec in cor.tables['attempt_events_v3.jsonl'].records():
            aid = canon_id(rec.get('attempt_id'))
            self.cancel_origin[aid] = canon_id(rec.get('cancel_origin'))

        # revoked attempts (the legacy export is the only source of REVOKE lines)
        self.revoked = set()
        for rec in cor.tables['usage_export_legacy.log'].records():
            kind = canon_id(rec.get('kind'))
            if kind == 'revoke':
                self.revoked.add(canon_id(rec.get('attempt')))

        # drain windows: the highest SEQUENCE of each UID, CANCELLED ignored
        drains = collections.defaultdict(list)
        for rec in cor.tables['change_freeze.ics'].records():
            uid = rec.get('uid')
            drains[uid].append(rec)
        self.drains = collections.defaultdict(list)
        for uid, recs in drains.items():
            best = max(recs, key=lambda r: int(r.get('sequence') or 0))
            if canon_id(best.get('status')) == 'cancelled':
                continue
            runner = canon_id(best.get('runner'))
            zone = reg.zone_of(runner)
            start = self._decode('change_freeze.ics', 'dtstart', reg.region_of(runner), best,
                                'timestamp')
            end = self._decode('change_freeze.ics', 'dtend', reg.region_of(runner), best,
                               'timestamp')
            if start is not None and end is not None:
                self.drains[runner].append((start, end))

        # junit testcases per attempt, quarantine windows
        self.testcases = collections.defaultdict(list)
        for rec in cor.tables['junit_results.xml'].records():
            aid = canon_id(rec.get('attempt'))
            ctx = cor.lang_of_attempt(aid)
            secs = self._decode('junit_results.xml', 'time', ctx, rec, 'duration')
            self.testcases[aid].append((canon_id(rec.get('testcase')), secs))
        self.quarantine = collections.defaultdict(list)
        for rec in cor.tables['flaky_windows.tsv'].records():
            target = canon_id(rec.get('target'))
            ctx = cor.lang_of_target.get(target)
            start = self._decode('flaky_windows.tsv', 'from', ctx, rec, 'timestamp')
            until = self._decode('flaky_windows.tsv', 'until', ctx, rec, 'timestamp')
            self.quarantine[(target, canon_id(rec.get('testcase')))].append((start, until))

        # retry budgets and preemption grace
        self.budget = {}
        self.grace = {}
        for rec in cor.tables['retry_policy.yaml'].records():
            job = canon_id(rec.get('job'))
            lang = cor.lang_of_job.get(job)
            value = self._decode('retry_policy.yaml', 'budget', lang, rec, 'integer')
            if job:
                self.budget[job] = int(value)
        for key, value in (cor.preemption_grace or {}).items():
            self.grace[canon_id(key)] = int(value) if value is not None else None
        default_budget = None
        for key, value in (cor.policy_defaults or {}).items():
            if canon_id(key) == 'budget':
                default_budget = int(value)
        self.default_budget = default_budget

        # clock skew windows per runner
        self.skew = collections.defaultdict(list)
        for rec in cor.tables['clock_sync.txt'].records():
            run = canon_id(rec.get('runner'))
            region = reg.region_of(run)
            frm = self._decode('clock_sync.txt', 'window_from', region, rec, 'timestamp')
            to = self._decode('clock_sync.txt', 'window_to', region, rec, 'timestamp')
            skew = self._decode('clock_sync.txt', 'skew_ms', region, rec, 'duration')
            if frm is not None and to is not None:
                self.skew[run].append((frm, to, skew))

        # reservations per runner and UTC day
        self.reserved_days = collections.defaultdict(set)
        for rec in cor.tables['close_parameters.toml'].records():
            run = canon_id(rec.get('runner'))
            day = self._decode('close_parameters.toml', 'day', reg.region_of(run), rec,
                               'timestamp')
            if day is not None:
                self.reserved_days[run].add(day // 86400)

        # owners registry: the last matching line by seq, indexed by path area
        self.owner_rules = []
        for rec in cor.tables['owners_registry.txt'].records():
            batch = rec.get('batch')
            seq = self._decode('owners_registry.txt', 'seq', batch, rec, 'integer')
            self.owner_rules.append((seq if seq is not None else 0, rec))
        self.owner_rules.sort(key=lambda r: r[0])
        self.owner_by_area = collections.defaultdict(list)
        self.owner_global = []
        for seq, rec in self.owner_rules:
            pattern = (rec.get('pattern') or '').strip()
            if not pattern:
                continue
            negated = pattern.startswith('!')
            pat = pattern[1:].strip() if negated else pattern
            entry = (seq, negated, self.pattern_regex(pat), canon_id(rec.get('handle')))
            m = re.match(r'//([^/*:]+)/', pat)
            if m:
                self.owner_by_area[m.group(1)].append(entry)
            else:
                self.owner_global.append(entry)
        self.owner_cache = {}

        # handle renames; those effective after the cutoff have no effect
        self.renames = {}
        self.rename_rows = collections.defaultdict(list)
        for rec in cor.tables['ownership_patterns_approved.tsv'].records():
            if canon_id(rec.get('kind')) != 'handle_rename':
                continue
            batch = rec.get('batch')
            eff = self._decode('ownership_patterns_approved.tsv', 'effective', batch, rec,
                               'timestamp')
            old = canon_id(rec.get('target'))
            new = canon_id(rec.get('handle'))
            if eff is None or old is None or new is None:
                continue
            self.rename_rows[old].append((eff, new))
            cur = self.renames.get(old)
            if cur is None or eff >= cur[0]:
                self.renames[old] = (eff, new)
        # roster and cost-center rows stay recorded under the earlier name
        self.rename_back = {}
        for old, entries in self.rename_rows.items():
            best = max(entries)
            self.rename_back[best[1]] = old

        # roster / transfers / cost centers, decoded
        self.roster_rows = collections.defaultdict(list)
        for rec in cor.roster:
            batch = rec.get('batch')
            eff = self._decode('team_roster.xlsx', 'effective_from', batch, rec, 'timestamp')
            self.roster_rows[rec['handle']].append((eff, rec['team']))
        for handle in self.roster_rows:
            self.roster_rows[handle].sort(key=lambda r: r[0])
        self.transfer_rows = collections.defaultdict(list)
        for rec in cor.transfers:
            eff = self._decode('team_roster.xlsx', 'effective_from', None, rec, 'timestamp')
            self.transfer_rows[rec['handle']].append((eff, rec['team']))
        for handle in self.transfer_rows:
            self.transfer_rows[handle].sort(key=lambda r: r[0])
        self.cost_center_rows = collections.defaultdict(list)
        for rec in cor.tables['cost_centers.csv'].records():
            handle = canon_id(rec.get('handle'))
            org = cor.org_of_handle(handle)
            eff = self._decode('cost_centers.csv', 'effective_from', org, rec, 'timestamp')
            cc = self._decode('cost_centers.csv', 'cost_center', org, rec, 'identifier')
            self.cost_center_rows[handle].append((eff, cc))
        for handle in self.cost_center_rows:
            self.cost_center_rows[handle].sort(key=lambda r: r[0])

        # cost center merges as a successor map with the effective instant
        self.merge_at = {}
        for cc, successor, eff in reg.merges:
            cur = self.merge_at.get(cc)
            if cur is None or eff >= cur[0]:
                self.merge_at[cc] = (eff, successor)

        # toolchain resolution
        self.releases = collections.defaultdict(list)
        for rel in reg.releases:
            self.releases[rel['toolchain']].append(rel)
        for tool in self.releases:
            self.releases[tool].sort(key=lambda r: r['released_at'])
        self.constraints = {}
        for rec in cor.tables['toolchain_pins.yaml'].records():
            target = canon_id(rec.get('target'))
            lang = cor.lang_of_target.get(target)
            eff = self._decode('toolchain_pins.yaml', 'pinned_at', lang, rec, 'timestamp')
            self.constraints[target] = (rec.get('constraint'), eff)
        # digests: toolchain digest -> version
        self.digest_version = {}
        for dig in (cor.digests or []):
            self.digest_version[(canon_id(dig.get('toolchain')), canon_id(dig.get('digest')))] = \
                dig.get('version')

        # shard index: prefix -> shard
        self.home_shard = {}
        for rec in cor.tables['shard_index.tsv'].records():
            prefix = canon_id(rec.get('prefix'))
            ctx = cor.lang_of_prefix.get(prefix[:6] if prefix else '')
            shard = self._decode('shard_index.tsv', 'shard', ctx, rec, 'integer')
            if prefix and shard is not None:
                self.home_shard[prefix[:6]] = shard

        # evictions: (action, shard) -> [(instant, eviction id)]
        self.evictions = collections.defaultdict(list)
        for rec in cor.tables['evictions.log'].records():
            action = canon_id(rec.get('action'))
            lang = cor.lang_of_action.get(action)
            shard = self._decode('evictions.log', 'shard', lang, rec, 'integer')
            ts = self._decode('evictions.log', 'ts', lang, rec, 'timestamp')
            ev = canon_id(rec.get('eviction'))
            if ts is not None:
                self.evictions[action].append((ts, shard, ev))

        # cache writes: action -> [(instant, )]
        self.writes = collections.defaultdict(list)
        for rec in cor.tables['lookups_archive.jsonl.gz'].records():
            if canon_id(rec.get('kind')) != 'write':
                continue
            action = canon_id(rec.get('action'))
            lang = cor.lang_of_action.get(action)
            at = self._decode('lookups_archive.jsonl.gz', 'at', lang, rec, 'timestamp')
            if at is not None:
                self.writes[action].append(at)
        for action in self.writes:
            self.writes[action].sort()

        # hermeticity inputs
        self.manifest = {}
        for rec in cor.tables['input_manifests.tsv'].records():
            action = canon_id(rec.get('action'))
            lang = cor.lang_of_action.get(action)
            declared = str(rec.get('declared')).strip().lower() == 'true'
            size = self._decode('input_manifests.tsv', 'size', lang, rec, 'integer')
            self.manifest[action] = {'declared': declared,
                                     'path': canon_id(rec.get('path')),
                                     'bytes': size}
        self.reads = {}
        for rec in cor.tables['env_allowlist.json'].records():
            action = canon_id(rec.get('action'))
            lang = cor.lang_of_action.get(action)
            at = self._decode('env_allowlist.json', 'observed', lang, rec, 'timestamp')
            reads = [canon_id(v) for v in (rec.get('reads') or [])]
            self.reads[action] = (at, reads)
        self.allowed_env = set(canon_id(v) for v in (cor.allowed_env or []) if v)

        # artifact gc events
        self.gc = collections.defaultdict(list)
        for rec in cor.tables['gc_events.csv'].records():
            artifact = canon_id(rec.get('artifact'))
            lang = cor.lang_of_artifact.get(artifact)
            at = self._decode('gc_events.csv', 'at', lang, rec, 'timestamp')
            self.gc[artifact].append((at, canon_id(rec.get('action'))))
        for artifact in self.gc:
            self.gc[artifact].sort()

        # vendor credits per invoice line
        self.credit = {}
        for rec in cor.tables['vendor_statement.xml'].records():
            line = canon_id(rec.get('line'))
            region = reg.region_of(canon_id(rec.get('runner')))
            self.credit[line] = self._decode('vendor_statement.xml', 'credit', region, rec,
                                             'money')
        # vendor locale (for the invoice restatement context)
        self.line_vendor = {}
        for line, rec in cor.invoice_lines.items():
            self.line_vendor[line] = canon_id(rec.get('vendor'))

        # invoice lines decoded
        self.invoice = {}
        for rec in cor.tables['invoice_lines.xlsx'].records():
            line = canon_id(rec.get('line_id'))
            locale = cor.vendor_locale.get(canon_id(rec.get('vendor')))
            week = self._decode('invoice_lines.xlsx', 'week_start', locale, rec, 'timestamp')
            billed = self._decode('invoice_lines.xlsx', 'billed', locale, rec, 'money')
            self.invoice[line] = {'runner': canon_id(rec.get('runner')),
                                  'week_start': week, 'billed': billed}
        self.dispute_closed = set()
        for rec in cor.tables['invoice_restatement.csv'].records():
            if canon_id(rec.get('type')) != 'dispute_closure':
                continue
            self.dispute_closed.add(canon_id(rec.get('line_id')))

        # ledger postings
        self.postings = []
        for rec in cor.tables['settlement_ledger.db'].records():
            batch = rec.get('batch')
            cc = self._decode('settlement_ledger.db', 'cost_center', batch, rec, 'identifier')
            amount = self._decode('settlement_ledger.db', 'amount', batch, rec, 'money')
            posted = self._decode('settlement_ledger.db', 'posted_at', batch, rec, 'timestamp')
            reverses = self._decode('settlement_ledger.db', 'reverses', batch, rec, 'identifier')
            self.postings.append({'posting': canon_id(rec.get('posting')), 'cost_center': cc,
                                  'amount': amount, 'posted_at': posted,
                                  'reverses': reverses or None})
        self.opening = collections.defaultdict(int)
        for rec in cor.tables['opening_balances.json'].records():
            batch = rec.get('batch')
            cc = self._decode('opening_balances.json', 'cost_center', batch, rec, 'identifier')
            amount = self._decode('opening_balances.json', 'amount', batch, rec, 'money')
            self.opening[cc] += amount

        # scope of a target
        self.scope = reg.scope

        # targets register
        self.target_kind = {}
        for rec in cor.tables['targets.csv'].records():
            target = canon_id(rec.get('target'))
            self.target_kind[target] = canon_id(rec.get('kind'))

        # period edges
        self.last_second = self.period_end - 1

        # edges: child -> [(parent, kind)]
        self.parents = collections.defaultdict(list)
        for rec in cor.tables['edges.csv'].records():
            child = canon_id(rec.get('child'))
            lang = cor.lang_of_target.get(child)
            declared = self._decode('edges.csv', 'declared_at', lang, rec, 'timestamp')
            self.parents[child].append((canon_id(rec.get('parent')),
                                        canon_id(rec.get('kind')), declared))

    def _decode(self, name, column, ctx, rec, kind):
        raw = rec.get(column)
        if raw is None:
            return None
        token = self.reg.sentinels.get((name, column))
        if token is not None and str(raw).strip() == token:
            return None
        codec = self.reg.codec(name, column, ctx)
        if codec is None:
            codec = self.reg.default_codec(kind)
        zone = None
        if CODEC_KIND.get(codec) == 'timestamp' and codec in ('local',):
            runner = canon_id(rec.get('runner'))
            if not runner:
                runner = self.cor.runner_of_attempt.get(
                    self.cor.erratum_attempt.get(rec.get('erratum')))
            zone = self.reg.zone_of(runner) if runner else None
        return self.reg.decoder.value(raw, codec, zone)

    # ---------------------------------------------------------- helpers
    def corrected_start(self, runner, reported):
        """S-4: a reported start inside a skew window of its runner is corrected."""
        for frm, to, skew in self.skew.get(runner, ()):
            if skew and frm <= reported < to:
                return reported - skew
        return reported

    def revision_in_force(self, runner, instant):
        revs = self.revisions.get(runner)
        if not revs:
            return None
        chosen = None
        for rev in revs:
            if rev['effective_from'] is not None and rev['effective_from'] <= instant:
                chosen = rev
        return chosen

    def rate_for(self, instance_class, region, instant):
        rows = self.rates.get((instance_class, region))
        if not rows:
            return None
        chosen = None
        for eff, micro in rows:
            if eff is not None and eff <= instant:
                chosen = micro
        return chosen

    @staticmethod
    def pattern_regex(pattern):
        """* stays inside one path segment (never / or :), ** matches anything."""
        parts = pattern.split('**')
        regex = ''
        for i, part in enumerate(parts):
            if i:
                regex += '.*'
            regex += re.escape(part).replace(r'\*', '[^/:]*')
        return re.compile(regex + r'\Z')

    def owner_of_target(self, target):
        """S-13: the last matching pattern by seq; a leading ! leaves the target unowned."""
        if target in self.owner_cache:
            return self.owner_cache[target]
        area = None
        m = re.match(r'//([^/*:]+)/', target or '')
        rules = list(self.owner_global)
        if m:
            area = m.group(1)
            rules += self.owner_by_area.get(area, ())
        rules.sort(key=lambda r: r[0])
        owner = None
        for seq, negated, regex, handle in rules:
            if regex.match(target or ''):
                owner = None if negated else handle
        self.owner_cache[target] = owner
        return owner

    def team_of(self, handle, instant):
        rows = self.roster_rows.get(handle) or ()
        team = None
        for eff, value in rows:
            if eff is not None and eff <= instant:
                team = value
        for eff, value in (self.transfer_rows.get(handle) or ()):
            if eff is not None and eff <= instant:
                team = value
        return team

    def cost_center_of(self, handle, instant):
        cc = None
        for eff, value in (self.cost_center_rows.get(handle) or ()):
            if eff is not None and eff <= instant:
                cc = value
        if cc is None:
            return None
        seen = 0
        while cc in self.merge_at and seen < 32:
            eff, successor = self.merge_at[cc]
            if eff is not None and eff <= instant:
                cc = successor
                seen += 1
            else:
                break
        return cc

    def rename_of(self, handle):
        """The name a handle is reported under: a rename effective at or before the
        cutoff applies, one effective after it has no effect (S-2, S-13)."""
        entry = self.renames.get(handle)
        if entry is not None and entry[0] <= self.cutoff:
            return entry[1]
        back = self.rename_back.get(handle)
        if back is not None:
            earlier = back
            entry = self.renames.get(earlier)
            if entry is not None and entry[0] <= self.cutoff:
                return handle
            return earlier
        return handle

    def roster_handle(self, reported):
        """The name the roster and cost-center rows are recorded under."""
        return self.rename_back.get(reported, reported)

    # ---------------------------------------------------------- toolchains
    def resolve_version(self, toolchain, constraint, instant):
        """The highest version satisfying the constraint, released and not yanked."""
        if not constraint or not toolchain:
            return None
        best = None
        for rel in self.releases.get(toolchain, ()):
            if rel['released_at'] is None or rel['released_at'] > instant:
                continue
            if rel['yanked_at'] is not None and rel['yanked_at'] <= instant:
                continue
            if self.satisfies(rel['version'], constraint):
                if best is None or self.version_key(rel['version']) > self.version_key(best):
                    best = rel['version']
        return best

    @staticmethod
    def version_key(version):
        return tuple(int(p) if p.isdigit() else p for p in re.split(r'[.\-]', str(version)))

    def satisfies(self, version, constraint):
        v = [int(p) for p in re.findall(r'\d+', version)]
        c = str(constraint).strip()
        m = re.fullmatch(r'>=(\d+)\.(\d+)\.(\d+)\s*<(\d+)\.(\d+)\.(\d+)', c)
        if m:
            lo = [int(x) for x in m.group(1, 2, 3)]
            hi = [int(x) for x in m.group(4, 5, 6)]
            return lo <= v < hi
        m = re.fullmatch(r'=(\d+)\.(\d+)\.(\d+)', c)
        if m:
            return v == [int(x) for x in m.group(1, 2, 3)]
        m = re.fullmatch(r'~(\d+)\.(\d+)\.(\d+)', c)
        if m:
            lo = [int(x) for x in m.group(1, 2, 3)]
            return v >= lo and v[0] == lo[0] and v[1] == lo[1]
        m = re.fullmatch(r'\^(\d+)\.(\d+)\.(\d+)', c)
        if m:
            lo = [int(x) for x in m.group(1, 2, 3)]
            if v < lo:
                return False
            if lo[0] > 0:
                return v[0] == lo[0]
            if lo[1] > 0:
                return v[0] == 0 and v[1] == lo[1]
            return v[0] == 0 and v[1] == 0 and v[2] == lo[2]
        return False

    # ---------------------------------------------------------- attempts
    FLEET_OF = {'fleet_north.log': 'north', 'fleet_south.log': 'south',
                'attempt_events.jsonl': 'east', 'usage_events.jsonl': 'west'}

    def attempts(self):
        """One row per attempt of the four fleets, settled."""
        out = []
        for name in ATTEMPT_SOURCES:
            fleet = self.FLEET_OF[name]
            for rec in self.cor.tables[name].records():
                row = self.settle_attempt(name, fleet, rec)
                if row is not None:
                    out.append(row)
        out.sort(key=lambda r: str(r['attempt_id']))
        return out

    def settle_attempt(self, name, fleet, rec):
        cor, reg = self.cor, self.reg
        acol, jcol = ATTEMPT_COLUMNS[name]
        attempt_id = canon_id(rec.get(acol))
        job = canon_id(rec.get(jcol))
        info = reg.jobs.get(job) or {}
        target = info.get('target')
        runner = canon_id(rec.get('runner'))
        lang = cor.lang_of_job.get(job)

        # reported start and duration
        zone = cor.zone_for(name, rec)
        start_col = 'ts' if fleet in ('north', 'south') else ('started' if fleet == 'east' else 'start')
        reported = self._decode(name, start_col, lang, rec, 'timestamp')
        if fleet in ('north', 'south'):
            mono_start = self._decode(name, 'mono_start', lang, rec, 'duration')
            mono_end = self._decode(name, 'mono_end', lang, rec, 'duration')
            duration_ms = None if (mono_start is None or mono_end is None) else mono_end - mono_start
        else:
            duration_ms = self._decode(name, 'duration_ms' if fleet == 'east' else 'elapsed',
                                        lang, rec, 'duration')
        if reported is None:
            return None
        start = self.corrected_start(runner, reported)

        # runner revision in force, its region and instance class
        rev = self.revision_in_force(runner, start)
        sku = rev['sku'] if rev else None
        region = reg.placements.get((runner, int(rev['rev']))) if rev else None
        instance = self.instance.get(sku) or {}
        instance_class = instance.get('instance_class')

        # status after errata
        status = canon_id(rec.get('status') or rec.get('state'))
        entry = self.errata.get(attempt_id)
        if entry and entry[1] is not None:
            status = entry[1]

        # attempt number
        if fleet in ('north', 'south'):
            no = rec.get('no')
        elif fleet == 'east':
            no = rec.get('attempt')
        else:
            no = rec.get('seq')
        try:
            attempt_no = int(str(no).strip())
        except (TypeError, ValueError):
            attempt_no = None

        exclusion = self.exclusion_of(attempt_id, fleet, job, target, runner, start,
                                      duration_ms, status, attempt_no)
        # the rate, the class and the reservation are properties of the attempt itself
        rate = self.rate_for(instance_class, region, start)
        entry_cls = self.job_class.get(job)
        billing_class = entry_cls[1] if entry_cls else 'standard'
        reserved = (start // 86400) in self.reserved_days.get(runner, ())
        billable_seconds = 0
        cost = 0
        if exclusion is None:
            granularity = self.granularity.get(sku)
            if granularity is None:
                granularity = 1
            units = -(-duration_ms // (1000 * granularity)) if duration_ms else 0
            billable_seconds = units * granularity
            multiplier = self.classes.get(billing_class, 1000)
            num = billable_seconds * (rate or 0) * multiplier
            den = 60 * 1000
            if instance.get('spot'):
                credit = self.spot_credit.get(instance_class, 0) or 0
                num *= (1000 - credit)
                den *= 1000
            if reserved:
                num *= int(self.reg.params.get('reserved_permille', 1000) or 1000)
                den *= 1000
            cost = round_half_even(num, den)

        # attribution
        owner = self.owner_of_target(target) if target else None
        if owner is None:
            owner = info.get('submitter')
        if owner is None:
            reported_owner = None
            roster_handle = None
        else:
            reported_owner = self.rename_of(owner)
            roster_handle = self.roster_handle(reported_owner)
        team = self.team_of(roster_handle, start) if roster_handle else None
        cost_center = self.cost_center_of(roster_handle, start) if roster_handle else None

        return {
            'attempt_id': attempt_id,
            'job_id': job,
            'attempt_no': attempt_no,
            'fleet': fleet,
            'runner': runner,
            'runner_rev': int(rev['rev']) if rev and rev.get('rev') else None,
            'region': region,
            'sku': sku,
            'instance_class': instance_class,
            'target': target,
            'started_at': iso(start),
            'start_epoch': start,
            'duration_ms': duration_ms,
            'status': status,
            'exclusion': exclusion,
            'billable_seconds': billable_seconds,
            'rate_micro_per_min': rate,
            'billing_class': billing_class,
            'reserved': reserved,
            'cost_micro': cost,
            'owner_handle': reported_owner,
            'team': team,
            'cost_center': cost_center,
        }

    # ---------------------------------------------------------- exclusions
    def exclusion_of(self, attempt_id, fleet, job, target, runner, start, duration_ms,
                     status, attempt_no):
        if not (self.period_start <= start < self.period_end):
            return 'out_of_period'
        if attempt_id in self.revoked:
            return 'revoked'
        for begin, end in self.drains.get(runner, ()):
            if begin <= start < end:
                return 'provider_drain'
        if status == 'cancelled' and self.cancel_origin.get(attempt_id) == 'platform':
            return 'platform_cancel'
        if status == 'failed':
            cases = self.testcases.get(attempt_id, ())
            if cases:
                quarantined = True
                for testcase, _secs in cases:
                    windows = self.quarantine.get((target, testcase)) or ()
                    if not any(w[0] is not None and w[1] is not None and w[0] <= start <= w[1]
                               for w in windows):
                        quarantined = False
                        break
                if quarantined:
                    return 'quarantined_flake'
        if status == 'preempted':
            grace = self.grace.get(fleet)
            if grace is not None and duration_ms is not None:
                if duration_ms < grace * 1000:
                    return 'preempt_grace'
        budget = self.budget.get(job)
        if budget is None:
            budget = self.default_budget
        if attempt_no is not None and budget is not None and attempt_no > budget:
            return 'over_budget'
        if self.scope.get(target) == 'exempt':
            return 'exempt_scope'
        return None

    # ---------------------------------------------------------- lookups
    def lookups(self):
        """One row per cache lookup in the three shard logs."""
        out = []
        for shard, name in enumerate(LOOKUP_SOURCES, start=1):
            for rec in self.cor.tables[name].records():
                out.append(self.settle_lookup(shard, name, rec))
        out.sort(key=lambda r: str(r['lookup_id']))
        return out

    def settle_lookup(self, shard, name, rec):
        cor, reg = self.cor, self.reg
        lookup_id = canon_id(rec.get('lookup') or rec.get('lookup_v2'))
        action = canon_id(rec.get('action'))
        attempt = canon_id(rec.get('attempt'))
        lang = cor.lang_of_action.get(action)
        at = self._decode(name, 'at', lang, rec, 'timestamp')
        size = self._decode(name, 'bytes', lang, rec, 'integer')
        result = canon_id(rec.get('result'))
        home = self.home_shard.get(action[:6])
        outcome = None
        eviction = None
        if home is None or home != shard:
            outcome = 'replay'
        elif result == 'miss':
            outcome = 'miss'
        else:
            manifest = self.manifest.get(action) or {}
            env = self.reads.get(action)
            hermetic = manifest.get('declared') is True and (
                env is None or all(v in self.allowed_env for v in env[1]))
            if not hermetic:
                outcome = 'nonhermetic_hit'
            else:
                last_write = None
                for ts in self.writes.get(action, ()):
                    if ts is not None and ts <= at:
                        last_write = ts
                ev = None
                for ts, eshard, evid in self.evictions.get(action, ()):
                    if eshard == home and last_write is not None and last_write < ts <= at:
                        if ev is None or ts < ev[0]:
                            ev = (ts, evid)
                if ev is not None:
                    outcome = 'evicted_hit'
                    eviction = ev[1]
                else:
                    target = cor.actions.get(action)
                    written_version = self.target_version(target, last_write)
                    lookup_version = self.target_version(target, at)
                    if written_version != lookup_version:
                        outcome = 'stale_hit'
                    else:
                        outcome = 'hit'
        return {
            'lookup_id': lookup_id,
            'attempt_id': attempt,
            'action_key': action,
            'shard': shard,
            'at': iso(at),
            'bytes': size,
            'outcome': outcome,
            'eviction_id': eviction,
        }

    def target_version(self, target, instant):
        """The toolchain version resolved for a target at an instant."""
        pin = self.constraints.get(target)
        if not pin:
            return None
        constraint, _pinned_at = pin
        package = self.cor.packages.get(target) or {}
        toolchain = package.get('toolchain')
        return self.resolve_version(toolchain, constraint, instant)

    # ---------------------------------------------------------- targets
    def targets(self):
        out = []
        universe = set(self.target_kind) | set(self.cor.packages) | set(self.constraints)
        for target in universe:
            out.append(self.settle_target(target))
        out.sort(key=lambda r: str(r['target']))
        return out

    def settle_target(self, target):
        cor = self.cor
        kind = self.target_kind.get(target)
        package = cor.packages.get(target) or {}
        lang = package.get('language')
        toolchain = package.get('toolchain')
        constraint = (self.constraints.get(target) or (None, None))[0]
        open_version = self.target_version(target, self.period_start)
        close_version = self.target_version(target, self.last_second)
        invalidated = self.invalidated(target, set(), open_version, close_version)
        owner = self.owner_of_target(target)
        reported = self.rename_of(owner) if owner else None
        team = self.team_of(self.roster_handle(reported), self.last_second) if owner else None
        return {
            'target': target,
            'kind': kind,
            'language': lang,
            'toolchain': toolchain,
            'constraint': constraint,
            'version_at_open': open_version,
            'version_at_close': close_version,
            'invalidated': invalidated,
            'scope': self.scope.get(target),
            'owner_handle': reported,
            'team': team,
        }

    def invalidated(self, target, seen, open_version, close_version):
        if target in seen:
            return False
        seen.add(target)
        if open_version != close_version:
            return True
        for parent, kind, _declared in self.parents.get(target, ()):
            if kind in ('src', 'toolchain'):
                if self.invalidated(parent, seen,
                                    self.target_version(parent, self.period_start),
                                    self.target_version(parent, self.last_second)):
                    return True
        return False

    # ---------------------------------------------------------- actions
    def actions(self):
        out = []
        for rec in self.cor.tables['action_keys.lock'].records():
            action = canon_id(rec.get('action'))
            out.append(self.settle_action(rec, action))
        out.sort(key=lambda r: str(r['action_key']))
        return out

    def settle_action(self, rec, action):
        cor = self.cor
        target = canon_id(rec.get('target'))
        digest = rec.get('digest')
        if digest is not None and str(digest).strip() == self.reg.sentinels.get(
                ('action_keys.lock', 'digest')):
            digest = None
        manifest = self.manifest.get(action) or {}
        observed, reads = self.reads.get(action, (None, []))
        undeclared = [] if manifest.get('declared') else [manifest.get('path')]
        undeclared = [p for p in undeclared if p]
        disallowed = sorted(v for v in reads if v not in self.allowed_env)
        hermetic = manifest.get('declared') is True and not disallowed
        package = cor.packages.get(target) or {}
        version = self.digest_version.get((package.get('toolchain'), canon_id(digest)))
        return {
            'action_key': action,
            'target': target,
            'home_shard': self.home_shard.get(action[:6]),
            'hermetic': hermetic,
            'undeclared_inputs': sorted(undeclared),
            'input_bytes': manifest.get('bytes'),
            'disallowed_env': disallowed,
            'toolchain_version': version,
        }

    # ---------------------------------------------------------- artifacts
    def artifacts(self):
        out = []
        for rec in self.cor.tables['artifact_registry.db'].records():
            out.append(self.settle_artifact(rec))
        out.sort(key=lambda r: str(r['artifact_id']))
        return out

    def settle_artifact(self, rec):
        cor, reg = self.cor, self.reg
        artifact = canon_id(rec.get('artifact'))
        target = canon_id(rec.get('target'))
        lang = cor.lang_of_target.get(target)
        created = self._decode('artifact_registry.db', 'created', lang, rec, 'timestamp')
        size = self._decode('artifact_registry.db', 'bytes', lang, rec, 'integer')
        retained = self.retained_seconds(created, self.gc.get(artifact, ()))
        rate = int(self.reg.params.get('storage_micro_per_gib_hour') or 0)
        cost = round_half_even(size * retained * rate, 1073741824 * 3600) if size else 0
        owner = self.owner_of_target(target) if target else None
        reported = self.rename_of(owner) if owner else None
        roster_handle = self.roster_handle(reported) if owner else None
        team = self.team_of(roster_handle, self.last_second) if roster_handle else None
        cost_center = (self.cost_center_of(roster_handle, self.last_second)
                       if roster_handle else None)
        return {
            'artifact_id': artifact,
            'target': target,
            'bytes': size,
            'retained_seconds': retained,
            'storage_cost_micro': cost,
            'team': team,
            'cost_center': cost_center,
        }

    def retained_seconds(self, created, events):
        """Retention inside the period: from created until a delete, again after a restore."""
        if created is None:
            return 0
        retained = []
        open_at = created
        live = True
        for at, action in events:
            if at is None:
                continue
            if action == 'delete' and live:
                retained.append((open_at, at))
                live = False
            elif action == 'restore' and not live:
                open_at = at
                live = True
        if live:
            retained.append((open_at, self.period_end))
        total = 0
        for begin, end in retained:
            lo = max(begin, self.period_start)
            hi = min(end, self.period_end)
            if hi > lo:
                total += hi - lo
        return total

    # ---------------------------------------------------------- invoices
    def invoice_reconciliation(self, attempts):
        """One row per vendor invoice line, reconciled against the computed cost."""
        by_runner = collections.defaultdict(list)
        for attempt in attempts:
            if attempt['exclusion'] is not None:
                continue
            by_runner[attempt['runner']].append(attempt)
        weeks = sorted({row['week_start'] for row in self.invoice.values()
                        if row['week_start'] is not None})
        out = []
        for line, row in self.invoice.items():
            runner = row['runner']
            start = row['week_start']
            if start is None:
                end = self.period_end
            else:
                idx = weeks.index(start) if start in weeks else None
                end = weeks[idx + 1] if (idx is not None and idx + 1 < len(weeks)) \
                    else self.period_end
            computed = 0
            for attempt in by_runner.get(runner, ()):
                when = attempt['start_epoch']
                if start is None:
                    ok = self.period_start <= when < self.period_end
                else:
                    ok = start <= when < end
                if ok:
                    computed += attempt['cost_micro']
            billed = row['billed']
            credit = self.credit.get(line)
            if line in self.dispute_closed:
                status = 'closed'
            elif billed == computed:
                status = 'match'
            elif credit is not None and billed - credit == computed:
                status = 'credited'
            else:
                status = 'mismatch'
            week = None
            if start is not None:
                week = (start - self.period_start) // 604800
            out.append({
                'line_id': line,
                'runner': runner,
                'week': week,
                'billed_micro': billed,
                'credit_micro': credit,
                'computed_micro': computed,
                'status': status,
            })
        out.sort(key=lambda r: str(r['line_id']))
        return out

    # ---------------------------------------------------------- aggregates
    def team_chargeback(self, attempts, artifacts, lookups):
        """S-18: compute per team, storage per team, cache credit per team."""
        credit = int(self.reg.params.get('cache_credit_micro') or 0)
        teams = {}
        attempt_of = {a['attempt_id']: a for a in attempts}

        def bucket(team):
            return teams.setdefault(team, {
                'attempts_billed': 0, 'compute_micro': 0, 'storage_micro': 0,
                'cache_credit_micro': 0, 'net_micro': 0})

        for attempt in attempts:
            if attempt['team'] is None:
                continue
            entry = bucket(attempt['team'])
            if attempt['exclusion'] is None:
                entry['attempts_billed'] += 1
                entry['compute_micro'] += attempt['cost_micro']
        for artifact in artifacts:
            if artifact['team'] is None:
                continue
            bucket(artifact['team'])['storage_micro'] += artifact['storage_cost_micro']
        for lookup in lookups:
            attempt = attempt_of.get(lookup['attempt_id'])
            if attempt is None or attempt['team'] is None:
                continue
            entry = bucket(attempt['team'])
            if lookup['outcome'] == 'hit':
                entry['cache_credit_micro'] += credit
        for entry in teams.values():
            entry['net_micro'] = (entry['compute_micro'] + entry['storage_micro']
                                  - entry['cache_credit_micro'])
        return teams

    def cache_effectiveness(self, attempts, lookups):
        attempt_of = {a['attempt_id']: a for a in attempts}
        out = {}
        for lookup in lookups:
            attempt = attempt_of.get(lookup['attempt_id'])
            if attempt is None or attempt['team'] is None:
                continue
            entry = out.setdefault(attempt['team'], {
                'hit': 0, 'miss': 0, 'stale_hit': 0, 'evicted_hit': 0, 'nonhermetic_hit': 0,
                'replay': 0, 'valid_hit_permille': 0})
            entry[lookup['outcome']] += 1
        for team, entry in out.items():
            hits = entry['hit']
            total = sum(entry[k] for k in ('hit', 'miss', 'stale_hit', 'evicted_hit',
                                           'nonhermetic_hit', 'replay'))
            valid = total - entry['replay']
            entry['valid_hit_permille'] = (1000 * hits) // valid if valid else 0
        return out

    def cost_center_ledger(self, attempts, artifacts):
        """Opening plus qualifying postings plus charges, per cost center."""
        charges = collections.defaultdict(int)
        for attempt in attempts:
            if attempt['exclusion'] is None and attempt['cost_center']:
                charges[attempt['cost_center']] += attempt['cost_micro']
        for artifact in artifacts:
            if artifact['cost_center']:
                charges[artifact['cost_center']] += artifact['storage_cost_micro']

        reversed_by = set()
        for posting in self.postings:
            if posting['reverses']:
                reversed_by.add(posting['reverses'])
        late = self.reg.late_voids
        postings = collections.defaultdict(int)
        for posting in self.postings:
            if posting['posted_at'] is None:
                continue
            if not (self.period_start <= posting['posted_at'] < self.period_end):
                continue
            if posting['reverses'] or posting['posting'] in reversed_by:
                continue
            if posting['posting'] in late:
                continue
            cc = posting['cost_center']
            seen = 0
            while cc in self.merge_at and seen < 32:
                eff, successor = self.merge_at[cc]
                if eff is not None and eff <= posting['posted_at']:
                    cc = successor
                    seen += 1
                else:
                    break
            postings[cc] += posting['amount'] or 0

        ledger = {}
        for cc, amount in self.opening.items():
            ledger[cc] = {
                'opening_micro': amount,
                'postings_micro': postings.get(cc, 0),
                'charges_micro': charges.get(cc, 0),
                'closing_micro': 0,
            }
        for entry in ledger.values():
            entry['closing_micro'] = (entry['opening_micro'] + entry['postings_micro']
                                      + entry['charges_micro'])
        return ledger

    def rate_resolution(self):
        """The rate windows in force per instance class and region."""
        out = {}
        for key in sorted(self.rates, key=lambda k: (str(k[0]), str(k[1]))):
            rows = self.rates[key]
            in_force = None
            later = []
            for eff, micro in rows:
                if eff is None:
                    continue
                if eff <= self.period_start:
                    in_force = micro
                elif self.period_start < eff < self.period_end:
                    later.append((eff, micro))
            if in_force is None and not later:
                continue
            windows = []
            if in_force is not None:
                windows.append([self.period_start, in_force])
            windows.extend([eff, micro] for eff, micro in sorted(later))
            out['%s|%s' % key] = windows
        return out

    def control_reconciliation(self):
        """Every published block control against my recomputation."""
        out = {}
        for cid, ctl in self.reg.controls.items():
            table = self.cor.tables.get(ctl['file'])
            records = None
            total = None
            if table is not None:
                for blk, count, value in table.blocks():
                    if blk == ctl['block']:
                        records = count
                        total = value
                        break
            src = ctl.get('source', 'audit_annex.pdf')
            recs_codec = self.reg.codec(src, 'records', ctl['batch'])
            sum_codec = self.reg.codec(src, 'control_sum', ctl['batch'])
            try:
                expected_records = self.reg.decoder.integer(ctl['records_raw'],
                                                            recs_codec or 'plain')
            except (TypeError, ValueError):
                expected_records = None
            try:
                expected_sum = self.reg.decoder.integer(ctl['sum_raw'], sum_codec or 'plain')
            except (TypeError, ValueError):
                expected_sum = None
            match = (records == expected_records and total == expected_sum)
            out[cid] = {
                'file': ctl['file'],
                'block': ctl['block'],
                'expected_records': expected_records,
                'expected_sum': expected_sum,
                'records': records,
                'sum': total,
                'match': match,
            }
        return out

    def source_audit(self):
        """Distinct record counts per input file."""
        out = {}
        for name in sorted(self.cor.tables):
            out[name] = {'records': len(self.cor.tables[name].records())}
        return out

    def close_summary(self, attempts, artifacts, lookups, invoices, controls, ledger):
        compute = sum(a['cost_micro'] for a in attempts if a['exclusion'] is None)
        storage = sum(a['storage_cost_micro'] for a in artifacts)
        credit = 0
        unit = int(self.reg.params.get('cache_credit_micro') or 0)
        attempt_of = {a['attempt_id']: a for a in attempts}
        for lookup in lookups:
            if lookup['outcome'] != 'hit':
                continue
            attempt = attempt_of.get(lookup['attempt_id'])
            if attempt is not None and attempt['team'] is not None:
                credit += unit
        return {
            'attempts_listed': len(attempts),
            'attempts_billed': sum(1 for a in attempts if a['exclusion'] is None),
            'compute_micro': compute,
            'storage_micro': storage,
            'cache_credit_micro': credit,
            'net_micro': compute + storage - credit,
            'invoice_mismatches': sum(1 for row in invoices if row['status'] == 'mismatch'),
            'controls_mismatched': sum(1 for row in controls.values() if not row['match']),
            'closing_micro': sum(entry['closing_micro'] for entry in ledger.values()),
        }


# ---------------------------------------------------------------- writing

ATTEMPT_KEYS = ('attempt_id', 'job_id', 'attempt_no', 'fleet', 'runner', 'runner_rev',
                'region', 'sku', 'instance_class', 'target', 'started_at', 'duration_ms',
                'status', 'exclusion', 'billable_seconds', 'rate_micro_per_min',
                'billing_class', 'reserved', 'cost_micro', 'owner_handle', 'team',
                'cost_center')
LOOKUP_KEYS = ('lookup_id', 'attempt_id', 'action_key', 'shard', 'at', 'bytes', 'outcome',
               'eviction_id')
TARGET_KEYS = ('target', 'kind', 'language', 'toolchain', 'constraint', 'version_at_open',
               'version_at_close', 'invalidated', 'scope', 'owner_handle', 'team')
ACTION_KEYS = ('action_key', 'target', 'home_shard', 'hermetic', 'undeclared_inputs',
               'input_bytes', 'disallowed_env', 'toolchain_version')
ARTIFACT_KEYS = ('artifact_id', 'target', 'bytes', 'retained_seconds', 'storage_cost_micro',
                 'team', 'cost_center')
INVOICE_KEYS = ('line_id', 'runner', 'week', 'billed_micro', 'credit_micro', 'computed_micro',
                'status')


def project(row, keys):
    return {k: row.get(k) for k in keys}


def write_jsonl(path, rows, keys):
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        for row in rows:
            fh.write(json.dumps(project(row, keys), sort_keys=True, separators=(',', ':')))
            fh.write('\n')


def write_json(path, obj):
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(obj, fh, sort_keys=True, separators=(',', ':'))
        fh.write('\n')


def run(data_dir, out_dir):
    reg = Registry(data_dir)
    cor = Corpus(reg)
    settle = Settlement(reg, cor)

    attempts = settle.attempts()
    lookups = settle.lookups()
    targets = settle.targets()
    actions = settle.actions()
    artifacts = settle.artifacts()
    invoices = settle.invoice_reconciliation(attempts)

    os.makedirs(out_dir, exist_ok=True)
    write_jsonl(os.path.join(out_dir, 'attempts.jsonl'), attempts, ATTEMPT_KEYS)
    write_jsonl(os.path.join(out_dir, 'lookups.jsonl'), lookups, LOOKUP_KEYS)
    write_jsonl(os.path.join(out_dir, 'targets.jsonl'), targets, TARGET_KEYS)
    write_jsonl(os.path.join(out_dir, 'actions.jsonl'), actions, ACTION_KEYS)
    write_jsonl(os.path.join(out_dir, 'artifacts.jsonl'), artifacts, ARTIFACT_KEYS)
    write_jsonl(os.path.join(out_dir, 'invoice_reconciliation.jsonl'), invoices, INVOICE_KEYS)

    write_json(os.path.join(out_dir, 'team_chargeback.json'),
               settle.team_chargeback(attempts, artifacts, lookups))
    ledger = settle.cost_center_ledger(attempts, artifacts)
    write_json(os.path.join(out_dir, 'cost_center_ledger.json'), ledger)
    write_json(os.path.join(out_dir, 'rate_resolution.json'), settle.rate_resolution())
    write_json(os.path.join(out_dir, 'cache_effectiveness.json'),
               settle.cache_effectiveness(attempts, lookups))
    controls = settle.control_reconciliation()
    write_json(os.path.join(out_dir, 'control_reconciliation.json'), controls)
    write_json(os.path.join(out_dir, 'source_audit.json'), settle.source_audit())
    write_json(os.path.join(out_dir, 'close_summary.json'),
               settle.close_summary(attempts, artifacts, lookups, invoices, controls, ledger))
    return len(attempts)


def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: settle.py DATA_DIR OUT_DIR\n')
        return 2
    run(argv[1], argv[2])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
