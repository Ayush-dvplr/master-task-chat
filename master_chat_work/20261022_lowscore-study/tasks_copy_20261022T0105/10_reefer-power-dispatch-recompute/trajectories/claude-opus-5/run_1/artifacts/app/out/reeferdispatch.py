#!/usr/bin/env python3
"""Ashgrove Point reefer yard dispatch recomputation.

Fourteen stages, exact rational arithmetic, standard library only.
Every identifier, control value, threshold, boundary and rung code is read
from the directory the --data option points at.
"""

import argparse
import csv
import hashlib
import json
import os
import re
import zipfile
import zlib
import xml.etree.ElementTree as ET
from fractions import Fraction


# --------------------------------------------------------------------------
# exact arithmetic helpers
# --------------------------------------------------------------------------

def frac(value):
    return value if isinstance(value, Fraction) else Fraction(value)


def round_half_up(value):
    """A remainder of exactly one half is carried away from zero."""
    v = frac(value)
    n, d = v.numerator, v.denominator
    if n >= 0:
        return (2 * n + d) // (2 * d)
    return -((2 * (-n) + d) // (2 * d))


def floor_div(value):
    v = frac(value)
    return v.numerator // v.denominator


def ceil_div(value):
    v = frac(value)
    return -((-v.numerator) // v.denominator)


def fmt_ratio(value):
    scaled = round_half_up(frac(value) * 1000000000)
    negative = scaled < 0
    scaled = abs(scaled)
    text = str(scaled).rjust(10, '0')
    out = text[:-9] + '.' + text[-9:]
    return ('-' + out) if (negative and scaled != 0) else out


def fmt_whole(value):
    n = int(value)
    return '0' if n == 0 else str(n)


# --------------------------------------------------------------------------
# plain text readers
# --------------------------------------------------------------------------

def read_delimited(path, delimiter):
    with open(path, newline='', encoding='utf-8') as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def read_lines(path):
    with open(path, encoding='utf-8') as handle:
        return handle.read().split('\n')


def read_jsonl(path):
    out = []
    with open(path, encoding='utf-8') as handle:
        for line in handle:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def parse_toml(path):
    """Minimal reader for the flat toml papers of this corpus."""

    def scalar(text):
        text = text.strip()
        if text.startswith('"') and text.endswith('"'):
            return text[1:-1]
        if text.startswith('[') and text.endswith(']'):
            body = text[1:-1].strip()
            if not body:
                return []
            return [scalar(part) for part in split_top(body)]
        if text.startswith('{') and text.endswith('}'):
            table = {}
            for part in split_top(text[1:-1]):
                if '=' in part:
                    key, value = part.split('=', 1)
                    table[key.strip()] = scalar(value)
            return table
        if text in ('true', 'false'):
            return text == 'true'
        if re.fullmatch(r'-?\d+', text):
            return int(text)
        return text

    def split_top(text):
        parts, depth, quoted, buf = [], 0, False, ''
        for ch in text:
            if ch == '"':
                quoted = not quoted
            if not quoted:
                if ch in '[{':
                    depth += 1
                elif ch in ']}':
                    depth -= 1
                elif ch == ',' and depth == 0:
                    parts.append(buf)
                    buf = ''
                    continue
            buf += ch
        if buf.strip():
            parts.append(buf)
        return parts

    data = {}
    current = data
    for raw in read_lines(path):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('[') and line.endswith(']'):
            current = data.setdefault(line[1:-1], {})
            continue
        if '=' not in line:
            continue
        key, value = line.split('=', 1)
        current[key.strip()] = scalar(value)
    return data


def parse_conf_sections(path):
    """Read an ini style paper, keeping the printed section order."""
    order, sections, current = [], {}, None
    for raw in read_lines(path):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('[') and line.endswith(']'):
            current = line[1:-1]
            order.append(current)
            sections[current] = {}
            continue
        if '=' not in line or current is None:
            continue
        key, value = line.split('=', 1)
        sections[current][key.strip()] = value.strip()
    return order, sections


# --------------------------------------------------------------------------
# office paper readers
# --------------------------------------------------------------------------

XL_MAIN = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
XL_REL = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
PKG_REL = '{http://schemas.openxmlformats.org/package/2006/relationships}'
WORD_MAIN = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def read_workbook(path):
    """Return the sheets in printed order as (name, {cell reference: text})."""
    archive = zipfile.ZipFile(path)
    try:
        names = archive.namelist()
        shared = []
        if 'xl/sharedStrings.xml' in names:
            root = ET.fromstring(archive.read('xl/sharedStrings.xml'))
            for item in root.findall(XL_MAIN + 'si'):
                shared.append(''.join(t.text or '' for t in item.iter(XL_MAIN + 't')))
        targets = {}
        rels = ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
        for rel in rels.findall(PKG_REL + 'Relationship'):
            targets[rel.get('Id')] = rel.get('Target')
        sheets = []
        book = ET.fromstring(archive.read('xl/workbook.xml'))
        for sheet in book.iter(XL_MAIN + 'sheet'):
            target = targets.get(sheet.get(XL_REL + 'id'), '')
            part = target[1:] if target.startswith('/') else 'xl/' + target
            cells = {}
            grid = ET.fromstring(archive.read(part))
            for row in grid.iter(XL_MAIN + 'row'):
                for cell in row.findall(XL_MAIN + 'c'):
                    kind = cell.get('t')
                    value = cell.find(XL_MAIN + 'v')
                    inline = cell.find(XL_MAIN + 'is')
                    if kind == 's' and value is not None:
                        text = shared[int(value.text)]
                    elif kind == 'inlineStr' and inline is not None:
                        text = ''.join(t.text or '' for t in inline.iter(XL_MAIN + 't'))
                    elif value is not None:
                        text = value.text or ''
                    else:
                        text = ''
                    cells[cell.get('r')] = text
            sheets.append((sheet.get('name'), cells))
        return sheets
    finally:
        archive.close()


def sheet_rows(cells):
    """Rows of a sheet as {column letter: text}, in ascending row order."""
    rows = {}
    for ref, text in cells.items():
        match = re.fullmatch(r'([A-Z]+)(\d+)', ref)
        if match:
            rows.setdefault(int(match.group(2)), {})[match.group(1)] = text
    return [(number, rows[number]) for number in sorted(rows)]


def pdf_text_lines(path):
    """Text showing operators of every content stream, in printed order."""

    def unescape(text):
        text = re.sub(r'\\(\d{1,3})', lambda m: chr(int(m.group(1), 8)), text)
        return text.replace('\\(', '(').replace('\\)', ')').replace('\\\\', '\\')

    with open(path, 'rb') as handle:
        raw = handle.read()
    lines, seen = [], set()
    for match in re.finditer(rb'stream\r?\n', raw):
        start = match.end()
        end = raw.find(b'endstream', start)
        if end < 0:
            continue
        body = raw[start:end]
        if body.endswith(b'\r\n'):
            body = body[:-2]
        elif body[-1:] in (b'\n', b'\r'):
            body = body[:-1]
        try:
            body = zlib.decompress(body)
        except zlib.error:
            pass
        if body in seen:
            continue
        seen.add(body)
        text = body.decode('latin-1')
        pattern = r'\[((?:[^\[\]\\]|\\.)*)\]\s*TJ|\(((?:[^()\\]|\\.)*)\)\s*Tj'
        for token in re.finditer(pattern, text):
            group = token.group(1)
            source = group if group is not None else '(' + (token.group(2) or '') + ')'
            pieces = re.findall(r'\(((?:[^()\\]|\\.)*)\)', source)
            lines.append(''.join(unescape(piece) for piece in pieces))
    return lines


def docx_tables(path):
    archive = zipfile.ZipFile(path)
    try:
        root = ET.fromstring(archive.read('word/document.xml'))
    finally:
        archive.close()
    tables = []
    for table in root.iter(WORD_MAIN + 'tbl'):
        rows = []
        for row in table.findall(WORD_MAIN + 'tr'):
            cells = []
            for cell in row.findall(WORD_MAIN + 'tc'):
                cells.append(''.join(t.text or '' for t in cell.iter(WORD_MAIN + 't')).strip())
            rows.append(cells)
        tables.append(rows)
    return tables


# --------------------------------------------------------------------------
# serialisation
# --------------------------------------------------------------------------

def json_object_text(obj, level=0):
    pad = '  ' * level
    inner = '  ' * (level + 1)
    if isinstance(obj, dict):
        if not obj:
            return '{}'
        items = list(obj.items())
        lines = ['{']
        for index, (key, value) in enumerate(items):
            tail = '' if index == len(items) - 1 else ','
            lines.append(inner + json.dumps(key, ensure_ascii=False) + ': '
                         + json_object_text(value, level + 1) + tail)
        lines.append(pad + '}')
        return '\n'.join(lines)
    if isinstance(obj, list):
        if not obj:
            return '[]'
        lines = ['[']
        for index, value in enumerate(obj):
            tail = '' if index == len(obj) - 1 else ','
            lines.append(inner + json_object_text(value, level + 1) + tail)
        lines.append(pad + ']')
        return '\n'.join(lines)
    if isinstance(obj, bool):
        return 'true' if obj else 'false'
    if isinstance(obj, int):
        return str(obj)
    if isinstance(obj, str):
        return json.dumps(obj, ensure_ascii=False)
    raise TypeError('unpublishable value')


class Publication:
    def __init__(self, outdir):
        self.outdir = outdir
        self.payloads = {}

    def write(self, name, text):
        data = text.encode('utf-8')
        with open(os.path.join(self.outdir, name), 'wb') as handle:
            handle.write(data)
        self.payloads[name] = data

    def delimited(self, name, header, rows, delimiter):
        lines = [delimiter.join(header)]
        lines.extend(delimiter.join(str(field) for field in row) for row in rows)
        self.write(name, '\n'.join(lines) + '\n')

    def object_document(self, name, obj):
        self.write(name, json_object_text(obj) + '\n')

    def line_objects(self, name, objects):
        lines = [json.dumps(obj, separators=(',', ':'), ensure_ascii=False)
                 for obj in objects]
        self.write(name, ('\n'.join(lines) + '\n') if lines else '')

    def digest(self, names):
        engine = hashlib.sha256()
        for name in names:
            engine.update(self.payloads[name])
        return engine.hexdigest()


# --------------------------------------------------------------------------
# the corpus
# --------------------------------------------------------------------------

class Corpus:
    def __init__(self, datadir):
        self.dir = datadir
        join = lambda name: os.path.join(datadir, name)

        topology = ET.parse(join('substation_topology.xml')).getroot()
        self.day_id = topology.get('day')
        self.day_reference = topology.get('reference')
        self.substation_order = []
        self.substation_ceiling_topology = {}
        self.feeders_in_force = []
        self.plug_zone_topology = {}
        for substation in topology.findall('substation'):
            sid = substation.get('id')
            self.substation_order.append(sid)
            self.substation_ceiling_topology[sid] = int(substation.get('ceiling_w'))
            for feeder in substation.findall('feeder'):
                self.feeders_in_force.append(feeder.get('id'))
                for plug in feeder.findall('plug'):
                    self.plug_zone_topology[plug.get('id')] = plug.get('zone')
        self.feeders_in_force_set = set(self.feeders_in_force)

        self.precedence = parse_toml(join('revision_precedence.toml'))
        self.applicable = set(self.precedence['record_state']['applicable'])
        self.set_aside = set(self.precedence['record_state']['set_aside'])
        self.sequence_field = self.precedence['sequence_field']

        self.units = parse_toml(join('unit_register_dictionary.toml'))
        self.form = parse_toml(join('publication_form_rules.toml'))
        self.absent = self.form['absent_marker']
        self.state_words = self.form['state_words']
        self.precedence_policy = parse_toml(join('priority_precedence_policy.toml'))
        self.pass_policy = parse_toml(join('reconciliation_pass_policy.toml'))
        self.battery_policy = parse_toml(join('battery_operating_policy.toml'))

        self.reefer_rows = read_delimited(join('reefer_service_register.csv'), ',')
        self.declaration_rows = read_delimited(join('energy_declaration_returns.psv'), '|')
        self.plug_rows = read_delimited(join('plug_assignment_register.csv'), ',')
        self.capacity_rows = read_delimited(join('feeder_capacity_register.csv'), ',')
        self.derating_rows = read_delimited(join('feeder_derating_notices.csv'), ',')
        self.call_rows = read_delimited(join('vessel_call_register.csv'), ',')
        self.withdrawn_rows = read_delimited(join('withdrawn_call_journal.tsv'), '\t')
        self.grid_rows = read_delimited(join('interval_grid_calendar.csv'), ',')
        self.window_rows = read_delimited(join('maintenance_window_register.csv'), ',')
        self.zone_rows = read_delimited(join('plug_zone_admission_matrix.csv'), ',')
        self.tariff_rows = read_delimited(join('tariff_interval_schedule.csv'), ',')
        self.band_rows = read_delimited(join('demand_charge_bands.tsv'), '\t')
        self.telemetry_rows = read_delimited(join('battery_telemetry_returns.csv'), ',')
        self.source_rows = read_delimited(join('source_priority_register.csv'), ',')

        self.ambient = json.load(open(join('ambient_condition_returns.json'), encoding='utf-8'))
        self.notices = read_jsonl(join('exception_notices.jsonl'))
        self.duty_rows = read_jsonl(join('crane_duty_feed.ndjson'))
        self.confirm_rows = read_jsonl(join('crane_confirmation_journal.jsonl'))

        self.ladder_order = []
        for line in read_lines(join('dispatch_admission_ladder.txt')):
            match = re.match(r'\s*rung\s+\d+\s+(DR_[A-Z_]+)\s*$', line)
            if match:
                self.ladder_order.append(match.group(1))

        self.stage_titles = []
        for line in read_lines(join('terminal_contract_overview.md')):
            match = re.match(r'Stage (p\d+), (.+)\. Specification', line.strip())
            if match:
                self.stage_titles.append((match.group(1), match.group(2)))

        roster_order, roster = parse_conf_sections(join('reporting_feeder_roster.conf'))
        self.reported_substations = []
        self.report_names = {}
        for name in roster_order:
            block = roster[name]
            if 'report' in block and block.get('published') == 'yes':
                self.reported_substations.append(name)
                self.report_names[name] = block['report']

        self._read_contract(join('serialisation_and_digest_contract.md'))
        self._read_workbook(join('substation_capacity_workbook.xlsx'))
        self._read_memo(join('dispatch_operations_memo.pdf'))
        self._read_directive(join('priority_ordering_directive.docx'))
        self._interval_grid()

    # -- the publication order and the core digest order ------------------

    def _read_contract(self, path):
        text = ' '.join(read_lines(path))
        pattern = r'[a-z_]+\.(?:jsonl|json|csv|psv|tsv|xml|conf|md)'

        core = text.split('concatenated in this order:', 1)[1]
        core = core.split('The publication digest', 1)[0]
        self.core_documents = re.findall(pattern, core)
        if not self.core_documents:
            raise SystemExit('the core digest order read no document')

        spine = text.split('First the fourteen stage documents', 1)[1]
        spine, rest = spine.split('Then the load family', 1)
        load, rest = rest.split('Then the tariff family', 1)
        tariff, publication = rest.split('Then the publication family', 1)

        self.stage_documents = re.findall(pattern, spine)
        before, after = publication.split('one substation report', 1)
        order = re.findall(pattern, before)
        order += [self.report_names[s] for s in self.reported_substations]
        order += re.findall(pattern, after)
        self.document_order = (self.stage_documents + re.findall(pattern, load)
                               + re.findall(pattern, tariff) + order)

    # -- the governing workbook sheet -------------------------------------

    def _read_workbook(self, path):
        self.live_sheet = None
        for name, cells in read_workbook(path):
            rows = sheet_rows(cells)
            key = None
            for _, row in rows:
                if row.get('A', '').strip().lower() == 'day reference':
                    key = row.get('B', '').strip()
                    break
            if key == self.day_reference:
                self.live_sheet = name
                self._parse_live_sheet(rows)
                break
        if self.live_sheet is None:
            raise SystemExit('no workbook sheet carries the day reference')

    def _parse_live_sheet(self, rows):
        self.maintenance_coefficient = {}
        self.vessel_ceiling = {}
        self.substation_ceiling = {}
        mode = None
        for _, row in rows:
            label = row.get('A', '').strip()
            b = row.get('B', '').strip()
            c = row.get('C', '').strip()
            low = label.lower()
            if low == 'control':
                mode = 'control'
                continue
            if low == 'temperature class':
                mode = 'maintenance'
                continue
            if low == 'vessel':
                mode = 'vessel'
                continue
            if low == 'substation':
                mode = 'substation'
                continue
            if low == 'feeder':
                mode = 'feeder'
                continue
            if not label:
                continue
            if low == 'reconciliation damping fraction':
                self.damping = Fraction(int(b), int(c))
                continue
            if low == 'base service charge cents':
                self.base_service_charge = round_half_up(Fraction(int(b), int(c)))
                continue
            if mode == 'maintenance' and b and c:
                self.maintenance_coefficient[label] = Fraction(int(b), int(c))
            elif mode == 'vessel' and b:
                self.vessel_ceiling[label] = int(b)
            elif mode == 'substation' and b:
                self.substation_ceiling[label] = int(b)

    # -- the operations memorandum ----------------------------------------

    def _read_memo(self, path):
        lines = pdf_text_lines(path)
        self.pass_budget = None
        self.minimum_step = None
        self.protection_depth = None
        self.surcharge_ladder = []
        self.crane_roster = []
        in_ladder = False
        in_roster = False
        for line in lines:
            squeezed = ' '.join(line.split())
            low = squeezed.lower()
            number = re.search(r'(-?\d+)\s*$', squeezed)
            if low.startswith('pass budget') and number and self.pass_budget is None:
                self.pass_budget = int(number.group(1))
            elif low.startswith('minimum step') and number and self.minimum_step is None:
                self.minimum_step = int(number.group(1))
            elif low.startswith('dependency protection depth') and number \
                    and self.protection_depth is None:
                self.protection_depth = int(number.group(1))
            if 'intervals short' in low and 'surcharge' in low:
                in_ladder = True
                continue
            if in_ladder:
                rung = re.fullmatch(r'(\d+)\s+(\d+)', squeezed)
                if rung:
                    self.surcharge_ladder.append((int(rung.group(1)), int(rung.group(2))))
                    continue
                if squeezed:
                    in_ladder = False
            if low.startswith('gang') and 'crane' in low and 'shift' in low:
                in_roster = True
                continue
            if in_roster:
                gang = re.fullmatch(r'(gang_\w+)\s+(cr_\w+)\s+(\w+)\s+(\w+)', squeezed)
                if gang:
                    self.crane_roster.append(gang.groups())
                    continue
                if squeezed:
                    in_roster = False
        self.surcharge_ladder.sort()

    # -- the priority ordering directive ----------------------------------

    def _read_directive(self, path):
        self.ordering_keys = []
        self.class_rank = {}
        for table in docx_tables(path):
            if not table:
                continue
            header = [cell.strip().lower() for cell in table[0]]
            if 'ordering key' in header:
                position = header.index('key position')
                key = header.index('ordering key')
                rows = []
                for row in table[1:]:
                    if len(row) > max(position, key):
                        rows.append((int(row[position]), row[key].strip()))
                self.ordering_keys = [name for _, name in sorted(rows)]
            elif 'class rank' in header:
                name = header.index('temperature class')
                rank = header.index('class rank')
                for row in table[1:]:
                    if len(row) > max(name, rank):
                        self.class_rank[row[name].strip()] = int(row[rank])

    # -- the interval grid ------------------------------------------------

    def _interval_grid(self):
        self.intervals_per_day = int(self.units['time']['intervals_per_day'])
        self.interval_minutes = int(self.units['time']['interval_minutes'])
        self.intervals = list(range(1, self.intervals_per_day + 1))
        self.tariff_band = {}
        self.ambient_class = {}
        for row in self.grid_rows:
            if row['day_id'] != self.day_id:
                continue
            self.tariff_band[int(row['interval'])] = row['tariff_band']
        for reading in self.ambient['interval_readings']:
            if reading['day_id'] == self.day_id:
                self.ambient_class[int(reading['interval'])] = reading['ambient_class']

    # -- row precedence ---------------------------------------------------

    def sequence_of(self, register, row):
        """The sequence field revision_precedence.toml names, or the one the
        row itself carries where that paper names none for the register."""
        field = self.sequence_field.get(register)
        if field is None or field not in row:
            carried = [name for name in row if name.endswith('_seq')]
            if len(carried) != 1:
                raise SystemExit('no sequence field settles ' + register)
            field = carried[0]
        return int(row[field])

    def governing(self, rows, register, key_of):
        """Day filter, then the set aside test, then the highest sequence.
        A register carrying no record state column is filtered on the day
        alone, since no row of it can be set aside."""
        best = {}
        for row in rows:
            if row.get('day_id') != self.day_id:
                continue
            state = row.get('record_state')
            if state is not None and state not in self.applicable:
                continue
            key = key_of(row)
            sequence = self.sequence_of(register, row)
            if key not in best or sequence > best[key][0]:
                best[key] = (sequence, row)
        return {key: row for key, (_, row) in best.items()}

    def day_rows(self, rows):
        return [row for row in rows if row.get('day_id') == self.day_id]

    def unit_factor(self, section, unit):
        entry = self.units[section].get(unit)
        if entry is None:
            return None
        return Fraction(int(entry['numerator']), int(entry['denominator']))


class Context:
    pass


# --------------------------------------------------------------------------
# stage p01, unit normalisation
# --------------------------------------------------------------------------

def stage_p01_unit_normalisation(corpus, ctx):
    reefers = corpus.governing(corpus.reefer_rows, 'reefer_service_register',
                              lambda row: row['reefer_id'])
    plugs = corpus.governing(corpus.plug_rows, 'plug_assignment_register',
                             lambda row: row['plug_id'])
    feeders = corpus.governing(corpus.capacity_rows, 'feeder_capacity_register',
                               lambda row: row['feeder_id'])
    declarations = corpus.governing(corpus.declaration_rows, 'energy_declaration_returns',
                                    lambda row: row['reefer_id'])
    withdrawn = set()
    for row in corpus.day_rows(corpus.withdrawn_rows):
        withdrawn.add((row['vessel_id'], int(row['revision_seq'])))
    call_rows = [row for row in corpus.call_rows
                 if (row['vessel_id'], int(row['revision_seq'])) not in withdrawn]
    calls = corpus.governing(call_rows, 'vessel_call_register',
                             lambda row: row['vessel_id'])

    ctx.calls = calls
    ctx.plug_register = plugs
    ctx.feeder_register = feeders
    ctx.feeder_substation = {fid: row['substation_id'] for fid, row in feeders.items()}
    ctx.feeder_nominal = {fid: int(row['nominal_capacity_w']) for fid, row in feeders.items()}
    ctx.feeder_reserve = {fid: int(row['standing_reserve_w']) for fid, row in feeders.items()}

    ctx.feeders = [fid for fid in corpus.feeders_in_force if fid in feeders]
    ctx.substation_feeders = {}
    for fid in ctx.feeders:
        ctx.substation_feeders.setdefault(ctx.feeder_substation[fid], []).append(fid)

    ctx.reefer_ids = sorted(reefers)
    ctx.reefer = {}
    normalised = []
    for rid in ctx.reefer_ids:
        row = reefers[rid]
        plug_id = row['plug_id']
        plug_row = plugs.get(plug_id)
        feeder_id = plug_row['feeder_id'] if plug_row else None
        substation_id = ctx.feeder_substation.get(feeder_id) if feeder_id else None

        factor = corpus.unit_factor('power', row['nameplate_unit'])
        if factor is None:
            nameplate = 0
            unit_state = 'unknown_unit'
        else:
            nameplate = round_half_up(Fraction(int(row['nameplate_value'])) * factor)
            unit_state = 'converted'

        declared = None
        declaration = declarations.get(rid)
        if declaration is not None:
            quoted = declaration['declared_value'].strip()
            if quoted != corpus.absent and re.fullmatch(r'-?\d+', quoted):
                energy_factor = corpus.unit_factor('energy', declaration['energy_unit'])
                if energy_factor is not None:
                    declared = round_half_up(Fraction(int(quoted)) * energy_factor)

        record = {
            'reefer_id': rid,
            'plug_id': plug_id,
            'feeder_id': feeder_id,
            'substation_id': substation_id,
            'vessel_id': row['vessel_id'],
            'temperature_class': row['temperature_class'],
            'nameplate_w': nameplate,
            'unit_state': unit_state,
            'connect_minute': int(row['connect_minute']),
            'disconnect_minute': int(row['disconnect_minute']),
            'declared_energy_wh': declared,
            'source_system': row['source_system'],
            'plug_zone': plug_row['plug_zone'] if plug_row else None,
            'plug_state': plug_row['plug_state'] if plug_row else None,
        }
        ctx.reefer[rid] = record
        normalised.append({
            'reefer_id': rid,
            'plug_id': plug_id,
            'feeder_id': feeder_id if feeder_id else corpus.absent,
            'substation_id': substation_id if substation_id else corpus.absent,
            'vessel_id': record['vessel_id'],
            'temperature_class': record['temperature_class'],
            'nameplate_w': nameplate,
            'unit_state': unit_state,
            'connect_minute': record['connect_minute'],
            'disconnect_minute': record['disconnect_minute'],
            'declared_energy_wh': declared if declared is not None else 'not_declared',
            'source_system': record['source_system'],
        })
    ctx.normalised_documents = normalised


# --------------------------------------------------------------------------
# stage p02, availability lattice
# --------------------------------------------------------------------------

def stage_p02_availability_lattice(corpus, ctx):
    booked = {'feeder': {}, 'plug': {}, 'crane': {}, 'battery': {}}
    for row in corpus.day_rows(corpus.window_rows):
        if row['window_state'] != 'booked':
            continue
        kind = row['resource_kind']
        if kind not in booked:
            booked[kind] = {}
        span = booked[kind].setdefault(row['resource_id'], set())
        for interval in range(int(row['first_interval']), int(row['last_interval']) + 1):
            span.add(interval)
    ctx.booked_windows = booked

    width = corpus.interval_minutes
    ctx.lattice = {}
    lattice_rows = []
    for rid in ctx.reefer_ids:
        record = ctx.reefer[rid]
        connect = record['connect_minute']
        disconnect = record['disconnect_minute']
        slots = []
        if disconnect > connect:
            for interval in corpus.intervals:
                start = width * interval - width
                end = width * interval
                if connect < end and disconnect > start:
                    slots.append(interval)
        struck = set()
        if record['feeder_id']:
            struck |= booked['feeder'].get(record['feeder_id'], set())
        struck |= booked['plug'].get(record['plug_id'], set())
        slots = [interval for interval in slots if interval not in struck]
        ctx.lattice[rid] = slots
        if not slots:
            state = 'empty'
            first = last = 0
        else:
            state = 'single_slot' if len(slots) == 1 else 'open'
            first, last = slots[0], slots[-1]
        lattice_rows.append([rid, fmt_whole(first), fmt_whole(last),
                             fmt_whole(len(slots)), state])
    ctx.lattice_document = lattice_rows

    demand = {}
    for rid in ctx.reefer_ids:
        record = ctx.reefer[rid]
        feeder_id = record['feeder_id']
        if feeder_id not in corpus.feeders_in_force_set:
            continue
        for interval in ctx.lattice[rid]:
            count, watts = demand.get((interval, feeder_id), (0, 0))
            demand[(interval, feeder_id)] = (count + 1, watts + record['nameplate_w'])
    rows = []
    for interval in corpus.intervals:
        for feeder_id in sorted(ctx.feeders):
            count, watts = demand.get((interval, feeder_id), (0, 0))
            rows.append([fmt_whole(interval), feeder_id, fmt_whole(count), fmt_whole(watts)])
    ctx.interval_demand_document = rows


# --------------------------------------------------------------------------
# stage p03, the mandatory energy floor
# --------------------------------------------------------------------------

def stage_p03_energy_floor(corpus, ctx):
    table = {}
    for entry in corpus.ambient['multiplier_table']:
        table[(entry['temperature_class'], entry['ambient_class'])] = Fraction(
            int(entry['multiplier_numerator']), int(entry['multiplier_denominator']))
    default = corpus.ambient['class_default_multiplier']
    default = Fraction(int(default['multiplier_numerator']),
                       int(default['multiplier_denominator']))

    quarter = Fraction(corpus.interval_minutes, 60)
    ctx.interval_floor = {}
    ctx.draw = {}
    ctx.mandatory = {}
    ctx.requested = {}
    ctx.discretionary = {}
    ctx.floor_state = {}
    rows = []
    for rid in ctx.reefer_ids:
        record = ctx.reefer[rid]
        coefficient = corpus.maintenance_coefficient.get(record['temperature_class'],
                                                         Fraction(1))
        floors = {}
        draws = {}
        for interval in ctx.lattice[rid]:
            multiplier = table.get(
                (record['temperature_class'], corpus.ambient_class[interval]), default)
            base = Fraction(record['nameplate_w']) * multiplier * coefficient
            floors[interval] = round_half_up(base * quarter)
            draws[interval] = round_half_up(base)
        ctx.interval_floor[rid] = floors
        ctx.draw[rid] = draws
        mandatory = sum(floors.values())
        declared = record['declared_energy_wh']
        if declared is not None:
            requested = declared
            state = 'declared'
        else:
            requested = mandatory
            state = 'defaulted'
        discretionary = max(0, requested - mandatory)
        ctx.mandatory[rid] = mandatory
        ctx.requested[rid] = requested
        ctx.discretionary[rid] = discretionary
        ctx.floor_state[rid] = state
        rows.append([rid, fmt_whole(len(ctx.lattice[rid])), fmt_whole(mandatory),
                     fmt_whole(requested), fmt_whole(discretionary), state])
    ctx.energy_floor_document = rows


# --------------------------------------------------------------------------
# stage p04, the admission ladder and the dispatch priority queue
# --------------------------------------------------------------------------

def stage_p04_priority_queue(corpus, ctx):
    zone_kind = corpus.precedence_policy['zone_waiver_notice_kind']
    override_kind = corpus.precedence_policy['override_notice_kind']
    ctx.zone_waivers = set()
    ctx.vessel_critical = set()
    for notice in corpus.notices:
        if notice.get('day_id') != corpus.day_id:
            continue
        if notice.get('kind') == zone_kind:
            ctx.zone_waivers.add(notice['subject_id'])
        elif notice.get('kind') == override_kind:
            ctx.vessel_critical.add(notice['subject_id'])

    admission = corpus.governing(
        corpus.zone_rows, 'plug_zone_admission_matrix',
        lambda row: (row['plug_zone'], row['temperature_class']))

    sentinel = int(corpus.precedence_policy['absent_call_slack_sentinel'])
    cluster_key = corpus.precedence_policy['cluster']['cluster_key']

    ctx.cutoff = {}
    ctx.urgency = {}
    ctx.service_group = {}
    for rid in ctx.reefer_ids:
        call = ctx.calls.get(ctx.reefer[rid]['vessel_id'])
        if call is None:
            ctx.cutoff[rid] = corpus.intervals_per_day
            ctx.urgency[rid] = 9
            ctx.service_group[rid] = 'sg_none'
        else:
            ctx.cutoff[rid] = int(call['cutoff_interval'])
            ctx.urgency[rid] = int(call['urgency_rank'])
            ctx.service_group[rid] = call['service_group']

    def catches(code, rid):
        record = ctx.reefer[rid]
        if code == 'DR_UNKNOWN_PLUG':
            return record['plug_state'] is None or record['plug_state'] != 'live'
        if code == 'DR_FEEDER_OUT_OF_FORCE':
            return record['feeder_id'] not in corpus.feeders_in_force_set
        if code == 'DR_WINDOW_EMPTY':
            return not ctx.lattice[rid]
        if code == 'DR_UNKNOWN_POWER_UNIT':
            return record['unit_state'] == 'unknown_unit'
        if code == 'DR_PLUG_ZONE_REFUSED':
            if rid in ctx.zone_waivers:
                return False
            row = admission.get((record['plug_zone'], record['temperature_class']))
            return row is not None and row['admission'] == 'refused'
        return False

    ctx.refused = {}
    standing = list(ctx.reefer_ids)
    for code in corpus.ladder_order:
        if code == 'DR_DUPLICATE_CONNECTION':
            clusters = {}
            for rid in standing:
                clusters.setdefault(ctx.reefer[rid][cluster_key], []).append(rid)
            caught = set()
            for members in clusters.values():
                for rid in sorted(members)[1:]:
                    caught.add(rid)
            for rid in caught:
                ctx.refused[rid] = code
            standing = [rid for rid in standing if rid not in caught]
            continue
        remaining = []
        for rid in standing:
            if catches(code, rid):
                ctx.refused[rid] = code
            else:
                remaining.append(rid)
        standing = remaining

    ctx.deadline_slack = {}
    for rid in standing:
        call = ctx.calls.get(ctx.reefer[rid]['vessel_id'])
        if call is None:
            ctx.deadline_slack[rid] = sentinel
        else:
            ctx.deadline_slack[rid] = ctx.cutoff[rid] - ctx.lattice[rid][-1]

    key_value = {
        'deadline_slack': lambda rid: ctx.deadline_slack[rid],
        'class_rank': lambda rid: corpus.class_rank[ctx.reefer[rid]['temperature_class']],
        'urgency_rank': lambda rid: ctx.urgency[rid],
        'reefer_id': lambda rid: rid,
    }
    ordering = [key_value[name] for name in corpus.ordering_keys]
    ctx.queue = sorted(standing, key=lambda rid: tuple(get(rid) for get in ordering))
    ctx.rank = {rid: index + 1 for index, rid in enumerate(ctx.queue)}
    ctx.queued_set = set(ctx.queue)

    rows = []
    for rid in ctx.queue:
        rows.append([fmt_whole(ctx.rank[rid]), rid, fmt_whole(ctx.deadline_slack[rid]),
                     fmt_whole(corpus.class_rank[ctx.reefer[rid]['temperature_class']]),
                     fmt_whole(ctx.urgency[rid]), 'queued'])
    for rid in sorted(ctx.refused):
        rows.append(['0', rid, '0', '0', '0', ctx.refused[rid]])
    ctx.queue_document = rows


# --------------------------------------------------------------------------
# stage p05, the provisional allocation
# --------------------------------------------------------------------------

def stage_p05_provisional_allocation(corpus, ctx):
    derating = {}
    best = {}
    for row in corpus.day_rows(corpus.derating_rows):
        if row['record_state'] not in corpus.applicable:
            continue
        sequence = int(row['notice_seq'])
        key = row['feeder_id']
        if key not in best or sequence > best[key][0]:
            best[key] = (sequence, row)
    for feeder_id, (_, row) in best.items():
        derating[feeder_id] = (int(row['first_interval']), int(row['last_interval']),
                               int(row['derate_permille']))

    ctx.nominal = {}
    for feeder_id in ctx.feeders:
        booked = ctx.booked_windows['feeder'].get(feeder_id, set())
        notice = derating.get(feeder_id)
        for interval in corpus.intervals:
            capacity = 0 if interval in booked else ctx.feeder_nominal[feeder_id]
            if notice and notice[0] <= interval <= notice[1]:
                capacity = floor_div(Fraction(capacity * notice[2], 1000))
            ctx.nominal[(feeder_id, interval)] = capacity

    ctx.powered = {rid: set() for rid in ctx.queue}
    load = {(feeder_id, interval): 0
            for feeder_id in ctx.feeders for interval in corpus.intervals}
    rows = []
    provisional_state = {}
    for interval in corpus.intervals:
        for rid in ctx.queue:
            if interval not in ctx.lattice[rid]:
                continue
            feeder_id = ctx.reefer[rid]['feeder_id']
            draw = ctx.draw[rid][interval]
            key = (feeder_id, interval)
            if load[key] + draw <= ctx.nominal[key]:
                load[key] += draw
                ctx.powered[rid].add(interval)
                provisional_state[(rid, interval)] = 'powered'
            else:
                provisional_state[(rid, interval)] = 'held'
    for interval in corpus.intervals:
        entries = []
        for rid in ctx.queue:
            if interval in ctx.lattice[rid]:
                entries.append((ctx.reefer[rid]['feeder_id'], rid))
        for feeder_id, rid in sorted(entries):
            rows.append([fmt_whole(interval), feeder_id, rid,
                         fmt_whole(ctx.draw[rid][interval]),
                         provisional_state[(rid, interval)]])
    ctx.provisional_document = rows
    ctx.provisional_load = dict(load)
    ctx.load = load


# --------------------------------------------------------------------------
# stage p06, the feeder reconciliation and the spill
# --------------------------------------------------------------------------

def stage_p06_feeder_reconciliation(corpus, ctx):
    ctx.reserved = {}
    for feeder_id in ctx.feeders:
        reserve = ctx.feeder_reserve[feeder_id]
        for interval in corpus.intervals:
            nominal = ctx.nominal[(feeder_id, interval)]
            ctx.reserved[(feeder_id, interval)] = max(0, nominal - reserve)

    violations = {}
    spills = []
    load = ctx.load
    for interval in corpus.intervals:
        for feeder_id in sorted(ctx.feeders):
            key = (feeder_id, interval)
            reserved = ctx.reserved[key]
            if load[key] <= reserved:
                continue
            standing_load = load[key]
            removed = 0
            while load[key] > reserved:
                members = [rid for rid in ctx.queue
                           if ctx.reefer[rid]['feeder_id'] == feeder_id
                           and interval in ctx.powered[rid]]
                if not members:
                    break
                victim = max(members, key=lambda rid: ctx.rank[rid])
                draw = ctx.draw[victim][interval]
                ctx.powered[victim].discard(interval)
                load[key] -= draw
                removed += 1
                target = 0
                for candidate in ctx.lattice[victim]:
                    if candidate <= interval or candidate in ctx.powered[victim]:
                        continue
                    other = (feeder_id, candidate)
                    moving = ctx.draw[victim][candidate]
                    if load[other] + moving <= ctx.reserved[other]:
                        target = candidate
                        break
                if target:
                    ctx.powered[victim].add(target)
                    load[(feeder_id, target)] += ctx.draw[victim][target]
                    spills.append([victim, interval, target, feeder_id, draw, 'spilled'])
                else:
                    spills.append([victim, interval, 0, feeder_id, draw, 'unspilled'])
            violations[key] = (standing_load, reserved, standing_load - reserved, removed)

    ctx.reconciled_load = dict(load)
    ctx.spill_rows = spills
    ctx.spill_count = len(spills)
    ctx.unspilled_count = sum(1 for row in spills if row[5] == 'unspilled')

    rows = []
    for interval in corpus.intervals:
        for feeder_id in sorted(ctx.feeders):
            key = (feeder_id, interval)
            if key not in violations:
                continue
            standing_load, reserved, excess, removed = violations[key]
            rows.append([fmt_whole(interval), feeder_id, fmt_whole(standing_load),
                         fmt_whole(reserved), fmt_whole(excess), fmt_whole(removed)])
    ctx.violation_document = rows

    ledger = []
    for interval in corpus.intervals:
        for feeder_id in sorted(ctx.feeders):
            key = (feeder_id, interval)
            reserved = ctx.reserved[key]
            current = ctx.reconciled_load[key]
            if current > reserved:
                state = 'over_capacity'
            elif current == reserved:
                state = 'at_capacity'
            else:
                state = 'clear'
            ledger.append([fmt_whole(interval), feeder_id,
                           fmt_whole(ctx.nominal[key]),
                           fmt_whole(ctx.feeder_reserve[feeder_id]),
                           fmt_whole(reserved), fmt_whole(current),
                           fmt_whole(max(0, reserved - current)), state])
    ctx.feeder_load_document = ledger

    spill_sorted = sorted(ctx.spill_rows, key=lambda row: (row[1], row[3], row[0]))
    ctx.spill_document = [[row[0], fmt_whole(row[1]), fmt_whole(row[2]), row[3],
                           fmt_whole(row[4]), row[5]] for row in spill_sorted]


# --------------------------------------------------------------------------
# stage p07, the crane adjusted capacity
# --------------------------------------------------------------------------

def stage_p07_crane_interaction(corpus, ctx):
    lowest = {}
    for row in corpus.confirm_rows:
        if row.get('day_id') != corpus.day_id:
            continue
        key = (row['crane_id'], int(row['interval']))
        sequence = int(row['confirm_seq'])
        if key not in lowest or sequence < lowest[key][0]:
            lowest[key] = (sequence, row['confirmation_state'])

    factor = corpus.unit_factor('demand', 'kw')
    crane_draw = {}
    for row in corpus.duty_rows:
        if row.get('day_id') != corpus.day_id:
            continue
        crane_id = row['crane_id']
        interval = int(row['interval'])
        confirmation = lowest.get((crane_id, interval))
        if confirmation is None or confirmation[1] != 'landed':
            continue
        if interval in ctx.booked_windows['crane'].get(crane_id, set()):
            continue
        feeder_id = row['feeder_id']
        watts = round_half_up(Fraction(int(row['demand_kw'])) * factor)
        crane_draw[(feeder_id, interval)] = crane_draw.get((feeder_id, interval), 0) + watts
    ctx.crane_draw = crane_draw

    ctx.adjusted = {}
    rows = []
    for interval in corpus.intervals:
        for feeder_id in sorted(ctx.feeders):
            key = (feeder_id, interval)
            reserved = ctx.reserved[key]
            draw = crane_draw.get(key, 0)
            difference = reserved - draw
            if difference < 0:
                adjusted, state = 0, 'clamped'
            else:
                adjusted, state = difference, 'clear'
            ctx.adjusted[key] = adjusted
            rows.append([fmt_whole(interval), feeder_id, fmt_whole(reserved),
                         fmt_whole(draw), fmt_whole(adjusted), state])
    ctx.crane_document = rows


# --------------------------------------------------------------------------
# stage p08, the battery intervention
# --------------------------------------------------------------------------

def stage_p08_battery_intervention(corpus, ctx):
    policy = corpus.battery_policy
    battery_id = policy['battery_id']
    substation_id = policy['substation_id']
    capacity = int(policy['capacity_wh'])
    reserve = int(policy['reserve_wh'])
    soc = int(policy['initial_state_of_charge_wh'])
    max_charge = int(policy['max_charge_w'])
    max_discharge = int(policy['max_discharge_w'])
    charge_efficiency = int(policy['charge_efficiency_permille'])
    discharge_efficiency = int(policy['discharge_efficiency_permille'])
    eligible = set(policy['charge_eligible_bands'])

    telemetry = {}
    best = {}
    for row in corpus.day_rows(corpus.telemetry_rows):
        interval = int(row['interval'])
        sequence = int(row['telemetry_seq'])
        if interval not in best or sequence > best[interval][0]:
            best[interval] = (sequence, row['availability_state'])
    for interval, (_, state) in best.items():
        telemetry[interval] = state

    feeders = ctx.substation_feeders.get(substation_id, [])
    ceiling = corpus.substation_ceiling.get(substation_id,
                                            corpus.substation_ceiling_topology.get(substation_id, 0))

    ctx.battery_support = {}
    ctx.battery_cycle = 0
    schedule_rows = []
    soc_rows = []
    ctx.soc_below_reserve = 0
    for interval in corpus.intervals:
        opening = soc
        deficit_watts = 0
        feeder_deficit = {}
        for feeder_id in sorted(feeders):
            key = (feeder_id, interval)
            gap = ctx.reconciled_load[key] - ctx.adjusted[key]
            if gap > 0:
                feeder_deficit[feeder_id] = gap
                deficit_watts += gap
        deficit_wh = floor_div(Fraction(deficit_watts, 4))

        available = (telemetry.get(interval) == 'online'
                     and interval not in ctx.booked_windows['battery'].get(battery_id, set()))
        discharge = 0
        charge = 0
        if not available:
            action = 'offline'
            reason = 'none'
        elif deficit_wh > 0 or deficit_watts > 0:
            action = 'discharging'
            rate_limit = floor_div(Fraction(max_discharge, 4))
            soc_limit = floor_div(Fraction((soc - reserve) * discharge_efficiency, 1000))
            soc_limit = max(0, soc_limit)
            discharge = min(deficit_wh, rate_limit, soc_limit)
            if discharge < 0:
                discharge = 0
            if discharge == 0:
                reason = 'state_of_charge_on_reserve'
            elif discharge == rate_limit:
                reason = 'discharge_limit'
            elif discharge == soc_limit:
                reason = 'state_of_charge_limit'
            else:
                reason = 'deficit_met'
            soc -= ceil_div(Fraction(discharge * 1000, discharge_efficiency))
        elif corpus.tariff_band[interval] in eligible:
            action = 'charging'
            rate_limit = floor_div(Fraction(max_charge, 4))
            substation_load = sum(ctx.reconciled_load[(f, interval)] for f in feeders)
            headroom_limit = floor_div(Fraction(max(0, ceiling - substation_load), 4))
            room = max(0, capacity - soc)
            charge = min(rate_limit, headroom_limit, room)
            if charge == 0:
                reason = 'no_room'
            elif charge == room:
                reason = 'capacity_limit'
            elif charge == rate_limit:
                reason = 'charge_limit'
            else:
                reason = 'headroom_limit'
            soc += floor_div(Fraction(charge * charge_efficiency, 1000))
        else:
            action = 'idle'
            reason = 'band_ineligible'

        remaining = 4 * discharge
        for feeder_id in sorted(feeders):
            need = feeder_deficit.get(feeder_id, 0)
            if need <= 0 or remaining <= 0:
                continue
            taken = min(remaining, need)
            ctx.battery_support[(feeder_id, interval)] = taken
            remaining -= taken

        ctx.battery_cycle += discharge + charge
        if soc == reserve:
            soc_state = 'at_reserve'
        elif soc < reserve:
            soc_state = 'below_reserve'
            ctx.soc_below_reserve += 1
        else:
            soc_state = 'above_reserve'

        schedule_rows.append([fmt_whole(interval), action, fmt_whole(deficit_wh),
                              fmt_whole(discharge), fmt_whole(charge), reason])
        soc_rows.append([fmt_whole(interval), fmt_whole(opening), fmt_whole(soc),
                         fmt_whole(reserve), soc_state])

    ctx.battery_document = schedule_rows
    ctx.soc_document = soc_rows
    ctx.battery_reserve = reserve


def support_of(ctx, feeder_id, interval):
    return ctx.battery_support.get((feeder_id, interval), 0)


# --------------------------------------------------------------------------
# stage p09, the load reconciliation passes
# --------------------------------------------------------------------------

def stage_p09_load_reconciliation(corpus, ctx):
    ctx.headroom = {}
    day_pool = {}
    for feeder_id in ctx.feeders:
        total = 0
        for interval in corpus.intervals:
            key = (feeder_id, interval)
            room = ctx.adjusted[key] + support_of(ctx, feeder_id, interval) \
                - ctx.reconciled_load[key]
            room = max(0, room)
            ctx.headroom[key] = room
            total += room
        day_pool[feeder_id] = floor_div(Fraction(total, 4))
    ctx.day_pool = day_pool

    members = {}
    for rid in ctx.queue:
        if ctx.discretionary[rid] > 0:
            members.setdefault(ctx.reefer[rid]['feeder_id'], []).append(rid)
    for feeder_id in members:
        members[feeder_id].sort()
    ctx.members = members

    limit = {}
    for feeder_id, group in members.items():
        for rid in group:
            ceiling = corpus.vessel_ceiling.get(ctx.reefer[rid]['vessel_id'])
            if ceiling is None:
                limit[rid] = ctx.discretionary[rid]
            else:
                limit[rid] = min(ctx.discretionary[rid], ceiling)
    ctx.share_limit = limit

    share = {rid: 0 for group in members.values() for rid in group}
    rows = []
    ctx.last_moving_pass = 0
    for index in range(1, corpus.pass_budget + 1):
        opening = dict(share)
        need = {}
        target = {}
        for feeder_id, group in members.items():
            pool = Fraction(day_pool[feeder_id] - sum(opening[rid] for rid in group))
            total_need = 0
            for rid in group:
                value = max(0, ctx.discretionary[rid] - opening[rid])
                need[rid] = value
                total_need += value
            for rid in group:
                if pool > 0 and total_need > 0:
                    target[rid] = Fraction(opening[rid]) \
                        + pool * Fraction(need[rid], total_need)
                else:
                    target[rid] = Fraction(opening[rid])

        freed = {}
        cell_of = {}
        for feeder_id, group in members.items():
            substation_id = ctx.feeder_substation[feeder_id]
            for rid in group:
                cell = (substation_id, ctx.service_group[rid])
                cell_of[rid] = cell
                if target[rid] > limit[rid]:
                    freed[cell] = freed.get(cell, Fraction(0)) \
                        + (target[rid] - Fraction(limit[rid]))
                    target[rid] = Fraction(limit[rid])

        for cell, amount in freed.items():
            if amount <= 0:
                continue
            receivers = [rid for rid in cell_of
                         if cell_of[rid] == cell and target[rid] < limit[rid]]
            total_room = sum(Fraction(limit[rid]) - target[rid] for rid in receivers)
            if not receivers or total_room <= 0:
                continue
            for rid in receivers:
                room = Fraction(limit[rid]) - target[rid]
                target[rid] = target[rid] + amount * room / total_room
                if target[rid] > limit[rid]:
                    target[rid] = Fraction(limit[rid])

        for feeder_id, group in members.items():
            for rid in group:
                move = corpus.damping * (target[rid] - Fraction(opening[rid]))
                if move != 0 and abs(move) < corpus.minimum_step:
                    move = Fraction(corpus.minimum_step) * (1 if move > 0 else -1)
                closing = round_half_up(Fraction(opening[rid]) + move)
                closing = max(0, min(closing, limit[rid]))
                share[rid] = closing

        for feeder_id in sorted(members):
            for rid in members[feeder_id]:
                state = 'moving' if share[rid] != opening[rid] else 'settled'
                if state == 'moving':
                    ctx.last_moving_pass = index
                rows.append([fmt_whole(index), feeder_id, rid, fmt_whole(opening[rid]),
                             fmt_whole(need[rid]), fmt_whole(round_half_up(target[rid])),
                             fmt_whole(share[rid]), state])
    ctx.iteration_document = rows
    ctx.share = share
    ctx.passes_run = corpus.pass_budget

    allowance_room = {}
    for feeder_id in ctx.feeders:
        for interval in corpus.intervals:
            key = (feeder_id, interval)
            allowance_room[key] = floor_div(Fraction(ctx.headroom[key], 4))
    ctx.allowance = {}
    ctx.unplaced = {}
    for rid in ctx.queue:
        remaining = share.get(rid, 0)
        feeder_id = ctx.reefer[rid]['feeder_id']
        for interval in ctx.lattice[rid]:
            if remaining <= 0:
                break
            key = (feeder_id, interval)
            taken = min(remaining, allowance_room[key])
            if taken > 0:
                ctx.allowance[(rid, interval)] = taken
                allowance_room[key] -= taken
                remaining -= taken
        ctx.unplaced[rid] = remaining

    ctx.final_load = {}
    for feeder_id in ctx.feeders:
        for interval in corpus.intervals:
            key = (feeder_id, interval)
            placed = 0
            for rid in ctx.queue:
                if ctx.reefer[rid]['feeder_id'] == feeder_id:
                    placed += ctx.allowance.get((rid, interval), 0)
            ctx.final_load[key] = ctx.reconciled_load[key] + 4 * placed


# --------------------------------------------------------------------------
# stage p10, the tariff and the demand charge
# --------------------------------------------------------------------------

def stage_p10_tariff_and_demand(corpus, ctx):
    tariff = corpus.governing(corpus.tariff_rows, 'tariff_interval_schedule',
                              lambda row: int(row['interval']))
    bands = corpus.governing(corpus.band_rows, 'demand_charge_bands',
                             lambda row: (row['substation_id'], row['band_code']))

    rows = []
    ctx.interval_charge = {}
    ctx.interval_energy = {}
    ctx.yard_load = {}
    for interval in corpus.intervals:
        row = tariff[interval]
        price = int(row['price_tenth_cents_per_kwh'])
        load = sum(ctx.final_load[(feeder_id, interval)] for feeder_id in ctx.feeders)
        energy = round_half_up(Fraction(load, 4))
        charge = round_half_up(Fraction(energy * price, 10000))
        ctx.yard_load[interval] = load
        ctx.interval_energy[interval] = energy
        ctx.interval_charge[interval] = charge
        rows.append([fmt_whole(interval), row['tariff_band'], fmt_whole(price),
                     fmt_whole(load), fmt_whole(energy), fmt_whole(charge)])
    ctx.tariff_document = rows
    ctx.energy_charge_total = sum(ctx.interval_charge.values())

    ctx.substation_peak = {}
    ctx.substation_band = {}
    ctx.substation_charge = {}
    for substation_id in corpus.substation_order:
        feeders = ctx.substation_feeders.get(substation_id, [])
        peak, peak_interval = -1, 0
        for interval in corpus.intervals:
            load = sum(ctx.final_load[(feeder_id, interval)] for feeder_id in feeders)
            if load > peak:
                peak, peak_interval = load, interval
        if peak < 0:
            peak, peak_interval = 0, 1
        ctx.substation_peak[substation_id] = (peak, peak_interval)
        code, charge = corpus.absent, 0
        for (sid, band_code), row in bands.items():
            if sid != substation_id:
                continue
            if int(row['floor_w']) <= peak < int(row['ceiling_w']):
                code, charge = band_code, int(row['charge_cents'])
                break
        ctx.substation_band[substation_id] = code
        ctx.substation_charge[substation_id] = charge
    ctx.demand_charge = sum(ctx.substation_charge.values())

    peak, peak_interval = -1, 0
    for interval in corpus.intervals:
        if ctx.yard_load[interval] > peak:
            peak, peak_interval = ctx.yard_load[interval], interval
    ctx.yard_peak = max(0, peak)
    ctx.yard_peak_interval = peak_interval


# --------------------------------------------------------------------------
# stage p11, the deadline correction
# --------------------------------------------------------------------------

def required_energy(ctx, rid):
    cutoff = ctx.cutoff[rid]
    return sum(value for interval, value in ctx.interval_floor[rid].items()
               if interval <= cutoff)


def served_energy(ctx, rid):
    cutoff = ctx.cutoff[rid]
    return sum(value for interval, value in ctx.interval_floor[rid].items()
               if interval <= cutoff and interval in ctx.powered[rid])


def shortfall_intervals(ctx, rid):
    cutoff = ctx.cutoff[rid]
    return [interval for interval in ctx.lattice[rid]
            if interval <= cutoff and interval not in ctx.powered[rid]]


def powered_below_cutoff(ctx, rid):
    cutoff = ctx.cutoff[rid]
    return sum(1 for interval in ctx.powered[rid] if interval <= cutoff)


def stage_p11_deadline_correction(corpus, ctx):
    ctx.correction_rows = []
    ctx.applied = []
    ctx.frozen = set()
    ctx.sweep_cycles = []
    ctx.base_load = {key: value for key, value in ctx.reconciled_load.items()}
    ctx.sweep_budget = corpus.protection_depth + 2

    def signature():
        pairs = []
        for rid in sorted(ctx.powered):
            for interval in sorted(ctx.powered[rid]):
                pairs.append('%s@%d' % (rid, interval))
        return hashlib.sha256(';'.join(pairs).encode('utf-8')).hexdigest()

    ctx.state_signatures = [signature()]
    ctx.sweeps_run = 0
    ctx.closing_state = 'budget_spent'
    ctx.settled_at_sweep = 0

    for sweep in range(1, ctx.sweep_budget + 1):
        ctx.sweeps_run = sweep
        applied_here = 0
        short = [rid for rid in ctx.queue
                 if required_energy(ctx, rid) - served_energy(ctx, rid) > 0]
        critical = [rid for rid in short if rid in ctx.vessel_critical]
        ordinary = [rid for rid in short if rid not in ctx.vessel_critical]
        critical.sort(key=lambda rid: ctx.rank[rid])
        ordinary.sort(key=lambda rid: ctx.rank[rid])

        for rid in critical + ordinary:
            if rid in ctx.frozen:
                continue
            if required_energy(ctx, rid) - served_energy(ctx, rid) <= 0:
                continue
            feeder_id = ctx.reefer[rid]['feeder_id']
            for interval in shortfall_intervals(ctx, rid):
                key = (feeder_id, interval)
                candidates = []
                for other in ctx.queue:
                    if other == rid or other in ctx.frozen:
                        continue
                    if other in ctx.vessel_critical:
                        continue
                    if ctx.reefer[other]['feeder_id'] != feeder_id:
                        continue
                    if interval not in ctx.powered[other]:
                        continue
                    if powered_below_cutoff(ctx, other) <= corpus.protection_depth:
                        continue
                    candidates.append(other)
                if not candidates:
                    ctx.correction_rows.append(
                        [rid, interval, corpus.absent, feeder_id, 'refused_protected'])
                    continue
                victim = max(candidates, key=lambda other: ctx.rank[other])
                raised = ctx.base_load[key] - ctx.draw[victim][interval] \
                    + ctx.draw[rid][interval]
                admitted = raised <= ctx.base_load[key] or raised <= (
                    ctx.adjusted[key] + support_of(ctx, feeder_id, interval))
                if not admitted:
                    ctx.correction_rows.append(
                        [rid, interval, victim, feeder_id, 'refused_no_headroom'])
                    continue
                ctx.powered[victim].discard(interval)
                ctx.powered[rid].add(interval)
                ctx.base_load[key] = raised
                ctx.correction_rows.append(
                    [rid, interval, victim, feeder_id, 'corrected'])
                ctx.applied.append((sweep, rid, victim, interval))
                applied_here += 1
                break

        cycles = []
        earlier = set((short_id, victim_id, interval)
                      for sweep_index, short_id, victim_id, interval in ctx.applied
                      if sweep_index < sweep)
        for sweep_index, short_id, victim_id, interval in ctx.applied:
            if sweep_index != sweep:
                continue
            if (victim_id, short_id, interval) in earlier:
                cycles.append((short_id, victim_id, interval))
        cycles.sort()
        if cycles:
            def penalty(entry):
                short_id, victim_id, interval = entry
                return (ctx.draw[victim_id].get(interval, 0), interval, victim_id, short_id)
            broken = min(cycles, key=penalty)
            for entry in cycles:
                ctx.sweep_cycles.append({
                    'sweep': sweep,
                    'short_reefer': entry[0],
                    'displaced_reefer': entry[1],
                    'interval': entry[2],
                    'broken': entry == broken,
                })
            ctx.frozen.add(broken[0])
            ctx.frozen.add(broken[1])

        ctx.state_signatures.append(signature())
        if applied_here == 0:
            ctx.closing_state = 'settled'
            ctx.settled_at_sweep = sweep
            break

    ctx.correction_rows.sort(key=lambda row: (row[1], row[3], row[0]))
    ctx.correction_document = [[row[0], fmt_whole(row[1]), row[2], row[3], row[4]]
                               for row in ctx.correction_rows]
    ctx.correction_count = len(ctx.applied)


# --------------------------------------------------------------------------
# stage p12, the cycle detection and the break
# --------------------------------------------------------------------------

def stage_p12_cycle_break(corpus, ctx):
    ctx.cycle_report = {
        'day_id': corpus.day_id,
        'sweeps_run': ctx.sweeps_run,
        'sweep_budget': ctx.sweep_budget,
        'closing_state': ctx.closing_state,
        'settled_at_sweep': ctx.settled_at_sweep if ctx.closing_state == 'settled' else 0,
        'correction_count': ctx.correction_count,
        'cycle_count': len(ctx.sweep_cycles),
        'cycles': ctx.sweep_cycles,
        'frozen_reefers': sorted(ctx.frozen),
        'state_signatures': [value[:16] for value in ctx.state_signatures],
    }


# --------------------------------------------------------------------------
# stage p13, the objective reconciliation
# --------------------------------------------------------------------------

def stage_p13_objective(corpus, ctx):
    ctx.post_load = {}
    for feeder_id in ctx.feeders:
        for interval in corpus.intervals:
            key = (feeder_id, interval)
            placed = 0
            for rid in ctx.queue:
                if ctx.reefer[rid]['feeder_id'] == feeder_id:
                    placed += ctx.allowance.get((rid, interval), 0)
            ctx.post_load[key] = ctx.base_load[key] + 4 * placed

    over = 0
    for feeder_id in ctx.feeders:
        for interval in corpus.intervals:
            key = (feeder_id, interval)
            limit = ctx.adjusted[key] + support_of(ctx, feeder_id, interval)
            if ctx.post_load[key] > limit:
                over += 1
    ctx.over_capacity_count = over
    ctx.hard_violations = over + ctx.soc_below_reserve

    ctx.required = {}
    ctx.served = {}
    ctx.shortfall = {}
    ctx.shortfall_count = {}
    ctx.surcharge = {}
    for rid in ctx.queue:
        required = required_energy(ctx, rid)
        served = served_energy(ctx, rid)
        ctx.required[rid] = required
        ctx.served[rid] = served
        ctx.shortfall[rid] = max(0, required - served)
        ctx.shortfall_count[rid] = len(shortfall_intervals(ctx, rid))
        charge = 0
        for intervals_short, surcharge in corpus.surcharge_ladder:
            if intervals_short <= ctx.shortfall_count[rid]:
                charge = surcharge
        ctx.surcharge[rid] = charge if ctx.shortfall[rid] > 0 else 0

    ctx.unmet_mandatory = sum(ctx.shortfall[rid] for rid in ctx.queue)
    ctx.deadline_penalty = sum(ctx.surcharge[rid] for rid in ctx.queue
                               if ctx.shortfall[rid] > 0)
    ctx.energy_cost = ctx.energy_charge_total + ctx.demand_charge \
        + corpus.base_service_charge

    powered_anywhere = sorted(rid for rid in ctx.queue if ctx.powered[rid])
    ctx.tie_key = hashlib.sha256(';'.join(powered_anywhere).encode('utf-8')).hexdigest()[:16]

    ctx.objective = {
        'day_id': corpus.day_id,
        'lexicographic_order': ['hard_violations', 'unmet_mandatory_wh',
                                'deadline_penalty_cents', 'peak_demand_w',
                                'energy_cost_cents', 'battery_cycle_wh', 'tie_key'],
        'hard_violations': ctx.hard_violations,
        'unmet_mandatory_wh': ctx.unmet_mandatory,
        'deadline_penalty_cents': ctx.deadline_penalty,
        'peak_demand_w': ctx.yard_peak,
        'energy_cost_cents': ctx.energy_cost,
        'battery_cycle_wh': ctx.battery_cycle,
        'tie_key': ctx.tie_key,
    }

    at_ceiling = 0
    for rid in ctx.queue:
        value = ctx.share.get(rid, 0)
        if value > 0 and value == ctx.share_limit.get(rid):
            at_ceiling += 1
    ctx.at_ceiling = at_ceiling
    ctx.unplaced_total = sum(ctx.unplaced.get(rid, 0) for rid in ctx.queue)

    ctx.certificate = {
        'day_id': corpus.day_id,
        'feeder_intervals_over_capacity': ctx.over_capacity_count,
        'state_of_charge_below_reserve': ctx.soc_below_reserve,
        'reefers_at_share_ceiling': at_ceiling,
        'unplaced_allowance_wh': ctx.unplaced_total,
        'reefers_refused': len(ctx.refused),
        'reefers_queued': len(ctx.queue),
        'spill_count': ctx.spill_count,
        'unspilled_count': ctx.unspilled_count,
    }


# --------------------------------------------------------------------------
# stage p14, the publication
# --------------------------------------------------------------------------

def stage_p14_publication(corpus, ctx, publication):
    absent = corpus.absent
    words = corpus.state_words

    publication.line_objects('normalised_reefers.jsonl', ctx.normalised_documents)
    publication.delimited('availability_lattice.csv',
                          ['reefer_id', 'first_interval', 'last_interval',
                           'slot_count', 'window_state'],
                          ctx.lattice_document, ',')
    publication.delimited('energy_floor_ledger.csv',
                          ['reefer_id', 'slot_count', 'mandatory_wh', 'requested_wh',
                           'discretionary_wh', 'floor_state'],
                          ctx.energy_floor_document, ',')
    publication.delimited('dispatch_priority_queue.csv',
                          ['rank', 'reefer_id', 'deadline_slack', 'class_rank',
                           'urgency_rank', 'queue_state'],
                          ctx.queue_document, ',')
    publication.delimited('provisional_allocation.psv',
                          ['interval', 'feeder_id', 'reefer_id', 'draw_w',
                           'allocation_state'],
                          ctx.provisional_document, '|')
    publication.delimited('feeder_violation_ledger.csv',
                          ['interval', 'feeder_id', 'provisional_load_w',
                           'reserved_capacity_w', 'excess_w', 'removed_count'],
                          ctx.violation_document, ',')
    publication.delimited('crane_adjusted_capacity.csv',
                          ['interval', 'feeder_id', 'reserved_capacity_w',
                           'crane_draw_w', 'adjusted_capacity_w', 'clamp_state'],
                          ctx.crane_document, ',')
    publication.delimited('battery_schedule.csv',
                          ['interval', 'action', 'deficit_wh', 'discharge_wh',
                           'charge_wh', 'limit_reason'],
                          ctx.battery_document, ',')
    publication.delimited('reconciliation_iterations.csv',
                          ['pass', 'feeder_id', 'reefer_id', 'opening_share_wh',
                           'need_wh', 'target_wh', 'closing_share_wh', 'pass_state'],
                          ctx.iteration_document, ',')
    publication.delimited('tariff_charge_ledger.csv',
                          ['interval', 'tariff_band', 'price_tenth_cents_per_kwh',
                           'load_w', 'energy_wh', 'charge_cents'],
                          ctx.tariff_document, ',')
    publication.delimited('deadline_correction.csv',
                          ['reefer_id', 'interval', 'displaced_reefer_id',
                           'feeder_id', 'correction_state'],
                          ctx.correction_document, ',')
    publication.object_document('cycle_break_report.json', ctx.cycle_report)
    publication.object_document('objective_vector.json', ctx.objective)

    schedule_rows = []
    for interval in corpus.intervals:
        entries = []
        for rid in ctx.queue:
            if interval in ctx.lattice[rid]:
                entries.append((ctx.reefer[rid]['feeder_id'], rid))
        for feeder_id, rid in sorted(entries):
            base = ctx.draw[rid][interval] if interval in ctx.powered[rid] else 0
            allowance = ctx.allowance.get((rid, interval), 0)
            if base > 0 and allowance > 0:
                state = 'powered_with_allowance'
            elif base > 0:
                state = words['powered']
            elif allowance > 0:
                state = 'allowance_only'
            else:
                state = words['held']
            energy = round_half_up(Fraction(base, 4)) + allowance
            schedule_rows.append([fmt_whole(interval), feeder_id, rid, fmt_whole(base),
                                  fmt_whole(allowance), fmt_whole(energy), state])
    publication.delimited('final_schedule.csv',
                          ['interval', 'feeder_id', 'reefer_id', 'base_draw_w',
                           'allowance_wh', 'energy_wh', 'schedule_state'],
                          schedule_rows, ',')

    publication.delimited('interval_demand.csv',
                          ['interval', 'feeder_id', 'connected_count',
                           'nominal_demand_w'],
                          ctx.interval_demand_document, ',')
    publication.delimited('feeder_load_ledger.csv',
                          ['interval', 'feeder_id', 'capacity_w', 'reserve_w',
                           'reserved_capacity_w', 'load_w', 'headroom_w', 'load_state'],
                          ctx.feeder_load_document, ',')
    publication.delimited('spill_decisions.tsv',
                          ['reefer_id', 'from_interval', 'to_interval', 'feeder_id',
                           'draw_w', 'spill_state'],
                          ctx.spill_document, '\t')
    publication.delimited('soc_ledger.psv',
                          ['interval', 'opening_soc_wh', 'closing_soc_wh',
                           'reserve_wh', 'soc_state'],
                          ctx.soc_document, '|')
    publication.object_document('constraint_certificate.json', ctx.certificate)

    substations = []
    for substation_id in corpus.substation_order:
        peak, interval = ctx.substation_peak[substation_id]
        substations.append({
            'substation_id': substation_id,
            'peak_w': peak,
            'peak_interval': interval,
            'band_code': ctx.substation_band[substation_id],
            'charge_cents': ctx.substation_charge[substation_id],
        })
    publication.object_document('peak_demand_certificate.json', {
        'day_id': corpus.day_id,
        'yard_peak_w': ctx.yard_peak,
        'yard_peak_interval': ctx.yard_peak_interval,
        'substations': substations,
        'demand_charge_cents': ctx.demand_charge,
    })

    unmet_rows = []
    certificate_rows = []
    for rid in sorted(ctx.queue):
        record = ctx.reefer[rid]
        allowance = sum(value for (holder, _), value in ctx.allowance.items()
                        if holder == rid)
        unplaced = ctx.unplaced.get(rid, 0)
        if ctx.shortfall[rid] > 0 or unplaced > 0:
            unmet_rows.append([rid, record['feeder_id'], record['vessel_id'],
                               fmt_whole(ctx.shortfall[rid]),
                               fmt_whole(ctx.shortfall_count[rid]),
                               fmt_whole(unplaced), fmt_whole(ctx.surcharge[rid])])
        certificate_rows.append([
            rid, record['feeder_id'], record['vessel_id'],
            fmt_whole(ctx.required[rid]), fmt_whole(ctx.served[rid]),
            fmt_whole(ctx.shortfall[rid]), fmt_whole(ctx.shortfall_count[rid]),
            fmt_whole(allowance), fmt_whole(unplaced), fmt_whole(ctx.surcharge[rid]),
            words['met'] if ctx.shortfall[rid] == 0 else words['unmet']])
    publication.delimited('unmet_requirement_report.tsv',
                          ['reefer_id', 'feeder_id', 'vessel_id', 'shortfall_wh',
                           'shortfall_intervals', 'unplaced_allowance_wh',
                           'surcharge_cents'],
                          unmet_rows, '\t')
    publication.delimited('reefer_service_certificate.csv',
                          ['reefer_id', 'feeder_id', 'vessel_id', 'required_wh',
                           'served_wh', 'shortfall_wh', 'shortfall_intervals',
                           'allowance_wh', 'unplaced_allowance_wh', 'surcharge_cents',
                           'service_state'],
                          certificate_rows, ',')

    measures = {
        'p01': len(ctx.normalised_documents),
        'p02': len(ctx.lattice_document),
        'p03': len(ctx.energy_floor_document),
        'p04': len(ctx.queue_document),
        'p05': len(ctx.provisional_document),
        'p06': len(ctx.violation_document),
        'p07': len(ctx.crane_document),
        'p08': ctx.battery_cycle,
        'p09': len(ctx.iteration_document),
        'p10': ctx.energy_charge_total,
        'p11': len(ctx.correction_document),
        'p12': ctx.sweeps_run,
        'p13': ctx.unmet_mandatory,
        'p14': len(corpus.document_order) + 1,
    }
    trace = []
    for stage, note in corpus.stage_titles:
        trace.append({'stage': stage, 'note': note, 'measure': measures[stage]})
    publication.line_objects('audit_trace.jsonl', trace)

    required_total = sum(ctx.required[rid] for rid in ctx.queue)
    share_text = fmt_ratio(Fraction(ctx.unmet_mandatory, required_total)) \
        if required_total else fmt_ratio(0)
    totals = [
        ('day_id', corpus.day_id),
        ('day_reference', corpus.day_reference),
        ('live_sheet', corpus.live_sheet),
        ('reefers_normalised', fmt_whole(len(ctx.reefer_ids))),
        ('reefers_queued', fmt_whole(len(ctx.queue))),
        ('reefers_refused', fmt_whole(len(ctx.refused))),
        ('spill_count', fmt_whole(ctx.spill_count)),
        ('hard_violations', fmt_whole(ctx.hard_violations)),
        ('unmet_mandatory_wh', fmt_whole(ctx.unmet_mandatory)),
        ('deadline_penalty_cents', fmt_whole(ctx.deadline_penalty)),
        ('peak_demand_w', fmt_whole(ctx.yard_peak)),
        ('energy_cost_cents', fmt_whole(ctx.energy_cost)),
        ('battery_cycle_wh', fmt_whole(ctx.battery_cycle)),
        ('unmet_share_of_mandatory', share_text),
    ]
    lines = ['# control totals for ' + corpus.day_id]
    lines += ['%s = %s' % (key, value) for key, value in totals]
    publication.write('dispatch_control_totals.conf', '\n'.join(lines) + '\n')

    by_feeder = []
    for feeder_id in sorted(ctx.feeders):
        for interval in corpus.intervals:
            key = (feeder_id, interval)
            support = support_of(ctx, feeder_id, interval)
            limit = ctx.adjusted[key] + support
            load = ctx.post_load[key]
            if load > limit:
                state = 'over_capacity'
            elif load == limit:
                state = 'at_capacity'
            else:
                state = 'clear'
            by_feeder.append([feeder_id, fmt_whole(interval), fmt_whole(load),
                              fmt_whole(ctx.adjusted[key]), fmt_whole(support), state])
    publication.delimited('final_schedule_by_feeder.psv',
                          ['feeder_id', 'interval', 'load_w', 'adjusted_capacity_w',
                           'battery_support_w', 'feeder_state'],
                          by_feeder, '|')

    vessels = {}
    for rid in ctx.queue:
        vessels.setdefault(ctx.reefer[rid]['vessel_id'], []).append(rid)
    lines = ['<?xml version="1.0" encoding="utf-8"?>',
             '<dispatch day="%s" reference="%s">' % (corpus.day_id, corpus.day_reference)]
    for vessel_id in sorted(vessels):
        members = sorted(vessels[vessel_id])
        cutoff = ctx.cutoff[members[0]]
        lines.append('  <vessel id="%s" cutoff="%d" members="%d">'
                     % (vessel_id, cutoff, len(members)))
        for rid in members:
            allowance = sum(value for (holder, _), value in ctx.allowance.items()
                            if holder == rid)
            lines.append('    <reefer id="%s" required_wh="%d" served_wh="%d"'
                         ' shortfall_wh="%d" allowance_wh="%d"/>'
                         % (rid, ctx.required[rid], ctx.served[rid],
                            ctx.shortfall[rid], allowance))
        lines.append('  </vessel>')
    lines.append('</dispatch>')
    publication.write('final_schedule_by_vessel.xml', '\n'.join(lines) + '\n')

    for substation_id in corpus.reported_substations:
        feeders = sorted(ctx.substation_feeders.get(substation_id, []))
        peak, interval = ctx.substation_peak[substation_id]
        served = 0
        for feeder_id in feeders:
            for slot in corpus.intervals:
                served += round_half_up(Fraction(ctx.post_load[(feeder_id, slot)], 4))
        publication.object_document(corpus.report_names[substation_id], {
            'day_id': corpus.day_id,
            'substation_id': substation_id,
            'feeder_count': len(feeders),
            'feeders': feeders,
            'ceiling_w': corpus.substation_ceiling.get(substation_id, 0),
            'peak_w': peak,
            'peak_interval': interval,
            'band_code': ctx.substation_band[substation_id],
            'demand_charge_cents': ctx.substation_charge[substation_id],
            'served_energy_wh': served,
        })

    spilled = ctx.spill_count - ctx.unspilled_count
    summary = [
        '# Ashgrove Point reefer yard dispatch summary',
        '',
        'Operating day %s was recomputed from the working papers under the input'
        ' directory. The governing workbook sheet was %s.'
        % (corpus.day_id, corpus.live_sheet),
        '',
        '## Admission',
        '',
        '%d reefers were normalised and %d of them reached the dispatch priority'
        ' queue. %d were set aside by the admission ladder.'
        % (len(ctx.reefer_ids), len(ctx.queue), len(ctx.refused)),
        '',
        '## Reconciliation',
        '',
        'The feeder reconciliation removed %d placements and spilled %d of them into'
        ' a later interval. The reconciliation ran %d passes against the pass budget.'
        % (ctx.spill_count, spilled, ctx.passes_run),
        '',
        '## Objective',
        '',
        'hard violations %d, unmet mandatory energy %d watt hours, deadline penalty'
        ' %d cents, peak demand %d watts, energy cost %d cents, battery cycle %d'
        ' watt hours.'
        % (ctx.hard_violations, ctx.unmet_mandatory, ctx.deadline_penalty,
           ctx.yard_peak, ctx.energy_cost, ctx.battery_cycle),
    ]
    publication.write('daily_dispatch_summary.md', '\n'.join(summary) + '\n')

    documents = []
    for name in corpus.document_order:
        data = publication.payloads[name]
        documents.append({
            'name': name,
            'bytes': len(data),
            'sha256': hashlib.sha256(data).hexdigest(),
        })
    core = publication.digest(corpus.core_documents)
    rest = [name for name in corpus.document_order
            if name not in set(corpus.core_documents)]
    publication.object_document('publication_manifest.json', {
        'day_id': corpus.day_id,
        'day_reference': corpus.day_reference,
        'document_count': len(documents),
        'core_digest': core,
        'publication_digest': publication.digest(rest),
        'documents': documents,
    })


# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='Ashgrove Point dispatch recomputation')
    parser.add_argument('--data', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()

    corpus = Corpus(args.data)
    os.makedirs(args.out, exist_ok=True)
    publication = Publication(args.out)
    ctx = Context()

    stage_p01_unit_normalisation(corpus, ctx)
    stage_p02_availability_lattice(corpus, ctx)
    stage_p03_energy_floor(corpus, ctx)
    stage_p04_priority_queue(corpus, ctx)
    stage_p05_provisional_allocation(corpus, ctx)
    stage_p06_feeder_reconciliation(corpus, ctx)
    stage_p07_crane_interaction(corpus, ctx)
    stage_p08_battery_intervention(corpus, ctx)
    stage_p09_load_reconciliation(corpus, ctx)
    stage_p10_tariff_and_demand(corpus, ctx)
    stage_p11_deadline_correction(corpus, ctx)
    stage_p12_cycle_break(corpus, ctx)
    stage_p13_objective(corpus, ctx)
    stage_p14_publication(corpus, ctx, publication)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
