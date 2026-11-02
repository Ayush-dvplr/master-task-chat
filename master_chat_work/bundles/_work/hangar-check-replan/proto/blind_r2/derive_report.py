#!/usr/bin/env python3
"""Derive the season heavy-check plan and its reports.

Usage:
    python3 derive_report.py --data <data folder> --out <output folder>

Reads the data folder described in environment/docs/data_conventions.md and
writes check_plan.json, regions/region_<base>.json,
segments/segment_<segment>.json, plan_summary.json and data_quality.json
into the output folder.

Standard library only.
"""

import argparse
import bisect
import csv
import io
import json
import os
import re
import sys
import zipfile
from datetime import date, timedelta
import xml.etree.ElementTree as ET

BASES = ["North", "South", "West", "East"]
SEGMENTS = ["commercial", "public"]
CLASS_SEGMENT = {
    "widebody": "commercial",
    "narrowbody": "commercial",
    "regional": "public",
}
CLASS_ORDER = ["widebody", "narrowbody", "regional"]
REASONS = [
    "duplicate_request",
    "unknown_base",
    "unknown_check_type",
    "unknown_tail",
    "retired_tail",
    "bad_date",
    "bad_duration",
    "no_published_start",
]

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
INT_RE = re.compile(r"^[+-]?\d+$")

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
MC_NS = "http://schemas.openxmlformats.org/markup-compatibility/2006"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
OFFICE_DOC_REL = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
    "officeDocument"
)


class DataError(Exception):
    """Raised when an input file is missing or cannot be understood."""

    def __init__(self, path, detail):
        super().__init__("%s: %s" % (path, detail))
        self.path = path
        self.detail = detail


def parse_iso_date(text):
    """Return a date for a strict YYYY-MM-DD string, else None."""
    if text is None:
        return None
    text = text.strip()
    if not DATE_RE.match(text):
        return None
    try:
        return date(int(text[0:4]), int(text[5:7]), int(text[8:10]))
    except ValueError:
        return None


def parse_whole(text):
    """Return an int for a plain whole-number string, else None."""
    if text is None:
        return None
    text = text.strip()
    if not INT_RE.match(text):
        return None
    return int(text)


def read_text_file(path):
    try:
        with open(path, "r", encoding="utf-8-sig") as handle:
            return handle.read()
    except OSError as exc:
        raise DataError(path, "cannot be read (%s)" % exc.strerror)
    except UnicodeDecodeError as exc:
        raise DataError(path, "is not valid UTF-8 text (%s)" % exc)


# ---------------------------------------------------------------- TOML (tiny)


def load_toml(path):
    """Parse the small flat/one-level TOML used for fleet_limits.toml."""
    text = read_text_file(path)
    values = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            continue  # sections are flattened; keys are unique in this format
        if "=" not in line:
            raise DataError(path, "line %r is not a key = value pair" % raw)
        key, _, value = line.partition("=")
        key = key.strip().strip('"').strip("'")
        value = value.strip()
        if value[:1] in ('"', "'") and len(value) >= 2:
            quote = value[0]
            end = value.find(quote, 1)
            if end < 0:
                raise DataError(path, "unterminated string for key %r" % key)
            values[key] = value[1:end]
        else:
            cut = value.find("#")
            if cut >= 0:
                value = value[:cut]
            values[key] = value.strip()
    return values


# ---------------------------------------------------------------- DOCX reader


class _DocxPart(object):
    """A parsed WordprocessingML part plus the namespace scope of each node."""

    def __init__(self, root, scopes):
        self.root = root
        self.scopes = scopes

    def scope_of(self, elem):
        return self.scopes.get(id(elem), {})


def _parse_part(path, name, data):
    """Parse XML keeping track of the namespace prefixes in scope per node."""
    try:
        parser = ET.iterparse(
            io.BytesIO(data), events=("start-ns", "start", "end")
        )
        pending = []
        stack = []
        scopes = {}
        root = None
        for event, payload in parser:
            if event == "start-ns":
                pending.append(payload)
            elif event == "start":
                parent_scope = stack[-1] if stack else {}
                if pending:
                    scope = dict(parent_scope)
                    for prefix, uri in pending:
                        scope[prefix] = uri
                    pending = []
                else:
                    scope = parent_scope
                scopes[id(payload)] = scope
                stack.append(scope)
            else:
                stack.pop()
                root = payload
    except ET.ParseError as exc:
        raise DataError(path, "part %s is not valid XML (%s)" % (name, exc))
    if root is None:
        raise DataError(path, "part %s is empty" % name)
    return _DocxPart(root, scopes)


def _zip_part(path, archive, name):
    try:
        return archive.read(name)
    except KeyError:
        raise DataError(path, "is missing the part %s" % name)
    except (zipfile.BadZipFile, OSError) as exc:
        raise DataError(path, "part %s cannot be read (%s)" % (name, exc))


def load_docx_tables(path):
    """Return the list of tables of a .docx as lists of rows of cell texts."""
    if not os.path.isfile(path):
        raise DataError(path, "is missing")
    try:
        archive = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as exc:
        raise DataError(path, "is not a readable Word package (%s)" % exc)
    try:
        rels = _parse_part(path, "_rels/.rels", _zip_part(path, archive, "_rels/.rels"))
        target = None
        for rel in rels.root:
            if rel.tag != "{%s}Relationship" % PKG_REL_NS:
                continue
            if rel.get("Type") == OFFICE_DOC_REL:
                target = rel.get("Target")
                break
        if not target:
            raise DataError(path, "has no officeDocument relationship")
        if target.startswith("/"):
            target = target[1:]
        name = os.path.normpath(target).replace(os.sep, "/")
        doc = _parse_part(path, name, _zip_part(path, archive, name))
        return _tables_of(doc)
    finally:
        archive.close()


def _requires_understood(elem, part):
    """True when every prefix of @Requires maps to the main w namespace."""
    requires = elem.get("Requires")
    if requires is None:
        return False
    scope = part.scope_of(elem)
    tokens = [token for token in requires.replace(",", " ").split() if token]
    if not tokens:
        return False
    for token in tokens:
        if scope.get(token) != W_NS:
            return False
    return True


def _eff_children(elem, part):
    """Children of elem after applying revisions and markup compatibility."""
    out = []
    for child in list(elem):
        tag = child.tag
        if tag in ("{%s}del" % W_NS, "{%s}moveFrom" % W_NS):
            continue
        if tag in ("{%s}ins" % W_NS, "{%s}moveTo" % W_NS):
            out.extend(_eff_children(child, part))
            continue
        if tag == "{%s}AlternateContent" % MC_NS:
            chosen = None
            for branch in list(child):
                if branch.tag == "{%s}Choice" % MC_NS and _requires_understood(
                    branch, part
                ):
                    chosen = branch
                    break
            if chosen is None:
                for branch in list(child):
                    if branch.tag == "{%s}Fallback" % MC_NS:
                        chosen = branch
                        break
            if chosen is not None:
                out.extend(_eff_children(chosen, part))
            continue
        out.append(child)
    return out


def _eff_descendants(elem, part, tag):
    """All effective descendants of elem with the given tag (outermost only)."""
    found = []
    for child in _eff_children(elem, part):
        if child.tag == tag:
            found.append(child)
        else:
            found.extend(_eff_descendants(child, part, tag))
    return found


def _eff_text(elem, part):
    pieces = []

    def walk(node):
        for child in _eff_children(node, part):
            tag = child.tag
            if tag == "{%s}t" % W_NS:
                pieces.append(child.text or "")
            elif tag == "{%s}tab" % W_NS:
                pieces.append("\t")
            elif tag in ("{%s}br" % W_NS, "{%s}cr" % W_NS):
                pieces.append("\n")
            else:
                walk(child)

    walk(elem)
    return "".join(pieces)


def _tables_of(part):
    tables = []
    for tbl in _eff_descendants(part.root, part, "{%s}tbl" % W_NS):
        rows = []
        for tr in _eff_children(tbl, part):
            if tr.tag != "{%s}tr" % W_NS:
                continue
            cells = [
                _eff_text(tc, part).strip()
                for tc in _eff_children(tr, part)
                if tc.tag == "{%s}tc" % W_NS
            ]
            rows.append(cells)
        tables.append(rows)
    return tables


def table_by_first_header(path, tables, header):
    """Return the table whose first header cell equals header, as dict rows."""
    for rows in tables:
        if not rows or not rows[0]:
            continue
        if rows[0][0].strip().lower() != header.lower():
            continue
        keys = [cell.strip() for cell in rows[0]]
        out = []
        for cells in rows[1:]:
            record = {}
            for index, key in enumerate(keys):
                record[key] = cells[index].strip() if index < len(cells) else ""
            out.append(record)
        return keys, out
    raise DataError(path, "has no table whose first header cell is %r" % header)


# ------------------------------------------------------------- input loading


def _open_csv(path):
    if not os.path.isfile(path):
        raise DataError(path, "is missing")
    try:
        handle = open(path, "r", encoding="utf-8-sig", newline="")
    except OSError as exc:
        raise DataError(path, "cannot be read (%s)" % exc.strerror)
    return handle


def _read_csv_rows(path, required):
    """Read a CSV into (line_number, row dict) pairs; header is line 1."""
    handle = _open_csv(path)
    try:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise DataError(path, "is empty")
        names = [(name or "").strip() for name in reader.fieldnames]
        reader.fieldnames = names
        missing = [name for name in required if name not in names]
        if missing:
            raise DataError(path, "has no column %s" % ", ".join(missing))
        rows = []
        try:
            for row in reader:
                rows.append((reader.line_num, row))
        except csv.Error as exc:
            raise DataError(path, "is not valid CSV (%s)" % exc)
        except UnicodeDecodeError as exc:
            raise DataError(path, "is not valid UTF-8 text (%s)" % exc)
        return rows
    finally:
        handle.close()


def _whole_from(path, text, what):
    value = parse_whole(text)
    if value is None:
        raise DataError(path, "has a non-numeric %s (%r)" % (what, text))
    return value


def load_inputs(data_dir):
    """Load every input file; raise DataError naming the offending file."""
    data = {}
    path = os.path.join(data_dir, "fleet_limits.toml")
    if not os.path.isfile(path):
        raise DataError(path, "is missing")
    limits = load_toml(path)
    for key in ("season", "season_start", "season_end"):
        if key not in limits:
            raise DataError(path, "has no %s" % key)
    season = limits["season"]
    season_start = parse_iso_date(limits["season_start"])
    season_end = parse_iso_date(limits["season_end"])
    if season_start is None:
        raise DataError(path, "has an invalid season_start")
    if season_end is None:
        raise DataError(path, "has an invalid season_end")
    if season_end < season_start:
        raise DataError(path, "has season_end before season_start")
    data["season"] = season
    data["season_start"] = season_start
    data["season_end"] = season_end
    data["days"] = (season_end - season_start).days + 1

    path = os.path.join(data_dir, "fleet_register.csv")
    tails = {}
    for _, row in _read_csv_rows(path, ("tail", "aircraft_class", "status")):
        tail = (row.get("tail") or "").strip()
        if not tail or tail in tails:
            continue
        tails[tail] = (
            (row.get("aircraft_class") or "").strip(),
            (row.get("status") or "").strip(),
        )
    data["tails"] = tails

    path = os.path.join(data_dir, "check_types.json")
    if not os.path.isfile(path):
        raise DataError(path, "is missing")
    try:
        raw_types = json.loads(read_text_file(path))
    except ValueError as exc:
        raise DataError(path, "is not valid JSON (%s)" % exc)
    if not isinstance(raw_types, dict):
        raise DataError(path, "is not a JSON object of check types")
    check_types = {}
    for name, spec in raw_types.items():
        if not isinstance(spec, dict):
            raise DataError(path, "has a malformed entry for %r" % name)
        try:
            check_types[name] = (
                int(spec["max_compress_days"]),
                int(spec["overtime_shifts_per_day"]),
            )
        except (KeyError, TypeError, ValueError):
            raise DataError(path, "has a malformed entry for %r" % name)
    data["check_types"] = check_types

    path = os.path.join(data_dir, "published_plan.csv")
    published = {}
    for _, row in _read_csv_rows(path, ("request_id", "published_start")):
        request_id = (row.get("request_id") or "").strip()
        if not request_id or request_id in published:
            continue
        published[request_id] = (row.get("published_start") or "").strip()
    data["published"] = published

    path = os.path.join(data_dir, "base_calendar.jsonl")
    if not os.path.isfile(path):
        raise DataError(path, "is missing")
    calendar = {}
    text = read_text_file(path)
    for number, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except ValueError as exc:
            raise DataError(path, "line %d is not valid JSON (%s)" % (number, exc))
        if not isinstance(record, dict):
            raise DataError(path, "line %d is not a JSON object" % number)
        base = str(record.get("base", "")).strip()
        day = parse_iso_date(str(record.get("date", "")))
        status = str(record.get("status", "")).strip()
        if day is None or not base:
            continue
        if day < season_start or day > season_end:
            continue
        calendar[(base, day)] = status
    data["calendar"] = calendar

    path = os.path.join(data_dir, "disruption_notice.docx")
    tables = load_docx_tables(path)
    closures = []
    _, rows = table_by_first_header(path, tables, "base")
    for row in rows:
        base = (row.get("base") or "").strip()
        if not base:
            continue
        start = parse_iso_date(row.get("from") or "")
        if start is None:
            raise DataError(path, "has a closure row with an invalid from date")
        length = _whole_from(path, row.get("days"), "closure length")
        closures.append((base, start, length))
    notice_avail = {}
    _, rows = table_by_first_header(path, tables, "tail")
    for row in rows:
        tail = (row.get("tail") or "").strip()
        if not tail:
            continue
        day = parse_iso_date(row.get("available_from") or "")
        if day is None:
            raise DataError(path, "has a tail row with an invalid available_from")
        notice_avail[tail] = day
    data["closures"] = closures
    data["notice_avail"] = notice_avail

    path = os.path.join(data_dir, "planning_limits.docx")
    tables = load_docx_tables(path)
    _, rows = table_by_first_header(path, tables, "item")
    items = {}
    for row in rows:
        name = (row.get("item") or "").strip()
        if not name:
            continue
        items[name] = _whole_from(path, row.get("value"), "value for " + name)
    for key in ("overtime_pool_shifts", "shift_cost"):
        if key not in items:
            raise DataError(path, "has no %s row" % key)
    data["overtime_pool_shifts"] = items["overtime_pool_shifts"]
    data["shift_cost"] = items["shift_cost"]

    _, rows = table_by_first_header(path, tables, "class")
    class_params = {}
    for row in rows:
        name = (row.get("class") or "").strip()
        if not name:
            continue
        class_params[name] = {
            "revenue_per_day": _whole_from(
                path, row.get("revenue_per_day"), "revenue_per_day"
            ),
            "overdue_weight": _whole_from(
                path, row.get("overdue_weight"), "overdue_weight"
            ),
            "deferral_penalty": _whole_from(
                path, row.get("deferral_penalty"), "deferral_penalty"
            ),
        }
    data["class_params"] = class_params

    _, rows = table_by_first_header(path, tables, "base")
    allowances = {}
    for row in rows:
        name = (row.get("base") or "").strip()
        if not name:
            continue
        allowances[name] = _whole_from(
            path, row.get("allowance_shifts"), "allowance_shifts"
        )
    data["allowances"] = allowances

    path = os.path.join(data_dir, "check_requests.csv")
    data["request_rows"] = _read_csv_rows(
        path,
        (
            "request_id",
            "season",
            "tail",
            "check_type",
            "base",
            "available_from",
            "due_date",
            "duration_days",
            "status",
        ),
    )
    return data


def screen_requests(data):
    """Split the in-season open rows into accepted requests and rejections."""
    season = data["season"]
    tails = data["tails"]
    check_types = data["check_types"]
    published = data["published"]
    season_start = data["season_start"]
    seen = set()
    accepted = []
    rejected = []
    for line, row in data["request_rows"]:
        request_id = (row.get("request_id") or "").strip()
        row_season = (row.get("season") or "").strip()
        status = (row.get("status") or "").strip()
        if row_season != season or status != "OPEN":
            seen.add(request_id)
            continue
        base = (row.get("base") or "").strip()
        check_type = (row.get("check_type") or "").strip()
        tail = (row.get("tail") or "").strip()
        available_text = (row.get("available_from") or "").strip()
        due_text = (row.get("due_date") or "").strip()
        duration_text = (row.get("duration_days") or "").strip()
        available = parse_iso_date(available_text)
        due = parse_iso_date(due_text)
        duration = parse_whole(duration_text)
        reason = None
        if request_id in seen:
            reason = "duplicate_request"
        elif base not in BASES:
            reason = "unknown_base"
        elif check_type not in check_types:
            reason = "unknown_check_type"
        elif tail not in tails:
            reason = "unknown_tail"
        elif tails[tail][1] != "ACTIVE":
            reason = "retired_tail"
        elif available is None or due is None:
            reason = "bad_date"
        elif duration is None or duration < 1:
            reason = "bad_duration"
        elif request_id not in published:
            reason = "no_published_start"
        seen.add(request_id)
        if reason is not None:
            rejected.append(
                {"request_id": request_id, "line": line, "reason": reason}
            )
            continue
        aircraft_class = tails[tail][0]
        effective = data["notice_avail"].get(tail, available)
        if effective < season_start:
            effective = season_start
        accepted.append(
            {
                "request_id": request_id,
                "tail": tail,
                "base": base,
                "check_type": check_type,
                "aircraft_class": aircraft_class,
                "segment": CLASS_SEGMENT.get(aircraft_class),
                "available": effective,
                "due": due,
                "duration": duration,
                "published_start": published[request_id],
            }
        )
    accepted.sort(key=lambda item: item["request_id"])
    return accepted, rejected


# ------------------------------------------------------------- base calendars


class BaseLine(object):
    """The closed / no-start days of one base line, with window lookups."""

    def __init__(self, days, closed, nostart):
        self.days = days
        self.closed = closed
        self.nostart = nostart
        self.can_start = [
            index >= 1 and not closed[index] and not nostart[index]
            for index in range(days + 2)
        ]
        self.can_start[0] = False
        prefix = [0] * (days + 2)
        for index in range(1, days + 1):
            prefix[index] = prefix[index - 1] + (1 if closed[index] else 0)
        prefix[days + 1] = prefix[days]
        self._closed_prefix = prefix
        self._ok = {}
        self._next = {}

    def ok_window(self, length):
        table = self._ok.get(length)
        if table is None:
            days = self.days
            prefix = self._closed_prefix
            table = [False] * (days + 2)
            for start in range(1, days + 2):
                finish = start + length - 1
                if finish > days:
                    break
                if not self.can_start[start]:
                    continue
                if prefix[finish] - prefix[start - 1] == 0:
                    table[start] = True
            self._ok[length] = table
        return table

    def next_start(self, length, earliest):
        """Smallest valid start >= earliest for a window of the given length."""
        table = self._next.get(length)
        if table is None:
            ok = self.ok_window(length)
            days = self.days
            table = [None] * (days + 3)
            following = None
            for start in range(days + 1, 0, -1):
                if start <= days and ok[start]:
                    following = start
                table[start] = following
            table[days + 2] = None
            self._next[length] = table
        if earliest < 1:
            earliest = 1
        if earliest > self.days + 2:
            return None
        return table[earliest]


def build_base_lines(data):
    days = data["days"]
    season_start = data["season_start"]
    season_end = data["season_end"]
    calendar = data["calendar"]
    lines = {}
    for base in BASES:
        closed = [False] * (days + 2)
        nostart = [False] * (days + 2)
        for offset in range(days):
            day = season_start + timedelta(days=offset)
            status = calendar.get((base, day), "OPEN")
            if status == "CLOSED":
                closed[offset + 1] = True
            elif status == "NO_START":
                nostart[offset + 1] = True
        for closure_base, start, length in data["closures"]:
            if closure_base != base or length < 1:
                continue
            for offset in range(length):
                day = start + timedelta(days=offset)
                if day < season_start or day > season_end:
                    continue
                closed[(day - season_start).days + 1] = True
        lines[base] = BaseLine(days, closed, nostart)
    return lines


# ------------------------------------------------------------------- planning


def build_objective(requests, data):
    """Weights that fold the lexicographic plan order into one integer.

    Term order is first, second, third, then the start-day list and the
    finish-day list in request_id order; each level is given a radix larger
    than any possible sum of the levels below it, so the integer compares
    exactly like the documented tuple and stays additive per request.
    """
    days = data["days"]
    count = len(requests)
    radix = 1 << max(11, (days + 2).bit_length() + 1)
    positions = 2 * count
    powers = [1] * (positions + 1)
    for index in range(1, positions + 1):
        powers[index] = powers[index - 1] * radix
    start_weight = [powers[positions - 1 - index] for index in range(count)]
    finish_weight = [powers[count - 1 - index] for index in range(count)]
    third = powers[positions]
    second = third * (1 << (max(1, count).bit_length() + 1))
    bound = 1
    shift_cost = data["shift_cost"]
    for request in requests:
        params = data["class_params"].get(request["aircraft_class"], {})
        revenue = params.get("revenue_per_day", 0)
        max_compress = data["check_types"][request["check_type"]][0]
        shifts_per_day = data["check_types"][request["check_type"]][1]
        bound += request["duration"] * max(0, revenue)
        bound += shift_cost * max_compress * max(0, shifts_per_day)
    first = second * (1 << (bound.bit_length() + 1))
    return {
        "start_weight": start_weight,
        "finish_weight": finish_weight,
        "first": first,
        "second": second,
        "third": third,
    }


def prepare_requests(requests, data):
    season_start = data["season_start"]
    days = data["days"]
    for index, request in enumerate(requests):
        request["index"] = index
        request["available_idx"] = max(
            1, (request["available"] - season_start).days + 1
        )
        request["due_idx"] = (request["due"] - season_start).days + 1
        published = parse_iso_date(request["published_start"])
        published_idx = None
        if published is not None:
            offset = (published - season_start).days + 1
            if 1 <= offset <= days:
                published_idx = offset
        request["published_idx"] = published_idx
        max_compress, shifts_per_day = data["check_types"][request["check_type"]]
        request["max_compress"] = max(0, min(max_compress, request["duration"] - 1))
        request["shifts_per_day"] = shifts_per_day
        params = data["class_params"].get(request["aircraft_class"])
        if params is None:
            params = {
                "revenue_per_day": 0,
                "overdue_weight": 0,
                "deferral_penalty": 0,
            }
        request["revenue_per_day"] = params["revenue_per_day"]
        request["overdue_weight"] = params["overdue_weight"]
        request["deferral_penalty"] = params["deferral_penalty"]


def scheduled_cost(request, start, compress, weights, shift_cost, index):
    ground = request["duration"] - compress
    finish = start + ground - 1
    overdue = finish - request["due_idx"]
    if overdue < 0:
        overdue = 0
    shifts = compress * request["shifts_per_day"]
    moved = 1 if start != request["published_idx"] else 0
    total = overdue * request["overdue_weight"] * weights["first"]
    total += (
        ground * request["revenue_per_day"] + shift_cost * shifts
    ) * weights["second"]
    total += moved * weights["third"]
    total += start * weights["start_weight"][index]
    total += finish * weights["finish_weight"][index]
    return total, finish, shifts


def deferred_cost(request, weights, days, index):
    sentinel = days + 1
    total = request["deferral_penalty"] * weights["first"]
    total += weights["third"]
    total += sentinel * weights["start_weight"][index]
    total += sentinel * weights["finish_weight"][index]
    return total


def prune_states(bucket):
    """Drop states dominated on (last finish day, shifts used, folded cost).

    The remaining requests of the mask see the state only through those three
    numbers, and every later contribution is additive, so a state beaten on
    all three can never lead to a better plan.
    """
    entries = []
    for finish, by_shifts in bucket.items():
        for shifts, value in by_shifts.items():
            entries.append((finish, shifts, value[0], value[1]))
    if len(entries) < 2:
        return
    entries.sort(key=lambda item: (item[0], item[1], item[2]))
    keys = []
    costs = []
    kept = {}
    for finish, shifts, cost, back in entries:
        position = bisect.bisect_right(keys, shifts) - 1
        if position >= 0 and costs[position] <= cost:
            continue
        insert = bisect.bisect_left(keys, shifts)
        if insert < len(keys) and keys[insert] == shifts:
            keys[insert] = shifts
            costs[insert] = cost
        else:
            keys.insert(insert, shifts)
            costs.insert(insert, cost)
        index = insert + 1
        while index < len(keys) and costs[index] >= cost:
            del keys[index]
            del costs[index]
        kept.setdefault(finish, {})[shifts] = (cost, back)
    bucket.clear()
    bucket.update(kept)


def plan_base(base_requests, line, weights, data):
    """Best plan of one base line for every feasible total of overtime shifts.

    Returns {shifts: (cost, decisions)} where the cost is already the folded
    lexicographic integer including the deferral of every request of this base
    that the plan leaves out.
    """
    days = data["days"]
    shift_cost = data["shift_cost"]
    count = len(base_requests)
    full = 1 << count
    states = [None] * full
    states[0] = {0: {0: (0, None)}}
    for mask in range(full):
        bucket = states[mask]
        if not bucket:
            continue
        prune_states(bucket)
        for finish, by_shifts in bucket.items():
            for shifts, (cost, _) in by_shifts.items():
                for slot, request in enumerate(base_requests):
                    bit = 1 << slot
                    if mask & bit:
                        continue
                    earliest = finish + 1
                    if earliest < request["available_idx"]:
                        earliest = request["available_idx"]
                    for compress in range(request["max_compress"] + 1):
                        length = request["duration"] - compress
                        candidates = []
                        first_start = line.next_start(length, earliest)
                        if first_start is None:
                            continue
                        candidates.append(first_start)
                        published_idx = request["published_idx"]
                        if (
                            published_idx is not None
                            and published_idx > first_start
                            and line.ok_window(length)[published_idx]
                        ):
                            candidates.append(published_idx)
                        for start in candidates:
                            delta, new_finish, used = scheduled_cost(
                                request,
                                start,
                                compress,
                                weights,
                                shift_cost,
                                request["index"],
                            )
                            new_mask = mask | bit
                            new_shifts = shifts + used
                            target = states[new_mask]
                            if target is None:
                                target = {}
                                states[new_mask] = target
                            slots = target.get(new_finish)
                            if slots is None:
                                slots = {}
                                target[new_finish] = slots
                            entry = (
                                cost + delta,
                                (mask, finish, shifts, slot, start, compress),
                            )
                            old = slots.get(new_shifts)
                            if old is None or entry[0] < old[0]:
                                slots[new_shifts] = entry
    best = {}
    for mask in range(full):
        bucket = states[mask]
        if not bucket:
            continue
        missing = 0
        for slot, request in enumerate(base_requests):
            if not mask & (1 << slot):
                missing += deferred_cost(
                    request, weights, days, request["index"]
                )
        for finish, by_shifts in bucket.items():
            for shifts, (cost, _) in by_shifts.items():
                total = cost + missing
                current = best.get(shifts)
                if current is None or total < current[0]:
                    best[shifts] = (total, mask, finish)
    return states, best


def reconstruct(states, mask, finish, shifts):
    picks = []
    while True:
        entry = states[mask][finish][shifts]
        back = entry[1]
        if back is None:
            break
        prev_mask, prev_finish, prev_shifts, slot, start, compress = back
        picks.append((slot, start, compress))
        mask, finish, shifts = prev_mask, prev_finish, prev_shifts
    picks.reverse()
    return picks


def combine_bases(per_base, pool):
    """Spread the one fleet overtime pool over the four base lines."""
    current = {0: (0, ())}
    for best in per_base:
        following = {}
        for used, (cost, allocation) in current.items():
            for extra, entry in best.items():
                total = used + extra
                if total > pool:
                    continue
                combined = cost + entry[0]
                previous = following.get(total)
                if previous is None or combined < previous[0]:
                    following[total] = (combined, allocation + (extra,))
        current = following
        if not current:
            return None
    chosen = None
    for used, (cost, allocation) in current.items():
        if chosen is None or cost < chosen[0]:
            chosen = (cost, allocation, used)
    return chosen


def solve(requests, lines, data):
    weights = build_objective(requests, data)
    prepare_requests(requests, data)
    pool = max(0, data["overtime_pool_shifts"])
    per_base = []
    for base in BASES:
        base_requests = [item for item in requests if item["base"] == base]
        states, best = plan_base(base_requests, lines[base], weights, data)
        trimmed = {}
        for shifts, entry in best.items():
            if shifts <= pool:
                trimmed[shifts] = entry
        per_base.append((base, base_requests, states, trimmed))
    chosen = combine_bases([item[3] for item in per_base], pool)
    if chosen is None:
        raise DataError(
            os.path.join(data["data_dir"], "check_requests.csv"),
            "has no plan that respects the overtime pool",
        )
    _, allocation, _ = chosen
    decisions = {}
    for slot_index, (base, base_requests, states, trimmed) in enumerate(per_base):
        shifts = allocation[slot_index]
        _, mask, finish = trimmed[shifts]
        line = lines[base]
        scheduled = set()
        for slot, start, compress in reconstruct(states, mask, finish, shifts):
            request = base_requests[slot]
            scheduled.add(slot)
            ground = request["duration"] - compress
            finish_idx = start + ground - 1
            overdue = max(0, finish_idx - request["due_idx"])
            decisions[request["request_id"]] = {
                "request": request,
                "decision": "scheduled",
                "start_idx": start,
                "finish_idx": finish_idx,
                "compress_days": compress,
                "overtime_shifts": compress * request["shifts_per_day"],
                "overdue_days": overdue,
                "days_on_ground": ground,
                "moved": start != request["published_idx"],
                "deferral_reason": None,
            }
        for slot, request in enumerate(base_requests):
            if slot in scheduled:
                continue
            fits = False
            for compress in range(request["max_compress"] + 1):
                length = request["duration"] - compress
                if line.next_start(length, request["available_idx"]) is not None:
                    fits = True
                    break
            decisions[request["request_id"]] = {
                "request": request,
                "decision": "deferred",
                "start_idx": None,
                "finish_idx": None,
                "compress_days": 0,
                "overtime_shifts": 0,
                "overdue_days": 0,
                "days_on_ground": 0,
                "moved": True,
                "deferral_reason": "plan_trade" if fits else "no_slot",
            }
    return decisions


# ----------------------------------------------------------------- settlement


def settle(decisions, data):
    """Spend the one fleet allowance over the scheduled checks in order."""
    shift_cost = data["shift_cost"]
    granted = 0
    for base in BASES:
        granted += max(0, data["allowances"].get(base, 0))
    order = [
        item
        for item in decisions.values()
        if item["decision"] == "scheduled"
    ]
    order.sort(
        key=lambda item: (
            CLASS_ORDER.index(item["request"]["aircraft_class"])
            if item["request"]["aircraft_class"] in CLASS_ORDER
            else len(CLASS_ORDER),
            item["request"]["due"],
            item["request"]["request_id"],
        )
    )
    left = granted
    for item in decisions.values():
        item["allowance_shifts"] = 0
        item["paid_shifts"] = 0
        item["overtime_cost"] = 0
        item["allowance_credit"] = 0
        item["settled_overtime_cost"] = 0
    for item in order:
        shifts = item["overtime_shifts"]
        taken = min(shifts, left)
        left -= taken
        item["allowance_shifts"] = taken
        item["paid_shifts"] = shifts - taken
        item["overtime_cost"] = shift_cost * shifts
        item["allowance_credit"] = shift_cost * taken
        item["settled_overtime_cost"] = item["overtime_cost"] - item[
            "allowance_credit"
        ]
    return granted, granted - left, left


# -------------------------------------------------------------------- reports


def day_to_iso(season_start, index):
    if index is None:
        return None
    return (season_start + timedelta(days=index - 1)).isoformat()


def group_report(items, season_start, fleet_overtime_used):
    scheduled = [item for item in items if item["decision"] == "scheduled"]
    deferred = [item for item in items if item["decision"] == "deferred"]
    starts = [item["start_idx"] for item in scheduled]
    finishes = [item["finish_idx"] for item in scheduled]
    report = {
        "checks_scheduled": len(scheduled),
        "checks_deferred": len(deferred),
        "compress_days": sum(item["compress_days"] for item in scheduled),
        "overtime_shifts": sum(item["overtime_shifts"] for item in scheduled),
        "overdue_days": sum(item["overdue_days"] for item in scheduled),
        "overdue_cost": sum(
            item["overdue_days"] * item["request"]["overdue_weight"]
            for item in scheduled
        ),
        "deferral_cost": sum(
            item["request"]["deferral_penalty"] for item in deferred
        ),
        "revenue_lost": sum(
            item["days_on_ground"] * item["request"]["revenue_per_day"]
            for item in scheduled
        ),
        "moved": sum(1 for item in items if item["moved"]),
        "first_start": day_to_iso(season_start, min(starts)) if starts else None,
        "last_finish": day_to_iso(season_start, max(finishes))
        if finishes
        else None,
        "fleet_overtime_used": fleet_overtime_used,
        "overtime_cost": sum(item["overtime_cost"] for item in scheduled),
        "allowance_credit": sum(item["allowance_credit"] for item in scheduled),
        "settled_overtime_cost": sum(
            item["settled_overtime_cost"] for item in scheduled
        ),
        "allowance_used": sum(item["allowance_shifts"] for item in scheduled),
    }
    return report


def write_json(out_dir, name, payload):
    path = os.path.join(out_dir, name)
    directory = os.path.dirname(path)
    if directory and not os.path.isdir(directory):
        os.makedirs(directory)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=False)
        handle.write("\n")


def write_reports(requests, decisions, rejected, data, out_dir):
    season_start = data["season_start"]
    ordered = [decisions[item["request_id"]] for item in requests]
    fleet_overtime_used = sum(
        item["overtime_shifts"] for item in ordered
    )
    granted, used, left = settle(decisions, data)

    checks = []
    for item in ordered:
        request = item["request"]
        checks.append(
            {
                "request_id": request["request_id"],
                "tail": request["tail"],
                "base": request["base"],
                "check_type": request["check_type"],
                "aircraft_class": request["aircraft_class"],
                "segment": request["segment"],
                "decision": item["decision"],
                "start_date": day_to_iso(season_start, item["start_idx"]),
                "finish_date": day_to_iso(season_start, item["finish_idx"]),
                "compress_days": item["compress_days"],
                "overtime_shifts": item["overtime_shifts"],
                "overdue_days": item["overdue_days"],
                "moved": bool(item["moved"]),
                "deferral_reason": item["deferral_reason"],
                "overtime_cost": item["overtime_cost"],
                "allowance_shifts": item["allowance_shifts"],
                "paid_shifts": item["paid_shifts"],
                "allowance_credit": item["allowance_credit"],
                "settled_overtime_cost": item["settled_overtime_cost"],
            }
        )
    write_json(out_dir, "check_plan.json", {"season": data["season"], "checks": checks})

    region_reports = {}
    for base in BASES:
        items = [item for item in ordered if item["request"]["base"] == base]
        report = group_report(items, season_start, fleet_overtime_used)
        report["allowance_granted"] = max(0, data["allowances"].get(base, 0))
        payload = {"base": base}
        payload.update(report)
        region_reports[base] = payload
        write_json(
            out_dir,
            os.path.join("regions", "region_%s.json" % base.lower()),
            payload,
        )

    segment_reports = {}
    for segment in SEGMENTS:
        items = [item for item in ordered if item["request"]["segment"] == segment]
        report = group_report(items, season_start, fleet_overtime_used)
        payload = {"segment": segment}
        payload.update(report)
        segment_reports[segment] = payload
        write_json(
            out_dir,
            os.path.join("segments", "segment_%s.json" % segment),
            payload,
        )

    scheduled = [item for item in ordered if item["decision"] == "scheduled"]
    deferred = [item for item in ordered if item["decision"] == "deferred"]
    first_term = sum(
        item["overdue_days"] * item["request"]["overdue_weight"]
        for item in scheduled
    ) + sum(item["request"]["deferral_penalty"] for item in deferred)
    second_term = sum(
        item["days_on_ground"] * item["request"]["revenue_per_day"]
        for item in scheduled
    ) + data["shift_cost"] * fleet_overtime_used
    third_term = sum(1 for item in ordered if item["moved"])
    summary = {
        "season": data["season"],
        "plan_terms": {
            "first": first_term,
            "second": second_term,
            "third": third_term,
        },
        "overtime_pool_shifts": data["overtime_pool_shifts"],
        "fleet_overtime_used": fleet_overtime_used,
        "checks_scheduled": len(scheduled),
        "checks_deferred": len(deferred),
        "moved": third_term,
        "settlement": {
            "allowance_granted": granted,
            "allowance_used": used,
            "allowance_left": left,
            "overtime_cost": sum(item["overtime_cost"] for item in ordered),
            "allowance_credit": sum(item["allowance_credit"] for item in ordered),
            "settled_overtime_cost": sum(
                item["settled_overtime_cost"] for item in ordered
            ),
        },
        "bases": [
            {
                "base": base,
                "checks_scheduled": region_reports[base]["checks_scheduled"],
                "checks_deferred": region_reports[base]["checks_deferred"],
                "overtime_shifts": region_reports[base]["overtime_shifts"],
                "allowance_granted": region_reports[base]["allowance_granted"],
                "allowance_used": region_reports[base]["allowance_used"],
                "settled_overtime_cost": region_reports[base][
                    "settled_overtime_cost"
                ],
            }
            for base in BASES
        ],
        "segments": [
            {
                "segment": segment,
                "checks_scheduled": segment_reports[segment]["checks_scheduled"],
                "checks_deferred": segment_reports[segment]["checks_deferred"],
            }
            for segment in SEGMENTS
        ],
    }
    write_json(out_dir, "plan_summary.json", summary)

    counts = dict((reason, 0) for reason in REASONS)
    for item in rejected:
        counts[item["reason"]] = counts.get(item["reason"], 0) + 1
    write_json(
        out_dir,
        "data_quality.json",
        {"rejected": rejected, "counts": counts},
    )
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Derive the season heavy-check plan and its reports."
    )
    parser.add_argument("--data", default="/app/environment/data/")
    parser.add_argument("--out", default="/app/out/")
    args = parser.parse_args(argv)
    data_dir = args.data
    out_dir = args.out
    try:
        if not os.path.isdir(data_dir):
            raise DataError(data_dir, "is not a readable data folder")
        data = load_inputs(data_dir)
        data["data_dir"] = data_dir
        requests, rejected = screen_requests(data)
        lines = build_base_lines(data)
        decisions = solve(requests, lines, data)
        if not os.path.isdir(out_dir):
            os.makedirs(out_dir)
        write_reports(requests, decisions, rejected, data, out_dir)
    except DataError as exc:
        sys.stderr.write("derive_report: %s\n" % exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
