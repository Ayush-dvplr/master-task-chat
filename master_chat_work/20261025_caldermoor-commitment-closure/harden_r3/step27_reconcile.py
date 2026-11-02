#!/usr/bin/env python3
"""Reconcile a Caldermoor commitment extract into its settlement closure.

Usage:
    reconcile.py DATA_DIR OUT_DIR

Reads one extract directory and publishes the twenty-nine deliverables of the
output contract into OUT_DIR.  The run is deterministic: no wall clock, host
name or local path reaches any deliverable.
"""

import datetime
import json
import os
import re
import shutil
import sys
import unicodedata

# ---------------------------------------------------------------------------
# Protocol constants
# ---------------------------------------------------------------------------

WINDOW_START_TEXT = '2032-03-01T00:00Z'
WINDOW_END_TEXT = '2032-12-01T00:00Z'
DAY_BOUNDARY_OFFSET_MINUTES = 240
EFFORT_FLOOR = 15
EFFORT_CEILING = 480
ALLOCATION_FLOOR = 15
BLOCKED_RESERVE_MINUTES = 30
WAIVED_RESERVE_MINUTES = 15
WAIVER_ALLOWANCE = 4
ESCALATION_DEBT_THRESHOLD = 4
ESCALATION_DEPTH_THRESHOLD = 2
ESCALATION_MONTH = '2032-11'

REASON_CODES = [
    'MALFORMED_ROW',
    'FEED_RETIRED',
    'OUT_OF_WINDOW',
    'UNKNOWN_PRINCIPAL',
    'AMBIGUOUS_IDENTITY',
    'UNKNOWN_PROJECT',
    'NONPOSITIVE_EFFORT',
    'UNKNOWN_COMMITMENT',
    'ILLEGAL_TRANSITION',
]

COMMITMENT_CLASSES = [
    'ACTIONABLE',
    'BLOCKED',
    'DEFERRED',
    'SETTLED',
    'UNRESOLVABLE',
    'WITHDRAWN',
]

OPEN_CLASSES = ('ACTIONABLE', 'BLOCKED', 'DEFERRED')
STATES = ('OPEN', 'SETTLED', 'DEFERRED', 'WITHDRAWN')

ALLOWED_TRANSITIONS = frozenset([
    ('OPEN', 'SETTLED'),
    ('OPEN', 'DEFERRED'),
    ('OPEN', 'WITHDRAWN'),
    ('DEFERRED', 'OPEN'),
    ('DEFERRED', 'WITHDRAWN'),
])

SOURCE_RANK = {
    'vault': 6,
    'desk': 5,
    'bridge': 4,
    'partner': 3,
    'mirror': 2,
    'import': 1,
    'relay': 1,
    'legacy': 0,
}

EFFORT_UNIT_FACTOR = {'minutes': 1, 'hours': 60, 'halfdays': 240}
UNITLESS_LAYOUT_FACTOR = 60  # the .fixed and .rec commitment layouts carry hours

IDENTITY_NAMES = [
    'I1_row_partition',
    'I2_class_partition',
    'I3_actor_effort',
    'I4_project_effort',
    'I5_closure_frontier',
]

COMMITMENT_FIELDS = (
    'assertion_id', 'commitment_key', 'obligor', 'obligee', 'project_ref',
    'due_at', 'effort', 'cadence_ref', 'observed_at',
)
STATE_FIELDS = ('state_id', 'commitment_key', 'to_state', 'observed_at')
EDGE_FIELDS = ('edge_id', 'dependent_key', 'blocker_key', 'asserted_at')

COMMITMENT_FIXED_COLUMNS = (
    ('assertion_id', 12), ('commitment_key', 12), ('obligor', 40),
    ('obligee', 40), ('project_ref', 10), ('due_at', 18), ('effort', 8),
    ('cadence_ref', 10), ('observed_at', 18),
)
STATE_FIXED_COLUMNS = (
    ('state_id', 12), ('commitment_key', 12), ('to_state', 12),
    ('observed_at', 18),
)
EDGE_FIXED_COLUMNS = (
    ('edge_id', 12), ('dependent_key', 12), ('blocker_key', 12),
    ('asserted_at', 18),
)

DELIMITERS = {'.csv': ',', '.tsv': '\t', '.psv': '|'}

# ---------------------------------------------------------------------------
# Instants and days
# ---------------------------------------------------------------------------

_INSTANT_RE = re.compile(r'\A(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})Z\Z')
_EPOCH = datetime.datetime(2000, 1, 1)
_INT_RE = re.compile(r'\A-?\d+\Z')


def parse_instant(text):
    """Return minutes since the internal epoch, or None when not an instant."""
    if not isinstance(text, str):
        return None
    m = _INSTANT_RE.match(text)
    if m is None:
        return None
    year, month, day, hour, minute = (int(g) for g in m.groups())
    try:
        stamp = datetime.datetime(year, month, day, hour, minute)
    except ValueError:
        return None
    return (stamp - _EPOCH).days * 1440 + (stamp - _EPOCH).seconds // 60


def format_instant(minutes):
    stamp = _EPOCH + datetime.timedelta(minutes=minutes)
    return '%04d-%02d-%02dT%02d:%02dZ' % (
        stamp.year, stamp.month, stamp.day, stamp.hour, stamp.minute)


def commitment_day(minutes):
    stamp = _EPOCH + datetime.timedelta(
        minutes=minutes - DAY_BOUNDARY_OFFSET_MINUTES)
    return '%04d-%02d-%02d' % (stamp.year, stamp.month, stamp.day)


WINDOW_START = parse_instant(WINDOW_START_TEXT)
WINDOW_END = parse_instant(WINDOW_END_TEXT)


def in_window(minutes):
    return WINDOW_START <= minutes < WINDOW_END


def is_integer_text(text):
    return isinstance(text, str) and _INT_RE.match(text) is not None


def clamp_effort(value):
    if value < EFFORT_FLOOR:
        return EFFORT_FLOOR
    if value > EFFORT_CEILING:
        return EFFORT_CEILING
    return value


# ---------------------------------------------------------------------------
# The comparison fold
# ---------------------------------------------------------------------------

_FOLD_DELETED = ".-_'"


def fold(text):
    value = unicodedata.normalize('NFC', text)
    value = value.strip()
    value = value.casefold()
    for char in _FOLD_DELETED:
        value = value.replace(char, '')
    value = ' '.join(value.split())
    return value.strip()


# ---------------------------------------------------------------------------
# Layout readers
#
# Every reader yields (record_index, field_mapping, structurally_sound).
# ---------------------------------------------------------------------------

def read_text(path):
    with open(path, 'r', encoding='utf-8', newline='') as handle:
        return handle.read()


def _record_lines(text):
    lines = text.split('\n')
    if lines and lines[-1] == '':
        lines.pop()
    return lines


def read_delimited(path, delimiter):
    lines = _record_lines(read_text(path))
    if not lines:
        return []
    header = lines[0].split(delimiter)
    records = []
    for index, line in enumerate(lines[1:]):
        fields = line.split(delimiter)
        records.append((index, dict(zip(header, fields)),
                        len(fields) == len(header)))
    return records


def read_jsonl(path):
    records = []
    for index, line in enumerate(_record_lines(read_text(path))):
        try:
            parsed = json.loads(line)
        except ValueError:
            records.append((index, {}, False))
            continue
        if not isinstance(parsed, dict):
            records.append((index, {}, False))
            continue
        records.append((index, {k: _json_scalar(v) for k, v in parsed.items()},
                        True))
    return records


def _json_scalar(value):
    if isinstance(value, str):
        return value
    if value is None:
        return 'null'
    if value is True:
        return 'true'
    if value is False:
        return 'false'
    if isinstance(value, int):
        return str(value)
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


_KV_LINE_RE = re.compile(r'\A([^:\n]+):(?: (.*))?\Z')


def read_kv(path):
    text = read_text(path)
    if text.endswith('\n'):
        text = text[:-1]
    if text == '':
        return []
    records = []
    for index, chunk in enumerate(text.split('\n\n')):
        fields = {}
        sound = True
        for line in chunk.split('\n'):
            m = _KV_LINE_RE.match(line)
            if m is None:
                sound = False
                continue
            fields[m.group(1)] = m.group(2) if m.group(2) is not None else ''
        records.append((index, fields, sound))
    return records


def read_rec(path):
    records = []
    for index, line in enumerate(_record_lines(read_text(path))):
        fields = {}
        sound = True
        for segment in line.split(';'):
            if '=' not in segment:
                sound = False
                continue
            name, value = segment.split('=', 1)
            fields[name] = value
        records.append((index, fields, sound))
    return records


_XML_ELEMENT_RE = re.compile(r'\A<([A-Za-z_][\w.-]*)((?:\s+[A-Za-z_][\w.-]*'
                             r'="[^"<>]*")*)\s*/>\Z')
_XML_ATTR_RE = re.compile(r'([A-Za-z_][\w.-]*)="([^"<>]*)"')
_XML_ENTITIES = (('&lt;', '<'), ('&gt;', '>'), ('&quot;', '"'),
                 ('&apos;', "'"), ('&amp;', '&'))


def _xml_unescape(value):
    for escaped, plain in _XML_ENTITIES:
        value = value.replace(escaped, plain)
    return value


def read_xml(path):
    records = []
    index = 0
    for line in _record_lines(read_text(path)):
        stripped = line.strip()
        if stripped == '':
            continue
        if stripped.startswith('<?') or stripped.startswith('<!'):
            continue
        if not stripped.endswith('/>'):
            # the opening or closing tag of the single wrapping element
            continue
        m = _XML_ELEMENT_RE.match(stripped)
        if m is None:
            records.append((index, {}, False))
            index += 1
            continue
        fields = {name: _xml_unescape(value)
                  for name, value in _XML_ATTR_RE.findall(m.group(2))}
        records.append((index, fields, True))
        index += 1
    return records


def read_fixed(path, columns):
    records = []
    for index, line in enumerate(_record_lines(read_text(path))):
        fields = {}
        offset = 0
        for name, width in columns:
            fields[name] = line[offset:offset + width].strip()
            offset += width
        records.append((index, fields, True))
    return records


def read_records(path, kind):
    """Read one feed file under the layout its extension names."""
    extension = os.path.splitext(path)[1]
    if extension in DELIMITERS:
        return read_delimited(path, DELIMITERS[extension])
    if extension == '.jsonl':
        return read_jsonl(path)
    if extension == '.kv':
        return read_kv(path)
    if extension == '.rec':
        return read_rec(path)
    if extension == '.xml':
        return read_xml(path)
    if extension == '.fixed':
        columns = {'commitment': COMMITMENT_FIXED_COLUMNS,
                   'state': STATE_FIXED_COLUMNS,
                   'edge': EDGE_FIXED_COLUMNS}[kind]
        return read_fixed(path, columns)
    return []


def layout_carries_effort_unit(path):
    return os.path.splitext(path)[1] not in ('.fixed', '.rec')


def read_table(directory, name):
    """Read one reference table, tolerating its absence."""
    path = os.path.join(directory, name)
    if not os.path.exists(path):
        return []
    return read_records(path, 'reference')


# ---------------------------------------------------------------------------
# Identity resolution
# ---------------------------------------------------------------------------

RESOLVED = 'RESOLVED'
UNKNOWN_PRINCIPAL = 'UNKNOWN_PRINCIPAL'
AMBIGUOUS_IDENTITY = 'AMBIGUOUS_IDENTITY'


class IdentityRegister(object):

    def __init__(self, handle_actor, alias_edges):
        self.handle_actor = handle_actor
        self.alias_edges = alias_edges
        self._cache = {}

    def resolve(self, surface, instant):
        """Return (outcome, actor_id, hop_count) for a surface at an instant."""
        folded = fold(surface)
        key = (folded, instant)
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        distance = {folded: 0}
        frontier = [folded]
        found = {}
        position = 0
        while position < len(frontier):
            current = frontier[position]
            position += 1
            depth = distance[current]
            actor = self.handle_actor.get(current)
            if actor is not None and actor not in found:
                found[actor] = depth
            for target, start, end in self.alias_edges.get(current, ()):
                if start <= instant < end and target not in distance:
                    distance[target] = depth + 1
                    frontier.append(target)
        if not found:
            outcome = (UNKNOWN_PRINCIPAL, '', 0)
        elif len(found) > 1:
            outcome = (AMBIGUOUS_IDENTITY, '', 0)
        else:
            actor, hops = next(iter(found.items()))
            outcome = (RESOLVED, actor, hops)
        self._cache[key] = outcome
        return outcome


def load_identity(directory):
    """Build the roster and the alias graph from the extract."""
    roster_lines = []
    for name in sorted(os.listdir(directory)):
        if not name.startswith('roster_'):
            continue
        for _index, fields, sound in read_records(
                os.path.join(directory, name), 'reference'):
            if not sound:
                continue
            actor = fields.get('actor_id', '')
            handle = fields.get('canonical_handle', '')
            if actor == '' or handle == '':
                continue
            roster_lines.append((actor, handle))

    spelling_counts = {}
    handle_actor = {}
    for actor, handle in roster_lines:
        spelling_counts.setdefault(actor, {})
        spelling_counts[actor][handle] = spelling_counts[actor].get(handle,
                                                                    0) + 1
        handle_actor.setdefault(fold(handle), actor)

    canonical = {}
    for actor in sorted(spelling_counts):
        counts = spelling_counts[actor]
        best = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))[0]
        canonical[actor] = best[0]

    assertions = set()
    for name in sorted(os.listdir(directory)):
        if not name.startswith('aliases_'):
            continue
        for _index, fields, sound in read_records(
                os.path.join(directory, name), 'reference'):
            if not sound:
                continue
            start = parse_instant(fields.get('scope_start', ''))
            end = parse_instant(fields.get('scope_end', ''))
            if start is None or end is None:
                continue
            surface = fold(fields.get('surface', ''))
            target = fold(fields.get('target', ''))
            if surface == '' or target == '':
                continue
            assertions.add((surface, target, start, end))

    alias_edges = {}
    for surface, target, start, end in sorted(assertions):
        if start >= end:
            # an interval whose start is at or after its end holds nowhere
            continue
        alias_edges.setdefault(surface, []).append((target, start, end))

    return IdentityRegister(handle_actor, alias_edges), canonical


# ---------------------------------------------------------------------------
# Project register
# ---------------------------------------------------------------------------

UNKNOWN_PROJECT = 'UNKNOWN_PROJECT'


class ProjectRegister(object):

    def __init__(self, revisions, renames):
        self.revisions = revisions  # code -> [(revised_at, revision, row)]
        self.renames = renames      # code -> [(effective_at, event_id, to)]
        self._roots = {}
        self._resolve_cache = {}

    def declares(self, code):
        return code in self.revisions

    def resolve(self, code, instant):
        key = (code, instant)
        hit = self._resolve_cache.get(key)
        if hit is not None:
            return hit
        current = code
        seen = {current}
        while True:
            applicable = [entry for entry in self.renames.get(current, ())
                          if entry[0] <= instant]
            if not applicable:
                break
            target = applicable[-1][2]
            if target in seen:
                break
            seen.add(target)
            current = target
        self._resolve_cache[key] = current
        return current

    def governing(self, code, instant):
        entries = self.revisions.get(code)
        if not entries:
            return None
        chosen = None
        for revised_at, revision, row in entries:
            if revised_at <= instant:
                chosen = row
        if chosen is None:
            chosen = entries[0][2]
        return chosen

    def latest(self, code):
        entries = self.revisions.get(code)
        if not entries:
            return None
        return entries[-1][2]

    def root(self, code):
        hit = self._roots.get(code)
        if hit is not None:
            return hit
        current = code
        seen = [current]
        while True:
            row = self.latest(current)
            if row is None:
                break
            parent = row.get('parent_code', '')
            if parent == '' or parent in seen:
                break
            seen.append(parent)
            current = parent
        self._roots[code] = current
        return current


def load_projects(directory):
    revisions = {}
    for _index, fields, sound in read_table(directory, 'project_registry.csv'):
        if not sound:
            continue
        code = fields.get('project_code', '')
        if code == '':
            continue
        revised_at = parse_instant(fields.get('revised_at', ''))
        if revised_at is None:
            continue
        revision = fields.get('revision', '0')
        revision = int(revision) if is_integer_text(revision) else 0
        revisions.setdefault(code, []).append((revised_at, revision, fields))
    for code in revisions:
        revisions[code].sort(key=lambda entry: (entry[0], entry[1]))

    renames = {}
    for _index, fields, sound in read_table(directory, 'project_events.tsv'):
        if not sound or fields.get('event_type', '') != 'RENAME':
            continue
        code = fields.get('project_code', '')
        target = fields.get('payload', '')
        effective_at = parse_instant(fields.get('effective_at', ''))
        if code == '' or target == '' or effective_at is None:
            continue
        renames.setdefault(code, []).append(
            (effective_at, fields.get('event_id', ''), target))
    for code in renames:
        renames[code].sort()

    return ProjectRegister(revisions, renames)


# ---------------------------------------------------------------------------
# Feed manifest
# ---------------------------------------------------------------------------

def load_manifest(directory):
    governing = {}
    for _index, fields, sound in read_table(directory, 'feed_manifest.csv'):
        if not sound:
            continue
        name = fields.get('feed_file', '')
        if name == '':
            continue
        revision = fields.get('revision', '')
        revision = int(revision) if is_integer_text(revision) else 0
        held = governing.get(name)
        if held is None or revision > held[0]:
            governing[name] = (revision, fields.get('retired_at', ''),
                               fields.get('source_class', ''))
    return governing


def feed_class_from_name(name):
    body = os.path.splitext(name)[0]
    parts = body.split('_')
    for part in parts[1:]:
        if part in SOURCE_RANK:
            return part
    return ''


# ---------------------------------------------------------------------------
# Feed ingestion
# ---------------------------------------------------------------------------

class Feed(object):

    def __init__(self, name, path, kind, source_class, retired_at):
        self.name = name
        self.path = path
        self.kind = kind
        self.source_class = source_class
        self.rank = SOURCE_RANK.get(source_class, -1)
        self.retired_at = retired_at
        self.carries_effort_unit = layout_carries_effort_unit(path)


def discover_feeds(directory, manifest):
    feeds = []
    for name in sorted(os.listdir(directory)):
        path = os.path.join(directory, name)
        if not os.path.isfile(path):
            continue
        if name.startswith('commitments_'):
            kind = 'commitment'
        elif name.startswith('states_'):
            kind = 'state'
        elif name.startswith('edges_'):
            kind = 'edge'
        else:
            continue
        entry = manifest.get(name)
        source_class = entry[2] if entry else ''
        if source_class not in SOURCE_RANK:
            source_class = feed_class_from_name(name)
        retired_at = parse_instant(entry[1]) if entry else None
        feeds.append(Feed(name, path, kind, source_class, retired_at))
    return feeds


class Reject(object):
    __slots__ = ('feed_file', 'row_index', 'record_kind', 'record_id',
                 'commitment_key', 'reason_code')

    def __init__(self, feed_file, row_index, record_kind, record_id,
                 commitment_key, reason_code):
        self.feed_file = feed_file
        self.row_index = row_index
        self.record_kind = record_kind
        self.record_id = record_id
        self.commitment_key = commitment_key
        self.reason_code = reason_code

    def sort_key(self):
        return (self.reason_code, self.feed_file, self.row_index,
                self.record_id)

    def row(self):
        return [self.feed_file, str(self.row_index), self.record_kind,
                self.record_id, self.commitment_key, self.reason_code]


# ---------------------------------------------------------------------------
# Largest remainder distribution
# ---------------------------------------------------------------------------

def distribute(total, items):
    """Share `total` across (key, weight) pairs by largest remainder."""
    weight_sum = sum(weight for _key, weight in items)
    if total <= 0 or weight_sum <= 0:
        return {key: 0 for key, _weight in items}
    shares = {}
    remainders = []
    handed = 0
    for key, weight in items:
        quotient, remainder = divmod(total * weight, weight_sum)
        shares[key] = quotient
        handed += quotient
        remainders.append((remainder, key))
    remainders.sort(key=lambda pair: (-pair[0], pair[1]))
    for index in range(total - handed):
        shares[remainders[index][1]] += 1
    return shares


# ---------------------------------------------------------------------------
# Strongly connected components, for the live dependency cycles
# ---------------------------------------------------------------------------

def nodes_on_cycles(adjacency):
    """Return the set of nodes lying on a cycle of the given digraph."""
    index_of = {}
    low = {}
    on_stack = {}
    stack = []
    counter = [0]
    cyclic = set()
    for root in sorted(adjacency):
        if root in index_of:
            continue
        work = [(root, 0)]
        while work:
            node, child = work[-1]
            if child == 0:
                index_of[node] = low[node] = counter[0]
                counter[0] += 1
                stack.append(node)
                on_stack[node] = True
            neighbours = adjacency.get(node, ())
            advanced = False
            while child < len(neighbours):
                nxt = neighbours[child]
                child += 1
                if nxt not in index_of:
                    work[-1] = (node, child)
                    work.append((nxt, 0))
                    advanced = True
                    break
                if on_stack.get(nxt):
                    low[node] = min(low[node], index_of[nxt])
            if advanced:
                continue
            work[-1] = (node, child)
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
            if low[node] == index_of[node]:
                component = []
                while True:
                    member = stack.pop()
                    on_stack[member] = False
                    component.append(member)
                    if member == node:
                        break
                if len(component) > 1:
                    cyclic.update(component)
                elif node in adjacency.get(node, ()):
                    cyclic.add(node)
    return cyclic


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def json_line(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True)


def json_document(obj):
    return json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=True)


class Publisher(object):
    """Collects every deliverable in memory and writes it once, atomically."""

    def __init__(self):
        self.files = {}

    def delimited(self, name, delimiter, header, rows):
        lines = [delimiter.join(header)]
        for row in rows:
            lines.append(delimiter.join(row))
        self.files[name] = '\n'.join(lines) + '\n'

    def jsonl(self, name, objects):
        self.files[name] = ''.join(json_line(obj) + '\n' for obj in objects)

    def document(self, name, obj):
        self.files[name] = json_document(obj) + '\n'

    def text(self, name, lines):
        self.files[name] = ''.join(line + '\n' for line in lines)

    def raw(self, name, content):
        self.files[name] = content


# ---------------------------------------------------------------------------
# The closure
# ---------------------------------------------------------------------------

def reconcile(data_dir):
    manifest = load_manifest(data_dir)
    identity, canonical_handles = load_identity(data_dir)
    projects = load_projects(data_dir)
    feeds = discover_feeds(data_dir, manifest)

    rejects = []
    rows_ingested = 0

    # -- commitment assertions ---------------------------------------------
    assertions = []
    for feed in (f for f in feeds if f.kind == 'commitment'):
        for index, fields, sound in read_records(feed.path, 'commitment'):
            rows_ingested += 1
            record_id = fields.get('assertion_id', '')
            key = fields.get('commitment_key', '')

            def reject(code):
                rejects.append(Reject(feed.name, index, 'commitment',
                                      record_id, key, code))

            malformed = not sound
            if not malformed:
                for name in COMMITMENT_FIELDS:
                    if name not in fields:
                        malformed = True
                        break
            if not malformed and feed.carries_effort_unit \
                    and 'effort_unit' not in fields:
                malformed = True

            due_at = observed_at = None
            effort_text = fields.get('effort', '')
            if not malformed:
                due_at = parse_instant(fields.get('due_at', ''))
                observed_at = parse_instant(fields.get('observed_at', ''))
                if due_at is None or observed_at is None:
                    malformed = True
            if not malformed:
                if effort_text == '' or effort_text == 'null':
                    pass
                elif is_integer_text(effort_text):
                    if int(effort_text) > 0 and feed.carries_effort_unit \
                            and fields.get('effort_unit', '') \
                            not in EFFORT_UNIT_FACTOR:
                        malformed = True
                else:
                    malformed = True
            if malformed:
                reject('MALFORMED_ROW')
                continue

            if feed.retired_at is not None and observed_at >= feed.retired_at:
                reject('FEED_RETIRED')
                continue
            if not in_window(due_at):
                reject('OUT_OF_WINDOW')
                continue

            obligor_outcome, obligor_actor, obligor_hops = identity.resolve(
                fields['obligor'], observed_at)
            if obligor_outcome != RESOLVED:
                reject(obligor_outcome)
                continue

            project_code = projects.resolve(fields['project_ref'], observed_at)
            if not projects.declares(project_code):
                reject('UNKNOWN_PROJECT')
                continue

            if is_integer_text(effort_text) and int(effort_text) <= 0:
                reject('NONPOSITIVE_EFFORT')
                continue

            if effort_text == 'null':
                effort_minutes = 0
                effort_origin = 'DECLARED_ZERO'
            elif effort_text == '':
                revision = projects.governing(project_code, observed_at)
                default = revision.get('default_effort', '') if revision else ''
                raw = int(default) if is_integer_text(default) else 0
                effort_minutes = clamp_effort(raw)
                effort_origin = 'DEFAULTED'
            else:
                if feed.carries_effort_unit:
                    factor = EFFORT_UNIT_FACTOR[fields['effort_unit']]
                else:
                    factor = UNITLESS_LAYOUT_FACTOR
                effort_minutes = clamp_effort(int(effort_text) * factor)
                effort_origin = 'STATED'

            obligee_outcome, obligee_actor, _hops = identity.resolve(
                fields['obligee'], due_at)
            obligee_status = {RESOLVED: 'RESOLVED',
                              AMBIGUOUS_IDENTITY: 'AMBIGUOUS',
                              UNKNOWN_PRINCIPAL: 'UNKNOWN'}[obligee_outcome]

            assertions.append({
                'assertion_id': record_id,
                'commitment_key': key,
                'obligor_actor': obligor_actor,
                'obligor_surface_folded': fold(fields['obligor']),
                'obligor_hops': obligor_hops,
                'obligee_actor': obligee_actor,
                'obligee_status': obligee_status,
                'project_code': project_code,
                'project_root': projects.root(project_code),
                'due_at': fields['due_at'],
                'due_at_minutes': due_at,
                'commitment_day': commitment_day(due_at),
                'effort_minutes': effort_minutes,
                'effort_origin': effort_origin,
                'cadence_ref': fields['cadence_ref'],
                'observed_at': fields['observed_at'],
                'observed_at_minutes': observed_at,
                'source_class': feed.source_class,
                'feed_file': feed.name,
                'feed_rank': feed.rank,
                'row_index': index,
            })

    by_key = {}
    for assertion in assertions:
        by_key.setdefault(assertion['commitment_key'], []).append(assertion)

    def commitment_order_key(assertion):
        instant = assertion['observed_at_minutes']
        if assertion['source_class'] == 'desk':
            instant = -instant
        return (assertion['feed_rank'], instant, assertion['assertion_id'])

    winners = {}
    for key in by_key:
        ordered = sorted(by_key[key], key=commitment_order_key)
        winners[key] = ordered[-1]
    admitted = set(winners)

    # -- state assertions ---------------------------------------------------
    state_rows = []
    for feed in (f for f in feeds if f.kind == 'state'):
        for index, fields, sound in read_records(feed.path, 'state'):
            rows_ingested += 1
            record_id = fields.get('state_id', '')
            key = fields.get('commitment_key', '')

            def reject(code):
                rejects.append(Reject(feed.name, index, 'state', record_id,
                                      key, code))

            malformed = not sound
            if not malformed:
                for name in STATE_FIELDS:
                    if name not in fields:
                        malformed = True
                        break
            observed_at = None
            if not malformed:
                observed_at = parse_instant(fields.get('observed_at', ''))
                if observed_at is None or fields.get('to_state') not in STATES:
                    malformed = True
            if malformed:
                reject('MALFORMED_ROW')
                continue
            if feed.retired_at is not None and observed_at >= feed.retired_at:
                reject('FEED_RETIRED')
                continue
            if not in_window(observed_at):
                reject('OUT_OF_WINDOW')
                continue
            if key not in admitted:
                reject('UNKNOWN_COMMITMENT')
                continue
            state_rows.append({
                'state_id': record_id,
                'commitment_key': key,
                'to_state': fields['to_state'],
                'observed_at_minutes': observed_at,
                'source_class': feed.source_class,
                'feed_rank': feed.rank,
                'feed_file': feed.name,
                'row_index': index,
            })

    def state_order_key(row):
        instant = row['observed_at_minutes']
        if row['source_class'] in ('desk', 'bridge'):
            instant = -instant
        return (row['feed_rank'], instant, row['state_id'])

    states_by_key = {}
    for row in state_rows:
        states_by_key.setdefault(row['commitment_key'], []).append(row)

    resolved_state = {}
    state_seen = {}
    state_applied = {}
    governing_class = {}
    applied_state_rows = 0
    for key in admitted:
        rows = sorted(states_by_key.get(key, []), key=state_order_key)
        held = 'OPEN'
        applied = 0
        held_class = ''
        for row in rows:
            if (held, row['to_state']) in ALLOWED_TRANSITIONS:
                held = row['to_state']
                applied += 1
                held_class = row['source_class']
            else:
                rejects.append(Reject(row['feed_file'], row['row_index'],
                                      'state', row['state_id'], key,
                                      'ILLEGAL_TRANSITION'))
        resolved_state[key] = held
        state_seen[key] = len(rows)
        state_applied[key] = applied
        governing_class[key] = held_class
        applied_state_rows += applied

    holding = {key for key in admitted
               if resolved_state[key] in ('OPEN', 'DEFERRED')}

    # -- edge rows ----------------------------------------------------------
    live_edges = []
    dropped_edges = []
    for feed in (f for f in feeds if f.kind == 'edge'):
        for index, fields, sound in read_records(feed.path, 'edge'):
            rows_ingested += 1
            record_id = fields.get('edge_id', '')
            dependent = fields.get('dependent_key', '')
            blocker = fields.get('blocker_key', '')

            def reject(code):
                rejects.append(Reject(feed.name, index, 'edge', record_id,
                                      dependent, code))

            malformed = not sound
            if not malformed:
                for name in EDGE_FIELDS:
                    if name not in fields:
                        malformed = True
                        break
            asserted_at = None
            if not malformed:
                asserted_at = parse_instant(fields.get('asserted_at', ''))
                if asserted_at is None:
                    malformed = True
            if malformed:
                reject('MALFORMED_ROW')
                continue
            if feed.retired_at is not None and asserted_at >= feed.retired_at:
                reject('FEED_RETIRED')
                continue
            if not in_window(asserted_at):
                reject('OUT_OF_WINDOW')
                continue

            edge = {
                'edge_id': record_id,
                'dependent_key': dependent,
                'blocker_key': blocker,
                'asserted_at': fields['asserted_at'],
                'asserted_at_minutes': asserted_at,
                'dependent_actor': '',
                'blocker_actor': '',
            }
            if dependent == blocker:
                edge['drop_reason'] = 'EDGE_SELF'
                dropped_edges.append(edge)
                continue
            if dependent not in admitted or blocker not in admitted:
                edge['drop_reason'] = 'EDGE_DANGLING'
                dropped_edges.append(edge)
                continue
            dep_outcome, dep_actor, _h = identity.resolve(
                winners[dependent]['obligor_surface'], asserted_at) \
                if False else identity.resolve(
                    winners[dependent]['obligor_surface_raw'], asserted_at)
            blk_outcome, blk_actor, _h2 = identity.resolve(
                winners[blocker]['obligor_surface_raw'], asserted_at)
            if dep_outcome != RESOLVED or blk_outcome != RESOLVED:
                edge['drop_reason'] = 'EDGE_OUT_OF_SCOPE'
                dropped_edges.append(edge)
                continue
            edge['dependent_actor'] = dep_actor
            edge['blocker_actor'] = blk_actor
            live_edges.append(edge)

    # -- blocking graph -----------------------------------------------------
    blocking = {}
    for edge in live_edges:
        if edge['blocker_key'] in holding:
            targets = blocking.setdefault(edge['dependent_key'], [])
            if edge['blocker_key'] not in targets:
                targets.append(edge['blocker_key'])
    for node in blocking:
        blocking[node].sort()

    cyclic = nodes_on_cycles(blocking)
    blocked = {key for key in blocking if key not in cyclic}

    closure_pairs = []
    closure_stats = {}
    for key in sorted(blocked):
        distance = {}
        frontier = [key]
        depth = 0
        distance[key] = 0
        position = 0
        while position < len(frontier):
            current = frontier[position]
            position += 1
            for target in blocking.get(current, ()):
                if target not in distance:
                    distance[target] = distance[current] + 1
                    frontier.append(target)
        reached = sorted(node for node in distance if node != key)
        terminal_count = 0
        greatest = 0
        for node in reached:
            terminal = node not in blocking
            if terminal:
                terminal_count += 1
            if distance[node] > greatest:
                greatest = distance[node]
            closure_pairs.append({
                'dependent_key': key,
                'blocker_key': node,
                'hop_distance': distance[node],
                'blocker_state': resolved_state[node],
                'terminal': 'yes' if terminal else 'no',
            })
        terminals = [node for node in reached if node not in blocking]
        closure_stats[key] = {
            'reachable_blockers': len(reached),
            'frontier_count': terminal_count,
            'chain_depth': greatest,
            'frontier_head': terminals[0] if terminals else '',
        }
        del depth

    # -- commitment classes -------------------------------------------------
    commitment_class = {}
    unresolvable_reason = {}
    for key in admitted:
        state = resolved_state[key]
        if state == 'SETTLED':
            commitment_class[key] = 'SETTLED'
        elif state == 'WITHDRAWN':
            commitment_class[key] = 'WITHDRAWN'
        elif key in cyclic:
            commitment_class[key] = 'UNRESOLVABLE'
            unresolvable_reason[key] = 'CIRCULAR_DEPENDENCY'
        elif winners[key]['obligee_status'] == 'AMBIGUOUS':
            commitment_class[key] = 'UNRESOLVABLE'
            unresolvable_reason[key] = 'AMBIGUOUS_COUNTERPARTY'
        elif key in blocked:
            commitment_class[key] = 'BLOCKED'
        elif state == 'DEFERRED':
            commitment_class[key] = 'DEFERRED'
        else:
            commitment_class[key] = 'ACTIONABLE'

    chain_depth = {}
    for key in admitted:
        if commitment_class[key] == 'BLOCKED' and key in closure_stats:
            chain_depth[key] = closure_stats[key]['chain_depth']
        else:
            chain_depth[key] = 0

    # -- cadences -----------------------------------------------------------
    cadence_rows = {}
    for _index, fields, sound in read_table(data_dir, 'cadence_register.csv'):
        if not sound:
            continue
        cadence_id = fields.get('cadence_id', '')
        if cadence_id == '':
            continue
        revision = fields.get('revision', '0')
        revision = int(revision) if is_integer_text(revision) else 0
        held = cadence_rows.get(cadence_id)
        if held is None or revision > held[0]:
            cadence_rows[cadence_id] = (revision, fields)

    cadences = {}
    for cadence_id in sorted(cadence_rows):
        fields = cadence_rows[cadence_id][1]
        anchor_at = parse_instant(fields.get('anchor_at', ''))
        period_days = fields.get('period_days', '')
        period_days = int(period_days) if is_integer_text(period_days) else 0
        owner = ''
        if anchor_at is not None:
            outcome, actor, _h = identity.resolve(fields.get('obligor', ''),
                                                  anchor_at)
            if outcome == RESOLVED:
                owner = actor
        length = period_days * 1440
        elapsed = 0
        if anchor_at is not None and length > 0 and anchor_at < WINDOW_END:
            span = WINDOW_END - anchor_at
            elapsed = span // length + (1 if span % length else 0)
        cadences[cadence_id] = {
            'cadence_id': cadence_id,
            'anchor_at': anchor_at,
            'period_days': period_days,
            'period_length': length,
            'owner': owner,
            'periods_elapsed': elapsed,
        }

    discharged = {}
    for key in admitted:
        if commitment_class[key] != 'SETTLED':
            continue
        cadence_id = winners[key]['cadence_ref']
        cadence = cadences.get(cadence_id)
        if cadence is None or cadence['period_length'] <= 0:
            continue
        due = winners[key]['due_at_minutes']
        if due < cadence['anchor_at']:
            continue
        period = (due - cadence['anchor_at']) // cadence['period_length']
        if period >= cadence['periods_elapsed']:
            continue
        start = cadence['anchor_at'] + period * cadence['period_length']
        end = min(start + cadence['period_length'], WINDOW_END)
        if start <= due < end:
            discharged.setdefault(cadence_id, set()).add(period)

    waiver_claims = set()
    for name in ('waivers_desk.csv', 'waivers_partner.psv'):
        for _index, fields, sound in read_table(data_dir, name):
            if not sound:
                continue
            cadence_id = fields.get('cadence_id', '')
            period_index = fields.get('period_index', '')
            if cadence_id not in cadences or not is_integer_text(period_index):
                continue
            period = int(period_index)
            if period < 0 or period >= cadences[cadence_id]['periods_elapsed']:
                continue
            waiver_claims.add((cadence_id, period))

    draws = []
    for cadence_id, period in waiver_claims:
        cadence = cadences[cadence_id]
        start = cadence['anchor_at'] + period * cadence['period_length']
        draws.append((start, cadence_id, period))
    draws.sort()

    waiver_granted = {}
    allowance_used = {}
    waivers_granted_count = {}
    waivers_lapsed_count = {}
    for start, cadence_id, period in draws:
        owner = cadences[cadence_id]['owner']
        if owner == '':
            waiver_granted[(cadence_id, period)] = True
            continue
        used = allowance_used.get(owner, 0)
        if used < WAIVER_ALLOWANCE:
            allowance_used[owner] = used + 1
            waiver_granted[(cadence_id, period)] = True
            waivers_granted_count[owner] = \
                waivers_granted_count.get(owner, 0) + 1
        else:
            waiver_granted[(cadence_id, period)] = False
            waivers_lapsed_count[owner] = waivers_lapsed_count.get(owner, 0) + 1

    cadence_debt = {}
    waiver_trace = []
    for cadence_id in sorted(cadences):
        cadence = cadences[cadence_id]
        debt = streak = max_streak = 0
        count_discharged = count_waived = 0
        settled_periods = discharged.get(cadence_id, frozenset())
        for period in range(cadence['periods_elapsed']):
            if period in settled_periods:
                streak = 0
                count_discharged += 1
            elif waiver_granted.get((cadence_id, period), False):
                count_waived += 1
            else:
                debt += 1
                streak += 1
                if streak > max_streak:
                    max_streak = streak
        cadence_debt[cadence_id] = {
            'period_days': cadence['period_days'],
            'periods_elapsed': cadence['periods_elapsed'],
            'periods_discharged': count_discharged,
            'periods_waived': count_waived,
            'debt': debt,
            'max_streak': max_streak,
        }
        for period in sorted(p for c, p in waiver_claims if c == cadence_id):
            if not waiver_granted.get((cadence_id, period), False):
                effect = 'LAPSED'
            elif period in settled_periods:
                effect = 'INERT'
            else:
                effect = 'SUPPRESSED'
            waiver_trace.append({
                'cadence_id': cadence_id,
                'period_index': period,
                'effect': effect,
                'period_start': format_instant(
                    cadence['anchor_at'] + period * cadence['period_length']),
            })

    owner_debt = {}
    owner_waived_periods = {}
    for cadence_id, cadence in cadences.items():
        owner = cadence['owner']
        if owner == '':
            continue
        owner_debt[owner] = owner_debt.get(owner, 0) \
            + cadence_debt[cadence_id]['debt']
        owner_waived_periods[owner] = owner_waived_periods.get(owner, 0) \
            + cadence_debt[cadence_id]['periods_waived']

    # -- attention envelopes ------------------------------------------------
    budgets = {}
    for _index, fields, sound in read_table(data_dir, 'attention_budget.csv'):
        if not sound:
            continue
        minutes = fields.get('monthly_minutes', '')
        if not is_integer_text(minutes):
            continue
        budgets[(fields.get('actor_id', ''), fields.get('year_month', ''))] = \
            int(minutes)
    overrides = {}
    for _index, fields, sound in read_table(data_dir, 'budget_overrides.psv'):
        if not sound:
            continue
        minutes = fields.get('monthly_minutes', '')
        if not is_integer_text(minutes):
            continue
        overrides[(fields.get('actor_id', ''), fields.get('year_month', ''))] \
            = int(minutes)

    blocked_lines = sorted(blocked)
    blocked_by_actor_month = {}
    for key in blocked_lines:
        pair = (winners[key]['obligor_actor'],
                winners[key]['commitment_day'][:7])
        blocked_by_actor_month[pair] = blocked_by_actor_month.get(pair, 0) + 1

    demand_groups = {}
    for key in sorted(admitted):
        if commitment_class[key] not in OPEN_CLASSES:
            continue
        if winners[key]['effort_minutes'] <= 0:
            continue
        pair = (winners[key]['obligor_actor'],
                winners[key]['commitment_day'][:7])
        demand_groups.setdefault(pair, []).append(key)

    allocated = {key: 0 for key in admitted}
    month_load = []
    allocations_starved = 0
    for pair in sorted(demand_groups, key=lambda p: (p[1], p[0])):
        actor, month = pair
        if (actor, month) in overrides:
            envelope = overrides[(actor, month)]
            source = 'OVERRIDE'
        elif (actor, month) in budgets:
            envelope = budgets[(actor, month)]
            source = 'REGISTERED'
        else:
            envelope = 0
            source = 'ABSENT'
        reserve = BLOCKED_RESERVE_MINUTES * blocked_by_actor_month.get(pair, 0) \
            + WAIVED_RESERVE_MINUTES * owner_waived_periods.get(actor, 0)
        distributable = envelope - reserve
        if distributable < 0:
            distributable = 0
        keys = demand_groups[pair]
        items = [(key, winners[key]['effort_minutes']) for key in keys]
        demand = sum(effort for _key, effort in items)
        if demand <= distributable:
            shares = {key: effort for key, effort in items}
        else:
            shares = distribute(distributable, items)
            qualifying = [(key, effort) for key, effort in items
                          if shares[key] >= ALLOCATION_FLOOR]
            allocations_starved += len(items) - len(qualifying)
            if qualifying:
                shares = distribute(distributable, qualifying)
                for key, _effort in items:
                    shares.setdefault(key, 0)
            else:
                shares = {key: 0 for key, _effort in items}
        for key in keys:
            allocated[key] = shares[key]
        month_load.append({
            'year_month': month,
            'obligor_actor': actor,
            'budget_source': source,
            'budget_minutes': envelope,
            'reserve_minutes': reserve,
            'demand_minutes': demand,
            'allocated_minutes': sum(shares[key] for key in keys),
            'open_count': len(keys),
        })

    # -- escalation ---------------------------------------------------------
    escalations = []
    for key in sorted(admitted):
        klass = commitment_class[key]
        if klass not in ('ACTIONABLE', 'BLOCKED'):
            continue
        effort = winners[key]['effort_minutes']
        share = allocated[key]
        if not share < effort:
            continue
        actor = winners[key]['obligor_actor']
        debt = owner_debt.get(actor, 0)
        if debt < ESCALATION_DEBT_THRESHOLD:
            continue
        depth = chain_depth[key]
        depth_holds = depth >= ESCALATION_DEPTH_THRESHOLD
        month_holds = winners[key]['commitment_day'][:7] == ESCALATION_MONTH
        if not (depth_holds or month_holds):
            continue
        if depth_holds and month_holds:
            trigger = 'BOTH'
        elif depth_holds:
            trigger = 'DEPTH'
        else:
            trigger = 'MONTH'
        escalations.append({
            'commitment_key': key,
            'obligor_actor': actor,
            'commitment_class': klass,
            'effort_minutes': effort,
            'allocated_minutes': share,
            'shortfall_minutes': effort - share,
            'principal_debt': debt,
            'chain_depth': depth,
            'trigger': trigger,
        })

    return {
        'manifest': manifest,
        'identity': identity,
        'canonical_handles': canonical_handles,
        'projects': projects,
        'rows_ingested': rows_ingested,
        'rejects': rejects,
        'assertions': assertions,
        'by_key': by_key,
        'winners': winners,
        'admitted': admitted,
        'state_rows': state_rows,
        'states_by_key': states_by_key,
        'resolved_state': resolved_state,
        'state_seen': state_seen,
        'state_applied': state_applied,
        'governing_class': governing_class,
        'applied_state_rows': applied_state_rows,
        'live_edges': live_edges,
        'dropped_edges': dropped_edges,
        'blocking': blocking,
        'cyclic': cyclic,
        'blocked': blocked,
        'blocked_lines': blocked_lines,
        'closure_pairs': closure_pairs,
        'closure_stats': closure_stats,
        'commitment_class': commitment_class,
        'unresolvable_reason': unresolvable_reason,
        'chain_depth': chain_depth,
        'cadences': cadences,
        'cadence_debt': cadence_debt,
        'waiver_trace': waiver_trace,
        'owner_debt': owner_debt,
        'waivers_granted_count': waivers_granted_count,
        'waivers_lapsed_count': waivers_lapsed_count,
        'allocated': allocated,
        'month_load': month_load,
        'allocations_starved': allocations_starved,
        'escalations': escalations,
        'demand_groups': demand_groups,
    }


def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: reconcile.py DATA_DIR OUT_DIR\n')
        return 2
    data_dir, out_dir = argv[1], argv[2]
    closure = reconcile(data_dir)
    publisher = Publisher()
    build_deliverables(closure, publisher)
    publish(publisher, out_dir)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
