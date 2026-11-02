#!/usr/bin/env python3
"""Normalize a LedgerPort quarterly settlement drop.

Usage:  python3 transform.py <DATA_DIR> <OUT_DIR>

The drop is a flat directory of transaction feeds, reference registry shards
and policy registers.  Everything the pipeline needs is discovered from the
directory itself: feeds come from the ``source_profiles`` register, registry
shards are recognised by their column sets and policy blocks by their key
names, so no file name, identifier or total is wired into the logic.
"""

from __future__ import annotations

import configparser
import csv
import json
import os
import re
import sqlite3
import sys
import tomllib
import zipfile
from bisect import bisect_right
from datetime import date, datetime, timedelta
from decimal import (
    Decimal,
    ROUND_CEILING,
    ROUND_DOWN,
    ROUND_FLOOR,
    ROUND_HALF_DOWN,
    ROUND_HALF_EVEN,
    ROUND_HALF_UP,
    ROUND_UP,
    getcontext,
)

import openpyxl
import pyarrow.parquet as pq
import pypdf
import yaml
from lxml import etree

getcontext().prec = 60

FEED_COLUMNS = (
    "event_id",
    "event_ts",
    "customer_id",
    "sku",
    "warehouse",
    "terminal",
    "kind",
    "quantity",
    "unit_price",
    "currency",
    "revision",
    "ref_event",
)

REGISTRY_COLUMNS = {
    "parties": ("customer_id", "valid_from", "valid_to", "segment", "postal_code"),
    "postal": ("postal_prefix", "valid_from", "valid_to", "region"),
    "items": ("sku", "valid_from", "valid_to", "category", "active"),
    "price": ("sku", "version_id", "valid_from", "valid_to", "list_price_minor", "currency"),
    "warehouses": ("warehouse", "valid_from", "valid_to", "postal_code"),
    "terminals": ("terminal", "valid_from", "valid_to", "channel_group", "utc_offset_minutes"),
    "fx": ("rate_date", "currency", "quote_source", "usd_rate"),
    "calendar": ("calendar_date", "region", "variant", "fiscal_week"),
    "crosswalk": ("legacy_code", "code_kind", "current_code"),
    "voids": ("voided_event_id",),
    "revisions": ("retired_source", "superseded_from"),
}
REGISTRY_BY_COLUMNS = {frozenset(v): k for k, v in REGISTRY_COLUMNS.items()}

ROUNDING_MODES = {
    "half_even": ROUND_HALF_EVEN,
    "half_up": ROUND_HALF_UP,
    "half_down": ROUND_HALF_DOWN,
    "floor": ROUND_FLOOR,
    "ceiling": ROUND_CEILING,
    "up": ROUND_UP,
    "down": ROUND_DOWN,
}

KINDS = ("sale", "refund", "fee", "credit")
TERMINAL_KINDS = ("sale", "refund")

REJECT_CODES = (
    "MALFORMED_ROW",
    "NON_NUMERIC_QUANTITY",
    "UNKNOWN_TERMINAL",
    "OUT_OF_SCOPE",
    "SUPERSEDED_SOURCE",
    "VOIDED",
    "UNKNOWN_CUSTOMER",
    "UNKNOWN_SKU",
    "INACTIVE_SKU",
    "UNKNOWN_WAREHOUSE",
    "NO_PRICE_VERSION",
    "NO_FX_RATE",
    "NO_FISCAL_WEEK",
    "DUPLICATE_LOWER_AUTHORITY",
    "REVERSED",
    "REVERSAL_ORPHAN",
)

EXCEL_EPOCH = datetime(1899, 12, 30)
ID_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-")


# ---------------------------------------------------------------- text helpers


def strip_bom(text: str) -> str:
    if text.startswith("\ufeff"):
        return text[1:]
    if text.startswith("\u00ef\u00bb\u00bf"):
        return text[3:]
    return text


def decode(data: bytes, encoding: str = "utf-8") -> str:
    try:
        text = data.decode(encoding)
    except (UnicodeDecodeError, LookupError):
        text = data.decode("latin-1")
    return strip_bom(text)


def clean_name(name: str) -> str:
    return strip_bom(str(name or "")).strip().lower()


def body_lines(text: str):
    """Text container lines with comments and filler removed."""
    for line in text.split("\n"):
        line = line.rstrip("\r")
        if not line.strip() or line.startswith("#"):
            continue
        yield line


def cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "Y" if value else "N"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


# ----------------------------------------------------------- container readers
#
# Every reader yields tables as ``(columns, rows)`` where ``rows`` is a list of
# dicts keyed by the cleaned column names, in file order.


def read_delimited(data: bytes, encoding: str, delimiter: str):
    text = decode(data, encoding)
    reader = csv.reader(body_lines(text), delimiter=delimiter)
    try:
        header = next(reader)
    except StopIteration:
        return []
    columns = [clean_name(c) for c in header]
    rows = []
    for raw in reader:
        row = {c: (raw[i].strip() if i < len(raw) else "") for i, c in enumerate(columns)}
        rows.append(row)
    return [(columns, rows)]


def read_fixed_width(data: bytes, encoding: str):
    text = decode(data, encoding)
    lines = list(body_lines(text))
    if not lines:
        return []
    spans = [(m.start(), clean_name(m.group())) for m in re.finditer(r"\S+", lines[0])]
    columns = [name for _, name in spans]
    starts = [start for start, _ in spans]
    ends = starts[1:] + [None]
    rows = []
    for line in lines[1:]:
        row = {}
        for name, start, end in zip(columns, starts, ends):
            row[name] = line[start:end].strip() if end is not None else line[start:].strip()
        rows.append(row)
    return [(columns, rows)]


def read_json(data: bytes, encoding: str):
    doc = json.loads(decode(data, encoding))
    raw_rows = doc.get("rows") or []
    columns = [clean_name(c) for c in doc.get("columns") or []]
    if not columns and raw_rows:
        columns = [clean_name(c) for c in raw_rows[0]]
    rows = [{clean_name(k): cell(v) for k, v in r.items()} for r in raw_rows]
    return [(columns, rows)]


def read_jsonl(data: bytes, encoding: str):
    rows = []
    columns = []
    for line in body_lines(decode(data, encoding)):
        obj = json.loads(line)
        if not isinstance(obj, dict) or set(obj) == {"_note"}:
            continue
        row = {clean_name(k): cell(v) for k, v in obj.items()}
        if not columns:
            columns = list(row)
        rows.append(row)
    return [(columns, rows)]


def read_xml(data: bytes, encoding: str):
    root = etree.fromstring(data, parser=etree.XMLParser(recover=True, huge_tree=True))
    rows = []
    columns = []
    for element in root.iter("row"):
        row = {}
        for child in element:
            if isinstance(child.tag, str):
                row[clean_name(child.tag)] = (child.text or "").strip()
        if not columns:
            columns = list(row)
        rows.append(row)
    return [(columns, rows)]


def read_parquet(path: str):
    table = pq.read_table(path)
    columns = [clean_name(c) for c in table.column_names]
    data = [table.column(i).to_pylist() for i in range(table.num_columns)]
    rows = []
    for i in range(table.num_rows):
        rows.append({columns[j]: cell(data[j][i]) for j in range(len(columns))})
    return [(columns, rows)]


def read_db(path: str):
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        cursor = connection.execute('SELECT * FROM "lines"')
        columns = [clean_name(d[0]) for d in cursor.description]
        rows = [{columns[i]: cell(v) for i, v in enumerate(values)} for values in cursor]
    finally:
        connection.close()
    return [(columns, rows)]


def read_xlsx(path: str):
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        name = "lines" if "lines" in workbook.sheetnames else workbook.sheetnames[0]
        sheet = workbook[name]
        iterator = sheet.iter_rows(values_only=True)
        try:
            header = next(iterator)
        except StopIteration:
            return []
        columns = [clean_name(c) for c in header if c is not None]
        rows = []
        for values in iterator:
            if values is None or all(v is None for v in values):
                continue
            row = {c: cell(values[i]) if i < len(values) else "" for i, c in enumerate(columns)}
            rows.append(row)
    finally:
        workbook.close()
    return [(columns, rows)]


DOCX_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def read_docx(path: str):
    with zipfile.ZipFile(path) as archive:
        document = archive.read("word/document.xml")
    root = etree.fromstring(document, parser=etree.XMLParser(huge_tree=True))
    table = None
    for candidate in root.iter(DOCX_NS + "tbl"):
        table = candidate
    if table is None:
        return []
    grid = []
    for tr in table.iter(DOCX_NS + "tr"):
        grid.append(
            [
                "".join(node.text or "" for node in tc.iter(DOCX_NS + "t")).strip()
                for tc in tr.iter(DOCX_NS + "tc")
            ]
        )
    if not grid:
        return []
    columns = [clean_name(c) for c in grid[0]]
    rows = [
        {c: (values[i] if i < len(values) else "") for i, c in enumerate(columns)}
        for values in grid[1:]
    ]
    return [(columns, rows)]


def read_pdf(path: str):
    reader = pypdf.PdfReader(path)
    columns = None
    rows = []
    for page in reader.pages:
        for line in page.extract_text().split("\n"):
            if " | " not in line:
                continue
            values = [v.strip() for v in line.split(" | ")]
            if columns is None:
                columns = [clean_name(v) for v in values]
                continue
            rows.append({c: (values[i] if i < len(values) else "") for i, c in enumerate(columns)})
    if columns is None:
        return []
    return [(columns, rows)]


def split_pipe_row(line: str):
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [v.strip() for v in stripped.split("|")]


def read_markdown(data: bytes, encoding: str):
    text = decode(data, encoding)
    tables = []
    columns = None
    rows = None
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2:
            values = split_pipe_row(stripped)
            if columns is None:
                columns = [clean_name(v) for v in values]
                rows = []
            elif set("".join(values)) <= set("-: "):
                continue
            else:
                rows.append(
                    {c: (values[i] if i < len(values) else "") for i, c in enumerate(columns)}
                )
            continue
        if columns is not None:
            tables.append((columns, rows))
            columns = None
            rows = None
    if columns is not None:
        tables.append((columns, rows))
    return tables


def read_html(data: bytes, encoding: str):
    # A board may append further sections after its first </html>, so the
    # document terminators are dropped before parsing.
    text = re.sub(r"(?i)</(?:body|html)>", "", decode(data, encoding))
    root = etree.fromstring(text, parser=etree.HTMLParser(huge_tree=True))
    tables = []
    for element in root.iter("table"):
        columns = None
        rows = []
        for tr in element.iter("tr"):
            values = [
                "".join(td.itertext()).strip()
                for td in tr
                if isinstance(td.tag, str) and td.tag in ("td", "th")
            ]
            if not values:
                continue
            if columns is None:
                columns = [clean_name(v) for v in values]
                continue
            rows.append({c: (values[i] if i < len(values) else "") for i, c in enumerate(columns)})
        if columns:
            tables.append((columns, rows))
    return tables


def read_log(data: bytes, encoding: str):
    rows = []
    columns = []
    for line in body_lines(decode(data, encoding)):
        row = {}
        for token in line.split(" "):
            if "=" not in token:
                continue
            key, _, value = token.partition("=")
            value = value.replace("\u00a0", " ")
            if value == "-":
                value = ""
            row[clean_name(key)] = value
        if not row:
            continue
        if not columns:
            columns = list(row)
        rows.append(row)
    return [(columns, rows)]


def read_ini_sections(data: bytes, encoding: str):
    parser = configparser.ConfigParser(strict=False, interpolation=None, delimiters=("=",))
    parser.optionxform = clean_name
    parser.read_string(decode(data, encoding))
    return parser


def read_ini(data: bytes, encoding: str):
    parser = read_ini_sections(data, encoding)
    indexed = []
    for name in parser.sections():
        match = re.fullmatch(r"row\.(\d+)", name.strip())
        if match:
            indexed.append((int(match.group(1)), name))
    indexed.sort()
    rows = [dict(parser[name]) for _, name in indexed]
    columns = list(rows[0]) if rows else []
    return [(columns, rows)]


def rows_from_mapping_list(entries):
    rows = []
    columns = []
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        row = {clean_name(k): cell(v) for k, v in entry.items()}
        if not columns:
            columns = list(row)
        rows.append(row)
    if not rows:
        return []
    return [(columns, rows)]


def read_toml(data: bytes, encoding: str):
    return rows_from_mapping_list(tomllib.loads(decode(data, encoding)).get("lines"))


def read_yaml(data: bytes, encoding: str):
    doc = yaml.safe_load(decode(data, encoding)) or {}
    return rows_from_mapping_list(doc.get("lines") if isinstance(doc, dict) else None)


def read_mbox(data: bytes, encoding: str):
    rows = []
    columns = []
    text = decode(data, encoding)
    current = None
    in_body = False
    for line in text.split("\n"):
        line = line.rstrip("\r")
        if line.startswith("From "):
            if current:
                rows.append(current)
            current = {}
            in_body = False
            continue
        if current is None:
            continue
        if not in_body:
            if not line.strip():
                in_body = True
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            current[clean_name(key)] = value.strip()
    if current:
        rows.append(current)
    rows = [r for r in rows if r]
    for row in rows:
        if row:
            columns = list(row)
            break
    return [(columns, rows)]


def read_ics(data: bytes, encoding: str):
    text = decode(data, encoding)
    unfolded = []
    for line in text.split("\n"):
        line = line.rstrip("\r")
        if line[:1] in (" ", "\t") and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
    rows = []
    columns = []
    current = None
    for line in unfolded:
        if line.strip() == "BEGIN:VEVENT":
            current = {}
            continue
        if line.strip() == "END:VEVENT":
            if current:
                if not columns:
                    columns = list(current)
                rows.append(current)
            current = None
            continue
        if current is None or not line.startswith("X-"):
            continue
        key, _, value = line.partition(":")
        key = key.split(";")[0]
        current[clean_name(key[2:].replace("-", "_"))] = value.strip()
    return [(columns, rows)]


BINARY_READERS = {
    "parquet": read_parquet,
    "db": read_db,
    "xlsx": read_xlsx,
    "docx": read_docx,
    "pdf": read_pdf,
}

TEXT_READERS = {
    "csv": lambda d, e: read_delimited(d, e, ","),
    "tsv": lambda d, e: read_delimited(d, e, "\t"),
    "txt": read_fixed_width,
    "json": read_json,
    "jsonl": read_jsonl,
    "xml": read_xml,
    "md": read_markdown,
    "html": read_html,
    "log": read_log,
    "ini": read_ini,
    "toml": read_toml,
    "yaml": read_yaml,
    "mbox": read_mbox,
    "ics": read_ics,
}


def read_container(path: str, container: str, encoding: str = "utf-8"):
    if container in BINARY_READERS:
        return BINARY_READERS[container](path)
    reader = TEXT_READERS.get(container)
    if reader is None:
        return []
    with open(path, "rb") as handle:
        data = handle.read()
    return reader(data, encoding)


# -------------------------------------------------------------- canonical form


class Canonicaliser:
    def __init__(self, homoglyphs: dict):
        self.table = {ord(k): v for k, v in homoglyphs.items()}
        self.cache: dict[str, str] = {}

    def __call__(self, value: str) -> str:
        if not value:
            return ""
        hit = self.cache.get(value)
        if hit is not None:
            return hit
        text = value.translate(self.table).strip().upper()
        text = "".join(ch for ch in text if ch in ID_CHARS)
        index = text.find("-")
        if index >= 0:
            text = text[:index] + "-" + text[index + 1 :].lstrip("0")
        self.cache[value] = text
        return text


# ---------------------------------------------------------- dated registries


class DatedRegistry:
    """Effective dated registry: ``valid_from <= day < valid_to``."""

    __slots__ = ("spans", "starts")

    def __init__(self):
        self.spans: dict[object, list] = {}
        self.starts: dict[object, list] = {}

    def add(self, key, valid_from: str, valid_to: str, payload) -> None:
        self.spans.setdefault(key, []).append((valid_from, valid_to, payload))

    def finish(self) -> None:
        for key, spans in self.spans.items():
            spans.sort(key=lambda s: s[0])
            self.starts[key] = [s[0] for s in spans]

    def get(self, key, day: str):
        spans = self.spans.get(key)
        if not spans:
            return None
        index = bisect_right(self.starts[key], day) - 1
        if index < 0:
            return None
        valid_from, valid_to, payload = spans[index]
        if valid_from <= day < valid_to:
            return payload
        return None


# ------------------------------------------------------------------ the drop


class Drop:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.files = sorted(
            name
            for name in os.listdir(data_dir)
            if os.path.isfile(os.path.join(data_dir, name))
        )
        self.input_file_count = len(self.files)

        self.source_profiles: dict[str, dict] = {}
        self.scope_windows: dict[str, dict] = {}
        self.settlement_window: dict[str, str] = {}
        self.homoglyphs: dict[str, str] = {}
        self.authority: dict[str, dict[str, int]] = {}
        self.minor_units: dict[str, int] = {}
        self.fx_policy: dict[str, str] = {}
        self.calendar_variant = None
        self.superseded: dict[str, str] = {}

        self.tables: dict[str, list] = {name: [] for name in REGISTRY_COLUMNS}

        self._load_policies()
        self.feeds = sorted(self.source_profiles)
        self._load_reference_tables()
        self._build_registries()

    # -- policy registers ---------------------------------------------------

    def _policy_documents(self):
        for name in self.files:
            extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
            if extension not in ("yaml", "yml", "toml", "ini"):
                continue
            path = os.path.join(self.data_dir, name)
            with open(path, "rb") as handle:
                data = handle.read()
            if extension in ("yaml", "yml"):
                doc = yaml.safe_load(decode(data)) or {}
                if isinstance(doc, dict):
                    yield name, "mapping", doc
            elif extension == "toml":
                yield name, "mapping", tomllib.loads(decode(data))
            else:
                yield name, "ini", read_ini_sections(data, "utf-8")

    def _load_policies(self) -> None:
        for _name, flavour, doc in self._policy_documents():
            if flavour == "mapping":
                sections = doc
                get = lambda section: sections.get(section)
            else:
                sections = doc
                get = lambda section: dict(doc[section]) if doc.has_section(section) else None

            profiles = get("source_profiles")
            if isinstance(profiles, dict):
                for feed, profile in profiles.items():
                    self.source_profiles[feed] = {clean_name(k): v for k, v in profile.items()}

            windows = get("scope_windows")
            if isinstance(windows, dict):
                for stem, window in windows.items():
                    self.scope_windows[stem] = {clean_name(k): str(v) for k, v in window.items()}

            window = get("settlement_window")
            if isinstance(window, dict):
                self.settlement_window = {clean_name(k): str(v) for k, v in window.items()}

            glyphs = get("homoglyphs")
            if isinstance(glyphs, dict):
                for code, replacement in glyphs.items():
                    self.homoglyphs[chr(int(str(code), 16))] = str(replacement)

            units = get("minor_units")
            if isinstance(units, dict):
                for currency, exponent in units.items():
                    self.minor_units[str(currency)] = int(exponent)

            fx = get("fx")
            if isinstance(fx, dict):
                self.fx_policy.update({clean_name(k): v for k, v in fx.items()})

            calendar = get("fiscal_calendar")
            if isinstance(calendar, dict):
                variant = calendar.get("variant")
                if variant:
                    self.calendar_variant = str(variant)

            names = sections.keys() if flavour == "mapping" else doc.sections()
            for section in names:
                match = re.fullmatch(r"authority_(\w+)", str(section).strip())
                if not match:
                    continue
                block = get(str(section))
                if isinstance(block, dict):
                    self.authority[match.group(1)] = {
                        str(k): int(str(v)) for k, v in block.items()
                    }

    # -- reference shards ---------------------------------------------------

    def _load_reference_tables(self) -> None:
        for name in self.files:
            if name in self.source_profiles:
                continue
            extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
            container = "yaml" if extension == "yml" else extension
            path = os.path.join(self.data_dir, name)
            for columns, rows in read_container(path, container):
                registry = REGISTRY_BY_COLUMNS.get(frozenset(columns))
                if registry:
                    self.tables[registry].append((name, rows))

    def _build_registries(self) -> None:
        canon = Canonicaliser(self.homoglyphs)
        self.canon = canon

        crosswalk: dict[str, str] = {}
        for _name, rows in self.tables["crosswalk"]:
            for row in rows:
                if row.get("code_kind") == "carrier":
                    continue
                crosswalk[canon(row.get("legacy_code", ""))] = canon(row.get("current_code", ""))
        crosswalk.pop("", None)
        self.crosswalk = crosswalk

        self.parties = DatedRegistry()
        for _name, rows in self.tables["parties"]:
            for row in rows:
                self.parties.add(
                    canon(row.get("customer_id", "")),
                    row.get("valid_from", ""),
                    row.get("valid_to", ""),
                    (row.get("segment", ""), row.get("postal_code", "")),
                )
        self.parties.finish()

        self.postal = DatedRegistry()
        for _name, rows in self.tables["postal"]:
            for row in rows:
                self.postal.add(
                    row.get("postal_prefix", "").strip(),
                    row.get("valid_from", ""),
                    row.get("valid_to", ""),
                    row.get("region", ""),
                )
        self.postal.finish()

        self.items = DatedRegistry()
        for _name, rows in self.tables["items"]:
            for row in rows:
                self.items.add(
                    canon(row.get("sku", "")),
                    row.get("valid_from", ""),
                    row.get("valid_to", ""),
                    (row.get("category", ""), row.get("active", "")),
                )
        self.items.finish()

        self.prices = DatedRegistry()
        for _name, rows in self.tables["price"]:
            for row in rows:
                self.prices.add(
                    canon(row.get("sku", "")),
                    row.get("valid_from", ""),
                    row.get("valid_to", ""),
                    row.get("version_id", ""),
                )
        self.prices.finish()

        self.warehouses = DatedRegistry()
        for _name, rows in self.tables["warehouses"]:
            for row in rows:
                self.warehouses.add(
                    canon(row.get("warehouse", "")),
                    row.get("valid_from", ""),
                    row.get("valid_to", ""),
                    row.get("postal_code", ""),
                )
        self.warehouses.finish()

        self.terminals = DatedRegistry()
        for _name, rows in self.tables["terminals"]:
            for row in rows:
                offset = row.get("utc_offset_minutes", "") or "0"
                self.terminals.add(
                    canon(row.get("terminal", "")),
                    row.get("valid_from", ""),
                    row.get("valid_to", ""),
                    (row.get("channel_group", ""), int(offset)),
                )
        self.terminals.finish()

        quote_source = str(self.fx_policy["quote_source"])
        self.fx_rates: dict[tuple[str, str], Decimal] = {}
        for _name, rows in self.tables["fx"]:
            for row in rows:
                if row.get("quote_source") != quote_source:
                    continue
                self.fx_rates[(row.get("currency", ""), row.get("rate_date", ""))] = Decimal(
                    row.get("usd_rate", "0")
                )
        self.carry_forward_days = int(str(self.fx_policy["carry_forward_days"]))
        self.rounding = ROUNDING_MODES[str(self.fx_policy["rounding_mode"])]

        variant = self.calendar_variant
        self.calendar: dict[tuple[str, str], str] = {}
        for _name, rows in self.tables["calendar"]:
            for row in rows:
                if row.get("variant") != variant:
                    continue
                self.calendar[(row.get("calendar_date", ""), row.get("region", ""))] = row.get(
                    "fiscal_week", ""
                )

        self.voids = set()
        for _name, rows in self.tables["voids"]:
            for row in rows:
                self.voids.add(canon(row.get("voided_event_id", "")))
        self.voids.discard("")

        stems = {name.rsplit(".", 1)[0]: name for name in self.feeds}
        for _name, rows in self.tables["revisions"]:
            for row in rows:
                feed = stems.get(row.get("retired_source", "").strip())
                if feed:
                    self.superseded[feed] = row.get("superseded_from", "").strip()
        self.scoped: dict[str, dict] = {}
        for stem, window in self.scope_windows.items():
            feed = stems.get(stem)
            if feed:
                self.scoped[feed] = window

    def resolve(self, code: str) -> str:
        return self.crosswalk.get(code, code)

    def registry_values(self, registry: str, column: str):
        """Every value a registry publishes for one of its columns, sorted."""
        values = set()
        for _name, rows in self.tables[registry]:
            for row in rows:
                value = row.get(column, "")
                if value:
                    values.add(value)
        return sorted(values)


# -------------------------------------------------------------- feed reading


DATE_PATTERNS = {
    "iso": re.compile(r"^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})$"),
    "us_slash": re.compile(r"^(\d{2})/(\d{2})/(\d{4}) (\d{2}):(\d{2}):(\d{2})$"),
    "eu_dot": re.compile(r"^(\d{2})\.(\d{2})\.(\d{4}) (\d{2}):(\d{2}):(\d{2})$"),
}
EPOCH_PATTERN = re.compile(r"^-?\d+$")
SERIAL_PATTERN = re.compile(r"^-?\d+(\.\d+)?$")
DIGITS_PATTERN = re.compile(r"^\d+$")


def parse_timestamp(text: str, style: str):
    text = (text or "").strip()
    if not text:
        return None
    try:
        if style in DATE_PATTERNS:
            match = DATE_PATTERNS[style].match(text)
            if not match:
                return None
            groups = [int(g) for g in match.groups()]
            if style == "iso":
                year, month, day, hour, minute, second = groups
            elif style == "us_slash":
                month, day, year, hour, minute, second = groups
            else:
                day, month, year, hour, minute, second = groups
            return datetime(year, month, day, hour, minute, second)
        if style == "epoch_s":
            if not EPOCH_PATTERN.match(text):
                return None
            return datetime(1970, 1, 1) + timedelta(seconds=int(text))
        if style == "epoch_ms":
            if not EPOCH_PATTERN.match(text):
                return None
            return datetime(1970, 1, 1) + timedelta(milliseconds=int(text))
        if style == "excel_serial":
            if not SERIAL_PATTERN.match(text):
                return None
            seconds = (Decimal(text) * 86400).quantize(Decimal(1), rounding=ROUND_HALF_UP)
            return EXCEL_EPOCH + timedelta(seconds=int(seconds))
    except (ValueError, OverflowError):
        return None
    return None


def parse_price(text: str, decimal_style: str, exponent=None):
    """Read a price magnitude; brackets mark no sign, only presentation."""
    text = (text or "").strip()
    if not text:
        return None
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1].strip()
    if text[:1] in ("+", "-"):
        text = text[1:].strip()
    if decimal_style == "comma":
        if text.count(",") > 1:
            return None
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        return None
    match = re.fullmatch(r"(\d+)(?:\.(\d+))?", text)
    if not match:
        return None
    if exponent is not None and len(match.group(2) or "") > exponent:
        return None
    return Decimal(text)


def read_feed(drop: Drop, name: str):
    profile = drop.source_profiles[name]
    container = str(profile.get("container", ""))
    encoding = str(profile.get("encoding", "utf-8"))
    path = os.path.join(drop.data_dir, name)
    tables = read_container(path, container, encoding)
    rows = []
    for _columns, table_rows in tables:
        rows.extend(table_rows)
    return rows


# ---------------------------------------------------------------- the pipeline


class Record:
    __slots__ = (
        "source_file",
        "position",
        "event_id",
        "kind",
        "revision",
        "ref_event",
        "posting_date",
        "fields",
    )


def build_records(drop: Drop):
    canon = drop.canon
    window_start = drop.settlement_window.get("start", "")
    window_end = drop.settlement_window.get("end_exclusive", "")
    minor_units = drop.minor_units
    rejected_by_code = {}
    rejected_by_source = {feed: 0 for feed in drop.feeds}
    candidates = []

    def reject(feed, code):
        rejected_by_code[code] = rejected_by_code.get(code, 0) + 1
        rejected_by_source[feed] = rejected_by_source.get(feed, 0) + 1

    for feed in drop.feeds:
        profile = drop.source_profiles[feed]
        date_style = str(profile.get("date_style", "iso"))
        decimal_style = str(profile.get("decimal_style", "point"))
        feed_offset = int(profile.get("utc_offset_minutes", 0) or 0)
        scope = drop.scoped.get(feed)
        scope_start = scope.get("scope_start") if scope else None
        scope_end = scope.get("scope_end_exclusive") if scope else None
        retired_from = drop.superseded.get(feed)

        for position, row in enumerate(read_feed(drop, feed)):
            event_id = canon(row.get("event_id", ""))
            kind = (row.get("kind", "") or "").strip()
            currency = (row.get("currency", "") or "").strip()
            exponent = minor_units.get(currency)
            price = parse_price(row.get("unit_price", ""), decimal_style, exponent)
            local = parse_timestamp(row.get("event_ts", ""), date_style)
            if not event_id or kind not in KINDS or not currency or price is None or local is None:
                reject(feed, "MALFORMED_ROW")
                continue

            quantity_text = (row.get("quantity", "") or "").strip()
            if not DIGITS_PATTERN.match(quantity_text):
                reject(feed, "NON_NUMERIC_QUANTITY")
                continue
            quantity = int(quantity_text)

            utc = local - timedelta(minutes=feed_offset)
            capture_date = utc.date().isoformat()

            if kind in TERMINAL_KINDS:
                terminal = drop.resolve(canon(row.get("terminal", "")))
                found = drop.terminals.get(terminal, capture_date)
                if found is None:
                    reject(feed, "UNKNOWN_TERMINAL")
                    continue
                channel_group, terminal_offset = found
            else:
                channel_group, terminal_offset = "contract", 0

            if channel_group == "branch":
                posting = (utc + timedelta(minutes=terminal_offset)).date()
            else:
                posting = utc.date()
            posting_date = posting.isoformat()

            if not (window_start <= posting_date < window_end):
                reject(feed, "OUT_OF_SCOPE")
                continue
            if scope is not None and not (scope_start <= posting_date < scope_end):
                reject(feed, "OUT_OF_SCOPE")
                continue

            if retired_from is not None and retired_from <= posting_date:
                reject(feed, "SUPERSEDED_SOURCE")
                continue

            if event_id in drop.voids:
                reject(feed, "VOIDED")
                continue

            customer_id = canon(row.get("customer_id", ""))
            party = drop.parties.get(customer_id, posting_date)
            if party is None:
                reject(feed, "UNKNOWN_CUSTOMER")
                continue
            segment, customer_postal = party

            sku = drop.resolve(canon(row.get("sku", "")))
            item = drop.items.get(sku, posting_date)
            if item is None:
                reject(feed, "UNKNOWN_SKU")
                continue
            category, active = item
            if active == "N":
                reject(feed, "INACTIVE_SKU")
                continue

            if kind in TERMINAL_KINDS:
                warehouse = drop.resolve(canon(row.get("warehouse", "")))
                postal_code = drop.warehouses.get(warehouse, posting_date)
                if postal_code is None:
                    reject(feed, "UNKNOWN_WAREHOUSE")
                    continue
                region_prefix = postal_code.split("-")[0]
            else:
                region_prefix = customer_postal.split("-")[0]
            region = drop.postal.get(region_prefix, posting_date)
            if region is None:
                reject(feed, "UNKNOWN_WAREHOUSE")
                continue

            if kind in TERMINAL_KINDS:
                version = drop.prices.get(sku, posting_date)
                if version is None:
                    reject(feed, "NO_PRICE_VERSION")
                    continue
            else:
                version = "n/a"

            if exponent is None:
                reject(feed, "NO_FX_RATE")
                continue
            rate = None
            for step in range(drop.carry_forward_days + 1):
                key = (currency, (posting - timedelta(days=step)).isoformat())
                rate = drop.fx_rates.get(key)
                if rate is not None:
                    break
            if rate is None:
                reject(feed, "NO_FX_RATE")
                continue

            fiscal_week = drop.calendar.get((posting_date, region))
            if fiscal_week is None:
                reject(feed, "NO_FISCAL_WEEK")
                continue

            unit_minor = int(price.scaleb(exponent))
            if kind == "sale":
                native = quantity * unit_minor
            elif kind == "refund":
                native = -(quantity * unit_minor)
            elif kind == "fee":
                native = unit_minor
                quantity = 0
            else:
                native = -unit_minor
                quantity = 0

            usd = Decimal(native) * rate * 100
            if exponent:
                usd = usd / (10**exponent)
            amount = int(usd.quantize(Decimal(1), rounding=drop.rounding))

            record = Record()
            record.source_file = feed
            record.position = position
            record.event_id = event_id
            record.kind = kind
            revision = (row.get("revision", "") or "").strip()
            record.revision = int(revision) if DIGITS_PATTERN.match(revision) else 0
            record.ref_event = (row.get("ref_event", "") or "").strip()
            record.posting_date = posting_date
            record.fields = {
                "amount_usd_cents": amount,
                "category": category,
                "channel_group": channel_group,
                "currency": currency,
                "customer_id": customer_id,
                "event_id": event_id,
                "fiscal_week": fiscal_week,
                "kind": kind,
                "native_amount_minor": native,
                "posting_date": posting_date,
                "price_list_version": version,
                "quantity": quantity,
                "region": region,
                "segment": segment,
                "sku": sku,
                "source_file": feed,
            }
            candidates.append(record)

    return candidates, rejected_by_code, rejected_by_source


def resolve_duplicates(drop: Drop, candidates, reject):
    groups: dict[str, list] = {}
    for record in candidates:
        groups.setdefault(record.event_id, []).append(record)

    authority = drop.authority
    duplicate_groups = 0
    survivors = []
    for event_id in groups:
        rows = groups[event_id]
        if len(rows) > 1:
            duplicate_groups += 1
            rows = sorted(
                rows,
                key=lambda r: (
                    authority.get(r.kind, {}).get(r.source_file, 0),
                    -r.revision,
                    r.source_file,
                    r.position,
                ),
            )
            for loser in rows[1:]:
                reject(loser.source_file, "DUPLICATE_LOWER_AUTHORITY")
        survivors.append(rows[0])
    return survivors, duplicate_groups


def resolve_reversals(survivors, canon, reject):
    walk = sorted(survivors, key=lambda r: (r.posting_date, r.event_id, r.source_file))
    live = {record.event_id: record for record in walk}
    reversal_orphans = 0
    reversed_pairs = 0
    for record in walk:
        if live.get(record.event_id) is not record:
            continue
        if record.kind != "credit" or not record.ref_event:
            continue
        reference = canon(record.ref_event)
        target = live.get(reference) if reference != record.event_id else None
        if target is None:
            del live[record.event_id]
            reject(record.source_file, "REVERSAL_ORPHAN")
            reversal_orphans += 1
            continue
        del live[record.event_id]
        del live[target.event_id]
        reject(record.source_file, "REVERSED")
        reject(target.source_file, "REVERSED")
        reversed_pairs += 1
    ledger = [record for record in walk if live.get(record.event_id) is record]
    return ledger, reversal_orphans, reversed_pairs


# ----------------------------------------------------------------- reporting


def sorted_sums(pairs):
    totals = {}
    for key, value in pairs:
        totals[key] = totals.get(key, 0) + value
    return {key: totals[key] for key in sorted(totals)}


def net_units(records):
    total = 0
    for record in records:
        if record["kind"] == "sale":
            total += record["quantity"]
        elif record["kind"] == "refund":
            total -= record["quantity"]
    return total


def group_report(field: str, value: str, records):
    customers = {}
    for record in records:
        customers[record["customer_id"]] = (
            customers.get(record["customer_id"], 0) + record["amount_usd_cents"]
        )
    top = sorted(customers.items(), key=lambda item: (-item[1], item[0]))[:5]
    return {
        field: value,
        "by_category": sorted_sums((r["category"], r["amount_usd_cents"]) for r in records),
        "by_channel_group": sorted_sums(
            (r["channel_group"], r["amount_usd_cents"]) for r in records
        ),
        "by_kind": sorted_sums((r["kind"], r["amount_usd_cents"]) for r in records),
        "customer_count": len(customers),
        "net_units": net_units(records),
        "record_count": len(records),
        "top_customers": [
            {"customer_id": customer, "total_usd_cents": total} for customer, total in top
        ],
        "total_usd_cents": sum(r["amount_usd_cents"] for r in records),
    }


def write_json(path: str, payload) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, sort_keys=True, indent=2)
        handle.write("\n")


def run(data_dir: str, out_dir: str) -> None:
    drop = Drop(data_dir)
    candidates, rejected_by_code, rejected_by_source = build_records(drop)

    def reject(feed, code):
        rejected_by_code[code] = rejected_by_code.get(code, 0) + 1
        rejected_by_source[feed] = rejected_by_source.get(feed, 0) + 1

    survivors, duplicate_groups = resolve_duplicates(drop, candidates, reject)
    ledger, reversal_orphans, reversed_pairs = resolve_reversals(survivors, drop.canon, reject)

    records = []
    for index, record in enumerate(ledger, start=1):
        fields = dict(record.fields)
        fields["ledger_index"] = index
        records.append(fields)

    os.makedirs(out_dir, exist_ok=True)

    with open(os.path.join(out_dir, "normalized.jsonl"), "w", encoding="utf-8", newline="\n") as handle:
        for fields in records:
            handle.write(json.dumps(fields, sort_keys=True, separators=(",", ":")))
            handle.write("\n")

    rejected_count = sum(rejected_by_code.values())
    write_json(
        os.path.join(out_dir, "summary.json"),
        {
            "accepted_count": len(records),
            "by_category": sorted_sums((r["category"], r["amount_usd_cents"]) for r in records),
            "by_channel_group": sorted_sums(
                (r["channel_group"], r["amount_usd_cents"]) for r in records
            ),
            "by_currency": sorted_sums((r["currency"], r["amount_usd_cents"]) for r in records),
            "by_kind": sorted_sums((r["kind"], r["amount_usd_cents"]) for r in records),
            "by_region": sorted_sums((r["region"], r["amount_usd_cents"]) for r in records),
            "by_segment": sorted_sums((r["segment"], r["amount_usd_cents"]) for r in records),
            "net_units": net_units(records),
            "rejected_count": rejected_count,
            "settlement_window": {
                "end_exclusive": drop.settlement_window.get("end_exclusive", ""),
                "start": drop.settlement_window.get("start", ""),
            },
            "total_usd_cents": sum(r["amount_usd_cents"] for r in records),
        },
    )

    accepted_by_source = {feed: 0 for feed in drop.feeds}
    for fields in records:
        accepted_by_source[fields["source_file"]] += 1
    write_json(
        os.path.join(out_dir, "data_quality.json"),
        {
            "accepted_by_source": {feed: accepted_by_source[feed] for feed in drop.feeds},
            "duplicate_groups": duplicate_groups,
            "input_file_count": drop.input_file_count,
            "rejected_by_code": {code: rejected_by_code[code] for code in REJECT_CODES if rejected_by_code.get(code)},
            "rejected_by_source": {feed: rejected_by_source[feed] for feed in drop.feeds},
            "reversal_orphans": reversal_orphans,
            "reversed_pairs": reversed_pairs,
            "scoped_sources": sorted(drop.scoped),
            "superseded_sources": sorted(drop.superseded),
        },
    )

    products: dict[str, dict] = {}
    for fields in records:
        product = products.get(fields["sku"])
        if product is None:
            product = products[fields["sku"]] = {
                "category": fields["category"],
                "net_units": 0,
                "price_list_versions": set(),
                "record_count": 0,
                "sku": fields["sku"],
                "total_usd_cents": 0,
            }
        product["record_count"] += 1
        product["total_usd_cents"] += fields["amount_usd_cents"]
        product["price_list_versions"].add(fields["price_list_version"])
        if fields["kind"] == "sale":
            product["net_units"] += fields["quantity"]
        elif fields["kind"] == "refund":
            product["net_units"] -= fields["quantity"]
    product_list = []
    for sku in sorted(products):
        product = products[sku]
        product["price_list_versions"] = sorted(product["price_list_versions"])
        product_list.append(product)
    write_json(
        os.path.join(out_dir, "product_summary.json"),
        {"product_count": len(product_list), "products": product_list},
    )

    for field, registry in (("region", "postal"), ("segment", "parties")):
        groups = {
            value: []
            for value in drop.registry_values(registry, field)
        }
        for fields in records:
            groups.setdefault(fields[field], []).append(fields)
        for value in sorted(groups):
            write_json(
                os.path.join(out_dir, f"{field}_{value}.json"),
                group_report(field, value, groups[value]),
            )


def main(argv) -> int:
    if len(argv) != 3:
        sys.stderr.write("usage: transform.py <DATA_DIR> <OUT_DIR>\n")
        return 2
    run(argv[1], argv[2])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
