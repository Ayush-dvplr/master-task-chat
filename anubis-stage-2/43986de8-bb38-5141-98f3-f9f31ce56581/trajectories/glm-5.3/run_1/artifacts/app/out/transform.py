#!/usr/bin/env python3
"""Close the ledger of a household budgeting extract and run its month-end sweep.

Usage: python3 transform.py DATA_DIR OUT_DIR
"""

import configparser
import csv
import hashlib
import io
import json
import os
import re
import sqlite3
import sys
import urllib.parse
import zipfile
import zlib
from datetime import date, timedelta
from xml.etree import ElementTree

DISTRICTS = ("central", "east", "north", "south", "west")
DISTRICT_RANK = {name: index for index, name in enumerate(DISTRICTS)}
SHEET_COLUMNS = ("damping_percent", "patience", "round_budget")
PLAN_RATES = tuple(range(12, 51))
SEARCH_BUDGET = 600000
NS_SPREAD = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
NS_WORD = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
NS_PACKAGE = "{http://schemas.openxmlformats.org/package/2006/relationships}"
NS_OFFICE = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
TXC_EPOCH = date(2026, 8, 31)
ZIP_STAMP = (1980, 1, 1, 0, 0, 0)


class DataError(Exception):
    """The extract breaks a rule of the inputs that std_ledger.md lists."""


def fail(message):
    raise DataError(message)


def round_half_zero(num, den):
    """num over den taken to the nearest whole number, halfway values toward zero."""
    if num < 0:
        return -round_half_zero(-num, den)
    whole, rest = divmod(num, den)
    return whole + 1 if 2 * rest > den else whole


def parse_date(text, where):
    match = re.match(r"^([0-9]{4})-([0-9]{2})-([0-9]{2})$", text)
    if match is None:
        fail("%s is not written as YYYY-MM-DD: %r" % (where, text))
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        fail("%s is not a calendar date: %r" % (where, text))


def read_ascii(path):
    with open(path, "r", encoding="ascii", newline="") as handle:
        return handle.read()


def read_bytes(path):
    with open(path, "rb") as handle:
        return handle.read()


def read_rows(path, delimiter):
    """The data rows of a delimited text file as dicts keyed by its header row."""
    reader = csv.reader(io.StringIO(read_ascii(path), newline=""), delimiter=delimiter)
    table = [row for row in reader if row]
    if not table:
        fail("%s holds no header row" % os.path.basename(path))
    header = table[0]
    rows = []
    for values in table[1:]:
        if len(values) < len(header):
            values = values + [""] * (len(header) - len(values))
        rows.append(dict(zip(header, values)))
    return rows


def load_config(data_dir):
    """office.ini: the period, the cutoff sequence and the sweep's parameter sheet."""
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(os.path.join(data_dir, "office.ini"), encoding="ascii")
    if not parser.has_section("period"):
        fail("office.ini holds no [period] section")
    first_day = parse_date(parser.get("period", "first_day"), "office.ini first_day")
    last_day = parse_date(parser.get("period", "last_day"), "office.ini last_day")
    if not parser.has_section("corrections"):
        fail("office.ini holds no [corrections] section")
    cutoff = int(parser.get("corrections", "cutoff_seq"))
    if not parser.has_section("sweep"):
        fail("office.ini holds no [sweep] section")
    config = {
        "first_day": first_day,
        "last_day": last_day,
        "cutoff": cutoff,
        "sheet": parser.get("sweep", "parameter_sheet"),
        "budget": {},
    }
    if parser.has_section("overrides"):
        for key, value in parser.items("overrides"):
            for district in DISTRICTS:
                for column in SHEET_COLUMNS:
                    if key.lower() == "%s_%s" % (district, column):
                        if column == "round_budget":
                            config["budget"][district] = int(value)
    return config


def canonical_row(row, crosswalk):
    return {crosswalk[key]: value for key, value in row.items() if key in crosswalk}


def envelope_record(fields, code):
    needed = ("file_no", "label", "category_code", "funding_code", "need_dollars", "opening_cents")
    for field in needed:
        if field not in fields:
            fail("the register gives envelope %r no %s" % (code, field))
    return {
        "code": code,
        "file_no": fields["file_no"],
        "label": fields["label"],
        "category_code": fields["category_code"],
        "funding_code": fields["funding_code"],
        "need": int(fields["need_dollars"]),
        "opening": int(fields["opening_cents"]),
    }


def load_envelopes(data_dir, crosswalk):
    """The envelope register of record, read through the crosswalk."""
    envelopes = {}
    for name, delimiter in (("env_a.csv", ","), ("env_b.tsv", "\t")):
        for row in read_rows(os.path.join(data_dir, name), delimiter):
            fields = canonical_row(row, crosswalk[name])
            code = fields["env_code"]
            envelopes[code] = envelope_record(fields, code)
    name = "env_c.jsonl"
    for line in read_ascii(os.path.join(data_dir, name)).splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            fail("%s holds a line that is not JSON" % name)
        fields = canonical_row(row, crosswalk[name])
        code = fields["env_code"]
        envelopes[code] = envelope_record(fields, code)
    if not envelopes:
        fail("the register of record holds no envelope")
    return envelopes


def open_core(path):
    uri = "file:" + urllib.parse.quote(os.path.abspath(path)) + "?mode=ro"
    return sqlite3.connect(uri, uri=True)


def load_core(data_dir):
    """The tables of hh_core.sqlite."""
    conn = open_core(os.path.join(data_dir, "hh_core.sqlite"))
    try:
        districts = list(conn.execute("select district_id, district_name from district"))
        households = list(conn.execute("select hh_code, family_name, district_id from household"))
        files = list(conn.execute("select file_no, hh_code from file"))
        plans = list(conn.execute("select env_code, plan from keep_plan"))
        aliases = list(conn.execute("select alias, env_code, since from env_alias"))
    finally:
        conn.close()
    core = {
        "district": {},
        "household": {},
        "file": {},
        "plan": {},
        "alias": {},
    }
    for district_id, district_name in districts:
        key = district_name.lower()
        if key not in DISTRICT_RANK:
            fail("the district table names a district the office does not keep: %r" % district_name)
        core["district"][district_id] = key
    for hh_code, family, district_id in households:
        if district_id not in core["district"]:
            fail("household %s sits in no district" % hh_code)
        core["household"][hh_code] = {"family": family, "district": core["district"][district_id]}
    for file_no, hh_code in files:
        core["file"][file_no] = hh_code
    for env_code, plan in plans:
        core["plan"][env_code.upper()] = plan
    for alias, env_code, since in aliases:
        core["alias"].setdefault(alias, []).append((env_code, since))
    for alias in core["alias"]:
        core["alias"][alias].sort(key=lambda item: item[1])
    return core


def pdf_escape(byte):
    table = {b"n": b"\n", b"r": b"\r", b"t": b"\t", b"b": b"\b", b"f": b"\f"}
    return table.get(byte, byte)


def pdf_strings(stream):
    """The literal strings of a PDF content stream, in order."""
    out = []
    index = 0
    while index < len(stream):
        if stream[index:index + 1] != b"(":
            index += 1
            continue
        index += 1
        depth = 1
        chunk = bytearray()
        while index < len(stream) and depth:
            char = stream[index:index + 1]
            if char == b"\\":
                nxt = stream[index + 1:index + 2]
                index += 2
                if nxt.isdigit():
                    digits = nxt
                    while len(digits) < 3 and stream[index:index + 1].isdigit():
                        digits += stream[index:index + 1]
                        index += 1
                    chunk.append(int(digits, 8) & 0xFF)
                else:
                    chunk.extend(pdf_escape(nxt))
                continue
            if char == b"(":
                depth += 1
            elif char == b")":
                depth -= 1
                if depth == 0:
                    break
            chunk.extend(char)
            index += 1
        out.append(chunk.decode("latin-1"))
    return out


def load_funding_segments(path):
    """fund_codes.pdf: each funding code and the segment it names."""
    raw = read_bytes(path)
    codes = {}
    for match in re.finditer(rb"stream\r\n|stream\n|stream\r", raw):
        start = match.end()
        stop = raw.find(b"endstream", start)
        if stop < 0:
            continue
        try:
            stream = zlib.decompress(raw[start:stop])
        except zlib.error:
            continue
        for line in pdf_strings(stream)[1:]:
            found = re.match(r"^(\S+) = (\S+)$", line)
            if found:
                codes[found.group(1)] = found.group(2)
    if not codes:
        fail("fund_codes.pdf gives no funding code")
    return codes


def docx_cell_text(cell):
    return "".join(node.text or "" for node in cell.iter(NS_WORD + "t"))


def load_categories(path):
    """cat_codes.docx: each category code and its category name."""
    with zipfile.ZipFile(path) as archive:
        root = ElementTree.fromstring(archive.read("word/document.xml"))
    table = root.find(".//" + NS_WORD + "tbl")
    if table is None:
        fail("cat_codes.docx holds no table")
    categories = {}
    rows = table.findall(".//" + NS_WORD + "tr")
    for row in rows:
        cells = [docx_cell_text(cell) for cell in row.findall(".//" + NS_WORD + "tc")]
        if len(cells) < 2 or (cells[0], cells[1]) == ("code", "category"):
            continue
        categories[cells[0]] = cells[1]
    if not categories:
        fail("cat_codes.docx gives no category code")
    return categories


def column_letters(reference):
    letters = "".join(char for char in reference if char.isalpha())
    if not letters:
        fail("a worksheet cell has no column reference: %r" % reference)
    return letters


def worksheet_rows(archive, target):
    """The rows of one worksheet as dicts keyed by their column letters."""
    root = ElementTree.fromstring(archive.read(target))
    rows = []
    for row in root.iter(NS_SPREAD + "row"):
        cells = {}
        for cell in row.iter(NS_SPREAD + "c"):
            if cell.get("t") == "inlineStr":
                value = "".join(node.text or "" for node in cell.iter(NS_SPREAD + "t"))
            else:
                node = cell.find(NS_SPREAD + "v")
                value = node.text if node is not None else ""
            cells[column_letters(cell.get("r"))] = value
        rows.append(cells)
    return rows


def workbook_sheets(path):
    """The worksheets of a SpreadsheetML workbook, in workbook order."""
    with zipfile.ZipFile(path) as archive:
        book = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        rels = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {}
    for node in rels.iter(NS_PACKAGE + "Relationship"):
        targets[node.get("Id")] = node.get("Target")
    sheets = []
    for node in book.iter(NS_SPREAD + "sheet"):
        target = targets.get(node.get(NS_OFFICE + "id"))
        if target is None:
            fail("sweep_tab.xlsx names a worksheet with no part: %r" % node.get("name"))
        if target.startswith("/"):
            part = target.lstrip("/")
        else:
            part = "xl/" + target
        sheets.append((node.get("name"), part))
    return sheets


def load_parameter_sheet(path, sheet_name):
    """The governing parameter sheet: each district's sweep parameters."""
    chosen = None
    for name, part in workbook_sheets(path):
        if name.lower() == sheet_name.lower():
            chosen = (name, part)
    if chosen is None:
        fail("sweep_tab.xlsx holds no worksheet named %r" % sheet_name)
    with zipfile.ZipFile(path) as archive:
        rows = worksheet_rows(archive, chosen[1])
    if not rows:
        fail("worksheet %s holds no header row" % sheet_name)
    header = {letters: text for letters, text in rows[0].items()}
    columns = {}
    for letters, text in header.items():
        if text in ("district",) + SHEET_COLUMNS:
            columns[text] = letters
    for column in ("district",) + SHEET_COLUMNS:
        if column not in columns:
            fail("worksheet %s gives no column %s" % (sheet_name, column))
    params = {}
    for cells in rows[1:]:
        name = cells.get(columns["district"], "")
        if not name:
            continue
        key = name.lower()
        if key not in DISTRICT_RANK:
            fail("worksheet %s names a district the office does not keep: %r" % (sheet_name, name))
        params[key] = {
            "damping_percent": int(cells.get(columns["damping_percent"], "")),
            "patience": int(cells.get(columns["patience"], "")),
            "round_budget": int(cells.get(columns["round_budget"], "")),
        }
    return params


class ByteReader:
    """A cursor over a binary export."""

    def __init__(self, data, position):
        self.data = data
        self.pos = position

    def byte(self):
        if self.pos >= len(self.data):
            fail("tx_c.bin ends inside a record")
        value = self.data[self.pos]
        self.pos += 1
        return value

    def varint(self):
        result = 0
        shift = 0
        while True:
            chunk = self.byte()
            result |= (chunk & 0x7F) << shift
            if not chunk & 0x80:
                return result
            shift += 7

    def zigzag(self):
        value = self.varint()
        return value >> 1 if not value & 1 else -((value + 1) >> 1)

    def raw(self, count):
        if self.pos + count > len(self.data):
            fail("tx_c.bin ends inside a record")
        part = self.data[self.pos:self.pos + count]
        self.pos += count
        return part


def parse_tx_c(path):
    """tx_c.bin: every record of the export."""
    raw = read_bytes(path)
    if len(raw) < 11:
        fail("tx_c.bin is too short to hold a header and a trailer")
    if raw[:4] != b"TXC1":
        fail("tx_c.bin does not start with the bytes TXC1")
    trailer = int.from_bytes(raw[-4:], "big")
    if zlib.crc32(raw[:-4]) != trailer:
        fail("the checksum of tx_c.bin does not match its trailer")
    reader = ByteReader(raw, 7)
    stop = len(raw) - 4
    records = []
    dictionary = []
    previous = {"env": None, "day": None}
    while reader.pos < stop:
        start = reader.pos
        selector = reader.byte()
        mode = selector & 0x03
        if mode == 3:
            fail("tx_c.bin holds a record of mode 3")
        malformed = bool(selector & 0x04)
        txn = "T%05d" % reader.varint()
        if mode == 0:
            length = reader.byte()
            try:
                env = reader.raw(length).decode("ascii")
            except UnicodeDecodeError:
                fail("tx_c.bin holds an envelope code that is not ASCII")
            day = reader.zigzag()
            if env.upper() not in {code.upper() for code in dictionary}:
                dictionary.append(env)
        elif mode == 1:
            env = previous["env"]
            day = previous["day"] + reader.zigzag()
        else:
            position = reader.byte()
            if position >= len(dictionary):
                fail("tx_c.bin holds a back-reference to no dictionary entry")
            env = dictionary[len(dictionary) - 1 - position]
            day = reader.zigzag()
        cents = None
        if not malformed:
            cents = reader.zigzag()
        records.append({
            "txn": txn,
            "day": TXC_EPOCH + timedelta(days=day),
            "env": env,
            "cents": cents,
            "malformed": malformed,
            "source": "tx_c.bin",
        })
        previous = {"env": env, "day": day}
    return records


def load_tx_a(path):
    """tx_a.csv, laid out as dict_tx.md gives."""
    rows = []
    for row in read_rows(path, ","):
        cents = row.get("cents", "")
        direction = row.get("dir", "")
        magnitude = int(cents) if re.match(r"^[0-9]+$", cents) else None
        if direction not in ("in", "out"):
            magnitude = None
        rows.append({
            "txn": row.get("txn", ""),
            "day": parse_date(row.get("day", ""), "tx_a.csv day"),
            "env": row.get("env", ""),
            "direction": 1 if direction == "in" else -1,
            "magnitude": magnitude,
            "malformed": magnitude is None,
            "source": "tx_a.csv",
        })
    return rows


def load_tx_b(path, aliases):
    """tx_b.tsv, whose rows name their envelope by an alias."""
    rows = []
    for row in read_rows(path, "\t"):
        amount = row.get("amount", "")
        kind = row.get("kind", "")
        magnitude = None
        if re.match(r"^[0-9]+\.[0-9]{2}$", amount) and kind in ("D", "S"):
            whole, rest = amount.split(".")
            magnitude = int(whole) * 100 + int(rest)
        alias = row.get("alias", "")
        day = parse_date(row.get("posted", ""), "tx_b.tsv posted")
        rows.append({
            "txn": row.get("id", ""),
            "day": day,
            "env": resolve_alias(aliases, alias, day),
            "direction": 1 if kind == "D" else -1,
            "magnitude": magnitude,
            "malformed": magnitude is None,
            "source": "tx_b.tsv",
        })
    return rows


def resolve_alias(aliases, alias, day):
    """The envelope code the alias names on a date."""
    best = None
    for env_code, since in aliases.get(alias, ()):
        if parse_date(since, "env_alias since") <= day and (best is None or since > best[1]):
            best = (env_code, since)
    if best is None:
        fail("the alias %r names no envelope on %s" % (alias, day.isoformat()))
    return best[0]


def load_tx_c(path):
    records = parse_tx_c(path)
    rows = []
    for record in records:
        cents = record["cents"]
        rows.append({
            "txn": record["txn"],
            "day": record["day"],
            "env": record["env"],
            "direction": 1 if cents is None or cents >= 0 else -1,
            "magnitude": None if cents is None else abs(cents),
            "malformed": record["malformed"],
            "source": "tx_c.bin",
        })
    return rows


def load_transactions(data_dir, core, envelopes):
    """The three transaction exports, tied to their envelopes."""
    sources = (
        ("tx_a.csv", lambda: load_tx_a(os.path.join(data_dir, "tx_a.csv"))),
        ("tx_b.tsv", lambda: load_tx_b(os.path.join(data_dir, "tx_b.tsv"), core["alias"])),
        ("tx_c.bin", lambda: load_tx_c(os.path.join(data_dir, "tx_c.bin"))),
    )
    index = {code.upper(): code for code in envelopes}
    rows = []
    for name, loader in sources:
        for row in loader():
            if row["env"].upper() not in index:
                fail("a row of %s names no envelope of the register: %r" % (name, row["env"]))
            row["env"] = index[row["env"].upper()]
            row["voided"] = False
            rows.append(row)
    seen = {}
    for row in rows:
        if row["txn"] in seen:
            fail("transaction id %s appears in more than one row" % row["txn"])
        seen[row["txn"]] = row
    return rows, seen


def period_flags(rows, first_day, last_day):
    """Mark each well-formed row that lies out of period."""
    for row in rows:
        row["out_of_period"] = not row["malformed"] and not first_day <= row["day"] <= last_day


def load_corrections(data_dir):
    rows = read_rows(os.path.join(data_dir, "adj_log.psv"), "|")
    corrections = []
    for row in rows:
        action = row.get("action", "")
        if action not in ("void", "amend"):
            fail("a correction of adj_log.psv has no known action: %r" % action)
        value = row.get("value", "")
        if action == "amend" and not re.match(r"^[0-9]+$", value):
            fail("an amend correction gives no magnitude in cents: %r" % value)
        corrections.append({
            "seq": int(row.get("seq", "")),
            "txn": row.get("txn", ""),
            "action": action,
            "value": int(value) if action == "amend" else None,
        })
    return corrections


def apply_corrections(corrections, by_txn, cutoff):
    """The corrections at or below the cutoff sequence, in ascending sequence."""
    applied = []
    for correction in corrections:
        if correction["seq"] > cutoff:
            continue
        if correction["txn"] not in by_txn:
            fail("correction %d names no transaction of the exports: %r"
                 % (correction["seq"], correction["txn"]))
        applied.append(correction)
    applied.sort(key=lambda item: item["seq"])
    for correction in applied:
        row = by_txn[correction["txn"]]
        if row["malformed"] or row["out_of_period"] or row["voided"]:
            continue
        if correction["action"] == "void":
            row["voided"] = True
        else:
            row["magnitude"] = correction["value"]
    return len(applied)


def rate_constraints(envelopes, fee_rows):
    """One (target, items) pair per row of the bank's fee statement."""
    constraints = []
    for row in fee_rows:
        ref = row.get("client_ref", "")
        target = int(row.get("charge_cents", ""))
        items = []
        for envelope in envelopes.values():
            if (envelope["hh"] == ref or envelope["funding_code"] == ref
                    or envelope["category_code"] == ref):
                items.append((envelope["opening"], envelope["plan"]))
        constraints.append((target, items))
    return constraints


def plan_groups(constraints):
    """Each constraint's items grouped by keeping plan."""
    grouped = []
    for target, items in constraints:
        plans = {}
        for opening, plan in items:
            plans.setdefault(plan, []).append(opening)
        grouped.append({"target": target, "groups": sorted(plans.items())})
    return grouped


class RateSearch:
    """A depth first search for the keeping rates the statement allows."""

    def __init__(self, plans, grouped):
        self.plans = plans
        self.grouped = grouped
        self.rates = {}
        self.solutions = []
        self.nodes = 0
        self.by_plan = {}
        self.charges = {}
        for index, constraint in enumerate(grouped):
            for plan, openings in constraint["groups"]:
                self.by_plan.setdefault(plan, []).append(index)
                self.charges[(plan, index)] = tuple(
                    sum(round_half_zero(opening * rate, 10000) for opening in openings)
                    for rate in PLAN_RATES)

    def charge(self, plan, index):
        """What the plan adds to one fee row at each rate of the range."""
        return self.charges[(plan, index)]

    def unsettled(self, constraint):
        return [plan for plan, _ in constraint["groups"] if plan not in self.rates]

    def holds(self, index):
        """May the settled rates stand against one fee row?"""
        constraint = self.grouped[index]
        total = 0
        low = 0
        high = 0
        for plan, _ in constraint["groups"]:
            charges = self.charge(plan, index)
            if plan in self.rates:
                total += charges[self.rates[plan] - 12]
            else:
                low += charges[0]
                high += charges[-1]
        return total + low <= constraint["target"] <= total + high

    def settled_total(self, index):
        """What the settled plans of one fee row add up to."""
        total = 0
        for plan, _ in self.grouped[index]["groups"]:
            if plan in self.rates:
                total += self.charge(plan, index)[self.rates[plan] - 12]
        return total

    def domain(self, plan):
        """The rates this plan may still take at this point of the search."""
        allowed = list(PLAN_RATES)
        for index in self.by_plan.get(plan, ()):
            constraint = self.grouped[index]
            if self.unsettled(constraint) != [plan]:
                continue
            need = constraint["target"] - self.settled_total(index)
            charges = self.charge(plan, index)
            allowed = [rate for rate in allowed if charges[rate - 12] == need]
        return allowed

    def pick(self):
        """The plan to settle next: the one whose rates are pinned narrowest."""
        best = None
        best_key = None
        for plan in self.plans:
            if plan in self.rates:
                continue
            counts = [len(self.unsettled(self.grouped[index]))
                      for index in self.by_plan.get(plan, ())]
            room = min(counts) if counts else len(self.plans)
            key = (len(self.domain(plan)), room, plan)
            if best_key is None or key < best_key:
                best, best_key = plan, key
        return best

    def dive(self):
        self.nodes += 1
        if self.nodes > SEARCH_BUDGET:
            fail("the keeping rates of the statement did not settle within the search budget")
        if len(self.solutions) > 1:
            return
        if len(self.rates) == len(self.plans):
            self.solutions.append(dict(self.rates))
            return
        plan = self.pick()
        for rate in self.domain(plan):
            self.rates[plan] = rate
            if all(self.holds(index) for index in self.by_plan.get(plan, ())):
                self.dive()
            del self.rates[plan]


def solve_rates(plans, constraints):
    """The one assignment of a rate to every keeping plan that meets the statement."""
    grouped = plan_groups(constraints)
    for constraint in grouped:
        if not constraint["groups"] and constraint["target"] != 0:
            return None
    search = RateSearch(sorted(plans), grouped)
    search.dive()
    if len(search.solutions) == 1:
        return search.solutions[0]
    return None


def settle_envelopes(envelopes, core):
    """Tie every envelope to its household, its plan and its code tables."""
    for envelope in envelopes.values():
        key = envelope["code"].upper()
        file_no = envelope["file_no"]
        if file_no not in core["file"]:
            fail("envelope %s sits in no folder of the file table" % envelope["code"])
        hh_code = core["file"][file_no]
        if hh_code not in core["household"]:
            fail("folder %s belongs to no household" % file_no)
        envelope["hh"] = hh_code
        envelope["district"] = core["household"][hh_code]["district"]
        if key not in core["plan"]:
            fail("envelope %s belongs to no keeping plan" % envelope["code"])
        envelope["plan"] = core["plan"][key]


def name_codes(envelopes, segments, categories):
    for envelope in envelopes.values():
        if envelope["funding_code"] not in segments:
            fail("fund_codes.pdf gives no segment for %s" % envelope["funding_code"])
        if envelope["category_code"] not in categories:
            fail("cat_codes.docx gives no category for %s" % envelope["category_code"])
        envelope["segment"] = segments[envelope["funding_code"]]
        envelope["category"] = categories[envelope["category_code"]]


def close_ledger(envelopes, rows, rates, statement_day):
    """The pre-sweep balance of every envelope, once the ledger has closed."""
    for envelope in envelopes.values():
        envelope["applied_cents"] = 0
        envelope["statement_cents"] = envelope["opening"]
    for row in rows:
        if row["malformed"] or row["out_of_period"] or row["voided"]:
            continue
        cents = row["direction"] * row["magnitude"]
        envelope = envelopes[row["env"]]
        envelope["applied_cents"] += cents
        if row["day"] <= statement_day:
            envelope["statement_cents"] += cents
    for envelope in envelopes.values():
        rate = rates[envelope["plan"]]
        charge = round_half_zero(envelope["statement_cents"] * rate, 1000000)
        closing = envelope["opening"] + envelope["applied_cents"]
        envelope["statement_cents"] = max(0, envelope["statement_cents"])
        envelope["closing_cents"] = max(0, closing)
        envelope["presweep"] = max(0, envelope["closing_cents"] // 100 - charge)


def sweep_targets(pool, needs, balances):
    """The gap of every envelope of one household."""
    claims = [need + (need - balance if need > balance else 0)
              for need, balance in zip(needs, balances)]
    total = sum(claims)
    return [round_half_zero(pool * claim, total) - balance
            for claim, balance in zip(claims, balances)]


def adjustment_index(codes, labels, gaps):
    """The envelope that takes the balancing adjustment."""
    best = 0
    for index in range(1, len(gaps)):
        wider = abs(gaps[index]) > abs(gaps[best])
        earlier = (abs(gaps[index]) == abs(gaps[best])
                   and labels[codes[index]] < labels[codes[best]])
        if wider or earlier:
            best = index
    return best


def is_lower(left, right):
    for first, second in zip(left, right):
        if first != second:
            return first < second
    return False


def lowest_state(states):
    best = states[0]
    for state in states[1:]:
        if is_lower(state, best):
            best = state
    return list(best)


def sweep_result(exit_name, rounds, rate, balances, rows):
    return {
        "exit": exit_name,
        "rounds": rounds,
        "damping_percent": rate,
        "final": list(balances),
        "round_rows": rows,
    }


def sweep_household(house, params):
    """The month-end sweep of one household."""
    codes = sorted(house)
    needs = [house[code]["need"] for code in codes]
    labels = {code: house[code]["label"] for code in codes}
    balances = [house[code]["presweep"] for code in codes]
    pool = sum(balances)
    rate = params["damping_percent"]
    patience = params["patience"]
    strikes = 0
    rounds = 0
    previous = None
    states = [tuple(balances)]
    seen = {tuple(balances): 0}
    rows = []
    while True:
        gaps = sweep_targets(pool, needs, balances)
        spread = sum(abs(gap) for gap in gaps)
        if spread == 0:
            return sweep_result("settled", rounds, rate, balances, rows)
        if previous is not None and spread >= previous:
            strikes += 1
            if strikes == patience:
                rate //= 2
                strikes = 0
        drafts = [round_half_zero(gap * rate, 100) for gap in gaps]
        rounds += 1
        if not any(drafts):
            rows.append((rounds, spread, rate, strikes, 0))
            return sweep_result("stalled", rounds, rate, balances, rows)
        posted = list(drafts)
        posted[adjustment_index(codes, labels, gaps)] -= sum(drafts)
        moved = sum(amount for amount in posted if amount > 0)
        rows.append((rounds, spread, rate, strikes, moved))
        balances = [balance + amount for balance, amount in zip(balances, posted)]
        state = tuple(balances)
        if state in seen:
            return sweep_result("cycling", rounds, rate,
                                lowest_state(states[seen[state]:]), rows)
        states.append(state)
        seen[state] = len(states) - 1
        previous = spread
        if rounds == params["round_budget"]:
            return sweep_result("budget", rounds, rate, balances, rows)


def ordered(value):
    """Every object's keys in code point order, at every level."""
    if isinstance(value, dict):
        return {key: ordered(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [ordered(item) for item in value]
    return value


def dumps_json(payload):
    return json.dumps(ordered(payload), indent=2, ensure_ascii=True, separators=(",", ": ")) + "\n"


def write_text(path, text):
    with open(path, "w", encoding="ascii", newline="") as handle:
        handle.write(text)


def lines_text(lines):
    return "".join(line + "\n" for line in lines)


def csv_line(values, delimiter):
    """One row of a delimited report, quoted as RFC 4180 gives."""
    buffer = io.StringIO(newline="")
    csv.writer(buffer, delimiter=delimiter, lineterminator="").writerow(values)
    return buffer.getvalue()


def moved_dollars(envelopes, codes):
    total = 0
    for code in codes:
        envelope = envelopes[code]
        gain = envelope["final"] - envelope["presweep"]
        total += gain if gain > 0 else 0
    return total


def load_prior(path):
    payload = json.loads(read_ascii(path))
    return payload.get("households", {})


def build_model(data_dir):
    """Close the ledger and sweep every household of the extract."""
    config = load_config(data_dir)
    crosswalk = json.loads(read_ascii(os.path.join(data_dir, "xw_columns.json")))
    core = load_core(data_dir)
    envelopes = load_envelopes(data_dir, crosswalk)
    settle_envelopes(envelopes, core)
    segments = load_funding_segments(os.path.join(data_dir, "fund_codes.pdf"))
    categories = load_categories(os.path.join(data_dir, "cat_codes.docx"))
    name_codes(envelopes, segments, categories)
    rows, by_txn = load_transactions(data_dir, core, envelopes)
    period_flags(rows, config["first_day"], config["last_day"])
    corrections = load_corrections(data_dir)
    applied_count = apply_corrections(corrections, by_txn, config["cutoff"])
    fee_rows = read_rows(os.path.join(data_dir, "stmt_fees.csv"), ",")
    if not fee_rows:
        fail("stmt_fees.csv holds no row")
    statement_day = parse_date(fee_rows[0]["through"], "stmt_fees.csv through")
    plans = sorted({envelope["plan"] for envelope in envelopes.values()})
    rates = solve_rates(plans, rate_constraints(envelopes, fee_rows))
    if rates is None:
        fail("no one assignment of keeping rates meets every row of stmt_fees.csv")
    close_ledger(envelopes, rows, rates, statement_day)
    params = load_parameter_sheet(os.path.join(data_dir, "sweep_tab.xlsx"), config["sheet"])
    model = {
        "config": config,
        "core": core,
        "envelopes": envelopes,
        "rows": rows,
        "quality": export_quality(rows),
        "corrections": {"applied": applied_count,
                        "past_cutoff": len(corrections) - applied_count},
        "households": {},
        "statement_day": statement_day,
        "rates": rates,
    }
    for district in DISTRICTS:
        if district not in params:
            fail("the parameter sheet gives no row for the %s district" % district)
        house = {code: env for code, env in envelopes.items() if env["district"] == district}
        if not house:
            fail("no envelope of the extract sits in the %s district" % district)
        settings = dict(params[district])
        if district in config["budget"]:
            settings["round_budget"] = config["budget"][district]
        model["households"][district] = sweep_household(house, settings)
        assign_final(model, district, house)
    model["prior"] = load_prior(os.path.join(data_dir, "prior_sweep.json"))
    return model


def assign_final(model, district, house):
    result = model["households"][district]
    codes = sorted(house)
    for index, code in enumerate(codes):
        house[code]["final"] = result["final"][index]
    result["codes"] = codes
    result["moved"] = moved_dollars(model["envelopes"], codes)
    result["pool"] = sum(house[code]["presweep"] for code in codes)
    hh_code = house[codes[0]]["hh"]
    result["hh"] = hh_code
    result["family"] = model["core"]["household"][hh_code]["family"]


def export_quality(rows):
    """The input-quality counts of every transaction export."""
    quality = {}
    for source in ("tx_a.csv", "tx_b.tsv", "tx_c.bin"):
        quality[source] = {"rows": 0, "malformed": 0, "out_of_period": 0,
                           "applied": 0, "voided": 0}
    for row in rows:
        counts = quality[row["source"]]
        counts["rows"] += 1
        if row["malformed"]:
            counts["malformed"] += 1
        elif row["out_of_period"]:
            counts["out_of_period"] += 1
        elif row["voided"]:
            counts["voided"] += 1
        else:
            counts["applied"] += 1
    return quality


def xml_escape(text):
    for old, new in (("&", "&amp;"), ("<", "&lt;"), (">", "&gt;"), ('"', "&quot;")):
        text = text.replace(old, new)
    return text


def ordered_envelopes(model):
    """Every envelope of the extract, by district and then envelope code."""
    return sorted(model["envelopes"].values(),
                  key=lambda env: (DISTRICT_RANK[env["district"]], env["code"]))


def applied_rows(model):
    return [row for row in model["rows"]
            if not (row["malformed"] or row["out_of_period"] or row["voided"])]


def report_normalized(model):
    rows = sorted(applied_rows(model), key=lambda row: row["txn"])
    lines = []
    for row in rows:
        payload = {
            "cents": row["direction"] * row["magnitude"],
            "date": row["day"].isoformat(),
            "district": model["envelopes"][row["env"]]["district"],
            "envelope": row["env"],
            "source": row["source"],
            "txn": row["txn"],
        }
        lines.append(json.dumps(ordered(payload), separators=(",", ":"), ensure_ascii=True))
    return "".join(line + "\n" for line in lines)


def report_quality(model):
    return {"exports": model["quality"], "corrections": model["corrections"]}


def report_summary(model):
    exits = {"budget": 0, "cycling": 0, "settled": 0, "stalled": 0}
    for district in DISTRICTS:
        exits[model["households"][district]["exit"]] += 1
    config = model["config"]
    return {
        "first_day": config["first_day"].isoformat(),
        "last_day": config["last_day"].isoformat(),
        "households": len(DISTRICTS),
        "exits": exits,
        "moved_dollars": sum(model["households"][name]["moved"] for name in DISTRICTS),
        "transactions_applied": len(applied_rows(model)),
    }


def report_product(model):
    groups = {}
    for envelope in model["envelopes"].values():
        entry = groups.setdefault(envelope["category"], {
            "category": envelope["category"], "envelopes": 0, "presweep_dollars": 0,
            "final_dollars": 0, "moved_in_dollars": 0, "moved_out_dollars": 0})
        entry["envelopes"] += 1
        entry["presweep_dollars"] += envelope["presweep"]
        entry["final_dollars"] += envelope["final"]
        gain = envelope["final"] - envelope["presweep"]
        if gain > 0:
            entry["moved_in_dollars"] += gain
        elif gain < 0:
            entry["moved_out_dollars"] -= gain
    return {"categories": [groups[name] for name in sorted(groups)]}


def report_region(model, district):
    result = model["households"][district]
    return {
        "district": district,
        "household": result["hh"],
        "family_name": result["family"],
        "exit": result["exit"],
        "rounds": result["rounds"],
        "damping_percent": result["damping_percent"],
        "pool_dollars": result["pool"],
        "moved_dollars": result["moved"],
        "envelopes": [{"code": env["code"], "label": env["label"],
                       "category": env["category"], "segment": env["segment"],
                       "need_dollars": env["need"], "presweep_dollars": env["presweep"],
                       "final_dollars": env["final"]}
                      for env in (model["envelopes"][code] for code in result["codes"])],
    }


def report_hold(model, district):
    result = model["households"][district]
    short = []
    for code in result["codes"]:
        envelope = model["envelopes"][code]
        if envelope["final"] < envelope["need"]:
            short.append({"code": code, "category": envelope["category"],
                          "segment": envelope["segment"],
                          "short_dollars": envelope["need"] - envelope["final"]})
    return {
        "district": district,
        "household": result["hh"],
        "rounds": result["rounds"],
        "envelopes": short,
        "short_dollars": sum(item["short_dollars"] for item in short),
    }


def report_segment(model, segment):
    members = [env for env in ordered_envelopes(model) if env["segment"] == segment]
    return {
        "segment": segment,
        "envelopes": len(members),
        "presweep_dollars": sum(env["presweep"] for env in members),
        "final_dollars": sum(env["final"] for env in members),
        "members": [{"district": env["district"], "code": env["code"],
                     "final_dollars": env["final"]} for env in members],
    }


def report_rounds(model):
    """sweep_rounds.csv: one row for every round a household ran."""
    rows = [["district", "round", "spread", "damping_percent", "strikes", "posted_dollars"]]
    for district in DISTRICTS:
        for round_no, spread, rate, strikes, posted in model["households"][district]["round_rows"]:
            rows.append([district, round_no, spread, rate, strikes, posted])
    return csv_text(rows)


def report_envelope_final(model):
    """envelope_final.tsv: every envelope and the balance it keeps."""
    head = ("district", "code", "label", "category", "segment", "final_dollars")
    lines = [csv_line(head, "\t")]
    for envelope in ordered_envelopes(model):
        lines.append(csv_line((envelope["district"], envelope["code"], envelope["label"],
                               envelope["category"], envelope["segment"], envelope["final"]), "\t"))
    return lines_text(lines)


def report_moves(model):
    """moves.csv: every envelope whose final balance differs from its pre-sweep balance."""
    rows = [["district", "code", "label", "presweep_dollars",
             "final_dollars", "moved_dollars"]]
    for envelope in ordered_envelopes(model):
        if envelope["final"] != envelope["presweep"]:
            rows.append([envelope["district"], envelope["code"], envelope["label"],
                         envelope["presweep"], envelope["final"],
                         envelope["final"] - envelope["presweep"]])
    return csv_text(rows)


def csv_text(rows):
    """The rows of a comma separated report, each line ending with one line feed."""
    buffer = io.StringIO(newline="")
    csv.writer(buffer, lineterminator="\n").writerows(rows)
    return buffer.getvalue()


def report_exits(model):
    """exits.xml: the exit of every household."""
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<sweep>"]
    for district in DISTRICTS:
        result = model["households"][district]
        lines.append('  <household district="%s" exit="%s" rounds="%d" damping_percent="%d"'
                     ' family_name="%s"/>' % (district, result["exit"], result["rounds"],
                                              result["damping_percent"],
                                              xml_escape(result["family"])))
    lines.append("</sweep>")
    return lines_text(lines)


def report_prior_delta(model):
    """prior_delta.yaml: the moved dollars against the earlier run of the sweep."""
    lines = []
    for district in DISTRICTS:
        prior = model["prior"].get(district, {})
        lines.append("%s: %d" % (district,
                                model["households"][district]["moved"]
                                - int(prior.get("moved_dollars", 0))))
    return lines_text(lines)


def report_reconciliation(model):
    """reconciliation.txt: the pool, the final balances and the moved dollars."""
    lines = []
    for district in DISTRICTS:
        result = model["households"][district]
        total = sum(model["envelopes"][code]["final"] for code in result["codes"])
        lines.append("%s pool=%d final=%d moved=%d"
                     % (district, result["pool"], total, result["moved"]))
    return lines_text(lines)


def report_ledger_totals(model):
    """ledger_totals.psv: the applied cents and pre-sweep balance of every envelope."""
    lines = [csv_line(("district", "code", "applied_cents", "presweep_dollars"), "|")]
    for envelope in ordered_envelopes(model):
        lines.append(csv_line((envelope["district"], envelope["code"],
                               envelope["applied_cents"], envelope["presweep"]), "|"))
    return lines_text(lines)


def table_text(name, head, rows):
    lines = ["table %s: %s" % (name, "|".join(head))]
    for row in rows:
        lines.append("|".join(str(value) for value in row))
    return "".join(line + "\n" for line in lines)


def household_rows(model):
    return [(district, model["households"][district]["exit"],
             model["households"][district]["rounds"],
             model["households"][district]["damping_percent"])
            for district in DISTRICTS]


def final_rows(model):
    return [(envelope["district"], envelope["code"], envelope["final"])
            for envelope in ordered_envelopes(model)]


def write_sqlite(path, exits, finals):
    if os.path.exists(path):
        os.remove(path)
    conn = sqlite3.connect(path)
    try:
        conn.execute("create table envelope_final (district TEXT, code TEXT,"
                      " final_dollars INTEGER)")
        conn.executemany("insert into envelope_final values (?, ?, ?)", finals)
        conn.execute("create table household_exit (district TEXT, exit TEXT,"
                     " rounds INTEGER, damping_percent INTEGER)")
        conn.executemany("insert into household_exit values (?, ?, ?, ?)", exits)
        conn.commit()
    finally:
        conn.close()


def sheet_xml(head, rows):
    parts = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
             '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
             '<sheetData>']
    values = [head] + [list(row) for row in rows]
    for number, row in enumerate(values, start=1):
        parts.append('<row r="%d">' % number)
        for column, value in enumerate(row, start=1):
            reference = "%s%d" % (chr(ord("A") + column - 1), number)
            if isinstance(value, str):
                parts.append('<c r="%s" t="inlineStr"><is><t>%s</t></is></c>'
                             % (reference, xml_escape(value)))
            else:
                parts.append('<c r="%s"><v>%d</v></c>' % (reference, value))
        parts.append("</row>")
    parts.append("</sheetData></worksheet>")
    return "".join(parts)


def write_xlsx(path, exits, finals):
    parts = {
        "[Content_Types].xml":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package'
            '.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.'
            'openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.'
            'openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.'
            'openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>',
        "_rels/.rels":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
            'relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
            'officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>',
        "xl/workbook.xml":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
            ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="exits" sheetId="1" r:id="rId1"/>'
            '<sheet name="final" sheetId="2" r:id="rId2"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
            'relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.'
            'org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/'
            '2006/relationships/worksheet" Target="worksheets/sheet2.xml"/></Relationships>',
        "xl/worksheets/sheet1.xml": sheet_xml(list(("district", "exit", "rounds",
                                                    "damping_percent")), exits),
        "xl/worksheets/sheet2.xml": sheet_xml(list(("district", "code", "final_dollars")),
                                             finals),
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(parts):
            info = zipfile.ZipInfo(name, date_time=ZIP_STAMP)
            archive.writestr(info, parts[name].encode("ascii"))
    with open(path, "wb") as handle:
        handle.write(buffer.getvalue())


def write_reports(out_dir, model):
    """Write every report the documents define into OUT_DIR."""
    os.makedirs(out_dir, exist_ok=True)
    exits = household_rows(model)
    finals = final_rows(model)
    texts = {
        "normalized.jsonl": report_normalized(model),
        "data_quality.json": dumps_json(report_quality(model)),
        "summary.json": dumps_json(report_summary(model)),
        "product_summary.json": dumps_json(report_product(model)),
        "sweep_rounds.csv": report_rounds(model),
        "envelope_final.tsv": report_envelope_final(model),
        "moves.csv": report_moves(model),
        "exits.xml": report_exits(model),
        "prior_delta.yaml": report_prior_delta(model),
        "reconciliation.txt": report_reconciliation(model),
        "ledger_totals.psv": report_ledger_totals(model),
    }
    for district in DISTRICTS:
        texts["region_%s.json" % district] = dumps_json(report_region(model, district))
        if model["households"][district]["exit"] == "stalled":
            code = model["households"][district]["hh"].lower()
            texts["hold_%s.json" % code] = dumps_json(report_hold(model, district))
    for segment in ("consumer", "corporate", "enterprise", "smb"):
        texts["segment_%s.json" % segment] = dumps_json(report_segment(model, segment))
    for name, text in sorted(texts.items()):
        write_text(os.path.join(out_dir, name), text)
    write_sqlite(os.path.join(out_dir, "sweep.sqlite"), exits, finals)
    write_xlsx(os.path.join(out_dir, "sweep_book.xlsx"), exits, finals)
    tables = (table_text("envelope_final", ("district", "code", "final_dollars"), finals)
              + table_text("household_exit", ("district", "exit", "rounds",
                                             "damping_percent"), exits))
    sheets = (table_text("exits", ("district", "exit", "rounds", "damping_percent"), exits)
              + table_text("final", ("district", "code", "final_dollars"), finals))
    reports = []
    for name in sorted(texts):
        reports.append({"name": name, "sha256": hashlib.sha256(
            texts[name].encode("ascii")).hexdigest()})
    reports.append({"name": "sweep.sqlite", "sha256": hashlib.sha256(
        tables.encode("ascii")).hexdigest()})
    reports.append({"name": "sweep_book.xlsx", "sha256": hashlib.sha256(
        sheets.encode("ascii")).hexdigest()})
    reports.sort(key=lambda item: item["name"])
    write_text(os.path.join(out_dir, "manifest.json"),
               dumps_json({"reports": reports}))


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: transform.py DATA_DIR OUT_DIR\n")
        return 2
    data_dir, out_dir = argv[1], argv[2]
    try:
        model = build_model(data_dir)
    except DataError as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 1
    write_reports(out_dir, model)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
