#!/usr/bin/env python3
"""Caldermoor commitment closure.

Reads one extract directory and writes the twenty-nine deliverables of
output-contract.md into an output directory.

    python3 reconcile.py DATA_DIR OUT_DIR
"""

import datetime
import json
import os
import re
import shutil
import sys
import tempfile
import unicodedata

# ---------------------------------------------------------------- constants

WINDOW_START = "2032-03-01T00:00Z"
WINDOW_END = "2032-12-01T00:00Z"
DAY_OFFSET_MINUTES = 240
EFFORT_FLOOR = 15
EFFORT_CEILING = 480
ALLOCATION_FLOOR = 15
WAIVER_ALLOWANCE = 4
RESERVE_PER_WAIT = 30
RESERVE_PER_WAIVED = 15
ESCALATION_DEBT = 4
ESCALATION_DEPTH = 2
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
STATES = ("OPEN", "SETTLED", "DEFERRED", "WITHDRAWN")
LEGAL_TRANSITIONS = {
    ("OPEN", "SETTLED"),
    ("OPEN", "DEFERRED"),
    ("OPEN", "WITHDRAWN"),
    ("DEFERRED", "OPEN"),
    ("DEFERRED", "WITHDRAWN"),
}
UNIT_FACTOR = {"minutes": 1, "hours": 60, "halfdays": 240}
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
IDENTITIES = [
    "I1_row_partition",
    "I2_class_partition",
    "I3_actor_effort",
    "I4_project_effort",
    "I5_closure_frontier",
]

COMMITMENT_FIELDS = (
    "assertion_id",
    "commitment_key",
    "obligor",
    "obligee",
    "project_ref",
    "due_at",
    "effort",
    "cadence_ref",
    "observed_at",
)
STATE_FIELDS = ("state_id", "commitment_key", "to_state", "observed_at")
EDGE_FIELDS = ("edge_id", "dependent_key", "blocker_key", "asserted_at")

COMMITMENT_COLUMNS = (
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
STATE_COLUMNS = (
    ("state_id", 12),
    ("commitment_key", 12),
    ("to_state", 12),
    ("observed_at", 18),
)

DELIMITERS = {"csv": ",", "tsv": "\t", "psv": "|"}
EPOCH = datetime.datetime(2000, 1, 1)
INSTANT_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})Z$")
INTEGER_RE = re.compile(r"^[+-]?[0-9]+$")
KV_LINE_RE = re.compile(r"^([^:]+):(?: (.*))?$")
ATTR_RE = re.compile(r'([A-Za-z_][\w.-]*)="([^"]*)"')
ELEMENT_RE = re.compile(r"^<[A-Za-z_][\w.-]*(\s|/|>)")


# ------------------------------------------------------------------ instants


def parse_instant(text):
    if not isinstance(text, str):
        return None
    match = INSTANT_RE.match(text)
    if not match:
        return None
    year, month, day, hour, minute = (int(g) for g in match.groups())
    if hour > 23 or minute > 59:
        return None
    try:
        moment = datetime.datetime(year, month, day, hour, minute)
    except ValueError:
        return None
    return (moment - EPOCH).days * 1440 + moment.hour * 60 + moment.minute


def format_instant(minutes):
    moment = EPOCH + datetime.timedelta(minutes=minutes)
    return "%04d-%02d-%02dT%02d:%02dZ" % (
        moment.year,
        moment.month,
        moment.day,
        moment.hour,
        moment.minute,
    )


def commitment_day(minutes):
    moment = EPOCH + datetime.timedelta(minutes=minutes - DAY_OFFSET_MINUTES)
    return "%04d-%02d-%02d" % (moment.year, moment.month, moment.day)


WINDOW_START_M = parse_instant(WINDOW_START)
WINDOW_END_M = parse_instant(WINDOW_END)


def in_window(minutes):
    return WINDOW_START_M <= minutes < WINDOW_END_M


# -------------------------------------------------------------------- layouts


def read_text(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def split_lines(text):
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def unescape_xml(value):
    value = value.replace("&lt;", "<").replace("&gt;", ">")
    value = value.replace("&quot;", '"').replace("&apos;", "'")
    return value.replace("&amp;", "&")


def records_delimited(text, delimiter):
    lines = split_lines(text)
    if not lines:
        return []
    header = lines[0].split(delimiter)
    out = []
    for line in lines[1:]:
        parts = line.split(delimiter)
        broken = len(parts) != len(header)
        out.append((dict(zip(header, parts)), broken))
    return out


def records_jsonl(text):
    out = []
    for line in split_lines(text):
        try:
            value = json.loads(line)
        except ValueError:
            out.append(({}, True))
            continue
        if not isinstance(value, dict):
            out.append(({}, True))
            continue
        fields = {}
        for key, item in value.items():
            if item is None:
                fields[key] = ""
            elif isinstance(item, bool):
                fields[key] = "true" if item else "false"
            elif isinstance(item, str):
                fields[key] = item
            elif isinstance(item, float) and item.is_integer():
                fields[key] = str(int(item))
            else:
                fields[key] = str(item)
        out.append((fields, False))
    return out


def records_kv(text):
    if text.endswith("\n"):
        text = text[:-1]
    if text == "":
        return []
    out = []
    for block in text.split("\n\n"):
        fields = {}
        broken = False
        for line in block.split("\n"):
            match = KV_LINE_RE.match(line)
            if not match:
                broken = True
                continue
            fields[match.group(1)] = match.group(2) or ""
        out.append((fields, broken))
    return out


def records_rec(text):
    out = []
    for line in split_lines(text):
        fields = {}
        broken = False
        for segment in line.split(";"):
            if "=" not in segment:
                broken = True
                continue
            name, _, value = segment.partition("=")
            fields[name] = value
        out.append((fields, broken))
    return out


def records_xml(text):
    lines = split_lines(text)
    if len(lines) < 2:
        return []
    out = []
    for line in lines[1:-1]:
        stripped = line.strip()
        if not ELEMENT_RE.match(stripped):
            out.append(({}, True))
            continue
        fields = {}
        for name, value in ATTR_RE.findall(stripped):
            fields[name] = unescape_xml(value)
        out.append((fields, not fields))
    return out


def records_fixed(text, columns):
    width = sum(size for _, size in columns)
    out = []
    for line in split_lines(text):
        fields = {}
        position = 0
        for name, size in columns:
            fields[name] = line[position:position + size].rstrip(" ")
            position += size
        out.append((fields, len(line) > width))
    return out


def load_records(path, kind):
    extension = path.rsplit(".", 1)[-1]
    text = read_text(path)
    if extension in DELIMITERS:
        return records_delimited(text, DELIMITERS[extension])
    if extension == "jsonl":
        return records_jsonl(text)
    if extension == "kv":
        return records_kv(text)
    if extension == "rec":
        return records_rec(text)
    if extension == "xml":
        return records_xml(text)
    if extension == "fixed":
        columns = COMMITMENT_COLUMNS if kind == "commitment" else STATE_COLUMNS
        return records_fixed(text, columns)
    raise ValueError("unknown layout: " + path)


def load_table(path):
    """Reference tables: field dicts for every well formed line, others skipped."""
    if not os.path.exists(path):
        return []
    return [fields for fields, broken in load_records(path, "table") if not broken]


def carries_effort_unit(name):
    return not name.endswith(".fixed") and not name.endswith(".rec")


# ------------------------------------------------------------------- identity


def fold(text):
    text = unicodedata.normalize("NFC", text).strip().casefold()
    for character in ".-_'":
        text = text.replace(character, "")
    return " ".join(text.split()).strip()


class Register(object):
    def __init__(self, data_dir):
        self.handle_actor = {}
        self.actor_handle = {}
        self._load_roster(data_dir)
        self.alias_edges = {}
        self.assertions = set()
        self._load_aliases(data_dir)
        self._cache = {}

    def _load_roster(self, data_dir):
        lines = []
        for name in sorted(os.listdir(data_dir)):
            if not name.startswith("roster_"):
                continue
            for fields in load_table(os.path.join(data_dir, name)):
                actor = fields.get("actor_id", "")
                handle = fields.get("canonical_handle", "")
                if not actor or not handle:
                    continue
                lines.append((actor, handle))
        spellings = {}
        for actor, handle in lines:
            self.handle_actor[fold(handle)] = actor
            counts = spellings.setdefault(actor, {})
            counts[handle] = counts.get(handle, 0) + 1
        for actor, counts in spellings.items():
            best = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
            self.actor_handle[actor] = best

    def _load_aliases(self, data_dir):
        for name in sorted(os.listdir(data_dir)):
            if not name.startswith("aliases_"):
                continue
            for fields in load_table(os.path.join(data_dir, name)):
                surface = fields.get("surface")
                target = fields.get("target")
                start = parse_instant(fields.get("scope_start", ""))
                end = parse_instant(fields.get("scope_end", ""))
                if surface is None or target is None:
                    continue
                if start is None or end is None:
                    continue
                self.assertions.add((fold(surface), fold(target), start, end))
        for surface, target, start, end in sorted(self.assertions):
            if start >= end:
                continue
            self.alias_edges.setdefault(surface, []).append((target, start, end))

    def resolve(self, surface, instant):
        """Return (outcome, actor_id, hop_count)."""
        folded = fold(surface)
        key = (folded, instant)
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        distance = {folded: 0}
        frontier = [folded]
        while frontier:
            following = []
            for node in frontier:
                step = distance[node] + 1
                for target, start, end in self.alias_edges.get(node, ()):
                    if start <= instant < end and target not in distance:
                        distance[target] = step
                        following.append(target)
            frontier = following
        reached = {}
        for node, hops in distance.items():
            actor = self.handle_actor.get(node)
            if actor is None:
                continue
            if actor not in reached or hops < reached[actor]:
                reached[actor] = hops
        if len(reached) == 1:
            actor, hops = next(iter(reached.items()))
            result = ("RESOLVED", actor, hops)
        elif len(reached) > 1:
            result = ("AMBIGUOUS_IDENTITY", None, None)
        else:
            result = ("UNKNOWN_PRINCIPAL", None, None)
        self._cache[key] = result
        return result


# ------------------------------------------------------------------- projects


class Projects(object):
    def __init__(self, data_dir):
        self.revisions = {}
        for fields in load_table(os.path.join(data_dir, "project_registry.csv")):
            code = fields.get("project_code", "")
            if not code:
                continue
            try:
                revision = int(fields.get("revision", ""))
            except ValueError:
                continue
            revised = parse_instant(fields.get("revised_at", ""))
            if revised is None:
                continue
            try:
                default = int(fields.get("default_effort", ""))
            except ValueError:
                continue
            self.revisions.setdefault(code, []).append(
                (revised, revision, fields.get("parent_code", ""), default)
            )
        for entries in self.revisions.values():
            entries.sort()
        self.renames = {}
        for fields in load_table(os.path.join(data_dir, "project_events.tsv")):
            if fields.get("event_type") != "RENAME":
                continue
            effective = parse_instant(fields.get("effective_at", ""))
            if effective is None:
                continue
            self.renames.setdefault(fields.get("project_code", ""), []).append(
                (effective, fields.get("event_id", ""), fields.get("payload", ""))
            )
        for entries in self.renames.values():
            entries.sort()
        self._roots = {}

    def resolve(self, code, instant):
        current = code
        seen = {code}
        while True:
            applicable = [
                entry for entry in self.renames.get(current, ()) if entry[0] <= instant
            ]
            if not applicable:
                break
            nxt = applicable[-1][2]
            if nxt in seen:
                break
            seen.add(nxt)
            current = nxt
        if current not in self.revisions:
            return None
        return current

    def governing(self, code, instant):
        entries = [
            entry for entry in self.revisions.get(code, ()) if entry[0] <= instant
        ]
        if not entries:
            return None
        return entries[-1]

    def latest_parent(self, code):
        entries = self.revisions.get(code)
        if not entries:
            return ""
        return entries[-1][2]

    def root(self, code):
        if code in self._roots:
            return self._roots[code]
        current = code
        seen = {code}
        while True:
            parent = self.latest_parent(current)
            if not parent or parent not in self.revisions or parent in seen:
                break
            seen.add(parent)
            current = parent
        self._roots[code] = current
        return current


# ----------------------------------------------------------------- allocation


def largest_remainder(items, total_minutes):
    """items: list of (key, weight). Returns {key: share}."""
    weight_sum = sum(weight for _, weight in items)
    if weight_sum <= 0 or total_minutes <= 0:
        return {key: 0 for key, _ in items}
    shares = {}
    remainders = []
    assigned = 0
    for key, weight in items:
        exact = weight * total_minutes
        base = exact // weight_sum
        shares[key] = base
        assigned += base
        remainders.append((exact - base * weight_sum, key))
    left = total_minutes - assigned
    remainders.sort(key=lambda item: (-item[0], item[1]))
    for index in range(left):
        shares[remainders[index][1]] += 1
    return shares


# ----------------------------------------------------------------------- run


class Closure(object):
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.rejects = []
        self.rows_ingested = 0
        self.feed_class = {}
        self.feed_retired = {}
        self.retired_feeds = []
        self._load_manifest()
        self.register = Register(data_dir)
        self.projects = Projects(data_dir)

    # ------------------------------------------------------------- manifest
    def _load_manifest(self):
        best = {}
        for fields in load_table(os.path.join(self.data_dir, "feed_manifest.csv")):
            name = fields.get("feed_file", "")
            if not name:
                continue
            try:
                revision = int(fields.get("revision", ""))
            except ValueError:
                continue
            if name not in best or revision > best[name][0]:
                best[name] = (
                    revision,
                    fields.get("source_class", ""),
                    fields.get("retired_at", ""),
                )
        for name, (_, source_class, retired) in best.items():
            self.feed_class[name] = source_class
            self.feed_retired[name] = parse_instant(retired)
            if retired:
                self.retired_feeds.append(name)
        self.retired_feeds.sort()

    def source_class(self, name):
        return self.feed_class.get(name, name.split("_")[1].split(".")[0])

    def rank(self, name):
        return CLASS_RANK.get(self.source_class(name), -1)

    def reject(self, feed, index, kind, record_id, key, reason):
        self.rejects.append((feed, index, kind, record_id, key, reason))

    def feeds(self, prefix):
        return sorted(
            name
            for name in os.listdir(self.data_dir)
            if name.startswith(prefix + "_")
        )

    # ---------------------------------------------------------- commitments
    def read_commitments(self):
        self.assertions = []
        for feed in self.feeds("commitments"):
            has_unit = carries_effort_unit(feed)
            source = self.source_class(feed)
            retired = self.feed_retired.get(feed)
            for index, (fields, broken) in enumerate(
                load_records(os.path.join(self.data_dir, feed), "commitment")
            ):
                self.rows_ingested += 1
                record_id = fields.get("assertion_id", "")
                key = fields.get("commitment_key", "")
                missing = [name for name in COMMITMENT_FIELDS if name not in fields]
                if has_unit and "effort_unit" not in fields:
                    missing.append("effort_unit")
                due = parse_instant(fields.get("due_at", ""))
                observed = parse_instant(fields.get("observed_at", ""))
                effort_text = fields.get("effort", "")
                unit = fields.get("effort_unit", "") if has_unit else None
                stated = None
                bad_effort = False
                if effort_text != "" and effort_text != "null":
                    if INTEGER_RE.match(effort_text):
                        stated = int(effort_text)
                    else:
                        bad_effort = True
                bad_unit = False
                if stated is not None and stated > 0 and has_unit:
                    bad_unit = unit not in UNIT_FACTOR
                if broken or missing or due is None or observed is None or bad_effort or bad_unit:
                    self.reject(feed, index, "commitment", record_id, key, "MALFORMED_ROW")
                    continue
                if retired is not None and observed >= retired:
                    self.reject(feed, index, "commitment", record_id, key, "FEED_RETIRED")
                    continue
                if not in_window(due):
                    self.reject(feed, index, "commitment", record_id, key, "OUT_OF_WINDOW")
                    continue
                outcome, actor, hops = self.register.resolve(
                    fields.get("obligor", ""), observed
                )
                if outcome != "RESOLVED":
                    self.reject(feed, index, "commitment", record_id, key, outcome)
                    continue
                code = self.projects.resolve(fields.get("project_ref", ""), observed)
                if code is None:
                    self.reject(feed, index, "commitment", record_id, key, "UNKNOWN_PROJECT")
                    continue
                if stated is not None and stated <= 0:
                    self.reject(
                        feed, index, "commitment", record_id, key, "NONPOSITIVE_EFFORT"
                    )
                    continue
                if effort_text == "null":
                    origin = "DECLARED_ZERO"
                    minutes = 0
                elif effort_text == "":
                    origin = "DEFAULTED"
                    governing = self.projects.governing(code, observed)
                    raw = governing[3] if governing else 0
                    minutes = min(EFFORT_CEILING, max(EFFORT_FLOOR, raw))
                else:
                    origin = "STATED"
                    factor = UNIT_FACTOR[unit] if has_unit else 60
                    minutes = min(EFFORT_CEILING, max(EFFORT_FLOOR, stated * factor))
                obligee_outcome, obligee_actor, _ = self.register.resolve(
                    fields.get("obligee", ""), due
                )
                obligee_status = {
                    "RESOLVED": "RESOLVED",
                    "AMBIGUOUS_IDENTITY": "AMBIGUOUS",
                    "UNKNOWN_PRINCIPAL": "UNKNOWN",
                }[obligee_outcome]
                self.assertions.append(
                    {
                        "assertion_id": record_id,
                        "commitment_key": key,
                        "obligor_surface": fields.get("obligor", ""),
                        "obligor_folded": fold(fields.get("obligor", "")),
                        "obligor_actor": actor,
                        "obligor_hops": hops,
                        "obligee_actor": obligee_actor or "",
                        "obligee_status": obligee_status,
                        "project_code": code,
                        "project_root": self.projects.root(code),
                        "due_at": fields.get("due_at", ""),
                        "due_min": due,
                        "commitment_day": commitment_day(due),
                        "effort_minutes": minutes,
                        "effort_origin": origin,
                        "cadence_ref": fields.get("cadence_ref", ""),
                        "observed_at": fields.get("observed_at", ""),
                        "observed_min": observed,
                        "source_class": source,
                        "feed_file": feed,
                    }
                )

    # -------------------------------------------------------------- winners
    def choose_winners(self):
        grouped = {}
        for row in self.assertions:
            grouped.setdefault(row["commitment_key"], []).append(row)
        self.groups = grouped
        self.commitments = {}
        for key in sorted(grouped):
            rows = sorted(grouped[key], key=self.assertion_order)
            winner = rows[-1]
            self.commitments[key] = {
                "commitment_key": key,
                "obligor_actor": winner["obligor_actor"],
                "obligee_actor": winner["obligee_actor"],
                "obligee_status": winner["obligee_status"],
                "project_code": winner["project_code"],
                "project_root": winner["project_root"],
                "commitment_day": winner["commitment_day"],
                "due_at": winner["due_at"],
                "due_min": winner["due_min"],
                "effort_minutes": winner["effort_minutes"],
                "effort_origin": winner["effort_origin"],
                "cadence_ref": winner["cadence_ref"],
                "source_class": winner["source_class"],
                "winning_assertion": winner["assertion_id"],
                "obligor_surface": winner["obligor_surface"],
            }

    def assertion_order(self, row):
        rank = CLASS_RANK.get(row["source_class"], -1)
        instant = row["observed_min"]
        if rank == 5:
            instant = -instant
        return (rank, instant, row["assertion_id"])

    def state_order(self, row):
        rank = CLASS_RANK.get(row["source_class"], -1)
        instant = row["observed_min"]
        if rank in (4, 5):
            instant = -instant
        return (rank, instant, row["state_id"])

    # --------------------------------------------------------------- states
    def read_states(self):
        self.state_rows = []
        for feed in self.feeds("states"):
            source = self.source_class(feed)
            retired = self.feed_retired.get(feed)
            for index, (fields, broken) in enumerate(
                load_records(os.path.join(self.data_dir, feed), "state")
            ):
                self.rows_ingested += 1
                record_id = fields.get("state_id", "")
                key = fields.get("commitment_key", "")
                missing = [name for name in STATE_FIELDS if name not in fields]
                observed = parse_instant(fields.get("observed_at", ""))
                to_state = fields.get("to_state", "")
                if broken or missing or observed is None or to_state not in STATES:
                    self.reject(feed, index, "state", record_id, key, "MALFORMED_ROW")
                    continue
                if retired is not None and observed >= retired:
                    self.reject(feed, index, "state", record_id, key, "FEED_RETIRED")
                    continue
                if not in_window(observed):
                    self.reject(feed, index, "state", record_id, key, "OUT_OF_WINDOW")
                    continue
                if key not in self.commitments:
                    self.reject(
                        feed, index, "state", record_id, key, "UNKNOWN_COMMITMENT"
                    )
                    continue
                self.state_rows.append(
                    {
                        "state_id": record_id,
                        "commitment_key": key,
                        "to_state": to_state,
                        "observed_at": fields.get("observed_at", ""),
                        "observed_min": observed,
                        "source_class": source,
                        "feed_file": feed,
                        "row_index": index,
                    }
                )

    def resolve_states(self):
        by_key = {}
        for row in self.state_rows:
            by_key.setdefault(row["commitment_key"], []).append(row)
        self.state_scope = by_key
        self.applied_states = 0
        for key, commitment in self.commitments.items():
            rows = sorted(by_key.get(key, ()), key=self.state_order)
            state = "OPEN"
            applied = 0
            governing = ""
            for row in rows:
                if (state, row["to_state"]) in LEGAL_TRANSITIONS:
                    state = row["to_state"]
                    applied += 1
                    governing = row["source_class"]
                else:
                    self.reject(
                        row["feed_file"],
                        row["row_index"],
                        "state",
                        row["state_id"],
                        key,
                        "ILLEGAL_TRANSITION",
                    )
            commitment["resolved_state"] = state
            commitment["assertions_seen"] = len(rows)
            commitment["assertions_applied"] = applied
            commitment["governing_class"] = governing
            self.applied_states += applied

    # ---------------------------------------------------------------- edges
    def read_edges(self):
        self.edges = []
        for feed in self.feeds("edges"):
            retired = self.feed_retired.get(feed)
            for index, (fields, broken) in enumerate(
                load_records(os.path.join(self.data_dir, feed), "edge")
            ):
                self.rows_ingested += 1
                record_id = fields.get("edge_id", "")
                dependent = fields.get("dependent_key", "")
                missing = [name for name in EDGE_FIELDS if name not in fields]
                asserted = parse_instant(fields.get("asserted_at", ""))
                if broken or missing or asserted is None:
                    self.reject(feed, index, "edge", record_id, dependent, "MALFORMED_ROW")
                    continue
                if retired is not None and asserted >= retired:
                    self.reject(feed, index, "edge", record_id, dependent, "FEED_RETIRED")
                    continue
                if not in_window(asserted):
                    self.reject(
                        feed, index, "edge", record_id, dependent, "OUT_OF_WINDOW"
                    )
                    continue
                self.edges.append(
                    {
                        "edge_id": record_id,
                        "dependent_key": dependent,
                        "blocker_key": fields.get("blocker_key", ""),
                        "asserted_at": fields.get("asserted_at", ""),
                        "asserted_min": asserted,
                    }
                )

    def classify_edges(self):
        self.live_edges = []
        self.dropped_edges = []
        for edge in self.edges:
            dependent = edge["dependent_key"]
            blocker = edge["blocker_key"]
            if dependent == blocker:
                edge["drop_reason"] = "EDGE_SELF"
                self.dropped_edges.append(edge)
                continue
            if dependent not in self.commitments or blocker not in self.commitments:
                edge["drop_reason"] = "EDGE_DANGLING"
                self.dropped_edges.append(edge)
                continue
            instant = edge["asserted_min"]
            left = self.register.resolve(
                self.commitments[dependent]["obligor_surface"], instant
            )
            right = self.register.resolve(
                self.commitments[blocker]["obligor_surface"], instant
            )
            if left[0] != "RESOLVED" or right[0] != "RESOLVED":
                edge["drop_reason"] = "EDGE_OUT_OF_SCOPE"
                self.dropped_edges.append(edge)
                continue
            edge["dependent_actor"] = left[1]
            edge["blocker_actor"] = right[1]
            self.live_edges.append(edge)

    # ------------------------------------------------------------- blocking
    def build_blocking(self):
        holding = {
            key
            for key, commitment in self.commitments.items()
            if commitment["resolved_state"] in ("OPEN", "DEFERRED")
        }
        self.holding = holding
        graph = {}
        for edge in self.live_edges:
            if edge["blocker_key"] in holding:
                graph.setdefault(edge["dependent_key"], set()).add(edge["blocker_key"])
        self.blocking = {key: sorted(value) for key, value in graph.items()}
        self.cycle_members = self._cycle_members()

    def _cycle_members(self):
        index = {}
        low = {}
        stack = []
        on_stack = set()
        counter = [0]
        members = set()
        for start in sorted(self.blocking):
            if start in index:
                continue
            work = [(start, iter(self.blocking.get(start, ())))]
            index[start] = low[start] = counter[0]
            counter[0] += 1
            stack.append(start)
            on_stack.add(start)
            while work:
                node, children = work[-1]
                advanced = False
                for child in children:
                    if child not in index:
                        index[child] = low[child] = counter[0]
                        counter[0] += 1
                        stack.append(child)
                        on_stack.add(child)
                        work.append((child, iter(self.blocking.get(child, ()))))
                        advanced = True
                        break
                    if child in on_stack:
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
                        item = stack.pop()
                        on_stack.discard(item)
                        component.append(item)
                        if item == node:
                            break
                    if len(component) > 1:
                        members.update(component)
                    elif node in self.blocking.get(node, ()):
                        members.add(node)
        return members

    def classify_commitments(self):
        self.dependency_blocked = {
            key
            for key in self.blocking
            if key not in self.cycle_members and self.blocking[key]
        }
        for key in sorted(self.commitments):
            commitment = self.commitments[key]
            state = commitment["resolved_state"]
            reason = ""
            if state == "SETTLED":
                klass = "SETTLED"
            elif state == "WITHDRAWN":
                klass = "WITHDRAWN"
            elif key in self.cycle_members:
                klass = "UNRESOLVABLE"
                reason = "CIRCULAR_DEPENDENCY"
            elif commitment["obligee_status"] == "AMBIGUOUS":
                klass = "UNRESOLVABLE"
                reason = "AMBIGUOUS_COUNTERPARTY"
            elif key in self.dependency_blocked:
                klass = "BLOCKED"
            elif state == "DEFERRED":
                klass = "DEFERRED"
            else:
                klass = "ACTIONABLE"
            commitment["commitment_class"] = klass
            commitment["unresolvable_reason"] = reason

    def build_closure(self):
        self.blocked_keys = sorted(
            key
            for key, commitment in self.commitments.items()
            if commitment["commitment_class"] == "BLOCKED"
        )
        self.closure_rows = []
        self.closure_stats = {}
        for key in self.blocked_keys:
            distance = {}
            frontier = [key]
            step = 0
            while frontier:
                step += 1
                following = []
                for node in frontier:
                    for child in self.blocking.get(node, ()):
                        if child not in distance:
                            distance[child] = step
                            following.append(child)
                frontier = following
            terminal = []
            for node in sorted(distance):
                is_terminal = not self.blocking.get(node)
                if is_terminal:
                    terminal.append(node)
                self.closure_rows.append(
                    {
                        "dependent_key": key,
                        "blocker_key": node,
                        "hop_distance": distance[node],
                        "blocker_state": self.commitments[node]["resolved_state"],
                        "terminal": "yes" if is_terminal else "no",
                    }
                )
            self.closure_stats[key] = {
                "reachable_blockers": len(distance),
                "frontier_count": len(terminal),
                "chain_depth": max(distance.values()) if distance else 0,
                "frontier_head": terminal[0] if terminal else "",
            }
        self.waits = {}
        for key in sorted(self.commitments):
            self._wait(key, set())

    def _wait(self, key, guard):
        if key in self.waits:
            return self.waits[key]
        children = self.blocking.get(key, ())
        if key not in self.dependency_blocked or not children or key in guard:
            self.waits[key] = 0
            return 0
        guard = guard | {key}
        value = 1 + max(self._wait(child, guard) for child in children)
        self.waits[key] = value
        return value

    # ------------------------------------------------------------- cadences
    def read_cadences(self):
        governing = {}
        for fields in load_table(os.path.join(self.data_dir, "cadence_register.csv")):
            cadence = fields.get("cadence_id", "")
            if not cadence:
                continue
            try:
                revision = int(fields.get("revision", ""))
                period_days = int(fields.get("period_days", ""))
            except ValueError:
                continue
            anchor = parse_instant(fields.get("anchor_at", ""))
            if anchor is None:
                continue
            if cadence not in governing or revision > governing[cadence]["revision"]:
                governing[cadence] = {
                    "cadence_id": cadence,
                    "revision": revision,
                    "obligor": fields.get("obligor", ""),
                    "period_days": period_days,
                    "anchor": anchor,
                }
        self.cadences = governing
        for cadence in governing.values():
            length = cadence["period_days"] * 1440
            count = 0
            if length > 0:
                while cadence["anchor"] + count * length < WINDOW_END_M:
                    count += 1
            cadence["periods_elapsed"] = count
            outcome, actor, _ = self.register.resolve(
                cadence["obligor"], cadence["anchor"]
            )
            cadence["owner"] = actor if outcome == "RESOLVED" else None

    def read_waivers(self):
        pairs = set()
        for name in self.feeds("waivers"):
            for fields in load_table(os.path.join(self.data_dir, name)):
                cadence = fields.get("cadence_id", "")
                try:
                    period = int(fields.get("period_index", ""))
                except (ValueError, TypeError):
                    continue
                pairs.add((cadence, period))
        self.waiver_pairs = sorted(
            (cadence, period)
            for cadence, period in pairs
            if cadence in self.cadences
            and 0 <= period < self.cadences[cadence]["periods_elapsed"]
        )

    def settle_cadences(self):
        discharges = {}
        for commitment in self.commitments.values():
            if commitment["commitment_class"] != "SETTLED":
                continue
            cadence = commitment["cadence_ref"]
            if cadence in self.cadences:
                discharges.setdefault(cadence, []).append(commitment["due_min"])
        order = []
        for cadence, period in self.waiver_pairs:
            info = self.cadences[cadence]
            start = info["anchor"] + period * info["period_days"] * 1440
            order.append((start, cadence, period))
        order.sort()
        allowance = {}
        granted = set()
        self.waivers_granted = {}
        self.waivers_lapsed = {}
        for start, cadence, period in order:
            owner = self.cadences[cadence]["owner"]
            if owner is None:
                granted.add((cadence, period))
                continue
            used = allowance.get(owner, 0)
            if used < WAIVER_ALLOWANCE:
                allowance[owner] = used + 1
                granted.add((cadence, period))
                self.waivers_granted[owner] = self.waivers_granted.get(owner, 0) + 1
            else:
                self.waivers_lapsed[owner] = self.waivers_lapsed.get(owner, 0) + 1
        self.waiver_rows = []
        for cadence in sorted(self.cadences):
            info = self.cadences[cadence]
            length = info["period_days"] * 1440
            waived_periods = {
                period for name, period in self.waiver_pairs if name == cadence
            }
            due_list = discharges.get(cadence, ())
            debt = 0
            streak = 0
            max_streak = 0
            discharged_count = 0
            waived_count = 0
            for period in range(info["periods_elapsed"]):
                start = info["anchor"] + period * length
                end = min(start + length, WINDOW_END_M)
                if any(start <= due < end for due in due_list):
                    discharged_count += 1
                    streak = 0
                elif period in waived_periods and (cadence, period) in granted:
                    waived_count += 1
                else:
                    debt += 1
                    streak += 1
                    if streak > max_streak:
                        max_streak = streak
            info["periods_discharged"] = discharged_count
            info["periods_waived"] = waived_count
            info["debt"] = debt
            info["max_streak"] = max_streak
            for period in sorted(waived_periods):
                start = info["anchor"] + period * length
                end = min(start + length, WINDOW_END_M)
                if (cadence, period) not in granted:
                    effect = "LAPSED"
                elif any(start <= due < end for due in due_list):
                    effect = "INERT"
                else:
                    effect = "SUPPRESSED"
                self.waiver_rows.append(
                    {
                        "cadence_id": cadence,
                        "period_index": period,
                        "effect": effect,
                        "period_start": format_instant(start),
                    }
                )
        self.waiver_rows.sort(key=lambda row: (row["cadence_id"], row["period_index"]))
        self.actor_debt = {}
        for cadence in self.cadences.values():
            owner = cadence["owner"]
            if owner is None:
                continue
            self.actor_debt[owner] = self.actor_debt.get(owner, 0) + cadence["debt"]

    # ------------------------------------------------------------ allocation
    def allocate(self):
        budgets = {}
        for fields in load_table(os.path.join(self.data_dir, "attention_budget.csv")):
            try:
                minutes = int(fields.get("monthly_minutes", ""))
            except (ValueError, TypeError):
                continue
            budgets[(fields.get("actor_id", ""), fields.get("year_month", ""))] = minutes
        overrides = {}
        for fields in load_table(os.path.join(self.data_dir, "budget_overrides.psv")):
            try:
                minutes = int(fields.get("monthly_minutes", ""))
            except (ValueError, TypeError):
                continue
            overrides[(fields.get("actor_id", ""), fields.get("year_month", ""))] = minutes
        waived_by_actor = {}
        for cadence in self.cadences.values():
            owner = cadence["owner"]
            if owner is None:
                continue
            waived_by_actor[owner] = (
                waived_by_actor.get(owner, 0) + cadence["periods_waived"]
            )
        for commitment in self.commitments.values():
            commitment["allocated_minutes"] = 0
        open_classes = ("ACTIONABLE", "BLOCKED", "DEFERRED")
        groups = {}
        for key in sorted(self.commitments):
            commitment = self.commitments[key]
            if commitment["commitment_class"] not in open_classes:
                continue
            if commitment["effort_minutes"] <= 0:
                continue
            month = commitment["commitment_day"][:7]
            groups.setdefault((month, commitment["obligor_actor"]), []).append(key)
        wait_reserve = {}
        for key in self.blocked_keys:
            commitment = self.commitments[key]
            slot = (commitment["commitment_day"][:7], commitment["obligor_actor"])
            wait_reserve[slot] = wait_reserve.get(slot, 0) + self.waits.get(key, 0)
        self.month_rows = []
        self.allocation_rows = []
        self.allocations_starved = 0
        for slot in sorted(groups):
            month, actor = slot
            keys = groups[slot]
            if (actor, month) in overrides:
                source = "OVERRIDE"
                envelope = overrides[(actor, month)]
            elif (actor, month) in budgets:
                source = "REGISTERED"
                envelope = budgets[(actor, month)]
            else:
                source = "ABSENT"
                envelope = 0
            reserve = RESERVE_PER_WAIT * wait_reserve.get(slot, 0)
            reserve += RESERVE_PER_WAIVED * waived_by_actor.get(actor, 0)
            distributable = envelope - reserve
            if distributable < 0:
                distributable = 0
            items = [(key, self.commitments[key]["effort_minutes"]) for key in keys]
            demand = sum(weight for _, weight in items)
            if demand <= distributable:
                shares = {key: weight for key, weight in items}
            else:
                first = largest_remainder(items, distributable)
                survivors = [
                    (key, weight)
                    for key, weight in items
                    if first[key] >= ALLOCATION_FLOOR
                ]
                self.allocations_starved += len(items) - len(survivors)
                if survivors:
                    second = largest_remainder(survivors, distributable)
                    shares = {key: second.get(key, 0) for key, _ in items}
                else:
                    shares = {key: 0 for key, _ in items}
            allocated = 0
            for key in keys:
                self.commitments[key]["allocated_minutes"] = shares[key]
                allocated += shares[key]
                self.allocation_rows.append(
                    {
                        "year_month": month,
                        "obligor_actor": actor,
                        "commitment_key": key,
                        "demand_minutes": self.commitments[key]["effort_minutes"],
                        "allocated_minutes": shares[key],
                    }
                )
            self.month_rows.append(
                {
                    "year_month": month,
                    "obligor_actor": actor,
                    "budget_source": source,
                    "budget_minutes": envelope,
                    "reserve_minutes": reserve,
                    "demand_minutes": demand,
                    "allocated_minutes": allocated,
                    "open_count": len(keys),
                }
            )

    def escalate(self):
        self.escalations = []
        for key in sorted(self.commitments):
            commitment = self.commitments[key]
            if commitment["commitment_class"] not in ("ACTIONABLE", "BLOCKED"):
                continue
            share = commitment["allocated_minutes"]
            if share >= commitment["effort_minutes"]:
                continue
            debt = self.actor_debt.get(commitment["obligor_actor"], 0)
            if debt < ESCALATION_DEBT:
                continue
            depth = self.closure_stats.get(key, {}).get("chain_depth", 0)
            by_depth = depth >= ESCALATION_DEPTH
            by_month = commitment["commitment_day"][:7] == ESCALATION_MONTH
            if not by_depth and not by_month:
                continue
            trigger = "BOTH" if by_depth and by_month else ("DEPTH" if by_depth else "MONTH")
            self.escalations.append(
                {
                    "commitment_key": key,
                    "obligor_actor": commitment["obligor_actor"],
                    "commitment_class": commitment["commitment_class"],
                    "effort_minutes": commitment["effort_minutes"],
                    "allocated_minutes": share,
                    "shortfall_minutes": commitment["effort_minutes"] - share,
                    "principal_debt": debt,
                    "chain_depth": depth,
                    "trigger": trigger,
                }
            )
        self.escalations.sort(
            key=lambda row: (-row["shortfall_minutes"], row["commitment_key"])
        )

    # ------------------------------------------------------------------ run
    def compute(self):
        self.read_commitments()
        self.choose_winners()
        self.read_states()
        self.resolve_states()
        self.read_edges()
        self.classify_edges()
        self.build_blocking()
        self.classify_commitments()
        self.build_closure()
        self.read_cadences()
        self.read_waivers()
        self.settle_cadences()
        self.allocate()
        self.escalate()


# ------------------------------------------------------------------- writing


def json_line(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def json_document(obj):
    return json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=True)


class Writer(object):
    def __init__(self, directory):
        self.directory = directory
        self.names = []

    def write(self, name, text):
        with open(os.path.join(self.directory, name), "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        self.names.append(name)

    def write_bytes(self, name, payload):
        with open(os.path.join(self.directory, name), "wb") as handle:
            handle.write(payload)
        self.names.append(name)

    def delimited(self, name, delimiter, header, rows):
        lines = [delimiter.join(header)]
        for row in rows:
            lines.append(delimiter.join(str(row[field]) for field in header))
        self.write(name, "\n".join(lines) + "\n")

    def jsonl(self, name, rows):
        self.write(name, "".join(json_line(row) + "\n" for row in rows))

    def document(self, name, obj):
        self.write(name, json_document(obj) + "\n")


def canonical_sort(commitments):
    return sorted(
        commitments,
        key=lambda row: (
            row["commitment_day"],
            row["obligor_actor"],
            -row["effort_minutes"],
            row["commitment_key"],
        ),
    )


def emit(closure, writer, source_bytes):
    commitments = closure.commitments
    ledger = canonical_sort(commitments.values())
    open_classes = ("ACTIONABLE", "BLOCKED", "DEFERRED")

    writer.write_bytes("reconcile.py", source_bytes)

    writer.jsonl(
        "normalized_assertions.jsonl",
        [
            {
                "assertion_id": row["assertion_id"],
                "commitment_key": row["commitment_key"],
                "obligor_actor": row["obligor_actor"],
                "obligee_actor": row["obligee_actor"],
                "obligee_status": row["obligee_status"],
                "project_code": row["project_code"],
                "project_root": row["project_root"],
                "due_at": row["due_at"],
                "commitment_day": row["commitment_day"],
                "effort_minutes": row["effort_minutes"],
                "effort_origin": row["effort_origin"],
                "cadence_ref": row["cadence_ref"],
                "observed_at": row["observed_at"],
                "source_class": row["source_class"],
            }
            for row in sorted(closure.assertions, key=lambda r: r["assertion_id"])
        ],
    )

    writer.delimited(
        "rejects.csv",
        ",",
        ["feed_file", "row_index", "record_kind", "record_id", "commitment_key", "reason_code"],
        [
            {
                "feed_file": feed,
                "row_index": index,
                "record_kind": kind,
                "record_id": record_id,
                "commitment_key": key,
                "reason_code": reason,
            }
            for reason, feed, index, record_id, kind, key in sorted(
                (reason, feed, index, record_id, kind, key)
                for feed, index, kind, record_id, key, reason in closure.rejects
            )
        ],
    )

    surfaces = {}
    for row in closure.assertions:
        entry = surfaces.setdefault(
            row["obligor_folded"], {"actors": set(), "count": 0, "hops": 0}
        )
        entry["actors"].add(row["obligor_actor"])
        entry["count"] += 1
        entry["hops"] = max(entry["hops"], row["obligor_hops"])
    writer.jsonl(
        "alias_resolution.jsonl",
        [
            {
                "surface_folded": surface,
                "distinct_actors": sorted(surfaces[surface]["actors"]),
                "assertion_count": surfaces[surface]["count"],
                "max_hops": surfaces[surface]["hops"],
            }
            for surface in sorted(surfaces)
        ],
    )
    split_surfaces = sum(1 for entry in surfaces.values() if len(entry["actors"]) > 1)
    multi_hop = sum(1 for row in closure.assertions if row["obligor_hops"] >= 2)

    actor_commitments = {}
    for commitment in commitments.values():
        actor_commitments.setdefault(commitment["obligor_actor"], []).append(commitment)
    writer.delimited(
        "actor_roster.csv",
        ",",
        ["actor_id", "canonical_handle", "commitment_count", "open_effort_minutes", "waivers_granted", "waivers_lapsed"],
        [
            {
                "actor_id": actor,
                "canonical_handle": closure.register.actor_handle[actor],
                "commitment_count": len(actor_commitments.get(actor, ())),
                "open_effort_minutes": sum(
                    item["effort_minutes"]
                    for item in actor_commitments.get(actor, ())
                    if item["commitment_class"] in open_classes
                ),
                "waivers_granted": closure.waivers_granted.get(actor, 0),
                "waivers_lapsed": closure.waivers_lapsed.get(actor, 0),
            }
            for actor in sorted(closure.register.actor_handle)
        ],
    )

    code_assertions = {}
    for row in closure.assertions:
        code_assertions[row["project_code"]] = code_assertions.get(row["project_code"], 0) + 1
    code_allocated = {}
    for commitment in commitments.values():
        code_allocated[commitment["project_code"]] = code_allocated.get(
            commitment["project_code"], 0
        ) + commitment["allocated_minutes"]
    writer.delimited(
        "project_lineage.csv",
        ",",
        ["project_code", "project_root", "assertion_count", "allocated_minutes"],
        [
            {
                "project_code": code,
                "project_root": closure.projects.root(code),
                "assertion_count": code_assertions[code],
                "allocated_minutes": code_allocated.get(code, 0),
            }
            for code in sorted(code_assertions)
        ],
    )

    writer.delimited(
        "assertion_contests.csv",
        ",",
        ["commitment_key", "winning_assertion", "winning_class", "contender_count", "distinct_classes"],
        [
            {
                "commitment_key": key,
                "winning_assertion": commitments[key]["winning_assertion"],
                "winning_class": commitments[key]["source_class"],
                "contender_count": len(closure.groups[key]),
                "distinct_classes": len(set(row["source_class"] for row in closure.groups[key])),
            }
            for key in sorted(commitments)
        ],
    )

    writer.jsonl(
        "commitment_ledger.jsonl",
        [
            {
                "commitment_key": row["commitment_key"],
                "obligor_actor": row["obligor_actor"],
                "obligee_actor": row["obligee_actor"],
                "project_code": row["project_code"],
                "project_root": row["project_root"],
                "commitment_day": row["commitment_day"],
                "due_at": row["due_at"],
                "effort_minutes": row["effort_minutes"],
                "effort_origin": row["effort_origin"],
                "resolved_state": row["resolved_state"],
                "commitment_class": row["commitment_class"],
                "cadence_ref": row["cadence_ref"],
                "source_class": row["source_class"],
                "winning_assertion": row["winning_assertion"],
                "allocated_minutes": row["allocated_minutes"],
            }
            for row in ledger
        ],
    )

    writer.delimited(
        "state_resolution.csv",
        ",",
        ["commitment_key", "resolved_state", "assertions_seen", "assertions_applied", "governing_class"],
        [
            {
                "commitment_key": key,
                "resolved_state": commitments[key]["resolved_state"],
                "assertions_seen": commitments[key]["assertions_seen"],
                "assertions_applied": commitments[key]["assertions_applied"],
                "governing_class": commitments[key]["governing_class"],
            }
            for key in sorted(commitments)
        ],
    )

    blocked_set = set(closure.blocked_keys)
    writer.delimited(
        "live_edges.csv",
        ",",
        ["edge_id", "dependent_key", "blocker_key", "asserted_at", "dependent_actor", "blocker_actor", "dependent_blocked"],
        [
            {
                "edge_id": edge["edge_id"],
                "dependent_key": edge["dependent_key"],
                "blocker_key": edge["blocker_key"],
                "asserted_at": edge["asserted_at"],
                "dependent_actor": edge["dependent_actor"],
                "blocker_actor": edge["blocker_actor"],
                "dependent_blocked": "yes" if edge["dependent_key"] in blocked_set else "no",
            }
            for edge in sorted(
                closure.live_edges,
                key=lambda e: (e["dependent_key"], e["blocker_key"], e["edge_id"]),
            )
        ],
    )

    writer.delimited(
        "dropped_edges.csv",
        ",",
        ["edge_id", "dependent_key", "blocker_key", "asserted_at", "drop_reason"],
        [
            {
                "edge_id": edge["edge_id"],
                "dependent_key": edge["dependent_key"],
                "blocker_key": edge["blocker_key"],
                "asserted_at": edge["asserted_at"],
                "drop_reason": edge["drop_reason"],
            }
            for edge in sorted(
                closure.dropped_edges, key=lambda e: (e["drop_reason"], e["edge_id"])
            )
        ],
    )

    closure_rows = sorted(
        closure.closure_rows, key=lambda row: (row["dependent_key"], row["blocker_key"])
    )
    writer.jsonl("blocking_closure.jsonl", closure_rows)

    writer.delimited(
        "blocked_commitments.csv",
        ",",
        ["commitment_key", "reachable_blockers", "frontier_count", "chain_depth", "frontier_head", "allocated_minutes"],
        [
            {
                "commitment_key": key,
                "reachable_blockers": closure.closure_stats[key]["reachable_blockers"],
                "frontier_count": closure.closure_stats[key]["frontier_count"],
                "chain_depth": closure.closure_stats[key]["chain_depth"],
                "frontier_head": closure.closure_stats[key]["frontier_head"],
                "allocated_minutes": commitments[key]["allocated_minutes"],
            }
            for key in closure.blocked_keys
        ],
    )

    queue_header = ["commitment_key", "obligor_actor", "commitment_day", "effort_minutes", "project_root", "allocated_minutes"]
    writer.delimited(
        "actionable_queue.tsv",
        "\t",
        queue_header,
        [row for row in ledger if row["commitment_class"] == "ACTIONABLE"],
    )
    writer.delimited(
        "deferred_queue.psv",
        "|",
        queue_header,
        [row for row in ledger if row["commitment_class"] == "DEFERRED"],
    )
    writer.delimited(
        "withdrawn_register.csv",
        ",",
        ["commitment_key", "obligor_actor", "commitment_day", "effort_minutes", "source_class"],
        [row for row in ledger if row["commitment_class"] == "WITHDRAWN"],
    )

    writer.jsonl(
        "unresolvable.jsonl",
        [
            {
                "commitment_key": row["commitment_key"],
                "reason_code": row["unresolvable_reason"],
                "obligor_actor": row["obligor_actor"],
                "commitment_day": row["commitment_day"],
            }
            for row in sorted(
                (item for item in commitments.values() if item["commitment_class"] == "UNRESOLVABLE"),
                key=lambda item: (item["unresolvable_reason"], item["commitment_key"]),
            )
        ],
    )

    writer.delimited(
        "cadence_debt.csv",
        ",",
        ["cadence_id", "period_days", "periods_elapsed", "periods_discharged", "periods_waived", "debt", "max_streak"],
        [closure.cadences[cadence] for cadence in sorted(closure.cadences)],
    )

    writer.jsonl("waiver_trace.jsonl", closure.waiver_rows)

    writer.delimited(
        "attention_allocation.csv",
        ",",
        ["year_month", "obligor_actor", "commitment_key", "demand_minutes", "allocated_minutes"],
        sorted(
            closure.allocation_rows,
            key=lambda row: (row["year_month"], row["obligor_actor"], row["commitment_key"]),
        ),
    )

    writer.delimited(
        "month_load_index.csv",
        ",",
        ["year_month", "obligor_actor", "budget_source", "budget_minutes", "reserve_minutes", "demand_minutes", "allocated_minutes", "open_count"],
        sorted(closure.month_rows, key=lambda row: (row["year_month"], row["obligor_actor"])),
    )

    writer.delimited(
        "escalation_queue.csv",
        ",",
        ["commitment_key", "obligor_actor", "commitment_class", "effort_minutes", "allocated_minutes", "shortfall_minutes", "principal_debt", "chain_depth", "trigger"],
        closure.escalations,
    )

    def rollup(groups):
        out = {}
        for name in sorted(groups):
            rows = groups[name]
            value = {klass: 0 for klass in CLASSES}
            for row in rows:
                value[row["commitment_class"]] += 1
            value["commitment_count"] = len(rows)
            value["open_effort_minutes"] = sum(
                row["effort_minutes"] for row in rows if row["commitment_class"] in open_classes
            )
            value["allocated_minutes"] = sum(row["allocated_minutes"] for row in rows)
            out[name] = value
        return out

    root_groups = {}
    for commitment in commitments.values():
        root_groups.setdefault(commitment["project_root"], []).append(commitment)
    actor_rollup = rollup(actor_commitments)
    project_rollup = rollup(root_groups)
    writer.document("actor_rollup.json", actor_rollup)
    writer.document("project_rollup.json", project_rollup)

    contributing = {}
    for row in closure.assertions:
        contributing.setdefault(row["commitment_key"], []).append(row)
    writer.jsonl(
        "provenance_index.jsonl",
        [
            {
                "commitment_key": key,
                "winning_assertion": commitments[key]["winning_assertion"],
                "contributing_assertions": sorted(
                    row["assertion_id"] for row in contributing[key]
                ),
                "source_files": sorted(set(row["feed_file"] for row in contributing[key])),
                "state_assertions": sorted(
                    row["state_id"] for row in closure.state_scope.get(key, ())
                ),
            }
            for key in sorted(commitments)
        ],
    )

    reject_counts = {code: 0 for code in REASON_CODES}
    for record in closure.rejects:
        reject_counts[record[5]] += 1
    class_counts = {klass: 0 for klass in CLASSES}
    for commitment in commitments.values():
        class_counts[commitment["commitment_class"]] += 1
    rows_rejected = len(closure.rejects)
    rows_accepted = closure.rows_ingested - rows_rejected
    open_effort = sum(
        row["effort_minutes"]
        for row in commitments.values()
        if row["commitment_class"] in open_classes
    )
    allocated_total = sum(row["allocated_minutes"] for row in commitments.values())
    cadence_debt_total = sum(item["debt"] for item in closure.cadences.values())

    figures = [
        ("rows_ingested", closure.rows_ingested, True),
        ("rows_rejected", rows_rejected, True),
        ("rows_accepted", rows_accepted, False),
        ("commitments_admitted", len(commitments), True),
        ("class_actionable", class_counts["ACTIONABLE"], True),
        ("class_blocked", class_counts["BLOCKED"], True),
        ("class_deferred", class_counts["DEFERRED"], True),
        ("class_settled", class_counts["SETTLED"], True),
        ("class_unresolvable", class_counts["UNRESOLVABLE"], True),
        ("class_withdrawn", class_counts["WITHDRAWN"], True),
        ("reject_ambiguous_identity", reject_counts["AMBIGUOUS_IDENTITY"], False),
        ("reject_feed_retired", reject_counts["FEED_RETIRED"], False),
        ("reject_illegal_transition", reject_counts["ILLEGAL_TRANSITION"], False),
        ("reject_malformed_row", reject_counts["MALFORMED_ROW"], False),
        ("reject_nonpositive_effort", reject_counts["NONPOSITIVE_EFFORT"], False),
        ("reject_out_of_window", reject_counts["OUT_OF_WINDOW"], False),
        ("reject_unknown_commitment", reject_counts["UNKNOWN_COMMITMENT"], False),
        ("reject_unknown_principal", reject_counts["UNKNOWN_PRINCIPAL"], False),
        ("reject_unknown_project", reject_counts["UNKNOWN_PROJECT"], False),
        ("live_edges", len(closure.live_edges), True),
        ("dropped_edges", len(closure.dropped_edges), True),
        ("closure_pairs", len(closure_rows), True),
        ("blocked_commitments", len(closure.blocked_keys), True),
        ("open_effort_minutes", open_effort, True),
        ("allocated_minutes", allocated_total, True),
        ("escalated_commitments", len(closure.escalations), True),
        ("cadence_debt_total", cadence_debt_total, True),
    ]
    writer.delimited(
        "audit_totals.csv",
        ",",
        ["metric", "value"],
        [{"metric": name, "value": value} for name, value, _ in figures],
    )

    actor_open = sum(
        value["open_effort_minutes"] for value in actor_rollup.values()
    )
    project_open = sum(
        value["open_effort_minutes"] for value in project_rollup.values()
    )
    terminal_pairs = sum(1 for row in closure_rows if row["terminal"] == "yes")
    frontier_total = sum(
        closure.closure_stats[key]["frontier_count"] for key in closure.blocked_keys
    )
    residuals = {
        "I1_row_partition": rows_accepted
        - (
            len(closure.assertions)
            + closure.applied_states
            + len(closure.live_edges)
            + len(closure.dropped_edges)
        ),
        "I2_class_partition": len(commitments) - sum(class_counts.values()),
        "I3_actor_effort": actor_open - open_effort,
        "I4_project_effort": project_open - open_effort,
        "I5_closure_frontier": frontier_total - terminal_pairs,
    }

    lines = ["CALDERMOOR COMMITMENT CLOSURE"]
    for name, value, starred in figures:
        if starred:
            lines.append("%s %d" % (name, value))
    for name in IDENTITIES:
        lines.append("identity_%s %d" % (name, residuals[name]))
    writer.write("reconciliation.txt", "\n".join(lines) + "\n")

    writer.document(
        "validation_report.json",
        {
            "identities": residuals,
            "identities_checked": list(IDENTITIES),
            "all_residuals_zero": all(value == 0 for value in residuals.values()),
        },
    )

    tiebreaks = 0
    for first, second in zip(ledger, ledger[1:]):
        if (
            first["commitment_day"] == second["commitment_day"]
            and first["obligor_actor"] == second["obligor_actor"]
            and first["effort_minutes"] != second["effort_minutes"]
        ):
            tiebreaks += 1
    effects = {"SUPPRESSED": 0, "INERT": 0, "LAPSED": 0}
    for row in closure.waiver_rows:
        effects[row["effect"]] += 1
    writer.document(
        "run_manifest.json",
        {
            "day_boundary_offset_minutes": DAY_OFFSET_MINUTES,
            "effort_floor_minutes": EFFORT_FLOOR,
            "effort_ceiling_minutes": EFFORT_CEILING,
            "allocation_floor_minutes": ALLOCATION_FLOOR,
            "window_start": WINDOW_START,
            "window_end": WINDOW_END,
            "reason_codes": sorted(REASON_CODES),
            "commitment_classes": sorted(CLASSES),
            "retired_feeds": closure.retired_feeds,
            "split_surfaces": split_surfaces,
            "multi_hop_assertions": multi_hop,
            "order_tiebreaks_applied": tiebreaks,
            "edges_dropped_out_of_scope": sum(
                1 for edge in closure.dropped_edges if edge["drop_reason"] == "EDGE_OUT_OF_SCOPE"
            ),
            "waivers_suppressing": effects["SUPPRESSED"],
            "waivers_inert": effects["INERT"],
            "waivers_lapsed": effects["LAPSED"],
            "allocations_starved": closure.allocations_starved,
            "illegal_transitions": reject_counts["ILLEGAL_TRANSITION"],
        },
    )


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: reconcile.py DATA_DIR OUT_DIR\n")
        return 2
    data_dir = argv[1]
    out_dir = argv[2]
    sys.setrecursionlimit(max(sys.getrecursionlimit(), 20000))
    with open(os.path.abspath(__file__), "rb") as handle:
        source_bytes = handle.read()
    closure = Closure(data_dir)
    closure.compute()
    staging = tempfile.mkdtemp(prefix=".reconcile-stage-")
    try:
        writer = Writer(staging)
        emit(closure, writer, source_bytes)
        if not os.path.isdir(out_dir):
            os.makedirs(out_dir)
        for entry in sorted(os.listdir(out_dir)):
            target = os.path.join(out_dir, entry)
            if os.path.isdir(target) and not os.path.islink(target):
                shutil.rmtree(target)
            else:
                os.remove(target)
        for name in sorted(writer.names):
            shutil.copyfile(os.path.join(staging, name), os.path.join(out_dir, name))
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
