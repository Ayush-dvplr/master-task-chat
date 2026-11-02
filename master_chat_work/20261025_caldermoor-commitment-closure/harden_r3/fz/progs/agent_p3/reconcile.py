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
        seated = self.handle_actor.get(folded)
        if seated is not None:
            # a reference folding to a canonical handle is seated at every
            # instant, with no hop
            outcome = (RESOLVED, seated, 0)
            self._cache[key] = outcome
            return outcome
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
                'obligor_surface': fields['obligor'],
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
    for key in sorted(admitted):
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
            dep_outcome, dep_actor, _dh = identity.resolve(
                winners[dependent]['obligor_surface'], asserted_at)
            blk_outcome, blk_actor, _bh = identity.resolve(
                winners[blocker]['obligor_surface'], asserted_at)
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
        distance = {key: 0}
        frontier = [key]
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


def build_deliverables(c, out):
    winners = c['winners']
    admitted = c['admitted']
    klass = c['commitment_class']
    allocated = c['allocated']
    resolved_state = c['resolved_state']
    closure_stats = c['closure_stats']

    def canonical(keys):
        return sorted(keys, key=lambda k: (winners[k]['commitment_day'],
                                           winners[k]['obligor_actor'],
                                           -winners[k]['effort_minutes'], k))

    ledger_keys = canonical(admitted)

    # -- normalized_assertions.jsonl ---------------------------------------
    out.jsonl('normalized_assertions.jsonl', [
        {
            'assertion_id': a['assertion_id'],
            'commitment_key': a['commitment_key'],
            'obligor_actor': a['obligor_actor'],
            'obligee_actor': a['obligee_actor']
            if a['obligee_status'] == 'RESOLVED' else '',
            'obligee_status': a['obligee_status'],
            'project_code': a['project_code'],
            'project_root': a['project_root'],
            'due_at': a['due_at'],
            'commitment_day': a['commitment_day'],
            'effort_minutes': a['effort_minutes'],
            'effort_origin': a['effort_origin'],
            'cadence_ref': a['cadence_ref'],
            'observed_at': a['observed_at'],
            'source_class': a['source_class'],
        }
        for a in sorted(c['assertions'],
                        key=lambda a: (a['assertion_id'], a['feed_file'],
                                       a['row_index']))
    ])

    # -- rejects.csv --------------------------------------------------------
    rejects = sorted(c['rejects'], key=lambda r: r.sort_key())
    out.delimited('rejects.csv', ',',
                  ['feed_file', 'row_index', 'record_kind', 'record_id',
                   'commitment_key', 'reason_code'],
                  [r.row() for r in rejects])

    # -- alias_resolution.jsonl --------------------------------------------
    surfaces = {}
    for a in c['assertions']:
        entry = surfaces.setdefault(a['obligor_surface_folded'],
                                    {'actors': set(), 'count': 0, 'hops': 0})
        entry['actors'].add(a['obligor_actor'])
        entry['count'] += 1
        if a['obligor_hops'] > entry['hops']:
            entry['hops'] = a['obligor_hops']
    out.jsonl('alias_resolution.jsonl', [
        {
            'surface_folded': surface,
            'distinct_actors': sorted(surfaces[surface]['actors']),
            'assertion_count': surfaces[surface]['count'],
            'max_hops': surfaces[surface]['hops'],
        }
        for surface in sorted(surfaces)
    ])

    # -- actor_roster.csv ---------------------------------------------------
    actor_commitments = {}
    actor_open_effort = {}
    actor_allocated = {}
    actor_classes = {}
    for key in admitted:
        actor = winners[key]['obligor_actor']
        actor_commitments[actor] = actor_commitments.get(actor, 0) + 1
        actor_classes.setdefault(actor, {name: 0 for name in
                                         COMMITMENT_CLASSES})
        actor_classes[actor][klass[key]] += 1
        actor_allocated[actor] = actor_allocated.get(actor, 0) + allocated[key]
        if klass[key] in OPEN_CLASSES:
            actor_open_effort[actor] = actor_open_effort.get(actor, 0) \
                + winners[key]['effort_minutes']
    out.delimited('actor_roster.csv', ',',
                  ['actor_id', 'canonical_handle', 'commitment_count',
                   'open_effort_minutes', 'waivers_granted', 'waivers_lapsed'],
                  [[actor, c['canonical_handles'][actor],
                    str(actor_commitments.get(actor, 0)),
                    str(actor_open_effort.get(actor, 0)),
                    str(c['waivers_granted_count'].get(actor, 0)),
                    str(c['waivers_lapsed_count'].get(actor, 0))]
                   for actor in sorted(c['canonical_handles'])])

    # -- project_lineage.csv ------------------------------------------------
    project_assertions = {}
    project_root_of = {}
    for a in c['assertions']:
        code = a['project_code']
        project_assertions[code] = project_assertions.get(code, 0) + 1
        project_root_of[code] = a['project_root']
    project_allocated = {}
    for key in admitted:
        code = winners[key]['project_code']
        project_allocated[code] = project_allocated.get(code, 0) \
            + allocated[key]
    out.delimited('project_lineage.csv', ',',
                  ['project_code', 'project_root', 'assertion_count',
                   'allocated_minutes'],
                  [[code, project_root_of[code],
                    str(project_assertions[code]),
                    str(project_allocated.get(code, 0))]
                   for code in sorted(project_assertions)])

    # -- assertion_contests.csv --------------------------------------------
    rows = []
    for key in sorted(admitted):
        contenders = c['by_key'][key]
        rows.append([key, winners[key]['assertion_id'],
                     winners[key]['source_class'], str(len(contenders)),
                     str(len({a['source_class'] for a in contenders}))])
    out.delimited('assertion_contests.csv', ',',
                  ['commitment_key', 'winning_assertion', 'winning_class',
                   'contender_count', 'distinct_classes'], rows)

    # -- commitment_ledger.jsonl -------------------------------------------
    out.jsonl('commitment_ledger.jsonl', [
        {
            'commitment_key': key,
            'obligor_actor': winners[key]['obligor_actor'],
            'obligee_actor': winners[key]['obligee_actor']
            if winners[key]['obligee_status'] == 'RESOLVED' else '',
            'project_code': winners[key]['project_code'],
            'project_root': winners[key]['project_root'],
            'commitment_day': winners[key]['commitment_day'],
            'due_at': winners[key]['due_at'],
            'effort_minutes': winners[key]['effort_minutes'],
            'effort_origin': winners[key]['effort_origin'],
            'resolved_state': resolved_state[key],
            'commitment_class': klass[key],
            'cadence_ref': winners[key]['cadence_ref'],
            'source_class': winners[key]['source_class'],
            'winning_assertion': winners[key]['assertion_id'],
            'allocated_minutes': allocated[key],
        }
        for key in ledger_keys
    ])

    # -- state_resolution.csv -----------------------------------------------
    out.delimited('state_resolution.csv', ',',
                  ['commitment_key', 'resolved_state', 'assertions_seen',
                   'assertions_applied', 'governing_class'],
                  [[key, resolved_state[key], str(c['state_seen'][key]),
                    str(c['state_applied'][key]), c['governing_class'][key]]
                   for key in sorted(admitted)])

    # -- live_edges.csv -----------------------------------------------------
    out.delimited('live_edges.csv', ',',
                  ['edge_id', 'dependent_key', 'blocker_key', 'asserted_at',
                   'dependent_actor', 'blocker_actor', 'dependent_blocked'],
                  [[e['edge_id'], e['dependent_key'], e['blocker_key'],
                    e['asserted_at'], e['dependent_actor'],
                    e['blocker_actor'],
                    'yes' if e['dependent_key'] in c['blocked'] else 'no']
                   for e in sorted(c['live_edges'],
                                   key=lambda e: (e['dependent_key'],
                                                  e['blocker_key'],
                                                  e['edge_id']))])

    # -- dropped_edges.csv --------------------------------------------------
    out.delimited('dropped_edges.csv', ',',
                  ['edge_id', 'dependent_key', 'blocker_key', 'asserted_at',
                   'drop_reason'],
                  [[e['edge_id'], e['dependent_key'], e['blocker_key'],
                    e['asserted_at'], e['drop_reason']]
                   for e in sorted(c['dropped_edges'],
                                   key=lambda e: (e['drop_reason'],
                                                  e['edge_id']))])

    # -- blocking_closure.jsonl ---------------------------------------------
    out.jsonl('blocking_closure.jsonl',
              sorted(c['closure_pairs'],
                     key=lambda p: (p['dependent_key'], p['blocker_key'])))

    # -- blocked_commitments.csv --------------------------------------------
    out.delimited('blocked_commitments.csv', ',',
                  ['commitment_key', 'reachable_blockers', 'frontier_count',
                   'chain_depth', 'frontier_head', 'allocated_minutes'],
                  [[key, str(closure_stats[key]['reachable_blockers']),
                    str(closure_stats[key]['frontier_count']),
                    str(closure_stats[key]['chain_depth']),
                    closure_stats[key]['frontier_head'],
                    str(allocated[key])]
                   for key in c['blocked_lines']])

    # -- the class queues ---------------------------------------------------
    queue_header = ['commitment_key', 'obligor_actor', 'commitment_day',
                    'effort_minutes', 'project_root', 'allocated_minutes']

    def queue_rows(name):
        return [[key, winners[key]['obligor_actor'],
                 winners[key]['commitment_day'],
                 str(winners[key]['effort_minutes']),
                 winners[key]['project_root'], str(allocated[key])]
                for key in ledger_keys if klass[key] == name]

    out.delimited('actionable_queue.tsv', '\t', queue_header,
                  queue_rows('ACTIONABLE'))
    out.delimited('deferred_queue.psv', '|', queue_header,
                  queue_rows('DEFERRED'))
    out.delimited('withdrawn_register.csv', ',',
                  ['commitment_key', 'obligor_actor', 'commitment_day',
                   'effort_minutes', 'source_class'],
                  [[key, winners[key]['obligor_actor'],
                    winners[key]['commitment_day'],
                    str(winners[key]['effort_minutes']),
                    winners[key]['source_class']]
                   for key in ledger_keys if klass[key] == 'WITHDRAWN'])

    unresolvable = [
        {
            'commitment_key': key,
            'reason_code': c['unresolvable_reason'][key],
            'obligor_actor': winners[key]['obligor_actor'],
            'commitment_day': winners[key]['commitment_day'],
        }
        for key in sorted(admitted) if klass[key] == 'UNRESOLVABLE'
    ]
    unresolvable.sort(key=lambda o: (o['reason_code'], o['commitment_key']))
    out.jsonl('unresolvable.jsonl', unresolvable)

    # -- cadences -----------------------------------------------------------
    out.delimited('cadence_debt.csv', ',',
                  ['cadence_id', 'period_days', 'periods_elapsed',
                   'periods_discharged', 'periods_waived', 'debt',
                   'max_streak'],
                  [[cadence_id,
                    str(c['cadence_debt'][cadence_id]['period_days']),
                    str(c['cadence_debt'][cadence_id]['periods_elapsed']),
                    str(c['cadence_debt'][cadence_id]['periods_discharged']),
                    str(c['cadence_debt'][cadence_id]['periods_waived']),
                    str(c['cadence_debt'][cadence_id]['debt']),
                    str(c['cadence_debt'][cadence_id]['max_streak'])]
                   for cadence_id in sorted(c['cadence_debt'])])
    out.jsonl('waiver_trace.jsonl',
              sorted(c['waiver_trace'],
                     key=lambda w: (w['cadence_id'], w['period_index'])))

    # -- attention ----------------------------------------------------------
    allocation_rows = []
    for pair in sorted(c['demand_groups'], key=lambda p: (p[1], p[0])):
        for key in sorted(c['demand_groups'][pair]):
            allocation_rows.append([pair[1], pair[0], key,
                                    str(winners[key]['effort_minutes']),
                                    str(allocated[key])])
    out.delimited('attention_allocation.csv', ',',
                  ['year_month', 'obligor_actor', 'commitment_key',
                   'demand_minutes', 'allocated_minutes'], allocation_rows)
    out.delimited('month_load_index.csv', ',',
                  ['year_month', 'obligor_actor', 'budget_source',
                   'budget_minutes', 'reserve_minutes', 'demand_minutes',
                   'allocated_minutes', 'open_count'],
                  [[m['year_month'], m['obligor_actor'], m['budget_source'],
                    str(m['budget_minutes']), str(m['reserve_minutes']),
                    str(m['demand_minutes']), str(m['allocated_minutes']),
                    str(m['open_count'])]
                   for m in sorted(c['month_load'],
                                   key=lambda m: (m['year_month'],
                                                  m['obligor_actor']))])

    # -- escalation_queue.csv -----------------------------------------------
    out.delimited('escalation_queue.csv', ',',
                  ['commitment_key', 'obligor_actor', 'commitment_class',
                   'effort_minutes', 'allocated_minutes', 'shortfall_minutes',
                   'principal_debt', 'chain_depth', 'trigger'],
                  [[e['commitment_key'], e['obligor_actor'],
                    e['commitment_class'], str(e['effort_minutes']),
                    str(e['allocated_minutes']), str(e['shortfall_minutes']),
                    str(e['principal_debt']), str(e['chain_depth']),
                    e['trigger']]
                   for e in sorted(c['escalations'],
                                   key=lambda e: (-e['shortfall_minutes'],
                                                  e['commitment_key']))])

    # -- rollups ------------------------------------------------------------
    actor_rollup = {}
    for actor in sorted(actor_commitments):
        value = dict(actor_classes[actor])
        value['commitment_count'] = actor_commitments[actor]
        value['open_effort_minutes'] = actor_open_effort.get(actor, 0)
        value['allocated_minutes'] = actor_allocated.get(actor, 0)
        actor_rollup[actor] = value
    out.document('actor_rollup.json', actor_rollup)

    root_rollup = {}
    for key in admitted:
        root = winners[key]['project_root']
        value = root_rollup.setdefault(
            root, dict([(name, 0) for name in COMMITMENT_CLASSES]
                       + [('commitment_count', 0), ('open_effort_minutes', 0),
                          ('allocated_minutes', 0)]))
        value[klass[key]] += 1
        value['commitment_count'] += 1
        value['allocated_minutes'] += allocated[key]
        if klass[key] in OPEN_CLASSES:
            value['open_effort_minutes'] += winners[key]['effort_minutes']
    out.document('project_rollup.json', root_rollup)

    # -- provenance_index.jsonl ---------------------------------------------
    out.jsonl('provenance_index.jsonl', [
        {
            'commitment_key': key,
            'winning_assertion': winners[key]['assertion_id'],
            'contributing_assertions': sorted(
                a['assertion_id'] for a in c['by_key'][key]),
            'source_files': sorted({a['feed_file'] for a in c['by_key'][key]}),
            'state_assertions': sorted(
                row['state_id'] for row in c['states_by_key'].get(key, [])),
        }
        for key in sorted(admitted)
    ])

    # -- audit figures ------------------------------------------------------
    class_counts = {name: 0 for name in COMMITMENT_CLASSES}
    for key in admitted:
        class_counts[klass[key]] += 1
    reject_counts = {code: 0 for code in REASON_CODES}
    for reject in rejects:
        reject_counts[reject.reason_code] += 1

    open_effort = sum(winners[key]['effort_minutes'] for key in admitted
                      if klass[key] in OPEN_CLASSES)
    allocated_total = sum(allocated[key] for key in admitted)
    rows_rejected = len(rejects)
    rows_accepted = c['rows_ingested'] - rows_rejected

    figures = [
        ('rows_ingested', c['rows_ingested'], True),
        ('rows_rejected', rows_rejected, True),
        ('rows_accepted', rows_accepted, False),
        ('commitments_admitted', len(admitted), True),
        ('class_actionable', class_counts['ACTIONABLE'], True),
        ('class_blocked', class_counts['BLOCKED'], True),
        ('class_deferred', class_counts['DEFERRED'], True),
        ('class_settled', class_counts['SETTLED'], True),
        ('class_unresolvable', class_counts['UNRESOLVABLE'], True),
        ('class_withdrawn', class_counts['WITHDRAWN'], True),
        ('reject_ambiguous_identity', reject_counts['AMBIGUOUS_IDENTITY'],
         False),
        ('reject_feed_retired', reject_counts['FEED_RETIRED'], False),
        ('reject_illegal_transition', reject_counts['ILLEGAL_TRANSITION'],
         False),
        ('reject_malformed_row', reject_counts['MALFORMED_ROW'], False),
        ('reject_nonpositive_effort', reject_counts['NONPOSITIVE_EFFORT'],
         False),
        ('reject_out_of_window', reject_counts['OUT_OF_WINDOW'], False),
        ('reject_unknown_commitment', reject_counts['UNKNOWN_COMMITMENT'],
         False),
        ('reject_unknown_principal', reject_counts['UNKNOWN_PRINCIPAL'],
         False),
        ('reject_unknown_project', reject_counts['UNKNOWN_PROJECT'], False),
        ('live_edges', len(c['live_edges']), True),
        ('dropped_edges', len(c['dropped_edges']), True),
        ('closure_pairs', len(c['closure_pairs']), True),
        ('blocked_commitments', len(c['blocked_lines']), True),
        ('open_effort_minutes', open_effort, True),
        ('allocated_minutes', allocated_total, True),
        ('escalated_commitments', len(c['escalations']), True),
        ('cadence_debt_total',
         sum(entry['debt'] for entry in c['cadence_debt'].values()), True),
    ]
    out.delimited('audit_totals.csv', ',', ['metric', 'value'],
                  [[name, str(value)] for name, value, _starred in figures])

    # -- identities ---------------------------------------------------------
    residuals = {
        'I1_row_partition': rows_accepted - (
            len(c['assertions']) + c['applied_state_rows']
            + len(c['live_edges']) + len(c['dropped_edges'])),
        'I2_class_partition': len(admitted) - sum(class_counts.values()),
        'I3_actor_effort': sum(actor_open_effort.values()) - open_effort,
        'I4_project_effort': sum(value['open_effort_minutes']
                                 for value in root_rollup.values())
        - open_effort,
        'I5_closure_frontier': sum(
            closure_stats[key]['frontier_count']
            for key in c['blocked_lines'])
        - sum(1 for pair in c['closure_pairs'] if pair['terminal'] == 'yes'),
    }

    lines = ['CALDERMOOR COMMITMENT CLOSURE']
    lines.extend('%s %d' % (name, value)
                 for name, value, starred in figures if starred)
    lines.extend('identity_%s %d' % (name, residuals[name])
                 for name in IDENTITY_NAMES)
    out.text('reconciliation.txt', lines)

    out.document('validation_report.json', {
        'identities': residuals,
        'identities_checked': sorted(residuals),
        'all_residuals_zero': all(value == 0 for value in residuals.values()),
    })

    # -- run_manifest.json --------------------------------------------------
    retired = sorted(name for name, entry in c['manifest'].items()
                     if entry[1] != '')
    effects = {}
    for waiver in c['waiver_trace']:
        effects[waiver['effect']] = effects.get(waiver['effect'], 0) + 1
    tiebreaks = 0
    for first, second in zip(ledger_keys, ledger_keys[1:]):
        if (winners[first]['commitment_day']
                == winners[second]['commitment_day']
                and winners[first]['obligor_actor']
                == winners[second]['obligor_actor']
                and winners[first]['effort_minutes']
                != winners[second]['effort_minutes']):
            tiebreaks += 1
    out.document('run_manifest.json', {
        'day_boundary_offset_minutes': DAY_BOUNDARY_OFFSET_MINUTES,
        'effort_floor_minutes': EFFORT_FLOOR,
        'effort_ceiling_minutes': EFFORT_CEILING,
        'allocation_floor_minutes': ALLOCATION_FLOOR,
        'window_start': WINDOW_START_TEXT,
        'window_end': WINDOW_END_TEXT,
        'reason_codes': sorted(REASON_CODES),
        'commitment_classes': sorted(COMMITMENT_CLASSES),
        'retired_feeds': retired,
        'split_surfaces': sum(1 for surface in surfaces
                              if len(surfaces[surface]['actors']) > 1),
        'multi_hop_assertions': sum(1 for a in c['assertions']
                                    if a['obligor_hops'] >= 2),
        'order_tiebreaks_applied': tiebreaks,
        'edges_dropped_out_of_scope': sum(
            1 for e in c['dropped_edges']
            if e['drop_reason'] == 'EDGE_OUT_OF_SCOPE'),
        'waivers_suppressing': effects.get('SUPPRESSED', 0),
        'waivers_inert': effects.get('INERT', 0),
        'waivers_lapsed': effects.get('LAPSED', 0),
        'allocations_starved': c['allocations_starved'],
        'illegal_transitions': reject_counts['ILLEGAL_TRANSITION'],
    })


DELIVERABLES = (
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
)


def publish(publisher, out_dir):
    """Write every deliverable into a staging directory, then move it across."""
    publisher.raw('reconcile.py', read_text(os.path.realpath(__file__)))
    missing = [name for name in DELIVERABLES if name not in publisher.files]
    extra = [name for name in sorted(publisher.files)
             if name not in DELIVERABLES]
    if missing or extra:
        raise RuntimeError('deliverable set mismatch: missing=%s extra=%s'
                           % (missing, extra))

    out_dir = os.path.abspath(out_dir)
    parent = os.path.dirname(out_dir) or '.'
    if out_dir == parent:
        raise RuntimeError('refusing to publish into a filesystem root')
    if not os.path.isdir(parent):
        os.makedirs(parent)
    stage = os.path.join(parent, '.%s.staging' % os.path.basename(out_dir))
    if os.path.exists(stage):
        shutil.rmtree(stage)
    os.makedirs(stage)
    try:
        for name in DELIVERABLES:
            with open(os.path.join(stage, name), 'w', encoding='utf-8',
                      newline='') as handle:
                handle.write(publisher.files[name])
        if os.path.isdir(out_dir):
            for name in sorted(os.listdir(out_dir)):
                victim = os.path.join(out_dir, name)
                if os.path.isdir(victim) and not os.path.islink(victim):
                    shutil.rmtree(victim)
                else:
                    os.remove(victim)
        else:
            os.makedirs(out_dir)
        for name in DELIVERABLES:
            os.replace(os.path.join(stage, name), os.path.join(out_dir, name))
    finally:
        if os.path.isdir(stage):
            shutil.rmtree(stage)


def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: reconcile.py DATA_DIR OUT_DIR\n')
        return 2
    data_dir, out_dir = argv[1], argv[2]
    if os.path.abspath(data_dir) == os.path.abspath(out_dir):
        sys.stderr.write('refusing to publish into the extract directory\n')
        return 2
    closure = reconcile(data_dir)
    publisher = Publisher()
    build_deliverables(closure, publisher)
    publish(publisher, out_dir)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
