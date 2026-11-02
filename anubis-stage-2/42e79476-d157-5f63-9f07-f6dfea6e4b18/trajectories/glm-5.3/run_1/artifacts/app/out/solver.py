#!/usr/bin/env python3
"""Network replan optimizer.

Rebuilds the cost coefficients from the flat registers, re-solves the plan the
operating contract defines and publishes the corrected plan with its audit
artifacts.  Usage:

    python3 solver.py <DATA_DIR> <OUT_DIR>

Standard library only, single process, no clock, no randomness.
"""

import csv
import json
import math
import os
import re
import sqlite3
import sys
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict

# --------------------------------------------------------------------------
# generic helpers
# --------------------------------------------------------------------------


def round_half_up(num, den):
    """round(num/den) half up, away from zero, on exact integers."""
    if den == 0:
        return 0
    if den < 0:
        num, den = -num, -den
    if num >= 0:
        return (2 * num + den) // (2 * den)
    return -((2 * (-num) + den) // (2 * den))


def norm_code(value):
    """Section 4 code normalisation: trim, upper case, drop separators,
    zero pad the numeric tail to two digits."""
    if value is None:
        return ''
    s = str(value).strip().upper()
    s = s.replace('-', '').replace('_', '')
    m = re.search(r'(\d+)$', s)
    if m:
        s = s[:m.start()] + m.group(1).zfill(2)
    return s


def norm_col(name):
    return re.sub(r'[^a-z0-9]+', '_', str(name).strip().lower()).strip('_')


# --------------------------------------------------------------------------
# minimal YAML subset parser (mappings, lists, scalars, comments)
# --------------------------------------------------------------------------


def _yaml_scalar(text):
    s = text.strip()
    if s.startswith('[') and s.endswith(']'):
        inner = s[1:-1].strip()
        if not inner:
            return []
        out, cur, quote = [], '', None
        for ch in inner:
            if quote is None and ch in '"\'':
                quote = ch
                continue
            if quote is not None and ch == quote:
                quote = None
                continue
            if quote is None and ch == ',':
                out.append(cur.strip())
                cur = ''
                continue
            cur += ch
        out.append(cur.strip())
        return [_yaml_scalar(x) for x in out if x != '']
    if len(s) >= 2 and s[0] == s[-1] and s[0] in '"\'':
        return s[1:-1]
    low = s.lower()
    if low in ('true', 'yes', 'on'):
        return True
    if low in ('false', 'no', 'off'):
        return False
    if low in ('null', '~', ''):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def _strip_comment(line):
    quote = None
    for i, ch in enumerate(line):
        if quote is not None:
            if ch == quote:
                quote = None
            continue
        if ch in '"\'':
            quote = ch
            continue
        if ch == '#' and (i == 0 or line[i - 1] in ' \t'):
            return line[:i]
    return line


def parse_yaml(text):
    items = []
    for raw in text.splitlines():
        line = _strip_comment(raw.replace('\t', '  ')).rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(' '))
        items.append((indent, line.strip()))
    value, pos = _yaml_block(items, 0, 0)
    return value if value is not None else {}


def _yaml_block(items, pos, indent):
    if pos < len(items) and items[pos][1].startswith('- '):
        out = []
        while pos < len(items) and items[pos][0] == indent and items[pos][1].startswith('- '):
            content = items[pos][1][2:].strip()
            pos += 1
            if not content:
                if pos < len(items) and items[pos][0] > indent:
                    val, pos = _yaml_block(items, pos, items[pos][0])
                    out.append(val)
                else:
                    out.append(None)
                continue
            if re.match(r'^[A-Za-z0-9_\- "\'()]+:', content) and ':' in content:
                # mapping entry inside a list item
                entry = {}
                key, _, rest = content.partition(':')
                rest = rest.strip()
                if rest:
                    entry[key.strip()] = _yaml_scalar(rest)
                else:
                    entry[key.strip()] = None
                if pos < len(items) and items[pos][0] > indent:
                    val, pos = _yaml_block(items, pos, items[pos][0])
                    if isinstance(val, dict):
                        entry.update(val)
                out.append(entry)
            else:
                out.append(_yaml_scalar(content))
        return out, pos
    out = {}
    while pos < len(items) and items[pos][0] == indent:
        content = items[pos][1]
        if content.startswith('- '):
            break
        key, sep, rest = content.partition(':')
        if not sep:
            pos += 1
            continue
        key = key.strip()
        rest = rest.strip()
        pos += 1
        if rest:
            out[key] = _yaml_scalar(rest)
        else:
            if pos < len(items) and items[pos][0] > indent:
                val, pos = _yaml_block(items, pos, items[pos][0])
                out[key] = val
            else:
                out[key] = None
    return out, pos


# --------------------------------------------------------------------------
# format readers
# --------------------------------------------------------------------------

DELIMS = {'csv': ',', 'tsv': '\t', 'psv': '|'}


def _txt_columns(line):
    m = re.search(r'(?:fixed column order|column order|columns)\s*[:=]\s*(.+)$', line)
    if not m:
        return None
    spec = m.group(1).strip()
    for sep in ('|', ',', ';', '\t'):
        if sep in spec:
            return [c.strip() for c in spec.split(sep) if c.strip() != '']
    return [spec] if spec else None


def read_text_lines(path):
    with open(path, 'r', encoding='utf-8', newline='') as fh:
        return fh.read().split('\n')


def parse_delimited(text, sep):
    rows = []
    header = None
    for line in text.split('\n'):
        if header is None:
            if line.strip() == '':
                continue
            header = [h.strip() for h in line.split(sep)]
            continue
        if line.strip() == '':
            continue
        vals = line.split(sep)
        row = {}
        for i, h in enumerate(header):
            row[h] = vals[i] if i < len(vals) else ''
        rows.append(row)
    return rows, (len(rows) if header is not None else 0)


def parse_lines_json(text):
    rows = []
    for line in text.split('\n'):
        if line.strip() == '':
            continue
        rows.append(json.loads(line))
    return rows, len(rows)


def parse_json_records(text):
    data = json.loads(text)
    if isinstance(data, dict):
        for key in ('records', 'rows', 'entries', 'data'):
            if key in data and isinstance(data[key], list):
                return data[key], len(data[key])
        return [], 0
    if isinstance(data, list):
        return data, len(data)
    return [], 0


def parse_xml(text):
    root = ET.fromstring(text)
    rows = [dict(child.attrib) for child in root]
    return rows, len(rows)


def parse_plain(text):
    rows = []
    cols = None
    count = 0
    for line in text.split('\n'):
        s = line.strip()
        if s == '':
            continue
        if s.startswith('#'):
            if cols is None:
                cols = _txt_columns(s)
            continue
        count += 1
        if cols:
            vals = s.split('|') if '|' in s else ([s] if ',' not in s else s.split(','))
            row = {}
            for i, c in enumerate(cols):
                row[c] = vals[i] if i < len(vals) else ''
            rows.append(row)
        else:
            rows.append({'line': s})
    return rows, count


def pdf_record_lines(raw):
    out = []
    for m in re.finditer(rb'stream\r?\n', raw):
        start = m.end()
        end = raw.find(b'endstream', start)
        if end < 0:
            end = len(raw)
        chunk = raw[start:end]
        text = None
        try:
            import zlib
            text = zlib.decompress(chunk).decode('latin-1')
        except Exception:
            try:
                text = chunk.decode('latin-1')
            except Exception:
                text = None
        if text:
            out.append(text)
    joined = '\n'.join(out)
    lines = []
    for m in re.finditer(r'\(((?:[^()\\]|\\.)*)\)', joined):
        token = m.group(1)
        token = re.sub(r'\\([()\\])', r'\1', token)
        token = token.replace('\\r', '\r').replace('\\n', '\n')
        lines.append(token)
    return lines


def docx_record_lines(path):
    """paragraphs of a word processing document that begin with the record
    prefix"""
    with zipfile.ZipFile(path) as zf:
        names = sorted(n for n in zf.namelist()
                        if n.startswith('word/') and n.endswith('.xml')
                        and 'document' in n)
        paras = []
        for name in names:
            root = ET.fromstring(zf.read(name))
            for p in root.iter():
                if not p.tag.endswith('}p'):
                    continue
                buf = [t.text for t in p.iter()
                       if t.tag.endswith('}t') and t.text]
                paras.append(''.join(buf))
    return [x.strip() for x in paras]


def xlsx_sheets(path):
    ns = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
    sheets = []
    with zipfile.ZipFile(path) as zf:
        names = sorted(n for n in zf.namelist()
                       if n.startswith('xl/worksheets/') and n.endswith('.xml'))
        for name in names:
            root = ET.fromstring(zf.read(name))
            table = []
            for row in root.iter(ns + 'row'):
                cells = []
                for c in row:
                    txt = ''
                    if c.get('t') == 'inlineStr':
                        txt = ''.join(t.text or '' for t in c.iter(ns + 't'))
                    else:
                        v = c.find(ns + 'v')
                        txt = v.text if (v is not None and v.text) else ''
                    cells.append(txt)
                table.append(cells)
            sheets.append(table)
    return sheets


def sqlite_tables(path):
    uri = 'file:' + path.replace('?', '%3f').replace('#', '%23') + '?mode=ro'
    con = sqlite3.connect(uri, uri=True)
    try:
        names = []
        for (name,) in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"):
            if not name.startswith('sqlite_'):
                names.append(name)
        tables = {}
        for name in names:
            tables[name] = [dict(zip([c[0] for c in con.execute(
                'SELECT * FROM "%s" LIMIT 0' % name).description],
                list(row))) for row in con.execute('SELECT * FROM "%s"' % name)]
        return tables
    finally:
        con.close()


# --------------------------------------------------------------------------
# corpus
# --------------------------------------------------------------------------


class Source(object):
    __slots__ = ('name', 'role', 'fmt', 'declared', 'authority', 'rows',
                 'rows_seen', 'order')

    def __init__(self, name, role, fmt, declared, authority):
        self.name = name
        self.role = role
        self.fmt = fmt
        self.declared = declared
        self.authority = authority
        self.rows = []
        self.rows_seen = 0
        self.order = 0


def find_manifest(indir):
    for name in sorted(os.listdir(indir)):
        path = os.path.join(indir, name)
        if not os.path.isfile(path):
            continue
        low = name.lower()
        if not (low.endswith('.db') or low.endswith('.sqlite')
                or low.endswith('.sqlite3')):
            continue
        try:
            tables = sqlite_tables(path)
        except Exception:
            continue
        for tname, rows in tables.items():
            if not rows:
                continue
            cols = set(rows[0].keys())
            if {'name', 'role', 'fmt', 'record_count', 'authority'} <= cols:
                return path, tname, tables
    return None, None, None


class Corpus(object):
    def __init__(self, indir):
        self.indir = indir
        self.sources = []
        self.by_role = defaultdict(list)
        self._load_manifest(indir)

    def _load_manifest(self, indir):
        mpath, mtable, tables = find_manifest(indir)
        self.manifest_path = mpath
        entries = []
        if mpath is not None:
            for row in tables[mtable]:
                entries.append((str(row['name']), str(row['role']),
                                str(row['fmt']),
                                int(row['record_count']),
                                str(row['authority'])))
        else:
            for name in sorted(os.listdir(indir)):
                path = os.path.join(indir, name)
                if os.path.isfile(path):
                    entries.append((name, guess_role(name), guess_fmt(name),
                                    -1, 'primary'))
        entries.sort(key=lambda e: e[0])
        for i, (name, role, fmt, count, auth) in enumerate(entries):
            src = Source(name, role, fmt, count, auth)
            src.order = i
            self.sources.append(src)
            self.by_role[role].append(src)

    def path(self, src):
        return os.path.join(self.indir, src.name)

    def primary(self, role):
        return [s for s in self.by_role.get(role, [])
                if s.authority == 'primary']

    def role_any(self, role):
        return self.by_role.get(role, [])



def guess_fmt(name):
    low = name.lower()
    for ext, fmt in (('.csv', 'csv'), ('.tsv', 'tsv'), ('.psv', 'psv'),
                     ('.jsonl', 'jsonl'), ('.ndjson', 'ndjson'),
                     ('.json', 'json'), ('.xml', 'xml'), ('.txt', 'txt'),
                     ('.md', 'md'), ('.yml', 'yml'), ('.yaml', 'yaml'),
                     ('.db', 'db'), ('.sqlite', 'sqlite'),
                     ('.xlsx', 'xlsx'), ('.pdf', 'pdf'), ('.docx', 'docx')):
        if low.endswith(ext):
            return fmt
    return 'txt'


def load_source_rows(src, path):
    """Parse a source into row dicts and count its physical rows."""
    fmt = src.fmt
    low = src.name.lower()
    if fmt in ('db', 'sqlite'):
        tables = sqlite_tables(path)
        total = 0
        for rows in tables.values():
            total += len(rows)
        src.rows_seen = total
        src.rows = []
        return
    try:
        with open(path, 'rb') as fh:
            raw = fh.read()
    except OSError:
        src.rows_seen = 0
        src.rows = []
        return
    if fmt in ('xlsx',):
        sheets = xlsx_sheets(path)
        total = 0
        for table in sheets:
            if table:
                total += len(table) - 1
        src.rows_seen = total
        src.rows = []
        return
    if fmt in ('pdf',):
        text_lines = pdf_record_lines(raw)
        recs = [l for l in text_lines if l.strip().startswith('R|')]
        src.rows_seen = len(recs)
        src.rows = [{'record': r.strip()} for r in recs]
        return
    if fmt in ('docx',):
        paras = docx_record_lines(path)
        recs = [p for p in paras if p.strip().startswith('R|')]
        src.rows_seen = len(recs)
        src.rows = [{'record': r.strip()} for r in recs]
        return
    text = raw.decode('utf-8', 'replace')
    if fmt in DELIMS:
        rows, n = parse_delimited(text, DELIMS[fmt])
        src.rows = rows
        src.rows_seen = n
        return
    if fmt in ('jsonl', 'ndjson'):
        rows, n = parse_lines_json(text)
        src.rows = rows
        src.rows_seen = n
        return
    if fmt == 'json':
        rows, n = parse_json_records(text)
        src.rows = rows
        src.rows_seen = n
        return
    if fmt == 'xml':
        rows, n = parse_xml(text)
        src.rows = rows
        src.rows_seen = n
        return
    if fmt in ('txt', 'md', 'yml', 'yaml'):
        rows, n = parse_plain(text)
        src.rows = rows
        src.rows_seen = n
        return
    src.rows = []
    src.rows_seen = 0


# --------------------------------------------------------------------------
# column resolution
# --------------------------------------------------------------------------


def find_column(keys, candidates):
    normed = {}
    for k in keys:
        normed.setdefault(norm_col(k), k)
    for cand in candidates:
        k = normed.get(norm_col(cand))
        if k is not None:
            return k
    return None


def find_column_fuzzy(keys, keywords):
    best = None
    for k in keys:
        n = norm_col(k)
        if all(norm_col(kw) in n for kw in keywords):
            if best is None or len(n) < len(norm_col(best)):
                best = k
    return best


# --------------------------------------------------------------------------
# registers
# --------------------------------------------------------------------------


def is_sentinel(value, tokens):
    if value is None:
        return True
    s = str(value).strip()
    if s == '':
        return True
    return s in tokens


def text_value(row, col):
    if col is None or row is None:
        return None
    v = row.get(col)
    if v is None:
        return None
    s = str(v).strip()
    return s if s != '' else None


def int_value(row, col, default=None):
    s = text_value(row, col)
    if s is None:
        return default
    try:
        return int(round(float(s)))
    except ValueError:
        return default


def build_lifecycle(src, cutoff):
    """row_uid -> True when the trailing lifecycle action at or below the
    cutoff is a void."""
    if src is None:
        return set()
    entries = defaultdict(list)
    for row in src.rows:
        uid = text_value(row, 'row_uid')
        seq = int_value(row, 'seq')
        if seq is None:
            seq = int_value(row, 'effective_seq')
        action = text_value(row, 'action')
        if uid is None or action is None:
            continue
        if seq is not None and seq > cutoff:
            continue
        entries[uid].append((seq if seq is not None else 0, action.strip().lower()))
    blocked = set()
    for uid, acts in entries.items():
        acts.sort(key=lambda x: x[0])
        last = None
        for _seq, act in acts:
            if act in ('void', 'restore'):
                last = act
        if last == 'void':
            blocked.add(uid)
    return blocked


# --------------------------------------------------------------------------
# sweep bookkeeping
# --------------------------------------------------------------------------


class RegisterSet(object):
    def __init__(self, cutoff, voided, sentinels, ignored):
        self.cutoff = cutoff
        self.voided = voided
        self.sentinels = sentinels
        self.ignored = ignored
        self.groups = defaultdict(list)   # logical name -> entries

    def add(self, logical, order, row, src):
        self.groups[logical].append((order, row, src))

    def _live(self, row):
        seq = int_value(row, 'effective_seq')
        if seq is None:
            return True                      # no sequence column: always live
        if seq > self.cutoff:
            return False
        v = text_value(row, 'void')
        if v is not None:
            try:
                if int(round(float(v))) != 0:
                    return False
            except ValueError:
                return False
        uid = text_value(row, 'row_uid')
        if uid is not None and uid in self.voided:
            return False
        return True

    def _flags_state(self, row):
        """(cut, voi) for the CUT and VOI coefficient letters."""
        seq = int_value(row, 'effective_seq')
        cut = seq is not None and seq > self.cutoff
        voi = False
        v = text_value(row, 'void')
        if v is not None:
            try:
                voi = int(round(float(v))) != 0
            except ValueError:
                voi = True
        uid = text_value(row, 'row_uid')
        if uid is not None and uid in self.voided:
            voi = True
        return cut, voi

    def winners(self, logical, keyfun, value_col=None):
        """live winning row per logical key (highest rev, then highest
        effective_seq, then later canonical order)."""
        buckets = defaultdict(list)
        for entry in self.groups.get(logical, []):
            order, row, src = entry
            buckets[keyfun(row)].append(entry)
        out = {}
        for key, entries in buckets.items():
            best = None
            for order, row, src in entries:
                if not self._live(row):
                    continue
                if value_col is not None and \
                        is_sentinel(row.get(value_col), self.sentinels):
                    continue
                rev = int_value(row, 'rev', 0) or 0
                seq = int_value(row, 'effective_seq', 0) or 0
                cand = (rev, seq, order)
                if best is None or cand > best[0]:
                    best = (cand, row, src)
            if best is not None:
                out[key] = best[1]
        return out

    def flags(self, logical, keyfun):
        """cut / voi flags per key for the coefficient letters."""
        buckets = defaultdict(list)
        for order, row, src in self.groups.get(logical, []):
            buckets[keyfun(row)].append(row)
        cut = set()
        voi = set()
        for key, rows in buckets.items():
            for row in rows:
                c, v = self._flags_state(row)
                if c:
                    cut.add(key)
                if v:
                    voi.add(key)
        return cut, voi

    def accumulators(self, logical, keyfun, id_col, value_col):
        """live accumulating register: first live row per identity, in
        canonical order."""
        buckets = defaultdict(list)
        for entry in self.groups.get(logical, []):
            order, row, src = entry
            buckets[keyfun(row)].append(entry)
        out = {}
        for key, entries in buckets.items():
            seen = {}
            for order, row, src in sorted(entries, key=lambda e: e[0]):
                ident = text_value(row, id_col)
                if ident is None:
                    ident = text_value(row, 'row_uid')
                if ident in seen:
                    continue
                if not self._live(row):
                    continue
                if is_sentinel(row.get(value_col), self.sentinels):
                    continue
                seen[ident] = row
            out[key] = list(seen.values())
        return out


def identifier_key(row, cols, cal_map):
    parts = []
    item = text_value(row, cols.get('item'))
    parts.append(norm_code(item) if item is not None else '')
    period = None
    pcol = cols.get('period')
    dcol = cols.get('date')
    if dcol is not None and text_value(row, dcol) is not None:
        period = cal_map.get(text_value(row, dcol))
    if period is None and pcol is not None:
        period = text_value(row, pcol)
    parts.append(norm_code(period) if period is not None else '')
    plant = text_value(row, cols.get('plant'))
    parts.append(norm_code(plant) if plant is not None else '')
    proj = text_value(row, cols.get('project'))
    parts.append(norm_code(proj) if proj is not None else '')
    zone = text_value(row, cols.get('zone'))
    parts.append(norm_code(zone) if zone is not None else '')
    return ':'.join(parts)


def detect_columns(rows, nomenclature):
    """work out which physical column of a source carries which identifier."""
    keys = set()
    for r in rows:
        keys.update(r.keys())
    cols = {
        'item': find_column(keys, nomenclature.get('item_code', [])
                            + ['item', 'item_code', 'sku', 'code']),
        'period': find_column(keys, nomenclature.get('period_code', [])
                              + ['period', 'period_code']),
        'plant': find_column(keys, nomenclature.get('plant_code', [])
                             + ['plant', 'plant_code']),
        'project': find_column(keys, ['project_id', 'project', 'project_code']),
        'zone': find_column(keys, ['zone', 'zone_code']),
        'date': find_column(keys, ['date', 'calendar_date', 'day']),
        'row_uid': find_column(keys, ['row_uid', 'uid']),
        'seq': find_column(keys, ['effective_seq']),
        'rev': find_column(keys, ['rev', 'revision']),
        'void': find_column(keys, ['void', 'voided']),
    }
    return cols


# --------------------------------------------------------------------------
# main model
# --------------------------------------------------------------------------


class Model(object):
    def __init__(self, indir):
        self.indir = indir
        self.corpus = Corpus(indir)
        self.nomenclature = {}
        self.runbook = {}
        self.control = {}
        self.item_defaults = {}
        self.plant_defaults = {}
        self.authority = {}
        self.sentinels = set()
        self.scales = {}
        self.ignored = set()
        self.retired_cols = set()
        self.aliases = {}
        self.cutoff = 0
        self.voided = set()

    # ---------------- contracts ----------------
    def load_contracts(self):
        for src in self.corpus.sources:
            if src.fmt in ('yaml', 'yml') and src.authority in ('contract',
                                                                'primary'):
                text = '\n'.join(read_text_lines(self.corpus.path(src)))
                data = parse_yaml(text)
                if 'control' in data or 'sentinel_tokens' in data:
                    if 'control' in data:
                        self.runbook.update(data)
                    else:
                        self.nomenclature.update(data)
        for src in self.corpus.sources:
            if src.fmt in ('db', 'sqlite'):
                tables = sqlite_tables(self.corpus.path(src))
                for tname, rows in tables.items():
                    if not rows:
                        continue
                    cols = set(rows[0].keys())
                    if 'parameter' in cols and 'value' in cols:
                        self.authority[tname] = rows
                    elif 'token' in cols and 'factor' in cols:
                        self.authority['scale'] = rows
                    elif 'token' in cols and 'disposition' in cols:
                        self.authority['sentinel'] = rows
                    elif 'raw' in cols and 'canonical' in cols:
                        self.authority['alias'] = rows
        control = self.runbook.get('control') or {}
        if isinstance(control, dict):
            self.control = control
        self.item_defaults = self.runbook.get('item_defaults') or {}
        self.plant_defaults = self.runbook.get('plant_defaults') or {}
        if not isinstance(self.item_defaults, dict):
            self.item_defaults = {}
        if not isinstance(self.plant_defaults, dict):
            self.plant_defaults = {}
        # authority db cutoff control as a fallback
        auth_control = {}
        for tname, rows in self.authority.items():
            if isinstance(rows, list) and rows and 'parameter' in rows[0]:
                for r in rows:
                    auth_control[str(r['parameter'])] = str(r['value'])
        for key, value in auth_control.items():
            self.control.setdefault(key, value)
        self.cutoff = self._int(self.control.get('plan_sequence_cutoff'), 0)
        # nomenclature
        nomen = self.nomenclature
        tokens = nomen.get('sentinel_tokens') or []
        if isinstance(tokens, list):
            self.sentinels = set(str(t) for t in tokens if t is not None)
        for r in self.authority.get('sentinel', []) or []:
            tok = str(r.get('token', '')).strip()
            if tok.lower() == '<empty>':
                tok = ''
            self.sentinels.add(tok)
        self.sentinels.discard('')
        ign = nomen.get('ignored_columns') or []
        if isinstance(ign, list):
            self.ignored = set(norm_col(x) for x in ign if x)
        ret = nomen.get('retired_aliases') or []
        if isinstance(ret, list):
            self.retired_cols = set(norm_col(x) for x in ret if x)
        aliases = nomen.get('header_aliases') or {}
        if isinstance(aliases, dict):
            self.aliases = aliases
        for token, factor in (('kcents', 1000), ('cents', 1), ('dozens', 12),
                              ('units_dz', 12), ('pct', 100), ('pct_to_bps', 100),
                              ('bps', 1), ('bps_denominator', 10000),
                              ('micros_denominator', 1000000)):
            self.scales.setdefault(token, factor)
        for token, factor in (nomen.get('scale_tokens') or {}).items():
            self.scales[str(token)] = int(factor)
        for r in self.authority.get('scale', []) or []:
            tok = str(r.get('token', '')).strip()
            try:
                self.scales[tok] = int(r.get('factor'))
            except (TypeError, ValueError):
                pass

    @staticmethod
    def _int(value, default=None):
        if value is None:
            return default
        if isinstance(value, bool):
            return int(value)
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            try:
                return int(round(float(value)))
            except (TypeError, ValueError):
                return default

    # ---------------- loading ----------------
    def load_sources(self):
        for src in self.corpus.sources:
            load_source_rows(src, self.corpus.path(src))

    # ---------------- sweeps ----------------
    def run_sweep(self):
        """one pass over every primary delimited / line delimited / JSON / XML
        or plain text source, in manifest name order."""
        self.rejected = []
        self.out_of_scope_rows = 0
        self.void_rows = 0
        # calendar and item status are needed to classify rows
        cal_map = self.build_calendar()
        item_status = self.build_item_status()
        for src in self.corpus.sources:
            if src.authority != 'primary':
                continue
            if src.fmt not in ('csv', 'tsv', 'psv', 'jsonl', 'ndjson', 'json',
                               'xml', 'txt'):
                continue
            cols = detect_columns(src.rows, self.aliases)
            is_demand = src.role in ('demand', 'demand_overlay')
            for row in src.rows:
                reason = None
                if is_demand:
                    item = norm_code(text_value(row, cols['item']) or '')
                    status = item_status.get(item)
                    if status is None:
                        reason = 'unknown_item'
                    elif status == 'retired':
                        reason = 'retired_item'
                if reason is None:
                    if self.row_has_sentinel(row, cols):
                        reason = 'sentinel'
                if reason is not None:
                    self.rejected.append({
                        'source': src.name,
                        'row_uid': text_value(row, cols['row_uid']) or '',
                        'key': identifier_key(row, cols, cal_map),
                        'reason': reason,
                    })
                    continue
                seq = int_value(row, cols['seq'])
                if seq is not None:
                    if seq > self.cutoff:
                        self.out_of_scope_rows += 1
                    else:
                        if self.row_blocked(row, cols):
                            self.void_rows += 1
        self.rejected.sort(key=lambda r: (r['source'], r['row_uid']))

    def row_has_sentinel(self, row, cols):
        for value in row.values():
            if is_sentinel(value, self.sentinels):
                return True
        return False

    def row_blocked(self, row, cols):
        v = text_value(row, cols['void'])
        if v is not None:
            try:
                if int(round(float(v))) != 0:
                    return True
            except ValueError:
                return True
        uid = text_value(row, cols['row_uid'])
        if uid is not None and uid in self.voided:
            return True
        return False

    # ---------------- registers ----------------
    def collect(self):
        """group every primary row into its logical register"""
        self.reg = RegisterSet(self.cutoff, self.voided, self.sentinels,
                               self.ignored)
        order = 0
        for src in self.corpus.sources:
            if src.authority != 'primary':
                continue
            if src.fmt not in ('csv', 'tsv', 'psv', 'jsonl', 'ndjson', 'json',
                               'xml', 'txt'):
                continue
            for row in src.rows:
                self.reg.add(src.role, order, row, src)
                order += 1

    def build_calendar(self):
        out = {}
        for src in self.corpus.primary('calendar'):
            for row in src.rows:
                d = text_value(row, 'date')
                p = text_value(row, 'period_code') or text_value(row, 'period')
                if d is None or p is None:
                    continue
                out.setdefault(d, norm_code(p))
        return out

    # ---------------- static register accessors ----------------
    def _winners(self, role, keyfun, value_col=None):
        return self.reg.winners(role, keyfun, value_col)

    # ---------------- horizon, items, plants ----------------
    def build_horizon(self):
        cal = self.build_calendar()
        winners = self._winners(
            'period_order',
            lambda r: norm_code(text_value(r, 'period_code')
                                or text_value(r, 'period') or ''),
            value_col='fiscal_ordinal')
        rows = []
        for period, row in winners.items():
            ordinal = int_value(row, 'fiscal_ordinal')
            fy = text_value(row, 'fy_start')
            fy_flag = False
            if fy is not None:
                fy_flag = fy.strip().lower() not in ('0', 'false', 'no', '')
            rows.append((period, ordinal if ordinal is not None else 0, fy_flag))
        rows.sort(key=lambda x: (x[1], x[0]))
        # the period flagged fy_start is ordinal one
        starts = [r for r in rows if r[2]]
        if starts:
            first = starts[0][0]
            rows = [r for r in rows if r[0] != first]
            rows.insert(0, (first, 1, True))
        self.periods = [r[0] for r in rows]
        self.ordinal = {}
        for i, p in enumerate(self.periods):
            self.ordinal[p] = i + 1
        return rows

    def build_item_status(self):
        winners = self._winners(
            'item_status',
            lambda r: norm_code(text_value(r, 'code')
                                or text_value(r, 'item')
                                or text_value(r, 'item_code')
                                or text_value(r, 'sku') or ''),
            value_col='status')
        return {k: (text_value(v, 'status') or '').strip().lower()
                for k, v in winners.items()}

    def build_families(self):
        winners = self._winners(
            'item_family',
            lambda r: norm_code(text_value(r, 'item')
                                or text_value(r, 'item_code')
                                or text_value(r, 'sku') or ''),
            value_col='family')
        out = {}
        for item, row in winners.items():
            fam = text_value(row, 'family')
            if fam:
                out[item] = fam.strip()
        return out

    def build_plant_status(self):
        winners = self._winners(
            'plant_status',
            lambda r: (norm_code(text_value(r, 'plant')
                                 or text_value(r, 'plant_code') or ''),
                       norm_code(text_value(r, 'period')
                                 or text_value(r, 'period_code') or '')),
            value_col='status')
        return {k: (text_value(v, 'status') or '').strip().lower()
                for k, v in winners.items()}

    def build_fx(self):
        """the treasury rate with the highest effective_seq at or below the
        cutoff among live rows"""
        best = None
        for order, row, src in self.reg.groups.get('fx_rate', []):
            seq = int_value(row, 'effective_seq')
            if seq is None or seq > self.cutoff:
                continue
            if not self.reg._live(row):
                continue
            rate = text_value(row, 'usd_per_eur_micros')
            if rate is None or is_sentinel(rate, self.sentinels):
                continue
            try:
                value = int(round(float(rate)))
            except ValueError:
                continue
            cand = (seq, order)
            if best is None or cand > best[0]:
                best = (cand, value)
        return best[1] if best else 1000000

    # ---------------- document parameters ----------------
    def read_prefixed_records(self, role):
        """rows of a document source whose records begin with the record
        prefix ``R|``."""
        out = []
        for src in self.corpus.primary(role):
            for row in src.rows:
                rec = row.get('record')
                if rec is None:
                    continue
                rec = rec.strip()
                if not rec.startswith('R|'):
                    continue
                fields = rec.split('|')
                out.append(fields)
        return out

    def doc_params(self, role, name_col=2, value_col=3, unit_col=4,
                   rev_col=5, seq_col=6, void_col=7, uid_col=8,
                   apply_prefix='APPLY'):
        """live winning PARAM rows of a document register, keyed by name."""
        winners = {}
        for fields in self.read_prefixed_records(role):
            if len(fields) < 8 or fields[1] != 'PARAM':
                continue
            seq = self._int(fields[seq_col]) if len(fields) > seq_col else None
            if seq is None or seq > self.cutoff:
                continue
            if len(fields) > void_col and fields[void_col].strip() not in ('0', ''):
                continue
            name = fields[name_col]
            if is_sentinel(fields[value_col], self.sentinels):
                continue
            rev = self._int(fields[rev_col]) if len(fields) > rev_col else 0
            uid = fields[uid_col] if len(fields) > uid_col else None
            if uid is not None and uid in self.voided:
                continue
            unit = fields[unit_col].strip().lower() if len(fields) > unit_col else ''
            value = self._int(fields[value_col])
            if value is not None:
                value = value * self.scales.get(unit, 1)
            cand = (rev if rev is not None else 0, seq, name)
            if name not in winners or cand > winners[name][0]:
                winners[name] = (cand, value, unit)
        return winners

    def build_penalty_params(self):
        role = 'penalty_schedule'
        params = self.doc_params(role)
        holding = params.get('holding_rate')
        penalty = params.get('shortfall_penalty_per_unit')
        self.holding_rate_bps = holding[1] if holding else 0
        self.shortfall_penalty = penalty[1] if penalty else 0

    def build_energy_params(self):
        params = self.doc_params('energy_memo')
        self.energy_surcharge_bps = params.get('energy_surcharge', (None, 0, ''))[1]

    def build_capital_programme(self):
        role = 'capital_programme'
        budget = None
        grid = None
        volumes = {}
        for src in self.corpus.primary(role):
            sheets = xlsx_sheets(self.corpus.path(src))
            for table in sheets:
                if not table:
                    continue
                header = [str(c).strip().lower() for c in table[0]]
                for cells in table[1:]:
                    row = {}
                    for i, key in enumerate(header):
                        row[key] = cells[i] if i < len(cells) else ''
                    row = {norm_col(k): v for k, v in row.items()}
                    self._consume_programme_row(row, header)
        budget = self._programme_params.get('capital_budget')
        grid = self._programme_params.get('capex_grid')
        self.budget_cents = budget[1] if budget is not None else 0
        self.capex_grid = grid[1] if grid is not None else \
            self._int(self.control.get('capex_grid_cents'), 5000) or 5000
        self.committed_volume = {k: v[1] for k, v in
                                 self._programme_volumes.items()}

    def _consume_programme_row(self, row, header):
        if not hasattr(self, '_programme_params'):
            self._programme_params = {}
            self._programme_volumes = {}
        keys = set(row.keys())
        pcol = find_column(keys, ['parameter', 'name', 'key'])
        vcol = find_column(keys, ['value'])
        ucol = find_column(keys, ['unit', 'scale'])
        pcol = find_column(keys, ['project_id', 'project', 'project_code'])
        pcol = pcol or find_column(keys, ['parameter', 'name', 'key'])
        # distinguish a control sheet from a volume sheet
        if find_column(keys, ['committed_volume_units']) is not None:
            volcol = find_column(keys, ['committed_volume_units'])
            proj = norm_code(text_value(row, pcol) or '')
            if not proj:
                return
            seq = int_value(row, 'effective_seq')
            void = text_value(row, 'void')
            uid = text_value(row, 'row_uid')
            if void is not None:
                try:
                    if int(round(float(void))) != 0:
                        return
                except ValueError:
                    return
            if uid is not None and uid in self.voided:
                return
            if seq is None or seq > self.cutoff:
                return
            val = int_value(row, volcol)
            if val is None or is_sentinel(str(val) if val is not None else None,
                                          self.sentinels):
                return
            rev = int_value(row, 'rev', 0) or 0
            cand = (rev, seq)
            cur = self._programme_volumes.get(proj)
            if cur is None or cand > cur[0]:
                self._programme_volumes[proj] = (cand, val)
            return
        # control sheet
        name = text_value(row, find_column(keys, ['parameter', 'name', 'key']))
        if name is None:
            return
        seq = int_value(row, 'effective_seq')
        void = text_value(row, 'void')
        uid = text_value(row, 'row_uid')
        if void is not None:
            try:
                if int(round(float(void))) != 0:
                    return
            except ValueError:
                return
        if uid is not None and uid in self.voided:
            return
        if seq is None or seq > self.cutoff:
            return
        val = text_value(row, find_column(keys, ['value']))
        if val is None or is_sentinel(val, self.sentinels):
            return
        unit = text_value(row, find_column(keys, ['unit', 'scale'])) or ''
        amount = self._int(val)
        if amount is None:
            return
        amount = amount * self.scales.get(unit.strip().lower(), 1)
        rev = int_value(row, 'rev', 0) or 0
        cand = (rev, seq)
        cur = self._programme_params.get(name.strip().lower())
        if cur is None or cand > cur[0]:
            self._programme_params[name.strip().lower()] = (cand, amount)

    # ---------------- demand ----------------
    def build_demand(self):
        cal = self.build_calendar()
        item_status = self.item_status_map
        aliases = self.nomenclature.get('header_aliases') or {}
        dozens_cols = set(norm_col(c) for c in
                           (aliases.get('demand_units_dozens') or ['units_dz']))
        self.dozens_factor = self.scales.get('dozens', 12)
        unit_cols = set()
        for c in (self.nomenclature.get('header_aliases', {})
                  .get('demand_units') or ['units', 'qty', 'planned_units']):
            unit_cols.add(norm_col(c))
        unit_cols.add(norm_col('demand_units'))
        buckets = defaultdict(list)
        for order, row, src in self.reg.groups.get('demand', []) + \
                self.reg.groups.get('demand_overlay', []):
            keys = set(row.keys())
            icol = find_column(keys, self.aliases.get('item_code', [])
                               + ['item', 'item_code', 'sku', 'code'])
            pcol = find_column(keys, self.aliases.get('period_code', [])
                               + ['period', 'period_code'])
            dcol = find_column(keys, ['date', 'calendar_date'])
            item = norm_code(text_value(row, icol) or '')
            period = None
            if dcol is not None and text_value(row, dcol) is not None:
                period = cal.get(text_value(row, dcol))
            if period is None:
                period = norm_code(text_value(row, pcol) or '')
            if not item or not period:
                continue
            value = None
            for key in row:
                if norm_col(key) in dozens_cols:
                    raw = self._int(row[key])
                    value = None if raw is None else raw * self.dozens_factor
                    break
            if value is None:
                for key in row:
                    if norm_col(key) in unit_cols:
                        value = self._int(row[key])
                        break
            if value is None:
                continue
            buckets[(item, period)].append((order, row, value))
        demand = {}
        for key, entries in buckets.items():
            best = None
            for order, row, value in entries:
                if not self.reg._live(row):
                    continue
                if is_sentinel(self._demand_value(row, dozens_cols, unit_cols),
                               self.sentinels):
                    continue
                rev = int_value(row, 'rev', 0) or 0
                seq = int_value(row, 'effective_seq', 0) or 0
                cand = (rev, seq, order)
                if best is None or cand > best[0]:
                    best = (cand, value)
            if best is not None:
                demand[key] = best[1]
        self.demand = demand
        return demand

    def _demand_value(self, row, dozens_cols, unit_cols):
        for key in row:
            if norm_col(key) in dozens_cols:
                return row[key]
        for key in row:
            if norm_col(key) in unit_cols:
                return row[key]
        return None

    # ---------------- coefficients ----------------
    def build_coefficients(self):
        periods = self.periods
        items = self.scope_items
        reg = self.reg
        cal = self.build_calendar()
        # ---- unit cost base
        base = reg.winners(
            'unit_cost',
            lambda r: (norm_code(text_value(r, 'item') or ''),
                       norm_code(text_value(r, 'period') or '')),
            value_col='amount')
        # ---- amendments accumulate
        amend = reg.accumulators(
            'cost_amendment',
            lambda r: (norm_code(text_value(r, 'item') or ''),
                       norm_code(text_value(r, 'period') or '')),
            'amend_id', 'amount')
        # ---- overrides
        over = reg.winners(
            'cost_override',
            lambda r: (norm_code(text_value(r, 'item') or ''),
                       norm_code(text_value(r, 'period') or '')),
            value_col='amount')
        # ---- energy index
        index = reg.winners(
            'energy_index',
            lambda r: norm_code(text_value(r, 'period') or ''),
            value_col='index_value')
        # ---- setup register
        setup = reg.winners(
            'setup_cost',
            lambda r: (norm_code(text_value(r, 'item') or ''),
                       norm_code(text_value(r, 'period') or '')),
            value_col='amount')
        # ---- flags
        def ukey(r):
            return (norm_code(text_value(r, 'item') or ''),
                    norm_code(text_value(r, 'period') or ''))
        cut_flags, voi_flags = {}, {}
        for role in ('unit_cost', 'cost_amendment', 'cost_override'):
            c, v = reg.flags(role, ukey)
            for key in c:
                cut_flags[key] = True
            for key in v:
                voi_flags[key] = True
        self.unit_cost = {}
        self.setup_cost = {}
        self.holding_cost = {}
        self.energy_bps = {}
        self.flags = {}
        for item in items:
            for period in periods:
                key = (item, period)
                flags = set()
                amt = None
                row = base.get(key)
                if row is not None:
                    raw = self._int(text_value(row, 'amount'))
                    scale = (text_value(row, 'scale') or '').strip().lower()
                    factor = self.scales.get(scale, 1)
                    ccy = (text_value(row, 'ccy') or '').strip().upper()
                    amt = raw * factor
                    if ccy == 'EUR':
                        amt = round_half_up(amt * self.fx_rate,
                                            self.scales.get('micros_denominator',
                                                           1000000))
                        flags.add('FX')
                    if scale == 'kcents':
                        flags.add('KC')
                # amendments
                amds = amend.get(key) or []
                if amds:
                    total = 0
                    for arow in amds:
                        sign = (text_value(arow, 'sign') or '').strip().lower()
                        aval = self._int(text_value(arow, 'amount')) or 0
                        if sign == 'credit':
                            total -= aval
                        else:
                            total += aval
                    amt = (amt if amt is not None else 0) + total
                    flags.add('AMD')
                # override
                orow = over.get(key)
                if orow is not None:
                    amt = self._int(text_value(orow, 'amount'))
                    flags.add('OVR')
                if amt is None:
                    amt = 0
                # energy uplift
                irow = index.get(period)
                ibps = 0
                if irow is not None:
                    val = self._int(text_value(irow, 'index_value')) or 0
                    unit = (text_value(irow, 'unit') or '').strip().lower()
                    ibps = val * self.scales.get(unit, 1)
                total_bps = ibps + self.energy_surcharge_bps
                if total_bps:
                    uplift = round_half_up(amt * total_bps,
                                           self.scales.get('bps_denominator',
                                                           10000))
                    if uplift:
                        flags.add('ENR')
                    amt += uplift
                self.energy_bps[key] = total_bps
                self.unit_cost[key] = amt
                if key in cut_flags:
                    flags.add('CUT')
                if key in voi_flags:
                    flags.add('VOI')
                self.flags[key] = '+'.join(sorted(flags))
                # setup coefficient
                srow = setup.get(key)
                if srow is not None:
                    raw = self._int(text_value(srow, 'amount')) or 0
                    scale = (text_value(srow, 'scale') or '').strip().lower()
                    self.setup_cost[key] = raw * self.scales.get(scale, 1)
                else:
                    dflt = self.item_defaults.get(item) or {}
                    if isinstance(dflt, dict) and dflt.get(
                            'setup_fallback_cents') is not None:
                        self.setup_cost[key] = self._int(
                            dflt.get('setup_fallback_cents')) or 0
                    else:
                        self.setup_cost[key] = self._int(
                            self.control.get('default_setup_cents'), 0) or 0
                self.holding_cost[key] = round_half_up(
                    amt * self.holding_rate_bps,
                    self.scales.get('bps_denominator', 10000))

    # ---------------- capacity and handling ----------------
    def build_capacity_handling(self):
        reg = self.reg
        plants = self.scope_plants
        periods = self.periods
        base = reg.winners(
            'capacity_base',
            lambda r: (norm_code(text_value(r, 'plant') or ''),
                       norm_code(text_value(r, 'period') or '')),
            value_col='base_capacity_units')
        adj = reg.accumulators(
            'capacity_adjustment',
            lambda r: (norm_code(text_value(r, 'plant') or ''),
                       norm_code(text_value(r, 'period') or '')),
            'adj_id', 'delta_units')
        hbase = reg.winners(
            'handling_base',
            lambda r: (norm_code(text_value(r, 'plant') or ''),
                       norm_code(text_value(r, 'period') or '')),
            value_col='handling_cents_per_unit')
        hadj = reg.accumulators(
            'handling_adjustment',
            lambda r: (norm_code(text_value(r, 'plant') or ''),
                       norm_code(text_value(r, 'period') or '')),
            'adj_id', 'delta_cents')
        shift = reg.winners(
            'shift_pattern',
            lambda r: norm_code(text_value(r, 'plant') or ''),
            value_col='shift_value')
        derate = reg.winners(
            'holiday_derate',
            lambda r: norm_code(text_value(r, 'period') or ''),
            value_col='derate_value')
        zone = reg.winners(
            'plant_zone',
            lambda r: norm_code(text_value(r, 'plant') or ''),
            value_col='zone')
        uplift = reg.winners(
            'zone_tariff',
            lambda r: norm_code(text_value(r, 'zone') or ''),
            value_col='uplift_value')
        status = self.plant_status_map

        def bps_of(row, value_col):
            val = self._int(text_value(row, value_col)) or 0
            unit = (text_value(row, 'unit') or '').strip().lower()
            return val * self.scales.get(unit, 1)

        self.capacity = {}
        self.handling = {}
        self.mothballed = set()
        for plant in plants:
            for period in periods:
                key = (plant, period)
                st = status.get(key)
                if st == 'mothballed':
                    self.mothballed.add(key)
                brow = base.get(key)
                b = self._int(text_value(brow, 'base_capacity_units')) \
                    if brow is not None else 0
                if b is None:
                    b = 0
                a = 0
                for rrow in (adj.get(key) or []):
                    a += self._int(text_value(rrow, 'delta_units')) or 0
                srow = shift.get(plant)
                sbps = bps_of(srow, 'shift_value') if srow is not None else \
                    self.scales.get('bps_denominator', 10000)
                drow = derate.get(period)
                dbps = bps_of(drow, 'derate_value') if drow is not None else \
                    self.scales.get('bps_denominator', 10000)
                if st == 'mothballed':
                    cap = 0
                else:
                    cap = round_half_up(
                        round_half_up((b + a) * sbps,
                                      self.scales.get('bps_denominator', 10000))
                        * dbps, self.scales.get('bps_denominator', 10000))
                    if cap < 0:
                        cap = 0
                self.capacity[key] = cap
                hrow = hbase.get(key)
                hb = self._int(text_value(hrow, 'handling_cents_per_unit')) \
                    if hrow is not None else 0
                if hb is None:
                    hb = 0
                ha = 0
                for rrow in (hadj.get(key) or []):
                    ha += self._int(text_value(rrow, 'delta_cents')) or 0
                zrow = zone.get(plant)
                zcode = norm_code(text_value(zrow, 'zone')) \
                    if zrow is not None else ''
                urow = uplift.get(zcode) if zcode else None
                ubps = bps_of(urow, 'uplift_value') if urow is not None else 0
                rate = round_half_up(
                    (hb + ha) * (self.scales.get('bps_denominator', 10000)
                                 + ubps),
                    self.scales.get('bps_denominator', 10000))
                if rate < 0:
                    rate = 0
                self.handling[key] = rate

    def apply_project_savings(self, projects):
        """selected projects reduce their plant handling rate"""
        savings = defaultdict(int)
        for pid, info in projects.items():
            if info['selected']:
                savings[info['plant']] += info['saving']
        for key in list(self.handling.keys()):
            plant = key[0]
            dflt = self.plant_defaults.get(plant) or {}
            floor = self._int(dflt.get('minimum_handling_cents'), None) \
                if isinstance(dflt, dict) else None
            if floor is None:
                floor = self._int(self.control.get('minimum_handling_cents'),
                                  0) or 0
            rate = self.handling[key] - savings.get(plant, 0)
            if rate < floor:
                rate = floor
            self.handling[key] = rate

    # ---------------- capital selection ----------------
    def build_projects(self):
        reg = self.reg
        capex_rows = reg.winners(
            'retrofit_capex',
            lambda r: norm_code(text_value(r, 'project_id') or ''),
            value_col='amount')
        saving_rows = reg.winners(
            'retrofit_savings',
            lambda r: norm_code(text_value(r, 'project_id') or ''),
            value_col='savings_value')
        elig_rows = reg.winners(
            'retrofit_eligibility',
            lambda r: norm_code(text_value(r, 'project_id') or ''),
            value_col='eligible')
        proj_rows = reg.winners(
            'retrofit_project',
            lambda r: norm_code(text_value(r, 'project_id') or ''),
            value_col='plant')
        projects = {}
        for pid in sorted(set(list(capex_rows) + list(saving_rows)
                              + list(elig_rows) + list(proj_rows))):
            if not pid:
                continue
            crow = capex_rows.get(pid)
            capex = 0
            if crow is not None:
                raw = self._int(text_value(crow, 'amount')) or 0
                scale = (text_value(crow, 'scale') or '').strip().lower()
                capex = raw * self.scales.get(scale, 1)
            srow = saving_rows.get(pid)
            saving = 0
            if srow is not None:
                raw = self._int(text_value(srow, 'savings_value')) or 0
                ccy = (text_value(srow, 'ccy') or '').strip().upper()
                if ccy == 'EUR':
                    raw = round_half_up(
                        raw * self.fx_rate,
                        self.scales.get('micros_denominator', 1000000))
                saving = raw
            erow = elig_rows.get(pid)
            eligible = (text_value(erow, 'eligible')
                        or '').strip().lower() == 'yes'
            prow = proj_rows.get(pid)
            plant = norm_code(text_value(prow, 'plant')) \
                if prow is not None else ''
            vol = (self.committed_volume or {}).get(pid)
            volume = vol if vol else 0
            projects[pid] = {
                'project_id': pid,
                'capex': capex,
                'saving': saving,
                'eligible': eligible,
                'plant': plant,
                'volume': volume,
                'value': saving * volume,
                'selected': False,
            }
        return projects

    def capital_unit(self, capex_list, budget):
        """state unit for the capital programme: the runbook grid when every
        cost is a multiple of it, otherwise the common divisor of the
        amounts."""
        unit = self.capex_grid or 1
        for c in capex_list:
            if c % unit:
                unit = 0
                break
        if not unit:
            unit = 0
            for c in list(capex_list) + [budget]:
                if c:
                    unit = c if not unit else math.gcd(unit, c)
            unit = unit or 1
        return max(unit, 1)

    def knapsack(self, items, envelope_units, grid):
        """items: list of (value, capex_cents).  Returns the best
        (value, capex, indicator) with capex <= envelope_units*grid."""
        states = {0: (0, 0, 0)}
        for i, (value, capex) in enumerate(items):
            w = capex // grid if grid else 0
            add = {}
            for used, (val, ind, cost) in states.items():
                nu = used + w
                if nu > envelope_units:
                    continue
                cand = (val + value, ind | (1 << i), cost + capex)
                cur = add.get(nu)
                if cur is None or self._better_state(cand, cur):
                    add[nu] = cand
            for used, cand in add.items():
                cur = states.get(used)
                if cur is None or self._better_state(cand, cur):
                    states[used] = cand
            states = self.prune_states(states)
        return states

    @staticmethod
    def prune_states(states, limit=50000):
        """drop dominated states: a state that costs more for no more value
        can never take part in the optimal selection"""
        if len(states) <= limit:
            return states
        out = {}
        best = None
        for used in sorted(states):
            value, indicator, cost = states[used]
            if best is None or value > best:
                out[used] = states[used]
                best = value
        return out

    def knapsack_values(self, items, envelope_units, grid):
        """maximum value only, for the sensitivity price of one more unit."""
        best = {}
        states = {0: 0}
        for value, capex in items:
            w = capex // grid if grid else 0
            add = {}
            for used, val in states.items():
                nu = used + w
                if nu > envelope_units:
                    continue
                cand = val + value
                if add.get(nu, -1) < cand:
                    add[nu] = cand
            for used, cand in add.items():
                if states.get(used, -1) < cand:
                    states[used] = cand
        return max(states.values()) if states else 0


    @staticmethod
    def _better_state(a, b):
        if a[0] != b[0]:
            return a[0] > b[0]
        if a[2] != b[2]:
            return a[2] < b[2]
        return a[1] < b[1]

    def select_capital(self, projects, budget):
        candidates = sorted(pid for pid, info in projects.items()
                            if info['eligible'])
        capex_list = [projects[pid]['capex'] for pid in candidates]
        grid = self.capital_unit(capex_list, budget)
        envelope_units = budget // grid
        items = [(projects[pid]['value'], projects[pid]['capex'])
                 for pid in candidates]
        states = self.knapsack(items, envelope_units, grid)
        best = None
        for used in sorted(states):
            cand = states[used]
            if best is None or self._better_state(cand, best):
                best = cand
        value, indicator, capex = best
        selected = []
        for i, pid in enumerate(candidates):
            if indicator & (1 << i):
                selected.append(pid)
        for pid in selected:
            projects[pid]['selected'] = True
        return candidates, selected, value, capex

    # ---------------- lot sizing ----------------
    def solve_lot_sizing(self, item):
        """Wagner Whitin programme for one item.  Returns the optimal cost and
        the production period indices (0 based, ascending)."""
        periods = self.periods
        T = len(periods)
        demand = [self.demand.get((item, p), 0) or 0 for p in periods]
        unit = [self.unit_cost[(item, p)] for p in periods]
        setup = [self.setup_cost[(item, p)] for p in periods]
        hold = [self.holding_cost[(item, p)] for p in periods]
        block = [[0] * T for _ in range(T)]
        for a in range(T):
            dsum = demand[a]
            haccum = 0
            hsum = 0
            block[a][a] = 0 if dsum == 0 else setup[a] + unit[a] * dsum
            for b in range(a + 1, T):
                hsum += hold[b - 1]
                haccum += demand[b] * hsum
                dsum += demand[b]
                block[a][b] = 0 if dsum == 0 else \
                    setup[a] + unit[a] * dsum + haccum
        # backward DP; the key is the production list in reverse fiscal order
        best = [None] * (T + 1)
        best[T] = (0, ())
        for t in range(T - 1, -1, -1):
            opts = []
            if demand[t] == 0:
                sub = best[t + 1]
                if sub is not None:
                    opts.append((sub[0], sub[1]))
            for b in range(t, T):
                if block[t][b] == 0:
                    continue
                sub = best[b + 1]
                if sub is None:
                    continue
                opts.append((block[t][b] + sub[0], sub[1] + (t,)))
            if not opts:
                best[t] = None
                continue
            top = min(o[0] for o in opts)
            tied = [o for o in opts if o[0] == top]
            tied.sort(key=lambda o: o[1])
            best[t] = (top, tied[0][1])
        if best[0] is None:
            return 0, []
        return best[0][0], sorted(best[0][1])

    # ---------------- sourcing ----------------
    def solve_sourcing(self, produced_items):
        """produced_items: period -> {item: units}; returns the allocation
        rows and the assigned units per plant and period."""
        plants = self.scope_plants
        allocations = []
        assigned = {}
        shortfall = {}
        for period in self.periods:
            remaining = {k: v for k, v in
                          (produced_items.get(period) or {}).items() if v}
            order = sorted(plants,
                           key=lambda pl: (self.handling[(pl, period)], pl))
            for pl in order:
                avail = self.capacity[(pl, period)]
                take = min(avail, sum(remaining.values()))
                assigned[(pl, period)] = take
                if take <= 0:
                    continue
                left = take
                for item in sorted(remaining):
                    if left <= 0:
                        break
                    take_i = min(remaining[item], left)
                    if take_i > 0:
                        remaining[item] -= take_i
                        left -= take_i
                        allocations.append({
                            'period': period,
                            'plant': pl,
                            'item': item,
                            'units': take_i,
                            'rate': self.handling[(pl, period)],
                        })
            shortfall[period] = sum(remaining.values())
        return allocations, assigned, shortfall

    # ---------------- incumbent ----------------
    def load_incumbent(self):
        self.incumbent_coefficients = {}
        for src in self.corpus.role_any('incumbent_plan'):
            for row in src.rows:
                item = norm_code(text_value(row, 'item')
                                or text_value(row, 'item_code')
                                or text_value(row, 'sku') or '')
                period = norm_code(text_value(row, 'period')
                                   or text_value(row, 'period_code') or '')
                cost = int_value(row, 'unit_cost_cents')
                if cost is None:
                    cost = int_value(row, 'unit_cost')
                if item and period and cost is not None:
                    self.incumbent_coefficients[(item, period)] = cost
        self.incumbent_report = {}
        for src in self.corpus.role_any('incumbent_report'):
            if src.fmt != 'json':
                continue
            text = '\n'.join(read_text_lines(self.corpus.path(src)))
            try:
                self.incumbent_report = json.loads(text)
            except ValueError:
                self.incumbent_report = {}

    # ---------------- run ----------------
    def run(self):
        self.load_contracts()
        self.load_sources()
        life_src = None
        for src in self.corpus.by_role.get('row_lifecycle', []):
            if src.authority == 'primary':
                life_src = src
                break
        self.voided = build_lifecycle(life_src, self.cutoff)
        self.collect()
        self.run_sweep()
        self.item_status_map = self.build_item_status()
        self.plant_status_map = self.build_plant_status()
        self.build_horizon()
        self.fx_rate = self.build_fx()
        self.build_penalty_params()
        self.build_energy_params()
        self.build_capital_programme()
        # scope
        self.scope_items = sorted(
            item for item, status in self.item_status_map.items()
            if status != 'retired' and item)
        self.scope_plants = sorted(set(
            pl for (pl, _per) in self.plant_status_map.keys() if pl))
        self.build_demand()
        self.build_coefficients()
        self.build_capacity_handling()
        self.load_incumbent()
        # stage two: capital
        self.projects = self.build_projects()
        candidates, selected, value, capex = self.select_capital(
            self.projects, self.budget_cents)
        self.apply_project_savings(self.projects)
        # stage three: lot sizing
        produced_items = defaultdict(dict)
        plan_rows = []
        self.lot_plan = {}
        for item in self.scope_items:
            cost, chosen = self.solve_lot_sizing(item)
            self.lot_plan[item] = chosen
            T = len(self.periods)
            for i, a in enumerate(chosen):
                end = chosen[i + 1] - 1 if i + 1 < len(chosen) else T - 1
                qty = sum(self.demand.get((item, self.periods[t]), 0) or 0
                          for t in range(a, end + 1))
                if qty <= 0:
                    continue
                period = self.periods[a]
                produced_items[period][item] = qty
                plan_rows.append({
                    'item': item,
                    'idx': a,
                    'period': period,
                    'qty': qty,
                    'covers': [self.periods[t] for t in range(a, end + 1)
                               if (self.demand.get((item, self.periods[t]), 0)
                                   or 0) > 0],
                })
        # stage four: sourcing
        allocations, assigned, shortfall = self.solve_sourcing(produced_items)
        self.allocation_rows = allocations
        self.assigned = assigned
        self.shortfall = shortfall
        self.plan_rows = plan_rows
        self.candidates = candidates
        self.selected = selected
        self.selected_value = value
        self.selected_capex = capex
        return self

    # ---------------- figures ----------------
    def compute_figures(self):
        items = self.scope_items
        periods = self.periods
        T = len(periods)
        self.production_cost = 0
        self.setup_total = 0
        self.holding_total = 0
        self.setup_count = defaultdict(int)
        item_production = defaultdict(int)
        item_setup = defaultdict(int)
        self.ending = {}
        cum_hold = defaultdict(int)
        self.period_holding = {}
        self.item_demand = defaultdict(int)
        self.item_produced = defaultdict(int)
        for item in items:
            chosen = list(self.lot_plan.get(item) or [])
            cover = {}
            bounds = {}
            for i, a in enumerate(chosen):
                end = chosen[i + 1] - 1 if i + 1 < len(chosen) else T - 1
                bounds[a] = end
                for t in range(a, end + 1):
                    cover[t] = a
            inv = 0
            for t, period in enumerate(periods):
                a = cover.get(t)
                qty = 0
                if a is not None and a == t:
                    end = bounds[a]
                    qty = sum(self.demand.get((item, periods[s]), 0) or 0
                              for s in range(a, end + 1))
                    unit = self.unit_cost[(item, period)]
                    setup = self.setup_cost[(item, period)]
                    self.production_cost += unit * qty
                    self.setup_total += setup
                    self.setup_count[item] += 1
                    item_production[item] += unit * qty
                    item_setup[item] += setup
                    self.item_produced[item] += qty
                dem = self.demand.get((item, period), 0) or 0
                self.item_demand[item] += dem
                inv += qty - dem
                self.ending[(item, period)] = inv
                charge = inv * self.holding_cost[(item, period)]
                self.period_holding[(item, period)] = charge
                cum_hold[item] += charge
                self.holding_total += charge
        self.cum_holding = dict(cum_hold)
        self.item_production_cost = dict(item_production)
        self.item_setup_cost = dict(item_setup)
        self.handling_total = 0
        for row in self.allocation_rows:
            self.handling_total += row['units'] * row['rate']
        self.shortfall_units = sum(self.shortfall.values())
        self.shortfall_penalty_total = self.shortfall_units * \
            self.shortfall_penalty
        self.total_demand = sum(self.item_demand.values())
        self.total_produced = sum(self.item_produced.values())
        self.total_objective = (self.production_cost + self.setup_total
                                + self.holding_total + self.handling_total
                                + self.shortfall_penalty_total
                                + self.selected_capex)

    # ---------------- derived reports ----------------
    def build_reports(self):
        items = self.scope_items
        plants = self.scope_plants
        periods = self.periods
        # item and period produced matrices
        self.item_period_produced = {}
        for row in self.plan_rows:
            self.item_period_produced[(row['item'], row['period'])] = row['qty']
        self.period_required = {}
        for period in periods:
            self.period_required[period] = sum(
                self.item_period_produced.get((item, period), 0)
                for item in items)
        self.families = self.build_families()
        # ---- sensitivity
        grid = self.capital_unit(
            [self.projects[pid]['capex'] for pid in self.candidates],
            self.budget_cents)
        items_kn = [(self.projects[pid]['value'], self.projects[pid]['capex'])
                    for pid in self.candidates]
        value_at_budget = self.knapsack_values(items_kn,
                                               self.budget_cents // grid, grid)
        value_at_more = self.knapsack_values(
            items_kn, (self.budget_cents + self.capex_grid) // grid, grid)
        marginal = value_at_more - value_at_budget
        self.budget_binding = marginal > 0
        unfunded = [pid for pid in self.candidates
                    if pid not in self.selected]
        top_id = ''
        top_capex = 0
        if unfunded:
            best = None
            for pid in sorted(unfunded):
                info = self.projects[pid]
                cap = info['capex'] or 0
                ratio = (info['value'], cap) if cap else (info['value'], 0)
                key = (info['value'] / cap) if cap else float(
                    info['value']) if info['value'] else 0.0
                if best is None or key > best[0] or (key == best[0]
                                                    and pid < best[1]):
                    best = (key, pid)
            top_id = best[1]
            top_capex = self.projects[top_id]['capex']
        next_unit = {}
        for period in periods:
            rates = [self.handling[(pl, period)] for pl in plants
                     if self.capacity.get((pl, period), 0)
                     - self.assigned.get((pl, period), 0) > 0]
            next_unit[period] = min(rates) if rates else self.shortfall_penalty
        self.sensitivity = {
            'budget_binding': bool(self.budget_binding),
            'budget_grid_unit_cents': self.capex_grid,
            'marginal_value_of_one_grid_unit_cents': marginal,
            'next_unit_cost_by_period': next_unit,
            'top_unfunded_capex_cents': top_capex,
            'top_unfunded_project_id': top_id,
        }
        # ---- certificate
        zero_inv = True
        for item in items:
            inv = 0
            for period in periods:
                qty = self.item_period_produced.get((item, period), 0)
                if qty > 0 and inv != 0:
                    zero_inv = False
                inv += qty - (self.demand.get((item, period), 0) or 0)
        # reconstruct the programme cost straight from the published plan
        recon = 0
        for row in self.plan_rows:
            key = (row['item'], row['period'])
            recon += self.unit_cost.get(key, 0) * row['qty']
            recon += self.setup_cost.get(key, 0)
        for item in items:
            for period in periods:
                recon += self.ending.get((item, period), 0) * \
                    self.holding_cost.get((item, period), 0)
        no_unfunded = True
        slack = self.budget_cents - self.selected_capex
        for pid in self.candidates:
            if pid in self.selected:
                continue
            info = self.projects[pid]
            if info['value'] > 0 and info['capex'] <= slack:
                no_unfunded = False
        sourcing_ok = True
        for period in periods:
            used_rates = [self.handling[(pl, period)] for pl in plants
                          if self.assigned.get((pl, period), 0) > 0]
            idle_rates = [self.handling[(pl, period)] for pl in plants
                          if self.capacity.get((pl, period), 0)
                          - self.assigned.get((pl, period), 0) > 0]
            if used_rates and idle_rates and max(used_rates) > min(idle_rates):
                sourcing_ok = False
        covered = (self.total_demand == self.total_produced
                   and self.total_produced == sum(self.assigned.values())
                   + self.shortfall_units)
        self.certificate = {
            'all_demand_covered_or_charged': bool(covered),
            'capital_no_unfunded_candidate_fits': bool(no_unfunded),
            'lot_sizing_reconstructed_cost_matches': bool(
                recon == self.production_cost + self.setup_total
                + self.holding_total),
            'lot_sizing_zero_inventory_property': bool(zero_inv),
            'sourcing_no_cheaper_idle_capacity': bool(sourcing_ok),
            'total_objective_cents': self.total_objective,
        }
        # ---- incumbent delta
        report = self.incumbent_report or {}
        stage = report.get('stage_totals_cents') or {}
        components = {}
        names = ['capex_cents', 'handling_cost_cents', 'holding_cost_cents',
                 'production_cost_cents', 'setup_cost_cents',
                 'shortfall_penalty_cents']
        corrected = {
            'capex_cents': self.selected_capex,
            'handling_cost_cents': self.handling_total,
            'holding_cost_cents': self.holding_total,
            'production_cost_cents': self.production_cost,
            'setup_cost_cents': self.setup_total,
            'shortfall_penalty_cents': self.shortfall_penalty_total,
        }
        for name in names:
            if name in stage:
                components[name] = corrected[name] - int(stage[name])
        incumbent_total = report.get('published_total_objective_cents')
        incumbent_total = int(incumbent_total) if incumbent_total is not None \
            else 0
        incumbent_projects = [norm_code(p) for p in
                              (report.get('selected_projects') or [])]
        added = sorted(set(self.selected) - set(incumbent_projects))
        dropped = sorted(set(incumbent_projects) - set(self.selected))
        self.incumbent_delta = {
            'component_deltas': components,
            'corrected_selected_project_ids': sorted(self.selected),
            'corrected_total_objective_cents': self.total_objective,
            'delta_cents': self.total_objective - incumbent_total,
            'incumbent_selected_project_ids': sorted(incumbent_projects),
            'incumbent_total_objective_cents': incumbent_total,
            'projects_added': added,
            'projects_dropped': dropped,
        }
        # ---- data quality
        sources = []
        mismatches = []
        for src in self.corpus.sources:
            sources.append({
                'authority': src.authority,
                'fmt': src.fmt,
                'name': src.name,
                'record_count_declared': src.declared,
                'role': src.role,
                'rows_seen': src.rows_seen,
            })
            if src.declared != src.rows_seen:
                mismatches.append(src.name)
        self.data_quality = {
            'count_mismatches': sorted(mismatches),
            'sources': sorted(sources, key=lambda s: s['name']),
            'totals': {
                'rejected_rows': len(self.rejected),
                'out_of_scope_rows': self.out_of_scope_rows,
                'void_rows': self.void_rows,
                'sources_seen': len(self.corpus.sources),
            },
        }
        # ---- reconciliation
        self.reconciliation = [
            ('corrected_total_objective_cents', self.total_objective),
            ('incumbent_total_objective_cents', incumbent_total),
            ('delta_cents', self.total_objective - incumbent_total),
            ('selected_capex_cents', self.selected_capex),
            ('budget_cents', self.budget_cents),
            ('total_shortfall_units', self.shortfall_units),
            ('shortfall_penalty_cents', self.shortfall_penalty_total),
            ('items_in_scope', len(items)),
            ('rejected_rows', len(self.rejected)),
        ]


# --------------------------------------------------------------------------
# artifact writers
# --------------------------------------------------------------------------


def write_json(path, data):
    with open(path, 'w', encoding='utf-8', newline='') as fh:
        json.dump(data, fh, sort_keys=True, indent=1)
        fh.write('\n')


def write_jsonl(path, rows):
    with open(path, 'w', encoding='utf-8', newline='') as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True,
                                separators=(',', ':')) + '\n')


def write_csv(path, header, rows):
    with open(path, 'w', encoding='utf-8', newline='') as fh:
        writer = csv.writer(fh, lineterminator='\n')
        writer.writerow(header)
        for row in rows:
            writer.writerow([row[h] for h in header])


def write_text(path, text):
    with open(path, 'w', encoding='utf-8', newline='') as fh:
        fh.write(text)


def publish(model, outdir):
    os.makedirs(outdir, exist_ok=True)
    items = model.scope_items
    plants = model.scope_plants
    periods = model.periods
    ordinal = model.ordinal

    # ---- corrected_coefficients.jsonl
    rows = []
    for item in items:
        for period in periods:
            key = (item, period)
            rows.append({
                'demand_units': model.demand.get(key, 0) or 0,
                'energy_bps_applied': model.energy_bps.get(key, 0),
                'fiscal_ordinal': ordinal[period],
                'flags': model.flags.get(key, ''),
                'holding_cost_cents': model.holding_cost.get(key, 0),
                'item': item,
                'period': period,
                'setup_cost_cents': model.setup_cost.get(key, 0),
                'unit_cost_cents': model.unit_cost.get(key, 0),
            })
    write_jsonl(os.path.join(outdir, 'corrected_coefficients.jsonl'), rows)

    # ---- objective.json
    write_json(os.path.join(outdir, 'objective.json'), {
        'capex_cents': model.selected_capex,
        'handling_cost_cents': model.handling_total,
        'holding_cost_cents': model.holding_total,
        'items_in_scope': len(items),
        'periods_in_horizon': len(periods),
        'plants_in_scope': len(plants),
        'production_cost_cents': model.production_cost,
        'setup_cost_cents': model.setup_total,
        'shortfall_penalty_cents': model.shortfall_penalty_total,
        'total_demand_units': model.total_demand,
        'total_objective_cents': model.total_objective,
        'total_produced_units': model.total_produced,
        'total_shortfall_units': model.shortfall_units,
    })

    # ---- optimal_plan.jsonl
    plan_rows = []
    for row in sorted(model.plan_rows, key=lambda r: (r['item'],
                                                     ordinal[r['period']])):
        key = (row['item'], row['period'])
        plan_rows.append({
            'covers_periods': row['covers'],
            'fiscal_ordinal': ordinal[row['period']],
            'item': row['item'],
            'period': row['period'],
            'production_cost_cents':
                model.unit_cost.get(key, 0) * row['qty'],
            'produced_units': row['qty'],
            'setup_cost_cents': model.setup_cost.get(key, 0),
        })
    write_jsonl(os.path.join(outdir, 'optimal_plan.jsonl'), plan_rows)

    # ---- production_schedule.csv
    rows = []
    for item in items:
        for period in periods:
            key = (item, period)
            rows.append({
                'item': item,
                'period': period,
                'fiscal_ordinal': ordinal[period],
                'demand_units': model.demand.get(key, 0) or 0,
                'produced_units': model.item_period_produced.get(key, 0),
                'ending_inventory_units': model.ending.get(key, 0),
            })
    write_csv(os.path.join(outdir, 'production_schedule.csv'),
              ['item', 'period', 'fiscal_ordinal', 'demand_units',
               'produced_units', 'ending_inventory_units'], rows)

    # ---- holding_profile.csv
    rows = []
    for item in items:
        cum = 0
        for period in periods:
            key = (item, period)
            charge = model.period_holding.get(key, 0)
            cum += charge
            rows.append({
                'item': item,
                'period': period,
                'fiscal_ordinal': ordinal[period],
                'ending_inventory_units': model.ending.get(key, 0),
                'holding_rate_cents': model.holding_cost.get(key, 0),
                'period_holding_cents': charge,
                'cumulative_holding_cents': cum,
            })
    write_csv(os.path.join(outdir, 'holding_profile.csv'),
              ['item', 'period', 'fiscal_ordinal', 'ending_inventory_units',
               'holding_rate_cents', 'period_holding_cents',
               'cumulative_holding_cents'], rows)

    # ---- sourcing_allocation.csv
    order_index = {}
    for period in periods:
        order = sorted(plants,
                       key=lambda pl: (model.handling[(pl, period)], pl))
        order_index[period] = {pl: i for i, pl in enumerate(order)}
    rows = []
    for row in model.allocation_rows:
        rows.append({
            'period': row['period'],
            'fiscal_ordinal': ordinal[row['period']],
            'plant': row['plant'],
            'item': row['item'],
            'units': row['units'],
            'handling_rate_cents': row['rate'],
            'handling_cost_cents': row['units'] * row['rate'],
            '_ord': ordinal[row['period']],
            '_fill': order_index[row['period']][row['plant']],
        })
    rows.sort(key=lambda r: (r['_ord'], r['_fill'], r['item']))
    write_csv(os.path.join(outdir, 'sourcing_allocation.csv'),
              ['period', 'fiscal_ordinal', 'plant', 'item', 'units',
               'handling_rate_cents', 'handling_cost_cents'], rows)

    # ---- plant_utilization.csv
    rows = []
    full_capacity = []
    zero_capacity = []
    for plant in plants:
        for period in periods:
            key = (plant, period)
            cap = model.capacity.get(key, 0)
            asg = model.assigned.get(key, 0)
            idle = cap - asg
            if idle < 0:
                idle = 0
            util = round_half_up(asg * 10000, cap) if cap else 0
            rows.append({
                'plant': plant,
                'period': period,
                'fiscal_ordinal': ordinal[period],
                'capacity_units': cap,
                'assigned_units': asg,
                'idle_units': idle,
                'utilisation_bps': util,
            })
            if cap > 0 and idle == 0:
                full_capacity.append([plant, period])
            if cap == 0:
                zero_capacity.append([plant, period])
    write_csv(os.path.join(outdir, 'plant_utilization.csv'),
              ['plant', 'period', 'fiscal_ordinal', 'capacity_units',
               'assigned_units', 'idle_units', 'utilisation_bps'], rows)

    # ---- shortfall_ledger.csv
    rows = []
    shortfall_periods = []
    for period in periods:
        req = model.period_required.get(period, 0)
        cap = sum(model.capacity.get((pl, period), 0) for pl in plants)
        short = model.shortfall.get(period, 0)
        if short > 0:
            shortfall_periods.append(period)
        rows.append({
            'period': period,
            'fiscal_ordinal': ordinal[period],
            'required_units': req,
            'capacity_units': cap,
            'shortfall_units': short,
            'penalty_rate_cents': model.shortfall_penalty,
            'penalty_cents': short * model.shortfall_penalty,
        })
    write_csv(os.path.join(outdir, 'shortfall_ledger.csv'),
              ['period', 'fiscal_ordinal', 'required_units', 'capacity_units',
               'shortfall_units', 'penalty_rate_cents', 'penalty_cents'], rows)

    # ---- retrofit_selection.json
    rejected = [pid for pid in model.candidates if pid not in model.selected]
    write_json(os.path.join(outdir, 'retrofit_selection.json'), {
        'budget_cents': model.budget_cents,
        'candidate_project_ids': list(model.candidates),
        'capex_grid_cents': model.capex_grid,
        'eligible_project_count': len(model.candidates),
        'rejected_project_ids': sorted(rejected),
        'selected_capex_cents': model.selected_capex,
        'selected_project_ids': sorted(model.selected),
        'selected_value_cents': model.selected_value,
    })

    # ---- budget_utilization.json
    slack = model.budget_cents - model.selected_capex
    grid = model.capex_grid or 1
    write_json(os.path.join(outdir, 'budget_utilization.json'), {
        'budget_binding': model.budget_binding,
        'budget_cents': model.budget_cents,
        'capex_cents': model.selected_capex,
        'slack_cents': slack,
        'slack_grid_units': slack // grid if slack > 0 else 0,
        'utilisation_bps': round_half_up(model.selected_capex * 10000,
                                        model.budget_cents)
        if model.budget_cents else 0,
    })

    # ---- period_costs.json
    period_costs = {}
    for period in periods:
        prod = 0
        setup = 0
        hold = 0
        for item in items:
            key = (item, period)
            prod += model.unit_cost.get(key, 0) * \
                model.item_period_produced.get(key, 0)
            if model.item_period_produced.get(key, 0) > 0:
                setup += model.setup_cost.get(key, 0)
            hold += model.period_holding.get(key, 0)
        hand = 0
        for row in model.allocation_rows:
            if row['period'] == period:
                hand += row['units'] * row['rate']
        short = model.shortfall.get(period, 0) * model.shortfall_penalty
        period_costs[period] = {
            'handling_cost_cents': hand,
            'holding_cost_cents': hold,
            'production_cost_cents': prod,
            'setup_cost_cents': setup,
            'shortfall_penalty_cents': short,
            'total_cents': prod + setup + hold + hand + short,
        }
    write_json(os.path.join(outdir, 'period_costs.json'), period_costs)

    # ---- item_summary.json
    families = model.families
    summary = {}
    for item in items:
        prod = model.item_production_cost.get(item, 0)
        setup = model.item_setup_cost.get(item, 0)
        hold = model.cum_holding.get(item, 0)
        summary[item] = {
            'demand_units': model.item_demand.get(item, 0),
            'family': families.get(item, ''),
            'holding_cost_cents': hold,
            'produced_units': model.item_produced.get(item, 0),
            'production_cost_cents': prod,
            'setup_count': model.setup_count.get(item, 0),
            'setup_cost_cents': setup,
            'total_cents': prod + setup + hold,
        }
    write_json(os.path.join(outdir, 'item_summary.json'), summary)

    # ---- binding_constraints.json
    binding_count = len(full_capacity) + len(shortfall_periods)
    if model.budget_binding:
        binding_count += 1
    write_json(os.path.join(outdir, 'binding_constraints.json'), {
        'binding_count': binding_count,
        'budget_binding': model.budget_binding,
        'full_capacity_plant_periods': sorted(
            full_capacity, key=lambda x: (x[0], ordinal[x[1]])),
        'shortfall_periods': sorted(shortfall_periods,
                                    key=lambda p: ordinal[p]),
        'zero_capacity_plant_periods': sorted(
            zero_capacity, key=lambda x: (x[0], ordinal[x[1]])),
    })

    # ---- optimality_certificate.json
    write_json(os.path.join(outdir, 'optimality_certificate.json'),
               model.certificate)

    # ---- incumbent_delta.json
    write_json(os.path.join(outdir, 'incumbent_delta.json'),
               model.incumbent_delta)

    # ---- coefficient_corrections.csv
    rows = []
    for item in items:
        for period in periods:
            key = (item, period)
            if key not in model.incumbent_coefficients:
                continue
            old = model.incumbent_coefficients[key]
            new = model.unit_cost.get(key, 0)
            if old != new:
                rows.append({
                    'item': item,
                    'period': period,
                    'fiscal_ordinal': ordinal[period],
                    'incumbent_unit_cost_cents': old,
                    'corrected_unit_cost_cents': new,
                    'delta_cents': new - old,
                    'flags': model.flags.get(key, ''),
                })
    rows.sort(key=lambda r: (r['item'], r['fiscal_ordinal']))
    write_csv(os.path.join(outdir, 'coefficient_corrections.csv'),
              ['item', 'period', 'incumbent_unit_cost_cents',
               'corrected_unit_cost_cents', 'delta_cents', 'flags'], rows)

    # ---- sensitivity_report.json
    write_json(os.path.join(outdir, 'sensitivity_report.json'),
               model.sensitivity)

    # ---- data_quality.json
    write_json(os.path.join(outdir, 'data_quality.json'), model.data_quality)

    # ---- rejected_records.csv
    write_csv(os.path.join(outdir, 'rejected_records.csv'),
              ['source', 'row_uid', 'key', 'reason'], model.rejected)

    # ---- reconciliation.txt and audit_summary.md
    fig = model.reconciliation
    lines = ['%s=%s' % (k, v) for k, v in fig]
    write_text(os.path.join(outdir, 'reconciliation.txt'), '\n'.join(lines) + '\n')
    audit = ['# Replan Audit Summary', '']
    for k, v in fig:
        audit.append('- %s: %s' % (k, v))
    audit.append('')
    audit.append('Selected projects: ' + ', '.join(sorted(model.selected)))
    write_text(os.path.join(outdir, 'audit_summary.md'), '\n'.join(audit) + '\n')


def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: solver.py <DATA_DIR> <OUT_DIR>\n')
        return 2
    indir = argv[1]
    outdir = argv[2]
    model = Model(indir)
    model.run()
    model.compute_figures()
    model.build_reports()
    publish(model, outdir)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
