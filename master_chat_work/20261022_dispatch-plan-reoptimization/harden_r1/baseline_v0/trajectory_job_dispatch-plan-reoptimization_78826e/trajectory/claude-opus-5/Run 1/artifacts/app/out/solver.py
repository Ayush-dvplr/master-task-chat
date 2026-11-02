#!/usr/bin/env python3
"""Network replan optimizer.

Rebuilds every cost coefficient from the registers named authoritative by the
operating contract, re-solves the four decision programmes the contract
defines, and writes the audit artifacts.

Usage:  solver.py <DATA_DIR> <OUT_DIR>

Standard library only.  Reads only from DATA_DIR, writes only into OUT_DIR.
Nothing in the logic depends on the identifiers, the row order or the values of
any particular export set: the corpus is discovered through the manifest
database, the parameters through the contract documents, and the horizon, item
and plant scopes through the registers the contract makes authoritative.
"""

import collections
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

XLM = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
XLR = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
WPM = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'

DELIM = {'csv': ',', 'tsv': '\t', 'psv': '|'}
LINE_JSON = ('jsonl', 'ndjson')
# Formats the rejection and accounting sweep walks (section 14).
SWEEP_FMT = frozenset(['csv', 'tsv', 'psv', 'jsonl', 'ndjson', 'json', 'xml', 'txt'])
DOC_PREFIX = 'R|'


# --------------------------------------------------------------------------
# arithmetic
# --------------------------------------------------------------------------
def rhu(num, den=1):
    """Round half up, away from zero, on exact integers."""
    num, den = int(num), int(den)
    if den < 0:
        num, den = -num, -den
    if num >= 0:
        return (2 * num + den) // (2 * den)
    return -((-2 * num + den) // (2 * den))


def as_int(value):
    text = str(value).strip()
    if text.startswith('+'):
        text = text[1:]
    return int(text)


# --------------------------------------------------------------------------
# minimal YAML subset reader (contract configuration files)
# --------------------------------------------------------------------------
def _yaml_scalar(text):
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ('"', "'"):
        return text[1:-1]
    return text


def _yaml_block(lines, index, indent):
    if index >= len(lines):
        return {}, index
    if lines[index][1].startswith('- '):
        out = []
        while index < len(lines):
            ind, text = lines[index]
            if ind != indent or not text.startswith('- '):
                break
            out.append(_yaml_scalar(text[2:]))
            index += 1
        return out, index
    out = {}
    while index < len(lines):
        ind, text = lines[index]
        if ind != indent:
            break
        key, _, rest = text.partition(':')
        key, rest = key.strip(), rest.strip()
        index += 1
        if rest:
            out[key] = _yaml_scalar(rest)
            continue
        if index < len(lines) and lines[index][0] > indent:
            out[key], index = _yaml_block(lines, index, lines[index][0])
        elif (index < len(lines) and lines[index][0] == indent
              and lines[index][1].startswith('- ')):
            out[key], index = _yaml_block(lines, index, indent)
        else:
            out[key] = {}
    return out, index


def read_yaml(path):
    lines = []
    with open(path, encoding='utf-8') as handle:
        for raw in handle:
            body = raw.rstrip('\n')
            if not body.strip() or body.lstrip().startswith('#'):
                continue
            lines.append((len(body) - len(body.lstrip(' ')), body.strip()))
    if not lines:
        return {}
    return _yaml_block(lines, 0, lines[0][0])[0]


# --------------------------------------------------------------------------
# format readers
# --------------------------------------------------------------------------
def read_delimited(path, sep):
    with open(path, newline='', encoding='utf-8') as handle:
        rows = [r for r in csv.reader(handle, delimiter=sep)
                if r and any(c.strip() for c in r)]
    if not rows:
        return []
    header = [h.strip() for h in rows[0]]
    return [dict(zip(header, r)) for r in rows[1:]]


def text_records(path):
    """Non empty lines that do not start with a hash."""
    out = []
    with open(path, encoding='utf-8') as handle:
        for raw in handle:
            body = raw.rstrip('\n')
            if body.strip() and not body.lstrip().startswith('#'):
                out.append(body)
    return out


def read_text_register(path):
    """Plain text register: a comment line declares the fixed column order."""
    header = None
    with open(path, encoding='utf-8') as handle:
        for raw in handle:
            if raw.lstrip().startswith('#'):
                found = re.search(r'order\s*:\s*(.+)$', raw)
                if found and '|' in found.group(1):
                    header = [c.strip() for c in found.group(1).strip().split('|')]
    out = []
    for body in text_records(path):
        if header and '|' in body:
            out.append(dict(zip(header, body.split('|'))))
        else:
            out.append({'_line': body})
    return out


def read_line_json(path):
    out = []
    with open(path, encoding='utf-8') as handle:
        for raw in handle:
            if raw.strip():
                out.append(json.loads(raw))
    return out


def read_json_records(path):
    """A JSON register counts the entries of its records array."""
    with open(path, encoding='utf-8') as handle:
        doc = json.load(handle)
    if isinstance(doc, list):
        return doc
    records = doc.get('records')
    if isinstance(records, list):
        return records
    for value in doc.values():
        if isinstance(value, list):
            return value
    return []


def read_xml(path):
    return [dict(child.attrib) for child in ET.parse(path).getroot()]


def _col_index(ref):
    found = re.match(r'([A-Za-z]+)', ref or '')
    if not found:
        return None
    number = 0
    for char in found.group(1).upper():
        number = number * 26 + (ord(char) - 64)
    return number - 1


def read_xlsx(path):
    book = zipfile.ZipFile(path)
    names = book.namelist()
    shared = []
    if 'xl/sharedStrings.xml' in names:
        for item in ET.fromstring(book.read('xl/sharedStrings.xml')):
            shared.append(''.join(t.text or '' for t in item.iter(XLM + 't')))
    targets = {rel.get('Id'): rel.get('Target')
               for rel in ET.fromstring(book.read('xl/_rels/workbook.xml.rels'))}
    sheets = []
    for sheet in ET.fromstring(book.read('xl/workbook.xml')).iter(XLM + 'sheet'):
        target = targets[sheet.get(XLR + 'id')]
        if not target.startswith('xl/'):
            target = 'xl/' + target.lstrip('/')
        sheets.append((sheet.get('name'), target))
    out = []
    for sheet_name, target in sheets:
        grid = []
        for row in ET.fromstring(book.read(target)).iter(XLM + 'row'):
            values = []
            for cell in row.iter(XLM + 'c'):
                kind = cell.get('t')
                if kind == 'inlineStr':
                    holder = cell.find(XLM + 'is')
                    text = ('' if holder is None else
                            ''.join(t.text or '' for t in holder.iter(XLM + 't')))
                elif kind == 's':
                    node = cell.find(XLM + 'v')
                    text = shared[int(node.text)] if node is not None else ''
                else:
                    node = cell.find(XLM + 'v')
                    text = node.text if node is not None and node.text else ''
                position = _col_index(cell.get('r'))
                if position is None:
                    values.append(text)
                else:
                    while len(values) <= position:
                        values.append('')
                    values[position] = text
            grid.append(values)
        if not grid:
            continue
        header = [h.strip() for h in grid[0]]
        for values in grid[1:]:
            padded = list(values) + [''] * (len(header) - len(values))
            record = dict(zip(header, padded))
            record['_sheet'] = sheet_name
            out.append(record)
    return out


def read_docx(path):
    book = zipfile.ZipFile(path)
    root = ET.fromstring(book.read('word/document.xml'))
    out = []
    for para in root.iter(WPM + 'p'):
        text = ''.join(node.text or '' for node in para.iter(WPM + 't'))
        if text.startswith(DOC_PREFIX):
            out.append(text)
    return out


def read_pdf(path):
    with open(path, 'rb') as handle:
        blob = handle.read()
    out = []
    for chunk in re.findall(rb'stream\r?\n(.*?)endstream', blob, re.S):
        try:
            chunk = zlib.decompress(chunk)
        except zlib.error:
            pass
        for shown in re.findall(rb'\((.*?)\)\s*Tj', chunk, re.S):
            text = shown.decode('latin-1')
            if text.startswith(DOC_PREFIX):
                out.append(text)
    return out


def sqlite_tables(path):
    conn = sqlite3.connect('file:%s?mode=ro' % path, uri=True)
    try:
        names = [r[0] for r in conn.execute(
            "select name from sqlite_master where type='table' "
            "and name not like 'sqlite_%' order by name")]
        out = {}
        for name in names:
            cursor = conn.execute('select * from "%s"' % name)
            columns = [c[0] for c in cursor.description]
            out[name] = [dict(zip(columns, row)) for row in cursor]
        return out
    finally:
        conn.close()


# --------------------------------------------------------------------------
# contract engine
# --------------------------------------------------------------------------
class Contract(object):
    """Corpus discovery, liveness, supersession and scale handling."""

    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.manifest_name = None
        self.sources = []
        self._cache = {}
        self._discover()
        self._load_contract_files()
        self._load_lifecycle()

    # ---- discovery ------------------------------------------------------
    def path(self, name):
        return os.path.join(self.data_dir, name)

    def _discover(self):
        """Find the manifest database by the table it carries, not by name."""
        for name in sorted(os.listdir(self.data_dir)):
            full = self.path(name)
            if not os.path.isfile(full):
                continue
            try:
                tables = sqlite_tables(full)
            except (sqlite3.DatabaseError, UnicodeDecodeError):
                continue
            if 'sources' not in tables:
                continue
            rows = tables['sources']
            if not rows or 'role' not in rows[0] or 'authority' not in rows[0]:
                continue
            self.manifest_name = name
            self.sources = [
                {'name': r['name'], 'role': r['role'], 'fmt': r['fmt'],
                 'declared': r.get('record_count'), 'authority': r['authority']}
                for r in rows]
            break
        if self.manifest_name is None:
            raise SystemExit('no source manifest found in %s' % self.data_dir)
        self.sources.sort(key=lambda s: s['name'])
        self.by_role = collections.defaultdict(list)
        for source in self.sources:
            self.by_role[source['role']].append(source)
        for group in self.by_role.values():
            group.sort(key=lambda s: s['name'])

    def role_sources(self, role, authority=('primary', 'contract')):
        return [s for s in self.by_role.get(role, [])
                if authority is None or s['authority'] in authority]

    def sole_source(self, role):
        found = self.role_sources(role)
        return found[0] if found else None

    # ---- raw reads ------------------------------------------------------
    def read_source(self, source):
        name, fmt = source['name'], source['fmt']
        if name in self._cache:
            return self._cache[name]
        full = self.path(name)
        if fmt in DELIM:
            rows = read_delimited(full, DELIM[fmt])
        elif fmt in LINE_JSON:
            rows = read_line_json(full)
        elif fmt == 'json':
            rows = read_json_records(full)
        elif fmt == 'xml':
            rows = read_xml(full)
        elif fmt == 'txt':
            rows = read_text_register(full)
        elif fmt in ('md', 'yaml', 'yml'):
            rows = text_records(full)
        elif fmt == 'xlsx':
            rows = read_xlsx(full)
        elif fmt == 'docx':
            rows = read_docx(full)
        elif fmt == 'pdf':
            rows = read_pdf(full)
        elif fmt in ('db', 'sqlite'):
            rows = sqlite_tables(full)
        else:
            rows = []
        self._cache[name] = rows
        return rows

    def physical_count(self, source):
        rows = self.read_source(source)
        if source['fmt'] in ('db', 'sqlite'):
            return sum(len(v) for v in rows.values())
        return len(rows)

    def rows_for_role(self, role, authority=('primary', 'contract')):
        """Canonical order: source name ascending, then row order in the file."""
        out = []
        for source in self.role_sources(role, authority):
            rows = self.read_source(source)
            if isinstance(rows, dict):
                continue
            for index, row in enumerate(rows):
                out.append((source['name'], index, row))
        return out

    # ---- contract documents --------------------------------------------
    def _load_contract_files(self):
        config_source = self.sole_source('contract_config')
        self.config = read_yaml(self.path(config_source['name'])) if config_source else {}
        nom_source = self.sole_source('contract_nomenclature')
        self.nomenclature = read_yaml(self.path(nom_source['name'])) if nom_source else {}

        auth_source = self.sole_source('authority_control')
        self.authority = sqlite_tables(self.path(auth_source['name'])) if auth_source else {}

        control = self.config.get('control', {})
        self.control = control
        self.cutoff = as_int(control['plan_sequence_cutoff'])

        tokens = self.nomenclature.get('sentinel_tokens', [])
        self.sentinels = {str(t).strip().lower() for t in tokens}
        for row in self.authority.get('sentinel_authority', []):
            token = str(row.get('token', '')).strip()
            self.sentinels.add('' if token == '<empty>' else token.lower())
        self.sentinels.add('')

        self.ignored = {str(c).strip() for c in
                        self.nomenclature.get('ignored_columns', [])}
        self.ignored |= {str(c).strip() for c in
                         self.nomenclature.get('retired_aliases', [])}
        self.ignored |= {'_sheet', '_line'}

        self.scales = {}
        for row in self.authority.get('scale_authority', []):
            self.scales[str(row['token']).strip().lower()] = int(row['factor'])
        for token, factor in self.nomenclature.get('scale_tokens', {}).items():
            key = str(token).strip().lower()
            if key == 'pct_to_bps':
                key = 'pct'
            if key == 'dozens':
                key = 'units_dz'
            self.scales.setdefault(key, int(factor))
        self.bps_denominator = self.scales.get('bps_denominator', 10000)
        self.micros_denominator = self.scales.get('micros_denominator', 1000000)

        aliases = self.nomenclature.get('header_aliases', {})
        self.alias_item = list(aliases.get('item_code', []))
        self.alias_period = list(aliases.get('period_code', []))
        self.alias_plant = list(aliases.get('plant_code', []))
        self.alias_units = list(aliases.get('demand_units', []))
        self.alias_dozens = list(aliases.get('demand_units_dozens', []))
        self.pad = int(self.nomenclature.get('code_normalisation', {})
                       .get('zero_pad_numeric_tail', 2))
        self.separators = list(self.nomenclature.get('code_normalisation', {})
                               .get('drop_separators', ['-', '_']))

    # ---- tokens ---------------------------------------------------------
    def is_sentinel(self, value):
        if value is None:
            return True
        return str(value).strip().lower() in self.sentinels

    def norm(self, value):
        text = str(value).strip().upper()
        for sep in self.separators:
            text = text.replace(sep, '')
        text = ''.join(text.split())
        found = re.match(r'^(.*?)(\d+)$', text)
        if found:
            text = found.group(1) + found.group(2).zfill(self.pad)
        return text

    def scale(self, token):
        if token is None:
            return 1
        return self.scales.get(str(token).strip().lower(), 1)

    def governing_fields(self, row):
        return [k for k in row if k not in self.ignored]

    def row_rejected(self, row):
        """A row whose governing value is a sentinel never supersedes."""
        return any(self.is_sentinel(row.get(k)) for k in self.governing_fields(row))

    # ---- lifecycle ------------------------------------------------------
    def _load_lifecycle(self):
        events = collections.defaultdict(list)
        for _name, _index, row in self.rows_for_role('row_lifecycle'):
            uid = str(row.get('row_uid', '')).strip()
            action = str(row.get('action', '')).strip()
            if not uid or action not in ('void', 'restore'):
                continue
            try:
                seq = as_int(row.get('seq'))
            except (TypeError, ValueError):
                continue
            if seq > self.cutoff:
                continue
            events[uid].append((seq, action))
        self.lifecycle = {}
        self.lifecycle_touched = set()
        for uid, entries in events.items():
            entries.sort(key=lambda e: e[0])
            self.lifecycle[uid] = entries[-1][1] == 'void'
            if any(action == 'void' for _seq, action in entries):
                self.lifecycle_touched.add(uid)

    def lifecycle_voided(self, uid):
        return self.lifecycle.get(str(uid).strip(), False)

    # ---- liveness -------------------------------------------------------
    def own_void(self, row):
        if 'void' not in row:
            return False
        value = row.get('void')
        if self.is_sentinel(value):
            return False
        try:
            return as_int(value) != 0
        except (TypeError, ValueError):
            return False

    def sequence(self, row):
        if 'effective_seq' not in row or self.is_sentinel(row.get('effective_seq')):
            return None
        try:
            return as_int(row.get('effective_seq'))
        except (TypeError, ValueError):
            return None

    def revision(self, row):
        if 'rev' not in row or self.is_sentinel(row.get('rev')):
            return 0
        try:
            return as_int(row.get('rev'))
        except (TypeError, ValueError):
            return 0

    def is_live(self, row):
        seq = self.sequence(row)
        if seq is None or seq > self.cutoff:
            return False
        if self.row_rejected(row):
            return False
        if self.own_void(row):
            return False
        return not self.lifecycle_voided(row.get('row_uid', ''))

    def live_rows(self, role):
        out = []
        for order, (name, index, row) in enumerate(self.rows_for_role(role)):
            if self.is_live(row):
                out.append((order, name, index, row))
        return out

    def winners(self, role, keyfn):
        """Supersede: highest rev, then highest seq, then later canonical row."""
        best = {}
        for order, _name, _index, row in self.live_rows(role):
            key = keyfn(row)
            if key is None:
                continue
            rank = (self.revision(row), self.sequence(row), order)
            if key not in best or rank > best[key][0]:
                best[key] = (rank, row)
        return {key: value[1] for key, value in best.items()}

    def accumulated(self, role, identity_col, keyfn, valuefn):
        """Accumulating register: one entry per identity, first live row wins."""
        first = {}
        for order, _name, _index, row in self.live_rows(role):
            identity = str(row.get(identity_col, '')).strip()
            if not identity or identity in first:
                continue
            first[identity] = (order, row)
        totals = collections.Counter()
        for _identity, (_order, row) in first.items():
            key = keyfn(row)
            if key is None:
                continue
            totals[key] += valuefn(row)
        return totals

    # ---- identifier helpers --------------------------------------------
    def first_present(self, row, aliases):
        for name in aliases:
            if name in row:
                return name
        return None

    def code_from(self, row, aliases):
        column = self.first_present(row, aliases)
        if column is None:
            return None
        value = row.get(column)
        if self.is_sentinel(value):
            return None
        return self.norm(value)

    # ---- document parameter rows ---------------------------------------
    def document_rows(self, role, kind):
        """`R|`-prefixed document records parsed into register shaped rows."""
        out = []
        for name, index, line in self.rows_for_role(role):
            if not isinstance(line, str):
                continue
            fields = line.split('|')
            if len(fields) != 9 or fields[1] != kind:
                continue
            out.append((name, index, {
                'parameter': fields[2], 'value': fields[3], 'unit': fields[4],
                'rev': fields[5], 'effective_seq': fields[6],
                'void': fields[7], 'row_uid': fields[8]}))
        return out

    def pick_parameter(self, rows, parameter):
        """Winning revision of one named parameter row set."""
        best = None
        for order, (_name, _index, row) in enumerate(rows):
            if str(row.get('parameter', '')).strip() != parameter:
                continue
            if not self.is_live(row):
                continue
            rank = (self.revision(row), self.sequence(row), order)
            if best is None or rank > best[0]:
                best = (rank, row)
        return best[1] if best else None

    def parameter_value(self, rows, parameter, default=None):
        row = self.pick_parameter(rows, parameter)
        if row is None:
            return default
        return as_int(row['value']) * self.scale(row.get('unit'))


# --------------------------------------------------------------------------
# capital programme: exact knapsack with the contract tie break
# --------------------------------------------------------------------------
def _gcd(a, b):
    while b:
        a, b = b, a % b
    return a


class CapitalProgramme(object):
    """Maximise value subject to the funded envelope, exactly.

    Ties resolve on highest total value, then lowest total capital cost, then
    the smallest indicator, where the indicator reads the candidate list in
    ascending project code with the first project as the least significant bit.
    """

    def __init__(self, codes, costs, values):
        self.codes = list(codes)
        self.costs = list(costs)
        self.values = list(values)

    def _step(self, budget):
        step = budget
        for cost in self.costs:
            step = _gcd(step, cost)
        return step or 1

    def solve(self, budget):
        """Return (total_value, total_cost, selected indices)."""
        if not self.codes or budget < 0:
            return 0, 0, []
        step = self._step(budget)
        span = budget // step
        # table[c] = (value, indicator) best achievable at exact cost c*step
        table = [None] * (span + 1)
        table[0] = (0, 0)
        for index, cost in enumerate(self.costs):
            units = cost // step
            gain = self.values[index]
            bit = 1 << index
            if units > span:
                continue
            for cell in range(span - units, -1, -1):
                current = table[cell]
                if current is None:
                    continue
                candidate = (current[0] + gain, current[1] | bit)
                target = table[cell + units]
                if target is None or (candidate[0], -candidate[1]) > (target[0], -target[1]):
                    table[cell + units] = candidate
        best = None
        for cell in range(span + 1):
            if table[cell] is None:
                continue
            value, indicator = table[cell]
            rank = (value, -cell, -indicator)
            if best is None or rank > best[0]:
                best = (rank, cell, indicator, value)
        _rank, cell, indicator, value = best
        chosen = [i for i in range(len(self.codes)) if indicator & (1 << i)]
        return value, cell * step, chosen


# --------------------------------------------------------------------------
# lot sizing: exact dynamic programme over the fiscal horizon
# --------------------------------------------------------------------------
def lot_size(demand, unit_cost, setup_cost, holding):
    """Minimum cost production plan with no backlog.

    Production in a period covers a contiguous block of periods starting at
    that period.  A block whose demand is zero opens no production and carries
    no setup charge.  Ties prefer the earlier production period, which the
    ascending scan of block ends secures.
    """
    span = len(demand)
    best = [0] * (span + 1)
    follow = [None] * (span + 1)
    for start in range(span - 1, -1, -1):
        chosen = None
        carried = 0           # holding per unit from `start` to the current end
        block_cost = 0
        block_demand = 0
        for end in range(start + 1, span + 1):
            last = end - 1
            if last > start:
                carried += holding[last - 1]
            block_cost += demand[last] * (unit_cost[start] + carried)
            block_demand += demand[last]
            total = block_cost + best[end]
            if block_demand > 0:
                total += setup_cost[start]
            if chosen is None or total < chosen[0]:
                chosen = (total, end)
        best[start] = chosen[0]
        follow[start] = chosen[1]

    produced = [0] * span
    blocks = []
    start = 0
    while start < span:
        end = follow[start]
        quantity = sum(demand[start:end])
        if quantity > 0:
            produced[start] = quantity
            blocks.append((start, end, quantity))
        start = end
    return best[0], produced, blocks


# --------------------------------------------------------------------------
# writers
# --------------------------------------------------------------------------
def write_json(path, payload):
    with open(path, 'w', encoding='utf-8', newline='\n') as handle:
        json.dump(payload, handle, sort_keys=True, indent=1)
        handle.write('\n')


def write_jsonl(path, rows):
    with open(path, 'w', encoding='utf-8', newline='\n') as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, separators=(',', ':')))
            handle.write('\n')


def write_csv(path, header, rows):
    with open(path, 'w', encoding='utf-8', newline='') as handle:
        writer = csv.writer(handle, lineterminator='\n')
        writer.writerow(header)
        for row in rows:
            writer.writerow(row)


def write_lines(path, lines):
    with open(path, 'w', encoding='utf-8', newline='\n') as handle:
        for line in lines:
            handle.write(line)
            handle.write('\n')


# --------------------------------------------------------------------------
# main rebuild
# --------------------------------------------------------------------------
def run(data_dir, out_dir):
    book = Contract(data_dir)
    cutoff = book.cutoff
    norm = book.norm

    # ---- scalar parameters from the documents that publish them --------
    memo = book.document_rows('energy_memo', 'PARAM')
    schedule = book.document_rows('penalty_schedule', 'PARAM')
    surcharge_bps = book.parameter_value(memo, 'energy_surcharge', 0)
    holding_bps = book.parameter_value(schedule, 'holding_rate', 0)
    penalty_cents = book.parameter_value(schedule, 'shortfall_penalty_per_unit', 0)

    programme_rows = [(n, i, r) for n, i, r in book.rows_for_role('capital_programme')
                      if isinstance(r, dict) and 'parameter' in r]
    budget_cents = book.parameter_value(programme_rows, 'capital_budget', 0)
    grid_cents = as_int(book.control['capex_grid_cents'])
    setup_fallback = as_int(book.control['default_setup_cents'])
    min_handling = as_int(book.control['minimum_handling_cents'])

    # ---- treasury rate: highest sequence at or below the cutoff --------
    rate_rows = []
    for order, _name, _index, row in book.live_rows('fx_rate'):
        rate_rows.append((book.sequence(row), order,
                          as_int(row['usd_per_eur_micros'])))
    rate_rows.sort()
    fx_micros = rate_rows[-1][2] if rate_rows else book.micros_denominator

    def to_usd_cents(amount, currency):
        if currency is not None and str(currency).strip().upper() == 'EUR':
            return rhu(amount * fx_micros, book.micros_denominator)
        return amount

    # ---- horizon -------------------------------------------------------
    period_rows = book.winners('period_order',
                               lambda r: book.code_from(r, book.alias_period))
    ordinal = {code: as_int(row['fiscal_ordinal'])
               for code, row in period_rows.items()}
    periods = sorted(ordinal, key=lambda p: (ordinal[p], p))
    span = len(periods)

    calendar = {}
    for _name, _index, row in book.rows_for_role('calendar'):
        if book.row_rejected(row):
            continue
        column = book.first_present(row, book.alias_period)
        if column is None:
            continue
        calendar[str(row.get('date', '')).strip()] = norm(row[column])

    slot = {code: index for index, code in enumerate(periods)}

    # ---- item and plant scope ------------------------------------------
    item_rows = book.winners('item_status',
                             lambda r: book.code_from(r, book.alias_item))
    item_status = {code: str(row.get('status', '')).strip().lower()
                   for code, row in item_rows.items()}
    items = sorted(code for code, status in item_status.items()
                   if status != 'retired')
    retired = {code for code, status in item_status.items() if status == 'retired'}

    family_rows = book.winners('item_family',
                               lambda r: book.code_from(r, book.alias_item))
    families = {code: str(row.get('family', '')).strip()
                for code, row in family_rows.items()}

    plant_rows = book.winners(
        'plant_status',
        lambda r: (book.code_from(r, book.alias_plant),
                   book.code_from(r, book.alias_period)))
    plants = sorted({key[0] for key in plant_rows if key[0] is not None})
    mothballed = {key for key, row in plant_rows.items()
                  if str(row.get('status', '')).strip().lower() == 'mothballed'}

    # ---- demand: blocks and overlays are one logical register ----------
    def demand_key(row):
        item = book.code_from(row, book.alias_item)
        if item is None:
            return None
        if 'date' in row and book.first_present(row, book.alias_period) is None:
            period = calendar.get(str(row.get('date', '')).strip())
        else:
            period = book.code_from(row, book.alias_period)
        if period is None:
            return None
        return (item, period)

    def demand_units(row):
        column = book.first_present(row, book.alias_dozens)
        if column is not None:
            return as_int(row[column]) * book.scale('units_dz')
        column = book.first_present(row, book.alias_units)
        return as_int(row[column]) if column is not None else 0

    demand_sources = (book.role_sources('demand') +
                      book.role_sources('demand_overlay'))
    demand_sources.sort(key=lambda s: s['name'])
    demand_live = []
    order = 0
    for source in demand_sources:
        for row in book.read_source(source):
            if book.is_live(row):
                demand_live.append((order, row))
            order += 1
    best_demand = {}
    for order, row in demand_live:
        key = demand_key(row)
        if key is None:
            continue
        rank = (book.revision(row), book.sequence(row), order)
        if key not in best_demand or rank > best_demand[key][0]:
            best_demand[key] = (rank, row)
    demand = collections.Counter()
    for key, (_rank, row) in best_demand.items():
        if key[0] in items and key[1] in slot:
            demand[key] = demand_units(row)

    # ---- coefficient rebuild -------------------------------------------
    def pair_key(row):
        item = book.code_from(row, book.alias_item)
        period = book.code_from(row, book.alias_period)
        return None if item is None or period is None else (item, period)

    base_rows = book.winners('unit_cost', pair_key)
    override_rows = book.winners('cost_override', pair_key)
    setup_rows = book.winners('setup_cost', pair_key)

    def amendment_value(row):
        amount = as_int(row['amount']) * book.scale(row.get('scale'))
        amount = to_usd_cents(amount, row.get('ccy'))
        return -amount if str(row.get('sign', '')).strip().lower() == 'credit' else amount

    amendments = book.accumulated('cost_amendment', 'amend_id', pair_key,
                                  amendment_value)
    amended_keys = set()
    seen_amend = set()
    for _order, _name, _index, row in book.live_rows('cost_amendment'):
        identity = str(row.get('amend_id', '')).strip()
        if not identity or identity in seen_amend:
            continue
        seen_amend.add(identity)
        key = pair_key(row)
        if key is not None:
            amended_keys.add(key)

    # CUT and VOI read the unit cost, amendment and override registers only.
    cut_keys, void_keys = set(), set()
    for role in ('unit_cost', 'cost_amendment', 'cost_override'):
        for _name, _index, row in book.rows_for_role(role):
            key = pair_key(row)
            if key is None:
                continue
            seq = book.sequence(row)
            if seq is None:
                continue
            if seq > cutoff:
                cut_keys.add(key)
                continue
            if (book.own_void(row) or
                    str(row.get('row_uid', '')).strip() in book.lifecycle_touched):
                void_keys.add(key)

    index_rows = book.winners('energy_index',
                              lambda r: book.code_from(r, book.alias_period))
    index_bps = {}
    for code, row in index_rows.items():
        index_bps[code] = as_int(row['index_value']) * book.scale(row.get('unit'))

    unit_cost, setup_cost, holding_cost, flags, energy_applied = {}, {}, {}, {}, {}
    for item in items:
        for period in periods:
            key = (item, period)
            letters = set()
            value = 0
            base = base_rows.get(key)
            if base is not None:
                value = as_int(base['amount']) * book.scale(base.get('scale'))
                if str(base.get('scale', '')).strip().lower() == 'kcents':
                    letters.add('KC')
                if str(base.get('ccy', '')).strip().upper() == 'EUR':
                    letters.add('FX')
                value = to_usd_cents(value, base.get('ccy'))
            if key in amended_keys:
                value += amendments.get(key, 0)
                letters.add('AMD')
            override = override_rows.get(key)
            if override is not None:
                value = to_usd_cents(
                    as_int(override['amount']) * book.scale(override.get('scale')),
                    override.get('ccy'))
                letters.add('OVR')
            applied = index_bps.get(period, 0) + surcharge_bps
            uplift = rhu(value * applied, book.bps_denominator)
            if uplift != 0:
                letters.add('ENR')
            value += uplift
            if key in cut_keys:
                letters.add('CUT')
            if key in void_keys:
                letters.add('VOI')
            unit_cost[key] = value
            energy_applied[key] = applied
            flags[key] = '+'.join(sorted(letters))
            row = setup_rows.get(key)
            setup_cost[key] = (as_int(row['amount']) * book.scale(row.get('scale'))
                               if row is not None else setup_fallback)
            holding_cost[key] = rhu(value * holding_bps, book.bps_denominator)

    # ---- capacity and handling -----------------------------------------
    def plant_period_key(row):
        plant = book.code_from(row, book.alias_plant)
        period = book.code_from(row, book.alias_period)
        return None if plant is None or period is None else (plant, period)

    capacity_base = book.winners('capacity_base', plant_period_key)
    capacity_adj = book.accumulated('capacity_adjustment', 'adj_id', plant_period_key,
                                    lambda r: as_int(r['delta_units']))
    handling_base = book.winners('handling_base', plant_period_key)
    handling_adj = book.accumulated('handling_adjustment', 'adj_id', plant_period_key,
                                    lambda r: as_int(r['delta_cents']))
    shift_rows = book.winners('shift_pattern',
                              lambda r: book.code_from(r, book.alias_plant))
    derate_rows = book.winners('holiday_derate',
                               lambda r: book.code_from(r, book.alias_period))
    zone_rows = book.winners('plant_zone',
                             lambda r: book.code_from(r, book.alias_plant))
    tariff_rows = book.winners('zone_tariff', lambda r: book.code_from(r, ['zone']))

    shift_bps = {code: as_int(row['shift_value']) * book.scale(row.get('unit'))
                 for code, row in shift_rows.items()}
    derate_bps = {code: as_int(row['derate_value']) * book.scale(row.get('unit'))
                  for code, row in derate_rows.items()}
    zone_of = {code: norm(row['zone']) for code, row in zone_rows.items()}
    uplift_bps = {code: as_int(row['uplift_value']) * book.scale(row.get('unit'))
                  for code, row in tariff_rows.items()}

    capacity = {}
    handling_pre = {}
    for plant in plants:
        for period in periods:
            key = (plant, period)
            if key in mothballed:
                capacity[key] = 0
            else:
                base = (as_int(capacity_base[key]['base_capacity_units'])
                        if key in capacity_base else 0)
                total = base + capacity_adj.get(key, 0)
                shift = shift_bps.get(plant, book.bps_denominator)
                derate = derate_bps.get(period, book.bps_denominator)
                stepped = rhu(total * shift, book.bps_denominator)
                capacity[key] = max(0, rhu(stepped * derate, book.bps_denominator))
            base = (as_int(handling_base[key]['handling_cents_per_unit'])
                    if key in handling_base else 0)
            total = base + handling_adj.get(key, 0)
            uplift = uplift_bps.get(zone_of.get(plant, ''), 0)
            handling_pre[key] = rhu(total * (book.bps_denominator + uplift),
                                    book.bps_denominator)

    # ---- stage one: capital selection ----------------------------------
    project_rows = book.winners('retrofit_project',
                                lambda r: book.code_from(r, ['project_id']))
    eligibility = book.winners('retrofit_eligibility',
                               lambda r: book.code_from(r, ['project_id']))
    capex_rows = book.winners('retrofit_capex',
                              lambda r: book.code_from(r, ['project_id']))
    savings_rows = book.winners('retrofit_savings',
                                lambda r: book.code_from(r, ['project_id']))

    best_volume = {}
    for order, (_name, _index, row) in enumerate(book.rows_for_role('capital_programme')):
        if not isinstance(row, dict) or 'committed_volume_units' not in row:
            continue
        if not book.is_live(row):
            continue
        code = book.code_from(row, ['project_id'])
        if code is None:
            continue
        rank = (book.revision(row), book.sequence(row), order)
        if code not in best_volume or rank > best_volume[code][0]:
            best_volume[code] = (rank, row)
    volume_rows = {code: as_int(row['committed_volume_units'])
                   for code, (_rank, row) in best_volume.items()}

    savings_cents = {}
    for code, row in savings_rows.items():
        amount = as_int(row['savings_value']) * book.scale(row.get('scale'))
        savings_cents[code] = to_usd_cents(amount, row.get('ccy'))
    capex_cents_of = {}
    for code, row in capex_rows.items():
        capex_cents_of[code] = as_int(row['amount']) * book.scale(row.get('scale'))

    candidates = sorted(
        code for code, row in eligibility.items()
        if str(row.get('eligible', '')).strip().lower() == 'yes'
        and code in project_rows and code in capex_cents_of
        and code in savings_cents and code in volume_rows)
    costs = [capex_cents_of[c] for c in candidates]
    values = [savings_cents[c] * volume_rows[c] for c in candidates]

    programme = CapitalProgramme(candidates, costs, values)
    selected_value, selected_capex, chosen = programme.solve(budget_cents)
    selected = sorted(candidates[i] for i in chosen)
    selected_set = set(selected)
    unfunded = [c for c in candidates if c not in selected_set]

    bumped_value, _bumped_capex, _bumped = programme.solve(budget_cents + grid_cents)
    marginal_grid_value = bumped_value - selected_value
    budget_binding = marginal_grid_value > 0

    plant_savings = collections.Counter()
    for code in selected:
        row = project_rows.get(code)
        plant = book.code_from(row, book.alias_plant) if row else None
        if plant is not None:
            plant_savings[plant] += savings_cents.get(code, 0)
    handling_rate = {}
    for key, rate in handling_pre.items():
        handling_rate[key] = max(min_handling, rate - plant_savings.get(key[0], 0))

    # ---- stage two: lot sizing -----------------------------------------
    produced = {}
    inventory = {}
    plan_blocks = {}
    lot_cost = {}
    for item in items:
        dem = [demand.get((item, p), 0) for p in periods]
        unit = [unit_cost[(item, p)] for p in periods]
        setup = [setup_cost[(item, p)] for p in periods]
        hold = [holding_cost[(item, p)] for p in periods]
        total, made, blocks = lot_size(dem, unit, setup, hold)
        lot_cost[item] = total
        plan_blocks[item] = blocks
        carried = 0
        for index, period in enumerate(periods):
            produced[(item, period)] = made[index]
            carried += made[index] - dem[index]
            inventory[(item, period)] = carried

    # ---- stage three: sourcing -----------------------------------------
    allocation = []
    assigned = collections.Counter()
    shortfall = {}
    required_by_period = {}
    for period in periods:
        pending = [(item, produced[(item, period)]) for item in items
                   if produced[(item, period)] > 0]
        required_by_period[period] = sum(units for _item, units in pending)
        fill_order = sorted(plants, key=lambda p: (handling_rate[(p, period)], p))
        cursor = 0
        for plant in fill_order:
            room = capacity[(plant, period)]
            if room <= 0:
                continue
            while room > 0 and cursor < len(pending):
                item, available = pending[cursor]
                move = min(room, available)
                if move > 0:
                    rate = handling_rate[(plant, period)]
                    allocation.append([period, ordinal[period], plant, item, move,
                                       rate, move * rate])
                    assigned[(plant, period)] += move
                    room -= move
                    available -= move
                pending[cursor] = (item, available)
                if available == 0:
                    cursor += 1
        shortfall[period] = sum(units for _item, units in pending[cursor:])

    # ---- cost roll up ---------------------------------------------------
    production_cost = collections.Counter()
    setup_total = collections.Counter()
    setup_count = collections.Counter()
    holding_total = collections.Counter()
    plan_rows = []
    for item in items:
        for start, end, quantity in plan_blocks[item]:
            period = periods[start]
            cost = unit_cost[(item, period)] * quantity
            production_cost[period] += cost
            setup_total[period] += setup_cost[(item, period)]
            setup_count[item] += 1
            covered = [periods[i] for i in range(start, end)
                       if demand.get((item, periods[i]), 0) > 0]
            plan_rows.append({
                'covers_periods': covered,
                'fiscal_ordinal': ordinal[period],
                'item': item,
                'period': period,
                'produced_units': quantity,
                'production_cost_cents': cost,
                'setup_cost_cents': setup_cost[(item, period)]})
        for period in periods:
            holding_total[period] += inventory[(item, period)] * holding_cost[(item, period)]
    plan_rows.sort(key=lambda r: (r['item'], r['fiscal_ordinal']))

    handling_by_period = collections.Counter()
    for row in allocation:
        handling_by_period[row[0]] += row[6]
    penalty_by_period = {p: shortfall[p] * penalty_cents for p in periods}

    period_costs = {}
    for period in periods:
        entry = {
            'handling_cost_cents': handling_by_period.get(period, 0),
            'holding_cost_cents': holding_total.get(period, 0),
            'production_cost_cents': production_cost.get(period, 0),
            'setup_cost_cents': setup_total.get(period, 0),
            'shortfall_penalty_cents': penalty_by_period[period]}
        entry['total_cents'] = sum(entry.values())
        period_costs[period] = entry

    total_production = sum(production_cost.values())
    total_setup = sum(setup_total.values())
    total_holding = sum(holding_total.values())
    total_handling = sum(handling_by_period.values())
    total_penalty = sum(penalty_by_period.values())
    total_objective = (total_production + total_setup + total_holding +
                       total_handling + total_penalty + selected_capex)

    total_demand = sum(demand.get((i, p), 0) for i in items for p in periods)
    total_produced = sum(produced.values())
    total_shortfall = sum(shortfall.values())

    # ---- certificates ---------------------------------------------------
    zero_inventory = True
    reconstructed = True
    for item in items:
        rebuilt = 0
        for start, end, quantity in plan_blocks[item]:
            if start > 0 and inventory[(item, periods[start - 1])] != 0:
                zero_inventory = False
            rebuilt += setup_cost[(item, periods[start])]
            rebuilt += unit_cost[(item, periods[start])] * quantity
        for period in periods:
            rebuilt += inventory[(item, period)] * holding_cost[(item, period)]
        if rebuilt != lot_cost[item]:
            reconstructed = False

    placed_by_period = collections.Counter()
    for row in allocation:
        placed_by_period[row[0]] += row[4]
    covered_or_charged = True
    for period in periods:
        if placed_by_period.get(period, 0) + shortfall[period] != required_by_period[period]:
            covered_or_charged = False
    for item in items:
        if (sum(produced[(item, p)] for p in periods) !=
                sum(demand.get((item, p), 0) for p in periods)):
            covered_or_charged = False

    no_cheaper_idle = True
    for period in periods:
        idle_rates = [handling_rate[(p, period)] for p in plants
                      if capacity[(p, period)] - assigned.get((p, period), 0) > 0]
        used_rates = [handling_rate[(p, period)] for p in plants
                      if assigned.get((p, period), 0) > 0]
        if idle_rates and used_rates and min(idle_rates) < max(used_rates):
            no_cheaper_idle = False

    remaining = budget_cents - selected_capex
    no_unfunded_fits = True
    for code in unfunded:
        if (savings_cents[code] * volume_rows[code] > 0 and
                capex_cents_of[code] <= remaining):
            no_unfunded_fits = False

    # ---- sensitivity ----------------------------------------------------
    next_unit = {}
    for period in periods:
        idle = [handling_rate[(p, period)] for p in plants
                if capacity[(p, period)] - assigned.get((p, period), 0) > 0]
        next_unit[period] = min(idle) if idle else penalty_cents

    top_project, top_capex = '', 0
    if unfunded:
        def ratio_key(code):
            value = savings_cents[code] * volume_rows[code]
            cost = capex_cents_of[code]
            if cost == 0:
                return (0, 0, code)
            return (1, -Fraction(value, cost), code)
        top_project = sorted(unfunded, key=ratio_key)[0]
        top_capex = capex_cents_of[top_project]

    # ---- incumbent comparison ------------------------------------------
    incumbent_unit = {}
    for _name, _index, row in book.rows_for_role('incumbent_plan', authority=None):
        key = (norm(row['item']), norm(row['period']))
        incumbent_unit[key] = as_int(row['unit_cost_cents'])

    incumbent_total = 0
    incumbent_components = {}
    incumbent_projects = []
    for source in book.by_role.get('incumbent_report', []):
        with open(book.path(source['name']), encoding='utf-8') as handle:
            report = json.load(handle)
        incumbent_total = as_int(report.get('published_total_objective_cents', 0))
        incumbent_components = {k: as_int(v) for k, v in
                                report.get('stage_totals_cents', {}).items()}
        incumbent_projects = sorted(norm(p) for p in report.get('selected_projects', []))

    corrected_components = {
        'capex_cents': selected_capex,
        'handling_cost_cents': total_handling,
        'holding_cost_cents': total_holding,
        'production_cost_cents': total_production,
        'setup_cost_cents': total_setup,
        'shortfall_penalty_cents': total_penalty}
    component_deltas = {name: corrected_components[name] - incumbent_components[name]
                        for name in sorted(set(corrected_components) &
                                           set(incumbent_components))}

    # ---- sweep: rejections and input accounting -------------------------
    rejected = []
    out_of_scope_rows = 0
    void_rows = 0
    demand_roles = {'demand', 'demand_overlay'}
    id_groups = [book.alias_item, book.alias_period, book.alias_plant,
                 ['project_id', 'project', 'project_code'], ['zone', 'zone_code']]

    def reject_key(row):
        fields = []
        for position, aliases in enumerate(id_groups):
            column = book.first_present(row, aliases)
            if column is None:
                if position == 1 and 'date' in row:
                    fields.append(calendar.get(str(row.get('date', '')).strip(), ''))
                continue
            fields.append(norm(row.get(column)))
        return ':'.join(fields)

    for source in book.sources:
        if source['authority'] != 'primary' or source['fmt'] not in SWEEP_FMT:
            continue
        rows = book.read_source(source)
        if isinstance(rows, dict):
            continue
        is_demand = source['role'] in demand_roles
        for row in rows:
            if not isinstance(row, dict):
                continue
            seq = book.sequence(row)
            reason = None
            if is_demand:
                item = book.code_from(row, book.alias_item)
                if item is None or item not in item_status:
                    reason = 'unknown_item'
                elif item in retired:
                    reason = 'retired_item'
            if reason is None and book.row_rejected(row):
                reason = 'sentinel'
            if reason is not None:
                rejected.append([source['name'], str(row.get('row_uid', '')).strip(),
                                 reject_key(row), reason])
                continue
            if seq is None:
                continue
            if seq > cutoff:
                out_of_scope_rows += 1
                continue
            if (book.own_void(row) or
                    book.lifecycle_voided(row.get('row_uid', ''))):
                void_rows += 1
    rejected.sort(key=lambda r: (r[0], r[1]))

    source_report = []
    mismatches = []
    for source in book.sources:
        seen = book.physical_count(source)
        declared = source['declared']
        declared = None if declared is None else as_int(declared)
        source_report.append({
            'authority': source['authority'],
            'fmt': source['fmt'],
            'name': source['name'],
            'record_count_declared': declared,
            'role': source['role'],
            'rows_seen': seen})
        if declared is not None and declared != seen:
            mismatches.append(source['name'])

    # ---- artifacts ------------------------------------------------------
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)

    def target(name):
        return os.path.join(out_dir, name)

    key_order = [(item, period) for item in items for period in periods]

    write_jsonl(target('corrected_coefficients.jsonl'), [{
        'demand_units': demand.get(key, 0),
        'energy_bps_applied': energy_applied[key],
        'fiscal_ordinal': ordinal[key[1]],
        'flags': flags[key],
        'holding_cost_cents': holding_cost[key],
        'item': key[0],
        'period': key[1],
        'setup_cost_cents': setup_cost[key],
        'unit_cost_cents': unit_cost[key]} for key in key_order])

    write_json(target('objective.json'), {
        'capex_cents': selected_capex,
        'handling_cost_cents': total_handling,
        'holding_cost_cents': total_holding,
        'items_in_scope': len(items),
        'periods_in_horizon': span,
        'plants_in_scope': len(plants),
        'production_cost_cents': total_production,
        'setup_cost_cents': total_setup,
        'shortfall_penalty_cents': total_penalty,
        'total_demand_units': total_demand,
        'total_objective_cents': total_objective,
        'total_produced_units': total_produced,
        'total_shortfall_units': total_shortfall})

    write_jsonl(target('optimal_plan.jsonl'), plan_rows)

    write_csv(target('production_schedule.csv'),
              ['item', 'period', 'fiscal_ordinal', 'demand_units',
               'produced_units', 'ending_inventory_units'],
              [[key[0], key[1], ordinal[key[1]], demand.get(key, 0),
                produced[key], inventory[key]] for key in key_order])

    holding_rows = []
    for item in items:
        running = 0
        for period in periods:
            key = (item, period)
            charge = inventory[key] * holding_cost[key]
            running += charge
            holding_rows.append([item, period, ordinal[period], inventory[key],
                                 holding_cost[key], charge, running])
    write_csv(target('holding_profile.csv'),
              ['item', 'period', 'fiscal_ordinal', 'ending_inventory_units',
               'holding_rate_cents', 'period_holding_cents',
               'cumulative_holding_cents'], holding_rows)

    write_csv(target('sourcing_allocation.csv'),
              ['period', 'fiscal_ordinal', 'plant', 'item', 'units',
               'handling_rate_cents', 'handling_cost_cents'], allocation)

    utilisation_rows = []
    full_capacity = []
    zero_capacity = []
    for plant in plants:
        for period in periods:
            key = (plant, period)
            room = capacity[key]
            used = assigned.get(key, 0)
            bps = rhu(used * book.bps_denominator, room) if room else 0
            utilisation_rows.append([plant, period, ordinal[period], room, used,
                                     room - used, bps])
            if room == 0:
                zero_capacity.append([plant, period])
            elif used == room:
                full_capacity.append([plant, period])
    write_csv(target('plant_utilization.csv'),
              ['plant', 'period', 'fiscal_ordinal', 'capacity_units',
               'assigned_units', 'idle_units', 'utilisation_bps'],
              utilisation_rows)

    write_csv(target('shortfall_ledger.csv'),
              ['period', 'fiscal_ordinal', 'required_units', 'capacity_units',
               'shortfall_units', 'penalty_rate_cents', 'penalty_cents'],
              [[period, ordinal[period], required_by_period[period],
                sum(capacity[(p, period)] for p in plants), shortfall[period],
                penalty_cents, penalty_by_period[period]] for period in periods])

    write_json(target('retrofit_selection.json'), {
        'budget_cents': budget_cents,
        'candidate_project_ids': candidates,
        'capex_grid_cents': grid_cents,
        'eligible_project_count': len(candidates),
        'rejected_project_ids': unfunded,
        'selected_capex_cents': selected_capex,
        'selected_project_ids': selected,
        'selected_value_cents': selected_value})

    write_json(target('budget_utilization.json'), {
        'budget_binding': budget_binding,
        'budget_cents': budget_cents,
        'capex_cents': selected_capex,
        'slack_cents': remaining,
        'slack_grid_units': remaining // grid_cents,
        'utilisation_bps': (rhu(selected_capex * book.bps_denominator, budget_cents)
                            if budget_cents else 0)})

    write_json(target('period_costs.json'), period_costs)

    item_summary = {}
    for item in items:
        produced_units = sum(produced[(item, p)] for p in periods)
        production = sum(unit_cost[(item, periods[s])] * q
                         for s, _e, q in plan_blocks[item])
        setups = sum(setup_cost[(item, periods[s])] for s, _e, _q in plan_blocks[item])
        holding = sum(inventory[(item, p)] * holding_cost[(item, p)] for p in periods)
        item_summary[item] = {
            'demand_units': sum(demand.get((item, p), 0) for p in periods),
            'family': families.get(item, ''),
            'holding_cost_cents': holding,
            'produced_units': produced_units,
            'production_cost_cents': production,
            'setup_count': setup_count.get(item, 0),
            'setup_cost_cents': setups,
            'total_cents': production + setups + holding}
    write_json(target('item_summary.json'), item_summary)

    shortfall_periods = [p for p in periods if shortfall[p] > 0]
    write_json(target('binding_constraints.json'), {
        'binding_count': (len(full_capacity) + len(shortfall_periods) +
                          (1 if budget_binding else 0)),
        'budget_binding': budget_binding,
        'full_capacity_plant_periods': full_capacity,
        'shortfall_periods': shortfall_periods,
        'zero_capacity_plant_periods': zero_capacity})

    write_json(target('optimality_certificate.json'), {
        'all_demand_covered_or_charged': covered_or_charged,
        'capital_no_unfunded_candidate_fits': no_unfunded_fits,
        'lot_sizing_reconstructed_cost_matches': reconstructed,
        'lot_sizing_zero_inventory_property': zero_inventory,
        'sourcing_no_cheaper_idle_capacity': no_cheaper_idle,
        'total_objective_cents': total_objective})

    write_json(target('sensitivity_report.json'), {
        'budget_binding': budget_binding,
        'budget_grid_unit_cents': grid_cents,
        'marginal_value_of_one_grid_unit_cents': marginal_grid_value,
        'next_unit_cost_by_period': next_unit,
        'top_unfunded_capex_cents': top_capex,
        'top_unfunded_project_id': top_project})

    write_json(target('incumbent_delta.json'), {
        'component_deltas': component_deltas,
        'corrected_selected_project_ids': selected,
        'corrected_total_objective_cents': total_objective,
        'delta_cents': total_objective - incumbent_total,
        'incumbent_selected_project_ids': incumbent_projects,
        'incumbent_total_objective_cents': incumbent_total,
        'projects_added': sorted(selected_set - set(incumbent_projects)),
        'projects_dropped': sorted(set(incumbent_projects) - selected_set)})

    write_csv(target('coefficient_corrections.csv'),
              ['item', 'period', 'incumbent_unit_cost_cents',
               'corrected_unit_cost_cents', 'delta_cents', 'flags'],
              [[key[0], key[1], incumbent_unit.get(key, 0), unit_cost[key],
                unit_cost[key] - incumbent_unit.get(key, 0), flags[key]]
               for key in key_order if unit_cost[key] != incumbent_unit.get(key, 0)])

    write_json(target('data_quality.json'), {
        'count_mismatches': sorted(mismatches),
        'sources': source_report,
        'totals': {
            'out_of_scope_rows': out_of_scope_rows,
            'rejected_rows': len(rejected),
            'sources_seen': len(book.sources),
            'void_rows': void_rows}})

    write_csv(target('rejected_records.csv'),
              ['source', 'row_uid', 'key', 'reason'], rejected)

    figures = [
        ('corrected_total_objective_cents', total_objective),
        ('incumbent_total_objective_cents', incumbent_total),
        ('delta_cents', total_objective - incumbent_total),
        ('selected_capex_cents', selected_capex),
        ('budget_cents', budget_cents),
        ('total_shortfall_units', total_shortfall),
        ('shortfall_penalty_cents', total_penalty),
        ('items_in_scope', len(items)),
        ('rejected_rows', len(rejected))]
    write_lines(target('reconciliation.txt'),
                ['%s=%s' % (name, value) for name, value in figures])
    write_lines(target('audit_summary.md'),
                ['# Replan Audit Summary', ''] +
                ['- %s: %s' % (name, value) for name, value in figures] +
                ['', 'Selected projects: ' + ', '.join(selected)])

    return {'objective': total_objective, 'rejected': len(rejected),
            'out_of_scope': out_of_scope_rows, 'void': void_rows,
            'capex': selected_capex, 'budget': budget_cents,
            'cutoff': cutoff, 'surcharge_bps': surcharge_bps,
            'holding_bps': holding_bps, 'penalty_cents': penalty_cents,
            'fx_micros': fx_micros, 'candidates': len(candidates),
            'selected': selected, 'shortfall': total_shortfall,
            'mismatches': sorted(mismatches)}


def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: %s <DATA_DIR> <OUT_DIR>\n' % os.path.basename(argv[0]))
        return 2
    summary = run(argv[1], argv[2])
    for name in sorted(summary):
        sys.stdout.write('%s=%s\n' % (name, summary[name]))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
