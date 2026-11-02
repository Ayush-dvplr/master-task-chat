#!/usr/bin/env python3
"""Network replan optimizer.

Rebuilds every cost coefficient from the shipped registers, re-solves the three
stage plan defined by the operating handbook (capital selection, lot sizing,
sourcing) and publishes the plan together with its audit artifacts.

Usage:  python3 solver.py <DATA_DIR> <OUT_DIR>
"""

import csv
import json
import os
import re
import sqlite3
import sys
import zipfile
import zlib
import xml.etree.ElementTree as ET
from fractions import Fraction

# --------------------------------------------------------------------------
# generic helpers
# --------------------------------------------------------------------------

DELIMS = {'csv': ',', 'tsv': '\t', 'psv': '|'}
SHEET_NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
RECORD_PREFIX = 'R|'


def rhu(num, den):
    """round half up, away from zero."""
    if den < 0:
        num, den = -num, -den
    if num >= 0:
        return (2 * num + den) // (2 * den)
    return -((-2 * num + den) // (2 * den))


def norm_code(value):
    if value is None:
        return ''
    s = re.sub(r'\s+', '', str(value)).upper()
    s = s.replace('-', '').replace('_', '')
    m = re.match(r'^(.*?)(\d+)$', s)
    if m:
        s = m.group(1) + m.group(2).rjust(2, '0')
    return s


def as_int(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    s = str(value).strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        try:
            f = float(s)
        except ValueError:
            return None
        return int(f) if f == int(f) else None


# --------------------------------------------------------------------------
# tiny yaml reader (indentation based mappings, scalars and sequences)
# --------------------------------------------------------------------------

def yaml_scalar(token):
    token = token.strip()
    if len(token) >= 2 and token[0] == token[-1] and token[0] in ("'", '"'):
        return token[1:-1]
    if token.lower() in ('true', 'false'):
        return token.lower() == 'true'
    return token


def load_yaml(text):
    """Indentation based yaml subset: nested mappings, scalars, sequences."""
    lines = []
    for raw in text.split('\n'):
        if not raw.strip() or raw.lstrip().startswith('#'):
            continue
        lines.append(raw)
    pos = [0]

    def block(indent):
        node = None
        while pos[0] < len(lines):
            raw = lines[pos[0]]
            cur = len(raw) - len(raw.lstrip(' '))
            if cur < indent:
                break
            line = raw.strip()
            if line.startswith('- '):
                if cur > indent and node is not None:
                    break
                if node is None:
                    node = []
                if not isinstance(node, list):
                    break
                pos[0] += 1
                node.append(yaml_scalar(line[2:]))
                continue
            if cur > indent:
                break
            if ':' not in line:
                pos[0] += 1
                continue
            key, _, rest = line.partition(':')
            key = key.strip()
            rest = rest.strip()
            pos[0] += 1
            if node is None:
                node = {}
            if not isinstance(node, dict):
                break
            if rest:
                node[key] = yaml_scalar(rest)
            else:
                nxt_indent = None
                if pos[0] < len(lines):
                    nraw = lines[pos[0]]
                    nxt_indent = len(nraw) - len(nraw.lstrip(' '))
                if nxt_indent is not None and nxt_indent > cur:
                    node[key] = block(nxt_indent)
                else:
                    node[key] = {}
        return node if node is not None else {}

    return block(0)


# --------------------------------------------------------------------------
# format readers
# --------------------------------------------------------------------------

def read_delimited(path, delim):
    with open(path, newline='', encoding='utf-8') as fh:
        rows = list(csv.reader(fh, delimiter=delim))
    if not rows:
        return []
    header = rows[0]
    out = []
    for row in rows[1:]:
        if not row:
            continue
        out.append(dict(zip(header, row)))
    return out


def read_jsonlines(path):
    out = []
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            if line.strip():
                out.append(json.loads(line))
    return out


def read_json_records(path):
    with open(path, encoding='utf-8') as fh:
        doc = json.load(fh)
    if isinstance(doc, dict):
        for key in ('records', 'rows', 'entries'):
            if key in doc and isinstance(doc[key], list):
                return doc[key]
        return []
    return doc if isinstance(doc, list) else []


def read_xml(path):
    root = ET.parse(path).getroot()
    return [dict(child.attrib) for child in root]


def read_text_rows(path):
    """plain text register: hash comments, one pipe separated record per line.

    A comment of the form "# fixed column order: a|b|c" names the columns.
    """
    header = None
    out = []
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith('#'):
                low = stripped.lower()
                if 'column order' in low and '|' in stripped:
                    header = stripped.split(':', 1)[1].strip().split('|')
                continue
            if header and '|' in stripped:
                out.append(dict(zip(header, stripped.split('|'))))
            else:
                out.append({'line': stripped})
    return out


def read_nonhash_lines(path):
    out = []
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                out.append({'line': line.rstrip('\n')})
    return out


def read_sqlite_rows(path):
    con = sqlite3.connect(path)
    try:
        tables = [r[0] for r in con.execute(
            "select name from sqlite_master where type='table' "
            "and name not like 'sqlite_%' order by name")]
        out = []
        for table in tables:
            cur = con.execute('select * from "%s"' % table)
            cols = [d[0] for d in cur.description]
            for row in cur.fetchall():
                rec = dict(zip(cols, row))
                rec['__table'] = table
                out.append(rec)
        return out
    finally:
        con.close()


def _cell_text(cell):
    node = cell.find(SHEET_NS + 'v')
    if node is not None:
        return node.text
    inline = cell.find(SHEET_NS + 'is/' + SHEET_NS + 't')
    if inline is not None:
        return inline.text
    return None


def read_xlsx(path):
    zf = zipfile.ZipFile(path)
    try:
        names = sorted(n for n in zf.namelist()
                       if n.startswith('xl/worksheets/sheet') and n.endswith('.xml'))
        out = []
        for name in names:
            root = ET.fromstring(zf.read(name))
            rows = root.findall('.//' + SHEET_NS + 'row')
            if not rows:
                continue
            header = [(_cell_text(c) or '') for c in rows[0]]
            for row in rows[1:]:
                values = [_cell_text(c) for c in row]
                rec = dict(zip(header, values))
                rec['__sheet'] = name
                out.append(rec)
        return out
    finally:
        zf.close()


def _pdf_text(path):
    with open(path, 'rb') as fh:
        blob = fh.read()
    chunks = []
    for match in re.finditer(rb'stream\r?\n(.*?)endstream', blob, re.S):
        data = match.group(1)
        try:
            chunks.append(zlib.decompress(data).decode('latin-1'))
        except zlib.error:
            chunks.append(data.decode('latin-1', 'replace'))
    return '\n'.join(chunks)


def read_pdf_records(path):
    text = _pdf_text(path)
    out = []
    for line in re.findall(r'\((.*?)\)\s*Tj', text, re.S):
        if line.startswith(RECORD_PREFIX):
            out.append({'line': line, 'fields': line.split('|')})
    return out


def read_docx_records(path):
    zf = zipfile.ZipFile(path)
    try:
        xml = zf.read('word/document.xml').decode('utf-8')
    finally:
        zf.close()
    out = []
    for para in re.findall(r'<w:p[ >].*?</w:p>', xml, re.S):
        text = ''.join(re.findall(r'<w:t[^>]*>(.*?)</w:t>', para, re.S))
        if text.startswith(RECORD_PREFIX):
            out.append({'line': text, 'fields': text.split('|')})
    return out


LINE_FORMATS = {'txt', 'md', 'yaml', 'yml'}
DELIMITED = set(DELIMS)
SWEEP_FORMATS = DELIMITED | {'jsonl', 'ndjson', 'json', 'xml', 'txt'}


def read_source(path, fmt):
    if fmt in DELIMS:
        return read_delimited(path, DELIMS[fmt])
    if fmt in ('jsonl', 'ndjson'):
        return read_jsonlines(path)
    if fmt == 'json':
        return read_json_records(path)
    if fmt == 'xml':
        return read_xml(path)
    if fmt == 'txt':
        return read_text_rows(path)
    if fmt in ('md', 'yaml', 'yml'):
        return read_nonhash_lines(path)
    if fmt in ('db', 'sqlite'):
        return read_sqlite_rows(path)
    if fmt == 'xlsx':
        return read_xlsx(path)
    if fmt == 'pdf':
        return read_pdf_records(path)
    if fmt == 'docx':
        return read_docx_records(path)
    return []


# --------------------------------------------------------------------------
# corpus
# --------------------------------------------------------------------------

class Source(object):
    def __init__(self, name, role, fmt, record_count, authority, rows):
        self.name = name
        self.role = role
        self.fmt = fmt
        self.record_count = record_count
        self.authority = authority
        self.rows = rows

    @property
    def rows_seen(self):
        return len(self.rows)


def find_manifest(data_dir):
    for name in sorted(os.listdir(data_dir)):
        path = os.path.join(data_dir, name)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, 'rb') as fh:
                if fh.read(16) != b'SQLite format 3\x00':
                    continue
        except OSError:
            continue
        con = sqlite3.connect(path)
        try:
            tables = {r[0] for r in con.execute(
                "select name from sqlite_master where type='table'")}
            if 'sources' in tables:
                rows = list(con.execute(
                    'select name, role, fmt, record_count, authority from sources'))
                return name, rows
        except sqlite3.DatabaseError:
            pass
        finally:
            con.close()
    raise SystemExit('no source manifest found in %s' % data_dir)


class Corpus(object):
    def __init__(self, data_dir):
        self.dir = data_dir
        self.manifest_name, manifest = find_manifest(data_dir)
        self.sources = []
        for name, role, fmt, record_count, authority in manifest:
            path = os.path.join(data_dir, name)
            rows = read_source(path, fmt) if os.path.exists(path) else []
            self.sources.append(
                Source(name, role, fmt, int(record_count), authority, rows))
        self.sources.sort(key=lambda s: s.name)
        self.by_name = {s.name: s for s in self.sources}

    def of_role(self, role, authorities=('primary', 'contract')):
        return [s for s in self.sources
                if s.role == role and s.authority in authorities]

    def rows_of_role(self, role, authorities=('primary', 'contract')):
        """Rows of a logical register in canonical order with provenance."""
        out = []
        for src in sorted(self.of_role(role, authorities), key=lambda s: s.name):
            for idx, row in enumerate(src.rows):
                out.append(Rec(src.name, idx, row))
        for order, rec in enumerate(out):
            rec.order = order
        return out


class Rec(object):
    __slots__ = ('src', 'idx', 'row', 'order')

    def __init__(self, src, idx, row):
        self.src = src
        self.idx = idx
        self.row = row
        self.order = 0

    def get(self, *names):
        for name in names:
            if name in self.row:
                return self.row[name]
        return None

    def has(self, *names):
        return any(name in self.row for name in names)


# --------------------------------------------------------------------------
# the plan
# --------------------------------------------------------------------------

class Plan(object):
    def __init__(self, data_dir, out_dir):
        self.out_dir = out_dir
        self.corpus = Corpus(data_dir)
        self.load_contract()
        self.build_lifecycle()
        self.load_documents()
        self.build_horizon()
        self.build_items()
        self.build_plants()
        self.build_demand()
        self.build_coefficients()
        self.build_capacity()
        self.build_handling_base()
        self.capital_selection()
        self.apply_retrofits()
        self.lot_sizing()
        self.sourcing()
        self.assemble_objective()
        self.sweep()
        self.incumbent()

    # ---------------- contract ----------------

    def load_contract(self):
        cps = self.corpus
        cfg_src = cps.of_role('contract_config', ('contract',))
        text = ''
        if cfg_src:
            with open(os.path.join(cps.dir, cfg_src[0].name), encoding='utf-8') as fh:
                text = fh.read()
        self.runbook = load_yaml(text) if text else {}
        control = self.runbook.get('control', {}) or {}

        nom_src = cps.of_role('contract_nomenclature', ('contract',))
        nom_text = ''
        if nom_src:
            with open(os.path.join(cps.dir, nom_src[0].name), encoding='utf-8') as fh:
                nom_text = fh.read()
        self.nomen = load_yaml(nom_text) if nom_text else {}

        ctl = {}
        for src in cps.of_role('authority_control', ('contract',)):
            for row in src.rows:
                if row.get('__table') == 'cutoff_control':
                    ctl[str(row.get('parameter'))] = row.get('value')
        self.authority_control = ctl
        self.scale_factors = {}
        for src in cps.of_role('authority_control', ('contract',)):
            for row in src.rows:
                if row.get('__table') == 'scale_authority':
                    self.scale_factors[str(row.get('token'))] = as_int(row.get('factor'))

        def param(name, default=None):
            if name in control:
                return control[name]
            if name in ctl:
                return ctl[name]
            return default

        self.cutoff = as_int(param('plan_sequence_cutoff'))
        self.capex_grid = as_int(param('capex_grid_cents'))
        self.default_setup = as_int(param('default_setup_cents'))
        self.min_handling = as_int(param('minimum_handling_cents'))
        self.fy_start_period = norm_code(param('fiscal_year_start_period'))

        sentinels = self.nomen.get('sentinel_tokens')
        tokens = set()
        if isinstance(sentinels, list):
            for tok in sentinels:
                tokens.add(str(tok).strip())
        for src in cps.of_role('authority_control', ('contract',)):
            for row in src.rows:
                if row.get('__table') == 'sentinel_authority':
                    tok = str(row.get('token'))
                    tokens.add('' if tok == '<empty>' else tok.strip())
        self.sentinels = tokens

        aliases = self.nomen.get('header_aliases', {}) or {}

        def alias(key, fallback):
            vals = aliases.get(key)
            if isinstance(vals, list) and vals:
                return [str(v) for v in vals]
            return fallback

        self.item_cols = alias('item_code', ['item', 'item_code', 'sku', 'code'])
        self.period_cols = alias('period_code', ['period', 'period_code'])
        self.plant_cols = alias('plant_code', ['plant', 'plant_code'])
        self.units_cols = alias('demand_units', ['units', 'qty', 'planned_units'])
        self.dozen_cols = alias('demand_units_dozens', ['units_dz'])
        self.item_defaults = self.runbook.get('item_defaults', {}) or {}

    def is_sentinel(self, value):
        if value is None:
            return True
        return str(value).strip() in self.sentinels

    def row_has_sentinel(self, rec):
        for key, value in rec.row.items():
            if key.startswith('__'):
                continue
            if self.is_sentinel(value):
                return True
        return False

    def scale(self, token):
        if token is None:
            return 1
        tok = str(token).strip()
        if tok in self.scale_factors and self.scale_factors[tok]:
            return self.scale_factors[tok]
        tokens = self.nomen.get('scale_tokens', {}) or {}
        if tok in tokens:
            return as_int(tokens[tok]) or 1
        return 1

    # ---------------- lifecycle ----------------

    def build_lifecycle(self):
        entries = {}
        for rec in self.corpus.rows_of_role('row_lifecycle'):
            uid = rec.get('row_uid')
            seq = as_int(rec.get('seq', 'effective_seq'))  # the log dates itself by seq
            action = str(rec.get('action') or '').strip().lower()
            if uid is None or seq is None:
                continue
            if seq > self.cutoff:
                continue
            entries.setdefault(str(uid).strip(), []).append((seq, rec.order, action))
        self.lifecycle_voided = set()
        self.lifecycle_touched_void = set()
        for uid, items in entries.items():
            items.sort()
            state = None
            for _, _, action in items:
                if action in ('void', 'restore'):
                    state = action
                if action == 'void':
                    self.lifecycle_touched_void.add(uid)
            if state == 'void':
                self.lifecycle_voided.add(uid)

    def uid(self, rec):
        value = rec.get('row_uid')
        return None if value is None else str(value).strip()

    def seq(self, rec):
        """planning sequence of a register row; the lifecycle log carries none."""
        return as_int(rec.get('effective_seq'))

    def rev(self, rec):
        return as_int(rec.get('rev')) or 0

    def own_void(self, rec):
        value = rec.get('void')
        if value is None:
            return False
        return (as_int(value) or 0) != 0

    def above_cutoff(self, rec):
        seq = self.seq(rec)
        return seq is not None and seq > self.cutoff

    def blocked(self, rec):
        return self.own_void(rec) or (self.uid(rec) in self.lifecycle_voided)

    def is_live(self, rec):
        if self.above_cutoff(rec):
            return False
        if self.blocked(rec):
            return False
        if self.row_has_sentinel(rec):
            return False
        return True

    # ---------------- selection primitives ----------------

    def winners(self, role, keyfn):
        best = {}
        for rec in self.corpus.rows_of_role(role):
            if not self.is_live(rec):
                continue
            key = keyfn(rec)
            if key is None:
                continue
            rank = (self.rev(rec), self.seq(rec) or 0, rec.order)
            if key not in best or rank > best[key][0]:
                best[key] = (rank, rec)
        return {k: v[1] for k, v in best.items()}

    def accumulated(self, role, keyfn, idfn, valfn):
        seen = set()
        totals = {}
        used = {}
        for rec in self.corpus.rows_of_role(role):
            if not self.is_live(rec):
                continue
            ident = idfn(rec)
            if ident in seen:
                continue
            seen.add(ident)
            key = keyfn(rec)
            if key is None:
                continue
            value = valfn(rec)
            if value is None:
                continue
            totals[key] = totals.get(key, 0) + value
            used.setdefault(key, []).append(rec)
        return totals, used

    def item_of(self, rec):
        value = rec.get(*self.item_cols)
        return norm_code(value) if value is not None else None

    def period_of(self, rec):
        value = rec.get(*self.period_cols)
        if value is not None:
            return norm_code(value)
        if rec.has('date'):
            return self.calendar.get(str(rec.get('date')).strip())
        return None

    def plant_of(self, rec):
        value = rec.get(*self.plant_cols)
        return norm_code(value) if value is not None else None

    # ---------------- documents ----------------

    def doc_params(self, role):
        """PARAM records of a document register, keyed by parameter name."""
        best = {}
        for src in self.corpus.of_role(role):
            for idx, row in enumerate(src.rows):
                fields = row.get('fields')
                if not fields or len(fields) < 9 or fields[1] != 'PARAM':
                    continue
                name, value, unit, rev, seq, void, uid = fields[2:9]
                seq_i = as_int(seq)
                if seq_i is None or seq_i > self.cutoff:
                    continue
                if (as_int(void) or 0) != 0:
                    continue
                if str(uid).strip() in self.lifecycle_voided:
                    continue
                if self.is_sentinel(value) or self.is_sentinel(unit):
                    continue
                rank = (as_int(rev) or 0, seq_i, idx)
                if name not in best or rank > best[name][0]:
                    best[name] = (rank, value, unit)
        return {k: (v[1], v[2]) for k, v in best.items()}

    def load_documents(self):
        memo = self.doc_params('energy_memo')
        value, unit = memo.get('energy_surcharge', (0, 'bps'))
        self.energy_surcharge_bps = (as_int(value) or 0) * self.scale_unit(unit)

        schedule = self.doc_params('penalty_schedule')
        value, unit = schedule.get('holding_rate', (0, 'bps'))
        self.holding_rate_bps = (as_int(value) or 0) * self.scale_unit(unit)
        value, unit = schedule.get('shortfall_penalty_per_unit', (0, 'cents'))
        self.shortfall_penalty = (as_int(value) or 0) * self.scale(unit)

        # capital programme workbook
        control_rows = []
        volume_rows = []
        for src in self.corpus.of_role('capital_programme'):
            for idx, row in enumerate(src.rows):
                rec = Rec(src.name, idx, row)
                rec.order = idx
                if 'parameter' in row:
                    control_rows.append(rec)
                elif 'project_id' in row:
                    volume_rows.append(rec)
        best = {}
        for rec in control_rows:
            if not self.is_live(rec):
                continue
            name = str(rec.get('parameter')).strip()
            rank = (self.rev(rec), self.seq(rec) or 0, rec.order)
            if name not in best or rank > best[name][0]:
                best[name] = (rank, rec)
        self.budget_cents = 0
        if 'capital_budget' in best:
            rec = best['capital_budget'][1]
            self.budget_cents = (as_int(rec.get('value')) or 0) * self.scale(rec.get('unit'))
        if 'capex_grid' in best:
            grid = as_int(best['capex_grid'][1].get('value'))
            if grid:
                self.capex_grid = grid * self.scale(best['capex_grid'][1].get('unit'))
        best_vol = {}
        for rec in volume_rows:
            if not self.is_live(rec):
                continue
            project = norm_code(rec.get('project_id'))
            rank = (self.rev(rec), self.seq(rec) or 0, rec.order)
            if project not in best_vol or rank > best_vol[project][0]:
                best_vol[project] = (rank, rec)
        self.committed_volume = {
            p: (as_int(r[1].get('committed_volume_units', 'committed_volume')) or 0)
            for p, r in best_vol.items()}

    def scale_unit(self, unit):
        """index and uplift columns: pct reaches basis points, bps is one."""
        tok = str(unit or '').strip()
        if tok == 'pct':
            return self.scale('pct') or 100
        return 1

    # ---------------- horizon, items, plants ----------------

    def build_horizon(self):
        cal = {}
        for rec in self.corpus.rows_of_role('calendar'):
            if not self.is_live(rec):
                continue
            date = rec.get('date')
            period = rec.get(*self.period_cols)
            if date is None or period is None:
                continue
            cal[str(date).strip()] = norm_code(period)
        self.calendar = cal

        winners = self.winners('period_order', lambda r: norm_code(r.get(*self.period_cols)))
        periods = []
        for period, rec in winners.items():
            ordinal = as_int(rec.get('fiscal_ordinal'))
            if ordinal is None:
                continue
            periods.append((ordinal, period, (as_int(rec.get('fy_start')) or 0) != 0))
        periods.sort(key=lambda x: (x[0], x[1]))
        self.periods = [p for _, p, _ in periods]
        self.ordinal = {p: i + 1 for i, p in enumerate(self.periods)}
        self.declared_ordinal = {p: o for o, p, _ in periods}
        self.fy_start_flagged = [p for _, p, flag in periods if flag]

    def build_items(self):
        self.item_status = {}
        for item, rec in self.winners('item_status', self.item_of).items():
            self.item_status[item] = str(rec.get('status') or '').strip().lower()
        self.items = sorted(i for i, s in self.item_status.items() if s != 'retired')
        self.retired_items = {i for i, s in self.item_status.items() if s == 'retired'}
        self.item_family = {}
        for item, rec in self.winners('item_family', self.item_of).items():
            self.item_family[item] = str(rec.get('family') or '').strip()
        for item in self.items:
            if not self.item_family.get(item):
                default = self.item_defaults.get(item, {})
                if isinstance(default, dict) and default.get('family'):
                    self.item_family[item] = str(default['family'])

    def build_plants(self):
        status = {}
        for rec in self.corpus.rows_of_role('plant_status'):
            if not self.is_live(rec):
                continue
            plant = self.plant_of(rec)
            period = self.period_of(rec)
            if plant is None or period is None:
                continue
            rank = (self.rev(rec), self.seq(rec) or 0, rec.order)
            key = (plant, period)
            if key not in status or rank > status[key][0]:
                status[key] = (rank, str(rec.get('status') or '').strip().lower())
        self.plant_period_status = {k: v[1] for k, v in status.items()}
        self.plants = sorted({p for p, _ in self.plant_period_status})

    # ---------------- demand ----------------

    def build_demand(self):
        recs = []
        for role in ('demand', 'demand_overlay'):
            recs.extend(self.corpus.rows_of_role(role))
        recs.sort(key=lambda r: (r.src, r.idx))
        for order, rec in enumerate(recs):
            rec.order = order
        best = {}
        for rec in recs:
            if not self.is_live(rec):
                continue
            item = self.item_of(rec)
            period = self.period_of(rec)
            if item is None or period is None:
                continue
            if item not in self.item_status or self.item_status[item] == 'retired':
                continue
            if period not in self.ordinal:
                continue
            units = self.demand_units(rec)
            if units is None:
                continue
            rank = (self.rev(rec), self.seq(rec) or 0, rec.order)
            key = (item, period)
            if key not in best or rank > best[key][0]:
                best[key] = (rank, units)
        self.demand = {k: v[1] for k, v in best.items()}

    def demand_units(self, rec):
        for col in self.dozen_cols:
            if col in rec.row:
                value = as_int(rec.row[col])
                return None if value is None else value * (self.scale('units_dz') or 12)
        for col in self.units_cols:
            if col in rec.row:
                return as_int(rec.row[col])
        return None

    def dem(self, item, period):
        return self.demand.get((item, period), 0)

    # ---------------- coefficients ----------------

    def build_coefficients(self):
        key_of = lambda r: ((self.item_of(r), self.period_of(r))
                            if self.item_of(r) and self.period_of(r) else None)

        base_win = self.winners('unit_cost', key_of)
        override_win = self.winners('cost_override', key_of)
        setup_win = self.winners('setup_cost', key_of)
        amend_totals, amend_used = self.accumulated(
            'cost_amendment', key_of,
            lambda r: ('amend_id', str(r.get('amend_id')).strip()),
            self.amend_value)

        fx = None
        best_rank = None
        for rec in self.corpus.rows_of_role('fx_rate'):
            if not self.is_live(rec):
                continue
            rate = as_int(rec.get('usd_per_eur_micros'))
            if rate is None:
                continue
            rank = (self.seq(rec) or 0, self.rev(rec), rec.order)
            if best_rank is None or rank > best_rank:
                best_rank, fx = rank, rate
        self.fx_micros = fx if fx is not None else 1000000

        energy_win = self.winners('energy_index', lambda r: self.period_of(r))
        self.energy_bps = {}
        for period in self.periods:
            rec = energy_win.get(period)
            value = as_int(rec.get('index_value', 'index_bps')) if rec is not None else 0
            unit = rec.get('unit') if rec is not None else 'bps'
            self.energy_bps[period] = (value or 0) * self.scale_unit(unit)

        # CUT and VOI evidence over the three cost registers for the key
        cut = set()
        voi = set()
        for role in ('unit_cost', 'cost_amendment', 'cost_override'):
            for rec in self.corpus.rows_of_role(role):
                key = key_of(rec)
                if key is None:
                    continue
                if self.above_cutoff(rec):
                    cut.add(key)
                elif self.own_void(rec) or self.uid(rec) in self.lifecycle_touched_void:
                    voi.add(key)

        self.unit_cost = {}
        self.setup_cost = {}
        self.holding_rate = {}
        self.flags = {}
        micros_den = self.scale('micros_denominator') or 1000000
        bps_den = self.scale('bps_denominator') or 10000
        for item in self.items:
            for period in self.periods:
                key = (item, period)
                letters = set()
                value = 0
                rec = base_win.get(key)
                if rec is not None:
                    amount = as_int(rec.get('amount')) or 0
                    scale_token = str(rec.get('scale') or '').strip()
                    value = amount * self.scale(scale_token)
                    if scale_token == 'kcents':
                        letters.add('KC')
                    if str(rec.get('ccy') or '').strip().upper() == 'EUR':
                        letters.add('FX')
                        value = rhu(value * self.fx_micros, micros_den)
                amend = amend_totals.get(key)
                if amend:
                    value += amend
                    letters.add('AMD')
                elif key in amend_used:
                    letters.add('AMD')
                orec = override_win.get(key)
                if orec is not None:
                    value = as_int(orec.get('amount')) or 0
                    letters.add('OVR')
                bps = self.energy_bps.get(period, 0) + self.energy_surcharge_bps
                uplift = rhu(value * bps, bps_den)
                if uplift:
                    letters.add('ENR')
                value += uplift
                if key in cut:
                    letters.add('CUT')
                if key in voi:
                    letters.add('VOI')
                self.unit_cost[key] = value
                self.flags[key] = '+'.join(sorted(letters))
                srec = setup_win.get(key)
                if srec is not None:
                    self.setup_cost[key] = ((as_int(srec.get('amount')) or 0)
                                            * self.scale(srec.get('scale')))
                else:
                    default = self.item_defaults.get(item, {})
                    fallback = None
                    if isinstance(default, dict):
                        fallback = as_int(default.get('setup_fallback_cents'))
                    self.setup_cost[key] = (fallback if fallback is not None
                                            else self.default_setup)
                self.holding_rate[key] = rhu(value * self.holding_rate_bps, bps_den)

    def amend_value(self, rec):
        amount = as_int(rec.get('amount'))
        if amount is None:
            return None
        sign = str(rec.get('sign') or '').strip().lower()
        return -amount if sign == 'credit' else amount

    # ---------------- capacity and handling ----------------

    def build_capacity(self):
        pair = lambda r: ((self.plant_of(r), self.period_of(r))
                          if self.plant_of(r) and self.period_of(r) else None)
        base_win = self.winners('capacity_base', pair)
        adj_totals, _ = self.accumulated(
            'capacity_adjustment', pair,
            lambda r: ('adj_id', str(r.get('adj_id')).strip()),
            lambda r: as_int(r.get('delta_units', 'adjustment_units')))
        shift_win = self.winners('shift_pattern', lambda r: self.plant_of(r))
        derate_win = self.winners('holiday_derate', lambda r: self.period_of(r))
        bps_den = self.scale('bps_denominator') or 10000

        self.shift_bps = {}
        for plant in self.plants:
            rec = shift_win.get(plant)
            self.shift_bps[plant] = ((as_int(rec.get('shift_value', 'shift_bps')) or 0)
                                     * self.scale_unit(rec.get('unit'))
                                     if rec is not None else bps_den)
        self.derate_bps = {}
        for period in self.periods:
            rec = derate_win.get(period)
            self.derate_bps[period] = ((as_int(rec.get('derate_value', 'derate_bps')) or 0)
                                       * self.scale_unit(rec.get('unit'))
                                       if rec is not None else bps_den)

        self.capacity = {}
        for plant in self.plants:
            for period in self.periods:
                key = (plant, period)
                if self.plant_period_status.get(key) == 'mothballed':
                    self.capacity[key] = 0
                    continue
                rec = base_win.get(key)
                base = as_int(rec.get('base_capacity_units', 'capacity_units')) if rec is not None else 0
                base = base or 0
                total = base + adj_totals.get(key, 0)
                value = rhu(rhu(total * self.shift_bps[plant], bps_den)
                            * self.derate_bps[period], bps_den)
                self.capacity[key] = max(0, value)

    def build_handling_base(self):
        pair = lambda r: ((self.plant_of(r), self.period_of(r))
                          if self.plant_of(r) and self.period_of(r) else None)
        base_win = self.winners('handling_base', pair)
        adj_totals, _ = self.accumulated(
            'handling_adjustment', pair,
            lambda r: ('adj_id', str(r.get('adj_id')).strip()),
            lambda r: as_int(r.get('delta_cents', 'adjustment_cents')))
        zone_win = self.winners('plant_zone', lambda r: self.plant_of(r))
        tariff_win = self.winners('zone_tariff', lambda r: norm_code(r.get('zone')))
        bps_den = self.scale('bps_denominator') or 10000

        self.plant_zone = {p: norm_code(r.get('zone')) for p, r in zone_win.items()}
        self.zone_uplift = {
            z: (as_int(r.get('uplift_value', 'uplift_bps')) or 0) * self.scale_unit(r.get('unit'))
            for z, r in tariff_win.items()}

        self.handling_pre = {}
        for plant in self.plants:
            uplift = self.zone_uplift.get(self.plant_zone.get(plant), 0)
            for period in self.periods:
                key = (plant, period)
                rec = base_win.get(key)
                base = as_int(rec.get('handling_cents_per_unit', 'handling_rate_cents')) if rec is not None else 0
                base = base or 0
                total = base + adj_totals.get(key, 0)
                self.handling_pre[key] = rhu(total * (bps_den + uplift), bps_den)

    # ---------------- stage one: capital ----------------

    def capital_selection(self):
        project_win = self.winners('retrofit_project', lambda r: norm_code(r.get('project_id')))
        capex_win = self.winners('retrofit_capex', lambda r: norm_code(r.get('project_id')))
        saving_win = self.winners('retrofit_savings', lambda r: norm_code(r.get('project_id')))
        elig_win = self.winners('retrofit_eligibility', lambda r: norm_code(r.get('project_id')))
        micros_den = self.scale('micros_denominator') or 1000000

        self.project_plant = {p: self.plant_of(r) for p, r in project_win.items()}
        self.project_capex = {}
        for project, rec in capex_win.items():
            self.project_capex[project] = ((as_int(rec.get('amount')) or 0)
                                           * self.scale(rec.get('scale')))
        self.project_saving = {}
        for project, rec in saving_win.items():
            value = as_int(rec.get('savings_value', 'unit_saving_cents')) or 0
            if str(rec.get('ccy') or '').strip().upper() == 'EUR':
                value = rhu(value * self.fx_micros, micros_den)
            self.project_saving[project] = value

        candidates = sorted(
            p for p, rec in elig_win.items()
            if str(rec.get('eligible') or '').strip().lower() == 'yes')
        self.candidates = candidates
        self.project_value = {
            p: self.project_saving.get(p, 0) * self.committed_volume.get(p, 0)
            for p in candidates}

        grid = self.capex_grid or 1
        self.grid_capacity = self.budget_cents // grid
        weights = [self.project_capex.get(p, 0) // grid for p in candidates]
        values = [self.project_value.get(p, 0) for p in candidates]
        self.knapsack_weights = weights
        self.knapsack_values = values
        # no selection can consume more than the whole candidate list
        reach = min(self.grid_capacity, sum(weights))
        self.knapsack_table = self.solve_knapsack(weights, values, reach)
        value, used, mask = self.best_of(self.knapsack_table, self.grid_capacity)
        self.selected = [candidates[i] for i in range(len(candidates)) if mask >> i & 1]
        self.selected_value = value
        self.selected_capex = used * grid
        self.rejected_projects = [p for p in candidates if p not in set(self.selected)]

        reach2 = min(self.grid_capacity + 1, sum(weights))
        table2 = (self.knapsack_table if reach2 == reach
                  else self.solve_knapsack(weights, values, reach2))
        value2, _, _ = self.best_of(table2, self.grid_capacity + 1)
        self.marginal_grid_value = value2 - value
        self.budget_binding = self.marginal_grid_value > 0

    @staticmethod
    def solve_knapsack(weights, values, capacity):
        """exact dp keyed by capex consumed; value maximal, then mask minimal."""
        neg = None
        table = [neg] * (capacity + 1)
        table[0] = (0, 0)
        for i, (weight, value) in enumerate(zip(weights, values)):
            if weight > capacity:
                continue
            for used in range(capacity - weight, -1, -1):
                cur = table[used]
                if cur is None:
                    continue
                cand = (cur[0] + value, cur[1] | (1 << i))
                target = used + weight
                old = table[target]
                if old is None or (cand[0] > old[0]
                                   or (cand[0] == old[0] and cand[1] < old[1])):
                    table[target] = cand
        return table

    @staticmethod
    def best_of(table, capacity):
        """highest value, then lowest capex, then smallest indicator."""
        best = None
        for used in range(0, min(capacity, len(table) - 1) + 1):
            cell = table[used]
            if cell is None:
                continue
            cand = (-cell[0], used, cell[1])
            if best is None or cand < best:
                best = cand
        return (-best[0], best[1], best[2])

    def apply_retrofits(self):
        saving_by_plant = {}
        for project in self.selected:
            plant = self.project_plant.get(project)
            if plant is None:
                continue
            saving_by_plant[plant] = (saving_by_plant.get(plant, 0)
                                      + self.project_saving.get(project, 0))
        self.plant_saving = saving_by_plant
        self.handling = {}
        for (plant, period), rate in self.handling_pre.items():
            value = rate - saving_by_plant.get(plant, 0)
            self.handling[(plant, period)] = max(self.min_handling, value)

    # ---------------- stage two: lot sizing ----------------

    def lot_sizing(self):
        self.production = {}
        self.inventory = {}
        self.lots = []
        periods = self.periods
        count = len(periods)
        self.item_cost = {}
        for item in self.items:
            demand = [self.dem(item, p) for p in periods]
            unit = [self.unit_cost[(item, p)] for p in periods]
            setup = [self.setup_cost[(item, p)] for p in periods]
            hold = [self.holding_rate[(item, p)] for p in periods]
            block_cost = {}
            for start in range(count):
                total = 0
                accrued = 0
                rate_sum = 0
                for end in range(start, count):
                    # demand of period end is carried out of periods start..end-1
                    if end > start:
                        accrued += demand[end] * rate_sum
                    total += demand[end]
                    cost = 0 if total == 0 else (setup[start] + unit[start] * total + accrued)
                    block_cost[(start, end + 1)] = (cost, total > 0)
                    rate_sum += hold[end]
            # suffix dp: (cost, descending production period key)
            best = [None] * (count + 1)
            best[count] = (0, ())
            choice = [None] * (count + 1)
            for start in range(count - 1, -1, -1):
                winner = None
                winner_end = None
                for end in range(start + 1, count + 1):
                    cost, opens = block_cost[(start, end)]
                    tail = best[end]
                    if tail is None:
                        continue
                    key = tail[1] + ((start,) if opens else ())
                    cand = (cost + tail[0], key)
                    if winner is None or self.schedule_less(cand, winner):
                        winner, winner_end = cand, end
                best[start] = winner
                choice[start] = winner_end
            total_cost = best[0][0]
            self.item_cost[item] = total_cost
            start = 0
            while start < count:
                end = choice[start]
                cost, opens = block_cost[(start, end)]
                quantity = sum(demand[start:end])
                if opens:
                    covered = [periods[j] for j in range(start, end) if demand[j] > 0]
                    self.lots.append({
                        'item': item,
                        'period': periods[start],
                        'produced_units': quantity,
                        'covers_periods': covered,
                        'setup_cost_cents': setup[start],
                        'production_cost_cents': unit[start] * quantity,
                    })
                for j in range(start, end):
                    self.production[(item, periods[j])] = quantity if j == start else 0
                start = end
            inventory = 0
            for idx, period in enumerate(periods):
                inventory += self.production.get((item, period), 0) - demand[idx]
                self.inventory[(item, period)] = inventory

    @staticmethod
    def schedule_less(a, b):
        """lower cost wins; ties compare production periods from the last back."""
        if a[0] != b[0]:
            return a[0] < b[0]
        return a[1] < b[1]

    # ---------------- stage three: sourcing ----------------

    def sourcing(self):
        self.allocation = []
        self.assigned = {}
        self.fill_rank = {}
        self.shortfall = {}
        self.required = {}
        for plant in self.plants:
            for period in self.periods:
                self.assigned[(plant, period)] = 0
        for period in self.periods:
            stream = [(item, self.production.get((item, period), 0))
                      for item in self.items
                      if self.production.get((item, period), 0) > 0]
            required = sum(units for _, units in stream)
            self.required[period] = required
            order = sorted(self.plants,
                           key=lambda p: (self.handling[(p, period)], p))
            for rank, plant in enumerate(order):
                self.fill_rank[(plant, period)] = rank
            pos = 0
            remaining_stream = list(stream)
            for plant in order:
                room = self.capacity[(plant, period)]
                if room <= 0:
                    continue
                while room > 0 and pos < len(remaining_stream):
                    item, units = remaining_stream[pos]
                    take = min(room, units)
                    if take > 0:
                        rate = self.handling[(plant, period)]
                        self.allocation.append({
                            'period': period,
                            'plant': plant,
                            'item': item,
                            'units': take,
                            'handling_rate_cents': rate,
                            'handling_cost_cents': rate * take,
                        })
                        self.assigned[(plant, period)] += take
                        room -= take
                    if take == units:
                        pos += 1
                    else:
                        remaining_stream[pos] = (item, units - take)
            left = sum(units for item, units in remaining_stream[pos:])
            self.shortfall[period] = left

    # ---------------- objective ----------------

    def assemble_objective(self):
        self.production_cost = {}
        self.setup_total = {}
        self.holding_total = {}
        self.handling_total = {}
        self.shortfall_cost = {}
        for period in self.periods:
            self.production_cost[period] = sum(
                self.unit_cost[(i, period)] * self.production.get((i, period), 0)
                for i in self.items)
            self.setup_total[period] = sum(
                self.setup_cost[(i, period)]
                for i in self.items if self.production.get((i, period), 0) > 0)
            self.holding_total[period] = sum(
                self.inventory[(i, period)] * self.holding_rate[(i, period)]
                for i in self.items)
            self.handling_total[period] = 0
            self.shortfall_cost[period] = self.shortfall[period] * self.shortfall_penalty
        for row in self.allocation:
            self.handling_total[row['period']] += row['handling_cost_cents']
        self.total_production = sum(self.production_cost.values())
        self.total_setup = sum(self.setup_total.values())
        self.total_holding = sum(self.holding_total.values())
        self.total_handling = sum(self.handling_total.values())
        self.total_shortfall_cost = sum(self.shortfall_cost.values())
        self.total_objective = (self.total_production + self.total_setup
                                + self.total_holding + self.total_handling
                                + self.total_shortfall_cost + self.selected_capex)
        self.total_demand = sum(self.dem(i, p) for i in self.items for p in self.periods)
        self.total_produced = sum(self.production.values())
        self.total_shortfall_units = sum(self.shortfall.values())

    # ---------------- rejection and accounting sweep ----------------

    def sweep(self):
        self.rejected = []
        self.out_of_scope_rows = 0
        self.void_rows = 0
        demand_roles = {'demand', 'demand_overlay'}
        for src in self.corpus.sources:
            if src.authority != 'primary' or src.fmt not in SWEEP_FORMATS:
                continue
            for idx, row in enumerate(src.rows):
                rec = Rec(src.name, idx, row)
                rec.order = idx
                if self.above_cutoff(rec):
                    self.out_of_scope_rows += 1
                    continue
                reason = None
                if src.role in demand_roles:
                    item = self.item_of(rec)
                    if item is not None:
                        if item not in self.item_status:
                            reason = 'unknown_item'
                        elif self.item_status[item] == 'retired':
                            reason = 'retired_item'
                if reason is None and self.row_has_sentinel(rec):
                    reason = 'sentinel'
                if reason is not None:
                    self.rejected.append({
                        'source': src.name,
                        'row_uid': str(rec.get('row_uid') or ''),
                        'key': self.reject_key(rec),
                        'reason': reason,
                    })
                    continue
                if self.seq(rec) is not None and self.blocked(rec):
                    self.void_rows += 1
        self.rejected.sort(key=lambda r: (r['source'], r['row_uid']))

    def reject_key(self, rec):
        parts = []
        if rec.has(*self.item_cols):
            parts.append(norm_code(rec.get(*self.item_cols)))
        if rec.has(*self.period_cols):
            parts.append(norm_code(rec.get(*self.period_cols)))
        elif rec.has('date'):
            parts.append(self.calendar.get(str(rec.get('date')).strip()) or '')
        if rec.has(*self.plant_cols):
            parts.append(norm_code(rec.get(*self.plant_cols)))
        if rec.has('project_id'):
            parts.append(norm_code(rec.get('project_id')))
        if rec.has('zone'):
            parts.append(norm_code(rec.get('zone')))
        return ':'.join(parts)

    # ---------------- incumbent ----------------

    def incumbent(self):
        self.incumbent_unit_cost = {}
        for src in self.corpus.of_role('incumbent_plan', ('informational',)):
            for row in src.rows:
                item = norm_code(row.get('item'))
                period = norm_code(row.get('period'))
                value = as_int(row.get('unit_cost_cents'))
                if item and period and value is not None:
                    self.incumbent_unit_cost[(item, period)] = value
        self.incumbent_totals = {}
        self.incumbent_objective = 0
        self.incumbent_projects = []
        for src in self.corpus.of_role('incumbent_report', ('informational',)):
            path = os.path.join(self.corpus.dir, src.name)
            with open(path, encoding='utf-8') as fh:
                doc = json.load(fh)
            self.incumbent_totals = doc.get('stage_totals_cents', {}) or {}
            self.incumbent_objective = as_int(
                doc.get('published_total_objective_cents')) or 0
            self.incumbent_projects = sorted(
                norm_code(p) for p in doc.get('selected_projects', []) or [])


# --------------------------------------------------------------------------
# artifact writing
# --------------------------------------------------------------------------

def write_json(path, obj):
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(obj, fh, sort_keys=True, indent=1)
        fh.write('\n')


def write_jsonl(path, rows):
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True, separators=(',', ':')))
            fh.write('\n')


def write_csv(path, header, rows):
    with open(path, 'w', encoding='utf-8', newline='') as fh:
        writer = csv.writer(fh, lineterminator='\n')
        writer.writerow(header)
        for row in rows:
            writer.writerow(row)


def emit(plan, out_dir):
    periods = plan.periods
    items = plan.items
    ordinal = plan.ordinal
    out = lambda name: os.path.join(out_dir, name)

    # corrected_coefficients.jsonl
    rows = []
    for item in items:
        for period in periods:
            key = (item, period)
            rows.append({
                'demand_units': plan.dem(item, period),
                'energy_bps_applied': plan.energy_bps.get(period, 0) + plan.energy_surcharge_bps,
                'fiscal_ordinal': ordinal[period],
                'flags': plan.flags[key],
                'holding_cost_cents': plan.holding_rate[key],
                'item': item,
                'period': period,
                'setup_cost_cents': plan.setup_cost[key],
                'unit_cost_cents': plan.unit_cost[key],
            })
    write_jsonl(out('corrected_coefficients.jsonl'), rows)

    # objective.json
    objective = {
        'capex_cents': plan.selected_capex,
        'handling_cost_cents': plan.total_handling,
        'holding_cost_cents': plan.total_holding,
        'items_in_scope': len(items),
        'periods_in_horizon': len(periods),
        'plants_in_scope': len(plan.plants),
        'production_cost_cents': plan.total_production,
        'setup_cost_cents': plan.total_setup,
        'shortfall_penalty_cents': plan.total_shortfall_cost,
        'total_demand_units': plan.total_demand,
        'total_objective_cents': plan.total_objective,
        'total_produced_units': plan.total_produced,
        'total_shortfall_units': plan.total_shortfall_units,
    }
    write_json(out('objective.json'), objective)

    # optimal_plan.jsonl
    lots = sorted(plan.lots, key=lambda l: (l['item'], ordinal[l['period']]))
    write_jsonl(out('optimal_plan.jsonl'), [{
        'covers_periods': lot['covers_periods'],
        'fiscal_ordinal': ordinal[lot['period']],
        'item': lot['item'],
        'period': lot['period'],
        'production_cost_cents': lot['production_cost_cents'],
        'produced_units': lot['produced_units'],
        'setup_cost_cents': lot['setup_cost_cents'],
    } for lot in lots])

    # production_schedule.csv
    rows = []
    for item in items:
        for period in periods:
            rows.append([item, period, ordinal[period], plan.dem(item, period),
                         plan.production.get((item, period), 0),
                         plan.inventory[(item, period)]])
    write_csv(out('production_schedule.csv'),
              ['item', 'period', 'fiscal_ordinal', 'demand_units',
               'produced_units', 'ending_inventory_units'], rows)

    # holding_profile.csv
    rows = []
    for item in items:
        cumulative = 0
        for period in periods:
            inventory = plan.inventory[(item, period)]
            rate = plan.holding_rate[(item, period)]
            cost = inventory * rate
            cumulative += cost
            rows.append([item, period, ordinal[period], inventory, rate, cost, cumulative])
    write_csv(out('holding_profile.csv'),
              ['item', 'period', 'fiscal_ordinal', 'ending_inventory_units',
               'holding_rate_cents', 'period_holding_cents',
               'cumulative_holding_cents'], rows)

    # sourcing_allocation.csv
    alloc = sorted(plan.allocation,
                   key=lambda r: (ordinal[r['period']],
                                  plan.fill_rank[(r['plant'], r['period'])],
                                  r['item']))
    write_csv(out('sourcing_allocation.csv'),
              ['period', 'fiscal_ordinal', 'plant', 'item', 'units',
               'handling_rate_cents', 'handling_cost_cents'],
              [[r['period'], ordinal[r['period']], r['plant'], r['item'],
                r['units'], r['handling_rate_cents'], r['handling_cost_cents']]
               for r in alloc])

    # plant_utilization.csv
    rows = []
    full_capacity = []
    zero_capacity = []
    for plant in plan.plants:
        for period in periods:
            capacity = plan.capacity[(plant, period)]
            assigned = plan.assigned[(plant, period)]
            idle = capacity - assigned
            util = 0 if capacity == 0 else rhu(assigned * 10000, capacity)
            rows.append([plant, period, ordinal[period], capacity, assigned, idle, util])
            if capacity > 0 and assigned == capacity:
                full_capacity.append([plant, period])
            if capacity == 0:
                zero_capacity.append([plant, period])
    write_csv(out('plant_utilization.csv'),
              ['plant', 'period', 'fiscal_ordinal', 'capacity_units',
               'assigned_units', 'idle_units', 'utilisation_bps'], rows)

    # shortfall_ledger.csv
    rows = []
    for period in periods:
        capacity = sum(plan.capacity[(p, period)] for p in plan.plants)
        shortfall = plan.shortfall[period]
        rows.append([period, ordinal[period], plan.required[period], capacity,
                     shortfall, plan.shortfall_penalty,
                     shortfall * plan.shortfall_penalty])
    write_csv(out('shortfall_ledger.csv'),
              ['period', 'fiscal_ordinal', 'required_units', 'capacity_units',
               'shortfall_units', 'penalty_rate_cents', 'penalty_cents'], rows)

    # retrofit_selection.json
    write_json(out('retrofit_selection.json'), {
        'budget_cents': plan.budget_cents,
        'candidate_project_ids': list(plan.candidates),
        'capex_grid_cents': plan.capex_grid,
        'eligible_project_count': len(plan.candidates),
        'rejected_project_ids': list(plan.rejected_projects),
        'selected_capex_cents': plan.selected_capex,
        'selected_project_ids': sorted(plan.selected),
        'selected_value_cents': plan.selected_value,
    })

    # budget_utilization.json
    slack = plan.budget_cents - plan.selected_capex
    write_json(out('budget_utilization.json'), {
        'budget_binding': bool(plan.budget_binding),
        'budget_cents': plan.budget_cents,
        'capex_cents': plan.selected_capex,
        'slack_cents': slack,
        'slack_grid_units': slack // plan.capex_grid if plan.capex_grid else 0,
        'utilisation_bps': (rhu(plan.selected_capex * 10000, plan.budget_cents)
                            if plan.budget_cents else 0),
    })

    # period_costs.json
    period_costs = {}
    for period in periods:
        entry = {
            'handling_cost_cents': plan.handling_total[period],
            'holding_cost_cents': plan.holding_total[period],
            'production_cost_cents': plan.production_cost[period],
            'setup_cost_cents': plan.setup_total[period],
            'shortfall_penalty_cents': plan.shortfall_cost[period],
        }
        entry['total_cents'] = sum(entry.values())
        period_costs[period] = entry
    write_json(out('period_costs.json'), period_costs)

    # item_summary.json
    item_summary = {}
    for item in items:
        demand = sum(plan.dem(item, p) for p in periods)
        produced = sum(plan.production.get((item, p), 0) for p in periods)
        production_cost = sum(plan.unit_cost[(item, p)] * plan.production.get((item, p), 0)
                              for p in periods)
        setup_count = sum(1 for p in periods if plan.production.get((item, p), 0) > 0)
        setup_cost = sum(plan.setup_cost[(item, p)] for p in periods
                         if plan.production.get((item, p), 0) > 0)
        holding = sum(plan.inventory[(item, p)] * plan.holding_rate[(item, p)]
                      for p in periods)
        item_summary[item] = {
            'demand_units': demand,
            'family': plan.item_family.get(item, ''),
            'holding_cost_cents': holding,
            'produced_units': produced,
            'production_cost_cents': production_cost,
            'setup_count': setup_count,
            'setup_cost_cents': setup_cost,
            'total_cents': production_cost + setup_cost + holding,
        }
    write_json(out('item_summary.json'), item_summary)

    # binding_constraints.json
    shortfall_periods = [p for p in periods if plan.shortfall[p] > 0]
    full_capacity.sort(key=lambda e: (e[0], ordinal[e[1]]))
    zero_capacity.sort(key=lambda e: (e[0], ordinal[e[1]]))
    write_json(out('binding_constraints.json'), {
        'binding_count': (len(full_capacity) + len(shortfall_periods)
                          + (1 if plan.budget_binding else 0)),
        'budget_binding': bool(plan.budget_binding),
        'full_capacity_plant_periods': full_capacity,
        'shortfall_periods': shortfall_periods,
        'zero_capacity_plant_periods': zero_capacity,
    })

    # optimality_certificate.json
    checks = certificate(plan)
    write_json(out('optimality_certificate.json'), checks)

    # sensitivity_report.json
    next_unit = {}
    for period in periods:
        idle = [(plan.handling[(p, period)], p) for p in plan.plants
                if plan.capacity[(p, period)] - plan.assigned[(p, period)] > 0]
        next_unit[period] = min(idle)[0] if idle else plan.shortfall_penalty
    top_id, top_capex = top_unfunded(plan)
    write_json(out('sensitivity_report.json'), {
        'budget_binding': bool(plan.budget_binding),
        'budget_grid_unit_cents': plan.capex_grid,
        'marginal_value_of_one_grid_unit_cents': plan.marginal_grid_value,
        'next_unit_cost_by_period': next_unit,
        'top_unfunded_capex_cents': top_capex,
        'top_unfunded_project_id': top_id,
    })

    # incumbent_delta.json
    corrected_components = {
        'capex_cents': plan.selected_capex,
        'handling_cost_cents': plan.total_handling,
        'holding_cost_cents': plan.total_holding,
        'production_cost_cents': plan.total_production,
        'setup_cost_cents': plan.total_setup,
        'shortfall_penalty_cents': plan.total_shortfall_cost,
    }
    component_deltas = {}
    for name, value in corrected_components.items():
        if name in plan.incumbent_totals:
            component_deltas[name] = value - (as_int(plan.incumbent_totals[name]) or 0)
    selected = set(plan.selected)
    incumbent_projects = set(plan.incumbent_projects)
    write_json(out('incumbent_delta.json'), {
        'component_deltas': component_deltas,
        'corrected_selected_project_ids': sorted(selected),
        'corrected_total_objective_cents': plan.total_objective,
        'delta_cents': plan.total_objective - plan.incumbent_objective,
        'incumbent_selected_project_ids': sorted(incumbent_projects),
        'incumbent_total_objective_cents': plan.incumbent_objective,
        'projects_added': sorted(selected - incumbent_projects),
        'projects_dropped': sorted(incumbent_projects - selected),
    })

    # coefficient_corrections.csv
    rows = []
    for item in items:
        for period in periods:
            key = (item, period)
            corrected = plan.unit_cost[key]
            previous = plan.incumbent_unit_cost.get(key)
            if previous is None or previous == corrected:
                continue
            rows.append([item, period, previous, corrected,
                         corrected - previous, plan.flags[key]])
    write_csv(out('coefficient_corrections.csv'),
              ['item', 'period', 'incumbent_unit_cost_cents',
               'corrected_unit_cost_cents', 'delta_cents', 'flags'], rows)

    # data_quality.json
    sources = []
    mismatches = []
    for src in sorted(plan.corpus.sources, key=lambda s: s.name):
        sources.append({
            'authority': src.authority,
            'fmt': src.fmt,
            'name': src.name,
            'record_count_declared': src.record_count,
            'role': src.role,
            'rows_seen': src.rows_seen,
        })
        if src.rows_seen != src.record_count:
            mismatches.append(src.name)
    write_json(out('data_quality.json'), {
        'count_mismatches': sorted(mismatches),
        'sources': sources,
        'totals': {
            'out_of_scope_rows': plan.out_of_scope_rows,
            'rejected_rows': len(plan.rejected),
            'sources_seen': len(plan.corpus.sources),
            'void_rows': plan.void_rows,
        },
    })

    # rejected_records.csv
    write_csv(out('rejected_records.csv'), ['source', 'row_uid', 'key', 'reason'],
              [[r['source'], r['row_uid'], r['key'], r['reason']] for r in plan.rejected])

    # reconciliation.txt and audit_summary.md
    figures = [
        ('corrected_total_objective_cents', plan.total_objective),
        ('incumbent_total_objective_cents', plan.incumbent_objective),
        ('delta_cents', plan.total_objective - plan.incumbent_objective),
        ('selected_capex_cents', plan.selected_capex),
        ('budget_cents', plan.budget_cents),
        ('total_shortfall_units', plan.total_shortfall_units),
        ('shortfall_penalty_cents', plan.total_shortfall_cost),
        ('items_in_scope', len(items)),
        ('rejected_rows', len(plan.rejected)),
    ]
    with open(out('reconciliation.txt'), 'w', encoding='utf-8', newline='\n') as fh:
        for name, value in figures:
            fh.write('%s=%d\n' % (name, value))
    with open(out('audit_summary.md'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('# Replan Audit Summary\n\n')
        for name, value in figures:
            fh.write('- %s: %d\n' % (name, value))
        fh.write('\n')
        fh.write('Selected projects: %s\n' % ', '.join(sorted(plan.selected)))


def top_unfunded(plan):
    best = None
    for project in plan.rejected_projects:
        value = plan.project_value.get(project, 0)
        capex = plan.project_capex.get(project, 0)
        ratio = Fraction(value, capex) if capex else Fraction(value * 10 ** 9, 1)
        cand = (-ratio, project)
        if best is None or cand < best[0]:
            best = (cand, project)
    if best is None:
        return '', 0
    return best[1], plan.project_capex.get(best[1], 0)


def certificate(plan):
    slack = plan.budget_cents - plan.selected_capex
    selected = set(plan.selected)
    capital_ok = True
    for project in plan.candidates:
        if project in selected:
            continue
        if (plan.project_value.get(project, 0) > 0
                and plan.project_capex.get(project, 0) <= slack):
            capital_ok = False
            break

    zero_inventory = True
    reconstructed = 0
    for item in plan.items:
        entering = 0
        for period in plan.periods:
            produced = plan.production.get((item, period), 0)
            if produced > 0 and entering != 0:
                zero_inventory = False
            reconstructed += produced * plan.unit_cost[(item, period)]
            if produced > 0:
                reconstructed += plan.setup_cost[(item, period)]
            ending = plan.inventory[(item, period)]
            reconstructed += ending * plan.holding_rate[(item, period)]
            entering = ending
    programme = sum(plan.item_cost.values())
    cost_matches = reconstructed == programme == (
        plan.total_production + plan.total_setup + plan.total_holding)

    sourcing_ok = True
    for period in plan.periods:
        receivers = [plan.handling[(p, period)] for p in plan.plants
                     if plan.assigned[(p, period)] > 0]
        if not receivers:
            continue
        worst = max(receivers)
        for plant in plan.plants:
            idle = plan.capacity[(plant, period)] - plan.assigned[(plant, period)]
            if idle > 0 and plan.handling[(plant, period)] < worst:
                sourcing_ok = False
                break

    covered = (plan.total_demand == plan.total_produced
               and plan.total_produced == sum(r['units'] for r in plan.allocation)
               + plan.total_shortfall_units)
    return {
        'all_demand_covered_or_charged': bool(covered),
        'capital_no_unfunded_candidate_fits': bool(capital_ok),
        'lot_sizing_reconstructed_cost_matches': bool(cost_matches),
        'lot_sizing_zero_inventory_property': bool(zero_inventory),
        'sourcing_no_cheaper_idle_capacity': bool(sourcing_ok),
        'total_objective_cents': plan.total_objective,
    }


def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: solver.py <DATA_DIR> <OUT_DIR>\n')
        return 2
    data_dir, out_dir = argv[1], argv[2]
    os.makedirs(out_dir, exist_ok=True)
    plan = Plan(data_dir, out_dir)
    emit(plan, out_dir)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
