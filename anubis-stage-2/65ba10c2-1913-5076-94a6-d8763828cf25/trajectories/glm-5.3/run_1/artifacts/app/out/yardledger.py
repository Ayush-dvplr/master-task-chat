#!/usr/bin/env python3
"""Kestrel Point container terminal: recompute one operating shift.

The program reads the working papers of one shift from the directory it is
pointed at, works the fourteen stages of the terminal contract in order and
publishes the documents of the shift's ledger into the output directory.

Nothing about any particular shift is held in this file.  Every identifier,
control value, threshold, boundary, rung code and vocabulary member is read
from the directory the program is pointed at.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import zipfile
import zlib
from collections import defaultdict
from fractions import Fraction
from xml.etree import ElementTree as ET

SSML = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
WML = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
RELNS = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'


# --------------------------------------------------------------------------
# exact arithmetic and published forms
# --------------------------------------------------------------------------

def round_half_up(value):
    """Half up, away from zero, over the exact rationals."""
    value = Fraction(value)
    if value >= 0:
        return (2 * value + 1) // 2
    return -((-2 * value + 1) // 2)


def fmt_int(value):
    """A whole quantity: a plain integer, no sign when it is zero."""
    return str(int(value))


def fmt_ratio(value):
    """A ratio at exactly nine decimal places."""
    rounded = round_half_up(Fraction(value) * 10 ** 9)
    magnitude = abs(int(rounded))
    whole, part = divmod(magnitude, 10 ** 9)
    sign = '-' if rounded < 0 and magnitude else ''
    return sign + str(whole) + '.' + format(part, '09d')


def choose(values, keyword, default=None):
    """The closed vocabulary member that carries a keyword."""
    for member in values:
        if member == keyword:
            return member
    for member in values:
        if keyword.lower() in member.lower():
            return member
    if default is not None:
        return default
    raise ValueError('no vocabulary member carries %r' % keyword)


# --------------------------------------------------------------------------
# reading the plain text papers
# --------------------------------------------------------------------------

def read_text(path):
    with open(path, 'r', encoding='utf-8', newline='') as handle:
        return handle.read()


def read_table(path, delimiter):
    """A delimited paper as a list of dicts keyed by its header names."""
    lines = read_text(path).split('\n')
    while lines and lines[-1] == '':
        lines.pop()
    if not lines:
        return []
    header = lines[0].split(delimiter)
    rows = []
    for line in lines[1:]:
        if line == '':
            continue
        rows.append(dict(zip(header, line.split(delimiter))))
    return rows


def read_jsonl(path):
    records = []
    for line in read_text(path).split('\n'):
        if line.strip():
            records.append(json.loads(line))
    return records


def read_ini(path):
    sections = {}
    current = ''
    for line in read_text(path).split('\n'):
        line = line.strip()
        if not line or line.startswith('#') or line.startswith(';'):
            continue
        if line.startswith('[') and line.endswith(']'):
            current = line[1:-1].strip()
            sections.setdefault(current, {})
            continue
        if '=' in line:
            key, _, value = line.partition('=')
            sections.setdefault(current, {})[key.strip()] = value.strip()
    return sections


def read_yaml_scalars(path):
    """The top level scalar keys of a simple yaml paper."""
    scalars = {}
    for line in read_text(path).split('\n'):
        if not line or line[0] in ' \t' or line.lstrip().startswith('#'):
            continue
        if ':' not in line:
            continue
        key, _, value = line.partition(':')
        value = value.strip()
        if value in ('', '>-', '|-', '>', '|'):
            continue
        scalars[key.strip()] = value
    return scalars


def read_toml(path):
    """The string valued keys of a simple toml paper."""
    text = read_text(path)
    text = re.sub(r'"""(.*?)"""',
                  lambda match: '"' + match.group(1).replace('\n', ' ') + '"',
                  text, flags=re.S)
    sections = {'': {}}
    current = ''
    for line in text.split('\n'):
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        if stripped.startswith('[') and stripped.endswith(']'):
            current = stripped[1:-1].strip()
            sections.setdefault(current, {})
            continue
        if '=' in stripped:
            key, _, value = stripped.partition('=')
            value = value.strip()
            if value.startswith('"') and value.endswith('"') and len(value) >= 2:
                value = value[1:-1]
            sections.setdefault(current, {})[key.strip()] = value
    return sections


# --------------------------------------------------------------------------
# reading the three office papers
# --------------------------------------------------------------------------

def read_workbook(path):
    """Every sheet of a workbook, as a list of rows, each a list of cells."""
    archive = zipfile.ZipFile(path)
    shared = []
    if 'xl/sharedStrings.xml' in archive.namelist():
        root = ET.fromstring(archive.read('xl/sharedStrings.xml'))
        for item in root:
            shared.append(''.join(node.text or '' for node in item.iter(SSML + 't')))
    rels = ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
    targets = {rel.get('Id'): rel.get('Target') for rel in rels}
    book = ET.fromstring(archive.read('xl/workbook.xml'))
    sheets = []
    for sheet in book.iter(SSML + 'sheet'):
        target = targets[sheet.get(RELNS + 'id')]
        if not target.startswith('xl/'):
            target = 'xl/' + target.lstrip('/')
        sheets.append((sheet.get('name'), target))
    result = []
    for name, target in sheets:
        root = ET.fromstring(archive.read(target))
        rows = []
        for row in root.iter(SSML + 'row'):
            cells = {}
            for cell in row:
                column = 0
                for char in re.sub(r'\d+', '', cell.get('r', '')):
                    column = column * 26 + (ord(char) - 64)
                node = cell.find(SSML + 'v')
                if node is None:
                    inline = cell.find(SSML + 'is')
                    value = (''.join(t.text or '' for t in inline.iter(SSML + 't'))
                             if inline is not None else '')
                elif cell.get('t') == 's':
                    value = shared[int(node.text)]
                else:
                    value = node.text or ''
                if value != '':
                    cells[column] = value
            width = max(cells) if cells else 0
            rows.append([cells.get(index, '') for index in range(1, width + 1)])
        result.append((name, rows))
    return result


def read_memo(path):
    """The memorandum as the list of text lines its pages carry."""
    data = open(path, 'rb').read()
    lines = []
    for match in re.finditer(rb'stream\r?\n(.*?)endstream', data, re.S):
        chunk = match.group(1)
        try:
            chunk = zlib.decompress(chunk)
        except zlib.error:
            pass
        text = chunk.decode('latin-1')
        for item in re.finditer(r'\((.*?)\)\s*Tj', text, re.S):
            body = item.group(1)
            body = body.replace('\\(', '(').replace('\\)', ')').replace('\\\\', '\\')
            lines.append(body)
    return lines


def read_directive(path):
    """The directive as its paragraphs and tables, in document order."""
    archive = zipfile.ZipFile(path)
    root = ET.fromstring(archive.read('word/document.xml'))
    items = []
    for child in root.find(WML + 'body'):
        if child.tag == WML + 'p':
            items.append(('p', ''.join(node.text or '' for node in child.iter(WML + 't'))))
        elif child.tag == WML + 'tbl':
            rows = []
            for tr in child.iter(WML + 'tr'):
                rows.append([''.join(node.text or '' for node in tc.iter(WML + 't'))
                             for tc in tr.findall(WML + 'tc')])
            items.append(('tbl', rows))
    return items


# --------------------------------------------------------------------------
# the publication contract read out of the shift's own papers
# --------------------------------------------------------------------------

def parse_schema_reference(path):
    """The artifact order, the core documents, the measures, the checks and
    the closed vocabularies, all read from the schema reference itself."""
    text = read_text(path)
    sections = {}
    current = None
    for line in text.split('\n'):
        head = re.match(r'^SECTION (\d+)\s', line)
        if head:
            current = int(head.group(1))
            sections[current] = []
            continue
        if current is not None:
            sections[current].append(line)
    names = re.compile(r'^\s{2}(\S+\.(?:csv|psv|tsv|jsonl|json|xml|conf|md))\s*$')
    simple = re.compile(r'^\s{2}(\w+)\s*$')
    artifacts = [names.search(line).group(1) for line in sections.get(1, [])
                 if names.search(line)]
    core = [names.search(line).group(1) for line in sections.get(2, [])
            if names.search(line)]
    measures = [simple.search(line).group(1) for line in sections.get(6, [])
                if simple.search(line)]
    identities = [simple.search(line).group(1) for line in sections.get(7, [])
                  if simple.search(line)]
    vocab = {}
    lines = sections.get(8, [])
    index = 0
    while index < len(lines):
        head = re.match(r'^\s*(\S+)\s+(\w+)\s+takes\s+(.*)$', lines[index])
        if not head:
            index += 1
            continue
        document, field, tail = head.groups()
        values = []
        if tail.strip().rstrip('.').startswith('one of'):
            # the list sits after a blank line
            index += 1
            while index < len(lines) and not lines[index].strip():
                index += 1
            while index < len(lines):
                item = simple.search(lines[index])
                if item:
                    values.append(item.group(1))
                    index += 1
                else:
                    break
        else:
            index += 1
            body = tail
            while re.search(r'\bor\s*$', body.rstrip('.')) and index < len(lines):
                body = body.rstrip('.') + ' ' + lines[index].strip()
                index += 1
            values = [value for value in re.split(r'\s+or\s+', body.rstrip('.')) if value]
            values = [value for value in values
                      if value and not value.startswith(('the ', 'or '))]
        vocab[(document, field)] = values
    return {'artifacts': artifacts, 'core': core, 'measures': measures,
            'identities': identities, 'vocab': vocab}


def parse_ladder(path):
    """The rungs of the admission ladder in the order the paper prints them."""
    rungs = []
    current = None
    for line in read_text(path).split('\n'):
        head = re.match(r'^rung\s+(\d+)\s+(\S+)\s*$', line)
        if head:
            current = {'position': int(head.group(1)), 'code': head.group(2), 'words': ''}
            rungs.append(current)
            continue
        if current is not None and line.startswith('        '):
            current['words'] += ' ' + line.strip()
    for rung in rungs:
        rung['test'] = classify_rung(rung['code'] + ' ' + rung['words'])
    rungs.sort(key=lambda rung: rung['position'])
    return rungs


def classify_rung(words):
    lowered = words.lower()
    if 'sealed' in lowered:
        return 'sealed'
    if 'already closed' in lowered or 'stale' in lowered:
        return 'stale'
    if 'master register' in lowered or 'does not carry' in lowered:
        return 'unknown'
    if 'tier' in lowered:
        return 'tier'
    if 'reserv' in lowered:
        return 'reserved'
    if 'cluster' in lowered or 'canonical' in lowered:
        return 'duplicate'
    raise ValueError('the ladder prints a rung no rule names: %r' % words)


def workbook_tables(rows):
    """The tables of a workbook sheet, keyed by the label that opens them."""
    tables = {}
    header = None
    label = None
    for row in rows:
        if not any(cell.strip() for cell in row):
            header = None
            continue
        first = row[0].strip() if row else ''
        if first.endswith('_table') or first.endswith('_register') or first == 'control_name':
            if first.endswith('_table'):
                label = first[:-len('_table')]
            elif first.endswith('_register'):
                label = first[:-len('_register')]
            else:
                label = 'control'
            header = row[1:]
            tables.setdefault(label, {'header': header, 'rows': []})
            continue
        if header is not None:
            width = len(header) + 1
            tables[label]['rows'].append(list(row[:width]) + [''] * max(0, width - len(row)))
    return tables


def table_records(table):
    """The rows of one workbook table as dicts keyed by its header."""
    header = table['header']
    width = len(header) + 1
    records = []
    for row in table['rows']:
        records.append({name: (row[index + 1] if index + 1 < len(row) else '')
                       for index, name in enumerate(header)})
    return records


def control_table(table):
    """The control values of a workbook sheet, keyed by their control name."""
    controls = {}
    for row in table['rows']:
        if len(row) >= 2 and row[0]:
            controls[row[0]] = row[1:]
    return controls


def mass_registers(dictionary):
    """The mass registers a declaration may name, from the unit dictionary."""
    pairs = []
    statement = dictionary.get('mass', {}).get('statement', '')
    for match in re.finditer(r'\bthe\s+(\S+)\s+register\s+is\s+in\s+(\S+)', statement,
                             re.IGNORECASE):
        unit, name = match.group(1), match.group(2).strip('.,;:')
        name = name[:-1] if name.endswith('s') else name
        pairs.append((unit, name))
    return pairs


def memo_controls(lines):
    """The control values the memorandum issues."""
    controls = {}
    for line in lines:
        match = re.match(r'^\s*([a-z_]+)\s+(\d+)', line)
        if match:
            controls[match.group(1)] = int(match.group(2))
    return controls


def memo_ladder(lines):
    """The rehandle surcharge ladder the memorandum issues."""
    rungs = []
    started = False
    for line in lines:
        tokens = line.split()
        if tokens == ['tier_depth', 'surcharge_cents']:
            started = True
            continue
        if started:
            if len(tokens) == 2 and tokens[0].isdigit() and tokens[1].isdigit():
                rungs.append((int(tokens[0]), int(tokens[1])))
            else:
                break
    return rungs


def memo_roster(lines):
    """The quay gang roster the memorandum crews."""
    roster = {}
    started = False
    for line in lines:
        tokens = line.split()
        if tokens[:4] == ['berth_id', 'slot_code', 'gang_code', 'gang_minutes']:
            started = True
            continue
        if started:
            if len(tokens) == 4 and tokens[3].isdigit():
                roster[(tokens[0], tokens[1])] = (roster.get((tokens[0], tokens[1]), 0)
                                                 + int(tokens[3]))
            elif tokens:
                break
    return roster


def directive_tables(items):
    """The stowage ordering keys and the class ranks the directive issues."""
    keys = []
    ranks = {}
    for kind, payload in items:
        if kind != 'tbl' or not payload:
            continue
        header = payload[0]
        if header[:2] == ['key_position', 'key_name']:
            placed = {int(row[0]): row[1] for row in payload[1:] if len(row) >= 2}
            keys = [placed[index] for index in sorted(placed)]
        elif header[:2] == ['box_class', 'class_rank']:
            for row in payload[1:]:
                if len(row) >= 2:
                    ranks[row[0]] = int(row[1])
    return keys, ranks


def applicable_revision(rows, subject, shift_id, set_aside):
    """The applicable revision of every subject, through revision precedence."""
    best = {}
    highest = {}
    for row in rows:
        if row.get('shift_id', shift_id) != shift_id:
            continue
        if any(row.get(column, 'no') == 'yes' for column in set_aside):
            continue
        key = row[subject]
        seq = int(row['revision_seq'])
        if key not in highest or seq > highest[key]:
            highest[key] = seq
            best[key] = row
    return best


def exception_rungs(ctx):
    """Which rung each exception kind lifts, from the words the ladder prints."""
    mapping = {}
    for kind in sorted({row['exception_kind'] for row in ctx['exceptions']
                        if row['shift_id'] == ctx['shift_id']}):
        stems = [stem for stem in kind.split('_')
                 if stem not in ('waiver', 'release') and len(stem) >= 4]
        lifted = None
        for rung in ctx['ladder']:
            hay = (rung['code'] + ' ' + rung['words']).lower()
            for stem in stems:
                if stem[:5].lower() in hay:
                    lifted = rung['code']
                    break
            if lifted:
                break
        mapping[kind] = lifted
    return mapping


# --------------------------------------------------------------------------
# writing documents
# --------------------------------------------------------------------------

def write_delimited(path, header, rows, delimiter):
    lines = [delimiter.join(header)]
    for row in rows:
        lines.append(delimiter.join(row))
    with open(path, 'w', encoding='utf-8', newline='') as handle:
        handle.write('\n'.join(lines) + '\n')


def write_jsonl(path, records):
    with open(path, 'w', encoding='utf-8', newline='') as handle:
        for record in records:
            handle.write(json.dumps(record, separators=(',', ':'), ensure_ascii=False) + '\n')


def write_json(path, obj):
    with open(path, 'w', encoding='utf-8', newline='') as handle:
        handle.write(json.dumps(obj, indent=2, ensure_ascii=False) + '\n')


def write_text(path, text):
    with open(path, 'w', encoding='utf-8', newline='') as handle:
        handle.write(text)


def xml_escape(value):
    return (str(value).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            .replace('"', '&quot;').replace("'", '&apos;'))


def slot_of(ctx, minute):
    """The slot a minute belongs to; a minute on a boundary closes a slot."""
    length = ctx['slot_length']
    ordinal = minute // length if minute % length == 0 else minute // length + 1
    if ordinal == 0:
        ordinal = 1
    if ordinal > ctx['slot_count']:
        return ctx['marker']
    return ctx['slots'][ordinal - 1]


def slot_ordinal(ctx, slot_code):
    if slot_code == ctx['marker'] or slot_code not in ctx['slots']:
        return None
    return ctx['slots'].index(slot_code) + 1


def canonical_order(events):
    """Y05.2: slot ordinal, source priority, event_seq, box_id, order_id."""
    def key(event):
        ordinal = event['slot_ordinal']
        return (1 if ordinal is None else 0, ordinal or 0, event['source_priority'],
                event['event_seq'], event['box_id'], event['order_id'])
    return sorted(events, key=key)


def service_group_of(ctx, box_id):
    """The service group a box carries, taken from its vessel's call."""
    record = ctx['box'].get(box_id)
    if not record:
        return ctx['marker']
    call = ctx['obligation'].get(record['vessel_id'])
    return call['service_group'] if call else ctx['marker']


# --------------------------------------------------------------------------
# the shift context
# --------------------------------------------------------------------------

def load_context(data_dir):
    ctx = {'data_dir': data_dir}
    join = lambda name: os.path.join(data_dir, name)

    topo = ET.parse(join('yard_topology.xml')).getroot()
    ctx['shift_id'] = (topo.findtext('shift') or '').strip()
    ctx['reference'] = (topo.findtext('reference') or '').strip()
    ctx['blocks_in_force'] = []
    ctx['zone_of_block'] = {}
    for block in topo.find('blocks'):
        if block.get('in_force') == 'yes':
            ctx['blocks_in_force'].append(block.get('id'))
            ctx['zone_of_block'][block.get('id')] = block.get('zone')
    ctx['blocks_in_force'].sort()

    dictionary = read_toml(join('unit_register_dictionary.toml'))
    ctx['marker'] = dictionary.get('absence', {}).get('marker', '-')

    boundaries = read_yaml_scalars(join('boundary_conventions.yaml'))
    ctx['slot_length'] = int(boundaries['slot_length_minutes'])
    ctx['slot_count'] = int(boundaries['slot_count'])

    grid = read_table(join('slot_grid_calendar.csv'), ',')
    ctx['slots'] = sorted({row['slot_code'] for row in grid})
    ctx['grid'] = {(row['slot_code'], row['block_id']): (row['sealed'], row['in_service'])
                   for row in grid}

    schema = parse_schema_reference(join('output_schema_reference.md'))
    ctx['artifact_order'] = schema['artifacts']
    ctx['core_documents'] = set(schema['core'])
    ctx['measures'] = schema['measures']
    ctx['identity_names'] = schema['identities']
    ctx['vocab'] = schema['vocab']

    ctx['ladder'] = parse_ladder(join('move_admission_ladder.txt'))

    workbook = read_workbook(join('quay_capacity_workbook.xlsx'))
    live = None
    for name, rows in workbook:
        if any(ctx['reference'] in row for row in rows):
            live = (name, rows)
            break
    if live is None:
        raise SystemExit('no workbook sheet carries the shift reference')
    ctx['live_sheet_name'] = live[0]
    tables = workbook_tables(live[1])
    controls = control_table(tables['control'])
    ctx['teu_factor'] = {record['iso_length']: int(record['teu_factor'])
                         for record in table_records(tables['teu_factor'])}
    ctx['vessel_slot_ceiling'] = {(record['vessel_id'], record['slot_code']):
                                  int(record['admissible_minutes'])
                                  for record in table_records(tables['vessel_slot_ceiling'])}
    ctx['damping'] = Fraction(int(controls['ration_damping_fraction'][0]),
                              int(controls['ration_damping_fraction'][1]))
    ctx['base_move_charge'] = int(controls['base_move_charge_cents'][0])
    ctx['unit_kilograms'] = {}
    for unit, name in mass_registers(dictionary):
        key = name + '_kilograms'
        if key in controls:
            ctx['unit_kilograms'][unit] = Fraction(int(controls[key][0]),
                                                    int(controls[key][1]))

    memo = read_memo(join('berth_operations_memo.pdf'))
    memo_values = memo_controls(memo)
    ctx['pass_budget'] = memo_values['ration_pass_budget']
    ctx['minimum_step'] = memo_values['ration_minimum_step']
    ctx['protection_depth'] = memo_values['dependency_protection_depth']
    ctx['surcharge_ladder'] = memo_ladder(memo)
    ctx['gang_roster'] = memo_roster(memo)

    keys, ranks = directive_tables(read_directive(join('stowage_ordering_directive.docx')))
    ctx['stowage_keys'] = keys
    ctx['class_rank'] = ranks

    roster = read_ini(join('berth_reporting_roster.conf'))
    ctx['reporting_berths'] = [b.strip() for b in roster['roster']['reporting_berths'].split(',')]

    ctx['orders'] = read_table(join('move_order_journal.csv'), ',')
    ctx['withdrawn_journal'] = read_table(join('withdrawn_order_journal.tsv'), '\t')
    ctx['dependencies'] = read_jsonl(join('move_dependency_declarations.jsonl'))
    ctx['source_register'] = read_table(join('source_priority_register.csv'), ',')
    ctx['box_register'] = read_table(join('box_master_register.csv'), ',')
    ctx['mass_returns'] = read_table(join('mass_declaration_returns.psv'), '|')
    ctx['vessel_calls'] = read_table(join('vessel_call_register.csv'), ',')
    ctx['geometry_register'] = read_table(join('block_geometry_register.csv'), ',')
    ctx['snapshot'] = read_table(join('stack_inventory_snapshot.csv'), ',')
    ctx['reservation_notices'] = read_jsonl(join('hold_reservation_notices.jsonl'))
    ctx['exceptions'] = read_table(join('operational_exception_notices.csv'), ',')
    ctx['confirmations'] = read_jsonl(join('crane_confirmation_feed.ndjson'))
    ctx['equipment_register'] = read_table(join('handling_equipment_register.csv'), ',')
    ctx['cutoff_board'] = read_table(join('cutoff_notice_board.tsv'), '\t')
    ctx['stowage'] = read_table(join('stowage_obligation_list.psv'), '|')
    ctx['demand'] = read_table(join('quay_demand_returns.csv'), ',')
    ctx['berth_windows'] = read_table(join('berth_window_register.csv'), ',')

    ctx['box'] = applicable_revision(ctx['box_register'], 'box_id', ctx['shift_id'], ['retired'])
    ctx['call'] = applicable_revision(ctx['vessel_calls'], 'vessel_id', ctx['shift_id'],
                                      ['withdrawn'])
    ctx['geom'] = applicable_revision(ctx['geometry_register'], 'block_id', ctx['shift_id'],
                                       ['retired', 'future'])
    ctx['source_rank'] = applicable_revision(ctx['source_register'], 'source_system',
                                             ctx['shift_id'], ['retired'])
    ctx['equipment'] = applicable_revision(ctx['equipment_register'], 'equipment_id',
                                           ctx['shift_id'], ['retired'])
    ctx['exception_rungs'] = exception_rungs(ctx)
    return ctx


# --------------------------------------------------------------------------
# Y01  the canonical event set
# --------------------------------------------------------------------------

def stage_y01_canonical_events(ctx, out):
    withdrawn = {row['order_id'] for row in ctx['withdrawn_journal']
                 if row['shift_id'] == ctx['shift_id'] and row['state'] == 'withdrawn'}
    events = []
    for row in ctx['orders']:
        if row['order_id'] in withdrawn:
            continue
        rank = ctx['source_rank'].get(row['source_system'])
        events.append({
            'order_id': row['order_id'], 'box_id': row['box_id'],
            'source_system': row['source_system'],
            'source_priority': int(rank['priority_rank']) if rank else 0,
            'event_seq': int(row['event_seq']), 'raised_min': int(row['raised_min']),
            'slot_code': slot_of(ctx, int(row['raised_min'])),
            'cluster_tag': row['cluster_tag'], 'to_block': row['to_block'],
            'to_row': row['to_row'], 'to_tier': row['to_tier']})
    for event in events:
        event['slot_ordinal'] = slot_ordinal(ctx, event['slot_code'])
    events = canonical_order(events)
    for index, event in enumerate(events, 1):
        event['event_key'] = index
    ctx['events'] = events
    ctx['event_by_order'] = {event['order_id']: event for event in events}
    ctx['counts']['canonical_events'] = len(events)
    header = ['event_key', 'order_id', 'box_id', 'source_system', 'source_priority',
              'event_seq', 'raised_min', 'slot_code', 'cluster_tag']
    rows = [[fmt_int(e['event_key']), e['order_id'], e['box_id'], e['source_system'],
             fmt_int(e['source_priority']), fmt_int(e['event_seq']), fmt_int(e['raised_min']),
             e['slot_code'], e['cluster_tag']] for e in events]
    write_delimited(os.path.join(out, 'canonical_events.csv'), header, rows, ',')


# --------------------------------------------------------------------------
# Y02  unit normalisation
# --------------------------------------------------------------------------

def stage_y02_unit_normalisation(ctx, out):
    marker = ctx['marker']
    filed = {}
    for row in ctx['mass_returns']:
        if row['state'] != 'filed':
            continue
        seq = int(row['declaration_seq'])
        if row['box_id'] not in filed or seq > filed[row['box_id']][0]:
            filed[row['box_id']] = (seq, row)
    states = ctx['vocab'][('container_dimensions.csv', 'mass_state')]
    declared_state = choose(states, 'declared')
    absent_state = choose(states, 'not_declared')
    dimensions = []
    for box_id in sorted(ctx['box']):
        record = ctx['box'][box_id]
        length = re.sub(r'(?i)\s*ft\s*$', '', record['iso_length']).strip()
        mass = None
        if box_id in filed:
            declaration = filed[box_id][1]
            if declaration['mass_value'] != marker:
                factor = ctx['unit_kilograms'].get(declaration['mass_unit'], Fraction(1))
                mass = int(Fraction(int(declaration['mass_value'])) * factor)
        dimensions.append({'box_id': box_id, 'iso_length': length,
                           'teu_factor': ctx['teu_factor'].get(length, 0),
                           'box_class': record['box_class'],
                           'vessel_id': record['vessel_id'],
                           'mass_kg': mass if mass is not None else 0,
                           'mass_state': declared_state if mass is not None else absent_state})
    ctx['dimensions'] = {d['box_id']: d for d in dimensions}
    ctx['boxes_never_declared'] = sorted(d['box_id'] for d in dimensions
                                         if d['mass_state'] == absent_state)
    header = ['box_id', 'iso_length', 'teu_factor', 'box_class', 'vessel_id', 'mass_kg',
              'mass_state']
    rows = [[d['box_id'], d['iso_length'], fmt_int(d['teu_factor']), d['box_class'],
             d['vessel_id'], fmt_int(d['mass_kg']), d['mass_state']] for d in dimensions]
    write_delimited(os.path.join(out, 'container_dimensions.csv'), header, rows, ',')


# --------------------------------------------------------------------------
# Y03  vessel obligation state
# --------------------------------------------------------------------------

def stage_y03_vessel_obligation(ctx, out):
    obligations = []
    for vessel_id in sorted(ctx['call']):
        row = ctx['call'][vessel_id]
        obligations.append({'vessel_id': vessel_id, 'voyage': row['voyage'],
                           'berth_id': row['berth_id'],
                           'service_group': row['service_group'],
                           'destination': row['destination'],
                           'voyage_sequence': row['voyage_sequence'],
                           'applicable_revision': row['revision_seq']})
    ctx['obligation'] = {o['vessel_id']: o for o in obligations}
    header = ['vessel_id', 'voyage', 'berth_id', 'service_group', 'destination',
              'voyage_sequence', 'applicable_revision']
    rows = [[o['vessel_id'], o['voyage'], o['berth_id'], o['service_group'], o['destination'],
             o['voyage_sequence'], o['applicable_revision']] for o in obligations]
    write_delimited(os.path.join(out, 'vessel_obligation.csv'), header, rows, ',')


# --------------------------------------------------------------------------
# Y04  the opening yard
# --------------------------------------------------------------------------

def stage_y04_opening_yard(ctx, out):
    geometry = {}
    for block_id in ctx['blocks_in_force']:
        row = ctx['geom'].get(block_id)
        rows = int(row['rows']) if row else 0
        tiers = int(row['tiers_max']) if row else 0
        geometry[block_id] = {'rows': rows, 'tiers_max': tiers,
                              'slot_capacity': rows * tiers,
                              'zone': row['zone'] if row else ctx['zone_of_block'].get(
                                  block_id, ctx['marker'])}
    ctx['geometry'] = geometry
    positions = {}
    for row in ctx['snapshot']:
        if row['stack_state'] != 'stacked':
            continue
        if row['block_id'] not in geometry or row['box_id'] not in ctx['box']:
            continue
        if row['box_id'] in positions:
            continue
        positions[row['box_id']] = (row['block_id'], int(row['row_no']), int(row['tier_no']))
    ctx['opening_positions'] = positions
    opening = defaultdict(int)
    for _box_id, (block_id, _row, _tier) in positions.items():
        opening[block_id] += 1
    ctx['opening_count'] = opening
    header = ['block_id', 'zone', 'rows', 'tiers_max', 'slot_capacity', 'opening_boxes',
              'opening_free']
    rows = []
    for block_id in sorted(geometry):
        g = geometry[block_id]
        boxes = opening.get(block_id, 0)
        rows.append([block_id, g['zone'], fmt_int(g['rows']), fmt_int(g['tiers_max']),
                     fmt_int(g['slot_capacity']), fmt_int(boxes),
                     fmt_int(g['slot_capacity'] - boxes)])
    write_delimited(os.path.join(out, 'initial_occupancy.psv'), header, rows, '|')


# --------------------------------------------------------------------------
# Y05  the canonical event order
# --------------------------------------------------------------------------

def stage_y05_event_ordering(ctx, out):
    header = ['event_key', 'order_id', 'slot_code', 'source_priority', 'event_seq', 'box_id']
    rows = [[fmt_int(e['event_key']), e['order_id'], e['slot_code'],
             fmt_int(e['source_priority']), fmt_int(e['event_seq']), e['box_id']]
            for e in ctx['events']]
    write_delimited(os.path.join(out, 'event_order.csv'), header, rows, ',')


# --------------------------------------------------------------------------
# Y06  move dependencies and their cycles
# --------------------------------------------------------------------------

def stage_y06_dependency_cycles(ctx, out):
    orders = {event['order_id'] for event in ctx['events']}
    edges = {}
    for edge in ctx['dependencies']:
        if edge['state'] != 'declared':
            continue
        before, after = edge['before_order'], edge['after_order']
        if before not in orders or after not in orders or before == after:
            continue
        edges[edge['edge_id']] = (before, after, int(edge['edge_weight']))
    removed = set()
    report = []
    while True:
        components = cyclic_components(orders, edges, removed)
        if not components:
            break
        report.append(break_component(components[0], edges, removed, ctx))
    order = dependency_order(ctx, edges, removed)
    components = []
    for entry in report:
        components.append({'component_key': entry['component_key'],
                           'member_count': len(entry['members']),
                           'members': entry['members'],
                           'edge_removed': entry['edge_removed'],
                           'edge_weight': entry['edge_weight'],
                           'before_order': entry['before_order'],
                           'after_order': entry['after_order'],
                           'protected_count': entry['protected_count']})
    write_json(os.path.join(out, 'cycle_break_report.json'), {
        'shift_id': ctx['shift_id'],
        'protection_depth': ctx['protection_depth'],
        'component_count': len({entry['component_key'] for entry in report}),
        'components': components})
    header = ['position', 'order_id', 'event_key']
    rows = [[fmt_int(position), order_id, fmt_int(ctx['event_by_order'][order_id]['event_key'])]
            for position, order_id in enumerate(order, 1)]
    write_delimited(os.path.join(out, 'dependency_order.csv'), header, rows, ',')


def cyclic_components(orders, edges, removed):
    """Every strongly connected component of two orders or more, in key order."""
    adjacency = defaultdict(set)
    for edge_id, (before, after, _weight) in edges.items():
        if edge_id in removed:
            continue
        adjacency[before].add(after)
    state, low = {}, {}
    stack, on_stack = [], set()
    components = []
    counter = [0]

    def visit(node):
        state[node] = low[node] = counter[0]
        counter[0] += 1
        stack.append(node)
        on_stack.add(node)
        for neighbour in sorted(adjacency[node]):
            if neighbour not in state:
                visit(neighbour)
                low[node] = min(low[node], low[neighbour])
            elif neighbour in on_stack:
                low[node] = min(low[node], state[neighbour])
        if low[node] == state[node]:
            component = []
            while True:
                member = stack.pop()
                on_stack.discard(member)
                component.append(member)
                if member == node:
                    break
            if len(component) > 1:
                components.append(sorted(component))

    for node in sorted(orders):
        if node not in state:
            visit(node)
    components.sort(key=lambda members: members[0])
    return components


def break_component(component, edges, removed, ctx):
    """Y06.3 and Y06.4: the edge one cyclic component loses."""
    inside = {edge_id: value for edge_id, value in edges.items()
              if edge_id not in removed and value[0] in component and value[1] in component}
    ranked = sorted(inside.items(), key=lambda item: (-item[1][2], item[0]))
    depth = min(ctx['protection_depth'], len(ranked))
    protected = {edge_id for edge_id, _value in ranked[:depth]}
    candidates = [edge_id for edge_id in inside if edge_id not in protected]
    if not candidates:
        candidates = list(inside)
    chosen = min(candidates, key=lambda edge_id: (inside[edge_id][2], edge_id))
    removed.add(chosen)
    before, after, weight = edges[chosen]
    return {'component_key': component[0], 'members': list(component),
            'edge_removed': chosen, 'edge_weight': weight, 'before_order': before,
            'after_order': after, 'protected_count': depth}


def dependency_order(ctx, edges, removed):
    """Y06.6: the placeable order of lowest event key, one at a time."""
    pending = defaultdict(set)
    for edge_id, (before, after, _weight) in edges.items():
        if edge_id in removed:
            continue
        pending[after].add(before)
    placed = set()
    remaining = [event['order_id'] for event in ctx['events']]
    order = []
    while remaining:
        placeable = sorted((order_id for order_id in remaining
                            if not (pending[order_id] - placed)),
                           key=lambda order_id: ctx['event_by_order'][order_id]['event_key'])
        chosen = placeable[0]
        order.append(chosen)
        placed.add(chosen)
        remaining.remove(chosen)
    return order


# --------------------------------------------------------------------------
# Y07  move admission
# --------------------------------------------------------------------------

def opening_reservations(ctx, capacity, count):
    """Y07.4: the credit every held reservation opens the shift with."""
    marker = ctx['marker']
    reservations = {}
    for notice in ctx['reservation_notices']:
        if notice['shift_id'] != ctx['shift_id'] or notice['state'] != 'held':
            continue
        block_id = notice['block_id']
        free = capacity.get(block_id, 0) - count.get(block_id, 0)
        asked = notice['quantity']
        if asked in (marker, '', None):
            asked = free
        else:
            asked = int(asked)
        credit = max(0, min(asked, free))
        reservations[notice['reservation_id']] = {
            'reservation_id': notice['reservation_id'], 'block_id': block_id,
            'service_group': notice['service_group'], 'first_slot': notice['first_slot'],
            'last_slot': notice['last_slot'], 'asked': asked, 'credit': credit,
            'unmet': max(0, asked - credit)}
    return reservations


def reservation_covers(reservation, block_id, slot_code, slots):
    """Y07.4: a reservation stands over every slot from its first to its last."""
    if reservation['block_id'] != block_id or slot_code not in slots:
        return False
    if reservation['first_slot'] not in slots or reservation['last_slot'] not in slots:
        return False
    position = slots.index(slot_code)
    return (slots.index(reservation['first_slot']) <= position
            <= slots.index(reservation['last_slot']))


def stage_y07_move_admission(ctx, out):
    outcomes = ctx['vocab'][('move_eligibility.csv', 'outcome')]
    ctx['admitted_outcome'] = choose(outcomes, 'admitted')
    ctx['set_aside_outcome'] = choose(outcomes, 'set_aside')

    waivers = defaultdict(set)
    for row in ctx['exceptions']:
        if row['shift_id'] != ctx['shift_id'] or row['withdrawn'] == 'yes':
            continue
        rung = ctx['exception_rungs'].get(row['exception_kind'])
        if rung is None or row['target_kind'] != 'order':
            continue
        waivers[row['target_id']].add(rung)

    geometry = ctx['geometry']
    capacity = {block_id: geometry[block_id]['slot_capacity'] for block_id in geometry}
    count = {block_id: ctx['opening_count'].get(block_id, 0) for block_id in geometry}
    positions = dict(ctx['opening_positions'])
    reservations = opening_reservations(ctx, capacity, count)
    credits = {rid: r['credit'] for rid, r in reservations.items()}
    consumed = {rid: 0 for rid in reservations}
    cluster_admitted = set()
    accepted, rejected = [], []
    per_slot_count, per_slot_credit = {}, {}
    slots = ctx['slots']
    snapshot_index = [0]

    def snapshot(slot_code):
        per_slot_count[slot_code] = dict(count)
        per_slot_credit[slot_code] = dict(credits)

    def flush(upto):
        while snapshot_index[0] < upto:
            snapshot(slots[snapshot_index[0]])
            snapshot_index[0] += 1

    for event in ctx['events']:
        ordinal = event['slot_ordinal']
        flush(len(slots) if ordinal is None else ordinal - 1)
        reason = settle_event(ctx, event, waivers, geometry, capacity, count, reservations,
                              credits, cluster_admitted)
        event['outcome'] = (ctx['admitted_outcome'] if reason is None
                           else ctx['set_aside_outcome'])
        event['reason_code'] = reason if reason is not None else ctx['marker']
        if reason is None:
            accepted.append(event)
            previous = positions.get(event['box_id'])
            if previous:
                count[previous[0]] -= 1
            count[event['to_block']] += 1
            positions[event['box_id']] = (event['to_block'], int(event['to_row']),
                                          int(event['to_tier']))
            consume_reservation(ctx, event, reservations, credits, consumed)
            cluster_admitted.add(event['cluster_tag'])
        else:
            rejected.append(event)
    flush(len(slots))

    ctx['admission'] = {'accepted': accepted, 'rejected': rejected, 'positions': positions,
                        'reservations': reservations, 'credits': credits,
                        'consumed': consumed, 'per_slot_count': per_slot_count,
                        'per_slot_credit': per_slot_credit}
    ctx['counts']['admitted_moves'] = len(accepted)
    ctx['counts']['set_aside_moves'] = len(rejected)

    header = ['event_key', 'order_id', 'box_id', 'slot_code', 'to_block', 'to_row', 'to_tier',
              'outcome', 'reason_code']
    rows = [[fmt_int(e['event_key']), e['order_id'], e['box_id'], e['slot_code'], e['to_block'],
             e['to_row'], e['to_tier'], e['outcome'], e['reason_code']]
            for e in ctx['events']]
    write_delimited(os.path.join(out, 'move_eligibility.csv'), header, rows, ',')

    header = ['event_key', 'order_id', 'box_id', 'slot_code', 'reason_code']
    rows = [[fmt_int(e['event_key']), e['order_id'], e['box_id'], e['slot_code'], e['reason_code']]
            for e in rejected]
    write_delimited(os.path.join(out, 'rejected_moves.tsv'), header, rows, '\t')

    tally = defaultdict(int)
    for event in rejected:
        tally[event['reason_code']] += 1
    ctx['ladder_tally'] = {rung['code']: tally.get(rung['code'], 0) for rung in ctx['ladder']}
    header = ['reason_code', 'order_count']
    rows = [[rung['code'], fmt_int(ctx['ladder_tally'][rung['code']])] for rung in ctx['ladder']]
    write_delimited(os.path.join(out, 'rejection_reasons.csv'), header, rows, ',')

    header = ['event_key', 'order_id', 'box_id', 'slot_code', 'to_block', 'to_row', 'to_tier']
    rows = [[fmt_int(e['event_key']), e['order_id'], e['box_id'], e['slot_code'], e['to_block'],
             e['to_row'], e['to_tier']] for e in accepted]
    write_delimited(os.path.join(out, 'accepted_moves.csv'), header, rows, ',')


def settle_event(ctx, event, waivers, geometry, capacity, count, reservations, credits,
                 cluster_admitted):
    """Y07.1: the first rung that catches the order settles it."""
    lifted = waivers.get(event['order_id'], set())
    slot_code = event['slot_code']
    box = ctx['box'].get(event['box_id'])
    block_id = event['to_block']
    free_capacity = capacity.get(block_id, 0)
    tier = int(event['to_tier'])
    for rung in ctx['ladder']:
        if rung['code'] in lifted:
            continue
        test = rung['test']
        if test == 'unknown' and box is None:
            return rung['code']
        if test == 'sealed':
            sealed, _in_service = ctx['grid'].get((slot_code, block_id), ('no', 'yes'))
            if sealed == 'yes':
                return rung['code']
        if test == 'stale' and slot_code == ctx['marker']:
            return rung['code']
        if test == 'tier':
            tiers = geometry[block_id]['tiers_max'] if block_id in geometry else 0
            if block_id not in geometry or tiers <= 0 or tier > tiers:
                return rung['code']
        if test == 'reserved':
            free = free_capacity - count.get(block_id, 0)
            group = service_group_of(ctx, event['box_id'])
            withheld = 0
            for reservation_id in sorted(reservations):
                reservation = reservations[reservation_id]
                if credits[reservation_id] <= 0:
                    continue
                if reservation['service_group'] == group:
                    continue
                if not reservation_covers(reservation, block_id, slot_code, ctx['slots']):
                    continue
                withheld += credits[reservation_id]
            if free - withheld <= 0:
                return rung['code']
        if test == 'duplicate' and event['cluster_tag'] in cluster_admitted:
            return rung['code']
    return None


def consume_reservation(ctx, event, reservations, credits, consumed):
    """Y07.5: an admitted order of the named group consumes one credit unit."""
    group = service_group_of(ctx, event['box_id'])
    if group == ctx['marker']:
        return
    for reservation_id in sorted(reservations):
        reservation = reservations[reservation_id]
        if reservation['service_group'] != group or credits[reservation_id] <= 0:
            continue
        if not reservation_covers(reservation, event['to_block'], event['slot_code'],
                                  ctx['slots']):
            continue
        credits[reservation_id] -= 1
        consumed[reservation_id] += 1
        return


# --------------------------------------------------------------------------
# Y08  yard state through the shift
# --------------------------------------------------------------------------

def stage_y08_yard_state(ctx, out):
    yes = choose(ctx['vocab'][('container_state_history.psv', 'was_stacked')], 'yes')
    no = choose(ctx['vocab'][('container_state_history.psv', 'was_stacked')], 'no')
    positions = dict(ctx['opening_positions'])
    history = []
    moves_of_box = defaultdict(list)
    for event in ctx['events']:
        if event['outcome'] != ctx['admitted_outcome']:
            continue
        previous = positions.get(event['box_id'])
        block_id, row_no, tier_no = event['to_block'], int(event['to_row']), int(event['to_tier'])
        history.append({'box_id': event['box_id'], 'event_key': event['event_key'],
                        'from_block': previous[0] if previous else ctx['marker'],
                        'from_row': fmt_int(previous[1]) if previous else ctx['marker'],
                        'from_tier': fmt_int(previous[2]) if previous else ctx['marker'],
                        'to_block': block_id, 'to_row': row_no, 'to_tier': tier_no,
                        'was_stacked': yes if previous else no})
        positions[event['box_id']] = (block_id, row_no, tier_no)
        moves_of_box[event['box_id']].append(event)
    history.sort(key=lambda record: record['event_key'])
    ctx['state_history'] = history
    ctx['history_by_event'] = {record['event_key']: record for record in history}
    ctx['moves_of_box'] = moves_of_box
    ctx['closing_positions'] = positions

    header = ['box_id', 'event_key', 'from_block', 'from_row', 'from_tier', 'to_block',
              'to_row', 'to_tier', 'was_stacked']
    rows = [[h['box_id'], fmt_int(h['event_key']), h['from_block'], h['from_row'], h['from_tier'],
             h['to_block'], fmt_int(h['to_row']), fmt_int(h['to_tier']), h['was_stacked']]
            for h in history]
    write_delimited(os.path.join(out, 'container_state_history.psv'), header, rows, '|')

    states = ctx['vocab'][('container_state_final.csv', 'state')]
    stacked_state = choose(states, 'stacked')
    off_state = choose(states, 'off_yard')
    final = []
    for box_id in sorted(ctx['box']):
        position = positions.get(box_id)
        final.append({'box_id': box_id,
                      'block_id': position[0] if position else ctx['marker'],
                      'row_no': position[1] if position else 0,
                      'tier_no': position[2] if position else 0,
                      'moves_applied': len(moves_of_box.get(box_id, [])),
                      'state': stacked_state if position else off_state})
    ctx['final_state'] = {f['box_id']: f for f in final}
    ctx['counts']['boxes_on_yard'] = sum(1 for f in final if f['state'] == stacked_state)
    header = ['box_id', 'block_id', 'row_no', 'tier_no', 'moves_applied', 'state']
    rows = [[f['box_id'], f['block_id'], fmt_int(f['row_no']), fmt_int(f['tier_no']),
             fmt_int(f['moves_applied']), f['state']] for f in final]
    write_delimited(os.path.join(out, 'container_state_final.csv'), header, rows, ',')

    closing = defaultdict(int)
    for _box_id, position in positions.items():
        closing[position[0]] += 1
    ctx['closing_count'] = closing
    header = ['block_id', 'zone', 'slot_capacity', 'opening_boxes', 'closing_boxes',
              'closing_free']
    rows = []
    for block_id in sorted(ctx['geometry']):
        g = ctx['geometry'][block_id]
        opening = ctx['opening_count'].get(block_id, 0)
        boxes = closing.get(block_id, 0)
        rows.append([block_id, g['zone'], fmt_int(g['slot_capacity']), fmt_int(opening),
                     fmt_int(boxes), fmt_int(g['slot_capacity'] - boxes)])
    write_delimited(os.path.join(out, 'yard_occupancy.psv'), header, rows, '|')


# --------------------------------------------------------------------------
# Y09  planned against physical
# --------------------------------------------------------------------------

def stage_y09_movement_reconciliation(ctx, out):
    states = ctx['vocab'][('movement_accounting.jsonl', 'movement_state')]
    state_confirmed = choose(states, 'confirmed')
    state_aborted = choose(states, 'aborted')
    state_unconfirmed = choose(states, 'unconfirmed')
    state_contradicted = choose(states, 'contradicted')
    state_set_aside = choose(states, 'set_aside')
    ctx['state_confirmed'] = state_confirmed
    by_order = defaultdict(list)
    loose = []
    for confirmation in ctx['confirmations']:
        if not confirmation.get('order_id'):
            loose.append(confirmation)
            continue
        by_order[confirmation['order_id']].append(confirmation)
    for order_id in by_order:
        by_order[order_id].sort(key=lambda c: (c['confirmed_min'], c['confirm_id']))
    ctx['loose_confirmations'] = sorted(loose, key=lambda c: c['confirm_id'])
    records = []
    tally = defaultdict(int)
    for event in ctx['events']:
        confirmations = by_order.get(event['order_id'])
        confirmation = confirmations[0] if confirmations else None
        if event['outcome'] == ctx['admitted_outcome']:
            if confirmation is None:
                state = state_unconfirmed
            elif confirmation['confirm_state'] == 'landed':
                state = state_confirmed
            else:
                state = state_aborted
        elif confirmation is not None and confirmation['confirm_state'] == 'landed':
            state = state_contradicted
        else:
            state = state_set_aside
        event['movement_state'] = state
        event['confirmation'] = confirmation
        tally[state] += 1
        records.append({'event_key': event['event_key'], 'order_id': event['order_id'],
                        'box_id': event['box_id'], 'planned_outcome': event['outcome'],
                        'confirm_id': (confirmation['confirm_id'] if confirmation
                                       else ctx['marker']),
                        'confirmed_min': confirmation['confirmed_min'] if confirmation else 0,
                        'movement_state': state})
    ctx['movement_tally'] = tally
    ctx['movement_states_present'] = sorted(tally)
    ctx['counts']['confirmed_moves'] = tally.get(state_confirmed, 0)
    ctx['counts']['contradicted_moves'] = tally.get(state_contradicted, 0)
    ctx['counts']['loose_confirmations'] = len(ctx['loose_confirmations'])
    write_jsonl(os.path.join(out, 'movement_accounting.jsonl'), records)


# --------------------------------------------------------------------------
# Y10  rehandles and equipment
# --------------------------------------------------------------------------

def stage_y10_rehandle_and_equipment(ctx, out):
    ladder = sorted(ctx['surcharge_ladder'])
    stacked = choose(ctx['vocab'][('container_state_history.psv', 'was_stacked')], 'yes')

    def surcharge(depth):
        rungs = [cents for tier, cents in ladder if tier <= depth]
        return rungs[-1] if rungs else 0

    ledger = []
    rehandle_moves = 0
    assessed_cents = 0
    for box_id in sorted(ctx['moves_of_box']):
        moves = ctx['moves_of_box'][box_id]
        depths = []
        for event in sorted(moves, key=lambda e: e['event_key']):
            record = ctx['history_by_event'][event['event_key']]
            if record['was_stacked'] == stacked:
                depths.append(int(record['from_tier']))
        surcharge_cents = sum(surcharge(depth) for depth in depths)
        charge = len(moves) * ctx['base_move_charge'] + surcharge_cents
        rehandle_moves += len(depths)
        assessed_cents += charge
        ledger.append({'box_id': box_id, 'moves': len(moves), 'rehandles': len(depths),
                       'tier_depths': depths, 'surcharge_cents': surcharge_cents,
                       'charge_cents': charge})
    ctx['rehandle_ledger'] = {entry['box_id']: entry for entry in ledger}
    ctx['counts']['rehandle_moves'] = rehandle_moves
    ctx['counts']['assessed_cents'] = assessed_cents
    write_jsonl(os.path.join(out, 'rehandle_ledger.jsonl'), ledger)

    codes = ctx['vocab'][('equipment_exceptions.tsv', 'reason_code')]
    unknown_code = choose(codes, 'unknown')
    beyond_code = choose(codes, 'beyond')
    allowances, base_minutes, classes = {}, {}, {}
    for equipment_id, row in ctx['equipment'].items():
        allowances[equipment_id] = int(row['move_limit'])
        base_minutes[equipment_id] = int(row['base_minutes'])
        classes[equipment_id] = row['equipment_class']
    used = {equipment_id: 0 for equipment_id in allowances}
    exceptions = []
    for event in ctx['events']:
        if event.get('movement_state') != ctx['state_confirmed']:
            continue
        equipment_id = event['confirmation']['equipment_id']
        if equipment_id not in allowances:
            exceptions.append({'event_key': event['event_key'], 'order_id': event['order_id'],
                               'equipment_id': equipment_id, 'reason_code': unknown_code})
            continue
        if used[equipment_id] >= allowances[equipment_id]:
            exceptions.append({'event_key': event['event_key'], 'order_id': event['order_id'],
                               'equipment_id': equipment_id, 'reason_code': beyond_code})
            continue
        used[equipment_id] += 1
    ctx['counts']['equipment_exceptions'] = len(exceptions)
    header = ['event_key', 'order_id', 'equipment_id', 'reason_code']
    rows = [[fmt_int(e['event_key']), e['order_id'], e['equipment_id'], e['reason_code']]
            for e in exceptions]
    write_delimited(os.path.join(out, 'equipment_exceptions.tsv'), header, rows, '\t')

    yes = choose(ctx['vocab'][('equipment_usage.csv', 'within_allowance')], 'yes')
    header = ['equipment_id', 'equipment_class', 'allowance', 'used', 'minutes',
              'within_allowance']
    rows = []
    for equipment_id in sorted(allowances):
        rows.append([equipment_id, classes[equipment_id], fmt_int(allowances[equipment_id]),
                     fmt_int(used[equipment_id]),
                     fmt_int(used[equipment_id] * base_minutes[equipment_id]), yes])
    write_delimited(os.path.join(out, 'equipment_usage.csv'), header, rows, ',')


# --------------------------------------------------------------------------
# Y11  block capacity state
# --------------------------------------------------------------------------

def stage_y11_block_capacity(ctx, out):
    admission = ctx['admission']
    slots = ctx['slots']
    rows = []
    for block_id in sorted(ctx['geometry']):
        capacity = ctx['geometry'][block_id]['slot_capacity']
        for slot_code in slots:
            sealed, in_service = ctx['grid'].get((slot_code, block_id), ('no', 'yes'))
            occupied = admission['per_slot_count'].get(slot_code, {}).get(block_id, 0)
            if sealed == 'yes' or in_service != 'yes' or capacity <= 0:
                unavailable, reserved, available = capacity, 0, 0
            else:
                free = capacity - occupied
                credit = 0
                for reservation_id in sorted(admission['reservations']):
                    reservation = admission['reservations'][reservation_id]
                    standing = admission['per_slot_credit'].get(slot_code, {}).get(
                        reservation_id, 0)
                    if standing <= 0:
                        continue
                    if not reservation_covers(reservation, block_id, slot_code, slots):
                        continue
                    credit += standing
                reserved = max(0, min(credit, free))
                unavailable = 0
                available = max(0, free - reserved)
            rows.append([block_id, slot_code, fmt_int(capacity), fmt_int(occupied),
                         fmt_int(reserved), fmt_int(unavailable), fmt_int(available)])
    header = ['block_id', 'slot_code', 'slot_capacity', 'occupied', 'reserved', 'unavailable',
              'available']
    write_delimited(os.path.join(out, 'yard_capacity.csv'), header, rows, ',')

    header = ['block_id', 'slot_capacity', 'closing_boxes', 'utilisation_ratio']
    rows = []
    for block_id in sorted(ctx['geometry']):
        capacity = ctx['geometry'][block_id]['slot_capacity']
        closing = ctx['closing_count'].get(block_id, 0)
        ratio = Fraction(closing, capacity) if capacity else Fraction(0)
        rows.append([block_id, fmt_int(capacity), fmt_int(closing), fmt_ratio(ratio)])
    write_delimited(os.path.join(out, 'block_utilization.csv'), header, rows, ',')

    header = ['reservation_id', 'block_id', 'service_group', 'first_slot', 'last_slot',
              'asked', 'withheld', 'consumed', 'unmet']
    rows = []
    for reservation_id in sorted(admission['reservations']):
        r = admission['reservations'][reservation_id]
        rows.append([reservation_id, r['block_id'], r['service_group'], r['first_slot'],
                     r['last_slot'], fmt_int(r['asked']), fmt_int(r['credit']),
                     fmt_int(admission['consumed'][reservation_id]), fmt_int(r['unmet'])])
    write_delimited(os.path.join(out, 'yard_reservations.psv'), header, rows, '|')

    header = ['slot_code', 'events', 'admitted', 'set_aside', 'confirmed']
    tally = {slot_code: defaultdict(int) for slot_code in slots + [ctx['marker']]}
    for event in ctx['events']:
        slot_code = event['slot_code'] if event['slot_code'] in slots else ctx['marker']
        bucket = tally[slot_code]
        bucket['events'] += 1
        bucket[event['outcome']] += 1
        if event.get('movement_state') == ctx['state_confirmed']:
            bucket['confirmed'] += 1
    rows = []
    for slot_code in slots + [ctx['marker']]:
        bucket = tally[slot_code]
        rows.append([slot_code, fmt_int(bucket['events']),
                     fmt_int(bucket[ctx['admitted_outcome']]),
                     fmt_int(bucket[ctx['set_aside_outcome']]),
                     fmt_int(bucket['confirmed'])])
    write_delimited(os.path.join(out, 'slot_accounting.csv'), header, rows, ',')


# --------------------------------------------------------------------------
# Y12  cutoff joined to yard state
# --------------------------------------------------------------------------

def eligibility_clauses(ctx):
    """Y12.4: the reasons in the order the rule puts them, with their codes."""
    vocabulary = set(ctx['vocab'][('load_eligibility.csv', 'reason_code')])
    text = read_text(os.path.join(ctx['data_dir'], 'spec_stage_y12_load_eligibility.md'))
    rule = re.search(r'RULE Y12\.4(.*?)(?:RULE Y12\.5|$)', text, re.S)
    body = rule.group(1) if rule else ''
    body = body.split('A box none of these catches')[0]
    clauses = []
    for chunk in body.split(';'):
        codes = [code for code in re.findall(r'\b([A-Z][A-Z_]{2,})\b', chunk)
                 if code in vocabulary]
        if not codes:
            continue
        lowered = chunk.lower()
        if 'outside' in lowered:
            kind = 'after_cutoff'
        elif 'obligation holds' in lowered or 'holds it' in lowered:
            kind = 'held'
        elif 'call' in lowered:
            kind = 'no_vessel'
        elif 'obligation' in lowered:
            kind = 'no_obligation'
        elif 'yard' in lowered:
            kind = 'off_yard'
        elif 'cutoff' in lowered:
            kind = 'no_cutoff'
        else:
            continue
        if kind not in [existing for existing, _code in clauses]:
            clauses.append((kind, codes[-1]))
    return clauses


def stage_y12_load_eligibility(ctx, out):
    codes = dict(eligibility_clauses(ctx))
    vocabulary = ctx['vocab'][('load_eligibility.csv', 'reason_code')]
    ok_code = [code for code in vocabulary if code not in codes.values()]
    ok_code = ok_code[0] if ok_code else ctx['marker']
    ctx['eligibility_codes'] = codes

    cutoff = {}
    for row in ctx['cutoff_board']:
        if row['shift_id'] != ctx['shift_id'] or row['superseded'] == 'yes':
            continue
        vessel_id = row['vessel_id']
        if vessel_id not in cutoff or int(row['notice_seq']) > int(cutoff[vessel_id]['notice_seq']):
            cutoff[vessel_id] = row
    ctx['cutoff_in_force'] = cutoff

    obligations = {}
    for row in ctx['stowage']:
        obligations[(row['vessel_id'], row['box_id'])] = row

    waived_orders = set()
    for row in ctx['exceptions']:
        if row['shift_id'] != ctx['shift_id'] or row['withdrawn'] == 'yes':
            continue
        if ctx['exception_rungs'].get(row['exception_kind']) is not None:
            continue
        if row['target_kind'] == 'order':
            waived_orders.add(row['target_id'])

    yes = choose(ctx['vocab'][('load_eligibility.csv', 'eligible')], 'yes')
    no = choose(ctx['vocab'][('load_eligibility.csv', 'eligible')], 'no')
    verdicts = []
    for box_id in sorted(ctx['box']):
        vessel_id = ctx['box'][box_id]['vessel_id']
        moves = sorted(ctx['moves_of_box'].get(box_id, []), key=lambda e: e['event_key'])
        ready = moves[-1]['raised_min'] if moves else 0
        reason = None
        if vessel_id not in ctx['obligation']:
            reason = codes['no_vessel']
        else:
            obligation = obligations.get((vessel_id, box_id))
            if obligation is None:
                reason = codes['no_obligation']
            elif obligation['hold_flag'] == 'yes':
                reason = codes['held']
            elif box_id not in ctx['closing_positions']:
                reason = codes['off_yard']
            else:
                notice = cutoff.get(vessel_id)
                if notice is None:
                    reason = codes['no_cutoff']
                else:
                    if not (moves and moves[-1]['order_id'] in waived_orders):
                        if ready > int(notice['cutoff_min']):
                            reason = codes['after_cutoff']
        verdicts.append({'box_id': box_id, 'vessel_id': vessel_id,
                         'eligible': yes if reason is None else no,
                         'reason_code': reason if reason is not None else ok_code,
                         'ready_min': ready})
    ctx['verdicts'] = {v['box_id']: v for v in verdicts}
    eligible_boxes = sorted(v['box_id'] for v in verdicts if v['eligible'] == yes)
    ctx['eligible_boxes'] = eligible_boxes
    ctx['counts']['eligible_boxes'] = len(eligible_boxes)
    header = ['box_id', 'vessel_id', 'eligible', 'reason_code', 'ready_min']
    rows = [[v['box_id'], v['vessel_id'], v['eligible'], v['reason_code'], fmt_int(v['ready_min'])]
            for v in verdicts]
    write_delimited(os.path.join(out, 'load_eligibility.csv'), header, rows, ',')

    status = []
    for vessel_id in sorted({v['vessel_id'] for v in verdicts}):
        boxes = [v for v in verdicts if v['vessel_id'] == vessel_id]
        outside = sum(1 for v in boxes if v['reason_code'] == codes['after_cutoff'])
        notice = cutoff.get(vessel_id)
        status.append({'vessel_id': vessel_id,
                       'notice_id': notice['notice_id'] if notice else ctx['marker'],
                       'cutoff_min': int(notice['cutoff_min']) if notice else 0,
                       'boxes_total': len(boxes), 'boxes_inside': len(boxes) - outside,
                       'boxes_outside': outside})
    header = ['vessel_id', 'notice_id', 'cutoff_min', 'boxes_total', 'boxes_inside',
              'boxes_outside']
    rows = [[s['vessel_id'], s['notice_id'], fmt_int(s['cutoff_min']), fmt_int(s['boxes_total']),
             fmt_int(s['boxes_inside']), fmt_int(s['boxes_outside'])] for s in status]
    write_delimited(os.path.join(out, 'vessel_cutoff_status.csv'), header, rows, ',')

    manifest = []
    for box_id in eligible_boxes:
        vessel_id = ctx['box'][box_id]['vessel_id']
        obligation = obligations[(vessel_id, box_id)]
        manifest.append({'vessel_id': vessel_id, 'box_id': box_id,
                         'class_rank': ctx['class_rank'][ctx['box'][box_id]['box_class']],
                         'stow_sequence': obligation['stow_sequence'],
                         'bay_no': obligation['bay_no'],
                         'teu_factor': ctx['dimensions'][box_id]['teu_factor'],
                         'mass_kg': ctx['dimensions'][box_id]['mass_kg']})
    ctx['manifest'] = manifest
    header = ['vessel_id', 'box_id', 'class_rank', 'stow_sequence', 'bay_no', 'teu_factor',
              'mass_kg']
    rows = [[m['vessel_id'], m['box_id'], fmt_int(m['class_rank']), m['stow_sequence'],
             m['bay_no'], fmt_int(m['teu_factor']), fmt_int(m['mass_kg'])]
            for m in sorted(manifest, key=lambda m: (m['vessel_id'], m['box_id']))]
    write_delimited(os.path.join(out, 'vessel_container_manifest.psv'), header, rows, '|')


# --------------------------------------------------------------------------
# Y13  the quay ration and the load
# --------------------------------------------------------------------------

def stage_y13_quay_ration(ctx, out):
    filed = {}
    for row in ctx['demand']:
        if row['return_state'] != 'filed':
            continue
        key = (row['vessel_id'], row['slot_code'])
        seq = int(row['revision_seq'])
        if key not in filed or seq > filed[key][0]:
            filed[key] = (seq, int(row['declared_minutes']))
    windows = {}
    for row in ctx['berth_windows']:
        if row['draft'] == 'yes':
            continue
        key = (row['berth_id'], row['slot_code'])
        seq = int(row['revision_seq'])
        if key not in windows or seq > int(windows[key]['revision_seq']):
            windows[key] = row

    trace, pairings = [], []
    share_of = defaultdict(int)
    for slot_code in ctx['slots']:
        for berth_id in sorted(ctx['reporting_berths']):
            members = [vessel_id for vessel_id in sorted(ctx['obligation'])
                       if ctx['obligation'][vessel_id]['berth_id'] == berth_id
                       and (vessel_id, slot_code) in filed]
            window = windows.get((berth_id, slot_code))
            crewed = ctx['gang_roster'].get((berth_id, slot_code), 0)
            pool = min(int(window['crane_minutes']) if window else 0, crewed)
            declared = {vessel_id: filed[(vessel_id, slot_code)][1] for vessel_id in members}
            ceilings = {vessel_id: ctx['vessel_slot_ceiling'].get((vessel_id, slot_code), 0)
                        for vessel_id in members}
            shares, passes = run_ration(ctx, members, pool, declared, ceilings)
            for pass_no, unplaced, standing in passes:
                trace.append({'slot_code': slot_code, 'berth_id': berth_id,
                              'pass_no': pass_no, 'pool_minutes': pool,
                              'unplaced_minutes': round_half_up(unplaced),
                              'shares': [{'vessel_id': v, 'share_minutes': standing[v]}
                                         for v in members]})
            for vessel_id in members:
                share_of[vessel_id] += shares[vessel_id]
            pairings.append({'slot_code': slot_code, 'berth_id': berth_id,
                             'pool_minutes': pool, 'declared_minutes': sum(declared.values()),
                             'crewed_minutes': crewed, 'vessel_count': len(members),
                             'rationed_minutes': sum(shares.values())})
    ctx['pairings'] = pairings
    ctx['share_of'] = share_of
    write_jsonl(os.path.join(out, 'ration_trace.jsonl'), trace)

    quay_units = sorted(equipment_id for equipment_id, row in ctx['equipment'].items()
                        if row['equipment_class'] == 'quay_crane')
    minutes_per_teu = int(ctx['equipment'][quay_units[0]]['base_minutes']) if quay_units else 0
    ctx['minutes_per_teu'] = minutes_per_teu

    loadable = defaultdict(list)
    for entry in ctx['manifest']:
        loadable[entry['vessel_id']].append(entry)
    vessels = []
    for vessel_id in sorted(ctx['obligation']):
        entries = sorted(loadable.get(vessel_id, []), key=lambda e: load_key(e, ctx['stowage_keys']))
        share = share_of.get(vessel_id, 0)
        loaded, deferred = [], []
        running, stopped = 0, False
        for entry in entries:
            minutes = entry['teu_factor'] * minutes_per_teu
            if stopped or running + minutes > share:
                stopped = True
                deferred.append((entry, minutes))
            else:
                running += minutes
                loaded.append((entry, minutes))
        vessels.append({'vessel_id': vessel_id,
                        'berth_id': ctx['obligation'][vessel_id]['berth_id'],
                        'share_minutes': share, 'eligible_count': len(entries),
                        'loaded': loaded, 'deferred': deferred, 'loaded_minutes': running})
    ctx['load'] = vessels

    write_json(os.path.join(out, 'load_sequence_ledger.json'), {
        'shift_id': ctx['shift_id'], 'minutes_per_teu': minutes_per_teu,
        'stowage_keys': list(ctx['stowage_keys']),
        'vessels': [{'vessel_id': v['vessel_id'], 'share_minutes': v['share_minutes'],
                     'eligible_count': v['eligible_count'], 'loaded_count': len(v['loaded']),
                     'deferred_count': len(v['deferred']),
                     'loaded_minutes': v['loaded_minutes'],
                     'unused_minutes': v['share_minutes'] - v['loaded_minutes']}
                    for v in vessels]})

    write_json(os.path.join(out, 'departure_ledger.json'), {
        'shift_id': ctx['shift_id'],
        'vessels': [{'vessel_id': v['vessel_id'], 'berth_id': v['berth_id'],
                     'share_minutes': v['share_minutes'],
                     'loaded_minutes': v['loaded_minutes'],
                     'unused_minutes': v['share_minutes'] - v['loaded_minutes'],
                     'boxes': [{'load_position': position, 'box_id': entry['box_id'],
                                'load_minutes': minutes}
                               for position, (entry, minutes) in enumerate(v['loaded'], 1)]}
                    for v in vessels]})

    ladder = sorted(ctx['surcharge_ladder'])
    last_rung = ladder[-1][1] if ladder else 0
    header = ['vessel_id', 'box_id', 'load_minutes', 'assessed_cents', 'published_cents']
    rows = []
    deferred_boxes = []
    for vessel in vessels:
        for entry, minutes in sorted(vessel['deferred'], key=lambda item: item[0]['box_id']):
            assessed = ctx['rehandle_ledger'].get(entry['box_id'], {}).get('charge_cents', 0)
            published = assessed + last_rung
            rows.append([vessel['vessel_id'], entry['box_id'], fmt_int(minutes),
                         fmt_int(assessed), fmt_int(published)])
            deferred_boxes.append((vessel['vessel_id'], entry['box_id'], assessed, published))
    write_delimited(os.path.join(out, 'deferred_containers.tsv'), header, rows, '\t')
    ctx['deferred_boxes'] = deferred_boxes
    ctx['counts']['deferred_boxes'] = len(deferred_boxes)
    ctx['counts']['loaded_boxes'] = sum(len(v['loaded']) for v in vessels)
    ctx['counts']['loaded_minutes'] = sum(v['loaded_minutes'] for v in vessels)
    ctx['counts']['rationed_minutes'] = sum(v['share_minutes'] for v in vessels)
    ctx['counts']['published_cents'] = sum(entry[3] for entry in deferred_boxes)


def load_key(entry, keys):
    """Y13.8: the keys the directive names, read left to right, each ascending."""
    values = []
    for key in keys:
        value = entry.get(key)
        text = '' if value is None else str(value)
        if re.match(r'^-?\d+$', text):
            values.append((0, int(text), ''))
        elif text:
            values.append((2, 0, text))
        else:
            values.append((1, 0, ''))
    return values


def run_ration(ctx, members, pool, declared, ceilings):
    """Y13.5: the damped iterate, run exactly as many passes as the budget allows."""
    shares = {vessel_id: 0 for vessel_id in members}
    passes = []
    cells = {vessel_id: (ctx['obligation'][vessel_id]['berth_id'],
                         ctx['obligation'][vessel_id]['service_group'])
             for vessel_id in members}
    for pass_no in range(1, ctx['pass_budget'] + 1):
        needs = {v: max(0, declared[v] - shares[v]) for v in members}
        total_need = sum(needs.values())
        unallocated = pool - sum(shares.values())
        unplaced = Fraction(0)
        if total_need == 0 or unallocated <= 0:
            passes.append((pass_no, unplaced, dict(shares)))
            break
        targets = {v: Fraction(shares[v]) + Fraction(unallocated) * Fraction(needs[v])
                   / Fraction(total_need) for v in members}
        capped = {v: min(targets[v], Fraction(ceilings[v])) for v in members}
        freed = defaultdict(Fraction)
        for v in members:
            freed[cells[v]] += targets[v] - capped[v]
        received = {v: Fraction(0) for v in members}
        for cell in sorted(freed):
            amount = freed[cell]
            if amount <= 0:
                continue
            receivers = [v for v in members
                         if cells[v] == cell and targets[v] <= Fraction(ceilings[v])]
            receiver_need = sum(Fraction(needs[v]) for v in receivers)
            if receiver_need > 0:
                for v in receivers:
                    received[v] = amount * Fraction(needs[v]) / receiver_need
            else:
                unplaced += amount
        aims = {v: min(capped[v] + received[v], Fraction(ceilings[v])) for v in members}
        for v in sorted(members):
            standing = shares[v]
            damped = Fraction(standing) + ctx['damping'] * (aims[v] - Fraction(standing))
            moved = round_half_up(damped)
            aim_rounded = round_half_up(aims[v])
            if moved == standing and aim_rounded != standing:
                if aim_rounded > standing:
                    moved = min(standing + ctx['minimum_step'], aim_rounded)
                else:
                    moved = max(standing - ctx['minimum_step'], aim_rounded)
            shares[v] = moved
        passes.append((pass_no, unplaced, dict(shares)))
    return shares, passes


# --------------------------------------------------------------------------
# Y14  terminal accounts and publication
# --------------------------------------------------------------------------

def stage_y14_terminal_accounts(ctx, out):
    counts = ctx['counts']
    header = ['measure', 'value']
    rows = [[measure, fmt_int(counts.get(measure, 0))] for measure in sorted(ctx['measures'])]
    write_delimited(os.path.join(out, 'terminal_reconciliation.csv'), header, rows, ',')

    tally = defaultdict(lambda: [0, 0])
    for row in ctx['exceptions']:
        if row['shift_id'] != ctx['shift_id']:
            continue
        bucket = tally[row['exception_kind']]
        bucket[1 if row['withdrawn'] == 'yes' else 0] += 1
    header = ['exception_kind', 'granted', 'withdrawn']
    rows = [[kind, fmt_int(tally[kind][0]), fmt_int(tally[kind][1])] for kind in sorted(tally)]
    write_delimited(os.path.join(out, 'exception_summary.tsv'), header, rows, '\t')

    yes = choose(ctx['vocab'][('load_eligibility.csv', 'eligible')], 'yes')
    loaded_boxes = {entry['box_id'] for vessel in ctx['load'] for entry, _m in vessel['loaded']}
    deferred_boxes = {entry['box_id'] for vessel in ctx['load']
                      for entry, _m in vessel['deferred']}
    eligible_boxes = set(ctx['eligible_boxes'])
    stacked_state = choose(ctx['vocab'][('container_state_final.csv', 'state')], 'stacked')
    moved_boxes = set(ctx['moves_of_box'])
    on_yard = {box_id for box_id, record in ctx['final_state'].items()
               if record['state'] == stacked_state}
    republished = {box_id for _vessel, box_id, _a, _p in ctx['deferred_boxes']}
    answers = {
        'loaded_and_deferred_partition_eligible':
            ((loaded_boxes | deferred_boxes) == eligible_boxes
             and not (loaded_boxes & deferred_boxes)),
        'moved_boxes_all_on_yard': moved_boxes <= on_yard,
        'decision_count_matches_events': len(ctx['events']) == counts['canonical_events'],
        'republished_covers_deferred': republished == deferred_boxes,
    }
    identities = {name: (yes if answers[name] else 'no') for name in ctx['identity_names']}
    ctx['identities'] = identities

    lines = ['<?xml version="1.0" encoding="utf-8"?>', '<vessel_reconciliation>',
             '  <shift_id>%s</shift_id>' % xml_escape(ctx['shift_id']), '  <vessels>']
    for vessel in ctx['load']:
        lines.append('    <vessel id="%s">' % xml_escape(vessel['vessel_id']))
        lines.append('      <berth_id>%s</berth_id>' % xml_escape(vessel['berth_id']))
        lines.append('      <eligible_count>%d</eligible_count>' % vessel['eligible_count'])
        lines.append('      <loaded_count>%d</loaded_count>' % len(vessel['loaded']))
        lines.append('      <deferred_count>%d</deferred_count>' % len(vessel['deferred']))
        lines.append('      <share_minutes>%d</share_minutes>' % vessel['share_minutes'])
        lines.append('    </vessel>')
    lines.append('  </vessels>')
    for name in ctx['identity_names']:
        lines.append('  <identity name="%s">%s</identity>'
                     % (xml_escape(name), xml_escape(identities[name])))
    lines.append('</vessel_reconciliation>')
    write_text(os.path.join(out, 'vessel_reconciliation.xml'), '\n'.join(lines) + '\n')

    lines = ['# The audit trail of one shift.', '[shift]',
             'shift_id = %s' % ctx['shift_id'],
             'live_sheet_name = %s' % ctx['live_sheet_name'],
             'reference = %s' % ctx['reference'], '', '[counts]']
    for measure in sorted(ctx['measures']):
        lines.append('%s = %s' % (measure, fmt_int(counts.get(measure, 0))))
    lines.append('')
    lines.append('[ladder]')
    for rung in ctx['ladder']:
        lines.append('%s = %s' % (rung['code'], fmt_int(ctx['ladder_tally'].get(rung['code'], 0))))
    lines.append('')
    lines.append('[movement]')
    for state in ctx['movement_states_present']:
        lines.append('%s = %s' % (state, fmt_int(ctx['movement_tally'].get(state, 0))))
    write_text(os.path.join(out, 'audit_trail.conf'), '\n'.join(lines) + '\n')

    for berth_id in sorted(ctx['reporting_berths']):
        berth_vessels = sorted(v for v in ctx['obligation']
                               if ctx['obligation'][v]['berth_id'] == berth_id)
        pairings = [p for p in ctx['pairings'] if p['berth_id'] == berth_id]
        write_json(os.path.join(out, 'berth_report_%s.json' % berth_id), {
            'shift_id': ctx['shift_id'], 'berth_id': berth_id,
            'vessel_count': len(berth_vessels), 'vessels': berth_vessels,
            'pool_minutes': sum(p['pool_minutes'] for p in pairings),
            'rationed_minutes': sum(p['rationed_minutes'] for p in pairings),
            'pairings': [{'slot_code': p['slot_code'], 'berth_id': p['berth_id'],
                          'pool_minutes': p['pool_minutes'],
                          'declared_minutes': p['declared_minutes'],
                          'crewed_minutes': p['crewed_minutes'],
                          'vessel_count': p['vessel_count'],
                          'rationed_minutes': p['rationed_minutes']} for p in pairings]})

    lines = ['# Daily operational summary', '',
             'shift %s at reference %s' % (ctx['shift_id'], ctx['reference']), '']
    for measure in sorted(ctx['measures']):
        lines.append('- %s: %s' % (measure, fmt_int(counts.get(measure, 0))))
    lines.append('')
    lines.append('## Ladder')
    lines.append('')
    for rung in ctx['ladder']:
        lines.append('- %s: %s' % (rung['code'],
                                   fmt_int(ctx['ladder_tally'].get(rung['code'], 0))))
    lines.append('')
    lines.append('## Identity checks')
    lines.append('')
    for name in ctx['identity_names']:
        lines.append('- %s: %s' % (name, identities[name]))
    write_text(os.path.join(out, 'daily_operational_summary.md'), '\n'.join(lines) + '\n')

    write_json(os.path.join(out, 'final_control_totals.json'), {
        'shift_id': ctx['shift_id'], 'live_sheet_name': ctx['live_sheet_name'],
        'minutes_per_teu': ctx['minutes_per_teu'],
        'totals': {measure: counts.get(measure, 0) for measure in sorted(ctx['measures'])},
        'identities': identities})


def write_publication_manifest(ctx, out):
    """Y14.4: the digests, taken last over every document beside the manifest."""
    manifest = 'publication_manifest.json'
    digests, sizes = {}, {}
    for name in ctx['artifact_order']:
        if name == manifest:
            continue
        with open(os.path.join(out, name), 'rb') as handle:
            payload = handle.read()
        digests[name] = hashlib.sha256(payload).hexdigest()
        sizes[name] = len(payload)

    def block(names):
        return ''.join('%s %s\n' % (name, digests[name]) for name in names)

    core = block([name for name in ctx['artifact_order'] if name in ctx['core_documents']])
    rest = block([name for name in ctx['artifact_order']
                  if name != manifest and name not in ctx['core_documents']])
    write_json(os.path.join(out, manifest), {
        'shift_id': ctx['shift_id'],
        'core_digest': hashlib.sha256(core.encode('utf-8')).hexdigest(),
        'publication_digest': hashlib.sha256(rest.encode('utf-8')).hexdigest(),
        'document_count': len(ctx['artifact_order']),
        'documents': [{'name': name, 'sha256': digests[name], 'bytes': sizes[name]}
                      for name in ctx['artifact_order'] if name != manifest]})


# --------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------

STAGES = [
    ('Y01', stage_y01_canonical_events),
    ('Y02', stage_y02_unit_normalisation),
    ('Y03', stage_y03_vessel_obligation),
    ('Y04', stage_y04_opening_yard),
    ('Y05', stage_y05_event_ordering),
    ('Y06', stage_y06_dependency_cycles),
    ('Y07', stage_y07_move_admission),
    ('Y08', stage_y08_yard_state),
    ('Y09', stage_y09_movement_reconciliation),
    ('Y10', stage_y10_rehandle_and_equipment),
    ('Y11', stage_y11_block_capacity),
    ('Y12', stage_y12_load_eligibility),
    ('Y13', stage_y13_quay_ration),
    ('Y14', stage_y14_terminal_accounts),
]


def main(argv=None):
    parser = argparse.ArgumentParser(description='recompute one shift of the terminal ledger')
    parser.add_argument('--data', required=True, help='the working papers of the shift')
    parser.add_argument('--out', required=True, help='the directory the publication is written to')
    args = parser.parse_args(argv)
    ctx = load_context(args.data)
    ctx['counts'] = {}
    os.makedirs(args.out, exist_ok=True)
    for _code, stage in STAGES:
        stage(ctx, args.out)
    write_publication_manifest(ctx, args.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
