#!/usr/bin/env python3
"""Caldermoor commitment closure.

Reads one extract directory laid out to the Caldermoor record layouts and
writes the twenty-nine deliverables of the output contract into an output
directory.

    python3 reconcile.py DATA_DIR OUT_DIR
"""

import collections
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
DAY_BOUNDARY_OFFSET_MINUTES = 240
EFFORT_FLOOR = 15
EFFORT_CEILING = 480
ALLOCATION_FLOOR = 15
WAIVER_ALLOWANCE = 4
BLOCKED_RESERVE_MINUTES = 30
WAIVED_RESERVE_MINUTES = 15
ESCALATION_DEBT_THRESHOLD = 4
ESCALATION_DEPTH_THRESHOLD = 2
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

IDENTITIES = [
    "I1_row_partition",
    "I2_class_partition",
    "I3_actor_effort",
    "I4_project_effort",
    "I5_closure_frontier",
]

SOURCE_RANK = {
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
HOLDING_STATES = ("OPEN", "DEFERRED")

COMMITMENT_FIELDS = [
    "assertion_id",
    "commitment_key",
    "obligor",
    "obligee",
    "project_ref",
    "due_at",
    "effort",
    "effort_unit",
    "cadence_ref",
    "observed_at",
]
STATE_FIELDS = ["state_id", "commitment_key", "to_state", "observed_at"]
EDGE_FIELDS = ["edge_id", "dependent_key", "blocker_key", "asserted_at"]

FIXED_COMMITMENT = [
    ("assertion_id", 12),
    ("commitment_key", 12),
    ("obligor", 40),
    ("obligee", 40),
    ("project_ref", 10),
    ("due_at", 18),
    ("effort", 8),
    ("cadence_ref", 10),
    ("observed_at", 18),
]
FIXED_STATE = [
    ("state_id", 12),
    ("commitment_key", 12),
    ("to_state", 12),
    ("observed_at", 18),
]

INSTANT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}Z$")
INTEGER_RE = re.compile(r"^-?\d+$")
XML_ATTR_RE = re.compile(r'([A-Za-z_][\w.-]*)="([^"]*)"')
EPOCH = datetime.datetime(1970, 1, 1)

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

AUDIT_METRICS = [
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


# ------------------------------------------------------------------ helpers


def fold(surface):
    """The six step comparison fold of the identity register."""
    text = unicodedata.normalize("NFC", surface)
    text = text.strip()
    text = text.casefold()
    for ch in ".-_'":
        text = text.replace(ch, "")
    text = " ".join(text.split())
    return text.strip()


def parse_instant(text):
    if not INSTANT_RE.match(text):
        return None
    try:
        return datetime.datetime(
            int(text[0:4]),
            int(text[5:7]),
            int(text[8:10]),
            int(text[11:13]),
            int(text[14:16]),
        )
    except ValueError:
        return None


def fmt_instant(moment):
    return moment.strftime("%Y-%m-%dT%H:%MZ")


def commitment_day(moment):
    return (
        moment - datetime.timedelta(minutes=DAY_BOUNDARY_OFFSET_MINUTES)
    ).strftime("%Y-%m-%d")


# ------------------------------------------------------------------ parsers


def read_text(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def split_lines(text):
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def parse_delimited(text, sep):
    lines = split_lines(text)
    if not lines:
        return []
    header = lines[0].split(sep)
    records = []
    for index, line in enumerate(lines[1:]):
        fields = line.split(sep)
        record = dict(zip(header, fields))
        records.append((index, record, len(fields) != len(header)))
    return records


def json_scalar(value):
    """A JSON value as the text a delimited layout would have carried."""
    if isinstance(value, str):
        return value
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    return json.dumps(value)


def parse_jsonl(text):
    records = []
    for index, line in enumerate(split_lines(text)):
        try:
            obj = json.loads(line)
        except ValueError:
            records.append((index, {}, True))
            continue
        if not isinstance(obj, dict):
            records.append((index, {}, True))
            continue
        records.append(
            (index, {k: json_scalar(v) for k, v in obj.items()}, False)
        )
    return records


def parse_kv(text):
    records = []
    index = 0
    for block in text.split("\n\n"):
        lines = [line for line in block.split("\n") if line != ""]
        if not lines:
            continue
        record = {}
        malformed = False
        for line in lines:
            if line.endswith(":") and ": " not in line:
                record[line[:-1]] = ""
            elif ": " in line:
                name, value = line.split(": ", 1)
                record[name] = value
            else:
                malformed = True
        records.append((index, record, malformed))
        index += 1
    return records


def parse_rec(text):
    records = []
    for index, line in enumerate(split_lines(text)):
        record = {}
        malformed = False
        for segment in line.split(";"):
            if "=" not in segment:
                malformed = True
                continue
            name, value = segment.split("=", 1)
            record[name] = value
        records.append((index, record, malformed))
    return records


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


def parse_xml(text, element):
    records = []
    index = 0
    opening = "<" + element
    for line in split_lines(text):
        stripped = line.strip()
        if not stripped.startswith(opening):
            continue
        if stripped[len(opening) : len(opening) + 1] not in (" ", "/", ">"):
            continue  # the wrapping element is not a record
        record = {}
        for match in XML_ATTR_RE.finditer(stripped):
            record[match.group(1)] = unescape_xml(match.group(2))
        records.append((index, record, False))
        index += 1
    return records


def parse_fixed(text, spec):
    records = []
    for index, line in enumerate(split_lines(text)):
        record = {}
        position = 0
        for name, width in spec:
            record[name] = line[position : position + width].rstrip(" ")
            position += width
        records.append((index, record, False))
    return records


def load_feed(path, kind):
    text = read_text(path)
    name = os.path.basename(path)
    if name.endswith(".csv"):
        return parse_delimited(text, ",")
    if name.endswith(".tsv"):
        return parse_delimited(text, "\t")
    if name.endswith(".psv"):
        return parse_delimited(text, "|")
    if name.endswith(".jsonl"):
        return parse_jsonl(text)
    if name.endswith(".kv"):
        return parse_kv(text)
    if name.endswith(".rec"):
        return parse_rec(text)
    if name.endswith(".xml"):
        return parse_xml(text, {"commitment": "commitment", "state": "state", "edge": "edge"}[kind])
    if name.endswith(".fixed"):
        return parse_fixed(text, FIXED_COMMITMENT if kind == "commitment" else FIXED_STATE)
    raise ValueError("unknown layout: " + name)


def load_table(path, sep):
    """A reference table as a list of dicts keyed by its header."""
    return [record for _, record, _ in parse_delimited(read_text(path), sep)]


# -------------------------------------------------------------- identity


class Identities(object):
    def __init__(self, data_dir):
        self.lines = []
        desk = os.path.join(data_dir, "roster_desk.csv")
        mirror = os.path.join(data_dir, "roster_mirror.tsv")
        vault = os.path.join(data_dir, "roster_vault.jsonl")
        for record in load_table(desk, ","):
            self.lines.append(record)
        for record in load_table(mirror, "\t"):
            self.lines.append(record)
        for _, record, _ in parse_jsonl(read_text(vault)):
            self.lines.append(record)

        spellings = collections.defaultdict(collections.Counter)
        for record in self.lines:
            spellings[record["actor_id"]][record["canonical_handle"]] += 1
        self.actors = sorted(spellings)
        self.canonical_handle = {}
        for actor in self.actors:
            counts = spellings[actor]
            self.canonical_handle[actor] = sorted(
                counts.items(), key=lambda item: (-item[1], item[0])
            )[0][0]

        self.handle_to_actor = {}
        for actor in self.actors:
            for spelling in spellings[actor]:
                self.handle_to_actor[fold(spelling)] = actor

        self.assertions = collections.defaultdict(list)
        seen = set()
        for name in (
            "aliases_desk.csv",
            "aliases_import.jsonl",
            "aliases_mirror.tsv",
            "aliases_partner.psv",
            "aliases_vault.kv",
        ):
            path = os.path.join(data_dir, name)
            if not os.path.exists(path):
                continue
            text = read_text(path)
            if name.endswith(".csv"):
                records = parse_delimited(text, ",")
            elif name.endswith(".tsv"):
                records = parse_delimited(text, "\t")
            elif name.endswith(".psv"):
                records = parse_delimited(text, "|")
            elif name.endswith(".jsonl"):
                records = parse_jsonl(text)
            else:
                records = parse_kv(text)
            for _, record, _ in records:
                surface = fold(record.get("surface", ""))
                target = fold(record.get("target", ""))
                start = record.get("scope_start", "")
                end = record.get("scope_end", "")
                key = (surface, target, start, end)
                if key in seen:
                    continue
                seen.add(key)
                start_dt = parse_instant(start)
                end_dt = parse_instant(end)
                if start_dt is None or end_dt is None:
                    continue
                if start_dt >= end_dt:
                    continue  # an interval containing no instant holds nowhere
                self.assertions[surface].append((target, start_dt, end_dt))
        for value in self.assertions.values():
            value.sort(key=lambda item: (item[0], item[1], item[2]))
        self._cache = {}

    def resolve(self, surface, instant_text, instant_dt):
        """Returns (actor_or_None, outcome, hops)."""
        folded = fold(surface)
        key = (folded, instant_text)
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        distance = {folded: 0}
        frontier = [folded]
        while frontier:
            nxt = []
            for node in frontier:
                for target, start, end in self.assertions.get(node, ()):
                    if start <= instant_dt < end and target not in distance:
                        distance[target] = distance[node] + 1
                        nxt.append(target)
            frontier = nxt
        reached = {}
        for node, hops in distance.items():
            actor = self.handle_to_actor.get(node)
            if actor is None:
                continue
            if actor not in reached or hops < reached[actor]:
                reached[actor] = hops
        if len(reached) == 1:
            actor = next(iter(reached))
            result = (actor, "RESOLVED", reached[actor])
        elif len(reached) > 1:
            result = (None, "AMBIGUOUS_IDENTITY", 0)
        else:
            result = (None, "UNKNOWN_PRINCIPAL", 0)
        self._cache[key] = result
        return result


# --------------------------------------------------------------- projects


class Projects(object):
    def __init__(self, data_dir):
        self.revisions = collections.defaultdict(list)
        for record in load_table(os.path.join(data_dir, "project_registry.csv"), ","):
            self.revisions[record["project_code"]].append(record)
        self.codes = set(self.revisions)
        for code in self.revisions:
            self.revisions[code].sort(
                key=lambda r: (r["revised_at"], int(r["revision"]))
            )

        self.renames = collections.defaultdict(list)
        events = load_table(os.path.join(data_dir, "project_events.tsv"), "\t")
        for record in events:
            if record.get("event_type") != "RENAME":
                continue
            moment = parse_instant(record.get("effective_at", ""))
            if moment is None:
                continue
            self.renames[record["project_code"]].append(
                (moment, record["event_id"], record["payload"])
            )
        for value in self.renames.values():
            value.sort()

        self._root_cache = {}
        self._resolve_cache = {}

    def resolve(self, code, instant_dt):
        key = (code, instant_dt)
        hit = self._resolve_cache.get(key)
        if hit is not None:
            return hit
        current = code
        seen = {current}
        while True:
            applicable = [
                entry
                for entry in self.renames.get(current, ())
                if entry[0] <= instant_dt
            ]
            if not applicable:
                break
            nxt = applicable[-1][2]
            if nxt in seen:
                break
            seen.add(nxt)
            current = nxt
        self._resolve_cache[key] = current
        return current

    def latest(self, code):
        return self.revisions[code][-1]

    def governing(self, code, instant_dt):
        rows = self.revisions[code]
        chosen = None
        for row in rows:
            moment = parse_instant(row["revised_at"])
            if moment is not None and moment <= instant_dt:
                chosen = row
        if chosen is None:
            chosen = rows[0]
        return chosen

    def root(self, code):
        hit = self._root_cache.get(code)
        if hit is not None:
            return hit
        current = code
        seen = {current}
        while True:
            parent = self.latest(current)["parent_code"]
            if not parent or parent not in self.codes or parent in seen:
                break
            seen.add(parent)
            current = parent
        self._root_cache[code] = current
        return current


# ---------------------------------------------------------------- closure


def strongly_connected(nodes, successors):
    """Iterative Tarjan; yields components as lists."""
    index = {}
    low = {}
    on_stack = set()
    stack = []
    counter = [0]
    components = []
    for start in nodes:
        if start in index:
            continue
        work = [(start, 0)]
        while work:
            node, step = work[-1]
            if step == 0:
                index[node] = low[node] = counter[0]
                counter[0] += 1
                stack.append(node)
                on_stack.add(node)
            children = successors.get(node, ())
            recursed = False
            while step < len(children):
                child = children[step]
                step += 1
                if child not in index:
                    work[-1] = (node, step)
                    work.append((child, 0))
                    recursed = True
                    break
                if child in on_stack:
                    low[node] = min(low[node], index[child])
            if recursed:
                continue
            work[-1] = (node, step)
            if step >= len(children):
                work.pop()
                if low[node] == index[node]:
                    component = []
                    while True:
                        member = stack.pop()
                        on_stack.discard(member)
                        component.append(member)
                        if member == node:
                            break
                    components.append(component)
                if work:
                    parent = work[-1][0]
                    low[parent] = min(low[parent], low[node])
    return components


# ------------------------------------------------------------- allocation


def largest_remainder(items, cap):
    """items is a list of (key, weight); returns {key: share}."""
    total = sum(weight for _, weight in items)
    if total <= cap:
        return {key: weight for key, weight in items}
    shares = {}
    remainders = []
    for key, weight in items:
        numerator = cap * weight
        whole = numerator // total
        shares[key] = whole
        remainders.append((numerator - whole * total, key))
    spare = cap - sum(shares.values())
    remainders.sort(key=lambda item: (-item[0], item[1]))
    for position in range(spare):
        shares[remainders[position][1]] += 1
    return shares


def distribute(items, cap):
    """Returns (shares, starved_keys) under protocol section 9."""
    total = sum(weight for _, weight in items)
    first = largest_remainder(items, cap)
    if total <= cap:
        return first, []
    starved = sorted(key for key, share in first.items() if share < ALLOCATION_FLOOR)
    if not starved:
        return first, []
    survivors = [
        (key, weight) for key, weight in items if first[key] >= ALLOCATION_FLOOR
    ]
    shares = {key: 0 for key, _ in items}
    if survivors:
        shares.update(largest_remainder(survivors, cap))
    return shares, starved


# ------------------------------------------------------------------ output


def csv_bytes(header, rows, sep=","):
    out = [sep.join(header)]
    for row in rows:
        out.append(sep.join("" if value is None else str(value) for value in row))
    return ("\n".join(out) + "\n").encode("utf-8")


def jsonl_bytes(objects):
    out = []
    for obj in objects:
        out.append(json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
    if not out:
        return b""
    return ("\n".join(out) + "\n").encode("utf-8")


def json_bytes(obj):
    return (
        json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    ).encode("utf-8")


def text_bytes(lines):
    return ("\n".join(lines) + "\n").encode("utf-8")


# -------------------------------------------------------------------- main


def build(data_dir):
    identities = Identities(data_dir)
    projects = Projects(data_dir)

    window_start = parse_instant(WINDOW_START)
    window_end = parse_instant(WINDOW_END)

    # ---- feed manifest ---------------------------------------------------
    manifest = collections.defaultdict(list)
    for record in load_table(os.path.join(data_dir, "feed_manifest.csv"), ","):
        manifest[record["feed_file"]].append(record)
    governing_feed = {}
    for name, records in manifest.items():
        governing_feed[name] = max(records, key=lambda r: int(r["revision"]))
    retired_at = {}
    for name, record in governing_feed.items():
        moment = parse_instant(record["retired_at"]) if record["retired_at"] else None
        retired_at[name] = moment
    retired_feeds = sorted(name for name, moment in retired_at.items() if moment)

    def source_class(name):
        record = governing_feed.get(name)
        if record is not None:
            return record["source_class"]
        return name.split("_")[1]

    # ---- ingest ----------------------------------------------------------
    names = sorted(os.listdir(data_dir))
    commitment_files = [n for n in names if n.startswith("commitments_")]
    state_files = [n for n in names if n.startswith("states_")]
    edge_files = [n for n in names if n.startswith("edges_")]

    rejects = []  # (reason, feed_file, row_index, record_id, kind, commitment_key)
    rows_ingested = 0

    def reject(reason, feed, row_index, kind, record_id, key):
        rejects.append((reason, feed, row_index, record_id, kind, key))

    # ---- commitment assertions ------------------------------------------
    assertions = []
    for feed in commitment_files:
        cls = source_class(feed)
        unitless = feed.endswith(".fixed") or feed.endswith(".rec")
        retire = retired_at.get(feed)
        records = load_feed(os.path.join(data_dir, feed), "commitment")
        rows_ingested += len(records)
        for row_index, record, malformed in records:
            values = {name: record.get(name, "") for name in COMMITMENT_FIELDS}
            key = values["commitment_key"]
            record_id = values["assertion_id"]
            due_dt = parse_instant(values["due_at"])
            observed_dt = parse_instant(values["observed_at"])
            effort_text = values["effort"]
            bad = malformed or due_dt is None or observed_dt is None
            effort_minutes = None
            origin = None
            if not bad:
                if effort_text == "":
                    origin = "DEFAULTED"
                elif effort_text == "null":
                    origin = "DECLARED_ZERO"
                    effort_minutes = 0
                elif INTEGER_RE.match(effort_text):
                    amount = int(effort_text)
                    if amount > 0:
                        origin = "STATED"
                        if unitless:
                            effort_minutes = amount * UNITLESS_FACTOR
                        else:
                            factor = EFFORT_UNITS.get(values["effort_unit"])
                            if factor is None:
                                bad = True
                            else:
                                effort_minutes = amount * factor
                    else:
                        origin = "NONPOSITIVE"
                else:
                    bad = True
            if bad:
                reject("MALFORMED_ROW", feed, row_index, "commitment", record_id, key)
                continue
            if retire is not None and observed_dt >= retire:
                reject("FEED_RETIRED", feed, row_index, "commitment", record_id, key)
                continue
            if not (window_start <= due_dt < window_end):
                reject("OUT_OF_WINDOW", feed, row_index, "commitment", record_id, key)
                continue
            obligor_actor, obligor_outcome, hops = identities.resolve(
                values["obligor"], values["observed_at"], observed_dt
            )
            if obligor_outcome != "RESOLVED":
                reject(obligor_outcome, feed, row_index, "commitment", record_id, key)
                continue
            project_code = projects.resolve(values["project_ref"], observed_dt)
            if project_code not in projects.codes:
                reject("UNKNOWN_PROJECT", feed, row_index, "commitment", record_id, key)
                continue
            if origin == "NONPOSITIVE":
                reject(
                    "NONPOSITIVE_EFFORT", feed, row_index, "commitment", record_id, key
                )
                continue
            if origin == "DEFAULTED":
                effort_minutes = int(
                    projects.governing(project_code, observed_dt)["default_effort"]
                )
            if effort_minutes > 0:
                effort_minutes = min(
                    EFFORT_CEILING, max(EFFORT_FLOOR, effort_minutes)
                )
            obligee_actor, obligee_outcome, _ = identities.resolve(
                values["obligee"], values["due_at"], due_dt
            )
            obligee_status = {
                "RESOLVED": "RESOLVED",
                "AMBIGUOUS_IDENTITY": "AMBIGUOUS",
                "UNKNOWN_PRINCIPAL": "UNKNOWN",
            }[obligee_outcome]
            assertions.append(
                {
                    "assertion_id": record_id,
                    "commitment_key": key,
                    "obligor_actor": obligor_actor,
                    "obligor": values["obligor"],
                    "obligor_surface": fold(values["obligor"]),
                    "obligor_hops": hops,
                    "obligee_actor": obligee_actor or "",
                    "obligee_status": obligee_status,
                    "project_code": project_code,
                    "project_root": projects.root(project_code),
                    "due_at": values["due_at"],
                    "due_dt": due_dt,
                    "commitment_day": commitment_day(due_dt),
                    "effort_minutes": effort_minutes,
                    "effort_origin": origin,
                    "cadence_ref": values["cadence_ref"],
                    "observed_at": values["observed_at"],
                    "observed_dt": observed_dt,
                    "source_class": cls,
                    "feed_file": feed,
                }
            )

    admitted_keys = set(item["commitment_key"] for item in assertions)

    # ---- winning assertions ---------------------------------------------
    by_key = collections.defaultdict(list)
    for item in assertions:
        by_key[item["commitment_key"]].append(item)

    def commitment_order(item):
        rank = SOURCE_RANK[item["source_class"]]
        minutes = int((item["observed_dt"] - EPOCH).total_seconds() // 60)
        if item["source_class"] == "desk":
            minutes = -minutes
        return (rank, minutes, item["assertion_id"])

    winners = {}
    for key, items in by_key.items():
        winners[key] = sorted(items, key=commitment_order)[-1]

    # ---- state assertions ------------------------------------------------
    state_rows = []
    for feed in state_files:
        cls = source_class(feed)
        retire = retired_at.get(feed)
        records = load_feed(os.path.join(data_dir, feed), "state")
        rows_ingested += len(records)
        for row_index, record, malformed in records:
            values = {name: record.get(name, "") for name in STATE_FIELDS}
            key = values["commitment_key"]
            record_id = values["state_id"]
            observed_dt = parse_instant(values["observed_at"])
            if malformed or observed_dt is None or values["to_state"] not in STATES:
                reject("MALFORMED_ROW", feed, row_index, "state", record_id, key)
                continue
            if retire is not None and observed_dt >= retire:
                reject("FEED_RETIRED", feed, row_index, "state", record_id, key)
                continue
            if not (window_start <= observed_dt < window_end):
                reject("OUT_OF_WINDOW", feed, row_index, "state", record_id, key)
                continue
            if key not in admitted_keys:
                reject("UNKNOWN_COMMITMENT", feed, row_index, "state", record_id, key)
                continue
            state_rows.append(
                {
                    "state_id": record_id,
                    "commitment_key": key,
                    "to_state": values["to_state"],
                    "observed_at": values["observed_at"],
                    "observed_dt": observed_dt,
                    "source_class": cls,
                    "feed_file": feed,
                    "row_index": row_index,
                }
            )

    def state_order(item):
        rank = SOURCE_RANK[item["source_class"]]
        minutes = int((item["observed_dt"] - EPOCH).total_seconds() // 60)
        if item["source_class"] in ("desk", "bridge"):
            minutes = -minutes
        return (rank, minutes, item["state_id"])

    states_by_key = collections.defaultdict(list)
    for item in state_rows:
        states_by_key[item["commitment_key"]].append(item)

    resolved_state = {}
    governing_class = {}
    applied_count = {}
    seen_count = {}
    applied_total = 0
    for key in admitted_keys:
        rows = sorted(states_by_key.get(key, []), key=state_order)
        held = "OPEN"
        applied = 0
        last_class = ""
        for item in rows:
            if (held, item["to_state"]) in ALLOWED_TRANSITIONS:
                held = item["to_state"]
                applied += 1
                last_class = item["source_class"]
            else:
                reject(
                    "ILLEGAL_TRANSITION",
                    item["feed_file"],
                    item["row_index"],
                    "state",
                    item["state_id"],
                    key,
                )
        resolved_state[key] = held
        governing_class[key] = last_class
        applied_count[key] = applied
        seen_count[key] = len(rows)
        applied_total += applied

    # ---- edge rows --------------------------------------------------------
    accepted_edges = []
    for feed in edge_files:
        retire = retired_at.get(feed)
        records = load_feed(os.path.join(data_dir, feed), "edge")
        rows_ingested += len(records)
        for row_index, record, malformed in records:
            values = {name: record.get(name, "") for name in EDGE_FIELDS}
            record_id = values["edge_id"]
            key = values["dependent_key"]
            asserted_dt = parse_instant(values["asserted_at"])
            if malformed or asserted_dt is None:
                reject("MALFORMED_ROW", feed, row_index, "edge", record_id, key)
                continue
            if retire is not None and asserted_dt >= retire:
                reject("FEED_RETIRED", feed, row_index, "edge", record_id, key)
                continue
            if not (window_start <= asserted_dt < window_end):
                reject("OUT_OF_WINDOW", feed, row_index, "edge", record_id, key)
                continue
            accepted_edges.append(
                {
                    "edge_id": record_id,
                    "dependent_key": key,
                    "blocker_key": values["blocker_key"],
                    "asserted_at": values["asserted_at"],
                    "asserted_dt": asserted_dt,
                }
            )

    live_edges = []
    dropped_edges = []
    for edge in accepted_edges:
        dependent = edge["dependent_key"]
        blocker = edge["blocker_key"]
        if dependent == blocker:
            edge["drop_reason"] = "EDGE_SELF"
            dropped_edges.append(edge)
            continue
        if dependent not in admitted_keys or blocker not in admitted_keys:
            edge["drop_reason"] = "EDGE_DANGLING"
            dropped_edges.append(edge)
            continue
        dependent_actor, dependent_outcome, _ = identities.resolve(
            winners[dependent]["obligor"], edge["asserted_at"], edge["asserted_dt"]
        )
        blocker_actor, blocker_outcome, _ = identities.resolve(
            winners[blocker]["obligor"], edge["asserted_at"], edge["asserted_dt"]
        )
        if dependent_outcome != "RESOLVED" or blocker_outcome != "RESOLVED":
            edge["drop_reason"] = "EDGE_OUT_OF_SCOPE"
            dropped_edges.append(edge)
            continue
        edge["dependent_actor"] = dependent_actor
        edge["blocker_actor"] = blocker_actor
        live_edges.append(edge)

    # ---- blocking graph ---------------------------------------------------
    successors = collections.defaultdict(set)
    for edge in live_edges:
        if resolved_state[edge["blocker_key"]] in HOLDING_STATES:
            successors[edge["dependent_key"]].add(edge["blocker_key"])
    ordered_keys = sorted(admitted_keys)
    succ = {node: sorted(targets) for node, targets in successors.items()}
    components = strongly_connected(ordered_keys, succ)
    on_cycle = set()
    for component in components:
        if len(component) > 1:
            on_cycle.update(component)
        else:
            node = component[0]
            if node in succ.get(node, ()):
                on_cycle.add(node)

    blocked = set()
    for node in ordered_keys:
        if node in on_cycle:
            continue
        if succ.get(node):
            blocked.add(node)

    # ---- classes ----------------------------------------------------------
    commitment_class = {}
    unresolvable_reason = {}
    for key in ordered_keys:
        state = resolved_state[key]
        if state == "SETTLED":
            commitment_class[key] = "SETTLED"
        elif state == "WITHDRAWN":
            commitment_class[key] = "WITHDRAWN"
        elif key in on_cycle:
            commitment_class[key] = "UNRESOLVABLE"
            unresolvable_reason[key] = "CIRCULAR_DEPENDENCY"
        elif winners[key]["obligee_status"] == "AMBIGUOUS":
            commitment_class[key] = "UNRESOLVABLE"
            unresolvable_reason[key] = "AMBIGUOUS_COUNTERPARTY"
        elif key in blocked:
            commitment_class[key] = "BLOCKED"
        elif state == "DEFERRED":
            commitment_class[key] = "DEFERRED"
        else:
            commitment_class[key] = "ACTIONABLE"

    OPEN_CLASSES = ("ACTIONABLE", "BLOCKED", "DEFERRED")

    # ---- closure ----------------------------------------------------------
    closure_rows = []
    closure_stats = {}
    for key in sorted(blocked):
        distance = {}
        frontier = [key]
        hop = 0
        while frontier:
            hop += 1
            nxt = []
            for node in frontier:
                for child in succ.get(node, ()):
                    if child not in distance and child != key:
                        distance[child] = hop
                        nxt.append(child)
            frontier = nxt
        terminal_keys = []
        for node in sorted(distance):
            is_terminal = not succ.get(node)
            if is_terminal:
                terminal_keys.append(node)
            closure_rows.append(
                {
                    "dependent_key": key,
                    "blocker_key": node,
                    "hop_distance": distance[node],
                    "blocker_state": resolved_state[node],
                    "terminal": "yes" if is_terminal else "no",
                }
            )
        closure_stats[key] = {
            "reachable_blockers": len(distance),
            "frontier_count": len(terminal_keys),
            "chain_depth": max(distance.values()) if distance else 0,
            "frontier_head": terminal_keys[0] if terminal_keys else "",
        }
    closure_rows.sort(key=lambda row: (row["dependent_key"], row["blocker_key"]))

    # ---- cadences ---------------------------------------------------------
    cadence_revisions = collections.defaultdict(list)
    for record in load_table(os.path.join(data_dir, "cadence_register.csv"), ","):
        cadence_revisions[record["cadence_id"]].append(record)
    cadences = {}
    for cadence_id, records in cadence_revisions.items():
        cadences[cadence_id] = max(records, key=lambda r: int(r["revision"]))

    cadence_owner = {}
    cadence_periods = {}
    for cadence_id in sorted(cadences):
        record = cadences[cadence_id]
        anchor = parse_instant(record["anchor_at"])
        period_days = int(record["period_days"])
        actor, outcome, _ = identities.resolve(
            record["obligor"], record["anchor_at"], anchor
        )
        cadence_owner[cadence_id] = actor if outcome == "RESOLVED" else None
        periods = []
        index = 0
        while True:
            start = anchor + datetime.timedelta(days=period_days * index)
            if start >= window_end:
                break
            end = anchor + datetime.timedelta(days=period_days * (index + 1))
            if end > window_end:
                end = window_end
            periods.append((index, start, end))
            index += 1
        cadence_periods[cadence_id] = periods

    discharges = collections.defaultdict(list)
    for key in ordered_keys:
        if commitment_class[key] != "SETTLED":
            continue
        winner = winners[key]
        if winner["cadence_ref"]:
            discharges[winner["cadence_ref"]].append(winner["due_dt"])

    discharged_periods = {}
    for cadence_id, periods in cadence_periods.items():
        moments = discharges.get(cadence_id, ())
        discharged = set()
        for index, start, end in periods:
            for moment in moments:
                if start <= moment < end:
                    discharged.add(index)
                    break
        discharged_periods[cadence_id] = discharged

    waiver_pairs = set()
    for name, sep in (("waivers_desk.csv", ","), ("waivers_partner.psv", "|")):
        path = os.path.join(data_dir, name)
        if not os.path.exists(path):
            continue
        for record in load_table(path, sep):
            cadence_id = record["cadence_id"]
            if cadence_id not in cadences:
                continue
            try:
                index = int(record["period_index"])
            except ValueError:
                continue
            if index < 0 or index >= len(cadence_periods[cadence_id]):
                continue
            waiver_pairs.add((cadence_id, index))

    waivers_by_owner = collections.defaultdict(list)
    for cadence_id, index in waiver_pairs:
        start = cadence_periods[cadence_id][index][1]
        waivers_by_owner[cadence_owner[cadence_id]].append((start, cadence_id, index))

    granted = set()
    lapsed = set()
    actor_waivers_granted = collections.Counter()
    actor_waivers_lapsed = collections.Counter()
    for owner in sorted(waivers_by_owner, key=lambda a: (a is not None, a or "")):
        entries = sorted(waivers_by_owner[owner])
        for position, (_, cadence_id, index) in enumerate(entries):
            if owner is None or position < WAIVER_ALLOWANCE:
                granted.add((cadence_id, index))
                if owner is not None:
                    actor_waivers_granted[owner] += 1
            else:
                lapsed.add((cadence_id, index))
                actor_waivers_lapsed[owner] += 1

    cadence_debt = {}
    waiver_trace = []
    for cadence_id in sorted(cadences):
        periods = cadence_periods[cadence_id]
        discharged = discharged_periods[cadence_id]
        debt = 0
        streak = 0
        max_streak = 0
        waived = 0
        for index, start, _ in periods:
            if index in discharged:
                streak = 0
            elif (cadence_id, index) in granted:
                waived += 1
            else:
                debt += 1
                streak += 1
                if streak > max_streak:
                    max_streak = streak
        cadence_debt[cadence_id] = {
            "period_days": int(cadences[cadence_id]["period_days"]),
            "periods_elapsed": len(periods),
            "periods_discharged": len(discharged),
            "periods_waived": waived,
            "debt": debt,
            "max_streak": max_streak,
        }
        for index, start, _ in periods:
            if (cadence_id, index) in lapsed:
                effect = "LAPSED"
            elif (cadence_id, index) in granted:
                effect = "INERT" if index in discharged else "SUPPRESSED"
            else:
                continue
            waiver_trace.append(
                {
                    "cadence_id": cadence_id,
                    "period_index": index,
                    "effect": effect,
                    "period_start": fmt_instant(start),
                }
            )
    waiver_trace.sort(key=lambda row: (row["cadence_id"], row["period_index"]))

    actor_debt = collections.Counter()
    actor_waived_periods = collections.Counter()
    for cadence_id, owner in cadence_owner.items():
        if owner is None:
            continue
        actor_debt[owner] += cadence_debt[cadence_id]["debt"]
        actor_waived_periods[owner] += cadence_debt[cadence_id]["periods_waived"]

    # ---- attention envelopes ---------------------------------------------
    budget = {}
    for record in load_table(os.path.join(data_dir, "attention_budget.csv"), ","):
        budget[(record["actor_id"], record["year_month"])] = int(
            record["monthly_minutes"]
        )
    override = {}
    for record in load_table(os.path.join(data_dir, "budget_overrides.psv"), "|"):
        override[(record["actor_id"], record["year_month"])] = int(
            record["monthly_minutes"]
        )

    blocked_in_month = collections.Counter()
    for key in blocked:
        blocked_in_month[
            (winners[key]["obligor_actor"], winners[key]["commitment_day"][:7])
        ] += 1

    groups = collections.defaultdict(list)
    for key in ordered_keys:
        if commitment_class[key] not in OPEN_CLASSES:
            continue
        winner = winners[key]
        if winner["effort_minutes"] <= 0:
            continue
        groups[(winner["obligor_actor"], winner["commitment_day"][:7])].append(key)

    allocated = {key: 0 for key in ordered_keys}
    month_load = []
    allocations_starved = 0
    for actor, month in sorted(groups):
        keys = sorted(groups[(actor, month)])
        items = [(key, winners[key]["effort_minutes"]) for key in keys]
        pair = (actor, month)
        if pair in override:
            envelope = override[pair]
            budget_source = "OVERRIDE"
        elif pair in budget:
            envelope = budget[pair]
            budget_source = "REGISTERED"
        else:
            envelope = 0
            budget_source = "ABSENT"
        reserve = (
            BLOCKED_RESERVE_MINUTES * blocked_in_month.get(pair, 0)
            + WAIVED_RESERVE_MINUTES * actor_waived_periods.get(actor, 0)
        )
        distributable = max(0, envelope - reserve)
        shares, starved = distribute(items, distributable)
        allocations_starved += len(starved)
        for key in keys:
            allocated[key] = shares[key]
        month_load.append(
            {
                "year_month": month,
                "obligor_actor": actor,
                "budget_source": budget_source,
                "budget_minutes": envelope,
                "reserve_minutes": reserve,
                "demand_minutes": sum(weight for _, weight in items),
                "allocated_minutes": sum(shares[key] for key in keys),
                "open_count": len(keys),
            }
        )

    # ---- ledger -----------------------------------------------------------
    def canonical_sort_key(key):
        winner = winners[key]
        return (
            winner["commitment_day"],
            winner["obligor_actor"],
            -winner["effort_minutes"],
            key,
        )

    ledger_keys = sorted(ordered_keys, key=canonical_sort_key)

    ledger = []
    for key in ledger_keys:
        winner = winners[key]
        ledger.append(
            {
                "commitment_key": key,
                "obligor_actor": winner["obligor_actor"],
                "obligee_actor": winner["obligee_actor"],
                "project_code": winner["project_code"],
                "project_root": winner["project_root"],
                "commitment_day": winner["commitment_day"],
                "due_at": winner["due_at"],
                "effort_minutes": winner["effort_minutes"],
                "effort_origin": winner["effort_origin"],
                "resolved_state": resolved_state[key],
                "commitment_class": commitment_class[key],
                "cadence_ref": winner["cadence_ref"],
                "source_class": winner["source_class"],
                "winning_assertion": winner["assertion_id"],
                "allocated_minutes": allocated[key],
            }
        )

    order_tiebreaks = 0
    for first, second in zip(ledger, ledger[1:]):
        if (
            first["commitment_day"] == second["commitment_day"]
            and first["obligor_actor"] == second["obligor_actor"]
            and first["effort_minutes"] != second["effort_minutes"]
        ):
            order_tiebreaks += 1

    # ---- escalation -------------------------------------------------------
    escalations = []
    for key in ledger_keys:
        klass = commitment_class[key]
        if klass not in ("ACTIONABLE", "BLOCKED"):
            continue
        winner = winners[key]
        effort = winner["effort_minutes"]
        share = allocated[key]
        if not share < effort:
            continue
        debt = actor_debt.get(winner["obligor_actor"], 0)
        if debt < ESCALATION_DEBT_THRESHOLD:
            continue
        depth = closure_stats[key]["chain_depth"] if key in closure_stats else 0
        depth_holds = depth >= ESCALATION_DEPTH_THRESHOLD
        month_holds = winner["commitment_day"][:7] == ESCALATION_MONTH
        if not (depth_holds or month_holds):
            continue
        if depth_holds and month_holds:
            trigger = "BOTH"
        elif depth_holds:
            trigger = "DEPTH"
        else:
            trigger = "MONTH"
        escalations.append(
            {
                "commitment_key": key,
                "obligor_actor": winner["obligor_actor"],
                "commitment_class": klass,
                "effort_minutes": effort,
                "allocated_minutes": share,
                "shortfall_minutes": effort - share,
                "principal_debt": debt,
                "chain_depth": depth,
                "trigger": trigger,
            }
        )
    escalations.sort(key=lambda row: (-row["shortfall_minutes"], row["commitment_key"]))

    # ---- rollups ----------------------------------------------------------
    def blank_rollup():
        entry = {name: 0 for name in CLASSES}
        entry["commitment_count"] = 0
        entry["open_effort_minutes"] = 0
        entry["allocated_minutes"] = 0
        return entry

    actor_rollup = {}
    project_rollup = {}
    for key in ledger_keys:
        winner = winners[key]
        klass = commitment_class[key]
        effort = winner["effort_minutes"] if klass in OPEN_CLASSES else 0
        for table, ident in (
            (actor_rollup, winner["obligor_actor"]),
            (project_rollup, winner["project_root"]),
        ):
            entry = table.setdefault(ident, blank_rollup())
            entry[klass] += 1
            entry["commitment_count"] += 1
            entry["open_effort_minutes"] += effort
            entry["allocated_minutes"] += allocated[key]

    ledger_open_effort = sum(
        winners[key]["effort_minutes"]
        for key in ledger_keys
        if commitment_class[key] in OPEN_CLASSES
    )
    total_allocated = sum(allocated[key] for key in ledger_keys)

    # ---- surfaces ---------------------------------------------------------
    surface_actors = collections.defaultdict(set)
    surface_count = collections.Counter()
    surface_hops = collections.Counter()
    multi_hop = 0
    for item in assertions:
        surface = item["obligor_surface"]
        surface_actors[surface].add(item["obligor_actor"])
        surface_count[surface] += 1
        if item["obligor_hops"] > surface_hops[surface]:
            surface_hops[surface] = item["obligor_hops"]
        if item["obligor_hops"] >= 2:
            multi_hop += 1
    split_surfaces = sum(1 for actors in surface_actors.values() if len(actors) > 1)

    # ---- identity residuals ----------------------------------------------
    reject_counts = collections.Counter(entry[0] for entry in rejects)
    rows_rejected = len(rejects)
    rows_accepted = rows_ingested - rows_rejected
    class_counts = collections.Counter(commitment_class[key] for key in ordered_keys)

    residuals = {}
    residuals["I1_row_partition"] = rows_accepted - (
        len(assertions) + applied_total + len(live_edges) + len(dropped_edges)
    )
    residuals["I2_class_partition"] = len(ordered_keys) - sum(
        class_counts.get(name, 0) for name in CLASSES
    )
    residuals["I3_actor_effort"] = (
        sum(entry["open_effort_minutes"] for entry in actor_rollup.values())
        - ledger_open_effort
    )
    residuals["I4_project_effort"] = (
        sum(entry["open_effort_minutes"] for entry in project_rollup.values())
        - ledger_open_effort
    )
    residuals["I5_closure_frontier"] = sum(
        stats["frontier_count"] for stats in closure_stats.values()
    ) - sum(1 for row in closure_rows if row["terminal"] == "yes")

    # ---- audit ------------------------------------------------------------
    audit = {
        "rows_ingested": rows_ingested,
        "rows_rejected": rows_rejected,
        "rows_accepted": rows_accepted,
        "commitments_admitted": len(ordered_keys),
        "class_actionable": class_counts.get("ACTIONABLE", 0),
        "class_blocked": class_counts.get("BLOCKED", 0),
        "class_deferred": class_counts.get("DEFERRED", 0),
        "class_settled": class_counts.get("SETTLED", 0),
        "class_unresolvable": class_counts.get("UNRESOLVABLE", 0),
        "class_withdrawn": class_counts.get("WITHDRAWN", 0),
        "reject_ambiguous_identity": reject_counts.get("AMBIGUOUS_IDENTITY", 0),
        "reject_feed_retired": reject_counts.get("FEED_RETIRED", 0),
        "reject_illegal_transition": reject_counts.get("ILLEGAL_TRANSITION", 0),
        "reject_malformed_row": reject_counts.get("MALFORMED_ROW", 0),
        "reject_nonpositive_effort": reject_counts.get("NONPOSITIVE_EFFORT", 0),
        "reject_out_of_window": reject_counts.get("OUT_OF_WINDOW", 0),
        "reject_unknown_commitment": reject_counts.get("UNKNOWN_COMMITMENT", 0),
        "reject_unknown_principal": reject_counts.get("UNKNOWN_PRINCIPAL", 0),
        "reject_unknown_project": reject_counts.get("UNKNOWN_PROJECT", 0),
        "live_edges": len(live_edges),
        "dropped_edges": len(dropped_edges),
        "closure_pairs": len(closure_rows),
        "blocked_commitments": len(blocked),
        "open_effort_minutes": ledger_open_effort,
        "allocated_minutes": total_allocated,
        "escalated_commitments": len(escalations),
        "cadence_debt_total": sum(
            entry["debt"] for entry in cadence_debt.values()
        ),
    }

    # ---- deliverables -----------------------------------------------------
    files = {}

    files["normalized_assertions.jsonl"] = jsonl_bytes(
        [
            {
                "assertion_id": item["assertion_id"],
                "commitment_key": item["commitment_key"],
                "obligor_actor": item["obligor_actor"],
                "obligee_actor": item["obligee_actor"],
                "obligee_status": item["obligee_status"],
                "project_code": item["project_code"],
                "project_root": item["project_root"],
                "due_at": item["due_at"],
                "commitment_day": item["commitment_day"],
                "effort_minutes": item["effort_minutes"],
                "effort_origin": item["effort_origin"],
                "cadence_ref": item["cadence_ref"],
                "observed_at": item["observed_at"],
                "source_class": item["source_class"],
            }
            for item in sorted(assertions, key=lambda i: i["assertion_id"])
        ]
    )

    files["rejects.csv"] = csv_bytes(
        ["feed_file", "row_index", "record_kind", "record_id", "commitment_key", "reason_code"],
        [
            (entry[1], entry[2], entry[4], entry[3], entry[5], entry[0])
            for entry in sorted(
                rejects, key=lambda e: (e[0], e[1], e[2], e[3])
            )
        ],
    )

    files["alias_resolution.jsonl"] = jsonl_bytes(
        [
            {
                "surface_folded": surface,
                "distinct_actors": sorted(surface_actors[surface]),
                "assertion_count": surface_count[surface],
                "max_hops": surface_hops[surface],
            }
            for surface in sorted(surface_actors)
        ]
    )

    actor_commitments = collections.Counter()
    actor_open_effort = collections.Counter()
    for key in ordered_keys:
        winner = winners[key]
        actor_commitments[winner["obligor_actor"]] += 1
        if commitment_class[key] in OPEN_CLASSES:
            actor_open_effort[winner["obligor_actor"]] += winner["effort_minutes"]
    files["actor_roster.csv"] = csv_bytes(
        [
            "actor_id",
            "canonical_handle",
            "commitment_count",
            "open_effort_minutes",
            "waivers_granted",
            "waivers_lapsed",
        ],
        [
            (
                actor,
                identities.canonical_handle[actor],
                actor_commitments.get(actor, 0),
                actor_open_effort.get(actor, 0),
                actor_waivers_granted.get(actor, 0),
                actor_waivers_lapsed.get(actor, 0),
            )
            for actor in identities.actors
        ],
    )

    code_assertions = collections.Counter(item["project_code"] for item in assertions)
    code_allocated = collections.Counter()
    for key in ordered_keys:
        code_allocated[winners[key]["project_code"]] += allocated[key]
    files["project_lineage.csv"] = csv_bytes(
        ["project_code", "project_root", "assertion_count", "allocated_minutes"],
        [
            (code, projects.root(code), code_assertions[code], code_allocated.get(code, 0))
            for code in sorted(code_assertions)
        ],
    )

    files["assertion_contests.csv"] = csv_bytes(
        ["commitment_key", "winning_assertion", "winning_class", "contender_count", "distinct_classes"],
        [
            (
                key,
                winners[key]["assertion_id"],
                winners[key]["source_class"],
                len(by_key[key]),
                len(set(item["source_class"] for item in by_key[key])),
            )
            for key in ordered_keys
        ],
    )

    files["commitment_ledger.jsonl"] = jsonl_bytes(ledger)

    files["state_resolution.csv"] = csv_bytes(
        ["commitment_key", "resolved_state", "assertions_seen", "assertions_applied", "governing_class"],
        [
            (
                key,
                resolved_state[key],
                seen_count[key],
                applied_count[key],
                governing_class[key],
            )
            for key in ordered_keys
        ],
    )

    files["live_edges.csv"] = csv_bytes(
        ["edge_id", "dependent_key", "blocker_key", "asserted_at", "dependent_actor", "blocker_actor", "dependent_blocked"],
        [
            (
                edge["edge_id"],
                edge["dependent_key"],
                edge["blocker_key"],
                edge["asserted_at"],
                edge["dependent_actor"],
                edge["blocker_actor"],
                "yes" if edge["dependent_key"] in blocked else "no",
            )
            for edge in sorted(
                live_edges,
                key=lambda e: (e["dependent_key"], e["blocker_key"], e["edge_id"]),
            )
        ],
    )

    files["dropped_edges.csv"] = csv_bytes(
        ["edge_id", "dependent_key", "blocker_key", "asserted_at", "drop_reason"],
        [
            (
                edge["edge_id"],
                edge["dependent_key"],
                edge["blocker_key"],
                edge["asserted_at"],
                edge["drop_reason"],
            )
            for edge in sorted(
                dropped_edges, key=lambda e: (e["drop_reason"], e["edge_id"])
            )
        ],
    )

    files["blocking_closure.jsonl"] = jsonl_bytes(closure_rows)

    files["blocked_commitments.csv"] = csv_bytes(
        ["commitment_key", "reachable_blockers", "frontier_count", "chain_depth", "frontier_head", "allocated_minutes"],
        [
            (
                key,
                closure_stats[key]["reachable_blockers"],
                closure_stats[key]["frontier_count"],
                closure_stats[key]["chain_depth"],
                closure_stats[key]["frontier_head"],
                allocated[key],
            )
            for key in sorted(blocked)
        ],
    )

    def queue_rows(target_class):
        return [
            (
                row["commitment_key"],
                row["obligor_actor"],
                row["commitment_day"],
                row["effort_minutes"],
                row["project_root"],
                row["allocated_minutes"],
            )
            for row in ledger
            if row["commitment_class"] == target_class
        ]

    queue_header = [
        "commitment_key",
        "obligor_actor",
        "commitment_day",
        "effort_minutes",
        "project_root",
        "allocated_minutes",
    ]
    files["actionable_queue.tsv"] = csv_bytes(
        queue_header, queue_rows("ACTIONABLE"), "\t"
    )
    files["deferred_queue.psv"] = csv_bytes(
        queue_header, queue_rows("DEFERRED"), "|"
    )

    files["withdrawn_register.csv"] = csv_bytes(
        ["commitment_key", "obligor_actor", "commitment_day", "effort_minutes", "source_class"],
        [
            (
                row["commitment_key"],
                row["obligor_actor"],
                row["commitment_day"],
                row["effort_minutes"],
                row["source_class"],
            )
            for row in ledger
            if row["commitment_class"] == "WITHDRAWN"
        ],
    )

    files["unresolvable.jsonl"] = jsonl_bytes(
        [
            {
                "commitment_key": key,
                "reason_code": unresolvable_reason[key],
                "obligor_actor": winners[key]["obligor_actor"],
                "commitment_day": winners[key]["commitment_day"],
            }
            for key in sorted(
                unresolvable_reason, key=lambda k: (unresolvable_reason[k], k)
            )
        ]
    )

    files["cadence_debt.csv"] = csv_bytes(
        ["cadence_id", "period_days", "periods_elapsed", "periods_discharged", "periods_waived", "debt", "max_streak"],
        [
            (
                cadence_id,
                cadence_debt[cadence_id]["period_days"],
                cadence_debt[cadence_id]["periods_elapsed"],
                cadence_debt[cadence_id]["periods_discharged"],
                cadence_debt[cadence_id]["periods_waived"],
                cadence_debt[cadence_id]["debt"],
                cadence_debt[cadence_id]["max_streak"],
            )
            for cadence_id in sorted(cadence_debt)
        ],
    )

    files["waiver_trace.jsonl"] = jsonl_bytes(waiver_trace)

    allocation_rows = []
    for actor, month in sorted(groups):
        for key in sorted(groups[(actor, month)]):
            allocation_rows.append(
                (
                    month,
                    actor,
                    key,
                    winners[key]["effort_minutes"],
                    allocated[key],
                )
            )
    allocation_rows.sort(key=lambda row: (row[0], row[1], row[2]))
    files["attention_allocation.csv"] = csv_bytes(
        ["year_month", "obligor_actor", "commitment_key", "demand_minutes", "allocated_minutes"],
        allocation_rows,
    )

    month_load.sort(key=lambda row: (row["year_month"], row["obligor_actor"]))
    files["month_load_index.csv"] = csv_bytes(
        ["year_month", "obligor_actor", "budget_source", "budget_minutes", "reserve_minutes", "demand_minutes", "allocated_minutes", "open_count"],
        [
            (
                row["year_month"],
                row["obligor_actor"],
                row["budget_source"],
                row["budget_minutes"],
                row["reserve_minutes"],
                row["demand_minutes"],
                row["allocated_minutes"],
                row["open_count"],
            )
            for row in month_load
        ],
    )

    files["escalation_queue.csv"] = csv_bytes(
        ["commitment_key", "obligor_actor", "commitment_class", "effort_minutes", "allocated_minutes", "shortfall_minutes", "principal_debt", "chain_depth", "trigger"],
        [
            (
                row["commitment_key"],
                row["obligor_actor"],
                row["commitment_class"],
                row["effort_minutes"],
                row["allocated_minutes"],
                row["shortfall_minutes"],
                row["principal_debt"],
                row["chain_depth"],
                row["trigger"],
            )
            for row in escalations
        ],
    )

    files["actor_rollup.json"] = json_bytes(actor_rollup)
    files["project_rollup.json"] = json_bytes(project_rollup)

    provenance = []
    for key in ordered_keys:
        contributing = sorted(item["assertion_id"] for item in by_key[key])
        provenance.append(
            {
                "commitment_key": key,
                "winning_assertion": winners[key]["assertion_id"],
                "contributing_assertions": contributing,
                "source_files": sorted(set(item["feed_file"] for item in by_key[key])),
                "state_assertions": sorted(
                    item["state_id"] for item in states_by_key.get(key, ())
                ),
            }
        )
    files["provenance_index.jsonl"] = jsonl_bytes(provenance)

    files["audit_totals.csv"] = csv_bytes(
        ["metric", "value"], [(name, audit[name]) for name, _ in AUDIT_METRICS]
    )

    lines = ["CALDERMOOR COMMITMENT CLOSURE"]
    for name, starred in AUDIT_METRICS:
        if starred:
            lines.append("%s %d" % (name, audit[name]))
    for name in IDENTITIES:
        lines.append("identity_%s %d" % (name, residuals[name]))
    files["reconciliation.txt"] = text_bytes(lines)

    files["validation_report.json"] = json_bytes(
        {
            "identities": {name: residuals[name] for name in IDENTITIES},
            "identities_checked": sorted(IDENTITIES),
            "all_residuals_zero": all(
                residuals[name] == 0 for name in IDENTITIES
            ),
        }
    )

    files["run_manifest.json"] = json_bytes(
        {
            "day_boundary_offset_minutes": DAY_BOUNDARY_OFFSET_MINUTES,
            "effort_floor_minutes": EFFORT_FLOOR,
            "effort_ceiling_minutes": EFFORT_CEILING,
            "allocation_floor_minutes": ALLOCATION_FLOOR,
            "window_start": WINDOW_START,
            "window_end": WINDOW_END,
            "reason_codes": sorted(REASON_CODES),
            "commitment_classes": sorted(CLASSES),
            "retired_feeds": retired_feeds,
            "split_surfaces": split_surfaces,
            "multi_hop_assertions": multi_hop,
            "order_tiebreaks_applied": order_tiebreaks,
            "edges_dropped_out_of_scope": sum(
                1 for edge in dropped_edges if edge["drop_reason"] == "EDGE_OUT_OF_SCOPE"
            ),
            "waivers_suppressing": sum(
                1 for row in waiver_trace if row["effect"] == "SUPPRESSED"
            ),
            "waivers_inert": sum(
                1 for row in waiver_trace if row["effect"] == "INERT"
            ),
            "waivers_lapsed": sum(
                1 for row in waiver_trace if row["effect"] == "LAPSED"
            ),
            "allocations_starved": allocations_starved,
            "illegal_transitions": reject_counts.get("ILLEGAL_TRANSITION", 0),
        }
    )

    return files


def publish(files, out_dir):
    staging = tempfile.mkdtemp(prefix="reconcile-stage-")
    try:
        for name, payload in files.items():
            with open(os.path.join(staging, name), "wb") as handle:
                handle.write(payload)
        if not os.path.isdir(out_dir):
            os.makedirs(out_dir)
        for existing in os.listdir(out_dir):
            target = os.path.join(out_dir, existing)
            if os.path.isdir(target) and not os.path.islink(target):
                shutil.rmtree(target)
            else:
                os.remove(target)
        for name in sorted(files):
            shutil.copyfile(os.path.join(staging, name), os.path.join(out_dir, name))
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: reconcile.py DATA_DIR OUT_DIR\n")
        return 2
    data_dir = argv[1]
    out_dir = argv[2]
    if os.path.realpath(data_dir) == os.path.realpath(out_dir):
        raise RuntimeError("the output directory may not be the extract directory")
    with open(os.path.abspath(__file__), "rb") as handle:
        own_source = handle.read()
    files = build(data_dir)
    files["reconcile.py"] = own_source
    missing = set(DELIVERABLES) - set(files)
    extra = set(files) - set(DELIVERABLES)
    if missing or extra:
        raise RuntimeError("deliverable set mismatch: %r %r" % (sorted(missing), sorted(extra)))
    publish(files, out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
