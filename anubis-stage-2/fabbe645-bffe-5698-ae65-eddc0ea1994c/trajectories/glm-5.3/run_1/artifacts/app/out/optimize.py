#!/usr/bin/env python3
"""KCBA archive desk planner.

Reads one cycle's estate export and writes the retention and tape packing plan:

    python3 optimize.py --data DATA_DIR --out OUT_DIR [--prior EARLIER_OUT_DIR]

Every rule is taken from the papers in the export folder: the retention charter and
its amendments, the volume layout note, the older papers for the single item each of
them still decides (charter section 10), the format notes of the four vault exports
and the run control file. Nothing that belongs to a particular cycle is built in here.
"""

import argparse
import base64
import collections
import configparser
import csv
import datetime
import hashlib
import json
import os
import re
import sqlite3
import struct
import tomllib
import xml.etree.ElementTree as ET
import zipfile

CHARTER_MIN_ROW = re.compile(r"^\|\s*(R\d+[AB]?)\s*\|\s*(\d+)\s*\|\s*$")
KLH_COL_ROW = re.compile(r"^\|\s*(\d+)\s*(?:to\s*(\d+))?\s*\|\s*(\d+)\s*\|([^|]*)\|$")


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------

def read_text(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def round_half_even(num, den):
    """num/den rounded to the nearest integer, an exact half to the even neighbour."""
    if den == 0:
        raise ZeroDivisionError("usable capacity is zero")
    neg = num < 0
    num = -num if neg else num
    quot, rem = divmod(num, den)
    twice = 2 * rem
    if twice > den or (twice == den and quot % 2 == 1):
        quot += 1
    return -quot if neg else quot


def local_name(tag):
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def byte_key(text):
    """Sort key for plain byte order."""
    return text.encode("utf-8")


def flatten(text):
    """Collapse line breaks and runs of blanks, so wrapped sentences still match."""
    return re.sub(r"\s+", " ", text)


def shard_number(stem):
    m = re.search(r"(\d+)$", stem)
    return m.group(1) if m else ""


# --------------------------------------------------------------------------
# papers
# --------------------------------------------------------------------------

class Papers:
    """Every rule the papers of this cycle state, as far as it can be read as data."""

    def __init__(self):
        self.charter_min = {}            # class -> minimum distinct vaults for a master
        self.sidecar_threshold = None   # bytes, a file strictly below is a sidecar
        self.label_digits = 5           # volume sequence padding
        self.tape_header_bytes = 16384  # bytes in front of every tape object
        self.fill_basis = 10000         # basis points of usable capacity
        self.ist_offset = datetime.timedelta(hours=5, minutes=30)
        self.decommissioned = {}         # storage node -> decommission date
        self.klh_rendition = {}         # letter -> rendition
        self.klh_columns = None         # field -> (start, end), 0 based half open
        self.klh_index = {"count_offset": 8, "count_size": 4, "header": 12,
                          "record": 44, "seq": 4, "size": 8, "digest": 32}
        self.digest_encodings = {}       # Margao code -> base32 | base64
        self.vault_profiles = []         # (family, code, cartridge, block size)
        self.cartridge_native = {}       # cartridge -> native capacity bytes
        self.cartridge_reserve = {}      # cartridge -> reserve bytes
        self.preferences = {}            # class -> vault codes, most preferred first
        self.amendments = {"rights": None, "split": None, "minimum": None}
        self.crosswalk = []              # (legacy id, current id, effective from)


def parse_charter(text, papers):
    for line in text.splitlines():
        m = CHARTER_MIN_ROW.match(line.strip())
        if m:
            papers.charter_min[m.group(1)] = int(m.group(2))


def parse_sidecar_note(text, papers):
    m = re.search(r"strictly below (\d+) bytes", flatten(text))
    if m:
        papers.sidecar_threshold = int(m.group(1))


def parse_ops_handbook(text, papers):
    m = re.search(r"padded with leading zeros to exactly (\d+) digits", flatten(text))
    if m:
        papers.label_digits = int(m.group(1))


def parse_volume_layout(text, papers):
    flat = flatten(text)
    m = re.search(r"header of (\d+) bytes", flat)
    if m:
        papers.tape_header_bytes = int(m.group(1))
    m = re.search(r"used_bytes \* (\d+) / usable_bytes", flat)
    if m:
        papers.fill_basis = int(m.group(1))


def parse_hold_faq(text, papers):
    m = re.search(r"UTC\+(\d{2}):(\d{2})", flatten(text))
    if m:
        papers.ist_offset = datetime.timedelta(hours=int(m.group(1)),
                                               minutes=int(m.group(2)))


def parse_nashik_audit(text, papers):
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", text, re.S):
        cells = [re.sub(r"<[^>]+>", "", c).strip()
                 for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)]
        if len(cells) < 4 or "decommission" not in cells[2].lower():
            continue
        m = re.search(r"(\d{4}-\d{2}-\d{2})", cells[3])
        if m:
            papers.decommissioned[cells[0]] = m.group(1)


def parse_kolhapur_notes(text, papers):
    for line in text.splitlines():
        m = re.match(r"^\s*(\S+)\s*=\s*(master|mezzanine|proxy)\s*$", line, re.I)
        if m:
            papers.klh_rendition[m.group(1)] = m.group(2).lower()


def parse_kolhapur_format(text, papers):
    for line in text.splitlines():
        m = KLH_COL_ROW.match(line.strip())
        if not m:
            continue
        start = int(m.group(1))
        end = int(m.group(2) or start)
        desc = m.group(4).strip().lower()
        field = None
        if desc.startswith("object path"):
            field = "path"
        elif desc.startswith("sequence number"):
            field = "seq"
        elif "sectors" in desc:
            field = "sectors"
        elif desc.startswith("collection id"):
            field = "collection"
        elif "rendition" in desc:
            field = "rendition"
        elif "date" in desc:
            field = "catalogued"
        if field:
            papers.klh_columns[field] = (start - 1, end)
    idx = papers.klh_index
    for line in text.splitlines():
        m = re.match(r"^\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([^|]*)\|", line.strip())
        if not m:
            continue
        off, size, desc = int(m.group(1)), int(m.group(2)), m.group(3).strip().lower()
        if desc.startswith("magic"):
            idx["magic_offset"], idx["magic_size"] = off, size
        elif desc.startswith("format version"):
            idx["version_offset"], idx["version_size"] = off, size
        elif desc.startswith("record count"):
            idx["count_offset"], idx["count_size"] = off, size
    m = re.search(r"\|\s*(\d+)\s+per record\s*\|", text)
    if m:
        idx["record"] = int(m.group(1))
    m = re.search(r"(\d+) byte sequence number", text)
    if m:
        idx["seq"] = int(m.group(1))
    m = re.search(r"(\d+) byte exact size", text)
    if m:
        idx["size"] = int(m.group(1))
    m = re.search(r"(\d+) raw bytes of the SHA-256", text)
    if m:
        idx["digest"] = int(m.group(1))


def parse_margao_readme(text, papers):
    for line in text.splitlines():
        m = re.match(r"^\|\s*`([^`]+)`\s*\|([^|]*)\|", line.strip())
        if not m:
            continue
        code, desc = m.group(1), m.group(2).lower()
        if "base32" in desc:
            papers.digest_encodings[code] = "base32"
        elif "base64" in desc:
            papers.digest_encodings[code] = "base64"


def parse_amendment(text, papers):
    """Recognise and read a dated charter amendment from what it says.

    The kinds of amendment are told apart by their own words: one that hands the class
    of a segment to the rights register, one that splits a class by ingest year, and one
    that overrides the minimum of a class in a segment for a dated window.
    """
    flat = flatten(text)
    if "rights register" in flat:
        m = re.search(r"From (\d{4}-\d{2}-\d{2}) the rights register `([^`]+)` is "
                      r"authoritative for the retention class of collections in the "
                      r"`(\w+)` segment", flat)
        if m:
            papers.amendments["rights"] = {"from": m.group(1), "segment": m.group(3)}
        return
    if "replaced by two classes" in flat:
        m = re.search(r"From (\d{4}-\d{2}-\d{2}) class (R\d+[AB]?) is replaced by "
                      r"two classes", flat)
        if not m:
            return
        split = {"from": m.group(1), "base": m.group(2), "branches": []}
        for line in text.splitlines():
            m = re.match(r"^\|\s*(R\d+[AB]?)\s*\|\s*`ingest_year`([^|]*)\|\s*(\d+)\s*\|",
                         line.strip())
            if not m:
                continue
            cond, year = m.group(2).strip(), None
            found = re.search(r"(\d{4})", cond)
            if found:
                year = int(found.group(1))
            branch = {"class": m.group(1), "min": int(m.group(3))}
            if "or later" in cond:
                branch["at_least"] = year
            else:
                branch["before"] = year
            split["branches"].append(branch)
        papers.amendments["split"] = split
        return
    m = re.search(r"Window:\s*from (\d{4}-\d{2}-\d{2})(.*?)(\d{4}-\d{2}-\d{2})",
                  flat)
    window = (m.group(1), m.group(3), "exclud" in m.group(2)) if m else None
    m = re.search(r"Scope:\s*collections of class (R\d+[AB]?) in the `(\w+)` segment",
                  flat)
    scope = (m.group(1), m.group(2)) if m else None
    m = re.search(r"class minimum of an (R\d+[AB]?) (\w+) collection is (\d+) "
                  r"instead of (\d+)", flat)
    rule = (m.group(1), int(m.group(3))) if m else None
    if window and scope and rule:
        papers.amendments["minimum"] = {
            "from": window[0], "until": window[1], "end_excluded": window[2],
            "class": rule[0], "segment": scope[1], "min": rule[1],
        }


def parse_retention_schedule(path, papers):
    with open(path, "r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            klass = (row.get("class") or "").strip()
            pref = (row.get("vault_preference") or "").strip()
            if klass and pref:
                papers.preferences[klass] = [v.strip() for v in pref.split(">") if v.strip()]


def parse_vault_profiles(path, papers):
    cp = configparser.ConfigParser()
    cp.read(path, encoding="utf-8")
    for section in cp.sections():
        if not cp.has_option(section, "code"):
            continue
        family = section.split(".", 1)[1] if "." in section else section
        papers.vault_profiles.append((
            family,
            cp.get(section, "code").strip().upper(),
            cp.get(section, "cartridge").strip(),
            int(cp.get(section, "block_size").strip()),
        ))
    papers.vault_profiles.sort(key=lambda p: p[1])


def parse_media_catalogue(path, papers):
    for medium in json.loads(read_text(path)).get("media", []):
        papers.cartridge_native[str(medium["type"]).strip()] = \
            int(medium["native_capacity_bytes"])


def parse_xlsx(path, papers):
    """Read the reserve column of the Reserve sheet of the capacity workbook."""
    ns_v = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v"
    with zipfile.ZipFile(path) as zf:
        shared = []
        if "xl/sharedStrings.xml" in zf.namelist():
            for si in ET.fromstring(zf.read("xl/sharedStrings.xml")):
                shared.append("".join(t.text or "" for t in si.iter()
                                      if local_name(t.tag) == "t"))
        rels = {}
        for rel in ET.fromstring(zf.read("xl/_rels/workbook.xml.rels")):
            rels[rel.get("Id")] = rel.get("Target")
        sheet_part = None
        for sh in ET.fromstring(zf.read("xl/workbook.xml")).iter():
            if local_name(sh.tag) != "sheet" or sh.get("name") != "Reserve":
                continue
            rid = [v for k, v in sh.attrib.items() if k.endswith("}id")]
            if rid and rid[0] in rels:
                target = rels[rid[0]]
                sheet_part = target if target.startswith("xl/") else "xl/" + target.lstrip("/")
        if sheet_part is None:
            return
        rows = []
        for row in ET.fromstring(zf.read(sheet_part)).iter():
            if local_name(row.tag) != "row":
                continue
            cells = {}
            for cell in row:
                if local_name(cell.tag) != "c":
                    continue
                col = re.match(r"([A-Z]+)", cell.get("r") or "")
                if not col:
                    continue
                value = cell.find(ns_v)
                if cell.get("t") == "s" and value is not None:
                    cells[col.group(1)] = shared[int(value.text)]
                elif cell.get("t") == "inlineStr":
                    cells[col.group(1)] = "".join(
                        t.text or "" for t in cell.iter() if local_name(t.tag) == "t")
                elif value is not None:
                    text = (value.text or "").strip()
                    cells[col.group(1)] = (int(text) if re.fullmatch(r"-?\d+", text)
                                           else float(text))
            rows.append(cells)
        if not rows:
            return
        header = {name: col for col, name in rows[0].items() if isinstance(name, str)}
        key_col, val_col = header.get("cartridge"), header.get("reserve_bytes")
        if not key_col or not val_col:
            return
        for cells in rows[1:]:
            name, value = cells.get(key_col), cells.get(val_col)
            if isinstance(name, str) and isinstance(value, (int, float)):
                papers.cartridge_reserve[name.strip()] = int(value)


def parse_crosswalk(path, papers):
    with open(path, "r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            papers.crosswalk.append((
                (row.get("legacy_id") or "").strip(),
                (row.get("collection_id") or "").strip(),
                (row.get("effective_from") or "").strip(),
            ))


PAPER_PARSERS = [
    (re.compile(r"^retention_charter\.md$"), parse_charter),
    (re.compile(r"^sidecar_policy_note\.md$"), parse_sidecar_note),
    (re.compile(r"^ops_handbook_2021\.md$"), parse_ops_handbook),
    (re.compile(r"^volume_layout\.md$"), parse_volume_layout),
    (re.compile(r"^legal_hold_faq\.md$"), parse_hold_faq),
    (re.compile(r"^nashik_audit_2024\.html$"), parse_nashik_audit),
    (re.compile(r"^kolhapur_tape_notes\.txt$"), parse_kolhapur_notes),
    (re.compile(r"^kolhapur_index_format\.md$"), parse_kolhapur_format),
    (re.compile(r"^margao_export_readme\.md$"), parse_margao_readme),
    (re.compile(r"^charter_amendment_\d+\.md$"), parse_amendment),
]

DATA_PARSERS = [
    (re.compile(r"^retention_schedule_2019\.csv$"), parse_retention_schedule),
    (re.compile(r"^vault_profiles\.ini$"), parse_vault_profiles),
    (re.compile(r"^media_catalogue\.json$"), parse_media_catalogue),
    (re.compile(r"^capacity_planning_2022\.xlsx$"), parse_xlsx),
    (re.compile(r"^collection_crosswalk\.tsv$"), parse_crosswalk),
]


def load_papers(data_dir):
    papers = Papers()
    papers.klh_columns = {}
    for name in sorted(os.listdir(data_dir)):
        path = os.path.join(data_dir, name)
        if not os.path.isfile(path):
            continue
        for pattern, parser in PAPER_PARSERS:
            if pattern.match(name):
                try:
                    text = read_text(path)
                except (UnicodeDecodeError, OSError):
                    text = ""
                parser(text, papers)
                break
        for pattern, parser in DATA_PARSERS:
            if pattern.match(name):
                parser(path, papers)
                break
    if not papers.klh_columns:
        papers.klh_columns = {"path": (0, 72), "seq": (72, 79), "sectors": (79, 90),
                              "collection": (90, 100), "rendition": (100, 101),
                              "catalogued": (101, 109)}
    return papers


# --------------------------------------------------------------------------
# census
# --------------------------------------------------------------------------

def count_records(path, name):
    """Count records the way the desk brief sets out for this kind of file."""
    if re.fullmatch(r"nashik_manifest_\d+\.csv", name):
        with open(path, "r", encoding="utf-8", newline="") as fh:
            rows = [row for row in csv.reader(fh) if any(cell.strip() for cell in row)]
        return max(len(rows) - 1, 0)
    if re.fullmatch(r"margao_inventory_\d+\.xml", name):
        return sum(1 for el in ET.parse(path).getroot().iter()
                   if local_name(el.tag) == "obj")
    if (re.fullmatch(r"ratnagiri_objects_\d+\.jsonl", name)
            or re.fullmatch(r"kolhapur_catalogue_\d+\.dat", name)):
        with open(path, "r", encoding="utf-8", newline="") as fh:
            return sum(1 for line in fh if line.strip())
    if re.fullmatch(r"kolhapur_index_\d+\.idx", name):
        return (os.path.getsize(path) - 12) // 44
    if name in ("legal_holds.psv", "collection_crosswalk.tsv"):
        with open(path, "r", encoding="utf-8", newline="") as fh:
            lines = fh.read().splitlines()
        return sum(1 for line in lines[1:] if line.strip())
    return None


def read_census(data_dir):
    """Check every file the census lists; return (entries, reasons)."""
    path = os.path.join(data_dir, "estate_census.toml")
    try:
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
    except (FileNotFoundError, tomllib.TOMLDecodeError, OSError):
        return [], ["MISSING:estate_census.toml"]
    entries, reasons = [], []
    for item in data.get("file", []):
        name = str(item["name"])
        expected_bytes = item.get("bytes")
        expected_sha = str(item.get("sha256") or "").lower()
        expected_records = item.get("records")
        fpath = os.path.join(data_dir, name)
        if not os.path.isfile(fpath):
            entries.append({"file": name, "present": False, "bytes_ok": False,
                            "sha256_ok": False, "records_expected": expected_records,
                            "records_seen": None})
            reasons.append("MISSING:%s" % name)
            continue
        digest = sha256_file(fpath)
        bytes_ok = expected_bytes is None or os.path.getsize(fpath) == int(expected_bytes)
        sha_ok = not expected_sha or digest == expected_sha
        records_seen, records_ok = None, True
        if expected_records is not None:
            records_seen = count_records(fpath, name)
            records_ok = records_seen is not None and records_seen == int(expected_records)
        if not bytes_ok:
            reasons.append("SIZE:%s" % name)
        if not sha_ok:
            reasons.append("SHA256:%s" % name)
        if not records_ok:
            reasons.append("RECORDS:%s" % name)
        entries.append({"file": name, "present": True, "bytes_ok": bytes_ok,
                        "sha256_ok": sha_ok, "records_expected": expected_records,
                        "records_seen": records_seen})
    entries.sort(key=lambda e: e["file"])
    return entries, sorted(set(reasons))


# --------------------------------------------------------------------------
# catalogue, holds, licences
# --------------------------------------------------------------------------

def load_collections(data_dir):
    path = os.path.join(data_dir, "catalogue.db")
    uri = "file:%s?mode=ro" % path.replace("?", "%3f")
    con = sqlite3.connect(uri, uri=True)
    try:
        columns = [r[1] for r in con.execute("PRAGMA table_info(collection)")]
        wanted = {"collection_id", "segment", "retention_class", "ingest_year"}
        if not wanted.issubset(columns):
            raise RuntimeError("catalogue.db table collection lacks %s"
                               % sorted(wanted - set(columns)))
        cols = {}
        for cid, segment, rclass, year in con.execute(
                "SELECT collection_id, segment, retention_class, ingest_year "
                "FROM collection"):
            cols[cid] = {"segment": segment, "klass": rclass, "ingest_year": int(year)}
        return cols
    finally:
        con.close()


def parse_timestamp(text, ist_offset):
    """Calendar date of a time stamp, taken in Indian Standard Time."""
    text = text.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    stamp = datetime.datetime.fromisoformat(text)
    return stamp.astimezone(datetime.timezone(ist_offset)).date().isoformat()


def load_holds(data_dir, papers):
    """Read the hold register.

    An event counts on the IST date of its effective time. On one date a PLACE comes
    after any RELEASE of that date, and between events of the same action the higher
    event id comes later (legal hold FAQ, the item kept in force by charter 10).
    """
    path = os.path.join(data_dir, "legal_holds.psv")
    events = collections.defaultdict(list)
    with open(path, "r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh, delimiter="|"):
            cid = (row.get("collection") or "").strip()
            action = (row.get("action") or "").strip().upper()
            event_id = (row.get("event_id") or "").strip()
            eff = parse_timestamp(row.get("effective") or "", papers.ist_offset)
            num = re.search(r"(\d+)$", event_id)
            events[cid].append((eff, 0 if action == "RELEASE" else 1,
                                int(num.group(1)) if num else 0, action))
    for cid in events:
        events[cid].sort()
    return events


def held_collections(events, as_of):
    held = set()
    for cid, evs in events.items():
        last = None
        for eff, _rank, _num, action in evs:
            if eff <= as_of:
                last = action
        if last == "PLACE":
            held.add(cid)
    return held


def load_licences(data_dir):
    path = os.path.join(data_dir, "rights_register.xml")
    if not os.path.isfile(path):
        return []
    licences = []
    for el in ET.parse(path).getroot().iter():
        if local_name(el.tag) != "licence":
            continue
        licences.append({"id": el.get("id") or "",
                         "collection": (el.get("collection") or "").strip(),
                         "klass": (el.get("class_override") or "").strip(),
                         "from": el.get("from") or "",
                         "to": el.get("to") or ""})
    return licences


def in_window(as_of, window):
    """Charter 2: a window counts when the date lies between its ends, unless the
    window says its end date is excluded."""
    if not window["from"] <= as_of:
        return False
    return as_of < window["until"] if window.get("end_excluded") else as_of <= window["until"]


class ClassBook:
    """Retention classes and required vault counts of every collection on one date."""

    def __init__(self, as_of, catalogue, papers, licences):
        self.as_of = as_of
        self.klass = {}
        self.master_min = {}
        for cid, info in catalogue.items():
            klass = info["klass"]
            rights = papers.amendments["rights"]
            if rights and rights["from"] <= as_of and info["segment"] == rights["segment"]:
                override = None
                for lic in licences:                     # last applicable licence wins
                    if lic["collection"] == cid and lic["from"] <= as_of <= lic["to"]:
                        override = lic["klass"]
                if override:
                    klass = override
            split = papers.amendments["split"]
            if split and split["from"] <= as_of and klass == split["base"]:
                for branch in split["branches"]:
                    if "at_least" in branch and info["ingest_year"] >= branch["at_least"]:
                        klass = branch["class"]
                        break
                    if "before" in branch and info["ingest_year"] < branch["before"]:
                        klass = branch["class"]
                        break
            self.klass[cid] = klass
            base = papers.charter_min.get(klass)
            if base is None and split:
                for branch in split["branches"]:
                    if branch["class"] == klass:
                        base = branch["min"]
            if base is None:
                raise RuntimeError("no charter minimum for class %s" % klass)
            minimum = papers.amendments["minimum"]
            if (minimum and in_window(as_of, minimum)
                    and klass == minimum["class"]
                    and info["segment"] == minimum["segment"]):
                base = minimum["min"]
            self.master_min[cid] = base

    def required(self, cid, rendition):
        base = self.master_min[cid]
        if rendition == "master":
            return base
        if rendition == "mezzanine":
            return base - 1 if base - 1 > 1 else 1
        if rendition == "proxy":
            return 1
        raise RuntimeError("unknown rendition %r" % rendition)


# --------------------------------------------------------------------------
# vault exports
# --------------------------------------------------------------------------

class Row:
    __slots__ = ("vault", "path", "size", "digest", "collection", "rendition",
                 "catalogued", "node", "family", "file", "legacy", "sidecar")

    def __init__(self, vault, path, size, digest, collection, rendition,
                 catalogued=None, node=None, family="", file="", legacy=False):
        self.vault = vault
        self.path = path
        self.size = size
        self.digest = digest
        self.collection = collection
        self.rendition = rendition
        self.catalogued = catalogued
        self.node = node
        self.family = family
        self.file = file
        self.legacy = legacy
        self.sidecar = False

    def sort_path(self):
        return byte_key(self.path)


def read_kolhapur_shard(dat_path, idx_path, vault, family, papers):
    idx = papers.klh_index
    with open(idx_path, "rb") as fh:
        blob = fh.read()
    records = {}
    count = struct.unpack("<I", blob[idx["count_offset"]:idx["count_offset"] + 4])[0]
    for i in range(count):
        off = idx["header"] + i * idx["record"]
        seq = struct.unpack("<I", blob[off:off + idx["seq"]])[0]
        size = struct.unpack("<Q", blob[off + idx["seq"]:off + idx["seq"] + idx["size"]])[0]
        start = off + idx["seq"] + idx["size"]
        records[seq] = (size, blob[start:start + idx["digest"]].hex())
    cols = papers.klh_columns
    rows = []
    with open(dat_path, "r", encoding="utf-8", newline="") as fh:
        for line in fh:
            line = line.rstrip("\n").rstrip("\r")
            if not line.strip():
                continue

            def cut(field, line=line, cols=cols):
                start, end = cols[field]
                return line[start:end]

            seq = int(cut("seq"))
            if seq not in records:
                raise RuntimeError("index %s has no record for sequence %d"
                                   % (os.path.basename(idx_path), seq))
            size, digest = records[seq]
            code = cut("rendition").strip()
            if code not in papers.klh_rendition:
                raise RuntimeError("unknown Kolhapur rendition code %r" % code)
            raw_date = cut("catalogued")
            rows.append(Row(
                vault=vault,
                path=cut("path").rstrip(" "),
                size=size,
                digest=digest.lower(),
                collection=cut("collection").rstrip(" "),
                rendition=papers.klh_rendition[code],
                catalogued="%s-%s-%s" % (raw_date[0:4], raw_date[4:6], raw_date[6:8]),
                family=family,
                file=os.path.basename(dat_path),
            ))
    return rows


def decode_margao_digest(text, enc, papers):
    kind = papers.digest_encodings.get(enc)
    if kind == "base32":
        return base64.b32decode(text + "=" * ((-len(text)) % 8)).hex()
    if kind == "base64":
        return base64.b64decode(text).hex()
    raise RuntimeError("unknown Margao digest encoding %r" % enc)


def read_margao_shard(path, vault, family, papers):
    rows = []
    for el in ET.parse(path).getroot().iter():
        if local_name(el.tag) != "obj":
            continue
        digest = None
        for child in el.iter():
            if local_name(child.tag) == "digest":
                digest = decode_margao_digest((child.text or "").strip(),
                                              child.get("enc") or "", papers)
                break
        if digest is None:
            raise RuntimeError("Margao object %s carries no digest" % el.get("path"))
        rows.append(Row(
            vault=vault,
            path=el.get("path") or "",
            size=int(el.get("size")),
            digest=digest.lower(),
            collection=el.get("coll") or "",
            rendition=(el.get("form") or "").strip().lower(),
            catalogued=el.get("catalogued"),
            family=family,
            file=os.path.basename(path),
        ))
    return rows


def read_nashik_shard(path, vault, family):
    rows = []
    with open(path, "r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            rows.append(Row(
                vault=vault,
                path=row["object_path"],
                size=int(row["bytes"]),
                digest=row["sha256"].strip().lower(),
                collection=row["collection"].strip(),
                rendition=row["rendition"].strip().lower(),
                node=row.get("node"),
                family=family,
                file=os.path.basename(path),
            ))
    return rows


def read_ratnagiri_shard(path, vault, family):
    rows = []
    with open(path, "r", encoding="utf-8", newline="") as fh:
        for line in fh:
            if not line.strip():
                continue
            obj = json.loads(line)
            if obj.get("len_hex") is not None:
                size = int(str(obj["len_hex"]), 16)
            else:
                size = int(obj["len"])
            digest = str(obj["dg"]).strip()
            digest = digest.split(":", 1)[1] if ":" in digest else digest
            rows.append(Row(
                vault=vault,
                path=obj["p"],
                size=size,
                digest=digest.lower(),
                collection=str(obj["col"]).strip(),
                rendition=str(obj["kind"]).strip().lower(),
                family=family,
                file=os.path.basename(path),
            ))
    return rows


def load_rows(data_dir, papers):
    """Read every vault export shard; return (rows, names of the export files)."""
    rows, export_files = [], []
    for family, code, _cartridge, _block in papers.vault_profiles:
        pattern = re.compile(r"^%s_.*?(\d+)\.(dat|idx|xml|csv|jsonl)$"
                             % re.escape(family))
        shards = collections.defaultdict(dict)
        for name in sorted(os.listdir(data_dir)):
            m = pattern.match(name)
            if m:
                shards[shard_number(m.group(1))][m.group(2)] = name
        for shard in sorted(shards):
            exts = shards[shard]
            if "dat" in exts:
                idx_name = exts.get("idx")
                if idx_name is None:
                    candidates = [n for n in sorted(os.listdir(data_dir))
                                  if re.fullmatch(r"%s_[a-z]+_%s\.idx"
                                                  % (re.escape(family),
                                                     re.escape(shard)), n)]
                    if not candidates:
                        raise RuntimeError("no index shard for %s" % exts["dat"])
                    idx_name = candidates[0]
                rows += read_kolhapur_shard(os.path.join(data_dir, exts["dat"]),
                                            os.path.join(data_dir, idx_name),
                                            code, family, papers)
                export_files.append(exts["dat"])
            elif "xml" in exts:
                rows += read_margao_shard(os.path.join(data_dir, exts["xml"]),
                                          code, family, papers)
                export_files.append(exts["xml"])
            elif "csv" in exts:
                rows += read_nashik_shard(os.path.join(data_dir, exts["csv"]), code, family)
                export_files.append(exts["csv"])
            elif "jsonl" in exts:
                rows += read_ratnagiri_shard(os.path.join(data_dir, exts["jsonl"]),
                                             code, family)
                export_files.append(exts["jsonl"])
    rows.sort(key=lambda r: (r.vault, byte_key(r.path)))
    for row in rows:
        row.sidecar = (papers.sidecar_threshold is not None
                       and row.size < papers.sidecar_threshold)
    return rows, sorted(export_files)


def resolve_legacy(rows, papers):
    """Map legacy collection ids to current ids (charter 4, migration memo)."""
    by_legacy = collections.defaultdict(list)
    for legacy, current, effective in papers.crosswalk:
        if legacy:
            by_legacy[legacy].append((effective, current))
    for group in by_legacy.values():
        group.sort()
    for row in rows:
        coll = row.collection
        if not coll.startswith("KCB-"):
            continue
        row.legacy = True
        options = by_legacy.get(coll)
        if not options:
            raise RuntimeError("legacy collection id %s is not in the crosswalk" % coll)
        chosen = None
        for effective, current in options:
            if row.catalogued and effective <= row.catalogued:
                chosen = current
        if chosen is None:
            chosen = options[0][1]
        row.collection = chosen


def file_statistics(rows, export_files):
    """Per export file counts for the data quality report."""
    stats = {name: {"rows": 0, "sidecar_rows": 0, "legacy_collection_rows": 0,
                    "duplicate_rows": 0}
             for name in export_files}
    for row in rows:
        entry = stats.get(row.file)
        if entry is None:
            continue
        entry["rows"] += 1
        if row.sidecar:
            entry["sidecar_rows"] += 1
        if row.legacy:
            entry["legacy_collection_rows"] += 1
    return stats


def mark_duplicates(rows):
    """Charter 7.1: inside one vault the lowest object path is the primary replica."""
    groups = collections.defaultdict(list)
    for row in rows:
        if not row.sidecar:
            groups[(row.digest, row.vault)].append(row)
    duplicates = []
    for group in groups.values():
        group.sort(key=lambda r: r.sort_path())
        duplicates.extend(group[1:])
    return duplicates


# --------------------------------------------------------------------------
# planning
# --------------------------------------------------------------------------

class PlannedObject:
    __slots__ = ("digest", "rendition", "collections", "klass", "required", "held",
                 "under_replicated", "kept_vaults", "governing")


def plan_scenario(as_of, rows, catalogue, papers, book, held):
    """Plan one scenario; return (objects, kept, released, rows left out)."""
    planned, void_rows = [], []
    for row in rows:
        if row.sidecar:
            continue
        gone = papers.decommissioned.get(row.node) if row.node else None
        if gone and gone <= as_of:
            void_rows.append(row)
            continue
        planned.append(row)

    by_digest = collections.defaultdict(list)
    for row in planned:
        by_digest[row.digest].append(row)

    objects, kept, released = [], [], []
    for digest in sorted(by_digest):
        obj_rows = by_digest[digest]
        obj = PlannedObject()
        obj.digest = digest
        obj.rendition = obj_rows[0].rendition
        coll_ids = sorted(set(row.collection for row in obj_rows))
        obj.collections = coll_ids
        obj.held = any(cid in held for cid in coll_ids)
        best = None
        for cid in coll_ids:
            if cid not in catalogue:
                raise RuntimeError("collection %s is not in the catalogue" % cid)
            need = book.required(cid, obj.rendition)
            if best is None or need > best[0] or (need == best[0] and cid < best[1]):
                best = (need, cid)
        obj.required = best[0]
        obj.governing = best[1]
        obj.klass = book.klass[best[1]]

        primaries = {}
        for row in obj_rows:
            current = primaries.get(row.vault)
            if current is None or row.sort_path() < current.sort_path():
                primaries[row.vault] = row
        vaults_holding = sorted(primaries)
        obj.under_replicated = len(vaults_holding) < obj.required

        if obj.held:
            keep = {id(row) for row in obj_rows}
        elif obj.under_replicated:
            keep = {id(row) for row in primaries.values()}
        else:
            order = preference_order(obj.klass, papers)
            keep = {id(primaries[v])
                    for v in [v for v in order if v in primaries][:obj.required]}
        kept_vaults = set()
        for row in obj_rows:
            if id(row) in keep:
                kept.append(row)
                kept_vaults.add(row.vault)
            else:
                released.append(row)
        obj.kept_vaults = sorted(kept_vaults)
        objects.append(obj)
    return objects, kept, released, void_rows


def preference_order(klass, papers):
    if klass in papers.preferences:
        return papers.preferences[klass]
    if len(klass) > 2 and klass[:2] in papers.preferences:
        return papers.preferences[klass[:2]]
    raise RuntimeError("no vault preference order for class %s" % klass)


class Volume:
    __slots__ = ("label", "vault", "usable", "members", "used", "seq")

    def __init__(self, label, vault, usable, seq):
        self.label = label
        self.vault = vault
        self.usable = usable
        self.members = []
        self.used = 0
        self.seq = seq

    def add(self, path, footprint_bytes):
        self.members.append((path, footprint_bytes))
        self.used += footprint_bytes


def footprint(row, papers, block_size):
    return papers.tape_header_bytes + -(-row.size // block_size) * block_size


def usable_bytes(papers, cartridge):
    if cartridge not in papers.cartridge_native:
        raise RuntimeError("cartridge %s is not in the media catalogue" % cartridge)
    return papers.cartridge_native[cartridge] - papers.cartridge_reserve.get(cartridge, 0)


def label_for(vault, seq, papers):
    return "%s-%s" % (vault, str(seq).zfill(papers.label_digits))


def pack_new(rows, papers, block_size, usable, vault, first_seq):
    """Fill fresh volumes in the order set by the volume layout note."""
    ordered = sorted(rows, key=lambda r: (-footprint(r, papers, block_size),
                                          r.digest, r.sort_path()))
    volumes = []
    for row in ordered:
        size = footprint(row, papers, block_size)
        for vol in volumes:
            if vol.used + size <= vol.usable:
                vol.add(row.path, size)
                break
        else:
            vol = Volume(None, vault, usable, first_seq + len(volumes))
            vol.label = label_for(vault, vol.seq, papers)
            vol.add(row.path, size)
            volumes.append(vol)
    return volumes


def build_volumes(vault, kept, papers, prior_volumes):
    """Pack the kept replicas of one vault, carrying surviving prior volumes over."""
    cartridge = block = None
    for _family, code, cart, blk in papers.vault_profiles:
        if code == vault:
            cartridge, block = cart, blk
            break
    if cartridge is None:
        raise RuntimeError("vault %s has no profile" % vault)
    usable = usable_bytes(papers, cartridge)
    if not prior_volumes:
        return pack_new(kept, papers, block, usable, vault, 1)
    kept_paths = {row.path: row for row in kept}
    max_seq = 0
    for vol in prior_volumes:
        found = re.search(r"(\d+)$", str(vol.get("label") or ""))
        if found:
            max_seq = max(max_seq, int(found.group(1)))
    carried = []
    for vol in prior_volumes:
        paths = [member[0] for member in vol.get("members", [])]
        if paths and all(path in kept_paths for path in paths):
            new = Volume(vol.get("label"), vault, usable, None)
            for path in paths:
                new.add(path, footprint(kept_paths[path], papers, block))
            carried.append(new)
    on_carried = {path for vol in carried for path, _fp in vol.members}
    # the members of a dissolved volume go back into the pool together with every
    # kept replica that was on no prior volume
    pool = [row for row in kept if row.path not in on_carried]
    pool.sort(key=lambda r: r.sort_path())
    return carried + pack_new(pool, papers, block, usable, vault, max_seq + 1)


def volume_json(vol, papers):
    return {"label": vol.label,
            "vault": vol.vault,
            "usable_bytes": vol.usable,
            "used_bytes": vol.used,
            "fill_bps": round_half_even(vol.used * papers.fill_basis, vol.usable),
            "members": [[path, fp] for path, fp in vol.members]}


def load_prior_volumes(prior_dir, scenario, vault):
    if not prior_dir:
        return None
    path = os.path.join(prior_dir, "scenario_%s.json" % scenario)
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return [v for v in data.get("volumes", []) if v.get("vault") == vault]


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def write_json(out_dir, name, payload):
    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)
    with open(os.path.join(out_dir, name), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
        fh.write("\n")


def read_run_control(data_dir):
    """Return (plan id, [(scenario name, as_of date)])."""
    path = os.path.join(data_dir, "run_control.json")
    if not os.path.isfile(path):
        return None, []
    try:
        control = json.loads(read_text(path))
    except (ValueError, OSError):
        return None, []
    raw = control.get("scenarios")
    scenarios = []
    if isinstance(raw, dict):
        for name in raw:
            as_of = raw[name].get("as_of") if isinstance(raw[name], dict) else None
            if as_of:
                scenarios.append((str(name), str(as_of)))
    return control.get("plan_id"), scenarios


def main(argv=None):
    ap = argparse.ArgumentParser(description="KCBA archive desk planner")
    ap.add_argument("--data", required=True, help="folder holding this cycle's export")
    ap.add_argument("--out", required=True, help="folder to write the plan into")
    ap.add_argument("--prior", default=None,
                    help="output folder of an earlier run of the planner")
    args = ap.parse_args(argv)
    data_dir = os.path.abspath(args.data)
    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)

    plan_id, scenarios = read_run_control(data_dir)
    census, reasons = read_census(data_dir)

    if reasons:
        write_json(out_dir, "perf_report.json", {
            "plan_id": plan_id,
            "status": "HELD",
            "reasons": reasons,
            "census": census,
            "scenarios": [],
        })
        return 0

    papers = load_papers(data_dir)
    catalogue = load_collections(data_dir)
    events = load_holds(data_dir, papers)
    licences = load_licences(data_dir)
    rows, export_files = load_rows(data_dir, papers)
    resolve_legacy(rows, papers)
    file_stats = file_statistics(rows, export_files)
    for row in mark_duplicates(rows):
        file_stats[row.file]["duplicate_rows"] += 1

    vault_codes = [code for _family, code, _cart, _blk in papers.vault_profiles]
    scenario_files, bottleneck, recommendations = {}, {}, {}
    report_scenarios, void_counts = [], {}

    for name, as_of in sorted(scenarios, key=lambda s: (s[1], s[0])):
        book = ClassBook(as_of, catalogue, papers, licences)
        held = held_collections(events, as_of)
        objects, kept, released, void_rows = plan_scenario(
            as_of, rows, catalogue, papers, book, held)

        keep_set = {id(row) for row in kept}
        volumes = []
        per_vault = {code: {"volumes": 0, "used_bytes": 0, "kept_replicas": 0}
                     for code in vault_codes}
        for code in vault_codes:
            kept_here = [row for row in kept if row.vault == code]
            volumes += build_volumes(code, kept_here, papers,
                                     load_prior_volumes(args.prior, name, code))
            per_vault[code]["kept_replicas"] = len(kept_here)
        for vol in volumes:
            per_vault[vol.vault]["volumes"] += 1
            per_vault[vol.vault]["used_bytes"] += vol.used

        scenario_files[name] = {
            "plan_id": plan_id,
            "scenario": name,
            "as_of": as_of,
            "objects": [{"digest": o.digest, "rendition": o.rendition,
                         "collections": o.collections, "class": o.klass,
                         "required": o.required, "held": o.held,
                         "under_replicated": o.under_replicated,
                         "kept_vaults": o.kept_vaults}
                        for o in objects],
            "replicas": [{"vault": r.vault, "path": r.path, "digest": r.digest,
                          "bytes": r.size, "collection": r.collection,
                          "rendition": r.rendition, "keep": id(r) in keep_set}
                         for r in sorted(kept + released,
                                         key=lambda r: (r.vault, r.sort_path()))],
            "volumes": [volume_json(v, papers) for v in volumes],
        }
        bottleneck[name] = {
            "under_replicated_objects": sum(1 for o in objects if o.under_replicated),
            "held_objects": sum(1 for o in objects if o.held),
            "vaults": per_vault,
        }
        by_vault = {code: 0 for code in vault_codes}
        by_segment = {}
        for row in released:
            by_vault[row.vault] += row.size
            segment = catalogue[row.collection]["segment"]
            by_segment[segment] = by_segment.get(segment, 0) + row.size
        for segment in ("commercial", "public"):
            by_segment.setdefault(segment, 0)
        recommendations[name] = {"release_replicas": len(released),
                                 "reclaim_bytes_by_vault": by_vault,
                                 "reclaim_bytes_by_segment": by_segment}
        report_scenarios.append({"name": name, "as_of": as_of, "objects": len(objects),
                                 "kept_replicas": len(kept),
                                 "released_replicas": len(released),
                                 "volumes": len(volumes)})
        void_counts[name] = len(void_rows)

    for name in sorted(scenario_files):
        write_json(out_dir, "scenario_%s.json" % name, scenario_files[name])
    write_json(out_dir, "bottleneck_analysis.json",
               {"plan_id": plan_id, "scenarios": bottleneck})
    write_json(out_dir, "recommendations.json",
               {"plan_id": plan_id, "scenarios": recommendations})
    write_json(out_dir, "data_quality.json",
               {"plan_id": plan_id, "files": file_stats, "void_node_rows": void_counts})
    shares = {}
    for cartridge, native in papers.cartridge_native.items():
        shares[cartridge] = round_half_even(
            papers.cartridge_reserve.get(cartridge, 0) * papers.fill_basis, native)
    write_json(out_dir, "perf_report.json", {
        "plan_id": plan_id,
        "status": "PUBLISHED",
        "reasons": [],
        "census": census,
        "scenarios": report_scenarios,
        "media_shares": shares,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
