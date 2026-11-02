#!/usr/bin/env python3
"""Reconcile the Caldermoor commitment closure for one extract directory.

Usage:  python3 reconcile.py DATA_DIR OUT_DIR

The extract directory is read only.  The closure is built in a staging
directory and published into the output directory once every deliverable is
complete, so an unfinished run leaves no partial file behind.
"""

import json
import os
import re
import shutil
import sys
import tempfile
import unicodedata
import xml.etree.ElementTree as ET
from collections import defaultdict, deque
from datetime import datetime, timedelta

# --------------------------------------------------------------------------
# Protocol constants

WINDOW_START_TEXT = '2032-03-01T00:00Z'
WINDOW_END_TEXT = '2032-12-01T00:00Z'
WINDOW_START = datetime(2032, 3, 1, 0, 0)
WINDOW_END = datetime(2032, 12, 1, 0, 0)
DAY_OFFSET_MINUTES = 240
EFFORT_FLOOR_MINUTES = 15
EFFORT_CEILING_MINUTES = 480
ALLOCATION_FLOOR_MINUTES = 15
WAIVER_ALLOWANCE = 4
ESCALATION_MONTH = '2032-11'
ESCALATION_MIN_DEPTH = 2
ESCALATION_MIN_DEBT = 4
RESERVE_PER_WAIT_MINUTES = 30
RESERVE_PER_WAIVED_PERIOD_MINUTES = 15

REASON_CODES = [
    'MALFORMED_ROW', 'FEED_RETIRED', 'OUT_OF_WINDOW', 'UNKNOWN_PRINCIPAL',
    'AMBIGUOUS_IDENTITY', 'UNKNOWN_PROJECT', 'NONPOSITIVE_EFFORT',
    'UNKNOWN_COMMITMENT', 'ILLEGAL_TRANSITION',
]
COMMITMENT_CLASSES = [
    'ACTIONABLE', 'BLOCKED', 'DEFERRED', 'SETTLED', 'UNRESOLVABLE', 'WITHDRAWN',
]
STATES = {'OPEN', 'SETTLED', 'DEFERRED', 'WITHDRAWN'}
SOURCE_RANKS = {
    'vault': 6, 'desk': 5, 'bridge': 4, 'partner': 3,
    'mirror': 2, 'import': 1, 'relay': 1, 'legacy': 0,
}
EFFORT_UNIT_FACTORS = {'minutes': 1, 'hours': 60, 'halfdays': 240}
LEGAL_TRANSITIONS = {
    ('OPEN', 'SETTLED'), ('OPEN', 'DEFERRED'), ('OPEN', 'WITHDRAWN'),
    ('DEFERRED', 'OPEN'), ('DEFERRED', 'WITHDRAWN'),
}
IDENTITY_NAMES = [
    'I1_row_partition', 'I2_class_partition', 'I3_actor_effort',
    'I4_project_effort', 'I5_closure_frontier',
]

AUDIT_FIGURES = [
    'rows_ingested', 'rows_rejected', 'rows_accepted', 'commitments_admitted',
    'class_actionable', 'class_blocked', 'class_deferred', 'class_settled',
    'class_unresolvable', 'class_withdrawn',
    'reject_ambiguous_identity', 'reject_feed_retired',
    'reject_illegal_transition', 'reject_malformed_row',
    'reject_nonpositive_effort', 'reject_out_of_window',
    'reject_unknown_commitment', 'reject_unknown_principal',
    'reject_unknown_project',
    'live_edges', 'dropped_edges', 'closure_pairs', 'blocked_commitments',
    'open_effort_minutes', 'allocated_minutes', 'escalated_commitments',
    'cadence_debt_total',
]
RECONCILIATION_FIGURES = [
    name for name in AUDIT_FIGURES
    if name != 'rows_accepted' and not name.startswith('reject_')
]

COMMITMENT_FIXED_COLUMNS = [
    ('assertion_id', 12), ('commitment_key', 12), ('obligor', 40),
    ('obligee', 40), ('project_ref', 10), ('due_at', 18), ('effort', 8),
    ('cadence_ref', 10), ('observed_at', 18),
]
STATE_FIXED_COLUMNS = [
    ('state_id', 12), ('commitment_key', 12), ('to_state', 12),
    ('observed_at', 18),
]

DELIVERABLES = [
    'reconcile.py',
    'normalized_assertions.jsonl',
    'rejects.csv',
    'alias_resolution.jsonl',
    'actor_roster.csv',
    'project_lineage.csv',
    'assertion_contests.csv',
    'commitment_ledger.jsonl',
    'state_resolution.csv',
    'live_edges.csv',
    'dropped_edges.csv',
    'blocking_closure.jsonl',
    'blocked_commitments.csv',
    'actionable_queue.tsv',
    'deferred_queue.psv',
    'withdrawn_register.csv',
    'unresolvable.jsonl',
    'cadence_debt.csv',
    'waiver_trace.jsonl',
    'attention_allocation.csv',
    'month_load_index.csv',
    'escalation_queue.csv',
    'actor_rollup.json',
    'project_rollup.json',
    'provenance_index.jsonl',
    'audit_totals.csv',
    'reconciliation.txt',
    'validation_report.json',
    'run_manifest.json',
]

EPOCH = datetime(1970, 1, 1)
INSTANT_RE = re.compile(r'^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})Z$')
KV_LINE_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*:( .*)?$')
XML_ELEMENT_RE = re.compile(r'<([A-Za-z_][A-Za-z0-9_.-]*)((?:\s+[^<>]*?)?)/>\s*$')
XML_ATTR_RE = re.compile(r'([A-Za-z_][A-Za-z0-9_.:-]*)\s*=\s*"([^"]*)"')
INTEGER_RE = re.compile(r'^-?\d+$')
UNSIGNED_RE = re.compile(r'^\d+$')


# --------------------------------------------------------------------------
# Small helpers

def parse_instant(text):
    """Return a naive UTC datetime for a protocol instant, else None."""
    if not isinstance(text, str):
        return None
    match = INSTANT_RE.match(text)
    if not match:
        return None
    year, month, day, hour, minute = (int(part) for part in match.groups())
    try:
        return datetime(year, month, day, hour, minute)
    except ValueError:
        return None


def instant_text(moment):
    return moment.strftime('%Y-%m-%dT%H:%MZ')


def commitment_day(moment):
    return (moment - timedelta(minutes=DAY_OFFSET_MINUTES)).strftime('%Y-%m-%d')


def fold(surface):
    """The comparison fold of the identity register, in its stated order."""
    text = unicodedata.normalize('NFC', surface)
    text = text.strip()
    text = text.casefold()
    text = ''.join(ch for ch in text if ch not in ".-_'")
    text = ' '.join(text.split())
    return text.strip()


def to_text(value):
    """Render a parsed JSON value the way the record layouts carry it."""
    if value is None:
        return 'null'
    if value is True:
        return 'true'
    if value is False:
        return 'false'
    return str(value)


def write_text(path, text):
    with open(path, 'w', encoding='utf-8', newline='\n') as handle:
        handle.write(text)


def jsonl_text(objects):
    """One JSON object per line, each line closed by a newline."""
    return ''.join(json.dumps(obj, sort_keys=True, separators=(',', ':'),
                              ensure_ascii=True) + '\n' for obj in objects)


def json_text(obj):
    return json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=True) + '\n'


def table_text(fields, rows, separator=','):
    lines = [separator.join(fields)]
    for row in rows:
        lines.append(separator.join(str(value) for value in row))
    return '\n'.join(lines) + '\n'


# --------------------------------------------------------------------------
# Record readers.  Each returns a list of (fields, malformed) in file order.


def _split_lines(text):
    if text.endswith('\n'):
        text = text[:-1]
    return text.split('\n')


def _read_file(path):
    with open(path, 'r', encoding='utf-8', newline='') as handle:
        return handle.read()


def read_delimited(path, separator):
    lines = _split_lines(_read_file(path))
    records = []
    if not lines:
        return records
    header = lines[0].split(separator)
    for line in lines[1:]:
        values = line.split(separator)
        malformed = len(values) != len(header)
        fields = {}
        for index, name in enumerate(header):
            fields[name] = values[index] if index < len(values) else ''
        records.append((fields, malformed))
    return records


def read_jsonl(path):
    records = []
    for line in _split_lines(_read_file(path)):
        try:
            obj = json.loads(line)
        except ValueError:
            records.append(({}, True))
            continue
        if not isinstance(obj, dict):
            records.append(({}, True))
            continue
        records.append(({key: to_text(value) for key, value in obj.items()},
                        False))
    return records


def read_kv(path):
    text = _read_file(path)
    if text.endswith('\n'):
        text = text[:-1]
    records = []
    for block in text.split('\n\n'):
        if block.strip() == '':
            continue
        fields = {}
        malformed = False
        for line in block.split('\n'):
            if line == '':
                continue
            if not KV_LINE_RE.match(line):
                malformed = True
                continue
            name, _, value = line.partition(':')
            value = value[1:] if value.startswith(' ') else value
            fields[name] = value
        records.append((fields, malformed))
    return records


def read_rec(path):
    records = []
    for line in _split_lines(_read_file(path)):
        fields = {}
        malformed = False
        for segment in line.split(';'):
            if '=' not in segment:
                malformed = True
                continue
            name, _, value = segment.partition('=')
            fields[name] = value
        records.append((fields, malformed))
    return records


def read_fixed(path, columns):
    records = []
    for line in _split_lines(_read_file(path)):
        fields = {}
        position = 0
        for name, width in columns:
            chunk = line[position:position + width]
            fields[name] = chunk.rstrip(' ')
            position += width
        records.append((fields, False))
    return records


def read_xml(path):
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return _read_xml_lines(path)
    return [({key: to_text(value) for key, value in child.attrib.items()}, False)
            for child in root]


def _read_xml_lines(path):
    """Fallback when the wrapping element is broken: one element per line."""
    records = []
    for line in _split_lines(_read_file(path)):
        stripped = line.strip()
        if stripped == '' or stripped.startswith('<?') or stripped.startswith('<!--'):
            continue
        if not stripped.startswith('<'):
            records.append(({}, True))
            continue
        match = XML_ELEMENT_RE.match(stripped)
        if not match:
            records.append(({}, True))
            continue
        body = stripped[match.end(1):]
        fields = dict(XML_ATTR_RE.findall(body))
        records.append((_unescape(fields), False))
    return records


def _unescape(fields):
    for key, value in list(fields.items()):
        value = (value.replace('&lt;', '<').replace('&gt;', '>')
                 .replace('&quot;', '"').replace('&apos;', "'"))
        fields[key] = value.replace('&amp;', '&')
    return fields


# --------------------------------------------------------------------------
# Reference tables


class References(object):
    """Every table the closure is computed from, read once per run."""

    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.feed_class = {}
        self.feed_retired = {}
        self.retired_feeds = []
        self.fold_to_actor = {}
        self.actor_handle = {}
        self.alias_graph = {}
        self.registry = {}
        self.rename_events = {}
        self.cadences = {}
        self.waivers = []
        self.budget = {}
        self.overrides = {}
        self._load()

    # -- generic helpers -------------------------------------------------
    def _delimited(self, name, separator=','):
        path = os.path.join(self.data_dir, name)
        if not os.path.isfile(path):
            return []
        rows = []
        for fields, malformed in read_delimited(path, separator):
            if malformed:
                continue
            rows.append(fields)
        return rows

    def _jsonl(self, name):
        path = os.path.join(self.data_dir, name)
        if not os.path.isfile(path):
            return []
        return [fields for fields, malformed in read_jsonl(path) if not malformed]

    def _kv(self, name):
        path = os.path.join(self.data_dir, name)
        if not os.path.isfile(path):
            return []
        return [fields for fields, malformed in read_kv(path) if not malformed]

    def _reference_rows(self, name):
        """Read one reference file in whichever layout it is written."""
        if name.endswith('.jsonl'):
            return self._jsonl(name)
        if name.endswith('.kv'):
            return self._kv(name)
        if name.endswith('.tsv'):
            return self._delimited(name, '\t')
        if name.endswith('.psv'):
            return self._delimited(name, '|')
        return self._delimited(name, ',')

    # -- loading ---------------------------------------------------------
    def _load(self):
        names = sorted(os.listdir(self.data_dir))
        self._load_feed_manifest(names)
        self._load_roster(names)
        self._load_aliases(names)
        self._load_projects(names)
        self._load_cadences(names)
        self._load_waivers(names)
        self._load_budgets(names)

    def _load_feed_manifest(self, names):
        revisions = defaultdict(list)
        for name in names:
            if name.startswith('feed_manifest.'):
                for fields in self._delimited(name):
                    revisions[fields.get('feed_file', '')].append(fields)
        for feed_file, rows in revisions.items():
            best = None
            for fields in rows:
                key = self._revision_number(fields.get('revision', ''))
                if best is None or key >= best[0]:
                    best = (key, fields)
            if best is None:
                continue
            governing = best[1]
            retired = governing.get('retired_at', '').strip()
            self.feed_class[feed_file] = governing.get('source_class', '').strip()
            self.feed_retired[feed_file] = parse_instant(retired) if retired else None
            if retired:
                self.retired_feeds.append(feed_file)
        self.retired_feeds = sorted(set(self.retired_feeds))

    @staticmethod
    def _revision_number(text):
        text = text.strip()
        if UNSIGNED_RE.match(text):
            return (1, int(text), text)
        return (0, 0, text)

    def _load_roster(self, names):
        spelling_count = defaultdict(lambda: defaultdict(int))
        for name in names:
            if not name.startswith('roster_'):
                continue
            for fields in self._reference_rows(name):
                actor = fields.get('actor_id', '').strip()
                handle = fields.get('canonical_handle', '')
                if not actor:
                    continue
                self.fold_to_actor.setdefault(fold(handle), actor)
                spelling_count[actor][handle] += 1
        for actor, spellings in spelling_count.items():
            best = sorted(spellings.items(), key=lambda item: (-item[1], item[0]))
            self.actor_handle[actor] = best[0][0]
        # a handle folding to two principals keeps the lowest identifier
        by_fold = defaultdict(list)
        for actor, handle in self.actor_handle.items():
            by_fold[fold(handle)].append(actor)
        for folded, actors in by_fold.items():
            if folded in self.fold_to_actor:
                self.fold_to_actor[folded] = sorted(actors)[0]

    def _load_aliases(self, names):
        seen = set()
        for name in names:
            if not name.startswith('aliases_'):
                continue
            for fields in self._reference_rows(name):
                surface = fold(fields.get('surface', ''))
                target = fold(fields.get('target', ''))
                start = parse_instant(fields.get('scope_start', '').strip())
                end = parse_instant(fields.get('scope_end', '').strip())
                if start is None or end is None or start >= end:
                    continue
                if end <= WINDOW_START or start >= WINDOW_END:
                    continue
                key = (surface, target, start, end)
                if key in seen:
                    continue
                seen.add(key)
                self.alias_graph.setdefault(surface, []).append((target, start, end))

    def _load_projects(self, names):
        for name in names:
            if not name.startswith('project_registry.'):
                continue
            for fields in self._delimited(name):
                code = fields.get('project_code', '').strip()
                if not code:
                    continue
                self.registry.setdefault(code, []).append(fields)
        for name in names:
            if not name.startswith('project_events.'):
                continue
            for fields in self._delimited(name, '\t'):
                if fields.get('event_type', '').strip() != 'RENAME':
                    continue
                code = fields.get('project_code', '').strip()
                effective = parse_instant(fields.get('effective_at', '').strip())
                payload = fields.get('payload', '').strip()
                if not code or effective is None or not payload:
                    continue
                self.rename_events.setdefault(code, []).append(
                    (effective, payload, fields.get('event_id', '').strip()))

    def _load_cadences(self, names):
        for name in names:
            if not name.startswith('cadence_register.'):
                continue
            for fields in self._delimited(name):
                cadence_id = fields.get('cadence_id', '').strip()
                if not cadence_id:
                    continue
                self.cadences.setdefault(cadence_id, []).append(fields)

    def _load_waivers(self, names):
        seen = set()
        for name in names:
            if not name.startswith('waivers_'):
                continue
            for fields in self._reference_rows(name):
                cadence_id = fields.get('cadence_id', '').strip()
                period = fields.get('period_index', '').strip()
                if not cadence_id or not UNSIGNED_RE.match(period):
                    continue
                key = (cadence_id, int(period))
                if key in seen:
                    continue
                seen.add(key)
                self.waivers.append({'cadence_id': cadence_id,
                                     'period_index': int(period)})

    def _load_budgets(self, names):
        for name in names:
            if not name.startswith('attention_budget.'):
                continue
            for fields in self._delimited(name):
                pair = self._budget_pair(fields)
                if pair is not None and pair[0] not in self.budget:
                    self.budget[pair[0]] = pair[1]
        for name in names:
            if not name.startswith('budget_overrides.'):
                continue
            for fields in self._delimited(name, '|'):
                pair = self._budget_pair(fields)
                if pair is not None and pair[0] not in self.overrides:
                    self.overrides[pair[0]] = pair[1]

    @staticmethod
    def _budget_pair(fields):
        actor = fields.get('actor_id', '').strip()
        month = fields.get('year_month', '').strip()
        minutes = fields.get('monthly_minutes', '').strip()
        if not actor or not month or not UNSIGNED_RE.match(minutes):
            return None
        return ((actor, month), int(minutes))

    # -- lookups ---------------------------------------------------------
    def source_class(self, feed_file):
        """The source class of a feed, from the manifest and its file name."""
        name_class = ''
        for token in os.path.basename(feed_file).replace('.', '_').split('_'):
            if token in SOURCE_RANKS:
                name_class = token
                break
        declared = self.feed_class.get(feed_file, '')
        if declared in SOURCE_RANKS:
            return declared
        return name_class

    def rank(self, source_class):
        """The rank of a source class under the precedence charter."""
        return SOURCE_RANKS.get(source_class, -1)

    def governing_registry(self, code, moment):
        """The registry revision with the greatest revised_at at or before moment."""
        best = None
        for fields in self.registry.get(code, []):
            revised = parse_instant(fields.get('revised_at', '').strip())
            if revised is None or revised > moment:
                continue
            if best is None or revised >= best[0]:
                best = (revised, fields)
        return best[1] if best else None

    def latest_registry(self, code):
        """The latest revision of a code, which carries the parent it walks to."""
        best = None
        for fields in self.registry.get(code, []):
            key = self._revision_number(fields.get('revision', ''))
            if best is None or key >= best[0]:
                best = (key, fields)
        return best[1] if best else None

    def resolve_project(self, project_ref, moment):
        """Walk the rename lineage, then read the registry."""
        code = project_ref
        visited = set()
        while code and code not in visited:
            visited.add(code)
            applicable = None
            for event in self.rename_events.get(code, []):
                if event[0] > moment:
                    continue
                if applicable is None or event > applicable:
                    applicable = event
            if applicable is None:
                break
            code = applicable[1]
        if code not in self.registry:
            return None
        return code

    def project_root(self, code):
        seen = set()
        current = code
        while current in self.registry and current not in seen:
            seen.add(current)
            revision = self.latest_registry(current)
            parent = revision.get('parent_code', '').strip() if revision else ''
            if not parent or parent not in self.registry:
                return current
            current = parent
        return current

    def governing_cadence(self, cadence_id):
        """The cadence revision with the greatest revision number."""
        best = None
        for fields in self.cadences.get(cadence_id, []):
            key = self._revision_number(fields.get('revision', ''))
            if best is None or key >= best[0]:
                best = (key, fields)
        return best[1] if best else None


# --------------------------------------------------------------------------
# Identity resolution


class Identity(object):
    def __init__(self, references):
        self.references = references
        self.cache = {}

    def resolve(self, surface, moment):
        """Return (status, actor, hops) for a surface resolved at an instant."""
        key = (surface, moment)
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        start = fold(surface)
        roster = self.references.fold_to_actor
        aliases = self.references.alias_graph
        seen = {start}
        queue = deque([(start, 0)])
        actors = {}
        while queue:
            node, hops = queue.popleft()
            actor = roster.get(node)
            if actor is not None:
                if actor not in actors or hops < actors[actor]:
                    actors[actor] = hops
            for target, scope_start, scope_end in aliases.get(node, ()):
                if not (scope_start <= moment < scope_end):
                    continue
                if target in seen:
                    continue
                seen.add(target)
                queue.append((target, hops + 1))
        if len(actors) == 1:
            actor = next(iter(actors))
            result = ('RESOLVED', actor, actors[actor])
        elif not actors:
            result = ('UNKNOWN', '', 0)
        else:
            result = ('AMBIGUOUS', '', min(actors.values()))
        self.cache[key] = result
        return result


# --------------------------------------------------------------------------
# Ingestion and the rejection ladder


class Row(object):
    __slots__ = ('feed_file', 'row_index', 'kind', 'fields', 'malformed',
                 'record_id', 'commitment_key', 'reason', 'source_class',
                 'observed_at')


def classify_feed(name):
    for prefix, kind in (('commitments_', 'commitment'), ('states_', 'state'),
                         ('edges_', 'edge')):
        if name.startswith(prefix):
            return kind
    return None


def read_feed(references, feed_file, kind):
    """Read one feed into (fields, malformed) pairs, one entry per record."""
    path = os.path.join(references.data_dir, feed_file)
    if kind == 'commitment' and feed_file.endswith('.fixed'):
        return read_fixed(path, COMMITMENT_FIXED_COLUMNS)
    if kind == 'state' and feed_file.endswith('.fixed'):
        return read_fixed(path, STATE_FIXED_COLUMNS)
    extension = os.path.splitext(feed_file)[1]
    if extension == '.csv':
        return read_delimited(path, ',')
    if extension == '.tsv':
        return read_delimited(path, '\t')
    if extension == '.psv':
        return read_delimited(path, '|')
    if extension == '.jsonl':
        return read_jsonl(path)
    if extension == '.kv':
        return read_kv(path)
    if extension == '.rec':
        return read_rec(path)
    if extension == '.xml':
        return read_xml(path)
    return []


def ingest(references, identity):
    """Read every commitment, state and edge record and reject what fails."""
    rows = []
    rejects = []
    names = sorted(os.listdir(references.data_dir))
    feeds = [name for name in names if classify_feed(name)]
    for feed_file in feeds:
        kind = classify_feed(feed_file)
        records = read_feed(references, feed_file, kind)
        retired = references.feed_retired.get(feed_file)
        source_class = references.source_class(feed_file)
        for index, (fields, malformed) in enumerate(records):
            row = Row()
            row.feed_file = feed_file
            row.row_index = index
            row.kind = kind
            row.fields = fields
            row.malformed = malformed
            row.source_class = source_class
            row.reason = None
            if kind == 'commitment':
                row.record_id = fields.get('assertion_id', '')
                row.commitment_key = fields.get('commitment_key', '')
                row.observed_at = parse_instant(fields.get('observed_at', '').strip())
            elif kind == 'state':
                row.record_id = fields.get('state_id', '')
                row.commitment_key = fields.get('commitment_key', '')
                row.observed_at = parse_instant(fields.get('observed_at', '').strip())
            else:
                row.record_id = fields.get('edge_id', '')
                row.commitment_key = fields.get('dependent_key', '')
                row.observed_at = parse_instant(fields.get('asserted_at', '').strip())
            rows.append(row)

    # ---- the ladder, in the fixed order of protocol section 6
    for row in rows:
        reason = test_row(references, identity, row)
        row.reason = reason
        if reason is not None:
            rejects.append(row)
    return rows, rejects


def test_row(references, identity, row):
    """Return the first reason code a row carries, or None when accepted."""
    fields = row.fields
    # 1. MALFORMED_ROW, tested ahead of every later code.
    if row.malformed:
        return 'MALFORMED_ROW'
    if row.kind == 'commitment':
        due_at = parse_instant(fields.get('due_at', '').strip())
        observed_at = row.observed_at
        if due_at is None or observed_at is None:
            return 'MALFORMED_ROW'
        effort_state = effort_of(fields, row.feed_file)
        if effort_state == 'MALFORMED':
            return 'MALFORMED_ROW'
    elif row.kind == 'state':
        if fields.get('to_state', '').strip() not in STATES:
            return 'MALFORMED_ROW'
        if row.observed_at is None:
            return 'MALFORMED_ROW'
    else:
        if row.observed_at is None:
            return 'MALFORMED_ROW'

    # 2. FEED_RETIRED
    retired = references.feed_retired.get(row.feed_file)
    if retired is not None and row.observed_at is not None and row.observed_at >= retired:
        return 'FEED_RETIRED'

    # 3. OUT_OF_WINDOW
    if row.kind == 'commitment':
        moment = parse_instant(fields.get('due_at', '').strip())
    else:
        moment = row.observed_at
    if not (WINDOW_START <= moment < WINDOW_END):
        return 'OUT_OF_WINDOW'

    # 4 and 5. UNKNOWN_PRINCIPAL and AMBIGUOUS_IDENTITY reject only the obligor.
    if row.kind == 'commitment':
        status, actor, _hops = identity.resolve(fields.get('obligor', ''),
                                                row.observed_at)
        if status == 'UNKNOWN':
            return 'UNKNOWN_PRINCIPAL'
        if status == 'AMBIGUOUS':
            return 'AMBIGUOUS_IDENTITY'

    # 6. UNKNOWN_PROJECT
    if row.kind == 'commitment':
        code = references.resolve_project(fields.get('project_ref', '').strip(),
                                          row.observed_at)
        if code is None:
            return 'UNKNOWN_PROJECT'

    # 7. NONPOSITIVE_EFFORT
    if row.kind == 'commitment':
        effort_state = effort_of(fields, row.feed_file)
        if effort_state == 'NONPOSITIVE':
            return 'NONPOSITIVE_EFFORT'
    return None


def effort_of(fields, feed_file):
    """Read the effort field of a commitment assertion.

    Returns 'EMPTY', 'NONPOSITIVE', 'MALFORMED', or ('VALUE'|'ZERO',
    origin, minutes).  The unit is read only for an integer above zero, and
    only in a layout carrying an effort_unit field.
    """
    raw = fields.get('effort', '')
    if raw is None:
        raw = 'null'
    raw = str(raw)
    carries_unit_field = not (feed_file.endswith('.fixed')
                              or feed_file.endswith('.rec'))
    if raw == '':
        return 'EMPTY'
    if raw == 'null':
        return ('ZERO', 'DECLARED_ZERO', 0)
    if not INTEGER_RE.match(raw):
        return 'MALFORMED'
    value = int(raw)
    if value <= 0:
        return 'NONPOSITIVE'
    if carries_unit_field:
        unit = fields.get('effort_unit', '')
        if unit not in EFFORT_UNIT_FACTORS:
            return 'MALFORMED'
        factor = EFFORT_UNIT_FACTORS[unit]
    else:
        factor = EFFORT_UNIT_FACTORS['hours']
    return ('VALUE', 'STATED', value * factor)


# --------------------------------------------------------------------------
# Assertions, states and edges


def build_assertions(references, identity, rows):
    """Normalized accepted assertions and the alias resolution survey."""
    assertions = []
    surfaces = {}
    multi_hop = 0
    for row in rows:
        if row.kind != 'commitment' or row.reason is not None:
            continue
        fields = row.fields
        due_at = parse_instant(fields.get('due_at', '').strip())
        observed_at = row.observed_at
        obligor_status, obligor_actor, hops = identity.resolve(
            fields.get('obligor', ''), observed_at)
        obligee_status, obligee_actor, _ = identity.resolve(
            fields.get('obligee', ''), due_at)
        project_code = references.resolve_project(
            fields.get('project_ref', '').strip(), observed_at)
        effort = effort_of(fields, row.feed_file)
        if effort == 'EMPTY':
            revision = references.governing_registry(project_code, observed_at)
            default = revision.get('default_effort', '').strip() if revision else ''
            if UNSIGNED_RE.match(default):
                minutes = int(default)
            else:
                minutes = 0
            origin = 'DEFAULTED'
        elif effort == 'NONPOSITIVE':
            continue
        elif effort == 'MALFORMED':
            continue
        else:
            origin = effort[1]
            minutes = effort[2]
        minutes = 0 if minutes == 0 else max(EFFORT_FLOOR_MINUTES,
                                             min(EFFORT_CEILING_MINUTES, minutes))
        assertion = {
            'assertion_id': fields.get('assertion_id', ''),
            'commitment_key': fields.get('commitment_key', ''),
            'obligor_actor': obligor_actor,
            'obligee_actor': obligee_actor if obligee_status == 'RESOLVED' else '',
            'obligee_status': obligee_status,
            'project_code': project_code,
            'project_root': references.project_root(project_code),
            'due_at': instant_text(due_at),
            'commitment_day': commitment_day(due_at),
            'effort_minutes': minutes,
            'effort_origin': origin,
            'cadence_ref': fields.get('cadence_ref', ''),
            'observed_at': instant_text(observed_at),
            'source_class': row.source_class,
            '_rank': references.rank(row.source_class),
            '_observed': observed_at,
            '_obligor_surface': fields.get('obligor', ''),
            '_feed_file': row.feed_file,
        }
        assertions.append(assertion)
        if hops >= 2:
            multi_hop += 1
        folded = fold(fields.get('obligor', ''))
        entry = surfaces.setdefault(folded, {'count': 0, 'actors': {}, 'hops': 0})
        entry['count'] += 1
        entry['actors'][obligor_actor] = True
        entry['hops'] = max(entry['hops'], hops)
    return assertions, surfaces, multi_hop


def precedence_key(references, kind, source_class, observed_at, record_id):
    """The order of precedence charter section 2, ascending.

    Rank first, then the instant inside a rank, with the two inversions the
    charter names: `desk` rows everywhere and `bridge` state rows.  A tie falls
    to the ascending row identifier.
    """
    rank = references.rank(source_class)
    minutes = (observed_at - EPOCH) // timedelta(minutes=1)
    inverted = source_class == 'desk' or (source_class == 'bridge'
                                          and kind == 'state')
    if inverted:
        minutes = -minutes
    return (rank, minutes, record_id)


def admit_commitments(references, assertions):
    """Group accepted assertions by commitment key and choose the winner."""
    grouped = defaultdict(list)
    for assertion in assertions:
        grouped[assertion['commitment_key']].append(assertion)
    winners = {}
    for key, contenders in grouped.items():
        contenders.sort(key=lambda a: precedence_key(
            references, 'commitment', a['source_class'], a['_observed'],
            a['assertion_id']))
        winners[key] = contenders[-1]
    return grouped, winners


def walk_states(references, rows, admitted, rejects):
    """Walk the accepted state rows and return the resolved state per key."""
    per_key = defaultdict(list)
    for row in rows:
        if row.kind != 'state' or row.reason is not None:
            continue
        per_key[row.commitment_key].append(row)
    resolved = {}
    applied_counts = {}
    seen_counts = {}
    governing = {}
    for key in admitted:
        state_rows = per_key.get(key, [])
        seen_counts[key] = len(state_rows)
        state_rows.sort(key=lambda r: precedence_key(
            references, 'state', r.source_class, r.observed_at, r.record_id))
        current = 'OPEN'
        applied = 0
        governing_class = ''
        for row in state_rows:
            to_state = row.fields.get('to_state', '').strip()
            if (current, to_state) in LEGAL_TRANSITIONS:
                current = to_state
                applied += 1
                governing_class = row.source_class
            else:
                row.reason = 'ILLEGAL_TRANSITION'
                rejects.append(row)
        resolved[key] = current
        applied_counts[key] = applied
        governing[key] = governing_class
    return resolved, seen_counts, applied_counts, governing


# --------------------------------------------------------------------------
# Edges, blocking and closure


def settle_edges(identity, rows, admitted, winners):
    """Split accepted edge rows into live and dropped, then find blockers."""
    live = []
    dropped = []
    for row in rows:
        if row.kind != 'edge' or row.reason is not None:
            continue
        fields = row.fields
        dependent = fields.get('dependent_key', '')
        blocker = fields.get('blocker_key', '')
        if dependent == blocker:
            dropped.append((row, 'EDGE_SELF'))
            continue
        if dependent not in admitted or blocker not in admitted:
            dropped.append((row, 'EDGE_DANGLING'))
            continue
        moment = row.observed_at
        dependent_status, dependent_actor, _ = identity.resolve(
            winners[dependent]['_obligor_surface'], moment)
        blocker_status, blocker_actor, _ = identity.resolve(
            winners[blocker]['_obligor_surface'], moment)
        if dependent_status != 'RESOLVED' or blocker_status != 'RESOLVED':
            dropped.append((row, 'EDGE_OUT_OF_SCOPE'))
            continue
        live.append((row, dependent, blocker, dependent_actor, blocker_actor))
    return live, dropped


def strongly_connected_components(nodes, edges):
    """Tarjan's algorithm, iterative, over a directed graph."""
    index = {}
    lowlink = {}
    on_stack = {}
    stack = []
    result = []
    counter = [0]
    adjacency = defaultdict(list)
    for source, target in edges:
        adjacency[source].append(target)
    for start in nodes:
        if start in index:
            continue
        work = [(start, 0)]
        while work:
            node, pointer = work.pop()
            if pointer == 0:
                index[node] = counter[0]
                lowlink[node] = counter[0]
                counter[0] += 1
                stack.append(node)
                on_stack[node] = True
            advanced = False
            neighbours = adjacency.get(node, [])
            while pointer < len(neighbours):
                target = neighbours[pointer]
                pointer += 1
                if target not in index:
                    work.append((node, pointer))
                    work.append((target, 0))
                    advanced = True
                    break
                if on_stack.get(target):
                    lowlink[node] = min(lowlink[node], index[target])
            if advanced:
                continue
            if lowlink[node] == index[node]:
                component = []
                while True:
                    member = stack.pop()
                    on_stack[member] = False
                    component.append(member)
                    if member == node:
                        break
                result.append(component)
            if work:
                parent = work[-1][0]
                lowlink[parent] = min(lowlink[parent], lowlink[node])
    return result


# --------------------------------------------------------------------------
# Cadence periods, waivers and debt


def cadence_periods(anchor, period_days):
    """The elapsed half open periods, the last one cut short at the window end."""
    periods = []
    if period_days <= 0:
        return periods
    index = 0
    while True:
        start = anchor + timedelta(minutes=period_days * 1440 * index)
        if start >= WINDOW_END:
            break
        end = anchor + timedelta(minutes=period_days * 1440 * (index + 1))
        if end > WINDOW_END:
            end = WINDOW_END
        periods.append((index, start, end))
        index += 1
    return periods


def build_cadences(references, identity, ledger):
    """Resolve cadence ownership, discharge, waivers, debt and streak."""
    settled_by_cadence = defaultdict(set)
    for key, commitment in ledger.items():
        if commitment['commitment_class'] != 'SETTLED':
            continue
        cadence_ref = commitment['cadence_ref']
        if not cadence_ref:
            continue
        settled_by_cadence[cadence_ref].add(parse_instant(commitment['due_at']))

    owners = {}
    periods_of = {}
    period_discharge = {}
    for cadence_id in sorted(references.cadences):
        governing = references.governing_cadence(cadence_id)
        obligor = governing.get('obligor', '')
        anchor = parse_instant(governing.get('anchor_at', '').strip())
        period_days = governing.get('period_days', '').strip()
        if anchor is None or not UNSIGNED_RE.match(period_days):
            periods = []
            period_days = 0
        else:
            period_days = int(period_days)
            periods = cadence_periods(anchor, period_days)
        status, actor, _hops = (identity.resolve(obligor, anchor)
                                if anchor is not None else ('UNKNOWN', '', 0))
        owner = actor if status == 'RESOLVED' else ''
        owners[cadence_id] = owner
        periods_of[cadence_id] = periods
        discharged = set()
        for index, start, end in periods:
            for due in settled_by_cadence.get(cadence_id, ()):
                if start <= due < end:
                    discharged.add(index)
                    break
        period_discharge[cadence_id] = discharged

    # waivers: one per cadence and period, in elapsed periods of declared cadences
    waiver_records = []
    for waiver in references.waivers:
        cadence_id = waiver['cadence_id']
        if cadence_id not in periods_of:
            continue
        periods = periods_of[cadence_id]
        index = waiver['period_index']
        if index < 0 or index >= len(periods):
            continue
        _index, start, end = periods[index]
        waiver_records.append({'cadence_id': cadence_id, 'period_index': index,
                               'period_start': start, 'period_end': end})

    # the allowance: one per principal, drawn in ascending period start then cadence
    per_owner = defaultdict(list)
    for waiver in waiver_records:
        owner = owners.get(waiver['cadence_id'], '')
        if owner:
            per_owner[owner].append(waiver)
    granted = set()
    for owner, owned in per_owner.items():
        owned.sort(key=lambda w: (w['period_start'], w['cadence_id']))
        for position, waiver in enumerate(owned):
            if position < WAIVER_ALLOWANCE:
                granted.add((waiver['cadence_id'], waiver['period_index']))
    for waiver in waiver_records:
        owner = owners.get(waiver['cadence_id'], '')
        if not owner:
            granted.add((waiver['cadence_id'], waiver['period_index']))

    trace = []
    for waiver in waiver_records:
        key = (waiver['cadence_id'], waiver['period_index'])
        if key not in granted:
            effect = 'LAPSED'
        elif waiver['period_index'] in period_discharge[waiver['cadence_id']]:
            effect = 'INERT'
        else:
            effect = 'SUPPRESSED'
        trace.append({'cadence_id': waiver['cadence_id'],
                      'period_index': waiver['period_index'],
                      'effect': effect,
                      'period_start': instant_text(waiver['period_start'])})
    trace.sort(key=lambda w: (w['cadence_id'], w['period_index']))

    cadence_rows = []
    debt_of = {}
    waived_of = {}
    for cadence_id in sorted(periods_of):
        discharged = period_discharge[cadence_id]
        debt = 0
        streak = 0
        max_streak = 0
        waived = 0
        discharge_count = 0
        for index, _start, _end in periods_of[cadence_id]:
            if index in discharged:
                streak = 0
                discharge_count += 1
            elif (cadence_id, index) in granted:
                waived += 1
            else:
                debt += 1
                streak += 1
            max_streak = max(max_streak, streak)
        cadence_rows.append({'cadence_id': cadence_id,
                             'period_days': (references.governing_cadence(
                                 cadence_id).get('period_days', '').strip()),
                             'periods_elapsed': len(periods_of[cadence_id]),
                             'periods_discharged': discharge_count,
                             'periods_waived': waived,
                             'debt': debt,
                             'max_streak': max_streak,
                             'owner': owners.get(cadence_id, '')})
        debt_of[cadence_id] = debt
        waived_of[cadence_id] = waived
    return cadence_rows, trace, owners, debt_of, waived_of


# --------------------------------------------------------------------------
# Attention envelopes


def distribute(total, items):
    """Distribute total minutes over (key, weight) by largest remainder."""
    shares = {key: 0 for key, _weight in items}
    weight_total = sum(weight for _key, weight in items)
    if total <= 0 or weight_total <= 0 or not items:
        return shares
    ordered = []
    allocated = 0
    for key, weight in items:
        exact = total * weight
        base = exact // weight_total
        remainder = exact % weight_total
        ordered.append((key, base, remainder))
        allocated += base
    left = total - allocated
    ordered.sort(key=lambda item: (-item[2], item[0]))
    awards = {key: 0 for key, _weight in items}
    for index in range(min(left, len(ordered))):
        awards[ordered[index][0]] = 1
    for key, base, _remainder in ordered:
        shares[key] = base + awards[key]
    return shares


# --------------------------------------------------------------------------
# The closure


def build_closure(ledger, blocking_edges, cycle_members):
    """The blocking closure of every blocked commitment."""
    leaves = defaultdict(list)
    for dependent, blocker in blocking_edges:
        leaves[dependent].append(blocker)
    blocked = [key for key in sorted(ledger)
               if key not in cycle_members and leaves.get(key)]
    closure_rows = []
    blocked_rows = []
    for key in blocked:
        distances = {key: 0}
        queue = deque([key])
        while queue:
            node = queue.popleft()
            for blocker in leaves.get(node, ()):
                if blocker not in distances:
                    distances[blocker] = distances[node] + 1
                    queue.append(blocker)
        reached = sorted(distances)
        terminal = [name for name in reached
                    if name != key and not leaves.get(name)]
        terminal_set = set(terminal)
        for name in reached:
            if name == key:
                continue
            closure_rows.append({
                'dependent_key': key,
                'blocker_key': name,
                'hop_distance': distances[name],
                'blocker_state': ledger[name]['resolved_state'],
                'terminal': 'yes' if name in terminal_set else 'no',
            })
        blocked_rows.append({
            'commitment_key': key,
            'reachable_blockers': len(reached) - 1,
            'frontier_count': len(terminal_set),
            'chain_depth': max(distances.values()),
            'frontier_head': terminal[0] if terminal else '',
        })
    closure_rows.sort(key=lambda row: (row['dependent_key'], row['blocker_key']))
    return closure_rows, blocked_rows, blocked


def compute_wait(blocked, blocking_edges, blocked_set):
    """The wait of a blocked commitment is one more than its blockers' greatest.

    A commitment that is not blocked has wait zero, so the recursion runs over
    a subgraph no member of which sits on a cycle.  A worklist walk settles it
    without depending on the interpreter recursion limit.
    """
    leaves = defaultdict(set)
    for dependent, blocker in blocking_edges:
        leaves[dependent].add(blocker)
    memo = {}
    pending = sorted(blocked)
    while pending:
        progressed = False
        remaining = []
        for key in pending:
            ready = True
            best = 0
            for blocker in leaves.get(key, ()):
                if blocker in blocked_set and blocker not in memo:
                    ready = False
                    break
                best = max(best, memo.get(blocker, 0))
            if ready:
                memo[key] = best + 1
                progressed = True
            else:
                remaining.append(key)
        if not progressed:
            for key in remaining:
                memo[key] = 1
            break
        pending = remaining
    return memo


# --------------------------------------------------------------------------
# Attention envelopes


def allocate_attention(references, ledger, blocked_rows, closure_info, waits,
                      cadence_owners, cadence_waived):
    """Distribute each principal's monthly envelope across open commitments."""
    open_classes = ('ACTIONABLE', 'BLOCKED', 'DEFERRED')
    groups = defaultdict(list)
    for key in sorted(ledger):
        item = ledger[key]
        if item['commitment_class'] not in open_classes:
            continue
        if item['effort_minutes'] <= 0:
            continue
        month = item['commitment_day'][:7]
        groups[(item['obligor_actor'], month)].append(key)

    waived_by_owner = defaultdict(int)
    for cadence_id, owner in cadence_owners.items():
        if owner:
            waived_by_owner[owner] += cadence_waived.get(cadence_id, 0)

    blocked_by_group = defaultdict(list)
    for row in blocked_rows:
        key = row['commitment_key']
        item = ledger[key]
        blocked_by_group[(item['obligor_actor'], item['commitment_day'][:7])].append(key)

    allocations = {key: 0 for key in ledger}
    month_index = {}
    starved = 0
    for pair in sorted(groups):
        actor, month = pair
        keys = groups[pair]
        if (actor, month) in references.overrides:
            source = 'OVERRIDE'
            envelope = references.overrides[(actor, month)]
        elif (actor, month) in references.budget:
            source = 'REGISTERED'
            envelope = references.budget[(actor, month)]
        else:
            source = 'ABSENT'
            envelope = 0

        reserve = 0
        for key in blocked_by_group.get(pair, ()):
            reserve += RESERVE_PER_WAIT_MINUTES * waits.get(key, 0)
        reserve += RESERVE_PER_WAIVED_PERIOD_MINUTES * waived_by_owner.get(actor, 0)
        distributable = envelope - reserve
        if distributable < 0:
            distributable = 0
        items = [(key, ledger[key]['effort_minutes']) for key in keys]
        demand = sum(weight for _key, weight in items)
        shares = {}
        if demand <= distributable:
            shares = {key: weight for key, weight in items}
        else:
            shares = distribute(distributable, items)
            poor = [key for key in keys
                    if shares[key] < ALLOCATION_FLOOR_MINUTES]
            if poor:
                starved += len(poor)
                survivors = [(key, ledger[key]['effort_minutes'])
                              for key in keys
                              if shares[key] >= ALLOCATION_FLOOR_MINUTES]
                shares = distribute(distributable, survivors)
                shares.update({key: 0 for key in keys if key not in shares})
        for key in keys:
            allocations[key] = shares.get(key, 0)
        allocated_total = sum(shares.get(key, 0) for key in keys)
        month_index[pair] = {
            'year_month': month,
            'obligor_actor': actor,
            'budget_source': source,
            'budget_minutes': envelope,
            'reserve_minutes': reserve,
            'demand_minutes': demand,
            'allocated_minutes': allocated_total,
            'open_count': len(keys),
        }
    return allocations, month_index, starved


def build_escalations(ledger, allocations, cadence_owners, cadence_debt,
                      closure_info):
    """The commitments that escalate under protocol section 10."""
    debt_by_owner = defaultdict(int)
    for cadence_id, owner in cadence_owners.items():
        if owner:
            debt_by_owner[owner] += cadence_debt.get(cadence_id, 0)
    escalations = []
    for key in sorted(ledger):
        item = ledger[key]
        if item['commitment_class'] not in ('ACTIONABLE', 'BLOCKED'):
            continue
        effort = item['effort_minutes']
        share = allocations.get(key, 0)
        if not (share < effort):
            continue
        principal_debt = debt_by_owner.get(item['obligor_actor'], 0)
        if principal_debt < ESCALATION_MIN_DEBT:
            continue
        depth = closure_info[key]['chain_depth'] if key in closure_info else 0
        month = item['commitment_day'][:7] == ESCALATION_MONTH
        if depth >= ESCALATION_MIN_DEPTH and month:
            trigger = 'BOTH'
        elif depth >= ESCALATION_MIN_DEPTH:
            trigger = 'DEPTH'
        elif month:
            trigger = 'MONTH'
        else:
            continue
        escalations.append({
            'commitment_key': key,
            'obligor_actor': item['obligor_actor'],
            'commitment_class': item['commitment_class'],
            'effort_minutes': effort,
            'allocated_minutes': share,
            'shortfall_minutes': effort - share,
            'principal_debt': principal_debt,
            'chain_depth': depth,
            'trigger': trigger,
        })
    escalations.sort(key=lambda row: (-row['shortfall_minutes'],
                                      row['commitment_key']))
    return escalations


# --------------------------------------------------------------------------
# Rendering the deliverables


def canonical_order(item):
    return (item['commitment_day'], item['obligor_actor'],
            -item['effort_minutes'], item['commitment_key'])


# --------------------------------------------------------------------------
# The run


def run(data_dir):
    """Compute the whole closure and return the deliverables as text."""
    references = References(data_dir)
    identity = Identity(references)
    rows, rejects = ingest(references, identity)

    assertions, surfaces, multi_hop = build_assertions(references, identity, rows)
    grouped, winners = admit_commitments(references, assertions)
    admitted = sorted(grouped)

    # a state row names a commitment no accepted assertion creates
    for row in rows:
        if row.kind == 'state' and row.reason is None:
            if row.commitment_key not in grouped:
                row.reason = 'UNKNOWN_COMMITMENT'
                rejects.append(row)

    resolved, seen_counts, applied_counts, governing = walk_states(
        references, rows, admitted, rejects)

    ledger = {}
    for key in admitted:
        winner = winners[key]
        ledger[key] = {
            'commitment_key': key,
            'obligor_actor': winner['obligor_actor'],
            'obligee_actor': winner['obligee_actor'],
            'project_code': winner['project_code'],
            'project_root': winner['project_root'],
            'commitment_day': winner['commitment_day'],
            'due_at': winner['due_at'],
            'effort_minutes': winner['effort_minutes'],
            'effort_origin': winner['effort_origin'],
            'resolved_state': resolved.get(key, 'OPEN'),
            'cadence_ref': winner['cadence_ref'],
            'source_class': winner['source_class'],
            'winning_assertion': winner['assertion_id'],
            'allocated_minutes': 0,
            'unresolvable_reason': '',
            'commitment_class': '',
            '_obligor_surface': winner['_obligor_surface'],
            '_obligee_status': winner['obligee_status'],
        }

    live, dropped = settle_edges(identity, rows, grouped, ledger)

    # blocking edges: live edges whose blocker holds
    holding = {key for key, item in ledger.items()
               if item['resolved_state'] in ('OPEN', 'DEFERRED')}
    blocking = sorted(set((dependent, blocker)
                          for _row, dependent, blocker, _a, _b in live
                          if blocker in holding))
    nodes = sorted({key for pair in blocking for key in pair})
    cycle_members = set()
    for component in strongly_connected_components(nodes, blocking):
        if len(component) > 1:
            cycle_members.update(component)

    closure_rows, blocked_rows, blocked = build_closure(
        ledger, blocking, cycle_members)
    blocked_set = set(blocked)
    waits = compute_wait(blocked, blocking, blocked_set)

    for item in ledger.values():
        key = item['commitment_key']
        if item['resolved_state'] == 'SETTLED':
            item['commitment_class'] = 'SETTLED'
        elif item['resolved_state'] == 'WITHDRAWN':
            item['commitment_class'] = 'WITHDRAWN'
        elif key in cycle_members:
            item['commitment_class'] = 'UNRESOLVABLE'
            item['unresolvable_reason'] = 'CIRCULAR_DEPENDENCY'
        elif item['_obligee_status'] == 'AMBIGUOUS':
            item['commitment_class'] = 'UNRESOLVABLE'
            item['unresolvable_reason'] = 'AMBIGUOUS_COUNTERPARTY'
        elif key in blocked_set:
            item['commitment_class'] = 'BLOCKED'
        elif item['resolved_state'] == 'DEFERRED':
            item['commitment_class'] = 'DEFERRED'
        else:
            item['commitment_class'] = 'ACTIONABLE'

    cadence_rows, waiver_trace, cadence_owners, cadence_debt, cadence_waived = (
        build_cadences(references, identity, ledger))

    closure_info = {row['commitment_key']: row for row in blocked_rows}
    allocations, month_index, starved = allocate_attention(
        references, ledger, blocked_rows, closure_info, waits, cadence_owners,
        cadence_waived)
    escalations = build_escalations(ledger, allocations, cadence_owners,
                                    cadence_debt, closure_info)

    return render(references, rows, rejects, assertions, surfaces, multi_hop,
                  grouped, admitted, ledger, live, dropped, closure_rows,
                  blocked_rows, closure_info, cadence_rows, waiver_trace,
                  cadence_owners, allocations, month_index, starved,
                  escalations, seen_counts, applied_counts, governing)


def render(references, rows, rejects, assertions, surfaces, multi_hop,
           grouped, admitted, ledger, live, dropped, closure_rows,
           blocked_rows, closure_info, cadence_rows, waiver_trace,
           cadence_owners, allocations, month_index, starved, escalations,
           seen_counts, applied_counts, governing):
    """Build every deliverable as text, keyed by its file name."""
    for key in ledger:
        ledger[key]['allocated_minutes'] = allocations.get(key, 0)

    ordered = sorted(ledger.values(), key=canonical_order)
    order_tiebreaks = 0
    for left, right in zip(ordered, ordered[1:]):
        if (left['commitment_day'] == right['commitment_day']
                and left['obligor_actor'] == right['obligor_actor']
                and left['effort_minutes'] != right['effort_minutes']):
            order_tiebreaks += 1

    files = {}

    # -- normalized_assertions.jsonl
    fields = ['assertion_id', 'commitment_key', 'obligor_actor', 'obligee_actor',
              'obligee_status', 'project_code', 'project_root', 'due_at',
              'commitment_day', 'effort_minutes', 'effort_origin', 'cadence_ref',
              'observed_at', 'source_class']
    files['normalized_assertions.jsonl'] = jsonl_text(
        [{name: assertion[name] for name in fields}
         for assertion in sorted(assertions,
                                 key=lambda a: a['assertion_id'])])

    # -- rejects.csv
    fields = ['feed_file', 'row_index', 'record_kind', 'record_id',
              'commitment_key', 'reason_code']
    reject_rows = []
    for row in rejects:
        reject_rows.append([row.feed_file, row.row_index, row.kind,
                            row.record_id, row.commitment_key, row.reason])
    reject_rows.sort(key=lambda row: (row[5], row[0], row[1], row[3]))
    files['rejects.csv'] = table_text(fields, reject_rows)

    # -- alias_resolution.jsonl
    alias_rows = []
    split_surfaces = 0
    for surface in sorted(surfaces):
        entry = surfaces[surface]
        actors = sorted(entry['actors'])
        if len(actors) > 1:
            split_surfaces += 1
        alias_rows.append({'surface_folded': surface,
                           'distinct_actors': actors,
                           'assertion_count': entry['count'],
                           'max_hops': entry['hops']})
    files['alias_resolution.jsonl'] = jsonl_text(alias_rows)

    # -- actor_roster.csv
    trace_by_owner = defaultdict(lambda: {'granted': 0, 'lapsed': 0})
    for waiver in waiver_trace:
        owner = cadence_owners.get(waiver['cadence_id'], '')
        if not owner:
            continue
        if waiver['effect'] == 'LAPSED':
            trace_by_owner[owner]['lapsed'] += 1
        else:
            trace_by_owner[owner]['granted'] += 1
    commitments_by_actor = defaultdict(list)
    for item in ledger.values():
        commitments_by_actor[item['obligor_actor']].append(item)
    roster_rows = []
    for actor in sorted(references.actor_handle):
        items = commitments_by_actor.get(actor, [])
        open_effort = sum(item['effort_minutes'] for item in items
                          if item['commitment_class'] in
                          ('ACTIONABLE', 'BLOCKED', 'DEFERRED'))
        roster_rows.append([
            actor, references.actor_handle[actor], len(items), open_effort,
            trace_by_owner[actor]['granted'],
            trace_by_owner[actor]['lapsed']])
    files['actor_roster.csv'] = table_text(
        ['actor_id', 'canonical_handle', 'commitment_count',
         'open_effort_minutes', 'waivers_granted', 'waivers_lapsed'],
        roster_rows)

    # -- project_lineage.csv
    assertion_count = defaultdict(int)
    for assertion in assertions:
        assertion_count[assertion['project_code']] += 1
    allocated_by_code = defaultdict(int)
    for item in ledger.values():
        allocated_by_code[item['project_code']] += item['allocated_minutes']
    lineage_rows = []
    for code in sorted(assertion_count):
        lineage_rows.append([code, references.project_root(code),
                              assertion_count[code],
                              allocated_by_code.get(code, 0)])
    files['project_lineage.csv'] = table_text(
        ['project_code', 'project_root', 'assertion_count', 'allocated_minutes'],
        lineage_rows)

    # -- assertion_contests.csv
    contest_rows = []
    for key in admitted:
        contenders = grouped[key]
        classes = sorted({c['source_class'] for c in contenders})
        contest_rows.append([key, ledger[key]['winning_assertion'],
                             ledger[key]['source_class'], len(contenders),
                             len(classes)])
    files['assertion_contests.csv'] = table_text(
        ['commitment_key', 'winning_assertion', 'winning_class',
         'contender_count', 'distinct_classes'], contest_rows)

    # -- commitment_ledger.jsonl
    ledger_fields = ['commitment_key', 'obligor_actor', 'obligee_actor',
                     'project_code', 'project_root', 'commitment_day', 'due_at',
                     'effort_minutes', 'effort_origin', 'resolved_state',
                     'commitment_class', 'cadence_ref', 'source_class',
                     'winning_assertion', 'allocated_minutes']
    files['commitment_ledger.jsonl'] = jsonl_text(
        [{name: item[name] for name in ledger_fields} for item in ordered])

    # -- state_resolution.csv
    state_rows = []
    for key in admitted:
        state_rows.append([key, ledger[key]['resolved_state'],
                           seen_counts.get(key, 0), applied_counts.get(key, 0),
                           governing.get(key, '')])
    files['state_resolution.csv'] = table_text(
        ['commitment_key', 'resolved_state', 'assertions_seen',
         'assertions_applied', 'governing_class'], state_rows)

    # -- live_edges.csv
    blocked_keys = set(closure_info)
    live_rows = []
    for row, dependent, blocker, dependent_actor, blocker_actor in live:
        live_rows.append([row.record_id, dependent, blocker,
                          row.fields.get('asserted_at', ''), dependent_actor,
                          blocker_actor,
                          'yes' if dependent in blocked_keys else 'no'])
    live_rows.sort(key=lambda row: (row[1], row[2], row[0]))
    files['live_edges.csv'] = table_text(
        ['edge_id', 'dependent_key', 'blocker_key', 'asserted_at',
         'dependent_actor', 'blocker_actor', 'dependent_blocked'], live_rows)

    # -- dropped_edges.csv
    dropped_rows = []
    for row, reason in dropped:
        dropped_rows.append([row.record_id, row.commitment_key,
                             row.fields.get('blocker_key', ''),
                             row.fields.get('asserted_at', ''), reason])
    dropped_rows.sort(key=lambda row: (row[4], row[0]))
    files['dropped_edges.csv'] = table_text(
        ['edge_id', 'dependent_key', 'blocker_key', 'asserted_at',
         'drop_reason'], dropped_rows)

    # -- blocking_closure.jsonl
    closure_fields = ['dependent_key', 'blocker_key', 'hop_distance',
                      'blocker_state', 'terminal']
    files['blocking_closure.jsonl'] = jsonl_text(
        [{name: row[name] for name in closure_fields}
         for row in sorted(closure_rows,
                           key=lambda r: (r['dependent_key'], r['blocker_key']))])

    # -- blocked_commitments.csv
    files['blocked_commitments.csv'] = table_text(
        ['commitment_key', 'reachable_blockers', 'frontier_count', 'chain_depth',
         'frontier_head', 'allocated_minutes'],
        [[row['commitment_key'], row['reachable_blockers'], row['frontier_count'],
          row['chain_depth'], row['frontier_head'],
          allocations.get(row['commitment_key'], 0)]
         for row in sorted(blocked_rows, key=lambda r: r['commitment_key'])])

    # -- the class queues
    queue_fields = ['commitment_key', 'obligor_actor', 'commitment_day',
                    'effort_minutes', 'project_root', 'allocated_minutes']
    queues = (
        ('actionable_queue.tsv', 'ACTIONABLE', '\t'),
        ('deferred_queue.psv', 'DEFERRED', '|'),
    )
    for name, klass, separator in queues:
        items = [item for item in ordered if item['commitment_class'] == klass]
        files[name] = table_text(
            queue_fields, [[item[field] for field in queue_fields] for item in items],
            separator)

    files['withdrawn_register.csv'] = table_text(
        ['commitment_key', 'obligor_actor', 'commitment_day', 'effort_minutes',
         'source_class'],
        [[item['commitment_key'], item['obligor_actor'], item['commitment_day'],
          item['effort_minutes'], item['source_class']]
         for item in ordered if item['commitment_class'] == 'WITHDRAWN'])

    files['unresolvable.jsonl'] = jsonl_text(
        sorted(({'commitment_key': item['commitment_key'],
                 'reason_code': item['unresolvable_reason'],
                 'obligor_actor': item['obligor_actor'],
                 'commitment_day': item['commitment_day']}
                for item in ledger.values()
                if item['commitment_class'] == 'UNRESOLVABLE'),
               key=lambda row: (row['reason_code'], row['commitment_key'])))

    # -- cadence_debt.csv and waiver_trace.jsonl
    files['cadence_debt.csv'] = table_text(
        ['cadence_id', 'period_days', 'periods_elapsed', 'periods_discharged',
         'periods_waived', 'debt', 'max_streak'],
        [[row['cadence_id'], row['period_days'], row['periods_elapsed'],
          row['periods_discharged'], row['periods_waived'], row['debt'],
          row['max_streak']]
         for row in sorted(cadence_rows, key=lambda r: r['cadence_id'])])
    files['waiver_trace.jsonl'] = jsonl_text(
        [{'cadence_id': row['cadence_id'], 'period_index': row['period_index'],
          'effect': row['effect'], 'period_start': row['period_start']}
         for row in waiver_trace])

    # -- attention_allocation.csv and month_load_index.csv
    allocation_rows = []
    for item in ordered:
        if item['commitment_class'] not in ('ACTIONABLE', 'BLOCKED', 'DEFERRED'):
            continue
        if item['effort_minutes'] <= 0:
            continue
        allocation_rows.append([item['commitment_day'][:7], item['obligor_actor'],
                                item['commitment_key'], item['effort_minutes'],
                                item['allocated_minutes']])
    allocation_rows.sort(key=lambda row: (row[0], row[1], row[2]))
    files['attention_allocation.csv'] = table_text(
        ['year_month', 'obligor_actor', 'commitment_key', 'demand_minutes',
         'allocated_minutes'], allocation_rows)

    month_rows = []
    for pair in sorted(month_index):
        row = month_index[pair]
        month_rows.append([row['year_month'], row['obligor_actor'],
                           row['budget_source'], row['budget_minutes'],
                           row['reserve_minutes'], row['demand_minutes'],
                           row['allocated_minutes'], row['open_count']])
    month_rows.sort(key=lambda row: (row[0], row[1]))
    files['month_load_index.csv'] = table_text(
        ['year_month', 'obligor_actor', 'budget_source', 'budget_minutes',
         'reserve_minutes', 'demand_minutes', 'allocated_minutes', 'open_count'],
        month_rows)

    # -- escalation_queue.csv
    files['escalation_queue.csv'] = table_text(
        ['commitment_key', 'obligor_actor', 'commitment_class', 'effort_minutes',
         'allocated_minutes', 'shortfall_minutes', 'principal_debt',
         'chain_depth', 'trigger'],
        [[row['commitment_key'], row['obligor_actor'], row['commitment_class'],
          row['effort_minutes'], row['allocated_minutes'],
          row['shortfall_minutes'], row['principal_debt'], row['chain_depth'],
          row['trigger']] for row in escalations])

    # -- rollups
    actor_rollup = {}
    project_rollup = {}
    for item in ordered:
        for rollup, key in ((actor_rollup, item['obligor_actor']),
                            (project_rollup, item['project_root'])):
            entry = rollup.setdefault(key, {
                'ACTIONABLE': 0, 'BLOCKED': 0, 'DEFERRED': 0, 'SETTLED': 0,
                'UNRESOLVABLE': 0, 'WITHDRAWN': 0, 'commitment_count': 0,
                'open_effort_minutes': 0, 'allocated_minutes': 0})
            entry[item['commitment_class']] += 1
            entry['commitment_count'] += 1
            entry['allocated_minutes'] += item['allocated_minutes']
            if item['commitment_class'] in ('ACTIONABLE', 'BLOCKED', 'DEFERRED'):
                entry['open_effort_minutes'] += item['effort_minutes']
    files['actor_rollup.json'] = json_text(actor_rollup)
    files['project_rollup.json'] = json_text(project_rollup)

    # -- provenance_index.jsonl
    contribution = defaultdict(set)
    source_files = defaultdict(set)
    for assertion in assertions:
        contribution[assertion['commitment_key']].add(assertion['assertion_id'])
        source_files[assertion['commitment_key']].add(assertion['_feed_file'])
    state_ids = defaultdict(set)
    for row in rows:
        if row.kind != 'state':
            continue
        if row.reason in ('MALFORMED_ROW', 'FEED_RETIRED', 'OUT_OF_WINDOW',
                          'UNKNOWN_COMMITMENT'):
            continue
        state_ids[row.commitment_key].add(row.record_id)
    provenance = []
    for key in admitted:
        provenance.append({
            'commitment_key': key,
            'winning_assertion': ledger[key]['winning_assertion'],
            'contributing_assertions': sorted(contribution.get(key, ())),
            'source_files': sorted(source_files.get(key, ())),
            'state_assertions': sorted(state_ids.get(key, ())),
        })
    files['provenance_index.jsonl'] = jsonl_text(provenance)

    # -- audit figures and the identities
    class_counts = defaultdict(int)
    for item in ledger.values():
        class_counts[item['commitment_class']] += 1
    reject_counts = defaultdict(int)
    for row in rejects:
        reject_counts[row.reason] += 1
    applied_state_rows = sum(applied_counts.get(key, 0) for key in admitted)
    open_effort = sum(item['effort_minutes'] for item in ledger.values()
                      if item['commitment_class'] in
                      ('ACTIONABLE', 'BLOCKED', 'DEFERRED'))
    allocated_total = sum(item['allocated_minutes'] for item in ledger.values())
    figures = {
        'rows_ingested': len(rows),
        'rows_rejected': len(rejects),
        'rows_accepted': len(rows) - len(rejects),
        'commitments_admitted': len(admitted),
        'class_actionable': class_counts['ACTIONABLE'],
        'class_blocked': class_counts['BLOCKED'],
        'class_deferred': class_counts['DEFERRED'],
        'class_settled': class_counts['SETTLED'],
        'class_unresolvable': class_counts['UNRESOLVABLE'],
        'class_withdrawn': class_counts['WITHDRAWN'],
        'reject_ambiguous_identity': reject_counts['AMBIGUOUS_IDENTITY'],
        'reject_feed_retired': reject_counts['FEED_RETIRED'],
        'reject_illegal_transition': reject_counts['ILLEGAL_TRANSITION'],
        'reject_malformed_row': reject_counts['MALFORMED_ROW'],
        'reject_nonpositive_effort': reject_counts['NONPOSITIVE_EFFORT'],
        'reject_out_of_window': reject_counts['OUT_OF_WINDOW'],
        'reject_unknown_commitment': reject_counts['UNKNOWN_COMMITMENT'],
        'reject_unknown_principal': reject_counts['UNKNOWN_PRINCIPAL'],
        'reject_unknown_project': reject_counts['UNKNOWN_PROJECT'],
        'live_edges': len(live),
        'dropped_edges': len(dropped),
        'closure_pairs': len(closure_rows),
        'blocked_commitments': len(blocked_rows),
        'open_effort_minutes': open_effort,
        'allocated_minutes': allocated_total,
        'escalated_commitments': len(escalations),
        'cadence_debt_total': sum(row['debt'] for row in cadence_rows),
    }
    files['audit_totals.csv'] = table_text(
        ['metric', 'value'], [[name, figures[name]] for name in AUDIT_FIGURES])

    actor_open_effort = defaultdict(int)
    project_open_effort = defaultdict(int)
    for item in ledger.values():
        if item['commitment_class'] not in ('ACTIONABLE', 'BLOCKED', 'DEFERRED'):
            continue
        actor_open_effort[item['obligor_actor']] += item['effort_minutes']
        project_open_effort[item['project_root']] += item['effort_minutes']
    frontier_total = sum(row['frontier_count'] for row in blocked_rows)
    terminal_pairs = sum(1 for row in closure_rows if row['terminal'] == 'yes')
    residuals = {
        'I1_row_partition': figures['rows_accepted'] - (
            len(assertions) + applied_state_rows + len(live) + len(dropped)),
        'I2_class_partition': figures['commitments_admitted'] - sum(
            class_counts[name] for name in COMMITMENT_CLASSES),
        'I3_actor_effort': sum(actor_open_effort.values()) - open_effort,
        'I4_project_effort': sum(project_open_effort.values()) - open_effort,
        'I5_closure_frontier': frontier_total - terminal_pairs,
    }

    reconciliation = ['CALDERMOOR COMMITMENT CLOSURE']
    for name in RECONCILIATION_FIGURES:
        reconciliation.append('%s %d' % (name, figures[name]))
    for name in IDENTITY_NAMES:
        reconciliation.append('identity_%s %d' % (name, residuals[name]))
    files['reconciliation.txt'] = '\n'.join(reconciliation) + '\n'

    files['validation_report.json'] = json_text({
        'identities': {name: residuals[name] for name in IDENTITY_NAMES},
        'identities_checked': sorted(IDENTITY_NAMES),
        'all_residuals_zero': all(residuals[name] == 0 for name in IDENTITY_NAMES),
    })

    effect_counts = defaultdict(int)
    for waiver in waiver_trace:
        effect_counts[waiver['effect']] += 1
    files['run_manifest.json'] = json_text({
        'day_boundary_offset_minutes': DAY_OFFSET_MINUTES,
        'effort_floor_minutes': EFFORT_FLOOR_MINUTES,
        'effort_ceiling_minutes': EFFORT_CEILING_MINUTES,
        'allocation_floor_minutes': ALLOCATION_FLOOR_MINUTES,
        'window_start': WINDOW_START_TEXT,
        'window_end': WINDOW_END_TEXT,
        'reason_codes': sorted(REASON_CODES),
        'commitment_classes': sorted(COMMITMENT_CLASSES),
        'retired_feeds': list(references.retired_feeds),
        'split_surfaces': split_surfaces,
        'multi_hop_assertions': multi_hop,
        'order_tiebreaks_applied': order_tiebreaks,
        'edges_dropped_out_of_scope': sum(
            1 for _row, reason in dropped if reason == 'EDGE_OUT_OF_SCOPE'),
        'waivers_suppressing': effect_counts['SUPPRESSED'],
        'waivers_inert': effect_counts['INERT'],
        'waivers_lapsed': effect_counts['LAPSED'],
        'allocations_starved': starved,
        'illegal_transitions': reject_counts['ILLEGAL_TRANSITION'],
    })
    return files


# --------------------------------------------------------------------------
# Publishing


def publish(files, out_dir, program_path):
    """Stage the closure, then move it into the output directory.

    The staging directory sits beside the output directory when that is
    possible, so publishing is one rename per deliverable, and falls back to
    the system temporary directory when the enclosing directory is not
    writable.  Nothing reaches the output directory until every deliverable is
    staged, and the staging directory is always removed.
    """
    out_dir = os.path.abspath(out_dir)
    parent = os.path.dirname(out_dir) or '.'
    try:
        os.makedirs(parent, exist_ok=True)
        stage = tempfile.mkdtemp(prefix='.reconcile-stage-', dir=parent)
    except OSError:
        stage = tempfile.mkdtemp(prefix='reconcile-stage-')
    try:
        for name in sorted(files):
            write_text(os.path.join(stage, name), files[name])
        if program_path and os.path.isfile(program_path):
            shutil.copyfile(program_path, os.path.join(stage, 'reconcile.py'))
        else:
            write_text(os.path.join(stage, 'reconcile.py'), '')
        os.makedirs(out_dir, exist_ok=True)
        for name in sorted(os.listdir(out_dir)):
            path = os.path.join(out_dir, name)
            if name in DELIVERABLES:
                continue
            if os.path.isdir(path) and not os.path.islink(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
        for name in DELIVERABLES:
            source = os.path.join(stage, name)
            target = os.path.join(out_dir, name)
            if not os.path.isfile(source):
                continue
            try:
                os.replace(source, target)
            except OSError:
                shutil.copyfile(source, target)
                os.remove(source)
    finally:
        if os.path.isdir(stage):
            shutil.rmtree(stage, ignore_errors=True)


def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: reconcile.py DATA_DIR OUT_DIR\n')
        return 2
    data_dir = os.path.abspath(argv[1])
    out_dir = os.path.abspath(argv[2])
    if not os.path.isdir(data_dir):
        sys.stderr.write('no extract directory at %s\n' % argv[1])
        return 2
    if out_dir == data_dir or data_dir.startswith(out_dir + os.sep):
        sys.stderr.write('the output directory must lie outside the extract\n')
        return 2
    program_path = None
    if '__file__' in globals():
        program_path = os.path.abspath(__file__)
    files = run(data_dir)
    publish(files, out_dir, program_path)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
