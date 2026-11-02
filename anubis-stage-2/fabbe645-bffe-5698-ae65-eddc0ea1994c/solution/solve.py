#!/usr/bin/env python3
"""Replica retention and tape packing planner for the KCBA archive desk.

Usage:
    python3 optimize.py --data <input folder> --out <output folder> [--prior <earlier output folder>]

Every rule value (class minimums, amendment windows, thresholds, encodings, label width,
reserves and so on) is read from the documents in the input folder on each run. The input
folder and the prior folder are only read. Output depends on file contents only.
"""

import argparse
import base64
import configparser
import csv
import datetime
import hashlib
import io
import json
import os
import re
import sqlite3
import struct
import sys
import tomllib
import xml.etree.ElementTree as ET
import zipfile

VAULT_CODES = ("KLH", "MRG", "NSK", "RTN")
CENSUS_NAME = "estate_census.toml"
RUN_CONTROL = "run_control.json"
MRG_NS = "{urn:kcba:margao:inventory:2}"
RIGHTS_NS = "{urn:kcba:rights:1}"
XLSX_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKG_REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
IST_OFFSET_MINUTES = 5 * 60 + 30


class RuleError(Exception):
    """A rule document does not contain the value the planner needs."""


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------

def read_bytes(folder, name):
    with open(os.path.join(folder, name), "rb") as handle:
        return handle.read()


def read_text(folder, name):
    return read_bytes(folder, name).decode("utf-8")


def parse_day(text):
    return datetime.date.fromisoformat(text.strip())


def find_one(pattern, text, what):
    match = re.search(pattern, text, re.S)
    if match is None:
        raise RuleError("cannot find %s" % what)
    return match


def shard_number(name):
    return int(re.search(r"_(\d+)\.", name).group(1))


def ceil_div(numerator, denominator):
    return -(-numerator // denominator)


def round_half_even(numerator, denominator):
    quotient, remainder = divmod(numerator, denominator)
    twice = 2 * remainder
    if twice > denominator or (twice == denominator and quotient % 2 == 1):
        quotient += 1
    return quotient


def write_json(folder, name, payload):
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    with open(os.path.join(folder, name), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


# --------------------------------------------------------------------------
# census
# --------------------------------------------------------------------------

def count_records(name, data):
    """Record count by the counting table of the desk brief."""
    if name.endswith(".csv"):
        return max(0, len(list(csv.reader(io.StringIO(data.decode("utf-8"))))) - 1)
    if name.endswith(".xml") and name.startswith("margao_inventory_"):
        root = ET.fromstring(data)
        return sum(1 for _ in root.iter(MRG_NS + "obj"))
    if name.endswith(".jsonl") or name.endswith(".dat"):
        return sum(1 for line in data.decode("utf-8").split("\n") if line.strip())
    if name.endswith(".idx"):
        return max(0, (len(data) - 12) // 44)
    if name.endswith(".psv") or name.endswith(".tsv"):
        lines = [line for line in data.decode("utf-8").split("\n") if line.strip()]
        return max(0, len(lines) - 1)
    return None


def reconcile_census(data_dir):
    """Return (reasons, entries) for the census of data_dir."""
    census_path = os.path.join(data_dir, CENSUS_NAME)
    if not os.path.isfile(census_path):
        return ["MISSING:" + CENSUS_NAME], []
    listing = tomllib.loads(read_text(data_dir, CENSUS_NAME))
    reasons = []
    entries = []
    for item in listing.get("file", []):
        name = item["name"]
        expected_records = item.get("records")
        entry = {"file": name, "present": False, "bytes_ok": False, "sha256_ok": False,
                 "records_expected": expected_records, "records_seen": None}
        if not os.path.isfile(os.path.join(data_dir, name)):
            reasons.append("MISSING:" + name)
            entries.append(entry)
            continue
        data = read_bytes(data_dir, name)
        entry["present"] = True
        entry["bytes_ok"] = len(data) == item["bytes"]
        entry["sha256_ok"] = hashlib.sha256(data).hexdigest() == item["sha256"]
        if not entry["bytes_ok"]:
            reasons.append("SIZE:" + name)
        if not entry["sha256_ok"]:
            reasons.append("SHA256:" + name)
        if expected_records is not None:
            try:
                entry["records_seen"] = count_records(name, data)
            except (ValueError, ET.ParseError, UnicodeDecodeError):
                entry["records_seen"] = None
            if entry["records_seen"] != expected_records:
                reasons.append("RECORDS:" + name)
        entries.append(entry)
    entries.sort(key=lambda e: e["file"])
    return sorted(reasons), entries


# --------------------------------------------------------------------------
# rule documents
# --------------------------------------------------------------------------

def read_xlsx_sheet(data, sheet_title):
    """Rows of one sheet of a plain xlsx workbook as lists of str or int."""
    with zipfile.ZipFile(io.BytesIO(data)) as book:
        shared = []
        if "xl/sharedStrings.xml" in book.namelist():
            for item in ET.fromstring(book.read("xl/sharedStrings.xml")).iter(XLSX_NS + "si"):
                shared.append("".join(t.text or "" for t in item.iter(XLSX_NS + "t")))
        workbook = ET.fromstring(book.read("xl/workbook.xml"))
        rels = ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
        targets = {rel.get("Id"): rel.get("Target") for rel in rels.iter(PKG_REL_NS + "Relationship")}
        target = None
        for sheet in workbook.iter(XLSX_NS + "sheet"):
            if sheet.get("name") == sheet_title:
                target = targets[sheet.get(REL_NS + "id")]
        if target is None:
            raise RuleError("sheet %s not in workbook" % sheet_title)
        sheet_xml = ET.fromstring(book.read("xl/" + target.lstrip("/").replace("xl/", "", 1)))
    rows = []
    for row in sheet_xml.iter(XLSX_NS + "row"):
        values = []
        for cell in row.iter(XLSX_NS + "c"):
            raw = cell.find(XLSX_NS + "v")
            text = raw.text if raw is not None else ""
            values.append(shared[int(text)] if cell.get("t") == "s" else int(text))
        rows.append(values)
    return rows


def load_rules(data_dir):
    """Collect every seed dependent rule value from the documents."""
    rules = {}

    charter = read_text(data_dir, "retention_charter.md")
    rules["class_min"] = {cls: int(num) for cls, num in
                          re.findall(r"^\|\s*(R\d)\s*\|\s*(\d+)\s*\|\s*$", charter, re.M)}

    first = read_text(data_dir, "charter_amendment_01.md")
    window = find_one(r"from (\d{4}-\d\d-\d\d) up to but excluding (\d{4}-\d\d-\d\d)", first,
                      "amendment 01 window")
    rules["r2_window"] = (parse_day(window.group(1)), parse_day(window.group(2)))
    rules["r2_commercial_min"] = int(find_one(r"R2 commercial collection is (\d+)", first,
                                              "amendment 01 minimum").group(1))

    second = read_text(data_dir, "charter_amendment_02.md")
    rules["rights_from"] = parse_day(find_one(r"From (\d{4}-\d\d-\d\d) the rights register", second,
                                              "amendment 02 date").group(1))

    third = read_text(data_dir, "charter_amendment_03.md")
    rules["split_from"] = parse_day(find_one(r"From (\d{4}-\d\d-\d\d) class R3 is replaced", third,
                                             "amendment 03 date").group(1))
    older = find_one(r"\|\s*R3A\s*\|[^|]*earlier than (\d{4})\s*\|\s*(\d+)\s*\|", third, "R3A row")
    newer = find_one(r"\|\s*R3B\s*\|[^|]*\|\s*(\d+)\s*\|", third, "R3B row")
    rules["split_year"] = int(older.group(1))
    rules["class_min"]["R3A"] = int(older.group(2))
    rules["class_min"]["R3B"] = int(newer.group(1))

    layout = read_text(data_dir, "volume_layout.md")
    rules["header_bytes"] = int(find_one(r"a header of (\d+) bytes", layout, "tape header").group(1))

    margao = read_text(data_dir, "margao_export_readme.md")
    rules["digest_codes"] = {}
    for code, kind in re.findall(r"^\|\s*`(\w+)`\s*\|\s*(standard Base64|Base32)", margao, re.M):
        rules["digest_codes"][code] = "b64" if kind.startswith("standard") else "b32"

    kolhapur = read_text(data_dir, "kolhapur_index_format.md")
    endian = find_one(r"unsigned and (little|big) endian", kolhapur, "index byte order").group(1)
    rules["index_order"] = "<" if endian == "little" else ">"

    tape_notes = read_text(data_dir, "kolhapur_tape_notes.txt")
    rules["rendition_letters"] = {letter: kind for letter, kind in
                                  re.findall(r"^\s+([A-Z]) = (master|mezzanine|proxy)\s*$", tape_notes, re.M)}

    changelog = read_text(data_dir, "ratnagiri_changelog.md")
    drift = find_one(r"starting with shard file `ratnagiri_objects_(\d+)\.jsonl`.*?as key `(\w+)`",
                     changelog, "Ratnagiri size change")
    rules["hex_from_shard"] = int(drift.group(1))
    rules["hex_size_key"] = drift.group(2)

    handbook = read_text(data_dir, "ops_handbook_2021.md")
    rules["label_digits"] = int(find_one(r"leading zeros to exactly (\d+) digits", handbook,
                                         "label width").group(1))

    sidecar = read_text(data_dir, "sidecar_policy_note.md")
    rules["sidecar_below"] = int(find_one(r"strictly below (\d+) bytes", sidecar, "sidecar threshold").group(1))

    faq = read_text(data_dir, "legal_hold_faq.md")
    tie_text = find_one(r"\*\*Q3\..*?\*\*\s*(.*?)\n\s*\n", faq, "hold order answer").group(1)
    rules["place_last_on_tie"] = "PLACE` comes after" in tie_text

    audit = read_text(data_dir, "nashik_audit_2024.html")
    rules["void_node"] = None
    for cells in re.findall(r"<tr>(.*?)</tr>", audit, re.S):
        values = [re.sub(r"<[^>]+>", "", c).strip() for c in re.findall(r"<td>(.*?)</td>", cells, re.S)]
        if len(values) == 4 and values[2].lower() == "decommissioned":
            rules["void_node"] = (values[0], parse_day(values[3]))

    with open(os.path.join(data_dir, "retention_schedule_2019.csv"), newline="", encoding="utf-8") as handle:
        rules["preference"] = {row["class"]: row["vault_preference"].split(">")
                               for row in csv.DictReader(handle)}

    reserve_rows = read_xlsx_sheet(read_bytes(data_dir, "capacity_planning_2022.xlsx"), "Reserve")
    head = reserve_rows[0]
    rules["reserve"] = {row[head.index("cartridge")]: row[head.index("reserve_bytes")]
                        for row in reserve_rows[1:]}

    media = json.loads(read_text(data_dir, "media_catalogue.json"))
    native = {item["type"]: item["native_capacity_bytes"] for item in media["media"]}
    rules["native"] = native

    profiles = configparser.ConfigParser()
    profiles.read_string(read_text(data_dir, "vault_profiles.ini"))
    rules["block"] = {}
    rules["usable"] = {}
    for section in profiles.sections():
        code = profiles[section]["code"].strip().upper()
        cartridge = profiles[section]["cartridge"].strip()
        rules["block"][code] = int(profiles[section]["block_size"])
        rules["usable"][code] = native[cartridge] - rules["reserve"][cartridge]
    return rules


def load_registers(data_dir):
    """Catalogue, rights, crosswalk and holds."""
    registers = {}
    # The catalogue is loaded into memory so the run writes nothing outside --out.
    connection = sqlite3.connect(":memory:")
    try:
        connection.deserialize(read_bytes(data_dir, "catalogue.db"))
        registers["collections"] = {
            cid: {"segment": segment, "class": cls, "year": int(year)}
            for cid, segment, cls, year in connection.execute(
                "SELECT collection_id, segment, retention_class, ingest_year FROM collection")}
    finally:
        connection.close()

    licences = {}
    for node in ET.fromstring(read_bytes(data_dir, "rights_register.xml")).iter(RIGHTS_NS + "licence"):
        licences.setdefault(node.get("collection"), []).append(
            (parse_day(node.get("from")), parse_day(node.get("to")), node.get("class_override")))
    registers["licences"] = licences

    crosswalk = {}
    with open(os.path.join(data_dir, "collection_crosswalk.tsv"), newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            crosswalk.setdefault(row["legacy_id"], []).append(
                (parse_day(row["effective_from"]), row["collection_id"]))
    registers["crosswalk"] = {key: sorted(value) for key, value in crosswalk.items()}

    holds = {}
    with open(os.path.join(data_dir, "legal_holds.psv"), newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle, delimiter="|"):
            holds.setdefault(row["collection"], []).append(
                (ist_date(row["effective"]), row["action"], int(row["event_id"].split("-")[1])))
    registers["holds"] = holds
    return registers


def ist_date(stamp):
    """Calendar date of a time stamp in Indian Standard Time."""
    text = stamp.strip()
    if text.endswith("Z"):
        moment = datetime.datetime.fromisoformat(text[:-1]).replace(tzinfo=datetime.timezone.utc)
    else:
        moment = datetime.datetime.fromisoformat(text)
    ist = datetime.timezone(datetime.timedelta(minutes=IST_OFFSET_MINUTES))
    return moment.astimezone(ist).date()


# --------------------------------------------------------------------------
# vault exports
# --------------------------------------------------------------------------

def export_files(data_dir, prefix, suffix):
    names = [n for n in os.listdir(data_dir) if n.startswith(prefix) and n.endswith(suffix)]
    return sorted(names, key=shard_number)


def nashik_rows(data_dir):
    for name in export_files(data_dir, "nashik_manifest_", ".csv"):
        with open(os.path.join(data_dir, name), newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                yield {"vault": "NSK", "file": name, "path": row["object_path"], "bytes": int(row["bytes"]),
                       "digest": row["sha256"].strip().lower(), "collection": row["collection"],
                       "legacy": False, "rendition": row["rendition"].strip().lower(),
                       "node": row["node"].strip()}


def decode_digest(text, encoding):
    text = text.strip()
    if encoding == "b32":
        raw = base64.b32decode(text + "=" * (-len(text) % 8))
    elif encoding == "b64":
        raw = base64.b64decode(text, validate=True)
    else:
        raise RuleError("unknown digest encoding")
    return raw.hex()


def margao_rows(data_dir, rules, registers):
    for name in export_files(data_dir, "margao_inventory_", ".xml"):
        root = ET.fromstring(read_bytes(data_dir, name))
        for node in root.iter(MRG_NS + "obj"):
            digest_node = node.find(MRG_NS + "digest")
            encoding = rules["digest_codes"].get(digest_node.get("enc"))
            collection = node.get("coll")
            legacy = collection.startswith("KCB-")
            if legacy:
                collection = resolve_legacy(collection, parse_day(node.get("catalogued")), registers)
            yield {"vault": "MRG", "file": name, "path": node.get("path"), "bytes": int(node.get("size")),
                   "digest": decode_digest(digest_node.text, encoding), "collection": collection,
                   "legacy": legacy, "rendition": node.get("form").strip().lower(), "node": None}


def resolve_legacy(legacy_id, catalogued, registers):
    """Crosswalk row with the latest effective_from on or before the catalogued date."""
    chosen = None
    for effective_from, collection in registers["crosswalk"][legacy_id]:
        if effective_from <= catalogued:
            chosen = collection
    if chosen is None:
        raise RuleError("legacy id %s has no row in force" % legacy_id)
    return chosen


def ratnagiri_rows(data_dir, rules):
    for name in export_files(data_dir, "ratnagiri_objects_", ".jsonl"):
        hex_sizes = shard_number(name) >= rules["hex_from_shard"]
        for line in read_text(data_dir, name).split("\n"):
            if not line.strip():
                continue
            record = json.loads(line)
            size = int(record[rules["hex_size_key"]], 16) if hex_sizes else int(record["len"])
            digest = record["dg"].split(":", 1)[1].lower()
            yield {"vault": "RTN", "file": name, "path": record["p"], "bytes": size, "digest": digest,
                   "collection": record["col"], "legacy": False, "rendition": record["kind"].lower(),
                   "node": None}


def kolhapur_rows(data_dir, rules):
    order = rules["index_order"]
    for name in export_files(data_dir, "kolhapur_catalogue_", ".dat"):
        index_name = "kolhapur_index_%02d.idx" % shard_number(name)
        blob = read_bytes(data_dir, index_name)
        if blob[:6] != b"KLHIDX":
            raise RuleError("bad index magic in %s" % index_name)
        _version, count = struct.unpack(order + "HI", blob[6:12])
        exact = {}
        for position in range(count):
            start = 12 + 44 * position
            seq, size = struct.unpack(order + "IQ", blob[start:start + 12])
            exact[seq] = (size, blob[start + 12:start + 44].hex())
        for line in read_text(data_dir, name).split("\n"):
            if not line.strip():
                continue
            seq = int(line[72:79])
            size, digest = exact[seq]
            yield {"vault": "KLH", "file": name, "path": line[0:72].rstrip(), "bytes": size,
                   "digest": digest, "collection": line[90:100].strip(), "legacy": False,
                   "rendition": rules["rendition_letters"][line[100]], "node": None}


def load_rows(data_dir, rules, registers):
    rows = []
    rows.extend(kolhapur_rows(data_dir, rules))
    rows.extend(margao_rows(data_dir, rules, registers))
    rows.extend(nashik_rows(data_dir))
    rows.extend(ratnagiri_rows(data_dir, rules))
    return rows


# --------------------------------------------------------------------------
# retention rules
# --------------------------------------------------------------------------

def collection_class(collection_id, as_of, rules, registers):
    """Settled class and master minimum of one collection on as_of."""
    info = registers["collections"][collection_id]
    cls = info["class"]
    if info["segment"] == "commercial" and as_of >= rules["rights_from"]:
        for start, end, override in registers["licences"].get(collection_id, []):
            if start <= as_of <= end:
                cls = override
    if cls == "R3" and as_of >= rules["split_from"]:
        cls = "R3A" if info["year"] < rules["split_year"] else "R3B"
    minimum = rules["class_min"][cls]
    start, end = rules["r2_window"]
    if cls == "R2" and info["segment"] == "commercial" and start <= as_of < end:
        minimum = rules["r2_commercial_min"]
    return cls, minimum


def vaults_needed(minimum, rendition):
    if rendition == "proxy":
        return 1
    if rendition == "mezzanine":
        return max(1, minimum - 1)
    return minimum


def under_hold(collection_id, as_of, rules, registers):
    latest = None
    for day, action, number in registers["holds"].get(collection_id, []):
        if day > as_of:
            continue
        rank = 1 if (rules["place_last_on_tie"] and action == "PLACE") else 0
        key = (day, rank, number)
        if latest is None or key > latest[0]:
            latest = (key, action)
    return latest is not None and latest[1] == "PLACE"


def preference_for(cls, rules):
    return rules["preference"]["R3" if cls in ("R3A", "R3B") else cls]


# --------------------------------------------------------------------------
# packing
# --------------------------------------------------------------------------

def tape_footprint(size, vault, rules):
    block = rules["block"][vault]
    return rules["header_bytes"] + ceil_div(size, block) * block


def volume_label(vault, number, rules):
    return "%s-%s" % (vault, str(number).zfill(rules["label_digits"]))


def label_number(label):
    match = re.search(r"(\d+)$", label)
    return int(match.group(1)) if match else 0


def describe_volume(label, vault, members, usable):
    used = sum(size for _path, size in members)
    return {"label": label, "vault": vault, "usable_bytes": usable, "used_bytes": used,
            "fill_bps": round_half_even(used * 10000, usable), "members": members}


def first_fit_decreasing(entries, usable):
    """entries: (path, footprint, digest). Returns member lists in opening order."""
    ordered = sorted(entries, key=lambda e: (-e[1], e[2], e[0].encode("utf-8")))
    bins = []
    for path, size, _digest in ordered:
        for members in bins:
            if members[0] + size <= usable:
                members[0] += size
                members[1].append([path, size])
                break
        else:
            bins.append([size, [[path, size]]])
    return [members for _used, members in bins]


def pack_one_vault(vault, entries, rules, earlier):
    usable = rules["usable"][vault]
    remaining = {entry[0]: entry for entry in entries}
    volumes = []
    next_number = 1
    if earlier:
        next_number = max(label_number(v["label"]) for v in earlier) + 1
        for volume in earlier:
            paths = [member[0] for member in volume["members"]]
            if paths and len(set(paths)) == len(paths) and all(p in remaining for p in paths):
                members = [[p, remaining[p][1]] for p in paths]
                volumes.append(describe_volume(volume["label"], vault, members, usable))
                for p in paths:
                    del remaining[p]
    for members in first_fit_decreasing(list(remaining.values()), usable):
        volumes.append(describe_volume(volume_label(vault, next_number, rules), vault, members, usable))
        next_number += 1
    return volumes


# --------------------------------------------------------------------------
# planning
# --------------------------------------------------------------------------

def group_objects(rows, rules):
    objects = {}
    for row in rows:
        if row["bytes"] < rules["sidecar_below"]:
            continue
        objects.setdefault(row["digest"], []).append(row)
    return objects


def plan_scenario(name, as_of, objects, rules, registers, plan_id, earlier):
    void = rules["void_node"]
    object_list = []
    replica_list = []
    void_count = 0
    for digest in sorted(objects):
        rows = []
        for row in objects[digest]:
            if row["vault"] == "NSK" and void is not None and row["node"] == void[0] and as_of >= void[1]:
                void_count += 1
                continue
            rows.append(row)
        if not rows:
            continue
        rendition = rows[0]["rendition"]
        collections = sorted({row["collection"] for row in rows})
        required, governing_class = 0, None
        for collection_id in collections:
            cls, minimum = collection_class(collection_id, as_of, rules, registers)
            need = vaults_needed(minimum, rendition)
            if governing_class is None or need > required:
                required, governing_class = need, cls
        held = any(under_hold(c, as_of, rules, registers) for c in collections)
        primary = {}
        for row in sorted(rows, key=lambda r: r["path"].encode("utf-8")):
            primary.setdefault(row["vault"], row)
        if held:
            keep = {id(row) for row in rows}
        else:
            chosen = [v for v in preference_for(governing_class, rules) if v in primary][:required]
            keep = {id(primary[v]) for v in chosen}
        object_list.append({
            "digest": digest, "rendition": rendition, "collections": collections,
            "class": governing_class, "required": required, "held": held,
            "under_replicated": len(primary) < required,
            "kept_vaults": sorted({row["vault"] for row in rows if id(row) in keep})})
        for row in rows:
            replica_list.append({"vault": row["vault"], "path": row["path"], "digest": digest,
                                 "bytes": row["bytes"], "collection": row["collection"],
                                 "rendition": rendition, "keep": id(row) in keep})
    replica_list.sort(key=lambda r: (r["vault"], r["path"].encode("utf-8")))
    volumes = []
    for vault in VAULT_CODES:
        entries = [(r["path"], tape_footprint(r["bytes"], vault, rules), r["digest"])
                   for r in replica_list if r["vault"] == vault and r["keep"]]
        prior_volumes = None
        if earlier is not None:
            prior_volumes = [v for v in earlier if v.get("vault") == vault]
        volumes.extend(pack_one_vault(vault, entries, rules, prior_volumes))
    document = {"plan_id": plan_id, "scenario": name, "as_of": as_of.isoformat(),
                "objects": object_list, "replicas": replica_list, "volumes": volumes}
    return document, void_count


def file_quality(rows, rules):
    """Per export file counts for data_quality.json."""
    primary = {}
    for row in sorted(rows, key=lambda r: r["path"].encode("utf-8")):
        primary.setdefault((row["digest"], row["vault"]), row)
    quality = {}
    for row in rows:
        counts = quality.setdefault(row["file"], {"rows": 0, "sidecar_rows": 0,
                                                  "legacy_collection_rows": 0, "duplicate_rows": 0})
        counts["rows"] += 1
        if row["legacy"]:
            counts["legacy_collection_rows"] += 1
        if row["bytes"] < rules["sidecar_below"]:
            counts["sidecar_rows"] += 1
        elif primary[(row["digest"], row["vault"])] is not row:
            counts["duplicate_rows"] += 1
    return {name: quality[name] for name in sorted(quality)}


def read_prior(prior_dir, scenario_name):
    if prior_dir is None:
        return None
    path = os.path.join(prior_dir, "scenario_%s.json" % scenario_name)
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle).get("volumes", [])


def read_plan_header(data_dir):
    try:
        control = json.loads(read_text(data_dir, RUN_CONTROL))
        scenarios = {name: parse_day(entry["as_of"]) for name, entry in control["scenarios"].items()}
        return control["plan_id"], scenarios
    except (OSError, ValueError, KeyError, TypeError):
        return None, None


def run(data_dir, out_dir, prior_dir):
    os.makedirs(out_dir, exist_ok=True)
    plan_id, scenarios = read_plan_header(data_dir)
    reasons, census = reconcile_census(data_dir)
    report = {"plan_id": plan_id, "status": "HELD", "reasons": reasons, "census": census, "scenarios": []}
    if reasons or scenarios is None:
        write_json(out_dir, "perf_report.json", report)
        return 1

    rules = load_rules(data_dir)
    registers = load_registers(data_dir)
    rows = load_rows(data_dir, rules, registers)
    objects = group_objects(rows, rules)

    summaries, bottleneck, recommendations, void_rows = [], {}, {}, {}
    for name, as_of in sorted(scenarios.items(), key=lambda item: (item[1], item[0])):
        document, void_rows[name] = plan_scenario(name, as_of, objects, rules, registers, plan_id,
                                                  read_prior(prior_dir, name))
        write_json(out_dir, "scenario_%s.json" % name, document)
        kept = [r for r in document["replicas"] if r["keep"]]
        released = [r for r in document["replicas"] if not r["keep"]]
        summaries.append({"name": name, "as_of": as_of.isoformat(), "objects": len(document["objects"]),
                          "kept_replicas": len(kept), "released_replicas": len(released),
                          "volumes": len(document["volumes"])})
        per_vault = {}
        for vault in VAULT_CODES:
            vault_volumes = [v for v in document["volumes"] if v["vault"] == vault]
            per_vault[vault] = {"volumes": len(vault_volumes),
                                "used_bytes": sum(v["used_bytes"] for v in vault_volumes),
                                "kept_replicas": sum(1 for r in kept if r["vault"] == vault)}
        bottleneck[name] = {
            "under_replicated_objects": sum(1 for o in document["objects"] if o["under_replicated"]),
            "held_objects": sum(1 for o in document["objects"] if o["held"]),
            "vaults": per_vault}
        by_vault = {vault: 0 for vault in VAULT_CODES}
        by_segment = {"commercial": 0, "public": 0}
        for replica in released:
            by_vault[replica["vault"]] += replica["bytes"]
            by_segment[registers["collections"][replica["collection"]]["segment"]] += replica["bytes"]
        recommendations[name] = {"release_replicas": len(released), "reclaim_bytes_by_vault": by_vault,
                                 "reclaim_bytes_by_segment": by_segment}

    report["status"] = "PUBLISHED"
    report["scenarios"] = summaries
    report["media_shares"] = {cartridge: round_half_even(rules["reserve"][cartridge] * 10000,
                                                         rules["native"][cartridge])
                              for cartridge in sorted(rules["native"])}
    write_json(out_dir, "bottleneck_analysis.json", {"plan_id": plan_id, "scenarios": bottleneck})
    write_json(out_dir, "recommendations.json", {"plan_id": plan_id, "scenarios": recommendations})
    write_json(out_dir, "data_quality.json", {"plan_id": plan_id, "files": file_quality(rows, rules),
                                              "void_node_rows": void_rows})
    write_json(out_dir, "perf_report.json", report)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="KCBA replica retention and tape packing planner")
    parser.add_argument("--data", required=True, help="input folder with the cycle export")
    parser.add_argument("--out", required=True, help="folder to write the plan into")
    parser.add_argument("--prior", default=None, help="output folder of an earlier run")
    args = parser.parse_args(argv)
    run(args.data, args.out, args.prior)
    return 0


if __name__ == "__main__":
    sys.exit(main())
