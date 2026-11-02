#!/usr/bin/env python3
"""Rebuild the reminder surface from change-ledger evidence.

Reads only the evidence directory handed to --input and writes
reproduced_state.json into the directory handed to --out.
"""

import argparse
import csv
import hashlib
import io
import json
import os
import re
import sqlite3
import xml.etree.ElementTree as ET
import zipfile

MAIN_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
DOC_REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

INT_FIELDS = ("seq", "value", "authority_rank", "effective_generation")

AUTHORITY_ORDERING_KEY = "effective_generation,seq"
CONTROL_ORDERING_KEY = "seq"


# --------------------------------------------------------------------------
# evidence readers
# --------------------------------------------------------------------------

def _coerce(record):
    for key, value in list(record.items()):
        if isinstance(value, str):
            record[key] = value.strip()
    for field in INT_FIELDS:
        if field in record and not isinstance(record[field], int):
            record[field] = int(record[field])
    return record


def _read_delimited(path, delimiter):
    with io.open(path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle, delimiter=delimiter)
        rows = [row for row in reader if any(cell.strip() for cell in row)]
    header = [cell.strip() for cell in rows[0]]
    return [_coerce(dict(zip(header, row))) for row in rows[1:]]


def _read_ndjson(path):
    out = []
    with io.open(path, "r", encoding="utf-8-sig") as handle:
        for line in handle:
            line = line.strip()
            if line:
                out.append(_coerce(json.loads(line)))
    return out


def read_record_file(path):
    lower = path.lower()
    if lower.endswith(".csv"):
        return _read_delimited(path, ",")
    if lower.endswith(".psv"):
        return _read_delimited(path, "|")
    if lower.endswith(".ndjson"):
        return _read_ndjson(path)
    raise ValueError("unsupported record format: %s" % path)


def read_ledger(input_dir):
    """The ledger is the union of shard_* files directly inside ledger/.

    A re-exported record sequence is governed by the copy in the shard whose
    file name sorts last.
    """
    ledger_dir = os.path.join(input_dir, "ledger")
    names = sorted(
        name for name in os.listdir(ledger_dir)
        if name.startswith("shard_")
        and os.path.isfile(os.path.join(ledger_dir, name))
    )
    by_seq = {}
    for name in names:
        for record in read_record_file(os.path.join(ledger_dir, name)):
            by_seq[record["seq"]] = record
    return [by_seq[seq] for seq in sorted(by_seq)]


def read_journal(input_dir):
    path = os.path.join(input_dir, "release_ops.sqlite")
    connection = sqlite3.connect(path)
    try:
        cursor = connection.execute(
            "SELECT line_no, op, scope, record_seq, retired_anchor,"
            " surviving_anchor, status FROM journal ORDER BY line_no ASC"
        )
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        connection.close()


def _sheet_rows(archive, target):
    shared = []
    if "xl/sharedStrings.xml" in archive.namelist():
        shared = [
            "".join(node.text or "" for node in item.iter(MAIN_NS + "t"))
            for item in ET.fromstring(archive.read("xl/sharedStrings.xml"))
        ]
    root = ET.fromstring(archive.read("xl/" + target.lstrip("/")))
    rows = []
    for row in root.iter(MAIN_NS + "row"):
        cells = []
        for cell in row.iter(MAIN_NS + "c"):
            node = cell.find(MAIN_NS + "v")
            text = node.text if node is not None else ""
            if cell.get("t") == "s":
                text = shared[int(text)]
            cells.append((text or "").strip())
        rows.append(cells)
    return rows


def read_restricted_map(input_dir):
    """Rows of the sheet whose name starts with active_, keyed by header."""
    path = os.path.join(input_dir, "restricted_scope_map.xlsx")
    archive = zipfile.ZipFile(path)
    try:
        rels = {
            rel.get("Id"): rel.get("Target")
            for rel in ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        }
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        target = None
        for sheet in workbook.iter(MAIN_NS + "sheet"):
            if sheet.get("name", "").startswith("active_"):
                target = rels[sheet.get(DOC_REL_NS + "id")]
        if target is None:
            raise ValueError("no active_ sheet in restricted scope map")
        rows = _sheet_rows(archive, target)
    finally:
        archive.close()
    header = [cell.strip() for cell in rows[0]]
    mapping = {}
    for row in rows[1:]:
        if not any(row):
            continue
        entry = dict(zip(header, row))
        mapping[(int(entry["alt_key"]), entry["lineage_anchor"])] = int(
            entry["canonical_value"]
        )
    return mapping


def read_catalogue_classes(input_dir):
    path = os.path.join(input_dir, "urgency_class_catalogue.json")
    with io.open(path, "r", encoding="utf-8-sig") as handle:
        catalogue = json.load(handle)
    return [entry["name"] for entry in catalogue["classes"]]


def read_addenda(input_dir):
    """Addendum body text keyed by addendum number, ascending."""
    pattern = re.compile(r"^policy_addendum_A(\d+)\.docx$")
    found = []
    for name in sorted(os.listdir(input_dir)):
        match = pattern.match(name)
        if not match:
            continue
        archive = zipfile.ZipFile(os.path.join(input_dir, name))
        try:
            xml = archive.read("word/document.xml").decode("utf-8")
        finally:
            archive.close()
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", xml))
        found.append((int(match.group(1)), text))
    found.sort()
    return found


def published_window_from_addenda(input_dir):
    """The window the highest-numbered addendum ruling on it publishes.

    None means the governing addendum withdrew publication, which sends the
    window back to parameter recovery.
    """
    verdict = None
    for _number, text in read_addenda(input_dir):
        if not re.search(r"deprecation window", text, re.I):
            continue
        if re.search(r"no longer published|recovered from the calibration",
                     text, re.I):
            verdict = None
            continue
        match = re.search(r"deprecation window is (\d+) generations", text, re.I)
        if match:
            verdict = int(match.group(1))
    return verdict


# --------------------------------------------------------------------------
# journal view
# --------------------------------------------------------------------------

class JournalView(object):
    """Admission, rollback and anchor settlement drawn from the journal."""

    def __init__(self, operations):
        self.applies = {}
        self.rollbacks = {}
        self.supersedes = {}
        for operation in operations:
            op = operation["op"]
            if op == "apply_change":
                self.applies.setdefault(operation["record_seq"], []).append(
                    operation["status"])
            elif op == "rollback_change":
                self.rollbacks.setdefault(operation["record_seq"], []).append(
                    operation["status"])
            elif op == "supersede_anchor":
                self.supersedes.setdefault(operation["scope"], []).append(operation)

    def rolled_back(self, seq):
        return any(status != "rejected" for status in self.rollbacks.get(seq, []))

    def admission_rejected(self, seq):
        statuses = self.applies.get(seq, [])
        return bool(statuses) and all(status == "rejected" for status in statuses)

    def settled_anchor(self, scope):
        """Surviving anchor of the last non-rejected supersede for a scope."""
        surviving = None
        for operation in self.supersedes.get(scope, []):
            if operation["status"] != "rejected":
                surviving = operation["surviving_anchor"]
        return surviving

    def retires_anchor(self, scope, anchor):
        return any(
            operation["status"] != "rejected"
            and operation["retired_anchor"] == anchor
            for operation in self.supersedes.get(scope, [])
        )

    def resolve_anchor(self, scope, anchor):
        if anchor == "pending" or self.retires_anchor(scope, anchor):
            settled = self.settled_anchor(scope)
            if settled is not None:
                return settled
        return anchor


class NoJournal(object):
    """Calibration controls are replayed with every record admitted."""

    def rolled_back(self, seq):
        return False

    def admission_rejected(self, seq):
        return False

    def resolve_anchor(self, scope, anchor):
        return anchor


# --------------------------------------------------------------------------
# replay
# --------------------------------------------------------------------------

def authority_sort_key(record):
    return (record["effective_generation"], record["seq"])


def control_sort_key(record):
    return (record["seq"],)


def resolve_value(record, journal, scope_map):
    if record.get("reference_domain") != "restricted_scope_index":
        return record["value"], record["lineage_anchor"]
    anchor = journal.resolve_anchor(record["scope"], record["lineage_anchor"])
    return scope_map[(record["value"], anchor)], anchor


def replay(records, journal, scope_map, window, order_key):
    """Fold the ledger into a surface under the given ordering key."""
    active = {}
    retired = []
    deprecations = {}
    effective = []
    inert = []
    revisited = []

    for record in sorted(records, key=order_key):
        seq = record["seq"]
        scope = record["scope"]
        op = record["op"]

        if journal.rolled_back(seq):
            inert.append((seq, "rolled_back"))
            continue
        if journal.admission_rejected(seq):
            inert.append((seq, "apply_change_rejected"))
            continue

        value, anchor = resolve_value(record, journal, scope_map)
        reason = None

        if op == "publish":
            if scope in active or scope in retired:
                reason = "publish_names_known_scope"
            else:
                active[scope] = value
        elif op == "revise":
            if scope not in active:
                reason = "revise_names_inactive_scope"
            elif active[scope] == value:
                reason = "revise_keeps_value"
            else:
                active[scope] = value
        elif op == "deprecate":
            if scope not in active:
                reason = "deprecate_names_inactive_scope"
            else:
                deprecations.setdefault(scope, []).append(
                    (record["authority_rank"], record["effective_generation"]))
        elif op == "restore":
            if scope not in active or not deprecations.get(scope):
                reason = "restore_without_open_deprecation"
            elif record["authority_rank"] < deprecations[scope][-1][0]:
                reason = "restore_rank_below_deprecation"
            else:
                deprecations[scope].pop()
        elif op == "withdraw":
            if scope not in active:
                reason = "withdraw_names_inactive_scope"
            else:
                del active[scope]
                deprecations.pop(scope, None)
                retired.append(scope)
        else:
            raise ValueError("unknown operation: %s" % op)

        if reason is not None:
            inert.append((seq, reason))
            continue

        effective.append(record)
        if record.get("reference_domain") == "restricted_scope_index":
            revisited.append({
                "seq": seq,
                "scope": scope,
                "lineage_anchor": anchor,
                "canonical_value": value,
            })

    surface_generation = max(record["effective_generation"] for record in records)

    aged = []
    for scope in list(active):
        open_deprecations = deprecations.get(scope)
        if not open_deprecations:
            continue
        _rank, generation = open_deprecations[-1]
        if surface_generation - generation >= window:
            aged.append((generation, scope))
    for _generation, scope in sorted(aged):
        del active[scope]
        retired.append(scope)

    inert.sort(key=lambda entry: entry[0])

    return {
        "active": active,
        "retired": retired,
        "surface_generation": surface_generation,
        "effective": effective,
        "inert": [{"seq": seq, "reason": reason} for seq, reason in inert],
        "revisited_anchors": revisited,
    }


# --------------------------------------------------------------------------
# derived quantities
# --------------------------------------------------------------------------

def surface_digest(active):
    payload = json.dumps(active, sort_keys=True, separators=(",", ":"))
    return hashlib.blake2b(payload.encode("utf-8"), digest_size=8).hexdigest()


def version_fold(effective_records):
    major = minor = patch = 0
    for record in effective_records:
        urgency = record["urgency_class"]
        if urgency == "breaking":
            major += 1
            minor = 0
            patch = 0
        elif urgency == "additive":
            minor += 1
            patch = 0
        elif urgency == "internal":
            patch += 1
        else:
            raise ValueError("unknown urgency class: %s" % urgency)
    return "%d.%d.%d" % (major, minor, patch)


def class_counts(records, classes):
    counts = dict((name, 0) for name in classes)
    for record in records:
        counts[record["urgency_class"]] = counts.get(record["urgency_class"], 0) + 1
    return counts


# --------------------------------------------------------------------------
# parameter recovery
# --------------------------------------------------------------------------

WINDOW_RANGE = range(2, 31)
WEIGHT_RANGE = range(1, 100)
TIE_BREAK_ORDER = ("breaking", "additive", "internal")


def read_controls(input_dir):
    calibration = os.path.join(input_dir, "calibration")
    published = _read_delimited(
        os.path.join(calibration, "published_controls.psv"), "|")
    controls = []
    for row in published:
        name = row["control"]
        retired = row["retired_scopes"]
        expected = [] if retired == "-" else [
            part.strip() for part in retired.split(";") if part.strip()]
        controls.append({
            "name": name,
            "records": read_record_file(
                os.path.join(calibration, name + ".ndjson")),
            "retired": expected,
            "grand_total": int(row["urgency_grand_total"]),
        })
    return controls


def recover_parameters(input_dir, classes, window_override=None):
    """Recover the window from the retired lists and the weights from the
    grand totals; where several candidates fit, take the largest window and
    then the largest weights in breaking, additive, internal order.

    A window an addendum still publishes binds on its own and is not put to
    the controls.
    """
    controls = read_controls(input_dir)
    no_journal = NoJournal()

    if window_override is None:
        windows = [
            window for window in WINDOW_RANGE
            if all(
                replay(control["records"], no_journal, {}, window,
                       authority_sort_key)["retired"] == control["retired"]
                for control in controls
            )
        ]
        if not windows:
            raise ValueError(
                "no deprecation window fits the calibration controls")
    else:
        windows = [window_override]

    ordered = [name for name in TIE_BREAK_ORDER if name in classes]
    ordered += [name for name in classes if name not in ordered]
    if len(ordered) != 3:
        raise ValueError("weight recovery expects three catalogue classes")

    counts = [class_counts(control["records"], classes) for control in controls]
    totals = [control["grand_total"] for control in controls]

    best = None
    for first in WEIGHT_RANGE:
        for second in WEIGHT_RANGE:
            for third in WEIGHT_RANGE:
                weights = {ordered[0]: first, ordered[1]: second,
                           ordered[2]: third}
                if all(
                    sum(count[name] * weights[name] for name in classes) == total
                    for count, total in zip(counts, totals)
                ):
                    rank = (first, second, third)
                    if best is None or rank > best[0]:
                        best = (rank, weights)
    if best is None:
        raise ValueError("no urgency weights fit the calibration controls")

    return max(windows), best[1]


# --------------------------------------------------------------------------
# recovery
# --------------------------------------------------------------------------

def recover(input_dir):
    classes = read_catalogue_classes(input_dir)
    window, weights = recover_parameters(
        input_dir, classes, published_window_from_addenda(input_dir))

    records = read_ledger(input_dir)
    journal = JournalView(read_journal(input_dir))
    scope_map = read_restricted_map(input_dir)

    authority = replay(records, journal, scope_map, window, authority_sort_key)
    control = replay(records, journal, scope_map, window, control_sort_key)
    counts = class_counts(records, classes)

    return {
        "classes": classes,
        "deprecation_window": window,
        "urgency_weights": weights,
        "records": records,
        "journal": journal,
        "authority": authority,
        "control": control,
        "surface_digest": surface_digest(authority["active"]),
        "control_digest": surface_digest(control["active"]),
        "release_version": version_fold(authority["effective"]),
        "generation": authority["surface_generation"],
        "urgency_totals": dict(
            (name, counts[name] * weights[name]) for name in classes),
    }


def write_json(path, payload):
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    with io.open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
        handle.write("\n")


def main():
    parser = argparse.ArgumentParser(
        description="Rebuild the reminder surface from ledger evidence.")
    parser.add_argument("--input", required=True, help="evidence directory")
    parser.add_argument("--out", required=True, help="output directory")
    arguments = parser.parse_args()

    state = recover(arguments.input)
    if not os.path.isdir(arguments.out):
        os.makedirs(arguments.out)

    active = state["authority"]["active"]
    write_json(os.path.join(arguments.out, "reproduced_state.json"), {
        "surface_digest": state["surface_digest"],
        "generation": state["generation"],
        "release_version": state["release_version"],
        "control_digest": state["control_digest"],
        "active_scopes": dict(sorted(active.items())),
        "retired_scopes": list(state["authority"]["retired"]),
        "deprecation_window": state["deprecation_window"],
        "urgency_weights": dict(
            (name, state["urgency_weights"][name])
            for name in sorted(state["classes"])),
    })


if __name__ == "__main__":
    main()
