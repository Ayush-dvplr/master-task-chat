#!/usr/bin/env python3
"""Rebuild the kestrel pump failure training data for run KP-24.

Three stages, each reading only the directories it is given:

    build.py phase1 DATA_DIR P1_DIR
    build.py phase2 P1_DIR P2_DIR
    build.py phase3 P1_DIR P2_DIR P3_DIR

The meaning of every value is set by the FPS-4 standard that ships with the
estate (``fps4_rules.md``); the shape of every file is set by the KP-24 output
contract.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import json
import math
import os
import re
import sys
import tomllib
import xml.etree.ElementTree as ET
from fractions import Fraction

import yaml

HALF = Fraction(1, 2)
DAY = 86400
UTC = dt.timezone.utc
EPOCH_DATE = dt.date(1970, 1, 1)


class BuildError(Exception):
    """An input the program cannot work with."""


# --------------------------------------------------------------------------
# numbers, dates and time zones
# --------------------------------------------------------------------------


def scaled_int(value, places: int) -> int:
    """Round value * 10**places to an integer, half to even."""
    scaled = Fraction(value) * (10 ** places)
    whole = scaled.numerator // scaled.denominator
    rest = scaled - whole
    if rest > HALF or (rest == HALF and whole % 2):
        whole += 1
    return whole


def round_places(value, places: int) -> Fraction:
    return Fraction(scaled_int(value, places), 10 ** places)


def fmt_places(value, places: int) -> str:
    """Write value with exactly ``places`` decimals, half to even, no -0."""
    whole = scaled_int(value, places)
    sign = "-" if whole < 0 else ""
    digits = str(abs(whole)).rjust(places + 1, "0")
    if places:
        digits = digits[:-places] + "." + digits[-places:]
    return sign + digits


def fmt_int(value) -> str:
    return str(int(value))


def epoch_of(day: dt.date, seconds: int = 0) -> int:
    return (day - EPOCH_DATE).days * DAY + seconds


def date_of_epoch(epoch: int) -> dt.date:
    return EPOCH_DATE + dt.timedelta(days=epoch // DAY)


def fmt_instant(epoch: int) -> str:
    return dt.datetime.fromtimestamp(epoch, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sunday_on_or_after(day: dt.date) -> dt.date:
    return day + dt.timedelta(days=(6 - day.weekday()) % 7)


def _last_sunday(year: int, month: int) -> dt.date:
    last = dt.date(year, month, 31) if month in (3, 5, 7, 8, 10, 12) else dt.date(year, month, 30)
    return last - dt.timedelta(days=(last.weekday() + 1) % 7)


def _nth_sunday(year: int, month: int, nth: int) -> dt.date:
    first = _sunday_on_or_after(dt.date(year, month, 1))
    return first + dt.timedelta(days=7 * (nth - 1))


TZ_OFFSETS = {"eu": (3600, 7200), "uk": (0, 3600), "us": (-18000, -14400), "ist": (19800,)}


def tz_offset(rule: str, epoch: int) -> int:
    """UTC offset in seconds of a time zone rule at an instant."""
    if rule == "ist":
        return 19800
    year = date_of_epoch(epoch).year
    if rule in ("eu", "uk"):
        start = epoch_of(_last_sunday(year, 3), 3600)
        end = epoch_of(_last_sunday(year, 10), 3600)
        base = 3600 if rule == "eu" else 0
    elif rule == "us":
        start = epoch_of(_nth_sunday(year, 3, 2), 7 * 3600)
        end = epoch_of(_nth_sunday(year, 11, 1), 6 * 3600)
        base = -18000
    else:
        raise BuildError("unknown time zone rule %s" % rule)
    return base + (3600 if start <= epoch < end else 0)


def local_to_utc(rule: str, wall_epoch: int) -> int:
    """Read a wall-clock instant (epoch as if UTC) in a time zone rule."""
    for offset in sorted(TZ_OFFSETS[rule], reverse=True):
        candidate = wall_epoch - offset
        if tz_offset(rule, candidate) == offset:
            return candidate
    return wall_epoch - tz_offset(rule, wall_epoch)


def local_date(rule: str, epoch: int) -> dt.date:
    return date_of_epoch(epoch + tz_offset(rule, epoch))


# --------------------------------------------------------------------------
# the standard
# --------------------------------------------------------------------------

UNIT_TO_CANONICAL = {
    "mm_s": lambda v: v,
    "in_s": lambda v: v * Fraction(254, 10),
    "um_s": lambda v: v / 1000,
    "c": lambda v: v,
    "f": lambda v: (v - 32) / Fraction(18, 10),
    "k": lambda v: v - Fraction(27315, 100),
    "bar": lambda v: v,
    "kpa": lambda v: v / 100,
    "psi": lambda v: v / Fraction("14.5037738"),
    "m3h": lambda v: v,
    "lps": lambda v: v * Fraction(36, 10),
    "gpm": lambda v: v / Fraction("4.402868"),
    "a": lambda v: v,
    "ma": lambda v: v / 1000,
    "ppm": lambda v: v,
    "ppb": lambda v: v / 1000,
    "h": lambda v: v,
    "min": lambda v: v / 60,
}


class Field:
    __slots__ = ("name", "kind", "quantity", "places", "vocab", "optional")

    def __init__(self, name: str, spec: str):
        self.name = name
        self.optional = spec.endswith("?")
        spec = spec[:-1] if self.optional else spec
        parts = spec.split(":")
        self.kind = parts[0]
        self.quantity = None
        self.places = None
        self.vocab = None
        if self.kind == "q":
            self.quantity = parts[1]
            self.places = int(parts[2])
        elif self.kind == "n":
            self.places = int(parts[1])
        elif self.kind == "code":
            self.vocab = parts[1]


def _md_rows(lines: list[str], start: int) -> tuple[list[list[str]], int]:
    """Read a pipe table starting at or after ``start``; return rows and index."""
    idx = start
    while idx < len(lines) and not lines[idx].startswith("|"):
        if lines[idx].startswith("#"):
            break
        idx += 1
    rows = []
    while idx < len(lines) and lines[idx].startswith("|"):
        cells = [c.strip() for c in lines[idx].strip().strip("|").split("|")]
        rows.append(cells)
        idx += 1
    return rows, idx


def _table_after_heading(lines: list[str], heading: str) -> list[list[str]]:
    for i, line in enumerate(lines):
        if line.strip() == heading:
            rows, _ = _md_rows(lines, i + 1)
            if len(rows) >= 2 and set(rows[1][0]) <= set("-: "):
                return rows[2:]
            return rows[1:]
    raise BuildError("heading %s not found in the standard" % heading)


class Standard:
    """Everything the standard states, read from the estate's rules file."""

    def __init__(self, text: str):
        lines = text.split("\n")
        self.freeze = self._instant(lines, r"^1\.2 ")
        self.freeze_date = date_of_epoch(self.freeze)
        window = re.search(
            r"^1\.3 .*?`(\d{4}-\d\d-\d\d)` to `(\d{4}-\d\d-\d\d)`",
            "\n".join(lines),
            re.M,
        )
        if not window:
            raise BuildError("the standard does not state the telemetry window")
        self.window_start = dt.date.fromisoformat(window.group(1))
        self.window_end = dt.date.fromisoformat(window.group(2))
        self.sites = {}
        self.site_by_number = {}
        for row in _table_after_heading(lines, "### Site register"):
            code, number, name, tzrule, region = row[:5]
            self.sites[code] = {"number": number, "name": name, "tz": tzrule, "region": region}
            self.site_by_number[number] = code
        self.models = {row[0]: row[1] for row in _table_after_heading(lines, "### Model catalogue")}
        self.vocabs = {}
        for row in _table_after_heading(lines, "### Code vocabularies"):
            self.vocabs[row[0]] = [v.strip() for v in row[1].split(",")]
        self.unit_extra = {}
        self.canonical_unit = {}
        for row in _table_after_heading(lines, "### Unit register"):
            quantity, unit, _meaning, extra = row[0], row[1], row[2], int(row[3])
            self.unit_extra[(quantity, unit)] = extra
            self.canonical_unit.setdefault(quantity, unit)
        self.roles = {row[0]: row[1] for row in _table_after_heading(lines, "### Source register")}
        cutoff = re.search(r"opened before (\d{4}-\d\d-\d\d)", text)
        if not cutoff:
            raise BuildError("the standard does not state the legacy mirror cutoff")
        self.legacy_cutoff = epoch_of(dt.date.fromisoformat(cutoff.group(1)))
        self.fields = {}
        self.tables = {}
        for row in _table_after_heading(lines, "### Field register"):
            file_name, table, name, spec = row[0], row[1], row[2], row[3]
            self.fields.setdefault((file_name, table), []).append(Field(name, spec))
            self.tables.setdefault(file_name, [])
            if table not in self.tables[file_name]:
                self.tables[file_name].append(table)

    @staticmethod
    def _instant(lines: list[str], pattern: str) -> int:
        for line in lines:
            if re.match(pattern, line):
                found = re.search(r"`(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ)`", line)
                if found:
                    return parse_utc_text(found.group(1))
        raise BuildError("the standard does not state the freeze")

    def tz_of_site(self, site: str) -> str:
        return self.sites[site]["tz"]

    def code_at(self, vocab: str, position: int) -> str:
        values = self.vocabs[vocab]
        if not 1 <= position <= len(values):
            raise BuildError("code %d outside vocabulary %s" % (position, vocab))
        return values[position - 1]


def parse_utc_text(text: str) -> int:
    return epoch_of(dt.date.fromisoformat(text[:10])) + _clock_seconds(text[11:19])


def _clock_seconds(text: str) -> int:
    hour, minute, second = (int(p) for p in text.split(":"))
    return hour * 3600 + minute * 60 + second


# --------------------------------------------------------------------------
# export profile registry
# --------------------------------------------------------------------------

class Profiles:
    """The export profile registry with its working draft."""

    def __init__(self, registry: dict, draft: dict):
        self.registry = registry
        self.draft = draft
        self.dialects = registry.get("dialects") or {}
        self.entries = registry.get("entries") or []
        self.draft_entries = draft.get("entries") or []
        self._chosen = {}
        for entry in self.entries:
            if entry.get("status") != "active":
                continue
            key = (entry["file"], entry["segment"])
            best = self._chosen.get(key)
            if best is None or entry["revision"] > best["revision"]:
                self._chosen[key] = entry
        self._draft_best = {}
        for entry in self.draft_entries:
            key = (entry["file"], entry["segment"])
            best = self._draft_best.get(key)
            if best is None or entry["revision"] > best["revision"]:
                self._draft_best[key] = entry

    def alt_columns(self, file_name: str) -> dict:
        return (self.dialects.get(file_name) or {}).get("alt_columns") or {}

    def tag_system(self, file_name: str) -> str:
        return (self.dialects.get(file_name) or {}).get("tag_system")

    def dims(self, file_name: str, segment: str, dim_errata: dict) -> dict:
        entry = self._chosen.get((file_name, segment))
        if entry is None:
            raise BuildError("no active profile for %s %s" % (file_name, segment))
        dims = {k: str(v) for k, v in (entry.get("dims") or {}).items()}
        if entry.get("inherit") == "draft":
            source = self._draft_best.get((file_name, segment))
            if source is None:
                raise BuildError("no draft profile for %s %s" % (file_name, segment))
            dims = {k: str(v) for k, v in (source.get("dims") or {}).items()}
        rid = "%s#%s#%s" % (file_name, segment, entry["revision"])
        for name, value in (dim_errata.get(rid) or {}).items():
            dims[name] = value
        return dims


def profile_entry_line(entry: dict) -> str:
    dims = entry.get("dims") or {}
    text = ";".join("%s=%s" % (k, dims[k]) for k in sorted(dims))
    return "|".join(
        [
            str(entry["file"]),
            str(entry["segment"]),
            str(entry["revision"]),
            str(entry["status"]),
            str(entry.get("inherit") or ""),
            text,
        ]
    )


# --------------------------------------------------------------------------
# segment decoding: splitting a source into segments of raw records
# --------------------------------------------------------------------------


class RawSegment:
    __slots__ = ("segment", "table", "rows", "control")

    def __init__(self, segment: str, rows: list, control, table=None):
        self.segment = segment
        self.table = table
        self.rows = rows
        self.control = control


_CONTROL_RE = re.compile(r"rows\s*[= ]\s*(\d+)\s*[,; ]\s*sum\s*[= ]\s*(-?\d+(?:\.\d+)?)")


def _control_from_text(text: str):
    found = _CONTROL_RE.search(text)
    if not found:
        raise BuildError("unreadable control line: %r" % text)
    return {"rows": int(found.group(1)), "sum": found.group(2)}


def _rows_from_cells(columns: list[str], cells: list[str], segment: str) -> dict:
    if len(cells) != len(columns):
        raise BuildError("segment %s row has %d of %d cells" % (segment, len(cells), len(columns)))
    return {columns[i].strip().lower(): cells[i] for i in range(len(columns))}


def _norm_keys(row: dict) -> dict:
    return {str(k).strip().lower(): v for k, v in row.items()}


def split_jsonl(text: str) -> list[RawSegment]:
    segments = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        if set(obj) == {"segment"}:
            segments.append(RawSegment(obj["segment"], [], None))
        elif set(obj) == {"control"}:
            segments[-1].control = {"rows": int(obj["control"]["rows"]), "sum": str(obj["control"]["sum"])}
        else:
            segments[-1].rows.append(_norm_keys(obj))
    return segments


def split_json(text: str) -> list[RawSegment]:
    document = json.loads(text)
    segments = []
    for block in document["segments"]:
        control = {"rows": int(block["control"]["rows"]), "sum": str(block["control"]["sum"])}
        segments.append(
            RawSegment(block["segment"], [_norm_keys(r) for r in block["rows"]], control, block.get("table"))
        )
    return segments


def split_yaml(text: str) -> list[RawSegment]:
    document = yaml.safe_load(text)
    segments = []
    for block in document["segments"]:
        control = {"rows": int(block["control"]["rows"]), "sum": str(block["control"]["sum"])}
        segments.append(
            RawSegment(block["segment"], [_norm_keys(r) for r in block["rows"]], control, block.get("table"))
        )
    return segments


def split_toml(text: str) -> list[RawSegment]:
    document = tomllib.loads(text)
    segments = []
    for block in document["segment"]:
        control = {"rows": int(block["control"]["rows"]), "sum": str(block["control"]["sum"])}
        segments.append(
            RawSegment(block["id"], [_norm_keys(r) for r in block["rows"]], control, block.get("table"))
        )
    return segments


_LOG_PAIR_RE = re.compile(r'([A-Za-z_0-9]+)="([^"]*)"')


def split_log(text: str) -> list[RawSegment]:
    segments = []
    for line in text.split("\n"):
        if not line.strip():
            continue
        if line.startswith("# segment "):
            segments.append(RawSegment(line[len("# segment "):].strip(), [], None))
        elif line.startswith("# control"):
            segments[-1].control = _control_from_text(line)
        elif line.startswith("rec "):
            segments[-1].rows.append(_norm_keys(dict(_LOG_PAIR_RE.findall(line))))
    return segments


def split_xml(text: str) -> list[RawSegment]:
    root = ET.fromstring(text)
    segments = []
    for element in root:
        if element.tag != "segment":
            continue
        current = RawSegment(element.get("id"), [], None)
        for child in element:
            if child.tag == "control":
                current.control = {"rows": int(child.get("rows")), "sum": child.get("sum")}
            else:
                current.rows.append(_norm_keys(dict(child.attrib)))
        segments.append(current)
    return segments


def split_fixed_text(text: str) -> list[RawSegment]:
    segments = []
    columns = None
    starts = None
    for line in text.split("\n"):
        if not line.strip():
            continue
        if line.startswith("SEGMENT "):
            segments.append(RawSegment(line[len("SEGMENT "):].strip(), [], None))
            columns = None
        elif line.startswith("CONTROL"):
            segments[-1].control = _control_from_text(line)
        elif columns is None:
            columns = line.split()
            starts = []
            offset = 0
            for name in columns:
                offset = line.index(name, offset)
                starts.append(offset)
                offset += len(name)
        else:
            cells = []
            for i, begin in enumerate(starts):
                end = starts[i + 1] if i + 1 < len(starts) else len(line)
                cells.append(line[begin:end].strip())
            segments[-1].rows.append(_rows_from_cells(columns, cells, segments[-1].segment))
    return segments


def split_tsv(text: str) -> list[RawSegment]:
    segments = []
    columns = None
    for line in text.split("\n"):
        if not line.strip("\n"):
            continue
        if line.startswith("#segment"):
            segments.append(RawSegment(line.split(None, 1)[1].strip() if " " in line else line[8:].strip(), [], None))
            columns = None
        elif line.startswith("#control"):
            segments[-1].control = _control_from_text(line)
        elif columns is None:
            columns = line.split("\t")
        else:
            segments[-1].rows.append(_rows_from_cells(columns, line.split("\t"), segments[-1].segment))
    return segments


def split_csv(text: str) -> list[RawSegment]:
    segments = []
    columns = None
    pending = []

    def flush():
        if not pending:
            return
        reader = csv.reader(io.StringIO("\n".join(pending)))
        rows = list(reader)
        for cells in rows[1:]:
            segments[-1].rows.append(_rows_from_cells(rows[0], cells, segments[-1].segment))
        pending.clear()

    for line in text.split("\n"):
        if not line.strip():
            continue
        if line.startswith("#segment"):
            flush()
            segments.append(RawSegment(line[len("#segment"):].strip(), [], None))
            columns = None
        elif line.startswith("#control"):
            flush()
            segments[-1].control = _control_from_text(line)
        else:
            pending.append(line)
    flush()
    return segments


def split_ini(text: str) -> list[RawSegment]:
    segments = []
    columns = None
    for line in text.split("\n"):
        line = line.rstrip("\n")
        if not line.strip() or line.startswith(";"):
            continue
        if line.startswith("[segment "):
            segments.append(RawSegment(line.strip()[len("[segment "):-1].strip(), [], None))
            columns = None
        elif line.startswith("columns"):
            columns = line.split("=", 1)[1].strip().split(";")
        elif line.startswith("control"):
            segments[-1].control = _control_from_text(line.split("=", 1)[1])
        else:
            cells = line.split("=", 1)[1].strip().split(";")
            segments[-1].rows.append(_rows_from_cells(columns, cells, segments[-1].segment))
    return segments


def split_md(text: str) -> list[RawSegment]:
    lines = text.split("\n")
    segments = []
    index = 0
    while index < len(lines):
        line = lines[index]
        found = re.match(r"^#{2,4} Segment (\S+)\s*$", line)
        if found:
            current = RawSegment(found.group(1), [], None)
            segments.append(current)
            rows, index = _md_rows(lines, index + 1)
            if len(rows) >= 2:
                columns = rows[0]
                for cells in rows[2:]:
                    current.rows.append(_rows_from_cells(columns, cells, current.segment))
            continue
        if segments and re.match(r"^Control:", line.strip()):
            segments[-1].control = _control_from_text(line)
        index += 1
    return segments


_TAG_RE = re.compile(r"<(t[dh])[^>]*>(.*?)</\1>", re.S)


def split_html(text: str) -> list[RawSegment]:
    segments = []
    columns = None
    for line in text.split("\n"):
        stripped = line.strip()
        found = re.match(r'<table data-segment="([^"]+)"', stripped)
        if found:
            segments.append(RawSegment(found.group(1), [], None))
            columns = None
            continue
        if stripped.startswith('<p class="control">'):
            segments[-1].control = _control_from_text(stripped)
            continue
        if stripped.startswith("<tr>"):
            cells = [m.group(2) for m in _TAG_RE.finditer(stripped)]
            if columns is None:
                columns = cells
            else:
                segments[-1].rows.append(_rows_from_cells(columns, cells, segments[-1].segment))
    return segments


def split_ics(text: str) -> list[RawSegment]:
    segments = []
    current = None
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("X-SEGMENT:"):
            segments.append(RawSegment(line[len("X-SEGMENT:"):].strip(), [], None))
        elif line.startswith("X-CONTROL:"):
            segments[-1].control = _control_from_text(line[len("X-CONTROL:"):])
        elif line == "BEGIN:VEVENT":
            current = {}
        elif line == "END:VEVENT":
            segments[-1].rows.append(_norm_keys(current))
            current = None
        elif current is not None and ":" in line:
            name, value = line.split(":", 1)
            name = name[2:] if name.startswith("X-") else name
            current[name.lower()] = value
    return segments


def split_mbox(text: str) -> list[RawSegment]:
    segments = []
    columns = None
    for line in text.split("\n"):
        stripped = line.strip()
        found = re.search(r"segment (\S+)\s*$", stripped)
        if stripped.startswith("Subject:") and found:
            segments.append(RawSegment(found.group(1), [], None))
            columns = None
        elif stripped.startswith("Columns:"):
            columns = [c.strip() for c in stripped[len("Columns:"):].split("|")]
        elif stripped.startswith("Control:"):
            segments[-1].control = _control_from_text(stripped)
        elif columns is not None and "|" in stripped:
            cells = [c.strip() for c in stripped.split("|")]
            segments[-1].rows.append(_rows_from_cells(columns, cells, segments[-1].segment))
    return segments


_SQL_VALUES_RE = re.compile(r"VALUES\s*\((.*)\);\s*$")


def _split_sql_values(text: str) -> list[str]:
    cells = []
    index = 0
    while index < len(text):
        char = text[index]
        if char in " ,":
            index += 1
            continue
        if char == "'":
            end = index + 1
            buffer = []
            while end < len(text):
                if text[end] == "'" and end + 1 < len(text) and text[end + 1] == "'":
                    buffer.append("'")
                    end += 2
                    continue
                if text[end] == "'":
                    break
                buffer.append(text[end])
                end += 1
            cells.append("".join(buffer))
            index = end + 1
        else:
            end = text.find(",", index)
            end = len(text) if end < 0 else end
            token = text[index:end].strip()
            # an unquoted NULL is this format's own empty value
            cells.append(None if token.upper() == "NULL" else token)
            index = end
    return cells


def split_sql(text: str) -> list[RawSegment]:
    segments = []
    columns = None
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("-- segment "):
            segments.append(RawSegment(stripped[len("-- segment "):].strip(), [], None))
            columns = None
        elif stripped.startswith("-- columns:"):
            columns = [c.strip() for c in stripped[len("-- columns:"):].split(",")]
        elif stripped.startswith("-- control"):
            segments[-1].control = _control_from_text(stripped)
        elif stripped.startswith("INSERT"):
            found = _SQL_VALUES_RE.search(stripped)
            if not found:
                raise BuildError("unreadable sql row: %r" % stripped)
            segments[-1].rows.append(
                _rows_from_cells(columns, _split_sql_values(found.group(1)), segments[-1].segment)
            )
    return segments


SPLITTERS = {
    ".jsonl": split_jsonl,
    ".json": split_json,
    ".yaml": split_yaml,
    ".toml": split_toml,
    ".log": split_log,
    ".xml": split_xml,
    ".txt": split_fixed_text,
    ".tsv": split_tsv,
    ".csv": split_csv,
    ".ini": split_ini,
    ".md": split_md,
    ".html": split_html,
    ".ics": split_ics,
    ".mbox": split_mbox,
    ".sql": split_sql,
}


def split_source(file_name: str, text: str) -> list[RawSegment]:
    """Split one source file into its export segments of raw records."""
    extension = os.path.splitext(file_name)[1]
    splitter = SPLITTERS.get(extension)
    if splitter is None:
        raise BuildError("no reader for %s" % file_name)
    segments = splitter(text)
    for segment in segments:
        if segment.control is None:
            raise BuildError("segment %s of %s has no control" % (segment.segment, file_name))
    return segments


# --------------------------------------------------------------------------
# segment decoding: raw text to values
# --------------------------------------------------------------------------

NULL_TOKENS = {"empty": "", "na": "NA", "dash": "-", "nullword": "null", "n999": "-999"}
GROUPING = {"plain": "", "en": ",", "de": ".", "fr": " \u00a0\u202f", "ch": "'"}
DECIMAL_COMMA = ("de", "fr")
_TS_RE = re.compile(r"^(\d{4}-\d\d-\d\d)[T ](\d\d:\d\d:\d\d)(Z|[+-]\d\d:\d\d)?$")


def parse_number(text: str, locale: str) -> Fraction:
    locale = locale or "plain"
    for char in GROUPING[locale]:
        text = text.replace(char, "")
    if locale in DECIMAL_COMMA:
        text = text.replace(",", ".")
    try:
        return Fraction(text)
    except (ValueError, ZeroDivisionError) as error:
        raise BuildError("unreadable number %r (%s)" % (text, locale)) from error


def parse_date_text(text: str, date_form: str) -> dt.date:
    form = date_form or "iso"
    try:
        if form == "iso":
            return dt.date.fromisoformat(text)
        if form == "compact":
            return dt.date(int(text[0:4]), int(text[4:6]), int(text[6:8]))
        first, second, third = text.split("/")
        if form == "dmy":
            return dt.date(int(third), int(second), int(first))
        if form == "mdy":
            return dt.date(int(third), int(first), int(second))
    except ValueError as error:
        raise BuildError("unreadable date %r (%s)" % (text, form)) from error
    raise BuildError("unknown date form %s" % form)


def scale_power(field: Field, unit: str, standard: Standard) -> int:
    extra = 0
    if field.quantity is not None:
        extra = standard.unit_extra[(field.quantity, unit)]
    power = max(0, field.places + extra)
    if unit == "k":
        power = max(power, 2)
    return power


class Decoder:
    """Decodes raw records of one estate into values."""

    def __init__(self, standard: Standard, profiles: Profiles):
        self.standard = standard
        self.profiles = profiles
        self.serial_to_asset = {}
        self.tag_index = {}
        self.site_events = {}

    # -- asset and site references ----------------------------------------

    def site_in_force(self, asset: str, epoch: int) -> str:
        events = self.site_events.get(asset)
        if not events:
            raise BuildError("no site known for asset %s" % asset)
        site = events[0][1]
        for at, value in events:
            if at <= epoch:
                site = value
            else:
                break
        return site

    def tz_of_asset(self, asset: str, epoch: int) -> str:
        return self.standard.tz_of_site(self.site_in_force(asset, epoch))

    def asset_of_tag(self, system: str, tag: str, epoch: int) -> str:
        for valid_from, valid_to, asset in self.tag_index.get((system, tag), ()):
            if valid_from <= epoch and (valid_to is None or valid_to > epoch):
                return asset
        raise BuildError("no asset for tag %s/%s at %d" % (system, tag, epoch))

    def resolve_asset(self, text: str, dims: dict, file_name: str, reference):
        form = dims.get("asset_ref") or "id"
        if form == "id":
            return text
        if form == "serial":
            asset = self.serial_to_asset.get(text)
            if asset is None:
                raise BuildError("no asset with serial %s" % text)
            return asset
        if reference is None:
            raise BuildError("no reference instant for a tag reference in %s" % file_name)
        return self.asset_of_tag(self.profiles.tag_system(file_name), text, reference)

    def resolve_site(self, text: str, dims: dict) -> str:
        if (dims.get("site_ref") or "code") == "code":
            if text not in self.standard.sites:
                raise BuildError("unknown site code %s" % text)
            return text
        site = self.standard.site_by_number.get(text)
        if site is None:
            raise BuildError("unknown site number %s" % text)
        return site

    # -- single values -----------------------------------------------------

    @staticmethod
    def is_null(field: Field, raw, dims: dict) -> bool:
        if not field.optional:
            if raw is None:
                raise BuildError("field %s holds no value" % field.name)
            return False
        if raw is None:
            return True
        return raw == NULL_TOKENS[dims.get("nulls") or "empty"]

    def decode_scalar(self, field: Field, raw: str, dims: dict, file_name: str, reference, tz_rule):
        kind = field.kind
        if kind in ("rid", "text"):
            return raw
        if kind == "int":
            value = parse_number(raw, dims.get("locale"))
            if value.denominator != 1:
                raise BuildError("integer field %s holds %r" % (field.name, raw))
            return int(value)
        if kind == "acode":
            return decode_alarm_code(raw, dims.get("codeform"))
        if kind == "bool":
            return decode_flag(raw, dims.get("bool"))
        if kind == "code":
            return self.decode_code(field, raw, dims)
        if kind == "date":
            return parse_date_text(raw, dims.get("date_form"))
        if kind == "ts":
            return self.decode_instant(raw, dims, tz_rule)
        if kind == "asset":
            return self.resolve_asset(raw, dims, file_name, reference)
        if kind == "site":
            return self.resolve_site(raw, dims)
        if kind in ("q", "n"):
            return self.decode_quantity(field, raw, dims)
        raise BuildError("unknown field kind %s" % kind)

    def decode_code(self, field: Field, raw: str, dims: dict) -> str:
        form = dims.get("status") or "word"
        values = self.standard.vocabs[field.vocab]
        if form == "num":
            return self.standard.code_at(field.vocab, int(raw))
        word = raw.lower() if form == "caps" else raw
        if word not in values:
            raise BuildError("value %r outside vocabulary %s" % (raw, field.vocab))
        return word

    def decode_quantity(self, field: Field, raw: str, dims: dict) -> Fraction:
        unit = self.standard.canonical_unit[field.quantity] if field.quantity else None
        if field.quantity is not None:
            unit = dims.get("unit_%s" % field.quantity) or unit
        value = parse_number(raw, dims.get("locale"))
        if (dims.get("numform") or "decimal") == "scaled":
            if value.denominator != 1:
                raise BuildError("scaled field %s holds %r" % (field.name, raw))
            value = value / (10 ** scale_power(field, unit, self.standard))
        if unit is not None:
            value = UNIT_TO_CANONICAL[unit](value)
        return round_places(value, field.places)

    def decode_instant(self, raw: str, dims: dict, tz_rule) -> int:
        clock = dims.get("clock") or "utc"
        if clock == "epoch":
            return int(raw)
        if clock == "epoch_ms":
            return int(raw) // 1000
        if clock in ("utc", "offset"):
            found = _TS_RE.match(raw)
            if not found:
                raise BuildError("unreadable instant %r (%s)" % (raw, clock))
            epoch = epoch_of(dt.date.fromisoformat(found.group(1))) + _clock_seconds(found.group(2))
            zone = found.group(3)
            if zone and zone != "Z":
                sign = 1 if zone[0] == "+" else -1
                epoch -= sign * _clock_seconds(zone[1:] + ":00")
            return epoch
        if clock == "local":
            form = dims.get("date_form") or "iso"
            if form == "compact":
                day = parse_date_text(raw[:8], "compact")
                clock_text = "%s:%s:%s" % (raw[9:11], raw[11:13], raw[13:15])
            else:
                date_text, clock_text = raw.split(" ")
                day = parse_date_text(date_text, form)
            wall = epoch_of(day) + _clock_seconds(clock_text)
            if tz_rule is None:
                raise BuildError("no time zone for a local instant %r" % raw)
            return local_to_utc(tz_rule(day), wall)
        raise BuildError("unknown clock %s" % clock)

    # -- records -----------------------------------------------------------

    def decode_segment(self, file_name: str, table: str, segment: RawSegment, dims: dict) -> list[dict]:
        fields = self.standard.fields[(file_name, table)]
        alt = self.profiles.alt_columns(file_name)
        rename = {str(v).lower(): k for k, v in alt.items()}
        rid_field = fields[0].name
        rename["uid"] = rid_field
        records = []
        for raw in segment.rows:
            row = {}
            for key, value in raw.items():
                row[rename.get(key, key)] = value
            records.append(self.decode_record(file_name, fields, row, dims))
        return records

    def decode_record(self, file_name: str, fields: list[Field], row: dict, dims: dict) -> dict:
        record = {}
        pending = []
        for field in fields:
            if field.name not in row:
                raise BuildError("field %s missing from a record of %s" % (field.name, file_name))
            raw = row[field.name]
            if isinstance(raw, bool):
                raw = "true" if raw else "false"
            elif raw is not None and not isinstance(raw, str):
                raw = str(raw)
            if self.is_null(field, raw, dims):
                record[field.name] = None
            else:
                pending.append((field, raw))
        # sites first, then the asset when it is not a tag, then instants
        order = {"site": 0, "asset": 1, "ts": 2}
        asset_form = dims.get("asset_ref") or "id"
        if asset_form == "tag":
            order["asset"] = 3
        pending.sort(key=lambda item: order.get(item[0].kind, 4))

        def tz_rule(day: dt.date) -> str:
            for field in fields:
                if field.kind == "site" and record.get(field.name) is not None:
                    return self.standard.tz_of_site(record[field.name])
            for field in fields:
                if field.kind == "asset" and record.get(field.name) is not None:
                    return self.tz_of_asset(record[field.name], epoch_of(day, 12 * 3600))
            raise BuildError("no site for a local instant in %s" % file_name)

        for field, raw in pending:
            reference = None
            if field.kind == "asset":
                reference = self.first_instant(fields, record)
            record[field.name] = self.decode_scalar(field, raw, dims, file_name, reference, tz_rule)
        return record

    @staticmethod
    def first_instant(fields: list[Field], record: dict):
        for field in fields:
            if field.kind == "ts" and record.get(field.name) is not None:
                return record[field.name]
        return None


def decode_alarm_code(raw: str, codeform: str) -> int:
    form = codeform or "dec"
    if form == "dec":
        return int(raw)
    if form == "pref":
        return int(raw.split("-", 1)[1])
    if form == "hex":
        return int(raw, 16)
    raise BuildError("unknown code form %s" % form)


def decode_flag(raw: str, form: str) -> bool:
    form = form or "tf"
    if form == "tf":
        if raw in ("true", "false"):
            return raw == "true"
    elif form == "yn":
        if raw in ("Y", "N"):
            return raw == "Y"
    elif form == "10":
        if raw in ("1", "0"):
            return raw == "1"
    else:
        raise BuildError("unknown flag form %s" % form)
    raise BuildError("unreadable flag %r (%s)" % (raw, form))


def canonical_text(field: Field, value) -> str:
    """The canonical text of a decoded value (FPS-4 2.4)."""
    if value is None:
        return ""
    if field.kind == "ts":
        return fmt_instant(value)
    if field.kind == "date":
        return value.isoformat()
    if field.kind in ("q", "n"):
        return fmt_places(value, field.places)
    if field.kind == "int":
        return fmt_int(value)
    if field.kind == "bool":
        return "true" if value else "false"
    if field.kind == "acode":
        return str(value)
    return str(value)


def parse_canonical(field: Field, text: str, standard: Standard):
    """Read canonical text back into a value (errata values)."""
    if text is None or text == "":
        return None
    if field.kind == "ts":
        return parse_utc_text(text)
    if field.kind == "date":
        return dt.date.fromisoformat(text)
    if field.kind in ("q", "n"):
        return round_places(Fraction(text), field.places)
    if field.kind == "int":
        return int(text)
    if field.kind == "bool":
        return text == "true"
    if field.kind == "acode":
        return int(text)
    if field.kind == "code":
        if text not in standard.vocabs[field.vocab]:
            raise BuildError("errata value %r outside vocabulary %s" % (text, field.vocab))
        return text
    if field.kind == "site" and text not in standard.sites:
        raise BuildError("errata value %r is not a site" % text)
    return text


def control_value(field: Field, value):
    """The contribution of one value to a segment control sum (FPS-4 2.1)."""
    if value is None:
        return None
    if field.kind == "ts":
        return Fraction(value)
    if field.kind == "date":
        return Fraction((value - EPOCH_DATE).days)
    if field.kind in ("q", "n", "int"):
        return Fraction(value)
    return None


def control_field(fields: list[Field]) -> Field:
    for kind in ("q", "n", "int", "ts", "date"):
        for field in fields[1:]:
            if field.kind == kind:
                return field
    raise BuildError("no control field")


# --------------------------------------------------------------------------
# the estate: every source decoded, attested and corrected
# --------------------------------------------------------------------------

RULES_FILE = "fps4_rules.md"


class Estate:
    """All sources of one input directory, decoded and corrected by errata."""

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        try:
            names = sorted(os.listdir(data_dir))
        except OSError as error:
            raise BuildError("cannot read the input directory: %s" % error) from error
        self.files = [n for n in names if os.path.isfile(os.path.join(data_dir, n))]
        if RULES_FILE not in self.files:
            raise BuildError("the input directory has no %s" % RULES_FILE)
        self.standard = Standard(self._read(RULES_FILE))
        self.table_files = {}
        for name in self.files:
            for table in self.standard.tables.get(name, ()):
                self.table_files.setdefault(table, []).append(name)
        # the profile registers are the only sources the field register leaves out
        self.registry_file = self._register_file("in_scope")
        self.draft_file = self._register_file("reference_copy")
        self.profiles = Profiles(
            yaml.safe_load(self._read(self.registry_file)), yaml.safe_load(self._read(self.draft_file))
        )
        self.decoder = Decoder(self.standard, self.profiles)
        self.records = {}
        self.digests = {}
        self.record_counts = {}
        self.control_mismatches = []
        self._raw = {}
        self._load()

    def _register_file(self, role: str) -> str:
        found = [
            name
            for name in self.files
            if name not in self.standard.tables and self.standard.roles.get(name) == role
        ]
        if len(found) != 1:
            raise BuildError("the estate does not hold exactly one %s profile register" % role)
        return found[0]

    # -- sources by the table they carry -----------------------------------

    def files_of(self, table: str, role: str = None) -> list[str]:
        return [
            name
            for name in self.table_files.get(table, [])
            if role is None or self.standard.roles.get(name) == role
        ]

    def file_of(self, table: str, role: str = None) -> str:
        found = self.files_of(table, role)
        if len(found) != 1:
            raise BuildError("the estate does not hold exactly one source of %s" % table)
        return found[0]

    def rows(self, table: str, role: str = None) -> list[dict]:
        """Every record of a table, its files in name order."""
        found = []
        for name in self.files_of(table, role):
            found.extend(record for record in self.records[name] if record["_table"] == table)
        return found

    def _read(self, name: str) -> str:
        with open(os.path.join(self.data_dir, name), encoding="utf-8") as handle:
            return handle.read()

    # -- loading -----------------------------------------------------------

    def _load(self):
        sources = [n for n in self.files if n not in (self.registry_file, self.draft_file)]
        for name in sources:
            self._raw[name] = split_source(name, self._read(name))
        for name, document in ((self.registry_file, self.profiles.registry), (self.draft_file, self.profiles.draft)):
            entries = document.get("entries") or []
            self.record_counts[name] = len(entries)
            self.digests[name] = digest_lines(profile_entry_line(e) for e in entries)
        self.errata_file = self.file_of("erratum")
        self.dim_errata = {}
        self._decode_file(self.errata_file)
        self.errata = self._resolve_errata()
        self.dim_errata = self._resolve_dim_errata()
        # the asset log carries the serials, the tag history the tags that
        # every other source may name its assets by
        asset_log, tag_history = self.file_of("asset_event"), self.file_of("tag")
        ordered = [asset_log, tag_history]
        for name, index_them in ((asset_log, self._index_assets), (tag_history, self._index_tags)):
            self._decode_file(name)
            self._apply_errata(name)
            index_them()
        for name in sources:
            if name in ordered or name == self.errata_file:
                continue
            self._decode_file(name)
            self._apply_errata(name)

    def _decode_file(self, name: str):
        tables = self.standard.tables.get(name)
        if not tables:
            raise BuildError("the field register does not describe %s" % name)
        records = []
        lines = []
        for segment in self._raw[name]:
            table = segment.table or tables[0]
            if table not in tables:
                raise BuildError("segment %s of %s names table %s" % (segment.segment, name, table))
            dims = self.profiles.dims(name, segment.segment, self.dim_errata)
            decoded = self.decoder.decode_segment(name, table, segment, dims)
            fields = self.standard.fields[(name, table)]
            self._check_control(name, segment, fields, decoded)
            for record in decoded:
                record["_table"] = table
                lines.append("|".join(canonical_text(f, record[f.name]) for f in fields))
            records.extend(decoded)
        self.records[name] = records
        self.record_counts[name] = len(records)
        self.digests[name] = digest_lines(lines)

    def _check_control(self, name: str, segment: RawSegment, fields: list[Field], decoded: list[dict]):
        """Compare a decoded segment with the control it publishes (FPS-4 2.1).

        Mismatches are collected rather than raised: the control describes the
        shipped values and is a check on this program, not a rule on the data.
        """
        if len(decoded) != segment.control["rows"]:
            self.control_mismatches.append("%s %s rows" % (name, segment.segment))
        field = control_field(fields)
        total = Fraction(0)
        for record in decoded:
            value = control_value(field, record[field.name])
            if value is not None:
                total += value
        if total != Fraction(segment.control["sum"]):
            self.control_mismatches.append(
                "%s %s sum %s want %s" % (name, segment.segment, total, segment.control["sum"])
            )

    # -- errata ------------------------------------------------------------

    def _errata_rows(self):
        rows = []
        for record in self.rows("erratum"):
            if record["status"] != "approved" or record["approved_at"] > self.standard.freeze:
                continue
            rows.append(record)
        return rows

    def _resolve_errata(self) -> dict:
        chosen = {}
        for index, record in enumerate(self._errata_rows()):
            key = (record["target_file"], record["target_rid"], record["field"])
            rank = (record["approved_at"], index)
            if key not in chosen or rank > chosen[key][0]:
                chosen[key] = (rank, record["value"])
        result = {}
        for (file_name, rid, field), (_rank, value) in chosen.items():
            result.setdefault(file_name, {}).setdefault(rid, {})[field] = value
        return result

    def _resolve_dim_errata(self) -> dict:
        return {rid: dict(fields) for rid, fields in (self.errata.get(self.registry_file) or {}).items()}

    def _apply_errata(self, name: str):
        corrections = self.errata.get(name)
        if not corrections:
            return
        by_field = {}
        for table in self.standard.tables[name]:
            for field in self.standard.fields[(name, table)]:
                by_field[(table, field.name)] = field
        rid_name = self.standard.fields[(name, self.standard.tables[name][0])][0].name
        for record in self.records[name]:
            fixes = corrections.get(record[rid_name])
            if not fixes:
                continue
            for field_name, text in fixes.items():
                field = by_field.get((record["_table"], field_name))
                if field is None:
                    continue
                record[field_name] = parse_canonical(field, text, self.standard)

    # -- reference indexes -------------------------------------------------

    def _index_assets(self):
        events = {}
        for record in self.rows("asset_event"):
            if record["kind"] in ("baseline", "commission"):
                if record["serial"]:
                    self.decoder.serial_to_asset.setdefault(record["serial"], record["asset"])
            if record["site"] is not None and record["kind"] in ("baseline", "commission", "relocate"):
                events.setdefault(record["asset"], []).append((record["at"], record["site"]))
        for asset, rows in events.items():
            rows.sort(key=lambda row: row[0])
            self.decoder.site_events[asset] = rows

    def _index_tags(self):
        index = {}
        for record in self.rows("tag"):
            index.setdefault((record["system"], record["tag"]), []).append(
                (record["valid_from"], record["valid_to"], record["asset"])
            )
        for rows in index.values():
            rows.sort(key=lambda row: row[0])
        self.decoder.tag_index = index

def digest_lines(lines) -> str:
    digest = hashlib.sha256()
    for line in lines:
        digest.update(line.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


# --------------------------------------------------------------------------
# phase 1: clean tables out of the sources
# --------------------------------------------------------------------------

CHANNEL_PLACES = {"vib": 3, "temp": 2, "prs": 3, "flw": 2, "cur": 2}
CM_CHANNELS = (("vib", "vib"), ("temp", "tmp"))
HIST_CHANNELS = (("prs", "prs"), ("flw", "flw"), ("cur", "cur"))
SERVICE_KINDS = ("lubrication", "seal", "bearing", "impeller", "overhaul")
MAINTENANCE_KINDS = ("overhaul", "impeller")
P1_FILES = (
    "asset_registry.csv",
    "sensor_daily.csv",
    "failure_events.csv",
    "maintenance_log.csv",
    "site_days.csv",
    "run_parameters.json",
)


def days_between(first: dt.date, last: dt.date):
    day = first
    while day <= last:
        yield day
        day += dt.timedelta(days=1)


class AssetTimeline:
    """The replayed state of one asset (FPS-4 3.1)."""

    __slots__ = ("asset", "model", "serial", "commissioned_on", "snapshots", "first_site")

    def __init__(self, asset: str):
        self.asset = asset
        self.model = None
        self.serial = None
        self.commissioned_on = None
        self.snapshots = []
        self.first_site = None

    def at(self, epoch: int) -> dict:
        state = {
            "site": self.first_site,
            "setpoint": None,
            "criticality": None,
            "active": False,
            "decommissioned_at": None,
        }
        for at, snapshot in self.snapshots:
            if at > epoch:
                break
            state = snapshot
        return state


class Phase1:
    """Builds the six phase 1 tables of one estate."""

    def __init__(self, estate: Estate):
        self.estate = estate
        self.standard = estate.standard
        self.freeze = estate.standard.freeze
        self.parameters = self._parameters()
        self.holdout = sorted(set((self.parameters.get("holdout_assets") or "").split()))
        self.timelines = self._replay_assets()
        self.rated_flows = self._rated_flows()
        self.sensors = self._sensor_timelines()
        self.certificates = self._certificates()
        self.fault_windows = self._fault_windows()
        self.envelopes = self._envelopes()
        self.embargoes = self._embargoes()
        self.outages = self._windows("outage", lambda r: r["status"] == "logged")
        self.standbys = self._standby_windows()
        self.holds = self._review_holds()
        self.alarm_days = self._alarm_days()
        self.site_days = self._site_days()
        self.readings = self._daily_readings()
        self.asset_days = self._asset_days()
        self.services = self._services()
        self.oil_samples = self._oil_samples()
        self.failures = self._failure_events()

    # -- parameters and assets --------------------------------------------

    def _parameters(self) -> dict:
        chosen = {}
        for index, row in enumerate(self.estate.rows("param")):
            if row["status"] != "active" or row["set_at"] > self.freeze:
                continue
            rank = (row["rev"], index)
            if row["name"] not in chosen or rank > chosen[row["name"]][0]:
                chosen[row["name"]] = (rank, row["value"])
        return {name: value for name, (_rank, value) in chosen.items()}

    def number(self, name: str) -> Fraction:
        return Fraction(self.parameters[name])

    def integer(self, name: str) -> int:
        return int(self.parameters[name])

    def day_parameter(self, name: str) -> dt.date:
        return dt.date.fromisoformat(self.parameters[name])

    def _replay_assets(self) -> dict:
        rows = {}
        for record in self.estate.rows("asset_event"):
            if record["at"] > self.freeze:
                continue
            rows.setdefault(record["asset"], []).append(record)
        snapshots = {}
        for asset in sorted(rows):
            ordered = sorted(rows[asset], key=lambda r: r["at"])
            if not any(r["kind"] in ("baseline", "commission") for r in ordered):
                continue
            timeline = AssetTimeline(asset)
            # before its first row an asset counts as being at the site of that row
            timeline.first_site = next((r["site"] for r in ordered if r["site"] is not None), None)
            state = {
                "site": timeline.first_site,
                "setpoint": None,
                "criticality": None,
                "active": False,
                "decommissioned_at": None,
            }
            commissioned = None
            for record in ordered:
                state = dict(state)
                kind = record["kind"]
                if kind in ("baseline", "commission"):
                    state["site"] = record["site"]
                    state["setpoint"] = record["setpoint"]
                    state["criticality"] = record["criticality"]
                    state["active"] = True
                    state["decommissioned_at"] = None
                    timeline.model = record["model"]
                    timeline.serial = record["serial"]
                    if kind == "commission":
                        commissioned = date_of_epoch(record["at"])
                elif kind == "relocate":
                    state["site"] = record["site"]
                elif kind == "decommission":
                    state["active"] = False
                    state["decommissioned_at"] = record["at"]
                elif kind == "reinstate":
                    state["active"] = True
                    state["decommissioned_at"] = None
                elif kind == "setpoint":
                    state["setpoint"] = record["setpoint"]
                elif kind == "criticality":
                    state["criticality"] = record["criticality"]
                timeline.snapshots.append((record["at"], state))
            timeline.commissioned_on = commissioned or self._snapshot_date(asset)
            snapshots[asset] = timeline
        return snapshots

    def _snapshot_date(self, asset: str):
        best = None
        for record in self.estate.rows("asset_snap", "reference_copy"):
            if record["asset"] != asset or record["as_of"] > self.standard.freeze_date:
                continue
            if best is None or record["as_of"] >= best["as_of"]:
                best = record
        return best["commissioned"] if best else None

    def site_of(self, asset: str, epoch: int) -> str:
        return self.timelines[asset].at(epoch)["site"]

    def local_day_of(self, asset: str, epoch: int) -> dt.date:
        site = self.site_of(asset, epoch)
        return local_date(self.standard.tz_of_site(site), epoch)

    def _rated_flows(self) -> dict:
        points = {}
        for index, record in enumerate(self.estate.rows("perf_point")):
            if not record["bep"] or not record["accepted"]:
                continue
            points.setdefault(record["asset"], []).append((record["tested_at"], index, record["flow"]))
        for rows in points.values():
            rows.sort(key=lambda row: (row[0], row[1]))
        return points

    def rated_flow_at(self, asset: str, epoch: int):
        flow = None
        for tested_at, _index, value in self.rated_flows.get(asset, ()):
            if tested_at <= epoch:
                flow = value
            else:
                break
        return flow

    # -- calibration -------------------------------------------------------

    def _sensor_timelines(self) -> dict:
        moves = {}
        for index, record in enumerate(self.estate.rows("sensor_move")):
            moves.setdefault((record["asset"], record["channel"]), []).append((record["at"], index, record))
        timelines = {}
        for key, rows in moves.items():
            rows.sort(key=lambda row: (row[0], row[1]))
            serial = None
            states = []
            for at, _index, record in rows:
                if record["action"] == "install":
                    serial = record["serial"]
                elif record["action"] == "remove" and serial == record["serial"]:
                    serial = None
                states.append((at, serial))
            timelines[key] = states
        return timelines

    def sensor_at(self, asset: str, channel: str, epoch: int):
        serial = None
        for at, value in self.sensors.get((asset, channel), ()):
            if at <= epoch:
                serial = value
            else:
                break
        return serial

    def _certificates(self) -> dict:
        reviews = {}
        for index, record in enumerate(self.estate.rows("cert_review")):
            if record["at"] > self.freeze:
                continue
            key = record["cert_no"]
            rank = (record["at"], index)
            if key not in reviews or rank > reviews[key][0]:
                reviews[key] = (rank, record["outcome"])
        pending = {}
        for record in self.estate.rows("cert_pending", "reference_copy"):
            pending.setdefault(record["cert_no"], record)
        certificates = {}
        for index, record in enumerate(self.estate.rows("cert")):
            if record["recorded_at"] > self.freeze:
                continue
            if reviews.get(record["cert_no"], (None, None))[1] == "revoke":
                continue
            gain, offset, effective = record["gain"], record["offset"], record["effective_from"]
            if record["status"] == "see_pending":
                row = pending.get(record["cert_no"])
                if row is None or row["approved_at"] is None or row["approved_at"] > self.freeze:
                    continue
                gain, offset, effective = row["gain"], row["offset"], row["effective_from"]
            elif record["status"] != "approved":
                continue
            certificates.setdefault(record["serial"], []).append(
                (effective, record["rev"], index, gain, offset)
            )
        for rows in certificates.values():
            rows.sort(key=lambda row: (row[0], row[1], row[2]))
        return certificates

    def certificate_at(self, serial: str, epoch: int):
        found = None
        for row in self.certificates.get(serial, ()):
            if row[0] <= epoch:
                found = row
            else:
                break
        return None if found is None else (found[3], found[4])

    def _fault_windows(self) -> dict:
        windows = {}
        for record in self.estate.rows("fault_window"):
            if record["decision"] != "accepted" or record["decided_at"] > self.freeze:
                continue
            windows.setdefault((record["asset"], record["channel"]), []).append(
                (record["start"], record["end"])
            )
        return windows

    def in_fault_window(self, asset: str, channel: str, epoch: int) -> bool:
        for start, end in self.fault_windows.get((asset, channel), ()):
            if start <= epoch < end:
                return True
        return False

    def _envelopes(self) -> dict:
        limits = {}
        for index, record in enumerate(self.estate.rows("envelope")):
            if record["status"] != "active":
                continue
            limits.setdefault((record["asset"], record["channel"]), []).append(
                (record["effective_from"], index, record["lo"], record["hi"])
            )
        for rows in limits.values():
            rows.sort(key=lambda row: (row[0], row[1]))
        return limits

    def is_quarantined(self, asset: str, channel: str, epoch: int, value: Fraction) -> bool:
        found = None
        for row in self.envelopes.get((asset, channel), ()):
            if row[0] <= epoch:
                found = row
            else:
                break
        if found is None:
            return False
        return value < found[2] or value > found[3]

    # -- telemetry ---------------------------------------------------------

    @staticmethod
    def _surviving(groups) -> dict:
        """One row per asset and interval instant: highest seq, later row on a tie."""
        best = {}
        order = 0
        for records in groups:
            for record in records:
                order += 1
                key = (record["asset"], record["at"])
                rank = (record["seq"], order)
                if key not in best or rank > best[key][0]:
                    best[key] = (rank, record)
        return best

    def _historian_groups(self) -> list:
        """The historian exports in name order, the backfill last (FPS-4 4.1)."""
        names = self.estate.files_of("hist", "in_scope")
        received = {
            name: any(
                field.name == "received_at" for field in self.standard.fields[(name, "hist")]
            )
            for name in names
        }
        groups = []
        for name in sorted(names, key=lambda n: (received[n], n)):
            rows = [r for r in self.estate.records[name] if r["_table"] == "hist"]
            if received[name]:
                rows = [r for r in rows if r["received_at"] <= self.freeze]
            groups.append(rows)
        return groups

    def _resend_rows(self) -> dict:
        best = {}
        for order, record in enumerate(self.estate.rows("resend", "reference_copy")):
            if not record["gapfill"]:
                continue
            key = (record["asset"], record["at"])
            rank = (record["seq"], order)
            if key not in best or rank > best[key][0]:
                best[key] = (rank, record)
        return best

    def _reading_rows(self):
        gateways = self.estate.files_of("cm", "in_scope")
        condition = self._surviving(self.estate.records[name] for name in gateways)
        for key, row in self._resend_rows().items():
            if key not in condition:
                condition[key] = row
        process = self._surviving(self._historian_groups())
        for (asset, at), (_rank, record) in condition.items():
            for channel, field in CM_CHANNELS:
                if record[field] is not None:
                    yield asset, at, channel, record[field]
        for (asset, at), (_rank, record) in process.items():
            for channel, field in HIST_CHANNELS:
                if record[field] is not None:
                    yield asset, at, channel, record[field]

    def _daily_readings(self) -> dict:
        daily = {}
        for asset, at, channel, raw in self._reading_rows():
            if asset not in self.timelines:
                continue
            day = self.local_day_of(asset, at)
            if not self.standard.window_start <= day <= self.standard.window_end:
                continue
            bucket = daily.setdefault((asset, day), {"values": {}, "readings": 0, "quarantined": 0})
            serial = self.sensor_at(asset, channel, at)
            if serial is None:
                continue
            calibration = self.certificate_at(serial, at)
            if calibration is None:
                continue
            if self.in_fault_window(asset, channel, at):
                continue
            gain, offset = calibration
            value = round_places(gain * raw + offset, CHANNEL_PLACES[channel])
            if self.is_quarantined(asset, channel, at, value):
                bucket["quarantined"] += 1
                continue
            bucket["readings"] += 1
            bucket["values"].setdefault(channel, []).append(value)
        return daily

    # -- availability ------------------------------------------------------

    def _embargoes(self) -> dict:
        chosen = {}
        for index, record in enumerate(self.estate.rows("embargo")):
            if record["set_at"] > self.freeze:
                continue
            key = (record["asset"], record["month"])
            rank = (record["rev"], index)
            if key not in chosen or rank > chosen[key][0]:
                chosen[key] = (rank, record["flag"])
        return {
            key: flag
            for key, (_rank, flag) in chosen.items()
            if key[1].day == 1
        }

    def _windows(self, table: str, keep) -> dict:
        windows = {}
        for record in self.estate.rows(table):
            if not keep(record):
                continue
            windows.setdefault(record["asset"], []).append((record["start"], record["end"]))
        return windows

    def _standby_windows(self) -> dict:
        chosen = {}
        for index, record in enumerate(self.estate.rows("standby")):
            rank = (record["seq"], index)
            if record["rid"] not in chosen or rank > chosen[record["rid"]][0]:
                chosen[record["rid"]] = (rank, record)
        windows = {}
        for _rank, record in chosen.values():
            if record["status"] != "confirmed":
                continue
            windows.setdefault(record["asset"], []).append((record["start"], record["end"]))
        return windows

    def _review_holds(self) -> dict:
        holds = {}
        for record in self.estate.rows("kp23_label", "reference_copy"):
            holds[(record["asset"], record["day"])] = record["review_hold"]
        return holds

    @staticmethod
    def covered_seconds(windows, start: int, end: int) -> int:
        spans = []
        for begin, finish in windows:
            low, high = max(begin, start), min(finish, end)
            if low < high:
                spans.append((low, high))
        spans.sort()
        total = 0
        reach = start
        for low, high in spans:
            if high <= reach:
                continue
            total += high - max(low, reach)
            reach = high
        return total

    def availability(self, asset: str, day: dt.date, site: str) -> str:
        month = dt.date(day.year, day.month, 1)
        if self.embargoes.get((asset, month)):
            return "embargo"
        rule = self.standard.tz_of_site(site)
        start = local_to_utc(rule, epoch_of(day))
        end = local_to_utc(rule, epoch_of(day + dt.timedelta(days=1)))
        half = 12 * 3600
        if self.covered_seconds(self.outages.get(asset, ()), start, end) >= half:
            return "outage"
        if self.covered_seconds(self.standbys.get(asset, ()), start, end) >= half:
            return "standby"
        if self.holds.get((asset, day)):
            return "hold"
        return "ok"

    # -- alarms ------------------------------------------------------------

    def _firmware(self) -> dict:
        rollouts = {}
        for index, record in enumerate(self.estate.rows("firmware")):
            if record["status"] not in ("done", "rolledback"):
                continue
            rollouts.setdefault(record["asset"], []).append((record["at"], index, record["version"]))
        for rows in rollouts.values():
            rows.sort(key=lambda row: (row[0], row[1]))
        return rollouts

    def major_version(self, rollouts: dict, asset: str, epoch: int) -> int:
        version = "1.0.0"
        for at, _index, value in rollouts.get(asset, ()):
            if at <= epoch:
                version = value
            else:
                break
        return int(version.split(".")[0])

    def _alarm_dictionary(self) -> tuple:
        appendix = {}
        for index, record in enumerate(self.estate.rows("alarm_code", "in_scope")):
            appendix.setdefault((record["oem"], record["code"]), []).append(
                (record["min_fw"], index, record["class"])
            )
        draft = {}
        for index, record in enumerate(self.estate.rows("alarm_code", "reference_copy")):
            draft.setdefault((record["oem"], record["code"]), []).append(
                (record["min_fw"], index, record["class"])
            )
        return appendix, draft

    @staticmethod
    def alarm_class(dictionary: dict, draft: dict, oem: str, code: int, major: int):
        rows = dictionary.get((oem, code))
        if rows is None:
            rows = draft.get((oem, code))
        if not rows:
            return None
        best = None
        for min_fw, index, value in rows:
            if min_fw > major:
                continue
            if best is None or min_fw > best[0]:
                best = (min_fw, index, value)
        return None if best is None else best[2]

    def _alarm_days(self) -> dict:
        rollouts = self._firmware()
        appendix, draft = self._alarm_dictionary()
        nuisance = {}
        for record in self.estate.rows("alarm_ack"):
            if record["kind"] not in ("nuisance", "test") or record["acked_at"] > self.freeze:
                continue
            key = record["alarm_rid"]
            if key not in nuisance or record["acked_at"] < nuisance[key]:
                nuisance[key] = record["acked_at"]
        shelving = {}
        for record in self.estate.rows("shelve"):
            if record["status"] != "active":
                continue
            shelving.setdefault((record["asset"], record["code"]), []).append(
                (record["start"], record["end"])
            )
        counts = {}
        for record in self.estate.rows("alarm"):
            asset = record["asset"]
            timeline = self.timelines.get(asset)
            if timeline is None or timeline.model is None:
                continue
            at = record["at"]
            oem = self.standard.models.get(timeline.model)
            if oem is None:
                continue
            major = self.major_version(rollouts, asset, at)
            kind = self.alarm_class(appendix, draft, oem, record["code"], major)
            if kind not in ("warning", "trip"):
                continue
            acked = nuisance.get(record["rid"])
            if acked is not None and acked <= at + 15 * 60:
                continue
            shelved = False
            for start, end in shelving.get((asset, record["code"]), ()):
                if start <= at < end:
                    shelved = True
                    break
            if shelved:
                continue
            day = self.local_day_of(asset, at)
            counts[(asset, day)] = counts.get((asset, day), 0) + 1
        return counts

    # -- site days ---------------------------------------------------------

    def _site_days(self) -> dict:
        shifts = {}
        for index, record in enumerate(self.estate.rows("shift")):
            key = (record["site"], record["day"], record["shift"])
            rank = (record["rev"], index)
            if key not in shifts or rank > shifts[key][0]:
                shifts[key] = (rank, record["status"])
        operating = {}
        for (site, day, _shift), (_rank, status) in shifts.items():
            if status == "operating":
                operating[(site, day)] = operating.get((site, day), 0) + 1
        ambient = self._ambient()
        rows = {}
        for site in sorted(self.standard.sites):
            for day in days_between(self.standard.window_start, self.standard.window_end):
                count = operating.get((site, day), 0)
                rows[(site, day)] = {
                    "shifts_operating": count,
                    "operating": count >= 2,
                    "ambient_c": ambient.get((site, day)),
                }
        return rows

    def _ambient(self) -> dict:
        checks = {}
        for index, record in enumerate(self.estate.rows("ambient_qc")):
            if record["at"] > self.freeze:
                continue
            key = record["obs_rid"]
            rank = (record["at"], index)
            if key not in checks or rank > checks[key][0]:
                checks[key] = (rank, record)
        shipped = {}
        for index, record in enumerate(self.estate.rows("ambient", "in_scope")):
            rule = self.standard.tz_of_site(record["site"])
            day = local_date(rule, record["at"])
            shipped.setdefault((record["site"], day, record["kind"]), []).append((record, index))
        for index, record in enumerate(self.estate.rows("ambient", "reference_copy")):
            rule = self.standard.tz_of_site(record["site"])
            day = local_date(rule, record["at"])
            key = (record["site"], day, record["kind"])
            if key not in shipped:
                shipped[key] = [(record, index)]
        values = {}
        for (site, day, kind), rows in shipped.items():
            best = None
            for record, index in rows:
                check = checks.get(record["rid"])
                value = record["temp"]
                if check is not None:
                    outcome = check[1]["outcome"]
                    if outcome == "reject":
                        continue
                    if outcome == "retest" and check[1]["temp"] is not None:
                        value = check[1]["temp"]
                rank = (record["at"], index)
                if best is None or rank > best[0]:
                    best = (rank, value)
            if best is not None:
                values[(site, day, kind)] = best[1]
        ambient = {}
        for site in self.standard.sites:
            for day in days_between(self.standard.window_start, self.standard.window_end):
                low = values.get((site, day, "min"))
                high = values.get((site, day, "max"))
                if low is None or high is None:
                    continue
                ambient[(site, day)] = round_places((low + high) / 2, 2)
        return ambient

    # -- asset days --------------------------------------------------------

    def _asset_days(self) -> list:
        rows = []
        noon = 12 * 3600
        for asset in sorted(self.timelines):
            for day in days_between(self.standard.window_start, self.standard.window_end):
                state = self.timelines[asset].at(epoch_of(day, noon))
                if not state["active"]:
                    continue
                site = state["site"]
                bucket = self.readings.get((asset, day)) or {"values": {}, "readings": 0, "quarantined": 0}
                values = bucket["values"]
                means = {}
                for channel, places in CHANNEL_PLACES.items():
                    found = values.get(channel)
                    means[channel] = (
                        round_places(sum(found, Fraction(0)) / len(found), places) if found else None
                    )
                vib = values.get("vib")
                rows.append(
                    {
                        "asset_id": asset,
                        "day": day,
                        "site": site,
                        "availability": self.availability(asset, day, site),
                        "vib_mean": means["vib"],
                        "vib_max": max(vib) if vib else None,
                        "temp": means["temp"],
                        "pressure": means["prs"],
                        "flow": means["flw"],
                        "current": means["cur"],
                        "setpoint": state["setpoint"],
                        "rated_flow": self.rated_flow_at(asset, epoch_of(day, noon)),
                        "alarms": self.alarm_days.get((asset, day), 0),
                        "readings": bucket["readings"],
                        "quarantined": bucket["quarantined"],
                    }
                )
        return rows

    # -- maintenance -------------------------------------------------------

    def _services(self) -> list:
        revisions = {}
        for index, record in enumerate(self.estate.rows("wo_rev")):
            if record["revised_at"] > self.freeze:
                continue
            key = record["wo_no"]
            rank = (record["rev"], record["revised_at"], index)
            if key not in revisions or rank > revisions[key][0]:
                revisions[key] = (rank, record)
        mirror = {}
        for record in self.estate.rows("work_order", "reference_copy"):
            mirror.setdefault(record["wo_no"], record)
        bookings = {}
        for record in self.estate.rows("labour"):
            key = record["wo_no"]
            if key not in bookings or record["end"] > bookings[key]:
                bookings[key] = record["end"]
        services = []
        for record in self.estate.rows("work_order", "in_scope"):
            status, closed = record["status"], record["closed_at"]
            revision = revisions.get(record["wo_no"])
            if revision is not None:
                status = revision[1]["status"]
                closed = revision[1]["closed_at"]
            if closed is None and record["opened_at"] < self.standard.legacy_cutoff:
                row = mirror.get(record["wo_no"])
                if row is not None:
                    closed = row["closed_at"]
            if status != "completed":
                continue
            at = bookings.get(record["wo_no"], closed)
            if at is None or at > self.freeze:
                continue
            asset = record["asset"]
            if asset not in self.timelines:
                continue
            services.append(
                {
                    "asset_id": asset,
                    "event_at": at,
                    "event_day": self.local_day_of(asset, at),
                    "kind": record["kind"],
                    "value": None,
                    "ref": record["wo_no"],
                }
            )
        return services

    def _oil_samples(self) -> list:
        checks = {}
        for index, record in enumerate(self.estate.rows("oil_qc")):
            if record["at"] > self.freeze:
                continue
            key = record["sample_no"]
            rank = (record["at"], index)
            if key not in checks or rank > checks[key][0]:
                checks[key] = (rank, record)
        samples = []
        for record in self.estate.rows("oil"):
            if record["status"] != "valid" or record["sampled_at"] > self.freeze:
                continue
            iron = record["iron"]
            check = checks.get(record["sample_no"])
            if check is not None:
                outcome = check[1]["outcome"]
                if outcome == "reject":
                    continue
                if outcome == "retest" and check[1]["iron"] is not None:
                    iron = check[1]["iron"]
            asset = record["asset"]
            if asset not in self.timelines:
                continue
            samples.append(
                {
                    "asset_id": asset,
                    "event_at": record["sampled_at"],
                    "event_day": self.local_day_of(asset, record["sampled_at"]),
                    "kind": "oil",
                    "value": int(iron),
                    "ref": record["sample_no"],
                }
            )
        return samples

    # -- failures ----------------------------------------------------------

    def _failure_events(self) -> list:
        notifications = [r for r in self.estate.rows("notification") if r["kind"] == "failure"]
        decisions = {}
        order = 0
        for record in self.estate.rows("rca"):
            order += 1
            if record["decided_at"] > self.freeze:
                continue
            decisions.setdefault(record["notif_no"], []).append(
                (record["decided_at"], 0, record["rev"], order, record["decision"], record["mode"])
            )
        amendments = {}
        for index, record in enumerate(self.estate.rows("amendment")):
            rank = (record["seq"], index)
            if record["rid"] not in amendments or rank > amendments[record["rid"]][0]:
                amendments[record["rid"]] = (rank, record)
        deferred = {}
        for (_seq, index), record in sorted(amendments.values(), key=lambda row: row[0][1]):
            if record["status"] != "confirmed":
                continue
            if record["amended_at"] > self.freeze:
                key = record["notif_no"]
                rank = (record["amended_at"], index)
                if key not in deferred or rank > deferred[key][0]:
                    deferred[key] = (rank, record)
                continue
            decisions.setdefault(record["notif_no"], []).append(
                (record["amended_at"], 1, record["seq"], index, record["decision"], record["mode"])
            )
        rows = []
        for record in notifications:
            asset = record["asset"]
            decision = None
            for candidate in decisions.get(record["notif_no"], ()):
                if decision is None or candidate[:4] > decision[:4]:
                    decision = candidate
            status = "unconfirmed"
            mode = record["mode"]
            decided_at = None
            if decision is not None:
                decided_at = decision[0]
                if decision[4] in ("confirm", "reclassify"):
                    status = "confirmed"
                if decision[5] is not None:
                    mode = decision[5]
            pending = deferred.get(record["notif_no"])
            rows.append(
                {
                    "event_id": record["notif_no"],
                    "asset_id": asset,
                    "failed_at": record["failed_at"],
                    "failed_day": self.local_day_of(asset, record["failed_at"]),
                    "status": status,
                    "mode": mode,
                    "decided_at": decided_at,
                    "pending_decision": pending[1]["decision"] if pending else None,
                    "pending_mode": (
                        pending[1]["mode"]
                        if pending and pending[1]["decision"] == "reclassify"
                        else None
                    ),
                    "pending_at": pending[1]["amended_at"] if pending else None,
                }
            )
        rows.sort(key=lambda row: row["event_id"])
        return rows

    # -- the six tables ----------------------------------------------------

    def asset_registry(self) -> list[list[str]]:
        rows = []
        for asset in sorted(self.timelines):
            timeline = self.timelines[asset]
            state = timeline.at(self.freeze)
            rows.append(
                [
                    asset,
                    state["site"],
                    timeline.model or "",
                    self.standard.models.get(timeline.model, "") if timeline.model else "",
                    timeline.serial or "",
                    timeline.commissioned_on.isoformat() if timeline.commissioned_on else "",
                    fmt_instant(state["decommissioned_at"]) if state["decommissioned_at"] else "",
                    state["criticality"] or "",
                    fmt_places(state["setpoint"], 3) if state["setpoint"] is not None else "",
                    self._flow_text(self.rated_flow_at(asset, self.freeze)),
                    "true" if asset in self.holdout else "false",
                ]
            )
        return rows

    @staticmethod
    def _flow_text(value) -> str:
        return "" if value is None else fmt_places(value, 2)

    def sensor_daily(self) -> list[list[str]]:
        rows = []
        for row in self.asset_days:
            rows.append(
                [
                    row["asset_id"],
                    row["day"].isoformat(),
                    row["site"],
                    row["availability"],
                    self._value_text(row["vib_mean"], 3),
                    self._value_text(row["vib_max"], 3),
                    self._value_text(row["temp"], 2),
                    self._value_text(row["pressure"], 3),
                    self._value_text(row["flow"], 2),
                    self._value_text(row["current"], 2),
                    self._value_text(row["setpoint"], 3),
                    self._value_text(row["rated_flow"], 2),
                    str(row["alarms"]),
                    str(row["readings"]),
                    str(row["quarantined"]),
                ]
            )
        return rows

    @staticmethod
    def _value_text(value, places: int) -> str:
        return "" if value is None else fmt_places(value, places)

    def failure_events(self) -> list[list[str]]:
        rows = []
        for row in self.failures:
            rows.append(
                [
                    row["event_id"],
                    row["asset_id"],
                    fmt_instant(row["failed_at"]),
                    row["failed_day"].isoformat(),
                    row["status"],
                    row["mode"] or "",
                    fmt_instant(row["decided_at"]) if row["decided_at"] else "",
                    row["pending_decision"] or "",
                    row["pending_mode"] or "",
                    fmt_instant(row["pending_at"]) if row["pending_at"] else "",
                ]
            )
        return rows

    def maintenance_log(self) -> list[list[str]]:
        entries = self.services + self.oil_samples
        entries.sort(key=lambda row: (row["asset_id"], row["event_at"], row["ref"]))
        rows = []
        for row in entries:
            rows.append(
                [
                    row["asset_id"],
                    fmt_instant(row["event_at"]),
                    row["event_day"].isoformat(),
                    row["kind"],
                    "" if row["value"] is None else str(row["value"]),
                    row["ref"],
                ]
            )
        return rows

    def site_day_rows(self) -> list[list[str]]:
        rows = []
        for (site, day), row in sorted(self.site_days.items()):
            rows.append(
                [
                    site,
                    day.isoformat(),
                    str(row["shifts_operating"]),
                    "true" if row["operating"] else "false",
                    self._value_text(row["ambient_c"], 2),
                ]
            )
        return rows

    def run_parameters(self) -> dict:
        sources = []
        for name in self.estate.files:
            role = self.standard.roles.get(name)
            if role is None:
                raise BuildError("the source register does not list %s" % name)
            sources.append(
                {
                    "file": name,
                    "role": role,
                    "records": self.estate.record_counts[name],
                    "digest": self.estate.digests[name],
                }
            )
        sources.sort(key=lambda row: row["file"])
        return {
            "run_id": "KP-24",
            "freeze": fmt_instant(self.freeze),
            "telemetry_window": [
                self.standard.window_start.isoformat(),
                self.standard.window_end.isoformat(),
            ],
            "parameters": {
                name: value for name, value in self.parameters.items() if name != "holdout_assets"
            },
            "holdout_assets": self.holdout,
            "regions": {code: site["region"] for code, site in self.standard.sites.items()},
            "sources": sources,
        }


ASSET_REGISTRY_HEADER = [
    "asset_id",
    "site",
    "model",
    "oem",
    "serial",
    "commissioned_on",
    "decommissioned_at",
    "criticality",
    "setpoint_bar",
    "rated_flow_m3h",
    "holdout",
]
SENSOR_DAILY_HEADER = [
    "asset_id",
    "day",
    "site",
    "availability",
    "vib_mean_mm_s",
    "vib_max_mm_s",
    "temp_c",
    "pressure_bar",
    "flow_m3h",
    "current_a",
    "setpoint_bar",
    "rated_flow_m3h",
    "alarms",
    "readings",
    "quarantined",
]
FAILURE_EVENTS_HEADER = [
    "event_id",
    "asset_id",
    "failed_at",
    "failed_day",
    "status",
    "mode",
    "decided_at",
    "pending_decision",
    "pending_mode",
    "pending_at",
]
MAINTENANCE_LOG_HEADER = ["asset_id", "event_at", "event_day", "kind", "value", "ref"]
SITE_DAYS_HEADER = ["site", "day", "shifts_operating", "operating", "ambient_c"]


def write_csv(path: str, header: list[str], rows: list[list[str]]):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def write_json(path: str, document):
    text = json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text + "\n")


def ensure_directory(path: str):
    try:
        os.makedirs(path, exist_ok=True)
    except OSError as error:
        raise BuildError("cannot create the output directory: %s" % error) from error


def phase1(data_dir: str, out_dir: str):
    """Decode and reconcile the sources into the six phase 1 files."""
    estate = Estate(data_dir)
    builder = Phase1(estate)
    ensure_directory(out_dir)
    write_csv(os.path.join(out_dir, "asset_registry.csv"), ASSET_REGISTRY_HEADER, builder.asset_registry())
    write_csv(os.path.join(out_dir, "sensor_daily.csv"), SENSOR_DAILY_HEADER, builder.sensor_daily())
    write_csv(os.path.join(out_dir, "failure_events.csv"), FAILURE_EVENTS_HEADER, builder.failure_events())
    write_csv(
        os.path.join(out_dir, "maintenance_log.csv"), MAINTENANCE_LOG_HEADER, builder.maintenance_log()
    )
    write_csv(os.path.join(out_dir, "site_days.csv"), SITE_DAYS_HEADER, builder.site_day_rows())
    write_json(os.path.join(out_dir, "run_parameters.json"), builder.run_parameters())


# --------------------------------------------------------------------------
# upstream directories: reading what an earlier phase handed on
# --------------------------------------------------------------------------

FEATURES = (
    "vib_mean_7d",
    "vib_max_7d",
    "temp_rise_7d",
    "pressure_dev_3d",
    "flow_ratio_7d",
    "current_7d",
    "days_since_service",
    "age_days",
    "iron_ppm",
    "alarms_7d",
)
INTEGER_FEATURES = ("days_since_service", "age_days", "iron_ppm", "alarms_7d")
EXCLUSION_REASONS = (
    "non_operating",
    "embargo",
    "outage",
    "standby",
    "hold",
    "low_coverage",
    "blackout",
    "maintenance",
    "purge",
)
P2_FILES = (
    "label_table.json",
    "feature_matrix.json",
    "scaler_stats.json",
    "class_balance.json",
    "quarantine_summary.json",
    "bin_edges.json",
)
def read_text(path: str) -> tuple[str, str]:
    try:
        with open(path, "rb") as handle:
            raw = handle.read()
    except OSError as error:
        raise BuildError("cannot read %s: %s" % (os.path.basename(path), error)) from error
    return raw.decode("utf-8"), hashlib.sha256(raw).hexdigest()


def read_table(text: str) -> list[dict]:
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        raise BuildError("an upstream table is empty")
    header = rows[0]
    return [dict(zip(header, cells)) for cells in rows[1:]]


def optional_fraction(text: str):
    return None if text == "" else Fraction(text)


def optional_day(text: str):
    return None if text == "" else dt.date.fromisoformat(text)


class Upstream:
    """The phase 1 (and phase 2) files one later phase reads."""

    def __init__(self, p1_dir: str, p2_dir: str = None):
        self.digests = {}
        self.texts = {}
        for name in P1_FILES:
            text, digest = read_text(os.path.join(p1_dir, name))
            self.texts["p1/" + name] = text
            self.digests["p1/" + name] = digest
        if p2_dir is not None:
            for name in P2_FILES:
                text, digest = read_text(os.path.join(p2_dir, name))
                self.texts["p2/" + name] = text
                self.digests["p2/" + name] = digest
        self.assets = read_table(self.texts["p1/asset_registry.csv"])
        self.sensor_daily = read_table(self.texts["p1/sensor_daily.csv"])
        self.failures = read_table(self.texts["p1/failure_events.csv"])
        self.maintenance = read_table(self.texts["p1/maintenance_log.csv"])
        self.site_days = read_table(self.texts["p1/site_days.csv"])
        self.run = json.loads(self.texts["p1/run_parameters.json"])
        self.parameters = self.run["parameters"]
        self.phase2 = {
            name: json.loads(self.texts["p2/" + name]) for name in P2_FILES
        } if p2_dir is not None else {}

    # -- parameters --------------------------------------------------------

    def day_parameter(self, name: str) -> dt.date:
        return dt.date.fromisoformat(self.parameters[name])

    def integer(self, name: str) -> int:
        return int(self.parameters[name])

    def number(self, name: str) -> Fraction:
        return Fraction(self.parameters[name])

    # -- lineage -----------------------------------------------------------

    def upstream_digest(self) -> str:
        digest = hashlib.sha256()
        for label in sorted(self.digests):
            digest.update(("%s\n%s\n" % (label, self.digests[label])).encode("utf-8"))
        return digest.hexdigest()

    def upstream_controls(self) -> dict:
        controls = {}
        controls["p1/asset_registry.csv"] = self._csv_control(
            self.assets, lambda r: optional_fraction(r["rated_flow_m3h"]), 2, lambda r: r["asset_id"]
        )
        controls["p1/sensor_daily.csv"] = self._csv_control(
            self.sensor_daily,
            lambda r: Fraction(int(r["readings"])),
            0,
            lambda r: "%s|%s" % (r["asset_id"], r["day"]),
        )
        controls["p1/failure_events.csv"] = self._csv_control(
            self.failures,
            lambda r: Fraction(1 if r["status"] == "confirmed" else 0),
            0,
            lambda r: r["event_id"],
        )
        controls["p1/maintenance_log.csv"] = self._csv_control(
            self.maintenance, lambda r: optional_fraction(r["value"]), 0, lambda r: r["ref"]
        )
        controls["p1/site_days.csv"] = self._csv_control(
            self.site_days,
            lambda r: Fraction(int(r["shifts_operating"])),
            0,
            lambda r: "%s|%s" % (r["site"], r["day"]),
        )
        sources = self.run["sources"]
        controls["p1/run_parameters.json"] = {
            "rows": len(sources),
            "total": fmt_int(sum(row["records"] for row in sources)),
            "last_key": sources[-1]["file"] if sources else "",
        }
        for name in sorted(self.phase2):
            controls["p2/" + name] = self._phase2_control(name, self.phase2[name])
        return controls

    @staticmethod
    def _csv_control(rows: list[dict], value, places: int, key) -> dict:
        total = Fraction(0)
        for row in rows:
            found = value(row)
            if found is not None:
                total += found
        return {
            "rows": len(rows),
            "total": fmt_places(total, places),
            "last_key": key(rows[-1]) if rows else "",
        }

    @staticmethod
    def _phase2_control(name: str, document: dict) -> dict:
        if name in ("label_table.json", "feature_matrix.json"):
            rows = document["rows"]
            field = "label" if name == "label_table.json" else "alarms_7d"
            total = 0
            for row in rows:
                if row[field] is not None:
                    total += int(row[field])
            last = rows[-1] if rows else None
            return {
                "rows": len(rows),
                "total": fmt_int(total),
                "last_key": "%s|%s" % (last["asset_id"], last["day"]) if last else "",
            }
        if name == "scaler_stats.json":
            features = document["features"]
            names = sorted(features)
            total = sum(features[key]["n"] for key in names)
            return {"rows": len(names), "total": fmt_int(total), "last_key": names[-1] if names else ""}
        if name == "bin_edges.json":
            features = document["features"]
            names = sorted(features)
            total = sum(len(features[key]) for key in names)
            return {"rows": len(names), "total": fmt_int(total), "last_key": names[-1] if names else ""}
        if name == "class_balance.json":
            splits = document["splits"]
            names = sorted(splits)
            total = sum(splits[key]["rows"] for key in names)
            return {"rows": len(names), "total": fmt_int(total), "last_key": names[-1] if names else ""}
        if name == "quarantine_summary.json":
            sites = document["sites"]
            names = sorted(sites)
            total = sum(sites[key]["samples_kept"] for key in names)
            return {"rows": len(names), "total": fmt_int(total), "last_key": names[-1] if names else ""}
        raise BuildError("no control for %s" % name)

    def lineage(self) -> dict:
        return {"upstream_digest": self.upstream_digest(), "upstream_controls": self.upstream_controls()}


# --------------------------------------------------------------------------
# phase 2: samples, features and fitted statistics
# --------------------------------------------------------------------------


def sqrt_places(value: Fraction, places: int) -> Fraction:
    """The square root of a non-negative fraction, rounded half to even."""
    if value < 0:
        raise BuildError("cannot take the square root of %s" % value)
    target = value * (10 ** (2 * places))
    num, den = target.numerator, target.denominator
    whole = num // den
    root = math.isqrt(whole)
    while (root + 1) ** 2 * den <= num:
        root += 1
    while root ** 2 * den > num:
        root -= 1
    left = 4 * num
    right = (2 * root + 1) ** 2 * den
    if left > right or (left == right and root % 2):
        root += 1
    return Fraction(root, 10 ** places)


class Phase2:
    """Builds the six phase 2 files from a phase 1 directory."""

    def __init__(self, upstream: Upstream):
        self.upstream = upstream
        self.sample_start = upstream.day_parameter("sample_start")
        self.sample_end = upstream.day_parameter("sample_end")
        self.train_end = upstream.day_parameter("train_end")
        self.val_end = upstream.day_parameter("val_end")
        self.horizon = upstream.integer("horizon_days")
        self.blackout = upstream.integer("blackout_days")
        self.min_readings = upstream.integer("min_readings")
        self.iron_lookback = upstream.integer("iron_lookback_days")
        self.holdout = set(upstream.run["holdout_assets"])
        self.registry = {row["asset_id"]: row for row in upstream.assets}
        self.days = self._asset_days()
        self.ambient = {
            (row["site"], dt.date.fromisoformat(row["day"])): optional_fraction(row["ambient_c"])
            for row in upstream.site_days
        }
        self.operating = {
            (row["site"], dt.date.fromisoformat(row["day"])): row["operating"] == "true"
            for row in upstream.site_days
        }
        self.failure_days = self._failure_days()
        self.services, self.maintenance_days = self._service_days()
        self.oil = self._oil_samples()
        self.samples, self.excluded = self._samples()
        self.features = self._feature_rows()
        self.train_values = self._train_values()

    # -- phase 1 tables ----------------------------------------------------

    def _asset_days(self) -> dict:
        days = {}
        for row in self.upstream.sensor_daily:
            day = dt.date.fromisoformat(row["day"])
            days[(row["asset_id"], day)] = {
                "site": row["site"],
                "availability": row["availability"],
                "vib_mean": optional_fraction(row["vib_mean_mm_s"]),
                "vib_max": optional_fraction(row["vib_max_mm_s"]),
                "temp": optional_fraction(row["temp_c"]),
                "pressure": optional_fraction(row["pressure_bar"]),
                "flow": optional_fraction(row["flow_m3h"]),
                "current": optional_fraction(row["current_a"]),
                "setpoint": optional_fraction(row["setpoint_bar"]),
                "rated_flow": optional_fraction(row["rated_flow_m3h"]),
                "alarms": int(row["alarms"]),
                "readings": int(row["readings"]),
                "quarantined": int(row["quarantined"]),
            }
        return days

    def _failure_days(self) -> dict:
        failures = {}
        for row in self.upstream.failures:
            if row["status"] != "confirmed":
                continue
            failures.setdefault(row["asset_id"], set()).add(dt.date.fromisoformat(row["failed_day"]))
        return failures

    def _service_days(self) -> tuple[dict, dict]:
        services = {}
        maintenance = {}
        for row in self.upstream.maintenance:
            if row["kind"] == "oil":
                continue
            day = dt.date.fromisoformat(row["event_day"])
            if row["kind"] in SERVICE_KINDS:
                services.setdefault(row["asset_id"], set()).add(day)
            if row["kind"] in MAINTENANCE_KINDS:
                maintenance.setdefault(row["asset_id"], set()).add(day)
        return services, maintenance

    def _oil_samples(self) -> dict:
        samples = {}
        for row in self.upstream.maintenance:
            if row["kind"] != "oil":
                continue
            samples.setdefault(row["asset_id"], []).append(
                (parse_utc_text(row["event_at"]), dt.date.fromisoformat(row["event_day"]), int(row["value"]))
            )
        for rows in samples.values():
            rows.sort()
        return samples

    # -- samples -----------------------------------------------------------

    def exclusion(self, asset: str, day: dt.date, row: dict):
        site_day = (row["site"], day)
        if not self.operating.get(site_day, False):
            return "non_operating"
        if row["availability"] != "ok":
            return row["availability"]
        if row["readings"] < self.min_readings:
            return "low_coverage"
        for failed in self.failure_days.get(asset, ()):
            if failed <= day < failed + dt.timedelta(days=self.blackout):
                return "blackout"
        for service in self.maintenance_days.get(asset, ()):
            if day == service or day == service + dt.timedelta(days=1):
                return "maintenance"
        if asset not in self.holdout:
            if self.train_end - dt.timedelta(days=self.horizon) < day <= self.train_end:
                return "purge"
        return None

    def split_of(self, asset: str, day: dt.date) -> str:
        if asset in self.holdout:
            return "test"
        if day <= self.train_end:
            return "train"
        if day <= self.val_end:
            return "val"
        return "test"

    def label_of(self, asset: str, day: dt.date) -> int:
        for failed in self.failure_days.get(asset, ()):
            if day < failed <= day + dt.timedelta(days=self.horizon):
                return 1
        return 0

    def _samples(self) -> tuple[list, dict]:
        kept = []
        excluded = {}
        for (asset, day), row in self.days.items():
            if not self.sample_start <= day <= self.sample_end:
                continue
            reason = self.exclusion(asset, day, row)
            if reason is not None:
                site = row["site"]
                excluded.setdefault(site, {}).setdefault(reason, 0)
                excluded[site][reason] += 1
                continue
            kept.append(
                {
                    "asset_id": asset,
                    "day": day,
                    "site": row["site"],
                    "split": self.split_of(asset, day),
                    "label": self.label_of(asset, day),
                }
            )
        kept.sort(key=lambda row: (row["asset_id"], row["day"]))
        return kept, excluded

    # -- features ----------------------------------------------------------

    def window(self, asset: str, day: dt.date, length: int) -> list[dict]:
        rows = []
        for back in range(length):
            found = self.days.get((asset, day - dt.timedelta(days=back)))
            if found is not None:
                rows.append(found)
        return rows

    @staticmethod
    def mean_of(values: list, minimum: int):
        if len(values) < minimum:
            return None
        return sum(values, Fraction(0)) / len(values)

    def feature_values(self, sample: dict) -> dict:
        asset, day = sample["asset_id"], sample["day"]
        seven = self.window(asset, day, 7)
        three = self.window(asset, day, 3)
        values = {}
        values["vib_mean_7d"] = self.mean_of([r["vib_mean"] for r in seven if r["vib_mean"] is not None], 4)
        maxima = [r["vib_max"] for r in seven if r["vib_max"] is not None]
        values["vib_max_7d"] = max(maxima) if len(maxima) >= 4 else None
        rises = []
        for back in range(7):
            that_day = day - dt.timedelta(days=back)
            row = self.days.get((asset, that_day))
            if row is None or row["temp"] is None:
                continue
            ambient = self.ambient.get((row["site"], that_day))
            if ambient is None:
                continue
            rises.append(row["temp"] - ambient)
        values["temp_rise_7d"] = self.mean_of(rises, 4)
        deviations = [
            r["pressure"] - r["setpoint"]
            for r in three
            if r["pressure"] is not None and r["setpoint"] is not None
        ]
        values["pressure_dev_3d"] = self.mean_of(deviations, 2)
        ratios = [
            r["flow"] / r["rated_flow"]
            for r in seven
            if r["flow"] is not None and r["rated_flow"] is not None and r["rated_flow"] > 0
        ]
        values["flow_ratio_7d"] = self.mean_of(ratios, 4)
        values["current_7d"] = self.mean_of([r["current"] for r in seven if r["current"] is not None], 4)
        service = None
        for found in self.services.get(asset, ()):
            if found <= day and (service is None or found > service):
                service = found
        values["days_since_service"] = None if service is None else (day - service).days
        commissioned = optional_day(self.registry[asset]["commissioned_on"])
        values["age_days"] = None if commissioned is None else (day - commissioned).days
        iron = None
        for at, sampled, value in self.oil.get(asset, ()):
            if sampled <= day and (day - sampled).days < self.iron_lookback:
                iron = value
        values["iron_ppm"] = iron
        alarms = 0
        for back in range(7):
            row = self.days.get((asset, day - dt.timedelta(days=back)))
            if row is not None:
                alarms += row["alarms"]
        values["alarms_7d"] = alarms
        return values

    def _feature_rows(self) -> list[dict]:
        rows = []
        for sample in self.samples:
            rows.append(self.feature_values(sample))
        return rows

    @staticmethod
    def feature_text(name: str, value):
        if value is None:
            return None
        if name in INTEGER_FEATURES:
            return int(value)
        return fmt_places(value, 4)

    @staticmethod
    def stored_value(name: str, value):
        """The value as the feature matrix states it, read back for statistics."""
        if value is None:
            return None
        if name in INTEGER_FEATURES:
            return Fraction(int(value))
        return round_places(value, 4)

    def _train_values(self) -> dict:
        values = {name: [] for name in FEATURES}
        for sample, row in zip(self.samples, self.features):
            if sample["split"] != "train":
                continue
            for name in FEATURES:
                stored = self.stored_value(name, row[name])
                if stored is not None:
                    values[name].append(stored)
        return values

    # -- the six files -----------------------------------------------------

    def label_table(self) -> dict:
        return {
            "rows": [
                {
                    "asset_id": sample["asset_id"],
                    "day": sample["day"].isoformat(),
                    "split": sample["split"],
                    "label": sample["label"],
                }
                for sample in self.samples
            ]
        }

    def feature_matrix(self) -> dict:
        rows = []
        for sample, row in zip(self.samples, self.features):
            entry = {"asset_id": sample["asset_id"], "day": sample["day"].isoformat()}
            for name in FEATURES:
                entry[name] = self.feature_text(name, row[name])
            rows.append(entry)
        return {"features": list(FEATURES), "rows": rows}

    def scaler_stats(self) -> dict:
        features = {}
        for name in FEATURES:
            values = self.train_values[name]
            count = len(values)
            if count < 2:
                features[name] = {"n": count, "mean": None, "std": None}
                continue
            mean = sum(values, Fraction(0)) / count
            variance = sum(((value - mean) ** 2 for value in values), Fraction(0)) / (count - 1)
            features[name] = {
                "n": count,
                "mean": fmt_places(mean, 6),
                "std": fmt_places(sqrt_places(variance, 6), 6),
            }
        return {"fit_split": "train", "features": features}

    def class_balance(self) -> dict:
        splits = {}
        for sample in self.samples:
            bucket = splits.setdefault(sample["split"], {"rows": 0, "positives": 0})
            bucket["rows"] += 1
            bucket["positives"] += sample["label"]
        result = {}
        for name, bucket in splits.items():
            rows, positives = bucket["rows"], bucket["positives"]
            result[name] = {
                "rows": rows,
                "positives": positives,
                "negatives": rows - positives,
                "prevalence": fmt_places(Fraction(positives, rows) if rows else Fraction(0), 6),
            }
        train = splits.get("train", {"rows": 0, "positives": 0})
        rows, positives = train["rows"], train["positives"]
        negatives = rows - positives
        return {
            "splits": result,
            "class_weights": {
                "positive": fmt_places(Fraction(rows, 2 * positives) if positives else Fraction(0), 6),
                "negative": fmt_places(Fraction(rows, 2 * negatives) if negatives else Fraction(0), 6),
            },
        }

    def bin_edges(self) -> dict:
        features = {}
        for name in FEATURES:
            values = sorted(self.train_values[name])
            count = len(values)
            if count < 10:
                features[name] = []
                continue
            edges = []
            for k in range(1, 10):
                position = -(-k * count // 10)
                value = values[position - 1]
                edges.append(fmt_int(value) if name in INTEGER_FEATURES else fmt_places(value, 4))
            features[name] = edges
        return {"features": features}

    def quarantine_summary(self) -> dict:
        sites = {}
        for (_asset, _day), row in self.days.items():
            bucket = sites.setdefault(
                row["site"],
                {"readings_quarantined": 0, "samples_kept": 0, "excluded": {r: 0 for r in EXCLUSION_REASONS}},
            )
            bucket["readings_quarantined"] += row["quarantined"]
        for sample in self.samples:
            sites[sample["site"]]["samples_kept"] += 1
        for site, reasons in self.excluded.items():
            for reason, count in reasons.items():
                sites[site]["excluded"][reason] += count
        return {"sites": sites}


def phase2(p1_dir: str, p2_dir: str):
    """Build the samples, features and fitted statistics of a phase 1 directory."""
    upstream = Upstream(p1_dir)
    builder = Phase2(upstream)
    lineage = upstream.lineage()
    documents = {
        "label_table.json": builder.label_table(),
        "feature_matrix.json": builder.feature_matrix(),
        "scaler_stats.json": builder.scaler_stats(),
        "class_balance.json": builder.class_balance(),
        "quarantine_summary.json": builder.quarantine_summary(),
        "bin_edges.json": builder.bin_edges(),
    }
    ensure_directory(p2_dir)
    for name, document in documents.items():
        document.update(lineage)
        write_json(os.path.join(p2_dir, name), document)


# --------------------------------------------------------------------------
# phase 3: training rows and reports
# --------------------------------------------------------------------------


def average_ranks(values: list) -> list:
    """Ranks from 1 up, tied values sharing their average rank."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [Fraction(0)] * len(values)
    index = 0
    while index < len(order):
        stop = index
        while stop + 1 < len(order) and values[order[stop + 1]] == values[order[index]]:
            stop += 1
        shared = Fraction(sum(range(index + 1, stop + 2)), stop - index + 1)
        for position in range(index, stop + 1):
            ranks[order[position]] = shared
        index = stop + 1
    return ranks


def area_under_curve(scores: list, labels: list) -> Fraction:
    positives = sum(labels)
    negatives = len(labels) - positives
    if not positives or not negatives:
        return Fraction(0)
    ranks = average_ranks(scores)
    total = sum(rank for rank, label in zip(ranks, labels) if label)
    return (total - Fraction(positives * (positives + 1), 2)) / (positives * negatives)


def f_one(true_positive: int, false_positive: int, false_negative: int) -> Fraction:
    denominator = 2 * true_positive + false_positive + false_negative
    if not denominator:
        return Fraction(0)
    return Fraction(2 * true_positive, denominator)


class Phase3:
    """Builds the six phase 3 files from a phase 1 and a phase 2 directory."""

    def __init__(self, upstream: Upstream):
        self.upstream = upstream
        self.labels = upstream.phase2["label_table.json"]["rows"]
        self.matrix = upstream.phase2["feature_matrix.json"]["rows"]
        self.scaler = upstream.phase2["scaler_stats.json"]["features"]
        self.balance = upstream.phase2["class_balance.json"]
        self.edges = upstream.phase2["bin_edges.json"]["features"]
        self.registry = {row["asset_id"]: row for row in upstream.assets}
        self.sites = {
            (row["asset_id"], row["day"]): row["site"] for row in upstream.sensor_daily
        }
        self.train_end = upstream.day_parameter("train_end")
        self.horizon = upstream.integer("horizon_days")
        self.half_life = upstream.number("decay_half_life_days")
        self.weight_cap = upstream.number("asset_weight_cap")
        self.rows = self._rows()
        self.scores = self._scores()

    # -- standardised rows -------------------------------------------------

    def _standardise(self, name: str, value) -> Fraction:
        stats = self.scaler.get(name)
        if value is None or stats is None or stats["mean"] is None or stats["std"] is None:
            return None
        deviation = Fraction(stats["std"])
        if deviation == 0:
            return None
        return round_places((Fraction(str(value)) - Fraction(stats["mean"])) / deviation, 4)

    def _rows(self) -> list[dict]:
        rows = []
        for label_row, feature_row in zip(self.labels, self.matrix):
            if (label_row["asset_id"], label_row["day"]) != (feature_row["asset_id"], feature_row["day"]):
                raise BuildError("the label table and the feature matrix disagree")
            standardised = {name: self._standardise(name, feature_row[name]) for name in FEATURES}
            rows.append(
                {
                    "asset_id": label_row["asset_id"],
                    "day": label_row["day"],
                    "split": label_row["split"],
                    "label": int(label_row["label"]),
                    "z": standardised,
                }
            )
        self._weigh(rows)
        return rows

    def _weigh(self, rows: list[dict]):
        weights = self.balance["class_weights"]
        used = {}
        for row in rows:
            if row["split"] != "train":
                row["sample_weight"] = Fraction(1)
                continue
            asset = row["asset_id"]
            day = dt.date.fromisoformat(row["day"])
            distance = (self.train_end - day).days
            recency = round_places(Fraction(2.0 ** (-float(distance) / float(self.half_life))), 6)
            criticality = self.registry[asset]["criticality"]
            multiplier = self.upstream.number("crit_multiplier_%s" % criticality)
            class_weight = Fraction(weights["positive" if row["label"] else "negative"])
            weight = round_places(class_weight * recency * multiplier, 6)
            spent = used.get(asset, Fraction(0))
            room = self.weight_cap - spent
            if room < 0:
                room = Fraction(0)
            if weight > room:
                weight = room
            used[asset] = spent + weight
            row["sample_weight"] = weight

    def _scores(self) -> dict:
        bias = self.upstream.number("score_bias")
        weights = {
            name: self.upstream.number("score_weight_%s" % name)
            for name in FEATURES
        }
        scores = {}
        for index, row in enumerate(self.rows):
            if row["split"] == "train":
                continue
            total = bias
            for name in FEATURES:
                value = row["z"][name]
                if value is not None:
                    total += weights[name] * value
            scores[index] = round_places(total, 6)
        return scores

    # -- the six files -----------------------------------------------------

    def train_ready(self) -> dict:
        rows = []
        for row in self.rows:
            rows.append(
                {
                    "asset_id": row["asset_id"],
                    "day": row["day"],
                    "split": row["split"],
                    "label": row["label"],
                    "z": {
                        name: (None if row["z"][name] is None else fmt_places(row["z"][name], 4))
                        for name in FEATURES
                    },
                    "sample_weight": fmt_places(row["sample_weight"], 6),
                }
            )
        return {"features": list(FEATURES), "rows": rows}

    def _split_scores(self, split: str) -> tuple[list, list]:
        scores, labels = [], []
        for index, row in enumerate(self.rows):
            if row["split"] == split:
                scores.append(self.scores[index])
                labels.append(row["label"])
        return scores, labels

    def baseline_metrics(self) -> dict:
        val_scores, val_labels = self._split_scores("val")
        test_scores, test_labels = self._split_scores("test")
        threshold = None
        best = None
        for candidate in sorted(set(val_scores), reverse=True):
            true_positive = false_positive = false_negative = 0
            for score, label in zip(val_scores, val_labels):
                if score >= candidate:
                    if label:
                        true_positive += 1
                    else:
                        false_positive += 1
                elif label:
                    false_negative += 1
            value = f_one(true_positive, false_positive, false_negative)
            if best is None or value > best:
                best = value
                threshold = candidate
        if threshold is None:
            threshold = Fraction(0)
            best = Fraction(0)
        counts = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
        for score, label in zip(test_scores, test_labels):
            if score >= threshold:
                counts["tp" if label else "fp"] += 1
            else:
                counts["fn" if label else "tn"] += 1
        precision_denominator = counts["tp"] + counts["fp"]
        recall_denominator = counts["tp"] + counts["fn"]
        precision = Fraction(counts["tp"], precision_denominator) if precision_denominator else Fraction(0)
        recall = Fraction(counts["tp"], recall_denominator) if recall_denominator else Fraction(0)
        return {
            "val": {
                "rows": len(val_scores),
                "positives": sum(val_labels),
                "auc": fmt_places(area_under_curve(val_scores, val_labels), 6),
                "threshold": fmt_places(threshold, 6),
                "f1": fmt_places(best, 6),
            },
            "test": {
                "rows": len(test_scores),
                "positives": sum(test_labels),
                "tp": counts["tp"],
                "fp": counts["fp"],
                "fn": counts["fn"],
                "tn": counts["tn"],
                "auc": fmt_places(area_under_curve(test_scores, test_labels), 6),
                "precision": fmt_places(precision, 6),
                "recall": fmt_places(recall, 6),
                "f1": fmt_places(f_one(counts["tp"], counts["fp"], counts["fn"]), 6),
            },
        }

    def drift_report(self) -> dict:
        features = {}
        for name in FEATURES:
            edges = [Fraction(edge) for edge in self.edges.get(name, [])]
            buckets = {"train": [0] * (len(edges) + 1), "test": [0] * (len(edges) + 1)}
            totals = {"train": 0, "test": 0}
            empty = {"train": 0, "test": 0}
            for label_row, feature_row in zip(self.labels, self.matrix):
                split = label_row["split"]
                if split not in buckets:
                    continue
                totals[split] += 1
                value = feature_row[name]
                if value is None:
                    empty[split] += 1
                    continue
                number = Fraction(str(value))
                position = 0
                for edge in edges:
                    if number > edge:
                        position += 1
                buckets[split][position] += 1
            psi = 0.0
            for index in range(len(edges) + 1):
                shares = {}
                for split in ("train", "test"):
                    filled = totals[split] - empty[split]
                    share = Fraction(buckets[split][index], filled) if filled else Fraction(0)
                    shares[split] = float(share) if share > 0 else 0.0001
                psi += (shares["test"] - shares["train"]) * math.log(shares["test"] / shares["train"])
            features[name] = {
                "psi": fmt_places(Fraction(psi), 6),
                "null_share_train": fmt_places(
                    Fraction(empty["train"], totals["train"]) if totals["train"] else Fraction(0), 6
                ),
                "null_share_test": fmt_places(
                    Fraction(empty["test"], totals["test"]) if totals["test"] else Fraction(0), 6
                ),
            }
        return {"features": features}

    def site_allocation(self) -> dict:
        regions = self.upstream.run["regions"]
        budget = self.upstream.integer("review_budget")
        site_cap = int(self.upstream.number("site_cap_share") * budget)
        region_cap = int(self.upstream.number("region_cap_share") * budget)
        positives = {site: 0 for site in regions}
        for row in self.rows:
            if row["split"] != "train" or not row["label"]:
                continue
            site = self.sites[(row["asset_id"], row["day"])]
            positives[site] = positives.get(site, 0) + 1
        total = sum(positives.values())
        quotas = {}
        for site, count in positives.items():
            quotas[site] = Fraction(budget * count, total) if total else Fraction(0)
        allocated = {site: 0 for site in positives}
        region_used = {}
        for site in sorted(positives, key=lambda s: (-quotas[s], s)):
            region = regions[site]
            whole = quotas[site].numerator // quotas[site].denominator
            room = min(site_cap, region_cap - region_used.get(region, 0))
            take = max(0, min(whole, room))
            allocated[site] = take
            region_used[region] = region_used.get(region, 0) + take
        remaining = budget - sum(allocated.values())
        order = sorted(
            (s for s in positives if positives[s] > 0),
            key=lambda s: (-(quotas[s] - (quotas[s].numerator // quotas[s].denominator)), s),
        )
        while remaining > 0:
            given = 0
            for site in order:
                if remaining == 0:
                    break
                region = regions[site]
                if allocated[site] >= site_cap or region_used.get(region, 0) >= region_cap:
                    continue
                allocated[site] += 1
                region_used[region] = region_used.get(region, 0) + 1
                remaining -= 1
                given += 1
            if given == 0:
                break
        sites = {}
        for site in sorted(positives):
            whole = quotas[site].numerator // quotas[site].denominator
            sites[site] = {
                "region": regions[site],
                "train_positives": positives[site],
                "allocated": allocated[site],
                "quota": fmt_places(quotas[site], 4),
                "capped": allocated[site] < whole,
            }
        return {
            "budget": budget,
            "site_cap": site_cap,
            "region_cap": region_cap,
            "unallocated": budget - sum(allocated.values()),
            "sites": sites,
        }

    def amendment_impact(self) -> dict:
        events = self.upstream.failures
        pending = 0
        confirmed = {}
        for row in events:
            status = row["status"]
            if row["pending_decision"]:
                pending += 1
                status = "confirmed" if row["pending_decision"] in ("confirm", "reclassify") else "unconfirmed"
            if status == "confirmed":
                confirmed.setdefault(row["asset_id"], set()).add(dt.date.fromisoformat(row["failed_day"]))
        changes = []
        by_split = {}
        for row in self.rows:
            day = dt.date.fromisoformat(row["day"])
            new_label = 0
            for failed in confirmed.get(row["asset_id"], ()):
                if day < failed <= day + dt.timedelta(days=self.horizon):
                    new_label = 1
                    break
            if new_label == row["label"]:
                continue
            changes.append(
                {
                    "asset_id": row["asset_id"],
                    "day": row["day"],
                    "split": row["split"],
                    "old_label": row["label"],
                    "new_label": new_label,
                }
            )
            bucket = by_split.setdefault(row["split"], {"flipped_up": 0, "flipped_down": 0})
            bucket["flipped_up" if new_label else "flipped_down"] += 1
        changes.sort(key=lambda change: (change["asset_id"], change["day"]))
        for split in sorted({row["split"] for row in self.rows}):
            by_split.setdefault(split, {"flipped_up": 0, "flipped_down": 0})
        return {
            "events_with_pending_amendment": pending,
            "label_changes": changes,
            "by_split": by_split,
        }

    def release_manifest(self) -> dict:
        counts = {}
        for row in self.rows:
            counts[row["split"]] = counts.get(row["split"], 0) + 1
        return {
            "run_id": self.upstream.run["run_id"],
            "files": dict(self.upstream.digests),
            "rows": {split: counts.get(split, 0) for split in ("train", "val", "test")},
            "features": list(FEATURES),
        }


def phase3(p1_dir: str, p2_dir: str, p3_dir: str):
    """Build the training rows and the reports of the release."""
    upstream = Upstream(p1_dir, p2_dir)
    builder = Phase3(upstream)
    lineage = upstream.lineage()
    documents = {
        "train_ready.json": builder.train_ready(),
        "baseline_metrics.json": builder.baseline_metrics(),
        "drift_report.json": builder.drift_report(),
        "site_allocation.json": builder.site_allocation(),
        "amendment_impact.json": builder.amendment_impact(),
        "release_manifest.json": builder.release_manifest(),
    }
    ensure_directory(p3_dir)
    for name, document in documents.items():
        document.update(lineage)
        write_json(os.path.join(p3_dir, name), document)


# --------------------------------------------------------------------------
# command line
# --------------------------------------------------------------------------

STAGES = {"phase1": 2, "phase2": 2, "phase3": 3}


def fail(message: str, status: int):
    sys.stderr.write("error: %s\n" % message)
    raise SystemExit(status)


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] not in STAGES:
        fail("usage: build.py phase1|phase2|phase3 DIRECTORIES", 2)
    stage = argv[1]
    directories = argv[2:]
    if len(directories) != STAGES[stage]:
        fail("%s takes %d directories" % (stage, STAGES[stage]), 2)
    for path in directories[:-1]:
        if not os.path.isdir(path) or not os.access(path, os.R_OK):
            fail("cannot read %s" % path, 3)
    try:
        if stage == "phase1":
            phase1(directories[0], directories[1])
        elif stage == "phase2":
            phase2(directories[0], directories[1])
        else:
            phase3(directories[0], directories[1], directories[2])
    except BuildError as error:
        fail(str(error), 3)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
