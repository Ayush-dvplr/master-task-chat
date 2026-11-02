#!/usr/bin/env python3
"""Reference recovery for the 11564348-6b1b-57f4-8851-490d0cbc1c5e bundle.

The recovery reads the evidence directory, replays the change ledger under the
authority ordering key, replays the pending journal operations, rebuilds the
reminder surface, runs the control replay under the record sequence ordering key,
and writes the nine artifacts named by the task contract.

The replay itself lives in one place: the reproducer program that the recovery
also delivers. The recovery loads that program and calls into it, so the
delivered reproducer and the artifacts can never drift apart.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

DATA = Path(os.environ.get("RECOVERY_DATA_DIR", "/app/data"))
OUT = Path(os.environ.get("RECOVERY_OUT_DIR", "/app/out"))

REPRODUCER_SOURCE = '''#!/usr/bin/env python3
"""Rebuild the reminder surface from a change ledger and its supporting files.

The program reads only the directory named by --input and writes
reproduced_state.json into the directory named by --out.
"""

import argparse
import csv
import hashlib
import io
import json
import re
import sqlite3
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

CATALOGUE = "urgency_class_catalogue.json"
ADDENDUM_PATTERN = re.compile(r"policy_addendum_A(\\d+)\\.docx")
PUBLISHED_WINDOW = re.compile(r"window is (\\d+) generations")
JOURNAL_DB = "release_ops.sqlite"
WORKBOOK = "restricted_scope_map.xlsx"
INT_FIELDS = ("seq", "value", "authority_rank", "effective_generation")
LEDGER_KEYS = ("seq", "scope", "op", "value", "urgency_class", "authority_rank",
               "reference_domain", "lineage_anchor", "effective_generation", "recorded_by")
SHEET_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKG_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _typed(record):
    for key in INT_FIELDS:
        record[key] = int(record[key])
    return record


def read_ledger(root):
    """Union of the shards directly inside ledger/; ledger/archive is not read."""
    by_seq = {}
    for path in sorted((root / "ledger").iterdir(), key=lambda item: item.name):
        if not path.is_file() or not path.name.startswith("shard_"):
            continue
        text = path.read_text(encoding="utf-8-sig")
        if path.suffix == ".ndjson":
            shard = [_typed(json.loads(line)) for line in text.splitlines() if line.strip()]
        elif path.suffix in (".csv", ".psv"):
            delimiter = "," if path.suffix == ".csv" else "|"
            reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
            shard = [_typed({key.strip(): value for key, value in row.items()}) for row in reader]
        else:
            raise SystemExit("unknown ledger shard format: %s" % path.name)
        # a record re-exported in a later shard (by file name) replaces the earlier copy
        for record in shard:
            by_seq[record["seq"]] = {key: record[key] for key in LEDGER_KEYS}
    return [by_seq[seq] for seq in sorted(by_seq)]


def read_journal(root):
    """The journal table of the release operations database, in line order."""
    uri = "file:%s?mode=ro&immutable=1" % (root / JOURNAL_DB).resolve()
    con = sqlite3.connect(uri, uri=True)
    try:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            # identifiers are case insensitive in SQLite; aliases fix the key spelling
            "SELECT op AS op, scope AS scope, record_seq AS record_seq, retired_anchor AS retired_anchor, "
            "surviving_anchor AS surviving_anchor, status AS status FROM journal ORDER BY line_no"
        ).fetchall()
    finally:
        con.close()
    return [dict(row) for row in rows]


def read_restricted_rows(root):
    """Rows of the workbook sheet whose name starts with active_."""
    with zipfile.ZipFile(root / WORKBOOK) as book:
        workbook = ET.fromstring(book.read("xl/workbook.xml"))
        rels = ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
        targets = {rel.get("Id"): rel.get("Target") for rel in rels.iter(PKG_NS + "Relationship")}
        active = [s for s in workbook.iter(SHEET_NS + "sheet") if s.get("name").startswith("active_")]
        if len(active) != 1:
            raise SystemExit("the workbook must hold exactly one active_ sheet")
        target = targets[active[0].get(REL_NS + "id")].lstrip("/")
        if not target.startswith("xl/"):
            target = "xl/" + target
        strings = []
        if "xl/sharedStrings.xml" in book.namelist():
            shared = ET.fromstring(book.read("xl/sharedStrings.xml"))
            strings = [_string_item_text(si) for si in shared.iter(SHEET_NS + "si")]
        sheet = ET.fromstring(book.read(target))
    table = []
    for row in sheet.iter(SHEET_NS + "row"):
        cells = {}
        position = 0
        for cell in row.iter(SHEET_NS + "c"):
            ref = cell.get("r")
            if ref:
                position = _column_index(ref)
            kind = cell.get("t")
            if kind == "s":
                cells[position] = strings[int(cell.find(SHEET_NS + "v").text)]
            elif kind == "inlineStr":
                cells[position] = _string_item_text(cell.find(SHEET_NS + "is"))
            elif cell.find(SHEET_NS + "v") is not None:
                cells[position] = int(cell.find(SHEET_NS + "v").text)
            position += 1
        table.append(cells)
    header = {index: str(name).strip() for index, name in table[0].items()}
    rows = []
    for cells in table[1:]:
        named = {header[i]: value for i, value in cells.items() if i in header}
        if "alt_key" not in named:
            continue
        rows.append({"alt_key": int(named["alt_key"]), "lineage_anchor": str(named["lineage_anchor"]).strip(),
                     "canonical_value": int(named["canonical_value"])})
    return rows


def _column_index(ref):
    """Zero based column of a cell reference such as C7."""
    index = 0
    for char in ref:
        if not char.isalpha():
            break
        index = index * 26 + (ord(char.upper()) - 64)
    return index - 1


def _string_item_text(item):
    """Text of a shared or inline string: its t and rich text runs, never phonetic rPh runs."""
    parts = []
    for child in item:
        if child.tag == SHEET_NS + "t":
            parts.append(child.text or "")
        elif child.tag == SHEET_NS + "r":
            parts.extend(t.text or "" for t in child.iter(SHEET_NS + "t"))
    return "".join(parts)


def read_docx_paragraphs(path):
    """Paragraph text of a Word document, one string per paragraph."""
    with zipfile.ZipFile(path) as document:
        body = ET.fromstring(document.read("word/document.xml"))
    return ["".join(node.text or "" for node in para.iter(WORD_NS + "t"))
            for para in body.iter(WORD_NS + "p")]


def governing_window(root):
    """The deprecation window the addenda put in force, or None to recover it.

    An addendum overrides the policy document on every rule it amends, and where
    two addenda amend the same rule the higher number governs, so the addenda are
    read highest number first and the first one that speaks about the deprecation
    window settles it. It either publishes an integer or withdraws the value and
    sends the window to parameter recovery.
    """
    numbered = []
    for path in root.iterdir():
        match = ADDENDUM_PATTERN.fullmatch(path.name)
        if match:
            numbered.append((int(match.group(1)), path))
    for _, path in sorted(numbered, key=lambda item: item[0], reverse=True):
        for line in read_docx_paragraphs(path):
            if "deprecation window" not in line.lower():
                continue
            if "no longer published" in line:
                return None
            published = PUBLISHED_WINDOW.search(line)
            if published:
                return int(published.group(1))
    return None


WINDOW_RANGE = range(2, 31)
WEIGHT_RANGE = range(1, 100)
CLASS_ORDER = ("breaking", "additive", "internal")


def read_calibration(root):
    """Control ledgers under calibration/ and the outputs published for them."""
    lines = (root / "calibration" / "published_controls.psv").read_text(encoding="utf-8-sig").splitlines()
    reader = csv.DictReader(lines, delimiter="|")
    controls = []
    for row in reader:
        name = row["control"]
        text = (root / "calibration" / (name + ".ndjson")).read_text(encoding="utf-8-sig")
        records = [_typed(json.loads(line)) for line in text.splitlines() if line.strip()]
        retired = [] if row["retired_scopes"] == "-" else row["retired_scopes"].split(";")
        controls.append((name, records, retired, int(row["urgency_grand_total"])))
    return controls


def control_retired(records, window):
    """Retired list of a calibration control: no journal, every reference literal."""
    surface = {}
    retired = []
    stacks = {}
    for record in sorted(records, key=lambda r: (r["effective_generation"], r["seq"])):
        scope, op = record["scope"], record["op"]
        if op == "publish" and scope not in surface and scope not in retired:
            surface[scope] = record["value"]
        elif op == "revise" and scope in surface:
            surface[scope] = record["value"]
        elif op == "deprecate" and scope in surface:
            stacks.setdefault(scope, []).append((record["authority_rank"], record["effective_generation"]))
        elif op == "restore" and scope in surface and stacks.get(scope):
            if record["authority_rank"] >= stacks[scope][-1][0]:
                stacks[scope].pop()
        elif op == "withdraw" and scope in surface:
            del surface[scope]
            retired.append(scope)
            stacks.pop(scope, None)
    generation = max(record["effective_generation"] for record in records)
    expired = sorted(
        (stack[-1][1], scope)
        for scope, stack in stacks.items()
        if scope in surface and stack and generation - stack[-1][1] >= window
    )
    return retired + [scope for _, scope in expired]


def recover_window(controls):
    """Largest window in range that reproduces every published retired list."""
    fitting = [w for w in WINDOW_RANGE if all(control_retired(rec, w) == ret for _, rec, ret, _ in controls)]
    if not fitting:
        raise SystemExit("no deprecation window reproduces the calibration controls")
    return max(fitting)


def recover_weights(controls):
    """Weights reproducing every grand total; ties go to the largest breaking, additive, internal."""
    counts = []
    for _, records, _, total in controls:
        tally = [sum(1 for r in records if r["urgency_class"] == name) for name in CLASS_ORDER]
        counts.append((tally, total))
    solver = [c for c in counts if c[0][2] > 0]
    best = None
    for breaking in WEIGHT_RANGE:
        for additive in WEIGHT_RANGE:
            if solver:
                (nb, na, ni), total = solver[0]
                rest = total - nb * breaking - na * additive
                if rest % ni:
                    continue
                choices = [rest // ni] if rest // ni in WEIGHT_RANGE else []
            else:
                choices = list(WEIGHT_RANGE)
            for internal in choices:
                weights = (breaking, additive, internal)
                if all(sum(n * w for n, w in zip(tally, weights)) == total for tally, total in counts):
                    if best is None or weights > best:
                        best = weights
    if best is None:
        raise SystemExit("no urgency weights reproduce the calibration controls")
    return dict(zip(CLASS_ORDER, best))


def digest(surface):
    blob = json.dumps(surface, sort_keys=True, separators=(",", ":"))
    return hashlib.blake2b(blob.encode("utf-8"), digest_size=8).hexdigest()


def journal_view(journal):
    """Collect the journal view: every operation not rejected takes part."""
    superseded = {}
    retired_anchors = {}
    withdrawn = set()
    named = set()
    admitted = set()
    for op in journal:
        kind = op.get("op")
        live = op.get("status") != "rejected"
        if kind == "apply_change":
            named.add(op["record_seq"])
            if live:
                admitted.add(op["record_seq"])
        if not live:
            continue
        if kind == "rollback_change":
            withdrawn.add(op["record_seq"])
        elif kind == "supersede_anchor":
            # the last non rejected supersede of a scope, in journal order, wins
            superseded[op["scope"]] = op["surviving_anchor"]
            retired_anchors.setdefault(op["scope"], set()).add(op["retired_anchor"])
    gated = named - admitted
    # a written anchor that a live supersede of its own scope retires resolves like a pending one
    superseded = {"latest": superseded, "retired": retired_anchors}
    return superseded, withdrawn, gated


def settled_anchor(record, superseded):
    anchor = record["lineage_anchor"]
    scope = record["scope"]
    if anchor == "pending" or anchor in superseded["retired"].get(scope, ()):
        anchor = superseded["latest"].get(scope)
    return anchor


def resolve_value(record, restricted_rows, superseded):
    if record["reference_domain"] == "scope_id":
        return record["value"]
    anchor = settled_anchor(record, superseded)
    for row in restricted_rows:
        if row["alt_key"] == record["value"] and row["lineage_anchor"] == anchor:
            return row["canonical_value"]
    raise SystemExit("unresolved reference for record %d" % record["seq"])


def fold(version, urgency_class):
    major, minor, patch = version
    if urgency_class == "breaking":
        return [major + 1, 0, 0]
    if urgency_class == "additive":
        return [major, minor + 1, 0]
    return [major, minor, patch + 1]


def replay(records, order_key, restricted_rows, superseded, withdrawn, gated, window):
    ordered = sorted(records, key=order_key)
    surface = {}
    retired = []
    deprecations = {}
    version = [0, 0, 0]
    effective = []
    inert = []
    anchors = []
    for record in ordered:
        seq = record["seq"]
        scope = record["scope"]
        op = record["op"]
        if seq in withdrawn:
            inert.append({"seq": seq, "reason": "rolled_back"})
            continue
        if seq in gated:
            inert.append({"seq": seq, "reason": "apply_change_rejected"})
            continue
        reason = None
        if op == "publish":
            if scope in surface or scope in retired:
                reason = "publish_names_known_scope"
            else:
                surface[scope] = resolve_value(record, restricted_rows, superseded)
        elif op == "revise":
            if scope not in surface:
                reason = "revise_names_inactive_scope"
            else:
                value = resolve_value(record, restricted_rows, superseded)
                if value == surface[scope]:
                    reason = "revise_keeps_value"
                else:
                    surface[scope] = value
        elif op == "deprecate":
            if scope not in surface:
                reason = "deprecate_names_inactive_scope"
            else:
                deprecations.setdefault(scope, []).append(
                    (record["authority_rank"], record["effective_generation"])
                )
        elif op == "restore":
            stack = deprecations.get(scope) or []
            if scope not in surface or not stack:
                reason = "restore_without_open_deprecation"
            elif record["authority_rank"] < stack[-1][0]:
                reason = "restore_rank_below_deprecation"
            else:
                stack.pop()
        elif op == "withdraw":
            if scope not in surface:
                reason = "withdraw_names_inactive_scope"
            else:
                del surface[scope]
                retired.append(scope)
                deprecations.pop(scope, None)
        if reason is not None:
            inert.append({"seq": seq, "reason": reason})
            continue
        version = fold(version, record["urgency_class"])
        effective.append(record)
        if record["reference_domain"] == "restricted_scope_index":
            anchors.append(
                {
                    "seq": seq,
                    "scope": scope,
                    "lineage_anchor": settled_anchor(record, superseded),
                    "canonical_value": surface[scope],
                }
            )
    generation = max(record["effective_generation"] for record in records)
    expired = []
    for scope, stack in deprecations.items():
        if scope in surface and stack and generation - stack[-1][1] >= window:
            expired.append((stack[-1][1], scope))
    for _, scope in sorted(expired):
        del surface[scope]
        retired.append(scope)
    return {
        "surface": surface,
        "retired": retired,
        "version": version,
        "effective": effective,
        "inert": sorted(inert, key=lambda item: item["seq"]),
        "anchors": anchors,
        "generation": generation,
    }


def build(input_dir):
    root = Path(input_dir)
    ledger = read_ledger(root)
    journal = read_journal(root)
    restricted_rows = read_restricted_rows(root)
    catalogue = json.loads((root / CATALOGUE).read_text(encoding="utf-8-sig"))
    controls = read_calibration(root)
    published = governing_window(root)
    window = recover_window(controls) if published is None else published
    weights = recover_weights(controls)
    classes = sorted(entry["name"] for entry in catalogue["classes"])
    if classes != sorted(CLASS_ORDER):
        raise SystemExit("the catalogue publishes urgency classes this recovery does not know: %s" % classes)

    superseded, withdrawn, gated = journal_view(journal)

    def authority_key(record):
        return (record["effective_generation"], record["seq"])

    def control_key(record):
        return (record["seq"],)

    authority = replay(
        ledger, authority_key, restricted_rows, superseded, withdrawn, gated, window
    )
    control = replay(
        ledger, control_key, restricted_rows, superseded, withdrawn, gated, window
    )

    surface = dict(sorted(authority["surface"].items()))
    control_surface = dict(sorted(control["surface"].items()))
    first_divergent = None
    ordered_authority = sorted(ledger, key=authority_key)
    ordered_control = sorted(ledger, key=control_key)
    for left, right in zip(ordered_authority, ordered_control):
        if left["seq"] != right["seq"]:
            first_divergent = left["seq"]
            break
    return {
        "surface": surface,
        "control_surface": control_surface,
        "surface_digest": digest(surface),
        "control_digest": digest(control_surface),
        "generation": authority["generation"],
        "release_version": ".".join(str(part) for part in authority["version"]),
        "control_release_version": ".".join(str(part) for part in control["version"]),
        "retired": authority["retired"],
        "control_retired": control["retired"],
        "effective_record_count": len(authority["effective"]),
        "inert_records": authority["inert"],
        "first_divergent_seq": first_divergent,
        "transitions": [
            "seq:%d:%s:%s" % (record["seq"], record["scope"], record["op"])
            for record in authority["effective"]
        ],
        "revisited_anchors": authority["anchors"],
        "ledger_classes": [r["urgency_class"] for r in ledger],
        "deprecation_window": window,
        "urgency_weights": weights,
        "rank_total_order": [
            name
            for name, _ in sorted(surface.items(), key=lambda kv: (-kv[1], kv[0]))
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    state = build(args.input)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "surface_digest": state["surface_digest"],
        "generation": state["generation"],
        "release_version": state["release_version"],
        "control_digest": state["control_digest"],
        "active_scopes": state["surface"],
        "retired_scopes": state["retired"],
        "deprecation_window": state["deprecation_window"],
        "urgency_weights": state["urgency_weights"],
    }
    (out / "reproduced_state.json").write_text(
        json.dumps(payload, indent=2) + "\\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
'''


def weighted_totals(ledger_classes, weights):
    """Addendum A2.2: per class, the sum of the recovered class weight over every ledger record."""
    return {name: sum(weights[name] for cls in ledger_classes if cls == name) for name in sorted(weights)}


def load_reproducer():
    namespace = {"__name__": "reproduce_scopes"}
    exec(compile(REPRODUCER_SOURCE, "reproduce_scopes.py", "exec"), namespace)
    return namespace


def write_json(path, payload):
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    reproducer = load_reproducer()
    state = reproducer["build"](str(DATA))

    snapshot = json.loads((DATA / "generated_scope_snapshot.json").read_text(encoding="utf-8"))
    stale = snapshot["active_scopes"]
    surface = state["surface"]
    divergent = sorted(name for name in surface if stale.get(name) != surface[name])

    script_path = OUT / "reproduce_scopes.py"
    script_path.write_text(REPRODUCER_SOURCE, encoding="utf-8")
    os.chmod(script_path, 0o755)

    write_json(
        OUT / "scope_surface_core.json",
        {
            "generation": state["generation"],
            "release_version": state["release_version"],
            "active_scopes": surface,
            "retired_scopes": state["retired"],
        },
    )
    write_json(
        OUT / "reconciliation_summary.json",
        {
            "authority_source": "ledger/",
            "authority_ordering_key": "effective_generation,seq",
            "control_ordering_key": "seq",
            "effective_record_count": state["effective_record_count"],
        },
    )
    write_json(
        OUT / "urgency_metrics.json",
        {
            "surface_digest": state["surface_digest"],
            "urgency_totals": weighted_totals(state["ledger_classes"], state["urgency_weights"]),
        },
    )
    write_json(
        OUT / "authority_verdict.json",
        {
            "layers_compared": [
                "coverage_gate_report.json",
                "assistant_runtime_state.json",
                "household_index.json",
                "generated_scope_snapshot.json",
            ],
            "authority_anchored": True,
            "pre_repair_divergence_count": len(divergent),
            "post_repair_divergence_count": 0,
        },
    )
    write_json(
        OUT / "resolution_trace.json",
        {
            "transitions": state["transitions"],
            "revisited_anchors": state["revisited_anchors"],
            "inert_records": state["inert_records"],
        },
    )
    write_json(
        OUT / "root_cause_report.json",
        {
            "root_cause": {
                "layer": "generated_scope_snapshot.json",
                "observed_ordering_key": "seq",
            },
            "rejected_hypothesis": {
                "name": "journal_backlog",
                "falsified_by": "control_replay_digest_matches_snapshot",
            },
            "minimal_delta": [
                {
                    "scope": name,
                    "snapshot_value": stale[name],
                    "authority_value": surface[name],
                }
                for name in divergent
            ],
        },
    )
    write_json(
        OUT / "control_replay.json",
        {
            "control_digest": state["control_digest"],
            "first_divergent_seq": state["first_divergent_seq"],
        },
    )

    write_json(
        OUT / "rank_order.json",
        {
            "rank_total_order": state["rank_total_order"],
        },
    )

    result = subprocess.run(
        [sys.executable, str(script_path), "--input", str(DATA), "--out", str(OUT)],
        capture_output=True,
        text=True,
        timeout=180,
    )
    if result.returncode != 0:
        sys.exit("delivered reproducer failed: " + result.stderr.strip()[:400])

    reproduced = json.loads((OUT / "reproduced_state.json").read_text(encoding="utf-8"))
    if reproduced["surface_digest"] != state["surface_digest"]:
        sys.exit("delivered reproducer disagrees with the recovery on the surface digest")
    if reproduced["control_digest"] == reproduced["surface_digest"]:
        sys.exit("control digest reproduced the surface digest, which is a reporting fault")
    if reproduced["control_digest"] != snapshot["surface_digest"]:
        sys.exit("control replay did not reproduce the digest stamped on the generated snapshot")

    print("[verify] surface digest      %s" % state["surface_digest"])
    print("[verify] control digest      %s" % state["control_digest"])
    print("[verify] snapshot digest     %s" % snapshot["surface_digest"])
    print("[verify] generation          %d" % state["generation"])
    print("[verify] household version     %s" % state["release_version"])
    print("[verify] effective records   %d" % state["effective_record_count"])
    print("[verify] divergent scopes   %s" % ", ".join(divergent))
    print("[verify] modules used        reproducer: argparse, csv, hashlib, io, json, re, pathlib, sqlite3, xml.etree.ElementTree, zipfile; recovery: json, os, pathlib, subprocess, sys")


if __name__ == "__main__":
    main()
