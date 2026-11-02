#!/usr/bin/env python3
"""Reservation quota settlement for one extract of a settlement period.

Forms:
  python3 optimize.py DATA_DIR OUT_DIR   settle the period, write every report
  python3 optimize.py EVENTS_LOG RULES   print the result object of one class
  aggregate(events_path, rules_path)     return that result object

Every rule this program follows is in the documents of the extract (ct_svc.md,
st_demand.md, st_settle.md, st_bill.md, pr_num.md, fm_reports.md, lg_rqb.md).
"""

import hashlib
import json
import os
import re
import sqlite3
import struct
import sys
import zlib
import zipfile

CLASSES = ("visible", "peak", "steady", "burst", "latency")
EPOCH_DAYS = 20454  # days between 1970-01-01 and 2026-01-01
ADMISSIBLE_UNITS = tuple(range(1200, 5001, 100))


class ExtractError(Exception):
    """An invariant of the service contract is broken."""


# ---------------------------------------------------------------- time forms

def days_from_civil(y, m, d):
    y -= 1 if m <= 2 else 0
    era = (y if y >= 0 else y - 399) // 400
    yoe = y - era * 400
    doy = (153 * (m + (-3 if m > 2 else 9)) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def civil_from_days(z):
    z += 719468
    era = (z if z >= 0 else z - 146096) // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    y = yoe + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = mp + (3 if mp < 10 else -9)
    return y + (1 if m <= 2 else 0), m, d


def to_instant(sec):
    days, rem = divmod(sec, 86400)
    y, m, d = civil_from_days(days + EPOCH_DAYS)
    return "%04d-%02d-%02dT%02d:%02d:%02dZ" % (
        y, m, d, rem // 3600, rem // 60 % 60, rem % 60)


def from_instant(text):
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})Z", text)
    if not m:
        raise ExtractError("malformed instant " + text)
    y, mo, d, h, mi, se = (int(p) for p in m.groups())
    return (days_from_civil(y, mo, d) - EPOCH_DAYS) * 86400 + h * 3600 + mi * 60 + se


# ------------------------------------------------------------ RQB1 container

def read_unsigned(buf, pos):
    value = 0
    shift = 0
    while True:
        if pos >= len(buf):
            raise ExtractError("truncated unsigned number")
        byte = buf[pos]
        pos += 1
        value |= (byte & 0x7F) << shift
        shift += 7
        if not byte & 0x80:
            return value, pos


def read_signed(buf, pos):
    n, pos = read_unsigned(buf, pos)
    return (n >> 1) if not n & 1 else -((n + 1) >> 1), pos


def read_ascii(buf, pos):
    if pos >= len(buf):
        raise ExtractError("truncated text length")
    n = buf[pos]
    if pos + 1 + n > len(buf):
        raise ExtractError("truncated text")
    return buf[pos + 1:pos + 1 + n].decode("ascii"), pos + 1 + n


def _read_key_text(sel, keys, pos, buf):
    if sel & 16:
        ref, pos = read_unsigned(buf, pos)
        if ref >= len(keys):
            raise ExtractError("key back-reference out of range")
        return keys[len(keys) - 1 - ref], pos, keys
    text, pos = read_ascii(buf, pos)
    if text not in keys:
        keys.append(text)
    return text, pos, keys


def _read_model_text(sel, models, pos, buf):
    if sel & 64:
        index, pos = read_unsigned(buf, pos)
        if index >= len(models):
            raise ExtractError("model index out of range")
        return models[index], pos, models
    text, pos = read_ascii(buf, pos)
    if text not in models:
        models.append(text)
    return text, pos, models


def parse_log(path):
    """Read one request log into a list of request tuples."""
    with open(path, "rb") as handle:
        buf = handle.read()
    keys, models, requests = [], [], []
    base, declared = log_header(path, buf)
    class_code, prefix = buf[5], buf[6:8].decode("ascii")
    running, last_key, last_model, pos = base, None, None, 21
    while pos < len(buf):
        sel = buf[pos]
        pos += 1
        if sel & 128:
            raise ExtractError("selector bit 7 set in " + os.path.basename(path))
        mode, status = sel & 3, (sel >> 2) & 3
        if status == 3:
            raise ExtractError("status outside the contract in " + os.path.basename(path))
        if mode == 3:
            if sel != 3:
                raise ExtractError("malformed filler in " + os.path.basename(path))
            continue
        extra = None
        if sel & 32:
            extra, pos = class_byte(path, buf, pos)
        number, pos = read_unsigned(buf, pos)
        if mode == 2:
            key, model = last_key, last_model
            if key is None:
                raise ExtractError("repeat record opens the log")
        else:
            key, pos, keys = _read_key_text(sel, keys, pos, buf)
            model, pos, models = _read_model_text(sel, models, pos, buf)
        prompt, pos = read_unsigned(buf, pos)
        completion, pos = read_unsigned(buf, pos)
        delta, pos = read_signed(buf, pos)
        running = base + delta if mode == 0 else running + delta
        last_key, last_model = key, model
        requests.append((
            "rq-%s%05d" % (prefix, number), key, model, prompt, completion,
            running, status, CLASSES[extra if extra is not None else class_code]))
    if len(requests) != declared:
        raise ExtractError("record count mismatch in " + os.path.basename(path))
    if not requests:
        raise ExtractError("empty request log " + os.path.basename(path))
    return requests


def log_header(path, buf):
    """Check the header of one request log and give its base instant and count."""
    name = os.path.basename(path)
    if len(buf) < 21:
        raise ExtractError("short request log " + name)
    if buf[0:4] != b"RQB1" or buf[4] != 1:
        raise ExtractError("bad magic or version in " + name)
    if buf[5] >= len(CLASSES):
        raise ExtractError("bad class code in " + name)
    base = struct.unpack(">I", buf[8:12])[0]
    declared = struct.unpack(">I", buf[12:16])[0]
    stored = struct.unpack(">I", buf[17:21])[0]
    if zlib.crc32(buf[16:17] + buf[21:]) != stored:
        raise ExtractError("checksum mismatch in " + name)
    return base, declared


def class_byte(path, buf, pos):
    """The class byte a record carries, checked against the class order."""
    if pos >= len(buf):
        raise ExtractError("truncated class byte in " + os.path.basename(path))
    code = buf[pos]
    if code >= len(CLASSES):
        raise ExtractError("bad class byte in " + os.path.basename(path))
    return code, pos + 1


def merge_logs(class_name, logs):
    """Requests of one class: those of all its logs, one request per req_id."""
    merged, origin, order = {}, {}, []
    for index, requests in enumerate(logs):
        for request in requests:
            rid = request[0]
            if rid in merged:
                if origin[rid] == index or merged[rid] != request:
                    raise ExtractError("req_id " + rid + " is not one request")
                continue
            merged[rid], origin[rid] = request, index
            order.append(rid)
    if not order:
        raise ExtractError("no request in " + class_name)
    return [merged[rid] for rid in order]


# ------------------------------------------------------------ delimited text

def read_delimited(text, delimiter, name="sheet"):
    """Rows of a comma, tab or bar separated sheet, RFC 4180 quoting."""
    rows, row, field, quoted = [], [], [], False
    index = 0
    while index < len(text):
        ch = text[index]
        if quoted:
            if ch == '"':
                if index + 1 < len(text) and text[index + 1] == '"':
                    field.append('"')
                    index += 2
                    continue
                quoted = False
                index += 1
                continue
            field.append(ch)
            index += 1
            continue
        if ch == '"' and not field:
            quoted = True
            index += 1
            continue
        if ch == delimiter:
            row.append("".join(field))
            field = []
            index += 1
            continue
        if ch in "\r\n":
            row.append("".join(field))
            rows.append(row)
            row, field = [], []
            index += 2 if ch == "\r" and text[index + 1:index + 2] == "\n" else 1
            continue
        field.append(ch)
        index += 1
    if quoted:
        raise ExtractError("unterminated quote in " + name)
    if field or row:
        row.append("".join(field))
        rows.append(row)
    if rows and not any(rows[-1]):
        rows.pop()
    return rows


def split_columns(path, delimiter):
    """Rows of a delimited text sheet, RFC 4180 quoting, no header handling."""
    with open(path, encoding="utf-8") as handle:
        raw = handle.read()
    if not raw:
        raise ExtractError("empty delimited file " + os.path.basename(path))
    return read_delimited(raw, delimiter, os.path.basename(path))


# ------------------------------------------------------- Office Open XML

def xml_text(data):
    return re.sub(r"<[^>]*>", "", data)


def read_ooxml_table(path, part):
    """Rows of the one table of a Word document, as lists of strings."""
    with zipfile.ZipFile(path) as archive:
        document = archive.read(part).decode("utf-8")
    rows = []
    for row in re.findall(r"<w:tr\b.*?</w:tr>", document, re.S):
        cells = []
        for cell in re.findall(r"<w:tc>.*?</w:tc>", row, re.S):
            cells.append("".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", cell, re.S)))
        if not cells:
            raise ExtractError("table row without cells in " + os.path.basename(path))
        rows.append([xml_text(c) for c in cells])
    if not rows:
        raise ExtractError("no table in " + os.path.basename(path))
    return rows


def read_sheet_rows(sheet):
    """Rows of one worksheet, as lists of strings."""
    rows = []
    for row in re.findall(r"<row\b[^>]*>(.*?)</row>|<row\b[^>]*/>", sheet, re.S):
        cells = []
        for cell in re.findall(r"<c\b[^>]*(?:/>|>.*?</c>)", row, re.S):
            inline = re.search(r"<t[^>]*>(.*?)</t>", cell, re.S)
            plain = re.search(r"<v>(.*?)</v>", cell, re.S)
            cells.append(inline.group(1) if inline else (plain.group(1) if plain else ""))
        rows.append([xml_text(c) for c in cells])
    return rows


def workbook_sheets(path):
    """Map every sheet name of a workbook to its worksheet part name."""
    with zipfile.ZipFile(path) as archive:
        workbook = archive.read("xl/workbook.xml").decode("utf-8")
        rels = archive.read("xl/_rels/workbook.xml.rels").decode("utf-8")
    targets = {}
    for rid, target in re.findall(r'Id="([^"]+)"[^>]*Target="([^"]+)"', rels):
        targets[rid] = target
    result = {}
    for name, rid in re.findall(
            r'<sheet\b[^>]*?name="([^"]+)"[^>]*?r:id="([^"]+)"', workbook):
        target = targets.get(rid)
        if target is None:
            raise ExtractError("missing relationship for sheet " + name)
        part = target.lstrip("/")
        if not part.startswith("xl/"):
            part = "xl/" + part
        result[name] = part
    return result


def read_rate_card(path):
    """Rate rows of the sheet rates, as (class, date, ru, over, round) tuples."""
    sheets = workbook_sheets(path)
    part = sheets.get("rates")
    if part is None:
        raise ExtractError("no sheet rates in " + os.path.basename(path))
    with zipfile.ZipFile(path) as archive:
        sheet = archive.read(part).decode("utf-8")
    rows = read_sheet_rows(sheet)
    if not rows:
        raise ExtractError("empty rate card")
    header = ["traffic_class", "eff_from", "ru_rate_micro",
              "over_rate_micro", "round_fee_micro"]
    if rows[0][:5] != header:
        raise ExtractError("unexpected rate card header")
    rates = []
    for row in rows[1:]:
        if len(row) < 5:
            raise ExtractError("short rate row")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", row[1]):
            raise ExtractError("bad effective date " + row[1])
        rates.append((row[0], row[1], int(row[2]), int(row[3]), int(row[4])))
    return rates


def read_word_table(path, columns):
    """Map the first column of a Word table to the remaining columns."""
    rows = read_ooxml_table(path, "word/document.xml")
    if rows[0][:len(columns)] != list(columns):
        raise ExtractError("unexpected table header in " + os.path.basename(path))
    table = {}
    for row in rows[1:]:
        key = row[0]
        if key in table:
            raise ExtractError("duplicate key " + key + " in " + os.path.basename(path))
        table[key] = row[1:]
    return table


# ---------------------------------------------------------------- PDF meter

def _pdf_streams(raw):
    """The content of every stream of a PDF, decompressed where it is filtered."""
    chunks = []
    for match in re.finditer(rb"\bstream\r?\n", raw):
        end = raw.find(b"endstream", match.end())
        if end < 0:
            raise ExtractError("unterminated PDF stream")
        head = raw[raw.rfind(b" obj", 0, match.start()):match.start()]
        data = raw[match.end():end].rstrip(b"\r\n")
        if b"FlateDecode" in head:
            data = zlib.decompress(data)
        chunks.append(data)
    if not chunks:
        raise ExtractError("no content stream in the meter sheet")
    return b"\n".join(chunks)


def read_meter_sheet(path):
    """Readings of the meter sheet: (id, instant, ru, keys) tuples."""
    with open(path, "rb") as handle:
        raw = handle.read()
    if raw[0:5] != b"%PDF-":
        raise ExtractError("not a PDF meter sheet")
    body = _pdf_streams(raw)
    readings = []
    for line in re.findall(rb"\((.*?)\) Tj", body, re.S):
        text = line.decode("latin-1")
        parts = text.split(" ")
        if len(parts) < 4 or parts[0] != "reading":
            continue
        reading_id, instant, value = parts[1], parts[2], parts[3]
        if not re.fullmatch(r"M\d+", reading_id):
            raise ExtractError("bad reading id " + reading_id)
        readings.append((reading_id, instant, int(value), parts[4:]))
    if not readings:
        raise ExtractError("no reading in " + os.path.basename(path))
    return readings



# ------------------------------------------------------------- corrections

def read_corrections(rules_dir, files, cutoff):
    """Correction entries of both layers: amendments by seq, then overrides by seq."""
    amendment_rows = split_columns(os.path.join(rules_dir, files["amendments"]), "\t")
    if not amendment_rows:
        raise ExtractError("empty amendment layer")
    if amendment_rows[0][:5] != ["seq", "tenant", "traffic_class", "field", "value"]:
        raise ExtractError("unexpected amendment header")
    amendments = []
    for row in amendment_rows[1:]:
        if len(row) != 5:
            raise ExtractError("short amendment row")
        amendments.append(("amendment", int(row[0]), row[1], row[2], row[3], row[4]))
    amendments.sort(key=lambda entry: entry[1])
    overrides = []
    with open(os.path.join(rules_dir, files["overrides"]), encoding="utf-8") as handle:
        for line in handle.read().split("\n"):
            if not line:
                continue
            record = json.loads(line)
            overrides.append(("override", int(record["seq"]), record["tenant"],
                             record["traffic_class"], record["field"], str(record["value"])))
    overrides.sort(key=lambda entry: entry[1])
    entries = amendments + overrides
    for entry in entries:
        if entry[4] not in ("contracted_ru", "pool", "retired"):
            raise ExtractError("unknown correction field " + entry[4])
    seqs = [entry[1] for entry in entries]
    if len(set(seqs)) != len(seqs):
        raise ExtractError("two correction entries share a seq")
    return entries


def apply_corrections(tenant_rows, entries, cutoff):
    """Return corrected rows keyed by (class, tenant)."""
    latest = {}
    for entry in entries:
        _, seq, tenant, cls, field, value = entry
        if seq > cutoff or (cls, tenant) not in tenant_rows:
            continue
        marker = (field, cls, tenant)
        if entry[0] == "override":
            latest[marker] = value
        elif marker not in latest:
            latest[marker] = value
    corrected = {}
    for key, row in tenant_rows.items():
        corrected[key] = dict(row)
    for (field, cls, tenant), value in latest.items():
        row = corrected[(cls, tenant)]
        if field == "contracted_ru":
            if not re.fullmatch(r"-?\d+", value):
                raise ExtractError("bad contracted_ru " + value)
            row["contracted_ru"] = int(value)
        elif field == "pool":
            row["pool"] = value
        else:
            if value not in ("yes", "no"):
                raise ExtractError("bad retired value " + value)
            row["retired"] = 1 if value == "yes" else 0
    return corrected


def correction_statuses(entries, tenant_rows, cutoff):
    """Statuses of every correction entry, in the order of the layers."""
    result = []
    for entry in entries:
        layer, seq, tenant, cls, field, _ = entry
        if seq > cutoff:
            status = "cutoff"
        elif (cls, tenant) not in tenant_rows:
            status = "unmatched"
        else:
            status = "applied"
        result.append({"layer": layer, "seq": seq, "tenant": tenant,
                       "class": cls, "field": field, "status": status})
    return result


# ---------------------------------------------------------------- register

def load_register(rules_dir, files):
    """Tenant rows, pool rows and the alias table of the register."""
    database = os.path.join(rules_dir, files["register"])
    if not os.path.exists(database):
        raise ExtractError("no register database in the extract")
    connection = sqlite3.connect("file:" + database + "?mode=ro", uri=True)
    try:
        tenant_rows = {}
        for code, cls, pool, contracted, retired in connection.execute(
                "select code, traffic_class, pool, contracted_ru, retired from tenant"):
            key = (cls, code)
            if key in tenant_rows:
                raise ExtractError("two tenant rows for " + code + " in " + cls)
            tenant_rows[key] = {"code": code, "class": cls, "pool": pool,
                                "contracted_ru": int(contracted), "retired": int(retired)}
        pool_rows = {}
        for pool_id, cls, grp in connection.execute(
                "select pool_id, traffic_class, grp from pool"):
            if pool_id in pool_rows:
                raise ExtractError("duplicate pool id " + pool_id)
            pool_rows[pool_id] = {"pool": pool_id, "class": cls, "grp": grp}
        aliases = {}
        seen = set()
        for key, tenant, eff_from in connection.execute(
                "select api_key, tenant, eff_from from alias"):
            marker = (key, eff_from)
            if marker in seen:
                raise ExtractError("two alias rows share key and instant")
            seen.add(marker)
            aliases.setdefault(key, []).append((from_instant(eff_from), tenant))
    finally:
        connection.close()
    for key in aliases:
        aliases[key].sort()
    return tenant_rows, pool_rows, aliases


def load_pool_parameters(rules_dir, files, pool_rows):
    """Pool table: pool rows joined on the crosswalk and the pool profiles."""
    crosswalk = {}
    rows = split_columns(os.path.join(rules_dir, files["crosswalk"]), ",")
    if not rows or rows[0][:2] != ["grp", "prof_code"]:
        raise ExtractError("unexpected crosswalk header")
    for row in rows[1:]:
        if len(row) < 2:
            raise ExtractError("short crosswalk row")
        crosswalk[row[0]] = row[1]
    profiles = read_word_table(os.path.join(rules_dir, files["profiles"]),
                               ["prof_code", "start_step", "patience", "budget"])
    for prof in crosswalk.values():
        if prof not in profiles:
            raise ExtractError("profile code " + prof + " absent from the profiles")
    table = {}
    for pool_id, row in pool_rows.items():
        grp = row["grp"]
        if crosswalk.get(grp) is None:
            raise ExtractError("group " + grp + " absent from the crosswalk")
        prof = crosswalk[grp]
        if prof not in profiles:
            raise ExtractError("profile code " + prof + " absent from the profiles")
        values = profiles[prof]
        params = [int(v) for v in values[:3]]
        if any(v < 1 for v in params):
            raise ExtractError("profile parameter below one")
        table[pool_id] = dict(row, start_step=params[0], patience=params[1], budget=params[2])
    groups = [row["grp"] for row in pool_rows.values()]
    for grp in set(groups):
        found = [row for row in rows[1:] if row[0] == grp]
        if len(found) != 1:
            raise ExtractError("group " + grp + " is not once in the crosswalk")
    return table



# ------------------------------------------------------------ demand stage

def alias_tenant(aliases, key, instant):
    """The tenant the alias row in force gives, or None."""
    best = None
    for eff_from, tenant in aliases.get(key, ()):
        if eff_from <= instant and (best is None or eff_from > best[0]):
            best = (eff_from, tenant)
    return None if best is None else best[1]


def round_half_to_zero(numerator, denominator):
    """numerator / denominator rounded to the nearest whole, halves to zero."""
    sign = -1 if numerator < 0 else 1
    value, rest = divmod(numerator * sign, denominator)
    return sign * (value + (1 if rest * 2 > denominator else 0))


def rounded_up(numerator, denominator):
    return -((-numerator) // denominator)


def request_units(request, weights):
    """Token units of one request, zero when it is rejected."""
    _, _, model, prompt, completion, _, status, _ = request
    if model not in weights:
        raise ExtractError("model " + model + " missing from the weight table")
    prompt_weight, completion_weight = weights[model]
    units = prompt * prompt_weight
    if status == 0:
        units += completion * completion_weight
    return units


def class_requests(class_name, requests, window, weights, members, aliases):
    """Sort the requests of one class into counted, rejected, orphan and other."""
    start, end = window
    counted, other = [], []
    by_tenant, by_model = {}, {}
    totals = {"in_window": 0, "out_of_window": 0, "rejected": 0, "orphan": 0}
    for request in requests:
        instant = request[5]
        if not start < instant <= end:
            totals["out_of_window"] += 1
            other.append((request, "out_of_window"))
            continue
        totals["in_window"] += 1
        if request[6] == 2:
            totals["rejected"] += 1
            other.append((request, "rejected"))
            continue
        tenant = alias_tenant(aliases, request[1], instant)
        member = members.get((class_name, tenant))
        if member is None:
            totals["orphan"] += 1
            other.append((request, "orphan"))
            continue
        counted.append(request)
        units = request_units(request, weights)
        by_tenant[tenant] = by_tenant.get(tenant, 0) + units
        stats = by_model.setdefault(request[2], [0, 0])
        stats[0] += 1
        stats[1] += units
    return {"counted": counted, "other": other, "units": by_tenant,
            "models": by_model, "totals": totals}


# -------------------------------------------------------- calibration stage

def cumulative_units(scope, logs, windows, weights, members, aliases):
    """Member token units from counted requests, sorted by instant."""
    entries = {}
    for class_name in scope:
        start, end = windows[class_name]
        for request in logs[class_name]:
            if request[6] == 2 or not start < request[5] <= end:
                continue
            tenant = alias_tenant(aliases, request[1], request[5])
            marker = (class_name, tenant)
            if marker not in members:
                continue
            entries.setdefault(marker, []).append((request[5], request_units(request, weights)))
    return entries


def cumulative_sums(entries):
    """For every member, its units to each instant, as a sorted cumulative table."""
    tables = {}
    for marker, history in entries.items():
        history = sorted(history)
        instants, running, totals = [], 0, []
        for instant, units in history:
            running += units
            instants.append(instant)
            totals.append(running)
        tables[marker] = (instants, totals)
    return tables


def member_units_at(tables, marker, cut):
    """Units of one member from its counted requests completed at or before cut."""
    instants, totals = tables.get(marker, ((), ()))
    low, high = 0, len(instants)
    while low < high:
        middle = (low + high) // 2
        if instants[middle] <= cut:
            low = middle + 1
        else:
            high = middle
    return totals[low - 1] if low else 0


def reading_members(readings, aliases, members, tables):
    """For every reading, the members with units its keys reach."""
    result = []
    for _, instant, _, keys in readings:
        cut = from_instant(instant)
        reached = set()
        for key in keys:
            tenant = alias_tenant(aliases, key, cut)
            for class_name in CLASSES:
                marker = (class_name, tenant)
                if marker in members and member_units_at(tables, marker, cut) > 0:
                    reached.add((members[marker]["pool"], marker))
        result.append((cut, sorted(reached)))
    return result


def calibrate_units(values, reached, tables, needed_pools):
    """The one assignment of admissible units per RU that meets every reading."""
    contributions = [
        [(pool, member_units_at(tables, marker, cut))
         for pool, marker in members_reached] for cut, members_reached in reached]
    needed = sorted({pool for contribution in contributions for pool, _ in contribution})
    if set(needed_pools) - set(needed):
        raise ExtractError("the meter readings settle no assignment of units per RU")
    candidates = {pool: list(ADMISSIBLE_UNITS) for pool in needed}
    _filter_candidates(candidates, contributions, values)
    solutions = []
    _calibrate_search(candidates, needed, contributions, values, 0, {}, solutions)
    if not solutions:
        raise ExtractError("the meter readings settle no assignment of units per RU")
    if len(solutions) > 1:
        raise ExtractError("the meter readings settle more than one assignment of units per RU")
    return solutions[0]


def _own_contribution(contribution, pool, candidate):
    """The part of one reading one pool covers, member by member."""
    return sum(rounded_up(units, candidate)
               for other, units in contribution if other == pool)


def _rest_range(candidates, contribution, pool):
    """The interval the members of other pools can cover in one reading."""
    low = high = 0
    for other, units in contribution:
        if other == pool:
            continue
        options = candidates.get(other)
        if not options:
            return None
        low += rounded_up(units, max(options))
        high += rounded_up(units, min(options))
    return (low, high)


def _filter_candidates(candidates, contributions, values):
    """Drop every candidate some reading cannot meet, until none is left."""
    changed = True
    while changed:
        changed = False
        for value, contribution in zip(values, contributions):
            for pool in sorted({other for other, _ in contribution}):
                rest = _rest_range(candidates, contribution, pool)
                keep = []
                for candidate in candidates[pool]:
                    own = _own_contribution(contribution, pool, candidate)
                    if rest[0] <= value - own <= rest[1]:
                        keep.append(candidate)
                if len(keep) != len(candidates[pool]):
                    candidates[pool] = keep
                    changed = True
                if not keep:
                    return


def _reading_total(contribution, assign):
    """The value of one reading under one assignment."""
    return sum(rounded_up(units, assign[pool]) for pool, units in contribution)


def _calibrate_search(candidates, needed, contributions, values,
                      index, assign, solutions):
    """Collect the assignments that meet every reading, two at the most."""
    if len(solutions) > 1:
        return
    if index == len(needed):
        for value, contribution in zip(values, contributions):
            if _reading_total(contribution, assign) != value:
                return
        solutions.append(dict(assign))
        return
    pool = needed[index]
    for candidate in list(candidates[pool]):
        assign[pool] = candidate
        feasible = True
        for value, contribution in zip(values, contributions):
            if pool not in {other for other, _ in contribution}:
                continue
            low = high = _own_contribution(contribution, pool, candidate)
            for other, units in contribution:
                if other == pool:
                    continue
                options = candidates.get(other)
                if not options:
                    feasible = False
                    break
                chosen = assign.get(other)
                low += rounded_up(units, chosen if chosen else max(options))
                high += rounded_up(units, chosen if chosen else min(options))
            if not feasible or low > value or high < value:
                feasible = False
                break
        if feasible:
            _calibrate_search(candidates, needed, contributions, values,
                              index + 1, assign, solutions)
        del assign[pool]


def pools_needing_units(per_class, members):
    """Every pool with a member whose token units are not zero."""
    pools = set()
    for class_name, data in per_class.items():
        for tenant, units in data["units"].items():
            if units > 0:
                pools.add(members[(class_name, tenant)]["pool"])
    return pools


# --------------------------------------------------------- settlement stage

def compute_targets(names, holdings, demands, pool_total):
    """Targets of a round: the pool total shared in proportion to demand."""
    total_demand = sum(demands)
    if total_demand == 0:
        return list(holdings)
    bases = [pool_total * demand // total_demand for demand in demands]
    rests = [pool_total * demand % total_demand for demand in demands]
    leftover = pool_total - sum(bases)
    order = sorted(range(len(names)),
                   key=lambda i: (-rests[i], -holdings[i], names[i]))
    targets = list(bases)
    for index in order[:leftover]:
        targets[index] += 1
    return targets


def round_movements(names, holdings, targets, residuals, step):
    """Movements a round yields after the correction that makes them sum to zero."""
    raw = [round_half_to_zero(residual * step, 4) for residual in residuals]
    total = sum(raw)
    if total:
        distance = [abs(target - (holding + move))
                    for target, holding, move in zip(targets, holdings, raw)]
        chosen = min(range(len(names)), key=lambda i: (-distance[i], names[i]))
        raw[chosen] -= total
    return raw


def settle_pool(pool, members, demands):
    """Settle one pool: its exit, rounds, final step, holdings and round trace."""
    names = [member["code"] for member in members]
    holdings = [member["contracted_ru"] for member in members]
    pool_total = sum(holdings)
    step, patience_count, closed = pool["start_step"], 0, 0
    trace, history = [], [tuple(holdings)]
    previous = None
    while True:
        targets = compute_targets(names, holdings, demands, pool_total)
        residuals = [target - holding for target, holding in zip(targets, holdings)]
        residual_total = sum(abs(residual) for residual in residuals)
        if previous is not None and residual_total >= previous:
            patience_count += 1
        if patience_count >= pool["patience"]:
            step = step // 2 if step > 1 else 1
            patience_count = 0
        trace.append([len(trace), residual_total, step])
        if residual_total == 0:
            return _pool_result(pool, "settled", len(trace) - 1, step, holdings, trace)
        movements = round_movements(names, holdings, targets, residuals, step)
        if not any(movements):
            return _pool_result(pool, "stalled", len(trace) - 1, step, holdings, trace)
        holdings = [holding + move for holding, move in zip(holdings, movements)]
        state = tuple(holdings)
        if state in history:
            cycle = history[history.index(state):] + [state]
            return _pool_result(pool, "cycled", -1, step, list(min(cycle)), trace)
        history.append(state)
        closed += 1
        if closed >= pool["budget"]:
            return _pool_result(pool, "budget", pool["budget"], step, holdings, trace)
        previous = residual_total


def _pool_result(pool, exit_name, rounds, step, holdings, trace):
    """The settlement result of one pool."""
    return {"exit": exit_name, "rounds": rounds, "final_step": step,
            "holdings": holdings, "trace": trace, "budget": pool["budget"]}


def settle_class(class_name, pool_table, members, demands_by_tenant):
    """Settle every pool of one class that has members after corrections."""
    pools = []
    for pool_id in sorted(pool_table):
        pool = pool_table[pool_id]
        if pool["class"] != class_name:
            continue
        pool_members = [members[key] for key in sorted(members)
                        if key[0] == class_name and members[key]["pool"] == pool_id]
        if not pool_members:
            continue
        demands = [demands_by_tenant.get(member["code"], 0) for member in pool_members]
        pools.append((pool_id, settle_pool(pool, pool_members, demands), pool_members))
    return pools


# -------------------------------------------------------------- billing stage

def rate_row_for(rates, class_name, window_end):
    """The rate row of a class in force at the date part of its window end."""
    day = to_instant(window_end)[:10]
    best = None
    for row in rates:
        if row[0] != class_name:
            continue
        if row[1] <= day and (best is None or row[1] > best[1]):
            best = row
    if best is None:
        raise ExtractError("no rate row in force for " + class_name)
    return {"eff_from": best[1], "ru_rate_micro": best[2],
            "over_rate_micro": best[3], "round_fee_micro": best[4]}


def orchestration_shares(charge, names):
    """A pool charge shared in whole micro-credits among its members."""
    count = len(names)
    base, rest = divmod(charge, count)
    return [base + (1 if index < rest else 0) for index in range(count)]


def build_bill_lines(class_name, pools, units_by_tenant, units_per_ru, rate):
    """One bill line per member of every settled pool of the class."""
    lines = []
    for pool_id, result, pool_members in pools:
        names = [member["code"] for member in pool_members]
        rounds = result["rounds"]
        charged = rounds if rounds != -1 else result["budget"]
        shares = orchestration_shares(rate["round_fee_micro"] * charged, names)
        for index, member in enumerate(pool_members):
            settled = result["holdings"][index]
            token_units = units_by_tenant.get(member["code"], 0)
            per_ru = units_per_ru.get(pool_id)
            overage = token_units - settled * per_ru if per_ru else 0
            if overage < 0:
                overage = 0
            reservation = settled * rate["ru_rate_micro"]
            overage_micro = rounded_up(overage * rate["over_rate_micro"], 1000)
            lines.append({
                "traffic_class": class_name, "pool": pool_id,
                "tenant": member["code"], "settled_ru": settled,
                "token_units": token_units, "overage_units": overage,
                "reservation_micro": reservation, "overage_micro": overage_micro,
                "orchestration_micro": shares[index],
                "total_micro": reservation + overage_micro + shares[index]})
    return lines


def class_billing(lines):
    """Totals over the bill lines of one class."""
    totals = {"lines": len(lines), "reservation_micro": 0, "overage_micro": 0,
              "orchestration_micro": 0, "total_micro": 0}
    for line in lines:
        for key in ("reservation_micro", "overage_micro",
                    "orchestration_micro", "total_micro"):
            totals[key] += line[key]
    return totals



# ------------------------------------------------------------ the whole run

def load_control(rules_path):
    """The control file of the extract and the folder it lives in."""
    with open(rules_path, encoding="utf-8") as handle:
        control = json.load(handle)
    for key in ("label", "cutoff_seq", "review_shift_ru", "windows", "files"):
        if key not in control:
            raise ExtractError("control file lacks " + key)
    for name in CLASSES:
        if name not in control["windows"]:
            raise ExtractError("control file lacks the window of " + name)
    return control


def find_logs(rules_dir):
    """The request logs of the extract, keyed by class, in class order."""
    logs = {}
    for name in sorted(os.listdir(rules_dir)):
        if not name.startswith("ev_") or not name.endswith(".rqb"):
            continue
        requests = parse_log(os.path.join(rules_dir, name))
        class_name = requests[0][7]
        for request in requests:
            if request[7] != class_name:
                raise ExtractError(name + " names two classes")
        logs.setdefault(class_name, []).append(requests)
    return logs


def check_scope(logs, windows):
    """Merge the logs of each class and list the classes in scope in class order."""
    for class_name in logs:
        if class_name not in windows:
            raise ExtractError("no window for " + class_name)
        merged = merge_logs(class_name, logs[class_name])
        if not merged:
            raise ExtractError("no request in " + class_name)
        logs[class_name] = merged
    return [name for name in CLASSES if name in logs]


def build_run(rules_path):
    """Settle the whole period: every figure every report needs."""
    control = load_control(rules_path)
    rules_dir = os.path.dirname(os.path.abspath(rules_path))
    files = control["files"]
    cutoff = int(control["cutoff_seq"])
    windows = {name: (from_instant(pair[0]), from_instant(pair[1]))
               for name, pair in control["windows"].items()}
    tenant_rows, pool_rows, aliases = load_register(rules_dir, files)
    entries = read_corrections(rules_dir, files, cutoff)
    corrected = apply_corrections(tenant_rows, entries, cutoff)
    pool_table = load_pool_parameters(rules_dir, files, pool_rows)
    for key, row in corrected.items():
        pool = pool_table.get(row["pool"])
        if pool is None or pool["class"] != row["class"]:
            raise ExtractError("pool " + row["pool"] + " is not a pool of " + row["class"])
    weights = {name: (int(values[0]), int(values[1])) for name, values in
               read_word_table(os.path.join(rules_dir, files["weights"]),
                               ["model", "prompt_weight", "completion_weight"]).items()}
    rates = read_rate_card(os.path.join(rules_dir, files["rates"]))
    logs = find_logs(rules_dir)
    scope = check_scope(logs, windows)
    for class_name in scope:
        for request in logs[class_name]:
            if request[2] not in weights:
                raise ExtractError("model " + request[2] + " missing from the weight table")
    members = {key: row for key, row in corrected.items() if not row["retired"]}
    readings = read_meter_sheet(os.path.join(rules_dir, files["units"]))
    return {"control": control, "rules_dir": rules_dir, "windows": windows,
            "corrected": corrected, "pool_table": pool_table, "aliases": aliases,
            "entries": entries, "weights": weights, "rates": rates, "scope": scope,
            "logs": logs, "members": members, "readings": readings}



# ----------------------------------------------------------- byte forms

def json_report(value):
    """A JSON report as fm_reports.md defines the byte form."""
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("utf-8")


def quoted_field(text):
    """One field of a CSV report, quoted only when it must be."""
    if any(mark in text for mark in (",", '"', "\n")):
        return '"' + text.replace('"', '""') + '"'
    return text


def delimited_report(rows, delimiter, quoted):
    """A CSV, TSV or PSV report: a header row and one line feed per row."""
    lines = []
    for row in rows:
        fields = [quoted_field(str(field)) if quoted else str(field) for field in row]
        lines.append(delimiter.join(fields) + "\n")
    return "".join(lines).encode("utf-8")


def xml_escape(value):
    text = str(value)
    for old, new in (("&", "&amp;"), ("<", "&lt;"), (">", "&gt;"), ('"', "&quot;")):
        text = text.replace(old, new)
    return text


def xml_report(root, elements):
    """An XML report: a root element holding childless elements."""
    head = '<?xml version="1.0" encoding="UTF-8"?>\n'
    if not elements:
        return (head + "<%s/>\n" % root).encode("utf-8")
    lines = [head, "<%s>\n" % root]
    for name, attributes in elements:
        rendered = " ".join('%s="%s"' % (key, xml_escape(value))
                            for key, value in attributes)
        lines.append("  <%s %s/>\n" % (name, rendered))
    lines.append("</%s>\n" % root)
    return "".join(lines).encode("utf-8")


def padded_report(rows, widths):
    """A plain text report of space padded columns."""
    lines = []
    for row in rows:
        cells = []
        for index, value in enumerate(row):
            cells.append(str(value).rjust(widths[index]) if index >= 2 else
                         str(value).ljust(widths[index]))
        lines.append("".join(cells) + "\n")
    return "".join(lines).encode("utf-8")



# --------------------------------------------------- report data assembly

def settle_run(run):
    """Complete every stage of the run over the classes in scope."""
    logs, windows, members = run["logs"], run["windows"], run["members"]
    scope = run["scope"]
    per_class = {}
    for class_name in scope:
        per_class[class_name] = class_requests(
            class_name, logs[class_name], windows[class_name],
            run["weights"], members, run["aliases"])
    tables = cumulative_sums(cumulative_units(
        scope, logs, windows, run["weights"], members, run["aliases"]))
    readings = run["readings"]
    reached = reading_members(readings, run["aliases"], members, tables)
    units_per_ru = calibrate_units([reading[2] for reading in readings], reached, tables,
                                    pools_needing_units(per_class, members))
    for class_name in scope:
        requests = per_class[class_name]
        demands = _member_demands(class_name, requests, members, units_per_ru)
        pools = settle_class(class_name, run["pool_table"], members, demands)
        rate = rate_row_for(run["rates"], class_name, windows[class_name][1])
        lines = build_bill_lines(class_name, pools, requests["units"], units_per_ru, rate)
        result = result_object(run["control"]["label"], class_name, requests, pools, demands)
        per_class[class_name] = dict(requests, pools=pools,
                                     demands=demands, rate=rate, lines=lines,
                                     billing=class_billing(lines), result=result)
    return per_class, units_per_ru


def _member_demands(class_name, requests, members, units_per_ru):
    """Demand in RU of every member of the class with counted requests."""
    demands = {}
    for tenant, units in requests["units"].items():
        pool = members[(class_name, tenant)]["pool"]
        demands[tenant] = rounded_up(units, units_per_ru[pool])
    return demands


def member_rows(per_class):
    """Every member of every settled pool: class, pool, tenant order."""
    rows = []
    for class_name in CLASSES:
        data = per_class.get(class_name)
        if not data:
            continue
        for pool_id, result, pool_members in data["pools"]:
            for index, member in enumerate(pool_members):
                rows.append((class_name, pool_id, member, result, index))
    return rows


def bill_lines(per_class):
    """Every bill line of the run in class, pool, tenant order."""
    lines = []
    for class_name in CLASSES:
        data = per_class.get(class_name)
        if data:
            lines.extend(data["lines"])
    return lines


def retired_rows(run):
    """Tenant rows of classes in scope that are retired after corrections."""
    scope = run["scope"]
    rows = []
    for class_name in CLASSES:
        for key, row in run["corrected"].items():
            if row["class"] == class_name and class_name in scope and row["retired"]:
                rows.append((class_name, row["code"]))
    return rows


def prior_settled(rules_dir, files):
    """The settled reservations of the earlier run, as a class, tenant map."""
    path = os.path.join(rules_dir, files["prior"])
    with open(path, encoding="utf-8") as handle:
        prior = json.load(handle)
    return {class_name: dict(values)
            for class_name, values in prior.get("settled", {}).items()}


def scenario_reports(run, per_class):
    """One scenario report per traffic class."""
    reports = {}
    for class_name in CLASSES:
        data = per_class.get(class_name)
        if data is None:
            body = {"traffic_class": class_name, "in_scope": False}
        else:
            body = {"traffic_class": class_name, "in_scope": True,
                    "window": list(run["control"]["windows"][class_name]),
                    "result": data["result"],
                    "bill_total_micro": data["billing"]["total_micro"]}
        reports["scenario_%s.json" % class_name] = json_report(body)
    return reports


def pool_rows(per_class):
    """One row per settled pool, in class then pool order."""
    rows = []
    for class_name in CLASSES:
        data = per_class.get(class_name)
        if not data:
            continue
        for pool_id, result, pool_members in data["pools"]:
            rows.append([class_name, pool_id, len(pool_members), result["exit"],
                         result["rounds"], result["final_step"],
                         sum(member["contracted_ru"] for member in pool_members)])
    return rows


def round_trace_rows(per_class):
    """One row per round every settled pool opened."""
    rows = []
    for class_name in CLASSES:
        data = per_class.get(class_name)
        if not data:
            continue
        for pool_id, result, _ in data["pools"]:
            for number, residual_total, step in result["trace"]:
                rows.append([class_name, pool_id, number, residual_total, step])
    return rows


def pool_members_report(per_class):
    """Every class in scope mapped to its pools and their member codes."""
    body = {}
    for class_name in CLASSES:
        data = per_class.get(class_name)
        if not data:
            continue
        body[class_name] = {pool_id: [member["code"] for member in pool_members]
                            for pool_id, _, pool_members in data["pools"]}
    return json_report(body)


def rate_application_report(per_class, units_per_ru):
    """The rate row in force and the units per RU of every class in scope."""
    body = {}
    for class_name in CLASSES:
        data = per_class.get(class_name)
        if not data:
            continue
        rate = {key: data["rate"][key] for key in
                ("eff_from", "ru_rate_micro", "over_rate_micro", "round_fee_micro")}
        rate["units_per_ru"] = {pool_id: units_per_ru[pool_id]
                                for pool_id, _, pool_members in data["pools"]
                                if pool_id in units_per_ru}
        body[class_name] = rate
    return json_report(body)


def class_billing_report(per_class):
    """The totals over the bill lines of every class in scope."""
    return json_report({class_name: per_class[class_name]["billing"]
                        for class_name in CLASSES if class_name in per_class})


def reconciliation_report(per_class, ledger_totals):
    """The check of the bill lines, the class totals and the ledger."""
    body = {}
    for class_name in CLASSES:
        data = per_class.get(class_name)
        if not data:
            continue
        lines_total = sum(line["total_micro"] for line in data["lines"])
        class_total = data["billing"]["total_micro"]
        members = data["pools"]
        ru_residual = 0
        for pool_id, result, pool_members in members:
            for index, member in enumerate(pool_members):
                ru_residual += result["holdings"][index] - member["contracted_ru"]
        body[class_name] = {
            "bill_lines_total": lines_total, "class_total": class_total,
            "ledger_total": ledger_totals.get(class_name, 0),
            "residual_micro": lines_total + ledger_totals.get(class_name, 0) - 2 * class_total,
            "ru_residual": ru_residual}
    return json_report(body)



def perf_report(run, per_class):
    """Classes in scope, settled pools, their members and counted requests."""
    pools = len(pool_rows(per_class))
    members = len(member_rows(per_class))
    counted = sum(len(per_class[name]["counted"]) for name in per_class)
    return json_report({"classes_in_scope": run["scope"], "counted_requests": counted,
                        "member_count": members, "pool_count": pools})


def bottleneck_report(per_class):
    """The pools that run longest, those unsettled and those stalled."""
    rows = pool_rows(per_class)
    longest, unsettled, stalled = [], [], []
    best = None
    for row in rows:
        if best is None or row[4] > best:
            best = row[4]
    for row in rows:
        if row[4] == best:
            longest.append([row[0], row[1], row[4]])
        if row[3] in ("cycled", "budget"):
            unsettled.append([row[0], row[1], row[3]])
        if row[3] == "stalled":
            stalled.append([row[0], row[1]])
    return json_report({"longest": longest, "stalled": stalled, "unsettled": unsettled})


def recommendations_report(run, per_class):
    """Every member whose settled reservation moved at least the threshold."""
    threshold = int(run["control"]["review_shift_ru"])
    actions = []
    for class_name, pool_id, member, result, index in member_rows(per_class):
        settled = result["holdings"][index]
        shift = settled - member["contracted_ru"]
        if abs(shift) < threshold:
            continue
        actions.append([class_name, member["code"],
                        "raise" if shift > 0 else "lower", shift])
    return json_report({"actions": actions, "review_shift_ru": threshold})


def data_quality_report(run, per_class, statuses):
    """Orphan, out of window and rejected requests, retired rows, corrections."""
    counts = {"orphan_requests": {}, "out_of_window": {}, "rejected_requests": {}}
    for class_name in run["scope"]:
        data = per_class[class_name]
        totals = data["totals"]
        counts["orphan_requests"][class_name] = totals["orphan"]
        counts["out_of_window"][class_name] = totals["out_of_window"]
        counts["rejected_requests"][class_name] = totals["rejected"]
    corrections = {"applied": 0, "cutoff": 0, "unmatched": 0}
    for status in statuses:
        corrections[status["status"]] += 1
    body = dict(counts)
    body["corrections"] = corrections
    body["retired_members"] = [list(row) for row in retired_rows(run)]
    return json_report(body)


def exit_summary_report(per_class):
    """The number of pools of every exit, per class in scope."""
    elements = []
    for class_name in CLASSES:
        data = per_class.get(class_name)
        if not data:
            continue
        tally = {"settled": 0, "stalled": 0, "cycled": 0, "budget": 0}
        for pool_id, result, _ in data["pools"]:
            tally[result["exit"]] += 1
        elements.append(("class", [("name", class_name), ("settled", tally["settled"]),
                                  ("stalled", tally["stalled"]),
                                  ("cycled", tally["cycled"]),
                                  ("budget", tally["budget"])]))
    return xml_report("exits", elements)


def holding_shift_report(per_class):
    """One element per member whose settled reservation moved."""
    elements = []
    for class_name, pool_id, member, result, index in member_rows(per_class):
        settled = result["holdings"][index]
        if settled == member["contracted_ru"]:
            continue
        elements.append(("shift", [("class", class_name), ("pool", pool_id),
                                   ("tenant", member["code"]),
                                   ("from", member["contracted_ru"]),
                                   ("to", settled),
                                   ("delta", settled - member["contracted_ru"])]))
    return xml_report("shifts", elements)


def invoice_lines_report(per_class):
    """One entry per bill line, as the invoice YAML file."""
    lines = []
    for line in bill_lines(per_class):
        lines.append("- class: %s\n  tenant: %s\n  total_micro: %d\n"
                      % (line["traffic_class"], line["tenant"], line["total_micro"]))
    return "".join(lines).encode("utf-8")


def invoice_digest_report(per_class):
    """The digest of every class in scope, as the markdown file."""
    chunks = []
    for class_name in CLASSES:
        data = per_class.get(class_name)
        if not data:
            continue
        chunk = "## %s\n\n| tenant | total_micro |\n|---|---:|\n" % class_name
        for line in data["lines"]:
            chunk += "| %s | %d |\n" % (line["tenant"], line["total_micro"])
        chunks.append(chunk)
    return "\n".join(chunks).encode("utf-8")


def overage_report(per_class):
    """One line per bill line with positive overage units."""
    rows = [[line["traffic_class"], line["tenant"],
             line["overage_units"], line["overage_micro"]]
            for line in bill_lines(per_class) if line["overage_units"] > 0]
    return padded_report(rows, (10, 12, 12, 14))


def tenant_bills_rows(per_class):
    """The rows of tenant_bills.csv."""
    rows = [["traffic_class", "pool", "tenant", "settled_ru", "token_units",
             "overage_units", "reservation_micro", "overage_micro",
             "orchestration_micro", "total_micro"]]
    for line in bill_lines(per_class):
        rows.append([line["traffic_class"], line["pool"], line["tenant"],
                     line["settled_ru"], line["token_units"], line["overage_units"],
                     line["reservation_micro"], line["overage_micro"],
                     line["orchestration_micro"], line["total_micro"]])
    return rows


def demand_by_model_rows(per_class):
    """One row per class in scope and model with at least one counted request."""
    rows = [["traffic_class", "model", "counted_requests", "token_units"]]
    for class_name in CLASSES:
        data = per_class.get(class_name)
        if not data:
            continue
        for model in sorted(data["models"]):
            counted, units = data["models"][model]
            rows.append([class_name, model, counted, units])
    return rows


def orphans_rows(per_class):
    """One row per request that adds nothing to demand."""
    rows = [["traffic_class", "req_id", "reason"]]
    for class_name in CLASSES:
        data = per_class.get(class_name)
        if not data:
            continue
        entries = sorted((request[0], reason) for request, reason in data["other"])
        rows.extend([class_name, req_id, reason] for req_id, reason in entries)
    return rows


def window_counts_rows(run, per_class):
    """One row per class in scope with its window counts."""
    rows = [["traffic_class", "in_window", "out_of_window"]]
    for class_name in run["scope"]:
        totals = per_class[class_name]["totals"]
        rows.append([class_name, totals["in_window"], totals["out_of_window"]])
    return rows


def corrections_rows(entries, tenant_rows, cutoff):
    """The rows of corrections_applied.csv."""
    rows = [["layer", "seq", "tenant", "traffic_class", "field", "status"]]
    for status in correction_statuses(entries, tenant_rows, cutoff):
        rows.append([status["layer"], status["seq"], status["tenant"],
                     status["class"], status["field"], status["status"]])
    return rows


def delta_prior_rows(run, per_class):
    """The rows of delta_prior.csv: settled against the earlier run."""
    prior = prior_settled(run["rules_dir"], run["control"]["files"])
    rows = [["traffic_class", "tenant", "settled_ru", "prior_ru", "delta_ru"]]
    for class_name, pool_id, member, result, index in member_rows(per_class):
        settled = result["holdings"][index]
        old = prior.get(class_name, {}).get(member["code"])
        if old is None:
            rows.append([class_name, member["code"], settled, "", ""])
        else:
            rows.append([class_name, member["code"], settled, old, settled - old])
    return rows


def tenant_holdings_rows(per_class):
    """The rows of tenant_holdings.tsv."""
    rows = [["traffic_class", "pool", "tenant", "contracted_ru", "demand_ru", "settled_ru"]]
    for class_name, pool_id, member, result, index in member_rows(per_class):
        demands = per_class[class_name]["demands"]
        rows.append([class_name, pool_id, member["code"], member["contracted_ru"],
                     demands.get(member["code"], 0), result["holdings"][index]])
    return rows




# ----------------------------------------------------- database and workbook

def ledger_database(path, per_class):
    """Write the billing ledger and return its dump with its class totals."""
    rows = [(line["traffic_class"], line["tenant"], line["total_micro"])
            for line in bill_lines(per_class)]
    pools = [(row[0], row[1], row[3], row[4]) for row in pool_rows(per_class)]
    if os.path.exists(path):
        os.remove(path)
    connection = sqlite3.connect(path)
    try:
        connection.execute("create table bills ("
                           "traffic_class TEXT, tenant TEXT, total_micro INTEGER)")
        connection.execute("create table pools ("
                           "traffic_class TEXT, pool TEXT, exit TEXT, rounds INTEGER)")
        connection.executemany("insert into bills values (?,?,?)", rows)
        connection.executemany("insert into pools values (?,?,?,?)", pools)
        connection.commit()
    finally:
        connection.close()
    dump = ["table bills\n"]
    for row in rows:
        dump.append("\t".join(str(value) for value in row) + "\n")
    dump.append("table pools\n")
    for row in pools:
        dump.append("\t".join(str(value) for value in row) + "\n")
    totals = {}
    for class_name, _, total in rows:
        totals[class_name] = totals.get(class_name, 0) + total
    return "".join(dump).encode("utf-8"), totals


def _sheet_xml(rows):
    """The worksheet XML of the bills sheet: text and number cells."""
    lines = ['<worksheet xmlns="http://schemas.openxmlformats.org/'
             'spreadsheetml/2006/main"><sheetData>']
    for number, row in enumerate(rows, 1):
        cells = ['<row r="%d">' % number]
        for index, value in enumerate(row, 1):
            name = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[index - 1]
            if isinstance(value, str):
                cells.append('<c r="%s%d" t="inlineStr"><is><t>%s</t></is></c>'
                             % (name, number, xml_escape(value)))
            else:
                cells.append('<c r="%s%d"><v>%d</v></c>' % (name, number, value))
        cells.append("</row>")
        lines.append("".join(cells))
    lines.append("</sheetData></worksheet>")
    return "".join(lines)


def write_zip(path, parts):
    """A zip file of the given parts, byte for byte the same every time."""
    if os.path.exists(path):
        os.remove(path)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in parts:
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            archive.writestr(info, content)


def billing_book(path, per_class):
    """Write the billing workbook and return its dump."""
    header = ["traffic_class", "tenant", "reservation_micro", "overage_micro",
              "orchestration_micro", "total_micro"]
    rows = [header]
    for line in bill_lines(per_class):
        rows.append([line["traffic_class"], line["tenant"], line["reservation_micro"],
                     line["overage_micro"], line["orchestration_micro"],
                     line["total_micro"]])
    sheet = ('<?xml version="1.0" encoding="UTF-8"?>\n' + _sheet_xml(rows)).encode("utf-8")
    content_types = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                     '<Types xmlns="http://schemas.openxmlformats.org/package/2006/'
                     'content-types"><Default Extension="rels" ContentType="application/'
                     'vnd.openxmlformats-package.relationships+xml"/>'
                     '<Default Extension="xml" ContentType="application/xml"/>'
                     '<Override PartName="/xl/workbook.xml" ContentType="application/'
                     'vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                     '<Override PartName="/xl/worksheets/sheet1.xml" ContentType='
                     '"application/vnd.openxmlformats-officedocument.spreadsheetml.'
                     'worksheet+xml"/></Types>').encode("utf-8")
    rels = ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
            'relationships"><Relationship Id="rId1" Type="http://schemas.'
            'openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="xl/workbook.xml"/></Relationships>').encode("utf-8")
    workbook = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/'
                'main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/'
                'relationships"><sheets><sheet name="bills" sheetId="1" r:id="rId1"/>'
                '</sheets></workbook>').encode("utf-8")
    sheet_rels = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                  '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
                  'relationships"><Relationship Id="rId1" Type="http://schemas.'
                  'openxmlformats.org/officeDocument/2006/relationships/worksheet" '
                  'Target="worksheets/sheet1.xml"/></Relationships>').encode("utf-8")
    write_zip(path, [("[Content_Types].xml", content_types), ("_rels/.rels", rels),
                     ("xl/workbook.xml", workbook),
                     ("xl/_rels/workbook.xml.rels", sheet_rels),
                     ("xl/worksheets/sheet1.xml", sheet)])
    dump = "".join("\t".join(str(value) for value in row) + "\n" for row in rows)
    return dump.encode("utf-8")




# ------------------------------------------------------------- write reports

def text_reports(run, per_class, units_per_ru):
    """Every text report of the run, keyed by file name."""
    cutoff = int(run["control"]["cutoff_seq"])
    reports = scenario_reports(run, per_class)
    reports["perf_report.json"] = perf_report(run, per_class)
    reports["bottleneck_analysis.json"] = bottleneck_report(per_class)
    reports["recommendations.json"] = recommendations_report(run, per_class)
    statuses = correction_statuses(run["entries"], run["corrected"], cutoff)
    reports["data_quality.json"] = data_quality_report(run, per_class, statuses)
    reports["pool_settlement.csv"] = delimited_report(
        [["traffic_class", "pool", "members", "exit", "rounds", "final_step",
          "pool_total_ru"]] + pool_rows(per_class), ",", True)
    reports["tenant_holdings.tsv"] = delimited_report(
        tenant_holdings_rows(per_class), "\t", False)
    reports["round_trace.psv"] = delimited_report(
        [["traffic_class", "pool", "round", "residual_total", "step"]] +
        round_trace_rows(per_class), "|", False)
    reports["exit_summary.xml"] = exit_summary_report(per_class)
    reports["pool_members.json"] = pool_members_report(per_class)
    reports["holding_shift.xml"] = holding_shift_report(per_class)
    reports["tenant_bills.csv"] = delimited_report(tenant_bills_rows(per_class), ",", True)
    reports["class_billing.json"] = class_billing_report(per_class)
    reports["invoice_lines.yaml"] = invoice_lines_report(per_class)
    reports["invoice_digest.md"] = invoice_digest_report(per_class)
    reports["overage.txt"] = overage_report(per_class)
    reports["rate_application.json"] = rate_application_report(per_class, units_per_ru)
    reports["delta_prior.csv"] = delimited_report(delta_prior_rows(run, per_class), ",", True)
    reports["demand_by_model.tsv"] = delimited_report(demand_by_model_rows(per_class), "\t", False)
    reports["orphans.csv"] = delimited_report(orphans_rows(per_class), ",", True)
    reports["corrections_applied.csv"] = delimited_report(
        corrections_rows(run["entries"], run["corrected"], cutoff), ",", True)
    reports["window_counts.csv"] = delimited_report(window_counts_rows(run, per_class), ",", True)
    return reports


def write_reports(out_dir, run, per_class, units_per_ru):
    """Write every report of the run, the manifest last of all."""
    os.makedirs(out_dir, exist_ok=True)
    reports = text_reports(run, per_class, units_per_ru)
    ledger_dump, ledger_totals = ledger_database(
        os.path.join(out_dir, "billing_ledger.sqlite"), per_class)
    book_dump = billing_book(os.path.join(out_dir, "billing_book.xlsx"), per_class)
    reports["reconciliation.json"] = reconciliation_report(per_class, ledger_totals)
    for name, content in sorted(reports.items()):
        with open(os.path.join(out_dir, name), "wb") as handle:
            handle.write(content)
    digests = {name: hashlib.sha256(content).hexdigest()
               for name, content in reports.items()}
    digests["billing_ledger.sqlite"] = hashlib.sha256(ledger_dump).hexdigest()
    digests["billing_book.xlsx"] = hashlib.sha256(book_dump).hexdigest()
    manifest = json_report({"reports": digests})
    with open(os.path.join(out_dir, "manifest.json"), "wb") as handle:
        handle.write(manifest)
    return sorted(digests)


def aggregate(events_path, rules_path):
    """The result object of the class of one request log."""
    run = build_run(rules_path)
    class_name = parse_log(events_path)[0][7]
    if class_name not in run["logs"]:
        raise ExtractError("no request log of " + class_name + " in the extract")
    per_class, _ = settle_run(run)
    return per_class[class_name]["result"]


def main(argv):
    """The two entry points of the program."""
    if len(argv) == 3 and os.path.isdir(argv[1]):
        run = build_run(_control_path(argv[1]))
        per_class, units_per_ru = settle_run(run)
        write_reports(argv[2], run, per_class, units_per_ru)
        return 0
    if len(argv) == 3:
        result = aggregate(argv[1], argv[2])
        sys.stdout.write(json.dumps(result, sort_keys=True, ensure_ascii=True,
                                     separators=(", ", ": ")) + "\n")
        return 0
    sys.stderr.write("usage: optimize.py DATA_DIR OUT_DIR | "
                     "optimize.py EVENTS_LOG RULES_JSON\n")
    return 2


def _control_path(data_dir):
    """The control file of an extract folder."""
    for name in sorted(os.listdir(data_dir)):
        if name.startswith("ctl_") and name.endswith(".json"):
            return os.path.join(data_dir, name)
    raise ExtractError("no control file in " + data_dir)


def result_object(label, class_name, requests, pools, demands):
    """The result object of one class, as fm_reports.md defines it."""
    pool_objects = []
    for pool_id, result, pool_members in pools:
        pool_objects.append({
            "pool": pool_id, "exit": result["exit"], "rounds": result["rounds"],
            "final_step": result["final_step"],
            "members": [{"tenant": member["code"],
                         "contracted_ru": member["contracted_ru"],
                         "demand_ru": demands.get(member["code"], 0),
                         "settled_ru": result["holdings"][index]}
                        for index, member in enumerate(pool_members)]})
    return {"label": label, "traffic_class": class_name,
            "counted_requests": len(requests["counted"]),
            "token_units": sum(requests["units"].values()),
            "pools": pool_objects}


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except ExtractError as error:
        sys.stderr.write("extract rejected: %s\n" % error)
        sys.exit(1)
    except (OSError, ValueError, TypeError, KeyError, IndexError,
            zipfile.BadZipFile, sqlite3.Error, zlib.error) as error:
        sys.stderr.write("extract rejected: %s: %s\n"
                         % (type(error).__name__, error))
        sys.exit(1)

