#!/usr/bin/env python3
"""Heavy hangar check replan.

Reads the data folder described in environment/docs/data_conventions.md and writes the
optimal season plan documents described in environment/docs/output_schema.md.

Usage:
    python3 derive_report.py --data <data folder> --out <output folder>

Standard library only.
"""

import argparse
import csv
import datetime
import json
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

BASES = ["North", "South", "West", "East"]
SEGMENT_OF_CLASS = {
    "widebody": "commercial",
    "narrowbody": "commercial",
    "regional": "public",
}
SEGMENTS = ["commercial", "public"]
REJECT_REASONS = [
    "duplicate_request",
    "unknown_base",
    "unknown_check_type",
    "unknown_tail",
    "retired_tail",
    "bad_date",
    "bad_duration",
    "no_published_start",
]

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
MC_NS = "http://schemas.openxmlformats.org/markup-compatibility/2006"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
OFFICE_DOC_REL = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
)

ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
INT_RE = re.compile(r"^[+-]?\d+$")


class DataError(Exception):
    """An input file is missing or cannot be parsed."""

    def __init__(self, path, detail):
        super().__init__("%s: %s" % (path, detail))
        self.path = path
        self.detail = detail


# --------------------------------------------------------------------------- dates


def parse_iso(text):
    """Return a date for a strict YYYY-MM-DD string, else None."""
    if text is None:
        return None
    text = text.strip()
    if not ISO_DATE_RE.match(text):
        return None
    try:
        return datetime.date(int(text[0:4]), int(text[5:7]), int(text[8:10]))
    except ValueError:
        return None


def require_iso(path, text, what):
    value = parse_iso(text)
    if value is None:
        raise DataError(path, "%s is not an ISO date: %r" % (what, text))
    return value


def require_int(path, text, what):
    text = (text or "").strip()
    if not INT_RE.match(text):
        raise DataError(path, "%s is not a whole number: %r" % (what, text))
    return int(text)


# ---------------------------------------------------------------------- docx reader


def _understood_prefixes(raw_xml):
    """Map of namespace prefixes declared in the part to their namespace URI."""
    prefixes = {}
    for match in re.finditer(rb'xmlns:([A-Za-z0-9_.\-]+)\s*=\s*"([^"]*)"', raw_xml):
        prefixes[match.group(1).decode("utf-8")] = match.group(2).decode("utf-8")
    return prefixes


def _requires_understood(requires, prefix_map):
    """A reader of these files understands only the WordprocessingML main namespace."""
    names = (requires or "").split()
    if not names:
        return True
    for name in names:
        if prefix_map.get(name) != W_NS:
            return False
    return True


def _children_in_effect(elem, prefix_map):
    """Children of elem that carry current text, honouring mc:AlternateContent."""
    for child in list(elem):
        tag = child.tag
        if tag in ("{%s}del" % W_NS, "{%s}moveFrom" % W_NS):
            continue
        if tag == "{%s}AlternateContent" % MC_NS:
            chosen = None
            for alt in list(child):
                if alt.tag == "{%s}Choice" % MC_NS and _requires_understood(
                    alt.get("Requires"), prefix_map
                ):
                    chosen = alt
                    break
            if chosen is None:
                for alt in list(child):
                    if alt.tag == "{%s}Fallback" % MC_NS:
                        chosen = alt
                        break
            if chosen is None:
                continue
            for sub in _children_in_effect(chosen, prefix_map):
                yield sub
            continue
        yield child


def _current_text(elem, prefix_map, parts):
    if elem.tag == "{%s}t" % W_NS:
        if elem.text:
            parts.append(elem.text)
        return
    if elem.tag == "{%s}tab" % W_NS:
        parts.append("\t")
        return
    for child in _children_in_effect(elem, prefix_map):
        _current_text(child, prefix_map, parts)


def _collect_tables(elem, prefix_map, out):
    for child in _children_in_effect(elem, prefix_map):
        if child.tag == "{%s}tbl" % W_NS:
            out.append(child)
        _collect_tables(child, prefix_map, out)


def _table_rows(tbl, prefix_map):
    rows = []
    for tr in _children_in_effect(tbl, prefix_map):
        if tr.tag != "{%s}tr" % W_NS:
            continue
        cells = []
        for tc in _children_in_effect(tr, prefix_map):
            if tc.tag != "{%s}tc" % W_NS:
                continue
            parts = []
            _current_text(tc, prefix_map, parts)
            cells.append("".join(parts).strip())
        rows.append(cells)
    return rows


def read_docx_tables(path):
    """Return a list of tables; each table is a list of rows of cell strings."""
    if not os.path.isfile(path):
        raise DataError(path, "file is missing")
    try:
        with zipfile.ZipFile(path) as package:
            rels = package.read("_rels/.rels")
            rels_root = ET.fromstring(rels)
            target = None
            for rel in rels_root:
                if rel.tag != "{%s}Relationship" % PKG_REL_NS:
                    continue
                if rel.get("Type") == OFFICE_DOC_REL:
                    target = rel.get("Target")
                    break
            if target is None:
                raise DataError(path, "no officeDocument relationship in the package")
            name = target.lstrip("/")
            raw = package.read(name)
    except DataError:
        raise
    except (zipfile.BadZipFile, KeyError, ET.ParseError, OSError) as exc:
        raise DataError(path, "cannot be parsed (%s)" % (exc,))

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise DataError(path, "main document part cannot be parsed (%s)" % (exc,))
    prefix_map = _understood_prefixes(raw)
    tables = []
    _collect_tables(root, prefix_map, tables)
    return [_table_rows(tbl, prefix_map) for tbl in tables]


def table_by_header(path, tables, first_header_cell):
    """The table whose first header cell holds the given text."""
    for rows in tables:
        if rows and rows[0] and rows[0][0] == first_header_cell:
            return rows
    raise DataError(path, "no table with first header cell %r" % (first_header_cell,))


def rows_as_dicts(path, rows):
    header = rows[0]
    out = []
    for cells in rows[1:]:
        if not cells or all(cell == "" for cell in cells):
            continue
        if len(cells) < len(header):
            raise DataError(path, "table row has too few cells: %r" % (cells,))
        out.append(dict(zip(header, cells)))
    return out


# ----------------------------------------------------------------------- plain files


def read_text_file(path):
    if not os.path.isfile(path):
        raise DataError(path, "file is missing")
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as handle:
            return handle.read()
    except (OSError, UnicodeDecodeError) as exc:
        raise DataError(path, "cannot be read (%s)" % (exc,))


def read_csv_rows(path):
    text = read_text_file(path)
    try:
        reader = csv.DictReader(text.splitlines(True))
        if reader.fieldnames is None:
            raise DataError(path, "has no header line")
        rows = list(reader)
    except csv.Error as exc:
        raise DataError(path, "cannot be parsed (%s)" % (exc,))
    return [name.strip() for name in reader.fieldnames], rows


def require_columns(path, fieldnames, needed):
    missing = [name for name in needed if name not in fieldnames]
    if missing:
        raise DataError(path, "missing column(s): %s" % ", ".join(missing))


def read_fleet_limits(path):
    text = read_text_file(path)
    values = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("["):
            continue
        if "=" not in stripped:
            raise DataError(path, "cannot be parsed: %r" % (line,))
        key, raw = stripped.split("=", 1)
        key = key.strip()
        raw = raw.strip()
        if "#" in raw and not (raw.startswith('"') or raw.startswith("'")):
            raw = raw.split("#", 1)[0].strip()
        if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
            raw = raw[1:-1]
        values[key] = raw
    for key in ("season", "season_start", "season_end"):
        if key not in values:
            raise DataError(path, "missing key %r" % key)
    season_start = require_iso(path, values["season_start"], "season_start")
    season_end = require_iso(path, values["season_end"], "season_end")
    if season_end < season_start:
        raise DataError(path, "season_end is before season_start")
    return values["season"], season_start, season_end


def read_json_file(path):
    text = read_text_file(path)
    try:
        return json.loads(text)
    except ValueError as exc:
        raise DataError(path, "cannot be parsed (%s)" % (exc,))


def read_calendar(path):
    text = read_text_file(path)
    entries = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except ValueError as exc:
            raise DataError(path, "line %d cannot be parsed (%s)" % (number, exc))
        if not isinstance(obj, dict):
            raise DataError(path, "line %d is not an object" % number)
        for key in ("base", "date", "status"):
            if key not in obj:
                raise DataError(path, "line %d has no %r" % (number, key))
        entries.append(obj)
    return entries


# ----------------------------------------------------------------------------- input


class Inputs(object):
    pass


def load_inputs(data_dir):
    paths = {
        "limits": os.path.join(data_dir, "fleet_limits.toml"),
        "register": os.path.join(data_dir, "fleet_register.csv"),
        "requests": os.path.join(data_dir, "check_requests.csv"),
        "published": os.path.join(data_dir, "published_plan.csv"),
        "calendar": os.path.join(data_dir, "base_calendar.jsonl"),
        "notice": os.path.join(data_dir, "disruption_notice.docx"),
        "planning": os.path.join(data_dir, "planning_limits.docx"),
        "types": os.path.join(data_dir, "check_types.json"),
    }

    inp = Inputs()
    inp.season, inp.season_start, inp.season_end = read_fleet_limits(paths["limits"])

    fields, rows = read_csv_rows(paths["register"])
    require_columns(paths["register"], fields, ["tail", "aircraft_class", "status"])
    inp.register = {}
    for row in rows:
        tail = (row.get("tail") or "").strip()
        if tail == "" or tail in inp.register:
            continue
        inp.register[tail] = {
            "aircraft_class": (row.get("aircraft_class") or "").strip(),
            "status": (row.get("status") or "").strip(),
        }

    fields, inp.request_rows = read_csv_rows(paths["requests"])
    require_columns(
        paths["requests"],
        fields,
        [
            "request_id",
            "season",
            "tail",
            "check_type",
            "base",
            "available_from",
            "due_date",
            "duration_days",
            "status",
        ],
    )

    fields, rows = read_csv_rows(paths["published"])
    require_columns(paths["published"], fields, ["request_id", "published_start"])
    inp.published = {}
    for row in rows:
        rid = (row.get("request_id") or "").strip()
        if rid == "" or rid in inp.published:
            continue
        inp.published[rid] = (row.get("published_start") or "").strip()

    types = read_json_file(paths["types"])
    if not isinstance(types, dict):
        raise DataError(paths["types"], "is not an object")
    inp.check_types = {}
    for name, spec in types.items():
        if not isinstance(spec, dict):
            raise DataError(paths["types"], "entry %r is not an object" % name)
        for key in ("max_compress_days", "overtime_shifts_per_day"):
            if key not in spec:
                raise DataError(paths["types"], "entry %r has no %r" % (name, key))
        inp.check_types[name] = {
            "max_compress_days": int(spec["max_compress_days"]),
            "overtime_shifts_per_day": int(spec["overtime_shifts_per_day"]),
        }

    inp.calendar = read_calendar(paths["calendar"])

    notice_tables = read_docx_tables(paths["notice"])
    closures = rows_as_dicts(
        paths["notice"], table_by_header(paths["notice"], notice_tables, "base")
    )
    inp.closures = []
    for row in closures:
        base = row.get("base", "").strip()
        start = require_iso(paths["notice"], row.get("from"), "closure from")
        days = require_int(paths["notice"], row.get("days"), "closure days")
        inp.closures.append((base, start, days))
    availability = rows_as_dicts(
        paths["notice"], table_by_header(paths["notice"], notice_tables, "tail")
    )
    inp.revised_availability = {}
    for row in availability:
        tail = row.get("tail", "").strip()
        when = require_iso(
            paths["notice"], row.get("available_from"), "revised available_from"
        )
        if tail:
            inp.revised_availability[tail] = when

    planning_tables = read_docx_tables(paths["planning"])
    items = rows_as_dicts(
        paths["planning"], table_by_header(paths["planning"], planning_tables, "item")
    )
    item_values = {}
    for row in items:
        item_values[row.get("item", "").strip()] = row.get("value", "")
    for key in ("overtime_pool_shifts", "shift_cost"):
        if key not in item_values:
            raise DataError(paths["planning"], "no %r row" % key)
    inp.overtime_pool_shifts = require_int(
        paths["planning"], item_values["overtime_pool_shifts"], "overtime_pool_shifts"
    )
    inp.shift_cost = require_int(
        paths["planning"], item_values["shift_cost"], "shift_cost"
    )

    class_rows = rows_as_dicts(
        paths["planning"], table_by_header(paths["planning"], planning_tables, "class")
    )
    inp.rates = {}
    for row in class_rows:
        name = row.get("class", "").strip()
        if not name:
            continue
        inp.rates[name] = {
            "revenue_per_day": require_int(
                paths["planning"], row.get("revenue_per_day"), "revenue_per_day"
            ),
            "overdue_weight": require_int(
                paths["planning"], row.get("overdue_weight"), "overdue_weight"
            ),
            "deferral_penalty": require_int(
                paths["planning"], row.get("deferral_penalty"), "deferral_penalty"
            ),
        }
    inp.planning_path = paths["planning"]
    return inp


# -------------------------------------------------------------------------- screening


def screen_requests(inp):
    """Split the read rows of the season into accepted requests and rejected rows."""
    accepted = []
    rejected = []
    seen_ids = set()
    for line_number, row in enumerate(inp.request_rows, start=2):
        if (row.get("season") or "").strip() != inp.season:
            continue
        if (row.get("status") or "").strip() != "OPEN":
            continue
        rid = (row.get("request_id") or "").strip()
        base = (row.get("base") or "").strip()
        check_type = (row.get("check_type") or "").strip()
        tail = (row.get("tail") or "").strip()
        available_text = (row.get("available_from") or "").strip()
        due_text = (row.get("due_date") or "").strip()
        duration_text = (row.get("duration_days") or "").strip()

        reason = None
        if rid in seen_ids:
            reason = "duplicate_request"
        elif base not in BASES:
            reason = "unknown_base"
        elif check_type not in inp.check_types:
            reason = "unknown_check_type"
        elif tail not in inp.register:
            reason = "unknown_tail"
        elif inp.register[tail]["status"] == "RETIRED":
            reason = "retired_tail"
        elif parse_iso(available_text) is None or parse_iso(due_text) is None:
            reason = "bad_date"
        elif not INT_RE.match(duration_text) or int(duration_text) < 1:
            reason = "bad_duration"
        elif rid not in inp.published:
            reason = "no_published_start"

        if reason is not None:
            rejected.append({"request_id": rid, "line": line_number, "reason": reason})
            if reason != "duplicate_request":
                seen_ids.add(rid)
            continue

        seen_ids.add(rid)
        # The notice overrides the row's own available_from for the plan; the row's
        # own value is what the bad_date screen above looks at.
        available_day = inp.revised_availability.get(tail, parse_iso(available_text))
        aircraft_class = inp.register[tail]["aircraft_class"]
        if aircraft_class not in inp.rates:
            raise DataError(
                inp.planning_path, "no class row for %r" % (aircraft_class,)
            )
        accepted.append(
            {
                "request_id": rid,
                "tail": tail,
                "base": base,
                "check_type": check_type,
                "aircraft_class": aircraft_class,
                "segment": SEGMENT_OF_CLASS.get(aircraft_class),
                "available_from": available_day,
                "due_date": parse_iso(due_text),
                "duration_days": int(duration_text),
                "published_start": inp.published[rid],
            }
        )
    return accepted, rejected


# -------------------------------------------------------------------------- calendars


def build_calendars(inp):
    total_days = (inp.season_end - inp.season_start).days + 1
    closed = {base: [False] * total_days for base in BASES}
    nostart = {base: [False] * total_days for base in BASES}
    for entry in inp.calendar:
        base = str(entry["base"]).strip()
        if base not in BASES:
            continue
        day = parse_iso(str(entry["date"]))
        if day is None or day < inp.season_start or day > inp.season_end:
            continue
        index = (day - inp.season_start).days
        status = str(entry["status"]).strip()
        if status == "CLOSED":
            closed[base][index] = True
        elif status == "NO_START":
            nostart[base][index] = True
    for base, start, days in inp.closures:
        if base not in BASES or days < 1:
            continue
        for offset in range(days):
            day = start + datetime.timedelta(days=offset)
            if day < inp.season_start or day > inp.season_end:
                continue
            closed[base][(day - inp.season_start).days] = True
    return total_days, closed, nostart


# ----------------------------------------------------------------------- base solving


def compress_options(request, check_types):
    spec = check_types[request["check_type"]]
    limit = min(spec["max_compress_days"], request["duration_days"] - 1)
    if limit < 0:
        limit = 0
    return list(range(limit + 1)), spec["overtime_shifts_per_day"]


def build_feasibility(requests, total_days, closed, nostart, check_types,
                      season_start):
    """For every request and compression, the earliest feasible start from each day."""
    closed_prefix = [0] * (total_days + 1)
    for index in range(total_days):
        closed_prefix[index + 1] = closed_prefix[index] + (1 if closed[index] else 0)

    info = []
    for request in requests:
        options, shifts_per_day = compress_options(request, check_types)
        available = (request["available_from"] - season_start).days
        if available < 0:
            available = 0
        per_compress = {}
        for compress in options:
            length = request["duration_days"] - compress
            feasible = [False] * total_days
            for start in range(available, total_days):
                finish = start + length - 1
                if finish >= total_days:
                    break
                if closed[start] or nostart[start]:
                    continue
                if closed_prefix[finish + 1] - closed_prefix[start] > 0:
                    continue
                feasible[start] = True
            nxt = [None] * (total_days + 1)
            following = None
            for start in range(total_days - 1, -1, -1):
                if feasible[start]:
                    following = start
                nxt[start] = following
            nxt[total_days] = None
            per_compress[compress] = {
                "length": length,
                "feasible": feasible,
                "next": nxt,
                "shifts": compress * shifts_per_day,
            }
        info.append(
            {
                "request": request,
                "available": available,
                "options": options,
                "shifts_per_day": shifts_per_day,
                "per_compress": per_compress,
            }
        )
    return info


def overdue_days(finish_date, due_date):
    delta = (finish_date - due_date).days
    return delta if delta > 0 else 0


def solve_base(requests, total_days, closed, nostart, inp):
    """Best per-base plan for every exact overtime usage.

    Returns {shifts: (first, second, third, starts, finishes)} where starts and
    finishes are tuples of day indices in request_id order, with total_days (the day
    after season end) for a deferred request.
    """
    count = len(requests)
    deferred_day = total_days
    if count == 0:
        return {0: (0, 0, 0, (), ())}

    info = build_feasibility(
        requests, total_days, closed, nostart, inp.check_types, inp.season_start
    )

    published_index = []
    for request in requests:
        day = parse_iso(request["published_start"])
        if day is None or day < inp.season_start or day > inp.season_end:
            published_index.append(None)
        else:
            published_index.append((day - inp.season_start).days)

    rates = [inp.rates[request["aircraft_class"]] for request in requests]
    shift_cost = inp.shift_cost

    mask_indices = []
    for mask in range(1 << count):
        mask_indices.append(tuple(i for i in range(count) if mask & (1 << i)))

    def key_of(mask, value):
        indices = mask_indices[mask]
        first, second, third, starts, finishes = value
        return (
            first,
            second,
            third,
            tuple(starts[i] for i in indices),
            tuple(finishes[i] for i in indices),
        )

    empty_starts = (None,) * count
    initial = (0, 0, 0, empty_starts, empty_starts)
    # states[mask][free_day][shifts] = value
    states = {0: {0: {0: initial}}}
    masks_by_bits = sorted(range(1 << count), key=lambda m: bin(m).count("1"))

    for mask in masks_by_bits:
        by_free = states.get(mask)
        if not by_free:
            continue
        for free_day, by_shifts in by_free.items():
            if free_day >= total_days:
                continue
            for index in range(count):
                bit = 1 << index
                if mask & bit:
                    continue
                item = info[index]
                request = item["request"]
                rate = rates[index]
                lower = free_day if free_day > item["available"] else item["available"]
                if lower >= total_days:
                    continue
                for compress, plan in item["per_compress"].items():
                    earliest = plan["next"][lower]
                    if earliest is None:
                        continue
                    candidates = [earliest]
                    pub = published_index[index]
                    if (
                        pub is not None
                        and pub > earliest
                        and pub >= lower
                        and plan["feasible"][pub]
                    ):
                        candidates.append(pub)
                    length = plan["length"]
                    shifts_used = plan["shifts"]
                    ground_cost = length * rate["revenue_per_day"]
                    shift_money = shifts_used * shift_cost
                    for start in candidates:
                        finish = start + length - 1
                        finish_date = inp.season_start + datetime.timedelta(days=finish)
                        late = overdue_days(finish_date, request["due_date"])
                        add_first = late * rate["overdue_weight"]
                        add_second = ground_cost + shift_money
                        moved = 1 if pub != start else 0
                        new_mask = mask | bit
                        new_free = finish + 1
                        new_shifts = 0
                        target_bucket = states.setdefault(new_mask, {})
                        bucket = target_bucket.setdefault(new_free, {})
                        for shifts, value in by_shifts.items():
                            new_shifts = shifts + shifts_used
                            if new_shifts > inp.overtime_pool_shifts:
                                continue
                            starts = list(value[3])
                            finishes = list(value[4])
                            starts[index] = start
                            finishes[index] = finish
                            candidate = (
                                value[0] + add_first,
                                value[1] + add_second,
                                value[2] + moved,
                                tuple(starts),
                                tuple(finishes),
                            )
                            existing = bucket.get(new_shifts)
                            if existing is None or key_of(
                                new_mask, candidate
                            ) < key_of(new_mask, existing):
                                bucket[new_shifts] = candidate

    best = {}
    for mask, by_free in states.items():
        indices = set(mask_indices[mask])
        add_first = 0
        add_third = 0
        deferred = [i for i in range(count) if i not in indices]
        for index in deferred:
            add_first += rates[index]["deferral_penalty"]
            add_third += 1
        for by_shifts in by_free.values():
            for shifts, value in by_shifts.items():
                starts = list(value[3])
                finishes = list(value[4])
                for index in deferred:
                    starts[index] = deferred_day
                    finishes[index] = deferred_day
                final = (
                    value[0] + add_first,
                    value[1],
                    value[2] + add_third,
                    tuple(starts),
                    tuple(finishes),
                )
                current = best.get(shifts)
                if current is None or final < current:
                    best[shifts] = final
    return best


# -------------------------------------------------------------------- fleet assembly


def combine_bases(per_base, base_requests, pool):
    """Knapsack over the shared overtime pool, keeping the full lexicographic key."""
    states = {0: (0, 0, 0, {})}
    for base in BASES:
        options = per_base[base]
        requests = base_requests[base]
        if not options:
            return None
        nxt = {}
        for used, value in states.items():
            for shifts, plan in options.items():
                total = used + shifts
                if total > pool:
                    continue
                assignment = dict(value[3])
                for index, request in enumerate(requests):
                    assignment[request["request_id"]] = (
                        plan[3][index],
                        plan[4][index],
                    )
                candidate = (
                    value[0] + plan[0],
                    value[1] + plan[1],
                    value[2] + plan[2],
                    assignment,
                )
                current = nxt.get(total)
                if current is None or compare_key(candidate) < compare_key(current):
                    nxt[total] = candidate
        states = nxt
        if not states:
            return None
    best_used = None
    best_value = None
    for used, value in states.items():
        if best_value is None or compare_key(value) < compare_key(best_value):
            best_value = value
            best_used = used
    if best_value is None:
        return None
    return best_used, best_value


def compare_key(value):
    first, second, third, assignment = value
    ids = sorted(assignment)
    return (
        first,
        second,
        third,
        tuple(assignment[rid][0] for rid in ids),
        tuple(assignment[rid][1] for rid in ids),
    )


def deferral_reason(request, total_days, closed, nostart, inp):
    """`no_slot` when no compression fits on an otherwise empty line."""
    options, _ = compress_options(request, inp.check_types)
    available = (request["available_from"] - inp.season_start).days
    if available < 0:
        available = 0
    for compress in options:
        length = request["duration_days"] - compress
        for start in range(available, total_days):
            finish = start + length - 1
            if finish >= total_days:
                break
            if closed[start] or nostart[start]:
                continue
            if any(closed[day] for day in range(start, finish + 1)):
                continue
            return "plan_trade"
    return "no_slot"


# ------------------------------------------------------------------------- reporting


def write_json(path, payload):
    directory = os.path.dirname(path)
    if directory and not os.path.isdir(directory):
        os.makedirs(directory)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def empty_totals(fleet_overtime):
    return {
        "checks_scheduled": 0,
        "checks_deferred": 0,
        "compress_days": 0,
        "overtime_shifts": 0,
        "overdue_days": 0,
        "overdue_cost": 0,
        "deferral_cost": 0,
        "revenue_lost": 0,
        "moved": 0,
        "first_start": None,
        "last_finish": None,
        "fleet_overtime_used": fleet_overtime,
    }


def accumulate(totals, check, rate):
    if check["decision"] == "scheduled":
        totals["checks_scheduled"] += 1
        totals["compress_days"] += check["compress_days"]
        totals["overtime_shifts"] += check["overtime_shifts"]
        totals["overdue_days"] += check["overdue_days"]
        totals["overdue_cost"] += check["overdue_days"] * rate["overdue_weight"]
        totals["revenue_lost"] += check["days_on_ground"] * rate["revenue_per_day"]
        if totals["first_start"] is None or check["start_date"] < totals["first_start"]:
            totals["first_start"] = check["start_date"]
        if (
            totals["last_finish"] is None
            or check["finish_date"] > totals["last_finish"]
        ):
            totals["last_finish"] = check["finish_date"]
    else:
        totals["checks_deferred"] += 1
        totals["deferral_cost"] += rate["deferral_penalty"]
    if check["moved"]:
        totals["moved"] += 1


def main(argv=None):
    parser = argparse.ArgumentParser(description="Heavy hangar check replan")
    parser.add_argument("--data", default="/app/environment/data/")
    parser.add_argument("--out", default="/app/out/")
    args = parser.parse_args(argv)

    data_dir = args.data
    out_dir = args.out

    inp = load_inputs(data_dir)
    accepted, rejected = screen_requests(inp)
    total_days, closed, nostart = build_calendars(inp)

    base_requests = {base: [] for base in BASES}
    for request in sorted(accepted, key=lambda item: item["request_id"]):
        base_requests[request["base"]].append(request)

    per_base = {}
    for base in BASES:
        per_base[base] = solve_base(
            base_requests[base], total_days, closed[base], nostart[base], inp
        )

    combined = combine_bases(per_base, base_requests, inp.overtime_pool_shifts)
    if combined is None:
        raise DataError(data_dir, "no plan satisfies the stated rules")
    fleet_overtime, plan = combined
    first_term, second_term, third_term, assignment = plan

    checks = []
    by_request = {}
    for request in sorted(accepted, key=lambda item: item["request_id"]):
        rid = request["request_id"]
        start_index, finish_index = assignment[rid]
        rate = inp.rates[request["aircraft_class"]]
        if start_index >= total_days:
            check = {
                "request_id": rid,
                "tail": request["tail"],
                "base": request["base"],
                "check_type": request["check_type"],
                "aircraft_class": request["aircraft_class"],
                "segment": request["segment"],
                "decision": "deferred",
                "start_date": None,
                "finish_date": None,
                "compress_days": 0,
                "overtime_shifts": 0,
                "overdue_days": 0,
                "moved": True,
                "deferral_reason": deferral_reason(
                    request,
                    total_days,
                    closed[request["base"]],
                    nostart[request["base"]],
                    inp,
                ),
            }
            check["days_on_ground"] = 0
        else:
            length = finish_index - start_index + 1
            compress = request["duration_days"] - length
            shifts_per_day = inp.check_types[request["check_type"]][
                "overtime_shifts_per_day"
            ]
            start_date = inp.season_start + datetime.timedelta(days=start_index)
            finish_date = inp.season_start + datetime.timedelta(days=finish_index)
            check = {
                "request_id": rid,
                "tail": request["tail"],
                "base": request["base"],
                "check_type": request["check_type"],
                "aircraft_class": request["aircraft_class"],
                "segment": request["segment"],
                "decision": "scheduled",
                "start_date": start_date.isoformat(),
                "finish_date": finish_date.isoformat(),
                "compress_days": compress,
                "overtime_shifts": compress * shifts_per_day,
                "overdue_days": overdue_days(finish_date, request["due_date"]),
                "moved": start_date.isoformat() != request["published_start"],
                "deferral_reason": None,
            }
            check["days_on_ground"] = length
        by_request[rid] = (check, rate, request)
        checks.append(check)

    base_totals = {base: empty_totals(fleet_overtime) for base in BASES}
    segment_totals = {segment: empty_totals(fleet_overtime) for segment in SEGMENTS}
    for check in checks:
        entry, rate, request = by_request[check["request_id"]]
        accumulate(base_totals[request["base"]], entry, rate)
        segment = request["segment"]
        if segment in segment_totals:
            accumulate(segment_totals[segment], entry, rate)

    public_checks = [dict(check) for check in checks]
    for check in public_checks:
        check.pop("days_on_ground", None)

    write_json(
        os.path.join(out_dir, "check_plan.json"),
        {"season": inp.season, "checks": public_checks},
    )
    for base in BASES:
        payload = {"base": base}
        payload.update(base_totals[base])
        write_json(
            os.path.join(out_dir, "regions", "region_%s.json" % base.lower()), payload
        )
    for segment in SEGMENTS:
        payload = {"segment": segment}
        payload.update(segment_totals[segment])
        write_json(
            os.path.join(out_dir, "segments", "segment_%s.json" % segment), payload
        )

    scheduled_total = sum(base_totals[base]["checks_scheduled"] for base in BASES)
    deferred_total = sum(base_totals[base]["checks_deferred"] for base in BASES)
    moved_total = sum(base_totals[base]["moved"] for base in BASES)
    write_json(
        os.path.join(out_dir, "plan_summary.json"),
        {
            "season": inp.season,
            "plan_terms": {
                "first": first_term,
                "second": second_term,
                "third": third_term,
            },
            "overtime_pool_shifts": inp.overtime_pool_shifts,
            "fleet_overtime_used": fleet_overtime,
            "checks_scheduled": scheduled_total,
            "checks_deferred": deferred_total,
            "moved": moved_total,
            "bases": [
                {
                    "base": base,
                    "checks_scheduled": base_totals[base]["checks_scheduled"],
                    "checks_deferred": base_totals[base]["checks_deferred"],
                    "overtime_shifts": base_totals[base]["overtime_shifts"],
                }
                for base in BASES
            ],
            "segments": [
                {
                    "segment": segment,
                    "checks_scheduled": segment_totals[segment]["checks_scheduled"],
                    "checks_deferred": segment_totals[segment]["checks_deferred"],
                }
                for segment in SEGMENTS
            ],
        },
    )
    counts = {reason: 0 for reason in REJECT_REASONS}
    for row in rejected:
        counts[row["reason"]] = counts.get(row["reason"], 0) + 1
    write_json(
        os.path.join(out_dir, "data_quality.json"),
        {
            "rejected": [
                {
                    "request_id": row["request_id"],
                    "line": row["line"],
                    "reason": row["reason"],
                }
                for row in rejected
            ],
            "counts": counts,
        },
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except DataError as error:
        sys.stderr.write("error: %s\n" % (error,))
        sys.exit(1)
