#!/usr/bin/env python3
"""KCBA replica retention and tape packing planner.

Reads a planning-cycle export folder, decides which replicas to keep for every
scenario in run_control.json, packs the kept replicas onto tape volumes and
writes the plan files described in plan_output_contract.md.

All cycle specific values (dates, thresholds, capacities, classes, scenario
names, file lists) are read from the export; nothing of one cycle is baked in.
"""

from __future__ import annotations

import argparse
import base64
import csv
import datetime as dt
import hashlib
import json
import os
import re
import sqlite3
import struct
import sys
import tomllib
import zipfile
from configparser import ConfigParser
from html.parser import HTMLParser
from xml.etree import ElementTree as ET

CENSUS_FILE = "estate_census.toml"
RUN_CONTROL = "run_control.json"


class PlanError(Exception):
    pass


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------

def round_half_even(num: int, den: int) -> int:
    """num/den rounded to the nearest integer, exact halves to the even side."""
    if den == 0:
        return 0
    neg = (num < 0) != (den < 0)
    num, den = abs(num), abs(den)
    q, r = divmod(num, den)
    twice = 2 * r
    if twice > den or (twice == den and q % 2 == 1):
        q += 1
    return -q if neg else q


def parse_date(text: str) -> dt.date:
    return dt.date.fromisoformat(text.strip())


def read_bytes(path: str) -> bytes:
    with open(path, "rb") as fh:
        return fh.read()


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def sorted_unique(values) -> list:
    return sorted(set(values))


# --------------------------------------------------------------------------
# census
# --------------------------------------------------------------------------

def count_csv_rows(path: str) -> int:
    with open(path, "r", encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        try:
            next(reader)
        except StopIteration:
            return 0
        return sum(1 for row in reader if row != [])


def count_xml_objects(path: str, local_name: str = "obj") -> int:
    try:
        total = 0
        for _event, elem in ET.iterparse(path, events=("end",)):
            if elem.tag.rsplit("}", 1)[-1] == local_name:
                total += 1
            elem.clear()
        return total
    except ET.ParseError:
        data = read_bytes(path).decode("utf-8", "replace")
        return len(re.findall(r"<[A-Za-z0-9_.-]*:?%s[\s/>]" % local_name, data))


def count_nonempty_lines(path: str) -> int:
    data = read_bytes(path).decode("utf-8", "replace")
    return sum(1 for line in data.split("\n") if line.strip() != "")


def count_data_lines(path: str) -> int:
    data = read_bytes(path).decode("utf-8", "replace")
    lines = [line for line in data.split("\n") if line.strip() != ""]
    return max(len(lines) - 1, 0)


def count_index_records(path: str, header: int = 12, record: int = 44) -> int:
    return max(os.path.getsize(path) - header, 0) // record


def record_counter_for(name: str):
    """The record counting rule of the desk brief for one census file."""
    lower = name.lower()
    if lower.endswith(".csv"):
        return count_csv_rows
    if lower.endswith(".xml"):
        return count_xml_objects
    if lower.endswith(".jsonl") or lower.endswith(".dat"):
        return count_nonempty_lines
    if lower.endswith(".idx"):
        return count_index_records
    if lower.endswith(".psv") or lower.endswith(".tsv"):
        return count_data_lines
    return None


def verify_census(data_dir: str):
    """Return (entries, reasons, census_ok)."""
    census_path = os.path.join(data_dir, CENSUS_FILE)
    if not os.path.isfile(census_path):
        return [], ["MISSING:" + CENSUS_FILE], False
    try:
        with open(census_path, "rb") as fh:
            census = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError):
        return [], ["MISSING:" + CENSUS_FILE], False

    entries = []
    reasons = []
    for item in census.get("file", []):
        name = item["name"]
        path = os.path.join(data_dir, name)
        expected = item.get("records")
        if not os.path.isfile(path):
            entries.append({
                "file": name,
                "present": False,
                "bytes_ok": False,
                "sha256_ok": False,
                "records_expected": expected,
                "records_seen": None,
            })
            reasons.append("MISSING:" + name)
            continue

        blob = read_bytes(path)
        bytes_ok = len(blob) == item["bytes"]
        sha_ok = hashlib.sha256(blob).hexdigest() == item["sha256"].strip().lower()
        seen = None
        if expected is not None:
            counter = record_counter_for(name)
            if counter is not None:
                try:
                    seen = counter(path)
                except Exception:
                    seen = None
        entries.append({
            "file": name,
            "present": True,
            "bytes_ok": bytes_ok,
            "sha256_ok": sha_ok,
            "records_expected": expected,
            "records_seen": seen,
        })
        if not bytes_ok:
            reasons.append("SIZE:" + name)
        if not sha_ok:
            reasons.append("SHA256:" + name)
        if expected is not None and seen != expected:
            reasons.append("RECORDS:" + name)

    entries.sort(key=lambda e: e["file"])
    reasons.sort()
    return entries, reasons, not reasons


def census_file_names(data_dir: str) -> list[str]:
    with open(os.path.join(data_dir, CENSUS_FILE), "rb") as fh:
        census = tomllib.load(fh)
    return sorted(item["name"] for item in census.get("file", []))


# --------------------------------------------------------------------------
# rule documents
# --------------------------------------------------------------------------

class _TableParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self._row = None
        self._cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None:
            self._row.append("".join(self._cell).strip())
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def read_reserve_sheet(path: str) -> dict[str, int]:
    """The reserve_bytes column of the Reserve sheet of a xlsx workbook."""
    main = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    rel = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
    pkg = "{http://schemas.openxmlformats.org/package/2006/relationships}"
    with zipfile.ZipFile(path) as book:
        workbook = ET.fromstring(book.read("xl/workbook.xml"))
        rels = ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
        targets = {node.get("Id"): node.get("Target")
                   for node in rels.findall(pkg + "Relationship")}
        shared = []
        if "xl/sharedStrings.xml" in book.namelist():
            sst = ET.fromstring(book.read("xl/sharedStrings.xml"))
            for item in sst.findall(main + "si"):
                shared.append("".join(node.text or ""
                                      for node in item.iter(main + "t")))
        target = None
        for sheet in workbook.iter(main + "sheet"):
            if (sheet.get("name") or "").strip().lower() == "reserve":
                target = targets[sheet.get(rel + "id")]
                break
        if target is None:
            raise PlanError("no Reserve sheet in the capacity workbook")
        if not target.startswith("xl/"):
            target = "xl/" + target.lstrip("/")
        sheet_xml = ET.fromstring(book.read(target))

    table = []
    for row in sheet_xml.iter(main + "row"):
        cells = {}
        for cell in row.findall(main + "c"):
            column = "".join(ch for ch in (cell.get("r") or "") if ch.isalpha())
            value = cell.find(main + "v")
            text = value.text if value is not None else None
            if cell.get("t") == "s" and text is not None:
                text = shared[int(text)]
            cells[column] = text
        table.append(cells)
    if not table:
        raise PlanError("empty Reserve sheet")

    header = {name: column for column, name in table[0].items() if name}
    key_col = header.get("cartridge")
    value_col = header.get("reserve_bytes")
    if key_col is None or value_col is None:
        raise PlanError("Reserve sheet has no cartridge/reserve_bytes columns")
    reserves = {}
    for cells in table[1:]:
        name = cells.get(key_col)
        raw = cells.get(value_col)
        if name is not None and raw is not None:
            reserves[name] = int(float(raw))
    return reserves


class Rules:
    """Every planning constant, read out of the export's own documents."""

    def __init__(self, data_dir: str, names: list[str]):
        self.dir = data_dir
        self.names = names
        self._load_charter()
        self._load_sidecar_threshold()
        self._load_label_format()
        self._load_layout()
        self._load_void_node()
        self._load_schedule()
        self._load_media()
        self._load_vaults()
        self._load_catalogue()
        self._load_crosswalk()
        self._load_holds()
        self._load_rights()
        self._load_amendments()

    def path(self, name: str) -> str:
        return os.path.join(self.dir, name)

    # ---- documents ------------------------------------------------------
    def _load_charter(self):
        text = read_text(self.path("retention_charter.md"))
        self.class_minimum = {}
        for cls, minimum in re.findall(
                r"^\|\s*(R[0-9A-Z]+)\s*\|\s*(\d+)\s*\|\s*$", text, re.M):
            self.class_minimum[cls] = int(minimum)
        if not self.class_minimum:
            raise PlanError("no retention class table in the charter")

    def _load_sidecar_threshold(self):
        text = read_text(self.path("sidecar_policy_note.md"))
        match = re.search(r"strictly below\s+(\d+)\s*bytes", text)
        if not match:
            raise PlanError("no sidecar threshold in the sidecar policy note")
        self.sidecar_threshold = int(match.group(1))

    def _load_label_format(self):
        text = read_text(self.path("ops_handbook_2021.md"))
        match = re.search(r"padded with leading zeros to exactly (\d+) digits", text)
        if not match:
            raise PlanError("no volume label format in the operations handbook")
        self.label_width = int(match.group(1))

    def _load_layout(self):
        text = read_text(self.path("volume_layout.md"))
        match = re.search(r"header of (\d+) bytes", text)
        if not match:
            raise PlanError("no tape object header size in the volume layout")
        self.tape_header = int(match.group(1))

    def _load_void_node(self):
        parser = _TableParser()
        parser.feed(read_text(self.path("nashik_audit_2024.html")))
        self.void_node = None
        self.void_date = None
        for row in parser.rows:
            if len(row) >= 4 and "decommission" in row[2].lower():
                self.void_node = row[0].strip()
                self.void_date = parse_date(row[3])
                break

    def _load_schedule(self):
        self.vault_preference = {}
        with open(self.path("retention_schedule_2019.csv"), "r",
                  encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                self.vault_preference[row["class"].strip()] = [
                    part.strip().upper() for part in row["vault_preference"].split(">")]

    def _load_media(self):
        catalogue = json.loads(read_text(self.path("media_catalogue.json")))
        self.native_capacity = {item["type"]: int(item["native_capacity_bytes"])
                                for item in catalogue.get("media", [])}
        self.reserve_bytes = read_reserve_sheet(
            self.path("capacity_planning_2022.xlsx"))

    def _load_vaults(self):
        parser = ConfigParser()
        parser.read(self.path("vault_profiles.ini"), encoding="utf-8")
        self.vault_code = {}
        self.block_size = {}
        self.cartridge = {}
        for section in parser.sections():
            name = section.split(".", 1)[1] if "." in section else section
            code = parser.get(section, "code").strip().upper()
            self.vault_code[name.strip().lower()] = code
            self.block_size[code] = parser.getint(section, "block_size")
            self.cartridge[code] = parser.get(section, "cartridge").strip()
        self.vault_codes = sorted(self.block_size)
        self.usable_bytes = {
            code: self.native_capacity[cart] - self.reserve_bytes[cart]
            for code, cart in self.cartridge.items()}

    def _load_catalogue(self):
        uri = "file:" + self.path("catalogue.db").replace("?", "%3f") + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        try:
            cur = conn.execute("SELECT collection_id, segment, retention_class, "
                               "ingest_year FROM collection")
            self.collections = {
                cid: {"segment": segment, "class": cls, "ingest_year": int(year)}
                for cid, segment, cls, year in cur.fetchall()}
        finally:
            conn.close()
        self.segments = sorted({c["segment"] for c in self.collections.values()})

    def _load_crosswalk(self):
        self.crosswalk = {}
        with open(self.path("collection_crosswalk.tsv"), "r",
                  encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh, delimiter="\t"):
                self.crosswalk.setdefault(row["legacy_id"].strip(), []).append(
                    (parse_date(row["effective_from"]), row["collection_id"].strip()))
        for rows in self.crosswalk.values():
            rows.sort()

    def _load_holds(self):
        faq = read_text(self.path("legal_hold_faq.md"))
        match = re.search(r"\(UTC([+-])(\d{2}):(\d{2})\)", faq)
        if not match:
            raise PlanError("no local time zone in the legal hold FAQ")
        sign = 1 if match.group(1) == "+" else -1
        self.local_zone = dt.timezone(sign * dt.timedelta(
            hours=int(match.group(2)), minutes=int(match.group(3))))

        self.hold_events = {}
        with open(self.path("legal_holds.psv"), "r",
                  encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh, delimiter="|"):
                stamp = dt.datetime.fromisoformat(row["effective"].strip())
                if stamp.tzinfo is None:
                    stamp = stamp.replace(tzinfo=self.local_zone)
                action = row["action"].strip().upper()
                self.hold_events.setdefault(row["collection"].strip(), []).append(
                    (stamp.astimezone(self.local_zone).date(),
                     1 if action == "PLACE" else 0,
                     row["event_id"].strip(), action))
        for events in self.hold_events.values():
            events.sort(key=lambda e: (e[0], e[1], e[2]))

    def _load_rights(self):
        root = ET.parse(self.path("rights_register.xml")).getroot()
        self.licences = []
        for elem in root.iter():
            if elem.tag.rsplit("}", 1)[-1] != "licence":
                continue
            self.licences.append({
                "collection": elem.get("collection"),
                "class": elem.get("class_override"),
                "from": parse_date(elem.get("from")),
                "to": parse_date(elem.get("to")),
            })
        self.licences.sort(key=lambda lic: (lic["collection"], lic["from"],
                                            lic["to"]))

    def _load_amendments(self):
        self.amend_min_override = None
        self.amend_rights = None
        self.amend_split = None
        for name in self.names:
            if not re.fullmatch(r"charter_amendment_\d+\.md", name):
                continue
            text = read_text(self.path(name))
            if re.search(r"rights register", text, re.I):
                date = re.search(r"From (\d{4}-\d{2}-\d{2})", text)
                segment = re.search(r"`(\w+)` segment|segment `(\w+)`", text)
                self.amend_rights = {
                    "from": parse_date(date.group(1)),
                    "segment": (segment.group(1) or segment.group(2))
                    if segment else None,
                }
            elif re.search(r"is replaced by two classes", text):
                date = re.search(
                    r"From (\d{4}-\d{2}-\d{2}) class (R[0-9A-Z]+) is replaced", text)
                table = []
                for cls, cond, minimum in re.findall(
                        r"^\|\s*(R[0-9A-Z]+)\s*\|\s*([^|]+?)\s*\|\s*(\d+)\s*\|\s*$",
                        text, re.M):
                    earlier = re.search(r"earlier than (\d+)", cond)
                    later = re.search(r"(\d+) or later", cond)
                    if earlier:
                        table.append((cls, "lt", int(earlier.group(1)), int(minimum)))
                    elif later:
                        table.append((cls, "ge", int(later.group(1)), int(minimum)))
                self.amend_split = {
                    "from": parse_date(date.group(1)),
                    "class": date.group(2),
                    "table": table,
                }
            elif re.search(r"instead of", text):
                scope = re.search(r"class (R[0-9A-Z]+) in the `?(\w+)`? segment", text)
                window = re.search(
                    r"from (\d{4}-\d{2}-\d{2}) up to but excluding "
                    r"(\d{4}-\d{2}-\d{2})", text)
                rule = re.search(r"is\s+(\d+)\s+instead\s+of\s+(\d+)", text)
                self.amend_min_override = {
                    "class": scope.group(1),
                    "segment": scope.group(2),
                    "start": parse_date(window.group(1)),
                    "end": parse_date(window.group(2)),
                    "minimum": int(rule.group(1)),
                }

    # ---- derived rules --------------------------------------------------
    def resolve_collection(self, raw: str, catalogued):
        """Map a row's collection id to a current id; flag legacy ids."""
        rows = self.crosswalk.get(raw)
        if rows is None:
            return raw, False
        if len(rows) == 1:
            return rows[0][1], True
        chosen = rows[0][1]
        for effective_from, current in rows:
            if catalogued is not None and effective_from <= catalogued:
                chosen = current
        return chosen, True

    def settled_class(self, collection_id: str, as_of: dt.date) -> str:
        """Class after the rights register amendment and the class split."""
        info = self.collections[collection_id]
        cls = info["class"]
        rights = self.amend_rights
        if rights is not None and as_of >= rights["from"]:
            if rights["segment"] is None or info["segment"] == rights["segment"]:
                for lic in self.licences:
                    if lic["collection"] == collection_id \
                            and lic["from"] <= as_of <= lic["to"]:
                        cls = lic["class"]
        split = self.amend_split
        if split is not None and as_of >= split["from"] and cls == split["class"]:
            year = info["ingest_year"]
            for new_class, kind, bound, _minimum in split["table"]:
                if (kind == "lt" and year < bound) or (kind == "ge" and year >= bound):
                    cls = new_class
                    break
        return cls

    def class_minimum_for(self, collection_id: str, cls: str, as_of: dt.date) -> int:
        split = self.amend_split
        if split is not None and as_of >= split["from"]:
            for new_class, _kind, _bound, minimum in split["table"]:
                if new_class == cls:
                    return self._with_min_override(collection_id, cls, as_of, minimum)
        base = self.class_minimum.get(cls)
        if base is None:
            raise PlanError("class %s has no minimum" % cls)
        return self._with_min_override(collection_id, cls, as_of, base)

    def _with_min_override(self, collection_id, cls, as_of, minimum):
        amendment = self.amend_min_override
        if amendment is None or cls != amendment["class"]:
            return minimum
        if self.collections[collection_id]["segment"] != amendment["segment"]:
            return minimum
        if amendment["start"] <= as_of < amendment["end"]:
            return amendment["minimum"]
        return minimum

    def required_for(self, collection_id: str, rendition: str, as_of: dt.date) -> int:
        cls = self.settled_class(collection_id, as_of)
        minimum = self.class_minimum_for(collection_id, cls, as_of)
        rendition = rendition.lower()
        if rendition == "proxy":
            return 1
        if rendition == "mezzanine":
            return max(minimum - 1, 1)
        return minimum

    def preference_for(self, cls: str) -> list[str]:
        name = cls
        while name and name not in self.vault_preference:
            name = name[:-1]
        order = [code for code in self.vault_preference.get(name, [])
                 if code in self.block_size]
        return order + [code for code in self.vault_codes if code not in order]

    def is_held(self, collection_id: str, as_of: dt.date) -> bool:
        last = None
        for local_date, _rank, _eid, action in self.hold_events.get(collection_id, []):
            if local_date <= as_of:
                last = action
        return last == "PLACE"

    def footprint(self, code: str, size: int) -> int:
        block = self.block_size[code]
        return self.tape_header + -(-size // block) * block

    def label(self, code: str, sequence: int) -> str:
        return "%s-%0*d" % (code, self.label_width, sequence)


# --------------------------------------------------------------------------
# vault exports
# --------------------------------------------------------------------------

KOLHAPUR_COLUMNS = (
    ("path", 0, 72),
    ("sequence", 72, 79),
    ("sectors", 79, 90),
    ("collection", 90, 100),
    ("rendition", 100, 101),
    ("catalogued", 101, 109),
)

RENDITION_WORDS = ("master", "mezzanine", "proxy")


def kolhapur_letters(rules: Rules) -> dict[str, str]:
    text = read_text(rules.path("kolhapur_tape_notes.txt"))
    letters = {}
    for letter, word in re.findall(r"^\s*([A-Z])\s*=\s*(\w+)\s*$", text, re.M):
        if word.lower() in RENDITION_WORDS:
            letters[letter] = word.lower()
    if not letters:
        raise PlanError("no Kolhapur rendition letter codes")
    return letters


def kolhapur_index(path: str) -> dict[int, tuple[int, str]]:
    blob = read_bytes(path)
    if blob[:6] != b"KLHIDX":
        raise PlanError("bad index magic in " + os.path.basename(path))
    count = struct.unpack_from("<I", blob, 8)[0]
    records = {}
    for i in range(count):
        offset = 12 + 44 * i
        sequence, size = struct.unpack_from("<IQ", blob, offset)
        records[sequence] = (size, blob[offset + 12:offset + 44].hex())
    return records


def _date_or_none(text):
    if not text:
        return None
    text = text.strip()
    if re.fullmatch(r"\d{8}", text):
        return dt.date(int(text[0:4]), int(text[4:6]), int(text[6:8]))
    try:
        return parse_date(text)
    except ValueError:
        return None


def _stamp_date(text):
    if not text:
        return None
    try:
        return dt.datetime.fromisoformat(text.strip().replace("Z", "+00:00")).date()
    except ValueError:
        return None


def decode_digest(encoding: str, text: str) -> str:
    if encoding == "q2":
        raw = base64.b64decode(text, validate=True)
    elif encoding == "k7":
        raw = base64.b32decode(text + "=" * ((8 - len(text) % 8) % 8))
    else:
        raise PlanError("unknown digest encoding " + repr(encoding))
    return raw.hex()


def load_rows(rules: Rules, names: list[str]) -> list[dict]:
    """Read every vault export row named by the census."""
    rows = []
    letters = None

    for name in names:
        prefix = name.split("_", 1)[0].lower()
        code = rules.vault_code.get(prefix)
        if code is None:
            continue
        path = rules.path(name)

        if name.endswith(".dat"):
            if letters is None:
                letters = kolhapur_letters(rules)
            shard = re.search(r"(\d+)\.dat$", name).group(1)
            index_name = next(
                (other for other in names
                 if other.endswith(shard + ".idx")
                 and other.split("_", 1)[0].lower() == prefix), None)
            if index_name is None:
                raise PlanError("no index shard for " + name)
            index = kolhapur_index(rules.path(index_name))
            for line in read_bytes(path).decode("ascii").split("\n"):
                if line.strip() == "":
                    continue
                field = {key: line[start:stop]
                         for key, start, stop in KOLHAPUR_COLUMNS}
                size, digest = index[int(field["sequence"])]
                rows.append({
                    "vault": code,
                    "path": field["path"].rstrip(" "),
                    "bytes": size,
                    "digest": digest.lower(),
                    "raw_collection": field["collection"].strip(),
                    "rendition": letters[field["rendition"]],
                    "catalogued": _date_or_none(field["catalogued"]),
                    "node": None,
                    "file": name,
                })

        elif name.endswith(".xml"):
            for obj in ET.parse(path).getroot():
                if obj.tag.rsplit("}", 1)[-1] != "obj":
                    continue
                digest_elem = next(
                    (child for child in obj
                     if child.tag.rsplit("}", 1)[-1] == "digest"), None)
                rows.append({
                    "vault": code,
                    "path": obj.get("path"),
                    "bytes": int(obj.get("size")),
                    "digest": decode_digest(digest_elem.get("enc"),
                                            (digest_elem.text or "").strip()),
                    "raw_collection": obj.get("coll").strip(),
                    "rendition": obj.get("form").strip().lower(),
                    "catalogued": _date_or_none(obj.get("catalogued")),
                    "node": None,
                    "file": name,
                })

        elif name.endswith(".csv"):
            with open(path, "r", encoding="utf-8", newline="") as fh:
                for row in csv.DictReader(fh):
                    rows.append({
                        "vault": code,
                        "path": row["object_path"],
                        "bytes": int(row["bytes"]),
                        "digest": row["sha256"].strip().lower(),
                        "raw_collection": row["collection"].strip(),
                        "rendition": row["rendition"].strip().lower(),
                        "catalogued": _stamp_date(row.get("written_utc")),
                        "node": (row.get("node") or "").strip() or None,
                        "file": name,
                    })

        elif name.endswith(".jsonl"):
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    if line.strip() == "":
                        continue
                    item = json.loads(line)
                    size = int(item["len"]) if "len" in item \
                        else int(item["len_hex"], 16)
                    digest = item["dg"]
                    if ":" in digest:
                        digest = digest.split(":", 1)[1]
                    rows.append({
                        "vault": code,
                        "path": item["p"],
                        "bytes": size,
                        "digest": digest.strip().lower(),
                        "raw_collection": item["col"].strip(),
                        "rendition": item["kind"].strip().lower(),
                        "catalogued": None,
                        "node": None,
                        "file": name,
                    })

    for row in rows:
        current, legacy = rules.resolve_collection(row["raw_collection"],
                                                   row["catalogued"])
        row["collection"] = current
        row["legacy"] = legacy
        row["sidecar"] = row["bytes"] < rules.sidecar_threshold
    rows.sort(key=lambda r: (r["vault"], r["path"], r["digest"]))
    return rows


# --------------------------------------------------------------------------
# planning
# --------------------------------------------------------------------------

def plan_scenario(rules: Rules, rows: list[dict], as_of: dt.date):
    """Decide the kept replicas of one scenario."""
    planned = []
    void_rows = 0
    for row in rows:
        if rules.void_node is not None and row["node"] == rules.void_node \
                and as_of >= rules.void_date:
            void_rows += 1
            continue
        if row["sidecar"]:
            continue
        planned.append(row)

    by_digest = {}
    for row in planned:
        by_digest.setdefault(row["digest"], []).append(row)

    objects = []
    keep_flags = {}
    for digest in sorted(by_digest):
        members = by_digest[digest]
        collections = sorted_unique(row["collection"] for row in members)
        rendition = members[0]["rendition"]

        required = -1
        governing = None
        for collection in collections:
            value = rules.required_for(collection, rendition, as_of)
            if value > required:
                required = value
                governing = collection
        reported_class = rules.settled_class(governing, as_of)
        held = any(rules.is_held(collection, as_of) for collection in collections)

        primary = {}
        for row in members:
            current = primary.get(row["vault"])
            if current is None or row["path"] < current["path"]:
                primary[row["vault"]] = row
        under = len(primary) < required

        if held:
            keep = {id(row) for row in members}
        elif under:
            keep = {id(row) for row in primary.values()}
        else:
            order = [code for code in rules.preference_for(reported_class)
                     if code in primary]
            keep = {id(primary[code]) for code in order[:required]}

        for row in members:
            keep_flags[id(row)] = id(row) in keep

        objects.append({
            "digest": digest,
            "rendition": rendition,
            "collections": collections,
            "class": reported_class,
            "required": required,
            "held": held,
            "under_replicated": under,
            "kept_vaults": sorted_unique(row["vault"] for row in members
                                         if keep_flags[id(row)]),
        })

    replicas = [{
        "vault": row["vault"],
        "path": row["path"],
        "digest": row["digest"],
        "bytes": row["bytes"],
        "collection": row["collection"],
        "rendition": row["rendition"],
        "keep": keep_flags[id(row)],
    } for row in sorted(planned, key=lambda r: (r["vault"], r["path"]))]

    kept = [row for row in planned if keep_flags[id(row)]]
    released = [row for row in planned if not keep_flags[id(row)]]
    return objects, replicas, kept, released, void_rows


def _label_sequence(label: str) -> int:
    match = re.search(r"(\d+)\s*$", label or "")
    return int(match.group(1)) if match else 0


def pack_vault(rules: Rules, code: str, kept: list[dict],
               prior_volumes: list[dict]) -> list[dict]:
    """Pack one vault's kept replicas, carrying prior volumes over."""
    usable = rules.usable_bytes[code]
    by_path = {row["path"]: row for row in kept}

    volumes = []
    taken = set()
    max_sequence = 0
    for prior in prior_volumes:
        max_sequence = max(max_sequence, _label_sequence(prior.get("label", "")))
        members = [member[0] for member in prior.get("members", [])]
        if not members or not all(path in by_path and path not in taken
                                  for path in members):
            continue
        taken.update(members)
        entries = [[path, rules.footprint(code, by_path[path]["bytes"])]
                   for path in members]
        used = sum(entry[1] for entry in entries)
        volumes.append({
            "label": prior.get("label"),
            "vault": code,
            "usable_bytes": usable,
            "used_bytes": used,
            "fill_bps": round_half_even(used * 10000, usable),
            "members": entries,
        })

    pool = [(rules.footprint(code, row["bytes"]), row["digest"], row["path"])
            for row in kept if row["path"] not in taken]
    pool.sort(key=lambda item: (-item[0], item[1], item[2]))

    opened = []
    for size, _digest, path in pool:
        for volume in opened:
            if volume["used_bytes"] + size <= usable:
                volume["used_bytes"] += size
                volume["members"].append([path, size])
                break
        else:
            max_sequence += 1
            opened.append({
                "label": rules.label(code, max_sequence),
                "vault": code,
                "usable_bytes": usable,
                "used_bytes": size,
                "fill_bps": 0,
                "members": [[path, size]],
            })

    for volume in opened:
        volume["fill_bps"] = round_half_even(volume["used_bytes"] * 10000, usable)
    volumes.extend(opened)
    return volumes


def load_prior(prior_dir, name: str) -> dict[str, list[dict]]:
    if not prior_dir:
        return {}
    path = os.path.join(prior_dir, "scenario_%s.json" % name)
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    by_vault = {}
    for volume in data.get("volumes", []):
        by_vault.setdefault(volume.get("vault"), []).append(volume)
    return by_vault


# --------------------------------------------------------------------------
# output
# --------------------------------------------------------------------------

def write_json(out_dir: str, name: str, payload) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)
    with open(os.path.join(out_dir, name), "w", encoding="utf-8",
              newline="\n") as fh:
        fh.write(text)
        fh.write("\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="KCBA replica retention planner")
    parser.add_argument("--data", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--prior", default=None)
    args = parser.parse_args(argv)

    data_dir, out_dir = args.data, args.out
    os.makedirs(out_dir, exist_ok=True)

    plan_id = None
    scenarios = {}
    run_path = os.path.join(data_dir, RUN_CONTROL)
    if os.path.isfile(run_path):
        try:
            control = json.loads(read_text(run_path))
            plan_id = control.get("plan_id")
            scenarios = control.get("scenarios") or {}
        except (OSError, ValueError):
            plan_id = None

    entries, reasons, census_ok = verify_census(data_dir)
    if not census_ok:
        write_json(out_dir, "perf_report.json", {
            "plan_id": plan_id,
            "status": "HELD",
            "reasons": reasons,
            "census": entries,
            "scenarios": [],
        })
        return 0

    names = census_file_names(data_dir)
    rules = Rules(data_dir, names)
    rows = load_rows(rules, names)

    file_stats = {}
    for row in rows:
        stats = file_stats.setdefault(row["file"], {
            "rows": 0,
            "sidecar_rows": 0,
            "legacy_collection_rows": 0,
            "duplicate_rows": 0,
        })
        stats["rows"] += 1
        if row["sidecar"]:
            stats["sidecar_rows"] += 1
        if row["legacy"]:
            stats["legacy_collection_rows"] += 1

    primaries = {}
    for row in rows:
        if row["sidecar"]:
            continue
        key = (row["vault"], row["digest"])
        current = primaries.get(key)
        if current is None or row["path"] < current["path"]:
            primaries[key] = row
    for row in rows:
        if not row["sidecar"] and primaries[(row["vault"], row["digest"])] is not row:
            file_stats[row["file"]]["duplicate_rows"] += 1

    perf_scenarios = []
    bottleneck = {}
    recommendations = {}
    void_counts = {}

    for name in sorted(scenarios):
        as_of = parse_date(scenarios[name]["as_of"])
        objects, replicas, kept, released, void_rows = plan_scenario(
            rules, rows, as_of)
        void_counts[name] = void_rows

        prior_volumes = load_prior(args.prior, name)
        kept_by_vault = {code: [] for code in rules.vault_codes}
        for row in kept:
            kept_by_vault.setdefault(row["vault"], []).append(row)

        volumes = []
        vault_rollup = {}
        for code in sorted(kept_by_vault):
            vault_volumes = pack_vault(rules, code, kept_by_vault[code],
                                       prior_volumes.get(code, []))
            volumes.extend(vault_volumes)
            vault_rollup[code] = {
                "volumes": len(vault_volumes),
                "used_bytes": sum(v["used_bytes"] for v in vault_volumes),
                "kept_replicas": len(kept_by_vault[code]),
            }

        write_json(out_dir, "scenario_%s.json" % name, {
            "plan_id": plan_id,
            "scenario": name,
            "as_of": as_of.isoformat(),
            "objects": objects,
            "replicas": replicas,
            "volumes": volumes,
        })

        perf_scenarios.append({
            "name": name,
            "as_of": as_of.isoformat(),
            "objects": len(objects),
            "kept_replicas": len(kept),
            "released_replicas": len(released),
            "volumes": len(volumes),
        })
        bottleneck[name] = {
            "under_replicated_objects": sum(1 for o in objects
                                            if o["under_replicated"]),
            "held_objects": sum(1 for o in objects if o["held"]),
            "vaults": vault_rollup,
        }

        by_vault = {code: 0 for code in rules.vault_codes}
        by_segment = {segment: 0 for segment in rules.segments}
        for row in released:
            by_vault[row["vault"]] = by_vault.get(row["vault"], 0) + row["bytes"]
            segment = rules.collections[row["collection"]]["segment"]
            by_segment[segment] = by_segment.get(segment, 0) + row["bytes"]
        recommendations[name] = {
            "release_replicas": len(released),
            "reclaim_bytes_by_vault": by_vault,
            "reclaim_bytes_by_segment": by_segment,
        }

    perf_scenarios.sort(key=lambda s: (s["as_of"], s["name"]))

    media_shares = {}
    for cartridge in sorted(rules.native_capacity):
        reserve = rules.reserve_bytes.get(cartridge)
        if reserve is not None:
            media_shares[cartridge] = round_half_even(
                reserve * 10000, rules.native_capacity[cartridge])

    write_json(out_dir, "perf_report.json", {
        "plan_id": plan_id,
        "status": "PUBLISHED",
        "reasons": [],
        "census": entries,
        "scenarios": perf_scenarios,
        "media_shares": media_shares,
    })
    write_json(out_dir, "bottleneck_analysis.json",
               {"plan_id": plan_id, "scenarios": bottleneck})
    write_json(out_dir, "recommendations.json",
               {"plan_id": plan_id, "scenarios": recommendations})
    write_json(out_dir, "data_quality.json", {
        "plan_id": plan_id,
        "files": file_stats,
        "void_node_rows": void_counts,
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
