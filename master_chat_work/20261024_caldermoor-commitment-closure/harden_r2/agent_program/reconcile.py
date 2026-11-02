#!/usr/bin/env python3
"""Caldermoor commitment closure.

Reads one extract directory and writes the whole closure into another:

    python3 reconcile.py DATA_DIR OUT_DIR

Standard library only, deterministic, and the extract is only ever read.
"""

import json
import os
import re
import shutil
import sys
import tempfile
import unicodedata
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------------------- constants

WINDOW_START_TEXT = "2032-03-01T00:00Z"
WINDOW_END_TEXT = "2032-12-01T00:00Z"
DAY_BOUNDARY_OFFSET_MINUTES = 240
EFFORT_FLOOR = 15
EFFORT_CEILING = 480
ALLOCATION_FLOOR = 15
ESCALATION_DEBT_FLOOR = 4
ESCALATION_DEPTH_FLOOR = 2
ESCALATION_MONTH = "2032-11"

REASON_CODES = [
    "MALFORMED_ROW",
    "FEED_RETIRED",
    "OUT_OF_WINDOW",
    "UNKNOWN_PRINCIPAL",
    "AMBIGUOUS_IDENTITY",
    "UNKNOWN_PROJECT",
    "NONPOSITIVE_EFFORT",
    "UNKNOWN_COMMITMENT",
    "ILLEGAL_TRANSITION",
]

CLASSES = [
    "ACTIONABLE",
    "BLOCKED",
    "DEFERRED",
    "SETTLED",
    "UNRESOLVABLE",
    "WITHDRAWN",
]
OPEN_CLASSES = ("ACTIONABLE", "BLOCKED", "DEFERRED")

IDENTITIES = [
    "I1_row_partition",
    "I2_class_partition",
    "I3_actor_effort",
    "I4_project_effort",
    "I5_closure_frontier",
]

CLASS_RANK = {
    "vault": 6,
    "desk": 5,
    "bridge": 4,
    "partner": 3,
    "mirror": 2,
    "import": 1,
    "relay": 1,
    "legacy": 0,
}

EFFORT_UNITS = {"minutes": 1, "hours": 60, "halfdays": 240}
UNITLESS_FACTOR = 60  # the .fixed and .rec commitment layouts count hours

ALLOWED_TRANSITIONS = {
    ("OPEN", "SETTLED"),
    ("OPEN", "DEFERRED"),
    ("OPEN", "WITHDRAWN"),
    ("DEFERRED", "OPEN"),
    ("DEFERRED", "WITHDRAWN"),
}
STATES = ("OPEN", "SETTLED", "DEFERRED", "WITHDRAWN")

COMMITMENT_FIXED = (
    ("assertion_id", 12),
    ("commitment_key", 12),
    ("obligor", 40),
    ("obligee", 40),
    ("project_ref", 10),
    ("due_at", 18),
    ("effort", 8),
    ("cadence_ref", 10),
    ("observed_at", 18),
)
STATE_FIXED = (
    ("state_id", 12),
    ("commitment_key", 12),
    ("to_state", 12),
    ("observed_at", 18),
)

DELIMITERS = {".csv": ",", ".tsv": "\t", ".psv": "|"}
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
INSTANT_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})Z$")
ATTR_RE = re.compile(r'([A-Za-z_][\w.-]*)="([^"]*)"')
KV_RE = re.compile(r"^([^:]+): (.*)$")


class Unfinishable(Exception):
    """Raised when the run cannot produce the closure."""


# ------------------------------------------------------------------ instants


def parse_instant(text):
    m = INSTANT_RE.match(text or "")
    if not m:
        return None
    year, month, day, hour, minute = (int(g) for g in m.groups())
    try:
        dt = datetime(year, month, day, hour, minute, tzinfo=timezone.utc)
    except ValueError:
        return None
    return int((dt - EPOCH).total_seconds()) // 60


def format_instant(minutes):
    return (EPOCH + timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%MZ")


def commitment_day(minutes):
    shifted = EPOCH + timedelta(minutes=minutes - DAY_BOUNDARY_OFFSET_MINUTES)
    return shifted.strftime("%Y-%m-%d")


WINDOW_START = parse_instant(WINDOW_START_TEXT)
WINDOW_END = parse_instant(WINDOW_END_TEXT)


def in_window(minutes):
    return WINDOW_START <= minutes < WINDOW_END


# --------------------------------------------------------------------- fold


def fold(surface):
    text = unicodedata.normalize("NFC", surface or "").strip().casefold()
    for ch in ".-_'":
        text = text.replace(ch, "")
    return " ".join(text.split()).strip()


# ------------------------------------------------------------------ readers


def read_text(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def split_lines(text):
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def coerce(value):
    if isinstance(value, str):
        return value
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    return str(value)


def read_delimited(path, sep):
    lines = split_lines(read_text(path))
    if not lines:
        return []
    header = lines[0].split(sep)
    out = []
    for line in lines[1:]:
        fields = line.split(sep)
        row = dict(zip(header, fields))
        out.append((row, len(fields) != len(header)))
    return out


def read_jsonl(path):
    out = []
    for line in split_lines(read_text(path)):
        try:
            obj = json.loads(line)
        except ValueError:
            obj = None
        if isinstance(obj, dict):
            out.append(({k: coerce(v) for k, v in obj.items()}, False))
        else:
            out.append(({}, True))
    return out


def read_kv(path):
    text = read_text(path)
    if text.endswith("\n"):
        text = text[:-1]
    out = []
    for record in text.split("\n\n"):
        row = {}
        malformed = False
        for line in record.split("\n"):
            if not line:
                continue
            m = KV_RE.match(line)
            if m:
                row[m.group(1)] = m.group(2)
            elif line.endswith(":") and len(line) > 1:
                row[line[:-1]] = ""
            else:
                malformed = True
        if row or malformed:
            out.append((row, malformed))
    return out


def read_rec(path):
    out = []
    for line in split_lines(read_text(path)):
        row = {}
        malformed = False
        for segment in line.split(";"):
            if "=" in segment:
                name, value = segment.split("=", 1)
                row[name] = value
            else:
                malformed = True
        out.append((row, malformed))
    return out


def unescape_xml(value):
    for entity, ch in (
        ("&lt;", "<"),
        ("&gt;", ">"),
        ("&quot;", '"'),
        ("&apos;", "'"),
        ("&amp;", "&"),
    ):
        value = value.replace(entity, ch)
    return value


def read_xml(path):
    out = []
    for line in split_lines(read_text(path)):
        stripped = line.strip()
        if not stripped.startswith("<") or not stripped.endswith("/>"):
            continue
        row = {k: unescape_xml(v) for k, v in ATTR_RE.findall(stripped)}
        out.append((row, False))
    return out


def read_fixed(path, spec):
    out = []
    for line in split_lines(read_text(path)):
        row = {}
        pos = 0
        for name, width in spec:
            row[name] = line[pos:pos + width].strip()
            pos += width
        out.append((row, False))
    return out


def read_rows(path, kind):
    ext = os.path.splitext(path)[1]
    if ext in DELIMITERS:
        return read_delimited(path, DELIMITERS[ext])
    if ext == ".jsonl":
        return read_jsonl(path)
    if ext == ".kv":
        return read_kv(path)
    if ext == ".rec":
        return read_rec(path)
    if ext == ".xml":
        return read_xml(path)
    if ext == ".fixed":
        if kind == "commitment":
            return read_fixed(path, COMMITMENT_FIXED)
        if kind == "state":
            return read_fixed(path, STATE_FIXED)
        raise Unfinishable("no fixed width layout for %s rows" % kind)
    raise Unfinishable("unknown layout %s" % ext)


def carries_effort_unit(name):
    return not name.endswith((".fixed", ".rec"))


# ------------------------------------------------------------------ extract


class Extract:
    """Every file of one extract directory, parsed but not yet judged."""

    def __init__(self, data_dir):
        self.dir = data_dir
        try:
            names = sorted(
                n for n in os.listdir(data_dir)
                if os.path.isfile(os.path.join(data_dir, n))
            )
        except OSError as exc:
            raise Unfinishable("cannot read extract directory: %s" % exc)
        self.names = names
        self.commitment_feeds = self._feeds("commitments_")
        self.state_feeds = self._feeds("states_")
        self.edge_feeds = self._feeds("edges_")
        self.alias_files = self._feeds("aliases_")
        self.roster_files = self._feeds("roster_")
        self.waiver_files = self._feeds("waivers_")
        self.manifest = self._table("feed_manifest.csv")
        self.registry = self._table("project_registry.csv")
        self.events = self._table("project_events.tsv")
        self.cadences = self._table("cadence_register.csv")
        self.budget = self._table("attention_budget.csv")
        self.overrides = self._table("budget_overrides.psv")

    def _feeds(self, prefix):
        return [n for n in self.names if n.startswith(prefix)]

    def path(self, name):
        return os.path.join(self.dir, name)

    def _table(self, name):
        if name not in self.names:
            return []
        return [row for row, _bad in read_rows(self.path(name), "reference")]

    def rows(self, name, kind):
        return read_rows(self.path(name), kind)


# ------------------------------------------------------------------ manifest


class Manifest:
    def __init__(self, extract):
        governing = {}
        for row in extract.manifest:
            name = row.get("feed_file", "")
            if not name or name == "feed_file":
                continue
            try:
                revision = int(row.get("revision", "0") or "0")
            except ValueError:
                revision = 0
            current = governing.get(name)
            if current is None or revision >= current[0]:
                governing[name] = (revision, row)
        self.source_class = {}
        self.retired_at = {}
        self.retired_feeds = []
        for name, (_rev, row) in governing.items():
            self.source_class[name] = row.get("source_class", "")
            self.retired_at[name] = parse_instant(row.get("retired_at", ""))
            if row.get("retired_at", ""):
                self.retired_feeds.append(name)
        self.retired_feeds.sort()

    def klass(self, name):
        found = self.source_class.get(name)
        if found in CLASS_RANK:
            return found
        parts = os.path.splitext(name)[0].split("_")
        for part in parts:
            if part in CLASS_RANK:
                return part
        raise Unfinishable("no source class for feed %s" % name)

    def retirement(self, name):
        return self.retired_at.get(name)


# ------------------------------------------------------------------ identity


class Identity:
    """The identity register: roster handles, alias assertions, resolution."""

    def __init__(self, extract):
        lines = []
        for name in extract.roster_files:
            for row, _bad in extract.rows(name, "roster"):
                if row.get("actor_id"):
                    lines.append(row)
        spellings = defaultdict(lambda: defaultdict(int))
        self.handle_actor = {}
        for row in lines:
            actor = row["actor_id"]
            handle = row.get("canonical_handle", "")
            spellings[actor][handle] += 1
            self.handle_actor[fold(handle)] = actor
        self.canonical_handle = {}
        for actor, counts in spellings.items():
            best = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
            self.canonical_handle[actor] = best
        self.actors = sorted(self.canonical_handle)

        seen = set()
        self.out_edges = defaultdict(list)
        for name in extract.alias_files:
            for row, _bad in extract.rows(name, "alias"):
                surface = fold(row.get("surface", ""))
                target = fold(row.get("target", ""))
                start = parse_instant(row.get("scope_start", ""))
                end = parse_instant(row.get("scope_end", ""))
                if not surface or not target or start is None or end is None:
                    continue
                key = (surface, target, start, end)
                if key in seen:
                    continue
                seen.add(key)
                self.out_edges[surface].append((target, start, end))
        for surface in self.out_edges:
            self.out_edges[surface].sort()
        self.assertion_count = len(seen)
        self._cache = {}

    def resolve(self, surface, instant):
        """Return (actor_id or outcome code, hop_count)."""
        key = (fold(surface), instant)
        found = self._cache.get(key)
        if found is None:
            found = self._resolve(key[0], key[1])
            self._cache[key] = found
        return found

    def _resolve(self, folded, instant):
        if folded in self.handle_actor:
            return (self.handle_actor[folded], 0)
        reached = {folded: 0}
        queue = deque([folded])
        hits = {}
        while queue:
            node = queue.popleft()
            depth = reached[node]
            for target, start, end in self.out_edges.get(node, ()):
                if not (start <= instant < end):
                    continue
                if target in reached:
                    continue
                reached[target] = depth + 1
                actor = self.handle_actor.get(target)
                if actor is not None and actor not in hits:
                    hits[actor] = depth + 1
                queue.append(target)
        if not hits:
            return ("UNKNOWN_PRINCIPAL", 0)
        if len(hits) > 1:
            return ("AMBIGUOUS_IDENTITY", 0)
        actor, hops = next(iter(hits.items()))
        return (actor, hops)


def resolution_outcome(result):
    actor = result[0]
    if actor in ("UNKNOWN_PRINCIPAL", "AMBIGUOUS_IDENTITY"):
        return actor
    return "RESOLVED"


# ------------------------------------------------------------------ projects


class Projects:
    def __init__(self, extract):
        self.revisions = defaultdict(list)
        for row in extract.registry:
            code = row.get("project_code", "")
            revised = parse_instant(row.get("revised_at", ""))
            if not code or revised is None:
                continue
            self.revisions[code].append((revised, row))
        for code in self.revisions:
            self.revisions[code].sort(key=lambda pair: pair[0])
        self.renames = defaultdict(list)
        for row in extract.events:
            if row.get("event_type") != "RENAME":
                continue
            effective = parse_instant(row.get("effective_at", ""))
            code = row.get("project_code", "")
            payload = row.get("payload", "")
            if effective is None or not code or not payload:
                continue
            self.renames[code].append((effective, row.get("event_id", ""), payload))
        for code in self.renames:
            self.renames[code].sort()
        self._roots = {}

    def resolve(self, code, instant):
        current = code
        seen = {current}
        while True:
            applicable = [r for r in self.renames.get(current, ()) if r[0] <= instant]
            if not applicable:
                break
            payload = applicable[-1][2]
            if payload in seen:
                break
            current = payload
            seen.add(current)
        if current not in self.revisions:
            return None
        return current

    def revision(self, code, instant):
        revisions = self.revisions[code]
        governing = None
        for revised, row in revisions:
            if revised <= instant:
                governing = row
            else:
                break
        if governing is None:
            governing = revisions[0][1]
        return governing

    def latest(self, code):
        return self.revisions[code][-1][1]

    def root(self, code):
        found = self._roots.get(code)
        if found is not None:
            return found
        current = code
        walked = [current]
        while True:
            parent = self.latest(current).get("parent_code", "")
            if not parent or parent not in self.revisions or parent in walked:
                break
            current = parent
            walked.append(current)
        for node in walked:
            self._roots.setdefault(node, current)
        return current

    def default_effort(self, code, instant):
        raw = self.revision(code, instant).get("default_effort", "")
        try:
            return int(raw)
        except ValueError:
            return 0


# ------------------------------------------------------------------- ingest


class Reject:
    __slots__ = ("feed_file", "row_index", "record_kind", "record_id",
                 "commitment_key", "reason_code")

    def __init__(self, feed_file, row_index, record_kind, record_id,
                 commitment_key, reason_code):
        self.feed_file = feed_file
        self.row_index = row_index
        self.record_kind = record_kind
        self.record_id = record_id
        self.commitment_key = commitment_key
        self.reason_code = reason_code


class Assertion:
    __slots__ = (
        "feed_file", "row_index", "source_class", "rank", "assertion_id",
        "commitment_key", "obligor", "obligee", "project_ref", "due_at",
        "observed_at", "cadence_ref", "obligor_actor", "obligor_hops",
        "obligee_actor", "obligee_status", "project_code", "project_root",
        "effort_minutes", "effort_origin", "commitment_day", "order_key",
    )


class StateRow:
    __slots__ = ("feed_file", "row_index", "source_class", "state_id",
                 "commitment_key", "to_state", "observed_at", "order_key")


class EdgeRow:
    __slots__ = ("feed_file", "row_index", "source_class", "edge_id",
                 "dependent_key", "blocker_key", "asserted_at",
                 "dependent_actor", "blocker_actor", "drop_reason")


def commitment_order_key(source_class, observed_at, row_id):
    inner = -observed_at if source_class == "desk" else observed_at
    return (CLASS_RANK[source_class], inner, row_id)


def state_order_key(source_class, observed_at, row_id):
    inner = -observed_at if source_class in ("desk", "bridge") else observed_at
    return (CLASS_RANK[source_class], inner, row_id)


class Closure:
    """The whole settlement, computed from one extract."""

    def __init__(self, extract):
        self.extract = extract
        self.manifest = Manifest(extract)
        self.identity = Identity(extract)
        self.projects = Projects(extract)
        self.rejects = []
        self.rows_ingested = 0
        self.ingest_commitments()
        self.admit_commitments()
        self.ingest_states()
        self.resolve_states()
        self.ingest_edges()
        self.build_graph()
        self.classify()
        self.allocate()
        self.cadence_debt()
        self.escalate()
        self.rollups()
        self.check_identities()

    # -- commitments ------------------------------------------------------

    def ingest_commitments(self):
        self.accepted_assertions = []
        for name in self.extract.commitment_feeds:
            source_class = self.manifest.klass(name)
            retired = self.manifest.retirement(name)
            has_unit = carries_effort_unit(name)
            for index, (row, malformed) in enumerate(
                    self.extract.rows(name, "commitment")):
                self.rows_ingested += 1
                reason = None
                key = row.get("commitment_key", "")
                row_id = row.get("assertion_id", "")
                due = parse_instant(row.get("due_at", ""))
                observed = parse_instant(row.get("observed_at", ""))
                effort_raw = row.get("effort", "")
                unit = row.get("effort_unit", "") if has_unit else ""
                effort_int = None
                if effort_raw not in ("", "null"):
                    try:
                        effort_int = int(effort_raw)
                    except ValueError:
                        malformed = True
                if malformed or due is None or observed is None:
                    reason = "MALFORMED_ROW"
                elif effort_int is not None and effort_int > 0 and has_unit \
                        and unit not in EFFORT_UNITS:
                    reason = "MALFORMED_ROW"
                elif retired is not None and observed >= retired:
                    reason = "FEED_RETIRED"
                elif not in_window(due):
                    reason = "OUT_OF_WINDOW"
                if reason is None:
                    obligor_actor, obligor_hops = self.identity.resolve(
                        row.get("obligor", ""), observed)
                    outcome = resolution_outcome((obligor_actor, obligor_hops))
                    if outcome != "RESOLVED":
                        reason = outcome
                if reason is None:
                    project_code = self.projects.resolve(
                        row.get("project_ref", ""), observed)
                    if project_code is None:
                        reason = "UNKNOWN_PROJECT"
                if reason is None and effort_int is not None and effort_int <= 0:
                    reason = "NONPOSITIVE_EFFORT"
                if reason is not None:
                    self.rejects.append(
                        Reject(name, index, "commitment", row_id, key, reason))
                    continue

                item = Assertion()
                item.feed_file = name
                item.row_index = index
                item.source_class = source_class
                item.rank = CLASS_RANK[source_class]
                item.assertion_id = row_id
                item.commitment_key = key
                item.obligor = row.get("obligor", "")
                item.obligee = row.get("obligee", "")
                item.project_ref = row.get("project_ref", "")
                item.due_at = due
                item.observed_at = observed
                item.cadence_ref = row.get("cadence_ref", "")
                item.obligor_actor = obligor_actor
                item.obligor_hops = obligor_hops
                obligee_actor, _hops = self.identity.resolve(item.obligee, due)
                status = resolution_outcome((obligee_actor, _hops))
                if status == "RESOLVED":
                    item.obligee_status = "RESOLVED"
                    item.obligee_actor = obligee_actor
                elif status == "AMBIGUOUS_IDENTITY":
                    item.obligee_status = "AMBIGUOUS"
                    item.obligee_actor = ""
                else:
                    item.obligee_status = "UNKNOWN"
                    item.obligee_actor = ""
                item.project_code = project_code
                item.project_root = self.projects.root(project_code)
                if effort_raw == "":
                    item.effort_origin = "DEFAULTED"
                    minutes = self.projects.default_effort(project_code, observed)
                    item.effort_minutes = clamp_effort(minutes)
                elif effort_raw == "null":
                    item.effort_origin = "DECLARED_ZERO"
                    item.effort_minutes = 0
                else:
                    item.effort_origin = "STATED"
                    factor = EFFORT_UNITS[unit] if has_unit else UNITLESS_FACTOR
                    item.effort_minutes = clamp_effort(effort_int * factor)
                item.commitment_day = commitment_day(due)
                item.order_key = commitment_order_key(source_class, observed, row_id)
                self.accepted_assertions.append(item)

    def admit_commitments(self):
        by_key = defaultdict(list)
        for item in self.accepted_assertions:
            by_key[item.commitment_key].append(item)
        self.contenders = by_key
        self.keys = sorted(by_key)
        self.winner = {}
        for key, items in by_key.items():
            self.winner[key] = max(items, key=lambda a: a.order_key)

    # -- states -----------------------------------------------------------

    def ingest_states(self):
        self.state_candidates = defaultdict(list)
        for name in self.extract.state_feeds:
            source_class = self.manifest.klass(name)
            retired = self.manifest.retirement(name)
            for index, (row, malformed) in enumerate(
                    self.extract.rows(name, "state")):
                self.rows_ingested += 1
                row_id = row.get("state_id", "")
                key = row.get("commitment_key", "")
                observed = parse_instant(row.get("observed_at", ""))
                to_state = row.get("to_state", "")
                reason = None
                if malformed or observed is None or to_state not in STATES:
                    reason = "MALFORMED_ROW"
                elif retired is not None and observed >= retired:
                    reason = "FEED_RETIRED"
                elif not in_window(observed):
                    reason = "OUT_OF_WINDOW"
                elif key not in self.winner:
                    reason = "UNKNOWN_COMMITMENT"
                if reason is not None:
                    self.rejects.append(
                        Reject(name, index, "state", row_id, key, reason))
                    continue
                item = StateRow()
                item.feed_file = name
                item.row_index = index
                item.source_class = source_class
                item.state_id = row_id
                item.commitment_key = key
                item.to_state = to_state
                item.observed_at = observed
                item.order_key = state_order_key(source_class, observed, row_id)
                self.state_candidates[key].append(item)

    def resolve_states(self):
        self.resolved_state = {}
        self.governing_class = {}
        self.states_seen = {}
        self.states_applied = {}
        self.applied_state_rows = 0
        self.illegal_transitions = 0
        for key in self.keys:
            rows = sorted(self.state_candidates.get(key, ()),
                          key=lambda s: s.order_key)
            held = "OPEN"
            applied = 0
            governing = ""
            for row in rows:
                if (held, row.to_state) in ALLOWED_TRANSITIONS:
                    held = row.to_state
                    applied += 1
                    governing = row.source_class
                else:
                    self.illegal_transitions += 1
                    self.rejects.append(
                        Reject(row.feed_file, row.row_index, "state",
                               row.state_id, key, "ILLEGAL_TRANSITION"))
            self.resolved_state[key] = held
            self.governing_class[key] = governing
            self.states_seen[key] = len(rows)
            self.states_applied[key] = applied
            self.applied_state_rows += applied

    # -- edges ------------------------------------------------------------

    def ingest_edges(self):
        self.live_edges = []
        self.dropped_edges = []
        for name in self.extract.edge_feeds:
            source_class = self.manifest.klass(name)
            retired = self.manifest.retirement(name)
            for index, (row, malformed) in enumerate(
                    self.extract.rows(name, "edge")):
                self.rows_ingested += 1
                row_id = row.get("edge_id", "")
                dependent = row.get("dependent_key", "")
                blocker = row.get("blocker_key", "")
                asserted = parse_instant(row.get("asserted_at", ""))
                reason = None
                if malformed or asserted is None:
                    reason = "MALFORMED_ROW"
                elif retired is not None and asserted >= retired:
                    reason = "FEED_RETIRED"
                elif not in_window(asserted):
                    reason = "OUT_OF_WINDOW"
                if reason is not None:
                    self.rejects.append(
                        Reject(name, index, "edge", row_id, dependent, reason))
                    continue
                item = EdgeRow()
                item.feed_file = name
                item.row_index = index
                item.source_class = source_class
                item.edge_id = row_id
                item.dependent_key = dependent
                item.blocker_key = blocker
                item.asserted_at = asserted
                item.dependent_actor = ""
                item.blocker_actor = ""
                item.drop_reason = None
                if dependent == blocker:
                    item.drop_reason = "EDGE_SELF"
                elif dependent not in self.winner or blocker not in self.winner:
                    item.drop_reason = "EDGE_DANGLING"
                else:
                    left = self.identity.resolve(
                        self.winner[dependent].obligor, asserted)
                    right = self.identity.resolve(
                        self.winner[blocker].obligor, asserted)
                    if resolution_outcome(left) != "RESOLVED" \
                            or resolution_outcome(right) != "RESOLVED":
                        item.drop_reason = "EDGE_OUT_OF_SCOPE"
                    else:
                        item.dependent_actor = left[0]
                        item.blocker_actor = right[0]
                if item.drop_reason is None:
                    self.live_edges.append(item)
                else:
                    self.dropped_edges.append(item)

    # -- blocking ---------------------------------------------------------

    def build_graph(self):
        holds = {key: self.resolved_state[key] in ("OPEN", "DEFERRED")
                 for key in self.keys}
        adjacency = defaultdict(set)
        for edge in self.live_edges:
            if holds[edge.blocker_key]:
                adjacency[edge.dependent_key].add(edge.blocker_key)
        self.adjacency = {k: sorted(v) for k, v in adjacency.items()}
        self.cycle_members = strongly_connected_members(self.keys, self.adjacency)
        self.blocked_keys = sorted(
            key for key in self.keys
            if self.adjacency.get(key) and key not in self.cycle_members)
        self.closure_pairs = []
        self.blocked_rows = []
        for key in self.blocked_keys:
            distances = {}
            queue = deque([(key, 0)])
            while queue:
                node, depth = queue.popleft()
                for target in self.adjacency.get(node, ()):
                    if target in distances:
                        continue
                    distances[target] = depth + 1
                    queue.append((target, depth + 1))
            terminal_keys = []
            for reached in sorted(distances):
                terminal = not self.adjacency.get(reached)
                if terminal:
                    terminal_keys.append(reached)
                self.closure_pairs.append({
                    "dependent_key": key,
                    "blocker_key": reached,
                    "hop_distance": distances[reached],
                    "blocker_state": self.resolved_state[reached],
                    "terminal": "yes" if terminal else "no",
                })
            self.blocked_rows.append({
                "commitment_key": key,
                "reachable_blockers": len(distances),
                "frontier_count": len(terminal_keys),
                "chain_depth": max(distances.values()) if distances else 0,
                "frontier_head": terminal_keys[0] if terminal_keys else "",
            })
        self.chain_depth = {row["commitment_key"]: row["chain_depth"]
                            for row in self.blocked_rows}

    # -- classes ----------------------------------------------------------

    def classify(self):
        self.commitment_class = {}
        self.unresolvable_reason = {}
        for key in self.keys:
            state = self.resolved_state[key]
            winner = self.winner[key]
            if state == "SETTLED":
                klass = "SETTLED"
            elif state == "WITHDRAWN":
                klass = "WITHDRAWN"
            elif key in self.cycle_members:
                klass = "UNRESOLVABLE"
                self.unresolvable_reason[key] = "CIRCULAR_DEPENDENCY"
            elif winner.obligee_status == "AMBIGUOUS":
                klass = "UNRESOLVABLE"
                self.unresolvable_reason[key] = "AMBIGUOUS_COUNTERPARTY"
            elif self.adjacency.get(key):
                klass = "BLOCKED"
            elif state == "DEFERRED":
                klass = "DEFERRED"
            else:
                klass = "ACTIONABLE"
            self.commitment_class[key] = klass
        self.ledger = sorted(
            self.keys,
            key=lambda key: (
                self.winner[key].commitment_day,
                self.winner[key].obligor_actor,
                -self.winner[key].effort_minutes,
                key,
            ),
        )
        self.open_effort = sum(
            self.winner[key].effort_minutes for key in self.keys
            if self.commitment_class[key] in OPEN_CLASSES)

    # -- attention --------------------------------------------------------

    def allocate(self):
        overrides = {}
        for row in self.extract.overrides:
            overrides[(row.get("actor_id", ""), row.get("year_month", ""))] = \
                row.get("monthly_minutes", "")
        registered = {}
        for row in self.extract.budget:
            registered[(row.get("actor_id", ""), row.get("year_month", ""))] = \
                row.get("monthly_minutes", "")
        groups = defaultdict(list)
        for key in self.ledger:
            if self.commitment_class[key] not in OPEN_CLASSES:
                continue
            winner = self.winner[key]
            if winner.effort_minutes <= 0:
                continue
            month = winner.commitment_day[:7]
            groups[(month, winner.obligor_actor)].append(key)
        self.allocated = {}
        self.month_rows = []
        self.allocations_starved = 0
        for (month, actor) in sorted(groups):
            keys = sorted(groups[(month, actor)])
            demands = [self.winner[key].effort_minutes for key in keys]
            demand = sum(demands)
            pair = (actor, month)
            if pair in overrides:
                source = "OVERRIDE"
                envelope = to_int(overrides[pair])
            elif pair in registered:
                source = "REGISTERED"
                envelope = to_int(registered[pair])
            else:
                source = "ABSENT"
                envelope = 0
            if demand <= envelope:
                shares = dict(zip(keys, demands))
            else:
                first = largest_remainder(keys, demands, envelope)
                standing = [k for k in keys if first[k] >= ALLOCATION_FLOOR]
                self.allocations_starved += len(keys) - len(standing)
                shares = {key: 0 for key in keys}
                if standing:
                    kept = [self.winner[k].effort_minutes for k in standing]
                    if sum(kept) <= envelope:
                        shares.update(zip(standing, kept))
                    else:
                        shares.update(
                            largest_remainder(standing, kept, envelope))
            for key in keys:
                self.allocated[key] = shares[key]
            self.month_rows.append({
                "year_month": month,
                "obligor_actor": actor,
                "budget_source": source,
                "budget_minutes": envelope,
                "demand_minutes": demand,
                "allocated_minutes": sum(shares[key] for key in keys),
                "open_count": len(keys),
            })
        self.allocated_total = sum(self.allocated.values())

    # -- cadences ---------------------------------------------------------

    def cadence_debt(self):
        governing = {}
        for row in self.extract.cadences:
            cadence = row.get("cadence_id", "")
            if not cadence:
                continue
            revision = to_int(row.get("revision", "0"))
            current = governing.get(cadence)
            if current is None or revision >= current[0]:
                governing[cadence] = (revision, row)
        waivers = set()
        for name in self.extract.waiver_files:
            for row, _bad in self.extract.rows(name, "waiver"):
                cadence = row.get("cadence_id", "")
                index = row.get("period_index", "")
                if not cadence or cadence not in governing:
                    continue
                try:
                    waivers.add((cadence, int(index)))
                except ValueError:
                    continue
        discharges = defaultdict(list)
        for key in self.keys:
            winner = self.winner[key]
            if winner.cadence_ref and self.commitment_class[key] == "SETTLED":
                discharges[winner.cadence_ref].append(winner.due_at)
        self.cadence_rows = []
        self.waiver_rows = []
        self.cadence_owner = {}
        self.cadence_debts = {}
        for cadence in sorted(governing):
            row = governing[cadence][1]
            period_days = to_int(row.get("period_days", "0"))
            anchor = parse_instant(row.get("anchor_at", ""))
            owner = None
            if anchor is not None:
                result = self.identity.resolve(row.get("obligor", ""), anchor)
                if resolution_outcome(result) == "RESOLVED":
                    owner = result[0]
            self.cadence_owner[cadence] = owner
            span = period_days * 1440
            starts = []
            if anchor is not None and span > 0:
                index = 0
                while anchor + index * span < WINDOW_END:
                    starts.append(anchor + index * span)
                    index += 1
            due_instants = sorted(discharges.get(cadence, ()))
            debt = 0
            streak = 0
            max_streak = 0
            discharged = 0
            waived = 0
            for index, start in enumerate(starts):
                end = min(start + span, WINDOW_END)
                is_discharged = any(start <= due < end for due in due_instants)
                is_waived = (cadence, index) in waivers
                if is_waived:
                    self.waiver_rows.append({
                        "cadence_id": cadence,
                        "period_index": index,
                        "effect": "INERT" if is_discharged else "SUPPRESSED",
                        "period_start": format_instant(start),
                    })
                if is_discharged:
                    discharged += 1
                    streak = 0
                elif is_waived:
                    waived += 1
                else:
                    debt += 1
                    streak += 1
                    max_streak = max(max_streak, streak)
            self.cadence_debts[cadence] = debt
            self.cadence_rows.append({
                "cadence_id": cadence,
                "period_days": period_days,
                "periods_elapsed": len(starts),
                "periods_discharged": discharged,
                "periods_waived": waived,
                "debt": debt,
                "max_streak": max_streak,
            })
        self.waiver_rows.sort(key=lambda r: (r["cadence_id"], r["period_index"]))
        self.principal_debt = defaultdict(int)
        for cadence, owner in self.cadence_owner.items():
            if owner is not None:
                self.principal_debt[owner] += self.cadence_debts[cadence]
        self.cadence_debt_total = sum(self.cadence_debts.values())

    # -- escalation -------------------------------------------------------

    def escalate(self):
        self.escalation_rows = []
        for key in self.ledger:
            klass = self.commitment_class[key]
            if klass not in ("ACTIONABLE", "BLOCKED"):
                continue
            winner = self.winner[key]
            share = self.allocated.get(key, 0)
            if share >= winner.effort_minutes:
                continue
            debt = self.principal_debt.get(winner.obligor_actor, 0)
            if debt < ESCALATION_DEBT_FLOOR:
                continue
            depth = self.chain_depth.get(key, 0)
            by_depth = depth >= ESCALATION_DEPTH_FLOOR
            by_month = winner.commitment_day[:7] == ESCALATION_MONTH
            if not by_depth and not by_month:
                continue
            trigger = "BOTH" if by_depth and by_month else (
                "DEPTH" if by_depth else "MONTH")
            self.escalation_rows.append({
                "commitment_key": key,
                "obligor_actor": winner.obligor_actor,
                "commitment_class": klass,
                "effort_minutes": winner.effort_minutes,
                "allocated_minutes": share,
                "shortfall_minutes": winner.effort_minutes - share,
                "principal_debt": debt,
                "chain_depth": depth,
                "trigger": trigger,
            })
        self.escalation_rows.sort(
            key=lambda r: (-r["shortfall_minutes"], r["commitment_key"]))

    # -- rollups ----------------------------------------------------------

    def rollups(self):
        self.actor_rollup = {}
        self.project_rollup = {}
        actor_keys = defaultdict(list)
        project_keys = defaultdict(list)
        for key in self.keys:
            winner = self.winner[key]
            actor_keys[winner.obligor_actor].append(key)
            project_keys[winner.project_root].append(key)
        for actor in sorted(actor_keys):
            entry = {name: 0 for name in CLASSES}
            open_effort = 0
            allocated = 0
            for key in actor_keys[actor]:
                entry[self.commitment_class[key]] += 1
                if self.commitment_class[key] in OPEN_CLASSES:
                    open_effort += self.winner[key].effort_minutes
                allocated += self.allocated.get(key, 0)
            entry["commitment_count"] = len(actor_keys[actor])
            entry["open_effort_minutes"] = open_effort
            entry["allocated_minutes"] = allocated
            self.actor_rollup[actor] = entry
        for root in sorted(project_keys):
            entry = {name: 0 for name in CLASSES}
            open_effort = 0
            for key in project_keys[root]:
                entry[self.commitment_class[key]] += 1
                if self.commitment_class[key] in OPEN_CLASSES:
                    open_effort += self.winner[key].effort_minutes
            entry["commitment_count"] = len(project_keys[root])
            entry["open_effort_minutes"] = open_effort
            self.project_rollup[root] = entry
        self.actor_commitments = {a: len(v) for a, v in actor_keys.items()}

    # -- identities -------------------------------------------------------

    def check_identities(self):
        rows_rejected = len(self.rejects)
        rows_accepted = self.rows_ingested - rows_rejected
        partition = (len(self.accepted_assertions) + self.applied_state_rows
                     + len(self.live_edges) + len(self.dropped_edges))
        class_counts = {name: 0 for name in CLASSES}
        for key in self.keys:
            class_counts[self.commitment_class[key]] += 1
        actor_effort = sum(entry["open_effort_minutes"]
                           for entry in self.actor_rollup.values())
        project_effort = sum(entry["open_effort_minutes"]
                             for entry in self.project_rollup.values())
        frontier = sum(row["frontier_count"] for row in self.blocked_rows)
        terminal = sum(1 for pair in self.closure_pairs
                       if pair["terminal"] == "yes")
        self.rows_rejected = rows_rejected
        self.rows_accepted = rows_accepted
        self.class_counts = class_counts
        self.residuals = {
            "I1_row_partition": rows_accepted - partition,
            "I2_class_partition": len(self.keys) - sum(class_counts.values()),
            "I3_actor_effort": actor_effort - self.open_effort,
            "I4_project_effort": project_effort - self.open_effort,
            "I5_closure_frontier": frontier - terminal,
        }


def clamp_effort(minutes):
    if minutes <= 0:
        return 0
    return min(max(minutes, EFFORT_FLOOR), EFFORT_CEILING)


def to_int(text):
    try:
        return int(str(text).strip())
    except (TypeError, ValueError):
        return 0


def largest_remainder(keys, demands, envelope):
    total = sum(demands)
    if total <= 0 or envelope <= 0:
        return {key: 0 for key in keys}
    shares = {}
    remainders = []
    assigned = 0
    for key, demand in zip(keys, demands):
        exact = envelope * demand
        base = exact // total
        shares[key] = base
        assigned += base
        remainders.append((-(exact - base * total), key))
    remainders.sort()
    leftover = envelope - assigned
    for _remainder, key in remainders[:max(leftover, 0)]:
        shares[key] += 1
    return shares


def strongly_connected_members(nodes, adjacency):
    """Every node that stands on a directed cycle of the given graph."""
    index = {}
    low = {}
    on_stack = {}
    stack = []
    counter = [0]
    members = set()
    for root in nodes:
        if root in index:
            continue
        work = [(root, iter(adjacency.get(root, ())))]
        index[root] = low[root] = counter[0]
        counter[0] += 1
        stack.append(root)
        on_stack[root] = True
        while work:
            node, children = work[-1]
            advanced = False
            for child in children:
                if child not in index:
                    index[child] = low[child] = counter[0]
                    counter[0] += 1
                    stack.append(child)
                    on_stack[child] = True
                    work.append((child, iter(adjacency.get(child, ()))))
                    advanced = True
                    break
                if on_stack.get(child):
                    low[node] = min(low[node], index[child])
            if advanced:
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
            if low[node] == index[node]:
                component = []
                while True:
                    popped = stack.pop()
                    on_stack[popped] = False
                    component.append(popped)
                    if popped == node:
                        break
                if len(component) > 1:
                    members.update(component)
                elif component[0] in adjacency.get(component[0], ()):
                    members.add(component[0])
    return members


# ------------------------------------------------------------------- output


def write_text(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def write_lines(path, lines):
    write_text(path, "".join(line + "\n" for line in lines))


def write_delimited(path, header, rows, sep=","):
    lines = [sep.join(header)]
    for row in rows:
        lines.append(sep.join(cell(row[name]) for name in header))
    write_lines(path, lines)


def cell(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    return value


def write_jsonl(path, objects):
    lines = [json.dumps(obj, sort_keys=True, separators=(",", ":"))
             for obj in objects]
    write_lines(path, lines)


def write_json(path, obj):
    write_text(path, json.dumps(obj, sort_keys=True, indent=2) + "\n")


AUDIT_ORDER = [
    ("rows_ingested", True),
    ("rows_rejected", True),
    ("rows_accepted", False),
    ("commitments_admitted", True),
    ("class_actionable", True),
    ("class_blocked", True),
    ("class_deferred", True),
    ("class_settled", True),
    ("class_unresolvable", True),
    ("class_withdrawn", True),
    ("reject_ambiguous_identity", False),
    ("reject_feed_retired", False),
    ("reject_illegal_transition", False),
    ("reject_malformed_row", False),
    ("reject_nonpositive_effort", False),
    ("reject_out_of_window", False),
    ("reject_unknown_commitment", False),
    ("reject_unknown_principal", False),
    ("reject_unknown_project", False),
    ("live_edges", True),
    ("dropped_edges", True),
    ("closure_pairs", True),
    ("blocked_commitments", True),
    ("open_effort_minutes", True),
    ("allocated_minutes", True),
    ("escalated_commitments", True),
    ("cadence_debt_total", True),
]


def publish(closure, staging, source_bytes):
    c = closure

    def out(name):
        return os.path.join(staging, name)

    with open(out("reconcile.py"), "wb") as handle:
        handle.write(source_bytes)

    assertions = sorted(c.accepted_assertions, key=lambda a: a.assertion_id)
    write_jsonl(out("normalized_assertions.jsonl"), [{
        "assertion_id": a.assertion_id,
        "commitment_key": a.commitment_key,
        "obligor_actor": a.obligor_actor,
        "obligee_actor": a.obligee_actor,
        "obligee_status": a.obligee_status,
        "project_code": a.project_code,
        "project_root": a.project_root,
        "due_at": format_instant(a.due_at),
        "commitment_day": a.commitment_day,
        "effort_minutes": a.effort_minutes,
        "effort_origin": a.effort_origin,
        "cadence_ref": a.cadence_ref,
        "observed_at": format_instant(a.observed_at),
        "source_class": a.source_class,
    } for a in assertions])

    rejects = sorted(c.rejects, key=lambda r: (
        r.reason_code, r.feed_file, r.row_index, r.record_id))
    write_delimited(
        out("rejects.csv"),
        ["feed_file", "row_index", "record_kind", "record_id",
         "commitment_key", "reason_code"],
        [{"feed_file": r.feed_file, "row_index": r.row_index,
          "record_kind": r.record_kind, "record_id": r.record_id,
          "commitment_key": r.commitment_key, "reason_code": r.reason_code}
         for r in rejects])

    surfaces = defaultdict(lambda: {"actors": set(), "count": 0, "hops": 0})
    for a in c.accepted_assertions:
        entry = surfaces[fold(a.obligor)]
        entry["actors"].add(a.obligor_actor)
        entry["count"] += 1
        entry["hops"] = max(entry["hops"], a.obligor_hops)
    write_jsonl(out("alias_resolution.jsonl"), [{
        "surface_folded": surface,
        "distinct_actors": sorted(surfaces[surface]["actors"]),
        "assertion_count": surfaces[surface]["count"],
        "max_hops": surfaces[surface]["hops"],
    } for surface in sorted(surfaces)])

    write_delimited(
        out("actor_roster.csv"),
        ["actor_id", "canonical_handle", "commitment_count",
         "open_effort_minutes"],
        [{"actor_id": actor,
          "canonical_handle": c.identity.canonical_handle[actor],
          "commitment_count": c.actor_commitments.get(actor, 0),
          "open_effort_minutes": c.actor_rollup.get(actor, {}).get(
              "open_effort_minutes", 0)}
         for actor in c.identity.actors])

    lineage = defaultdict(int)
    for a in c.accepted_assertions:
        lineage[a.project_code] += 1
    write_delimited(
        out("project_lineage.csv"),
        ["project_code", "project_root", "assertion_count"],
        [{"project_code": code, "project_root": c.projects.root(code),
          "assertion_count": lineage[code]} for code in sorted(lineage)])

    write_delimited(
        out("assertion_contests.csv"),
        ["commitment_key", "winning_assertion", "winning_class",
         "contender_count", "distinct_classes"],
        [{"commitment_key": key,
          "winning_assertion": c.winner[key].assertion_id,
          "winning_class": c.winner[key].source_class,
          "contender_count": len(c.contenders[key]),
          "distinct_classes": len({a.source_class for a in c.contenders[key]})}
         for key in c.keys])

    write_jsonl(out("commitment_ledger.jsonl"), [{
        "commitment_key": key,
        "obligor_actor": c.winner[key].obligor_actor,
        "obligee_actor": c.winner[key].obligee_actor,
        "project_code": c.winner[key].project_code,
        "project_root": c.winner[key].project_root,
        "commitment_day": c.winner[key].commitment_day,
        "due_at": format_instant(c.winner[key].due_at),
        "effort_minutes": c.winner[key].effort_minutes,
        "effort_origin": c.winner[key].effort_origin,
        "resolved_state": c.resolved_state[key],
        "commitment_class": c.commitment_class[key],
        "cadence_ref": c.winner[key].cadence_ref,
        "source_class": c.winner[key].source_class,
        "winning_assertion": c.winner[key].assertion_id,
    } for key in c.ledger])

    write_delimited(
        out("state_resolution.csv"),
        ["commitment_key", "resolved_state", "assertions_seen",
         "assertions_applied", "governing_class"],
        [{"commitment_key": key, "resolved_state": c.resolved_state[key],
          "assertions_seen": c.states_seen[key],
          "assertions_applied": c.states_applied[key],
          "governing_class": c.governing_class[key]} for key in c.keys])

    live = sorted(c.live_edges, key=lambda e: (
        e.dependent_key, e.blocker_key, e.edge_id))
    write_delimited(
        out("live_edges.csv"),
        ["edge_id", "dependent_key", "blocker_key", "asserted_at",
         "dependent_actor", "blocker_actor"],
        [{"edge_id": e.edge_id, "dependent_key": e.dependent_key,
          "blocker_key": e.blocker_key,
          "asserted_at": format_instant(e.asserted_at),
          "dependent_actor": e.dependent_actor,
          "blocker_actor": e.blocker_actor} for e in live])

    dropped = sorted(c.dropped_edges, key=lambda e: (e.drop_reason, e.edge_id))
    write_delimited(
        out("dropped_edges.csv"),
        ["edge_id", "dependent_key", "blocker_key", "asserted_at",
         "drop_reason"],
        [{"edge_id": e.edge_id, "dependent_key": e.dependent_key,
          "blocker_key": e.blocker_key,
          "asserted_at": format_instant(e.asserted_at),
          "drop_reason": e.drop_reason} for e in dropped])

    write_jsonl(out("blocking_closure.jsonl"), sorted(
        c.closure_pairs, key=lambda p: (p["dependent_key"], p["blocker_key"])))

    write_delimited(
        out("blocked_commitments.csv"),
        ["commitment_key", "reachable_blockers", "frontier_count",
         "chain_depth", "frontier_head"],
        sorted(c.blocked_rows, key=lambda r: r["commitment_key"]))

    def queue_rows(klass):
        return [{"commitment_key": key,
                 "obligor_actor": c.winner[key].obligor_actor,
                 "commitment_day": c.winner[key].commitment_day,
                 "effort_minutes": c.winner[key].effort_minutes,
                 "project_root": c.winner[key].project_root}
                for key in c.ledger if c.commitment_class[key] == klass]

    queue_header = ["commitment_key", "obligor_actor", "commitment_day",
                    "effort_minutes", "project_root"]
    write_delimited(out("actionable_queue.tsv"), queue_header,
                    queue_rows("ACTIONABLE"), "\t")
    write_delimited(out("deferred_queue.psv"), queue_header,
                    queue_rows("DEFERRED"), "|")

    write_delimited(
        out("withdrawn_register.csv"),
        ["commitment_key", "obligor_actor", "commitment_day",
         "effort_minutes", "source_class"],
        [{"commitment_key": key,
          "obligor_actor": c.winner[key].obligor_actor,
          "commitment_day": c.winner[key].commitment_day,
          "effort_minutes": c.winner[key].effort_minutes,
          "source_class": c.winner[key].source_class}
         for key in c.ledger if c.commitment_class[key] == "WITHDRAWN"])

    unresolvable = [{
        "commitment_key": key,
        "reason_code": c.unresolvable_reason[key],
        "obligor_actor": c.winner[key].obligor_actor,
        "commitment_day": c.winner[key].commitment_day,
    } for key in c.keys if c.commitment_class[key] == "UNRESOLVABLE"]
    unresolvable.sort(key=lambda r: (r["reason_code"], r["commitment_key"]))
    write_jsonl(out("unresolvable.jsonl"), unresolvable)

    write_delimited(
        out("cadence_debt.csv"),
        ["cadence_id", "period_days", "periods_elapsed", "periods_discharged",
         "periods_waived", "debt", "max_streak"],
        c.cadence_rows)

    write_jsonl(out("waiver_trace.jsonl"), c.waiver_rows)

    allocation_rows = []
    for key in c.allocated:
        winner = c.winner[key]
        allocation_rows.append({
            "year_month": winner.commitment_day[:7],
            "obligor_actor": winner.obligor_actor,
            "commitment_key": key,
            "demand_minutes": winner.effort_minutes,
            "allocated_minutes": c.allocated[key],
        })
    allocation_rows.sort(key=lambda r: (
        r["year_month"], r["obligor_actor"], r["commitment_key"]))
    write_delimited(
        out("attention_allocation.csv"),
        ["year_month", "obligor_actor", "commitment_key", "demand_minutes",
         "allocated_minutes"],
        allocation_rows)

    write_delimited(
        out("month_load_index.csv"),
        ["year_month", "obligor_actor", "budget_source", "budget_minutes",
         "demand_minutes", "allocated_minutes", "open_count"],
        c.month_rows)

    write_delimited(
        out("escalation_queue.csv"),
        ["commitment_key", "obligor_actor", "commitment_class",
         "effort_minutes", "allocated_minutes", "shortfall_minutes",
         "principal_debt", "chain_depth", "trigger"],
        c.escalation_rows)

    write_json(out("actor_rollup.json"), c.actor_rollup)
    write_json(out("project_rollup.json"), c.project_rollup)

    write_jsonl(out("provenance_index.jsonl"), [{
        "commitment_key": key,
        "winning_assertion": c.winner[key].assertion_id,
        "contributing_assertions": sorted(
            a.assertion_id for a in c.contenders[key]),
        "source_files": sorted({a.feed_file for a in c.contenders[key]}),
        "state_assertions": sorted(
            s.state_id for s in c.state_candidates.get(key, ())),
    } for key in c.keys])

    reject_counts = defaultdict(int)
    for reject in c.rejects:
        reject_counts[reject.reason_code] += 1
    figures = {
        "rows_ingested": c.rows_ingested,
        "rows_rejected": c.rows_rejected,
        "rows_accepted": c.rows_accepted,
        "commitments_admitted": len(c.keys),
        "live_edges": len(c.live_edges),
        "dropped_edges": len(c.dropped_edges),
        "closure_pairs": len(c.closure_pairs),
        "blocked_commitments": len(c.blocked_rows),
        "open_effort_minutes": c.open_effort,
        "allocated_minutes": c.allocated_total,
        "escalated_commitments": len(c.escalation_rows),
        "cadence_debt_total": c.cadence_debt_total,
    }
    for name in CLASSES:
        figures["class_" + name.lower()] = c.class_counts[name]
    for code in REASON_CODES:
        figures["reject_" + code.lower()] = reject_counts[code]
    write_delimited(
        out("audit_totals.csv"), ["metric", "value"],
        [{"metric": name, "value": figures[name]} for name, _star in AUDIT_ORDER])

    lines = ["CALDERMOOR COMMITMENT CLOSURE"]
    for name, starred in AUDIT_ORDER:
        if starred:
            lines.append("%s %d" % (name, figures[name]))
    for name in IDENTITIES:
        lines.append("identity_%s %d" % (name, c.residuals[name]))
    write_lines(out("reconciliation.txt"), lines)

    write_json(out("validation_report.json"), {
        "identities": {name: c.residuals[name] for name in IDENTITIES},
        "identities_checked": list(IDENTITIES),
        "all_residuals_zero": all(
            c.residuals[name] == 0 for name in IDENTITIES),
    })

    split_surfaces = sum(1 for entry in surfaces.values()
                         if len(entry["actors"]) > 1)
    multi_hop = sum(1 for a in c.accepted_assertions if a.obligor_hops >= 2)
    tiebreaks = 0
    for left, right in zip(c.ledger, c.ledger[1:]):
        one, two = c.winner[left], c.winner[right]
        if one.commitment_day == two.commitment_day \
                and one.obligor_actor == two.obligor_actor \
                and one.effort_minutes != two.effort_minutes:
            tiebreaks += 1
    write_json(out("run_manifest.json"), {
        "day_boundary_offset_minutes": DAY_BOUNDARY_OFFSET_MINUTES,
        "effort_floor_minutes": EFFORT_FLOOR,
        "effort_ceiling_minutes": EFFORT_CEILING,
        "allocation_floor_minutes": ALLOCATION_FLOOR,
        "window_start": WINDOW_START_TEXT,
        "window_end": WINDOW_END_TEXT,
        "reason_codes": sorted(REASON_CODES),
        "commitment_classes": sorted(CLASSES),
        "retired_feeds": c.manifest.retired_feeds,
        "split_surfaces": split_surfaces,
        "multi_hop_assertions": multi_hop,
        "order_tiebreaks_applied": tiebreaks,
        "edges_dropped_out_of_scope": sum(
            1 for e in c.dropped_edges if e.drop_reason == "EDGE_OUT_OF_SCOPE"),
        "waivers_suppressing": sum(
            1 for r in c.waiver_rows if r["effect"] == "SUPPRESSED"),
        "waivers_inert": sum(
            1 for r in c.waiver_rows if r["effect"] == "INERT"),
        "allocations_starved": c.allocations_starved,
        "illegal_transitions": reject_counts["ILLEGAL_TRANSITION"],
    })


DELIVERABLES = [
    "reconcile.py",
    "normalized_assertions.jsonl",
    "rejects.csv",
    "alias_resolution.jsonl",
    "actor_roster.csv",
    "project_lineage.csv",
    "assertion_contests.csv",
    "commitment_ledger.jsonl",
    "state_resolution.csv",
    "live_edges.csv",
    "dropped_edges.csv",
    "blocking_closure.jsonl",
    "blocked_commitments.csv",
    "actionable_queue.tsv",
    "deferred_queue.psv",
    "withdrawn_register.csv",
    "unresolvable.jsonl",
    "cadence_debt.csv",
    "waiver_trace.jsonl",
    "attention_allocation.csv",
    "month_load_index.csv",
    "escalation_queue.csv",
    "actor_rollup.json",
    "project_rollup.json",
    "provenance_index.jsonl",
    "audit_totals.csv",
    "reconciliation.txt",
    "validation_report.json",
    "run_manifest.json",
]


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: reconcile.py DATA_DIR OUT_DIR\n")
        return 2
    data_dir = os.path.abspath(argv[1])
    out_dir = os.path.abspath(argv[2])
    if out_dir == data_dir or out_dir.startswith(data_dir + os.sep):
        sys.stderr.write("reconcile: the output directory would overwrite "
                         "the extract\n")
        return 2
    with open(os.path.abspath(__file__), "rb") as handle:
        source_bytes = handle.read()
    parent = os.path.dirname(out_dir) or "."
    os.makedirs(parent, exist_ok=True)
    staging = tempfile.mkdtemp(prefix=".reconcile_stage_", dir=parent)
    try:
        closure = Closure(Extract(data_dir))
        publish(closure, staging, source_bytes)
        produced = sorted(os.listdir(staging))
        if produced != sorted(DELIVERABLES):
            raise Unfinishable("staging holds %d deliverables" % len(produced))
        os.makedirs(out_dir, exist_ok=True)
        for name in sorted(os.listdir(out_dir)):
            victim = os.path.join(out_dir, name)
            if os.path.isdir(victim) and not os.path.islink(victim):
                shutil.rmtree(victim)
            else:
                os.remove(victim)
        for name in DELIVERABLES:
            os.replace(os.path.join(staging, name),
                       os.path.join(out_dir, name))
    except Unfinishable as exc:
        sys.stderr.write("reconcile: %s\n" % exc)
        return 1
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
