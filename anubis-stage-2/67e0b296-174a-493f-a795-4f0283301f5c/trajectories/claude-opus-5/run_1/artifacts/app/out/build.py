#!/usr/bin/env python3
"""Rack power cap compiler.

Three stages:
    phase1 <DATA_DIR> <P1_DIR>              facts from the sources
    phase2 <P1_DIR> <P2_DIR>                planning, from phase-1 tables only
    phase3 <P1_DIR> <P2_DIR> <P3_DIR>       pushed configuration

Source reading follows /app/data/power_standard.md; output shapes follow
/app/contract/output_contract.md.
"""

import csv
import datetime as dt
import email.utils
import hashlib
import json
import os
import re
import sqlite3
import sys
import zipfile
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_FLOOR, ROUND_CEILING

PROG = "build.py"
UTC = dt.timezone.utc


class UsageError(Exception):
    """Wrong stage name or argument count (exit 2)."""


class InputError(Exception):
    """Missing or unreadable input directory or file (exit 3)."""


# --------------------------------------------------------------------------
# numbers (standard section 5)
# --------------------------------------------------------------------------

GROUPING_CHARS = " \t\u00a0\u202f\u2007\u2009'\u2019"
MISSING_WORDS = {"", "-", "n/a", "null", "nan"}

_NUM_RE = re.compile(
    r"^([+-]?[0-9][0-9.,'\u2019 \t\u00a0\u202f\u2007\u2009]*(?:[eE][+-]?[0-9]+)?)(.*)$"
)


def split_value(text):
    """Split a written value into (numeric text, trailing unit word)."""
    if text is None:
        return "", ""
    s = str(text).strip()
    m = _NUM_RE.match(s)
    if not m:
        return s, ""
    return m.group(1).strip(), m.group(2).strip()


def parse_decimal(num_text):
    """Decimal value of a written number, or None when it is missing."""
    if num_text is None:
        return None
    s = str(num_text).strip()
    if s.lower() in MISSING_WORDS:
        return None
    for ch in GROUPING_CHARS:
        s = s.replace(ch, "")
    if not s:
        return None
    mantissa, exp_sep, exponent = s, "", ""
    for sep in ("e", "E"):
        if sep in mantissa:
            mantissa, exponent = mantissa.split(sep, 1)
            exp_sep = "e"
            break
    dots = mantissa.count(".")
    commas = mantissa.count(",")
    if dots and commas:
        dec = "." if mantissa.rfind(".") > mantissa.rfind(",") else ","
        other = "," if dec == "." else "."
        mantissa = mantissa.replace(other, "")
        if mantissa.count(dec) > 1:
            head, _, tail = mantissa.rpartition(dec)
            mantissa = head.replace(dec, "") + "." + tail
        else:
            mantissa = mantissa.replace(dec, ".")
    elif dots > 1:
        mantissa = mantissa.replace(".", "")
    elif commas:
        mantissa = mantissa.replace(",", "") if commas > 1 else mantissa.replace(",", ".")
    try:
        return Decimal(mantissa + (exp_sep + exponent if exp_sep else ""))
    except ArithmeticError:
        return None


def half_even(value):
    """Round a Decimal half to even, as an int."""
    return int(Decimal(value).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


def floor_int(value):
    return int(Decimal(value).quantize(Decimal(1), rounding=ROUND_FLOOR))


def ceil_int(value):
    return int(Decimal(value).quantize(Decimal(1), rounding=ROUND_CEILING))


def dec_str(value, places):
    """Fixed-decimal text, half to even."""
    q = Decimal(1).scaleb(-places)
    return str(Decimal(value).quantize(q, rounding=ROUND_HALF_EVEN))


def attr_text(text):
    """Render an attrs value: a plain integer when it is a whole number."""
    num, trailing = split_value(text)
    if trailing or not num:
        return str(text)
    value = parse_decimal(num)
    if value is None:
        return str(text)
    if value == value.to_integral_value():
        return str(int(value))
    return str(text)


# --------------------------------------------------------------------------
# times (standard section 4)
# --------------------------------------------------------------------------

SERIAL_EPOCH = dt.datetime(1899, 12, 30, tzinfo=UTC)

_ISO_RE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2}))?"
    r"(Z|z|[+-]\d{2}:?\d{2})?$"
)
_COMPACT_RE = re.compile(r"^(\d{8})T(\d{6})(Z|z|[+-]\d{2}:?\d{2})?$")
_SERIAL_RE = re.compile(r"^\d{1,7}(\.\d+)?$")


def _last_sunday(year, month):
    day = 31 if month in (1, 3, 5, 7, 8, 10, 12) else 30
    while dt.date(year, month, day).weekday() != 6:
        day -= 1
    return dt.date(year, month, day)


def _nth_sunday(year, month, nth):
    day = 1
    while dt.date(year, month, day).weekday() != 6:
        day += 1
    return dt.date(year, month, day + 7 * (nth - 1))


def _fra1_dst_for_utc(moment):
    start = dt.datetime.combine(_last_sunday(moment.year, 3), dt.time(1), tzinfo=UTC)
    end = dt.datetime.combine(_last_sunday(moment.year, 10), dt.time(1), tzinfo=UTC)
    return start <= moment < end


def _us_dst_local(naive):
    start = dt.datetime.combine(_nth_sunday(naive.year, 3, 2), dt.time(2))
    end = dt.datetime.combine(_nth_sunday(naive.year, 11, 1), dt.time(2))
    return start <= naive < end


def site_offset_hours(site, naive):
    """Offset in hours for a naive civil time at a site."""
    if site == "sin1":
        return 8
    if site == "fra1":
        for guess in (2, 1):
            moment = naive.replace(tzinfo=UTC) - dt.timedelta(hours=guess)
            if _fra1_dst_for_utc(moment) == (guess == 2):
                return guess
        return 1
    if site == "iad2":
        return -4 if _us_dst_local(naive) else -5
    if site == "den1":
        return -6 if _us_dst_local(naive) else -7
    return None


def _apply_zone(naive, zone, site):
    if zone in (None, ""):
        if site is None:
            return None
        hours = site_offset_hours(site, naive)
        if hours is None:
            return None
        return naive.replace(tzinfo=UTC) - dt.timedelta(hours=hours)
    if zone in ("Z", "z"):
        return naive.replace(tzinfo=UTC)
    sign = 1 if zone[0] == "+" else -1
    digits = zone[1:].replace(":", "")
    delta = dt.timedelta(hours=int(digits[:2]), minutes=int(digits[2:4]))
    return naive.replace(tzinfo=UTC) - sign * delta


def parse_time_rough(text):
    """Parse a time, reading a civil time with no offset as if it were UTC.

    Used only to pick the alias of a record whose site is not known yet; alias
    windows are far wider than any site offset.
    """
    moment = parse_time(text)
    if moment is not None:
        return moment
    if not needs_site(text):
        return None
    return parse_time(str(text).strip() + "Z")


def parse_time(text, site=None):
    """Parse a record time to an aware UTC datetime, or None."""
    if text is None:
        return None
    s = str(text).strip()
    if not s or s.lower() in MISSING_WORDS:
        return None
    if re.fullmatch(r"\d{13}", s):
        return dt.datetime.fromtimestamp(int(s) / 1000, UTC)
    if re.fullmatch(r"\d{10}", s):
        return dt.datetime.fromtimestamp(int(s), UTC)
    m = _COMPACT_RE.match(s)
    if m:
        base = dt.datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
        return _apply_zone(base, m.group(3), site)
    m = _ISO_RE.match(s)
    if m:
        base = dt.datetime(
            int(m.group(1)), int(m.group(2)), int(m.group(3)),
            int(m.group(4)), int(m.group(5)), int(m.group(6) or 0),
        )
        return _apply_zone(base, m.group(7), site)
    if _SERIAL_RE.match(s):
        seconds = (Decimal(s) * 86400).quantize(Decimal(1), rounding=ROUND_HALF_EVEN)
        return SERIAL_EPOCH + dt.timedelta(seconds=int(seconds))
    try:
        parsed = email.utils.parsedate_to_datetime(s)
    except (TypeError, ValueError):
        return None
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        return _apply_zone(parsed, None, site)
    return parsed.astimezone(UTC)


def needs_site(text):
    """True when a written time carries no offset and so needs a site."""
    if text is None:
        return False
    s = str(text).strip()
    if not s:
        return False
    if re.fullmatch(r"\d{10}", s) or re.fullmatch(r"\d{13}", s):
        return False
    if _SERIAL_RE.match(s):
        return False
    m = _COMPACT_RE.match(s)
    if m:
        return not m.group(3)
    m = _ISO_RE.match(s)
    if m:
        return not m.group(7)
    return False


def iso_z(moment):
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------
# source readers
# --------------------------------------------------------------------------

ID_RE = re.compile(r"^[A-Za-z]{2}\d{2}-\d{6}$")


def _is_record_row(fields):
    return len(fields) >= 8 and bool(ID_RE.match(fields[0].strip()))


def _norm(fields):
    fields = list(fields)
    while len(fields) < 8:
        fields.append("")
    return [f if isinstance(f, str) else str(f) for f in fields[:8]]


def _pipe_rows(lines):
    rows = []
    for line in lines:
        if "|" not in line:
            continue
        fields = [f.strip() for f in line.split("|")]
        if fields and fields[0] == "":
            fields = fields[1:]
        if fields and fields[-1] == "":
            fields = fields[:-1]
        fields = _norm(fields)
        if _is_record_row(fields):
            rows.append(fields)
    return rows


def _read_text(path):
    with open(path, "rb") as handle:
        return handle.read().decode("utf-8", "replace")


def read_csv_like(path, delimiter):
    rows = []
    with open(path, "r", encoding="utf-8", newline="") as handle:
        if delimiter == "\t":
            reader = csv.reader(handle, delimiter="\t", quoting=csv.QUOTE_NONE)
        else:
            reader = csv.reader(handle, delimiter=delimiter)
        for fields in reader:
            fields = _norm([f.strip() for f in fields])
            if _is_record_row(fields):
                rows.append(fields)
    return rows


def _cell_text(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    return str(value).strip()


def _mapping_rows(items):
    rows = []
    for obj in items:
        if isinstance(obj, dict):
            values = [_cell_text(v) for v in obj.values()]
        elif isinstance(obj, (list, tuple)):
            values = [_cell_text(v) for v in obj]
        else:
            continue
        fields = _norm(values)
        if _is_record_row(fields):
            rows.append(fields)
    return rows


def _first_list(doc):
    if isinstance(doc, list):
        return doc
    if isinstance(doc, dict):
        for value in doc.values():
            if isinstance(value, list):
                return value
    return []


def read_jsonl(path):
    items = []
    for line in _read_text(path).splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            items.append(json.loads(line))
        except ValueError:
            continue
    return _mapping_rows(items)


def read_json(path):
    try:
        doc = json.loads(_read_text(path))
    except ValueError:
        return []
    return _mapping_rows(_first_list(doc))


def read_yaml(path):
    import yaml

    return _mapping_rows(_first_list(yaml.safe_load(_read_text(path))))


def read_toml(path):
    import tomllib

    with open(path, "rb") as handle:
        doc = tomllib.load(handle)
    return _mapping_rows(_first_list(doc))


def read_ini(path):
    rows = []
    for line in _read_text(path).splitlines():
        stripped = line.strip()
        if not stripped or stripped[0] in ";#[":
            continue
        if "=" not in stripped:
            continue
        key, _, rest = stripped.partition("=")
        fields = _norm([key.strip()] + [f.strip() for f in rest.split("|")])
        if _is_record_row(fields):
            rows.append(fields)
    return rows


def read_xml(path):
    from lxml import etree

    rows = []
    for _event, element in etree.iterparse(path, events=("end",)):
        fields = _norm([_cell_text(v) for v in element.attrib.values()])
        if _is_record_row(fields):
            rows.append(fields)
        element.clear()
    return rows


def read_parquet(path):
    import pyarrow.parquet as pq

    table = pq.read_table(path)
    columns = [table.column(i).to_pylist() for i in range(table.num_columns)]
    rows = []
    for index in range(table.num_rows):
        fields = _norm([_cell_text(col[index]) for col in columns])
        if _is_record_row(fields):
            rows.append(fields)
    return rows


def read_sqlite(path):
    connection = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
    try:
        names = [
            row[0]
            for row in connection.execute(
                "select name from sqlite_master where type='table' order by rowid"
            )
        ]
        rows = []
        for name in names:
            quoted = '"' + name.replace('"', '""') + '"'
            for record in connection.execute("select * from %s order by rowid" % quoted):
                fields = _norm([_cell_text(v) for v in record])
                if _is_record_row(fields):
                    rows.append(fields)
        return rows
    finally:
        connection.close()


def read_mbox(path):
    return _pipe_rows(_read_text(path).splitlines())


def read_ics(path):
    text = _read_text(path).replace("\r\n", "\n")
    text = re.sub(r"\n[ \t]", "", text)
    lines = [line[len("X-REC:"):] for line in text.split("\n") if line.startswith("X-REC:")]
    return _pipe_rows(lines)


def read_md(path):
    return _pipe_rows(_read_text(path).splitlines())


_LOG_RE = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)="((?:[^"\\]|\\.)*)"')


def read_log(path):
    rows = []
    for line in _read_text(path).splitlines():
        if '="' in line:
            fields = _norm([m.group(2).strip() for m in _LOG_RE.finditer(line)])
            if _is_record_row(fields):
                rows.append(fields)
        elif "|" in line:
            rows.extend(_pipe_rows([line]))
    return rows


def read_text_pipe(path):
    return _pipe_rows(_read_text(path).splitlines())


def read_html(path):
    from lxml import etree

    tree = etree.parse(path, etree.HTMLParser())
    rows = []
    for tr in tree.iter("tr"):
        cells = []
        for cell in tr:
            if etree.QName(cell).localname in ("td", "th"):
                cells.append("".join(cell.itertext()).strip())
        fields = _norm(cells)
        if _is_record_row(fields):
            rows.append(fields)
    return rows


def read_xlsx(path):
    import openpyxl

    book = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = []
    try:
        for sheet in book.worksheets:
            for record in sheet.iter_rows(values_only=True):
                fields = _norm([_cell_text(v) for v in record])
                if _is_record_row(fields):
                    rows.append(fields)
    finally:
        book.close()
    return rows


def read_docx(path):
    from lxml import etree

    with zipfile.ZipFile(path) as archive:
        data = archive.read("word/document.xml")
    root = etree.fromstring(data)
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    lines = [
        "".join(node.text or "" for node in paragraph.iter(ns + "t"))
        for paragraph in root.iter(ns + "p")
    ]
    return _pipe_rows(lines)


def read_pdf(path):
    import pdfplumber

    lines = []
    with pdfplumber.open(path) as doc:
        for page in doc.pages:
            lines.extend((page.extract_text() or "").splitlines())
    return _pipe_rows(lines)


READERS = {
    ".csv": lambda p: read_csv_like(p, ","),
    ".tsv": lambda p: read_csv_like(p, "\t"),
    ".jsonl": read_jsonl,
    ".json": read_json,
    ".yaml": read_yaml,
    ".yml": read_yaml,
    ".toml": read_toml,
    ".ini": read_ini,
    ".xml": read_xml,
    ".parquet": read_parquet,
    ".db": read_sqlite,
    ".sqlite": read_sqlite,
    ".mbox": read_mbox,
    ".ics": read_ics,
    ".md": read_md,
    ".log": read_log,
    ".txt": read_text_pipe,
    ".html": read_html,
    ".htm": read_html,
    ".xlsx": read_xlsx,
    ".docx": read_docx,
    ".pdf": read_pdf,
}


def read_source(path):
    reader = READERS.get(os.path.splitext(path)[1].lower())
    if reader is None:
        return []
    return reader(path)


# --------------------------------------------------------------------------
# record model
# --------------------------------------------------------------------------

SUPERSEDED_RE = re.compile(
    r"re-?export|replay|backfill|legacy|prev|draft|rescan|prelim", re.I
)

UNIT_FACTOR = {
    "w": Decimal(1000),
    "watt": Decimal(1000),
    "kw": Decimal(1000000),
    "mw": Decimal(1),
    "va": Decimal(1000),
    "kva": Decimal(1000000),
    "btu/h": Decimal("293.071"),
    "btu/hr": Decimal("293.071"),
}
VA_UNITS = {"va", "kva"}
PRIORITY_RANK = {"gold": 0, "silver": 1, "bronze": 2}
SRC_RANK = {"pdu": 0, "bmc": 1, "agent": 2}
SITE_PARAMS = (
    ("cont", "cont_pm"),
    ("derate", "derate_pm"),
    ("volts", "volts"),
    ("tariff", "tariff_mc"),
    ("pue", "pue_milli"),
    ("step", "cap_step_w"),
    ("margin", "margin_pm"),
    ("warn", "warn_pm"),
    ("crit", "crit_pm"),
    ("pool", "pool_pm"),
    ("corr", "correction_ms"),
)

HOST_RE = re.compile(r"^[nN](\d{5})(\.pwr\.corp)?$")
SERIAL_RE = re.compile(r"^SN[0-9A-Za-z]+$")

# line tuple positions
L_FILE, L_KIND, L_ID, L_SUBJ, L_AT, L_VAL, L_UNIT, L_ATTRS = range(8)


def parse_attrs(text):
    out = {}
    for piece in str(text).split(";"):
        if "=" not in piece:
            continue
        key, _, value = piece.partition("=")
        out[key.strip().lower()] = value.strip()
    return out


def strip_rec(text):
    name = str(text).strip().lower()
    return name[4:] if name.startswith("rec:") else name


def unit_of(line):
    unit = line[L_UNIT].strip()
    if unit:
        return unit.lower()
    return split_value(line[L_VAL])[1].lower()


class Sources(object):
    """Every data line of a source directory, with the resolution the standard sets."""

    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.files = []
        self.lines = []
        self.file_lines = {}
        self.occurs = {}
        self.rep = {}
        self.freeze = None
        self.window_start = None
        self._site_cache = {}
        self._time_cache = {}
        self._load()

    # -- loading ---------------------------------------------------------
    def _load(self):
        if not os.path.isdir(self.data_dir):
            raise InputError("input directory not found: %s" % self.data_dir)
        if not os.access(self.data_dir, os.R_OK | os.X_OK):
            raise InputError("input directory is not readable: %s" % self.data_dir)
        try:
            names = sorted(os.listdir(self.data_dir))
        except OSError as exc:
            raise InputError("cannot read input directory: %s" % exc)
        self.files = [
            n for n in names if os.path.isfile(os.path.join(self.data_dir, n))
        ]
        self._read_freeze()
        for file_index, name in enumerate(self.files):
            path = os.path.join(self.data_dir, name)
            indexes = []
            for row in read_source(path):
                indexes.append(len(self.lines))
                self.lines.append(
                    (
                        file_index,
                        row[1].strip().upper(),
                        row[0].strip(),
                        row[2].strip(),
                        row[3].strip(),
                        row[4],
                        row[5],
                        row[6],
                    )
                )
            self.file_lines[name] = indexes
        self.superseded = [bool(SUPERSEDED_RE.search(n)) for n in self.files]
        for index, line in enumerate(self.lines):
            self.occurs.setdefault(line[L_ID].lower(), []).append(index)
        for rid, indexes in self.occurs.items():
            best = None
            for index in indexes:
                key = (self.superseded[self.lines[index][L_FILE]], index)
                if best is None or key < best[0]:
                    best = (key, index)
            self.rep[rid] = best[1]
        self._build_hosts()
        self._resolve_force()

    def _read_freeze(self):
        freeze = window = None
        for name in self.files:
            if not name.lower().endswith(".md"):
                continue
            text = _read_text(os.path.join(self.data_dir, name))
            m = re.search(
                r"as-of freeze is\s+(\S+?)\s+and the telemetry window runs from\s+(\S+?)\s",
                text,
            )
            if m:
                freeze = parse_time(m.group(1))
                window = parse_time(m.group(2))
                break
        if freeze is None or window is None:
            raise InputError("freeze and window not stated in the source directory")
        self.freeze = freeze
        self.window_start = window

    # -- in force --------------------------------------------------------
    def _resolve_force(self):
        ratified = set()
        for index, line in enumerate(self.lines):
            if line[L_KIND] != "RT" or self.superseded[line[L_FILE]]:
                continue
            attrs = parse_attrs(line[L_ATTRS])
            ratified.add((strip_rec(line[L_SUBJ]), attrs.get("file", "")))
        placed = {}
        for rid, indexes in self.occurs.items():
            ok = False
            for index in indexes:
                file_index = self.lines[index][L_FILE]
                if not self.superseded[file_index]:
                    ok = True
                    break
                if (rid, self.files[file_index]) in ratified:
                    ok = True
                    break
            placed[rid] = ok
        self._placed = placed
        voided = set()
        for rid, index in self.rep.items():
            line = self.lines[index]
            if line[L_KIND] != "VO" or not placed[rid]:
                continue
            moment = self.time_of(index)
            if moment is not None and moment < self.freeze:
                voided.add(strip_rec(line[L_SUBJ]))
        self.voided = voided

    def in_force(self, rid):
        if not self._placed.get(rid):
            return False
        kind = self.lines[self.rep[rid]][L_KIND]
        if kind in ("VO", "RT"):
            return True
        return rid not in self.voided

    def records(self, kind):
        """Representative line index of every in-force record of a kind."""
        for rid, index in self.rep.items():
            if self.lines[index][L_KIND] == kind and self.in_force(rid):
                yield index

    # -- sites and times -------------------------------------------------
    def site_of(self, index, depth=0):
        if index in self._site_cache:
            return self._site_cache[index]
        if depth > 6:
            return None
        self._site_cache[index] = None
        line = self.lines[index]
        kind = line[L_KIND]
        subject = line[L_SUBJ]
        site = None
        if kind in ("RD", "HV", "QV"):
            site = self.host_site.get(self.rough_host(subject, line[L_AT]))
        elif kind == "AM":
            if HOST_RE.match(subject) or SERIAL_RE.match(subject):
                site = self.host_site.get(self.rough_host(subject, line[L_AT]))
            else:
                site = subject[:4].lower()
        elif kind in ("CV", "CA"):
            site = subject[:4].lower()
        elif kind == "SP":
            site = subject.split(":")[0].strip().lower()
        elif kind == "TN":
            site = subject.split("@")[-1].strip().lower()
        elif kind == "AL":
            target = parse_attrs(line[L_ATTRS]).get("target", "")
            site = self.host_site.get(self.rough_host(target, line[L_AT]))
        elif kind in ("VO", "ER", "RT"):
            target = self.rep.get(strip_rec(subject))
            if target is not None:
                site = self.site_of(target, depth + 1)
        self._site_cache[index] = site
        return site

    def time_of(self, index):
        if index in self._time_cache:
            return self._time_cache[index]
        line = self.lines[index]
        site = self.site_of(index) if needs_site(line[L_AT]) else None
        moment = parse_time(line[L_AT], site)
        self._time_cache[index] = moment
        return moment

    # -- host names ------------------------------------------------------
    def _build_hosts(self):
        self.host_site = {}
        self.serial_host = {}
        self.alias_windows = {}
        self.alias_rules = {}
        for index, line in enumerate(self.lines):
            if line[L_KIND] != "HV":
                continue
            m = HOST_RE.match(line[L_SUBJ])
            if not m:
                continue
            host = "n" + m.group(1)
            attrs = parse_attrs(line[L_ATTRS])
            rack = attrs.get("rack", "")
            if rack and host not in self.host_site:
                self.host_site[host] = rack[:4].lower()
            serial = attrs.get("serial", "")
            if serial:
                self.serial_host.setdefault(serial.upper(), host)
        for index, line in enumerate(self.lines):
            if line[L_KIND] != "AL":
                continue
            attrs = parse_attrs(line[L_ATTRS])
            self.alias_rules.setdefault(line[L_SUBJ].lower(), []).append(
                (index, attrs.get("target", ""), attrs.get("until", ""))
            )
        for name, rules in self.alias_rules.items():
            self.alias_windows[name] = [
                (parse_time_rough(self.lines[i][L_AT]), parse_time_rough(u), t, i)
                for i, t, u in rules
            ]

    def rough_host(self, name, at_text, depth=0):
        """Host a name leads to, using rough times and ignoring void and ratification."""
        host = self.direct_host(name)
        if host is not None:
            return host
        if depth > 6:
            return None
        windows = self.alias_windows.get(str(name).strip().lower())
        if not windows:
            return None
        moment = parse_time_rough(at_text)
        best = None
        for start, stop, target, index in windows:
            if start is None:
                continue
            if moment is not None:
                if start > moment or (stop is not None and stop <= moment):
                    continue
            key = (start, self.lines[index][L_ID].lower())
            if best is None or key > best[0]:
                best = (key, target, index)
        if best is None:
            return None
        return self.rough_host(best[1], self.lines[best[2]][L_AT], depth + 1)

    def direct_host(self, name):
        """Canonical host id of a name that does not need an alias."""
        text = str(name).strip()
        m = HOST_RE.match(text)
        if m:
            return "n" + m.group(1)
        if SERIAL_RE.match(text):
            return self.serial_host.get(text.upper())
        return None

    def host_of_name(self, name, moment=None, depth=0):
        """Canonical host id of any host name, at an instant when given."""
        host = self.direct_host(name)
        if host is not None:
            return host
        if depth > 6:
            return None
        rules = self.alias_rules.get(str(name).strip().lower())
        if not rules:
            return None
        if moment is None:
            return self.rough_host(name, "")
        best = None
        for index, target, until in rules:
            rid = self.lines[index][L_ID].lower()
            if not self.in_force(rid):
                continue
            start = self.time_of(index)
            if start is None or start >= self.freeze or start > moment:
                continue
            site = self.site_of(index) if needs_site(until) else None
            stop = parse_time(until, site)
            if stop is not None and stop <= moment:
                continue
            key = (start, rid)
            if best is None or key > best[0]:
                best = (key, target)
        if best is None:
            return None
        return self.host_of_name(best[1], moment, depth + 1)

    # -- effective records -----------------------------------------------
    def effective(self, kind, key_of):
        """Effective record line index per subject key, by revision then time then id."""
        best = {}
        for index in self.records(kind):
            line = self.lines[index]
            key = key_of(line)
            if key is None:
                continue
            moment = self.time_of(index)
            if moment is None or moment >= self.freeze:
                continue
            revision = parse_decimal(number_or_none(line[L_VAL]))
            if revision is None:
                continue
            rank = (revision, moment, line[L_ID].lower())
            current = best.get(key)
            if current is None or rank > current[0]:
                best[key] = (rank, index)
        return {key: value[1] for key, value in best.items()}


def number_or_none(text):
    return split_value(text)[0]


# --------------------------------------------------------------------------
# output helpers
# --------------------------------------------------------------------------


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def write_lines(path, text):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def csv_text(header, rows):
    out = [",".join(header)]
    for row in rows:
        out.append(",".join("" if v is None else str(v) for v in row))
    return "\n".join(out) + "\n"


def json_text(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def read_csv_table(path):
    if not os.path.isfile(path):
        raise InputError("input file not found: %s" % path)
    try:
        with open(path, "r", encoding="utf-8", newline="") as handle:
            rows = list(csv.reader(handle))
    except OSError as exc:
        raise InputError("cannot read input file: %s" % exc)
    if not rows:
        raise InputError("input file is empty: %s" % path)
    header = rows[0]
    return [dict(zip(header, row)) for row in rows[1:] if row]


def read_json_file(path):
    if not os.path.isfile(path):
        raise InputError("input file not found: %s" % path)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except OSError as exc:
        raise InputError("cannot read input file: %s" % exc)
    except ValueError as exc:
        raise InputError("input file is not JSON: %s" % exc)


def lineage_of(path, label):
    if not os.path.isfile(path):
        raise InputError("input file not found: %s" % path)
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except OSError as exc:
        raise InputError("cannot read input file: %s" % exc)
    return label, {
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "lines": data.count(b"\n"),
    }


def as_int(text, default=None):
    value = parse_decimal(number_or_none(text))
    if value is None:
        return default
    return int(value.to_integral_value(rounding=ROUND_HALF_EVEN))


def opt_int(text):
    if text is None or str(text).strip() == "":
        return None
    return as_int(text)


def opt_dec(text):
    if text is None or str(text).strip() == "":
        return None
    return Decimal(str(text).strip())


# --------------------------------------------------------------------------
# phase 1
# --------------------------------------------------------------------------

P1_FILES = (
    "hosts.csv",
    "circuits.csv",
    "demand.csv",
    "psu.csv",
    "registry.json",
    "amendments.csv",
)

HOSTS_HEADER = [
    "host_id", "site", "rack_id", "model", "psu_model", "psu_count", "tenant",
    "priority", "cap_domain", "nameplate_w", "idle_w", "floor_w", "cap_ceiling_w",
]
CIRCUITS_HEADER = [
    "circuit_id", "site", "rack_id", "feed", "voltage_v", "breaker_a", "usable_w",
]
DEMAND_HEADER = ["host_id", "samples", "mean_w", "p95_w", "peak_w", "energy_wh"]
PSU_HEADER = ["psu_model", "rated_w", "load_pm", "eff_bp"]
AMEND_HEADER = ["amendment_id", "effective_utc", "target", "field", "value"]


def pv_basis_points(line):
    """Efficiency of a PV point in basis points."""
    number, trailing = split_value(line[L_VAL])
    value = parse_decimal(number)
    if value is None:
        return None
    unit = (line[L_UNIT].strip() or trailing).lower()
    if unit in ("%", "percent", "pct"):
        return half_even(value * 100)
    if unit == "frac":
        return half_even(value * 10000)
    if unit == "permille":
        return half_even(value * 10)
    if unit == "bp":
        return half_even(value)
    return None


class Fleet(object):
    """Phase-1 facts resolved from a source directory."""

    def __init__(self, sources):
        self.src = sources
        self._resolve()

    def _resolve(self):
        src = self.src
        self.hv = src.effective("HV", lambda ln: src.direct_host(ln[L_SUBJ])
                                or src.rough_host(ln[L_SUBJ], ln[L_AT]))
        self.cv = src.effective("CV", lambda ln: ln[L_SUBJ].lower())
        self.mv = src.effective("MV", lambda ln: ln[L_SUBJ])
        self.pr = src.effective("PR", lambda ln: ln[L_SUBJ])
        self.qv = {}
        best = {}
        for index in src.records("QV"):
            line = src.lines[index]
            moment = src.time_of(index)
            if moment is None or moment >= src.freeze:
                continue
            host = src.host_of_name(line[L_SUBJ], moment)
            if host is None:
                continue
            revision = parse_decimal(number_or_none(line[L_VAL]))
            if revision is None:
                continue
            rank = (revision, moment, line[L_ID].lower())
            if host not in best or rank > best[host][0]:
                best[host] = (rank, index)
        self.qv = {host: value[1] for host, value in best.items()}
        self.circuit_names = {
            key: src.lines[index][L_SUBJ] for key, index in self.cv.items()
        }
        self.sp = src.effective("SP", lambda ln: ln[L_SUBJ].lower())
        self.tn = src.effective("TN", lambda ln: ln[L_SUBJ].lower())

        self.site_params = {}
        for key, index in self.sp.items():
            site, _, name = key.partition(":")
            value = parse_attrs(src.lines[index][L_ATTRS]).get(name.strip())
            self.site_params.setdefault(site, {})[name.strip()] = as_int(value)

        self.rated = {}
        for model, index in self.pr.items():
            self.rated[model] = as_int(parse_attrs(src.lines[index][L_ATTRS]).get("rated"))

        self.eff = {}
        for index in src.records("PV"):
            line = src.lines[index]
            points = parse_attrs(line[L_ATTRS])
            load = as_int(points.get("load"))
            basis = pv_basis_points(line)
            if load is None or basis is None:
                continue
            self.eff[(line[L_SUBJ], load)] = basis

        self.amendments = []
        for index in src.records("AM"):
            line = src.lines[index]
            moment = src.time_of(index)
            if moment is None:
                continue
            attrs = parse_attrs(line[L_ATTRS])
            field = attrs.get("field", "").strip()
            raw = attrs.get("value", "")
            subject = line[L_SUBJ]
            host = src.host_of_name(subject, moment)
            if host is not None:
                target = host
            else:
                target = self.circuit_names.get(subject.lower(), subject)
            value = raw.strip() if field == "priority" else attr_text(raw)
            self.amendments.append(
                (moment, line[L_ID].lower(), target, field, value)
            )
        self.amendments.sort(key=lambda a: (a[0], a[1]))

        self._build_hosts()
        self._build_circuits()

    # -- hosts -----------------------------------------------------------
    def _build_hosts(self):
        src = self.src
        pre = [a for a in self.amendments if a[0] < src.freeze]
        self.hosts = {}
        for host, index in self.hv.items():
            attrs = parse_attrs(src.lines[index][L_ATTRS])
            if attrs.get("status", "").lower() != "active":
                continue
            rack = attrs.get("rack", "")
            model = attrs.get("model", "")
            model_index = self.mv.get(model)
            model_attrs = (
                parse_attrs(src.lines[model_index][L_ATTRS])
                if model_index is not None
                else {}
            )
            volt_amps = as_int(model_attrs.get("va"), 0)
            power_factor = as_int(model_attrs.get("pf"), 0)
            idle = as_int(model_attrs.get("idle"), 0)
            domain = model_attrs.get("domain", "").strip().upper()
            nameplate = half_even(Decimal(volt_amps) * power_factor / 1000)
            policy_index = self.qv.get(host)
            if policy_index is None:
                priority, floor = "bronze", 0
            else:
                policy = parse_attrs(src.lines[policy_index][L_ATTRS])
                priority = policy.get("prio", "bronze").strip().lower()
                floor = as_int(policy.get("floor"), 0)
            floor = max(idle, floor)
            ceiling = None
            for _moment, _rid, target, field, value in pre:
                if target != host:
                    continue
                if field == "floor_w":
                    floor = as_int(value, floor)
                elif field == "cap_ceiling_w":
                    ceiling = as_int(value)
                elif field == "priority":
                    priority = value.strip().lower()
            self.hosts[host] = {
                "host_id": host,
                "site": rack[:4].lower(),
                "rack_id": rack,
                "model": model,
                "psu_model": attrs.get("psu", ""),
                "psu_count": as_int(attrs.get("n"), 0),
                "tenant": attrs.get("tenant", ""),
                "priority": priority,
                "cap_domain": domain,
                "nameplate_w": nameplate,
                "idle_w": idle,
                "floor_w": floor,
                "cap_ceiling_w": ceiling,
            }
        self.host_order = sorted(
            self.hosts,
            key=lambda h: (
                self.hosts[h]["rack_id"],
                PRIORITY_RANK.get(self.hosts[h]["priority"], 3),
                h,
            ),
        )

    # -- circuits --------------------------------------------------------
    def _build_circuits(self):
        src = self.src
        pre = [a for a in self.amendments if a[0] < src.freeze]
        self.circuits = {}
        for key, index in self.cv.items():
            attrs = parse_attrs(src.lines[index][L_ATTRS])
            circuit = src.lines[index][L_SUBJ]
            site = key[:4]
            params = self.site_params.get(site, {})
            volts = as_int(attrs.get("volts"), 0)
            amps = as_int(attrs.get("amps"), 0)
            for _moment, _rid, target, field, value in pre:
                if target.lower() == key and field == "breaker_a":
                    amps = as_int(value, amps)
            cont = params.get("cont", 0) or 0
            derate = params.get("derate", 0) or 0
            usable = floor_int(
                Decimal(volts) * amps * cont * derate / 1000000
            )
            self.circuits[circuit] = {
                "circuit_id": circuit,
                "site": site,
                "rack_id": attrs.get("rack", ""),
                "feed": attrs.get("feed", ""),
                "voltage_v": volts,
                "breaker_a": amps,
                "usable_w": usable,
            }

    # -- readings --------------------------------------------------------
    def _profiles(self):
        src = self.src
        scales = {}
        for index in src.records("PF"):
            line = src.lines[index]
            moment = src.time_of(index)
            if moment is None or moment >= src.freeze:
                continue
            scale = as_int(parse_attrs(line[L_ATTRS]).get("scale"))
            if scale is None:
                continue
            batch = line[L_SUBJ]
            rank = (moment, line[L_ID].lower())
            if batch not in scales or rank > scales[batch][0]:
                scales[batch] = (rank, scale)
        return {batch: value[1] for batch, value in scales.items()}

    def _calibrations(self):
        src = self.src
        table = {}
        for index in src.records("CA"):
            line = src.lines[index]
            moment = src.time_of(index)
            if moment is None or moment >= src.freeze:
                continue
            attrs = parse_attrs(line[L_ATTRS])
            gain = as_int(attrs.get("gain"))
            offset = as_int(attrs.get("offset"))
            if gain is None or offset is None:
                continue
            table.setdefault(line[L_SUBJ].lower(), []).append(
                (moment, line[L_ID].lower(), gain, offset)
            )
        for entries in table.values():
            entries.sort(key=lambda e: (e[0], e[1]))
        return table

    def _errata(self):
        src = self.src
        table = {}
        for index in src.records("ER"):
            line = src.lines[index]
            moment = src.time_of(index)
            if moment is None or moment >= src.freeze:
                continue
            number = parse_decimal(number_or_none(line[L_VAL]))
            if number is None:
                continue
            factor = UNIT_FACTOR.get(unit_of(line))
            if factor is None:
                continue
            target = strip_rec(line[L_SUBJ])
            rank = (moment, line[L_ID].lower())
            if target not in table or rank > table[target][0]:
                table[target] = (rank, half_even(number * factor))
        return {key: value[1] for key, value in table.items()}

    def efficiency_at(self, psu_model, load_pm):
        return self.eff.get((psu_model, load_pm))

    def load_per_mille(self, milliwatts, psu_count, rated):
        if not psu_count or not rated:
            return None
        value = half_even(Decimal(milliwatts) / (psu_count * rated))
        return min(1000, max(1, value))

    def compute_demand(self):
        src = self.src
        scales = self._profiles()
        calibration = self._calibrations()
        errata = self._errata()
        kept = {}
        self.src_ties = 0
        for index in src.records("RD"):
            line = src.lines[index]
            moment = src.time_of(index)
            if moment is None or moment < src.window_start or moment >= src.freeze:
                continue
            host = src.host_of_name(line[L_SUBJ], moment)
            info = self.hosts.get(host)
            if info is None:
                continue
            number = parse_decimal(number_or_none(line[L_VAL]))
            if number is None:
                continue
            unit = unit_of(line)
            factor = UNIT_FACTOR.get(unit)
            if factor is None:
                continue
            attrs = parse_attrs(line[L_ATTRS])
            rid = line[L_ID].lower()
            source = attrs.get("src", "").lower()
            key = (host, moment)
            rank = SRC_RANK.get(source, 9)
            current = kept.get(key)
            if current is not None:
                if rank > current[0]:
                    continue
                if rank == current[0]:
                    # the standard gives no order inside one source: greater id wins
                    self.src_ties += 1
                    if rid < current[1]:
                        continue
            value = number * factor
            scale = scales.get(attrs.get("batch", ""))
            if scale is not None:
                value = value * scale / 1000
            milliwatts = half_even(value)
            if unit in VA_UNITS:
                model_index = self.mv.get(info["model"])
                power_factor = (
                    as_int(parse_attrs(src.lines[model_index][L_ATTRS]).get("pf"), 0)
                    if model_index is not None
                    else 0
                )
                milliwatts = half_even(Decimal(milliwatts) * power_factor / 1000)
            if source == "pdu":
                entries = calibration.get(attrs.get("outlet", "").lower())
                if entries:
                    chosen = None
                    for entry in entries:
                        if entry[0] <= moment:
                            chosen = entry
                        else:
                            break
                    if chosen is not None:
                        milliwatts = half_even(
                            Decimal(milliwatts) * (1000000 + chosen[2]) / 1000000
                        ) + chosen[3]
            if attrs.get("dom", "").strip().upper() == "DC":
                rated = self.rated.get(info["psu_model"])
                load = self.load_per_mille(milliwatts, info["psu_count"], rated)
                basis = self.efficiency_at(info["psu_model"], load) if load else None
                if basis:
                    milliwatts = half_even(Decimal(milliwatts) * 10000 / basis)
            if rid in errata:
                milliwatts = errata[rid]
            kept[key] = (rank, rid, milliwatts)
        series = {}
        for (host, _moment), (_rank, _rid, milliwatts) in kept.items():
            series.setdefault(host, []).append(milliwatts)
        self.demand = {}
        for host in self.hosts:
            values = series.get(host)
            if not values:
                self.demand[host] = {
                    "samples": 0, "mean_w": None, "p95_w": None,
                    "peak_w": None, "energy_wh": None,
                }
                continue
            values.sort()
            count = len(values)
            total = sum(values)
            rank = ceil_int(Decimal(95 * count) / 100)
            rank = min(count, max(1, rank))
            self.demand[host] = {
                "samples": count,
                "mean_w": dec_str(Decimal(total) / count / 1000, 1),
                "p95_w": dec_str(Decimal(values[rank - 1]) / 1000, 1),
                "peak_w": dec_str(Decimal(values[-1]) / 1000, 1),
                "energy_wh": half_even(Decimal(total) / 4000),
            }

    # -- canonical lines -------------------------------------------------
    def canonical_line(self, index):
        src = self.src
        line = src.lines[index]
        kind = line[L_KIND]
        subject = line[L_SUBJ]
        if kind in ("VO", "ER", "RT"):
            subject_text = strip_rec(subject)
        elif kind in ("RD", "HV", "QV"):
            host = src.host_of_name(subject, src.time_of(index))
            subject_text = host if host else subject
        else:
            subject_text = subject
        if kind == "PV":
            time_text = ""
        else:
            moment = src.time_of(index)
            time_text = iso_z(moment) if moment is not None else ""
        attrs = parse_attrs(line[L_ATTRS])
        if kind == "RD":
            number = parse_decimal(number_or_none(line[L_VAL]))
            unit = unit_of(line)
            factor = UNIT_FACTOR.get(unit)
            if number is None or factor is None:
                value_text = "null"
            else:
                value_text = str(half_even(number * factor))
            extra = "batch=%s;dom=%s;outlet=%s;src=%s;uc=%s" % (
                attrs.get("batch", ""),
                attrs.get("dom", ""),
                attrs.get("outlet", ""),
                attrs.get("src", ""),
                "VA" if unit in VA_UNITS else "W",
            )
        elif kind == "AL":
            until = attrs.get("until", "")
            site = src.site_of(index) if needs_site(until) else None
            stop = parse_time(until, site)
            extra = "target=%s;until=%s" % (
                attrs.get("target", ""),
                iso_z(stop) if stop is not None else "",
            )
            value_text = ""
        else:
            extra = ";".join(
                "%s=%s" % (key, attr_text(value)) for key, value in sorted(attrs.items())
            )
            if kind in ("HV", "CV", "MV", "PR", "QV", "SP", "TN"):
                value_text = str(line[L_VAL]).strip()
            elif kind == "PV":
                basis = pv_basis_points(line)
                value_text = "" if basis is None else str(basis)
            elif kind == "ER":
                number = parse_decimal(number_or_none(line[L_VAL]))
                factor = UNIT_FACTOR.get(unit_of(line))
                value_text = (
                    str(half_even(number * factor))
                    if number is not None and factor is not None
                    else ""
                )
            else:
                value_text = ""
        return "|".join(
            [kind, line[L_ID], subject_text, time_text, value_text, extra]
        )

    def source_entries(self):
        src = self.src
        entries = []
        for name in src.files:
            indexes = src.file_lines.get(name, [])
            digest = hashlib.sha256()
            voided = 0
            post_cut = 0
            for index in indexes:
                line = src.lines[index]
                digest.update((self.canonical_line(index) + "\n").encode("utf-8"))
                if line[L_KIND] not in ("VO", "RT"):
                    if line[L_ID].lower() in src.voided:
                        voided += 1
                if line[L_KIND] != "PV":
                    moment = src.time_of(index)
                    if moment is not None and moment >= src.freeze:
                        post_cut += 1
            entries.append(
                {
                    "file": name,
                    "records": len(indexes),
                    "voided": voided,
                    "post_cut": post_cut,
                    "digest": digest.hexdigest(),
                }
            )
        return entries


def phase1(data_dir, out_dir):
    sources = Sources(data_dir)
    fleet = Fleet(sources)
    fleet.compute_demand()
    ensure_dir(out_dir)

    rows = []
    for host in fleet.host_order:
        info = fleet.hosts[host]
        rows.append([info[column] for column in HOSTS_HEADER])
    write_lines(os.path.join(out_dir, "hosts.csv"), csv_text(HOSTS_HEADER, rows))

    rows = []
    for circuit in sorted(fleet.circuits):
        info = fleet.circuits[circuit]
        rows.append([info[column] for column in CIRCUITS_HEADER])
    write_lines(os.path.join(out_dir, "circuits.csv"), csv_text(CIRCUITS_HEADER, rows))

    rows = []
    for host in fleet.host_order:
        info = fleet.demand[host]
        rows.append(
            [host, info["samples"], info["mean_w"], info["p95_w"],
             info["peak_w"], info["energy_wh"]]
        )
    write_lines(os.path.join(out_dir, "demand.csv"), csv_text(DEMAND_HEADER, rows))

    rows = []
    for (model, load) in sorted(fleet.eff):
        rows.append([model, fleet.rated.get(model), load, fleet.eff[(model, load)]])
    write_lines(os.path.join(out_dir, "psu.csv"), csv_text(PSU_HEADER, rows))

    rows = []
    for moment, rid, target, field, value in fleet.amendments:
        if moment < sources.freeze:
            continue
        rows.append([rid, iso_z(moment), target, field, value])
    write_lines(os.path.join(out_dir, "amendments.csv"), csv_text(AMEND_HEADER, rows))

    sites = []
    for site in sorted(fleet.site_params):
        params = fleet.site_params[site]
        entry = {"site": site}
        for name, column in SITE_PARAMS:
            entry[column] = params.get(name)
        sites.append(entry)
    tenants = []
    for key in sorted(fleet.tn):
        tenant, _, site = key.partition("@")
        watts = parse_attrs(sources.lines[fleet.tn[key]][L_ATTRS]).get("watts")
        tenants.append(
            {"site": site, "tenant": tenant, "entitlement_w": as_int(watts)}
        )
    tenants.sort(key=lambda t: (t["site"], t["tenant"]))
    registry = {
        "freeze_utc": iso_z(sources.freeze),
        "window_start_utc": iso_z(sources.window_start),
        "sites": sites,
        "tenants": tenants,
        "sources": fleet.source_entries(),
    }
    write_lines(os.path.join(out_dir, "registry.json"), json_text(registry))
    return fleet


# --------------------------------------------------------------------------
# phase 2
# --------------------------------------------------------------------------

P2_FILES = (
    "rack_budget.csv",
    "host_alloc.csv",
    "site_energy.csv",
    "circuit_alarms.csv",
    "tenant_pool.csv",
    "fleet_summary.json",
)

RACK_HEADER = [
    "rack_id", "site", "hosts", "feed_a_w", "feed_b_w", "budget_w", "nameplate_w",
    "p95_w", "headroom_w", "psu_n1_ok", "pending",
]
ALLOC_HEADER = [
    "host_id", "rack_id", "request_w", "alloc_w", "short_w", "overcommit", "amended",
]
ENERGY_HEADER = [
    "site", "hosts", "null_hosts", "zero_hosts", "it_kwh", "dc_kwh", "facility_kwh",
    "cost_cents", "capacity_kw", "pending",
]
ALARM_HEADER = [
    "circuit_id", "rack_id", "feed", "voltage_v", "expected_a", "failover_a",
    "warn_a", "crit_a", "state", "psu_over", "pending",
]
POOL_HEADER = [
    "site", "tenant", "hosts", "request_w", "entitlement_w", "granted_w", "cut_w",
    "pending",
]


class Upstream(object):
    """The phase-1 tables, and the phase-2 tables when a stage is given them."""

    def __init__(self, p1_dir, p2_dir=None):
        for directory in (p1_dir, p2_dir):
            if directory is None:
                continue
            if not os.path.isdir(directory):
                raise InputError("input directory not found: %s" % directory)
            if not os.access(directory, os.R_OK | os.X_OK):
                raise InputError("input directory is not readable: %s" % directory)
        self.p1_dir = p1_dir
        self.p2_dir = p2_dir
        self.hosts = read_csv_table(os.path.join(p1_dir, "hosts.csv"))
        self.circuits = read_csv_table(os.path.join(p1_dir, "circuits.csv"))
        self.demand = read_csv_table(os.path.join(p1_dir, "demand.csv"))
        self.psu = read_csv_table(os.path.join(p1_dir, "psu.csv"))
        self.amendments = read_csv_table(os.path.join(p1_dir, "amendments.csv"))
        self.registry = read_json_file(os.path.join(p1_dir, "registry.json"))

        self.host_by_id = {row["host_id"]: row for row in self.hosts}
        self.demand_by_id = {row["host_id"]: row for row in self.demand}
        self.circuit_by_id = {row["circuit_id"]: row for row in self.circuits}
        self.site_params = {row["site"]: row for row in self.registry.get("sites", [])}
        self.entitlement = {
            (row["site"], row["tenant"]): row["entitlement_w"]
            for row in self.registry.get("tenants", [])
        }
        self.rated = {}
        self.efficiency = {}
        for row in self.psu:
            model = row["psu_model"]
            self.rated[model] = as_int(row["rated_w"])
            self.efficiency[(model, as_int(row["load_pm"]))] = as_int(row["eff_bp"])
        self.rack_hosts = {}
        self.rack_site = {}
        for row in self.hosts:
            self.rack_hosts.setdefault(row["rack_id"], []).append(row)
            self.rack_site[row["rack_id"]] = row["site"]
        self.rack_circuits = {}
        for row in self.circuits:
            self.rack_circuits.setdefault(row["rack_id"], []).append(row)
            self.rack_site.setdefault(row["rack_id"], row["site"])
        self.pending_target = {}
        for row in self.amendments:
            self.pending_target[row["target"]] = self.pending_target.get(
                row["target"], 0
            ) + 1
        if p2_dir is not None:
            self.rack_budget = read_csv_table(os.path.join(p2_dir, "rack_budget.csv"))
            self.host_alloc = read_csv_table(os.path.join(p2_dir, "host_alloc.csv"))
            self.site_energy = read_csv_table(os.path.join(p2_dir, "site_energy.csv"))
            self.circuit_alarms = read_csv_table(
                os.path.join(p2_dir, "circuit_alarms.csv")
            )
            self.tenant_pool = read_csv_table(os.path.join(p2_dir, "tenant_pool.csv"))
            self.fleet_summary = read_json_file(
                os.path.join(p2_dir, "fleet_summary.json")
            )

    # -- shared terms ----------------------------------------------------
    def step_of(self, site):
        params = self.site_params.get(site, {})
        return as_int(params.get("cap_step_w"), 0) or 1

    def param(self, site, name, default=0):
        params = self.site_params.get(site, {})
        value = params.get(name)
        if value is None:
            return default
        return as_int(value, default)

    def feed_usable(self, rack):
        feeds = {}
        for row in self.rack_circuits.get(rack, []):
            feeds[row["feed"].upper()] = as_int(row["usable_w"], 0)
        return feeds

    def rack_budget_w(self, rack):
        feeds = self.feed_usable(rack)
        if not feeds:
            return 0
        smallest = min(feeds.values())
        step = self.step_of(self.rack_site.get(rack, ""))
        return (smallest // step) * step

    def host_ceiling(self, host):
        row = self.host_by_id[host]
        limits = [as_int(row["nameplate_w"], 0)]
        rated = self.rated.get(row["psu_model"])
        if rated is not None:
            limits.append(rated * as_int(row["psu_count"], 0))
        ceiling = opt_int(row["cap_ceiling_w"])
        if ceiling is not None:
            limits.append(ceiling)
        return min(limits)

    def host_request(self, host):
        row = self.host_by_id[host]
        measured = self.demand_by_id.get(host, {})
        samples = as_int(measured.get("samples"), 0)
        site = row["site"]
        step = self.step_of(site)
        if samples == 0:
            request = as_int(row["nameplate_w"], 0)
        else:
            margin = self.param(site, "margin_pm")
            raised = opt_dec(measured.get("p95_w")) * (1000 + margin) / 1000
            request = ceil_int(raised / step) * step
        request = max(request, as_int(row["floor_w"], 0))
        return min(request, self.host_ceiling(host))

    def allocate(self):
        """Allocation walk over hosts.csv in written order."""
        left = {}
        out = {}
        for row in self.hosts:
            rack = row["rack_id"]
            if rack not in left:
                left[rack] = self.rack_budget_w(rack)
            host = row["host_id"]
            request = self.host_request(host)
            floor = as_int(row["floor_w"], 0)
            alloc = max(0, min(request, left[rack]))
            overcommit = 0
            if alloc < floor:
                alloc = floor
                overcommit = 1
            left[rack] -= alloc
            out[host] = {
                "host_id": host,
                "rack_id": rack,
                "request_w": request,
                "alloc_w": alloc,
                "short_w": request - alloc,
                "overcommit": overcommit,
                "amended": 1 if self.pending_target.get(host) else 0,
            }
        return out

    def feed_load(self, rack, column):
        """Feed A and feed B shares of a per-host figure."""
        feed_a = Decimal(0)
        feed_b = Decimal(0)
        for row in self.rack_hosts.get(rack, []):
            value = column(row)
            if value is None:
                continue
            if as_int(row["psu_count"], 0) >= 2:
                feed_a += Decimal(value) / 2
                feed_b += Decimal(value) / 2
            else:
                feed_a += Decimal(value)
        return feed_a, feed_b

    def threshold(self, site, breaker, which):
        cont = self.param(site, "cont_pm")
        derate = self.param(site, "derate_pm")
        level = self.param(site, which)
        value = Decimal(breaker) * cont * derate * level / Decimal(10) ** 9
        return value.quantize(Decimal("0.1"), rounding=ROUND_FLOOR)

    def load_per_mille(self, watts, count, rated):
        if not count or not rated:
            return None
        value = half_even(Decimal(watts) * 1000 / (count * rated))
        return min(1000, max(1, value))


def phase2(p1_dir, out_dir):
    up = Upstream(p1_dir)
    alloc = up.allocate()
    amendments = up.amendments
    pending = up.pending_target

    rack_rows = []
    rack_budget = {}
    for rack in sorted(up.rack_circuits):
        site = up.rack_site.get(rack, "")
        feeds = up.feed_usable(rack)
        budget = up.rack_budget_w(rack)
        members = up.rack_hosts.get(rack, [])
        nameplate = sum(as_int(row["nameplate_w"], 0) for row in members)
        p95_total = Decimal(0)
        n1_ok = 0
        for row in members:
            measured = up.demand_by_id.get(row["host_id"], {})
            p95 = opt_dec(measured.get("p95_w")) or Decimal(0)
            p95_total += p95
            if as_int(row["psu_count"], 0) == 2:
                rated = up.rated.get(row["psu_model"])
                if rated is not None and p95 <= rated:
                    n1_ok += 1
        p95_whole = half_even(p95_total)
        count = pending_for_rack(up, rack)
        rack_budget[rack] = budget
        rack_rows.append(
            [
                rack, site, len(members), feeds.get("A"), feeds.get("B"), budget,
                nameplate, p95_whole, budget - p95_whole, n1_ok, count,
            ]
        )

    alloc_rows = []
    for row in up.hosts:
        info = alloc[row["host_id"]]
        alloc_rows.append([info[column] for column in ALLOC_HEADER])

    energy_rows = []
    site_names = sorted({row["site"] for row in up.hosts} | {row["site"] for row in up.circuits})
    for site in site_names:
        members = [row for row in up.hosts if row["site"] == site]
        null_hosts = 0
        zero_hosts = 0
        it_wh = 0
        dc_wh = 0
        for row in members:
            measured = up.demand_by_id.get(row["host_id"], {})
            samples = as_int(measured.get("samples"), 0)
            if samples == 0:
                null_hosts += 1
                continue
            if opt_dec(measured.get("peak_w")) == 0:
                zero_hosts += 1
            energy = as_int(measured.get("energy_wh"), 0)
            it_wh += energy
            rated = up.rated.get(row["psu_model"])
            load = up.load_per_mille(
                opt_dec(measured.get("mean_w")), as_int(row["psu_count"], 0), rated
            )
            basis = up.efficiency.get((row["psu_model"], load)) if load else None
            if basis:
                dc_wh += half_even(Decimal(energy) * basis / 10000)
        it_kwh = Decimal(dec_str(Decimal(it_wh) / 1000, 2))
        dc_kwh = dec_str(Decimal(dc_wh) / 1000, 2)
        facility = Decimal(
            dec_str(it_kwh * up.param(site, "pue_milli") / 1000, 2)
        )
        cost = half_even(facility * up.param(site, "tariff_mc") / 1000)
        capacity = Decimal(0)
        for rack in sorted(up.rack_circuits):
            if up.rack_site.get(rack) != site:
                continue
            feeds = up.feed_usable(rack)
            if feeds:
                capacity += min(feeds.values())
        energy_rows.append(
            [
                site, len(members), null_hosts, zero_hosts, dec_str(it_kwh, 2), dc_kwh,
                dec_str(facility, 2), cost, dec_str(capacity / 1000, 2),
                pending_for_site(up, site),
            ]
        )

    alarm_rows = []
    for row in sorted(up.circuits, key=lambda r: r["circuit_id"]):
        rack = row["rack_id"]
        site = row["site"]
        feed = row["feed"].upper()
        volts = as_int(row["voltage_v"], 0)
        breaker = as_int(row["breaker_a"], 0)
        mean_a, mean_b = up.feed_load(
            rack, lambda r: opt_dec(up.demand_by_id.get(r["host_id"], {}).get("mean_w")) or Decimal(0)
        )
        load = mean_a if feed == "A" else mean_b
        failover = Decimal(0)
        psu_over = 0
        for member in up.rack_hosts.get(rack, []):
            measured = up.demand_by_id.get(member["host_id"], {})
            peak = opt_dec(measured.get("peak_w")) or Decimal(0)
            count = as_int(member["psu_count"], 0)
            if feed == "A" or count >= 2:
                failover += peak
            if count == 2:
                rated = up.rated.get(member["psu_model"])
                if rated is not None and peak > rated:
                    psu_over += 1
        expected = dec_str(load / volts, 2) if volts else dec_str(0, 2)
        failover_a = dec_str(failover / volts, 2) if volts else dec_str(0, 2)
        warn = up.threshold(site, breaker, "warn_pm")
        crit = up.threshold(site, breaker, "crit_pm")
        state = alarm_state(Decimal(failover_a), warn, crit)
        alarm_rows.append(
            [
                row["circuit_id"], rack, feed, volts, expected, failover_a,
                dec_str(warn, 1), dec_str(crit, 1), state, psu_over,
                pending.get(row["circuit_id"], 0),
            ]
        )

    pool_rows = []
    pairs = set(up.entitlement)
    for row in up.hosts:
        pairs.add((row["site"], row["tenant"]))
    pool_left = {}
    for site in site_names:
        total = sum(
            rack_budget[rack]
            for rack in rack_budget
            if up.rack_site.get(rack) == site
        )
        pool_left[site] = floor_int(Decimal(total) * up.param(site, "pool_pm") / 1000)
    for site, tenant in sorted(pairs):
        members = [
            row for row in up.hosts
            if row["site"] == site and row["tenant"] == tenant
        ]
        request = sum(alloc[row["host_id"]]["alloc_w"] for row in members)
        entitlement = as_int(up.entitlement.get((site, tenant)), 0) or 0
        left = pool_left.get(site, 0)
        granted = max(0, min(request, entitlement, left))
        pool_left[site] = left - granted
        count = sum(pending.get(row["host_id"], 0) for row in members)
        pool_rows.append(
            [
                site, tenant, len(members), request, entitlement, granted,
                request - granted, count,
            ]
        )

    ensure_dir(out_dir)
    write_lines(os.path.join(out_dir, "rack_budget.csv"), csv_text(RACK_HEADER, rack_rows))
    write_lines(os.path.join(out_dir, "host_alloc.csv"), csv_text(ALLOC_HEADER, alloc_rows))
    write_lines(os.path.join(out_dir, "site_energy.csv"), csv_text(ENERGY_HEADER, energy_rows))
    write_lines(
        os.path.join(out_dir, "circuit_alarms.csv"), csv_text(ALARM_HEADER, alarm_rows)
    )
    write_lines(os.path.join(out_dir, "tenant_pool.csv"), csv_text(POOL_HEADER, pool_rows))

    inputs = {}
    for name in P1_FILES:
        label, entry = lineage_of(os.path.join(p1_dir, name), "p1/" + name)
        inputs[label] = entry
    sites = []
    for site in site_names:
        members = [row for row in up.hosts if row["site"] == site]
        sites.append(
            {
                "site": site,
                "hosts": len(members),
                "budget_w": sum(
                    rack_budget[rack] for rack in rack_budget
                    if up.rack_site.get(rack) == site
                ),
                "request_w": sum(alloc[row["host_id"]]["request_w"] for row in members),
                "alloc_w": sum(alloc[row["host_id"]]["alloc_w"] for row in members),
                "pending": pending_for_site(up, site),
            }
        )
    summary = {
        "freeze_utc": up.registry.get("freeze_utc"),
        "inputs": inputs,
        "sites": sites,
    }
    write_lines(os.path.join(out_dir, "fleet_summary.json"), json_text(summary))


def alarm_state(failover, warn, crit):
    if failover >= crit:
        return "crit"
    if failover >= warn:
        return "warn"
    return "ok"


def pending_for_rack(up, rack):
    count = 0
    for row in up.rack_hosts.get(rack, []):
        count += up.pending_target.get(row["host_id"], 0)
    for row in up.rack_circuits.get(rack, []):
        count += up.pending_target.get(row["circuit_id"], 0)
    return count


def pending_for_site(up, site):
    count = 0
    for row in up.hosts:
        if row["site"] == site:
            count += up.pending_target.get(row["host_id"], 0)
    for row in up.circuits:
        if row["site"] == site:
            count += up.pending_target.get(row["circuit_id"], 0)
    return count


# --------------------------------------------------------------------------
# phase 3
# --------------------------------------------------------------------------

CAP_KEYS = (
    "cap_w", "domain", "native_cap_w", "correction_ms", "throttle",
    "site_share_pm", "feed_breaker_a", "pue_milli",
)
THROTTLE = {"gold": "protect", "silver": "standard", "bronze": "aggressive"}


def build_lineage(p1_dir, p2_dir):
    lineage = {}
    for name in P1_FILES:
        label, entry = lineage_of(os.path.join(p1_dir, name), "p1/" + name)
        lineage[label] = entry
    for name in P2_FILES:
        label, entry = lineage_of(os.path.join(p2_dir, name), "p2/" + name)
        lineage[label] = entry
    return lineage


class Release(object):
    """Caps, alarms and finance worked out from a phase-1 and a phase-2 directory."""

    def __init__(self, p1_dir, p2_dir):
        self.up = Upstream(p1_dir, p2_dir)
        up = self.up
        self.alloc = {row["host_id"]: row for row in up.host_alloc}
        self.rack = {row["rack_id"]: row for row in up.rack_budget}
        self.alarms = {row["circuit_id"]: row for row in up.circuit_alarms}
        self.energy = {row["site"]: row for row in up.site_energy}
        self.pool = {(row["site"], row["tenant"]): row for row in up.tenant_pool}
        self.site_alloc = {
            entry["site"]: as_int(entry.get("alloc_w"), 0)
            for entry in up.fleet_summary.get("sites", [])
        }
        self.host_amendments = {}
        for row in up.amendments:
            self.host_amendments.setdefault(row["target"], []).append(row)
        self._caps()

    def _caps(self):
        up = self.up
        self.caps = {}
        for row in up.hosts:
            host = row["host_id"]
            site = row["site"]
            rack = row["rack_id"]
            step = up.step_of(site)
            cap = as_int(self.alloc[host]["alloc_w"], 0)
            pool_row = self.pool.get((site, row["tenant"]))
            if pool_row and as_int(pool_row["cut_w"], 0) > 0:
                request = as_int(pool_row["request_w"], 0)
                if request > 0:
                    cap = floor_int(
                        Decimal(cap) * as_int(pool_row["granted_w"], 0) / request
                    )
            floor = as_int(row["floor_w"], 0)
            priority = row["priority"]
            for amendment in self.host_amendments.get(host, []):
                field = amendment["field"]
                value = amendment["value"]
                if field == "cap_ceiling_w":
                    cap = min(cap, as_int(value, cap))
                elif field == "floor_w":
                    floor = as_int(value, floor)
                elif field == "priority":
                    priority = value
            cap = (cap // step) * step
            cap = max(cap, floor)
            rated = up.rated.get(row["psu_model"])
            if row["cap_domain"].upper() == "DC":
                load = up.load_per_mille(cap, as_int(row["psu_count"], 0), rated)
                basis = up.efficiency.get((row["psu_model"], load)) if load else None
                native = half_even(Decimal(cap) * basis / 10000) if basis else cap
            else:
                native = cap
            correction = up.param(site, "correction_ms")
            states = [
                self.alarms[circuit["circuit_id"]]["state"]
                for circuit in up.rack_circuits.get(rack, [])
                if circuit["circuit_id"] in self.alarms
            ]
            if any(state != "ok" for state in states):
                correction *= 2
            samples = as_int(up.demand_by_id.get(host, {}).get("samples"), 0)
            headroom = as_int(self.rack.get(rack, {}).get("headroom_w"), 0)
            if samples == 0:
                throttle = "static"
            elif headroom < 0:
                throttle = "aggressive"
            else:
                throttle = THROTTLE.get(priority, "aggressive")
            site_total = self.site_alloc.get(site, 0)
            share = half_even(Decimal(cap) * 1000 / site_total) if site_total else 0
            breakers = [
                as_int(circuit["breaker_a"], 0)
                for circuit in up.rack_circuits.get(rack, [])
            ]
            site_energy = self.energy.get(site, {})
            it_kwh = opt_dec(site_energy.get("it_kwh")) or Decimal(0)
            if it_kwh == 0:
                pue = up.param(site, "pue_milli")
            else:
                facility = opt_dec(site_energy.get("facility_kwh")) or Decimal(0)
                pue = half_even(facility * 1000 / it_kwh)
            self.caps[host] = {
                "cap_w": cap,
                "domain": row["cap_domain"],
                "native_cap_w": native,
                "correction_ms": correction,
                "throttle": throttle,
                "site_share_pm": share,
                "feed_breaker_a": min(breakers) if breakers else 0,
                "pue_milli": pue,
                "priority": priority,
            }

    # -- outputs ---------------------------------------------------------
    def ini_text(self, lineage):
        out = []
        for row in self.up.hosts:
            info = self.caps[row["host_id"]]
            out.append("[%s]" % row["host_id"])
            for key in CAP_KEYS:
                out.append("%s = %s" % (key, info[key]))
            out.append("")
        out.append("[lineage]")
        for label, entry in lineage.items():
            out.append(
                "%s = %s:%d:%d"
                % (label, entry["sha256"], entry["bytes"], entry["lines"])
            )
        return "\n".join(out) + "\n"

    def carried_breaker(self, circuit):
        value = None
        for amendment in self.host_amendments.get(circuit, []):
            if amendment["field"] == "breaker_a":
                value = as_int(amendment["value"])
        return value

    def pdu_alarms(self):
        up = self.up
        circuits = []
        for row in sorted(up.circuits, key=lambda r: r["circuit_id"]):
            circuit = row["circuit_id"]
            alarm = self.alarms.get(circuit, {})
            site = row["site"]
            volts = as_int(row["voltage_v"], 0)
            breaker = as_int(row["breaker_a"], 0)
            carried = self.carried_breaker(circuit)
            if carried is not None and carried != breaker:
                breaker = carried
                warn = up.threshold(site, breaker, "warn_pm")
                crit = up.threshold(site, breaker, "crit_pm")
            else:
                if carried is not None:
                    breaker = carried
                warn = opt_dec(alarm.get("warn_a")) or Decimal(0)
                crit = opt_dec(alarm.get("crit_a")) or Decimal(0)
            feed = row["feed"].upper()
            alloc_a, alloc_b = up.feed_load(
                row["rack_id"],
                lambda r: as_int(self.alloc[r["host_id"]]["alloc_w"], 0),
            )
            share = alloc_a if feed == "A" else alloc_b
            failover = opt_dec(alarm.get("failover_a")) or Decimal(0)
            circuits.append(
                {
                    "circuit_id": circuit,
                    "breaker_a": breaker,
                    "warn_a": dec_str(warn, 1),
                    "crit_a": dec_str(crit, 1),
                    "expected_a": alarm.get("expected_a"),
                    "alloc_a": dec_str(share / volts, 2) if volts else dec_str(0, 2),
                    "state": alarm_state(failover, warn, crit),
                }
            )
        return circuits

    def chargeback(self):
        up = self.up
        pairs = {}
        for row in up.hosts:
            key = (row["site"], row["tenant"])
            measured = up.demand_by_id.get(row["host_id"], {})
            energy = 0
            if as_int(measured.get("samples"), 0) > 0:
                energy = as_int(measured.get("energy_wh"), 0)
            entry = pairs.setdefault(key, {"hosts": 0, "energy": 0})
            entry["hosts"] += 1
            entry["energy"] += energy
        by_site = {}
        for (site, tenant), entry in pairs.items():
            by_site.setdefault(site, []).append((tenant, entry["energy"]))
        out = []
        for site in sorted(by_site):
            tenants = sorted(by_site[site])
            total = sum(energy for _tenant, energy in tenants)
            cost = as_int(self.energy.get(site, {}).get("cost_cents"), 0)
            shares = []
            for tenant, energy in tenants:
                if total:
                    exact = Decimal(cost) * energy / total
                else:
                    exact = Decimal(0)
                whole = floor_int(exact)
                shares.append([tenant, energy, whole, exact - whole])
            spare = cost - sum(entry[2] for entry in shares)
            order = sorted(
                range(len(shares)), key=lambda i: (-shares[i][3], shares[i][0])
            )
            for position in range(spare):
                shares[order[position % len(order)]][2] += 1
            for tenant, energy, whole, _remainder in shares:
                out.append(
                    {
                        "site": site,
                        "tenant": tenant,
                        "energy_wh": energy,
                        "share_ppm": half_even(Decimal(energy) * 1000000 / total)
                        if total
                        else 0,
                        "cost_cents": whole,
                    }
                )
        return out

    def exceptions(self, alarms):
        up = self.up
        out = []
        for row in up.hosts:
            host = row["host_id"]
            cap = self.caps[host]["cap_w"]
            peak = up.demand_by_id.get(host, {}).get("peak_w")
            if peak not in (None, "") and Decimal(cap) < Decimal(peak):
                out.append(
                    {
                        "type": "cap_below_peak",
                        "id": host,
                        "detail": "cap=%d;peak=%s" % (cap, peak),
                    }
                )
            info = self.alloc[host]
            if as_int(info["overcommit"], 0):
                out.append(
                    {
                        "type": "overcommit",
                        "id": host,
                        "detail": "alloc=%s;request=%s"
                        % (info["alloc_w"], info["request_w"]),
                    }
                )
        for row in up.rack_budget:
            if as_int(row["headroom_w"], 0) < 0:
                out.append(
                    {
                        "type": "rack_over_budget",
                        "id": row["rack_id"],
                        "detail": "headroom=%s" % row["headroom_w"],
                    }
                )
        for entry in alarms:
            if entry["state"] == "crit":
                alarm = self.alarms.get(entry["circuit_id"], {})
                out.append(
                    {
                        "type": "circuit_crit",
                        "id": entry["circuit_id"],
                        "detail": "failover=%s;crit=%s"
                        % (alarm.get("failover_a"), entry["crit_a"]),
                    }
                )
        for row in self.up.tenant_pool:
            if as_int(row["cut_w"], 0) > 0:
                out.append(
                    {
                        "type": "tenant_cut",
                        "id": "%s@%s" % (row["tenant"], row["site"]),
                        "detail": "cut=%s" % row["cut_w"],
                    }
                )
        out.sort(key=lambda e: (e["type"], e["id"]))
        return out

    def capacity(self):
        up = self.up
        free_by_rack = {}
        for row in up.rack_budget:
            rack = row["rack_id"]
            used = sum(
                self.caps[member["host_id"]]["cap_w"]
                for member in up.rack_hosts.get(rack, [])
            )
            free_by_rack[rack] = as_int(row["budget_w"], 0) - used
        sites = []
        for site in sorted({row["site"] for row in up.rack_budget}):
            racks = sorted(
                row["rack_id"] for row in up.rack_budget if row["site"] == site
            )
            total = sum(
                as_int(row["budget_w"], 0)
                for row in up.rack_budget
                if row["site"] == site
            )
            quota = floor_int(Decimal(total) * up.param(site, "pool_pm") / 1000)
            for row in up.tenant_pool:
                if row["site"] == site:
                    quota -= as_int(row["granted_w"], 0)
            slots = 0
            for rack in racks:
                available = min(max(free_by_rack[rack], 0), max(quota, 0))
                taken = available // 500
                quota -= taken * 500
                slots += taken
            sites.append(
                {
                    "site": site,
                    "free_w": sum(free_by_rack[rack] for rack in racks),
                    "slots_500w": slots,
                    "racks_full": sum(1 for rack in racks if free_by_rack[rack] < 500),
                }
            )
        return sites

    def applied(self):
        up = self.up
        state = {}
        for row in up.hosts:
            state[row["host_id"]] = {
                "floor_w": row["floor_w"],
                "cap_ceiling_w": row["cap_ceiling_w"] or None,
                "priority": row["priority"],
            }
        for row in up.circuits:
            state[row["circuit_id"]] = {"breaker_a": row["breaker_a"]}
        out = []
        for row in up.amendments:
            target = row["target"]
            field = row["field"]
            before = state.get(target, {}).get(field)
            out.append(
                {
                    "amendment_id": row["amendment_id"],
                    "target": target,
                    "field": field,
                    "before": before,
                    "after": row["value"],
                }
            )
            if target in state:
                state[target][field] = row["value"]
        return out


def phase3(p1_dir, p2_dir, out_dir):
    release = Release(p1_dir, p2_dir)
    lineage = build_lineage(p1_dir, p2_dir)
    alarms = release.pdu_alarms()
    ensure_dir(out_dir)
    write_lines(os.path.join(out_dir, "bmc_caps.ini"), release.ini_text(lineage))
    write_lines(
        os.path.join(out_dir, "pdu_alarms.json"),
        json_text({"circuits": alarms, "lineage": lineage}),
    )
    write_lines(
        os.path.join(out_dir, "chargeback.json"),
        json_text({"tenants": release.chargeback(), "lineage": lineage}),
    )
    write_lines(
        os.path.join(out_dir, "exceptions.json"),
        json_text({"exceptions": release.exceptions(alarms), "lineage": lineage}),
    )
    write_lines(
        os.path.join(out_dir, "capacity.json"),
        json_text({"sites": release.capacity(), "lineage": lineage}),
    )
    caps = [release.caps[row["host_id"]] for row in release.up.hosts]
    write_lines(
        os.path.join(out_dir, "release.json"),
        json_text(
            {
                "freeze_utc": release.up.registry.get("freeze_utc"),
                "applied": release.applied(),
                "totals": {
                    "hosts": len(caps),
                    "cap_w": sum(info["cap_w"] for info in caps),
                    "native_cap_w": sum(info["native_cap_w"] for info in caps),
                },
                "lineage": lineage,
            }
        ),
    )


# --------------------------------------------------------------------------
# command line
# --------------------------------------------------------------------------

STAGES = {"phase1": 2, "phase2": 2, "phase3": 3}


def main(argv):
    try:
        if not argv or argv[0] not in STAGES:
            raise UsageError(
                "unknown stage: %s" % (argv[0] if argv else "<none>")
            )
        stage = argv[0]
        rest = argv[1:]
        if len(rest) != STAGES[stage]:
            raise UsageError(
                "%s takes %d arguments, got %d" % (stage, STAGES[stage], len(rest))
            )
        if stage == "phase1":
            phase1(rest[0], rest[1])
        elif stage == "phase2":
            phase2(rest[0], rest[1])
        else:
            phase3(rest[0], rest[1], rest[2])
    except UsageError as exc:
        print("%s: error: %s" % (PROG, exc), file=sys.stderr)
        return 2
    except InputError as exc:
        print("%s: error: %s" % (PROG, exc), file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
